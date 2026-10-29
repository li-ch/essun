"""Golden identities for the W5 PD/KV event generator (T031).

Expected values are recomputed independently here (hand-derived counts and
byte sums spelled out, not by calling the implementation under test), per
the handoff rule that golden tests derive from the specified identities.

Identities under test (W5 PD/KV Prefill/Decode, A-W5-PLACE / A-W5-SIZE /
A-W5-LIFE / A-W5-VIS / A-W5-MEM / A-W5-DAG / A-W5-STEP):

    per request q and KV chunk c: alloc(q,c) -> write(q,c) ->
    transfer(q,c) -> visible(q,c) -> [read(q,s,c) for s in 0..S-1] ->
    release(q); the transfer is the ONLY fabric op (prefill node writes the
    chunk into the decode node's memory, memory semantics); reads are
    decode-node-local; control ops move no bytes; requests never depend on
    each other.

Worked cases (derived by hand below, asserted exactly):

A) Tiny case (r=4, P=1, Q=1, C=1, b=1024, S=2): nodes 0 prefill, 1..3
   decode; request 0 prefilled on 0, decoded on 1. 7 ops: alloc, write,
   transfer (0 -> 1, 1024 bytes), visible, read(step 0), read(step 1),
   release; every field of every op spelled out literal-by-literal.

B) Committed smoke YAML (r=8, P=2, Q=3, C=2, b=4096, S=3): nodes 0-1
   prefill, 2-7 decode; placement q0 -> (0, 2), q1 -> (1, 3), q2 -> (0, 4).
   15 ops per request (4C + SC + 1 = 8 + 6 + 1), 45 total. Writes
   Q*C*b = 24576 bytes, transfers Q*C*b = 24576 (the fabric bytes), reads
   Q*S*C*b = 73728; total payload 122880; allocated capacity == released
   capacity == 24576.

LIFECYCLE (the task's acceptance bar): allocation -> transfer ->
visibility -> release ordering is asserted as a DAG REACHABILITY property
(not by emission position), and the property checker is itself proven to
catch edge-removal mutations. HONEST SCOPE, tested as behavior: W5 issues
memory-semantic ops and NO registered backend executes them — the L0
backends raise on the op kind, and the orchestrator's capability gate
rejects a W5 manifest loudly (run-path negatives in
tests/negative/test_dispatch_gates.py). Executing PD/KV traffic needs an
L1/L2 memory-semantics fabric model.
"""

from dataclasses import asdict, replace
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.evidence.store import canonical_json
from essun.workload import w5
from essun.workload.base import DAGCollectiveOp

REPO = Path(__file__).resolve().parents[2]
WORKLOAD_YAML = REPO / "experiments" / "workloads" / "w5_pd_kv_prefill_decode_small.yaml"
TOPO = REPO / "experiments" / "topologies"


def _tiny_config(**overrides):
    # Case A: r=4, P=1, Q=1, C=1, b=1024, S=2.
    params = dict(
        tp_size=4,
        prefill_nodes=1,
        requests=1,
        chunks_per_request=1,
        chunk_bytes=1024,
        decode_steps=2,
    )
    params.update(overrides)
    return w5.W5Config(**params)


def _smoke_config():
    return w5.load_w5_config(WORKLOAD_YAML)


# --- op-count / ordering identity ---------------------------------------------


def test_w5_ops_count_order_and_kinds():
    # 3 requests x (4*2 prefill-phase + 3*2 reads + 1 release) = 45 ops;
    # request-major emission: chunk-major prefill phase (alloc, write,
    # transfer, visible), step-major/chunk-minor reads, then release.
    ops = w5.generate_w5_ops(_smoke_config())
    assert len(ops) == 45
    expected_request0 = [
        "q000000-c000000-kv-alloc",
        "q000000-c000000-kv-write",
        "q000000-c000000-kv-transfer",
        "q000000-c000000-kv-visible",
        "q000000-c000001-kv-alloc",
        "q000000-c000001-kv-write",
        "q000000-c000001-kv-transfer",
        "q000000-c000001-kv-visible",
        "q000000-s000000-c000000-kv-read",
        "q000000-s000000-c000001-kv-read",
        "q000000-s000001-c000000-kv-read",
        "q000000-s000001-c000001-kv-read",
        "q000000-s000002-c000000-kv-read",
        "q000000-s000002-c000001-kv-read",
        "q000000-kv-release",
    ]
    assert [op.op_id for op in ops[:15]] == expected_request0
    # Every request repeats the same pattern with its own prefix.
    for request in range(3):
        block = ops[request * 15 : (request + 1) * 15]
        assert [op.op_id for op in block] == [
            f"q{request:06d}" + op_id[len("q000000") :] for op_id in expected_request0
        ]
        assert [op.request for op in block] == [request] * 15
    assert [op.collective for op in ops[:15]] == [
        "kv_alloc",
        "kv_write",
        "kv_transfer",
        "kv_visible",
        "kv_alloc",
        "kv_write",
        "kv_transfer",
        "kv_visible",
        "kv_read",
        "kv_read",
        "kv_read",
        "kv_read",
        "kv_read",
        "kv_read",
        "kv_release",
    ]
    assert all(isinstance(op, DAGCollectiveOp) for op in ops)


def test_w5_workload_yaml_loads():
    config = _smoke_config()
    assert config == w5.W5Config(
        tp_size=8,
        prefill_nodes=2,
        requests=3,
        chunks_per_request=2,
        chunk_bytes=4096,
        decode_steps=3,
        model_name="pd-kv-prefill-decode-smoke",
    )
    assert len(w5.generate_w5_ops(config)) == 45


# --- A: tiny case, every field of every op hand-derived -------------------------


def test_w5_tiny_ops_hand_derived():
    # Node placement: P=1 (rank 0 prefill), D=3 (ranks 1-3 decode); request
    # 0: prefill 0%1 = 0, decode 1 + 0%3 = 1. Every field literal-by-literal.
    ops = w5.generate_w5_ops(_tiny_config())
    by_id = {op.op_id: op for op in ops}

    def check(op_id, kind, ranks, payload, chunk, step, src, dst, chunk_bytes, deps):
        op = by_id[op_id]
        assert (op.collective, op.comm_ranks, op.payload_bytes) == (kind, ranks, payload)
        assert (op.request, op.chunk, op.step) == (0, chunk, step)
        assert (op.src_node, op.dst_node, op.chunk_bytes) == (src, dst, chunk_bytes)
        assert op.depends_on == deps

    check(
        "q000000-c000000-kv-alloc", "kv_alloc", (0,), 0, 0, None, 0, 0, 1024, ()
    )
    check(
        "q000000-c000000-kv-write",
        "kv_write",
        (0,),
        1024,
        0,
        None,
        0,
        0,
        1024,
        ("q000000-c000000-kv-alloc",),
    )
    check(
        "q000000-c000000-kv-transfer",
        "kv_transfer",
        (0, 1),
        1024,
        0,
        None,
        0,
        1,
        1024,
        ("q000000-c000000-kv-write",),
    )
    check(
        "q000000-c000000-kv-visible",
        "kv_visible",
        (1,),
        0,
        0,
        None,
        1,
        1,
        1024,
        ("q000000-c000000-kv-transfer",),
    )
    check(
        "q000000-s000000-c000000-kv-read",
        "kv_read",
        (1,),
        1024,
        0,
        0,
        1,
        1,
        1024,
        ("q000000-c000000-kv-visible",),
    )
    check(
        "q000000-s000001-c000000-kv-read",
        "kv_read",
        (1,),
        1024,
        0,
        1,
        1,
        1,
        1024,
        ("q000000-s000000-c000000-kv-read",),
    )
    check(
        "q000000-kv-release",
        "kv_release",
        (1,),
        0,
        None,
        None,
        1,
        1,
        1024,  # freed capacity C*b = 1*1024
        ("q000000-s000001-c000000-kv-read",),
    )
    assert list(by_id) == [op.op_id for op in ops]


# --- B: committed smoke YAML, placement and byte sums hand-derived ---------------


def test_w5_placement_hand_derived():
    # A-W5-PLACE: q%2 prefill over ranks {0,1}, 2+q%6 decode over {2..7}:
    # q0 -> (0, 2), q1 -> (1, 3), q2 -> (0, 4). Asserted from the transfer
    # ops (the only cross-node ops) and from every op's endpoints.
    config = _smoke_config()
    ops = w5.generate_w5_ops(config)
    transfers = {op.request: (op.src_node, op.dst_node) for op in ops if op.collective == "kv_transfer"}
    assert transfers == {0: (0, 2), 1: (1, 3), 2: (0, 4)}
    for op in ops:
        if op.collective in ("kv_alloc", "kv_write"):
            assert (op.src_node, op.dst_node) == (op.request % 2, op.request % 2)
        elif op.collective == "kv_transfer":
            src, dst = transfers[op.request]
            assert (op.src_node, op.dst_node) == (src, dst)
            assert op.comm_ranks == (src, dst)
        else:  # kv_visible, kv_read, kv_release: decode-node-local
            assert (op.src_node, op.dst_node) == (2 + op.request % 6, 2 + op.request % 6)


def test_w5_smoke_byte_sums_hand_derived():
    ops = w5.generate_w5_ops(_smoke_config())
    by_kind = {}
    for op in ops:
        by_kind.setdefault(op.collective, []).append(op)
    # Writes: Q*C*b = 3*2*4096 = 24576. Transfers (the FABRIC bytes,
    # A-W5-MEM): the same 24576 — each chunk moves exactly once. Reads:
    # Q*S*C*b = 3*3*2*4096 = 73728. Control ops (15 of them): 0 bytes.
    assert sum(op.payload_bytes for op in by_kind["kv_write"]) == 24576
    assert sum(op.payload_bytes for op in by_kind["kv_transfer"]) == 24576
    assert sum(op.payload_bytes for op in by_kind["kv_read"]) == 73728
    for kind in w5.CONTROL_KINDS:
        assert all(op.payload_bytes == 0 for op in by_kind[kind]), kind
    assert len(by_kind["kv_alloc"]) == len(by_kind["kv_visible"]) == 6
    assert len(by_kind["kv_release"]) == 3
    assert sum(op.payload_bytes for op in ops) == 24576 + 24576 + 73728 == 122880
    # Capacity conservation (algebraic): every allocated byte is released —
    # sum(alloc.chunk_bytes) = Q*C*b = 24576 = sum(release.chunk_bytes),
    # each release freeing C*b = 8192.
    assert sum(op.chunk_bytes for op in by_kind["kv_alloc"]) == 24576
    assert [op.chunk_bytes for op in by_kind["kv_release"]] == [8192, 8192, 8192]


def test_w5_per_op_payload_and_fabric_identity():
    # Per op: payload == chunk_bytes exactly on the byte-moving kinds
    # (write/transfer/read) and 0 on control kinds; ONLY kv_transfer has
    # src != dst (A-W5-MEM: writes/reads are node-local under the
    # KV-migrating identity); every chunk is written once, transferred
    # once, and read S times (the per-chunk conservation identity).
    config = _smoke_config()
    ops = w5.generate_w5_ops(config)
    for op in ops:
        if op.collective in ("kv_write", "kv_transfer", "kv_read"):
            assert op.payload_bytes == op.chunk_bytes == config.chunk_bytes
        else:
            assert op.payload_bytes == 0
        assert (op.src_node != op.dst_node) == (op.collective in w5.FABRIC_KINDS)
    for request in range(config.requests):
        for chunk in range(config.chunks_per_request):
            written = [
                op
                for op in ops
                if op.request == request and op.chunk == chunk and op.collective == "kv_write"
            ]
            transferred = [
                op
                for op in ops
                if op.request == request and op.chunk == chunk and op.collective == "kv_transfer"
            ]
            reads = [
                op
                for op in ops
                if op.request == request and op.chunk == chunk and op.collective == "kv_read"
            ]
            assert len(written) == len(transferred) == 1
            assert len(reads) == config.decode_steps
            assert written[0].payload_bytes == transferred[0].payload_bytes
            assert all(op.payload_bytes == written[0].payload_bytes for op in reads)


# --- dependency semantics (A-W5-LIFE / A-W5-VIS / A-W5-DAG) ---------------------


def test_w5_dependency_semantics_frozen():
    ops = w5.generate_w5_ops(_smoke_config())
    by_id = {op.op_id: op for op in ops}
    # First chunk's alloc has no dependencies; chunk chain: alloc(q, c>0)
    # <- write(q, c-1) (prefill produces the sequence chunk by chunk).
    assert by_id["q000000-c000000-kv-alloc"].depends_on == ()
    assert by_id["q000000-c000001-kv-alloc"].depends_on == ("q000000-c000000-kv-write",)
    # Lifecycle edges: write <- alloc, transfer <- write, visible <- transfer.
    assert by_id["q000000-c000001-kv-write"].depends_on == ("q000000-c000001-kv-alloc",)
    assert by_id["q000000-c000001-kv-transfer"].depends_on == ("q000000-c000001-kv-write",)
    assert by_id["q000000-c000001-kv-visible"].depends_on == ("q000000-c000001-kv-transfer",)
    # A-W5-VIS request gate: the FIRST read depends on visible of ALL
    # chunks — decode starts only after the request's ENTIRE KV is visible.
    assert by_id["q000000-s000000-c000000-kv-read"].depends_on == (
        "q000000-c000000-kv-visible",
        "q000000-c000001-kv-visible",
    )
    # Serialized per-request read chain: chunk-minor within a step,
    # step-major across steps.
    assert by_id["q000000-s000000-c000001-kv-read"].depends_on == (
        "q000000-s000000-c000000-kv-read",
    )
    assert by_id["q000000-s000001-c000000-kv-read"].depends_on == (
        "q000000-s000000-c000001-kv-read",
    )
    assert by_id["q000000-s000002-c000000-kv-read"].depends_on == (
        "q000000-s000001-c000001-kv-read",
    )
    # Release <- the read chain's tail (transitively every read).
    assert by_id["q000000-kv-release"].depends_on == ("q000000-s000002-c000001-kv-read",)


# --- lifecycle: allocation -> transfer -> visibility -> release as a DAG property


def _ancestors(ops):
    """op_id -> set of all transitive dependency ids (reachability)."""
    deps = {op.op_id: tuple(op.depends_on) for op in ops}
    memo: dict[str, set[str]] = {}

    def walk(op_id: str) -> set[str]:
        if op_id in memo:
            return memo[op_id]
        memo[op_id] = set()  # cycle guard; acyclicity is proven by Kahn below
        acc: set[str] = set()
        for dep in deps[op_id]:
            acc.add(dep)
            acc |= walk(dep)
        memo[op_id] = acc
        return acc

    return {op.op_id: walk(op.op_id) for op in ops}


def _lifecycle_violations(ops, config):
    """The task's acceptance property, checked by DAG REACHABILITY (not
    emission position): for every (q, c), alloc -> write -> transfer ->
    visible in stage order, every read of the chunk after visible, and
    release after the chunk's last read."""
    anc = _ancestors(ops)
    violations = []
    for request in range(config.requests):
        for chunk in range(config.chunks_per_request):
            prefix = f"q{request:06d}-c{chunk:06d}"
            stages = [f"{prefix}-kv-alloc", f"{prefix}-kv-write", f"{prefix}-kv-transfer", f"{prefix}-kv-visible"]
            for before, after in zip(stages, stages[1:]):
                if before not in anc[after]:
                    violations.append(f"{after} does not follow {before}")
            for step in range(config.decode_steps):
                read = f"q{request:06d}-s{step:06d}-c{chunk:06d}-kv-read"
                if read not in anc:
                    violations.append(f"missing read op {read}")
                elif stages[-1] not in anc[read]:
                    violations.append(f"read before visible: {read}")
            last_read = f"q{request:06d}-s{config.decode_steps - 1:06d}-c{chunk:06d}-kv-read"
            release = f"q{request:06d}-kv-release"
            if release not in anc or last_read not in anc[release]:
                violations.append(f"{release} does not follow last read {last_read}")
    return violations


def test_w5_lifecycle_order_is_a_dag_property():
    # The acceptance bar: allocation -> transfer (via write) -> visibility
    # -> release holds as DEPENDENCY REACHABILITY for every (q, c).
    config = _smoke_config()
    ops = w5.generate_w5_ops(config)
    assert _lifecycle_violations(ops, config) == []
    # Same property on the tiny case.
    tiny = _tiny_config()
    assert _lifecycle_violations(w5.generate_w5_ops(tiny), tiny) == []


def test_w5_lifecycle_checker_catches_edge_mutations():
    # The property checker must have teeth: removing any lifecycle edge is
    # reported, proving the property is the DAG's, not the emitter's.
    config = _smoke_config()
    ops = w5.generate_w5_ops(config)

    def mutate(op_id, **changes):
        return [replace(op, **changes) if op.op_id == op_id else op for op in ops]

    # (a) read before visible: first read loses its full-visibility gate.
    broken = mutate("q000000-s000000-c000000-kv-read", depends_on=())
    assert any("read before visible" in v for v in _lifecycle_violations(broken, config))
    # (b) release before the last read: release loses its tail dependency.
    broken = mutate("q000000-kv-release", depends_on=())
    assert any("does not follow last read" in v for v in _lifecycle_violations(broken, config))
    # (c) transfer before write: transfer loses its write dependency
    # (allocation/write no longer reach transfer).
    broken = mutate("q000000-c000000-kv-transfer", depends_on=())
    assert any("does not follow" in v for v in _lifecycle_violations(broken, config))


def test_w5_requests_are_independent():
    # A-W5-DAG: no op of request q depends on any op of another request —
    # requests never depend on each other (concurrent serving is the
    # executor's business, T032 scope).
    ops = w5.generate_w5_ops(_smoke_config())
    by_id = {op.op_id: op for op in ops}
    for op in ops:
        for dep in op.depends_on:
            assert by_id[dep].request == op.request, (op.op_id, dep)


def test_w5_dependency_dag_is_a_dag():
    # No cycles (Kahn), every dependency resolves, dependencies only point
    # backwards in emission order; with the deterministic smallest-index
    # tie-break the walk must reproduce the frozen emission order (it is a
    # topological order of the DAG).
    ops = w5.generate_w5_ops(_smoke_config())
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
        assert ready, "dependency cycle detected in W5 op DAG"
        take = min(ready, key=index.__getitem__)
        consumed.append(take)
        pending.remove(take)
    assert consumed == [op.op_id for op in ops]


# --- determinism ----------------------------------------------------------------


def test_w5_generation_deterministic_canonical_json():
    # Two generations from independently constructed equal configs must be
    # byte-identical under canonical JSON (handoff determinism rules). The
    # placement and lifecycle construction use no RNG anywhere.
    first = w5.generate_w5_ops(_smoke_config())
    second = w5.generate_w5_ops(
        w5.W5Config(
            tp_size=8,
            prefill_nodes=2,
            requests=3,
            chunks_per_request=2,
            chunk_bytes=4096,
            decode_steps=3,
        )
    )
    a = canonical_json([asdict(op) for op in first])
    b = canonical_json([asdict(op) for op in second])
    assert a == b
    assert a == canonical_json([asdict(op) for op in w5.generate_w5_ops(_smoke_config())])


# --- negative: degenerate configs rejected ---------------------------------------


def test_w5_degenerate_config_rejected():
    base = dict(
        tp_size=8,
        prefill_nodes=2,
        requests=3,
        chunks_per_request=2,
        chunk_bytes=4096,
        decode_steps=3,
    )
    for bad in (
        dict(tp_size=0),
        dict(prefill_nodes=0),  # no prefill node
        dict(prefill_nodes=8),  # P == r: no decode node left
        dict(prefill_nodes=9),  # P > r
        dict(requests=0),
        dict(chunks_per_request=0),
        dict(chunk_bytes=0),
        dict(decode_steps=0),
    ):
        try:
            w5.generate_w5_ops(w5.W5Config(**{**base, **bad}))
        except ValueError as exc:
            assert "degenerate" in str(exc), f"{bad}: {exc}"
        else:
            raise AssertionError(f"expected ValueError for degenerate config {bad}")


def test_w5_loader_rejects_wrong_kind_degenerate_and_ambiguous_layers(tmp_path):
    wrong = tmp_path / "wrong_kind.yaml"
    wrong.write_text("workload: w1_dense_tp_decode\ntp_size: 8\n", encoding="utf-8")
    try:
        w5.load_w5_config(wrong)
    except ValueError as exc:
        assert "expected workload kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for wrong workload kind")

    degenerate = tmp_path / "degenerate.yaml"
    degenerate.write_text(
        "workload: w5_pd_kv_prefill_decode\ntp_size: 8\nprefill_nodes: 2\n"
        "requests: 0\nchunks_per_request: 2\nchunk_bytes: 4096\ndecode_steps: 3\n",
        encoding="utf-8",
    )
    try:
        w5.load_w5_config(degenerate)
    except ValueError as exc:
        assert "degenerate" in str(exc)
    else:
        raise AssertionError("expected ValueError for degenerate YAML")

    # 'layers' is ambiguous on a W5 document (W5's positional structure is
    # requests/chunks/steps) — rejected loudly, never silently ignored.
    ambiguous = tmp_path / "ambiguous.yaml"
    ambiguous.write_text(
        "workload: w5_pd_kv_prefill_decode\ntp_size: 8\nlayers: 2\nprefill_nodes: 2\n"
        "requests: 3\nchunks_per_request: 2\nchunk_bytes: 4096\ndecode_steps: 3\n",
        encoding="utf-8",
    )
    try:
        w5.load_w5_config(ambiguous)
    except ValueError as exc:
        assert "layers" in str(exc)
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("expected ValueError for ambiguous layers key")


# --- capability gates: L0 cannot run memory-semantic KV ops — tested behavior ----


def test_w5_ops_rejected_by_base_l0_allreduce_backend():
    # The landed L0 ring adapter executes AllReduce only; feeding it W5's
    # memory-semantic ops must raise the explicit capability error.
    ops = w5.generate_w5_ops(_tiny_config())
    infra = l0.load_infra(
        yaml.safe_load((TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8"))
    )
    try:
        l0.execute(ops, infra)
    except ValueError as exc:
        assert "not supported" in str(exc)
        assert "kv_alloc" in str(exc)  # first op in emission order
    else:
        raise AssertionError("expected ValueError for KV ops on base L0")


def test_w5_ops_rejected_by_phase_collectives_backend():
    # ReduceScatter/AllGather phases do not cover memory-semantic KV ops
    # either.
    ops = w5.generate_w5_ops(_tiny_config())
    infra = l0.load_infra(
        yaml.safe_load((TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8"))
    )
    try:
        l0p.execute_ring_phases(ops, infra)
    except ValueError as exc:
        assert "not supported" in str(exc)
        assert "kv_" in str(exc)
    else:
        raise AssertionError("expected ValueError for KV ops on phase backend")


def test_no_registered_backend_declares_kv_memory_ops():
    # HONEST SCOPE, pinned structurally: no registered backend (five L0
    # models, both Docker-pinned adapters) declares any W5 op kind, so W5
    # manifests cannot run anywhere in the CURRENT set — executing PD/KV
    # traffic needs an L1/L2 memory-semantics fabric model. If a future
    # backend declares a kv_* kind, this pin forces revisiting the W5
    # scope note.
    from essun.orchestrator import runs as orch

    for backend_id, module in sorted(orch.BACKENDS.items()):
        declared = {
            name.rsplit("_", 1)[0] for name in module.CAPABILITIES["collectives"]
        }
        for kind in w5.OP_KINDS:
            assert kind not in declared, (backend_id, kind)
