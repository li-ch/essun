"""Multi-source public-paper anchor registry for the UnifiedBus profile (Q6 S1).

The Q1 registry (``essun.specir.anchors``) anchors ONE extracted standard
document (STD-UEC-11).  The UnifiedBus ladder cannot use that shape: the
UnifiedBus specification track is license-gated (license review pending), so the
profile is built ONLY from public papers and vendor engineering posts —
necessarily MULTIPLE sources (UB-Mesh paper, Huawei Connect 2026 post, the
public unifiedbus.com pages, the Nested-Parallel-von-Neumann paper).

This module therefore provides :class:`PaperAnchorRegistry`, the multi-source
counterpart of :class:`~essun.specir.anchors.AnchorRegistry`:

- each :class:`PaperAnchor` additionally carries the ``source_id`` of the
  public document it cites (plus a ``category`` used by profile stages S2-S4
  to select design parameters);
- every source block must declare ``access: PUBLIC_READ`` — the license gate
  is enforced structurally by :meth:`PaperAnchorRegistry.verify`, so a gated
  (e.g. UnifiedBus-specification) source can never be anchored silently;
- integrity is checkable offline and deterministically: page-file sha256 is
  recomputed and every quote is re-matched against the page text, exactly
  like Q1.

The registry data file is ``experiments/unifiedbus/anchor_registry.yaml``
(built by ``experiments/unifiedbus/build_anchor_registry.py`` from the
extraction under ``experiments/unifiedbus/source/``); raw fetched documents
never enter git (``.cache/ub_sources/``).

Honesty rule (absolute): values anchored here describe a PAPER-DERIVED design
profile, not a normative standard profile.  Whether that satisfies the
public-release gate's "2 distinct standards" leg is an open decision
(license review pending) — never encoded in this module.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .anchors import (
    Anchor,
    AnchorRegistryError,
    normalize_whitespace,
)

REPO_ROOT = Path(__file__).resolve().parents[3]  # src/essun/specir/ -> repo root
DEFAULT_REGISTRY_PATH = REPO_ROOT / "experiments/unifiedbus/anchor_registry.yaml"
DEFAULT_SOURCE_MANIFEST = REPO_ROOT / "experiments/unifiedbus/source/source_manifest.yaml"

#: Citation-snippet bound. Q1 bounds quotes at 30 whitespace-words; Chinese
#: source text packs far more content per whitespace-word, so an additional
#: character bound keeps every quote citation-grade in both languages.
MAX_QUOTE_CHARS = 200

#: Registry quotes from public papers/posts only (ladder honesty rule).
REQUIRED_ACCESS = "PUBLIC_READ"

_SECTION_RE = re.compile(r"^\d+(\.\d+)*$")


@dataclass(frozen=True)
class PaperAnchor:
    """One verifiable citation into one extracted public paper/post."""

    anchor_id: str
    source_id: str
    section: str
    page: int
    quote: str
    page_sha256: str
    title: str = ""
    category: str = ""

    # -- reuse of the Q1 anchor's well-tested shape/quote logic ------------

    def to_core_anchor(self) -> Anchor:
        return Anchor(
            anchor_id=self.anchor_id,
            section=self.section,
            page=self.page,
            quote=self.quote,
            page_sha256=self.page_sha256,
            title=self.title,
        )

    def word_count(self) -> int:
        return len(self.quote.split())

    def char_count(self) -> int:
        return len(self.quote)

    def check_shape(self) -> list[str]:
        problems = self.to_core_anchor().check_shape()
        if not self.source_id or not self.source_id.strip():
            problems.append(f"{self.anchor_id!r}: empty source_id")
        if self.char_count() > MAX_QUOTE_CHARS:
            problems.append(
                f"{self.anchor_id}: quote has {self.char_count()} chars "
                f"(> {MAX_QUOTE_CHARS})"
            )
        return problems

    def quote_in(self, page_text: str) -> bool:
        return normalize_whitespace(self.quote) in normalize_whitespace(page_text)


@dataclass
class PaperAnchorRegistry:
    """Loaded multi-source registry plus the extracted pages it cites."""

    sources: dict[str, dict[str, Any]]
    anchors: tuple[PaperAnchor, ...]
    registry_path: Path = field(default=DEFAULT_REGISTRY_PATH)
    repo_root: Path = field(default=REPO_ROOT)

    @classmethod
    def load(
        cls,
        path: Path | str = DEFAULT_REGISTRY_PATH,
        repo_root: Path | str = REPO_ROOT,
    ) -> "PaperAnchorRegistry":
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if (
            not isinstance(raw, dict)
            or "sources" not in raw
            or "anchors" not in raw
        ):
            raise AnchorRegistryError(
                f"paper anchor registry {path} must be a mapping with "
                "'sources' and 'anchors'"
            )
        sources: dict[str, dict[str, Any]] = {}
        for entry in raw["sources"]:
            sid = entry.get("source_id")
            if not sid:
                raise AnchorRegistryError(f"registry source missing source_id in {path}")
            if sid in sources:
                raise AnchorRegistryError(f"duplicate source_id {sid} in {path}")
            sources[sid] = entry
        anchors: list[PaperAnchor] = []
        for entry in raw["anchors"]:
            try:
                anchors.append(
                    PaperAnchor(
                        anchor_id=entry["id"],
                        source_id=entry["source_id"],
                        section=str(entry["section"]),
                        page=int(entry["page"]),
                        quote=entry["quote"],
                        page_sha256=entry["page_sha256"],
                        title=entry.get("title", ""),
                        category=entry.get("category", ""),
                    )
                )
            except KeyError as missing:
                raise AnchorRegistryError(
                    f"anchor entry missing field {missing} in {path}"
                ) from missing
        return cls(
            sources=sources,
            anchors=tuple(anchors),
            registry_path=path,
            repo_root=Path(repo_root),
        )

    # -- lookups -----------------------------------------------------------

    def by_id(self) -> dict[str, PaperAnchor]:
        return {anchor.anchor_id: anchor for anchor in self.anchors}

    def resolve(
        self, anchor_ids: list[str] | tuple[str, ...]
    ) -> tuple[PaperAnchor, ...]:
        """Resolve anchor ids; raise on any dangling id (profile stages use this)."""
        index = self.by_id()
        missing = [aid for aid in anchor_ids if aid not in index]
        if missing:
            raise AnchorRegistryError(
                f"dangling anchor ids (not in {self.registry_path}): {missing}"
            )
        return tuple(index[aid] for aid in anchor_ids)

    def anchors_for(self, source_id: str) -> tuple[PaperAnchor, ...]:
        return tuple(a for a in self.anchors if a.source_id == source_id)

    def categories(self) -> set[str]:
        return {a.category for a in self.anchors}

    def by_category(self, category: str) -> tuple[PaperAnchor, ...]:
        return tuple(a for a in self.anchors if a.category == category)

    def source_of(self, anchor: PaperAnchor) -> dict[str, Any]:
        try:
            return self.sources[anchor.source_id]
        except KeyError as missing:
            raise AnchorRegistryError(
                f"{anchor.anchor_id}: unknown source_id {missing}"
            ) from missing

    def pages_dir(self, source_id: str) -> Path:
        entry = self.sources[source_id]
        declared = entry.get("pages_dir")
        if not declared:
            raise AnchorRegistryError(f"source {source_id} missing pages_dir")
        return self.repo_root / declared

    def page_path(self, anchor: PaperAnchor) -> Path:
        return self.pages_dir(anchor.source_id) / f"page_{anchor.page:04d}.txt"

    # -- integrity ----------------------------------------------------------

    def verify(self) -> list[str]:
        """Recompute every integrity check; return all problems (empty = valid).

        Checks: every source declares ``access: PUBLIC_READ`` and the
        metadata needed for provenance (url, doc_sha256, page_count,
        pages_dir); anchor shape (reusing the Q1 :class:`Anchor` rules plus
        the source_id/char bound); unique anchor ids; every anchor's
        source_id known; page file exists; sha256(page file bytes) equals the
        recorded page_sha256; and the quote is a whitespace-normalized
        substring of that page's text.
        """
        problems: list[str] = []
        seen: dict[str, int] = {}
        for sid, entry in self.sources.items():
            if entry.get("access") != REQUIRED_ACCESS:
                problems.append(
                    f"source {sid}: access {entry.get('access')!r} != "
                    f"{REQUIRED_ACCESS!r} — license gate violated (paper-derived "
                    "registry may only anchor public sources)"
                )
            for key in ("url", "doc_sha256", "page_count", "pages_dir"):
                if key not in entry:
                    problems.append(f"source {sid}: metadata missing {key!r}")
        for anchor in self.anchors:
            problems.extend(anchor.check_shape())
            seen[anchor.anchor_id] = seen.get(anchor.anchor_id, 0) + 1
            if anchor.source_id not in self.sources:
                problems.append(
                    f"{anchor.anchor_id}: unknown source_id {anchor.source_id}"
                )
        problems.extend(
            f"duplicate anchor id {aid} ({count} entries)"
            for aid, count in sorted(seen.items())
            if count > 1
        )
        for anchor in self.anchors:
            if anchor.source_id not in self.sources:
                continue
            path = self.page_path(anchor)
            if not path.is_file():
                problems.append(f"{anchor.anchor_id}: missing page file {path}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != anchor.page_sha256:
                problems.append(
                    f"{anchor.anchor_id}: page {anchor.page} sha256 {digest} != "
                    f"recorded {anchor.page_sha256}"
                )
            if not anchor.quote_in(path.read_text(encoding="utf-8")):
                problems.append(
                    f"{anchor.anchor_id}: quote not found in extracted page "
                    f"{anchor.page}"
                )
        return problems

    def assert_valid(self) -> None:
        problems = self.verify()
        if problems:
            detail = "; ".join(problems[:10])
            more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
            raise AnchorRegistryError(
                f"paper anchor registry {self.registry_path} failed integrity: "
                f"{detail}{more}"
            )

    # -- provenance ---------------------------------------------------------

    def public_sources_summary(self) -> list[dict[str, Any]]:
        """Per-source provenance summary (id, url, access, doc sha, role)."""
        return [
            {
                "source_id": sid,
                "url": entry.get("url"),
                "access": entry.get("access"),
                "doc_sha256": entry.get("doc_sha256"),
                "handoff_row": entry.get("handoff_row"),
                "role": entry.get("role"),
                "anchor_count": len(self.anchors_for(sid)),
            }
            for sid, entry in self.sources.items()
        ]
