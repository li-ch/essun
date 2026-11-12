"""Golden identities for the W6 RL rollout generator.

Expected values are recomputed independently here (hand-derived counts,
orderings, byte sums, and ring identities spelled out, not by calling the
implementation under test), per the handoff rule that golden tests derive
from the specified identities.

Identity under test (W6 rollout, frozen): one rollout round is a
GENERATION burst — ``gen_steps`` decode-style steps x ``layers`` AllReduces
of ``gen_bytes`` — followed by ONE weight-sync phase of ``sync_allreduces``
AllReduces of ``sync_bytes`` (op-id prefix ``sync-``). Emission order is
round-major, then step, then layer for generation ops, with the sync ops
last within each round. All ops go to the full TP group (ranks
``[0, tp_size)``); integer byte counts; no RNG anywhere (replayable).

Worked cases (derived by hand below, asserted exactly):

A) Tiny case (tp=2, layers=1, gen_steps=1, gen_bytes=8,
   sync_allreduces=1, sync_bytes=16, rounds=1): 2 ops, every field of
   every op spelled out literal-by-literal.

B) Committed smoke YAML (tp=8, layers=2, gen_steps=3, gen_bytes=16384,
   sync_allreduces=2, sync_bytes=65536, rounds=2): 8 ops per round
   (3*2 generation + 2 sync), 16 total. Generation payload sum
   2*3*2*16384 = 196608; sync payload sum 2*2*65536 = 262144; total
   458752. On the L0 ring (B=64 B/ns, L=200 ns, r=8): per generation op
   t = 7/4*16384/64 + 14*200 = 448 + 2800 = 3248 ns; per sync op
   t = 7/4*65536/64 + 2800 = 1792 + 2800 = 4592 ns; serialized mean over
   the 16 ops (12*3248 + 4*4592)/16 = 57344/16 = 3584 ns; total wire
   bytes 12*2*7*16384 + 4*2*7*65536 = 2752512 + 3670016 = 6422528.
"""

from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.evidence.store import canonical_json
from essun.workload import w6

REPO = Path(__file__).resolve().parents[2]
WORKLOAD_YAML = REPO / "experiments" / "workloads" / "w6_rollout_small.yaml"
W1_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"


def _tiny_config():
    # Case A: tp=2, layers=1, gen_steps=1, gen_bytes=8, sync_allreduces=1,
    # sync_bytes=16, rounds=1.
    return w6.W6Config(
        tp_size=2,
        layers=1,
        gen_steps=1,
        gen_bytes=8,
        sync_allreduces=1,
        sync_bytes=16,
        rounds=1,
    )


def _smoke_config():
    return w6.load_w6_config(WORKLOAD_YAML)


# --- op-count / ordering identity (round-major, sync last per round) ------------


def test_w6_ops_count_order_and_phases():
    # 2 rounds x (3 steps x 2 layers generation ops + 2 sync ops) = 16 ops;
    # emission is round-major -> step -> layer, sync ops LAST within each
    # round with the frozen "sync-" op-id prefix.
    ops = w6.generate_w6_ops(_smoke_config())
    assert len(ops) == 16
    expected_round0 = [
        "r000000-s000000-l000000-allreduce",
        "r000000-s000000-l000001-allreduce",
        "r000000-s000001-l000000-allreduce",
        "r000000-s000001-l000001-allreduce",
        "r000000-s000002-l000000-allreduce",
        "r000000-s000002-l000001-allreduce",
        "sync-r000000-a000000-allreduce",
        "sync-r000000-a000001-allreduce",
    ]
    assert [op.op_id for op in ops[:8]] == expected_round0
    assert [op.op_id for op in ops[8:]] == [
        op_id.replace("r000000", "r000001") for op_id in expected_round0
    ]
    assert [op.op_id for op in ops] == [op.op_id for op in ops]  # stable
    assert len({op.op_id for op in ops}) == 16  # globally unique ids
    for op in ops[:6] + ops[8:14]:
        assert op.collective == "allreduce"
        assert op.phase == w6.PHASE_GENERATION
        assert op.payload_bytes == 16384
        assert op.comm_ranks == tuple(range(8))
        assert not op.op_id.startswith("sync-")
    for op in ops[6:8] + ops[14:16]:
        assert op.collective == "allreduce"
        assert op.phase == w6.PHASE_WEIGHT_SYNC
        assert op.payload_bytes == 65536
        assert op.comm_ranks == tuple(range(8))
        assert op.op_id.startswith("sync-")


def test_w6_round_block_structure():
    # Round-major: ops come in per-round blocks of gen_steps*layers +
    # sync_allreduces, rounds 0..R-1 in order, each block ending with its
    # sync ops; within the generation burst, step is the minor order and
    # layer the innermost.
    config = _smoke_config()
    ops = w6.generate_w6_ops(config)
    per_round = config.gen_steps * config.layers + config.sync_allreduces
    for round_index in range(config.rounds):
        block = ops[round_index * per_round : (round_index + 1) * per_round]
        assert all(op.round == round_index for op in block)
        gen, sync = block[: config.gen_steps * config.layers], block[config.gen_steps * config.layers :]
        assert all(op.phase == w6.PHASE_GENERATION for op in gen)
        assert all(op.phase == w6.PHASE_WEIGHT_SYNC for op in sync)
        assert [(op.step, op.layer) for op in gen] == [
            (step, layer)
            for step in range(config.gen_steps)
            for layer in range(config.layers)
        ]
        assert all(op.step is None and op.layer is None for op in sync)


# --- A: tiny case, every field of every op hand-derived -------------------------


def test_w6_tiny_ops_hand_derived():
    # Every field literal-by-literal: one generation AllReduce (8 bytes over
    # ranks {0,1}) then one weight-sync AllReduce (16 bytes, "sync-" prefix).
    ops = w6.generate_w6_ops(_tiny_config())
    assert len(ops) == 2
    gen, sync = ops
    assert gen.op_id == "r000000-s000000-l000000-allreduce"
    assert gen.collective == "allreduce"
    assert gen.comm_ranks == (0, 1)
    assert gen.payload_bytes == 8
    assert (gen.round, gen.step, gen.layer) == (0, 0, 0)
    assert gen.phase == "generation"
    assert sync.op_id == "sync-r000000-a000000-allreduce"
    assert sync.collective == "allreduce"
    assert sync.comm_ranks == (0, 1)
    assert sync.payload_bytes == 16
    assert (sync.round, sync.step, sync.layer) == (0, None, None)
    assert sync.phase == "weight_sync"


# --- B: committed smoke YAML, byte sums hand-derived ----------------------------


def test_w6_workload_yaml_loads():
    config = _smoke_config()
    assert config == w6.W6Config(
        tp_size=8,
        layers=2,
        gen_steps=3,
        gen_bytes=16384,
        sync_allreduces=2,
        sync_bytes=65536,
        rounds=2,
        model_name="rl-rollout-smoke",
    )
    assert len(w6.generate_w6_ops(config)) == 16


def test_w6_smoke_byte_sums_hand_derived():
    ops = w6.generate_w6_ops(_smoke_config())
    gen = [op for op in ops if op.phase == w6.PHASE_GENERATION]
    sync = [op for op in ops if op.phase == w6.PHASE_WEIGHT_SYNC]
    # Generation: rounds*gen_steps*layers*gen_bytes = 2*3*2*16384 = 196608.
    assert len(gen) == 12
    assert sum(op.payload_bytes for op in gen) == 196608
    # Weight sync: rounds*sync_allreduces*sync_bytes = 2*2*65536 = 262144.
    assert len(sync) == 4
    assert sum(op.payload_bytes for op in sync) == 262144
    assert sum(op.payload_bytes for op in ops) == 196608 + 262144 == 458752


# --- determinism / replay equality ----------------------------------------------


def test_w6_generation_deterministic_canonical_json():
    # Two generations from independently constructed equal configs must be
    # equal (replay equality), byte-identical under canonical JSON (handoff
    # determinism rules). The construction uses no RNG anywhere.
    first = w6.generate_w6_ops(_smoke_config())
    second = w6.generate_w6_ops(
        w6.W6Config(
            tp_size=8,
            layers=2,
            gen_steps=3,
            gen_bytes=16384,
            sync_allreduces=2,
            sync_bytes=65536,
            rounds=2,
        )
    )
    assert first == second
    a = canonical_json([asdict(op) for op in first])
    b = canonical_json([asdict(op) for op in second])
    assert a == b
    assert a == canonical_json([asdict(op) for op in w6.generate_w6_ops(_smoke_config())])


# --- negative: degenerate configs rejected --------------------------------------


def test_w6_degenerate_config_rejected():
    base = dict(
        tp_size=8,
        layers=2,
        gen_steps=3,
        gen_bytes=16384,
        sync_allreduces=2,
        sync_bytes=65536,
        rounds=2,
    )
    for bad in (
        dict(tp_size=0),
        dict(layers=0),
        dict(gen_steps=0),
        dict(gen_bytes=0),
        dict(sync_allreduces=0),
        dict(sync_bytes=0),
        dict(rounds=0),
    ):
        try:
            w6.generate_w6_ops(w6.W6Config(**{**base, **bad}))
        except ValueError as exc:
            assert "degenerate" in str(exc), f"{bad}: {exc}"
        else:
            raise AssertionError(f"expected ValueError for degenerate config {bad}")


def test_w6_loader_rejects_wrong_kind_and_degenerate(tmp_path):
    wrong = tmp_path / "wrong_kind.yaml"
    wrong.write_text("workload: w1_dense_tp_decode\ntp_size: 8\n", encoding="utf-8")
    try:
        w6.load_w6_config(wrong)
    except ValueError as exc:
        assert "expected workload kind" in str(exc)
    else:
        raise AssertionError("expected ValueError for wrong workload kind")

    degenerate = tmp_path / "degenerate.yaml"
    degenerate.write_text(
        "workload: w6_rollout\ntp_size: 8\nlayers: 2\ngen_steps: 0\n"
        "gen_bytes: 16384\nsync_allreduces: 2\nsync_bytes: 65536\nrounds: 2\n",
        encoding="utf-8",
    )
    try:
        w6.load_w6_config(degenerate)
    except ValueError as exc:
        assert "degenerate" in str(exc)
    else:
        raise AssertionError("expected ValueError for degenerate YAML")


# --- L0 ring execution identity (hand-derived; see module docstring case B) -----


def test_w6_ops_execute_on_l0_ring_identity():
    ops = w6.generate_w6_ops(_smoke_config())
    infra = l0.load_infra(
        yaml.safe_load(
            (REPO / "experiments" / "topologies" / "ring8_free_params.yaml").read_text(
                encoding="utf-8"
            )
        )
    )
    result = l0.execute(ops, infra)
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 16
    assert conservation["violations"] == 0
    # Total wire bytes = 12 * 2*(r-1)*gen_bytes + 4 * 2*(r-1)*sync_bytes
    #                  = 12*229376 + 4*917504 = 6422528.
    assert conservation["total_wire_bytes_exact"] == str(Fraction(6422528))
    cct = result["observables"]["O-CCT"]
    # Serialized per-op completions: 12 x 3248 ns + 4 x 4592 ns; mean
    # 57344/16 = 3584 ns exactly.
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3584))


# --- registration: dispatchable through the real run path -----------------------


def test_w6_registered_and_dispatchable(tmp_path):
    # The kind is registered in the orchestrator's WORKLOADS (the W5
    # precedent: every generator kind is), and a W6 workload actually runs
    # end-to-end through run_experiment on the ring AllReduce model — W6
    # issues plain AllReduces, so unlike W3/W5 it is not capability-gated.
    from essun.orchestrator import runs as orch

    assert w6.WORKLOAD_KIND in orch.WORKLOADS
    assert orch.WORKLOADS[w6.WORKLOAD_KIND] == (w6.load_w6_config, w6.generate_w6_ops)

    import json

    data = yaml.safe_load(W1_MANIFEST.read_text(encoding="utf-8"))
    data["workload_ir"]["path"] = "experiments/workloads/w6_rollout_small.yaml"
    manifest = tmp_path / "w6_smoke.yaml"
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
    result = orch.run_experiment(manifest, results_root=tmp_path / "results")
    observations = json.loads(
        (result["run_dir"] / "observations.json").read_text(encoding="utf-8")
    )
    assert observations["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == str(
        Fraction(3584)
    )
