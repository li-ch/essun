"""Analytical L0 fully-connected (crossbar) AllReduce model (P2 stage S1).

Transport model (single-port crossbar): r ranks are pairwise adjacent through
a non-blocking switch fabric with a uniform per-pair transfer latency L (ns).
Each rank injects through ONE port of total bandwidth B (bytes/ns) shared
across all r-1 peers. The single-port assumption is a MODELING ASSUMPTION
(A-L0X-PORT in experiments/vertical_slice/assumptions_l0.yaml), not a
standard-derived fact: a multi-port fabric, where each pair gets the full B,
follows a different identity and is declared unsupported below.

AllReduce is the textbook reduce-scatter + allgather decomposition over a
fully-connected network (Rabenseifner/Thakur-Rabenseifner direct-algorithm
linear model). Chunks pipeline behind the injection port, so each phase is
charged the per-pair latency once (the last byte of the phase arrives L ns
after its injection), not once per peer:

    reduce-scatter:  t_rs(M, r) = (r-1)/r * M / B + L
    allgather:       t_ag(M, r) = (r-1)/r * M / B + L
    AllReduce:       t(M, r)    = 2*(r-1)/r * M / B + 2L

In each phase every rank sends r-1 chunks of M/r bytes (one per peer), so the
per-rank wire traffic is

    T(M, r) = 2*(r-1)/r * M

and total wire bytes across all ranks are 2*(r-1)*M — the same conservation
identity as the ring backend (O-CONSERVATION is exact here too).

All arithmetic uses :class:`fractions.Fraction`. B and L are free parameters
carried by the assumptions file — NOT standard-derived values and NOT
measurements (provenance rules).

Divisibility (O1 honesty fix, increment 5a; assumption A-L0X-DIV in
experiments/vertical_slice/assumptions_l0.yaml): each phase sends r-1 chunks
of M/r bytes, so the construction is physically realizable only when r
divides M. Non-divisible payloads are rejected at execution time (via
:func:`essun.backends.analytical.l0.require_divisible`) rather than
silently evaluated as a fractional-chunk schedule.

O-CONSERVATION honesty label (O6, increment 5a): the conservation check is
an ALGEBRAIC SELF-CHECK of this model's own byte accounting (per-rank
traffic summed over ranks equals the wire identity by construction), not an
independent physical measurement.

Degenerate topologies: ranks < 2 are rejected at load time (the identity
would charge 2L of latency to a collective with no peers).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from essun.backends.analytical.l0 import require_divisible

BACKEND_ID = "analytical_l0_crossbar"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0",
    "collectives": ("allreduce_crossbar",),
    "transport_model": "bandwidth_latency_crossbar_single_port",
    "observables": ("O-CONSERVATION", "O-CCT"),
    "explicitly_unsupported": (
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "multi_port_injection",
        "nonuniform_pair_latency",
        "standard_specific_semantics",
    ),
}


@dataclass(frozen=True)
class CrossbarConfig:
    topology_id: str
    ranks: int
    injection_bytes_per_ns: Fraction  # B: per-rank single-port injection bandwidth
    pair_latency_ns: Fraction  # L: uniform per-pair transfer latency


def load_crossbar_config(data: dict) -> CrossbarConfig:
    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    ranks = int(data["ranks"])
    if ranks < 2:
        raise ValueError(
            f"{BACKEND_ID}: fully-connected topology needs ranks >= 2, got {ranks}"
        )
    return CrossbarConfig(
        topology_id=str(data["topology_id"]),
        ranks=ranks,
        injection_bytes_per_ns=frac(data["nic"]["injection_bytes_per_ns"]),
        pair_latency_ns=frac(data["link"]["pair_latency_ns"]),
    )


def crossbar_traffic_per_rank(message_bytes: int, ranks: int) -> Fraction:
    """T(M, r) = 2*(r-1)/r * M — (r-1) chunks of M/r sent per phase, 2 phases."""
    return Fraction(2 * (ranks - 1) * message_bytes, ranks)


def crossbar_reduce_scatter_time_ns(
    message_bytes: int, ranks: int, infra: CrossbarConfig
) -> Fraction:
    """t_rs = (r-1)/r * M / B + L — single-port sends serialized at B, one L."""
    return (
        Fraction((ranks - 1) * message_bytes, ranks) / infra.injection_bytes_per_ns
        + infra.pair_latency_ns
    )


def crossbar_allgather_time_ns(
    message_bytes: int, ranks: int, infra: CrossbarConfig
) -> Fraction:
    """t_ag = (r-1)/r * M / B + L — symmetric to the reduce-scatter phase."""
    return (
        Fraction((ranks - 1) * message_bytes, ranks) / infra.injection_bytes_per_ns
        + infra.pair_latency_ns
    )


def crossbar_allreduce_time_ns(
    message_bytes: int, ranks: int, infra: CrossbarConfig
) -> Fraction:
    """t = t_rs + t_ag = 2*(r-1)/r * M / B + 2L (serialized phases)."""
    return (
        crossbar_reduce_scatter_time_ns(message_bytes, ranks, infra)
        + crossbar_allgather_time_ns(message_bytes, ranks, infra)
    )


def execute(ops, infra: CrossbarConfig) -> dict:
    """Execute AllReduce ops on the L0 single-port crossbar model.

    O-CONSERVATION (exact): for each op, per-rank traffic summed over ranks
    equals 2*(r-1)*M — every wire byte is sent once and received once. Checked
    by exact Fraction equality; any violation raises. This is an algebraic
    self-check of the model's own accounting, not an independent physical
    check (O6).

    Divisibility (O1, A-L0X-DIV): each op's payload must be divisible by the
    rank count (chunks of M/r per phase); non-divisible payloads are
    rejected before any identity is evaluated.

    O-CCT (analytical): per-op completion time under the crossbar equation,
    with the phase decomposition recorded per op, plus mean/max aggregates.
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
            BACKEND_ID, op.op_id, op.payload_bytes, infra.ranks, "A-L0X-DIV"
        )
        per_rank = crossbar_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = per_rank * infra.ranks  # == 2*(r-1)*M exactly
        expected_wire = Fraction(2 * (infra.ranks - 1) * op.payload_bytes)
        if op_wire != expected_wire:
            violations.append(op.op_id)
        reduce_scatter = crossbar_reduce_scatter_time_ns(
            op.payload_bytes, infra.ranks, infra
        )
        allgather = crossbar_allgather_time_ns(op.payload_bytes, infra.ranks, infra)
        completion = reduce_scatter + allgather
        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "payload_bytes": op.payload_bytes,
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "reduce_scatter_time_ns_exact": str(reduce_scatter),
                "allgather_time_ns_exact": str(allgather),
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
            "injection_bytes_per_ns_exact": str(infra.injection_bytes_per_ns),
            "pair_latency_ns_exact": str(infra.pair_latency_ns),
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
