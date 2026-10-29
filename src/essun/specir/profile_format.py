"""Versioned profile format: loader for the D2 ten-element artifact (S3).

Design doc D2 (docs/plans/design-integration-20261029.md) makes the profile
a first-class, engine-separable artifact with TEN required elements, and
ladder S3 (docs/away/2026-10-29-overnight/prompts/p1_dispositions.md) lands
its versioned format as schema + loader plus conformance tests:

1. ``source``      — source identity/revision
2. ``provenance``  — provenance and permissions (license-gate vocabulary)
3. ``requirements``— interpreted requirements WITH dispositions (D1)
4. ``freedom``     — declared implementation freedom (free parameters)
5. ``bindings``    — backend capability bindings
6. ``checks``      — executable checks (golden / negative / invariant)
7. ``supported``   — supported workloads/observables
8. ``calibration`` — calibration scope (verification != calibration)
9. ``omissions``   — known omissions
10. ``versioning`` — versioning rules (the profile's own version + policy)

plus the two identity keys ``format`` (the format carries its own version
field) and ``profile_id``.  The declarative contract is
``schemas/profile.schema.json``; THIS module is its enforcement, in the
specir house style (problem-list validators, element-named messages: every
problem starts with the top-level key it indicts).  Tests pin the two
layers in agreement on every structural rule, so the published schema
cannot drift from the loader silently.

DRAFT CONTRACT: the format is version ``0.1`` and stays a draft until
promoted by an ADR (workspace rule: "schemas are draft contracts until
promoted by an ADR").  While the format is a 0.x draft, loader and
artifact must agree on the version EXACTLY; minor-version tolerance
arrives with the ADR promotion.  Every change to the format is a
conscious, versioned change.

Honesty rules the format enforces structurally (mirrors D1/S1/S2):

- every requirement carries a disposition from the six-value D1
  vocabulary (:data:`DISPOSITIONS`, imported from the S1 object model —
  one vocabulary, two enforcers);
- an empty interpreted-requirements set is legal only as a VISIBLE
  absence (``requirements.note``), never as a fabricated empty table;
- a disposition is an executable claim, not a label: every
  ``simulated_behavior`` requirement has at least one backend capability
  binding, every ``conformance_test`` requirement is exercised by at
  least one check, and a binding may reference ONLY a
  ``simulated_behavior`` requirement (a binding on an ``unsupported``
  requirement is a contradiction and is rejected);
- calibration scope is explicit: ``uncalibrated`` carries no targets,
  ``partial``/``calibrated`` carry at least one.

Portability (the D2/D5 gate this format exists to make testable): loading
never touches the filesystem beyond the artifact itself, never resolves
anchors against a registry, and never consults the installed backends.
The loud-failure primitives are separate, caller-driven checks:

- :func:`check_bindings_against` — the profile's bindings vs ONE backend's
  declared ``CAPABILITIES`` dict (the shape every essun backend already
  publishes); an unsupported binding fails loudly, by name;
- :func:`check_anchor_refs` — every cited anchor id resolves in a given
  registry (or plain id set).

The UEC and UnifiedBus profiles migrate INTO this format in ladder
S4/S5 — this module ships the format only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .uec_link_transport import DISPOSITIONS

REPO_ROOT = Path(__file__).resolve().parents[3]  # src/essun/specir/ -> repo root
#: The declarative form of this contract (kept in agreement by tests).
SCHEMA_PATH = REPO_ROOT / "schemas" / "profile.schema.json"

#: Identity of the format itself.  The artifact is self-describing
#: (``format: {name, version}``) so a loader can dispatch on it.
PROFILE_FORMAT_NAME = "essun-profile"

#: Format version.  DRAFT CONTRACT until promoted by an ADR; while 0.x,
#: the loader accepts exactly this version (see module docstring).
PROFILE_FORMAT_VERSION = "0.1"

#: Draft status, restated wherever the version is shown to humans.
PROFILE_FORMAT_STATUS = (
    "DRAFT CONTRACT — not promoted by an ADR (workspace rule); "
    f"format {PROFILE_FORMAT_NAME} v{PROFILE_FORMAT_VERSION}"
)

#: The ten D2 elements, as top-level keys of a profile artifact.
D2_ELEMENTS: tuple[str, ...] = (
    "source",
    "provenance",
    "requirements",
    "freedom",
    "bindings",
    "checks",
    "supported",
    "calibration",
    "omissions",
    "versioning",
)

#: Identity keys required alongside the ten elements (not counted in the
#: ten: the format identity block and the profile's stable name).
IDENTITY_KEYS: tuple[str, ...] = ("format", "profile_id")

#: Exactly the keys a valid artifact may carry (the schema's root
#: additionalProperties: false, mirrored).
REQUIRED_KEYS: tuple[str, ...] = IDENTITY_KEYS + D2_ELEMENTS

#: Executable-check kinds (element 6).  ``golden`` pins a value an
#: execution must reproduce; ``negative`` pins a rejection an execution
#: must produce; ``invariant`` pins a relation that must always hold.
CHECK_KINDS: tuple[str, ...] = ("golden", "negative", "invariant")

#: Calibration-scope statuses (element 8).  ``uncalibrated`` is the honest
#: default; ``partial``/``calibrated`` must name their targets.
CALIBRATION_STATUSES: tuple[str, ...] = ("uncalibrated", "partial", "calibrated")

#: Profile versions are X.Y.Z; format versions are X.Y.
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_FORMAT_VERSION_RE = re.compile(r"^\d+\.\d+$")

#: Free parameters are FREE by construction (never a spec value).
_DOMAIN_VALUES: tuple[str, ...] = ("FREE",)


class ProfileFormatError(Exception):
    """Raised when a profile artifact violates the format contract."""


# ---------------------------------------------------------------------------
# typed surface (what S4/S5 and third-party loaders program against)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormatIdentity:
    """The format block: the artifact declares which format loads it."""

    name: str
    version: str


@dataclass(frozen=True)
class SourceIdentity:
    """Element 1: which standard/document the profile interprets."""

    name: str
    document_id: str
    revision: str
    extra: Mapping[str, Any]  # url, ... — preserved verbatim


@dataclass(frozen=True)
class Provenance:
    """Element 2: provenance and permissions (license-gate vocabulary)."""

    source_record: str
    access: str
    note: str = ""
    extra: Mapping[str, Any] = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ProfileRequirement:
    """Element 3, one entry: an interpreted requirement with disposition.

    Extra keys (keyword, subject, unit, value_kind, ...) are preserved so
    the migrating profile families keep their specifics.
    """

    requirement_id: str
    anchor_ids: tuple[str, ...]
    statement: str
    disposition: str
    extra: Mapping[str, Any] = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ProfileFreeParameter:
    """Element 4, one entry: a declared degree of freedom."""

    parameter_id: str
    name: str
    freedom: str
    anchor_ids: tuple[str, ...]
    domain: str = "FREE"
    extra: Mapping[str, Any] = None  # type: ignore[assignment]


@dataclass(frozen=True)
class BackendBinding:
    """Element 5, one entry: requirement -> backend capability."""

    requirement_id: str
    backend: str
    capability: str
    parameters: Mapping[str, Any] = None  # type: ignore[assignment]
    note: str = ""
    extra: Mapping[str, Any] = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ProfileCheck:
    """Element 6, one entry: an executable check."""

    check_id: str
    kind: str
    requirement_ids: tuple[str, ...]
    description: str
    location: str = ""
    extra: Mapping[str, Any] = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SupportedSurface:
    """Element 7: the profile's declared executable surface."""

    workloads: tuple[str, ...]
    observables: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationScope:
    """Element 8: what the profile is calibrated against (or is not)."""

    status: str
    targets: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class KnownOmission:
    """Element 9, one entry: something the profile visibly does not do."""

    what: str
    reason: str = ""


@dataclass(frozen=True)
class VersioningRules:
    """Element 10: the profile's version and declared change policy."""

    profile_version: str
    bump_rules: Mapping[str, tuple[str, ...]]  # major/minor/patch -> fields
    note: str = ""


@dataclass(frozen=True)
class LoadedProfile:
    """A validated profile artifact (all ten elements, typed)."""

    profile_id: str
    format: FormatIdentity
    source: SourceIdentity
    provenance: Provenance
    requirements: tuple[ProfileRequirement, ...]
    requirements_note: str  # visible-absence note; "" when objects exist
    freedom: tuple[ProfileFreeParameter, ...]
    bindings: tuple[BackendBinding, ...]
    checks: tuple[ProfileCheck, ...]
    supported: SupportedSurface
    calibration: CalibrationScope
    omissions: tuple[KnownOmission, ...]
    versioning: VersioningRules

    def requirements_by_id(self) -> dict[str, ProfileRequirement]:
        return {req.requirement_id: req for req in self.requirements}

    def disposition_counts(self) -> dict[str, int]:
        """Per-disposition counts over the profile's requirements.

        All six :data:`DISPOSITIONS` keys are always present, zeros kept
        (the S2 coverage-report convention: a dropped column would be a
        silent claim).
        """
        counts = dict.fromkeys(DISPOSITIONS, 0)
        for req in self.requirements:
            counts[req.disposition] += 1
        return counts

    @property
    def profile_version(self) -> str:
        return self.versioning.profile_version


# ---------------------------------------------------------------------------
# validation (problem lists, element-named messages)
# ---------------------------------------------------------------------------


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _str_list_problems(
    element: str, where: str, values: Any, *, min_items: int
) -> list[str]:
    """Validate a list of non-empty unique strings; name the element."""
    problems: list[str] = []
    if not isinstance(values, list):
        return [f"{element}: {where} must be a list of strings, got {type(values).__name__}"]
    if len(values) < min_items:
        problems.append(
            f"{element}: {where} needs at least {min_items} entr"
            f"{'y' if min_items == 1 else 'ies'}, got {len(values)}"
        )
    for i, value in enumerate(values):
        if not _is_nonempty_str(value):
            problems.append(f"{element}: {where}[{i}] must be a non-empty string")
    duplicates = sorted(
        {v for v in values if isinstance(v, str) and values.count(v) > 1}
    )
    if duplicates:
        problems.append(f"{element}: {where} has duplicate ids {duplicates}")
    return problems


def _mapping_problems(element: str, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return [
            f"{element}: must be a mapping, got {type(value).__name__} "
            f"(see schemas/profile.schema.json)"
        ]
    return []


def _format_problems(fmt: Any) -> list[str]:
    problems = _mapping_problems("format", fmt)
    if problems:
        return problems
    assert isinstance(fmt, dict)
    name = fmt.get("name")
    if name != PROFILE_FORMAT_NAME:
        problems.append(
            f"format: name {name!r} is not {PROFILE_FORMAT_NAME!r} — "
            f"this loader reads {PROFILE_FORMAT_NAME} artifacts"
        )
    version = fmt.get("version")
    if not _is_nonempty_str(version):
        problems.append("format: version must be a non-empty string like '0.1'")
    elif not _FORMAT_VERSION_RE.match(version):
        problems.append(
            f"format: version {version!r} is not an X.Y version string "
            f"(quote it in YAML: unquoted 0.1 parses as a float)"
        )
    elif version != PROFILE_FORMAT_VERSION:
        problems.append(
            f"format: version {version!r} != loader format version "
            f"{PROFILE_FORMAT_VERSION!r} ({PROFILE_FORMAT_STATUS}; while the "
            f"format is a 0.x draft the artifact must match exactly)"
        )
    return problems


def _source_problems(source: Any) -> list[str]:
    problems = _mapping_problems("source", source)
    if problems:
        return problems
    assert isinstance(source, dict)
    for field in ("name", "document_id", "revision"):
        if not _is_nonempty_str(source.get(field)):
            problems.append(
                f"source: {field!r} is required and must be a non-empty "
                f"string (source identity/revision)"
            )
    return problems


def _provenance_problems(provenance: Any) -> list[str]:
    problems = _mapping_problems("provenance", provenance)
    if problems:
        return problems
    assert isinstance(provenance, dict)
    for field in ("source_record", "access"):
        if not _is_nonempty_str(provenance.get(field)):
            problems.append(
                f"provenance: {field!r} is required and must be a non-empty "
                f"string (provenance and permissions; the license-gate "
                f"vocabulary: access is copied verbatim from the source "
                f"registry row)"
            )
    return problems


def _requirements_problems(requirements: Any) -> list[str]:
    problems = _mapping_problems("requirements", requirements)
    if problems:
        return problems
    assert isinstance(requirements, dict)
    objects = requirements.get("objects")
    if not isinstance(objects, list):
        return [
            "requirements: 'objects' is required and must be a list of "
            f"requirement mappings, got {type(objects).__name__}"
        ]
    note = requirements.get("note", "")
    if not objects and not _is_nonempty_str(note):
        problems.append(
            "requirements: no requirement objects and no note — an empty "
            "interpreted set must be a VISIBLE absence (set requirements.note)"
        )
    seen: set[str] = set()
    for i, obj in enumerate(objects):
        where = f"objects[{i}]"
        if not isinstance(obj, dict):
            problems.append(
                f"requirements: {where} must be a mapping, got {type(obj).__name__}"
            )
            continue
        rid = obj.get("requirement_id")
        if not _is_nonempty_str(rid):
            problems.append(
                f"requirements: {where}: 'requirement_id' is required and "
                f"must be a non-empty string"
            )
            rid = None
        elif rid in seen:
            problems.append(
                f"requirements: {where}: duplicate requirement_id {rid!r}"
            )
        else:
            seen.add(rid)
        label = rid or where
        problems.extend(
            _str_list_problems(
                "requirements", f"{label}: anchor_ids", obj.get("anchor_ids"),
                min_items=1,
            )
            if "anchor_ids" in obj
            else [f"requirements: {label}: 'anchor_ids' is required (>= 1)"]
        )
        if not _is_nonempty_str(obj.get("statement")):
            problems.append(
                f"requirements: {label}: 'statement' is required and must be "
                f"a non-empty string"
            )
        disposition = obj.get("disposition")
        if not disposition:
            problems.append(
                f"requirements: {label}: missing disposition "
                f"(one of {DISPOSITIONS})"
            )
        elif disposition not in DISPOSITIONS:
            problems.append(
                f"requirements: {label}: unknown disposition {disposition!r} "
                f"(not in {DISPOSITIONS})"
            )
    return problems


def _freedom_problems(freedom: Any) -> list[str]:
    if not isinstance(freedom, list):
        return [
            f"freedom: must be a list of free-parameter mappings, got "
            f"{type(freedom).__name__}"
        ]
    problems: list[str] = []
    seen: set[str] = set()
    for i, obj in enumerate(freedom):
        where = f"[{i}]"
        if not isinstance(obj, dict):
            problems.append(
                f"freedom: {where} must be a mapping, got {type(obj).__name__}"
            )
            continue
        pid = obj.get("parameter_id")
        label = pid if _is_nonempty_str(pid) else where
        if not _is_nonempty_str(pid):
            problems.append(
                f"freedom: {where}: 'parameter_id' is required and must be "
                f"a non-empty string"
            )
        elif pid in seen:
            problems.append(f"freedom: duplicate parameter_id {pid!r}")
        else:
            seen.add(pid)
        for field in ("name", "freedom"):
            if not _is_nonempty_str(obj.get(field)):
                problems.append(
                    f"freedom: {label}: {field!r} is required and must be a "
                    f"non-empty string"
                )
        if "anchor_ids" not in obj:
            problems.append(
                f"freedom: {label}: 'anchor_ids' is required (>= 1)"
            )
        else:
            problems.extend(
                _str_list_problems(
                    "freedom", f"{label}: anchor_ids", obj["anchor_ids"],
                    min_items=1,
                )
            )
        domain = obj.get("domain", "FREE")
        if domain not in _DOMAIN_VALUES:
            problems.append(
                f"freedom: {label}: domain {domain!r} is not one of "
                f"{_DOMAIN_VALUES} (a free parameter is FREE by construction)"
            )
    return problems


def _bindings_problems(bindings: Any) -> list[str]:
    if not isinstance(bindings, list):
        return [
            f"bindings: must be a list of binding mappings, got "
            f"{type(bindings).__name__}"
        ]
    problems: list[str] = []
    for i, obj in enumerate(bindings):
        where = f"[{i}]"
        if not isinstance(obj, dict):
            problems.append(
                f"bindings: {where} must be a mapping, got {type(obj).__name__}"
            )
            continue
        label = (
            obj.get("requirement_id") if _is_nonempty_str(obj.get("requirement_id")) else where
        )
        for field in ("requirement_id", "backend", "capability"):
            if not _is_nonempty_str(obj.get(field)):
                problems.append(
                    f"bindings: {where}: {field!r} is required and must be a "
                    f"non-empty string"
                )
        if "parameters" in obj and not isinstance(obj["parameters"], dict):
            problems.append(
                f"bindings: {label}: 'parameters' must be a mapping of "
                f"binding parameter values"
            )
    return problems


def _checks_problems(checks: Any) -> list[str]:
    if not isinstance(checks, list):
        return [
            f"checks: must be a list of check mappings, got "
            f"{type(checks).__name__}"
        ]
    problems: list[str] = []
    seen: set[str] = set()
    for i, obj in enumerate(checks):
        where = f"[{i}]"
        if not isinstance(obj, dict):
            problems.append(
                f"checks: {where} must be a mapping, got {type(obj).__name__}"
            )
            continue
        cid = obj.get("check_id")
        label = cid if _is_nonempty_str(cid) else where
        if not _is_nonempty_str(cid):
            problems.append(
                f"checks: {where}: 'check_id' is required and must be a "
                f"non-empty string"
            )
        elif cid in seen:
            problems.append(f"checks: duplicate check_id {cid!r}")
        else:
            seen.add(cid)
        kind = obj.get("kind")
        if kind not in CHECK_KINDS:
            problems.append(
                f"checks: {label}: kind {kind!r} is not one of {CHECK_KINDS}"
            )
        if "requirement_ids" not in obj:
            problems.append(
                f"checks: {label}: 'requirement_ids' is required (>= 1)"
            )
        else:
            problems.extend(
                _str_list_problems(
                    "checks", f"{label}: requirement_ids",
                    obj["requirement_ids"], min_items=1,
                )
            )
        if not _is_nonempty_str(obj.get("description")):
            problems.append(
                f"checks: {label}: 'description' is required and must be a "
                f"non-empty string"
            )
    return problems


def _supported_problems(supported: Any) -> list[str]:
    problems = _mapping_problems("supported", supported)
    if problems:
        return problems
    assert isinstance(supported, dict)
    for field, min_items in (("workloads", 1), ("observables", 1)):
        if field not in supported:
            problems.append(
                f"supported: {field!r} is required (>= 1 id) — the profile's "
                f"executable surface is part of its identity"
            )
        else:
            problems.extend(
                _str_list_problems(
                    "supported", field, supported[field], min_items=min_items
                )
            )
    return problems


def _calibration_problems(calibration: Any) -> list[str]:
    problems = _mapping_problems("calibration", calibration)
    if problems:
        return problems
    assert isinstance(calibration, dict)
    status = calibration.get("status")
    if status not in CALIBRATION_STATUSES:
        return [
            f"calibration: status {status!r} is not one of "
            f"{CALIBRATION_STATUSES}"
        ]
    targets = calibration.get("targets", [])
    if not isinstance(targets, list):
        return [
            "calibration: 'targets' must be a list of anchor/dataset ids"
        ]
    problems.extend(
        _str_list_problems("calibration", "targets", targets, min_items=0)
    )
    if status == "uncalibrated" and targets:
        problems.append(
            f"calibration: status is uncalibrated but targets "
            f"{sorted(targets)} are listed (declare 'partial', or move them "
            f"to the note)"
        )
    if status in ("partial", "calibrated") and not targets:
        problems.append(
            f"calibration: status {status!r} requires at least one target "
            f"(anchor ids or dataset identities)"
        )
    return problems


def _omissions_problems(omissions: Any) -> list[str]:
    if not isinstance(omissions, list):
        return [
            f"omissions: must be a list of omission mappings, got "
            f"{type(omissions).__name__}"
        ]
    problems: list[str] = []
    for i, obj in enumerate(omissions):
        if not isinstance(obj, dict):
            problems.append(
                f"omissions: [{i}] must be a mapping with at least 'what'"
            )
        elif not _is_nonempty_str(obj.get("what")):
            problems.append(
                f"omissions: [{i}]: 'what' is required and must be a "
                f"non-empty string (a known omission is stated visibly)"
            )
    return problems


def _versioning_problems(versioning: Any) -> list[str]:
    problems = _mapping_problems("versioning", versioning)
    if problems:
        return problems
    assert isinstance(versioning, dict)
    version = versioning.get("profile_version")
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        problems.append(
            f"versioning: profile_version {version!r} is not an X.Y.Z "
            f"version string (quote it in YAML)"
        )
    rules = versioning.get("bump_rules")
    if not isinstance(rules, dict):
        problems.append(
            "versioning: 'bump_rules' is required and must be a mapping of "
            "major/minor/patch -> field-name lists"
        )
    else:
        for level in ("major", "minor", "patch"):
            if level not in rules:
                problems.append(
                    f"versioning: bump_rules is missing the {level!r} "
                    f"policy list"
                )
            else:
                problems.extend(
                    _str_list_problems(
                        "versioning", f"bump_rules[{level!r}]", rules[level],
                        min_items=0,
                    )
                )
    return problems


def _cross_reference_problems(data: Mapping[str, Any]) -> list[str]:
    """Loader-only rules the JSON Schema cannot express (see SCHEMA_PATH).

    Dispositions are executable claims: simulated_behavior binds, checks
    exercise, and dangling references are rejected by name.
    """
    problems: list[str] = []
    requirements = data["requirements"]["objects"]
    by_id = {
        obj.get("requirement_id"): obj
        for obj in requirements
        if isinstance(obj, dict) and _is_nonempty_str(obj.get("requirement_id"))
    }
    bindings = data["bindings"]
    checks = data["checks"]

    bound: dict[str, int] = {}
    for i, binding in enumerate(bindings):
        rid = binding.get("requirement_id")
        requirement = by_id.get(rid)
        if requirement is None:
            problems.append(
                f"bindings: [{i}] binds {rid!r}, which is not a requirement "
                f"of this profile (dangling reference)"
            )
            continue
        disposition = requirement.get("disposition")
        if disposition != "simulated_behavior":
            problems.append(
                f"bindings: [{i}] binds {rid!r} whose disposition is "
                f"{disposition!r} — only simulated_behavior requirements may "
                f"bind a backend capability (D1: a disposition is an "
                f"executable claim, not a label)"
            )
        else:
            bound[rid] = bound.get(rid, 0) + 1

    for i, check in enumerate(checks):
        cid = check.get("check_id", f"[{i}]")
        for rid in check.get("requirement_ids", []):
            if rid not in by_id:
                problems.append(
                    f"checks: {cid}: references requirement {rid!r}, which "
                    f"is not a requirement of this profile"
                )

    for rid, requirement in by_id.items():
        disposition = requirement.get("disposition")
        if disposition == "simulated_behavior" and not bound.get(rid):
            problems.append(
                f"requirements: {rid}: disposition simulated_behavior "
                f"requires at least one backend capability binding"
            )
        if disposition == "conformance_test":
            exercising = [
                c.get("check_id", f"[{j}]")
                for j, c in enumerate(checks)
                if rid in c.get("requirement_ids", [])
            ]
            if not exercising:
                problems.append(
                    f"requirements: {rid}: disposition conformance_test "
                    f"requires an executable checks entry referencing it"
                )
    return problems


def profile_problems(data: Any) -> list[str]:
    """Validate a parsed profile artifact; empty list means valid.

    Every problem message names the element it indicts (``"<element>: ..."``),
    so a rejected profile says which of the ten elements (or identity keys)
    is missing or invalid.  All problems are returned, not just the first.
    """
    if not isinstance(data, dict):
        return [
            f"profile: expected a mapping of a profile artifact, got "
            f"{type(data).__name__} (see schemas/profile.schema.json)"
        ]
    problems: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in data:
            kind = (
                "identity key" if key in IDENTITY_KEYS else "element"
            )
            problems.append(f"{key}: required profile {kind} is missing")
    unknown = sorted(set(data) - set(REQUIRED_KEYS))
    if unknown:
        problems.append(
            f"profile: unknown top-level key(s) {unknown} — the format "
            f"allows exactly {list(REQUIRED_KEYS)}"
        )
    element_validators = {
        "format": _format_problems,
        "source": _source_problems,
        "provenance": _provenance_problems,
        "requirements": _requirements_problems,
        "freedom": _freedom_problems,
        "bindings": _bindings_problems,
        "checks": _checks_problems,
        "supported": _supported_problems,
        "calibration": _calibration_problems,
        "omissions": _omissions_problems,
        "versioning": _versioning_problems,
    }
    for element, validate in element_validators.items():
        if element in data:
            problems.extend(validate(data[element]))
    if "profile_id" in data and not _is_nonempty_str(data["profile_id"]):
        problems.append(
            "profile_id: required and must be a non-empty string"
        )
    complete = all(key in data for key in REQUIRED_KEYS)
    if complete:
        # Cross-reference rules only make sense over a structurally whole
        # artifact; run them last so their messages ride on valid shapes.
        structurally_ok = not any(
            problem.split(":", 1)[0] in ("requirements", "bindings", "checks")
            for problem in problems
        )
        if structurally_ok:
            problems.extend(_cross_reference_problems(data))
    return problems


# ---------------------------------------------------------------------------
# loading (parse -> validate -> typed artifact)
# ---------------------------------------------------------------------------


def _extra_of(mapping: Mapping[str, Any], known: tuple[str, ...]) -> dict[str, Any]:
    return {k: v for k, v in mapping.items() if k not in known}


def profile_from_dict(data: Any, *, source: str = "<dict>") -> LoadedProfile:
    """Validate and build a :class:`LoadedProfile` from a parsed mapping.

    Raises :class:`ProfileFormatError` naming each missing/invalid element.
    """
    problems = profile_problems(data)
    if problems:
        identity = data.get("profile_id") if isinstance(data, dict) else None
        who = identity if _is_nonempty_str(identity) else source
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise ProfileFormatError(
            f"profile {who!r} failed format validation "
            f"({PROFILE_FORMAT_STATUS}): {detail}{more}"
        )
    assert isinstance(data, dict)  # validated above
    fmt = data["format"]
    src = data["source"]
    prov = data["provenance"]
    reqs = data["requirements"]
    versioning = data["versioning"]
    return LoadedProfile(
        profile_id=data["profile_id"],
        format=FormatIdentity(name=fmt["name"], version=fmt["version"]),
        source=SourceIdentity(
            name=src["name"],
            document_id=src["document_id"],
            revision=src["revision"],
            extra=_extra_of(src, ("name", "document_id", "revision")),
        ),
        provenance=Provenance(
            source_record=prov["source_record"],
            access=prov["access"],
            note=prov.get("note", ""),
            extra=_extra_of(prov, ("source_record", "access", "note")),
        ),
        requirements=tuple(
            ProfileRequirement(
                requirement_id=obj["requirement_id"],
                anchor_ids=tuple(obj["anchor_ids"]),
                statement=obj["statement"],
                disposition=obj["disposition"],
                extra=_extra_of(
                    obj,
                    ("requirement_id", "anchor_ids", "statement", "disposition"),
                ),
            )
            for obj in reqs["objects"]
        ),
        requirements_note=reqs.get("note", "") if not reqs["objects"] else "",
        freedom=tuple(
            ProfileFreeParameter(
                parameter_id=obj["parameter_id"],
                name=obj["name"],
                freedom=obj["freedom"],
                anchor_ids=tuple(obj["anchor_ids"]),
                domain=obj.get("domain", "FREE"),
                extra=_extra_of(
                    obj,
                    ("parameter_id", "name", "freedom", "anchor_ids", "domain"),
                ),
            )
            for obj in data["freedom"]
        ),
        bindings=tuple(
            BackendBinding(
                requirement_id=obj["requirement_id"],
                backend=obj["backend"],
                capability=obj["capability"],
                parameters=obj.get("parameters", {}) or {},
                note=obj.get("note", ""),
                extra=_extra_of(
                    obj,
                    ("requirement_id", "backend", "capability", "parameters", "note"),
                ),
            )
            for obj in data["bindings"]
        ),
        checks=tuple(
            ProfileCheck(
                check_id=obj["check_id"],
                kind=obj["kind"],
                requirement_ids=tuple(obj["requirement_ids"]),
                description=obj["description"],
                location=obj.get("location", ""),
                extra=_extra_of(
                    obj,
                    ("check_id", "kind", "requirement_ids", "description", "location"),
                ),
            )
            for obj in data["checks"]
        ),
        supported=SupportedSurface(
            workloads=tuple(data["supported"]["workloads"]),
            observables=tuple(data["supported"]["observables"]),
        ),
        calibration=CalibrationScope(
            status=data["calibration"]["status"],
            targets=tuple(data["calibration"].get("targets", [])),
            note=data["calibration"].get("note", ""),
        ),
        omissions=tuple(
            KnownOmission(what=obj["what"], reason=obj.get("reason", ""))
            for obj in data["omissions"]
        ),
        versioning=VersioningRules(
            profile_version=versioning["profile_version"],
            bump_rules={
                level: tuple(versioning["bump_rules"].get(level, ()))
                for level in ("major", "minor", "patch")
            },
            note=versioning.get("note", ""),
        ),
    )


def load_profile(path: Path | str) -> LoadedProfile:
    """Load, validate, and type a profile artifact from a YAML file.

    Loading is placement-independent: nothing outside ``path`` is read
    (anchors and backends are checked by :func:`check_anchor_refs` /
    :func:`check_bindings_against`, never here).
    """
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileFormatError(
            f"profile {path} is not parseable YAML: {exc}"
        ) from exc
    return profile_from_dict(data, source=str(path))


# ---------------------------------------------------------------------------
# loud-failure primitives (the D2/D5 gate hooks; caller-driven on purpose)
# ---------------------------------------------------------------------------


def check_bindings_against(
    profile: LoadedProfile, capabilities: Mapping[str, Any]
) -> list[str]:
    """Check the profile's bindings against ONE backend's capabilities.

    ``capabilities`` is the ``CAPABILITIES`` dict every essun backend
    already declares (``backend_id``, string or tuple/list capability
    fields, and ``explicitly_unsupported``).  This is the D2 gate
    primitive: a profile must load anywhere, and then its bindings must
    either match the executing backend's declared capabilities or FAIL
    LOUDLY by name — never be silently approximated.  Empty list: every
    binding is executable on this backend.
    """
    backend_id = capabilities.get("backend_id")
    if not _is_nonempty_str(backend_id):
        return [
            "capabilities: missing 'backend_id' — a backend's declared "
            "capability dict is required to check bindings against it"
        ]
    offered: set[str] = set()
    for key, value in capabilities.items():
        if key in ("backend_id", "explicitly_unsupported"):
            continue
        if isinstance(value, str):
            offered.add(value)
        elif isinstance(value, (list, tuple)):
            offered.update(v for v in value if isinstance(v, str))
    unsupported = {
        v
        for v in capabilities.get("explicitly_unsupported", ())
        if isinstance(v, str)
    }
    problems: list[str] = []
    for binding in profile.bindings:
        label = (
            f"{binding.requirement_id} -> "
            f"{binding.backend}.{binding.capability}"
        )
        if binding.backend != backend_id:
            problems.append(
                f"bindings: {label}: profile binds backend "
                f"{binding.backend!r}, but this backend is {backend_id!r}"
            )
            continue
        if binding.capability in unsupported:
            problems.append(
                f"bindings: {label}: capability is declared "
                f"explicitly_unsupported by {backend_id!r} — failing loudly, "
                f"never silently approximating it"
            )
        elif binding.capability not in offered:
            problems.append(
                f"bindings: {label}: backend {backend_id!r} declares no "
                f"such capability (offered: {sorted(offered)})"
            )
    return problems


def check_anchor_refs(
    profile: LoadedProfile,
    registry: Any,
) -> list[str]:
    """Check that every anchor id the profile cites resolves.

    ``registry`` is an :class:`~essun.specir.anchors.AnchorRegistry` (or
    any object with a ``by_id()`` mapping) or a plain collection of known
    anchor ids.  Kept OUT of :func:`load_profile` on purpose: the artifact
    loads anywhere (D5 portability); anchor resolution is the caller's
    explicit, environment-specific check.  Empty list: every citation
    resolves.
    """
    if hasattr(registry, "by_id"):
        known: Any = set(registry.by_id())
    else:
        known = set(registry)
    problems: list[str] = []
    for req in profile.requirements:
        dangling = [aid for aid in req.anchor_ids if aid not in known]
        if dangling:
            problems.append(
                f"requirements: {req.requirement_id}: dangling anchor ids "
                f"{dangling} (not in the provided registry)"
            )
    for param in profile.freedom:
        dangling = [aid for aid in param.anchor_ids if aid not in known]
        if dangling:
            problems.append(
                f"freedom: {param.parameter_id}: dangling anchor ids "
                f"{dangling} (not in the provided registry)"
            )
    return problems
