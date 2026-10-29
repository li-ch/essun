"""Anchor registry integrity tests for the UEC 1.1 source ingest (T010, S1).

Bars from the stage prompt: registry covers the spec's top-level structure,
has >= 30 anchors, and a test validates registry integrity with recomputable
hashes. The license gate (S0) is additionally enforced permanently: the
registry's pdf_sha256 must equal the value recorded for STD-UEC-11 in the
repo-level source record (experiments/uec/source_record.yaml, copied
verbatim from the handoff sources.csv at D-035 stage S2).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import (
    MAX_QUOTE_WORDS,
    Anchor,
    AnchorRegistry,
    AnchorRegistryError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RECORD = REPO_ROOT / "experiments/uec/source_record.yaml"
SOURCE_MANIFEST = REPO_ROOT / "experiments/uec/source/source_manifest.yaml"


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()  # every test below sees a fully verified registry
    return reg


def test_registry_has_at_least_30_anchors(registry: AnchorRegistry) -> None:
    assert len(registry.anchors) >= 30


def test_registry_covers_toplevel_structure(registry: AnchorRegistry) -> None:
    # Chapters 1-8 plus the unnumbered Release Notes are the spec's
    # top-level structure (experiments/uec/source/outline.json).
    assert registry.toplevel_sections() >= {str(n) for n in range(1, 9)} | {
        "Release Notes"
    }


def test_page_hashes_are_recomputable(registry: AnchorRegistry) -> None:
    # Recompute sha256 over the committed page files, independent of the
    # module's own verify(), then also cross-check against the extraction
    # manifest written by tools/uec_extract.py.
    manifest = yaml.safe_load(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    sha_by_page = {rec["page"]: rec["sha256"] for rec in manifest["pages"]}
    for anchor in registry.anchors:
        page_file = registry.page_path(anchor.page)
        digest = hashlib.sha256(page_file.read_bytes()).hexdigest()
        assert digest == anchor.page_sha256, anchor.anchor_id
        assert sha_by_page[anchor.page] == anchor.page_sha256, anchor.anchor_id


def test_quotes_are_verbatim_and_bounded(registry: AnchorRegistry) -> None:
    for anchor in registry.anchors:
        assert 0 < anchor.word_count() <= MAX_QUOTE_WORDS, anchor.anchor_id
        page_text = registry.page_path(anchor.page).read_text(encoding="utf-8")
        assert anchor.quote_in(page_text), anchor.anchor_id


def test_anchor_ids_unique(registry: AnchorRegistry) -> None:
    ids = [anchor.anchor_id for anchor in registry.anchors]
    assert len(ids) == len(set(ids))


def test_license_gate_matches_source_record(registry: AnchorRegistry) -> None:
    """S0 made permanent: registry pdf_sha256 == sha256 recorded for STD-UEC-11.

    The repo-level record (D-035 S2) carries the handoff csv row verbatim,
    so the structured hash must also appear unchanged inside the copied
    notes text — that keeps the copy honest, not paraphrased.
    """
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    assert record["source_id"] == "STD-UEC-11"
    assert record["access"] == "PUBLIC_READ"
    assert record["pdf_sha256"] in record["notes"]
    assert registry.source["pdf_sha256"] == record["pdf_sha256"]
    assert registry.source["source_id"] == record["source_id"]
    assert registry.source["url"] == record["url"]


# -- negative tests: integrity failures are hard errors ----------------------


def _synthetic_registry(tmp_path: Path) -> tuple[AnchorRegistry, Path]:
    pages = tmp_path / "pages"
    pages.mkdir()
    page_text = "5.2 Credit-based Flow Control\n\nCBFC is an alternative to the IEEE 802.3xx priority-based flow control. "
    (pages / "page_0650.txt").write_text(page_text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0650.txt").read_bytes()).hexdigest()
    entry = {
        "source": {
            "source_id": "SYNTH-1",
            "pdf_sha256": "0" * 64,
            "page_count": 1,
            "pages_dir": "unused",
        },
        "anchors": [
            {
                "id": "SYN-1",
                "section": "5.2",
                "title": "synthetic",
                "page": 650,
                "quote": "CBFC is an alternative to the IEEE 802.3xx priority-based flow control.",
                "page_sha256": digest,
            }
        ],
    }
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    reg = AnchorRegistry.load(registry_file, pages_dir=pages)
    reg.assert_valid()  # synthetic baseline is valid
    return reg, pages


def test_synthetic_registry_validates(tmp_path: Path) -> None:
    _synthetic_registry(tmp_path)


def test_dangling_page_hash_is_rejected(tmp_path: Path) -> None:
    reg, _ = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = Anchor(
        anchor_id=anchor.anchor_id,
        section=anchor.section,
        page=anchor.page,
        quote=anchor.quote,
        page_sha256="f" * 64,  # does not match the page file
        title=anchor.title,
    )
    bad = AnchorRegistry(reg.source, (tampered,), reg.registry_path, reg.pages_dir)
    with pytest.raises(AnchorRegistryError, match="sha256"):
        bad.assert_valid()
    assert any("sha256" in p for p in bad.verify())


def test_quote_not_on_page_is_rejected(tmp_path: Path) -> None:
    reg, _ = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = Anchor(
        anchor_id=anchor.anchor_id,
        section=anchor.section,
        page=anchor.page,
        quote="This sentence is nowhere in the extracted page.",
        page_sha256=anchor.page_sha256,
        title=anchor.title,
    )
    bad = AnchorRegistry(reg.source, (tampered,), reg.registry_path, reg.pages_dir)
    with pytest.raises(AnchorRegistryError, match="quote not found"):
        bad.assert_valid()


def test_missing_page_file_is_rejected(tmp_path: Path) -> None:
    reg, _ = _synthetic_registry(tmp_path)
    anchor = reg.anchors[0]
    tampered = Anchor(
        anchor_id=anchor.anchor_id,
        section=anchor.section,
        page=999,  # no such extracted page
        quote=anchor.quote,
        page_sha256=anchor.page_sha256,
        title=anchor.title,
    )
    bad = AnchorRegistry(reg.source, (tampered,), reg.registry_path, reg.pages_dir)
    with pytest.raises(AnchorRegistryError, match="missing page file"):
        bad.assert_valid()


def test_overlong_quote_is_rejected_by_shape() -> None:
    anchor = Anchor(
        anchor_id="SYN-LONG",
        section="5.2",
        page=650,
        quote=" ".join(["word"] * (MAX_QUOTE_WORDS + 1)),
        page_sha256="0" * 64,
    )
    assert any("words" in p for p in anchor.check_shape())


def test_resolve_rejects_dangling_anchor_ids(tmp_path: Path) -> None:
    reg, _ = _synthetic_registry(tmp_path)
    resolved = reg.resolve(["SYN-1"])
    assert resolved[0].anchor_id == "SYN-1"
    with pytest.raises(AnchorRegistryError, match="dangling anchor ids"):
        reg.resolve(["SYN-1", "UEC11-DOES-NOT-EXIST"])
