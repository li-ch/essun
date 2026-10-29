"""Determinism/replay proofs for the serving feedback loop (T027 first
slice): same inputs -> same feedback -> same downstream values, byte-identical
through the canonical JSON serialization, and the feedback-derived run
replays byte-identically through the dispatched run path (same standard as
tests/determinism/test_replay.py).
"""

import json
from fractions import Fraction
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.evidence.store import canonical_json
from essun.orchestrator.runs import run_experiment
from essun.serving import feedback
from essun.workload import w1

REPO = Path(__file__).resolve().parents[2]
SMOKE_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"


def _infra():
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=8,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )


def _config():
    return w1.W1Config(tp_size=8, layers=2, steps=3, allreduce_bytes=16384)


def _policy():
    return feedback.BatchCCTPolicy(Fraction(3000), 30, 64, 512)


def test_within_run_loop_replays_identically():
    ops = w1.generate_w1_ops(_config())
    first = feedback.apply_within_run(_policy(), feedback.ServingState(32), ops, _infra())
    second = feedback.apply_within_run(_policy(), feedback.ServingState(32), ops, _infra())
    assert first == second
    # and byte-identical under the platform's canonical serialization
    assert canonical_json(first) == canonical_json(second)


def test_no_overlap_loop_replays_identically():
    first = feedback.no_overlap_rounds(
        _policy(), feedback.ServingState(32), _config(), _infra(), rounds=3
    )
    second = feedback.no_overlap_rounds(
        _policy(), feedback.ServingState(32), _config(), _infra(), rounds=3
    )
    assert first == second
    assert canonical_json(first) == canonical_json(second)
    # the per-round observations digests are stable across replays
    assert [r["observations_sha256"] for r in first["rounds"]] == [
        r["observations_sha256"] for r in second["rounds"]
    ]


def test_feedback_manifest_replays_byte_identical(tmp_path):
    """The feedback-derived run N+1 manifest replays byte-identically
    through run_experiment (run_id + artifacts), extending the existing
    replay proof to feedback-derived workloads."""
    policy = feedback.BatchCCTPolicy(Fraction(3000), 1, 64, 512)
    run_n = run_experiment(SMOKE_MANIFEST, results_root=tmp_path / "store_n")
    state = feedback.apply_between_runs(policy, feedback.ServingState(32), run_n["observations"])
    config = feedback.next_w1_config(policy, state, _config())

    workload_path = tmp_path / "w1_feedback_b31.yaml"
    workload_path.write_text(
        yaml.safe_dump(
            {
                "workload": w1.WORKLOAD_KIND,
                "model_name": "dense-tp-decode-feedback-b31",
                "tp_size": 8,
                "layers": 2,
                "steps": 3,
                "allreduce_bytes": config.allreduce_bytes,
            }
        ),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(SMOKE_MANIFEST.read_text(encoding="utf-8"))
    manifest["experiment_id"] = "EXP-T027-W1-FEEDBACK-REPLAY-001"
    manifest["workload_ir"]["path"] = str(workload_path)
    manifest_path = tmp_path / "manifest_feedback.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    first = run_experiment(manifest_path, results_root=tmp_path / "a")
    second = run_experiment(manifest_path, results_root=tmp_path / "b")
    assert first["run_id"] == second["run_id"]
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right, f"{artifact} differs between identical feedback replays"
    # sanity: the replayed run is the feedback-altered one (mean 3234)
    observations = json.loads(
        (tmp_path / "a" / first["run_id"] / "observations.json").read_text(encoding="utf-8")
    )
    assert (
        observations["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == "3234"
    )


def test_different_observation_yields_different_feedback():
    """Controlled ablation at the decision point: only the observation
    changes, and the downstream state and payload follow it (the feedback
    channel is the observation, not the seed or the clock)."""
    policy = feedback.BatchCCTPolicy(Fraction(3000), 1, 64, 512)
    base = {"kind": "analytical"}

    def obs(mean_exact: str) -> dict:
        return {"observables": {"O-CCT": base | {"completion_time_ns_mean_exact": mean_exact}}}

    slow = feedback.apply_between_runs(policy, feedback.ServingState(32), obs("3248"))
    fast = feedback.apply_between_runs(policy, feedback.ServingState(32), obs("2999"))
    assert slow.decode_batch_size == 31
    assert fast.decode_batch_size == 33
    assert (
        feedback.next_w1_config(policy, slow, _config()).allreduce_bytes
        != feedback.next_w1_config(policy, fast, _config()).allreduce_bytes
    )
