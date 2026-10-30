"""Immutability + fence guard for the stage-S4 calibration fit record
(group G3: CAL-A8 + CAL-A9 + CAL-A10 + GF-10 — the latency axis — per the
split record's group assignment).

The S4 fit runs under the immutable split record (S1,
``3862e227…``): the four G3 anchors carry NO within-series split (the
split record's within_series_splits lists only CAL-A3/CAL-A6/GF-02/
GF-04), so every executed payload is fit-side and no held-out reporting
run exists in this stage. No cross-anchor holdout (the split's four
holdout anchors, plus blocked GF-06) may be read by any objective,
swept value, or tolerance — sole recorded exception: CAL-A4's ~5%
mean-error scalar as tolerance-SHAPE context (named exactly once, inside
the tolerance-shape provenance).

This guard re-executes the stage's whole evidence chain (the two sweeps
and the five dimensioned runs) into a scratch store and rebuilds the
fit record BYTE-IDENTICALLY from it, then checks the separation
invariants on the committed record. A drift of the committed copy is an
error: the record is append-only (a change requires fit_record_v2).
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
BUILDER = REPO / "experiments" / "calibration" / "s4" / "build_fit_record.py"
COMMITTED_COPY = REPO / "experiments" / "calibration" / "s4" / "fit_record_v1.json"
SWEEP_MANIFESTS = {
    "lat": REPO / "experiments" / "calibration" / "s4" / "sweep_s4_lat_v1.yaml",
    "boundary": REPO / "experiments" / "calibration" / "s4" / "sweep_s4_boundary_v1.yaml",
}
RUN_MANIFESTS = {
    "a8_l64": REPO / "experiments" / "calibration" / "s4" / "run_s4_a8_fit_l64.yaml",
    "a8_l140": REPO / "experiments" / "calibration" / "s4" / "run_s4_a8_fit_l140.yaml",
    "a9_l80": REPO / "experiments" / "calibration" / "s4" / "run_s4_a9_fit_pair80.yaml",
    "a10_l800": REPO / "experiments" / "calibration" / "s4" / "run_s4_a10_fit_pair800.yaml",
    "gf10_l9000": REPO / "experiments" / "calibration" / "s4" / "run_s4_gf10_anchor_l9000.yaml",
}

SWEEP_IDS = {
    "lat": "778f67f319e8771f525a929b6ef698b11b938c6188c2ed521a5edc4ebee1aeab",
    "boundary": "f2afb64120237a1fdb2e788769de48239a3f8ce11fd579ae7bcab559729324a7",
}
RUN_IDS = {
    "a8_l64": "2ca54ead178cd0a361be29124c3e4c37053d1e75125ac02600792384dc5e905d",
    "a8_l140": "774cc400a6446bd77d4f28e0a297462a0bbfee84e6c8b1e7d8fe3803c964a66d",
    "a9_l80": "95222277ecad82b9dd8f063465d13b9ad2733b50338fa772e059163749a8808d",
    "a10_l800": "6c3b7566eeedd0595bc197cb21bacd3a03f9ce45ea69dd803bd1e43e27d02ce2",
    "gf10_l9000": "a54446b6d774d7853fef7a84e08bb0230cd9bb8a28e4f3a35601f3cbb54f4080",
}

EXPECTED_GRID_L = {Fraction(v) for v in (10, 16, 32, 64, 128, 200, 256, 512, 1024, 2000)}
EXPECTED_PROV_L = {Fraction(80), Fraction(140), Fraction(800), Fraction(9000)}
HOLDOUT_ANCHOR_IDS = ("GF-01", "GF-03", "GF-11", "GF-06")
SMOKE = 16384


def _load_builder():
    spec = importlib.util.spec_from_file_location("s4_fit_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the S4 evidence chain into a scratch store and rebuild
    the record from it (the documented reproduce path, end to end)."""
    scratch = tmp_path_factory.mktemp("s4_scratch_results")
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


def _committed_record() -> dict:
    return json.loads(COMMITTED_COPY.read_text(encoding="utf-8"))


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
    assert record["calibration_target"] == ["CAL-A8", "CAL-A9", "CAL-A10", "GF-10"]
    assert record["held_out"]["held_out"] is False


def test_no_within_series_holdout_exists_all_runs_fit_side(scratch_record):
    record, _, run_ids = scratch_record
    # the split record's within_series_splits has no G3 anchor; the record
    # states it and every run is fit-side
    assert "NONE of the four G3 anchors carries a within-series split" in record["split_record"]["within_series_rules"]
    assert record["held_out"]["held_out"] is False
    for name in RUN_IDS:
        payload = json.loads(
            (scratch_record[1] / run_ids[name] / "run.json").read_text()
        )
        assert payload["evidence_schema_version"] == 2
        assert payload["held_out"]["held_out"] is False, name


def test_run_records_dimensions_declare_their_anchor(scratch_record):
    _, scratch, run_ids = scratch_record
    expected_targets = {
        "a8_l64": "CAL-A8", "a8_l140": "CAL-A8", "a9_l80": "CAL-A9",
        "a10_l800": "CAL-A10", "gf10_l9000": "GF-10",
    }
    for name, target in expected_targets.items():
        payload = json.loads((scratch / run_ids[name] / "run.json").read_text())
        assert payload["calibration_target"] == [target]


def test_no_holdout_anchor_numbers_or_ids_in_record(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    for anchor_id in HOLDOUT_ANCHOR_IDS:
        assert anchor_id not in text
    # the sole admitted holdout scalar context: CAL-A4 named exactly once,
    # inside the CAL-A8 tolerance-shape provenance
    assert text.count("CAL-A4") == 1
    tau_prov = record["fits"]["cal_a8"]["tolerance_shape_windows"]["shape_provenance"]
    assert "CAL-A4" in tau_prov


def test_grid_is_anchor_blind_and_provenance_is_labeled(scratch_record):
    record, _, _ = scratch_record
    per_l = record["executed_sweeps"]["lat_axis"]["per_L_table_crossbar"]
    grid_members = {Fraction(row["L_ns"]) for row in per_l if row["grid_member"]}
    assert grid_members == EXPECTED_GRID_L
    non_grid = {Fraction(row["L_ns"]) for row in per_l if not row["grid_member"]}
    assert non_grid == EXPECTED_PROV_L
    for row in per_l:
        if not row["grid_member"]:
            assert row["provenance"].startswith("anchor:"), row
    # 64 is a grid member by powers-of-two arithmetic; its CAL-A8 coincidence
    # is NOT provenance (the note appears inside the grid label)
    row64 = next(r for r in per_l if Fraction(r["L_ns"]) == 64)
    assert row64["grid_member"] is True
    assert "COINCIDENCE" in row64["provenance"]


def test_gf10_miss_is_reported_never_tuned(scratch_record):
    record, _, _ = scratch_record
    gf10 = record["fits"]["gf10"]
    assert gf10["fitted_L"]["required_exact"] == "9000"
    assert "OUTSIDE the declared free range" in gf10["fitted_L"]["range_membership"]
    best = gf10["fitted_L"]["best_in_range"]
    assert best["L_exact"].startswith("2000")
    assert Fraction(best["cct_miss_at_smoke_exact"]) == Fraction(-875, 1153)
    assert best["floor_miss_exact"] == "-5/9"
    # the in-range ring-chain alternative exists, is flagged, never selected
    alt = record["executed_sweeps"]["lat_axis"]["schedule_absorption_alternative"]
    assert alt["L_exact"] == "4500/7"
    assert "never selected" in alt["status"]
    assert Fraction(*map(int, alt["L_exact"].split("/"))) < 2000
    # the registry range itself is NOT moved by the miss
    narrow = record["registry_discipline"]["narrow_range_upper_candidate"]
    assert "does NOT validate" in narrow
    assert "The registry range [10, 2000] is NOT changed" in narrow


def test_latency_registry_values_untouched(scratch_record):
    record, _, _ = scratch_record
    declared = record["model"]["declared_free_parameters"]
    for param in ("A-L0-LAT", "A-L0X-LAT", "A-L0T-LAT", "A-L0D-LAT"):
        assert declared[param]["registry_value"] == 200
        assert declared[param]["registry_range"] == [10, 2000]
    # and the shipped registry file itself still says the same
    import yaml

    registry = yaml.safe_load(
        (REPO / "experiments" / "vertical_slice" / "assumptions_l0.yaml").read_text()
    )
    by_id = {e["id"]: e for e in registry["assumptions"]}
    for param in ("A-L0-LAT", "A-L0X-LAT", "A-L0T-LAT", "A-L0D-LAT"):
        entry = by_id[param]
        assert entry["value"] == 200, param
        assert list(entry["range"]) == [10, 2000], param
    assert "PROPOSED" in record["status"]


def test_chain_laws_recomputed_from_scratch_rows(scratch_record):
    _, scratch, _ = scratch_record
    table = json.loads(
        (scratch / "sweeps" / SWEEP_IDS["lat"] / "table.json").read_text()
    )
    by = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        alg = row["algorithm"]
        by[(alg, topo)] = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
    for v in (10, 16, 32, 64, 80, 128, 140, 200, 256, 512, 800, 1024, 2000, 9000):
        l_value = Fraction(v)
        ring = by[("allreduce_ring", f"ring8_s4_l{v}_v1")]
        xbar = by[("allreduce_crossbar", f"crossbar8_s4_l{v}_v1")]
        rd = by[("allreduce_recursive_doubling", f"exchange8_s4_l{v}_v1")]
        torus = by[("allreduce_torus2d", f"torus8_s4_l{v}_v1")]
        assert ring - xbar == 12 * l_value, v
        assert rd - xbar == 4 * l_value, v
        assert ring - rd == 8 * l_value, v
        assert torus - xbar == Fraction(192) + 6 * l_value, v
    # the ring-only alternative row charges exactly GF-10's headline
    alt = by[("allreduce_ring", "ring8_s4_l4500_7_v1")]
    assert alt - Fraction(448) == Fraction(9000)


def test_boundary_crossover_facts(scratch_record):
    record, _, _ = scratch_record
    cross = record["executed_sweeps"]["boundary"]["crossover_spectrum_exact"]
    anchor_own = cross["gf10_own_numbers_crossbar"]
    assert anchor_own["flat_p100_16384_inside"] is True
    assert anchor_own["flat_v100_65536_inside"] is True
    assert Fraction(anchor_own["M_star_exact"]) == Fraction(8 * 9000 * 25, 7)
    reg = cross["registry_pair_crossbar"]
    assert Fraction(reg["M_star_exact"]) == Fraction(102400, 7)
    assert Fraction(28, 25) == Fraction(SMOKE) / Fraction(102400, 7)
    assert "28/25" in reg["smoke_sits_above_by_exact"]


def test_fitted_values_are_degenerate_anchor_values(scratch_record):
    record, _, _ = scratch_record
    assert record["fits"]["cal_a8"]["fitted_L"]["low_exact"] == "64"
    assert record["fits"]["cal_a8"]["fitted_L"]["high_exact"] == "140"
    assert record["fits"]["cal_a9"]["fitted_L"]["one_stage_pair_exact"] == "80"
    assert record["fits"]["cal_a10"]["fitted_L"]["exact"] == "800"
    # exact registry placements (transcription-bug fence)
    assert record["fits"]["cal_a8"]["registry_placements"]["registry_200_over_a8_low_64_exact"] == "25/8"
    assert record["fits"]["cal_a8"]["registry_placements"]["registry_200_over_a8_high_140_exact"] == "10/7"
    assert record["fits"]["cal_a9"]["registry_placements"]["registry_200_over_pair_80_exact"] == "5/2"
    assert record["fits"]["cal_a10"]["registry_placements"]["registry_200_over_assumption_800_exact"] == "1/4"
    assert record["fits"]["gf10"]["registry_placements"]["range_upper_2000_over_9000_exact"] == "2/9"


def test_predictions_for_s6_are_model_side_only(scratch_record):
    record, _, _ = scratch_record
    preds = record["predictions_for_s6"]
    text = canonical_json(preds)
    for anchor_id in HOLDOUT_ANCHOR_IDS + ("CAL-A4",):
        assert anchor_id not in text
    table = preds["predictions_table"]
    assert set(table) == {"registry_200", "a8_64", "a8_140", "a9_80", "a10_800", "gf10_9000"}
    # every prediction is an executed sweep row value (spot: crossbar at 80)
    assert Fraction(table["a9_80"]["crossbar_chain2L_ns_exact"]) == Fraction(608)
    assert Fraction(table["gf10_9000"]["ring_chain14L_ns_exact"]) == Fraction(448) + 14 * 9000


def test_b_sensitivity_cross_checks_present(scratch_record):
    record, _, _ = scratch_record
    block = record["b_sensitivity_cross_checks"]
    assert block["check_1_fits_are_b_free"].startswith("the four fitted L values are parameter-axis placements")
    assert block["check_1_fits_are_b_free"].endswith("exactly B-free, not merely insensitive); the degenerate fits cannot move with B")
    assert "28:25" in block["check_3_the_regime_is_mixed_at_the_registry_pair"]
