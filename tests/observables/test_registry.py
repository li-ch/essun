"""Observable registry: kind/failure-policy behavior (task T012).

The registry is the contract layer ValidationEngine consumes; these tests
pin the policy semantics per kind:
- exact: violation raises (a bug, not a finding);
- bounded: tolerance + validity domain required at registration,
  violations are returned findings, not raises;
- analytical: identity citation required, observations pass as cited.
"""

from fractions import Fraction

import pytest

from essun.observables import (
    ANALYTICAL,
    BOUNDED,
    EXACT,
    ObservableSpec,
    ObservableViolationError,
    ValidityDomain,
    check,
    lookup,
    register,
    registered,
)


def test_builtin_observables_registered():
    assert "O-CONSERVATION" in registered()
    assert "O-CCT" in registered()
    conservation = lookup("O-CONSERVATION")
    assert conservation.kind == EXACT
    assert conservation.unit == "bytes"
    assert conservation.failure_policy == "violation_is_bug"
    cct = lookup("O-CCT")
    assert cct.kind == ANALYTICAL
    assert cct.failure_policy == "identity_cited"
    # The citation must name the identity and its free parameters.
    assert "free parameters" in cct.identity
    assert "B" in cct.identity and "L" in cct.identity


def test_o_conservation_labeled_algebraic_self_check():
    # O6 honesty fix (increment 5a): everywhere O-CONSERVATION is surfaced it
    # must be labeled an algebraic self-check of the model's own accounting,
    # not an independent physical check. The registry is one of those
    # surfaces; the L0 module docstrings and the README row are the others.
    description = lookup("O-CONSERVATION").description
    assert "ALGEBRAIC SELF-CHECK" in description
    assert "NOT an independent physical check" in description


def test_exact_clean_observation_passes():
    result = check(
        lookup("O-CONSERVATION"),
        {"kind": "exact", "ops_checked": 6, "violations": 0, "total_wire_bytes_exact": "229376"},
    )
    assert result.status == "pass"
    assert result.observable_id == "O-CONSERVATION"


def test_exact_violation_raises_as_bug():
    # An exact violation is a model bug: it must raise (and count as an
    # assertion failure), never come back as a "finding".
    with pytest.raises(ObservableViolationError, match="bug"):
        check(
            lookup("O-CONSERVATION"),
            {"kind": "exact", "ops_checked": 6, "violations": 2},
        )
    assert issubclass(ObservableViolationError, AssertionError)


def test_exact_observation_missing_violations_field_rejected():
    with pytest.raises(ValueError, match="violations"):
        check(lookup("O-CONSERVATION"), {"kind": "exact", "ops_checked": 6})


def test_kind_mismatch_rejected():
    with pytest.raises(ValueError, match="declares kind"):
        check(lookup("O-CONSERVATION"), {"kind": "analytical"})
    with pytest.raises(ValueError, match="declares kind"):
        check(lookup("O-CCT"), {"kind": "exact"})


def test_non_mapping_observation_rejected():
    with pytest.raises(ValueError, match="mapping"):
        check(lookup("O-CONSERVATION"), [1, 2, 3])


def test_analytical_observation_passes_identity_cited():
    # Real O-CCT observation shape as emitted by the L0 backends.
    observation = {
        "kind": "analytical",
        "ops": 6,
        "completion_time_ns_mean_exact": "3248",
        "completion_time_ns_mean": 3248.0,
        "completion_time_ns_max": 3248.0,
    }
    result = check(lookup("O-CCT"), observation)
    assert result.status == "identity_cited"
    assert "l0.py" in result.detail


def test_bounded_without_validity_domain_rejected_at_registration():
    with pytest.raises(ValueError, match="validity domain"):
        register(
            ObservableSpec(
                observable_id="O-TEST-NODOMAIN",
                kind=BOUNDED,
                unit="ns",
                tolerance=Fraction(1, 10),
            )
        )


def test_bounded_without_tolerance_rejected_at_registration():
    with pytest.raises(ValueError, match="tolerance"):
        register(
            ObservableSpec(
                observable_id="O-TEST-NOTOL",
                kind=BOUNDED,
                unit="ns",
                validity_domain=ValidityDomain(topology="ring8_free_v1"),
            )
        )


def test_bounded_empty_domain_rejected_at_registration():
    with pytest.raises(ValueError, match="validity domain"):
        register(
            ObservableSpec(
                observable_id="O-TEST-EMPTYDOMAIN",
                kind=BOUNDED,
                unit="ns",
                tolerance=Fraction(1),
                validity_domain=ValidityDomain(),
            )
        )


def test_analytical_without_identity_rejected_at_registration():
    with pytest.raises(ValueError, match="identity"):
        register(ObservableSpec(observable_id="O-TEST-NOIDENT", kind=ANALYTICAL, unit="ns"))


def test_unknown_kind_rejected_at_registration():
    with pytest.raises(ValueError, match="not in"):
        register(ObservableSpec(observable_id="O-TEST-BADKIND", kind="statistical", unit="ns"))


def test_registry_is_append_only_on_ids():
    spec = ObservableSpec(observable_id="O-TEST-DUP", kind=EXACT, unit="bytes")
    register(spec)
    register(spec)  # identical re-registration is idempotent
    with pytest.raises(ValueError, match="append-only"):
        register(ObservableSpec(observable_id="O-TEST-DUP", kind=EXACT, unit="ns"))


def test_lookup_unknown_observable_lists_registered():
    with pytest.raises(ValueError, match="not registered"):
        lookup("O-DOES-NOT-EXIST")


def _bounded_spec():
    return register(
        ObservableSpec(
            observable_id="O-TEST-BWBOUNDED",
            kind=BOUNDED,
            unit="ns",
            tolerance=Fraction(1, 10),
            validity_domain=ValidityDomain(
                topology="ring8_free_v1",
                implementation="analytical L0",
                parameters=(("link_bytes_per_ns", "64"), ("hop_latency_ns", "200")),
            ),
        )
    )


def test_bounded_within_tolerance_passes_exactly():
    spec = _bounded_spec()
    # |3248.05 - 3248| = 1/20 <= 1/10, decided by exact Fraction arithmetic.
    result = check(spec, {"kind": "bounded", "value": "3248.05", "expected": "3248"})
    assert result.status == "pass"
    assert "ring8_free_v1" in result.detail


def test_bounded_outside_tolerance_is_a_finding_not_a_raise():
    spec = _bounded_spec()
    result = check(spec, {"kind": "bounded", "value": 3248, "expected": 4000})
    assert result.status == "violation"
    assert "tolerance=1/10" in result.detail


def test_bounded_missing_value_fields_rejected():
    spec = _bounded_spec()
    with pytest.raises(ValueError, match="'value'"):
        check(spec, {"kind": "bounded", "expected": 3248})
    with pytest.raises(ValueError, match="'expected'"):
        check(spec, {"kind": "bounded", "value": 3248})
