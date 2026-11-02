"""NVLink-class paper-derived design profile: M1 parameters.

Typed design parameters of the NVLink-class scale-up family (the
GPU/accelerator-attached proprietary fabrics that NVLink/NVSwitch
exemplifies) AS REPORTED by the public sources anchored in the M1 stage-S1
registry (:class:`~essun.specir.unifiedbus_sources.PaperAnchorRegistry`
loaded from ``experiments/nvlink/anchor_registry.yaml``): NVSwitch/NVLink
structure from the TPDS-2019 microbenchmark paper, NVLink5/NVL72 spec
figures from two vendor public pages, the communication stack's internal
bandwidth model from the NCCL project's public tracker, and the class's
independent public-paper member (TPU v4 ICI) from the ISCA-2023 paper.
Where the public sources are silent, the value is a
:class:`NVFreeParameter` (always ``FREE``) — never invented
(free-parameter rule).  The platform map
(:mod:`essun.specir.nvlink_platform_map`) puts these onto the platform's
L0/L1/L2 models; this module is pure extraction.

Honesty rules enforced structurally (mirroring the UnifiedBus family
exactly — same discipline, third fabric):

- PAPER-DERIVED, NOT NORMATIVE.  Nothing here is an NVLink/NVSwitch
  standard profile; no public specification document exists (the
  specification track is licensee/NDA-gated, source-record row STD-NV-SPEC,
  never fetched).  Every parameter carries paper/page anchors and an
  :data:`EVIDENCE_GRADES` grade that separates peer-paper reporting
  (``PAPER_REPORTED``) from vendor spec/marketing claims
  (``VENDOR_CLAIMED``) and the communication stack's official public
  tracker page (``OFFICIAL_PUBLIC_PAGE``) — a vendor number can never
  enter the profile laundered as a neutral fact.
- AS REPORTED.  ``as_reported`` strings paraphrase in our own words but
  keep every number exactly as the source states it.  Anchors are
  page-pinned with sha256; quotes are re-matched at load.  TPU-v4-ICI
  parameters describe the class member TPU v4 ICI, never NVIDIA hardware,
  and say so in their names.
- Citations are load-bearing: every anchor id (including free-parameter
  candidate anchors) must resolve in the verified S1 registry; a dangling
  id is a hard error (:func:`check_against_registry` /
  :func:`assert_valid`).
- D1 DISPOSITIONS (the S5 rule, same as the UnifiedBus migration): each
  design parameter carries a ``disposition`` from the ONE D1 vocabulary
  (:data:`essun.specir.uec_link_transport.DISPOSITIONS`).  The initial
  assignment (:func:`initial_disposition`) is the honest rule for a
  profile executed by NO backend binding: paper-stated structure facts
  (DESIGN_CONSTANT / DESIGN_CLASS / DESIGN_DEFAULT) are ``informational``
  (carried knowledge, executed by nothing); everything else
  (REPORTED_MEASURE / BEHAVIOR / COMPONENT — outcome figures, observed
  behaviors) is ``unsupported``.  Nothing becomes simulated_behavior /
  constraint / conformance_test here: a promotion requires a reviewed
  binding in :mod:`essun.specir.bindings`, and none exists for the
  NVLink-class family.  Free parameters carry NO disposition by design
  (declared freedom is not a requirement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .uec_link_transport import DISPOSITIONS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .unifiedbus_sources import PaperAnchorRegistry

#: The M1 S1 registry this profile resolves against (multi-source public
#: papers/pages; the loader class is shared with the UnifiedBus family).
REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = REPO_ROOT / "experiments/nvlink/anchor_registry.yaml"

#: Parameter categories — identical to the S1 registry anchor categories.
CATEGORIES: tuple[str, ...] = (
    "topology",
    "link_scale",
    "scale",
    "latency",
    "routing",
    "performance",
    "software",
)

#: How a parameter's value is reported by its sources.
VALUE_KINDS: tuple[str, ...] = (
    "DESIGN_CONSTANT",  # structural count/number of the design (18 ports, 72 GPUs, 57.6 Tbps)
    "DESIGN_CLASS",  # qualitative architectural class (non-blocking crossbar, 3D torus + OCS)
    "DESIGN_DEFAULT",  # default with publicly explored alternatives (none in this family yet)
    "REPORTED_MEASURE",  # measured/modeled outcome figure (latency, derating, topology gain)
    "BEHAVIOR",  # protocol/communication behavior description
    "COMPONENT",  # named software/stack component of the public surface
)

#: Evidence grades (the three labels of this family, same names as the
#: UnifiedBus family so cross-family tooling reads one vocabulary).
EVIDENCE_GRADES: tuple[str, ...] = (
    "PAPER_REPORTED",  # peer-reviewable public paper (TPDS 2019, ISCA 2023)
    "VENDOR_CLAIMED",  # vendor spec/marketing figures (docs/product pages)
    "OFFICIAL_PUBLIC_PAGE",  # official public tracker page, non-normative (NCCL issue)
)

#: Source-id -> evidence grade.  Kept explicit so grade honesty is testable.
SOURCE_EVIDENCE_GRADES: dict[str, str] = {
    "PUB-NV-LI-TPDS19": "PAPER_REPORTED",
    "PUB-NV-TPU4-ICI23": "PAPER_REPORTED",
    "PUB-NV-GB200-UG": "VENDOR_CLAIMED",
    "PUB-NV-GB200-NVL72": "VENDOR_CLAIMED",
    "PUB-NV-NCCL-1054": "OFFICIAL_PUBLIC_PAGE",
}

#: ``as_reported`` strings stay crisp so every value stays reviewable.
MAX_AS_REPORTED_WORDS = 50

#: Free-parameter gap descriptions (what the sources do NOT say).
MAX_GAP_WORDS = 80

#: Value kinds that state the STRUCTURE of the design as the public sources
#: report it (counts, classes, defaults).  These and only these qualify for
#: the ``informational`` initial disposition; every other kind is a fact a
#: backend could in principle execute (an outcome figure, an observed
#: behavior), so with no binding in existence it stays ``unsupported`` —
#: the honest initial for a profile executed by nothing.
STRUCTURE_FACT_KINDS: tuple[str, ...] = (
    "DESIGN_CONSTANT",
    "DESIGN_CLASS",
    "DESIGN_DEFAULT",
)


def initial_disposition(value_kind: str) -> str:
    """The initial rule: structure facts informational, all else unsupported.

    Never returns an executed disposition (constraint /
    simulated_behavior / conformance_test) — those require a reviewed
    binding in :mod:`essun.specir.bindings`, and none exists for the
    NVLink-class family.  A promotion is a conscious change to the frozen
    counts in tests/specir/test_nvlink_paper_profile.py, never silent.
    """
    return "informational" if value_kind in STRUCTURE_FACT_KINDS else "unsupported"


@dataclass(frozen=True)
class NVDesignParameter:
    """One design parameter with its AS-REPORTED value and paper anchors.

    The profile's disposition-bearing requirement object: ``disposition``
    is required and drawn from the D1 vocabulary; free parameters
    (:class:`NVFreeParameter`) carry none by design.
    """

    parameter_id: str
    name: str
    category: str  # element of CATEGORIES
    value_kind: str  # element of VALUE_KINDS
    as_reported: str  # value as the public sources report it, own words
    unit: str  # "" for qualitative classes/behaviors
    anchor_ids: tuple[str, ...]
    evidence_grade: str  # element of EVIDENCE_GRADES, consistent with sources
    disposition: str  # element of DISPOSITIONS (D1; initial rule)
    notes: str = ""  # caveats, same-sentence numbers, pointers to FREE params


@dataclass(frozen=True)
class NVFreeCandidate:
    """A public figure nearest to a gap — anchored, never normative."""

    label: str
    anchor_id: str
    evidence_grade: str


@dataclass(frozen=True)
class NVFreeParameter:
    """A degree of freedom: the public sources are silent, so the value is
    FREE (never invent a value where sources are silent).  ``candidates``
    may record anchored public figures that sit closest to the gap without
    filling it."""

    parameter_id: str
    name: str
    category: str  # element of CATEGORIES
    gap: str  # what is NOT reported (the silence being marked)
    anchor_ids: tuple[str, ...]  # anchors evidencing the reported context
    candidates: tuple[NVFreeCandidate, ...] = field(default=())
    domain: str = "FREE"  # always FREE by construction


_PARAMETERS: tuple[NVDesignParameter, ...] = (
    # -- topology ------------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P01",
        name="nvswitch_crossbar_class",
        category="topology",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "Each NVSwitch is an 18x18 fully connected non-blocking "
            "crossbar; 8 of the 18 ports serve intra-baseboard "
            "communication."
        ),
        unit="",
        anchor_ids=("NVP-LI-2-NVSWITCH-CROSSBAR",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Same sentence continues: any of the 8 GPUs on one baseboard "
            "reaches any other at a full bandwidth of 50 GB/s x 6 switches "
            "= 300 GB/s via a single NVSwitch hop."
        ),
    ),
    NVDesignParameter(
        parameter_id="NVP-P02",
        name="dgx2_baseboards",
        category="topology",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "DGX-2 NVSwitch fabric: two baseboards, each containing 6 "
            "NVSwitches and hosting 8 GPUs."
        ),
        unit="baseboards; NVSwitches; GPUs",
        anchor_ids=("NVP-LI-2-DGX2-BASEBOARDS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P20",
        name="tpu_ici_topology",
        category="topology",
        value_kind="DESIGN_CLASS",
        as_reported=(
            "TPU v4 ICI (class member, not NVIDIA): a 3D torus with a "
            "built-in router per chip between ICI links; OCSes dynamically "
            "reconfigure the interconnect topology."
        ),
        unit="",
        anchor_ids=(
            "NVP-TPU4-0-OCS-TOPOLOGY",
            "NVP-TPU4-7.2-ICI-ROUTER",
        ),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    # -- link scale ----------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P03",
        name="nvswitch2_ports",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "NVSwitch (NVLink-V2 generation): a switch chip featuring 18 "
            "ports of NVLink for intra-node communication."
        ),
        unit="NVLink ports",
        anchor_ids=("NVP-LI-2-NVSWITCH-PORTS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P04",
        name="nvlink2_gpu_links",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "V100 GPU: 6 NVLink slots connecting to 6 NVSwitches "
            "simultaneously, at 50 GB/s bidirectional bandwidth per link."
        ),
        unit="NVLink slots; GB/s",
        anchor_ids=("NVP-LI-2-V100-LINKS-BW",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Same page: baseboard-to-baseboard raw bisection bandwidth 25 "
            "GB/s x 8 links/switch x 6 switches = 2.4 TB/s."
        ),
    ),
    NVDesignParameter(
        parameter_id="NVP-P05",
        name="nvlink1_gpu_links",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "P100 GPU: quad (4) NVLink slots; a dual-GPU system gangs all "
            "four for 4x single-link bandwidth."
        ),
        unit="NVLink slots",
        anchor_ids=("NVP-LI-2-P100-QUADSLOTS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P10",
        name="nvlink5_switch_capacity",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "NVLink5 switch system: 57.6 Tbps of full-duplex bandwidth in "
            "a 1U design."
        ),
        unit="Tbps",
        anchor_ids=("NVP-UG-1-SWITCH-57.6T",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
        notes="Spec ceiling on a vendor documentation page, never a measurement.",
    ),
    NVDesignParameter(
        parameter_id="NVP-P11",
        name="nvlink5_switch_ports",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "Each NVLink switch tray has 2 NVLink NVSwitch chips, each "
            "with 72 NVLink ports."
        ),
        unit="chips; NVLink ports",
        anchor_ids=("NVP-UG-1-SWITCH-PORTS",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P14",
        name="nvlink5_per_gpu_bw",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="Fifth-generation NVLink: 1.8 TB/s of GPU-to-GPU interconnect.",
        unit="TB/s",
        anchor_ids=("NVP-NVL72-1-PERGPU-1.8TB",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
        notes=(
            "Vendor spec ceiling (bidirectional class); the per-link rate "
            "is not stated — see NVP-F01."
        ),
    ),
    NVDesignParameter(
        parameter_id="NVP-P15",
        name="nvlink5_aggregate_bw",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "NVLink Switch System provides 130 TB/s of low-latency GPU "
            "communications across the 72-GPU domain."
        ),
        unit="TB/s",
        anchor_ids=("NVP-NVL72-1-AGGREGATE-130TB",),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
        notes="Aggregate spec ceiling; never an achieved value.",
    ),
    NVDesignParameter(
        parameter_id="NVP-P18",
        name="tpu_ici_links",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "TPU v4 ICI (class member, not NVIDIA): 6 links at 50 GB/s "
            "per chip; TPU v3 had 4 links at 70 GB/s."
        ),
        unit="links; GB/s",
        anchor_ids=("NVP-TPU4-5-T4-ICI-LINKS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P22",
        name="ici_vs_ib_bw",
        category="link_scale",
        value_kind="DESIGN_CONSTANT",
        as_reported="ICI link bandwidth is 2x IB: 400 vs 200 Gbit/s.",
        unit="Gbit/s",
        anchor_ids=("NVP-TPU4-7.3-ICI-VS-IB",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    # -- scale ---------------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P06",
        name="dgx1_dgx2_scales",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "DGX-1: 8 P100/V100 GPUs connected by NVLink; DGX-2: 16 GPUs "
            "connected by NVSwitch."
        ),
        unit="GPUs",
        anchor_ids=("NVP-LI-1-DGX-SIZES",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P12",
        name="gb200_rack_composition",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "DGX GB rack: 18x 1RU compute trays (2 Grace CPUs + 4 "
            "Blackwell GPUs each) and 9x 1RU NVLink switch trays."
        ),
        unit="trays",
        anchor_ids=(
            "NVP-UG-1-COMPUTE-TRAYS",
            "NVP-UG-1-SWITCH-TRAYS",
        ),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
        notes=(
            "The 18x4 multiplication yields the 72-GPU rack; the switch "
            "tier is 9 trays x 2 chips (NVP-P11)."
        ),
    ),
    NVDesignParameter(
        parameter_id="NVP-P13",
        name="nvlink5_domain",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "GB200 NVL72: 36 Grace CPUs and 72 Blackwell GPUs in one "
            "rack-scale design; a 72-GPU NVLink domain acting as a single, "
            "massive GPU."
        ),
        unit="GPUs; CPUs",
        anchor_ids=(
            "NVP-NVL72-1-RACK-COMPOSITION",
            "NVP-NVL72-1-DOMAIN-72",
        ),
        evidence_grade="VENDOR_CLAIMED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P19",
        name="tpu_ici_scale",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "TPU v4 (class member, not NVIDIA): largest scale "
            "configuration 4096 chips; TPU v3 reached 1024."
        ),
        unit="chips",
        anchor_ids=("NVP-TPU4-5-T4-SCALE",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
    ),
    NVDesignParameter(
        parameter_id="NVP-P21",
        name="nvswitch_two_level_scale",
        category="scale",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "Independent paper's NVSwitch characterization: electrical "
            "packet switching for 8 GPUs with one switch, up to 256 GPUs "
            "with two levels of switches."
        ),
        unit="GPUs",
        anchor_ids=("NVP-TPU4-7.2-NVSWITCH-256",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes=(
            "Cross-vendor (Google) view of NVSwitch-generation scale; the "
            "NVIDIA public pages in this set state no multi-rack domain "
            "(see NVP-F06)."
        ),
    ),
    # -- latency -------------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P07",
        name="nvlink2_p2p_latency",
        category="latency",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "Measured NVLink P2P start-up latency around 9 microseconds "
            "for directly connected nodes; manual-routing paths increase "
            "it about 2x (P100-DGX-1) to 3x (V100-DGX-1)."
        ),
        unit="µs",
        anchor_ids=("NVP-LI-3-NVLINK-LATENCY",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes=(
            "V100-era measured OUTCOME (cudaEvent microbenchmark, shortest "
            "message); not a per-hop decomposition and not current-gen — "
            "see NVP-F02."
        ),
    ),
    NVDesignParameter(
        parameter_id="NVP-P08",
        name="nvswitch_p2p_homogeneity",
        category="latency",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "Measured on DGX-2: all remote accesses are homogeneous for "
            "NVSwitch, confirming all-to-all fully-connected behavior."
        ),
        unit="",
        anchor_ids=("NVP-LI-3-NVSWITCH-HOMOG",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes=(
            "Same paragraph: cross-baseboard access incurs two switch "
            "hops, but the latency difference is very small, almost "
            "negligible."
        ),
    ),
    # -- routing -------------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P23",
        name="ocs_reconfig_timescale",
        category="routing",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "TPU v4's Palomar OCS reconfigures through 3D MEMS mirrors "
            "that switch in milliseconds."
        ),
        unit="ms (timescale)",
        anchor_ids=("NVP-TPU4-2.1-OCS-MS",),
        evidence_grade="PAPER_REPORTED",
        disposition="informational",
        notes="Reconfiguration timescale, not a data-path latency.",
    ),
    # -- performance ---------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P09",
        name="nvlink_numa_effects",
        category="performance",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "Four GPU-communication NUMA effect classes observed; three "
            "are triggered by NVLink's topology, connectivity, and "
            "routing, one by a PCIe chipset design issue."
        ),
        unit="effect classes",
        anchor_ids=("NVP-LI-1-NUMA-FOUR",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
    ),
    NVDesignParameter(
        parameter_id="NVP-P17",
        name="nccl_app_derating",
        category="performance",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "Maintainer guidance on the NCCL tracker: application-level "
            "NVLink bandwidth is roughly 80% of peak, due to NVLink "
            "packet overhead."
        ),
        unit="%",
        anchor_ids=("NVP-NCCL-1-DERATE-80",),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="unsupported",
        notes=(
            "The spec-to-measured derating bridge (calibration anchor "
            "CAL-A12's figure); an outcome-class claim, never an L0 input."
        ),
    ),
    NVDesignParameter(
        parameter_id="NVP-P24",
        name="twisted_torus_gain",
        category="performance",
        value_kind="REPORTED_MEASURE",
        as_reported=(
            "TPU v4 measured: the twisted torus improves all-to-all "
            "throughput by 1.63x (4x4x8 slice) and 1.31x (4x8x8) over the "
            "regular torus."
        ),
        unit="x",
        anchor_ids=("NVP-TPU4-4-TWIST-GAIN",),
        evidence_grade="PAPER_REPORTED",
        disposition="unsupported",
        notes=(
            "Topology-sensitivity falsifier for torus identities (the "
            "calibration track's CAL-A5)."
        ),
    ),
    # -- software ------------------------------------------------------------
    NVDesignParameter(
        parameter_id="NVP-P16",
        name="nccl_nvlink_model",
        category="software",
        value_kind="DESIGN_CONSTANT",
        as_reported=(
            "NCCL topo detection models an NVLink at 20 GB/s (src/graph/"
            "topo.h), yielding system->totalBw of 240 GB/s on an 8-GPU "
            "A100 against 300 GB/s physical."
        ),
        unit="GB/s",
        anchor_ids=(
            "NVP-NCCL-1-MODEL-20GB",
            "NVP-NCCL-1-TOTALBW-240",
        ),
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        disposition="informational",
        notes=(
            "The reference communication stack's internal constant "
            "(NVLink3-era A100), not a link specification."
        ),
    ),
)

_FREE_PARAMETERS: tuple[NVFreeParameter, ...] = (
    NVFreeParameter(
        parameter_id="NVP-F01",
        name="per_link_line_rate",
        category="link_scale",
        gap=(
            "No public source states a per-link NVLink5 line rate in "
            "GB/s; only the per-GPU (1.8 TB/s) and aggregate (130 TB/s) "
            "figures exist, and the per-GPU NVLink5 link count is itself "
            "not stated (72 switch ports per chip is a switch-side "
            "figure). Neither candidate below is a per-link NVLink5 rate."
        ),
        anchor_ids=(
            "NVP-NVL72-1-PERGPU-1.8TB",
            "NVP-NVL72-1-AGGREGATE-130TB",
            "NVP-LI-2-V100-LINKS-BW",
        ),
        candidates=(
            NVFreeCandidate(
                label="1.8 TB/s per GPU — vendor aggregate, scope not per-link",
                anchor_id="NVP-NVL72-1-PERGPU-1.8TB",
                evidence_grade="VENDOR_CLAIMED",
            ),
            NVFreeCandidate(
                label="50 GB/s bidirectional per link — NVLink-V2 generation, measured-paper scope",
                anchor_id="NVP-LI-2-V100-LINKS-BW",
                evidence_grade="PAPER_REPORTED",
            ),
        ),
    ),
    NVFreeParameter(
        parameter_id="NVP-F02",
        name="per_hop_latency_current_gen",
        category="latency",
        gap=(
            "NVIDIA publishes no per-hop or pair latency for "
            "current-generation NVLink/NVSwitch; the only public measured "
            "figures are V100-era P2P outcomes (~9 microseconds class), "
            "and no component breakdown exists in any cited source."
        ),
        anchor_ids=(
            "NVP-LI-3-NVLINK-LATENCY",
            "NVP-LI-3-NVSWITCH-HOMOG",
        ),
        candidates=(
            NVFreeCandidate(
                label="~9 µs direct P2P, 2-3x routed — V100-era measured outcome",
                anchor_id="NVP-LI-3-NVLINK-LATENCY",
                evidence_grade="PAPER_REPORTED",
            ),
        ),
    ),
    NVFreeParameter(
        parameter_id="NVP-F03",
        name="flow_control_mechanism",
        category="routing",
        gap=(
            "None of the five public sources describes the NVLink/"
            "NVSwitch flow-control or congestion mechanism; no window, "
            "credit, or backpressure law is public, so no admission term "
            "may be modeled for this family."
        ),
        anchor_ids=(
            "NVP-LI-2-NVSWITCH-CROSSBAR",
            "NVP-UG-1-SWITCH-57.6T",
        ),
    ),
    NVFreeParameter(
        parameter_id="NVP-F04",
        name="switch_fabric_wiring",
        category="topology",
        gap=(
            "How the 9 switch trays' 2x72-port NVLink5 chips wire the 72 "
            "GPUs (links per GPU on the switch side, fat-tree shape, "
            "oversubscription) is not public; only chip, tray, and "
            "aggregate-bandwidth figures appear."
        ),
        anchor_ids=(
            "NVP-UG-1-SWITCH-TRAYS",
            "NVP-UG-1-SWITCH-PORTS",
            "NVP-NVL72-1-PERGPU-1.8TB",
        ),
    ),
    NVFreeParameter(
        parameter_id="NVP-F05",
        name="packet_flit_format",
        category="routing",
        gap=(
            "No public NVLink packet or FLIT format, MTU, or header "
            "layout exists in any cited source; packet overhead is "
            "referenced only as an aggregate derating (NVP-P17)."
        ),
        anchor_ids=("NVP-NCCL-1-DERATE-80",),
    ),
    NVFreeParameter(
        parameter_id="NVP-F06",
        name="domain_scale_beyond_72",
        category="scale",
        gap=(
            "The public record fixes no NVLink domain beyond the 72-GPU "
            "NVL72 rack; whether and how NVLink domains compose beyond "
            "one rack is stated by none of the cited sources."
        ),
        anchor_ids=(
            "NVP-NVL72-1-DOMAIN-72",
            "NVP-TPU4-7.2-NVSWITCH-256",
        ),
        candidates=(
            NVFreeCandidate(
                label="up to 256 GPUs with two levels of switches — independent paper's NVSwitch-generation characterization",
                anchor_id="NVP-TPU4-7.2-NVSWITCH-256",
                evidence_grade="PAPER_REPORTED",
            ),
        ),
    ),
)


class ProfileObjectError(Exception):
    """Raised when an NVLink-class profile object fails validation."""


def parameters() -> tuple[NVDesignParameter, ...]:
    """All design-parameter objects of this stage."""
    return _PARAMETERS


def requirements() -> tuple[NVDesignParameter, ...]:
    """The profile's disposition-bearing requirement objects.

    For this paper-derived family the requirement objects ARE the design
    parameters (:class:`NVDesignParameter`, each carrying a D1 disposition);
    the alias matches the UnifiedBus stage module's accessor so coverage
    tooling and the profile builder read one shape.  Free parameters stay
    outside: declared freedom carries no disposition by design.
    """
    return _PARAMETERS


def free_parameters() -> tuple[NVFreeParameter, ...]:
    """All free-parameter objects of this stage."""
    return _FREE_PARAMETERS


def all_objects() -> tuple[NVDesignParameter | NVFreeParameter, ...]:
    """Design parameters and free parameters together."""
    return _PARAMETERS + _FREE_PARAMETERS


def anchor_ids() -> frozenset[str]:
    """Every anchor id cited by any object, including free candidates."""
    ids = {aid for obj in all_objects() for aid in obj.anchor_ids}
    for obj in _FREE_PARAMETERS:
        ids.update(cand.anchor_id for cand in obj.candidates)
    return frozenset(ids)


def by_category(category: str) -> tuple[NVDesignParameter | NVFreeParameter, ...]:
    """All objects (parameters and free parameters) in one category."""
    return tuple(obj for obj in all_objects() if obj.category == category)


def load_registry(
    path: Path | str = REGISTRY_PATH,
    repo_root: Path | str = REPO_ROOT,
) -> "PaperAnchorRegistry":
    """Load and verify THIS family's paper-anchor registry."""
    from .unifiedbus_sources import PaperAnchorRegistry

    registry = PaperAnchorRegistry.load(path=path, repo_root=Path(repo_root))
    registry.assert_valid()  # sha256 + quote re-match, PUBLIC_READ gate
    return registry


def _shape_problems(obj: NVDesignParameter | NVFreeParameter) -> list[str]:
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
    if isinstance(obj, NVDesignParameter):
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
                isinstance(obj, NVDesignParameter)
                and obj.evidence_grade != grade
            ):
                problems.append(
                    f"{oid}: evidence grade {obj.evidence_grade!r} not "
                    f"derivable from anchor {anchor.anchor_id} "
                    f"(source grade {grade!r})"
                )
        if isinstance(obj, NVFreeParameter):
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
            f"NVLink-class paper profile objects failed validation: "
            f"{detail}{more}"
        )
