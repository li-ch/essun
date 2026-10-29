"""Determinism: identical manifest, inputs and code version must produce
byte-identical run artifacts (handoff AGENTS.md determinism rules).

Increment 5a extends the replay proof beyond the original W1-on-ring slice:
the W2 prefill manifest (phase collectives on the NON-RING exchange fabric —
non-ring AND non-W1) and the W1 torus manifest (non-ring) must replay
byte-identically through the dispatched run path too.
"""

from pathlib import Path

from essun.orchestrator.runs import run_experiment

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml"
W2_MANIFEST = REPO / "experiments" / "vertical_slice" / "w2_prefill_smoke.yaml"
TORUS_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_torus2d.yaml"


def test_two_runs_produce_identical_artifacts(tmp_path):
    first = run_experiment(MANIFEST, results_root=tmp_path / "a")
    second = run_experiment(MANIFEST, results_root=tmp_path / "b")

    assert first["run_id"] == second["run_id"]
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right, f"{artifact} differs between identical replays"


def test_non_ring_non_w1_manifest_replays_byte_identical(tmp_path):
    # W2 prefill on the exchange fabric (doubling phases): neither the
    # original ring topology nor the W1 workload.
    first = run_experiment(W2_MANIFEST, results_root=tmp_path / "a")
    second = run_experiment(W2_MANIFEST, results_root=tmp_path / "b")

    assert first["run_id"] == second["run_id"]
    assert first["observations"]["backend_id"] == "analytical_l0_phase_collectives"
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right, f"{artifact} differs between identical W2 replays"


def test_non_ring_manifest_replays_byte_identical(tmp_path):
    # W1 on the 2D torus through the dispatched run path.
    first = run_experiment(TORUS_MANIFEST, results_root=tmp_path / "a")
    second = run_experiment(TORUS_MANIFEST, results_root=tmp_path / "b")

    assert first["run_id"] == second["run_id"]
    assert first["observations"]["backend_id"] == "analytical_l0_torus2d"
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right, f"{artifact} differs between identical torus replays"


def test_run_record_contains_provenance(tmp_path):
    result = run_experiment(MANIFEST, results_root=tmp_path)
    import json

    run = json.loads((result["run_dir"] / "run.json").read_text(encoding="utf-8"))
    assert run["code_version"]
    assert set(run["inputs"]) == {
        "workload_ir",
        "infra_graph",
        "standard_profile",
        "implementation_profile",
        "assumptions",
    }
    assert all(len(info["sha256"]) == 64 for info in run["inputs"].values())
    observations = json.loads(
        (result["run_dir"] / "observations.json").read_text(encoding="utf-8")
    )
    assert observations["observables"]["O-CONSERVATION"]["violations"] == 0
