"""D3 orthogonal evidence dimensions on run records (store-side, 2026-10-29).

Design doc D3: verification != calibration != independent reproduction !=
physical validity — the run record carries the five facts SEPARATELY
(``verification`` / ``calibration_target`` / ``held_out`` /
``independent_reproduction`` / ``known_omissions``); an absent dimension
is UNKNOWN, never silently false; the store's run-record schema is
version-bumped to 2 with OLD (version-1) records still loading — the
backfill-safe gate. The public label ladder is unchanged.

Two backfill gates are pinned here:

1. a version-1-shaped payload (no dimension keys, no version key) still
   stores, loads, and reads all-UNKNOWN;
2. the TFC flagship manifest — the record G2 landed at the same HEAD as
   this change — still reproduces its stored run_id byte-identically,
   because manifests without the ``evidence_dimensions`` block leave the
   payload byte-identical (a code_version bump re-stores goldens by
   design; that discipline is documented in
   experiments/vertical_slice/w1_decode_smoke.GOLDEN.md).
"""

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from essun.evidence.dimensions import (
    EVIDENCE_DIMENSIONS,
    INDEPENDENT_REPRODUCTION_NONE_YET,
    MANIFEST_KEY,
    RUN_RECORD_SCHEMA_VERSION,
    SCHEMA_VERSION_KEY,
    UNKNOWN,
    dimension_value,
    dimensions_from_manifest,
    dimensions_problems,
    read_dimensions,
    run_record_problems,
)
from essun.evidence.store import EvidenceError, EvidenceStore, canonical_json

REPO = Path(__file__).resolve().parents[2]
SMOKE_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"
TFC_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_tfc.yaml"
# The G2 flagship run record landed at HEAD (labels E0); its id must not
# move under this change (backfill gate 2).
TFC_RUN_ID = "dc7d83b6afa23ef33fd87512eb637bd737ab8ad905a6802bc6d0965be1da21d9"

PAYLOAD = {
    "experiment_id": "EXP-TEST-DIMS",
    "code_version": "0.1.0",
    "inputs": {},
    "observables_digest": hashlib.sha256(b"obs").hexdigest(),
}
OBSERVATIONS = {
    "backend_id": "analytical_l0",
    "observables": {"O-CONSERVATION": {"kind": "exact", "violations": 0}},
}

# A complete, honest dimensions block of the shape D3 asks for: checks
# passed with their scope, calibration targets by anchor id (here: none —
# free parameters, uncalibrated), held-out bool + scope, reproductions
# (none yet), and the stated omissions.
DIMS = {
    "verification": [
        {
            "check": "tests/golden/test_w1_l0_golden.py",
            "scope": "W1 smoke identity on ring8 free parameters (exact)",
        }
    ],
    "calibration_target": [],  # explicit none: free parameters, no anchors
    "held_out": {
        "held_out": False,
        "scope": "no data withheld; every input derives from the identity",
    },
    "independent_reproduction": [],  # none yet — honest
    "known_omissions": [
        "steady-state only; fill/drain transients excluded",
    ],
}
V2_PAYLOAD = {**PAYLOAD, **DIMS, SCHEMA_VERSION_KEY: RUN_RECORD_SCHEMA_VERSION}


def _manifest_dict(**overrides):
    manifest = yaml.safe_load(SMOKE_MANIFEST.read_text(encoding="utf-8"))
    manifest.update(overrides)
    return manifest


def _write_manifest(tmp_path, manifest):
    tmp_path = Path(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# the five dimensions, and absence = UNKNOWN (never false)
# ---------------------------------------------------------------------------


def test_dimension_names_are_the_five_d3_fields():
    assert EVIDENCE_DIMENSIONS == (
        "verification",
        "calibration_target",
        "held_out",
        "independent_reproduction",
        "known_omissions",
    )
    assert RUN_RECORD_SCHEMA_VERSION == 2


def test_absent_dimensions_read_unknown_never_false():
    # A version-1 record (pre-D3): no dimension keys at all. Every
    # dimension reads UNKNOWN — a string, distinguishable from every
    # RECORDED fact (False, None, []).
    dims = read_dimensions(PAYLOAD)
    assert set(dims) == set(EVIDENCE_DIMENSIONS)
    for name in EVIDENCE_DIMENSIONS:
        assert dims[name] == UNKNOWN
        assert dims[name] is not False
        assert dims[name] is not None
        assert dims[name] != []
    assert dimension_value(PAYLOAD, "held_out") == UNKNOWN


def test_recorded_values_read_back_as_recorded():
    # "None" facts are RECORDED, not defaulted: an empty
    # independent_reproduction is [] (considered, none exist), and an
    # explicit held_out False is the boolean — neither collapses to
    # UNKNOWN, and UNKNOWN never collapses to them.
    dims = read_dimensions(V2_PAYLOAD)
    assert dims["independent_reproduction"] == []
    assert dims["calibration_target"] == []
    assert dims["held_out"] == {"held_out": False, "scope": DIMS["held_out"]["scope"]}
    assert dims["verification"] == DIMS["verification"]
    assert dims["known_omissions"] == DIMS["known_omissions"]


def test_dimensions_are_orthogonal_in_the_record():
    # Any subset may be present: verification can be recorded while
    # calibration stays UNKNOWN — the five facts never imply each other.
    partial = {**PAYLOAD, "verification": DIMS["verification"], SCHEMA_VERSION_KEY: 2}
    dims = read_dimensions(partial)
    assert dims["verification"] == DIMS["verification"]
    for name in ("calibration_target", "held_out", "independent_reproduction", "known_omissions"):
        assert dims[name] == UNKNOWN


def test_dimension_value_rejects_unknown_dimension_name():
    with pytest.raises(ValueError, match="unknown evidence dimension"):
        dimension_value(PAYLOAD, "physical_validity")


# ---------------------------------------------------------------------------
# manifest block: all five required, honest values, anchor-id targets
# ---------------------------------------------------------------------------


def test_manifest_without_block_declares_nothing():
    assert dimensions_from_manifest(_manifest_dict()) is None


def test_manifest_block_requires_all_five_dimensions():
    for name in EVIDENCE_DIMENSIONS:
        block = {key: value for key, value in DIMS.items() if key != name}
        problems = dimensions_problems(block)
        assert any(name in problem for problem in problems), problems
    with pytest.raises(ValueError, match="missing dimension"):
        dimensions_from_manifest({MANIFEST_KEY: {k: v for k, v in DIMS.items() if k != "held_out"}})


def test_manifest_block_rejects_unknown_dimensions():
    block = {**DIMS, "physical_validity": "calibrated"}
    with pytest.raises(ValueError, match="unknown dimension"):
        dimensions_from_manifest({MANIFEST_KEY: block})


def test_manifest_may_declare_calibration_targets_by_anchor_id():
    # By anchor id (the D2 profile-format calibration vocabulary) or as
    # the explicit none; both are structural facts of the block.
    by_anchor = dimensions_from_manifest(
        _manifest_dict(
            evidence_dimensions={**DIMS, "calibration_target": ["UEC11-S3.6.15-TFC"]}
        )
    )
    assert by_anchor["calibration_target"] == ["UEC11-S3.6.15-TFC"]


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda b: b.update(verification={"check": "x", "scope": "y"}), "verification: must be a list"),
        (lambda b: b["verification"].append({"check": "x"}), "missing field"),
        (lambda b: b["verification"].append({"check": "x", "scope": "y", "extra": 1}), "unknown field"),
        (lambda b: b["verification"].append({"check": "", "scope": "y"}), "non-empty string"),
        (lambda b: b.update(calibration_target=None), "calibration_target: must be a list"),
        (lambda b: b.update(calibration_target=[42]), "non-empty string"),
        (lambda b: b.update(held_out=None), "held_out: must be a mapping"),
        (lambda b: b.update(held_out={"held_out": "no"}), "missing field"),
        (lambda b: b.update(held_out={"held_out": 1, "scope": "s"}), "boolean"),
        (lambda b: b.update(held_out={"held_out": False}), "missing field"),
        (lambda b: b.update(independent_reproduction=None), "independent_reproduction: must be a list"),
        (lambda b: b.update(independent_reproduction="none yet"), "must be a list"),
        (lambda b: b.update(known_omissions=[""]), "non-empty string"),
    ],
)
def test_block_rejects_untyped_values(mutation, match):
    block = json.loads(json.dumps(DIMS))  # deep copy
    mutation(block)
    with pytest.raises(ValueError, match=match):
        dimensions_from_manifest({MANIFEST_KEY: block})


def test_none_yet_constant_is_the_honest_empty():
    # The honest value of independent_reproduction everywhere today:
    # considered, none exist. An empty list IS the fact.
    assert INDEPENDENT_REPRODUCTION_NONE_YET == []


# ---------------------------------------------------------------------------
# run-record schema version rules (the version bump, enforced at the door)
# ---------------------------------------------------------------------------


def test_dimensions_without_version_stamp_are_rejected():
    problems = run_record_problems({**PAYLOAD, **DIMS})
    assert any(SCHEMA_VERSION_KEY in p and "required" in p for p in problems), problems


@pytest.mark.parametrize(
    "version,ok",
    [
        (None, False),   # dimensions present, stamp missing
        (1, False),      # version 1 is definitionally dimension-free
        (2, True),       # the version this code writes
        (3, False),      # future version: not silently loadable
        ("2", False),    # not an integer
        (True, False),   # bool is not a version
        (0, False),      # versions start at 1
    ],
)
def test_version_stamp_rules(version, ok):
    payload = {**PAYLOAD, **DIMS}
    if version is not None:
        payload[SCHEMA_VERSION_KEY] = version
    assert (run_record_problems(payload) == []) is ok


def test_version_two_without_dimensions_is_legal_all_unknown():
    # Version 2 does not FORCE dimensions: absence stays allowed (UNKNOWN),
    # the version only gates what a record carrying dimensions must stamp.
    assert run_record_problems({**PAYLOAD, SCHEMA_VERSION_KEY: 2}) == []
    assert read_dimensions({**PAYLOAD, SCHEMA_VERSION_KEY: 2})[
        "held_out"
    ] == UNKNOWN


def test_version_one_explicit_without_dimensions_is_legal():
    # A record may explicitly claim version 1 (dimension-free) — it is
    # every pre-D3 record plus the stamp.
    assert run_record_problems({**PAYLOAD, SCHEMA_VERSION_KEY: 1}) == []


# ---------------------------------------------------------------------------
# store integration: v2 records store; malformed rejected; v1 loads
# ---------------------------------------------------------------------------


def test_put_run_stores_v2_record_and_roundtrips(tmp_path):
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(V2_PAYLOAD, OBSERVATIONS)
    record = store.get_run(run_id)
    assert record[SCHEMA_VERSION_KEY] == 2
    assert read_dimensions(record) == read_dimensions(V2_PAYLOAD)
    # The stored bytes carry the five fields as separate top-level keys.
    raw = json.loads((tmp_path / run_id / "run.json").read_text(encoding="utf-8"))
    for name in EVIDENCE_DIMENSIONS:
        assert raw[name] == DIMS[name]


def test_put_run_rejects_malformed_dimensions(tmp_path):
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="held_out: 'held_out' must be a boolean"):
        store.put_run(
            {**V2_PAYLOAD, "held_out": {"held_out": "no", "scope": "s"}}, OBSERVATIONS
        )
    with pytest.raises(EvidenceError, match="evidence_schema_version: required"):
        store.put_run({**PAYLOAD, **DIMS}, OBSERVATIONS)  # no stamp
    with pytest.raises(EvidenceError, match="newer than this store understands"):
        store.put_run({**V2_PAYLOAD, SCHEMA_VERSION_KEY: 3}, OBSERVATIONS)


def test_put_run_still_accepts_version_one_records(tmp_path):
    # BACKFILL GATE 1: the pre-D3 payload shape stores unchanged.
    store = EvidenceStore(tmp_path)
    run_id = store.put_run(PAYLOAD, OBSERVATIONS)
    assert run_id == hashlib.sha256(canonical_json(PAYLOAD).encode("utf-8")).hexdigest()
    record = store.get_run(run_id)  # loads
    assert read_dimensions(record)["verification"] == UNKNOWN
    assert read_dimensions(record)["held_out"] == UNKNOWN


# ---------------------------------------------------------------------------
# run path: the manifest block rides the record; manifests without it do
# not move (the G2 flagship id is the pinned witness)
# ---------------------------------------------------------------------------


def test_run_path_carries_declared_dimensions(tmp_path):
    from essun.orchestrator.runs import run_experiment

    manifest_path = _write_manifest(tmp_path, _manifest_dict(evidence_dimensions=DIMS))
    result = run_experiment(manifest_path, results_root=tmp_path / "store")
    store = EvidenceStore(tmp_path / "store")
    record = store.get_run(result["run_id"])
    assert record[SCHEMA_VERSION_KEY] == RUN_RECORD_SCHEMA_VERSION
    dims = read_dimensions(record)
    assert dims["verification"] == DIMS["verification"]
    assert dims["calibration_target"] == []  # the declared none, not UNKNOWN
    assert dims["held_out"] == DIMS["held_out"]
    assert dims["independent_reproduction"] == []
    assert dims["known_omissions"] == DIMS["known_omissions"]
    # The declared block is inside the content address: replaying the
    # identical manifest is idempotent (same run_id, no second record).
    replay = run_experiment(manifest_path, results_root=tmp_path / "store")
    assert replay["run_id"] == result["run_id"]
    assert store.list_runs() == [result["run_id"]]


def test_run_path_rejects_bad_block_before_executing(tmp_path):
    # Defense in depth: the declarative schema rejects the malformed
    # block at manifest LOAD (ContractError) and the run path's own gate
    # (ExecutionError) would catch anything the schema missed — either
    # way the failure is loud and BEFORE anything executes or stores.
    from essun.contracts import ContractError
    from essun.orchestrator.runs import ExecutionError, run_experiment

    manifest = _manifest_dict(evidence_dimensions={**DIMS, "held_out": {"held_out": "maybe"}})
    with pytest.raises((ContractError, ExecutionError)) as excinfo:
        run_experiment(_write_manifest(tmp_path, manifest), results_root=tmp_path / "store")
    assert "held_out" in str(excinfo.value)  # the fault is named
    assert not (tmp_path / "store").exists()  # nothing ran, nothing stored


def test_run_path_without_block_reproduces_flagship_run_id(tmp_path):
    # BACKFILL GATE 2: the G2 flagship record (dc7d83b6…, landed at this
    # HEAD) still reproduces byte-identically from its manifest, which
    # does not declare the block — the D3 change is additive to run
    # identity. (A code_version bump re-stores goldens by design; see
    # w1_decode_smoke.GOLDEN.md for that discipline.)
    from essun.orchestrator.runs import run_experiment

    result = run_experiment(TFC_MANIFEST, results_root=tmp_path)
    assert result["run_id"] == TFC_RUN_ID
    record = EvidenceStore(tmp_path).get_run(result["run_id"])
    for key in (*EVIDENCE_DIMENSIONS, SCHEMA_VERSION_KEY):
        assert key not in record
    assert set(read_dimensions(record).values()) == {UNKNOWN}


# ---------------------------------------------------------------------------
# schema/enforcement agreement (experiment.schema.json <-> this module)
# ---------------------------------------------------------------------------


def _manifest_schema():
    return json.loads((REPO / "schemas" / "experiment.schema.json").read_text(encoding="utf-8"))


def test_valid_manifest_with_block_validates_against_schema():
    schema = _manifest_schema()
    jsonschema.Draft202012Validator(schema).validate(_manifest_dict(evidence_dimensions=DIMS))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.pop("held_out"),
        lambda b: b.update(verification=[{"check": "x"}]),
        lambda b: b.update(calibration_target=None),
        lambda b: b.update(held_out={"held_out": "no", "scope": "s"}),
        lambda b: b.update(independent_reproduction=[3]),
        lambda b: b.update(known_omissions=[""]),
        lambda b: b.update(extra_dimension=[]),
    ],
)
def test_schema_and_loader_reject_the_same_faults(mutation):
    # The published schema's evidence_dimensions subschema and the code
    # validator are pinned to reject the same battery of structural
    # faults, so neither can drift from the other silently.
    import copy

    block = mutation(copy.deepcopy(DIMS))
    subschema = _manifest_schema()["properties"][MANIFEST_KEY]
    assert not jsonschema.Draft202012Validator(subschema).is_valid(block)
    assert dimensions_problems(block), "loader accepted a schema-rejected block"
