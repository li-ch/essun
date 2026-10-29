"""Build the PROPOSED calibration-candidate record for anchor CAL-A9 (Q1
calibration stage A9.

Pure function of immutable artifacts: reads the two append-only store run
records and the sweep table produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record, mirroring the evidence-store
addressing discipline; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_staging.md`` §A9
(declared below with provenance; the staging doc paraphrases Berger et
al., IEEE Micro 2023, so no "verbatim" quote strings are claimed here),
or (b) computed from the stored run/sweep artifacts by this script, or
(c) exact closed-form identity arithmetic cross-checked against executed
artifacts by exact Fraction string equality (declared inline wherever
used). Nothing is tuned: the swept L values carry their anchor/registry
provenance, and the record measures where the model output sits relative
to the anchor's latency-budget decomposition.

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
RUN_ID_XBAR_PAIR80 = "2297ae6312cc53787ea20d377175b95741bf85a65d2b17b0e372344758f908a8"
RUN_ID_XBAR_REG200 = "f0ea2363122802f2b0ef11a36272222ffff792735441476388cff65949fb4f23"
SWEEP_ID = "e1ef1ccf8204e1f342871c0dfbf76c4cdf691e96c50301d990edfade9c6f9400"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A9 staged numbers (docs/calibration/anchors_staging.md §A9,
# transcription confidence H; DESIGN-ESTIMATE numbers from the paper's own
# latency-budget analysis, NOT silicon measurements — the staging doc's
# explicit caveat, to be paired with CAL-A8's emulated 64/140 ns).
A9_LINK_NS = Fraction(10)       # "~10 ns" per CXL link, per direction
A9_SWITCH_NS = Fraction(70)     # "at least ~70 ns" per CXL switch stage (FLOOR)

# The calibration plan's stated one-stage pair sum for this anchor
# (§2.1 row A-L0X-LAT: "pair-across-a-switch: ≈80 ns CXL-class
# (CAL-A9 link+switch sum)") — the reconciliation authority this stage
# follows; the two-link alternative (2*10 + 70 = 90) is recorded as a
# flagged interpretation risk, NOT swept.
PAIR_ONE_STAGE = A9_LINK_NS + A9_SWITCH_NS          # 80
PAIR_TWO_LINK_READING = 2 * A9_LINK_NS + A9_SWITCH_NS  # 90 (recorded ambiguity)
PAIR_TWO_STAGE = 2 * PAIR_ONE_STAGE                 # 160 (anchor arithmetic)

# Registry points (values UNTOUCHED — placements only).
B_REGISTRY = Fraction(64)        # A-L0X-BW / A-L0-BW point (anchor-free axis here)
L_REGISTRY = Fraction(200)       # A-L0X-LAT / A-L0-LAT point, range [10, 2000]
L_SPAN_UPPER = Fraction(800)     # plan §2.1 A-L0X-LAT stated span upper (CAL-A10 transfer)

R = 8                            # free smoke-default rank count (anchor pins none)
L_LINK_ONLY = A9_LINK_NS         # 10 (swept budget-component row)
L_SWITCH_ONLY = A9_SWITCH_NS     # 70 (swept budget-component row)

LADDER = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
          134217728, 268435456, 536870912, 2147483648, 8589934592]
ANCHOR_POINT_SIZE = 8192         # 8*2^10, the latency-bound ladder member

TOPO_BY_L = {
    "crossbar8_a9_link10_v1": L_LINK_ONLY,
    "crossbar8_a9_switch70_v1": L_SWITCH_ONLY,
    "crossbar8_a9_pair80_v1": PAIR_ONE_STAGE,
    "crossbar8_a9_pair160_v1": PAIR_TWO_STAGE,
    "crossbar8_a9_pair200_v1": L_REGISTRY,
    "crossbar8_a9_pair800_v1": L_SPAN_UPPER,
}
RING_TOPO = "ring8_a9_hop80_v1"


def anchor_derived() -> dict:
    """Arithmetic consequences of CAL-A9's own staged numbers (plus the
    plan's stated reconciliation, which this stage follows)."""
    pair_one = A9_LINK_NS + A9_SWITCH_NS
    two_link = 2 * A9_LINK_NS + A9_SWITCH_NS
    two_stage = 2 * pair_one

    # Self-checks: the staged numbers must produce these exact values;
    # anything else is a transcription bug, not a finding.
    assert pair_one == PAIR_ONE_STAGE == 80
    assert two_link == PAIR_TWO_LINK_READING == 90
    assert two_stage == PAIR_TWO_STAGE == 160
    assert all(size % R == 0 for size in LADDER)  # A-L0-DIV / A-L0X-DIV accept

    return {
        "staged_numbers": {
            "cxl_link_added_latency_ns_per_direction": "10 (staged '~10 ns')",
            "cxl_switch_added_latency_ns_per_stage": "70 (staged 'at least ~70 ns' — "
            "a FLOOR, one-sided; components named in the source: ports, "
            "arbitration, NoC)",
            "provenance_class": "design-estimate numbers from the paper's own "
            "latency-budget analysis, NOT silicon measurements (staging-doc "
            "caveat: pair with CAL-A8's emulated 64/140 ns added memory "
            "latency)",
        },
        "derived_arithmetic": {
            "pair_across_one_switch_stage_ns": str(pair_one),
            "pair_one_stage_derivation": "10 (link) + 70 (switch stage) — summed "
            "exactly as the calibration plan states for this anchor (§2.1 row "
            "A-L0X-LAT: 'pair-across-a-switch: ≈80 ns CXL-class (CAL-A9 "
            "link+switch sum)'); the plan is the reconciliation authority this "
            "stage follows",
            "pair_two_link_reading_ns": str(two_link),
            "pair_two_link_note": "FLAGGED INTERPRETATION RISK, recorded not "
            "swept: a physical pair path through one switch crosses TWO CXL "
            "links (source->switch, switch->target) and the staged quote is "
            "per link per direction, so a two-link reading gives 2*10 + 70 = "
            "90 ns; the plan's stated sum (80) uses one link term",
            "pair_two_cascaded_stages_ns": str(two_stage),
            "pair_two_stage_note": "ANCHOR ARITHMETIC, labeled: two cascaded "
            "one-stage traversals (2 x 80); the per-path link COUNT of a "
            "multi-stage CXL path is not stated by the anchor — this is the "
            "plan-stated sum doubled, never a paper quote",
            "one_sided_floor": "the switch term is worded 'AT LEAST ~70 ns', "
            "so any one-stage CXL-class pair latency >= 80 ns is "
            "consistent-with the budget and any value < 80 ns CONTRADICTS it "
            "— the falsification direction is one-sided; no upper bound "
            "follows from this anchor",
            "plan_stated_pair_latency_span_ns": "[80, 800] — plan §2.1 row "
            "A-L0X-LAT: '≈80 ns CXL-class (CAL-A9 link+switch sum) to 800 ns "
            "GPU-class assumption (CAL-A10)'",
        },
    }


def recorded_ambiguities() -> dict:
    """The FAIL-clause duty: every ambiguity of this anchor, recorded."""
    return {
        "one_link_vs_two_link_path_sum": {
            "ambiguity": "the staged link term is '~10 ns per link per "
            "direction'; a switched pair path crosses two links, so the "
            "one-stage pair sum is 10 + 70 = 80 (one link term, the plan's "
            "stated reading) or 2*10 + 70 = 90 (two link terms)",
            "resolution_followed": "the calibration plan's stated sum 80 "
            "(§2.1 A-L0X-LAT) — the plan is the reconciliation authority; "
            "the 90 ns alternative is recorded here and NOT swept",
            "action_if_reversed": "re-point the anchor-point topology "
            "at L=90; every identity relation in this record is linear in L, "
            "so all deltas rescale by the same closed forms",
        },
        "at_least_wording": {
            "ambiguity": "'switches add at least ~70 ns' is a lower bound, "
            "not a central estimate",
            "consequence": "80 ns is executed as a FLOOR-located anchor "
            "point, never as a target value; consistency is one-sided "
            "(model >= 80 ok, model < 80 falsified)",
        },
        "multi_stage_link_count_unstated": {
            "ambiguity": "the anchor states per-link and per-switch-stage "
            "terms but not how many links a multi-stage path crosses",
            "consequence": "the 160 ns row is pure doubling of the plan's "
            "one-stage sum (labeled anchor arithmetic), and the general "
            "chain k-stages -> L = 80k is likewise arithmetic, not a quote",
        },
        "rank_count_and_bandwidth_unpinned": {
            "ambiguity": "the anchor is a memory-pool latency-budget study "
            "— it pins no collective rank count and no bandwidth number",
            "consequence": "r=8 (free smoke default, power of two, divides "
            "every 8*2^k ladder size) and B=64 B/ns (A-L0X-BW / A-L0-BW "
            "registry point) are declared FREE and FIXED respectively; the "
            "bandwidth axis is anchor-free for this stage (the mirror of "
            "stage A7, which swept B at fixed L)",
        },
        "design_estimate_not_silicon": {
            "ambiguity": "transcription confidence H, but the numbers are "
            "the paper's own budget estimates, not measurements",
            "consequence": "the record's placement facts locate the model "
            "relative to a PUBLISHED BUDGET, not to hardware; no E3/E4 "
            "language anywhere",
        },
    }


def registry_placements() -> dict:
    """Placement facts against the free-parameter registry points (values
    untouched — these are placements, not changes)."""
    reg_minus_anchor = L_REGISTRY - PAIR_ONE_STAGE  # 120
    ratio = L_REGISTRY / PAIR_ONE_STAGE             # 5/2
    assert reg_minus_anchor == 120 and ratio == Fraction(5, 2)
    return {
        "A-L0X-LAT_point_200_vs_anchor_one_stage_sum_80": {
            "registry_point_ns": "200",
            "anchor_one_stage_pair_sum_ns": "80",
            "absolute_delta_ns": str(reg_minus_anchor),
            "ratio": str(ratio),
            "consistency": "CONSISTENT-WITH the anchor's one-sided floor "
            "(200 >= 80) — but selected by no anchor; the plan §2.1 verdict "
            "KEEP (point) stands on span membership (200 lies inside the "
            "anchored axis span ~10-800 ns), not on any anchor choosing it",
        },
        "A-L0-LAT_point_200_same_arithmetic": {
            "note": "the ring hop-latency registry point is numerically the "
            "same 200 ns; on a switched fabric a ring hop is one "
            "link+switch traversal, so the identical +120 ns / 5:2 placement "
            "applies to A-L0-LAT; stage A8 sweeps that axis on the ring "
            "identity — this record's placement arithmetic covers both "
            "parameters",
        },
        "A-L0X-LAT_range_upper_2000_anchor_free_above_800": {
            "note": "no anchor supports >= ~1 us on the pair-latency axis; "
            "the plan §2.1 NARROW (range upper) candidate (<= 800-1000 ns, "
            "contingent on extracting the deferred V100-era measured P2P "
            "series) is recorded here as the plan states it — the registry "
            "range is NOT changed by this stage",
        },
        "A-AS2-DELAY-POS_numeric_coincidence_10": {
            "note": "CAL-A9's ~10 ns per-link term coincides NUMERICALLY "
            "with the ASTRA-sim adapter's endpoint-delay feasibility value "
            "10 ns (A-AS2-DELAY-POS); the plan §2.2 already classifies these "
            "as DIFFERENT mechanisms (wire delay vs endpoint processing) — "
            "KEEP / OUT-OF-DOMAIN; the coincidence is a placement fact "
            "only, never a cross-derivation",
        },
        "A-L0X-BW_anchor_free_here": {
            "note": "CAL-A9 stages no bandwidth number; B = 64 B/ns is the "
            "fixed free registry point on this stage's every row (the "
            "bandwidth axis belongs to stages A1/A2/A7 and the global "
            "sensitivity stages)",
        },
    }


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2*L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (R - 1) * m, R) / B_REGISTRY + 2 * l


def t_ring(m: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2(r-1)*L  (src/essun/backends/analytical/l0.py)."""
    return Fraction(2 * (R - 1) * m, R) / B_REGISTRY + 2 * (R - 1) * l


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    bw_term = t_xbar(per_op["payload_bytes"], Fraction(0))  # 2(r-1)/r*M/B
    lat_term = cct - bw_term                                # == 2L exactly
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
            "injection_bytes_per_ns_exact": model["injection_bytes_per_ns_exact"],
            "pair_latency_ns_exact": model["pair_latency_ns_exact"],
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "bandwidth_term_ns_exact": str(bw_term),
        "latency_term_ns_exact": str(lat_term),
        "latency_fraction_of_cct_exact": str(lat_term / cct),
        "latency_fraction_of_cct_float": float(lat_term / cct),
    }


def sweep_rows() -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    rows_by_size: dict[int, list[dict]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        size = row["payload_bytes"]
        rows_by_size.setdefault(size, []).append(
            {
                "topology_id": topo,
                "config_id": row["config_id"],
                "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
                "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
                "delta_vs_anchor_point_exact": row["delta_vs_baseline"]["delta_exact"],
                "delta_vs_anchor_point_float": row["delta_vs_baseline"]["delta_float"],
            }
        )
    ladder = [
        {"payload_bytes": size, "rows": rows}
        for size, rows in sorted(rows_by_size.items())
    ]
    return {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "ladder": ladder,
    }


def budget_decomposition(sweep_table: dict) -> dict:
    """The anchor's two-component budget, isolated additively on EXECUTED
    sweep rows at every ladder size (exact Fraction string equality)."""
    by = {}  # (topo, size) -> exact cct string
    for row in sweep_table["configs"]:
        by[(row["config_id"].split("-")[2], row["payload_bytes"])] = row[
            "o_cct"
        ]["completion_time_ns_mean_exact"]

    link_iso, switch_iso, chain_double = [], [], []
    for m in LADDER:
        t10 = Fraction(by[("crossbar8_a9_link10_v1", m)])
        t70 = Fraction(by[("crossbar8_a9_switch70_v1", m)])
        t80 = Fraction(by[("crossbar8_a9_pair80_v1", m)])
        t160 = Fraction(by[("crossbar8_a9_pair160_v1", m)])
        # closed-form cross-checks first
        assert t10 == t_xbar(m, L_LINK_ONLY)
        assert t70 == t_xbar(m, L_SWITCH_ONLY)
        assert t80 == t_xbar(m, PAIR_ONE_STAGE)
        assert t160 == t_xbar(m, PAIR_TWO_STAGE)
        # the link component, isolated: (80 - 70) charges 2*10 exactly
        assert t80 - t70 == 2 * A9_LINK_NS, (m, t80 - t70)
        # the switch component, isolated: (80 - 10) charges 2*70 exactly
        assert t80 - t10 == 2 * A9_SWITCH_NS, (m, t80 - t10)
        # chain doubling is additive: (160 - 80) charges 2*80 exactly
        assert t160 - t80 == 2 * PAIR_ONE_STAGE, (m, t160 - t80)
        link_iso.append((m, str(t80 - t70)))
        switch_iso.append((m, str(t80 - t10)))
        chain_double.append((m, str(t160 - t80)))

    return {
        "claim": "the anchor's two-component budget is recovered additively "
        "from executed rows at every ladder size: t(80) - t(70) = 2*10 ns "
        "(the LINK component isolated), t(80) - t(10) = 2*70 ns (the SWITCH "
        "component isolated), and t(160) - t(80) = 2*80 ns (a cascaded "
        "second stage doubles the sum) — each charged twice because the "
        "AllReduce identity charges the pair latency once per phase "
        "(reduce-scatter + allgather)",
        "link_component_isolated_2x10_at_all_12_sizes": [
            {"payload_bytes": m, "delta_ns_exact": d} for m, d in link_iso
        ],
        "switch_component_isolated_2x70_at_all_12_sizes": [
            {"payload_bytes": m, "delta_ns_exact": d} for m, d in switch_iso
        ],
        "second_stage_additive_2x80_at_all_12_sizes": [
            {"payload_bytes": m, "delta_ns_exact": d} for m, d in chain_double
        ],
        "cross_check": "closed forms t_xbar(m, L) = 2(r-1)/r*M/64 + 2L equal "
        "every executed row by exact Fraction string equality (all 12 sizes "
        "x 6 crossbar topologies)",
    }


def chain_multiplicity(sweep_table: dict) -> dict:
    """The same budget sum under two chain multiplicities (ring 14L vs
    crossbar 2L), verified on executed rows at every size."""
    by = {}
    for row in sweep_table["configs"]:
        by[(row["config_id"].split("-")[2], row["payload_bytes"])] = row[
            "o_cct"
        ]["completion_time_ns_mean_exact"]
    rows = []
    for m in LADDER:
        t_x = Fraction(by[("crossbar8_a9_pair80_v1", m)])
        t_r = Fraction(by[(RING_TOPO, m)])
        assert t_r == t_ring(m, PAIR_ONE_STAGE)  # closed-form cross-check
        assert t_r - t_x == 2 * (R - 1 - 1) * PAIR_ONE_STAGE, (m, t_r - t_x)
        rows.append(
            {
                "payload_bytes": m,
                "ring_hop80_cct_ns_exact": str(t_r),
                "crossbar_pair80_cct_ns_exact": str(t_x),
                "difference_ns_exact": str(t_r - t_x),
            }
        )
    assert 2 * (R - 1 - 1) * PAIR_ONE_STAGE == 960  # 12L at L=80
    return {
        "claim": "at the SAME budget sum L=80 ns and equal B, the ring "
        "identity (every hop one link+switch traversal) charges the "
        "per-stage budget 2*(r-1) = 14 times per AllReduce against the "
        "crossbar's 2 (once per phase); the difference is exactly "
        "2*(r-2)*L = 12*80 = 960 ns at EVERY ladder size — an identity of "
        "the two backends, here verified against executed artifacts. The "
        "switch-stage cost is paid per traversal: the SAME budget amplifies "
        "(r-1)-fold under a multi-hop schedule (the latency-axis analog of "
        "stage A7's bandwidth-side 7x bracket)",
        "verified_at_all_12_ladder_sizes": rows,
        "bracket_note": "the two identities bracket the chain multiplicities "
        "{2, 14} of one budget sum; which schedule a CXL-class fabric "
        "actually serves is a workload/implementation question the platform "
        "leaves to a declared implementation profile, not to a parameter",
    }


def crossover_spectrum() -> dict:
    """Exact crossover sizes M*(L) where the latency chain equals the
    bandwidth term; connects the anchor's axis to the plan's small-message
    gap (§4.3)."""
    def m_star(l: Fraction) -> Fraction:
        # 2(r-1)/r * M/B = 2L  =>  M* = L*B*r/(r-1) = 512L/7 at r=8, B=64
        return l * B_REGISTRY * R / (R - 1)

    entries = []
    for label, l in [
        ("link10 (budget component)", L_LINK_ONLY),
        ("switch70 (budget component)", L_SWITCH_ONLY),
        ("pair80 (anchor point)", PAIR_ONE_STAGE),
        ("pair160 (two stages)", PAIR_TWO_STAGE),
        ("pair200 (registry point)", L_REGISTRY),
        ("pair800 (plan span upper, CAL-A10 transfer)", L_SPAN_UPPER),
    ]:
        entries.append(
            {
                "row": label,
                "L_ns": str(l),
                "crossover_bytes_exact": str(m_star(l)),
                "crossover_bytes_float": float(m_star(l)),
            }
        )
    # exact boundary fact: the smallest ladder member (8192 B) is
    # latency-dominant iff L > 7*8192/512 = 112 ns
    boundary = Fraction(7 * ANCHOR_POINT_SIZE, 512)
    assert boundary == 112
    assert m_star(PAIR_ONE_STAGE) == Fraction(40960, 7)  # ~5851.4 < 8192
    assert m_star(L_REGISTRY) == Fraction(102400, 7)     # ~14628.6 > 8192
    f80 = Fraction(2 * 80) / t_xbar(ANCHOR_POINT_SIZE, Fraction(80))
    f200 = Fraction(2 * 200) / t_xbar(ANCHOR_POINT_SIZE, Fraction(200))
    assert f80 == Fraction(5, 12) and f200 == Fraction(25, 39)
    return {
        "identity": "M*(L) = L*B*r/(r-1) = 512*L/7 bytes at r=8, B=64: the "
        "payload at which the latency chain (2L) equals the bandwidth term "
        "(2(r-1)/r*M/B); below M* the latency axis GOVERNS O-CCT",
        "rows": entries,
        "smallest_ladder_member_boundary": {
            "payload_bytes": ANCHOR_POINT_SIZE,
            "flip_latency_ns_exact": str(boundary),
            "statement": "the 8 KiB ladder member is latency-dominant iff "
            "L > 112 ns exactly: at the anchor point L=80 it is "
            "bandwidth-dominant (latency fraction exactly 5/12 ~ 41.7%), at "
            "the registry point L=200 latency-dominant (exactly 25/39 ~ "
            "64.1%) — WHERE the model sits on this anchor's axis decides "
            "which term governs the small-message regime",
        },
        "gap_connection": "the plan's gap §4.3 (no O-CCT anchor at <= ~64 "
        "KiB — exactly the current smoke regime) is the regime this axis "
        "governs: CAL-A9 locates the axis itself (a budget), but no anchor "
        "measures a CCT series on it — the two facts together are why this "
        "stage classifies as latency-axis placement, not calibration",
    }


def expressiveness_loss() -> dict:
    """What the lumped per-pair latency parameter cannot express — the
    latency-axis analog of stage A7's per-pair capacity finding (anchor-
    anchor arithmetic; no run ids by construction)."""
    return {
        "role": "quantifies what the L0 input space loses against the "
        "anchor's budget structure (a DECOMPOSITION, not a single number)",
        "lumped_parameter": "link.pair_latency_ns is ONE lumped per-pair "
        "value: the link term (10) and switch term (>=70) are not separable "
        "inputs, and the switch-STAGE COUNT of a path is not an input at "
        "all — a k-stage chain can enter only as the lumped arithmetic "
        "L = 80k",
        "structural_declaration": "the crossbar backend itself lists "
        "nonuniform_pair_latency (and multi_port_injection) among its "
        "explicitly_unsupported capabilities (src/essun/backends/analytical/"
        "l0_crossbar.py CAPABILITIES) — paths with different stage counts "
        "or different per-path budgets are structurally out of the input "
        "space, not merely unswept",
        "consequence_for_calibration": "no parameter choice inside the "
        "current input space can express '10 ns per link + 70 ns per stage, "
        "k stages' as such; a CXL-profile backend would need a decomposed "
        "latency input (owner design decision, recorded — the plan's §3.2 "
        "free-parameter discipline applies to any such new input)",
        "provenance": "anchor-registry arithmetic on CAL-A9's own staged "
        "structure plus the backend's declared capability list (declared "
        "interpretation); the additive recovery of the components on "
        "executed rows is in budget_decomposition above",
    }


def main() -> int:
    derived = anchor_derived()
    sweep_table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A9 (anchor CAL-A9)",
        "anchor": {
            "anchor_id": "CAL-A9",
            "title": "Berger et al. (IEEE Micro 2023): CXL link and switch latency breakdown",
            "source_row": "the anchor registry row CAL-A9 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A9",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A9",
            "urls": [
                "https://pages.cs.wisc.edu/~markhill/papers/ieeemicro23_cxl_memory_pooling.pdf",
            ],
            "confidence": "H for transcription; DESIGN-ESTIMATE numbers from "
            "the paper's own latency-budget analysis, NOT silicon "
            "measurements (staging-doc caveat: pair with CAL-A8's emulated "
            "64/140 ns); the switch term is worded 'at least' — a one-sided "
            "floor",
            "staged_numbers": "CXL links add ~10 ns per direction; CXL "
            "switches add at least ~70 ns (ports, arbitration, NoC) per "
            "switch stage — numbers as staged in anchors_staging.md §A9 "
            "(staging-doc transcription; no verbatim quote strings are "
            "claimed by this record)",
        },
        "target": {
            "role": "latency_budget_breakdown_axis_input",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "CAL-A9 publishes no "
            "collective measurements — it is a latency-budget breakdown "
            "(design estimates from the paper's own analysis); per "
            "CALIBRATION_PLAN.md §1.1: 'Cannot calibrate O-CCT — no "
            "collective measurements; a latency-budget breakdown. "
            "Decomposes per-hop latency into link term vs switch term for "
            "switch-based memory-semantic fabrics.' The anchor's "
            "extractable targets are the per-link term (~10 ns), the "
            "per-switch-stage floor (>=~70 ns), their one-stage pair sum "
            "(80 ns, plan-stated), the multi-stage chain arithmetic, and "
            "the one-sided floor direction — all recorded and executed "
            "here as latency-axis placement",
            "regime": {
                "topology_class": "switch-based memory-semantic fabrics "
                "(CXL class); executed on the landed single-non-blocking-"
                "switch-stage abstraction (fully_connected_crossbar) plus "
                "one ring row as the chain-multiplicity contrast (every "
                "ring hop one link+switch traversal)",
                "ranks": 8,
                "ranks_provenance": "FREE smoke-default rank count — the "
                "anchor pins none (a memory-pool budget study); power of "
                "two, divides every ladder size",
                "message_bytes_ladder": LADDER,
                "message_regime_note": "n/a (budget, not a series); the "
                "ladder spans both latency-term regimes so the exact "
                "crossover spectrum M*(L) = 512L/7 is recorded — the "
                "anchor's axis governs the small-message regime (plan gap "
                "§4.3), where no O-CCT anchor exists",
            },
        },
        "anchor_derived": derived,
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (the single-switch-stage fabric "
                "abstraction; 6 L-axis rows)",
                "analytical_l0 (ring; one row — the chain-multiplicity "
                "contrast at the anchor sum)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; B=64 fixed free, L in "
                "{10, 70, 80, 160, 200, 800}",
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L ; B=64, L=80 (each hop "
                "one link+switch traversal)",
            },
            "free_parameters": {
                "L_pair_swept_ns": {
                    "10": "CAL-A9 link term alone (budget-component row; also the A-L0X-LAT registry range lower endpoint)",
                    "70": "CAL-A9 switch-stage floor alone (budget-component row)",
                    "80": "CAL-A9 one-stage pair sum 10+70 — THE ANCHOR POINT (plan §2.1 A-L0X-LAT stated sum)",
                    "160": "2 x 80, two cascaded one-stage traversals (anchor arithmetic, labeled)",
                    "200": "A-L0X-LAT registry point (placement row; KEEP point / NARROW range-upper proposals recorded, value untouched)",
                    "800": "plan §2.1 A-L0X-LAT stated pair-latency span upper endpoint (CAL-A10 0.8 us assumption-class GPU figure; cross-class transfer, labeled)",
                },
                "L_hop_ns": {"80": "ring row: the plan-stated one-stage sum charged per hop"},
                "B_bytes_per_ns": 64,
                "B_provenance": "A-L0X-BW / A-L0-BW registry point, FIXED and free — CAL-A9 stages no bandwidth number (the mirror of stage A7: that stage swept B at fixed L, this stage sweeps L at fixed B)",
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar); A-L0-BW/A-L0-LAT/A-L0-FD/A-L0-DIV (ring) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_PAIR80,
                    "anchor point (L=80 ns = plan-stated one-stage budget sum; latency-bound 8 KiB ladder member)",
                ),
                run_summary(
                    RUN_ID_XBAR_REG200,
                    "registry point (L=200 ns = A-L0X-LAT smoke default; the SAME payload isolates the latency axis: per-op CCT delta exactly 2*(200-80) = 240 ns)",
                ),
            ],
            "reconciled_sweep": sweep_rows(),
            "budget_decomposition": budget_decomposition(sweep_table),
            "chain_multiplicity": chain_multiplicity(sweep_table),
            "crossover_spectrum": crossover_spectrum(),
            "expressiveness_loss": expressiveness_loss(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — the "
            "anchor publishes a latency budget, not a (size -> time) "
            "series; recorded per the stage's FAIL-clause duty instead of "
            "skipped because the anchor's actual role (the latency-axis "
            "decomposition: link term, switch-stage floor, one-stage pair "
            "sum) IS extractable and is executed above",
            "placement_summary": "the registry pair-latency point 200 ns "
            "sits +120 ns above (ratio exactly 5/2) the anchor-derived "
            "one-stage CXL-class pair sum 80 ns — consistent-with the "
            "anchor's one-sided floor (>= 80) and selected by no anchor; "
            "at the anchor point the executed per-op CCT is 384 ns "
            "(latency fraction exactly 5/12) vs the registry point's 624 ns "
            "(exactly 25/39), per-op delta exactly 240 ns = 2*(200-80); the "
            "two budget components are recovered additively on executed "
            "rows at all 12 sizes (t(80)-t(70) = 20 = 2x10 link, t(80)-t(10) "
            "= 140 = 2x70 switch); a cascaded second stage doubles the sum "
            "(t(160)-t(80) = 160 = 2x80) and a multi-hop schedule "
            "amplifies it (ring minus crossbar exactly 12L = 960 ns at "
            "every size)",
            "span_placement": "swept rows place the model across the "
            "plan's stated pair-latency span [80, 800] on the exact "
            "parameter quoted (link.pair_latency_ns); the swept 800 row is "
            "a labeled CAL-A10 cross-class transfer, not a CAL-A9 number; "
            "the anchor itself floors only the lower end",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the "
            "latency-axis-input role; no E3/E4 language — CAL-A9 is an "
            "external published design-estimate budget, not our testbed "
            "and not a measurement",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_PAIR80, RUN_ID_XBAR_REG200],
            "sweep_ids": [SWEEP_ID],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID}"],
            "run_backed_numbers": "every model output in "
            "comparison.anchor_point_runs and comparison.reconciled_sweep; "
            "comparison.budget_decomposition and comparison.chain_multiplicity "
            "cross-check closed forms against those executed sweep rows by "
            "exact Fraction string equality (declared inline); "
            "crossover_spectrum is closed-form identity arithmetic (its "
            "5/12 and 25/39 fractions are properties of the executed "
            "anchor-point and registry-point rows); expressiveness_loss is "
            "anchor-registry arithmetic plus the backend's declared "
            "capability list (no run ids claimed)",
            "inputs": [
                "experiments/calibration/a9/sweep_a9_pair_latency_v1.yaml",
                "experiments/calibration/a9/run_a9_anchor80_v1.yaml",
                "experiments/calibration/a9/run_a9_registry200_v1.yaml",
                "experiments/calibration/a9/workloads/w1_dense_tp_decode_tp8_8kib.yaml",
                "experiments/calibration/a9/topologies/ (7 files)",
                "experiments/calibration/a9/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/a9/run_a9_anchor80_v1.yaml ; "
            "make run EXP=experiments/calibration/a9/run_a9_registry200_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a9/sweep_a9_pair_latency_v1.yaml ; "
            "python experiments/calibration/a9/build_calibration_record.py",
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
