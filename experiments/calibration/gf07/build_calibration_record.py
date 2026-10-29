"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-07
(calibration stage GF-07).

GF-07 = "Characterizing the Impact of Congestion in Modern HPC
Interconnects" (arXiv:2604.11432) — MEASURED collective slowdowns across
five HPC fabrics (Leonardo HDR IB Dragonfly+ 400 Gb/s/node, CRESCO8 NDR
IB 1.67:1-blocking fat tree, LUMI Cray Slingshot dragonfly 4x200 Gb/s,
HAICGU EDR IB+RoCE, Nanjing RoCE NSLB). Stage role (gap-fill doc
§GF-07): R3 measured congestion-effect magnitudes — the falsification
envelope (5% -> 25x) any congestion-effect model must fall inside; direct
evidence for plan gap 7 (no scale-up congestion anchor exists; these are
scale-out HPC fabrics, staged under the same labeled-proxy rule as
CAL-A11).

Pure function of immutable artifacts: reads the two append-only store
run records and the three sweep tables produced by this stage, recomputes
every derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_gapfill.md`` §GF-07
(numbers AS STAGED, not re-fetched), or (b) computed from the stored
run/sweep artifacts by this script, or (c) exact closed-form identity
arithmetic cross-checked against executed artifacts by exact Fraction
string equality (declared inline wherever used). Nothing is tuned: every
swept B value and the executed rank scale carry their anchor/registry
provenance, and the record measures where the model output sits relative
to the anchor's fabric rates, measured envelope, absolute bandwidth pair,
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
RUN_ID_XBAR_CARRIER100 = "4b466c5df7920f21618a8f08a6ef9ffb0d57ca8ce95f159ccd58457873281d62"
RUN_ID_XBAR_REGISTRY = "49a1180a40e31b8a0a98e36ec369976495edaf5fcb88230b61423d7e7edf862c"
SWEEP_ID_ENVELOPE = "266f3bbe380112592b9f21bfed43b3575fd1a358436869d2206080218e948253"
SWEEP_ID_CARRIER = "633e10e35966ed44106d02f4d06a6328692dd1dc7df109bab34077061700d622"
SWEEP_ID_SCALE64 = "07d10537d1c7b914d66fedb3f9124de7773aa4a46245f7d563a862901dcfb9c9"

RESULTS = REPO_ROOT / "results"

# Anchor GF-07 staged numbers (docs/calibration/anchors_gapfill.md §GF-07;
# confidence H — extracted from the paper HTML; MEASURED on production/
# testbed allocations; SCALE-OUT HPC fabrics, not GPU scale-up; outcome
# metrics are COLLECTIVE BANDWIDTH RATIOS, not O-CCT series).
GF07_LUMI_GBPS = Fraction(4 * 200)    # "LUMI (Cray Slingshot Dragonfly, 4x200 Gb/s)" per-node aggregate
GF07_LEONARDO_GBPS = Fraction(400)  # "Leonardo (HDR IB Dragonfly+, 400 Gb/s/node)"
GF07_NJ_PEAK_GBPS = Fraction(180)   # Nanjing victim AllToAll "180 Gb/s" peak
GF07_NJ_OFF_GBPS = Fraction(120)    # "drops to 120 Gb/s" with NSLB disabled
GF07_BLOCKING = Fraction("1.67")    # CRESCO8 "1.67:1 blocking fat tree"
GF07_VECTOR_MIN_B = 8               # "vectors 8 B - 16 MiB"
GF07_VECTOR_MAX_B = 16 * 1024 * 1024
GF07_ITERATIONS = 1000              # victim collectives methodology
GF07_WARMUP = 100
GF07_PARTITION_PCT = 2              # congestion effects "even at ... ~2% of a partition"

# Measured envelope factors (exact Fractions from the staged ratios).
F_FLOOR = Fraction(20, 19)          # LUMI "always within 5%"  (bw >= 19/20)
F_ALLREDUCE = Fraction(4, 3)        # "25% bandwidth loss"      (bw = 3/4)
F_BURST_A2A = Fraction(10, 7)       # "drops to 70%"            (bw = 7/10)
F_NSJB_PAIR = Fraction(3, 2)        # Nanjing pair 180/120      (bw = 2/3)
F_STEADY_INCAST = Fraction(5, 3)    # "dropping to 60%"         (bw = 3/5)
F_LEONARDO_COLLAPSE = Fraction(5)   # "collapse to 0.2"         (bw = 1/5, exact)
F_BURSTY_INCAST = Fraction(25, 2)   # "0.08" read exactly       (bw = 2/25)
F_BURSTY_INCAST_ALT = Fraction(12)  # the paper's own "12x slower" gloss
F_WORST = Fraction(25)              # CRESCO8 AllToAll victims "up to 25x"

# Derived under the DECLARED readings (decimal units, the plan's convention
# 1 GB/s = 1 B/ns; per-node aggregate mapped onto the per-rank single-port
# injection B — A-L0X-PORT first-order; no direction split staged).
B_CARRIER = GF07_LUMI_GBPS / 8                  # 100 B/ns (LUMI; the managed floor fabric)
B_LEONARDO = GF07_LEONARDO_GBPS / 8             # 50 B/ns
B_NJ_PEAK = GF07_NJ_PEAK_GBPS / 8               # 22.5 B/ns (measured absolute)
B_NJ_OFF = GF07_NJ_OFF_GBPS / 8                 # 15 B/ns (measured absolute)
B_REGISTRY = Fraction(64)                       # A-L0X-BW / A-L0-BW registry point
L_REGISTRY = Fraction(200)                      # A-L0X-LAT / A-L0-LAT registry point (GF-07 stages NO latency number)

# Executed displacement rows at the carrier (representable finite decimals).
B_FLOOR = B_CARRIER / F_FLOOR                   # 95
B_ALLREDUCE = B_CARRIER / F_ALLREDUCE           # 75
B_BURST_A2A = B_CARRIER / F_BURST_A2A           # 70
B_STEADY_INCAST = B_CARRIER / F_STEADY_INCAST   # 60
B_COLLAPSE = B_CARRIER / F_LEONARDO_COLLAPSE    # 20
B_BURSTY = B_CARRIER / F_BURSTY_INCAST          # 8
B_WORST = B_CARRIER / F_WORST                   # 4
B_COLLAPSE_ON_LEONARDO = B_LEONARDO / F_LEONARDO_COLLAPSE  # 10 (carrier sweep)

# Recorded NOT executed (non-representable as finite decimals).
B_BURSTY_ALT = B_CARRIER / F_BURSTY_INCAST_ALT  # 100/12 = 25/3 (the "12x" gloss)
B_BLOCKED = B_CARRIER / GF07_BLOCKING           # 100/1.67 = 10000/167 (first-order blocking displacement)

# Envelope span, managed floor to worst (exact).
ENVELOPE_SPAN = F_WORST / F_FLOOR               # 25 / (20/19) = 95/4 = 23.75

R_SMOKE = 8
R_ANCHOR = 64                                   # the anchor's largest staged exact node count

RUN_PAYLOAD = GF07_VECTOR_MAX_B                 # 16 MiB — the anchor's maximum staged vector

LADDER_R8 = [8 * 2 ** k for k in range(22)]     # the anchor's staged vector range 8 B -> 16 MiB
LADDER_R64 = [64 * 2 ** k for k in range(19)]   # 64 B -> 16 MiB

# topology_id -> (B or "ring", role label) for the cross-checks below.
ENV_ROWS = [
    ("crossbar8_gf07_rate100_l200_v1", B_CARRIER, "carrier: LUMI staged per-node aggregate (uncongested reference; managed-floor fabric)"),
    ("crossbar8_gf07_floor95_l200_v1", B_FLOOR, "20/19 floor: LUMI 'always within 5%' (per-flow HW CM + global-aware adaptive routing)"),
    ("crossbar8_gf07_ar75_l200_v1", B_ALLREDUCE, "4/3: 'Open MPI AllReduce ... up to a 25% bandwidth loss' (the one AllReduce-class quote)"),
    ("crossbar8_gf07_a2a70_l200_v1", B_BURST_A2A, "10/7: bursty alltoall 'drops to 70% of its uncongested baseline'"),
    ("crossbar8_gf07_reg64_l200_v1", B_REGISTRY, "A-L0X-BW registry point (placement; no GF-07 provenance)"),
    ("crossbar8_gf07_inc60_l200_v1", B_STEADY_INCAST, "5/3: steady incast 'performance dropping to 60%'"),
    ("crossbar8_gf07_njpeak22_5_l200_v1", B_NJ_PEAK, "absolute: Nanjing victim AllToAll '180 Gb/s' peak (AllToAll-class proxy)"),
    ("crossbar8_gf07_leo20_l200_v1", B_COLLAPSE, "5: Leonardo incast 'collapse to 0.2' at 32-64 nodes (exact staged ratio)"),
    ("crossbar8_gf07_njoff15_l200_v1", B_NJ_OFF, "absolute: Nanjing NSLB-off '120 Gb/s' (exact pair factor 180/120 = 3/2)"),
    ("crossbar8_gf07_burst8_l200_v1", B_BURSTY, "25/2: bursty incast 64 nodes, staged ratio '0.08' read exactly"),
    ("crossbar8_gf07_worst4_l200_v1", B_WORST, "25: CRESCO8 steady-incast AllToAll victims 'slowdowns up to 25x' (ceiling)"),
]

CARRIER_ROWS = [
    ("crossbar8_gf07_rate100_l200_v1", B_CARRIER, "LUMI-rate carrier (uncongested)"),
    ("crossbar8_gf07_leo20_l200_v1", B_COLLAPSE, "factor 5 at the LUMI rate (100/5)"),
    ("crossbar8_gf07_rate50_l200_v1", B_LEONARDO, "Leonardo-rate carrier (uncongested)"),
    ("crossbar8_gf07_leo10_l200_v1", B_COLLAPSE_ON_LEONARDO, "the SAME factor 5 at Leonardo's OWN rate (50/5)"),
]


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction = L_REGISTRY) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def t_ring(m: int, b: Fraction, ranks: int, l: Fraction = L_REGISTRY) -> Fraction:
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
        "cct_ns_float": float(per_op["completion_time_ns"]),
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
    # Self-checks: the staged numbers must produce these exact values.
    assert Fraction("0.08") == Fraction(2, 25) and 1 / Fraction("0.08") == F_BURSTY_INCAST
    assert GF07_NJ_PEAK_GBPS / GF07_NJ_OFF_GBPS == F_NSJB_PAIR == Fraction(3, 2)
    assert ENVELOPE_SPAN == Fraction(95, 4)
    assert B_BURSTY_ALT == Fraction(100) / 12 == Fraction(25, 3)
    assert B_BLOCKED == Fraction(10000, 167)
    assert GF07_VECTOR_MAX_B == 16777216 and LADDER_R8[-1] == GF07_VECTOR_MAX_B
    assert LADDER_R8[0] == GF07_VECTOR_MIN_B and LADDER_R64[-1] == GF07_VECTOR_MAX_B
    assert Fraction("1.67") == Fraction(167, 100)
    return {
        "staged_numbers": {
            "fabrics": "Leonardo (HDR IB Dragonfly+, 400 Gb/s/node), CRESCO8 (NDR IB, 1.67:1 blocking fat tree), LUMI (Cray Slingshot Dragonfly, 4x200 Gb/s), HAICGU (EDR IB + RoCE CE8850 — staged with NO numbers), Nanjing (RoCE NSLB CE9855)",
            "methodology": "victim collectives 1,000 iterations, 100 warmup discarded; vectors 8 B - 16 MiB (a per-size repetition/warmup protocol — no L0 counterpart: the identity is deterministic, no repetition statistics exist)",
            "outcome_ratios": "CRESCO8 steady incast AllToAll victims 'slowdowns up to 25x'; steady incast 'performance dropping to 60%'; bursty incast 64 nodes 'a ratio of approximately 0.08 (i.e., 12x slower)'; bursty alltoall 'drops to 70%'; Leonardo incast ratios 'collapse to 0.2 (more than a 5x slowdown)' at 32-64 nodes; LUMI (per-flow HW CM + global-aware adaptive routing) 'always within 5%'; Nanjing victim AllToAll '180 Gb/s' peak, 'drops to 120 Gb/s' with NSLB disabled (~33% loss); 'Open MPI AllReduce showed up to a 25% bandwidth loss compared to AllToAll'; congestion effects 'even at ... ~2% of a partition'; RoCE/DCQCN 'recurring sawtooth pattern ... larger than 16 MiB'",
            "provenance_class": "H-confidence extraction from the paper HTML; MEASURED production/testbed numbers on HPC SCALE-OUT fabrics (labeled proxy per the CAL-A11 rule — NOT GPU scale-up, NOT UEC silicon); outcomes are collective BANDWIDTH RATIOS, not O-CCT series",
        },
        "derived_arithmetic": {
            "carrier_rate_bytes_per_ns_declared_reading": str(B_CARRIER),
            "carrier_derivation": "LUMI's staged per-node aggregate 4x200 = 800 Gb/s / 8 = 100 B/ns (decimal convention 1 GB/s = 1 B/ns; per-node aggregate mapped onto the per-rank single-port injection B — A-L0X-PORT first-order, the 4 NICs collapsed to one port; no direction split staged, flagged)",
            "carrier_role": "the anchor's ratios are per-fabric against each fabric's OWN uncongested baseline — NO shared reference fabric is staged; the carrier is a DECLARED choice (LUMI, the managed floor fabric); Leonardo's 50 B/ns is executed as the alternative carrier by the carrier sweep",
            "leonardo_rate_bytes_per_ns": str(B_LEONARDO),
            "nj_peak_bytes_per_ns_measured_absolute": str(B_NJ_PEAK),
            "nj_off_bytes_per_ns_measured_absolute": str(B_NJ_OFF),
            "nj_pair_factor_exact": str(F_NSJB_PAIR),
            "nj_pair_note": "180/120 = 3/2 exactly — a SAME-fabric on/off pair, baseline-free (the only measured absolute pair in the staged set); the anchor's '~33% loss' is the bandwidth-loss 1/3, consistent: bw ratio 2/3, CCT factor 3/2",
            "factor_definitions": "every staged ratio r maps to a CCT factor 1/r EXACTLY for a fixed-size collective (t_congested/t_uncongested = bw_uncongested/bw_congested — the ratio->factor bridge is dimensionally exact, STRONGER than GF-05's FCT bridge which was declared inexpressible; what is missing here is any absolute (size -> time) series, so no time comparison exists to make)",
            "envelope_factors_exact": {
                "floor_lumi_within_5pct": str(F_FLOOR),
                "allreduce_25pct_loss": str(F_ALLREDUCE),
                "bursty_alltoall_70pct": str(F_BURST_A2A),
                "nanjing_nslb_pair": str(F_NSJB_PAIR),
                "steady_incast_60pct": str(F_STEADY_INCAST),
                "leonardo_collapse_0p2": str(F_LEONARDO_COLLAPSE),
                "bursty_incast_0p08_exact_reading": str(F_BURSTY_INCAST),
                "bursty_incast_12x_gloss_reading": str(F_BURSTY_INCAST_ALT),
                "cresco8_alltoall_25x_ceiling": str(F_WORST),
            },
            "envelope_span_managed_floor_to_worst_exact": str(ENVELOPE_SPAN),
            "envelope_span_note": "25 / (20/19) = 95/4 = 23.75 exactly — the gap-fill doc's 'falsification envelope (5% -> 25x)' expressed as a factor span",
            "vector_range_note": "the anchor's staged vector range 8 B - 16 MiB IS the r=8 sweep ladder 8*2^k (22 sizes, both endpoints members; 16 MiB is also the DCQCN sawtooth threshold quote); every in-range member of the standard 12-size ladder of stages A1/A2/A7/A9/A11/GF-05 (8 KiB ... 8 MiB) is contained",
            "blocking_displacement_recorded_not_executed": str(B_BLOCKED),
            "blocking_note": "CRESCO8's staged '1.67:1 blocking' = 167/100 exact; first-order effective-B displacement 100/1.67 = 10000/167 (non-representable as a finite decimal — RECORDED NOT EXECUTED; fat-tree tier structure itself inexpressible, no topology_class). Note 10000/167 ~ 59.88 lands between the registry 64 and the steady-incast row 60 — inside the envelope band",
            "interference_threshold": "congestion effects 'even at ... ~2% of a partition' = an interfering-traffic fraction 1/50 — a THRESHOLD on exogenous load, no L0 input key; recorded, not a bandwidth factor",
            "dcqcn_threshold": "RoCE/DCQCN 'recurring sawtooth pattern ... larger than 16 MiB' — a time-varying dynamics threshold AT the anchor's range edge (the staged range tops out at exactly 16 MiB); no input key; recorded",
            "no_latency_number": "GF-07 stages NO latency number — L stays at the A-L0X-LAT registry point 200 throughout the stage (stage A11 precedent)",
        },
    }


def envelope_factor_table() -> dict:
    # Self-checks: every executed displacement times its factor equals the
    # carrier exactly; the absolute pair ratio is the NSLB factor.
    for _tid, b, _role in ENV_ROWS:
        pass
    assert B_FLOOR * F_FLOOR == B_CARRIER
    assert B_ALLREDUCE * F_ALLREDUCE == B_CARRIER
    assert B_BURST_A2A * F_BURST_A2A == B_CARRIER
    assert B_STEADY_INCAST * F_STEADY_INCAST == B_CARRIER
    assert B_COLLAPSE * F_LEONARDO_COLLAPSE == B_CARRIER
    assert B_BURSTY * F_BURSTY_INCAST == B_CARRIER
    assert B_WORST * F_WORST == B_CARRIER
    assert B_NJ_PEAK / B_NJ_OFF == F_NSJB_PAIR
    assert B_COLLAPSE_ON_LEONARDO * F_LEONARDO_COLLAPSE == B_LEONARDO
    rows = []
    for factor, quote, fabric, victim, b, tid, kind in [
        (F_FLOOR, "always within 5% of the uncongested case", "LUMI", "collectives under exogenous load (managed: per-flow HW CM + global-aware adaptive routing)", B_FLOOR, "crossbar8_gf07_floor95_l200_v1", "displacement"),
        (F_ALLREDUCE, "Open MPI AllReduce ... up to a 25% bandwidth loss", "(unattributed per staging)", "AllReduce (the ONE AllReduce-class quote)", B_ALLREDUCE, "crossbar8_gf07_ar75_l200_v1", "displacement"),
        (F_BURST_A2A, "bursty alltoall drops to 70% of its uncongested baseline", "(unattributed per staging)", "AllToAll", B_BURST_A2A, "crossbar8_gf07_a2a70_l200_v1", "displacement"),
        (None, None, "Nanjing", "AllToAll (absolute measured pair, peak leg)", B_NJ_PEAK, "crossbar8_gf07_njpeak22_5_l200_v1", "absolute"),
        (F_NSJB_PAIR, "drops to 120 Gb/s with NSLB disabled (~33% loss)", "Nanjing", "AllToAll (absolute measured pair, NSLB-off leg)", B_NJ_OFF, "crossbar8_gf07_njoff15_l200_v1", "absolute"),
        (F_STEADY_INCAST, "performance dropping to 60% of the uncongested case", "CRESCO8", "collectives under steady incast", B_STEADY_INCAST, "crossbar8_gf07_inc60_l200_v1", "displacement"),
        (F_LEONARDO_COLLAPSE, "collapse to 0.2 (more than a 5x slowdown) at 32-64 nodes", "Leonardo", "collectives under incast", B_COLLAPSE, "crossbar8_gf07_leo20_l200_v1", "displacement"),
        (F_BURSTY_INCAST, "bursty incast 64 nodes: ratio approximately 0.08 (exact reading)", "CRESCO8", "collectives under bursty incast", B_BURSTY, "crossbar8_gf07_burst8_l200_v1", "displacement"),
        (F_WORST, "slowdowns up to 25x", "CRESCO8", "AllToAll victims under steady incast", B_WORST, "crossbar8_gf07_worst4_l200_v1", "displacement"),
    ]:
        row = {
            "topology_id": tid,
            "kind": kind,
            "fabric": fabric,
            "victim_class": victim,
            "quote": quote,
            "B_executed": str(b),
        }
        if kind == "displacement":
            row["factor_exact"] = str(factor)
            row["factor_float"] = float(factor)
            row["asymptotic_cct_ratio_vs_carrier_exact"] = str(factor)
        else:
            row["factor_exact"] = str(factor) if factor else None
            row["asymptotic_cct_ratio_vs_carrier_exact"] = str(B_CARRIER / b)
            row["note"] = (
                "MEASURED ABSOLUTE bandwidth (the only ones staged), NOT a "
                "displacement of the carrier: the ratio to the carrier is a "
                "cross-fabric scale contrast, not a congestion factor"
            )
        rows.append(row)
    rows.sort(key=lambda r: Fraction(r["B_executed"]), reverse=True)
    return {
        "carrier_point": f"B_ref = {B_CARRIER} B/ns = LUMI's staged per-node aggregate (declared reading; the managed-floor fabric — natural uncongested reference)",
        "mapping_technique": "stage A11's / GF-05's congestion-envelope -> effective-bandwidth displacement technique, with GF-07's stronger bridge: the anchor's outcomes are collective BANDWIDTH RATIOS, so factor = 1/ratio is dimensionally exact for a fixed-size collective (no metric-bridge inexpressibility claim is needed, unlike GF-05's FCTs); what remains inexpressible is the MECHANISM (no congestion/queueing/load-balancing/adaptive-routing input key) and the anchor stages no absolute (size -> time) series",
        "victim_class_audit": "8 of the 9 factor quotes are incast/AllToAll victim classes — L0 supports ONLY allreduce (incast/AllToAll collectives do not exist in the input space); every factor enters the AllReduce identity's B axis as a DECLARED dimensionless displacement; the one AllReduce-class quote (4/3) is still an AllReduce-vs-AllToAll COMPARISON whose AllToAll side has no counterpart",
        "rows": rows,
        "recorded_not_executed": {
            str(B_BURSTY_ALT): "the paper's own '12x slower' gloss of the 0.08 quote — mutually inconsistent with the exact reading (1/0.08 = 12.5 = 25/2, executed as B=8); 100/12 = 25/3 is non-representable; BOTH readings kept, never conflated",
            str(B_BLOCKED): "CRESCO8's staged 1.67:1 blocking as a first-order effective-B displacement (10000/167 ~ 59.88); non-representable; the fat-tree tier structure itself is inexpressible",
        },
        "executed_rows_provenance": {str(b): role for tid, b, role in ENV_ROWS},
    }


def envelope_mapping(sweep_id: str) -> dict:
    by, table = _by_cell(sweep_id)
    b_by_tid = {tid: b for tid, b, _role in ENV_ROWS}
    # Cross-check EVERY executed row against the closed form (exact string
    # equality of Fractions).
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, b_by_tid[tid], R_SMOKE)), (tid, m)
        checked += 1
    assert checked == len(ENV_ROWS) * len(LADDER_R8) == 242
    # Displacement signature: the CCT ratio vs the carrier row rises
    # strictly monotonically with payload toward the exact asymptote
    # B_carrier/B_row, on every displacement row.
    asymptote = {tid: B_CARRIER / b for tid, b, _ in ENV_ROWS}
    signature = {}
    for tid in b_by_tid:
        if tid == "crossbar8_gf07_rate100_l200_v1":
            continue
        prev = None
        for m in LADDER_R8:
            ratio = by[(tid, m)] / by[("crossbar8_gf07_rate100_l200_v1", m)]
            if prev is not None:
                assert ratio > prev, (tid, m)
            assert ratio < asymptote[tid], (tid, m)
            prev = ratio
        signature[tid] = {
            "asymptotic_ratio_exact": str(asymptote[tid]),
            "ratio_at_16mib_exact": str(prev),
            "ratio_at_16mib_float": float(prev),
            "ratio_at_2mib_exact": str(by[(tid, 2097152)] / by[("crossbar8_gf07_rate100_l200_v1", 2097152)]),
            "ratio_at_8b_exact": str(by[(tid, 8)] / by[("crossbar8_gf07_rate100_l200_v1", 8)]),
        }
    # Wire-conservation audit: per-rank wire = 2(r-1)/r*M = 7M/4 on r=8.
    wire_ok = all(
        row["per_rank_wire_bytes_exact"] == str(Fraction(7 * row["payload_bytes"], 4))
        for row in table["configs"]
    )
    assert wire_ok
    return {
        "claim": "the anchor's MEASURED congestion envelope maps onto the L0 B axis as exact-fraction displacements; the executed rows reproduce the envelope's ORDERING and the A11/GF-05 displacement signature (ratio rises strictly monotonically toward the exact asymptote as payload grows) on all 242 rows, cross-checked against the closed form by exact Fraction string equality",
        "rows_cross_checked": checked,
        "closed_form": "t = 2(r-1)/r*M/B + 2L = 7/4*M/B + 400 at r=8, L=200 (registry)",
        "signature_by_row": signature,
        "row_at_anchor_16mib": {
            tid: {
                "cct_ns_exact": str(by[(tid, 16777216)]),
                "cct_ns_float": float(by[(tid, 16777216)]),
            }
            for tid in b_by_tid
        },
        "monotonicity_note": "every non-carrier row's ratio vs the carrier is strictly increasing over the anchor's own 8 B - 16 MiB range and strictly below its exact asymptote at every size — the observed slowdown at finite size is ALWAYS below the anchor's headline factor, converging to it as the latency fraction 2L/t vanishes (0.136% at 16 MiB on the carrier row)",
    }


def carrier_transfer(sweep_id: str) -> dict:
    by, _table = _by_cell(sweep_id)
    b_by_tid = {tid: b for tid, b, _role in CARRIER_ROWS}
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, b_by_tid[tid], R_SMOKE)), (tid, m)
        checked += 1
    assert checked == len(CARRIER_ROWS) * len(LADDER_R8) == 88
    # The transfer property: with x = c_rank*M/B_ref, ratio(x) = (x*f+2L)/(x+2L)
    # is strictly increasing in x, hence ratio_50(M) > ratio_100(M) at every
    # finite M (the slower carrier reads CLOSER to the factor), equality only
    # in the bandwidth-bound limit.
    per_size = {}
    for m in LADDER_R8:
        r100 = by[("crossbar8_gf07_leo20_l200_v1", m)] / by[("crossbar8_gf07_rate100_l200_v1", m)]
        r50 = by[("crossbar8_gf07_leo10_l200_v1", m)] / by[("crossbar8_gf07_rate50_l200_v1", m)]
        assert r50 > r100, m
        assert r100 < F_LEONARDO_COLLAPSE and r50 < F_LEONARDO_COLLAPSE
        per_size[m] = {
            "ratio_at_lumi_rate_exact": str(r100),
            "ratio_at_lumi_rate_float": float(r100),
            "ratio_at_leonardo_rate_exact": str(r50),
            "ratio_at_leonardo_rate_float": float(r50),
        }
    return {
        "claim": "a congestion factor is a PER-FABRIC dimensionless ratio: mapped onto the B axis it is asymptotically carrier-independent, but at FINITE size the observed CCT ratio depends on the carrier rate through the latency fraction — the SAME factor 5 (Leonardo's own staged 0.2 collapse) executes to DIFFERENT observed ratios on the two staged fabric rates at every one of the 22 sizes",
        "rows_cross_checked": checked,
        "headline_mid_size_8kib": per_size[8192],
        "headline_2mib": per_size[2097152],
        "headline_16mib": per_size[16777216],
        "per_size": per_size,
        "property": "ratio_50(M) > ratio_100(M) strictly at every finite M (executed at all 22 sizes; closed form d/dx[(x*f+2L)/(x+2L)] = 2L(f-1)/(x+2L)^2 > 0 with x = c_rank*M/B_ref); consequence: cross-fabric transfer of congestion magnitudes is EXACT only in the bandwidth-bound limit — at the 8 KiB member the same factor 5 reads as ~2.06x on a LUMI-rate fabric and ~2.67x on Leonardo's rate, a ~30% discrepancy in the OBSERVED slowdown",
        "asymptote": str(F_LEONARDO_COLLAPSE),
    }


def scale_and_schedule(sweep_id: str) -> dict:
    by, table = _by_cell(sweep_id)
    # Cross-check all 57 rows against the closed forms.
    checked = 0
    for (tid, m), cct in by.items():
        if tid == "ring64_gf07_rate100_l200_v1":
            expected = t_ring(m, B_CARRIER, R_ANCHOR)
        else:
            b = B_CARRIER if tid == "crossbar64_gf07_rate100_l200_v1" else B_WORST
            expected = t_xbar(m, b, R_ANCHOR)
        assert str(cct) == str(expected), (tid, m)
        checked += 1
    assert checked == 3 * len(LADDER_R64) == 57
    # Structural facts.
    assert c_rank(R_ANCHOR) == Fraction(63, 32)
    assert c_rank(R_ANCHOR) / c_rank(R_SMOKE) == Fraction(9, 8)
    # Ring-minus-crossbar is exactly 2(r-2)L at every size.
    for m in LADDER_R64:
        delta = by[("ring64_gf07_rate100_l200_v1", m)] - by[("crossbar64_gf07_rate100_l200_v1", m)]
        assert delta == 2 * (R_ANCHOR - 2) * L_REGISTRY == 24800, m
    # Regime boundary M* = L*B*r and the exact at-M* ratio.
    m_star = L_REGISTRY * B_CARRIER * R_ANCHOR
    assert m_star == 1280000
    assert t_ring(1280000, B_CARRIER, R_ANCHOR) == 50400
    assert t_xbar(1280000, B_CARRIER, R_ANCHOR) == 25600
    assert Fraction(50400, 25600) == Fraction(63, 32) == c_rank(R_ANCHOR)
    # Bracketing members and the endpoint.
    ratio_1mib = by[("ring64_gf07_rate100_l200_v1", 1048576)] / by[("crossbar64_gf07_rate100_l200_v1", 1048576)]
    ratio_2mib = by[("ring64_gf07_rate100_l200_v1", 2097152)] / by[("crossbar64_gf07_rate100_l200_v1", 2097152)]
    ratio_16mib = by[("ring64_gf07_rate100_l200_v1", 16777216)] / by[("crossbar64_gf07_rate100_l200_v1", 16777216)]
    worst_vs_ceiling_16mib = by[("crossbar64_gf07_worst4_l200_v1", 16777216)] / by[("crossbar64_gf07_rate100_l200_v1", 16777216)]
    wire_ok = all(
        row["per_rank_wire_bytes_exact"] == str(Fraction(2 * 63 * row["payload_bytes"], 64))
        for row in table["configs"]
    )
    assert wire_ok
    return {
        "rows_cross_checked": checked,
        "rank_coefficient": {
            "c_rank_r64_exact": "63/32",
            "vs_r8_default": "exactly 9/8 (+12.5%): (63/32)/(7/4) = 63/56 = 9/8 — rank-count structure sits INSIDE the measured envelope's lower band (between the 20/19 and 4/3 rows), inseparable from mild congestion in a raw reading",
        },
        "schedule_contrast": {
            "identity": "ring and crossbar share the bandwidth coefficient 63/32; ring-minus-crossbar = 2(r-2)L = 24,800 ns EXACTLY at every one of the 19 sizes (verified)",
            "ring_latency_chain_ns": "2*(r-1)*L = 25,200 vs the crossbar's 2L = 400",
            "ratio_at_1mib_exact": str(ratio_1mib),
            "ratio_at_1mib_float": float(ratio_1mib),
            "ratio_at_2mib_exact": str(ratio_2mib),
            "ratio_at_2mib_float": float(ratio_2mib),
            "ratio_at_16mib_exact": str(ratio_16mib),
            "ratio_at_16mib_float": float(ratio_16mib),
            "regime_boundary": "M* = L*B*r = 1,280,000 B (the payload where the ring's latency chain equals its bandwidth term) — bracketed by the 1 MiB and 2 MiB ladder members; at M* itself the ring/crossbar ratio is EXACTLY 63/32 = 1.96875 (t_ring = 4(r-1)L = 50,400, t_crossbar = 2(r-1)L + 2L = 25,600; closed form, off-grid) — the SAME value as the bandwidth coefficient: at M* the ring doubles its latency term into both terms and the ratio collapses to 2(r-1)/r",
        },
        "ceiling_vs_worst": {
            "row_honesty": "the crossbar64 B=100 row is the NON-BLOCKING single-stage CEILING abstraction at the anchor's own 64-node scale (the bursty-incast configuration) — never a prediction of CRESCO8's blocked fat tree; the B=4 row displaces it by the anchor's worst measured factor 25",
            "ratio_at_16mib_exact": str(worst_vs_ceiling_16mib),
            "ratio_at_16mib_float": float(worst_vs_ceiling_16mib),
        },
    }


def confounder_separation() -> dict:
    return {
        "role": "the R3 classification the stage was assigned: order the axes by magnitude at the anchor's own scale, from the anchor's own numbers and the executed identities",
        "four_confounders_ordered_by_magnitude": {
            "1_congestion_envelope_measured": "20/19 -> 25 (the anchor's subject; managed-to-worst span exactly 95/4 = 23.75) — the DOMINANT axis by more than an order of magnitude over everything else",
            "2_schedule_structure_executed": "ring/crossbar at r=64: 2.18 (1 MiB) falling to 1.075 (16 MiB), exactly 63/32 = 1.96875 at M* = 1.28 MiB, -> 1 asymptotically — INSIDE the measured envelope",
            "3_rank_count_structure_executed": "exactly 9/8 = +12.5% (63/32 vs 7/4) — inside the envelope's lower band, between the floor 20/19 and the AllReduce row 4/3",
            "4_carrier_rate_choice_executed": "the same factor reads differently per fabric at finite size (carrier sweep): at 8 KiB, factor 5 reads ~2.06x at the LUMI rate vs ~2.67x at Leonardo's rate — a ~30% swing in the OBSERVED slowdown from the carrier alone",
        },
        "dominance_over_noise_floors": "the managed floor 20/19 (~+5.26%) is the ONLY envelope member at the anchor set's noise floors (CAL-A4 ~5% validated band, CAL-A6 5-8% software swing); every unmanaged member (4/3 and up) exceeds them by multiples — a congestion-blind comparison in this regime cannot attribute residuals below the envelope",
        "conclusion": "REVERSE of GF-05's ordering: at GF-07's scale (r=64, <=16 MiB vectors) the un-modeled axis (congestion) dominates schedule and rank structure, so any CCT comparison in this regime MUST pin the congestion state before a residual is attributable to anything calibratable; the measured band 20/19 - 25 is exactly the falsification envelope any future congestion-modeling backend must reproduce, and the carrier-relativity property bounds how its factors transfer across fabric classes",
    }


def expressiveness_classification() -> dict:
    return {
        "CAN_express": {
            "fabric_rate_placement": "the two STAGED per-node fabric rates on the B axis (LUMI 100, Leonardo 50 — declared per-node-aggregate -> single-port readings); the two measured absolute AllToAll-class bandwidths (22.5, 15) and their exact pair factor 3/2",
            "envelope_magnitudes": "every measured factor as an exact-fraction effective-B displacement with the dimensionally exact ratio->factor bridge (stronger than GF-05's FCT case); executed {20/19, 4/3, 10/7, 5/3, 5, 25/2, 25} at the carrier, {5} at both carriers; recorded {12, 10000/167}",
            "carrier_relativity": "the finite-size carrier dependence of an observed factor (executed at 22 sizes, both staged carriers)",
            "scale_and_schedule_structure": "the non-blocking ceiling, its worst displacement, and the ring contrast at the anchor's 64-node scale (exact 24,800 ns differences, M* = 1,280,000 with ratio exactly 63/32, coefficient 63/32 = 9/8 x the r=8 default)",
        },
        "CANNOT_express": {
            "congestion_mechanism": "incast trees, queueing, victim/interferer dynamics — 'congestion' is in explicitly_unsupported for both backends; no key exists",
            "management_mechanisms": "DCQCN (sawtooth > 16 MiB), NSLB (Nanjing), per-flow HW congestion management + global-aware adaptive routing (LUMI's floor), Swift-class CC — no input keys; only their measured magnitudes enter",
            "victim_collective_classes": "incast and AllToAll — the victim classes of 8 of 9 factor quotes — are not L0 collectives (allreduce only); the AllReduce quote's own baseline is an AllToAll comparison with no counterpart",
            "interference_threshold": "'even at ~2% of a partition' — a threshold on exogenous interfering-traffic fraction; no key",
            "iteration_statistics": "1,000 iterations / 100 warmup — a measurement protocol; the L0 identity is deterministic with no repetition semantics to express it",
            "topology_classes": "IB Dragonfly+, 1.67:1-blocking fat tree, Slingshot dragonfly, RoCE CLOS — no landed topology_class; the crossbar is a ceiling abstraction (the blocking's first-order displacement 10000/167 recorded)",
            "direction_conventions": "the staged Gb/s rates carry no per-direction split — flagged, single declared reading per rate",
        },
        "consequence_for_calibration": "GF-07 can never calibrate L0-family O-CCT directly: it stages NO (size -> time) series, its victim collective classes are unsupported, and its subject axis is declared out of model scope. Its calibrated use — the R3 falsification envelope (20/19 -> 25, span exactly 95/4) any congestion-modeling backend must reproduce, plus the only measured absolute bandwidth pair (180/120 Gb/s, factor exactly 3/2) and the carrier-relativity bound on factor transfer — is an owner design decision this record stages, mirroring A11's scale-out-profile note and GF-05's classification",
    }


def registry_placements() -> dict:
    assert B_CARRIER / B_REGISTRY == Fraction(25, 16)
    assert B_STEADY_INCAST < B_REGISTRY < B_BURST_A2A  # 60 < 64 < 70
    executed = sorted(b for _t, b, _r in ENV_ROWS)
    return {
        "A-L0X-BW_point_64_vs_carrier_100": {
            "asymptotic_cct_ratio_exact": "25/16",
            "asymptotic_cct_ratio_float": 1.5625,
            "band_membership": "60 (factor 5/3) < 64 < 70 (factor 10/7): the registry default B sits INSIDE the anchor's measured congestion envelope band — an L0 run at registry defaults produces CCTs numerically indistinguishable from a 25-43% congested collective on the anchor's fabrics (placement fact, never a tuning target)",
        },
        "A-L0X-LAT_A-L0-LAT": {
            "statement": "GF-07 stages NO latency number — the registry point 200 was kept throughout (A11 precedent); no latency-axis placement exists for this anchor",
        },
        "anchored_span_membership": {
            "note": f"executed B values {executed}: below the plan §2.1 anchored span [20, 64] — {{4, 8, 10, 15}} (the unmanaged envelope displacements and the Nanjing absolute pair); inside — {{20, 22.5, 50, 60, 64}}; above — {{70, 75, 95, 100}} (the mild displacements and the LUMI carrier). The unmanaged congestion regime extends an order BELOW the anchored span; recorded, the registry range is untouched",
        },
        "cross_anchor_coincidences": {
            "100_bytes_per_ns": "numerically identical to GF-05's uet-htsim sim line rate (800 Gbps per direction) — one executed row family per anchor, never cross-derived; also exactly 2x Leonardo's staged rate",
            "50_bytes_per_ns": "numerically identical to CAL-A1's derived NVLink5 per-port rate, CAL-A5's staged ICI rate, and CAL-A11's 400G optics rate (the GF-05 record noted the same coincidence class)",
            "20_bytes_per_ns": "numerically identical to GF-05's RoCE x5 displacement value (100/5) — same displacement arithmetic applied to a MEASURED factor here, coincidence of technique recorded",
        },
    }


def recorded_ambiguities() -> dict:
    return {
        "ratio_008_vs_12x": {
            "ambiguity": "the staged sentence 'a ratio of approximately 0.08 (i.e., 12x slower)' is MUTUALLY INCONSISTENT: 1/0.08 = 12.5 exactly (factor 25/2), while the gloss 12x implies ratio 1/12 = 0.0833...",
            "resolution_followed": "the exact-decimal 0.08 reading was EXECUTED (B = 8 = 100 x 2/25); the 12x reading's displacement 25/3 is non-representable and RECORDED NOT EXECUTED; both kept side by side, never conflated (the owner adjudicates at integration)",
        },
        "carrier_choice": {
            "ambiguity": "the anchor's ratios are measured per-fabric against each fabric's OWN uncongested baseline; NO shared reference fabric or absolute uncongested series is staged, so the displacement mapping requires a carrier B_ref that is a DECLARED choice",
            "resolution_followed": "carrier = 100 (LUMI's staged per-node aggregate — the managed-floor fabric, hence the natural uncongested reference); Leonardo's 50 executed as the alternative carrier; the carrier-relativity of observed factors at finite size is itself EXECUTED (carrier sweep) and bounds every mapping",
        },
        "per_node_aggregate_to_single_port": {
            "ambiguity": "'4x200 Gb/s' (LUMI) and '400 Gb/s/node' (Leonardo) are per-node aggregates; the L0 B is a per-rank SINGLE-PORT injection (A-L0X-PORT); no direction split is staged for any rate",
            "resolution_followed": "declared first-order reading: per-node aggregate / 8 = B on the single-port axis (4 NICs collapsed to one port); direction conventions left flagged — a reversal rescales by closed form",
        },
        "collective_class_mismatch": {
            "ambiguity": "8 of 9 factor quotes are incast/AllToAll victim classes; L0 supports only allreduce; even the one AllReduce-class quote (25% loss) is an AllReduce-vs-AllToAll comparison whose AllToAll side has no counterpart",
            "resolution_followed": "every factor enters the AllReduce identity's B axis as a DECLARED dimensionless displacement (A11/GF-05 technique); the class mismatch is carried on every row, and NO anchor-time comparison is attempted anywhere",
        },
        "absolute_pair_congestion_state": {
            "ambiguity": "the Nanjing '180 Gb/s' peak's own baseline (uncongested state) is NOT staged — 'peak' is read as the uncongested leg by declaration; the pair factor 3/2 is baseline-free (same fabric, NSLB on/off)",
            "resolution_followed": "both absolute values executed on the B axis as measured placements; the pair factor used as the anchor-backed envelope member; the peak's state reading flagged",
        },
        "envelope_edges_not_means": {
            "ambiguity": "the 'up to 25x' / 'up to 25% loss' quotes are worst-case EDGES of measured distributions; the iteration protocol (1,000/100) is staged but no dispersion statistics are",
            "resolution_followed": "rows are placed at the EDGE values, labeled as such; no mean/variance claim is made anywhere in the record",
        },
        "scale_out_domain": {
            "ambiguity": "all five fabrics are HPC SCALE-OUT interconnects, not GPU scale-up; the staging doc's own caveat: 'metrics are collective bandwidth ratios, not O-CCT series'",
            "resolution_followed": "staged under the labeled-proxy rule (CAL-A11 class) — usable as the R3 falsification envelope, never as scale-up calibration evidence; no E3/E4 language",
        },
        "blocking_factor_reading": {
            "ambiguity": "CRESCO8's '1.67:1 blocking' is a fat-tree tier-capacity ratio; reading it as a first-order effective-B displacement ignores queueing and tier structure (both inexpressible)",
            "resolution_followed": "exact fraction 167/100; displacement 10000/167 recorded NOT executed (non-representable, and structural honesty: the displacement is first-order only)",
        },
        "unattributed_quotes": {
            "ambiguity": "the staging doc does not attribute the steady-incast 60%, bursty-alltoall 70%, AllReduce 25%, DCQCN sawtooth, and 2%-of-partition quotes to specific fabrics (several read as CRESCO8/HAICGU context but are not labeled per-fabric in the staged text)",
            "resolution_followed": "factors carried with '(unattributed per staging)' fabric labels where the staging text does not name the fabric; no attribution inferred",
        },
        "lumi_floor_attribution": {
            "ambiguity": "LUMI's 'within 5%' floor is the behavior of ITS SPECIFIC management stack (per-flow HW CM + global-aware adaptive routing) — a mechanism configuration, not a fabric property",
            "resolution_followed": "the floor magnitude 20/19 is executed as the envelope's lower edge with the mechanism explicitly inexpressible; the row is the MANAGED pole of the falsification envelope, never a claim that dragonfly class floors at 5%",
        },
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-07 (gap-fill anchor GF-07)",
        "anchor": {
            "anchor_id": "GF-07",
            "title": "Congestion impact characterization (arXiv 2026): measured collective slowdowns across 5 HPC fabrics (R3)",
            "source_row": "gap-fill anchor — NOT yet a sources.csv row (the owner integrates accepted rows; this stage made no handoff write)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-07",
            "urls": ["https://arxiv.org/html/2604.11432v1"],
            "confidence": "H (numbers extracted from the paper HTML; used AS STAGED, not re-fetched). Caveat classes carried: MEASURED production/testbed numbers on HPC SCALE-OUT fabrics (labeled proxy per CAL-A11 — not GPU scale-up, not UEC silicon); outcome metrics are collective BANDWIDTH RATIOS, not O-CCT series; 'up to' quotes are envelope edges",
            "staged_numbers": "Leonardo HDR IB Dragonfly+ 400 Gb/s/node; CRESCO8 NDR IB 1.67:1 blocking fat tree; LUMI Slingshot 4x200 Gb/s; HAICGU EDR IB+RoCE (no numbers); Nanjing RoCE NSLB; victims 1,000 iterations / 100 warmup; vectors 8 B - 16 MiB; ratios: 25x, 60%, 0.08 ('12x'), 70%, 0.2 (5x), within 5%, 180 -> 120 Gb/s (~33%), AllReduce 25% loss, ~2% of a partition, DCQCN sawtooth > 16 MiB",
        },
        "target": {
            "role": "r3_measured_congestion_effects_envelope",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "GF-07 stages NO (size -> time) series: its outcomes are per-fabric collective BANDWIDTH RATIOS on victim collectives (plus exactly two absolute AllToAll-class bandwidths, 180/120 Gb/s, whose peak's uncongested-state reading is itself declared). The ratio->CCT-factor bridge is dimensionally EXACT for a fixed-size collective — STRONGER than GF-05's FCT case, which was declared inexpressible — but there is no time series to calibrate against, and the victim collective classes (incast, AllToAll) are not L0 collectives. The extractable targets — the two staged fabric rates, the measured envelope factors, the absolute pair, the stated 64-node scale — ARE executed here as placement and mapping, which is exactly the R3 falsification-envelope role the gap-fill doc assigns",
            "regime": {
                "topology_class": "IB Dragonfly+ / blocked fat tree (1.67:1) / Slingshot dragonfly / RoCE CLOS — NO landed topology_class; executed on the NON-BLOCKING single-stage abstraction (fully_connected_crossbar) as ceiling rows plus one multi-hop ring row as the schedule contrast at r=64",
                "ranks": {
                    "executed": [R_SMOKE, R_ANCHOR],
                    "provenance": "r=8 free smoke default (envelope/carrier sweeps and the run pair); r=64 the anchor's largest STAGED exact node count (the bursty-incast configuration; top of the Leonardo collapse range 32-64)",
                },
                "message_bytes_ladders": {
                    "envelope_and_carrier_sweeps": LADDER_R8,
                    "scale_sweep": LADDER_R64,
                },
                "message_regime_note": "the anchor's OWN staged vector range 8 B - 16 MiB executed in full as the power-of-2 ladder 8*2^k (both endpoints members; 16 MiB is also the DCQCN-threshold size); the run pair executes exactly the 16 MiB maximum",
            },
        },
        "anchor_derived": derived,
        "envelope_factor_table": envelope_factor_table(),
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (envelope rows and carrier rows at r=8; ceiling + worst-displacement rows at r=64)",
                "analytical_l0 (ring; one row at r=64 — the schedule-structure contrast at the anchor's own scale)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; envelope sweep B in {100, 95, 75, 70, 64, 60, 22.5, 20, 15, 8, 4} at L=200; carrier sweep B in {100, 50} x {uncongested, /5}; scale sweep B in {100, 4} at L=200, r=64",
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L ; B=100, L=200, r=64",
            },
            "free_parameters": {
                "B_injection_swept_ns": "see envelope_factor_table.executed_rows_provenance — {100 LUMI carrier, 95 (20/19), 75 (4/3), 70 (10/7), 64 registry, 60 (5/3), 22.5 Nanjing peak absolute, 20 (5), 15 Nanjing NSLB-off absolute, 8 (25/2 exact-0.08), 4 (25)}; carrier sweep adds {50 Leonardo carrier, 10 = 50/5}; scale sweep {100, 4} at r=64",
                "L_pair_swept_ns": "{200} — the A-L0X-LAT registry point throughout: GF-07 stages NO latency number (A11 precedent)",
                "ranks": {"8": "free smoke default", "64": "the anchor's largest staged exact node count"},
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar); A-L0-BW/A-L0-LAT/A-L0-FD/A-L0-DIV (ring) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_CARRIER100,
                    "envelope carrier point (B=100 B/ns = LUMI's staged 4x200 Gb/s per-node aggregate, declared reading; L=200 ns registry — GF-07 stages no latency; payload 16 MiB = the anchor's maximum staged vector and DCQCN-threshold size)",
                ),
                run_summary(
                    RUN_ID_XBAR_REGISTRY,
                    "registry twin (B=64 B/ns, L=200 ns — both free registry points; the SAME payload isolates the B axis; both latency terms exactly 400 ns)",
                ),
            ],
            "run_pair_placement": {
                "cct_ratio_registry_vs_carrier_exact": "717425/459377",
                "cct_ratio_registry_vs_carrier_float": float(Fraction(717425, 459377)),
                "cct_delta_registry_minus_carrier_ns_exact": "4128768/25",
                "cct_delta_registry_minus_carrier_ns_float": float(Fraction(4128768, 25)),
                "statement": "at the anchor's own 16 MiB maximum vector the registry twin sits at 459,152 ns vs the carrier row's 7350032/25 = 294,001.28 ns — ratio exactly 717425/459377 (~1.562), 0.2% below the pure-B asymptote 25/16 = 1.5625 (the 400 ns latency terms are 0.136%/0.087% of the two CCTs): the registry defaults sit INSIDE the anchor's measured congestion envelope band, numerically indistinguishable from a 25-43% congested collective — placement arithmetic, never a tuning target",
            },
            "reconciled_sweep_envelope": sweep_rows(SWEEP_ID_ENVELOPE, "ladder"),
            "envelope_mapping": envelope_mapping(SWEEP_ID_ENVELOPE),
            "reconciled_sweep_carrier": sweep_rows(SWEEP_ID_CARRIER, "ladder"),
            "carrier_transfer": carrier_transfer(SWEEP_ID_CARRIER),
            "reconciled_sweep_scale64": sweep_rows(SWEEP_ID_SCALE64, "ladder"),
            "scale_and_schedule": scale_and_schedule(SWEEP_ID_SCALE64),
            "confounder_separation": confounder_separation(),
            "expressiveness_classification": expressiveness_classification(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — GF-07 stages no CCT-class series at all: its outcomes are collective bandwidth ratios on victim collectives (plus two absolute AllToAll-class bandwidths with a declared uncongested-state reading). Per the stage prompt's FAIL clause the inextractable time target is RECORDED and SKIPPED honestly — no comparison against any anchor time is attempted anywhere; the anchor's assigned role (the R3 measured envelope) IS extractable and is executed above",
            "placement_summary": "the model's axes: two staged fabric rates on the B axis (LUMI 100, Leonardo 50; declared per-node-aggregate -> single-port readings); the measured envelope 20/19 -> 25 mapped to exact-fraction displacements, all executed rows reproducing the ordering and the monotone displacement signature (242 rows closed-form-cross-checked); the only measured absolute pair (22.5/15 B/ns, factor exactly 3/2); the same factor 5 executed at BOTH carriers demonstrating finite-size carrier relativity (~2.06x vs ~2.67x at 8 KiB — a ~30% observed-slowdown swing from the carrier alone); at the anchor's 64-node scale, rank structure (exactly 9/8) and schedule structure (1.075-2.18, exactly 63/32 at M* = 1,280,000 B) both sit INSIDE the measured envelope — the un-modeled congestion axis dominates by more than an order of magnitude, the REVERSE of GF-05's ordering",
            "span_placement": "executed B values {4, 8, 10, 15, 20, 22.5, 50, 60, 64, 70, 75, 95, 100}: the unmanaged congestion regime extends an order BELOW the plan §2.1 anchored span [20, 64] and the mild displacements sit above it; L never moved (no staged latency); recorded, registry untouched",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the R3 measured-envelope role; no E3/E4 language — GF-07 is an external published measurement study on scale-out HPC fabrics, not our testbed, and not GPU scale-up (labeled proxy)",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_CARRIER100, RUN_ID_XBAR_REGISTRY],
            "sweep_ids": [SWEEP_ID_ENVELOPE, SWEEP_ID_CARRIER, SWEEP_ID_SCALE64],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_ENVELOPE}",
                f"results/sweeps/{SWEEP_ID_CARRIER}",
                f"results/sweeps/{SWEEP_ID_SCALE64}",
            ],
            "run_backed_numbers": "every model output in comparison.anchor_point_runs and comparison.reconciled_sweep_*; comparison.envelope_mapping, carrier_transfer and scale_and_schedule cross-check closed forms against all 387 executed sweep rows by exact Fraction string equality (declared inline); comparison.run_pair_placement, confounder_separation, expressiveness_classification, registry_placements, the M*-point values and the recorded-not-executed displacements are identity/anchor-registry arithmetic declared inline",
            "inputs": [
                "experiments/calibration/gf07/sweep_gf07_envelope_v1.yaml",
                "experiments/calibration/gf07/sweep_gf07_carrier_v1.yaml",
                "experiments/calibration/gf07/sweep_gf07_scale64_v1.yaml",
                "experiments/calibration/gf07/run_gf07_carrier100_v1.yaml",
                "experiments/calibration/gf07/run_gf07_registry_v1.yaml",
                "experiments/calibration/gf07/workloads/ (2 files)",
                "experiments/calibration/gf07/topologies/ (16 files)",
                "experiments/calibration/gf07/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf07/run_gf07_carrier100_v1.yaml ; "
            "make run EXP=experiments/calibration/gf07/run_gf07_registry_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf07/sweep_gf07_envelope_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf07/sweep_gf07_carrier_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf07/sweep_gf07_scale64_v1.yaml ; "
            "python experiments/calibration/gf07/build_calibration_record.py",
        },
    }

    # Exact-value self-checks on the executed run pair (transcription guards).
    obs100 = load_json(RESULTS / RUN_ID_XBAR_CARRIER100 / "observations.json")
    obsreg = load_json(RESULTS / RUN_ID_XBAR_REGISTRY / "observations.json")
    t100 = Fraction(obs100["per_op"][0]["completion_time_ns_exact"])
    treg = Fraction(obsreg["per_op"][0]["completion_time_ns_exact"])
    assert t100 == t_xbar(RUN_PAYLOAD, B_CARRIER, R_SMOKE)
    assert treg == t_xbar(RUN_PAYLOAD, B_REGISTRY, R_SMOKE)
    assert t100 == Fraction(7350032, 25) and treg == 459152
    assert treg / t100 == Fraction(717425, 459377)
    assert treg - t100 == Fraction(4128768, 25)
    assert 2 * L_REGISTRY / t100 == Fraction(625, 459377)

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
