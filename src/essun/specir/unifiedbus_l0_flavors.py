"""Flavor configs for the cross-design same-workload L0 comparison table
(UEC flavor vs UnifiedBus PAPER-DERIVED flavor, extended 2026-11-02 with
the NVLink-paper PAPER-DERIVED flavor — three architectures, M1).

This module turns the stage's honesty rules into executable checks so the
comparison cannot drift into tuning:

1. **Equal free parameters (mechanical):** every flavor topology file in
   the sweep :data:`experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml`
   and the three-architecture payload grid
   :data:`experiments/sweeps/cross_fabric_3arch_payload_grid_v1.yaml`
   carries the SAME shared free bandwidth (B = 64 bytes/ns) and latency
   (L = 200 ns) from the ONE shared record
   :data:`experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml`
   (A-XDUO-BW / A-XDUO-LAT).  Any file that changes one knob without the
   record is a hard error — the flavors may differ ONLY through anchored
   structure, never through unequal free parameters.
2. **Anchored rank scale, both directions stated:** the UnifiedBus
   flavor's ``ranks = 64`` is not a free choice; it is pinned to the S2
   profile parameter ``UBP-P17`` (64 NPUs per rack, PAPER_REPORTED,
   anchor ``UBP-UBMESH-3.3.1-RACK-64NPU``) whose anchors must resolve in
   the S1 public-source registry.  The NVLink-paper flavor's ``ranks =
   64`` is the REVERSE asymmetry, and the check enforces that the file
   says so: the anchored NVLink5 domain scale is 72 (``NVP-P13``,
   VENDOR_CLAIMED) and 64 is a stated MATCHED-FREE choice against it
   (``A-XDUO-IDNV``) so the same-workload gate holds.  The UEC flavor's
   rank count is explicitly FREE (UEC 1.1 fixes none).
3. **Anchored identity:** the UB flavor's crossbar identity must be backed
   by the S3 platform map's L0_READY rows for ``UBP-P17`` (rack full-mesh
   level) and ``UBP-P06`` (switch-free adjacency precedent); the NV
   flavor's by the M1 platform map's L0_READY rows for ``NVP-P01`` (the
   paper-reported NVSwitch non-blocking crossbar) and ``NVP-P13`` (the
   72-GPU switched domain).
4. **Honesty labels in the artifacts:** the UB and NV flavor files must
   carry the marker "paper-derived design profile, NOT a normative
   standard profile" and cite the bandwidth/latency silences they run
   inside (``UBP-F01`` / ``UBP-F02``; ``NVP-F01`` / ``NVP-F02`` /
   ``NVP-F03``); the UEC flavor files must carry the "no UEC-derived
   numeric value" marker.  Dropping a label trips a check.

Whether a paper-derived profile satisfies the public-release gate's "2
distinct standards" leg is an open decision (the normative
path) — teed up in ``reports/p6_stage4.md``; this module enforces honesty,
it does not decide the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from essun.contracts import REPO_ROOT

# ---------------------------------------------------------------------------
# The shared comparison contract (stage S4 values; mirrors the assumption
# record and the sweep manifest — drift between these three is an error).
# ---------------------------------------------------------------------------

#: One shared free bandwidth for BOTH flavors, every L0 knob spelling.
SHARED_FREE_B_BYTES_PER_NS: int = 64

#: One shared free latency for BOTH flavors, every L0 knob spelling.
SHARED_FREE_L_NS: int = 200

#: Rank count of the comparison: anchored on the UB side (UBP-P17 rack),
#: free on the UEC side — the asymmetry A-XDUO-TP states loudly.
COMPARISON_RANKS: int = 64

#: Payload sizes of the sweep grid (free parameters, A-XDUO-PAYLOAD).
PAYLOAD_SIZES_BYTES: tuple[int, ...] = (16384, 1048576)

#: Payload ladder of the cross-fabric payload grids (the shared registry
#: A-XDUO-PAYLOAD range's power-of-two ladder; identical for the committed
#: two-architecture grid and the M1 three-architecture grid so their rows
#: interleave without re-anchoring).
THREE_ARCH_PAYLOAD_SIZES: tuple[int, ...] = (
    4096, 8192, 16384, 65536, 131072, 262144,
    1048576, 2097152, 4194304, 16777216,
)

#: Torus stand-in grid shape (free design-space choice, A-L0T-SHAPE pattern).
TORUS_GRID: tuple[int, int] = (8, 8)

ASSUMPTIONS_ID: str = "assumptions_uec_vs_ub_l0_v1"
ASSUMPTIONS_PATH: str = "experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml"
WORKLOAD_PATH: str = "experiments/workloads/w1_dense_tp_decode_rack64.yaml"
SWEEP_MANIFEST_PATH: str = "experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml"
SWEEP_NAME: str = "cross_design_uec_vs_ub_paper_l0_v1"
#: The M1 three-architecture payload grid (UEC + UB + NVLink crossbars).
SWEEP_3ARCH_MANIFEST_PATH: str = "experiments/sweeps/cross_fabric_3arch_payload_grid_v1.yaml"
SWEEP_3ARCH_NAME: str = "cross_fabric_3arch_payload_grid_v1"

#: Absolute honesty marker every UB-flavor artifact must carry (case-folded
#: match): the ladder's rule 1, stated in the artifact itself.
UB_PROFILE_MARKER: str = "paper-derived design profile, not a normative standard profile"

#: The same marker for the NVLink-paper flavor (M1): same rule, third
#: fabric, stated in the artifact itself.
NV_PROFILE_MARKER: str = "paper-derived design profile, not a normative standard profile"

#: The matched-free statement the NV flavor's rank scale must carry: the
#: anchored NVLink domain is 72 (NVP-P13) and 64 is a stated matched-free
#: choice — the asymmetry is printed, never hidden.
NV_RANK_SCALE_MARKER: str = "matched-free"

#: The UEC-flavor honesty marker: Q1's UEC ladder has landed SEMANTICS, not
#: L0 numbers, so UEC-flavor files must say so where they stand.
UEC_FREE_MARKER: str = "no uec-derived numeric value"

# Provenance pins (S2 profile ids, S1 anchor ids).
RANK_SCALE_PARAMETER_ID: str = "UBP-P17"
RANK_SCALE_ANCHOR_ID: str = "UBP-UBMESH-3.3.1-RACK-64NPU"
ADJACENCY_PARAMETER_ID: str = "UBP-P06"  # switch-free 16-NPU crossbar precedent
LANE_STRUCTURE_PARAMETER_ID: str = "UBP-P07"  # B = 72 x per-lane rate, structure only
BW_SILENCE_PARAMETER_ID: str = "UBP-F01"  # per-lane rate FREE
LAT_SILENCE_PARAMETER_ID: str = "UBP-F02"  # latency breakdown FREE

# NVLink-paper provenance pins (M1 profile ids; experiments/nvlink/).
NV_IDENTITY_PARAMETER_ID: str = "NVP-P01"  # NVSwitch non-blocking crossbar, PAPER_REPORTED
NV_DOMAIN_PARAMETER_ID: str = "NVP-P13"  # 72-GPU NVLink5 domain, VENDOR_CLAIMED
NV_BW_SILENCE_PARAMETER_ID: str = "NVP-F01"  # per-link NVLink5 rate FREE
NV_LAT_SILENCE_PARAMETER_ID: str = "NVP-F02"  # current-gen per-hop latency FREE
NV_FC_SILENCE_PARAMETER_ID: str = "NVP-F03"  # flow-control mechanism silence

#: Assumption-record entries every check re-reads (rule: every
#: assumption carries parameter, value, unit, range, rationale,
#: sensitivity, owner, review).
_ASSUMPTION_FIELDS: tuple[str, ...] = (
    "id",
    "parameter",
    "value",
    "unit",
    "range",
    "rationale",
    "sensitivity",
    "owner",
    "review",
)


class FlavorConfigError(Exception):
    """Raised when the cross-design flavor configs violate the honesty contract."""


@dataclass(frozen=True)
class FlavorTopology:
    """One flavor row of the cross-design sweep grid."""

    flavor: str  # "UEC_FREE" | "UB_PAPER" | "NV_PAPER"
    algorithm: str
    topology_class: str
    path: str  # repo-relative
    topology_id: str
    bandwidth_knob: str  # dotted path into the topology YAML
    latency_knob: str
    grid: Optional[tuple[int, int]] = None  # torus only

    def knob_value(self, data: dict, knob: str) -> Any:
        node: Any = data
        for part in knob.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


#: The exact grid of the committed two-architecture cross-design sweep
#: (mirrors the manifest; drift between this tuple and the manifest file
#: is an error, never a re-pin).  The M1 NV flavor joins the
#: three-architecture payload grid below, not this manifest, so the
#: committed sweep's artifact id is untouched.
CROSS_DESIGN_TOPOLOGIES: tuple[FlavorTopology, ...] = (
    FlavorTopology(
        flavor="UEC_FREE",
        algorithm="allreduce_ring",
        topology_class="unidirectional_ring",
        path="experiments/topologies/ring64_uec_free_params.yaml",
        topology_id="uec_free_ring64_v1",
        bandwidth_knob="link.bytes_per_ns",
        latency_knob="link.hop_latency_ns",
    ),
    FlavorTopology(
        flavor="UEC_FREE",
        algorithm="allreduce_crossbar",
        topology_class="fully_connected_crossbar",
        path="experiments/topologies/crossbar64_uec_free_params.yaml",
        topology_id="uec_free_crossbar64_v1",
        bandwidth_knob="nic.injection_bytes_per_ns",
        latency_knob="link.pair_latency_ns",
    ),
    FlavorTopology(
        flavor="UB_PAPER",
        algorithm="allreduce_crossbar",
        topology_class="fully_connected_crossbar",
        path="experiments/topologies/crossbar64_ub_rack_free_params.yaml",
        topology_id="ub_rack64_crossbar_v1",
        bandwidth_knob="nic.injection_bytes_per_ns",
        latency_knob="link.pair_latency_ns",
    ),
    FlavorTopology(
        flavor="UEC_FREE",
        algorithm="allreduce_torus2d",
        topology_class="torus2d_ring_x_ring",
        path="experiments/topologies/torus2d64_uec_free_params.yaml",
        topology_id="uec_free_torus2d64_v1",
        bandwidth_knob="link.bytes_per_ns",
        latency_knob="link.hop_latency_ns",
        grid=TORUS_GRID,
    ),
)

#: The NVLink-paper flavor of the three-architecture payload grid (M1):
#: identity ANCHORED (NVP-P01/NVP-P13), rank scale matched-free against
#: the anchored 72-GPU domain, B/L shared free parameters.
NV_PAPER_TOPOLOGY = FlavorTopology(
    flavor="NV_PAPER",
    algorithm="allreduce_crossbar",
    topology_class="fully_connected_crossbar",
    path="experiments/topologies/crossbar64_nvl_rack_free_params.yaml",
    topology_id="nvl_rack64_crossbar_v1",
    bandwidth_knob="nic.injection_bytes_per_ns",
    latency_knob="link.pair_latency_ns",
)

#: Every declared flavor topology (both manifests' union).
FLAVOR_TOPOLOGIES: tuple[FlavorTopology, ...] = CROSS_DESIGN_TOPOLOGIES + (
    NV_PAPER_TOPOLOGY,
)

#: The exact config set of the three-architecture payload grid (the three
#: identity-matched crossbars; drift against its manifest is an error).
THREE_ARCH_TOPOLOGIES: tuple[FlavorTopology, ...] = (
    CROSS_DESIGN_TOPOLOGIES[1],  # UEC crossbar (baseline)
    CROSS_DESIGN_TOPOLOGIES[2],  # UB paper crossbar
    NV_PAPER_TOPOLOGY,           # NVLink paper crossbar
)

#: Baseline of the sweep: the identity-matched UEC control, so the UB row's
#: delta column reads exactly 0 under the shared free parameters.
BASELINE: tuple[str, str] = (
    "allreduce_crossbar",
    "experiments/topologies/crossbar64_uec_free_params.yaml",
)


def _fold(text: str) -> str:
    """Case-fold and collapse whitespace for marker matching in comments.

    YAML comment markers (``#``) are stripped first so a marker phrase that
    wraps across comment lines ("... NOT A\\n# NORMATIVE ...") still matches.
    """
    return " ".join(text.replace("#", " ").split()).casefold()


# ---------------------------------------------------------------------------
# Pure checks over parsed/loaded content (tests feed tampered copies here)
# ---------------------------------------------------------------------------


def flavor_file_problems(spec: FlavorTopology, text: str, data: dict) -> list[str]:
    problems: list[str] = []
    label = f"{spec.path} ({spec.flavor})"
    if not isinstance(data, dict):
        return [f"{label}: topology file is not a mapping"]

    if data.get("topology_class") != spec.topology_class:
        problems.append(
            f"{label}: topology_class {data.get('topology_class')!r} != declared "
            f"{spec.topology_class!r}"
        )
    if data.get("topology_id") != spec.topology_id:
        problems.append(
            f"{label}: topology_id {data.get('topology_id')!r} != declared "
            f"{spec.topology_id!r}"
        )
    if data.get("ranks") != COMPARISON_RANKS:
        problems.append(
            f"{label}: ranks {data.get('ranks')!r} != comparison rank count "
            f"{COMPARISON_RANKS}"
            + (
                " — on the UB flavor this rank count is ANCHORED (UBP-P17), "
                "not a free choice" if spec.flavor == "UB_PAPER" else ""
            )
            + (
                " — on the NV flavor the anchored domain scale is 72 "
                "(NVP-P13) and 64 is a stated MATCHED-FREE choice, so the "
                "statement itself is required" if spec.flavor == "NV_PAPER" else ""
            )
        )

    bw = spec.knob_value(data, spec.bandwidth_knob)
    lat = spec.knob_value(data, spec.latency_knob)
    if bw != SHARED_FREE_B_BYTES_PER_NS:
        problems.append(
            f"{label}: bandwidth knob {spec.bandwidth_knob}={bw!r} != shared "
            f"free parameter {SHARED_FREE_B_BYTES_PER_NS} (A-XDUO-BW) — the "
            "flavors may differ ONLY through anchored structure, never "
            "through unequal free parameters"
        )
    if lat != SHARED_FREE_L_NS:
        problems.append(
            f"{label}: latency knob {spec.latency_knob}={lat!r} != shared "
            f"free parameter {SHARED_FREE_L_NS} (A-XDUO-LAT)"
        )

    if spec.grid is not None:
        grid = data.get("grid") or {}
        dims = (grid.get("dim1_ranks"), grid.get("dim2_ranks"))
        if dims != spec.grid:
            problems.append(
                f"{label}: grid {dims!r} != declared free shape {spec.grid!r}"
            )
        elif dims[0] * dims[1] != data.get("ranks"):
            problems.append(f"{label}: grid {dims!r} does not factor ranks")

    folded = _fold(text)
    if ASSUMPTIONS_PATH not in text:
        problems.append(
            f"{label}: file must cite the shared free-parameter record "
            f"{ASSUMPTIONS_PATH}"
        )
    if spec.flavor == "UB_PAPER":
        if UB_PROFILE_MARKER not in folded:
            problems.append(
                f"{label}: missing the honesty marker {UB_PROFILE_MARKER!r} — "
                "the UB flavor is paper-derived, NOT a normative standard "
                "profile, and the artifact must say so"
            )
        for pin, why in (
            (RANK_SCALE_PARAMETER_ID, "anchored rank scale"),
            (LANE_STRUCTURE_PARAMETER_ID, "B = 72 x per-lane-rate structure"),
            (BW_SILENCE_PARAMETER_ID, "per-lane rate silence (B stays FREE)"),
            (LAT_SILENCE_PARAMETER_ID, "latency-breakdown silence (L stays FREE)"),
        ):
            if pin not in text:
                problems.append(f"{label}: must cite {pin} ({why})")
    elif spec.flavor == "NV_PAPER":
        if NV_PROFILE_MARKER not in folded:
            problems.append(
                f"{label}: missing the honesty marker {NV_PROFILE_MARKER!r} — "
                "the NVLink-paper flavor is paper-derived, NOT a normative "
                "standard profile, and the artifact must say so"
            )
        if NV_RANK_SCALE_MARKER not in folded:
            problems.append(
                f"{label}: missing the matched-free rank statement "
                f"({NV_RANK_SCALE_MARKER!r}) — the anchored NVLink domain "
                "scale is 72 (NVP-P13), and 64 must be stated as a "
                "matched-free choice, never passed off as anchored"
            )
        for pin, why in (
            (NV_IDENTITY_PARAMETER_ID, "anchored NVSwitch crossbar identity"),
            (NV_DOMAIN_PARAMETER_ID, "anchored 72-GPU domain scale"),
            (NV_BW_SILENCE_PARAMETER_ID, "per-link rate silence (B stays FREE)"),
            (NV_LAT_SILENCE_PARAMETER_ID, "current-gen latency silence (L stays FREE)"),
            (NV_FC_SILENCE_PARAMETER_ID, "flow-control silence (no window)"),
        ):
            if pin not in text:
                problems.append(f"{label}: must cite {pin} ({why})")
    else:
        if UEC_FREE_MARKER not in folded:
            problems.append(
                f"{label}: missing the marker {UEC_FREE_MARKER!r} — the UEC "
                "flavor must state that UEC 1.1 anchors no numeric L0 value"
            )
        if "free parameter" not in folded:
            problems.append(f"{label}: must label its values as free parameters")
    return problems


def assumptions_problems(assumptions: dict) -> list[str]:
    problems: list[str] = []
    if not isinstance(assumptions, dict):
        return ["assumptions record is not a mapping"]
    if assumptions.get("assumptions_id") != ASSUMPTIONS_ID:
        problems.append(
            f"assumptions_id {assumptions.get('assumptions_id')!r} != {ASSUMPTIONS_ID!r}"
        )
    if assumptions.get("status") != "PROPOSED":
        problems.append(
            f"assumptions status {assumptions.get('status')!r} != 'PROPOSED' — "
            "these are free-parameter assumptions, never verified values"
        )
    entries = assumptions.get("assumptions")
    if not isinstance(entries, list) or not entries:
        return problems + ["assumptions record has no entries"]
    by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("assumptions entry is not a mapping")
            continue
        missing = [field for field in _ASSUMPTION_FIELDS if field not in entry]
        if missing:
            problems.append(
                f"assumption {entry.get('id')!r} missing field(s) {missing} "
                "(handoff rule: every assumption has range, rationale, "
                "sensitivity, owner, review status)"
            )
    expected_values = {
        "A-XDUO-BW": SHARED_FREE_B_BYTES_PER_NS,
        "A-XDUO-LAT": SHARED_FREE_L_NS,
        "A-XDUO-TP": COMPARISON_RANKS,
    }
    for assumption_id, value in expected_values.items():
        entry = by_id.get(assumption_id)
        if entry is None:
            problems.append(f"assumptions record missing {assumption_id}")
        elif entry.get("value") != value:
            problems.append(
                f"{assumption_id}.value {entry.get('value')!r} != {value!r}"
            )
    payload = by_id.get("A-XDUO-PAYLOAD")
    if payload is None:
        problems.append("assumptions record missing A-XDUO-PAYLOAD")
    elif tuple(payload.get("value") or ()) != PAYLOAD_SIZES_BYTES:
        problems.append(
            f"A-XDUO-PAYLOAD.value {payload.get('value')!r} != "
            f"{list(PAYLOAD_SIZES_BYTES)!r}"
        )
    # The record must state the two load-bearing honesty facts in prose:
    # the UB rank asymmetry and the UB-silence markers.
    text = _fold(yaml.safe_dump(assumptions, sort_keys=False))
    for token, why in (
        (RANK_SCALE_PARAMETER_ID, "the anchored rank scale"),
        (BW_SILENCE_PARAMETER_ID, "the bandwidth silence"),
        (LAT_SILENCE_PARAMETER_ID, "the latency silence"),
        ("owner decision", "the gate-leg owner decision fence"),
    ):
        if token.casefold() not in text:
            problems.append(f"assumptions record must cite {token!r} ({why})")
    return problems


def workload_manifest_problems(
    workload: dict,
    manifest: dict,
    *,
    sweep_name: str = SWEEP_NAME,
    expected_topologies: tuple[FlavorTopology, ...] = CROSS_DESIGN_TOPOLOGIES,
    payload_sizes: tuple[int, ...] = PAYLOAD_SIZES_BYTES,
) -> list[str]:
    problems: list[str] = []
    if not isinstance(workload, dict) or not isinstance(manifest, dict):
        return ["workload or sweep manifest is not a mapping"]

    if workload.get("workload") != "w1_dense_tp_decode":
        problems.append(
            f"workload kind {workload.get('workload')!r} != 'w1_dense_tp_decode'"
        )
    if workload.get("tp_size") != COMPARISON_RANKS:
        problems.append(
            f"workload tp_size {workload.get('tp_size')!r} != {COMPARISON_RANKS} — "
            "the SAME-workload gate (one workload file => one tp_size for "
            "every config) is what makes this comparison literal"
        )

    if manifest.get("sweep") != sweep_name:
        problems.append(f"manifest sweep name {manifest.get('sweep')!r} != {sweep_name!r}")
    if manifest.get("workload") != WORKLOAD_PATH:
        problems.append(
            f"manifest workload {manifest.get('workload')!r} != {WORKLOAD_PATH!r}"
        )
    baseline = manifest.get("baseline") or {}
    if (baseline.get("algorithm"), baseline.get("topology")) != BASELINE:
        problems.append(
            f"manifest baseline {(baseline.get('algorithm'), baseline.get('topology'))!r} "
            f"!= the identity-matched control {BASELINE!r} — the baseline choice "
            "is what makes the paper-derived rows' delta-0 coincidence visible"
        )

    grid = manifest.get("grid") or {}
    sizes = grid.get("payload_sizes_bytes")
    if tuple(sizes or ()) != payload_sizes:
        problems.append(f"grid.payload_sizes_bytes {sizes!r} != {list(payload_sizes)!r}")
    for size in sizes or ():
        if not isinstance(size, int) or size % COMPARISON_RANKS or size % TORUS_GRID[0]:
            problems.append(
                f"payload {size!r} violates the equal-chunk divisibility "
                f"identities (must divide by {COMPARISON_RANKS} and "
                f"{TORUS_GRID[0]})"
            )

    expected_pairs = {(spec.algorithm, spec.path) for spec in expected_topologies}
    actual_pairs: set[tuple[str, str]] = set()
    entries = grid.get("algorithms")
    if not isinstance(entries, list):
        problems.append("grid.algorithms is not a list")
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                problems.append(f"grid algorithm entry {entry!r} is not a mapping")
                continue
            for topology in entry.get("topologies") or ():
                actual_pairs.add((entry.get("algorithm"), topology))
    if actual_pairs != expected_pairs:
        problems.append(
            f"grid configs {sorted(actual_pairs)} != the declared flavor grid "
            f"{sorted(expected_pairs)} — every row must be a declared flavor "
            "topology with its provenance labels (no unprovenanced rows)"
        )
    return problems


def provenance_problems(repo_root: Path) -> list[str]:
    """Anchor-chain checks, offline (S1 pages and registries are committed)."""
    from essun.specir import nvlink_paper_profile as nv_profile
    from essun.specir import nvlink_platform_map as nv_platform_map
    from essun.specir import unifiedbus_paper_profile as profile
    from essun.specir import unifiedbus_platform_map as platform_map
    from essun.specir.unifiedbus_sources import PaperAnchorRegistry

    problems: list[str] = []
    registry = PaperAnchorRegistry.load(repo_root=repo_root)
    anchors = registry.by_id()

    parameters = {p.parameter_id: p for p in profile.parameters()}
    frees = {f.parameter_id: f for f in profile.free_parameters()}

    rank = parameters.get(RANK_SCALE_PARAMETER_ID)
    if rank is None:
        problems.append(f"S2 profile missing {RANK_SCALE_PARAMETER_ID}")
    else:
        if rank.evidence_grade != "PAPER_REPORTED":
            problems.append(
                f"{RANK_SCALE_PARAMETER_ID} grade {rank.evidence_grade!r} != "
                "'PAPER_REPORTED' — the anchored rank scale must not launder "
                "a weaker grade"
            )
        if RANK_SCALE_ANCHOR_ID not in rank.anchor_ids:
            problems.append(
                f"{RANK_SCALE_PARAMETER_ID} does not cite {RANK_SCALE_ANCHOR_ID}"
            )
        if "64 npus" not in _fold(rank.as_reported):
            problems.append(
                f"{RANK_SCALE_PARAMETER_ID}.as_reported does not state the "
                "64-NPU rack scale the flavor file's ranks must equal"
            )
    for anchor_id in (RANK_SCALE_ANCHOR_ID,):
        if anchor_id not in anchors:
            problems.append(
                f"anchor {anchor_id} does not resolve in the S1 public-source "
                "registry — the rank-scale chain is broken"
            )

    for free_id in (BW_SILENCE_PARAMETER_ID, LAT_SILENCE_PARAMETER_ID):
        free = frees.get(free_id)
        if free is None:
            problems.append(f"S2 profile missing free parameter {free_id}")
        elif free.domain != "FREE":
            problems.append(f"{free_id}.domain {free.domain!r} != 'FREE'")

    # The crossbar identity must be the S3 map's anchored approximation for
    # the rack (UBP-P17) with the switch-free precedent (UBP-P06).
    for parameter_id in (RANK_SCALE_PARAMETER_ID, ADJACENCY_PARAMETER_ID):
        matching = [
            entry
            for entry in platform_map.by_bucket("L0_READY")
            if entry.parameter_id == parameter_id
        ]
        if not matching:
            problems.append(
                f"S3 platform map has no L0_READY row for {parameter_id}"
            )
            continue
        backed = any(
            target.backend_id == "analytical_l0_crossbar"
            and target.topology_class == "fully_connected_crossbar"
            for entry in matching
            for target in entry.targets
        )
        if not backed:
            problems.append(
                f"S3 map row for {parameter_id} does not back the "
                "fully_connected_crossbar identity the UB flavor file uses"
            )

    # -- the M1 NVLink-paper chain: identity (NVP-P01, paper-reported
    # NVSwitch crossbar) + domain scale (NVP-P13, vendor-claimed 72-GPU
    # domain, matched-free at 64) + the three silences, all resolving in
    # the experiments/nvlink/ registry, with the M1 platform map's
    # L0_READY rows backing the crossbar identity.
    nv_registry = PaperAnchorRegistry.load(
        path=repo_root / "experiments/nvlink/anchor_registry.yaml",
        repo_root=repo_root,
    )
    nv_anchors = nv_registry.by_id()
    nv_parameters = {p.parameter_id: p for p in nv_profile.parameters()}
    nv_frees = {f.parameter_id: f for f in nv_profile.free_parameters()}

    identity = nv_parameters.get(NV_IDENTITY_PARAMETER_ID)
    if identity is None:
        problems.append(f"M1 profile missing {NV_IDENTITY_PARAMETER_ID}")
    else:
        if identity.evidence_grade != "PAPER_REPORTED":
            problems.append(
                f"{NV_IDENTITY_PARAMETER_ID} grade {identity.evidence_grade!r} "
                "!= 'PAPER_REPORTED' — the crossbar-identity anchor is a "
                "paper measurement-grade claim and must not launder a "
                "weaker grade"
            )
        for anchor_id in identity.anchor_ids:
            if anchor_id not in nv_anchors:
                problems.append(
                    f"anchor {anchor_id} does not resolve in the M1 "
                    "public-source registry — the NV identity chain is broken"
                )
    domain = nv_parameters.get(NV_DOMAIN_PARAMETER_ID)
    if domain is None:
        problems.append(f"M1 profile missing {NV_DOMAIN_PARAMETER_ID}")
    else:
        if "72" not in domain.as_reported:
            problems.append(
                f"{NV_DOMAIN_PARAMETER_ID}.as_reported does not state the "
                "72-GPU domain scale the NV flavor's matched-free statement "
                "cites"
            )
        if domain.evidence_grade != "VENDOR_CLAIMED":
            problems.append(
                f"{NV_DOMAIN_PARAMETER_ID} grade {domain.evidence_grade!r} != "
                "'VENDOR_CLAIMED' — the domain scale is a vendor public-page "
                "figure and must carry its grade"
            )
    for free_id in (
        NV_BW_SILENCE_PARAMETER_ID,
        NV_LAT_SILENCE_PARAMETER_ID,
        NV_FC_SILENCE_PARAMETER_ID,
    ):
        free = nv_frees.get(free_id)
        if free is None:
            problems.append(f"M1 profile missing free parameter {free_id}")
        elif free.domain != "FREE":
            problems.append(f"{free_id}.domain {free.domain!r} != 'FREE'")
    for parameter_id in (NV_IDENTITY_PARAMETER_ID, NV_DOMAIN_PARAMETER_ID):
        matching = [
            entry
            for entry in nv_platform_map.by_bucket("L0_READY")
            if entry.parameter_id == parameter_id
        ]
        if not matching:
            problems.append(
                f"M1 platform map has no L0_READY row for {parameter_id}"
            )
            continue
        backed = any(
            target.backend_id == "analytical_l0_crossbar"
            and target.topology_class == "fully_connected_crossbar"
            for entry in matching
            for target in entry.targets
        )
        if not backed:
            problems.append(
                f"M1 map row for {parameter_id} does not back the "
                "fully_connected_crossbar identity the NV flavor file uses"
            )
    return problems


# ---------------------------------------------------------------------------
# Whole-contract validation (reads the repo files)
# ---------------------------------------------------------------------------


def flavor_problems(repo_root: Path | str = REPO_ROOT) -> list[str]:
    """Every honesty check over the committed flavor artifacts."""
    root = Path(repo_root)
    problems: list[str] = []

    assumptions_path = root / ASSUMPTIONS_PATH
    if not assumptions_path.is_file():
        return [f"missing shared free-parameter record {ASSUMPTIONS_PATH}"]
    problems += assumptions_problems(
        yaml.safe_load(assumptions_path.read_text(encoding="utf-8"))
    )

    texts: dict[str, str] = {}
    datas: dict[str, dict] = {}
    for spec in FLAVOR_TOPOLOGIES:
        path = root / spec.path
        if not path.is_file():
            problems.append(f"missing flavor topology {spec.path}")
            continue
        texts[spec.path] = path.read_text(encoding="utf-8")
        datas[spec.path] = yaml.safe_load(texts[spec.path])
        problems += flavor_file_problems(spec, texts[spec.path], datas[spec.path])

    workload_path = root / WORKLOAD_PATH
    manifest_path = root / SWEEP_MANIFEST_PATH
    if not workload_path.is_file():
        problems.append(f"missing comparison workload {WORKLOAD_PATH}")
    if not manifest_path.is_file():
        problems.append(f"missing sweep manifest {SWEEP_MANIFEST_PATH}")
    if workload_path.is_file() and manifest_path.is_file():
        problems += workload_manifest_problems(
            yaml.safe_load(workload_path.read_text(encoding="utf-8")),
            yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
        )

    # The M1 three-architecture payload grid: the three identity-matched
    # crossbars (UEC control, UB paper, NVLink paper) on the same shared
    # workload and the full payload ladder the registry permits.
    three_arch_path = root / SWEEP_3ARCH_MANIFEST_PATH
    if not three_arch_path.is_file():
        problems.append(f"missing three-architecture sweep manifest {SWEEP_3ARCH_MANIFEST_PATH}")
    elif workload_path.is_file():
        problems += workload_manifest_problems(
            yaml.safe_load(workload_path.read_text(encoding="utf-8")),
            yaml.safe_load(three_arch_path.read_text(encoding="utf-8")),
            sweep_name=SWEEP_3ARCH_NAME,
            expected_topologies=THREE_ARCH_TOPOLOGIES,
            payload_sizes=THREE_ARCH_PAYLOAD_SIZES,
        )

    problems += provenance_problems(root)
    return problems


def assert_flavors_valid(repo_root: Path | str = REPO_ROOT) -> None:
    problems = flavor_problems(repo_root)
    if problems:
        raise FlavorConfigError(
            "cross-design flavor configs violate the honesty contract:\n- "
            + "\n- ".join(problems)
        )
