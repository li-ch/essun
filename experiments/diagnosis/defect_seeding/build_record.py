#!/usr/bin/env python3
"""Build the G9 leg-3 seeded-defect trial record (exact, committed).

Four ground-truth semantic defects (credit-consumption bug, return-
batching error, ignored unit conversion, silent scheduling omission) are
seeded as SILENT carriers over real essun engines and run through the
SAME pipeline as any cross-backend disagreement:

    probe -> delta-debugging minimize -> exact form attribution -> classify

Detection and classification are measured HONESTLY against the committed
ground truth (``essun.diagnosis.defects.GROUND_TRUTH``): a missed defect
or a misclassification is a finding about the DIAGNOSIS ENGINE, reported
in the record, never hidden. Nothing here tunes any engine, any anchor,
or any label; the carriers never enter the orchestrator or the evidence
store.

Usage: ``.venv/bin/python experiments/diagnosis/defect_seeding/build_record.py``
(rebuilds ``defect_seeding_record_v1.json`` in place; byte-identical
rebuild is enforced by tests/diagnosis/test_defect_seeding.py).
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from essun.diagnosis.minimize import (  # noqa: E402
    CaseDelta,
    InfeasibleDelta,
    ProbeResult,
    _public,
    minimize as minimize_case,
)
from essun.diagnosis.minimize import ERROR_A, ERROR_B, REPRODUCES, VANISHED  # noqa: E402
from essun.diagnosis.classify import (  # noqa: E402
    CONTRADICTS_BOUND_REQUIREMENT,
    DECLARED_IDENTITY,
    DECLARED_DIFFERENT_QUANTITY,
    FREE_IMPLEMENTATION_CHOICE,
    MISAPPLIES_DECLARED_CONVENTION,
    EngineFacts,
    classify_component,
)
from essun.diagnosis.defects import (  # noqa: E402
    GROUND_TRUTH,
    LinkCase,
    RingCase,
    TfcCase,
    defect_link_batched_return_completion,
    defect_ring_latency_omitted_after_first,
    defect_ring_unit_ignored,
    defect_tfc_floor_not_roundup,
    link_transfer_completion,
    ring_chain_completion,
    tfc_cell_completion,
)
from essun.specir import credit_automaton as ca  # noqa: E402

COMMITTED_COPY = Path(__file__).resolve().parent / "defect_seeding_record_v1.json"

# -- committed initial cases (free parameters; nothing standard-derived) ----

INITIAL_RING_UNIT = RingCase(
    ranks=8, payload_bytes=8 * 896, ops_count=1, link_gbps=828, hop_latency_ns=200
)
INITIAL_RING_SCHED = RingCase(
    ranks=8, payload_bytes=8 * 896, ops_count=4, link_gbps=828, hop_latency_ns=200
)
INITIAL_TFC = TfcCase(
    ranks=8,
    payload_bytes=8 * 896,  # chunk = 896 B = 3.5 cells (non-integral)
    cell_bytes=256,
    window_bytes=8192,
    link_bytes_per_ns=64,
    hop_latency_ns=200,
    credit_return_latency_ns=200,
)
INITIAL_LINK = LinkCase(
    total_bytes=64 * 256,
    window_bytes=4096,  # 16 packets per window (s | W invariant)
    link_bytes_per_ns=64,
    hop_latency_ns=100,
    credit_return_latency_ns=100,
    packet_bytes=256,
)


# -- probes -------------------------------------------------------------------


def _probe_pair(clean_fn, defect_fn, quantity_name):
    """Build a probe comparing two exact-quantity engines on a case."""

    def probe(case):
        try:
            clean_values = clean_fn(case)
        except Exception as exc:
            return ProbeResult(
                ERROR_A, {"engine": "clean", "error": f"{type(exc).__name__}: {exc}"}
            )
        try:
            defect_values = defect_fn(case)
        except Exception as exc:
            return ProbeResult(
                ERROR_B,
                {"engine": "defect_carrier", "error": f"{type(exc).__name__}: {exc}"},
            )
        a = [
            str(v) for v in (clean_values if isinstance(clean_values, tuple) else (clean_values,))
        ]
        b = [
            str(v) for v in (defect_values if isinstance(defect_values, tuple) else (defect_values,))
        ]
        disagrees = a != b
        first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
        return ProbeResult(
            REPRODUCES if disagrees else VANISHED,
            {
                "quantity": quantity_name,
                "clean_exact": a,
                "defect_exact": b,
                "first_diverging_index": first,
            },
        )

    return probe


# -- shrink ladders -----------------------------------------------------------


def _halving_to_floor(value: int, floor: int) -> list[int]:
    """Largest-first halving ladder: value, value//2, ..., > floor."""
    out = []
    v = value
    while v > floor:
        v = max(floor + 1, v // 2)
        if v not in out:
            out.append(v)
        if v <= floor + 1:
            break
    return out


def ring_ladder(case: RingCase):
    """Shrink order: ranks (largest proper divisor chain), payload bytes
    (halving to the divisibility floor r), op count (ddmin granularity)."""
    deltas = []
    for ranks in _rank_chain(case.ranks):
        def mk(rr=ranks):
            def apply(c):
                if c.payload_bytes % rr:
                    raise InfeasibleDelta(f"payload {c.payload_bytes} not divisible by {rr}")
                if c.ops_count * rr > c.payload_bytes // rr:
                    pass  # ops may exceed new chunk count; ring identity is per-op
                return replace(c, ranks=rr, payload_bytes=(c.payload_bytes // rr) * rr)

            return apply

        deltas.append(
            CaseDelta("ranks", f"ranks {case.ranks} -> {ranks}", mk())
        )
    for payload in _halving_to_floor(case.payload_bytes, case.ranks):
        def mp(p=payload):
            def apply(c):
                if c.ops_count > 1 and p // c.ranks < 1:
                    raise InfeasibleDelta("chunk below 1 byte per rank")
                return replace(c, payload_bytes=(p // c.ranks) * c.ranks)

            return apply

        deltas.append(
            CaseDelta(
                "payload_bytes", f"payload {case.payload_bytes} -> {(payload // case.ranks) * case.ranks}", mp()
            )
        )
    for removal in _removal_chain(case.ops_count):
        def mo(k=removal):
            def apply(c):
                if c.ops_count - k < 1:
                    raise InfeasibleDelta("at least one op")
                return replace(c, ops_count=c.ops_count - k)

            return apply

        deltas.append(
            CaseDelta("ops_count", f"ops {case.ops_count} -> {case.ops_count - removal}", mo())
        )
    return deltas


def _rank_chain(ranks: int) -> list[int]:
    """Largest-proper-divisor chain below ranks (keeps payload divisible)."""
    out = []
    r = ranks
    while r > 2:
        divs = [d for d in range(r // 2, 1, -1) if r % d == 0]
        if not divs:
            break
        r = divs[0]
        out.append(r)
    if ranks > 2 and 2 not in out:
        out.append(2)  # 2 divides every even chain member; odd chains stop earlier
    return out


def _removal_chain(count: int) -> list[int]:
    """ddmin-granularity removal ladder: n//2, n//4, ..., 1."""
    out = []
    k = count // 2
    while k >= 1:
        if k not in out:
            out.append(k)
        k //= 2
    return out


def tfc_ladder(case: TfcCase):
    deltas = []
    for ranks in _rank_chain(case.ranks):
        def mk(rr=ranks):
            def apply(c):
                if c.payload_bytes % rr:
                    raise InfeasibleDelta("payload not divisible")
                return replace(c, ranks=rr)

            return apply

        deltas.append(CaseDelta("ranks", f"ranks {case.ranks} -> {ranks}", mk()))
    for payload in _halving_to_floor(case.payload_bytes, case.ranks):
        def mp(p=payload):
            def apply(c):
                return replace(c, payload_bytes=(p // c.ranks) * c.ranks)

            return apply

        deltas.append(
            CaseDelta("payload_bytes", f"payload {case.payload_bytes} -> {(payload // case.ranks) * case.ranks}", mp())
        )
    return deltas


def link_ladder(case: LinkCase):
    s = case.packet_bytes
    deltas = []
    for removal in _removal_chain(case.total_bytes // s):
        def mt(k=removal):
            def apply(c):
                packets = c.total_bytes // s - k
                if packets < 1:
                    raise InfeasibleDelta("at least one packet")
                return replace(c, total_bytes=packets * s)

            return apply

        deltas.append(
            CaseDelta(
                "total_bytes",
                f"packets {case.total_bytes // s} -> {case.total_bytes // s - removal}",
                mt(),
            )
        )
    for window in _halving_to_floor(case.window_bytes, s):
        def mw(w=window):
            def apply(c):
                ww = (w // s) * s  # keep the s | W case-space invariant
                if ww < s:
                    raise InfeasibleDelta("window below one packet")
                return replace(c, window_bytes=ww)

            return apply

        deltas.append(
            CaseDelta("window_bytes", f"window {case.window_bytes} -> {(window // s) * s}", mw())
        )
    return deltas


# -- form libraries (exact attribution at the minimal case) --------------------


def _as_tuple(v):
    return [str(x) for x in (v if isinstance(v, tuple) else (v,))]


def attribute_ring_unit(case: RingCase, clean_values, defect_values) -> list:
    """Variants: the declared convention applied vs skipped."""
    variants = [
        ("gb_convention_applied_2p30", DECLARED_IDENTITY, "", ring_chain_completion),
        ("gb_convention_ignored_value_as_b_per_ns", MISAPPLIES_DECLARED_CONVENTION,
         "A-AS1-BW-UNIT-analogue (1 GB = 2^30 B)", defect_ring_unit_ignored),
    ]
    return _match(variants, case, clean_values, defect_values)


def attribute_ring_sched(case: RingCase, clean_values, defect_values) -> list:
    variants = [
        ("l0_ring_identity_per_op_latency", DECLARED_IDENTITY, "", ring_chain_completion),
        (
            "latency_omitted_after_first_op",
            CONTRADICTS_BOUND_REQUIREMENT,
            "SPEC:L0-RING-IDENTITY(A-L0-LAT per op)",
            defect_ring_latency_omitted_after_first,
        ),
    ]
    return _match(variants, case, clean_values, defect_values)


def attribute_tfc(case: TfcCase, clean_values, defect_values) -> list:
    variants = [
        ("r08_roundup_law", DECLARED_IDENTITY, "", tfc_cell_completion),
        (
            "floor_not_roundup_credit_consumption",
            CONTRADICTS_BOUND_REQUIREMENT,
            "UEC11-FC-R08",
            defect_tfc_floor_not_roundup,
        ),
    ]
    return _match(variants, case, clean_values, defect_values)


def attribute_link(case: LinkCase, clean_values, defect_values) -> list:
    variants = [
        ("per_packet_credit_return_automaton", DECLARED_IDENTITY, "",
         link_transfer_completion),
        (
            "whole_window_batched_credit_return",
            FREE_IMPLEMENTATION_CHOICE,
            "",
            defect_link_batched_return_completion,
        ),
    ]
    return _match(variants, case, clean_values, defect_values)


def _match(variants, case, clean_values, defect_values):
    out = []
    for variant_id, normativity, req, fn in variants:
        try:
            values = _as_tuple(fn(case))
        except Exception as exc:
            out.append(
                {
                    "variant_id": variant_id,
                    "normativity": normativity,
                    "requirement_or_convention": req,
                    "clean_matches": None,
                    "defect_matches": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        out.append(
            {
                "variant_id": variant_id,
                "normativity": normativity,
                "requirement_or_convention": req,
                "clean_matches": values == _as_tuple(clean_values),
                "defect_matches": values == _as_tuple(defect_values),
            }
        )
    return out


# -- the four trials ----------------------------------------------------------


def _trial(name, initial, probe, ladder, attribute, clean_fn, defect_fn, facts):
    result = minimize_case(initial, probe, ladder)
    if not result.reproducer_found:
        return {
            "defect_id": name,
            "detected": False,
            "ground_truth": GROUND_TRUTH[name],
            "finding": "MISSED DEFECT: the probe found no disagreement at the "
            "initial case — a finding about the diagnosis engine, reported "
            "as such",
            "initial_case": _public(initial),
        }
    minimal = result.minimal_case
    clean_values = clean_fn(minimal)
    defect_values = defect_fn(minimal)
    attributions = attribute(minimal, clean_values, defect_values)
    defect_attr = next(
        (a for a in attributions if a.get("defect_matches") and a["normativity"] != DECLARED_IDENTITY),
        None,
    )
    if defect_attr is None:
        classification = {
            "label": "unresolved",
            "reasons": ["defect values match no library variant exactly"],
            "residual_exact": "unattributed",
        }
    else:
        from essun.diagnosis.classify import Attribution

        attribution = Attribution(
            engine_id=facts.engine_id,
            variant_id=defect_attr["variant_id"],
            normativity=defect_attr["normativity"],
            requirement_or_convention=defect_attr.get("requirement_or_convention", ""),
            attributed_delta_exact="see minimal_case values",
        )
        verdict = classify_component(
            attribution, facts, facts, component=name
        )
        classification = verdict.as_dict()
    expected = GROUND_TRUTH[name]["expected_label"]
    return {
        "defect_id": name,
        "defect_kind": GROUND_TRUTH[name]["defect_kind"],
        "detected": True,
        "initial_case": _public(initial),
        "minimal_case": _public(minimal),
        "minimization": {
            "passes": result.passes,
            "probes": len(result.probes),
            "accepted": sum(1 for p in result.probes if p.accepted),
            "final_pass_rejections": [
                {
                    "dimension": p.dimension,
                    "description": p.description,
                    "outcome": p.outcome,
                }
                for p in result.rejections_of_final_pass()
            ],
            "probe_log": [
                {
                    "pass": p.pass_index,
                    "dimension": p.dimension,
                    "description": p.description,
                    "outcome": p.outcome,
                    "accepted": p.accepted,
                }
                for p in result.probes
            ],
        },
        "minimal_values": {
            "clean_exact": _as_tuple(clean_values),
            "defect_exact": _as_tuple(defect_values),
        },
        "attribution": attributions,
        "classification": classification,
        "expected_label": expected,
        "classification_matches_ground_truth": classification["label"] == expected,
        "ground_truth_reason": GROUND_TRUTH[name]["expected_reason"],
    }


def build() -> dict:
    # Trial 1: credit-consumption bug (FLOOR vs UEC11-FC-R08 ROUNDUP).
    facts_tfc = EngineFacts(
        engine_id="defect_carrier:l0_tfc_cell",
        bound_requirements=("UEC11-FC-R08", "UEC11-FC-R02"),
        observable_definition_id="O-CCT(l0_tfc cell-quantized identity)",
    )
    t1 = _trial(
        "floor_not_roundup_credit_consumption",
        INITIAL_TFC,
        _probe_pair(tfc_cell_completion, defect_tfc_floor_not_roundup, "completion_ns_exact"),
        tfc_ladder,
        attribute_tfc,
        tfc_cell_completion,
        defect_tfc_floor_not_roundup,
        facts_tfc,
    )

    # Trial 2: return-batching error (whole-window batches, admission law
    # intact — verified mechanically on the carrier's own admission trace).
    facts_link = EngineFacts(
        engine_id="defect_carrier:credit_automaton",
        bound_requirements=("UEC11-FC-R02",),
        observable_definition_id="completion_ns(greedy single link)",
    )
    config = INITIAL_LINK.as_automaton_config()
    batched = __import__(
        "essun.diagnosis.defects", fromlist=["_BatchedGreedyExecutor"]
    )._BatchedGreedyExecutor(config)
    batched.run_transfer(INITIAL_LINK.total_bytes)
    r02_holds = ca.sliding_window_bound_holds(
        batched.machine.admissions, INITIAL_LINK.window_bytes,
        config.credit_loop_delay_ns,
    )
    t2 = _trial(
        "drain_batched_credit_return",
        INITIAL_LINK,
        _probe_pair(link_transfer_completion, defect_link_batched_return_completion, "completion_ns"),
        link_ladder,
        attribute_link,
        link_transfer_completion,
        defect_link_batched_return_completion,
        facts_link,
    )
    t2["admission_law_check_on_carrier_trace"] = {
        "requirement": "UEC11-FC-R02",
        "check": "sliding_window_bound_holds over the carrier's own admissions",
        "holds": r02_holds,
        "note": (
            "mechanical evidence behind the classification: the carrier never "
            "exceeds the granted window in flight, so the bound admission law "
            "is intact and the divergence is return TIMING — not pinned by "
            "any bound requirement"
        ),
    }

    # Trial 3: ignored unit conversion (declared GB 2^30 convention skipped).
    facts_unit = EngineFacts(
        engine_id="defect_carrier:ring_translation",
        bound_requirements=(),
        declared_assumption_ids=("A-AS1-BW-UNIT-analogue",),
        observable_definition_id="O-CCT(l0 ring)",
    )
    t3 = _trial(
        "ignored_gb_unit_conversion",
        INITIAL_RING_UNIT,
        _probe_pair(ring_chain_completion, defect_ring_unit_ignored, "per_op_completion_ns_exact"),
        ring_ladder,
        attribute_ring_unit,
        ring_chain_completion,
        defect_ring_unit_ignored,
        facts_unit,
    )

    # Trial 4: silent scheduling omission (latency term dropped after op 1).
    facts_sched = EngineFacts(
        engine_id="defect_carrier:l0_ring",
        bound_requirements=("SPEC:L0-RING-IDENTITY(A-L0-LAT per op)",),
        observable_definition_id="O-CCT(l0 ring)",
    )
    t4 = _trial(
        "latency_omitted_after_first_op",
        INITIAL_RING_SCHED,
        _probe_pair(ring_chain_completion, defect_ring_latency_omitted_after_first, "per_op_completion_ns_exact"),
        ring_ladder,
        attribute_ring_sched,
        ring_chain_completion,
        defect_ring_latency_omitted_after_first,
        facts_sched,
    )

    trials = [t1, t2, t3, t4]
    detected = sum(1 for t in trials if t.get("detected"))
    classified = sum(1 for t in trials if t.get("classification_matches_ground_truth"))
    return {
        "record_type": "essun.diagnosis.defect_seeding.v1",
        "pipeline": "probe -> delta-debugging minimize -> exact form attribution -> classify",
        "taxonomy_note": (
            "labels from essun.diagnosis.classify.TAXONOMY; residuals stay "
            "visible; nothing tuned, no dispositions changed"
        ),
        "trials": trials,
        "summary": {
            "defects_seeded": len(trials),
            "detected": detected,
            "classification_matches_ground_truth": classified,
            "missed_or_misclassified": [
                t["defect_id"]
                for t in trials
                if not t.get("detected") or not t.get("classification_matches_ground_truth")
            ],
        },
    }


def main() -> int:
    record = build()
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    COMMITTED_COPY.write_text(text, encoding="utf-8")
    print(f"wrote {COMMITTED_COPY}")
    print(json.dumps(record["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
