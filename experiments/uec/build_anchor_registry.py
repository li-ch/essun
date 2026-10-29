#!/usr/bin/env python3
"""Build ``experiments/uec/anchor_registry.yaml`` for STD-UEC-11 (T010, stage S1).

The curated list below is the reviewed editorial content: one anchor per
top-level chapter, one per level-2 section, and mechanism-critical level-3
sections needed by the S2-S5 semantic-profile stages (transport semantics,
reliability & ordering, congestion management/UET-CC + CSIG, credit-based
flow control) plus the S2b stage (F07 mechanism-list extension: 3.4.9 memory
model, 3.5.23 RUDI, 5.3.2.2 CBFC TLV wire clauses, 2.4 INC detail, 6.1.x PHY
rates). Every quote is a verbatim (whitespace-normalized) substring
of the extracted page text and is at most 30 words long; both properties are
verified mechanically against ``experiments/uec/source/`` before the registry
is written.

Re-run after re-extraction::

    .venv/bin/python experiments/uec/build_anchor_registry.py
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPO_ROOT / "experiments/uec/source"
MANIFEST_PATH = SOURCE_DIR / "source_manifest.yaml"
REGISTRY_PATH = REPO_ROOT / "experiments/uec/anchor_registry.yaml"

MAX_QUOTE_WORDS = 30

# (anchor_id, section, title, page, quote) — quotes verbatim from the
# extracted page text (whitespace-normalized; line-wrap artifacts such as
# "CSIG- capable" are preserved on purpose).
ANCHORS: list[tuple[str, str, str, int, str]] = [
    # --- chapter 1: Introduction + scale-up context ---
    ("UEC11-S1-INTRODUCTION", "1", "Introduction", 28,
     "with a mission to enhance Ethernet for use in AI and HPC."),
    ("UEC11-S1.1-BACKGROUND", "1.1", "Background", 28,
     "The Ultra Ethernet Consortium (UEC) is an industry effort"),
    ("UEC11-S1.2-CONVENTIONS", "1.2", "UE Specification Conventions", 30,
     "devices supporting a given profile exhibit interoperability and "
     "functionality as described in these specifications"),
    ("UEC11-S1.3-SYSTEM-VIEW", "1.3", "System View and Nomenclature", 49,
     "The field of AI and HPC is evolving at a very fast pace."),
    ("UEC11-S1.4-SOFTWARE", "1.4", "Software", 60,
     "AI inference is often run only in scale-up networks because it does "
     "not require more than 100 endpoints."),
    ("UEC11-S1.5-NETWORKING", "1.5", "Networking", 62,
     "The control plane software interacts with data plane functionality "
     "through an abstract API."),
    ("UEC11-S1.5.1.3-LOCAL-SCALE-UP", "1.5.1.3", "Local Scale-up Network", 64,
     "Scale-up networks are typically very specialized short-range "
     "interconnects that often come with only a single or limited tier of "
     "switches or possibly no switch at all."),
    ("UEC11-S1.5.2-UET-OBJECTIVES", "1.5.2", "UE Transport (UET) Objectives", 65,
     "UET mainly targets RDMA service and attempts to provide the best, "
     "modernized, and highly optimized transport service for carrying RDMA "
     "in AI and HPC workloads."),
    ("UEC11-S1.5.3.3-TOPOLOGIES", "1.5.3.3", "Topologies", 67,
     "Topology is a critical part of an AI and HPC fabric as it sets the "
     "performance bounds by establishing the network diameter and bisection "
     "bandwidth."),
    ("UEC11-S1.6-LAYERS-OVERVIEW", "1.6",
     "UE Specification Overview: Layers", 71,
     "The UE specification spans multiple layers from software down through "
     "the physical layer."),
    # --- chapter 2: Software Layer ---
    ("UEC11-S2-SOFTWARE-LAYER", "2", "UE Software Layer", 77,
     "The UEC develops specifications, software APIs, and open-source code "
     "for various AI/HPC use cases/applications."),
    ("UEC11-S2.1-SOFTWARE-OVERVIEW", "2.1", "UE Software Overview", 77,
     "Support of UE transports and API within the OFI ecosystem (libfabric)."),
    ("UEC11-S2.2-LIBFABRIC-MAPPING", "2.2", "UE Libfabric Mapping", 81,
     "This document specifies the mapping between libfabric v2.0, also "
     "known as Open Fabrics Interfaces (OFI), and the Ultra Ethernet "
     "Transport (UET v1.0)"),
    ("UEC11-S2.3-VERBS-MAPPING", "2.3", "UE Verbs Mapping", 135,
     "UET verbs are device and transport primitive operations for accessing "
     "hardware devices supporting the Ultra Ethernet Transport."),
    ("UEC11-S2.4-INC", "2.4", "In-Network Collectives (INC)", 154,
     "High-performance computing (HPC) and artificial intelligence (AI) "
     "workloads frequently require multiple accelerators to coordinate as "
     "groups of cooperating processes"),
    # --- S2b (F07 extension): INC detail anchors ---
    ("UEC11-S2.4.1-INC-ASSUMPTIONS", "2.4.1", "Assumptions", 154,
     "UE INC MUST operate over a lossless fabric (using PFC or CBFC) over "
     "the UET ROD transport between the FEP and the SEP."),
    ("UEC11-S2.4.3-INC-OPERATIONS", "2.4.3", "INC Operations", 156,
     "An implementation MUST support at least one broadcast implementation, "
     "either UET_INC_BCAST (where non-root FEPs do not synchronize with the "
     "SEP, enabling pipelining of multiple BCAST operations)"),
    ("UEC11-S2.4.6-INC-ORDERING-MODES", "2.4.6", "Operator Ordering Modes", 158,
     "INC implementations MUST support at least one of the following operator "
     "ordering modes when configured through the IM:"),
    ("UEC11-S2.4.10-INC-SWITCH-CAPS", "2.4.10",
     "INC Switch Required and Optional Capabilities", 161,
     "A switch MUST support the following capabilities to be INC switch "
     "compliant:"),
    ("UEC11-S2.4.11-INC-TRANSPORT", "2.4.11", "INC Transport", 162,
     "INC leverages existing UET services and introduces a compact extension "
     "field to a semantic sublayer header"),
    # --- chapter 3: Transport Layer (S2/S3/S4 mechanism core) ---
    ("UEC11-S3-TRANSPORT-LAYER", "3", "UE Transport Layer", 178,
     "Its goals are minimal tail latency and highest network utilization."),
    ("UEC11-S3.1-UET-SCOPE", "3.1", "UET Scope, Scale, and Reach", 178,
     "The transport supports up to millions of endpoints (NIC ports) with "
     "the ability to address up to billions of processes."),
    ("UEC11-S3.2-UET-COMPONENTS", "3.2",
     "UET Layers, Components, and Capabilities", 179,
     "The objective of UET is to serve the breadth of all those use cases "
     "with a single transport."),
    ("UEC11-S3.3-PROFILES", "3.3", "Profiles and Capabilities [normative]",
     187,
     "PDS is responsible for delivering packets from sender to receiver."),
    ("UEC11-S3.4-SES", "3.4", "Semantics Sublayer (SES)", 193,
     "UET specifies a semantic sublayer (SES) with support for a range of "
     "use cases."),
    ("UEC11-S3.4.2-SEMANTIC-CONCEPTS", "3.4.2",
     "Definition of Semantic Concepts", 194,
     "This section articulates the semantics provided by the UET to support "
     "AI and HPC applications."),
    # --- S2b (F07 extension): memory-model anchors ---
    ("UEC11-S3.4.9-MEMORY-MODEL", "3.4.9",
     "UE Transport Semantics: Memory Model", 283,
     "The AI Base, AI Full, and HPC profiles provide a memory model that is "
     "consistent with options that are available through the libfabric API."),
    ("UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY", "3.4.9.5",
     "Memory Model for the Unified Local Profile", 286,
     "The transport for the Unified Local profile is defined only over the "
     "RODL delivery mode; thus, it guarantees idempotency."),
    ("UEC11-S3.5-PDS", "3.5", "Packet Delivery Sublayer (PDS)", 292,
     "The packet delivery sublayer is the part of the Ultra Ethernet "
     "Transport (UET) protocol responsible for delivering packets over "
     "IP/Ethernet networks."),
    ("UEC11-S3.5.3-PDS-SERVICES", "3.5.3", "Packet Delivery Services", 297,
     "SES requests PDS to deliver a packet with specified ordering and "
     "reliability."),
    ("UEC11-S3.5.6-RELIABILITY-ORDERING", "3.5.6",
     "Reliability and Ordering", 306,
     "Five combinations of reliability and ordering define the packet "
     "delivery modes."),
    ("UEC11-S3.5.15-LOSS-DETECTION", "3.5.15",
     "Loss Detection and Recovery", 376,
     "PDS MUST detect the loss of packets using the methods listed in "
     "Table 3-70."),
    ("UEC11-S3.5.20-RUD", "3.5.20", "Reliable Unordered Delivery", 401,
     "A RUD PDC is a reliable PDC established between a single initiating "
     "FEP and a single target FEP that guarantees packets are delivered "
     "once and only once."),
    ("UEC11-S3.5.21-ROD", "3.5.21", "Reliable Ordered Delivery", 415,
     "A ROD PDC is a reliable PDC established between a single initiating "
     "FEP and a single target FEP that guarantees packets are delivered at "
     "most once."),
    ("UEC11-S3.5.22-RODL", "3.5.22",
     "Reliable Ordered Delivery for Local Networks", 420,
     "RODL is a variation of ROD that is optimized for scale-up networks."),
    # --- S2b (F07 extension): RUDI anchor ---
    ("UEC11-S3.5.23-RUDI", "3.5.23", "RUDI", 424,
     "RUDI provides reliable delivery for idempotent operations. It does not "
     "use PDCs."),
    ("UEC11-S3.6-CMS", "3.6", "Congestion Management Sublayer (CMS)", 439,
     "UET defines an end-to-end congestion management solution, UET-CC (UET "
     "Congestion Control), for packet buffer congestion in a best-effort "
     "(sometimes called \u201dlossy\u201d) Ethernet network."),
    ("UEC11-S3.6.13-NSCC", "3.6.13",
     "Network Signal-based Congestion Control", 476,
     "NSCC uses a congestion window, ccc.cwnd, that limits the amount of "
     "outstanding in-flight data."),
    ("UEC11-S3.6.14-RCCC", "3.6.14",
     "UET Receiver-Credit Congestion Control", 491,
     "The UET receiver-credit congestion control (RCCC) service is derived "
     "from EQDS[11]."),
    ("UEC11-S3.6.15-TFC", "3.6.15", "Transport Flow Control (TFC)", 505,
     "A source MUST NOT transmit a packet if it does not have credit"),
    ("UEC11-S3.6.16-MULTIPATH", "3.6.16", "Multipath Path Selection", 508,
     "It is RECOMMENDED that a UET endpoint performs multipath load "
     "balancing for RUD and RUDI traffic, but the choice of precise "
     "implementation is left to implementations."),
    ("UEC11-S3.7-TSS", "3.7", "Transport Security Sublayer (TSS)", 548,
     "This section defines an optional method of end-to-end confidentiality, "
     "integrity, and basic service protection for UET."),
    ("UEC11-S3.8-REFERENCES", "3.8", "References", 585,
     "Tunnelling of Explicit Congestion Notification"),
    # --- chapter 4: Network Layer (CSIG feeds S4) ---
    ("UEC11-S4-NETWORK-LAYER", "4", "UE Network Layer", 590,
     "If the buffer is unable to accommodate an arriving packet, a switch "
     "either drops the packet or signals the upstream port to pause the "
     "flow of traffic."),
    ("UEC11-S4.1-PACKET-TRIMMING", "4.1", "Packet Trimming", 590,
     "Network switches store packets in buffers prior to forwarding them on "
     "busy egress ports."),
    ("UEC11-S4.2-CSIG", "4.2", "Congestion Signaling (CSIG)", 600,
     "Contemporary machine learning (ML) training and high-performance "
     "computing (HPC) workloads compute across a switched network fabric in "
     "closely coupled, synchronous fashion."),
    ("UEC11-S4.2.7-CSIG-PROFILES", "4.2.7", "CSIG Profiles", 619,
     "We define two CSIG configuration profiles: a base profile, which "
     "describes the set of signals that all CSIG- capable devices MUST "
     "support"),
    ("UEC11-S4.2.9-CSIG-SIGNALS", "4.2.9", "CSIG Signals", 621,
     "This section describes each signal, the algorithm for any associated "
     "computation, boundary conditions, and the signal\u2019s applicability in "
     "example use cases."),
    # --- chapter 5: Link Layer (S2 link semantics + S5 credits) ---
    ("UEC11-S5-LINK-LAYER", "5", "UE Link Layer", 630,
     "These optional-to-implement specifications enhance performance and "
     "reliability of the link layer while also simplifying configuration."),
    ("UEC11-S5.1-LLR", "5.1", "Link Layer Retry (LLR)", 631,
     "The impact of delay on efficiency becomes more significant as network "
     "link speeds, utilization, and scale increase."),
    ("UEC11-S5.1.3-LLR-OPERATION", "5.1.3", "LLR Operation", 635,
     "The ON mode of operation enables the LLR mechanism and provides "
     "lossless link-level behavior for LLR-eligible frames"),
    ("UEC11-S5.2-CBFC", "5.2", "Credit-based Flow Control", 650,
     "This specification defines the protocols, procedures, and message "
     "formats that enable credit-based flow control (CBFC) on a "
     "per-priority basis on a UE full duplex link"),
    ("UEC11-S5.2.4-CBFC-OVERVIEW", "5.2.4", "CBFC Overview", 652,
     "The sender keeps track of the available buffer space at the receiver "
     "in units of credits"),
    ("UEC11-S5.2.5-CBFC-OPERATION", "5.2.5", "CBFC Operation", 653,
     "CBFC is a link-layer function defined only for a pair of full-duplex "
     "MACs connected by one point-to-point link."),
    ("UEC11-S5.2.10-CBFC-COMPLIANCE", "5.2.10", "CBFC Compliance Requirements",
     678,
     "The receiver\u2019s input buffer is typically divided into cells, and the "
     "cell size (in bytes) is the input buffer allocation unit."),
    ("UEC11-S5.3-LINK-NEGOTIATION", "5.3", "UE Link Negotiation", 685,
     "defines the negotiation of optional link local features for the UE "
     "link layer"),
    # --- S2b (F07 extension): CBFC TLV wire-clause anchors ---
    ("UEC11-S5.3.2.2-CBFC-TLV", "5.3.2.2",
     "UE Link Negotiation CBFC TLV (CBFC TLV)", 692,
     "Determine if CBFC is supported by the presence or absence of the CBFC "
     "TLV in both the local and remote LLDP databases."),
    ("UEC11-S5.3.2.2-CBFC-TLV-HANDSHAKE", "5.3.2.2",
     "UE Link Negotiation CBFC TLV (CBFC TLV)", 693,
     "The sender SHALL NOT use CBFC for a VC unless the remote receiver has "
     "set R_VC_RTR = TRUE for the VC."),
    ("UEC11-S5.4-OPTIMIZED-HEADERS", "5.4",
     "Optimized Headers and Packet Rate Improvement", 716,
     "This flexibility comes at the cost of larger packet overheads."),
    ("UEC11-S5.5-IDLE-REDUCTION", "5.5", "Idle Reduction", 728,
     "This standard specifies an optional feature that reduces the number "
     "of idle bytes inserted between frames."),
    # --- chapter 6: Physical Layer ---
    ("UEC11-S6-PHYSICAL-LAYER", "6", "UE Physical Layer", 730,
     "Ultra Ethernet (UE) applications, such as AI and HPC systems, require "
     "physical layers that support a variety of electrical and optical "
     "channels"),
    ("UEC11-S6.1-PHY-SUPPORT", "6.1", "UE PHY Support", 730,
     "provide low frame loss ratio, low latency, power efficiency, and "
     "reliability at scale; and leverage existing ecosystems and standards "
     "that enable seamless interoperability"),
    # --- S2b (F07 extension): PHY rate/media anchors ---
    ("UEC11-S6.1.1.1-PHY-MEDIA-100G", "6.1.1.1", "Media support", 730,
     "The following physical media are supported for 100 Gb/s per lane "
     "signaling, with relevant clause numbers in the Ethernet standard:"),
    ("UEC11-S6.1.1.2-PHY-RATES-100G", "6.1.1.2",
     "PHY rates and types supported", 731,
     "The following Ethernet PHY rates and types are in scope for UE:"),
    ("UEC11-S6.1.2.1-PHY-MEDIA-200G", "6.1.2.1", "Media Support", 731,
     "The following physical media are supported for 200 Gb/s per lane "
     "signaling, with relevant clause numbers in the Ethernet standard:"),
    ("UEC11-S6.1.2.2-PHY-RATES-200G", "6.1.2.2",
     "PHY Rates and Types Supported", 731,
     "Note that the PHYs for the media above all use the same RS-FEC "
     "(544,514) with interleaving of 10-bit symbols from four RS-FEC "
     "codewords."),
    ("UEC11-S6.2-CONTROL-ORDERED-SETS", "6.2", "Control ordered sets", 732,
     "UE control ordered sets are an OPTIONAL UE feature. A PHY that "
     "supports this feature SHALL comply with the requirements in this "
     "section."),
    ("UEC11-S6.3-FEC-STATISTICS", "6.3",
     "FEC statistics for prediction of link quality", 736,
     "FEC statistics for prediction of link quality is an OPTIONAL UE "
     "feature."),
    ("UEC11-S6.4-RECOMMENDATIONS", "6.4", "Recommendations", 749,
     "the MTBPE can be estimated as 6.4e-9/2e-19=3.2e10 seconds, or about "
     "1000 years"),
    ("UEC11-S6.5-REFERENCES", "6.5", "References", 750,
     "IEEE Std 802.3-2022, \"IEEE Standard for Ethernet,\" 2022."),
    # --- chapter 7: Management ---
    ("UEC11-S7-MANAGEMENT", "7", "UE Management", 752,
     "Other brands, names, or logos contained herein are the property of "
     "their respective owners."),
    ("UEC11-S7.1-MGMT-SCOPE", "7.1", "UE Management Scope", 752,
     "The UE specification covers the layers between the UE PHY and UE "
     "software."),
    ("UEC11-S7.2-MGMT-ARCH", "7.2",
     "High-Level UE Management Architecture", 752,
     "The initial focus of UE management is to define management "
     "specifications for the UE link layer and the UE PHY layer."),
    ("UEC11-S7.3-FABRIC-MGMT", "7.3", "UE Fabric Management", 754,
     "Switch Abstraction Interface (SAI) is widely supported by switch "
     "vendors as the abstraction layer to program switch hardware."),
    ("UEC11-S7.4-REDFISH", "7.4", "Redfish for UE Endpoint Manageability",
     755,
     "Remote management of the server can be done via two manageability "
     "paths, as shown in Figure 7-3:"),
    ("UEC11-S7.5-YANG", "7.5",
     "YANG Model for UE Network Manageability", 756,
     "UE NIC endpoint manageability shall be prescribed by extending the "
     "OCP Ethernet NIC profile."),
    ("UEC11-S7.6-SAI", "7.6", "Switch Abstraction Interface (SAI) for UE",
     759,
     "SAI is a subproject under the OCP Networking Project."),
    # --- chapter 8: Compliance + release notes ---
    ("UEC11-S8-COMPLIANCE", "8", "UE Compliance", 761,
     "To assist implementors in efforts to comply to this UE specification, "
     "the UEC provides test collateral including profile matrices, "
     "compliance checklists, and a best practices document"),
    ("UEC11-S8.1-COMPLIANCE-STATEMENT", "8.1", "Compliance Statement", 761,
     "The profile matrix and compliance checklist should be used by "
     "implementors to self-attest for compliance."),
    ("UEC11-RELNOTES", "Release Notes", "Release Notes", 763,
     "This release includes significant new functionality and normative "
     "requirements."),
]


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def page_text(page: int) -> str:
    path = SOURCE_DIR / "pages" / f"page_{page:04d}.txt"
    if not path.is_file():
        raise SystemExit(f"missing extracted page {path}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    sha_by_page = {rec["page"]: rec["sha256"] for rec in manifest["pages"]}
    problems: list[str] = []

    seen_ids: set[str] = set()
    entries = []
    for anchor_id, section, title, page, quote in ANCHORS:
        if anchor_id in seen_ids:
            problems.append(f"{anchor_id}: duplicate id")
        seen_ids.add(anchor_id)
        if len(quote.split()) > MAX_QUOTE_WORDS:
            problems.append(f"{anchor_id}: quote exceeds {MAX_QUOTE_WORDS} words")
        if normalize_ws(quote) not in normalize_ws(page_text(page)):
            problems.append(f"{anchor_id}: quote not found on page {page}")
        entries.append(
            {
                "id": anchor_id,
                "section": section,
                "title": title,
                "page": page,
                "quote": normalize_ws(quote),
                "page_sha256": sha_by_page[page],
            }
        )

    if problems:
        for line in problems:
            print(f"error: {line}", file=__import__("sys").stderr)
        return 1

    registry = {
        "source": dict(manifest["source"], pages_dir="experiments/uec/source/pages"),
        "anchors": entries,
    }
    REGISTRY_PATH.write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    toplevel = sorted(
        {e["section"].split(".")[0] for e in entries}, key=lambda s: (s != "Release Notes", s)
    )
    print(
        f"wrote {REGISTRY_PATH.relative_to(REPO_ROOT)}: {len(entries)} anchors, "
        f"top-level sections covered: {', '.join(toplevel)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
