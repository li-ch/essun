"""Schema contract for external-reproduction records.

``schemas/reproduction.schema.json`` is the shape of a committed
transcription (``experiments/reproductions/*.yaml``, example:
``examples/reproduction.example.yaml``).  The schema deliberately covers
SHAPE only: the cross-field gates — an adjudication verdict of
``externally_reproduced`` requires a ``byte_identical`` outcome, a
non-author reproducer, and all four criteria judged met; an attempt may
not judge any criterion itself — live in
``essun.evidence.reproductions`` (tests/evidence/test_reproductions.py),
where the attempt is available to check against.  What the schema DOES
freeze: an attempt's ``independence`` entries are ``null``-typed, so a
self-judging attempt is not even schema-valid.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "schemas" / "reproduction.schema.json"
EXAMPLE = REPO / "examples" / "reproduction.example.yaml"


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def error_messages(instance: object) -> list[str]:
    messages: list[str] = []
    for error in jsonschema.Draft202012Validator(load_schema()).iter_errors(instance):
        messages.append(error.message)
        for context in error.context:
            messages.append(context.message)
    return messages


def _reject(instance: object, expected_substring: str) -> None:
    messages = error_messages(instance)
    assert messages, "expected validation to fail, but it passed"
    joined = "\n".join(messages)
    assert expected_substring in joined, (
        f"expected actionable message {expected_substring!r} not found in:\n{joined}"
    )


def valid_document() -> dict:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def test_schema_is_valid_draft202012():
    jsonschema.Draft202012Validator.check_schema(load_schema())


def test_example_validates():
    jsonschema.Draft202012Validator(load_schema()).validate(valid_document())


def test_example_is_an_attempt_not_a_claim():
    """The shipped example asserts nothing: no adjudication, all criteria null."""
    document = valid_document()
    assert "adjudication" not in document
    assert set(document["independence"]) == {
        "distinct_hands",
        "distinct_machine",
        "released_artifacts_only",
        "public_report",
    }
    assert all(value is None for value in document["independence"].values())


def test_negative_self_judging_attempt():
    document = valid_document()
    document["independence"]["distinct_hands"] = {"met": True, "note": "trust me"}
    _reject(document, "is not of type 'null'")


def test_negative_missing_required_field():
    document = valid_document()
    del document["report_url"]
    _reject(document, "'report_url' is a required property")


def test_negative_bad_commit_shape():
    document = valid_document()
    document["reproduced_at_commit"] = "cb7f9fc"  # short form is not enough
    _reject(document, "does not match")


def test_negative_bad_run_id():
    document = valid_document()
    document["reproduced_run_ids"] = ["not-a-run-id"]
    _reject(document, "does not match")


def test_negative_bad_outcome():
    document = valid_document()
    document["outcome"] = "close_enough"
    _reject(document, "is not one of")


def test_negative_empty_run_list():
    document = valid_document()
    document["reproduced_run_ids"] = []
    _reject(document, "should be non-empty")


def test_negative_adjudication_missing_judgment():
    document = valid_document()
    judgments = {
        name: {"met": True, "note": "checked"} for name in (
            "distinct_hands", "distinct_machine", "released_artifacts_only",
        )
    }
    document["adjudication"] = {
        "verdict": "not_independent",
        "adjudicator": "li-ch",
        "date": "2026-11-03",
        "basis": "example negative",
        "independence": judgments,
    }
    _reject(document, "'public_report' is a required property")


def test_negative_adjudication_judgment_without_note():
    document = valid_document()
    judgments = {
        name: {"met": True} for name in (
            "distinct_hands", "distinct_machine",
            "released_artifacts_only", "public_report",
        )
    }
    document["adjudication"] = {
        "verdict": "not_counted",
        "adjudicator": "li-ch",
        "date": "2026-11-03",
        "basis": "example negative",
        "independence": judgments,
    }
    _reject(document, "'note' is a required property")
