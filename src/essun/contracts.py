"""Contract loading and validation against the draft schemas.

The schemas under schemas/ are draft contracts (promoted into one
authoritative set by ADR-0002, now at repo level per the public-tree
structure decision). This module
is the single place that knows where they live and how inputs are resolved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"  # back at repo level (ADR-0002 note)

# Roles the experiment manifest must reference (experiment.schema.json).
INPUT_ROLES = (
    "workload_ir",
    "infra_graph",
    "standard_profile",
    "implementation_profile",
    "assumptions",
)


class ContractError(Exception):
    """Raised when an input violates a schema or a provenance contract."""


def load_yaml(path: Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_experiment_manifest(manifest: Any, source: str = "") -> None:
    schema = load_schema("experiment.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    issues = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))
    if issues:
        detail = "; ".join(
            f"{'/'.join(map(str, issue.path)) or '<root>'}: {issue.message}"
            for issue in issues
        )
        raise ContractError(
            f"experiment manifest {source} failed schema validation: {detail}"
        )


def load_experiment_manifest(path: Path) -> dict:
    path = Path(path)
    manifest = load_yaml(path)
    if not isinstance(manifest, dict):
        raise ContractError(f"experiment manifest {path} is not a mapping")
    validate_experiment_manifest(manifest, source=str(path))
    return manifest


def resolve_inputs(manifest: dict, base: Path = REPO_ROOT) -> dict[str, dict]:
    """Resolve and hash the manifest's input references.

    Returns ``{role: {"path": Path, "sha256": str, "declared_sha256": str|None}}``.
    Raises ContractError when a declared sha256 does not match the file on disk.
    """
    resolved: dict[str, dict] = {}
    for role in INPUT_ROLES:
        ref = manifest[role]
        path = Path(base) / ref["path"]
        if not path.is_file():
            raise ContractError(f"{role} input not found: {path}")
        actual = sha256_of(path)
        declared = ref.get("sha256")
        if declared is not None and declared != actual:
            raise ContractError(
                f"{role} sha256 mismatch for {path}: declared {declared}, actual {actual}"
            )
        resolved[role] = {"path": path, "sha256": actual, "declared_sha256": declared}
    return resolved
