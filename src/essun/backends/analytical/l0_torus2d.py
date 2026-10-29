"""Analytical L0 2D-torus (ring x ring) AllReduce model (P2 stage S2).

Transport model (homogeneous 2D torus): r = r1*r2 ranks on an r1 x r2 grid
with wrapped (ring) links in each dimension. A dimension-1 ring connects the
r1 ranks that share a dimension-2 coordinate (r2 disjoint rings of size r1);
symmetrically for dimension 2. All links share one bandwidth B (bytes/ns) and
one per-hop latency L (ns) — the uniform-link model is the modeling
assumption A-L0T-UNIF in experiments/vertical_slice/assumptions_l0.yaml.

AllReduce is the standard per-dimension (two-phase, row-then-column)
decomposition on a Cartesian grid: a full ring AllReduce of the entire
message M within each dimension-1 ring, then a full ring AllReduce of M
within each dimension-2 ring. Dimensions execute SEQUENTIALLY
(modeling assumption A-L0T-SEQ): dimension-1 AllReduce leaves every rank
with its ring's partial sum (r2 disjoint partial sums); dimension-2
AllReduce then sums the r1 partial sums, so every rank ends with the global
sum — correct semantics with no over-reduction. Because the phases do not
overlap, each dimension's links are used exclusively and the completion
time is the sum over dimensions:

    t_2d(M, r1, r2) = t_ring(M, r1) + t_ring(M, r2)
    t_ring(M, k)     = 2*(k-1)/k * M / B + 2*(k-1)*L

where t_ring is the landed unidirectional-ring identity (l0.py), whose two
phases are the standard reduce-scatter + allgather decomposition
(Thakur-Rabenseifner direct-algorithm linear model): each phase moves
(k-1)/k * M bytes per rank at bandwidth B and (k-1) hops at latency L.

Wire traffic (exact, per rank, sum over dimensions):

    T_2d(M, r1, r2) = 2*(r1-1)/r1 * M + 2*(r2-1)/r2 * M
                    = 2 * (2 - 1/r1 - 1/r2) * M

Total bytes on all wires: r * T_2d = 2*(2r - r1 - r2) * M. Note this naive
full-M-per-dimension composition moves MORE wire than a flat ring over all r
ranks (2*(r-1)/r*M per rank): the trade is a shorter latency chain
(2*(r1 + r2 - 2) vs 2*(r - 1) hops) against more bandwidth. That trade is
the design-space comparison this backend exists for. An interleaved
variant (reduce-scatter in dim 1, AllReduce of the M/r1 chunk in dim 2,
allgather in dim 1) matches the flat ring's traffic while keeping the short
latency chain — it is a DIFFERENT identity and is declared unsupported here
(A-L0T-SEQ); nothing in this module evaluates it.

Degenerate shapes are rejected at load time: each dimension needs >= 2
ranks to wrap into a ring, and the grid must satisfy r1*r2 == ranks.

All arithmetic uses :class:`fractions.Fraction`. B and L are free parameters
carried by the assumptions file — NOT standard-derived values and NOT
measurements (provenance rules).

Divisibility (O1 honesty fix, increment 5a; assumption A-L0T-DIV in
experiments/vertical_slice/assumptions_l0.yaml): each dimension's ring
phase moves chunks of M/r_d bytes, so the construction is physically
realizable only when r1 divides M and r2 divides M. Non-divisible payloads
are rejected at execution time (via
:func:`essun.backends.analytical.l0.require_divisible`) rather than
silently evaluated as a fractional-chunk schedule.

O-CONSERVATION honesty label (O6, increment 5a): the conservation check is
an ALGEBRAIC SELF-CHECK of this model's own byte accounting (per-ring
traffic summed over rings equals the per-dimension wire identity by
construction), not an independent physical measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from essun.backends.analytical.l0 import (
    InfraConfig,
    require_divisible,
    ring_allreduce_time_ns,
    ring_traffic_per_rank,
)

BACKEND_ID = "analytical_l0_torus2d"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0",
    "collectives": ("allreduce_torus2d",),
    "transport_model": "bandwidth_latency_torus2d_sequential_dims",
    "observables": ("O-CONSERVATION", "O-CCT"),
    "explicitly_unsupported": (
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "overlapped_dimensions",
        "per_dimension_heterogeneous_links",
        "interleaved_rs_ag_decomposition",
        "standard_specific_semantics",
    ),
}


@dataclass(frozen=True)
class Torus2DConfig:
    topology_id: str
    ranks: int  # r = dim1_ranks * dim2_ranks
    dim1_ranks: int  # r1: ranks per dimension-1 ring
    dim2_ranks: int  # r2: ranks per dimension-2 ring
    link_bytes_per_ns: Fraction  # B: uniform across both dimensions (A-L0T-UNIF)
    hop_latency_ns: Fraction  # L: uniform across both dimensions (A-L0T-UNIF)

    def dim_ring_view(self, dim: int) -> InfraConfig:
        """Ring view of one dimension, reusing the landed l0 ring kernel."""
        group = self.dim1_ranks if dim == 1 else self.dim2_ranks
        return InfraConfig(
            topology_id=f"{self.topology_id}:dim{dim}",
            ranks=group,
            link_bytes_per_ns=self.link_bytes_per_ns,
            hop_latency_ns=self.hop_latency_ns,
        )


def load_torus2d_config(data: dict) -> Torus2DConfig:
    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    ranks = int(data["ranks"])
    dim1 = int(data["grid"]["dim1_ranks"])
    dim2 = int(data["grid"]["dim2_ranks"])
    if dim1 < 2 or dim2 < 2:
        raise ValueError(
            f"{BACKEND_ID}: a torus dimension must wrap >= 2 ranks, got {dim1}x{dim2}"
        )
    if dim1 * dim2 != ranks:
        raise ValueError(
            f"{BACKEND_ID}: grid {dim1}x{dim2} does not tile ranks={ranks} exactly"
        )
    link = data["link"]
    return Torus2DConfig(
        topology_id=str(data["topology_id"]),
        ranks=ranks,
        dim1_ranks=dim1,
        dim2_ranks=dim2,
        link_bytes_per_ns=frac(link["bytes_per_ns"]),
        hop_latency_ns=frac(link["hop_latency_ns"]),
    )


def torus2d_dim_time_ns(message_bytes: int, dim: int, infra: Torus2DConfig) -> Fraction:
    """Per-dimension ring AllReduce time over the FULL message M.

    t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L — the landed l0 identity
    (standard two-phase reduce-scatter + allgather ring model), applied to
    the dimension's ring; computed by the landed kernel itself.
    """
    group = infra.dim1_ranks if dim == 1 else infra.dim2_ranks
    return ring_allreduce_time_ns(message_bytes, group, infra.dim_ring_view(dim))


def torus2d_allreduce_time_ns(
    message_bytes: int, infra: Torus2DConfig
) -> Fraction:
    """t_2d = t_ring(M, r1) + t_ring(M, r2): sum over dimensions (A-L0T-SEQ)."""
    return torus2d_dim_time_ns(message_bytes, 1, infra) + torus2d_dim_time_ns(
        message_bytes, 2, infra
    )


def torus2d_dim_traffic_per_rank(message_bytes: int, dim: int, infra: Torus2DConfig) -> Fraction:
    """Per-rank wire bytes in one dimension: 2*(k-1)/k * M for k = r_dim.

    Computed by the landed ring identity (l0.ring_traffic_per_rank).
    """
    group = infra.dim1_ranks if dim == 1 else infra.dim2_ranks
    return ring_traffic_per_rank(message_bytes, group)


def torus2d_traffic_per_rank(message_bytes: int, infra: Torus2DConfig) -> Fraction:
    """T_2d = 2*(r1-1)/r1*M + 2*(r2-1)/r2*M = 2*(2 - 1/r1 - 1/r2)*M per rank."""
    return ring_traffic_per_rank(
        message_bytes, infra.dim1_ranks
    ) + ring_traffic_per_rank(message_bytes, infra.dim2_ranks)


def execute(ops, infra: Torus2DConfig) -> dict:
    """Execute AllReduce ops on the L0 2D-torus model and emit observations.

    O-CONSERVATION (exact, per dimension): dimension d has r/r_d disjoint
    rings, each ring AllReduce puts exactly 2*(r_d-1)*M bytes on its wires
    (sent once, received once), so the dimension's total wire is
    2*(r_d-1)*M*(r/r_d). Checked by exact Fraction equality per dimension;
    any violation raises. This is an algebraic self-check of the model's own
    accounting, not an independent physical check (O6).

    Divisibility (O1, A-L0T-DIV): each op's payload must be divisible by
    BOTH dimension sizes (chunks of M/r_d per ring phase); non-divisible
    payloads are rejected before any identity is evaluated.

    O-CCT (analytical): per-op completion time under the sum-over-dimensions
    equation, with the per-dimension decomposition recorded per op, plus
    mean/max aggregates.
    """
    per_op = []
    total_wire = Fraction(0)
    violations: list[str] = []
    times: list[Fraction] = []

    for op in ops:
        if op.collective != "allreduce":
            raise ValueError(
                f"{BACKEND_ID} capability: collective {op.collective!r} not supported (op {op.op_id})"
            )
        if len(op.comm_ranks) != infra.ranks:
            raise ValueError(
                f"op {op.op_id}: comm group size {len(op.comm_ranks)} != topology ranks {infra.ranks}"
            )
        require_divisible(
            BACKEND_ID, op.op_id, op.payload_bytes, infra.dim1_ranks, "A-L0T-DIV"
        )
        require_divisible(
            BACKEND_ID, op.op_id, op.payload_bytes, infra.dim2_ranks, "A-L0T-DIV"
        )
        # Per-dimension traffic and conservation.
        dim_traffic = {}
        dim_wire = {}
        for dim, group in ((1, infra.dim1_ranks), (2, infra.dim2_ranks)):
            per_rank = ring_traffic_per_rank(op.payload_bytes, group)
            wire = per_rank * infra.ranks
            # r/group disjoint rings, each wiring 2*(group-1)*M exactly.
            expected = Fraction(
                2 * (group - 1) * op.payload_bytes * (infra.ranks // group)
            )
            if wire != expected:
                violations.append(op.op_id)
            dim_traffic[dim] = per_rank
            dim_wire[dim] = wire
        per_rank_total = dim_traffic[1] + dim_traffic[2]

        dim1_time = torus2d_dim_time_ns(op.payload_bytes, 1, infra)
        dim2_time = torus2d_dim_time_ns(op.payload_bytes, 2, infra)
        completion = dim1_time + dim2_time
        times.append(completion)
        op_wire = dim_wire[1] + dim_wire[2]
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "payload_bytes": op.payload_bytes,
                "dim1_group_ranks": infra.dim1_ranks,
                "dim2_group_ranks": infra.dim2_ranks,
                "dim1_per_rank_wire_bytes_exact": str(dim_traffic[1]),
                "dim2_per_rank_wire_bytes_exact": str(dim_traffic[2]),
                "per_rank_wire_bytes_exact": str(per_rank_total),
                "dim1_wire_bytes_exact": str(dim_wire[1]),
                "dim2_wire_bytes_exact": str(dim_wire[2]),
                "total_wire_bytes_exact": str(op_wire),
                "dim1_time_ns_exact": str(dim1_time),
                "dim2_time_ns_exact": str(dim2_time),
                "completion_time_ns_exact": str(completion),
                "completion_time_ns": float(completion),
            }
        )

    if violations:
        raise AssertionError(
            f"O-CONSERVATION violated for ops {violations}; this is a model bug, not a tunable parameter"
        )

    count = len(times)
    mean_time = sum(times) / count if count else Fraction(0)
    return {
        "backend_id": BACKEND_ID,
        "model": {
            "transport_model": CAPABILITIES["transport_model"],
            "topology_id": infra.topology_id,
            "ranks": infra.ranks,
            "dim1_ranks": infra.dim1_ranks,
            "dim2_ranks": infra.dim2_ranks,
            "link_bytes_per_ns_exact": str(infra.link_bytes_per_ns),
            "hop_latency_ns_exact": str(infra.hop_latency_ns),
        },
        "observables": {
            "O-CONSERVATION": {
                "kind": "exact",
                "ops_checked": count,
                "violations": 0,
                "total_wire_bytes_exact": str(total_wire),
            },
            "O-CCT": {
                "kind": "analytical",
                "ops": count,
                "completion_time_ns_mean_exact": str(mean_time),
                "completion_time_ns_mean": float(mean_time),
                "completion_time_ns_max": float(max(times)) if times else None,
            },
        },
        "per_op": per_op,
    }
