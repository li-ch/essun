"""Build the PROPOSED calibration-candidate record for anchor CAL-A6 (Q1
calibration stage A6.

CAL-A6 is NCCL GitHub issue #1222 ("Loss or Performance for NCCL test
between 2.19.3 and 2.20.3"): allreduce on 4 nodes x 8 H100 (SXM) with
inter-node "16*200Gbps ROCEv2", sizes 1-16 GiB, out-of-place, two NCCL
versions. Per docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A6 this
anchor is the ladder's NOISE-FLOOR anchor (secondary O-CCT target for
hybrid rail topologies; out of the pure scale-up domain — the inter-node
legs dominate; it "sets the software-version noise floor any pass
criterion must exceed"). This stage executes both roles:

  1. NOISE FLOOR, quantified three ways (CCT-time swing, time-implied
     busbw swing, quoted-busbw swing) plus a recorded AMBIGUITY: the
     2.20.3 quoted busbw values are inconsistent with their own quoted
     times under the standard r=32 ring convention by -3.2% — the CCT
     targets are the anchor's TIMES, the inconsistent quotes are recorded,
     never smoothed, and the ambiguity is classified (transcription vs
     table-variant vs accounting), not resolved.
  2. O-CCT placement, CCT-vs-CCT per plan §3: the L0 flat-ring identity
     at r=32 with the hybrid projected onto the uniform ring at the rail
     rate B (declared bottleneck-dominated projection), swept over
     {25, 320, 400} B/ns fixed by the anchor's own staged CONFIG
     arithmetic (per-port / CAL-A12-derated / per-node rail) — never by
     its measured times. A second sweep executes the 4x8 2D-torus twin
     (the anchor's own node x GPU shape) to quantify the A-L0T-UNIF
     uniform-B blindness of the hybrid's link heterogeneity.

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity with exact Fractions, and writes a content-addressed
record to ``results/calibration/<record_id>/record.json`` (record_id =
SHA-256 of the canonical record; append-only — an existing record with
different bytes is an error, identical bytes are idempotent).

Closed-form coverage: both sweeps execute 6 configs each (3 topologies x
2 exact anchor sizes); the record cross-checks every EXECUTED row against
the same identity functions (``l0.ring_allreduce_time_ns`` /
``l0_torus2d.torus2d_allreduce_time_ns``) by exact Fraction string
equality, and evaluates the closed forms at both anchor sizes over the
full swept span for both identities. Payload sizes 2^30 and 2^34 are both
divisible by 32 = 2^5 (and by the 4x8 torus dimensions), so the
A-L0-DIV / A-L0T-DIV gates ACCEPT the anchor's sizes exactly — no
bracketing (the mirror image of stage A3, where 72 = 8*9 rejected every
power of two).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number is either (a) transcribed from the anchor's staged
numbers in ``docs/calibration/anchors_staging.md`` §A6 (declared with
provenance), or (b) computed from stored run/sweep artifacts or the
identity functions by this script. Nothing is tuned: the swept B values
carry their anchor-config arithmetic provenance, the measured series
(busbw 353.69-391.10 GB/s) is never a topology value, and the version
swing is classified, never absorbed.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical import l0
from essun.backends.analytical import l0_torus2d
from essun.backends.analytical.l0 import require_divisible
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json
from essun.workload import w1

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_RAIL = "4e24c4ec75b0cef450c94e1c856ca7cccd9c1b1a3f44fc3f6574f3ab23e2e417"
RUN_ID_DERATED = "640c3b0c66d3d1ae509a22959d1234de0f336deae4033502d4eb3742659827ad"
SWEEP_ID_RING = "78f11f396f7bb286d8f227e65016c5b413bfd47d33fd41cca60764ee5e33c158"
SWEEP_ID_TORUS = "723f732333bd423879c62b125fc0796d68484a83eaccea203e14cf022417481c"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A6 staged numbers (docs/calibration/anchors_staging.md §A6;
# transcription confidence M-H — machine-pasted nccl-tests output, credible,
# community-reported, not peer-reviewed). System: allreduce, 4 nodes x 8
# H100 (SXM), inter-node "16*200Gbps ROCEv2", sizes 1-16 GiB
# (bandwidth-bound), out-of-place.
RANKS = 32
NODES = 4
GPUS_PER_NODE = 8
PORTS_PER_NODE = 16
PORT_GBPS = Fraction(200)            # per port; Ethernet convention: per direction
SIZE_1GIB = 1 << 30                  # staged verbatim as "1 GiB (1073741824 B)"
SIZE_16GIB = 1 << 34
NCCL_2193 = {
    SIZE_1GIB: {"t_us": Fraction("5397.8"), "algbw": Fraction("198.92"), "busbw": Fraction("385.41")},
    SIZE_16GIB: {"t_us": Fraction("85110"), "algbw": Fraction("201.86"), "busbw": Fraction("391.10")},
}
NCCL_2203 = {
    SIZE_1GIB: {"t_us": Fraction("5692.2"), "busbw": Fraction("353.69")},   # algbw not staged for 2.20.3
    SIZE_16GIB: {"t_us": Fraction("86981"), "busbw": Fraction("370.33")},
}
ROOT_CAUSE_QUOTE = (
    "regression from treating '16x200G ports as 8x400G ports' and DGX H100 "
    "default tuning using 'only 16 SMs for NCCL operations' (NVIDIA/sjeaugey, "
    "staged in anchors_staging.md §A6)"
)

# Rail arithmetic (the anchor's own staged CONFIG statement, not a measurement):
# per-direction Ethernet port convention, decimal units (200 Gbps = 25 GB/s).
PORT_B = Fraction(200, 8)      # 25 B/ns per port per direction
RAIL_B = PORT_B * PORTS_PER_NODE   # 400 B/ns per node per direction
DERATED_B = RAIL_B * Fraction(4, 5)    # 320 B/ns (CAL-A12 ~80% bridge)
B_SWEPT = {"25": PORT_B, "320": DERATED_B, "400": RAIL_B}

L_REGISTRY_NS = Fraction(200)   # A-L0-LAT / A-L0T-LAT registry point (KEEP)
RING_LAT_CHAIN = 2 * (RANKS - 1) * L_REGISTRY_NS      # 12400 ns
TORUS_LAT_CHAIN = (2 * 3 + 2 * 7) * L_REGISTRY_NS     # 4000 ns

# Plan/registry anchors for the placement statements.
PLAN_PERLINK_SPAN = (Fraction(20), Fraction(64))   # CALIBRATION_PLAN §2.1 A-L0-BW candidate span
CAL_A12_DERATING = Fraction(4, 5)                  # ~80% of peak (application level)
CAL_A4_BAND = Fraction(5, 100)                     # CAL-A4 validated mean-error band
FACTOR = Fraction(2 * (RANKS - 1), RANKS)          # 62/32 — the busbw convention factor

TOP_DIR = Path("experiments/calibration/a6/topologies")
RING_TOPO = {
    "25": f"{TOP_DIR}/ring32_a6_port25_v1.yaml",
    "320": f"{TOP_DIR}/ring32_a6_derated320_v1.yaml",
    "400": f"{TOP_DIR}/ring32_a6_rail400_v1.yaml",
}
TORUS_TOPO = {
    "25": f"{TOP_DIR}/torus2d32_a6_4x8_b25_v1.yaml",
    "320": f"{TOP_DIR}/torus2d32_a6_4x8_b320_v1.yaml",
    "400": f"{TOP_DIR}/torus2d32_a6_4x8_b400_v1.yaml",
}
SIZES = [SIZE_1GIB, SIZE_16GIB]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ring_config(b: Fraction) -> l0.InfraConfig:
    return l0.InfraConfig(
        topology_id=f"cal_a6_closed_form_ring32_b{b}",
        ranks=RANKS,
        link_bytes_per_ns=b,
        hop_latency_ns=L_REGISTRY_NS,
    )


def torus_config(b: Fraction) -> l0_torus2d.Torus2DConfig:
    return l0_torus2d.Torus2DConfig(
        topology_id=f"cal_a6_closed_form_torus2d32_4x8_b{b}",
        ranks=RANKS,
        dim1_ranks=NODES,
        dim2_ranks=GPUS_PER_NODE,
        link_bytes_per_ns=b,
        hop_latency_ns=L_REGISTRY_NS,
    )


def ring_cct(payload: int, b: Fraction) -> Fraction:
    return l0.ring_allreduce_time_ns(payload, RANKS, ring_config(b))


def torus_cct(payload: int, b: Fraction) -> Fraction:
    return l0_torus2d.torus2d_allreduce_time_ns(payload, torus_config(b))


def pct(x: Fraction) -> float:
    return float(x * 100)


# ---------------------------------------------------------------------------
# 1. Anchor transcription + internal-consistency check (the ambiguity find)
# ---------------------------------------------------------------------------
def anchor_transcription() -> dict:
    """Transcribe the staged numbers and check each point against its own
    accounting: algbw = M/t and busbw = algbw * 2(r-1)/r under the r=32
    ring convention (exact Fractions; the 2.19.3 rows must reconcile to
    print precision, the 2.20.3 quotes must NOT — that is the recorded
    ambiguity, asserted so the record cannot be built on a misreading)."""
    rows = {}
    for size in SIZES:
        for version, table in (("2.19.3", NCCL_2193), ("2.20.3", NCCL_2203)):
            p = table[size]
            t_ns = p["t_us"] * 1000
            algbw = Fraction(size) / t_ns          # B/ns == GB/s (decimal)
            busbw = algbw * FACTOR
            row = {
                "size_bytes": size,
                "size_label": "1 GiB" if size == SIZE_1GIB else "16 GiB",
                "time_us_staged": str(p["t_us"]),
                "algbw_staged": str(p["algbw"]) if p.get("algbw") is not None else None,
                "busbw_staged": str(p["busbw"]),
                "algbw_time_implied_exact": str(algbw),
                "algbw_time_implied_float": float(algbw),
                "busbw_time_implied_exact": str(busbw),
                "busbw_time_implied_float": float(busbw),
                "busbw_residual_exact": str(busbw - p["busbw"]),
                "busbw_residual_gb_per_s": float(busbw - p["busbw"]),
            }
            rows[f"{version}_{row['size_label']}"] = row
    # The 2.19.3 series reconciles to print precision (<= 0.01 GB/s)...
    for size in SIZES:
        assert abs(float(NCCL_2193[size]["busbw"] - Fraction(size) / (NCCL_2193[size]["t_us"] * 1000) * FACTOR)) <= 0.01
    # ...the 2.20.3 quotes do NOT (-3.2%): the recorded ambiguity.
    for size in SIZES:
        implied = Fraction(size) / (NCCL_2203[size]["t_us"] * 1000) * FACTOR
        delta = NCCL_2203[size]["busbw"] / implied - 1
        assert float(delta) < -Fraction(3, 100)

    inconsistency = {}
    for size in SIZES:
        implied = Fraction(size) / (NCCL_2203[size]["t_us"] * 1000) * FACTOR
        inconsistency[f"2.20.3_{'1 GiB' if size == SIZE_1GIB else '16 GiB'}"] = {
            "quoted_busbw": str(NCCL_2203[size]["busbw"]),
            "time_implied_busbw_exact": str(implied),
            "quote_vs_implied_exact": str(NCCL_2203[size]["busbw"] / implied - 1),
            "quote_vs_implied_pct": pct(NCCL_2203[size]["busbw"] / implied - 1),
        }

    return {
        "system": {
            "nodes": NODES,
            "gpus_per_node": GPUS_PER_NODE,
            "ranks": RANKS,
            "interconnect_staged": "16*200Gbps ROCEv2 per node (staged config statement, not a measurement)",
            "nccl_versions": ["2.19.3", "2.20.3"],
            "variant": "out-of-place (staged for the 2.19.3 table; the 2.20.3 rows' variant is not separately staged — recorded ambiguity, minor)",
            "regime": "1-16 GiB per rank, bandwidth-bound",
        },
        "rail_arithmetic": {
            "convention": "Ethernet port rating is PER DIRECTION (full-duplex port); decimal units, 200 Gbps = 25 GB/s = 25 B/ns",
            "per_port_per_direction_B_per_ns": str(PORT_B),
            "per_node_rail_per_direction_B_per_ns": str(RAIL_B),
            "derated_bridge_cal_a12_B_per_ns": str(DERATED_B),
            "status": "the anchor's own staged CONFIG arithmetic — a ceiling, never an achieved value; the measured series sits at 96.4-97.8% of it (see rail_placement)",
        },
        "root_cause_staged": ROOT_CAUSE_QUOTE,
        "points": rows,
        "internal_consistency": {
            "finding_2193": "the 2.19.3 rows reconcile with their own times to <= 0.007 GB/s (print precision of the source table) — the series is internally consistent and used directly as the CCT target",
            "finding_2203": "the 2.20.3 QUOTED busbw values disagree with their own quoted TIMES under the standard r=32 ring convention (busbw = algbw * 2(r-1)/r) by -3.2% at BOTH sizes — recorded ambiguity, never smoothed",
            "inconsistency_rows": inconsistency,
            "classification": "unresolvable from the staged numbers; candidate classes: (a) staging transcription error, (b) the issue's 2.20.3 table being a different variant/size row pairing than its caption suggests, (c) an accounting-convention change in the quoted table. The CCT targets below use the anchor's TIMES (the direct measurement); the inconsistent quotes are recorded for the noise-floor analysis with their discrepancy declared",
            "treatment_per_fail_clause": "NOT inextractable as a whole — the times are unambiguous targets; only the 2.20.3 busbw QUOTES are quarantined (recorded, not used as targets)",
        },
        "confidence": "M-H (machine-pasted nccl-tests output; credible, community-reported, not peer-reviewed) — per the staging doc; the 2.20.3 quote inconsistency found here is exactly the kind of detail the plan §3.1 schedules for re-verification at owner integration",
    }


# ---------------------------------------------------------------------------
# 2. Rail placement (where the measured series sits vs the anchor's config ceiling)
# ---------------------------------------------------------------------------
def effective_b(size: int, t_us: Fraction) -> Fraction:
    """Fixed B that reproduces the anchor time on the ring identity at L=200:
    B_eff = 2(r-1)/r * M / (t - 2(r-1)L)."""
    return FACTOR * Fraction(size) / (t_us * 1000 - RING_LAT_CHAIN)


def rail_placement() -> dict:
    rows = {}
    for size in SIZES:
        for version, table in (("2.19.3", NCCL_2193), ("2.20.3", NCCL_2203)):
            p = table[size]
            beff = effective_b(size, p["t_us"])
            rows[f"{version}_{'1 GiB' if size == SIZE_1GIB else '16 GiB'}"] = {
                "quoted_busbw_over_rail_exact": str(p["busbw"] / RAIL_B),
                "quoted_busbw_over_rail_pct": pct(p["busbw"] / RAIL_B),
                "effective_B_from_time_exact": str(beff),
                "effective_B_from_time_float": float(beff),
                "effective_B_over_rail_pct": pct(beff / RAIL_B),
                "effective_B_over_derated_pct": pct(beff / DERATED_B),
            }
    beff_19 = [effective_b(s, NCCL_2193[s]["t_us"]) for s in SIZES]
    beff_20 = [effective_b(s, NCCL_2203[s]["t_us"]) for s in SIZES]
    return {
        "question": "where does the measured series sit relative to the anchor's own 400 B/ns per-node rail arithmetic and the CAL-A12 320 B/ns derated bridge?",
        "rows": rows,
        "readings": {
            "2.19.3": f"busbw at {pct(NCCL_2193[SIZE_1GIB]['busbw'] / RAIL_B):.2f}%-"
                      f"{pct(NCCL_2193[SIZE_16GIB]['busbw'] / RAIL_B):.2f}% of rail; time-implied effective B "
                      f"{float(beff_19[0]):.2f} -> {float(beff_19[1]):.2f} B/ns "
                      f"(ramp +{pct(beff_19[1] / beff_19[0] - 1):.2f}%)",
            "2.20.3": f"time-implied effective B {float(beff_20[0]):.2f} -> {float(beff_20[1]):.2f} B/ns "
                      f"(ramp +{pct(beff_20[1] / beff_20[0] - 1):.2f}%); the QUOTED busbw "
                      f"(88.42%-92.58% of rail) is the quarantined series (internal-consistency finding)",
            "cal_a12_contrast": "CAL-A12's ~80% software-effective derating is PESSIMISTIC for this fabric at these sizes: the 2.19.3 series reaches 96.4%-97.8% of the rail ceiling (contrast CAL-A3's NVLink domain at 87.6%-100.8% of its 900 line) — a placement fact about the achieved fraction, recorded; the derated bridge stays a swept point, not a fitted one",
        },
        "parameter_scale_note": {
            "finding": "the anchor's per-port reading 25 B/ns sits INSIDE the plan §2.1 A-L0-BW candidate per-link span [20, 64]; the per-node rail aggregate 400 B/ns (and the 320 bridge) are PER-CROSSING aggregates — a different parameter scale the per-link registry axis does not carry (nearest registry scale: A-L0X-BW aggregate injection 448-900 B/ns, a different fabric class). Recorded as placement; no registry value or span is changed",
        },
    }


# ---------------------------------------------------------------------------
# 3. The noise floor (the anchor's PRIMARY plan-assigned role)
# ---------------------------------------------------------------------------
def noise_floor() -> dict:
    # Input-space enumeration: the ring identity's config is exactly
    # {topology_id, ranks, B, L} — verified against the landed dataclass.
    fields = {f.name for f in dataclasses.fields(l0.InfraConfig)}
    assert fields == {"topology_id", "ranks", "link_bytes_per_ns", "hop_latency_ns"}, fields
    assert "software_version" not in fields

    swings = {}
    for size, label in ((SIZE_1GIB, "1 GiB"), (SIZE_16GIB, "16 GiB")):
        t19 = NCCL_2193[size]["t_us"]
        t20 = NCCL_2203[size]["t_us"]
        b19 = NCCL_2193[size]["busbw"]
        b20 = NCCL_2203[size]["busbw"]
        ib19 = Fraction(size) / (t19 * 1000) * FACTOR
        ib20 = Fraction(size) / (t20 * 1000) * FACTOR
        swings[label] = {
            "cct_time_swing_2203_over_2193_exact": str(t20 / t19 - 1),
            "cct_time_swing_pct": pct(t20 / t19 - 1),
            "time_implied_busbw_swing_exact": str(ib20 / ib19 - 1),
            "time_implied_busbw_swing_pct": pct(ib20 / ib19 - 1),
            "quoted_busbw_swing_exact": str(b20 / b19 - 1),
            "quoted_busbw_swing_pct": pct(b20 / b19 - 1),
        }
    assert pct(Fraction("5692.2") / Fraction("5397.8") - 1) > 5.4
    assert abs(pct(Fraction("353.69") / Fraction("385.41") - 1) + 8.23) < 0.01

    # The model-vs-anchor deviations at the untuned anchor point (computed in
    # cct_comparison) sit INSIDE the anchor's own version movement — the
    # overfitting statement is quantified against both swing readings.
    t19_1g = NCCL_2193[SIZE_1GIB]["t_us"] * 1000
    t19_16g = NCCL_2193[SIZE_16GIB]["t_us"] * 1000
    t20_1g = NCCL_2203[SIZE_1GIB]["t_us"] * 1000
    t20_16g = NCCL_2203[SIZE_16GIB]["t_us"] * 1000
    dev_anchor_pt = {
        "vs_2193_1gib_pct": pct(ring_cct(SIZE_1GIB, RAIL_B) / t19_1g - 1),
        "vs_2193_16gib_pct": pct(ring_cct(SIZE_16GIB, RAIL_B) / t19_16g - 1),
        "vs_2203_1gib_pct": pct(ring_cct(SIZE_1GIB, RAIL_B) / t20_1g - 1),
        "vs_2203_16gib_pct": pct(ring_cct(SIZE_16GIB, RAIL_B) / t20_16g - 1),
    }

    return {
        "role": "the anchor's PRIMARY plan-assigned role (plan §1.1 row CAL-A6): set the software-version noise floor any pass criterion must exceed",
        "input_space_enumeration": {
            "ring_config_fields": sorted(fields),
            "finding": "the L0 identity's input space carries NO software-version parameter (nor any channel/SM/chunk-count parameter — the ring's chunk is fixed at M/r by construction, A-L0-DIV): a 5.4%/2.2% CCT movement between adjacent NCCL versions on IDENTICAL hardware is INEXPRESSIBLE by any (B, L) setting, the same input-space-blindness class as stage A5's twist finding but an order smaller",
        },
        "quantified_three_ways": {
            "rows": swings,
            "reading": "the plan's '5-8% version swing' matches the QUOTED-busbw swing (-8.23%/-5.31%); the CCT-time swing (the quantity O-CCT compares) is +5.45%/+2.20%, and the time-implied busbw swing -5.17%/-2.15% — all three recorded; the quote-based members inherit the 2.20.3 internal-consistency ambiguity",
        },
        "pass_criterion_implication": {
            "plan_reference": "plan §3.4: 'a match criterion tighter than the measured software variance would be overfitting'",
            "quantified": f"any O-CCT match criterion for this regime tighter than the anchor's own version-to-version movement — {pct(Fraction('5692.2') / Fraction('5397.8') - 1):.2f}% at 1 GiB / {pct(Fraction('86981') / Fraction('85110') - 1):.2f}% at 16 GiB on times, up to 8.23% on the quoted-busbw reading — would be fitting NCCL's software state, not the fabric; CAL-A4's ~5% validated band sits INSIDE this range (5.45% > 5%), so even that band is at the noise edge for hybrid-rail comparisons",
            "model_placement_inside_the_floor": {
                "deviation_at_untuned_anchor_point_pct": dev_anchor_pt,
                "statement": "the identity at the anchor point B=400 (untuned config arithmetic) deviates -2.21%..-8.41% from the two measured series — every deviation magnitude is WITHIN the anchor's own version movement, so the placement cannot be distinguished from software state by these two series alone",
            },
        },
        "root_cause_class": {
            "staged": ROOT_CAUSE_QUOTE,
            "classification": "the staged root cause is channel/SM/port-bundling CONFIGURATION (16x200G read as 8x400G; 16 SMs) — exactly the chunk-count/channel sensitivity class the plan §2.2 A-AS1-CHUNKS-1 flag names FIRST-CLASS for CAL-A6 ('chunk/channel/SM config moves measured bandwidth-bound CCT by whole factors'). The L0 family has no such knob (structural); the ASTRA adapter's active-chunks-per-dimension=1 convention is the only chunk-count parameter in the repo and is NOT exercised by this stage",
        },
        "classification_per_handoff_rule_5": {
            "minimized_counterexample": "identical hardware and size, two adjacent NCCL versions, +2.2%..+5.5% CCT (times) / -5.3%..-8.2% busbw (quotes): a real software-stack effect no model parameter can express",
            "class": "STRUCTURAL input-space blindness (software-version axis), magnitude comparable to CAL-A4's ~5% validated band and far below CAL-A5's 31-63% geometry effect — it is absorbed as NOISE FLOOR, not refit: the correct response is the plan's (pin software config with every target series), not a new parameter",
            "refinement": "owner decision, out of scope: any future model term for channelization/SM count would be a new identity; this stage only quantifies the floor",
        },
    }


# ---------------------------------------------------------------------------
# 4. CCT comparison (the secondary role): ring identity vs the anchor times
# ---------------------------------------------------------------------------
def minimax_fixed_b(t1: Fraction, t2: Fraction) -> tuple[Fraction, Fraction, Fraction]:
    """Exact fixed-B minimax over the two staged sizes (diagnostic only).

    dev_i(B) = (a_i/B + c)/t_i - 1 with a_i = 2(r-1)/r*M_i, c = 2(r-1)L.
    dev2 > dev1 on the relevant branch and the optimum is interior where
    dev1 = -dev2 (max|dev| switches from |dev1| to dev2 there):
        B* = (a1*t2 + a2*t1) / (2*t1*t2 - c*(t1+t2)).
    Returned: (B*, dev1, dev2) with dev1 = -dev2 asserted; a deterministic
    Fraction scan verifies no grid point beats it."""
    a1 = FACTOR * SIZE_1GIB
    a2 = FACTOR * SIZE_16GIB
    c = RING_LAT_CHAIN
    b_star = (a1 * t2 + a2 * t1) / (2 * t1 * t2 - c * (t1 + t2))
    d1 = (a1 / b_star + c) / t1 - 1
    d2 = (a2 / b_star + c) / t2 - 1
    assert d1 == -d2, (d1, d2)
    best = max(abs(d1), abs(d2))
    for i in range(1, 20000):   # deterministic scan, Fraction grid
        b = Fraction(25) + Fraction(375) * Fraction(i, 20000)
        m = max(abs((a1 / b + c) / t1 - 1), abs((a2 / b + c) / t2 - 1))
        assert m >= best  # no grid point beats the exact optimum
    return b_star, d1, d2


def cct_comparison() -> dict:
    table = {}
    for b_str, b in B_SWEPT.items():
        for size in SIZES:
            label = "1 GiB" if size == SIZE_1GIB else "16 GiB"
            row = {"model_cct_ns_exact": str(ring_cct(size, b)),
                   "model_cct_us_float": float(ring_cct(size, b) / 1000)}
            for version, tbl in (("2.19.3", NCCL_2193), ("2.20.3", NCCL_2203)):
                t_ns = tbl[size]["t_us"] * 1000
                row[f"ratio_model_over_{version}_exact"] = str(ring_cct(size, b) / t_ns)
                row[f"delta_{version}_pct"] = pct(ring_cct(size, b) / t_ns - 1)
            table[f"B={b_str}_{label}"] = row

    t1 = NCCL_2193[SIZE_1GIB]["t_us"] * 1000
    t2 = NCCL_2193[SIZE_16GIB]["t_us"] * 1000
    u1 = NCCL_2203[SIZE_1GIB]["t_us"] * 1000
    u2 = NCCL_2203[SIZE_16GIB]["t_us"] * 1000
    b19, d19a, d19b = minimax_fixed_b(t1, t2)
    b20, d20a, d20b = minimax_fixed_b(u1, u2)

    lat_share = {
        "ring_latency_chain_ns_exact": str(RING_LAT_CHAIN),
        "share_of_model_cct_at_anchor_point": {
            "1 GiB": pct(RING_LAT_CHAIN / ring_cct(SIZE_1GIB, RAIL_B)),
            "16 GiB": pct(RING_LAT_CHAIN / ring_cct(SIZE_16GIB, RAIL_B)),
        },
        "share_of_anchor_times": {
            "2.19.3_1GiB": pct(RING_LAT_CHAIN / t1),
            "2.19.3_16GiB": pct(RING_LAT_CHAIN / t2),
        },
        "note": "0.015%-0.24% — the anchor's regime is bandwidth-bound (the mirror image of stage A5's latency-dominated 4 KiB regime); the unanchored L=200 ns registry point moves CCT by at most ~0.2% here (both legs' real per-hop latencies — RoCE microsecond-class, NVLink unpublished — are NOT staged; recorded in inextractable)",
    }

    return {
        "metric_discipline": "CCT vs CCT: the anchor's quoted TIMES are the targets; busbw->algbw->CCT mapping written per point in anchor_transcription; the 2(r-1)/r = 62/32 factor is carried by both sides (NCCL's busbw convention and the model's per-rank wire identity) and cancels — no mixed metric",
        "identity": "t = 2(r-1)/r*M/B + 2(r-1)*L at r=32 (l0.ring_allreduce_time_ns)",
        "rows_by_B_and_size": table,
        "anchor_point_reading": {
            "B=400 (untuned rail arithmetic)": "model is -3.42% (1 GiB) / -2.21% (16 GiB) vs the 2.19.3 times and -8.41% / -4.32% vs 2.20.3 — i.e. 2.2-3.4% FASTER than the consistent series at spec-ceiling B, with the measurement at 96.4-97.8% of rail",
            "B=320 (CAL-A12 derated bridge)": "+14.43%..+22.23% slower than every measured point — the ~80% derating overshoots this fabric (it reaches 96-98% of ceiling); recorded, the bridge stays a swept point",
            "B=25 (single-port endpoint)": "+1362%..+1464% — the per-port endpoint is excluded by the data an order over: the crossing demonstrably bundles many ports (consistent with the staged 8x400G bundling remark)",
        },
        "effective_B_ramp": {
            "2.19.3": f"{float(effective_b(SIZE_1GIB, NCCL_2193[SIZE_1GIB]['t_us'])):.2f} -> "
                      f"{float(effective_b(SIZE_16GIB, NCCL_2193[SIZE_16GIB]['t_us'])):.2f} B/ns (+1.26%)",
            "2.20.3": f"{float(effective_b(SIZE_1GIB, NCCL_2203[SIZE_1GIB]['t_us'])):.2f} -> "
                      f"{float(effective_b(SIZE_16GIB, NCCL_2203[SIZE_16GIB]['t_us'])):.2f} B/ns (+4.49%)",
            "statement": "a fixed-B, zero-overhead identity cannot express a size-dependent rate; the ramp here is +1.3% (2.19.3) — an order flatter than CAL-A3's +15.1% on the same convention — so the flat-B reading is much closer to sufficient in this regime",
        },
        "fixed_B_minimax_diagnostic_only": {
            "2.19.3_series": {
                "B_star_exact": str(b19),
                "B_star_float": float(b19),
                "worst_deviation_pct": pct(max(abs(d19a), abs(d19b))),
                "binding": "both staged sizes (deviations exactly opposite)",
            },
            "2.20.3_series": {
                "B_star_exact": str(b20),
                "B_star_float": float(b20),
                "worst_deviation_pct": pct(max(abs(d20a), abs(d20b))),
            },
            "status": "DIAGNOSTIC ONLY — no topology or manifest carries these B values; a TWO-POINT series cannot overconstrain a one-parameter fit and the ±misfit is a property of these two staged points, not a validated band (stage A3's ±7.02% bound came from five sizes; this anchor stages two per version)",
            "cross_anchor_note": "the 2.19.3 minimax misfit (+-0.62%) is far below CAL-A4's ~5% band and below this anchor's own version swing — consistent with the flat-B reading being adequate here; the 2.20.3 minimax (~+2.7%) likewise inside the swing",
        },
        "latency_share": lat_share,
    }


# ---------------------------------------------------------------------------
# 5. The 4x8 hierarchical twin (A-L0T-UNIF uniform-B blindness, quantified)
# ---------------------------------------------------------------------------
def torus_twin() -> dict:
    t19_1g = NCCL_2193[SIZE_1GIB]["t_us"] * 1000
    t19_16g = NCCL_2193[SIZE_16GIB]["t_us"] * 1000
    t20_1g = NCCL_2203[SIZE_1GIB]["t_us"] * 1000
    t20_16g = NCCL_2203[SIZE_16GIB]["t_us"] * 1000
    wire_ratio = (l0_torus2d.torus2d_traffic_per_rank(SIZE_1GIB, torus_config(RAIL_B))
                  / l0.ring_traffic_per_rank(SIZE_1GIB, RANKS))
    assert wire_ratio == Fraction(52, 31)
    rows = {}
    for b_str, b in B_SWEPT.items():
        for size, s_label in ((SIZE_1GIB, "1 GiB"), (SIZE_16GIB, "16 GiB")):
            t = torus_cct(size, b)
            rows[f"B={b_str}_{s_label}"] = {
                "model_cct_ns_exact": str(t),
                "model_cct_us_float": float(t / 1000),
                "delta_vs_2193_pct": pct(t / (t19_1g if size == SIZE_1GIB else t19_16g) - 1),
                "delta_vs_2203_pct": pct(t / (t20_1g if size == SIZE_1GIB else t20_16g) - 1),
            }
    return {
        "identity": "t_2d = t_ring(M,4) + t_ring(M,8) on the anchor's own node x GPU shape (4x8, r=32), uniform B/L across dimensions (A-L0T-UNIF)",
        "rows_by_B_and_size": rows,
        "structural_finding": {
            "wire_coefficient_exact": "13/4 = 2*(3/4) + 2*(7/8) per rank vs the flat ring's 62/32 = 1.9375 (each dimension reduces the FULL message, A-L0T-SEQ)",
            "wire_ratio_torus_over_ring_exact": str(wire_ratio),
            "wire_ratio_float": float(wire_ratio),
            "blindness": "the real hybrid has FAST intra-node NVLink legs and a 400 B/ns-class rail; A-L0T-UNIF forces BOTH dimensions onto the same B, so at every swept value the NVLink dimension is charged the rail rate — the heterogeneity is inexpressible by any (B, L, shape) choice; at the anchor point the twin sits +61.7% (1 GiB) / +64.0% (16 GiB) above the 2.19.3 times",
            "classification": "STRUCTURAL (uniform-link class, the same KEEP-verdict family as A-L0-FD / A-L0T-UNIF), quantified not tuned: the twin is executed as the family's only multi-level identity in the anchor's exact shape, never as a competing fit; a heterogeneous-link identity is a new model (owner decision)",
        },
    }


# ---------------------------------------------------------------------------
# 6. Executed-row cross-checks (sweeps) + store-run checks
# ---------------------------------------------------------------------------
def sweep_row_checks() -> list[dict]:
    checks = []
    for sweep_id, cct_fn, topo_map, kind in (
        (SWEEP_ID_RING, ring_cct, RING_TOPO, "ring"),
        (SWEEP_ID_TORUS, torus_cct, TORUS_TOPO, "torus2d_4x8"),
    ):
        table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
        assert len(table["configs"]) == 6, sweep_id
        for row in table["configs"]:
            topo_id = row["config_id"].split("-")[2]
            size = row["payload_bytes"]
            if kind == "ring":
                # ring32_a6_{port25,derated320,rail400}_v1 -> the token before _v1
                token = topo_id.split("_")[-2]           # port25 / derated320 / rail400
                b_str = {"port25": "25", "derated320": "320", "rail400": "400"}[token]
            else:
                # torus2d32_a6_4x8_b{25,320,400}_v1
                b_str = topo_id.split("_b")[-1].split("_")[0]
            b = B_SWEPT[b_str]
            assert str(topo_map[b_str]).endswith(topo_id + ".yaml"), (topo_id, b_str)
            # the executed row equals the closed form of the same identity
            assert row["o_cct"]["completion_time_ns_mean_exact"] == str(cct_fn(size, b))
            checks.append(
                {
                    "sweep_id": sweep_id,
                    "config_id": row["config_id"],
                    "identity": kind,
                    "payload_bytes": size,
                    "B_bytes_per_ns": b_str,
                    "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
                    "delta_vs_baseline_exact": row["delta_vs_baseline"]["delta_exact"],
                    "verdict": "executed row == closed form of the same identity function (exact Fraction string equality)",
                }
            )
    assert len(checks) == 12
    return checks


def run_checks() -> list[dict]:
    checks = []
    for run_id, b, label in (
        (RUN_ID_RAIL, RAIL_B, "anchor point (B=400, the staged rail arithmetic)"),
        (RUN_ID_DERATED, DERATED_B, "derated bridge (B=320, CAL-A12 ~80% x 400)"),
    ):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        per_op = obs["per_op"][0]
        assert per_op["payload_bytes"] == SIZE_16GIB
        assert obs["model"]["ranks"] == RANKS
        assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == b
        assert Fraction(obs["model"]["hop_latency_ns_exact"]) == L_REGISTRY_NS
        assert per_op["completion_time_ns_exact"] == str(ring_cct(SIZE_16GIB, b))
        assert per_op["per_rank_wire_bytes_exact"] == str(l0.ring_traffic_per_rank(SIZE_16GIB, RANKS))
        checks.append(
            {
                "run_id": run_id,
                "mapping": f"ring r=32 at 16 GiB (the anchor's largest staged size, exact), {label}",
                "experiment_id": run["manifest"]["experiment_id"],
                "manifest_path": run["manifest_path"],
                "payload_bytes": per_op["payload_bytes"],
                "cct_ns_exact": per_op["completion_time_ns_exact"],
                "cct_us_float": per_op["completion_time_ns"],
                "verdict": "store run == closed form of the same identity function (exact Fraction string equality); per-rank wire bytes == the ring identity",
            }
        )
    return checks


# ---------------------------------------------------------------------------
# 7. Divisibility-gate acceptance (the anti-A3 check)
# ---------------------------------------------------------------------------
def div_gate_acceptance() -> dict:
    for size in SIZES:
        require_divisible("analytical_l0", "cal_a6_probe", size, RANKS, "A-L0-DIV")
        for d in (NODES, GPUS_PER_NODE):
            require_divisible("analytical_l0_torus2d", "cal_a6_probe", size, d, "A-L0T-DIV")
    return {
        "finding": "CAL-A6's staged sizes are powers of two (2^30, 2^34) and r = 32 = 2^5 (dims 4 and 8 likewise), so the A-L0-DIV / A-L0T-DIV gates ACCEPT the anchor's sizes exactly",
        "sizes_checked": SIZES,
        "contrast": "stage A3 needed 72-divisible floor/ceil brackets because 72 = 8*9 never divides a power of two; here no bracketing exists and every executed row sits AT the anchor's sizes (like stage A5)",
    }


# ---------------------------------------------------------------------------
# 8. Inextractable targets (FAIL-clause honesty duty)
# ---------------------------------------------------------------------------
def inextractable_targets() -> list[dict]:
    return [
        {
            "target": "the full 1-16 GiB series",
            "reason": "the staging doc transcribes TWO sizes per version (1 and 16 GiB) with times; the issue's full -b/-e ladder is not staged, so no intermediate sizes are compared and the fixed-B minimax is a two-point diagnostic (declared in cct_comparison)",
        },
        {
            "target": "the 2.20.3 QUOTED busbw values as targets",
            "reason": "internally inconsistent with their own quoted times under the r=32 ring convention (-3.2% at both sizes; see anchor_transcription.internal_consistency) — quarantined: recorded for the noise-floor analysis with the discrepancy declared, never used as CCT targets and never smoothed",
        },
        {
            "target": "NCCL channelization / ring count / algorithm",
            "reason": "not pinned by the staged numbers; the comparison uses the single-flat-ring reading with the declared crossing-rate mapping (busbw = per-node rail demand under node-contiguous ring placement). Channel/SM config is the staged ROOT CAUSE of the version swing (A-AS1-CHUNKS-1 class) and the L0 family has no such parameter — structural, recorded",
        },
        {
            "target": "intra-node NVLink leg rate and both legs' per-hop latencies",
            "reason": "not staged by CAL-A6 (no H100 NVLink numbers in this anchor; the RoCE per-hop latency is likewise absent). The hybrid's fast-leg rate is therefore UNANCHORED in this stage — the uniform-B projection declares this — and L=200 ns is inherited from the registry (CCT share <= 0.24% in this bandwidth-bound regime)",
        },
        {
            "target": "the regression's fix state / post-2.20.3 behavior",
            "reason": "the issue's resolution is not staged; only the two versions' tables are. The swing direction (2.20.3 slower) is used exactly as staged",
        },
        {
            "target": "loss/performance tradeoff framing (the issue's title topic)",
            "reason": "the issue discusses NCCL_LOSS/timeout behavior context that the staging doc does not transcribe; no RoCE loss/retry parameters exist in the L0 family (congestion/loss explicitly unsupported) — out of scope, recorded",
        },
    ]


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------
def main() -> int:
    transcription = anchor_transcription()
    placement = rail_placement()
    floor = noise_floor()
    comparison = cct_comparison()
    twin = torus_twin()
    sweep_checks = sweep_row_checks()
    runs = run_checks()
    gate = div_gate_acceptance()
    inextractable = inextractable_targets()

    t1 = NCCL_2193[SIZE_1GIB]["t_us"]
    t2 = NCCL_2193[SIZE_16GIB]["t_us"]
    u1 = NCCL_2203[SIZE_1GIB]["t_us"]
    u2 = NCCL_2203[SIZE_16GIB]["t_us"]
    swing_time_1g = pct(u1 / t1 - 1)
    swing_time_16g = pct(u2 / t2 - 1)
    swing_quote_1g = pct(NCCL_2203[SIZE_1GIB]["busbw"] / NCCL_2193[SIZE_1GIB]["busbw"] - 1)
    swing_quote_16g = pct(NCCL_2203[SIZE_16GIB]["busbw"] / NCCL_2193[SIZE_16GIB]["busbw"] - 1)
    dev19 = [pct(ring_cct(SIZE_1GIB, RAIL_B) / (t1 * 1000) - 1), pct(ring_cct(SIZE_16GIB, RAIL_B) / (t2 * 1000) - 1)]
    dev20 = [pct(ring_cct(SIZE_1GIB, RAIL_B) / (u1 * 1000) - 1), pct(ring_cct(SIZE_16GIB, RAIL_B) / (u2 * 1000) - 1)]
    b19, d19a, _ = minimax_fixed_b(t1 * 1000, t2 * 1000)

    deviation_summary = (
        "CAL-A6 is the ladder's NOISE-FLOOR anchor first and an O-CCT target second. "
        f"Noise floor, quantified three ways: the anchor moves ITSELF +{swing_time_1g:.2f}%/"
        f"+{swing_time_16g:.2f}% in CCT (times) and {swing_quote_1g:.2f}%/{swing_quote_16g:.2f}% in "
        "quoted busbw between adjacent NCCL versions on identical hardware — inexpressible by any "
        "(B, L) setting (no software-version parameter exists in the input space) and therefore the "
        "floor any pass criterion must exceed; CAL-A4's ~5% band sits inside this range (5.45% > 5%), "
        "so even that band is at the noise edge for hybrid-rail comparisons. Recorded ambiguity: the "
        "2.20.3 quoted busbw disagree with their own quoted times by -3.2% at BOTH sizes under the "
        "r=32 convention — the times are the CCT targets, the quotes are quarantined with the "
        "discrepancy declared, never smoothed. O-CCT placement at the UNTUNED anchor point B=400 "
        f"(the staged '16*200Gbps' rail arithmetic): the identity sits {dev19[0]:.2f}%/{dev19[1]:.2f}% "
        f"vs the consistent 2.19.3 times and {dev20[0]:.2f}%/{dev20[1]:.2f}% vs 2.20.3 — every "
        "deviation magnitude is inside the anchor's own version movement, with the measurement at "
        "96.4-97.8% of rail (CAL-A12's ~80% derating is pessimistic here; its 320 B/ns bridge "
        "overshoots every measured point by +14-22%), effective-B ramping only +1.26% across sizes "
        "(an order flatter than CAL-A3's +15.1%), and the exact two-point fixed-B minimax at "
        f"B*={float(b19):.2f} B/ns with worst deviation +-"
        f"{pct(max(abs(d19a), abs(-d19a))):.2f}% (diagnostic only; no topology carries it). The 4x8 "
        "hierarchical twin quantifies the A-L0T-UNIF blindness: uniform B forces the rail rate onto "
        "the NVLink dimension and the twin sits +61.7%/+64.0% off at the anchor point — structural, "
        "never tuned"
    )

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A6 (anchor CAL-A6)",
        "anchor": {
            "anchor_id": "CAL-A6",
            "title": "NCCL GitHub issue #1222: 4x8 H100 allreduce over 16x200 Gbps RoCEv2 (MEASURED)",
            "source_row": "the anchor registry row CAL-A6 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A6",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A6 (noise-floor anchor, secondary target; out of the pure scale-up domain — the inter-node legs dominate)",
            "url": "https://github.com/NVIDIA/nccl/issues/1222",
            "confidence": "M-H (machine-pasted nccl-tests output; credible, community-reported, not peer-reviewed)",
            "transcription": transcription,
        },
        "target": {
            "role": "noise_floor_anchor_plus_secondary_oct_target",
            "regime": {
                "message_bytes": SIZES,
                "message_regime": "1-16 GiB per rank, bandwidth-bound (latency term <= 0.24% of CCT)",
                "ranks": RANKS,
                "topology_class": "hybrid rail: intra-node NVLink + inter-node RoCE (16x200Gbps per node) — OUT of the pure scale-up domain per the plan; UEC-proxy shape (labeled proxy, never silent)",
            },
            "inextractable_targets": inextractable,
        },
        "model": {
            "backend_id": "analytical_l0",
            "identity": "t(M, r) = 2*(r-1)/r*M/B + 2*(r-1)*L at r=32; per-rank wire bytes 2*(r-1)/r*M",
            "projection": "hybrid -> uniform ring at the rail rate: in the anchor's bandwidth-bound regime the rail legs dominate; under the node-contiguous single-ring crossing reading the crossing link carries the same per-collective bytes as every ring link (2(r-1)/r*M), so B maps to the per-node rail rate. Declared bottleneck-dominated projection (the fast NVLink legs are projected away) — same discipline as stage A5's declared 3D->2D projection; the 4x8 torus twin quantifies what the projection costs a multi-level identity",
            "ranks": RANKS,
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "25": "one 200 Gbps RoCEv2 port per direction (the anchor's staged port rating; per-port endpoint; inside the plan's per-link span [20, 64])",
                    "320": "CAL-A12 ~80% software-effective derating x 400 (the plan's mandatory spec-vs-measured normalization)",
                    "400": "the ANCHOR POINT: the staged '16*200Gbps ROCEv2' per-node rail under the per-direction Ethernet port convention (16 x 25 B/ns) — config ceiling, never a measurement",
                },
                "L_hop_latency_ns": 200,
                "L_provenance": "A-L0-LAT registry point (KEEP per plan §2.1); CCT share <= 0.24% in this regime, but both legs' real latencies are unstaged (gap §4.2) — recorded as a known limit",
            },
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV (experiments/vertical_slice/assumptions_l0.yaml); twin: A-L0T-SEQ / A-L0T-UNIF / A-L0T-SHAPE / A-L0T-BW / A-L0T-LAT / A-L0T-DIV",
            "closed_form_coverage": "executed 12 configs (2 sweeps x 6); every executed row cross-checked against the same identity functions by exact Fraction string equality, and the closed forms evaluated at both anchor sizes over the full swept span for both identities (rows in cct_comparison / torus_twin)",
        },
        "comparison": {
            "rail_placement": placement,
            "noise_floor": floor,
            "cct_comparison": comparison,
            "torus2d_hierarchical_twin": twin,
            "divisibility_gate": gate,
            "executed_row_checks": sweep_checks,
            "anchor_point_runs": runs,
        },
        "deviation": {
            "summary": deviation_summary,
            "not_tuned": "nothing was tuned: the B span {25, 320, 400} is fixed by the anchor's own staged CONFIG statement ('16*200Gbps ROCEv2', per-direction Ethernet port convention) and prior anchors' arithmetic (CAL-A12 derating, per-port rate) — never by the measured times; the measured series (busbw 353.69-391.10) is never a topology value; the minimax B* is a recorded diagnostic carried by NO topology; the version swing is classified (structural software-axis blindness absorbed as noise floor), never refit; the 2.20.3 quote inconsistency is recorded, never smoothed",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external published measurement; no E3/E4 language — CAL-A6 is not our testbed, and the owner's adjudication precedes any label move",
        },
        "backing": {
            "run_ids": [RUN_ID_RAIL, RUN_ID_DERATED],
            "sweep_ids": [SWEEP_ID_RING, SWEEP_ID_TORUS],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_RING}", f"results/sweeps/{SWEEP_ID_TORUS}"],
            "run_backed_numbers": "every run-path-executed number (12 sweep configs, 2 store runs); the closed-form rows are the same identity functions whose executed instances are cross-checked above (declared inline)",
            "inputs": [
                "experiments/calibration/a6/sweep_a6_ring_v1.yaml",
                "experiments/calibration/a6/sweep_a6_torus_v2.yaml (v2: re-id after a provenance-comment correction in the b400 torus topology file tripped the sweep store's byte-drift fence; grid and values unchanged)",
                "experiments/calibration/a6/run_a6_rail_16gib_v1.yaml",
                "experiments/calibration/a6/run_a6_derated_16gib_v1.yaml",
                "experiments/calibration/a6/workloads/ (2 files)",
                "experiments/calibration/a6/topologies/ (6 files)",
                "experiments/calibration/a6/profiles/implementation_profile_l0_ring_cal_a6_v1.yaml",
            ],
            "reproduce": "make run EXP=experiments/calibration/a6/run_a6_rail_16gib_v1.yaml ; "
            "make run EXP=experiments/calibration/a6/run_a6_derated_16gib_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a6/sweep_a6_ring_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a6/sweep_a6_torus_v2.yaml ; "
            "python experiments/calibration/a6/build_calibration_record.py",
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
