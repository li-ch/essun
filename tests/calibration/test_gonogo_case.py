"""Immutability + fence guard for the G7 leg-(a) cross-engine case record
(anchor CAL-A3, the motivation case study).

This guard (a) rebuilds ``case_record_v1.json`` BYTE-IDENTICALLY from the
builder (a drift of the committed copy is an error: the record is
append-only, a change requires ``case_record_v2``); (b) re-executes the
twelve in-process essun-L0 runs into a scratch store and checks they
reproduce the declared content-addressed run ids and the exact completion
times the record carries (the ASTRA-sim legs need Docker and are verified
against the local store copy when present, skipped on a cold clone); and
(c) re-checks the audit's arithmetic invariants in exact Fractions: the
busbw convention reproduces the published series inside the publication's
rounding, the ring reading of the 32 GiB row exceeds the CAL-A2 vendor
line while the multicast reading stays below half of it, the fixed-B_fit
deviation ramp and the ceiling crossing have the recorded signs, and the
engine-B twin deltas are the recorded positive range.

Fence: this study never tunes toward the anchor — B_fit is the S2
recorded diagnostic carried unchanged; the {16,32} GiB rows are
within-series held-out from the fit (split record 3862e227...) and stay
report-only here; no holdout anchor is read; claim_id is empty on every
manifest.
"""

from __future__ import annotations

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest

from essun.orchestrator.runs import run_experiment

REPO = Path(__file__).resolve().parents[2]
CASE_DIR = REPO / "experiments" / "gonogo" / "case_a3_cross_engine"
BUILDER = CASE_DIR / "build_case_record.py"
COMMITTED_COPY = CASE_DIR / "case_record_v1.json"

L0_MANIFESTS = {
    ("l0x_fitb", "2GiB"): "run_a3-l0x-fitb-2gib.yaml",
    ("l0x_fitb", "4GiB"): "run_a3-l0x-fitb-4gib.yaml",
    ("l0x_fitb", "8GiB"): "run_a3-l0x-fitb-8gib.yaml",
    ("l0x_fitb", "16GiB"): "run_a3-l0x-fitb-16gib.yaml",
    ("l0x_fitb", "32GiB"): "run_a3-l0x-fitb-32gib.yaml",
    ("l0x_ceil900", "16GiB"): "run_a3-l0x-ceil900-16gib.yaml",
    ("l0x_ceil900", "32GiB"): "run_a3-l0x-ceil900-32gib.yaml",
    ("l0ring_b828", "2GiB"): "run_a3-l0ring-b828-2gib.yaml",
    ("l0ring_b828", "4GiB"): "run_a3-l0ring-b828-4gib.yaml",
    ("l0ring_b828", "8GiB"): "run_a3-l0ring-b828-8gib.yaml",
    ("l0ring_b828", "16GiB"): "run_a3-l0ring-b828-16gib.yaml",
    ("l0ring_b828", "32GiB"): "run_a3-l0ring-b828-32gib.yaml",
}
ASTRA_MANIFESTS = {
    size: f"run_a3-astra-b828-{size.lower()}.yaml"
    for size in ("2GiB", "4GiB", "8GiB", "16GiB", "32GiB")
}

ROUNDING_BOUND = Fraction(1, 40)  # 0.025 GB/s: publication rounds t to 0.01 us


def _load_builder():
    spec = importlib.util.spec_from_file_location("gonogo_case_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record() -> dict:
    return json.loads(COMMITTED_COPY.read_text(encoding="utf-8"))


def test_case_record_rebuilds_byte_identically() -> None:
    module = _load_builder()
    payload = json.dumps(module.build(), indent=2, sort_keys=True) + "\n"
    assert payload == COMMITTED_COPY.read_text(encoding="utf-8")


def test_l0_runs_reproduce_their_content_addressed_ids(tmp_path) -> None:
    # The twelve in-process legs re-execute deterministically into a
    # scratch store at the SAME content-addressed run ids with the SAME
    # exact completion times the committed record carries.
    record = _record()
    for (leg, size), manifest in L0_MANIFESTS.items():
        result = run_experiment(CASE_DIR / manifest, results_root=tmp_path)
        entry = record["rows"][["2GiB", "4GiB", "8GiB", "16GiB", "32GiB"].index(size)]["engines"][leg]
        assert result["run_id"] == entry["run_id"], (leg, size)
        observed = result["observations"]["observables"]["O-CCT"]
        exact = (
            observed["per_op"][0]["completion_time_ns_exact"]
            if "per_op" in observed
            else observed["completion_time_ns_mean_exact"]
        )
        assert exact == entry["completion_time_ns_exact"], (leg, size)


def test_astra_runs_match_the_record_when_the_store_copy_exists() -> None:
    # The ASTRA legs need Docker; on this development tree the store copy
    # must agree with the committed record (cold clones skip — the
    # reproduce path is the committed manifest).
    record = _record()
    for size, manifest in ASTRA_MANIFESTS.items():
        entry = record["rows"][["2GiB", "4GiB", "8GiB", "16GiB", "32GiB"].index(size)]["engines"]["astra_b828"]
        path = REPO / "results" / entry["run_id"] / "observations.json"
        if not path.is_file():
            pytest.skip(f"no local store copy for the ASTRA {size} run (cold clone)")
        observed = json.loads(path.read_text(encoding="utf-8"))["observables"]["O-CCT"]
        assert observed["completion_time_ns"] == int(entry["completion_time_ns_exact"])


def test_busbw_convention_reproduces_the_published_series() -> None:
    record = _record()
    for row in record["rows"]:
        delta = Fraction(row["busbw_convention_check"]["recomputed_minus_published_exact"])
        assert abs(delta) < ROUNDING_BOUND, row["size"]


def test_the_ring_reading_crosses_the_vendor_line_and_the_multicast_does_not() -> None:
    record = _record()
    by_size = {row["size"]: row for row in record["rows"]}
    ring = {s: Fraction(by_size[s]["ceiling_audit"]["ring_reading_pct_of_line_exact"]) for s in by_size}
    mc = {s: Fraction(by_size[s]["ceiling_audit"]["multicast_reading_pct_of_line_exact"]) for s in by_size}
    # Monotone ramp; the ring reading crosses 100% of the CAL-A2 line
    # between 16 and 32 GiB; the multicast reading stays below 51.5%.
    assert ring["2GiB"] < ring["4GiB"] < ring["8GiB"] < ring["16GiB"] < ring["32GiB"]
    assert ring["16GiB"] < 100 < ring["32GiB"]
    assert mc["32GiB"] == Fraction(17179869184, 33623284500) * 100  # algbw/900
    assert mc["32GiB"] < Fraction(515, 10)
    # The two readings differ by exactly the traffic-identity factor.
    assert ring["32GiB"] / mc["32GiB"] == Fraction(71, 36)


def test_fixed_parameter_deviation_ramp_and_ceiling_crossing() -> None:
    record = _record()
    by_size = {row["size"]: row for row in record["rows"]}
    fitb = {
        s: Fraction(by_size[s]["engines"]["l0x_fitb"]["deviation_vs_published_pct_exact"])
        for s in by_size
    }
    # The S2 known-omission finding, executed: the held-out sizes miss
    # high, the fit sizes bracket the minimax band (+/- 4.735% at the
    # exact fit sizes; the bracket payloads and the publication's 0.01 us
    # time rounding move the recomputed deviations by < 0.01 points).
    assert fitb["2GiB"] < 0 < fitb["32GiB"]
    # (recorded deviations are percent values: -4.735 = Fraction(-4735, 1000))
    assert abs(fitb["2GiB"] - Fraction(-4735, 1000)) < Fraction(1, 100)
    assert abs(fitb["8GiB"] - Fraction(4735, 1000)) < Fraction(1, 100)
    assert fitb["32GiB"] > fitb["16GiB"] > fitb["8GiB"]
    ceil16 = Fraction(by_size["16GiB"]["engines"]["l0x_ceil900"]["deviation_vs_published_pct_exact"])
    ceil32 = Fraction(by_size["32GiB"]["engines"]["l0x_ceil900"]["deviation_vs_published_pct_exact"])
    # Even the vendor ceiling line is crossed by the published series.
    assert ceil16 < 0 < ceil32


def test_the_twin_disagreement_is_the_recorded_positive_range() -> None:
    record = _record()
    twins = []
    for row in record["rows"]:
        entry = row["engines"]["l0ring_b828"]
        twin = Fraction(entry["twin_delta_astra_over_l0ring_pct_exact"])
        assert twin > 0, row["size"]  # engine B's Wall is slower at every size
        twins.append(twin)
    assert max(twins) == twins[0]  # largest at the smallest size (2 GiB)
    assert min(twins) == twins[-1]  # smallest at the largest size (32 GiB)
    assert Fraction(80) < twins[-1] < twins[0] < Fraction(119)


def test_b_twin_sits_above_the_unrepresentable_b_fit() -> None:
    record = _record()
    b_fit = Fraction(record["parameter_provenance"]["B_fit_exact"])
    delta = Fraction(record["parameter_provenance"]["b_twin_minus_b_fit_pct_exact"])
    assert Fraction(828) > b_fit  # nearest admissible integer ABOVE B_fit
    assert 0 < delta < Fraction(1, 10)  # +0.0988%


def test_every_gonogo_manifest_declares_v2_dimensions_and_empty_claim() -> None:
    # Fence: all seventeen runs carry the five-dimension block, target
    # CAL-A3 only, split-record held_out flags, and NO claim link.
    import yaml

    record = _record()
    manifests = list(L0_MANIFESTS.values()) + list(ASTRA_MANIFESTS.values())
    assert len(manifests) == 17
    for name in manifests:
        data = yaml.safe_load((CASE_DIR / name).read_text(encoding="utf-8"))
        assert data["claim_id"] == "", name
        assert data["calibration_target"] if False else data["evidence_dimensions"]["calibration_target"] == ["CAL-A3"], name
        dims = data["evidence_dimensions"]
        assert set(dims) == {
            "verification",
            "calibration_target",
            "held_out",
            "independent_reproduction",
            "known_omissions",
        }, name
        held = dims["held_out"]["held_out"]
        assert held == ("16gib" in name or "32gib" in name), name
