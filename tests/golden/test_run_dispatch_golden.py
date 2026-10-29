"""Golden run-path cases for the increment 5a dispatch wiring.

Every expected value below is hand-derived in the test file from the frozen
identities and the committed free parameters (B = 64 bytes/ns, L = 200 ns,
r = 8) — independent of the implementation under test, per the handoff rule
that golden tests derive from the specified identities.

Cases:

A) W2 Dense TP Prefill through the NORMAL run path on the doubling family
   (committed manifest w2_prefill_smoke.yaml: exchange fabric, halving RS /
   doubling AG). Workload: 2 layers x 2 chunks x 2 phases = 8 ops of
   M = 16384. Halving chunks 8192/4096/2048 -> step times 128+200, 64+200,
   32+200 = 328/264/232 -> phase 824 ns; doubling mirrored 232/264/328 ->
   824 ns. Wire per op = 7*M = 114688; conservation 8*114688 = 917504.
   Composed chunk pair 824+824 = 1648 = 2*(7/8)*16384/64 + 6*200 = 448+1200;
   serialized chain (4 pairs) = 4*1648 = 6592.

B) W2 through the run path on the RING family (tmp manifest variant with the
   ring fabric): per phase t = 7/8*16384/64 + 7*200 = 224 + 1400 = 1624;
   RS result M/8 = 2048, AG result M = 16384; conservation 8*114688 =
   917504; chunk pair 3248 = the landed ring AllReduce identity.

C) W1 Dense TP Decode through the run path on the NON-RING 2D torus
   (committed manifest w1_decode_torus2d.yaml: 2x4 grid). 6 ops (2 layers x
   3 steps) of M = 16384. dim1 (k=2): t = 16384/64 + 2*200 = 656; dim2
   (k=4): t = (3/2)*16384/64 + 6*200 = 1584; per-op t_2d = 2240. Wire per
   rank 40960 (= 16384 + 24576); per-op wire 8*40960 = 327680; conservation
   6*327680 = 1966080.
"""

import json
from fractions import Fraction
from pathlib import Path

import yaml

from essun.orchestrator.runs import run_experiment

REPO = Path(__file__).resolve().parents[2]
W2_MANIFEST = REPO / "experiments" / "vertical_slice" / "w2_prefill_smoke.yaml"
TORUS_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_torus2d.yaml"

DIVISIBLE = 16384  # 8 | 16384 (chunk 2048 B), 2 | M and 4 | M for the torus


def _run(manifest, root):
    result = run_experiment(manifest, results_root=root)
    observations = json.loads(
        (result["run_dir"] / "observations.json").read_text(encoding="utf-8")
    )
    record = json.loads((result["run_dir"] / "run.json").read_text(encoding="utf-8"))
    return result, observations, record


def test_dispatch_registries_cover_all_models_and_workloads():
    # Requirement 1: five L0 models and both workload kinds are registered
    # for dispatch; the hardcoded ring/W1 path is gone (no l0/w1 imports
    # used directly by the manifest execution path beyond the registries).
    # T022 S2 adds the Docker-pinned external adapter astra_sim_analytical
    # and Q3 S2 the uet_htsim_cms adapter to BACKENDS; each owns its
    # validate->compile->execute->parse pipeline via execute_experiment and
    # therefore has no DISPATCH routes.
    from essun.orchestrator import runs as orch

    assert sorted(orch.BACKENDS) == [
        "analytical_l0",
        "analytical_l0_crossbar",
        "analytical_l0_phase_collectives",
        "analytical_l0_recursive_doubling",
        "analytical_l0_tfc",
        "analytical_l0_torus2d",
        "astra_sim_analytical",
        "uet_htsim_cms",
    ]
    in_process = {
        backend_id
        for backend_id, module in orch.BACKENDS.items()
        if not hasattr(module, "execute_experiment")
    }
    assert set(orch.DISPATCH) == in_process
    assert "astra_sim_analytical" not in orch.DISPATCH
    assert "uet_htsim_cms" not in orch.DISPATCH
    # Every model routes at least one declared topology class.
    assert all(routes for routes in orch.DISPATCH.values())
    assert sorted(orch.WORKLOADS) == [
        "w1_dense_tp_decode",
        "w2_dense_tp_prefill",
        "w3_moe_dispatch_combine",
        "w5_pd_kv_prefill_decode",
    ]


def test_w2_prefill_runs_end_to_end_on_doubling_family(tmp_path):
    # A) the committed W2 manifest: phase collectives on the exchange fabric.
    result, observations, record = _run(W2_MANIFEST, tmp_path)
    assert len(result["run_id"]) == 64
    assert observations["backend_id"] == "analytical_l0_phase_collectives"
    model = observations["model"]
    assert model["topology_id"] == "rdoubling8_free_v1"
    assert model["algorithm_family"] == "recursive_halving_doubling"
    assert model["steps_log2_ranks"] == 3
    assert record["manifest"]["backends"] == ["analytical_l0_phase_collectives"]
    assert set(record["inputs"]) == {
        "workload_ir",
        "infra_graph",
        "standard_profile",
        "implementation_profile",
        "assumptions",
    }

    conservation = observations["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 8
    assert conservation["violations"] == 0
    # 8 ops x 7*16384 = 917504.
    assert conservation["total_wire_bytes_exact"] == str(Fraction(8 * 7 * DIVISIBLE))

    per_op = observations["per_op"]
    assert [op["op_id"] for op in per_op][:4] == [
        "l000000-c000000-reducescatter",
        "l000000-c000000-allgather",
        "l000000-c000001-reducescatter",
        "l000000-c000001-allgather",
    ]
    for op in per_op:
        assert op["per_rank_wire_bytes_exact"] == str(Fraction(7 * DIVISIBLE, 8))
        assert op["total_wire_bytes_exact"] == str(Fraction(7 * DIVISIBLE))
        assert op["completion_time_ns_exact"] == str(Fraction(824))
        # Halving chunks 8192/4096/2048 -> 328/264/232; doubling mirrored.
        if op["collective"] == "reducescatter":
            assert op["algorithm"] == "recursive_halving"
            assert op["result_bytes_per_rank_exact"] == str(Fraction(2048))
            assert [s["time_ns_exact"] for s in op["steps"]] == [
                str(Fraction(328)),
                str(Fraction(264)),
                str(Fraction(232)),
            ]
        else:
            assert op["collective"] == "allgather"
            assert op["algorithm"] == "recursive_doubling"
            assert op["result_bytes_per_rank_exact"] == str(Fraction(16384))
            assert [s["time_ns_exact"] for s in op["steps"]] == [
                str(Fraction(232)),
                str(Fraction(264)),
                str(Fraction(328)),
            ]
    cct = observations["observables"]["O-CCT"]
    assert cct["ops"] == 8
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(824))
    assert cct["completion_time_ns_max"] == 824.0
    # Composed chunk pair (A-L0P-COMP): 1648 = 448 + 1200, hand-derived.
    pair = Fraction(824) + Fraction(824)
    assert pair == Fraction(2 * 7 * DIVISIBLE, 8 * 64) + 6 * Fraction(200)
    # The serialized A-W2-DAG chain: 4 chunk pairs = 4*1648 = 6592.
    chain = sum(Fraction(op["completion_time_ns_exact"]) for op in per_op)
    assert chain == 4 * pair == Fraction(6592)


def test_w2_prefill_runs_end_to_end_on_ring_family(tmp_path):
    # B) same workload through the run path with the ring fabric selected:
    # the topology class routes to the ring phase family (A-L0P-ALGO).
    data = yaml.safe_load(W2_MANIFEST.read_text(encoding="utf-8"))
    data["infra_graph"]["path"] = "experiments/topologies/ring8_free_params.yaml"
    data["experiment_id"] = "EXP-VS-W2-RING-TEST"
    variant = tmp_path / "w2_ring.yaml"
    variant.write_text(yaml.safe_dump(data), encoding="utf-8")

    _, observations, _ = _run(variant, tmp_path)
    assert observations["model"]["algorithm_family"] == "ring"
    assert observations["model"]["topology_id"] == "ring8_free_v1"
    conservation = observations["observables"]["O-CONSERVATION"]
    assert conservation["ops_checked"] == 8
    assert conservation["total_wire_bytes_exact"] == str(Fraction(8 * 7 * DIVISIBLE))
    for op in observations["per_op"]:
        # t = 7/8*16384/64 + 7*200 = 224 + 1400 = 1624.
        assert op["algorithm"] == "ring"
        assert op["completion_time_ns_exact"] == str(Fraction(1624))
        assert op["hops"] == 7
        assert op["chunk_bytes_exact"] == str(Fraction(2048))
        if op["collective"] == "reducescatter":
            assert op["result_bytes_per_rank_exact"] == str(Fraction(2048))
        else:
            assert op["result_bytes_per_rank_exact"] == str(Fraction(16384))
    # Chunk pair composes the landed ring AllReduce identity: 2*224 + 2800.
    pair = 2 * Fraction(observations["per_op"][0]["completion_time_ns_exact"])
    assert pair == Fraction(3248) == Fraction(448) + Fraction(2800)


def test_w1_torus2d_runs_end_to_end(tmp_path):
    # C) the committed NON-RING manifest: W1 on the 2D torus.
    result, observations, record = _run(TORUS_MANIFEST, tmp_path)
    assert observations["backend_id"] == "analytical_l0_torus2d"
    assert observations["model"]["topology_id"] == "torus2d8_free_v1"
    assert (observations["model"]["dim1_ranks"], observations["model"]["dim2_ranks"]) == (
        2,
        4,
    )
    assert record["manifest"]["backends"] == ["analytical_l0_torus2d"]

    conservation = observations["observables"]["O-CONSERVATION"]
    # 6 ops (2 layers x 3 steps); wire per op 8*40960 = 327680.
    assert conservation["ops_checked"] == 6
    assert conservation["violations"] == 0
    assert conservation["total_wire_bytes_exact"] == str(Fraction(6 * 8 * 40960))

    per_op = observations["per_op"]
    assert len(per_op) == 6
    assert [op["op_id"] for op in per_op] == [
        f"s{step:06d}-l{layer:06d}-allreduce"
        for step in range(3)
        for layer in range(2)
    ]
    for op in per_op:
        # dim1: M/64 + 2*200 = 656; dim2: (3/2)M/64 + 6*200 = 1584.
        assert op["dim1_time_ns_exact"] == str(Fraction(656))
        assert op["dim2_time_ns_exact"] == str(Fraction(1584))
        assert op["completion_time_ns_exact"] == str(Fraction(2240))
        assert op["per_rank_wire_bytes_exact"] == str(Fraction(40960))
        assert op["dim1_wire_bytes_exact"] == str(Fraction(4 * 2 * DIVISIBLE))
        assert op["dim2_wire_bytes_exact"] == str(Fraction(2 * 6 * DIVISIBLE))
        assert op["total_wire_bytes_exact"] == str(Fraction(327680))
    cct = observations["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(2240))
    assert cct["completion_time_ns_max"] == 2240.0
