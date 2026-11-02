"""The trust dashboard: honest indicators, generated, gated by tests.

``tools/trust_dashboard.py`` renders the marked section of
``site/trust.html`` from the committed snapshot
``experiments/trust/indicators.yaml``; the snapshot's repo-derived
counts are re-derived from ``experiments/reproductions/`` and
``experiments/community/``.  Properties under test:

- schema honesty: a count may not exist without its source (a citation
  count without a configured paper is refused), stranger counts may not
  exceed totals, field sets are exact;
- the stranger rule (author identities + automation excluded, deleted
  accounts still strangers) and GitHub aggregation (pull requests
  interleaved in the issues payload are counted as pull requests);
- render: deterministic, escaped, and UNKNOWN — never a zero — for a
  source that cannot be read yet;
- freshness: the committed page must be the render of the committed
  snapshot and the snapshot's tree-derived counts must match the tree
  (the ``--check`` mode and this test fail otherwise, the same gate as
  the reproduction board and the community table).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from essun.evidence.reproductions import INDEPENDENCE_CRITERIA
from essun.evidence.trust import (
    TrustError,
    aggregate_github,
    derive_repo,
    dump_snapshot,
    is_stranger,
    load_snapshot,
    load_sources,
    render_dashboard_rows,
    repo_drift,
    snapshot_problems,
)

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "trust_dashboard.py"
PAGE = REPO / "site" / "trust.html"
SNAPSHOT = REPO / "experiments" / "trust" / "indicators.yaml"
SOURCES = REPO / "experiments" / "trust" / "sources.yaml"
EXAMPLE = REPO / "examples" / "submission.example.yaml"

#: Committed files the submission tree gates read (copied into tmp repos
#: so a derive test can land one valid community record offline).
TREE_GATE_FILES = (
    "experiments/vertical_slice/assumptions_l0.yaml",
    "experiments/calibration/s4/topologies/ring8_s4_l64_v1.yaml",
    "experiments/calibration/s4/topologies/ring8_s4_l140_v1.yaml",
)


def snapshot_document() -> dict:
    """A valid snapshot in the honest state of the project today."""
    return {
        "schema": "trust-indicators/v1",
        "repo": {
            "as_of_commit": "a" * 40,
            "reproduction_attempts_total": 0,
            "externally_reproduced_total": 0,
            "community_submissions_total": 0,
        },
        "github": {
            "repository": "li-ch/essun",
            "as_of": "2026-11-02",
            "issues_total": 1,
            "issues_from_strangers": 0,
            "pulls_total": 0,
            "pulls_from_strangers": 0,
        },
        "citations": {
            "source": "semanticscholar",
            "arxiv_id": None,
            "as_of": "2026-11-02",
            "count": None,
            "note": "no public paper to count citations of yet",
        },
    }


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


def adjudication() -> dict:
    return {
        "verdict": "externally_reproduced",
        "adjudicator": "li-ch",
        "date": "2026-11-03",
        "basis": "checked: account history, environment, pinned ids",
        "independence": {
            name: {"met": True, "note": "checked"} for name in INDEPENDENCE_CRITERIA
        },
    }


def github_entry(number: int, login: str | None, pull: bool = False) -> dict:
    entry: dict = {"number": number, "user": {"login": login} if login else None}
    if pull:
        entry["pull_request"] = {}
    return entry


# ---------------------------------------------------------------------------
# snapshot schema
# ---------------------------------------------------------------------------


def test_snapshot_schema_accepts_the_honest_zeros():
    assert snapshot_problems(snapshot_document()) == []


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d["repo"].update(reproduction_attempts_total=-1), "non-negative"),
        (lambda d: d["repo"].update(externally_reproduced_total=True), "non-negative"),
        (lambda d: d["github"].update(issues_from_strangers=2), "exceeds"),
        (lambda d: d["github"].update(pulls_from_strangers=1), "exceeds"),
        (lambda d: d["citations"].update(count=0), "no public paper"),
        (lambda d: d["citations"].pop("note"), "citations.note"),
        (lambda d: d.update(extra={}), "unknown section"),
        (lambda d: d["repo"].pop("as_of_commit"), "missing field"),
        (lambda d: d["repo"].update(as_of_commit="XYZ"), "40 lowercase hex"),
        (lambda d: d.update(schema="trust-indicators/v2"), "schema"),
        (lambda d: d["github"].update(repository="not-a-repo"), "owner/name"),
        (lambda d: d["github"].update(as_of="yesterday"), "ISO date"),
    ],
)
def test_snapshot_schema_refuses_hand_edits(mutate, fragment):
    document = snapshot_document()
    mutate(document)
    problems = snapshot_problems(document)
    assert problems, "the mutation must be refused"
    assert any(fragment in problem for problem in problems), problems


def test_citation_count_is_refused_without_a_public_paper():
    """Unknown is not zero: no arXiv id, no count — even an honest-looking 0."""
    document = snapshot_document()
    document["citations"]["count"] = 0
    problems = snapshot_problems(document)
    assert any("no public paper" in problem for problem in problems)


def test_snapshot_dump_is_deterministic():
    text = dump_snapshot(snapshot_document())
    assert text == dump_snapshot(snapshot_document())
    assert "schema: trust-indicators/v1" in text


# ---------------------------------------------------------------------------
# strangers and aggregation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "login, expected",
    [
        ("some-stranger", True),
        ("li-ch", False),
        ("@Li-Ch", False),
        ("li chen", False),
        ("dependabot[bot]", False),
        ("github-actions[bot]", False),
        (None, True),
        ("", True),
    ],
)
def test_stranger_rule(login, expected):
    assert is_stranger(login) is expected


def test_aggregate_separates_prs_and_filters_authors_and_bots():
    issues = [
        github_entry(1, "li-ch"),  # the author's own funnel issue
        github_entry(2, "someone"),  # a stranger
        github_entry(3, "dependabot[bot]"),  # automation, not a person
        github_entry(4, None),  # deleted account: still a stranger
        github_entry(5, "li-ch", pull=True),  # interleaved PR: not an issue
    ]
    pulls = [github_entry(101, "li-ch"), github_entry(102, "someone-else")]
    assert aggregate_github(issues, pulls) == {
        "issues_total": 4,
        "issues_from_strangers": 2,
        "pulls_total": 2,
        "pulls_from_strangers": 1,
    }


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def test_render_is_deterministic():
    assert render_dashboard_rows(snapshot_document()) == render_dashboard_rows(
        snapshot_document()
    )


def test_render_reads_unknown_not_zero_for_unmeasured_citations():
    row = render_dashboard_rows(snapshot_document()).split("Citations of the paper")[1]
    row = row.split("</tr>")[0]
    assert "UNKNOWN" in row
    assert "no public paper" in row  # the recorded reason travels with the unknown
    assert '<td class="n">0</td>' not in row


def test_render_shows_a_measured_zero_as_zero():
    document = snapshot_document()
    document["citations"].update(
        arxiv_id="2611.01234",
        count=0,
        note="Semantic Scholar citation count for arXiv:2611.01234",
    )
    row = render_dashboard_rows(document).split("Citations of the paper")[1]
    row = row.split("</tr>")[0]
    assert "UNKNOWN" not in row
    assert '<td class="n">0</td>' in row  # a read zero is a zero


def test_render_escapes_free_text():
    document = snapshot_document()
    document["citations"]["note"] = "<script>alert(1)</script>"
    rendered = render_dashboard_rows(document)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_render_carries_stranger_totals_as_context():
    rendered = render_dashboard_rows(snapshot_document())
    assert "Issues opened by strangers" in rendered
    assert "(of 1 total)" in rendered


# ---------------------------------------------------------------------------
# repo derivation
# ---------------------------------------------------------------------------


def test_derive_repo_counts_attempts_and_gated_labels(tmp_path):
    records = tmp_path / "experiments" / "reproductions"
    records.mkdir(parents=True)
    (records / "a_unknown.yaml").write_text(attempt_yaml("@someone-else"), encoding="utf-8")
    adjudicated = yaml.safe_load(attempt_yaml("@another-person"))
    adjudicated["adjudication"] = adjudication()
    (records / "b_adjudicated.yaml").write_text(
        yaml.safe_dump(adjudicated, sort_keys=True), encoding="utf-8"
    )
    derived = derive_repo(tmp_path, "c" * 40)
    assert derived == {
        "as_of_commit": "c" * 40,
        "reproduction_attempts_total": 2,
        "externally_reproduced_total": 1,  # only through the gated adjudication
        "community_submissions_total": 0,  # no community dir: an honest zero
    }


def test_derive_repo_refuses_an_invalid_record(tmp_path):
    records = tmp_path / "experiments" / "reproductions"
    records.mkdir(parents=True)
    broken = yaml.safe_load(attempt_yaml("@someone"))
    broken["outcome"] = "mostly-fine"  # not a valid outcome
    (records / "broken.yaml").write_text(yaml.safe_dump(broken), encoding="utf-8")
    with pytest.raises(Exception):
        derive_repo(tmp_path, "c" * 40)


def test_derive_repo_counts_committed_submissions(tmp_path):
    community = tmp_path / "experiments" / "community"
    community.mkdir(parents=True)
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    cited = [row["run_ids"][0] for row in document["results"]]
    document["review"] = {
        "decision": "published",
        "reviewer": "@maintainer",
        "date": "2026-11-02",
        "basis": "re-ran the cited manifests; ids regenerated byte-for-byte",
        "verified_run_ids": cited,
    }
    (community / "sample.yaml").write_text(
        yaml.safe_dump(document, sort_keys=True), encoding="utf-8"
    )
    for relative in TREE_GATE_FILES:  # the tree gates read the committed files
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, target)
    derived = derive_repo(tmp_path, "c" * 40)
    assert derived["community_submissions_total"] == 1


def test_repo_drift_flags_counts_but_not_commit_provenance():
    snapshot = snapshot_document()
    moved_commit = dict(snapshot["repo"], as_of_commit="b" * 40)
    problems: list[str] = []
    repo_drift(problems, moved_commit, snapshot)
    assert problems == []  # every later commit moves as_of_commit; not drift
    drifted = dict(snapshot["repo"], reproduction_attempts_total=1)
    repo_drift(problems, drifted, snapshot)
    assert len(problems) == 1
    assert "reproduction_attempts_total" in problems[0]


# ---------------------------------------------------------------------------
# files and the committed state
# ---------------------------------------------------------------------------


def test_load_snapshot_names_the_file_on_error(tmp_path):
    path = tmp_path / "indicators.yaml"
    path.write_text("schema: [", encoding="utf-8")
    with pytest.raises(TrustError, match="indicators.yaml"):
        load_snapshot(path)


def test_committed_sources_are_valid_and_point_at_the_public_repo():
    sources = load_sources(SOURCES)
    assert sources["github_repository"] == "li-ch/essun"
    assert sources["arxiv_id"] is None  # no paper public yet; citations stay UNKNOWN


def test_load_sources_rejects_unknown_fields(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("github_repository: a/b\narxiv_id: null\nstars: 999\n", encoding="utf-8")
    with pytest.raises(TrustError, match="unknown field"):
        load_sources(path)


def test_committed_snapshot_is_schema_valid():
    assert load_snapshot(SNAPSHOT)["schema"] == "trust-indicators/v1"


def test_committed_page_and_snapshot_match_the_tree():
    """The freshness gate: page, snapshot, and records must not drift apart."""
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"trust dashboard is stale or invalid:\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert "PASS" in proc.stdout


def test_committed_page_carries_the_markers():
    text = PAGE.read_text(encoding="utf-8")
    assert "DASHBOARD:BEGIN" in text and "DASHBOARD:END" in text
