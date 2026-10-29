"""Q3 stage S2 execution tests: container run -> parse -> RunRecord.

The parse tests run against the recorded stdout of a REAL execution of the
W1 smoke manifest in the pinned container (fixture
``tests/fixtures/uet_htsim/w1_smoke_8rank_6op_stdout.txt``, provenance in
its README) — so the parser is pinned to the binary's actual output, not to
a hand-written fantasy of it. The run/record path is exercised with the
container invocation replayed from that fixture (no Docker needed in CI);
the real-container execution is additionally verified by the determinism
check recorded in the S2 stage report (two fresh containers, byte-identical
stdout AND byte-identical logout.dat traces, idempotent content-addressed
evidence-store put — run_id fbb46d16…).

Golden numbers below are hand-derived from the executed free parameters
(ring8_free_params.yaml B=64 B/ns L=200 ns ranks 8; w1_dense_tp_decode_
small.yaml 3 steps x 2 layers M=16384 B) and the pinned binary's
deterministic run: every flow 28672 B wire / 32688 counted bytes, per-op
completion = max flow FCT {3.17033, 3.17033, 3.16832, 3.16832, 3.17033,
3.17033} us, serialized chain = 19.01796 us = 19017.96 ns exactly (sum by
exact Fraction arithmetic, re-derived in the test).
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.backends.uet_htsim import adapter
from essun.orchestrator.runs import BACKENDS, ExecutionError, run_experiment

REPO = Path(__file__).resolve().parents[2]
UET_MANIFEST = (
    REPO / "experiments" / "vertical_slice" / "w1_decode_smoke_uet.yaml"
)
FIXTURES = REPO / "tests" / "fixtures" / "uet_htsim"
REAL_STDOUT = (FIXTURES / "w1_smoke_8rank_6op_stdout.txt").read_text(
    encoding="utf-8"
)
COMPILED_DIR = REPO / "experiments" / "vertical_slice" / "uet_w1_decode_smoke_uet"

# Hand-derived from the executed free parameters and the pinned binary's
# deterministic run (see module docstring).
RANKS = 8
OPS = 6
OP_FILES = [f"w1_decode_smoke_uet.op{index:06d}.cm" for index in range(OPS)]
PER_OP_COMPLETION_US = [
    "3.17033", "3.17033", "3.16832", "3.16832", "3.17033", "3.17033",
]
CHAIN_NS = "19017.96"  # 4*3.17033 + 2*3.16832 = 19.01796 us exactly
OP0_FLOW_FCTS = {  # flow_id -> printed finish us (start is 0 for all)
    1: "1.31749", 2: "2.24391", 3: "1.37417", 4: "3.17033",
    5: "1.31749", 6: "2.2419", 7: "1.37417", 8: "3.16832",
}


# --- parse: golden against the real recorded output -------------------------


def test_parse_real_w1_smoke_output():
    parsed = adapter.parse_output(REAL_STDOUT, exit_code=0, op_files=OP_FILES, ranks=RANKS)
    assert parsed["ranks"] == RANKS
    assert len(parsed["ops"]) == OPS
    for op, expected_us in zip(parsed["ops"], PER_OP_COMPLETION_US):
        assert op["completion_us_exact"] == expected_us
        assert Fraction(op["completion_us_exact"]) == Fraction(expected_us)
        assert Fraction(op["completion_ns_exact"]) == Fraction(expected_us) * 1000
        assert len(op["per_flow"]) == RANKS
    # op 0 per-flow golden: ids 1..8 (A-UET1-IDS), ring endpoints, FCTs.
    op0 = {flow["flow_id"]: flow for flow in parsed["ops"][0]["per_flow"]}
    assert sorted(op0) == list(range(1, RANKS + 1))
    for flow_id, fct in OP0_FLOW_FCTS.items():
        flow = op0[flow_id]
        rank = flow_id - 1
        assert flow["src"] == rank
        assert flow["dst"] == (rank + 1) % RANKS  # ring successor (A-UET1-WIRE)
        assert flow["finish_us_printed"] == fct
        assert Fraction(flow["fct_us_exact"]) == Fraction(fct)  # start is 0
        assert flow["total_bytes"] == 32688  # counted bytes, not payload
        assert flow["rts"] == 0
    assert parsed["ops"][0]["summary"]["new"] == 64  # 8 flows x 8 packets
    assert parsed["ops"][0]["summary"]["rtx"] == 0  # no retransmissions
    # Serialized chain: exact sum of per-op completions, by Fractions.
    chain = sum(
        (Fraction(op["completion_us_exact"]) for op in parsed["ops"]),
        Fraction(0),
    )
    assert chain == Fraction("19.01796")
    assert parsed["completion_time_ns_exact"] == CHAIN_NS
    assert Fraction(parsed["completion_time_ns_exact"]) == chain * 1000
    # A-UET1-END sufficiency: max observed finish far inside the -end window.
    assert Fraction(parsed["max_finish_us_printed"]) == Fraction("3.17033")
    assert "us as printed" in parsed["units"]


def test_parse_flow_ids_walk_the_op_index():
    # The binary echoes the compiled flow ids: op k's ids are k*8+1..k*8+8
    # (A-UET1-IDS) — the output proves the executed file is the compiled one.
    for op_index, op in enumerate(
        adapter.parse_output(
            REAL_STDOUT, exit_code=0, op_files=OP_FILES, ranks=RANKS
        )["ops"]
    ):
        assert sorted(flow["flow_id"] for flow in op["per_flow"]) == [
            op_index * RANKS + rank + 1 for rank in range(RANKS)
        ]


# --- parse: every failure mode rejected with the gap named ------------------

_SUMMARY = "New: 64 Rtx: 0 RTS: 0 Bounced: 0 ACKs: 26 NACKs: 0 Pulls: 0 sleek_pkts: 0"


def _minimal_output(**overrides) -> str:
    """One valid op section (op 0 of the smoke shape) plus the pinned-binary
    sha preamble, with mutation hooks for the negative tests."""
    sha = f"ESSUN_BINARY_SHA256={adapter.PIN['binary_sha256']}"
    name = overrides.get("name", OP_FILES[0])
    lines = [sha, f"=== OP FILE {name} ===", "Starting simulation"]
    for rank in range(RANKS):
        dst = (rank + 1) % RANKS
        fid = rank + 1
        lines.append(f"Flow Uec_{rank}_{dst} flowId {fid} uecSrc {rank} starting at 0")
        lines.append(
            f"Flow Uec_{rank}_{dst} flowId {fid} uecSrc {rank} finished at "
            "1.5 total messages 1 total packets 8 RTS 0 total bytes 32688 "
            "in_flight now 0 fair_inc 0 prop_inc 0 fast_inc 0 eta_inc 0 "
            "multi_dec -0 quick_dec -0 nack_dec -0"
        )
    lines.append(_SUMMARY)
    lines.append("UET_EXIT=0")
    lines = overrides.get("transform", lambda ls: ls)(lines)
    return "\n".join(lines)


def test_parse_rejects_container_failure():
    with pytest.raises(adapter.AdapterError, match="exited with code 1"):
        adapter.parse_output(
            _minimal_output(), exit_code=1, op_files=OP_FILES[:1], ranks=RANKS
        )


def test_parse_rejects_unpinned_binary():
    text = _minimal_output().replace(
        f"ESSUN_BINARY_SHA256={adapter.PIN['binary_sha256']}",
        "ESSUN_BINARY_SHA256=" + "0" * 64,
    )
    with pytest.raises(adapter.AdapterError, match="unpinned binary"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_missing_sha_marker():
    text = "\n".join(_minimal_output().splitlines()[1:])
    with pytest.raises(adapter.AdapterError, match="ESSUN_BINARY_SHA256 marker"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_op_sequence_mismatch():
    # The executed marker names op 1's file while the orchestration expects
    # op 0's: serialization order is a contract (A-UET1-OPFILE), not a hint.
    text = _minimal_output(name=OP_FILES[1])
    with pytest.raises(
        adapter.AdapterError, match=r"op-file sequence.*A-UET1-OPFILE"
    ):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_simulator_failure():
    text = _minimal_output().replace("UET_EXIT=0", "UET_EXIT=1")
    with pytest.raises(adapter.AdapterError, match=r"exited with code 1"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_missing_op_markers():
    text = "\n".join(
        line for line in _minimal_output().splitlines()
        if not line.startswith("=== OP FILE")
    )
    with pytest.raises(adapter.AdapterError, match="no '=== OP FILE"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_unfinished_flow_naming_end():
    # A flow that started but never finished: the -end window closed first.
    def drop_flow_8_finish(lines):
        return [
            line for line in lines
            if not ("flowId 8" in line and "finished at" in line)
        ]

    text = _minimal_output(transform=drop_flow_8_finish)
    with pytest.raises(
        adapter.AdapterError, match=r"flow id\(s\) \[8\].*A-UET1-END"
    ):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_duplicate_flow_finish():
    def duplicate(lines):
        dup = [line for line in lines if "flowId 3" in line and "finished at" in line][0]
        return lines + [dup]

    text = _minimal_output(transform=duplicate)
    with pytest.raises(adapter.AdapterError, match="flow id 3.*twice"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_unexpected_flow_id():
    # flowId 9 in op 0 is outside the compiled A-UET1-IDS set 1..8.
    text = _minimal_output().replace("flowId 8", "flowId 9")
    with pytest.raises(adapter.AdapterError, match="A-UET1-IDS set"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_non_ring_endpoint():
    # dst 2 for rank 0 is not the ring successor — wrong matrix executed.
    text = _minimal_output().replace("Flow Uec_0_1 flowId 1", "Flow Uec_0_2 flowId 1")
    with pytest.raises(adapter.AdapterError, match="A-UET1-WIRE"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_finish_before_start():
    text = _minimal_output().replace(
        "flowId 4 uecSrc 3 starting at 0", "flowId 4 uecSrc 3 starting at 2"
    )
    with pytest.raises(adapter.AdapterError, match="finished before it started"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_finish_at_or_after_end_window():
    text = _minimal_output().replace(
        "flowId 4 uecSrc 3 finished at 1.5",
        "flowId 4 uecSrc 3 finished at 1000.0",
    )
    with pytest.raises(adapter.AdapterError, match=r"A-UET1-END"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_missing_summary_line():
    text = "\n".join(
        line for line in _minimal_output().splitlines() if not line.startswith("New: ")
    )
    with pytest.raises(adapter.AdapterError, match=r"'New:' summary line"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


def test_parse_rejects_missing_starting_simulation():
    text = "\n".join(
        line for line in _minimal_output().splitlines()
        if line.strip() != "Starting simulation"
    )
    with pytest.raises(adapter.AdapterError, match="Starting simulation"):
        adapter.parse_output(text, exit_code=0, op_files=OP_FILES[:1], ranks=RANKS)


# --- execute_experiment with the container replayed from the fixture --------


@pytest.fixture
def replay_container(monkeypatch):
    """Replay the recorded real container output; capture the invocation so
    tests can additionally assert on what was executed."""
    calls = []

    def fake_run_container(inputs_dir, op_files, linkspeed, hop_latency, seed):
        calls.append(
            {
                "inputs_dir": Path(inputs_dir),
                "op_files": list(op_files),
                "linkspeed": linkspeed,
                "hop_latency": hop_latency,
                "seed": seed,
            }
        )
        return {"exit_code": 0, "stdout": REAL_STDOUT}

    monkeypatch.setattr(adapter, "docker_run_container", fake_run_container)
    return calls


def test_execute_experiment_observations_and_provenance(replay_container):
    out = adapter.execute_experiment(UET_MANIFEST)
    obs = out["observations"]
    assert obs["backend_id"] == "uet_htsim_cms"
    assert obs["model"]["ranks"] == RANKS
    assert obs["model"]["link_bytes_per_ns_exact"] == "64"
    assert obs["model"]["hop_latency_ns_exact"] == "200"
    assert "uet_htsim_commit" in obs["model"]["pin"]
    # O-CCT: parsed, honestly labeled (registry kind: analytical).
    occt = obs["observables"]["O-CCT"]
    assert occt["kind"] == "analytical"
    assert "parsed" in occt["method"]
    assert occt["ops"] == OPS
    assert occt["completion_time_ns_exact"] == CHAIN_NS
    assert [Fraction(op["completion_time_ns_exact"]) for op in occt["per_op"]] == [
        Fraction(us) * 1000 for us in PER_OP_COMPLETION_US
    ]
    assert occt["per_op"][0]["op_id"] == "s000000-l000000-allreduce"
    # O-CONSERVATION: honest unsupported record with the live counter
    # evidence (32688 counted for the 28672-byte flows), not a silent gap.
    unsupported = obs["unsupported_observables"]["O-CONSERVATION"]
    assert "32688" in unsupported and "28672" in unsupported
    # Execution provenance: pin identity, exact flags, parsed values.
    execution = out["execution"]
    assert execution["container"]["image_id_verified"] is True
    assert execution["container"]["binary_sha256_verified"] is True
    assert execution["container"]["flags_executed"] == {
        "-linkspeed": 512000,
        "-hop_latency": "0.2",
        "-seed": 20261026,
        "-end": 1000,
    }
    assert execution["parsed"]["completion_time_ns_exact"] == CHAIN_NS
    assert execution["end_sufficiency"]["max_finish_us_printed"] == "3.17033"
    # The container was invoked once with the freshly compiled input set:
    # exactly the six op matrices, in op order, with the manifest-derived
    # flags verbatim (A-UET1-BW/LAT/SEED conversions).
    assert len(replay_container) == 1
    call = replay_container[0]
    assert call["op_files"] == OP_FILES
    assert call["linkspeed"] == 512000
    assert call["hop_latency"] == "0.2"
    assert call["seed"] == 20261026
    # The executed inputs ARE the committed compiled set, hash for hash.
    executed = obs["model"]["executed_input_files"]
    assert sorted(executed) == OP_FILES
    for name, sha in executed.items():
        assert adapter.contracts.sha256_of(COMPILED_DIR / name) == sha


def test_backend_registered_in_orchestrator():
    assert "uet_htsim_cms" in BACKENDS


def test_w1_smoke_runs_on_l0_and_uet_from_one_command(replay_container, tmp_path):
    # PASS bar: the SAME run command/path executes the W1 smoke manifest on
    # L0 and on uet_htsim_cms, both producing RunRecords in the store root.
    l0 = run_experiment(
        REPO / "experiments" / "vertical_slice" / "w1_decode_smoke.yaml",
        results_root=tmp_path,
    )
    uet = run_experiment(UET_MANIFEST, results_root=tmp_path)
    assert l0["observations"]["backend_id"] == "analytical_l0"
    assert uet["observations"]["backend_id"] == "uet_htsim_cms"
    assert l0["run_id"] != uet["run_id"]
    for result in (l0, uet):
        for artifact in ("run.json", "observations.json"):
            assert (tmp_path / result["run_id"] / artifact).is_file()
    # The uet record carries the execution provenance block; L0's does not.
    uet_run = json.loads(
        (tmp_path / uet["run_id"] / "run.json").read_text(encoding="utf-8")
    )
    assert uet_run["execution"]["backend_id"] == "uet_htsim_cms"
    l0_run = json.loads(
        (tmp_path / l0["run_id"] / "run.json").read_text(encoding="utf-8")
    )
    assert "execution" not in l0_run


def test_identical_replays_produce_byte_identical_run_records(
    replay_container, tmp_path
):
    # Determinism bar through the full orchestrator path (the real-container
    # equivalent — two fresh containers, byte-identical stdout and traces,
    # idempotent evidence-store put — is recorded in the S2 stage report).
    first = run_experiment(UET_MANIFEST, results_root=tmp_path / "a")
    second = run_experiment(UET_MANIFEST, results_root=tmp_path / "b")
    assert first["run_id"] == second["run_id"]
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right, f"{artifact} differs between identical replays"
    # Idempotent re-put into the SAME store: identical bytes, no error.
    third = run_experiment(UET_MANIFEST, results_root=tmp_path / "a")
    assert third["run_id"] == first["run_id"]


def test_run_record_provenance_and_observable_gate(replay_container, tmp_path):
    result = run_experiment(UET_MANIFEST, results_root=tmp_path)
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
    assert run["execution"]["parsed"]["completion_time_ns_exact"] == CHAIN_NS
    observations = json.loads(
        (tmp_path / result["run_id"] / "observations.json").read_text("utf-8")
    )
    # Manifest declares only O-CCT; the registry gate checked it (kind
    # analytical -> identity_cited), and conservation is recorded unsupported.
    assert "O-CCT" in observations["observables"]
    assert "O-CONSERVATION" in observations["unsupported_observables"]


def test_orchestrator_rejects_unsupported_observable_naming_gap(tmp_path):
    data = yaml.safe_load(UET_MANIFEST.read_text(encoding="utf-8"))
    data["observables"] = ["O-CONSERVATION", "O-CCT"]
    path = tmp_path / "variant.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ExecutionError, match=r"O-CONSERVATION.*capabilities"):
        run_experiment(path, results_root=tmp_path / "unused")


def test_orchestrator_rejects_parse_failure_naming_gap(monkeypatch, tmp_path):
    # A container whose output cannot be parsed (here: simulator exit 1) is
    # rejected loudly end-to-end — no partial RunRecord is ever written.
    def aborting_runner(inputs_dir, op_files, linkspeed, hop_latency, seed):
        return {
            "exit_code": 0,
            "stdout": REAL_STDOUT.replace("UET_EXIT=0", "UET_EXIT=1"),
        }

    monkeypatch.setattr(adapter, "docker_run_container", aborting_runner)
    with pytest.raises(adapter.AdapterError, match="exited with code 1"):
        run_experiment(UET_MANIFEST, results_root=tmp_path)
    assert not list(tmp_path.iterdir())
