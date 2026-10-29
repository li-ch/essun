"""Tests for the UnifiedBus paper-profile -> platform capability map (Q6 S3).

Mirrors the ladder's bar style: resolution/coverage bars, vocabulary and
shape discipline, evidence-grade passthrough, L0 targets pinned to REAL
landed backend code (cross-checked against the orchestrator's DISPATCH
table for drift), and the negative family (dangling ids, grade laundering,
unknown buckets/backends/knobs, per-bucket field leakage).
"""

from __future__ import annotations

import dataclasses

import pytest

from essun.backends.analytical import (
    l0,
    l0_crossbar,
    l0_recursive_doubling,
    l0_torus2d,
)
from essun.specir import unifiedbus_paper_profile as profile
from essun.specir import unifiedbus_platform_map as pmap
from essun.workload import w1

CONFIG_DATACLASSES = {
    l0.BACKEND_ID: l0.InfraConfig,
    l0_crossbar.BACKEND_ID: l0_crossbar.CrossbarConfig,
    l0_torus2d.BACKEND_ID: l0_torus2d.Torus2DConfig,
    l0_recursive_doubling.BACKEND_ID: l0_recursive_doubling.RecursiveDoublingConfig,
}


def test_assert_valid_passes_on_real_map():
    assert pmap.check() == []
    assert pmap.coverage_problems() == []
    pmap.assert_valid()  # must not raise


def test_exact_profile_coverage():
    mapped = {entry.parameter_id for entry in pmap.entries()}
    profile_ids = {obj.parameter_id for obj in profile.all_objects()}
    assert mapped == profile_ids
    assert len(profile_ids) == 62  # 54 design + 8 free
    assert len(pmap.entries()) == 62


def test_bucket_counts_match_stage_report():
    by_bucket = {bucket: pmap.by_bucket(bucket) for bucket in pmap.BUCKETS}
    assert {name: len(ids) for name, ids in by_bucket.items()} == {
        "L0_READY": 8,
        "L1_L2_REQUIRED": 28,
        "UNSUPPORTED": 26,
    }
    design = {obj.parameter_id for obj in profile.parameters()}
    free = {obj.parameter_id for obj in profile.free_parameters()}
    for bucket, n_design, n_free in (
        ("L0_READY", 6, 2),
        ("L1_L2_REQUIRED", 23, 5),
        ("UNSUPPORTED", 25, 1),
    ):
        ids = {entry.parameter_id for entry in by_bucket[bucket]}
        assert len(ids & design) == n_design, bucket
        assert len(ids & free) == n_free, bucket


def test_needed_fidelity_and_reason_tallies():
    tally: dict[str, int] = {}
    for entry in pmap.by_bucket("L1_L2_REQUIRED"):
        tally[entry.needed_fidelity] = tally.get(entry.needed_fidelity, 0) + 1
    assert tally == {
        "L1_flow_collective": 8,
        "L2_packet_flit": 14,
        "L2_memory_semantic_unpinned": 6,
    }
    reasons: dict[str, int] = {}
    for entry in pmap.by_bucket("UNSUPPORTED"):
        reasons[entry.reason_kind] = reasons.get(entry.reason_kind, 0) + 1
    assert reasons == {
        "software_surface": 8,
        "design_context": 8,
        "physical_deployment_cost": 3,
        "reliability_dynamics": 3,
        "scale_out_scope": 2,
        "application_outcome": 1,
        "unquantified_claim": 1,
    }


def test_evidence_grades_pass_through_no_laundering():
    grades = {
        obj.parameter_id: (
            obj.evidence_grade if isinstance(obj, profile.UBDesignParameter) else ""
        )
        for obj in profile.all_objects()
    }
    for entry in pmap.entries():
        assert entry.evidence_grade == grades[entry.parameter_id], entry.parameter_id


def test_l0_targets_resolve_to_real_config_fields():
    """The load-bearing pin: every L0 target knob is a field of the backend's
    config dataclass in the landed code, not an aspirational name."""
    l0_entries = pmap.by_bucket("L0_READY")
    assert any(entry.targets for entry in l0_entries)  # non-workload entries exist
    for entry in l0_entries:
        for target in entry.targets:
            assert target.backend_id in CONFIG_DATACLASSES
            names = {
                f.name for f in dataclasses.fields(CONFIG_DATACLASSES[target.backend_id])
            }
            assert (
                target.knob.replace(".", "_") in names
                or target.knob.rsplit(".", 1)[-1] in names
            ), (entry.parameter_id, target.knob)


def test_topology_classes_match_orchestrator_dispatch():
    """Drift guard: the map's declared topology classes must equal the
    orchestrator's DISPATCH table for the targeted backends."""
    from essun.orchestrator import runs as orchestrator_runs

    for backend_id, classes in pmap.BACKEND_TOPOLOGY_CLASSES.items():
        assert set(orchestrator_runs.DISPATCH[backend_id]) == set(classes), backend_id


def test_workload_kinds_are_landed_generators():
    scoped = [e for e in pmap.by_bucket("L0_READY") if e.l0_role == "workload_scoping"]
    assert [e.parameter_id for e in scoped] == ["UBP-P39"]
    assert scoped[0].workload_kinds == (w1.WORKLOAD_KIND,)
    assert w1.WORKLOAD_KIND in pmap.ALLOWED_WORKLOAD_KINDS


def test_l0_role_knob_consistency():
    for entry in pmap.by_bucket("L0_READY"):
        if entry.l0_role == "workload_scoping":
            continue
        allowed = pmap._ROLE_KNOB_KINDS[entry.l0_role]
        for target in entry.targets:
            assert pmap._KNOB_KINDS[target.knob] in allowed, (
                entry.parameter_id,
                target.knob,
            )


def _replace(entry, **kwargs):
    return dataclasses.replace(entry, **kwargs)


def _with_entry(entry):
    return pmap.entries() + (entry,)


# ------------------------------------------------------------------ negatives


def test_check_rejects_dangling_profile_id():
    rogue = _replace(
        pmap.entries()[0],
        parameter_id="UBP-P99",
        evidence_grade="",
    )
    problems = pmap.check(_with_entry(rogue))
    assert any("not an S2 profile object id" in p for p in problems)
    assert any("UBP-P99" in p for p in problems)
    assert pmap.coverage_problems(_with_entry(rogue)) == [
        "mapped id UBP-P99 is not an S2 profile object"
    ]


def test_check_rejects_grade_laundering():
    p05 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P05")
    assert p05.evidence_grade == "VENDOR_CLAIMED"
    problems = pmap.check(
        tuple(_replace(e, evidence_grade="PAPER_REPORTED") if e is p05 else e
              for e in pmap.entries())
    )
    assert any("does not echo the S2 object grade" in p for p in problems)


def test_check_rejects_unknown_bucket():
    bad = _replace(pmap.entries()[0], bucket="L3_QUANTUM")
    problems = pmap.check(
        tuple(_replace(e, bucket="L3_QUANTUM") if e is pmap.entries()[0] else e
              for e in pmap.entries())
    )
    assert any("unknown bucket" in p for p in problems)


def test_check_rejects_l0_entry_without_targets():
    p17 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P17")
    stripped = _replace(p17, targets=())
    problems = pmap.check(
        tuple(_replace(e, targets=()) if e is p17 else e for e in pmap.entries())
    )
    assert any("L0_READY entry needs targets" in p for p in problems)


def test_check_rejects_workload_scoping_with_targets():
    p39 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P39")
    polluted = _replace(p39, targets=(pmap.UBPlatformTarget(
        "analytical_l0", "unidirectional_ring", "ranks"
    ),))
    problems = pmap.check(
        tuple(_replace(e, targets=polluted.targets) if e is p39 else e
              for e in pmap.entries())
    )
    assert any("workload_scoping entry must not carry targets" in p for p in problems)


def test_check_rejects_l1l2_entry_with_targets():
    p01 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P01")
    polluted = _replace(
        p01,
        targets=(pmap.UBPlatformTarget("analytical_l0", "unidirectional_ring", "ranks"),),
    )
    problems = pmap.check(
        tuple(_replace(e, targets=polluted.targets) if e is p01 else e
              for e in pmap.entries())
    )
    assert any("L1_L2_REQUIRED entry carries L0/UNSUPPORTED fields" in p for p in problems)


def test_check_rejects_unsupported_without_reason_kind():
    p50 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P50")
    stripped = _replace(p50, reason_kind="")
    problems = pmap.check(
        tuple(_replace(e, reason_kind="") if e is p50 else e for e in pmap.entries())
    )
    assert any("reason_kind" in p and "not in" in p for p in problems)


def test_check_rejects_bad_needed_fidelity():
    p33 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P33")
    problems = pmap.check(
        tuple(_replace(e, needed_fidelity="L0") if e is p33 else e
              for e in pmap.entries())
    )
    assert any("needed_fidelity" in p for p in problems)


def test_check_rejects_nonexistent_knob():
    p07 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P07")
    bad_targets = (
        pmap.UBPlatformTarget("analytical_l0", "unidirectional_ring", "link.gigabytes_per_ns"),
    )
    problems = pmap.check(
        tuple(_replace(e, targets=bad_targets) if e is p07 else e for e in pmap.entries())
    )
    assert any("does not resolve to a config field" in p for p in problems)


def test_check_rejects_unknown_backend_target():
    p17 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P17")
    bad_targets = (
        pmap.UBPlatformTarget("analytical_l0_clos", "symmetric_clos", "ranks"),
    )
    problems = pmap.check(
        tuple(_replace(e, targets=bad_targets) if e is p17 else e for e in pmap.entries())
    )
    assert any("not a landed analytical backend" in p for p in problems)


def test_check_rejects_role_knob_mismatch():
    p07 = next(e for e in pmap.entries() if e.parameter_id == "UBP-P07")
    bad_targets = (
        pmap.UBPlatformTarget("analytical_l0", "unidirectional_ring", "ranks"),
    )
    problems = pmap.check(
        tuple(_replace(e, targets=bad_targets) if e is p07 else e for e in pmap.entries())
    )
    assert any("may not target" in p for p in problems)


def test_coverage_rejects_missing_entry():
    trimmed = tuple(
        e for e in pmap.entries() if e.parameter_id != "UBP-F01"
    )
    problems = pmap.coverage_problems(trimmed)
    assert problems == ["S2 object UBP-F01 has no platform mapping"]


def test_coverage_rejects_extra_entry():
    doubled = pmap.entries() + (pmap.entries()[0],)
    # A duplicate id is a coverage non-issue but a check() issue; the pure
    # extra-id case is the rogue-id test above. Here: duplicate detection.
    problems = pmap.check(doubled)
    assert any("duplicate mapping id" in p for p in problems)


def test_by_bucket_rejects_unknown_bucket():
    with pytest.raises(ValueError):
        pmap.by_bucket("L4_TELEPATHIC")
