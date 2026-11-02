"""The public reproduction board: deterministic render, gated by tests.

``tools/reproduction_board.py`` rewrites the marked section of
``site/reproductions.html`` from ``experiments/reproductions/*.yaml``.
Two properties are under test:

- determinism: the same record set renders byte-identically, ordered by
  (reported, reproduction id), content escaped, no wall-clock;
- freshness: the committed page must match the committed records — the
  ``--check`` mode (and this test) fails otherwise, which is what makes
  the page display a new attempt the moment its record lands: landing a
  record without re-rendering breaks the suite.

Also: the board refuses to render an asserting record (the adjudication
gate runs at load time), so a label cannot reach the page by editing
HTML or YAML alone.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from essun.evidence.reproductions import (
    INDEPENDENCE_CRITERIA,
    ReproductionError,
    load_reproduction_file,
    render_board_rows,
)

REPO = Path(__file__).resolve().parents[2]
BOARD_TOOL = REPO / "tools" / "reproduction_board.py"
PAGE = REPO / "site" / "reproductions.html"
RECORDS_DIR = REPO / "experiments" / "reproductions"


def attempt_yaml(reproducer: str, reported: str = "2026-11-02") -> str:
    document = {
        "reported": reported,
        "report_url": "https://github.com/li-ch/essun/issues/1#issuecomment-1",
        "reproducer": reproducer,
        "reproduced_at_commit": "a" * 40,
        "environment": "test host",
        "outcome": "byte_identical",
        "divergence_notes": None,
        "reproduced_run_ids": ["b" * 64],
        "independence": {name: None for name in INDEPENDENCE_CRITERIA},
    }
    return yaml.safe_dump(document, sort_keys=True)


def test_empty_board_renders_the_honest_empty_state():
    html = render_board_rows([])
    assert "No reproduction attempts recorded yet" in html
    assert "<table" not in html


def test_board_renders_adjudicated_label_only_through_the_gate(tmp_path):
    """A fully supported adjudication renders the label with its class."""
    document = yaml.safe_load(attempt_yaml("@someone-else"))
    document["adjudication"] = {
        "verdict": "externally_reproduced",
        "adjudicator": "li-ch",
        "date": "2026-11-03",
        "basis": "checked: account history, environment, pinned ids",
        "independence": {
            name: {"met": True, "note": "checked"} for name in INDEPENDENCE_CRITERIA
        },
    }
    path = tmp_path / "adjudicated.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    attempt, adjudication = load_reproduction_file(path)
    html = render_board_rows([(attempt, adjudication)])
    assert "EXTERNALLY_REPRODUCED" in html
    assert "label label-external" in html


def test_board_renders_a_row(tmp_path):
    path = tmp_path / "attempt.yaml"
    path.write_text(attempt_yaml("@someone-else"), encoding="utf-8")
    attempt, adjudication = load_reproduction_file(path)
    html = render_board_rows([(attempt, adjudication)])
    assert "<table" in html
    assert "@someone-else" in html
    assert "byte_identical" in html
    assert "bbbbbbbb" in html  # run id is shown shortened
    assert "UNKNOWN" in html  # no adjudication: label reads unknown


def test_board_escapes_content(tmp_path):
    path = tmp_path / "attempt.yaml"
    path.write_text(attempt_yaml('<script>alert("x")</script>'), encoding="utf-8")
    attempt, adjudication = load_reproduction_file(path)
    html = render_board_rows([(attempt, adjudication)])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_board_ordering_is_deterministic(tmp_path):
    later = tmp_path / "b_later.yaml"
    later.write_text(attempt_yaml("@later-person", reported="2026-11-05"), encoding="utf-8")
    earlier = tmp_path / "a_earlier.yaml"
    earlier.write_text(attempt_yaml("@earlier-person", reported="2026-11-01"), encoding="utf-8")
    records = [load_reproduction_file(p) for p in (later, earlier)]
    first = render_board_rows(records)
    second = render_board_rows(list(reversed(records)))
    assert first == second  # input order cannot change the render
    assert first.index("@earlier-person") < first.index("@later-person")


def test_board_refuses_an_asserting_record(tmp_path):
    """A record may not assert the label for an author's own re-run."""
    document = yaml.safe_load(attempt_yaml("@li-ch"))
    document["adjudication"] = {
        "verdict": "externally_reproduced",
        "adjudicator": "li-ch",
        "date": "2026-11-03",
        "basis": "self-asserted",
        "independence": {
            name: {"met": True, "note": "x"} for name in INDEPENDENCE_CRITERIA
        },
    }
    path = tmp_path / "asserting.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    try:
        load_reproduction_file(path)
    except ReproductionError as error:
        assert "author identity" in str(error)
    else:
        raise AssertionError("expected the gate to refuse the self-adjudication")


def test_committed_page_matches_committed_records():
    """The freshness gate: page and records must not drift apart."""
    proc = subprocess.run(
        [sys.executable, str(BOARD_TOOL), "--check"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"board is stale or invalid:\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert "up to date" in proc.stdout


def test_committed_page_carries_the_markers():
    text = PAGE.read_text(encoding="utf-8")
    assert "BOARD:BEGIN" in text and "BOARD:END" in text
