"""Golden identities for the W3 MoE dispatch/combine generator (T030).

Expected values are recomputed independently here (hand-derived counts and
byte sums spelled out, not by calling the implementation under test), per
the handoff rule that golden tests derive from the specified identities.

Identities under test (W3 MoE Dispatch/Combine, A-W3-ROUTE / A-W3-SHARES /
A-W3-SIZE / A-W3-A2A / A-W3-LOCAL / A-W3-DAG):

    per layer l: one dispatch all-to-all then one combine all-to-all over
    the full group; every expert visit carries token_bytes b in BOTH
    phases; combine is dispatch's exact mirror (transposed pair matrix).

Worked cases (derived by hand below, asserted exactly):

A) Tiny uniform case (r=4, layers=1, E=4, k=2, t=1, b=8, shares (1,1,1,1),
   placement round-robin e%4): apportioned visits (2,2,2,2); greedy fill
   (rank-major, token-minor, largest-remaining-first, ties by expert id)
   routes rank0 -> (0,1), rank1 -> (2,3), rank2 -> (0,1), rank3 -> (2,3).
   Dispatch pair matrix rows (src -> dst = expert host, diagonal = local):
   (8,8,0,0)/(0,0,8,8)/(8,8,0,0)/(0,0,8,8); send = recv = (16,16,16,16);
   payload 64. Combine is the transpose (8,0,8,0)/(8,0,8,0)/(0,8,0,8)/
   (0,8,0,8) with the same totals.

B) Committed smoke YAML (r=8, layers=2, E=4, k=2, t=5, b=2048): N = 80
   visits per layer. Layer 0 uniform shares (1,1,1,1) -> visits
   (20,20,20,20) (80/4 each, exact). Layer 1 skew shares (2,1,1,1) ->
   quotas 80*2/5 = 32 and 80/5 = 16 each (exact) -> visits (32,16,16,16):
   expert 0 takes a 2/5 configurable share. Every rank's dispatch send is
   t*k*b = 5*2*2048 = 20480 (origin-side uniform by construction); dispatch
   recv lands on ranks 0-3 (round-robin placement): layer 0
   (40960,40960,40960,40960,0,0,0,0), layer 1 (65536,32768,32768,32768,
   0,0,0,0). Every op's payload = N*b = 163840; workload total 4*163840 =
   655360. Combines mirror (send <-> recv, transposed pair matrix).

HONEST SCOPE, tested as behavior: W3 issues all-to-all ops and NO
registered backend executes all-to-all — the L0 backends raise on the
collective, and the orchestrator's collective capability gate rejects a W3
manifest loudly (run-path negative in tests/negative/test_dispatch_gates.py).
Executing MoE dispatch/combine traffic needs an L1/L2 backend.
"""

from dataclasses import asdict
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.evidence.store import canonical_json
from essun.workload import w3
from essun.workload.base import DAGCollectiveOp

REPO = Path(__file__).resolve().parents[2]
WORKLOAD_YAML = REPO / "experiments" / "workloads" / "w3_moe_dispatch_combine_small.yaml"
TOPO = REPO / "experiments" / "topologies"


def _tiny_config(**overrides):
    # Case A: r=4, 1 layer, E=4, k=2, t=1, b=8, uniform shares.
    params = dict(
        tp_size=4,
        layers=1,
        experts_per_layer=4,
        top_k=2,
        tokens_per_rank=1,
        token_bytes=8,
        expert_shares=((1, 1, 1, 1),),
    )
    params.update(overrides)
    return w3.W3Config(**params)


def _smoke_config():
    return w3.load_w3_config(WORKLOAD_YAML)


# --- op-count / ordering identity ---------------------------------------------


def test_w3_ops_count_order_and_phases():
    # 2 layers x (dispatch, combine) = 4 ops; layer-major, dispatch before
    # combine (frozen emission order); the collective TYPE is all-to-all for
    # both phases — dispatch/combine are MoE phase names on the same
    # collective (A-W3-A2A).
    ops = w3.generate_w3_ops(_smoke_config())
    assert len(ops) == 4
    assert [op.op_id for op in ops] == [
        "l000000-dispatch",
        "l000000-combine",
        "l000001-dispatch",
        "l000001-combine",
    ]
    assert all(op.collective == "alltoall" for op in ops)
    assert [op.phase for op in ops] == ["dispatch", "combine"] * 2
    assert [op.layer for op in ops] == [0, 0, 1, 1]
    assert all(op.comm_ranks == tuple(range(8)) for op in ops)
    assert all(isinstance(op, DAGCollectiveOp) for op in ops)


def test_w3_workload_yaml_loads():
    config = _smoke_config()
    assert config == w3.W3Config(
        tp_size=8,
        layers=2,
        experts_per_layer=4,
        top_k=2,
        tokens_per_rank=5,
        token_bytes=2048,
        routing="shares",
        expert_shares=((1, 1, 1, 1), (2, 1, 1, 1)),
        expert_placement=None,
        routing_table=None,
        model_name="moe-dispatch-combine-smoke",
    )
    assert len(w3.generate_w3_ops(config)) == 4


# --- A: tiny case, every byte hand-derived -------------------------------------


def test_w3_tiny_routing_table_hand_derived():
    # Greedy fill of shares (1,1,1,1): rank0 -> (0,1) (all budgets 2, ties
    # by index), rank1 -> (2,3) (budgets 1,1,2,2), rank2 -> (0,1)
    # (1,1,1,1 ties), rank3 -> (2,3).
    table = w3.build_routing_table(_tiny_config())
    assert table == ((((0, 1),), ((2, 3),), ((0, 1),), ((2, 3),)),)


def test_w3_tiny_dispatch_pair_matrix_hand_derived():
    ops = w3.generate_w3_ops(_tiny_config())
    dispatch, combine = ops
    # src rows -> expert-host columns (placement e%4): rank0's token visits
    # expert0 (host 0, diagonal) and expert1 (host 1): row (8,8,0,0); etc.
    assert dispatch.per_pair_bytes == (
        (8, 8, 0, 0),
        (0, 0, 8, 8),
        (8, 8, 0, 0),
        (0, 0, 8, 8),
    )
    assert dispatch.per_rank_send_bytes == (16, 16, 16, 16)
    assert dispatch.per_rank_recv_bytes == (16, 16, 16, 16)
    assert dispatch.payload_bytes == 64
    # Combine is the exact mirror: transposed pair matrix, swapped per-rank
    # send/recv (here symmetric in totals, not in the matrix).
    assert combine.per_pair_bytes == (
        (8, 0, 8, 0),
        (8, 0, 8, 0),
        (0, 8, 0, 8),
        (0, 8, 0, 8),
    )
    assert combine.per_rank_send_bytes == dispatch.per_rank_recv_bytes
    assert combine.per_rank_recv_bytes == dispatch.per_rank_send_bytes
    assert combine.payload_bytes == 64


def test_w3_explicit_table_mode_matches_shares_construction():
    # The same tiny case routed by an EXPLICIT routing table must produce
    # byte-identical ops to the shares-mode construction (A-W3-ROUTE: the
    # table is the input either way).
    table_config = _tiny_config(
        routing="table",
        expert_shares=None,
        routing_table=((((0, 1),), ((2, 3),), ((0, 1),), ((2, 3),)),),
    )
    from_shares = w3.generate_w3_ops(_tiny_config())
    from_table = w3.generate_w3_ops(table_config)
    assert canonical_json([asdict(op) for op in from_shares]) == canonical_json(
        [asdict(op) for op in from_table]
    )


# --- B: committed smoke YAML, counts and byte sums hand-derived -----------------


def test_w3_apportionment_and_skew_share_hand_derived():
    # Largest-remainder apportionment over N = 8*5*2 = 80 visits:
    # uniform (1,1,1,1): 80/4 = 20 each (exact); skew (2,1,1,1):
    # 80*2/5 = 32, 80/5 = 16 (exact) — expert 0 takes a 2/5 share.
    assert w3.apportion_expert_visits((1, 1, 1, 1), 80) == (20, 20, 20, 20)
    assert w3.apportion_expert_visits((2, 1, 1, 1), 80) == (32, 16, 16, 16)
    config = _smoke_config()
    assert w3.expert_visit_counts(config, 0) == (20, 20, 20, 20)
    assert w3.expert_visit_counts(config, 1) == (32, 16, 16, 16)


def test_w3_smoke_per_rank_byte_sums_hand_derived():
    ops = w3.generate_w3_ops(_smoke_config())
    by_id = {op.op_id: op for op in ops}
    # Origin-side send is uniform by construction: t*k*b = 5*2*2048 = 20480.
    uniform_send = (20480,) * 8
    # Round-robin placement (e%8) puts experts 0..3 on ranks 0..3.
    assert by_id["l000000-dispatch"].per_rank_send_bytes == uniform_send
    assert by_id["l000000-dispatch"].per_rank_recv_bytes == (
        40960,
        40960,
        40960,
        40960,
        0,
        0,
        0,
        0,
    )  # 20 visits x 2048 on each of ranks 0..3
    assert by_id["l000001-dispatch"].per_rank_send_bytes == uniform_send
    assert by_id["l000001-dispatch"].per_rank_recv_bytes == (
        65536,
        32768,
        32768,
        32768,
        0,
        0,
        0,
        0,
    )  # (32,16,16,16) visits x 2048
    # Each op moves N*b = 80*2048 = 163840 bytes; workload total 4*163840.
    for op in ops:
        assert op.payload_bytes == 163840
    assert sum(op.payload_bytes for op in ops) == 655360
    # Combines mirror dispatch exactly (A-W3-A2A).
    for layer in (0, 1):
        dispatch = by_id[f"l{layer:06d}-dispatch"]
        combine = by_id[f"l{layer:06d}-combine"]
        assert combine.per_rank_send_bytes == dispatch.per_rank_recv_bytes
        assert combine.per_rank_recv_bytes == dispatch.per_rank_send_bytes
        assert combine.per_pair_bytes == tuple(
            tuple(dispatch.per_pair_bytes[src][dst] for src in range(8))
            for dst in range(8)
        )


def test_w3_per_op_byte_conservation_identity():
    # Per op: sum(send) == sum(recv) == payload_bytes, and the pair matrix
    # row sums are the per-rank sends while column sums are the recvs
    # (every byte is sent once and received once — the logical W3
    # counterpart of O-CONSERVATION, an algebraic property of the
    # generator's own accounting, not a physical measurement).
    for op in w3.generate_w3_ops(_smoke_config()):
        assert sum(op.per_rank_send_bytes) == op.payload_bytes
        assert sum(op.per_rank_recv_bytes) == op.payload_bytes
        rows = tuple(sum(row) for row in op.per_pair_bytes)
        cols = tuple(
            sum(op.per_pair_bytes[src][dst] for src in range(8)) for dst in range(8)
        )
        assert rows == op.per_rank_send_bytes
        assert cols == op.per_rank_recv_bytes


# --- dependency DAG (A-W3-DAG) -------------------------------------------------


def test_w3_dependency_semantics_frozen():
    # Chain: combine(l) <- dispatch(l); dispatch(l+1) <- combine(l); the
    # first op has no dependencies. Serialized MoE layer chain.
    ops = w3.generate_w3_ops(_smoke_config())
    by_id = {op.op_id: op for op in ops}
    assert by_id["l000000-dispatch"].depends_on == ()
    assert by_id["l000000-combine"].depends_on == ("l000000-dispatch",)
    assert by_id["l000001-dispatch"].depends_on == ("l000000-combine",)
    assert by_id["l000001-combine"].depends_on == ("l000001-dispatch",)


def test_w3_dependency_dag_is_a_dag():
    # No cycles (Kahn), every dependency resolves, dependencies only point
    # backwards in emission order; with the deterministic smallest-index
    # tie-break the walk must reproduce the frozen emission order (it is a
    # topological order of the chain).
    ops = w3.generate_w3_ops(_smoke_config())
    index = {op.op_id: i for i, op in enumerate(ops)}
    for op in ops:
        for dep in op.depends_on:
            assert dep in index, f"unresolved dependency {dep}"
            assert index[dep] < index[op.op_id], f"forward edge {dep} -> {op.op_id}"
    remaining = {op.op_id: set(op.depends_on) for op in ops}
    pending = [op.op_id for op in ops]
    consumed: list[str] = []
    while pending:
        ready = [i for i in pending if not (remaining[i] - set(consumed))]
        assert ready, "dependency cycle detected in W3 op DAG"
        take = min(ready, key=index.__getitem__)
        consumed.append(take)
        pending.remove(take)
    assert consumed == [op.op_id for op in ops]


# --- determinism ----------------------------------------------------------------


def test_w3_generation_deterministic_canonical_json():
    # Two generations from independently constructed equal configs must be
    # byte-identical under canonical JSON (handoff determinism rules). The
    # routing construction uses no RNG anywhere (A-W3-ROUTE).
    first = w3.generate_w3_ops(_smoke_config())
    second = w3.generate_w3_ops(
        w3.W3Config(
            tp_size=8,
            layers=2,
            experts_per_layer=4,
            top_k=2,
            tokens_per_rank=5,
            token_bytes=2048,
            routing="shares",
            expert_shares=((1, 1, 1, 1), (2, 1, 1, 1)),
        )
    )
    a = canonical_json([asdict(op) for op in first])
    b = canonical_json([asdict(op) for op in second])
    assert a == b
    assert a == canonical_json([asdict(op) for op in w3.generate_w3_ops(_smoke_config())])


# --- negative: degenerate configs rejected ---------------------------------------


def test_w3_degenerate_config_rejected():
    base = dict(
        tp_size=4,
        layers=1,
        experts_per_layer=4,
        top_k=2,
        tokens_per_rank=1,
        token_bytes=8,
    )
    for bad in (
        dict(tp_size=0),
        dict(layers=0),
        dict(experts_per_layer=0),
        dict(top_k=0),
        dict(tokens_per_rank=0),
        dict(token_bytes=0),
        dict(top_k=5),  # top_k > experts_per_layer: distinctness impossible
        dict(routing="learned"),  # not a deterministic routing input mode
    ):
        try:
            w3.generate_w3_ops(_tiny_config(**{**base, **bad}))
        except ValueError as exc:
            assert "degenerate" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for degenerate config {bad}")


def test_w3_degenerate_shares_placement_and_table_rejected():
    for bad in (
        # shares shape violations
        dict(expert_shares=((1, 1, 1),)),  # wrong row width
        dict(expert_shares=((1, 1, 1, 1), (1, 1, 1, 1))),  # wrong layer count
        dict(expert_shares=((1, 1, 1, -1),)),  # negative weight
        dict(expert_shares=((0, 0, 0, 0),)),  # all-zero layer
        # placement violations
        dict(expert_placement=(0, 1, 2)),  # wrong length
        dict(expert_placement=(0, 1, 2, 4)),  # rank 4 outside [0, 4)
        # routing mode ambiguity
        dict(routing="table"),  # table mode without a table
        dict(
            routing="table",
            routing_table=((((0, 1),), ((2, 3),), ((0, 1),), ((2, 3),)),),
            expert_shares=((1, 1, 1, 1),),
        ),
        # table content violations
        dict(routing="table", routing_table=(((0, 1),),)),  # wrong rank count
        dict(
            routing="table",
            routing_table=(((0,), ((2, 3),), ((0, 1),), ((2, 3),)),),
        ),  # rank 0 route shorter than top_k
        dict(
            routing="table",
            routing_table=((((0, 1, 2),), ((2, 3),), ((0, 1),), ((2, 3),)),),
        ),  # route longer than top_k
        dict(
            routing="table",
            routing_table=((((0, 0),), ((2, 3),), ((0, 1),), ((2, 3),)),),
        ),  # repeated expert in one token's route
        dict(
            routing="table",
            routing_table=((((0, 4),), ((2, 3),), ((0, 1),), ((2, 3),)),),
        ),  # expert 4 outside [0, 4)
    ):
        try:
            w3.generate_w3_ops(_tiny_config(**bad))
        except ValueError as exc:
            assert "degenerate" in str(exc), f"{bad}: {exc}"
        else:
            raise AssertionError(f"expected ValueError for degenerate config {bad}")


def test_w3_infeasible_shares_rejected():
    # (9,1) over r=2, t=1, k=2 -> N=4 visits apportioned (4,0): expert 0
    # needs 4 visits but only 2 tokens exist and each visits an expert at
    # most once — rejected loudly, never silently re-balanced.
    config = _tiny_config(tp_size=2, experts_per_layer=2, expert_shares=((9, 1),))
    try:
        w3.generate_w3_ops(config)
    except ValueError as exc:
        assert "infeasible" in str(exc)
        assert "at most once" in str(exc)
    else:
        raise AssertionError("expected ValueError for infeasible shares")
    # The feasible control with the same shape still generates.
    assert len(
        w3.generate_w3_ops(_tiny_config(tp_size=2, experts_per_layer=2, expert_shares=((1, 1),)))
    ) == 2


def test_w3_loader_rejects_wrong_kind_and_degenerate(tmp_path):
    wrong = tmp_path / "wrong_kind.yaml"
    wrong.write_text("workload: w1_dense_tp_decode\ntp_size: 8\n", encoding="utf-8")
    try:
        w3.load_w3_config(wrong)
    except ValueError as exc:
        assert "expected workload kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for wrong workload kind")
    degenerate = tmp_path / "degenerate.yaml"
    degenerate.write_text(
        "workload: w3_moe_dispatch_combine\ntp_size: 8\nlayers: 2\n"
        "experts_per_layer: 4\ntop_k: 2\ntokens_per_rank: 0\ntoken_bytes: 2048\n",
        encoding="utf-8",
    )
    try:
        w3.load_w3_config(degenerate)
    except ValueError as exc:
        assert "degenerate" in str(exc)
    else:
        raise AssertionError("expected ValueError for degenerate YAML")


# --- capability gates: L0 cannot run all-to-all — tested behavior -----------------


def test_w3_ops_rejected_by_base_l0_allreduce_backend():
    # The landed L0 ring adapter executes AllReduce only; feeding it W3's
    # all-to-all ops must raise the explicit capability error.
    ops = w3.generate_w3_ops(
        _tiny_config(tp_size=8, experts_per_layer=8, expert_shares=None)
    )
    infra = l0.load_infra(
        yaml.safe_load((TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8"))
    )
    try:
        l0.execute(ops, infra)
    except ValueError as exc:
        assert "not supported" in str(exc)
        assert "alltoall" in str(exc)
    else:
        raise AssertionError("expected ValueError for all-to-all on base L0")


def test_w3_ops_rejected_by_phase_collectives_backend():
    # ReduceScatter/AllGather phases do not cover all-to-all either.
    ops = w3.generate_w3_ops(
        _tiny_config(tp_size=8, experts_per_layer=8, expert_shares=None)
    )
    infra = l0.load_infra(
        yaml.safe_load((TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8"))
    )
    try:
        l0p.execute_ring_phases(ops, infra)
    except ValueError as exc:
        assert "not supported" in str(exc)
        assert "alltoall" in str(exc)
    else:
        raise AssertionError("expected ValueError for all-to-all on phase backend")


def test_no_registered_backend_declares_alltoall():
    # HONEST SCOPE, pinned structurally: no registered backend (five L0
    # models, both Docker-pinned adapters) declares an all-to-all
    # collective, so W3 manifests cannot run anywhere in the CURRENT set —
    # executing MoE traffic needs an L1/L2 backend. If a future backend
    # declares alltoall, this pin forces revisiting the W3 scope note.
    from essun.orchestrator import runs as orch

    for backend_id, module in sorted(orch.BACKENDS.items()):
        declared = {
            name.rsplit("_", 1)[0] for name in module.CAPABILITIES["collectives"]
        }
        assert "alltoall" not in declared, backend_id
