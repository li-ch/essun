"""Analytical L0.5 ring AllReduce: per-chunk serialization term and per-hop
latency charged per chunk transfer.

Sources: second-pair-of-eyes re-derivation observations O3 (no
compute/serialization term) and O4 (coarse 2*(r-1)*L latency granularity),
recorded during the 2026-10-26 assumption review; the review routed O3/O4
into "a future L0.5 model" instead of silently widening the landed
identities. This module is that model. The landed L0
family (l0.py and siblings) is untouched and stays the convergence anchor.

Identity. Same fabric and chunked schedule as the landed ring models — a
unidirectional ring, AllReduce = ReduceScatter + AllGather (serialized
phases), each phase (r-1) chunk transfers of c = M/r bytes, each chunk
transfer crossing exactly one ring hop (the landed equal-chunk construction,
Thakur-Rabenseifner direct pipelined ring). L0.5 charges each chunk transfer
an explicit service time with THREE terms — serialize the chunk at the
transmitting NIC, occupy the link, one per-hop latency per transfer:

    chunk size         c = M / r                    [c integral: r | M]
    one transfer       s = c/I + c/B + L            [one hop]
    one phase             t_phase(M, r) = (r-1) * s
    AllReduce (2 phases)  t_L05(M, r)   = 2 * (r-1) * (c/I + c/B + L)

Expanded against the landed L0 ring identity t_L0 = 2*(r-1)/r*M/B + 2*(r-1)*L:

    t_L05(M, r) = t_L0(M, r) + 2*(r-1)/r * M / I

Convergence (the point of the model, pinned by tests as an EXACT identity,
not an approximation): the disagreement with L0 is exactly the serialization
term 2*(r-1)*c/I for every finite injection rate I, and vanishes as I ->
infinity. ``injection_bytes_per_ns = None`` encodes that limit (the term is
exactly 0), where t_L05 == l0.ring_allreduce_time_ns == the landed golden
literals, and phase times == the landed l0_phase_collectives ring identities.

Construction reading (why (r-1)*s is the textbook pipelined form): run the
phase in r-1 lockstep slots of duration s per transmitting NIC — every rank
puts one chunk on its outgoing link per slot, a chunk received in slot k is
forwarded in slot k+1 (store-and-forward), and the long-distance-first
schedule has every chunk finish its journey in slot r-1, so the phase
completes at (r-1)*s. At I -> infinity the slot collapses to the landed
reading c/B + L and the identity reduces to L0 exactly; L0's "coarse"
2*(r-1)*L is thereby made explicit as one L per chunk transfer per phase.

Wire traffic is UNCHANGED from the landed identity — serialization moves no
bytes: per rank 2*(r-1)/r*M, total 2*(r-1)*M per op, so O-CONSERVATION is
the same ALGEBRAIC SELF-CHECK of the model's own byte accounting as in L0
(O6 honesty label: not an independent physical measurement).

Every numeric parameter is FREE — not standard-derived, not measured
(provenance rules) — registered in
experiments/vertical_slice/assumptions_l0.yaml:

    I  nic.injection_bytes_per_ns  (A-L05-INJ; None encodes the I->inf limit)
    B  link.bytes_per_ns           (A-L05-BW; same value as the L0 ring so
                                    the convergence anchor is shared)
    L  link.hop_latency_ns         (A-L05-LAT; same value as the L0 ring)

The chunk size c = M/r is NOT an independent free parameter (A-L05-CHUNK):
it is the landed equal-chunk construction, so divisibility r | M is required
and non-divisible payloads are rejected at execution time via
:func:`essun.backends.analytical.l0.require_divisible` (A-L05-DIV) — the
same gate as every L0 family member.

Explicitly different identities, declared unsupported below and not
evaluated here: relay re-serialization beyond one serialization per
transmitting NIC per transfer, transfer-to-transfer overlap (steady-state
fill+drain forms), free pipelining depth (chunk size != M/r changes the
(r-1)*L chain), per-element compute/reduce terms (F1's pre-registered scope
is the serialization rate plus latency granularity only), and the shared L0
exclusions (congestion, credits, packetization/FLIT effects, in-network
computing, overlapping collectives, standard-specific semantics).

Deliberately NOT registered in orchestrator/runs.py DISPATCH: this module
lands the model, its identities and its convergence tests; run-path/golden
integration is a separate capability-gated step.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from essun.backends.analytical import l0
from essun.backends.analytical.l0 import require_divisible

BACKEND_ID = "analytical_l05"

# Distinct from the landed "unidirectional_ring" so no landed backend can
# silently load an L0.5 topology (l0.load_infra would ignore the nic term);
# the L0.5 loader checks the class explicitly.
TOPOLOGY_CLASS = "unidirectional_ring_with_serialization"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0.5",
    "collectives": ("allreduce_ring",),
    "transport_model": "serialized_pipelined_ring",
    "observables": ("O-CONSERVATION", "O-CCT"),
    "explicitly_unsupported": (
        # Shared L0 exclusions (all backends).
        "congestion",
        "credit_flow_control",
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "standard_specific_semantics",
        # L0.5-specific (A-L05-SER / A-L05-CHUNK).
        "relay_re_serialization",
        "overlapped_chunk_transfers",
        "free_pipelining_depth",
        "compute_reduce_terms",
    ),
}


@dataclass(frozen=True)
class L05Config:
    topology_id: str
    ranks: int  # r >= 2
    link_bytes_per_ns: Fraction  # B: per-direction link bandwidth (free)
    hop_latency_ns: Fraction  # L: per-hop latency (free)
    # I: per-chunk serialization (injection) rate (free); None encodes the
    # I -> infinity limit — serialization term exactly 0 — which is the
    # convergence anchor to the landed L0 identity.
    injection_bytes_per_ns: Fraction | None


def load_l05_config(data: dict) -> L05Config:
    """Load and validate an L0.5 topology/config YAML.

    Schema: experiments/topologies/ring8_l05_free_params.yaml. The loader
    refuses wrong topology classes, degenerate ranks, non-positive bandwidth
    or latency, and non-positive injection rates explicitly (mirroring the
    family loaders' explicit-refusal rule); ``nic.injection_bytes_per_ns``
    absent or null loads as None, the no-serialization limit.
    """

    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    topology_class = data.get("topology_class")
    if topology_class != TOPOLOGY_CLASS:
        raise ValueError(
            f"{BACKEND_ID}: topology_class {topology_class!r} is not "
            f"{TOPOLOGY_CLASS!r}; the L0.5 serialization identity is declared "
            "for the serialized ring only — undeclared pairings are different "
            "identities and are explicitly unsupported"
        )
    ranks = int(data["ranks"])
    if ranks < 2:
        raise ValueError(f"{BACKEND_ID}: ring topology needs ranks >= 2, got {ranks}")
    link = data["link"]
    link_bw = frac(link["bytes_per_ns"])
    hop_lat = frac(link["hop_latency_ns"])
    if link_bw <= 0:
        raise ValueError(f"{BACKEND_ID}: link bytes_per_ns must be > 0, got {link_bw}")
    if hop_lat < 0:
        raise ValueError(f"{BACKEND_ID}: link hop_latency_ns must be >= 0, got {hop_lat}")
    raw_injection = data.get("nic", {}).get("injection_bytes_per_ns")
    injection = None if raw_injection is None else frac(raw_injection)
    if injection is not None and injection <= 0:
        raise ValueError(
            f"{BACKEND_ID}: nic injection_bytes_per_ns must be > 0 (or null "
            f"for the no-serialization limit), got {injection}"
        )
    return L05Config(
        topology_id=str(data["topology_id"]),
        ranks=ranks,
        link_bytes_per_ns=link_bw,
        hop_latency_ns=hop_lat,
        injection_bytes_per_ns=injection,
    )


# ---------------------------------------------------------------------------
# Identity (exact Fraction arithmetic throughout)
# ---------------------------------------------------------------------------


def chunk_bytes(message_bytes: int, ranks: int) -> Fraction:
    """c = M/r — the landed equal-chunk construction (A-L05-CHUNK)."""
    return Fraction(message_bytes, ranks)


def chunk_serialization_ns(
    chunk: Fraction, injection_bytes_per_ns: Fraction | None
) -> Fraction:
    """Serialization term c/I of one chunk transfer; exactly 0 at I -> inf.

    ``injection_bytes_per_ns=None`` is that limit by definition — this
    function is where the convergence to the landed L0 identity happens.
    """
    if injection_bytes_per_ns is None:
        return Fraction(0)
    return chunk / injection_bytes_per_ns


def chunk_transfer_time_ns(chunk: Fraction, config: L05Config) -> Fraction:
    """One chunk transfer (one ring hop): s = c/I + c/B + L."""
    return (
        chunk_serialization_ns(chunk, config.injection_bytes_per_ns)
        + chunk / config.link_bytes_per_ns
        + config.hop_latency_ns
    )


def phase_time_ns(message_bytes: int, ranks: int, config: L05Config) -> Fraction:
    """t_phase = (r-1) * (c/I + c/B + L) — the pipelined-ring phase identity.

    At the injection limit this equals the landed l0_phase_collectives ring
    phase identity (r-1)/r*M/B + (r-1)*L exactly (pinned by tests).
    """
    chunk = chunk_bytes(message_bytes, ranks)
    return (ranks - 1) * chunk_transfer_time_ns(chunk, config)


def allreduce_time_ns(message_bytes: int, ranks: int, config: L05Config) -> Fraction:
    """t_L05 = 2 * t_phase — serialized ReduceScatter + AllGather phases.

    Equals the landed l0.ring_allreduce_time_ns PLUS exactly
    2*(r-1)/r*M/I (see :func:`serialization_term_ns`); at the injection
    limit the two identities coincide exactly.
    """
    return 2 * phase_time_ns(message_bytes, ranks, config)


def serialization_term_ns(message_bytes: int, ranks: int, config: L05Config) -> Fraction:
    """The exact L0-vs-L0.5 disagreement: 2*(r-1)/r * M / I.

    Zero at the injection limit; positive for every finite I. This closed
    form is re-checked against the evaluated times inside :func:`execute`
    (an algebraic self-check: a mismatch is a model bug, never a parameter).
    """
    chunk = chunk_bytes(message_bytes, ranks)
    return 2 * (ranks - 1) * chunk_serialization_ns(
        chunk, config.injection_bytes_per_ns
    )


def _l0_anchor_config(config: L05Config) -> l0.InfraConfig:
    """The landed L0 ring fabric with the SAME B and L (shared parameters)."""
    return l0.InfraConfig(
        topology_id=config.topology_id,
        ranks=config.ranks,
        link_bytes_per_ns=config.link_bytes_per_ns,
        hop_latency_ns=config.hop_latency_ns,
    )


# ---------------------------------------------------------------------------
# Execution with observables
# ---------------------------------------------------------------------------


def execute(ops, config: L05Config) -> dict:
    """Execute AllReduce ops on the L0.5 ring model and emit observations.

    O-CONSERVATION (exact): wire bytes are IDENTICAL to the landed L0 ring
    identity — serialization moves no bytes — so per op, per-rank traffic
    summed over ranks equals 2*(r-1)*M. Checked by exact Fraction equality;
    any violation raises. As in L0 this is an ALGEBRAIC SELF-CHECK of the
    model's own accounting, not an independent physical check (O6).

    Divisibility (O1, A-L05-DIV): each op's payload must be divisible by the
    rank count (chunks of M/r); non-divisible payloads are rejected before
    any identity is evaluated.

    O-CCT (analytical): per-op completion time under the L0.5 identity, with
    the per-transfer decomposition (serialization / wire / hop latency), the
    landed-L0 anchor time at the SAME B and L, and the exact disagreement
    term — re-checked per op against the closed form
    2*(r-1)/r*M/I (a mismatch is a model bug, not a tunable parameter).
    """
    per_op = []
    total_wire = Fraction(0)
    times: list[Fraction] = []

    for op in ops:
        if op.collective != "allreduce":
            raise ValueError(
                f"{BACKEND_ID} capability: collective {op.collective!r} not supported (op {op.op_id})"
            )
        if len(op.comm_ranks) != config.ranks:
            raise ValueError(
                f"op {op.op_id}: comm group size {len(op.comm_ranks)} != topology ranks {config.ranks}"
            )
        require_divisible(
            BACKEND_ID, op.op_id, op.payload_bytes, config.ranks, "A-L05-DIV"
        )

        # Wire traffic: unchanged from the landed L0 identity.
        per_rank = l0.ring_traffic_per_rank(op.payload_bytes, config.ranks)
        op_wire = per_rank * config.ranks  # == 2*(r-1)*M exactly
        expected_wire = Fraction(2 * (config.ranks - 1) * op.payload_bytes)
        if op_wire != expected_wire:
            raise AssertionError(
                f"O-CONSERVATION violated for op {op.op_id}: {op_wire} != "
                f"{expected_wire}; this is a model bug, not a tunable parameter"
            )

        chunk = chunk_bytes(op.payload_bytes, config.ranks)
        completion = allreduce_time_ns(op.payload_bytes, config.ranks, config)
        anchor = l0.ring_allreduce_time_ns(
            op.payload_bytes, config.ranks, _l0_anchor_config(config)
        )
        term = serialization_term_ns(op.payload_bytes, config.ranks, config)
        if completion - anchor != term:
            raise AssertionError(
                f"convergence identity violated for op {op.op_id}: "
                f"t_L05 - t_L0 = {completion - anchor} != serialization term "
                f"{term}; this is a model bug, not a tunable parameter"
            )

        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "payload_bytes": op.payload_bytes,
                "chunk_bytes_exact": str(chunk),
                "transfers_per_phase": config.ranks - 1,
                "phases": 2,
                "per_transfer": {
                    "serialization_ns_exact": str(
                        chunk_serialization_ns(chunk, config.injection_bytes_per_ns)
                    ),
                    "wire_ns_exact": str(chunk / config.link_bytes_per_ns),
                    "hop_latency_ns_exact": str(config.hop_latency_ns),
                },
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "completion_time_ns_exact": str(completion),
                "completion_time_ns": float(completion),
                "l0_anchor_time_ns_exact": str(anchor),
                "serialization_term_ns_exact": str(term),
            }
        )

    count = len(times)
    mean_time = sum(times) / count if count else Fraction(0)
    return {
        "backend_id": BACKEND_ID,
        "model": {
            "transport_model": CAPABILITIES["transport_model"],
            "topology_id": config.topology_id,
            "ranks": config.ranks,
            "link_bytes_per_ns_exact": str(config.link_bytes_per_ns),
            "hop_latency_ns_exact": str(config.hop_latency_ns),
            "injection_bytes_per_ns_exact": (
                None
                if config.injection_bytes_per_ns is None
                else str(config.injection_bytes_per_ns)
            ),
            "at_injection_limit": config.injection_bytes_per_ns is None,
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
