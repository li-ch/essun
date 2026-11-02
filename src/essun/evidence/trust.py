"""Trust dashboard: adoption indicators, observed — never asserted.

The positioning analysis defined the leading indicators that would show
the project is (or is not) becoming something the community depends on:
reproduction attempts, issues from strangers, pull requests, citations,
and submissions through the comparison-submission door.  This module is
the machinery that observes them and renders one public table
(``site/trust.html``, via ``tools/trust_dashboard.py``) under three
rules that override every other:

1. **Zeros stay zeros.**  A number is written only when a source was
   actually read.  The honest state of every adoption indicator today is
   zero, and the page says so because the sources say so — not because
   zero looks modest.
2. **No manual curation.**  Every number is either re-derived from the
   committed tree (reproduction attempts and adjudicated labels from
   ``experiments/reproductions/``, submissions from
   ``experiments/community/``) or fetched from a named public API (the
   GitHub REST API for issues and pull requests, Semantic Scholar for
   citations, keyed on the arXiv id configured in
   ``experiments/trust/sources.yaml``).  Nothing on the page is typed by
   a person, and a hand-edited number cannot survive: the render is a
   pure function of the committed snapshot, and the suite fails if the
   page, the snapshot, and the tree drift apart.
3. **Unknown is never rounded to anything.**  A source that cannot be
   read renders as UNKNOWN with its reason, per the absence semantics of
   :mod:`essun.evidence.dimensions`.  Citations are the live case: until
   the paper is public (``arxiv_id: null``), the citation count is not
   zero — it is not measurable, and the snapshot refuses to carry a
   count without a configured paper to count from.

A **stranger** is anyone who is neither a repository author identity
(:data:`essun.evidence.reproductions.AUTHOR_IDENTITIES`, the single
shared list) nor automation: a login ending in ``[bot]`` is machinery,
not a person depending on the tool, and a missing login (a deleted
account) is still a stranger — it is certainly not an author.

Committed surface: the snapshot ``experiments/trust/indicators.yaml``
(schema ``trust-indicators/v1`` below) is the only state; the page is
regenerated from it between DASHBOARD markers.  ``--fetch`` (CI, weekly)
refreshes the fetched sections and commits the result; any record
landing under ``experiments/reproductions/`` or
``experiments/community/`` re-derives the repo-derived counts locally,
and the suite-enforced freshness check fails until the page is
re-rendered — the same discipline as the reproduction board and the
community table.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Mapping

#: Snapshot schema version; bump on any breaking change to the field set.
TRUST_SCHEMA = "trust-indicators/v1"

#: Exactly the keys the ``repo`` section may carry (tree-derived counts).
REPO_FIELDS = (
    "as_of_commit",
    "reproduction_attempts_total",
    "externally_reproduced_total",
    "community_submissions_total",
)

#: Exactly the keys the ``github`` section may carry (fetched counts).
GITHUB_FIELDS = (
    "repository",
    "as_of",
    "issues_total",
    "issues_from_strangers",
    "pulls_total",
    "pulls_from_strangers",
)

#: Exactly the keys the ``citations`` section may carry.
CITATION_FIELDS = ("source", "arxiv_id", "as_of", "count", "note")

#: The only citation source the fetch layer knows how to read.
CITATION_SOURCES = ("semanticscholar",)

#: Login suffix that marks automation (GitHub App / bot accounts).
BOT_SUFFIX = "[bot]"

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

#: Hard cap on API pagination (10 pages x 100 records): beyond it the
#: count is refused rather than truncated — a partial count is a wrong
#: count, and the fetch fails loudly instead.
MAX_PAGES = 10


class TrustError(ValueError):
    """Raised when the snapshot, a source config, or a record is malformed.

    A ``ValueError`` subclass on purpose, matching
    :class:`essun.evidence.reproductions.ReproductionError`.
    """


# ---------------------------------------------------------------------------
# snapshot schema
# ---------------------------------------------------------------------------


def _count_problems(section: str, field: str, value: Any) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return [f"trust: {section}.{field} must be a non-negative integer, got {value!r}"]
    return []


def _date_problems(section: str, field: str, value: Any) -> list[str]:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return [f"trust: {section}.{field} must be an ISO date (YYYY-MM-DD), got {value!r}"]
    return []


def _require_fields(record: Mapping, fields: tuple[str, ...], section: str) -> list[str]:
    missing = [field for field in fields if field not in record]
    if missing:
        return [f"trust: {section} missing field(s): {', '.join(missing)}"]
    unknown = [key for key in record if key not in fields]
    if unknown:
        return [f"trust: {section} unknown field(s): {', '.join(sorted(unknown))}"]
    return []


def snapshot_problems(document: Any) -> list[str]:
    """All structural problems of a trust snapshot.

    Empty problems means the snapshot is valid.  Besides exact field
    sets, the cross-field honesty rules live here: stranger counts may
    not exceed totals, and a citation count may not exist without a
    configured paper (``arxiv_id``) to count from.
    """
    if not isinstance(document, Mapping):
        return ["trust: snapshot must be a mapping"]
    if document.get("schema") != TRUST_SCHEMA:
        return [f"trust: schema must be {TRUST_SCHEMA!r}, got {document.get('schema')!r}"]
    unknown = [key for key in document if key not in ("schema", "repo", "github", "citations")]
    if unknown:
        return [f"trust: unknown section(s): {', '.join(sorted(unknown))}"]
    problems: list[str] = []

    repo = document.get("repo")
    if not isinstance(repo, Mapping):
        problems.append("trust: repo must be a mapping")
    else:
        problems.extend(_require_fields(repo, REPO_FIELDS, "repo"))
        commit = repo.get("as_of_commit")
        if not isinstance(commit, str) or not _COMMIT_RE.match(commit or ""):
            problems.append(
                f"trust: repo.as_of_commit must be 40 lowercase hex characters, got {commit!r}"
            )
        for field in REPO_FIELDS[1:]:
            problems.extend(_count_problems("repo", field, repo.get(field)))

    github = document.get("github")
    if not isinstance(github, Mapping):
        problems.append("trust: github must be a mapping")
    else:
        problems.extend(_require_fields(github, GITHUB_FIELDS, "github"))
        repository = github.get("repository")
        if not isinstance(repository, str) or not _REPO_RE.match(repository or ""):
            problems.append(
                f"trust: github.repository must be owner/name, got {repository!r}"
            )
        problems.extend(_date_problems("github", "as_of", github.get("as_of")))
        for field in ("issues_total", "issues_from_strangers", "pulls_total", "pulls_from_strangers"):
            problems.extend(_count_problems("github", field, github.get(field)))
        if (
            isinstance(github.get("issues_total"), int)
            and isinstance(github.get("issues_from_strangers"), int)
            and github["issues_from_strangers"] > github["issues_total"]
        ):
            problems.append("trust: github.issues_from_strangers exceeds issues_total")
        if (
            isinstance(github.get("pulls_total"), int)
            and isinstance(github.get("pulls_from_strangers"), int)
            and github["pulls_from_strangers"] > github["pulls_total"]
        ):
            problems.append("trust: github.pulls_from_strangers exceeds pulls_total")

    citations = document.get("citations")
    if not isinstance(citations, Mapping):
        problems.append("trust: citations must be a mapping")
    else:
        problems.extend(_require_fields(citations, CITATION_FIELDS, "citations"))
        if citations.get("source") not in CITATION_SOURCES:
            problems.append(
                f"trust: citations.source must be one of {CITATION_SOURCES}, "
                f"got {citations.get('source')!r}"
            )
        arxiv_id = citations.get("arxiv_id")
        if arxiv_id is not None and (not isinstance(arxiv_id, str) or not arxiv_id):
            problems.append("trust: citations.arxiv_id must be null or a non-empty string")
        problems.extend(_date_problems("citations", "as_of", citations.get("as_of")))
        count = citations.get("count")
        if count is not None:
            problems.extend(_count_problems("citations", "count", count))
            if arxiv_id is None:
                problems.append(
                    "trust: citations.count may not be set while arxiv_id is null — "
                    "there is no public paper to count citations of (unknown is not zero)"
                )
        note = citations.get("note")
        if not isinstance(note, str) or not note:
            problems.append("trust: citations.note must be a non-empty string")
    return problems


def validate_snapshot(document: Any) -> None:
    """Validate a snapshot; raise :class:`TrustError` on any problem."""
    problems = snapshot_problems(document)
    if problems:
        raise TrustError("; ".join(problems))


def load_snapshot(path: Path | str) -> dict:
    """Parse and validate one snapshot YAML file, naming it on error."""
    path = Path(path)
    import yaml  # local import: stdlib-free module otherwise, like the store

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TrustError(f"{path.name}: unreadable ({error})") from error
    except yaml.YAMLError as error:
        raise TrustError(f"{path.name}: invalid YAML ({error})") from error
    try:
        validate_snapshot(document)
    except TrustError as error:
        raise TrustError(f"{path.name}: {error}") from error
    return dict(document)


def dump_snapshot(document: Mapping) -> str:
    """Deterministic YAML text for a snapshot (sorted keys, no host state)."""
    import yaml

    return yaml.safe_dump(dict(document), sort_keys=True, allow_unicode=False)


def load_sources(path: Path | str) -> dict:
    """Parse and validate ``experiments/trust/sources.yaml``.

    Two keys: ``github_repository`` (owner/name) and ``arxiv_id`` (null
    until the owner records the published paper's id — a one-line config
    edit, the only human input the dashboard accepts, and it is a
    pointer, never a number).
    """
    path = Path(path)
    import yaml

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise TrustError(f"{path.name}: unreadable ({error})") from error
    except yaml.YAMLError as error:
        raise TrustError(f"{path.name}: invalid YAML ({error})") from error
    if not isinstance(document, Mapping):
        raise TrustError(f"{path.name}: must be a mapping of source pointers")
    missing = [k for k in ("github_repository", "arxiv_id") if k not in document]
    if missing:
        raise TrustError(f"{path.name}: missing field(s): {', '.join(missing)}")
    unknown = [k for k in document if k not in ("schema", "github_repository", "arxiv_id")]
    if unknown:
        raise TrustError(f"{path.name}: unknown field(s): {', '.join(sorted(unknown))}")
    if "schema" in document and document["schema"] != "trust-sources/v1":
        raise TrustError(
            f"{path.name}: schema must be 'trust-sources/v1', got {document['schema']!r}"
        )
    repository = document["github_repository"]
    if not isinstance(repository, str) or not _REPO_RE.match(repository):
        raise TrustError(f"{path.name}: github_repository must be owner/name, got {repository!r}")
    arxiv_id = document["arxiv_id"]
    if arxiv_id is not None and (not isinstance(arxiv_id, str) or not arxiv_id):
        raise TrustError(f"{path.name}: arxiv_id must be null or a non-empty string")
    return dict(document)


# ---------------------------------------------------------------------------
# strangers and GitHub aggregation (pure; fixtures in tests)
# ---------------------------------------------------------------------------


def is_stranger(login: Any) -> bool:
    """Whether a GitHub login counts as a stranger.

    False for repository author identities (case-insensitive, leading
    ``@`` stripped — same floor as the reproduction gate) and for bot
    accounts (login ending ``[bot]``); True for everyone else, including
    a null login (a deleted account is not an author).
    """
    if not isinstance(login, str) or not login:
        return True
    name = login.lstrip("@").lower()
    if name.endswith(BOT_SUFFIX):
        return False
    from .reproductions import AUTHOR_IDENTITIES  # the single shared list

    return name not in AUTHOR_IDENTITIES


def aggregate_github(issues: list[Any], pulls: list[Any]) -> dict:
    """Count issues and pull requests, total and from strangers.

    ``issues`` is the REST ``/issues`` payload (which interleaves pull
    requests — entries carrying a ``pull_request`` key are excluded from
    the issue counts, they are counted from ``pulls`` instead); ``pulls``
    is the REST ``/pulls`` payload.  Pure and order-insensitive.
    """
    real_issues = [i for i in issues if isinstance(i, Mapping) and "pull_request" not in i]

    def logins(entries: list[Any]) -> list[Any]:
        values = []
        for entry in entries:
            user = entry.get("user") if isinstance(entry, Mapping) else None
            values.append(user.get("login") if isinstance(user, Mapping) else None)
        return values

    issue_logins = logins(real_issues)
    pull_logins = logins(pulls)
    return {
        "issues_total": len(issue_logins),
        "issues_from_strangers": sum(1 for x in issue_logins if is_stranger(x)),
        "pulls_total": len(pull_logins),
        "pulls_from_strangers": sum(1 for x in pull_logins if is_stranger(x)),
    }


# ---------------------------------------------------------------------------
# repo-derived counts (offline, deterministic)
# ---------------------------------------------------------------------------


def derive_repo(repo_root: Path | str, as_of_commit: str) -> dict:
    """The ``repo`` section, re-derived from the committed tree.

    Reproduction attempts load through the reproduction gate (an invalid
    or asserting record fails the derivation — the dashboard refuses to
    render over a record the board would refuse) and submissions through
    the community gate.  ``externally_reproduced_total`` counts
    :func:`effective_label` results, so it can only read nonzero through
    a gated adjudication — never by assertion.
    """
    from .reproductions import effective_label, load_reproduction_file
    from .submissions import load_submission_file

    root = Path(repo_root)
    attempts = 0
    external = 0
    records_dir = root / "experiments" / "reproductions"
    for path in sorted(records_dir.glob("*.yaml")) if records_dir.is_dir() else []:
        attempt, adjudication = load_reproduction_file(path)
        attempts += 1
        if effective_label(attempt, adjudication) == "EXTERNALLY_REPRODUCED":
            external += 1
    submissions = 0
    community_dir = root / "experiments" / "community"
    for path in sorted(community_dir.glob("*.yaml")) if community_dir.is_dir() else []:
        load_submission_file(path, at_door=False, repo_root=root)
        submissions += 1
    return {
        "as_of_commit": as_of_commit,
        "reproduction_attempts_total": attempts,
        "externally_reproduced_total": external,
        "community_submissions_total": submissions,
    }


def repo_drift(problems: list[str], derived: Mapping, snapshot: Mapping) -> None:
    """Append drift problems for tree-derived counts (in place).

    ``as_of_commit`` is provenance, not a count — it is deliberately not
    compared, or every commit after a fetch would look like drift.
    """
    for field in REPO_FIELDS[1:]:
        if derived.get(field) != snapshot.get("repo", {}).get(field):
            problems.append(
                f"trust: repo.{field} is {snapshot.get('repo', {}).get(field)!r} in the "
                f"snapshot but {derived.get(field)!r} in the tree — re-run "
                "tools/trust_dashboard.py"
            )


# ---------------------------------------------------------------------------
# render (pure, deterministic)
# ---------------------------------------------------------------------------


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_dashboard_rows(snapshot: Mapping) -> str:
    """Deterministic HTML for the indicator table, one ``<tr>`` per row.

    A pure function of the snapshot: no wall-clock, no host state, input
    order fixed by the row list below — two renders of the same snapshot
    are byte-identical, which is what the freshness check pins.  A null
    citation count renders UNKNOWN with its note, never a zero.
    """

    def value_cell(count: int, total: int | None = None) -> str:
        text = f"{count}"
        if total is not None:
            text += f' <span class="note">(of {total} total)</span>'
        return f'<td class="n">{text}</td>'

    def code_commit(commit: str) -> str:
        return f'<td><code>{_escape(commit[:12])}</code></td>'

    def date_cell(date: str) -> str:
        return f"<td>{_escape(date)}</td>"

    repo = snapshot["repo"]
    github = snapshot["github"]
    citations = snapshot["citations"]

    rows = [
        (
            'Reproduction attempts recorded <span class="note">(any outcome, '
            'nothing filtered)</span>',
            value_cell(repo["reproduction_attempts_total"]),
            code_commit(repo["as_of_commit"]),
            '<td>committed records — <a href="reproductions.html">the board</a></td>',
        ),
        (
            "Attempts adjudicated EXTERNALLY_REPRODUCED",
            f'<td class="n">{repo["externally_reproduced_total"]}</td>',
            code_commit(repo["as_of_commit"]),
            "<td>committed records — adjudications only</td>",
        ),
        (
            'Comparison submissions through the door <span class="note">'
            "(published and rejected alike)</span>",
            value_cell(repo["community_submissions_total"]),
            code_commit(repo["as_of_commit"]),
            '<td>committed records — <a href="community.html">the table</a></td>',
        ),
        (
            "Issues opened by strangers",
            value_cell(github["issues_from_strangers"], github["issues_total"]),
            date_cell(github["as_of"]),
            f'<td>GitHub API — <a href="https://github.com/{_escape(github["repository"])}/issues">{_escape(github["repository"])}</a></td>',
        ),
        (
            "Pull requests from strangers",
            value_cell(github["pulls_from_strangers"], github["pulls_total"]),
            date_cell(github["as_of"]),
            f'<td>GitHub API — <a href="https://github.com/{_escape(github["repository"])}/pulls">{_escape(github["repository"])}</a></td>',
        ),
    ]
    if citations["count"] is None:
        citation_value = (
            f'<td class="n"><span class="label label-unverified">UNKNOWN</span> '
            f'<span class="note">{_escape(citations["note"])}</span></td>'
        )
    else:
        citation_value = f'<td class="n">{citations["count"]}</td>'
    rows.append(
        (
            "Citations of the paper",
            citation_value,
            date_cell(citations["as_of"]),
            "<td>Semantic Scholar, keyed on the arXiv id</td>",
        )
    )

    lines = [
        '      <table class="board">',
        "        <thead>",
        "          <tr><th>Indicator</th><th>Value</th><th>As of</th><th>Source</th></tr>",
        "        </thead>",
        "        <tbody>",
    ]
    for indicator, value, as_of, source in rows:
        lines.append(
            "          <tr>"
            f"<th scope=\"row\">{indicator}</th>"
            f"{value}{as_of}{source}"
            "</tr>"
        )
    lines.append("        </tbody>")
    lines.append("      </table>")
    return "\n".join(lines) + "\n"
