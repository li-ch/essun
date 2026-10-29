"""UnifiedBus paper-profile -> platform capability map (Q6 stage S3).

Maps every stage-S2 object (54 design parameters ``UBP-P01..P54`` + 8 free
parameters ``UBP-F01..F08`` of
:mod:`essun.specir.unifiedbus_paper_profile`) onto what the platform can
actually run, in exactly three buckets (stage prompt wording):

- ``L0_READY`` — consumable TODAY by a landed L0 analytical backend knob
  (``ranks``, per-fabric bandwidth/latency, torus grid shape), or by the
  workload-side selection (W1).  Numeric bandwidth/latency values remain
  FREE parameters (UBP-F01/F02): the anchored lane counts supply structure,
  never a standard-derived Gbit/s figure.
- ``L1_L2_REQUIRED`` — within the platform's multi-fidelity plan
  (L1 flow/collective, L2 packet/FLIT) but NO such backend has landed;
  nothing in this bucket is runnable today.  ``needed_fidelity`` names the
  lowest class that could honestly host it;
  ``L2_memory_semantic_unpinned`` marks content that additionally has no
  pinned backend at all (the memory-semantic scale-up track stays
  license-gated, HUM-02/D-008).
- ``UNSUPPORTED`` — the platform CANNOT represent it today and no
  landed-or-planned fidelity class in the current plan covers it; declared
  loudly with a ``reason_kind`` (software surface, physical deployment /
  cost, reliability dynamics, application outcome, design context,
  scale-out scope, unquantified claim).

Honesty rules enforced structurally (mirroring S2):

- PAPER-DERIVED, NOT NORMATIVE: this maps a paper-derived design profile;
  the UnifiedBus specification track stays license-gated (license review pending).
- Evidence grades pass through: every design entry must echo its S2
  ``evidence_grade`` exactly, so a VENDOR_CLAIMED figure can never be
  silently mixed into a comparison as a neutral fact (:func:`check`).
- L0 targets are pinned to REAL landed code: each target names a backend
  id, a topology class, and a knob that must resolve to a field of that
  backend's config dataclass (imported from
  :mod:`essun.backends.analytical`), so the mapping cannot drift from the
  backends it claims to feed.  The ASTRA-sim analytical adapter is
  deliberately not targeted: it translates the same ring knobs but adds no
  representational power for UnifiedBus-specific content (congestion and
  scale-up memory semantics are in its ``explicitly_unsupported``).
- Exact coverage: every S2 object is mapped, nothing else is (checked in
  :func:`coverage_problems` / :func:`assert_valid`).

Stage S4 consumes this map to build the UEC-flavored vs
UnifiedBus-paper-flavored L0 comparison with equal free parameters where
honest; this module is pure mapping and runs nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Optional

from essun.backends.analytical import l0, l0_crossbar, l0_recursive_doubling, l0_torus2d
from essun.specir import unifiedbus_paper_profile as _profile
from essun.workload import w1, w2

#: The three buckets, in stage-prompt order.
BUCKETS: tuple[str, ...] = ("L0_READY", "L1_L2_REQUIRED", "UNSUPPORTED")

#: How an L0_READY entry feeds the platform today.
L0_ROLES: tuple[str, ...] = (
    "rank_scale",  # anchored number sets the rank count (flat sense)
    "bandwidth_derivation",  # lane counts constrain B via free per-lane rate (F01)
    "topology_class_approximation",  # design class approximated by a landed identity
    "workload_scoping",  # consumed at workload-selection time (no infra knob)
    "free_parameter_gate",  # the free parameter itself gates L0 knobs
)

#: Lowest fidelity class that could honestly host an L1_L2_REQUIRED entry.
NEEDED_FIDELITIES: tuple[str, ...] = (
    "L1_flow_collective",  # flow/collective-level structure (topology classes, routing strategies)
    "L2_packet_flit",  # packet/FLIT-level detail (switch structure, headers, VLs, CC)
    "L2_memory_semantic_unpinned",  # load/store scale-up semantics; NO pinned backend exists
)

#: Why an UNSUPPORTED entry cannot be represented.
REASON_KINDS: tuple[str, ...] = (
    "software_surface",  # host OS / driver / service software, outside the fidelity ladder
    "physical_deployment_cost",  # cables, packaging, CapEx — no cost/deployment model
    "reliability_dynamics",  # failure/failover/MTBF — no failure model landed or pinned
    "application_outcome",  # training-level outcome metrics — no compute/training model
    "design_context",  # design-philosophy claim, not a simulable quantity
    "scale_out_scope",  # scale-out (DCN/SuperCluster) domain, outside scale-up scope
    "unquantified_claim",  # level-scope claim with no settable number
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

#: Workload kinds a workload_scoping entry may name.
ALLOWED_WORKLOAD_KINDS = (w1.WORKLOAD_KIND, w2.WORKLOAD_KIND)

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
class UBPlatformTarget:
    """One landed backend knob an L0_READY entry feeds."""

    backend_id: str
    topology_class: str
    knob: str  # dotted YAML key of the backend's infra file
    note: str = ""


@dataclass(frozen=True)
class UBPlatformMapping:
    """One S2 object's mapping onto the platform capability surface."""

    parameter_id: str
    bucket: str  # element of BUCKETS
    evidence_grade: str  # echo of the S2 design parameter's grade; "" for frees
    how: str  # bounded prose: what maps where, and what does not
    l0_role: str = ""  # L0_READY only, element of L0_ROLES
    targets: tuple[UBPlatformTarget, ...] = field(default=())
    workload_kinds: tuple[str, ...] = field(default=())  # workload_scoping only
    needed_fidelity: str = ""  # L1_L2_REQUIRED only, element of NEEDED_FIDELITIES
    reason_kind: str = ""  # UNSUPPORTED only, element of REASON_KINDS
    notes: str = ""


# Convenience shorthands for the entry bodies below.
def _ring(knob: str, note: str = "") -> UBPlatformTarget:
    return UBPlatformTarget("analytical_l0", "unidirectional_ring", knob, note)


def _crossbar(knob: str, note: str = "") -> UBPlatformTarget:
    return UBPlatformTarget("analytical_l0_crossbar", "fully_connected_crossbar", knob, note)


def _torus(knob: str, note: str = "") -> UBPlatformTarget:
    return UBPlatformTarget("analytical_l0_torus2d", "torus2d_ring_x_ring", knob, note)


def _rd(knob: str, note: str = "") -> UBPlatformTarget:
    return UBPlatformTarget(
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

_MAPPINGS: tuple[UBPlatformMapping, ...] = (
    # ------------------------------------------------------------------ L0_READY
    UBPlatformMapping(
        parameter_id="UBP-P06",
        bucket="L0_READY",
        evidence_grade="VENDOR_CLAIMED",
        l0_role="topology_class_approximation",
        how=(
            "Switch-free direct 16-NPU interconnect is the fully-connected "
            "crossbar identity at ranks=16: the identity needs only pairwise "
            "adjacency, uniform pair latency, and single-port injection "
            "(A-L0X-PORT/A-L0X-LAT assumptions), all of which direct links "
            "satisfy in function; per-pair bandwidth split across 16 peers is "
            "not public, so B/L stay free (F01/F02). Vendor grade carried."
        ),
        targets=(
            _crossbar("ranks", "16 NPUs pairwise adjacent, no switch stage"),
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P07",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="bandwidth_derivation",
        how=(
            "x72 lanes per NPU bounds every per-rank bandwidth knob as "
            "B = 72 x per-lane rate, but the per-lane rate is FREE (UBP-F01), "
            "so the anchored lane count supplies structure only: the numeric "
            "B is a recorded free-parameter assumption, never a "
            "standard-derived value."
        ),
        targets=_BW_TARGETS,
    ),
    UBPlatformMapping(
        parameter_id="UBP-P16",
        bucket="L0_READY",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        l0_role="bandwidth_derivation",
        how=(
            "224/256 Gbit/s enters only as an anchored UBP-F01 candidate "
            "whose scope (per-lane vs per-port) the source does not state; a "
            "run built on it must record the rate choice and its "
            "OFFICIAL_PUBLIC_PAGE grade as a free-parameter assumption."
        ),
        targets=_BW_TARGETS,
    ),
    UBPlatformMapping(
        parameter_id="UBP-P17",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="rank_scale",
        how=(
            "64 sets the rank count of any flat L0 fabric directly; the "
            "crossbar identity is the structural match for the intra-rack "
            "full-mesh level (the LRS plane's non-blocking function is what "
            "it assumes). NPUs doubling as routers (indirect routes) are "
            "outside every landed identity."
        ),
        targets=(
            _crossbar("ranks", "rack scope = one full-mesh level"),
            _ring("ranks"),
            _torus("ranks"),
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P18",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="rank_scale",
        how=(
            "1024 sets flat ranks directly; the 16-rack hierarchy is NOT "
            "representable at L0 — a torus2d 64x16 grid is a ring-based "
            "structural stand-in under uniform B/L (A-L0T-UNIF/A-L0T-SEQ), "
            "not the paper's inter-rack full-mesh, so the honest Pod-scale "
            "L0 run is flat."
        ),
        targets=(
            _ring("ranks", "flat 1024, hierarchy lost"),
            _torus("ranks", "flat count"),
            _torus("grid.dim1_ranks", "64: rack-level ring stand-in"),
            _torus("grid.dim2_ranks", "16: pod-level ring stand-in"),
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P39",
        bucket="L0_READY",
        evidence_grade="PAPER_REPORTED",
        l0_role="workload_scoping",
        how=(
            "97% TP+SP traffic share justifies Dense TP Decode (W1) as the "
            "platform's first workload; the share is a workload-design fact "
            "consumed at selection time, not an infra knob — it never enters "
            "an L0 identity."
        ),
        workload_kinds=(w1.WORKLOAD_KIND,),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F01",
        bucket="L0_READY",
        evidence_grade="",
        l0_role="free_parameter_gate",
        how=(
            "Gates every bandwidth knob: no public per-lane rate exists, so "
            "B stays a recorded free assumption in any UB-flavored run; both "
            "anchored candidates (224/256 Gbit/s highlight; 1.6 Tbit/s per "
            "LinkDevice port) keep their own grades if used."
        ),
        targets=_BW_TARGETS,
    ),
    UBPlatformMapping(
        parameter_id="UBP-F02",
        bucket="L0_READY",
        evidence_grade="",
        l0_role="free_parameter_gate",
        how=(
            "Gates every latency knob: only end-to-end RTT claims exist "
            "publicly, so per-hop/pair L stays free; decomposition into "
            "per-link/per-switch components becomes possible only at L2."
        ),
        targets=_LAT_TARGETS,
    ),
    # ---------------------------------------------------------- L1_L2_REQUIRED
    UBPlatformMapping(
        parameter_id="UBP-P01",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Hierarchical localized full-mesh with per-level link widths "
            "exceeds every landed L0 identity (flat ring/crossbar/torus2d/"
            "exchange, each one uniform B); honest representation needs a "
            "flow/packet model or a not-yet-landed hierarchical identity. "
            "Nearest landed stand-ins: crossbar (one full-mesh level), "
            "torus2d (two ring levels, uniform B)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P02",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "The LRS plane's non-blocking FUNCTION is exactly what the "
            "crossbar identity assumes; the structure — 18 parallel LRSes "
            "(2 CPU/backup, 8 regular-NPU, 8 inter-rack), x72 IO each — "
            "needs switch-level fidelity (L1 contention at best, L2 switch/"
            "wiring detail), and the port wiring itself is FREE (UBP-F07)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P03",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "0-2-hop locality is an OUTCOME of topology plus routing under "
            "TP/SP placement; at L0 the hop count is an identity constant "
            "(e.g. 2(r-1) ring hops), never emergent, so this figure can "
            "only be observed once routing fidelity exists (L1 strategies "
            "or L2 paths)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P08",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "CPU endpoints (x32 UB IO) require endpoint heterogeneity: every "
            "landed model has homogeneous ranks only. Packet-level endpoint "
            "modeling (L2) is the lowest honest host; any CPU bandwidth "
            "derivation is additionally gated by UBP-F01."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P09",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "LRS switch IO capability (UB x72) is switch capacity: at L0 "
            "switches are abstracted away entirely by the non-blocking "
            "crossbar assumption, so this figure has no knob; it needs "
            "switch-level (L2) modeling."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P10",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "HRS x512 IO capacity belongs to the Pod-switch tier, which no "
            "landed topology class represents (the HRS Clos tier itself is "
            "UBP-P19); switch capacity is L2 content."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P11",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Rack uplink aggregation (4 x x256 backplane IO) is a "
            "per-hierarchy-level width: every landed fabric carries ONE "
            "uniform B, so aggregation needs the hierarchical identity / "
            "flow model that has not landed."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P12",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Inter-rack x128 link width is again a per-level width (as "
            "UBP-P11): no flat L0 fabric can carry intra-rack and inter-rack "
            "widths in one topology (A-L0T-UNIF forbids it even in torus2d)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P13",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Default x16 inter-rack allocation per NPU (x4/x8/x16/x32 "
            "explored) defines the intra/inter-rack bandwidth ASYMMETRY "
            "(x16 of x72 lanes); not expressible in any single landed "
            "topology. The anchored exploration is a ready-made sweep axis "
            "once a hierarchical identity exists; at L0 only scenario-split "
            "approximations (separate runs) are honest."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P15",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_packet_flit",
        how=(
            "LinkDevice 176 ports x 1.6 Tbit/s (280 Tbit/s) is an optical "
            "switch-device capacity; device-level port counts and rates are "
            "packet-fidelity content. Its per-port rate is also an anchored "
            "UBP-F01 candidate (per-port, NOT per-lane) with the vendor "
            "grade carried."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P19",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "The 8K SuperPod tier is reached via HRS Pod-switches in a "
            "symmetrical Clos; no Clos topology class exists at any landed "
            "fidelity (an L0 Clos identity could land someday; the pinned "
            "uet-htsim could host it at L2). 8192 as a flat rank count "
            "would silently delete the Clos structure — not done here."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P21",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_packet_flit",
        how=(
            "UBG switch radix 1024 is switch-level structure; L0 abstracts "
            "switches (crossbar assumes non-blocking, no radix), so radix "
            "needs L2 device modeling."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P23",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_memory_semantic_unpinned",
        how=(
            "Unified global addressing is a load/store memory-semantic "
            "behavior: every landed backend models message-passing "
            "collectives only, and the ASTRA-sim adapter lists "
            "scale_up_memory_semantics as explicitly unsupported. Needs a "
            "memory-semantic L2 backend — none pinned (track license-gated)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P24",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_memory_semantic_unpinned",
        how=(
            "Synchronous Load/Store/Atomic plus asynchronous Read/Write/"
            "Message operation classes are memory-semantic protocol "
            "behavior; notional at best until an L2 memory-semantic backend "
            "exists AND the consistency model is fixed (UBP-F05 is FREE)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P28",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_memory_semantic_unpinned",
        how=(
            "One memory-semantic bus end to end with full peer equality is "
            "the umbrella design class for P23/P24; at L0 it is pure "
            "context (no identity consumes it) and it needs the same "
            "unpinned L2 memory track."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P29",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_memory_semantic_unpinned",
        how=(
            "Tiered memory pooling (DDR as NPU alternative memory, "
            "activation caching) requires an endpoint memory-system model; "
            "no landed or pinned backend models memory tiers — beyond even "
            "the pinned packet backend, which is transport-only."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P30",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_memory_semantic_unpinned",
        how=(
            "Heterogeneous peer access (CPU/NPU/memory/SSD, disaggregation) "
            "needs heterogeneous endpoints plus memory semantics — the "
            "union of UBP-P08's endpoint heterogeneity and P23/P24's "
            "unpinned memory track."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P31",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_packet_flit",
        how=(
            "RTT 7 -> 2 microseconds is an end-to-end OUTCOME claim, not an "
            "input: it cannot set any L0 knob (UBP-F02 blocks the per-hop "
            "decomposition). Usable only as a future L2 calibration target "
            "(O-CCT-RELERR machinery), with the vendor grade carried."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P32",
        bucket="L1_L2_REQUIRED",
        evidence_grade="VENDOR_CLAIMED",
        needed_fidelity="L2_packet_flit",
        how=(
            "LinkDevice RTT <= 2 microseconds is again an outcome claim "
            "calibration-target-only at L2; it never parameterizes a "
            "landed model."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P33",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "The 8-byte APR source-routing header is packet-format detail; "
            "L0 has no packets (packetization_flit_effects explicitly "
            "unsupported by every landed backend). L2 content; the rest of "
            "the format is FREE (UBP-F03)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P34",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L2_packet_flit",
        how=(
            "2-VL deadlock-free all-path routing is a routing-resource "
            "mechanism; no landed model has virtual lanes or routing "
            "freedom (routes are identity-implicit). L2 content."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P35",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Shortest/Detour/Borrow routing strategies (and their measured "
            "degradations vs Clos) need selectable paths over a represented "
            "topology; L0 identities have no routing choice. L1 strategy "
            "level first, L2 for per-path detail."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P43",
        bucket="L1_L2_REQUIRED",
        evidence_grade="PAPER_REPORTED",
        needed_fidelity="L1_flow_collective",
        how=(
            "Flexible IO bandwidth allocation and link pooling: STATIC "
            "allocation points are expressible today only as separate L0 "
            "runs with different B; the dynamic one-pool flexibility is not "
            "representable at L0 and needs flow-level resource modeling."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F03",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "Packet/FLIT format and MTU silence gates any L2 packet-format "
            "modeling; even at L2 the format would be a declared free "
            "assumption, never a paper-derived value."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F04",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "Congestion-control silence: every landed backend declares "
            "congestion and credit flow control explicitly unsupported; at "
            "L2 (uet-htsim pinned for the UEC track) any UB CC choice "
            "remains a free assumption because the public text is silent."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F05",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_memory_semantic_unpinned",
        how=(
            "Ordering/atomicity/consistency silence gates the memory-"
            "semantic track entirely: without a public consistency model, "
            "even an L2 memory-semantic backend could only carry declared "
            "assumptions."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F07",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "LRS-plane port wiring (18 LRSes onto 64 NPUs and 4 x256 "
            "uplinks) is topology detail below every landed abstraction; "
            "needed before any L2 switch-structure model of the rack."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F08",
        bucket="L1_L2_REQUIRED",
        evidence_grade="",
        needed_fidelity="L2_packet_flit",
        how=(
            "Reliable-rerouting mechanism silence: rerouting dynamics are "
            "L2 content, and no pinned backend has failure injection; the "
            "feature name alone (public) cannot parameterize anything."
        ),
    ),
    # ------------------------------------------------------------- UNSUPPORTED
    UBPlatformMapping(
        parameter_id="UBP-P04",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="physical_deployment_cost",
        how=(
            "Cable-mix percentages (86.7% passive electrical, optical "
            "splits) are physical-deployment facts; no landed or planned "
            "backend models cable plant, reach, or media mix."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P05",
        bucket="UNSUPPORTED",
        evidence_grade="VENDOR_CLAIMED",
        reason_kind="physical_deployment_cost",
        how=(
            "LinkBlade (cable-free in-cabinet interconnect, ~196 km copper "
            "cut, 4096-NPU SuperPoD) is packaging; its SCALE aspect could "
            "set a rank count, but the claim itself (circuit-loss "
            "elimination, cabling reduction) has no model at any planned "
            "fidelity."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P14",
        bucket="UNSUPPORTED",
        evidence_grade="VENDOR_CLAIMED",
        reason_kind="unquantified_claim",
        how=(
            "'100 GB/s level to TB/s level' is an order-of-magnitude "
            "marketing claim with unstated scope; it can set no knob. The "
            "nearest quantitative anchor is the UBP-F01 candidate list, "
            "which already carries the honest figures with grades."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P20",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="scale_out_scope",
        how=(
            "The 100K-NPU DCN domain is the scale-OUT tier; the platform "
            "targets GPU-to-GPU scale-up fabrics (charter scope), so this "
            "figure is out of scope for every planned backend."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P22",
        bucket="UNSUPPORTED",
        evidence_grade="VENDOR_CLAIMED",
        reason_kind="scale_out_scope",
        how=(
            "Million-NPU SuperCluster is a data-center-scale claim beyond "
            "the scale-up scope; no backend models it or is planned to."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P25",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "CDMA is a host-side library service of the UB OS component "
            "surface; the platform simulates interconnect fabrics, not host "
            "software stacks — outside the fidelity ladder entirely."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P26",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "UMMU (registration, address/permission tables) is host OS "
            "memory-management software; not an interconnect parameter at "
            "any fidelity."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P27",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "OBMM EXPORT/IMPORT memory-lending interfaces are host service "
            "software; only their existence motivates the (unpinned) "
            "memory-semantic track — the interfaces themselves are not "
            "simulable content."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P36",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="reliability_dynamics",
        how=(
            "The 64+1 backup-NPU takeover (one-hop redirect through the "
            "LRS) is failure-and-failover dynamics; no landed or pinned "
            "backend has failure injection, spare activation, or rerouting "
            "— loudly unrepresentable today."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P37",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="reliability_dynamics",
        how=(
            "MTBF 98.5 h vs 13.8 h is the outcome of a reliability model "
            "the platform does not have; it is not a fabric parameter and "
            "no planned fidelity class computes it."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P38",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="reliability_dynamics",
        how=(
            "98.8% availability at 75-minute MTTR is likewise a "
            "reliability-model outcome; unrepresentable today and not on "
            "any backend roadmap in the current plan."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P40",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="physical_deployment_cost",
        how=(
            "98%/93% switch/optical reduction and CapEx shares are cost "
            "claims; the platform has no cost model and cost is not an "
            "observable in the registry."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P41",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="application_outcome",
        how=(
            "Training linearity >95% at 64K NPUs is an application-level "
            "outcome; the platform models collectives on fabrics (Chakra "
            "compute timing exists in the pinned adapter but no "
            "linearity observable) — not representable."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P42",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="design_context",
        how=(
            "'UB replaces PCIe+NVLink+IB/RoCE stacks' is the design-"
            "philosophy frame for the whole profile; it is interpretation "
            "context, not a simulable quantity."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P44",
        bucket="UNSUPPORTED",
        evidence_grade="VENDOR_CLAIMED",
        reason_kind="design_context",
        how=(
            "'More than ten protocols combined' is a marketing-count "
            "claim; context only."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P45",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="design_context",
        how=(
            "Public layer-title enumeration (physical/data-link/network "
            "test volumes) documents what is public; it parameterizes "
            "nothing and points at UBP-F06."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P46",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="design_context",
        how=(
            "SuperPoD reference-architecture feature list is a summary of "
            "the other entries; context only."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P47",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="design_context",
        how=(
            "Layer-boundary alignment is an architectural claim about "
            "implementation cleanliness; no knob at any planned fidelity."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P48",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="design_context",
        how=(
            "Peers-on-one-bus is consistent with the homogeneous-rank L0 "
            "abstraction (no endpoint hierarchy anywhere in the platform) "
            "but supplies no parameter; context only."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P49",
        bucket="UNSUPPORTED",
        evidence_grade="PAPER_REPORTED",
        reason_kind="design_context",
        how=(
            "Copper-near/optics-far is a reach-and-media philosophy; the "
            "platform has no cable/reach model (see UBP-P04), so it stays "
            "context."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P50",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "URMA driver is host software; outside the interconnect "
            "fidelity ladder (predicted by S2's coverage notes)."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P51",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "ummu-core (TokenID management) is host software; the gated "
            "Base Specification it references stays unread by construction."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P52",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "UBus base services (enumeration, hot-plug, interrupts) are "
            "host software; not simulable content."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P53",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "ubutils tooling is host software; outside the ladder."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-P54",
        bucket="UNSUPPORTED",
        evidence_grade="OFFICIAL_PUBLIC_PAGE",
        reason_kind="software_surface",
        how=(
            "openEuler host OS is the software platform under the fabric; "
            "the simulator models fabrics, not operating systems."
        ),
    ),
    UBPlatformMapping(
        parameter_id="UBP-F06",
        bucket="UNSUPPORTED",
        evidence_grade="",
        reason_kind="design_context",
        how=(
            "The layer model above the network layer is not public and is "
            "not a simulable quantity anyway; it stays interpretive "
            "context for any future memory-semantic track."
        ),
    ),
)


class PlatformMapError(Exception):
    """Raised when the platform map fails validation."""


def entries() -> tuple[UBPlatformMapping, ...]:
    """All mapping entries."""
    return _MAPPINGS


def by_bucket(bucket: str) -> tuple[UBPlatformMapping, ...]:
    """All entries in one bucket."""
    if bucket not in BUCKETS:
        raise ValueError(f"unknown bucket {bucket!r} (not in {BUCKETS})")
    return tuple(entry for entry in _MAPPINGS if entry.bucket == bucket)


def _knob_field_ok(config_cls, knob: str) -> bool:
    names = {f.name for f in dataclass_fields(config_cls)}
    return knob.replace(".", "_") in names or knob.rsplit(".", 1)[-1] in names


def _entry_problems(entry: UBPlatformMapping, grades: dict[str, str]) -> list[str]:
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
        if entry.l0_role == "workload_scoping":
            if entry.targets:
                problems.append(f"{eid}: workload_scoping entry must not carry targets")
            if not entry.workload_kinds:
                problems.append(f"{eid}: workload_scoping entry needs workload_kinds")
            for kind in entry.workload_kinds:
                if kind not in ALLOWED_WORKLOAD_KINDS:
                    problems.append(f"{eid}: unknown workload kind {kind!r}")
        else:
            if entry.workload_kinds:
                problems.append(f"{eid}: workload_kinds only on workload_scoping")
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
        if entry.targets or entry.workload_kinds or entry.l0_role or entry.reason_kind:
            problems.append(f"{eid}: L1_L2_REQUIRED entry carries L0/UNSUPPORTED fields")
    else:  # UNSUPPORTED
        if entry.reason_kind not in REASON_KINDS:
            problems.append(f"{eid}: reason_kind {entry.reason_kind!r} not in {REASON_KINDS}")
        if (
            entry.targets
            or entry.workload_kinds
            or entry.l0_role
            or entry.needed_fidelity
        ):
            problems.append(f"{eid}: UNSUPPORTED entry carries L0/L1L2 fields")
    return problems


def check(entries: Optional[tuple[UBPlatformMapping, ...]] = None) -> list[str]:
    """Structurally validate a mapping list. Returns all problems; empty = valid.

    Validates bucket vocabularies, per-bucket field rules, evidence-grade
    passthrough against the S2 profile, uniqueness, and — the load-bearing
    check — that every L0 target names a landed analytical backend, a
    declared topology class, and a knob that resolves to a field of that
    backend's config dataclass, with role/knob-kind consistency.
    """
    checked = _MAPPINGS if entries is None else entries
    grades = {
        obj.parameter_id: (
            obj.evidence_grade if isinstance(obj, _profile.UBDesignParameter) else ""
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


def coverage_problems(entries: Optional[tuple[UBPlatformMapping, ...]] = None) -> list[str]:
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
            f"UnifiedBus platform map failed validation: {detail}{more}"
        )
