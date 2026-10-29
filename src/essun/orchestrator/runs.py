"""Experiment execution: manifest -> validated inputs -> dispatched backend -> content-addressed run record.

Deterministic-by-construction: identical manifest, inputs, and code version
produce a byte-identical run record (verified by tests/determinism). Wall-clock
metadata is deliberately kept out of run artifacts.

Dispatch (increment 5a): the experiment manifest selects the topology (the
``infra_graph`` file reference) and the algorithm (the single ``backends``
entry — a registered backend/model id naming one of the five analytical L0
models, or a Docker-pinned external
adapter: ``astra_sim_analytical``), plus the workload (the
``workload_ir`` file reference, whose ``workload:`` kind selects the
generator). Nothing is hardcoded to the ring or to W1 anymore:

    analytical_l0                     ring AllReduce        (unidirectional_ring)
    analytical_l0_crossbar            crossbar AllReduce    (fully_connected_crossbar)
    analytical_l0_torus2d             2D-torus AllReduce    (torus2d_ring_x_ring)
    analytical_l0_recursive_doubling  doubling AllReduce    (fully_connected_exchange)
    analytical_l0_phase_collectives   ReduceScatter/AllGather phases; the topology
                                      class picks the declared family (A-L0P-ALGO):
                                      unidirectional_ring -> ring phases,
                                      fully_connected_exchange -> halving/doubling phases

Capability gates (a bypass is a bug, never a feature) fire BEFORE any model
executes: an unknown backend, more than one backend per run, an unsupported
observable, an undeclared (model, topology_class) pairing, an unknown
workload kind, a workload whose collectives the model does not declare, and
a workload/topology rank mismatch all fail loudly with the gap named. The
observable registry (:mod:`essun.observables`) gates every declared
observable again on the emitted observations (exact violations raise: they
are bugs), and run records are persisted through the append-only evidence
store (:mod:`essun.evidence.store`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from essun import __version__
from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar
from essun.backends.analytical import l0_phase_collectives
from essun.backends.analytical import l0_recursive_doubling
from essun.backends.analytical import l0_tfc
from essun.backends.analytical import l0_torus2d
from essun.backends.astra_sim import adapter as astra_sim_analytical
from essun.backends.uet_htsim import adapter as uet_htsim_cms
from essun.contracts import (
    REPO_ROOT,
    load_experiment_manifest,
    load_yaml,
    resolve_inputs,
)
from essun.evidence.dimensions import (
    RUN_RECORD_SCHEMA_VERSION,
    dimensions_from_manifest,
)
from essun.evidence.store import EvidenceStore, canonical_json  # noqa: F401 (re-exported)
from essun.observables import check as check_observable
from essun.observables import lookup as lookup_observable
from essun.workload import w1
from essun.workload import w2
from essun.workload import w3
from essun.workload import w5

# The deterministic orchestrator, not an agent, owns execution (IMPLEMENTATION_GUIDE §2).
# In-process analytical models plus the Docker-pinned external adapters
# (ASTRA-sim analytical; uet-htsim CMS, the independent third
# backend): modules here need BACKEND_ID + CAPABILITIES; an adapter that owns
# its whole validate->compile->execute->parse pipeline additionally exposes
# ``execute_experiment`` and takes the branch below instead of DISPATCH.
BACKENDS = {
    module.BACKEND_ID: module
    for module in (
        l0,
        l0_crossbar,
        l0_torus2d,
        l0_recursive_doubling,
        l0_phase_collectives,
        l0_tfc,  # flagship slice: executes UEC11-FC-R02 (TFC admission law)
        astra_sim_analytical,
        uet_htsim_cms,
    )
}

# Workload dispatch: the workload file's `workload:` kind selects
# (config loader, op generator). Kinds are the generators' own constants.
# W3 registers its kind knowing no backend executes all-to-all yet,
# and W5 likewise: W5's ops are MEMORY-SEMANTIC (kv_alloc/kv_write/
# kv_transfer/kv_visible/kv_read/kv_release), declared by no backend. A W3
# or W5 manifest must fail the collective capability gate below, loudly —
# that rejection is a tested behavior (tests/negative/test_dispatch_gates.py),
# not a run path that silently fakes MoE or KV traffic on an AllReduce model.
WORKLOADS = {
    w1.WORKLOAD_KIND: (w1.load_w1_config, w1.generate_w1_ops),
    w2.WORKLOAD_KIND: (w2.load_w2_config, w2.generate_w2_ops),
    w3.WORKLOAD_KIND: (w3.load_w3_config, w3.generate_w3_ops),
    w5.WORKLOAD_KIND: (w5.load_w5_config, w5.generate_w5_ops),
}

# Model dispatch: for each registered backend/model id, the fabric loader and
# executor for every topology_class its identity is declared for. An
# undeclared (model, topology_class) pairing is a different identity (the
# same pairing rule as orchestrator/sweeps.py gate 2 and A-L0P-ALGO) and is
# rejected explicitly — never silently re-routed.
DISPATCH = {
    l0.BACKEND_ID: {
        "unidirectional_ring": (l0.load_infra, l0.execute),
    },
    l0_crossbar.BACKEND_ID: {
        "fully_connected_crossbar": (
            l0_crossbar.load_crossbar_config,
            l0_crossbar.execute,
        ),
    },
    l0_torus2d.BACKEND_ID: {
        "torus2d_ring_x_ring": (l0_torus2d.load_torus2d_config, l0_torus2d.execute),
    },
    l0_recursive_doubling.BACKEND_ID: {
        "fully_connected_exchange": (
            l0_recursive_doubling.load_recursive_doubling_config,
            l0_recursive_doubling.execute,
        ),
    },
    l0_phase_collectives.BACKEND_ID: {
        # A-L0P-ALGO: ring phases run on the ring fabric (l0 loader);
        # halving/doubling phases run on the power-of-two exchange fabric
        # (l0d loader). Other fabric classes are undeclared pairings.
        "unidirectional_ring": (
            l0.load_infra,
            l0_phase_collectives.execute_ring_phases,
        ),
        "fully_connected_exchange": (
            l0_recursive_doubling.load_recursive_doubling_config,
            l0_phase_collectives.execute_doubling_phases,
        ),
    },
    l0_tfc.BACKEND_ID: {
        # Flagship slice (D1 build order item 2): the TFC credit-windowed
        # ring executes UEC requirement UEC11-FC-R02 (binding
        # BIND-UEC11-FC-R02-L0TFC, essun.specir.bindings). Only its own
        # topology class loads — an unbound ring must not silently run
        # windowed and a TFC window must not silently vanish.
        "unidirectional_ring_tfc_window": (l0_tfc.load_tfc_config, l0_tfc.execute),
    },
}


class ExecutionError(Exception):
    """Raised when an experiment cannot run as declared (capability or registration gap)."""


def _rel(path: Path) -> str:
    """Repo-relative path when possible; absolute for out-of-repo inputs
    (e.g. test fixtures), mirroring orchestrator/sweeps.py."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _supported_collectives(backend) -> set[str]:
    """Collective names a backend declares, stripped of their algorithm suffix.

    ``CAPABILITIES['collectives']`` entries are (collective, algorithm) pairs
    like 'allreduce_ring' or 'reducescatter_recursive_halving'; the workload
    ops carry the bare collective name ('allreduce', 'reducescatter').
    """
    return {name.rsplit("_", 1)[0] for name in backend.CAPABILITIES["collectives"]}


def run_experiment(manifest_path, results_root=None) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_experiment_manifest(manifest_path)
    inputs = resolve_inputs(manifest)

    # D3 orthogonal evidence dimensions: the manifest MAY declare the
    # five-field block (verification / calibration_target / held_out /
    # independent_reproduction / known_omissions); the block is validated
    # HERE, before any backend executes — a malformed declaration fails
    # loudly with nothing run. A manifest without the block leaves the run
    # payload byte-identical to the pre-D3 format (already-stored run_ids
    # reproduce; the fields then read UNKNOWN, never false).
    try:
        evidence_dimensions = dimensions_from_manifest(manifest)
    except ValueError as exc:
        raise ExecutionError(
            f"manifest {manifest_path} declares an invalid "
            f"evidence_dimensions block: {exc}"
        ) from exc

    unknown = [b for b in manifest["backends"] if b not in BACKENDS]
    if unknown:
        raise ExecutionError(
            f"unknown backend(s) {unknown}; registered: {sorted(BACKENDS)}"
        )
    if len(manifest["backends"]) != 1:
        raise ExecutionError("this increment executes exactly one backend per run")

    backend = BACKENDS[manifest["backends"][0]]
    missing = set(manifest["observables"]) - set(backend.CAPABILITIES["observables"])
    if missing:
        raise ExecutionError(
            f"backend {backend.BACKEND_ID} does not support observable(s) {sorted(missing)}; "
            f"capabilities: {backend.CAPABILITIES}"
        )

    # External-tool backend (the Docker-pinned ASTRA-sim analytical
    # adapter; the Docker-pinned uet-htsim CMS adapter) vs in-process
    # analytical model. The adapter owns validate ->
    # compile -> execute -> parse for its manifest (its validate_experiment
    # enforces the same gates the in-process branch enforces below: topology
    # class, workload kind, rank match, collective support), while the
    # orchestrator keeps the evidence store, observable-registry gate and
    # claim link uniform for every backend.
    execution_provenance = None
    if hasattr(backend, "execute_experiment"):
        executed = backend.execute_experiment(manifest_path)
        observations = executed["observations"]
        execution_provenance = executed["execution"]
    else:
        # In-process analytical model: dispatch by (backend, topology_class).

        # Topology: the infra_graph file reference selects the fabric; its
        # topology_class must be a declared pairing of the selected model.
        topology_data = load_yaml(inputs["infra_graph"]["path"])
        topology_class = topology_data.get("topology_class")
        routes = DISPATCH[backend.BACKEND_ID]
        if topology_class not in routes:
            raise ExecutionError(
                f"backend {backend.BACKEND_ID} is not declared for topology_class "
                f"{topology_class!r} ({manifest['infra_graph']['path']}); declared "
                f"fabric classes: {sorted(routes)} — undeclared pairings are "
                "different identities and are explicitly unsupported"
            )
        load_infra_config, execute_backend = routes[topology_class]
        try:
            infra_config = load_infra_config(topology_data)
        except Exception as exc:  # loaders reject degenerate values explicitly
            raise ExecutionError(
                f"topology {manifest['infra_graph']['path']} rejected by "
                f"{backend.BACKEND_ID}: {exc}"
            ) from exc

        # Workload: the workload file's `workload:` kind selects the generator.
        workload_data = load_yaml(inputs["workload_ir"]["path"])
        workload_kind = workload_data.get("workload")
        if workload_kind not in WORKLOADS:
            raise ExecutionError(
                f"unknown workload kind {workload_kind!r} in "
                f"{manifest['workload_ir']['path']}; registered: {sorted(WORKLOADS)}"
            )
        load_workload_config, generate_ops = WORKLOADS[workload_kind]
        workload_config = load_workload_config(inputs["workload_ir"]["path"])
        if workload_config.tp_size != infra_config.ranks:
            raise ExecutionError(
                f"workload tp_size {workload_config.tp_size} != topology ranks {infra_config.ranks}"
            )

        ops = generate_ops(workload_config)

        # Collective capability gate: every collective the workload issues must
        # be covered by a declared capability entry of the selected model.
        unsupported = sorted(
            {op.collective for op in ops} - _supported_collectives(backend)
        )
        if unsupported:
            raise ExecutionError(
                f"backend {backend.BACKEND_ID} does not support collective(s) "
                f"{unsupported} issued by workload kind {workload_kind!r}; "
                f"declared collective capabilities: "
                f"{list(backend.CAPABILITIES['collectives'])}"
            )

        observations = execute_backend(ops, infra_config)

    # Pin run identity to the manifest's declared observable set :
    # the record contains exactly what the manifest asked for, so growing a
    # backend's emitted output cannot silently shift an already-stored
    # manifest's run_id (the ADD-F cold-tree drill failure mode).
    declared = set(manifest["observables"])
    if set(observations["observables"]) - declared:
        observations = {
            **observations,
            "observables": {
                observable_id: obs
                for observable_id, obs in observations["observables"].items()
                if observable_id in declared
            },
        }

    run_payload = {
        "manifest": manifest,
        "manifest_path": _rel(manifest_path),
        "inputs": {
            role: {
                "path": _rel(info["path"]),
                "sha256": info["sha256"],
            }
            for role, info in inputs.items()
        },
        "code_version": __version__,
        "observations_digest": hashlib.sha256(
            canonical_json(observations).encode("utf-8")
        ).hexdigest(),
    }
    if execution_provenance is not None:
        run_payload["execution"] = execution_provenance
    if evidence_dimensions is not None:
        # D3 dimensions ride the payload as plain content-addressed bytes
        # (deterministic: pure functions of the manifest), stamped with
        # the run-record schema version that introduced them.
        run_payload.update(evidence_dimensions)
        run_payload["evidence_schema_version"] = RUN_RECORD_SCHEMA_VERSION
    results_root = Path(results_root) if results_root else REPO_ROOT / "results"
    store = EvidenceStore(results_root)
    run_id = store.put_run(run_payload, observations)  # content-addressed, append-only

    # Registry policy gate: every observable the manifest declares must be a
    # registered spec and its emitted observation must satisfy that spec's
    # failure policy (exact violations raise: they are bugs).
    for observable_id in manifest["observables"]:
        check_observable(lookup_observable(observable_id), observations["observables"][observable_id])

    if manifest.get("claim_id"):
        store.link_run_to_claim(
            run_id, manifest["claim_id"], relation="declared_by_manifest"
        )
    return {
        "run_id": run_id,
        "run_dir": store.run_dir(run_id),
        "observations": observations,
    }


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run an experiment manifest on registered backends"
    )
    parser.add_argument("manifest", help="path to the experiment manifest YAML")
    args = parser.parse_args(argv)
    result = run_experiment(args.manifest)
    print(json.dumps({"run_id": result["run_id"], "run_dir": str(result["run_dir"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
