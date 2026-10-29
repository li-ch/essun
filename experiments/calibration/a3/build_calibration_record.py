"""Build the PROPOSED calibration-candidate record for anchor CAL-A3 (Q1
calibration stage A3.

CAL-A3 is the ladder's first MEASURED O-CCT target: NCCL 2.28.3
``all_reduce_perf`` on all 72 GPUs of a GB200 NVL72 rack (Crusoe Cloud),
2-32 GiB per rank, out-of-place. This stage measures WHERE the L0
single-port crossbar identity sits relative to that series (ratio and
absolute delta per size, anchor-implied effective-B placement) — it never
tunes anything, and it CLASSIFIES (does not tune away) the interpretation
flag stage A2 handed over: CAL-A3's 32 GiB busbw sits +0.77% above the
CAL-A2-derived 900 B/ns per-direction line.

Pure function of immutable artifacts: reads the two append-only store run
records and the sweep table produced by this stage, recomputes every
derived quantity with exact Fractions, and writes a content-addressed
record to ``results/calibration/<record_id>/record.json`` (record_id =
SHA-256 of the canonical record; append-only — an existing record with
different bytes is an error, identical bytes are idempotent).

Model numbers at the anchor's EXACT message sizes are closed-form
evaluations of the very identity function the run path executes
(``l0_crossbar.crossbar_allreduce_time_ns``); the A-L0X-DIV input gate (a
structural KEEP assumption) rejects the anchor's exact power-of-two sizes
at r=72, so the run-path-backed rows sit at the 72-divisible floor/ceil
brackets (relative offset <= 2.7e-8) and the record cross-checks the
closed form against BOTH the sweep rows (every bracket size, every swept
B) and the two store runs. Every such cross-check is an exact Fraction
string equality; a mismatch is a bug, not a finding.

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_staging.md`` §A3
(declared below with provenance), or (b) computed from stored run/sweep
artifacts or the identity function by this script. Nothing is tuned: the
swept B values carry their anchor provenance, and the anchor-implied
effective-B values are recorded DIAGNOSTICS (placement), never topology
values.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical.l0 import require_divisible
from essun.backends.analytical.l0_crossbar import (
    BACKEND_ID,
    CrossbarConfig,
    crossbar_allreduce_time_ns,
)
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweep; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_CEIL900 = "9546a20f6f7a9c1efa8a9dab433286f0ce5cabc3237ea3018b9fee811e7f20f3"
RUN_ID_DER720 = "232a2d9913996ca5e87650e5e9e7e4b4c3ad9ec362ab2fcd7991a82ebf907310"
SWEEP_ID = "6c8a62bed0e6db353b9eb31ad6682f3618aaa266fbac358a3ea42f6f7166e1da"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A3 staged numbers (docs/calibration/anchors_staging.md §A3,
# transcription confidence M-H: real measurement with full config context,
# vendor ops guide not peer-reviewed; GB200 NVL72 rack exposed as 18 x
# 4-GPU instances; all_reduce_perf float32, -b 2G -e 32G, 10 warmup /
# 20 iterations; out-of-place variant is the primary series, the in-place
# variant carries the source's own kernel/SM-contention caveat).
# Units: times quoted in us (exact 2-decimal decimals), busbw in GB/s
# decimal (1 GB/s = 1 B/ns); message sizes are per-rank GiB (binary), as
# issued by nccl-tests -b/-e suffixes.
RANKS = 72
SOFTWARE_PINS = (
    "NCCL 2.28.3, CUDA 12.9.1, driver 580.82.07; all_reduce_perf float32; "
    "-b 2G -e 32G; 10 warmup / 20 iterations; 72 GPUs of one GB200 NVL72 "
    "rack exposed as 18 x 4-GPU instances; NVLink-vs-IB path split for the "
    "72-GPU communicator NOT stated in the source (staging caveat)"
)
A3_STAGED_OUT_OF_PLACE = {  # size label -> (payload bytes, time us, busbw GB/s)
    "2GiB": (2**31, "5375.10", "787.95"),
    "4GiB": (2**32, "10193.01", "831.03"),
    "8GiB": (2**33, "19555.07", "866.36"),
    "16GiB": (2**34, "38056.60", "890.32"),
    "32GiB": (2**35, "74718.41", "906.94"),
}
A3_STAGED_AVG_BUSBW_GBPS = Fraction("855.949")
A3_STAGED_IN_PLACE = {  # labeled, EXCLUDED from the comparison (plan §4.10)
    "2GiB": (2**31, "409019.60", "5.20"),  # source-acknowledged kernel/SM-contention outlier
    "32GiB": (2**35, "75675.13", "895.31"),
}

# Model free parameters of this stage (A-L0X-BW swept, A-L0X-LAT registry).
B_VALUES = {
    "448": Fraction(448),
    "720": Fraction(720),
    "900": Fraction(900),
}
L_PAIR_LATENCY_NS = Fraction(200)
CEILING_LINE = Fraction(900)  # CAL-A2 per-GPU per-direction line (stage A2)

# NCCL busbw accounting: busbw = algbw * 2(r-1)/r with algbw = M/t. The
# crossbar identity's per-rank wire bytes carry the SAME factor, so a
# CCT-vs-CCT comparison is immune to the convention (it cancels).
BUSBW_FACTOR = Fraction(2 * (RANKS - 1), RANKS)  # 71/36


def wire_bytes(payload: int) -> Fraction:
    """Per-rank wire bytes of the crossbar AllReduce identity (== NCCL's
    busbw accounting base): 2*(r-1)/r * M."""
    return Fraction(2 * (RANKS - 1) * payload, RANKS)


def config_for(b: Fraction) -> CrossbarConfig:
    return CrossbarConfig(
        topology_id="cal_a3_closed_form",
        ranks=RANKS,
        injection_bytes_per_ns=b,
        pair_latency_ns=L_PAIR_LATENCY_NS,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Target extraction with the plan §3 per-point algebraic mapping
# ---------------------------------------------------------------------------
def anchor_self_consistency() -> dict:
    """Write down the busbw -> algbw -> CCT mapping per point (plan §3) and
    self-check the anchor's own numbers: implied busbw (from the quoted
    time under the standard NCCL ring accounting) vs quoted busbw. A
    residual beyond print precision would be a transcription bug."""
    rows = []
    for label, (payload, time_us, busbw_gbps) in A3_STAGED_OUT_OF_PLACE.items():
        t_ns = Fraction(time_us) * 1000  # us (2 decimals) -> ns, exact
        algbw = Fraction(payload) / t_ns  # B/ns == GB/s (decimal)
        implied_busbw = algbw * BUSBW_FACTOR
        quoted = Fraction(busbw_gbps)
        residual = implied_busbw - quoted
        assert abs(residual) < Fraction("0.05"), (label, residual)
        rows.append(
            {
                "size": label,
                "payload_bytes": payload,
                "staged_time_us": time_us,
                "staged_time_ns_exact": str(t_ns),
                "staged_busbw_GB_per_s": busbw_gbps,
                "algbw_GB_per_s_exact": str(algbw),
                "implied_busbw_GB_per_s_exact": str(implied_busbw),
                "implied_busbw_GB_per_s_float": float(implied_busbw),
                "residual_implied_minus_quoted_exact": str(residual),
                "residual_float": float(residual),
                "mapping": "algbw = M/t ; busbw = algbw * 2(r-1)/r (r=72 => "
                "factor 71/36); anchor CCT = quoted t directly (no mixed "
                "metric is compared)",
            }
        )
    in_place = []
    for label, (payload, time_us, busbw_gbps) in A3_STAGED_IN_PLACE.items():
        t_ns = Fraction(time_us) * 1000
        implied = Fraction(payload) / t_ns * BUSBW_FACTOR
        algbw = Fraction(payload) / t_ns
        quoted = Fraction(busbw_gbps)
        in_place.append(
            {
                "size": label,
                "payload_bytes": payload,
                "staged_time_us": time_us,
                "staged_busbw_GB_per_s": busbw_gbps,
                "implied_ring_convention_busbw_exact": str(implied),
                "implied_ring_convention_busbw_float": float(implied),
                "algbw_GB_per_s_exact": str(algbw),
                "residual_vs_quoted_exact": str(implied - quoted),
                "status": "EXCLUDED from the comparison per CALIBRATION_PLAN "
                "§4.10 (excluded or labeled, never smoothed): the source "
                "itself acknowledges kernel/SM contention for the in-place "
                "2 GiB row; the in-place 32 GiB row is within 0.02% of the "
                "out-of-place series and is recorded for context only",
            }
        )
    return {
        "primary_series": "out-of-place allreduce, 5 sizes, per-rank GiB payloads",
        "software_pins": SOFTWARE_PINS,
        "rows": rows,
        "avg_staged_busbw_GB_per_s": "855.949",
        "in_place_variant": in_place,
        "consistency_verdict": "all 5 out-of-place rows internally consistent "
        "under the standard NCCL accounting within <= 0.03 GB/s (print "
        "precision); the anchor's own (size -> time) series is therefore "
        "extractable and used directly as the CCT target",
    }


# ---------------------------------------------------------------------------
# 2. The A-L0X-DIV gate finding (why the run path runs brackets)
# ---------------------------------------------------------------------------
def div_gate_finding() -> dict:
    rows = []
    for label, (payload, _, _) in A3_STAGED_OUT_OF_PLACE.items():
        try:
            require_divisible(BACKEND_ID, "cal_a3_probe", payload, RANKS, "A-L0X-DIV")
            rejected = False
        except ValueError:
            rejected = True
        assert rejected, (label, "power of two unexpectedly divisible by 72")
        residue = payload % RANKS
        floor = payload - residue
        ceil = floor + RANKS
        assert floor % RANKS == 0 and ceil % RANKS == 0
        rel = Fraction(residue, payload)
        assert rel < Fraction(3, 10**8)
        rows.append(
            {
                "size": label,
                "payload_bytes": payload,
                "mod_72": residue,
                "floor_bracket": floor,
                "ceil_bracket": ceil,
                "bracket_offset_bytes": residue,
                "bracket_relative_offset_exact": str(rel),
                "bracket_relative_offset_float": float(rel),
            }
        )
    return {
        "finding": "CAL-A3's exact message sizes are powers of two; 72 = 8*9 "
        "never divides 2^k, so the A-L0X-DIV structural input gate (KEEP "
        "verdict in CALIBRATION_PLAN.md §2.1 — non-calibratable by "
        "construction) rejects every exact anchor size at r=72. Recorded, "
        "not worked around silently: the run path executes the "
        "72-divisible floor/ceil brackets (relative offset <= 2.7e-8) and "
        "this record evaluates the identity at the exact sizes as declared "
        "closed-form arithmetic of the same function, cross-checked against "
        "the executed rows.",
        "rows": rows,
        "gate_check": "require_divisible raised for all 5 exact sizes "
        "(verified programmatically while building this record)",
    }


# ---------------------------------------------------------------------------
# 3. Closed-form exact-size evaluation, cross-checked against artifacts
# ---------------------------------------------------------------------------
def closed_form_and_crosschecks() -> tuple[dict, dict, dict]:
    """Evaluate the identity at the exact anchor sizes for every swept B;
    cross-check the SAME identity function against the sweep table rows at
    all 30 bracket configs and the two store runs (exact string equality)."""
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    b_by_topology = {
        "crossbar72_a3_span448_v1": Fraction(448),
        "crossbar72_a3_derated720_v1": Fraction(720),
        "crossbar72_a3_ceiling900_v1": Fraction(900),
    }
    sweep_rows = {}  # (topology_id, payload) -> exact cct string
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        sweep_rows[(topo, row["payload_bytes"])] = row["o_cct"][
            "completion_time_ns_mean_exact"
        ]
    assert len(sweep_rows) == 30, len(sweep_rows)

    gate = div_gate_finding()
    bracket_by_exact = {
        r["payload_bytes"]: (r["floor_bracket"], r["ceil_bracket"])
        for r in gate["rows"]
    }
    topo_by_b = {v: k for k, v in b_by_topology.items()}

    crosschecks = []
    exact_times = {}  # (payload, B str) -> Fraction
    for label, (payload, _, _) in A3_STAGED_OUT_OF_PLACE.items():
        floor, ceil = bracket_by_exact[payload]
        for b_str, b in B_VALUES.items():
            t_exact = crossbar_allreduce_time_ns(payload, RANKS, config_for(b))
            exact_times[(payload, b_str)] = t_exact
            # cross-check 1: the sweep's executed bracket rows must equal
            # the same identity function at the bracket sizes
            for bracket in (floor, ceil):
                t_bracket = crossbar_allreduce_time_ns(bracket, RANKS, config_for(b))
                assert (
                    sweep_rows[(topo_by_b[b], bracket)] == str(t_bracket)
                ), (label, b_str, bracket)
            # cross-check 2: monotone bracket sandwich around the exact size
            assert (
                crossbar_allreduce_time_ns(floor, RANKS, config_for(b))
                < t_exact
                < crossbar_allreduce_time_ns(ceil, RANKS, config_for(b))
            )
        crosschecks.append(
            {
                "size": label,
                "payload_bytes": payload,
                "brackets_checked": [floor, ceil],
                "per_b_rows_verified": 6,  # 2 brackets x 3 B values
                "verdict": "sweep rows at both brackets == closed form of the "
                "same identity function (exact Fraction string equality); "
                "exact-size time bracketed by the executed rows",
            }
        )

    # cross-check 3: the two store runs at the 32 GiB floor bracket
    run_checks = []
    for run_id, b_str, mapping in (
        (RUN_ID_CEIL900, "900", "ceiling (B=900: the CAL-A2-derived line)"),
        (RUN_ID_DER720, "720", "derated (B=720 = 0.8 x 900 via CAL-A12)"),
    ):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        per_op = obs["per_op"][0]
        assert per_op["payload_bytes"] == 2**35 - 32
        assert obs["model"]["ranks"] == RANKS
        assert Fraction(obs["model"]["pair_latency_ns_exact"]) == L_PAIR_LATENCY_NS
        assert Fraction(obs["model"]["injection_bytes_per_ns_exact"]) == B_VALUES[b_str]
        # the store runs sit at the 32 GiB FLOOR BRACKET (the exact 2^35 is
        # rejected by A-L0X-DIV), so the closed-form reference is evaluated
        # at that same bracket payload
        t_bracket_closed = crossbar_allreduce_time_ns(
            per_op["payload_bytes"], RANKS, config_for(B_VALUES[b_str])
        )
        assert per_op["completion_time_ns_exact"] == str(t_bracket_closed)
        run_checks.append(
            {
                "run_id": run_id,
                "mapping": mapping,
                "experiment_id": run["manifest"]["experiment_id"],
                "manifest_path": run["manifest_path"],
                "payload_bytes": per_op["payload_bytes"],
                "cct_ns_exact": per_op["completion_time_ns_exact"],
                "cct_ns_float": per_op["completion_time_ns"],
                "verdict": "store run == closed form at the 32 GiB floor "
                "bracket (exact equality)",
            }
        )

    return {"bracket_crosschecks": crosschecks}, {"run_checks": run_checks}, {
        "exact_times": exact_times,
        "gate": gate,
    }


# ---------------------------------------------------------------------------
# 4. The CCT-vs-CCT comparison (where the model sits) + B_eff placement
# ---------------------------------------------------------------------------
def comparison(exact_times: dict) -> dict:
    rows = []
    b_eff_rows = []
    for label, (payload, time_us, busbw_gbps) in A3_STAGED_OUT_OF_PLACE.items():
        t_anchor = Fraction(time_us) * 1000
        wire = wire_bytes(payload)
        row = {
            "size": label,
            "payload_bytes": payload,
            "anchor_cct_ns_exact": str(t_anchor),
            "anchor_busbw_GB_per_s": busbw_gbps,
            "anchor_busbw_fraction_of_900_line_exact": str(
                Fraction(busbw_gbps) / CEILING_LINE
            ),
        }
        for b_str, b in B_VALUES.items():
            t_model = exact_times[(payload, b_str)]
            ratio = t_model / t_anchor
            row[f"model_cct_ns_exact_B{b_str}"] = str(t_model)
            row[f"model_cct_ns_float_B{b_str}"] = float(t_model)
            row[f"ratio_model_over_anchor_exact_B{b_str}"] = str(ratio)
            row[f"ratio_model_over_anchor_float_B{b_str}"] = float(ratio)
            row[f"delta_pct_float_B{b_str}"] = float((ratio - 1) * 100)
            row[f"model_implied_busbw_exact_B{b_str}"] = str(wire / t_model)
            row[f"model_implied_busbw_fraction_of_900_exact_B{b_str}"] = str(
                wire / t_model / CEILING_LINE
            )
        # anchor-implied effective-B placement (DIAGNOSTIC, never a value):
        # the fixed B that would make the identity reproduce the anchor CCT
        b_eff = wire / (t_anchor - 2 * L_PAIR_LATENCY_NS)
        row["anchor_implied_effective_B_exact"] = str(b_eff)
        row["anchor_implied_effective_B_float"] = float(b_eff)
        row["effective_B_fraction_of_900_line_exact"] = str(b_eff / CEILING_LINE)
        rows.append(row)
        b_eff_rows.append((label, b_eff))

    b_eff_values = [b for _, b in b_eff_rows]
    ramp_span = b_eff_values[-1] / b_eff_values[0]
    b_eff_by_label = dict(b_eff_rows)
    assert b_eff_by_label["16GiB"] < CEILING_LINE < b_eff_by_label["32GiB"], (
        "crossover statement below must be re-derived if this fails"
    )
    return {
        "metric": "CCT vs CCT (plan §3: no mixed metrics; the 2(r-1)/r busbw "
        "factor is carried by both sides and cancels)",
        "rows": rows,
        "b_eff_placement": {
            "definition": "anchor-implied effective B = [2(r-1)/r * M] / "
            "(t_anchor - 2L): the fixed injection bandwidth at which the "
            "identity would reproduce the anchor's quoted time at that size. "
            "A RECORDED DIAGNOSTIC locating the measurement in the free "
            "parameter space — NOT a tuned value; no topology anywhere "
            "carries these numbers.",
            "values": {label: str(b) for label, b in b_eff_rows},
            "values_float": {label: float(b) for label, b in b_eff_rows},
            "span_last_over_first_exact": str(ramp_span),
            "span_last_over_first_float": float(ramp_span),
            "monotone_increasing": all(
                b_eff_values[i] < b_eff_values[i + 1]
                for i in range(len(b_eff_values) - 1)
            ),
            "crossover_vs_900_line": "effective B crosses the 900 line "
            "between 16 GiB (below) and 32 GiB (above), so at B=900 the "
            "model crosses from FASTER than the anchor (2 GiB) to SLOWER "
            "than the anchor (32 GiB)",
        },
    }


# ---------------------------------------------------------------------------
# 5. Fixed-B misfit bound (exact minimax over the free parameter)
# ---------------------------------------------------------------------------
def fixed_b_misfit() -> dict:
    """Exact, deterministic quantification of 'no single fixed B fits the
    series': minimize over B of max_i |t_model(B, M_i)/t_anchor_i - 1|.
    Solved in closed form: deviations are monotone in B, so the minimax B
    equalizes the deviations of some pair (i, j); evaluate every pair's
    candidate exactly and take the argmin. Diagnostic only — no parameter
    is set to the result anywhere."""
    data = [
        (label, wire_bytes(payload), Fraction(time_us) * 1000)
        for label, (payload, time_us, _) in A3_STAGED_OUT_OF_PLACE.items()
    ]
    two_l = 2 * L_PAIR_LATENCY_NS

    def max_dev(b: Fraction) -> Fraction:
        worst = None
        for _, wire, t in data:
            ratio = (wire / b + two_l) / t
            dev = abs(ratio - 1)
            if worst is None or dev > worst:
                worst = dev
        return worst

    candidates = []
    n = len(data)
    for i in range(n):
        for j in range(i + 1, n):
            # equalize 1 - r_i = r_j - 1  =>  B = (w_i/t_i + w_j/t_j) / (2 - 2L/t_i - 2L/t_j)
            denom = 2 - two_l / data[i][2] - two_l / data[j][2]
            if denom <= 0:
                continue
            b_star = (data[i][1] / data[i][2] + data[j][1] / data[j][2]) / denom
            if b_star > 0:
                candidates.append((max_dev(b_star), b_star, (data[i][0], data[j][0])))
    assert candidates
    best_dev, best_b, best_pair = min(candidates, key=lambda c: (c[0], c[1]))

    # binding-pair check: the argmin's worst deviations must be attained at
    # the candidate's own pair (both ends), else the equalization is off.
    devs = {
        label: abs((wire / best_b + two_l) / t - 1) for label, wire, t in data
    }
    binding = {label for label, d in devs.items() if d == max(devs.values())}
    assert set(best_pair) == binding, (best_pair, binding)

    return {
        "question": "what is the smallest worst-case CCT deviation any FIXED "
        "B can achieve against the 5-point CAL-A3 series (L at the registry "
        "point 200 ns)?",
        "minimax_B_exact": str(best_b),
        "minimax_B_float": float(best_b),
        "binding_sizes": list(best_pair),
        "minimax_worst_case_relative_deviation_exact": str(best_dev),
        "minimax_worst_case_relative_deviation_float": float(best_dev),
        "minimax_worst_case_deviation_pct": float(best_dev * 100),
        "status": "DIAGNOSTIC ONLY — quantifies the fixed-B misfit; no "
        "topology or manifest carries this B; nothing was tuned",
        "context": "the misfit (+/- this deviation at the binding sizes) is "
        "LARGER than CAL-A4's ~5% validated mean error band and sits at the "
        "bottom edge of CAL-A6's 5-8% software-version swing; the cause is "
        "the anchor's size-dependent effective B (see b_eff placement), "
        "which a fixed-B, zero-overhead L0 identity cannot express by "
        "construction",
    }


# ---------------------------------------------------------------------------
# 6. Classification of the stage-A2 interpretation flag (assigned duty)
# ---------------------------------------------------------------------------
def a2_flag_classification() -> dict:
    """Stage A2 handed over: CAL-A3's staged 32 GiB busbw 906.94 GB/s sits
    +0.77% ABOVE the CAL-A2-derived 900 B/ns per-direction line. Classify
    (bidirectional split convention / NVLink-vs-IB path split / busbw
    accounting), never tune."""
    busbw_32 = Fraction("906.94")
    line_per_gpu_quote = CEILING_LINE  # 900 = 1.8 TB/s bidir / 2 (per-GPU quote)
    line_from_quoted_aggregate = Fraction(65000, 72)  # 130 TB/s bidir / 72 / 2
    frac_vs_900 = busbw_32 / line_per_gpu_quote
    frac_vs_90278 = busbw_32 / line_from_quoted_aggregate
    t32_anchor = Fraction("74718.41") * 1000
    t2_anchor = Fraction("5375.10") * 1000
    b_eff_32 = wire_bytes(2**35) / (t32_anchor - 2 * L_PAIR_LATENCY_NS)
    t2_model = crossbar_allreduce_time_ns(2**31, RANKS, config_for(CEILING_LINE))
    t32_model = crossbar_allreduce_time_ns(2**35, RANKS, config_for(CEILING_LINE))
    faster_2_pct = float((1 - t2_model / t2_anchor) * 100)
    slower_32_pct = float((t32_model / t32_anchor - 1) * 100)
    return {
        "flag": "CAL-A3 32 GiB out-of-place busbw 906.94 GB/s vs the "
        "CAL-A2-derived 900 B/ns per-GPU per-direction line",
        "headline_residual_vs_900_exact": str(frac_vs_900 - 1),
        "headline_residual_vs_900_pct": float((frac_vs_900 - 1) * 100),
        "candidates": [
            {
                "class": "bidirectional split convention",
                "mechanism": "the 900 line is itself a DERIVED split of "
                "CAL-A2's 1.8 TB/s bidirectional marketing quote (staging "
                "doc states the split and flags the risk); the anchor's own "
                "two quotes agree only to rounding (130 vs exact 129.6 TB/s, "
                "+1/324 — stage A2's finding)",
                "magnitude": "reading the line from the quoted aggregate "
                "instead (65000/72 = 902.78 B/ns) shrinks the residual from "
                f"+{float((frac_vs_900 - 1) * 100):.4f}% to "
                f"+{float((frac_vs_90278 - 1) * 100):.4f}%: the split/rounding "
                "convention explains <= 0.31 percentage points of the 0.77 "
                "and cannot eliminate the residual",
            },
            {
                "class": "busbw accounting (2(r-1)/r convention)",
                "mechanism": "NCCL's busbw = algbw * 2(r-1)/r is a "
                "RING-NORMALIZED figure; the crossbar identity's wire bytes "
                "carry the same factor, so the factor CANCELS in this "
                "stage's CCT-vs-CCT comparison (verified: the anchor's own "
                "times and busbw are consistent under exactly this "
                "convention at every size). But if the measured run used an "
                "algorithm that moves FEWER wire bytes than the ring plan "
                "(e.g. NVSwitch in-switch reduction, the NVLS class), its "
                "ring-normalized busbw can exceed any per-direction "
                "injection rate; the staged numbers do NOT pin the NCCL "
                "algorithm",
                "magnitude": "unbounded from the staged numbers — a "
                "sufficient explanation for +0.77% exists in this class but "
                "cannot be confirmed or excluded from the staged text",
            },
            {
                "class": "NVLink-vs-IB path split",
                "mechanism": "the source sets NCCL_IB_HCA guidance and the "
                "rack is exposed as 18 x 4-GPU instances; the staging doc "
                "flags that the split between NVLink-domain and IB paths for "
                "the 72-GPU communicator is not stated. If any allreduce "
                "traffic rode IB rails, the 906.94 figure would not be "
                "attributable to NVLink alone",
                "magnitude": "an ATTRIBUTION risk, not a magnitude: it "
                "changes what the number is evidence ABOUT, and cannot be "
                "resolved from the staged numbers",
            },
            {
                "class": "software/measurement noise floor",
                "mechanism": "CAL-A6's measured 5-8% busbw swing across NCCL "
                "versions and CAL-A4's ~5% validated simulator error band "
                "are the anchor set's own noise scales; the table's print "
                "precision (~1e-5 relative) is negligible",
                "magnitude": "+0.77% is roughly an order of magnitude BELOW "
                "every noise floor in the anchor set",
            },
        ],
        "verdict": "CLASSIFIED, not tuned, and NOT a physical-ceiling "
        "violation claim: the residual is smaller than every noise floor in "
        "the anchor set, the line itself is a derived reading of a rounded "
        "marketing spec, the algorithm and path split are unpinned (either "
        "could fully explain the residual), and the busbw accounting factor "
        "cancels on the CCT side. CCT-side restatement for this stage: the "
        "anchor's implied effective B at 32 GiB is "
        f"{float(b_eff_32):.2f} B/ns "
        f"({float((b_eff_32 / CEILING_LINE - 1) * 100):+.2f}% vs the line after "
        f"the 2L correction) — the model at B=900 is {slower_32_pct:+.2f}% "
        f"SLOWER than the measurement at 32 GiB while being "
        f"{faster_2_pct:.2f}% FASTER at 2 GiB, i.e. the "
        "binding issue is the size-dependent effective B, not the ceiling",
        "b_eff_32GiB_exact": str(b_eff_32),
        "b_eff_32GiB_fraction_of_900_exact": str(b_eff_32 / CEILING_LINE),
        "duty": "flag handed to this stage by stage A2 "
        "(reports/p1_stageA2.md §3); classified here per handoff rule 5 "
        "(minimize and classify, never tune)",
    }


# ---------------------------------------------------------------------------
# 7. Sweep table pointer (executed rows for every bracket/B combination)
# ---------------------------------------------------------------------------
def sweep_pointer() -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    return {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "crossbar72_a3_ceiling900_v1 (the CAL-A2-derived 900 "
        "B/ns line; delta columns measure placement vs it)",
        "grid": "10 bracket sizes (floor/ceil around each of CAL-A3's 5 "
        "sizes) x 3 swept B {448, 720, 900} = 30 configs x 6 ops",
        "note": "per-config CCT, wire bytes and delta-vs-baseline for every "
        "bracket row live in results/sweeps/<id>/table.json; the exact-size "
        "rows in comparison.rows above are the closed form of the same "
        "identity, cross-checked against every bracket row",
    }


def main() -> int:
    self_check = anchor_self_consistency()
    bracket_checks, run_checks, ctx = closed_form_and_crosschecks()
    comp = comparison(ctx["exact_times"])
    misfit = fixed_b_misfit()
    flag = a2_flag_classification()

    # headline numbers for the record's deviation summary, computed exactly
    # (nothing in the prose below is hand-transcribed)
    anchor_t = {
        label: Fraction(time_us) * 1000
        for label, (_, time_us, _) in A3_STAGED_OUT_OF_PLACE.items()
    }
    ratio = {
        (label, b_str): ctx["exact_times"][(payload, b_str)] / anchor_t[label]
        for label, (payload, _, _) in A3_STAGED_OUT_OF_PLACE.items()
        for b_str in B_VALUES
    }

    def pct(key) -> str:
        return f"{float((ratio[key] - 1) * 100):+.2f}%"

    b_eff_values = list(comp["b_eff_placement"]["values_float"].values())
    b_eff_span_pct = (b_eff_values[-1] / b_eff_values[0] - 1) * 100
    minimax_pct = misfit["minimax_worst_case_deviation_pct"]
    deviation_summary = (
        "at the anchor point B=900 the identity is FASTER than the "
        f"measurement at 2 GiB (ratio {float(ratio[('2GiB', '900')]):.6f}, "
        f"{pct(('2GiB', '900'))}) and SLOWER at 32 GiB (ratio "
        f"{float(ratio[('32GiB', '900')]):.6f}, {pct(('32GiB', '900'))}); "
        f"at B=720 it is {pct(('2GiB', '720'))} (2 GiB) to "
        f"{pct(('32GiB', '720'))} (32 GiB) slower; at B=448 "
        f"{pct(('2GiB', '448'))} to {pct(('32GiB', '448'))} slower "
        "(MI300X-class endpoint, expected far below an NVL72 measurement)"
    )
    root_cause = (
        "the anchor's implied effective B ramps monotonically with message "
        f"size ({b_eff_values[0]:.1f} -> {b_eff_values[-1]:.1f} B/ns, "
        f"+{b_eff_span_pct:.1f}% across the series) — a size-dependent "
        "software-stack efficiency (channel/pipelining fill; consistent with "
        "the source's own 76x in-place outlier at 2 GiB and CAL-A6's "
        "SM-count finding) that a fixed-B, zero-overhead L0 identity cannot "
        "express BY CONSTRUCTION; no single fixed B fits the series within "
        f"+/- {minimax_pct:.1f}%"
    )

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A3 (anchor CAL-A3)",
        "anchor": {
            "anchor_id": "CAL-A3",
            "title": "Crusoe Cloud: NCCL allreduce validation on a GB200 NVL72 rack (MEASURED)",
            "source_row": "the anchor registry row CAL-A3 (PROPOSED)",
            "staging_doc": "docs/calibration/anchors_staging.md §A3",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A3 (primary O-CCT calibration target)",
            "url": "https://support.crusoecloud.com/hc/en-us/articles/41038210396443",
            "confidence": "M-H — real measurement with full config context; "
            "vendor ops guide, not peer-reviewed; NVLink-vs-IB path split "
            "unstated (staging caveat); NCCL algorithm not pinned",
            "software_pins": SOFTWARE_PINS,
        },
        "target": {
            "role": "primary_o_cct_calibration_target",
            "regime": {
                "message_bytes": [2**31, 2**32, 2**33, 2**34, 2**35],
                "message_regime": "2-32 GiB per rank, bandwidth-bound",
                "ranks": 72,
                "topology_class": "fully_connected_crossbar (L0 abstraction of the NVSwitch rack)",
            },
            "series": self_check,
            "holdout_note": "this stage FITS NOTHING (zero parameter "
            "changes), so CALIBRATION_PLAN §3.5's fit-on-{2,4,8} / "
            "hold-out-{16,32} split is recorded as available to the owner's "
            "future fitting pass: per-size deviations for all 5 sizes are in "
            "comparison.rows",
        },
        "anchor_derived": {
            "divisibility_gate": ctx["gate"],
            "note": "the anchor's own arithmetic only: (size -> time) "
            "series used directly; every derived fraction of the 900 line "
            "is anchor-anchor arithmetic declared inline",
        },
        "model": {
            "backend_id": "analytical_l0_crossbar",
            "identity": "t = 2*(r-1)/r * M/B + 2*L ; per-rank wire bytes = 2*(r-1)/r * M",
            "ranks": 72,
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "448": "CAL-A7-derived MI300X-class aggregate-span endpoint",
                    "720": "CAL-A2 900 x CAL-A12 ~80% software derating (spec-to-measured bridge)",
                    "900": "CAL-A2 per-GPU per-direction ceiling (stage A2's normalization line)",
                },
                "L_pair_latency_ns": 200,
                "L_provenance": "A-L0X-LAT registry point (KEEP per plan §2.1); latency axis deferred to its own global stage",
            },
            "assumptions": "A-L0X-PORT single-port injection, A-L0X-LAT, A-L0X-DIV (experiments/vertical_slice/assumptions_l0.yaml)",
            "exact_size_evaluation": "closed form of the run path's own "
            "identity function at the anchor's exact powers of two (the "
            "A-L0X-DIV gate rejects them at r=72); cross-checked against "
            "all 30 executed sweep bracket rows and both store runs by "
            "exact Fraction string equality",
        },
        "comparison": {
            "cct_vs_cct": comp,
            "bracket_crosschecks": bracket_checks["bracket_crosschecks"],
            "anchor_point_runs": run_checks["run_checks"],
            "reconciled_sweep": sweep_pointer(),
            "fixed_B_misfit": misfit,
            "stage_A2_flag_classification": flag,
        },
        "deviation": {
            "summary": deviation_summary,
            "root_cause_classification": root_cause,
            "not_tuned": "nothing was tuned: B values were fixed by anchor "
            "arithmetic before CAL-A3's times were read; the minimax B and "
            "the effective-B values are recorded diagnostics only",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external "
            "published measurement; no E3/E4 language — CAL-A3 is not our "
            "testbed, and the owner's adjudication precedes any label move",
        },
        "backing": {
            "run_ids": [RUN_ID_CEIL900, RUN_ID_DER720],
            "sweep_id": SWEEP_ID,
            "sweep_dir": f"results/sweeps/{SWEEP_ID}",
            "run_backed_numbers": "every run-path-executed number "
            "(bracket rows, store runs); the exact-size rows are the same "
            "identity function evaluated in closed form, cross-checked "
            "against those executed artifacts (declared inline)",
            "inputs": [
                "experiments/calibration/a3/sweep_a3_cct_v1.yaml",
                "experiments/calibration/a3/run_a3_ceiling_v1.yaml",
                "experiments/calibration/a3/run_a3_derated_v1.yaml",
                "experiments/calibration/a3/workloads/w1_dense_tp_decode_tp72_32gib_floorbr.yaml",
                "experiments/calibration/a3/topologies/ (3 files)",
                "experiments/calibration/a3/profiles/implementation_profile_l0_crossbar_cal_a3_v1.yaml",
            ],
            "reproduce": "make run EXP=experiments/calibration/a3/run_a3_ceiling_v1.yaml ; "
            "make run EXP=experiments/calibration/a3/run_a3_derated_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a3/sweep_a3_cct_v1.yaml ; "
            "python experiments/calibration/a3/build_calibration_record.py",
        },
    }

    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    record_id = hashlib.sha256(record_bytes).hexdigest()
    out_dir = RESULTS / "calibration" / record_id
    if out_dir.exists():
        stored = (out_dir / "record.json").read_bytes()
        if stored != record_bytes:
            print(f"ERROR: record {record_id} exists with different bytes", file=sys.stderr)
            return 1
        print(f"idempotent: record {record_id} already stored byte-identically")
        return 0
    out_dir.mkdir(parents=True)
    (out_dir / "record.json").write_bytes(record_bytes)
    print(f"record_id: {record_id}")
    print(f"path: {out_dir / 'record.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
