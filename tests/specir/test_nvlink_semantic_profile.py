"""M1: the NVLink-class profile IN the essun-profile v0.1 format.

Mirrors the UnifiedBus migration's conformance gate
(``tests/specir/test_unifiedbus_semantic_profile.py``) for the third
fabric's artifact (``experiments/nvlink/semantic_profile.yaml``, built by
``experiments/nvlink/build_semantic_profile.py``), with the same
categorical bar: NON-NORMATIVE LABELING PRESERVED — the artifact states
its paper-derived status itself, cites the verbatim license-gate record
(including the never-fetched STD-NV-SPEC row; no public NVLink/NVSwitch
specification exists), keeps every requirement's evidence grade, matches
the live registry's dispositions statement-by-statement, carries ZERO
bindings by content, and regenerates byte-identically.
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

from essun.specir.disposition_coverage import nvlink_profile_coverage
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
from essun.specir.nvlink_paper_profile import (
    free_parameters,
    load_registry,
    requirements,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "experiments/nvlink/semantic_profile.yaml"
BUILDER = REPO_ROOT / "experiments/nvlink/build_semantic_profile.py"
SCHEMA = REPO_ROOT / "schemas/profile.schema.json"
SOURCE_RECORD = REPO_ROOT / "experiments/nvlink/source_record.yaml"
THREE_ARCH_SWEEP = REPO_ROOT / "experiments/sweeps/cross_fabric_3arch_payload_grid_v1.yaml"
FLAVOR_FILE = REPO_ROOT / "experiments/topologies/crossbar64_nvl_rack_free_params.yaml"


def _rejects(data, *needles: str) -> None:
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
def registry():
    return load_registry()


# -- the migrated profile loads, with the paper identity -----------------------


def test_artifact_loads_with_the_nvlink_identity(document: dict) -> None:
    assert document["format"] == {
        "name": PROFILE_FORMAT_NAME,
        "version": PROFILE_FORMAT_VERSION,
    }
    assert document["profile_id"] == "nvlink-class-paper-derived"
    assert document["source"]["document_id"] == "nvlink_class_public_papers"
    assert document["source"]["revision"] == _source_set_revision()


def _source_set_revision() -> str:
    registry = load_registry()
    lines = sorted(
        f"{source_id} {entry['doc_sha256']}"
        for source_id, entry in registry.sources.items()
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def test_artifact_validates_against_the_published_schema(document: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(document, schema)


def test_artifact_has_all_ten_elements_and_no_unknown_keys(document: dict) -> None:
    assert set(document) == set(REQUIRED_KEYS)


def test_non_normative_status_is_stated_in_the_artifact_itself(document: dict) -> None:
    note = document["source"]["note"]
    assert document["source"]["normative"] is False
    assert "PAPER-DERIVED, NOT NORMATIVE" in note
    assert "NVLink" in note
    header = ARTIFACT.read_text(encoding="utf-8").splitlines()[:6]
    assert any("PAPER-DERIVED, NOT NORMATIVE" in line for line in header)


def test_provenance_cites_the_verbatim_record_and_pinned_papers(document: dict) -> None:
    provenance = document["provenance"]
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in record["sources"]}
    # the gated specification row is named, never fetched
    assert "STD-NV-SPEC" in provenance["gated_specification_row"]
    assert rows["STD-NV-SPEC"]["access"] == "APPROVAL_REQUIRED"
    # the five pinned papers, with their doc sha256s, all PUBLIC_READ
    assert len(provenance["paper_sources"]) == 5
    for source in provenance["paper_sources"]:
        assert source["access"] == "PUBLIC_READ"
        assert len(source["doc_sha256"]) == 64
    assert provenance["evidence_grades_in_use"] == [
        "OFFICIAL_PUBLIC_PAGE", "PAPER_REPORTED", "VENDOR_CLAIMED",
    ]


def test_every_requirement_keeps_its_evidence_grade(document: dict) -> None:
    live = {p.parameter_id: p.evidence_grade for p in requirements()}
    for req in document["requirements"]["objects"]:
        assert req["evidence_grade"] == live[req["requirement_id"]]


def test_requirement_set_is_exactly_the_live_registry(document: dict) -> None:
    assert [r["requirement_id"] for r in document["requirements"]["objects"]] == [
        p.parameter_id for p in requirements()
    ]


def test_every_disposition_statement_and_anchor_matches_the_live_registry(
    document: dict,
) -> None:
    by_id = {p.parameter_id: p for p in requirements()}
    for req in document["requirements"]["objects"]:
        live = by_id[req["requirement_id"]]
        assert req["disposition"] == live.disposition
        assert req["statement"] == live.as_reported
        assert req["anchor_ids"] == list(live.anchor_ids)
        assert req["value_kind"] == live.value_kind
        assert req["unit"] == live.unit


def test_disposition_counts_are_the_live_coverage_totals(document: dict) -> None:
    coverage = nvlink_profile_coverage()
    counts: dict[str, int] = {}
    for req in document["requirements"]["objects"]:
        counts[req["disposition"]] = counts.get(req["disposition"], 0) + 1
    assert counts == {k: v for k, v in coverage.total_counts().items() if v}
    assert coverage.executed == 0
    assert coverage.free_parameters == 6


def test_no_executed_disposition_and_the_omission_says_so(document: dict) -> None:
    executed = {"constraint", "simulated_behavior", "conformance_test"}
    for req in document["requirements"]["objects"]:
        assert req["disposition"] not in executed
    joined = " ".join(o["what"] + o["reason"] for o in document["omissions"])
    assert "zero backend capability bindings" in joined


def test_freedom_is_exactly_the_live_free_parameters(document: dict) -> None:
    assert [f["parameter_id"] for f in document["freedom"]] == [
        f.parameter_id for f in free_parameters()
    ]
    for entry, live in zip(document["freedom"], free_parameters()):
        assert entry["domain"] == "FREE"
        assert entry["freedom"] == live.gap
        assert entry["anchor_ids"] == list(live.anchor_ids)


def test_bindings_list_is_empty_by_content_not_by_omission(document: dict) -> None:
    assert document["bindings"] == []  # present, empty: executed by nothing


def test_a_fabricated_binding_on_a_non_simulated_requirement_is_rejected(
    document: dict,
) -> None:
    doctored = copy.deepcopy(document)
    doctored["bindings"] = [
        {
            "binding_id": "BIND-NVP-FAKE",
            "requirement_id": "NVP-P10",  # informational, never promoted
            "backend": "analytical_l0_crossbar",
            "capability": "bandwidth",
            "parameters": {"B": "FREE"},
            "note": "fabricated",
        }
    ]
    _rejects(doctored, "NVP-P10")


def test_an_upgraded_requirement_without_a_binding_is_an_orphan(document: dict) -> None:
    doctored = copy.deepcopy(document)
    for req in doctored["requirements"]["objects"]:
        if req["requirement_id"] == "NVP-P10":
            req["disposition"] = "simulated_behavior"
    _rejects(doctored, "NVP-P10")


def test_a_fabricated_binding_pair_fails_loudly_on_a_real_backend(document: dict) -> None:
    doctored = copy.deepcopy(document)
    for req in doctored["requirements"]["objects"]:
        if req["requirement_id"] == "NVP-P10":
            req["disposition"] = "simulated_behavior"
    doctored["bindings"] = [
        {
            "binding_id": "BIND-NVP-FAKE",
            "requirement_id": "NVP-P10",
            "backend": "analytical_l0_crossbar",
            "capability": "definitely_not_a_real_capability",
            "parameters": {"B": "FREE"},
            "note": "fabricated",
        }
    ]
    profile = profile_from_dict(doctored)
    from essun.backends.analytical import l0_crossbar

    problems = check_bindings_against(profile, {l0_crossbar.BACKEND_ID: l0_crossbar})
    assert problems


def test_checks_live_in_real_files_and_reference_real_requirements(document: dict) -> None:
    for check in document["checks"]:
        path = REPO_ROOT / check["location"]
        assert path.is_file(), check["location"]
        for requirement_id in check["requirement_ids"]:
            assert requirement_id in {p.parameter_id for p in requirements()}


def test_supported_surface_is_the_real_comparison_sweep(document: dict) -> None:
    # the supported surface names the three-architecture comparison, and
    # the artifacts it names exist
    assert document["supported"]["workloads"] == ["w1_dense_tp_decode"]
    assert document["supported"]["observables"] == ["O-CCT", "O-CONSERVATION"]
    assert THREE_ARCH_SWEEP.is_file()
    assert FLAVOR_FILE.is_file()


def test_every_anchor_citation_resolves_in_the_paper_registry(
    profile: LoadedProfile, registry,
) -> None:
    assert check_anchor_refs(profile, {a.anchor_id for a in registry.anchors}) == []


# -- corruption bars: named rejections, never silent ---------------------------


def test_missing_element_is_rejected_naming_it(document: dict) -> None:
    for key in REQUIRED_KEYS:
        doctored = copy.deepcopy(document)
        del doctored[key]
        _rejects(doctored, key)


def test_unknown_top_level_key_is_rejected_naming_it(document: dict) -> None:
    doctored = copy.deepcopy(document)
    doctored["aspirations"] = []
    _rejects(doctored, "aspirations")


def test_readjudicated_disposition_is_rejected_naming_requirement(document: dict) -> None:
    doctored = copy.deepcopy(document)
    for req in doctored["requirements"]["objects"]:
        if req["requirement_id"] == "NVP-P07":
            req["disposition"] = "normative_fact"  # not in the vocabulary
    _rejects(doctored, "requirements:", "NVP-P07", "normative_fact")


def test_calibration_cannot_carry_targets_while_uncalibrated(document: dict) -> None:
    doctored = copy.deepcopy(document)
    doctored["calibration"]["targets"] = ["CAL-A3"]
    _rejects(doctored, "calibration")


def test_rebuilding_the_artifact_is_byte_identical(tmp_path: Path) -> None:
    out = tmp_path / "nvlink_semantic_profile.yaml"
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.read_text(encoding="utf-8") == ARTIFACT.read_text(encoding="utf-8")
    assert "paper-derived, not normative" in result.stdout
