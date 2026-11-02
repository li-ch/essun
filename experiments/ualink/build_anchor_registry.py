#!/usr/bin/env python3
"""Build ``experiments/ualink/anchor_registry.yaml`` (M5 worked example).

Mirrors ``experiments/unifiedbus/build_anchor_registry.py`` for the UALink
MEMBER-PUBLIC EXCERPT set: the curated list below is the reviewed editorial
content — one anchor per architecture-level fact or named feature the two
consortium-published public documents state.  These anchors exist to
exercise the whole ingestion pipeline on text that is legal to hold while
the HUM-02 license question is pending, so authorized specification text,
when it arrives, lands through the identical path.

Honesty rule (absolute): these are MEMBER-PUBLIC EXCERPT anchors — the
consortium's own public whitepaper (STD-UALINK-10-WP) and public technical
overview post (STD-UALINK-OVERVIEW), both PUBLIC_READ rows of the
license-gate source registry.  Nothing in this registry quotes the UALink
specification family (member-gated; STD-UALINK-COMMON20 is
APPROVAL_REQUIRED and was never fetched).  An excerpt figure is never a
normative value: the activation skeleton promotes nothing — every figure
below can only appear as a graded CANDIDATE under an explicit free
parameter in ``experiments/ualink/semantic_profile.yaml``.

Each quote is a verbatim (whitespace-normalized) substring of the extracted
page text, at most 30 whitespace-words AND at most 200 characters.  The
page is AUTO-LOCATED: the builder scans the source's pages in order and
records the first page containing the quote — verified mechanically before
the registry is written, so a hand-edited quote is a hard error.  (The
whitepaper PDF extraction preserves a few typographic ligatures as odd
glyphs, e.g. 'Ɵ' for 'ti'; quotes copy the extracted text EXACTLY, which
is what makes them re-matchable.)

Re-run after re-fetching/re-extracting::

    .venv/bin/python experiments/ualink/build_anchor_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "experiments/ualink/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/ualink/anchor_registry.yaml"

MAX_QUOTE_WORDS = 30
MAX_QUOTE_CHARS = 200

#: Categories kept closed; the builder rejects unknown ones.  The set is
#: the UnifiedBus registry's categories plus flit_format (the UALink
#: excerpts state flit/header sizes) minus the vendor-cost ones with no
#: UALink counterpart yet.
CATEGORIES = {
    "architecture",        # what the design IS (layer stack, PHY lineage)
    "link_scale",          # lane counts / rates / station bandwidth
    "flit_format",         # flit sizes, header sizes, payload bounds
    "flow_control",        # credit/flow-control mechanics (named or silent)
    "latency",             # latency figures/goals
    "memory_semantics",    # load/store/atomic + ordering + addressing
    "routing",             # routing identifiers and schemes
    "scale",               # endpoint/pod scale figures
    "security",            # UALinkSec scope
    "reliability",         # replay/error handling
    "performance",         # reported efficiency outcomes (context only)
    "manageability",       # pod management / scope boundaries
}

# (anchor_id, source_id, section, title, category, quote)
# Sections: the whitepaper and overview post are unnumbered documents, so
# "0" = front matter and "1" = the whole document (the UnifiedBus registry's
# convention for unnumbered sources); the title carries the real location.
# Quotes are verbatim from the extracted pages (whitespace-normalized).
ANCHORS: list[tuple[str, str, str, str, str, str]] = [
    # --- PUB-UAL-WP10: UALink 1.0 public whitepaper (11 PDF pages) --------
    ("UAL-WP10-1-DESIGN-GOALS", "PUB-UAL-WP10", "0",
     "Introduction: optimized for area, latency, power", "architecture",
     "UALink is designed to deliver scale‐up solutions, optimized for area, "
     "latency and power"),
    ("UAL-WP10-1-MEMSEMANTICS", "PUB-UAL-WP10", "0",
     "Introduction: memory semantics, direct read/write/atomic", "memory_semantics",
     "Reduced soŌware complexity using memory semanƟcs with direct read, "
     "write, atomic transacƟons"),
    ("UAL-WP10-2-LANE-DATA-RATE", "PUB-UAL-WP10", "1",
     "Overview: maximum data rate 200 GT/s per lane", "link_scale",
     "The UALink 1.0 specification supports a maximum data rate of 200 GT/s "
     "per lane."),
    ("UAL-WP10-2-SIGNALING-RATE", "PUB-UAL-WP10", "1",
     "Overview: 212.5 GT/s signaling incl. FEC overhead", "link_scale",
     "The signaling rate is higher at 212.5 GT/s to account for the "
     "bandwidth required by Ethernet Layer 1 for Forward Error Correction "
     "Code (FEC)"),
    ("UAL-WP10-2-LINK-WIDTHS", "PUB-UAL-WP10", "1",
     "Overview: x1 / x2 / x4 lane groupings", "link_scale",
     "UALink lanes can be configured into various groupings: a single‐lane "
     "Link (x1 Link), a dual‐lane Link (x2 Link), or a quad‐lane Link "
     "(x4 Link)."),
    ("UAL-WP10-2-STATION-800G", "PUB-UAL-WP10", "1",
     "Overview: Station = 4 lanes, 800 Gbps each TX and RX", "link_scale",
     "A group of four lanes constitutes a Station, offering a maximum "
     "bandwidth of 800 Gbps each in transmit (TX) and receive (RX) "
     "directions."),
    ("UAL-WP10-2-GOALS-FLOWCTRL", "PUB-UAL-WP10", "1",
     "Figure 2 goals: credit-based flow control (named feature)", "flow_control",
     "Credit‐Based Flow Control"),
    ("UAL-WP10-2-GOALS-VCS", "PUB-UAL-WP10", "1",
     "Figure 2 goals: virtual channels (named feature)", "routing",
     "Virtual Channels"),
    ("UAL-WP10-2-GOALS-RTT", "PUB-UAL-WP10", "1",
     "Figure 2 goals: req-to-resp RTT < 1 microsecond", "latency",
     "Req‐To‐Resp RTT < 1µs"),
    ("UAL-WP10-2-GOALS-CABLE", "PUB-UAL-WP10", "1",
     "Figure 2 goals: cable length < 4 meters", "link_scale",
     "cable length < 4 meters"),
    ("UAL-WP10-2-GOALS-ENDPOINTS", "PUB-UAL-WP10", "1",
     "Figure 2 goals: end points <= 1K", "scale",
     "end points <= 1K"),
    ("UAL-WP10-3-ULS-1024", "PUB-UAL-WP10", "1",
     "System: ULS switches connect up to 1024 endpoints", "scale",
     "UALink Switches (ULS) connect up to 1024 Accelerators or endpoints."),
    ("UAL-WP10-3-ROUTING-ID", "PUB-UAL-WP10", "1",
     "System: unique 10-bit routing identifier per accelerator", "routing",
     "Each Accelerator is assigned a unique 10‐bit routing identifier."),
    ("UAL-WP10-6-DL-FLITS", "PUB-UAL-WP10", "1",
     "DL: packs 64-byte TL flits into 640-byte flits", "flit_format",
     "The Data Link packs 64‐byte Flits from the transaction layer into "
     "640 Bytes Flits for the Physical Layer."),
    ("UAL-WP10-6-LLR-REPLAY", "PUB-UAL-WP10", "1",
     "DL: link-level replay on a 640-byte flit basis", "reliability",
     "The Link level replay is provided on a 640 Byte Flit basis."),
    ("UAL-WP10-6-CRC32", "PUB-UAL-WP10", "1",
     "DL: 32-bit CRC computed per 640-byte flit", "flit_format",
     "A 32‐bit CRC is computed, checked, and included as part of the 640 "
     "Byte Flit."),
    ("UAL-WP10-8-HEADER-SIZES", "PUB-UAL-WP10", "1",
     "TL: compressed request header 8B; write response and flow control 4B",
     "flit_format",
     "A compressed request header is 8 Bytes, and a compressed write "
     "response and flow control each are 4 Bytes."),
    ("UAL-WP10-8-PACK-EFFICIENCY", "PUB-UAL-WP10", "1",
     "TL: example packing efficiency 95.2% (20/21 flits)", "performance",
     "five write requests, five write completions, and one Flow Control "
     "packet are sent over 21 TL Flits achieving an efficiency of 95.2% "
     "(20/21)"),
    ("UAL-WP10-9-UALSEC", "PUB-UAL-WP10", "1",
     "Security: confidentiality plus optional integrity with replay protection",
     "security",
     "UALinkSec provides data confidentiality and optional data integrity "
     "(including replay protection)"),
    ("UAL-WP10-10-INTERPOD", "PUB-UAL-WP10", "1",
     "Manageability: inter-Pod communication not specified", "manageability",
     "inter‐Pod communication and control is not specified by the UALink "
     "specification"),
    ("UAL-WP10-11-LOADSTORE-1024", "PUB-UAL-WP10", "1",
     "Summary: load/store across a Pod of up to 1024 accelerators",
     "memory_semantics",
     "load/store operaƟons across an enƟre Pod of up to 1024 accelerators"),
    # --- PUB-UAL-OVERVIEW: official UALink 200G 1.0 technical overview -----
    ("UAL-OV-1-MEMSEMANTICS", "PUB-UAL-OVERVIEW", "1",
     "Features: memory semantics read/write/atomic", "memory_semantics",
     "Using memory semantics with read, write, and atomic operations, "
     "UALink ensures efficient data handling."),
    ("UAL-OV-1-COHERENCY-SW", "PUB-UAL-OVERVIEW", "1",
     "Features: software coherency, 64-256 byte transactions",
     "memory_semantics",
     "Coherency is maintained through software with transactions ranging "
     "from 64 to 256 bytes."),
    ("UAL-OV-1-ROUTING-1024", "PUB-UAL-OVERVIEW", "1",
     "Features: src/dst routing, 1024 endpoints now, 4096 future", "routing",
     "The simple source/destination-based routing can handle up to 1024 "
     "endpoints, with future releases potentially extending this to 4096 "
     "endpoints."),
    ("UAL-OV-1-ADDR-57BIT", "PUB-UAL-OVERVIEW", "1",
     "Features: vendor-defined 57-bit physical address space",
     "memory_semantics",
     "UALink utilizes a vendor-defined, 57-bit physical address space"),
    ("UAL-OV-1-ORDERING", "PUB-UAL-OVERVIEW", "1",
     "Features: ordered requests, unordered completions", "memory_semantics",
     "supports ordered request addresses from source to destination, "
     "though completions are not ordered"),
    ("UAL-OV-1-HOST-FENCE", "PUB-UAL-OVERVIEW", "1",
     "Features: host CPU may not access remote-node memory",
     "memory_semantics",
     "a host CPU may not access memory attached to a remote system node"),
    ("UAL-OV-1-STATION-800G", "PUB-UAL-OVERVIEW", "1",
     "Station: four UALink lanes, max 800 Gb/s in v1.0", "link_scale",
     "A UALink station is defined as a group of four UALink lanes, "
     "supporting a maximum of 800 Gb/s traffic in v1.0."),
    ("UAL-OV-2-TL-CREDITS", "PUB-UAL-OVERVIEW", "1",
     "Stack: TL manages the credits", "flow_control",
     "The Transaction Layer (TL) manages the credits and handles the "
     "packing and unpacking of the TL flits."),
    ("UAL-OV-2-PHY-8023DJ", "PUB-UAL-OVERVIEW", "1",
     "Stack: PHY based on the IEEE P802.3dj draft standard", "architecture",
     "The Physical (PHY) Layer includes the Physical Coding Sublayer (PCS) "
     "and is based on the IEEE P802.3dj draft standard."),
]


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    src_meta = {rec["source_id"]: rec for rec in manifest["sources"]}
    sha_by_sid_page: dict[str, dict[int, str]] = {
        rec["source_id"]: {p["page"]: p["sha256"] for p in rec["pages"]}
        for rec in manifest["sources"]
    }
    page_text_cache: dict[tuple[str, int], str] = {}

    def page_text(sid: str, page: int) -> str:
        key = (sid, page)
        if key not in page_text_cache:
            path = SOURCE_DIR / "pages" / sid / f"page_{page:04d}.txt"
            if not path.is_file():
                raise SystemExit(f"missing extracted page {path}")
            page_text_cache[key] = path.read_text(encoding="utf-8")
        return page_text_cache[key]

    problems: list[str] = []
    seen_ids: set[str] = set()
    entries = []
    for anchor_id, sid, section, title, category, quote in ANCHORS:
        if anchor_id in seen_ids:
            problems.append(f"{anchor_id}: duplicate id")
        seen_ids.add(anchor_id)
        if sid not in src_meta:
            problems.append(f"{anchor_id}: unknown source_id {sid}")
            continue
        if category not in CATEGORIES:
            problems.append(f"{anchor_id}: unknown category {category!r}")
        n_words = len(quote.split())
        if n_words > MAX_QUOTE_WORDS:
            problems.append(f"{anchor_id}: quote exceeds {MAX_QUOTE_WORDS} words")
        if len(quote) > MAX_QUOTE_CHARS:
            problems.append(f"{anchor_id}: quote exceeds {MAX_QUOTE_CHARS} chars")
        # auto-locate: first page of this source containing the quote
        located = None
        for page in sorted(sha_by_sid_page[sid]):
            if normalize_ws(quote) in normalize_ws(page_text(sid, page)):
                located = page
                break
        if located is None:
            problems.append(f"{anchor_id}: quote not found in any page of {sid}")
            continue
        entries.append({
            "id": anchor_id,
            "source_id": sid,
            "section": section,
            "title": title,
            "category": category,
            "page": located,
            "quote": normalize_ws(quote),
            "page_sha256": sha_by_sid_page[sid][located],
        })

    if problems:
        for line in problems:
            print(f"error: {line}", file=sys.stderr)
        return 1

    sources_out = [
        {k: v for k, v in rec.items() if k != "pages"} for rec in manifest["sources"]
    ]
    registry = {
        "registry_family": "ualink_member_public_excerpts",
        "honesty_note": (
            "MEMBER-PUBLIC EXCERPT anchors only: the UALink Consortium's own "
            "public whitepaper (STD-UALINK-10-WP) and public 200G technical "
            "overview (STD-UALINK-OVERVIEW), both PUBLIC_READ rows of the "
            "license-gate source registry. The UALink specification family is "
            "member-gated (STD-UALINK-COMMON20 APPROVAL_REQUIRED, HUM-02 "
            "pending) and was never fetched. An excerpt figure is never a "
            "normative value: the activation skeleton interprets nothing and "
            "promotes nothing."
        ),
        "sources": sources_out,
        "anchors": entries,
    }
    REGISTRY_PATH.write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    by_sid: dict[str, int] = {}
    cats: dict[str, int] = {}
    for e in entries:
        by_sid[e["source_id"]] = by_sid.get(e["source_id"], 0) + 1
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    print(f"wrote {REGISTRY_PATH.relative_to(REPO_ROOT)}: {len(entries)} anchors")
    for sid, count in by_sid.items():
        print(f"  {sid}: {count} anchors")
    print(f"  categories: {dict(sorted(cats.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
