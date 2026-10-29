"""Golden tests for the network-to-serving feedback loop (T027 first slice).

Expected values are HAND-DERIVED here from the L0 ring identity, not taken
from the implementation's output (same rule as test_w1_l0_golden.py):

    t(M, r=8) = 2*(r-1)/r * M / B + 2*(r-1)*L
              = (7/4 * M) / 64 + 14 * 200
              = 7*M/256 + 2800   [ns], with B=64 B/ns, L=200 ns (free params)

Decode batch b with per_sample_bytes 512 -> M = 512*b:

    b=27 -> M=13824 -> t = 7*13824/256 + 2800 = 378 + 2800 = 3178
    b=28 -> M=14336 -> t = 392 + 2800 = 3192
    b=29 -> M=14848 -> t = 406 + 2800 = 3206
    b=30 -> M=15360 -> t = 420 + 2800 = 3220
    b=31 -> M=15872 -> t = 434 + 2800 = 3234
    b=32 -> M=16384 -> t = 448 + 2800 = 3248
    b=33 -> M=16896 -> t = 462 + 2800 = 3262
    b=34 -> M=17408 -> t = 476 + 2800 = 3276

All payloads are divisible by r=8 (512 is), so A-L0-DIV holds for every
reachable batch.
"""

from fractions import Fraction
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.orchestrator.runs import run_experiment
from essun.serving import feedback
from essun.workload import w1

RANKS = 8
PER_SAMPLE = 512
REPO = Path(__file__).resolve().parents[2]
SMOKE_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"


def _infra():
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )


def _base_config():
    # allreduce_bytes is overwritten by the loop; tp/layers/steps fixed.
    return w1.W1Config(tp_size=RANKS, layers=2, steps=3, allreduce_bytes=16384)


# ---------------------------------------------------------------------------
# No-overlap case: feedback applies only between runs
# ---------------------------------------------------------------------------


def test_no_overlap_golden_between_runs():
    """Run N's O-CCT mean (3248) > threshold (3000) -> batch 32 -> 31 ->
    run N+1 payload 15872 -> O-CCT mean 3234 (hand-derived)."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3000), min_batch=1, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    state = feedback.ServingState(32)

    # Run N: the committed smoke payload (16384 = 32*512).
    config_n = feedback.next_w1_config(policy, state, _base_config())
    assert config_n.allreduce_bytes == 16384
    obs_n = l0.execute(w1.generate_w1_ops(config_n), _infra())
    assert obs_n["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == "3248"

    # Feedback: 3248 > 3000 -> decrease.
    state_n1 = feedback.apply_between_runs(policy, state, obs_n)
    assert state_n1.decode_batch_size == 31

    # Run N+1: payload 31*512 = 15872; mean t = 7*15872/256 + 2800 = 3234.
    config_n1 = feedback.next_w1_config(policy, state_n1, _base_config())
    assert config_n1.allreduce_bytes == 15872
    ops_n1 = w1.generate_w1_ops(config_n1)
    assert all(op.payload_bytes == 15872 for op in ops_n1)
    obs_n1 = l0.execute(ops_n1, _infra())
    assert obs_n1["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == "3234"
    # The downstream run's observable VALUES changed with the state.
    assert (
        obs_n1["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
        != obs_n["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
    )


def test_no_overlap_rounds_golden_with_min_clamp():
    """Four rounds, threshold 3000, min_batch 30: 32 -> 31 -> 30 -> 30 (clamped)."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3000), min_batch=30, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    record = feedback.no_overlap_rounds(
        policy, feedback.ServingState(32), _base_config(), _infra(), rounds=4
    )
    expected = [
        # (batch, payload, cct_mean) hand-derived from 7M/256 + 2800
        (32, 16384, "3248"),
        (31, 15872, "3234"),
        (30, 15360, "3220"),
        (30, 15360, "3220"),  # target 29 clamped to min_batch 30
    ]
    assert len(record["rounds"]) == 4
    for entry, (batch, payload, cct) in zip(record["rounds"], expected):
        assert entry["decode_batch_size"] == batch
        assert entry["allreduce_bytes"] == payload
        assert entry["cct_mean_ns_exact"] == cct
    assert record["final_state"]["decode_batch_size"] == 30


def test_no_overlap_runs_through_dispatched_run_path(tmp_path):
    """The loop integrates with run_experiment + the evidence store: run N
    through the committed manifest, feedback-derived workload for run N+1
    through a manifest, landing a stored run whose O-CCT is the hand-derived
    3234 (not run N's 3248)."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3000), min_batch=1, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    state = feedback.ServingState(32)

    # Run N on the dispatched run path (committed smoke manifest).
    run_n = run_experiment(SMOKE_MANIFEST, results_root=tmp_path / "store_n")
    assert (
        run_n["observations"]["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
        == "3248"
    )

    state_n1 = feedback.apply_between_runs(policy, state, run_n["observations"])
    assert state_n1.decode_batch_size == 31
    config_n1 = feedback.next_w1_config(policy, state_n1, _base_config())
    assert config_n1.allreduce_bytes == 15872

    # Run N+1 workload file + manifest (tmp only; absolute paths win in
    # resolve_inputs' Path join).
    workload_path = tmp_path / "w1_feedback_b31.yaml"
    workload_path.write_text(
        yaml.safe_dump(
            {
                "workload": w1.WORKLOAD_KIND,
                "model_name": "dense-tp-decode-feedback-b31",
                "tp_size": RANKS,
                "layers": 2,
                "steps": 3,
                "allreduce_bytes": 15872,
            }
        ),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(SMOKE_MANIFEST.read_text(encoding="utf-8"))
    manifest["experiment_id"] = "EXP-T027-W1-FEEDBACK-NOOVERLAP-001"
    manifest["claim_id"] = "C4"
    manifest["workload_ir"]["path"] = str(workload_path)
    manifest["validity_domain"]["workload"] = (
        "w1_dense_tp_decode smoke config with feedback-derived batch 31 "
        "(payload 15872 = 31*512, free parameter per_sample_bytes)"
    )
    manifest_path = tmp_path / "manifest_feedback.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    run_n1 = run_experiment(manifest_path, results_root=tmp_path / "store_n1")
    cct_n1 = run_n1["observations"]["observables"]["O-CCT"]
    assert cct_n1["completion_time_ns_mean_exact"] == "3234"
    assert cct_n1["completion_time_ns_mean_exact"] != (
        run_n["observations"]["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
    )
    # The feedback-derived run is stored and conservation-clean.
    assert (run_n1["run_dir"] / "observations.json").is_file()
    assert (
        run_n1["observations"]["observables"]["O-CONSERVATION"]["violations"] == 0
    )


# ---------------------------------------------------------------------------
# Overlap case: feedback applies within a run, collective -> next collective
# ---------------------------------------------------------------------------


def test_overlap_golden_within_run_decrease():
    """Threshold 3000, initial batch 32, six ops (3 steps x 2 layers): the
    batch drops by one after every op (all cct > threshold), each next op's
    payload follows. Full hand-derived trace below."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3000), min_batch=1, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    ops = w1.generate_w1_ops(_base_config())
    assert len(ops) == 6
    record = feedback.apply_within_run(policy, feedback.ServingState(32), ops, _infra())

    expected_trace = [
        # op_id, batch, payload, cct (all hand-derived: 7*M/256 + 2800)
        ("s000000-l000000-allreduce", 32, 16384, "3248"),
        ("s000000-l000001-allreduce", 31, 15872, "3234"),
        ("s000001-l000000-allreduce", 30, 15360, "3220"),
        ("s000001-l000001-allreduce", 29, 14848, "3206"),
        ("s000002-l000000-allreduce", 28, 14336, "3192"),
        ("s000002-l000001-allreduce", 27, 13824, "3178"),
    ]
    assert record["ops"] == 6
    for entry, (op_id, batch, payload, cct) in zip(record["trace"], expected_trace):
        assert entry["op_id"] == op_id
        assert entry["batch_size"] == batch
        assert entry["payload_bytes"] == payload
        assert entry["cct_ns_exact"] == cct
        assert entry["next_batch_size"] == batch - 1
    # In-run feedback actually fired: the last op ran at a different batch
    # than the first, inside ONE run.
    assert record["trace"][0]["batch_size"] != record["trace"][-1]["batch_size"]
    assert record["final_state"]["decode_batch_size"] == 26


def test_overlap_increase_direction_and_max_clamp():
    """Threshold 3300, max_batch 34: cct < threshold increases the batch
    (3248 -> batch 33 -> 3262 -> batch 34 -> 3276 -> clamped at 34)."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3300), min_batch=1, max_batch=34,
        per_sample_bytes=PER_SAMPLE,
    )
    ops = w1.generate_w1_ops(w1.W1Config(tp_size=RANKS, layers=1, steps=3, allreduce_bytes=16384))
    record = feedback.apply_within_run(policy, feedback.ServingState(32), ops, _infra())
    expected = [
        (32, 16384, "3248", 33),
        (33, 16896, "3262", 34),
        (34, 17408, "3276", 34),  # target 35 clamped to max_batch 34
    ]
    for entry, (batch, payload, cct, nxt) in zip(record["trace"], expected):
        assert entry["batch_size"] == batch
        assert entry["payload_bytes"] == payload
        assert entry["cct_ns_exact"] == cct
        assert entry["next_batch_size"] == nxt
    assert record["final_state"]["decode_batch_size"] == 34


def test_overlap_exact_equality_holds_tie_breaking():
    """Threshold exactly 3248 with payload 16384: cct == threshold -> hold
    (the documented fixed tie-breaking; decidable because O-CCT is exact)."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3248), min_batch=1, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    ops = w1.generate_w1_ops(_base_config())
    record = feedback.apply_within_run(policy, feedback.ServingState(32), ops, _infra())
    for entry in record["trace"]:
        assert entry["batch_size"] == 32
        assert entry["payload_bytes"] == 16384
        assert entry["cct_ns_exact"] == "3248"
        assert entry["next_batch_size"] == 32
    assert record["final_state"]["decode_batch_size"] == 32


def test_overlap_min_clamp_on_decrease():
    """Threshold 2000, min_batch 30: every cct exceeds it, the batch floors
    at 30 (32 -> 31 -> 30 -> 30)."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(2000), min_batch=30, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    ops = w1.generate_w1_ops(w1.W1Config(tp_size=RANKS, layers=1, steps=3, allreduce_bytes=16384))
    record = feedback.apply_within_run(policy, feedback.ServingState(32), ops, _infra())
    expected = [(32, "3248", 31), (31, "3234", 30), (30, "3220", 30)]
    for entry, (batch, cct, nxt) in zip(record["trace"], expected):
        assert entry["batch_size"] == batch
        assert entry["cct_ns_exact"] == cct
        assert entry["next_batch_size"] == nxt


def test_feedback_is_observation_driven():
    """The decision flips with the observation around the threshold, and is
    a pure function of (state, observation) — the feedback is driven by the
    emitted observable, nothing else."""
    policy = feedback.BatchCCTPolicy(
        threshold_ns=Fraction(3000), min_batch=1, max_batch=64,
        per_sample_bytes=PER_SAMPLE,
    )
    state = feedback.ServingState(32)
    assert policy.next_state(state, Fraction(3001)).decode_batch_size == 31
    assert policy.next_state(state, Fraction(2999)).decode_batch_size == 33
    assert policy.next_state(state, Fraction(3000)).decode_batch_size == 32
    # Same observation twice -> same decision (no hidden state).
    obs = {"observables": {"O-CCT": {
        "kind": "analytical", "completion_time_ns_mean_exact": "3248"}}}
    first = feedback.apply_between_runs(policy, state, obs)
    second = feedback.apply_between_runs(policy, state, obs)
    assert first == second and first.decode_batch_size == 31
