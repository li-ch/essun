"""S5 of the dispositions/profile ladder: the UnifiedBus profile IN the D2 format.

Ladder S5 migrates the UnifiedBus PAPER-DERIVED design profile into the
versioned ``essun-profile`` v0.1 format landed in S3
(:mod:`essun.specir.profile_format`), mirroring the UEC migration of S4
(``tests/specir/test_uec_semantic_profile.py``) with one categorical
difference the tests enforce: NON-NORMATIVE LABELING PRESERVED.  The
artifact is ``experiments/unifiedbus/semantic_profile.yaml``, BUILT (not
hand-written) by ``experiments/unifiedbus/build_semantic_profile.py`` from
the live specir registry.  This file is the migration's conformance gate:

- the migrated profile LOADS through the S3 loader and validates against
  the published JSON Schema (``schemas/profile.schema.json``);
- NON-NORMATIVE STATUS IS STATED IN THE ARTIFACT ITSELF: element 1 carries
  the paper-derived/not-normative note and ``normative: false``; element 2
  cites the verbatim license-gate source record (including the gated
  STD-UB-LICENSE row, never fetched) plus the five PUBLIC_READ papers with
  their doc sha256s; every requirement keeps its evidence grade
  (PAPER_REPORTED / VENDOR_CLAIMED / OFFICIAL_PUBLIC_PAGE), so a vendor
  number cannot be laundered — and the multi-source set's ``revision`` is
  the COMPUTED content digest of the five pinned documents, never an
  invented version number;
- every included requirement's DISPOSITION matches the live specir
  registry (the S5 record) — statements (``as_reported``), anchor
  citations, value kinds and grades are compared too, so the artifact is
  the same interpretation, not a paraphrase of a paraphrase;
- the artifact's per-disposition counts equal the live D1 coverage
  report's UnifiedBus totals (32 informational / 22 unsupported over 54
  requirements, ZERO executed, 8 free parameters outside the table);
- ZERO BINDINGS, honestly: the artifact's ``bindings`` list is empty
  because no reviewed binding exists for UnifiedBus, and the format's
  contradiction rules are exercised on the real artifact — a fabricated
  binding on a non-simulated_behavior requirement is rejected, and a
  requirement flipped to simulated_behavior without a binding is an
  orphan the loader rejects; a fabricated binding pair fails LOUDLY
  against a real backend's declared capabilities, never silently;
- every anchor citation resolves in the live paper-anchor registry
  (provenance preserved, anchors unchanged — a swapped citation is caught
  by name, never at load);
- a corrupted or missing element is rejected NAMING the element — the
  full S3 battery run on the REAL artifact;
- regeneration is byte-identical: re-running the builder reproduces the
  committed artifact exactly — no silent hand-edits between the live
  registry and the artifact.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

from essun.specir.disposition_coverage import unifiedbus_profile_coverage
from essun.specir.profile_format import (
    PROFILE_FORMAT_NAME,
    PROFILE_FORMAT_VERSION,
    REQUIRED_KEYS,
    LoadedProfile,
    ProfileFormatError,
    check_anchor_refs,
    check_bindings_against,
    load_profile,
    profile_from_dict,
    profile_problems,
)
from essun.specir.unifiedbus_paper_profile import free_parameters, requirements
from essun.specir.unifiedbus_sources import PaperAnchorRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "experiments/unifiedbus/semantic_profile.yaml"
BUILDER = REPO_ROOT / "experiments/unifiedbus/build_semantic_profile.py"
SCHEMA = REPO_ROOT / "schemas/profile.schema.json"
SWEEP = REPO_ROOT / "experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml"


def _rejects(data, *needles: str) -> None:
    """Assert the artifact is rejected, with each needle in the error."""
    with pytest.raises(ProfileFormatError) as excinfo:
        profile_from_dict(data)
    text = str(excinfo.value)
    for needle in needles:
        assert needle in text, f"{needle!r} not named in: {text}"


@pytest.fixture(scope="module")
def document() -> dict:
    return yaml.safe_load(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def profile() -> LoadedProfile:
    return load_profile(ARTIFACT)


@pytest.fixture(scope="module")
def registry() -> PaperAnchorRegistry:
    reg = PaperAnchorRegistry.load()
    reg.assert_valid()  # sha256 + quote re-match + PUBLIC_READ gate
    return reg


@pytest.fixture(scope="module")
def anchor_ids(registry: PaperAnchorRegistry) -> frozenset[str]:
    return frozenset(anchor.anchor_id for anchor in registry.anchors)


def _source_set_revision(registry: PaperAnchorRegistry) -> str:
    lines = sorted(
        f"{source_id} {entry['doc_sha256']}"
        for source_id, entry in registry.sources.items()
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# -- the migrated profile loads, with the paper identity -----------------------


def test_artifact_loads_with_the_unifiedbus_identity(
    profile: LoadedProfile, registry: PaperAnchorRegistry
) -> None:
    assert profile.profile_id == "unifiedbus-paper-derived"
    assert profile.format.name == PROFILE_FORMAT_NAME
    assert profile.format.version == PROFILE_FORMAT_VERSION
    # Multi-source paper set: identity is the registry family (verbatim),
    # revision is the COMPUTED digest of the five pinned documents.
    assert profile.source.document_id == "unifiedbus_public_papers"
    assert (
        registry_anchor_family(registry) == "unifiedbus_public_papers"
    )
    assert profile.source.revision == _source_set_revision(registry)
    assert profile.source.extra["normative"] is False
    assert profile.provenance.source_record == (
        "experiments/unifiedbus/source_record.yaml"
    )
    assert profile.provenance.access == "PUBLIC_READ"
    assert profile.calibration.status == "uncalibrated"
    assert profile.profile_version == "0.1.0"  # a bump is conscious


def registry_anchor_family(registry: PaperAnchorRegistry) -> str | None:
    raw = yaml.safe_load(
        (REPO_ROOT / "experiments/unifiedbus/anchor_registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    return raw.get("registry_family")


def test_artifact_validates_against_the_published_schema(document: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


def test_artifact_has_all_ten_elements_and_no_unknown_keys(
    document: dict,
) -> None:
    assert set(document) == set(REQUIRED_KEYS)
    assert profile_problems(document) == []


# -- non-normative labeling is IN the artifact (the S5 mandate) -----------------


def test_non_normative_status_is_stated_in_the_artifact_itself(
    document: dict,
) -> None:
    note = document["source"]["note"]
    assert "PAPER-DERIVED, NOT NORMATIVE" in note
    assert "not a UnifiedBus standard profile" in note
    assert "license-gated" in note
    assert document["source"]["normative"] is False


def test_provenance_cites_the_verbatim_record_and_pinned_papers(
    document: dict, registry: PaperAnchorRegistry
) -> None:
    provenance = document["provenance"]
    record = yaml.safe_load(
        (REPO_ROOT / "experiments/unifiedbus/source_record.yaml").read_text(
            encoding="utf-8"
        )
    )
    row_ids = {row["id"] for row in record["sources"]}
    assert "STD-UB-LICENSE" in row_ids  # the gated row, kept verbatim
    assert "STD-UB-LICENSE" in provenance["gated_specification_row"]
    # The five cited papers are exactly the registry's sources, sha256 and
    # all; every one is PUBLIC_READ (a gated source is never citable).
    assert [src["source_id"] for src in provenance["paper_sources"]] == sorted(
        registry.sources
    )
    for src in provenance["paper_sources"]:
        entry = registry.sources[src["source_id"]]
        assert src["doc_sha256"] == entry["doc_sha256"]
        assert src["access"] == entry["access"] == "PUBLIC_READ"
        assert src["url"] == entry["url"]
    # No cited paper is the license-gated specification track.
    assert not (row_ids & {src["source_id"] for src in provenance["paper_sources"]})


def test_every_requirement_keeps_its_evidence_grade(
    profile: LoadedProfile,
) -> None:
    live = {p.parameter_id: p.evidence_grade for p in requirements()}
    grades = {req.extra.get("evidence_grade") for req in profile.requirements}
    assert grades == {"PAPER_REPORTED", "VENDOR_CLAIMED", "OFFICIAL_PUBLIC_PAGE"}
    for req in profile.requirements:
        assert req.extra["evidence_grade"] == live[req.requirement_id], (
            f"{req.requirement_id}: grade laundered in the artifact"
        )


# -- dispositions match the live registry (S5 record, read-only) ----------------


def test_requirement_set_is_exactly_the_live_registry(
    profile: LoadedProfile,
) -> None:
    live = {p.parameter_id for p in requirements()}
    assert set(profile.requirements_by_id()) == live == {
        f"UBP-P{i:02d}" for i in range(1, 55)
    }


def test_every_disposition_statement_and_anchor_matches_the_live_registry(
    profile: LoadedProfile,
) -> None:
    live = {p.parameter_id: p for p in requirements()}
    for req in profile.requirements:
        lreq = live[req.requirement_id]
        assert req.disposition == lreq.disposition, (
            f"{req.requirement_id}: artifact disposition {req.disposition!r} "
            f"!= live {lreq.disposition!r} — the migration re-adjudicated a "
            "disposition (S5 does not; regenerate the artifact)"
        )
        assert req.anchor_ids == tuple(lreq.anchor_ids)
        assert req.statement == lreq.as_reported
        assert req.extra["name"] == lreq.name
        assert req.extra["category"] == lreq.category
        assert req.extra["value_kind"] == lreq.value_kind
        assert req.extra["unit"] == lreq.unit


def test_disposition_counts_are_the_live_coverage_totals(
    profile: LoadedProfile,
) -> None:
    live = unifiedbus_profile_coverage().total_counts()
    assert profile.disposition_counts() == live
    assert live["informational"] == 32
    assert live["unsupported"] == 22
    assert live["simulated_behavior"] == 0
    assert live["constraint"] == 0
    assert live["conformance_test"] == 0
    assert live["not_applicable"] == 0
    assert len(profile.requirements) == 54


def test_no_executed_disposition_and_the_omission_says_so(
    profile: LoadedProfile,
) -> None:
    # The S5 honest headline: NOTHING is executed (no reviewed binding
    # exists for UnifiedBus), and the artifact states it visibly.
    executed = ("constraint", "simulated_behavior", "conformance_test")
    assert not [r for r in profile.requirements if r.disposition in executed]
    assert any(
        "zero backend capability bindings" in omission.what
        for omission in profile.omissions
    )


def test_freedom_is_exactly_the_live_free_parameters(
    profile: LoadedProfile,
) -> None:
    live = {p.parameter_id: p for p in free_parameters()}
    assert len(profile.freedom) == len(live) == 8
    for param in profile.freedom:
        lparam = live[param.parameter_id]
        assert param.anchor_ids == tuple(lparam.anchor_ids)
        assert param.name == lparam.name
        assert param.freedom == lparam.gap  # the silence being marked
        assert param.domain == "FREE"
        assert param.extra["category"] == lparam.category
        candidates = param.extra.get("candidates", [])
        assert [
            (c["label"], c["anchor_id"], c["evidence_grade"])
            for c in candidates
        ] == [
            (c.label, c.anchor_id, c.evidence_grade) for c in lparam.candidates
        ]


# -- zero bindings, honestly (the paper-derived family's fence) ------------------


def test_bindings_list_is_empty_by_content_not_by_omission(
    document: dict,
) -> None:
    # The format's own words: "a profile executed by no backend today says
    # so by having no bindings, never by omitting the element."
    assert document["bindings"] == []


def test_a_fabricated_binding_on_a_non_simulated_requirement_is_rejected(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["bindings"].append(
        {
            "requirement_id": "UBP-P17",  # informational, not simulated
            "backend": "analytical_l0_crossbar",
            "capability": "ranks",
        }
    )
    _rejects(
        corrupted,
        "bindings:",
        "UBP-P17",
        "only simulated_behavior requirements may bind a backend capability",
    )


def test_an_upgraded_requirement_without_a_binding_is_an_orphan(
    document: dict,
) -> None:
    # Flip one parameter to simulated_behavior with NO binding: the loader
    # rejects the orphan — the honest fence made mechanical.
    corrupted = copy.deepcopy(document)
    for obj in corrupted["requirements"]["objects"]:
        if obj["requirement_id"] == "UBP-P17":
            obj["disposition"] = "simulated_behavior"
    _rejects(
        corrupted,
        "requirements:",
        "UBP-P17",
        "simulated_behavior requires at least one backend capability binding",
    )


def test_a_fabricated_binding_pair_fails_loudly_on_a_real_backend(
    document: dict,
) -> None:
    # A fully self-consistent fabrication (simulated_behavior + matching
    # binding) still cannot execute silently: against a REAL backend's
    # declared capabilities the loud-failure primitive names it.
    from essun.backends.analytical import l0_crossbar

    corrupted = copy.deepcopy(document)
    for obj in corrupted["requirements"]["objects"]:
        if obj["requirement_id"] == "UBP-P17":
            obj["disposition"] = "simulated_behavior"
    corrupted["bindings"].append(
        {
            "requirement_id": "UBP-P17",
            "backend": "analytical_l0_crossbar",
            "capability": "paper_derived_rack_scale",  # not declared
        }
    )
    fabricated = profile_from_dict(corrupted)  # loads (self-consistent)
    problems = check_bindings_against(fabricated, l0_crossbar.CAPABILITIES)
    assert any(
        "UBP-P17 -> analytical_l0_crossbar.paper_derived_rack_scale" in p
        for p in problems
    )


def test_the_real_artifact_has_nothing_to_check_against_a_real_backend(
    profile: LoadedProfile,
) -> None:
    # Sanity of the empty list: with zero bindings the loud-failure check
    # is vacuously green against any real backend.
    from essun.backends.analytical import l0_crossbar

    assert check_bindings_against(profile, l0_crossbar.CAPABILITIES) == []


# -- checks reference real requirements in real files ---------------------------

def test_checks_live_in_real_files_and_reference_real_requirements(
    profile: LoadedProfile,
) -> None:
    ids = set(profile.requirements_by_id())
    assert profile.checks, "the profile declares its executable checks"
    for check in profile.checks:
        assert (REPO_ROOT / check.location).is_file(), check.location
        assert set(check.requirement_ids) <= ids
        assert check.kind in {"golden", "negative", "invariant"}
    (chk,) = profile.checks
    assert chk.check_id == "UBP-CHK-01"
    assert set(chk.requirement_ids) == {"UBP-P06", "UBP-P07", "UBP-P17"}


def test_supported_surface_is_the_real_comparison_sweep(
    profile: LoadedProfile,
) -> None:
    # The declared surface is exactly what the real cross-design L0
    # comparison sweep records (drift between artifact and sweep is loud).
    sweep = yaml.safe_load(SWEEP.read_text(encoding="utf-8"))
    assert profile.supported.workloads == ("w1_dense_tp_decode",)
    assert set(sweep["observables"]) == set(profile.supported.observables)
    assert set(profile.supported.observables) == {"O-CCT", "O-CONSERVATION"}


# -- provenance preserved: anchors unchanged and resolving ----------------------


def test_every_anchor_citation_resolves_in_the_paper_registry(
    profile: LoadedProfile, anchor_ids: frozenset[str]
) -> None:
    assert check_anchor_refs(profile, anchor_ids) == []


def test_a_swapped_anchor_is_named_and_never_fails_at_load(
    document: dict, anchor_ids: frozenset[str]
) -> None:
    swapped = copy.deepcopy(document)
    for obj in swapped["requirements"]["objects"]:
        if obj["requirement_id"] == "UBP-P17":
            obj["anchor_ids"] = ["UBP-FABRICATED-ANCHOR"]
    profile = profile_from_dict(swapped)  # loads anywhere (D5 portability)
    problems = check_anchor_refs(profile, anchor_ids)
    assert len(problems) == 1
    assert problems[0].startswith("requirements: UBP-P17:")
    assert "UBP-FABRICATED-ANCHOR" in problems[0]


# -- a corrupted or missing element is rejected NAMING the element ---------------


@pytest.mark.parametrize("key", REQUIRED_KEYS, ids=lambda k: f"missing-{k}")
def test_missing_element_is_rejected_naming_it(document: dict, key: str) -> None:
    corrupted = copy.deepcopy(document)
    del corrupted[key]
    _rejects(corrupted, f"{key}:")


def test_unknown_top_level_key_is_rejected_naming_it(document: dict) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["verified_claims"] = ["everything"]
    _rejects(corrupted, "unknown top-level key", "verified_claims")


def test_readjudicated_disposition_is_rejected_naming_requirement(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    for obj in corrupted["requirements"]["objects"]:
        if obj["requirement_id"] == "UBP-P17":
            obj["disposition"] = "normative_fact"  # not in the vocabulary
    _rejects(corrupted, "requirements:", "UBP-P17", "normative_fact")


def test_corrupted_calibration_and_check_elements_are_named(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["calibration"]["status"] = "vendor-calibrated"
    corrupted["checks"][0]["kind"] = "fluff"
    problems = profile_problems(corrupted)
    assert any(p.startswith("calibration:") for p in problems)
    assert any(p.startswith("checks:") for p in problems)


def test_calibration_cannot_carry_targets_while_uncalibrated(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["calibration"]["targets"] = ["UBP-HC26-1-RTT"]
    _rejects(corrupted, "calibration:", "uncalibrated")


# -- regeneration is byte-identical (no silent hand-edits) -----------------------


def test_rebuilding_the_artifact_is_byte_identical(tmp_path: Path) -> None:
    regenerated = tmp_path / "semantic_profile.yaml"
    subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(regenerated)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert regenerated.read_bytes() == ARTIFACT.read_bytes(), (
        "the committed artifact differs from what the builder produces — "
        "either regenerate it or fix the hand-edit"
    )
