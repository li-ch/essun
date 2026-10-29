"""Schema and example validation (task T004 increment).

Mirrors the structural checks the handoff verifier performed so drift is
caught in `make test` / CI, not only at bundle verification (the bundle
itself leaves HEAD in the D-035 cleanup; the checks stay).
"""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "schemas"  # D-035 S2: repo level (ADR-0002 note)
EXAMPLES_DIR = REPO / "examples"

PAIRS = [
    ("specir.schema.json", "specir.example.yaml"),
    ("experiment.schema.json", "experiment.example.yaml"),
    ("source.schema.json", "source.example.yaml"),
    ("evidence.schema.json", "evidence.example.yaml"),
]


@pytest.mark.parametrize("schema_name", [pair[0] for pair in PAIRS])
def test_schema_is_valid_draft202012(schema_name):
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    "example_path", sorted(EXAMPLES_DIR.glob("*.yaml")), ids=lambda p: p.name
)
def test_example_parses(example_path):
    assert yaml.safe_load(example_path.read_text(encoding="utf-8")) is not None


@pytest.mark.parametrize("schema_name,example_name", PAIRS)
def test_example_validates_against_schema(schema_name, example_name):
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    instance = yaml.safe_load((EXAMPLES_DIR / example_name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(instance)
