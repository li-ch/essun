#!/usr/bin/env python3
"""Build the ODS 1.0 semantic profile (essun-profile v0.1 artifact).

Deterministic: running this script always produces the same bytes in
experiments/ods/semantic_profile.yaml. The profile interprets the ODCC
"Open Disaggregated SuperPoD (ODS) System Architecture Whitepaper 1.0"
(Chinese edition, 91 pages). Every requirement cites an anchor in
experiments/ods/anchor_registry.yaml; every quoted phrase is a verbatim
substring of the page text under experiments/ods/source/pages/ (<= 120
characters). The whitepaper states that its 1.0 edition defines the
hardware system architecture only and does not define the interconnect
protocol, so the profile carries no protocol-semantics requirement.
Dispositions follow the mechanism-existence convention of the other
public profiles: constraint for existence statements, informational for
scope/menu statements. Bindings are empty on purpose (no backend claims
ODS support yet) and checks are empty on purpose (nothing executable is
claimed); both are honest absences, not omissions.
"""

from __future__ import annotations

import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "semantic_profile.yaml"

HEADER = """\
# ODS 1.0 (ODCC Open Disaggregated SuperPoD) semantic profile — essun-profile v0.1 artifact.
# GENERATED FILE; regenerate with:
#   .venv/bin/python experiments/ods/build_semantic_profile.py
# Interpretation of the ODCC whitepaper "开放解构节点（ODS）系统架构技术白皮书" 1.0
# (91 pages, sha256 in the source record). The 1.0 edition explicitly limits
# itself to the hardware system architecture and does not define the interconnect
# protocol (anchor ODS10-P08-SCOPE); no protocol-semantics requirement is
# interpreted here. Anchor quotes resolve against
# experiments/ods/anchor_registry.yaml; page text lives under
# experiments/ods/source/pages/. Conformance gate:
# tests/specir/test_ods_semantic_profile.py (loads, anchors resolve verbatim,
# quote length, zero-binding honesty, corruption rejection, byte-identical
# regeneration).
"""


def requirement(req_id, module, keyword, disposition, anchors, statement):
    return {
        "requirement_id": req_id,
        "module": module,
        "subject": "ODS",
        "keyword": keyword,
        "disposition": disposition,
        "anchor_ids": anchors,
        "statement": statement,
    }


def freedom(param_id, module, name, anchors, note):
    return {
        "parameter_id": param_id,
        "module": module,
        "name": name,
        "domain": "FREE",
        "anchor_ids": anchors,
        "freedom": note,
    }


REQUIREMENTS = {
    "ods_system": [
        requirement(
            "ODS10-SYS-R01", "ods_system", "DEFINITIONAL", "informational",
            ["ODS10-P08-SCOPE"],
            "The 1.0 edition defines the open disaggregated superpod hardware system "
            "architecture only; the interconnect protocol is explicitly out of scope, so "
            "this profile interprets no protocol semantics.",
        ),
        requirement(
            "ODS10-SYS-R02", "ods_system", "OPEN", "constraint",
            ["ODS10-P15-OPENETH"],
            "The design route is open Ethernet for the scale-up network, reusing the "
            "Ethernet ecosystem and maximizing a unified scale-up / scale-out technology "
            "stack.",
        ),
        requirement(
            "ODS10-SYS-R03", "ods_system", "DISAGGREGATION", "constraint",
            ["ODS10-P15-DISAGG"],
            "Compute nodes are lightweight customized servers and switch nodes are "
            "standardized switches; the two interconnect through generic copper or fiber "
            "ports, disaggregating the hardware architecture.",
        ),
        requirement(
            "ODS10-SYS-R04", "ods_system", "SCALING", "constraint",
            ["ODS10-P15-SCALE"],
            "The system scales smoothly from tens of cards to more than a thousand cards "
            "(design principle; the per-configuration maxima live in the topology "
            "requirements).",
        ),
        requirement(
            "ODS10-SYS-R05", "ods_system", "EFFICIENCY", "constraint",
            ["ODS10-P16-HIGHRADIX"],
            "High-radix switches are preferred to simplify the network, reduce switch "
            "hop count, and lower end-to-end latency (part of the interconnect-efficiency "
            "principle, alongside copper-first cabling and minimizing optical-electrical "
            "conversion).",
        ),
    ],
    "ods_topology": [
        requirement(
            "ODS10-TOPO-R06", "ods_topology", "SINGLE_TIER", "constraint",
            ["ODS10-P17-SWITCHCAP", "ODS10-P17-BASEMAX"],
            "The base ODS uses one tier of full peer-to-peer switching; the switch is "
            "either 51.2T (128x400G) or 102.4T (128x800G), and one tier supports at most "
            "256 cards (liquid cooled) or 128 cards (air cooled), limited by port density "
            "and cable reach.",
        ),
        requirement(
            "ODS10-TOPO-R07", "ods_topology", "EXAMPLE", "informational",
            ["ODS10-P18-4X800G", "ODS10-P20-ROCE24", "ODS10-P20-SIXSW"],
            "The 64-card air-cooled reference (Gaudi3): each GPU connects through four "
            "800G AEC cables to four switches (3.2 Tbps per GPU), each GPU exposes 24x200G "
            "RoCE interfaces, and the cluster uses six 51.2T switches.",
        ),
        requirement(
            "ODS10-TOPO-R08", "ods_topology", "MULTI_PLANE", "constraint",
            ["ODS10-P21-8PLANES", "ODS10-P22-RESERVE50"],
            "The cascade first tier builds 8 scale-up planes (8x 51.2T, one 400G link per "
            "GPU per plane) or 4 planes (4x 102.4T, one 800G link per GPU per plane), and "
            "reserves 50% of first-tier ports for the cascade uplinks.",
        ),
        requirement(
            "ODS10-TOPO-R09", "ods_topology", "CASCADE_TIER2", "constraint",
            ["ODS10-P22-OCS"],
            "The second tier uses either the same switch model or an optical circuit "
            "switch (OCS); the OCS is strongly recommended to remove repeated "
            "optical-electrical conversion.",
        ),
        requirement(
            "ODS10-TOPO-R10", "ods_topology", "MAX_SCALE", "constraint",
            ["ODS10-P23-MAX8192", "ODS10-P26-MAX16384", "ODS10-P26-MAX2048OCS"],
            "Maximum cluster size is determined by the two tiers: 51.2T+51.2T reaches "
            "8192 cards; 102.4T+102.4T reaches 16384 cards; replacing the second tier "
            "with a 256x256 OCS gives 1024 cards (first tier 51.2T) or 2048 cards (first "
            "tier 102.4T).",
        ),
    ],
    "ods_interconnect": [
        requirement(
            "ODS10-INT-R11", "ods_interconnect", "LATENCY", "constraint",
            ["ODS10-P51-LAT1US"],
            "Switches must support cut-through or an equivalent function to reduce "
            "latency; the total in-network latency is recommended to stay below 1 "
            "microsecond.",
        ),
        requirement(
            "ODS10-INT-R12", "ods_interconnect", "MEMORY_SEMANTICS", "constraint",
            ["ODS10-P51-SHORT64B"],
            "Switches are recommended to forward 64-byte short packets at line rate to "
            "serve native memory-semantics traffic (the transport itself is not defined "
            "in edition 1.0).",
        ),
        requirement(
            "ODS10-INT-R13", "ods_interconnect", "RELIABILITY", "constraint",
            ["ODS10-P51-LLR"],
            "Link-layer retransmission (LLR) is recommended on switches to improve "
            "packet error-retransmission efficiency.",
        ),
        requirement(
            "ODS10-INT-R14", "ods_interconnect", "LOAD_BALANCING", "constraint",
            ["ODS10-P51-SPRAY"],
            "Switches must support packet spraying, with weight-based spraying as defined "
            "by the FARE (fully adaptive routing Ethernet) protocol recommended.",
        ),
        requirement(
            "ODS10-INT-R15", "ods_interconnect", "CABLES", "constraint",
            ["ODS10-P69-AEC7M", "ODS10-P71-AECLAT", "ODS10-P75-OPTMENU"],
            "Compute-to-switch links prefer AEC copper (up to 7 m at 112G SerDes; "
            "bidirectional cable delay recommended below 50 ns); switch-to-switch links "
            "use optics, with FRO / LPO / LRO / CPO coexisting as the optical menu.",
        ),
    ],
}

FREEDOM = [
    freedom(
        "ODS10-F01", "ods_topology", "per_xpu_scaleup_bandwidth",
        ["ODS10-P18-4X800G", "ODS10-P20-ROCE24"],
        "The whitepaper gives examples (4x800G AEC = 3.2 Tbps per GPU in the 64-card "
        "reference; 24x200G RoCE interfaces available per GPU) but states no normative "
        "per-xPU scale-up bandwidth; any profile-level value stays free.",
    ),
    freedom(
        "ODS10-F02", "ods_topology", "plane_count",
        ["ODS10-P21-8PLANES"],
        "First-tier plane count is configuration-dependent (8 planes with 51.2T switches "
        "or 4 planes with 102.4T switches); the profile keeps it free per configuration.",
    ),
    freedom(
        "ODS10-F03", "ods_topology", "per_plane_link_rate",
        ["ODS10-P21-8PLANES"],
        "Per-GPU per-plane single-link rate is 400G in the 8-plane scheme and 800G in "
        "the 4-plane scheme; not fixed normatively.",
    ),
    freedom(
        "ODS10-F04", "ods_topology", "l2_interconnect_type",
        ["ODS10-P22-OCS"],
        "Second tier may be an electrical switch or an OCS (OCS strongly recommended); "
        "deployment choice.",
    ),
    freedom(
        "ODS10-F05", "ods_interconnect", "network_total_latency_budget",
        ["ODS10-P51-LAT1US"],
        "The <1 us total in-network latency is a recommendation; the profile records it "
        "as a parameter an evaluation may instantiate.",
    ),
    freedom(
        "ODS10-F06", "ods_interconnect", "aec_bidirectional_delay",
        ["ODS10-P71-AECLAT"],
        "The <50 ns bidirectional AEC delay is a recommendation; kept as a parameter.",
    ),
    freedom(
        "ODS10-F07", "ods_system", "protocol_semantics",
        ["ODS10-P08-SCOPE"],
        "Edition 1.0 does not define the interconnect protocol; all protocol semantics "
        "remain unspecified and therefore free.",
    ),
]

PROFILE = {
    "format": {"name": "essun-profile", "version": "0.1"},
    "profile_id": "ods-1.0-semantic",
    "source": {
        "name": "ODCC Open Disaggregated SuperPoD (ODS) system architecture whitepaper 1.0",
        "document_id": "ods_wp_1_0",
        "revision": "9c6457bf98fdad7fed53d2525cb8c2175a315df4abb26fb6b532bf175bba3a89",
        "normative": False,
        "note": (
            "Interpretation of the ODCC ODS 1.0 whitepaper (Chinese edition). The "
            "document defines the hardware system architecture and states that the "
            "1.0 edition does not define the interconnect protocol; requirements here "
            "are mechanism-existence interpretations with verbatim anchors, values the "
            "document states as examples or recommendations keep their anchors and "
            "everything unstated stays an explicit free parameter."
        ),
    },
    "provenance": {
        "source_record": "experiments/ods/source_record.yaml",
        "access": "PUBLIC_READ_VIA_OWNER",
        "paper_sources": [
            {
                "source_id": "STD-ODS-WP10",
                "title": "开放解构节点（ODS）系统架构技术白皮书（1.0 版）",
                "url": None,
                "access": "PUBLIC_READ_VIA_OWNER",
                "doc_sha256": "9c6457bf98fdad7fed53d2525cb8c2175a315df4abb26fb6b532bf175bba3a89",
            }
        ],
        "anchor_registry": "experiments/ods/anchor_registry.yaml",
        "license_status": (
            "No usage notice appears inside the document (scanned); the owner "
            "confirmed public anchored-quotation usage on 2026-11-13 "
            "(STD-ODS-LICENSE, RESOLVED_BY_OWNER). The PDF stays out of git; the "
            "page-text representation lives under experiments/ods/source/pages/."
        ),
    },
    "requirements": {
        "objects": [
            req
            for module in (
                "ods_system",
                "ods_topology",
                "ods_interconnect",
            )
            for req in REQUIREMENTS[module]
        ]
    },
    "freedom": FREEDOM,
    "bindings": [],
    "checks": [],
    "supported": {"workloads": ["w1_dense_tp_decode"], "observables": ["O-CCT", "O-CONSERVATION"]},
    "calibration": {
        "status": "uncalibrated",
        "note": (
            "E0 evidence level: interpretation and anchoring only; no ODS hardware "
            "measurements exist and no backend claims ODS support (bindings empty by "
            "honest absence)."
        ),
    },
    "omissions": [
        {
            "what": "Protocol semantics are not interpreted",
            "reason": (
                "Edition 1.0 explicitly limits itself to the hardware system "
                "architecture and does not define the interconnect protocol "
                "(ODS10-P08-SCOPE); this is the document's scope statement, not a "
                "coverage gap of this profile."
            ),
        },
        {
            "what": (
                "The 'supported' element names the TARGET comparison surface (the "
                "cross-design L0 identity under w1_dense_tp_decode with O-CCT and "
                "O-CONSERVATION), not an executed ODS surface — no backend claims "
                "ODS support today"
            ),
            "reason": (
                "The format requires at least one workload and observable id; the "
                "honest declaration is the surface the cross-standard comparison "
                "aims at, stated here so no reader mistakes it for a claim that ODS "
                "behavior executes anywhere."
            ),
        },
        {
            "what": "Zero backend bindings and zero executable checks",
            "reason": (
                "No requirement carries a simulated_behavior disposition (the "
                "whitepaper describes architecture, not simulated behavior), so both "
                "lists are empty by content; the profile's real invariants — "
                "verbatim anchors against page text and byte-identical regeneration "
                "— live as tests at tests/specir/test_ods_semantic_profile.py."
            ),
        },
        {
            "what": (
                "No whitepaper example figure is promoted to a normative value: "
                "3.2 Tbps per GPU (4x800G), 24x200G RoCE interfaces, 8/4 plane "
                "schemes, <1 us and <50 ns latency recommendations all stay graded "
                "statements under their anchors or explicit free parameters "
                "(ODS10-F01..F07)"
            ),
            "reason": (
                "A whitepaper example or recommendation is evidence about a public "
                "document, not a normative value; each keeps its anchor and every "
                "unstated quantity stays free."
            ),
        },
    ],
    "versioning": {
        "profile_version": "0.1.0",
        "bump_rules": {
            "major": ["dispositions", "bindings", "anchor_ids"],
            "minor": ["requirements", "freedom", "checks", "supported"],
            "patch": ["notes"],
        },
        "note": "The profile version tracks this ARTIFACT, not the whitepaper edition.",
    },
}


def build() -> str:
    body = yaml.safe_dump(
        PROFILE, allow_unicode=True, width=88, sort_keys=True, default_flow_style=False
    )
    return HEADER + body


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
