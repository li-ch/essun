#!/usr/bin/env python3
"""Build ``experiments/ualink/semantic_profile.yaml`` — the UALink ACTIVATION
SKELETON (M5, 2026-11-02).

This is NOT a UALink profile.  It is the wired, empty slot a profile lands
into the moment the pending license question (HUM-02: may an independent
open-source project derive and distribute a machine-readable UALink
profile?) gets an answer that permits ingestion.  Everything that can be
built before that answer is built here:

- the ten-element ``essun-profile`` v0.1 artifact, structurally complete
  and valid TODAY, with ZERO interpreted requirements (a visible absence,
  stated in ``requirements.note`` — the honest shape of a skeleton);
- the free-parameter skeleton: the eight degrees of freedom any UALink
  profile of this family will carry, each anchored to the MEMBER-PUBLIC
  EXCERPT registry so the silence (or the excerpt-stated candidate) is on
  the record before the specification is ever read;
- provenance that cites the verbatim license-gate source record, including
  the APPROVAL_REQUIRED row (STD-UALINK-COMMON20) that was never fetched.

Division of content (mirrors the UnifiedBus S5 builder's honesty contract):

- DERIVED, never hand-edited: ``provenance.paper_sources`` (read live from
  ``experiments/ualink/anchor_registry.yaml``), the computed
  ``source.revision`` (a sha256 over the sorted (source_id, doc_sha256)
  pairs of the pinned excerpt set — a multi-source set has no version
  number to cite and inventing one is forbidden), and ``freedom`` (the
  structural slots defined below, whose anchor citations are verified
  against the live registry).
- CURATED, reviewed editorial content: the skeleton identity, the
  requirements absence note, ``omissions``, ``versioning``, and the notes.
- EMPTY BY CONTENT, never by omission: ``requirements`` (no authorized
  source exists to interpret), ``bindings`` (nothing to bind), ``checks``
  (nothing to exercise — the license-fence invariants live as tests, see
  ``tests/specir/test_ualink_activation_skeleton.py``).

The builder enforces its own fences before writing:

1. the license gate: the excerpt registry loads through
   :class:`~essun.specir.unifiedbus_sources.PaperAnchorRegistry` and
   re-verifies (per-page sha256, quote re-match, PUBLIC_READ-only sources);
2. the gated track is absent: no source-record row with access other than
   PUBLIC_READ appears among the fetched sources, by id AND by url;
3. the skeleton stays a skeleton: zero requirement objects, zero bindings,
   zero checks — if any of those is non-empty this builder is the wrong
   tool (activation replaces it; see ``experiments/ualink/ACTIVATION.md``).

Re-run after any change to the excerpt registry or the source record::

    .venv/bin/python experiments/ualink/build_semantic_profile.py

Usage::

    .venv/bin/python experiments/ualink/build_semantic_profile.py [--output PATH]
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
from essun.specir.unifiedbus_sources import PaperAnchorRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RECORD_PATH = REPO_ROOT / "experiments/ualink/source_record.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/ualink/anchor_registry.yaml"
PROFILE_PATH = REPO_ROOT / "experiments/ualink/semantic_profile.yaml"

#: Stable identity of this artifact.  The name says what it is: an
#: activation SKELETON, not a profile — comparisons and matrix tools must
#: never mistake it for one (it interprets nothing).
PROFILE_ID = "ualink-activation-skeleton"

#: The artifact's own version.  0.1.0 is the skeleton; the first release
#: that interprets authorized specification text is 1.0.0 (a major bump:
#: dispositions, bindings, anchor_ids, and sources all change).
PROFILE_VERSION = "0.1.0"

#: The single evidence grade this skeleton knows.  Activation adds
#: AUTHORIZED_SPEC alongside it (never replacing the excerpt grade —
#: excerpt-derived facts keep their lower grade by construction).
EVIDENCE_GRADE = "MEMBER_PUBLIC_EXCERPT"

#: The pending license decision this skeleton exists behind.
HUM_STATUS = (
    "HUM-02 (UALink license question) PENDING: no answer received; the "
    "specification family (STD-UALINK-COMMON20 and the DL/PL, Manageability, "
    "Chiplet documents it indexes) was never fetched and is not interpreted "
    "here. When an answer permits ingestion, activation follows "
    "experiments/ualink/ACTIVATION.md."
)

#: Requirements interpreted from authorized UALink specification text.
#: ZERO today — there is no authorized source.  Activation replaces this
#: builder step with live requirement modules (the UEC/UnifiedBus pattern);
#: as long as this constant is empty the artifact honestly states that it
#: interprets nothing.
INTERPRETED_REQUIREMENTS: tuple = ()

#: The requirements element's visible-absence note (the format requires it
#: when objects is empty — an empty interpreted set must never masquerade
#: as an empty table of interpreted facts).
REQUIREMENTS_NOTE = (
    "no UALink requirement is interpreted: the specification documents are "
    "member-gated (HUM-02 pending; STD-UALINK-COMMON20 APPROVAL_REQUIRED, "
    "never fetched), and the member-public excerpts this skeleton anchors "
    "are architecture-level documents the license-gate registry itself "
    "marks 'not full specification'. This element is the wired slot "
    "authorized text lands in at activation (experiments/ualink/ACTIVATION.md); "
    "it is empty by content, never by omission"
)

#: The structural free-parameter skeleton: the eight degrees of freedom any
#: UALink profile of this family will carry, anchored TODAY to what the
#: member-public excerpts state or fail to state.  Anchored candidates keep
#: the excerpt grade and are never promoted — a promotion requires an
#: authorized-spec anchor that does not exist yet.
FREEDOM: list[dict] = [
    {
        "parameter_id": "UAL-F01",
        "name": "credit_flow_control_law",
        "freedom": (
            "credit-based flow control is NAMED by both member-public "
            "excerpts (a Figure-2 goal bullet; 'the TL manages the credits') "
            "but no public text states the credit unit, window size, or "
            "return-path law — the exact admission mechanics a simulation "
            "of UALink flow control needs"
        ),
        "anchor_ids": [
            "UAL-WP10-2-GOALS-FLOWCTRL",
            "UAL-OV-2-TL-CREDITS",
        ],
        "domain": "FREE",
        "category": "flow_control",
    },
    {
        "parameter_id": "UAL-F02",
        "name": "latency_component_breakdown",
        "freedom": (
            "the only public latency statement is a design GOAL (req-to-resp "
            "RTT < 1 microsecond); no per-hop, per-switch, serialization, or "
            "propagation component is reported anywhere public"
        ),
        "anchor_ids": ["UAL-WP10-2-GOALS-RTT"],
        "domain": "FREE",
        "category": "latency",
        "candidates": [
            {
                "label": (
                    "Req-To-Resp RTT < 1 microsecond — a Figure-2 design "
                    "goal, not a measured or component latency"
                ),
                "anchor_id": "UAL-WP10-2-GOALS-RTT",
                "evidence_grade": EVIDENCE_GRADE,
            },
        ],
    },
    {
        "parameter_id": "UAL-F03",
        "name": "per_lane_rate_scope",
        "freedom": (
            "the whitepaper states 200 GT/s maximum data rate per lane and "
            "212.5 GT/s signaling (FEC/layer-1 overhead); the figures are "
            "excerpt-stated architecture facts, not spec-anchored values — "
            "their scope (which links, which speeds mandatory vs optional, "
            "the 106.25G lower option's role) is not fixed by any public "
            "normative text"
        ),
        "anchor_ids": [
            "UAL-WP10-2-LANE-DATA-RATE",
            "UAL-WP10-2-SIGNALING-RATE",
        ],
        "domain": "FREE",
        "category": "link_scale",
        "candidates": [
            {
                "label": "maximum data rate 200 GT/s per lane (whitepaper)",
                "anchor_id": "UAL-WP10-2-LANE-DATA-RATE",
                "evidence_grade": EVIDENCE_GRADE,
            },
            {
                "label": "signaling rate 212.5 GT/s incl. FEC overhead",
                "anchor_id": "UAL-WP10-2-SIGNALING-RATE",
                "evidence_grade": EVIDENCE_GRADE,
            },
        ],
    },
    {
        "parameter_id": "UAL-F04",
        "name": "flit_and_payload_sizes",
        "freedom": (
            "the excerpts state concrete sizes (64-byte TL flits packed into "
            "640-byte DL flits with a 32-bit CRC; compressed request header "
            "8 bytes, write response and flow control 4 bytes each; "
            "software-coherency transactions 64-256 bytes) — excerpt figures, "
            "kept as graded candidates; full format fields, packing rules, "
            "and the max-payload law are not public"
        ),
        "anchor_ids": [
            "UAL-WP10-6-DL-FLITS",
            "UAL-WP10-8-HEADER-SIZES",
            "UAL-OV-1-COHERENCY-SW",
        ],
        "domain": "FREE",
        "category": "flit_format",
        "candidates": [
            {
                "label": "64B TL flit -> 640B DL flit, 32-bit CRC",
                "anchor_id": "UAL-WP10-6-DL-FLITS",
                "evidence_grade": EVIDENCE_GRADE,
            },
            {
                "label": (
                    "compressed header 8B; write response and flow control "
                    "4B each"
                ),
                "anchor_id": "UAL-WP10-8-HEADER-SIZES",
                "evidence_grade": EVIDENCE_GRADE,
            },
            {
                "label": "coherency transactions 64-256 bytes (software)",
                "anchor_id": "UAL-OV-1-COHERENCY-SW",
                "evidence_grade": EVIDENCE_GRADE,
            },
        ],
    },
    {
        "parameter_id": "UAL-F05",
        "name": "memory_consistency_model",
        "freedom": (
            "ordering appears only at overview grade (ordered request "
            "addresses, unordered completions; a host CPU may not access "
            "remote-node memory); no public text defines the consistency "
            "model, the atomic-operation set, or fence semantics"
        ),
        "anchor_ids": [
            "UAL-OV-1-ORDERING",
            "UAL-OV-1-HOST-FENCE",
            "UAL-WP10-1-MEMSEMANTICS",
        ],
        "domain": "FREE",
        "category": "memory_semantics",
    },
    {
        "parameter_id": "UAL-F06",
        "name": "pod_scale_and_addressing",
        "freedom": (
            "1024 endpoints is stated by both excerpts (with 4096 named as a "
            "potential future extension, 10-bit routing identifiers, and a "
            "vendor-defined 57-bit physical address space); the excerpts do "
            "not fix the binding of these numbers as normative limits — "
            "kept as graded candidates until authorized text anchors them"
        ),
        "anchor_ids": [
            "UAL-WP10-3-ULS-1024",
            "UAL-OV-1-ROUTING-1024",
            "UAL-WP10-3-ROUTING-ID",
            "UAL-OV-1-ADDR-57BIT",
        ],
        "domain": "FREE",
        "category": "scale",
        "candidates": [
            {
                "label": "up to 1024 endpoints per pod (both excerpts)",
                "anchor_id": "UAL-WP10-3-ULS-1024",
                "evidence_grade": EVIDENCE_GRADE,
            },
            {
                "label": "4096 endpoints — 'future releases potentially'",
                "anchor_id": "UAL-OV-1-ROUTING-1024",
                "evidence_grade": EVIDENCE_GRADE,
            },
            {
                "label": "unique 10-bit routing identifier per accelerator",
                "anchor_id": "UAL-WP10-3-ROUTING-ID",
                "evidence_grade": EVIDENCE_GRADE,
            },
        ],
    },
    {
        "parameter_id": "UAL-F07",
        "name": "switch_and_topology_structure",
        "freedom": (
            "multi-node, multi-plane switching and a UALink Switch (ULS) "
            "class are named; no public text states switch radix, staging "
            "levels, plane wiring, or scheduling — the structure a topology "
            "model would need"
        ),
        "anchor_ids": [
            "UAL-WP10-3-ULS-1024",
            "UAL-WP10-1-DESIGN-GOALS",
        ],
        "domain": "FREE",
        "category": "topology",
    },
    {
        "parameter_id": "UAL-F08",
        "name": "virtual_channels_and_llr_detail",
        "freedom": (
            "virtual channels are a named goal with no public count or "
            "semantics; link-layer retransmission (LLR) is named with its "
            "replay basis (640-byte flit) but no public retry law (timeouts, "
            "retry counts, error classification)"
        ),
        "anchor_ids": [
            "UAL-WP10-2-GOALS-VCS",
            "UAL-WP10-6-LLR-REPLAY",
        ],
        "domain": "FREE",
        "category": "reliability",
        "candidates": [
            {
                "label": "link-level replay on a 640-byte flit basis",
                "anchor_id": "UAL-WP10-6-LLR-REPLAY",
                "evidence_grade": EVIDENCE_GRADE,
            },
        ],
    },
]

#: Known omissions (element 9) — stated visibly, honesty over coverage.
OMISSIONS: list[dict] = [
    {
        "what": (
            "ZERO interpreted requirements: this artifact is an activation "
            "SKELETON, not a UALink profile — it interprets no requirement "
            "from any source, public or gated"
        ),
        "reason": (
            "the UALink specification family is member-gated (HUM-02 "
            "pending; STD-UALINK-COMMON20 APPROVAL_REQUIRED, never fetched), "
            "and the member-public excerpts are architecture-level documents "
            "the license-gate registry itself marks 'not full specification' "
            "— insufficient for normative interpretation even where quotable"
        ),
    },
    {
        "what": (
            "the 'supported' element names the ACTIVATION TARGET surface "
            "(the cross-design L0 comparison's workload and observables), "
            "not an executed surface — nothing executes today"
        ),
        "reason": (
            "the format requires at least one workload and observable id; "
            "the honest declaration is the surface activation aims at "
            "(w1_dense_tp_decode under O-CCT/O-CONSERVATION, the same shape "
            "as the UEC/UnifiedBus comparison), stated here so no reader "
            "mistakes it for a claim that UALink behavior runs anywhere"
        ),
    },
    {
        "what": (
            "zero backend capability bindings and zero executable checks "
            "inside the artifact"
        ),
        "reason": (
            "bindings attach to simulated_behavior requirements and checks "
            "exercise requirements; with zero requirements both lists are "
            "empty by content. The skeleton's real invariants — the license "
            "fence (gated rows never fetched; the fetch guard refuses them) "
            "and byte-identical regeneration — live as tests at "
            "tests/specir/test_ualink_activation_skeleton.py"
        ),
    },
    {
        "what": (
            "no excerpt figure is promoted to a value: 200 GT/s per lane, "
            "64B/640B flits, 8B/4B headers, 1024 endpoints, and every other "
            "number the member-public excerpts state stays a graded "
            "CANDIDATE under an explicit free parameter (UAL-F01..F08)"
        ),
        "reason": (
            "an excerpt-stated figure is evidence about a public document, "
            "not a normative value; promotion requires an authorized-spec "
            "anchor, which does not exist until HUM-02 is answered and "
            "activation runs"
        ),
    },
    {
        "what": (
            "the UALink specification documents themselves (Common 2.0 "
            "Evaluation Copy and the DL/PL, Manageability, Chiplet family): "
            "not fetched, not read, not interpreted"
        ),
        "reason": (
            "license review precedes ingestion (workspace rule); the gated "
            "row STD-UALINK-COMMON20 (APPROVAL_REQUIRED) is kept verbatim "
            "and visible in the source record precisely so its pending "
            "status cannot be forgotten"
        ),
    },
    {
        "what": (
            "no calibration: no UALink hardware measurements exist on this "
            "platform"
        ),
        "reason": (
            "verification is not calibration; a skeleton that executes "
            "nothing has nothing to calibrate, and the status says so"
        ),
    },
]

#: Versioning rules (element 10).  Activation is a MAJOR bump by definition.
BUMP_RULES: dict[str, list[str]] = {
    "major": [
        "dispositions",  # first interpreted requirements arrive (activation)
        "bindings",  # first backend capability binding
        "anchor_ids",  # authorized-spec anchors cited
        "sources",  # the authorized source set lands (revision changes)
    ],
    "minor": ["requirements", "freedom", "checks", "supported"],
    "patch": ["notes"],
}

SKELETON_NOTE = (
    "ACTIVATION SKELETON, NOT A PROFILE: this artifact interprets zero "
    "UALink requirements. It exists so that the moment the pending license "
    "question (HUM-02) is answered with permission, the second NORMATIVE "
    "essun profile lands in one work session through the already-wired "
    "path: license-gated fetch guard -> sha-pinned extraction -> anchored "
    "quotes -> requirement modules -> this format (experiments/ualink/"
    "ACTIVATION.md). Its freedom element records, before the specification "
    "is ever read, the eight degrees of freedom a UALink profile will "
    "carry; the member-public excerpts anchor what they state as graded "
    "candidates and what they leave silent as explicit free parameters"
)

HEADER = f"""\
# UALink activation skeleton — {PROFILE_FORMAT_NAME} v{PROFILE_FORMAT_VERSION} artifact.
# GENERATED FILE (M5 UALink activation kit, 2026-11-02); regenerate with:
#   .venv/bin/python experiments/ualink/build_semantic_profile.py
# ACTIVATION SKELETON, NOT A PROFILE (stated here and in the artifact):
# zero interpreted requirements; the UALink specification family is
# member-gated (HUM-02 pending) and was never fetched. The two member-public
# excerpts (consortium whitepaper + 200G overview) exercise the pipeline and
# anchor the free-parameter skeleton only. Conformance gate:
# tests/specir/test_ualink_activation_skeleton.py (loads, visible absence,
# license fence, zero-binding honesty, corruption rejection, byte-identical
# regeneration).
"""


def _load_registry() -> PaperAnchorRegistry:
    registry = PaperAnchorRegistry.load(REGISTRY_PATH)
    registry.assert_valid()  # sha256 + quote re-match + PUBLIC_READ gate
    return registry


def _load_source_record() -> dict:
    raw = yaml.safe_load(SOURCE_RECORD_PATH.read_text(encoding="utf-8"))
    rows = raw.get("sources") if isinstance(raw, dict) else None
    if not rows:
        raise SystemExit(
            f"source record {SOURCE_RECORD_PATH} is missing its verbatim "
            "license-gate rows; the skeleton's provenance cites them"
        )
    return raw


def _check_license_fences(registry: PaperAnchorRegistry, record: dict) -> None:
    """Fence 2: no gated row appears among the fetched sources."""
    rows = record["sources"]
    gated = {row["id"]: row for row in rows if row["access"] != "PUBLIC_READ"}
    if "STD-UALINK-COMMON20" not in gated:
        raise SystemExit(
            "license fence: source record no longer carries the gated row "
            "STD-UALINK-COMMON20 (APPROVAL_REQUIRED) — the pending HUM-02 "
            "question must stay visible; re-copy the verbatim registry rows"
        )
    fetched_urls = {entry["url"].rstrip("/") for entry in registry.sources.values()}
    for row_id, row in sorted(gated.items()):
        if row["url"].rstrip("/") in fetched_urls:
            raise SystemExit(
                f"license fence: gated row {row_id} ({row['access']}) appears "
                "among the fetched excerpt sources — forbidden"
            )


def _source_set_revision(registry: PaperAnchorRegistry) -> str:
    """Content digest of the pinned excerpt set (computed, never invented)."""
    lines = sorted(
        f"{source_id} {entry['doc_sha256']}"
        for source_id, entry in registry.sources.items()
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def build_document(registry: PaperAnchorRegistry) -> dict:
    """Build the ten-element skeleton from the live registry and record."""
    record = _load_source_record()
    _check_license_fences(registry, record)
    gated_rows = [
        f"{row['id']} ({row['access']}, never fetched)"
        for row in record["sources"]
        if row["access"] != "PUBLIC_READ"
    ]

    excerpt_sources = [
        {
            "source_id": source_id,
            "title": entry["title"],
            "url": entry["url"],
            "access": entry["access"],
            "doc_sha256": entry["doc_sha256"],
            "handoff_row": entry.get("handoff_row"),
        }
        for source_id, entry in sorted(registry.sources.items())
    ]

    # Fence 3: the skeleton stays a skeleton (structural self-check).
    if INTERPRETED_REQUIREMENTS:
        raise SystemExit(
            "skeleton fence: INTERPRETED_REQUIREMENTS is non-empty — this "
            "builder ships skeletons only; activation supersedes it (see "
            "experiments/ualink/ACTIVATION.md)"
        )

    return {
        "format": {
            "name": PROFILE_FORMAT_NAME,
            "version": PROFILE_FORMAT_VERSION,
        },
        "profile_id": PROFILE_ID,
        # Element 1 — source identity/revision: the excerpt set today; the
        # authorized specification set at activation (a major bump).
        "source": {
            "name": (
                "UALink member-public excerpts (activation skeleton; the "
                "member-gated specification is not a source of this artifact)"
            ),
            "document_id": "ualink_member_public_excerpts",
            "revision": _source_set_revision(registry),
            "normative": False,
            "note": SKELETON_NOTE,
        },
        # Element 2 — provenance and permissions (license-gate vocabulary).
        "provenance": {
            "source_record": "experiments/ualink/source_record.yaml",
            "access": "PUBLIC_READ",  # both cited excerpts, verbatim rows
            "paper_sources": excerpt_sources,
            "anchor_registry": "experiments/ualink/anchor_registry.yaml",
            "gated_specification_rows": gated_rows,
            "license_status": HUM_STATUS,
            "evidence_grades_in_use": [EVIDENCE_GRADE],
            "note": (
                "license review precedes ingestion: the repo source record "
                "carries the verbatim license-gate rows, including the gated "
                "specification row, which was never fetched and is not "
                "interpreted here. Raw fetched bytes stay out of git "
                "(.cache/ualink_sources/); extracted pages carry per-page "
                "sha256; quotes in the anchor registry are citation-bounded "
                "and re-matched at load"
            ),
        },
        # Element 3 — interpreted requirements: NONE (visible absence).
        "requirements": {
            "objects": list(INTERPRETED_REQUIREMENTS),
            "note": REQUIREMENTS_NOTE,
        },
        # Element 4 — declared implementation freedom: the structural
        # skeleton, anchored to the member-public excerpts.
        "freedom": FREEDOM,
        # Element 5 — backend capability bindings: empty BY CONTENT.
        "bindings": [],
        # Element 6 — executable checks: empty BY CONTENT (the skeleton's
        # invariants live as tests; see omissions).
        "checks": [],
        # Element 7 — the ACTIVATION TARGET surface (see omissions: this is
        # what activation aims at, not an executed surface).
        "supported": {
            "workloads": ["w1_dense_tp_decode"],
            "observables": ["O-CCT", "O-CONSERVATION"],
        },
        # Element 8 — calibration scope (verification != calibration).
        "calibration": {
            "status": "uncalibrated",
            "targets": [],
            "note": (
                "nothing executes, so nothing is calibrated; no UALink "
                "hardware measurements exist on this platform, and the "
                "excerpt-stated figures (RTT goal, packing efficiency) are "
                "design claims carried with their grade, never calibration "
                "targets"
            ),
        },
        # Element 9 — known omissions (curated above).
        "omissions": OMISSIONS,
        # Element 10 — versioning rules.
        "versioning": {
            "profile_version": PROFILE_VERSION,
            "bump_rules": BUMP_RULES,
            "note": (
                "the version tracks this ARTIFACT; activation (the first "
                "interpreted requirement, binding, authorized-spec anchor, "
                "or authorized source) is a MAJOR bump to 1.0.0 by rule — "
                "a skeleton never silently becomes a profile"
            ),
        },
    }


def validate_document(document: dict, registry: PaperAnchorRegistry) -> list[str]:
    """Every gate the builder itself enforces before writing; [] = valid."""
    problems = list(profile_problems(document))
    if problems:
        return problems
    profile = profile_from_dict(document, source="<built document>")
    problems.extend(
        check_anchor_refs(profile, {a.anchor_id for a in registry.anchors})
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
            f"refusing to write an invalid skeleton artifact: {detail}{more}"
        )

    profile = profile_from_dict(document, source="<built document>")
    counts = profile.disposition_counts()
    args.output.write_text(render(document), encoding="utf-8")
    print(f"wrote {args.output}")
    print(
        "skeleton record: "
        f"{len(profile.requirements)} requirements (visible absence), "
        f"{len(profile.freedom)} free parameters, "
        f"{len(profile.bindings)} binding(s), {len(profile.checks)} check(s)"
    )
    print(
        "ACTIVATION SKELETON, NOT A PROFILE: interprets nothing; gated "
        "specification never fetched (HUM-02 pending)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
