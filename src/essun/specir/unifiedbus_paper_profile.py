"""UnifiedBus paper-derived design profile: stage S2 parameters (Q6).

Typed design parameters of the UnifiedBus-class scale-up design AS REPORTED
by the public sources anchored in stage S1
(:class:`~essun.specir.unifiedbus_sources.PaperAnchorRegistry`): link
counts/bandwidths, topology classes, memory-semantic behavior, latency
figures, scale tiers, routing, reliability/availability, and the public
software surface.  Where the public sources are silent, the value is a
:class:`UBFreeParameter` (always ``FREE``) — never invented (free-parameter
rule).  The platform map puts these onto the platform's L0/L1/L2 models; this
module is pure extraction.

Honesty rules enforced structurally:

- PAPER-DERIVED, NOT NORMATIVE.  Nothing here is a UnifiedBus standard
  profile; the specification track stays license-gated (license review pending).
  Every parameter carries paper anchors and an :data:`EVIDENCE_GRADES`
  grade that separates peer-paper reporting (``PAPER_REPORTED``) from
  vendor-announcement claims (``VENDOR_CLAIMED``) and official public-page
  highlights (``OFFICIAL_PUBLIC_PAGE``) — a vendor number can never enter
  the profile laundered as a neutral fact.
- AS REPORTED.  ``as_reported`` strings paraphrase in our own words but
  keep every number exactly as the source states it.  Anchors are
  page-pinned with sha256; a statement may be drawn from its cited
  anchors' section page span (e.g. the 3.2 anchor pins page 6 and grounds
  3.2.2 text continuing on page 7), mirroring the Q1 convention; anything
  outside an anchored page span is a free parameter instead.
- Citations are load-bearing: every anchor id (including free-parameter
  candidate anchors) must resolve in the verified S1 registry; a dangling
  id is a hard error (:func:`check_against_registry` /
  :func:`assert_valid`).
- D1 DISPOSITIONS (ladder S5, 2026-10-29; per the S1 scope decision, the
  paper-profile objects "receive dispositions when the ladder's S5
  migrates them into the D2 profile format ... not in S1").  Each design
  parameter — the profile's disposition-bearing requirement object (see
  :func:`requirements`) — carries a ``disposition`` from the ONE D1
  vocabulary (:data:`essun.specir.uec_link_transport.DISPOSITIONS`).  The
  initial assignment (:func:`initial_disposition`) is the honest rule for
  a profile executed by NO backend binding: paper-stated structure facts
  (DESIGN_CONSTANT / DESIGN_CLASS / DESIGN_DEFAULT) are ``informational``
  (carried knowledge, executed by nothing); everything else
  (REPORTED_MEASURE / BEHAVIOR / COMPONENT — outcome figures, protocol
  behaviors, host software) is ``unsupported``.  Nothing becomes
  simulated_behavior / constraint / conformance_test here: a promotion
  requires a reviewed binding in :mod:`essun.specir.bindings`, and none
  exists for UnifiedBus.  The dispositions are read (never assigned) by
  ``experiments/unifiedbus/build_semantic_profile.py``; free parameters
  carry NO disposition by design (declared freedom is not a requirement,
  the S1 scope decision unchanged).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .uec_link_transport import DISPOSITIONS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .unifiedbus_sources import PaperAnchorRegistry

#: Parameter categories — identical to the S1 registry anchor categories.
CATEGORIES: tuple[str, ...] = (
    "topology",
    "link_scale",
    "scale",
    "memory_semantics",
    "latency",
    "routing",
    "reliability",
    "availability",
    "software",
    "architecture",
    "workload_locality",
    "performance",
)

#: How a parameter's value is reported by its sources.
VALUE_KINDS: tuple[str, ...] = (
    "DESIGN_CONSTANT",  # structural count/number of the design (x72, 1024, 8-byte header)
    "DESIGN_CLASS",  # qualitative architectural class (4D-FullMesh, one-bus peer equality)
    "DESIGN_DEFAULT",  # default with publicly explored alternatives (x16 default; x4-x32)
    "REPORTED_MEASURE",  # measured/modeled outcome figure (MTBF, linearity, RTT claim)
    "BEHAVIOR",  # protocol/memory-semantic behavior description
    "COMPONENT",  # named software/stack component of the public surface
)

#: Evidence grades.  A parameter's grade must be derivable from the sources
#: its anchors cite (see :data:`SOURCE_EVIDENCE_GRADES`).
EVIDENCE_GRADES: tuple[str, ...] = (
    "PAPER_REPORTED",  # peer-reviewable public paper (UB-Mesh, Nested-vN)
    "VENDOR_CLAIMED",  # vendor announcement/engineering post numbers (HC26)
    "OFFICIAL_PUBLIC_PAGE",  # official public site page, non-normative (unifiedbus.com)
)

#: Source-id -> evidence grade.  Kept explicit so grade honesty is testable.
SOURCE_EVIDENCE_GRADES: dict[str, str] = {
    "PUB-UB-UBMESH-25": "PAPER_REPORTED",
    "PUB-UB-NESTEDVN-26": "PAPER_REPORTED",
    "PUB-UB-HUAWEI-HC26": "VENDOR_CLAIMED",
    "PUB-UB-OSCOMP": "OFFICIAL_PUBLIC_PAGE",
    "PUB-UB-DOCS-EN": "OFFICIAL_PUBLIC_PAGE",
}

#: ``as_reported`` strings stay crisp so every value stays reviewable.
MAX_AS_REPORTED_WORDS = 50

#: Free-parameter gap descriptions (what the sources do NOT say).
MAX_GAP_WORDS = 80

#: Value kinds that state the STRUCTURE of the design as the public sources
#: report it (counts, classes, defaults).  These and only these qualify for
#: the ``informational`` initial disposition; every other kind is a fact a
#: backend could in principle execute or host (an outcome figure, a protocol
#: behavior, a software component), so with no binding in existence it stays
#: ``unsupported`` — the honest initial for a profile executed by nothing.
STRUCTURE_FACT_KINDS: tuple[str, ...] = (
    "DESIGN_CONSTANT",
    "DESIGN_CLASS",
    "DESIGN_DEFAULT",
)


def initial_disposition(value_kind: str) -> str:
    """The S5 initial rule: structure facts informational, all else unsupported.

    Never returns an executed disposition (constraint /
    simulated_behavior / conformance_test) — those require a reviewed
    binding in :mod:`essun.specir.bindings`, and none exists for
    UnifiedBus.  A promotion is a conscious change to the frozen counts in
    tests/specir/test_unifiedbus_paper_profile.py, never silent.
    """
    return "informational" if value_kind in STRUCTURE_FACT_KINDS else "unsupported"


@dataclass(frozen=True)
class UBDesignParameter:
    """One design parameter with its AS-REPORTED value and paper anchors.

    The profile's disposition-bearing requirement object (S5): ``disposition``
    is required and drawn from the D1 vocabulary; free parameters
    (:class:`UBFreeParameter`) carry none by design.
    """

    parameter_id: str
    name: str
    category: str  # element of CATEGORIES
    value_kind: str  # element of VALUE_KINDS
    as_reported: str  # value as the public sources report it, own words
    unit: str  # "" for qualitative classes/behaviors
    anchor_ids: tuple[str, ...]
    evidence_grade: str  # element of EVIDENCE_GRADES, consistent with sources
    disposition: str  # element of DISPOSITIONS (D1; S5 initial rule)
    notes: str = ""  # caveats, same-page tables, pointers to FREE params


@dataclass(frozen=True)
class UBFreeCandidate:
    """A public figure nearest to a gap — anchored, never normative."""

    label: str
    anchor_id: str
    evidence_grade: str


@dataclass(frozen=True)
class UBFreeParameter:
    """A degree of freedom: the public papers are silent, so the value is
    FREE (never invent a value where sources are
    silent).  ``candidates`` may record anchored public figures that sit
    closest to the gap without filling it."""

    parameter_id: str
    name: str
    category: str  # element of CATEGORIES
    gap: str  # what is NOT reported (the silence being marked)
    anchor_ids: tuple[str, ...]  # anchors evidencing the reported context
    candidates: tuple[UBFreeCandidate, ...] = field(default=())
    domain: str = "FREE"  # always FREE by construction


_PARAMETERS: tuple[UBDesignParameter, ...] = (
    # -- topology ------------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P01",
        name="pod_topology_class",
        category="topology",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "4D-FullMesh: a 2D-FullMesh within each rack plus another "
            "2D-FullMesh across racks; the paper calls this a "
            "hierarchically localized nD-FullMesh and stays at 4D this "
            "generation, adopting Clos beyond."
        ),
        unit="",
        anchor_ids=(
            "UBP-UBMESH-3.3.3-4D-FULLMESH",
            "UBP-UBMESH-0-ABSTRACT-TOPOLOGY",
        ),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes="Page 7 states the not-5D-this-generation and Clos-beyond choice.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P02",
        name="rack_switch_plane",
        category="topology",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "One switch plane per rack: 18 fully-connected LRSes — two "
            "serve CPUs and backup NPUs, eight regular NPUs, eight "
            "inter-rack; CPU boards are separate and attach through "
            "switches."
        ),
        unit="LRSes",
        anchor_ids=("UBP-UBMESH-3.3.1-LRS-PLANE",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P03",
        name="hop_locality",
        category="topology",
        value_kind="REPORTED_MEASURE",
        as_reported="Most transmissions, typically TP or SP, complete in 0-2 hops.",
        unit="hops",
        anchor_ids=("UBP-UBMESH-3.1-HOPS",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P04",
        name="cable_mix",
        category="topology",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "Short-range passive electrical cables account for 86.7% of "
            "consumed cables (XY dimension, about 1 m)."
        ),
        unit="%",
        anchor_ids=("UBP-UBMESH-3.1-CABLE-MIX",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes=(
            "Same-page Table 2: Z active electrical 7.2% (~10 m); alpha "
            "optical 4.8% (~100 m); beta/gamma optical 1.2% (~1000 m)."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P05",
        name="linkblade_in_cabinet",
        category="topology",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "LinkBlade: cable-free in-cabinet interconnect that eliminates "
            "circuit losses and cuts about 196 kilometers of copper "
            "cabling within a 4,096-NPU SuperPoD."
        ),
        unit="km; NPUs",
        anchor_ids=("UBP-HC26-1-LINKBLADE",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P06",
        name="atlas_650e_switch_free",
        category="topology",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "Two Atlas 650E air-cooled servers link directly through "
            "UnifiedBus for switch-free interconnect across 16 NPUs; "
            "one-to-eight-NPU appliances also exist."
        ),
        unit="NPUs",
        anchor_ids=("UBP-HC26-1-ATLAS650E",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
        notes="Vendor says the pair scales toward a small SuperPoD.",
    ),
    # -- link scale ----------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P07",
        name="npu_ub_lanes",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="Each NPU has two UB IO controllers providing x72 UB lanes in total.",
        unit="UB lanes",
        anchor_ids=("UBP-UBMESH-3.2.1-NPU-IO",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes="Per-lane rate is not public — see UBP-F01.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P08",
        name="cpu_ub_lanes",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="Each CPU has one UB IO controller offering a UB x32 IO.",
        unit="UB lanes",
        anchor_ids=("UBP-UBMESH-3.2.1-CPU-IO",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P09",
        name="lrs_class_and_io",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "LRS: lightweight, low-radix, low-cost switches ensuring "
            "non-blocking communication; Table 3 lists LRS IO capability "
            "as UB x72."
        ),
        unit="UB IO width",
        anchor_ids=("UBP-UBMESH-3.2.1-LRS-DEF",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Same section (3.2 span, pages 6-7): one reusable UB IO "
            "controller design covers CPU, NPU, and LRS switch."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P10",
        name="hrs_io_capacity",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="HRS: high-radix switches offering a UB x512 IO capacity for Pod-level switching.",
        unit="UB IO width",
        anchor_ids=("UBP-UBMESH-3.2.1-HRS-IO",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P11",
        name="backplane_io",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="The rack's back-plane switches aggregately output four UB x256 IO.",
        unit="UB IO width",
        anchor_ids=("UBP-UBMESH-3.3.1-BACKPLANE-IO",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P12",
        name="interrack_link_width",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="Each inter-rack link in the 4D-FullMesh is a UB x128 IO.",
        unit="UB IO width",
        anchor_ids=("UBP-UBMESH-3.3.3-INTERRACK-LINK",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P13",
        name="interrack_bw_per_npu",
        category="link_scale",
        value_kind="DESIGN_DEFAULT",
        as_reported=(
            "Default inter-rack allocation: UB x16 IO per NPU for "
            "cost-performance balance; the paper explores x4/x8/x16/x32 "
            "per NPU."
        ),
        unit="UB IO width per NPU",
        anchor_ids=(
            "UBP-UBMESH-6.3-INTERRACK-DEFAULT",
            "UBP-UBMESH-6.3-INTERRACK-EXPLORED",
        ),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Reported optimal x16 at sequence lengths 8K-32K and x32 at "
            "64K-10M; measured gains 0.44% (x8 to x16) and 1.85% (x16 to "
            "x32) at 8K SuperPod."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P14",
        name="hc26_bandwidth_level",
        category="link_scale",
        value_kind="REPORTED_MEASURE",
        as_reported="Interconnect bandwidth increased from 100 GB/s level to TB/s level.",
        unit="GB/s (level claim)",
        anchor_ids=("UBP-HC26-1-BANDWIDTH-LEVEL",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P15",
        name="linkdevice_ports",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "LinkDevice: 176 ports at 1.6 Tbit/s per port, delivering "
            "280 Tbit/s all-optical interconnection."
        ),
        unit="ports; Tbit/s",
        anchor_ids=("UBP-HC26-1-LINKDEVICE",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
        notes="Only public per-port rate figure; per-lane rate remains UBP-F01.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P16",
        name="spec21_rate_highlight",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "Base Spec 2.1 public highlight: new 224/256 Gbit/s rates, "
            "reliable rerouting, higher system bandwidth efficiency, "
            "lower multi-path communication latency."
        ),
        unit="Gbit/s",
        anchor_ids=("UBP-UBDOCS-1-SPEC21-RATES",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="informational",
        notes=(
            "Highlight-grade figure off the public docs index; the rate "
            "scope (per-lane vs per-port) is NOT stated — see UBP-F01, "
            "UBP-F08."
        ),
    ),
    # -- scale ---------------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P17",
        name="npus_per_rack",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "Rack core: eight NPU boards with eight NPUs each, 64 NPUs "
            "total, in an intra-rack 2D full-mesh; UB IO controllers "
            "route, so each NPU is also a router enabling indirect "
            "routing."
        ),
        unit="NPUs",
        anchor_ids=("UBP-UBMESH-3.3.1-RACK-64NPU",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P18",
        name="pod_scale",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="UB-Mesh-Pod: 16 racks, 1024 NPUs total.",
        unit="racks; NPUs",
        anchor_ids=("UBP-UBMESH-3.3.3-POD-1024",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Same page: four adjacent racks per row form a 1D full-mesh; "
            "rack columns directly connected, completing the inter-rack "
            "2D full-mesh."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P19",
        name="superpod_tier",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "UB-Mesh-SuperPod connects each rack through HRS Pod-switches "
            "in a symmetrical Clos at Pod level, scaling up to 8K NPUs."
        ),
        unit="NPUs",
        anchor_ids=("UBP-UBMESH-3.3.4-SUPERPOD-8K",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes="Clos chosen beyond 4D-FullMesh for divisible full-bandwidth domains.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P20",
        name="dcn_tier",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "DCN domain: Clos-organized switches scaling to 100K NPUs or "
            "more; racks attach via UB switches or CPU-board NICs."
        ),
        unit="NPUs",
        anchor_ids=("UBP-UBMESH-3.3.4-DCN-100K",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P21",
        name="ubg_radix",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="UBG switch: radix fan-out capacity of up to 1,024.",
        unit="radix",
        anchor_ids=("UBP-HC26-1-UBG-RADIX",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P22",
        name="supercluster_scale",
        category="scale",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "A million-NPU SuperCluster is supported (TaiShan 950 and "
            "Atlas 960 SuperPoDs, OceanStor M900, Xinghe UBG switch)."
        ),
        unit="NPUs",
        anchor_ids=("UBP-HC26-1-MILLION-SUPERCLUSTER",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
    ),
    # -- memory semantics ----------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P23",
        name="global_addressing",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported="Unified global memory addressing within SuperPoDs.",
        unit="",
        anchor_ids=("UBP-HC26-1-GLOBAL-ADDRESSING",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P24",
        name="ub_operation_classes",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported=(
            "UB simultaneously supports synchronized operations "
            "(Load/Store/Atomic) and asynchronous operations "
            "(Read/Write/Message)."
        ),
        unit="",
        anchor_ids=("UBP-UBMESH-3.2-UB-DEFINITION",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes="Section 3.2.2 text, within the anchored section 3.2 span (pages 6-7).",
    ),
    UBDesignParameter(
        parameter_id="UBP-P25",
        name="cdma_service",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported=(
            "CDMA library: asynchronous memory read/write between hosts "
            "and between host and device, for user-space applications."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-CDMA",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P26",
        name="ummu_service",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported=(
            "UMMU: device registration, initialization, "
            "configuration-table, address-translation-table, and "
            "permission-table management."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-UMMU",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P27",
        name="obmm_service",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported=(
            "OBMM: memory-lending interfaces (EXPORT and IMPORT) plus "
            "coherence maintenance; the coherence interface is used only "
            "in memory-sharing scenarios."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-OBMM-EXPORT-IMPORT",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P28",
        name="end_to_end_memory_bus",
        category="memory_semantics",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "Compute and memory are joined by one memory-semantic bus "
            "end to end, with full peer equality."
        ),
        unit="",
        anchor_ids=("UBP-NESTEDVN-1-MEMSEMANTIC-BUS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P29",
        name="tiered_memory_pooling",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported=(
            "Hybrid-media resource pooling: DDR memory serves as "
            "alternative memory for NPUs (activation caching), claimed to "
            "double vector-retrieval performance and reduce per-NPU HBM "
            "requirements."
        ),
        unit="",
        anchor_ids=("UBP-HC26-1-HETERO-PEER",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="unsupported",
        notes=(
            "HC26 key feature 3, on the page every HC26 anchor pins; "
            "cited anchor is thematically the closest HC26 row."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P30",
        name="hetero_peer_access",
        category="memory_semantics",
        value_kind="BEHAVIOR",
        as_reported=(
            "UnifiedBus directly interconnects CPUs, NPUs, memory, and "
            "SSDs for decentralized peer-to-peer access, flexible "
            "CPU-NPU mixing, and Attention-FFN disaggregation."
        ),
        unit="",
        anchor_ids=("UBP-HC26-1-HETERO-PEER",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="unsupported",
    ),
    # -- latency -------------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P31",
        name="rtt_level_claim",
        category="latency",
        value_kind="REPORTED_MEASURE",
        as_reported="RTT latency reduced from 7 microseconds to 2 microseconds.",
        unit="μs",
        anchor_ids=("UBP-HC26-1-RTT",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="unsupported",
        notes="Protocol-level claim; no component breakdown — see UBP-F02.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P32",
        name="linkdevice_rtt_claim",
        category="latency",
        value_kind="REPORTED_MEASURE",
        as_reported="LinkDevice RTT latency as low as 2 microseconds.",
        unit="μs",
        anchor_ids=("UBP-HC26-1-LINKDEVICE-RTT",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="unsupported",
    ),
    # -- routing -------------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P33",
        name="sr_header",
        category="routing",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "APR adds an 8-byte source-routing header containing "
            "forwarding instructions to the original packet header."
        ),
        unit="bytes",
        anchor_ids=("UBP-UBMESH-4.1.1-SR-HEADER",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes="Only public header-layout figure — see UBP-F03.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P34",
        name="apr_two_vl",
        category="routing",
        value_kind="DESIGN_CONSTANT",
        as_reported="All-path routing is deadlock-free using only 2 VL resources.",
        unit="VLs",
        anchor_ids=("UBP-UBMESH-4.1.3-TWO-VL",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P35",
        name="pod_routing_strategies",
        category="routing",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "In-Pod routing strategies: Shortest (baseline shortest "
            "path), Detour (all-path routing uses additional paths), "
            "Borrow (racks borrow switch bandwidth)."
        ),
        unit="",
        anchor_ids=("UBP-UBMESH-6.3-INTERRACK-EXPLORED",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Section 6.3 text on the anchored page: GPT4-2T degradation "
            "vs Clos 0.73% naive, 0.46% with Detour and Borrow."
        ),
    ),
    # -- reliability / availability ------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P36",
        name="backup_npu_64plus1",
        category="reliability",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "64 regular NPUs plus one backup NPU connected via LRS; on "
            "failure the backup takes over, redirecting the failed "
            "NPU's direct links through the LRS as one-hop routing."
        ),
        unit="NPUs",
        anchor_ids=("UBP-UBMESH-3.3.2-64PLUS1",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Paper says the one-hop redirect slightly increases latency "
            "but beats masking the failed NPU."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P37",
        name="mtbf_8k",
        category="availability",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "8K-NPU cluster MTBF: 98.5 hours for UB-Mesh vs 13.8 hours "
            "for the Clos baseline."
        ),
        unit="hours",
        anchor_ids=("UBP-UBMESH-6.6-MTBF",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P38",
        name="availability_claim",
        category="availability",
        value_kind="REPORTED_MEASURE",
        as_reported="UB-Mesh availability 98.8% under an assumed 75-minute MTTR.",
        unit="%",
        anchor_ids=("UBP-UBMESH-6.6-AVAILABILITY",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
    ),
    # -- workload locality ---------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P39",
        name="tp_sp_traffic_share",
        category="workload_locality",
        value_kind="REPORTED_MEASURE",
        as_reported="TP and SP account for approximately 97% of total traffic.",
        unit="%",
        anchor_ids=("UBP-UBMESH-2.2-LOCALITY-97",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes="Locality basis for the 0-2-hop claim (UBP-P03).",
    ),
    # -- performance ---------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P40",
        name="switch_optical_reduction",
        category="performance",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "High-radix switch usage reduced 98% and optical module "
            "usage 93% versus the Clos baseline."
        ),
        unit="%",
        anchor_ids=("UBP-UBMESH-1-COST-CLAIM",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes=(
            "Section 6.4 (page 12) adds: network-infrastructure cost "
            "share 67% to 20%; CapEx reductions 1.18x/1.26x/1.65x/2.46x "
            "vs alternative architectures."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P41",
        name="linearity_64k",
        category="performance",
        value_kind="REPORTED_MEASURE",
        as_reported="Training linearity still above 95% at 64K NPUs.",
        unit="%",
        anchor_ids=("UBP-UBMESH-6.5-LINEARITY",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
    ),
    # -- architecture --------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P42",
        name="ub_interconnect_role",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "UB is the single interconnection mechanism joining the "
            "heterogeneous modules, replacing hybrid PCIe + NVLink + "
            "InfiniBand/RoCE stacks."
        ),
        unit="",
        anchor_ids=("UBP-UBMESH-3.2-UB-DEFINITION",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Section 3.2.2 (page 7, anchored span) states the detailed "
            "UB protocol specification is 'going to be released' — "
            "consistent with the license-gated spec track (HUM-02)."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P43",
        name="ub_flex_pooling_claims",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "UB enables flexible IO bandwidth allocation and hardware "
            "resource pooling: one link pool adjustable between "
            "inter-NPU and CPU-NPU use; DDR/CPU/NPU/NIC pooled "
            "peer-to-peer; no protocol conversions."
        ),
        unit="",
        anchor_ids=("UBP-UBMESH-0-ABSTRACT-UB",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P44",
        name="protocol_unification_claim",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported="More than ten interconnect protocols combined under the UnifiedBus protocol.",
        unit="",
        anchor_ids=("UBP-HC26-1-UNIFIED-PROTOCOL",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P45",
        name="public_layer_titles",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "Public Compatibility Test Specification 2.0 title "
            "enumerates Volume 1 test cases for physical, data-link, "
            "and network layers only."
        ),
        unit="",
        anchor_ids=("UBP-UBDOCS-1-LAYERS",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="informational",
        notes="No public test-volume titles above the network layer — see UBP-F06.",
    ),
    UBDesignParameter(
        parameter_id="UBP-P46",
        name="superpod_ref_arch_features",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "SuperPoD reference architecture features: bus interconnect, "
            "unified protocol, peer-to-peer coordination, all-resource "
            "pooling, large-scale networking, high availability."
        ),
        unit="",
        anchor_ids=("UBP-UBDOCS-1-SUPERPOD-ARCH",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P47",
        name="layer_boundary_alignment",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "Every layer's split and join points line up so a command "
            "does not break at layer boundaries."
        ),
        unit="",
        anchor_ids=("UBP-NESTEDVN-2-LAYER-BOUNDARIES",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P48",
        name="peers_on_one_bus",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "Concurrent units at every layer, from package to autonomous "
            "zone, are peers on one bus."
        ),
        unit="",
        anchor_ids=("UBP-NESTEDVN-2-PEERS-ON-ONE-BUS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    UBDesignParameter(
        parameter_id="UBP-P49",
        name="copper_near_optics_far",
        category="architecture",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "One protocol end to end, memory semantics, full peer "
            "equality, copper near and optics far."
        ),
        unit="",
        anchor_ids=("UBP-NESTEDVN-3-HARDWARE-PROPERTIES",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    # -- software ------------------------------------------------------------
    UBDesignParameter(
        parameter_id="UBP-P50",
        name="urma_driver",
        category="software",
        value_kind="COMPONENT",
        as_reported=(
            "URMA communication device driver provided by hardware "
            "vendors, accessible in user state via UMDK."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-URMA-DRIVER",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P51",
        name="ummu_core",
        category="software",
        value_kind="COMPONENT",
        as_reported=(
            "ummu-core: basic TokenID management plus configuration and "
            "management of advanced capabilities defined in UnifiedBus "
            "Base Specification 2.0."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-UMMUCORE-TOKENID",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
        notes=(
            "The gated Base Specification is referenced by title only, "
            "through this public page; the document itself was never "
            "fetched."
        ),
    ),
    UBDesignParameter(
        parameter_id="UBP-P52",
        name="ubus_services",
        category="software",
        value_kind="COMPONENT",
        as_reported=(
            "UBus base services: bus enumeration, UB device creation and "
            "management, error handling, hot-plug, interrupts."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-UBUS-SERVICES",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P53",
        name="ubutils",
        category="software",
        value_kind="COMPONENT",
        as_reported="ubutils tools: UB topology query, configuration-space query, and configuration.",
        unit="",
        anchor_ids=("UBP-UBOS-1-UBUTILS-TOPO",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
    UBDesignParameter(
        parameter_id="UBP-P54",
        name="host_os",
        category="software",
        value_kind="COMPONENT",
        as_reported=(
            "Host OS: openEuler 24.03-LTS-based enhanced extension on "
            "the 6.6 kernel — the first openEuler version supporting "
            "supernodes."
        ),
        unit="",
        anchor_ids=("UBP-UBOS-1-OSEULER",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
    ),
)

_FREE_PARAMETERS: tuple[UBFreeParameter, ...] = (
    UBFreeParameter(
        parameter_id="UBP-F01",
        name="per_lane_line_rate",
        category="link_scale",
        gap=(
            "No public source states a per-lane UB line rate in Gbit/s; "
            "only lane counts are reported (x72/x32/x512/x256/x128/x16). "
            "Neither public rate figure below is stated as per-lane."
        ),
        anchor_ids=(
            "UBP-UBMESH-3.2.1-NPU-IO",
            "UBP-UBDOCS-1-SPEC21-RATES",
            "UBP-HC26-1-LINKDEVICE",
        ),
        candidates=(
            UBFreeCandidate(
                label="224/256 Gbit/s rates — Base Spec 2.1 public highlight, scope unstated",
                anchor_id="UBP-UBDOCS-1-SPEC21-RATES",
                evidence_grade="OFFICIAL_PUBLIC_PAGE",
            ),
            UBFreeCandidate(
                label="1.6 Tbit/s per LinkDevice port — per-port, not per-lane",
                anchor_id="UBP-HC26-1-LINKDEVICE",
                evidence_grade="VENDOR_CLAIMED",
            ),
        ),
    ),
    UBFreeParameter(
        parameter_id="UBP-F02",
        name="component_latency_breakdown",
        category="latency",
        gap=(
            "Only end-to-end RTT figures are public (7 to 2 microseconds; "
            "LinkDevice as low as 2 microseconds). No per-hop, per-link, "
            "per-switch, serialization, or propagation latency components "
            "are reported."
        ),
        anchor_ids=("UBP-HC26-1-RTT", "UBP-HC26-1-LINKDEVICE-RTT"),
    ),
    UBFreeParameter(
        parameter_id="UBP-F03",
        name="packet_flit_format",
        category="routing",
        gap=(
            "No public packet or FLIT format, MTU, or header layout "
            "beyond the 8-byte APR source-routing header is reported."
        ),
        anchor_ids=("UBP-UBMESH-4.1.1-SR-HEADER",),
    ),
    UBFreeParameter(
        parameter_id="UBP-F04",
        name="congestion_control",
        category="routing",
        gap=(
            "None of the five public sources describes a "
            "congestion-control mechanism; only switch planes, "
            "all-path routing, and 2-VL deadlock freedom appear. The "
            "flow-control scheme is unknown from public text."
        ),
        anchor_ids=("UBP-UBMESH-3.2.1-LRS-DEF", "UBP-UBMESH-4.1.3-TWO-VL"),
    ),
    UBFreeParameter(
        parameter_id="UBP-F05",
        name="ordering_atomicity_detail",
        category="memory_semantics",
        gap=(
            "Ordering, atomicity, and memory-consistency semantics "
            "appear only as prose ('memory semantics', coherence in "
            "shared scenes); no public consistency model or "
            "atomic-operation set exists."
        ),
        anchor_ids=(
            "UBP-NESTEDVN-1-MEMSEMANTIC-BUS",
            "UBP-UBOS-1-OBMM-EXPORT-IMPORT",
        ),
    ),
    UBFreeParameter(
        parameter_id="UBP-F06",
        name="layer_model_above_network",
        category="architecture",
        gap=(
            "The public layer inventory stops at physical, data-link, "
            "and network test volumes; the protocol's layer model above "
            "the network layer is not public."
        ),
        anchor_ids=("UBP-UBDOCS-1-LAYERS",),
    ),
    UBFreeParameter(
        parameter_id="UBP-F07",
        name="lrs_plane_wiring",
        category="link_scale",
        gap=(
            "How the 18 LRSes' ports map onto the 64 NPUs and the four "
            "x256 backplane IOs is not spelled out; only plane "
            "composition and per-LRS IO capability are reported."
        ),
        anchor_ids=(
            "UBP-UBMESH-3.3.1-LRS-PLANE",
            "UBP-UBMESH-3.2.1-LRS-DEF",
            "UBP-UBMESH-3.3.1-BACKPLANE-IO",
        ),
    ),
    UBFreeParameter(
        parameter_id="UBP-F08",
        name="rerouting_mechanism",
        category="reliability",
        gap=(
            "Reliable rerouting is named as a Base Spec 2.1 highlight "
            "with no public mechanism; the 64+1 design covers NPU "
            "failure, not link-failure rerouting."
        ),
        anchor_ids=("UBP-UBDOCS-1-SPEC21-RATES", "UBP-UBMESH-3.3.2-64PLUS1"),
        candidates=(
            UBFreeCandidate(
                label="Reliable rerouting — feature name only, no mechanism",
                anchor_id="UBP-UBDOCS-1-SPEC21-RATES",
                evidence_grade="OFFICIAL_PUBLIC_PAGE",
            ),
        ),
    ),
)


class ProfileObjectError(Exception):
    """Raised when a UnifiedBus profile object fails validation."""


def parameters() -> tuple[UBDesignParameter, ...]:
    """All design-parameter objects of this stage."""
    return _PARAMETERS


def requirements() -> tuple[UBDesignParameter, ...]:
    """The profile's disposition-bearing requirement objects (S5 naming).

    For this paper-derived family the requirement objects ARE the design
    parameters (:class:`UBDesignParameter`, each carrying a D1 disposition);
    the alias matches the UEC stage modules' accessor so coverage tooling
    (:func:`essun.specir.disposition_coverage.module_disposition_counts`)
    and the profile builder read one shape.  Free parameters stay outside:
    declared freedom carries no disposition by design.
    """
    return _PARAMETERS


def free_parameters() -> tuple[UBFreeParameter, ...]:
    """All free-parameter objects of this stage."""
    return _FREE_PARAMETERS


def all_objects() -> tuple[UBDesignParameter | UBFreeParameter, ...]:
    """Design parameters and free parameters together."""
    return _PARAMETERS + _FREE_PARAMETERS


def anchor_ids() -> frozenset[str]:
    """Every anchor id cited by any object, including free candidates."""
    ids = {aid for obj in all_objects() for aid in obj.anchor_ids}
    for obj in _FREE_PARAMETERS:
        ids.update(cand.anchor_id for cand in obj.candidates)
    return frozenset(ids)


def by_category(category: str) -> tuple[UBDesignParameter | UBFreeParameter, ...]:
    """All objects (parameters and free parameters) in one category."""
    return tuple(obj for obj in all_objects() if obj.category == category)


def _shape_problems(obj: UBDesignParameter | UBFreeParameter) -> list[str]:
    problems: list[str] = []
    oid = obj.parameter_id
    if not obj.name.strip():
        problems.append(f"{oid}: empty name")
    if obj.category not in CATEGORIES:
        problems.append(
            f"{oid}: unknown category {obj.category!r} (not in {CATEGORIES})"
        )
    if not obj.anchor_ids:
        problems.append(f"{oid}: no anchor ids")
    if isinstance(obj, UBDesignParameter):
        if obj.value_kind not in VALUE_KINDS:
            problems.append(
                f"{oid}: unknown value_kind {obj.value_kind!r} "
                f"(not in {VALUE_KINDS})"
            )
        words = len(obj.as_reported.split())
        if words == 0:
            problems.append(f"{oid}: empty as_reported value")
        elif words > MAX_AS_REPORTED_WORDS:
            problems.append(
                f"{oid}: as_reported has {words} words "
                f"(> {MAX_AS_REPORTED_WORDS})"
            )
        if obj.evidence_grade not in EVIDENCE_GRADES:
            problems.append(
                f"{oid}: unknown evidence_grade {obj.evidence_grade!r} "
                f"(not in {EVIDENCE_GRADES})"
            )
        # D1 gate (S5): a disposition-bearing object without a valid
        # disposition is invalid — same messages as the UEC stages'
        # disposition gate so the vocabulary has one enforcement shape.
        # (Rule parity dispositions == initial_disposition is pinned by
        # the tests, mirroring the UEC PROMOTED-table pattern, so a future
        # promotion does not have to touch this module check.)
        if not obj.disposition:
            problems.append(
                f"{oid}: missing disposition (one of {DISPOSITIONS})"
            )
        elif obj.disposition not in DISPOSITIONS:
            problems.append(
                f"{oid}: unknown disposition {obj.disposition!r} "
                f"(not in {DISPOSITIONS})"
            )
    else:
        if obj.domain != "FREE":
            problems.append(f"{oid}: free parameter must stay domain=FREE")
        gap_words = len(obj.gap.split())
        if gap_words == 0:
            problems.append(f"{oid}: empty gap description")
        elif gap_words > MAX_GAP_WORDS:
            problems.append(
                f"{oid}: gap has {gap_words} words (> {MAX_GAP_WORDS})"
            )
        for cand in obj.candidates:
            if not cand.label.strip():
                problems.append(f"{oid}: free candidate with empty label")
            if not cand.anchor_id.strip():
                problems.append(f"{oid}: free candidate with empty anchor_id")
            if cand.evidence_grade not in EVIDENCE_GRADES:
                problems.append(
                    f"{oid}: free candidate grade {cand.evidence_grade!r} "
                    f"not in {EVIDENCE_GRADES}"
                )
    return problems


def check_against_registry(registry: "PaperAnchorRegistry") -> list[str]:
    """Validate every object against the S1 paper-anchor registry.

    Checks: unique object ids, structural shape (vocabularies, word
    bounds), every cited anchor id resolves (dangling ids are hard
    errors), and evidence-grade honesty — each object's declared grade
    must be derivable from the sources its anchors cite via
    :data:`SOURCE_EVIDENCE_GRADES`, so a vendor claim can never be typed
    as a paper measurement or vice versa.  Returns all problems; an
    empty list means valid.
    """
    problems: list[str] = []
    seen: dict[str, int] = {}
    for obj in all_objects():
        oid = obj.parameter_id
        seen[oid] = seen.get(oid, 0) + 1
        problems.extend(_shape_problems(obj))
        try:
            resolved = registry.resolve(obj.anchor_ids)
        except Exception as exc:  # AnchorRegistryError on dangling ids
            problems.append(f"{oid}: {exc}")
            resolved = ()
        for anchor in resolved:
            grade = SOURCE_EVIDENCE_GRADES.get(anchor.source_id)
            if grade is None:
                problems.append(
                    f"{oid}: anchor {anchor.anchor_id} cites unknown source "
                    f"{anchor.source_id!r} (not in SOURCE_EVIDENCE_GRADES)"
                )
            elif (
                isinstance(obj, UBDesignParameter)
                and obj.evidence_grade != grade
            ):
                problems.append(
                    f"{oid}: evidence grade {obj.evidence_grade!r} not "
                    f"derivable from anchor {anchor.anchor_id} "
                    f"(source grade {grade!r})"
                )
        if isinstance(obj, UBFreeParameter):
            for cand in obj.candidates:
                try:
                    (anchor,) = registry.resolve([cand.anchor_id])
                except Exception as exc:
                    problems.append(f"{oid}: candidate {cand.label!r}: {exc}")
                    continue
                expected = SOURCE_EVIDENCE_GRADES.get(anchor.source_id)
                if cand.evidence_grade != expected:
                    problems.append(
                        f"{oid}: candidate {cand.label!r} grade "
                        f"{cand.evidence_grade!r} != source grade "
                        f"{expected!r}"
                    )
    problems.extend(
        f"duplicate object id {oid} ({count} entries)"
        for oid, count in sorted(seen.items())
        if count > 1
    )
    return problems


def assert_valid(registry: "PaperAnchorRegistry") -> None:
    """Raise :class:`ProfileObjectError` if any check fails."""
    problems = check_against_registry(registry)
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise ProfileObjectError(
            f"UnifiedBus paper profile objects failed validation: "
            f"{detail}{more}"
        )
