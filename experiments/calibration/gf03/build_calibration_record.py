"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-03
(calibration stage GF-03;
p1_calibration.md; anchor staged in docs/calibration/anchors_gapfill.md §GF-03).

GF-03 = "B300 Field Notes (for the AI Infra/Performance Engineer)",
sixrackunits Substack (independent practitioner blog; NCCL allreduce/
broadcast + nvbandwidth on a B300 / Blackwell Ultra NVLink-5-class system;
confidence M — methodology context light: rank count and NCCL version not
cleanly captured): a measured O-CCT point on the POST-NVL72 generation
("AllReduce completes 2 MiB in as little as 42-52 us" — the anchor's only
staged CCT row), the measured allreduce peak 837 GB/s = 93% of its own
900 GB/s theoretical (a measured/spec derating point extending CAL-A3's
GB200 series by one generation), and measured D2D microbenchmark latencies
(~1.6 us device-to-device, ~1.4 us PCIe) for the plan's weakest axis
(gap §4.2). GF anchors are NOT sources.csv rows: the owner integrates
accepted rows; this record cites the gap-fill staging doc only.

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity with exact Fractions, and writes a content-addressed
record to ``results/calibration/<record_id>/record.json`` (record_id =
SHA-256 of the canonical record; append-only — existing different bytes are
an error, identical bytes are idempotent).

Every number below is (a) transcribed from the anchor's staged numbers in
docs/calibration/anchors_gapfill.md §GF-03 (declared with provenance; the
staging doc's M-confidence flags — rank count, NCCL version, paywall — are
carried, not resolved; numbers are used AS STAGED, not re-fetched), or
(b) computed from stored run/sweep artifacts, or (c) exact closed-form
identity arithmetic cross-checked against executed artifacts by exact
Fraction string equality (declared inline), or (d) anchor-anchor /
cross-anchor arithmetic on staged numbers (implied effective-B, implied-L,
derating ratios, CAL-A3-band containment — declared "no run id by
construction"). Nothing is tuned: the swept B values carry their anchor
provenance, fixed before any model output was read.

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
RUN_ID_CCT = "a7e2e3a96361cc9e9a0d049d8154db77ab600d0557ee2a01a7ec7d61c3308316"
RUN_ID_PLATEAU = "f31df808e75afb2b5195d2d84ca0ccba893653b9fcacb08465e2f975fdda14c1"
SWEEP_ID_BAND = "89009b661dcb9ec9e195c55e27ba9057144245c43e88ec585225851ba4826eb0"
SWEEP_ID_PLATEAU = "92fec4b450e18b7a31fc2e856ffde99bb851c5fe884c4f1d17c80af8ddb2dfdc"

RESULTS = REPO_ROOT / "results"

# GF-03 staged numbers (docs/calibration/anchors_gapfill.md §GF-03;
# confidence M — independent practitioner blog, methodology context light;
# decimal units, 1 GB/s = 1 B/ns; verbatim quotes in the record).
PEAK_GBPS = Fraction(837)            # "NCCL allreduce peak ~837 GB/s"
SPEC_GBPS = Fraction(900)            # "theoretical quoted as 900 GB/s class"
BCAST_GBPS = Fraction(682)           # "broadcast ~682 GB/s (~76%)"
D2D_UNI_A_GBPS = Fraction(782)       # "unidirectional 782 / 717 GB/s (per direction)"
D2D_UNI_B_GBPS = Fraction(717)
D2D_BI_A_GBPS = Fraction(1350)       # "bidirectional 1.35 / 1.41 TB/s"
D2D_BI_B_GBPS = Fraction(1410)
D2D_LATENCY_NS = Fraction(1600)      # "D2D latency ~1.6 us"
PCIE_LATENCY_NS = Fraction(1400)     # "PCIe H2D/D2H latency ~1.4 us"
CCT_ROW_BYTES = 2**21                # "NCCL AllReduce completes 2 MiB"
CCT_ROW_NS = (Fraction(42000), Fraction(52000))   # "in as little as 42-52 us"

R = 8                                # EXECUTED rank count (assumption: HGX B300 node default)
K_BUSBW = Fraction(2 * (R - 1), R)   # 7/4 — NCCL busbw convention at r=8
L = Fraction(200)                    # A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry point

B_LINK = Fraction(50)        # per-link per-direction (CAL-A1/A2 NVLink5 arithmetic: 18 x 50 = 900)
B_D2D_LO = Fraction(717)     # nvbandwidth unidirectional, lower quote
B_D2D_HI = Fraction(782)     # nvbandwidth unidirectional, higher quote
B_PEAK = Fraction(837)       # measured allreduce peak (plateau baseline)
B_SPEC = Fraction(900)       # the anchor's "theoretical" = CAL-A2's line

BAND_SIZES = [2**16, 2**18, 2**20, 2**21, 2**22]          # 64 KiB .. 4 MiB
PLATEAU_SIZES = [2**24, 2**27, 2**30, 2**34]              # 16 MiB .. 16 GiB (declared probe sizes)
PROBE_SIZE = 2**34                                         # GF-01 plateau cross-reference size

CHAIN = {"ring": 2 * (R - 1), "doubling": 2 * 3, "crossbar": 2}  # latency-chain multiples at r=8

# Cross-anchor staged constants (declared provenance, no run ids by construction).
A12_DERATING = Fraction(4, 5)             # CAL-A12: NCCL app ~80% of physical peak (NVLink-3/A100)
GF01_DERATING = Fraction("318.98") / Fraction(448)   # GF-01 xGMI plateau/spec (stage GF-01 record)
A3_BUSBW_SERIES = [Fraction(x) for x in ("787.95", "831.03", "866.36", "890.32", "906.94")]  # CAL-A3 GB200


def anchor_band_ns() -> tuple[Fraction, Fraction]:
    return CCT_ROW_NS


# ---------------------------------------------------------------------------
# 1. Headline reconciliation — the FAIL-clause duty, applied per headline
#    claim (GF-03 stages headline numbers, not a (size, time, busbw) table).
# ---------------------------------------------------------------------------
def headline_reconciliation() -> dict:
    peak_ratio = PEAK_GBPS / SPEC_GBPS                       # 93/100 exactly
    bcast_ratio = BCAST_GBPS / SPEC_GBPS                     # 341/450
    # Self-checks: transcription bugs must not silently change verdicts.
    assert peak_ratio == Fraction(93, 100)
    assert abs(bcast_ratio - Fraction(76, 100)) <= Fraction(1, 400)   # "~76%" at half-percent rounding

    # The 2 MiB CCT row: no paired busbw quote; enter as a BAND point after
    # checking it does not CONTRADICT the peak (a sub-plateau point is
    # consistent; a super-plateau implied busbw would be a FAIL-clause row).
    implied_busbw = [K_BUSBW * Fraction(CCT_ROW_BYTES) / t for t in CCT_ROW_NS]
    assert all(bw < PEAK_GBPS for bw in implied_busbw)       # 70.6 .. 87.4 < 837 — consistent

    # nvbandwidth uni/bi pairing: unstated by the anchor; arithmetic tension
    # recorded (2x each unidirectional EXCEEDS both bidirectional quotes).
    uni_doubled = [2 * D2D_UNI_A_GBPS, 2 * D2D_UNI_B_GBPS]   # 1564, 1434
    bi_quotes = [D2D_BI_A_GBPS, D2D_BI_B_GBPS]               # 1350, 1410
    assert all(u > b for u in uni_doubled for b in bi_quotes)

    rows = [
        {
            "claim": "allreduce peak ~837 GB/s is '93% of theoretical' (900)",
            "arithmetic": "837/900 = 93/100 exactly",
            "status": "RECONCILES — the anchor's own percentage is exact",
        },
        {
            "claim": "broadcast ~682 GB/s (~76%)",
            "arithmetic": "682/900 = 341/450 = 0.75778",
            "status": "RECONCILES at quote rounding (residual +0.0022 vs '76%') — "
            "NOT executed: no broadcast identity exists in the L0 backend set; "
            "recorded as anchor-anchor derating arithmetic only",
        },
        {
            "claim": "AllReduce completes 2 MiB 'in as little as 42-52 us'",
            "arithmetic": "implied busbw 2(r-1)/r*M/t at r=8 = "
            + "/".join(str(float(b)) for b in implied_busbw)
            + " GB/s — sub-plateau, consistent with (not contradicting) the 837 peak",
            "status": "BAND POINT (no paired busbw to reconcile against; 'as little "
            "as' = best-case semantics recorded in ambiguities) — the stage's only "
            "CCT-vs-CCT target",
        },
        {
            "claim": "nvbandwidth D2D unidirectional 782 / 717 GB/s, bidirectional 1.35 / 1.41 TB/s",
            "arithmetic": "pairing of the two unidirectional with the two "
            "bidirectional quotes is UNSTATED; 2x782 = 1564 and 2x717 = 1434 both "
            "EXCEED both bidirectional quotes (by 5.9-9.8%)",
            "status": "AMBIGUOUS PAIRING — the four numbers do not mutually "
            "contradict, but no pairing reconciles them; each unidirectional "
            "reading is used as its own aggregate point, the bidirectional quotes "
            "enter only as recorded derating arithmetic (1350/1800 = 0.75, "
            "1410/1800 = 0.7833)",
        },
        {
            "claim": "D2D latency ~1.6 us; PCIe H2D/D2H ~1.4 us",
            "arithmetic": "no cross-check available (latency microbenchmark quotes)",
            "status": "LATENCY-AXIS POINTS (comparison §latency_axis; app-level "
            "D2D includes the software stack — interpretation caveat carried)",
        },
    ]
    assert all(size % R == 0 for size in BAND_SIZES + PLATEAU_SIZES + [CCT_ROW_BYTES])
    assert R & (R - 1) == 0  # A-L0D-POW2 accepts natively

    return {
        "convention": "GF-03 stages headline numbers, not a (size -> time, busbw) "
        "table, so reconciliation runs per headline claim: each quoted ratio is "
        "checked against its own quoted percentage; the CCT row against the peak; "
        "the nvbandwidth uni/bi quotes against each other. CCT-vs-CCT comparisons "
        "use the quoted times directly; the plateau reference uses the DECLARED "
        "busbw->CCT conversion t_ref = 2(r-1)/r*M/837 (the NCCL busbw convention "
        "inverted) — never mixed metrics",
        "rows": rows,
        "verdict": {
            "reconciling": ["837 = 93% of 900 (exact)", "682 ~ 76% of 900 (rounding)"],
            "band_point": "2 MiB @ 42-52 us (consistent, sub-plateau)",
            "ambiguous": ["nvbandwidth uni/bi pairing (unstated; used per-reading)"],
            "exclusion_rule": "the FAIL clause of the stage prompt applied per "
            "claim: nothing here is contradictory enough to exclude a number, but "
            "the broadcast row is NOT executed (no L0 broadcast identity) and the "
            "bidirectional quotes are not executed (no bidirectional identity); "
            "both are recorded as declared arithmetic with no run ids",
        },
    }


# ---------------------------------------------------------------------------
# 2. Derating arithmetic (anchor-anchor / cross-anchor; no run ids).
# ---------------------------------------------------------------------------
def derating_arithmetic() -> dict:
    peak_over_spec = PEAK_GBPS / SPEC_GBPS                   # 0.93
    ratios = {
        "allreduce_peak_over_theoretical": {
            "exact": "93/100", "float": 0.93,
            "note": "the anchor's own derating claim, exact"},
        "broadcast_over_theoretical": {
            "exact": str(BCAST_GBPS / SPEC_GBPS), "float": float(BCAST_GBPS / SPEC_GBPS),
            "note": "~76% claimed; not executable (no broadcast identity)"},
        "nvband_uni_over_theoretical": [
            {"quote": "782", "exact": str(D2D_UNI_A_GBPS / SPEC_GBPS),
             "float": float(D2D_UNI_A_GBPS / SPEC_GBPS)},
            {"quote": "717", "exact": str(D2D_UNI_B_GBPS / SPEC_GBPS),
             "float": float(D2D_UNI_B_GBPS / SPEC_GBPS)},
        ],
        "nvband_bidir_over_theoretical": [
            {"quote": "1.35 TB/s", "exact": str(D2D_BI_A_GBPS / (2 * SPEC_GBPS)),
             "float": float(D2D_BI_A_GBPS / (2 * SPEC_GBPS))},
            {"quote": "1.41 TB/s", "exact": str(D2D_BI_B_GBPS / (2 * SPEC_GBPS)),
             "float": float(D2D_BI_B_GBPS / (2 * SPEC_GBPS))},
        ],
    }
    # CAL-A3 GB200 band containment (the gap-fill doc's stated role: GF-03
    # "extends CAL-A3's GB200 series by one generation").
    a3_fractions = [x / SPEC_GBPS for x in A3_BUSBW_SERIES]
    assert min(a3_fractions) < peak_over_spec < max(a3_fractions)
    return {
        "ratios": ratios,
        "cal_a12_pairing": {
            "nvlink5_b300_derating": "0.93 (GF-03 measured peak / its own 900 theoretical)",
            "nvlink3_a12_derating": "0.8 (CAL-A12: NCCL app-level ~80% of physical peak)",
            "xgmi_gf01_derating": f"{float(GF01_DERATING):.4f} (GF-01 MI300X plateau / 7x64 spec)",
            "nvlink5_over_a12_exact": str(peak_over_spec / A12_DERATING),
            "nvlink5_over_a12_float": float(peak_over_spec / A12_DERATING),
            "nvlink5_over_xgmi_float": float(peak_over_spec / GF01_DERATING),
            "note": "THREE fabric-class derating brackets now exist (xGMI 0.712 / "
            "NVLink-3 0.80 / NVLink-5 B300 0.93): the software derating SHRINKS "
            "with generation on these anchors' own numbers; cross-fabric and "
            "cross-generation transfer remains a labeled assumption, never tuned",
        },
        "cal_a3_corroboration": {
            "a3_gb200_fractions_float": [float(x) for x in a3_fractions],
            "gf03_fraction_float": float(peak_over_spec),
            "claim": "GF-03's 0.93 sits INSIDE CAL-A3's GB200 measured band "
            "(0.8755 at 2 GiB .. 1.00771 at 32 GiB) — the post-NVL72 generation "
            "corroborates the GB200 series' scale one generation later (two "
            "independent sources, M and M-H confidence respectively; not averaged, "
            "not fitted)",
        },
        "peak_vs_d2d_readings": {
            "peak_over_d2d782_exact": str(PEAK_GBPS / D2D_UNI_A_GBPS),
            "peak_over_d2d782_float": float(PEAK_GBPS / D2D_UNI_A_GBPS),
            "peak_over_d2d717_float": float(PEAK_GBPS / D2D_UNI_B_GBPS),
            "note": "the measured COLLECTIVE peak EXCEEDS both measured single-pair "
            "D2D readings — the per-pair microbenchmark UNDERPREDICTS the "
            "multi-pair collective by 7.0-16.7% (opposite direction from GF-01, "
            "whose worst-link 315 sat only 1.26% below its collective plateau); "
            "nvbandwidth D2D is kernel-launch-limited (known caveat class) — "
            "ordering recorded, mechanism not adjudicated",
        },
        "ring_channel_factor": {
            "peak_over_per_link_exact": str(PEAK_GBPS / B_LINK),
            "peak_over_per_link_float": float(PEAK_GBPS / B_LINK),
            "note": "837/50 = 16.74: a single-channel ring at the per-link rate "
            "cannot reach the measured peak; a real NCCL ring would need ~17 of "
            "the 18 available NVLink-5 links/channels — consistent with NCCL's "
            "default multi-channel behavior; arithmetic ordering only",
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


def sweep_rows_by_size(sweep_id: str) -> dict[int, dict[str, dict[str, str]]]:
    """Executed CCT exact strings keyed by (size, topology_id)."""
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    out: dict[int, dict[str, dict[str, str]]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        out.setdefault(row["payload_bytes"], {})[topo] = {
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "config_id": row["config_id"],
            "delta_vs_baseline_exact": row["delta_vs_baseline"]["delta_exact"],
        }
    return out


BAND_TOPOS = {
    "ring_B50_per_link_reading": ("ring8_gf03_link50_v1", B_LINK, t_ring),
    "crossbar_B717_d2d_reading": ("crossbar8_gf03_d2d717_v1", B_D2D_LO, t_xbar),
    "crossbar_B782_d2d_reading": ("crossbar8_gf03_d2d782_v1", B_D2D_HI, t_xbar),
    "crossbar_B837_measured_peak": ("crossbar8_gf03_peak837_v1", B_PEAK, t_xbar),
    "crossbar_B900_theoretical": ("crossbar8_gf03_spec900_v1", B_SPEC, t_xbar),
    "doubling_B900_theoretical": ("exchange8_gf03_spec900_v1", B_SPEC, t_doubling),
}


def _crosscheck(rows_by_size: dict[int, dict[str, dict[str, str]]], sizes: list[int],
                topos: dict[str, tuple[str, Fraction, object]]) -> None:
    for m in sizes:
        for ident, (topo, b, closed) in topos.items():
            assert rows_by_size[m][topo]["cct_ns_exact"] == str(closed(m, b)), (m, ident)


# ---------------------------------------------------------------------------
# 3. Band comparison — the 2 MiB CCT row (the only CCT-vs-CCT target).
# ---------------------------------------------------------------------------
def comparison_band() -> dict:
    band = sweep_rows_by_size(SWEEP_ID_BAND)
    # ALL five B readings execute at ALL five band sizes, so the anchor's own
    # 2 MiB row is executed at every reading (30 configs).
    band_topos = dict(BAND_TOPOS)
    _crosscheck(band, BAND_SIZES, band_topos)

    t_lo, t_hi = anchor_band_ns()
    m0 = CCT_ROW_BYTES

    per_size = []
    for m in BAND_SIZES:
        entry = {
            "payload_bytes": m,
            "is_anchor_row": m == m0,
            "model": {
                ident: {
                    "cct_ns_exact": band[m][topo]["cct_ns_exact"],
                    "config_id": band[m][topo]["config_id"],
                    **({"ratio_over_anchor_band": [
                        str(Fraction(band[m][topo]["cct_ns_exact"]) / t_lo),
                        str(Fraction(band[m][topo]["cct_ns_exact"]) / t_hi)]}
                       if m == m0 else {}),
                }
                for ident, (topo, b, closed) in band_topos.items()
            },
        }
        per_size.append(entry)

    # Implied effective-B (crossbar chain, L=200) from the measured band.
    km = K_BUSBW * Fraction(m0)
    b_eff = [km / (t - CHAIN["crossbar"] * L) for t in (t_lo, t_hi)]
    # r=72 sensitivity of that diagnostic (the anchor states no rank count).
    k72 = Fraction(2 * 71, 72) * Fraction(m0)
    b_eff_r72 = [k72 / (t - CHAIN["crossbar"] * L) for t in (t_lo, t_hi)]
    # Implied L (crossbar chain) at the anchor's own plateau reading.
    impl_L_837 = [(t - km / B_PEAK) / CHAIN["crossbar"] for t in (t_lo, t_hi)]
    impl_L_900 = [(t - km / B_SPEC) / CHAIN["crossbar"] for t in (t_lo, t_hi)]
    # Exhaustive no-combination check: every (chain, B, L) pair constructible
    # from the anchor's own numbers, vs the measured band.
    combos = {}
    for chain_key, chain_L in (("ring", CHAIN["ring"]), ("doubling", CHAIN["doubling"]),
                               ("crossbar", CHAIN["crossbar"])):
        for b in (B_LINK, B_D2D_LO, B_D2D_HI, B_PEAK, B_SPEC):
            for lat in (L, D2D_LATENCY_NS):
                combos[f"{chain_key}_B{b}_L{lat}"] = km / b + chain_L * lat
    below = {k: v for k, v in combos.items() if v < t_lo}
    above = {k: v for k, v in combos.items() if v > t_hi}
    assert not (set(combos) - set(below) - set(above))   # none lands inside the band
    max_below = max(below.values())
    min_above = min(above.values())
    # Transcription guard: pin the extremes to their constructible identities so
    # narrative numbers can never silently desynchronize from the arithmetic.
    assert max_below == km / Fraction(717) + CHAIN["ring"] * D2D_LATENCY_NS
    assert min_above == km / B_LINK + CHAIN["crossbar"] * L
    fastest_at_measured_L = km / B_SPEC + CHAIN["crossbar"] * D2D_LATENCY_NS

    # Model monotone in M (fixed B, L); the single measured point cannot be
    # monotone-checked against itself — the finding is the GAP, not ordering.
    for m_small, m_big in zip(BAND_SIZES, BAND_SIZES[1:]):
        assert t_ring(m_big, B_LINK) > t_ring(m_small, B_LINK)

    return {
        "regime": "medium-small O-CCT around the anchor's only staged CCT row "
        "(2 MiB in 'as little as 42-52 us') on the post-NVL72 B300 NVLink-5 "
        "generation — the anchor's sole CCT-vs-CCT target",
        "anchor_row": {
            "size_bytes": m0,
            "band_ns_exact": [str(t_lo), str(t_hi)],
            "semantics": "'as little as' = best-case observed band, not a mean; "
            "warmup/iteration protocol unstated (ambiguity register)",
        },
        "per_size": per_size,
        "placement_finding": {
            "claim": "every AGGREGATE-reading chain sits 8.0-11.6x BELOW the "
            "measured band (crossbar837 4,784.7 ns = 8.78-10.87x below; "
            "crossbar900 4,477.8 ns = 9.38-11.61x; doubling900 5,277.8 ns = "
            "7.96-9.85x) while the PER-LINK ring reading overshoots 1.47-1.81x "
            "ABOVE it (76,200.3 ns) — the measured row lies strictly between the "
            "two reading classes of the anchor's own numbers",
            "no_combination_check": {
                "n_combinations": len(combos),
                "construction": "3 latency chains x 5 anchor B readings {50, 717, "
                "782, 837, 900} x 2 L values {200 registry, 1,600 measured D2D}",
                "largest_below_band_exact": str(max_below),
                "largest_below_band_float": float(max_below),
                "smallest_above_band_exact": str(min_above),
                "smallest_above_band_float": float(min_above),
                "verdict": "NONE of the 30 constructible predictions lands inside "
                "the 42,000-52,000 ns band — even the most generous chain "
                "(crossbar at B=900, L at the anchor's own measured D2D latency) "
                "predicts " + str(float(fastest_at_measured_L)) + " ns = 5.77-7.15x "
                "below it; the row is an algorithm/software-overhead floor, "
                "INEXPRESSIBLE in the fixed-(B, L) L0 input space",
                "classification": "EXPRESSIVENESS LIMIT of the identity family "
                "(the GF-01 small-message launch-floor finding, repeated one "
                "fabric generation later and 4-5x larger in relative gap)",
            },
        },
        "implied_effective_B": {
            "crossbar_chain_L200_r8_exact": [str(x) for x in b_eff],
            "crossbar_chain_L200_r8_float": [float(x) for x in b_eff],
            "crossbar_chain_L200_r72_float": [float(x) for x in b_eff_r72],
            "collapse_vs_plateau_float": [float(B_PEAK / x) for x in b_eff],
            "note": "diagnostics computed FROM the measured band (anchor-anchor "
            "arithmetic + the executed bandwidth terms; NO run id; nothing set): "
            "the 2 MiB row implies effective B 71.1-88.2 B/ns at r=8 (80.2-99.4 "
            "at r=72 — the finding is rank-count-robust), a 9.5-11.8x "
            "size-dependent collapse below the 837 plateau — stage A3's "
            "size-dependent effective-B finding class, now with a measured "
            "mid-size row on the newest generation",
        },
        "implied_effective_L": {
            "crossbar_at_B837_exact": [str(x) for x in impl_L_837],
            "crossbar_at_B837_float": [float(x) for x in impl_L_837],
            "crossbar_at_B900_float": [float(x) for x in impl_L_900],
            "note": "solving the crossbar chain for L at the measured times gives "
            "18.8-24.0 us — 11.8-14.9x the anchor's own measured D2D latency "
            "(1.6 us) and 94-119x the 200 ns registry point: the row is not "
            "latency-explainable either; declared arithmetic, no parameter moved",
        },
        "backing": "every model number is an executed sweep row (sweep "
        + SWEEP_ID_BAND + ", 30 configs: 6 readings x 5 sizes — the anchor's own "
        "2 MiB row executed at EVERY reading); closed forms verified by exact "
        "Fraction string equality on every executed row; implied-B / implied-L / "
        "no-combination arithmetic is declared with no run ids",
    }


# ---------------------------------------------------------------------------
# 4. Plateau comparison — the 837-peak placement (declared conversion).
# ---------------------------------------------------------------------------
def comparison_plateau() -> dict:
    plateau = sweep_rows_by_size(SWEEP_ID_PLATEAU)
    _crosscheck(plateau, PLATEAU_SIZES, BAND_TOPOS)

    out = {}
    for m in PLATEAU_SIZES:
        t_ref = K_BUSBW * Fraction(m) / B_PEAK   # DECLARED busbw->CCT conversion
        rows = {}
        for ident, (topo, b, closed) in BAND_TOPOS.items():
            executed = plateau[m][topo]["cct_ns_exact"]
            assert executed == str(closed(m, b))
            rows[ident] = {
                "cct_ns_exact": executed,
                "cct_ns_float": float(Fraction(executed)),
                "config_id": plateau[m][topo]["config_id"],
                "delta_vs_measured_peak_baseline_exact": plateau[m][topo][
                    "delta_vs_baseline_exact"
                ],
                "ratio_model_over_anchor_ref_exact": str(Fraction(executed) / t_ref),
                "ratio_model_over_anchor_ref_float": float(Fraction(executed) / t_ref),
            }
        out[str(m)] = {
            "anchor_reference_ns_exact": str(t_ref),
            "conversion": "t_ref = 2(r-1)/r * M / 837 (the measured peak busbw, "
            "NCCL convention inverted; no latency term — the quote carries none; "
            "the model's own chain latency makes model ratios +0.001%..+0.008% "
            "conservative at these sizes)",
            "rows": rows,
        }

    m = PROBE_SIZE
    probe = out[str(m)]["rows"]
    # Ordering + findings at the probe size.
    assert B_D2D_LO < B_D2D_HI < B_PEAK < B_SPEC
    assert float(probe["crossbar_B717_d2d_reading"]["ratio_model_over_anchor_ref_float"]) > 1
    assert float(probe["crossbar_B900_theoretical"]["ratio_model_over_anchor_ref_float"]) < 1
    # the B837 baseline row's exact time is K*M/837 + 2L (closed-form assert in
    # _crosscheck); its ratio vs the no-latency reference is the 2L term only.
    assert probe["crossbar_B837_measured_peak"]["cct_ns_exact"] == str(t_xbar(PROBE_SIZE, B_PEAK))

    return {
        "regime": "large-message bandwidth-bound placement on the post-NVL72 "
        "generation: the anchor's measured allreduce peak (837 GB/s = 93% of its "
        "own 900 theoretical) read through the DECLARED busbw->CCT conversion at "
        "four probe sizes — size-independent to 1/B-linear closed form",
        "probe_sizes_declared_free": "GF-03 stages NO size in this regime; "
        "{16 MiB, 128 MiB, 1 GiB, 16 GiB} are declared free execution probes "
        "(2^34 cross-references GF-01's plateau row); every ratio below changes "
        "by < 0.008% across the four sizes",
        "per_size": out,
        "placement_finding_16gib": {
            "claim": "at the 16 GiB probe: D2D readings sit +7.03% (782) / +16.74% "
            "(717) ABOVE the anchor reference (slower), the measured-peak baseline "
            "+0.001% (its own 2L term only), the theoretical reading -7.00% below "
            "(the anchor's own 93% derating made model-exact), the per-link ring "
            "16.74x above — ordering 717 < 782 < 837 < 900 exact",
            "d2d_underpredicts": "the measured single-pair D2D readings lie BELOW "
            "the measured collective peak by the same 7.0-16.7% (see "
            "derating_arithmetic.peak_vs_d2d_readings) — the aggregate sweep makes "
            "the methodology gap executable, not adjudicated",
            "cross_stage": "GF-01's mirror structure inverts: there the link "
            "measurements BRACKETED the collective plateau (315 < 318.98 < "
            "325.6); here both D2D readings sit strictly BELOW it — two measured "
            "microbenchmark-vs-collective relationships on two fabric classes, "
            "both recorded, neither tuned",
        },
        "backing": "every model number is an executed sweep row (sweep "
        + SWEEP_ID_PLATEAU + ", 24 configs; 6 readings x 4 sizes) cross-checked "
        "against closed forms by exact Fraction string equality; the anchor "
        "reference and all ratios are declared arithmetic with no run ids",
    }


# ---------------------------------------------------------------------------
# 5. Latency-axis placement (measured D2D microbenchmark points).
# ---------------------------------------------------------------------------
def latency_axis() -> dict:
    return {
        "measured_points": {
            "d2d_latency_ns": str(D2D_LATENCY_NS),
            "pcie_h2d_d2h_latency_ns": str(PCIE_LATENCY_NS),
            "note": "nvbandwidth D2D (~1.6 us) and PCIe H2D/D2H (~1.4 us) "
            "latencies — measured microbenchmark points for the plan's weakest "
            "axis (gap §4.2: previously only assumption-grade CAL-A10 0.8 us or "
            "CXL-class design estimates)",
        },
        "placement": {
            "registry_point_200_ns": "the D2D point sits 8.0x ABOVE the "
            "A-L0X-LAT / A-L0-LAT registry point 200 ns (PCIe: 7.0x) — "
            "arithmetic placement only, NO parameter moved",
            "vs_cal_a10_800ns": "the D2D point sits 2.0x ABOVE CAL-A10's "
            "assumption-class 0.8 us end-to-end figure",
            "vs_gf01_implied_band": "GF-01's MI300X ring-identity implied-L band "
            "was 451-1,196 ns — the B300 D2D point (1,600 ns) sits above that "
            "entire band: measured app-level pair latency has DOUBLED-ish "
            "generation-over-generation while both sit far above the 200 ns "
            "registry point",
            "vs_band_row": "the 2 MiB CCT row is NOT latency-explainable by this "
            "point either: implied L from the row is 18.8-24.0 us = 11.8-14.9x "
            "the D2D point (comparison_band.implied_effective_L)",
        },
        "interpretation_caveat": "nvbandwidth D2D latency is an APPLICATION-LEVEL "
        "pair measurement (includes the software stack), not a hop/wire latency "
        "— it bounds what a collective can observe per pair, not what a switch "
        "adds per hop; GF-10 (V100-era P2P) and GF-11 (NVLink5 component "
        "decomposition 0.306/0.792 us) own the measured-latency-axis stages; "
        "GF-03 contributes the B300-generation microbenchmark point only",
    }


# ---------------------------------------------------------------------------
# 6. Ambiguity register (the FAIL-clause duty, centralized).
# ---------------------------------------------------------------------------
def ambiguities() -> dict:
    return {
        "rank_count_unstated": "the anchor does not state the rank count "
        "(staging doc: 'rank count, NCCL version not cleanly captured'); r=8 "
        "(HGX B300 single-node default, a power of two) is an EXECUTED "
        "ASSUMPTION — the plateau derating arithmetic is rank-count-insensitive "
        "(busbw = per-rank send rate <= injection cap at any r), and the 2 MiB "
        "implied-B diagnostic is computed at r=72 as well (finding robust); a "
        "GB300-NVL72 reading (r=72) would change executed TIMES but not the "
        "0.93/plateau ratios",
        "nccl_version_unstated": "no NCCL version pin (staging-doc flag); the "
        "5-8% software-version swing CAL-A6 measures cannot be applied or "
        "removed — carried as M-confidence provenance",
        "as_little_as_semantics": "the 2 MiB row is quoted 'in as little as "
        "42-52 us' — a BEST-CASE band, not a mean/median; warmup and iteration "
        "protocol unstated; treated strictly as a band everywhere",
        "busbw_convention": "837 is read as an nccl-tests-style busbw plateau "
        "(the anchor's own '93% of 900' is exact under that reading; if it were "
        "algbw, the implied per-rank send rate 7/4 x 837 = 1464.75 would exceed "
        "the 900 injection cap — infeasible). GF-02's counting-convention "
        "hazard class; the CCT comparisons use quoted times / the declared "
        "conversion, never mixed metrics",
        "nvbandwidth_pairing": "the two unidirectional {782, 717} and two "
        "bidirectional {1.35, 1.41 TB/s} D2D quotes have no stated pairing; "
        "2x each unidirectional exceeds both bidirectional quotes by 5.9-9.8% — "
        "recorded, each unidirectional reading used as its own aggregate point",
        "broadcast_not_executed": "no broadcast identity exists in the L0 "
        "backend set; the 682 GB/s (~76%) row is recorded as derating "
        "arithmetic only — EXECUTION of that target is impossible at this "
        "fidelity, an honest gap, not a skip",
        "plateau_size_free": "GF-03 stages no message size for its 837 peak; "
        "the plateau probe sizes {16 MiB..16 GiB} are declared free execution "
        "choices (GF-01's 16 GiB row WAS its anchor's own size — the contrast "
        "is recorded); the comparison is size-independent to closed form",
        "provenance": "independent practitioner blog (not peer-reviewed, not "
        "vendor), confidence M per the staging doc, partial paywall possible — "
        "all numbers used AS STAGED in docs/calibration/anchors_gapfill.md "
        "§GF-03, not re-fetched by this stage; NOT a sources.csv row — the "
        "owner integrates accepted gap-fill rows; no handoff write was made",
        "spec_reading_cross_anchor": "the '900 GB/s class theoretical' is used "
        "as the spec reading with CAL-A1/CAL-A2 cross-anchor provenance "
        "(1.8 TB/s bidirectional per GPU / 2 = 18 links x 50 B/ns) — the anchor "
        "quotes the class number, the cross-anchor arithmetic pins it exactly",
    }


def main() -> int:
    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-03 (gap-fill anchor GF-03)",
        "anchor": {
            "anchor_id": "GF-03",
            "title": "B300 field notes (independent practitioner): next-gen scale-up AllReduce",
            "source_row": "NONE YET — gap-fill anchors are staging-doc rows only "
            "(docs/calibration/anchors_gapfill.md §GF-03); the owner integrates "
            "accepted rows into the anchor registry; this "
            "stage made no handoff write",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-03",
            "urls": [
                "https://sixrackunits.substack.com/p/b300-field-notes-for-the-ai-infraperformance",
            ],
            "confidence": "M — independent, methodology context light (rank count, "
            "NCCL version not cleanly captured); a corroboration point, not a "
            "primary series; re-verify numbers and config at integration "
            "(staging-doc flag, carried not resolved)",
            "measured_system": "NCCL allreduce/broadcast and nvbandwidth on a B300 "
            "(Blackwell Ultra, NVLink-5-class) system; independent engineer's "
            "blog; partial paywall possible",
        },
        "targets": {
            "o_cct_cct_row": {
                "role": "the anchor's only CCT-vs-CCT target: 2 MiB AllReduce "
                "'in as little as 42-52 us' — CALIBRATABLE as a band point on "
                "the post-NVL72 generation",
            },
            "o_cct_large_message_plateau": {
                "role": "the measured allreduce peak 837 GB/s (93% of its own "
                "900 theoretical) — CALIBRATABLE as effective-B placement via "
                "the declared busbw->CCT conversion (no staged size; the "
                "gap-fill doc's role: extends CAL-A3's GB200 series by one "
                "generation — its 0.93 sits inside CAL-A3's 0.8755..1.00771 band)",
            },
            "injection_derating": {
                "role": "measured/spec derating points for the NVLink-5 class "
                "(0.93 allreduce, 0.758 broadcast, 0.797/0.869 nvbandwidth uni, "
                "0.75/0.783 bidir) pairing with CAL-A12 (~0.80 NVLink-3) and "
                "GF-01 (0.712 xGMI)",
            },
            "latency_axis": {
                "role": "measured D2D microbenchmark latency ~1.6 us (+ PCIe "
                "~1.4 us) for the plan's weakest axis (gap §4.2) — placement "
                "arithmetic only; GF-10/GF-11 own the latency-axis stages",
            },
        },
        "headline_reconciliation": headline_reconciliation(),
        "derating_arithmetic": derating_arithmetic(),
        "model": {
            "backends_executed": [
                "analytical_l0 (ring; per-link reading at CAL-A1's 50 B/ns)",
                "analytical_l0_crossbar (aggregate readings at 4 anchor points)",
                "analytical_l0_recursive_doubling (aggregate reading at 900; "
                "sweep path only — stage A7's gate finding)",
            ],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 14L ; B=50 (CAL-A1 NVLink5 per-link)",
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; B in {717, 782, 837, 900}",
                "doubling": "t = 2(r-1)/r*M/B + 6L ; B=900",
            },
            "free_parameters": {
                "B_values_and_provenance": {
                    "717": "anchor's nvbandwidth unidirectional D2D quote (lower)",
                    "782": "anchor's nvbandwidth unidirectional D2D quote (higher)",
                    "837": "anchor's MEASURED allreduce peak (baseline of the plateau sweep)",
                    "900": "anchor's own 'theoretical' quote (= CAL-A2's line = CAL-A1's 18x50)",
                    "50": "CAL-A1/A2 per-link per-direction arithmetic (the ring reading)",
                },
                "L_ns": 200,
                "L_provenance": "A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry points "
                "(KEEP — the stage measures where the registry point sits "
                "relative to the measured D2D latency point, 8.0x above it; it "
                "does not move it; implied-L diagnostics are declared "
                "arithmetic, never parameter values)",
                "no_tuning_statement": "every B was fixed by the anchor's own "
                "staged numbers / cross-anchor arithmetic BEFORE any model "
                "output was read; the comparison outcomes (D2D below peak, "
                "no-combination gap at 2 MiB) are recorded, not selected — no "
                "shipped manifest or topology value changed",
            },
            "assumptions": "A-L0-BW/A-L0-FD/A-L0-DIV (ring); A-L0X-PORT/A-L0X-BW/"
            "A-L0X-LAT/A-L0X-DIV (crossbar — IN-DOMAIN single-port reading for "
            "the NVSwitch class, plan §2.1); A-L0D-POW2/A-L0D-STEP/A-L0D-BW/"
            "A-L0D-LAT/A-L0D-DIV (doubling) — all from experiments/vertical_slice/"
            "assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_CCT,
                    "aggregate reading (single-port crossbar at the anchor's "
                    "measured peak B=837) at the anchor's only staged CCT row "
                    "(2 MiB, 'as little as 42-52 us')",
                ),
                run_summary(
                    RUN_ID_PLATEAU,
                    "aggregate reading at the anchor's theoretical B=900 (= the "
                    "CAL-A2 line) at the DECLARED 16 GiB plateau probe — lands "
                    "-7.00% below the converted 837 reference: the anchor's own "
                    "93% derating made model-exact",
                ),
            ],
            "band": comparison_band(),
            "plateau": comparison_plateau(),
            "latency_axis": latency_axis(),
        },
        "ambiguities": ambiguities(),
        "deviation": {
            "summary": "CCT row (2 MiB): every aggregate-reading chain sits "
            "8.0-11.6x BELOW the measured 42-52 us band while the per-link ring "
            "overshoots 1.47-1.81x — none of the 30 constructible "
            "(chain, B, L) combinations from the anchor's own numbers reaches "
            "the band (largest below 27,518.6 ns = ring at B=717, L=1,600; "
            "smallest above 73,800.3 ns = crossbar at B=50, L=200): "
            "an algorithm/software floor inexpressible at L0; implied effective "
            "B collapses 9.5-11.8x below the 837 plateau (stage A3's "
            "size-dependent-B class, measured mid-size on the newest "
            "generation). Plateau: the theoretical reading sits -7.00% below "
            "the converted measured reference (= the anchor's own 93% derating, "
            "model-exact), the D2D readings +7.03%/+16.74% above it (slower), "
            "the measured-peak baseline +0.001% (its 2L term only), ring "
            "per-link 16.74x above; the measured collective peak EXCEEDS both "
            "measured single-pair D2D readings — microbenchmark-underpredicts-"
            "collective, opposite direction from GF-01's bracket",
            "cct_deviation_vs_anchor": "DEFINED at the 2 MiB band (the only "
            "staged CCT row) and at the plateau via the declared busbw->CCT "
            "conversion (no staged size — probe-size-independent to closed "
            "form); UNDEFINED for broadcast (no L0 identity) and for the "
            "bidirectional D2D quotes (no bidirectional identity)",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, "
            "content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external "
            "published MEASUREMENT (independent practitioner blog) — not our "
            "testbed, no E3/E4 language; owner adjudication required",
        },
        "backing": {
            "run_ids": [RUN_ID_CCT, RUN_ID_PLATEAU],
            "sweep_ids": [SWEEP_ID_BAND, SWEEP_ID_PLATEAU],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_BAND}",
                f"results/sweeps/{SWEEP_ID_PLATEAU}",
            ],
            "run_backed_numbers": "every model output in comparison.* (2 store "
            "runs + 54 executed sweep configs); all 54 rows cross-checked "
            "against the closed-form identities by exact Fraction string "
            "equality; implied-B, implied-L, derating ratios, no-combination "
            "arithmetic, CAL-A3 containment, and the D2D-vs-peak ordering are "
            "declared anchor-anchor arithmetic with no run ids",
            "inputs": [
                "experiments/calibration/gf03/run_gf03_cct_anchor_v1.yaml",
                "experiments/calibration/gf03/run_gf03_plateau_spec_v1.yaml",
                "experiments/calibration/gf03/sweep_gf03_band_v1.yaml",
                "experiments/calibration/gf03/sweep_gf03_plateau_v1.yaml",
                "experiments/calibration/gf03/topologies/ (6 files)",
                "experiments/calibration/gf03/profiles/ (1 file)",
                "experiments/calibration/gf03/workloads/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf03/run_gf03_cct_anchor_v1.yaml ; "
            "make run EXP=experiments/calibration/gf03/run_gf03_plateau_spec_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf03/sweep_gf03_band_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf03/sweep_gf03_plateau_v1.yaml ; "
            "python experiments/calibration/gf03/build_calibration_record.py",
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
