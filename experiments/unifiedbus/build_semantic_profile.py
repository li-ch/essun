#!/usr/bin/env python3
"""Build ``experiments/unifiedbus/semantic_profile.yaml`` (ladder S5, 2026-10-29).

Migrate the UnifiedBus PAPER-DERIVED design profile INTO the versioned D2
profile format (``essun-profile`` v0.1: ``schemas/profile.schema.json`` +
loader :mod:`essun.specir.profile_format`, ladder S3).  The artifact is the
ten-element first-class profile of design doc D2 — the same shape as the UEC
migration of ladder S4 (``experiments/uec/build_semantic_profile.py``), with
ONE categorical difference the artifact states about itself: this profile is
PAPER-DERIVED, NOT NORMATIVE.  UnifiedBus is not an ingested standard; the
specification track stays license-gated (``experiments/unifiedbus/source_record.yaml``
carries the verbatim license-gate rows, including the never-fetched
APPROVAL_REQUIRED row), so element 1 cites the five PUBLIC_READ papers/pages
of the paper-anchor registry, and every requirement keeps its evidence grade
(PAPER_REPORTED / VENDOR_CLAIMED / OFFICIAL_PUBLIC_PAGE) — a vendor number
can never enter the artifact laundered as a neutral fact.

Division of content (the honesty contract of this migration):

- DERIVED, never hand-edited: ``requirements`` (all 54 design parameters of
  :mod:`essun.specir.unifiedbus_paper_profile`, with their S5 dispositions —
  the builder READS the dispositions from the live registry, it cannot
  assign or change them: this is a migration, not a re-adjudication),
  ``freedom`` (all 8 free parameters, candidates preserved), and the
  ``source``/``provenance`` identity fields, read live from the paper-anchor
  registry (``experiments/unifiedbus/anchor_registry.yaml``) plus the
  verbatim repo license-gate record.  The source ``revision`` is COMPUTED:
  a sha256 over the sorted (source_id, doc_sha256) pairs of the five
  pinned sources, so any change to any source document changes the
  revision — a multi-source paper set has no version number to cite, and
  inventing one is forbidden (free-parameter rule applied to identity).
  ``bindings`` is DERIVED-EMPTY: no reviewed binding exists for UnifiedBus
  (``UB_BINDINGS`` below), so the artifact says "executed by no backend"
  by carrying an empty bindings list, never by omitting the element.
- CURATED, reviewed editorial content: ``checks`` (the one real invariant
  that exists today), ``omissions``, ``versioning``, and the notes — stated
  in this script so every sentence in the artifact has a source under
  review.

The builder refuses to write an invalid artifact: it validates the built
document with the S3 loader, verifies every cited anchor id against the
live paper-anchor registry, and enforces the license gate structurally
(every registry source must be PUBLIC_READ).  Conformance is then pinned by
``tests/specir/test_unifiedbus_semantic_profile.py``, which also re-runs
this builder and requires byte-identical output (no silent hand-edits).

Re-run after any change to the paper-profile module, the paper-anchor
registry, or the source record::

    .venv/bin/python experiments/unifiedbus/build_semantic_profile.py

Usage::

    .venv/bin/python experiments/unifiedbus/build_semantic_profile.py [--output PATH]
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml

from essun.specir.profile_format import (
    PROFILE_FORMAT_NAME,
    PROFILE_FORMAT_VERSION,
    check_anchor_refs,
    profile_from_dict,
    profile_problems,
)
from essun.specir.unifiedbus_paper_profile import (
    free_parameters,
    requirements,
)
from essun.specir.unifiedbus_sources import PaperAnchorRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RECORD_PATH = REPO_ROOT / "experiments/unifiedbus/source_record.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/unifiedbus/anchor_registry.yaml"
PROFILE_PATH = REPO_ROOT / "experiments/unifiedbus/semantic_profile.yaml"

#: Stable identity of this profile artifact (named-profile comparisons, D4).
PROFILE_ID = "unifiedbus-paper-derived"

#: The artifact's own version.  0.1.0 is the first release of the profile
#: in the essun-profile format (ladder S5); the source set's changing state
#: is carried by the computed ``source.revision``, not by this version.
PROFILE_VERSION = "0.1.0"

#: Backend capability bindings for UnifiedBus: NONE.  A binding is a
#: reviewed act registered in essun.specir.bindings; none exists for the
#: paper-derived family, so every requirement stays informational /
#: unsupported and the artifact carries an empty bindings list on purpose
#: (the format's own words: "a profile executed by no backend today says so
#: by having no bindings, never by omitting the element").  Adding one is a
#: conscious, reviewed change to this constant plus the bindings registry.
UB_BINDINGS: tuple = ()

#: The executable checks (element 6) — real, existing tests only.  Every
#: entry names a file that must exist; the conformance test enforces that.
#: With zero bindings there are no golden/negative execution checks; the
#: one real invariant is the drift check pinning the only place the profile
#: is consumed by execution today: the cross-design L0 comparison sweep,
#: whose UB flavor is anchored to UBP-P17 (rack scale), UBP-P06
#: (switch-free adjacency precedent), and UBP-P07 (lane structure -> B =
#: 72 x FREE per-lane rate).
CHECKS: list[dict] = [
    {
        "check_id": "UBP-CHK-01",
        "kind": "invariant",
        "requirement_ids": ["UBP-P06", "UBP-P07", "UBP-P17"],
        "description": (
            "the cross-design L0 comparison's UB flavor is anchored, not "
            "free: ranks=64 must equal UBP-P17's reported rack scale "
            "(tampering with the rank count is flagged naming UBP-P17), "
            "the crossbar identity must be backed by the platform map's "
            "L0_READY rows for UBP-P17/UBP-P06, bandwidth B must enter "
            "only as 72 x per-lane rate with the rate FREE (UBP-F01), and "
            "the flavor files must carry the paper-derived, not-normative "
            "marker plus the UBP-F01/UBP-F02 silence citations — drift is "
            "a hard error, not silent"
        ),
        "location": "tests/specir/test_unifiedbus_l0_flavors.py",
    },
]

#: Known omissions (element 9) — stated visibly, honesty over coverage.
OMISSIONS: list[dict] = [
    {
        "what": (
            "zero backend capability bindings: the profile is executed by "
            "no backend, and its 54 requirements carry no executed "
            "disposition (32 informational / 22 unsupported)"
        ),
        "reason": (
            "a binding is a reviewed act (essun.specir.bindings); none "
            "exists for the paper-derived family. The platform map's "
            "L0_READY rows (essun.specir.unifiedbus_platform_map) are "
            "mappings to landed knobs, NOT bindings: they record which "
            "knobs UB structure facts could feed, and the cross-design "
            "comparison consumes them under shared free parameters — no "
            "requirement's execution is claimed"
        ),
    },
    {
        "what": (
            "the UnifiedBus specification itself (Base Specification 2.x, "
            "Compatibility Test Specification, Spec 2.1 highlights): not "
            "interpreted, not cited as a source"
        ),
        "reason": (
            "the specification track is license-gated "
            "(experiments/unifiedbus/source_record.yaml row STD-UB-LICENSE, "
            "APPROVAL_REQUIRED, never fetched); this profile is built ONLY "
            "from the five PUBLIC_READ papers/pages of the paper-anchor "
            "registry. The gated Base Specification is referenced by title "
            "only, through one public page (UBP-P51)"
        ),
    },
    {
        "what": (
            "22 of 54 requirements carry disposition unsupported: reported "
            "outcome measures (MTBF, availability, RTT claims, linearity), "
            "memory-semantic behaviors, host software components"
        ),
        "reason": (
            "honesty over coverage: per-disposition counts are computed "
            "live (tools/disposition_coverage.py) and frozen in "
            "tests/specir/test_unifiedbus_paper_profile.py; a promotion is "
            "a reviewed act with a registered binding"
        ),
    },
    {
        "what": (
            "no numeric bandwidth or latency value is derived from the "
            "profile: per-lane rate and per-component latency are explicit "
            "free parameters (UBP-F01 / UBP-F02), so any run consumes them "
            "as recorded free assumptions"
        ),
        "reason": (
            "no public source states a per-lane rate or a latency "
            "breakdown; inventing one is forbidden (free-parameter rule). "
            "The anchored candidates (224/256 Gbit/s highlight, 1.6 "
            "Tbit/s per LinkDevice port, 7->2 microsecond RTT) keep their "
            "own evidence grades and are never promoted to values"
        ),
    },
    {
        "what": (
            "no golden or negative execution checks: the profile has no "
            "executable value semantics to pin"
        ),
        "reason": (
            "checks exercise requirements through bindings; with zero "
            "bindings the only executable check is the anchoring invariant "
            "UBP-CHK-01. Golden checks arrive only with the first reviewed "
            "binding"
        ),
    },
]

#: Versioning rules (element 10) — which changes bump which component.
BUMP_RULES: dict[str, list[str]] = {
    "major": [
        "dispositions",  # what the profile claims to execute changed
        "bindings",  # which backend executes which requirement changed
        "anchor_ids",  # a changed citation is a new version, never an edit
        "sources",  # the source set or any doc_sha256 changed (revision)
    ],
    "minor": ["requirements", "freedom", "checks", "supported"],
    "patch": ["notes"],
}

#: The non-normative marker, stated in the artifact itself (element 1).
NON_NORMATIVE_NOTE = (
    "PAPER-DERIVED, NOT NORMATIVE: this is a design profile of the "
    "UnifiedBus-class architecture AS REPORTED by five public papers and "
    "public pages — not a UnifiedBus standard profile. The specification "
    "track stays license-gated and was never fetched. Every requirement "
    "carries its evidence grade; a vendor-claimed number is never "
    "laundered as a neutral fact, and paper-derived values keep their "
    "paper anchors while everything the sources do not state stays an "
    "explicit free parameter"
)

HEADER = f"""\
# UnifiedBus paper-derived profile — {PROFILE_FORMAT_NAME} v{PROFILE_FORMAT_VERSION} artifact.
# GENERATED FILE (ladder S5 of the dispositions/profile work, 2026-10-29);
# regenerate with:
#   .venv/bin/python experiments/unifiedbus/build_semantic_profile.py
# PAPER-DERIVED, NOT NORMATIVE (stated here and in the artifact): UnifiedBus
# is not an ingested standard — the spec track is license-gated and never
# fetched; the profile interprets five PUBLIC_READ papers/pages only.
# Dispositions are READ from the live specir registry (the S5 record);
# this migration does not assign or change any disposition.  Anchor
# citations are unchanged from the paper-profile module and resolve against
# experiments/unifiedbus/anchor_registry.yaml.  Conformance gate:
# tests/specir/test_unifiedbus_semantic_profile.py (loads, disposition
# parity with the live registry, zero-binding honesty, corruption
# rejection, byte-identical regeneration).
"""


def _load_registry() -> PaperAnchorRegistry:
    registry = PaperAnchorRegistry.load(REGISTRY_PATH)
    registry.assert_valid()  # sha256 + quote re-match, PUBLIC_READ gate
    return registry


def _load_source_record() -> dict:
    raw = yaml.safe_load(SOURCE_RECORD_PATH.read_text(encoding="utf-8"))
    rows = raw.get("sources") if isinstance(raw, dict) else None
    if not rows:
        raise SystemExit(
            f"source record {SOURCE_RECORD_PATH} is missing its verbatim "
            "license-gate rows; the profile's provenance cites them"
        )
    return raw


def _source_set_revision(registry: PaperAnchorRegistry) -> str:
    """Content digest of the pinned source set (the set's revision).

    A multi-source paper set has no version number to cite; inventing one
    is forbidden.  Instead the revision is COMPUTED over the sorted
    (source_id, doc_sha256) pairs: any change to any source document
    changes it, and the builder recomputes it from the live registry so it
    cannot drift.
    """
    lines = sorted(
        f"{source_id} {entry['doc_sha256']}"
        for source_id, entry in registry.sources.items()
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def build_document(registry: PaperAnchorRegistry) -> dict:
    """Build the ten-element artifact from the live registries."""
    record = _load_source_record()

    # License gate, enforced structurally: every cited source is PUBLIC_READ
    # (the registry's own verify() already rejects gated sources; restate it
    # so the builder fails loudly and locally if that ever changes).
    not_public = sorted(
        sid
        for sid, entry in registry.sources.items()
        if entry.get("access") != "PUBLIC_READ"
    )
    if not_public:
        raise SystemExit(
            f"registry sources {not_public} are not PUBLIC_READ; a "
            "paper-derived profile may cite public papers/pages only"
        )

    requirements_list: list[dict] = []
    for param in requirements():  # the 54 design parameters (S5 record)
        requirements_list.append(
            {
                "requirement_id": param.parameter_id,
                "anchor_ids": list(param.anchor_ids),
                "statement": param.as_reported,
                "disposition": param.disposition,  # S5 record, read-only
                "name": param.name,
                "category": param.category,
                "value_kind": param.value_kind,
                "unit": param.unit,
                "evidence_grade": param.evidence_grade,
                **({"notes": param.notes} if param.notes else {}),
            }
        )

    freedom: list[dict] = []
    for param in free_parameters():  # the 8 free parameters (no disposition)
        freedom.append(
            {
                "parameter_id": param.parameter_id,
                "name": param.name,
                "freedom": param.gap,  # the silence being marked
                "anchor_ids": list(param.anchor_ids),
                "domain": "FREE",
                "category": param.category,
                **(
                    {
                        "candidates": [
                            {
                                "label": cand.label,
                                "anchor_id": cand.anchor_id,
                                "evidence_grade": cand.evidence_grade,
                            }
                            for cand in param.candidates
                        ]
                    }
                    if param.candidates
                    else {}
                ),
            }
        )

    paper_sources = [
        {
            "source_id": source_id,
            "title": entry["title"],
            "url": entry["url"],
            "access": entry["access"],
            "doc_sha256": entry["doc_sha256"],
        }
        for source_id, entry in sorted(registry.sources.items())
    ]
    grades_in_use = sorted(
        {param.evidence_grade for param in requirements()}
    )

    return {
        "format": {
            "name": PROFILE_FORMAT_NAME,
            "version": PROFILE_FORMAT_VERSION,
        },
        "profile_id": PROFILE_ID,
        # Element 1 — source identity/revision.  Multi-source paper set:
        # identity is the registry family (verbatim), revision is the
        # computed content digest, and the non-normative status is stated
        # here, in the artifact itself.
        "source": {
            "name": (
                "UnifiedBus public papers and public pages (paper-derived "
                "design profile)"
            ),
            "document_id": "unifiedbus_public_papers",  # registry family
            "revision": _source_set_revision(registry),
            "normative": False,
            "note": NON_NORMATIVE_NOTE,
        },
        # Element 2 — provenance and permissions (license-gate vocabulary).
        "provenance": {
            "source_record": "experiments/unifiedbus/source_record.yaml",
            "access": "PUBLIC_READ",  # all five cited sources, verbatim
            "paper_sources": paper_sources,
            "anchor_registry": "experiments/unifiedbus/anchor_registry.yaml",
            "gated_specification_row": "STD-UB-LICENSE (APPROVAL_REQUIRED, "
            "never fetched; the record keeps the verbatim row)",
            "evidence_grades_in_use": grades_in_use,
            "note": (
                "license review precedes ingestion: the repo source record "
                "carries the verbatim license-gate rows, including the "
                "gated specification row, which was never fetched and is "
                "not interpreted here. Raw fetched pages stay under "
                "experiments/unifiedbus/source/ with per-page sha256; "
                "quotes in the anchor registry are citation-bounded and "
                "re-matched at load; requirement statements below are "
                "paraphrases in essun's own words with every number as the "
                "source states it"
            ),
        },
        # Element 3 — interpreted requirements WITH S5 dispositions.
        "requirements": {
            "objects": requirements_list,
            "note": (
                "the requirement objects of this paper-derived family are "
                "its design parameters (UBP-P01..P54); none is executed: "
                "paper-stated structure facts are informational, "
                "everything else is unsupported, and a promotion requires "
                "a reviewed binding (none exists)"
            ),
        },
        # Element 4 — declared implementation freedom.
        "freedom": freedom,
        # Element 5 — backend capability bindings: empty BY CONTENT (no
        # reviewed binding exists), never by omission.
        "bindings": [
            {
                "binding_id": binding.binding_id,
                "requirement_id": binding.requirement_id,
                "backend": binding.backend_id,
                "capability": binding.capability,
                "parameters": {name: "FREE" for name in binding.parameters},
                "note": binding.notes,
            }
            for binding in UB_BINDINGS
        ],
        # Element 6 — executable checks (curated above).
        "checks": CHECKS,
        # Element 7 — supported workloads/observables: the profile's
        # executable surface today is the cross-design L0 comparison sweep
        # (W1 decode on the L0 family; O-CCT moves, O-CONSERVATION is the
        # byte-accounting self-check), whose UB flavor is anchored to
        # UBP-P17/UBP-P06 and runs under SHARED free parameters — see
        # omissions: this is NOT a backend capability binding.
        "supported": {
            "workloads": ["w1_dense_tp_decode"],
            "observables": ["O-CCT", "O-CONSERVATION"],
        },
        # Element 8 — calibration scope (verification != calibration).
        "calibration": {
            "status": "uncalibrated",
            "targets": [],
            "note": (
                "E0 evidence level: identity and determinism only; no "
                "UnifiedBus hardware measurements exist. The reported "
                "figures (RTT 7->2 microseconds, MTBF, availability, "
                "linearity) are vendor/paper OUTCOME claims carried with "
                "their grades, never calibration targets of this artifact; "
                "the free parameters UBP-F01/UBP-F02 gate every numeric B/L"
            ),
        },
        # Element 9 — known omissions (curated above).
        "omissions": OMISSIONS,
        # Element 10 — versioning rules.
        "versioning": {
            "profile_version": PROFILE_VERSION,
            "bump_rules": BUMP_RULES,
            "note": (
                "the profile version tracks this ARTIFACT, not the source "
                "set (source.revision is the computed digest of the five "
                "pinned documents and changes with any of them); anchor "
                "citations are immutable — a changed citation is a new "
                "version, never a silent edit"
            ),
        },
    }


def validate_document(document: dict, registry: PaperAnchorRegistry) -> list[str]:
    """Every gate the builder itself enforces before writing; [] = valid.

    Format (S3 loader) plus anchor citations against the live paper-anchor
    registry.  With zero bindings there is no backend CAPABILITIES check to
    run — that check arrives with the first reviewed binding.
    """
    problems = list(profile_problems(document))
    if problems:
        return problems
    profile = profile_from_dict(document, source="<built document>")
    problems.extend(
        check_anchor_refs(profile, {a.anchor_id for a in registry.anchors})
    )
    # Grades ride along unchanged: the artifact's per-requirement grade must
    # match the live object (no laundering in the artifact either).
    live_grades = {
        param.parameter_id: param.evidence_grade for param in requirements()
    }
    for req in profile.requirements:
        grade = req.extra.get("evidence_grade")
        if grade != live_grades[req.requirement_id]:
            problems.append(
                f"requirements: {req.requirement_id}: evidence grade "
                f"{grade!r} != live {live_grades[req.requirement_id]!r}"
            )
    return problems


def render(document: dict) -> str:
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        width=96,
        allow_unicode=True,
    )
    return HEADER + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=PROFILE_PATH,
        help=f"where to write the artifact (default: {PROFILE_PATH})",
    )
    args = parser.parse_args(argv)

    registry = _load_registry()
    document = build_document(registry)
    problems = validate_document(document, registry)
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise SystemExit(
            f"refusing to write an invalid profile artifact: {detail}{more}"
        )

    profile = profile_from_dict(document, source="<built document>")
    counts = profile.disposition_counts()
    executed = sum(counts[d] for d in ("constraint", "simulated_behavior", "conformance_test"))
    args.output.write_text(render(document), encoding="utf-8")
    print(f"wrote {args.output}")
    print(
        "review record: "
        f"{len(profile.requirements)} requirements "
        f"({counts['informational']} informational / "
        f"{counts['unsupported']} unsupported / "
        f"{counts['simulated_behavior']} simulated_behavior; "
        f"constraint {counts['constraint']}, conformance_test "
        f"{counts['conformance_test']}, not_applicable "
        f"{counts['not_applicable']}; {executed} executed), "
        f"{len(profile.freedom)} free parameters, "
        f"{len(profile.bindings)} binding(s), {len(profile.checks)} check(s)"
    )
    print(
        "paper-derived, not normative; dispositions are read from the live "
        "registry (S5 record) and this builder cannot assign or change them"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
