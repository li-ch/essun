"""Guards for the G9 leg-3 seeded-defect trial record.

(a) the committed record rebuilds BYTE-IDENTICALLY from the builder (a
drift is an error: the record is append-only; a change requires a v2);
(b) the measured detection/classification table is what it claims: every
trial detected, every classification matching ground truth — and if a
future engine change breaks one, this test reports the finding instead
of papering over it;
(c) spot exact values: the minimal reproducers are the committed ones
and the return-batching carrier provably respects the admission law.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from essun.diagnosis import defects as defect_carriers

REPO = Path(__file__).resolve().parents[2]
CASE_DIR = REPO / "experiments" / "diagnosis" / "defect_seeding"
BUILDER = CASE_DIR / "build_record.py"
COMMITTED = CASE_DIR / "defect_seeding_record_v1.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location("g9_defect_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_record_rebuilds_byte_identically() -> None:
    module = _load_builder()
    rebuilt = json.dumps(module.build(), indent=2, sort_keys=True) + "\n"
    committed = COMMITTED.read_text(encoding="utf-8")
    assert rebuilt == committed


def test_all_defects_detected_and_classified() -> None:
    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    summary = record["summary"]
    assert summary["defects_seeded"] == 4
    assert summary["detected"] == 4, (
        "a seeded defect went undetected — a finding about the diagnosis "
        "engine; read the record, fix the engine, never this test"
    )
    assert summary["classification_matches_ground_truth"] == 4
    assert summary["missed_or_misclassified"] == []


def test_minimal_reproducers_are_the_committed_ones() -> None:
    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    by_id = {t["defect_id"]: t for t in record["trials"]}
    # the FLOOR carrier crashes on sub-cell chunks: the minimizer certified
    # the crash boundary (final-pass rejections are error_engine_b)
    floor = by_id["floor_not_roundup_credit_consumption"]
    assert floor["minimal_case"]["payload_bytes"] == 896
    assert any(
        p["outcome"] == "error_engine_b"
        for p in floor["minimization"]["final_pass_rejections"]
    )
    # the batched-return disagreement needs MORE packets than one window
    # batch covers: 3 packets at W=2 packets, vanishing at 2 packets
    batched = by_id["drain_batched_credit_return"]
    assert batched["minimal_case"]["total_bytes"] == 768  # 3 x 256 B
    assert batched["minimal_case"]["window_bytes"] == 512  # 2 packets
    rejections = {
        (p["description"], p["outcome"])
        for p in batched["minimization"]["final_pass_rejections"]
    }
    assert ("packets 3 -> 2", "vanished") in rejections
    assert ("window 512 -> 256", "vanished") in rejections
    # the op-count-dependent omission certifies its 2-op lower bound
    sched = by_id["latency_omitted_after_first_op"]
    assert sched["minimal_case"]["ops_count"] == 2
    assert ("ops 2 -> 1", "vanished") in {
        (p["description"], p["outcome"])
        for p in sched["minimization"]["final_pass_rejections"]
    }


def test_batched_return_carrier_respects_admission_law() -> None:
    """The permitted-variation classification's mechanical basis: the
    carrier's own admission trace satisfies the UEC11-FC-R02 sliding-window
    bound (never more than the granted window in flight)."""
    from essun.specir import credit_automaton as ca

    case = defect_carriers.LinkCase(
        total_bytes=64 * 256,
        window_bytes=4096,
        link_bytes_per_ns=64,
        hop_latency_ns=100,
        credit_return_latency_ns=100,
        packet_bytes=256,
    )
    executor = defect_carriers._BatchedGreedyExecutor(case.as_automaton_config())
    result = executor.run_transfer(case.total_bytes)
    assert ca.sliding_window_bound_holds(
        executor.machine.admissions,
        case.window_bytes,
        case.as_automaton_config().credit_loop_delay_ns,
    )
    # and the carrier is strictly slower or equal to the clean machine
    clean = defect_carriers.link_transfer_completion(case)
    assert result.completion_ns >= clean
