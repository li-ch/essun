"""S4 of the dispositions/profile ladder: the UEC profile IN the D2 format.

Ladder S4 migrates the UEC 1.1 semantic profile into the versioned
``essun-profile`` v0.1 format landed in S3
(:mod:`essun.specir.profile_format`).  The artifact is
``experiments/uec/semantic_profile.yaml``, BUILT (not hand-written) by
``experiments/uec/build_semantic_profile.py`` from the live specir
registry.  This file is the migration's conformance gate:

- the migrated profile LOADS through the S3 loader and validates against
  the published JSON Schema (``schemas/profile.schema.json``);
- every included requirement's DISPOSITION matches the live specir
  registry — the S1 record is the single source of truth; the migration
  reads dispositions, it cannot re-adjudicate them.  Statements, anchor
  citations, keywords and subjects are compared too, so the artifact is
  the same interpretation, not a paraphrase of a paraphrase;
- the artifact's per-disposition counts equal the live D1 coverage
  report's UEC totals (189 informational / 255 unsupported /
  1 simulated_behavior over 445 requirements, 67 free parameters
  outside the table);
- the BINDING check passes against the declared backend: the artifact's
  bindings are exactly the live :data:`essun.specir.bindings.BINDINGS`
  registry (BIND-UEC11-FC-R02-L0TFC on analytical_l0_tfc), and
  ``check_bindings_against`` is green against the backend's real
  CAPABILITIES;
- every anchor citation resolves in the live UEC anchor registry
  (provenance preserved, anchors unchanged — and a swapped citation is
  caught by name, never at load);
- a corrupted or missing element is rejected NAMING the element — the
  full S3 battery, run on the REAL artifact, plus the migration-specific
  corruptions: a re-adjudicated disposition, a binding on a
  non-simulated_behavior requirement, a dropped binding under a
  simulated_behavior requirement;
- regeneration is byte-identical: re-running the builder reproduces the
  committed artifact exactly — no silent hand-edits between the live
  registry and the artifact.
"""

from __future__ import annotations

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.bindings import BINDINGS, UEC_REQUIREMENT_MODULES, requirement_index
from essun.specir.disposition_coverage import uec_profile_coverage
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

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "experiments/uec/semantic_profile.yaml"
BUILDER = REPO_ROOT / "experiments/uec/build_semantic_profile.py"
SCHEMA = REPO_ROOT / "schemas/profile.schema.json"

#: The flagship promotion the migration must carry forward (G2): the one
#: requirement executed today, with its binding and golden test.
SIMULATED = ("UEC11-FC-R02", "BIND-UEC11-FC-R02-L0TFC", "analytical_l0_tfc")


@pytest.fixture(scope="module")
def document() -> dict:
    return yaml.safe_load(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def profile() -> LoadedProfile:
    return load_profile(ARTIFACT)


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()  # citations are checked against a verified registry
    return reg


def _rejects(data, *needles: str) -> None:
    """Assert the artifact is rejected, with each needle in the error."""
    with pytest.raises(ProfileFormatError) as excinfo:
        profile_from_dict(data)
    text = str(excinfo.value)
    for needle in needles:
        assert needle in text, f"{needle!r} not named in: {text}"


# -- the migrated profile loads -------------------------------------------------


def test_artifact_loads_with_the_uec_identity(profile: LoadedProfile) -> None:
    assert profile.profile_id == "uec-1.1-semantic"
    assert profile.format.name == PROFILE_FORMAT_NAME
    assert profile.format.version == PROFILE_FORMAT_VERSION
    assert profile.source.document_id == "STD-UEC-11"
    assert profile.source.revision == "1.1"
    assert profile.source.name == "Ultra Ethernet Specification 1.1"
    assert profile.provenance.source_record == "experiments/uec/source_record.yaml"
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


# -- dispositions match the live registry (S1 record, read-only) ----------------


def test_requirement_set_is_exactly_the_live_registry(
    profile: LoadedProfile,
) -> None:
    live = requirement_index()  # the five stage modules, live
    assert set(profile.requirements_by_id()) == set(live)


def test_every_disposition_statement_and_anchor_matches_the_live_registry(
    profile: LoadedProfile,
) -> None:
    live = requirement_index()
    for req in profile.requirements:
        lreq = live[req.requirement_id]
        assert req.disposition == lreq.disposition, (
            f"{req.requirement_id}: artifact disposition {req.disposition!r} "
            f"!= live {lreq.disposition!r} — the migration re-adjudicated a "
            "disposition (S4 does not; regenerate the artifact)"
        )
        assert req.anchor_ids == tuple(lreq.anchor_ids)
        assert req.statement == lreq.statement
        assert req.extra["keyword"] == lreq.keyword
        assert req.extra["subject"] == lreq.subject


def test_disposition_counts_are_the_live_coverage_totals(
    profile: LoadedProfile,
) -> None:
    live = uec_profile_coverage().total_counts()
    assert profile.disposition_counts() == live
    assert live["informational"] == 189
    assert live["unsupported"] == 255
    assert live["simulated_behavior"] == 1
    assert live["constraint"] == 0
    assert live["conformance_test"] == 0
    assert live["not_applicable"] == 0
    assert len(profile.requirements) == 445


def test_freedom_is_exactly_the_live_free_parameters(
    profile: LoadedProfile,
) -> None:
    live = {
        param.parameter_id: (param, module_name.rsplit(".", 1)[-1])
        for module_name in UEC_REQUIREMENT_MODULES
        for param in importlib.import_module(module_name).free_parameters()
    }
    assert len(profile.freedom) == len(live) == 67
    for param in profile.freedom:
        lparam, short = live[param.parameter_id]
        assert param.anchor_ids == tuple(lparam.anchor_ids)
        assert param.name == lparam.name
        assert param.freedom == lparam.freedom
        assert param.domain == "FREE"
        assert param.extra["module"] == short


def test_module_extras_name_the_owning_stage_modules(
    profile: LoadedProfile,
) -> None:
    shorts = {name.rsplit(".", 1)[-1] for name in UEC_REQUIREMENT_MODULES}
    for req in profile.requirements:
        assert req.extra["module"] in shorts


# -- the binding carries forward and the backend declares it ---------------------


def test_bindings_are_exactly_the_live_binding_registry(
    profile: LoadedProfile,
) -> None:
    assert len(profile.bindings) == len(BINDINGS)
    by_requirement = {b.requirement_id: b for b in profile.bindings}
    for binding in BINDINGS:
        entry = by_requirement[binding.requirement_id]
        assert entry.extra["binding_id"] == binding.binding_id
        assert entry.backend == binding.backend_id
        assert entry.capability == binding.capability
        assert tuple(entry.parameters) == binding.parameters
        assert all(value == "FREE" for value in entry.parameters.values())
        assert entry.extra["parameter_effect"] == binding.parameter_effect
        assert tuple(entry.extra["enforced_invariants"]) == (
            binding.enforced_invariants
        )
        assert tuple(entry.extra["observable_ids"]) == binding.observable_ids
        assert entry.extra["golden_test"] == binding.golden_test


def test_binding_check_passes_against_the_declared_backend(
    profile: LoadedProfile,
) -> None:
    from essun.backends.analytical import l0_tfc

    assert SIMULATED == ("UEC11-FC-R02", "BIND-UEC11-FC-R02-L0TFC", l0_tfc.BACKEND_ID)
    assert check_bindings_against(profile, l0_tfc.CAPABILITIES) == []


def test_binding_check_fails_loudly_on_a_foreign_backend(
    profile: LoadedProfile,
) -> None:
    from essun.backends.analytical import l0  # a real backend without TFC

    problems = check_bindings_against(profile, l0.CAPABILITIES)
    assert problems, "the unbound L0 backend must not silently accept the binding"
    assert any(
        "UEC11-FC-R02 -> analytical_l0_tfc.tfc_credit_windowed_ring" in p
        for p in problems
    )


def test_simulated_behavior_requirement_is_executed_and_checked(
    profile: LoadedProfile,
) -> None:
    by_id = profile.requirements_by_id()
    req = by_id[SIMULATED[0]]
    assert req.disposition == "simulated_behavior"
    assert any(b.extra["binding_id"] == SIMULATED[1] for b in profile.bindings)
    golden = [c for c in profile.checks if c.kind == "golden"]
    assert any(SIMULATED[0] in c.requirement_ids for c in golden)


# -- checks reference real requirements in real files ---------------------------


def test_checks_live_in_real_files_and_reference_real_requirements(
    profile: LoadedProfile,
) -> None:
    ids = set(profile.requirements_by_id())
    assert profile.checks, "the profile declares its executable checks"
    for check in profile.checks:
        assert (REPO_ROOT / check.location).is_file(), check.location
        assert set(check.requirement_ids) <= ids
    assert {c.kind for c in profile.checks} <= {"golden", "negative", "invariant"}


def test_supported_surface_is_the_flagships_executed_surface(
    profile: LoadedProfile,
) -> None:
    # Honest minimal surface: what the registered binding executes today.
    assert profile.supported.workloads == ("w1_dense_tp_decode",)
    assert set(profile.supported.observables) == {"O-CCT", "O-CONSERVATION"}


# -- provenance preserved: anchors unchanged and resolving ----------------------


def test_every_anchor_citation_resolves_in_the_uec_registry(
    profile: LoadedProfile, registry: AnchorRegistry
) -> None:
    assert check_anchor_refs(profile, registry) == []


def test_a_swapped_anchor_is_named_and_never_fails_at_load(
    document: dict, registry: AnchorRegistry
) -> None:
    swapped = copy.deepcopy(document)
    for obj in swapped["requirements"]["objects"]:
        if obj["requirement_id"] == SIMULATED[0]:
            obj["anchor_ids"] = ["UEC11-S0-FABRICATED"]
    profile = profile_from_dict(swapped)  # loads anywhere (D5 portability)
    problems = check_anchor_refs(profile, registry)
    assert len(problems) == 1
    assert problems[0].startswith(f"requirements: {SIMULATED[0]}:")
    assert "UEC11-S0-FABRICATED" in problems[0]


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
        if obj["requirement_id"] == "UEC11-LT-R15":
            obj["disposition"] = "simulated_someday"  # not in the vocabulary
    _rejects(corrupted, "requirements:", "UEC11-LT-R15", "simulated_someday")


def test_binding_on_a_non_simulated_requirement_is_rejected(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    # Re-adjudicate UEC11-FC-R02 down to unsupported, keep the binding: the
    # format must reject the contradiction (S4 does not re-adjudicate).
    for obj in corrupted["requirements"]["objects"]:
        if obj["requirement_id"] == SIMULATED[0]:
            obj["disposition"] = "unsupported"
    _rejects(
        corrupted,
        "bindings:",
        SIMULATED[0],
        "only simulated_behavior requirements may bind a backend capability",
    )


def test_dropping_the_binding_orphans_the_simulated_requirement(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["bindings"] = []
    _rejects(
        corrupted,
        "requirements:",
        SIMULATED[0],
        "simulated_behavior requires at least one backend capability binding",
    )


def test_corrupted_calibration_and_check_elements_are_named(
    document: dict,
) -> None:
    corrupted = copy.deepcopy(document)
    corrupted["calibration"]["status"] = "calibrated-finally"
    corrupted["checks"][0]["kind"] = "fluff"
    problems = profile_problems(corrupted)
    assert any(p.startswith("calibration:") for p in problems)
    assert any(p.startswith("checks:") for p in problems)


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
