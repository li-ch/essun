"""The binding registry gate: simulated_behavior must stay machine-checkable.

Every :data:`~essun.specir.bindings.BINDINGS` entry is re-verified against
the live requirement registry, the verified anchor registry, the live
backend module and the observable registry. The gate also cross-checks
the promotion table of the D1 record (tests/specir/test_dispositions.py
PROMOTED): a requirement may not appear in one and not the other.

Since G2 stage S4 (2026-10-30) PROMOTED carries TWO carrier kinds: a
``simulated_behavior`` promotion rides a live binding, while a
``conformance_test`` promotion rides an executable CHECK of the built
UEC profile (the D2 rule: a profile binding may reference only a
simulated_behavior requirement) — the parity below verifies each leg
against its own carrier.
"""

from __future__ import annotations

import dataclasses

import pytest

from essun.specir import bindings
from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_credits_flow_control import requirements as fc_requirements

# The reviewed promotion table (single source of truth for which
# promotions exist) — importing it pins registry-vs-record agreement,
# mirroring the disposition coverage tests.
from test_dispositions import PROMOTED

#: The built UEC profile artifact — the conformance carrier surface.
_PROFILE_ARTIFACT = "experiments/uec/semantic_profile.yaml"


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()
    return reg


def test_all_bindings_consistent(registry: AnchorRegistry) -> None:
    assert bindings.check_all(registry) == []
    bindings.assert_valid(registry)  # does not raise


def test_binding_registry_matches_promotion_table() -> None:
    # The simulated_behavior leg: every simulated_behavior promotion has
    # its live binding and every binding claims a promoted requirement —
    # exactly, in both directions.
    bound = {b.requirement_id: b.disposition for b in bindings.BINDINGS}
    simulated = {
        rid: disposition
        for rid, disposition in PROMOTED.items()
        if disposition == "simulated_behavior"
    }
    assert bound == simulated, (
        "bindings and the simulated_behavior promotions of the D1 record "
        "disagree — a promotion must update both in the same commit"
    )


def test_conformance_promotions_are_carried_by_profile_checks() -> None:
    # The conformance_test leg (G2 S4, mirroring the binding leg): every
    # conformance_test promotion is exercised by at least one check of
    # the BUILT profile whose location is a real file citing the
    # requirement — and no requirement carries conformance_test in the
    # live registry without a PROMOTED entry here (no silent promotion,
    # no silent check).
    import importlib
    import pathlib

    from essun.specir.profile_format import load_profile

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    profile = load_profile(repo_root / _PROFILE_ARTIFACT)
    conformance = {
        rid: disposition
        for rid, disposition in PROMOTED.items()
        if disposition == "conformance_test"
    }
    live_conformance = set()
    for module_name in bindings.UEC_REQUIREMENT_MODULES:
        module = importlib.import_module(module_name)
        live_conformance.update(
            req.requirement_id
            for req in module.requirements()
            if req.disposition == "conformance_test"
        )
    assert set(conformance) == live_conformance, (
        "the conformance_test promotions of the D1 record and the live "
        "stage registries disagree — update PROMOTED and the stage module "
        "in the same commit"
    )
    for rid in conformance:
        exercising = [
            check
            for check in profile.checks
            if rid in check.requirement_ids
            and check.kind in ("golden", "negative", "invariant")
        ]
        assert exercising, (
            f"{rid}: conformance_test promotion with no executable check "
            "in the built profile — land the check and regenerate "
            "experiments/uec/semantic_profile.yaml in the same commit"
        )
        for check in exercising:
            location = repo_root / check.location
            assert location.is_file(), (
                f"{rid}: check {check.check_id} names {check.location} "
                "which does not exist"
            )
            assert rid in location.read_text(encoding="utf-8"), (
                f"{rid}: check {check.check_id} lives in {check.location} "
                "but never cites the requirement it executes"
            )


def test_flagship_requirement_object_carries_the_binding_disposition() -> None:
    req = {r.requirement_id: r for r in fc_requirements()}["UEC11-FC-R02"]
    flagship = next(
        b for b in bindings.BINDINGS if b.requirement_id == "UEC11-FC-R02"
    )
    assert req.disposition == flagship.disposition == "simulated_behavior"
    assert tuple(req.anchor_ids) == flagship.anchor_ids


def test_golden_test_named_by_the_binding_exists() -> None:
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    for binding in bindings.BINDINGS:
        assert (repo_root / binding.golden_test).is_file(), (
            f"{binding.binding_id} names golden test {binding.golden_test} "
            "which does not exist"
        )


# -- negative: the gate fires on tampered bindings -----------------------------


def test_gate_fires_on_disposition_mismatch(registry: AnchorRegistry) -> None:
    flagship = bindings.BINDINGS[0]
    rogue = dataclasses.replace(flagship, disposition="unsupported")
    problems = bindings.check_binding(rogue, registry)
    assert any("disposition" in p for p in problems)


def test_gate_fires_on_unknown_requirement(registry: AnchorRegistry) -> None:
    flagship = bindings.BINDINGS[0]
    rogue = dataclasses.replace(flagship, requirement_id="UEC11-FC-R999")
    problems = bindings.check_binding(rogue, registry)
    assert any("not found in the live stage registries" in p for p in problems)


def test_gate_fires_on_missing_backend_parameter(registry: AnchorRegistry) -> None:
    flagship = bindings.BINDINGS[0]
    rogue = dataclasses.replace(
        flagship, parameters=flagship.parameters + ("not_a_config_field",)
    )
    problems = bindings.check_binding(rogue, registry)
    assert any("not a config field" in p for p in problems)


def test_gate_fires_on_capability_mismatch(registry: AnchorRegistry) -> None:
    flagship = bindings.BINDINGS[0]
    rogue = dataclasses.replace(flagship, capability="wrong_transport_model")
    problems = bindings.check_binding(rogue, registry)
    assert any("transport_model" in p for p in problems)


def test_gate_fires_on_invented_spec_constant(registry: AnchorRegistry) -> None:
    flagship = bindings.BINDINGS[0]
    rogue = dataclasses.replace(
        flagship,
        spec_derived_constants=(("tfc_credit_unit_bytes", "128", "UEC11-FC-R05"),),
    )
    problems = bindings.check_binding(rogue, registry)
    assert any("spec-derived constant" in p for p in problems)
    # ... and on a constant citing a requirement that does not exist
    rogue2 = dataclasses.replace(
        flagship,
        spec_derived_constants=(("tfc_credit_unit_bytes", "256", "UEC11-FC-R999"),),
    )
    assert any("cites unknown requirement" in p for p in bindings.check_binding(rogue2, registry))
