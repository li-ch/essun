"""Observable registry: what is measured, with which failure policy, and
over what validity domain.

This is the contract layer that ``ValidationEngine.check_invariants`` and
``compare`` (IMPLEMENTATION_GUIDE §5) consume: every observable id the
platform can report must be registered here with an explicit kind and
failure policy *before* a backend may emit it.

Kinds and failure policies:

- ``exact``    — an identity/conservation obligation checked by exact
                 arithmetic. A violation is a *bug* (model or backend
                 defect), never a tunable parameter: :func:`check` raises.
- ``logical``  — a logical-traffic/DAG obligation: the emitted traffic
                 pattern must satisfy an exact relation *under the same
                 declared algorithm* (per the validation framework table:
                 "Logical traffic/DAG — exact under the same declared
                 algorithm"). FAIL: a structural violation of the declared
                 relation is a bug and raises, exactly like ``exact``.
                 WARN: an advisory quantity beyond its declared threshold
                 is a *finding* (returned, never raised) — a candidate for
                 validity-domain refinement, not a bug. Registration without
                 a relation citation is rejected.
- ``bounded``  — a numeric obligation with a tolerance, valid only inside a
                 declared :class:`ValidityDomain`. A violation is a
                 *finding* (counterexample candidate to minimize and
                 classify), reported not raised. Registration without both
                 tolerance and a non-empty domain is rejected. The
                 comparison form is either ``absolute``
                 (``|expected - value| <= tolerance``) or ``relative``
                 (``|value/expected - 1| <= tolerance``; a zero reference is
                 a contract error, not a finding) — the ratio-vs-bound form
                 the differential-validation path compares backends with.
- ``analytical`` — a closed-form model output, not an obligation against
                 reality. It must cite the identity it instantiates
                 (equation + free parameters); ``check`` verifies the
                 observation declares the registered kind and passes.

All comparisons use :class:`fractions.Fraction` (exact; floats enter via
``str()`` so decimal literals are interpreted exactly), matching the L0
backends' arithmetic policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

EXACT = "exact"
LOGICAL = "logical"
BOUNDED = "bounded"
ANALYTICAL = "analytical"

KINDS = (EXACT, LOGICAL, BOUNDED, ANALYTICAL)

# Comparison forms for bounded specs (statistical/bounded class).
ABSOLUTE = "absolute"
RELATIVE = "relative"
FORMS = (ABSOLUTE, RELATIVE)

# Derived failure policies (one per kind); a spec never carries these fields.
FAILURE_POLICIES = {
    EXACT: "violation_is_bug",
    LOGICAL: "exact_relation_violation_is_bug_with_warn",
    BOUNDED: "tolerance_and_validity_domain",
    ANALYTICAL: "identity_cited",
}


class ObservableViolationError(AssertionError):
    """An exact (identity/conservation) obligation was violated.

    Subclasses :class:`AssertionError` because an exact violation is a
    model/backend bug, not an experimental outcome.
    """


@dataclass(frozen=True)
class ValidityDomain:
    """The domain inside which a bounded obligation holds.

    Fields mirror the experiment manifest's ``validity_domain`` block;
    a bounded spec must declare at least one non-empty field at
    registration. Free parameters are recorded as ``(name, value)`` pairs —
    explicitly free, never standard-derived (provenance rules).
    """

    topology: str = ""
    workload: str = ""
    implementation: str = ""
    parameters: tuple[tuple[str, str], ...] = ()

    def is_declared(self) -> bool:
        return bool(
            self.topology or self.workload or self.implementation or self.parameters
        )

    def to_dict(self) -> dict:
        return {
            "topology": self.topology,
            "workload": self.workload,
            "implementation": self.implementation,
            "parameters": [list(pair) for pair in self.parameters],
        }


@dataclass(frozen=True)
class ObservableSpec:
    observable_id: str
    kind: str
    unit: str
    description: str = ""
    # bounded only: obligation tolerance (exact Fraction; never None for bounded)
    tolerance: Fraction | None = None
    # bounded only: where the obligation holds
    validity_domain: ValidityDomain | None = None
    # analytical only: citation of the identity being instantiated
    identity: str = ""
    # logical only: the exact traffic-pattern relation under the declared
    # algorithm (the analogue of ``identity`` for logical-traffic specs)
    relation: str = ""
    # logical only: optional advisory bound. FAIL is reserved for structural
    # violations of ``relation`` (bugs, raised); a ``warn_value`` beyond this
    # threshold is a WARN finding (returned, never raised). None declares
    # that no advisory quantity is tracked at this fidelity.
    warn_threshold: Fraction | None = None
    # bounded only: comparison form (absolute | relative); default absolute
    form: str = ABSOLUTE

    @property
    def failure_policy(self) -> str:
        return FAILURE_POLICIES[self.kind]


@dataclass(frozen=True)
class CheckResult:
    """Outcome of applying a spec's failure policy to one observation."""

    observable_id: str
    kind: str
    status: str  # "pass" | "violation" | "identity_cited"
    detail: str


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

_REGISTRY: dict[str, ObservableSpec] = {}


def register(spec: ObservableSpec) -> ObservableSpec:
    """Validate and register a spec; returns it.

    Re-registering a byte-identical spec is idempotent; the same id with
    different content is rejected (the registry is append-only, like the
    evidence store).
    """
    if not spec.observable_id:
        raise ValueError("observable id must be a non-empty string")
    if spec.kind not in KINDS:
        raise ValueError(f"kind {spec.kind!r} not in {KINDS}")
    if not spec.unit:
        raise ValueError(f"observable {spec.observable_id}: unit is required")

    if spec.kind == BOUNDED:
        if spec.tolerance is None:
            raise ValueError(
                f"observable {spec.observable_id}: bounded spec requires a tolerance"
            )
        if spec.form not in FORMS:
            raise ValueError(
                f"observable {spec.observable_id}: bounded form {spec.form!r} "
                f"not in {FORMS}"
            )
        if spec.validity_domain is None or not spec.validity_domain.is_declared():
            raise ValueError(
                f"observable {spec.observable_id}: bounded spec requires a "
                "non-empty validity domain"
            )
    if spec.kind == LOGICAL:
        if not spec.relation:
            raise ValueError(
                f"observable {spec.observable_id}: logical spec requires a "
                "relation citation (the exact pattern relation under the "
                "declared algorithm)"
            )
        if spec.warn_threshold is not None and spec.warn_threshold < 0:
            raise ValueError(
                f"observable {spec.observable_id}: warn_threshold must be a "
                "non-negative exact Fraction"
            )
    if spec.kind == ANALYTICAL and not spec.identity:
        raise ValueError(
            f"observable {spec.observable_id}: analytical spec requires an "
            "identity citation"
        )

    existing = _REGISTRY.get(spec.observable_id)
    if existing is not None:
        if existing == spec:
            return existing
        raise ValueError(
            f"observable {spec.observable_id} already registered with a "
            "different spec; the registry is append-only"
        )
    _REGISTRY[spec.observable_id] = spec
    return spec


def lookup(observable_id: str) -> ObservableSpec:
    try:
        return _REGISTRY[observable_id]
    except KeyError:
        raise ValueError(
            f"observable {observable_id!r} is not registered; "
            f"registered: {sorted(_REGISTRY)}"
        ) from None


def registered() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


# --------------------------------------------------------------------------
# Policy application
# --------------------------------------------------------------------------


def _as_fraction(value: Any) -> Fraction:
    # str() first so floats/decimal strings are interpreted exactly.
    return Fraction(str(value))


def check(spec: ObservableSpec, observation: Mapping[str, Any]) -> CheckResult:
    """Apply ``spec``'s failure policy to one emitted observation.

    Raises :class:`ObservableViolationError` for ``exact`` violations (a
    bug), and :class:`ValueError` for contract mismatches (missing fields,
    kind disagreement) so a backend cannot pass off-shape data as an
    observable. ``bounded`` violations are *returned* (findings), and
    ``analytical`` observations pass as identity-cited model output.
    """
    if not isinstance(observation, Mapping):
        raise ValueError(
            f"observable {spec.observable_id}: observation must be a mapping, "
            f"got {type(observation).__name__}"
        )
    kind = observation.get("kind")
    if kind != spec.kind:
        raise ValueError(
            f"observable {spec.observable_id}: observation declares kind "
            f"{kind!r} but the registered spec is {spec.kind!r}"
        )

    if spec.kind == EXACT:
        if "violations" not in observation:
            raise ValueError(
                f"observable {spec.observable_id}: exact observation must "
                "report a 'violations' count"
            )
        violations = observation["violations"]
        if violations != 0:
            raise ObservableViolationError(
                f"observable {spec.observable_id}: {violations} exact-identity "
                "violation(s); this is a bug, not a tunable parameter"
            )
        return CheckResult(
            observable_id=spec.observable_id,
            kind=spec.kind,
            status="pass",
            detail=f"{observation.get('ops_checked', '?')} op(s) checked, 0 violations",
        )

    if spec.kind == LOGICAL:
        # FAIL (structural): the emitted pattern violates the exact relation
        # declared for the algorithm — a bug, raised like an exact violation.
        if "violations" not in observation:
            raise ValueError(
                f"observable {spec.observable_id}: logical observation must "
                "report a 'violations' count"
            )
        violations = observation["violations"]
        if violations != 0:
            raise ObservableViolationError(
                f"observable {spec.observable_id}: {violations} logical-pattern "
                "violation(s) of the declared algorithm relation; this is a "
                "bug, not a tunable parameter"
            )
        # WARN (advisory): an out-of-threshold advisory quantity is a finding
        # for validity-domain refinement — returned, never raised. The spec
        # and the observation must agree on whether an advisory quantity is
        # tracked at all.
        warn_value = observation.get("warn_value")
        if spec.warn_threshold is None:
            if warn_value is not None:
                raise ValueError(
                    f"observable {spec.observable_id}: spec declares no "
                    "warn_threshold but the observation carries a 'warn_value'"
                )
            status, detail = "pass", (
                f"0 pattern violations of relation: {spec.relation}"
            )
        else:
            if warn_value is None:
                raise ValueError(
                    f"observable {spec.observable_id}: spec declares "
                    f"warn_threshold={spec.warn_threshold} but the "
                    "observation carries no 'warn_value'"
                )
            advisory = _as_fraction(warn_value)
            if advisory > spec.warn_threshold:
                status = "warn"
                detail = (
                    f"advisory {advisory} > warn_threshold={spec.warn_threshold} "
                    f"(finding, not a bug); relation holds: {spec.relation}"
                )
            else:
                status = "pass"
                detail = (
                    f"advisory {advisory} <= warn_threshold={spec.warn_threshold}; "
                    f"relation holds: {spec.relation}"
                )
        return CheckResult(
            observable_id=spec.observable_id,
            kind=spec.kind,
            status=status,
            detail=detail,
        )

    if spec.kind == ANALYTICAL:
        return CheckResult(
            observable_id=spec.observable_id,
            kind=spec.kind,
            status="identity_cited",
            detail=spec.identity,
        )

    # bounded: tolerance inside a declared domain; violations are findings.
    for required in ("value", "expected"):
        if required not in observation:
            raise ValueError(
                f"observable {spec.observable_id}: bounded observation "
                f"requires {required!r}"
            )
    value = _as_fraction(observation["value"])
    expected = _as_fraction(observation["expected"])
    domain = spec.validity_domain.to_dict() if spec.validity_domain else {}
    if spec.form == RELATIVE:
        # Ratio-vs-bound: |value/expected - 1| <= tolerance. A zero
        # reference makes the ratio undefined — a contract error, not a
        # finding (a finding must be a comparable counterexample).
        if expected == 0:
            raise ValueError(
                f"observable {spec.observable_id}: relative-form bounded "
                "observation declares expected=0; the reference of a ratio "
                "must be nonzero"
            )
        delta = value / expected - 1
        within = abs(delta) <= spec.tolerance
        return CheckResult(
            observable_id=spec.observable_id,
            kind=spec.kind,
            status="pass" if within else "violation",
            detail=(
                f"|relerr|={abs(delta)} vs tolerance={spec.tolerance} "
                f"within domain={domain}"
            ),
        )
    delta = expected - value
    within = abs(delta) <= spec.tolerance
    return CheckResult(
        observable_id=spec.observable_id,
        kind=spec.kind,
        status="pass" if within else "violation",
        detail=(
            f"|delta|={abs(delta)} vs tolerance={spec.tolerance} "
            f"within domain={domain}"
        ),
    )


# --------------------------------------------------------------------------
# Built-in registrations (the vertical slice's two observables)
# --------------------------------------------------------------------------

O_CONSERVATION = register(
    ObservableSpec(
        observable_id="O-CONSERVATION",
        kind=EXACT,
        unit="bytes",
        description=(
            "Wire conservation per collective: total bytes sent across all "
            "ranks equals total bytes received equals 2*(r-1)*M — every wire "
            "byte is sent once and received once; nothing is created or lost. "
            "Checked by exact Fraction equality in each L0 backend. Honesty "
            "label (O6): this is an ALGEBRAIC SELF-CHECK of the model's own "
            "byte accounting — the sent-bytes ledger equals the identity's "
            "construction by design — NOT an independent physical check; a "
            "cross-fidelity sent-vs-received comparison becomes meaningful "
            "only once a packet/FLIT backend exists."
        ),
    )
)

O_CCT = register(
    ObservableSpec(
        observable_id="O-CCT",
        kind=ANALYTICAL,
        unit="ns",
        description=(
            "Collective completion time under a closed-form L0 transport "
            "identity, with mean/max aggregates (exact Fractions serialized "
            "alongside floats)."
        ),
        identity=(
            "L0 closed-form completion-time identities with free parameters "
            "B (bytes/ns) and L (ns), never standard-derived: ring "
            "t = 2*(r-1)/r * M/B + 2*(r-1)*L (src/essun/backends/analytical/"
            "l0.py) and the ladder stage variants in l0_crossbar.py, "
            "l0_torus2d.py, l0_recursive_doubling.py, "
            "l0_phase_collectives.py; plus the TFC credit-window variant "
            "t = 2*(r-1)/r * M/min(B, W/(L+L_cr)) + 2*(r-1)*L with FREE "
            "window W and credit-return latency L_cr (l0_tfc.py — since G8 "
            "the declared steady-state abstraction of the credit "
            "obligation automaton, which executes UEC requirement "
            "UEC11-FC-R02 via binding BIND-UEC11-FC-R02-AUTOMATON; the "
            "256-byte credit unit is the one spec-derived constant, "
            "UEC11-FC-R05)"
        ),
    )
)


# --------------------------------------------------------------------------
# Built-in registrations: the logical-traffic
# class instance and the statistical/bounded ratio-vs-bound builtin.
# --------------------------------------------------------------------------

O_TRAFFIC_IMBALANCE = register(
    ObservableSpec(
        observable_id="O-TRAFFIC-IMBALANCE",
        kind=LOGICAL,
        unit="bytes",
        description=(
            "Per-rank imbalance of the logical wire-traffic pattern: for "
            "each rank, total bytes sent to its ring successor, summed over "
            "the run's ops. Under the per-rank-symmetric chunked-ring "
            "AllReduce algorithm every rank sends exactly "
            "2*(r-1)/r*M per op, so the per-rank totals are exactly equal "
            "and the imbalance (max - min) is exactly 0 bytes. FAIL: any "
            "nonzero imbalance is a structural violation of the declared "
            "algorithm's pattern — a bug, raised. WARN: no advisory "
            "quantity is declared at L0 (warn_threshold=None): the pattern "
            "is exactly symmetric by construction, so there is no advisory "
            "band yet; advisory quantities (e.g. measured imbalance "
            "headroom) attach when a higher-fidelity backend emits this "
            "observable. Honesty label (O6 pattern): like O-CONSERVATION, "
            "at L0 this is an ALGEBRAIC SELF-CHECK of the model's own "
            "declared traffic pattern — NOT an independent physical "
            "measurement of hardware imbalance."
        ),
        relation=(
            "per-rank total wire bytes are exactly equal under the "
            "per-rank-symmetric declared algorithm (chunked ring: each rank "
            "sends 2*(r-1)/r*M per op to its single successor), i.e. "
            "max(per-rank totals) - min(per-rank totals) == 0 bytes exactly "
            "(src/essun/backends/analytical/l0.py, "
            "ring_per_rank_totals)"
        ),
        warn_threshold=None,
    )
)

O_CCT_RELERR = register(
    ObservableSpec(
        observable_id="O-CCT-RELERR",
        kind=BOUNDED,
        unit="ratio",
        description=(
            "Relative error of a mean collective completion time against a "
            "declared reference value of the same quantity — the "
            "ratio-vs-bound comparison the differential-validation path "
            "(cross-backend / cross-fidelity, e.g. L0 identity vs DES "
            "adapter on the same manifest) applies: "
            "|value/reference - 1| <= tolerance inside the validity domain. "
            "Failure policy (bounded): a violation is a FINDING — a "
            "counterexample candidate to minimize and classify — never a "
            "raise; tuning the tolerance to make curves match is forbidden "
            "(rule: classify, never tune). Tolerance policy: E0 zero-slack "
            "(tolerance = 0, every nonzero relative deviation is a finding) "
            "because no calibration basis exists yet; any nonzero tolerance "
            "must arrive through CGFR with a recorded evidence run, as a "
            "free parameter with provenance — never standard-derived."
        ),
        tolerance=Fraction(0),
        form=RELATIVE,
        validity_domain=ValidityDomain(
            topology="any declared fabric of the compared backends (free parameters)",
            workload="same workload file, same payload sizes (controlled comparison)",
            implementation=(
                "differential comparison of two declared backends on one "
                "manifest (sweeps delta column; future ValidationEngine)"
            ),
            parameters=(
                ("reference", "declared per comparison (baseline run or config)"),
                ("tolerance_policy", "E0 zero-slack; refine only via CGFR evidence"),
            ),
        ),
    )
)


def differential_observation(value_exact, reference_exact, quantity: str = "cct_mean_ns") -> dict:
    """Build the bounded relative-form observation for a differential check.

    The differential-validation path (sweeps, future ValidationEngine)
    compares the same quantity across two backends/configs; this helper
    packages a measured value and its declared reference into the
    observation shape ``check`` consumes for O-CCT-RELERR. Both arguments
    are exact values (Fraction/int/str); they are serialized via ``str()``
    so the observation carries exact arithmetic.
    """
    return {
        "kind": BOUNDED,
        "quantity": quantity,
        "observable_ref": "O-CCT-RELERR",
        "value": str(value_exact),
        "expected": str(reference_exact),
    }
