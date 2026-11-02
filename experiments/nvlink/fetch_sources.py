#!/usr/bin/env python3
"""Fetch + deterministically extract the public NVLink-class paper/page sources
(M1, ``experiments/nvlink/``).

Sources are PUBLIC papers and public pages only (the same rule as the
UnifiedBus paper-derived profile): this is a paper-derived design profile of
the NVLink-class scale-up family, never a normative NVLink/NVSwitch
specification profile — no public specification document exists (the
specification track is proprietary, licensee/NDA-gated; see
``experiments/nvlink/source_record.yaml`` row STD-NV-SPEC).  The guard below
refuses to fetch:

- any URL registered in the source record with access other than
  ``PUBLIC_READ`` (STD-NV-SPEC), and
- any other path on the NVIDIA vendor hosts (nvidia.com, docs.nvidia.com,
  developer.nvidia.com) beyond the pre-cleared public rows — the vendor's
  partner/licensee material must never enter this pipeline uninvited.

Raw bytes land in ``.cache/nv_sources/`` (git-ignored); committed artifacts
are the extracted page text under
``experiments/nvlink/source/pages/<SOURCE_ID>/`` plus
``experiments/nvlink/source/source_manifest.yaml``.  Extraction is
deterministic for a fixed raw document: HTML via stdlib HTMLParser with
paragraph-boundary chunking (~4000-char pseudo-pages, exactly the UnifiedBus
S1 extractor); PDF via pypdf (one PDF page = one pseudo-page; the extractor
and pypdf version are recorded in the manifest).

Re-run::

    .venv/bin/python experiments/nvlink/fetch_sources.py            # refetch
    .venv/bin/python experiments/nvlink/fetch_sources.py --offline  # re-extract from cached raw only
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import re
import sys
import urllib.request
from pathlib import Path

import pypdf
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / ".cache/nv_sources"
SOURCE_DIR = REPO_ROOT / "experiments/nvlink/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
SOURCE_RECORD = REPO_ROOT / "experiments/nvlink/source_record.yaml"

#: Approximate extracted characters per pseudo-page for HTML sources (a PDF
#: page of dense text is ~4k chars; one PDF page is one pseudo-page below).
PAGE_CHAR_TARGET = 4000

#: Vendor hosts whose every non-pre-cleared path is treated as potentially
#: licensee/partner material and refused (specification-track fence).
NVIDIA_HOSTS = ("www.nvidia.com", "nvidia.com", "docs.nvidia.com", "developer.nvidia.com")

#: Pre-cleared public NVIDIA paths (the two PUBLIC_READ vendor rows).
NVIDIA_PUBLIC_PATHS = {
    ("docs.nvidia.com", "/dgx/dgxgb200-user-guide/hardware.html"),
    ("www.nvidia.com", "/en-us/data-center/gb200-nvl72/"),
}

# source_id -> metadata.  handoff_row links a pre-cleared row in
# experiments/nvlink/source_record.yaml; found_via documents how a public
# follow-up source was located.
SOURCES: list[dict[str, str]] = [
    {
        "source_id": "PUB-NV-LI-TPDS19",
        "title": (
            "Evaluating Modern GPU Interconnect: PCIe, NVLink, NV-SLI, "
            "NVSwitch and GPUDirect (IEEE TPDS 2019; arXiv:1903.04611)"
        ),
        "url": "https://arxiv.org/html/1903.04611",
        "kind": "arxiv_html",
        "access": "PUBLIC_READ",
        "role": (
            "Primary public paper: measured NVLink-V1/V2 and NVSwitch P2P "
            "latency/bandwidth, DGX-1/DGX-2 topologies, NVSwitch crossbar "
            "structure, NUMA effects"
        ),
        "handoff_row": "PUB-NV-LI-TPDS19",
        "found_via": (
            "Calibration anchor staging (docs/calibration/anchors_staging.md "
            "additional candidates, Li et al. TPDS 2019); arXiv native HTML"
        ),
        "notes": (
            "arXiv HTML of the TPDS paper; raw bytes hashed at fetch time; "
            "the only public MEASURED latency/bandwidth microbenchmarks of "
            "this family in the source set"
        ),
    },
    {
        "source_id": "PUB-NV-TPU4-ICI23",
        "title": (
            "TPU v4: An Optically Reconfigurable Supercomputer for Machine "
            "Learning with Hardware Support for Embeddings (ISCA 2023; "
            "arXiv:2304.01433)"
        ),
        "url": "https://arxiv.org/pdf/2304.01433",
        "kind": "arxiv_pdf",
        "access": "PUBLIC_READ",
        "role": (
            "Class-member public paper: TPU v4 ICI link specs, 3D torus + "
            "OCS, twisted-torus measurements, and the paper's own NVSwitch "
            "characterization"
        ),
        "handoff_row": "PUB-NV-TPU4-ICI23",
        "found_via": (
            "Calibration anchor CAL-A5 (docs/calibration/anchors_staging.md "
            "A5); no arXiv HTML exists for 2304.04133-era submissions, so "
            "the public arXiv PDF is the fetched form"
        ),
        "notes": (
            "The independent (non-NVIDIA) member of the NVLink-class "
            "family; parameters drawn from it describe TPU ICI, never "
            "NVIDIA hardware, and say so in their names"
        ),
    },
    {
        "source_id": "PUB-NV-GB200-UG",
        "title": (
            "Hardware - NVIDIA DGX GB Rack Scale Systems User Guide "
            "(NVLink switch section)"
        ),
        "url": "https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html",
        "kind": "vendor_doc_page",
        "access": "PUBLIC_READ",
        "role": (
            "Vendor official documentation page: NVLink5 switch chip "
            "capacity/ports, switch trays, rack composition"
        ),
        "handoff_row": "STD-NV-GB200-UG",
        "found_via": "Calibration anchor CAL-A1 (anchors_staging.md A1)",
        "notes": (
            "Official docs page; figures are vendor spec claims, labeled "
            "VENDOR_CLAIMED in the profile"
        ),
    },
    {
        "source_id": "PUB-NV-GB200-NVL72",
        "title": "NVIDIA GB200 NVL72 product page",
        "url": "https://www.nvidia.com/en-us/data-center/gb200-nvl72/",
        "kind": "vendor_product_page",
        "access": "PUBLIC_READ",
        "role": (
            "Vendor product page: 72-GPU NVLink domain, per-GPU and "
            "aggregate NVLink5 bandwidth figures"
        ),
        "handoff_row": "STD-NV-GB200-NVL72",
        "found_via": "Calibration anchor CAL-A2 (anchors_staging.md A2)",
        "notes": (
            "Marketing page; every figure is a vendor claim (VENDOR_CLAIMED), "
            "spec ceilings rather than measurements"
        ),
    },
    {
        "source_id": "PUB-NV-NCCL-1054",
        "title": (
            "NVIDIA/nccl issue #1054: The total nvlink bandwidth obtained "
            "by NCCL topo is not the actual total bandwidth"
        ),
        "url": "https://github.com/NVIDIA/nccl/issues/1054",
        "kind": "project_tracker_page",
        "access": "PUBLIC_READ",
        "role": (
            "NCCL project public tracker: the library's internal NVLink "
            "bandwidth model (20 GB/s per link) and the app-level ~80% "
            "derating, maintainer reply on the record"
        ),
        "handoff_row": "PUB-NV-NCCL-1054",
        "found_via": "Calibration anchor CAL-A12 (anchors_gapfill.md; issue #1054)",
        "notes": (
            "Official public page of the NCCL project (the reference "
            "communication stack for this fabric family); community issue "
            "body plus maintainer answer, carried OFFICIAL_PUBLIC_PAGE"
        ),
    },
]


class _TextExtractor(html.parser.HTMLParser):
    """Collect visible text, dropping script/style/noscript/svg chrome.

    Byte-identical to the UnifiedBus S1 extractor
    (experiments/unifiedbus/fetch_sources.py) so HTML provenance has one
    deterministic shape across paper-derived families.
    """

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


def extract_html(raw: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return parser.text()


def extract_pdf_pages(raw: bytes) -> list[str]:
    """One PDF page = one pseudo-page (pypdf text extraction, recorded)."""
    import io

    reader = pypdf.PdfReader(io.BytesIO(raw))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        # normalize intra-page whitespace exactly like the HTML path's line
        # collapsing so quote matching has one convention
        lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n")]
        body = "\n".join(ln for ln in lines if ln)
        pages.append(body + "\n" if body else "\n")
    return pages


def chunk_pages(text: str, target: int = PAGE_CHAR_TARGET) -> list[str]:
    """Split extracted HTML text into pseudo-pages at paragraph boundaries."""
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
    if host in NVIDIA_HOSTS and (host, path) not in NVIDIA_PUBLIC_PATHS:
        raise SystemExit(
            f"license guard: {url} is on vendor host {host} but not one of "
            f"the pre-cleared public paths {sorted(NVIDIA_PUBLIC_PATHS)} "
            "(the NVLink/NVSwitch specification track is licensee-gated; "
            "only registered public rows may be fetched)"
        )


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "essun-m1-source-fetch/1.0 (research provenance; contact: repo owner)"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
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
        suffix = "pdf" if source["kind"] == "arxiv_pdf" else "html"
        raw_path = RAW_DIR / f"{sid}.{suffix}"
        if args.offline:
            if not raw_path.is_file():
                raise SystemExit(f"--offline but raw fetch missing: {raw_path}")
            raw = raw_path.read_bytes()
        else:
            raw = fetch(source["url"])
            raw_path.write_bytes(raw)
        doc_sha = sha256_bytes(raw)

        if source["kind"] == "arxiv_pdf":
            pages = extract_pdf_pages(raw)
            extractor = f"pypdf {pypdf.__version__} page.extract_text (one PDF page = one page)"
        else:
            pages = chunk_pages(extract_html(raw))
            extractor = (
                "stdlib html.parser (skip script/style/noscript/svg; "
                f"paragraph chunks ~{PAGE_CHAR_TARGET} chars)"
            )

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
            "raw_format": "pdf" if source["kind"] == "arxiv_pdf" else "html",
            "doc_sha256": doc_sha,
            "extractor": extractor,
            "page_count": len(pages),
            "pages_dir": f"experiments/nvlink/source/pages/{sid}",
            "notes": source["notes"],
        }
        manifest_sources.append({**entry, "pages": page_records})
        print(f"{sid}: {len(pages)} pages, doc sha256 {doc_sha[:12]}…")

    manifest = {
        "registry_family": "nvlink_class_public_papers",
        "honesty_note": (
            "Paper-derived NVLink-class profile sources only (public papers "
            "and public pages); no public NVLink/NVSwitch specification "
            "exists — the specification track is licensee/NDA-gated "
            "(STD-NV-SPEC) and was never fetched"
        ),
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
