"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-05
(calibration stage GF-05).

GF-05 = SMaRTT and REPS (NSDI 2025, arXiv:2404.01630) — "the algorithm that
forms the basis of the UEC NSCC specification" and the UET 1.0 reference
load-balancing mechanism — evaluated in the uet-htsim simulator (the family
pre-pinned as this repo's third backend) plus a DPDK hardware testbed.
Stage role (gap-fill doc §GF-05): R1 (UEC-class transport, sim-config
provenance) + R3 (congestion-management effect sizes) in one row, with the
assigned duty to CLASSIFY HONESTLY what an L0 placement can and cannot
express about a congestion-control anchor.

Pure function of immutable artifacts: reads the two append-only store run
records and the three sweep tables produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_gapfill.md`` §GF-05
(numbers AS STAGED, not re-fetched; the staging doc quotes the paper HTML,
so quote strings are staged paraphrases at H confidence), or (b) computed
from the stored run/sweep artifacts by this script, or (c) exact closed-form
identity arithmetic cross-checked against executed artifacts by exact
Fraction string equality (declared inline wherever used). Nothing is tuned:
every swept B/L value and the executed rank scale carry their anchor/registry
provenance, and the record measures where the model output sits relative to
the anchor's sim config, oversubscription structure, envelope magnitudes,
and stated scale.

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
RUN_ID_XBAR_ANCHOR100 = "422f8baf8b1d6d126e1d5c427e3149eb3488c83bd5324ab4b5e1d56998da65ec"
RUN_ID_XBAR_REGISTRY = "f65cb83c1ebfc9763c55a040057dc91729a7bcf484c67fc403939596b4696f70"
SWEEP_ID_ENVELOPE = "1175a22c8c7e0ea9307ef006f96d4176ae31cc835d016286d27714aedd2630bd"
SWEEP_ID_LATENCY = "3a72252d4693d393d748a34e5f335ffd336f24bdf0b750b7c7a0b564ea4fbfdb"
SWEEP_ID_SCALE = "f24d23cdbb016a8b662c3f5854802f003daa9ae6411d8b55e7a4ccfb31be5c4d"

RESULTS = REPO_ROOT / "results"

# Anchor GF-05 staged numbers (docs/calibration/anchors_gapfill.md §GF-05;
# confidence H — numbers extracted from the paper HTML; CAVEAT: peer-reviewed
# SIMULATION + a small DPDK hardware testbed, not UEC silicon; outcome
# metrics are FCTs, not collective CCTs).
GF05_SIM_RATE_GBPS = Fraction(800)    # "4KiB MTU size, a 800 Gbps network bandwidth, and a 400ns switch traversal latency"
GF05_SWITCH_NS = Fraction(400)        # switch traversal latency (verbatim)
GF05_LINK_NS = Fraction(600)          # link latency (verbatim)
GF05_MTU_BYTES = 4096                 # 4 KiB MTU (verbatim)
GF05_TRIM_US = Fraction(84)           # trimming/loss-learn quote: "roughly 84 us = 7 base RTTs"
GF05_TRIM_RTTS = 7
GF05_NODES = 1024                     # "1,024-node non-blocking and 2:1/4:1/8:1 oversubscribed" fat trees
GF05_SUBS = (2, 4, 8)                 # oversubscription series (verbatim)
# Outcome deltas (FCT metrics, dimensionless factors):
GF05_CC_GAIN = Fraction(1, 2)         # "outperforms ... Swift, RoCE, and MPRDMA by up to 50%"
GF06_ALLTOALL_IDEAL = Fraction(6, 100)      # "only up to 6% behind the ideal time"
GF05_ALLTOALL_BETTER = Fraction(1, 5)       # "up to 20% better than other sender-based schemes"
GF05_FAIRNESS = Fraction(65, 100)     # "FCT of the slowest flow is 65% longer than the fastest flow" (under Swift)
GF05_ROCE_PERM = (3, 5)               # HW permutation: "RoCE ... are 3-5 times slower than optimal"
GF05_ROCE_ALLTOALL = (3, 6)           # HW alltoall: "RoCEv2 is 3-6x slower"
GF05_EQDS_TRIM = 155                  # EQDS "can generate up to 155x more trimmed packets"
GF05_TARGET_RTT_FACTOR = Fraction(3, 2)     # "target RTT 1.5x base RTT"
GF05_WINDOW_BDP = Fraction(3, 2)      # window "clamped to 1.5 BDP"

# Derived under the DECLARED reading (decimal units, the plan's convention
# 1 GB/s = 1 B/ns; full-duplex per-direction line rate): 800 Gbps = 100 B/ns
# per direction. The bidirectional-aggregate alternative (50 B/ns) is a
# flagged ambiguity, recorded not swept.
B_LINE = GF05_SIM_RATE_GBPS / 8                  # 100
B_LINE_ALT_READING = B_LINE / 2                  # 50 (recorded; = CAL-A1/A5/A11 rate)
L_HOP = GF05_SWITCH_NS + GF05_LINK_NS            # 1000 = the anchor's per-hop decomposition
L_PATH_ONEWAY = 6 * L_HOP                        # 6000 = 6-hop one-way path reading
BASE_RTT = GF05_TRIM_US * 1000 / GF05_TRIM_RTTS  # 12000 = 84 us / 7 exactly
L_REGISTRY = Fraction(200)                       # A-L0X-LAT / A-L0-LAT registry point
B_REGISTRY = Fraction(64)                        # A-L0X-BW / A-L0-BW registry point
TARGET_RTT = BASE_RTT * GF05_TARGET_RTT_FACTOR   # 18000
BDP_BYTES = BASE_RTT * B_LINE                    # 1,200,000 B
WINDOW_MAX_BYTES = BDP_BYTES * GF05_WINDOW_BDP   # 1,800,000 B
MTU_SERIALIZATION_NS = Fraction(GF05_MTU_BYTES) / B_LINE  # 4096/100 = 1024/25 = 40.96

# Envelope factors (exact) and their B-axis displacements.
F_FIFTY_PRIMARY = 1 + GF05_CC_GAIN                # 3/2 (t_baseline = 1.5 x t_SMaRTT)
F_FIFTY_ALT = 1 / (1 - GF05_CC_GAIN) if False else Fraction(2)  # alt reading: "50% faster" = x2
F_SIX_PCT = 1 + GF06_ALLTOALL_IDEAL               # 53/50
F_TWENTY = 1 + GF05_ALLTOALL_BETTER               # 6/5
F_FAIRNESS = 1 + GF05_FAIRNESS                    # 33/20
B_FIFTY = B_LINE / F_FIFTY_PRIMARY                # 200/3 (non-representable; recorded)
B_TWENTY = B_LINE / F_TWENTY                      # 250/3 (recorded)
B_SIX_PCT = B_LINE / F_SIX_PCT                    # 5000/53 (recorded)
B_ROCE3 = B_LINE / 3                              # 100/3 (recorded)
B_ROCE6 = B_LINE / 6                              # 50/3 (recorded)
B_FAIRNESS = B_LINE / F_FAIRNESS                  # 2000/33 (recorded)
# Executed displacement rows (representable as finite decimals):
B_SUB2 = B_LINE / 2                               # 50
B_SUB4 = B_LINE / 4                               # 25
B_ROCE5 = B_LINE / 5                              # 20
B_SUB8 = B_LINE / 8                               # 25/2 = 12.5 (the one non-integer executed B)

R_SMOKE = 8
R_ANCHOR = GF05_NODES                             # 1024

LADDER_R8 = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
             134217728, 268435456, 536870912, 2147483648, 8589934592]
LADDER_SCALE = [1024 * 2 ** k for k in range(18)]  # 1 KiB -> 128 MiB
RUN_PAYLOAD = 2097152                             # 2 MiB — the anchor's only staged size

TOPO_BY_B = {
    "crossbar8_gf05_line100_v1": B_LINE,
    "crossbar8_gf05_reg64_l1000_v1": B_REGISTRY,
    "crossbar8_gf05_sub2to1_50_v1": B_SUB2,
    "crossbar8_gf05_sub4to1_25_v1": B_SUB4,
    "crossbar8_gf05_roce5x_20_v1": B_ROCE5,
    "crossbar8_gf05_sub8to1_12_5_v1": B_SUB8,
}
TOPO_BY_L = {
    "crossbar8_gf05_line100_l12000_v1": BASE_RTT,
    "crossbar8_gf05_line100_l6000_v1": L_PATH_ONEWAY,
    "crossbar8_gf05_line100_v1": L_HOP,
    "crossbar8_gf05_line100_l600_v1": GF05_LINK_NS,
    "crossbar8_gf05_line100_l400_v1": GF05_SWITCH_NS,
    "crossbar8_gf05_line100_l200_v1": L_REGISTRY,
}
TOPO_XBAR_SCALE = "crossbar1024_gf05_line100_v1"
TOPO_XBAR_SCALE_SUB8 = "crossbar1024_gf05_sub8to1_12_5_v1"
TOPO_RING_SCALE = "ring1024_gf05_line100_v1"


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction = L_HOP) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def t_ring(m: int, b: Fraction, ranks: int, l: Fraction = L_HOP) -> Fraction:
    """t = 2(r-1)/r*M/B + 2(r-1)*L  (src/essun/backends/analytical/l0.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * (ranks - 1) * l


def c_rank(ranks: int) -> Fraction:
    """The bandwidth coefficient 2(r-1)/r of both identities."""
    return Fraction(2 * (ranks - 1), ranks)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    model = obs["model"]
    l_val = Fraction(model["pair_latency_ns_exact"])
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": model["ranks"],
            "backend_id": obs["backend_id"],
            "transport_model": model["transport_model"],
            "injection_bytes_per_ns_exact": model["injection_bytes_per_ns_exact"],
            "pair_latency_ns_exact": model["pair_latency_ns_exact"],
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "latency_term_ns_exact": str(2 * l_val),
        "latency_fraction_of_cct_exact": str(2 * l_val / cct),
        "latency_fraction_of_cct_float": float(2 * l_val / cct),
    }


def _by_cell(sweep_id: str) -> tuple[dict[tuple[str, int], Fraction], dict]:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    by = {
        (row["config_id"].split("-")[2], row["payload_bytes"]): Fraction(
            row["o_cct"]["completion_time_ns_mean_exact"]
        )
        for row in table["configs"]
    }
    return by, table


def sweep_rows(sweep_id: str, name_key: str) -> dict:
    by, table = _by_cell(sweep_id)
    sizes = sorted({m for (_t, m) in by})
    ladder = []
    for m in sizes:
        rows = []
        for (topo, mm), cct in sorted(by.items()):
            if mm != m:
                continue
            rows.append(
                {
                    "topology_id": topo,
                    "cct_ns_exact": str(cct),
                    "cct_ns_float": float(cct),
                }
            )
        ladder.append({"payload_bytes": m, "rows": rows})
    return {
        "sweep_id": sweep_id,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        name_key: ladder,
    }


def anchor_derived() -> dict:
    # Self-checks: the staged numbers must produce these exact values;
    # anything else is a transcription bug, not a finding.
    assert B_LINE == 100 and B_LINE_ALT_READING == 50
    assert L_HOP == 1000 and L_PATH_ONEWAY == 6000
    assert BASE_RTT == 12000 and TARGET_RTT == 18000
    assert BDP_BYTES == 1200000 and WINDOW_MAX_BYTES == 1800000
    assert MTU_SERIALIZATION_NS == Fraction(1024, 25)  # 40.96 ns
    assert MTU_SERIALIZATION_NS / L_HOP == Fraction(1024, 25000)  # 4.096% of per-hop
    # Base-RTT consistency: the anchor's own per-hop components reconcile the
    # derived base RTT for a 6-hop one-way path EXACTLY, and miss a standard
    # 5-switch/6-link 3-tier path by exactly one switch traversal each way.
    assert 2 * 6 * (GF05_SWITCH_NS + GF05_LINK_NS) == BASE_RTT
    assert 2 * (5 * GF05_SWITCH_NS + 6 * GF05_LINK_NS) == 11200
    assert BASE_RTT - 11200 == 2 * GF05_SWITCH_NS
    # Envelope factors and displacements.
    assert F_FIFTY_PRIMARY == Fraction(3, 2) and F_FIFTY_ALT == 2
    assert F_SIX_PCT == Fraction(53, 50) and F_TWENTY == Fraction(6, 5)
    assert F_FAIRNESS == Fraction(33, 20)
    assert B_FIFTY == Fraction(200, 3) and B_TWENTY == Fraction(250, 3)
    assert B_SIX_PCT == Fraction(5000, 53)
    assert B_ROCE3 == Fraction(100, 3) and B_ROCE6 == Fraction(50, 3)
    assert B_FAIRNESS == Fraction(2000, 33)
    assert B_SUB2 == 50 and B_SUB4 == 25 and B_ROCE5 == 20 and B_SUB8 == Fraction(25, 2)
    assert B_LINE / B_REGISTRY == Fraction(25, 16)
    return {
        "staged_numbers": {
            "sim_config": "4 fat trees incl. 1,024-node non-blocking and "
            "2:1/4:1/8:1 oversubscribed; '4KiB MTU size, a 800 Gbps network "
            "bandwidth, and a 400ns switch traversal latency'; link latency "
            "600 ns; baselines EQDS, Swift, MPRDMA, RoCEv2; packet-level "
            "simulation extending htsim (= the uet-htsim family pre-pinned "
            "as this repo's third backend)",
            "standardization": "SMaRTT is 'the algorithm that forms the "
            "basis of the UEC NSCC specification'; REPS 'cited as a "
            "reference load-balancing mechanism for Ultra Ethernet Transport "
            "(UET)' by the 1.0 spec",
            "outcome_deltas_fct_metrics": "SMaRTT 'outperforms ... like "
            "Swift, RoCE, and MPRDMA by up to 50%'; alltoall 'only up to 6% "
            "behind the ideal time and up to 20% better than other "
            "sender-based schemes'; under Swift 'the FCT of the slowest "
            "flow is 65% longer than the fastest flow' (2 MiB permutation, "
            "1,024 nodes, 8:1 oversubscription); HW permutation 'within 20% "
            "of optimal' vs 'RoCE ... 3-5 times slower than optimal'; HW "
            "alltoall 'within 1.5x of optimal, while RoCEv2 is 3-6x slower'",
            "transport_mechanism_numbers": "loss learned in 'roughly 84 us = "
            "7 base RTTs' vs ~half-to-one base RTT with trimming; EQDS 'can "
            "generate up to 155x more trimmed packets'; per-flow state '19 "
            "bytes'; '59 ... to 94' instructions per packet; window clamped "
            "to 1.5 BDP; target RTT 1.5x base RTT",
            "hardware_testbed": "DPDK: 2 Broadcom Trident 4 switches, "
            "Broadcom Thor 2x100 Gbps NICs at 50 Gbps (rate-reading "
            "ambiguous: 50 Gbps => 6.25 B/ns per direction under the "
            "declared decimal per-direction reading — recorded arithmetic "
            "only, not executed)",
            "provenance_class": "H-confidence extraction from the paper "
            "HTML; the sim-config numbers are simulator INPUTS (config "
            "provenance for uet-htsim), the deltas are peer-reviewed "
            "simulation + small-HW-testbed OUTCOMES in FCT metrics — not "
            "UEC silicon, not collective CCTs",
        },
        "derived_arithmetic": {
            "line_rate_bytes_per_ns_per_direction_declared_reading": str(B_LINE),
            "declared_reading_derivation": "800 Gbps / 8 = 100 GB/s = 100 "
            "B/ns per direction under the DECLARED reading: decimal units "
            "(the plan's convention 1 GB/s = 1 B/ns) + full-duplex "
            "per-direction line rate",
            "line_rate_alt_reading_recorded_not_swept": str(B_LINE_ALT_READING),
            "alt_reading_note": "FLAGGED AMBIGUITY: if '800 Gbps' were a "
            "bidirectional aggregate the per-direction figure is 50 B/ns — "
            "numerically identical to CAL-A1's derived NVLink5 per-port "
            "rate, CAL-A5's ICI rate, and CAL-A11's 400G optics (a "
            "four-fabric-class coincidence at one byte rate, recorded never "
            "cross-derived); every CCT relation rescales by closed form; "
            "the owner adjudicates at integration",
            "per_hop_decomposition_ns": {
                "switch_traversal_verbatim": str(GF05_SWITCH_NS),
                "link_verbatim": str(GF05_LINK_NS),
                "sum_the_anchor_point": str(L_HOP),
            },
            "base_rtt_ns_exact": str(BASE_RTT),
            "base_rtt_derivation": "84 us / 7 = 12 us exactly (the anchor's "
            "own 'roughly 84 us = 7 base RTTs')",
            "base_rtt_consistency": "12000 = 2 x 6 x (400 + 600) EXACTLY — "
            "consistent with a 6-hop one-way path (6 links + 6 switch "
            "stages at the anchor's own components); a standard 3-tier "
            "fat-tree path (5 switches + 6 links) gives 2 x (5x400 + 6x600) "
            "= 11200 ns, 800 ns = one switch traversal each way short of "
            "12000 — CONSISTENT-WITH class, the tier/hop count is NOT "
            "staged; flagged as interpretation, never a derivation",
            "smrtt_target_rtt_ns": str(TARGET_RTT),
            "bdp_bytes": str(BDP_BYTES),
            "window_clamp_max_bytes": str(WINDOW_MAX_BYTES),
            "window_note": "1.5 BDP at base RTT = 1,800,000 B max in-flight "
            "per flow — an allreduce payload larger than this cannot be "
            "fully in flight under the clamp; the L0 identities assume "
            "continuous streaming and carry no window term (inexpressible; "
            "recorded)",
            "mtu_serialization_ns_exact": str(MTU_SERIALIZATION_NS),
            "mtu_note": "4 KiB MTU at 100 B/ns = 4096/100 = 40.96 ns per "
            "packet = 4.096% of the anchor's own per-hop latency 1000 ns — "
            "packetization has no input key at L0 (inexpressible); the "
            "scale comparison bounds it as a second-order term at this "
            "config point",
        },
    }


def envelope_factor_table() -> dict:
    """The R3 mapping table: every outcome quote -> exact factor -> B-axis
    displacement, with representability verdict (executed vs recorded)."""
    return {
        "mapping_technique": "stage A11's congestion-envelope -> "
        "effective-bandwidth displacement: FCT factors are dimensionless, so "
        "t_x/t_ref = F maps to B_x = B_ref/F in the bandwidth-bound limit "
        "(asymptotic CCT ratio exactly F); the MECHANISM (congestion "
        "control, load balancing, queueing) is inexpressible — only the "
        "MAGNITUDE enters as a free-scalar displacement",
        "carrier_point": "B_ref = 100 B/ns = the anchor's own sim line rate "
        "(the near-optimal SMaRTT end: consistent with its 'within 6%/20% "
        "of optimal' positioning); baselines are displaced DOWN from it",
        "rows": [
            {"quote": "outperforms Swift/RoCE/MPRDMA by up to 50%",
             "factor_exact": str(F_FIFTY_PRIMARY), "factor_float": float(F_FIFTY_PRIMARY),
             "b_displacement_exact": str(B_FIFTY), "b_displacement_float": float(B_FIFTY),
             "status": "RECORDED NOT EXECUTED (200/3 non-representable)",
             "ambiguity": "two readings: primary t_base = 1.5 x t_SMaRTT "
             "(factor 3/2); alternative '50% faster' = t_base = 2 x t_SMaRTT "
             "(factor 2 -> displacement exactly 50, numerically identical to "
             "the executed 2:1 row — coincidence recorded, readings never "
             "conflated); 'up to' one-sided semantics"},
            {"quote": "alltoall only up to 6% behind the ideal time",
             "factor_exact": str(F_SIX_PCT), "factor_float": float(F_SIX_PCT),
             "b_displacement_exact": str(B_SIX_PCT), "b_displacement_float": float(B_SIX_PCT),
             "status": "RECORDED NOT EXECUTED (5000/53 non-representable)",
             "ambiguity": "'ideal time' is the paper's own simulator "
             "baseline (definition unstaged); factor transferred dimensionless"},
            {"quote": "alltoall up to 20% better than other sender-based schemes",
             "factor_exact": str(F_TWENTY), "factor_float": float(F_TWENTY),
             "b_displacement_exact": str(B_TWENTY), "b_displacement_float": float(B_TWENTY),
             "status": "RECORDED NOT EXECUTED (250/3 non-representable)"},
            {"quote": "HW permutation RoCE 3x slower than optimal",
             "factor_exact": "3",
             "b_displacement_exact": str(B_ROCE3), "b_displacement_float": float(B_ROCE3),
             "status": "RECORDED NOT EXECUTED (100/3 non-representable)"},
            {"quote": "HW permutation RoCE 5x slower than optimal",
             "factor_exact": "5",
             "b_displacement_exact": str(B_ROCE5), "b_displacement_float": float(B_ROCE5),
             "status": "EXECUTED (crossbar8_gf05_roce5x_20_v1)",
             "ambiguity": "dimensionless HW factor transferred onto the sim "
             "line-rate point — declared transfer, not a derivation (HW-rate "
             "variants 6.25 and 1.25 B/ns recorded arithmetic only)"},
            {"quote": "HW alltoall RoCEv2 6x slower",
             "factor_exact": "6",
             "b_displacement_exact": str(B_ROCE6), "b_displacement_float": float(B_ROCE6),
             "status": "RECORDED NOT EXECUTED (50/3 non-representable)"},
            {"quote": "2:1 oversubscription (topology series)",
             "factor_exact": "2",
             "b_displacement_exact": str(B_SUB2), "b_displacement_float": float(B_SUB2),
             "status": "EXECUTED (crossbar8_gf05_sub2to1_50_v1)",
             "ambiguity": "STRUCTURAL displacement (first-order capacity "
             "only; queueing inexpressible); 50 also = alt line reading and "
             "alt 50%-quote reading — triple coincidence recorded"},
            {"quote": "4:1 oversubscription",
             "factor_exact": "4",
             "b_displacement_exact": str(B_SUB4), "b_displacement_float": float(B_SUB4),
             "status": "EXECUTED (crossbar8_gf05_sub4to1_25_v1)"},
            {"quote": "8:1 oversubscription (the fairness quote's topology)",
             "factor_exact": "8",
             "b_displacement_exact": str(B_SUB8), "b_displacement_float": float(B_SUB8),
             "status": "EXECUTED at r=8 (crossbar8_gf05_sub8to1_12_5_v1) AND "
             "at the anchor's r=1,024 fairness configuration "
             "(crossbar1024_gf05_sub8to1_12_5_v1)"},
            {"quote": "fairness: slowest flow 65% longer than fastest (under Swift)",
             "factor_exact": str(F_FAIRNESS), "factor_float": float(F_FAIRNESS),
             "b_displacement_exact": str(B_FAIRNESS), "b_displacement_float": float(B_FAIRNESS),
             "status": "RECORDED NOT EXECUTED (2000/33 non-representable) — "
             "and the per-flow SPREAD dimension is inexpressible: identical "
             "flows by construction, L0 per-flow spread exactly 0, no "
             "per-flow observable exists"},
            {"quote": "EQDS generates up to 155x more trimmed packets",
             "factor_exact": "155",
             "b_displacement_exact": None,
             "status": "RECORDED ONLY — trimming counts have no L0 "
             "observable or input key at all"},
            {"quote": "loss learned in 84 us = 7 base RTTs vs ~0.5-1 with trimming",
             "factor_exact": "7 vs {1/2, 1}",
             "b_displacement_exact": None,
             "status": "RECORDED ONLY — a CONTROL-TIMESCALE quantity "
             "(7 vs <=1 base RTTs to learn loss): time-varying state, no "
             "reaction/window key at L0; the staging sentence itself is "
             "garbled-adjacent ('with trimming' attribution unclear) — used "
             "AS STAGED, flagged"},
        ],
        "executed_rows_provenance": {
            "100": "THE ANCHOR POINT — the paper's staged 800 Gbps sim line "
            "rate per direction (declared reading); first staged anchor "
            "value ABOVE the plan §2.1 A-L0-BW candidate anchored span "
            "[20, 64] (registry point 64 sits 36% below it)",
            "64": "A-L0X-BW / A-L0-BW registry point (placement row; "
            "asymptotic CCT ratio exactly 25/16)",
            "50": "2:1 oversubscription displacement (= alt line reading = "
            "alt 50% reading; triple coincidence)",
            "25": "4:1 oversubscription displacement (bottom edge of the "
            "plan's anchored span [20, 64])",
            "20": "HW permutation RoCE x5 envelope transferred onto the sim "
            "point (declared dimensionless transfer)",
            "25/2": "8:1 oversubscription displacement — BELOW the plan's "
            "anchored span: the oversubscribed UEC-class regime extends "
            "below [20, 64] while the line rate extends above it; recorded "
            "as a placement fact, the registry range untouched",
        },
    }


def envelope_mapping(sweep_id: str) -> dict:
    """The executed displacement signature at every ladder size (R3 leg)."""
    by, _ = _by_cell(sweep_id)
    anchor_topo = "crossbar8_gf05_line100_v1"
    rows = []
    for m in LADDER_R8:
        t_anchor = by[(anchor_topo, m)]
        assert t_anchor == t_xbar(m, B_LINE, R_SMOKE)
        entry = {"payload_bytes": m, "t_anchor100_exact": str(t_anchor)}
        for topo, b in TOPO_BY_B.items():
            if topo == anchor_topo:
                continue
            t = by[(topo, m)]
            assert t == t_xbar(m, b, R_SMOKE)  # closed-form cross-check, every row
            entry[f"ratio_{topo}_vs_anchor_exact"] = str(t / t_anchor)
            entry[f"ratio_{topo}_vs_anchor_float"] = float(t / t_anchor)
        rows.append(entry)
    asymptotes = {
        "reg64_vs_anchor": str(B_LINE / B_REGISTRY),      # 25/16
        "sub2to1_vs_anchor": str(B_LINE / B_SUB2),        # 2
        "sub4to1_vs_anchor": str(B_LINE / B_SUB4),        # 4
        "roce5x_vs_anchor": str(B_LINE / B_ROCE5),        # 5
        "sub8to1_vs_anchor": str(B_LINE / B_SUB8),        # 8
    }
    assert B_LINE / B_REGISTRY == Fraction(25, 16)
    assert B_LINE / B_SUB8 == 8 and B_LINE / B_ROCE5 == 5
    # Monotone approach to every asymptote (limit of pure 1/B arithmetic).
    smallest, largest = rows[0], rows[-1]
    for topo, asym in [
        ("crossbar8_gf05_reg64_l1000_v1", Fraction(25, 16)),
        ("crossbar8_gf05_sub2to1_50_v1", Fraction(2)),
        ("crossbar8_gf05_sub4to1_25_v1", Fraction(4)),
        ("crossbar8_gf05_roce5x_20_v1", Fraction(5)),
        ("crossbar8_gf05_sub8to1_12_5_v1", Fraction(8)),
    ]:
        r_small = Fraction(smallest[f"ratio_{topo}_vs_anchor_exact"])
        r_large = Fraction(largest[f"ratio_{topo}_vs_anchor_exact"])
        assert abs(r_large - asym) < abs(r_small - asym)
    m2 = next(r for r in rows if r["payload_bytes"] == RUN_PAYLOAD)
    return {
        "claim": "the anchor's congestion-control and oversubscription "
        "envelopes, which the L0 family declares out of scope BY "
        "CONSTRUCTION, can enter these identities ONLY as displacements of "
        "the free B axis; the executed rows show the exact signature: at "
        "the anchor's own 2 MiB flow size the ratios sit at "
        "{reg64 1.533, sub2to1 1.948, sub4to1 3.845, roce5x 4.793, sub8to1 "
        "7.638} rising monotonically toward the exact asymptotes {25/16, 2, "
        "4, 5, 8} as the payload grows — pure 1/B arithmetic with the 2L "
        "latency term constant at the anchor's own L=1000",
        "asymptotic_ratios_exact": asymptotes,
        "row_at_anchor_2mib": m2,
        "ladder_rows_cross_checked": rows,
        "consistency_property": "the x5 row reproduces the anchor's own "
        "'RoCE 3-5x slower' factor EXACTLY as its asymptotic CCT ratio (the "
        "displacement construction is consistent with the quoted factor by "
        "construction — the A11 technique's self-check, executed on GF-05's "
        "numbers)",
        "input_space_audit": "the crossbar loader reads exactly "
        "{topology_id, ranks, nic.injection_bytes_per_ns, link.pair_latency_ns} "
        "and the ring loader {topology_id, ranks, link.bytes_per_ns, "
        "link.hop_latency_ns} — no CC-algorithm / ECMP / queueing / window / "
        "MTU / fairness / trimming key exists anywhere in the input space, "
        "and BOTH backends list 'congestion' among their "
        "explicitly_unsupported capabilities (CAPABILITIES in "
        "src/essun/backends/analytical/l0_crossbar.py and l0.py); the "
        "closed forms above equal every executed row by exact Fraction "
        "string equality, so no congestion-control term can be hiding in "
        "the arithmetic",
    }


def latency_placement(sweep_id: str) -> dict:
    """The R1 latency leg: the anchor's own sim-config latency numbers on
    the free L axis, with the exact difference identity."""
    by, _ = _by_cell(sweep_id)
    anchor_topo = "crossbar8_gf05_line100_v1"
    rows = []
    for m in LADDER_R8:
        t_anchor = by[(anchor_topo, m)]
        assert t_anchor == t_xbar(m, B_LINE, R_SMOKE, L_HOP)
        entry = {"payload_bytes": m}
        for topo, l_val in sorted(TOPO_BY_L.items(), key=lambda kv: -kv[1]):
            t = by[(topo, m)]
            assert t == t_xbar(m, B_LINE, R_SMOKE, l_val)
            # identity: every row differs from the anchor row by exactly 2(L-1000)
            assert t - t_anchor == 2 * (l_val - L_HOP)
            entry[f"t_{topo}_exact"] = str(t)
            entry[f"latency_fraction_{topo}_exact"] = str(2 * l_val / t)
            entry[f"latency_fraction_{topo}_float"] = float(2 * l_val / t)
        rows.append(entry)
    t2m = next(r for r in rows if r["payload_bytes"] == RUN_PAYLOAD)
    lat_frac_anchor_2mib = Fraction(t2m[f"latency_fraction_{anchor_topo}_exact"])
    lat_frac_basertt_2mib = Fraction(
        t2m["latency_fraction_crossbar8_gf05_line100_l12000_v1_exact"]
    )
    lat_frac_anchor_8k = Fraction(rows[0][f"latency_fraction_{anchor_topo}_exact"])
    assert lat_frac_anchor_2mib == Fraction(3125, 60469)  # ~5.17% at 2 MiB
    return {
        "claim": "GF-05 stages the first UEC-class sim-config latency "
        "numbers on the plan's weakest axis (gap §4.2): switch traversal "
        "400 ns + link 600 ns (both verbatim), per-hop sum 1000 ns = 5x the "
        "registry point 200 ns (inside the A-L0X-LAT free range [10, 2000] "
        "and matching the plan's candidate range upper ~800-1000 ns), the "
        "6-hop one-way path reading 6000 ns, and the base RTT 12000 ns "
        "(= 84 us / 7 exactly, consistent with a 6-hop path at 1000 ns/hop) "
        "— the CC reaction timescale, 6x the free-range upper because a "
        "path-round-trip is NOT a per-hop parameter. Every row differs from "
        "the anchor row by exactly 2(L - 1000) ns at EVERY size (identity, "
        "verified on all 72 executed rows)",
        "ladder_rows_cross_checked": rows,
        "latency_fraction_of_cct": {
            "anchor_row_2mib_exact": str(lat_frac_anchor_2mib),
            "anchor_row_2mib_float": float(lat_frac_anchor_2mib),
            "base_rtt_row_2mib_exact": str(lat_frac_basertt_2mib),
            "base_rtt_row_2mib_float": float(lat_frac_basertt_2mib),
            "anchor_row_8kib_float": float(lat_frac_anchor_8k),
            "note": "at the anchor's own 2 MiB flow size the per-hop latency "
            "is ~5.17% of CCT but the base-RTT reading is ~39.5% — the CC "
            "timescale, if charged as static latency, would dominate "
            "small/medium payloads; in reality it is a reaction bound, not "
            "a per-pair latency (inexpressible; recorded)",
        },
        "registry_placement": {
            "L_registry_200_vs_anchor_1000": "the registry point sits 5x "
            "BELOW the anchor's own per-hop decomposition; the anchor "
            "decomposition sits INSIDE the free range [10, 2000]",
            "L_base_rtt_12000": "OUTSIDE the free range upper 2000 — a "
            "different quantity class (path RTT vs per-hop latency); the "
            "plan §2.1 A-L0-LAT NARROW(range upper) candidate (~<= 800-1000 "
            "ns) is CONSISTENT with the per-hop point 1000, not the RTT; "
            "recorded, the registry range is untouched",
        },
    }


def scale_and_schedule(sweep_id: str) -> dict:
    """The scale sweep: rank-count structure, the fairness configuration,
    and the schedule contrast at the anchor's stated r=1,024."""
    by, _ = _by_cell(sweep_id)
    c8, c1024 = c_rank(R_SMOKE), c_rank(R_ANCHOR)
    assert c8 == Fraction(7, 4) and c1024 == Fraction(1023, 512)
    assert c1024 / c8 == Fraction(1023, 896)
    assert Fraction(8, 7) - c1024 / c8 == Fraction(1, 896)
    chain = 2 * (R_ANCHOR - 1) * L_HOP
    diff_const = 2 * (R_ANCHOR - 2) * L_HOP
    assert chain == 2046000 and diff_const == 2044000
    rows = []
    for m in LADDER_SCALE:
        tx = by[(TOPO_XBAR_SCALE, m)]
        ts8 = by[(TOPO_XBAR_SCALE_SUB8, m)]
        tr = by[(TOPO_RING_SCALE, m)]
        assert tx == t_xbar(m, B_LINE, R_ANCHOR)
        assert ts8 == t_xbar(m, B_SUB8, R_ANCHOR)
        assert tr == t_ring(m, B_LINE, R_ANCHOR)
        assert tr - tx == diff_const  # identity at every size
        rows.append(
            {
                "payload_bytes": m,
                "xbar_cct_ns_exact": str(tx),
                "xbar_sub8_cct_ns_exact": str(ts8),
                "ring_cct_ns_exact": str(tr),
                "ring_vs_xbar_ratio_exact": str(tr / tx),
                "ring_vs_xbar_ratio_float": float(tr / tx),
                "sub8_vs_xbar_ratio_exact": str(ts8 / tx),
                "sub8_vs_xbar_ratio_float": float(ts8 / tx),
            }
        )
    crossover = L_HOP * B_LINE * R_ANCHOR  # 102,400,000 B
    assert crossover == 102400000
    below_m, above_m = 67108864, 134217728  # 64 MiB < M* < 128 MiB
    r_below = by[(TOPO_RING_SCALE, below_m)] / by[(TOPO_XBAR_SCALE, below_m)]
    r_above = by[(TOPO_RING_SCALE, above_m)] / by[(TOPO_XBAR_SCALE, above_m)]
    assert r_below == Fraction(755997, 299747)  # ~2.522
    assert r_above == Fraction(7387083, 4193333)  # ~1.762
    # At M* the ring's bandwidth term equals its latency chain, so
    # ring(M*) = 2 x 2(r-1)L and xbar(M*) = 2(r-1)L + 2L: ratio = 1023/512.
    ring_at_mstar = t_ring(crossover, B_LINE, R_ANCHOR)
    xbar_at_mstar = t_xbar(crossover, B_LINE, R_ANCHOR)
    assert ring_at_mstar == 2 * chain and xbar_at_mstar == chain + 2 * L_HOP
    assert ring_at_mstar / xbar_at_mstar == c1024  # declared arithmetic
    m_2mib = next(r for r in rows if r["payload_bytes"] == RUN_PAYLOAD)
    smallest = rows[0]
    return {
        "rank_coefficient": {
            "claim": "at the anchor's stated scale r = 1,024 the bandwidth "
            "coefficient 2(r-1)/r = 1023/512 (~1.998) is exactly "
            "(8/7)(r-1)/r = 1023/896 (~1.1421) above the r=8 smoke default "
            "— the structural rank-count effect is AT MOST +1/7 (~+14.29%) "
            "for ANY r, reached to within 1/896 (~0.11%) at the anchor's "
            "scale (the same structural class stage A11 executed at "
            "r=24,576)",
            "c8_exact": str(c8),
            "c1024_exact": str(c1024),
            "ratio_exact": str(c1024 / c8),
            "gap_to_8_sevenths_exact": str(Fraction(8, 7) - c1024 / c8),
        },
        "ceiling_row_honesty": "the crossbar1024 B=100 row is the "
        "NON-BLOCKING single-stage CEILING abstraction of the paper's own "
        "1,024-node non-blocking fat tree (the role CAL-A1/A2 spec ceilings "
        "play) — never a prediction of the fat tree: no tiers, no queueing, "
        "no congestion, no packetization exist at L0",
        "fairness_configuration_row": {
            "claim": "the anchor's fairness-quote configuration ('2 MiB "
            "permutation, 1,024 nodes, 8:1 oversubscription', under Swift) "
            "executed as the ceiling displaced by 8:1: asymptotic CCT ratio "
            "exactly 8 vs the non-blocking row; the quote itself (slowest "
            "flow 65% longer than fastest, factor exactly 33/20) is "
            "INEXPRESSIBLE — identical flows by construction give L0 "
            "per-flow spread exactly 0, and no per-flow observable exists",
            "row_at_2mib": m_2mib,
            "sub8_asymptotic_ratio_exact": "8",
        },
        "schedule_contrast": {
            "claim": "at the SAME scale and sim-config point the multi-hop "
            "ring schedule charges the per-hop latency 2(r-1) = 2,046 times "
            "per AllReduce (latency chain exactly 2,046,000 ns) against the "
            "crossbar ceiling's 2; ring-minus-crossbar is EXACTLY "
            "2(r-2)L = 2,044,000 ns at every one of the 18 executed sizes "
            "(identity). Across the ladder members bracketing the ring's "
            "regime boundary M* = L*B*r = 102,400,000 B (~97.66 MiB, where "
            "the ring's bandwidth term equals its latency chain) the "
            "ring/crossbar ratio is ~2.522 (64 MiB) and ~1.762 (128 MiB); "
            "at M* it is exactly the coefficient 1023/512 (~1.998); at the "
            "smallest member (1 KiB) it is ~927 — SCHEDULE STRUCTURE ALONE, "
            "an in-model choice with no congestion, moves CCT by factors "
            "far beyond every envelope the anchor measures",
            "latency_chain_ns_exact": str(chain),
            "difference_identity_ns_exact": str(diff_const),
            "crossover_bytes_exact": str(crossover),
            "crossover_float_mib": float(crossover / 2**20),
            "ratio_at_crossover_exact": str(ring_at_mstar / xbar_at_mstar),
            "bracketing_members": {
                "below_64mib_ratio_exact": str(r_below),
                "below_64mib_ratio_float": float(r_below),
                "above_128mib_ratio_exact": str(r_above),
                "above_128mib_ratio_float": float(r_above),
            },
            "smallest_member_1kib": smallest,
            "no_schedule_claim": "no schedule is claimed to be THE "
            "SMaRTT/uet-htsim behavior — the paper's FCT tables are "
            "unstaged and no FCT comparison is attempted; the ring row "
            "brackets schedule-structure magnitude at the anchor's own "
            "scale and config (the scale-side analog of stage A9's "
            "chain-multiplicity contrast and A11's r=24,576 contrast)",
        },
        "ladder_rows_cross_checked": rows,
    }


def confounder_separation() -> dict:
    """The stage's central R3 conclusion, assembled from the anchor's own
    numbers and the executed rows above."""
    return {
        "role": "the R3 congestion-effects classification the stage was "
        "assigned: order the separable confounders by magnitude, using the "
        "anchor's own quotes and this stage's executed identities",
        "four_confounders_ordered_by_magnitude": {
            "1_schedule_structure_in_model": {
                "magnitude": "ring-vs-crossbar at r=1,024: exact difference "
                "2,044,000 ns at every size; ratios ~1.76 (128 MiB) to "
                "~2.52 (64 MiB) around the regime boundary, ~927 at 1 KiB",
                "status": "fully in-model (identity choice)",
            },
            "2_oversubscription_structure_anchor_staged": {
                "magnitude": "exactly x2 / x4 / x8 (the anchor's own "
                "simulated topology series, mapped as first-order "
                "displacements)",
                "status": "structure inexpressible (no subscription key; "
                "non-blocking identity); magnitude expressible as "
                "displacement only",
            },
            "3_roce_class_envelope_anchor_measured": {
                "magnitude": "x3-x6 vs optimal (HW quotes; x5 executed on "
                "the sim point)",
                "status": "outcome of CC+LB mechanisms — inexpressible "
                "mechanism, expressible magnitude",
            },
            "4_cc_scheme_envelope_the_papers_subject": {
                "magnitude": "x1.06 (6% behind ideal) to x1.5 (up to 50% "
                "vs Swift/RoCE/MPRDMA) between schemes; x1.65 slowest-flow "
                "fairness spread under Swift; x1.2 vs sender-based schemes",
                "status": "THE ANCHOR'S SUBJECT — smallest of the four "
                "confounder classes",
            },
            "rank_count_structure_in_model": {
                "magnitude": "exactly (8/7)(r-1)/r: +14.2% at r=1,024 vs "
                "r=8 (at most +1/7 for any r)",
                "status": "fully in-model (identity coefficient)",
            },
        },
        "dominance_over_noise_floors": "the smallest CC-scheme factor 53/50 "
        "(+6%) is the only one anywhere near CAL-A4's ~5% validated band "
        "and CAL-A6's 5-8% software-version noise floor; the primary 3/2 "
        "envelope exceeds them ~2.9-3.0x; oversubscription x8 exceeds them "
        "~14-16x; schedule structure exceeds them ~35-50x at the bracketing "
        "sizes — every structural class dominates the CC effect the paper "
        "measures",
        "conclusion": "in a raw collective-time number read through an L0 "
        "lens, schedule choice, oversubscription ratio, and rank scale each "
        "swamp the 6-50% congestion-control effects that are GF-05's "
        "subject — any future scale-out/UEC-proxy comparison (per plan gap "
        "§4.1) must pin all four states before a residual is attributable "
        "to anything calibratable; conversely the anchor's envelope "
        "(53/50 ... 3/2 between schemes, 3-6x vs RoCE-class, x8 at 8:1 "
        "oversubscription, 33/20 fairness) is exactly the falsification "
        "band any future congestion-modeling backend must reproduce",
    }


def expressiveness_classification() -> dict:
    """The assigned duty, executed: what an L0 placement CAN and CANNOT
    express about a congestion-control anchor (anchor-registry arithmetic
    and loader/capability audit; executed displacements above)."""
    return {
        "CAN_express": {
            "sim_config_provenance": "the anchor's own simulator parameters "
            "land directly on the free axes: B=100 B/ns (800 Gbps, declared "
            "reading), L in {400, 600, 1000, 6000, 12000} ns (component, "
            "per-hop, path, RTT readings) — the first UEC-class sim-config "
            "provenance on the axes, and directly anchor-able config "
            "provenance for the pinned uet-htsim third-backend family",
            "envelope_magnitudes": "every outcome quote maps to an exact "
            "Fraction factor and an effective-B displacement (executed "
            "{25/16, 2, 4, 5, 8}; recorded {3/2, 6/5, 53/50, 3, 6, 33/20}) "
            "with monotone-approach signatures — magnitude placement, the "
            "A11 technique",
            "oversubscription_first_order": "the 2:1/4:1/8:1 series as "
            "exact capacity displacements (first-order only)",
            "scale_and_schedule_structure": "r=1,024 coefficient 1023/512 "
            "(+14.2% vs r=8, at most +1/7 for any r); ring-vs-crossbar "
            "exact 2,044,000 ns differences",
        },
        "CANNOT_express": {
            "congestion_control_itself": "no CC-algorithm key anywhere in "
            "the loader surface; 'congestion' in both backends' "
            "explicitly_unsupported capabilities — the anchor's SUBJECT "
            "(SMaRTT vs Swift/RoCE/MPRDMA/EQDS behavior) is not unswept, "
            "it is INEXPRESSIBLE; only outcome displacements enter",
            "load_balancing": "no path-count/ECMP/spray key — REPS "
            "(the UET 1.0 reference LB mechanism) is equally inexpressible",
            "fct_metric": "no per-flow completion observable exists; FCT "
            "(the anchor's every outcome metric) is not bridgeable to CCT "
            "at L0 — the regime bridge is declared INEXPRESSIBLE, so no "
            "time comparison is attempted anywhere in this stage (the "
            "anchor's FCT tables are additionally unstaged)",
            "fairness_spread": "identical flows by construction: L0 "
            "per-flow spread is exactly 0; the 65% quote (factor 33/20) "
            "has no in-model counterpart dimension",
            "oversubscribed_queueing": "the non-blocking identity's "
            "per-pair bandwidth is independent of other pairs — exactly "
            "the no-congestion abstraction; a subscribed fabric's "
            "load-dependent capacity and queueing have no input",
            "packetization": "no packet/FLIT/MTU key; the 4 KiB MTU's "
            "40.96 ns serialization is inexpressible (bounded: 4.096% of "
            "the anchor's own per-hop latency)",
            "cc_timescales_and_state": "target RTT (1.5x base = 18000 ns), "
            "window clamp (1.5 BDP = 1,800,000 B), loss-learn (7 base RTTs "
            "vs <=1), trimming counts (EQDS 155x), per-flow state (19 B), "
            "processing budgets (59-94 instr/packet) — all time-varying or "
            "per-packet state with no key; only the base-RTT scale enters, "
            "as the declared L=12000 upper-envelope reading",
            "fat_tree_structure": "no fat-tree topology_class in the landed "
            "set {unidirectional_ring, fully_connected_crossbar, "
            "fully_connected_exchange, torus2d_ring_x_ring}; the multi-hop "
            "path enters only through L readings; the tiered oversubscribed "
            "structure only through B displacements",
            "hardware_testbed": "the DPDK testbed (2 Trident 4, Thor NICs "
            "at 50 Gbps => 6.25 B/ns per direction under the declared "
            "reading) is below the plan's anchored span and has no "
            "expressible topology; recorded arithmetic only",
        },
        "consequence_for_calibration": "per the gap-fill doc's role "
        "assignment, GF-05 can never calibrate L0-family O-CCT (its "
        "outcomes are FCTs of a mechanism the family declares out of "
        "scope); its calibrated use is (a) sim-config provenance for the "
        "UEC-profile backend family (the pinned uet-htsim: 800 Gbps, 400 ns "
        "switch traversal, 600 ns link, 4 KiB MTU, r=1,024 fat trees, "
        "2:1/4:1/8:1 oversubscription) and (b) the R3 falsification "
        "envelope (53/50...3/2 between schemes, 3-6x vs RoCE-class, x8 at "
        "8:1, 33/20 fairness, 5%->25x family: cross-reference GF-07's "
        "measured envelope) that any future congestion-modeling backend "
        "must reproduce — an owner design decision this record stages, "
        "mirroring stage A11's scale-out-profile note",
    }


def registry_placements() -> dict:
    axis_ratio = B_LINE / B_REGISTRY  # 25/16
    cct_ratio = B_REGISTRY / B_LINE   # 16/25
    assert axis_ratio == Fraction(25, 16) and cct_ratio == Fraction(16, 25)
    return {
        "A-L0X-BW_point_64_vs_anchor_line_100": {
            "axis_ratio": str(axis_ratio),
            "asymptotic_cct_ratio": str(cct_ratio),
            "asymptotic_cct_ratio_float": float(cct_ratio),
            "statement": "the registry point sits 36% BELOW the anchor's "
            "sim line rate on the bandwidth axis (the registry default is "
            "56.25% slower in the bandwidth-bound limit at the UEC-class "
            "config) — a placement fact, never a tuning target; GF-05's "
            "100 B/ns is the FIRST staged anchor value ABOVE the plan §2.1 "
            "A-L0-BW candidate anchored span [20, 64], and its 8:1 "
            "displacement 12.5 the first BELOW it — the UEC-class axis "
            "extends past the span in BOTH directions; the registry value "
            "and range are untouched",
        },
        "A-L0X-LAT_A-L0-LAT": {
            "statement": "the anchor's per-hop decomposition 1000 ns is 5x "
            "the registry point 200 ns, inside the free range [10, 2000] "
            "and consistent with the plan's NARROW(range upper) candidate "
            "(~<= 800-1000 ns); the base RTT 12000 ns is a different "
            "quantity class (path round-trip) and sits outside the range — "
            "recorded, nothing changed",
        },
        "anchored_span_membership": {
            "note": "executed B values {12.5, 20, 25, 50, 64, 100}: 12.5 "
            "below the plan's candidate span [20, 64], {20, 25, 50, 64} "
            "inside it, 100 above it; recorded B values {50/3, 100/3, "
            "200/3, 250/3, 5000/53, 2000/33} span 16.7-94.3 across the span",
        },
        "cross_anchor_coincidences": {
            "50_bytes_per_ns": "numerically identical to CAL-A1's derived "
            "NVLink5 per-port rate, CAL-A5's ICI rate, CAL-A11's 400G "
            "optics — and here the alt bidirectional reading of 800 Gbps, "
            "the 2:1 oversubscription displacement, and the alt '50%' "
            "reading: coincidences recorded, never cross-derived",
            "100_bytes_per_ns": "2x the CAL-A1/A5/A11 50 rate — the first "
            "staged point above the plan's anchored span; consistent with "
            "GF-09's UEC design target '400+ Gbps' (same-class provenance "
            "note, recorded)",
            "12_5_bytes_per_ns": "numerically identical to GF-06's "
            "UET-htsim link rate (100 Gbit/s links, 1,024-host fat tree — "
            "the same host count as GF-05's node count): a second "
            "UET-htsim config coinciding with this stage's 8:1 displaced "
            "row; recorded, never cross-derived",
        },
    }


def recorded_ambiguities() -> dict:
    """The FAIL-clause duty: every ambiguity of this anchor, recorded."""
    return {
        "fct_not_cct_metric_bridge": {
            "ambiguity": "every GF-05 outcome number is a per-flow FCT "
            "(or packet count) from simulation or a small HW testbed; the "
            "model's observable is collective CCT; the anchor's FCT tables "
            "are additionally unstaged (only headline quotes exist)",
            "resolution_followed": "the regime bridge is declared "
            "INEXPRESSIBLE at L0 (no per-flow observable): NO time "
            "comparison is attempted anywhere in this stage — the "
            "extractable targets (sim-config axes, dimensionless envelope "
            "factors, stated scale/topology series) are executed as "
            "placement/mapping, the plan-consistent treatment for an "
            "anchor whose subject the family declares out of scope",
        },
        "line_rate_direction_convention": {
            "ambiguity": "'800 Gbps network bandwidth' does not state "
            "per-direction vs bidirectional aggregate",
            "resolution_followed": "per-direction reading (100 B/ns) "
            "executed; the 50 B/ns aggregate reading recorded — the latter "
            "lands exactly on the CAL-A1/A5/A11 rate; all relations rescale "
            "by closed form; owner adjudicates",
        },
        "fifty_percent_reading": {
            "ambiguity": "'outperforms ... by up to 50%' admits t_base = "
            "1.5 x t_SMaRTT (primary, factor 3/2, displacement 200/3) and "
            "the '50% faster' reading t_base = 2 x t_SMaRTT (factor 2, "
            "displacement exactly 50); 'up to' is one-sided in both",
            "consequence": "both readings recorded with exact fractions; "
            "the alternative's displacement coincides numerically with the "
            "executed 2:1 row — never conflated (three provenances on one "
            "point are declared); neither reading averaged nor tuned",
        },
        "hw_factor_transfer": {
            "ambiguity": "the x3-x6 factors are measured on the DPDK "
            "testbed (50 Gbps class), executed here on the 800 Gbps sim "
            "point",
            "consequence": "the transfer is a DECLARED dimensionless "
            "reading (factors carry no units); HW-rate variants (6.25, "
            "6.25/3, 1.25 B/ns) recorded as arithmetic only",
        },
        "base_rtt_hop_count": {
            "ambiguity": "the base RTT 12000 ns reconciles exactly with a "
            "6-switch+6-link one-way path at the staged components; a "
            "5-switch 3-tier path misses by one switch traversal per "
            "direction; the tier/hop count is not staged",
            "consequence": "CONSISTENT-WITH class note, flagged as "
            "interpretation; the L readings {400, 600, 1000} are verbatim "
            "staged numbers and carry no such ambiguity",
        },
        "oversubscription_mapping": {
            "ambiguity": "the 2:1/4:1/8:1 series is a TIER-TO-TIER capacity "
            "ratio of a subscribed fabric, mapped here as a per-rank "
            "effective-B displacement",
            "consequence": "declared FIRST-ORDER reading (cross-bisection "
            "bandwidth only); the queueing dynamics of a subscribed fabric "
            "are inexpressible — see expressiveness_classification",
        },
        "trimming_quote_wording": {
            "ambiguity": "the staged sentence 'trimming learns loss in "
            "'roughly 84 us = 7 base RTTs' vs ~half-to-one base RTT with "
            "trimming' does not name which mechanism each timescale "
            "belongs to (as-staged wording)",
            "consequence": "only the arithmetic content is used: base RTT "
            "= 84/7 us exactly, and a 7-vs-<=1-RTT loss-learn contrast "
            "(recorded); no attribution claim is made; numbers AS STAGED, "
            "not re-fetched (the GF-03 discipline)",
        },
        "fairness_attribution": {
            "ambiguity": "the 65% fairness quote is measured UNDER SWIFT "
            "(a baseline), not under SMaRTT",
            "consequence": "the factor 33/20 is recorded as a "
            "baseline-behavior datapoint (what L0 cannot express either "
            "way — per-flow spread exactly 0)",
        },
        "sim_not_silicon": {
            "ambiguity": "GF-05 is peer-reviewed SIMULATION + a small HW "
            "testbed, not UEC silicon; the sim-config numbers are simulator "
            "inputs, the deltas simulator outputs",
            "consequence": "everything is tagged sim-config-provenance / "
            "sim-outcome class; no E3/E4 language; the R1 hardware bookend "
            "is GF-08 (Falcon), not this anchor",
        },
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-05 (gap-fill anchor GF-05)",
        "anchor": {
            "anchor_id": "GF-05",
            "title": "SMaRTT + REPS (NSDI 2025): the congestion control UEC "
            "standardized, evaluated in uet-htsim + hardware (R1+R3)",
            "source_row": "gap-fill anchor — NOT yet a sources.csv row (the "
            "owner integrates accepted rows; this stage made no handoff "
            "write)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-05",
            "urls": [
                "https://arxiv.org/html/2404.01630",
                "https://github.com/ultraethernet/uet-htsim",
            ],
            "confidence": "H (numbers extracted from the paper HTML; used AS "
            "STAGED, not re-fetched). Caveat classes carried: peer-reviewed "
            "simulation + small DPDK testbed, not UEC silicon; FCT (not "
            "collective-CCT) outcome metrics — the regime bridge is declared "
            "inexpressible at L0 and no time comparison is attempted",
            "staged_numbers": "sim config: 1,024-node non-blocking + "
            "2:1/4:1/8:1 oversubscribed fat trees, 4 KiB MTU, 800 Gbps, "
            "400 ns switch traversal, 600 ns link latency, baselines "
            "EQDS/Swift/MPRDMA/RoCEv2; outcomes: up to 50% vs Swift/RoCE/"
            "MPRDMA, 6% behind ideal / 20% better (alltoall), 65% fairness "
            "spread (2 MiB permutation, 1,024 nodes, 8:1), RoCE 3-5x / "
            "RoCEv2 3-6x from optimal (HW), 84 us = 7 base RTTs loss-learn, "
            "EQDS 155x trimmed packets, 19 B per-flow state, 59-94 "
            "instr/packet, window 1.5 BDP, target RTT 1.5x base",
        },
        "target": {
            "role": "r1_sim_config_provenance_plus_r3_congestion_effects",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "GF-05's outcomes are FCTs of "
            "a CONGESTION-CONTROL mechanism — the axis the L0 family "
            "declares out of scope (capability lists) and for which no "
            "input key exists; its FCT tables are unstaged and the "
            "FCT->CCT bridge is inexpressible at L0 (no per-flow "
            "observable). The extractable targets — the sim-config axes "
            "(100 B/ns line rate; 400/600/1000 ns latency components), the "
            "dimensionless envelope factors, the stated scale r=1,024 and "
            "oversubscription series — ARE executed here as placement and "
            "mapping, which is exactly the R1/R3 role the gap-fill doc "
            "assigns",
            "regime": {
                "topology_class": "packet-level fat trees (1,024-node "
                "non-blocking + 2:1/4:1/8:1 oversubscribed) — no landed "
                "topology_class; executed on the NON-BLOCKING single-stage "
                "abstraction (fully_connected_crossbar) as ceiling rows "
                "plus one multi-hop ring row as the schedule contrast",
                "ranks": {
                    "executed": [R_SMOKE, R_ANCHOR],
                    "provenance": "r=8 free smoke default (B/L sweeps); "
                    "r=1,024 the anchor's STATED node count (scale sweep: "
                    "non-blocking ceiling + the fairness-quote 8:1 "
                    "configuration + the ring contrast)",
                },
                "message_bytes_ladders": {
                    "bw_and_latency_sweeps": LADDER_R8,
                    "scale_sweep": LADDER_SCALE,
                },
                "message_regime_note": "the anchor's only staged size is "
                "the 2 MiB permutation flow (fairness-quote context) — an "
                "FCT-class size executed as a free probe (in both r=8 "
                "ladders at k-member 2097152 and the r=1,024 ladder at "
                "k=11), never compared to any anchor time; the store runs "
                "execute exactly this size",
            },
        },
        "anchor_derived": derived,
        "envelope_factor_table": envelope_factor_table(),
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (B-axis envelope rows and L-axis "
                "rows at r=8; non-blocking ceiling, fairness-configuration "
                "and baseline rows at r=1,024)",
                "analytical_l0 (ring; one row at r=1,024 — the "
                "schedule-structure contrast at the anchor's scale and "
                "sim-config point)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; envelope sweep B in "
                "{12.5, 20, 25, 50, 64, 100} at L=1000; latency sweep L in "
                "{200, 400, 600, 1000, 6000, 12000} at B=100; scale sweep "
                "B in {100, 12.5} at L=1000, r=1,024",
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L ; B=100, L=1000, "
                "r=1,024",
            },
            "free_parameters": {
                "B_injection_swept_ns": "see envelope_factor_table."
                "executed_rows_provenance — {100 anchor, 64 registry, 50 "
                "(2:1 = alt readings), 25 (4:1), 20 (RoCE x5), 12.5 (8:1 "
                "= 25/2 exact)}",
                "L_pair_swept_ns": "{200 registry, 400 switch component, "
                "600 link component, 1000 per-hop sum (anchor point), 6000 "
                "6-hop one-way path, 12000 base RTT (= 84 us/7)}",
                "ranks": {"8": "free smoke default", "1024": "the anchor's "
                          "stated node count"},
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar); A-L0-BW/A-L0-LAT/A-L0-FD/A-L0-DIV (ring) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_ANCHOR100,
                    "anchor sim-config point (B=100 B/ns = GF-05's 800 Gbps per direction, declared reading; L=1000 ns = the anchor's 600+400 per-hop decomposition; payload 2 MiB = the anchor's only staged size)",
                ),
                run_summary(
                    RUN_ID_XBAR_REGISTRY,
                    "registry twin (B=64 B/ns, L=200 ns — both free registry points; the SAME payload isolates both axes)",
                ),
            ],
            "run_pair_placement": {
                "cct_ratio_registry_vs_anchor_exact": "90225/60469",
                "cct_ratio_registry_vs_anchor_float": 1.4920868544212738,
                "cct_delta_registry_minus_anchor_ns_exact": "476096/25",
                "cct_delta_registry_minus_anchor_ns_float": 19043.84,
                "statement": "at the anchor's own 2 MiB size the registry "
                "twin sits at 57,744 ns vs the anchor row's 967504/25 = "
                "38,700.16 ns — ratio exactly 90225/60469 (~1.492): the "
                "registry defaults predict ~49% slower than the anchor's "
                "own sim config, decomposing into the pure-B asymptote "
                "25/16 = 1.5625 and the latency terms 400 vs 2000 ns — "
                "placement arithmetic, never a tuning target",
            },
            "reconciled_sweep_envelope": sweep_rows(SWEEP_ID_ENVELOPE, "ladder"),
            "envelope_mapping": envelope_mapping(SWEEP_ID_ENVELOPE),
            "reconciled_sweep_latency": sweep_rows(SWEEP_ID_LATENCY, "ladder"),
            "latency_placement": latency_placement(SWEEP_ID_LATENCY),
            "reconciled_sweep_scale": sweep_rows(SWEEP_ID_SCALE, "ladder"),
            "scale_and_schedule": scale_and_schedule(SWEEP_ID_SCALE),
            "confounder_separation": confounder_separation(),
            "expressiveness_classification": expressiveness_classification(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — GF-05 "
            "stages no CCT-class series at all: its outcomes are per-flow "
            "FCTs of a congestion-control mechanism (tables unstaged; only "
            "headline quotes), the L0 family declares the mechanism out of "
            "scope, and the FCT->CCT bridge is inexpressible (no per-flow "
            "observable). Per the stage prompt's FAIL clause the "
            "inextractable time target is RECORDED and SKIPPED honestly; "
            "the anchor's assigned role (R1 sim-config provenance + R3 "
            "envelope) IS extractable and is executed above",
            "placement_summary": "the model's axes: anchor sim line rate "
            "100 B/ns (declared reading; 50 alternative recorded) — the "
            "first staged value above the plan's [20, 64] anchored span, "
            "registry point 64 sits 36% below (asymptotic CCT ratio 25/16); "
            "latency components 400/600 ns verbatim, per-hop 1000 ns (5x "
            "the registry point, inside the free range), base RTT 12000 ns "
            "(= 84 us/7, outside the range — a path-RTT, not a per-hop "
            "quantity); the anchor's envelopes map to exact-fraction "
            "displacements {25/16, 2, 4, 5, 8} executed and {3/2, 6/5, "
            "53/50, 3, 6, 33/20} recorded; at the anchor's stated r=1,024 "
            "the structural rank-count effect is exactly (8/7)(r-1)/r = "
            "1023/896 (+14.2%) and the schedule contrast moves CCT by exact "
            "2,044,000 ns differences (ratios 1.76-2.52 at the "
            "regime-boundary-bracketing sizes around M* = 102,400,000 B) — "
            "schedule, oversubscription (x8), and rank scale each dominate "
            "the 6-50% CC effects that are the anchor's subject",
            "span_placement": "executed B values {12.5, 20, 25, 50, 64, "
            "100} extend past the plan's anchored span on BOTH sides; "
            "executed L values span 200-12000 ns across two quantity "
            "classes (per-hop vs path-RTT); recorded, registry untouched",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the "
            "R1 sim-config-provenance + R3 envelope role; no E3/E4 "
            "language — GF-05 is an external published simulation study, "
            "not our testbed, and not UEC silicon",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_ANCHOR100, RUN_ID_XBAR_REGISTRY],
            "sweep_ids": [SWEEP_ID_ENVELOPE, SWEEP_ID_LATENCY, SWEEP_ID_SCALE],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_ENVELOPE}",
                f"results/sweeps/{SWEEP_ID_LATENCY}",
                f"results/sweeps/{SWEEP_ID_SCALE}",
            ],
            "run_backed_numbers": "every model output in "
            "comparison.anchor_point_runs, comparison.reconciled_sweep_*; "
            "comparison.envelope_mapping, comparison.latency_placement and "
            "comparison.scale_and_schedule cross-check closed forms against "
            "all 198 executed sweep rows by exact Fraction string equality "
            "(declared inline); comparison.run_pair_placement, "
            "confounder_separation, expressiveness_classification, "
            "registry_placements and the M*-point values are "
            "identity/anchor-registry arithmetic declared inline",
            "inputs": [
                "experiments/calibration/gf05/sweep_gf05_envelope_v2.yaml",
                "experiments/calibration/gf05/sweep_gf05_latency_v2.yaml",
                "experiments/calibration/gf05/sweep_gf05_scale1024_v1.yaml",
                "experiments/calibration/gf05/run_gf05_anchor_sim_v1.yaml",
                "experiments/calibration/gf05/run_gf05_registry_v1.yaml",
                "experiments/calibration/gf05/workloads/ (2 files)",
                "experiments/calibration/gf05/topologies/ (15 files)",
                "experiments/calibration/gf05/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf05/run_gf05_anchor_sim_v1.yaml ; "
            "make run EXP=experiments/calibration/gf05/run_gf05_registry_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf05/sweep_gf05_envelope_v2.yaml ; "
            "make sweep EXP=experiments/calibration/gf05/sweep_gf05_latency_v2.yaml ; "
            "make sweep EXP=experiments/calibration/gf05/sweep_gf05_scale1024_v1.yaml ; "
            "python experiments/calibration/gf05/build_calibration_record.py",
        },
    }

    # Exact-value self-checks on the executed run pair (transcription guards).
    obs100 = load_json(RESULTS / RUN_ID_XBAR_ANCHOR100 / "observations.json")
    obsreg = load_json(RESULTS / RUN_ID_XBAR_REGISTRY / "observations.json")
    t100 = Fraction(obs100["per_op"][0]["completion_time_ns_exact"])
    treg = Fraction(obsreg["per_op"][0]["completion_time_ns_exact"])
    assert t100 == t_xbar(RUN_PAYLOAD, B_LINE, R_SMOKE, L_HOP)
    assert treg == t_xbar(RUN_PAYLOAD, B_REGISTRY, R_SMOKE, L_REGISTRY)
    assert t100 == Fraction(967504, 25) and treg == 57744
    assert treg / t100 == Fraction(90225, 60469)
    assert treg - t100 == Fraction(476096, 25)

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
