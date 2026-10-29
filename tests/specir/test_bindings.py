"""The binding registry gate: simulated_behavior must stay machine-checkable.

Every :data:`~essun.specir.bindings.BINDINGS` entry is re-verified against
the live requirement registry, the verified anchor registry, the live
backend module and the observable registry. The gate also cross-checks
the promotion table of the D1 record (tests/specir/test_dispositions.py
PROMOTED): a requirement may not appear in one and not the other.
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


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()
    return reg


def test_all_bindings_consistent(registry: AnchorRegistry) -> None:
    assert bindings.check_all(registry) == []
    bindings.assert_valid(registry)  # does not raise


def test_binding_registry_matches_promotion_table() -> None:
    bound = {b.requirement_id: b.disposition for b in bindings.BINDINGS}
    assert bound == PROMOTED, (
        "bindings and the PROMOTED table of the D1 record disagree — a "
        "promotion must update both in the same commit"
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
