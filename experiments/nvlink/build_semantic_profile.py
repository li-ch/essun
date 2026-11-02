#!/usr/bin/env python3
"""Build ``experiments/nvlink/semantic_profile.yaml`` (M1, 2026-11-02).

Migrate the NVLink-class PAPER-DERIVED design profile INTO the versioned D2
profile format (``essun-profile`` v0.1: ``schemas/profile.schema.json`` +
loader :mod:`essun.specir.profile_format`) — the same shape as the
UnifiedBus migration (``experiments/unifiedbus/build_semantic_profile.py``),
with the same categorical difference the artifact states about itself: this
profile is PAPER-DERIVED, NOT NORMATIVE.  No public NVLink/NVSwitch
specification document exists (the specification track is licensee/NDA-gated;
``experiments/nvlink/source_record.yaml`` carries the verbatim gate row
STD-NV-SPEC, never fetched), so element 1 cites the five PUBLIC_READ
papers/pages of the M1 paper-anchor registry, and every requirement keeps
its evidence grade (PAPER_REPORTED / VENDOR_CLAIMED / OFFICIAL_PUBLIC_PAGE)
— a vendor number can never enter the artifact laundered as a neutral fact.

Division of content (the honesty contract, mirroring the UnifiedBus
migration):

- DERIVED, never hand-edited: ``requirements`` (all 24 design parameters of
  :mod:`essun.specir.nvlink_paper_profile`, with their dispositions — the
  builder READS them from the live registry, it cannot assign or change
  them), ``freedom`` (all 6 free parameters, candidates preserved), and the
  ``source``/``provenance`` identity fields, read live from the paper-anchor
  registry plus the verbatim repo license-gate record.  The source
  ``revision`` is COMPUTED: a sha256 over the sorted (source_id, doc_sha256)
  pairs of the five pinned sources.
- CURATED, reviewed editorial content: ``checks``, ``omissions``,
  ``versioning``, and the notes — stated in this script so every sentence
  in the artifact has a source under review.

The builder refuses to write an invalid artifact: it validates the built
document with the S3 loader, verifies every cited anchor id against the
live paper-anchor registry, and enforces the license gate structurally
(every registry source must be PUBLIC_READ).  Conformance is then pinned by
``tests/specir/test_nvlink_semantic_profile.py``, which also re-runs this
builder and requires byte-identical output (no silent hand-edits).

Re-run after any change to the paper-profile module, the paper-anchor
registry, or the source record::

    .venv/bin/python experiments/nvlink/build_semantic_profile.py
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
from essun.specir.nvlink_paper_profile import (
    free_parameters,
    load_registry,
    requirements,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RECORD_PATH = REPO_ROOT / "experiments/nvlink/source_record.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/nvlink/anchor_registry.yaml"
PROFILE_PATH = REPO_ROOT / "experiments/nvlink/semantic_profile.yaml"

#: Stable identity of this profile artifact (named-profile comparisons).
PROFILE_ID = "nvlink-class-paper-derived"

#: The artifact's own version.  0.1.0 is the first release of the profile
#: in the essun-profile format (M1); the source set's changing state is
#: carried by the computed ``source.revision``, not by this version.
PROFILE_VERSION = "0.1.0"

#: Backend capability bindings for the NVLink-class family: NONE.  A
#: binding is a reviewed act registered in essun.specir.bindings; none
#: exists for this paper-derived family, so every requirement stays
#: informational / unsupported and the artifact carries an empty bindings
#: list on purpose.  Adding one is a conscious, reviewed change to this
#: constant plus the bindings registry.
NV_BINDINGS: tuple = ()

#: The executable checks (element 6) — real, existing tests only.  The one
#: real invariant is the drift check pinning the only place the profile is
#: consumed by execution today: the three-architecture cross-fabric
#: comparison, whose NVLink-paper flavor is anchored to NVP-P01 (the
#: paper-reported NVSwitch non-blocking crossbar) and NVP-P13 (the 72-GPU
#: domain scale), running under shared free parameters with the rank-scale
#: asymmetry stated.
CHECKS: list[dict] = [
    {
        "check_id": "NVP-CHK-01",
        "kind": "invariant",
        "requirement_ids": ["NVP-P01", "NVP-P13", "NVP-P14"],
        "description": (
            "the three-architecture comparison's NVLink-paper flavor is "
            "anchored, not free: its crossbar identity must be backed by "
            "the platform map's L0_READY rows for NVP-P01/NVP-P13, the "
            "flavor file must carry the paper-derived, not-normative "
            "marker plus the NVP-F01/NVP-F02/NVP-F03 silence citations "
            "and the matched-free rank statement (the anchored domain "
            "scale is 72, NVP-P13; the comparison workload pins tp=64), "
            "and bandwidth B must enter only with the rate FREE (NVP-F01) "
            "— drift is a hard error, not silent"
        ),
        "location": "tests/specir/test_unifiedbus_l0_flavors.py",
    },
]

#: Known omissions (element 9) — stated visibly, honesty over coverage.
OMISSIONS: list[dict] = [
    {
        "what": (
            "zero backend capability bindings: the profile is executed by "
            "no backend, and its 24 requirements carry no executed "
            "disposition (19 informational / 5 unsupported)"
        ),
        "reason": (
            "a binding is a reviewed act (essun.specir.bindings); none "
            "exists for the paper-derived family. The platform map's "
            "L0_READY rows (essun.specir.nvlink_platform_map) are mappings "
            "to landed knobs, NOT bindings: they record which knobs "
            "NVLink-class structure facts could feed, and the "
            "three-architecture comparison consumes them under shared "
            "free parameters — no requirement's execution is claimed"
        ),
    },
    {
        "what": (
            "any NVLink/NVSwitch specification: not interpreted, not "
            "cited as a source — no public specification document exists"
        ),
        "reason": (
            "the specification track is licensee/NDA-gated "
            "(experiments/nvlink/source_record.yaml row STD-NV-SPEC, "
            "APPROVAL_REQUIRED, never fetched); this profile is built "
            "ONLY from the five PUBLIC_READ papers/pages of the "
            "paper-anchor registry"
        ),
    },
    {
        "what": (
            "5 of 24 requirements carry disposition unsupported: measured "
            "outcome figures (V100-era P2P latency, derating, "
            "twisted-torus gains) and the observed NUMA-effect classes"
        ),
        "reason": (
            "honesty over coverage: per-disposition counts are computed "
            "live (tools/disposition_coverage.py) and frozen in "
            "tests/specir/test_nvlink_paper_profile.py; a promotion is a "
            "reviewed act with a registered binding"
        ),
    },
    {
        "what": (
            "no numeric bandwidth or latency value is derived from the "
            "profile: per-link rate and per-hop latency are explicit free "
            "parameters (NVP-F01 / NVP-F02), so any run consumes them as "
            "recorded free assumptions"
        ),
        "reason": (
            "no public source states a per-link NVLink5 rate or a "
            "current-gen latency breakdown; inventing one is forbidden "
            "(free-parameter rule). The anchored candidates (1.8 TB/s per "
            "GPU, 130 TB/s aggregate, 50 GB/s per link at V100 era, ~9 "
            "microsecond V100 P2P) keep their own evidence grades and are "
            "never promoted to values"
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
            "NVP-CHK-01. Golden checks arrive only with the first reviewed "
            "binding"
        ),
    },
    {
        "what": (
            "the measured GB200 NVL72 NCCL series (calibration anchor "
            "CAL-A3) is not a source of this profile"
        ),
        "reason": (
            "the operator's support article is Cloudflare-gated against "
            "deterministic fetching, and measured calibration anchors "
            "belong to the calibration track (docs/calibration/), whose "
            "split discipline governs them; re-anchoring them here would "
            "duplicate that governance, not strengthen it"
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
    "NVLink-class scale-up family (the fabrics NVLink/NVSwitch exemplify, "
    "plus the class member TPU v4 ICI) AS REPORTED by five public papers "
    "and public pages — not an NVLink/NVSwitch standard profile. No public "
    "specification document exists; the specification track stays "
    "licensee-gated and was never fetched. Every requirement carries its "
    "evidence grade; a vendor-claimed number is never laundered as a "
    "neutral fact, and paper-derived values keep their paper anchors "
    "while everything the sources do not state stays an explicit free "
    "parameter"
)

HEADER = f"""\
# NVLink-class paper-derived profile — {PROFILE_FORMAT_NAME} v{PROFILE_FORMAT_VERSION} artifact.
# GENERATED FILE (M1, 2026-11-02); regenerate with:
#   .venv/bin/python experiments/nvlink/build_semantic_profile.py
# PAPER-DERIVED, NOT NORMATIVE (stated here and in the artifact): no public
# NVLink/NVSwitch specification exists — the specification track is
# licensee/NDA-gated and never fetched; the profile interprets five
# PUBLIC_READ papers/pages only. Dispositions are READ from the live specir
# registry (the M1 record); this migration does not assign or change any
# disposition. Anchor citations are unchanged from the paper-profile module
# and resolve against experiments/nvlink/anchor_registry.yaml. Conformance
# gate: tests/specir/test_nvlink_semantic_profile.py (loads, disposition
# parity with the live registry, zero-binding honesty, corruption
# rejection, byte-identical regeneration).
"""


def _load_registry():
    registry = load_registry(REGISTRY_PATH)
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


def _source_set_revision(registry) -> str:
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


def build_document(registry) -> dict:
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
    for param in requirements():  # the 24 design parameters (M1 record)
        requirements_list.append(
            {
                "requirement_id": param.parameter_id,
                "anchor_ids": list(param.anchor_ids),
                "statement": param.as_reported,
                "disposition": param.disposition,  # M1 record, read-only
                "name": param.name,
                "category": param.category,
                "value_kind": param.value_kind,
                "unit": param.unit,
                "evidence_grade": param.evidence_grade,
                **({"notes": param.notes} if param.notes else {}),
            }
        )

    freedom: list[dict] = []
    for param in free_parameters():  # the 6 free parameters (no disposition)
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
                "NVLink-class public papers and public pages (paper-derived "
                "design profile)"
            ),
            "document_id": "nvlink_class_public_papers",  # registry family
            "revision": _source_set_revision(registry),
            "normative": False,
            "note": NON_NORMATIVE_NOTE,
        },
        # Element 2 — provenance and permissions (license-gate vocabulary).
        "provenance": {
            "source_record": "experiments/nvlink/source_record.yaml",
            "access": "PUBLIC_READ",  # all five cited sources, verbatim
            "paper_sources": paper_sources,
            "anchor_registry": "experiments/nvlink/anchor_registry.yaml",
            "gated_specification_row": "STD-NV-SPEC (APPROVAL_REQUIRED, "
            "never fetched; no public NVLink/NVSwitch specification exists "
            "— the record keeps the verbatim row)",
            "evidence_grades_in_use": grades_in_use,
            "note": (
                "license review precedes ingestion: the repo source record "
                "carries the verbatim license-gate rows, including the "
                "gated specification row, which was never fetched and is "
                "not interpreted here. Raw fetched pages stay under "
                "experiments/nvlink/source/ with per-page sha256; quotes "
                "in the anchor registry are citation-bounded and "
                "re-matched at load; requirement statements below are "
                "paraphrases in essun's own words with every number as the "
                "source states it"
            ),
        },
        # Element 3 — interpreted requirements WITH dispositions.
        "requirements": {
            "objects": requirements_list,
            "note": (
                "the requirement objects of this paper-derived family are "
                "its design parameters (NVP-P01..P24); none is executed: "
                "paper-stated structure facts are informational, "
                "everything else is unsupported, and a promotion requires "
                "a reviewed binding (none exists)"
            ),
        },
        # Element 4 — declared implementation freedom.
        "freedom": freedom,
        # Element 5 — backend capability bindings: empty BY CONTENT (no
        # reviewed binding exists), never by omission.
        "bindings": [],
        # Element 6 — executable checks (curated above).
        "checks": CHECKS,
        # Element 7 — supported workloads/observables: the profile's
        # executable surface today is the three-architecture cross-fabric
        # comparison sweep (W1 decode on the L0 family), whose NV flavor
        # is anchored to NVP-P01/NVP-P13 and runs under SHARED free
        # parameters — see omissions: this is NOT a backend capability
        # binding.
        "supported": {
            "workloads": ["w1_dense_tp_decode"],
            "observables": ["O-CCT", "O-CONSERVATION"],
        },
        # Element 8 — calibration scope (verification != calibration).
        "calibration": {
            "status": "uncalibrated",
            "targets": [],
            "note": (
                "E0 evidence level: identity and determinism only; this "
                "artifact calibrates nothing. The reported figures (57.6 "
                "Tbps, 1.8 TB/s, 130 TB/s, ~9 microsecond V100 P2P, ~80% "
                "derating) are vendor/paper claims carried with their "
                "grades, never calibration targets of this artifact; the "
                "measured GB200 series and the derating guidance live in "
                "the calibration track (docs/calibration/, anchors "
                "CAL-A1/A2/A3/A12) under its own split discipline — the "
                "free parameters NVP-F01/NVP-F02 gate every numeric B/L"
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


def validate_document(document: dict, registry) -> list[str]:
    """Every gate the builder itself enforces before writing; [] = valid."""
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
        "registry (M1 record) and this builder cannot assign or change them"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
