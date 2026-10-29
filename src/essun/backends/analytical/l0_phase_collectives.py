"""Analytical L0 ReduceScatter / AllGather phase collectives (P2 stage S4).

ReduceScatter and AllGather become FIRST-CLASS collectives, so workloads can
compose phases instead of only whole AllReduces. One algorithm family per
collective on each fabric that landed with a prior stage:

  Ring family — unidirectional ring (l0.py fabric: link bandwidth B,
  per-hop latency L). A phase forwards (r-1) chunks of M/r around the ring
  (pipelined direct-algorithm linear model, Thakur-Rabenseifner):

      t_rs_ring(M, r) = (r-1)/r * M / B + (r-1) * L     [frozen stage identity]
      t_ag_ring(M, r) = (r-1)/r * M / B + (r-1) * L

  Doubling family — power-of-two fully-connected exchange fabric
  (l0_recursive_doubling.py, stage S3). ReduceScatter is recursive halving
  and AllGather is recursive doubling (Thakur-Gropp-Rabenseifner, "Optimization
  of Collective Communication Operations in MPICH", 2005): the two phases are
  exactly the landed S3 AllReduce phases, now executable as standalone
  collectives (step chunks reused from l0d so the schedules cannot drift):

      t_rs_dbl(M, r) = sum_{i=1..k} (M/2^i)/B + k*L        = (r-1)/r*M/B + log2(r)*L
      t_ag_dbl(M, r) = sum_{i=1..k} (2^(i-1)*M/r)/B + k*L  = (r-1)/r*M/B + log2(r)*L
      with k = log2(r), one exchange partner per rank per step.

Message-size semantics (modeling assumption A-L0P-MSG): M is the per-rank
input size for ReduceScatter (every rank ends with M/r reduced bytes) and the
TOTAL gathered size for AllGather (every rank contributes M/r and ends with M
bytes). With this reading the phases compose exactly — the reason this stage
exists:

      AllReduce(M) = ReduceScatter(M) + AllGather(M)   (serialized, A-L0P-COMP)
      ring:  t_rs_ring + t_ag_ring == l0.ring_allreduce_time_ns
      dbl:   t_rs_dbl  + t_ag_dbl  == l0d.rd_allreduce_time_ns

Wire traffic (both families, one phase): each rank sends (r-1) chunks of
M/r bytes, so

      T_phase(M, r) = (r-1)/r * M    per rank
      total wire    = (r-1) * M      per op — conservation, exact

Every sent byte is received once (ring neighbor or step partner), so
O-CONSERVATION holds exactly. Emerging design-space property, pinned by
tests: ALL phase variants — ring, halving/doubling, and the crossbar phases
landed inside S1's AllReduce — move the SAME (r-1)/r*M per-rank wire bytes;
the phase algorithms differ ONLY in the latency chain per phase:
(r-1)*L (ring) >= log2(r)*L (halving/doubling) >= L (single-port crossbar).

Fabric/algorithm pairing (modeling assumption A-L0P-ALGO): ring phases run
on the ring fabric (l0.InfraConfig / l0.load_infra), halving/doubling phases
on the power-of-two exchange fabric (l0d.RecursiveDoublingConfig /
l0d.load_recursive_doubling_config, which rejects non-powers). Other
pairings are different identities and are not evaluated here. The crossbar
RS/AG identities exist in l0_crossbar as the internal phases of its
AllReduce decomposition; executing them as first-class ops is outside this
stage's pre-registered content.

All arithmetic uses :class:`fractions.Fraction`. B and L are the SAME free
parameters already registered for the two fabrics (A-L0-BW / A-L0-LAT for
the ring, A-L0D-BW / A-L0D-LAT for the exchange fabric) — this stage
introduces no new numeric parameters; its assumption entries (A-L0P-*)
cover the semantics and composition rules above.

Divisibility (O1 honesty fix, increment 5a; assumption A-L0P-DIV in
experiments/vertical_slice/assumptions_l0.yaml): every phase moves (r-1)
chunks of M/r bytes and ReduceScatter leaves each rank with M/r reduced
bytes, so the construction is physically realizable only when r divides M.
Non-divisible payloads are rejected at execution time (via
:func:`essun.backends.analytical.l0.require_divisible`) rather than
silently evaluated as a fractional-chunk schedule.

O-CONSERVATION honesty label (O6, increment 5a): the conservation check is
an ALGEBRAIC SELF-CHECK of this model's own byte accounting (per-rank
traffic summed over ranks equals the phase wire identity by construction),
not an independent physical measurement.
"""

from __future__ import annotations

from fractions import Fraction

from essun.backends.analytical import l0
from essun.backends.analytical import l0_recursive_doubling as l0d
from essun.backends.analytical.l0 import require_divisible

BACKEND_ID = "analytical_l0_phase_collectives"

# Single source of truth for the (collective, algorithm) pairings; the
# capability names and the algorithm-config loader are both derived from it.
_ALGORITHM_PAIRINGS = (
    ("reducescatter", "ring"),
    ("allgather", "ring"),
    ("reducescatter", "recursive_halving"),
    ("allgather", "recursive_doubling"),
)

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0",
    "collectives": tuple(f"{c}_{a}" for c, a in _ALGORITHM_PAIRINGS),
    "transport_model": "bandwidth_latency_phase_collectives",
    "observables": ("O-CONSERVATION", "O-CCT"),
    "explicitly_unsupported": (
        # Shared L0 exclusions (all backends).
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "standard_specific_semantics",
        # Stage S4 modeling assumptions.
        "overlapped_rs_ag_phases",  # A-L0P-COMP
        "ring_phases_on_exchange_fabric",  # A-L0P-ALGO pairings only
        "exchange_phases_on_ring_fabric",  # A-L0P-ALGO pairings only
        # Inherited from the doubling fabric family (S3, A-L0D-POW2/STEP).
        "non_power_of_two_ranks",
        "ragged_non_power_splitting",
        "multi_partner_per_step",
    ),
}

_PHASE_COLLECTIVES = ("reducescatter", "allgather")


def load_phase_algorithm_config(data: dict) -> tuple[dict, ...]:
    """Validate a phase-collective algorithm config.

    Input schema: experiments/topologies/phase_collectives8_free_params.yaml
    (the stage's algorithm YAML — it references the two committed fabrics
    rather than duplicating them). Every (collective, algorithm) pairing
    must be one of the capability-declared identities; other pairings are
    different identities (A-L0P-ALGO) and are rejected explicitly, mirroring
    the fabric loaders' explicit-refusal rule.
    """
    supported = frozenset(_ALGORITHM_PAIRINGS)
    entries = []
    for entry in data["collectives"]:
        key = (str(entry["collective"]), str(entry["algorithm"]))
        if key not in supported:
            raise ValueError(
                f"{BACKEND_ID}: pairing collective={key[0]!r}, "
                f"algorithm={key[1]!r} is not a capability-declared "
                "identity (A-L0P-ALGO); it is explicitly unsupported"
            )
        entries.append(
            {
                "collective": key[0],
                "algorithm": key[1],
                "topology": str(entry["topology"]),
            }
        )
    if not entries:
        raise ValueError(f"{BACKEND_ID}: algorithm config declares no pairings")
    return tuple(entries)


# ---------------------------------------------------------------------------
# Wire traffic and result semantics (exact, family-independent)
# ---------------------------------------------------------------------------


def phase_traffic_per_rank(message_bytes: int, ranks: int) -> Fraction:
    """T_phase = (r-1)/r * M — per-rank sent bytes of ONE phase.

    Each rank sends (r-1) chunks of M/r. Two phases make the landed ring /
    recursive-doubling AllReduce traffic 2*(r-1)/r*M (pinned by tests).
    """
    return Fraction((ranks - 1) * message_bytes, ranks)


def reducescatter_result_bytes(message_bytes: int, ranks: int) -> Fraction:
    """ReduceScatter leaves every rank with M/r reduced bytes."""
    return Fraction(message_bytes, ranks)


def allgather_result_bytes(message_bytes: int, ranks: int) -> Fraction:
    """AllGather leaves every rank with the full gathered M bytes."""
    return Fraction(message_bytes)


# ---------------------------------------------------------------------------
# Ring family (fabric: l0.InfraConfig, the landed ring topology)
# ---------------------------------------------------------------------------


def ring_reducescatter_time_ns(
    message_bytes: int, ranks: int, infra: l0.InfraConfig
) -> Fraction:
    """t_rs = (r-1)/r * M / B + (r-1) * L  [frozen stage identity]."""
    return (
        phase_traffic_per_rank(message_bytes, ranks) / infra.link_bytes_per_ns
        + (ranks - 1) * infra.hop_latency_ns
    )


def ring_allgather_time_ns(
    message_bytes: int, ranks: int, infra: l0.InfraConfig
) -> Fraction:
    """t_ag = (r-1)/r * M / B + (r-1) * L — symmetric to the RS phase."""
    return (
        phase_traffic_per_rank(message_bytes, ranks) / infra.link_bytes_per_ns
        + (ranks - 1) * infra.hop_latency_ns
    )


# ---------------------------------------------------------------------------
# Doubling family (fabric: l0d.RecursiveDoublingConfig, the landed S3 fabric)
# ---------------------------------------------------------------------------


def halving_reducescatter_time_ns(
    message_bytes: int, infra: l0d.RecursiveDoublingConfig
) -> Fraction:
    """t_rs = sum_i (M/2^i)/B + log2(r)*L = (r-1)/r * M/B + log2(r)*L.

    The literal per-step sum over the landed S3 halving schedule; the
    fractions telescope to the closed form (pinned by tests).
    """
    total = Fraction(0)
    for step in range(1, infra.steps + 1):
        chunk = l0d.reduce_step_chunk(message_bytes, step, infra.ranks)
        total += chunk / infra.injection_bytes_per_ns + infra.pair_latency_ns
    return total


def doubling_allgather_time_ns(
    message_bytes: int, infra: l0d.RecursiveDoublingConfig
) -> Fraction:
    """t_ag = sum_i (2^(i-1)*M/r)/B + log2(r)*L = (r-1)/r * M/B + log2(r)*L."""
    total = Fraction(0)
    for step in range(1, infra.steps + 1):
        chunk = l0d.broadcast_step_chunk(message_bytes, step, infra.ranks)
        total += chunk / infra.injection_bytes_per_ns + infra.pair_latency_ns
    return total


# ---------------------------------------------------------------------------
# Phase composition (the point of this stage)
# ---------------------------------------------------------------------------


def ring_allreduce_from_phases_time_ns(
    message_bytes: int, ranks: int, infra: l0.InfraConfig
) -> Fraction:
    """AllReduce(M) = RS(M) + AG(M), serialized phases (A-L0P-COMP).

    Equals l0.ring_allreduce_time_ns exactly — identity, not approximation;
    pinned by golden tests against independently derived literals.
    """
    return ring_reducescatter_time_ns(
        message_bytes, ranks, infra
    ) + ring_allgather_time_ns(message_bytes, ranks, infra)


def rd_allreduce_from_phases_time_ns(
    message_bytes: int, infra: l0d.RecursiveDoublingConfig
) -> Fraction:
    """AllReduce(M) = halving RS(M) + doubling AG(M) (A-L0P-COMP).

    Equals l0d.rd_allreduce_time_ns exactly — the S3 two-phase form.
    """
    return halving_reducescatter_time_ns(
        message_bytes, infra
    ) + doubling_allgather_time_ns(message_bytes, infra)


# ---------------------------------------------------------------------------
# Execution with observables
# ---------------------------------------------------------------------------


def _check_conservation(op_id: str, per_rank: Fraction, ranks: int, message_bytes: int):
    """O-CONSERVATION per op: per_rank * r == (r-1)*M exactly, or raise."""
    op_wire = per_rank * ranks
    expected_wire = Fraction((ranks - 1) * message_bytes)
    if op_wire != expected_wire:
        raise AssertionError(
            f"O-CONSERVATION violated for op {op_id}: {op_wire} != {expected_wire}; "
            "this is a model bug, not a tunable parameter"
        )
    return op_wire


def _aggregate(backend_id: str, transport_model: str, model_extra: dict, per_op, times, total_wire):
    count = len(times)
    mean_time = sum(times) / count if count else Fraction(0)
    return {
        "backend_id": backend_id,
        "model": {
            "transport_model": transport_model,
            **model_extra,
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


def execute_ring_phases(ops, infra: l0.InfraConfig) -> dict:
    """Execute ReduceScatter / AllGather ops on the L0 ring fabric.

    O-CONSERVATION (exact): for each op, per-rank traffic summed over ranks
    equals (r-1)*M — every wire byte is sent once and received once. This is
    an algebraic self-check of the model's own accounting, not an
    independent physical check (O6).

    Divisibility (O1, A-L0P-DIV): each op's payload must be divisible by the
    rank count (chunks of M/r; ReduceScatter result M/r stays integral);
    non-divisible payloads are rejected before any identity is evaluated.

    O-CCT (analytical): per-op completion time under the ring phase equation,
    with per-op result bytes (M/r for ReduceScatter, M for AllGather) and
    mean/max aggregates. Workloads compose phases by summing per-op
    completions; RS(M) + AG(M) reproduces the landed ring AllReduce exactly.
    """
    per_op = []
    total_wire = Fraction(0)
    times: list[Fraction] = []

    for op in ops:
        if op.collective not in _PHASE_COLLECTIVES:
            raise ValueError(
                f"{BACKEND_ID} capability: collective {op.collective!r} not supported "
                f"on the ring phase fabric (op {op.op_id})"
            )
        if len(op.comm_ranks) != infra.ranks:
            raise ValueError(
                f"op {op.op_id}: comm group size {len(op.comm_ranks)} != topology ranks {infra.ranks}"
            )
        require_divisible(
            BACKEND_ID, op.op_id, op.payload_bytes, infra.ranks, "A-L0P-DIV"
        )
        per_rank = phase_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = _check_conservation(op.op_id, per_rank, infra.ranks, op.payload_bytes)
        if op.collective == "reducescatter":
            completion = ring_reducescatter_time_ns(op.payload_bytes, infra.ranks, infra)
            result_bytes = reducescatter_result_bytes(op.payload_bytes, infra.ranks)
        else:
            completion = ring_allgather_time_ns(op.payload_bytes, infra.ranks, infra)
            result_bytes = allgather_result_bytes(op.payload_bytes, infra.ranks)
        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "collective": op.collective,
                "algorithm": "ring",
                "payload_bytes": op.payload_bytes,
                "chunk_bytes_exact": str(Fraction(op.payload_bytes, infra.ranks)),
                "hops": infra.ranks - 1,
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "result_bytes_per_rank_exact": str(result_bytes),
                "completion_time_ns_exact": str(completion),
                "completion_time_ns": float(completion),
            }
        )

    return _aggregate(
        BACKEND_ID,
        CAPABILITIES["transport_model"],
        {
            "topology_id": infra.topology_id,
            "ranks": infra.ranks,
            "algorithm_family": "ring",
            "link_bytes_per_ns_exact": str(infra.link_bytes_per_ns),
            "hop_latency_ns_exact": str(infra.hop_latency_ns),
        },
        per_op,
        times,
        total_wire,
    )


def execute_doubling_phases(ops, infra: l0d.RecursiveDoublingConfig) -> dict:
    """Execute ReduceScatter / AllGather ops on the L0 exchange fabric.

    ReduceScatter runs the recursive-halving schedule, AllGather the
    recursive-doubling schedule (step chunks reused from l0d, one partner per
    step). O-CONSERVATION (exact) as in the ring family — an algebraic
    self-check of the model's own accounting, not an independent physical
    check (O6); O-CCT records the per-step (chunk, time) decomposition per
    op. Divisibility (O1, A-L0P-DIV): payloads must be divisible by the rank
    count or the op is rejected. RS(M) + AG(M) reproduces the landed S3
    recursive-doubling AllReduce exactly.
    """
    per_op = []
    total_wire = Fraction(0)
    times: list[Fraction] = []

    for op in ops:
        if op.collective not in _PHASE_COLLECTIVES:
            raise ValueError(
                f"{BACKEND_ID} capability: collective {op.collective!r} not supported "
                f"on the exchange phase fabric (op {op.op_id})"
            )
        if len(op.comm_ranks) != infra.ranks:
            raise ValueError(
                f"op {op.op_id}: comm group size {len(op.comm_ranks)} != topology ranks {infra.ranks}"
            )
        require_divisible(
            BACKEND_ID, op.op_id, op.payload_bytes, infra.ranks, "A-L0P-DIV"
        )
        per_rank = phase_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = _check_conservation(op.op_id, per_rank, infra.ranks, op.payload_bytes)
        steps = []
        if op.collective == "reducescatter":
            chunk_fn = l0d.reduce_step_chunk
            completion = halving_reducescatter_time_ns(op.payload_bytes, infra)
            algorithm = "recursive_halving"
            result_bytes = reducescatter_result_bytes(op.payload_bytes, infra.ranks)
        else:
            chunk_fn = l0d.broadcast_step_chunk
            completion = doubling_allgather_time_ns(op.payload_bytes, infra)
            algorithm = "recursive_doubling"
            result_bytes = allgather_result_bytes(op.payload_bytes, infra.ranks)
        for step in range(1, infra.steps + 1):
            chunk = chunk_fn(op.payload_bytes, step, infra.ranks)
            steps.append(
                {
                    "step": step,
                    "chunk_bytes_exact": str(chunk),
                    "time_ns_exact": str(
                        chunk / infra.injection_bytes_per_ns
                        + infra.pair_latency_ns
                    ),
                }
            )
        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "collective": op.collective,
                "algorithm": algorithm,
                "payload_bytes": op.payload_bytes,
                "steps_log2_ranks": infra.steps,
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "result_bytes_per_rank_exact": str(result_bytes),
                "steps": steps,
                "completion_time_ns_exact": str(completion),
                "completion_time_ns": float(completion),
            }
        )

    return _aggregate(
        BACKEND_ID,
        CAPABILITIES["transport_model"],
        {
            "topology_id": infra.topology_id,
            "ranks": infra.ranks,
            "algorithm_family": "recursive_halving_doubling",
            "steps_log2_ranks": infra.steps,
            "injection_bytes_per_ns_exact": str(infra.injection_bytes_per_ns),
            "pair_latency_ns_exact": str(infra.pair_latency_ns),
        },
        per_op,
        times,
        total_wire,
    )
