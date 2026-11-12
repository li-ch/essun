"""Analytical L0 multi-plane switched topology backend.

Model: ``P`` parallel switch planes, each an ``N``-port single-tier
switch; every rank holds one port per plane, so the per-rank AGGREGATE
injection bandwidth is ``P * B_port``. One collective op stripes its
payload evenly across the planes (``M/P`` per plane) and all planes
transfer concurrently, so the op completes when the slowest plane
finishes:

    per-rank wire traffic  T(M, N)   = 2 * (N - 1) / N * M
    completion time        t(M,N,P)  = 2 * (N - 1) / N * (M / P) / B_port + 2 * L + E

Equivalently: a fully-connected crossbar whose bandwidth term uses the
aggregate injection ``P * B_port`` while each phase still pays one pair
latency ``L`` (a plane traversal is not faster because there are more
planes). The phase decomposition mirrors the crossbar backend:
reduce-scatter and all-gather each transfer ``(N-1)/N * (M/P)`` at
``B_port`` plus one ``L``; ``E`` — the optional endpoint (software)
latency — is charged ONCE per collective op (A-L0E-CHG, shared rule).

Divisibility (A-L0M-DIV): the equal-chunk striping needs ``ranks * planes``
to divide ``M`` so every per-plane per-rank chunk is an integral byte
count; non-divisible payloads are rejected at execution time (same guard
family as A-L0-DIV / A-L0X-DIV).

Honesty labels (same family): O-CONSERVATION and O-TRAFFIC-IMBALANCE are
ALGEBRAIC SELF-CHECKS of the model's own accounting, not physical
measurements. Explicitly unsupported: congestion, credit-based flow
control, packetization/FLIT effects, in-network computing, overlapping
collectives, heterogeneous planes, uneven striping, and any
standard-specific semantics.

Scope fence: NOT registered in the run-path or sweep registries (same
rule as the L0.5 atlas cells) — integration is a separate
capability-gated step. The module's own loader checks
``topology_class: multiplane_switch`` so no other family's topology file
can load through it silently.

Evidence label: [IMPLEMENTED_UNVERIFIED] — identities and determinism
tested; no claim about any physical fabric.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from essun.backends.analytical.l0 import (
    endpoint_term_ns,
    load_endpoint_latency_ns,
    require_divisible,
)

BACKEND_ID = "analytical_l0_multiplane"

TOPOLOGY_CLASS = "multiplane_switch"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0",
    "collectives": ("allreduce_ring_striped",),
    "transport_model": "bandwidth_latency_multiplane_switch",
    "observables": ("O-CONSERVATION", "O-CCT", "O-TRAFFIC-IMBALANCE"),
    "explicitly_unsupported": (
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "heterogeneous_planes",
        "uneven_striping",
        "standard_specific_semantics",
    ),
}


@dataclass(frozen=True)
class MultiplaneConfig:
    topology_id: str
    ranks: int          # N: xPUs, one port per plane each
    planes: int         # P: parallel single-tier switch planes
    port_bytes_per_ns: Fraction   # B_port: per-plane port injection bandwidth
    pair_latency_ns: Fraction     # L: uniform per-plane traversal latency
    # E: endpoint (software) latency per collective op (free, A-L0E-LAT).
    # None = the term is NOT declared — the landed identity, byte-for-byte.
    endpoint_latency_ns: Fraction | None = None


def load_multiplane_config(data: dict) -> MultiplaneConfig:
    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    klass = data.get("topology_class")
    if klass != TOPOLOGY_CLASS:
        raise ValueError(
            f"{BACKEND_ID}: topology_class {klass!r} != {TOPOLOGY_CLASS!r}; "
            "each backend loads only its own class (scope fence)"
        )
    ranks = int(data["ranks"])
    planes = int(data["planes"])
    if ranks < 2:
        raise ValueError(
            f"{BACKEND_ID}: single-tier switch needs ranks >= 2, got {ranks}"
        )
    if planes < 1:
        raise ValueError(f"{BACKEND_ID}: planes must be >= 1, got {planes}")
    return MultiplaneConfig(
        topology_id=str(data["topology_id"]),
        ranks=ranks,
        planes=planes,
        port_bytes_per_ns=frac(data["nic"]["port_bytes_per_ns"]),
        pair_latency_ns=frac(data["link"]["pair_latency_ns"]),
        endpoint_latency_ns=load_endpoint_latency_ns(data),
    )


def multiplane_traffic_per_rank(message_bytes: int, ranks: int) -> Fraction:
    """T(M, N) = 2*(N-1)/N * M — striping changes timing, not wire traffic."""
    return Fraction(2 * (ranks - 1) * message_bytes, ranks)


def multiplane_reduce_scatter_time_ns(
    message_bytes: int, ranks: int, planes: int, infra: MultiplaneConfig
) -> Fraction:
    """t_rs = (N-1)/N * (M/P) / B_port + L — per-plane striped phase."""
    return (
        Fraction((ranks - 1) * message_bytes, ranks * planes)
        / infra.port_bytes_per_ns
        + infra.pair_latency_ns
    )


def multiplane_allgather_time_ns(
    message_bytes: int, ranks: int, planes: int, infra: MultiplaneConfig
) -> Fraction:
    """t_ag = (N-1)/N * (M/P) / B_port + L — symmetric to reduce-scatter."""
    return multiplane_reduce_scatter_time_ns(message_bytes, ranks, planes, infra)


def multiplane_allreduce_time_ns(
    message_bytes: int, ranks: int, planes: int, infra: MultiplaneConfig
) -> Fraction:
    """t = t_rs + t_ag + E = 2*(N-1)/N * M/(P*B_port) + 2L + E."""
    return (
        multiplane_reduce_scatter_time_ns(message_bytes, ranks, planes, infra)
        + multiplane_allgather_time_ns(message_bytes, ranks, planes, infra)
        + endpoint_term_ns(infra)
    )


def execute(ops, infra: MultiplaneConfig) -> dict:
    """Execute AllReduce ops on the multi-plane model and emit observations.

    Same observable contract as the crossbar backend: O-CONSERVATION exact
    (algebraic self-check), O-CCT analytical with phase decomposition,
    per-op exact fractions alongside floats. Divisibility guard divisor is
    ranks * planes (A-L0M-DIV).
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
            BACKEND_ID,
            op.op_id,
            op.payload_bytes,
            infra.ranks * infra.planes,
            "A-L0M-DIV",
        )
        per_rank = multiplane_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = per_rank * infra.ranks  # == 2*(N-1)*M exactly
        expected_wire = Fraction(2 * (infra.ranks - 1) * op.payload_bytes)
        if op_wire != expected_wire:
            violations.append(op.op_id)
        reduce_scatter = multiplane_reduce_scatter_time_ns(
            op.payload_bytes, infra.ranks, infra.planes, infra
        )
        allgather = multiplane_allgather_time_ns(
            op.payload_bytes, infra.ranks, infra.planes, infra
        )
        endpoint = endpoint_term_ns(infra)
        completion = reduce_scatter + allgather + endpoint
        times.append(completion)
        total_wire += op_wire
        op_record = {
            "op_id": op.op_id,
            "payload_bytes": op.payload_bytes,
            "per_rank_wire_bytes_exact": str(per_rank),
            "total_wire_bytes_exact": str(op_wire),
            "reduce_scatter_time_ns_exact": str(reduce_scatter),
            "allgather_time_ns_exact": str(allgather),
            "completion_time_ns_exact": str(completion),
            "completion_time_ns": float(completion),
        }
        if infra.endpoint_latency_ns is not None:
            op_record["endpoint_term_ns_exact"] = str(endpoint)
        per_op.append(op_record)

    if violations:
        raise AssertionError(
            f"O-CONSERVATION violated for ops {violations}; this is a model bug, not a tunable parameter"
        )

    count = len(times)
    mean_time = sum(times) / count if count else Fraction(0)
    model = {
        "transport_model": CAPABILITIES["transport_model"],
        "topology_id": infra.topology_id,
        "ranks": infra.ranks,
        "planes": infra.planes,
        "port_bytes_per_ns_exact": str(infra.port_bytes_per_ns),
        "aggregate_injection_bytes_per_ns_exact": str(
            infra.planes * infra.port_bytes_per_ns
        ),
        "pair_latency_ns_exact": str(infra.pair_latency_ns),
    }
    if infra.endpoint_latency_ns is not None:
        model["endpoint_latency_ns_exact"] = str(infra.endpoint_latency_ns)
    return {
        "backend_id": BACKEND_ID,
        "model": model,
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
