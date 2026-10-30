"""Build the PROPOSED calibration FIT record for stage S3 (group G2).

Stage S3 fits anchor-group G2 per the immutable split record ``3862e227…``
(committed at ``experiments/calibration/split/anchor_split_v1.json`` and the
S2 handoff ``docs/away/2026-10-30-program/reports/p1_stage2.md`` §8):

- **CAL-A6** (noise-floor anchor, DEGENERATE split): the fit objective
  touches BOTH staged endpoint sizes {1 GiB, 16 GiB} of EACH NCCL version
  (2.19.3, 2.20.3) — the split record's within_series rule: two endpoints,
  no within-series holdout exists; the version pair itself measures the
  noise floor. Targets are the anchor's staged TIMES (the 2.20.3 quoted
  busbw rows are quarantined as internally inconsistent by stage A6 and
  are never used as targets).
- **GF-02** (DEGENERATE split): the fit signal is the single saturation
  band 128 MiB-16 GiB at plateau busbw ~360 GB/s; every band payload is
  fit-side (a within-series split would hold out noise).
- **GF-04**: the fit objective touches the 8-GPU single-node point ONLY;
  the 16-GPU two-node point is HELD OUT on the multi-rank scaling
  dimension ("the scaling dimension is validated, not fitted") and is
  reported as held-out error at the fitted B, never fitted. Mechanical
  fence: NO r=16 topology enters any S3 sweep; the stage's sole r=16
  execution is the declared held_out:true reporting run.
- The GF-02-vs-GF-04 360-vs-476.37 GB/s counting-convention/audit duty
  (split record, group G2 note) is executed and classified here.

"Fit" under the program fence means: sweep the DECLARED free-parameter
ranges (A-L0-BW and A-L0X-BW, registry value 64, range [1, 1024] B/ns)
against the group's published numbers, report exact deviations and
ranges, and record the fitted configurations as DIAGNOSTICS — we report
where the model sits; we never tune a shipped value toward an anchor.
Where the model misses (the held-out 16-GPU point), the miss IS the
finding (a known-omission candidate). No holdout anchor (the split's
four, plus blocked GF-06) is read by any objective, swept value, or
tolerance here. Sole split-record exception, used only as
tolerance-SHAPE context: CAL-A4's ~5% scalar (plan §3.4).

Pure function of immutable artifacts: committed inputs (this directory),
the three executed sweep tables, and the six store run records this stage
produced — all deterministically reproducible via the documented commands
(identical manifests + code => identical content addresses). Every derived
quantity is recomputed with exact Fractions; every cross-check is an exact
string-equality assert (a mismatch is a bug, not a finding). No wall-clock,
no host metadata: identical inputs reproduce byte-identical records.

Outputs: an append-only store copy under ``results/calibration/<record_id>/
record.json`` and the committed immutability anchor
``experiments/calibration/s3/fit_record_v1.json`` (byte-identical;
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

from essun.backends.analytical import l0
from essun.backends.analytical import l0_phase_collectives
from essun.backends.analytical.l0 import load_infra
from essun.backends.analytical.l0_crossbar import load_crossbar_config
from essun.contracts import REPO_ROOT, load_yaml
from essun.evidence.dimensions import dimensions_problems
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses; identical manifests + code reproduce
# them, so replay reproduces this record byte-identically).
# ---------------------------------------------------------------------------
SWEEP_ID_A6 = "26e275b7b3697b6f6640471e05fa0439ba122d3ee609f7ed5ba13c77842ed834"
SWEEP_ID_GF02 = "13bc507205108c718f06e836bf003f71d2ce84a8b02e8cec19e0d7ee6c8dab9c"
SWEEP_ID_GF04 = "96b91ab6dd42b5e084a17ff56b35694e29e5526b4de13b0a9298df2736002499"
RUN_ID_A6_2193 = "ad7e937c83882b2bf0d117838a5d9a25e136a8a8f609a1f085eead5b2158e450"
RUN_ID_A6_2203 = "7d7624054d2777655dd36a0ce0d620129e744d550f3c09a960c1f767134299d8"
RUN_ID_GF02_AR = "ffdd546d3a7a12342680808c1f56bb7eb9f3dcad6e9ecb7207c9f3a3b0bc43fb"
RUN_ID_GF02_AG = "96d480731cd2017be8d251f04c357e5a2739b9f62846b4e64fbb19254836fd17"
RUN_ID_GF04_FIT = "5af31f3b51ef54579371fcc4ae643cf567ebd900388d6cc2162da1c6904ad3d4"
RUN_ID_GF04_HOLD = "ed77cce301ef938c5497e936904c01ce9665b1885099fd568e0f006a61ee2b48"
SPLIT_RECORD_ID = "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20"

RESULTS = REPO_ROOT / "results"
COMMITTED_COPY = REPO_ROOT / "experiments" / "calibration" / "s3" / "fit_record_v1.json"
S3_DIR = REPO_ROOT / "experiments" / "calibration" / "s3"

# ---------------------------------------------------------------------------
# Anchor staged numbers (transcription sources: stage builders committed at
# experiments/calibration/{a6,gf02,gf04}/; staging docs anchors_staging.md
# §A6 and anchors_gapfill.md §GF-02/§GF-04). Units: times us, busbw GB/s
# decimal (1 GB/s = 1 B/ns); sizes binary GiB/MiB. Nothing else is read.
# ---------------------------------------------------------------------------
R32 = 32          # CAL-A6 ranks (4 nodes x 8 H100)
R8 = 8            # GF-02 / GF-04 single-node ranks
L_NS = Fraction(200)   # A-L0-LAT / A-L0X-LAT registry points (KEEP; S4 owns the axis)

A6_SIZES = (1 << 30, 1 << 34)               # 1 GiB, 16 GiB (both fit-side; degenerate)
A6_T19 = {1 << 30: Fraction("5397.8") * 1000, 1 << 34: Fraction("85110") * 1000}
A6_T20 = {1 << 30: Fraction("5692.2") * 1000, 1 << 34: Fraction("86981") * 1000}
A6_FACTOR = Fraction(2 * (R32 - 1), R32)    # 62/32 (carried by both sides; cancels)
A6_CHAIN = 2 * (R32 - 1) * L_NS             # 12400 ns

GF02_BAND = (1 << 27, 1 << 30, 1 << 34)     # 128 MiB, 1 GiB, 16 GiB (all fit-side)
GF02_PLATEAU = Fraction(360)                # anchor's own plateau (busbw = B pinned mapping)
GF02_PERDIR = Fraction(450)                 # the poster's 900/2 physical split
GF04_B8 = Fraction("476.37")                # 8-GPU single-node summary busbw (the FIT point)
GF04_B16 = Fraction("469.67")               # 16-GPU two-node summary busbw (HELD OUT)
GF04_M_COMMON = 1 << 32                     # largest size common to both ladders
GF04_FIT_SIZES = (1 << 30, GF04_M_COMMON, 1 << 33)   # the executed r=8 sweep sizes

AR8_FACTOR = Fraction(2 * (R8 - 1), R8)     # 7/4 — allreduce wire factor at r=8
AG8_FACTOR = Fraction(R8 - 1, R8)           # 7/8 — allgather (result-basis) factor
GF04_FACTOR8 = AR8_FACTOR
GF04_FACTOR16 = Fraction(2 * 15, 16)        # 15/8

# Free-parameter registries (unchanged by this stage).
REGISTRY_VALUE = 64
REGISTRY_RANGE = (1, 1024)

# Exact fitted values (asserted against the closed forms below).
B_FIT_A6_2193 = Fraction(111478703128576, 286778506025)     # ~= 388.7275 B/ns
B_FIT_A6_2203 = Fraction(115757383942144, 309086671475)     # ~= 374.5143 B/ns
B_FIT_GF02 = GF02_PLATEAU                                   # degenerate: 360 exactly
B_FIT_GF04 = GF04_B8                                         # degenerate: 476.37 exactly

A6_FIT_TOPO_2193 = "experiments/calibration/s3/topologies/ring32_s3_fitb19_v1.yaml"
A6_FIT_TOPO_2203 = "experiments/calibration/s3/topologies/ring32_s3_fitb20_v1.yaml"

# Swept topology sets of the three executed sweeps (repo-relative).
A6_SWEEP_TOPOS = [
    ("experiments/calibration/s3/topologies/ring32_s3_b64_v1.yaml", "grid: 64=64x1"),
    ("experiments/calibration/s3/topologies/ring32_s3_b128_v1.yaml", "grid: 128=64x2"),
    ("experiments/calibration/s3/topologies/ring32_s3_b192_v1.yaml", "grid: 192=64x3"),
    ("experiments/calibration/s3/topologies/ring32_s3_b256_v1.yaml", "grid: 256=64x4"),
    ("experiments/calibration/a6/topologies/ring32_a6_derated320_v1.yaml",
     "grid+anchor: 320=64x5 AND the CAL-A12 ~80% derated-rail provenance point"),
    ("experiments/calibration/s3/topologies/ring32_s3_b384_v1.yaml", "grid: 384=64x6"),
    ("experiments/calibration/s3/topologies/ring32_s3_b448_v1.yaml", "grid: 448=64x7"),
    ("experiments/calibration/s3/topologies/ring32_s3_b512_v1.yaml", "grid: 512=64x8"),
    ("experiments/calibration/s3/topologies/ring32_s3_b576_v1.yaml", "grid: 576=64x9"),
    ("experiments/calibration/s3/topologies/ring32_s3_b640_v1.yaml", "grid: 640=64x10"),
    ("experiments/calibration/s3/topologies/ring32_s3_b704_v1.yaml", "grid: 704=64x11"),
    ("experiments/calibration/s3/topologies/ring32_s3_b768_v1.yaml", "grid: 768=64x12"),
    ("experiments/calibration/s3/topologies/ring32_s3_b832_v1.yaml", "grid: 832=64x13"),
    ("experiments/calibration/s3/topologies/ring32_s3_b896_v1.yaml", "grid: 896=64x14"),
    ("experiments/calibration/s3/topologies/ring32_s3_b960_v1.yaml", "grid: 960=64x15"),
    ("experiments/calibration/s3/topologies/ring32_s3_b1024_v1.yaml", "grid: 1024=64x16 (declared-range upper endpoint)"),
    ("experiments/calibration/a6/topologies/ring32_a6_port25_v1.yaml",
     "anchor-config: 25 = one 200 Gbps RoCEv2 port per direction (per-port endpoint)"),
    ("experiments/calibration/a6/topologies/ring32_a6_rail400_v1.yaml",
     "anchor-config: 400 = the staged 16x200Gbps per-node rail aggregate (the anchor point)"),
]
GF02_SWEEP_TOPOS = [
    ("experiments/calibration/s3/topologies/crossbar8_s3_b64_v1.yaml", "grid: 64=64x1"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b128_v1.yaml", "grid: 128=64x2"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b192_v1.yaml", "grid: 192=64x3"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b256_v1.yaml", "grid: 256=64x4"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b320_v1.yaml", "grid: 320=64x5"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b384_v1.yaml", "grid: 384=64x6"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b448_v1.yaml", "grid: 448=64x7"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b512_v1.yaml", "grid: 512=64x8"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b576_v1.yaml", "grid: 576=64x9"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b640_v1.yaml", "grid: 640=64x10"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b704_v1.yaml", "grid: 704=64x11"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b768_v1.yaml", "grid: 768=64x12"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b832_v1.yaml", "grid: 832=64x13"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b896_v1.yaml", "grid: 896=64x14"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b960_v1.yaml", "grid: 960=64x15"),
    ("experiments/calibration/s3/topologies/crossbar8_s3_b1024_v1.yaml", "grid: 1024=64x16 (declared-range upper endpoint)"),
    ("experiments/calibration/gf02/topologies/crossbar8_gf02_plateau360_v1.yaml",
     "anchor: 360 = the anchor's measured plateau (the degenerate FIT value)"),
    ("experiments/calibration/gf02/topologies/crossbar8_gf02_perdir450_v1.yaml",
     "anchor: 450 = the poster's own 900/2 physical per-direction split"),
    ("experiments/calibration/gf02/topologies/crossbar8_gf02_gf04_476_37_v1.yaml",
     "anchor: 476.37 = GF-04's figure (this group's OPEN 360-vs-476 audit bracket)"),
    ("experiments/calibration/gf02/topologies/crossbar8_gf02_bidir900_v1.yaml",
     "anchor: 900 = the bidirectional-misread hazard bracket (never a bridge)"),
]
GF04_SWEEP_TOPOS = [
    ("experiments/calibration/s3/topologies/ring8_s3_b64_v1.yaml", "grid: 64=64x1"),
    ("experiments/calibration/s3/topologies/ring8_s3_b128_v1.yaml", "grid: 128=64x2"),
    ("experiments/calibration/s3/topologies/ring8_s3_b192_v1.yaml", "grid: 192=64x3"),
    ("experiments/calibration/s3/topologies/ring8_s3_b256_v1.yaml", "grid: 256=64x4"),
    ("experiments/calibration/s3/topologies/ring8_s3_b320_v1.yaml", "grid: 320=64x5"),
    ("experiments/calibration/s3/topologies/ring8_s3_b384_v1.yaml", "grid: 384=64x6"),
    ("experiments/calibration/s3/topologies/ring8_s3_b448_v1.yaml", "grid: 448=64x7"),
    ("experiments/calibration/s3/topologies/ring8_s3_b512_v1.yaml", "grid: 512=64x8"),
    ("experiments/calibration/s3/topologies/ring8_s3_b576_v1.yaml", "grid: 576=64x9"),
    ("experiments/calibration/s3/topologies/ring8_s3_b640_v1.yaml", "grid: 640=64x10"),
    ("experiments/calibration/s3/topologies/ring8_s3_b704_v1.yaml", "grid: 704=64x11"),
    ("experiments/calibration/s3/topologies/ring8_s3_b768_v1.yaml", "grid: 768=64x12"),
    ("experiments/calibration/s3/topologies/ring8_s3_b832_v1.yaml", "grid: 832=64x13"),
    ("experiments/calibration/s3/topologies/ring8_s3_b896_v1.yaml", "grid: 896=64x14"),
    ("experiments/calibration/s3/topologies/ring8_s3_b960_v1.yaml", "grid: 960=64x15"),
    ("experiments/calibration/s3/topologies/ring8_s3_b1024_v1.yaml", "grid: 1024=64x16 (declared-range upper endpoint)"),
    ("experiments/calibration/gf02/topologies/ring8_gf02_perdir450_v1.yaml",
     "anchor: 450 = physical per-direction NVLink ceiling (GF-02 poster arithmetic)"),
    ("experiments/calibration/gf04/topologies/ring8_gf04_anchor476_37_v1.yaml",
     "anchor: 476.37 = the anchor's own single-node figure (the degenerate FIT value)"),
    ("experiments/calibration/gf02/topologies/ring8_gf02_plateau360_v1.yaml",
     "anchor: 360 = GF-02's plateau (this group's OPEN 360-vs-476 audit bracket)"),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Closed-form identities (the same functions the backends execute).
# ---------------------------------------------------------------------------
def ring_time(payload: int, b: Fraction, ranks: int) -> Fraction:
    return l0.ring_allreduce_time_ns(payload, ranks, _ring_config(b, ranks))


def _ring_config(b: Fraction, ranks: int) -> l0.InfraConfig:
    return l0.InfraConfig(
        topology_id="cal_s3_closed_form", ranks=ranks,
        link_bytes_per_ns=b, hop_latency_ns=L_NS,
    )


def _xbar_config(b: Fraction):
    from essun.backends.analytical.l0_crossbar import CrossbarConfig

    return CrossbarConfig(
        topology_id="cal_s3_closed_form", ranks=R8,
        injection_bytes_per_ns=b, pair_latency_ns=L_NS,
    )


def xbar_time(payload: int, b: Fraction) -> Fraction:
    from essun.backends.analytical.l0_crossbar import crossbar_allreduce_time_ns

    return crossbar_allreduce_time_ns(payload, R8, _xbar_config(b))


def ag_ring_time(m_total: int, b: Fraction) -> Fraction:
    return l0_phase_collectives.ring_allgather_time_ns(
        m_total, R8, _ring_config(b, R8)
    )


def pct(x: Fraction) -> float:
    return float(x * 100)


def topo_b(path: str) -> Fraction:
    data = load_yaml(REPO_ROOT / path)
    if data.get("topology_class") == "fully_connected_crossbar":
        return load_crossbar_config(data).injection_bytes_per_ns
    return load_infra(data).link_bytes_per_ns


def sweep_b_map(sweep_topos: list[tuple[str, str]]) -> dict[str, Fraction]:
    return {path: topo_b(path) for path, _ in sweep_topos}


# ---------------------------------------------------------------------------
# 1. CAL-A6 fit: exact two-point minimax per NCCL version (degenerate split).
# ---------------------------------------------------------------------------
def a6_minimax(times: dict[int, Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    """Exact fixed-B minimax over the two staged sizes.

    dev_i(B) = (a_i/B + c)/t_i - 1 with a_i = 2(r-1)/r*M_i, c = 2(r-1)L;
    the optimum is interior where dev_1 = -dev_2:
        B* = (a1*t2 + a2*t1) / (2*t1*t2 - c*(t1+t2)).
    A deterministic Fraction scan verifies no grid point beats it.
    """
    (m1, t1), (m2, t2) = sorted(times.items())
    a1, a2 = A6_FACTOR * m1, A6_FACTOR * m2
    c = A6_CHAIN
    b_star = (a1 * t2 + a2 * t1) / (2 * t1 * t2 - c * (t1 + t2))
    d1 = (a1 / b_star + c) / t1 - 1
    d2 = (a2 / b_star + c) / t2 - 1
    assert d1 == -d2, (d1, d2)
    best = abs(d1)
    for i in range(1, 20001):
        b = Fraction(25) + Fraction(375) * Fraction(i, 20000)
        worst = max(abs((a1 / b + c) / t1 - 1), abs((a2 / b + c) / t2 - 1))
        assert worst >= best
    return b_star, d1, d2


def a6_dev(b: Fraction, payload: int, t: Fraction) -> Fraction:
    return ring_time(payload, b, R32) / t - 1


def window(pairs: list[tuple[Fraction, Fraction, Fraction]], tau: Fraction) -> dict:
    """Tolerance-shape window over B: {B : max_i |dev_i(B)| <= tau}, where
    pairs are (wire_i, c_i, ref_i) and dev_i(B) = (wire_i/B + c_i)/ref_i - 1."""
    lo = max(w / ((1 + tau) * ref - c) for w, c, ref in pairs)
    hi = min(w / ((1 - tau) * ref - c) for w, c, ref in pairs)
    assert 0 < lo < hi, (lo, hi)
    return {
        "B_low_exact": str(lo), "B_low_float": float(lo),
        "B_high_exact": str(hi), "B_high_float": float(hi),
        "width_float": float(hi - lo),
    }


def grid_members_inside(win: dict, grid_bs: list[Fraction]) -> list[str]:
    lo, hi = Fraction(win["B_low_exact"]), Fraction(win["B_high_exact"])
    return [str(b) for b in grid_bs if lo <= b <= hi]


def cal_a6_fit() -> dict:
    b19, d19a, d19b = a6_minimax(A6_T19)
    b20, d20a, d20b = a6_minimax(A6_T20)
    assert b19 == B_FIT_A6_2193, (b19, B_FIT_A6_2193)
    assert b20 == B_FIT_A6_2203, (b20, B_FIT_A6_2203)
    assert Fraction(1) < b19 < Fraction(1024) and Fraction(1) < b20 < Fraction(1024)

    def per_size(b: Fraction, times: dict[int, Fraction]) -> list[dict]:
        rows = []
        for m in A6_SIZES:
            label = "1 GiB" if m == 1 << 30 else "16 GiB"
            r = a6_dev(b, m, times[m])
            rows.append({
                "size": label,
                "payload_bytes": m,
                "anchor_cct_ns_exact": str(times[m]),
                "model_cct_ns_exact": str(ring_time(m, b, R32)),
                "ratio_model_over_anchor_exact": str(r + 1),
                "delta_pct_float": pct(r),
                "anchor_implied_effective_B_exact": str(
                    A6_FACTOR * m / (times[m] - A6_CHAIN)
                ),
            })
        return rows

    wire_c_ref = lambda times: [
        (A6_FACTOR * m, A6_CHAIN, times[m]) for m in A6_SIZES
    ]
    win5_19 = window(wire_c_ref(A6_T19), Fraction(5, 100))
    win8_19 = window(wire_c_ref(A6_T19), Fraction(8, 100))
    win5_20 = window(wire_c_ref(A6_T20), Fraction(5, 100))
    win8_20 = window(wire_c_ref(A6_T20), Fraction(8, 100))
    grid_bs = [topo_b(p) for p, prov in A6_SWEEP_TOPOS if prov.startswith("grid")]
    grid_bs = sorted(set(grid_bs) | {Fraction(320)})   # 320 = grid member riding the a6 topology

    return {
        "identity": "t = 2*(r-1)/r*M/B + 2*(r-1)*L at r=32, L=200 ns "
                    "(l0.ring_allreduce_time_ns); targets = the anchor's staged TIMES",
        "split_role": "DEGENERATE per the split record: both endpoint sizes are "
                      "fit-side (no within-series holdout exists at two points); the "
                      "version pair itself measures the noise floor; the 2.20.3 "
                      "quoted busbw rows are quarantined (internally inconsistent "
                      "with their own times by -3.2%, stage A6) and never used",
        "series_2_19_3": {
            "minimax_B_exact": str(b19),
            "minimax_B_float": float(b19),
            "minimax_B_materialized_as": str(B_FIT_A6_2193) + " (carried by "
                + A6_FIT_TOPO_2193 + " — asserted equal)",
            "worst_case_deviation_pct": pct(max(abs(d19a), abs(d19b))),
            "binding": "both staged sizes (deviations exactly opposite)",
            "per_size_at_fitted_B": per_size(b19, A6_T19),
        },
        "series_2_20_3": {
            "minimax_B_exact": str(b20),
            "minimax_B_float": float(b20),
            "minimax_B_materialized_as": str(B_FIT_A6_2203) + " (carried by "
                + A6_FIT_TOPO_2203 + " — asserted equal)",
            "worst_case_deviation_pct": pct(max(abs(d20a), abs(d20b))),
            "binding": "both staged sizes (deviations exactly opposite)",
            "per_size_at_fitted_B": per_size(b20, A6_T20),
        },
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance is adopted (the E0 "
                      "zero-slack policy stands; a nonzero tolerance must arrive "
                      "through CGFR with recorded evidence, plan §3.4)",
            "tau_5pct": {
                "shape_provenance": "CAL-A4's ~5% validated mean-error SCALAR "
                    "admitted solely as tolerance-shape context per the split "
                    "record's sole recorded exception (plan §3.4; the anchor's "
                    "series and per-configuration errors are NOT fit inputs)",
                "series_2_19_3": {**win5_19, "uniform_grid_members_inside":
                                  grid_members_inside(win5_19, grid_bs)},
                "series_2_20_3": {**win5_20, "uniform_grid_members_inside":
                                  grid_members_inside(win5_20, grid_bs)},
            },
            "tau_8pct": {
                "shape_provenance": "upper edge of CAL-A6's measured 5-8% "
                    "software-version swing (this stage's own noise-floor anchor, "
                    "plan §3.4); a criterion tighter than the measured software "
                    "variance would be overfitting",
                "series_2_19_3": {**win8_19, "uniform_grid_members_inside":
                                  grid_members_inside(win8_19, grid_bs)},
                "series_2_20_3": {**win8_20, "uniform_grid_members_inside":
                                  grid_members_inside(win8_20, grid_bs)},
            },
            "note": "unlike S2 (no grid member inside the 5% window), the 64 B/ns "
                    "grid member 384 lies inside BOTH versions' 5% windows — the "
                    "hybrid series is flatter in effective-B than CAL-A3's ramp",
        },
        "L_sensitivity": {
            "chain_share_of_anchor_t_pct": {
                "2.19.3_1GiB": pct(A6_CHAIN / A6_T19[1 << 30]),
                "2.19.3_16GiB": pct(A6_CHAIN / A6_T19[1 << 34]),
            },
            "note": "0.23%-0.015% — bandwidth-bound; the latency axis is stage "
                    "S4's; no L degree of freedom is fitted here",
        },
    }


def noise_floor_execution() -> dict:
    """The anchor's PRIMARY role, executed on the parameter axis by this fit."""
    b19, b20 = B_FIT_A6_2193, B_FIT_A6_2203
    separation = b20 / b19 - 1
    t19_1g, t20_1g = A6_T19[1 << 30], A6_T20[1 << 30]
    t19_16g, t20_16g = A6_T19[1 << 34], A6_T20[1 << 34]
    swing_time_1g = t20_1g / t19_1g - 1
    swing_time_16g = t20_16g / t19_16g - 1
    assert pct(separation) < -3.6 and pct(separation) > -3.7
    assert pct(swing_time_1g) > 5.4 and pct(swing_time_16g) < 2.3
    return {
        "question": "what does the anchor's software-version noise floor look "
                    "like on the FITTED-parameter axis?",
        "fitted_B_separation_2203_over_2193_exact": str(separation),
        "fitted_B_separation_pct": pct(separation),
        "in_fit_worst_case_residuals_pct": {
            "2.19.3": pct(max(abs(a6_dev(b19, m, A6_T19[m])) for m in A6_SIZES)),
            "2.20.3": pct(max(abs(a6_dev(b20, m, A6_T20[m])) for m in A6_SIZES)),
        },
        "anchor_time_swings_pct": {"1GiB": pct(swing_time_1g), "16GiB": pct(swing_time_16g)},
        "finding": "the two fitted-B values differ by -3.66% — the software-version "
                   "movement, moved onto the free-parameter axis by fitting each "
                   "version's times exactly. The L0 input space carries no "
                   "software-version parameter (structural, stage A6), so this "
                   "separation is a LOWER bound on any B-reading ambiguity a "
                   "hybrid-rail comparison must absorb: it exceeds the 2.19.3 "
                   "fit's own worst-case residual (0.62%) by ~6x and is comparable "
                   "to the 2.20.3 fit residual (2.19%). A B quoted for this "
                   "regime without an NCCL pin is software-state-dependent to at "
                   "least this degree — recorded, never tuned",
        "placement_of_fitted_Bs_vs_config_ceilings": {
            "B_fit_2193_over_rail400_pct": pct(b19 / Fraction(400)),
            "B_fit_2203_over_rail400_pct": pct(b20 / Fraction(400)),
            "B_fit_2193_over_derated320_pct": pct(b19 / Fraction(320)),
            "note": "the fitted effective B sits at 94-97% of the anchor's own "
                    "400 B/ns rail arithmetic (the measurement never fully reaches "
                    "config arithmetic; CAL-A12's 320 derated bridge is 17-21% "
                    "below both fitted values — pessimistic here, as stage A6 "
                    "recorded)",
        },
    }


# ---------------------------------------------------------------------------
# 2. GF-02 fit: degenerate band fit (B = the plateau) + residuals.
# ---------------------------------------------------------------------------
def gf02_fit() -> dict:
    b = B_FIT_GF02
    ar_residuals = {}
    for m in GF02_BAND:
        ref = AR8_FACTOR * m / GF02_PLATEAU       # anchor-implied reference CCT
        model = xbar_time(m, b)
        residual = model / ref - 1
        assert residual == (2 * L_NS) / ref       # exactly the +2L registry term
        ar_residuals[f"{m}"] = {
            "payload_bytes": m,
            "size_label": {1 << 27: "128 MiB (band bottom)", 1 << 30: "1 GiB (in-band)",
                            1 << 34: "16 GiB (band top)"}[m],
            "anchor_implied_reference_ns_exact": str(ref),
            "model_cct_ns_exact": str(model),
            "residual_exact": str(residual),
            "residual_pct": pct(residual),
        }
    # allgather twin: same fitted B on the phase-collectives identity
    m_total = 8 * (1 << 34)
    ag_ref = AG8_FACTOR * m_total / GF02_PLATEAU
    ag_model = ag_ring_time(m_total, b)
    ag_residual = ag_model / ag_ref - 1
    assert ag_residual == (7 * L_NS) / ag_ref

    # tolerance-shape windows across the band (allreduce identity)
    pairs = [(AR8_FACTOR * m, 2 * L_NS, AR8_FACTOR * m / GF02_PLATEAU) for m in GF02_BAND]
    win5 = window(pairs, Fraction(5, 100))
    win8 = window(pairs, Fraction(8, 100))
    grid_bs = sorted({topo_b(p) for p, prov in GF02_SWEEP_TOPOS if prov.startswith("grid")})

    return {
        "identity": "allreduce crossbar t = 2(r-1)/r*M/B + 2L at r=8 (plus the "
                    "allgather ring twin t = (r-1)/r*M_total/B + (r-1)L = +1400 ns, "
                    "A-L0P-MSG); "
                    "mapping pinned from nccl-tests source by stage GF-02's fetch: "
                    "busbw = algbw x 2(r-1)/r, algbw = M/t => asymptotic busbw IS B",
        "split_role": "DEGENERATE per the split record: a single saturation band "
                      "(128 MiB-16 GiB); every band payload is fit-side; a "
                      "within-series split would hold out noise",
        "degeneracy": "the fit has ZERO residual degrees of freedom: under the "
                      "pinned mapping the fitted B equals the anchor's own plateau "
                      "reading 360 exactly; the residual at every band size is the "
                      "fixed latency term ONLY",
        "fitted_B_exact": str(b),
        "fitted_B_float": float(b),
        "fitted_B_materialized_as": "the committed stage-GF-02 plateau topology "
            "(crossbar8_gf02_plateau360_v1.yaml / ring8_gf02_plateau360_v1.yaml)",
        "allreduce_residuals_across_band": ar_residuals,
        "allgather_twin_residual": {
            "m_total_gathered_bytes": m_total,
            "anchor_implied_reference_ns_exact": str(ag_ref),
            "model_cct_ns_exact": str(ag_model),
            "residual_exact": str(ag_residual),
            "residual_pct": pct(ag_residual),
            "statement": "the anchor states its plateau for BOTH collectives; the "
                         "same fitted B lands on the allgather identity with the "
                         "same pure-latency residual — one B point, two "
                         "collectives, as staged",
        },
        "worst_band_residual_pct": max(r["residual_pct"] for r in ar_residuals.values()),
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance is adopted (E0 zero-slack "
                      "stands, plan §3.4)",
            "tau_5pct": {
                "shape_provenance": "the 5% tolerance-shape scalar as admitted "
                    "solely as context per the split record's single recorded "
                    "exception (identical role and provenance as the CAL-A6 "
                    "section's window above — see fits.cal_a6.tolerance_shape_"
                    "windows.tau_5pct.shape_provenance)",
                **win5,
                "uniform_grid_members_inside": grid_members_inside(win5, grid_bs),
            },
            "tau_8pct": {
                "shape_provenance": "upper edge of CAL-A6's measured 5-8% "
                    "software-version swing (this stage's noise-floor anchor)",
                **win8,
                "uniform_grid_members_inside": grid_members_inside(win8, grid_bs),
            },
            "note": "no uniform 64 B/ns grid member lies inside the 5% window "
                    "(384 misses it from above); the exact boundaries are the "
                    "finding, the grid is the anchor-blind sampling instrument "
                    "(same posture as S2)",
        },
    }


# ---------------------------------------------------------------------------
# 3. GF-04 fit: degenerate one-point fit (8-GPU) + the held-out 16-GPU report.
# ---------------------------------------------------------------------------
def gf04_fit() -> dict:
    b = B_FIT_GF04
    # fit-point residual at the common ladder member (r=8)
    ref8 = GF04_FACTOR8 * GF04_M_COMMON / GF04_B8
    model8 = ring_time(GF04_M_COMMON, b, R8)
    residual8 = model8 / ref8 - 1
    assert residual8 == (14 * L_NS) / ref8        # exactly the +14L registry term

    # executed r=8 sweep sizes residuals (the summary figure is the reference at
    # every ladder size; plateau-flatness caveat recorded by stage GF-04)
    sweep_residuals = {}
    for m in GF04_FIT_SIZES:
        ref = GF04_FACTOR8 * m / GF04_B8
        sweep_residuals[str(m)] = {
            "payload_bytes": m,
            "anchor_implied_reference_ns_exact": str(ref),
            "model_cct_ns_exact": str(ring_time(m, b, R8)),
            "residual_pct": pct(ring_time(m, b, R8) / ref - 1),
        }

    pairs = [(GF04_FACTOR8 * m, 14 * L_NS, GF04_FACTOR8 * m / GF04_B8) for m in GF04_FIT_SIZES]
    win5 = window(pairs, Fraction(5, 100))
    win8 = window(pairs, Fraction(8, 100))
    grid_bs = sorted({topo_b(p) for p, prov in GF04_SWEEP_TOPOS if prov.startswith("grid")})

    return {
        "identity": "ring t = 2(r-1)/r*M/B + 2(r-1)*L at r=8, L=200 ns; mapping "
                    "pinned from nccl-tests source (stage GF-02's fetch): busbw = B",
        "split_role": "the fit objective touches the 8-GPU single-node point ONLY; "
                      "the 16-GPU two-node point is HELD OUT on the scaling "
                      "dimension (split record: 'the scaling dimension is "
                      "validated, not fitted'); no r=16 topology enters any S3 "
                      "sweep (mechanically asserted)",
        "degeneracy": "the one-point fit has ZERO residual degrees of freedom: "
                      "the fitted B equals the anchor's own summary figure 476.37 "
                      "exactly; the residual at the fit point is the fixed +14L "
                      "registry term ONLY",
        "fitted_B_exact": str(b),
        "fitted_B_float": float(b),
        "fitted_B_materialized_as": "the committed stage-GF-04 topology "
            "(ring8_gf04_anchor476_37_v1.yaml; the r=16 twin of the same B is "
            "ring16_gf04_anchor476_37_v1.yaml, used ONLY by the held-out run)",
        "fit_point_residual": {
            "payload_bytes": GF04_M_COMMON,
            "anchor_implied_reference_ns_exact": str(ref8),
            "model_cct_ns_exact": str(model8),
            "residual_exact": str(residual8),
            "residual_pct": pct(residual8),
        },
        "sweep_size_residuals": sweep_residuals,
        "summary_figure_caveat": "the fit target is the anchor's SUMMARY figure "
            "(per-size tables are images, not text-extractable); the "
            "anchor-implied reference at any ladder size is wire/476.37 — the "
            "aggregation ambiguity cannot move the executed ratio axis by more "
            "than the plateau's own flatness (stage GF-04's recorded caveat)",
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance is adopted (E0 zero-slack "
                      "stands, plan §3.4)",
            "tau_5pct": {
                "shape_provenance": "the 5% tolerance-shape scalar as admitted "
                    "solely as context per the split record's single recorded "
                    "exception (identical role and provenance as the CAL-A6 "
                    "section's window above — see fits.cal_a6.tolerance_shape_"
                    "windows.tau_5pct.shape_provenance)",
                **win5,
                "uniform_grid_members_inside": grid_members_inside(win5, grid_bs),
            },
            "tau_8pct": {
                "shape_provenance": "upper edge of CAL-A6's measured 5-8% "
                    "software-version swing (this stage's noise-floor anchor)",
                **win8,
                "uniform_grid_members_inside": grid_members_inside(win8, grid_bs),
            },
        },
    }


def gf04_held_out() -> dict:
    """The split record's within-series holdout: GF-04's 16-GPU two-node point,
    evaluated at the 8-GPU-fitted B (never fitted)."""
    b = B_FIT_GF04
    obs = load_json(RESULTS / RUN_ID_GF04_HOLD / "observations.json")
    run = load_json(RESULTS / RUN_ID_GF04_HOLD / "run.json")
    per_op = obs["per_op"][0]
    assert obs["model"]["ranks"] == 16
    assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == b
    assert Fraction(obs["model"]["hop_latency_ns_exact"]) == L_NS
    assert per_op["payload_bytes"] == GF04_M_COMMON
    assert per_op["completion_time_ns_exact"] == str(ring_time(GF04_M_COMMON, b, 16))
    assert per_op["per_rank_wire_bytes_exact"] == str(GF04_FACTOR16 * GF04_M_COMMON)
    assert run["held_out"]["held_out"] is True
    assert run["calibration_target"] == ["GF-04"]
    assert run["evidence_schema_version"] == 2

    ref16 = GF04_FACTOR16 * GF04_M_COMMON / GF04_B16     # the held-out reference
    model16 = ring_time(GF04_M_COMMON, b, 16)
    delta = model16 / ref16 - 1
    # pair view (the scaling axis): model CCT ratio vs anchor-implied ratio
    model_pair = model16 / ring_time(GF04_M_COMMON, b, R8)
    anchor_pair = (GF04_FACTOR16 / GF04_B16) / (GF04_FACTOR8 / GF04_B8)
    # model-side 8->16 busbw ratio (rank-invariance, the structural null)
    model_busbw16 = GF04_FACTOR16 * GF04_M_COMMON / model16
    model_busbw8 = GF04_FACTOR8 * GF04_M_COMMON / ring_time(GF04_M_COMMON, b, R8)
    measured_ratio = GF04_B16 / GF04_B8
    assert pct(delta) < -1.3 and pct(delta) > -1.4
    assert abs(pct(1 - measured_ratio) - 1.407) < 0.01

    return {
        "held_out_point": "GF-04's 16-GPU two-node leg (busbw 469.67 GB/s) on the "
                          "multi-rank scaling dimension, at the common ladder "
                          "member 2^32",
        "at": "the 8-GPU-fitted configuration B_fit = " + str(b) + " B/ns, UNCHANGED "
              "at r=16 (the scaling counterfactual)",
        "run_backing": {
            "run_id": RUN_ID_GF04_HOLD,
            "held_out_dimension": run["held_out"],
            "cct_ns_exact": per_op["completion_time_ns_exact"],
            "note": "the stage's ONLY r=16 execution; evaluation-only",
        },
        "anchor_implied_reference_ns_exact": str(ref16),
        "model_cct_ns_exact": str(model16),
        "ratio_model_over_anchor_exact": str(delta + 1),
        "delta_pct_float": pct(delta),
        "scaling_axis": {
            "measured_busbw_ratio_exact": str(measured_ratio),
            "measured_drop_pct": pct(1 - measured_ratio),
            "model_busbw_ratio_at_fixed_B_exact": str(model_busbw16 / model_busbw8),
            "model_cct_pair_exact": str(model_pair),
            "anchor_implied_cct_pair_exact": str(anchor_pair),
            "pair_residual_pct": pct(model_pair / anchor_pair - 1),
        },
        "finding": "the held-out deviation is -1.37% (the model at the fitted B "
                   "runs 1.37% FASTER than the measured 16-GPU leg): the single-B "
                   "identity is rank-count-invariant in busbw by construction "
                   "(model ratio 1 - 1.8e-4) while the anchor measures a -1.41% "
                   "drop — the 8->16 crossing cost (an inter-node RoCE leg "
                   "distinct from the intra-node fabric) is structurally "
                   "inexpressible in the uniform-B input space. THE MISS IS THE "
                   "FINDING (known-omission candidate: fabric asymmetry / "
                   "r-dependent effective bandwidth); nothing was tuned toward "
                   "this point — B_fit was fixed by the 8-GPU leg alone before "
                   "this evaluation existed",
        "in_scale_context": "the held-out miss (-1.37%) is inside the group's own "
                            "noise-floor context (CAL-A6's 5.45% version swing at "
                            "1 GiB) but is a DISTINCT, structural residual: it "
                            "does not move with software state, it moves with "
                            "rank count",
    }


# ---------------------------------------------------------------------------
# 4. The GF-02-vs-GF-04 360-vs-476.37 audit (the group's standing duty).
# ---------------------------------------------------------------------------
def gf02_gf04_audit() -> dict:
    ratio = GF04_B8 / GF02_PLATEAU
    perdir = GF02_PERDIR
    assert pct(GF02_PLATEAU / perdir - 1) == -20.0          # exactly 4/5 of 450
    assert pct(GF04_B8 / perdir - 1) > 5.8 and pct(GF04_B8 / perdir - 1) < 5.9
    assert pct(ratio - 1) > 32.3 and pct(ratio - 1) < 32.4
    return {
        "duty": "the split record assigns this group the open 360 (GF-02) vs "
                "476.37 (GF-04) GB/s discrepancy audit — carried, classified, "
                "never averaged",
        "the_two_numbers": {
            "GF-02": "community 8xH100 NVSwitch node, NCCL allreduce/allgather "
                     "busbw plateau ~360 GB/s (maintainer-confirmed as the "
                     "expected H100 figure; thread verified 2026-10-28)",
            "GF-04": "vendor 8xH100 single-node NCCL summary busbw 476.37 GB/s "
                     "(fetch-verified 2026-10-28)",
            "same_fabric_class": "both are single-node 8xH100 NVSwitch-class "
                                 "series — the discrepancy is NOT a fabric-class "
                                 "difference",
        },
        "audit_rows": {
            "ratio_gf04_over_gf02_exact": str(ratio),
            "ratio_gf04_over_gf02_pct": pct(ratio - 1),
            "gf02_over_perdir_450_exact": str(GF02_PLATEAU / perdir),
            "gf04_over_perdir_450_exact": str(GF04_B8 / perdir),
            "fitted_B_separation": "the two fitted B values of THIS stage "
                "(360 and 476.37) differ by the same 32.3% — both are recorded "
                "diagnostics, carried separately to S6",
        },
        "classification": "GF-02's plateau sits at exactly 4/5 of the 450 "
            "physical per-direction aggregate (the CAL-A12 derating factor, the "
            "first measured point ON that bridge); GF-04's 476.37 sits 5.86% "
            "ABOVE 450 — no physical B <= 450 can produce it under the "
            "single-port injection abstraction, and in-network computing is "
            "declared unsupported by every L0 backend: the 476.37 figure is the "
            "NVLS/in-switch-reduction algorithm class (stage GF-02's "
            "classification, inherited). The 32.3% span between two same-fabric "
            "community/vendor readings is therefore a SOFTWARE-STACK/ALGORITHM "
            "axis (NCCL algorithm choice unpinned in both threads), not a fabric "
            "axis — B in this family is a software-effective rate, and the "
            "discrepancy is exactly the range of that effectiveness. KEPT OPEN: "
            "the two numbers are never averaged or reconciled into one "
            "parameter; both fitted values stand as separate diagnostics with "
            "their own provenance",
        "implication_for_the_fit_family": "any single-B claim about the 8xH100 "
            "NVSwitch class must carry a software-config pin or a >= 32% "
            "algorithm-class bracket; the L0 input space has no algorithm-class "
            "parameter (structural, recorded — the same blindness class as the "
            "CAL-A6 version axis and the size-dependent ramp of S2)",
    }


# ---------------------------------------------------------------------------
# 5. Executed-sweep reconciliation + closed-form cross-checks on every row.
# ---------------------------------------------------------------------------
def sweep_reconciliation(sweep_id: str, sweep_topos: list[tuple[str, str]],
                         allowed_payloads: set[int], cct_of,
                         per_b_deltas, grid_prefix: str = "grid") -> dict:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    b_by_path = sweep_b_map(sweep_topos)
    rows = {(r["topology"]["path"], r["payload_bytes"]): r for r in table["configs"]}
    assert len(rows) == len(sweep_topos) * len(allowed_payloads), (sweep_id, len(rows))
    for (path, payload), row in rows.items():
        assert payload in allowed_payloads, (path, payload, "payload fence")
        b = b_by_path[path]
        closed = cct_of(payload, b)
        assert row["o_cct"]["completion_time_ns_mean_exact"] == str(closed), (path, payload)
    per_b = []
    for path, provenance in sweep_topos:
        b = b_by_path[path]
        entry = {
            "topology": path.split("/")[-1],
            "provenance": provenance,
            "B_bytes_per_ns": str(b),
            "B_float": float(b),
            "grid_member": provenance.startswith(grid_prefix),
        }
        entry.update(per_b_deltas(b))
        per_b.append(entry)
    return {
        "sweep_id": sweep_id,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "grid": f"{len(sweep_topos)} topologies x {len(allowed_payloads)} payload "
                f"sizes = {len(rows)} configs x 6 ops",
        "payload_fence": "every executed payload is a fit-side size of this "
                         "anchor's split record (asserted)",
        "cross_check": "all executed rows equal the closed form of the same "
                       "identity function at the same payload and swept B "
                       "(exact Fraction string equality)",
        "per_B_deltas": per_b,
    }


def a6_deltas(b: Fraction) -> dict:
    out = {}
    worst = Fraction(0)
    for m in A6_SIZES:
        label = "1GiB" if m == 1 << 30 else "16GiB"
        for ver, times in (("2193", A6_T19), ("2203", A6_T20)):
            d = a6_dev(b, m, times[m])
            out[f"delta_pct_{ver}_{label}"] = pct(d)
            if abs(d) > worst:
                worst = abs(d)
    out["max_abs_delta_pct"] = pct(worst)
    return out


def gf02_deltas(b: Fraction) -> dict:
    out = {}
    worst = Fraction(0)
    for m in GF02_BAND:
        ref = AR8_FACTOR * m / GF02_PLATEAU
        d = xbar_time(m, b) / ref - 1
        out[f"delta_pct_{m}"] = pct(d)
        if abs(d) > worst:
            worst = abs(d)
    out["max_abs_delta_pct"] = pct(worst)
    return out


def gf04_deltas(b: Fraction) -> dict:
    out = {}
    worst = Fraction(0)
    for m in GF04_FIT_SIZES:
        ref = GF04_FACTOR8 * m / GF04_B8
        d = ring_time(m, b, R8) / ref - 1
        out[f"delta_pct_{m}"] = pct(d)
        if abs(d) > worst:
            worst = abs(d)
    out["max_abs_delta_pct"] = pct(worst)
    return out


def run_cross_checks() -> list[dict]:
    checks = []
    for run_id, closed, label in (
        (RUN_ID_A6_2193, ring_time(1 << 34, B_FIT_A6_2193, R32),
         "CAL-A6 2.19.3 fit-side run at the 16 GiB fit size, B_fit(2.19.3)"),
        (RUN_ID_A6_2203, ring_time(1 << 34, B_FIT_A6_2203, R32),
         "CAL-A6 2.20.3 fit-side run at the 16 GiB fit size, B_fit(2.20.3)"),
        (RUN_ID_GF02_AR, xbar_time(1 << 34, B_FIT_GF02),
         "GF-02 allreduce fit-side run at the band top, B_fit = 360"),
        (RUN_ID_GF02_AG, ag_ring_time(8 * (1 << 34), B_FIT_GF02),
         "GF-02 allgather twin run at M_total = 2^37, the same fitted B"),
        (RUN_ID_GF04_FIT, ring_time(GF04_M_COMMON, B_FIT_GF04, R8),
         "GF-04 8-GPU fit-side run at the common ladder member 2^32, B_fit = 476.37"),
        (RUN_ID_GF04_HOLD, ring_time(GF04_M_COMMON, B_FIT_GF04, 16),
         "GF-04 held-out reporting run at r=16, 2^32, the SAME fitted B (held_out: true)"),
    ):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        if obs["backend_id"] == "analytical_l0_phase_collectives":
            per = next(p for p in obs["per_op"] if p["collective"] == "allgather")
        else:
            per = obs["per_op"][0]
        assert per["completion_time_ns_exact"] == str(closed), (run_id, per)
        assert run["evidence_schema_version"] == 2
        expected_target = ("CAL-A6" if "A6" in run["manifest"]["experiment_id"]
                           else ("GF-02" if "GF02" in run["manifest"]["experiment_id"]
                                 else "GF-04"))
        assert run["calibration_target"] == [expected_target], run_id
        checks.append({
            "run_id": run_id,
            "mapping": label,
            "experiment_id": run["manifest"]["experiment_id"],
            "held_out": run["held_out"]["held_out"],
            "calibration_target": run["calibration_target"],
            "cct_ns_exact": per["completion_time_ns_exact"],
            "verdict": "store run == closed form of the same identity function "
                       "(exact Fraction string equality)",
        })
    assert [c["held_out"] for c in checks] == [False, False, False, False, False, True]
    return checks


# ---------------------------------------------------------------------------
# 6. v2 evidence dimensions (the five D3 fields, mirrored on this record).
# ---------------------------------------------------------------------------
def evidence_dimensions_block() -> dict:
    block = {
        "verification": [
            {
                "check": "tests/calibration/test_s3_fit.py",
                "scope": "S3 fit guard — re-executes the three S3 fit sweeps and "
                         "the six S3 runs into a scratch store, rebuilds this "
                         "record byte-identically, and checks the fit/holdout "
                         "separation invariants (GF-04's 16-GPU point held out; "
                         "CAL-A6/GF-02 degenerate splits; no r=16 topology in "
                         "any sweep)",
            },
            {
                "check": "tests/calibration/test_anchor_split.py",
                "scope": "the split record's own immutability guard (S1) — the "
                         "data separation this fit runs under",
            },
        ],
        "calibration_target": ["CAL-A6", "GF-02", "GF-04"],
        "held_out": {
            "held_out": False,
            "scope": "the S3 fit objectives and every swept value here touch only "
                     "the group-G2 fit signals: CAL-A6's two endpoint sizes per "
                     "NCCL version (degenerate split), GF-02's saturation band "
                     "(degenerate split), and GF-04's 8-GPU single-node point "
                     "ONLY; the provenance points (25/320/400/450/900) are "
                     "config/ceiling arithmetic, never measured values; GF-04's "
                     "16-GPU point appears ONLY in held_out_evaluation (its run "
                     "record declares held_out: true)",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "single fixed-B, zero-overhead L0 identities — no software-version "
            "parameter (the CAL-A6 fitted-B separation of -3.66% is that axis "
            "executed), no algorithm-class parameter (the 32.3% GF-02-vs-GF-04 "
            "span), no fabric-asymmetry parameter (the GF-04 held-out -1.37%)",
            "A-L0-LAT / A-L0X-LAT fixed at the registry point 200 ns; the latency "
            "axis is stage S4's (every S3 fit is bandwidth-bound, latency-term "
            "share <= 0.24%)",
            "no congestion, no credit flow control, no packetization, no "
            "multi-port injection, no in-network reduction (analytical L0 "
            "transport model only)",
            "GF-02's per-size rows are screenshots (plateau + regime endpoints "
            "extractable only); GF-04's per-size tables are images (summary "
            "figures extractable only) — both recorded by their stages; the "
            "NCCL algorithm/channelization is UNPINNED in both threads",
        ],
    }
    problems = dimensions_problems(block)
    assert not problems, problems
    return block


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------
def build_record() -> dict:
    a6 = cal_a6_fit()
    floor = noise_floor_execution()
    gf02 = gf02_fit()
    gf04 = gf04_fit()
    held = gf04_held_out()
    audit = gf02_gf04_audit()

    sweep_a6 = sweep_reconciliation(
        SWEEP_ID_A6, A6_SWEEP_TOPOS, set(A6_SIZES),
        lambda m, b: ring_time(m, b, R32), a6_deltas,
    )
    sweep_gf02 = sweep_reconciliation(
        SWEEP_ID_GF02, GF02_SWEEP_TOPOS, set(GF02_BAND),
        xbar_time, gf02_deltas,
    )
    sweep_gf04 = sweep_reconciliation(
        SWEEP_ID_GF04, GF04_SWEEP_TOPOS, set(GF04_FIT_SIZES),
        lambda m, b: ring_time(m, b, R8), gf04_deltas,
    )
    # the GF-04 fit sweep carries NO r=16 topology (mechanical fence)
    for entry in sweep_gf04["per_B_deltas"]:
        assert "ring16" not in entry["topology"], entry
    runs = run_cross_checks()

    b19 = float(B_FIT_A6_2193)
    b20 = float(B_FIT_A6_2203)
    record = {
        "record_kind": "calibration_fit",
        "evidence_schema_version": 2,
        "status": "PROPOSED — owner adjudication required; no claim, label, or "
                  "shipped parameter value changes; every fitted B is a recorded "
                  "diagnostic, never a shipped value",
        "stage": "calibration fit record, S3 (group G2)",
        "split_record": {
            "record_id": SPLIT_RECORD_ID,
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "within_series_rules": "CAL-A6 fit BOTH endpoint sizes {1,16} GiB per "
                                   "version (degenerate — no within-series holdout "
                                   "exists; the version pair is the noise floor); "
                                   "GF-02 fit the whole saturation band "
                                   "(degenerate); GF-04 fit the 8-GPU point ONLY — "
                                   "the 16-GPU point is held out on the scaling "
                                   "dimension and reported as held-out error",
            "group": "G2 — H100-class community series + hybrid scale-up/scale-out "
                     "+ multi-rank injection scaling (fitting stage S3)",
            "no_leakage": "none of the split record's cross-anchor holdouts or "
                          "its blocked anchor is read by any objective, swept "
                          "value, or tolerance in this record (mechanically "
                          "asserted: their ids appear nowhere in the record "
                          "bytes); sole recorded exception used: the ~5% "
                          "mean-error scalar as tolerance-SHAPE context only — "
                          "the ids stay unlisted here by design",
        },
        "group_g2_anchors": {
            "fit_targets": [
                "CAL-A6 — noise-floor anchor + secondary O-CCT target (NCCL "
                "issue #1222, 4x8 H100 hybrid NVLink+RoCE, 2.19.3 vs 2.20.3, "
                "1-16 GiB; staging §A6; confidence M-H; targets = the staged "
                "TIMES, the 2.20.3 busbw quotes quarantined)",
                "GF-02 — community 8xH100 NVSwitch saturation band ~360 GB/s "
                "(nccl-tests issue #326; staging §GF-02; confidence M-H; thread "
                "verified 2026-10-28)",
                "GF-04 — vendor 8-GPU point 476.37 GB/s of the 8->16 scaling pair "
                "(Oracle OCI blog; staging §GF-04; confidence M-H; page verified "
                "2026-10-28; the 16-GPU leg 469.67 is held out)",
            ],
            "carried_duty": "the GF-02-vs-GF-04 360/476.37 GB/s audit (see "
                            "gf02_gf04_audit)",
        },
        "model": {
            "backend_ids": ["analytical_l0", "analytical_l0_crossbar",
                            "analytical_l0_phase_collectives"],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L (chains 62L-term structure "
                        "at r=32, 14L at r=8, 30L at r=16)",
                "crossbar": "t = 2(r-1)/r*M/B + 2L (r=8)",
                "allgather_ring_phase": "t = (r-1)/r*M_total/B + (r-1)*L "
                                        "(A-L0P-MSG total-gathered semantics)",
            },
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-DIV (ring), A-L0X-PORT / "
                           "A-L0X-BW / A-L0X-LAT / A-L0X-DIV (crossbar), "
                           "A-L0P-ALGO / A-L0P-MSG / A-L0P-COMP / A-L0P-DIV "
                           "(phase collectives) — experiments/vertical_slice/"
                           "assumptions_l0.yaml; the anchor sizes are powers of "
                           "two and every rank count divides them, so all gates "
                           "ACCEPT with NO bracketing (the anti-A3 case)",
            "declared_free_parameters": {
                "A-L0-BW": {
                    "parameter": "link.bytes_per_ns",
                    "registry_value": REGISTRY_VALUE,
                    "registry_range": list(REGISTRY_RANGE),
                    "swept_by": "the CAL-A6 (r=32 ring) and GF-04 (r=8 ring) fits",
                },
                "A-L0X-BW": {
                    "parameter": "nic.injection_bytes_per_ns",
                    "registry_value": REGISTRY_VALUE,
                    "registry_range": list(REGISTRY_RANGE),
                    "swept_by": "the GF-02 (r=8 crossbar) fit",
                },
                "registry_note": "both registry VALUES stay 64 — unchanged by "
                                 "this stage; the grid is the same anchor-blind "
                                 "64 B/ns instrument as S2 (64..1024 = 16 uniform "
                                 "points over the declared range)",
            },
            "chunk_count_declaration": "A-AS1-CHUNKS-1 duty (plan §2.2, the "
                "split record's parameter_axes): the ring identity's chunk "
                "treatment is FIXED at the equal-chunk construction M/r in "
                "serialized single-partner steps — the identity carries NO "
                "chunk-count/channel/SM parameter, and the CAL-A6 anchor's "
                "staged root cause (16x200G read as 8x400G; 16 SMs) is exactly "
                "that sensitivity class: the version swing is the mechanism's "
                "measured shadow, inexpressible in this input space",
        },
        "executed_sweeps": {
            "cal_a6": sweep_a6,
            "gf02": sweep_gf02,
            "gf04_tp8_only": sweep_gf04,
        },
        "fits": {
            "cal_a6": a6,
            "gf02": gf02,
            "gf04": gf04,
        },
        "noise_floor_execution": floor,
        "gf02_gf04_audit": audit,
        "held_out_evaluation": held,
        "store_run_cross_checks": runs,
        "headline": (
            f"group G2 fits: CAL-A6 two-point minimax per NCCL version lands at "
            f"B_fit = {b19:.4f} (2.19.3, worst ±0.62%) and {b20:.4f} B/ns "
            f"(2.20.3, worst ±2.19%) — a -3.66% fitted-B separation that IS the "
            f"anchor's noise-floor role executed on the parameter axis; GF-02 is "
            f"degenerate (B_fit = 360 exactly, residuals = the pure latency "
            f"terms, worst +0.061% at the band bottom); GF-04 is degenerate "
            f"(B_fit = 476.37 exactly, fit-point residual +0.018%) with the "
            f"16-GPU point held out: the model at the fitted B misses it by "
            f"-1.37% (rank-count-invariance vs the measured -1.41% busbw drop — "
            f"the fabric-asymmetry known-omission finding); the 360-vs-476.37 "
            f"audit resolves to a 32.3% software-stack/algorithm axis on the "
            f"same fabric class — kept open, both fitted values carried as "
            f"separate diagnostics"
        ),
        "not_tuned": "every sweep grid was fixed by registry-range arithmetic "
                     "and anchor-CONFIG provenance before any deviation was "
                     "computed; the A6 minimax values are exact closed forms "
                     "over the fit points only; the GF-02/GF-04 fitted values "
                     "are the anchors' own figures under the source-pinned "
                     "mapping (degenerate fits with zero residual degrees of "
                     "freedom); the held-out 16-GPU row was evaluated AFTER "
                     "B_fit was fixed and changed nothing; the registry values "
                     "stay 64 and no manifest outside this calibration "
                     "directory carries any fitted value",
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, "
                    "replay reproduces byte-identical artifacts)",
            "fit": "PROPOSED calibration fit candidate against external published "
                   "measurements; no E3/E4 language — none of the anchors is our "
                   "testbed, and owner adjudication precedes any label move",
        },
        "backing": {
            "sweep_ids": [SWEEP_ID_A6, SWEEP_ID_GF02, SWEEP_ID_GF04],
            "run_ids": [RUN_ID_A6_2193, RUN_ID_A6_2203, RUN_ID_GF02_AR,
                        RUN_ID_GF02_AG, RUN_ID_GF04_FIT, RUN_ID_GF04_HOLD],
            "run_roles": {
                RUN_ID_A6_2193: "CAL-A6 2.19.3 fit-side (held_out: false)",
                RUN_ID_A6_2203: "CAL-A6 2.20.3 fit-side (held_out: false)",
                RUN_ID_GF02_AR: "GF-02 allreduce fit-side (held_out: false)",
                RUN_ID_GF02_AG: "GF-02 allgather twin, fit-side backing "
                                "(held_out: false)",
                RUN_ID_GF04_FIT: "GF-04 8-GPU fit-side (held_out: false)",
                RUN_ID_GF04_HOLD: "GF-04 16-GPU held-out reporting, the stage's "
                                  "sole r=16 execution (held_out: true)",
            },
            "inputs": [
                "experiments/calibration/s3/sweep_s3_a6_bw_v1.yaml",
                "experiments/calibration/s3/sweep_s3_gf02_bw_v1.yaml",
                "experiments/calibration/s3/sweep_s3_gf04_tp8_bw_v1.yaml",
                "experiments/calibration/s3/run_s3_a6_fit_2193_16gib.yaml",
                "experiments/calibration/s3/run_s3_a6_fit_2203_16gib.yaml",
                "experiments/calibration/s3/run_s3_gf02_fit_ar_16gib.yaml",
                "experiments/calibration/s3/run_s3_gf02_fit_ag_twin.yaml",
                "experiments/calibration/s3/run_s3_gf04_fit_tp8_4gib.yaml",
                "experiments/calibration/s3/run_s3_gf04_holdout_tp16_4gib.yaml",
                "experiments/calibration/s3/topologies/ (49 files)",
                "experiments/calibration/s3/profiles/ (3 files)",
                "experiments/calibration/{a6,gf02,gf04}/ committed stage inputs "
                "(workloads + anchor/provenance topologies, reused)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/s3/"
                         "sweep_s3_a6_bw_v1.yaml ; make sweep "
                         "EXP=experiments/calibration/s3/sweep_s3_gf02_bw_v1.yaml "
                         "; make sweep EXP=experiments/calibration/s3/"
                         "sweep_s3_gf04_tp8_bw_v1.yaml ; make run EXP="
                         "(each of the six run_s3_*.yaml manifests) ; python "
                         "experiments/calibration/s3/build_fit_record.py",
            "s6_handoff": "the fitted configurations this record hands to the S6 "
                          "holdout evaluation: B_fit(CAL-A6 2.19.3) = "
                          + str(B_FIT_A6_2193) + ", B_fit(CAL-A6 2.20.3) = "
                          + str(B_FIT_A6_2203) + ", B_fit(GF-02) = 360, "
                          "B_fit(GF-04) = 476.37 B/ns — all recorded diagnostics",
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
