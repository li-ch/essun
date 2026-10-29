"""Schema contracts for assumptions / infragraph / workload_ir (Q3 / G4, T004).

Closes the T004 coverage gap: the assumptions, infragraph, and workload_ir
examples had no JSON Schema, so 3 of 7 handoff examples were parse-only.
The three schemas were written at repo level (handoff fence), then
promoted unchanged into the handoff schema set on 2026-10-28 per ADR-0002
(D-032 item 8), then relocated back to repo level by D-035 stage S2 (the
handoff bundle leaves HEAD; ADR-0002 records the superseded placement).
The point of these contracts is that the REAL experiment inputs under
experiments/ validate, not just the toy examples — both directions are
tested here, plus one negative instance per schema rejected with an
actionable message.
"""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "schemas"  # ADR-0002 promotion; D-035 S2 repo-level move
EXAMPLES_DIR = REPO / "examples"

# Schema <-> example pairs (the other 4 pairs live in test_schemas.py).
REPO_PAIRS = [
    ("assumptions.schema.json", "assumptions.example.yaml"),
    ("infragraph.schema.json", "infragraph.example.yaml"),
    ("workload_ir.schema.json", "workload_ir.example.yaml"),
]

# Real experiment inputs each schema must cover (globbed so newly landed
# inputs of an existing dialect are picked up automatically).
REAL_INPUTS = {
    "assumptions.schema.json": [
        REPO / "experiments/vertical_slice/assumptions_l0.yaml",
        REPO / "experiments/vertical_slice/assumptions_l05.yaml",
        REPO / "experiments/vertical_slice/assumptions_tfc.yaml",
        REPO / "experiments/vertical_slice/assumptions_w3.yaml",
        REPO / "experiments/vertical_slice/assumptions_w5.yaml",
    ],
    "infragraph.schema.json": sorted((REPO / "experiments/topologies").glob("*.yaml")),
    "workload_ir.schema.json": sorted((REPO / "experiments/workloads").glob("*.yaml")),
}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def error_messages(schema: dict, instance: object) -> list[str]:
    """All validation error messages, with oneOf/anyOf branch contexts flattened.

    Draft 2020-12 reports keyword-combinator failures as one opaque message
    plus per-branch contexts; flattening keeps negative-test failures
    actionable (they name the missing field or the bad type).
    """
    validator = jsonschema.Draft202012Validator(schema)
    messages: list[str] = []
    for error in validator.iter_errors(instance):
        messages.append(error.message)
        for context in error.context:
            messages.append(context.message)
    return messages


@pytest.mark.parametrize("schema_name", [pair[0] for pair in REPO_PAIRS])
def test_schema_is_valid_draft202012(schema_name):
    jsonschema.Draft202012Validator.check_schema(load_schema(schema_name))


@pytest.mark.parametrize("schema_name,example_name", REPO_PAIRS)
def test_handoff_example_validates_against_repo_schema(schema_name, example_name):
    instance = yaml.safe_load(
        (EXAMPLES_DIR / example_name).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(load_schema(schema_name)).validate(instance)


@pytest.mark.parametrize(
    "schema_name,path",
    [
        (schema_name, path)
        for schema_name, paths in REAL_INPUTS.items()
        for path in paths
    ],
    ids=lambda p: p.name if isinstance(p, Path) else str(p),
)
def test_real_experiment_input_validates(schema_name, path):
    assert path.is_file(), f"declared real input is missing: {path}"
    instance = yaml.safe_load(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(load_schema(schema_name)).validate(instance)


# ---------------------------------------------------------------------------
# Negative instances: rejection must carry an actionable message.
# ---------------------------------------------------------------------------


def _reject(schema_name: str, instance: object, expected_substring: str) -> None:
    messages = error_messages(load_schema(schema_name), instance)
    assert messages, "expected validation to fail, but it passed"
    joined = "\n".join(messages)
    assert expected_substring in joined, (
        f"expected actionable message {expected_substring!r} not found in:\n{joined}"
    )


def test_assumptions_negative_missing_required_parameter():
    """An entry in neither dialect: missing registry `parameter` and handoff `assumption_id`."""
    instance = {
        "assumptions_id": "negative",
        "assumptions": [
            {
                "id": "A-NEG-1",
                "value": 1,
                "rationale": "negative test entry",
                "sensitivity": "none",
                "owner": "tests",
                "review": "PROPOSED",
            }
        ],
    }
    _reject("assumptions.schema.json", instance, "'parameter' is a required property")


def test_assumptions_negative_wrong_value_type():
    instance = {
        "assumptions_id": "negative",
        "assumptions": [
            {
                "id": "A-NEG-2",
                "parameter": "link.bytes_per_ns",
                "value": [64, 128],
                "rationale": "negative test entry",
                "sensitivity": "none",
                "owner": "tests",
                "review": "PROPOSED",
            }
        ],
    }
    _reject(
        "assumptions.schema.json",
        instance,
        "is not of type 'number', 'string'",
    )


def test_infragraph_negative_missing_topology_class():
    instance = {
        "topology_id": "neg_free_v0",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
    }
    _reject("infragraph.schema.json", instance, "'topology_class' is a required property")


def test_infragraph_negative_degenerate_ranks():
    instance = {
        "topology_id": "neg_free_v0",
        "topology_class": "unidirectional_ring",
        "ranks": 0,
    }
    _reject("infragraph.schema.json", instance, "is less than the minimum of 1")


def test_workload_ir_negative_missing_layers():
    instance = {
        "workload": "w1_dense_tp_decode",
        "model_name": "negative",
        "tp_size": 8,
        "steps": 3,
        "allreduce_bytes": 16384,
    }
    _reject("workload_ir.schema.json", instance, "'layers' is a required property")


def test_workload_ir_negative_collective_without_payload():
    """An AllReduce event without message_bytes is meaningless; must be rejected."""
    instance = {
        "workload_id": "WK-NEG",
        "trace_kind": "synthetic",
        "events": [
            {
                "id": "ar0",
                "type": "AllReduce",
                "depends_on": [],
                "participants": [0, 1],
            }
        ],
    }
    _reject("workload_ir.schema.json", instance, "'message_bytes' is a required property")


def test_workload_ir_negative_non_integer_bytes():
    instance = {
        "workload": "w2_dense_tp_prefill",
        "model_name": "negative",
        "tp_size": 8,
        "layers": 2,
        "chunks_per_layer": 2,
        "chunk_bytes": 16384.5,
    }
    _reject("workload_ir.schema.json", instance, "is not of type 'integer'")


def test_workload_ir_negative_w3_unknown_kind():
    """The W3 ladder extension is a closed enum: an unregistered MoE kind is rejected."""
    instance = {
        "workload": "w3_moe_alltoall",
        "model_name": "negative",
        "tp_size": 8,
        "layers": 2,
        "experts_per_layer": 4,
        "top_k": 2,
        "tokens_per_rank": 5,
        "token_bytes": 2048,
    }
    messages = error_messages(load_schema("workload_ir.schema.json"), instance)
    joined = "\n".join(messages)
    assert "is not one of" in joined


def test_workload_ir_negative_w3_float_token_bytes():
    instance = {
        "workload": "w3_moe_dispatch_combine",
        "model_name": "negative",
        "tp_size": 8,
        "layers": 2,
        "experts_per_layer": 4,
        "top_k": 2,
        "tokens_per_rank": 5,
        "token_bytes": 2048.5,
    }
    _reject("workload_ir.schema.json", instance, "is not of type 'integer'")


def test_workload_ir_negative_w5_unknown_kind():
    """The W5 ladder extension is a closed enum: an unregistered PD/KV kind is rejected."""
    instance = {
        "workload": "w5_kv_pd",
        "model_name": "negative",
        "tp_size": 8,
        "prefill_nodes": 2,
        "requests": 3,
        "chunks_per_request": 2,
        "chunk_bytes": 4096,
        "decode_steps": 3,
    }
    messages = error_messages(load_schema("workload_ir.schema.json"), instance)
    joined = "\n".join(messages)
    assert "is not one of" in joined


def test_workload_ir_negative_w5_float_chunk_bytes():
    instance = {
        "workload": "w5_pd_kv_prefill_decode",
        "model_name": "negative",
        "tp_size": 8,
        "prefill_nodes": 2,
        "requests": 3,
        "chunks_per_request": 2,
        "chunk_bytes": 4096.5,
        "decode_steps": 3,
    }
    _reject("workload_ir.schema.json", instance, "is not of type 'integer'")


def test_workload_ir_negative_w5_layers_is_ambiguous():
    """`layers` became kind-conditional at 1.1.0: still required for w1/w2/w3 (the pre-existing w1-missing-layers negative guards that direction) and FORBIDDEN on w5, where it is ambiguous input."""
    instance = {
        "workload": "w5_pd_kv_prefill_decode",
        "model_name": "negative",
        "tp_size": 8,
        "layers": 2,
        "prefill_nodes": 2,
        "requests": 3,
        "chunks_per_request": 2,
        "chunk_bytes": 4096,
        "decode_steps": 3,
    }
    messages = error_messages(load_schema("workload_ir.schema.json"), instance)
    assert messages, "expected validation to fail, but it passed"
    joined = "\n".join(messages)
    assert "layers" in joined
