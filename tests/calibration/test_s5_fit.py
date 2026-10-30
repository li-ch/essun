"""Immutability + fence guard for the stage-S5 calibration fit record
(group G4: CAL-A5 + CAL-A11 + GF-05 + GF-07 + GF-08 + GF-09 — the
geometry falsifier and the UEC/congestion envelopes — per the split
record's group assignment).

The S5 fit runs under the immutable split record (S1,
``3862e227…``): none of the six G4 anchors carries a within-series split
(the split record's within_series_splits lists only CAL-A3/CAL-A6/
GF-02/GF-04), so every executed payload is fit-side and no held-out
reporting run exists in this stage. No cross-anchor holdout (the split's
four holdout anchors, plus blocked GF-06) may be read by any objective,
swept value, or tolerance — S5's record carries ZERO holdout anchor ids
in its bytes, a strictly stronger fence than naming the sole admitted
exception (the ~5% mean-error scalar is referenced descriptively, as
noise-scale context, exactly once).

This guard re-executes the stage's whole evidence chain (the three
sweeps and the seven dimensioned runs) into a scratch store and rebuilds
the fit record BYTE-IDENTICALLY from it, then checks the separation
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
S5 = REPO / "experiments" / "calibration" / "s5"
BUILDER = S5 / "build_fit_record.py"
COMMITTED_COPY = S5 / "fit_record_v1.json"
SWEEP_MANIFESTS = {
    "torus128": S5 / "sweep_s5_torus128_v1.yaml",
    "torus256": S5 / "sweep_s5_torus256_v1.yaml",
    "envelope": S5 / "sweep_s5_envelope_v1.yaml",
}
RUN_MANIFESTS = {
    "a5_slice128": S5 / "run_s5_a5_slice128.yaml",
    "a5_slice256": S5 / "run_s5_a5_slice256.yaml",
    "a11_carrier": S5 / "run_s5_a11_carrier.yaml",
    "gf05_simconfig": S5 / "run_s5_gf05_simconfig.yaml",
    "gf07_carrier": S5 / "run_s5_gf07_carrier.yaml",
    "gf08_falcon": S5 / "run_s5_gf08_falcon.yaml",
    "gf09_uec50": S5 / "run_s5_gf09_uec50.yaml",
}

SWEEP_IDS = {
    "torus128": "9351c33052f72e2dc56049ea1894011e49f8b8d0e9102abf81c296a895c94b9b",
    "torus256": "c0b0e9618c34de2e081db5b161e3da1dc6f8046d79032d65a35b3992bdc9e3dd",
    "envelope": "a489d720259ee6f3eb7bc0b7872d03fcf5dbb19f7f370dee8769c2aa8f7b25b5",
}
RUN_IDS = {
    "a5_slice128": "43091e1545280c151bb56769897cff7e538e3c3e8935d8ab11bb5599d49c9458",
    "a5_slice256": "645e8b4f2a733ab358c60be719c1575757ec21bc6ed0ffd8402c7a146fbbb6b5",
    "a11_carrier": "7f8dfd7fd28f65e42c458004f0f952f47ae7b5d5db115bd7d0e7638a92981837",
    "gf05_simconfig": "f96b688ca8524eaebb846b46819edcbbe10c367687c7ddacf2524c7235a59ae1",
    "gf07_carrier": "e14917e9f91c47020d5c29e75d473fcbc385a9cecf389247b7192d47f4670017",
    "gf08_falcon": "09cae0bf8cbc0739c334b8b7ae6786eb72f7eeb85d137dd338c49f56a8ca0b16",
    "gf09_uec50": "610653fb4b9d9bf82f51a73ec91d8cb84ba7309bd9a0d7674c859f1501c7cbb7",
}

HOLDOUT_ANCHOR_IDS = ("GF-01", "GF-03", "GF-11", "GF-06", "CAL-A4")
ANCHOR_IDS = ["CAL-A5", "CAL-A11", "GF-05", "GF-07", "GF-08", "GF-09"]
GRID_B = {Fraction(64 * k) for k in range(1, 17)}
LADDER = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
          134217728, 268435456, 536870912, 2147483648, 8589934592]


def _load_builder():
    spec = importlib.util.spec_from_file_location("s5_fit_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the S5 evidence chain into a scratch store and rebuild
    the record from it (the documented reproduce path, end to end)."""
    scratch = tmp_path_factory.mktemp("s5_scratch_results")
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


# ---------------------------------------------------------------------------
# byte identity + evidence dimensions
# ---------------------------------------------------------------------------

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
    assert record["calibration_target"] == ANCHOR_IDS
    assert record["held_out"]["held_out"] is False


def test_all_seven_runs_fit_side_and_declare_their_anchor(scratch_record):
    record, scratch, run_ids = scratch_record
    assert "NONE of the six G4 anchors carries a within-series split" in \
        record["split_record"]["within_series_rules"]
    expected_targets = {
        "a5_slice128": "CAL-A5", "a5_slice256": "CAL-A5",
        "a11_carrier": "CAL-A11", "gf05_simconfig": "GF-05",
        "gf07_carrier": "GF-07", "gf08_falcon": "GF-08",
        "gf09_uec50": "GF-09",
    }
    for name, target in expected_targets.items():
        payload = json.loads((scratch / run_ids[name] / "run.json").read_text())
        assert payload["evidence_schema_version"] == 2, name
        assert payload["calibration_target"] == [target], name
        assert payload["held_out"]["held_out"] is False, name


# ---------------------------------------------------------------------------
# the no-leakage fence (S5: zero holdout ids, including the exception id)
# ---------------------------------------------------------------------------

def test_no_holdout_anchor_ids_or_numbers_in_record(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    for anchor_id in HOLDOUT_ANCHOR_IDS:
        assert anchor_id not in text
    # the sole admitted holdout scalar is referenced DESCRIPTIVELY (never by
    # id), exactly twice: once in the no-leakage rule statement, once as
    # noise-scale context in the falsifier provenance
    assert text.count("~5% mean-error scalar") == 2
    prov = record["fits"]["cal_a5"]["noise_scale_comparison_provenance"]
    assert "~5% mean-error scalar" in prov
    assert "~5% mean-error scalar" in record["split_record"]["no_leakage"]


# ---------------------------------------------------------------------------
# the falsifier (CAL-A5)
# ---------------------------------------------------------------------------

def test_falsifier_blind_spots_and_below_floor_arithmetic(scratch_record):
    record, _, _ = scratch_record
    fal = record["fits"]["cal_a5"]["falsifier"]
    assert float(fal["slice_128"]["blind_spot_pct"]) == 63.0
    assert float(fal["slice_256"]["blind_spot_pct"]) == 31.0
    for key, floor in (("slice_128", Fraction(8800)), ("slice_256", Fraction(15200))):
        row = fal[key]
        assert Fraction(row["b_to_infinity_latency_chain_floor_ns_exact"]) == floor
        # the executed statement of the falsification: the anchor's ratio read
        # onto the model's own point demands a CCT BELOW the B->infinity floor
        assert Fraction(row["required_twisted_cct_ns_exact"]) < floor
        assert "lies BELOW the identity's B->infinity floor" in \
            row["falsification_2_b_axis_cannot_reach_it"]
    # the delivered fractions are the exact closed forms over executed rows
    assert Fraction(fal["slice_128"]["delivered_fraction_of_required_gain_exact"]) == \
        Fraction(23200, 433125)
    assert Fraction(fal["slice_256"]["delivered_fraction_of_required_gain_exact"]) == \
        Fraction(23600, 368125)
    # the executed displacement rows deliver ~1.3%/0.5% against the required
    # 38.65%/23.66% cuts — the misattribution demonstration
    for key, required_pct in (("slice_128", 38.65), ("slice_256", 23.66)):
        disp = fal[key]["executed_twist_displacement_row"]
        assert disp["cct_cut_vs_anchor_point_pct"] < 2.0, key
        assert abs(disp["required_cut_pct"] - required_pct) < 0.01, key
        assert "never selected" in disp["statement"]


def test_twist_displacement_rows_are_executed_in_the_torus_sweeps(scratch_record):
    _, scratch, _ = scratch_record
    for sweep_id, ranks, suffix in (
        (SWEEP_IDS["torus128"], 128, "81_5"),   # 50 x 1.63, decimal file naming
        (SWEEP_IDS["torus256"], 256, "65_5"),   # 50 x 1.31
    ):
        table = json.loads((scratch / "sweeps" / sweep_id / "table.json").read_text())
        stems = {row["config_id"].split("-")[2] for row in table["configs"]}
        assert f"torus2d{ranks}_s5_8x{'16' if ranks == 128 else '32'}_b{suffix}_v1" in stems
        # every torus sweep row sits at the anchor's single DMA payload
        assert {row["payload_bytes"] for row in table["configs"]} == {4096}


def test_l_absorption_alternative_flagged_never_selected(scratch_record):
    record, _, _ = scratch_record
    alt = record["fits"]["cal_a5"]["axis_absorption_alternatives"]
    for key, lo_hi in (("slice_128", (Fraction(10), Fraction(2000))),
                       ("slice_256", (Fraction(10), Fraction(2000)))):
        l_val = Fraction(alt[key]["L_absorption_alternative_exact"])
        assert lo_hi[0] < l_val < lo_hi[1], key  # in range BUT
        assert alt[key]["in_declared_range"] is True
        assert "never selected" in alt[key]["status"]


def test_a5_registry_placements_exact(scratch_record):
    record, _, _ = scratch_record
    placement = record["fits"]["cal_a5"]["per_link_placement"]
    assert Fraction(placement["registry_point_contrast"]["registry_64_over_reading1_exact"]) \
        == Fraction(32, 25)


# ---------------------------------------------------------------------------
# the envelope sweep: convergence law + range admittance
# ---------------------------------------------------------------------------

def test_envelope_convergence_law_monotone_with_exact_asymptotes(scratch_record):
    record, _, _ = scratch_record
    law = record["executed_sweeps"]["envelope"]["convergence_law"]
    rows = law["rows"]
    assert len(rows) == 16
    for row in rows:
        f = Fraction(row["factor_exact"])
        assert Fraction(row["B_carrier_exact"]) / Fraction(row["B_edge_exact"]) == f
        assert row["ratio_at_8kib_float"] < row["ratio_at_8gib_float"] < float(f)
    worst = next(r for r in rows if r["factor_exact"] == "25")
    assert Fraction(worst["ratio_at_8kib_exact"]) == Fraction(2075, 283)
    assert Fraction(worst["asymptotic_shortfall_exact"]) == Fraction(5000, 78293883)


def test_every_edge_and_carrier_inside_the_declared_range(scratch_record):
    record, _, _ = scratch_record
    law = record["executed_sweeps"]["envelope"]["convergence_law"]["rows"]
    for row in law:
        for key in ("B_edge_exact", "B_carrier_exact"):
            assert Fraction(1) <= Fraction(row[key]) <= Fraction(1024), row
    # the executed statement in the record
    assert "INSIDE the declared A-L0X-BW range" in \
        record["executed_sweeps"]["envelope"]["all_edges_inside_declared_range"]


def test_envelope_grid_is_anchor_blind(scratch_record):
    record, scratch, _ = scratch_record
    table = json.loads(
        (scratch / "sweeps" / SWEEP_IDS["envelope"] / "table.json").read_text())
    payloads = {row["payload_bytes"] for row in table["configs"]}
    assert payloads == set(LADDER)
    # the 16 grid members are exactly the 64-multiples 64..1024
    grid_stems = {row["config_id"].split("-")[2] for row in table["configs"]
                  if row["config_id"].split("-")[2].startswith("crossbar8_s5_b")}
    parsed = {}
    for stem in grid_stems:
        stem_b = stem.split("_b", 1)[1].split("_l200")[0]
        parsed[Fraction(stem_b.replace("_", "."))] = stem
    assert GRID_B <= set(parsed)
    # the registry row is the sweep baseline
    assert table["baseline"]["topology"].endswith("crossbar8_s5_b64_l200_v1.yaml")


def test_convergence_law_recomputed_from_scratch_rows(scratch_record):
    _, scratch, _ = scratch_record
    table = json.loads(
        (scratch / "sweeps" / SWEEP_IDS["envelope"] / "table.json").read_text())
    by = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        if row["payload_bytes"] in (8192, 8589934592):
            by[(topo, row["payload_bytes"])] = Fraction(
                row["o_cct"]["completion_time_ns_mean_exact"])
    # the worst edge vs its carrier: monotone compression, exact bottom ratio
    edge = by[("crossbar8_s5_b4_l200_v1", 8192)]
    carrier = by[("crossbar8_s5_b100_l200_v1", 8192)]
    assert edge / carrier == Fraction(2075, 283)
    edge_top = by[("crossbar8_s5_b4_l200_v1", 8589934592)]
    carrier_top = by[("crossbar8_s5_b100_l200_v1", 8589934592)]
    assert edge_top / carrier_top == Fraction(1957342075, 78293883)  # 25 - 5000/78293883


# ---------------------------------------------------------------------------
# per-anchor inexpressibility / placement facts
# ---------------------------------------------------------------------------

def test_gf08_ops_rate_inexpressible_from_below(scratch_record):
    record, _, _ = scratch_record
    ops = record["fits"]["gf08"]["ops_rate_axis_inexpressible"]
    assert Fraction(ops["implied_pair_L_exact"]) == Fraction(25, 6)
    assert Fraction(ops["implied_pair_L_exact"]) < 10  # below the range lower
    assert Fraction(ops["floor_over_per_op_at_range_lower_exact"]) == Fraction(12, 5)
    assert Fraction(ops["floor_over_per_op_at_registry_exact"]) == 48


def test_gf09_design_target_constrains_nothing(scratch_record):
    record, _, _ = scratch_record
    gf09 = record["fits"]["gf09"]["how_a_design_target_constrains_a_fit"]
    constraint = gf09["constraint_on_fit_values"]
    assert constraint.startswith("NONE")
    assert "ZERO falsification power" in constraint
    assert "NO fit objective" in constraint
    placements = gf09["registry_placements"]
    assert Fraction(placements["target_rtt_over_declared_range_upper_exact"]) == \
        Fraction(5, 2)
    assert "NOT moved" in placements["range_not_moved"]
    # the class-floor direction is stated as OPPOSITE to the spec ceilings
    assert "OPPOSITE" in gf09["normalization_only_use"]


def test_gf05_sim_config_in_range_and_gf07_envelope_span(scratch_record):
    record, _, _ = scratch_record
    gf05 = record["fits"]["gf05"]["sim_config_provenance"]
    assert gf05["L_per_hop_in_declared_A_L0X_LAT_range"] is True
    assert Fraction(gf05["registry_200_over_anchor_1000_exact"]) == Fraction(1, 5)
    gf07 = record["fits"]["gf07"]["envelope_table_exact"]
    assert Fraction(gf07["span_floor_to_ceiling_exact"]) == Fraction(95, 4)
    summary = record["envelope_summary"]["delivered_fractions_and_spans"]
    assert Fraction(summary["gf07_envelope_span_floor_to_ceiling_exact"]) == Fraction(95, 4)


def test_a11_proxy_fence_and_carrier_placement(scratch_record):
    record, _, _ = scratch_record
    a11 = record["fits"]["cal_a11"]
    assert "labeled-proxy" in a11["role"] or "labeled proxy" in a11["role"]
    assert "does NOT falsify" in a11["where_the_model_sits"]
    assert Fraction(a11["carrier_placement"]["registry_64_over_carrier_exact"]) == \
        Fraction(32, 25)


# ---------------------------------------------------------------------------
# registry discipline (nothing tuned)
# ---------------------------------------------------------------------------

def test_bw_registry_values_untouched_everywhere(scratch_record):
    record, _, _ = scratch_record
    declared = record["model"]["declared_free_parameters"]
    for param in ("A-L0T-BW", "A-L0X-BW"):
        assert declared[param]["registry_value"] == 64
        assert declared[param]["registry_range"] == [1, 1024]
    # and the shipped registry file itself still says the same
    import yaml

    registry = yaml.safe_load(
        (REPO / "experiments" / "vertical_slice" / "assumptions_l0.yaml").read_text()
    )
    by_id = {e["id"]: e for e in registry["assumptions"]}
    for param in ("A-L0T-BW", "A-L0X-BW"):
        assert by_id[param]["value"] == 64, param
        assert list(by_id[param]["range"]) == [1, 1024], param
    for param in ("A-L0T-LAT", "A-L0X-LAT"):
        assert by_id[param]["value"] == 200, param
        assert list(by_id[param]["range"]) == [10, 2000], param
    assert "PROPOSED" in record["status"]


def test_adapter_registry_untouched_and_declared(scratch_record):
    record, _, _ = scratch_record
    duty = record["split_record"]["parameter_axes_duty"]
    assert "A-AS2-* adapter entries stay in their own registry" in duty
    # mechanically: no ASTRA-side content rides the S5 record
    assert "astra" not in canonical_json(record).lower()


def test_no_oct_fit_claimed_for_group_g4(scratch_record):
    record, _, _ = scratch_record
    assert "no O-CCT fit exists in this group" in record["status"]
    assert "envelope/context checks, not O-CCT fits" in \
        record["group_g4_anchors"]["no_oct_fit_exists"]
    # the torus sweeps execute only the anchor's DMA payload (no series exists
    # to fit against — the payload fence)
    for key in ("torus128", "torus256"):
        rows = record["executed_sweeps"][key]["rows"]
        assert len(rows) in (22, 23)
        assert "payload 4096" in record["executed_sweeps"][key]["payload_fence"]
