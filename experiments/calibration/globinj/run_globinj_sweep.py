"""GLOB-INJ sweep vehicle — injection-BW (A-L05-INJ) global sensitivity
on the W1 smoke config (Q1 calibration-ladder GLOBAL stage 3 of 4,
the calibration prompt).

The L0.5 serialized-ring module (essun.backends.analytical.l05) is
deliberately unregistered in BOTH run-path registries per its own
scope fence ("run-path/golden integration is a separate
capability-gated step"):

- sweep runner (essun/orchestrator/sweeps.py) — the registry holds only the
  four landed AllReduce ids; a manifest naming the L0.5 id fails with
  ``unknown algorithm(s) ['allreduce_ring_l05']; registered: [...]``;
- run path (essun/orchestrator/runs.py) — BACKENDS holds the five L0
  models plus the ASTRA-sim adapter; a manifest naming the backend fails
  with ``unknown backend(s) ['analytical_l05']; registered: [...]``.

Both rejections are RE-EXERCISED LIVE by this vehicle on this stage's
own manifests before anything executes (the same strings recorded at
rank classes 4/8/16 by the atlas l05 cells — structural,
rank-independent). This script is therefore the stage's execution
vehicle: it mirrors the sweep runner's discipline WITHOUT touching
src/ — classified, not fixed (the atlas 4r/8r/16r_l05 pattern).

Gates mirrored from the sweep runner (a bypass is a bug):

1. live run-path rejections asserted with their exact substrings;
2. the L0.5 topology loads through the module's OWN loader
   (l05.load_l05_config — wrong topology_class, degenerate ranks, and
   non-positive B/L/I rejected there; null/absent nic loads as the
   I -> infinity limit);
3. workload tp_size == ranks;
4. every requested observable is an l05-declared capability AND a
   registered observable spec, and every emitted observation is checked
   through the registry (exact violations raise: they are bugs);
5. every row is rederived INDEPENDENTLY from the closed forms
   (Fractions from the manifest's free parameters — never by calling
   the model a second time); a mismatch raises.

Determinism/content addressing, same formulas as sweeps.py: canonical
JSON (sort_keys), exact Fractions as strings, no wall-clock in
artifacts; sweep_id = sha256(canonical manifest + code version); an
existing output directory with different bytes is an error, never a
silent overwrite.

Usage (repo root):
    .venv/bin/python experiments/calibration/globinj/run_globinj_sweep.py \
        [experiments/calibration/globinj/sweep_globinj_v1.yaml]
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from essun import __version__
from essun.backends.analytical import l05
from essun.contracts import REPO_ROOT, load_yaml, sha256_of
from essun.evidence.store import canonical_json
from essun.observables import check as check_observable
from essun.observables import lookup as lookup_observable
from essun.observables import registered as registered_observables
from essun.workload import w1

OBSERVABLES = ("O-CONSERVATION", "O-CCT")
ALGORITHM_ID = "allreduce_ring_l05"  # this stage's local registry entry
VEHICLE = "experiments/calibration/globinj/run_globinj_sweep.py"
ENDPOINT_MANIFEST_FOR_LIVE_REJECTION = (
    "experiments/calibration/globinj/run_globinj_i1_v1.yaml"
)


class VehicleError(Exception):
    """The sweep manifest or one of its configs violates a contract."""


# ---------------------------------------------------------------------------
# Live run-path rejections (gate 1) — structural, recorded in the table
# ---------------------------------------------------------------------------


def live_run_path_rejections() -> dict:
    """Exercise both run-path gates on this stage's own manifests.

    Returns the exact rejection strings for the table's execution
    provenance. A rejection that does NOT fire is a contract surprise and
    raises: if either registry ever grows analytical_l05 registration,
    this vehicle must be retired in favor of it (classified, not fixed).
    """
    from essun.orchestrator import runs as orchestrator_runs
    from essun.orchestrator import sweeps as orchestrator_sweeps

    sweep_manifest = load_yaml(REPO_ROOT / "experiments/calibration/globinj/sweep_globinj_v1.yaml")
    sweep_rejection = None
    try:
        orchestrator_sweeps.expand_grid(sweep_manifest, source="globinj-live-rejection")
    except orchestrator_sweeps.SweepError as exc:
        sweep_rejection = str(exc)
    if sweep_rejection is None or "unknown algorithm(s)" not in sweep_rejection or "allreduce_ring_l05" not in sweep_rejection:
        raise VehicleError(
            "sweep runner no longer rejects allreduce_ring_l05 — "
            f"rejection was {sweep_rejection!r}; retire this vehicle in "
            "favor of the registered path (do not keep both)"
        )

    run_rejection = None
    try:
        orchestrator_runs.run_experiment(REPO_ROOT / ENDPOINT_MANIFEST_FOR_LIVE_REJECTION)
    except orchestrator_runs.ExecutionError as exc:
        run_rejection = str(exc)
    if run_rejection is None or "unknown backend(s)" not in run_rejection or "analytical_l05" not in run_rejection:
        raise VehicleError(
            "run path no longer rejects analytical_l05 — "
            f"rejection was {run_rejection!r}; retire this vehicle in "
            "favor of the registered path (do not keep both)"
        )
    return {
        "sweep_runner": (
            f"expand_grid(sweep_globinj_v1.yaml) -> SweepError: {sweep_rejection}"
        ),
        "run_orchestrator": (
            f"run_experiment({ENDPOINT_MANIFEST_FOR_LIVE_REJECTION}) -> "
            f"ExecutionError: {run_rejection}"
        ),
    }


# ---------------------------------------------------------------------------
# Manifest loading and validation (sweeps.py-shaped)
# ---------------------------------------------------------------------------


def load_manifest(path: Path) -> dict:
    manifest = load_yaml(path)
    if not isinstance(manifest, dict) or not manifest.get("sweep"):
        raise VehicleError(f"sweep manifest {path}: a non-empty 'sweep' name is required")
    grid = manifest.get("grid")
    if not isinstance(grid, dict) or not isinstance(grid.get("payload_sizes_bytes"), list) or not grid["payload_sizes_bytes"]:
        raise VehicleError("'grid.payload_sizes_bytes' must be a non-empty integer list")
    sizes = grid["payload_sizes_bytes"]
    for size in sizes:
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise VehicleError(f"payload size {size!r} is not a positive integer byte count")
    entries = grid.get("algorithms")
    if not isinstance(entries, list) or len(entries) != 1 or entries[0].get("algorithm") != ALGORITHM_ID:
        raise VehicleError(f"this vehicle executes exactly one '{ALGORITHM_ID}' grid algorithm entry")
    if not isinstance(entries[0].get("topologies"), list) or not entries[0]["topologies"]:
        raise VehicleError("the grid algorithm entry needs a non-empty 'topologies' list")
    baseline = manifest.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("algorithm") != ALGORITHM_ID:
        raise VehicleError(f"'baseline' must name the in-grid {ALGORITHM_ID!r} config")
    if manifest.get("observables", list(OBSERVABLES)) != list(OBSERVABLES):
        raise VehicleError(f"this vehicle executes exactly {list(OBSERVABLES)}")
    unregistered = [o for o in manifest.get("observables", OBSERVABLES) if o not in registered_observables()]
    if unregistered:
        raise VehicleError(f"observable(s) {unregistered} are not registered")
    return manifest


def compute_sweep_id(manifest: dict) -> str:
    """sweep_id = sha256(canonical sweep manifest + code version) — the
    same content-addressing formula as sweeps.compute_sweep_id."""
    body = {"manifest": manifest, "code_version": __version__}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _fmt_pct(delta: Fraction) -> str:
    return f"{float(delta * 100):.4f}"


# ---------------------------------------------------------------------------
# Execution with gates 2-5 (module-direct, closed-form rederivation)
# ---------------------------------------------------------------------------


def injection_of(topology_id: str) -> str:
    """'i64' -> '64', 'inone' -> 'inf' (the null encoding, for labels)."""
    tag = topology_id.split("_i")[1].split("_")[0]
    return "inf" if tag == "none" else tag


def run_sweep(manifest_path: Path, results_root: Path | None = None) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    rejections = live_run_path_rejections()
    requested = list(manifest.get("observables", OBSERVABLES))

    workload_path = REPO_ROOT / manifest["workload"]
    if not workload_path.is_file():
        raise VehicleError(f"workload file not found: {workload_path}")
    workload_config = w1.load_w1_config(workload_path)

    # Gate 4 (capability side): requested observables must be l05-declared.
    missing = set(requested) - set(l05.CAPABILITIES["observables"])
    if missing:
        raise VehicleError(
            f"l05 backend does not support observable(s) {sorted(missing)}; "
            f"capabilities: {l05.CAPABILITIES}"
        )

    rows = []
    seen: set[str] = set()
    baseline_pairs = {
        (manifest["baseline"]["algorithm"], manifest["baseline"]["topology"])
    }
    grid_pairs = set()
    index = 0
    for entry in manifest["grid"]["algorithms"]:
        for topology_ref in entry["topologies"]:
            if topology_ref in seen:
                raise VehicleError(f"duplicate grid topology {topology_ref}")
            seen.add(topology_ref)
            grid_pairs.add((entry["algorithm"], topology_ref))
            topology_path = REPO_ROOT / topology_ref
            if not topology_path.is_file():
                raise VehicleError(f"config #{index}: topology file not found: {topology_path}")
            topology_data = load_yaml(topology_path)
            # Gate 2: the module's OWN loader rejects wrong class / degenerates.
            try:
                config = l05.load_l05_config(topology_data)
            except Exception as exc:
                raise VehicleError(
                    f"config #{index}: topology {topology_ref} rejected by "
                    f"{l05.BACKEND_ID}: {exc}"
                ) from exc
            # Gate 3: workload tp_size == ranks.
            if config.ranks != workload_config.tp_size:
                raise VehicleError(
                    f"config #{index}: workload tp_size {workload_config.tp_size} "
                    f"!= topology ranks {config.ranks} ({topology_ref})"
                )
            for size in manifest["grid"]["payload_sizes_bytes"]:
                workload_for_size = replace(workload_config, allreduce_bytes=size)
                ops = w1.generate_w1_ops(workload_for_size)
                observations = l05.execute(ops, config)

                # Gate 4 (registry side): check every emitted observation.
                registry_results = []
                for observable_id in requested:
                    spec = lookup_observable(observable_id)
                    result = check_observable(spec, observations["observables"][observable_id])
                    registry_results.append({"observable_id": observable_id, "status": result.status})

                # Gate 5: independent closed-form rederivation from the
                # manifest's own free parameters (never a second model call).
                r = Fraction(config.ranks)
                B, L = config.link_bytes_per_ns, config.hop_latency_ns
                I = config.injection_bytes_per_ns
                M = Fraction(size)
                chunk = M / r
                ser = Fraction(0) if I is None else chunk / I
                closed_t = 2 * (r - 1) * (ser + chunk / B + L)
                closed_l0 = Fraction(2 * (r - 1) * size, r) / B + 2 * (r - 1) * L
                closed_term = 2 * (r - 1) * ser
                t = Fraction(observations["observables"]["O-CCT"]["completion_time_ns_mean_exact"])
                per_op = observations["per_op"][0]
                if (
                    t != closed_t
                    or Fraction(per_op["l0_anchor_time_ns_exact"]) != closed_l0
                    or Fraction(per_op["serialization_term_ns_exact"]) != closed_term
                    or t - closed_l0 != closed_term
                ):
                    raise VehicleError(
                        f"closed-form rederivation mismatch at {topology_ref}: "
                        f"t {t} vs {closed_t}, anchor "
                        f"{per_op['l0_anchor_time_ns_exact']} vs {closed_l0}, "
                        f"term {per_op['serialization_term_ns_exact']} vs {closed_term}"
                    )
                if Fraction(per_op["per_rank_wire_bytes_exact"]) != Fraction(2 * (r - 1) * size, r):
                    raise VehicleError(f"per-rank wire mismatch at {topology_ref}")

                conservation = observations["observables"]["O-CONSERVATION"]
                cct = observations["observables"]["O-CCT"]
                rows.append(
                    {
                        "config_id": f"c{index:04d}-{ALGORITHM_ID}-{config.topology_id}-{size}",
                        "index": index,
                        "algorithm": ALGORITHM_ID,
                        "backend_id": observations["backend_id"],
                        "topology": {"path": _rel(topology_path), "sha256": sha256_of(topology_path)},
                        "payload_bytes": size,
                        "input_hashes": {
                            "workload_sha256": sha256_of(workload_path),
                            "topology_sha256": sha256_of(topology_path),
                        },
                        "injection_bytes_per_ns": (
                            None if I is None else str(I)
                        ),
                        "injection_role": (
                            "I -> infinity convergence limit (null I; OUTSIDE the "
                            "registered range [1, 1024] — the model's pinned "
                            "convergence anchor, executed as the twin cross-check row)"
                            if I is None
                            else f"finite I = {I} B/ns"
                        ),
                        "ops": len(observations["per_op"]),
                        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
                        "l0_anchor_time_ns_exact": per_op["l0_anchor_time_ns_exact"],
                        "serialization_term_ns_exact": per_op["serialization_term_ns_exact"],
                        "o_conservation": {
                            "kind": conservation["kind"],
                            "ops_checked": conservation["ops_checked"],
                            "violations": conservation["violations"],
                            "total_wire_bytes_exact": conservation["total_wire_bytes_exact"],
                        },
                        "o_cct": {
                            "kind": cct["kind"],
                            "ops": cct["ops"],
                            "completion_time_ns_mean_exact": cct["completion_time_ns_mean_exact"],
                            "completion_time_ns_mean": cct["completion_time_ns_mean"],
                            "completion_time_ns_max": cct["completion_time_ns_max"],
                        },
                        "observable_registry": registry_results,
                        "delta_vs_baseline": None,  # filled below
                    }
                )
            index += 1

    if baseline_pairs - grid_pairs:
        raise VehicleError("baseline config is not part of the grid")

    # Relative deltas vs the named baseline, matched per payload size
    # (sweeps.py rule: a delta across different payload sizes is meaningless).
    baseline_topology_rel = _rel(REPO_ROOT / manifest["baseline"]["topology"])
    by_key = {
        (row["payload_bytes"], row["algorithm"], row["topology"]["path"]): row
        for row in rows
    }
    baseline_ids: dict[str, str] = {}
    for size in manifest["grid"]["payload_sizes_bytes"]:
        baseline_row = by_key.get((size, ALGORITHM_ID, baseline_topology_rel))
        if baseline_row is None:
            raise VehicleError("baseline row missing at payload size {size}")
        baseline_ids[str(size)] = baseline_row["config_id"]
        baseline_time = Fraction(baseline_row["o_cct"]["completion_time_ns_mean_exact"])
        for row in rows:
            if row["payload_bytes"] != size:
                continue
            time = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
            delta = (time - baseline_time) / baseline_time
            row["delta_vs_baseline"] = {
                "baseline_config_id": baseline_row["config_id"],
                "delta_exact": str(delta),
                "delta_float": float(delta),
            }

    sweep_id = compute_sweep_id(manifest)
    table = {
        "sweep": manifest["sweep"],
        "sweep_id": sweep_id,
        "code_version": __version__,
        "evidence_level": "E0",
        "execution_vehicle": (
            f"{VEHICLE} (module-direct; both run-path registries reject the "
            "L0.5 backend — exact live strings below, the 4r/8r/16r-l05 "
            "atlas pattern; classified, not fixed, no src/ change)"
        ),
        "orchestrator_rejections": rejections,
        "manifest_path": _rel(manifest_path),
        "manifest_sha256": sha256_of(manifest_path),
        "workload": {
            "path": _rel(workload_path),
            "sha256": sha256_of(workload_path),
            "tp_size": workload_config.tp_size,
            "layers": workload_config.layers,
            "steps": workload_config.steps,
            "allreduce_bytes_in_workload_file": workload_config.allreduce_bytes,
            "payload_bytes_source": "grid.payload_sizes_bytes (overridden per config)",
        },
        "baseline": {
            "algorithm": manifest["baseline"]["algorithm"],
            "topology": manifest["baseline"]["topology"],
            "config_ids_by_payload_bytes": baseline_ids,
        },
        "free_parameters_fixed": {
            "link_bytes_per_ns_exact": "64 (A-L05-BW registry point, KEEP)",
            "hop_latency_ns_exact": "200 (A-L05-LAT registry point, KEEP)",
        },
        "observables": requested,
        "configs": rows,
    }

    table_json_bytes = (canonical_json(table) + "\n").encode("utf-8")
    table_md_bytes = (render_table_md(table) + "\n").encode("utf-8")

    results_root = Path(results_root) if results_root else REPO_ROOT / "results"
    sweep_dir = results_root / "sweeps" / sweep_id
    expected = {"table.json": table_json_bytes, "table.md": table_md_bytes}
    if sweep_dir.exists():
        for name, payload in expected.items():
            path = sweep_dir / name
            if not path.is_file() or path.read_bytes() != payload:
                raise VehicleError(
                    f"sweep {sweep_id} already exists with different {name} "
                    "bytes; sweep outputs are deterministic — a byte drift is "
                    "a bug, not a new result"
                )
    else:
        sweep_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in expected.items():
            (sweep_dir / name).write_bytes(payload)

    return {"sweep_id": sweep_id, "sweep_dir": sweep_dir, "table": table}


def render_table_md(table: dict) -> str:
    lines: list[str] = []
    lines.append(
        f"# Sweep `{table['sweep']}` — L0.5 analytical comparison table "
        "(GLOB-INJ injection-BW sensitivity)"
    )
    lines.append("")
    lines.append(f"Sweep id: `{table['sweep_id']}`")
    lines.append("")
    lines.append(
        "E0 evidence only. Every value below is the output of a closed-form "
        "L0.5 analytical identity under explicit free parameters "
        "(I = injection/serialization rate swept, B = "
        f"{table['free_parameters_fixed']['link_bytes_per_ns_exact']}, "
        f"L = {table['free_parameters_fixed']['hop_latency_ns_exact']}, ranks, "
        "payload size) — this table compares analytical identities, NOT "
        "empirical performance, and nothing here is measured on hardware. "
        "The delta columns are arithmetic facts of those identities (same "
        "workload shape, same payload size)."
    )
    lines.append("")
    workload = table["workload"]
    lines.append(f"- manifest: `{table['manifest_path']}` (sha256 `{table['manifest_sha256']}`)")
    lines.append(
        f"- workload: `{workload['path']}` (sha256 `{workload['sha256']}`) — "
        f"tp_size {workload['tp_size']}, layers {workload['layers']}, steps "
        f"{workload['steps']} ({workload['layers'] * workload['steps']} ops per config)"
    )
    baseline = table["baseline"]
    lines.append(
        f"- baseline: `{baseline['algorithm']}` on `{baseline['topology']}`, "
        "matched per payload size (deltas compare same-size configs)"
    )
    lines.append(f"- execution vehicle: {table['execution_vehicle']}")
    lines.append(f"- code version: {table['code_version']}")
    lines.append(
        "| config id | algorithm | topology | payload B | I (B/ns) | "
        "O-CONSERVATION | wire B/rank (exact) | L0 anchor ns (exact) | "
        "serialization term ns (exact) | L0.5 CCT mean ns (exact) | "
        "delta vs baseline (exact) | delta vs baseline (%) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in table["configs"]:
        delta = row["delta_vs_baseline"]
        lines.append(
            "| {config_id} | {algorithm} | {topology} | {payload} | {inj} | "
            "{violations} violations | {wire} | {anchor} | {term} | {cct_exact} | "
            "{delta_exact} | {delta_pct} |".format(
                config_id=row["config_id"],
                algorithm=row["algorithm"],
                topology=row["topology"]["path"].split("/")[-1],
                payload=row["payload_bytes"],
                inj=("inf" if row["injection_bytes_per_ns"] is None else row["injection_bytes_per_ns"]),
                violations=row["o_conservation"]["violations"],
                wire=row["per_rank_wire_bytes_exact"],
                anchor=row["l0_anchor_time_ns_exact"],
                term=row["serialization_term_ns_exact"],
                cct_exact=row["o_cct"]["completion_time_ns_mean_exact"],
                delta_exact=delta["delta_exact"],
                delta_pct=_fmt_pct(Fraction(delta["delta_exact"])),
            )
        )
    lines.append("")
    lines.append(
        "Generated deterministically from the sweep manifest (canonical "
        "JSON, exact Fractions, no wall-clock); byte-identical on replay. "
        "Every row rederived independently from the closed forms before "
        "emission."
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute the GLOB-INJ injection-BW sensitivity sweep (L0.5 module-direct)"
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(Path(__file__).parent / "sweep_globinj_v1.yaml"),
        help="path to the sweep manifest YAML (default: the sibling v1 manifest)",
    )
    args = parser.parse_args(argv)
    result = run_sweep(Path(args.manifest))
    print(
        json.dumps(
            {"sweep_id": result["sweep_id"], "sweep_dir": str(result["sweep_dir"])},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
