"""Negative tests for the serving feedback loop (T027 first slice).

Every guard must fail loudly with the gap named: unknown policy ids,
unknown driver observables, degenerate bounds, malformed observations,
and — via the backend's own gate — non-divisible feedback-derived payloads
(A-L0-DIV). A silent fallback would fabricate an undeclared feedback
semantic.
"""

from fractions import Fraction

import pytest

from essun.backends.analytical import l0
from essun.serving import feedback
from essun.workload import w1


def _infra():
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=8,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )


def _config():
    return {
        "policy_id": feedback.POLICY_ID,
        "threshold_ns": 3000,
        "min_batch": 1,
        "max_batch": 64,
        "per_sample_bytes": 512,
    }


def test_unknown_policy_id_rejected():
    cfg = _config() | {"policy_id": "aimd_batch"}
    with pytest.raises(ValueError, match="unknown feedback policy_id 'aimd_batch'"):
        feedback.policy_from_config(cfg)


def test_missing_config_keys_rejected():
    for key in ("policy_id", "threshold_ns", "min_batch", "max_batch", "per_sample_bytes"):
        cfg = {k: v for k, v in _config().items() if k != key}
        with pytest.raises(ValueError, match=f"missing key"):
            feedback.policy_from_config(cfg)


def test_degenerate_bounds_rejected():
    with pytest.raises(ValueError, match="max_batch 8 < min_batch 9"):
        feedback.BatchCCTPolicy(Fraction(3000), 9, 8, 512)
    with pytest.raises(ValueError, match="min_batch must be >= 1"):
        feedback.BatchCCTPolicy(Fraction(3000), 0, 8, 512)
    with pytest.raises(ValueError, match="per_sample_bytes must be >= 1"):
        feedback.BatchCCTPolicy(Fraction(3000), 1, 8, 0)
    with pytest.raises(ValueError, match="threshold_ns must be >= 0"):
        feedback.BatchCCTPolicy(Fraction(-1), 1, 8, 512)


def test_unknown_driver_observable_rejected():
    cfg = _config() | {"driver_observable": "O-TRAFFIC-IMBALANCE"}
    with pytest.raises(ValueError, match="identically 0"):
        feedback.policy_from_config(cfg)


def test_zero_batch_state_rejected():
    with pytest.raises(ValueError, match="decode_batch_size must be >= 1"):
        feedback.ServingState(0)


def test_cct_extraction_guards():
    policy = feedback.BatchCCTPolicy(Fraction(3000), 1, 64, 512)
    # no O-CCT entry at all
    with pytest.raises(ValueError, match="cannot drive feedback"):
        feedback.apply_between_runs(
            policy, feedback.ServingState(32), {"observables": {"O-CONSERVATION": {}}}
        )
    # wrong kind (registry mismatch)
    with pytest.raises(ValueError, match="kind 'exact'"):
        feedback.apply_between_runs(
            policy,
            feedback.ServingState(32),
            {"observables": {"O-CCT": {"kind": "exact"}}},
        )
    # missing exact-mean field
    with pytest.raises(ValueError, match="completion_time_ns_mean_exact"):
        feedback.apply_between_runs(
            policy,
            feedback.ServingState(32),
            {"observables": {"O-CCT": {"kind": "analytical"}}},
        )


def test_within_run_requires_ops():
    policy = feedback.BatchCCTPolicy(Fraction(3000), 1, 64, 512)
    with pytest.raises(ValueError, match="non-empty op list"):
        feedback.apply_within_run(policy, feedback.ServingState(32), [], _infra())


def test_rounds_requires_positive_rounds():
    policy = feedback.BatchCCTPolicy(Fraction(3000), 1, 64, 512)
    config = w1.W1Config(tp_size=8, layers=1, steps=1, allreduce_bytes=16384)
    with pytest.raises(ValueError, match="rounds must be >= 1"):
        feedback.no_overlap_rounds(
            policy, feedback.ServingState(32), config, _infra(), rounds=0
        )


def test_divisibility_gate_still_fires_on_feedback_payload():
    """The backend's A-L0-DIV gate guards the feedback path: a policy whose
    per-sample bytes yield a non-divisible payload is rejected at execution,
    not silently chunked fractionally."""
    policy = feedback.BatchCCTPolicy(Fraction(3000), 1, 64, 1)  # payload = batch
    ops = w1.generate_w1_ops(w1.W1Config(tp_size=8, layers=1, steps=1, allreduce_bytes=16384))
    with pytest.raises(ValueError, match="A-L0-DIV"):
        feedback.apply_within_run(policy, feedback.ServingState(17), ops, _infra())
