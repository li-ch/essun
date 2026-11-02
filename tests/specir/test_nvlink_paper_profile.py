"""M1 S2: NVLink-class paper-derived design-parameter tests.

Mirrors the UnifiedBus S2 tests
(``tests/specir/test_unifiedbus_paper_profile.py``) for the third fabric:
every object's anchors resolve in the M1 registry, the profile cites
EXACTLY the registry (no orphaned anchors, nothing outside citable),
evidence grades are derivable from the cited sources (no laundering), the
declared silences are FREE with anchored candidates, and the D1
dispositions follow the S5 structure-fact rule with frozen counts.  A
promotion must update EXPECTED_NV_COUNTS and PROMOTED_NV in the same
commit, in the open.
"""

from __future__ import annotations

import dataclasses

import pytest

from essun.specir.uec_link_transport import DISPOSITIONS
from essun.specir.nvlink_paper_profile import (
    CATEGORIES,
    EVIDENCE_GRADES,
    MAX_AS_REPORTED_WORDS,
    MAX_GAP_WORDS,
    SOURCE_EVIDENCE_GRADES,
    VALUE_KINDS,
    NVDesignParameter,
    NVFreeCandidate,
    NVFreeParameter,
    all_objects,
    anchor_ids,
    assert_valid,
    by_category,
    check_against_registry,
    free_parameters,
    initial_disposition,
    load_registry,
    parameters,
    requirements,
)

#: The M1 disposition record: exact per-disposition counts over the 24
#: design parameters.  Deliberately exact (same mechanism as the
#: UnifiedBus family): changing any disposition must update this dict in
#: the same commit — the "no silent promotion" gate.
EXPECTED_NV_COUNTS: dict[str, int] = {
    "informational": 19,
    "unsupported": 5,
}

#: Requirements consciously promoted past the initial rule.  A promotion
#: is valid ONLY with a binding registered in essun.specir.bindings whose
#: consistency check is green — none exists for the NVLink-class family.
PROMOTED_NV: dict[str, str] = {}


@pytest.fixture(scope="module")
def registry():
    return load_registry()


# -- positive bars -------------------------------------------------------------


def test_all_object_anchors_resolve_in_registry(registry) -> None:
    for obj in all_objects():
        resolved = registry.resolve(obj.anchor_ids)
        assert [a.anchor_id for a in resolved] == list(obj.anchor_ids)
    for param in free_parameters():
        for cand in param.candidates:
            assert registry.resolve([cand.anchor_id])[0].anchor_id == cand.anchor_id


def test_objects_cite_exactly_the_s1_registry(registry) -> None:
    registry_ids = {a.anchor_id for a in registry.anchors}
    used = anchor_ids()
    assert used <= registry_ids
    assert used == registry_ids  # every anchor backs at least one object


def test_stage_objects_present_and_unique() -> None:
    params = parameters()
    frees = free_parameters()
    assert len(params) == 24
    assert len(frees) == 6
    ids = [p.parameter_id for p in params] + [f.parameter_id for f in frees]
    assert len(ids) == len(set(ids))
    assert all(p.parameter_id.startswith("NVP-P") for p in params)
    assert all(f.parameter_id.startswith("NVP-F") for f in frees)


def test_categories_and_kinds_use_declared_vocabularies(registry) -> None:
    assert set(CATEGORIES) == registry.categories()
    for obj in all_objects():
        assert obj.category in CATEGORIES, obj.parameter_id
    for param in parameters():
        assert param.value_kind in VALUE_KINDS, param.parameter_id


def test_as_reported_values_are_bounded() -> None:
    for param in parameters():
        assert 0 < len(param.as_reported.split()) <= MAX_AS_REPORTED_WORDS
        assert param.as_reported.strip()
        assert param.evidence_grade in EVIDENCE_GRADES


def test_free_parameters_are_marked_free_and_bounded() -> None:
    for param in free_parameters():
        assert param.domain == "FREE"
        assert 0 < len(param.gap.split()) <= MAX_GAP_WORDS
        assert param.anchor_ids  # gap context must be anchored too


def test_m1_silences_are_marked_free() -> None:
    by_name = {p.name: p for p in free_parameters()}
    for name in (
        "per_link_line_rate",
        "per_hop_latency_current_gen",
        "flow_control_mechanism",
    ):
        assert name in by_name, name
        assert by_name[name].domain == "FREE"
    per_link = by_name["per_link_line_rate"]
    cand_anchors = {c.anchor_id for c in per_link.candidates}
    assert cand_anchors == {
        "NVP-NVL72-1-PERGPU-1.8TB",
        "NVP-LI-2-V100-LINKS-BW",
    }
    # and no design parameter may smuggle a per-link rate value in
    assert all(p.name != "per_link_line_rate" for p in parameters())


def test_evidence_grades_derive_from_cited_sources(registry) -> None:
    assert set(SOURCE_EVIDENCE_GRADES) == set(registry.sources)
    for param in parameters():
        grades = {
            SOURCE_EVIDENCE_GRADES[a.source_id]
            for a in registry.resolve(param.anchor_ids)
        }
        assert param.evidence_grade in grades, param.parameter_id
    # the three grades are all actually in use
    used = {p.evidence_grade for p in parameters()}
    assert set(EVIDENCE_GRADES) == used


def test_vendor_and_tracker_figures_are_labeled(registry) -> None:
    for param in parameters():
        source_ids = {a.source_id for a in registry.resolve(param.anchor_ids)}
        if {"PUB-NV-GB200-UG", "PUB-NV-GB200-NVL72"} & source_ids:
            assert param.evidence_grade == "VENDOR_CLAIMED", param.parameter_id
        if "PUB-NV-NCCL-1054" in source_ids:
            assert param.evidence_grade == "OFFICIAL_PUBLIC_PAGE", param.parameter_id


def test_tpu_class_member_parameters_say_so() -> None:
    # Class-member parameters describe TPU v4 ICI, never NVIDIA hardware;
    # their names and statements must carry the provenance.
    tpu = {p.name for p in parameters() if p.name.startswith("tpu_")}
    assert {"tpu_ici_links", "tpu_ici_scale", "tpu_ici_topology"} <= tpu
    for param in parameters():
        if param.name.startswith("tpu_"):
            assert "TPU" in param.as_reported or "class member" in param.as_reported


def test_by_category_helpers_agree() -> None:
    for category in CATEGORIES:
        objs = by_category(category)
        assert objs, f"category {category} has no objects"
        assert all(o.category == category for o in objs)
    assert sum(len(by_category(c)) for c in CATEGORIES) == len(all_objects())


def test_assert_valid_passes_on_real_registry(registry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- D1 dispositions -----------------------------------------------------------


def test_requirements_alias_is_the_design_parameters() -> None:
    assert requirements() == parameters()
    assert all(p.disposition for p in requirements())


def test_initial_disposition_rule_is_conservative() -> None:
    for kind in ("DESIGN_CONSTANT", "DESIGN_CLASS", "DESIGN_DEFAULT"):
        assert initial_disposition(kind) == "informational"
    for kind in ("REPORTED_MEASURE", "BEHAVIOR", "COMPONENT"):
        assert initial_disposition(kind) == "unsupported"
    assert not {"constraint", "simulated_behavior", "conformance_test"} & {
        initial_disposition(kind) for kind in VALUE_KINDS
    }


def test_every_parameter_carries_a_valid_disposition() -> None:
    for param in parameters():
        assert param.disposition in DISPOSITIONS, param.parameter_id


def test_initial_assignment_follows_the_s5_rule() -> None:
    for param in parameters():
        expected = PROMOTED_NV.get(
            param.parameter_id, initial_disposition(param.value_kind)
        )
        assert param.disposition == expected, (
            f"{param.parameter_id}: {param.value_kind} -> "
            f"{param.disposition!r} deviates from the initial rule (or is "
            "not a registered promotion); update EXPECTED_NV_COUNTS and "
            "PROMOTED_NV in the same commit and say why"
        )


def test_disposition_counts_are_the_frozen_m1_record() -> None:
    counts: dict[str, int] = {}
    for param in parameters():
        counts[param.disposition] = counts.get(param.disposition, 0) + 1
    assert counts == EXPECTED_NV_COUNTS
    assert sum(EXPECTED_NV_COUNTS.values()) == len(parameters()) == 24


def test_no_executed_disposition_without_a_promotion() -> None:
    executed = ("constraint", "simulated_behavior", "conformance_test")
    assert PROMOTED_NV == {}
    for param in parameters():
        assert param.disposition not in executed, param.parameter_id


# -- negative bars: dangling anchors, grade laundering, malformed objects ------


def test_check_rejects_parameter_without_disposition(
    registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.nvlink_paper_profile as mod

    rogue = dataclasses.replace(parameters()[0], disposition="")
    monkeypatch.setattr(mod, "_PARAMETERS", mod._PARAMETERS + (rogue,))
    problems = mod.check_against_registry(registry)
    assert any("missing disposition" in p for p in problems)
    with pytest.raises(mod.ProfileObjectError):
        mod.assert_valid(registry)


def test_check_rejects_object_with_dangling_anchor(
    registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.nvlink_paper_profile as mod

    rogue = NVDesignParameter(
        parameter_id="NVP-P-ROGUE-1",
        name="rogue",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="A rogue value citing nothing.",
        unit="",
        anchor_ids=("NVP-NO-SUCH-ANCHOR",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    )
    monkeypatch.setattr(mod, "_PARAMETERS", mod._PARAMETERS + (rogue,))
    problems = mod.check_against_registry(registry)
    assert any("dangling anchor ids" in p for p in problems)


def test_check_rejects_free_parameter_with_dangling_candidate(
    registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.nvlink_paper_profile as mod

    rogue = NVFreeParameter(
        parameter_id="NVP-F-ROGUE-1",
        name="rogue_gap",
        category="latency",
        gap="A rogue gap with a dangling candidate.",
        anchor_ids=("NVP-LI-3-NVLINK-LATENCY",),
        candidates=(
            NVFreeCandidate(
                label="dangling candidate",
                anchor_id="NVP-NO-SUCH-CANDIDATE",
                evidence_grade="PAPER_REPORTED",
            ),
        ),
    )
    monkeypatch.setattr(mod, "_FREE_PARAMETERS", mod._FREE_PARAMETERS + (rogue,))
    problems = mod.check_against_registry(registry)
    assert any("dangling anchor ids" in p for p in problems)


def test_check_rejects_grade_laundering(
    registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.nvlink_paper_profile as mod

    laundered = NVDesignParameter(
        parameter_id="NVP-P-ROGUE-2",
        name="laundered",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="A vendor-page figure typed as a paper measurement.",
        unit="",
        anchor_ids=("NVP-NVL72-1-PERGPU-1.8TB",),  # vendor source
        evidence_grade="PAPER_REPORTED",  # not derivable
        disposition="informational",
    )
    monkeypatch.setattr(mod, "_PARAMETERS", (laundered,))
    problems = mod.check_against_registry(registry)
    assert any("not derivable from anchor" in p for p in problems)


def test_check_rejects_malformed_objects(
    registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.nvlink_paper_profile as mod

    rogue = NVDesignParameter(
        parameter_id="NVP-P-ROGUE-3",
        name="malformed",
        category="quirks",
        value_kind="WISH",
        as_reported="word " * (MAX_AS_REPORTED_WORDS + 1),
        unit="",
        anchor_ids=("NVP-LI-2-NVSWITCH-CROSSBAR",),
        evidence_grade="TRUST_ME",
        disposition="unsupported",
    )
    monkeypatch.setattr(mod, "_PARAMETERS", (rogue,))
    problems = mod.check_against_registry(registry)
    assert any("unknown category" in p for p in problems)
    assert any("unknown value_kind" in p for p in problems)
    assert any("words" in p for p in problems)
    assert any("unknown evidence_grade" in p for p in problems)


def test_free_parameter_domain_must_stay_free(
    registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.nvlink_paper_profile as mod

    rogue = dataclasses.replace(
        free_parameters()[0],
        domain="FIXED",
        gap="",
    )
    monkeypatch.setattr(mod, "_FREE_PARAMETERS", (rogue,))
    problems = mod.check_against_registry(registry)
    assert any("must stay domain=FREE" in p for p in problems)
    assert any("empty gap" in p for p in problems)
