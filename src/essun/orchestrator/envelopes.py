"""Envelope runner: named comparators over operating-point grids, with
exact-Fraction reversal detection (design doc D4, 2026-10-29).

This extends the sweep machinery (``orchestrator/sweeps.py``) along the
axis D4 names: instead of ONE fixed operating point per topology file, an
envelope manifest declares

- assumption REGISTRIES as the authority for numeric freedom ranges
  (``experiments/vertical_slice/assumptions_l0.yaml`` /
  ``assumptions_l05.yaml`` / ``assumptions_tfc.yaml`` patterns, and the
  cross-design record ``experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml``);
- FIXED exact operating-point values (each validated inside its registered
  range) and one or more freedom AXES sampled at EXACT grid points
  (Fractions, never floats — see ``orchestrator/opgrids.py``);
- named COMPARATOR MODELS (profile/algorithm identities), each a topology
  file whose bound knobs are overridden by the exact operating point, and
- REVERSAL PAIRS whose ranking is examined for flips along every axis by
  ``orchestrator/reversals.py`` (exact boundaries, verified, never
  interpolated).

The four sweep-registered L0 algorithms are taken from the sweep runner's
own ``ALGORITHMS`` registry (they cannot drift); the envelope adds the two
ring refinements the sweep runner deliberately does not dispatch — the
L0.5 serialized ring and the UEC TFC credit-window ring (the UEC profile's
flagship ``simulated_behavior``: since G8 the credit automaton binding
``BIND-UEC11-FC-R02-AUTOMATON`` executes UEC11-FC-R02 and this ring is
its declared steady-state abstraction).

Every emitted value is the output of the REAL backend's ``execute`` (the
same code the run path and sweeps use), so per-point evaluation carries
every in-model gate (conservation self-checks, the TFC admission
invariant, divisibility) — an envelope row is a executed identity, not a
re-derived formula.

Determinism: the sweep-runner policy — integer byte counts, exact
Fractions serialized as strings, canonical JSON (sort_keys), no
wall-clock. ``envelope_id`` is the SHA-256 of the canonical manifest plus
the code version; the emitted ``reversal.json`` is additionally
CONTENT-ADDRESSED: ``reversal.json.sha256`` records the SHA-256 of the
exact artifact bytes (recorded in the committed experiment record so the
artifact is checkable forever).

Evidence level E0 ONLY, status PROPOSED. An envelope compares ANALYTICAL
MODEL IDENTITIES under declared freedom; a reversal is a statement about
the ranking of those identities — never about measured behavior, and the
artifact language carries no hardware claims.
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
from essun.backends.analytical import l0_tfc
from essun.backends.analytical import l0_torus2d
from essun.backends.analytical import l05
from essun.contracts import REPO_ROOT, load_yaml, sha256_of
from essun.evidence.store import canonical_json
from essun.observables import registered as registered_observables
from essun.orchestrator.opgrids import (
    AssumptionRange,
    FixedParameter,
    GridAxis,
    GridError,
    OperatingPoint,
    build_axis,
    build_fixed,
    expand_operating_points,
    load_ranges,
)
from essun.orchestrator.reversals import detect_reversals
from essun.orchestrator.sweeps import ALGORITHMS
from essun.workload import w1

DEFAULT_OBSERVABLE = "O-CCT"


class EnvelopeError(Exception):
    """An envelope manifest or one of its comparators violates a contract.

    Raised for unknown models, undeclared fabric pairings, unbound or
    out-of-range operating points, non-exact coordinates, ranks
    mismatches, and non-deterministic rewrites — always BEFORE or INSTEAD
    OF producing an artifact that would silently narrow the comparison.
    """


# ---------------------------------------------------------------------------
# Comparator models: the sweep-registered L0 family (imported, not
# duplicated) plus the two envelope-only ring refinements.
# ---------------------------------------------------------------------------


def _ring_identity(message_bytes: int, infra) -> Fraction:
    return l0.ring_allreduce_time_ns(message_bytes, infra.ranks, infra)


def _crossbar_identity(message_bytes: int, infra) -> Fraction:
    return l0_crossbar.crossbar_allreduce_time_ns(message_bytes, infra.ranks, infra)


def _rdoubling_identity(message_bytes: int, infra) -> Fraction:
    return l0_recursive_doubling.rd_allreduce_time_ns(
        message_bytes, infra.ranks, infra
    )


def _torus_identity(message_bytes: int, infra) -> Fraction:
    return l0_torus2d.torus2d_allreduce_time_ns(message_bytes, infra)


def _l05_identity(message_bytes: int, config) -> Fraction:
    return l05.allreduce_time_ns(message_bytes, config.ranks, config)


def _tfc_identity(message_bytes: int, infra) -> Fraction:
    return l0_tfc.ring_allreduce_time_tfc_ns(message_bytes, infra.ranks, infra)


@dataclass(frozen=True)
class EnvelopeModel:
    """One comparator identity: loader, executor, fabric classes, knobs.

    ``knobs`` maps an assumption id to the dotted config path it overrides
    (e.g. ``"link.bytes_per_ns"``); ``bindable`` is the set of assumption
    ids a manifest may legally bind to this model.
    """

    algorithm_id: str
    backend_id: str
    topology_classes: tuple[str, ...]
    load_config: Callable[[dict], Any]
    execute: Callable[[list, Any], dict]
    identity: Callable[[int, Any], Fraction]
    knobs: dict[str, str]
    divisors: Callable[[Any], tuple[int, ...]]
    divisibility_note: str

    def as_dict(self) -> dict:
        return {
            "algorithm_id": self.algorithm_id,
            "backend_id": self.backend_id,
            "topology_classes": list(self.topology_classes),
            "knobs": dict(self.knobs),
        }


def _rank_divisors(config) -> tuple[int, ...]:
    return (config.ranks,)


def _torus_divisors(config) -> tuple[int, ...]:
    return (config.dim1_ranks, config.dim2_ranks)


def _build_models() -> dict[str, EnvelopeModel]:
    models: dict[str, EnvelopeModel] = {}
    # The sweep-registered L0 family, taken from the sweep runner's own
    # registry so the two cannot drift apart.
    sweep_knobs = {
        "allreduce_ring": {
            "link.bytes_per_ns": "B",
            "link.hop_latency_ns": "L",
        },
        "allreduce_crossbar": {
            "nic.injection_bytes_per_ns": "B",
            "link.pair_latency_ns": "L",
        },
        "allreduce_recursive_doubling": {
            "nic.injection_bytes_per_ns": "B",
            "link.pair_latency_ns": "L",
        },
        "allreduce_torus2d": {
            "link.bytes_per_ns": "B",
            "link.hop_latency_ns": "L",
        },
    }
    sweep_identity = {
        "allreduce_ring": _ring_identity,
        "allreduce_crossbar": _crossbar_identity,
        "allreduce_recursive_doubling": _rdoubling_identity,
        "allreduce_torus2d": _torus_identity,
    }
    for algorithm_id, spec in ALGORITHMS.items():
        models[algorithm_id] = EnvelopeModel(
            algorithm_id=algorithm_id,
            backend_id=spec.module.BACKEND_ID,
            topology_classes=spec.topology_classes,
            load_config=spec.load_config,
            execute=spec.execute,
            identity=sweep_identity[algorithm_id],
            knobs=sweep_knobs[algorithm_id],
            divisors=(
                _torus_divisors
                if algorithm_id == "allreduce_torus2d"
                else _rank_divisors
            ),
            divisibility_note=(
                "A-L0T-DIV (both dimension sizes divide the payload)"
                if algorithm_id == "allreduce_torus2d"
                else "A-L0-DIV family (rank count divides the payload)"
            ),
        )
    # Envelope-only comparators: the two ring refinements the sweep runner
    # deliberately does not dispatch (each module documents its own fence).
    models["envelope_l05_ring"] = EnvelopeModel(
        algorithm_id="envelope_l05_ring",
        backend_id=l05.BACKEND_ID,
        topology_classes=(l05.TOPOLOGY_CLASS,),
        load_config=l05.load_l05_config,
        execute=l05.execute,
        identity=_l05_identity,
        knobs={
            "link.bytes_per_ns": "B",
            "link.hop_latency_ns": "L",
            "nic.injection_bytes_per_ns": "I (serialization rate; null = limit)",
        },
        divisors=_rank_divisors,
        divisibility_note="A-L05-DIV (rank count divides the payload)",
    )
    models["envelope_tfc_ring"] = EnvelopeModel(
        algorithm_id="envelope_tfc_ring",
        backend_id=l0_tfc.BACKEND_ID,
        topology_classes=(l0_tfc.TOPOLOGY_CLASS,),
        load_config=l0_tfc.load_tfc_config,
        execute=l0_tfc.execute,
        identity=_tfc_identity,
        knobs={
            "link.bytes_per_ns": "B",
            "link.hop_latency_ns": "L",
            "tfc.window_bytes": "W (credit window, 256-byte units)",
            "tfc.credit_return_latency_ns": "L_cr (credit return)",
        },
        divisors=_rank_divisors,
        divisibility_note="A-TFC-DIV (rank count divides the payload)",
    )
    return models


ENVELOPE_MODELS: dict[str, EnvelopeModel] = _build_models()


# ---------------------------------------------------------------------------
# Manifest loading and validation
# ---------------------------------------------------------------------------


def load_envelope_manifest(path: Path) -> dict:
    path = Path(path)
    manifest = load_yaml(path)
    if not isinstance(manifest, dict):
        raise EnvelopeError(f"envelope manifest {path} is not a mapping")
    return manifest


def _parse_bind_path(path_text, model_id: str, assumption_id: str) -> tuple[str, ...]:
    parts = tuple(str(path_text).split("."))
    if len(parts) < 2 or not all(parts):
        raise EnvelopeError(
            f"model {model_id}: bind {assumption_id} -> {path_text!r} is not a "
            "dotted config path like 'link.bytes_per_ns'"
        )
    return parts


def _walk(data: dict, parts: tuple[str, ...]):
    node = data
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise KeyError(".".join(parts))
        node = node[part]
    return node


def _set_path(data: dict, parts: tuple[str, ...], value) -> None:
    node = data
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value


@dataclass(frozen=True)
class ModelEntry:
    model_id: str
    model: EnvelopeModel
    topology_path: Path
    topology_sha256: str
    binds: dict[str, tuple[str, ...]]  # assumption id -> path parts


def _validate_and_load_models(
    manifest: dict, source: str, base: Path, ranges: dict[str, AssumptionRange]
) -> dict[str, ModelEntry]:
    entries_raw = manifest.get("models")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise EnvelopeError(f"envelope manifest {source}: 'models' must be a non-empty list")
    workload_path = Path(base) / manifest["workload"]
    workload_config = w1.load_w1_config(workload_path)

    models: dict[str, ModelEntry] = {}
    for entry in entries_raw:
        if not isinstance(entry, dict):
            raise EnvelopeError(f"envelope manifest {source}: model entry {entry!r} is not a mapping")
        model_id = entry.get("model")
        algorithm = entry.get("algorithm")
        if not isinstance(model_id, str) or not model_id:
            raise EnvelopeError(f"envelope manifest {source}: model entry {entry!r} needs a 'model' name")
        if model_id in models:
            raise EnvelopeError(f"envelope manifest {source}: duplicate model name {model_id!r}")
        if algorithm not in ENVELOPE_MODELS:
            raise EnvelopeError(
                f"envelope manifest {source}: unknown algorithm {algorithm!r} "
                f"(model {model_id}); registered: {sorted(ENVELOPE_MODELS)}"
            )
        model = ENVELOPE_MODELS[algorithm]
        topology_ref = entry.get("topology")
        if not isinstance(topology_ref, str):
            raise EnvelopeError(f"model {model_id}: 'topology' must be a path")
        topology_path = Path(base) / topology_ref
        if not topology_path.is_file():
            raise EnvelopeError(f"model {model_id}: topology file not found: {topology_path}")
        topology_data = load_yaml(topology_path)
        topology_class = topology_data.get("topology_class")
        if topology_class not in model.topology_classes:
            raise EnvelopeError(
                f"model {model_id}: algorithm {algorithm!r} is not declared for "
                f"topology_class {topology_class!r} ({topology_ref}); declared "
                f"fabric classes: {list(model.topology_classes)} — undeclared "
                "pairings are different identities and are explicitly unsupported"
            )
        ranks = int(topology_data["ranks"])
        if ranks != workload_config.tp_size:
            raise EnvelopeError(
                f"model {model_id}: workload tp_size {workload_config.tp_size} != "
                f"topology ranks {ranks} ({topology_ref}) — one envelope, one "
                "same-workload operating point"
            )

        binds_raw = entry.get("binds")
        if not isinstance(binds_raw, dict) or not binds_raw:
            raise EnvelopeError(
                f"model {model_id}: 'binds' must map assumption ids to dotted paths"
            )
        binds: dict[str, tuple[str, ...]] = {}
        for assumption_id, path_text in binds_raw.items():
            if assumption_id not in ranges:
                raise EnvelopeError(
                    f"model {model_id}: bind {assumption_id!r} is not a loaded "
                    f"numeric assumption; loaded: {sorted(ranges)}"
                )
            parts = _parse_bind_path(path_text, model_id, assumption_id)
            try:
                _walk(topology_data, parts)  # presence check: bind, never invent
            except KeyError:
                raise EnvelopeError(
                    f"model {model_id}: bind {assumption_id} -> "
                    f"'{'.'.join(parts)}' is not a knob of topology "
                    f"{topology_ref} (path absent; the envelope overrides "
                    "existing knobs, it never invents them)"
                ) from None
            binds[assumption_id] = parts
        models[model_id] = ModelEntry(
            model_id=model_id,
            model=model,
            topology_path=topology_path,
            topology_sha256=sha256_of(topology_path),
            binds=binds,
        )
    return models


# ---------------------------------------------------------------------------
# Evaluation (through the real backends) and reversal detection
# ---------------------------------------------------------------------------


def _evaluate_model(
    entry: ModelEntry,
    axis_values: dict[str, Fraction],
    fixed_values: dict[str, Fraction],
    payload_bytes: int,
    workload_config,
) -> Fraction:
    """Execute one comparator at one exact operating point; return mean O-CCT.

    The evaluation goes through the model's real ``execute`` so every
    in-model gate (conservation self-checks, divisibility, the TFC
    admission invariant) fires per point.
    """
    data = load_yaml(entry.topology_path)
    for assumption_id, parts in sorted(entry.binds.items()):
        if assumption_id in axis_values:
            value = axis_values[assumption_id]
        elif assumption_id in fixed_values:
            value = fixed_values[assumption_id]
        else:
            raise EnvelopeError(
                f"model {entry.model_id}: bound assumption {assumption_id} has "
                "no value at this operating point (neither axis nor fixed)"
            )
        # Fractions are placed directly; every loader parses knobs via
        # Fraction(str(v)), and str(Fraction) round-trips exactly.
        _set_path(data, parts, value)

    try:
        config = entry.model.load_config(data)
    except Exception as exc:
        raise EnvelopeError(
            f"model {entry.model_id}: config rejected at operating point "
            f"{sorted((k, str(v)) for k, v in axis_values.items())}: {exc}"
        ) from exc

    for divisor in entry.model.divisors(config):
        if payload_bytes % divisor:
            raise EnvelopeError(
                f"model {entry.model_id}: payload {payload_bytes} not divisible "
                f"by {divisor} ({entry.model.divisibility_note}); the "
                "equal-chunk construction requires integral chunk byte counts"
            )

    workload_for_point = dataclasses.replace(
        workload_config, allreduce_bytes=payload_bytes
    )
    ops = w1.generate_w1_ops(workload_for_point)
    payloads = {op.payload_bytes for op in ops}
    if len(payloads) != 1:
        raise EnvelopeError(
            "envelope evaluation expects a uniform-payload workload "
            f"(W1 shape), got payloads {sorted(payloads)}"
        )
    try:
        result = entry.model.execute(ops, config)
    except Exception as exc:
        raise EnvelopeError(
            f"model {entry.model_id}: execution rejected at operating point "
            f"{sorted((k, str(v)) for k, v in axis_values.items())}: {exc}"
        ) from exc
    return Fraction(result["observables"]["O-CCT"]["completion_time_ns_mean_exact"])


def _difference_at(
    entry_a: ModelEntry,
    entry_b: ModelEntry,
    axis_id: str,
    axis_other: dict[str, Fraction],
    fixed_values: dict[str, Fraction],
    payload_bytes: int,
    workload_config,
) -> Callable[[Fraction], Fraction] | None:
    """Exact difference evaluator for boundary VERIFICATION (not sampling)."""

    def difference(x: Fraction) -> Fraction:
        values = dict(axis_other)
        values[axis_id] = x
        return _evaluate_model(
            entry_a, values, fixed_values, payload_bytes, workload_config
        ) - _evaluate_model(
            entry_b, values, fixed_values, payload_bytes, workload_config
        )

    return difference


# ---------------------------------------------------------------------------
# Envelope run and artifact emission
# ---------------------------------------------------------------------------


def compute_envelope_id(manifest: dict) -> str:
    """envelope_id = sha256(canonical manifest + code version) — sweep policy."""
    body = {"manifest": manifest, "code_version": __version__}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def run_envelope(manifest_path, results_root=None) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_envelope_manifest(manifest_path)
    source = str(manifest_path)

    def fail(message: str) -> None:
        raise EnvelopeError(f"envelope manifest {source}: {message}")

    if not isinstance(manifest.get("envelope"), str) or not manifest["envelope"]:
        fail("a non-empty 'envelope' name is required")
    if not isinstance(manifest.get("workload"), str):
        fail("'workload' must be a path to one workload file")

    registries_raw = manifest.get("assumption_registries")
    if not isinstance(registries_raw, list) or not registries_raw:
        fail("'assumption_registries' must list at least one assumptions YAML")
    registry_paths = []
    for ref in registries_raw:
        path = REPO_ROOT / ref
        if not path.is_file():
            fail(f"assumption registry not found: {path}")
        registry_paths.append(path)
    try:
        ranges = load_ranges(registry_paths)
    except GridError as exc:
        raise EnvelopeError(str(exc)) from exc

    observable = manifest.get("observable", DEFAULT_OBSERVABLE)
    if observable != "O-CCT":
        fail(
            f"observable {observable!r} is not supported by the envelope runner "
            "v1 (O-CCT only: completion-time ranking is the reversal metric)"
        )
    if observable not in registered_observables():
        fail(f"observable {observable!r} is not registered")

    fixed_raw = manifest.get("fixed", [])
    if not isinstance(fixed_raw, list):
        fail("'fixed' must be a list of {assumption, value} entries")
    try:
        fixed: tuple[FixedParameter, ...] = tuple(
            build_fixed(ranges, item["assumption"], item["value"])
            for item in fixed_raw
        )
    except GridError as exc:
        raise EnvelopeError(str(exc)) from exc

    axes_raw = manifest.get("axes")
    if not isinstance(axes_raw, list) or not axes_raw:
        fail("'axes' must be a non-empty list of {assumption, points} entries")
    try:
        axes: tuple[GridAxis, ...] = tuple(
            build_axis(ranges, item["assumption"], item["points"])
            for item in axes_raw
        )
    except GridError as exc:
        raise EnvelopeError(str(exc)) from exc

    models = _validate_and_load_models(manifest, source, REPO_ROOT, ranges)

    # Every axis must reach at least one model; every fixed parameter must
    # reach a model or be consumed as the payload/ranks cross-check.
    payload_assumption = manifest.get("payload_assumption")
    ranks_assumption = manifest.get("ranks_assumption")
    for axis in axes:
        if not any(axis.assumption_id in entry.binds for entry in models.values()):
            fail(
                f"axis {axis.assumption_id} is bound by no model — it would "
                "vary nothing"
            )
    for item in fixed:
        consumed = (
            item.assumption_id
            in (payload_assumption, ranks_assumption)
        ) or any(item.assumption_id in entry.binds for entry in models.values())
        if not consumed:
            fail(
                f"fixed parameter {item.assumption_id} reaches no model and is "
                "not the payload/ranks assumption"
            )

    workload_path = REPO_ROOT / manifest["workload"]
    workload_config = w1.load_w1_config(workload_path)
    if payload_assumption is not None:
        if payload_assumption not in {item.assumption_id for item in fixed}:
            fail(f"payload_assumption {payload_assumption!r} is not a fixed parameter")
        payload_bytes = int(
            next(item.value for item in fixed if item.assumption_id == payload_assumption)
        )
    else:
        payload_bytes = workload_config.allreduce_bytes
    if ranks_assumption is not None:
        ranks_value = next(
            (
                item.value
                for item in fixed
                if item.assumption_id == ranks_assumption
            ),
            None,
        )
        if ranks_value is None:
            fail(f"ranks_assumption {ranks_assumption!r} is not a fixed parameter")
        if int(ranks_value) != workload_config.tp_size:
            fail(
                f"ranks_assumption {ranks_assumption} = {int(ranks_value)} does "
                f"not equal workload tp_size {workload_config.tp_size}"
            )

    points = expand_operating_points(axes, fixed)
    fixed_values = {item.assumption_id: item.value for item in fixed}

    # --- evaluate every model at every operating point (exact Fractions)
    evaluations: list[dict] = []
    values_by_model_point: dict[tuple[str, int], Fraction] = {}
    for point in points:
        axis_values = dict(point.axis_values)
        for model_id, entry in models.items():
            value = _evaluate_model(
                entry, axis_values, fixed_values, payload_bytes, workload_config
            )
            values_by_model_point[(model_id, point.index)] = value
            evaluations.append(
                {
                    "point_id": point.point_id,
                    "point_index": point.index,
                    "model": model_id,
                    "axis_values_exact": [
                        [aid, str(v)] for aid, v in point.axis_values
                    ],
                    "o_cct_ns_mean_exact": str(value),
                    "o_cct_ns_mean": float(value),
                }
            )

    # --- reversal detection per declared pair, per axis slice
    pairs_raw = manifest.get("reversal_pairs")
    if not isinstance(pairs_raw, list) or not pairs_raw:
        fail("'reversal_pairs' must list at least one [model_a, model_b] pair")
    pairs: list[tuple[str, str]] = []
    for pair in pairs_raw:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(name, str) for name in pair)
        ):
            fail(f"reversal pair {pair!r} must be a two-model list")
        for name in pair:
            if name not in models:
                fail(f"reversal pair names unknown model {name!r}; models: {sorted(models)}")
        if pair[0] == pair[1]:
            fail(f"reversal pair {pair!r} must name two distinct models")
        key = tuple(pair)
        if key in pairs or (key[1], key[0]) in pairs:
            fail(f"duplicate reversal pair {pair!r}")
        pairs.append(key)

    reversals: list[dict] = []
    regions_out: list[dict] = []
    for model_a, model_b in pairs:
        for axis in axes:
            # Group operating points by the OTHER axes' values (slices),
            # first-seen order, and walk each slice in axis order.
            slices: dict[tuple[tuple[str, Fraction], ...], list[OperatingPoint]] = {}
            for point in points:
                key = tuple(
                    (aid, point.axis_value(aid))
                    for aid in [a.assumption_id for a in axes]
                    if aid != axis.assumption_id
                )
                slices.setdefault(key, []).append(point)
            for slice_key, slice_points in slices.items():
                slice_points = sorted(
                    slice_points, key=lambda p: p.axis_value(axis.assumption_id)
                )
                coords = [p.axis_value(axis.assumption_id) for p in slice_points]
                vals_a = [
                    values_by_model_point[(model_a, p.index)] for p in slice_points
                ]
                vals_b = [
                    values_by_model_point[(model_b, p.index)] for p in slice_points
                ]
                axis_other = dict(slice_key)
                difference_at = _difference_at(
                    models[model_a],
                    models[model_b],
                    axis.assumption_id,
                    axis_other,
                    fixed_values,
                    payload_bytes,
                    workload_config,
                )
                # A candidate boundary the models themselves reject (e.g. a
                # non-grantable TFC window at a secant root that is not a
                # multiple of the 256-byte credit unit) is handled inside
                # the solver: verification fails and the flip keeps the
                # bracket only (grid evidence, never a fake boundary).
                flips, regions = detect_reversals(
                    axis.assumption_id,
                    coords,
                    vals_a,
                    vals_b,
                    difference_at=difference_at,
                    slice_values=slice_key,
                )
                for flip in flips:
                    reversals.append(
                        {
                            "pair": [model_a, model_b],
                            **flip.as_dict(),
                        }
                    )
                for region in regions:
                    regions_out.append(
                        {
                            "pair": [model_a, model_b],
                            **region.as_dict(),
                        }
                    )

    envelope_id = compute_envelope_id(manifest)
    table = {
        "envelope": manifest["envelope"],
        "envelope_id": envelope_id,
        "code_version": __version__,
        "evidence_level": "E0",
        "status": "PROPOSED",
        "manifest_path": _rel(manifest_path),
        "manifest_sha256": sha256_of(manifest_path),
        "assumption_registries": [
            {
                "path": _rel(path),
                "sha256": sha256_of(path),
                "assumptions_id": load_yaml(path).get("assumptions_id"),
            }
            for path in registry_paths
        ],
        "workload": {
            "path": _rel(workload_path),
            "sha256": sha256_of(workload_path),
            "tp_size": workload_config.tp_size,
            "layers": workload_config.layers,
            "steps": workload_config.steps,
            "ops_per_point": workload_config.layers * workload_config.steps,
            "allreduce_bytes_in_workload_file": workload_config.allreduce_bytes,
            "payload_bytes_at_operating_point": payload_bytes,
        },
        "observable": observable,
        "operating_point_fixed": [item.as_dict() for item in fixed],
        "freedom_axes": [axis.as_dict() for axis in axes],
        "models": [
            {
                "model": entry.model_id,
                **entry.model.as_dict(),
                "topology": {
                    "path": _rel(entry.topology_path),
                    "sha256": entry.topology_sha256,
                },
                "binds": {
                    aid: ".".join(parts) for aid, parts in sorted(entry.binds.items())
                },
            }
            for entry in models.values()
        ],
        "reversal_pairs": [list(pair) for pair in pairs],
        "evaluations": evaluations,
        "reversals": reversals,
        "regions": regions_out,
        "framing": [
            "E0 evidence only: every value is the output of a closed-form "
            "analytical identity executed by its landed backend under explicit "
            "free parameters at exact operating points.",
            "A reversal is a statement about the RANKING OF MODEL IDENTITIES "
            "under declared freedom — not about any measured system; nothing "
            "here was run on or says anything about hardware.",
            "Registered free-parameter ranges are the authority: every grid "
            "point and fixed value was validated inside its range before any "
            "model executed.",
        ],
    }

    artifact_bytes = (canonical_json(table) + "\n").encode("utf-8")
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    md_bytes = (render_envelope_md(table) + "\n").encode("utf-8")

    results_root = Path(results_root) if results_root else REPO_ROOT / "results"
    out_dir = results_root / "envelopes" / envelope_id
    expected = {
        "reversal.json": artifact_bytes,
        "reversal.md": md_bytes,
        "reversal.json.sha256": (artifact_sha256 + "\n").encode("utf-8"),
    }
    if out_dir.exists():
        for name, payload in expected.items():
            path = out_dir / name
            if not path.is_file() or path.read_bytes() != payload:
                raise EnvelopeError(
                    f"envelope {envelope_id} already exists with different "
                    f"{name} bytes; envelope outputs are deterministic — a "
                    "byte drift is a bug, not a new result"
                )
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in expected.items():
            (out_dir / name).write_bytes(payload)

    return {
        "envelope_id": envelope_id,
        "artifact_dir": out_dir,
        "artifact_sha256": artifact_sha256,
        "table": table,
    }


# ---------------------------------------------------------------------------
# Human rendering (deterministic: derived only from the table dict)
# ---------------------------------------------------------------------------


def _cell(text: str) -> str:
    """Sanitize one markdown table cell (registry 'parameter' fields spell
    multiple knob names separated by pipes)."""
    return text.replace("|", "/")


def render_envelope_md(table: dict) -> str:
    lines: list[str] = []
    lines.append(
        f"# Envelope `{table['envelope']}` — operating-point grid + reversal report"
    )
    lines.append("")
    lines.append(f"Envelope id: `{table['envelope_id']}`")
    lines.append("")
    lines.append(
        f"Status: {table['status']} at evidence level {table['evidence_level']}. "
        "This artifact ranks ANALYTICAL MODEL IDENTITIES under declared "
        "freedom at exact operating points; it is not a measurement and "
        "makes no statement about hardware."
    )
    lines.append("")
    lines.append(f"- manifest: `{table['manifest_path']}` (sha256 `{table['manifest_sha256']}`)")
    workload = table["workload"]
    lines.append(
        f"- workload: `{workload['path']}` (sha256 `{workload['sha256']}`) — "
        f"tp_size {workload['tp_size']}, {workload['ops_per_point']} ops per "
        f"point, payload {workload['payload_bytes_at_operating_point']} bytes "
        "at the operating point"
    )
    for registry in table["assumption_registries"]:
        lines.append(
            f"- assumptions: `{registry['path']}` (sha256 `{registry['sha256']}`, "
            f"id `{registry['assumptions_id']}`)"
        )
    lines.append("- code version: " + table["code_version"])
    lines.append("")
    lines.append("## Fixed operating point (exact, range-validated)")
    lines.append("")
    lines.append("| assumption | parameter | value (exact) | registered range |")
    lines.append("|---|---|---|---|")
    for item in table["operating_point_fixed"]:
        lines.append(
            f"| {item['assumption_id']} | {_cell(item['parameter'])} | "
            f"{item['value_exact']} | [{item['range_exact'][0]}, {item['range_exact'][1]}] |"
        )
    lines.append("")
    lines.append("## Freedom axes (exact grid points inside the registered ranges)")
    lines.append("")
    lines.append("| assumption | parameter | range | grid points (exact) |")
    lines.append("|---|---|---|---|")
    for axis in table["freedom_axes"]:
        points = ", ".join(axis["points_exact"])
        lines.append(
            f"| {axis['assumption_id']} | {_cell(axis['parameter'])} | "
            f"[{axis['range_exact'][0]}, {axis['range_exact'][1]}] | {points} |"
        )
    lines.append("")
    lines.append("## Comparator identities")
    lines.append("")
    lines.append("| model | algorithm | backend | topology |")
    lines.append("|---|---|---|---|")
    for model in table["models"]:
        lines.append(
            f"| {model['model']} | {model['algorithm_id']} | {model['backend_id']} "
            f"| {model['topology']['path'].split('/')[-1]} |"
        )
    lines.append("")
    lines.append("## Evaluations (O-CCT mean, exact ns)")
    lines.append("")
    header = [axis["assumption_id"] for axis in table["freedom_axes"]]
    lines.append("| " + " | ".join(header + ["model", "O-CCT ns (exact)", "O-CCT ns (float)"]) + " |")
    lines.append("|" + "---|" * (len(header) + 3))
    for row in table["evaluations"]:
        axis_cells = [str(v) for _, v in row["axis_values_exact"]]
        lines.append(
            "| "
            + " | ".join(
                axis_cells
                + [
                    row["model"],
                    row["o_cct_ns_mean_exact"],
                    f"{row['o_cct_ns_mean']:.4f}",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Reversals (exact-Fraction flips)")
    lines.append("")
    if not table["reversals"]:
        lines.append(
            "No ranking reversal at any sampled operating point: every "
            "declared pair keeps one ranking across the whole grid."
        )
    for flip in table["reversals"]:
        boundary = (
            flip["boundary_exact"]
            if flip["boundary_verified"]
            else f"unresolved (bracket {flip['bracket_exact']})"
        )
        lines.append(
            f"- pair {flip['pair'][0]} vs {flip['pair'][1]}, axis {flip['axis']}"
            + (f", slice {flip['slice_values_exact']}" if flip["slice_values_exact"] else "")
            + f": sign {flip['sign_lo']} -> {flip['sign_hi']} on bracket "
            f"{flip['bracket_exact']}; boundary {boundary} "
            f"({flip['boundary_method']}); exact differences "
            f"{flip['difference_exact']}"
        )
    lines.append("")
    lines.append("### Ranking regions (grid evidence, exact endpoints)")
    lines.append("")
    for region in table["regions"]:
        lines.append(
            f"- pair {region['pair'][0]} vs {region['pair'][1]}, axis "
            f"{region['axis']}: {region['sign_reading']} on "
            f"[{region['from_exact']}, {region['to_exact']}]"
        )
    lines.append("")
    lines.append(
        "Generated deterministically from the envelope manifest (canonical "
        "JSON, exact Fractions, no wall-clock); byte-identical on replay. "
        "The artifact is content-addressed: reversal.json.sha256 records "
        "the SHA-256 of reversal.json."
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run an envelope manifest and emit the reversal artifact"
    )
    parser.add_argument("manifest", help="path to the envelope manifest YAML")
    parser.add_argument(
        "--results-root",
        default=None,
        help="results root (default: <repo>/results); artifacts land under envelopes/<envelope_id>/",
    )
    args = parser.parse_args(argv)
    result = run_envelope(args.manifest, results_root=args.results_root)
    print(
        json.dumps(
            {
                "envelope_id": result["envelope_id"],
                "artifact_dir": str(result["artifact_dir"]),
                "artifact_sha256": result["artifact_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
