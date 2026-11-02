"""M5: the UALink ACTIVATION SKELETON in the D2 format, behind its fences.

The UALink specification family is member-gated (HUM-02 pending), so the M5
activation kit ships a SKELETON, not a profile, and this file is its
conformance gate.  The artifact is ``experiments/ualink/semantic_profile.yaml``,
BUILT (not hand-written) by ``experiments/ualink/build_semantic_profile.py``
from the member-public excerpt registry.  What the tests enforce:

- the skeleton LOADS through the profile-format loader and validates
  against the published JSON Schema, with all ten elements present;
- the SKELETON STATUS IS STATED IN THE ARTIFACT ITSELF: element 1 carries
  the "ACTIVATION SKELETON, NOT A PROFILE" note and ``normative: false``;
  element 2 cites the verbatim license-gate source record including the
  gated STD-UALINK-COMMON20 row (APPROVAL_REQUIRED, never fetched) and the
  pending HUM-02 status;
- the requirements element is a VISIBLE absence: zero objects AND a note —
  strip the note and the format rejects it;
- the freedom element is the structural skeleton: eight free parameters
  (UAL-F01..F08), all FREE by construction, every anchor citation resolving
  in the excerpt registry, and every excerpt figure kept as a graded
  CANDIDATE (MEMBER_PUBLIC_EXCERPT) that promotes nothing;
- the LICENSE FENCE is mechanical: the fetch guard refuses the gated row's
  URL and every non-cleared path on the consortium host BEFORE any fetch,
  and the committed manifest contains only the two cleared public sources
  whose doc sha256s match the registry;
- the excerpt registry itself verifies offline (per-page sha256 recompute,
  quote re-match, PUBLIC_READ-only sources);
- zero bindings and zero checks BY CONTENT, never by omission: a fabricated
  binding is a dangling reference the loader rejects by name;
- a corrupted or missing element is rejected NAMING the element;
- regeneration is byte-identical (no silent hand-edits).

Activation (HUM-02 answered with permission) replaces the skeleton with a
real profile through ``experiments/ualink/ACTIVATION.md``; until then these
tests fail loudly on any attempt to smuggle interpretation in.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

from essun.specir.profile_format import (
    PROFILE_FORMAT_NAME,
    PROFILE_FORMAT_VERSION,
    REQUIRED_KEYS,
    LoadedProfile,
    ProfileFormatError,
    check_anchor_refs,
    load_profile,
    profile_from_dict,
    profile_problems,
)
from essun.specir.unifiedbus_sources import PaperAnchorRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "experiments/ualink/semantic_profile.yaml"
BUILDER = REPO_ROOT / "experiments/ualink/build_semantic_profile.py"
FETCHER = REPO_ROOT / "experiments/ualink/fetch_sources.py"
ANCHOR_BUILDER = REPO_ROOT / "experiments/ualink/build_anchor_registry.py"
SCHEMA = REPO_ROOT / "schemas/profile.schema.json"
REGISTRY_PATH = REPO_ROOT / "experiments/ualink/anchor_registry.yaml"
SOURCE_RECORD = REPO_ROOT / "experiments/ualink/source_record.yaml"
MANIFEST = REPO_ROOT / "experiments/ualink/source/source_manifest.yaml"


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("ualink_fetch_sources", FETCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    reg = PaperAnchorRegistry.load(REGISTRY_PATH)
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


# -- the skeleton loads, with the excerpt identity ------------------------------


def test_artifact_loads_with_the_skeleton_identity(
    profile: LoadedProfile, registry: PaperAnchorRegistry
) -> None:
    assert profile.profile_id == "ualink-activation-skeleton"
    assert profile.format.name == PROFILE_FORMAT_NAME
    assert profile.format.version == PROFILE_FORMAT_VERSION
    assert profile.source.document_id == "ualink_member_public_excerpts"
    assert profile.source.revision == _source_set_revision(registry)
    assert profile.source.extra["normative"] is False
    assert profile.provenance.source_record == (
        "experiments/ualink/source_record.yaml"
    )
    assert profile.provenance.access == "PUBLIC_READ"
    assert profile.calibration.status == "uncalibrated"
    assert profile.profile_version == "0.1.0"  # a bump is conscious


def test_artifact_validates_against_the_published_schema(document: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


def test_artifact_has_all_ten_elements_and_no_unknown_keys(
    document: dict,
) -> None:
    assert set(document) == set(REQUIRED_KEYS)
    assert profile_problems(document) == []


# -- the skeleton status is IN the artifact (the M5 mandate) ---------------------


def test_skeleton_status_is_stated_in_the_artifact_itself(document: dict) -> None:
    note = document["source"]["note"]
    assert "ACTIVATION SKELETON, NOT A PROFILE" in note
    assert document["source"]["normative"] is False
    status = document["provenance"]["license_status"]
    assert "HUM-02" in status and "PENDING" in status


def test_provenance_cites_the_verbatim_record_and_the_gated_row(
    document: dict, registry: PaperAnchorRegistry
) -> None:
    provenance = document["provenance"]
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in record["sources"]}
    # The gated specification row is kept verbatim and named as never fetched.
    assert rows["STD-UALINK-COMMON20"]["access"] == "APPROVAL_REQUIRED"
    assert any(
        "STD-UALINK-COMMON20" in row and "never fetched" in row
        for row in provenance["gated_specification_rows"]
    )
    # The cited excerpts are exactly the registry's sources, sha256 and all;
    # every one is PUBLIC_READ and none is a gated row.
    assert [src["source_id"] for src in provenance["paper_sources"]] == sorted(
        registry.sources
    )
    gated_urls = {
        row["url"].rstrip("/")
        for row in rows.values()
        if row["access"] != "PUBLIC_READ"
    }
    for src in provenance["paper_sources"]:
        entry = registry.sources[src["source_id"]]
        assert src["doc_sha256"] == entry["doc_sha256"]
        assert src["access"] == entry["access"] == "PUBLIC_READ"
        assert src["url"] == entry["url"]
        assert src["url"].rstrip("/") not in gated_urls


# -- requirements: a visible absence, never a fabricated empty table -------------


def test_requirements_are_a_visible_absence(profile: LoadedProfile) -> None:
    assert profile.requirements == ()
    raw = yaml.safe_load(ARTIFACT.read_text(encoding="utf-8"))
    note = raw["requirements"]["note"]
    assert note  # the format demands a note when objects is empty
    assert "HUM-02" in note or "STD-UALINK-COMMON20" in note


def test_stripping_the_absence_note_is_rejected(document: dict) -> None:
    corrupted = copy.deepcopy(document)
    del corrupted["requirements"]["note"]
    _rejects(
        corrupted,
        "requirements:",
        "VISIBLE absence",
    )


def test_disposition_counts_are_all_zero(profile: LoadedProfile) -> None:
    counts = profile.disposition_counts()
    assert sum(counts.values()) == 0  # nothing interpreted, honestly


# -- freedom: the structural skeleton, anchored and never promoted ---------------


def test_freedom_is_the_structural_skeleton(profile: LoadedProfile) -> None:
    ids = [param.parameter_id for param in profile.freedom]
    assert ids == [f"UAL-F{i:02d}" for i in range(1, 9)]
    for param in profile.freedom:
        assert param.domain == "FREE"
        assert param.anchor_ids  # every slot cites the record it stands on
        for cand in param.extra.get("candidates", []):
            assert cand["evidence_grade"] == "MEMBER_PUBLIC_EXCERPT"


def test_every_anchor_citation_resolves_in_the_excerpt_registry(
    profile: LoadedProfile, anchor_ids: frozenset[str]
) -> None:
    assert check_anchor_refs(profile, anchor_ids) == []
    # Candidate anchors resolve too (they are part of the record).
    raw = yaml.safe_load(ARTIFACT.read_text(encoding="utf-8"))
    for param in raw["freedom"]:
        for cand in param.get("candidates", []):
            assert cand["anchor_id"] in anchor_ids


def test_no_excerpt_figure_is_promoted_to_a_value(document: dict) -> None:
    # The one laundering path a skeleton has is smuggling a requirement in;
    # the loader already rejects unknown dispositions, and the builder fence
    # keeps objects empty — pin that the graded candidates stay inside
    # freedom (the only place an excerpt figure may appear).
    assert document["requirements"]["objects"] == []
    graded_labels = [
        cand["label"]
        for param in document["freedom"]
        for cand in param.get("candidates", [])
    ]
    assert any("200 GT/s" in label for label in graded_labels)
    assert all(
        cand["evidence_grade"] == "MEMBER_PUBLIC_EXCERPT"
        for param in document["freedom"]
        for cand in param.get("candidates", [])
    )


# -- the license fence is mechanical ----------------------------------------------


def test_fetch_guard_refuses_the_gated_row_before_any_fetch() -> None:
    fetcher = _load_fetcher()
    gated_url = (
        "https://ualinkconsortium.org/specification/"
        "ualink-common-2-0-specification/"
    )
    with pytest.raises(SystemExit, match="STD-UALINK-COMMON20"):
        fetcher.license_guard(gated_url)


def test_fetch_guard_refuses_uncleared_paths_on_the_consortium_host() -> None:
    fetcher = _load_fetcher()
    for url in (
        "https://ualinkconsortium.org/specification/",
        "https://ualinkconsortium.org/specification/ualink-dl-pl-2-0/",
        "https://ualinkconsortium.org/wp-content/uploads/2026/10/other.pdf",
    ):
        with pytest.raises(SystemExit, match="license guard"):
            fetcher.license_guard(url)


def test_fetch_guard_clears_exactly_the_two_member_public_excerpts() -> None:
    fetcher = _load_fetcher()
    for source in fetcher.SOURCES:
        fetcher.license_guard(source["url"])  # must not raise
    assert len(fetcher.SOURCES) == 2


def test_committed_manifest_contains_only_cleared_public_sources(
    registry: PaperAnchorRegistry,
) -> None:
    fetcher = _load_fetcher()
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["registry_family"] == "ualink_member_public_excerpts"
    cleared = {
        f"https://ualinkconsortium.org{path}" for path in fetcher.UALINK_PUBLIC_PATHS
    }
    for rec in manifest["sources"]:
        assert rec["url"] in cleared, rec["url"]
        assert rec["access"] == "PUBLIC_READ"
        entry = registry.sources[rec["source_id"]]
        assert rec["doc_sha256"] == entry["doc_sha256"]


def test_excerpt_registry_verifies_offline(registry: PaperAnchorRegistry) -> None:
    # assert_valid already ran in the fixture (sha256 + quote re-match);
    # pin the counts and the PUBLIC_READ-only rule explicitly.
    assert len(registry.anchors) == 30
    assert set(registry.sources) == {"PUB-UAL-WP10", "PUB-UAL-OVERVIEW"}
    assert all(
        entry["access"] == "PUBLIC_READ" for entry in registry.sources.values()
    )
    raw = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert raw["registry_family"] == "ualink_member_public_excerpts"
    assert "never fetched" in raw["honesty_note"]


# -- zero bindings and zero checks, by content ------------------------------------


def test_bindings_and_checks_are_empty_by_content(document: dict) -> None:
    assert document["bindings"] == []
    assert document["checks"] == []


def test_a_fabricated_binding_is_a_dangling_reference(document: dict) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["bindings"].append(
        {
            "requirement_id": "UAL-R01",  # no requirements exist at all
            "backend": "analytical_l0_crossbar",
            "capability": "ranks",
        }
    )
    _rejects(
        corrupted,
        "bindings:",
        "UAL-R01",
        "not a requirement of this profile",
    )


# -- the supported element names the ACTIVATION TARGET, and says so ---------------


def test_supported_names_the_activation_target_and_omits_honestly(
    profile: LoadedProfile,
) -> None:
    assert profile.supported.workloads == ("w1_dense_tp_decode",)
    assert set(profile.supported.observables) == {"O-CCT", "O-CONSERVATION"}
    assert any(
        "ACTIVATION TARGET" in omission.what for omission in profile.omissions
    )
    assert any(
        "ZERO interpreted requirements" in omission.what
        for omission in profile.omissions
    )


def test_versioning_declares_activation_a_major_bump(document: dict) -> None:
    assert "dispositions" in document["versioning"]["bump_rules"]["major"]
    assert "sources" in document["versioning"]["bump_rules"]["major"]


# -- a corrupted or missing element is rejected NAMING the element -----------------


@pytest.mark.parametrize("key", REQUIRED_KEYS, ids=lambda k: f"missing-{k}")
def test_missing_element_is_rejected_naming_it(document: dict, key: str) -> None:
    corrupted = copy.deepcopy(document)
    del corrupted[key]
    _rejects(corrupted, f"{key}:")


def test_unknown_top_level_key_is_rejected_naming_it(document: dict) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["ualink_profile_ready"] = True
    _rejects(corrupted, "unknown top-level key", "ualink_profile_ready")


def test_a_smuggled_requirement_with_a_fake_disposition_is_rejected(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["requirements"]["objects"] = [
        {
            "requirement_id": "UAL-R01",
            "anchor_ids": ["UAL-WP10-3-ULS-1024"],
            "statement": "smuggled interpretation",
            "disposition": "normative_fact",  # not in the vocabulary
        }
    ]
    _rejects(corrupted, "requirements:", "UAL-R01", "normative_fact")


# -- regeneration is byte-identical (no silent hand-edits) -------------------------


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


def test_the_builders_exist_where_the_artifact_says() -> None:
    # The wired pipeline the runbook depends on: fetch -> anchor -> profile.
    for path in (FETCHER, ANCHOR_BUILDER, BUILDER):
        assert path.is_file(), path
