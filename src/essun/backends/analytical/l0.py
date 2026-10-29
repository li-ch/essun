"""Analytical L0 backend (first increment).

Model: chunked ring AllReduce over a unidirectional ring with per-direction
link bandwidth B (bytes/ns) and per-hop latency L (ns). Identities:

    per-rank wire traffic  T(M, r) = 2 * (r - 1) / r * M
    completion time        t(M, r) = T(M, r) / B + 2 * (r - 1) * L

The single T/B bandwidth term assumes FULL-DUPLEX, uniform per-direction
links — send and receive proceed at B simultaneously on every link
(duplexity assumption A-L0-FD); half-duplex or heterogeneous-link models are
different identities.

All arithmetic uses :class:`fractions.Fraction`, so conservation checks are
exact. B and L are free parameters carried by the experiment's assumptions
file — they are NOT standard-derived values and NOT measurements
(provenance rules).

Divisibility (O1 honesty fix; assumption A-L0-DIV in
experiments/vertical_slice/assumptions_l0.yaml): the chunked construction
behind the identities is physically realizable with equal chunks only when
the rank count r divides the payload M, so every chunk M/r is an integral
byte count. The Fraction arithmetic would stay exact for any M, but a
non-divisible payload has no equal-chunk construction behind it; such ops
are therefore rejected at execution time (:func:`require_divisible`) instead
of silently evaluating a fractional-chunk schedule. Ragged or padded-chunk
variants are different identities and are not evaluated.

O-CONSERVATION honesty label (O6, increment 5a): the conservation check is
an ALGEBRAIC SELF-CHECK of this model's own byte accounting (per-rank
traffic summed over ranks equals the wire identity by construction), not an
independent physical measurement — a cross-fidelity sent-vs-received
comparison becomes meaningful only once a packet/FLIT backend exists.

Explicitly unsupported (capability-declared, rejected at compile time by the
orchestrator): congestion, credit-based flow control, packetization/FLIT
effects, in-network computing, overlapping collectives, and any
standard-specific semantics (UEC/UALink/... profiles remain PROPOSED until
later).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

BACKEND_ID = "analytical_l0"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0",
    "collectives": ("allreduce_ring",),
    "transport_model": "bandwidth_latency_ring",
    "observables": ("O-CONSERVATION", "O-CCT", "O-TRAFFIC-IMBALANCE"),
    "explicitly_unsupported": (
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "standard_specific_semantics",
    ),
}


@dataclass(frozen=True)
class InfraConfig:
    topology_id: str
    ranks: int
    link_bytes_per_ns: Fraction
    hop_latency_ns: Fraction


def load_infra(data: dict) -> InfraConfig:
    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    link = data["link"]
    return InfraConfig(
        topology_id=str(data["topology_id"]),
        ranks=int(data["ranks"]),
        link_bytes_per_ns=frac(link["bytes_per_ns"]),
        hop_latency_ns=frac(link["hop_latency_ns"]),
    )


def ring_traffic_per_rank(message_bytes: int, ranks: int) -> Fraction:
    return Fraction(2 * (ranks - 1) * message_bytes, ranks)


def ring_per_rank_totals(ops, ranks: int) -> tuple[Fraction, ...]:
    """Per-rank logical wire-traffic totals (O-TRAFFIC-IMBALANCE input).

    Under the chunked-ring algorithm each rank sends every op's full
    per-rank traffic 2*(r-1)/r*M to its single ring successor, so rank i's
    total is sum over ops of ring_traffic_per_rank(M, r) — identical for
    every rank by construction. Emitted as the logical-traffic pattern; the
    imbalance max-min is exactly 0 (an algebraic self-check of the declared
    pattern, same honesty status as O-CONSERVATION, not a physical
    measurement of hardware imbalance).
    """
    per_op = [ring_traffic_per_rank(op.payload_bytes, ranks) for op in ops]
    return tuple(sum(per_op, start=Fraction(0)) for _ in range(ranks))


def require_divisible(
    backend_id: str, op_id: str, message_bytes: int, divisor: int, assumption_id: str
) -> None:
    """O1 input guard shared by the L0 backends: reject non-integral chunking.

    The equal-chunk constructions assume ``divisor`` divides ``message_bytes``
    so every chunk is an integral byte count (see the per-model divisibility
    assumption named by ``assumption_id`` in
    experiments/vertical_slice/assumptions_l0.yaml). The Fraction identities
    would still compute for any payload, but the construction behind them
    would not exist, so execution rejects such ops explicitly.
    """
    if message_bytes % divisor:
        raise ValueError(
            f"{backend_id}: op {op_id}: payload {message_bytes} bytes is not "
            f"divisible by {divisor}; the equal-chunk construction requires "
            f"integral chunk byte counts (divisibility assumption "
            f"{assumption_id} in experiments/vertical_slice/assumptions_l0.yaml). "
            "Ragged or padded-chunk variants are different identities and are "
            "explicitly rejected"
        )


def ring_allreduce_time_ns(message_bytes: int, ranks: int, infra: InfraConfig) -> Fraction:
    traffic = ring_traffic_per_rank(message_bytes, ranks)
    return traffic / infra.link_bytes_per_ns + 2 * (ranks - 1) * infra.hop_latency_ns


def execute(ops, infra: InfraConfig) -> dict:
    """Execute AllReduce ops on the L0 ring model and emit observations.

    O-CONSERVATION (exact): for each op, total bytes sent across all ranks
    equals total bytes received equals 2*(r-1)*M — every wire byte is sent
    once and received once; nothing is created or lost. Checked by exact
    Fraction equality; any violation raises. This is an algebraic self-check
    of the model's own accounting, not an independent physical check (O6).

    Divisibility (O1, A-L0-DIV): each op's payload must be divisible by the
    rank count; non-divisible payloads are rejected before any identity is
    evaluated.

    O-CCT (analytical): per-op completion time under the ring equation, with
    mean/max aggregates. Exact fractions are serialized alongside floats.

    O-TRAFFIC-IMBALANCE (logical): per-rank logical wire-traffic
    totals; under the per-rank-symmetric chunked-ring algorithm they are
    exactly equal, so imbalance max-min == 0 bytes. Like O-CONSERVATION this
    is an ALGEBRAIC SELF-CHECK of the model's own declared pattern, not a
    physical measurement; a nonzero imbalance raises (structural bug).
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
            BACKEND_ID, op.op_id, op.payload_bytes, infra.ranks, "A-L0-DIV"
        )
        per_rank = ring_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = per_rank * infra.ranks  # == 2*(r-1)*M exactly
        expected_wire = Fraction(2 * (infra.ranks - 1) * op.payload_bytes)
        if op_wire != expected_wire:
            violations.append(op.op_id)
        completion = ring_allreduce_time_ns(op.payload_bytes, infra.ranks, infra)
        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "payload_bytes": op.payload_bytes,
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "completion_time_ns_exact": str(completion),
                "completion_time_ns": float(completion),
            }
        )

    if violations:
        raise AssertionError(
            f"O-CONSERVATION violated for ops {violations}; this is a model bug, not a tunable parameter"
        )

    # O-TRAFFIC-IMBALANCE (logical): the per-rank pattern must be exactly
    # uniform under the symmetric declared algorithm; derived from the
    # emitted pattern itself so the check trips if the construction drifts.
    totals = ring_per_rank_totals(ops, infra.ranks)
    imbalance = (max(totals) - min(totals)) if totals else Fraction(0)
    min_total = min(totals) if totals else Fraction(0)
    max_over_min = (max(totals) / min_total) if min_total > 0 else None
    if imbalance != 0:
        raise AssertionError(
            f"O-TRAFFIC-IMBALANCE: per-rank totals not uniform under the "
            f"symmetric declared algorithm (imbalance {imbalance} bytes); "
            "this is a model bug, not a tunable parameter"
        )

    count = len(times)
    mean_time = sum(times) / count if count else Fraction(0)
    return {
        "backend_id": BACKEND_ID,
        "model": {
            "transport_model": CAPABILITIES["transport_model"],
            "topology_id": infra.topology_id,
            "ranks": infra.ranks,
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
            "O-TRAFFIC-IMBALANCE": {
                "kind": "logical",
                "ranks": infra.ranks,
                "per_rank_total_wire_bytes_exact": [str(total) for total in totals],
                "imbalance_bytes_exact": str(imbalance),
                "max_over_min_exact": str(max_over_min) if max_over_min is not None else None,
                "violations": 0,
            },
        },
        "per_op": per_op,
    }
