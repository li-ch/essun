"""Analytical L0 recursive-doubling AllReduce model (P2 stage S3).

Transport model: r ranks (r a power of two, r >= 2) fully reachable from one
another with uniform per-pair exchange latency L (ns) and per-rank injection
bandwidth B (bytes/ns). The fabric assumption is the same single-port
non-blocking fully-connected fabric as the crossbar backend (S1); what
differs is the ALGORITHM — a partner schedule, not a pipelined per-peer
chunk schedule. The power-of-two requirement and the serialized-step
execution are MODELING ASSUMPTIONS (A-L0D-POW2, A-L0D-STEP in
experiments/vertical_slice/assumptions_l0.yaml), not standard-derived facts.

AllReduce is the standard two-phase recursive halving + recursive doubling
decomposition (Thakur-Gropp-Rabenseifner, "Optimization of Collective
Communication Operations in MPICH", 2005). With k = log2(r) steps per phase
and exactly ONE exchange partner per rank per step (partner = rank XOR
2^(i-1) at step i), each step costs chunk_i/B + L:

  Reduce phase (recursive halving reduce-scatter): step i sends half of the
  current buffer, chunk_i = M / 2^i for i = 1..k. Every rank ends with M/r
  reduced bytes.

      t_reduce(M, r) = sum_i (M/2^i)/B + k*L = (r-1)/r * M/B + k*L

  Broadcast phase (recursive doubling allgather of the result): step i sends
  chunk_i = 2^(i-1) * M/r for i = 1..k (doubling payload).

      t_bcast(M, r) = sum_i (2^(i-1)*M/r)/B + k*L = (r-1)/r * M/B + k*L

  AllReduce (serialized phases, A-L0D-STEP):

      t(M, r) = 2*(r-1)/r * M/B + 2*log2(r)*L

Per-rank wire traffic (sent bytes; every sent byte is received once by the
partner, so conservation holds exactly):

    T(M, r) = (1 - 1/r + 1 - 1/r) * M = 2*(r-1)/r * M
    total wire across ranks = 2*(r-1)*M

— identical traffic to the flat ring and the single-port crossbar: all three
L0 designs differ only in the latency chain (ring 2(r-1)L, recursive
doubling 2*log2(r)*L, pipelined crossbar 2L). Under the shared single-port
linear model t_rd = t_crossbar + 2*(log2(r) - 1)*L: same wire bytes, longer
latency chain; and t_rd = t_ring - 2*(r - 1 - log2(r))*L: same wire bytes,
shorter latency chain. At r = 2 (k = 1) all three identities coincide. These
emerging design-space properties are what this backend exists to expose.

Non-power-of-two ranks are REJECTED at load time: the ragged/non-power
splitting variants are different identities (A-L0D-POW2) and are declared
unsupported below, not silently mis-evaluated.

All arithmetic uses :class:`fractions.Fraction`. B and L are free parameters
carried by the assumptions file — NOT standard-derived values and NOT
measurements (provenance rules).

Divisibility (O1 honesty fix, increment 5a; assumption A-L0D-DIV in
experiments/vertical_slice/assumptions_l0.yaml): the halving schedule sends
chunks M/2^i and the doubling schedule sends chunks 2^(i-1)*M/r, so the
construction is physically realizable only when r divides M (with r a power
of two this also makes every M/2^i integral). Non-divisible payloads are
rejected at execution time (via
:func:`essun.backends.analytical.l0.require_divisible`) rather than
silently evaluated as a fractional-chunk schedule.

O-CONSERVATION honesty label (O6, increment 5a): the conservation check is
an ALGEBRAIC SELF-CHECK of this model's own byte accounting (per-rank
traffic summed over ranks equals the wire identity by construction), not an
independent physical measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from essun.backends.analytical.l0 import require_divisible

BACKEND_ID = "analytical_l0_recursive_doubling"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0",
    "collectives": ("allreduce_recursive_doubling",),
    "transport_model": "bandwidth_latency_exchange_steps",
    "observables": ("O-CONSERVATION", "O-CCT"),
    "explicitly_unsupported": (
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "non_power_of_two_ranks",
        "ragged_non_power_splitting",
        "overlapped_phases",
        "multi_partner_per_step",
        "standard_specific_semantics",
    ),
}


def _log2_steps(ranks: int) -> int:
    """k = log2(r) for a power-of-two r (checked by the loader)."""
    steps = 0
    group = ranks
    while group > 1:
        group //= 2
        steps += 1
    return steps


def is_power_of_two(ranks: int) -> bool:
    return ranks >= 1 and ranks & (ranks - 1) == 0


@dataclass(frozen=True)
class RecursiveDoublingConfig:
    topology_id: str
    ranks: int  # r, power of two, >= 2
    injection_bytes_per_ns: Fraction  # B: per-rank injection bandwidth
    pair_latency_ns: Fraction  # L: uniform per-pair exchange latency
    steps: int  # k = log2(r), derived and re-checked at load


def load_recursive_doubling_config(data: dict) -> RecursiveDoublingConfig:
    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    ranks = int(data["ranks"])
    if ranks < 2:
        raise ValueError(
            f"{BACKEND_ID}: recursive doubling needs ranks >= 2, got {ranks}"
        )
    if not is_power_of_two(ranks):
        raise ValueError(
            f"{BACKEND_ID}: recursive doubling requires a power-of-two rank "
            f"count, got {ranks}; ragged non-power variants are a different "
            "identity and are explicitly unsupported"
        )
    return RecursiveDoublingConfig(
        topology_id=str(data["topology_id"]),
        ranks=ranks,
        injection_bytes_per_ns=frac(data["nic"]["injection_bytes_per_ns"]),
        pair_latency_ns=frac(data["link"]["pair_latency_ns"]),
        steps=_log2_steps(ranks),
    )


def reduce_step_chunk(message_bytes: int, step: int, ranks: int) -> Fraction:
    """chunk_i = M / 2^i (recursive halving): halving payload per step."""
    if not 1 <= step <= _log2_steps(ranks):
        raise ValueError(f"reduce step {step} out of range 1..{_log2_steps(ranks)}")
    return Fraction(message_bytes, 2**step)


def broadcast_step_chunk(message_bytes: int, step: int, ranks: int) -> Fraction:
    """chunk_i = 2^(i-1) * M / r (recursive doubling): doubling payload per step."""
    steps = _log2_steps(ranks)
    if not 1 <= step <= steps:
        raise ValueError(f"broadcast step {step} out of range 1..{steps}")
    return Fraction(2 ** (step - 1) * message_bytes, ranks)


def rd_reduce_phase_time_ns(
    message_bytes: int, infra: RecursiveDoublingConfig
) -> Fraction:
    """t_reduce = sum_i (M/2^i)/B + k*L = (r-1)/r * M/B + k*L (exact step sum)."""
    total = Fraction(0)
    for step in range(1, infra.steps + 1):
        chunk = reduce_step_chunk(message_bytes, step, infra.ranks)
        total += chunk / infra.injection_bytes_per_ns + infra.pair_latency_ns
    return total


def rd_broadcast_phase_time_ns(
    message_bytes: int, infra: RecursiveDoublingConfig
) -> Fraction:
    """t_bcast = sum_i (2^(i-1)*M/r)/B + k*L = (r-1)/r * M/B + k*L."""
    total = Fraction(0)
    for step in range(1, infra.steps + 1):
        chunk = broadcast_step_chunk(message_bytes, step, infra.ranks)
        total += chunk / infra.injection_bytes_per_ns + infra.pair_latency_ns
    return total


def rd_allreduce_time_ns(
    message_bytes: int, infra: RecursiveDoublingConfig
) -> Fraction:
    """t = t_reduce + t_bcast = 2*(r-1)/r * M/B + 2*log2(r)*L (serialized phases)."""
    return rd_reduce_phase_time_ns(message_bytes, infra) + rd_broadcast_phase_time_ns(
        message_bytes, infra
    )


def rd_traffic_per_rank(message_bytes: int, ranks: int) -> Fraction:
    """T = 2*(r-1)/r * M — same per-rank wire as the flat ring and crossbar."""
    return Fraction(2 * (ranks - 1) * message_bytes, ranks)


def execute(ops, infra: RecursiveDoublingConfig) -> dict:
    """Execute AllReduce ops on the L0 recursive-doubling model.

    O-CONSERVATION (exact): for each op, per-rank traffic summed over ranks
    equals 2*(r-1)*M — every wire byte is sent once and received once by the
    step partner; nothing is created or lost. Checked by exact Fraction
    equality; any violation raises. This is an algebraic self-check of the
    model's own accounting, not an independent physical check (O6).

    Divisibility (O1, A-L0D-DIV): each op's payload must be divisible by the
    rank count (halving chunks M/2^i and doubling chunks 2^(i-1)*M/r stay
    integral); non-divisible payloads are rejected before any identity is
    evaluated.

    O-CCT (analytical): per-op completion time under the two-phase
    recursive-doubling equation, with the per-phase and per-step (chunk, time)
    decomposition recorded per op, plus mean/max aggregates.
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
            BACKEND_ID, op.op_id, op.payload_bytes, infra.ranks, "A-L0D-DIV"
        )
        per_rank = rd_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = per_rank * infra.ranks  # == 2*(r-1)*M exactly
        expected_wire = Fraction(2 * (infra.ranks - 1) * op.payload_bytes)
        if op_wire != expected_wire:
            violations.append(op.op_id)

        reduce_steps = []
        broadcast_steps = []
        for step in range(1, infra.steps + 1):
            r_chunk = reduce_step_chunk(op.payload_bytes, step, infra.ranks)
            b_chunk = broadcast_step_chunk(op.payload_bytes, step, infra.ranks)
            reduce_steps.append(
                {
                    "step": step,
                    "chunk_bytes_exact": str(r_chunk),
                    "time_ns_exact": str(
                        r_chunk / infra.injection_bytes_per_ns
                        + infra.pair_latency_ns
                    ),
                }
            )
            broadcast_steps.append(
                {
                    "step": step,
                    "chunk_bytes_exact": str(b_chunk),
                    "time_ns_exact": str(
                        b_chunk / infra.injection_bytes_per_ns
                        + infra.pair_latency_ns
                    ),
                }
            )
        reduce_time = rd_reduce_phase_time_ns(op.payload_bytes, infra)
        broadcast_time = rd_broadcast_phase_time_ns(op.payload_bytes, infra)
        completion = reduce_time + broadcast_time
        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "payload_bytes": op.payload_bytes,
                "steps_per_phase": infra.steps,
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "reduce_steps": reduce_steps,
                "broadcast_steps": broadcast_steps,
                "reduce_phase_time_ns_exact": str(reduce_time),
                "broadcast_phase_time_ns_exact": str(broadcast_time),
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
            "steps_log2_ranks": infra.steps,
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
