"""W3 MoE Dispatch/Combine workload generator.

Mixture-of-Experts layers replace the dense TP AllReduce with a
dispatch/combine pair: every rank holds ``tokens_per_rank`` activation
tokens; a router sends each token to its ``top_k`` experts (hosted on ranks
per the expert-placement table); experts compute; results return. Both
phases are realized as ONE all-to-all collective over the full group per
layer — the pattern the scale-up fabric actually carries in MoE inference.

Routing is INPUT, never learned and never random (assumption A-W3-ROUTE in
experiments/vertical_slice/assumptions_w3.yaml):

- ``routing="shares"`` (default): the per-layer integer expert-shares
  MATRIX — the free-parameter skew input — is apportioned over the
  N = ranks * tokens_per_rank * top_k expert-visits by exact-Fraction
  largest-remainder (:func:`apportion_expert_visits`), and the routing
  table is filled greedily (largest remaining budget first, ties by
  smallest expert id) in rank-major, token-minor order
  (:func:`_fill_routing_from_shares`). No RNG anywhere; skew is a
  parameter, not a stochastic outcome. An infeasible shares matrix (an
  expert apportioned more visits than there are tokens, or a fill that
  runs out of distinct experts for a token) is rejected loudly.
- ``routing="table"``: the fully explicit deterministic routing table
  (layer, rank, token) -> top_k distinct experts is validated and used
  as-is.

Byte semantics (frozen, A-W3-SIZE / A-W3-A2A / A-W3-LOCAL): one expert
visit carries ``token_bytes`` in dispatch and the same ``token_bytes`` back
in combine (equal in/out widths; asymmetric phase widths are a different
identity and are not generated). Each phase emits ONE all-to-all op whose
``payload_bytes`` is the phase's total bytes moved across the group
(integer); the per-rank and per-pair accounting rides the op as
``per_rank_send_bytes`` / ``per_rank_recv_bytes`` / ``per_pair_bytes[src][dst]``.
Visits to experts co-located with the origin token are recorded on the
``per_pair`` diagonal and included in these LOGICAL totals; whether
co-located bytes consume fabric bandwidth is an executor (L1/L2) modeling
decision, deliberately not decided here. Combine is the exact mirror of
dispatch: same totals, transposed pair matrix.

Dependency semantics (frozen, A-W3-DAG, the W3 analogue of W2's A-W2-DAG):
combine(l) depends on dispatch(l) — experts consume the dispatched
activations before results return; dispatch(l+1) depends on combine(l) —
the next layer's input is the previous layer's combined output. The DAG is
therefore a chain in the fixed emission order (layer-major, dispatch
before combine), which is a topological order of it. Overlapped
dispatch/combine or pipelined multi-batch schedules are different
identities and are not generated.

HONEST SCOPE (A-W3-SCOPE note in the assumptions registry): W3 issues
all-to-all ops, and NO registered backend executes all-to-all — the L0
family declares only allreduce/reducescatter/allgather, and both
Docker-pinned adapters translate W1 only. A W3 manifest is therefore
REJECTED loudly by the orchestrator's collective capability gate (that
rejection is itself a tested behavior, tests/golden/test_w3_moe_golden.py
and tests/negative/test_dispatch_gates.py). Executing MoE dispatch/combine
traffic requires an L1 (flow/collective) or L2 (packet/FLIT) backend; the
generator and its exact integer byte identities are testable without one.

Sizes are deterministic model parameters, not random draws; integer byte
counts only. The experiment seed is still recorded by the orchestrator for
every run so future stochastic extensions must use partitioned RNG streams
(determinism rules).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from essun.workload.base import DAGCollectiveOp

WORKLOAD_KIND = "w3_moe_dispatch_combine"

ROUTING_MODES = ("shares", "table")
PHASES = ("dispatch", "combine")


@dataclass(frozen=True)
class W3CollectiveOp(DAGCollectiveOp):
    """One W3 MoE collective op: the dispatch or combine all-to-all of ``layer``.

    ``payload_bytes`` is the phase's total bytes moved across the group
    (sum of all per-pair entries, integer). ``per_pair_bytes[src][dst]``
    is rank ``src``'s bytes to rank ``dst`` under that phase: dst is the
    expert-hosting rank in dispatch and the token-origin rank in combine
    (combine's matrix is dispatch's transpose). Co-located visits sit on
    the diagonal (A-W3-LOCAL).
    """

    phase: str
    per_rank_send_bytes: tuple[int, ...]
    per_rank_recv_bytes: tuple[int, ...]
    per_pair_bytes: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class W3Config:
    tp_size: int
    layers: int
    experts_per_layer: int
    top_k: int
    tokens_per_rank: int
    token_bytes: int
    routing: str = "shares"
    # A-W3-SHARES: per-layer integer weight matrix (layers x experts). The
    # free-parameter SKEW input; None means uniform (all-ones) routing.
    expert_shares: tuple[tuple[int, ...], ...] | None = None
    # A-W3-PLACE: expert -> rank placement table (length experts_per_layer);
    # None means deterministic round-robin expert % tp_size.
    expert_placement: tuple[int, ...] | None = None
    # A-W3-ROUTE explicit-table mode: (layer, rank, token) -> top_k distinct
    # expert ids. Required when routing == "table"; rejected otherwise.
    routing_table: tuple[tuple[tuple[tuple[int, ...], ...], ...], ...] | None = None
    model_name: str = "w3-smoke"


def _validate_w3_config(config: W3Config) -> None:
    """Degenerate-shape rejection (feasibility of shares is checked at fill)."""
    positive = (
        config.tp_size,
        config.layers,
        config.experts_per_layer,
        config.top_k,
        config.tokens_per_rank,
        config.token_bytes,
    )
    if min(positive) < 1:
        raise ValueError(f"degenerate W3 configuration: {config}")
    if config.top_k > config.experts_per_layer:
        raise ValueError(
            f"degenerate W3 configuration: top_k {config.top_k} exceeds "
            f"experts_per_layer {config.experts_per_layer} (a token's experts "
            "must be distinct)"
        )
    if config.routing not in ROUTING_MODES:
        raise ValueError(
            f"degenerate W3 configuration: routing {config.routing!r} not in "
            f"{list(ROUTING_MODES)}"
        )
    if config.routing == "table" and config.routing_table is None:
        raise ValueError(
            "degenerate W3 configuration: routing='table' requires routing_table"
        )
    if config.routing == "shares" and config.routing_table is not None:
        raise ValueError(
            "degenerate W3 configuration: routing_table given alongside "
            "routing='shares' — ambiguous routing input, use routing='table'"
        )
    if config.routing == "table" and config.expert_shares is not None:
        raise ValueError(
            "degenerate W3 configuration: expert_shares given alongside "
            "routing='table' — ambiguous routing input, the explicit table "
            "is the only routing input in table mode"
        )
    if config.expert_shares is not None:
        if len(config.expert_shares) != config.layers:
            raise ValueError(
                f"degenerate W3 configuration: expert_shares has "
                f"{len(config.expert_shares)} rows, expected {config.layers} "
                "(one per layer)"
            )
        for layer, row in enumerate(config.expert_shares):
            if len(row) != config.experts_per_layer:
                raise ValueError(
                    f"degenerate W3 configuration: expert_shares layer {layer} "
                    f"has {len(row)} weights, expected {config.experts_per_layer}"
                )
            if any(weight < 0 for weight in row):
                raise ValueError(
                    f"degenerate W3 configuration: negative expert_shares "
                    f"weight in layer {layer}"
                )
            if sum(row) == 0:
                raise ValueError(
                    f"degenerate W3 configuration: expert_shares layer {layer} "
                    "sums to zero (no routing weight to apportion)"
                )
    if config.expert_placement is not None:
        if len(config.expert_placement) != config.experts_per_layer:
            raise ValueError(
                f"degenerate W3 configuration: expert_placement has "
                f"{len(config.expert_placement)} entries, expected "
                f"{config.experts_per_layer}"
            )
        for expert, rank in enumerate(config.expert_placement):
            if not 0 <= rank < config.tp_size:
                raise ValueError(
                    f"degenerate W3 configuration: expert {expert} placed on "
                    f"rank {rank}, outside [0, {config.tp_size})"
                )
    if config.routing_table is not None:
        _validate_routing_table(config)


def _validate_routing_table(config: W3Config) -> None:
    table = config.routing_table
    assert table is not None  # narrowed by the caller
    if len(table) != config.layers:
        raise ValueError(
            f"degenerate W3 configuration: routing_table has {len(table)} "
            f"layers, expected {config.layers}"
        )
    for layer, per_rank in enumerate(table):
        if len(per_rank) != config.tp_size:
            raise ValueError(
                f"degenerate W3 configuration: routing_table layer {layer} "
                f"covers {len(per_rank)} ranks, expected {config.tp_size}"
            )
        for rank, per_token in enumerate(per_rank):
            if len(per_token) != config.tokens_per_rank:
                raise ValueError(
                    f"degenerate W3 configuration: routing_table layer "
                    f"{layer} rank {rank} has {len(per_token)} tokens, "
                    f"expected {config.tokens_per_rank}"
                )
            for token, route in enumerate(per_token):
                if len(route) != config.top_k:
                    raise ValueError(
                        f"degenerate W3 configuration: routing_table layer "
                        f"{layer} rank {rank} token {token} routes to "
                        f"{len(route)} experts, expected top_k "
                        f"{config.top_k}"
                    )
                if len(set(route)) != len(route):
                    raise ValueError(
                        f"degenerate W3 configuration: routing_table layer "
                        f"{layer} rank {rank} token {token} repeats an "
                        "expert (top-k experts must be distinct)"
                    )
                for expert in route:
                    if not 0 <= expert < config.experts_per_layer:
                        raise ValueError(
                            f"degenerate W3 configuration: routing_table layer "
                            f"{layer} rank {rank} token {token} names expert "
                            f"{expert}, outside [0, {config.experts_per_layer})"
                        )


def load_w3_config(path: Path) -> W3Config:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data.get("workload") != WORKLOAD_KIND:
        raise ValueError(
            f"expected workload kind {WORKLOAD_KIND!r}, got {data.get('workload')!r} in {path}"
        )
    config = W3Config(
        tp_size=int(data["tp_size"]),
        layers=int(data["layers"]),
        experts_per_layer=int(data["experts_per_layer"]),
        top_k=int(data["top_k"]),
        tokens_per_rank=int(data["tokens_per_rank"]),
        token_bytes=int(data["token_bytes"]),
        routing=str(data.get("routing", "shares")),
        expert_shares=(
            tuple(tuple(int(weight) for weight in row) for row in data["expert_shares"])
            if data.get("expert_shares") is not None
            else None
        ),
        expert_placement=(
            tuple(int(rank) for rank in data["expert_placement"])
            if data.get("expert_placement") is not None
            else None
        ),
        routing_table=(
            tuple(
                tuple(
                    tuple(tuple(int(expert) for expert in route) for route in per_token)
                    for per_token in per_rank
                )
                for per_rank in data["routing_table"]
            )
            if data.get("routing_table") is not None
            else None
        ),
        model_name=str(data.get("model_name", "w3-smoke")),
    )
    _validate_w3_config(config)
    return config


def apportion_expert_visits(
    weights: tuple[int, ...], total_visits: int
) -> tuple[int, ...]:
    """Largest-remainder apportionment of ``total_visits`` among experts.

    Exact :class:`fractions.Fraction` quotas; leftover seats go to the
    largest remainders, ties broken by smallest expert index. Deterministic
    and integer-only by construction (A-W3-ROUTE).
    """
    total_weight = sum(weights)
    quotas = [Fraction(total_visits * weight, total_weight) for weight in weights]
    counts = [quota.numerator // quota.denominator for quota in quotas]
    leftover = total_visits - sum(counts)
    by_remainder = sorted(
        range(len(weights)),
        key=lambda expert: (-(quotas[expert] - counts[expert]), expert),
    )
    for expert in by_remainder[:leftover]:
        counts[expert] += 1
    return tuple(counts)


def _fill_routing_from_shares(
    shares: tuple[int, ...], ranks: int, tokens_per_rank: int, top_k: int, layer: int
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Greedy deterministic fill of one layer's routing table from shares.

    Visits are apportioned per expert, then tokens (rank-major,
    token-minor) each pick the ``top_k`` experts with the largest
    remaining budget, ties by smallest expert id. Infeasible inputs are
    rejected loudly, never silently re-balanced.
    """
    tokens_total = ranks * tokens_per_rank
    visits = apportion_expert_visits(shares, tokens_total * top_k)
    for expert, count in enumerate(visits):
        if count > tokens_total:
            raise ValueError(
                f"W3 shares matrix infeasible at layer {layer}: expert "
                f"{expert} weight {shares[expert]} apportions {count} visits "
                f"but only {tokens_total} tokens exist and each token visits "
                "an expert at most once (top-k distinctness); use a smaller "
                "share or more tokens"
            )
    budget = list(visits)
    per_rank: list[tuple[tuple[int, ...], ...]] = []
    for rank in range(ranks):
        per_token: list[tuple[int, ...]] = []
        for token in range(tokens_per_rank):
            available = [expert for expert in range(len(shares)) if budget[expert] > 0]
            if len(available) < top_k:
                raise ValueError(
                    f"W3 shares matrix infeasible at layer {layer}: token "
                    f"{token} of rank {rank} needs {top_k} distinct experts "
                    f"but only {len(available)} have routing budget left "
                    f"({dict(enumerate(budget))}); the share profile cannot "
                    "honor top-k distinctness"
                )
            picked = sorted(available, key=lambda expert: (-budget[expert], expert))[
                :top_k
            ]
            for expert in picked:
                budget[expert] -= 1
            per_token.append(tuple(picked))
        per_rank.append(tuple(per_token))
    if any(budget):
        raise AssertionError(
            f"W3 routing fill left unspent budget {budget} at layer {layer}; "
            "this is a generator bug, not a tunable parameter"
        )
    return tuple(per_rank)


def build_routing_table(config: W3Config) -> tuple[tuple[tuple[tuple[int, ...], ...], ...], ...]:
    """Return the deterministic routing table: [layer][rank][token] -> top_k experts.

    ``routing="table"`` validates and returns the explicit input;
    ``routing="shares"`` constructs it from the skew matrix
    (A-W3-ROUTE). Pure function of the config — no RNG, no clock.
    """
    _validate_w3_config(config)
    if config.routing == "table":
        return config.routing_table  # type: ignore[return-value]  # validated above
    shares = config.expert_shares or tuple(
        (1,) * config.experts_per_layer for _ in range(config.layers)
    )
    return tuple(
        _fill_routing_from_shares(
            row, config.tp_size, config.tokens_per_rank, config.top_k, layer
        )
        for layer, row in enumerate(shares)
    )


def expert_visit_counts(config: W3Config, layer: int) -> tuple[int, ...]:
    """Per-expert visit counts of ``layer`` under the frozen routing input.

    The skew observable: under ``routing="shares"`` this is exactly the
    apportionment of the shares matrix (A-W3-SHARES); under
    ``routing="table"`` it is the table's column sums.
    """
    table = build_routing_table(config)
    counts = [0] * config.experts_per_layer
    for per_rank in table[layer]:
        for route in per_rank:
            for expert in route:
                counts[expert] += 1
    return tuple(counts)


def _phase_accounting(
    table_layer, placement: tuple[int, ...], ranks: int, token_bytes: int
) -> tuple[list[list[int]], tuple[int, ...], tuple[int, ...]]:
    """Dispatch-phase (src=origin, dst=expert host) byte accounting."""
    pair = [[0] * ranks for _ in range(ranks)]
    for src, per_token in enumerate(table_layer):
        for route in per_token:
            for expert in route:
                pair[src][placement[expert]] += token_bytes
    send = tuple(sum(row) for row in pair)
    recv = tuple(sum(pair[src][dst] for src in range(ranks)) for dst in range(ranks))
    return pair, send, recv


def generate_w3_ops(config: W3Config) -> list[W3CollectiveOp]:
    """Emit dispatch/combine all-to-all ops in a fixed, replayable order.

    Layer-major, dispatch before combine per layer. ``depends_on`` encodes
    the frozen A-W3-DAG chain (combine(l) <- dispatch(l);
    dispatch(l+1) <- combine(l)); see the module docstring.
    """
    _validate_w3_config(config)
    ranks = config.tp_size
    placement = config.expert_placement or tuple(
        expert % ranks for expert in range(config.experts_per_layer)
    )
    table = build_routing_table(config)
    group = tuple(range(ranks))
    ops: list[W3CollectiveOp] = []
    previous_combine: str | None = None
    for layer in range(config.layers):
        pair, send, recv = _phase_accounting(
            table[layer], placement, ranks, config.token_bytes
        )
        dispatch_id = f"l{layer:06d}-dispatch"
        combine_id = f"l{layer:06d}-combine"
        ops.append(
            W3CollectiveOp(
                op_id=dispatch_id,
                collective="alltoall",
                comm_ranks=group,
                payload_bytes=sum(send),
                layer=layer,
                depends_on=() if previous_combine is None else (previous_combine,),
                phase="dispatch",
                per_rank_send_bytes=send,
                per_rank_recv_bytes=recv,
                per_pair_bytes=tuple(tuple(row) for row in pair),
            )
        )
        ops.append(
            W3CollectiveOp(
                op_id=combine_id,
                collective="alltoall",
                comm_ranks=group,
                payload_bytes=sum(send),
                layer=layer,
                depends_on=(dispatch_id,),
                phase="combine",
                per_rank_send_bytes=recv,  # mirror: experts ship results back
                per_rank_recv_bytes=send,
                per_pair_bytes=tuple(
                    tuple(pair[src][dst] for src in range(ranks)) for dst in range(ranks)
                ),
            )
        )
        previous_combine = combine_id
    return ops
