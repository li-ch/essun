"""Evidence store: append-only, content-addressed run records and claim
links (task T006), the counterexample / figure / reproduction-bundle
extensions (G6), plus the orchestrator routing integration.
"""

import hashlib
import json
from pathlib import Path

import pytest

from essun.evidence.store import EvidenceError, EvidenceStore, canonical_json

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"

PAYLOAD = {
    "experiment_id": "EXP-TEST-STORE",
    "code_version": "0.1.0",
    "inputs": {},
    "observables_digest": hashlib.sha256(b"obs").hexdigest(),
}
OBSERVATIONS = {
    "backend_id": "analytical_l0",
    "observables": {"O-CONSERVATION": {"kind": "exact", "violations": 0}},
}

COUNTEREXAMPLE = {
    "run_ids": [],  # filled per-test with real run_ids
    "observable": "O1-LATENCY-US",
    "description": "L0 and DES disagree on exposed time at ring size 8",
    "cause_class": "modeling_assumption",
    "minimized_case_ref": None,
}


def test_put_run_is_content_addressed(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    expected = hashlib.sha256(canonical_json(PAYLOAD).encode("utf-8")).hexdigest()
    assert run_id == expected
    record = json.loads((tmp_path / run_id / "run.json").read_text(encoding="utf-8"))
    assert record["run_id"] == run_id
    assert record["experiment_id"] == "EXP-TEST-STORE"
    observations = json.loads(
        (tmp_path / run_id / "observations.json").read_text(encoding="utf-8")
    )
    assert observations == OBSERVATIONS
    # Same serialization contract as the previous run-record format.
    assert (tmp_path / run_id / "run.json").read_bytes().endswith(b"\n")


def test_put_run_same_bytes_is_idempotent(tmp_path):
    store = EvidenceStore(tmp_path)
    first = store.put_run(PAYLOAD, OBSERVATIONS)
    second = store.put_run(PAYLOAD, OBSERVATIONS)
    assert first == second
    assert store.list_runs() == [first]


def test_put_run_rejects_same_id_different_bytes(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    # Identical payload (hence identical run_id) with different observations
    # bytes: the store must refuse to overwrite.
    with pytest.raises(EvidenceError, match="append-only violation"):
        store.put_run(PAYLOAD, {**OBSERVATIONS, "extra": 1})


def test_put_run_rejects_partially_written_record(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    (store.run_dir(run_id) / "observations.json").unlink()
    with pytest.raises(EvidenceError, match="missing"):
        store.put_run(PAYLOAD, OBSERVATIONS)


def test_different_payload_is_a_new_run_not_a_conflict(tmp_path):
    store = EvidenceStore(tmp_path)
    first = store.put_run(PAYLOAD, OBSERVATIONS)
    second = store.put_run({**PAYLOAD, "experiment_id": "EXP-TEST-STORE-2"}, OBSERVATIONS)
    assert first != second
    assert store.list_runs() == sorted([first, second])


def test_get_run_roundtrip(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    assert store.get_run(run_id)["run_id"] == run_id
    with pytest.raises(EvidenceError, match="no run record"):
        store.get_run("0" * 64)


def test_list_runs_empty_root(tmp_path):
    assert EvidenceStore(tmp_path / "nothere").list_runs() == []


def test_link_run_to_claim_appends_index(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    store.link_run_to_claim(run_id, "C2", relation="declared_by_manifest")
    assert store.claim_links() == [
        {"run_id": run_id, "claim_id": "C2", "relation": "declared_by_manifest"}
    ]
    index_bytes = (tmp_path / "claims_index.jsonl").read_bytes()
    assert index_bytes.endswith(b"\n")


def test_link_run_to_claim_identical_link_is_idempotent(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    store.link_run_to_claim(run_id, "C2")
    store.link_run_to_claim(run_id, "C2")  # replay appends nothing
    assert store.claim_links() == [
        {"run_id": run_id, "claim_id": "C2", "relation": "supports"}
    ]


def test_link_run_to_claim_different_claim_appends_line(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    store.link_run_to_claim(run_id, "C2")
    store.link_run_to_claim(run_id, "C1")
    links = store.claim_links()
    assert len(links) == 2
    assert links[0]["claim_id"] == "C2"
    assert links[1]["claim_id"] == "C1"


def test_link_unknown_run_rejected(tmp_path):
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="not in the store"):
        store.link_run_to_claim("f" * 64, "C2")


def test_orchestrator_routes_through_store_and_links_claim(tmp_path):
    # End-to-end: run_experiment persists via the evidence store, gates
    # observables through the registry, and links the run to the manifest
    # claim. Replaying into the same root stays idempotent (determinism
    # through the store path).
    from essun.orchestrator.runs import run_experiment

    result = run_experiment(MANIFEST, results_root=tmp_path)
    store = EvidenceStore(tmp_path)
    assert store.list_runs() == [result["run_id"]]
    assert store.claim_links() == [
        {
            "run_id": result["run_id"],
            "claim_id": "C2",
            "relation": "declared_by_manifest",
        }
    ]

    replay = run_experiment(MANIFEST, results_root=tmp_path)
    assert replay["run_id"] == result["run_id"]
    assert store.list_runs() == [result["run_id"]]  # no second run dir
    assert len(store.claim_links()) == 1  # no duplicate claim link
    for artifact in ("run.json", "observations.json"):
        left = (tmp_path / result["run_id"] / artifact).read_bytes()
        right = (tmp_path / replay["run_id"] / artifact).read_bytes()
        assert left == right


# ---------------------------------------------------------------------------
# put_counterexample (G6)
# ---------------------------------------------------------------------------


def _counterexample(store, **overrides):
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    record = {**COUNTEREXAMPLE, "run_ids": [run_id], **overrides}
    return run_id, record


def test_put_counterexample_is_content_addressed(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id, record = _counterexample(store)
    cx_id = store.put_counterexample(record)
    expected = hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
    assert cx_id == expected
    entries = store.counterexamples()
    assert entries == [{**record, "counterexample_id": cx_id}]
    assert entries[0]["run_ids"] == [run_id]
    index_bytes = (tmp_path / "counterexamples.jsonl").read_bytes()
    assert index_bytes.endswith(b"\n")  # one canonical line per record


def test_put_counterexample_same_record_is_idempotent(tmp_path):
    store = EvidenceStore(tmp_path)
    _, record = _counterexample(store)
    first = store.put_counterexample(record)
    second = store.put_counterexample(record)
    assert first == second
    assert len(store.counterexamples()) == 1  # replay appends nothing


def test_put_counterexample_different_record_appends_not_overwrites(tmp_path):
    store = EvidenceStore(tmp_path)
    _, record = _counterexample(store)
    first = store.put_counterexample(record)
    other = store.put_counterexample({**record, "cause_class": "backend_bug"})
    assert first != other
    assert [e["counterexample_id"] for e in store.counterexamples()] == [first, other]


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"run_ids": "not-a-list"}, "must be a list"),
        ({"run_ids": []}, "must not be empty"),
        ({"run_ids": [42]}, "non-empty string"),
        ({"observable": ""}, "non-empty string"),
        ({"description": None}, "non-empty string"),
        ({"cause_class": 7}, "non-empty string"),
        ({"minimized_case_ref": 3}, "non-empty string"),
        ({"extra": 1}, "unknown field"),
    ],
)
def test_put_counterexample_rejects_untyped_records(tmp_path, overrides, match):
    store = EvidenceStore(tmp_path)
    _, record = _counterexample(store, **overrides)
    with pytest.raises(EvidenceError, match=match):
        store.put_counterexample(record)


def test_put_counterexample_rejects_missing_fields(tmp_path):
    store = EvidenceStore(tmp_path)
    _, record = _counterexample(store)
    incomplete = {key: value for key, value in record.items() if key != "cause_class"}
    with pytest.raises(EvidenceError, match="missing field"):
        store.put_counterexample(incomplete)


def test_put_counterexample_rejects_unknown_runs(tmp_path):
    store = EvidenceStore(tmp_path)
    _, record = _counterexample(store)
    dangling = {**record, "run_ids": ["f" * 64]}
    with pytest.raises(EvidenceError, match="not in the store"):
        store.put_counterexample(dangling)


def test_put_counterexample_rejects_tampered_duplicate_id(tmp_path):
    # The index is append-only: a stored entry whose id matches the new
    # put but whose bytes differ (manual tampering) must be refused, never
    # silently accepted as idempotent.
    store = EvidenceStore(tmp_path)
    _, record = _counterexample(store)
    cx_id = store.put_counterexample(record)
    index_path = tmp_path / "counterexamples.jsonl"
    tampered = json.loads(index_path.read_text(encoding="utf-8"))
    assert tampered["counterexample_id"] == cx_id
    tampered["description"] = "rewritten description"  # id kept, bytes changed
    index_path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError, match="append-only violation"):
        store.put_counterexample(record)  # same record → same id, stored bytes differ


# ---------------------------------------------------------------------------
# register_figure (G6: figure-provenance gate consumed by T055; T006 fix —
# figure_id is content-addressed, derived from the referenced artifact
# bytes + run binding, never caller-chosen)
# ---------------------------------------------------------------------------


def _expected_figure_id(store: EvidenceStore, run_ids: list[str]) -> str:
    """Recompute the figure content address independently of the store:
    sha256 over the canonical binding of the sorted run set to the sha256
    of every artifact byte in those run dirs."""
    runs = sorted(set(run_ids))
    artifacts = {
        run_id: {
            path.relative_to(store.root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(store.run_dir(run_id).rglob("*"))
            if path.is_file()
        }
        for run_id in runs
    }
    return hashlib.sha256(
        canonical_json(
            {"artifact_sha256": artifacts, "source_run_ids": runs}
        ).encode("utf-8")
    ).hexdigest()


def test_register_figure_is_content_addressed(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    figure_id = store.register_figure([run_id], ["C2"])
    assert figure_id == _expected_figure_id(store, [run_id])
    assert store.figures() == [
        {"figure_id": figure_id, "source_run_ids": [run_id], "claim_ids": ["C2"]}
    ]
    assert (tmp_path / "figures_index.jsonl").read_bytes().endswith(b"\n")


def test_register_figure_same_content_same_id_idempotent(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    first = store.register_figure([run_id], ["C2"])
    second = store.register_figure([run_id], ["C2"])  # replay appends nothing
    assert first == second
    assert len(store.figures()) == 1


def test_register_figure_same_content_any_run_order_same_id(tmp_path):
    # The id is a function of the referenced run SET, not of the caller's
    # ordering (same rule as reproduction bundles).
    store = EvidenceStore(tmp_path)
    left = store.put_run(PAYLOAD, OBSERVATIONS)
    right = store.put_run({**PAYLOAD, "experiment_id": "EXP-TEST-STORE-2"}, OBSERVATIONS)
    first = store.register_figure([left, right], [])
    second = store.register_figure([right, left], [])
    assert first == second
    assert len(store.figures()) == 1


def test_register_figure_different_content_different_id(tmp_path):
    # Different referenced runs are different content: a different
    # figure_id, appended as a new figure — never a conflict, never an
    # overwrite.
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    other = store.put_run({**PAYLOAD, "experiment_id": "EXP-TEST-STORE-2"}, OBSERVATIONS)
    first = store.register_figure([run_id], ["C2"])
    second = store.register_figure([other], ["C2"])
    assert first != second
    assert [entry["figure_id"] for entry in store.figures()] == [first, second]


def test_register_figure_rejects_unknown_runs(tmp_path):
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="not in the store"):
        store.register_figure(["f" * 64], ["C2"])


def test_register_figure_rejects_changed_claims_for_same_content(tmp_path):
    # claim_ids are recorded provenance but not identity: same content
    # keeps one figure_id, so changed claims would rewrite the stored
    # entry — an append-only violation, never a silent update.
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    store.register_figure([run_id], ["C2"])
    with pytest.raises(EvidenceError, match="append-only violation"):
        store.register_figure([run_id], ["C2", "C1"])
    assert len(store.figures()) == 1


def test_register_figure_rejects_empty_or_untyped_arguments(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    with pytest.raises(EvidenceError, match="must not be empty"):
        store.register_figure([], ["C2"])
    with pytest.raises(EvidenceError, match="must be a list"):
        store.register_figure(run_id, [])  # not a list
    with pytest.raises(EvidenceError, match="must be a list"):
        store.register_figure([run_id], "C2")  # not a list


# ---------------------------------------------------------------------------
# export_reproduction_bundle (G6)
# ---------------------------------------------------------------------------


def _tree_digest(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_export_reproduction_bundle_copies_runs_and_manifest(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    out = tmp_path / "bundle"
    store.export_reproduction_bundle([run_id], out)
    assert (out / run_id / "run.json").read_bytes() == (
        tmp_path / run_id / "run.json"
    ).read_bytes()
    assert (out / run_id / "observations.json").read_bytes() == (
        tmp_path / run_id / "observations.json"
    ).read_bytes()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_ids"] == [run_id]
    for relative, digest in manifest["hashes"].items():
        assert digest == hashlib.sha256((out / relative).read_bytes()).hexdigest()
    assert set(manifest["hashes"]) == {
        f"{run_id}/observations.json",
        f"{run_id}/run.json",
    }


def test_export_reproduction_bundle_rejects_unknown_runs(tmp_path):
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="not in the store"):
        store.export_reproduction_bundle(["f" * 64], tmp_path / "bundle")


def test_export_reproduction_bundle_is_hash_stable(tmp_path):
    store = EvidenceStore(tmp_path)
    first = store.put_run(PAYLOAD, OBSERVATIONS)
    second = store.put_run({**PAYLOAD, "experiment_id": "EXP-TEST-STORE-2"}, OBSERVATIONS)
    left = store.export_reproduction_bundle([first, second], tmp_path / "bundle-a")
    # Reversed input order: the bundle is a function of the run set, not
    # of the caller's ordering.
    right = store.export_reproduction_bundle([second, first], tmp_path / "bundle-b")
    assert _tree_digest(left) == _tree_digest(right)


def test_export_reproduction_bundle_two_exports_are_byte_identical(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    store.export_reproduction_bundle([run_id], tmp_path / "bundle-1")
    store.export_reproduction_bundle([run_id], tmp_path / "bundle-2")
    assert _tree_digest(tmp_path / "bundle-1") == _tree_digest(tmp_path / "bundle-2")
    # No wall-clock or host metadata keys anywhere in the bundle manifest.
    manifest = json.loads(
        (tmp_path / "bundle-1" / "manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest) == {"run_ids", "hashes"}
    for text in [json.dumps(manifest), *manifest["hashes"].keys()]:
        lowered = text.lower()
        assert not any(
            marker in lowered for marker in ("time", "date", "host", "generated")
        )
