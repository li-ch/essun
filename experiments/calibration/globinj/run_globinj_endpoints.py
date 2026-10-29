"""GLOB-INJ endpoint store runs — the two registered-range endpoints of
the A-L05-INJ axis (I = 1 and I = 1024 B/ns) as append-only
content-addressed evidence-store runs (Q1 calibration-ladder GLOBAL
stage 3 of 4).

The run path (essun.orchestrator.runs.run_experiment) cannot
execute these manifests: analytical_l05 is deliberately unregistered in
its BACKENDS registry per the L0.5 module's own scope fence, and
the live rejection is asserted here (exact substring) before anything
executes — the same structural string recorded by the atlas 4r/8r/16r
l05 cells and re-exercised by this stage's sweep vehicle. This script
is therefore the endpoints' execution vehicle: it mirrors
run_experiment's own gates and record shape WITHOUT touching src/ —
classified, not fixed:

1. the manifest loads through the run path's own loader
   (load_experiment_manifest: schema validation) and its inputs
   resolve + hash through resolve_inputs — the same contract path;
2. exactly one backend, and every declared observable must be an
   l05-declared capability (mirrors run_experiment's gates);
3. the topology loads through l05.load_l05_config (module's own
   loader) and workload tp_size == ranks;
4. every declared observable is checked through the registry (exact
   violations raise: they are bugs), and the declared-observable
   filtering of run records (D-030) is mirrored;
5. the run payload has EXACTLY the run_experiment shape (manifest,
   manifest_path, inputs, code_version, observations_digest) plus an
   ``execution`` provenance block — the same field the run path
   itself adds for external-adapter backends — naming this vehicle and
   the live run-path rejection string, so a stored record always
   says how it was executed;
6. every op is rederived INDEPENDENTLY from the closed forms
   (Fractions from the manifest's free parameters — never a second
   call into the model); a mismatch raises.

claim_id is empty in both manifests, so no claim link is written (a
PROPOSED global sensitivity candidate must not link to any claim).

Determinism: identical manifest + inputs + code version reproduce
byte-identical run records (content-addressed run_id = sha256 of the
canonical payload; put_run is idempotent on identical bytes).

Usage (repo root):
    .venv/bin/python experiments/calibration/globinj/run_globinj_endpoints.py \
        [manifest.yaml ...]   # default: the two endpoint manifests
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from essun import __version__
from essun.backends.analytical import l05
from essun.contracts import (
    REPO_ROOT,
    load_experiment_manifest,
    load_yaml,
    resolve_inputs,
)
from essun.evidence.store import EvidenceStore, canonical_json
from essun.observables import check as check_observable
from essun.observables import lookup as lookup_observable
from essun.orchestrator.runs import ExecutionError, run_experiment
from essun.workload import w1

VEHICLE = "experiments/calibration/globinj/run_globinj_endpoints.py"
DEFAULT_MANIFESTS = (
    "experiments/calibration/globinj/run_globinj_i1_v1.yaml",
    "experiments/calibration/globinj/run_globinj_i1024_v1.yaml",
)


class VehicleError(Exception):
    """An endpoint manifest or its execution violates a contract."""


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def run_endpoint(manifest_path: Path, results_root: Path | None = None) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_experiment_manifest(manifest_path)  # gate 1 (schema)
    inputs = resolve_inputs(manifest)  # gate 1 (paths + hashes)

    # Gate 2: exactly one backend, and it is the L0.5 module this vehicle
    # executes; its live rejection by the run path is asserted.
    if manifest["backends"] != [l05.BACKEND_ID]:
        raise VehicleError(
            f"this vehicle executes exactly ['{l05.BACKEND_ID}'], manifest "
            f"declares {manifest['backends']}"
        )
    try:
        run_experiment(manifest_path)
    except ExecutionError as exc:
        rejection = str(exc)
        if "unknown backend(s)" not in rejection or l05.BACKEND_ID not in rejection:
            raise VehicleError(
                f"run-path rejection changed shape: {rejection!r}; "
                "retire this vehicle in favor of the registered path"
            ) from exc
    else:
        raise VehicleError(
            "run path executed analytical_l05 directly — retire this "
            "vehicle in favor of the registered path (do not keep both)"
        )

    missing = set(manifest["observables"]) - set(l05.CAPABILITIES["observables"])
    if missing:
        raise VehicleError(
            f"backend {l05.BACKEND_ID} does not support observable(s) "
            f"{sorted(missing)}; capabilities: {l05.CAPABILITIES}"
        )
    if manifest.get("claim_id"):
        raise VehicleError(
            "this stage's manifests carry claim_id \"\" deliberately (a "
            "PROPOSED candidate must not link to any claim)"
        )

    # Gate 3: module-own loader; workload kind, tp_size == ranks, and the
    # workload's collectives must be declared capabilities (run gates).
    topology_data = load_yaml(inputs["infra_graph"]["path"])
    try:
        config = l05.load_l05_config(topology_data)
    except Exception as exc:
        raise VehicleError(f"topology rejected by {l05.BACKEND_ID}: {exc}") from exc
    workload_data = load_yaml(inputs["workload_ir"]["path"])
    workload_kind = workload_data.get("workload")
    if workload_kind != w1.WORKLOAD_KIND:
        raise VehicleError(f"this vehicle executes workload kind {w1.WORKLOAD_KIND!r}")
    workload_config = w1.load_w1_config(inputs["workload_ir"]["path"])
    if workload_config.tp_size != config.ranks:
        raise VehicleError(
            f"workload tp_size {workload_config.tp_size} != topology ranks {config.ranks}"
        )
    ops = w1.generate_w1_ops(workload_config)
    supported = {name.rsplit("_", 1)[0] for name in l05.CAPABILITIES["collectives"]}
    unsupported = sorted({op.collective for op in ops} - supported)
    if unsupported:
        raise VehicleError(f"collective(s) {unsupported} not supported by {l05.BACKEND_ID}")

    observations = l05.execute(ops, config)

    # Gate 4: registry checks on every declared observable, and the D-030
    # declared-observable filtering of the stored record.
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
    for observable_id in manifest["observables"]:
        check_observable(
            lookup_observable(observable_id), observations["observables"][observable_id]
        )

    # Gate 6: independent closed-form rederivation of every op (Fractions
    # from the manifest's free parameters — never a second model call).
    r = Fraction(config.ranks)
    B, L = config.link_bytes_per_ns, config.hop_latency_ns
    I = config.injection_bytes_per_ns
    if I is None:
        raise VehicleError("this vehicle executes finite-I endpoint manifests")
    for entry in observations["per_op"]:
        M = Fraction(entry["payload_bytes"])
        chunk = M / r
        closed_t = 2 * (r - 1) * (chunk / I + chunk / B + L)
        closed_l0 = Fraction(2 * (r - 1) * int(M), int(r)) / B + 2 * (r - 1) * L
        closed_term = 2 * (r - 1) * chunk / I
        if (
            Fraction(entry["completion_time_ns_exact"]) != closed_t
            or Fraction(entry["l0_anchor_time_ns_exact"]) != closed_l0
            or Fraction(entry["serialization_term_ns_exact"]) != closed_term
        ):
            raise VehicleError(f"closed-form rederivation mismatch on op {entry['op_id']}")

    run_payload = {
        "manifest": manifest,
        "manifest_path": _rel(manifest_path),
        "inputs": {
            role: {"path": _rel(info["path"]), "sha256": info["sha256"]}
            for role, info in inputs.items()
        },
        "code_version": __version__,
        "observations_digest": hashlib.sha256(
            canonical_json(observations).encode("utf-8")
        ).hexdigest(),
        "execution": {
            "vehicle": VEHICLE,
            "reason": (
                "the run path rejects analytical_l05 live (module "
                "deliberately unregistered in essun/orchestrator/runs.py BACKENDS "
                "per the L0.5 scope fence); this vehicle mirrors "
                "run_experiment's gates and record shape — the 4r/8r/16r "
                "l05 atlas pattern, classified not fixed, no src/ change"
            ),
            "live_run_path_rejection": rejection,
        },
    }
    results_root = Path(results_root) if results_root else REPO_ROOT / "results"
    store = EvidenceStore(results_root)
    run_id = store.put_run(run_payload, observations)  # content-addressed, append-only
    return {"run_id": run_id, "run_dir": store.run_dir(run_id), "observations": observations}


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute the GLOB-INJ endpoint manifests (L0.5 module-direct) into the evidence store"
    )
    parser.add_argument(
        "manifests",
        nargs="*",
        default=list(DEFAULT_MANIFESTS),
        help="endpoint run manifests (default: the two registered-range endpoint manifests)",
    )
    args = parser.parse_args(argv)
    summary = {}
    for manifest in args.manifests:
        result = run_endpoint(REPO_ROOT / manifest)
        summary[manifest] = {"run_id": result["run_id"], "run_dir": str(result["run_dir"])}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
