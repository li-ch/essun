#!/usr/bin/env python3
"""Build ``experiments/nvlink/anchor_registry.yaml`` (M1 stage S1).

Mirrors ``experiments/unifiedbus/build_anchor_registry.py`` for the
NVLink-class multi-source public-paper registry: the curated list below is
the reviewed editorial content — one anchor per design-relevant claim a
paper-derived NVLink-class profile needs (switch/topology structure, link
counts and bandwidth figures, domain scale, measured latency, the software
stack's bandwidth model, and the class member TPU v4 ICI).

Honesty rule (absolute, same as the UnifiedBus family): these are
PAPER-DERIVED anchors from public papers and public pages, NOT a normative
NVLink/NVSwitch specification profile — no public specification document
exists (the specification track is licensee/NDA-gated; source record row
STD-NV-SPEC was never fetched). Nothing in this registry quotes any
licensee/vendor confidential document.

Each quote is a verbatim (whitespace-normalized) substring of the extracted
page text, at most 30 whitespace-words AND at most 200 characters. The page
is AUTO-LOCATED: the builder scans the source's pages in order and records
the first page containing the quote — verified mechanically before the
registry is written, so a hand-edited quote is a hard error.

Re-run after re-fetching/re-extracting::

    .venv/bin/python experiments/nvlink/build_anchor_registry.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "experiments/nvlink/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/nvlink/anchor_registry.yaml"

MAX_QUOTE_WORDS = 30
MAX_QUOTE_CHARS = 200

#: Categories consumed by the profile stages (design parameters, platform
#: mapping, comparison). Kept closed; the builder rejects unknown ones.
CATEGORIES = {
    "topology",            # topology class and construction
    "link_scale",          # link counts / widths / bandwidth figures
    "scale",               # endpoint / rack / domain scale figures
    "latency",             # latency figures
    "routing",             # routing / reconfiguration mechanics
    "performance",         # measured performance outcomes (context only)
    "software",            # communication-stack software surface
}

# (anchor_id, source_id, section, title, category, quote)
# section uses the paper's own numbering; "0" = front matter/abstract,
# "1" = the whole document for unnumbered vendor/tracker pages. Quotes are
# verbatim from the extracted pages (whitespace-normalized); LaTeX-source
# artifacts of the arXiv HTML (\times, \mu s, zero-width spaces) are copied
# EXACTLY as extracted — verbatim means byte-honest, not pretty.
ANCHORS: list[tuple[str, str, str, str, str, str]] = [
    # --- PUB-NV-LI-TPDS19: Li et al., TPDS 2019 (arXiv:1903.04611) --------
    ("NVP-LI-1-DGX-SIZES", "PUB-NV-LI-TPDS19", "1",
     "DGX-1 8 GPUs / DGX-2 16 GPUs (NVLink, NVSwitch)", "scale",
     "which incorporate 8 and 16 P100/V100 GPUs connected by NVLink and "
     "NVSwitch, respectively."),
    ("NVP-LI-1-NUMA-FOUR", "PUB-NV-LI-TPDS19", "1",
     "Four NUMA effect classes, three from NVLink topology", "performance",
     "we have observed four new types of GPU communication network NUMA "
     "effects:"),
    ("NVP-LI-2-P100-QUADSLOTS", "PUB-NV-LI-TPDS19", "2",
     "P100 GPU has quad NVLink slots", "link_scale",
     "A Pascal-P100 GPU has quad NVLink slots."),
    ("NVP-LI-2-NVSWITCH-PORTS", "PUB-NV-LI-TPDS19", "2",
     "NVSwitch: NVLink-V2 switch chip, 18 NVLink ports", "link_scale",
     "NVSwitch is an NVLink-V2 based switch chip for intra-node "
     "communication, featuring 18 ports of NVLink per switch."),
    ("NVP-LI-2-NVSWITCH-CROSSBAR", "PUB-NV-LI-TPDS19", "2",
     "Each NVSwitch is an 18x18 fully connected non-blocking crossbar",
     "topology",
     "Each NVSwitch is a 18x18 fully connected non-blocking crossbar: "
     "(1) 8 of the 18 ports are used for intra-baseboard communication"),
    ("NVP-LI-2-V100-LINKS-BW", "PUB-NV-LI-TPDS19", "2",
     "V100: 6 NVLink slots, 50 GB/s bidirectional per link", "link_scale",
     "a V100 GPU incorporates 6 NVLink slots, being able to connect to "
     "6 NVSwitches simultaneously, each target per link, at 50 GB/s "
     "bidirectional bandwidth."),
    ("NVP-LI-2-DGX2-BASEBOARDS", "PUB-NV-LI-TPDS19", "2",
     "DGX-2: two baseboards, 6 NVSwitches and 8 GPUs each", "topology",
     "there are two baseboards; each contains 6 NVSwitches and hosts "
     "8 GPUs"),
    ("NVP-LI-3-NVLINK-LATENCY", "PUB-NV-LI-TPDS19", "3",
     "NVLink P2P latency ~9us direct, 2-3x routed (measured)", "latency",
     "the latency is around 9μ​s\\mu s; for nodes that require manual "
     "routing, the latency is increased by about 2x for P100-DGX-1 and "
     "3x for V100-DGX-1."),
    ("NVP-LI-3-NVSWITCH-HOMOG", "PUB-NV-LI-TPDS19", "3",
     "NVSwitch remote access homogeneous, all-to-all fully-connected",
     "latency",
     "all the remote access are homogeneous, either for PCIe or NVSwitch, "
     "confirming that NVSwitch is all-to-all fully-connected."),
    # --- PUB-NV-TPU4-ICI23: Jouppi et al., ISCA 2023 (arXiv:2304.01433) ---
    ("NVP-TPU4-0-OCS-TOPOLOGY", "PUB-NV-TPU4-ICI23", "0",
     "OCSes dynamically reconfigure the interconnect topology", "topology",
     "Optical circuit switches (OCSes) dynamically reconfigure its "
     "interconnect topology to improve scale, availability, utilization, "
     "modularity, deployment, security, power, and performance;"),
    ("NVP-TPU4-2.1-OCS-MS", "PUB-NV-TPU4-ICI23", "2.1",
     "Palomar OCS: MEMS mirrors switch in milliseconds", "routing",
     "The resulting Google Palomar OCS is based on 3D "
     "Micro-Electro-Mechanical Systems (MEMS) mirrors that switch in "
     "milliseconds."),
    ("NVP-TPU4-4-TWIST-GAIN", "PUB-NV-TPU4-ICI23", "4",
     "Twisted torus: 1.63x/1.31x all-to-all over regular torus",
     "performance",
     "The twisted torus improves all-to-all throughput by 1.63x and 1.31x "
     "over the regular torus on 4×4×8 and 4×8×8 slices, respectively."),
    ("NVP-TPU4-5-T4-ICI-LINKS", "PUB-NV-TPU4-ICI23", "5",
     "TPU v4 ICI: 6 links @ 50 GB/s (v3: 4 @ 70 GB/s)", "link_scale",
     "Inter Chip Interconnect 6 links @ 50 GB/s 4 links @ 70 GB/s"),
    ("NVP-TPU4-5-T4-SCALE", "PUB-NV-TPU4-ICI23", "5",
     "Largest scale: 4096 chips (v3: 1024)", "scale",
     "Largest scale configuration 4096 chips 1024 chips"),
    ("NVP-TPU4-7.2-ICI-ROUTER", "PUB-NV-TPU4-ICI23", "7.2",
     "Built-in router between ICI links (torus)", "topology",
     "Every TPU since 2017 has had its own built-in router between links "
     "(ICI) to neighboring chips in the torus."),
    ("NVP-TPU4-7.2-NVSWITCH-256", "PUB-NV-TPU4-ICI23", "7.2",
     "NVSwitch: 8 GPUs one switch, up to 256 two levels", "scale",
     "which uses electrical packet switching for 8 GPUs with one switch "
     "and up to 256 GPUs with two levels of switches."),
    ("NVP-TPU4-7.3-ICI-VS-IB", "PUB-NV-TPU4-ICI23", "7.3",
     "ICI link bandwidth 2x IB: 400 vs 200 Gbit/s", "link_scale",
     "ICI link bandwidth is 2x IB—400 vs 200 Gbit/s"),
    # --- PUB-NV-GB200-UG: DGX GB rack user guide (hardware page) ----------
    ("NVP-UG-1-SWITCH-57.6T", "PUB-NV-GB200-UG", "1",
     "NVLink5 switch: 57.6 Tbps full duplex", "link_scale",
     "The NVLink switch system delivers an unprecedented 57.6 terabits "
     "per second (Tbps) of full duplex bandwidth for the fifth-generation "
     "NVLink in a 1U design."),
    ("NVP-UG-1-SWITCH-PORTS", "PUB-NV-GB200-UG", "1",
     "2x NVLink NVSwitches per tray, 72 NVLink ports each", "link_scale",
     "2x NVLink NVSwitches, each of which has 72 NVLink ports"),
    ("NVP-UG-1-COMPUTE-TRAYS", "PUB-NV-GB200-UG", "1",
     "18x compute trays: 2 Grace CPUs + 4 Blackwell GPUs each", "scale",
     "18x 1RU compute trays, each with 2 Grace CPUs and 4 Blackwell GPUs."),
    ("NVP-UG-1-SWITCH-TRAYS", "PUB-NV-GB200-UG", "1",
     "9x 1RU NVLink switch trays", "scale",
     "9x 1RU NVLink switch trays."),
    # --- PUB-NV-GB200-NVL72: product page ---------------------------------
    ("NVP-NVL72-1-RACK-COMPOSITION", "PUB-NV-GB200-NVL72", "1",
     "36 Grace CPUs + 72 Blackwell GPUs, rack-scale liquid-cooled",
     "scale",
     "The NVIDIA GB200 NVL72 connects 36 Grace CPUs and 72 Blackwell GPUs "
     "in a rack-scale, liquid-cooled design."),
    ("NVP-NVL72-1-DOMAIN-72", "PUB-NV-GB200-NVL72", "1",
     "One 72-GPU NVLink domain acting as a single, massive GPU", "scale",
     "It boasts a 72-GPU NVIDIA NVLink™ domain that acts as a single, "
     "massive GPU"),
    ("NVP-NVL72-1-AGGREGATE-130TB", "PUB-NV-GB200-NVL72", "1",
     "NVLink Switch System: 130 TB/s GPU communications", "link_scale",
     "With 72 NVIDIA Blackwell GPUs interconnected by the largest NVIDIA "
     "NVLink domain ever offered, NVLink Switch System provides 130 "
     "terabytes per second (TB/s) of low-latency GPU communications"),
    ("NVP-NVL72-1-PERGPU-1.8TB", "PUB-NV-GB200-NVL72", "1",
     "Fifth-generation NVLink: 1.8 TB/s GPU-to-GPU", "link_scale",
     "the fifth-generation NVLink, which provides 1.8 TB/s of "
     "GPU-to-GPU interconnect,"),
    # --- PUB-NV-NCCL-1054: NCCL issue #1054 -------------------------------
    ("NVP-NCCL-1-TOTALBW-240", "PUB-NV-NCCL-1054", "1",
     "NCCL topo totalBw 240 GB/s on 8-GPU A100", "software",
     "I found that the system->totalBw obtained at ncclTopoSearchInit was "
     "only 240GB/s."),
    ("NVP-NCCL-1-MODEL-20GB", "PUB-NV-NCCL-1054", "1",
     "NCCL topo.h models an NVLink at 20 GB/s (not 25)", "software",
     "in the src/graph/topo.h file, an nvlink bandwidth is defined as "
     "20GB/s instead of 25GB/s."),
    ("NVP-NCCL-1-DERATE-80", "PUB-NV-NCCL-1054", "1",
     "App-level NVLink bandwidth ~80% of peak (maintainer)", "performance",
     "The NVLink peak bandwidth and the real application-level bandwidth "
     "are different, since there is an overhead for NVLink packets. "
     "Roughly, the app-level bandwidth is 80% of the peak bandwidth."),
]


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = {rec["source_id"]: rec for rec in manifest["sources"]}

    # page text + sha per source/page, straight from the committed extraction
    text_by_sid_page: dict[str, dict[int, str]] = {}
    sha_by_sid_page: dict[str, dict[int, str]] = {}
    for sid, rec in sources.items():
        pages: dict[int, str] = {}
        shas: dict[int, str] = {}
        for page in sorted((REPO_ROOT / rec["pages_dir"]).glob("page_*.txt")):
            number = int(page.stem.split("_")[1])
            pages[number] = page.read_text(encoding="utf-8")
            shas[number] = hashlib.sha256(page.read_bytes()).hexdigest()
        text_by_sid_page[sid] = pages
        sha_by_sid_page[sid] = shas

    problems: list[str] = []
    entries: list[dict] = []
    for anchor_id, sid, section, title, category, quote in ANCHORS:
        if sid not in sources:
            problems.append(f"{anchor_id}: unknown source_id {sid}")
            continue
        if category not in CATEGORIES:
            problems.append(f"{anchor_id}: unknown category {category!r}")
            continue
        norm_quote = normalize_whitespace(quote)
        if len(norm_quote.split()) > MAX_QUOTE_WORDS:
            problems.append(f"{anchor_id}: quote over {MAX_QUOTE_WORDS} words")
        if len(norm_quote) > MAX_QUOTE_CHARS:
            problems.append(f"{anchor_id}: quote over {MAX_QUOTE_CHARS} chars")
        located = None
        for number in sorted(text_by_sid_page[sid]):
            if norm_quote in normalize_whitespace(text_by_sid_page[sid][number]):
                located = number
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
            "quote": norm_quote,
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
        "registry_family": "nvlink_class_public_papers",
        "honesty_note": (
            "Paper-derived NVLink-class design profile anchors from PUBLIC "
            "papers and public pages only; NOT a normative NVLink/NVSwitch "
            "specification profile. No public specification document exists — "
            "the specification track is licensee/NDA-gated (STD-NV-SPEC) and "
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
