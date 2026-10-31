"""The flag-driven fault-injection harness is itself under test.

Mission of these guards (the evaluation demand behind the harness):

(a) INJECTIONS ACTUALLY CHANGE OUTPUTS — every flagged defect carrier
    must produce values different from the clean engine on the
    committed initial case (a flag that changes nothing detects
    nothing);
(b) CLEAN RUNS DETECT NOTHING — with every injection flag off, the
    same probes, minimizer, and classifier over clean-vs-clean pairs
    must report no disagreement at the initial case, at EVERY candidate
    the committed shrink ladder generates, and through the minimizer
    (a false alarm is an engine finding);
(c) the CLI's flag selection, JSON summary, and honest exit codes do
    what they claim (a missed/misclassified defect or false alarm
    exits nonzero — findings are never hidden by a green exit).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CASE_DIR = REPO / "experiments" / "diagnosis" / "defect_seeding"
COMMITTED = CASE_DIR / "defect_seeding_record_v1.json"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, CASE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = _load("g9_defect_harness_tests", "harness.py")
BUILDER = _load("g9_defect_harness_tests_builder", "build_record.py")


# -- (a) injections actually change outputs -------------------------------------


def test_every_injection_changes_outputs() -> None:
    specs = BUILDER._trial_specs()
    for name in BUILDER.TRIAL_ORDER:
        spec = specs[name]
        clean = spec["clean_fn"](spec["initial"])
        injected = spec["defect_fn"](spec["initial"])
        assert clean != injected, (
            f"defect {name}: the carrier reproduces the clean engine's "
            "values on the committed initial case — the flag changes "
            "nothing and the harness could never detect it"
        )


# -- (b) clean runs detect nothing ------------------------------------------------


def test_clean_runs_detect_nothing() -> None:
    """Injection off in every case space: no disagreement may be found —
    at the initial case, at any ladder candidate, or by the minimizer."""
    for name in BUILDER.TRIAL_ORDER:
        baseline = HARNESS.run_clean_baseline(BUILDER, name)
        assert baseline["initial_outcome"] == "vanished", baseline
        assert baseline["false_alarm_count"] == 0, baseline
        assert baseline["minimizer_reproducer_found"] is False, baseline
        # the baseline actually probed the ladder's candidates (not a
        # vacuous pass over an empty candidate set)
        assert baseline["candidates_probed"] >= 10, baseline


# -- (c) the CLI does what it claims ----------------------------------------------


def test_cli_default_runs_all_four_and_matches_committed_summary() -> None:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = HARNESS.main(["--json"])
    assert rc == 0
    payload = json.loads(buffer.getvalue())
    summary = payload["summary"]
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))["summary"]
    assert payload["injected"] == list(BUILDER.TRIAL_ORDER)
    assert summary["injections_run"] == 4
    assert summary["detected"] == committed["detected"] == 4
    assert (
        summary["classification_matches_ground_truth"]
        == committed["classification_matches_ground_truth"]
        == 4
    )
    assert summary["findings"] == committed["missed_or_misclassified"] == []


def test_cli_single_defect_flag_selects_one_trial() -> None:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = HARNESS.main(["--inject", "ignored_gb_unit_conversion", "--json"])
    assert rc == 0
    payload = json.loads(buffer.getvalue())
    assert payload["injected"] == ["ignored_gb_unit_conversion"]
    assert len(payload["trials"]) == 1
    assert payload["trials"][0]["classification"]["label"] == "translation_defect"


def test_cli_clean_baseline_reports_zero_false_alarms() -> None:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = HARNESS.main(["--inject", "all", "--clean-baseline"])
    assert rc == 0
    text = buffer.getvalue()
    assert "false alarms 0/4" in text


def test_cli_exits_nonzero_on_a_finding(monkeypatch) -> None:
    """The honesty of the exit path: a missed defect (or false alarm)
    must FAIL the run — findings are reported, never hidden."""

    original_run_injected = HARNESS.run_injected

    def fake_run_injected(builder, name):
        trial = original_run_injected(builder, name)
        if name == builder.TRIAL_ORDER[0]:
            trial["detected"] = False  # simulate an engine regression
        return trial

    monkeypatch.setattr(HARNESS, "run_injected", fake_run_injected)
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = HARNESS.main([])
    assert rc == 1
    assert "FINDINGS" in buffer.getvalue()
