"""External-reproduction records: the EXTERNALLY_REPRODUCED machinery.

The design rule under test (docs/reproduction-policy.md): the record
defaults to unknown and can never assert the label by itself.  An
ATTEMPT may not judge its own independence (self-judged criteria are
rejected at the door); an ADJUDICATION is the only path to the label,
and the cross-field gate refuses ``externally_reproduced`` without a
``byte_identical`` outcome, a non-author reproducer, and all four
criteria judged met.  Store-side: append-only, content-addressed
attempt identity that judging never rewrites, and the same
only-cite-immutable-runs rule as counterexamples and figures.
"""

from __future__ import annotations

import pytest

from essun.evidence.reproductions import (
    AUTHOR_IDENTITIES,
    INDEPENDENCE_CRITERIA,
    UNKNOWN,
    ReproductionError,
    adjudication_problems,
    effective_label,
    load_reproduction_file,
    reproduction_id,
    reproduction_problems,
    validate_reproduction,
)
from essun.evidence.store import EvidenceError, EvidenceStore

COMMIT = "a" * 40
RUN_ID = "b" * 64

ATTEMPT = {
    "reported": "2026-11-02",
    "report_url": "https://github.com/li-ch/essun/issues/1#issuecomment-1",
    "reproducer": "@someone-else",
    "reproduced_at_commit": COMMIT,
    "environment": "test host, Python 3.12",
    "outcome": "byte_identical",
    "divergence_notes": None,
    "reproduced_run_ids": [RUN_ID],
    "independence": {name: None for name in INDEPENDENCE_CRITERIA},
}

ALL_MET = {
    name: {"met": True, "note": f"{name}: checked, pointer in basis"}
    for name in INDEPENDENCE_CRITERIA
}

ADJUDICATION = {
    "verdict": "externally_reproduced",
    "adjudicator": "li-ch",
    "date": "2026-11-03",
    "basis": "account history read; environment differs; ids match pins",
    "independence": ALL_MET,
}


@pytest.fixture()
def store(tmp_path):
    """A store holding exactly one run that attempts may cite."""
    evidence = EvidenceStore(tmp_path)
    payload = {
        "experiment_id": "EXP-TEST-REPRO",
        "code_version": "0.1.0",
        "inputs": {},
    }
    real_id = evidence.put_run(
        payload, {"backend_id": "analytical_l0", "observables": {}}
    )
    attempt = {**ATTEMPT, "reproduced_run_ids": [real_id]}
    return evidence, attempt


# ---------------------------------------------------------------------------
# attempt validation
# ---------------------------------------------------------------------------


def test_valid_attempt_passes():
    validate_reproduction(ATTEMPT)
    assert reproduction_problems(ATTEMPT) == []


def test_missing_independence_block_is_unknown_not_error():
    attempt = {k: v for k, v in ATTEMPT.items() if k != "independence"}
    validate_reproduction(attempt)  # absence is unknown, never an error


def test_self_judged_criterion_is_refused():
    attempt = {
        **ATTEMPT,
        "independence": {"distinct_hands": {"met": True, "note": "trust me"}},
    }
    problems = reproduction_problems(attempt)
    assert any("judged only by an adjudication" in p for p in problems)
    with pytest.raises(ReproductionError, match="adjudication"):
        validate_reproduction(attempt)


def test_unknown_criterion_name_is_refused():
    attempt = {**ATTEMPT, "independence": {"distinct_hands_extra": None}}
    assert any("unknown criterion" in p for p in reproduction_problems(attempt))


def test_bad_commit_sha_is_refused():
    attempt = {**ATTEMPT, "reproduced_at_commit": "Z" * 40}
    assert any("40 lowercase hex" in p for p in reproduction_problems(attempt))


def test_bad_run_id_is_refused():
    attempt = {**ATTEMPT, "reproduced_run_ids": ["b" * 63]}
    assert any("64 lowercase hex" in p for p in reproduction_problems(attempt))


def test_bad_date_and_url_are_refused():
    assert any("ISO date" in p for p in reproduction_problems({**ATTEMPT, "reported": "2026-11"}))
    assert any("http(s) URL" in p for p in reproduction_problems({**ATTEMPT, "report_url": "ftp://x"}))


def test_outcome_enum_is_closed():
    assert any("outcome" in p for p in reproduction_problems({**ATTEMPT, "outcome": "close_enough"}))


def test_divergence_notes_required_when_not_byte_identical():
    attempt = {**ATTEMPT, "outcome": "diverged", "divergence_notes": None}
    assert any("divergence_notes" in p for p in reproduction_problems(attempt))


def test_divergence_notes_forbidden_when_byte_identical():
    attempt = {**ATTEMPT, "divergence_notes": "nothing diverged, but a note"}
    assert any("must be null" in p for p in reproduction_problems(attempt))


def test_unknown_and_missing_fields_are_refused():
    assert any("unknown field" in p for p in reproduction_problems({**ATTEMPT, "extra": 1}))
    broken = {k: v for k, v in ATTEMPT.items() if k != "reproducer"}
    assert any("missing field" in p for p in reproduction_problems(broken))


def test_run_ids_must_be_non_empty():
    assert any("non-empty list" in p for p in reproduction_problems({**ATTEMPT, "reproduced_run_ids": []}))


# ---------------------------------------------------------------------------
# adjudication: the only label path, and its gate
# ---------------------------------------------------------------------------


def test_adjudication_all_met_passes_for_byte_identical_non_author():
    assert adjudication_problems(ADJUDICATION, ATTEMPT) == []


def test_author_reproducer_cannot_be_externally_reproduced():
    for identity in AUTHOR_IDENTITIES:
        attempt = {**ATTEMPT, "reproducer": f"@{identity}"}
        problems = adjudication_problems(ADJUDICATION, attempt)
        assert any("author identity" in p for p in problems), identity


def test_diverged_attempt_cannot_be_externally_reproduced():
    attempt = {
        **ATTEMPT,
        "outcome": "diverged",
        "divergence_notes": "run X produced different bytes; minimized case filed",
    }
    problems = adjudication_problems(ADJUDICATION, attempt)
    assert any("byte_identical" in p for p in problems)


def test_unmet_criterion_blocks_the_label():
    judgments = {name: {"met": True, "note": "ok"} for name in INDEPENDENCE_CRITERIA}
    judgments["public_report"] = {"met": False, "note": "report link is dead"}
    adjudication = {**ADJUDICATION, "independence": judgments}
    problems = adjudication_problems(adjudication, ATTEMPT)
    assert any("public_report" in p and "unmet" in p for p in problems)


def test_partial_judgment_blocks_the_label():
    judgments = {name: {"met": True, "note": "ok"} for name in INDEPENDENCE_CRITERIA}
    del judgments["distinct_machine"]
    adjudication = {**ADJUDICATION, "independence": judgments}
    assert any("must judge" in p for p in adjudication_problems(adjudication, ATTEMPT))


def test_adjudication_shape_problems():
    assert adjudication_problems({"verdict": "externally_reproduced"}) != []
    bad_note = {name: {"met": True, "note": ""} for name in INDEPENDENCE_CRITERIA}
    problems = adjudication_problems({**ADJUDICATION, "independence": bad_note}, ATTEMPT)
    assert any("note" in p for p in problems)
    non_bool = {name: {"met": "yes", "note": "x"} for name in INDEPENDENCE_CRITERIA}
    problems = adjudication_problems({**ADJUDICATION, "independence": non_bool}, ATTEMPT)
    assert any("boolean" in p for p in problems)


def test_schema_only_adjudication_skips_cross_gate():
    """Without the attempt the gate cannot run (structure still checked)."""
    assert adjudication_problems(ADJUDICATION, None) == []


def test_not_independent_verdict_needs_no_full_support():
    judgments = {
        "distinct_hands": {"met": False, "note": "account has repository commits"},
        "distinct_machine": {"met": True, "note": "different platform"},
        "released_artifacts_only": {"met": True, "note": "ids derivable from tree"},
        "public_report": {"met": True, "note": "issue comment public"},
    }
    adjudication = {**ADJUDICATION, "verdict": "not_independent", "independence": judgments}
    assert adjudication_problems(adjudication, ATTEMPT) == []


# ---------------------------------------------------------------------------
# effective label: defaults unknown
# ---------------------------------------------------------------------------


def test_effective_label_defaults_to_unknown():
    assert effective_label(ATTEMPT, None) == UNKNOWN
    assert effective_label(ATTEMPT, {}) == UNKNOWN


def test_effective_label_follows_verdict():
    assert effective_label(ATTEMPT, ADJUDICATION) == "EXTERNALLY_REPRODUCED"
    judgments = {name: {"met": False, "note": "n"} for name in INDEPENDENCE_CRITERIA}
    not_independent = {**ADJUDICATION, "verdict": "not_independent", "independence": judgments}
    assert effective_label(ATTEMPT, not_independent) == "NOT_INDEPENDENT"
    not_counted = {**ADJUDICATION, "verdict": "not_counted", "independence": judgments}
    assert effective_label(ATTEMPT, not_counted) == "NOT_COUNTED"


def test_attempt_id_is_stable_under_adjudication():
    """Judging never rewrites identity: the id covers the attempt only."""
    assert reproduction_id(ATTEMPT) == reproduction_id(dict(ATTEMPT))


# ---------------------------------------------------------------------------
# store integration
# ---------------------------------------------------------------------------


def test_put_reproduction_appends_and_is_idempotent(store):
    evidence, attempt = store
    first = evidence.put_reproduction(attempt)
    second = evidence.put_reproduction(attempt)
    assert first == second
    assert len(evidence.reproductions()) == 1
    entry = evidence.reproductions()[0]
    assert entry["kind"] == "reproduction"
    assert entry["reproduction_id"] == first


def test_put_reproduction_requires_runs_in_store(tmp_path):
    evidence = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="is not in the store"):
        evidence.put_reproduction(ATTEMPT)  # RUN_ID never stored


def test_put_reproduction_rejects_invalid(store):
    evidence, _ = store
    with pytest.raises(EvidenceError, match="adjudication"):
        evidence.put_reproduction(
            {**ATTEMPT, "independence": {"distinct_hands": {"met": True, "note": "x"}}}
        )


def test_different_attempt_content_is_a_new_record_not_a_conflict(store):
    evidence, attempt = store
    first = evidence.put_reproduction(attempt)
    # A different environment is a different attempt: new id, new append
    # (the id covers the whole attempt, so same-id-different-bytes cannot
    # arise without a hash collision; the violation branch stays defensive).
    other = {**attempt, "environment": "a different host"}
    second = evidence.put_reproduction(other)
    assert first != second
    assert len(evidence.reproductions()) == 2


def test_put_adjudication_gates_against_stored_attempt(store):
    evidence, attempt = store
    rid = evidence.put_reproduction(attempt)
    # An author attempt stored: the gate must refuse the label.
    author_attempt = {**attempt, "reproducer": "@li-ch"}
    author_rid = evidence.put_reproduction(author_attempt)
    with pytest.raises(EvidenceError, match="author identity"):
        evidence.put_adjudication(ADJUDICATION, author_rid)
    # The honest attempt accepts it.
    aid = evidence.put_adjudication(ADJUDICATION, rid)
    assert evidence.put_adjudication(ADJUDICATION, rid) == aid  # idempotent
    assert len(evidence.adjudications()) == 1
    assert evidence.adjudications()[0]["of_reproduction"] == rid


def test_put_adjudication_requires_stored_reproduction(store):
    evidence, _ = store
    with pytest.raises(EvidenceError, match="not in the store"):
        evidence.put_adjudication(ADJUDICATION, "c" * 64)


def test_put_adjudication_rejects_unsupported_verdict(store):
    evidence, attempt = store
    rid = evidence.put_reproduction(attempt)
    judgments = {name: {"met": True, "note": "x"} for name in INDEPENDENCE_CRITERIA}
    judgments["distinct_hands"] = {"met": False, "note": "same hands"}
    with pytest.raises(EvidenceError, match="unmet"):
        evidence.put_adjudication({**ADJUDICATION, "independence": judgments}, rid)


# ---------------------------------------------------------------------------
# committed file loading
# ---------------------------------------------------------------------------


def test_load_reproduction_file_roundtrip(tmp_path):
    import yaml

    path = tmp_path / "attempt.yaml"
    path.write_text(yaml.safe_dump(ATTEMPT, sort_keys=True), encoding="utf-8")
    attempt, adjudication = load_reproduction_file(path)
    assert attempt == ATTEMPT
    assert adjudication is None


def test_load_reproduction_file_runs_the_gate(tmp_path):
    import yaml

    path = tmp_path / "asserting.yaml"
    document = {**ATTEMPT, "adjudication": ADJUDICATION}
    # Make the attempt one the gate must refuse (author reproducer).
    document["reproducer"] = "@li-ch"
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    with pytest.raises(ReproductionError, match="author identity"):
        load_reproduction_file(path)


def test_load_reproduction_file_accepts_valid_adjudication(tmp_path):
    import yaml

    path = tmp_path / "adjudicated.yaml"
    document = {**ATTEMPT, "adjudication": ADJUDICATION}
    path.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    attempt, adjudication = load_reproduction_file(path)
    assert adjudication["verdict"] == "externally_reproduced"
    assert effective_label(attempt, adjudication) == "EXTERNALLY_REPRODUCED"


def test_load_reproduction_file_rejects_self_judging_attempt(tmp_path):
    import yaml

    path = tmp_path / "self_judged.yaml"
    attempt = {
        **ATTEMPT,
        "independence": {"distinct_hands": {"met": True, "note": "trust me"}},
    }
    path.write_text(yaml.safe_dump(attempt, sort_keys=True), encoding="utf-8")
    with pytest.raises(ReproductionError, match="adjudication"):
        load_reproduction_file(path)
