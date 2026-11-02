"""M1 S1: the NVLink-class public-paper anchor registry.

Mirrors the UnifiedBus registry tests
(``tests/specir/test_unifiedbus_paper_registry.py``) for the third
fabric's registry (``experiments/nvlink/anchor_registry.yaml``): only
PUBLIC_READ sources, the repo license-gate record matched verbatim
(including the never-fetched STD-NV-SPEC row — no public NVLink/NVSwitch
specification exists), page hashes re-computable, quotes verbatim and
citation-bounded, and the synthetic-registry negative bars.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.unifiedbus_sources import (
    AnchorRegistryError,
    PaperAnchorRegistry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "experiments/nvlink/anchor_registry.yaml"
SOURCE_RECORD = REPO_ROOT / "experiments/nvlink/source_record.yaml"


@pytest.fixture(scope="module")
def registry() -> PaperAnchorRegistry:
    reg = PaperAnchorRegistry.load(REGISTRY)
    reg.assert_valid()  # sha256 + quote re-match + PUBLIC_READ gate
    return reg


def test_five_anchored_public_sources(registry: PaperAnchorRegistry) -> None:
    assert len(registry.sources) == 5
    assert {s.split("PUB-NV-")[1][:4] for s in registry.sources} == {
        "LI-T", "TPU4", "GB20", "GB20", "NCCL",
    }


def test_every_source_is_public_read(registry: PaperAnchorRegistry) -> None:
    for sid, entry in registry.sources.items():
        assert entry["access"] == "PUBLIC_READ", sid


def test_license_gate_matches_source_record(registry: PaperAnchorRegistry) -> None:
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in record["sources"]}
    # The gated specification row exists, is not PUBLIC_READ, is never a
    # registry source, and no registry URL matches it.
    gated = rows["STD-NV-SPEC"]
    assert gated["access"] == "APPROVAL_REQUIRED"
    for sid, entry in registry.sources.items():
        assert sid != "STD-NV-SPEC"
        assert entry["url"].rstrip("/") != gated["url"].rstrip("/")
    # Every registry source with a handoff row echoes that row verbatim.
    for sid, entry in registry.sources.items():
        row_id = entry.get("handoff_row")
        if row_id:
            assert rows[row_id]["access"] == "PUBLIC_READ"
            assert rows[row_id]["url"].rstrip("/") == entry["url"].rstrip("/"), sid


def test_page_hashes_are_recomputable(registry: PaperAnchorRegistry) -> None:
    for anchor in registry.anchors:
        page = REPO_ROOT / registry.pages_dir(anchor.source_id) / (
            f"page_{anchor.page:04d}.txt"
        )
        assert page.is_file(), anchor.anchor_id
        digest = hashlib.sha256(page.read_bytes()).hexdigest()
        assert digest == anchor.page_sha256, anchor.anchor_id


def test_quotes_are_verbatim_and_bounded(registry: PaperAnchorRegistry) -> None:
    for anchor in registry.anchors:
        assert anchor.word_count() <= 30, anchor.anchor_id
        assert anchor.char_count() <= 200, anchor.anchor_id
        page = REPO_ROOT / registry.page_path(anchor)
        assert anchor.quote_in(page.read_text(encoding="utf-8")), anchor.anchor_id


def test_anchor_ids_unique(registry: PaperAnchorRegistry) -> None:
    ids = [a.anchor_id for a in registry.anchors]
    assert len(ids) == len(set(ids)) == 28


def test_registry_covers_design_categories(registry: PaperAnchorRegistry) -> None:
    assert registry.categories() == {
        "topology", "link_scale", "scale", "latency",
        "routing", "performance", "software",
    }


def test_resolve_rejects_dangling_anchor_ids(registry: PaperAnchorRegistry) -> None:
    with pytest.raises(AnchorRegistryError, match="dangling anchor ids"):
        registry.resolve(["NVP-DOES-NOT-EXIST"])


# -- synthetic-registry negative bars ----------------------------------------


def _synthetic(tmp_path: Path, **overrides) -> tuple[Path, dict]:
    pages = tmp_path / "pages" / "SYN-NV"
    pages.mkdir(parents=True, exist_ok=True)
    text = "Each NVSwitch is a 18x18 fully connected non-blocking crossbar."
    (pages / "page_0001.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0001.txt").read_bytes()).hexdigest()
    entry = {
        "sources": [
            {
                "source_id": "SYN-NV",
                "title": "synthetic public paper",
                "url": "https://example.org/synthetic",
                "access": "PUBLIC_READ",
                "doc_sha256": "0" * 64,
                "page_count": 1,
                "pages_dir": str(pages),
            }
        ],
        "anchors": [
            {
                "id": "SYN-NV-1",
                "source_id": "SYN-NV",
                "section": "1",
                "title": "synthetic",
                "category": "topology",
                "page": 1,
                "quote": text,
                "page_sha256": digest,
            }
        ],
    }
    for key, value in overrides.items():
        entry[key] = value
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(entry), encoding="utf-8")
    return path, entry


def test_synthetic_registry_validates(tmp_path: Path) -> None:
    path, _ = _synthetic(tmp_path)
    PaperAnchorRegistry.load(path, repo_root=tmp_path).assert_valid()


def test_non_public_source_is_rejected(tmp_path: Path) -> None:
    path, entry = _synthetic(tmp_path)
    entry["sources"][0]["access"] = "APPROVAL_REQUIRED"
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    with pytest.raises(AnchorRegistryError, match="license gate violated"):
        PaperAnchorRegistry.load(path, repo_root=tmp_path).assert_valid()


def test_dangling_page_hash_is_rejected(tmp_path: Path) -> None:
    path, entry = _synthetic(tmp_path)
    entry["anchors"][0]["page_sha256"] = "f" * 64
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    with pytest.raises(AnchorRegistryError, match="sha256"):
        PaperAnchorRegistry.load(path, repo_root=tmp_path).assert_valid()


def test_quote_not_on_page_is_rejected(tmp_path: Path) -> None:
    path, entry = _synthetic(tmp_path)
    entry["anchors"][0]["quote"] = "57.6 terabits per second, nowhere on this page"
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    with pytest.raises(AnchorRegistryError, match="quote not found"):
        PaperAnchorRegistry.load(path, repo_root=tmp_path).assert_valid()


def test_missing_page_file_is_rejected(tmp_path: Path) -> None:
    path, entry = _synthetic(tmp_path)
    entry["anchors"][0]["page"] = 7
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    with pytest.raises(AnchorRegistryError, match="missing page file"):
        PaperAnchorRegistry.load(path, repo_root=tmp_path).assert_valid()
