"""Comparison submissions v0: the door, the fairness gates, the store gates.

The contract under test (``essun.evidence.submissions``,
``docs/submission-format.md``): a submission is an operating point —
workload, shared free-parameter record, one or two arms over committed
topologies, results citing run ids.  The door REJECTS malformed input by
design (the malformed classes below are the design's teeth, not an
exhaustive enumeration); the fairness gates are the delta-zero style of
the cross-fabric matrix — everything shared must be verified equal and
only the declared axis may differ; the store gates refuse any number
that does not trace to a cited run exactly.

The positive instance is ``examples/submission.example.yaml`` — the S4
latency pair, whose run ids and values are real stored records in the
tree that built it (regenerated deterministically from committed
manifests).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from essun.evidence.submissions import (
    BACKENDS,
    DIFF_AXES,
    PROFILES,
    WORKLOAD_KINDS,
    SubmissionError,
    fairness_problems,
    load_submission_file,
    render_table_rows,
    review_problems,
    submission_id,
    submission_problems,
    tree_problems,
    validate_submission,
    verify_against_store,
)
from essun.evidence.store import EvidenceStore

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "examples" / "submission.example.yaml"


def valid_submission() -> dict:
    """A deep copy of the committed example (itself door-valid)."""
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# the positive path
# ---------------------------------------------------------------------------


def test_example_passes_the_door() -> None:
    problems = submission_problems(valid_submission(), repo_root=REPO)
    assert problems == []


def test_example_loads_and_has_stable_identity() -> None:
    submission, review = load_submission_file(EXAMPLE, repo_root=REPO)
    assert review is None
    assert submission_id(submission) == submission_id(valid_submission())
    # The identity excludes the review (appending one cannot rewrite it).
    with_review = {**valid_submission(), "review": None}
    assert submission_id(with_review) == submission_id(submission)


def test_single_arm_submission_passes_the_door() -> None:
    submission = valid_submission()
    del submission["arms"][1]
    del submission["comparison"]
    del submission["results"][1]
    assert submission_problems(submission, repo_root=REPO) == []


# ---------------------------------------------------------------------------
# malformed submissions are rejected (the door's design requirement)
# ---------------------------------------------------------------------------


def test_missing_required_field_is_rejected() -> None:
    submission = valid_submission()
    del submission["essun_commit"]
    problems = submission_problems(submission)
    assert any("missing field" in problem for problem in problems)


def test_unknown_field_is_rejected() -> None:
    submission = valid_submission()
    submission["verdict"] = "excellent"
    problems = submission_problems(submission)
    assert any("unknown field" in problem for problem in problems)


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("format_version", "format_version must be 0"),
        ("submitted", "must be an ISO date"),
        ("source_url", "must be a public http(s) URL"),
        ("essun_commit", "40 lowercase hex characters"),
        ("backend", "backend must be one of"),
    ],
    )
def test_scalar_patterns_are_rejected(mutation: str, expected: str) -> None:
    bad_values = {
        "format_version": 1,
        "submitted": "2026-11-02T00:00",
        "source_url": "file:///tmp/x",
        "essun_commit": "deadbeef",
        "backend": "my_laptop",
    }
    submission = valid_submission()
    submission[mutation] = bad_values[mutation]
    problems = submission_problems(submission)
    assert any(expected in problem for problem in problems), problems


def test_unknown_workload_kind_is_rejected() -> None:
    submission = valid_submission()
    submission["workload"]["kind"] = "w99_mystery"
    assert any("workload.kind must be one of" in p for p in submission_problems(submission))


def test_unknown_workload_parameter_is_rejected() -> None:
    submission = valid_submission()
    submission["workload"]["parameters"]["mystery_knob"] = 3
    assert any("unknown key" in p for p in submission_problems(submission))


def test_empty_shared_values_are_rejected() -> None:
    submission = valid_submission()
    submission["shared_parameters"]["values"] = {}
    assert any("shared_parameters.values must not be empty" in p for p in submission_problems(submission))


def test_three_arms_are_rejected() -> None:
    submission = valid_submission()
    submission["arms"].append(copy.deepcopy(submission["arms"][0]))
    assert any("one or two arm blocks" in p for p in submission_problems(submission))


def test_unknown_profile_is_rejected() -> None:
    submission = valid_submission()
    submission["arms"][0]["profile"] = "uec-1.1-semantic"
    problems = submission_problems(submission)
    assert any("profile must be one of" in p for p in problems)


def test_url_topology_is_rejected() -> None:
    submission = valid_submission()
    submission["arms"][0]["topology"] = "https://example.com/topo.yaml"
    assert any("repo-relative committed path" in p for p in submission_problems(submission))


def test_run_id_of_wrong_shape_is_rejected() -> None:
    submission = valid_submission()
    submission["results"][0]["run_ids"] = ["2ca54ead" * 7]  # 63 hex
    assert any("64 lowercase hex" in p for p in submission_problems(submission))


def test_result_without_run_ids_is_rejected() -> None:
    submission = valid_submission()
    submission["results"][0]["run_ids"] = []
    assert any("run_ids must be a non-empty list" in p for p in submission_problems(submission))


def test_unregistered_observable_is_rejected() -> None:
    submission = valid_submission()
    submission["results"][0]["observable"] = "O-TELEPATHY"
    assert any("not registered" in p for p in submission_problems(submission))


def test_non_numeric_value_is_rejected() -> None:
    submission = valid_submission()
    submission["results"][0]["value"] = "fast"
    assert any("exact numeric string" in p for p in submission_problems(submission))


def test_empty_results_are_rejected() -> None:
    submission = valid_submission()
    submission["results"] = []
    assert any("results must be a non-empty list" in p for p in submission_problems(submission))


def test_self_review_is_refused_at_the_door() -> None:
    submission = valid_submission()
    submission["review"] = {
        "decision": "published",
        "reviewer": "self",
        "date": "2026-11-02",
        "basis": "trust me",
        "verified_run_ids": [],
    }
    problems = submission_problems(submission, at_door=True)
    assert any("never accepted at the door" in p for p in problems)


def test_validate_submission_raises_on_malformed_input() -> None:
    submission = valid_submission()
    submission["results"][1]["value"] = {}
    with pytest.raises(SubmissionError, match="value must be a number"):
        validate_submission(submission)


# ---------------------------------------------------------------------------
# the fairness gates (delta-zero style)
# ---------------------------------------------------------------------------


def test_undeclared_axis_difference_is_unfair() -> None:
    submission = valid_submission()
    # the arms differ on topology, but the comparison declares parameters
    submission["comparison"]["differs_on"] = ["parameters"]
    submission["arms"][0]["parameters"] = {"A-L0-LAT": 64}
    submission["arms"][1]["parameters"] = {"A-L0-LAT": 140}
    problems = fairness_problems(submission)
    assert any("undeclared axis" in p for p in problems)


def test_declared_axis_without_difference_is_mislabeled() -> None:
    submission = valid_submission()
    # declare profile as the axis while the arms differ only on topology
    submission["comparison"]["differs_on"] = ["profile", "topology"]
    problems = fairness_problems(submission)
    assert any("mislabeled comparison" in p for p in problems)


def test_shared_parameter_shadowing_is_rejected() -> None:
    submission = valid_submission()
    submission["arms"][0]["parameters"] = {"A-L0-BW": 32}
    problems = fairness_problems(submission)
    assert any("shadows shared parameter" in p for p in problems)


def test_unpaired_results_are_rejected() -> None:
    submission = valid_submission()
    del submission["results"][1]  # only the first arm reports
    problems = fairness_problems(submission)
    assert any("unpaired result" in p for p in problems)


def test_control_pair_with_unequal_values_is_rejected() -> None:
    submission = valid_submission()
    submission["comparison"]["control"] = True  # values are 1344 vs 2408
    problems = fairness_problems(submission)
    assert any("control pair violated" in p for p in problems)


def test_control_pair_with_equal_values_passes() -> None:
    submission = valid_submission()
    submission["comparison"]["control"] = True
    submission["results"][1]["value"] = 1344
    assert fairness_problems(submission) == []


def test_single_arm_with_comparison_block_is_rejected() -> None:
    submission = valid_submission()
    del submission["arms"][1]
    problems = submission_problems(submission)
    assert any("two-arm field" in p for p in problems)


# ---------------------------------------------------------------------------
# the tree gates (committed paths, shared inputs read from the files)
# ---------------------------------------------------------------------------


def test_uncommitted_topology_is_rejected(tmp_path: Path) -> None:
    submission = valid_submission()
    submission["arms"][0]["topology"] = "experiments/nowhere/topo.yaml"
    problems = tree_problems(submission, tmp_path)
    # tmp tree has neither file; the shared record complaint comes first
    assert any("not a committed file" in p for p in problems)


def test_unknown_shared_parameter_id_is_rejected(tmp_path: Path) -> None:
    _copy_input_tree(tmp_path)
    submission = valid_submission()
    submission["shared_parameters"]["values"]["A-NOWHERE"] = 1
    problems = tree_problems(submission, tmp_path)
    assert any("unknown id 'A-NOWHERE'" in p for p in problems)


def test_shared_value_contradicted_by_topology_is_rejected(tmp_path: Path) -> None:
    _copy_input_tree(tmp_path)
    submission = valid_submission()
    submission["shared_parameters"]["values"]["A-L0-BW"] = 32  # files carry 64
    problems = tree_problems(submission, tmp_path)
    assert any("the arms would not share it" in p for p in problems)


def test_shared_value_absent_from_topology_is_rejected(tmp_path: Path) -> None:
    _copy_input_tree(tmp_path)
    submission = valid_submission()
    # A-L0-LAT's spelling exists in both files; a spelling-less id shows
    # the not-carried branch: use A-L0-LAT with a topology that drops it.
    topo = yaml.safe_load((tmp_path / submission["arms"][0]["topology"]).read_text())
    del topo["link"]["hop_latency_ns"]
    (tmp_path / submission["arms"][0]["topology"]).write_text(yaml.safe_dump(topo))
    submission["shared_parameters"]["values"] = {"A-L0-LAT": 64}
    problems = tree_problems(submission, tmp_path)
    assert any("carries none of its spellings" in p for p in problems)


def _copy_input_tree(root: Path) -> None:
    """The example's committed inputs, copied under a tmp repo root."""
    submission = valid_submission()
    for relative in (
        submission["shared_parameters"]["record"],
        *(arm["topology"] for arm in submission["arms"]),
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPO / relative).read_bytes())


# ---------------------------------------------------------------------------
# the store gates (every number traces to a cited run)
# ---------------------------------------------------------------------------


def _run_payload(
    *,
    topology: str,
    manifest: str,
    workload: str,
    assumptions: str,
    standard: str = "experiments/vertical_slice/profiles/standard_profile_none.yaml",
    implementation: str = "experiments/calibration/s4/profiles/implementation_profile_l0_ring_cal_s4_v1.yaml",
) -> dict:
    return {
        "experiment_id": "SUBMISSION-TEST",
        "code_version": "0.1.0",
        "manifest_path": manifest,
        "inputs": {
            "workload_ir": {"path": workload, "sha256": "0" * 64},
            "assumptions": {"path": assumptions, "sha256": "1" * 64},
            "standard_profile": {"path": standard, "sha256": "2" * 64},
            "implementation_profile": {"path": implementation, "sha256": "3" * 64},
            "infra_graph": {"path": topology, "sha256": "4" * 64},
        },
        "observables_digest": "0" * 64,
    }


def _observations(value: float) -> dict:
    return {
        "backend_id": "analytical_l0",
        "observables": {
            "O-CCT": {
                "kind": "analytical",
                "completion_time_ns_max": value,
                "completion_time_ns_mean_exact": str(int(value)),
            }
        },
    }


@pytest.fixture()
def store_tree(tmp_path: Path) -> tuple[EvidenceStore, Path]:
    """A tmp store + repo tree holding the example's cited runs.

    The runs mirror the example's real records: same workload/assumptions/
    implementation/standard inputs, topologies differing (the declared
    axis), manifests and workload file committed under the tmp root.
    """
    submission = valid_submission()
    (tmp_path / "experiments/vertical_slice").mkdir(parents=True, exist_ok=True)
    workload_file = tmp_path / "experiments/workloads/w1_dense_tp_decode_small.yaml"
    workload_file.parent.mkdir(parents=True, exist_ok=True)
    workload_file.write_text(
        yaml.safe_dump(
            {
                "workload": "w1_dense_tp_decode",
                "tp_size": 8,
                "layers": 2,
                "steps": 3,
                "allreduce_bytes": 16384,
            }
        )
    )
    for arm in submission["arms"]:
        destination = tmp_path / arm["topology"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPO / arm["topology"]).read_bytes())
    (tmp_path / submission["shared_parameters"]["record"]).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / submission["shared_parameters"]["record"]).write_bytes(
        (REPO / submission["shared_parameters"]["record"]).read_bytes()
    )
    store = EvidenceStore(tmp_path / "results")
    manifests = [
        "experiments/calibration/s4/run_s4_a8_fit_l64.yaml",
        "experiments/calibration/s4/run_s4_a8_fit_l140.yaml",
    ]
    values = [1344.0, 2408.0]
    for arm, manifest, value in zip(submission["arms"], manifests, values):
        (tmp_path / manifest).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / manifest).write_text("sweep: placeholder\n")
        run_id = store.put_run(
            _run_payload(
                topology=arm["topology"],
                manifest=manifest,
                workload="experiments/workloads/w1_dense_tp_decode_small.yaml",
                assumptions=submission["shared_parameters"]["record"],
            ),
            _observations(value),
        )
        for row in submission["results"]:
            if row["arm"] == arm["label"]:
                row["run_ids"] = [run_id]
                row["value"] = int(value)
    return store, tmp_path


def test_verify_happy_path(store_tree: tuple[EvidenceStore, Path]) -> None:
    store, root = store_tree
    submission = valid_submission()
    # rebind run ids to the tmp store's (fixture rewrote valid_submission's
    # copy — rebuild from the fixture's records instead)
    submission = _rebind_from_store(store, root)
    assert verify_against_store(submission, store, root) == []


def _rebind_from_store(store: EvidenceStore, root: Path) -> dict:
    """The example with run ids/values rebound to the tmp store's runs."""
    submission = valid_submission()
    by_topology = {}
    for run_id in store.list_runs():
        record = store.get_run(run_id)
        by_topology[record["inputs"]["infra_graph"]["path"]] = (
            run_id,
            json.loads(
                (store.run_dir(run_id) / "observations.json").read_text()
            )["observables"]["O-CCT"]["completion_time_ns_max"],
        )
    for row in submission["results"]:
        arm = next(a for a in submission["arms"] if a["label"] == row["arm"])
        run_id, value = by_topology[arm["topology"]]
        row["run_ids"] = [run_id]
        row["value"] = int(value)
    return submission


def test_verify_rejects_fabricated_value(store_tree: tuple[EvidenceStore, Path]) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    submission["results"][0]["value"] = 999999
    problems = verify_against_store(submission, store, root)
    assert any("does not match run" in p and "trace to the cited run" in p for p in problems)


def test_verify_rejects_missing_run(store_tree: tuple[EvidenceStore, Path]) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    submission["results"][0]["run_ids"] = ["f" * 64]
    problems = verify_against_store(submission, store, root)
    assert any("is not in the local store" in p for p in problems)


def test_verify_rejects_cross_arm_workload_difference(
    store_tree: tuple[EvidenceStore, Path]
) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    # rebuild arm two with a DIFFERENT workload file: same-workload violated
    arm = submission["arms"][1]
    other_workload = "experiments/workloads/w1_other.yaml"
    (root / other_workload).write_text("workload: w1_dense_tp_decode\n")
    record = store.get_run(submission["results"][1]["run_ids"][0])
    rebuilt = copy.deepcopy(record)
    del rebuilt["run_id"]
    rebuilt["inputs"]["workload_ir"] = {"path": other_workload, "sha256": "9" * 64}
    new_id = store.put_run(rebuilt, _observations(2408.0))
    submission["results"][1]["run_ids"] = [new_id]
    problems = verify_against_store(submission, store, root)
    assert any("differ on workload_ir" in p for p in problems)


def test_verify_rejects_topology_difference_without_declared_axis(
    store_tree: tuple[EvidenceStore, Path]
) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    # declare the profile axis (exempts only standard_profile) while the
    # runs differ on infra_graph: nothing exempts the difference
    submission["comparison"]["differs_on"] = ["profile"]
    submission["arms"][0]["profile"] = submission["arms"][1]["profile"]
    problems = verify_against_store(submission, store, root)
    assert any("differ on infra_graph" in p and "no declared axis" in p for p in problems)


def test_verify_rejects_uncommitted_manifest(store_tree: tuple[EvidenceStore, Path]) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    missing_manifest = "experiments/calibration/s4/run_s4_uncommitted.yaml"
    record = store.get_run(submission["results"][0]["run_ids"][0])
    rebuilt = copy.deepcopy(record)
    del rebuilt["run_id"]
    rebuilt["manifest_path"] = missing_manifest
    new_id = store.put_run(rebuilt, _observations(1344.0))
    submission["results"][0]["run_ids"] = [new_id]
    problems = verify_against_store(submission, store, root)
    assert any("not a committed path" in p for p in problems)


def test_verify_rejects_declared_topology_mismatch(
    store_tree: tuple[EvidenceStore, Path]
) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    submission["arms"][0]["topology"] = submission["arms"][1]["topology"]
    submission["comparison"]["differs_on"] = ["parameters"]
    problems = verify_against_store(submission, store, root)
    assert any("declares topology" in p and "consumed" in p for p in problems)


def test_verify_rejects_workload_parameter_mismatch(
    store_tree: tuple[EvidenceStore, Path]
) -> None:
    store, root = store_tree
    submission = _rebind_from_store(store, root)
    submission["workload"]["parameters"]["allreduce_bytes"] = 32768
    problems = verify_against_store(submission, store, root)
    assert any("does not match the runs' workload file" in p for p in problems)


# ---------------------------------------------------------------------------
# the review gates
# ---------------------------------------------------------------------------


def _review(**overrides) -> dict:
    base = {
        "decision": "published",
        "reviewer": "@maintainer",
        "date": "2026-11-02",
        "basis": "re-ran the cited manifests; both ids regenerated byte-for-byte",
        "verified_run_ids": [],
    }
    base.update(overrides)
    return base


def test_published_review_requires_full_coverage() -> None:
    submission = valid_submission()
    review = _review(verified_run_ids=[submission["results"][0]["run_ids"][0]])
    problems = review_problems(review, submission)
    assert any("requires every cited run id re-verified" in p for p in problems)


def test_published_review_with_full_coverage_passes() -> None:
    submission = valid_submission()
    cited = [row["run_ids"][0] for row in submission["results"]]
    assert review_problems(_review(verified_run_ids=cited), submission) == []


def test_review_cannot_verify_uncited_runs() -> None:
    submission = valid_submission()
    review = _review(verified_run_ids=["e" * 64])
    problems = review_problems(review, submission)
    assert any("does not cite" in p for p in problems)


def test_committed_copy_without_review_is_rejected() -> None:
    submission = valid_submission()
    problems = submission_problems(submission, at_door=False)
    assert any("must carry a review block" in p for p in problems)


def test_load_file_rejects_self_review_at_door(tmp_path: Path) -> None:
    submission = valid_submission()
    submission["review"] = _review()
    path = tmp_path / "self-reviewed.yaml"
    path.write_text(yaml.safe_dump(submission))
    with pytest.raises(SubmissionError, match="never accepted at the door"):
        load_submission_file(path, repo_root=REPO)


# ---------------------------------------------------------------------------
# the rendered community table
# ---------------------------------------------------------------------------


def test_table_empty_state_is_honest() -> None:
    html = render_table_rows([])
    assert "No operating-point submissions recorded yet" in html


def test_table_rows_are_deterministic_and_escaped() -> None:
    submission = valid_submission()
    submission["submitter"] = "<script>x</script>"
    records = [(submission, None), (valid_submission(), _review(verified_run_ids=[]))]
    first = render_table_rows(records)
    second = render_table_rows(list(reversed(records)))
    assert first == second
    assert "&lt;script&gt;" in first


def test_table_marks_maintainer_submissions() -> None:
    submission = valid_submission()
    submission["submitter"] = "li-ch"
    html = render_table_rows([(submission, None)])
    assert "(maintainer)" in html


# ---------------------------------------------------------------------------
# vocabulary drift guards (constants may not silently diverge from code)
# ---------------------------------------------------------------------------


def test_backend_vocabulary_matches_the_modules() -> None:
    from essun.backends.analytical.l0 import BACKEND_ID as l0
    from essun.backends.analytical.l0_crossbar import BACKEND_ID as l0x
    from essun.backends.analytical.l0_phase_collectives import BACKEND_ID as l0pc
    from essun.backends.analytical.l0_recursive_doubling import BACKEND_ID as l0rd
    from essun.backends.analytical.l0_tfc import BACKEND_ID as l0tfc
    from essun.backends.analytical.l0_torus2d import BACKEND_ID as l0t
    from essun.backends.analytical.l05 import BACKEND_ID as l05
    from essun.backends.astra_sim.adapter import BACKEND_ID as astra
    from essun.backends.uet_htsim.adapter import BACKEND_ID as uet

    assert BACKENDS == tuple(
        sorted({l0, l0x, l0t, l0rd, l0pc, l0tfc, l05, astra, uet})
    ) or set(BACKENDS) == {l0, l0x, l0t, l0rd, l0pc, l0tfc, l05, astra, uet}


def test_workload_vocabulary_matches_the_generators() -> None:
    from essun.workload import w1, w2, w3, w5, w6

    assert set(WORKLOAD_KINDS) == {
        w1.WORKLOAD_KIND,
        w2.WORKLOAD_KIND,
        w3.WORKLOAD_KIND,
        w5.WORKLOAD_KIND,
        w6.WORKLOAD_KIND,
    }
    assert set(DIFF_AXES) == {"profile", "topology", "parameters"}


def test_profile_vocabulary_and_its_widening_preconditions() -> None:
    # v0 vocabulary is none-only; the semantic profile documents exist in
    # the tree as anchor registries — widening PROFILES without a backend
    # consuming one as a run input is the drift this test catches.
    assert PROFILES == ("none",)
    for profile in (
        "uec/semantic_profile.yaml",
        "unifiedbus/semantic_profile.yaml",
        "nvlink/semantic_profile.yaml",
    ):
        assert (REPO / "experiments" / profile).is_file()
