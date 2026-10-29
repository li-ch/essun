#!/usr/bin/env python3
"""Extract the UEC 1.1 specification text for source-anchored ingest.

License gate is enforced mechanically: the PDF's sha256 must equal the value
recorded for ``STD-UEC-11`` in ``experiments/uec/source_record.yaml``
(copied verbatim from the license-gate source registry) before
any text is read. The PDF itself never enters git (see .gitignore);
only the extracted per-page text, a deterministic per-page manifest and the
bookmark outline are written under ``experiments/uec/source/``.

Usage::

    .venv/bin/python tools/uec_extract.py \
        --pdf .cache/standards/UE-Specification-1.1.pdf

Output is deterministic for a given (pdf, pypdf) pair: no timestamps are
recorded, so re-extraction reproduces byte-identical files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml
from pypdf import PdfReader
from pypdf import __version__ as PYPDF_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]

# Provenance recorded in experiments/uec/source_record.yaml (STD-UEC-11,
# verbatim copy of the license-gate source-registry row.
SOURCE_ID = "STD-UEC-11"
SOURCE_TITLE = "Ultra Ethernet Specification 1.1"
SOURCE_URL = (
    "https://ultraethernet.org/wp-content/uploads/sites/20/2026/10/"
    "UE-Specification-1.1.pdf"
)
EXPECTED_PDF_SHA256 = (
    "4c8436ec7daa627ad6cce0680bea66cfac496dfe4e217631064e68acafe04531"
)
EXPECTED_PAGE_COUNT = 764

DEFAULT_PDF = REPO_ROOT / ".cache/standards/UE-Specification-1.1.pdf"
DEFAULT_OUT_DIR = REPO_ROOT / "experiments/uec/source"


class ExtractionError(Exception):
    """Raised when the license gate or extraction consistency checks fail."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def flatten_outline(reader: PdfReader, items: list, level: int = 0) -> list[dict]:
    flat: list[dict] = []
    for item in items:
        if isinstance(item, list):
            flat.extend(flatten_outline(reader, item, level + 1))
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except Exception:  # pragma: no cover - malformed bookmark targets
            page = None
        flat.append({"title": str(item.title), "page": page, "level": level})
    return flat


def extract(pdf_path: Path, out_dir: Path) -> dict:
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    digest = sha256_bytes(pdf_path.read_bytes())
    if digest != EXPECTED_PDF_SHA256:
        raise ExtractionError(
            f"license gate failed: sha256 {digest} != recorded "
            f"{EXPECTED_PDF_SHA256} for {SOURCE_ID}; refusing to extract"
        )

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        raise ExtractionError("PDF is encrypted; unexpected for STD-UEC-11")
    page_count = len(reader.pages)
    if page_count != EXPECTED_PAGE_COUNT:
        raise ExtractionError(
            f"page count {page_count} != recorded {EXPECTED_PAGE_COUNT} "
            f"for {SOURCE_ID}"
        )

    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_records: list[dict] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        payload = text.encode("utf-8")
        (pages_dir / f"page_{index:04d}.txt").write_bytes(payload)
        page_records.append(
            {
                "page": index,
                "file": f"pages/page_{index:04d}.txt",
                "sha256": sha256_bytes(payload),
                "chars": len(text),
            }
        )

    outline = flatten_outline(reader, reader.outline)
    (out_dir / "outline.json").write_text(
        json.dumps(outline, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "source": {
            "source_id": SOURCE_ID,
            "title": SOURCE_TITLE,
            "url": SOURCE_URL,
            "access": "PUBLIC_READ",
            "pdf_sha256": digest,
            "page_count": page_count,
            "extractor": f"pypdf {PYPDF_VERSION}",
            "notes": (
                "PDF kept out of git (.cache/); CC BY-ND scope: quotes in the "
                "anchor registry are <= 30 words with attribution, no "
                "redistribution of the document itself"
            ),
        },
        "pages": page_records,
    }
    (out_dir / "source_manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    try:
        manifest = extract(args.pdf, args.out_dir)
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    total_chars = sum(rec["chars"] for rec in manifest["pages"])
    print(
        f"extracted {manifest['source']['source_id']}: "
        f"{manifest['source']['page_count']} pages, {total_chars} chars -> "
        f"{args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
