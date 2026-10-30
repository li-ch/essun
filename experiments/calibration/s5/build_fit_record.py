"""Build the PROPOSED calibration fit record for stage S5 (group G4, the
geometry-falsifier + UEC/congestion-envelope stage: CAL-A5 + CAL-A11 +
GF-05 + GF-07 + GF-08 + GF-09 per the immutable split record 3862e227...,
experiments/calibration/split/anchor_split_v1.json).

What this stage fits: NO O-CCT fit exists in this group. None of the six
G4 anchors stages a collective (size -> time) series — CAL-A5 stages a
dimensionless twisted-vs-regular geometry RATIO, CAL-A11/GF-05/GF-07/
GF-08 stage dimensionless effect-size FACTORS and absolute carrier
RATES, and GF-09 stages DESIGN TARGETS. The split record's own
parameter_axes duty is therefore "envelope/context checks, not O-CCT
fits" plus the A-L0T-UNIF geometry-abstraction falsification. This stage
sweeps the DECLARED free ranges of A-L0T-BW (torus link.bytes_per_ns)
and A-L0X-BW (crossbar nic.injection_bytes_per_ns) — registry value 64,
range [1, 1024] B/ns each — as the executed instrument of exactly those
checks, with L fixed at the registry 200 ns (the latency axis was S4's).
NOTHING IS TUNED: registry values stay 64, every anchor figure is a
placement or a classified miss, and the misses ARE the findings.

Run-backed cross-checks enforced here (a mismatch is a bug, not a
finding):

1. every executed row of ALL THREE sweeps equals the closed form of its
   own identity function at the same (payload, B, L) by exact Fraction
   string equality;
2. all seven store runs equal the same closed forms at their anchor
   points, and their stamped evidence dimensions are as declared (v2,
   calibration_target per anchor, held_out FALSE — the split record
   defines NO within-series holdout for any G4 anchor);
3. the falsifier's exact arithmetic: the anchor's twist ratio read onto
   the model's own anchor-point CCT demands a completion time BELOW the
   identity's B->infinity latency-chain floor at BOTH slices (the B axis
   cannot express the effect at ANY admissible B, let alone in the
   declared range) — asserted as exact Fraction inequalities on executed
   rows; the executed twist-displacement rows deliver only a computed
   ~1.26%/0.46% CCT cut against the required 38.65%/23.66%;
4. the envelope convergence law: for every executed degradation edge
   (carrier B_c, edge B_e = B_c / f), the CCT ratio t_e/t_c is strictly
   increasing across the executed 12-size ladder, bounded above by the
   exact asymptote f = B_c/B_e — asserted for every edge/carrier pair on
   executed rows;
5. every executed envelope-edge and carrier B value lies INSIDE the
   declared free range [1, 1024] (the range admits the whole envelope;
   the identity still predicts only the uncongested carrier row).

Pure function of immutable artifacts: reads the three append-only store
sweep tables and the seven store run records produced by this stage,
recomputes every derived quantity with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/
record.json`` plus the committed copy
``experiments/calibration/s5/fit_record_v1.json`` (byte-identical;
append-only — an existing record with different bytes is an error, a
change requires fit_record_v2). No wall-clock, no host metadata.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim, label, or shipped parameter value changes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical.l0_torus2d import Torus2DConfig
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
SWEEP_ID_TORUS128 = "9351c33052f72e2dc56049ea1894011e49f8b8d0e9102abf81c296a895c94b9b"
SWEEP_ID_TORUS256 = "c0b0e9618c34de2e081db5b161e3da1dc6f8046d79032d65a35b3992bdc9e3dd"
SWEEP_ID_ENVELOPE = "a489d720259ee6f3eb7bc0b7872d03fcf5dbb19f7f370dee8769c2aa8f7b25b5"
RUN_IDS = {
    "a5_slice128": "43091e1545280c151bb56769897cff7e538e3c3e8935d8ab11bb5599d49c9458",
    "a5_slice256": "645e8b4f2a733ab358c60be719c1575757ec21bc6ed0ffd8402c7a146fbbb6b5",
    "a11_carrier": "7f8dfd7fd28f65e42c458004f0f952f47ae7b5d5db115bd7d0e7638a92981837",
    "gf05_simconfig": "f96b688ca8524eaebb846b46819edcbbe10c367687c7ddacf2524c7235a59ae1",
    "gf07_carrier": "e14917e9f91c47020d5c29e75d473fcbc385a9cecf389247b7192d47f4670017",
    "gf08_falcon": "09cae0bf8cbc0739c334b8b7ae6786eb72f7eeb85d137dd338c49f56a8ca0b16",
    "gf09_uec50": "610653fb4b9d9bf82f51a73ec91d8cb84ba7309bd9a0d7674c859f1501c7cbb7",
}
RUN_ROLES = {
    "a5_slice128": "CAL-A5 falsifier anchor-side reference run (torus 8x16, B=50 reading 1; held_out: false)",
    "a5_slice256": "CAL-A5 falsifier anchor-side reference run (torus 8x32, B=50 reading 1; held_out: false)",
    "a11_carrier": "CAL-A11 context-proxy carrier run (crossbar B=50, 8 GiB; held_out: false)",
    "gf05_simconfig": "GF-05 anchor-CONFIG provenance run at the anchor's own uet-htsim sim config (crossbar B=100, L=1000, 2 MiB; held_out: false)",
    "gf07_carrier": "GF-07 measured-envelope carrier run (crossbar B=100 LUMI, 16 MiB; held_out: false)",
    "gf08_falcon": "GF-08 hardware-transport carrier run (crossbar B=25 Falcon, 16 KiB; held_out: false)",
    "gf09_uec50": "GF-09 design-target ceiling placement run (crossbar B=50 design-class floor, 2 MiB; held_out: false)",
}
RUN_EXPERIMENT_IDS = {
    "a5_slice128": "EXP-CAL-S5-A5-FALSIFIER-128-001",
    "a5_slice256": "EXP-CAL-S5-A5-FALSIFIER-256-001",
    "a11_carrier": "EXP-CAL-S5-A11-CARRIER-001",
    "gf05_simconfig": "EXP-CAL-S5-GF05-SIMCONFIG-001",
    "gf07_carrier": "EXP-CAL-S5-GF07-CARRIER-001",
    "gf08_falcon": "EXP-CAL-S5-GF08-FALCON-001",
    "gf09_uec50": "EXP-CAL-S5-GF09-UEC50-001",
}

RESULTS = REPO_ROOT / "results"
S5_DIR = REPO_ROOT / "experiments" / "calibration" / "s5"
COMMITTED_COPY = S5_DIR / "fit_record_v1.json"

# ---------------------------------------------------------------------------
# Anchor staged numbers (transcription sources: the committed E1 builders
# at experiments/calibration/{a5,a11,gf05,gf07,gf08,gf09}/; staging docs
# anchors_staging.md §A5/§A11 and anchors_gapfill.md §GF-05/§GF-07/
# §GF-08/§GF-09). Nothing else is read; nothing is re-fetched.
# ---------------------------------------------------------------------------
# CAL-A5 (TPU v4, ISCA 2023; H transcription, direction convention flagged
# UNVERIFIED by the staging doc — both readings executed, neither chosen):
A5_TWIST = {128: Fraction(163, 100), 256: Fraction(131, 100)}  # twisted vs regular, all-to-all
A5_READING1 = Fraction(50)   # per-link per-direction ("400 vs. 200 Gbit/s")
A5_READING2 = Fraction(25)   # per-link bidirectional alternative
A5_DMA_BYTES = 4096          # "individual DMAs of 4 KiB"
A5_TPUV3_ROW = Fraction(70)  # Table 4 comparison row: 4 links @ 70 GB/s
A5_A100_ROW = Fraction(25)   # Table 4 comparison row: 12 links @ 25 GB/s
A5_OCS_NS = Fraction(1_000_000)  # declared lower edge of the staged WORD "milliseconds"
FAITHFUL = {128: (8, 16), 256: (8, 32)}        # declared 3D->2D projections
SHAPES_128 = {"8x16": (8, 16), "4x32": (4, 32), "2x64": (2, 64)}
SHAPES_256 = {"8x32": (8, 32), "4x64": (4, 64), "2x128": (2, 128), "16x16": (16, 16)}
# CAL-A11 (Meta SIGCOMM 2024 RoCE production fabric; M-H, labeled proxy):
A11_CARRIER = Fraction(50)             # 400G optics / 8, declared per-direction reading
A11_DEGRADE = Fraction(7, 10)          # path pinning "up to more than 30%"
A11_IMPROVE = Fraction(7, 5)           # E-ECMP + QP scaling "up to 40% improvement"
A11_IMPLIED_BASELINE = Fraction(250, 7)  # 50 / 1.4 — recorded, not executed
# GF-05 (SMaRTT/REPS, NSDI 2025; H, sim + small HW testbed, FCT metrics):
GF05_RATE_GBPS = Fraction(800)
GF05_B_LINE = GF05_RATE_GBPS / 8       # 100 (declared per-direction reading)
GF05_B_ALT = GF05_B_LINE / 2           # 50 (bidirectional-aggregate, recorded)
GF05_SWITCH_NS = Fraction(400)         # switch traversal latency (verbatim)
GF05_LINK_NS = Fraction(600)           # link latency (verbatim)
GF05_L_HOP = GF05_SWITCH_NS + GF05_LINK_NS    # 1000
GF05_BASE_RTT = Fraction(12000)        # 84 us / 7 exactly
GF05_TARGET_RTT = Fraction(18000)      # 1.5 x base RTT
GF05_MTU = 4096
GF05_BDP = GF05_BASE_RTT * GF05_B_LINE          # 1,200,000 B
GF05_WINDOW = GF05_BDP * Fraction(3, 2)         # 1.5 BDP clamp
GF05_CC_GAIN = Fraction(1, 2)          # "outperforms ... by up to 50%"
GF05_ALLTOALL_IDEAL = Fraction(6, 100) # "only up to 6% behind the ideal time"
GF05_ALLTOALL_BETTER = Fraction(1, 5)  # "up to 20% better than other sender-based schemes"
GF05_FAIRNESS = Fraction(65, 100)      # slowest flow FCT 65% longer (under Swift)
GF05_ROCE_PERM = (3, 5)                # HW permutation "3-5 times slower than optimal"
GF05_ROCE_ALLTOALL = (3, 6)            # HW alltoall "RoCEv2 is 3-6x slower"
GF05_EQDS_TRIM = 155                   # "up to 155x more trimmed packets"
GF05_SUBS = (2, 4, 8)                  # oversubscription series
# GF-07 (arXiv 2604.11432; H, MEASURED, scale-out labeled proxy):
GF07_LUMI_GBPS = Fraction(4 * 200)
GF07_B_CARRIER = GF07_LUMI_GBPS / 8    # 100 (LUMI per-node aggregate, declared reading)
GF07_B_LEONARDO = Fraction(400) / 8    # 50
GF07_NJ_PEAK = Fraction("22.5")        # 180 Gb/s / 8
GF07_NJ_OFF = Fraction(15)             # 120 Gb/s / 8
F_FLOOR = Fraction(20, 19)             # LUMI "always within 5%"
F_ALLREDUCE = Fraction(4, 3)           # "up to a 25% bandwidth loss" (AllReduce-class)
F_BURST_A2A = Fraction(10, 7)          # bursty alltoall "drops to 70%"
F_STEADY_INCAST = Fraction(5, 3)       # steady incast "dropping to 60%"
F_LEONARDO_COLLAPSE = Fraction(5)      # "collapse to 0.2"
F_BURSTY_INCAST = Fraction(25, 2)      # staged ratio "0.08" read exactly
F_BURSTY_ALT = Fraction(12)            # the paper's own "12x slower" gloss
F_WORST = Fraction(25)                 # CRESCO8 "slowdowns up to 25x"
GF07_ENVELOPE_SPAN = F_WORST / F_FLOOR # 95/4 = 23.75
GF07_PARTITION_PCT = 2                 # congestion effects "even at ~2% of a partition"
# GF-08 (Falcon, SIGCOMM 2025; M-H, abstract-level headline numbers):
GF08_B_FALCON = Fraction(200) / 8      # 25 (per-endpoint reading)
GF08_B_ALT = Fraction(200) / 2 / 8     # 12.5 (bidirectional-aggregate reading)
GF08_F_CONGESTION = Fraction(8)        # "8x lower than CX-7 RoCE under congestion"
GF08_F_LOSSY = Fraction(33, 20)        # "up to 65% higher goodput" (1.65)
GF08_MOPS = Fraction(120 * 10 ** 6)    # "120 Mops/sec"
GF08_OPS_PER_NS = GF08_MOPS / 10 ** 9  # 3/25
GF08_T_PER_OP = 1 / GF08_OPS_PER_NS    # 25/3 ns/op
GF08_BYTES_PER_OP = GF08_B_FALCON / GF08_OPS_PER_NS  # 625/3
GF08_L_IMPLIED = GF08_T_PER_OP / 2     # 25/6 ~ 4.17 ns (below the range lower 10)
# GF-09 (Ultra Ethernet design principles, arXiv 2508.08906; M, design
# targets — NOT measurements; public paper, no spec text ingested):
GF09_B_UEC = Fraction(400) / 8         # 50: the "400+ Gbps" class floor, per-direction reading
GF09_B_ALT = Fraction(400) / 2 / 8     # 25: bidirectional-aggregate reading
GF09_SUBUS_NS = Fraction(1000)         # "sub-microsecond latency" target boundary edge
GF09_TARGET_RTT_NS = Fraction(10000)   # "target round-trip times of 10 us"
GF09_L_RTT_CHARGED = GF09_TARGET_RTT_NS / 2  # 5000, charged as the identity's 2L
GF09_RCCC_SHARE = Fraction(1, 4)       # "assigns 25% of the bandwidth to each" of 4 flows
GF09_OVERSUB_SATISFY = Fraction(33, 100)     # "can only satisfy 33% of the bandwidth"
GF09_LINK_M = (Fraction(10), Fraction(150))  # "medium-length (10-150m) links"
GF09_FIBER_NS_PER_M = Fraction(5)      # DECLARED engineering constant (~2/3 c)
GF09_SACK_BITS, GF09_NSCC_FB_B, GF09_CBFC_BITS = 64, Fraction(8), 20
GF09_BDP_AT_TARGET = GF09_TARGET_RTT_NS * GF09_B_UEC  # 500,000 B

# Registry / free-parameter discipline (UNCHANGED by this stage).
L_REG = Fraction(200)                  # A-L0T-LAT / A-L0X-LAT registry point (fixed this stage)
B_REG = Fraction(64)                   # A-L0T-BW / A-L0X-BW registry value
B_RANGE = (Fraction(1), Fraction(1024))
PLAN_SPAN_BW = (Fraction(20), Fraction(64))  # plan §2.1 A-L0T-BW candidate span
CAL_A6_SWING_UPPER = Fraction(8, 100)  # CAL-A6 software-version swing upper (fit-set anchor, G2)

GRID_B = [Fraction(64 * k) for k in range(1, 17)]  # the uniform anchor-blind grid
LADDER = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
          134217728, 268435456, 536870912, 2147483648, 8589934592]

# Envelope edge/carrier map: executed B -> the displacement spec (carrier,
# factor, anchor, quote). Edges not representable as finite decimals are
# recorded in NON_REPR_EDGES and never executed.
ENV_EDGES = [
    # (B_edge, carrier, factor, anchor, quote)
    (Fraction(95), Fraction(100), F_FLOOR, "GF-07", "LUMI 'always within 5% of the uncongested case' (per-flow HW CM + adaptive routing) — the envelope FLOOR"),
    (Fraction(75), Fraction(100), F_ALLREDUCE, "GF-07", "'Open MPI AllReduce showed up to a 25% bandwidth loss' — the anchor's ONE AllReduce-class quote"),
    (Fraction(70), Fraction(100), F_BURST_A2A, "GF-07", "bursty alltoall 'drops to 70% of its uncongested baseline'"),
    (Fraction(60), Fraction(100), F_STEADY_INCAST, "GF-07", "steady incast 'performance dropping to 60% of the uncongested case'"),
    (Fraction(20), Fraction(100), F_LEONARDO_COLLAPSE, "GF-07", "Leonardo incast 'collapse to 0.2' at 32-64 nodes"),
    (Fraction(10), GF07_B_LEONARDO, F_LEONARDO_COLLAPSE, "GF-07", "the SAME factor 5 at Leonardo's OWN rate (50/5) — carrier-invariant ratio"),
    (Fraction(8), Fraction(100), F_BURSTY_INCAST, "GF-07", "bursty incast 64 nodes, staged ratio '0.08' read exactly"),
    (Fraction(4), Fraction(100), F_WORST, "GF-07", "CRESCO8 steady-incast AllToAll victims 'slowdowns up to 25x' — the envelope CEILING"),
    (Fraction(50), GF05_B_LINE, Fraction(2), "GF-05", "2:1 oversubscription displacement (100/2)"),
    (Fraction(25), GF05_B_LINE, Fraction(4), "GF-05", "4:1 oversubscription displacement (100/4)"),
    (Fraction(20), GF05_B_LINE, Fraction(5), "GF-05", "RoCE '3-5 times slower than optimal' lower edge (100/5)"),
    (Fraction("12.5"), GF05_B_LINE, Fraction(8), "GF-05", "8:1 oversubscription displacement (100/8)"),
    (Fraction("3.125"), GF08_B_FALCON, GF08_F_CONGESTION, "GF-08", "'operation completion times 8x lower than CX-7 RoCE under network congestion' (25/8)"),
    (Fraction("16.5"), GF09_B_UEC, 1 / GF09_OVERSUB_SATISFY, "GF-09", "oversubscription worked example 'can only satisfy 33% of the bandwidth' (50 x 33/100)"),
    (Fraction("12.5"), GF09_B_UEC, 1 / GF09_RCCC_SHARE, "GF-09", "RCCC worked example 'assigns 25% of the bandwidth to each' of 4 incast flows (50/4, factor exactly 4)"),
    (Fraction(35), A11_CARRIER, 1 / A11_DEGRADE, "CAL-A11", "path pinning degraded training 'up to more than 30%' (50 x 7/10, the declared lower-edge reading of 'more than 30%')"),
]
ENV_CARRIERS = [
    (Fraction(100), "GF-05+GF-07", "GF-05's uet-htsim '800 Gbps network bandwidth' (declared per-direction reading) AND GF-07's LUMI '4x200 Gb/s' per-node aggregate — two anchors, one rate; the UNCONGESTED reference the identity predicts"),
    (Fraction(50), "CAL-A11+GF-09", "CAL-A11's '400G single-mode optics' (declared per-direction reading) AND GF-09's '400+ Gbps' design-class floor — carrier and class floor, never achieved values for GF-09"),
    (Fraction(25), "GF-08", "Falcon 'peak performance of 200 Gbps' per-endpoint reading — a shipped HW transport's headline rate, not a collective measurement"),
]
NON_REPR_EDGES = {
    "GF-05": {"200/3": "CC gain 'up to 50%', primary reading t_baseline = 3/2 t_SMaRTT (100 / 3/2)",
              "500/53": "alltoall 'only up to 6% behind the ideal time' (100 / 53/50)",
              "250/3": "'up to 20% better than other sender-based schemes' (100 / 6/5)",
              "2000/33": "fairness 'slowest flow FCT 65% longer' (100 / 33/20)",
              "100/3": "RoCE 3x from optimal (100/3)",
              "50/3": "RoCE alltoall 6x from optimal (100/6)"},
    "GF-07": {"100/12": "the paper's own '12x slower' gloss of the 0.08 row (100/12)",
              "10000/167": "CRESCO8 '1.67:1 blocking' first-order displacement (100/1.67)"},
    "GF-08": {"500/33": "'up to 65% higher goodput under lossy conditions' (25 / 33/20)",
              "250/33": "the same 65% edge at the alternative carrier (12.5 / 33/20)"},
}


def pct(x: Fraction) -> float:
    return float(x) * 100.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Closed forms (exact).
# ---------------------------------------------------------------------------
def t_xbar(payload: int, b: Fraction, l: Fraction = L_REG) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L at r=8 (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(7 * payload, 4) / b + 2 * l


def t_torus(payload: int, r1: int, r2: int, b: Fraction, l: Fraction = L_REG) -> Fraction:
    """t_2d = t_ring(M,r1) + t_ring(M,r2); t_ring = 2(k-1)/k*M/B + 2(k-1)*L."""
    def ring(k: int) -> Fraction:
        return Fraction(2 * (k - 1) * payload, k) / b + 2 * (k - 1) * l
    return ring(r1) + ring(r2)


def torus_latency_chain(r1: int, r2: int, l: Fraction = L_REG) -> Fraction:
    return 2 * (r1 - 1) * l + 2 * (r2 - 1) * l


def torus_wire_coeff(r1: int, r2: int) -> Fraction:
    return Fraction(2 * (r1 - 1), r1) + Fraction(2 * (r2 - 1), r2)


def b_from_torus_id(topo_id: str) -> tuple[Fraction, tuple[int, int], int]:
    """torus2d128_s5_8x16_b81_5_v1 / torus2d128_a5_8x16_b50_v1 -> (B, shape, ranks)."""
    parts = topo_id.split("_")
    ranks = int(parts[0].removeprefix("torus2d"))
    shape = (int(parts[2].split("x")[0]), int(parts[2].split("x")[1]))
    stem = topo_id.split("_b", 1)[1].rsplit("_v1", 1)[0]
    return Fraction(stem.replace("_", ".")), shape, ranks


def b_from_xbar_id(topo_id: str) -> Fraction:
    """crossbar8_s5_b3_125_l200_v1 -> 3.125."""
    stem = topo_id.split("_b", 1)[1].split("_l200")[0]
    return Fraction(stem.replace("_", "."))


def sweep_rows(sweep_id: str) -> list[dict]:
    return load_json(RESULTS / "sweeps" / sweep_id / "table.json")["configs"]


# ---------------------------------------------------------------------------
# 1. The CAL-A5 geometry falsifier (the group's main duty).
# ---------------------------------------------------------------------------
def fit_cal_a5() -> dict:
    # (a) structural blindness, verified against the landed dataclass
    fields = {f.name for f in dataclasses.fields(Torus2DConfig)}
    assert fields == {"topology_id", "ranks", "dim1_ranks", "dim2_ranks",
                      "link_bytes_per_ns", "hop_latency_ns"}, fields

    rows_by_slice: dict[int, dict[Fraction, Fraction]] = {128: {}, 256: {}}
    for sweep_id, ranks in ((SWEEP_ID_TORUS128, 128), (SWEEP_ID_TORUS256, 256)):
        for row in sweep_rows(sweep_id):
            topo = row["config_id"].split("-")[2]
            b, shape, r = b_from_torus_id(topo)
            assert r == ranks
            if shape != FAITHFUL[ranks]:
                continue  # the shape-space bound rows are reconciled separately
            cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
            assert cct == t_torus(A5_DMA_BYTES, shape[0], shape[1], b), (topo, cct)
            assert row["payload_bytes"] == A5_DMA_BYTES
            rows_by_slice[ranks][b] = cct
    # grid membership + provenance rows present
    for ranks in (128, 256):
        got = set(rows_by_slice[ranks])
        assert set(GRID_B) <= got and {A5_READING1, A5_READING2, Fraction(20)} <= got, ranks

    falsifier_rows = {}
    absorption = {}
    for ranks, measured in A5_TWIST.items():
        r1, r2 = FAITHFUL[ranks]
        floor = torus_latency_chain(r1, r2)                     # B -> infinity
        t_reg = rows_by_slice[ranks][A5_READING1]
        required = t_reg / measured                             # ratio read onto the model's own point
        # cross-check 3: required lies BELOW the B->infty floor — the B axis
        # cannot express the effect at ANY B (the whole [1, inf) axis)
        assert required < floor, (ranks, required, floor)
        max_gain = t_reg / floor                                # max throughput gain B: 50 -> inf
        delivered = (max_gain - 1) / (measured - 1)             # fraction of the required gain
        # the executed twist-displacement row (B = 50 x ratio)
        b_disp = A5_READING1 * measured
        t_disp = rows_by_slice[ranks][b_disp]
        cut_disp = (t_reg - t_disp) / t_reg
        cut_required = 1 - 1 / measured
        # the latency-absorption alternative (recorded, never executed/selected)
        wire_at_50 = torus_wire_coeff(r1, r2) * A5_DMA_BYTES / A5_READING1
        l_absorb = (required - wire_at_50) / torus_latency_chain(r1, r2, Fraction(1))
        blind = measured - 1
        falsifier_rows[f"slice_{ranks}"] = {
            "measured_twisted_over_regular_all_to_all_exact": str(measured),
            "model_twisted_over_regular": "1 (exactly, by input-space blindness — no geometry field exists)",
            "blind_spot_exact": str(blind),
            "blind_spot_pct": pct(blind),
            "blind_spot_over_cal_a6_8pct_swing_exact": str(blind / CAL_A6_SWING_UPPER),
            "anchor_point_cct_ns_exact": str(t_reg),
            "required_twisted_cct_ns_exact": str(required),
            "required_twisted_cct_ns_float": float(required),
            "b_to_infinity_latency_chain_floor_ns_exact": str(floor),
            "falsification_1_structural": "the input schema carries NO geometry field (verified against the landed Torus2DConfig): twisted and regular tori of the same (r1, r2, B, L) map to IDENTICAL model inputs — the anchor's ratio is INEXPRESSIBLE, not merely mispredicted",
            "falsification_2_b_axis_cannot_reach_it": f"the required twisted CCT {float(required):.1f} ns lies BELOW the identity's B->infinity floor {float(floor):.0f} ns: NO per-link B (finite or infinite, in or out of the declared range) can produce the anchor's geometry speedup in this hop-latency-dominated regime",
            "max_b_axis_throughput_gain_50_to_infinity_exact": str(max_gain),
            "delivered_fraction_of_required_gain_exact": str(delivered),
            "delivered_fraction_pct": pct(delivered),
            "executed_twist_displacement_row": {
                "B_exact": str(b_disp),
                "cct_ns_exact": str(t_disp),
                "cct_cut_vs_anchor_point_exact": str(cut_disp),
                "cct_cut_vs_anchor_point_pct": pct(cut_disp),
                "required_cut_pct": pct(cut_required),
                "statement": f"executing the twist ratio as a per-link-B displacement (50 x {measured} = {float(b_disp)}) delivers only {pct(cut_disp):.2f}% of a CCT cut where the anchor measures {pct(cut_required):.2f}% — the executed demonstration that absorbing a geometry (bisection-structure) effect into the bandwidth axis is a MISATTRIBUTION, not a fit; recorded, never selected",
            },
        }
        absorption[f"slice_{ranks}"] = {
            "L_absorption_alternative_exact": str(l_absorb),
            "L_absorption_alternative_float": float(l_absorb),
            "in_declared_range": Fraction(10) <= l_absorb <= Fraction(2000),
            "status": "RECORDED, never executed, never selected: in this latency-dominated regime the twist effect COULD be absorbed into the hop-latency axis (the required CCT is reachable by reducing L), but that charges a bisection-structure effect to the per-hop latency parameter — the same misattribution class as the B displacement, on the axis S4 fitted; flagged so S6/S7 see the full ambiguity, never tuned",
        }

    # per-link placement (the anchor's first plan role)
    placement = {
        "readings_vs_plan_span_20_64": {
            "reading1_50": "INSIDE (20 <= 50 <= 64)",
            "reading2_25": "INSIDE (20 <= 25 <= 64)",
            "reading_convention": "UNVERIFIED per the staging doc (Table 4 column order); BOTH readings executed in the sweeps, neither chosen; reading 1 is supported by the anchor's own §7.3 '400 vs. 200 Gbit/s' per-link quote",
        },
        "registry_point_contrast": {
            "registry_64_over_reading1_exact": str(B_REG / A5_READING1),
            "registry_64_over_reading1_pct": pct(B_REG / A5_READING1 - 1),
            "statement": "the A-L0T-BW registry point 64 sits +28.0% above the reading-1 anchor point (64/50 = 32/25) — a PLACEMENT fact, not a change (the registry value is untouched)",
        },
        "plan_span_flag": {
            "finding": "CAL-A5's own Table 4 comparison rows bracket the plan's candidate span [20, 64] differently: TPU v3 70 GB/s/link sits ABOVE the span ceiling (70/64 = 35/32) and A100 25 GB/s/link inside it — the span was derived from CAL-A7/CAL-A12 endpoints + CAL-A5's 50; the anchor's own comparison rows were not span inputs (direction convention of the 70 figure UNVERIFIED, same flag as the 50)",
            "status": "recorded for the owner; no span or value is changed here",
        },
    }

    # B-axis visibility in the executed instrument (the declared-range sweep)
    b_axis = {}
    for ranks in (128, 256):
        r1, r2 = FAITHFUL[ranks]
        rows = rows_by_slice[ranks]
        t_grid_hi, t_grid_lo = rows[Fraction(1024)], rows[Fraction(64)]
        t_closed_lo = t_torus(A5_DMA_BYTES, r1, r2, Fraction(1))  # closed-form-only
        b_axis[f"slice_{ranks}"] = {
            "grid_64_to_1024_cct_span_pct": pct((t_grid_lo - t_grid_hi) / t_grid_lo),
            "whole_declared_range_1_to_1024_span_exact": str(t_closed_lo / t_grid_hi),
            "whole_declared_range_1_to_1024_span_float": float(t_closed_lo / t_grid_hi),
            "statement": "the executed anchor-blind grid {64..1024} moves anchor-shape CCT by only 2.41% (r=128) / 1.43% (r=256) — the regime is hop-latency-dominated; extending to the declared range lower endpoint B=1 (closed-form-only row, not executed) the whole span is 2.68x / 1.99x, still directionally unable to express the twist effect (see falsification_2)",
        }

    # shape-space context (executed committed bound rows)
    shape_rows = {}
    for sweep_id, ranks, shapes in ((SWEEP_ID_TORUS128, 128, SHAPES_128),
                                    (SWEEP_ID_TORUS256, 256, SHAPES_256)):
        by_name = {}
        for row in sweep_rows(sweep_id):
            topo = row["config_id"].split("-")[2]
            if "_a5_" not in topo or "_b50_" not in topo:
                continue
            b, shape, r = b_from_torus_id(topo)
            assert b == A5_READING1 and r == ranks
            name = f"{shape[0]}x{shape[1]}"
            by_name[name] = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert set(by_name) == set(shapes), (ranks, sorted(by_name))
        fastest = min(by_name, key=lambda k: (by_name[k], k))
        slowest = max(by_name, key=lambda k: (by_name[k], k))
        shape_rows[f"slice_{ranks}"] = {
            "times_at_anchor_B_exact": {k: str(v) for k, v in sorted(by_name.items())},
            "fastest_shape": fastest,
            "slowest_shape": slowest,
            "spread_exact": str(by_name[slowest] / by_name[fastest]),
            "spread_float": float(by_name[slowest] / by_name[fastest]),
        }
        assert shape_rows[f"slice_{ranks}"]["fastest_shape"] in (
            ("8x16", "16x16")[ranks == 256])

    ocs = {
        "staged": "Palomar OCS 136x136 ports (128 usable + 8 spare), path switching 'milliseconds'",
        "declared_lower_edge_ns": "1e6 (the conservative lower edge of the staged WORD — a declared interpretation, not a staged number)",
        "vs_per_hop_L_200_exact": str(A5_OCS_NS / L_REG),
        "vs_anchor_point_cct_slice128_exact": str(A5_OCS_NS / rows_by_slice[128][A5_READING1]),
        "vs_anchor_point_cct_slice256_exact": str(A5_OCS_NS / rows_by_slice[256][A5_READING1]),
        "bound": "OCS path switching is 5000x the per-hop latency and > 64x every CCT the identity emits in the anchor's regime: reconfiguration is QUASI-STATIC relative to collective completion — per plan §1.1 the OCS timescale CANNOT calibrate O-CCT; it bounds only dynamic-topology reconfiguration modeling, and the L0 topology schema is static by construction",
    }

    return {
        "role": "topology-sensitivity FALSIFIER (plan §1.1 row CAL-A5; plan §2.1 A-L0T-UNIF flag: 'torus-class calibration should treat CAL-A5 as the first falsifier of geometry abstractions >30%') + per-link BW anchor",
        "staged_signal": "TPU v4 measured twisted-vs-regular torus all-to-all ratios 1.63x (4x4x8, r=128) / 1.31x (4x8x8, r=256) at individual 4 KiB DMAs; per-link ICI 6 links @ 50 GB/s (direction convention UNVERIFIED — both readings executed); NO absolute (size -> time) series exists, so no CCT-vs-CCT comparison is defined",
        "split_role": "DEGENERATE (no series): the anchor's whole staged signal is fit-side; the split record defines NO within-series holdout for CAL-A5",
        "metric_discipline": "ratio vs ratio (the anchor's dimensionless geometry ratio vs the model's structural invariance ratio of exactly 1); all-to-all throughput and AllReduce CCT are never compared to each other — no mixed metric; the anchor's ratio is read onto the model's OWN anchor-point CCT only to compute what the ratio demands of the model",
        "falsifier": falsifier_rows,
        "axis_absorption_alternatives": absorption,
        "per_link_placement": placement,
        "b_axis_visibility": b_axis,
        "shape_space_context": {
            "rows": shape_rows,
            "note": "the model is NOT geometry-insensitive in general — its shape axis (factor-pair choice at fixed r, A-L0T-SHAPE) moves CCT by 2.84x / 4.18x at the anchor B, MORE than the twist effect — but along an axis orthogonal to twist: shape changes the latency chain 2(r1+r2-2), twist changes bisection structure. Recorded as context, NOT agreement",
        },
        "ocs_reconfiguration_bound": ocs,
        "inextractable_targets": [
            "absolute all-to-all completion times / throughputs — only the RATIOS are staged, so no CCT-vs-CCT comparison is defined (this stage never compares a model CCT against a CAL-A5 number)",
            "all-to-all as a model collective — the L0 torus identity executes ALLREDUCE only (backend capabilities); different collectives are never compared",
            "3D torus geometry — the model is 2D (A-L0T-SHAPE); the declared 3D->2D projection is declared in every topology file",
            "hybrid IB+ICI all-reduce penalty (1.8x-2.4x slower) — the paper's PROJECTION of an unbuilt alternative, recorded not used",
            "PaLM 57.8%-of-peak FLOPs — an FLOPs-utilization figure, not a fabric observable",
        ],
        "noise_scale_comparison_provenance": "the blind spots (63%/31%) are compared against CAL-A6's 5-8% software-version swing (a FIT-SET anchor, group G2) — 7.875x / 3.875x its upper edge; the split record's sole admitted holdout-adjacent exception (the ~5% mean-error scalar) is used ONCE here as tolerance-shape/noise-scale context per plan §3.4: 12.6x / 6.2x that band — an order above every noise scale in the anchor set, so the effect cannot be absorbed as measurement noise",
    }


# ---------------------------------------------------------------------------
# 2. The envelope sweep + the convergence law (cross-checks 4 and 5).
# ---------------------------------------------------------------------------
def envelope_sweep_block() -> tuple[dict, dict]:
    rows = {}
    for row in sweep_rows(SWEEP_ID_ENVELOPE):
        topo = row["config_id"].split("-")[2]
        b = b_from_xbar_id(topo)
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == t_xbar(row["payload_bytes"], b), (topo, row["payload_bytes"])
        assert row["algorithm"] == "allreduce_crossbar"
        rows[(topo, row["payload_bytes"])] = cct
    assert set(LADDER) == {m for (_t, m) in rows}

    by_b: dict[Fraction, dict[int, Fraction]] = {}
    for (topo, m), cct in rows.items():
        by_b.setdefault(b_from_xbar_id(topo), {})[m] = cct

    # cross-check 5: every carrier/edge B inside the declared range
    edge_bs = [e[0] for e in ENV_EDGES] + [c[0] for c in ENV_CARRIERS]
    for b in edge_bs:
        assert B_RANGE[0] <= b <= B_RANGE[1], b
        assert b in by_b, b

    # cross-check 4: the convergence law per edge
    law_rows = []
    for b_edge, b_carrier, factor, anchor, quote in ENV_EDGES:
        assert b_carrier / b_edge == factor, (b_edge, b_carrier, factor)
        ratios = [by_b[b_edge][m] / by_b[b_carrier][m] for m in LADDER]
        assert all(x < y for x, y in zip(ratios, ratios[1:])), (b_edge, "not monotone")
        assert all(r < factor for r in ratios), (b_edge, "exceeds asymptote")
        top = ratios[-1]
        law_rows.append({
            "anchor": anchor,
            "B_edge_exact": str(b_edge),
            "B_carrier_exact": str(b_carrier),
            "factor_exact": str(factor),
            "factor_float": float(factor),
            "quote": quote,
            "ratio_at_8kib_exact": str(ratios[0]),
            "ratio_at_8kib_float": float(ratios[0]),
            "ratio_at_8gib_exact": str(top),
            "ratio_at_8gib_float": float(top),
            "asymptotic_shortfall_exact": str(factor - top),
        })

    # the registry coincidence (anchor-blind placement context)
    reg_factor = Fraction(100) / B_REG
    edges_sorted = sorted({f for (_b, _c, f, _a, _q) in ENV_EDGES})
    below = [f for f in edges_sorted if f < reg_factor]
    above = [f for f in edges_sorted if f > reg_factor]

    executed = {
        "sweep_id": SWEEP_ID_ENVELOPE,
        "sweep_name": "cal_s5_envelope_v1",
        "manifest_path": "experiments/calibration/s5/sweep_s5_envelope_v1.yaml",
        "grid": "33 crossbar topologies (16 anchor-blind grid members + 3 carriers + 14 distinct edge/absolute rows) x 12 ladder sizes = 396 configs x 6 ops",
        "cross_check": "every executed row equals the crossbar closed form 7/4*M/B + 400 at the same (payload, B) — exact Fraction string equality (396/396)",
        "payload_fence": "the 12-size standard ladder 8 KiB..8 GiB (all fit-side; no G4 anchor carries a within-series split)",
        "carriers": [
            {"B_exact": str(b), "anchors": anchors, "role": role} for b, anchors, role in ENV_CARRIERS
        ],
        "convergence_law": {
            "statement": "for every degradation edge (B_e = carrier/f): the executed CCT ratio t_edge/t_carrier is STRICTLY INCREASING across the 12 ladder sizes, starts at 1 in the M->0 limit (latency-masked) and is bounded above by the exact asymptote f = B_c/B_e, reached only in the bandwidth-bound limit — a dimensionless congestion factor enters an affine identity only as an ASYMPTOTIC effective-B displacement; verified on executed rows for all 16 edge rows",
            "rows": law_rows,
        },
        "registry_placement_coincidence": {
            "registry_64_as_factor_over_carrier_100_exact": str(reg_factor),
            "float": float(reg_factor),
            "bracketed_by_executed_edges": [str(below[-1]), str(above[0])] if below and above else None,
            "statement": "as a displacement from the 100 B/ns carrier the registry 64 equals a factor of 25/16 = 1.5625 — strictly between the executed GF-07 edges 3/2 (the Nanjing pair 180/120) and 5/3 (steady incast 60%): a NUMERICAL COINCIDENCE (the registry point is anchor-free), recorded because it locates the shipped default inside the measured envelope's lower range",
        },
        "all_edges_inside_declared_range": "every executed carrier and edge B value (min 3.125 = GF-08's 8x edge, max 1024 = grid member) lies INSIDE the declared A-L0X-BW range [1, 1024] — the declared range ADMITS the whole envelope as effective-B displacement; the identity still predicts only the uncongested carrier row (no congestion term exists)",
    }
    return executed, by_b


# ---------------------------------------------------------------------------
# 3. The five envelope/context fits.
# ---------------------------------------------------------------------------
def fit_cal_a11(by_b: dict) -> dict:
    carrier_row = by_b[A11_CARRIER]
    edge_row = by_b[Fraction(35)]
    t_carrier = carrier_row[LADDER[-1]]
    t_edge = edge_row[LADDER[-1]]
    assert t_edge / t_carrier > 1
    return {
        "role": "context proxy (scale-out rail-optimized RoCE production fabric — the plan's labeled-proxy rule; NOT a GPU-to-GPU scale-up fabric)",
        "staged_signal": "path pinning degraded training 'up to more than 30%'; E-ECMP + QP scaling 'up to 40% improvement for the AllReduce collective'; 400G single-mode optics; two ~24,576-GPU clusters; Llama 3 on 16,000 GPUs; the anchor's per-collective throughput tables live in the paper PDF and are NOT staged (staging §A11)",
        "split_role": "DEGENERATE (no series): dimensionless envelope factors + an absolute optics rate",
        "carrier_placement": {
            "carrier_B_exact": str(A11_CARRIER),
            "registry_64_over_carrier_exact": str(B_REG / A11_CARRIER),
            "registry_64_over_carrier_pct": pct(B_REG / A11_CARRIER - 1),
            "executed_edge_B_35_exact": str(Fraction(35)),
            "executed_edge_factor_exact": str(1 / A11_DEGRADE),
            "recorded_not_executed_implied_baseline_exact": str(A11_IMPLIED_BASELINE),
            "improvement_factor_exact": str(A11_IMPROVE),
            "scale_context": "cluster scale 24,576 GPUs / training scale 16,000 recorded as staged arithmetic (stage A11 executed the r=24576 rows at E1); this stage's executions are r=8",
        },
        "where_the_model_sits": "the identity's prediction IS the uncongested carrier row (factor exactly 1): the anchor's 30-40% congestion/load-balance effects are STRUCTURALLY INEXPRESSIBLE — no congestion, load-balancing, or multi-plane routing semantics exist in the L0 input space. The proxy BOUNDS the cost of the omission (up to 30-40% on real production fabrics of a neighboring class); it does NOT falsify the scale-up identity (wrong domain, declared)",
        "improvement_direction_note": "the 'up to 40% improvement' edge points the OTHER way (a congestion-MANAGEMENT gain toward the uncongested reference the model already predicts) — both edges bracket the model's fixed point from opposite sides; neither is expressible as a prediction",
    }


def fit_gf05(by_b: dict) -> dict:
    l_hop_in_range = Fraction(10) <= GF05_L_HOP <= Fraction(2000)
    return {
        "role": "envelope sim+HW (R1+R3): the congestion control UEC standardized (SMaRTT = 'the algorithm that forms the basis of the UEC NSCC specification'; REPS = the UET 1.0 reference load-balancing mechanism) + sim-config provenance for the UEC profile",
        "staged_signal": "CC 'outperforms ... Swift, RoCE, and MPRDMA by up to 50%'; alltoall 'only up to 6% behind the ideal time'; 'up to 20% better than other sender-based schemes'; fairness 'slowest flow FCT 65% longer' (under Swift); HW permutation RoCE '3-5 times slower than optimal'; HW alltoall 'RoCEv2 is 3-6x slower'; EQDS 'up to 155x more trimmed packets'; trimming learns loss in 'roughly 84 us = 7 base RTTs'; sim config '4KiB MTU, 800 Gbps network bandwidth, 400ns switch traversal latency', link latency 600 ns; 1,024-node fat trees at 2:1/4:1/8:1 oversubscription; window clamped to 1.5 BDP; target RTT 1.5x base RTT",
        "split_role": "DEGENERATE (no series): FCT effect sizes + the sim configuration",
        "sim_config_provenance": {
            "B_line_exact": str(GF05_B_LINE),
            "B_alt_reading_recorded_exact": str(GF05_B_ALT),
            "L_per_hop_decomposition": {"switch_ns": str(GF05_SWITCH_NS), "link_ns": str(GF05_LINK_NS), "sum_ns": str(GF05_L_HOP)},
            "L_per_hop_in_declared_A_L0X_LAT_range": l_hop_in_range,
            "registry_200_over_anchor_1000_exact": str(L_REG / GF05_L_HOP),
            "base_rtt_exact_ns": str(GF05_BASE_RTT),
            "base_rtt_derivation": "84 us / 7 base RTTs, exact",
            "base_rtt_over_range_upper_exact": str(GF05_BASE_RTT / Fraction(2000)),
            "target_rtt_exact_ns": str(GF05_TARGET_RTT),
            "bdp_exact_bytes": str(GF05_BDP),
            "window_1_5_bdp_exact_bytes": str(GF05_WINDOW),
            "mtu_serialization_exact_ns": str(Fraction(GF05_MTU) / GF05_B_LINE),
            "statement": "the anchor's per-hop L = 1000 ns (400 switch + 600 link) sits INSIDE the declared A-L0X-LAT range [10, 2000] — the ONLY UEC-class latency figure in the corpus, and it is a SIMULATION configuration, not silicon; the registry point 200 ns is exactly 1/5 of it; the RTT-scale figures (12,000 / 18,000 ns) sit 6x/9x above the range upper — they quantify CC reaction scales, a different quantity class (the CAL-A9 decomposition / GF-05 lumped-L expressiveness loss, carried)",
            "executed_run": "run f96b688c... at the anchor's OWN sim config (B=100, L=1000, 2 MiB) on the committed stage-GF-05 topology — anchor-CONFIG provenance, never a fit",
        },
        "effect_size_envelope": {
            "cc_gain_up_to_50pct_primary_factor_3_2": "displaced B = 100/(3/2) = 200/3 — NOT representable, recorded",
            "cc_gain_alt_reading_factor_2": "'50% faster' read as x2 => displaced B = 50, EXECUTED (shared with the 2:1 oversubscription row)",
            "alltoall_6pct_behind_ideal_factor_53_50": "the model sits AT the anchor's OWN 'ideal time' reference by construction — this 6% edge is the anchor's own distance-from-ideal of a REALIZED system, the exact quantity the identity cannot move off zero",
            "alltoall_20pct_better_factor_6_5": "displaced 250/3, recorded",
            "fairness_65pct_factor_33_20": "a DISTRIBUTIONAL metric (slowest-vs-fastest flow) — no per-flow axis exists in the identity at all; recorded, not displaced",
            "roce_perm_3_to_5x": "5x EXECUTED (B=20, shared); 3x => 100/3 recorded",
            "roce_alltoall_3_to_6x": "6x => 50/3 recorded; 4:1 and 8:1 oversubscription rows EXECUTED at 25 / 12.5",
            "eqds_trim_155x": "a protocol-behavior count, not a time or rate metric — inexpressible; recorded",
            "trimming_84us_equals_7_base_rtts": "a CC reaction-time scale (7x the 12 us base RTT), not a collective quantity; recorded",
        },
        "where_the_model_sits": "the L0 identity IS the anchor's 'ideal time' reference (factor exactly 1) — the UEC-standardized CM's measured 20-50% gains and RoCE's 3-6x distances are both defined RELATIVE to the row this model predicts; every CM delta is structurally inexpressible (no congestion control, no load balancing, no trimming, no window/BDP semantics exist in the input space). These effect sizes BOUND what any UEC-profile congestion-semantics modeling must reproduce — the split record's exact duty assignment",
        "domain_caveats": "peer-reviewed SIMULATION (uet-htsim, the family pre-pinned as the repo's third backend) + a small DPDK hardware testbed — NOT UEC silicon; FCT metrics, not collective CCTs (the regime bridge is declared, never assumed)",
    }


def fit_gf07(by_b: dict) -> dict:
    ar_effect = F_ALLREDUCE - 1
    return {
        "role": "envelope MEASURED (R3): the 5% -> 25x collective-slowdown falsification envelope across five HPC fabrics — the measured magnitudes any congestion-effect model must fall inside; direct evidence for plan gap 7 (no scale-up-domain congestion anchor exists)",
        "staged_signal": "CRESCO8 steady-incast AllToAll victims 'slowdowns up to 25x'; steady incast 'dropping to 60%'; bursty incast 64 nodes ratio ~0.08 (12x slower gloss); bursty alltoall 'drops to 70%'; Leonardo incast ratios 'collapse to 0.2' at 32-64 nodes; LUMI 'always within 5%'; Nanjing victim AllToAll 180 Gb/s peak, 120 Gb/s NSLB-off; 'Open MPI AllReduce showed up to a 25% bandwidth loss'; effects appear 'even at ~2% of a partition'; fabrics: Leonardo HDR IB Dragonfly+, CRESCO8 NDR IB 1.67:1 fat tree, LUMI Slingshot Dragonfly, HAICGU EDR IB+RoCE, Nanjing RoCE NSLB",
        "split_role": "DEGENERATE (no series): measured bandwidth-ratio effects across fabrics",
        "envelope_table_exact": {
            "floor_20_over_19": "LUMI (per-flow HW CM + global-aware adaptive routing) — EXECUTED at B=95 on carrier 100",
            "allreduce_class_4_over_3": "the anchor's ONE AllReduce-class quote — EXECUTED at B=75; its 1/3 effect is 25/6 x CAL-A6's 8% software-version noise floor (a fit-set comparison)",
            "bursty_alltoall_10_over_7": "EXECUTED at B=70",
            "steady_incast_5_over_3": "EXECUTED at B=60",
            "leonardo_collapse_5": "EXECUTED at B=20 on the LUMI carrier AND at B=10 on Leonardo's OWN 50 — the carrier-invariance statement (the envelope is a RATIO axis)",
            "bursty_incast_25_over_2": "the staged ratio '0.08' read exactly — EXECUTED at B=8; the paper's '12x' gloss => 100/12 recorded",
            "ceiling_25": "CRESCO8 'up to 25x' — EXECUTED at B=4",
            "absolutes": "Nanjing peak 22.5 / NSLB-off 15 B/ns (measured absolute rates, exact pair factor 180/120 = 3/2) — EXECUTED",
            "span_floor_to_ceiling_exact": str(GF07_ENVELOPE_SPAN),
            "span_float": float(GF07_ENVELOPE_SPAN),
        },
        "where_the_model_sits": "the identity's prediction IS the uncongested carrier row — factor exactly 1 at every size, i.e. AT the envelope's reference point, with the whole measured 5% -> 25x span (a 23.75x floor-to-ceiling ratio) structurally inexpressible: no congestion, incast, adaptive-routing, or HW-CM term exists. The nearest edge to O-CCT (the AllReduce 4/3 quote) alone exceeds CAL-A6's 8% software-version noise floor by 25/6 — an unabsorbable miss class",
        "domain_caveats": "MEASURED, but on scale-out HPC fabrics (IB Dragonfly+, Slingshot, RoCE) under a victim-collective methodology (1000 iterations, 100 warmup discarded) — staged under the labeled-proxy rule; metrics are collective bandwidth ratios, not O-CCT series; the ~2%-of-partition onset has no model-side counterpart (no background-traffic axis exists)",
        "carrier_note": "the LUMI carrier (100 B/ns) coincides with GF-05's sim line rate — two anchors, one executed row (both declared in the topology header); the envelope's factors are what the two anchors independently measured at their own carriers",
    }


def fit_gf08(by_b: dict) -> dict:
    return {
        "role": "envelope HW transport (R1): the hardware bookend — a SHIPPED UEC-class hardware transport (Falcon on commodity lossy PFC-free Ethernet, Intel IPU E2000), architecturally the closest shipped relative of UEC's UET design points",
        "staged_signal": "'peak performance of 200 Gbps, 120 Mops/sec'; 'operation completion times 8x lower than CX-7 RoCE under network congestion'; 'up to 65% higher goodput under lossy conditions' (official abstract, verified via the MSR mirror; full paper tables NOT extracted at staging — ACM 403 in the staging sandbox)",
        "split_role": "DEGENERATE (no series): headline rates + dimensionless deltas",
        "carrier_placement": {
            "carrier_B_exact": str(GF08_B_FALCON),
            "alt_carrier_B_exact": str(GF08_B_ALT),
            "reading": "200 Gbps per-endpoint per-direction (Ethernet full-duplex convention); the bidirectional-aggregate alternative is exactly x2 down and is EXECUTED as the 12.5 row (shared)",
            "registry_64_over_carrier_exact": str(B_REG / GF08_B_FALCON),
            "registry_64_over_carrier_float": float(B_REG / GF08_B_FALCON),
            "executed_8x_edge_B_exact": str(GF08_B_FALCON / GF08_F_CONGESTION),
            "recorded_65pct_edge_exact": "500/33 (25 / 33/20) — NOT representable, recorded",
        },
        "ops_rate_axis_inexpressible": {
            "ops_per_ns_exact": str(GF08_OPS_PER_NS),
            "per_op_time_ns_exact": str(GF08_T_PER_OP),
            "bytes_per_op_exact": str(GF08_BYTES_PER_OP),
            "implied_pair_L_exact": str(GF08_L_IMPLIED),
            "implied_pair_L_float": float(GF08_L_IMPLIED),
            "implied_L_vs_range_lower": "25/6 < 10 — the per-op rate implies a pair latency BELOW the declared A-L0X-LAT range's lower endpoint",
            "floor_over_per_op_at_range_lower_exact": str(Fraction(2 * 10) / GF08_T_PER_OP),
            "floor_over_per_op_at_registry_exact": str(Fraction(2 * 200) / GF08_T_PER_OP),
            "statement": "the '120 Mops/sec' headline is an OPERATIONS-RATE metric: at EVERY admissible L the identity's minimum per-op completion 2L >= 20 ns exceeds the anchor's 25/3 ns/op (floor/per-op = 12/5 exactly at the range lower endpoint, 48 at the registry pair) — a per-operation completion-time metric is structurally inexpressible in a collective-CCT identity (no per-op/operation-rate axis exists)",
            "staging_gloss_check": "the staging doc's own '~6 ns/operation amortized' gloss equals 1/120e6 s per op to 3 significant figures — a rate statement, not a latency; the 200 Gbps / 120 Mops pair is self-consistent only as bytes/op = 625/3 ~ 208 B (small-message regime), which the identity reaches only through its M/B wire term at M ~ 208 B — an M the smoke manifests never execute",
        },
        "where_the_model_sits": "factor exactly 1 (uncongested carrier row): the 8x congestion delta and the 65% lossy-goodput delta are structurally inexpressible — no congestion, loss, retransmission, or multipath-spraying semantics exist in the identity; the deltas bound what a UET-class transport's congestion/loss handling buys over RoCE, i.e. the envelope a UEC-profile transport model must reproduce",
        "domain_caveats": "endpoint/NIC-class transport on scale-out Ethernet — not GPU scale-up, not UEC silicon; headline abstract-level numbers only (staging confidence M-H: verified against the official abstract mirror; full tables unextracted)",
    }


def fit_gf09(by_b: dict) -> dict:
    return {
        "role": "design-target CEILING (R1 design-target class; the split record's role annotation: 'ceiling/target class, same discipline as CAL-A1/A2: never achieved values')",
        "staged_signal": "UE 'is designed to operate at high bandwidths (400+ Gbps) over medium-length (10-150m) links'; local networks target 'sub-microsecond latency'; CC discussion assumes 'target round-trip times of 10 us'; receiver ACKs carry 'a 64-bit SACK bitmap'; NSCC receiver feedback is 'an 8B congestion window penalty value'; CBFC uses 'two 20-bit cyclic counters'; RCCC 'assigns 25% of the bandwidth to each' of 4 incast flows; an oversubscription bottleneck 'can only satisfy 33% of the bandwidth'; UEC CM 'is designed and tested in simulation' (evaluation deferred to the GF-05 paper)",
        "split_role": "DEGENERATE BY CLASS: a design target is not data — there is NO fit signal and NO fit objective can exist",
        "how_a_design_target_constrains_a_fit": {
            "constraint_on_fit_values": "NONE. A design target is an ASPIRATIONAL outcome, not a measurement of any built system: it has ZERO falsification power (no model output can be tested against it — a model predicting below a target has not 'missed' anything, because nothing was achieved to miss), it can seed NO fit objective, NO tolerance, and NO swept-value provenance. This stage derives no fitted value from GF-09 and asserts that none may ever be",
            "normalization_only_use": "the CAL-A1/A2 discipline, with the OPPOSITE bounding direction: CAL-A1/A2 are spec CEILINGS (achieved values stay below them), while '400+ Gbps' is an open-ended class FLOOR — the '+' states no upper bound at all. It therefore bounds the admissible scale of any future UEC-PROFILE configuration from below (a UEC-profile run at B < 50 B/ns under the declared per-direction reading would sit below the design class its profile names), and bounds nothing from above. The sub-microsecond latency target (boundary edge 1000 ns) and the 10 us target RTT (5000 ns charged as 2L) locate the LATENCY REGIME a UEC-profile model must operate in — as context, never as achieved or achievable values",
            "registry_placements": {
                "design_class_floor_B_exact": str(GF09_B_UEC),
                "alt_reading_B_exact": str(GF09_B_ALT),
                "registry_64_over_class_floor_exact": str(B_REG / GF09_B_UEC),
                "subus_boundary_ns": str(GF09_SUBUS_NS),
                "registry_200_inside_subus_at_exact": str(L_REG / GF09_SUBUS_NS),
                "target_rtt_charged_2L_ns": str(GF09_L_RTT_CHARGED),
                "target_rtt_over_declared_range_upper_exact": str(GF09_L_RTT_CHARGED / Fraction(2000)),
                "range_not_moved": "the 10 us target RTT lies OUTSIDE the declared A-L0X-LAT range [10, 2000] at 2.5x its upper endpoint — a RECORDED PLACEMENT; the registry range is NOT moved by design-target material (design targets constrain nothing)",
                "propagation_bounds_declared_physics": {
                    "10m_at_5ns_per_m_exact_ns": str(GF09_LINK_M[0] * GF09_FIBER_NS_PER_M),
                    "150m_at_5ns_per_m_exact_ns": str(GF09_LINK_M[1] * GF09_FIBER_NS_PER_M),
                    "note": "5 ns/m is a DECLARED engineering constant (~2/3 c, typical fiber), never an anchor- or standard-derived value; both bounds lie inside the declared range — the only GF-09 latency figures that do, and they are declared physics, not targets",
                },
            },
            "protocol_constants_recorded": {
                "sack_bitmap_bits": GF09_SACK_BITS,
                "nscc_feedback_bytes_exact": str(GF09_NSCC_FB_B),
                "cbfc_counter_bits": GF09_CBFC_BITS,
                "bdp_at_target_rtt_exact_bytes": str(GF09_BDP_AT_TARGET),
                "feedback_over_bdp_exact": str(GF09_NSCC_FB_B / GF09_BDP_AT_TARGET),
                "note": "scale context only: protocol-constant arithmetic (feedback bytes vs BDP at the target RTT) enters no model parameter in this stage",
            },
            "worked_examples_executed": {
                "rccc_B_exact": str(GF09_B_UEC * GF09_RCCC_SHARE),
                "rccc_factor_exact": str(1 / GF09_RCCC_SHARE),
                "oversub_B_exact": str(GF09_B_UEC * GF09_OVERSUB_SATISFY),
                "oversub_factor_exact": str(1 / GF09_OVERSUB_SATISFY),
                "note": "the paper's OWN worked arithmetic (25% x 4 flows => factor 4 exactly; 33% => 100/33), executed as displacement rows on the design-class carrier — the paper's examples, never our fits; the 1/3 oversubscription reading (50/3) recorded not executed",
            },
        },
        "cm_evaluation_deferral": "the anchor's own text: UEC CM 'is designed and tested in simulation' — its evaluation is deferred to the simulation study it cites (the GF-05 material, fitted separately above); GF-09 itself stages NO measurement of any kind",
        "provenance_fence": "public arXiv design-principles paper by consortium participants — NOT a specification document; nothing was ingested from ultraethernet.org; confidence M (targets and worked examples, not measurements)",
    }


# ---------------------------------------------------------------------------
# 4. Store-run cross-checks (cross-check 2).
# ---------------------------------------------------------------------------
def run_summary(run_key: str, mapping: str, target: str) -> dict:
    run_id = RUN_IDS[run_key]
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]
    payload = per_op["payload_bytes"]
    cct = Fraction(per_op["completion_time_ns_exact"])
    model = obs["model"]
    if obs["backend_id"] == "analytical_l0_crossbar":
        b = Fraction(model["injection_bytes_per_ns_exact"])
        l_val = Fraction(model["pair_latency_ns_exact"])
        expected = t_xbar(payload, b, l_val)
        identity = f"crossbar (B={b}, L={l_val})"
    else:
        b = Fraction(model["link_bytes_per_ns_exact"])
        l_val = Fraction(model["hop_latency_ns_exact"])
        expected = t_torus(payload, model["dim1_ranks"], model["dim2_ranks"], b, l_val)
        identity = f"torus2d {model['dim1_ranks']}x{model['dim2_ranks']} (B={b}, L={l_val})"
    assert cct == expected, (run_key, cct, expected)
    assert run["manifest"]["experiment_id"] == RUN_EXPERIMENT_IDS[run_key]
    assert run.get("evidence_schema_version") == 2
    assert run.get("calibration_target") == [target]
    assert run.get("held_out", {}).get("held_out") is False
    return {
        "run_id": run_id,
        "calibration_target": [target],
        "mapping": mapping,
        "experiment_id": RUN_EXPERIMENT_IDS[run_key],
        "identity": identity,
        "payload_bytes": payload,
        "cct_ns_exact": str(cct),
        "cct_ns_float": float(cct),
        "held_out": False,
        "verdict": "store run == closed form of the same identity function (exact Fraction string equality); v2 dimensions as declared (held_out: false)",
    }


def store_run_cross_checks() -> list[dict]:
    specs = [
        ("a5_slice128", "CAL-A5 falsifier anchor-side reference: the faithful 8x16 projection at B=50 (reading 1), L=200, payload 4096", "CAL-A5"),
        ("a5_slice256", "CAL-A5 falsifier anchor-side reference: the faithful 8x32 projection at B=50 (reading 1), L=200, payload 4096", "CAL-A5"),
        ("a11_carrier", "CAL-A11 context-proxy carrier row: B=50 (400G optics per-direction), L=200, payload 8 GiB, r=8", "CAL-A11"),
        ("gf05_simconfig", "GF-05 anchor-CONFIG provenance: the anchor's OWN sim config B=100, L=1000 (400 switch + 600 link), payload 2 MiB, r=8", "GF-05"),
        ("gf07_carrier", "GF-07 measured-envelope carrier row: B=100 (LUMI per-node aggregate), L=200, payload 16 MiB, r=8", "GF-07"),
        ("gf08_falcon", "GF-08 hardware-transport carrier row: B=25 (Falcon 200 Gbps per-endpoint), L=200, payload 16 KiB, r=8", "GF-08"),
        ("gf09_uec50", "GF-09 design-target ceiling placement: B=50 (the '400+' class floor), L=200, payload 2 MiB, r=8 — a placement, never a fit", "GF-09"),
    ]
    return [run_summary(k, m, t) for k, m, t in specs]


# ---------------------------------------------------------------------------
# 5. Torus sweep blocks (executed-sweep reconciliation for the falsifier).
# ---------------------------------------------------------------------------
def torus_sweep_block(sweep_id: str, ranks: int, name: str, manifest: str) -> dict:
    faithful_shape = FAITHFUL[ranks]
    rows = []
    n = 0
    for row in sweep_rows(sweep_id):
        topo = row["config_id"].split("-")[2]
        b, shape, r = b_from_torus_id(topo)
        assert r == ranks and row["payload_bytes"] == A5_DMA_BYTES
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == t_torus(A5_DMA_BYTES, shape[0], shape[1], b)
        is_faithful = shape == faithful_shape
        rows.append({
            "topology_id": topo,
            "B_exact": str(b),
            "shape": f"{shape[0]}x{shape[1]}",
            "faithful_projection": is_faithful,
            "grid_member": b in GRID_B and is_faithful,
            "cct_ns_exact": str(cct),
            "latency_chain_ns_exact": str(torus_latency_chain(shape[0], shape[1])),
            "latency_share_exact": str(torus_latency_chain(shape[0], shape[1]) / cct),
        })
        n += 1
    assert n == (22 if ranks == 128 else 23), n
    return {
        "sweep_id": sweep_id,
        "sweep_name": name,
        "manifest_path": manifest,
        "grid": f"{n} configs x 6 ops at payload 4096 (the anchor's DMA size)",
        "cross_check": "every executed row equals the torus closed form at the same (payload, shape, B, L=200) — exact Fraction string equality",
        "payload_fence": "single payload 4096 = the anchor's individual DMA size (fit-side; no within-series holdout exists for CAL-A5)",
        "rows": rows,
        "row_families": {
            "anchor_readings": "B in {20, 25, 50} on the committed stage-A5 faithful-shape topologies (direction-convention readings; 64 = the registry point is a grid member)",
            "anchor_blind_grid": f"B in {{64, 128, ..., 1024}} at the faithful {faithful_shape[0]}x{faithful_shape[1]} projection (s5-authored)",
            "twist_displacement": f"B = {float(A5_READING1 * A5_TWIST[ranks])} = 50 x {A5_TWIST[ranks]} (the anchor's own ratio absorbed into B; declared misattribution, never selected)",
            "shape_bounds": "the committed stage-A5 bound shapes at B=50 (shape-axis context)",
        },
    }


# ---------------------------------------------------------------------------
# 6. Evidence dimensions + assembly.
# ---------------------------------------------------------------------------
def evidence_dimensions_block() -> dict:
    return {
        "verification": [
            {
                "check": "tests/calibration/test_s5_fit.py",
                "scope": "S5 fit guard — re-executes the three S5 sweeps and the seven S5 runs into a scratch store, rebuilds this record byte-identically, and checks the separation invariants (anchor-blind grid membership in both axes' sweeps; no holdout anchor id anywhere in the record bytes; the A-L0T-BW/A-L0X-BW registry values untouched at 64/[1,1024]; the falsifier's below-the-floor arithmetic exact; the envelope convergence law monotone; every envelope edge inside the declared range)",
            },
            {
                "check": "tests/calibration/test_anchor_split.py",
                "scope": "the split record's own immutability guard (S1) — the data separation this fit runs under",
            },
        ],
        "calibration_target": ["CAL-A5", "CAL-A11", "GF-05", "GF-07", "GF-08", "GF-09"],
        "held_out": {
            "held_out": False,
            "scope": "the S5 checks and every swept/executed value here touch only the group-G4 staged signals: CAL-A5's geometry ratios and per-link readings, CAL-A11's envelope factors and optics rate, GF-05's effect sizes and sim config, GF-07's measured envelope, GF-08's headline deltas and rates, GF-09's design targets — the split record defines NO within-series holdout for any of the six, so every row is fit-side and no held-out reporting run exists in this stage",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "NO congestion, load-balance, incast, or congestion-control semantics exist in ANY L0 identity: the whole measured 5%->25x envelope (GF-07), the 30-40% production effects (CAL-A11), the 20-50% UEC-NSCC gains and 3-6x RoCE distances (GF-05), and the 8x/65% transport deltas (GF-08) are structurally inexpressible — the model sits at factor exactly 1 (the uncongested reference) by construction; the fourth structural-omission axis of the fit family (with S2's software-effective bandwidth ramp, S3's software-version/fabric-asymmetry axes, S4's missing software-latency term)",
            "NO geometry field exists in the torus input space: CAL-A5's measured 31-63% twisted-vs-regular effect is inexpressible (model ratio exactly 1), the B axis delivers at most 5.4%/6.4% of the required gain even unbounded, and the in-range L absorption would misattribute bisection structure to hop latency — flagged, never selected",
            "GF-08's operations-rate metric (120 Mops/s => 25/3 ns/op) is inexpressible from below: the implied pair latency 25/6 ns lies below the declared range lower 10 ns and the identity's 2L floor exceeds the per-op time at every admissible L — no per-op axis exists in a collective-CCT identity",
            "GF-05's (switch 400, link 600) per-hop decomposition is not expressible in the lumped L (the CAL-A9 expressiveness-loss class); fairness (65% slowest-vs-fastest) is distributional — no per-flow axis exists",
            "GF-09 is design-target material: zero falsification power, normalization-only use (an open-ended class FLOOR, opposite direction to the CAL-A1/A2 ceilings); the 10 us target RTT (5000 ns as 2L) lies outside the declared latency range — recorded, the range NOT moved",
            "CAL-A11 and GF-07 are scale-out fabrics staged under the labeled-proxy rule — no scale-up-domain congestion measurement exists anywhere (plan gap 7); FCT (GF-05) and bandwidth-ratio (GF-07) metrics are not collective CCTs (declared regime bridges, never assumed)",
            "no software/endpoint latency term, no packetization, no multi-port injection, no in-network reduction, no reconfiguration (static topologies; OCS switching is quasi-static at >= 1e6 ns) — the standing L0 transport-model omissions",
        ],
    }


def envelope_summary(by_b: dict) -> dict:
    worst_edge = by_b[Fraction(4)]
    carrier = by_b[Fraction(100)]
    ratio_bottom = worst_edge[LADDER[0]] / carrier[LADDER[0]]
    ratio_top = worst_edge[LADDER[-1]] / carrier[LADDER[-1]]
    return {
        "the_one_sentence_where_the_model_sits": "every G4 envelope anchor measures effects RELATIVE to the uncongested reference row that the L0 identity predicts by construction (factor exactly 1 at every size): the model is the envelope's ORIGIN, and the measured spans around that origin (5%..25x collectives; 30-40% production load-balance; 20-50% CC gains / 3-6x RoCE; 8x/65% transport deltas; 31-63% geometry) are all structurally outside its input space",
        "delivered_fractions_and_spans": {
            "gf07_envelope_span_floor_to_ceiling_exact": str(GF07_ENVELOPE_SPAN),
            "allreduce_class_edge_effect_exact": str(F_ALLREDUCE - 1),
            "allreduce_edge_over_cal_a6_8pct_exact": str((F_ALLREDUCE - 1) / CAL_A6_SWING_UPPER),
            "a5_blind_spans_exact": {k: str(v - 1) for k, v in A5_TWIST.items()},
        },
        "convergence_law_consequence": (
            f"a dimensionless congestion factor enters the affine identity only as an "
            f"ASYMPTOTIC effective-B displacement (the executed law): the worst 25x edge "
            f"executes at {float(ratio_bottom):.3f}x ({str(ratio_bottom)} exactly) at the "
            f"8 KiB ladder bottom and reaches {float(ratio_top):.6f}x at 8 GiB "
            f"(asymptotic shortfall {str(F_WORST - ratio_top)}) — any future "
            "congestion-semantics modeling must be size-aware, and small-message "
            "congestion costs are latency-masked in exactly the regime the smoke "
            "manifests exercise"
        ),
        "range_admittance_statement": "every executed carrier and edge B value lies inside the declared A-L0X-BW range [1, 1024] (min 3.125): the DECLARED RANGE admits the whole envelope as displacement; the SHIPPED VALUE (64) does not move, and the identity predicts none of the displaced rows",
    }


def build_record() -> dict:
    torus128 = torus_sweep_block(SWEEP_ID_TORUS128, 128, "cal_s5_torus128_v1",
                                 "experiments/calibration/s5/sweep_s5_torus128_v1.yaml")
    torus256 = torus_sweep_block(SWEEP_ID_TORUS256, 256, "cal_s5_torus256_v1",
                                 "experiments/calibration/s5/sweep_s5_torus256_v1.yaml")
    envelope, by_b = envelope_sweep_block()
    a5 = fit_cal_a5()
    evidence = evidence_dimensions_block()
    record = {
        "record_kind": "calibration_fit",
        "stage": "calibration fit record, S5 (group G4 — torus-geometry falsifier + UEC-class transport / congestion-management envelopes)",
        "status": "PROPOSED — owner adjudication required; no claim, label, or shipped parameter value changes; no O-CCT fit exists in this group and none is claimed",
        "evidence_schema_version": 2,
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay reproduces byte-identical artifacts)",
            "fit": "PROPOSED envelope/context checks and a structural falsification against external published ratios, factors, rates, and design targets; no E3/E4 language — none of the anchors is our testbed, and owner adjudication precedes any label move",
        },
        "calibration_target": ["CAL-A5", "CAL-A11", "GF-05", "GF-07", "GF-08", "GF-09"],
        "split_record": {
            "record_id": "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20",
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "group": "G4 — torus-geometry falsifier + UEC-class transport / congestion-management envelopes (fitting stage S5)",
            "within_series_rules": "NONE of the six G4 anchors carries a within-series split (the split record's within_series_splits lists only CAL-A3/CAL-A6/GF-02/GF-04); every staged anchor signal is fit-side and no held-out reporting run exists in this stage",
            "parameter_axes_duty": "A-L0T-UNIF geometry-abstraction falsification duty (plan §2.1 flag, executed in fits.cal_a5); CM effect-size envelopes bound what congestion semantics modeling must reproduce (executed in the envelope sweep + the five envelope fits); A-AS2-* adapter entries stay in their own registry (untouched by this stage)",
            "no_leakage": "none of the split record's cross-anchor holdouts or its blocked anchor is read by any objective, swept value, or tolerance in this record (mechanically asserted: their ids appear nowhere in the record bytes); sole recorded exception used: the ~5% mean-error scalar as noise-scale/tolerance-SHAPE context, exactly once, in fits.cal_a5.noise_scale_comparison_provenance",
        },
        "model": {
            "backend_ids": ["analytical_l0_torus2d", "analytical_l0_crossbar"],
            "identities": {
                "torus2d": "t_2d(M,r1,r2) = sum_d [2(k_d-1)/k_d*M/B + 2(k_d-1)*L] — at the faithful projections 8x16/8x32, M=4096, L=200: wire coefficients 29/8 and 59/16 (14848/B and 15104/B ns), latency chains 8800 and 15200 ns",
                "crossbar": "t = 2(r-1)/r*M/B + 2L = 7/4*M/B + 400 ns at r=8, L=200",
            },
            "assumptions": "A-L0T-SEQ / A-L0T-UNIF / A-L0T-SHAPE / A-L0T-BW / A-L0T-LAT / A-L0T-DIV (torus), A-L0X-PORT / A-L0X-BW / A-L0X-LAT / A-L0X-DIV (crossbar) — experiments/vertical_slice/assumptions_l0.yaml",
            "declared_free_parameters": {
                "A-L0T-BW": {"parameter": "link.bytes_per_ns", "registry_value": 64,
                             "registry_range": [1, 1024], "swept_by": "the S5 torus sweeps (the falsifier's axis)"},
                "A-L0X-BW": {"parameter": "nic.injection_bytes_per_ns", "registry_value": 64,
                             "registry_range": [1, 1024], "swept_by": "the S5 envelope sweep (the envelope anchors' displacement axis)"},
                "registry_note": "both registry VALUES stay 64 B/ns — UNCHANGED by this stage; the grids are anchor-blind (uniform 64-multiples 64..1024); L stays at the A-L0X-LAT/A-L0T-LAT registry 200 ns on every S5-authored row (the GF-05 run's L=1000 is the anchor's OWN sim config on a committed stage file — anchor-CONFIG provenance, never a fitted value)",
            },
        },
        "group_g4_anchors": {
            "fit_targets": [
                "CAL-A5 — TPU v4 (ISCA 2023) twisted-vs-regular torus ratios 1.63x/1.31x + 6x50 GB/s ICI (falsifier; staging §A5; H, direction convention unverified)",
                "CAL-A11 — Meta SIGCOMM 2024 RoCE production fabric 30-40% congestion/load-balance envelope (context proxy; staging §A11; M-H, scale-out labeled proxy)",
                "GF-05 — SMaRTT/REPS (NSDI 2025) UEC-standardized CC effect sizes 20-50%/3-6x + the uet-htsim sim config (envelope sim+HW; gapfill §GF-05; H, FCT metrics)",
                "GF-07 — congestion impact across 5 HPC fabrics, 5% -> 25x measured envelope (envelope measured; gapfill §GF-07; H, scale-out labeled proxy)",
                "GF-08 — Falcon (SIGCOMM 2025) 200 Gbps / 120 Mops/s + 8x/65% deltas (envelope HW transport; gapfill §GF-08; M-H, abstract-level)",
                "GF-09 — Ultra Ethernet design-principles targets 400+ Gbps / sub-us / 10 us RTT (design-target ceiling; gapfill §GF-09; M, never achieved values)",
            ],
            "no_oct_fit_exists": "none of the six stages a collective (size -> time) series: CAL-A5 stages a ratio, the envelope anchors stage factors/rates/targets — the split record's own words ('envelope/context checks, not O-CCT fits') are this record's method; every 'fit' below is a placement, an envelope check, or a classified structural miss",
        },
        "executed_sweeps": {"torus128": torus128, "torus256": torus256, "envelope": envelope},
        "fits": {
            "cal_a5": a5,
            "cal_a11": fit_cal_a11(by_b),
            "gf05": fit_gf05(by_b),
            "gf07": fit_gf07(by_b),
            "gf08": fit_gf08(by_b),
            "gf09": fit_gf09(by_b),
        },
        "envelope_summary": envelope_summary(by_b),
        "not_tuned": "the sweep grids were fixed by registry-range arithmetic (uniform 64-multiples) and the anchor rows by the anchors' OWN staged figures before any deviation was computed; the falsifier's displacement and absorption alternatives are executed/recorded diagnostics, never selected; no envelope edge, carrier, or design target moved any registry value; no fit objective existed to tune toward (no G4 anchor stages a series); the registry values stay 64 across A-L0T-BW and A-L0X-BW and 200 across the latency parameters; no manifest outside this calibration directory carries any anchor figure",
        "held_out": {
            "held_out": False,
            "scope": "all seven stage runs and all three sweeps are fit-side (the split record defines no within-series holdout for any G4 anchor); the stage's structural-miss findings (twist blindness, congestion blindness, ops-rate inexpressibility) are REPORTED classifications at anchor points fixed before evaluation, never tuned targets",
        },
        "store_run_cross_checks": store_run_cross_checks(),
        "verification": evidence["verification"],
        "known_omissions": evidence["known_omissions"],
        "independent_reproduction": evidence["independent_reproduction"],
        "backing": {
            "run_ids": [RUN_IDS[k] for k in RUN_IDS],
            "run_roles": dict(RUN_ROLES),
            "sweep_ids": [SWEEP_ID_TORUS128, SWEEP_ID_TORUS256, SWEEP_ID_ENVELOPE],
            "inputs": [
                "experiments/calibration/s5/sweep_s5_torus128_v1.yaml",
                "experiments/calibration/s5/sweep_s5_torus256_v1.yaml",
                "experiments/calibration/s5/sweep_s5_envelope_v1.yaml",
                "experiments/calibration/s5/run_s5_*.yaml (7 manifests)",
                "experiments/calibration/s5/topologies/ (67 files)",
                "experiments/calibration/s5/profiles/ (2 files)",
                "experiments/calibration/a5/topologies/{torus2d128_a5_8x16_b20,b25,b50,4x32_b50,2x64_b50, torus2d256_a5_8x32_b20,b25,b50,4x64_b50,2x128_b50,16x16_b50}_v1.yaml and a5 workloads (committed stage-A5 files, reused as anchor-CONFIG provenance)",
                "experiments/calibration/{a11,gf05,gf07,gf08,gf09}/ committed files reused in the runs (the anchors' own carrier/sim-config topologies and payloads)",
                "experiments/workloads/w1_dense_tp_decode_small.yaml (the committed smoke workload, envelope sweep ladder base)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/s5/sweep_s5_torus128_v1.yaml ; make sweep EXP=experiments/calibration/s5/sweep_s5_torus256_v1.yaml ; make sweep EXP=experiments/calibration/s5/sweep_s5_envelope_v1.yaml ; make run EXP=(each of the seven run_s5_*.yaml manifests) ; python experiments/calibration/s5/build_fit_record.py",
            "s6_handoff": "this stage adds NO fitted parameter configuration (no G4 anchor stages a series, so there is nothing to fit): S6 runs the S2-S4 fitted configurations against the holdout untouched; G4 hands S6/S7 its recorded diagnostics — the CAL-A5 per-link readings {20, 25, 50} inside the plan span with the registry at 32/25 above reading 1; the falsifier facts (structural blindness; B-axis delivered fractions 23200/433125 and 23600/368125; the flagged L-absorption values); GF-05's in-range sim-config L = 1000 (the only UEC-class latency figure, a simulation config); GF-09's out-of-range 10 us RTT placement (5000 as 2L, 2.5x the range upper, the range NOT moved); and the envelope displacement table with its convergence law",
        },
        "headline": (
            "group G4 executes NO O-CCT fit (no anchor stages a series) — it executes the split record's two duties instead. "
            "THE FALSIFIER (CAL-A5): the torus input space carries NO geometry field, so the model's twisted/regular ratio is exactly 1 against the measured 1.63/1.31 — a 63%/31% blind spot (7.9x/3.9x CAL-A6's 8% noise floor); sweeping the DECLARED A-L0T-BW range shows the B axis cannot express the effect AT ALL in this hop-latency-dominated regime (the required twisted CCT lies BELOW the B->infinity latency floor; the whole unbounded B axis delivers at most 5.4%/6.4% of the required gain; the executed displacement rows deliver 1.26%/0.46% CCT cuts against the required 38.7%/23.7%), and the arithmetic L-absorption that COULD reach it would misattribute bisection structure to hop latency — flagged, never selected. "
            "THE ENVELOPES (CAL-A11 + GF-05 + GF-07 + GF-08): the identity predicts exactly the uncongested carrier row — the ORIGIN every envelope anchor measures its effects against (5%->25x measured collectives, 30-40% production load-balance, 20-50% NSCC gains / 3-6x RoCE, 8x/65% transport deltas); all are structurally inexpressible (no congestion semantics exist), every executed edge displacement lies INSIDE the declared A-L0X-BW range, and the executed convergence law shows a dimensionless factor enters an affine identity only as an asymptotic effective-B displacement (the 25x edge executes at 2075/283 ~ 7.33x at the 8 KiB ladder bottom, reaching 25 only in the bandwidth-bound limit). "
            "GF-08's 120 Mops/s is inexpressible from below (implied L = 25/6 ns < the range lower 10; the 2L floor exceeds the per-op time at every admissible L). "
            "GF-09 (design-target ceiling) CONSTRAINS NOTHING: zero falsification power, normalization-only, an open-ended class FLOOR (opposite direction to the CAL-A1/A2 ceilings); its 10 us RTT target (5000 ns as 2L) is an out-of-range recorded placement — the range is NOT moved"
        ),
    }
    # cross-check sanity fences (a transcription bug fails here)
    assert record["fits"]["cal_a5"]["falsifier"]["slice_128"]["blind_spot_pct"] == 63.0
    assert record["fits"]["cal_a5"]["falsifier"]["slice_256"]["blind_spot_pct"] == 31.0
    assert GF07_ENVELOPE_SPAN == Fraction(95, 4)
    assert GF08_L_IMPLIED == Fraction(25, 6) and GF08_L_IMPLIED < 10
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
