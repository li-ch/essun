"""S2 design-parameter tests: UnifiedBus paper-derived profile (Q6).

Bars from the stage prompt: typed design parameters AS REPORTED, each
carrying paper anchors; free parameters where the papers are silent; tests
mirror Q1's — every object's anchors resolve in the registry, and a
negative test rejects an object with a dangling anchor. Additional bars
enforced here (the ladder honesty rule made mechanical):

- the profile cites EXACTLY the S1 registry anchors: every one of the 53
  anchors backs at least one object and nothing outside the registry is
  citable (this ladder has a single-stage anchor map, unlike Q1's
  mechanism-per-stage maps);
- evidence grades are honest: each declared grade is derivable from the
  sources its anchors cite, so vendor/marketing numbers can never enter
  the profile typed as paper measurements;
- the three FREE territories S1 marked (per-lane Gbit/s, latency
  breakdown, congestion control) are marked FREE with their anchored
  candidates, never invented values;
- D1 dispositions (ladder S5): every design parameter carries a valid
  disposition from the one D1 vocabulary, the initial assignment follows
  the honest structure-fact rule (DESIGN_CONSTANT / DESIGN_CLASS /
  DESIGN_DEFAULT -> informational; REPORTED_MEASURE / BEHAVIOR /
  COMPONENT -> unsupported — a profile executed by NO binding), and the
  exact counts are frozen below; nothing is simulated_behavior /
  constraint / conformance_test because no reviewed binding exists for
  UnifiedBus (a promotion must update EXPECTED_UB_COUNTS and PROMOTED_UB
  in the same commit, in the open).
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.uec_link_transport import DISPOSITIONS
from essun.specir.unifiedbus_paper_profile import (
    CATEGORIES,
    EVIDENCE_GRADES,
    MAX_AS_REPORTED_WORDS,
    MAX_GAP_WORDS,
    SOURCE_EVIDENCE_GRADES,
    VALUE_KINDS,
    UBDesignParameter,
    UBFreeCandidate,
    UBFreeParameter,
    all_objects,
    anchor_ids,
    assert_valid,
    by_category,
    check_against_registry,
    free_parameters,
    initial_disposition,
    parameters,
    requirements,
)
from essun.specir.unifiedbus_sources import PaperAnchorRegistry

#: The S5 disposition record (ladder S5, 2026-10-29): exact per-disposition
#: counts over the 54 design parameters.  Deliberately exact, mirroring
#: EXPECTED_COUNTS in tests/specir/test_dispositions.py: changing any
#: disposition must update this dict in the same commit — that is the
#: "no silent promotion" gate for the paper-derived family.
EXPECTED_UB_COUNTS: dict[str, int] = {
    "informational": 32,
    "unsupported": 22,
}

#: Requirements consciously promoted past the S5 initial rule.  A
#: promotion is valid ONLY with a binding registered in
#: essun.specir.bindings whose consistency check is green — none exists
#: for UnifiedBus, so the table stays empty on purpose.
PROMOTED_UB: dict[str, str] = {}


@pytest.fixture(scope="module")
def registry() -> PaperAnchorRegistry:
    reg = PaperAnchorRegistry.load()
    reg.assert_valid()  # objects are checked against a verified registry
    return reg


# -- positive bars -------------------------------------------------------------


def test_all_object_anchors_resolve_in_registry(registry: PaperAnchorRegistry) -> None:
    # The core bar: every design parameter, free parameter, and free
    # candidate anchor resolves fully in the S1 registry.
    for obj in all_objects():
        resolved = registry.resolve(obj.anchor_ids)
        assert [a.anchor_id for a in resolved] == list(obj.anchor_ids)
    for param in free_parameters():
        for cand in param.candidates:
            assert registry.resolve([cand.anchor_id])[0].anchor_id == cand.anchor_id


def test_objects_cite_exactly_the_s1_registry(registry: PaperAnchorRegistry) -> None:
    # Stage discipline, Q1-style, adapted to this single-stage ladder: the
    # S2 profile must cover every S1 anchor (none orphaned) and may cite
    # nothing the registry does not contain.
    registry_ids = {a.anchor_id for a in registry.anchors}
    used = anchor_ids()
    assert used <= registry_ids
    assert used == registry_ids


def test_stage_objects_present_and_unique() -> None:
    params = parameters()
    frees = free_parameters()
    assert len(params) >= 40
    assert len(frees) >= 6
    ids = [p.parameter_id for p in params] + [f.parameter_id for f in frees]
    assert len(ids) == len(set(ids))
    assert all(p.parameter_id.startswith("UBP-P") for p in params)
    assert all(f.parameter_id.startswith("UBP-F") for f in frees)


def test_categories_and_kinds_use_declared_vocabularies(
    registry: PaperAnchorRegistry,
) -> None:
    # The module vocabulary must stay in lockstep with the S1 registry's
    # categories, and every object must use it.
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


def test_s1_free_territories_are_marked_free() -> None:
    # The three silences S1 explicitly marked: per-lane Gbit/s, latency
    # breakdown, congestion control. Each must be a FREE parameter; the
    # per-lane one must carry both public rate figures as anchored
    # candidates (recorded, never promoted to values).
    by_name = {p.name: p for p in free_parameters()}
    for name in ("per_lane_line_rate", "component_latency_breakdown", "congestion_control"):
        assert name in by_name, name
        assert by_name[name].domain == "FREE"
    per_lane = by_name["per_lane_line_rate"]
    cand_anchors = {c.anchor_id for c in per_lane.candidates}
    assert cand_anchors == {
        "UBP-UBDOCS-1-SPEC21-RATES",
        "UBP-HC26-1-LINKDEVICE",
    }
    # and no design parameter may smuggle a per-lane rate value in
    assert all(p.name != "per_lane_line_rate" for p in parameters())


def test_evidence_grades_derive_from_cited_sources(registry: PaperAnchorRegistry) -> None:
    # Grade honesty: the per-source mapping covers exactly the registry's
    # sources, and each parameter's grade matches what its anchors cite.
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


def test_vendor_and_official_figures_are_labeled(
    registry: PaperAnchorRegistry,
) -> None:
    for param in parameters():
        source_ids = {a.source_id for a in registry.resolve(param.anchor_ids)}
        if "PUB-UB-HUAWEI-HC26" in source_ids:
            assert param.evidence_grade == "VENDOR_CLAIMED", param.parameter_id
        if {"PUB-UB-OSCOMP", "PUB-UB-DOCS-EN"} & source_ids:
            assert param.evidence_grade == "OFFICIAL_PUBLIC_PAGE", param.parameter_id


def test_by_category_helpers_agree() -> None:
    for category in CATEGORIES:
        objs = by_category(category)
        assert objs, f"category {category} has no objects"
        assert all(o.category == category for o in objs)
    assert sum(len(by_category(c)) for c in CATEGORIES) == len(all_objects())


def test_assert_valid_passes_on_real_registry(registry: PaperAnchorRegistry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- D1 dispositions (ladder S5) ------------------------------------------------


def test_requirements_alias_is_the_design_parameters() -> None:
    # The profile's disposition-bearing requirement objects ARE the design
    # parameters; free parameters stay outside (no disposition by design).
    assert requirements() == parameters()
    assert all(p.disposition for p in requirements())


def test_initial_disposition_rule_is_conservative() -> None:
    # The S5 rule never assigns an executed disposition, and it splits
    # exactly on structure facts: DESIGN_* kinds informational, everything
    # else (measures, behaviors, software components) unsupported.
    for kind in ("DESIGN_CONSTANT", "DESIGN_CLASS", "DESIGN_DEFAULT"):
        assert initial_disposition(kind) == "informational"
    for kind in ("REPORTED_MEASURE", "BEHAVIOR", "COMPONENT"):
        assert initial_disposition(kind) == "unsupported"
    assert not {"constraint", "simulated_behavior", "conformance_test"} & {
        initial_disposition(kind) for kind in VALUE_KINDS
    }


def test_every_parameter_carries_a_valid_disposition() -> None:
    for param in parameters():
        assert param.disposition in DISPOSITIONS, (
            f"{param.parameter_id}: {param.disposition!r}"
        )


def test_initial_assignment_follows_the_s5_rule() -> None:
    for param in parameters():
        expected = PROMOTED_UB.get(
            param.parameter_id, initial_disposition(param.value_kind)
        )
        assert param.disposition == expected, (
            f"{param.parameter_id}: {param.value_kind} -> "
            f"{param.disposition!r} deviates from the S5 initial rule (or "
            "is not a registered promotion); update EXPECTED_UB_COUNTS and "
            "PROMOTED_UB in the same commit and say why"
        )


def test_disposition_counts_are_the_frozen_s5_record() -> None:
    counts: dict[str, int] = {}
    for param in parameters():
        counts[param.disposition] = counts.get(param.disposition, 0) + 1
    assert counts == EXPECTED_UB_COUNTS, (
        "disposition counts drifted from the S5 record; a promotion must "
        "consciously update EXPECTED_UB_COUNTS (no silent "
        "simulated_behavior)"
    )
    assert sum(EXPECTED_UB_COUNTS.values()) == len(parameters()) == 54


def test_no_executed_disposition_without_a_promotion() -> None:
    # No binding exists for UnifiedBus, so PROMOTED_UB must be empty and
    # no parameter may carry an executed disposition (constraint /
    # simulated_behavior / conformance_test).
    executed = ("constraint", "simulated_behavior", "conformance_test")
    assert PROMOTED_UB == {}
    for param in parameters():
        assert param.disposition not in executed, (
            f"{param.parameter_id}: executed disposition "
            f"{param.disposition!r} with no registered binding — silent "
            "promotion; register the binding and the PROMOTED_UB entry in "
            "the same commit"
        )


def test_check_rejects_parameter_without_disposition(
    registry: PaperAnchorRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    # THE D1 gate for this family: strip a real parameter's disposition
    # and the registry check must flag it.
    import essun.specir.unifiedbus_paper_profile as mod

    rogue = dataclasses.replace(parameters()[0], disposition="")
    monkeypatch.setattr(mod, "_PARAMETERS", mod._PARAMETERS + (rogue,))
    problems = mod.check_against_registry(registry)
    assert any(
        f"{parameters()[0].parameter_id}: missing disposition" in p
        for p in problems
    )
    with pytest.raises(mod.ProfileObjectError):
        mod.assert_valid(registry)


def test_check_rejects_unknown_disposition(
    registry: PaperAnchorRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    import essun.specir.unifiedbus_paper_profile as mod

    rogue = dataclasses.replace(parameters()[0], disposition="aspirational")
    monkeypatch.setattr(mod, "_PARAMETERS", mod._PARAMETERS + (rogue,))
    problems = mod.check_against_registry(registry)
    assert any(
        f"{parameters()[0].parameter_id}: unknown disposition" in p
        for p in problems
    )


# -- negative bars: dangling anchors, malformed objects, grade laundering ----


def test_registry_resolve_rejects_dangling_anchor(registry: PaperAnchorRegistry) -> None:
    with pytest.raises(Exception, match="dangling anchor ids"):
        registry.resolve(["UBP-DOES-NOT-EXIST"])


def test_check_rejects_object_with_dangling_anchor(monkeypatch) -> None:
    # THE stage bar: an object with a dangling anchor is rejected.
    import essun.specir.unifiedbus_paper_profile as mod

    rogue = UBDesignParameter(
        parameter_id="UBP-P-ROGUE-1",
        name="rogue",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="A rogue value citing nothing.",
        unit="",
        anchor_ids=("UBP-NO-SUCH-ANCHOR",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    )
    monkeypatch.setattr(mod, "_PARAMETERS", mod._PARAMETERS + (rogue,))
    registry = PaperAnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UBP-P-ROGUE-1" in p and "dangling anchor ids" in p for p in problems
    )
    with pytest.raises(mod.ProfileObjectError):
        mod.assert_valid(registry)


def test_check_rejects_free_parameter_with_dangling_candidate(monkeypatch) -> None:
    import essun.specir.unifiedbus_paper_profile as mod

    rogue = UBFreeParameter(
        parameter_id="UBP-F-ROGUE-1",
        name="rogue_gap",
        category="latency",
        gap="A rogue gap with a dangling candidate.",
        anchor_ids=("UBP-HC26-1-RTT",),
        candidates=(
            UBFreeCandidate(
                label="dangling candidate",
                anchor_id="UBP-NO-SUCH-CANDIDATE-ANCHOR",
                evidence_grade="VENDOR_CLAIMED",
            ),
        ),
    )
    monkeypatch.setattr(mod, "_FREE_PARAMETERS", mod._FREE_PARAMETERS + (rogue,))
    registry = PaperAnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UBP-F-ROGUE-1" in p and "dangling anchor ids" in p for p in problems
    )


def test_check_rejects_grade_laundering(monkeypatch) -> None:
    # A paper-sourced value may not be typed as a vendor claim and vice
    # versa: grade must be derivable from the cited sources.
    import essun.specir.unifiedbus_paper_profile as mod

    laundered = UBDesignParameter(
        parameter_id="UBP-P-ROGUE-2",
        name="laundered",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="A paper-sourced value typed as a vendor claim.",
        unit="",
        anchor_ids=("UBP-UBMESH-3.2.1-NPU-IO",),  # paper source
        evidence_grade="VENDOR_CLAIMED",  # not derivable
        disposition="informational",
    )
    monkeypatch.setattr(mod, "_PARAMETERS", (laundered,))
    registry = PaperAnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any("not derivable from anchor" in p for p in problems)


def test_check_rejects_malformed_objects(monkeypatch) -> None:
    import essun.specir.unifiedbus_paper_profile as mod

    rogue = UBDesignParameter(
        parameter_id="UBP-P-ROGUE-3",
        name="malformed",
        category="quirks",  # not in vocabulary
        value_kind="WISH",  # not in vocabulary
        as_reported="word " * (MAX_AS_REPORTED_WORDS + 1),  # too long
        unit="",
        anchor_ids=("UBP-UBMESH-3.2.1-NPU-IO",),
        evidence_grade="TRUST_ME",  # not in vocabulary
        disposition="unsupported",
    )
    monkeypatch.setattr(mod, "_PARAMETERS", (rogue,))
    registry = PaperAnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any("unknown category" in p for p in problems)
    assert any("unknown value_kind" in p for p in problems)
    assert any("words" in p for p in problems)
    assert any("unknown evidence_grade" in p for p in problems)


def test_check_rejects_empty_and_duplicate_objects(monkeypatch) -> None:
    import essun.specir.unifiedbus_paper_profile as mod

    no_anchor = dataclasses.replace(
        parameters()[0],
        parameter_id="UBP-P-ROGUE-4",
        anchor_ids=(),
    )
    duplicate = dataclasses.replace(parameters()[0])  # same id twice
    monkeypatch.setattr(
        mod,
        "_PARAMETERS",
        (no_anchor,) + mod._PARAMETERS + (duplicate,),
    )
    registry = PaperAnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any("no anchor ids" in p for p in problems)
    assert any("duplicate object id" in p for p in problems)


def test_free_parameter_domain_must_stay_free(monkeypatch) -> None:
    import essun.specir.unifiedbus_paper_profile as mod

    rogue = dataclasses.replace(
        free_parameters()[0],
        domain="FIXED",  # free parameters are FREE by construction
        gap="",
    )
    monkeypatch.setattr(mod, "_FREE_PARAMETERS", (rogue,))
    registry = PaperAnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any("must stay domain=FREE" in p for p in problems)
    assert any("empty gap" in p for p in problems)


def test_real_object_against_synthetic_registry_is_dangling(tmp_path: Path) -> None:
    # End-to-end mirror of Q1's last test: a one-anchor synthetic
    # registry validates like S1's, and a real S2 object cannot resolve
    # against it — citations are load-bearing.
    pages = tmp_path / "pages" / "SYN-SRC"
    pages.mkdir(parents=True)
    text = (
        "3.2 Building Blocks\n\nThe NPU equips two UB IO controllers, "
        "which collectively provide x72 UB lanes."
    )
    (pages / "page_0001.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0001.txt").read_bytes()).hexdigest()
    entry = {
        "sources": [
            {
                "source_id": "SYN-SRC",
                "title": "synthetic public post",
                "url": "https://example.org/synthetic",
                "access": "PUBLIC_READ",
                "doc_sha256": "0" * 64,
                "page_count": 1,
                "pages_dir": str(pages),
            }
        ],
        "anchors": [
            {
                "id": "SYN-1",
                "source_id": "SYN-SRC",
                "section": "3.2",
                "title": "synthetic",
                "category": "link_scale",
                "page": 1,
                "quote": (
                    "The NPU equips two UB IO controllers, which "
                    "collectively provide x72 UB lanes."
                ),
                "page_sha256": digest,
            }
        ],
    }
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    syn = PaperAnchorRegistry.load(reg_file, repo_root=tmp_path)
    syn.assert_valid()

    assert syn.resolve(["SYN-1"])[0].anchor_id == "SYN-1"
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(["SYN-1", "UBP-UBMESH-3.2.1-NPU-IO"])  # real id, absent here

    npu_lanes = next(p for p in parameters() if p.name == "npu_ub_lanes")
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(npu_lanes.anchor_ids)
