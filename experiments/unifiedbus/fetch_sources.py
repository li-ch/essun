#!/usr/bin/env python3
"""Fetch + deterministically extract the public UnifiedBus paper/post sources
(Q6 stage S1, ``experiments/unifiedbus/``).

Sources are PUBLIC papers and vendor engineering posts only (ladder honesty
rule: this is a paper-derived design profile, never a normative UnifiedBus
specification profile; the spec track stays license-gated under HUM-02/D-008).
The guard below refuses to fetch:

- any URL whose exact value is registered in
  ``experiments/unifiedbus/source_record.yaml`` (STD-UB rows copied
  verbatim from the handoff sources.csv at D-035 stage S2) with access
  other than ``PUBLIC_READ`` (e.g. STD-UB-LICENSE), and
- any other path on ``unifiedbus.com`` beyond the pre-cleared public rows
  (STD-UB-HOME ``/`` and its public English docs index ``/en``; STD-UB-OS
  ``/zh/software/ub-os-component``) — the specification documents hosted on
  that site are license-gated and are never fetched.

Raw bytes land in ``.cache/ub_sources/`` (git-ignored, like Q1's PDF);
committed artifacts are the extracted page text under
``experiments/unifiedbus/source/pages/<SOURCE_ID>/`` plus
``experiments/unifiedbus/source/source_manifest.yaml``. Extraction is
deterministic for a fixed raw document (stdlib HTMLParser, paragraph-boundary
chunking), so re-running on the same bytes is byte-identical (verified in the
stage report).

Re-run::

    .venv/bin/python experiments/unifiedbus/fetch_sources.py            # refetch
    .venv/bin/python experiments/unifiedbus/fetch_sources.py --offline  # re-extract from cached raw only
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
RAW_DIR = REPO_ROOT / ".cache/ub_sources"
SOURCE_DIR = REPO_ROOT / "experiments/unifiedbus/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
SOURCE_RECORD = REPO_ROOT / "experiments/unifiedbus/source_record.yaml"

#: Approximate extracted characters per pseudo-page (a PDF page of dense
#: text is ~4k chars; Q1's UEC pages average ~2.3k).
PAGE_CHAR_TARGET = 4000

#: Pre-cleared public unifiedbus.com paths. Everything else on that host is
#: treated as license-gated (specification family) and refused.
UNIFIEDBUS_HOST = "www.unifiedbus.com"
UNIFIEDBUS_PUBLIC_PATHS = {"/", "/en", "/zh/software/ub-os-component"}

# source_id -> metadata. handoff_row links a pre-cleared row in
# experiments/unifiedbus/source_record.yaml (verbatim copy of the
# historical handoff sources.csv rows, D-035 S2); found_via documents how
# a public follow-up source was located (ladder S1: "public rows +
# search").
SOURCES: list[dict[str, str]] = [
    {
        "source_id": "PUB-UB-UBMESH-25",
        "title": ("UB-Mesh: a Hierarchically Localized nD-FullMesh Datacenter "
                  "Network Architecture (v3)"),
        "url": "https://arxiv.org/html/2503.20377v3",
        "kind": "arxiv_html",
        "access": "PUBLIC_READ",
        "role": "Primary public paper: Unified Bus (UB) technique, 4D-FullMesh topology, LRS/HRS, APR routing, availability",
        "handoff_row": "",
        "found_via": "Public follow-up search for UnifiedBus; arXiv listing (v3 2025-05-17)",
        "notes": "arXiv HTML; raw bytes hashed at fetch time; not the UnifiedBus specification",
    },
    {
        "source_id": "PUB-UB-HUAWEI-HC26",
        "title": ("Huawei Unveils New UnifiedBus Computing Architecture for "
                  "SuperPoDs and Clusters (Huawei Connect 2026 news post)"),
        "url": "https://www.huawei.com/en/news/2026/9/hc-lingqu-agent-ai",
        "kind": "vendor_post",
        "access": "PUBLIC_READ",
        "role": "Vendor engineering post: SuperPoD scale, LinkBlade/LinkDevice/UBG numbers, RTT, memory semantics",
        "handoff_row": "",
        "found_via": "Public follow-up of the UnifiedBus ecosystem named via STD-UB-HOME; huawei.com newsroom",
        "notes": "Marketing/announcement post; numbers are vendor-claimed, labeled as such in the profile",
    },
    {
        "source_id": "PUB-UB-OSCOMP",
        "title": "UnifiedBus OS component overview (UB OS 组件, unifiedbus.com)",
        "url": "https://www.unifiedbus.com/zh/software/ub-os-component",
        "kind": "public_page",
        "access": "PUBLIC_READ",
        "role": "Official public page: UB protocol software surface (URMA, CDMA, UMMU, OBMM, device management)",
        "handoff_row": "STD-UB-OS",
        "found_via": "Pre-cleared public row STD-UB-OS in sources.csv",
        "notes": "Public component description page; NOT the license-gated specification",
    },
    {
        "source_id": "PUB-UB-DOCS-EN",
        "title": "UnifiedBus documentation index, English (unifiedbus.com/en)",
        "url": "https://www.unifiedbus.com/en",
        "kind": "public_page",
        "access": "PUBLIC_READ",
        "role": "Official public docs index: spec-family structure, Base Spec 2.1 public highlights (224/256 Gbit/s), SuperPoD architecture features",
        "handoff_row": "STD-UB-HOME",
        "found_via": ("Pre-cleared public row STD-UB-HOME (https://www.unifiedbus.com/) is a "
                      "client-rendered shell with no extractable text; /en is the same public "
                      "site's server-rendered English docs index"),
        "notes": ("Only the public index text is used; the linked specification documents "
                  "(Base/Firmware/Compatibility Test specs, gated by STD-UB-LICENSE) are "
                  "never fetched"),
    },
    {
        "source_id": "PUB-UB-NESTEDVN-26",
        "title": "Nested Parallel von Neumann Architecture and Nested BSP (v1)",
        "url": "https://arxiv.org/html/2609.16787v1",
        "kind": "arxiv_html",
        "access": "PUBLIC_READ",
        "role": "Public paper (same lead author): Unified Bus as end-to-end memory-semantic interconnect, peer equality",
        "handoff_row": "",
        "found_via": "Public follow-up search for UnifiedBus; arXiv listing (2026-09-15)",
        "notes": "Architecture-concept source; no bus link numbers expected here",
    },
]


class _TextExtractor(html.parser.HTMLParser):
    """Collect visible text, dropping script/style/noscript/svg/nav chrome."""

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
        # collapse line breaks inside paragraphs (HTML wraps); blank lines are
        # paragraph separators
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


def extract_text(raw: bytes) -> str:
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_source_record() -> list[dict[str, str]]:
    record = yaml.safe_load(SOURCE_RECORD.read_text(encoding="utf-8"))
    return record["sources"]


def license_guard(url: str) -> None:
    """Refuse gated/unreviewed URLs before any fetch (hard rule 3)."""
    rows = load_source_record()
    for row in rows:
        if row["url"].rstrip("/") == url.rstrip("/") and row["access"] != "PUBLIC_READ":
            raise SystemExit(
                f"license guard: refusing {url} — registered as {row['id']} with "
                f"access {row['access']} in the source record"
            )
    match = re.match(r"https?://([^/]+)(/[^?#]*)?", url)
    if not match:
        raise SystemExit(f"license guard: unparseable url {url}")
    host, path = match.group(1), match.group(2) or "/"
    if host == UNIFIEDBUS_HOST and path not in UNIFIEDBUS_PUBLIC_PATHS:
        raise SystemExit(
            f"license guard: {url} is on {UNIFIEDBUS_HOST} but not one of the "
            f"pre-cleared public paths {sorted(UNIFIEDBUS_PUBLIC_PATHS)} "
            "(the UnifiedBus specification family is license-gated)"
        )


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "essun-s1-source-fetch/1.0 (research provenance; contact: repo owner)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="re-extract from cached raw bytes only (no network)")
    args = parser.parse_args(argv)

    rows = load_source_record()
    by_id = {row["id"]: row for row in rows}
    for source in SOURCES:
        license_guard(source["url"])  # refuse-before-fetch, every run
        row = by_id.get(source["handoff_row"]) if source["handoff_row"] else None
        if row and row["access"] != "PUBLIC_READ":
            raise SystemExit(
                f"{source['source_id']}: source-record row "
                f"{source['handoff_row']} is not PUBLIC_READ"
            )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pages_root = SOURCE_DIR / "pages"
    manifest_sources: list[dict] = []

    for source in SOURCES:
        sid = source["source_id"]
        raw_path = RAW_DIR / f"{sid}.html"
        if args.offline:
            if not raw_path.is_file():
                raise SystemExit(f"--offline but raw fetch missing: {raw_path}")
            raw = raw_path.read_bytes()
        else:
            raw = fetch(source["url"])
            raw_path.write_bytes(raw)
        doc_sha = sha256_bytes(raw)
        text = extract_text(raw)
        pages = chunk_pages(text)
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
            "handoff_row": source["handoff_row"] or None,
            "access": source["access"],
            "role": source["role"],
            "found_via": source["found_via"],
            "kind": source["kind"],
            "raw_format": "html",
            "doc_sha256": doc_sha,
            "extractor": ("stdlib html.parser (skip script/style/noscript/svg; "
                          f"paragraph chunks ~{PAGE_CHAR_TARGET} chars)"),
            "page_count": len(pages),
            "pages_dir": f"experiments/unifiedbus/source/pages/{sid}",
            "notes": source["notes"],
        }
        # page records live in the per-source manifest section
        manifest_sources.append({**entry, "pages": page_records})
        print(f"{sid}: {len(pages)} pages, {len(text)} chars, doc sha256 {doc_sha[:12]}…")

    manifest = {
        "registry_family": "unifiedbus_public_papers",
        "honesty_note": ("Paper-derived design profile sources only (public papers "
                         "and vendor posts); the UnifiedBus specification track is "
                         "license-gated (HUM-02, D-008) and is never fetched"),
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
