"""Source anchors: verifiable citations into extracted standard text (T010).

An :class:`Anchor` is the unit of provenance for every spec-derived value in
SpecIR (provenance rule: every standard-derived value keeps a source
anchor).  An anchor points at

- a *source* (``STD-UEC-11`` today),
- a *section number* and *page* of that source,
- a verbatim *quote* of at most :data:`MAX_QUOTE_WORDS` words, and
- the sha256 of the *extracted page file* the quote was taken from.

The companion registry data file is ``experiments/uec/anchor_registry.yaml``
(built by ``experiments/uec/build_anchor_registry.py`` from the extraction
under ``experiments/uec/source/``); the PDF itself never enters git.

Integrity is checkable offline and deterministically:
:meth:`AnchorRegistry.verify` re-hashes the page files and re-matches every
quote against the page text, so a registry edited by hand, a stale extraction
or a dangling anchor is a hard error, never a silent drift.  Later SpecIR
objects (requirement → anchor ids → typed statement) resolve their anchors
through :meth:`AnchorRegistry.resolve`, which rejects dangling ids.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]  # src/essun/specir/ -> repo root
DEFAULT_REGISTRY_PATH = REPO_ROOT / "experiments/uec/anchor_registry.yaml"
DEFAULT_PAGES_DIR = REPO_ROOT / "experiments/uec/source/pages"

#: Registry quotes are citation snippets, not text reproduction (S0 license
#: gate: <= 30 words per quote, always with source attribution).
MAX_QUOTE_WORDS = 30

_SECTION_RE = re.compile(r"^\d+(\.\d+)*$|^Release Notes$")


class AnchorRegistryError(Exception):
    """Raised when a registry or anchor fails an integrity check."""


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces (extraction wraps lines)."""
    return " ".join(text.split())


@dataclass(frozen=True)
class Anchor:
    """One verifiable citation into an extracted standard document."""

    anchor_id: str
    section: str
    page: int
    quote: str
    page_sha256: str
    title: str = ""

    def word_count(self) -> int:
        return len(self.quote.split())

    def check_shape(self) -> list[str]:
        """Return structural problems (no filesystem access needed)."""
        problems: list[str] = []
        if not self.anchor_id or not self.anchor_id.strip():
            problems.append(f"{self.anchor_id!r}: empty anchor id")
        if not _SECTION_RE.match(self.section):
            problems.append(f"{self.anchor_id}: malformed section {self.section!r}")
        if not (1 <= self.page):
            problems.append(f"{self.anchor_id}: page must be >= 1, got {self.page}")
        if not re.fullmatch(r"[0-9a-f]{64}", self.page_sha256 or ""):
            problems.append(f"{self.anchor_id}: page_sha256 is not a sha256 hex digest")
        if self.word_count() == 0:
            problems.append(f"{self.anchor_id}: empty quote")
        elif self.word_count() > MAX_QUOTE_WORDS:
            problems.append(
                f"{self.anchor_id}: quote has {self.word_count()} words "
                f"(> {MAX_QUOTE_WORDS})"
            )
        return problems

    def quote_in(self, page_text: str) -> bool:
        return normalize_whitespace(self.quote) in normalize_whitespace(page_text)


@dataclass
class AnchorRegistry:
    """Loaded anchor registry plus the extracted pages it cites."""

    source: dict[str, Any]
    anchors: tuple[Anchor, ...]
    registry_path: Path = field(default=DEFAULT_REGISTRY_PATH)
    pages_dir: Path = field(default=DEFAULT_PAGES_DIR)

    @classmethod
    def load(
        cls,
        path: Path | str = DEFAULT_REGISTRY_PATH,
        pages_dir: Path | str | None = None,
    ) -> "AnchorRegistry":
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "source" not in raw or "anchors" not in raw:
            raise AnchorRegistryError(
                f"anchor registry {path} must be a mapping with 'source' and 'anchors'"
            )
        anchors: list[Anchor] = []
        for entry in raw["anchors"]:
            try:
                anchors.append(
                    Anchor(
                        anchor_id=entry["id"],
                        section=str(entry["section"]),
                        page=int(entry["page"]),
                        quote=entry["quote"],
                        page_sha256=entry["page_sha256"],
                        title=entry.get("title", ""),
                    )
                )
            except KeyError as missing:
                raise AnchorRegistryError(
                    f"anchor entry missing field {missing} in {path}"
                ) from missing
        declared_pages_dir = raw["source"].get("pages_dir")
        if pages_dir is not None:
            resolved_pages = Path(pages_dir)
        elif declared_pages_dir:
            # Registry stores the path repo-relative; resolve against REPO_ROOT.
            resolved_pages = REPO_ROOT / declared_pages_dir
        else:
            resolved_pages = DEFAULT_PAGES_DIR
        return cls(
            source=raw["source"],
            anchors=tuple(anchors),
            registry_path=path,
            pages_dir=resolved_pages,
        )

    # -- lookups ---------------------------------------------------------

    def by_id(self) -> dict[str, Anchor]:
        return {anchor.anchor_id: anchor for anchor in self.anchors}

    def sections(self) -> list[str]:
        return [anchor.section for anchor in self.anchors]

    def toplevel_sections(self) -> set[str]:
        """First component of every anchored section (chapter coverage)."""
        return {anchor.section.split(".")[0] for anchor in self.anchors}

    def resolve(self, anchor_ids: list[str] | tuple[str, ...]) -> tuple[Anchor, ...]:
        """Resolve anchor ids; raise on any dangling id (S2-S5 objects use this)."""
        index = self.by_id()
        missing = [aid for aid in anchor_ids if aid not in index]
        if missing:
            raise AnchorRegistryError(
                f"dangling anchor ids (not in {self.registry_path}): {missing}"
            )
        return tuple(index[aid] for aid in anchor_ids)

    def page_path(self, page: int) -> Path:
        return self.pages_dir / f"page_{page:04d}.txt"

    # -- integrity -------------------------------------------------------

    def verify(self) -> list[str]:
        """Recompute every integrity check; return all problems (empty = valid).

        Checks: structural anchor shape, unique ids, page file exists,
        sha256(page file bytes) == recorded page_sha256, quote is a
        whitespace-normalized substring of the page text, and registry
        source metadata (source_id, pdf_sha256) is present.
        """
        problems: list[str] = []
        seen: dict[str, int] = {}
        for anchor in self.anchors:
            problems.extend(anchor.check_shape())
            seen[anchor.anchor_id] = seen.get(anchor.anchor_id, 0) + 1
        problems.extend(
            f"duplicate anchor id {aid} ({count} entries)"
            for aid, count in sorted(seen.items())
            if count > 1
        )
        for key in ("source_id", "pdf_sha256", "page_count"):
            if key not in self.source:
                problems.append(f"registry source metadata missing {key!r}")
        for anchor in self.anchors:
            path = self.page_path(anchor.page)
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
                f"anchor registry {self.registry_path} failed integrity: "
                f"{detail}{more}"
            )
