"""Build the PROPOSED calibration-candidate record for anchor CAL-A8 (Q1
calibration stage A8.

CAL-A8 is Pond (ASPLOS 2023, arXiv:2203.00241): CXL added-latency tolerance
emulation on production cloud workloads — "emulating either 64ns or 140ns of
additional memory access overheads over same-NUMA-node memory", with 43% and
37% of 158 workloads respectively remaining within performance goals. Per
docs/calibration/CALIBRATION_PLAN.md §1.1 this anchor CANNOT calibrate O-CCT
("a workload-level latency-tolerance study, not a collective completion
time. Locates the CXL-class point on the latency axis for L parameters
only"), so this stage executes that plan-assigned role: the LATENCY-AXIS
PLACEMENT of the anchor's two emulated points (64/140 ns) against the
A-L0-LAT registry point (200 ns), the registry free range [10, 2000], and
the plan's anchored axis span (~10-800 ns) — as the mirror image of stages
A4/A5/A6, which swept the bandwidth axis at fixed latency. The anchor's
MEASURED outputs (the 43%/37% workload-goal fractions) are shown to be
STRUCTURALLY INEXPRESSIBLE in the L0 input space (no population/SLO axis
exists), classified per handoff rule 5 — never tuned, never smoothed.

Honesty discipline specific to this anchor: the 64/140 ns figures are
EMULATED study inputs (injected additions that bound plausible CXL-class
device latency), not device measurements; the per-access ns-scale is read
onto the collective per-hop latency L by a DECLARED projection — the same
reading the plan's A-L0-LAT row uses. No staged number is presented as a
measured device latency anywhere in this record.

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity with exact Fractions, and writes a content-addressed
record to ``results/calibration/<record_id>/record.json`` (record_id =
SHA-256 of the canonical record; append-only — an existing record with
different bytes is an error, identical bytes are idempotent).

Run-backed cross-checks enforced here (a mismatch is a bug, not a finding):

1. all 12 executed sweep rows (6 L values x 2 regimes) equal the closed
   form of the run path's own identity function
   (``l0.ring_allreduce_time_ns``) by exact Fraction string equality;
2. both store runs equal the same closed form at the anchor points;
3. the L0 input space is enumerated against the landed dataclasses
   (InfraConfig / W1Config field sets) and the observables registry — no
   population/SLO axis and no goal observable exists;
4. the identity's response to L is verified EXACTLY affine with slope
   2*(r-1) identical across regimes (the homogeneous-response fact the
   anchor's heterogeneous population CDF contradicts);
5. the divisibility gate accepts both payload sizes at r = 8.

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number is either (a) transcribed from the anchor's staged
numbers in ``docs/calibration/anchors_staging.md`` §A8 (declared with
provenance), or (b) computed from stored run/sweep artifacts or the
identity function by this script. Nothing is tuned.

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

from essun.backends.analytical.l0 import (
    BACKEND_ID,
    InfraConfig,
    execute as l0_execute,
    require_divisible,
    ring_allreduce_time_ns,
)
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json
from essun.observables import registered as registered_observables
from essun.workload import w1

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_L64 = "206c82a0ec1f5b7ce12865dba15225b3d856a4e9d70f36054ce926d5cd892208"
RUN_ID_L140 = "d352f5f34d8ae15812efb669dc5ff0e2941193bdd96fe0ffd02aa4be4d1cc47b"
SWEEP_ID_SMALL = "df630860b11ce82819940fb72422ba12bdaf87cb098f854f4fb2ccb57871ee04"
SWEEP_ID_LARGE = "477e6d196faa79310ee67278caec92c858697feee6332f4c4acb6c3989cd9af0"

RESULTS = REPO_ROOT / "results"
A8 = REPO_ROOT / "experiments" / "calibration" / "a8"

# Anchor CAL-A8 staged numbers (docs/calibration/anchors_staging.md §A8;
# transcription confidence H — numbers verified from the paper text by the
# staging job; H. Li et al., "Pond: CXL-Based Memory Pooling Systems for
# Cloud Platforms", ASPLOS 2023, arXiv:2203.00241).
STAGED_QUOTE = (
    "emulating either 64ns or 140ns of additional memory access overheads "
    "over same-NUMA-node memory"
)
ANCHOR_L_NS = {"lower": Fraction(64), "upper": Fraction(140)}
FRACTION_WITHIN_GOALS = {"64ns": Fraction(43, 100), "140ns": Fraction(37, 100)}
WORKLOAD_POPULATION = 158
STAGED_CAVEAT = (
    "numbers are emulated additions, not a CXL product measurement — they "
    "bound plausible device latencies rather than measure one (staging doc, "
    "verbatim)"
)

# Plan/registry anchors for the placement statements.
REGISTRY_RANGE = (Fraction(10), Fraction(2000))    # A-L0-LAT free range
REGISTRY_POINT = Fraction(200)                     # A-L0-LAT registry value
PLAN_SPAN = (Fraction(10), Fraction(800))          # plan §2.1 anchored-axis span
#                                                       (~10 ns CAL-A9 lower,
#                                                        0.8 us CAL-A10 upper)
B_REGISTRY = Fraction(64)                          # A-L0-BW registry point (fixed)
RANKS = 8                                          # free smoke default
SMOKE_BYTES = 16384                                # 2^14; A-W1-SIZE registry point
LARGE_BYTES = 16777216                             # 2^24; A-W1-SIZE range upper
L_SWEPT = {
    "10": (Fraction(10), "A-L0-LAT registry free-range LOWER endpoint [10, 2000] (also numerically the plan's anchored-axis lower context, CAL-A9's ~10 ns/link — a different anchor's number, span context only)"),
    "64": (Fraction(64), "CAL-A8 LOWER emulated added-latency point (the stage's anchor point 1)"),
    "140": (Fraction(140), "CAL-A8 UPPER emulated added-latency point (the stage's anchor point 2)"),
    "200": (Fraction(200), "A-L0-LAT registry point (KEEP) — the sweep baseline every repo manifest inherits"),
    "800": (Fraction(800), "plan §2.1 anchored-axis UPPER endpoint context (CAL-A10 assumption-class 0.8 us — a different anchor's number, span context only)"),
    "2000": (Fraction(2000), "A-L0-LAT registry free-range UPPER endpoint — executed to show the range's upper half is anchor-free (plan NARROW-range-upper candidate context)"),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def infra_for(l_ns: Fraction) -> InfraConfig:
    return InfraConfig(
        topology_id=f"cal_a8_l{l_ns}",
        ranks=RANKS,
        link_bytes_per_ns=B_REGISTRY,
        hop_latency_ns=l_ns,
    )


def cct(l_ns: Fraction, payload: int) -> Fraction:
    return ring_allreduce_time_ns(payload, RANKS, infra_for(l_ns))


def latency_term(l_ns: Fraction) -> Fraction:
    return Fraction(2 * (RANKS - 1)) * l_ns


# ---------------------------------------------------------------------------
# 1. Anchor transcription
# ---------------------------------------------------------------------------
def anchor_transcription() -> dict:
    return {
        "staged_numbers": {
            "emulated_added_latency_ns": {
                "lower": str(ANCHOR_L_NS["lower"]),
                "upper": str(ANCHOR_L_NS["upper"]),
                "quote": STAGED_QUOTE,
                "status": "study INPUTS (injected in hardware), not device measurements",
            },
            "workload_goal_fractions": {
                "at_64ns": "43% of 158 workloads remain within performance goals",
                "at_140ns": "37% of 158 workloads remain within performance goals",
                "status": "the anchor's MEASURED outputs (production-trace-driven evaluation on cloud platforms)",
            },
            "population": WORKLOAD_POPULATION,
        },
        "emulation_caveat": STAGED_CAVEAT,
        "percentage_integrality_note": (
            "43% and 37% of 158 workloads are 67.94 and 58.46 workloads — "
            "non-integral, so exact compliant-workload counts are NOT "
            "reconstructible from the staged percentages (the paper rounds); "
            "the fractions are carried as staged percentages, never as counts"
        ),
        "confidence": "H (numbers verified from paper text by the staging job); arXiv copy open, ACM version paywalled",
    }


# ---------------------------------------------------------------------------
# 2. Latency-axis placement (the anchor's plan-assigned role)
# ---------------------------------------------------------------------------
def latency_axis_placement() -> dict:
    lo, hi = ANCHOR_L_NS["lower"], ANCHOR_L_NS["upper"]
    inside_range = all(REGISTRY_RANGE[0] <= v <= REGISTRY_RANGE[1] for v in (lo, hi))
    inside_span = all(PLAN_SPAN[0] <= v <= PLAN_SPAN[1] for v in (lo, hi))
    assert inside_range and inside_span
    return {
        "question": "where do CAL-A8's emulated added-latency points sit on the A-L0-LAT axis relative to the registry point, the registry free range, and the plan's anchored span?",
        "declared_reading": (
            "the anchor's per-memory-access ADDED latency is read onto the "
            "identity's per-hop latency L as per-traversal added latency "
            "beyond the serialization term — the same reading as the plan "
            "§2.1 A-L0-LAT row. Pond studies per-VM memory access over "
            "pooled CXL fabric (memory-semantic load/store); the L0 identity "
            "executes a collective over a ring — a DECLARED projection, "
            "recorded here, never claimed as an identity of quantities"
        ),
        "placements_exact": {
            "anchor_lower_64_over_registry_200": str(lo / REGISTRY_POINT),        # 8/25
            "anchor_upper_140_over_registry_200": str(hi / REGISTRY_POINT),       # 7/10
            "registry_200_over_anchor_lower_64": str(REGISTRY_POINT / lo),        # 25/8
            "registry_200_over_anchor_upper_140": str(REGISTRY_POINT / hi),       # 10/7
            "anchor_upper_over_lower": str(hi / lo),                              # 35/16
            "registry_range_upper_2000_over_plan_span_upper_800": str(REGISTRY_RANGE[1] / PLAN_SPAN[1]),  # 5/2
        },
        "placements_float": {
            "anchor_lower_64_over_registry_200": float(lo / REGISTRY_POINT),      # 0.32
            "anchor_upper_140_over_registry_200": float(hi / REGISTRY_POINT),     # 0.70
            "registry_200_over_anchor_upper_140": float(REGISTRY_POINT / hi),     # 1.4286
            "anchor_upper_over_lower": float(hi / lo),                            # 2.1875
        },
        "findings": [
            "BOTH anchor points sit INSIDE the A-L0-LAT registry free range [10, 2000] and INSIDE the plan §2.1 anchored axis span (~10-800 ns) — the arithmetic behind the plan's KEEP (point) verdict for the registry 200 ns, which lies between the anchor's upper point (140) and the span's upper endpoint (800)",
            "the registry point 200 ns sits +42.9% ABOVE the anchor's upper emulated point (200/140 = 10/7) and 3.125x above the lower point — the repo-wide latency default is MORE pessimistic than the anchor's entire emulated CXL-class band; a placement fact, the registry value is untouched",
            "the anchor's own emulated band is narrow: a x2.1875 step (64 -> 140 ns), an interior sub-band of the anchored span, NOT its endpoint — CAL-A8 bounds the CXL-class point's scale, not the span (whose endpoints belong to CAL-A9/CAL-A10)",
            "the registry free range's upper half is anchor-free: the 2000 ns endpoint is 2.5x above the plan's anchored-span upper endpoint (800 ns) — the placement fact behind the plan's NARROW-range-upper candidate; no range or value is changed here",
        ],
    }


# ---------------------------------------------------------------------------
# 3. CCT placement along the L axis (both regimes, executed rows)
# ---------------------------------------------------------------------------
def sweep_rows() -> dict:
    rows = {}
    for sweep_id in (SWEEP_ID_SMALL, SWEEP_ID_LARGE):
        table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
        for row in table["configs"]:
            topo = row["config_id"].split("-")[2]
            rows[(sweep_id, topo)] = row
    assert len(rows) == 12, len(rows)
    return rows


def cct_placement() -> tuple[dict, dict]:
    rows = sweep_rows()
    regimes = {
        SWEEP_ID_SMALL: ("small_message_latency_bound", SMOKE_BYTES, "16 KiB (2^14) — the A-W1-SIZE registry smoke point, the plan §1.2 latency-bound regime where the L axis is visible in O-CCT"),
        SWEEP_ID_LARGE: ("bandwidth_bound_contrast", LARGE_BYTES, "16 MiB (2^24) — the A-W1-SIZE registry range upper endpoint, where the anchor's axis disappears from O-CCT"),
    }
    executed = []
    for (sweep_id, topo), row in rows.items():
        regime, payload, note = regimes[sweep_id]
        l_str = topo.split("_l")[1].split("_")[0]
        l_ns = Fraction(l_str)
        # cross-check: the executed row equals the closed form of the same
        # identity function (exact Fraction string equality)
        assert row["o_cct"]["completion_time_ns_mean_exact"] == str(cct(l_ns, payload))
        t = cct(l_ns, payload)
        lat = latency_term(l_ns)
        executed.append(
            {
                "sweep_id": sweep_id,
                "regime": regime,
                "topology_id": topo,
                "L_ns": l_str,
                "payload_bytes": payload,
                "cct_ns_exact": str(t),
                "cct_ns_float": float(t),
                "latency_term_fraction_exact": str(lat / t),
                "latency_term_fraction_pct": float(lat / t * 100),
                "delta_vs_registry_baseline_exact": row["delta_vs_baseline"]["delta_exact"],
                "delta_vs_registry_baseline_pct": row["delta_vs_baseline"]["delta_float"] * 100,
                "provenance": L_SWEPT[l_str][1],
            }
        )

    # anchor-point readings in both regimes (exact)
    anchor_readings = {}
    for sweep_id, (regime, payload, _note) in regimes.items():
        t64, t140, t200 = (cct(v, payload) for v in (ANCHOR_L_NS["lower"], ANCHOR_L_NS["upper"], REGISTRY_POINT))
        anchor_readings[regime] = {
            "cct_at_anchor_lower_64_exact": str(t64),
            "cct_at_anchor_upper_140_exact": str(t140),
            "cct_at_registry_200_exact": str(t200),
            "anchor_lower_over_registry_exact": str(t64 / t200),      # 12/29
            "anchor_upper_over_registry_exact": str(t140 / t200),     # 43/58
            "registry_over_anchor_lower_exact": str(t200 / t64),      # 29/12
            "registry_over_anchor_upper_exact": str(t200 / t140),     # 58/43
            "anchor_step_cct_ratio_exact": str(t140 / t64),
            "anchor_step_cct_ratio_float": float(t140 / t64),
            "anchor_step_cct_pct": float((t140 / t64 - 1) * 100),
        }
    # exact spot values asserted (guard against typos in the findings text)
    assert anchor_readings["small_message_latency_bound"]["anchor_lower_over_registry_exact"] == "12/29"
    assert anchor_readings["small_message_latency_bound"]["anchor_upper_over_registry_exact"] == "43/58"
    assert anchor_readings["small_message_latency_bound"]["anchor_step_cct_ratio_exact"] == "43/24"
    assert anchor_readings["bandwidth_bound_contrast"]["anchor_step_cct_ratio_exact"] == "433/432"

    # whole-span effect per regime (the registered L range's total CCT move)
    span_effect = {}
    for sweep_id, (regime, payload, _note) in regimes.items():
        t_lo, t_hi = cct(REGISTRY_RANGE[0], payload), cct(REGISTRY_RANGE[1], payload)
        span_effect[regime] = {
            "whole_registered_span_cct_ratio_exact": str(t_hi / t_lo),
            "whole_registered_span_cct_ratio_float": float(t_hi / t_lo),
        }
    assert span_effect["small_message_latency_bound"]["whole_registered_span_cct_ratio_float"] > 48
    assert span_effect["bandwidth_bound_contrast"]["whole_registered_span_cct_ratio_float"] < 1.07

    placement = {
        "regimes": {r: note for r, _p, note in regimes.values()},
        "fixed_parameters": {
            "B_bytes_per_ns": str(B_REGISTRY),
            "B_provenance": "A-L0-BW registry point, kept FIXED (the anchor says nothing about bandwidth; this stage sweeps only L)",
            "ranks": RANKS,
            "ranks_provenance": "the free smoke default — the anchor stages no rank count, no collective, no message size (declared model-side choice, never an anchor-derived number)",
        },
        "executed_rows": executed,
        "anchor_point_readings": anchor_readings,
        "whole_span_effect": span_effect,
        "latency_share_at_anchor_points": (
            "in the 16 KiB regime the hop-latency term is 66.7% (L=64) / 81.4% "
            "(L=140) / 86.2% (L=200) of CCT — the anchor's ns scale dominates "
            "small-message CCT exactly where the anchor shows it to be a "
            "first-order production concern (57-63% of workloads outside goals); "
            "in the 16 MiB regime the same term is 0.20% (L=64) / 0.43% (L=140) "
            "/ 0.61% (L=200) — the anchor's axis is invisible in O-CCT there"
        ),
        "punchline": (
            "the anchor's own x2.1875 latency step (64 -> 140 ns) moves the "
            "model's 16 KiB CCT by x2.0476 (+104.8%) but its 16 MiB CCT by only "
            "+0.231% — the CXL-class latency points CAL-A8 contributes can only "
            "ever be seen by O-CCT in the small-message regime, and the whole "
            "registered L range [10, 2000] spans a x48.4 CCT effect at 16 KiB "
            "vs a +6.1% effect at 16 MiB"
        ),
    }
    return placement, {"executed_coverage_note": "all 12 grid cells (6 L x 2 regimes) were executed by the two sweeps; the record contains no closed-form-only rows — every number above is backed by a sweep row or store run cross-checked by exact Fraction string equality"}


# ---------------------------------------------------------------------------
# 4. The tolerance-fraction blindness (the anchor's measured output)
# ---------------------------------------------------------------------------
def tolerance_fraction_blindness() -> dict:
    """The anchor's MEASURED outputs (43%/37% of 158 workloads within
    performance goals) are population fractions over heterogeneous
    production workloads. The L0 input space carries no population and no
    performance-goal axis, and its response to L is exactly affine and
    homogeneous — the population CDF the anchor measures is inexpressible,
    not merely mispredicted. Minimized and classified per handoff rule 5."""
    # (a) input-space enumeration against the landed dataclasses
    infra_fields = {f.name for f in dataclasses.fields(InfraConfig)}
    expected_infra = {"topology_id", "ranks", "link_bytes_per_ns", "hop_latency_ns"}
    assert infra_fields == expected_infra, infra_fields
    w1_fields = {f.name for f in dataclasses.fields(w1.W1Config)}
    expected_w1 = {"tp_size", "layers", "steps", "allreduce_bytes", "model_name"}
    assert w1_fields == expected_w1, w1_fields
    obs_ids = set(registered_observables())
    expected_obs = {"O-CCT", "O-CONSERVATION", "O-CCT-RELERR", "O-TRAFFIC-IMBALANCE"}
    assert obs_ids == expected_obs, obs_ids

    # (b) live demonstration, part 1: workload LABELS do not exist in the
    # input space — two configs differing only in model_name produce
    # identical exact per-op completions through the landed execute()
    wl_a = w1.W1Config(tp_size=RANKS, layers=2, steps=3, allreduce_bytes=SMOKE_BYTES, model_name="pond_workload_a")
    wl_b = w1.W1Config(tp_size=RANKS, layers=2, steps=3, allreduce_bytes=SMOKE_BYTES, model_name="pond_workload_b")
    out_a = l0_execute(w1.generate_w1_ops(wl_a), infra_for(ANCHOR_L_NS["lower"]))
    out_b = l0_execute(w1.generate_w1_ops(wl_b), infra_for(ANCHOR_L_NS["lower"]))
    per_op_a = [op["completion_time_ns_exact"] for op in out_a["per_op"]]
    per_op_b = [op["completion_time_ns_exact"] for op in out_b["per_op"]]
    assert per_op_a == per_op_b

    # (c) live demonstration, part 2: at fixed (B, L, r) the ONLY workload
    # axis that moves output is the payload size (M) — two workloads with
    # equal M cannot differ AT ALL, so goal-compliance ordering is undefined
    t_small = cct(ANCHOR_L_NS["lower"], SMOKE_BYTES)
    t_large = cct(ANCHOR_L_NS["lower"], LARGE_BYTES)
    assert t_large > t_small

    # (d) the homogeneous-response fact, verified exactly: the identity is
    # affine in L with slope 2*(r-1), IDENTICAL for every payload/regime
    slope = Fraction(2 * (RANKS - 1))
    for payload in (SMOKE_BYTES, LARGE_BYTES):
        for l1, l2 in ((Fraction(10), Fraction(64)), (ANCHOR_L_NS["lower"], ANCHOR_L_NS["upper"]), (Fraction(800), Fraction(2000))):
            assert cct(l2, payload) - cct(l1, payload) == slope * (l2 - l1)

    # (e) the anchor's heterogeneous population response, transcribed
    f64, f140 = FRACTION_WITHIN_GOALS["64ns"], FRACTION_WITHIN_GOALS["140ns"]
    pp_drop = f64 - f140                      # 6 percentage points = 3/50
    relative_drop = (f64 - f140) / f64        # 6/43
    outside_goals = {
        "at_64ns": str(Fraction(1) - f64),    # 57%
        "at_140ns": str(Fraction(1) - f140),  # 63%
    }

    return {
        "anchor_measured_output": {
            "at_64ns": "43% of 158 workloads within performance goals (57% outside)",
            "at_140ns": "37% of 158 workloads within performance goals (63% outside)",
            "population_step": "a x2.1875 added-latency step moves the compliant fraction by -6 percentage points (-13.95% relative) — a shallow heterogeneous population CDF",
        },
        "input_space_enumeration": {
            "infra_config_fields": sorted(infra_fields),
            "w1_config_fields": sorted(w1_fields),
            "observables_registry": sorted(obs_ids),
            "finding": "no population parameter, no per-workload performance-goal parameter, and no SLO/goal observable exists anywhere in the input space or the registry — the quantity 'fraction of workloads within performance goals' has NO OPERAND in the model: it is undefined, not merely mispredicted",
        },
        "demonstrations": {
            "labels_do_not_exist": "two W1 configs differing only in model_name (pond_workload_a/b) executed through the landed l0.execute at the anchor point L=64: per-op exact completions IDENTICAL (exact Fraction string equality, verified while building this record)",
            "only_M_moves_output": "at fixed (B=64, L=64, r=8) the 16 KiB and 16 MiB workloads differ only through payload M (CCT strictly increasing in M); two workloads with equal M cannot differ at all — no axis exists along which the anchor's 158-workload heterogeneity could be encoded",
            "homogeneous_affine_response": "verified EXACTLY: cct(L2) - cct(L1) == 2*(r-1)*(L2-L1) for every payload and every swept L pair — every workload of a given shape responds to L with the IDENTICAL slope 14 ns/ns; the anchor measures 57-63% of workloads responding differently enough to leave their performance goals",
        },
        "quantified_contrast": {
            "anchor_population_step_pp_exact": str(pp_drop),          # 3/50
            "anchor_population_step_relative_exact": str(relative_drop),  # 6/43
            "model_step_at_16kib_exact": "43/24 (+104.76% — every workload, identically)",
            "model_step_at_16mib_exact": "433/432 (+0.23% — every workload, identically)",
            "outside_goals_fractions": outside_goals,
        },
        "classification_per_handoff_rule_5": {
            "minimized_counterexample": "CAL-A8's measured outputs are population fractions over 158 heterogeneous production workloads at fixed added latency; the L0 input space {topology_id, ranks, B, L} x {tp_size, layers, steps, allreduce_bytes, model_name(label)} admits NO population and NO goal axis, and its CCT response to L is exactly affine and homogeneous — the population CDF is INEXPRESSIBLE by any (B, L, M, r) setting",
            "class": "STRUCTURAL (population/SLO-axis blindness), not a parameter mismatch — the same class as A5's twist blindness and A6's software-version blindness, on the workload axis; it cannot be absorbed as noise because no comparable model quantity exists to attach noise TO",
            "refinement": "owner decision, out of this stage's scope: expressing workload populations with per-workload goals (and a compliance observable) is a NEW modeling layer, not a parameter of any landed identity",
            "consistency_note_not_a_match": "direction-consistent context only: the anchor shows the ns-scale added-latency band is a first-order production concern (a majority of workloads outside goals at 64-140 ns), and the model's small-message CCT is 66.7-81.4% latency-term at exactly those points — both say the CXL-class scale MATTERS; neither says the model predicts the anchor",
        },
    }


# ---------------------------------------------------------------------------
# 5. Inextractable targets (FAIL-clause honesty duty)
# ---------------------------------------------------------------------------
def inextractable_targets() -> list[dict]:
    return [
        {
            "target": "the workload-goal fractions (43%/37% of 158) as a calibration target",
            "reason": "no population/SLO axis exists in the L0 input space and no goal observable exists in the registry — the fraction has no model operand (quantified structurally in tolerance_fraction_blindness); recorded and classified, never smoothed",
        },
        {
            "target": "the 158 production workload traces and their performance-goal definitions",
            "reason": "not staged (only the fractions are); additionally 43%/37% of 158 are non-integral (67.94/58.46), so even compliant counts are not reconstructible from the staged percentages",
        },
        {
            "target": "absolute CXL device / fabric latency",
            "reason": "the anchor stages ADDED latency over a same-NUMA-node baseline whose value is not staged — no absolute device latency is reconstructible; the axis points are emulated additions that BOUND plausible device latency (the staging doc's own caveat), so every placement statement here reads 'bounds', never 'measures'",
        },
        {
            "target": "rank count / topology / message size for a regime-faithful rerun",
            "reason": "the anchor is per-VM memory access (memory-semantic, load/store), not a collective — it stages no collective, rank count, or message size; this stage's r=8, 16 KiB/16 MiB, ring choices are DECLARED model-side regime choices (smoke defaults / registry endpoints), never anchor-derived",
        },
        {
            "target": "CXL link/switch latency decomposition",
            "reason": "that is CAL-A9's anchor (a different row: ~10 ns/link, ~70 ns/switch design estimates) — cited here only as the plan's span context; the ASTRA-sim side is covered by A-AS1-NO-EXPANSION (no anchor speaks to expansion config)",
        },
    ]


# ---------------------------------------------------------------------------
# 6. Store-run cross-checks
# ---------------------------------------------------------------------------
def run_checks() -> list[dict]:
    checks = []
    for run_id, l_key in ((RUN_ID_L64, "lower"), (RUN_ID_L140, "upper")):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        per_op = obs["per_op"][0]
        assert per_op["payload_bytes"] == SMOKE_BYTES
        assert obs["model"]["ranks"] == RANKS
        assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == B_REGISTRY
        assert Fraction(obs["model"]["hop_latency_ns_exact"]) == ANCHOR_L_NS[l_key]
        assert per_op["completion_time_ns_exact"] == str(cct(ANCHOR_L_NS[l_key], SMOKE_BYTES))
        checks.append(
            {
                "run_id": run_id,
                "mapping": f"anchor point: CAL-A8's {'lower (64 ns)' if l_key == 'lower' else 'upper (140 ns)'} emulated added-latency point on the ring at B=64 B/ns, r=8, 16 KiB",
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
# 7. Divisibility-gate acceptance
# ---------------------------------------------------------------------------
def div_gate_acceptance() -> dict:
    for payload in (SMOKE_BYTES, LARGE_BYTES):
        require_divisible(BACKEND_ID, "cal_a8_probe", payload, RANKS, "A-L0-DIV")
    return {
        "finding": "both stage payloads (2^14 and 2^24) are divisible by r = 8 = 2^3, so the A-L0-DIV gate ACCEPTS both regime sizes exactly — no bracketing",
        "contrast": "the mirror of stage A3 (r = 72 = 8*9 rejected every power of two); no anchor regime is bracketed anywhere in this stage",
    }


def main() -> int:
    transcription = anchor_transcription()
    placement_l = latency_axis_placement()
    placement_c, coverage = cct_placement()
    blindness = tolerance_fraction_blindness()
    inextractable = inextractable_targets()
    runs = run_checks()
    gate = div_gate_acceptance()

    lo, hi = ANCHOR_L_NS["lower"], ANCHOR_L_NS["upper"]
    deviation_summary = (
        "CAL-A8 pins no completion time, so no CCT deviation exists; the anchor's "
        "three plan-assigned deviations are: (1) LATENCY-AXIS PLACEMENT — both "
        f"emulated points sit INSIDE the registry free range [10, 2000] and the "
        f"plan's anchored span (~10-800 ns), at 32.0%/70.0% of the registry point "
        f"200 ns, which itself sits +42.9% ABOVE the anchor's upper point "
        f"(200/140 = 10/7; a placement fact, the registry value untouched), while "
        "the free range's anchor-free upper half (2000 vs 800 ns, ratio 5/2) is "
        "the placement fact behind the plan's NARROW-range-upper candidate; "
        "(2) CCT SENSITIVITY — at the anchor points the 16 KiB smoke-regime CCT "
        "sits -58.62%/-25.86% below the registry default (1344/2408 vs 3248 ns; "
        "latency shares 66.7%/81.4%), the anchor's own x2.1875 step moves 16 KiB "
        "CCT x2.0476 but 16 MiB CCT only +0.231%, and the whole registered L "
        "range spans x48.4 at 16 KiB vs +6.1% at 16 MiB — the anchor's axis is "
        "visible ONLY in the small-message regime; (3) the TOLERANCE FRACTIONS "
        "(43%/37% of 158 workloads) are STRUCTURALLY INEXPRESSIBLE — no "
        "population/SLO axis or goal observable exists in the input space "
        "(enumerated; labels demonstrated inert, only M moves output), and the "
        "identity's response to L is exactly affine with slope 14 ns/ns "
        "identical for every workload, against the anchor's shallow "
        "heterogeneous population CDF (-6 pp over the same step) — classified "
        "per handoff rule 5, never tuned, never smoothed"
    )

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A8 (anchor CAL-A8)",
        "anchor": {
            "anchor_id": "CAL-A8",
            "title": "Pond (ASPLOS 2023): CXL added-latency tolerance emulation",
            "source_row": "the anchor registry row CAL-A8 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A8",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A8 (cannot calibrate O-CCT; locates the CXL-class point on the latency axis for L parameters only)",
            "url": "https://arxiv.org/abs/2203.00241",
            "confidence": "H (numbers verified from paper text by the staging job); the staged numbers are emulated study inputs bounding plausible CXL device latency, not device measurements",
            "transcription": transcription,
        },
        "target": {
            "role": "latency_axis_anchor_for_L_parameters",
            "regime": {
                "message_bytes": None,
                "message_regime": "n/a staged (per-memory-access added latency); model side DECLARED as the 16 KiB smoke small-message regime (where the L axis is visible in O-CCT) plus the 16 MiB bandwidth-bound contrast (where it is not)",
                "ranks": None,
                "ranks_note": "anchor stages no rank count; r=8 is the free smoke default",
                "topology_class": "memory-semantic (load/store) pooling fabric; projected onto the unidirectional ring — a DECLARED projection, never an identity of quantities",
            },
            "inextractable_targets": inextractable,
        },
        "model": {
            "backend_id": BACKEND_ID,
            "identity": "t(M, r) = 2*(r-1)/r*M/B + 2*(r-1)*L; per-rank wire bytes 2*(r-1)/r*M (see src/essun/backends/analytical/l0.py)",
            "ranks": RANKS,
            "free_parameters": {
                "L_swept_ns": {k: v[1] for k, v in L_SWEPT.items()},
                "B_fixed_bytes_per_ns": str(B_REGISTRY),
                "B_provenance": "A-L0-BW registry point, FIXED — the anchor says nothing about bandwidth (the mirror of stages A4/A5/A6, which swept B at fixed L=200)",
                "payloads_bytes": [SMOKE_BYTES, LARGE_BYTES],
                "payloads_provenance": "registry smoke point (16 KiB) and registry range upper endpoint (16 MiB) — declared model-side regime choices, the anchor stages no size",
            },
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV (experiments/vertical_slice/assumptions_l0.yaml)",
            "closed_form_coverage": coverage["executed_coverage_note"],
        },
        "comparison": {
            "latency_axis_placement": placement_l,
            "cct_placement": placement_c,
            "tolerance_fraction_blindness": blindness,
            "divisibility_gate": gate,
            "anchor_point_runs": runs,
        },
        "deviation": {
            "summary": deviation_summary,
            "not_tuned": "nothing was tuned: the L span was fixed by registry/anchor/plan arithmetic BEFORE any stage output was read; B, r, and both payload sizes are registry defaults/endpoints, never anchor-derived; the anchor's measured outputs (population fractions) are classified structurally inexpressible, and its emulated inputs are recorded as bounds on device latency, never as measurements — no registry value, range, manifest parameter, or claim was changed",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external published emulation study; no E3/E4 language — CAL-A8 is not our testbed, and the owner's adjudication precedes any label move",
        },
        "backing": {
            "run_ids": [RUN_ID_L64, RUN_ID_L140],
            "sweep_ids": [SWEEP_ID_SMALL, SWEEP_ID_LARGE],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_SMALL}", f"results/sweeps/{SWEEP_ID_LARGE}"],
            "run_backed_numbers": "every run-path-executed number (12 sweep configs, 2 store runs); all grid cells executed — no closed-form-only rows exist in this stage",
            "inputs": [
                "experiments/calibration/a8/sweep_a8_laxis_small_v1.yaml",
                "experiments/calibration/a8/sweep_a8_laxis_large_v1.yaml",
                "experiments/calibration/a8/run_a8_anchor64_v1.yaml",
                "experiments/calibration/a8/run_a8_anchor140_v1.yaml",
                "experiments/calibration/a8/workloads/ (2 files)",
                "experiments/calibration/a8/topologies/ (6 files)",
                "experiments/calibration/a8/profiles/implementation_profile_l0_ring_cal_a8_v1.yaml",
            ],
            "reproduce": "make run EXP=experiments/calibration/a8/run_a8_anchor64_v1.yaml ; "
            "make run EXP=experiments/calibration/a8/run_a8_anchor140_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a8/sweep_a8_laxis_small_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a8/sweep_a8_laxis_large_v1.yaml ; "
            ".venv/bin/python experiments/calibration/a8/build_calibration_record.py",
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
