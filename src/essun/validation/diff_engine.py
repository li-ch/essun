"""Differential-validation engine, first slice.

Compares two immutable RunRecords in the evidence store under an explicit
obligation and emits a structured, typed verdict — the engine that
generalizes the manual G3-S3 difference report
(``results/difference_reports/w1_smoke_l0_vs_astra_sim_analytical.json``,
`results/difference_reports/`).

Obligations
-----------

- ``exact``   — bit-exact equality of an aligned value series between the
  two runs, compared with :class:`fractions.Fraction`. The verdict is the
  FIRST divergence (observable, location, both values, delta, ratio) or
  ``equal``. A divergence is *reported*, never tuned away: this
  engine adjusts no parameter, ever.
- ``bounded`` — a tolerance obligation taken from a registered ``bounded``
  observable spec (e.g. ``O-CCT-RELERR``); every aligned location pair is
  evaluated through the observable registry's own ``check`` via
  ``differential_observation``, so the registry stays the single source
  of units, tolerance, form, and validity domain. The verdict is
  pass/violation per location plus the worst deviation and its margin
  (deviation − tolerance).

Judgment calls of this first slice (owner refines at adjudication):

1. Obligations are programmatic (:class:`Obligation`), not a YAML schema.
2. A bounded obligation's tolerance comes from the registry; an explicit
   ``tolerance`` on the obligation must EQUAL the registered one — any
   other value is rejected, so a tolerance cannot be tuned through the
   engine's back door (classify, never tune).
3. Reference orientation: run ``a`` is the reference/expected side, run
   ``b`` the measured/value side. For bounded obligations the engine
   verifies the recorded baseline relationship (b's manifest
   ``baseline_id`` == a's ``experiment_id``) whenever b declares one.
4. Quantity extractors are shape-keyed (per-op series vs whole-chain
   wall) and record their aggregation provenance in the verdict. The
   ASTRA per-op equivalent is the exact chain/ops division validated by
   the S3 single-op diagnostic probe (24048) — the engine never
   re-derives the S3 term decomposition, it only reports divergences
   consistent with it.
5. Comparability gates fire BEFORE any comparison: unknown run ids,
   unregistered observables, uncontrolled comparisons (different workload
   or topology input hashes), empty series, and
   misaligned series lengths are explicit errors; a capability gap (an
   observable a run declares unsupported) is a ``not_comparable`` verdict,
   mirroring the S3 treatment of O-CONSERVATION.

Output: one typed JSON record per (runs, obligation), content-addressed
as ``diff_id = sha256(canonical JSON of the record body)`` and written —
append-only and idempotent — to
``results/difference_reports/<diff_id>.json`` (additive next to the manual
S3 report, which is never rewritten). No wall-clock or host metadata:
identical inputs reproduce byte-identical records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from essun import __version__
from essun.contracts import REPO_ROOT
from essun.evidence.store import OBSERVATIONS, EvidenceStore, canonical_json
from essun.observables import (
    BOUNDED,
    RELATIVE,
    check as check_observable,
    differential_observation,
    lookup as lookup_observable,
)

EXACT_MODE = "exact"
BOUNDED_MODE = "bounded"
MODES = (EXACT_MODE, BOUNDED_MODE)

ENGINE_ID = "essun.validation.diff_engine"
DIFFERENCE_REPORTS_DIR = "difference_reports"

# Input hashes two compared runs MUST share for the comparison to be
# controlled (runs with different workloads are not
# controlled ablations). The implementation profile is intentionally NOT
# gated — different backends legitimately translate different profiles.
SHARED_INPUT_KEYS = ("workload_ir", "infra_graph")


class DiffEngineError(Exception):
    """A differential comparison violates a contract.

    Raised for unknown run ids, unregistered observables, tolerance
    mismatches, uncontrolled comparisons, empty or misaligned series —
    always INSTEAD OF producing a verdict that would silently narrow the
    comparison. Capability gaps and numeric divergences are never errors:
    they are verdicts (``not_comparable`` / ``diverged`` / ``violation``).
    """


@dataclass(frozen=True)
class SeriesPoint:
    """One located exact value extracted from a run's observations."""

    location: dict  # e.g. {"op": 0} or {"scope": "chain"}
    value: Fraction
    provenance: str


@dataclass(frozen=True)
class Obligation:
    """What the two runs must satisfy for the comparison to hold.

    ``mode``        — ``exact`` (bit-exact series equality) or ``bounded``
                      (registry tolerance).
    ``quantity``    — a registered quantity extractor id (QUANTITIES).
    ``spec_id``     — the registered observable that owns the obligation:
                      for ``exact`` it must be the emitted observable
                      itself; for ``bounded`` a registered bounded spec
                      whose tolerance/form/validity domain apply.
    ``tolerance``   — bounded only; when given it must EQUAL the
                      registered tolerance (anti-tuning gate).
    """

    mode: str
    quantity: str
    spec_id: str
    tolerance: Fraction | None = None


@dataclass(frozen=True)
class QuantitySpec:
    """A named, shape-keyed extractor from a run's observations.json."""

    quantity_id: str
    emitted_observable: str
    description: str
    extract: Callable[[dict], list[SeriesPoint]]


def _as_fraction(value: Any) -> Fraction:
    # Same exact-arithmetic policy as the observable registry: str() first
    # so ints, decimal strings, and floats all enter exactly.
    return Fraction(str(value))


def _cct_observable(observations: dict) -> dict:
    occt = observations.get("observables", {}).get("O-CCT")
    if not isinstance(occt, dict):
        raise DiffEngineError(
            "quantity needs the run's O-CCT observation; none present"
        )
    return occt


def _extract_cct_per_op(observations: dict) -> list[SeriesPoint]:
    """Per-op CCT series, ns.

    Shape-keyed: a run that emits a ``per_op`` list (L0 shape) yields its
    exact per-op completion times directly; a run that emits only the
    whole-chain wall (ASTRA shape) yields the exact chain/ops division —
    valid because the chain is dependency-serialized with zero inter-op
    gap, validated by the S3 single-op diagnostic (Wall = 24048). A
    non-exact division is a contract error, never a rounded comparison.
    """
    per_op = observations.get("per_op")
    if isinstance(per_op, list):
        if not per_op:
            raise DiffEngineError(
                "cct_per_op_ns: run produced an EMPTY per_op series; there "
                "is nothing to compare and the engine refuses to fabricate "
                "a verdict"
            )
        return [
            SeriesPoint(
                location={"op": index},
                value=_as_fraction(entry["completion_time_ns_exact"]),
                provenance="per_op[].completion_time_ns_exact (per-op series)",
            )
            for index, entry in enumerate(per_op)
        ]
    occt = _cct_observable(observations)
    ops = occt.get("ops")
    wall = occt.get("completion_time_ns")
    if not isinstance(ops, int) or ops < 1 or wall is None:
        raise DiffEngineError(
            "cct_per_op_ns: run emits neither a per_op series nor an "
            "(ops, completion_time_ns) chain; aggregation alignment undefined"
        )
    chain = _as_fraction(wall)
    if chain % ops != 0:
        raise DiffEngineError(
            f"cct_per_op_ns: chain {chain} ns does not divide exactly by "
            f"{ops} op(s); per-op equivalence is undefined (refusing to "
            "compare a rounded value)"
        )
    per_op_value = chain / ops
    return [
        SeriesPoint(
            location={"op": index},
            value=per_op_value,
            provenance=(
                f"O-CCT.completion_time_ns / ops = {chain}/{ops} (exact "
                "division; dependency-serialized zero-gap chain, single-op "
                "probe per P3 S3)"
            ),
        )
        for index in range(ops)
    ]


def _extract_cct_chain_total(observations: dict) -> list[SeriesPoint]:
    """Whole-chain CCT, ns: sum of per-op series vs reported chain wall."""
    per_op = observations.get("per_op")
    if isinstance(per_op, list):
        if not per_op:
            raise DiffEngineError(
                "cct_chain_total_ns: run produced an EMPTY per_op series; "
                "there is nothing to compare and the engine refuses to "
                "fabricate a verdict"
            )
        total = sum((_as_fraction(e["completion_time_ns_exact"]) for e in per_op), Fraction(0))
        return [
            SeriesPoint(
                location={"scope": "chain"},
                value=total,
                provenance="sum(per_op[].completion_time_ns_exact) (chain total)",
            )
        ]
    occt = _cct_observable(observations)
    if occt.get("completion_time_ns") is None:
        raise DiffEngineError(
            "cct_chain_total_ns: run emits neither a per_op series nor a "
            "chain completion_time_ns"
        )
    return [
        SeriesPoint(
            location={"scope": "chain"},
            value=_as_fraction(occt["completion_time_ns"]),
            provenance=(
                "O-CCT.completion_time_ns (per-rank wall of the full "
                "serialized chain)"
            ),
        )
    ]


def _extract_wire_bytes_per_op(observations: dict) -> list[SeriesPoint]:
    """Per-op per-rank wire-byte ledger, bytes (uniform across ranks at L0)."""
    per_op = observations.get("per_op")
    if not isinstance(per_op, list) or not per_op:
        raise DiffEngineError(
            "per_rank_wire_bytes_per_op: run emits no (or an EMPTY) per_op "
            "wire-byte ledger; there is nothing to compare"
        )
    return [
        SeriesPoint(
            location={"op": index},
            value=_as_fraction(entry["per_rank_wire_bytes_exact"]),
            provenance="per_op[].per_rank_wire_bytes_exact (uniform per rank)",
        )
        for index, entry in enumerate(per_op)
    ]


QUANTITIES: dict[str, QuantitySpec] = {
    spec.quantity_id: spec
    for spec in (
        QuantitySpec(
            quantity_id="cct_per_op_ns",
            emitted_observable="O-CCT",
            description="Collective completion time per op (ns)",
            extract=_extract_cct_per_op,
        ),
        QuantitySpec(
            quantity_id="cct_chain_total_ns",
            emitted_observable="O-CCT",
            description="Collective completion time of the whole op chain (ns)",
            extract=_extract_cct_chain_total,
        ),
        QuantitySpec(
            quantity_id="per_rank_wire_bytes_per_op",
            emitted_observable="O-CONSERVATION",
            description="Per-rank wire bytes per op (bytes; uniform per rank at L0)",
            extract=_extract_wire_bytes_per_op,
        ),
    )
}


class DiffEngine:
    """Differential comparison of two stored runs under one obligation."""

    def __init__(self, store: EvidenceStore):
        self.store = store

    # -- run loading ------------------------------------------------------

    def _load(self, run_id: str, role: str) -> tuple[dict, dict]:
        if not isinstance(run_id, str) or not run_id:
            raise DiffEngineError(f"run id for role {role!r} must be a non-empty string")
        try:
            record = self.store.get_run(run_id)
        except Exception as exc:
            raise DiffEngineError(
                f"unknown run for role {role!r}: no run record for run_id {run_id}"
            ) from exc
        observations_path = self.store.run_dir(run_id) / OBSERVATIONS
        if not observations_path.is_file():
            raise DiffEngineError(
                f"run {run_id} has no {OBSERVATIONS} artifact; cannot compare"
            )
        observations = json.loads(observations_path.read_text(encoding="utf-8"))
        return record, observations

    # -- comparability gates ----------------------------------------------

    @staticmethod
    def _require_controlled_comparison(record_a: dict, record_b: dict) -> None:
        inputs_a = record_a.get("inputs", {})
        inputs_b = record_b.get("inputs", {})
        for key in SHARED_INPUT_KEYS:
            sha_a = inputs_a.get(key, {}).get("sha256")
            sha_b = inputs_b.get(key, {}).get("sha256")
            if sha_a is None or sha_b is None:
                raise DiffEngineError(
                    f"uncontrolled comparison: run record is missing the "
                    f"{key}.sha256 input hash; the engine only compares runs "
                    "with fully pinned inputs"
                )
            if sha_a != sha_b:
                raise DiffEngineError(
                    f"uncontrolled comparison: {key} sha256 differs between "
                    f"the two runs ({sha_a} vs {sha_b}); runs with different "
                    "workloads/topologies are not a controlled ablation "
                    "(handoff rule 6)"
                )

    @staticmethod
    def _capability_gap(
        observations: dict, role: str, emitted_observable: str
    ) -> str | None:
        emitted = observations.get("observables", {}).get(emitted_observable)
        if isinstance(emitted, dict):
            return None
        unsupported = observations.get("unsupported_observables", {})
        if emitted_observable in unsupported:
            return (
                f"run {role} declares {emitted_observable} unsupported: "
                f"{unsupported[emitted_observable]}"
            )
        return f"run {role} does not emit {emitted_observable} (not requested)"

    # -- obligation validation ---------------------------------------------

    def _resolve_spec(self, obligation: Obligation, quantity: QuantitySpec) -> dict:
        if obligation.mode not in MODES:
            raise DiffEngineError(
                f"obligation mode {obligation.mode!r} not in {MODES}"
            )
        try:
            spec = lookup_observable(obligation.spec_id)
        except ValueError as exc:
            raise DiffEngineError(f"obligation spec rejected: {exc}") from exc
        if obligation.mode == EXACT_MODE:
            if spec.observable_id != quantity.emitted_observable:
                raise DiffEngineError(
                    f"exact obligation spec {spec.observable_id!r} must be the "
                    f"quantity's emitted observable "
                    f"{quantity.emitted_observable!r}"
                )
        else:
            if spec.kind != BOUNDED:
                raise DiffEngineError(
                    f"bounded obligation spec {spec.observable_id!r} has kind "
                    f"{spec.kind!r}; it must be a registered bounded spec"
                )
            if obligation.tolerance is not None and obligation.tolerance != spec.tolerance:
                raise DiffEngineError(
                    f"obligation tolerance {obligation.tolerance} != registered "
                    f"tolerance {spec.tolerance} of {spec.observable_id!r}; the "
                    "registry is the single source of tolerance (tuning a "
                    "tolerance through the engine is forbidden, handoff rule 5)"
                )
        return {
            "spec": spec,
            "spec_kind": spec.kind,
            "emitted_unit": lookup_observable(
                quantity.emitted_observable
            ).unit,
        }

    # -- series alignment ---------------------------------------------------

    @staticmethod
    def _aligned_series(
        series_a: list[SeriesPoint], series_b: list[SeriesPoint], quantity_id: str
    ) -> None:
        if not series_a or not series_b:
            raise DiffEngineError(
                f"quantity {quantity_id!r}: a compared run produced an EMPTY "
                "series; there is nothing to compare and the engine refuses "
                "to fabricate a verdict"
            )
        if len(series_a) != len(series_b):
            raise DiffEngineError(
                f"quantity {quantity_id!r}: misaligned series lengths "
                f"({len(series_a)} vs {len(series_b)}); comparing a subset "
                "would silently narrow the obligation"
            )
        if [p.location for p in series_a] != [p.location for p in series_b]:
            raise DiffEngineError(
                f"quantity {quantity_id!r}: series locations do not align; "
                "the runs disagree on the op/rank grid"
            )

    # -- engine core ---------------------------------------------------------

    def compare(self, run_id_a: str, run_id_b: str, obligation: Obligation) -> dict:
        """Compare run ``a`` (reference) against run ``b`` (value).

        Returns the typed verdict record (not yet written anywhere); use
        :func:`write_report` to persist it under
        ``results/difference_reports/``.
        """
        if not isinstance(obligation, Obligation):
            raise DiffEngineError("obligation must be an Obligation instance")
        quantity = QUANTITIES.get(obligation.quantity)
        if quantity is None:
            raise DiffEngineError(
                f"unknown quantity {obligation.quantity!r}; registered: "
                f"{sorted(QUANTITIES)}"
            )
        resolved = self._resolve_spec(obligation, quantity)
        spec = resolved["spec"]

        record_a, obs_a = self._load(run_id_a, "a")
        record_b, obs_b = self._load(run_id_b, "b")
        self._require_controlled_comparison(record_a, record_b)

        manifest_a = record_a.get("manifest", {})
        manifest_b = record_b.get("manifest", {})
        if obligation.mode == BOUNDED_MODE:
            baseline_id = manifest_b.get("baseline_id")
            if baseline_id is not None and baseline_id != manifest_a.get(
                "experiment_id"
            ):
                raise DiffEngineError(
                    f"reference misalignment: run b declares baseline "
                    f"{baseline_id!r} but run a is "
                    f"{manifest_a.get('experiment_id')!r}; a bounded "
                    "obligation must use the recorded baseline as reference"
                )

        runs_block = {
            role: {
                "run_id": record["run_id"],
                "backend_id": obs.get("backend_id"),
                "experiment_id": record.get("manifest", {}).get("experiment_id"),
                "baseline_id": record.get("manifest", {}).get("baseline_id"),
                "manifest_path": record.get("manifest_path"),
                "record_path": f"results/{record['run_id']}/",
            }
            for role, record, obs in (
                ("a", record_a, obs_a),
                ("b", record_b, obs_b),
            )
        }
        obligation_block = {
            "mode": obligation.mode,
            "quantity": obligation.quantity,
            "spec_id": spec.observable_id,
            "spec_kind": resolved["spec_kind"],
            "emitted_observable": quantity.emitted_observable,
            "emitted_unit": resolved["emitted_unit"],
            "description": quantity.description,
        }

        def record_with(verdict: dict, series_info: dict | None = None) -> dict:
            body = {
                "engine": ENGINE_ID,
                "engine_slice": "T040 first differential-validation engine slice",
                "code_version": __version__,
                "evidence_level": "E0",
                "classify_dont_tune": (
                    "the engine reports differences only; it never adjusts "
                    "parameters (D-006)"
                ),
                "runs": runs_block,
                "obligation": {**obligation_block, **(series_info or {})},
                "verdict": verdict,
            }
            body["diff_id"] = hashlib.sha256(
                canonical_json(body).encode("utf-8")
            ).hexdigest()
            return body

        # Capability gate: an observable a run cannot emit is a recorded
        # capability gap, not a numeric difference (S3 precedent).
        gap = self._capability_gap(obs_a, "a", quantity.emitted_observable) or (
            self._capability_gap(obs_b, "b", quantity.emitted_observable)
        )
        if gap is not None:
            return record_with(
                {
                    "status": "not_comparable",
                    "reason": gap,
                    "detail": (
                        "capability gap, not a numeric difference; recorded "
                        "as such and never classified as divergence"
                    ),
                }
            )

        series_a = quantity.extract(obs_a)
        series_b = quantity.extract(obs_b)
        self._aligned_series(series_a, series_b, obligation.quantity)
        series_info = {
            "series_length": len(series_a),
            "series_provenance": {
                "a": sorted({p.provenance for p in series_a}),
                "b": sorted({p.provenance for p in series_b}),
            },
        }

        if obligation.mode == EXACT_MODE:
            first = next(
                ((pa, pb) for pa, pb in zip(series_a, series_b) if pa.value != pb.value),
                None,
            )
            if first is None:
                return record_with(
                    {
                        "status": "equal",
                        "first_divergence": None,
                        "detail": (
                            f"all {len(series_a)} aligned value(s) equal "
                            "bit-exactly (exact Fractions)"
                        ),
                    },
                    series_info,
                )
            pa, pb = first
            delta = pb.value - pa.value
            ratio = None if pa.value == 0 else pb.value / pa.value
            return record_with(
                {
                    "status": "diverged",
                    "first_divergence": {
                        "observable": quantity.emitted_observable,
                        "location": pa.location,
                        "value_a_exact": str(pa.value),
                        "value_b_exact": str(pb.value),
                        "delta_exact": str(delta),
                        "ratio_b_over_a_exact": None if ratio is None else str(ratio),
                        "ratio_b_over_a_float": None if ratio is None else float(ratio),
                    },
                    "detail": (
                        f"first divergence at {pa.location}: {pa.value} vs "
                        f"{pb.value} {resolved['emitted_unit']} "
                        f"(delta {delta})"
                    ),
                },
                series_info,
            )

        # bounded: registry check per aligned location, worst deviation wins
        per_location = []
        for index, (pa, pb) in enumerate(zip(series_a, series_b)):
            if spec.form == RELATIVE and pa.value == 0:
                raise DiffEngineError(
                    "relative-form bounded obligation with zero reference "
                    "value; the ratio is undefined"
                )
            result = check_observable(
                spec,
                differential_observation(pb.value, pa.value, quantity=obligation.quantity),
            )
            if spec.form == RELATIVE:
                deviation = abs(pb.value / pa.value - 1)
            else:
                deviation = abs(pa.value - pb.value)
            per_location.append((index, pa, pb, result.status, deviation))
        worst = max(per_location, key=lambda item: (item[4], -item[0]))
        index, pa, pb, _, deviation = worst
        margin = deviation - spec.tolerance
        violating = sum(1 for item in per_location if item[3] == "violation")
        status = "violation" if violating else "pass"
        return record_with(
            {
                "status": status,
                "reference_orientation": (
                    "a = reference/expected (recorded baseline); b = value"
                ),
                "locations_checked": len(per_location),
                "violating_locations": violating,
                "tolerance_exact": str(spec.tolerance),
                "form": spec.form,
                "validity_domain": spec.validity_domain.to_dict()
                if spec.validity_domain
                else None,
                "worst": {
                    "location": pa.location,
                    "value_a_exact": str(pa.value),
                    "value_b_exact": str(pb.value),
                    "delta_exact": str(pb.value - pa.value),
                    "deviation_exact": str(deviation),
                    "deviation_float": float(deviation),
                    "margin_exact": str(margin),
                },
                "detail": (
                    f"worst deviation {deviation} vs tolerance "
                    f"{spec.tolerance} (margin {margin}) at {pa.location}; "
                    "a violation is a finding (counterexample candidate), "
                    "never raised"
                ),
            },
            series_info,
        )


def write_report(record: dict, results_root: Path | str | None = None) -> Path:
    """Persist a verdict record append-only under difference_reports/.

    ``diff_id`` is the SHA-256 of the canonical record body, so writing the
    identical record again is idempotent (byte comparison, no rewrite) and
    a byte drift under an existing id is an explicit append-only violation.
    """
    if "diff_id" not in record:
        raise DiffEngineError("record is not a typed engine record (no diff_id)")
    root = Path(results_root) if results_root is not None else REPO_ROOT / "results"
    directory = root / DIFFERENCE_REPORTS_DIR
    path = directory / f"{record['diff_id']}.json"
    payload = (canonical_json(record) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise DiffEngineError(
                f"append-only violation: difference report {record['diff_id']} "
                "already exists with different bytes"
            )
        return path
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path
