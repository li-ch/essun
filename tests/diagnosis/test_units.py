"""Unit guards for the G9 diagnosis engine: minimizer + classifier.

Pure in-process tests (no Docker, no evidence store): determinism of the
delta-debugging search, 1-minimality certificates, probe-outcome
semantics, and every taxonomy label of the mechanical classifier being
reachable with the right reason.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from essun.diagnosis.classify import (
    ABSTRACTION_DIFFERENCE,
    CONTRADICTS_BOUND_REQUIREMENT,
    DECLARED_DIFFERENT_QUANTITY,
    DECLARED_IDENTITY,
    FREE_IMPLEMENTATION_CHOICE,
    MISSING_CAPABILITY,
    MISAPPLIES_DECLARED_CONVENTION,
    PERMITTED_IMPLEMENTATION_VARIATION,
    SPECIFICATION_VIOLATION,
    UNRESOLVED,
    Attribution,
    EngineFacts,
    classify_component,
)
from essun.diagnosis.minimize import (
    INFEASIBLE,
    REPRODUCES,
    VANISHED,
    CaseDelta,
    InfeasibleDelta,
    MinimizationResult,
    ProbeResult,
    minimize,
)


# -- a tiny case space: disagreement present iff size >= 8 and flag -----


@dataclass(frozen=True)
class ToyCase:
    size: int
    flag: bool


def toy_probe(case: ToyCase) -> ProbeResult:
    # engines disagree iff size >= 8 AND flag is True
    if case.size < 8:
        return ProbeResult(VANISHED, {"why": "below 8 the engines agree"})
    if not case.flag:
        return ProbeResult(VANISHED, {"why": "flag off: engines agree"})
    return ProbeResult(REPRODUCES, {"size": case.size})


def toy_ladder(case: ToyCase) -> list[CaseDelta]:
    deltas = []
    if case.size // 2 >= 1:
        def hs(s=case.size // 2):
            def apply(c):
                if s < 1:
                    raise InfeasibleDelta()
                return replace(c, size=s)
            return apply
        deltas.append(CaseDelta("size", f"size {case.size} -> {case.size // 2}", hs()))
    def tf(c):
        return replace(c, flag=not c.flag)
    deltas.append(CaseDelta("flag", f"flag {case.flag} -> {not case.flag}", tf))
    return deltas


def test_minimizer_shrinks_to_boundary_and_is_deterministic():
    first = minimize(ToyCase(size=64, flag=True), toy_probe, toy_ladder)
    second = minimize(ToyCase(size=64, flag=True), toy_probe, toy_ladder)
    assert first.reproducer_found and second.reproducer_found
    assert first.minimal_case == ToyCase(size=8, flag=True)
    assert first.probes == second.probes  # byte-identical search
    assert first.minimal_case != first.initial_case


def test_minimizer_1_minimality_certificate_covers_every_dimension():
    result = minimize(ToyCase(size=64, flag=True), toy_probe, toy_ladder)
    final = result.rejections_of_final_pass()
    dims = {p.dimension for p in final}
    assert dims == {"size", "flag"}  # every dimension's shrink was probed
    outcomes = {(p.dimension, p.outcome) for p in final}
    assert ("size", VANISHED) in outcomes  # size 8 -> 4 kills it
    assert ("flag", VANISHED) in outcomes  # flag flip kills it


def test_minimizer_no_disagreement_reports_not_found():
    result = minimize(ToyCase(size=4, flag=True), toy_probe, toy_ladder)
    assert not result.reproducer_found
    assert result.probes == ()


def test_minimizer_records_error_outcomes_not_crashes():
    def error_probe(case: ToyCase) -> ProbeResult:
        if case.size == 4:
            return ProbeResult("error_engine_b", {"error": "boom"})
        return toy_probe(case)

    result = minimize(ToyCase(size=16, flag=True), error_probe, toy_ladder)
    assert result.reproducer_found
    # 16 -> 8 accepted; 8 -> 4 is an engine error (recorded, rejected);
    # the reproducer stays at the error boundary
    assert result.minimal_case == ToyCase(size=8, flag=True)
    outcomes = {(p.dimension, p.outcome) for p in result.probes}
    assert ("size", "error_engine_b") in outcomes


# -- classifier: every taxonomy label reachable, mechanically ----------

FACTS = EngineFacts(engine_id="engine_x", bound_requirements=("REQ-1",))
OTHER = EngineFacts(engine_id="engine_y", observable_definition_id="wire-only")


def test_missing_capability_when_observable_declared_unsupported():
    facts = EngineFacts(
        engine_id="engine_x", observable_declared_unsupported=True
    )
    verdict = classify_component(
        Attribution("engine_x", "any", DECLARED_IDENTITY), facts, OTHER, component="c"
    )
    assert verdict.label == MISSING_CAPABILITY


def test_specification_violation_only_for_bound_requirements():
    verdict = classify_component(
        Attribution(
            "engine_x",
            "floor_form",
            CONTRADICTS_BOUND_REQUIREMENT,
            "REQ-1",
            attributed_delta_exact="25",
        ),
        FACTS,
        OTHER,
        component="c",
    )
    assert verdict.label == SPECIFICATION_VIOLATION
    assert any("REQ-1" in r for r in verdict.reasons)
    # the SAME contradiction against a requirement the engine does NOT
    # bind is unresolved (normative scope is the other side's)
    unbound = EngineFacts(engine_id="engine_x", bound_requirements=("REQ-2",))
    verdict2 = classify_component(
        Attribution("engine_x", "f", CONTRADICTS_BOUND_REQUIREMENT, "REQ-1"),
        unbound,
        OTHER,
        component="c",
    )
    assert verdict2.label == UNRESOLVED


def test_translation_defect_and_permitted_variation_labels():
    t = classify_component(
        Attribution("engine_x", "unit_ignored", MISAPPLIES_DECLARED_CONVENTION, "CONV-1"),
        FACTS,
        OTHER,
        component="c",
    )
    assert t.label == "translation_defect"
    p = classify_component(
        Attribution("engine_x", "free_choice_form", FREE_IMPLEMENTATION_CHOICE),
        FACTS,
        OTHER,
        component="c",
    )
    assert p.label == PERMITTED_IMPLEMENTATION_VARIATION
    assert p.residual_visible  # the divergence stays visible


def test_abstraction_difference_requires_zero_residual():
    facts = EngineFacts(
        engine_id="engine_x", observable_definition_id="wall-bundled"
    )
    ok = classify_component(
        Attribution("engine_x", "wall_definition", DECLARED_DIFFERENT_QUANTITY),
        facts,
        OTHER,
        component="c",
        unattributed_residual_exact="0",
    )
    assert ok.label == ABSTRACTION_DIFFERENCE
    residual = classify_component(
        Attribution("engine_x", "wall_definition", DECLARED_DIFFERENT_QUANTITY),
        facts,
        OTHER,
        component="c",
        unattributed_residual_exact="37",
    )
    assert residual.label == UNRESOLVED
    assert residual.residual_exact == "37"  # stays visible


def test_no_match_is_unresolved_and_visible():
    verdict = classify_component(
        Attribution("engine_x", "none", "no_match"),
        FACTS,
        OTHER,
        component="c",
        unattributed_residual_exact="118/100",
    )
    assert verdict.label == UNRESOLVED
    assert verdict.residual_visible


def test_declared_identity_is_not_a_defect():
    verdict = classify_component(
        Attribution("engine_x", "clean_form", DECLARED_IDENTITY),
        FACTS,
        OTHER,
        component="c",
    )
    assert verdict.label == DECLARED_IDENTITY
    assert not verdict.residual_visible
