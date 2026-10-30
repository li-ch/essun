"""The fixed disagreement taxonomy and its mechanical classifier.

Six labels, no more (G9 prompt; founding rule 5 — classify, never tune):

===============  =======================================================
label            meaning
===============  =======================================================
specification_   the executed behavior contradicts a NORMATIVE
violation        requirement (standard MUST/MUST-NOT) that the engine
                 itself claims to implement through a declared binding.
permitted_       the engines disagree on an aspect the governing
implementation_ specification / declarations leave FREE (e.g. credit
variation        return timing); both engines are self-consistent with
                 their declared laws; the divergence is real and stays
                 visible.
abstraction_     the compared observables are DECLARED to be different
difference       quantities (different bundling of terms); the
                 disagreement is exactly attributed to the declared
                 extra/missing terms (residual zero).
translation_     the manifest -> engine-input translation misapplies a
defect           declared convention (unit, grid, rounding), so the
                 case EXECUTED by the engine is not the case the
                 manifest declares.
missing_         one engine cannot execute the case or emit the
capability      compared observable at all (a declared or discovered
                 gap).
unresolved       the exact facts do not determine any label above;
                 the residual disagreement stays visible.
===============  =======================================================

The classifier is MECHANICAL and DETERMINISTIC over an exact fact set the
driver computes (exact-Fraction form attribution, declaration lookups,
ablation deltas). It invents nothing: if the facts do not determine a
label, the answer is ``unresolved`` with the residual quantified — an
honest unknown, never a guessed class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

SPECIFICATION_VIOLATION = "specification_violation"
PERMITTED_IMPLEMENTATION_VARIATION = "permitted_implementation_variation"
ABSTRACTION_DIFFERENCE = "abstraction_difference"
TRANSLATION_DEFECT = "translation_defect"
MISSING_CAPABILITY = "missing_capability"
UNRESOLVED = "unresolved"

#: The fixed taxonomy (label -> normative definition, committed verbatim
#: with every classification record so a record is self-describing).
TAXONOMY: dict[str, str] = {
    SPECIFICATION_VIOLATION: (
        "executed behavior contradicts a normative requirement the engine "
        "claims to implement through a declared binding (the binding's law "
        "is not the law that executed)"
    ),
    PERMITTED_IMPLEMENTATION_VARIATION: (
        "engines disagree on an aspect the governing specification and the "
        "engines' own declarations leave free; both are self-consistent; "
        "the divergence is quantified and stays visible (never tuned away)"
    ),
    ABSTRACTION_DIFFERENCE: (
        "the compared observables are declared as different quantities "
        "(different term bundling); the disagreement is exactly attributed "
        "to the declared extra/missing terms"
    ),
    TRANSLATION_DEFECT: (
        "the manifest-to-engine-input translation misapplies a declared "
        "convention (unit, grid, rounding), so the executed case is not the "
        "declared case"
    ),
    MISSING_CAPABILITY: (
        "one engine cannot execute the case or emit the compared "
        "observable at all; the comparison cannot be made on that axis"
    ),
    UNRESOLVED: (
        "the exact facts do not determine a label; the residual "
        "disagreement stays visible and is an open research fact"
    ),
}

#: Variant normativity statuses the attribution may carry.
CONTRADICTS_BOUND_REQUIREMENT = "contradicts_bound_requirement"
MISAPPLIES_DECLARED_CONVENTION = "misapplies_declared_convention"
FREE_IMPLEMENTATION_CHOICE = "free_implementation_choice"
DECLARED_IDENTITY = "declared_identity"
DECLARED_DIFFERENT_QUANTITY = "declared_different_quantity"
NO_MATCH = "no_match"


@dataclass(frozen=True)
class Attribution:
    """One exact form-attribution result for one engine's values.

    The driver evaluates a LIBRARY of candidate law/translation variants
    (each an exact callable over the case) and reports which variant
    reproduces the engine's values EXACTLY (Fraction equality; a near
    match is NO match — attribution is exact or absent).

    ``variant_id``              — library id of the matching form;
    ``normativity``             — the variant's status: DECLARED_IDENTITY
                                  (the engine's own declared law),
                                  CONTRADICTS_BOUND_REQUIREMENT (a bound
                                  normative requirement the executed form
                                  violates), MISAPPLIES_DECLARED_CONVENTION
                                  (an input-convention error),
                                  FREE_IMPLEMENTATION_CHOICE (a legal
                                  alternative the spec does not pin),
                                  DECLARED_DIFFERENT_QUANTITY (a declared
                                  different observable bundling), or
                                  NO_MATCH (residual unattributed);
    ``requirement_or_convention`` — the requirement/convention id the
                                  status refers to (e.g. "UEC11-FC-R08"),
                                  or "";
    ``attributed_delta_exact``  — the exact delta this attribution
                                  accounts for (value side), Fraction;
    ``evidence``                — exact strings grounding the match.
    """

    engine_id: str
    variant_id: str
    normativity: str
    requirement_or_convention: str = ""
    attributed_delta_exact: str = "0"
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineFacts:
    """Declaration facts for one side of the comparison (driver-computed).

    Every field is looked up from a real declaration source (capability
    record, assumptions file, binding registry, translation-assumption
    table) — the classifier treats them as ground facts, never guesses.
    """

    engine_id: str
    #: normative requirement ids this engine claims via declared bindings
    bound_requirements: tuple[str, ...] = ()
    #: the engine declares the compared observable unsupported/absent
    observable_declared_unsupported: bool = False
    #: ids of the engine's declared identity/translation assumptions on
    #: the compared axis (e.g. ("A-AS2-DELAY-POS", "A-AS2-MEM-BW"))
    declared_assumption_ids: tuple[str, ...] = ()
    #: the engine's declared DEFINITION of the compared observable (id or
    #: short formula); differing definitions across engines are the
    #: abstraction-difference fact
    observable_definition_id: str = ""


@dataclass(frozen=True)
class Classification:
    """The verdict for one component (or the whole) disagreement."""

    label: str
    engine_id: str
    component: str
    reasons: tuple[str, ...]
    residual_exact: str = "0"
    residual_visible: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "label_definition": TAXONOMY.get(
                self.label,
                "not a taxonomy label: the engine matches its own "
                "declared identity on this component (no defect found)",
            ),
            "engine_id": self.engine_id,
            "component": self.component,
            "reasons": list(self.reasons),
            "residual_exact": self.residual_exact,
            "residual_visible": self.residual_visible,
        }


def classify_component(
    attribution: Attribution,
    facts: EngineFacts,
    other_facts: EngineFacts,
    *,
    component: str,
    unattributed_residual_exact: str = "0",
) -> Classification:
    """Classify ONE attributed component of a disagreement.

    Deterministic rule order (first match wins; every rule is mechanical
    over the given facts):

    1. missing_capability — the engine declares the compared observable
       unsupported (a declared gap is a capability fact, not a defect);
    2. specification_violation — the engine's values exactly match a form
       that CONTRADICTS a requirement the engine itself BOUND;
    3. translation_defect — the values exactly match a form that
       MISAPPLIES a declared input convention;
    4. abstraction_difference — the values match the engine's declared
       different-quantity bundling AND the component delta is exactly
       attributed (residual zero);
    5. permitted_implementation_variation — the values exactly match a
       free-choice form (no bound requirement, no convention violated);
    6. unresolved — no variant matched exactly, or an unattributed
       residual remains on this component.
    """
    reasons: list[str] = []
    if facts.observable_declared_unsupported:
        reasons.append(
            f"engine {facts.engine_id} declares the compared observable "
            "unsupported (capability declaration)"
        )
        return Classification(
            label=MISSING_CAPABILITY,
            engine_id=facts.engine_id,
            component=component,
            reasons=tuple(reasons),
            residual_exact="0",
            residual_visible=False,
        )
    if attribution.normativity == CONTRADICTS_BOUND_REQUIREMENT:
        req = attribution.requirement_or_convention
        if req in facts.bound_requirements:
            reasons.append(
                f"engine {facts.engine_id} values match form "
                f"{attribution.variant_id!r} exactly, which contradicts "
                f"normative requirement {req} that the engine itself "
                f"binds ({', '.join(facts.bound_requirements)})"
            )
            return Classification(
                label=SPECIFICATION_VIOLATION,
                engine_id=facts.engine_id,
                component=component,
                reasons=tuple(reasons),
                residual_exact=attribution.attributed_delta_exact,
                residual_visible=True,
            )
        # contradicts A requirement, but not one THIS engine bound: the
        # violation is real but its normative scope is the other side's.
        reasons.append(
            f"engine {facts.engine_id} values match form "
            f"{attribution.variant_id!r} contradicting {req}, which this "
            "engine does not bind — normative scope unresolved"
        )
        return Classification(
            label=UNRESOLVED,
            engine_id=facts.engine_id,
            component=component,
            reasons=tuple(reasons),
            residual_exact=attribution.attributed_delta_exact,
            residual_visible=True,
        )
    if attribution.normativity == MISAPPLIES_DECLARED_CONVENTION:
        reasons.append(
            f"engine {facts.engine_id} values match form "
            f"{attribution.variant_id!r} exactly: the declared convention "
            f"{attribution.requirement_or_convention} is not the one that "
            "executed — the executed case differs from the declared case"
        )
        return Classification(
            label=TRANSLATION_DEFECT,
            engine_id=facts.engine_id,
            component=component,
            reasons=tuple(reasons),
            residual_exact=attribution.attributed_delta_exact,
            residual_visible=True,
        )
    if attribution.normativity == DECLARED_DIFFERENT_QUANTITY:
        residual = Fraction(unattributed_residual_exact)
        reasons.append(
            f"engine {facts.engine_id} emits {attribution.variant_id!r} — "
            "a DECLARED different quantity (observable definition "
            f"{facts.observable_definition_id!r} vs "
            f"{other_facts.observable_definition_id!r})"
        )
        if residual == 0:
            reasons.append(
                "the component delta is exactly attributed to the declared "
                "extra/missing terms (exact residual zero)"
            )
            return Classification(
                label=ABSTRACTION_DIFFERENCE,
                engine_id=facts.engine_id,
                component=component,
                reasons=tuple(reasons),
                residual_exact="0",
                residual_visible=False,
            )
        reasons.append(
            f"an exact residual of {unattributed_residual_exact} ns remains "
            "after the declared bundling terms — not fully attributed"
        )
        return Classification(
            label=UNRESOLVED,
            engine_id=facts.engine_id,
            component=component,
            reasons=tuple(reasons),
            residual_exact=unattributed_residual_exact,
            residual_visible=True,
        )
    if attribution.normativity == FREE_IMPLEMENTATION_CHOICE:
        reasons.append(
            f"engine {facts.engine_id} values match form "
            f"{attribution.variant_id!r} exactly; no bound requirement of "
            f"({', '.join(facts.bound_requirements) or 'none'}) is "
            "violated and no declared convention is misapplied — the "
            "diverged aspect is specification-free, both engines "
            "self-consistent; the divergence is quantified and STAYS VISIBLE"
        )
        return Classification(
            label=PERMITTED_IMPLEMENTATION_VARIATION,
            engine_id=facts.engine_id,
            component=component,
            reasons=tuple(reasons),
            residual_exact=attribution.attributed_delta_exact,
            residual_visible=True,
        )
    if attribution.normativity == DECLARED_IDENTITY:
        reasons.append(
            f"engine {facts.engine_id} matches its OWN declared identity — "
            "no defect on this component for this engine"
        )
        return Classification(
            label=DECLARED_IDENTITY,
            engine_id=facts.engine_id,
            component=component,
            reasons=tuple(reasons),
            residual_exact="0",
            residual_visible=False,
        )
    reasons.append(
        f"engine {facts.engine_id} values match NO library variant exactly "
        f"(attribution {attribution.normativity}); the disagreement on "
        "this component is not explained by the fact set"
    )
    return Classification(
        label=UNRESOLVED,
        engine_id=facts.engine_id,
        component=component,
        reasons=tuple(reasons),
        residual_exact=unattributed_residual_exact,
        residual_visible=True,
    )
