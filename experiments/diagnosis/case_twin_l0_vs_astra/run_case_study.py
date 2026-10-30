#!/usr/bin/env python3
"""G9 leg-4 case study: the misleading twin comparison, minimized and classified.

THE STORY (one complete misleading comparison):

  Engine A (essun ``analytical_l0``, the ring identity) and engine B
  (ASTRA-sim analytical, pinned Docker 4ce9ecfe, native Ring AllReduce)
  run the IDENTICAL topology and workload bytes (the G7 twin pair at
  r=72, B=828, the CAL-A3 2 GiB floor bracket). Engine B's completion
  lands +118.1% above engine A's. An engineer who diffs the two
  "completion times" concludes the ring identity is ~2x optimistic — a
  MISLEADING comparison, because the two numbers are different
  observables bundled with translation knobs the diff never names.

This driver executes the diagnosis pipeline on that disagreement:

  1. ORDINARY DIFFING (the failure): the S3 differential-validation
     engine's exact O-CCT obligation reports ONE first divergence
     (+118.1%) — a magnitude, not an explanation. Recorded for contrast.
  2. MINIMIZE: deterministic delta debugging over (ranks, payload) —
     every candidate is a REAL run pair through the orchestrator (L0
     in-process; ASTRA in the pinned container), every probe logged with
     its content-addressed run ids.
  3. LOCALIZE: at the minimal reproducer, single-knob ablations of the
     pinned binary's translation knobs (A-AS2-MEM-BW, A-AS1-CHUNKS-1,
     A-AS2-DELAY-POS), executed DIRECTLY against the pinned container
     (the S2-counterexample precedent) with raw stdout committed.
  4. CLASSIFY: components labeled through the mechanical classifier; the
     residual after all feasible ablations STAYS VISIBLE as unresolved.

Usage:
    .venv/bin/python experiments/diagnosis/case_twin_l0_vs_astra/run_case_study.py execute   # needs Docker
    .venv/bin/python experiments/diagnosis/case_twin_l0_vs_astra/run_case_study.py build     # pure, from committed blocks
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from essun.diagnosis.minimize import (  # noqa: E402
    CaseDelta,
    InfeasibleDelta,
    ProbeResult,
    _public,
    minimize as minimize_case,
)
from essun.diagnosis.classify import (  # noqa: E402
    DECLARED_DIFFERENT_QUANTITY,
    EngineFacts,
)

CASE_DIR = Path(__file__).resolve().parent
PROBES_DIR = CASE_DIR / "probes"
ABLATIONS_DIR = CASE_DIR / "localization"
COMMITTED_RECORD = CASE_DIR / "case_record_v1.json"

B = 828  # B/ns (the G7 twin value; nearest ASTRA-representable integer above B_fit)
L = 200  # ns (A-L0-LAT registry point)
INITIAL_RANKS = 72
INITIAL_PAYLOAD = 2147483592  # CAL-A3 2 GiB floor bracket (largest multiple of 72 <= 2^31)
MATERIAL_DISAGREEMENT = Fraction(1, 100)  # declared threshold: >1% relative deviation

# The G7 twin pair at 2 GiB (stored run ids from the G7 case study; the
# diff-engine demo re-executes against the local results/ store when
# present and is skipped on a cold clone with a recorded note).
G7_TWIN = {
    "l0_run_id": "2e3b54e953b3e8dc8f7b59637ea4fd3cb5b5ced9c57fd4070433841509644c7b",
    "astra_run_id": "8bcf3697dd731d1c47146ff59ad37c5577e3b6358d6ed4b8eb414f1d19baf252",
    "manifests": [
        "experiments/gonogo/case_a3_cross_engine/run_a3-l0ring-b828-2gib.yaml",
        "experiments/gonogo/case_a3_cross_engine/run_a3-astra-b828-2gib.yaml",
    ],
    "l0_cct_exact": "2129415031/414",  # from the G7 case record
    "astra_wall_ns": 11216448,         # from the G7 case record
}


@dataclass(frozen=True)
class TwinCase:
    ranks: int
    payload_bytes: int


# ---------------------------------------------------------------- probe files


def _write_probe_files(case: TwinCase) -> dict:
    case_id = f"r{case.ranks}-m{case.payload_bytes}"
    d = PROBES_DIR / case_id
    d.mkdir(parents=True, exist_ok=True)
    topo = d / f"topology_ring{case.ranks}_b828_v1.yaml"
    wl = d / f"workload_tp{case.ranks}_{case.payload_bytes}.yaml"
    if not topo.exists():
        topo.write_text(
            f"# G9 diagnosis twin probe topology (case {case_id}): identical\n"
            f"# file shared by both engines (the same-workload bar).\n"
            f"topology_id: ring{case.ranks}_diag_b828_v1\ntopology_class: unidirectional_ring\n"
            f"ranks: {case.ranks}\nlink:\n  bytes_per_ns: {B}\n  hop_latency_ns: {L}\n",
            encoding="utf-8",
        )
    if not wl.exists():
        wl.write_text(
            f"# G9 diagnosis twin probe workload (case {case_id}): one op.\n"
            f"workload: w1_dense_tp_decode\nmodel_name: diag-twin-{case_id}\n"
            f"tp_size: {case.ranks}\nlayers: 1\nsteps: 1\n"
            f"allreduce_bytes: {case.payload_bytes}\n",
            encoding="utf-8",
        )
    manifests = {}
    for engine, backend, obs in (
        ("l0", "analytical_l0", ["O-CONSERVATION", "O-CCT"]),
        ("astra", "astra_sim_analytical", ["O-CCT"]),
    ):
        m = d / f"run-diag-{engine}-{case_id}.yaml"
        if not m.exists():
            m.write_text(
                f"# G9 diagnosis twin probe: engine {engine} at case {case_id}.\n"
                f"experiment_id: EXP-DIAG-TWIN-{engine.upper()}-{case_id.upper()}-001\n"
                f"research_question: RQ2\nclaim_id: \"\"\nbaseline_id: null\n"
                f"workload_ir:\n  path: {_rel(wl)}\ninfra_graph:\n  path: {_rel(topo)}\n"
                f"standard_profile:\n  path: experiments/vertical_slice/profiles/standard_profile_none.yaml\n"
                f"implementation_profile:\n  path: experiments/vertical_slice/profiles/"
                f"{'implementation_profile_l0.yaml' if engine == 'l0' else 'implementation_profile_astra_sim_analytical.yaml'}\n"
                f"assumptions:\n  path: experiments/vertical_slice/assumptions_l0.yaml\n"
                f"backends:\n- {backend}\nseed: 20261030\nrepetitions: 1\nmetrics: []\n"
                f"observables:\n  - " + "\n  - ".join(obs) + "\n"
                f"counterexample_policy: minimize_then_refine\n"
                f"validity_domain:\n"
                f"  topology: ring{case.ranks} at B={B}, L={L} (free parameters, the G7 twin values)\n"
                f"  workload: one w1 AllReduce of {case.payload_bytes} B (divisible by {case.ranks})\n"
                f"  implementation: G9 diagnosis minimization probe; E0/PROPOSED; nothing tuned; no labels\n"
                f"evidence_level_requested: E0\n"
                f"evidence_dimensions:\n"
                f"  verification:\n  - check: tests/diagnosis/test_case_twin.py\n"
                f"    scope: G9 twin case study guard — rebuilds the case record from these runs\n"
                f"  calibration_target: []\n"
                f"  held_out:\n    held_out: false\n    scope: diagnosis probe; no anchor read\n"
                f"  independent_reproduction: []\n"
                f"  known_omissions:\n"
                f"  - diagnosis minimization probe of the G7 twin disagreement; not a calibration leg\n",
                encoding="utf-8",
            )
        manifests[engine] = m
    return {"topology": topo, "workload": wl, "manifests": manifests, "case_id": case_id}


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


# ---------------------------------------------------------------- the probe


def _observations(run_result: dict) -> dict:
    return run_result["observations"]


def probe(case: TwinCase, *, cache: dict) -> ProbeResult:
    """Run BOTH engines on the case through the orchestrator; compare."""
    key = (case.ranks, case.payload_bytes)
    if key in cache:
        return cache[key]
    files = _write_probe_files(case)
    from essun.orchestrator.runs import run_experiment

    try:
        run_l0 = run_experiment(files["manifests"]["l0"])
    except Exception as exc:
        result = ProbeResult("error_engine_a", {"error": f"{type(exc).__name__}: {exc}"})
        cache[key] = result
        return result
    try:
        run_b = run_experiment(files["manifests"]["astra"])
    except Exception as exc:
        result = ProbeResult("error_engine_b", {"error": f"{type(exc).__name__}: {exc}"})
        cache[key] = result
        return result
    obs_b = _observations(run_b)["observables"]["O-CCT"]
    a_exact = run_l0["observations"]["per_op"][0]["completion_time_ns_exact"]
    b_wall = Fraction(str(obs_b["completion_time_ns"]))
    rel = abs(b_wall / Fraction(a_exact) - 1)
    reproduces = rel > MATERIAL_DISAGREEMENT
    evidence = {
        "case_id": files["case_id"],
        "l0_run_id": run_l0["run_id"],
        "astra_run_id": run_b["run_id"],
        "l0_manifest": _rel(files["manifests"]["l0"]),
        "astra_manifest": _rel(files["manifests"]["astra"]),
        "l0_cct_exact": a_exact,
        "astra_wall_ns": str(b_wall),
        "relative_deviation_exact": str(rel),
        "threshold_exact": str(MATERIAL_DISAGREEMENT),
    }
    result = ProbeResult("reproduces" if reproduces else "vanished", evidence)
    cache[key] = result
    return result


def ladder(case: TwinCase) -> list[CaseDelta]:
    deltas = []
    for ranks in _rank_targets(case.ranks):
        def rk(rr=ranks):
            def apply(c):
                if c.payload_bytes % rr:
                    raise InfeasibleDelta("payload not divisible by target ranks")
                return replace(c, ranks=rr)

            return apply

        deltas.append(CaseDelta("ranks", f"ranks {case.ranks} -> {ranks}", rk()))
    for payload in _payload_targets(case.payload_bytes, case.ranks):
        def pk(p=payload):
            def apply(c):
                return replace(c, payload_bytes=(p // c.ranks) * c.ranks)

            return apply

        deltas.append(
            CaseDelta(
                "payload_bytes",
                f"payload {case.payload_bytes} -> {(payload // case.ranks) * case.ranks}",
                pk(),
            )
        )
    return deltas


def _rank_targets(ranks: int) -> list[int]:
    targets = (ranks // 2, ranks // 3, 24, 18, 12, 9, 8, 6, 4, 3, 2)
    return [t for t in targets if 2 <= t < ranks]


def _payload_targets(payload: int, ranks: int) -> list[int]:
    out, v = [], payload
    while v > ranks:
        v = max(ranks, v // 2)
        if v not in out:
            out.append(v)
    return out


# ---------------------------------------------------------------- localization


PINNED_SYSTEM = {
    "scheduling-policy": "LIFO",
    "endpoint-delay": 10,
    "active-chunks-per-dimension": 1,
    "local-mem-bw": 1600,
}


def run_ablation(case: TwinCase, name: str, overrides: dict) -> dict:
    """Direct pinned-binary run with patched system knobs (S2 precedent).

    Compiles the case via the adapter, patches ``system.json`` with
    ``overrides``, runs the container, and commits the raw stdout.
    """
    from essun.backends.astra_sim import adapter
    from essun.backends.astra_sim.adapter import docker_run_container, parse_output

    files = _write_probe_files(case)
    manifest = files["manifests"]["astra"]
    import tempfile

    with tempfile.TemporaryDirectory(prefix="essun-g9-ablation-") as tmp:
        inputs_dir = Path(tmp) / "inputs"
        plan = adapter.compile_experiment(manifest, inputs_dir)
        (inputs_dir / "compile_plan.json").unlink()
        system = dict(PINNED_SYSTEM)
        system.update(
            {
                "preferred-dataset-splits": case.ranks,
                "all-reduce-implementation": ["ring"],
                "all-gather-implementation": ["ring"],
                "reduce-scatter-implementation": ["ring"],
                "all-to-all-implementation": ["ring"],
                "collective-optimization": "localBWAware",
            }
        )
        system.update(overrides)
        (inputs_dir / "system.json").write_text(
            json.dumps(system, indent=4) + "\n", encoding="utf-8"
        )
        result = docker_run_container(inputs_dir, manifest.stem, case.ranks)
    out_dir = ABLATIONS_DIR / f"{files['case_id']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.stdout").write_text(result["stdout"], encoding="utf-8")
    (out_dir / f"{name}.system.json").write_text(
        json.dumps(system, indent=4, sort_keys=True) + "\n", encoding="utf-8"
    )
    record = {
        "ablation": name,
        "case_id": files["case_id"],
        "overrides": overrides,
        "exit_code": result["exit_code"],
        "system_json": json.dumps(system, sort_keys=True),
        "stdout_file": f"localization/{files['case_id']}/{name}.stdout",
    }
    try:
        record["parsed"] = parse_output(
            result["stdout"], result["exit_code"], case.ranks
        )
        record["aborted"] = False
    except Exception as exc:
        # A knob the pinned binary cannot survive (e.g. endpoint-delay 0,
        # A-AS2-DELAY-POS): the infeasibility itself is the finding —
        # that term cannot be zeroed in engine B. Recorded, never hidden.
        record["aborted"] = True
        record["abortion_error"] = f"{type(exc).__name__}: {exc}"
    return record


def execute() -> dict:
    """The Docker execution phase: minimization + ablations."""
    cache: dict = {}
    initial = TwinCase(ranks=INITIAL_RANKS, payload_bytes=INITIAL_PAYLOAD)
    result = minimize_case(initial, lambda c: probe(c, cache=cache), ladder)
    if not result.reproducer_found:
        raise SystemExit("FATAL: twin disagreement did not reproduce at the initial case")
    minimal = result.minimal_case

    probe_log = [
        {
            "pass": p.pass_index,
            "dimension": p.dimension,
            "description": p.description,
            "candidate": p.candidate,
            "outcome": p.outcome,
            "accepted": p.accepted,
            "evidence": p.evidence,
        }
        for p in result.probes
    ]
    minimization_block = {
        "initial_case": _public(initial),
        "minimal_case": _public(minimal),
        "passes": result.passes,
        "probes": len(result.probes),
        "accepted": sum(1 for p in result.probes if p.accepted),
        "final_pass_rejections": [
            {
                "dimension": p.dimension,
                "description": p.description,
                "outcome": p.outcome,
                "evidence": p.evidence,
            }
            for p in result.rejections_of_final_pass()
        ],
        "probe_log": probe_log,
    }

    (CASE_DIR / "minimization_v1.json").write_text(
        json.dumps(minimization_block, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Localization ablations at the minimal reproducer. A0 must reproduce
    # the orchestrator ASTRA run's Wall exactly (sanity anchor).
    ablations = [
        ("a0_pinned_knobs", {}),
        ("a1_local_mem_bw_relaxed", {"local-mem-bw": 1600000}),
        ("a2_chunks_relaxed", {"active-chunks-per-dimension": 4}),
        ("a3_endpoint_delay_zero", {"endpoint-delay": 0}),
        ("a4_all_feasible_relaxed", {"local-mem-bw": 1600000, "active-chunks-per-dimension": 4}),
    ]
    ablation_results = []
    for name, overrides in ablations:
        ablation_results.append(run_ablation(minimal, name, overrides))

    (CASE_DIR / "ablations_v1.json").write_text(
        json.dumps(ablation_results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"minimal_case": minimization_block["minimal_case"],
                      "passes": result.passes, "probes": len(result.probes)}, indent=2))
    for a in ablation_results:
        wall = a["parsed"].get("completion_time_ns") if not a.get("aborted") else "ABORTED"
        print(a["ablation"], "exit", a["exit_code"], "wall", wall)
    return {"minimization": minimization_block, "ablations": ablation_results}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "execute"
    if mode == "execute":
        execute()
    else:
        raise SystemExit(f"unknown mode {mode!r} (use: execute)")
