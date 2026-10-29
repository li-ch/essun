"""Negative tests for the increment 5a dispatch wiring: every capability
gate fails loudly with the gap named, and the O1 divisibility guards reject
non-integral chunking explicitly (never silently computed).

Manifest variants are written from the committed manifests so the gates are
exercised through the real run path (orchestrator.runs.run_experiment).
"""

from pathlib import Path

import pytest
import yaml

from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.backends.analytical import l0_recursive_doubling as l0d
from essun.backends.analytical import l0_torus2d as l0t
from essun.orchestrator import runs as orch
from essun.workload import w1, w2

REPO = Path(__file__).resolve().parents[2]
W1_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"
W2_MANIFEST = REPO / "experiments" / "vertical_slice" / "w2_prefill_smoke.yaml"
W3_WORKLOAD = REPO / "experiments" / "workloads" / "w3_moe_dispatch_combine_small.yaml"
W5_WORKLOAD = REPO / "experiments" / "workloads" / "w5_pd_kv_prefill_decode_small.yaml"
TOPO = REPO / "experiments" / "topologies"
DIVISIBLE = 16384
NON_DIVISIBLE = 16385  # 8 does not divide 16385


def _write_manifest(base, tmp_path, mutate, name="variant.yaml"):
    data = yaml.safe_load(Path(base).read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# --- requirement 3: capability gates through the run path -------------------


def test_allreduce_backend_rejects_w2_phase_collectives(tmp_path):
    # The ring AllReduce model does not declare reducescatter/allgather;
    # the run must fail loudly, not silently fake the phases.
    path = _write_manifest(
        W1_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w2_dense_tp_prefill_small.yaml"
        ),
    )
    with pytest.raises(orch.ExecutionError, match="reducescatter"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_phase_backend_rejects_w1_allreduce(tmp_path):
    path = _write_manifest(
        W2_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w1_dense_tp_decode_small.yaml"
        ),
    )
    with pytest.raises(orch.ExecutionError, match="allreduce"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_model_topology_class_pairing_gates(tmp_path):
    # A torus model on a ring fabric is an undeclared pairing: different
    # identity, rejected before anything executes.
    path = _write_manifest(
        W2_MANIFEST,
        tmp_path,
        lambda data: (
            data.update(backends=["analytical_l0_torus2d"]),
            data["infra_graph"].update(
                path="experiments/topologies/ring8_free_params.yaml"
            ),
            data["workload_ir"].update(
                path="experiments/workloads/w1_dense_tp_decode_small.yaml"
            ),
        ),
        name="torus_on_ring.yaml",
    )
    with pytest.raises(orch.ExecutionError, match="topology_class"):
        orch.run_experiment(path, results_root=tmp_path / "results")

    # The phase model on the crossbar fabric is likewise undeclared.
    path = _write_manifest(
        W2_MANIFEST,
        tmp_path,
        lambda data: data["infra_graph"].update(
            path="experiments/topologies/crossbar8_free_params.yaml"
        ),
        name="phases_on_crossbar.yaml",
    )
    with pytest.raises(orch.ExecutionError, match="explicitly unsupported"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_allreduce_backend_rejects_w3_alltoall(tmp_path):
    # T030 (MoE W3 dispatch/combine): the workload kind is REGISTERED but
    # its all-to-all ops are declared by no model — the run must fail the
    # collective capability gate loudly, never fake MoE traffic on an
    # AllReduce identity. This rejection is a tested behavior; executing
    # MoE dispatch/combine needs an L1/L2 backend.
    path = _write_manifest(
        W1_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w3_moe_dispatch_combine_small.yaml"
        ),
    )
    with pytest.raises(orch.ExecutionError, match="alltoall"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_phase_backend_rejects_w3_alltoall(tmp_path):
    # Same gate on the phase-collectives model: ReduceScatter/AllGather do
    # not cover all-to-all either.
    path = _write_manifest(
        W2_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w3_moe_dispatch_combine_small.yaml"
        ),
    )
    with pytest.raises(orch.ExecutionError, match="alltoall"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_allreduce_backend_rejects_w5_kv_memory_ops(tmp_path):
    # T031 (PD/KV W5): the workload kind is REGISTERED but its
    # memory-semantic ops (kv_alloc/kv_write/kv_transfer/kv_visible/
    # kv_read/kv_release) are declared by no model — the run must fail the
    # collective capability gate loudly, never fake KV traffic on an
    # AllReduce identity. This rejection is a tested behavior; executing
    # PD/KV traffic needs an L1/L2 memory-semantics fabric model.
    path = _write_manifest(
        W1_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w5_pd_kv_prefill_decode_small.yaml"
        ),
    )
    with pytest.raises(orch.ExecutionError, match="kv_transfer"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_phase_backend_rejects_w5_kv_memory_ops(tmp_path):
    # Same gate on the phase-collectives model: ReduceScatter/AllGather do
    # not cover memory-semantic KV ops either.
    path = _write_manifest(
        W2_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w5_pd_kv_prefill_decode_small.yaml"
        ),
    )
    with pytest.raises(orch.ExecutionError, match="kv_transfer"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_unknown_workload_kind_rejected(tmp_path):
    workload = tmp_path / "w3.yaml"
    workload.write_text(
        "workload: w3_moe_alltoall\ntp_size: 8\n", encoding="utf-8"
    )
    path = _write_manifest(
        W1_MANIFEST,
        tmp_path,
        lambda data: data["workload_ir"].update(path=str(workload)),
    )
    with pytest.raises(orch.ExecutionError, match="unknown workload kind"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_workload_topology_rank_mismatch_rejected(tmp_path):
    ring4 = tmp_path / "ring4.yaml"
    ring4.write_text(
        "topology_id: ring4_free_v1\ntopology_class: unidirectional_ring\n"
        "ranks: 4\nlink:\n  bytes_per_ns: 64\n  hop_latency_ns: 200\n",
        encoding="utf-8",
    )
    path = _write_manifest(
        W1_MANIFEST, tmp_path, lambda data: data["infra_graph"].update(path=str(ring4))
    )
    with pytest.raises(orch.ExecutionError, match="tp_size 8 != topology ranks 4"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_degenerate_topology_rejected_through_run_path(tmp_path):
    # A 3x3 grid does not tile ranks=8: the model loader's explicit refusal
    # surfaces as an ExecutionError, not a silent partial run.
    torus_bad = tmp_path / "torus_bad.yaml"
    torus_bad.write_text(
        "topology_id: torus_bad\ntopology_class: torus2d_ring_x_ring\n"
        "ranks: 8\ngrid:\n  dim1_ranks: 3\n  dim2_ranks: 3\n"
        "link:\n  bytes_per_ns: 64\n  hop_latency_ns: 200\n",
        encoding="utf-8",
    )
    path = _write_manifest(
        REPO / "experiments" / "vertical_slice" / "w1_decode_torus2d.yaml",
        tmp_path,
        lambda data: data["infra_graph"].update(path=str(torus_bad)),
    )
    with pytest.raises(orch.ExecutionError, match="does not tile"):
        orch.run_experiment(path, results_root=tmp_path / "results")


# --- requirement 4 (O1): non-integral chunking rejected ---------------------


def test_non_divisible_payload_rejected_through_run_path(tmp_path):
    workload = tmp_path / "w1_nodiv.yaml"
    workload.write_text(
        "workload: w1_dense_tp_decode\nmodel_name: w1-nodiv\n"
        f"tp_size: 8\nlayers: 1\nsteps: 1\nallreduce_bytes: {NON_DIVISIBLE}\n",
        encoding="utf-8",
    )
    path = _write_manifest(
        W1_MANIFEST, tmp_path, lambda data: data["workload_ir"].update(path=str(workload))
    )
    with pytest.raises(ValueError, match="A-L0-DIV"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def _w1_op(payload_bytes):
    op = w1.generate_w1_ops(
        w1.W1Config(tp_size=8, layers=1, steps=1, allreduce_bytes=payload_bytes)
    )[0]
    return op


def _w2_ops(payload_bytes):
    return w2.generate_w2_ops(
        w2.W2Config(tp_size=8, layers=1, chunks_per_layer=1, chunk_bytes=payload_bytes)
    )


def _ring8():
    return l0.load_infra(
        yaml.safe_load((TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8"))
    )


def _crossbar8():
    return l0_crossbar.load_crossbar_config(
        yaml.safe_load((TOPO / "crossbar8_free_params.yaml").read_text(encoding="utf-8"))
    )


def _rdoubling8():
    return l0d.load_recursive_doubling_config(
        yaml.safe_load((TOPO / "rdoubling8_free_params.yaml").read_text(encoding="utf-8"))
    )


def _torus8():
    return l0t.load_torus2d_config(
        yaml.safe_load((TOPO / "torus2d_8_free_params.yaml").read_text(encoding="utf-8"))
    )


def test_l0_ring_rejects_non_divisible_payload():
    with pytest.raises(ValueError, match="not divisible by 8"):
        l0.execute([_w1_op(NON_DIVISIBLE)], _ring8())
    # The divisible control still executes (identity unchanged).
    assert l0.execute([_w1_op(DIVISIBLE)], _ring8())["observables"]["O-CONSERVATION"][
        "violations"
    ] == 0


def test_crossbar_rejects_non_divisible_payload():
    with pytest.raises(ValueError, match="A-L0X-DIV"):
        l0_crossbar.execute([_w1_op(NON_DIVISIBLE)], _crossbar8())


def test_recursive_doubling_rejects_non_divisible_payload():
    with pytest.raises(ValueError, match="A-L0D-DIV"):
        l0d.execute([_w1_op(NON_DIVISIBLE)], _rdoubling8())


def test_torus_rejects_payload_not_divisible_by_a_dimension():
    # 16386 is divisible by dim1 (2) but NOT by dim2 (4) -> dim2 raises.
    assert 16386 % 2 == 0 and 16386 % 4 != 0
    with pytest.raises(ValueError, match="A-L0T-DIV"):
        l0t.execute([_w1_op(16386)], _torus8())
    # 16387 is odd: dim1 raises first.
    with pytest.raises(ValueError, match="not divisible by 2"):
        l0t.execute([_w1_op(16387)], _torus8())


def test_phase_collectives_reject_non_divisible_payload():
    # Ring family.
    with pytest.raises(ValueError, match="A-L0P-DIV"):
        l0p.execute_ring_phases(_w2_ops(NON_DIVISIBLE), _ring8())
    # Doubling family.
    with pytest.raises(ValueError, match="A-L0P-DIV"):
        l0p.execute_doubling_phases(_w2_ops(NON_DIVISIBLE), _rdoubling8())


def test_divisibility_rejection_names_the_assumption_registry():
    # The error text must point at the assumption registry entry so the
    # rejection is auditable (O1: state the assumption, name it when fired).
    try:
        l0.execute([_w1_op(NON_DIVISIBLE)], _ring8())
    except ValueError as exc:
        message = str(exc)
        assert "A-L0-DIV" in message
        assert "assumptions_l0.yaml" in message
        assert str(NON_DIVISIBLE) in message
    else:
        raise AssertionError("expected ValueError for non-divisible payload")
