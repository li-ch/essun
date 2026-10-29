"""Build the PROPOSED calibration-candidate record for anchor CAL-A10 (Q1
calibration stage A10.

CAL-A10 is "Communication-Centric UALink and NVLink Comparison for Large
Scale AI Training" (IEEE/ACM HiPC 2025 Workshops, IEEE CSDL 453800a068) —
an ANALYTICAL model comparison whose staged numbers are: the explicit
NVLink-side latency ASSUMPTION "NVIDIA does not publish end-to-end latency
for NVLink Network; we assume 0.8 us, consistent with 'sub-us' positioning
for NVSwitch hops" (quote via public search snippet; full text paywalled),
plus two QUALITATIVE outputs (a flat UALink pod reduces the step-time
contribution of small-message collectives at scales up to 1024 GPUs;
NVLink 5 keeps an advantage in bandwidth-bound scenarios). Per
docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A10 this anchor CANNOT
calibrate O-CCT ("a stated assumption, not a measurement"); its
plan-assigned roles are the SANITY BAND for GPU-fabric hop/pair latency —
the 800 ns figure IS the plan §2.1 anchored-span upper endpoint (~10-800
ns) and the A-L0X-LAT pair-latency span upper — while "UALink-side
parameters remain model-only until silicon". This stage executes those
roles: LATENCY-AXIS PLACEMENT of the assumption value, plus the anchor's
own regime contribution — the SCALE claim ("to 1024 GPUs") — as a swept
rank ladder {8,...,1024} over the three single-port L0 identities (ring
2(r-1)L linear, recursive doubling 2*log2(r)*L logarithmic, crossbar 2L
constant; identical wire bytes and bandwidth term in all three), at the
assumption point L=800 ns, B=64 B/ns registry point, M=16384 B registry
smoke point.

ASSUMPTION-CLASS HONESTY (the stage's core classification duty): the
0.8 us figure is a STATED ASSUMPTION in a peer-reviewed usage — peer
review certifies the plausibility of the USAGE, never the value; it is
NOT a measurement, and the quote's own premise (NVIDIA publishes no such
number) means no L value can be falsified against it. Transcription
confidence is M per the staging doc (search-snippet quote, paywalled
parameter table; wording re-verification at owner integration is an open
item recorded here). The anchor's outputs are qualitative direction
statements; the record quantifies the model-side structural facts they
can be checked against and classifies what the L0 input space cannot
express — never tuning, never smoothing.

Pure function of immutable artifacts: reads the two append-only store run
records and the eight sweep tables produced by this stage, recomputes
every derived quantity with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

Run-backed cross-checks enforced here (a mismatch is a bug, not a finding):

1. all 24 executed sweep rows (8 ranks x 3 identities) equal the closed
   forms of the run path's own identity functions
   (``l0.ring_allreduce_time_ns``, ``l0_crossbar.crossbar_allreduce_time_ns``,
   ``l0_recursive_doubling.rd_allreduce_time_ns``) by exact Fraction
   string equality;
2. both store runs (flat/crossbar and chained/ring at the anchor's scale
   ceiling r=1024) equal the same closed forms;
3. the latency-chain laws hold EXACTLY at every rung: ring - crossbar ==
   2L(r-2), doubling - crossbar == 2L(log2(r)-1), ring - doubling ==
   2L(r-1-log2(r)), and all three identities coincide at r=2
   (closed-form-only note — r=2 is not a sweep rung);
4. the r=8 ring rung reproduces stage A8's executed L=800 row exactly
   (11648 ns) — the cross-stage determinism tie-in;
5. the three identities' bandwidth terms are IDENTICAL at every rung
   (exact Fraction equality) — the fact behind the bandwidth-bound
   expressiveness classification;
6. the divisibility gates accept M=16384 at every power-of-two rung on
   all three identities, and the POW2 gate accepts the ladder natively.

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number is either (a) transcribed from the anchor's staged
material in ``docs/calibration/anchors_staging.md`` §A10 (declared with
provenance), or (b) computed from stored run/sweep artifacts or the
identity functions by this script. Nothing is tuned.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical import l0, l0_crossbar, l0_recursive_doubling
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_FLAT = "01f0bc598ba32e28564a66e58bfb8e7fa64943091e9c5edc63ddeb1416453660"   # crossbar r=1024
RUN_ID_CHAIN = "ce4d730952ee66d604cd93615de0d5cbb3f840e38399fbc5891fc9a5ea606c67"  # ring r=1024
SWEEP_IDS = {
    8: "6c88912760e8b0b6028959b7e59e4c60bb5b95c1f95b1f846fabb47709f5de9b",
    16: "ba546c7557f4c873bd0f68cf37613477635e9dc04607f6a90ce62940ae125640",
    32: "b18550ab1c99c85d91fe8f55047a5d98228fff8a0efe8c840c128e004167346a",
    64: "0e4c2acd96bca13e287c658f0962af1e94ba4675e312864d2bb54e7bba2937dd",
    128: "fcc05f4fc0420c9eaaf21405ee4033576ab7ba0174915ddb4265f22be0b1fb42",
    256: "10e03f2a05b24120da297a37afdc341f5a93d336ebdf147590a5cc0661808b34",
    512: "48e9174b3caf0ba03e6471c0a10b0be16653454ddae1d8e08a6900bfdd68402c",
    1024: "24d4890245d357f7c3dc727746aa95d42f2dd0bdebe3fdc1accb614556450b67",
}

RESULTS = REPO_ROOT / "results"
A10 = REPO_ROOT / "experiments" / "calibration" / "a10"

# Anchor CAL-A10 staged material (docs/calibration/anchors_staging.md §A10;
# transcription confidence M — quote via public search snippet of the
# paywalled paper; exact parameter table NOT extracted; wording
# re-verification at owner integration is an OPEN item).
STAGED_QUOTE = (
    "NVIDIA does not publish end-to-end latency for NVLink Network; we "
    "assume 0.8 \u00b5s, consistent with 'sub-\u00b5s' positioning for "
    "NVSwitch hops"
)
ANCHOR_L_NS = Fraction(800)  # 0.8 us, decimal units
STAGED_SCALE_CEILING = 1024  # "at scales up to 1024 GPUs"
STAGED_OUTPUTS = (
    "a flat UALink pod reduces the step-time contribution of small-message "
    "collectives at scales up to 1024 GPUs, while NVLink 5 keeps an "
    "advantage in bandwidth-bound scenarios",
)

# Plan/registry anchors for the placement statements.
REGISTRY_RANGE = (Fraction(10), Fraction(2000))    # A-L0-LAT / A-L0X-LAT / A-L0D-LAT free range
REGISTRY_POINT = Fraction(200)                     # the shared registry latency point
PLAN_SPAN = (Fraction(10), Fraction(800))          # plan §2.1 anchored-axis span (~10-800 ns)
B_REGISTRY = Fraction(64)                          # A-L0-BW / A-L0X-BW / A-L0D-BW registry point
M_BYTES = 16384                                    # 2^14; A-W1-SIZE registry smoke point
RANKS_LADDER = [8, 16, 32, 64, 128, 256, 512, 1024]
LADDER_PROVENANCE = (
    "power-of-2 ladder from the free smoke default r=8 to the anchor's own "
    "stated scale ceiling 1024 — the ONLY anchor-derived regime number in "
    "this stage; every rung is a power of two (A-L0D-POW2 accepts natively) "
    "and divides M=16384 exactly (A-L0-DIV / A-L0X-DIV / A-L0D-DIV accept, "
    "no bracketing)"
)
# Context anchors on the latency axis (different anchors' numbers; placement
# context only, per the plan's own span arithmetic).
A8_CXL_UPPER = Fraction(140)   # CAL-A8 emulated upper point
A9_ONE_STAGE = Fraction(80)    # CAL-A9 plan-stated one-stage link+switch sum


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ring_infra(r: int) -> l0.InfraConfig:
    return l0.InfraConfig(
        topology_id=f"ring{r}_a10_hop800_v1",
        ranks=r,
        link_bytes_per_ns=B_REGISTRY,
        hop_latency_ns=ANCHOR_L_NS,
    )


def xbar_infra(r: int) -> l0_crossbar.CrossbarConfig:
    return l0_crossbar.CrossbarConfig(
        topology_id=f"crossbar{r}_a10_pair800_v1",
        ranks=r,
        injection_bytes_per_ns=B_REGISTRY,
        pair_latency_ns=ANCHOR_L_NS,
    )


def rd_infra(r: int) -> l0_recursive_doubling.RecursiveDoublingConfig:
    return l0_recursive_doubling.RecursiveDoublingConfig(
        topology_id=f"exchange{r}_a10_pair800_v1",
        ranks=r,
        injection_bytes_per_ns=B_REGISTRY,
        pair_latency_ns=ANCHOR_L_NS,
        steps=r.bit_length() - 1,
    )


def cct_ring(r: int) -> Fraction:
    return l0.ring_allreduce_time_ns(M_BYTES, r, ring_infra(r))


def cct_xbar(r: int) -> Fraction:
    return l0_crossbar.crossbar_allreduce_time_ns(M_BYTES, r, xbar_infra(r))


def cct_rd(r: int) -> Fraction:
    return l0_recursive_doubling.rd_allreduce_time_ns(M_BYTES, rd_infra(r))


def serialization_term(r: int) -> Fraction:
    return Fraction(2 * (r - 1) * M_BYTES, r) / B_REGISTRY


def log2(r: int) -> int:
    return r.bit_length() - 1


# ---------------------------------------------------------------------------
# 1. Anchor transcription + assumption-class classification
# ---------------------------------------------------------------------------
def anchor_transcription() -> dict:
    return {
        "staged_material": {
            "assumption_quote": STAGED_QUOTE,
            "status": "a STATED MODEL ASSUMPTION (study INPUT), not a measurement — the anchor's own premise is that NVIDIA publishes no such number",
            "assumed_value": "0.8 \u00b5s = 800 ns end-to-end latency for NVLink Network (the NVLink-side latency input of their analytical model)",
            "sub_us_context": "the assumption is stated as 'consistent with sub-\u00b5s positioning for NVSwitch hops' — 800 ns sits at exactly 4/5 of the 1 \u00b5s boundary its own citation draws",
            "scale_ceiling_gpus": STAGED_SCALE_CEILING,
            "qualitative_outputs": STAGED_OUTPUTS,
            "outputs_status": "DIRECTION STATEMENTS of their analytical model — no per-configuration completion-time number is staged anywhere (abstract + snippet only; full text paywalled)",
        },
        "confidence": (
            "M per the staging doc — quote via public search snippet of the "
            "paywalled paper; exact parameter table NOT extracted; wording "
            "re-verification against the paper at owner integration is an "
            "OPEN item (recorded, not resolved here)"
        ),
        "access": "abstract public (IEEE CSDL 453800a068); full text paywalled",
    }


def assumption_class_classification() -> dict:
    return {
        "class": "ASSUMPTION-CLASS (peer-reviewed USAGE of an assumed value), distinct from every measurement-, spec-, and emulation-class anchor in the set (CAL-A1/A2/A7 spec; CAL-A3/A6 measured; CAL-A8 emulated inputs; CAL-A9 design-estimate)",
        "what_peer_review_certifies": (
            "the plausibility of USING 0.8 \u00b5s in a training-scale "
            "analytical comparison — never the value itself; the anchor "
            "cannot serve as evidence that any fabric HAS this latency"
        ),
        "falsification_power": (
            "NONE on the L axis: the quote's own premise is that the true "
            "number is unpublished, so no model L value (registry 200 ns "
            "included) can be falsified or confirmed against it; the anchor "
            "can only place a USED value on the axis and bound the "
            "conversation's scale — which is exactly the plan's 'sanity "
            "band' role"
        ),
        "verification_debt": (
            "the staged quote is search-snippet provenance (confidence M) "
            "and the paper's exact model equations and UALink-side "
            "parameter table are paywalled and unstaged — which latency "
            "READING their model charges (per-hop vs end-to-end) is "
            "unverifiable from staged material; this stage declares and "
            "quantifies BOTH readings instead of adjudicating (\u00a7 dual_reading_projection)"
        ),
    }


# ---------------------------------------------------------------------------
# 2. Latency-axis placement (the anchor's plan-assigned role)
# ---------------------------------------------------------------------------
def latency_axis_placement() -> dict:
    v = ANCHOR_L_NS
    inside_range = REGISTRY_RANGE[0] <= v <= REGISTRY_RANGE[1]
    assert inside_range
    # spot values asserted to guard the findings text
    assert str(v / REGISTRY_POINT) == "4"
    assert str(REGISTRY_RANGE[1] / v) == "5/2"
    assert str(v / A8_CXL_UPPER) == "40/7"
    assert str(v / A9_ONE_STAGE) == "10"
    assert str(v / Fraction(1000)) == "4/5"
    return {
        "question": "where does CAL-A10's assumed 0.8 \u00b5s sit on the shared latency axis relative to the registry point, the registry free range, the plan's anchored span, and the other anchors' axis points?",
        "placements_exact": {
            "assumption_800_over_registry_200": str(v / REGISTRY_POINT),          # 4
            "registry_200_over_assumption_800": str(REGISTRY_POINT / v),          # 1/4
            "registry_range_upper_2000_over_assumption_800": str(REGISTRY_RANGE[1] / v),  # 5/2
            "assumption_800_over_cal_a8_emulated_upper_140": str(v / A8_CXL_UPPER),      # 40/7
            "assumption_800_over_cal_a9_one_stage_80": str(v / A9_ONE_STAGE),     # 10
            "assumption_800_over_1us_boundary": str(v / Fraction(1000)),          # 4/5
        },
        "placements_float": {
            "assumption_over_registry": float(v / REGISTRY_POINT),          # 4.0
            "registry_over_assumption": float(REGISTRY_POINT / v),          # 0.25
            "assumption_over_range_upper_pct": float(v / REGISTRY_RANGE[1] * 100),  # 40.0
            "assumption_over_a8_upper": float(v / A8_CXL_UPPER),            # 5.714
            "assumption_over_a9_one_stage": float(v / A9_ONE_STAGE),        # 10.0
        },
        "findings": [
            "the assumed 800 ns sits INSIDE the registry free range [10, 2000] — in its upper region, at exactly 40% of the range's upper endpoint — and it IS, exactly, the plan §2.1 anchored-span UPPER endpoint (~10-800 ns): unlike stages A8/A9, which cited 800 ns as a different anchor's span context, THIS anchor owns that endpoint; the plan's span arithmetic terminates at this stage's own number",
            "the registry point 200 ns is exactly 1/4 of the assumption (800/200 = 4): the repo-wide latency default is 4x more optimistic than the peer-reviewed assumption-class usage on the same axis — a placement fact; the registry value is untouched",
            "on the axis's anchored points: the assumption sits 40/7 \u2248 5.71x above CAL-A8's emulated CXL-class upper point (140 ns) and exactly 10x above CAL-A9's plan-stated one-stage link+switch sum (80 ns) — the GPU-class assumption-class point is a full order above the CXL-class budget points, quantifying the class separation the plan's two-tier span encodes",
            "the assumption sits at exactly 4/5 of the 1 \u00b5s boundary of its own cited 'sub-\u00b5s positioning' — internally consistent with its own justification by a 20% margin",
            "the free range's upper half remains anchor-free (2000 vs 800 ns = 5/2) — the placement fact behind the plan's NARROW-range-upper candidate; no range or value is changed here",
        ],
    }


# ---------------------------------------------------------------------------
# 3. Dual-reading projection (end-to-end pair vs per-hop) — declared, both
#    executed, never adjudicated
# ---------------------------------------------------------------------------
def dual_reading_projection() -> dict:
    multipliers = {
        "crossbar (end-to-end pair reading, PRIMARY)": {r: 2 for r in RANKS_LADDER},
        "recursive doubling (pair-exchange steps)": {r: 2 * log2(r) for r in RANKS_LADDER},
        "ring (per-hop reading, SECONDARY)": {r: 2 * (r - 1) for r in RANKS_LADDER},
    }
    r1024 = {name: m[1024] for name, m in multipliers.items()}
    assert r1024 == {
        "crossbar (end-to-end pair reading, PRIMARY)": 2,
        "recursive doubling (pair-exchange steps)": 20,
        "ring (per-hop reading, SECONDARY)": 2046,
    }
    return {
        "declared_readings": {
            "primary_end_to_end_pair": "the quote's own wording is END-TO-END latency for NVLink Network — pair-level across the fabric; the natural operand is the crossbar identity's link.pair_latency_ns (A-L0X-LAT), charged exactly 2L per AllReduce regardless of rank count",
            "secondary_per_hop": "the same quote cites 'sub-\u00b5s positioning for NVSwitch hops', and the plan §2.1 A-L0-LAT row reads the figure as hop-axis span context; the ring identity's link.hop_latency_ns (A-L0-LAT) is charged 2(r-1) times per AllReduce — stage A8 already executed this reading at r=8",
        },
        "ambiguity_status": (
            "the anchor's model equations are PAYWALLED — which reading their "
            "model charges is unverifiable from staged material; this stage "
            "executes BOTH (plus the log-chain middle point) and quantifies "
            "the spread; it does NOT adjudicate"
        ),
        "chain_multipliers_of_the_800ns_figure_per_allreduce": {
            name: {str(r): m for r, m in per_r.items()} for name, per_r in multipliers.items()
        },
        "spread_at_anchor_scale_ceiling_1024": {
            "multipliers": r1024,
            "latency_term_ratio_ring_over_crossbar_exact": "1023",
            "finding": (
                "the SAME single assumed number, read two ways, produces a "
                "1023x spread in the charged latency at the anchor's own "
                "scale ceiling (2046 x 800 ns vs 2 x 800 ns) — the reading "
                "choice dominates every other placement question at scale, "
                "and it cannot be settled from the staged material"
            ),
        },
    }


# ---------------------------------------------------------------------------
# 4. Scale sweep: all 24 executed rows + exact chain-law cross-checks
# ---------------------------------------------------------------------------
def scale_sweep() -> tuple[dict, dict]:
    rows = []
    for r in RANKS_LADDER:
        table = load_json(RESULTS / "sweeps" / SWEEP_IDS[r] / "table.json")
        by_algo = {row["algorithm"]: row for row in table["configs"]}
        assert set(by_algo) == {"allreduce_ring", "allreduce_recursive_doubling", "allreduce_crossbar"}
        closed = {
            "allreduce_ring": cct_ring(r),
            "allreduce_recursive_doubling": cct_rd(r),
            "allreduce_crossbar": cct_xbar(r),
        }
        for algo, exact in closed.items():
            executed = by_algo[algo]["o_cct"]["completion_time_ns_mean_exact"]
            assert executed == str(exact), (r, algo, executed, str(exact))
        t_ring, t_rd, t_xbar = closed["allreduce_ring"], closed["allreduce_recursive_doubling"], closed["allreduce_crossbar"]

        # chain laws (exact at every rung)
        L = ANCHOR_L_NS
        assert t_ring - t_xbar == 2 * L * (r - 2)
        assert t_rd - t_xbar == 2 * L * (log2(r) - 1)
        assert t_ring - t_rd == 2 * L * (r - 1 - log2(r))
        # bandwidth-term identity across the three (exact)
        ser = serialization_term(r)
        assert t_ring - 2 * (r - 1) * L == ser
        assert t_rd - 2 * log2(r) * L == ser
        assert t_xbar - 2 * L == ser

        lat_ring = 2 * (r - 1) * L
        lat_rd = 2 * log2(r) * L
        lat_xbar = 2 * L
        rows.append(
            {
                "ranks": r,
                "log2_r": log2(r),
                "sweep_id": SWEEP_IDS[r],
                "cct_ring_ns_exact": str(t_ring),
                "cct_ring_ns_float": float(t_ring),
                "cct_recursive_doubling_ns_exact": str(t_rd),
                "cct_recursive_doubling_ns_float": float(t_rd),
                "cct_crossbar_ns_exact": str(t_xbar),
                "cct_crossbar_ns_float": float(t_xbar),
                "serialization_term_ns_exact": str(ser),
                "latency_share_ring_pct": float(lat_ring / t_ring * 100),
                "latency_share_doubling_pct": float(lat_rd / t_rd * 100),
                "latency_share_crossbar_pct": float(lat_xbar / t_xbar * 100),
                "ring_over_crossbar_exact": str(t_ring / t_xbar),
                "ring_over_crossbar_float": float(t_ring / t_xbar),
                "doubling_over_crossbar_exact": str(t_rd / t_xbar),
                "doubling_over_crossbar_float": float(t_rd / t_xbar),
            }
        )

    # spot values at the anchor scale ceiling (guard the findings text)
    r8 = next(row for row in rows if row["ranks"] == 8)
    r1024 = next(row for row in rows if row["ranks"] == 1024)
    assert r8["cct_ring_ns_exact"] == "11648"  # reproduces stage A8's executed L=800 row
    assert r8["cct_crossbar_ns_exact"] == "2048"
    assert r1024["cct_ring_ns_exact"] == "3274623/2"
    assert r1024["cct_crossbar_ns_exact"] == "4223/2"
    assert r1024["cct_recursive_doubling_ns_exact"] == "33023/2"
    assert r1024["ring_over_crossbar_exact"] == "3274623/4223"
    assert r1024["latency_share_ring_pct"] > 99.96
    assert r1024["latency_share_crossbar_pct"] < 76

    # r=2 coincidence (closed-form only; r=2 is not a sweep rung)
    L = ANCHOR_L_NS
    t2_ring = serialization_term(2) + 2 * 1 * L
    t2_rd = serialization_term(2) + 2 * 1 * L
    t2_xbar = serialization_term(2) + 2 * L
    assert t2_ring == t2_rd == t2_xbar

    summary = {
        "ladder": LADDER_PROVENANCE,
        "fixed_parameters": {
            "L_ns": str(ANCHOR_L_NS),
            "L_provenance": "CAL-A10's assumption point (0.8 \u00b5s), held FIXED on all three identities — the anchor says nothing about rank dependence of latency",
            "B_bytes_per_ns": str(B_REGISTRY),
            "B_provenance": "A-L0-BW / A-L0X-BW / A-L0D-BW registry point, FIXED — the anchor's bandwidth values are not staged (UALink side paywalled; NVLink side belongs to different anchors' spec ceilings)",
            "payload_bytes": M_BYTES,
            "payload_provenance": "A-W1-SIZE registry smoke point (16 KiB), FIXED while ranks sweep — the anchor's scenario is more ranks exchanging the same small per-layer tensors; the anchor names no size (declared model-side regime choice)",
        },
        "executed_rows": rows,
        "chain_laws_verified_exact": [
            "ring - crossbar == 2L(r-2) at every rung (zero at r=2, linear growth)",
            "doubling - crossbar == 2L(log2(r)-1) at every rung",
            "ring - doubling == 2L(r-1-log2(r)) at every rung",
            "all three identities coincide at r=2 (closed-form check; r=2 is not a sweep rung — labeled closed-form-only)",
            "the bandwidth term 2(r-1)/r*M/B is IDENTICAL across the three identities at every rung (exact Fraction equality) — every CCT difference in this stage is PURELY latency-chain structure",
        ],
        "cross_stage_determinism": "the r=8 ring rung reproduces stage A8's executed L=800 row exactly (11648 ns; A8 sweep df630860…, row ring8_a8_l800_v1) — same identity, same values, independent files",
        "punchline": (
            "at the anchor's assumption point and scale ceiling (L=800 ns, "
            "r=1024, 16 KiB): ring CCT = 3274623/2 ns \u2248 1.637 \u00b5s (99.97% "
            "latency term), recursive doubling = 33023/2 ns \u2248 16.5 \u00b5s "
            "(96.90%), crossbar = 4223/2 ns \u2248 2.1 \u00b5s (75.78%) — a "
            "ring/crossbar spread of 3274623/4223 \u2248 775.4x at IDENTICAL wire "
            "bytes, bandwidth, payload, and assumed latency; the spread at "
            "r=8 is only 91/16 \u2248 5.69x — the flat-vs-chained gap is a "
            "SCALE phenomenon, growing linearly as 2L(r-2)"
        ),
    }
    coverage = {
        "executed_coverage_note": (
            "all 24 grid cells (8 rungs x 3 identities) were executed by the "
            "eight sweeps; every row was cross-checked against the closed "
            "form of its own run-path identity function by exact "
            "Fraction string equality; the r=2 coincidence is the only "
            "closed-form-only statement in this record and is labeled as such"
        )
    }
    return summary, coverage


# ---------------------------------------------------------------------------
# 5. Qualitative-output expressiveness (the anchor's two direction findings)
# ---------------------------------------------------------------------------
def qualitative_output_expressiveness() -> dict:
    # (b) bandwidth-bound half: expressible only through B — verify the
    # bandwidth terms are identical across identities at every rung (done
    # in scale_sweep); at fixed registry B no identity difference exists.
    for r in RANKS_LADDER:
        ser = serialization_term(r)
        assert cct_ring(r) - 2 * (r - 1) * ANCHOR_L_NS == ser == cct_xbar(r) - 2 * ANCHOR_L_NS
    return {
        "anchor_output_a_small_message_flat_advantage": {
            "staged": "a flat UALink pod REDUCES the step-time contribution of small-message collectives at scales up to 1024 GPUs",
            "model_side_fact": (
                "at the anchor's own assumption point the L0 family's "
                "flat-vs-chained latency-charge structure reproduces the "
                "SHAPE of this finding: the flat (crossbar) identity's "
                "latency charge is CONSTANT (2L) while both chained "
                "identities' charges grow with r (linear 2(r-1)L, "
                "logarithmic 2log2(r)L), so the flat identity's small-message "
                "CCT advantage grows without bound in r — from 91/16 \u2248 "
                "5.69x at r=8 to 3274623/4223 \u2248 775.4x at the anchor's "
                "stated ceiling r=1024, with the ring's latency share at "
                "99.97% there"
            ),
            "classification": (
                "DIRECTION-CONSISTENT STRUCTURAL CONTEXT, not a match and "
                "not a calibration: the anchor stages NO completion-time "
                "number, its fabric models are paywalled, and the L0 "
                "identities are our constructions — the consistency says "
                "both models agree that latency-chain structure dominates "
                "small-message collective time at scale; it cannot say the "
                "models agree quantitatively about anything"
            ),
        },
        "anchor_output_b_bandwidth_bound_nvlink_advantage": {
            "staged": "NVLink 5 keeps an advantage in bandwidth-bound scenarios",
            "model_side_fact": (
                "at L0 the bandwidth term 2(r-1)/r*M/B is IDENTICAL across "
                "all three identities at every rung (verified by exact "
                "Fraction equality) — a bandwidth-bound advantage between "
                "fabric classes is expressible ONLY through a B difference, "
                "and the anchor's B values are not staged (UALink side "
                "paywalled/model-only until silicon; NVLink5 side would be "
                "different anchors' spec ceilings, e.g. CAL-A1/A2)"
            ),
            "classification": (
                "EXPRESSIVENESS-LIMITED (the bandwidth-axis sibling of the "
                "stage's dual-reading blindness): the second half of the "
                "anchor's comparative finding has NO operand difference at "
                "L0 at fixed B — neither agreement nor contradiction can be "
                "stated; recorded as a declared limit, not a gap to tune "
                "around"
            ),
        },
    }


# ---------------------------------------------------------------------------
# 6. GF-context note (labeled, non-CAL anchors from anchors_gapfill.md)
# ---------------------------------------------------------------------------
def gf_context() -> dict:
    return {
        "status": "CONTEXT ONLY — GF-* rows are gapfill-staging candidates (docs/calibration/anchors_gapfill.md), NOT integrated CAL anchors; no GF number is used as a calibration target anywhere in this stage",
        "gapfill_note_verbatim_context": (
            "the gapfill doc's GF-10 row states the interpretation duty: "
            "'the \u00b5s-class P2P numbers that CAL-A10's 0.8 \u00b5s "
            "assumption-class value can finally be checked against' — "
            "measured app-level P2P \u2248 9 \u00b5s on 2018-era NVLink is an "
            "order above the assumption, but app-level P2P includes the "
            "software stack, so the two bound different things"
        ),
        "scale_context_points": {
            "GF-10 (V100-era app-level P2P, measured)": "\u2248 9 \u00b5s — an order ABOVE the assumption; includes software stack",
            "GF-11 (GB200 NVL72 measured components, H)": "LL2_RTT 0.306 \u00b5s, Lremote_store 0.792 \u00b5s — the current-gen measured remote-store component lands numerically within 1% of the assumed 0.8 \u00b5s",
            "GF-03 (B300 D2D microbenchmark, M)": "\u2248 1.4-1.6 \u00b5s device-to-device — same order, above the assumption",
        },
        "finding": (
            "the assumption-class value sits at the scale of current-gen "
            "MEASURED latency COMPONENTS (GF-11: 0.792 \u00b5s remote store) "
            "and an order below app-level P2P that includes software (GF-10: "
            "9 \u00b5s) — i.e. the peer-reviewed assumption is component-scale, "
            "not software-path-scale; plausibility context only, never "
            "evidence about the assumed number itself"
        ),
    }


# ---------------------------------------------------------------------------
# 7. Inextractable targets (FAIL-clause honesty duty)
# ---------------------------------------------------------------------------
def inextractable_targets() -> list[dict]:
    return [
        {
            "target": "the paper's UALink-side parameters",
            "reason": "paywalled parameter table, not staged; the plan §1.1 row itself states 'UALink-side parameters remain model-only until silicon' — no UALink B or L number exists to place on any axis; the flat-pod side of this stage is a STRUCTURAL stand-in (the constant-chain crossbar identity), never a reproduction of their model",
        },
        {
            "target": "the paper's exact model equations (which latency reading it charges: per-hop vs end-to-end pair)",
            "reason": "full text paywalled; unverifiable from staged material — this stage declares and executes BOTH readings plus the log-chain middle and quantifies the spread (1023x in the latency charge at r=1024) instead of adjudicating; owner resolves against the paper",
        },
        {
            "target": "any quantitative step-time / completion-time number",
            "reason": "none staged — the anchor's outputs are two QUALITATIVE direction statements; no CCT deviation exists anywhere in this stage, and no O-CCT comparison is possible (the plan's 'cannot calibrate O-CCT' verdict executed literally)",
        },
        {
            "target": "the exact small-message sizes and per-scale run configurations",
            "reason": "'small-message collectives' is unnamed and per-size tables are paywalled; the stage's 16 KiB payload is the A-W1-SIZE registry smoke point — a declared model-side regime choice inside the plan's ≤ ~64 KiB small-message boundary, never an anchor-derived size",
        },
        {
            "target": "NVLink Network actual end-to-end latency",
            "reason": "explicitly unpublished — the quote's own premise; the 0.8 \u00b5s is an assumption filling a publication gap, so there is nothing measured to compare against and no L value can be falsified by this anchor (the assumption-class classification quantified above)",
        },
        {
            "target": "verification of the staged quote's wording",
            "reason": "confidence M — the quote's provenance is a public search snippet of the paywalled paper (staging doc flags 're-verify wording against the paper at integration'); an open verification debt recorded for the owner, per the staging doc's own caveat",
        },
    ]


# ---------------------------------------------------------------------------
# 8. Store-run cross-checks
# ---------------------------------------------------------------------------
def run_checks() -> list[dict]:
    checks = []
    for run_id, name, closed in (
        (RUN_ID_FLAT, "flat1024", cct_xbar(1024)),
        (RUN_ID_CHAIN, "chain1024", cct_ring(1024)),
    ):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        per_op = obs["per_op"][0]
        assert per_op["payload_bytes"] == M_BYTES
        assert obs["model"]["ranks"] == 1024
        assert per_op["completion_time_ns_exact"] == str(closed)
        if name == "flat1024":
            assert obs["backend_id"] == "analytical_l0_crossbar"
            assert Fraction(obs["model"]["pair_latency_ns_exact"]) == ANCHOR_L_NS
            assert Fraction(obs["model"]["injection_bytes_per_ns_exact"]) == B_REGISTRY
        else:
            assert obs["backend_id"] == "analytical_l0"
            assert Fraction(obs["model"]["hop_latency_ns_exact"]) == ANCHOR_L_NS
            assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == B_REGISTRY
        checks.append(
            {
                "run_id": run_id,
                "mapping": (
                    f"anchor scale ceiling: CAL-A10's stated 1024-GPU bound at the "
                    f"assumption point L=800 ns on the "
                    f"{'FLAT crossbar (primary end-to-end pair reading)' if name == 'flat1024' else 'CHAINED ring (secondary per-hop reading)'} "
                    f"identity, B=64 B/ns, 16 KiB"
                ),
                "experiment_id": run["manifest"]["experiment_id"],
                "manifest_path": run["manifest_path"],
                "payload_bytes": per_op["payload_bytes"],
                "cct_ns_exact": per_op["completion_time_ns_exact"],
                "cct_ns_float": per_op["completion_time_ns"],
                "verdict": "store run == closed form of the same identity function (exact Fraction string equality)",
            }
        )
    return checks


# ---------------------------------------------------------------------------
# 9. Divisibility / POW2 gate acceptance
# ---------------------------------------------------------------------------
def gate_acceptance() -> dict:
    for r in RANKS_LADDER:
        assert r & (r - 1) == 0  # power of two: A-L0D-POW2 native
        l0.require_divisible("analytical_l0", "cal_a10_probe", M_BYTES, r, "A-L0-DIV")
        l0.require_divisible("analytical_l0_crossbar", "cal_a10_probe", M_BYTES, r, "A-L0X-DIV")
        l0.require_divisible("analytical_l0_recursive_doubling", "cal_a10_probe", M_BYTES, r, "A-L0D-DIV")
    return {
        "finding": (
            "M = 16384 = 2^14 is divisible by every power-of-two ladder rung "
            "(8…1024), so the A-L0-DIV / A-L0X-DIV / A-L0D-DIV gates ACCEPT "
            "the payload exactly at all 24 grid cells — no bracketing "
            "anywhere in the stage — and the A-L0D-POW2 gate accepts the "
            "ladder natively (every rung is a power of two)"
        ),
        "contrast": (
            "the mirror of stage A3, where r = 72 = 8*9 rejected every power "
            "of two; the anchor's 1024-scale claim is power-of-two-clean, "
            "which is exactly why the ladder could be executed without a "
            "single bracketed cell"
        ),
    }


def main() -> int:
    transcription = anchor_transcription()
    classification = assumption_class_classification()
    placement = latency_axis_placement()
    dual = dual_reading_projection()
    sweep, coverage = scale_sweep()
    expressiveness = qualitative_output_expressiveness()
    gf = gf_context()
    inextractable = inextractable_targets()
    runs = run_checks()
    gates = gate_acceptance()

    deviation_summary = (
        "CAL-A10 stages no completion time, so no CCT deviation exists; the "
        "anchor's plan-assigned deviations are: (1) LATENCY-AXIS PLACEMENT — "
        "the assumed 800 ns IS the plan §2.1 anchored-span upper endpoint "
        "(this anchor owns the number stages A8/A9 cited as context), sits "
        "inside the registry free range [10, 2000] at exactly 40% of its "
        "upper endpoint, is exactly 4x the registry point 200 ns (the "
        "repo-wide default is 4x more optimistic than the peer-reviewed "
        "assumption-class usage), sits 40/7 ≈ 5.71x above CAL-A8's emulated "
        "CXL-class upper and exactly 10x above CAL-A9's one-stage budget "
        "sum, and lands at exactly 4/5 of the 1 µs boundary of its own "
        "'sub-µs' justification; (2) SCALE-AXIS EXECUTION at the assumption "
        "point — the swept rank ladder 8→1024 (the anchor's own stated "
        "ceiling, its only staged regime number) over the three single-port "
        "L0 identities shows the flat-vs-chained small-message spread "
        "growing linearly as 2L(r-2): from 91/16 ≈ 5.69x at r=8 to "
        "3274623/4223 ≈ 775.4x at r=1024 (ring latency share 99.97% there, "
        "crossbar 75.78%), with identical wire bytes, bandwidth term, "
        "payload, and assumed latency across all 24 executed cells; (3) the "
        "DUAL-READING spread — the same single assumed number, read "
        "end-to-end (crossbar 2L) vs per-hop (ring 2(r-1)L), differs by a "
        "1023x latency charge at the anchor's ceiling, and which reading "
        "the paywalled model uses is unverifiable — declared and quantified, "
        "never adjudicated; (4) the anchor's two QUALITATIVE outputs — the "
        "flat-pod small-message advantage is direction-consistent structural "
        "context (constant vs growing latency chains), while the NVLink5 "
        "bandwidth-bound advantage has NO operand difference at L0 at fixed "
        "B (identical 2(r-1)/r·M/B terms, exact) — expressiveness-limited, "
        "recorded, not tuned"
    )

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A10 (anchor CAL-A10)",
        "anchor": {
            "anchor_id": "CAL-A10",
            "title": "HiPC 2025 Workshop: Communication-Centric UALink vs NVLink comparison (analytical model, assumption-class latency input)",
            "source_row": "sources.csv row CAL-A10 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A10",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A10 (cannot calibrate O-CCT — a stated assumption; sanity band for GPU-fabric hop latency; UALink-side parameters remain model-only until silicon)",
            "url": "https://www.computer.org/csdl/proceedings-article/hipcw/2025/453800a068/2fmcmT1r8Jy",
            "confidence": "M — quote via public search snippet; full text paywalled; exact parameter table not extracted; wording re-verification at owner integration is an open item",
            "transcription": transcription,
            "assumption_class_classification": classification,
        },
        "target": {
            "role": "assumption_class_latency_anchor_plus_scale_regime",
            "regime": {
                "message_bytes": M_BYTES,
                "message_regime": "small-message (the plan §1.2 row: 'small-message regime implied'); 16 KiB is the A-W1-SIZE registry smoke point — a declared model-side choice inside the plan's ≤ ~64 KiB boundary, the anchor names no size",
                "ranks": RANKS_LADDER,
                "ranks_note": "power-of-2 ladder from the free smoke default 8 to the anchor's stated ceiling 1024 — the only anchor-derived regime number in this stage",
                "topology_class": "flat single-tier switch (crossbar identity, the anchor's 'flat UALink pod' structural stand-in) vs chained schedules (ring linear, recursive doubling logarithmic) — the anchor's hierarchical NVLink-Network side has no landed identity claim",
            },
            "inextractable_targets": inextractable,
        },
        "model": {
            "backends": ["analytical_l0", "analytical_l0_crossbar", "analytical_l0_recursive_doubling"],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L (src/essun/backends/analytical/l0.py)",
                "crossbar": "t = 2(r-1)/r*M/B + 2L (src/essun/backends/analytical/l0_crossbar.py)",
                "recursive_doubling": "t = 2(r-1)/r*M/B + 2*log2(r)*L (src/essun/backends/analytical/l0_recursive_doubling.py)",
            },
            "free_parameters": {
                "ranks_swept": LADDER_PROVENANCE,
                "L_fixed_ns": str(ANCHOR_L_NS),
                "L_provenance": "CAL-A10's assumption-class 0.8 µs under the declared dual reading (primary end-to-end pair on crossbar/doubling pair_latency_ns; secondary per-hop on ring hop_latency_ns)",
                "B_fixed_bytes_per_ns": str(B_REGISTRY),
                "B_provenance": "shared registry point on all three identities — the anchor stages no bandwidth number for either fabric",
                "payload_fixed_bytes": M_BYTES,
            },
            "assumptions": "A-L0-* / A-L0X-* / A-L0D-* families (experiments/vertical_slice/assumptions_l0.yaml)",
            "closed_form_coverage": coverage["executed_coverage_note"],
        },
        "comparison": {
            "latency_axis_placement": placement,
            "dual_reading_projection": dual,
            "scale_sweep": sweep,
            "qualitative_output_expressiveness": expressiveness,
            "gf_context": gf,
            "gates": gates,
            "anchor_scale_runs": runs,
        },
        "deviation": {
            "summary": deviation_summary,
            "not_tuned": (
                "nothing was tuned: the anchor stages NO completion time, so "
                "no parameter could be tuned toward any anchor output; the "
                "ladder, the assumption point, and every fixed value were "
                "fixed by registry/anchor/plan arithmetic BEFORE any stage "
                "output was read; the anchor's assumption is recorded as an "
                "assumption (peer-reviewed usage, M-confidence snippet "
                "provenance) and never as a measurement; no registry value, "
                "range, manifest parameter, or claim was changed"
            ),
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external published assumption-class analytical study; no E3/E4 language — CAL-A10 is not our testbed and its number is not a measurement; the owner's adjudication precedes any label move",
        },
        "backing": {
            "run_ids": [RUN_ID_FLAT, RUN_ID_CHAIN],
            "sweep_ids": [SWEEP_IDS[r] for r in RANKS_LADDER],
            "sweep_dirs": [f"results/sweeps/{SWEEP_IDS[r]}" for r in RANKS_LADDER],
            "run_backed_numbers": "every run-path-executed number (24 sweep cells, 2 store runs); all grid cells executed — the r=2 coincidence is the only closed-form-only statement and is labeled",
            "inputs": [
                "experiments/calibration/a10/sweep_a10_scale_r{8,16,32,64,128,256,512,1024}_v1.yaml (8 files)",
                "experiments/calibration/a10/run_a10_flat1024_v1.yaml",
                "experiments/calibration/a10/run_a10_chain1024_v1.yaml",
                "experiments/calibration/a10/workloads/ (8 files)",
                "experiments/calibration/a10/topologies/ (24 files)",
                "experiments/calibration/a10/profiles/implementation_profile_l0_{ring,crossbar}_cal_a10_v1.yaml",
            ],
            "reproduce": (
                "for r in 8 16 32 64 128 256 512 1024: "
                "make sweep EXP=experiments/calibration/a10/sweep_a10_scale_r${r}_v1.yaml ; "
                "make run EXP=experiments/calibration/a10/run_a10_flat1024_v1.yaml ; "
                "make run EXP=experiments/calibration/a10/run_a10_chain1024_v1.yaml ; "
                ".venv/bin/python experiments/calibration/a10/build_calibration_record.py"
            ),
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
