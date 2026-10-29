"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-08
(calibration stage GF-08).

GF-08 = "Falcon: A Reliable, Low Latency Hardware Transport" (Singhvi et
al., ACM SIGCOMM 2025) — Google's shipped reliable hardware transport on
commodity lossy PFC-free Ethernet (multi-ULP RDMA/NVMe; delay-based HW
congestion control + multipath packet spraying + selective retransmission;
implemented on the Intel IPU E2000 per the OCP/Google blog). Stage role
(gap-fill doc §GF-08): R1 — UEC-class transport on REAL hardware, the
hardware bookend paired with GF-05 (sim); architecturally the closest
shipped relative of UEC's UET design points.

Pure function of immutable artifacts: reads the two append-only store
run records and the two sweep tables produced by this stage, recomputes
every derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_gapfill.md`` §GF-08
(numbers AS STAGED, not re-fetched), or (b) computed from the stored
run/sweep artifacts by this script, or (c) exact closed-form identity
arithmetic cross-checked against executed artifacts by exact Fraction
string equality (declared inline wherever used). Nothing is tuned: every
swept B value carries its anchor/registry provenance, and the record
measures where the model output sits relative to the anchor's endpoint
rate, measured factors, and implied per-op scale.

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
RUN_ID_XBAR_FALCON25 = "78aa3a85f3e0851d903a4664bfacf85f393d02da296a699f2da8741b2c951256"
RUN_ID_XBAR_REGISTRY = "738ca52491198219de2ffa69e5925dfb44878749dbc299b40de0c03aa9dd2086"
SWEEP_ID_ENVELOPE = "edc4f8226fea0fe132d72cd6d4a667456c9b28bf84586906e13141041eeb5735"
SWEEP_ID_CARRIER = "c96c69349f0cbfbcb6dc164bcf9580a1be7aa5c5774dfdd95a0325d4dfb5a507"

RESULTS = REPO_ROOT / "results"

# Anchor GF-08 staged numbers (docs/calibration/anchors_gapfill.md §GF-08;
# confidence M-H — headline numbers verified against the official abstract
# mirror; full paper tables NOT extracted at staging (ACM 403 in the
# staging sandbox; NetDev 0x18 slides fetch failed URL validation)).
# SHIPPED HARDWARE transport (endpoint/NIC-class on scale-out Ethernet,
# not GPU scale-up, not UEC silicon); staged numbers are abstract-level
# headline rates and envelope-edge factors, NOT a (size -> time) series.
GF08_PEAK_GBPS = Fraction(200)        # "peak performance of 200 Gbps"
GF08_MOPS_PER_SEC = Fraction(120 * 10 ** 6)  # "120 Mops/sec"
GF08_STAGING_GLOSS_NS = Fraction(6)   # the staging doc's own "~6 ns/operation amortized" gloss

# Measured dimensionless factors (exact Fractions from the staged quotes).
F_CONGESTION = Fraction(8)            # "8x lower than CX-7 RoCE under network congestion"
F_LOSSY = Fraction(33, 20)            # "up to 65% higher goodput under lossy conditions" (1.65 = 33/20)

# Derived under the DECLARED readings (decimal units, the plan's convention
# 1 GB/s = 1 B/ns; the endpoint peak mapped onto the per-rank single-port
# injection B — A-L0X-PORT first-order; NO direction split staged).
B_FALCON = GF08_PEAK_GBPS / 8                    # 25 B/ns (primary per-endpoint reading)
B_ALT = GF08_PEAK_GBPS / 2 / 8                   # 12.5 B/ns (bidirectional-aggregate reading)
B_REGISTRY = Fraction(64)                        # A-L0X-BW / A-L0-BW registry point
L_REGISTRY = Fraction(200)                       # A-L0X-LAT / A-L0-LAT registry point (GF-08 stages NO latency number)

# Executed displacement rows at the anchor's OWN carrier (representable
# finite decimals) — unlike GF-07 no declared-carrier choice is needed:
# the anchor stages its own absolute rate.
B_ROCE_CONG = B_FALCON / F_CONGESTION            # 25/8 = 3.125
B_ROCE_CONG_ALT = B_ALT / F_CONGESTION           # 12.5/8 = 1.5625

# Recorded NOT executed (non-representable as finite decimals).
B_ROCE_LOSSY = B_FALCON / F_LOSSY                # 500/33
B_ROCE_LOSSY_ALT = B_ALT / F_LOSSY               # 250/33

# Per-op-rate axis (exact identity arithmetic; the "120 Mops/sec" headline).
OPS_PER_NS = GF08_MOPS_PER_SEC / Fraction(10 ** 9)   # 0.12 = 3/25 ops/ns
T_PER_OP_NS = 1 / OPS_PER_NS                          # 25/3 ~ 8.33 ns/op
BYTES_PER_OP = B_FALCON / OPS_PER_NS                  # 625/3 ~ 208.33 B/op
PER_OP_FLOOR_RATIO = (2 * L_REGISTRY) / T_PER_OP_NS   # 400 / (25/3) = 48 EXACTLY
L_IMPLIED_BY_RATE = T_PER_OP_NS / 2                   # 25/6 ~ 4.17 ns (below the registry range lower 10)

R_SMOKE = 8                                       # free smoke default (GF-08 stages NO rank count)

RUN_PAYLOAD = 16384                               # the A-W1-SIZE registry point (a ladder member)

LADDER = [8 * 2 ** k for k in range(22)]          # 8 B -> 16 MiB (declared free-probe grid)

# topology_id -> (B, role label) for the closed-form cross-checks below.
ENV_ROWS = [
    ("crossbar8_gf08_falcon25_l200_v1", B_FALCON, "carrier: Falcon's staged 200 Gbps peak, per-endpoint reading (the anchor's OWN absolute rate — no declared-carrier choice needed)"),
    ("crossbar8_gf08_alt12_5_l200_v1", B_ALT, "bidirectional-aggregate alternative reading of the same 200 Gbps (the reading ambiguity is a factor exactly x2)"),
    ("crossbar8_gf08_reg64_l200_v1", B_REGISTRY, "A-L0X-BW registry point (placement; no GF-08 provenance)"),
    ("crossbar8_gf08_roce8x3_125_l200_v1", B_ROCE_CONG, "8: 'operation completion times 8x lower than CX-7 RoCE under network congestion' (asymptote exactly 8)"),
]

CARRIER_ROWS = [
    ("crossbar8_gf08_falcon25_l200_v1", B_FALCON, "primary carrier (uncongested reference)"),
    ("crossbar8_gf08_roce8x3_125_l200_v1", B_ROCE_CONG, "factor 8 at the primary carrier (25/8)"),
    ("crossbar8_gf08_alt12_5_l200_v1", B_ALT, "alternative carrier (uncongested reference)"),
    ("crossbar8_gf08_roce8xalt1_5625_l200_v1", B_ROCE_CONG_ALT, "the SAME factor 8 at the alternative carrier (12.5/8)"),
]


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction = L_REGISTRY) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def c_rank(ranks: int) -> Fraction:
    """The bandwidth coefficient 2(r-1)/r of the identity."""
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
    assert GF08_PEAK_GBPS / 8 == B_FALCON == 25
    assert B_ALT == Fraction(25, 2) and B_ROCE_CONG == Fraction("3.125") == Fraction(25, 8)
    assert B_ROCE_CONG_ALT == Fraction("1.5625") == Fraction(25, 16)
    assert Fraction("1.65") == Fraction(33, 20) == F_LOSSY
    assert B_ROCE_LOSSY == Fraction(500, 33) and B_ROCE_LOSSY_ALT == Fraction(250, 33)
    assert 1 / Fraction("0.12") == Fraction(25, 3) == T_PER_OP_NS
    assert BYTES_PER_OP == Fraction(625, 3)
    assert PER_OP_FLOOR_RATIO == 48  # 2L = 400 ns is EXACTLY 48x the amortized per-op time
    assert L_IMPLIED_BY_RATE == Fraction(25, 6) and L_IMPLIED_BY_RATE < 10
    assert (2 * 10) / T_PER_OP_NS == Fraction(12, 5)  # even at the range lower bound L=10 the floor is 2.4x
    assert LADDER[0] == 8 and LADDER[-1] == 16 * 1024 * 1024 and len(LADDER) == 22
    assert LADDER[4] == 128 < BYTES_PER_OP < 256 == LADDER[5]  # the ladder brackets the implied per-op size
    assert GF08_STAGING_GLOSS_NS != T_PER_OP_NS  # the staging gloss is mutually inconsistent — see ambiguities
    assert B_REGISTRY / B_FALCON == Fraction(64, 25)  # the registry-placement asymptote
    return {
        "staged_numbers": {
            "system": "Google's Falcon: reliable, low-latency HARDWARE transport on commodity (lossy, PFC-free) Ethernet; multi-ULP (RDMA, NVMe); delay-based HW congestion control + multipath packet spraying + selective retransmission; implemented on the Intel IPU E2000 per the OCP/Google blog (context only — no numbers staged from the blog)",
            "headline": "abstract (MSR mirror), verbatim: 'peak performance of 200 Gbps, 120 Mops/sec'; operation completion times '8x lower than CX-7 RoCE under network congestion'; 'up to 65% higher goodput under lossy conditions'",
            "provenance_class": "M-H confidence — headline numbers verified against the official abstract mirror; full paper tables (latency us, message-rate curves) NOT extracted at staging (ACM 403 in the sandbox; NetDev 0x18 slides fetch failed URL validation) — extract at integration; SHIPPED HARDWARE endpoint transport on SCALE-OUT Ethernet, not GPU scale-up, not UEC silicon (labeled proxy)",
        },
        "derived_arithmetic": {
            "falcon_rate_bytes_per_ns_declared_reading": str(B_FALCON),
            "falcon_rate_derivation": "200 Gb/s / 8 = 25 B/ns (decimal convention 1 GB/s = 1 B/ns; the endpoint peak mapped onto the per-rank single-port injection B — A-L0X-PORT first-order; NO direction split staged, flagged)",
            "alternative_reading_bytes_per_ns": str(B_ALT),
            "carrier_role": "the carrier is the ANCHOR'S OWN absolute rate — unlike GF-07 (per-fabric ratios, no shared reference, DECLARED carrier choice), no declared-carrier choice is needed here; the only reading choice is the direction convention, whose two members are BOTH executed",
            "congestion_factor_exact": str(F_CONGESTION),
            "congestion_factor_note": "'8x lower than CX-7 RoCE under network congestion' — operation completion times, an endpoint-transport metric class; the displacement B = 25/8 = 3.125 is representable and EXECUTED (and 12.5/8 = 1.5625 at the alternative carrier)",
            "lossy_factor_exact": str(F_LOSSY),
            "lossy_factor_note": "'up to 65% higher goodput under lossy conditions' — goodput ratio 1.65 = 33/20 exactly, hence CCT factor 33/20 for a fixed payload; the displacements 500/33 and 250/33 are NON-representable finite decimals — RECORDED NOT EXECUTED",
            "recorded_not_executed": {str(B_ROCE_LOSSY): "the lossy factor at the primary carrier", str(B_ROCE_LOSSY_ALT): "the lossy factor at the alternative carrier"},
            "per_op_time_ns_exact": str(T_PER_OP_NS),
            "per_op_bytes_exact": str(BYTES_PER_OP),
            "per_op_axis_note": "the '120 Mops/sec' headline implies an amortized 25/3 ~ 8.333 ns per operation and 625/3 ~ 208.33 B per operation at the peak rate; the sweep ladder brackets the latter between its 128 B and 256 B members",
            "no_latency_number": "GF-08 stages NO abstract-level latency number (the paper's latency us tables were not extracted at staging) — L stays at the A-L0X-LAT registry point 200 throughout the stage (A11/GF-07 precedent)",
            "no_size_regime": "GF-08 stages NO message-size regime — the payload grid is a DECLARED free probe (the 8*2^k ladder, 8 B -> 16 MiB; contains every in-range member of the standard 12-size ladder of stages A1/A2/A7/A9/A11/GF-05)",
            "no_rank_count": "GF-08 stages NO rank count — r=8 is the free smoke default; no scale sweep is executed (executing an un-staged scale would invent an axis the anchor does not speak to)",
        },
    }


def envelope_factor_table() -> dict:
    # Self-checks: every executed displacement times its factor equals the
    # carrier exactly.
    assert B_ROCE_CONG * F_CONGESTION == B_FALCON
    assert B_ROCE_CONG_ALT * F_CONGESTION == B_ALT
    assert B_ALT * 2 == B_FALCON  # the direction-reading ambiguity is exactly x2
    rows = [
        {
            "topology_id": "crossbar8_gf08_falcon25_l200_v1",
            "kind": "carrier",
            "quote": "peak performance of 200 Gbps",
            "B_executed": str(B_FALCON),
            "asymptotic_cct_ratio_vs_carrier_exact": "1",
        },
        {
            "topology_id": "crossbar8_gf08_alt12_5_l200_v1",
            "kind": "direction-reading",
            "quote": "the same 200 Gbps read as a bidirectional aggregate",
            "B_executed": str(B_ALT),
            "factor_exact": str(Fraction(2)),
            "asymptotic_cct_ratio_vs_carrier_exact": "2",
            "note": "NOT a congestion factor: the reading-ambiguity displacement — the direction convention alone moves the row by exactly x2, MORE than the anchor's own lossy factor 33/20",
        },
        {
            "topology_id": "crossbar8_gf08_reg64_l200_v1",
            "kind": "registry-placement",
            "quote": "(no GF-08 provenance)",
            "B_executed": str(B_REGISTRY),
            "asymptotic_cct_ratio_vs_carrier_exact": str(B_FALCON / B_REGISTRY),
            "note": "the registry default predicts bandwidth-bound CCTs 64/25 = 2.56x FASTER than the anchor rate; the ratio vs the carrier falls monotonically toward 25/64 (< 1) from 1",
        },
        {
            "topology_id": "crossbar8_gf08_roce8x3_125_l200_v1",
            "kind": "displacement",
            "quote": "operation completion times 8x lower than CX-7 RoCE under network congestion",
            "B_executed": str(B_ROCE_CONG),
            "factor_exact": str(F_CONGESTION),
            "asymptotic_cct_ratio_vs_carrier_exact": str(F_CONGESTION),
        },
    ]
    return {
        "carrier_point": f"B_ref = {B_FALCON} B/ns = Falcon's staged peak (declared per-endpoint reading; the anchor's OWN rate — no declared-carrier choice needed, unlike GF-07)",
        "mapping_technique": "the A11/GF-05/GF-07 effective-bandwidth displacement technique: each dimensionless factor enters the AllReduce identity's B axis as carrier/factor; the anchor's metrics are endpoint-transport quantities (operation completion times, goodput — RDMA/NVMe-class ops), not collective CCTs, so the transfer onto the AllReduce axis is a DECLARED dimensionless proxy",
        "rows": rows,
        "recorded_not_executed": {
            str(B_ROCE_LOSSY): "'up to 65% higher goodput under lossy conditions' — factor 33/20 exactly; 25/(33/20) = 500/33 ~ 15.15 is non-representable as a finite decimal",
            str(B_ROCE_LOSSY_ALT): "the same factor at the alternative carrier (12.5/(33/20) = 250/33)",
        },
        "executed_rows_provenance": {str(b): role for _tid, b, role in ENV_ROWS},
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
    assert checked == len(ENV_ROWS) * len(LADDER) == 88
    # Displacement signature: rows SLOWER than the carrier (12.5, 3.125)
    # have CCT ratios vs the carrier rising strictly monotonically with
    # payload toward the exact asymptote B_carrier/B_row; the FASTER
    # registry row (64) falls strictly monotonically toward 25/64 from 1.
    carrier_tid = "crossbar8_gf08_falcon25_l200_v1"
    signature = {}
    for tid in b_by_tid:
        asymptote = B_FALCON / b_by_tid[tid]
        prev = None
        for m in LADDER:
            ratio = by[(tid, m)] / by[(carrier_tid, m)]
            if tid == carrier_tid:
                # the carrier row's ratio is EXACTLY 1 at every size.
                assert ratio == 1, (tid, m)
                prev = ratio
                continue
            if prev is not None:
                if asymptote > 1:
                    assert ratio > prev, (tid, m)
                    assert ratio < asymptote, (tid, m)
                else:
                    assert ratio < prev, (tid, m)
                    assert ratio > asymptote, (tid, m)
            else:
                if asymptote > 1:
                    assert ratio < asymptote, (tid, m)
                else:
                    assert ratio > asymptote, (tid, m)
            prev = ratio
        signature[tid] = {
            "asymptotic_ratio_exact": str(asymptote),
            "ratio_at_16mib_exact": str(prev),
            "ratio_at_16mib_float": float(prev),
            "ratio_at_16kib_exact": str(by[(tid, 16384)] / by[(carrier_tid, 16384)]),
            "ratio_at_8b_exact": str(by[(tid, 8)] / by[(carrier_tid, 8)]),
        }
    # Wire-conservation audit: per-rank wire = 2(r-1)/r*M = 7M/4 on r=8.
    wire_ok = all(
        row["per_rank_wire_bytes_exact"] == str(Fraction(7 * row["payload_bytes"], 4))
        for row in table["configs"]
    )
    assert wire_ok
    return {
        "claim": "the anchor's endpoint rate and measured factors map onto the L0 B axis as exact-fraction rows; the executed rows reproduce the ordering and the A11/GF-05/GF-07 displacement signature (slower rows rise strictly monotonically toward their exact asymptotes; the faster registry row falls strictly toward 25/64) on all 88 rows, cross-checked against the closed form by exact Fraction string equality",
        "rows_cross_checked": checked,
        "closed_form": "t = 2(r-1)/r*M/B + 2L = 7/4*M/B + 400 at r=8, L=200 (registry)",
        "signature_by_row": signature,
        "row_at_anchor_implied_op_neighborhood": {
            "note": "the anchor's implied per-op size 625/3 ~ 208.33 B is bracketed by the ladder's 128 B and 256 B members; those rows' carrier-relative ratios are listed (the latency floor dominates this neighborhood)",
            "ratio_at_128b_roce8x_exact": str(by[("crossbar8_gf08_roce8x3_125_l200_v1", 128)] / by[(carrier_tid, 128)]),
            "ratio_at_256b_roce8x_exact": str(by[("crossbar8_gf08_roce8x3_125_l200_v1", 256)] / by[(carrier_tid, 256)]),
        },
        "monotonicity_note": "every slower-than-carrier row's ratio is strictly increasing over the ladder and strictly below its exact asymptote at every size; the registry row's ratio is strictly decreasing and strictly above 25/64 — at finite size an observed displacement is ALWAYS below its bandwidth-bound limit on the slow side, and above it on the fast side",
    }


def carrier_transfer(sweep_id: str) -> dict:
    by, _table = _by_cell(sweep_id)
    b_by_tid = {tid: b for tid, b, _role in CARRIER_ROWS}
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, b_by_tid[tid], R_SMOKE)), (tid, m)
        checked += 1
    assert checked == len(CARRIER_ROWS) * len(LADDER) == 88
    # The transfer property (GF-07's executed finding, replicated on the
    # GF-08 factor): ratio(x) = (x*f+2L)/(x+2L) with x = c_rank*M/B_ref is
    # strictly increasing in x, hence at every finite size the SAME factor
    # reads CLOSER to f at the SLOWER carrier (12.5) than at the faster
    # one (25); equality only in the bandwidth-bound limit.
    per_size = {}
    for m in LADDER:
        r25 = by[("crossbar8_gf08_roce8x3_125_l200_v1", m)] / by[("crossbar8_gf08_falcon25_l200_v1", m)]
        r125 = by[("crossbar8_gf08_roce8xalt1_5625_l200_v1", m)] / by[("crossbar8_gf08_alt12_5_l200_v1", m)]
        assert r125 > r25, m
        assert r25 < F_CONGESTION and r125 < F_CONGESTION
        per_size[m] = {
            "ratio_at_primary_carrier_exact": str(r25),
            "ratio_at_primary_carrier_float": float(r25),
            "ratio_at_alt_carrier_exact": str(r125),
            "ratio_at_alt_carrier_float": float(r125),
        }
    # Exact headline self-checks (transcription guards).
    assert by[("crossbar8_gf08_roce8x3_125_l200_v1", 8192)] / by[("crossbar8_gf08_falcon25_l200_v1", 8192)] == Fraction(7793, 1521)
    assert by[("crossbar8_gf08_roce8xalt1_5625_l200_v1", 8192)] / by[("crossbar8_gf08_alt12_5_l200_v1", 8192)] == Fraction(14961, 2417)
    return {
        "claim": "the measured 8x congestion factor executed at BOTH direction readings of the anchor's 200 Gbps peak: the observed ratio depends on the carrier at every finite size, reading closer to 8 at the slower (bidirectional-aggregate) carrier — the finite-size carrier relativity of dimensionless factors (GF-07's property, replicated on the GF-08 numbers)",
        "rows_cross_checked": checked,
        "headline_mid_size_8kib": per_size[8192],
        "headline_2mib": per_size[2097152],
        "headline_16mib": per_size[16777216],
        "per_size": per_size,
        "property": "ratio_alt(M) > ratio_primary(M) strictly at every finite M (executed at all 22 sizes; closed form d/dx[(x*f+2L)/(x+2L)] = 2L(f-1)/(x+2L)^2 > 0 with x = c_rank*M/B_ref); consequence: at the 8 KiB member the same factor 8 reads as 7793/1521 ~ 5.124x at the primary reading but 14961/2417 ~ 6.189x at the bidirectional-aggregate reading — a ~21% discrepancy in the OBSERVED displacement from the direction convention alone, ON TOP of the x2 row displacement itself",
        "asymptote": str(F_CONGESTION),
    }


def per_op_rate_axis() -> dict:
    assert PER_OP_FLOOR_RATIO == 48
    assert L_IMPLIED_BY_RATE == Fraction(25, 6) < 10
    assert (2 * 10) / T_PER_OP_NS == Fraction(12, 5)
    return {
        "role": "the axis this anchor uniquely contributes: a MEASURED hardware operation-rate endpoint ('120 Mops/sec'), placed against the L0 identity's structural per-op latency floor by exact arithmetic (no L0 rate observable exists — nothing to sweep; the facts are identity arithmetic)",
        "amortized_per_op_time_ns_exact": str(T_PER_OP_NS),
        "implied_per_op_bytes_exact": str(BYTES_PER_OP),
        "identity_floor_ns": "2L = 400 at the registry L=200",
        "floor_ratio_exact": str(PER_OP_FLOOR_RATIO),
        "floor_ratio_statement": "the identity's empty-payload per-op floor 2L is EXACTLY 48x the anchor's amortized per-op time (400 = 48 x 25/3) — an analytical AllReduce identity with a per-op latency term cannot express sub-latency amortized operation rates AT ALL",
        "implied_L_exact": str(L_IMPLIED_BY_RATE),
        "implied_L_statement": "matching the floor to the anchor's per-op time requires L = 25/6 ~ 4.17 ns, BELOW the A-L0X-LAT declared free-range lower bound 10 — recorded, the registry range is untouched (and even at L=10 the floor 20 ns remains 12/5 = 2.4x the anchor per-op time)",
        "ladder_bracket": "the implied per-op size 625/3 ~ 208.33 B is bracketed by the sweep ladder's 128 B and 256 B members",
    }


def confounder_separation() -> dict:
    return {
        "role": "the R1 classification the stage was assigned: order the axes by magnitude at the anchor, from the anchor's own numbers and the executed identities",
        "ordered_by_magnitude": {
            "1_identity_per_op_floor_vs_anchor_rate": "exactly 48 (identity arithmetic) — the structural per-op latency floor dwarfs every other axis when the anchor's operation-RATE (not CCT) headline is the target",
            "2_measured_congestion_delta": "8 ('8x lower than CX-7 RoCE under network congestion') — the anchor's headline hardware envelope edge",
            "3_registry_placement": "exactly 64/25 = 2.56 (the model at registry defaults vs at the anchor's own rate, bandwidth-bound asymptote; observed 2417/1325 ~ 1.824 at the 16 KiB run-pair payload)",
            "4_direction_reading_ambiguity": "exactly x2 (25 vs 12.5 B/ns) — LARGER than the anchor's own lossy factor: an UNPINNED direction convention moves the row more than the second-largest measured effect",
            "5_measured_lossy_delta": "33/20 = 1.65 ('up to 65% higher goodput under lossy conditions')",
        },
        "dominance_over_noise_floors": "the SMALLEST anchor factor 33/20 (+65%) sits ~8-13x above the anchor set's noise floors (CAL-A4 ~5% validated band, CAL-A6 5-8% software swing) — every member of this anchor's envelope is far outside the noise floors, unlike GF-07 whose managed floor 20/19 grazed them",
        "conclusion": "any future UEC-proxy backend comparison against R1 hardware must pin (a) the direction convention (x2), (b) the congestion state (the 8x quote is explicitly 'under network congestion'), and (c) the loss state (the 65% quote is explicitly 'under lossy conditions') before ANY residual is attributable to a calibratable axis — the three pinned states differ by up to 8x among themselves; the per-op floor fact additionally bounds what a latency-term analytical identity can say about Mops-rate operation endpoints (nothing, at any in-range L)",
    }


def expressiveness_classification() -> dict:
    return {
        "CAN_express": {
            "rate_placement": "the staged endpoint peak on the B axis under BOTH direction readings (25, 12.5 — the anchor's OWN absolute rate, so no declared-carrier choice is needed; the reading ambiguity is itself quantified at exactly x2 and executed)",
            "factor_magnitudes": "the measured dimensionless factors as exact-fraction displacements — 8 EXECUTED at both carriers (3.125, 1.5625), 33/20 recorded (displacements 500/33, 250/33 non-representable)",
            "carrier_relativity": "the finite-size carrier dependence of an observed factor, executed at 22 sizes with the anchor's own factor at its own two readings",
            "per_op_rate_axis": "the operation-rate headline as exact identity arithmetic (25/3 ns, 625/3 B, floor ratio exactly 48, implied L = 25/6)",
            "registry_placement": "the A-L0X-BW point 64 against the anchor rate (asymptote exactly 64/25 = 2.56; the observed ratio at the run-pair payload 2417/1325)",
        },
        "CANNOT_express": {
            "the_transport_itself": "delay-based HW congestion control, multipath packet spraying, selective retransmission, PFC-free lossy-operation semantics — no input keys; 'congestion' is in explicitly_unsupported; the anchor's SUBJECT is the axis the model family declares out of scope (the same structural verdict as GF-05, now on the hardware side)",
            "multi_ulp_endpoint_ops": "RDMA/NVMe-class operation semantics — the workload space has W1/W2 collectives only; no op-class key exists",
            "operation_rate_observables": "no rate-based observable exists; the per-op latency floor 2L makes sub-latency amortized rates structurally inexpressible (exactly 48x at the registry L)",
            "endpoint_class": "a NIC/DPU/endpoint transport on scale-out Ethernet — no landed topology_class; the crossbar rows are non-blocking ceiling abstractions, never predictions of Falcon",
            "message_and_latency_tables": "the paper's latency us values and message-rate curves were NOT extracted at staging (ACM 403) — nothing to place on the latency axis (L stays at the registry 200)",
            "the_cx7_roce_baseline_as_hardware": "CX-7 RoCE exists here only as the displacement row (3.125/1.5625), never as a modeled endpoint",
        },
        "consequence_for_calibration": "GF-08 can never calibrate L0-family O-CCT directly: it stages NO (size -> time) series, and its subject is an endpoint transport, not a collective. Its staged calibrated use — (a) the R1 HARDWARE BOOKEND rate (the first staged UEC-class hardware transport endpoint, landing INSIDE the plan §2.1 anchored span [20, 64]), (b) the hardware congestion/loss envelope edges (8 under congestion, 33/20 under loss) any UEC-proxy backend must reproduce alongside GF-07's fabric-side band (20/19 -> 25), and (c) the per-op-rate floor bound — is an owner design decision this record stages, mirroring A11's scale-out-profile note and the GF-05/GF-07 classifications",
    }


def registry_placements() -> dict:
    executed = sorted(b for _t, b, _r in ENV_ROWS)
    return {
        "A-L0X-BW_point_64_vs_anchor_25": {
            "asymptotic_cct_ratio_exact": "64/25",
            "asymptotic_cct_ratio_float": 2.56,
            "statement": "the model at registry defaults predicts bandwidth-bound CCTs exactly 64/25 = 2.56x faster than at the anchor's own endpoint rate (placement fact, never a tuning target)",
        },
        "anchored_span_membership": {
            "note": f"the anchor rate 25 B/ns lands INSIDE the plan §2.1 A-L0-BW anchored span [20, 64], between CAL-A12's NCCL-model 20 and CAL-A7's per-direction 64 — the FIRST staged UEC-class HARDWARE endpoint rate, and (unlike GF-05's sim rate 100) it does NOT extend past the span; the executed displacements {executed} extend BELOW it (3.125 is the lowest executed B row in the calibration corpus to date, below GF-07's worst 4); recorded, the registry range is untouched",
        },
        "A-L0X-LAT_A-L0-LAT": {
            "statement": "GF-08 stages NO abstract-level latency number — the registry point 200 was kept throughout (A11/GF-07 precedent); additionally the per-op-rate axis implies L = 25/6 ~ 4.17 ns BELOW the declared free range [10, 2000] lower bound — recorded as identity arithmetic, the range untouched",
        },
        "cross_anchor_coincidences": {
            "25_bytes_per_ns": "numerically identical to GF-05's uet-htsim 4:1-oversubscription displacement value (100/4) — one executed row family per anchor, never cross-derived",
            "12_5_bytes_per_ns": "numerically identical to GF-05's 8:1-oversubscription displacement value (100/8) — same class, never cross-derived",
            "33_20": "the lossy-goodput factor 1.65 = 33/20 exactly is numerically the same fraction as GF-05's fairness '65%' quote — different quote classes (goodput vs fairness spread), coincidence recorded",
        },
    }


def recorded_ambiguities() -> dict:
    return {
        "direction_convention": {
            "ambiguity": "the abstract's '200 Gbps' peak stages NO direction split; the per-endpoint reading (25 B/ns) and the bidirectional-aggregate reading (12.5 B/ns) differ by exactly x2",
            "resolution_followed": "BOTH readings executed (primary as the envelope carrier, alternative as its own row and the carrier-transfer reference); the ambiguity itself quantified at x2 and placed ABOVE the anchor's lossy factor in the confounder ordering — the owner pins the reading at integration",
        },
        "staging_gloss_vs_exact_per_op_time": {
            "ambiguity": "the staging doc's own gloss '200 Gbps / 120 Mops/s => ~6 ns/operation amortized' is MUTUALLY INCONSISTENT with the exact arithmetic: 1/120e6 s = 25/3 ~ 8.333 ns per op (and 6 ns would imply ~168 Mops/s at the stated rate)",
            "resolution_followed": "the EXACT fraction 25/3 used everywhere; the ~6 ns gloss recorded side by side, never conflated (GF-07's 0.08-vs-12x precedent); the implied per-op size 625/3 B follows from the exact reading only",
        },
        "no_size_time_series": {
            "ambiguity": "the anchor's outcome numbers are abstract-level headline rates and envelope-edge factors — the full paper tables (latency us, message-rate curves) were NOT extracted at staging (ACM 403 in the staging sandbox; NetDev slides fetch failed URL validation)",
            "resolution_followed": "per the stage prompt's FAIL clause the inextractable time target is RECORDED and SKIPPED honestly — NO comparison against any anchor time is attempted anywhere; the payload grid is a DECLARED free probe (extract the tables at integration to re-open)",
        },
        "per_op_metric_class": {
            "ambiguity": "'operation completion times' and 'goodput' are endpoint-transport metrics (RDMA/NVMe-class ops), not collective CCTs; L0 supports only allreduce",
            "resolution_followed": "every factor enters the AllReduce identity's B axis as a DECLARED dimensionless displacement (A11/GF-05/GF-07 technique); the class mismatch is carried on every row",
        },
        "edges_not_means": {
            "ambiguity": "'peak performance', '8x lower', 'up to 65% higher' are best/worst-case EDGES (headline and worst-case quotes); no distribution statistics are staged",
            "resolution_followed": "rows are placed at the EDGE values, labeled as such; no mean/variance claim is made anywhere in the record",
        },
        "congestion_and_loss_states": {
            "ambiguity": "the 8x quote holds 'under network congestion' and the 65% quote 'under lossy conditions' — the two factors are measured under DIFFERENT (both adverse) network states; no uncongested/unlossy CCT comparison between Falcon and CX-7 is staged",
            "resolution_followed": "the two factors are kept as SEPARATE envelope edges, never composed or compared to each other; their state conditions carried on every row",
        },
        "endpoint_domain": {
            "ambiguity": "Falcon is an endpoint/NIC-class transport on SCALE-OUT Ethernet — not a GPU scale-up fabric, not UEC silicon (the R1 role is architectural kinship: 'the closest shipped relative of UEC's UET design points', per the staging doc)",
            "resolution_followed": "staged under the labeled-proxy rule (CAL-A11 class) — usable as the R1 hardware bookend, never as scale-up calibration evidence; no E3/E4 language",
        },
        "confidence_class": {
            "ambiguity": "M-H confidence: headline numbers verified against the official abstract mirror only; the full paper is ACM-paywalled; the OCP/Google blog (Intel IPU E2000) is context only — no numbers staged from it",
            "resolution_followed": "numbers used AS STAGED, not re-fetched; re-verification against the full paper deferred to owner integration (the staging doc's own instruction)",
        },
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-08 (gap-fill anchor GF-08)",
        "anchor": {
            "anchor_id": "GF-08",
            "title": "Falcon (SIGCOMM 2025): a real UEC-class hardware transport, measured (R1)",
            "source_row": "gap-fill anchor — NOT yet a sources.csv row (the owner integrates accepted rows; this stage made no handoff write)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-08",
            "urls": [
                "https://dl.acm.org/doi/10.1145/3718958.3754353",
                "https://www.microsoft.com/en-us/research/publication/falcon-a-reliable-low-latency-hardware-transport",
                "https://cloud.google.com/blog/topics/systems/introducing-falcon-a-reliable-low-latency-hardware-transport",
            ],
            "confidence": "M-H (headline numbers verified against the official abstract mirror; full paper tables not extracted at staging — ACM 403; NetDev slides fetch failed). Caveat classes carried: SHIPPED HARDWARE endpoint transport on SCALE-OUT Ethernet (labeled proxy — not GPU scale-up, not UEC silicon); staged numbers are headline rates and envelope-edge factors, NOT a (size -> time) series",
            "staged_numbers": "peak 200 Gbps, 120 Mops/sec; operation completion times 8x lower than CX-7 RoCE under network congestion; up to 65% higher goodput under lossy conditions; delay-based HW CC + multipath packet spraying + selective retransmission on lossy PFC-free commodity Ethernet; multi-ULP (RDMA, NVMe); Intel IPU E2000 implementation (blog, context only)",
        },
        "target": {
            "role": "r1_uec_class_transport_hardware_bookend",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "GF-08 stages NO (size -> time) series: its staged numbers are an endpoint peak rate, an operation-rate headline, and two dimensionless envelope-edge factors measured under adverse network states. The extractable targets — the endpoint rate under both direction readings, the two factors as exact-fraction displacements, the per-op-rate axis as identity arithmetic — ARE executed here as placement and mapping, which is exactly the R1 hardware-bookend role the gap-fill doc assigns (paired with GF-05's sim-side rows)",
            "regime": {
                "topology_class": "endpoint/NIC-class transport on commodity lossy Ethernet (Intel IPU E2000) — NO landed topology_class; executed on the NON-BLOCKING single-stage abstraction (fully_connected_crossbar) as ceiling rows",
                "ranks": {
                    "executed": [R_SMOKE],
                    "provenance": "r=8 free smoke default — GF-08 stages NO rank count; no scale sweep is executed (an un-staged scale would invent an axis the anchor does not speak to; contrast GF-05's r=1,024 and GF-07's r=64, both anchor-stated)",
                },
                "message_bytes_ladder": {
                    "grid": LADDER,
                    "provenance": "DECLARED FREE PROBE — GF-08 stages no size regime; the 8*2^k ladder (8 B -> 16 MiB, 22 sizes) brackets the anchor's implied per-op size 625/3 ~ 208.33 B between its 128/256 members and contains every in-range member of the standard 12-size ladder of stages A1/A2/A7/A9/A11/GF-05; the run pair executes the A-W1-SIZE registry point 16 KiB (a ladder member)",
                },
            },
        },
        "anchor_derived": derived,
        "envelope_factor_table": envelope_factor_table(),
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (envelope rows and carrier rows at r=8; the run pair)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; envelope sweep B in {25, 12.5, 64, 3.125} at L=200; carrier sweep B in {25, 3.125, 12.5, 1.5625}",
            },
            "free_parameters": {
                "B_injection_swept_ns": "see envelope_factor_table.executed_rows_provenance — {25 Falcon peak primary reading (the carrier), 12.5 bidirectional-aggregate reading, 64 registry placement, 3.125 = 25/8 (factor 8 at the primary carrier)}; carrier sweep adds {1.5625 = 12.5/8 (factor 8 at the alternative carrier)}",
                "L_pair_swept_ns": "{200} — the A-L0X-LAT registry point throughout: GF-08 stages NO abstract-level latency number (A11/GF-07 precedent); the per-op-rate axis implies L = 25/6 below the declared range lower bound (recorded identity arithmetic, the range untouched)",
                "ranks": {"8": "free smoke default (GF-08 stages no rank count)"},
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_FALCON25,
                    "Falcon carrier point (B=25 B/ns = the staged 200 Gbps peak under the declared per-endpoint reading; L=200 ns registry — GF-08 stages no abstract-level latency; payload 16 KiB = the A-W1-SIZE registry point, a declared free probe)",
                ),
                run_summary(
                    RUN_ID_XBAR_REGISTRY,
                    "registry twin (B=64 B/ns, L=200 ns — both free registry points; the SAME payload isolates the B axis; both latency terms exactly 400 ns)",
                ),
            ],
            "run_pair_placement": {
                "cct_ratio_anchor_vs_registry_exact": "2417/1325",
                "cct_ratio_anchor_vs_registry_float": float(Fraction(2417, 1325)),
                "cct_delta_anchor_minus_registry_ns_exact": "17472/25",
                "cct_delta_anchor_minus_registry_ns_float": float(Fraction(17472, 25)),
                "statement": "at the registry's own 16 KiB payload the anchor-rate row sits at 38672/25 = 1,546.88 ns vs the registry twin's 848 ns — ratio exactly 2417/1325 (~1.824), below the pure-B asymptote 64/25 = 2.56 (the anchor row's latency fraction is 625/2417 ~ 25.9%): the model at the anchor's own endpoint rate is ~1.8x slower than at registry defaults at this size — placement arithmetic, never a tuning target",
            },
            "reconciled_sweep_envelope": sweep_rows(SWEEP_ID_ENVELOPE, "ladder"),
            "envelope_mapping": envelope_mapping(SWEEP_ID_ENVELOPE),
            "reconciled_sweep_carrier": sweep_rows(SWEEP_ID_CARRIER, "ladder"),
            "carrier_transfer": carrier_transfer(SWEEP_ID_CARRIER),
            "per_op_rate_axis": per_op_rate_axis(),
            "confounder_separation": confounder_separation(),
            "expressiveness_classification": expressiveness_classification(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — GF-08 stages no CCT-class series at all: its outcomes are an endpoint peak rate, an operation-rate headline, and dimensionless envelope-edge factors under declared adverse network states. Per the stage prompt's FAIL clause the inextractable time target is RECORDED and SKIPPED honestly — no comparison against any anchor time is attempted anywhere; the anchor's assigned role (the R1 hardware bookend) IS extractable and is executed above",
            "placement_summary": "the model's axes: the staged endpoint rate on the B axis under both direction readings (25 primary carrier, 12.5 alternative — the reading ambiguity exactly x2); the measured factors as exact-fraction displacements (8 executed at BOTH carriers with the monotone displacement signature on all 88 envelope rows; 33/20 recorded non-representable); the registry placement 64/25 = 2.56 (observed 2417/1325 at the run-pair payload); the carrier-transfer property (the same factor 8 reads 7793/1521 ~ 5.124x at the primary carrier vs 14961/2417 ~ 6.189x at the alternative at 8 KiB — a ~21% observed-displacement swing from the direction convention alone); and the per-op-rate axis (amortized 25/3 ns/op vs the identity floor 2L = 400 ns — exactly 48x; implied L = 25/6 below the declared range)",
            "span_placement": "executed B values {3.125, 12.5, 25, 64}: the anchor rate 25 lands INSIDE the plan §2.1 anchored span [20, 64] (the first UEC-class hardware endpoint rate — it does NOT extend past the span, unlike GF-05's sim 100), while the 8x congestion displacement 3.125 extends an order BELOW it (the lowest executed B row in the corpus to date); L never moved (no staged latency); recorded, registry untouched",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the R1 hardware-bookend role; no E3/E4 language — GF-08 is an external published hardware-transport study on scale-out Ethernet, not our testbed, and not GPU scale-up (labeled proxy)",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_FALCON25, RUN_ID_XBAR_REGISTRY],
            "sweep_ids": [SWEEP_ID_ENVELOPE, SWEEP_ID_CARRIER],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_ENVELOPE}",
                f"results/sweeps/{SWEEP_ID_CARRIER}",
            ],
            "run_backed_numbers": "every model output in comparison.anchor_point_runs and comparison.reconciled_sweep_*; comparison.envelope_mapping and carrier_transfer cross-check closed forms against all 176 executed sweep rows by exact Fraction string equality (declared inline; per-row wire conservation 7M/4); comparison.run_pair_placement, per_op_rate_axis, confounder_separation, expressiveness_classification, registry_placements and the recorded-not-executed displacements are identity/anchor-registry arithmetic declared inline",
            "inputs": [
                "experiments/calibration/gf08/sweep_gf08_envelope_v1.yaml",
                "experiments/calibration/gf08/sweep_gf08_carrier_v1.yaml",
                "experiments/calibration/gf08/run_gf08_falcon25_v1.yaml",
                "experiments/calibration/gf08/run_gf08_registry_v1.yaml",
                "experiments/calibration/gf08/workloads/ (1 file)",
                "experiments/calibration/gf08/topologies/ (5 files)",
                "experiments/calibration/gf08/profiles/ (1 file)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf08/run_gf08_falcon25_v1.yaml ; "
            "make run EXP=experiments/calibration/gf08/run_gf08_registry_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf08/sweep_gf08_envelope_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf08/sweep_gf08_carrier_v1.yaml ; "
            "python experiments/calibration/gf08/build_calibration_record.py",
        },
    }

    # Exact-value self-checks on the executed run pair (transcription guards).
    obs25 = load_json(RESULTS / RUN_ID_XBAR_FALCON25 / "observations.json")
    obsreg = load_json(RESULTS / RUN_ID_XBAR_REGISTRY / "observations.json")
    t25 = Fraction(obs25["per_op"][0]["completion_time_ns_exact"])
    treg = Fraction(obsreg["per_op"][0]["completion_time_ns_exact"])
    assert t25 == t_xbar(RUN_PAYLOAD, B_FALCON, R_SMOKE)
    assert treg == t_xbar(RUN_PAYLOAD, B_REGISTRY, R_SMOKE)
    assert t25 == Fraction(38672, 25) and treg == 848
    assert t25 / treg == Fraction(2417, 1325)
    assert t25 - treg == Fraction(17472, 25)
    assert 2 * L_REGISTRY / t25 == Fraction(625, 2417)

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
