"""Diagnosis engine (G9): minimize, localize, classify — never tune.

Given a cross-backend disagreement, the diagnosis engine (a) MINIMIZES the
reproducing case to the smallest one the declared shrink ladder can reach
(delta-debugging style, deterministic, every probe logged), (b) LOCALIZES
the disagreement by exact form attribution (which law variant, which
translation convention, which declared term accounts for the delta, in
exact :class:`fractions.Fraction` arithmetic), and (c) CLASSIFIES it into
the fixed taxonomy of :mod:`essun.diagnosis.classify`.

Design contract (founding rule 5: verification != validation — when
backends disagree, minimize and classify the counterexample first, never
tune parameters until curves look similar):

- the minimizer NEVER evaluates a parameter change that is not a case
  shrink; the localizer NEVER proposes a fix; the classifier NEVER labels
  a disagreement away. Nonzero residuals STAY VISIBLE — "everything
  explained" is an outcome, never a requirement (:class:`classify` returns
  ``unresolved`` components and exact residual quantities);
- every probe (accepted or rejected) is recorded in the minimization log,
  so a committed record rebuilds the entire search deterministically;
- the classifier's rules are mechanical and deterministic over an exact,
  driver-computed fact set (:class:`classify.Attribution`,
  :class:`classify.EngineFacts`); the classifier itself invents no values.

Synthetic defect carriers (:mod:`essun.diagnosis.defects`) are ground
truth for measuring the engine: seeded semantic defects with known
expected classifications, run through the same minimize -> attribute ->
classify pipeline as real disagreements. They are NEVER registered as
orchestrator backends and NEVER enter the evidence store as runs.
"""

from essun.diagnosis.classify import (
    TAXONOMY,
    Attribution,
    Classification,
    EngineFacts,
    classify_component,
)
from essun.diagnosis.minimize import (
    CaseDelta,
    MinimizationResult,
    ProbeOutcome,
    ProbeResult,
    minimize,
)

__all__ = [
    "TAXONOMY",
    "Attribution",
    "Classification",
    "EngineFacts",
    "classify_component",
    "CaseDelta",
    "MinimizationResult",
    "ProbeOutcome",
    "ProbeResult",
    "minimize",
]
