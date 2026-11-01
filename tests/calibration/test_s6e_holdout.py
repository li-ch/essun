"""Immutability + fence guard for the stage-S6e holdout-evaluation record
(the small-message-axis rerun of the S6 external check under the SAME
immutable split record, 3862e227...).

Everything here is evaluation-only: the fitted endpoint placements are
carried bit-exact from the S4e fit record, the holdout measured rows are
evaluation targets, and NOTHING tunes. The guard re-executes the stage's
evidence chain (two sweeps, two dimensioned runs) into a scratch store,
rebuilds the record BYTE-IDENTICALLY, and checks the nothing-tunes
invariants on the committed record. A drift of the committed copy is an
error: the record is append-only (a change requires holdout_record_v2).
"""

from __future__ import annotations

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest

from essun.evidence.dimensions import dimensions_problems
from essun.evidence.store import canonical_json
from essun.orchestrator.runs import run_experiment
from essun.orchestrator.sweeps import run_sweep

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "experiments" / "calibration" / "s6e" / "build_holdout_record.py"
COMMITTED_COPY = REPO / "experiments" / "calibration" / "s6e" / "holdout_record_v1.json"
SWEEP_MANIFESTS = {
    "gf11_tp4": REPO / "experiments" / "calibration" / "s6e" / "sweep_s6e_gf11_tp4_v1.yaml",
    "gf01_small": REPO / "experiments" / "calibration" / "s6e" / "sweep_s6e_gf01_small_v1.yaml",
}
RUN_MANIFESTS = {
    "gf11_xbar2_e600": REPO / "experiments" / "calibration" / "s6e" / "run_s6e_gf11_eval_xbar2_e600.yaml",
    "gf11_xbar2_e8800": REPO / "experiments" / "calibration" / "s6e" / "run_s6e_gf11_eval_xbar2_e8800.yaml",
}

SWEEP_IDS = {
    "gf11_tp4": "242873ae8a27e76549843f1187ac0275af277ce75b62121acaafc46badbd8d38",
    "gf01_small": "da3eb61d989663f7f0f7fde0c7e9f26ed6f66c29dd09e1c7b3312662427479e6",
}
RUN_IDS = {
    "gf11_xbar2_e600": "51fcccd63dee24747eb4a5251fb8d17164cc330c63b976878cab1d3f5f347ec4",
    "gf11_xbar2_e8800": "9ab8dc8fe82a2d61ac586f59b858cab664b83f364281ca3dccde8687247bb2a3",
}

S4E_RECORD_ID = "d91aaf874b983a684a230babe59a38c7ee6c2b5bc88cc39340ddfe481145c8c8"


def _load_builder():
    spec = importlib.util.spec_from_file_location("s6e_holdout_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    scratch = tmp_path_factory.mktemp("s6e_scratch_results")
    for name, manifest in SWEEP_MANIFESTS.items():
        result = run_sweep(manifest, results_root=scratch)
        assert result["sweep_id"] == SWEEP_IDS[name], (name, result["sweep_id"])
    run_ids = {}
    for name, manifest in RUN_MANIFESTS.items():
        executed = run_experiment(manifest, results_root=scratch)
        run_ids[name] = executed["run_id"]
    assert run_ids == RUN_IDS
    builder = _load_builder()
    builder.RESULTS = scratch
    record = builder.build_record()
    return record, scratch, run_ids


def test_scratch_rebuild_is_byte_identical_to_committed_copy(scratch_record):
    record, _, _ = scratch_record
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    assert COMMITTED_COPY.read_bytes() == record_bytes


def test_record_carries_valid_v2_evidence_dimensions(scratch_record):
    record, _, _ = scratch_record
    assert record["evidence_schema_version"] == 2
    assert not dimensions_problems(
        {k: record[k] for k in ("verification", "calibration_target", "held_out",
                                "independent_reproduction", "known_omissions")}
    )
    assert record["calibration_target"] == []
    assert record["held_out"]["held_out"] is True


def test_runs_are_evaluation_only(scratch_record):
    _, scratch, run_ids = scratch_record
    for name in RUN_IDS:
        payload = json.loads(
            (scratch / run_ids[name] / "run.json").read_text()
        )
        assert payload["evidence_schema_version"] == 2
        assert payload["held_out"]["held_out"] is True, name
        assert payload["calibration_target"] == [], name


def test_fitted_placements_carried_bit_exact_from_s4e(scratch_record):
    record, _, _ = scratch_record
    source = record["fitted_configurations_evaluated"]["source"]
    assert S4E_RECORD_ID[:8] in source
    placements = record["fitted_configurations_evaluated"]["placements"]
    assert Fraction(record["evaluation"]["gf11"]["r2_decomposition_point"]["placements"]["gf11_xbar2_e600"]["E_ns_exact"]) == 600
    assert Fraction(record["evaluation"]["gf11"]["r2_decomposition_point"]["placements"]["gf11_xbar2_e8800"]["E_ns_exact"]) == 8800
    assert "never selected" in placements["gf10_alt_e9000_flagged"]


def test_nothing_tunes_invariants(scratch_record):
    record, _, _ = scratch_record
    assert "no parameter is set to any of them" in record["nothing_tuned"]
    assert "no range is moved" in record["nothing_tuned"]
    # implied diagnostics are declared FROM the measurements, never set
    implied = record["evaluation"]["gf11"]["implied_effective_E"]
    assert "NOTHING is set to them" in implied["definition"]
    assert implied["in_range_members"] == [
        "r2_sol_crossbar", "r4_nearopt_crossbar", "r4_nearopt_ring", "r4_nearopt_exchange",
    ]
    assert implied["above_range_members"] == [
        "r4_nccl_crossbar", "r4_nccl_ring", "r4_nccl_exchange",
    ]
    assert Fraction(implied["per_point_exact"]["r2_sol_crossbar"]) == 1002
    assert Fraction(implied["per_point_exact"]["r4_nearopt_crossbar"]) == 1967


def test_gf01_band_is_entirely_above_the_range_top(scratch_record):
    record, _, _ = scratch_record
    implied = record["evaluation"]["gf01"]["implied_effective_E"]
    ring_band = [Fraction(v) for v in implied["ring_band_float"]]
    assert ring_band[0] == Fraction(9178)
    assert ring_band[1] > 9000
    assert "ENTIRELY ABOVE the declared range upper 9000" in implied["placement"]
    # the model rows stay strictly monotone while the measured band is not
    findings = record["evaluation"]["gf01"]["findings"]
    assert "NON-monotone" in findings["non_monotone_floor_inexpressible"]


def test_the_sharpened_falsification_is_the_deliverable(scratch_record):
    record, _, _ = scratch_record
    falsification = record["cross_anchor_observations"]["the_sharpened_falsification"]
    assert len(falsification) == 3
    joined = " ".join(falsification)
    assert "UNOCCUPIED WINDOW" in joined
    assert "EVIDENTIAL" in joined
    assert "RANGE-TOP CHALLENGE" in joined
    assert "software-stack/generation" in joined
    assert "SHAPE DEMANDS UNCHANGED" in joined
    assert "FIXED" in record["cross_anchor_observations"]["what_the_term_earned"]
    # and the record proposes no label anywhere
    assert "PROPOSED" in record["status"]


def test_split_record_id_is_the_immutable_one(scratch_record):
    record, _, _ = scratch_record
    assert (
        record["split_record"]["record_id"]
        == "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20"
    )
