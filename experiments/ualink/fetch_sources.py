#!/usr/bin/env python3
"""Fetch + deterministically extract the UALink MEMBER-PUBLIC excerpts (M5).

The UALink specification documents (Common 2.0 Evaluation Copy and the
DL/PL, Manageability, Chiplet family) are MEMBER-GATED; the pending license
question is HUM-02 and no answer exists yet.  License review precedes
ingestion (workspace rule 3), so this script NEVER touches the gated track:
it fetches only MEMBER-PUBLIC excerpts — documents the consortium itself
publishes for the public — whose rows in ``experiments/ualink/source_record.yaml``
(verbatim copies of the license-gate source registry) carry
``access: PUBLIC_READ``:

- PUB-UAL-WP10: the UALink 1.0 public whitepaper (STD-UALINK-10-WP; PDF,
  real pages, pypdf extraction like ``tools/uec_extract.py``);
- PUB-UAL-OVERVIEW: the official UALink 200G 1.0 technical overview blog
  post (STD-UALINK-OVERVIEW; HTML, pseudo-page chunking like
  ``experiments/unifiedbus/fetch_sources.py``).

The guard refuses BEFORE any fetch, every run:

- any URL whose exact value is registered in the source record with access
  other than PUBLIC_READ (e.g. STD-UALINK-COMMON20, the evaluation-copy
  page — even the license page itself is not fetched), and
- any other path on ``ualinkconsortium.org`` beyond the two pre-cleared
  excerpt URLs above — the specification family hosted on that site is
  member-gated and is never fetched, whatever its URL shape.

These two excerpts exist to exercise the whole ingestion pipeline
(fetch -> sha-pinned extraction -> anchored quotes -> registry) on text
that is legal to hold TODAY, so that authorized specification text, when
HUM-02 is answered, lands through the identical path in one work session
(see ``experiments/ualink/ACTIVATION.md``).  They are architecture-level
member-public documents, NOT the specification: the activation skeleton
interprets nothing from them (zero requirements; every number they state
stays a graded CANDIDATE under an explicit free parameter).

Raw bytes land in ``.cache/ualink_sources/`` (git-ignored, like Q1's PDF);
committed artifacts are the extracted page text under
``experiments/ualink/source/pages/<SOURCE_ID>/`` plus
``experiments/ualink/source/source_manifest.yaml``.  Extraction is
deterministic for fixed raw bytes: PDF pages via pypdf (no timestamps
recorded), HTML via the stdlib parser with paragraph-boundary chunking.

Re-run::

    .venv/bin/python experiments/ualink/fetch_sources.py            # refetch
    .venv/bin/python experiments/ualink/fetch_sources.py --offline  # re-extract from cached raw only
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import re
import sys
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / ".cache/ualink_sources"
SOURCE_DIR = REPO_ROOT / "experiments/ualink/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
SOURCE_RECORD = REPO_ROOT / "experiments/ualink/source_record.yaml"

#: Approximate extracted characters per pseudo-page for HTML sources (a
#: PDF page of dense text is ~4k chars; mirrors the UnifiedBus S1 choice).
PAGE_CHAR_TARGET = 4000

#: The consortium's host.  Every path on it EXCEPT the two pre-cleared
#: excerpt paths below is treated as member-gated specification family and
#: refused before fetch.
UALINK_HOST = "ualinkconsortium.org"
UALINK_PUBLIC_PATHS = {
    "/wp-content/uploads/2025/04/UALink-1.0-White_Paper_FINAL.pdf",
    "/blog/ualink-200g-1-0-specification-overview-802/",
}

# source_id -> metadata.  handoff_row links a row in
# experiments/ualink/source_record.yaml (verbatim copy of the license-gate
# source registry); both cited rows are PUBLIC_READ.
SOURCES: list[dict[str, str]] = [
    {
        "source_id": "PUB-UAL-WP10",
        "title": "UALink 1.0 public whitepaper",
        "url": "https://ualinkconsortium.org/wp-content/uploads/2025/04/UALink-1.0-White_Paper_FINAL.pdf",
        "kind": "pdf",
        "raw_format": "pdf",
        "access": "PUBLIC_READ",
        "role": "Member-public architecture excerpt: UALink 1.0 design targets, protocol stack shape, memory-operation classes",
        "handoff_row": "STD-UALINK-10-WP",
        "found_via": "Pre-cleared PUBLIC_READ row STD-UALINK-10-WP in the license-gate source registry",
        "notes": "Consortium-published whitepaper; NOT the specification (registry row: 'Not full specification')",
    },
    {
        "source_id": "PUB-UAL-OVERVIEW",
        "title": "Official UALink 200G 1.0 technical overview (consortium blog)",
        "url": "https://ualinkconsortium.org/blog/ualink-200g-1-0-specification-overview-802/",
        "kind": "public_page",
        "raw_format": "html",
        "access": "PUBLIC_READ",
        "role": "Member-public technical excerpt: 200G signaling-rate context, layer structure at overview level",
        "handoff_row": "STD-UALINK-OVERVIEW",
        "found_via": "Pre-cleared PUBLIC_READ row STD-UALINK-OVERVIEW in the license-gate source registry",
        "notes": "Official blog overview; registry row says 'Verify against authorized specification' — it is cross-check grade, never a normative source",
    },
]


class _TextExtractor(html.parser.HTMLParser):
    """Collect visible text, dropping script/style/noscript/svg chrome."""

    _SKIP = {"script", "style", "noscript", "svg", "template"}
    _BLOCK = {"p", "div", "section", "article", "li", "tr", "table",
              "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "figcaption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._chunks.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self._chunks.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
        out: list[str] = []
        buf: list[str] = []
        for ln in lines:
            if ln:
                buf.append(ln)
            elif buf:
                out.append(" ".join(buf))
                buf = []
        if buf:
            out.append(" ".join(buf))
        return "\n\n".join(out) + "\n"


def extract_html_text(raw: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return parser.text()


def chunk_pages(text: str, target: int = PAGE_CHAR_TARGET) -> list[str]:
    """Split extracted text into pseudo-pages at paragraph boundaries."""
    paragraphs = text.split("\n\n")
    pages: list[str] = []
    current: list[str] = []
    size = 0
    for para in paragraphs:
        current.append(para)
        size += len(para)
        if size >= target:
            pages.append("\n\n".join(current) + "\n")
            current, size = [], 0
    if current:
        pages.append("\n\n".join(current) + "\n")
    return pages


def extract_pdf_pages(raw: bytes) -> tuple[list[str], str]:
    """One text page per PDF page, pypdf, deterministic for fixed bytes."""
    import io

    from pypdf import PdfReader
    from pypdf import __version__ as pypdf_version

    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise SystemExit("license guard: refusing an encrypted PDF (unexpected for a member-public excerpt)")
    pages = [(page.extract_text() or "") + "\n" for page in reader.pages]
    return pages, pypdf_version


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_source_record() -> list[dict[str, str]]:
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    return record["sources"]


def license_guard(url: str) -> None:
    """Refuse gated/unreviewed URLs before any fetch (hard rule 3).

    Two fences, both checked on every run for every source:

    1. the URL must not equal a registered non-PUBLIC_READ row (the HUM-02
       gated track, e.g. STD-UALINK-COMMON20 — the evaluation-copy page);
    2. if it is on the consortium host, it must be one of the pre-cleared
       member-public excerpt paths (UALINK_PUBLIC_PATHS); anything else on
       that host is specification family and is refused.
    """
    rows = load_source_record()
    for row in rows:
        if row["url"].rstrip("/") == url.rstrip("/") and row["access"] != "PUBLIC_READ":
            raise SystemExit(
                f"license guard: refusing {url} — registered as {row['id']} with "
                f"access {row['access']} in the source record (HUM-02 pending)"
            )
    match = re.match(r"https?://([^/]+)(/[^?#]*)?", url)
    if not match:
        raise SystemExit(f"license guard: unparseable url {url}")
    host, path = match.group(1), match.group(2) or "/"
    if host == UALINK_HOST and path not in UALINK_PUBLIC_PATHS:
        raise SystemExit(
            f"license guard: {url} is on {UALINK_HOST} but not one of the "
            f"pre-cleared member-public excerpt paths {sorted(UALINK_PUBLIC_PATHS)} "
            "(the UALink specification family is member-gated; HUM-02 pending)"
        )


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "essun-m5-source-fetch/1.0 (research provenance; contact: repo owner)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true",
                        help="re-extract from cached raw bytes only (no network)")
    args = parser.parse_args(argv)

    rows = load_source_record()
    by_id = {row["id"]: row for row in rows}
    for source in SOURCES:
        license_guard(source["url"])  # refuse-before-fetch, every run
        row = by_id[source["handoff_row"]]
        if row["url"].rstrip("/") != source["url"].rstrip("/"):
            raise SystemExit(
                f"{source['source_id']}: url drift vs source-record row "
                f"{source['handoff_row']} ({row['url']})"
            )
        if row["access"] != "PUBLIC_READ":
            raise SystemExit(
                f"{source['source_id']}: source-record row "
                f"{source['handoff_row']} is not PUBLIC_READ"
            )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pages_root = SOURCE_DIR / "pages"
    manifest_sources: list[dict] = []

    for source in SOURCES:
        sid = source["source_id"]
        suffix = "pdf" if source["raw_format"] == "pdf" else "html"
        raw_path = RAW_DIR / f"{sid}.{suffix}"
        if args.offline:
            if not raw_path.is_file():
                raise SystemExit(f"--offline but raw fetch missing: {raw_path}")
            raw = raw_path.read_bytes()
        else:
            raw = fetch(source["url"])
            raw_path.write_bytes(raw)
        doc_sha = sha256_bytes(raw)
        if source["kind"] == "pdf":
            pages, extractor_version = extract_pdf_pages(raw)
            extractor = f"pypdf {extractor_version} (one page per PDF page; no timestamps)"
            chunking = "pdf-pages"
        else:
            text = extract_html_text(raw)
            pages = chunk_pages(text)
            extractor = ("stdlib html.parser (skip script/style/noscript/svg; "
                         f"paragraph chunks ~{PAGE_CHAR_TARGET} chars)")
            chunking = f"paragraph-chunks~{PAGE_CHAR_TARGET}"
        page_dir = pages_root / sid
        page_dir.mkdir(parents=True, exist_ok=True)
        page_records = []
        for number, page_text in enumerate(pages, start=1):
            name = f"page_{number:04d}.txt"
            (page_dir / name).write_text(page_text, encoding="utf-8")
            page_records.append({
                "page": number,
                "file": f"pages/{sid}/{name}",
                "sha256": sha256_bytes((page_dir / name).read_bytes()),
                "chars": len(page_text),
            })
        entry = {
            "source_id": sid,
            "title": source["title"],
            "url": source["url"],
            "handoff_row": source["handoff_row"],
            "access": source["access"],
            "role": source["role"],
            "found_via": source["found_via"],
            "kind": source["kind"],
            "raw_format": source["raw_format"],
            "doc_sha256": doc_sha,
            "extractor": extractor,
            "page_count": len(pages),
            "pages_dir": f"experiments/ualink/source/pages/{sid}",
            "chunking": chunking,
            "notes": source["notes"],
        }
        manifest_sources.append({**entry, "pages": page_records})
        print(f"{sid}: {len(pages)} pages, doc sha256 {doc_sha[:12]}…")

    manifest = {
        "registry_family": "ualink_member_public_excerpts",
        "honesty_note": ("Member-public excerpt sources only (the consortium's own "
                         "public whitepaper and technical overview). The UALink "
                         "specification family is member-gated (HUM-02 pending, "
                         "STD-UALINK-COMMON20 APPROVAL_REQUIRED) and is never "
                         "fetched. Nothing here is normative input."),
        "sources": manifest_sources,
    }
    MANIFEST_PATH.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} ({len(manifest_sources)} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
