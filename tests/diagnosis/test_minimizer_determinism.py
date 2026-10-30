"""Soak seed 2 (2026-10-30): the diagnosis minimizer's determinism
property on REAL disagreements.

tests/diagnosis/test_units.py pins minimizer determinism on a toy case
space (size >= 8 AND flag).  This module extends the property to the
four REAL seeded disagreements of the G9 defect-seeding record
(experiments/diagnosis/defect_seeding/): the same disagreement must
yield the same shrink — byte-identical minimization — across two
invocations with freshly built probes and ladders, in either trial
order, and the result must still equal the committed immutable record
(a prior invocation, effectively a third witness).

"Byte-identical" is literal: the whole :class:`MinimizationResult`
(initial case, minimal case, every probe record with its candidate and
evidence, pass count) is canonically serialized (sorted keys, no
whitespace) and the encoded bytes must be equal.  Any divergence is a
finding about the minimizer or a carrier — never silence it by
re-recording the committed artifact.

Deterministic and fast: pure in-process execution of the same carriers
the record builder uses; no Docker, no store, no network.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import fields, is_dataclass
from fractions import Fraction
from pathlib import Path

from essun.diagnosis.minimize import minimize

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "experiments" / "diagnosis" / "defect_seeding" / "build_record.py"
COMMITTED = (
    REPO / "experiments" / "diagnosis" / "defect_seeding" / "defect_seeding_record_v1.json"
)


def _load_builder():
    spec = importlib.util.spec_from_file_location("g9_defect_builder_determinism", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _real_trials(module) -> list[tuple[str, object, object, object]]:
    """The four real disagreements, wired exactly as build() wires them
    (same initial cases, same probe pair construction, same ladders),
    but with the closures rebuilt FRESH per retrieval so two
    invocations share no object identity by accident."""

    def probe(clean_fn, defect_fn, quantity):
        return module._probe_pair(clean_fn, defect_fn, quantity)

    return [
        (
            "floor_not_roundup_credit_consumption",
            module.INITIAL_TFC,
            probe(
                module.tfc_cell_completion,
                module.defect_tfc_floor_not_roundup,
                "completion_ns_exact",
            ),
            module.tfc_ladder,
        ),
        (
            "drain_batched_credit_return",
            module.INITIAL_LINK,
            probe(
                module.link_transfer_completion,
                module.defect_link_batched_return_completion,
                "completion_ns",
            ),
            module.link_ladder,
        ),
        (
            "ignored_gb_unit_conversion",
            module.INITIAL_RING_UNIT,
            probe(
                module.ring_chain_completion,
                module.defect_ring_unit_ignored,
                "per_op_completion_ns_exact",
            ),
            module.ring_ladder,
        ),
        (
            "latency_omitted_after_first_op",
            module.INITIAL_RING_SCHED,
            probe(
                module.ring_chain_completion,
                module.defect_ring_latency_omitted_after_first,
                "per_op_completion_ns_exact",
            ),
            module.ring_ladder,
        ),
    ]


def _canonical(result) -> bytes:
    """The whole MinimizationResult as canonical bytes (sorted keys,
    Fractions as strings — no host metadata, no wall clock)."""

    def clean(value):
        if is_dataclass(value) and not isinstance(value, type):
            return {f.name: clean(getattr(value, f.name)) for f in fields(value)}
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(item) for item in value]
        if isinstance(value, Fraction):
            return str(value)
        return value

    return json.dumps(
        clean(result), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def test_same_disagreement_same_shrink_byte_identical() -> None:
    # Two invocations with freshly built probes and ladders: the whole
    # result — minimal case, every probe, pass count — must be equal
    # AND canonically byte-identical.  Non-vacuous: every trial must
    # have found and actually shrunk a reproducer (the committed record
    # pins the same; a change here is a finding, not noise).
    module = _load_builder()
    for name, initial, probe, ladder in _real_trials(module):
        first = minimize(initial, probe, ladder)
        second = minimize(initial, probe, ladder)
        assert first.reproducer_found, (
            f"{name}: the disagreement no longer reproduces at the initial "
            "case — a finding about the carrier or the engine, not this test"
        )
        assert first.minimal_case != first.initial_case, (
            f"{name}: the minimizer no longer shrinks this disagreement"
        )
        assert first == second, name
        assert _canonical(first) == _canonical(second), (
            f"{name}: two invocations of the same disagreement produced "
            "different canonical bytes"
        )


def test_determinism_survives_trial_reordering() -> None:
    # No hidden cross-trial state: running the four trials in REVERSE
    # order reproduces each trial's canonical bytes from the forward
    # run (the carriers must be pure functions of the case).
    module = _load_builder()
    forward = {
        name: minimize(initial, probe, ladder)
        for name, initial, probe, ladder in _real_trials(module)
    }
    for name, initial, probe, ladder in reversed(_real_trials(module)):
        replayed = minimize(initial, probe, ladder)
        assert _canonical(replayed) == _canonical(forward[name]), (
            f"{name}: the minimization changed when other trials ran first"
        )


def test_minimization_still_matches_the_committed_record() -> None:
    # The committed immutable record is a prior invocation of the same
    # disagreements: the recomputed search statistics (passes, probe
    # count, accepted count) and the minimal cases must equal it.  A
    # divergence means the search or a carrier drifted since the record
    # was stored — a finding; the record is append-only (a change
    # requires a v2, never an edit).
    module = _load_builder()
    record = json.loads(COMMITTED.read_text(encoding="utf-8"))
    by_id = {trial["defect_id"]: trial for trial in record["trials"]}
    for name, initial, probe, ladder in _real_trials(module):
        result = minimize(initial, probe, ladder)
        committed = by_id[name]
        assert result.passes == committed["minimization"]["passes"], name
        assert len(result.probes) == committed["minimization"]["probes"], name
        assert (
            sum(1 for p in result.probes if p.accepted)
            == committed["minimization"]["accepted"]
        ), name
        from essun.diagnosis.minimize import _public

        assert _public(result.minimal_case) == committed["minimal_case"], name
        assert _public(result.initial_case) == committed["initial_case"], name
