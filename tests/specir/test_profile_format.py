"""S3 of the dispositions/profile ladder: the versioned profile format.

Design doc D2 gate: "profile-format conformance tests; a profile must load
and its checks run on ANY compliant backend, with unsupported bindings
failing loudly."  This file pins the format landed in S3
(:mod:`essun.specir.profile_format` + ``schemas/profile.schema.json``):

- the EXAMPLE artifact (``examples/profile.example.yaml``) loads and
  types into :class:`~essun.specir.profile_format.LoadedProfile`;
- every missing or invalid element is REJECTED NAMING THE ELEMENT — each
  of the ten D2 elements plus the two identity keys, one test each;
- every problem message is element-prefixed (the naming convention is
  itself under test, not just each case);
- dispositions are executable claims: simulated_behavior requires a
  binding, conformance_test requires a check, a binding on a
  non-simulated_behavior requirement is rejected, dangling references are
  rejected;
- the published JSON Schema and the loader agree on every structural rule
  (both reject the same battery of mutations), so neither can drift
  silently — the cross-reference rules are loader-only by design and say
  so;
- the loud-failure primitives do what the D2 gate needs:
  :func:`~essun.specir.profile_format.check_bindings_against` names the
  backend, capability, and requirement when a backend cannot execute a
  binding (including explicitly-unsupported ones);
  :func:`~essun.specir.profile_format.check_anchor_refs` names dangling
  citations.  Neither runs at load: the artifact loads anywhere.

The example is a fictional "widgynet" profile on purpose: the real UEC
and UnifiedBus migrations are ladder S4/S5 and are NOT done here.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from essun.specir.profile_format import (
    CALIBRATION_STATUSES,
    CHECK_KINDS,
    D2_ELEMENTS,
    IDENTITY_KEYS,
    PROFILE_FORMAT_NAME,
    PROFILE_FORMAT_STATUS,
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
from essun.specir.uec_link_transport import DISPOSITIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "profile.example.yaml"
SCHEMA = REPO_ROOT / "schemas" / "profile.schema.json"

#: Anchor ids cited by the example profile (EX-* ids are fictional, so a
#: stub registry is the honest way to exercise resolution).
EXAMPLE_ANCHORS = {
    "EX-S2.1-CREDITS",
    "EX-S3.1-RETRY",
    "EX-S5.1-MTU",
    "EX-S4-ARBITRATION",
}

#: One backend's declared capability dict, in the same shape every essun
#: backend publishes (see src/essun/backends/analytical/l0.py CAPABILITIES).
#: It executes the example profile's single binding (EX-R01 ->
#: example_backend.credit_accounting).
EXAMPLE_CAPABILITIES = {
    "backend_id": "example_backend",
    "fidelity": "L0",
    "collectives": ("allreduce_ring",),
    "credit_semantics": ("credit_accounting", "credit_return"),
    "observables": ("O-CCT",),
    "explicitly_unsupported": ("multicast_credits",),
}


@pytest.fixture()
def example_dict() -> dict:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture()
def example() -> LoadedProfile:
    return load_profile(EXAMPLE)


def _rejects(data, *needles: str) -> list[str]:
    """Assert the artifact is rejected, return its problems.

    With needles: each must appear in the joined error text.
    """
    with pytest.raises(ProfileFormatError) as excinfo:
        profile_from_dict(data)
    text = str(excinfo.value)
    for needle in needles:
        assert needle in text, f"{needle!r} not named in: {text}"
    return profile_problems(data)


# -- a valid profile loads ----------------------------------------------------


def test_example_profile_loads_from_file(example: LoadedProfile) -> None:
    assert example.profile_id == "example-widgynet-profile"
    assert example.format.name == PROFILE_FORMAT_NAME
    assert example.format.version == PROFILE_FORMAT_VERSION
    assert example.source.document_id == "STD-EXAMPLE-WIDGENET"
    assert example.source.revision == "1.0"
    assert example.provenance.access == "PUBLIC_READ"
    assert example.calibration.status == "uncalibrated"
    assert example.calibration.targets == ()
    assert example.supported.workloads == ("W1",)
    assert example.supported.observables == ("O-CCT",)
    assert example.profile_version == "0.1.0"
    assert example.versioning.bump_rules["major"] == (
        "dispositions",
        "bindings",
        "calibration",
    )


def test_example_requirements_carry_dispositions_and_extras(
    example: LoadedProfile,
) -> None:
    by_id = example.requirements_by_id()
    assert set(by_id) == {"EX-R01", "EX-R02", "EX-R03", "EX-R04"}
    assert by_id["EX-R01"].disposition == "simulated_behavior"
    assert by_id["EX-R01"].extra["keyword"] == "MUST"  # extras preserved
    assert by_id["EX-R02"].disposition == "unsupported"
    assert by_id["EX-R04"].disposition == "conformance_test"
    assert by_id["EX-R01"].anchor_ids == ("EX-S2.1-CREDITS",)


def test_disposition_counts_keep_all_six_columns(
    example: LoadedProfile,
) -> None:
    counts = example.disposition_counts()
    assert set(counts) == set(DISPOSITIONS)  # zeros kept (S2 convention)
    assert counts == {
        "constraint": 0,
        "simulated_behavior": 1,
        "conformance_test": 1,
        "informational": 1,
        "unsupported": 1,
        "not_applicable": 0,
    }


def test_format_module_exports_the_d2_elements() -> None:
    # The format is the ten D2 elements plus the two identity keys.
    assert len(D2_ELEMENTS) == 10
    assert set(REQUIRED_KEYS) == set(IDENTITY_KEYS) | set(D2_ELEMENTS)
    assert "format" in IDENTITY_KEYS and "profile_id" in IDENTITY_KEYS
    assert PROFILE_FORMAT_STATUS.startswith("DRAFT CONTRACT")


def test_load_profile_rejects_unparseable_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.profile.yaml"
    bad.write_text("format: [unclosed\n  bad indent", encoding="utf-8")
    with pytest.raises(ProfileFormatError, match="not parseable YAML"):
        load_profile(bad)


def test_load_profile_from_written_file(
    example_dict: dict, tmp_path: Path
) -> None:
    artifact = tmp_path / "copy.profile.yaml"
    artifact.write_text(yaml.safe_dump(example_dict), encoding="utf-8")
    loaded = load_profile(artifact)
    assert loaded.profile_id == "example-widgynet-profile"


# -- an invalid profile is rejected NAMING the element ------------------------


@pytest.mark.parametrize(
    "key", REQUIRED_KEYS, ids=lambda k: f"missing-{k}"
)
def test_missing_element_is_rejected_naming_it(
    example_dict: dict, key: str
) -> None:
    del example_dict[key]
    _rejects(example_dict, f"{key}:")


def test_two_missing_elements_are_both_named(example_dict: dict) -> None:
    del example_dict["calibration"]
    del example_dict["checks"]
    problems = _rejects(example_dict, "calibration:", "checks:")
    assert any(p.startswith("calibration:") for p in problems)
    assert any(p.startswith("checks:") for p in problems)


def test_unknown_top_level_key_is_rejected_naming_it(
    example_dict: dict,
) -> None:
    example_dict["executed_claims"] = ["everything"]
    _rejects(example_dict, "unknown top-level key", "executed_claims")


def test_not_a_mapping_is_rejected() -> None:
    problems = profile_problems(["not", "a", "mapping"])
    assert problems == [
        "profile: expected a mapping of a profile artifact, got list "
        "(see schemas/profile.schema.json)"
    ]


def test_wrong_format_name_is_rejected_naming_format(
    example_dict: dict,
) -> None:
    example_dict["format"]["name"] = "some-other-format"
    _rejects(example_dict, "format:", "some-other-format")


def test_wrong_format_version_is_rejected_naming_format(
    example_dict: dict,
) -> None:
    example_dict["format"]["version"] = "0.2"
    _rejects(example_dict, "format:", "0.2")


def test_unquoted_yaml_float_version_is_rejected_with_hint(
    example_dict: dict,
) -> None:
    example_dict["format"]["version"] = 0.1  # what unquoted 0.1 parses as
    _rejects(example_dict, "format:", "non-empty string like '0.1'")


def test_bad_disposition_is_rejected_naming_requirement_and_value(
    example_dict: dict,
) -> None:
    example_dict["requirements"]["objects"][1]["disposition"] = "banana"
    _rejects(example_dict, "requirements:", "EX-R02", "banana")


def test_missing_disposition_is_rejected(example_dict: dict) -> None:
    del example_dict["requirements"]["objects"][1]["disposition"]
    _rejects(example_dict, "requirements:", "EX-R02", "missing disposition")


def test_anchorless_requirement_is_rejected(example_dict: dict) -> None:
    del example_dict["requirements"]["objects"][0]["anchor_ids"]
    _rejects(example_dict, "requirements:", "EX-R01", "anchor_ids")


def test_duplicate_requirement_ids_are_rejected(example_dict: dict) -> None:
    objects = example_dict["requirements"]["objects"]
    objects[1]["requirement_id"] = objects[0]["requirement_id"]
    _rejects(example_dict, "requirements:", "duplicate requirement_id")


def test_bad_profile_version_is_rejected_naming_versioning(
    example_dict: dict,
) -> None:
    example_dict["versioning"]["profile_version"] = "v1-final"
    _rejects(example_dict, "versioning:", "profile_version")


def test_missing_bump_rules_level_is_rejected(example_dict: dict) -> None:
    del example_dict["versioning"]["bump_rules"]["patch"]
    _rejects(example_dict, "versioning:", "bump_rules", "patch")


def test_bad_check_kind_is_rejected_naming_checks(
    example_dict: dict,
) -> None:
    example_dict["checks"][0]["kind"] = "fuzz"
    _rejects(example_dict, "checks:", "fuzz")


def test_bad_calibration_status_is_rejected_naming_calibration(
    example_dict: dict,
) -> None:
    example_dict["calibration"]["status"] = "probably-fine"
    _rejects(example_dict, "calibration:", "probably-fine")


def test_uncalibrated_with_targets_is_rejected(example_dict: dict) -> None:
    example_dict["calibration"]["targets"] = ["EX-S2.1-CREDITS"]
    _rejects(example_dict, "calibration:", "uncalibrated", "targets")


def test_calibrated_without_targets_is_rejected(example_dict: dict) -> None:
    example_dict["calibration"].update(status="calibrated", targets=[])
    _rejects(example_dict, "calibration:", "calibrated", "target")


def test_empty_supported_surface_is_rejected(example_dict: dict) -> None:
    example_dict["supported"]["observables"] = []
    _rejects(example_dict, "supported:", "observables")


# -- dispositions are executable claims, not labels ---------------------------


def test_simulated_behavior_requires_a_binding(example_dict: dict) -> None:
    example_dict["bindings"] = []
    _rejects(
        example_dict,
        "requirements:",
        "EX-R01",
        "simulated_behavior requires at least one backend capability binding",
    )


def test_binding_on_unsupported_requirement_is_a_contradiction(
    example_dict: dict,
) -> None:
    example_dict["bindings"][0]["requirement_id"] = "EX-R02"
    _rejects(
        example_dict,
        "bindings:",
        "EX-R02",
        "only simulated_behavior requirements may bind a backend capability",
    )


def test_dangling_binding_reference_is_rejected(example_dict: dict) -> None:
    example_dict["bindings"][0]["requirement_id"] = "EX-R99"
    _rejects(example_dict, "bindings:", "EX-R99", "dangling reference")


def test_conformance_test_requires_a_check(example_dict: dict) -> None:
    example_dict["checks"] = [c for c in example_dict["checks"]
                              if "EX-R04" not in c["requirement_ids"]]
    _rejects(
        example_dict,
        "requirements:",
        "EX-R04",
        "conformance_test requires an executable checks entry",
    )


def test_check_with_dangling_requirement_ids_is_rejected(
    example_dict: dict,
) -> None:
    example_dict["checks"][0]["requirement_ids"] = ["EX-R77"]
    _rejects(example_dict, "checks:", "EX-C01", "EX-R77")


# -- an empty interpreted set is a VISIBLE absence ----------------------------


def test_empty_requirements_without_note_are_rejected(
    example_dict: dict,
) -> None:
    example_dict["requirements"] = {"objects": []}
    _rejects(example_dict, "requirements:", "VISIBLE absence")


def test_empty_requirements_with_note_load(example_dict: dict) -> None:
    example_dict["requirements"] = {
        "objects": [],
        "note": "interpreted set lands with the S5 migration",
    }
    # A profile with no interpreted requirements has nothing to bind or
    # check, so those must go too — the note is the whole story.
    example_dict["bindings"] = []
    example_dict["checks"] = []
    loaded = profile_from_dict(example_dict)
    assert loaded.requirements == ()
    assert loaded.requirements_note.startswith("interpreted set")
    assert all(count == 0 for count in loaded.disposition_counts().values())


# -- the published schema and the loader cannot drift silently -----------------


def _schema_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def test_example_validates_against_the_published_schema() -> None:
    example = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    _schema_validator().validate(example)  # raises on any mismatch


def test_schema_pins_the_disposition_and_element_vocabularies() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    root_required = schema["required"]
    assert set(root_required) == set(REQUIRED_KEYS)
    assert schema["additionalProperties"] is False
    disposition = schema["$defs"]["requirement"]["properties"]["disposition"]
    assert set(disposition["enum"]) == set(DISPOSITIONS)
    kinds = schema["$defs"]["check"]["properties"]["kind"]
    assert set(kinds["enum"]) == set(CHECK_KINDS)
    status = schema["properties"]["calibration"]["properties"]["status"]
    assert set(status["enum"]) == set(CALIBRATION_STATUSES)
    assert schema["properties"]["format"]["properties"]["name"]["const"] == (
        PROFILE_FORMAT_NAME
    )


#: Structural mutations the SCHEMA and the LOADER must both reject.
#: (Cross-reference rules are loader-only — the schema says so in its
#: description — so they are not in this battery.)
def _structural_mutations():
    def remove(key):
        def mutate(d):
            del d[key]
        return mutate

    def disposition_banana(d):
        d["requirements"]["objects"][1]["disposition"] = "banana"

    def kind_fuzz(d):
        d["checks"][0]["kind"] = "fuzz"

    def status_bogus(d):
        d["calibration"]["status"] = "probably-fine"

    def empty_requirements_no_note(d):
        d["requirements"] = {"objects": []}

    def requirements_as_list(d):
        d["requirements"] = []

    def no_anchor_ids(d):
        del d["requirements"]["objects"][0]["anchor_ids"]

    def empty_workloads(d):
        d["supported"]["workloads"] = []

    def bad_semver(d):
        d["versioning"]["profile_version"] = "1.0"

    def bad_format_version(d):
        d["format"]["version"] = "0.1.0"

    cases = [(f"remove-{key}", remove(key)) for key in REQUIRED_KEYS]
    cases += [
        ("disposition-outside-vocabulary", disposition_banana),
        ("check-kind-outside-vocabulary", kind_fuzz),
        ("calibration-status-outside-vocabulary", status_bogus),
        ("empty-requirements-without-note", empty_requirements_no_note),
        ("requirements-not-a-mapping", requirements_as_list),
        ("requirement-without-anchor-ids", no_anchor_ids),
        ("supported-workloads-empty", empty_workloads),
        ("profile-version-not-semver", bad_semver),
        ("format-version-not-X.Y", bad_format_version),
    ]
    return cases


_STRUCTURAL_CASES = _structural_mutations()


@pytest.mark.parametrize(
    "name,mutate", _STRUCTURAL_CASES, ids=[name for name, _ in _STRUCTURAL_CASES]
)
def test_schema_and_loader_reject_the_same_structural_faults(
    example_dict: dict, name: str, mutate
) -> None:
    mutated = copy.deepcopy(example_dict)
    mutate(mutated)
    schema_invalid = not _schema_validator().is_valid(mutated)
    loader_problems = profile_problems(mutated)
    assert schema_invalid, f"{name}: the published schema accepted a fault"
    assert loader_problems, f"{name}: the loader accepted a fault"


@pytest.mark.parametrize(
    "name,mutate", _STRUCTURAL_CASES, ids=[name for name, _ in _STRUCTURAL_CASES]
)
def test_every_problem_message_names_an_element(
    example_dict: dict, name: str, mutate
) -> None:
    mutated = copy.deepcopy(example_dict)
    mutate(mutated)
    for problem in profile_problems(mutated):
        prefix = problem.split(":", 1)[0]
        assert prefix in REQUIRED_KEYS + ("profile",), (
            f"{name}: problem not element-named: {problem!r}"
        )


# -- unsupported bindings fail LOUDLY (the D2 gate primitive) ------------------


def test_bindings_supported_by_the_backend_pass(example: LoadedProfile) -> None:
    assert check_bindings_against(example, EXAMPLE_CAPABILITIES) == []


def test_unknown_capability_fails_loudly_by_name(
    example: LoadedProfile,
) -> None:
    capabilities = dict(EXAMPLE_CAPABILITIES)
    capabilities["credit_semantics"] = ()  # credit_accounting now undeclared
    problems = check_bindings_against(example, capabilities)
    assert len(problems) == 1
    assert "EX-R01 -> example_backend.credit_accounting" in problems[0]
    assert "declares no such capability" in problems[0]


def test_explicitly_unsupported_binding_fails_loudly(
    example: LoadedProfile,
) -> None:
    capabilities = dict(EXAMPLE_CAPABILITIES)
    # The backend executes credit semantics but rejects this flavor.
    capabilities["credit_semantics"] = ("credit_return",)
    capabilities["explicitly_unsupported"] = ("credit_accounting",)
    problems = check_bindings_against(example, capabilities)
    assert len(problems) == 1
    assert "explicitly_unsupported" in problems[0]
    assert "never silently approximating" in problems[0]


def test_binding_for_a_different_backend_fails_loudly(
    example: LoadedProfile,
) -> None:
    capabilities = dict(EXAMPLE_CAPABILITIES, backend_id="other_backend")
    problems = check_bindings_against(example, capabilities)
    assert len(problems) == 1
    assert "profile binds backend 'example_backend'" in problems[0]
    assert "other_backend" in problems[0]


def test_capability_check_requires_a_backend_id(example: LoadedProfile) -> None:
    problems = check_bindings_against(example, {"fidelity": "L0"})
    assert problems == [
        "capabilities: missing 'backend_id' — a backend's declared "
        "capability dict is required to check bindings against it"
    ]


# -- anchor citations resolve (explicitly, never at load) ---------------------


def test_anchor_refs_resolve_against_a_registry(example: LoadedProfile) -> None:
    assert check_anchor_refs(example, EXAMPLE_ANCHORS) == []


def test_dangling_anchor_refs_are_named(example: LoadedProfile) -> None:
    known = EXAMPLE_ANCHORS - {"EX-S3.1-RETRY", "EX-S4-ARBITRATION"}
    problems = check_anchor_refs(example, known)
    assert len(problems) == 2
    assert any(
        p.startswith("requirements: EX-R02:") and "EX-S3.1-RETRY" in p
        for p in problems
    )
    assert any(
        p.startswith("freedom: EX-F01:") and "EX-S4-ARBITRATION" in p
        for p in problems
    )


def test_anchor_check_accepts_by_id_registry_objects(
    example: LoadedProfile,
) -> None:
    class StubRegistry:
        def by_id(self):
            return {aid: object() for aid in EXAMPLE_ANCHORS}

    assert check_anchor_refs(example, StubRegistry()) == []
