"""Immutability + fence guard for the stage-S2 calibration fit record
(group G1, anchor CAL-A3's split-record fit sizes {2,4,8} GiB).

The S2 fit runs under the immutable split record (S1,
``3862e227…``): the fit objective may touch ONLY CAL-A3's {2,4,8} GiB
points, the {16,32} GiB sizes are within-series holdouts reported as
held-out error, and no cross-anchor holdout (the split's four holdout
anchors, plus blocked GF-06) may be read by any objective, swept value, or
tolerance — sole recorded exception: the ~5% mean-error scalar as
tolerance-SHAPE context.

This guard re-executes the stage's whole evidence chain (the 108-config
fit sweep and the three dimensioned runs) into a scratch store and
rebuilds the fit record BYTE-IDENTICALLY from it, then checks the
fit/holdout separation invariants on the committed record. A drift of the
committed copy is an error: the record is append-only (a change requires
fit_record_v2).
"""

from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path

import pytest

from essun.evidence.dimensions import dimensions_problems
from essun.evidence.store import canonical_json
from essun.orchestrator.runs import run_experiment
from essun.orchestrator.sweeps import run_sweep

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "experiments" / "calibration" / "s2" / "build_fit_record.py"
COMMITTED_COPY = REPO / "experiments" / "calibration" / "s2" / "fit_record_v1.json"
SWEEP_MANIFEST = REPO / "experiments" / "calibration" / "s2" / "sweep_s2_bw_v1.yaml"
RUN_MANIFESTS = {
    "fit_8gib": REPO / "experiments" / "calibration" / "s2" / "run_s2_fit_8gib_floorbr.yaml",
    "hold_16gib": REPO / "experiments" / "calibration" / "s2" / "run_s2_holdout_16gib_floorbr.yaml",
    "hold_32gib": REPO / "experiments" / "calibration" / "s2" / "run_s2_holdout_32gib_floorbr.yaml",
}
FIT_TOPOLOGY = REPO / "experiments" / "calibration" / "s2" / "topologies" / "crossbar72_s2_fitb_v1.yaml"

FIT_SIZES = {"2GiB", "4GiB", "8GiB"}
HELD_SIZES = {"16GiB", "32GiB"}
HOLDOUT_ANCHOR_IDS = ("GF-01", "GF-03", "GF-11", "GF-06")


def _load_builder():
    spec = importlib.util.spec_from_file_location("s2_fit_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the S2 evidence chain into a scratch store and rebuild
    the record from it (the documented reproduce path, end to end)."""
    scratch = tmp_path_factory.mktemp("s2_scratch_results")
    sweep_result = run_sweep(SWEEP_MANIFEST, results_root=scratch)
    assert sweep_result["sweep_id"] == "9cf1ed89c1f2e6056e9afa1e9f8642a53df68e5e8c4bebee7365beea0b60ef70"
    run_ids = {}
    for name, manifest in RUN_MANIFESTS.items():
        executed = run_experiment(manifest, results_root=scratch)
        run_ids[name] = executed["run_id"]
    assert run_ids == {
        "fit_8gib": "c32d3c646a5f4acedf054eb219675c7711e5ee3f412e1c2ee9ea5f0c215ce32a",
        "hold_16gib": "f1f0604853f1ffb712903848624d6afe9b3072a58cb26d741f7297ef9f896140",
        "hold_32gib": "7b2136ae9d09d16cdb4324bcb4d3a66b83261b22560938c10532f18e225fe1d1",
    }
    builder = _load_builder()
    builder.RESULTS = scratch
    record = builder.build_record()
    return record, scratch, run_ids


def _committed_record() -> dict:
    import json

    return json.loads(COMMITTED_COPY.read_text(encoding="utf-8"))


def test_scratch_rebuild_is_byte_identical_to_committed_copy(scratch_record):
    record, _, _ = scratch_record
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    assert COMMITTED_COPY.read_bytes() == record_bytes


def test_fit_objective_touches_only_split_fit_sizes(scratch_record):
    record, _, _ = scratch_record
    fit = record["fit"]
    assert {row["size"] for row in fit["per_size_at_fitted_B"]} == FIT_SIZES
    assert set(fit["binding_sizes"]) <= FIT_SIZES
    # every per-B delta column is a fit size only
    for entry in record["executed_sweep"]["per_B_deltas_at_exact_fit_sizes"]:
        delta_keys = {k[len("delta_pct_"):] for k in entry if k.startswith("delta_pct_")}
        assert delta_keys == FIT_SIZES, (entry["topology"], delta_keys)
    # held-out sizes appear ONLY in the held-out evaluation section
    assert {row["size"] for row in record["held_out_evaluation"]["rows"]} == HELD_SIZES


def test_executed_fit_sweep_carries_no_held_out_brackets(scratch_record):
    _, scratch, _ = scratch_record
    import json

    table = json.loads(
        (scratch / "sweeps" / "9cf1ed89c1f2e6056e9afa1e9f8642a53df68e5e8c4bebee7365beea0b60ef70" / "table.json").read_text()
    )
    payloads = {row["payload_bytes"] for row in table["configs"]}
    held_brackets = {2**34 - 16, 2**34 - 16 + 72, 2**35 - 32, 2**35 - 32 + 72}
    assert payloads and not payloads & held_brackets
    fit_brackets = {2**31 - 56, 2**31 - 56 + 72, 2**32 - 40, 2**32 - 40 + 72, 2**33 - 8, 2**33 - 8 + 72}
    assert payloads == fit_brackets


def test_record_carries_valid_v2_evidence_dimensions(scratch_record):
    record, _, _ = scratch_record
    assert record["evidence_schema_version"] == 2
    assert not dimensions_problems(
        {k: record[k] for k in ("verification", "calibration_target", "held_out", "independent_reproduction", "known_omissions")}
    )
    assert record["calibration_target"] == ["CAL-A3"]
    assert record["held_out"]["held_out"] is False


def test_run_records_dimensions_split_fit_vs_heldout(scratch_record):
    _, scratch, run_ids = scratch_record
    import json

    def run_payload(name):
        return json.loads((scratch / run_ids[name] / "run.json").read_text())

    fit = run_payload("fit_8gib")
    assert fit["calibration_target"] == ["CAL-A3"]
    assert fit["held_out"]["held_out"] is False
    assert fit["evidence_schema_version"] == 2
    for hold in ("hold_16gib", "hold_32gib"):
        payload = run_payload(hold)
        assert payload["calibration_target"] == ["CAL-A3"]
        assert payload["held_out"]["held_out"] is True  # evaluation-only reporting runs
        assert payload["evidence_schema_version"] == 2


def test_no_holdout_anchor_numbers_or_ids_in_record(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    for anchor_id in HOLDOUT_ANCHOR_IDS:
        assert anchor_id not in text
    # the sole admitted holdout scalar context: CAL-A4's ~5% appears exactly
    # once, inside the tolerance-shape provenance
    assert text.count("CAL-A4") == 1
    tau5 = record["fit"]["tolerance_shape_windows"]["tau_5pct"]
    assert "CAL-A4" in tau5["shape_provenance"]


def test_fitted_B_is_the_recorded_minimax_and_stays_a_diagnostic(scratch_record):
    record, _, _ = scratch_record
    exact = Fraction(record["fit"]["minimax_B_exact"])
    topology_text = FIT_TOPOLOGY.read_text(encoding="utf-8")
    assert str(exact.numerator) + "/" + str(exact.denominator) in topology_text
    assert Fraction(1) < exact < Fraction(1024)  # inside the declared free range
    # the shipped registry value is untouched by the stage
    assert record["model"]["declared_free_parameter"]["registry_value"] == 64
    assert record["model"]["declared_free_parameter"]["registry_range"] == [1, 1024]
    assert "PROPOSED" in record["status"]
