"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-01
(calibration stage GF-01;
p1_calibration.md; anchor staged in docs/calibration/anchors_gapfill.md §GF-01).

GF-01 = AMD ROCm blog "Understanding RCCL Bandwidth and xGMI Performance on
AMD Instinct MI300X" (RCCL 2.22.3-develop:f5b15f2 / ROCm 6.3.0.0,
all_reduce_perf + TransferBench on all 8 GPUs of one MI300X node, 7-hop
full-mesh xGMI): the first MEASURED staged anchor whose series covers the
small-message O-CCT regime (<= 64 KiB, plan gap §4.3 — exactly the smoke-
manifest regime), a large-message plateau row on a non-NVIDIA scale-up
fabric, and measured link-rate derating for the xGMI class (the CAL-A12
pairing the gap-fill doc assigns it). GF anchors are NOT sources.csv rows:
the owner integrates accepted rows (suggested continuation id CAL-A13);
this record cites the gap-fill staging doc only.

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity with exact Fractions, and writes a content-addressed
record to ``results/calibration/<record_id>/record.json`` (record_id =
SHA-256 of the canonical record; append-only — existing different bytes are
an error, identical bytes are idempotent).

Every number below is (a) transcribed from the anchor's staged numbers in
docs/calibration/anchors_gapfill.md §GF-01 (declared with provenance; the
staging doc flags the blog's percentage sentence and the graph-table mid
rows for re-verification at integration — those flags are carried, not
resolved), or (b) computed from stored run/sweep artifacts, or (c) exact
closed-form identity arithmetic cross-checked against executed artifacts by
exact Fraction string equality (declared inline), or (d) anchor-anchor
arithmetic on staged numbers (implied-effective-L / derating ratios —
declared "no run id by construction"). Nothing is tuned: the swept B values
carry their anchor provenance, fixed before any model output was read.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_RING_SMALL = "6cb42e5fed02eefe1d6ad6704d08af1485b146e3bbd38c87ce069108f32648ce"
RUN_ID_XBAR_LARGE = "6f921c396e5f82ff506c8758b176c0e8878f2e2c188e60768fff94b26b66db2b"
SWEEP_ID_SMALL = "58084faecff6d294b064d86bf6411211024fcee9d3d095b023fb6619a2315f5b"
SWEEP_ID_LARGE = "a0f647ff81fc6f33bcf7f9aaf9ee2a61639efb8b3810f8d07f1b28cb014294e8"

RESULTS = REPO_ROOT / "results"

# GF-01 staged numbers (docs/calibration/anchors_gapfill.md §GF-01;
# confidence M-H — vendor blog, not peer-reviewed; decimal units,
# 1 GB/s = 1 B/ns). Eager series: (label, payload B, time in us as staged,
# busbw in GB/s as staged or None when the source prints time only).
EAGER_ROWS = [
    ("8 B", 8, "16.61", None),
    ("32 B", 32, "16.74", None),
    ("64 B", 64, "16.61", None),
    ("16 KiB", 16384, "13.54", "2.12"),
    ("64 KiB", 65536, "13.77", "8.33"),
    ("128 KiB", 131072, "14.71", "35.98"),
    ("1 MiB", 1048576, "26.71", "160.45"),
    ("8 MiB", 8388608, "99.18", "251.22"),
    ("16 MiB", 16777216, "176.23", "264.26"),
    ("128 MiB", 134217728, "1264.98", "293.11"),
    ("1 GiB", 1073741824, "9926.44", "314.44"),
    ("16 GiB", 17179869184, "94254.55", "318.98"),
]
# Graph-mode rows staged with times only (the staging doc flags the graph
# table's mid rows for re-verification; only the rows it quotes verbatim
# are used). Plus the graph 16 GiB plateau busbw quote (no staged time).
GRAPH_ROWS = [
    ("8 B", 8, "16.38"),
    ("32 B", 32, "6.32"),
    ("64 KiB", 65536, "9.14"),
]
GRAPH_PLATEAU_BUSBW_GBPS = "319.22"   # at 16 GiB, no time staged

# Link-level staged numbers (TransferBench, per-pair measurements).
LINK_RAW_GBPS = Fraction(64)          # "raw unidirectional bandwidth of 64 GB/s"
LINK_USABLE_GBPS = Fraction(48)       # "only about 48 GB/s (or 75%) is usable"
LINK_WORST_GBPS = Fraction(45)        # "the slowest link caps ... at ~45 GB/s"
LINK_OBSERVED_MIN_GBPS = Fraction("45.1")
LINK_OBSERVED_MAX_GBPS = Fraction("47.2")
LINK_AVG_GBPS = Fraction("45.8")      # "average across all links: 45.8 GB/s"
LINK_SUM_GBPS = Fraction("325.6")     # "Sum of Average Bandwidth ... 325.6 GB/s"

R = 8                                # the anchor's own rank count (one MI300X node)
K_BUSBW = Fraction(2 * (R - 1), R)    # 7/4 — RCCL/NCCL busbw convention at r=8
L = Fraction(200)                     # A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry point

EXECUTED_SIZES = [8, 32, 64, 16384, 65536, 17179869184]   # reconciling/latency rows
PLATEAU_SIZE = 17179869184                                 # 16 GiB
SMALL_SIZES = [8, 32, 64, 16384, 65536]

B_RING = Fraction(64)        # raw per-link per-direction rate (A-L0-BW point)
B_AGG = Fraction(448)        # 7 x 64 raw aggregate (CAL-A7 arithmetic)
B_WORST = Fraction(315)      # 7 x 45 worst-link aggregate
B_SUM = Fraction("325.6")    # measured link-sum aggregate
B_USABLE = Fraction(336)     # 7 x 48 usable-rate aggregate

PRINT_PRECISION = Fraction(1, 100)   # busbw columns print to 0.01 GB/s

CHAIN = {"ring": 2 * (R - 1), "doubling": 2 * 3, "crossbar": 2}  # latency-chain multiples at r=8


def anchor_t_ns(time_us: str) -> Fraction:
    return Fraction(time_us) * 1000


# ---------------------------------------------------------------------------
# 1. Series reconciliation — the FAIL-clause duty, executed per row.
# ---------------------------------------------------------------------------
def series_reconciliation() -> dict:
    """Check every staged (time, busbw) pair under the RCCL convention
    busbw = 2(r-1)/r * M / t at r=8 (the same convention class CAL-A3/A6
    carry). A row RECONCILES when |implied - quoted| <= 0.01 GB/s (the
    source table's print precision); latency-only rows carry no busbw and
    enter as measured band points; non-reconciling rows are EXCLUDED from
    every comparison and recorded with their exact residuals."""
    rows = []
    reconciling, excluded, latency_only = [], [], []
    for label, m, t_us, bw in EAGER_ROWS:
        t = anchor_t_ns(t_us)
        entry = {
            "size": label,
            "payload_bytes": m,
            "time_ns_exact": str(t),
            "algbw_bytes_per_ns_exact": str(Fraction(m) / t),
            "algbw_GB_per_s_float": float(Fraction(m) / t),
        }
        if bw is None:
            entry["status"] = "LATENCY_ONLY (no busbw quoted; enters the measured small-message band)"
            latency_only.append(label)
        else:
            implied = K_BUSBW * Fraction(m) / t
            quoted = Fraction(bw)
            residual = implied - quoted
            entry["implied_busbw_GB_per_s_exact"] = str(implied)
            entry["quoted_busbw_GB_per_s"] = bw
            entry["residual_GB_per_s_exact"] = str(residual)
            if abs(residual) <= PRINT_PRECISION:
                entry["status"] = "RECONCILES (within 0.01 GB/s print precision)"
                reconciling.append(label)
            else:
                entry["status"] = ("EXCLUDED — time and busbw mutually inconsistent "
                                   "under the 2(r-1)/r convention at r=8 (no real rank "
                                   "count produces the quoted factor; see ambiguities)")
                excluded.append(label)
        rows.append(entry)

    # Self-checks: a transcription bug must not silently change the verdicts.
    assert reconciling == ["16 KiB", "64 KiB", "16 GiB"], reconciling
    assert excluded == ["128 KiB", "1 MiB", "8 MiB", "16 MiB", "128 MiB", "1 GiB"], excluded
    assert latency_only == ["8 B", "32 B", "64 B"], latency_only
    assert all(size % R == 0 for size in EXECUTED_SIZES)  # A-L0-DIV / A-L0X-DIV / A-L0D-DIV accept
    assert R & (R - 1) == 0  # A-L0D-POW2 accepts natively

    return {
        "convention": "busbw = 2(r-1)/r * M / t at r=8 (factor 7/4) — the RCCL/NCCL "
        "convention; the comparison itself is CCT-vs-CCT (anchor CCT = the quoted "
        "times directly), so the factor cancels and reconciliation is only an "
        "internal-consistency gate on the staged table",
        "rows": rows,
        "verdict": {
            "reconciling": reconciling,
            "latency_only": latency_only,
            "excluded_mid_rows": excluded,
            "exclusion_rule": "the FAIL clause of the stage prompt applied per row: "
            "a row whose own two numbers disagree by 20-125 GB/s under the "
            "convention the series itself uses elsewhere is ambiguous as staged; "
            "the staging doc itself flags the mid rows ('re-verify at integration') "
            "— recorded here, never smoothed, never re-derived",
        },
    }


# ---------------------------------------------------------------------------
# 2. Link-level derating arithmetic (anchor-anchor; no run ids by construction).
# ---------------------------------------------------------------------------
def derating_arithmetic() -> dict:
    per_link_usable = LINK_USABLE_GBPS / LINK_RAW_GBPS                 # 3/4
    per_link_avg = LINK_AVG_GBPS / LINK_RAW_GBPS                       # 0.715625
    per_link_worst = LINK_WORST_GBPS / LINK_RAW_GBPS                   # 45/64
    plateau_busbw = Fraction("318.98")                                 # eager 16 GiB quote
    plateau_busbw_graph = Fraction(GRAPH_PLATEAU_BUSBW_GBPS)
    agg_spec = B_AGG                                                   # 448 = 7 x 64
    ratios = {
        "per_link_usable_over_raw": {"exact": "3/4", "float": 0.75,
                                     "note": "the blog's own '48 GB/s (or 75%)' "
                                     "usable quote over the 64 raw rate"},
        "per_link_avg_over_raw": {"exact": str(per_link_avg), "float": float(per_link_avg),
                                  "note": "measured TransferBench average link 45.8"},
        "per_link_worst_over_raw": {"exact": str(per_link_worst), "float": float(per_link_worst),
                                    "note": "worst-link cap ~45 of 64"},
        "plateau_busbw_over_spec_aggregate": {
            "exact": str(plateau_busbw / agg_spec), "float": float(plateau_busbw / agg_spec),
            "note": "eager 16 GiB busbw 318.98 over 7 x 64 = 448 — the ~0.71 "
            "measured/spec ratio the gap-fill doc names (graph 319.22 gives "
            + str(float(plateau_busbw_graph / agg_spec)) + ")"},
        "link_sum_over_spec_aggregate": {"exact": str(LINK_SUM_GBPS / agg_spec),
                                         "float": float(LINK_SUM_GBPS / agg_spec)},
        "worst_aggregate_over_spec": {"exact": str(B_WORST / agg_spec),
                                      "float": float(B_WORST / agg_spec)},
        "usable_aggregate_over_spec": {"exact": str(B_USABLE / agg_spec),
                                       "float": float(B_USABLE / agg_spec)},
    }
    # Internal tension of the link-sum quote: 7 x 45.8 = 320.6, not 325.6.
    seven_times_avg = 7 * LINK_AVG_GBPS
    tension = (LINK_SUM_GBPS - seven_times_avg) / LINK_SUM_GBPS
    assert seven_times_avg == Fraction("320.6")
    # Measured plateau EXCEEDS the worst-link aggregate (ring-caps-at-slowest-link reading).
    plateau_over_worst = plateau_busbw / B_WORST
    plateau_over_seven_avg = plateau_busbw / seven_times_avg
    # CAL-A12 pairing (xGMI class vs NVLink-3 class derating bridge).
    a12_derating = Fraction(4, 5)   # CAL-A12: app ~80% of physical peak (A100/NCCL)
    return {
        "ratios": ratios,
        "link_sum_internal_tension": {
            "quote": "'Sum of Average Bandwidth Across All GPU Pairs: 325.6 GB/s "
            "(average across all links: 45.8 GB/s)'",
            "arithmetic": "7 x 45.8 = 320.6 != 325.6 (sum would need avg 46.51); "
            "relative tension " + str(float(tension)) + " — recorded, the SUM used "
            "as staged (all model relations are 1/B-linear, so the 320.6 "
            "alternative rescales by closed form; nothing re-run)",
        },
        "plateau_vs_worst_link_aggregate": {
            "ratio_exact": str(plateau_over_worst),
            "ratio_float": float(plateau_over_worst),
            "note": "the measured collective plateau sits +1.26% ABOVE the "
            "anchor's own 7 x 45 = 315 worst-link expectation — a single ring "
            "capped by its slowest link cannot express this; the blog's 4-channel "
            "RCCL configuration can spread rings over faster links, and the "
            "measured average-link aggregate 320.6 is the consistent scale "
            "(plateau/320.6 = " + str(float(plateau_over_seven_avg)) + ") — "
            "ordering recorded, mechanism not adjudicated",
        },
        "cal_a12_pairing": {
            "xgmi_plateau_derating_float": float(plateau_busbw / agg_spec),
            "nvlink3_a12_derating": "0.8 (CAL-A12: NCCL app-level ~80% of "
            "physical peak, NVLink-3/A100 class)",
            "ratio_exact": str((plateau_busbw / agg_spec) / a12_derating),
            "ratio_float": float((plateau_busbw / agg_spec) / a12_derating),
            "note": "the xGMI class derating point this anchor contributes sits "
            "~11% below CAL-A12's NVLink-3 point (0.712 vs 0.80) — two "
            "fabric-class derating brackets now exist; cross-fabric transfer "
            "remains an assumption, labeled (the same discipline as stages "
            "A2/A7's derating bridges)",
        },
    }


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; cross-checked against every
# executed artifact by exact string equality).
# ---------------------------------------------------------------------------
def t_ring(m: int, b: Fraction) -> Fraction:
    """t = 2(r-1)/r * M/B + 2(r-1)*L  (src/essun/backends/analytical/l0.py)."""
    return K_BUSBW * Fraction(m) / b + CHAIN["ring"] * L


def t_xbar(m: int, b: Fraction) -> Fraction:
    """t = 2(r-1)/r * M/B + 2*L  (l0_crossbar.py)."""
    return K_BUSBW * Fraction(m) / b + CHAIN["crossbar"] * L


def t_doubling(m: int, b: Fraction) -> Fraction:
    """t = 2(r-1)/r * M/B + 2*log2(r)*L  (l0_recursive_doubling.py)."""
    return K_BUSBW * Fraction(m) / b + CHAIN["doubling"] * L


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    model = obs["model"]
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": model["ranks"],
            "backend_id": obs["backend_id"],
            "transport_model": model["transport_model"],
            "bandwidth_param_exact": model.get("link_bytes_per_ns_exact")
            or model.get("injection_bytes_per_ns_exact"),
            "latency_param_exact": model.get("hop_latency_ns_exact")
            or model.get("pair_latency_ns_exact"),
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "implied_busbw_bytes_per_ns_exact": str(
            Fraction(per_op["per_rank_wire_bytes_exact"])
            / Fraction(per_op["completion_time_ns_exact"])
        ),
    }


def sweep_rows_by_size(sweep_id: str) -> dict[int, dict[str, str]]:
    """Executed CCT exact strings keyed by (size, topology_id)."""
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    out: dict[int, dict[str, str]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        out.setdefault(row["payload_bytes"], {})[topo] = {
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "config_id": row["config_id"],
            "delta_vs_baseline_exact": row["delta_vs_baseline"]["delta_exact"],
        }
    return out


# ---------------------------------------------------------------------------
# 3. Small-message comparison (the smoke-regime target).
# ---------------------------------------------------------------------------
def comparison_small() -> dict:
    small = sweep_rows_by_size(SWEEP_ID_SMALL)
    eager = {label: anchor_t_ns(t) for label, m, t, bw in EAGER_ROWS if m in SMALL_SIZES}
    eager_by_size = {m: anchor_t_ns(t) for label, m, t, bw in EAGER_ROWS if m in SMALL_SIZES}
    graph_by_size = {m: anchor_t_ns(t) for label, m, t in GRAPH_ROWS}

    # Cross-check every executed row against the closed forms (exact).
    for m, topos in small.items():
        assert topos["ring8_gf01_link64_v1"]["cct_ns_exact"] == str(t_ring(m, B_RING)), m
        assert topos["crossbar8_gf01_agg448_v1"]["cct_ns_exact"] == str(t_xbar(m, B_AGG)), m
        assert topos["exchange8_gf01_agg448_v1"]["cct_ns_exact"] == str(t_doubling(m, B_AGG)), m

    per_size = []
    for m in SMALL_SIZES:
        t_eager = eager_by_size[m]
        entry = {
            "payload_bytes": m,
            "size_label": next(lbl for lbl, mm, t, bw in EAGER_ROWS if mm == m),
            "measured_eager_ns_exact": str(t_eager),
            "measured_graph_ns_exact": str(graph_by_size[m]) if m in graph_by_size else None,
            "model": {
                ident: {
                    "cct_ns_exact": small[m][topo]["cct_ns_exact"],
                    "config_id": small[m][topo]["config_id"],
                    "ratio_model_over_eager_exact": str(
                        Fraction(small[m][topo]["cct_ns_exact"]) / t_eager
                    ),
                    "ratio_model_over_eager_float": float(
                        Fraction(small[m][topo]["cct_ns_exact"]) / t_eager
                    ),
                    **(
                        {
                            "ratio_model_over_graph_float": float(
                                Fraction(small[m][topo]["cct_ns_exact"])
                                / graph_by_size[m]
                            )
                        }
                        if m in graph_by_size
                        else {}
                    ),
                }
                for ident, topo in (
                    ("ring_B64_per_link_reading", "ring8_gf01_link64_v1"),
                    ("doubling_B448_aggregate_reading", "exchange8_gf01_agg448_v1"),
                    ("crossbar_B448_aggregate_reading", "crossbar8_gf01_agg448_v1"),
                )
            },
            # Implied-effective-L: solve each identity's latency chain for L at
            # the measured time (anchor-anchor arithmetic on staged numbers +
            # executed bandwidth terms; NO run id claims these, and no
            # parameter anywhere is set to them).
            "implied_effective_L_ns": {
                ident: {
                    "from_eager_exact": str(
                        (t_eager - bw_term(m, ident)) / CHAIN[key]
                    ),
                    "from_eager_float": float((t_eager - bw_term(m, ident)) / CHAIN[key]),
                    **(
                        {
                            "from_graph_exact": str(
                                (graph_by_size[m] - bw_term(m, ident)) / CHAIN[key]
                            ),
                            "from_graph_float": float(
                                (graph_by_size[m] - bw_term(m, ident)) / CHAIN[key]
                            ),
                        }
                        if m in graph_by_size
                        else {}
                    ),
                }
                for ident, key in (
                    ("ring_B64", "ring"),
                    ("doubling_B448", "doubling"),
                    ("crossbar_B448", "crossbar"),
                )
            },
        }
        per_size.append(entry)

    # The measured band is non-monotone; the identity family is monotone in M.
    assert eager_by_size[8] > eager_by_size[16384]          # 16.61 us at 8 B > 13.54 us at 16 KiB
    assert graph_by_size[8] > graph_by_size[32]             # 16.38 us at 8 B > 6.32 us at 32 B
    for m_small, m_big in ((8, 32), (32, 64), (64, 16384), (16384, 65536)):
        assert t_ring(m_big, B_RING) > t_ring(m_small, B_RING)   # strictly monotone in M

    # Registry / CAL-A10 placement vs the ring-identity implied-L band.
    ring_L_eager = [
        (eager_by_size[m] - bw_term(m, "ring_B64")) / CHAIN["ring"] for m in SMALL_SIZES
    ]
    ring_L_all = ring_L_eager + [
        (graph_by_size[m] - bw_term(m, "ring_B64")) / CHAIN["ring"] for m in graph_by_size
    ]
    a10 = Fraction(800)   # CAL-A10 assumption-class 0.8 us end-to-end
    band_lo, band_hi = min(ring_L_all), max(ring_L_all)
    eager_lo, eager_hi = min(ring_L_eager), max(ring_L_eager)

    return {
        "regime": "small-message O-CCT, <= 64 KiB — the smoke-manifest regime; "
        "GF-01 is the first MEASURED staged anchor covering it (plan gap §4.3: "
        "previously 'none' / 'cannot be calibrated at all today, only verified')",
        "measured_band": {
            "eager": "16.61-16.74 us at 8-64 B; 13.54 / 13.77 us at 16 / 64 KiB",
            "graph": "16.38 us at 8 B; 6.32 us at 32 B; 9.14 us at 64 KiB",
            "envelope_note": "the eager/graph pair brackets software launch "
            "overhead: at 32 B graph mode saves 10,420 ns (16.74 -> 6.32 us, "
            "factor 2.65x); at 64 KiB 4,630 ns — a pure software-stack effect",
        },
        "per_size": per_size,
        "monotonicity_finding": {
            "claim": "the measured eager series is NON-MONOTONE in size "
            "(t(8 B) = 16,610 ns > t(16 KiB) = 13,540 ns; graph repeats it: "
            "t(8 B) = 16,380 ns > t(32 B) = 6,320 ns), while every fixed-(B,L) "
            "L0 identity is strictly monotone increasing in M (verified on the "
            "executed rows) — the measured small-message floor is set by "
            "launch/scheduling overheads INEXPRESSIBLE in the L0 input space, "
            "the latency-axis analog of stage A3's size-dependent effective-B "
            "finding on the bandwidth axis",
            "classification": "EXPRESSIVENESS LIMIT of the identity family, not a "
            "parameter mismatch; recorded for the owner (any future "
            "software-overhead term is a different identity)",
        },
        "latency_axis_placement": {
            "ring_identity_implied_L_band_ns": {
                "eager_only": [str(eager_lo), str(eager_hi)],
                "with_graph": [str(band_lo), str(band_hi)],
                "floats": [float(band_lo), float(band_hi)],
            },
            "registry_point_200_ns": "sits BELOW every implied L: "
            "eager band is " + str(float(eager_lo / L)) + "x to "
            + str(float(eager_hi / L)) + "x the registry point (the model is "
            "2.0-6.0x faster than the measured band in this regime, ring "
            "identity: 3.0-6.0x vs eager, 2.0-5.9x vs graph)",
            "cal_a10_800ns_assumption": "sits inside the overall implied band "
            "(" + str(float(a10 / band_hi)) + "x its upper edge, "
            + str(float(a10 / band_lo)) + "x its lower edge) but BELOW the "
            "eager-only band (800 < " + str(float(eager_lo)) + " ns) — "
            "arithmetic placement only; GF-10/GF-11 own the measured-latency "
            "axis stages",
            "honesty": "implied-L values are diagnostics computed FROM the "
            "measurements (anchor-anchor arithmetic on staged numbers plus the "
            "executed bandwidth terms); NO parameter anywhere is set to them — "
            "the registry point and every topology keep L = 200 ns",
        },
        "backing": "every model number is an executed sweep row (sweep "
        + SWEEP_ID_SMALL + ", 15 configs); closed forms verified against all "
        "15 rows by exact Fraction string equality; implied-L and placement "
        "ratios are declared arithmetic with no run ids",
    }


def bw_term(m: int, ident: str) -> Fraction:
    """The bandwidth term 2(r-1)/r*M/B of one identity at its stage-fixed B."""
    b = B_RING if "ring" in ident else B_AGG
    return K_BUSBW * Fraction(m) / b


# ---------------------------------------------------------------------------
# 4. Large-message comparison (the 16 GiB plateau target).
# ---------------------------------------------------------------------------
def comparison_large() -> dict:
    large = sweep_rows_by_size(SWEEP_ID_LARGE)
    t_anchor = anchor_t_ns("94254.55")   # eager 16 GiB, reconciling row

    topos = {
        "ring_B64_per_link_reading": ("ring8_gf01_link64_v1", B_RING, t_ring),
        "crossbar_B315_worst_link_aggregate": ("crossbar8_gf01_worst315_v1", B_WORST, t_xbar),
        "crossbar_B325_6_measured_link_sum": ("crossbar8_gf01_sum325_6_v1", B_SUM, t_xbar),
        "crossbar_B336_usable_aggregate": ("crossbar8_gf01_usable336_v1", B_USABLE, t_xbar),
        "crossbar_B448_raw_spec_ceiling": ("crossbar8_gf01_agg448_v1", B_AGG, t_xbar),
    }
    rows = {}
    for ident, (topo, b, closed) in topos.items():
        executed = large[PLATEAU_SIZE][topo]["cct_ns_exact"]
        assert executed == str(closed(PLATEAU_SIZE, b))  # closed-form cross-check
        rows[ident] = {
            "cct_ns_exact": executed,
            "cct_ns_float": float(Fraction(executed)),
            "config_id": large[PLATEAU_SIZE][topo]["config_id"],
            "delta_vs_measured_link_sum_baseline_exact": large[PLATEAU_SIZE][topo][
                "delta_vs_baseline_exact"
            ],
            "ratio_model_over_anchor_exact": str(Fraction(executed) / t_anchor),
            "ratio_model_over_anchor_float": float(Fraction(executed) / t_anchor),
        }

    # Anchor-implied effective aggregate B (crossbar reading, 2L removed):
    T = K_BUSBW * Fraction(PLATEAU_SIZE)      # per-rank wire bytes identity
    b_eff_xbar = T / (t_anchor - CHAIN["crossbar"] * L)
    b_eff_ring = T / (t_anchor - CHAIN["ring"] * L)
    seven_avg = 7 * LINK_AVG_GBPS             # 320.6

    ordering = [
        ("worst-link aggregate 7x45", B_WORST),
        ("anchor-implied effective B (crossbar chain, 2L removed)", b_eff_xbar),
        ("7 x measured avg link 45.8", seven_avg),
        ("measured link-sum aggregate 325.6", B_SUM),
        ("usable aggregate 7x48", B_USABLE),
        ("raw spec aggregate 7x64", B_AGG),
    ]
    for (_, lo), (_, hi) in zip(ordering, ordering[1:]):
        assert lo < hi, (lo, hi)

    return {
        "regime": "large-message bandwidth-bound O-CCT on a NON-NVIDIA scale-up "
        "fabric (MI300X xGMI full mesh) — extends the CAL-A3 (NVLink5/NVSwitch) "
        "target class to a second fabric class at r=8",
        "anchor_row": {
            "size": "16 GiB",
            "time_ns_exact": str(t_anchor),
            "busbw_quoted_GB_per_s": "318.98 (eager; graph 319.22 — both "
            "plateaus agree; only the eager row has a staged time)",
            "reconciliation": "RECONCILES (residual -0.006 GB/s at print "
            "precision) — the only bandwidth-bound row of the series that does",
        },
        "model_rows_at_16gib": rows,
        "anchor_implied_effective_aggregate_B": {
            "crossbar_chain_2L_removed_exact": str(b_eff_xbar),
            "crossbar_chain_2L_removed_float": float(b_eff_xbar),
            "ring_chain_14L_removed_float": float(b_eff_ring),
            "note": "diagnostic computed FROM the measured time (anchor-anchor "
            "arithmetic; no run id; nothing tuned) — the chain choice moves it "
            "by < 0.01 B/ns at this size (318.9756 crossbar vs 318.9837 ring); "
            "to print precision it coincides with the quoted busbw 318.98, as "
            "it must (2L is 4.2e-6 of t)",
        },
        "ordering_finding": {
            "claim": "the anchor-implied effective aggregate B (318.98 B/ns) "
            "lands BETWEEN the anchor's own worst-link expectation 315 "
            "(7 x 45) and its 7 x measured-average-link 320.6 — i.e. the "
            "blog's TransferBench link measurements PREDICT its collective "
            "plateau to within +1.26% (vs 315) / -0.51% (vs 320.6) via the "
            "bracket, while the raw spec aggregate 448 overestimates it by "
            "40.4% and the per-link ring reading underestimates it by 79.9%",
            "bracket": [
                {"reading": name, "B_exact": str(b), "B_float": float(b)}
                for name, b in ordering
            ],
            "verified_monotone": True,
        },
        "cross_stage_consistency": {
            "cal_a7_bracket": "stage A7's exact 7x bracket between the "
            "per-link (64) and aggregate (448) readings CONTAINS the measured "
            "plateau: 318.98/448 = 0.7120 of the aggregate reading, 318.98/64 "
            "= 4.978x the per-link reading (executed ring row at 16 GiB: "
            "469,764,848 ns = 4.98x the measured time, latency chain included)",
            "a3_mirror": "the -28.80% (spec point) to +1.26% (worst-link point) "
            "spread mirrors stage A3's finding that fixed-B placement dominates "
            "the comparison; GF-01's reconciling row implies a nearly "
            "size-independent effective B (one point only — no ramp claim)",
        },
        "backing": "every model number is an executed sweep row (sweep "
        + SWEEP_ID_LARGE + ", 30 configs; 5 topologies x 6 sizes) "
        "cross-checked against closed forms by exact Fraction string equality; "
        "effective-B, ratios, and the ordering are declared arithmetic",
    }


# ---------------------------------------------------------------------------
# 5. Ambiguity register (the FAIL-clause duty, centralized).
# ---------------------------------------------------------------------------
def ambiguities() -> dict:
    return {
        "mid_rows_excluded": "128 KiB, 1 MiB, 8 MiB, 16 MiB, 128 MiB, 1 GiB: "
        "staged time and busbw disagree by 20-125 GB/s under the convention "
        "the series' own reconciling rows use (residuals recorded per row in "
        "series_reconciliation); the staging doc flags the table rows and the "
        "overhead-percentage sentence for re-verification at integration — "
        "this stage neither re-derives nor averages them",
        "percentage_sentence_flag": "the blog's CRC-flit/packet-overhead "
        "percentages 'did not arithmetically reconcile during extraction' "
        "(staging doc's own flag); only the 48 GB/s usable figure is used, "
        "as staged",
        "link_sum_tension": "325.6 sum vs 45.8 average tension 1.56% at r=8 "
        "(see derating_arithmetic.link_sum_internal_tension); the SUM used "
        "as staged, 320.6 recorded as the closed-form alternative",
        "provenance": "vendor engineering blog (not peer-reviewed), confidence "
        "M-H per the staging doc; RCCL 2.22.3-develop:f5b15f2 / ROCm 6.3.0.0 "
        "pins carried; NOT a sources.csv row — the owner integrates accepted "
        "gap-fill rows (suggested continuation id CAL-A13); no handoff write "
        "was made by this stage",
        "busbw_convention": "busbw quotes carry RCCL/NCCL's 2(r-1)/r factor "
        "(same caveat class as CAL-A3/A6); handled by comparing CCT-vs-CCT "
        "(quoted times directly) — the factor cancels",
        "algorithm_unpinned": "the blog does not state which RCCL algorithm "
        "(ring/tree/hierarchical) produced the series, nor the channel count "
        "beyond '4 channels' at GPU 0; the stage executes the three available "
        "L0 identities as readings and records where each sits — algorithm "
        "choice belongs to a declared implementation profile, not this stage",
        "rank_domain": "r=8 is the anchor's own rank count and a power of two; "
        "all executed sizes divisible by 8 — every input gate ACCEPTS the "
        "anchor's exact sizes, no bracketing (the stage-A3 contrast)",
    }


def main() -> int:
    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-01 (gap-fill anchor GF-01)",
        "anchor": {
            "anchor_id": "GF-01",
            "title": "AMD ROCm blog: RCCL/xGMI on MI300X, full measured tables",
            "source_row": "NONE YET — gap-fill anchors are staging-doc rows only "
            "(docs/calibration/anchors_gapfill.md §GF-01); the owner integrates "
            "accepted rows into the anchor registry "
            "(suggested continuation id CAL-A13); this stage made no handoff write",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-01",
            "urls": [
                "https://github.com/ROCm/rocm-blogs/discussions/598",
                "https://rocm.blogs.amd.com/software-tools-optimization/mi300x-rccl-xgmi/README.html",
            ],
            "confidence": "M-H — real measured output with full software pins, "
            "but vendor blog (not peer-reviewed); per-pair row-level values and "
            "the overhead-percentage sentences flagged for re-verification in "
            "the staging doc; carried, not resolved",
            "measured_system": "all_reduce_perf on all 8 GPUs of an MI300X node "
            "(7-hop full-mesh xGMI); RCCL 2.22.3-develop:f5b15f2, ROCm 6.3.0.0; "
            "per-pair link measurements via TransferBench; eager and CUDA-graph "
            "modes; NCCL_GRAPH_MIX_SUPPORT=1",
        },
        "targets": {
            "o_cct_small_message": {
                "role": "the first MEASURED staged O-CCT series in the "
                "smoke-manifest regime (<= 64 KiB; plan gap §4.3) — CALIBRATABLE",
                "rows": "8/32/64 B (latency-only), 16 KiB, 64 KiB (both reconcile)",
            },
            "o_cct_large_message": {
                "role": "large-message O-CCT on a non-NVIDIA scale-up fabric — "
                "CALIBRATABLE at the single reconciling 16 GiB row",
            },
            "injection_derating": {
                "role": "measured link-rate derating for the xGMI class (48/64 "
                "usable; 45.1-47.2 observed; 315/320.6/325.6 aggregates) to pair "
                "with CAL-A12's ~80% on the NVLink-3 class",
            },
        },
        "series_reconciliation": series_reconciliation(),
        "derating_arithmetic": derating_arithmetic(),
        "model": {
            "backends_executed": [
                "analytical_l0 (ring; per-link reading)",
                "analytical_l0_crossbar (aggregate readings at 4 anchor points)",
                "analytical_l0_recursive_doubling (aggregate reading; sweep path "
                "only — stage A7's gate finding: run manifests cannot reach it)",
            ],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 14L ; B=64 (raw per-link)",
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; B in {315, 325.6, 336, 448}",
                "doubling": "t = 2(r-1)/r*M/B + 6L ; B=448",
            },
            "free_parameters": {
                "B_values_and_provenance": {
                    "64": "anchor's raw unidirectional xGMI link rate (= A-L0-BW registry point = stage A7's anchor point)",
                    "315": "7 x 45 — the anchor's worst-link expectation",
                    "325.6": "the anchor's measured TransferBench link-sum (baseline of the large sweep)",
                    "336": "7 x 48 — the anchor's usable-rate aggregate",
                    "448": "7 x 64 — the raw spec aggregate (CAL-A7 arithmetic; stage A7's anchor point)",
                },
                "L_ns": 200,
                "L_provenance": "A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry points "
                "(KEEP — the stage measures where the registry point sits "
                "relative to the first measured small-message band; it does not "
                "move it; the implied-L diagnostics are declared arithmetic, "
                "never parameter values)",
                "no_tuning_statement": "every B was fixed by the anchor's own "
                "staged arithmetic BEFORE any model output was read; the "
                "comparison outcome (plateau between 315 and 320.6) is recorded, "
                "not selected — no shipped manifest or topology value changed",
            },
            "assumptions": "A-L0-BW/A-L0-FD/A-L0-DIV (ring); A-L0X-PORT/A-L0X-BW/"
            "A-L0X-LAT/A-L0X-DIV (crossbar); A-L0D-POW2/A-L0D-STEP/A-L0D-BW/"
            "A-L0D-LAT/A-L0D-DIV (doubling) — all from experiments/vertical_slice/"
            "assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_RING_SMALL,
                    "per-link reading (ring in the mesh, B=64) at the registry "
                    "smoke payload 16 KiB — itself a reconciling GF-01 measured row",
                ),
                run_summary(
                    RUN_ID_XBAR_LARGE,
                    "aggregate reading (single-port crossbar at the anchor's "
                    "measured link-sum B=325.6) at the reconciling 16 GiB plateau row",
                ),
            ],
            "small_message": comparison_small(),
            "large_message": comparison_large(),
        },
        "ambiguities": ambiguities(),
        "deviation": {
            "summary": "small message: every identity at registry parameters is "
            "FASTER than the measured band — ring (the slowest chain) is "
            "3.0-6.0x faster than eager and 2.0-5.9x faster than graph across "
            "the reconciling sizes; the measured floor is launch-overhead-"
            "dominated and non-monotone, inexpressible at L0. Large message "
            "(16 GiB): model-vs-anchor lands -28.80% (raw spec point) / -5.07% "
            "(usable) / -2.03% (measured link-sum) / +1.26% (worst-link) — the "
            "anchor's own link measurements bracket its plateau within ~1.3% "
            "(implied effective B 318.98 between 315 and 320.6)",
            "cct_deviation_vs_anchor": "DEFINED at 5 reconciling sizes + the "
            "16 GiB row (the first GF-anchor stage with a measured CCT target); "
            "UNDEFINED for the 6 excluded mid rows (ambiguous as staged)",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, "
            "content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external "
            "published MEASUREMENT (vendor blog) — not our testbed, no E3/E4 "
            "language; owner adjudication required",
        },
        "backing": {
            "run_ids": [RUN_ID_RING_SMALL, RUN_ID_XBAR_LARGE],
            "sweep_ids": [SWEEP_ID_SMALL, SWEEP_ID_LARGE],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_SMALL}",
                f"results/sweeps/{SWEEP_ID_LARGE}",
            ],
            "run_backed_numbers": "every model output in comparison.* (2 store "
            "runs + 45 executed sweep configs); all 45 rows cross-checked "
            "against the closed-form identities by exact Fraction string "
            "equality; implied-L, derating ratios, effective-B, and ordering "
            "are declared anchor-anchor arithmetic with no run ids",
            "inputs": [
                "experiments/calibration/gf01/run_gf01_small_anchor_v1.yaml",
                "experiments/calibration/gf01/run_gf01_large_anchor_v1.yaml",
                "experiments/calibration/gf01/sweep_gf01_small_v1.yaml",
                "experiments/calibration/gf01/sweep_gf01_large_v1.yaml",
                "experiments/calibration/gf01/topologies/ (6 files)",
                "experiments/calibration/gf01/profiles/ (2 files)",
                "experiments/calibration/gf01/workloads/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf01/run_gf01_small_anchor_v1.yaml ; "
            "make run EXP=experiments/calibration/gf01/run_gf01_large_anchor_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf01/sweep_gf01_small_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf01/sweep_gf01_large_v1.yaml ; "
            "python experiments/calibration/gf01/build_calibration_record.py",
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
