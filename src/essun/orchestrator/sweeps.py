"""Deterministic sweep runner: one shared workload across a GRID of
algorithms x topologies x payload sizes.

This is the first product-facing artifact of the fair cross-configuration
comparison thesis: a sweep manifest (YAML, under ``experiments/sweeps/``)
names ONE workload file and a grid; the runner expands the grid into
per-config executions over the landed L0 analytical models, enforcing the
capability gates per config, and emits a machine-readable comparison table
(``table.json``) plus a human grid with a relative-delta column
(``table.md``) into ``results/sweeps/<sweep_id>/``.

Evidence level E0 ONLY. Every number in a sweep table is the output of a
closed-form L0 identity under explicit free parameters (B, L, ranks, payload
size); the tables compare ANALYTICAL IDENTITIES, not empirical performance,
and no artifact may be read as a statement about measured hardware behavior.
Relative deltas are arithmetic facts of those identities (same workload
shape, same payload size), labeled as such in ``table.md``.

Determinism (same policy as runs.py): integer byte
counts, exact Fractions serialized as strings, canonical JSON
(``sort_keys``), and NO wall-clock inside artifacts. ``sweep_id`` is the
SHA-256 of the canonical sweep manifest plus the code version, so identical
manifest + code reproduce byte-identical tables (tests/determinism).

Capability gates enforced per config (a bypass is a bug, never a feature):

1. every grid algorithm id must be registered below (unknown -> explicit
   error before anything executes);
2. the (algorithm, topology_class) pairing must be a DECLARED identity —
   each L0 algorithm runs on exactly the fabric class its module documents
   (the fabric/algorithm pairing rule, same spirit as A-L0P-ALGO);
3. the topology config must load through the algorithm module's own loader
   (loaders reject degenerate values explicitly);
4. workload ``tp_size`` must equal topology ``ranks``;
5. every requested observable must be a backend-declared capability AND a
   registered observable spec, and every emitted observation is checked
   through the registry (exact violations raise: they are bugs).

Per-config run records in the append-only evidence store are intentionally
NOT written here: the sweep table records per-config input hashes and
observable results itself; linking sweep rows to store runs is a later
increment once a claim needs it (fence: E0, no claims).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from essun import __version__
from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar
from essun.backends.analytical import l0_recursive_doubling
from essun.backends.analytical import l0_torus2d
from essun.contracts import REPO_ROOT, load_yaml, sha256_of
from essun.evidence.store import canonical_json
from essun.observables import check as check_observable
from essun.observables import lookup as lookup_observable
from essun.observables import registered as registered_observables
from essun.workload import w1

DEFAULT_OBSERVABLES = ("O-CONSERVATION", "O-CCT")


class SweepError(Exception):
    """A sweep manifest or one of its configs violates a contract.

    Raised for unknown algorithms, undeclared fabric pairings, capability
    gaps, baseline mismatches, and non-deterministic rewrites — always
    BEFORE or INSTEAD OF producing a table that would silently narrow the
    comparison.
    """


@dataclass(frozen=True)
class AlgorithmSpec:
    """One registered L0 algorithm: module, loader, executor, fabrics.

    ``topology_classes`` lists the fabric classes this algorithm's identity
    is declared for (the ``topology_class`` field of the topology YAML);
    any other pairing is a different identity and is rejected explicitly.
    """

    algorithm_id: str
    module: Any
    load_config: Callable[[dict], Any]
    execute: Callable[[list, Any], dict]
    topology_classes: tuple[str, ...]


ALGORITHMS: dict[str, AlgorithmSpec] = {
    spec.algorithm_id: spec
    for spec in (
        AlgorithmSpec(
            algorithm_id="allreduce_ring",
            module=l0,
            load_config=l0.load_infra,
            execute=l0.execute,
            topology_classes=("unidirectional_ring",),
        ),
        AlgorithmSpec(
            algorithm_id="allreduce_crossbar",
            module=l0_crossbar,
            load_config=l0_crossbar.load_crossbar_config,
            execute=l0_crossbar.execute,
            topology_classes=("fully_connected_crossbar",),
        ),
        AlgorithmSpec(
            algorithm_id="allreduce_recursive_doubling",
            module=l0_recursive_doubling,
            load_config=l0_recursive_doubling.load_recursive_doubling_config,
            execute=l0_recursive_doubling.execute,
            topology_classes=("fully_connected_exchange",),
        ),
        AlgorithmSpec(
            algorithm_id="allreduce_torus2d",
            module=l0_torus2d,
            load_config=l0_torus2d.load_torus2d_config,
            execute=l0_torus2d.execute,
            topology_classes=("torus2d_ring_x_ring",),
        ),
    )
}


@dataclass(frozen=True)
class SweepConfig:
    """One expanded grid cell: (algorithm, topology file, payload size)."""

    index: int
    config_id: str
    spec: AlgorithmSpec
    topology_path: Path
    topology_sha256: str
    payload_bytes: int


# ---------------------------------------------------------------------------
# Manifest loading and validation
# ---------------------------------------------------------------------------


def load_sweep_manifest(path: Path) -> dict:
    path = Path(path)
    manifest = load_yaml(path)
    if not isinstance(manifest, dict):
        raise SweepError(f"sweep manifest {path} is not a mapping")
    return manifest


def _validate_manifest(manifest: dict, source: str) -> None:
    def fail(message: str) -> None:
        raise SweepError(f"sweep manifest {source}: {message}")

    if not isinstance(manifest.get("sweep"), str) or not manifest["sweep"]:
        fail("a non-empty 'sweep' name is required")
    if not isinstance(manifest.get("workload"), str):
        fail("'workload' must be a path (repo-relative) to one workload file")

    grid = manifest.get("grid")
    if not isinstance(grid, dict):
        fail("'grid' must be a mapping with 'algorithms' and 'payload_sizes_bytes'")

    sizes = grid.get("payload_sizes_bytes")
    if not isinstance(sizes, list) or not sizes:
        fail("'grid.payload_sizes_bytes' must be a non-empty list of integer byte counts")
    for size in sizes:
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            fail(f"payload size {size!r} is not a positive integer byte count")
    if len(set(sizes)) != len(sizes):
        fail(f"duplicate payload sizes in {sizes}")

    entries = grid.get("algorithms")
    if not isinstance(entries, list) or not entries:
        fail("'grid.algorithms' must be a non-empty list")

    unknown: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"grid algorithm entry {entry!r} is not a mapping")
        algorithm = entry.get("algorithm")
        if not isinstance(algorithm, str):
            fail(f"grid algorithm entry {entry!r} needs an 'algorithm' id")
        if algorithm not in ALGORITHMS:
            unknown.append(algorithm)
            continue
        topologies = entry.get("topologies")
        if not isinstance(topologies, list) or not topologies:
            fail(f"algorithm {algorithm!r} needs a non-empty 'topologies' list")
        for topology in topologies:
            if not isinstance(topology, str):
                fail(f"topology {topology!r} of algorithm {algorithm!r} is not a path")
            pair = (algorithm, topology)
            if pair in seen_pairs:
                fail(f"duplicate grid config (algorithm, topology) pair {pair}")
            seen_pairs.add(pair)
    if unknown:
        raise SweepError(
            f"sweep manifest {source}: unknown algorithm(s) {unknown}; "
            f"registered: {sorted(ALGORITHMS)}"
        )

    baseline = manifest.get("baseline")
    if not isinstance(baseline, dict):
        fail("'baseline' (algorithm + topology naming the delta reference config) is required")
    if not isinstance(baseline.get("algorithm"), str) or not isinstance(
        baseline.get("topology"), str
    ):
        fail("'baseline' needs 'algorithm' and 'topology' paths")
    if baseline["algorithm"] not in ALGORITHMS:
        raise SweepError(
            f"sweep manifest {source}: unknown baseline algorithm "
            f"{baseline['algorithm']!r}; registered: {sorted(ALGORITHMS)}"
        )

    observables = manifest.get("observables", list(DEFAULT_OBSERVABLES))
    if not isinstance(observables, list) or not observables:
        fail("'observables' must be a non-empty list of registered observable ids")
    unregistered = [o for o in observables if o not in registered_observables()]
    if unregistered:
        fail(f"observable(s) {unregistered} are not registered; registered: {sorted(registered_observables())}")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:  # manifest living outside the repo (e.g. a test tmpdir)
        return str(path.resolve())


def compute_sweep_id(manifest: dict) -> str:
    """sweep_id = sha256(canonical sweep manifest + code version)."""
    body = {"manifest": manifest, "code_version": __version__}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Grid expansion with per-config capability gates
# ---------------------------------------------------------------------------


def expand_grid(manifest: dict, source: str = "<manifest>", base: Path = REPO_ROOT) -> list[SweepConfig]:
    """Expand the grid, validating every config's capability contracts.

    All gates fire BEFORE any model executes: a sweep either runs whole or
    fails with an explicit error — no partial tables, no silently skipped
    configs.
    """
    _validate_manifest(manifest, source)

    workload_path = Path(base) / manifest["workload"]
    if not workload_path.is_file():
        raise SweepError(f"workload file not found: {workload_path}")
    workload_config = w1.load_w1_config(workload_path)

    configs: list[SweepConfig] = []
    sha_cache: dict[Path, str] = {}
    requested = list(manifest.get("observables", DEFAULT_OBSERVABLES))

    def topo_sha(path: Path) -> str:
        if path not in sha_cache:
            sha_cache[path] = sha256_of(path)
        return sha_cache[path]

    index = 0
    for entry in manifest["grid"]["algorithms"]:
        spec = ALGORITHMS[entry["algorithm"]]
        for topology_ref in entry["topologies"]:
            topology_path = Path(base) / topology_ref
            if not topology_path.is_file():
                raise SweepError(
                    f"config #{index}: topology file not found: {topology_path} "
                    f"(algorithm {spec.algorithm_id})"
                )
            topology_data = load_yaml(topology_path)
            topology_class = topology_data.get("topology_class")
            if topology_class not in spec.topology_classes:
                raise SweepError(
                    f"config #{index}: algorithm {spec.algorithm_id!r} is not "
                    f"declared for topology_class {topology_class!r} "
                    f"({topology_ref}); declared fabric classes: "
                    f"{list(spec.topology_classes)} — undeclared pairings are "
                    "different identities and are explicitly unsupported"
                )
            try:
                infra = spec.load_config(topology_data)
            except Exception as exc:  # loaders reject degenerate values explicitly
                raise SweepError(
                    f"config #{index}: topology {topology_ref} rejected by "
                    f"{spec.module.BACKEND_ID}: {exc}"
                ) from exc
            ranks = getattr(infra, "ranks")
            if ranks != workload_config.tp_size:
                raise SweepError(
                    f"config #{index}: workload tp_size {workload_config.tp_size} "
                    f"!= topology ranks {ranks} ({topology_ref}, algorithm "
                    f"{spec.algorithm_id})"
                )

            missing = set(requested) - set(spec.module.CAPABILITIES["observables"])
            if missing:
                raise SweepError(
                    f"config #{index}: backend {spec.module.BACKEND_ID} does not "
                    f"support observable(s) {sorted(missing)}; capabilities: "
                    f"{spec.module.CAPABILITIES}"
                )

            sha = topo_sha(topology_path)
            for size in manifest["grid"]["payload_sizes_bytes"]:
                config_id = (
                    f"c{index:04d}-{spec.algorithm_id}-{infra.topology_id}-{size}"
                )
                configs.append(
                    SweepConfig(
                        index=index,
                        config_id=config_id,
                        spec=spec,
                        topology_path=topology_path,
                        topology_sha256=sha,
                        payload_bytes=size,
                    )
                )
            index += 1

    baseline = manifest["baseline"]
    baseline_pair = (baseline["algorithm"], str(Path(base) / baseline["topology"]))
    grid_pairs = {
        (entry["algorithm"], str(Path(base) / topology))
        for entry in manifest["grid"]["algorithms"]
        for topology in entry["topologies"]
    }
    if baseline_pair not in grid_pairs:
        raise SweepError(
            f"baseline config (algorithm {baseline['algorithm']!r}, topology "
            f"{baseline['topology']!r}) is not part of the grid; the delta "
            "column needs the baseline present at every payload size"
        )
    return configs


# ---------------------------------------------------------------------------
# Sweep execution and table emission
# ---------------------------------------------------------------------------


def _execute_config(config: SweepConfig, workload_config, requested: list[str]) -> dict:
    """Execute one config through its L0 model and gate its observables."""
    workload_for_size = dataclasses.replace(
        workload_config, allreduce_bytes=config.payload_bytes
    )
    ops = w1.generate_w1_ops(workload_for_size)
    infra = config.spec.load_config(load_yaml(config.topology_path))
    observations = config.spec.execute(ops, infra)

    registry_results = []
    for observable_id in requested:
        spec = lookup_observable(observable_id)
        result = check_observable(
            spec, observations["observables"][observable_id]
        )
        registry_results.append(
            {"observable_id": observable_id, "status": result.status}
        )

    conservation = observations["observables"]["O-CONSERVATION"]
    cct = observations["observables"]["O-CCT"]
    return {
        "backend_id": observations["backend_id"],
        "ops": len(observations["per_op"]),
        "per_rank_wire_bytes_exact": observations["per_op"][0][
            "per_rank_wire_bytes_exact"
        ],
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
    }


def run_sweep(manifest_path, results_root=None) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_sweep_manifest(manifest_path)
    configs = expand_grid(manifest, source=str(manifest_path))

    workload_path = REPO_ROOT / manifest["workload"]
    workload_config = w1.load_w1_config(workload_path)
    requested = list(manifest.get("observables", DEFAULT_OBSERVABLES))

    rows = []
    for config in configs:
        executed = _execute_config(config, workload_config, requested)
        rows.append(
            {
                "config_id": config.config_id,
                "index": config.index,
                "algorithm": config.spec.algorithm_id,
                "backend_id": executed["backend_id"],
                "topology": {
                    "path": _rel(config.topology_path),
                    "sha256": config.topology_sha256,
                },
                "payload_bytes": config.payload_bytes,
                "input_hashes": {
                    "workload_sha256": sha256_of(workload_path),
                    "topology_sha256": config.topology_sha256,
                },
                "ops": executed["ops"],
                "per_rank_wire_bytes_exact": executed["per_rank_wire_bytes_exact"],
                "o_conservation": executed["o_conservation"],
                "o_cct": executed["o_cct"],
                "observable_registry": executed["observable_registry"],
                "delta_vs_baseline": None,  # filled below
            }
        )

    # Relative deltas vs the named baseline, matched per payload size (a
    # delta across different payload sizes would be meaningless). The
    # baseline is a full (algorithm, topology) config from the grid.
    baseline = manifest["baseline"]
    baseline_topology_rel = _rel(REPO_ROOT / baseline["topology"])
    by_key = {
        (row["payload_bytes"], row["algorithm"], row["topology"]["path"]): row
        for row in rows
    }
    baseline_ids: dict[str, str] = {}
    for size in manifest["grid"]["payload_sizes_bytes"]:
        baseline_row = by_key.get(
            (size, baseline["algorithm"], baseline_topology_rel)
        )
        if baseline_row is None:
            raise SweepError(
                f"baseline config (algorithm {baseline['algorithm']!r}, "
                f"topology {baseline['topology']!r}) is missing at payload "
                f"size {size}; the delta column needs the baseline at every size"
            )
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
            "algorithm": baseline["algorithm"],
            "topology": baseline["topology"],
            "config_ids_by_payload_bytes": baseline_ids,
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
                raise SweepError(
                    f"sweep {sweep_id} already exists with different {name} "
                    "bytes; sweep outputs are deterministic — a byte drift is "
                    "a bug, not a new result"
                )
    else:
        sweep_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in expected.items():
            (sweep_dir / name).write_bytes(payload)

    return {"sweep_id": sweep_id, "sweep_dir": sweep_dir, "table": table}


# ---------------------------------------------------------------------------
# Human table rendering (deterministic: derived only from the table dict)
# ---------------------------------------------------------------------------


def _fmt_pct(delta: Fraction) -> str:
    return f"{float(delta * 100):.4f}"


def render_table_md(table: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Sweep `{table['sweep']}` — L0 analytical comparison table")
    lines.append("")
    lines.append(f"Sweep id: `{table['sweep_id']}`")
    lines.append("")
    lines.append(
        "E0 evidence only. Every value below is the output of a closed-form "
        "L0 analytical identity under explicit free parameters (B, L, ranks, "
        "payload size) — this table compares analytical identities, NOT "
        "empirical performance, and nothing here is measured on hardware. "
        "The delta columns are arithmetic facts of those identities (same "
        "workload shape, same payload size), not measured speedups."
    )
    lines.append("")
    workload = table["workload"]
    lines.append(f"- manifest: `{table['manifest_path']}` (sha256 `{table['manifest_sha256']}`)")
    lines.append(
        f"- workload: `{workload['path']}` (sha256 `{workload['sha256']}`) — "
        f"tp_size {workload['tp_size']}, layers {workload['layers']}, steps "
        f"{workload['steps']} ({workload['layers'] * workload['steps']} ops per config)"
    )
    lines.append(f"- code version: {table['code_version']}")
    baseline = table["baseline"]
    lines.append(
        f"- baseline: `{baseline['algorithm']}` on `{baseline['topology']}`, "
        "matched per payload size (deltas compare same-size configs)"
    )
    lines.append("")
    lines.append(
        "| config id | algorithm | topology | payload B | O-CONSERVATION | "
        "wire B/rank (exact) | CCT mean ns (exact) | CCT mean ns (float) | "
        "delta vs baseline (exact) | delta vs baseline (%) |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    for row in table["configs"]:
        delta = row["delta_vs_baseline"]
        lines.append(
            "| {config_id} | {algorithm} | {topology} | {payload} | "
            "{violations} violations | {wire} | {cct_exact} | {cct_float} | "
            "{delta_exact} | {delta_pct} |".format(
                config_id=row["config_id"],
                algorithm=row["algorithm"],
                topology=row["topology"]["path"].split("/")[-1],
                payload=row["payload_bytes"],
                violations=row["o_conservation"]["violations"],
                wire=row["per_rank_wire_bytes_exact"],
                cct_exact=row["o_cct"]["completion_time_ns_mean_exact"],
                cct_float=row["o_cct"]["completion_time_ns_mean"],
                delta_exact=delta["delta_exact"],
                delta_pct=_fmt_pct(Fraction(delta["delta_exact"])),
            )
        )
    lines.append("")
    lines.append(
        "Generated deterministically from the sweep manifest (canonical "
        "JSON, exact Fractions, no wall-clock); byte-identical on replay "
        "(tests/determinism/test_sweep_replay.py)."
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a sweep manifest and emit the comparison tables"
    )
    parser.add_argument("manifest", help="path to the sweep manifest YAML")
    parser.add_argument(
        "--results-root",
        default=None,
        help="results root (default: <repo>/results); tables land under sweeps/<sweep_id>/",
    )
    args = parser.parse_args(argv)
    result = run_sweep(args.manifest, results_root=args.results_root)
    print(
        json.dumps(
            {"sweep_id": result["sweep_id"], "sweep_dir": str(result["sweep_dir"])},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
