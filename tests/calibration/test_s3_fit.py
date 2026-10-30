"""Immutability + fence guard for the stage-S3 calibration fit record
(group G2: CAL-A6 + GF-02 + GF-04 per the split record's within-series
rules).

The S3 fit runs under the immutable split record (S1,
``3862e227…``): CAL-A6's degenerate split fits BOTH endpoint sizes per
NCCL version (no within-series holdout exists; the version pair is the
noise floor), GF-02's degenerate split fits the whole saturation band,
and GF-04's fit objective touches the 8-GPU single-node point ONLY — the
16-GPU two-node point is held out on the scaling dimension and is
reported as held-out error at the fitted B. No cross-anchor holdout (the
split's four holdout anchors, plus blocked GF-06) may be read by any
objective, swept value, or tolerance — sole recorded exception: the ~5%
mean-error scalar as tolerance-SHAPE context.

This guard re-executes the stage's whole evidence chain (the three fit
sweeps and the six dimensioned runs) into a scratch store and rebuilds
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
BUILDER = REPO / "experiments" / "calibration" / "s3" / "build_fit_record.py"
COMMITTED_COPY = REPO / "experiments" / "calibration" / "s3" / "fit_record_v1.json"
SWEEP_MANIFESTS = {
    "a6": REPO / "experiments" / "calibration" / "s3" / "sweep_s3_a6_bw_v1.yaml",
    "gf02": REPO / "experiments" / "calibration" / "s3" / "sweep_s3_gf02_bw_v1.yaml",
    "gf04": REPO / "experiments" / "calibration" / "s3" / "sweep_s3_gf04_tp8_bw_v1.yaml",
}
RUN_MANIFESTS = {
    "a6_fit_2193": REPO / "experiments" / "calibration" / "s3" / "run_s3_a6_fit_2193_16gib.yaml",
    "a6_fit_2203": REPO / "experiments" / "calibration" / "s3" / "run_s3_a6_fit_2203_16gib.yaml",
    "gf02_fit_ar": REPO / "experiments" / "calibration" / "s3" / "run_s3_gf02_fit_ar_16gib.yaml",
    "gf02_fit_ag": REPO / "experiments" / "calibration" / "s3" / "run_s3_gf02_fit_ag_twin.yaml",
    "gf04_fit_tp8": REPO / "experiments" / "calibration" / "s3" / "run_s3_gf04_fit_tp8_4gib.yaml",
    "gf04_hold_tp16": REPO / "experiments" / "calibration" / "s3" / "run_s3_gf04_holdout_tp16_4gib.yaml",
}
A6_FIT_TOPOLOGIES = {
    "2193": REPO / "experiments" / "calibration" / "s3" / "topologies" / "ring32_s3_fitb19_v1.yaml",
    "2203": REPO / "experiments" / "calibration" / "s3" / "topologies" / "ring32_s3_fitb20_v1.yaml",
}

SWEEP_IDS = {
    "a6": "26e275b7b3697b6f6640471e05fa0439ba122d3ee609f7ed5ba13c77842ed834",
    "gf02": "13bc507205108c718f06e836bf003f71d2ce84a8b02e8cec19e0d7ee6c8dab9c",
    "gf04": "96b91ab6dd42b5e084a17ff56b35694e29e5526b4de13b0a9298df2736002499",
}
RUN_IDS = {
    "a6_fit_2193": "ad7e937c83882b2bf0d117838a5d9a25e136a8a8f609a1f085eead5b2158e450",
    "a6_fit_2203": "7d7624054d2777655dd36a0ce0d620129e744d550f3c09a960c1f767134299d8",
    "gf02_fit_ar": "ffdd546d3a7a12342680808c1f56bb7eb9f3dcad6e9ecb7207c9f3a3b0bc43fb",
    "gf02_fit_ag": "96d480731cd2017be8d251f04c357e5a2739b9f62846b4e64fbb19254836fd17",
    "gf04_fit_tp8": "5af31f3b51ef54579371fcc4ae643cf567ebd900388d6cc2162da1c6904ad3d4",
    "gf04_hold_tp16": "ed77cce301ef938c5497e936904c01ce9665b1885099fd568e0f006a61ee2b48",
}

A6_FIT_SIZES = {"1 GiB", "16 GiB"}          # degenerate: BOTH sizes fit-side
GF02_BAND_BYTES = {1 << 27, 1 << 30, 1 << 34}  # the whole band is fit-side
GF04_FIT_BYTES = {1 << 30, 1 << 32, 1 << 33}
HOLDOUT_ANCHOR_IDS = ("GF-01", "GF-03", "GF-11", "GF-06")


def _load_builder():
    spec = importlib.util.spec_from_file_location("s3_fit_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the S3 evidence chain into a scratch store and rebuild
    the record from it (the documented reproduce path, end to end)."""
    scratch = tmp_path_factory.mktemp("s3_scratch_results")
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


def test_a6_fit_touches_only_the_degenerate_fit_sizes(scratch_record):
    record, _, _ = scratch_record
    for series in ("series_2_19_3", "series_2_20_3"):
        rows = record["fits"]["cal_a6"][series]["per_size_at_fitted_B"]
        assert {row["size"] for row in rows} == A6_FIT_SIZES
    # the A6 sweep's payloads are exactly the two fit sizes — nothing is held
    # out within CAL-A6 (degenerate split)
    _, scratch, _ = scratch_record
    table = json.loads((scratch / "sweeps" / SWEEP_IDS["a6"] / "table.json").read_text())
    assert {row["payload_bytes"] for row in table["configs"]} == {1 << 30, 1 << 34}


def test_gf02_fit_covers_the_whole_band_fit_side(scratch_record):
    record, _, _ = scratch_record
    residuals = record["fits"]["gf02"]["allreduce_residuals_across_band"]
    assert {int(k) for k in residuals} == GF02_BAND_BYTES
    _, scratch, _ = scratch_record
    table = json.loads((scratch / "sweeps" / SWEEP_IDS["gf02"] / "table.json").read_text())
    assert {row["payload_bytes"] for row in table["configs"]} == GF02_BAND_BYTES


def test_gf04_sweep_is_r8_only_and_holds_out_the_16_gpu_point(scratch_record):
    record, _, _ = scratch_record
    # the executed GF-04 fit sweep: r=8 topologies only, fit-side sizes only
    _, scratch, _ = scratch_record
    table = json.loads((scratch / "sweeps" / SWEEP_IDS["gf04"] / "table.json").read_text())
    assert {row["payload_bytes"] for row in table["configs"]} == GF04_FIT_BYTES
    for row in table["configs"]:
        assert "ring16" not in row["config_id"], row["config_id"]
        assert "crossbar16" not in row["config_id"], row["config_id"]
    # no r=16 topology in ANY S3 sweep (the mechanical held-out fence)
    for sweep_id in SWEEP_IDS.values():
        rows = json.loads((scratch / "sweeps" / sweep_id / "table.json").read_text())["configs"]
        for row in rows:
            assert "ring16" not in row["config_id"] and "crossbar16" not in row["config_id"]
    # the fit sections carry only the 8-GPU point; the 16-GPU point appears
    # ONLY in the held-out evaluation
    fit = record["fits"]["gf04"]
    assert set(fit["sweep_size_residuals"]) == {str(m) for m in GF04_FIT_BYTES}
    assert fit["fit_point_residual"]["payload_bytes"] == 1 << 32
    held = record["held_out_evaluation"]
    assert held["held_out_point"].startswith("GF-04's 16-GPU two-node leg")
    assert held["run_backing"]["held_out_dimension"]["held_out"] is True


def test_record_carries_valid_v2_evidence_dimensions(scratch_record):
    record, _, _ = scratch_record
    assert record["evidence_schema_version"] == 2
    assert not dimensions_problems(
        {k: record[k] for k in ("verification", "calibration_target", "held_out",
                                "independent_reproduction", "known_omissions")}
    )
    assert record["calibration_target"] == ["CAL-A6", "GF-02", "GF-04"]
    assert record["held_out"]["held_out"] is False


def test_run_records_dimensions_split_fit_vs_heldout(scratch_record):
    _, scratch, run_ids = scratch_record

    def run_payload(name):
        return json.loads((scratch / run_ids[name] / "run.json").read_text())

    expected_targets = {
        "a6_fit_2193": "CAL-A6", "a6_fit_2203": "CAL-A6",
        "gf02_fit_ar": "GF-02", "gf02_fit_ag": "GF-02",
        "gf04_fit_tp8": "GF-04", "gf04_hold_tp16": "GF-04",
    }
    for name, target in expected_targets.items():
        payload = run_payload(name)
        assert payload["calibration_target"] == [target]
        assert payload["evidence_schema_version"] == 2
        if name == "gf04_hold_tp16":
            assert payload["held_out"]["held_out"] is True   # evaluation-only
        else:
            assert payload["held_out"]["held_out"] is False


def test_no_holdout_anchor_numbers_or_ids_in_record(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    for anchor_id in HOLDOUT_ANCHOR_IDS:
        assert anchor_id not in text
    # the sole admitted holdout scalar context: the ~5% appears exactly once,
    # inside the CAL-A6 tolerance-shape provenance
    assert text.count("CAL-A4") == 1
    tau5 = record["fits"]["cal_a6"]["tolerance_shape_windows"]["tau_5pct"]
    assert "CAL-A4" in tau5["shape_provenance"]


def test_fitted_values_are_recorded_diagnostics_registry_untouched(scratch_record):
    record, _, _ = scratch_record
    a6 = record["fits"]["cal_a6"]
    for series, topo_key in (("series_2_19_3", "2193"), ("series_2_20_3", "2203")):
        exact = Fraction(a6[series]["minimax_B_exact"])
        topology_text = A6_FIT_TOPOLOGIES[topo_key].read_text(encoding="utf-8")
        assert f"{exact.numerator}/{exact.denominator}" in topology_text
        assert Fraction(1) < exact < Fraction(1024)   # inside the declared range
    assert Fraction(record["fits"]["gf02"]["fitted_B_exact"]) == Fraction(360)
    assert record["fits"]["gf02"]["fitted_B_materialized_as"].startswith(
        "the committed stage-GF-02 plateau topology"
    )
    assert Fraction(record["fits"]["gf04"]["fitted_B_exact"]) == Fraction("476.37")
    # the shipped registry values are untouched by the stage
    for param in ("A-L0-BW", "A-L0X-BW"):
        declared = record["model"]["declared_free_parameters"][param]
        assert declared["registry_value"] == 64
        assert declared["registry_range"] == [1, 1024]
    assert "PROPOSED" in record["status"]


def test_noise_floor_and_audit_blocks_present(scratch_record):
    record, _, _ = scratch_record
    floor = record["noise_floor_execution"]
    assert floor["fitted_B_separation_pct"] == pytest.approx(-3.656, abs=0.001)
    audit = record["gf02_gf04_audit"]
    assert audit["audit_rows"]["ratio_gf04_over_gf02_pct"] == pytest.approx(32.325, abs=0.01)
    assert "never averaged" in audit["classification"]
