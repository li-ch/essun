"""Atlas cell 32r-l05 execution vehicle — rank class 32 x L0.5 family.

The L0.5 serialized-ring module (essun.backends.analytical.l05) is
deliberately unregistered in both run-path registries (its own step
fence: "run-path/golden integration is a separate capability-gated
step"):

- sweep runner (essun/orchestrator/sweeps.py) — registry holds only the four
  AllReduce ids; a manifest naming the L0.5 id fails
  ``unknown algorithm(s) ['allreduce_ring_l05']; registered: [...]``;
- run path (essun/orchestrator/runs.py) — BACKENDS holds the five L0
  models plus the ASTRA-sim adapter; a manifest naming the backend fails
  ``unknown backend(s) ['analytical_l05']; registered: [...]``.

Both rejections were re-exercised LIVE at rank class 32 during this stage
on the rank-32 configs (workload w1_dense_tp_decode_tp32.yaml, topology
ring32_l05_free_params.yaml — exact strings recorded on
docs/atlas/32r-l05.md) and reproduce the rank-4, rank-8 and rank-16
strings verbatim: the gap is structural and rank-independent. This script
is therefore the cell's execution vehicle — the rank-32 mirror of
experiments/atlas/4r_l05/run_atlas_4r_l05_cell.py,
experiments/atlas/8r_l05/run_atlas_8r_l05_cell.py and
experiments/atlas/16r_l05/run_atlas_16r_l05_cell.py — mirroring the sweep
runner's discipline WITHOUT touching src/: classified, not fixed.

Gates mirrored from the sweep runner (a bypass is a bug):

1. the L0.5 topology loads through the module's OWN loader
   (l05.load_l05_config — wrong topology_class, degenerate ranks, and
   non-positive B/L/I are rejected there);
2. the baseline topology loads through l0.load_infra;
3. workload tp_size == ranks for both configs;
4. every requested observable is an l05-declared capability AND a
   registered observable spec, and every emitted observation is checked
   through the registry (exact violations raise: they are bugs);
5. every row is rederived INDEPENDENTLY from the closed forms
   (Fractions from the manifest's free parameters — never by calling the
   model a second time); a mismatch raises.

Determinism/content addressing, same formulas as sweeps.py: canonical JSON
(sort_keys), exact Fractions as strings, no wall-clock in artifacts;
cell_id = sha256(canonical manifest + code version); an existing output
directory with different bytes is an error, never a silent overwrite.

Usage (repo root):
    .venv/bin/python experiments/atlas/32r_l05/run_atlas_32r_l05_cell.py \
        experiments/atlas/32r_l05/atlas_32r_l05_cell_v1.yaml
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from essun import __version__
from essun.backends.analytical import l0, l05
from essun.contracts import REPO_ROOT, load_yaml, sha256_of
from essun.evidence.store import canonical_json
from essun.observables import check as check_observable
from essun.observables import lookup as lookup_observable
from essun.observables import registered as registered_observables
from essun.workload import w1

OBSERVABLES = ("O-CONSERVATION", "O-CCT")


class CellError(Exception):
    """The cell manifest or one of its configs violates a contract."""


def compute_cell_id(manifest: dict) -> str:
    """cell_id = sha256(canonical cell manifest + code version) — the
    same content-addressing formula as sweeps.compute_sweep_id."""
    body = {"manifest": manifest, "code_version": __version__}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _fmt_pct(delta: Fraction) -> str:
    return f"{float(delta * 100):.4f}"


def _human(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    value, unit = Fraction(size), 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    if value.denominator == 1:
        return f"{value.numerator} {units[unit]}"
    return f"{float(value):g} {units[unit]}"


def _load_manifest(path: Path) -> dict:
    manifest = load_yaml(path)
    if not isinstance(manifest, dict) or not manifest.get("cell"):
        raise CellError(f"cell manifest {path}: a non-empty 'cell' name is required")
    sizes = manifest.get("grid", {}).get("payload_sizes_bytes")
    if not isinstance(sizes, list) or not sizes:
        raise CellError("grid.payload_sizes_bytes must be a non-empty integer list")
    if manifest.get("observables", list(OBSERVABLES)) != list(OBSERVABLES):
        raise CellError(f"this vehicle executes exactly {list(OBSERVABLES)}")
    unregistered = [o for o in manifest.get("observables", OBSERVABLES) if o not in registered_observables()]
    if unregistered:
        raise CellError(f"observable(s) {unregistered} are not registered")
    return manifest


def _execute_config(observations: dict, requested: list[str], label: str) -> dict:
    """Registry-gate one config's observations (sweeps.py gate 5)."""
    missing = set(requested) - set(observations["observables"])
    if missing:
        raise CellError(f"{label}: emitted observations missing {sorted(missing)}")
    registry_results = []
    for observable_id in requested:
        spec = lookup_observable(observable_id)
        result = check_observable(spec, observations["observables"][observable_id])
        registry_results.append({"observable_id": observable_id, "status": result.status})
    conservation = observations["observables"]["O-CONSERVATION"]
    cct = observations["observables"]["O-CCT"]
    return {
        "backend_id": observations["backend_id"],
        "ops": len(observations["per_op"]),
        "per_rank_wire_bytes_exact": observations["per_op"][0]["per_rank_wire_bytes_exact"],
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


def run_cell(manifest_path: Path, results_root: Path | None = None) -> dict:
    manifest_path = Path(manifest_path)
    manifest = _load_manifest(manifest_path)
    requested = list(manifest.get("observables", OBSERVABLES))

    workload_path = REPO_ROOT / manifest["workload"]
    if not workload_path.is_file():
        raise CellError(f"workload file not found: {workload_path}")
    workload_config = w1.load_w1_config(workload_path)

    l05_topo_path = REPO_ROOT / manifest["algorithms"][0]["topology"]
    baseline_topo_path = REPO_ROOT / manifest["baseline"]["topology"]
    for path in (l05_topo_path, baseline_topo_path):
        if not path.is_file():
            raise CellError(f"topology file not found: {path}")

    # Gates 1-2: module-own loaders reject degenerate/wrong-class configs.
    l05_config = l05.load_l05_config(load_yaml(l05_topo_path))
    l0_config = l0.load_infra(load_yaml(baseline_topo_path))

    # Gate 3: workload tp_size == ranks for both configs.
    for config, label in ((l05_config, "l05"), (l0_config, "baseline")):
        if config.ranks != workload_config.tp_size:
            raise CellError(
                f"{label}: workload tp_size {workload_config.tp_size} != topology ranks {config.ranks}"
            )
    if (l05_config.ranks, l05_config.link_bytes_per_ns, l05_config.hop_latency_ns) != (
        l0_config.ranks,
        l0_config.link_bytes_per_ns,
        l0_config.hop_latency_ns,
    ):
        raise CellError(
            "fairness rule violated: L0.5 and baseline must share ranks, B and L"
        )

    # Gate 4: requested observables must be l05-declared capabilities.
    missing = set(requested) - set(l05.CAPABILITIES["observables"])
    if missing:
        raise CellError(
            f"l05 backend does not support observable(s) {sorted(missing)}; "
            f"capabilities: {l05.CAPABILITIES}"
        )

    rows = []
    for size in manifest["grid"]["payload_sizes_bytes"]:
        workload_for_size = replace(workload_config, allreduce_bytes=size)
        ops = w1.generate_w1_ops(workload_for_size)

        l05_obs = l05.execute(ops, l05_config)
        l0_obs = l0.execute(ops, l0_config)
        executed_l05 = _execute_config(l05_obs, requested, f"l05@{size}")
        executed_l0 = _execute_config(l0_obs, requested, f"baseline@{size}")

        t_l05 = Fraction(l05_obs["observables"]["O-CCT"]["completion_time_ns_mean_exact"])
        t_l0 = Fraction(l0_obs["observables"]["O-CCT"]["completion_time_ns_mean_exact"])
        delta = (t_l05 - t_l0) / t_l0

        # Gate 5: independent closed-form rederivation (module identities
        # spelled out here, evaluated from the manifest's parameters —
        # never by calling the model again). A mismatch is a model bug.
        r, B, L = (
            Fraction(l05_config.ranks),
            l05_config.link_bytes_per_ns,
            l05_config.hop_latency_ns,
        )
        I = l05_config.injection_bytes_per_ns
        if I is None:
            raise CellError("this atlas cell executes a finite I (A-L05-INJ), not the injection limit")
        M = Fraction(size)
        closed_ring = 2 * (r - 1) / r * M / B + 2 * (r - 1) * L
        closed_l05 = 2 * (r - 1) * (M / (r * I) + M / (r * B) + L)
        closed_term = 2 * (r - 1) / r * M / I
        if t_l0 != closed_ring or t_l05 != closed_l05 or t_l05 - t_l0 != closed_term:
            raise CellError(
                f"closed-form rederivation mismatch at M={size}: "
                f"t_l0 {t_l0} vs {closed_ring}, t_l05 {t_l05} vs {closed_l05}, "
                f"disagreement {t_l05 - t_l0} vs {closed_term}"
            )

        per_op = l05_obs["per_op"][0]
        rows.append(
            {
                "payload_bytes": size,
                "chunk_bytes_exact": per_op["chunk_bytes_exact"],
                "transfers_per_phase": per_op["transfers_per_phase"],
                "phases": per_op["phases"],
                "per_transfer": per_op["per_transfer"],
                "per_rank_wire_bytes_exact": executed_l05["per_rank_wire_bytes_exact"],
                "ring_cct_ns_exact": str(t_l0),
                "ring_cct_ns": float(t_l0),
                "l05_cct_ns_exact": str(t_l05),
                "l05_cct_ns": float(t_l05),
                "serialization_term_ns_exact": str(t_l05 - t_l0),
                "delta_vs_baseline": {
                    "baseline": "allreduce_ring (in-grid)",
                    "delta_exact": str(delta),
                    "delta_float": float(delta),
                },
                "o_conservation": executed_l05["o_conservation"],
                "observable_registry": executed_l05["observable_registry"],
            }
        )

    cell_id = compute_cell_id(manifest)
    table = {
        "cell": manifest["cell"],
        "cell_id": cell_id,
        "code_version": __version__,
        "evidence_level": "E0",
        "execution_vehicle": "experiments/atlas/32r_l05/run_atlas_32r_l05_cell.py (module-direct; both run-path registries reject analytical_l05 — see docs/atlas/32r-l05.md)",
        "manifest_path": str(manifest_path.relative_to(REPO_ROOT)) if manifest_path.is_relative_to(REPO_ROOT) else str(manifest_path),
        "manifest_sha256": sha256_of(manifest_path),
        "workload": {
            "path": str(workload_path.relative_to(REPO_ROOT)),
            "sha256": sha256_of(workload_path),
            "tp_size": workload_config.tp_size,
            "layers": workload_config.layers,
            "steps": workload_config.steps,
            "allreduce_bytes_in_workload_file": workload_config.allreduce_bytes,
            "payload_bytes_source": "grid.payload_sizes_bytes (overridden per row)",
        },
        "baseline": {
            "algorithm": manifest["baseline"]["algorithm"],
            "topology": manifest["baseline"]["topology"],
            "sha256": sha256_of(baseline_topo_path),
        },
        "l05": {
            "algorithm": manifest["algorithms"][0]["algorithm"],
            "topology": manifest["algorithms"][0]["topology"],
            "sha256": sha256_of(l05_topo_path),
            "link_bytes_per_ns_exact": str(l05_config.link_bytes_per_ns),
            "hop_latency_ns_exact": str(l05_config.hop_latency_ns),
            "injection_bytes_per_ns_exact": str(l05_config.injection_bytes_per_ns),
        },
        "observables": requested,
        "rows": rows,
    }

    table_json_bytes = (canonical_json(table) + "\n").encode("utf-8")
    table_md_bytes = (render_table_md(table) + "\n").encode("utf-8")

    results_root = Path(results_root) if results_root else REPO_ROOT / "results"
    cell_dir = results_root / "atlas" / "32r_l05" / cell_id
    expected = {"table.json": table_json_bytes, "table.md": table_md_bytes}
    if cell_dir.exists():
        for name, payload in expected.items():
            path = cell_dir / name
            if not path.is_file() or path.read_bytes() != payload:
                raise CellError(
                    f"cell {cell_id} already exists with different {name} bytes; "
                    "cell outputs are deterministic — a byte drift is a bug, "
                    "not a new result"
                )
    else:
        cell_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in expected.items():
            (cell_dir / name).write_bytes(payload)

    return {"cell_id": cell_id, "cell_dir": cell_dir, "table": table}


def render_table_md(table: dict) -> str:
    l05_meta = table["l05"]
    lines = [
        f"# Atlas cell `{table['cell']}` — rank class 32 x L0.5, deltas vs ring baseline",
        "",
        f"Cell id: `{table['cell_id']}`",
        "",
        "E0 evidence only. Every value below is the output of a closed-form "
        "L0.5/L0 analytical identity under explicit free parameters "
        f"(B = {l05_meta['link_bytes_per_ns_exact']} bytes/ns, "
        f"L = {l05_meta['hop_latency_ns_exact']} ns, "
        f"I = {l05_meta['injection_bytes_per_ns_exact']} bytes/ns, ranks = "
        f"{table['workload']['tp_size']}) — this table compares analytical "
        "identities, NOT empirical performance, and nothing here is measured "
        "on hardware. The delta column is an arithmetic fact of the "
        "identities (same workload shape, same payload size).",
        "",
        f"- manifest: `{table['manifest_path']}` (sha256 `{table['manifest_sha256']}`)",
        f"- workload: `{table['workload']['path']}` (sha256 `{table['workload']['sha256']}`) — "
        f"tp_size {table['workload']['tp_size']}, layers {table['workload']['layers']}, "
        f"steps {table['workload']['steps']} "
        f"({table['workload']['layers'] * table['workload']['steps']} ops per row)",
        f"- baseline: `{table['baseline']['algorithm']}` on `{table['baseline']['topology']}`, carried in-grid",
        f"- L0.5 topology: `{table['l05']['topology']}` (sha256 `{table['l05']['sha256']}`)",
        f"- execution vehicle: {table['execution_vehicle']}",
        f"- code version: {table['code_version']}",
        "",
        "| payload B | payload (human) | chunk c = M/r (exact) | per-transfer c/I + c/B + L (exact) | "
        "wire B/rank (exact) | ring CCT ns (exact) | L0.5 CCT ns (exact) | "
        "serialization term t_L05 - t_L0 (exact) | delta vs ring baseline (exact) | delta (%) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in table["rows"]:
        per_transfer = row["per_transfer"]
        transfer_exact = (
            f"{per_transfer['serialization_ns_exact']} + "
            f"{per_transfer['wire_ns_exact']} + "
            f"{per_transfer['hop_latency_ns_exact']}"
        )
        lines.append(
            "| {payload} | {human} | {chunk} | {transfer} | {wire} | {ring} | {l05cct} | "
            "{term} | {delta_exact} | {delta_pct} |".format(
                payload=row["payload_bytes"],
                human=_human(row["payload_bytes"]),
                chunk=row["chunk_bytes_exact"],
                transfer=transfer_exact,
                wire=row["per_rank_wire_bytes_exact"],
                ring=row["ring_cct_ns_exact"],
                l05cct=row["l05_cct_ns_exact"],
                term=row["serialization_term_ns_exact"],
                delta_exact=row["delta_vs_baseline"]["delta_exact"],
                delta_pct=_fmt_pct(Fraction(row["delta_vs_baseline"]["delta_exact"])),
            )
        )
    lines.append("")
    lines.append(
        "Generated deterministically from the cell manifest (canonical JSON, "
        "exact Fractions, no wall-clock); byte-identical on replay. Every "
        "row rederived independently from the closed forms before emission."
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute the 32r-l05 atlas cell (L0.5 vs ring baseline)"
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(Path(__file__).parent / "atlas_32r_l05_cell_v1.yaml"),
        help="path to the cell manifest YAML (default: the sibling v1 manifest)",
    )
    args = parser.parse_args(argv)
    result = run_cell(Path(args.manifest))
    print(
        json.dumps(
            {"cell_id": result["cell_id"], "cell_dir": str(result["cell_dir"])},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
