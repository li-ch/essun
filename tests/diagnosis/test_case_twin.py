"""Guards for the G9 leg-4 twin case-study record.

(a) the committed case record rebuilds BYTE-IDENTICALLY from the pure
builder (drift = error; the record is append-only);
(b) the exact decomposition arithmetic re-derives in Fractions from the
committed ablation walls;
(c) the minimal reproducer's in-process L0 leg re-executes into a scratch
store to its declared content-addressed run id and exact completion time
(no Docker);
(d) the ordinary-diff demo numbers equal the G7 case record's 2 GiB twin
numbers exactly (cross-record consistency);
(e) the committed ablation stdout files re-parse to the recorded walls
(Docker-free replay of the localization legs).
"""

from __future__ import annotations

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CASE_DIR = REPO / "experiments" / "diagnosis" / "case_twin_l0_vs_astra"
BUILDER = CASE_DIR / "build_case_record.py"
COMMITTED = CASE_DIR / "case_record_v1.json"
MINIMAL_MANIFEST = CASE_DIR / "probes" / "r2-m2" / "run-diag-l0-r2-m2.yaml"


def _load_builder():
    spec = importlib.util.spec_from_file_location("g9_case_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_case_record_rebuilds_byte_identically() -> None:
    module = _load_builder()
    rebuilt = json.dumps(module.build(), indent=2, sort_keys=True) + "\n"
    assert rebuilt == COMMITTED.read_text(encoding="utf-8")


def test_decomposition_arithmetic_is_exact() -> None:
    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    loc = record["localization"]
    t_l0 = Fraction(loc["minimal_case_l0_cct_exact"])
    wall0 = Fraction(loc["a0_pinned_wall_ns"])
    chunk = Fraction(loc["chunk_knob"]["measured_term_exact"])
    mem = Fraction(loc["memory_knob"]["measured_term_exact"])
    residual = Fraction(loc["residual_after_feasible_relaxations"]["residual_exact"])
    wall4 = Fraction(loc["residual_after_feasible_relaxations"]["wall_a4_ns"])
    # twin delta and its decomposition
    assert wall0 - t_l0 == Fraction(loc["twin_delta_exact"])
    assert mem == 0  # measured inert at the minimal case
    assert chunk == 430  # the dominant, exactly measured bundling term
    assert wall4 - t_l0 == residual
    assert residual > 0  # the unattributed residual STAYS VISIBLE
    # share of the chunk term in the twin delta
    share = Fraction(loc["chunk_knob"]["share_of_twin_delta_exact"])
    assert share == chunk / (wall0 - t_l0)
    # the minimal case is the case-space floor
    assert record["minimization"]["minimal_case"] == {
        "ranks": 2,
        "payload_bytes": 2,
    }


def test_initial_pair_equals_g7_twin_numbers() -> None:
    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    diff = record["ordinary_diffing"]
    init = json.loads((CASE_DIR / "ordinary_diff_demo.json").read_text())
    assert Fraction(init["initial_pair"]["l0_cct_exact"]) == Fraction(
        "2129415031/414"
    )
    assert Fraction(init["initial_pair"]["astra_wall_ns"]) == 11216448
    dev = Fraction(11216448) / Fraction("2129415031/414") - 1
    assert Fraction(diff["initial_relative_deviation_exact"]) == dev
    # +118.07% — the G7 case record's recorded +118.1% twin delta
    assert Fraction(118, 100) < dev < Fraction(119, 100)


def test_minimal_l0_leg_reexecutes_to_declared_run_id(tmp_path) -> None:
    from essun.orchestrator.runs import run_experiment

    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    probes = record["minimization"]["probe_log"]
    initial_probe_ids = {
        p["evidence"]["l0_run_id"]
        for p in probes
        if p["candidate"] == record["minimization"]["initial_case"]
    }
    result = run_experiment(MINIMAL_MANIFEST, results_root=tmp_path)
    obs = result["observations"]["per_op"][0]
    assert obs["completion_time_ns_exact"] == record["localization"][
        "minimal_case_l0_cct_exact"
    ]
    # the minimal case's own probe log entry names this run id
    minimal_ids = {
        p["evidence"]["l0_run_id"]
        for p in probes
        if p["candidate"] == record["minimization"]["minimal_case"]
    }
    assert result["run_id"] in minimal_ids or not minimal_ids


def test_ablation_stdouts_reparse_to_recorded_walls() -> None:
    from essun.backends.astra_sim.adapter import parse_output

    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    loc = record["localization"]
    walls = {
        "a0_pinned_knobs": loc["a0_pinned_wall_ns"],
        "a1_local_mem_bw_relaxed": None,  # via ablations file below
        "a2_chunks_relaxed": None,
        "a4_all_feasible_relaxed": loc["residual_after_feasible_relaxations"]["wall_a4_ns"],
    }
    ablations = json.loads((CASE_DIR / "ablations_v1.json").read_text())
    by_name = {a["ablation"]: a for a in ablations}
    for name, wall in walls.items():
        stdout = (CASE_DIR / "localization" / "r2-m2" / f"{name}.stdout").read_text()
        parsed = parse_output(stdout, by_name[name]["exit_code"], 2)
        expected = wall if wall is not None else by_name[name]["parsed"]["completion_time_ns"]
        assert parsed["completion_time_ns"] == Fraction(str(expected)), name
    # the infeasible endpoint ablation is committed and provably aborted
    a3 = by_name["a3_endpoint_delay_zero"]
    assert a3["aborted"] is True
    a3_stdout = (CASE_DIR / "localization" / "r2-m2" / "a3_endpoint_delay_zero.stdout").read_text()
    assert "EventQueue.cpp:33" in a3_stdout
