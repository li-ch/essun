"""Tests for tools/paper_check.py (T060 placeholder-discipline checker).

Frozen readouts from the P6 program:
  - checker passes on the committed paper/ skeleton;
  - checker fails on a planted fabricated number;
  - checker fails on a planted forbidden claim word.
Plus one bonus case covering rule R3 (results/ reference without a run_id).

The OD-6a vocabulary extension promised tests that never landed (IP7
round-2 note N2); D-032 item 8 lands them here and extends the vocabulary
with the 3 round-2 documented forms (IP7 N1: SOTA, novelty, spaced
"state of the art"), and the 2026-10-29 drift batch extends it again with
6 program-4 forms (owner decision 8 / pool-8 round-3 note N1:
industrial-grade, battle-tested, production-proven, seamless; note N2:
the inflection variants seamlessly, novelties). Every form in the
checker's vocabulary tuple is planted in its own test case and asserted
flagged — the parametrization is driven by the checker module itself, so
a newly added form gains a test case automatically.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools" / "paper_check.py"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load_checker():
    spec = importlib.util.spec_from_file_location("paper_check_under_test", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paper_check = _load_checker()


def planted_text(form: str) -> str:
    """The literal prose planted for a vocabulary form (regex escapes
    like ``\\s+`` become the plain spaced phrase they match)."""
    return form.replace(r"\s+", " ")


def run_checker(paper_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--paper-dir", str(paper_dir)],
        capture_output=True,
        text=True,
    )


def test_checker_passes_on_repo_skeleton():
    proc = run_checker(ROOT / "paper")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_checker_passes_on_clean_fixture():
    proc = run_checker(FIXTURES / "paper_clean")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_checker_fails_on_planted_fabricated_number():
    proc = run_checker(FIXTURES / "paper_fabricated_number")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    # 37% (unit), 1.9x (factor), 1024 (bare int) all flagged
    for planted in ("37%", "1.9x", "1024"):
        assert planted in proc.stdout, proc.stdout
    assert "[number/" in proc.stdout


def test_checker_fails_on_planted_forbidden_word():
    proc = run_checker(FIXTURES / "paper_forbidden_word")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "novel" in proc.stdout
    assert "first" in proc.stdout
    assert "[claim-word]" in proc.stdout


def test_checker_fails_on_results_ref_without_run_id():
    proc = run_checker(FIXTURES / "paper_figref_no_runid")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "results/latest" in proc.stdout
    assert "[fig-ref]" in proc.stdout


def test_claim_words_regex_is_built_from_the_form_tuple():
    """Drift guard: the R2 regex must be exactly the tuple's alternation,
    so the parametrized planting below provably covers every form the
    regex matches (hand-editing the pattern breaks this test)."""
    assert paper_check.CLAIM_WORDS.pattern == (
        r"\b(?:" + "|".join(paper_check.CLAIM_WORD_FORMS) + r")\b"
    )


@pytest.mark.parametrize(
    "form", list(paper_check.CLAIM_WORD_FORMS), ids=planted_text
)
def test_every_claim_word_form_is_flagged(form, tmp_path):
    """One test case per form in the checker's vocabulary (OD-6a's
    promised coverage, landed 2026-10-28): planting the form in otherwise
    clean prose must fail the checker with a [claim-word] violation that
    names the planted form."""
    planted = planted_text(form)
    probe = tmp_path / "probe.md"
    probe.write_text(
        f"Our approach is {planted} among the baselines.\n", encoding="utf-8"
    )
    proc = run_checker(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "[claim-word]" in proc.stdout
    assert f"'{planted}'" in proc.stdout, proc.stdout
    # exactly one violation: the planted claim word, nothing else
    violation_lines = [
        line for line in proc.stdout.splitlines() if ": " in line and "FAIL" not in line
    ]
    assert len(violation_lines) == 1, proc.stdout
