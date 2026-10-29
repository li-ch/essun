"""Anchor registry integrity tests for the UnifiedBus public-paper sources
(Q6 stage S1).

Bars from the stage prompt: >= 3 anchored public sources, registry integrity
test green. The ladder's honesty rule is enforced permanently here:

- every registry source must be ``PUBLIC_READ`` (checked by the module's
  verify() AND re-checked against the repo-level source record below);
- sources citing a recorded row (STD-UB-HOME, STD-UB-OS) must match that
  row's URL and access;
- NO registry source URL may equal the URL of any recorded row whose
  access is not PUBLIC_READ — in particular the license-gated UnifiedBus
  specification (STD-UB-LICENSE, carried in the record precisely so this
  check keeps meaning) and every REVIEW_REQUIRED/DO_NOT_INGEST row can
  never be anchored from this registry.

The record is ``experiments/unifiedbus/source_record.yaml``: all three
STD-UB rows copied verbatim from the handoff sources.csv at D-035 stage
S2 (F2 scope choice — public rows the registry cites plus the gated
license row, so the gate does not silently narrow).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import AnchorRegistryError, MAX_QUOTE_WORDS
from essun.specir.unifiedbus_sources import (
    MAX_QUOTE_CHARS,
    PaperAnchor,
    PaperAnchorRegistry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RECORD = REPO_ROOT / "experiments/unifiedbus/source_record.yaml"
SOURCE_MANIFEST = REPO_ROOT / "experiments/unifiedbus/source/source_manifest.yaml"

#: Design-relevant categories the S2-S4 stages rely on (a registry missing
#: any of these cannot parameterize topology / link scale / memory semantics
#: / latency, the four axes the ladder prompt names).
REQUIRED_CATEGORIES = {"topology", "link_scale", "memory_semantics", "latency"}


@pytest.fixture(scope="module")
def registry() -> PaperAnchorRegistry:
    reg = PaperAnchorRegistry.load()
    reg.assert_valid()  # every test below sees a fully verified registry
    return reg


def test_at_least_three_anchored_public_sources(registry: PaperAnchorRegistry) -> None:
    # Stage bar: >= 3 anchored sources.
    assert len(registry.sources) >= 3
    assert len(registry.anchors) >= 10


def test_every_source_is_public_read(registry: PaperAnchorRegistry) -> None:
    for sid, entry in registry.sources.items():
        assert entry["access"] == "PUBLIC_READ", sid


def test_license_gate_matches_source_record(registry: PaperAnchorRegistry) -> None:
    """Ladder honesty rule made permanent.

    1. For every registry source citing a recorded row, that row must
       exist, be PUBLIC_READ, and its URL must match the fetched URL.
    2. No registry source URL may appear in the source record with a
       non-public access label (gated UnifiedBus specification license,
       STD-UB-LICENSE, ...).
    """
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    rows = record["sources"]
    assert {row["id"] for row in rows} == {
        "STD-UB-HOME",
        "STD-UB-LICENSE",
        "STD-UB-OS",
    }
    url_access = {row["url"].rstrip("/"): row for row in rows}
    by_id = {row["id"]: row for row in rows}

    for source in registry.public_sources_summary():
        url = str(source["url"]).rstrip("/")
        if url in url_access:
            row = url_access[url]
            assert row["access"] == "PUBLIC_READ", (
                f"{source['source_id']} fetches {url} registered as "
                f"{row['id']} with access {row['access']}"
            )
        handoff_row = source["handoff_row"]
        if handoff_row:
            assert handoff_row in by_id, handoff_row
            row = by_id[handoff_row]
            assert row["access"] == "PUBLIC_READ", handoff_row
            # the pre-cleared row's URL must be the registry URL or its
            # public same-site variant (STD-UB-HOME "/" vs "/en" index)
            assert url == row["url"].rstrip("/") or url.startswith(row["url"].rstrip("/")), (
                f"{source['source_id']}: url {url} does not match handoff row "
                f"{handoff_row} url {row['url']}"
            )


def test_pre_cleared_public_rows_are_used(registry: PaperAnchorRegistry) -> None:
    # The two pre-cleared public unifiedbus.com rows must be among the sources
    # (S1 asked for "sources.csv public rows + search").
    handoff_rows = {s["handoff_row"] for s in registry.public_sources_summary()}
    assert {"STD-UB-HOME", "STD-UB-OS"} <= handoff_rows


def test_page_hashes_are_recomputable(registry: PaperAnchorRegistry) -> None:
    # Recompute sha256 over the committed page files, independent of the
    # module's own verify(), then cross-check against the fetch manifest.
    manifest = yaml.safe_load(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    sha_by_sid = {
        rec["source_id"]: {p["page"]: p["sha256"] for p in rec["pages"]}
        for rec in manifest["sources"]
    }
    for anchor in registry.anchors:
        page_file = registry.page_path(anchor)
        digest = hashlib.sha256(page_file.read_bytes()).hexdigest()
        assert digest == anchor.page_sha256, anchor.anchor_id
        assert sha_by_sid[anchor.source_id][anchor.page] == anchor.page_sha256, (
            anchor.anchor_id
        )


def test_quotes_are_verbatim_and_bounded(registry: PaperAnchorRegistry) -> None:
    for anchor in registry.anchors:
        assert 0 < anchor.word_count() <= MAX_QUOTE_WORDS, anchor.anchor_id
        assert 0 < anchor.char_count() <= MAX_QUOTE_CHARS, anchor.anchor_id
        page_text = registry.page_path(anchor).read_text(encoding="utf-8")
        assert anchor.quote_in(page_text), anchor.anchor_id


def test_anchor_ids_unique(registry: PaperAnchorRegistry) -> None:
    ids = [anchor.anchor_id for anchor in registry.anchors]
    assert len(ids) == len(set(ids))


def test_registry_covers_design_categories(registry: PaperAnchorRegistry) -> None:
    # The S2 profile needs parameters on all four axes the ladder names.
    assert REQUIRED_CATEGORIES <= registry.categories()
    for category in REQUIRED_CATEGORIES:
        assert len(registry.by_category(category)) >= 1, category


def test_resolve_rejects_dangling_anchor_ids(registry: PaperAnchorRegistry) -> None:
    some_id = registry.anchors[0].anchor_id
    resolved = registry.resolve([some_id])
    assert resolved[0].anchor_id == some_id
    with pytest.raises(AnchorRegistryError, match="dangling anchor ids"):
        registry.resolve([some_id, "UBP-DOES-NOT-EXIST"])


# -- negative tests: integrity and license failures are hard errors ---------


def _synthetic_registry(tmp_path: Path, access: str = "PUBLIC_READ") -> PaperAnchorRegistry:
    pages = tmp_path / "pages" / "SYN-SRC"
    pages.mkdir(parents=True)
    page_text = (
        "3.2 Building Blocks\n\nThe NPU equips two UB IO controllers, which "
        "collectively provide x72 UB lanes."
    )
    (pages / "page_0001.txt").write_text(page_text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0001.txt").read_bytes()).hexdigest()
    entry = {
        "sources": [
            {
                "source_id": "SYN-SRC",
                "title": "synthetic public post",
                "url": "https://example.org/synthetic",
                "access": access,
                "doc_sha256": "0" * 64,
                "page_count": 1,
                "pages_dir": str(pages),
            }
        ],
        "anchors": [
            {
                "id": "SYN-1",
                "source_id": "SYN-SRC",
                "section": "3.2",
                "title": "synthetic",
                "category": "link_scale",
                "page": 1,
                "quote": "The NPU equips two UB IO controllers, which "
                "collectively provide x72 UB lanes.",
                "page_sha256": digest,
            }
        ],
    }
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    reg = PaperAnchorRegistry.load(registry_file, repo_root=tmp_path)
    if access == "PUBLIC_READ":
        reg.assert_valid()  # synthetic baseline is valid
    return reg


def test_synthetic_registry_validates(tmp_path: Path) -> None:
    _synthetic_registry(tmp_path)


def test_non_public_source_is_rejected(tmp_path: Path) -> None:
    reg = _synthetic_registry(tmp_path, access="APPROVAL_REQUIRED")
    problems = reg.verify()
    assert any("license gate violated" in p for p in problems)
    with pytest.raises(AnchorRegistryError, match="license gate violated"):
        reg.assert_valid()


def test_unknown_source_id_is_rejected(tmp_path: Path) -> None:
    reg = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = PaperAnchor(
        anchor_id=anchor.anchor_id,
        source_id="SYN-OTHER-SRC",  # not in sources
        section=anchor.section,
        page=anchor.page,
        quote=anchor.quote,
        page_sha256=anchor.page_sha256,
        title=anchor.title,
        category=anchor.category,
    )
    bad = PaperAnchorRegistry(reg.sources, (tampered,), reg.registry_path, reg.repo_root)
    with pytest.raises(AnchorRegistryError, match="unknown source_id"):
        bad.assert_valid()


def test_dangling_page_hash_is_rejected(tmp_path: Path) -> None:
    reg = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = PaperAnchor(
        anchor_id=anchor.anchor_id,
        source_id=anchor.source_id,
        section=anchor.section,
        page=anchor.page,
        quote=anchor.quote,
        page_sha256="f" * 64,  # does not match the page file
        title=anchor.title,
        category=anchor.category,
    )
    bad = PaperAnchorRegistry(reg.sources, (tampered,), reg.registry_path, reg.repo_root)
    with pytest.raises(AnchorRegistryError, match="sha256"):
        bad.assert_valid()


def test_quote_not_on_page_is_rejected(tmp_path: Path) -> None:
    reg = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = PaperAnchor(
        anchor_id=anchor.anchor_id,
        source_id=anchor.source_id,
        section=anchor.section,
        page=anchor.page,
        quote="This sentence is nowhere in the extracted page.",
        page_sha256=anchor.page_sha256,
        title=anchor.title,
        category=anchor.category,
    )
    bad = PaperAnchorRegistry(reg.sources, (tampered,), reg.registry_path, reg.repo_root)
    with pytest.raises(AnchorRegistryError, match="quote not found"):
        bad.assert_valid()


def test_missing_page_file_is_rejected(tmp_path: Path) -> None:
    reg = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = PaperAnchor(
        anchor_id=anchor.anchor_id,
        source_id=anchor.source_id,
        section=anchor.section,
        page=999,  # no such extracted page
        quote=anchor.quote,
        page_sha256=anchor.page_sha256,
        title=anchor.title,
        category=anchor.category,
    )
    bad = PaperAnchorRegistry(reg.sources, (tampered,), reg.registry_path, reg.repo_root)
    with pytest.raises(AnchorRegistryError, match="missing page file"):
        bad.assert_valid()


def test_overlong_quote_is_rejected_by_shape() -> None:
    anchor = PaperAnchor(
        anchor_id="SYN-LONG",
        source_id="SYN-SRC",
        section="3.2",
        page=1,
        quote=" ".join(["word"] * (MAX_QUOTE_WORDS + 1)),
        page_sha256="0" * 64,
    )
    assert any("words" in p for p in anchor.check_shape())


def test_overlong_chars_quote_is_rejected_by_shape() -> None:
    anchor = PaperAnchor(
        anchor_id="SYN-LONG-CHARS",
        source_id="SYN-SRC",
        section="3.2",
        page=1,
        quote="字" * (MAX_QUOTE_CHARS + 1),  # one whitespace-word, but too long
        page_sha256="0" * 64,
    )
    assert any("chars" in p for p in anchor.check_shape())
