"""D3 orthogonal evidence dimensions on run records (store-side).

Design doc D3 (docs/plans/design-integration-20261029.md): verification is
not calibration is not independent reproduction is not physical validity —
"a result can be reproduced and still wrong."  A run record therefore
carries the five facts SEPARATELY, as structured top-level fields:

1. ``verification``              — what checks passed, in what scope
2. ``calibration_target``        — anchor ids, or none (empty list)
3. ``held_out``                  — bool + scope
4. ``independent_reproduction``  — none yet (empty list) — honest
5. ``known_omissions``           — stated omissions

The public label ladder (PROPOSED / IMPLEMENTED_UNVERIFIED / … and the
E0..E4 evidence levels) is a COMMUNICATION device and is unchanged; these
fields are the record-level facts underneath it.  Nothing here may invent
a value: every field is declared by the experiment manifest or absent.

Absence semantics (the rule this module exists to enforce):

- an ABSENT dimension is ``UNKNOWN`` — :data:`UNKNOWN` — and is never
  silently defaulted to ``False``, ``None``, or an empty list.  "We do not
  know" and "we know: none" are different states, and the reader
  (:func:`read_dimensions`) keeps them different;
- a PRESENT dimension is the recorded fact, even when the fact is "none":
  ``calibration_target: []`` means uncalibrated-by-declaration, and
  ``independent_reproduction: []`` means considered-and-none-exist (the
  honest value everywhere today), not "not applicable".

Run-record schema VERSION BUMP (1 -> 2):

- version 1 — every record stored before D3: none of the five keys, no
  ``evidence_schema_version`` key.  These records still load, unchanged
  (the backfill-safe gate: their dimensions read as UNKNOWN);
- version 2 — :data:`RUN_RECORD_SCHEMA_VERSION`, the version this code
  writes: records MAY carry the five dimensions; a record that carries
  ANY of them MUST stamp ``evidence_schema_version: 2``.  A version-2
  record with no dimensions is legal (all five read UNKNOWN — absence is
  still allowed; the fields are per-dimension optional in the record).

Manifest side: the experiment manifest may declare the block

.. code-block:: yaml

    evidence_dimensions:
      verification:
      - check: tests/golden/test_w1_l0_golden.py
        scope: W1 smoke identity on ring8 free parameters
      calibration_target: []          # anchor ids, or none
      held_out:
        held_out: false
        scope: no data withheld; all inputs derive from the identity
      independent_reproduction: []    # none yet — honest
      known_omissions:
      - steady-state only; fill/drain transients excluded

and the run path (:mod:`essun.orchestrator.runs`) copies it, validated,
into the run payload together with the version stamp.  Declaring the
block requires ALL five dimensions — you cannot declare the block and
stay silent on one; silence is what omitting the block means.
``calibration_target`` entries follow the same vocabulary as the D2
profile format's calibration element (anchor registry ids or dataset
identities); resolving them against a registry is a downstream,
caller-driven check, never a load-time one.

Determinism: the fields are pure functions of the manifest, so they enter
the content address (run_id) exactly like every other payload byte, and
manifests WITHOUT the block produce byte-identical run_ids to before this
change — already-stored goldens (e.g. the TFC flagship run
``dc7d83b6…``) re-run byte-identically.
"""

from __future__ import annotations

from typing import Any, Mapping

#: Run-record schema version this code writes and understands.  Version 1
#: is every record stored before D3 (no dimension keys, no version key);
#: those still load.  See the module docstring for the version contract.
RUN_RECORD_SCHEMA_VERSION = 2

#: The run-payload key carrying the record's schema version.  Present
#: only on records written at version >= 2 (or explicitly claiming 1).
SCHEMA_VERSION_KEY = "evidence_schema_version"

#: The five D3 dimensions, as run-record top-level keys.  Order is the
#: design doc's order and is stable (it is part of the human-facing
#: presentation of a record's evidence).
EVIDENCE_DIMENSIONS: tuple[str, ...] = (
    "verification",
    "calibration_target",
    "held_out",
    "independent_reproduction",
    "known_omissions",
)

#: The reading of an absent dimension.  A string (not ``False``, not
#: ``None``) so it can never be confused with a recorded boolean or an
#: empty "none": unknown means "not stated by this record".
UNKNOWN = "UNKNOWN"

#: The manifest key that declares the dimensions block.
MANIFEST_KEY = "evidence_dimensions"

# Exactly the keys a ``held_out`` dimension may carry (bool + scope).
HELD_OUT_KEYS = ("held_out", "scope")

# Exactly the keys a ``verification`` entry may carry (check + scope).
VERIFICATION_ENTRY_KEYS = ("check", "scope")


class DimensionsError(ValueError):
    """Raised when a dimensions block or dimension field is malformed.

    A ``ValueError`` subclass on purpose: the evidence store catches it
    and re-raises as its own ``EvidenceError``, and the run path wraps it
    into its ``ExecutionError`` — each layer keeps its native exception
    while the message (dimension-prefixed, per the house style) passes
    through unchanged.
    """


def _str_problems(dimension: str, field: str, value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"{dimension}: {field} must be a non-empty string"]
    return []


def _str_list_problems(dimension: str, value: Any) -> list[str]:
    """Problems with a list-of-non-empty-strings dimension value.

    Empty lists are LEGAL: they are the explicit "none" (uncalibrated,
    no reproductions yet, no omissions known) — distinct from absence.
    ``None`` is illegal: write ``[]`` for none, omit the dimension for
    unknown.
    """
    if not isinstance(value, list):
        return [f"{dimension}: must be a list (of non-empty strings)"]
    for item in value:
        if not isinstance(item, str) or not item:
            return [f"{dimension}: each entry must be a non-empty string"]
    return []


def _verification_problems(value: Any) -> list[str]:
    """What checks passed, in what scope: a list of {check, scope}."""
    if not isinstance(value, list):
        return ["verification: must be a list of {check, scope} entries"]
    for index, entry in enumerate(value):
        label = f"verification: entry {index}"
        if not isinstance(entry, dict):
            return [f"{label}: must be a mapping with 'check' and 'scope'"]
        unknown = [key for key in entry if key not in VERIFICATION_ENTRY_KEYS]
        if unknown:
            return [f"{label}: unknown field(s): {', '.join(sorted(unknown))}"]
        missing = [key for key in VERIFICATION_ENTRY_KEYS if key not in entry]
        if missing:
            return [f"{label}: missing field(s): {', '.join(missing)}"]
        problems = _str_problems(label, "check", entry["check"]) + _str_problems(
            label, "scope", entry["scope"]
        )
        if problems:
            return problems
    return []


def _calibration_target_problems(value: Any) -> list[str]:
    """Anchor ids (or dataset identities), or none: list of id strings."""
    return _str_list_problems("calibration_target", value)


def _held_out_problems(value: Any) -> list[str]:
    """Bool + scope: {held_out: bool, scope: non-empty string}."""
    if not isinstance(value, dict):
        return ["held_out: must be a mapping with 'held_out' (bool) and 'scope'"]
    unknown = [key for key in value if key not in HELD_OUT_KEYS]
    if unknown:
        return [f"held_out: unknown field(s): {', '.join(sorted(unknown))}"]
    missing = [key for key in HELD_OUT_KEYS if key not in value]
    if missing:
        return [f"held_out: missing field(s): {', '.join(missing)}"]
    if not isinstance(value["held_out"], bool):
        return ["held_out: 'held_out' must be a boolean (never a defaulted value)"]
    return _str_problems("held_out", "scope", value["scope"])


def _independent_reproduction_problems(value: Any) -> list[str]:
    """External reproduction references, or none YET: list of strings."""
    return _str_list_problems("independent_reproduction", value)


def _known_omissions_problems(value: Any) -> list[str]:
    """Stated omissions, or none: list of non-empty strings."""
    return _str_list_problems("known_omissions", value)


#: Per-dimension validators (the dimension-prefixed-message dispatch).
_DIMENSION_VALIDATORS = {
    "verification": _verification_problems,
    "calibration_target": _calibration_target_problems,
    "held_out": _held_out_problems,
    "independent_reproduction": _independent_reproduction_problems,
    "known_omissions": _known_omissions_problems,
}

#: The honest value of ``independent_reproduction`` today, everywhere:
#: considered, none exist.  Provided as a constant so callers (and
#: manifests) can name it instead of retyping it; it is a plain empty
#: list, and empty is the point.
INDEPENDENT_REPRODUCTION_NONE_YET: list[str] = []


def dimensions_problems(block: Any) -> list[str]:
    """All structural problems of a declared dimensions block.

    A block is a mapping carrying ALL five dimensions (the manifest
    cannot declare the block and stay silent on one) and nothing else.
    Empty problems means the block is valid.  Messages are
    dimension-prefixed.
    """
    if not isinstance(block, dict):
        return [f"{MANIFEST_KEY}: must be a mapping of the five dimensions"]
    missing = [name for name in EVIDENCE_DIMENSIONS if name not in block]
    if missing:
        return [f"{MANIFEST_KEY}: missing dimension(s): {', '.join(missing)}"]
    unknown = [key for key in block if key not in EVIDENCE_DIMENSIONS]
    if unknown:
        return [f"{MANIFEST_KEY}: unknown dimension(s): {', '.join(sorted(unknown))}"]
    for name in EVIDENCE_DIMENSIONS:
        problems = _DIMENSION_VALIDATORS[name](block[name])
        if problems:
            return problems
    return []


def validate_dimensions(block: Any) -> None:
    """Validate a declared dimensions block; raise on the first problem list."""
    problems = dimensions_problems(block)
    if problems:
        raise DimensionsError("; ".join(problems))


def dimensions_from_manifest(manifest: Mapping) -> dict | None:
    """The validated dimensions block of a manifest, or ``None``.

    ``None`` means the manifest does not declare the block — its run
    record carries none of the five keys and every dimension reads
    UNKNOWN.  Raises :class:`DimensionsError` (a ``ValueError``) when the
    declared block is malformed.
    """
    if MANIFEST_KEY not in manifest:
        return None
    block = manifest[MANIFEST_KEY]
    validate_dimensions(block)
    return {name: block[name] for name in EVIDENCE_DIMENSIONS}


def run_record_problems(payload: Mapping) -> list[str]:
    """All dimension problems of a RUN PAYLOAD (version rules included).

    Rules (the version-2 contract, enforced at the store door):

    - each of the five keys present in the payload must be a VALID
      dimension (per-dimension validators); any may be absent — absence
      is UNKNOWN, never an error;
    - a payload carrying ANY dimension MUST stamp
      ``evidence_schema_version: 2``;
    - a stamped version must be an integer in ``1..RUN_RECORD_SCHEMA_VERSION``
      (a future version is not silently loadable);
    - version 1 with dimensions is a contradiction (version 1 is
      definitionally dimension-free).
    """
    if not isinstance(payload, Mapping):
        return ["run payload: must be a mapping"]
    problems: list[str] = []
    present = [name for name in EVIDENCE_DIMENSIONS if name in payload]
    for name in present:
        problems.extend(_DIMENSION_VALIDATORS[name](payload[name]))
    version = payload.get(SCHEMA_VERSION_KEY)
    if version is None:
        if present:
            problems.append(
                f"{SCHEMA_VERSION_KEY}: required ({RUN_RECORD_SCHEMA_VERSION}) when "
                f"any evidence dimension is present, missing for: {', '.join(present)}"
            )
    elif not isinstance(version, int) or isinstance(version, bool) or version < 1:
        problems.append(
            f"{SCHEMA_VERSION_KEY}: must be an integer >= 1, got {version!r}"
        )
    elif version > RUN_RECORD_SCHEMA_VERSION:
        problems.append(
            f"{SCHEMA_VERSION_KEY}: {version} is newer than this store understands "
            f"(max {RUN_RECORD_SCHEMA_VERSION})"
        )
    elif version == 1 and present:
        problems.append(
            f"{SCHEMA_VERSION_KEY}: version 1 records carry no evidence dimensions "
            f"(found: {', '.join(present)})"
        )
    return problems


def validate_run_record(payload: Mapping) -> None:
    """Validate a run payload's dimensions; raise on the first problem list."""
    problems = run_record_problems(payload)
    if problems:
        raise DimensionsError("; ".join(problems))


def dimension_value(record: Mapping, name: str) -> Any:
    """One dimension of a stored record: the recorded value, or UNKNOWN.

    For an ABSENT dimension the answer is :data:`UNKNOWN` — never
    ``False``, never ``None``, never ``[]``; those are all RECORDED
    facts (a present-but-null field is a malformed record, which the
    store rejects at ``put_run`` — the reader is not a validator and
    returns whatever is recorded rather than papering over it).
    """
    if name not in EVIDENCE_DIMENSIONS:
        raise DimensionsError(f"unknown evidence dimension: {name!r}")
    return record.get(name, UNKNOWN)


def read_dimensions(record: Mapping) -> dict[str, Any]:
    """All five dimensions of a stored record, absent ones as UNKNOWN."""
    return {name: dimension_value(record, name) for name in EVIDENCE_DIMENSIONS}
