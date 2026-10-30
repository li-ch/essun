"""Build the PROPOSED calibration FIT record for stage S2 (group G1).

Stage S2 fits the L0 single-port crossbar identity against anchor CAL-A3
per the immutable split record ``3862e227…`` (committed at
``experiments/calibration/split/anchor_split_v1.json``): the fit objective
touches ONLY CAL-A3's within-series fit sizes {2, 4, 8} GiB; the {16, 32}
GiB sizes are held out and reported as held-out error, never fitted.
CAL-A1/A2/A7/A12 enter as declared-scale provenance of the swept values
(normalization ceilings / derating bridge — never measured values), and no
holdout anchor (CAL-A4, GF-01, GF-03, GF-11; GF-06 blocked) is read by any
objective, swept value, or tolerance here. Sole split-record exception,
used only as tolerance-SHAPE context: CAL-A4's ~5% scalar (plan §3.4).

"Fit" under the program fence means: sweep the DECLARED free-parameter
range of A-L0X-BW (registry range [1, 1024] B/ns) against the group's
published numbers, report exact deviations and ranges, and record the
fitted configuration as a DIAGNOSTIC — we report where the model sits; we
never tune a shipped value toward an anchor. Where the model misses badly
(the held-out sizes), the miss IS the finding (a known-omission candidate).

Pure function of immutable artifacts: committed inputs (this directory),
the executed sweep table, and the three store run records this stage
produced — all deterministically reproducible via the documented commands
(identical manifests + code => identical content addresses). Every derived
quantity is recomputed with exact Fractions; every cross-check is an exact
string-equality assert (a mismatch is a bug, not a finding). No wall-clock,
no host metadata: identical inputs reproduce byte-identical records.

Outputs: an append-only store copy under ``results/calibration/<record_id>/
record.json`` and the committed immutability anchor
``experiments/calibration/s2/fit_record_v1.json`` (byte-identical;
regenerating with different bytes is an error — a change requires a NEW
record ``fit_record_v2``).

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim, label, or shipped parameter value changes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical.l0_crossbar import (
    CrossbarConfig,
    crossbar_allreduce_time_ns,
    load_crossbar_config,
)
from essun.contracts import REPO_ROOT, load_yaml
from essun.evidence.dimensions import dimensions_problems
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses; identical manifests + code reproduce
# them, so replay reproduces this record byte-identically).
# ---------------------------------------------------------------------------
SWEEP_ID = "9cf1ed89c1f2e6056e9afa1e9f8642a53df68e5e8c4bebee7365beea0b60ef70"
RUN_ID_FIT_8GIB = "c32d3c646a5f4acedf054eb219675c7711e5ee3f412e1c2ee9ea5f0c215ce32a"
RUN_ID_HOLD_16GIB = "f1f0604853f1ffb712903848624d6afe9b3072a58cb26d741f7297ef9f896140"
RUN_ID_HOLD_32GIB = "7b2136ae9d09d16cdb4324bcb4d3a66b83261b22560938c10532f18e225fe1d1"
SPLIT_RECORD_ID = "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20"

RESULTS = REPO_ROOT / "results"
COMMITTED_COPY = REPO_ROOT / "experiments" / "calibration" / "s2" / "fit_record_v1.json"
S2_DIR = REPO_ROOT / "experiments" / "calibration" / "s2"

# Anchor CAL-A3 staged numbers (docs/calibration/anchors_staging.md §A3,
# transcription confidence M-H; out-of-place series is primary; the in-place
# variant is excluded per CALIBRATION_PLAN.md §4.10 and not used here).
# Units: times in us (exact 2-decimal), busbw in GB/s decimal (1 GB/s = 1
# B/ns); sizes per-rank GiB (binary). Roles per the split record's
# within_series_splits: fit {2,4,8} GiB, held out {16,32} GiB.
RANKS = 72
SOFTWARE_PINS = (
    "NCCL 2.28.3, CUDA 12.9.1, driver 580.82.07; all_reduce_perf float32; "
    "-b 2G -e 32G; 10 warmup / 20 iterations; 72 GPUs of one GB200 NVL72 "
    "rack exposed as 18 x 4-GPU instances; NVLink-vs-IB path split for the "
    "72-GPU communicator NOT stated in the source (staging caveat)"
)
A3_OUT_OF_PLACE = {  # size label -> (payload bytes, time us, busbw GB/s, split role)
    "2GiB": (2**31, "5375.10", "787.95", "fit"),
    "4GiB": (2**32, "10193.01", "831.03", "fit"),
    "8GiB": (2**33, "19555.07", "866.36", "fit"),
    "16GiB": (2**34, "38056.60", "890.32", "held_out"),
    "32GiB": (2**35, "74718.41", "906.94", "held_out"),
}
FIT_LABELS = ("2GiB", "4GiB", "8GiB")
HELD_LABELS = ("16GiB", "32GiB")

# Model free parameters of this stage.
L_PAIR_LATENCY_NS = Fraction(200)  # A-L0X-LAT registry point (KEEP; S4 owns the axis)
TWO_L = 2 * L_PAIR_LATENCY_NS
B_REGISTRY_VALUE = 64
B_REGISTRY_RANGE = (1, 1024)

# 72-divisible floor/ceil brackets around the FIT sizes (the A-L0X-DIV gate
# rejects the exact powers of two at r=72); the executed sweep runs these.
FIT_BRACKETS = {
    "2GiB": (2**31 - 56, 2**31 - 56 + 72),
    "4GiB": (2**32 - 40, 2**32 - 40 + 72),
    "8GiB": (2**33 - 8, 2**33 - 8 + 72),
}
HELD_FLOOR_BRACKETS = {  # run-path payloads of the held-out reporting runs
    "16GiB": 2**34 - 16,
    "32GiB": 2**35 - 32,
}

# Swept topologies of the executed grid (committed files). Provenance:
# 'grid' = the uniform anchor-blind 64 B/ns family over the declared
# A-L0X-BW range; the other three carry group-G1 anchor provenance.
SWEEP_TOPOLOGIES = [  # (repo path, provenance class)
    ("experiments/calibration/s2/topologies/crossbar72_s2_b64_v1.yaml", "grid: 64=64x1"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b128_v1.yaml", "grid: 128=64x2"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b192_v1.yaml", "grid: 192=64x3"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b256_v1.yaml", "grid: 256=64x4"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b320_v1.yaml", "grid: 320=64x5"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b384_v1.yaml", "grid: 384=64x6"),
    ("experiments/calibration/a3/topologies/crossbar72_a3_span448_v1.yaml",
     "anchor: 448 = CAL-A7-derived MI300X-class endpoint (7 x 64 B/ns per direction)"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b512_v1.yaml", "grid: 512=64x8"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b576_v1.yaml", "grid: 576=64x9"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b640_v1.yaml", "grid: 640=64x10"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b704_v1.yaml", "grid: 704=64x11"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b768_v1.yaml", "grid: 768=64x12"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b832_v1.yaml", "grid: 832=64x13"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b896_v1.yaml", "grid: 896=64x14"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b960_v1.yaml", "grid: 960=64x15"),
    ("experiments/calibration/s2/topologies/crossbar72_s2_b1024_v1.yaml", "grid: 1024=64x16 (declared-range upper endpoint)"),
    ("experiments/calibration/a3/topologies/crossbar72_a3_derated720_v1.yaml",
     "anchor: 720 = CAL-A2 900 x CAL-A12 ~80% spec-to-measured bridge (derating)"),
    ("experiments/calibration/a3/topologies/crossbar72_a3_ceiling900_v1.yaml",
     "anchor: 900 = CAL-A2 per-GPU per-direction ceiling (normalization line)"),
]
FIT_TOPOLOGY = "experiments/calibration/s2/topologies/crossbar72_s2_fitb_v1.yaml"
B_FIT_TOPOLOGY_STRING = "19561820264071168/23648730912675"  # exact, asserted below

BUSBW_FACTOR = Fraction(2 * (RANKS - 1), RANKS)  # 71/36 — cancels CCT-vs-CCT
CEILING_LINE = Fraction(900)  # CAL-A2 per-GPU per-direction line (stage A2)


def wire_bytes(payload: int) -> Fraction:
    """Per-rank wire bytes of the crossbar AllReduce identity: 2(r-1)/r * M."""
    return Fraction(2 * (RANKS - 1) * payload, RANKS)


def config_for(b: Fraction) -> CrossbarConfig:
    return CrossbarConfig(
        topology_id="cal_s2_closed_form",
        ranks=RANKS,
        injection_bytes_per_ns=b,
        pair_latency_ns=L_PAIR_LATENCY_NS,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_times() -> dict[str, Fraction]:
    return {
        label: Fraction(t_us) * 1000
        for label, (_, t_us, _, _) in A3_OUT_OF_PLACE.items()
    }


# ---------------------------------------------------------------------------
# 1. Target extraction (plan §3 algebraic mapping) — all 5 rows declared,
#    fit/held roles per the split record; only FIT rows are ever compared
#    in the fit sections.
# ---------------------------------------------------------------------------
def anchor_self_consistency() -> dict:
    rows = []
    for label, (payload, time_us, busbw_gbps, role) in A3_OUT_OF_PLACE.items():
        t_ns = Fraction(time_us) * 1000
        algbw = Fraction(payload) / t_ns
        implied_busbw = algbw * BUSBW_FACTOR
        residual = implied_busbw - Fraction(busbw_gbps)
        assert abs(residual) < Fraction("0.05"), (label, residual)
        rows.append(
            {
                "size": label,
                "split_role": role,
                "payload_bytes": payload,
                "staged_time_us": time_us,
                "staged_time_ns_exact": str(t_ns),
                "staged_busbw_GB_per_s": busbw_gbps,
                "algbw_GB_per_s_exact": str(algbw),
                "implied_busbw_GB_per_s_exact": str(implied_busbw),
                "residual_implied_minus_quoted_exact": str(residual),
                "mapping": "algbw = M/t ; busbw = algbw * 2(r-1)/r (r=72 => "
                           "factor 71/36); CCT target = the quoted time "
                           "(CCT-vs-CCT, the factor cancels)",
            }
        )
    return {
        "primary_series": "out-of-place allreduce, 5 sizes, per-rank GiB "
                          "payloads (in-place variant excluded per plan §4.10)",
        "software_pins": SOFTWARE_PINS,
        "rows": rows,
        "consistency_verdict": "all 5 out-of-place rows internally consistent "
            "under the standard NCCL accounting within <= 0.03 GB/s (print "
            "precision); only the {2,4,8} GiB rows enter the fit objective "
            "(split record within_series_splits)",
    }


# ---------------------------------------------------------------------------
# 2. Executed sweep reconciliation + closed-form cross-checks (fit sizes only)
# ---------------------------------------------------------------------------
def sweep_reconciliation() -> tuple[dict, dict]:
    """Cross-check every executed sweep row against the closed form of the
    same identity at the same bracket payload and swept B; verify the grid
    carries ONLY fit-size brackets (the held-out brackets must be absent)."""
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    b_by_path = {}
    for path, _ in SWEEP_TOPOLOGIES:
        b_by_path[path] = load_crossbar_config(load_yaml(REPO_ROOT / path)).injection_bytes_per_ns
    assert len(b_by_path) == 18

    fit_bracket_set = {b for pair in FIT_BRACKETS.values() for b in pair}
    rows = {(r["topology"]["path"], r["payload_bytes"]): r for r in table["configs"]}
    assert len(rows) == 18 * 6, len(rows)
    for (path, payload), row in rows.items():
        assert payload in fit_bracket_set, (path, payload, "held-out bracket leaked into the fit sweep")
        b = b_by_path[path]
        closed = crossbar_allreduce_time_ns(payload, RANKS, config_for(b))
        assert row["o_cct"]["completion_time_ns_mean_exact"] == str(closed), (path, payload)

    per_b = []
    for path, provenance in SWEEP_TOPOLOGIES:
        rel = path
        b = b_by_path[rel]
        entry = {
            "topology": path.split("/")[-1],
            "provenance": provenance,
            "B_bytes_per_ns": str(b),
            "B_float": float(b),
            "grid_member": provenance.startswith("grid"),
        }
        worst = Fraction(0)
        for label in FIT_LABELS:
            payload = A3_OUT_OF_PLACE[label][0]
            t_anchor = anchor_times()[label]
            ratio = crossbar_allreduce_time_ns(payload, RANKS, config_for(b)) / t_anchor
            entry[f"delta_pct_{label}"] = float((ratio - 1) * 100)
            if abs(ratio - 1) > worst:
                worst = abs(ratio - 1)
        entry["max_abs_delta_pct_at_fit_sizes"] = float(worst * 100)
        per_b.append(entry)
    summary = {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "crossbar72_a3_ceiling900_v1 (the CAL-A2-derived 900 B/ns "
                    "line; the sweep table's delta columns measure vs it)",
        "grid": "18 topologies (uniform anchor-blind 64 B/ns grid 64..1024 "
                "plus the three group-G1 anchor-provenance points 448/720/"
                "900 on the committed stage-A3 files) x 6 fit-size floor/ceil "
                "brackets = 108 configs x 6 ops",
        "payload_fence": "every executed payload is a {2,4,8} GiB bracket "
                         "(asserted; the {16,32} GiB held-out brackets are "
                         "absent from the fit sweep by construction)",
        "cross_check": "all 108 executed rows equal the closed form of the "
                       "same identity function at the same bracket payload "
                       "and swept B (exact Fraction string equality)",
        "per_B_deltas_at_exact_fit_sizes": per_b,
    }
    return summary, b_by_path


# ---------------------------------------------------------------------------
# 3. The fit: exact minimax fixed-B over the three fit points + windows
# ---------------------------------------------------------------------------
def fit_math() -> dict:
    data = [
        (label, wire_bytes(A3_OUT_OF_PLACE[label][0]), anchor_times()[label])
        for label in FIT_LABELS
    ]

    def ratio(b: Fraction, label: str) -> Fraction:
        payload = A3_OUT_OF_PLACE[label][0]
        return crossbar_allreduce_time_ns(payload, RANKS, config_for(b)) / anchor_times()[label]

    # minimax over B of max_i |t_model(B, M_i)/t_anchor_i - 1|: deviations
    # are monotone in B, so the optimum equalizes some pair; evaluate every
    # pair's candidate exactly and take the argmin (worst dev, then B).
    candidates = []
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            denom = 2 - TWO_L / data[i][2] - TWO_L / data[j][2]
            if denom <= 0:
                continue
            b_star = (data[i][1] / data[i][2] + data[j][1] / data[j][2]) / denom
            if b_star > 0:
                worst = max(abs(ratio(b_star, row[0]) - 1) for row in data)
                candidates.append((worst, b_star, (data[i][0], data[j][0])))
    assert candidates
    best_dev, best_b, best_pair = min(candidates, key=lambda c: (c[0], c[1]))
    devs = {label: abs(ratio(best_b, label) - 1) for label in FIT_LABELS}
    binding = {label for label, d in devs.items() if d == max(devs.values())}
    assert binding == set(best_pair), (best_pair, binding)
    assert best_b == Fraction(B_FIT_TOPOLOGY_STRING), (
        "the fitb topology file must carry the exact minimax B: "
        f"{best_b.numerator}/{best_b.denominator}"
    )
    assert Fraction(1) < best_b < Fraction(1024)  # inside the declared free range

    per_size_at_fit = []
    for label in FIT_LABELS:
        payload = A3_OUT_OF_PLACE[label][0]
        r = ratio(best_b, label)
        per_size_at_fit.append(
            {
                "size": label,
                "payload_bytes": payload,
                "anchor_cct_ns_exact": str(anchor_times()[label]),
                "model_cct_ns_exact": str(crossbar_allreduce_time_ns(payload, RANKS, config_for(best_b))),
                "ratio_model_over_anchor_exact": str(r),
                "delta_pct_float": float((r - 1) * 100),
                "anchor_implied_effective_B_exact": str(
                    wire_bytes(payload) / (anchor_times()[label] - TWO_L)
                ),
                "anchor_implied_effective_B_float": float(
                    wire_bytes(payload) / (anchor_times()[label] - TWO_L)
                ),
            }
        )

    # tolerance-SHAPE windows over B (exact algebra; diagnostics only — the
    # E0 zero-slack policy stands; no tolerance is adopted by this record)
    def window(tau: Fraction) -> dict:
        lo = max(w / ((1 + tau) * t - TWO_L) for _, w, t in data)
        hi = min(w / ((1 - tau) * t - TWO_L) for _, w, t in data)
        assert 0 < lo < hi
        return {
            "B_low_exact": str(lo),
            "B_low_float": float(lo),
            "B_high_exact": str(hi),
            "B_high_float": float(hi),
            "width_exact": str(hi - lo),
            "width_float": float(hi - lo),
        }

    grid_bs = [
        load_crossbar_config(load_yaml(REPO_ROOT / path)).injection_bytes_per_ns
        for path, prov in SWEEP_TOPOLOGIES
        if prov.startswith("grid")
    ]
    win5 = window(Fraction(5, 100))
    win8 = window(Fraction(8, 100))
    in5 = [str(b) for b in grid_bs if Fraction(win5["B_low_exact"]) <= b <= Fraction(win5["B_high_exact"])]
    in8 = [str(b) for b in grid_bs if Fraction(win8["B_low_exact"]) <= b <= Fraction(win8["B_high_exact"])]

    # L-sensitivity (the latency axis is S4's; here it is bounded)
    b_star_l0 = (data[0][1] / data[0][2] + data[-1][1] / data[-1][2]) / 2
    two_l_over_t = {label: TWO_L / t for label, _, t in data}

    return {
        "objective": "minimax over the free parameter B of the worst-case "
                     "CCT deviation at the three split-record fit sizes "
                     "{2, 4, 8} GiB (exact Fractions; L at the A-L0X-LAT "
                     "registry point 200 ns)",
        "identity": "t = 2*(r-1)/r * M/B + 2*L ; per-rank wire bytes = "
                    "2*(r-1)/r * M (r=72)",
        "minimax_B_exact": str(best_b),
        "minimax_B_float": float(best_b),
        "minimax_B_materialized_as": B_FIT_TOPOLOGY_STRING + " (the exact "
            "rational carried by " + FIT_TOPOLOGY + " — asserted equal)",
        "binding_sizes": list(best_pair),
        "worst_case_relative_deviation_exact": str(best_dev),
        "worst_case_deviation_pct": float(best_dev * 100),
        "per_size_at_fitted_B": per_size_at_fit,
        "effective_B_ramp_at_fit_sizes": {
            "definition": "anchor-implied effective B = [2(r-1)/r * M] / "
                          "(t_anchor - 2L) per fit size — RECORDED "
                          "DIAGNOSTIC placement, never a topology value",
            "values_float": {
                label: float(wire_bytes(A3_OUT_OF_PLACE[label][0])
                             / (anchor_times()[label] - TWO_L))
                for label in FIT_LABELS
            },
            "span_last_over_first_float": float(
                (wire_bytes(A3_OUT_OF_PLACE["8GiB"][0]) / (anchor_times()["8GiB"] - TWO_L))
                / (wire_bytes(A3_OUT_OF_PLACE["2GiB"][0]) / (anchor_times()["2GiB"] - TWO_L))
            ),
        },
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance is adopted (the E0 "
                      "zero-slack policy stands; a nonzero tolerance must "
                      "arrive through CGFR with recorded evidence, plan §3.4)",
            "tau_5pct": {
                **win5,
                "shape_provenance": "CAL-A4's ~5% validated mean-error "
                    "SCALAR admitted solely as tolerance-shape context per "
                    "the split record's sole recorded exception (plan §3.4; "
                    "the anchor's series and per-configuration errors are "
                    "NOT fit inputs)",
                "uniform_grid_members_inside": in5,
            },
            "tau_8pct": {
                **win8,
                "shape_provenance": "upper edge of CAL-A6's measured 5-8% "
                    "software-version swing (calibration-set noise-floor "
                    "anchor, plan §3.4); a criterion tighter than the "
                    "measured software variance would be overfitting",
                "uniform_grid_members_inside": in8,
            },
            "note": "the 5% window contains NO member of the uniform 64 "
                    "B/ns grid (reported, not resolved by adding grid "
                    "points: the exact window boundaries are the finding, "
                    "the grid is the anchor-blind sampling instrument)",
        },
        "L_sensitivity": {
            "two_L_over_anchor_t_exact": {k: str(v) for k, v in two_l_over_t.items()},
            "two_L_over_anchor_t_float": {k: float(v) for k, v in two_l_over_t.items()},
            "minimax_B_at_L_zero_exact": str(b_star_l0),
            "minimax_B_shift_pct_when_L_0_to_200_float": float((best_b / b_star_l0 - 1) * 100),
            "note": "the fit is bandwidth-bound and L-insensitive at these "
                    "sizes (2L/t <= 7.5e-5); the latency axis belongs to "
                    "stage S4 — no L degree of freedom is fitted here",
        },
    }


# ---------------------------------------------------------------------------
# 4. Provenance-point placement (group G1 declared-scale anchors)
# ---------------------------------------------------------------------------
def provenance_placement(b_by_path: dict) -> dict:
    t = anchor_times()
    rows = []
    placements = {
        "448": "CAL-A7-derived MI300X-class endpoint (spec ceiling of a "
               "different fabric class; included for span completeness)",
        "720": "CAL-A2 900 x CAL-A12 ~80% spec-to-measured derating bridge "
               "(NCCL internal NVLink model; NVLink-3-era A100 provenance, "
               "M confidence)",
        "900": "CAL-A2 per-GPU per-direction ceiling line (spec, never an "
               "achieved value; the group's normalization line)",
    }
    for b_str, label in (("448", "crossbar72_a3_span448_v1"),
                         ("720", "crossbar72_a3_derated720_v1"),
                         ("900", "crossbar72_a3_ceiling900_v1")):
        path = next(p for p in SWEEP_TOPOLOGIES if p[0].endswith(label + ".yaml"))[0]
        b = b_by_path[path]
        row = {"B": b_str, "placement": placements[b_str]}
        for size in FIT_LABELS:
            r = crossbar_allreduce_time_ns(A3_OUT_OF_PLACE[size][0], RANKS, config_for(b)) / t[size]
            row[f"delta_pct_{size}"] = float((r - 1) * 100)
        rows.append(row)
    b_fit = Fraction(B_FIT_TOPOLOGY_STRING)
    return {
        "rows": rows,
        "verdict": "NO group-G1 provenance point falls inside the 5% "
                   "tolerance-shape window at the fit sizes: the MI300X-"
                   "class endpoint (448) misses by +75.9..+93.4% (expected: "
                   "different fabric class), the CAL-A12-derated bridge "
                   "(720) by +9.4..+20.3% (the NVLink-3-era ~80% derating "
                   "under-states this GB200-era series), and the CAL-A2 "
                   "ceiling line (900) by -12.4..-3.7% (the model at the "
                   "spec ceiling is FASTER than the measurement at every "
                   "fit size — the ceiling is never achieved)",
        "fitted_B_placement": {
            "fraction_of_900_line_exact": str(b_fit / CEILING_LINE),
            "fraction_of_900_line_float": float(b_fit / CEILING_LINE),
            "over_720_bridge_ratio_exact": str(b_fit / Fraction(720)),
            "over_720_bridge_ratio_float": float(b_fit / Fraction(720)),
            "note": "the fitted B sits at ~91.9% of the CAL-A2 line — above "
                    "the CAL-A12 ~80% bridge; the spec-to-measured derating "
                    "is generation/stack-dependent (recorded placement, "
                    "never a shipped value)",
        },
    }


# ---------------------------------------------------------------------------
# 5. Held-out evaluation ({16,32} GiB at the fitted configuration)
# ---------------------------------------------------------------------------
def held_out_evaluation() -> dict:
    b_fit = Fraction(B_FIT_TOPOLOGY_STRING)
    t = anchor_times()
    run_map = {
        "16GiB": (RUN_ID_HOLD_16GIB, HELD_FLOOR_BRACKETS["16GiB"]),
        "32GiB": (RUN_ID_HOLD_32GIB, HELD_FLOOR_BRACKETS["32GiB"]),
    }
    rows = []
    for label in HELD_LABELS:
        payload = A3_OUT_OF_PLACE[label][0]
        run_id, bracket = run_map[label]
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        per_op = obs["per_op"][0]
        # run-record cross-checks: right payload, right B, held_out declared
        assert per_op["payload_bytes"] == bracket, (label, per_op["payload_bytes"])
        assert Fraction(obs["model"]["injection_bytes_per_ns_exact"]) == b_fit
        assert run["held_out"]["held_out"] is True
        assert run["calibration_target"] == ["CAL-A3"]
        assert run["evidence_schema_version"] == 2
        closed_bracket = crossbar_allreduce_time_ns(bracket, RANKS, config_for(b_fit))
        assert per_op["completion_time_ns_exact"] == str(closed_bracket), label
        t_exact = crossbar_allreduce_time_ns(payload, RANKS, config_for(b_fit))
        r_exact = t_exact / t[label]
        rows.append(
            {
                "size": label,
                "payload_bytes": payload,
                "anchor_cct_ns_exact": str(t[label]),
                "model_cct_at_fitted_B_exact": str(t_exact),
                "ratio_model_over_anchor_exact": str(r_exact),
                "delta_pct_float": float((r_exact - 1) * 100),
                "anchor_implied_effective_B_exact": str(
                    wire_bytes(payload) / (t[label] - TWO_L)
                ),
                "anchor_implied_effective_B_float": float(
                    wire_bytes(payload) / (t[label] - TWO_L)
                ),
                "run_backing": {
                    "run_id": run_id,
                    "payload_bytes": bracket,
                    "held_out_dimension": run["held_out"],
                    "cct_ns_exact": per_op["completion_time_ns_exact"],
                    "note": "run executes the 72-divisible FLOOR bracket; "
                            "the exact-size row above is the same identity "
                            "in closed form (asserted equal at the bracket)",
                },
            }
        )
    fit_run = load_json(RESULTS / RUN_ID_FIT_8GIB / "run.json")
    assert fit_run["held_out"]["held_out"] is False
    assert fit_run["calibration_target"] == ["CAL-A3"]
    assert fit_run["evidence_schema_version"] == 2
    devs = [row["delta_pct_float"] for row in rows]
    return {
        "sizes": list(HELD_LABELS),
        "at": "the fitted configuration B_fit = " + B_FIT_TOPOLOGY_STRING,
        "rows": rows,
        "finding": "held-out deviations at the fitted B grow monotonically "
                   f"with size ({devs[0]:+.2f}% at 16 GiB, {devs[1]:+.2f}% "
                   "at 32 GiB) and exceed the 5% tolerance-shape band: the "
                   "anchor's implied effective B keeps ramping above the "
                   "fitted window out-of-fit (890.3 / 906.9 B/ns at the "
                   "held-out sizes vs 788.0..866.4 across the fit sizes) — "
                   "the fixed-B, zero-overhead L0 identity cannot express "
                   "a size-dependent software-effective bandwidth BY "
                   "CONSTRUCTION. THE MISS IS THE FINDING (known-omission "
                   "candidate); nothing was tuned toward these sizes — "
                   "B_fit was fixed by the {2,4,8} GiB points alone before "
                   "the held-out rows were evaluated",
        "historical_context": "the E1 untuned sweep's five-point fixed-B "
                   "minimax misfit was +/-7.02% (docs/calibration/"
                   "ADJUDICATION.md headline read, 2026-10-29); the S2 "
                   "three-point fit sits at +/-4.73% in-fit while the "
                   "held-out rows land at +7.6%/+9.6% — the clean "
                   "fit/holdout separation isolates the size-dependent "
                   "ramp as the dominant residual",
    }


# ---------------------------------------------------------------------------
# 6. v2 evidence dimensions (the five D3 fields, mirrored on this record)
# ---------------------------------------------------------------------------
def evidence_dimensions_block() -> dict:
    block = {
        "verification": [
            {
                "check": "tests/calibration/test_s2_fit.py",
                "scope": "S2 fit guard — re-executes the fit sweep and the "
                         "three S2 runs into a scratch store, rebuilds this "
                         "record byte-identically, and checks the "
                         "fit/holdout size-separation invariants",
            },
            {
                "check": "tests/calibration/test_anchor_split.py",
                "scope": "the split record's own immutability guard (S1) — "
                         "the data separation this fit runs under",
            },
        ],
        "calibration_target": ["CAL-A3"],
        "held_out": {
            "held_out": False,
            "scope": "the S2 fit objective and every swept value here touch "
                     "only CAL-A3's split-record fit sizes {2,4,8} GiB; "
                     "CAL-A1/A2/A7/A12 enter as declared-scale provenance of "
                     "the swept values (ceilings/derating bridge, never "
                     "measured values); the {16,32} GiB rows appear ONLY in "
                     "held_out_evaluation (their run records declare "
                     "held_out: true)",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "single fixed-B, zero-overhead L0 crossbar identity — cannot "
            "express the size-dependent software-effective bandwidth ramp "
            "the anchor series exhibits (the S2 known-omission candidate, "
            "confirmed out-of-fit by the held-out rows)",
            "A-L0X-LAT fixed at the registry point 200 ns; the latency axis "
            "is stage S4's (the S2 fit is L-insensitive: 2L/t <= 7.5e-5)",
            "no congestion, no credit flow control, no packetization, no "
            "multi-port injection, no in-network reduction (analytical L0 "
            "transport model only)",
            "the anchor's NCCL algorithm and NVLink-vs-IB path split are "
            "unstated in the source (staging caveat — an attribution risk "
            "recorded with the anchor, not resolvable here)",
        ],
    }
    problems = dimensions_problems(block)
    assert not problems, problems
    return block


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------
def build_record() -> dict:
    sweep, b_by_path = sweep_reconciliation()
    fit = fit_math()
    prov = provenance_placement(b_by_path)
    held = held_out_evaluation()

    fitted = fit["minimax_B_float"]
    worst = fit["worst_case_deviation_pct"]
    w5 = fit["tolerance_shape_windows"]["tau_5pct"]
    record = {
        "record_kind": "calibration_fit",
        "evidence_schema_version": 2,
        "status": "PROPOSED — owner adjudication required; no claim, label, "
                  "or shipped parameter value changes; the fitted B is a "
                  "recorded diagnostic, never a shipped value",
        "stage": "calibration fit record, S2 (group G1)",
        "split_record": {
            "record_id": SPLIT_RECORD_ID,
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "within_series_rule": "CAL-A3 fit {2,4,8} GiB / hold out {16,32} "
                                  "GiB; held-out sizes never enter a fit "
                                  "objective and are reported as held-out error",
            "group": "G1 — large-message bandwidth-bound switched scale-up "
                     "+ spec ceilings + spec-to-measured derating bridge "
                     "(fitting stage S2)",
            "no_leakage": "none of the split record's four cross-anchor "
                          "holdouts or its blocked anchor is read by any "
                          "objective, swept value, or tolerance in this "
                          "record (mechanically asserted: their ids appear "
                          "nowhere in the record bytes); sole recorded "
                          "exception used: the ~5% mean-error scalar as "
                          "tolerance-SHAPE context only (see "
                          "fit.tolerance_shape_windows.tau_5pct)"
                          " — the ids stay unlisted here by design",
        },
        "group_g1_anchors": {
            "fit_target": "CAL-A3 (Crusoe Cloud GB200 NVL72 NCCL 2.28.3 "
                          "allreduce, 2-32 GiB, r=72, out-of-place; "
                          "staging §A3; confidence M-H)",
            "declared_scale_provenance_only": [
                "CAL-A1 — NVLink5 switch chip spec: 57.6 Tbps full-duplex, "
                "72 ports => 50 B/ns per port per direction (radix/fan-in "
                "context for the NVSwitch class; ceiling, never achieved)",
                "CAL-A2 — GB200 NVL72 per-GPU 1.8 TB/s bidirectional => "
                "900 B/ns per-direction line (the normalization line and "
                "sweep baseline topology)",
                "CAL-A7 — MI300X Infinity Fabric 7 x 128 GB/s bidirectional "
                "=> 448 B/ns per-direction aggregate (the anchored-span "
                "lower endpoint; a different fabric class — included for "
                "span completeness, flagged by A-L0X-PORT as full-mesh "
                "OUT-OF-DOMAIN there)",
                "CAL-A12 — NCCL internal NVLink model ~80% of peak (the "
                "720 B/ns spec-to-measured derating bridge; NVLink-3-era, "
                "M confidence)",
            ],
        },
        "anchor": {
            "anchor_id": "CAL-A3",
            "staging_doc": "docs/calibration/anchors_staging.md §A3",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row "
                        "CAL-A3 (primary O-CCT calibration target)",
            "url": "https://support.crusoecloud.com/hc/en-us/articles/41038210396443",
            "series": anchor_self_consistency(),
        },
        "model": {
            "backend_id": "analytical_l0_crossbar",
            "identity": "t = 2*(r-1)/r * M/B + 2*L ; per-rank wire bytes = "
                        "2*(r-1)/r * M",
            "ranks": RANKS,
            "assumptions": "A-L0X-PORT single-port injection (KEEP for "
                           "NVSwitch-class), A-L0X-LAT (KEEP, registry point "
                           "200 ns), A-L0X-DIV (structural; rejects the "
                           "anchor's exact powers of two at r=72 — the "
                           "executed rows sit at the 72-divisible floor/ceil "
                           "brackets, relative offset <= 2.7e-8, and the "
                           "exact-size rows are the same identity in closed "
                           "form, cross-checked)",
            "declared_free_parameter": {
                "id": "A-L0X-BW",
                "parameter": "nic.injection_bytes_per_ns",
                "registry_value": B_REGISTRY_VALUE,
                "registry_range": list(B_REGISTRY_RANGE),
                "registry": "experiments/vertical_slice/assumptions_l0.yaml "
                            "(plan §2.1 verdict NARROW-scale: anchored span "
                            "448..900 B/ns; the registry VALUE stays 64 — "
                            "unchanged by this stage)",
            },
        },
        "executed_sweep": sweep,
        "fit": fit,
        "provenance_point_placement": prov,
        "held_out_evaluation": held,
        "headline": (
            f"the fixed-B L0 crossbar identity fits CAL-A3's split-record "
            f"fit sizes {{2,4,8}} GiB to a worst case of +/-{worst:.2f}% at "
            f"B_fit = {fitted:.4f} B/ns (exact minimax; binding sizes 2 GiB "
            f"and 8 GiB); the 5% tolerance-shape window is "
            f"[{w5['B_low_float']:.2f}, {w5['B_high_float']:.2f}] B/ns "
            f"(width {w5['width_float']:.2f}); NO group-G1 provenance point "
            f"(448 / 720 / 900) lies inside it; the held-out sizes "
            f"{{16,32}} GiB miss by +7.63% / +9.64% at B_fit and the miss "
            f"grows with size — the known-omission finding (size-dependent "
            f"software-effective bandwidth), reported, never tuned"
        ),
        "not_tuned": "the sweep grid was fixed by registry-range arithmetic "
                     "and group-G1 anchor provenance before any CAL-A3 "
                     "deviation was computed; the minimax B is an exact "
                     "closed-form diagnostic over the fit points only; the "
                     "held-out rows were evaluated AFTER B_fit was fixed "
                     "and changed nothing; the registry A-L0X-BW value "
                     "stays 64 and no manifest outside this calibration "
                     "directory carries the fitted value",
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, "
                    "content-addressed, replay reproduces byte-identical "
                    "artifacts)",
            "fit": "PROPOSED calibration fit candidate against an external "
                   "published measurement; no E3/E4 language — CAL-A3 is "
                   "not our testbed, and owner adjudication precedes any "
                   "label move",
        },
        "backing": {
            "sweep_id": SWEEP_ID,
            "sweep_dir": f"results/sweeps/{SWEEP_ID}",
            "run_ids": [RUN_ID_FIT_8GIB, RUN_ID_HOLD_16GIB, RUN_ID_HOLD_32GIB],
            "run_roles": {
                RUN_ID_FIT_8GIB: "fit-side run at the 8 GiB floor bracket, "
                                 "B_fit (held_out: false)",
                RUN_ID_HOLD_16GIB: "held-out reporting run at the 16 GiB "
                                   "floor bracket, B_fit (held_out: true)",
                RUN_ID_HOLD_32GIB: "held-out reporting run at the 32 GiB "
                                   "floor bracket, B_fit (held_out: true)",
            },
            "inputs": [
                "experiments/calibration/s2/sweep_s2_bw_v1.yaml",
                "experiments/calibration/s2/topologies/ (16 files)",
                "experiments/calibration/s2/workloads/ (2 files)",
                "experiments/calibration/a3/workloads/"
                "w1_dense_tp_decode_tp72_32gib_floorbr.yaml",
                "experiments/calibration/s2/run_s2_fit_8gib_floorbr.yaml",
                "experiments/calibration/s2/run_s2_holdout_16gib_floorbr.yaml",
                "experiments/calibration/s2/run_s2_holdout_32gib_floorbr.yaml",
                "experiments/calibration/s2/profiles/"
                "implementation_profile_l0_crossbar_cal_s2_v1.yaml",
                "experiments/calibration/a3/topologies/ (3 files, reused "
                "anchor-provenance points)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/s2/"
                         "sweep_s2_bw_v1.yaml ; make run "
                         "EXP=experiments/calibration/s2/"
                         "run_s2_fit_8gib_floorbr.yaml ; make run "
                         "EXP=experiments/calibration/s2/"
                         "run_s2_holdout_16gib_floorbr.yaml ; make run "
                         "EXP=experiments/calibration/s2/"
                         "run_s2_holdout_32gib_floorbr.yaml ; python "
                         "experiments/calibration/s2/build_fit_record.py",
        },
    }
    record.update(evidence_dimensions_block())

    # fence self-checks over the assembled record bytes
    text = canonical_json(record)
    for forbidden in ("GF-01", "GF-03", "GF-11", "GF-06"):
        assert forbidden not in text, forbidden
    assert text.count("CAL-A4") == 1, text.count("CAL-A4")  # tolerance-shape context only
    return record


def main() -> int:
    record = build_record()
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    record_id = hashlib.sha256(record_bytes).hexdigest()

    # append-only store copy (house convention; results/ is untracked)
    store_dir = RESULTS / "calibration" / record_id
    store_path = store_dir / "record.json"
    if store_path.exists():
        if store_path.read_bytes() != record_bytes:
            print(f"ERROR: store record {record_id} exists with different bytes",
                  file=sys.stderr)
            return 1
        print(f"idempotent: store record {record_id} already byte-identical")
    else:
        store_dir.mkdir(parents=True)
        store_path.write_bytes(record_bytes)
        print(f"stored: results/calibration/{record_id}/record.json")

    # committed copy — the immutability anchor of this fit record
    if COMMITTED_COPY.exists():
        if COMMITTED_COPY.read_bytes() != record_bytes:
            print(
                f"ERROR: committed copy {COMMITTED_COPY} differs from the "
                "rebuilt record — this fit record is immutable; record a "
                "NEW record (fit_record_v2) instead of editing",
                file=sys.stderr,
            )
            return 1
        print(f"immutable: committed copy matches record {record_id}")
    else:
        COMMITTED_COPY.write_bytes(record_bytes)
        print(f"wrote committed copy: {COMMITTED_COPY}")

    print(f"record_id: {record_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
