"""Deterministic delta-debugging minimizer for cross-backend disagreements.

Given a case (workload / parameters / topology, as a frozen dataclass the
driver defines) and a :func:`probe` that re-executes both engines on a
candidate case and reports whether the DISAGREEMENT still reproduces, this
module shrinks the case to a 1-minimal reproducer:

- **1-minimal w.r.t. the declared shrink ladder**: at the fixpoint, every
  single ladder step applicable to the final case was probed and rejected
  (the rejection reason is in the log). The certificate is the final
  pass's rejections. Minimality is w.r.t. the LADDER the driver declares,
  never a claim over all conceivable cases — the honest statement is
  "no single declared shrink preserves the disagreement".
- **deterministic**: ladder steps are generated in a fixed order
  (dimension order, then descending magnitude), ties broken by that order
  alone; no RNG, no wall clock, no host metadata anywhere in the result.
- **classic ddmin spirit** (Zeller: "Yesterday, my program worked"): each
  pass tries the LARGEST applicable shrink per dimension first; an
  accepted shrink restarts the pass (a smaller case may enable shrinks
  that were inapplicable before, e.g. rank divisors of a smaller rank
  count); passes repeat until one full pass accepts nothing.

Probe outcomes distinguish WHY a candidate is not a reproducer:

- ``REPRODUCES``  — both engines executed and the disagreement predicate
  holds (the candidate is a reproducer);
- ``VANISHED``    — both engines executed, predicate false (the shrink
  destroyed the disagreement — the most informative rejection: it
  localizes the disagreement to what the shrink removed);
- ``ERROR_A``/``ERROR_B`` — one engine cannot execute the candidate
  (capability/feasibility boundary; the error text is preserved);
- ``INFEASIBLE``  — the candidate violates a case-space invariant of the
  driver (e.g. divisibility guards) before any engine runs.

The VANISHED-vs-ERROR distinction is the minimizer's localization
contribution: a disagreement that VANISHES when ops are removed is
op-count-dependent; one that survives to one op but vanishes when the
payload shrinks is size-dependent; one that ERRORS below a rank count has
a feasibility floor — each shape is a different defect signature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

REPRODUCES = "reproduces"
VANISHED = "vanished"
ERROR_A = "error_engine_a"
ERROR_B = "error_engine_b"
INFEASIBLE = "infeasible"

#: Terminal probe outcomes (REPRODUCES is the only accepting one).
ProbeOutcome = str


@dataclass(frozen=True)
class ProbeResult:
    """One probe execution: outcome plus its evidence.

    ``evidence`` carries the exact compared values (strings, exact
    Fractions) and engine error texts — enough to rebuild every audit
    number of the minimization without re-executing the engines.
    """

    outcome: ProbeOutcome
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def is_reproducer(self) -> bool:
        return self.outcome == REPRODUCES


class Probe(Protocol):
    def __call__(self, case: Any) -> ProbeResult:
        ...


@dataclass(frozen=True)
class CaseDelta:
    """One candidate shrink of the case.

    ``dimension``    — case dimension being shrunk ("payload_bytes",
                       "ranks", "ops", ...; driver's vocabulary);
    ``description``  — human-readable, committed to the record;
    ``apply``        — ``case -> case``; raising :class:`InfeasibleDelta`
                       marks the step inapplicable (a different case
                       invariant than an engine error).
    """

    dimension: str
    description: str
    apply: Callable[[Any], Any]


class InfeasibleDelta(Exception):
    """The shrink step cannot apply to this case (case-space invariant)."""


@dataclass(frozen=True)
class ProbeRecord:
    """One logged probe: the delta tried, the candidate, the outcome."""

    pass_index: int
    step_index: int
    dimension: str
    description: str
    candidate: Any
    outcome: ProbeOutcome
    evidence: dict[str, Any]
    accepted: bool


@dataclass(frozen=True)
class MinimizationResult:
    """The 1-minimal reproducer plus the complete deterministic search log."""

    initial_case: Any
    minimal_case: Any
    probes: tuple[ProbeRecord, ...]
    passes: int
    reproducer_found: bool

    def rejections_of_final_pass(self) -> tuple[ProbeRecord, ...]:
        """The 1-minimality certificate: every probe of the last pass."""
        return tuple(p for p in self.probes if p.pass_index == self.passes)

    def shrink_summary(self) -> dict[str, Any]:
        """Dimension-wise shrink factor of the minimized case vs initial."""
        return {
            "initial": _public(self.initial_case),
            "minimal": _public(self.minimal_case),
            "passes": self.passes,
            "probes": len(self.probes),
            "accepted_probes": sum(1 for p in self.probes if p.accepted),
        }


def _public(case: Any) -> Any:
    """Case as committed JSON data (dataclasses -> dicts, Fractions -> str)."""
    from dataclasses import fields, is_dataclass
    from fractions import Fraction

    if is_dataclass(case) and not isinstance(case, type):
        out = {}
        for f in fields(case):
            value = getattr(case, f.name)
            if isinstance(value, Fraction):
                out[f.name] = str(value)
            elif isinstance(value, (tuple, list)):
                out[f.name] = [_public(v) for v in value]
            elif is_dataclass(value) and not isinstance(value, type):
                out[f.name] = _public(value)
            else:
                out[f.name] = value
        return out
    if isinstance(case, (tuple, list)):
        return [_public(v) for v in case]
    return case


def minimize(
    case: Any,
    probe: Probe,
    ladder: Callable[[Any], list[CaseDelta]],
    *,
    max_probes: int = 4096,
) -> MinimizationResult:
    """Shrink ``case`` to a 1-minimal reproducer of the disagreement.

    ``ladder(case)`` must return the driver's ordered shrink steps for the
    CURRENT case (largest first within each dimension; the driver owns the
    dimension order). An accepting probe replaces the case and restarts
    the pass; a full rejecting pass ends the search.
    """
    if not probe(case).is_reproducer:
        return MinimizationResult(
            initial_case=case,
            minimal_case=case,
            probes=(),
            passes=0,
            reproducer_found=False,
        )

    current = case
    probes: list[ProbeRecord] = []
    pass_index = 0
    while True:
        pass_index += 1
        accepted_any = False
        steps = ladder(current)
        for step_index, delta in enumerate(steps):
            if len(probes) >= max_probes:
                raise RuntimeError(
                    f"minimizer exceeded max_probes={max_probes}; the ladder "
                    "is not making progress — this is a driver bug"
                )
            try:
                candidate = delta.apply(current)
            except InfeasibleDelta:
                continue  # not applicable; not a probe
            if candidate == current:
                continue
            try:
                result = probe(candidate)
            except Exception as exc:  # driver defects never kill the search
                result = ProbeResult(
                    outcome=INFEASIBLE,
                    evidence={"driver_error": f"{type(exc).__name__}: {exc}"},
                )
            record = ProbeRecord(
                pass_index=pass_index,
                step_index=step_index,
                dimension=delta.dimension,
                description=delta.description,
                candidate=_public(candidate),
                outcome=result.outcome,
                evidence=result.evidence,
                accepted=result.is_reproducer,
            )
            probes.append(record)
            if result.is_reproducer:
                current = candidate
                accepted_any = True
                break  # restart the pass on the smaller case
        if not accepted_any:
            break
    return MinimizationResult(
        initial_case=case,
        minimal_case=current,
        probes=tuple(probes),
        passes=pass_index,
        reproducer_found=True,
    )
