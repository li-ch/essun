"""Immutability + fence guard for the stage-S6 calibration holdout record
(the split record's four holdout anchors: CAL-A4 + GF-01 + GF-03 + GF-11 —
evaluated against the LANDED fitted configurations of S2-S5).

S6 is the split record's evaluation-only stage (``3862e227…``): the four
holdout anchors' numbers are EVALUATION targets — unlike S2-S5, this
record necessarily CONTAINS the holdout anchor ids and their measured
numbers. The fences therefore invert to NOTHING-TUNES invariants:

1. every executed value is a landed fitted configuration carried
   BIT-EXACT from its fit record (content addresses re-verified; the
   fitted values in the S6 record asserted equal to the S2/S3/S4 records'
   own exact rationals) or the untouched registry point;
2. the shipped registry (assumptions_l0.yaml) still carries
   64 B/ns and 200 ns with ranges [1, 1024] / [10, 2000];
3. every S6 run record declares ``calibration_target: []`` and
   ``held_out: true`` with an evaluation-only scope naming its anchor;
4. no tolerance is adopted anywhere (E0 zero-slack stands) — the misses
   and non-evaluations are recorded findings, never tuned away;
5. GF-06 is untouched (named once, inside the nothing-tuned statement).

This guard re-executes the stage's whole evidence chain (8 sweeps + 4
dimensioned runs) into a scratch store and rebuilds the holdout record
BYTE-IDENTICALLY from it, then checks the invariants on the committed
record. A drift of the committed copy is an error: the record is
append-only (a change requires holdout_record_v2).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest

from essun.contracts import load_yaml
from essun.evidence.dimensions import dimensions_problems
from essun.evidence.store import canonical_json
from essun.orchestrator.runs import run_experiment
from essun.orchestrator.sweeps import run_sweep

REPO = Path(__file__).resolve().parents[2]
S6 = REPO / "experiments" / "calibration" / "s6"
BUILDER = S6 / "build_holdout_record.py"
COMMITTED_COPY = S6 / "holdout_record_v1.json"

SWEEP_MANIFESTS = {
    name: S6 / f"sweep_s6_{name}_v1.yaml"
    for name in ("a4_ring4", "a4_ring16", "gf01_bw", "gf01_small",
                 "gf03", "gf11_tp2", "gf11_tp4", "gf11_tp64")
}
RUN_MANIFESTS = {
    "a4": S6 / "run_s6_a4_eval.yaml",
    "gf01": S6 / "run_s6_gf01_eval.yaml",
    "gf03": S6 / "run_s6_gf03_eval.yaml",
    "gf11": S6 / "run_s6_gf11_eval.yaml",
}
SWEEP_IDS = {
    "a4_ring4": "3a34576656e090f3830beaffdf85da14d48863c079ebb6a327bb8ed3f8600704",
    "a4_ring16": "9f8580e5a085bdddfc6128b6b505265772d1867ec308da0064e2ed10c656428a",
    "gf01_bw": "e2b963723e37f1c023147fc81ec7ee9479fe1ee9e8eee38d663c2f0939326b15",
    "gf01_small": "bb092e47925a716950253ad954400d4227dca1d66d1dd91abe02e3f908b74ca7",
    "gf03": "f86f189a80c31a6785015d4e7ae1e86639d335ccc2d58949f41954866c2364b2",
    "gf11_tp2": "5fbf7e902cbe42486549775ff37af3f2805f5d82320d31ed83fbc0cf329c5791",
    "gf11_tp4": "fe243b3a56da92baa79cc03eda258a6698b9f5a80fc15fe7453803e30c590714",
    "gf11_tp64": "1340cbeb22e3dc408fb613fe39804419383bc2e3adf2a7695134fe8af8c22ad7",
}
RUN_IDS = {
    "a4": "e1d2aede889d31c43aa510f86eb7bc4f478f1d82a8b601acdfd29bd07b553b71",
    "gf01": "d70ef4265dcba35f760f44d2ca617a5fc75d2165c730805f0424b9b29800bb99",
    "gf03": "f99ca410bb13d8e9cd910f7bd8ebf63ca66b59d84f309948b4a64cfc7d81287e",
    "gf11": "7eda947ca7025b99bea378719f6ec54c42c85f02753a17777596bebdddf30075",
}
SPLIT_ID = "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20"
FIT_IDS = {
    "s2": "31b0d090f918ba486775d204912a1b9cc82a5f2f3b758ccebc0142967e6df24f",
    "s3": "23036816e86f81025853decde3b846809f0560f4e3922619ef9eddb52a6106b5",
    "s4": "ef9c4517d18913645a90ee3daa26b1bc365a978a10efdf78d276fbf9418101df",
    "s5": "43fca722ff77711d67b2879dca1407510dd6a60132e047d6b34fd7b7ee6bb34b",
}
HOLDOUT_ANCHORS = ("CAL-A4", "GF-01", "GF-03", "GF-11")


def _load_builder():
    spec = importlib.util.spec_from_file_location("s6_holdout_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the S6 evidence chain into a scratch store and rebuild
    the record from it (the documented reproduce path, end to end)."""
    scratch = tmp_path_factory.mktemp("s6_scratch_results")
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
    # evaluation-only: NOTHING is calibrated against holdout data
    assert record["calibration_target"] == []
    assert record["held_out"]["held_out"] is True


def test_every_run_declares_evaluation_only_dimensions(scratch_record):
    _, scratch, run_ids = scratch_record
    anchor_by_run = {"a4": "CAL-A4", "gf01": "GF-01", "gf03": "GF-03", "gf11": "GF-11"}
    for name, anchor in anchor_by_run.items():
        payload = json.loads((scratch / run_ids[name] / "run.json").read_text())
        assert payload["evidence_schema_version"] == 2, name
        assert payload["calibration_target"] == [], name
        assert payload["held_out"]["held_out"] is True, name
        assert anchor in payload["held_out"]["scope"], name
        assert payload["manifest"]["claim_id"] == "", name


def test_all_four_holdout_anchors_evaluated_or_recorded(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    for anchor in HOLDOUT_ANCHORS:
        assert anchor in text
    # CAL-A4's non-evaluation is RECORDED, not forced
    a4 = record["evaluation"]["cal_a4"]
    assert a4["cct_evaluation"]["verdict"].startswith("NON-EVALUATION")
    assert "NO hardware (size -> time) series" in a4["cct_evaluation"]["reason"]
    # the other three carry recorded errors
    for anchor_key in ("gf01", "gf03", "gf11"):
        assert record["evaluation"][anchor_key]["verdict"].startswith("EVALUATED")


def test_nothing_tunes_fitted_values_bit_exact_vs_fit_records(scratch_record):
    record, _, _ = scratch_record
    # the four fit records and the split record are unchanged
    split = REPO / "experiments" / "calibration" / "split" / "anchor_split_v1.json"
    assert hashlib.sha256(split.read_bytes()).hexdigest() == SPLIT_ID
    s2r = json.loads((REPO / "experiments" / "calibration" / "s2" / "fit_record_v1.json").read_text())
    s3r = json.loads((REPO / "experiments" / "calibration" / "s3" / "fit_record_v1.json").read_text())
    s4r = json.loads((REPO / "experiments" / "calibration" / "s4" / "fit_record_v1.json").read_text())
    for stage, rid in FIT_IDS.items():
        path = REPO / "experiments" / "calibration" / stage / "fit_record_v1.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == rid, stage
    # the S6 record's evaluated values equal the fit records' own values
    fitted = record["fitted_configurations_evaluated"]
    assert fitted["s2_xbar_cal_a3"]["B_exact"] == s2r["fit"]["minimax_B_exact"]
    assert fitted["s3_ring_a6_2193"]["B_exact"] == s3r["fits"]["cal_a6"]["series_2_19_3"]["minimax_B_exact"]
    assert fitted["s3_ring_a6_2203"]["B_exact"] == s3r["fits"]["cal_a6"]["series_2_20_3"]["minimax_B_exact"]
    assert fitted["s3_xbar_gf02"]["B_exact"] == s3r["fits"]["gf02"]["fitted_B_exact"]
    assert fitted["s3_ring_gf04"]["B_exact"] == s3r["fits"]["gf04"]["fitted_B_exact"]
    assert fitted["s5"]["configuration"].startswith("NONE")
    # the executed topology files carry those same values (spot: the S2 fit)
    fitb = load_yaml(S6 / "topologies" / "crossbar8_s6_fitb_s2_gf03_v1.yaml")
    assert Fraction(str(fitb["nic"]["injection_bytes_per_ns"])) == Fraction(s2r["fit"]["minimax_B_exact"])


def test_registry_untouched_in_shipped_assumptions(scratch_record):
    """A-L0X-BW / A-L0-BW stay 64 [1, 1024]; the LAT axes stay 200
    [10, 2000] — S6 moved nothing."""
    data = load_yaml(REPO / "experiments" / "vertical_slice" / "assumptions_l0.yaml")
    by_id = {a["id"]: a for a in data["assumptions"]}
    for bw in ("A-L0-BW", "A-L0X-BW", "A-L0T-BW", "A-L0D-BW"):
        assert by_id[bw]["value"] == 64 and by_id[bw]["range"] == [1, 1024], bw
    for lat in ("A-L0-LAT", "A-L0X-LAT", "A-L0T-LAT", "A-L0D-LAT"):
        assert by_id[lat]["value"] == 200 and by_id[lat]["range"] == [10, 2000], lat


def test_gf06_untouched_single_mention(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    assert text.count("GF-06") == 1  # only inside the nothing-tuned statement
    assert "GF-06" in record["nothing_tuned"]["gf06_untouched"]


def test_gf01_large_message_errors_exact(scratch_record):
    record, _, _ = scratch_record
    rows = record["evaluation"]["gf01"]["large_message_16gib"]["rows"]
    by_name = {r["fitted_configuration"]: r for r in rows}
    # every fitted configuration over-predicts bandwidth (time below anchor)
    for r in rows:
        assert Fraction(r["ratio_model_over_anchor_exact"]) < 1
    # exact pinned values (transcription guards against narrative drift)
    t_anchor = Fraction("94254.55") * 1000
    wire = Fraction(2 * 7 * 17179869184, 8)
    assert by_name["s3_xbar_gf02"]["cct_ns_exact"] == str(wire / Fraction(360) + 400)
    assert by_name["s2_xbar_cal_a3"]["ratio_model_over_anchor_float"] == pytest.approx(0.38562, abs=1e-4)
    assert by_name["s3_xbar_gf02"]["ratio_model_over_anchor_float"] == pytest.approx(0.88604, abs=1e-4)
    # the implied effective B is pinned exact
    impl = record["evaluation"]["gf01"]["large_message_16gib"]["anchor_implied_effective_B"]
    assert Fraction(impl["value_exact"]) == wire / (t_anchor - 400)


def test_gf03_plateau_transfer_and_band_miss_exact(scratch_record):
    record, _, _ = scratch_record
    plateau = record["evaluation"]["gf03"]["plateau_837"]["effective_B_transfer"]
    b_fit = Fraction("19561820264071168/23648730912675")
    assert Fraction(plateau["B_fit_over_837_exact"]) == b_fit / Fraction(837)
    assert plateau["B_fit_over_837_float"] == pytest.approx(0.98827, abs=1e-5)
    # the executed probe ratio is the 1/B ratio plus the pure 2L term
    probe = plateau["executed_probe"]
    t_ref = Fraction(2 * 7 * 2**34, 8) / Fraction(837)
    t_model = Fraction(2 * 7 * 2**34, 8) / b_fit + 400
    assert probe["model_cct_ns_exact"] == str(t_model)
    assert Fraction(probe["ratio_model_over_anchor_ref_exact"]) == t_model / t_ref
    # the 2 MiB miss and its no-combination verdict are present and pinned
    band = record["evaluation"]["gf03"]["cct_row_2mib"]
    assert band["model_cct_ns_exact"] == str(Fraction(2 * 7 * 2**21, 8) / b_fit + 400)
    assert band["miss_factor_float"][0] == pytest.approx(8.685, abs=1e-2)
    nc = band["no_combination_check"]
    assert Fraction(nc["largest_below_band_exact"]) == Fraction(2 * 7 * 2**21, 8) / Fraction(360) + 14 * 1600
    assert Fraction(nc["smallest_above_band_exact"]) == Fraction(2 * 7 * 2**21, 8) / Fraction(50) + 128


def test_gf11_bracket_straddle_and_scaling_exact(scratch_record):
    record, _, _ = scratch_record
    r4 = record["evaluation"]["gf11"]["r4_bracket"]["rows"]
    cross = Fraction(r4["a10_800"]["crossbar"]["cct_ns_exact"])
    exch = Fraction(r4["a10_800"]["exchange"]["cct_ns_exact"])
    ring = Fraction(r4["a10_800"]["ring"]["cct_ns_exact"])
    assert cross == 1603 and exch == 3203 and ring == 4803
    # the near-optimal leg lands between the two shortest chains
    assert cross < 2370 < exch
    # the stock leg sits above its own ring identity
    assert Fraction(r4["a10_800"]["ring"]["over_nccl_11000_exact"]) == pytest.approx(0.4366, abs=1e-4)
    # implied L diagnostics pinned exact
    impl = record["evaluation"]["gf11"]["r4_bracket"]["implied_effective_L"]
    assert Fraction(impl["crossbar_from_oneshot_exact"]) == Fraction(2367, 2)
    assert Fraction(impl["ring_from_nccl_leg_exact"]) == Fraction(10997, 6)
    # r=2: only the A10 placement is in the measured decade
    r2 = record["evaluation"]["gf11"]["r2_decomposition_point"]["fitted_placements_vs_sol"]
    assert r2["a10_800"]["cct_ns_exact"] == "1602"
    assert Fraction(r2["a10_800"]["cct_over_sol_exact"]) == Fraction(89, 78)
    for key in ("a8_64", "a9_80", "a8_140", "registry_200"):
        assert Fraction(r2[key]["cct_over_sol_exact"]) < Fraction(1, 3)
    # r=64 growth: chain-constant ratios, measured growth between flat and 6x
    growth = record["evaluation"]["gf11"]["r64_scaling"]["identity_chain_growth_at_L800"]
    assert growth["crossbar"]["growth_float"] < 1.002          # rank-flat
    assert 5.9 < growth["exchange"]["growth_float"] < 6.4      # 12L vs 2L plus wire
    assert Fraction(170, 107) > growth["crossbar"]["growth_float"]
    assert Fraction(170, 107) < growth["exchange"]["growth_float"]


def test_cal_a4_placement_and_generation_gap(scratch_record):
    record, _, _ = scratch_record
    gap = record["evaluation"]["cal_a4"]["executed_placement"]["generation_gap_vs_anchor_quote"]["ratios"]
    assert Fraction(gap["s3_ring_a6_2203"]["B_over_150_exact"]) == Fraction(
        "115757383942144/309086671475") / 150
    for r in gap.values():
        lo, hi = Fraction(249, 100), Fraction(16, 5)
        assert lo < Fraction(r["B_over_150_exact"]) < hi       # 2.497x .. 3.176x
    # both rank sweeps executed and cross-checked
    checked = record["backing"]["executed_rows_cross_checked"]
    assert checked["a4_ring4"] == 18 and checked["a4_ring16"] == 18
    assert sum(checked.values()) == 195


def test_s7_handoff_names_the_five_omission_axes(scratch_record):
    record, _, _ = scratch_record
    om = record["known_omissions_for_s7"]
    assert len(om) == 5
    text = canonical_json(om)
    for axis in ("size-dependent software-effective bandwidth",
                 "fabric asymmetry", "software/endpoint latency",
                 "congestion/load-balance/CM semantics", "torus geometry"):
        assert axis in text
    # S6 never promotes anything: the S7 proposal is pending
    assert "pending owner adjudication" in canonical_json(record).lower() or \
           record["status"].startswith("PROPOSED")
