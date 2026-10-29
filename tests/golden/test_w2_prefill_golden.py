"""Golden identities for the W2 generator and its L0 execution (P5 / G5).

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the handoff
rule that golden tests derive from the specified identities.

Identities under test (W2 Dense TP Prefill, A-W2-DAG / A-W2-CHUNK):

    per chunk c in layer k: ReduceScatter(M) then AllGather(M), M = chunk_bytes;
    ring family phase (fabric ring8: B=64, L=200, r=8):
        t = 7/8*M/64 + 7*200 ; wire/rank 7/8*M ; op wire 7*M ; RS result M/8, AG result M.

Worked cases (derived by hand below, asserted as exact Fractions):

A) M=16384 (16 KiB, A-W2-CHUNK): phase wire 14336; t = 14336/64 + 1400
   = 224 + 1400 = 1624; op wire 8*14336 = 114688 = 7*16384; RS result
   2048; AG result 16384. Chunk pair RS+AG = 3248 = ring AllReduce(16384)
   independently derived: 2*7/8*16384/64 + 2*7*200 = 448 + 2800.
B) M=1048576 (1 MiB): phase wire 917504; t = 14336 + 1400 = 15736; op wire
   7340032. Doubling family (rdoubling8: k=3): halving chunks 524288 /
   262144 / 131072 -> steps 8392 / 4296 / 2248 -> 14936; AG mirrored
   14936; pair = 29872 = 2*7/8*1048576/64 + 6*200 = 28672 + 1200.
C) Workload totals (layers=2, chunks=2, tp=8): 8 ops, conservation total
   8*114688 = 917504; serialized critical path along the A-W2-DAG chain
   4*3248 = 12992.
"""

from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.backends.analytical import l0_recursive_doubling as l0d
from essun.evidence.store import canonical_json
from essun.workload import w2
from essun.workload.base import DAGCollectiveOp

RANKS = 8
REPO = Path(__file__).resolve().parents[2]
WORKLOAD_YAML = REPO / "experiments" / "workloads" / "w2_dense_tp_prefill_small.yaml"
_TOPO = REPO / "experiments" / "topologies"

# 16 KiB and 1 MiB are the W2 acceptance chunk sizes (A-W2-CHUNK range).
SIZES = [16384, 1048576]


def _ring_infra():
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )


def _config(tp_size=RANKS, layers=2, chunks=2, chunk_bytes=16384):
    return w2.W2Config(
        tp_size=tp_size,
        layers=layers,
        chunks_per_layer=chunks,
        chunk_bytes=chunk_bytes,
    )


# --- op-count / ordering identity ---------------------------------------------


def test_w2_ops_count_order_and_sizes():
    # 2 layers x 3 chunks x 2 phases = 12 ops; layer-major, chunk-minor,
    # ReduceScatter before AllGather within each chunk (frozen order).
    ops = w2.generate_w2_ops(_config(layers=2, chunks=3))
    assert len(ops) == 12
    expected_ids = [
        f"l{layer:06d}-c{chunk:06d}-{phase}"
        for layer in range(2)
        for chunk in range(3)
        for phase in ("reducescatter", "allgather")
    ]
    assert [op.op_id for op in ops] == expected_ids
    assert [op.collective for op in ops] == ["reducescatter", "allgather"] * 6
    assert all(op.comm_ranks == tuple(range(RANKS)) for op in ops)
    assert all(op.payload_bytes == 16384 for op in ops)
    assert [(op.layer, op.chunk) for op in ops] == [
        (layer, chunk)
        for layer in range(2)
        for chunk in range(3)
        for _ in range(2)
    ]
    assert all(isinstance(op, DAGCollectiveOp) for op in ops)


def test_w2_identity_16kib_and_1mib_chunks():
    # Every phase of every chunk carries the full chunk size M.
    for size in SIZES:
        ops = w2.generate_w2_ops(_config(chunk_bytes=size))
        assert len(ops) == 8
        assert all(op.payload_bytes == size for op in ops)


def test_w2_workload_yaml_loads():
    config = w2.load_w2_config(WORKLOAD_YAML)
    assert config == w2.W2Config(
        tp_size=8,
        layers=2,
        chunks_per_layer=2,
        chunk_bytes=16384,
        model_name="dense-tp-prefill-smoke",
    )
    ops = w2.generate_w2_ops(config)
    assert len(ops) == 8


# --- dependency DAG (A-W2-DAG) -------------------------------------------------


def test_w2_dependency_semantics_frozen():
    # Phase pair: AG(k,c) depends on RS(k,c) only. Chunk chain: RS(k,c>0)
    # depends on AG(k,c-1). Layer chain: RS(k>0,0) depends on the previous
    # layer's final AG. The first op has no dependencies.
    ops = w2.generate_w2_ops(_config(layers=3, chunks=2))
    by_id = {op.op_id: op for op in ops}
    assert by_id["l000000-c000000-reducescatter"].depends_on == ()
    for layer in range(3):
        for chunk in range(2):
            ag = by_id[f"l{layer:06d}-c{chunk:06d}-allgather"]
            assert ag.depends_on == (f"l{layer:06d}-c{chunk:06d}-reducescatter",)
            rs = by_id[f"l{layer:06d}-c{chunk:06d}-reducescatter"]
            if chunk > 0:
                assert rs.depends_on == (f"l{layer:06d}-c{chunk - 1:06d}-allgather",)
            elif layer > 0:
                assert rs.depends_on == (f"l{layer - 1:06d}-c000001-allgather",)
            else:
                assert rs.depends_on == ()


def test_w2_dependency_dag_is_a_dag():
    # No cycles (Kahn), every dependency resolves, dependencies only point
    # backwards in emission order, and layer k ops depend only on layer k
    # or layer k-1 ops (never a later layer, never further back).
    ops = w2.generate_w2_ops(_config(layers=3, chunks=2))
    index = {op.op_id: i for i, op in enumerate(ops)}
    layers = {op.op_id: op.layer for op in ops}
    for op in ops:
        for dep in op.depends_on:
            assert dep in index, f"unresolved dependency {dep}"
            assert index[dep] < index[op.op_id], f"forward edge {dep} -> {op.op_id}"
            assert op.layer - layers[dep] in (0, 1), (
                f"layer-crossing edge {dep} (layer {layers[dep]}) -> {op.op_id} "
                f"(layer {op.layer})"
            )
    # Kahn's algorithm must consume every node exactly once -> acyclic; with
    # the deterministic smallest-emission-index tie-break the walk must
    # reproduce the frozen emission order exactly (it is a topological order).
    remaining = {op.op_id: set(op.depends_on) for op in ops}
    pending = [op.op_id for op in ops]
    consumed: list[str] = []
    while pending:
        ready = [i for i in pending if not (remaining[i] - set(consumed))]
        assert ready, "dependency cycle detected in W2 op DAG"
        take = min(ready, key=index.__getitem__)
        consumed.append(take)
        pending.remove(take)
    assert len(consumed) == len(ops)
    assert consumed == [op.op_id for op in ops]


# --- determinism ----------------------------------------------------------------


def test_w2_generation_deterministic_canonical_json():
    # Two generations from independently constructed equal configs must be
    # byte-identical under canonical JSON (handoff determinism rules).
    first = w2.generate_w2_ops(_config(layers=3, chunks=2))
    second = w2.generate_w2_ops(
        w2.W2Config(tp_size=RANKS, layers=3, chunks_per_layer=2, chunk_bytes=16384)
    )
    a = canonical_json([asdict(op) for op in first])
    b = canonical_json([asdict(op) for op in second])
    assert a == b
    assert a == canonical_json([asdict(op) for op in w2.generate_w2_ops(_config(layers=3, chunks=2))])


# --- negative: degenerate config rejected ----------------------------------------


def test_w2_degenerate_config_rejected():
    for bad in (
        dict(tp_size=0),
        dict(layers=0),
        dict(chunks=0),
        dict(chunk_bytes=0),
        dict(tp_size=-1),
    ):
        try:
            w2.generate_w2_ops(_config(**bad))
        except ValueError as exc:
            assert "degenerate" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for degenerate config {bad}")


def test_w2_loader_rejects_wrong_kind_and_degenerate(tmp_path):
    wrong = tmp_path / "wrong_kind.yaml"
    wrong.write_text("workload: w1_dense_tp_decode\ntp_size: 8\n", encoding="utf-8")
    try:
        w2.load_w2_config(wrong)
    except ValueError as exc:
        assert "expected workload kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for wrong workload kind")
    degenerate = tmp_path / "degenerate.yaml"
    degenerate.write_text(
        "workload: w2_dense_tp_prefill\ntp_size: 8\nlayers: 2\n"
        "chunks_per_layer: 0\nchunk_bytes: 16384\n",
        encoding="utf-8",
    )
    try:
        w2.load_w2_config(degenerate)
    except ValueError as exc:
        assert "degenerate" in str(exc)
    else:
        raise AssertionError("expected ValueError for degenerate YAML")


# --- capability gate: base L0 ring AllReduce backend refuses phase ops -----------


def test_w2_ops_rejected_by_base_l0_allreduce_backend():
    # The landed L0 ring adapter executes AllReduce only; feeding it W2's
    # ReduceScatter/AllGather ops must raise the explicit capability error.
    ops = w2.generate_w2_ops(_config())
    try:
        l0.execute(ops, _ring_infra())
    except ValueError as exc:
        assert "not supported" in str(exc)
        assert "reducescatter" in str(exc)
    else:
        raise AssertionError("expected ValueError for phase collective on base L0")


# --- golden execution through L0 (S4 phase collectives, landed) -------------------


def test_w2_golden_execution_ring_family_16kib():
    # A/C: 8 ops on the committed ring fabric; every phase 1624 ns, op wire
    # 114688, conservation total 8*114688 = 917504; each chunk pair composes
    # the ring AllReduce 3248 (independently derived below); the serialized
    # critical path along the A-W2-DAG chain is 4*3248 = 12992.
    data = yaml.safe_load((_TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8"))
    infra = l0.load_infra(data)
    result = l0p.execute_ring_phases(w2.generate_w2_ops(_config()), infra)
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 8
    assert conservation["violations"] == 0
    assert conservation["total_wire_bytes_exact"] == str(Fraction(8 * 114688))
    for op in result["per_op"]:
        assert op["algorithm"] == "ring"
        assert op["per_rank_wire_bytes_exact"] == str(Fraction(14336))
        assert op["total_wire_bytes_exact"] == str(Fraction(114688))
        assert op["completion_time_ns_exact"] == str(Fraction(1624))
        if op["collective"] == "reducescatter":
            assert op["result_bytes_per_rank_exact"] == str(Fraction(2048))
        else:
            assert op["collective"] == "allgather"
            assert op["result_bytes_per_rank_exact"] == str(Fraction(16384))
    # Independent derivation of the phase and composition identities:
    # t_phase = 7/8*16384/64 + 7*200 = 224 + 1400; AllReduce = 448 + 2800.
    assert Fraction(224) + Fraction(1400) == Fraction(1624)
    allreduce_expected = Fraction(2 * 7 * 16384, 8 * 64) + 2 * 7 * Fraction(200)
    assert allreduce_expected == Fraction(3248)
    critical_path = sum(Fraction(op["completion_time_ns_exact"]) for op in result["per_op"])
    assert critical_path == 4 * Fraction(3248) == Fraction(12992)
    assert critical_path == 4 * l0.ring_allreduce_time_ns(16384, RANKS, infra)
    cct = result["observables"]["O-CCT"]
    assert cct["ops"] == 8
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(1624))
    assert cct["completion_time_ns_max"] == 1624.0


def test_w2_golden_execution_doubling_family_1mib():
    # B: 1 MiB chunks on the committed doubling fabric; halving steps
    # 8392/4296/2248 -> 14936, AG mirrored; pair 29872 = 28672 + 1200
    # (independently derived closed form), conservation 2*7340032.
    data = yaml.safe_load(
        (_TOPO / "rdoubling8_free_params.yaml").read_text(encoding="utf-8")
    )
    infra = l0d.load_recursive_doubling_config(data)
    ops = w2.generate_w2_ops(_config(layers=1, chunks=1, chunk_bytes=1048576))
    assert [op.collective for op in ops] == ["reducescatter", "allgather"]
    result = l0p.execute_doubling_phases(ops, infra)
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["ops_checked"] == 2
    assert conservation["violations"] == 0
    assert conservation["total_wire_bytes_exact"] == str(Fraction(2 * 7340032))
    rs, ag = result["per_op"]
    assert [s["time_ns_exact"] for s in rs["steps"]] == [
        str(Fraction(8392)),
        str(Fraction(4296)),
        str(Fraction(2248)),
    ]
    assert [s["time_ns_exact"] for s in ag["steps"]] == [
        str(Fraction(2248)),
        str(Fraction(4296)),
        str(Fraction(8392)),
    ]
    for op in (rs, ag):
        assert op["per_rank_wire_bytes_exact"] == str(Fraction(917504))
        assert op["completion_time_ns_exact"] == str(Fraction(14936))
    assert rs["result_bytes_per_rank_exact"] == str(Fraction(131072))
    assert ag["result_bytes_per_rank_exact"] == str(Fraction(1048576))
    composed = Fraction(rs["completion_time_ns_exact"]) + Fraction(
        ag["completion_time_ns_exact"]
    )
    assert composed == Fraction(29872) == Fraction(28672) + Fraction(1200)
    assert composed == l0d.rd_allreduce_time_ns(1048576, infra)
