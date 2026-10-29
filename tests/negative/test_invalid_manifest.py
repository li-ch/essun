"""Negative tests: invalid manifests and capability violations are rejected
explicitly, never silently downgraded (handoff AGENTS.md implementation rules).
"""

from pathlib import Path

import pytest
import yaml

from essun.contracts import ContractError, load_experiment_manifest
from essun.orchestrator import runs as orch

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"


def _write_variant(tmp_path, mutate):
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "variant.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_missing_seed_rejected(tmp_path):
    path = _write_variant(tmp_path, lambda data: data.pop("seed"))
    with pytest.raises(ContractError, match="seed"):
        load_experiment_manifest(path)


def test_empty_backends_rejected(tmp_path):
    path = _write_variant(tmp_path, lambda data: data.update(backends=[]))
    with pytest.raises(ContractError, match="backends"):
        load_experiment_manifest(path)


def test_invalid_evidence_level_rejected(tmp_path):
    path = _write_variant(
        tmp_path, lambda data: data.update(evidence_level_requested="E9")
    )
    with pytest.raises(ContractError, match="evidence_level_requested"):
        load_experiment_manifest(path)


def test_unknown_backend_rejected_at_execution(tmp_path):
    path = _write_variant(tmp_path, lambda data: data.update(backends=["ns3_l2"]))
    with pytest.raises(orch.ExecutionError, match="unknown backend"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_unsupported_observable_rejected_at_execution(tmp_path):
    # O-CREDIT requires credit semantics L0 explicitly does not model;
    # the run must fail loudly, not silently fake it.
    path = _write_variant(
        tmp_path,
        lambda data: data.update(observables=["O-CONSERVATION", "O-CREDIT"]),
    )
    with pytest.raises(orch.ExecutionError, match="O-CREDIT"):
        orch.run_experiment(path, results_root=tmp_path / "results")


def test_declared_input_hash_mismatch_rejected(tmp_path):
    def mutate(data):
        data["workload_ir"]["sha256"] = "0" * 64

    path = _write_variant(tmp_path, mutate)
    with pytest.raises(ContractError, match="sha256 mismatch"):
        orch.run_experiment(path, results_root=tmp_path / "results")
