"""T022 stage S2 execution tests: container run -> parse -> RunRecord.

The parse tests run against the recorded stdout of a REAL execution of the
W1 smoke manifest in the pinned container (fixture
``tests/fixtures/astra_sim/w1_smoke_8rank_stdout.txt``, provenance in its
README) — so the parser is pinned to the binary's actual output, not to a
hand-written fantasy of it. The run/record path is exercised with the
container invocation replayed from that fixture (no Docker needed in CI);
the real-container execution is additionally verified by the determinism
spot-check recorded in the S2 stage report (two fresh containers, identical
numbers, idempotent evidence-store put).
"""

import json
from pathlib import Path

import pytest
import yaml

from essun.backends.astra_sim import adapter
from essun.orchestrator.runs import BACKENDS, ExecutionError, run_experiment

REPO = Path(__file__).resolve().parents[2]
ASTRA_MANIFEST = (
    REPO / "experiments" / "vertical_slice" / "w1_decode_smoke_astra.yaml"
)
FIXTURES = REPO / "tests" / "fixtures" / "astra_sim"
REAL_STDOUT = (FIXTURES / "w1_smoke_8rank_stdout.txt").read_text(encoding="utf-8")

# Hand-derived from the executed free parameters (ring8_free_params.yaml,
# w1_dense_tp_decode_small.yaml) and the pinned binary's deterministic run.
RANKS = 8
OPS_PER_RANK = 6
REAL_WALL_TIME = 144288  # ns per rank; whole 6-op chain, all ranks equal


# --- parse: golden against the real recorded output -------------------------


def test_parse_real_w1_smoke_output():
    parsed = adapter.parse_output(REAL_STDOUT, exit_code=0, ranks=RANKS)
    assert parsed["completion_time_ns"] == REAL_WALL_TIME
    assert len(parsed["per_rank"]) == RANKS
    for entry in parsed["per_rank"]:
        assert entry["wall_time_ns"] == REAL_WALL_TIME
        assert entry["comm_time_ns"] == REAL_WALL_TIME
        assert entry["finished_cycles"] == REAL_WALL_TIME
        assert entry["exposed_comm_cycles"] == REAL_WALL_TIME
    # ns units carried from the pin (EventTime, common/Type.h).
    assert "ns" in parsed["units"]


# --- parse: every failure mode rejected with the gap named ------------------


def _minimal_output(**overrides) -> str:
    lines = [f"ESSUN_BINARY_SHA256={adapter.PIN['binary_sha256']}"]
    for rank in range(RANKS):
        lines += [
            f"[2026-10-27 00:00:00.000] [workload] [info] sys[{rank}] finished, "
            f"{REAL_WALL_TIME} cycles, exposed communication {REAL_WALL_TIME} cycles.",
            f"[2026-10-27 00:00:00.000] [statistics] [info] sys[{rank}], "
            f"Wall time: {REAL_WALL_TIME}",
            f"[2026-10-27 00:00:00.000] [statistics] [info] sys[{rank}], "
            f"Comm time: {REAL_WALL_TIME}",
        ]
    lines.append("ASTRA_EXIT=0")
    return "\n".join(overrides.get("extra", []) + lines)


def test_parse_rejects_container_failure():
    with pytest.raises(adapter.AdapterError, match="exited with code 1"):
        adapter.parse_output(_minimal_output(), exit_code=1, ranks=RANKS)


def test_parse_rejects_simulator_failure():
    text = _minimal_output().replace("ASTRA_EXIT=0", "ASTRA_EXIT=134")
    with pytest.raises(adapter.AdapterError, match=r"exited with code 134"):
        adapter.parse_output(text, exit_code=0, ranks=RANKS)


def test_parse_rejects_unpinned_binary():
    text = _minimal_output().replace(
        f"ESSUN_BINARY_SHA256={adapter.PIN['binary_sha256']}",
        "ESSUN_BINARY_SHA256=" + "0" * 64,
    )
    with pytest.raises(adapter.AdapterError, match="unpinned binary"):
        adapter.parse_output(text, exit_code=0, ranks=RANKS)


def test_parse_rejects_critical_lines_even_with_exit_zero():
    # The S2 counterexample shape: without local-mem-bw the run "finishes"
    # with exit 0 but logs unreleased-nodes criticals — parse must refuse.
    text = _minimal_output(
        extra=["[2026-10-27 00:00:00.000] [HardwareResource] [critical] "
               "!!!Hardware Resource sys.id=0 has unreleased nodes!!!"]
    )
    with pytest.raises(adapter.AdapterError, match=r"critical.*unreleased"):
        adapter.parse_output(text, exit_code=0, ranks=RANKS)


def test_parse_rejects_missing_rank():
    lines = _minimal_output().splitlines()
    # drop rank 0's three lines (they precede rank 1's)
    kept = [l for l in lines if "sys[0]" not in l]
    with pytest.raises(adapter.AdapterError, match=r"no result lines.*\[0\]"):
        adapter.parse_output("\n".join(kept), exit_code=0, ranks=RANKS)


def test_parse_rejects_rank_out_of_range():
    text = _minimal_output().replace("sys[0]", "sys[8]")
    with pytest.raises(adapter.AdapterError, match="outside declared ranks"):
        adapter.parse_output(text, exit_code=0, ranks=RANKS)


def test_parse_rejects_duplicate_rank_lines():
    lines = _minimal_output().splitlines()
    dup = [l for l in lines if ", Wall time:" in l and "sys[1]" in l][0]
    with pytest.raises(adapter.AdapterError, match="twice"):
        adapter.parse_output(_minimal_output() + "\n" + dup, exit_code=0, ranks=RANKS)


def test_parse_rejects_wall_below_comm():
    text = _minimal_output().replace("sys[2], Wall time: 144288", "sys[2], Wall time: 1")
    with pytest.raises(adapter.AdapterError, match="Wall time < Comm time"):
        adapter.parse_output(text, exit_code=0, ranks=RANKS)


def test_parse_rejects_missing_sha_marker():
    lines = _minimal_output().splitlines()[1:]  # drop the sha preamble line
    with pytest.raises(adapter.AdapterError, match="ESSUN_BINARY_SHA256 marker"):
        adapter.parse_output("\n".join(lines), exit_code=0, ranks=RANKS)


# --- execute_experiment with the container replayed from the fixture --------


@pytest.fixture
def replay_container(monkeypatch):
    """Replay the recorded real container output; capture the compiled
    inputs so tests can additionally assert on what was executed."""
    calls = []

    def fake_run_container(inputs_dir, workload_prefix, ranks):
        calls.append(
            {
                "inputs_dir": Path(inputs_dir),
                "workload_prefix": workload_prefix,
                "ranks": ranks,
            }
        )
        return {"exit_code": 0, "stdout": REAL_STDOUT}

    monkeypatch.setattr(adapter, "docker_run_container", fake_run_container)
    return calls


def test_execute_experiment_observations_and_provenance(replay_container):
    out = adapter.execute_experiment(ASTRA_MANIFEST)
    obs = out["observations"]
    assert obs["backend_id"] == "astra_sim_analytical"
    assert obs["model"]["ranks"] == RANKS
    assert obs["model"]["link_bytes_per_ns_exact"] == "64"
    assert obs["model"]["hop_latency_ns_exact"] == "200"
    # O-CCT: parsed, honestly labeled as such (registry kind: analytical).
    occt = obs["observables"]["O-CCT"]
    assert occt["kind"] == "analytical"
    assert "parsed" in occt["method"]
    assert occt["ops"] == OPS_PER_RANK
    assert occt["completion_time_ns"] == REAL_WALL_TIME
    # O-CONSERVATION: honest unsupported record, not a silent omission.
    assert "O-CONSERVATION" in obs["unsupported_observables"]
    assert "byte accounting" in obs["unsupported_observables"]["O-CONSERVATION"]
    # Execution provenance: pin identity, verified markers, parsed values.
    execution = out["execution"]
    assert execution["container"]["image_id_verified"] is True
    assert execution["container"]["binary_sha256_verified"] is True
    assert execution["parsed"]["completion_time_ns"] == REAL_WALL_TIME
    # The container was invoked with the freshly compiled input set whose
    # hashes are recorded in the observations (no host paths anywhere).
    assert len(replay_container) == 1
    assert replay_container[0]["ranks"] == RANKS
    assert "executed_input_files" in obs["model"]
    assert set(obs["model"]["executed_input_files"]) == {
        "network.yml",
        "remote_memory.json",
        "system.json",
        *(f"workload/w1_decode_smoke_astra.{rank}.et" for rank in range(RANKS)),
    }


def test_backend_registered_in_orchestrator():
    assert "astra_sim_analytical" in BACKENDS


def test_w1_smoke_runs_on_both_backends_from_one_command(replay_container, tmp_path):
    # PASS bar: the SAME run command/path executes the W1 smoke manifest on
    # L0 and on astra_sim_analytical, both producing RunRecords in results/.
    l0 = run_experiment(
        REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml",
        results_root=tmp_path,
    )
    astra = run_experiment(ASTRA_MANIFEST, results_root=tmp_path)
    assert l0["observations"]["backend_id"] == "analytical_l0"
    assert astra["observations"]["backend_id"] == "astra_sim_analytical"
    assert l0["run_id"] != astra["run_id"]
    for result in (l0, astra):
        for artifact in ("run.json", "observations.json"):
            assert (tmp_path / result["run_id"] / artifact).is_file()
    # The astra record carries the execution provenance block; L0's does not.
    astra_run = json.loads(
        (tmp_path / astra["run_id"] / "run.json").read_text(encoding="utf-8")
    )
    assert astra_run["execution"]["backend_id"] == "astra_sim_analytical"
    l0_run = json.loads(
        (tmp_path / l0["run_id"] / "run.json").read_text(encoding="utf-8")
    )
    assert "execution" not in l0_run


def test_identical_replays_produce_byte_identical_run_records(
    replay_container, tmp_path
):
    # Determinism bar through the full orchestrator path (the real-container
    # equivalent — two fresh containers, idempotent evidence-store put — is
    # recorded in the S2 stage report).
    first = run_experiment(ASTRA_MANIFEST, results_root=tmp_path / "a")
    second = run_experiment(ASTRA_MANIFEST, results_root=tmp_path / "b")
    assert first["run_id"] == second["run_id"]
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right, f"{artifact} differs between identical replays"
    # Idempotent re-put into the SAME store: identical bytes, no error.
    third = run_experiment(ASTRA_MANIFEST, results_root=tmp_path / "a")
    assert third["run_id"] == first["run_id"]


def test_run_record_provenance_and_observable_gate(replay_container, tmp_path):
    result = run_experiment(ASTRA_MANIFEST, results_root=tmp_path)
    run = json.loads(
        (tmp_path / result["run_id"] / "run.json").read_text(encoding="utf-8")
    )
    assert run["code_version"]
    assert set(run["inputs"]) == {
        "workload_ir",
        "infra_graph",
        "standard_profile",
        "implementation_profile",
        "assumptions",
    }
    assert run["execution"]["parsed"]["completion_time_ns"] == REAL_WALL_TIME
    observations = json.loads(
        (tmp_path / result["run_id"] / "observations.json").read_text("utf-8")
    )
    # Manifest declares only O-CCT; the registry gate checked it (kind
    # analytical -> identity_cited), and conservation is recorded unsupported.
    assert "O-CCT" in observations["observables"]
    assert "O-CONSERVATION" in observations["unsupported_observables"]


def test_orchestrator_rejects_unsupported_observable_naming_gap(tmp_path):
    data = yaml.safe_load(ASTRA_MANIFEST.read_text(encoding="utf-8"))
    data["observables"] = ["O-CONSERVATION", "O-CCT"]
    path = tmp_path / "variant.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ExecutionError, match=r"O-CONSERVATION.*capabilities"):
        run_experiment(path, results_root=tmp_path / "unused")


def test_orchestrator_rejects_parse_failure_naming_gap(monkeypatch, tmp_path):
    # A container whose output cannot be parsed (here: simulator abort) is
    # rejected loudly end-to-end — no partial RunRecord is ever written.
    def aborting_runner(inputs_dir, workload_prefix, ranks):
        return {
            "exit_code": 0,
            "stdout": REAL_STDOUT.replace("ASTRA_EXIT=0", "ASTRA_EXIT=134"),
        }

    monkeypatch.setattr(adapter, "docker_run_container", aborting_runner)
    with pytest.raises(adapter.AdapterError, match="exited with code 134"):
        run_experiment(ASTRA_MANIFEST, results_root=tmp_path)
    assert not list(tmp_path.iterdir())
