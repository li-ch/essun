"""D1 disposition gate: every UEC requirement carries an honest disposition.

Design doc D1 (2026-10-29): "anchored requirement count is not executable
coverage."  Every :class:`~essun.specir.uec_link_transport.UECRequirement`
must carry a ``disposition`` from :data:`DISPOSITIONS`
(constraint / simulated_behavior / conformance_test / informational /
unsupported / not_applicable), and the registry gate fails on a requirement
without one.

Bars enforced here:

- the vocabulary is exactly the six D1 values, no more, no fewer;
- every requirement object of all five stage modules carries a valid
  disposition and the stages' registry checks pass (the migration
  tools/migrate_dispositions.py assigned the initial values);
- a requirement WITHOUT a disposition is rejected by every stage's
  ``check_against_registry`` — the registry test fails, which is the D1 gate;
- an UNKNOWN disposition value is likewise rejected;
- the initial assignment follows the honest rule (DEFINITIONAL ->
  informational, every normative keyword -> unsupported) and the exact
  per-module counts are frozen: the migration never assigns
  constraint / simulated_behavior / conformance_test / not_applicable, so a
  requirement cannot silently become ``simulated_behavior`` — any promotion
  (the flagship slice) must consciously update EXPECTED_COUNTS here.
"""

from __future__ import annotations

import dataclasses
import importlib

import pytest

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_link_transport import (
    DISPOSITIONS,
    UECRequirement,
    disposition_problems,
    initial_disposition,
)

#: The five stage modules that own UEC requirement objects (S2 is the model
#: home; S3/S4/S5/S2b reuse its dataclass).
STAGE_MODULES: tuple[str, ...] = (
    "essun.specir.uec_link_transport",
    "essun.specir.uec_reliability_ordering",
    "essun.specir.uec_congestion_management",
    "essun.specir.uec_credits_flow_control",
    "essun.specir.uec_f07_mechanisms",
)

#: The migration record (tools/migrate_dispositions.py output, 2026-10-29)
#: plus the first conscious promotion. Deliberately exact: changing any
#: disposition must update this dict in the same commit, in the open —
#: that is the "no silent promotion" gate.
EXPECTED_COUNTS: dict[str, dict[str, int]] = {
    "essun.specir.uec_link_transport": {
        "informational": 22,
        "unsupported": 43,
    },
    "essun.specir.uec_reliability_ordering": {
        "informational": 43,
        "unsupported": 58,
    },
    "essun.specir.uec_congestion_management": {
        "informational": 42,
        "unsupported": 80,
    },
    "essun.specir.uec_credits_flow_control": {
        "informational": 32,
        "unsupported": 32,
        # Flagship slice 2026-10-29 (design doc D1 build order item 2):
        # UEC11-FC-R02 (TFC admission law) promoted to simulated_behavior
        # via binding BIND-UEC11-FC-R02-L0TFC (re-pointed at the
        # credit automaton as BIND-UEC11-FC-R02-AUTOMATON by G8,
        # 2026-10-30 — same disposition, same requirement, new backend;
        # golden test tests/golden/test_credit_automaton_golden.py).
        # G2 credit-family ladder S2 (2026-10-30, per the S1 plan in
        # experiments/uec/credit_family_inventory.md): UEC11-FC-R08
        # (ROUNDUP cell-quantized credit consumption) promoted to
        # simulated_behavior via binding BIND-UEC11-FC-R08-L0TFC; golden
        # test tests/golden/test_l0_tfc_cell_golden.py.
        "simulated_behavior": 2,
    },
    "essun.specir.uec_f07_mechanisms": {
        "informational": 49,
        "unsupported": 42,
    },
}

#: Requirements consciously promoted past the initial honest rule, with
#: the disposition granted. A promotion is valid ONLY with a binding
#: registered in essun.specir.bindings whose consistency check is green
#: (tests/specir/test_bindings.py) — keep this table tiny on purpose.
PROMOTED: dict[str, str] = {
    "UEC11-FC-R02": "simulated_behavior",  # BIND-UEC11-FC-R02-AUTOMATON (G8 re-point)
    "UEC11-FC-R08": "simulated_behavior",  # BIND-UEC11-FC-R08-L0TFC (G2 S2)
}


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()  # objects are checked against a verified registry
    return reg


@pytest.fixture(params=STAGE_MODULES)
def stage(request: pytest.FixtureRequest) -> object:
    return importlib.import_module(request.param)


# -- vocabulary ---------------------------------------------------------------


def test_dispositions_are_exactly_the_d1_six() -> None:
    assert set(DISPOSITIONS) == {
        "constraint",
        "simulated_behavior",
        "conformance_test",
        "informational",
        "unsupported",
        "not_applicable",
    }
    assert len(DISPOSITIONS) == 6


def test_initial_disposition_rule_is_conservative() -> None:
    # The migration rule never upgrades a requirement to an executed
    # disposition; only informational/unsupported are scriptable.
    assert initial_disposition("DEFINITIONAL") == "informational"
    for keyword in (
        "MUST",
        "MUST NOT",
        "SHALL",
        "SHALL NOT",
        "SHOULD",
        "SHOULD NOT",
        "MAY",
    ):
        assert initial_disposition(keyword) == "unsupported"


# -- the gate: every requirement carries a valid disposition -------------------


def test_every_requirement_has_a_valid_disposition(stage: object) -> None:
    reqs: tuple[UECRequirement, ...] = stage.requirements()  # type: ignore[attr-defined]
    assert reqs
    for req in reqs:
        assert req.disposition in DISPOSITIONS, (
            f"{req.requirement_id}: {req.disposition!r}"
        )


def test_stage_registry_check_passes_with_dispositions(
    stage: object, registry: AnchorRegistry
) -> None:
    # Post-migration the D1 gate is green for every stage.
    assert stage.check_against_registry(registry) == []  # type: ignore[attr-defined]
    stage.assert_valid(registry)  # type: ignore[attr-defined]


# -- the gate rejects requirements without (or outside) the vocabulary ----------


def test_check_rejects_requirement_without_disposition(
    stage: object, registry: AnchorRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    # THE D1 gate: strip a real requirement's disposition and the registry
    # check must flag it — a requirement object without a disposition is
    # invalid, in every stage module.
    real: UECRequirement = stage.requirements()[0]  # type: ignore[attr-defined]
    rogue = dataclasses.replace(real, disposition="")
    assert rogue.requirement_id == real.requirement_id
    monkeypatch.setattr(
        stage, "_REQUIREMENTS", stage._REQUIREMENTS + (rogue,)  # type: ignore[attr-defined]
    )
    problems = stage.check_against_registry(registry)  # type: ignore[attr-defined]
    assert any(
        f"{real.requirement_id}: missing disposition" in p for p in problems
    )
    with pytest.raises(stage.SemanticObjectError):  # type: ignore[attr-defined]
        stage.assert_valid(registry)  # type: ignore[attr-defined]


def test_check_rejects_unknown_disposition(
    stage: object, registry: AnchorRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    real: UECRequirement = stage.requirements()[0]  # type: ignore[attr-defined]
    rogue = dataclasses.replace(real, disposition="aspirational")
    monkeypatch.setattr(
        stage, "_REQUIREMENTS", stage._REQUIREMENTS + (rogue,)  # type: ignore[attr-defined]
    )
    problems = stage.check_against_registry(registry)  # type: ignore[attr-defined]
    assert any(
        f"{real.requirement_id}: unknown disposition" in p for p in problems
    )


def test_disposition_problems_helper_shapes() -> None:
    assert disposition_problems("X", "") == [
        "X: missing disposition (one of "
        f"{DISPOSITIONS})"
    ]
    assert disposition_problems("X", "simulated_someday") == [
        "X: unknown disposition 'simulated_someday' "
        f"(not in {DISPOSITIONS})"
    ]
    assert disposition_problems("X", "unsupported") == []


# -- the honest record: nothing silently becomes simulated_behavior ------------


def test_initial_assignment_follows_the_honest_rule(stage: object) -> None:
    reqs: tuple[UECRequirement, ...] = stage.requirements()  # type: ignore[attr-defined]
    for req in reqs:
        expected = PROMOTED.get(req.requirement_id, initial_disposition(req.keyword))
        assert req.disposition == expected, (
            f"{req.requirement_id}: {req.keyword} -> {req.disposition!r} "
            "deviates from the migration rule (or is not a registered "
            "promotion); update EXPECTED_COUNTS and PROMOTED in the same "
            "commit and say why"
        )


def test_migration_counts_are_the_frozen_record(stage: object) -> None:
    reqs: tuple[UECRequirement, ...] = stage.requirements()  # type: ignore[attr-defined]
    counts: dict[str, int] = {}
    for req in reqs:
        counts[req.disposition] = counts.get(req.disposition, 0) + 1
    assert counts == EXPECTED_COUNTS[stage.__name__], (  # type: ignore[attr-defined]
        "disposition counts drifted from the migration record; a promotion "
        "must consciously update EXPECTED_COUNTS (no silent "
        "simulated_behavior)"
    )


def test_executed_dispositions_are_exactly_the_promoted_table(stage: object) -> None:
    # The D1 starting point was zero executed requirements. The flagship
    # slice (2026-10-29) promoted exactly PROMOTED — every executed
    # disposition must appear in that reviewed table with a live binding;
    # anything else is a silent promotion and fails here.
    reqs: tuple[UECRequirement, ...] = stage.requirements()  # type: ignore[attr-defined]
    executed = ("constraint", "simulated_behavior", "conformance_test")
    for req in reqs:
        if req.disposition in executed:
            assert req.requirement_id in PROMOTED, (
                f"{req.requirement_id}: executed disposition "
                f"{req.disposition!r} without a PROMOTED entry — silent "
                "promotion; register the binding and the table entry in "
                "the same commit"
            )
            assert PROMOTED[req.requirement_id] == req.disposition
