"""M1 S3: NVLink-class paper-profile -> platform capability map tests.

Mirrors the UnifiedBus S3 tests
(``tests/specir/test_unifiedbus_platform_map.py``) for the third fabric's
map (``essun.specir.nvlink_platform_map``): exact coverage of the S2
objects, evidence-grade passthrough (no laundering), L0 targets resolving
to real landed backend config fields with role/knob consistency, the
frozen bucket tallies of the M1 record, and the negative bars.
"""

from __future__ import annotations

import dataclasses

import pytest

from essun.specir import nvlink_platform_map as pm
from essun.specir import nvlink_paper_profile as profile


def test_assert_valid_passes_on_real_map():
    pm.assert_valid()  # must not raise


def test_exact_profile_coverage():
    assert pm.coverage_problems() == []


def test_bucket_counts_match_m1_record():
    l0 = pm.by_bucket("L0_READY")
    l12 = pm.by_bucket("L1_L2_REQUIRED")
    unsup = pm.by_bucket("UNSUPPORTED")
    assert len(l0) == 11
    assert len(l12) == 16
    assert len(unsup) == 3
    assert len(pm.entries()) == len(profile.all_objects()) == 30


def test_needed_fidelity_and_reason_tallies():
    fidelities = {}
    for entry in pm.by_bucket("L1_L2_REQUIRED"):
        fidelities[entry.needed_fidelity] = fidelities.get(entry.needed_fidelity, 0) + 1
    assert set(fidelities) <= set(pm.NEEDED_FIDELITIES)
    assert fidelities == {"L1_flow_collective": 8, "L2_packet_flit": 8}
    reasons = {}
    for entry in pm.by_bucket("UNSUPPORTED"):
        reasons[entry.reason_kind] = reasons.get(entry.reason_kind, 0) + 1
    assert set(reasons) <= set(pm.REASON_KINDS)
    assert reasons == {
        "physical_deployment_cost": 1,
        "design_context": 1,
        "software_surface": 1,
    }


def test_evidence_grades_pass_through_no_laundering():
    grades = {
        obj.parameter_id: (
            obj.evidence_grade if isinstance(obj, profile.NVDesignParameter) else ""
        )
        for obj in profile.all_objects()
    }
    for entry in pm.entries():
        assert entry.evidence_grade == grades[entry.parameter_id], entry.parameter_id


def test_l0_targets_resolve_to_real_config_fields():
    from essun.orchestrator import runs

    for entry in pm.by_bucket("L0_READY"):
        assert entry.targets, entry.parameter_id
        for target in entry.targets:
            assert target.backend_id in pm._BACKEND_CONFIGS
            assert (
                target.topology_class
                in pm.BACKEND_TOPOLOGY_CLASSES[target.backend_id]
            ), (entry.parameter_id, target.knob)
            config_cls = pm._BACKEND_CONFIGS[target.backend_id]
            from dataclasses import fields as dataclass_fields

            names = {f.name for f in dataclass_fields(config_cls)}
            assert (
                target.knob.replace(".", "_") in names
                or target.knob.rsplit(".", 1)[-1] in names
            ), (entry.parameter_id, target.knob)
            assert target.backend_id in runs.DISPATCH


def test_the_comparison_identity_rows_back_the_crossbar():
    # The M1 comparison's NV flavor identity chain: NVP-P01 (crossbar
    # class) and NVP-P13 (domain scale) must have L0_READY rows backing
    # the fully_connected_crossbar identity on the landed crossbar backend.
    for parameter_id in ("NVP-P01", "NVP-P13"):
        matching = [e for e in pm.by_bucket("L0_READY") if e.parameter_id == parameter_id]
        assert matching, parameter_id
        assert any(
            t.backend_id == "analytical_l0_crossbar"
            and t.topology_class == "fully_connected_crossbar"
            and t.knob == "ranks"
            for e in matching
            for t in e.targets
        ), parameter_id


def test_free_parameter_gates_cover_every_bandwidth_and_latency_knob():
    gates = [e for e in pm.by_bucket("L0_READY") if e.l0_role == "free_parameter_gate"]
    assert {e.parameter_id for e in gates} == {"NVP-F01", "NVP-F02"}
    for entry in gates:
        knobs = {t.knob for t in entry.targets}
        if entry.parameter_id == "NVP-F01":
            assert knobs == {
                "link.bytes_per_ns", "nic.injection_bytes_per_ns",
            }
        else:
            assert knobs == {"link.hop_latency_ns", "link.pair_latency_ns"}


def test_check_rejects_dangling_profile_id():
    rogue = dataclasses.replace(pm.entries()[0], parameter_id="NVP-P-NOPE")
    assert any("not an S2 profile object id" in p for p in pm.check((rogue,)))


def test_check_rejects_grade_laundering():
    entry = next(e for e in pm.entries() if e.parameter_id == "NVP-P13")
    rogue = dataclasses.replace(entry, evidence_grade="PAPER_REPORTED")
    assert any("does not echo" in p for p in pm.check((rogue,)))


def test_check_rejects_unknown_bucket():
    rogue = dataclasses.replace(pm.entries()[0], bucket="L3_WISHLIST")
    assert any("unknown bucket" in p for p in pm.check((rogue,)))


def test_check_rejects_l0_entry_without_targets():
    entry = next(e for e in pm.by_bucket("L0_READY") if e.l0_role != "workload_scoping")
    rogue = dataclasses.replace(entry, targets=())
    assert any("needs targets" in p for p in pm.check((rogue,)))


def test_check_rejects_l1l2_entry_with_targets():
    entry = pm.by_bucket("L1_L2_REQUIRED")[0]
    rogue = dataclasses.replace(
        entry,
        targets=(pm.NVPlatformTarget("analytical_l0", "unidirectional_ring", "ranks"),),
    )
    assert any("carries L0/UNSUPPORTED fields" in p for p in pm.check((rogue,)))


def test_check_rejects_unsupported_without_reason_kind():
    entry = pm.by_bucket("UNSUPPORTED")[0]
    rogue = dataclasses.replace(entry, reason_kind="vibes")
    assert any("reason_kind" in p for p in pm.check((rogue,)))


def test_check_rejects_bad_needed_fidelity():
    entry = pm.by_bucket("L1_L2_REQUIRED")[0]
    rogue = dataclasses.replace(entry, needed_fidelity="L9_quantum")
    assert any("needed_fidelity" in p for p in pm.check((rogue,)))


def test_check_rejects_nonexistent_knob():
    entry = next(
        e for e in pm.by_bucket("L0_READY") if e.l0_role == "rank_scale"
    )
    targets = tuple(
        dataclasses.replace(t, knob="quantum.entanglement") for t in entry.targets
    )
    rogue = dataclasses.replace(entry, targets=targets)
    assert any("does not resolve to a config field" in p for p in pm.check((rogue,)))


def test_check_rejects_role_knob_mismatch():
    # rank_scale may not target a bandwidth knob
    entry = next(
        e for e in pm.by_bucket("L0_READY") if e.l0_role == "rank_scale"
    )
    targets = (pm.NVPlatformTarget(
        "analytical_l0_crossbar", "fully_connected_crossbar",
        "nic.injection_bytes_per_ns",
    ),)
    rogue = dataclasses.replace(entry, targets=targets)
    assert any("may not target" in p for p in pm.check((rogue,)))


def test_coverage_rejects_missing_entry():
    assert any(
        "has no platform mapping" in p
        for p in pm.coverage_problems(pm.entries()[:-1])
    )


def test_coverage_rejects_extra_entry():
    rogue = dataclasses.replace(pm.entries()[0], parameter_id="NVP-P-EXTRA")
    assert any(
        "is not an S2 profile object" in p
        for p in pm.coverage_problems(pm.entries() + (rogue,))
    )


def test_by_bucket_rejects_unknown_bucket():
    with pytest.raises(ValueError, match="unknown bucket"):
        pm.by_bucket("L0_WISHLIST")
