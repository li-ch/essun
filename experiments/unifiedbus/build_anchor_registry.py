#!/usr/bin/env python3
"""Build ``experiments/unifiedbus/anchor_registry.yaml`` (Q6 stage S1).

Mirrors ``experiments/uec/build_anchor_registry.py`` (Q1) for a MULTI-source
public-paper registry: the curated list below is the reviewed editorial
content — one anchor per design-relevant claim a UnifiedBus-class profile
needs (architecture, topology, link scale, routing, reliability/availability,
memory semantics, latency, software surface, scale, cost/availability).

Honesty rule (absolute, from the ladder prompt): these are PAPER-DERIVED
anchors from public papers and vendor engineering posts, NOT a normative
UnifiedBus specification profile; the specification track stays license-gated
(HUM-02, D-008). Nothing in this registry may quote the UnifiedBus
specification documents.

Each quote is a verbatim (whitespace-normalized) substring of the extracted
page text, at most 30 whitespace-words AND at most 200 characters (Chinese
text packs more content per word). Unlike Q1 (PDF page numbers known from the
outline), the page is AUTO-LOCATED: the builder scans the source's pages in
order and records the first page containing the quote — verified mechanically
before the registry is written, so a hand-edited quote is a hard error.

Re-run after re-fetching/re-extracting::

    .venv/bin/python experiments/unifiedbus/build_anchor_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "experiments/unifiedbus/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/unifiedbus/anchor_registry.yaml"

MAX_QUOTE_WORDS = 30
MAX_QUOTE_CHARS = 200

#: Categories consumed by S2 (design parameters), S3 (platform mapping) and
#: S4 (UEC-vs-UB comparison). Kept closed; the builder rejects unknown ones.
CATEGORIES = {
    "architecture",        # what the design IS (protocol family, peer model)
    "topology",            # topology class and construction
    "link_scale",          # link counts / widths / bandwidth figures
    "latency",             # latency figures
    "memory_semantics",    # load/store/atomic + memory addressing behavior
    "routing",             # routing / flow control mechanics
    "reliability",         # redundancy and failure behavior
    "availability",        # measured/derived availability, MTBF, MTTR
    "performance",         # measured performance outcomes (context only)
    "software",            # host software/programming surface
    "scale",               # endpoint/rack/pod/cluster scale figures
    "workload_locality",   # traffic locality evidence motivating the design
}

# (anchor_id, source_id, section, title, category, quote)
# section uses the paper's own numbering; "0" = front matter/abstract,
# "1" = the whole document for unnumbered vendor pages. Quotes are verbatim
# from the extracted pages (whitespace-normalized).
ANCHORS: list[tuple[str, str, str, str, str, str]] = [
    # --- PUB-UB-UBMESH-25: UB-Mesh paper (v3) -----------------------------
    ("UBP-UBMESH-0-ABSTRACT-UB", "PUB-UB-UBMESH-25", "0",
     "Abstract: the Unified Bus technique", "architecture",
     "These components are interconnected via a novel Unified Bus (UB) "
     "technique, which enables flexible IO bandwidth allocation and hardware "
     "resource pooling."),
    ("UBP-UBMESH-0-ABSTRACT-TOPOLOGY", "PUB-UB-UBMESH-25", "0",
     "Abstract: hierarchically localized nD-FullMesh", "topology",
     "UB-Mesh employs a hierarchically localized nD-FullMesh network "
     "topology."),
    ("UBP-UBMESH-1-COST-CLAIM", "PUB-UB-UBMESH-25", "1",
     "Introduction: switch/optical reduction claims", "performance",
     "UB-Mesh reduces high-radix switch usage by 98% and optical module "
     "usage by 93%"),
    ("UBP-UBMESH-3.2-UB-DEFINITION", "PUB-UB-UBMESH-25", "3.2",
     "Unified Bus as the interconnection mechanism", "architecture",
     "These modules are interconnected through a novel interconnection "
     "mechanism called Unified Bus (UB)."),
    ("UBP-UBMESH-3.2.1-NPU-IO", "PUB-UB-UBMESH-25", "3.2.1",
     "NPU IO: two controllers, x72 UB lanes", "link_scale",
     "The NPU equips two UB IO controllers, which collectively provide x72 "
     "UB lanes."),
    ("UBP-UBMESH-3.2.1-CPU-IO", "PUB-UB-UBMESH-25", "3.2.1",
     "CPU IO: one controller, x32 IO", "link_scale",
     "The CPU, responsible for executing host programs, is also equipped "
     "with one UB IO controller, offering a UB x32 IO."),
    ("UBP-UBMESH-3.2.1-LRS-DEF", "PUB-UB-UBMESH-25", "3.2.1",
     "LRS: lightweight low-radix switch", "link_scale",
     "we develop LRS, which are lightweight, low-radix switches."),
    ("UBP-UBMESH-3.2.1-HRS-IO", "PUB-UB-UBMESH-25", "3.2.1",
     "HRS: UB x512 IO capacity for Pod-level switching", "link_scale",
     "UB-Mesh also includes high-radix switches (HRS) that offer a UB x512 "
     "IO capacity for Pod-level switching."),
    ("UBP-UBMESH-2.2-LOCALITY-97", "PUB-UB-UBMESH-25", "2.2",
     "TP+SP ~97% of total traffic (locality basis)", "workload_locality",
     "TP and SP account for approximately 97% of the total traffic"),
    ("UBP-UBMESH-3.1-HOPS", "PUB-UB-UBMESH-25", "3.1",
     "Most transmissions complete in 0-2 hops", "topology",
     "most transmissions (typically involving TP or SP as per Table 1) can "
     "be completed in 0-2 hops"),
    ("UBP-UBMESH-3.1-CABLE-MIX", "PUB-UB-UBMESH-25", "3.1",
     "86.7% of cables are short-range passive electrical", "topology",
     "short-range passive electrical cables account for 86.7% of the total "
     "consumed cables"),
    ("UBP-UBMESH-3.3.1-RACK-64NPU", "PUB-UB-UBMESH-25", "3.3.1",
     "Rack: 8 NPU boards x 8 NPUs", "scale",
     "The core of the rack consists of eight NPU boards, each containing "
     "eight NPUs"),
    ("UBP-UBMESH-3.3.1-LRS-PLANE", "PUB-UB-UBMESH-25", "3.3.1",
     "18-LRS fully-connected switch plane", "topology",
     "18 LRSes are fully-connected to form one switch plane, where two "
     "LRSes are used for CPUs and backup NPUs, eight for regular NPUs and "
     "eight for inter-rack connection."),
    ("UBP-UBMESH-3.3.1-BACKPLANE-IO", "PUB-UB-UBMESH-25", "3.3.1",
     "Backplane switches output four UB x256 IO", "link_scale",
     "Aggregately, these back-plane switches output four UB x256 IO."),
    ("UBP-UBMESH-3.3.2-64PLUS1", "PUB-UB-UBMESH-25", "3.3.2",
     "64+1 backup NPU design", "reliability",
     "the system comprises 64 regular NPUs along with an additional backup "
     "NPU."),
    ("UBP-UBMESH-3.3.3-4D-FULLMESH", "PUB-UB-UBMESH-25", "3.3.3",
     "4D-FullMesh = intra-rack 2D + inter-rack 2D", "topology",
     "we create a 2D-FullMesh within each rack and extend this to another "
     "2D-FullMesh beyond the rack, resulting in a 4D-FullMesh."),
    ("UBP-UBMESH-3.3.3-INTERRACK-LINK", "PUB-UB-UBMESH-25", "3.3.3",
     "Inter-rack link = UB x128 IO", "link_scale",
     "Each link in this configuration represents a UB x128 IO"),
    ("UBP-UBMESH-3.3.3-POD-1024", "PUB-UB-UBMESH-25", "3.3.3",
     "Pod: 16 racks, 1024 NPUs", "scale",
     "Since each rack has 64 NPUs and each pod has 16 racks, a 4D-FullMesh "
     "UB-Mesh-Pod contains 1024 NPUs in total."),
    ("UBP-UBMESH-3.3.4-SUPERPOD-8K", "PUB-UB-UBMESH-25", "3.3.4",
     "SuperPod: HRS-connected racks, up to 8K NPUs", "scale",
     "we use high-radix Pod-switches (HRS) to connect each rack in the "
     "SuperPod, scaling up to 8K NPUs."),
    ("UBP-UBMESH-3.3.4-DCN-100K", "PUB-UB-UBMESH-25", "3.3.4",
     "DCN domain scales to 100K+ NPUs (Clos)", "scale",
     "The DCN domain can scale to 100K NPUs or more."),
    ("UBP-UBMESH-4.1.1-SR-HEADER", "PUB-UB-UBMESH-25", "4.1.1",
     "APR source routing: 8-byte SR header", "routing",
     "an 8-byte SR header, containing the forwarding instructions, is added "
     "to original packet header."),
    ("UBP-UBMESH-4.1.3-TWO-VL", "PUB-UB-UBMESH-25", "4.1.3",
     "Deadlock-free all-path routing with 2 VLs", "routing",
     "enabling deadlock-free all-path routing with only 2 VL resources."),
    ("UBP-UBMESH-6.3-INTERRACK-DEFAULT", "PUB-UB-UBMESH-25", "6.3",
     "Default inter-rack allocation: UB x16 per NPU", "link_scale",
     "UB-Mesh assigns a UB x16 IO per NPU for inter-rack communication by "
     "default"),
    ("UBP-UBMESH-6.3-INTERRACK-EXPLORED", "PUB-UB-UBMESH-25", "6.3",
     "Inter-rack bandwidths explored: x4/x8/x16/x32", "link_scale",
     "The inter-rack bandwidths evaluated are x4, x8, x16, and x32 UB IO "
     "per NPU."),
    ("UBP-UBMESH-6.5-LINEARITY", "PUB-UB-UBMESH-25", "6.5",
     "Linearity still above 95% at 64K NPUs", "performance",
     "the linearity is still above 95%."),
    ("UBP-UBMESH-6.6-MTBF", "PUB-UB-UBMESH-25", "6.6",
     "MTBF 98.5h (UB-Mesh) vs 13.8h (Clos) at 8K NPUs", "availability",
     "the baseline Clos is 13.8 hours for a 8K-NPU cluster, while UB-Mesh "
     "achieves 98.5 hours"),
    ("UBP-UBMESH-6.6-AVAILABILITY", "PUB-UB-UBMESH-25", "6.6",
     "Availability 98.8% with 75-minute MTTR assumption", "availability",
     "the availability of UB-Mesh is 98.8% according to Eq.3 (We assume a "
     "75-minute MTTR"),
    # --- PUB-UB-HUAWEI-HC26: Huawei Connect 2026 announcement -------------
    ("UBP-HC26-1-UNIFIED-PROTOCOL", "PUB-UB-HUAWEI-HC26", "1",
     "10+ protocols combined under UnifiedBus", "architecture",
     "More than ten interconnect protocols have been combined under the "
     "UnifiedBus protocol"),
    ("UBP-HC26-1-BANDWIDTH-LEVEL", "PUB-UB-HUAWEI-HC26", "1",
     "Interconnect bandwidth from 100 GB/s level to TB/s level", "link_scale",
     "increases interconnect bandwidth from 100 GB/s level to TB/s level"),
    ("UBP-HC26-1-RTT", "PUB-UB-HUAWEI-HC26", "1",
     "RTT latency from 7 microseconds to 2 microseconds", "latency",
     "reduces round-trip time (RTT) latency from 7 microseconds to 2 "
     "microseconds"),
    ("UBP-HC26-1-GLOBAL-ADDRESSING", "PUB-UB-HUAWEI-HC26", "1",
     "Unified global memory addressing within SuperPoDs", "memory_semantics",
     "This protocol also enables unified global memory addressing within "
     "SuperPoDs."),
    ("UBP-HC26-1-HETERO-PEER", "PUB-UB-HUAWEI-HC26", "1",
     "Direct interconnect of CPUs, NPUs, memory, SSDs", "architecture",
     "UnifiedBus directly interconnects CPUs, NPUs, memory, and solid-state "
     "drives (SSDs)"),
    ("UBP-HC26-1-LINKBLADE", "PUB-UB-HUAWEI-HC26", "1",
     "LinkBlade: cable-free in-cabinet, 4096-NPU SuperPoD", "topology",
     "the UnifiedBus LinkBlade eliminates circuit losses with a cable-free "
     "design, which reduces copper cabling within a 4,096-NPU SuperPoD by "
     "about 196 kilometers."),
    ("UBP-HC26-1-LINKDEVICE", "PUB-UB-HUAWEI-HC26", "1",
     "LinkDevice: 176 ports x 1.6 Tbit/s, 280 Tbit/s", "link_scale",
     "the UnifiedBus LinkDevice supports 176 ports, with 1.6 Tbit/s "
     "bandwidth per port, delivering 280 Tbit/s all-optical "
     "interconnection."),
    ("UBP-HC26-1-LINKDEVICE-RTT", "PUB-UB-HUAWEI-HC26", "1",
     "LinkDevice RTT as low as 2 microseconds", "latency",
     "with an RTT latency as low as 2 microseconds."),
    ("UBP-HC26-1-UBG-RADIX", "PUB-UB-HUAWEI-HC26", "1",
     "UBG switch radix fan-out up to 1,024", "scale",
     "the UnifiedBus UBG switch provides a massive radix fan-out capacity "
     "of up to 1,024"),
    ("UBP-HC26-1-MILLION-SUPERCLUSTER", "PUB-UB-HUAWEI-HC26", "1",
     "Million-NPU SuperCluster support", "scale",
     "it can support a million-NPU SuperCluster"),
    ("UBP-HC26-1-ATLAS650E", "PUB-UB-HUAWEI-HC26", "1",
     "Two Atlas 650E servers: 16-NPU switch-free", "topology",
     "Two Atlas 650E air-cooled servers can be directly linked through "
     "UnifiedBus to enable switch-free interconnect across 16 NPUs"),
    # --- PUB-UB-OSCOMP: unifiedbus.com UB OS component page (zh) -----------
    ("UBP-UBOS-1-URMA-DRIVER", "PUB-UB-OSCOMP", "1",
     "URMA communication device driver, user-state UMDK", "software",
     "由硬件供应商提供的URMA通信设备驱动，可在用户态接入UMDK。"),
    ("UBP-UBOS-1-CDMA", "PUB-UB-OSCOMP", "1",
     "CDMA: async memory read/write host-host and host-device",
     "memory_semantics",
     "CDMA库为用户空间应用程序提供了CDMA功能，支持主机之间或主机与设备之间异步的内存读写操作。"),
    ("UBP-UBOS-1-UMMU", "PUB-UB-OSCOMP", "1",
     "UMMU: address translation and permission tables", "memory_semantics",
     "提供UMMU设备注册、初始化、配置表管理、地址转换表管理及权限表管理等功能。"),
    ("UBP-UBOS-1-OBMM-EXPORT-IMPORT", "PUB-UB-OSCOMP", "1",
     "OBMM: memory lending EXPORT/IMPORT + coherence", "memory_semantics",
     "提供内存拆借接口（EXPORT和IMPORT）、一致性维护接口（一致性维护接口仅在内存共享场景使用）。"),
    ("UBP-UBOS-1-UMMUCORE-TOKENID", "PUB-UB-OSCOMP", "1",
     "ummu-core: TokenID management, spec-2.0 advanced capabilities",
     "software",
     "提供基础的TokenID管理和《灵衢基础规范2.0》中定义的高级能力的配置和管理。"),
    ("UBP-UBOS-1-UBUS-SERVICES", "PUB-UB-OSCOMP", "1",
     "UBus: enumeration, device mgmt, error handling, hot-plug", "software",
     "提供UB总线的枚举、UB设备创建、UB设备管理、错误处理、热拔插、中断等和设备相关的基础服务。"),
    ("UBP-UBOS-1-UBUTILS-TOPO", "PUB-UB-OSCOMP", "1",
     "ubutils: UB topology query and configuration", "software",
     "提供UB设备管理的工具，实现UB拓扑查询、配置空间查询及配置等功能。"),
    ("UBP-UBOS-1-OSEULER", "PUB-UB-OSCOMP", "1",
     "openEuler 24.03 LTS SP3 (6.6 kernel) host OS", "software",
     "openEuler首个支持超节点的版本，基于6.6内核的24.03-LTS版本增强扩展版本"),
    # --- PUB-UB-DOCS-EN: unifiedbus.com public docs index ------------------
    ("UBP-UBDOCS-1-SPEC21-RATES", "PUB-UB-DOCS-EN", "1",
     "Base Spec 2.1 public highlight: 224/256 Gbit/s rates", "link_scale",
     "New: 224/256 Gbit/s rates | Reliable rerouting | Higher system "
     "bandwidth efficiency"),
    ("UBP-UBDOCS-1-LAYERS", "PUB-UB-DOCS-EN", "1",
     "Layer family: physical, data link, network test cases", "architecture",
     "Volume 1: Physical layer, data link layer, and network layer test "
     "cases"),
    ("UBP-UBDOCS-1-SUPERPOD-ARCH", "PUB-UB-DOCS-EN", "1",
     "SuperPoD reference architecture features", "architecture",
     "The reference architecture features bus interconnect, unified "
     "protocol, peer-to-peer coordination, all-resource pooling, "
     "large-scale networking, and high availability."),
    # --- PUB-UB-NESTEDVN-26: Nested Parallel von Neumann paper -------------
    ("UBP-NESTEDVN-1-MEMSEMANTIC-BUS", "PUB-UB-NESTEDVN-26", "1",
     "One memory-semantic bus end to end, full peer equality",
     "memory_semantics",
     "joined by one memory-semantic bus end to end, with full peer "
     "equality"),
    ("UBP-NESTEDVN-2-LAYER-BOUNDARIES", "PUB-UB-NESTEDVN-26", "2",
     "Command does not break at layer boundaries", "architecture",
     "it makes the split and join of every layer line up, so that command "
     "does not break at the boundaries"),
    ("UBP-NESTEDVN-2-PEERS-ON-ONE-BUS", "PUB-UB-NESTEDVN-26", "2",
     "Package to autonomous zone, peers on one bus", "architecture",
     "from package to autonomous zone, concurrent units at every layer, "
     "peers on one bus."),
    ("UBP-NESTEDVN-3-HARDWARE-PROPERTIES", "PUB-UB-NESTEDVN-26", "3",
     "One protocol end to end; copper near, optics far", "architecture",
     "one protocol end to end, memory semantics, full peer equality, "
     "copper near and optics far"),
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
        "registry_family": "unifiedbus_public_papers",
        "honesty_note": (
            "Paper-derived design profile anchors from PUBLIC papers and vendor "
            "posts only; NOT a normative UnifiedBus specification profile. The "
            "UnifiedBus specification track is license-gated (HUM-02, D-008) and "
            "was never fetched."
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
