"""NVLink-class paper-profile -> platform capability map (M1 stage S3).

Maps every M1 object (24 design parameters ``NVP-P01..P24`` + 6 free
parameters ``NVP-F01..F06`` of
:mod:`essun.specir.nvlink_paper_profile`) onto what the platform can
actually run, in exactly three buckets (the UnifiedBus S3 shape,
third fabric):

- ``L0_READY`` — consumable TODAY by a landed L0 analytical backend knob
  (``ranks``, per-fabric bandwidth/latency), or by the workload-side
  selection.  Numeric bandwidth/latency values remain FREE parameters
  (NVP-F01/F02): the anchored counts and ceilings supply structure,
  never a derived Gbit/s figure.
- ``L1_L2_REQUIRED`` — within the platform's multi-fidelity plan
  (L1 flow/collective, L2 packet/FLIT) but NO such backend has landed;
  nothing in this bucket is runnable today.  ``needed_fidelity`` names
  the lowest class that could honestly host it.
- ``UNSUPPORTED`` — the platform CANNOT represent it today and no
  landed-or-planned fidelity class in the current plan covers it;
  declared loudly with a ``reason_kind``.

Honesty rules enforced structurally (mirroring the UnifiedBus S3):

- PAPER-DERIVED, NOT NORMATIVE: this maps a paper-derived design profile;
  no public NVLink/NVSwitch specification exists (licensee/NDA-gated
  track, never fetched).
- Evidence grades pass through: every design entry must echo its S2
  ``evidence_grade`` exactly, so a VENDOR_CLAIMED figure can never be
  silently mixed into a comparison as a neutral fact (:func:`check`).
- L0 targets are pinned to REAL landed code: each target names a backend
  id, a topology class, and a knob that must resolve to a field of that
  backend's config dataclass (imported from
  :mod:`essun.backends.analytical`), so the mapping cannot drift from the
  backends it claims to feed.
- Exact coverage: every S2 object is mapped, nothing else is (checked in
  :func:`coverage_problems` / :func:`assert_valid`).

The three-architecture comparison (M1 stage S4) consumes this map: the
NVLink-paper flavor's crossbar identity is backed by the L0_READY rows
for ``NVP-P01`` (the paper-reported non-blocking crossbar structure) and
``NVP-P13`` (the 72-GPU domain scale); this module is pure mapping and
runs nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from essun.backends.analytical import l0, l0_crossbar, l0_recursive_doubling, l0_torus2d
from essun.specir import nvlink_paper_profile as _profile

#: The three buckets (same as the UnifiedBus S3).
BUCKETS: tuple[str, ...] = ("L0_READY", "L1_L2_REQUIRED", "UNSUPPORTED")

#: How an L0_READY entry feeds the platform today.
L0_ROLES: tuple[str, ...] = (
    "rank_scale",  # anchored number sets the rank count (flat sense)
    "bandwidth_derivation",  # counts/ceilings constrain B via free rates (F01)
    "topology_class_approximation",  # design class approximated by a landed identity
    "free_parameter_gate",  # the free parameter itself gates L0 knobs
)

#: Lowest fidelity class that could honestly host an L1_L2_REQUIRED entry.
NEEDED_FIDELITIES: tuple[str, ...] = (
    "L1_flow_collective",  # flow/collective-level structure (topology classes, strategies)
    "L2_packet_flit",  # packet/FLIT-level detail (switch structure, headers, CC)
)

#: Why an UNSUPPORTED entry cannot be represented.
REASON_KINDS: tuple[str, ...] = (
    "physical_deployment_cost",  # trays, packaging — no cost/deployment model
    "design_context",  # comparative/philosophical claim, not a simulable quantity
    "software_surface",  # communication-stack software, outside the fidelity ladder
)

#: Landed analytical backends the map may target (id -> config dataclass).
_BACKEND_CONFIGS = {
    l0.BACKEND_ID: l0.InfraConfig,
    l0_crossbar.BACKEND_ID: l0_crossbar.CrossbarConfig,
    l0_torus2d.BACKEND_ID: l0_torus2d.Torus2DConfig,
    l0_recursive_doubling.BACKEND_ID: l0_recursive_doubling.RecursiveDoublingConfig,
}

#: Topology classes each targeted backend is declared for.  Mirrors
#: orchestrator/runs.py DISPATCH for these ids; tests cross-check for drift.
BACKEND_TOPOLOGY_CLASSES = {
    l0.BACKEND_ID: ("unidirectional_ring",),
    l0_crossbar.BACKEND_ID: ("fully_connected_crossbar",),
    l0_torus2d.BACKEND_ID: ("torus2d_ring_x_ring",),
    l0_recursive_doubling.BACKEND_ID: ("fully_connected_exchange",),
}

#: What kind of quantity a knob is (role/knob consistency is checked).
_KNOB_KINDS = {
    "ranks": "rank",
    "link.bytes_per_ns": "bandwidth",
    "nic.injection_bytes_per_ns": "bandwidth",
    "link.hop_latency_ns": "latency",
    "link.pair_latency_ns": "latency",
    "grid.dim1_ranks": "shape",
    "grid.dim2_ranks": "shape",
}

#: Which knob kinds each L0 role may target.
_ROLE_KNOB_KINDS = {
    "rank_scale": frozenset({"rank", "shape"}),
    "bandwidth_derivation": frozenset({"bandwidth"}),
    "topology_class_approximation": frozenset({"rank", "shape"}),
    "free_parameter_gate": frozenset({"bandwidth", "latency"}),
}

MAX_HOW_WORDS = 90
MAX_NOTES_WORDS = 60


@dataclass(frozen=True)
class NVPlatformTarget:
    """One landed backend knob an L0_READY entry feeds."""

    backend_id: str
    topology_class: str
    knob: str  # dotted YAML key of the backend's infra file
    note: str = ""


@dataclass(frozen=True)
class NVPlatformMapping:
    """One S2 object's mapping onto the platform capability surface."""

    parameter_id: str
    bucket: str  # element of BUCKETS
    evidence_grade: str  # echo of the S2 design parameter's grade; "" for frees
    how: str  # bounded prose: what maps where, and what does not
    l0_role: str = ""  # L0_READY only, element of L0_ROLES
    targets: tuple[NVPlatformTarget, ...] = field(default=())
    needed_fidelity: str = ""  # L1_L2_REQUIRED only, element of NEEDED_FIDELITIES
    reason_kind: str = ""  # UNSUPPORTED only, element of REASON_KINDS
    notes: str = ""


# Convenience shorthands for the entry bodies below.
def _ring(knob: str, note: str = "") -> NVPlatformTarget:
    return NVPlatformTarget("analytical_l0", "unidirectional_ring", knob, note)


def _crossbar(knob: str, note: str = "") -> NVPlatformTarget:
    return NVPlatformTarget("analytical_l0_crossbar", "fully_connected_crossbar", knob, note)


def _torus(knob: str, note: str = "") -> NVPlatformTarget:
    return NVPlatformTarget("analytical_l0_torus2d", "torus2d_ring_x_ring", knob, note)


def _rd(knob: str, note: str = "") -> NVPlatformTarget:
    return NVPlatformTarget(
        "analytical_l0_recursive_doubling", "fully_connected_exchange", knob, note
    )


_BW_TARGETS = (
    _ring("link.bytes_per_ns"),
    _crossbar("nic.injection_bytes_per_ns"),
    _torus("link.bytes_per_ns"),
    _rd("nic.injection_bytes_per_ns"),
)

_LAT_TARGETS = (
    _ring("link.hop_latency_ns"),
    _crossbar("link.pair_latency_ns"),
    _torus("link.hop_latency_ns"),
    _rd("link.pair_latency_ns"),
)

_MAPPINGS: tuple[NVPlatformMapping, ...] = (
    # ------------------------------------------------------------------ L0_READY
    NVPlatformMapping(
        parameter_id="NVP-P01",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="topology_class_approximation",
        how=(
            "The paper-reported structure of the NVSwitch fabric IS the "
            "landed fully-connected crossbar identity: an 18x18 "
            "non-blocking crossbar with homogeneous remote access (the "
            "same paper's measured homogeneity).  The identity assumes "
            "pairwise adjacency, uniform pair latency, and single-port "
            "injection (A-L0X-PORT/A-L0X-LAT assumptions); per-pair "
            "bandwidth split and switch internals stay out (NVP-F04, "
            "L2).  This is the M1 comparison's NV-flavor identity anchor."
        ),
        targets=(
            _crossbar("ranks", "switched all-to-all domain, one logical hop"),
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P04",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="bandwidth_derivation",
        how=(
            "6 links x 50 GB/s per V100 GPU bounds every per-rank "
            "bandwidth knob of an NVLink2-flavored run as B = 6 x "
            "per-link rate with the generation scope stated; the "
            "NVLink5-era rate is FREE (NVP-F01), and this figure is a "
            "recorded candidate with its PAPER_REPORTED grade, never "
            "silently applied."
        ),
        targets=_BW_TARGETS,
    ),
    NVPlatformMapping(
        parameter_id="NVP-P05",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="bandwidth_derivation",
        how=(
            "Quad NVLink slots per P100 GPU bound B = 4 x per-link rate "
            "for an NVLink1-flavored run; same rule as NVP-P04, "
            "generation scope stated, rate still a recorded choice."
        ),
        targets=_BW_TARGETS,
    ),
    NVPlatformMapping(
        parameter_id="NVP-P06",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="rank_scale",
        how=(
            "8 (DGX-1) and 16 (DGX-2) set flat rank counts directly; the "
            "DGX-2 two-baseboard structure behind its 16 is NOT "
            "representable at L0 and stays L1 (NVP-P02)."
        ),
        targets=(
            _crossbar("ranks", "single switched node"),
            _ring("ranks"),
            _torus("ranks"),
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P13",
        bucket="L0_READY",
        evidence_grade="VENDOR_CLAIMED",
        l0_role="rank_scale",
        how=(
            "72 sets the rank count of any flat NVLink5-flavored L0 "
            "fabric directly, with the crossbar identity as the "
            "structural match for the single-switched-domain claim "
            "(vendor grade carried).  The committed three-architecture "
            "comparison runs at the ONE shared workload's tp=64, so its "
            "NV flavor states 64 as a matched-free choice against this "
            "anchored 72 — the asymmetry is printed in the flavor file, "
            "never hidden."
        ),
        targets=(
            _crossbar("ranks", "one 72-GPU switched domain"),
            _ring("ranks"),
            _torus("ranks"),
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P14",
        bucket="L0_READY",
        evidence_grade="VENDOR_CLAIMED",
        l0_role="bandwidth_derivation",
        how=(
            "1.8 TB/s per GPU enters only as an anchored NVP-F01 "
            "candidate whose per-link scope the source does not state; a "
            "run built on it must record the choice and the "
            "VENDOR_CLAIMED grade as a free-parameter assumption — a "
            "spec ceiling, never a measured rate."
        ),
        targets=_BW_TARGETS,
    ),
    NVPlatformMapping(
        parameter_id="NVP-P15",
        bucket="L0_READY",
        evidence_grade="VENDOR_CLAIMED",
        l0_role="bandwidth_derivation",
        how=(
            "130 TB/s aggregate is a domain-level ceiling; it is never "
            "divided down to per-rank B by the platform (that division "
            "is a derivation the source does not make).  It anchors the "
            "F01 candidate list as context with the vendor grade "
            "carried."
        ),
        targets=_BW_TARGETS,
    ),
    NVPlatformMapping(
        parameter_id="NVP-P18",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="bandwidth_derivation",
        how=(
            "The class member's per-link figure IS public (6 links @ 50 "
            "GB/s per TPU v4 chip), the one place this family states a "
            "rate; an ICI-flavored run may anchor B = 6 x 50 GB/s with "
            "the counting-convention caveat (bidirectional vs "
            "per-direction class) stated.  No committed run consumes it "
            "today."
        ),
        targets=_BW_TARGETS,
    ),
    NVPlatformMapping(
        parameter_id="NVP-P19",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="rank_scale",
        how=(
            "4096 sets a flat rank count directly; the 3D-torus "
            "structure it lives in is NOT representable at L0 (torus2d "
            "is 2D; see NVP-P20), so a flat run states the lost "
            "structure loudly."
        ),
        targets=(
            _ring("ranks", "flat 4096, 3D structure lost"),
            _torus("ranks", "flat count"),
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-F01",
        bucket="L0_READY",
        evidence_grade="",
        l0_role="free_parameter_gate",
        how=(
            "Gates every bandwidth knob: no public per-link NVLink5 "
            "rate exists, so B stays a recorded free assumption in any "
            "NV-flavored run; the anchored candidates (1.8 TB/s per GPU "
            "vendor; 50 GB/s per link, V100-era paper) keep their own "
            "grades if used."
        ),
        targets=_BW_TARGETS,
    ),
    NVPlatformMapping(
        parameter_id="NVP-F02",
        bucket="L0_READY",
        evidence_grade="",
        l0_role="free_parameter_gate",
        how=(
            "Gates every latency knob: no public current-gen per-hop or "
            "pair latency exists (only V100-era measured outcomes), so L "
            "stays free; decomposition into per-link/per-switch "
            "components becomes possible only at L2."
        ),
        targets=_LAT_TARGETS,
    ),
    # ---------------------------------------------------------- L1_L2_REQUIRED
    NVPlatformMapping(
        parameter_id="NVP-P02",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "Two baseboards x 6 NVSwitches hosting 8 GPUs each is "
            "switch-level fabric structure; L0 abstracts switches away "
            "(the crossbar identity assumes the non-blocking function), "
            "so this needs switch-structure fidelity (L2), with the "
            "port wiring itself FREE (NVP-F04)."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P03",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "18 NVLink ports per NVSwitch chip is switch capacity; at L0 "
            "switches are abstracted away entirely, so this figure has "
            "no knob and needs switch-level (L2) modeling."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P07",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "The ~9 microsecond V100-era P2P latency is a measured "
            "OUTCOME, not an input: it cannot set any L0 knob (NVP-F02 "
            "blocks the per-hop decomposition and the generation is "
            "two generations old).  Usable only as a future calibration "
            "target, with the paper grade carried."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P08",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "The measured homogeneity of NVSwitch remote access is "
            "exactly what the crossbar identity ASSUMES (NVP-P01); "
            "verifying an identity against it needs flow-level "
            "fidelity.  At L0 it is context for the identity's validity "
            "domain, never a knob."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P09",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "NUMA-effect classes are OUTCOMES of topology plus routing "
            "under placement; at L0 hop counts are identity constants, "
            "never emergent, so these classes can only be observed once "
            "routing fidelity exists (L1) or per-path detail (L2)."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P10",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_packet_flit",
        how=(
            "57.6 Tbps full-duplex per switch system is switch-device "
            "capacity; device-level capacities are packet-fidelity "
            "content, and as a whole-domain ceiling it additionally "
            "bounds any B choice only through a recorded free-parameter "
            "assumption (NVP-F01), never automatically."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P17",
        bucket="L1_L2_REQUIRED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        needed_fidelity="L1_flow_collective",
        how=(
            "The ~80% app-level derating is a software-stack scheduling "
            "fact: L0 identities consume physical B and any derating is "
            "a recorded free assumption; hosting the derating mechanism "
            "itself needs collective-level software modeling (L1)."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P20",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "A 3D torus with per-chip routers exceeds every landed L0 "
            "identity (torus2d is 2D; no per-chip routing exists); "
            "honest representation needs flow-level topology or a "
            "not-yet-landed 3D identity.  OCS reconfiguration dynamics "
            "additionally need failure/topology-change modeling (see "
            "NVP-P23)."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P21",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Two levels of NVSwitch switches (up to 256 GPUs) are a "
            "switch hierarchy; no landed topology class represents a "
            "hierarchy (a flat 256-rank run would silently delete the "
            "two-level structure — not done)."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P23",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Millisecond OCS reconfiguration is topology-change "
            "dynamics; no landed or pinned backend has topology "
            "reconfiguration, and the ms timescale is three orders "
            "above data-path latencies — needs the L1 strategy track "
            "plus topology-change modeling."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P24",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "The 1.63x/1.31x twisted-torus all-to-all gains are measured "
            "topology effects; no landed identity executes all-to-all or "
            "a bisection-bound collective (the standing CAL-A5 "
            "falsifier), so these figures are calibration targets, not "
            "inputs."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-F03",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "Flow-control silence: every landed backend declares "
            "congestion and credit flow control explicitly unsupported; "
            "at L2 any NV-side flow-control choice remains a free "
            "assumption because the public text is silent.  This gate "
            "is why the matrix's NVLink columns carry no window."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-F04",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "Switch-fabric wiring (links per GPU on the switch side, "
            "fat-tree shape, oversubscription) is topology detail below "
            "every landed abstraction; needed before any L2 "
            "switch-structure model of the NVL72 rack."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-F05",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "Packet/FLIT format silence gates any L2 packet-format "
            "modeling; even at L2 the format would be a declared free "
            "assumption, never a paper-derived value."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-F06",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L1_flow_collective",
        how=(
            "No public NVLink domain beyond the 72-GPU rack: any larger "
            "NV-flavored identity is a declared free stand-in (the "
            "comparison states this where relevant), and multi-rack "
            "composition needs hierarchy fidelity nothing landed "
            "provides."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P11",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_packet_flit",
        how=(
            "72 NVLink ports per NVLink5 switch chip is switch-device "
            "capacity (the NVSwitch-generation counterpart of NVP-P03's "
            "18); at L0 switches are abstracted away entirely, so it "
            "needs switch-level (L2) modeling and never parameterizes a "
            "landed knob."
        ),
    ),
    # ------------------------------------------------------------- UNSUPPORTED
    NVPlatformMapping(
        parameter_id="NVP-P12",
        bucket="UNSUPPORTED",
        evidence_grade="VENDOR_CLAIMED",
        reason_kind="physical_deployment_cost",
        how=(
            "Rack/tray composition (18 compute trays, 9 switch trays) is "
            "packaging and deployment structure; its arithmetic role "
            "(18x4 = 72 GPUs) is carried by the rank-scale row NVP-P13, "
            "and no landed or planned backend models trays, power, or "
            "liquid cooling."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P22",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="design_context",
        how=(
            "The ICI-vs-IB comparative claim (400 vs 200 Gbit/s) is "
            "context about a different (scale-out) interconnect; the "
            "ICI figure itself is carried by NVP-P18, and the "
            "comparison parameterizes nothing here."
        ),
    ),
    NVPlatformMapping(
        parameter_id="NVP-P16",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "NCCL's internal NVLink bandwidth model (20 GB/s per link, "
            "240 GB/s totalBw on 8x A100) is a constant inside the "
            "communication stack's topology detection, not a fabric "
            "parameter; the platform simulates fabrics, not the "
            "software stack's detection heuristics (its derating "
            "consequence is carried separately by NVP-P17)."
        ),
    ),
)


class PlatformMapError(Exception):
    """Raised when the platform map fails validation."""


def entries() -> tuple[NVPlatformMapping, ...]:
    """All mapping entries."""
    return _MAPPINGS


def by_bucket(bucket: str) -> tuple[NVPlatformMapping, ...]:
    """All entries in one bucket."""
    if bucket not in BUCKETS:
        raise ValueError(f"unknown bucket {bucket!r} (not in {BUCKETS})")
    return tuple(entry for entry in _MAPPINGS if entry.bucket == bucket)


def _knob_field_ok(config_cls, knob: str) -> bool:
    from dataclasses import fields as dataclass_fields

    names = {f.name for f in dataclass_fields(config_cls)}
    return knob.replace(".", "_") in names or knob.rsplit(".", 1)[-1] in names


def _entry_problems(entry: NVPlatformMapping, grades: dict[str, str]) -> list[str]:
    problems: list[str] = []
    eid = entry.parameter_id
    if eid not in grades:
        problems.append(f"{eid}: not an S2 profile object id")
        return problems
    if entry.bucket not in BUCKETS:
        problems.append(f"{eid}: unknown bucket {entry.bucket!r} (not in {BUCKETS})")
        return problems
    words = len(entry.how.split())
    if words == 0:
        problems.append(f"{eid}: empty how")
    elif words > MAX_HOW_WORDS:
        problems.append(f"{eid}: how has {words} words (> {MAX_HOW_WORDS})")
    if len(entry.notes.split()) > MAX_NOTES_WORDS:
        problems.append(f"{eid}: notes over {MAX_NOTES_WORDS} words")
    # Evidence-grade passthrough: design entries echo S2 exactly; frees stay "".
    expected_grade = grades[eid]
    if entry.evidence_grade != expected_grade:
        problems.append(
            f"{eid}: evidence grade {entry.evidence_grade!r} does not echo the "
            f"S2 object grade {expected_grade!r} (no laundering)"
        )
    if entry.bucket == "L0_READY":
        if entry.l0_role not in L0_ROLES:
            problems.append(f"{eid}: unknown l0_role {entry.l0_role!r}")
        if entry.needed_fidelity or entry.reason_kind:
            problems.append(f"{eid}: L0_READY entry carries L1L2/UNSUPPORTED fields")
        if not entry.targets:
            problems.append(f"{eid}: L0_READY entry needs targets")
        allowed_kinds = _ROLE_KNOB_KINDS.get(entry.l0_role, frozenset())
        for target in entry.targets:
            if target.backend_id not in _BACKEND_CONFIGS:
                problems.append(
                    f"{eid}: target backend {target.backend_id!r} is not a "
                    "landed analytical backend"
                )
                continue
            if target.topology_class not in BACKEND_TOPOLOGY_CLASSES[target.backend_id]:
                problems.append(
                    f"{eid}: topology class {target.topology_class!r} not "
                    f"declared for {target.backend_id}"
                )
            if not _knob_field_ok(_BACKEND_CONFIGS[target.backend_id], target.knob):
                problems.append(
                    f"{eid}: knob {target.knob!r} does not resolve to a "
                    f"config field of {target.backend_id}"
                )
            knob_kind = _KNOB_KINDS.get(target.knob)
            if knob_kind is None:
                problems.append(f"{eid}: knob {target.knob!r} not in knob vocabulary")
            elif knob_kind not in allowed_kinds:
                problems.append(
                    f"{eid}: l0_role {entry.l0_role!r} may not target "
                    f"{knob_kind}-kind knob {target.knob!r}"
                )
    elif entry.bucket == "L1_L2_REQUIRED":
        if entry.needed_fidelity not in NEEDED_FIDELITIES:
            problems.append(
                f"{eid}: needed_fidelity {entry.needed_fidelity!r} not in "
                f"{NEEDED_FIDELITIES}"
            )
        if entry.targets or entry.l0_role or entry.reason_kind:
            problems.append(f"{eid}: L1_L2_REQUIRED entry carries L0/UNSUPPORTED fields")
    else:  # UNSUPPORTED
        if entry.reason_kind not in REASON_KINDS:
            problems.append(f"{eid}: reason_kind {entry.reason_kind!r} not in {REASON_KINDS}")
        if (
            entry.targets
            or entry.l0_role
            or entry.needed_fidelity
        ):
            problems.append(f"{eid}: UNSUPPORTED entry carries L0/L1L2 fields")
    return problems


def check(entries: Optional[tuple[NVPlatformMapping, ...]] = None) -> list[str]:
    """Structurally validate a mapping list. Returns all problems; empty = valid."""
    from dataclasses import fields as dataclass_fields  # noqa: F401  (parity with UB)

    checked = _MAPPINGS if entries is None else entries
    grades = {
        obj.parameter_id: (
            obj.evidence_grade if isinstance(obj, _profile.NVDesignParameter) else ""
        )
        for obj in _profile.all_objects()
    }
    problems: list[str] = []
    seen: dict[str, int] = {}
    for entry in checked:
        seen[entry.parameter_id] = seen.get(entry.parameter_id, 0) + 1
        problems.extend(_entry_problems(entry, grades))
    problems.extend(
        f"duplicate mapping id {eid} ({count} entries)"
        for eid, count in sorted(seen.items())
        if count > 1
    )
    return problems


def coverage_problems(entries: Optional[tuple[NVPlatformMapping, ...]] = None) -> list[str]:
    """Exact-coverage check: every S2 object mapped, nothing else."""
    checked = _MAPPINGS if entries is None else entries
    mapped = {entry.parameter_id for entry in checked}
    profile_ids = {obj.parameter_id for obj in _profile.all_objects()}
    problems: list[str] = []
    for missing in sorted(profile_ids - mapped):
        problems.append(f"S2 object {missing} has no platform mapping")
    for extra in sorted(mapped - profile_ids):
        problems.append(f"mapped id {extra} is not an S2 profile object")
    return problems


def assert_valid() -> None:
    """Raise :class:`PlatformMapError` if any check fails (structure + coverage)."""
    problems = check() + coverage_problems()
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise PlatformMapError(
            f"NVLink-class platform map failed validation: {detail}{more}"
        )
