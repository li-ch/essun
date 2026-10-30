"""S2 of the dispositions ladder: the per-profile coverage report.

Design doc D1 gate (2026-10-29): "a coverage report (per-disposition
counts) ships with every profile."  :mod:`essun.specir.disposition_coverage`
computes that report LIVE from the five specir stage modules and renders it
printable (``tools/disposition_coverage.py``, ``make disposition-report``).

Bars enforced here:

- the report covers exactly the five S1 stage modules and its per-module
  counts agree with the frozen S1 review record (``EXPECTED_COUNTS`` in
  tests/specir/test_dispositions.py) — computed and frozen can never
  disagree silently;
- every row keeps all six disposition columns, zeros included (a dropped
  column would be a silent claim);
- row totals equal the live ``requirements()`` counts; UEC totals are the
  honest 445 = 187 informational + 254 unsupported + 4 executed
  (simulated_behavior: the flagship promotion of UEC11-FC-R02 via
  binding BIND-UEC11-FC-R02-L0TFC, 2026-10-29, and the G2 credit-family
  promotions of UEC11-FC-R08 via BIND-UEC11-FC-R08-L0TFC, 2026-10-30,
  and UEC11-FC-R09 via BIND-UEC11-FC-R09-L0TFC, 2026-10-30;
  conformance_test: the UEC11-FC-R05 credit-arrival arithmetic as
  profile checks UEC11-CHK-12/13/14, G2 stage S4, 2026-10-30 — the
  platform's first conformance count),
  with the 67 free parameters reported OUTSIDE the table (declared
  freedom is not a requirement);
- the UnifiedBus paper-derived profile reports REAL per-disposition counts
  since ladder S5 (2026-10-29): 54 requirements = 32 informational +
  22 unsupported, ZERO executed (no reviewed binding exists for
  UnifiedBus), 8 free parameters outside the table.  Ladder-internal
  change, declared: S2 pinned an explicit-absence note here; the S5
  dispositions resolved the absence and the pin moved from the note to
  the counts (which say the same thing more strongly: nothing executed);
- the rendered report prints ``unsupported`` and the executed fraction
  plainly, and the CLI artifact runs and prints the same numbers
  (``--json`` round-trips);
- since the credit-family ladder's S6 (2026-10-30) the report also states
  the G2 credit-family ladder window: the frozen program-start BEFORE
  (family 33 informational / 32 unsupported / 1 simulated_behavior at
  commit 3db1d4e; profile-wide 189/255/1), the live AFTER (family
  31/31/3 simulated_behavior + 1 conformance_test; profile-wide
  187/254/3 + 1 conformance_test = 4 executed of 445), every change
  justified by the landed binding/check and its commit, and the 56 stays
  stated plainly — the window record raises on drift instead of rendering
  a stale story.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from essun.specir.disposition_coverage import (
    CREDIT_FAMILY_BEFORE_COMMIT,
    CREDIT_FAMILY_BEFORE_COUNTS,
    CREDIT_FAMILY_CAPABLE_NOT_PLANNED,
    CREDIT_FAMILY_CHANGES,
    CREDIT_FAMILY_RE_POINT,
    DispositionChange,
    EXECUTED_DISPOSITIONS,
    LadderWindow,
    UEC_STAGE_MODULES,
    UNIFIEDBUS_PROFILE_MODULE,
    coverage_report,
    credit_family_window,
    module_disposition_counts,
    reconcile_window,
    render_report,
    report_json,
    unifiedbus_profile_coverage,
    uec_profile_coverage,
)
from essun.specir.uec_link_transport import DISPOSITIONS

# The frozen S1 record — the single review-owned count source.  Importing
# it here pins report-vs-record agreement instead of duplicating numbers.
from test_dispositions import EXPECTED_COUNTS, STAGE_MODULES
from test_unifiedbus_paper_profile import EXPECTED_UB_COUNTS

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "tools" / "disposition_coverage.py"


# -- the report is computed from exactly the S1 modules -----------------------


def test_report_modules_are_exactly_the_s1_stage_modules() -> None:
    uec = uec_profile_coverage()
    assert {m.module for m in uec.modules} == set(STAGE_MODULES)
    assert {d for d, _ in UEC_STAGE_MODULES} == set(STAGE_MODULES)
    assert len(uec.modules) == 5


def test_module_counts_agree_with_the_frozen_s1_record() -> None:
    uec = uec_profile_coverage()
    for mod in uec.modules:
        expected = dict.fromkeys(DISPOSITIONS, 0)
        expected.update(EXPECTED_COUNTS[mod.module])
        assert mod.counts == expected, mod.module


def test_counts_helper_keeps_all_six_dispositions() -> None:
    for dotted, _ in UEC_STAGE_MODULES:
        module = importlib.import_module(dotted)
        counts = module_disposition_counts(module)
        assert set(counts) == set(DISPOSITIONS)  # zeros kept, none dropped
        assert sum(counts.values()) == len(module.requirements())


def test_row_totals_match_live_requirement_counts() -> None:
    for mod in uec_profile_coverage().modules:
        live = importlib.import_module(mod.module).requirements()
        assert mod.total == len(live), mod.module


# -- the honest UEC totals ------------------------------------------------------


def test_uec_profile_totals() -> None:
    uec = uec_profile_coverage()
    assert uec.requirements_total == 445
    totals = uec.total_counts()
    assert totals["informational"] == 187
    assert totals["unsupported"] == 254
    assert (
        totals["simulated_behavior"] == 3
    )  # FC-R02 (flagship) + FC-R08 (G2 S2) + FC-R09 (G2 S3)
    assert (
        totals["conformance_test"] == 1
    )  # FC-R05 credit-arrival arithmetic (G2 S4)
    assert set(totals) == set(DISPOSITIONS)
    assert uec.executed == 4  # flagship + G2 S2/S3 bindings + G2 S4 check
    assert uec.free_parameters == 67  # outside the table by design


def test_executed_dispositions_are_the_d1_three() -> None:
    assert set(EXECUTED_DISPOSITIONS) == {
        "constraint",
        "simulated_behavior",
        "conformance_test",
    }


# -- UnifiedBus: real counts since S5, zero executed -----------------------------


def test_unifiedbus_counts_are_real_and_zero_executed() -> None:
    # S5 resolved S2's explicit-absence note: the design parameters carry
    # dispositions now, so the section reports a real table.  The honest
    # headline survives the migration: NOTHING is executed (no reviewed
    # binding exists for UnifiedBus).
    ub = unifiedbus_profile_coverage()
    assert [m.module for m in ub.modules] == [UNIFIEDBUS_PROFILE_MODULE]
    assert ub.requirements_total == 54
    totals = ub.total_counts()
    assert totals == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 32,
        "unsupported": 22,
    }
    assert ub.executed == 0
    assert ub.free_parameters == 8
    assert "not normative" in ub.note and "zero executed" in ub.note


def test_unifiedbus_module_counts_agree_with_the_frozen_s5_record() -> None:
    ub = unifiedbus_profile_coverage()
    for mod in ub.modules:
        expected = dict.fromkeys(DISPOSITIONS, 0)
        expected.update(EXPECTED_UB_COUNTS)
        assert mod.counts == expected, mod.module
        live = importlib.import_module(mod.module).requirements()
        assert mod.total == len(live) == 54


def test_coverage_report_lists_both_profiles() -> None:
    profiles = coverage_report()
    assert [p.profile for p in profiles] == [
        "UEC 1.1 semantic profile",
        "UnifiedBus paper-derived profile",
    ]


# -- the printable artifact -----------------------------------------------------


def test_rendered_report_shows_unsupported_plainly() -> None:
    text = render_report()
    for disposition in DISPOSITIONS:  # every column header present
        assert disposition in text
    assert "unsupported" in text
    uec_section = text.split("Profile: UEC 1.1 semantic profile")[1].split(
        "Profile: UnifiedBus"
    )[0]
    assert " 254 " in uec_section.replace("\n", " ")  # the plain count
    assert "4/445 = 0.9%" in uec_section  # the executed fraction
    assert "67" in uec_section  # free parameters stated, outside the table
    ub_section = text.split("Profile: UnifiedBus paper-derived profile")[1]
    assert " 22 " in ub_section.replace("\n", " ")  # unsupported, plainly
    assert "0/54 = 0.0%" in ub_section  # zero executed, plainly
    assert "8" in ub_section  # free parameters outside the table
    assert "445" in text and "4 executed" in text  # platform total line
    assert "499 disposition-bearing requirements" in text  # 445 + 54


def test_json_report_keeps_zeros_and_sums() -> None:
    data = report_json()
    assert data["dispositions"] == list(DISPOSITIONS)
    uec = data["profiles"][0]
    assert len(uec["modules"]) == 5
    assert sum(uec["total_counts"].values()) == uec["requirements_total"] == 445
    for module in uec["modules"]:
        assert set(module["counts"]) == set(DISPOSITIONS)
        assert sum(module["counts"].values()) == module["total"]
    ub = data["profiles"][1]
    assert len(ub["modules"]) == 1
    assert sum(ub["total_counts"].values()) == ub["requirements_total"] == 54
    assert ub["executed"] == 0
    assert ub["free_parameters"] == 8
    assert set(ub["modules"][0]["counts"]) == set(DISPOSITIONS)  # zeros kept
    assert ub["note"]


# -- the CLI artifact ------------------------------------------------------------


def test_cli_prints_the_report_table() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "disposition coverage report" in result.stdout
    assert "profile total" in result.stdout
    assert "254" in result.stdout  # unsupported, printed plainly
    assert "4/445 = 0.9%" in result.stdout


def test_cli_json_flag_round_trips() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["profiles"][0]["requirements_total"] == 445
    assert data["profiles"][0]["executed"] == 4


# -- the G2 credit-family ladder window (S6, 2026-10-30) --------------------------


def test_window_before_is_the_frozen_program_start_record() -> None:
    # Pinned to the program-start literals: re-verified live against a
    # worktree of CREDIT_FAMILY_BEFORE_COMMIT by stage S6 before this pin
    # landed (family 33/32/1 of 66; profile-wide 189/255/1 of 445).
    assert CREDIT_FAMILY_BEFORE_COMMIT == "3db1d4e"
    assert CREDIT_FAMILY_BEFORE_COUNTS == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 33,
        "unsupported": 32,
        "simulated_behavior": 1,
    }


def test_window_after_is_the_live_family_row_not_a_copy() -> None:
    window = credit_family_window(coverage_report())
    family = next(
        m
        for m in uec_profile_coverage().modules
        if m.module.endswith("uec_credits_flow_control")
    )
    assert window.after == family.counts
    assert window.requirements_total == 66
    assert window.executed == 4


def test_window_derives_the_profile_wide_before_live() -> None:
    # Profile-wide program start (189/255/1, 1 executed of 445) is DERIVED
    # as live profile totals minus the named changes' deltas — which also
    # asserts nothing outside the family flipped during the window.
    window = credit_family_window(coverage_report())
    assert window.profile_before == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 189,
        "unsupported": 255,
        "simulated_behavior": 1,
    }
    assert window.profile_after["informational"] == 187
    assert window.profile_after["unsupported"] == 254
    assert window.profile_after["simulated_behavior"] == 3
    assert window.profile_after["conformance_test"] == 1


def test_window_changes_name_the_landed_carriers_and_commits() -> None:
    by_requirement = {c.requirement: c for c in CREDIT_FAMILY_CHANGES}
    assert by_requirement["UEC11-FC-R08"] == DispositionChange(
        requirement="UEC11-FC-R08",
        before="informational",
        after="simulated_behavior",
        carrier="binding BIND-UEC11-FC-R08-L0TFC",
        commit="11aec6d",
    )
    assert by_requirement["UEC11-FC-R09"].carrier == (
        "binding BIND-UEC11-FC-R09-L0TFC"
    )
    assert by_requirement["UEC11-FC-R09"].commit == "c22e256"
    assert by_requirement["UEC11-FC-R05"].after == "conformance_test"
    assert by_requirement["UEC11-FC-R05"].carrier == (
        "profile checks UEC11-CHK-12/13/14"
    )
    assert by_requirement["UEC11-FC-R05"].commit == "9af9e33"
    # the re-point moved the executed semantics, not the disposition
    assert CREDIT_FAMILY_RE_POINT.requirement == "UEC11-FC-R02"
    assert CREDIT_FAMILY_RE_POINT.before == CREDIT_FAMILY_RE_POINT.after
    assert "BIND-UEC11-FC-R02-AUTOMATON" in CREDIT_FAMILY_RE_POINT.carrier
    assert CREDIT_FAMILY_RE_POINT.commit == "0854a13"
    assert len(CREDIT_FAMILY_CHANGES) == 3  # no unnamed promotions


def test_window_carriers_exist_in_the_live_registries() -> None:
    import essun.specir.bindings as bindings_module

    binding_ids = {b.binding_id for b in bindings_module.BINDINGS}
    for binding_id in (
        "BIND-UEC11-FC-R02-AUTOMATON",
        "BIND-UEC11-FC-R08-L0TFC",
        "BIND-UEC11-FC-R09-L0TFC",
    ):
        assert binding_id in binding_ids, binding_id
    # R05's carrier is checks, not a binding (the D2 rule): the shipped
    # profile artifact must carry all three check ids referencing R05.
    profile = (REPO_ROOT / "experiments" / "uec" / "semantic_profile.yaml").read_text()
    for check_id in ("UEC11-CHK-12", "UEC11-CHK-13", "UEC11-CHK-14"):
        assert f"check_id: {check_id}" in profile, check_id
    window = credit_family_window(coverage_report())
    for change in (*window.changes, window.re_point):
        assert change.carrier  # every named carrier is non-empty


def test_window_registry_dispositions_match_every_named_change() -> None:
    family = importlib.import_module("essun.specir.uec_credits_flow_control")
    live = {r.requirement_id: r.disposition for r in family.requirements()}
    window = credit_family_window(coverage_report())
    for change in (*window.changes, window.re_point):
        assert live[change.requirement] == change.after, change.requirement
        if change is not window.re_point:
            assert change.before != change.after  # real flips only


def test_window_stays_are_the_point_not_the_count() -> None:
    window = credit_family_window(coverage_report())
    assert window.stays_unsupported == 31
    assert window.stays_informational == 25
    assert window.stays_total == 56  # the inventory's STAYS verdict tally
    non_executed = window.requirements_total - window.executed
    assert window.stays_total + len(window.capable_not_planned) == non_executed
    family = importlib.import_module("essun.specir.uec_credits_flow_control")
    live = {r.requirement_id: r.disposition for r in family.requirements()}
    assert all(live[r] == "informational" for r in CREDIT_FAMILY_CAPABLE_NOT_PLANNED)


def test_window_record_refuses_to_render_when_stale() -> None:
    # A future promotion must consciously edit the window record: a stale
    # BEFORE (or a change list missing the flip) raises instead of
    # rendering a story the registries no longer tell.
    window = credit_family_window(coverage_report())
    stale = LadderWindow(
        module=window.module,
        before_commit=window.before_commit,
        before=dict(window.before, informational=window.before["informational"] + 1),
        after=dict(window.after),
        profile_before=dict(window.profile_before),
        profile_after=dict(window.profile_after),
        changes=window.changes,
        re_point=window.re_point,
        stays_unsupported=window.stays_unsupported,
        stays_informational=window.stays_informational,
        capable_not_planned=window.capable_not_planned,
    )
    with pytest.raises(ValueError, match="stale"):
        reconcile_window(stale)


def test_window_record_refuses_a_change_list_missing_a_flip() -> None:
    # Dropping one named change from the record must also fail: BEFORE +
    # two changes does not land on the live family row.
    window = credit_family_window(coverage_report())
    incomplete = LadderWindow(
        module=window.module,
        before_commit=window.before_commit,
        before=dict(window.before),
        after=dict(window.after),
        profile_before=dict(window.profile_before),
        profile_after=dict(window.profile_after),
        changes=tuple(
            c for c in window.changes if c.requirement != "UEC11-FC-R09"
        ),
        re_point=window.re_point,
        stays_unsupported=window.stays_unsupported,
        stays_informational=window.stays_informational,
        capable_not_planned=window.capable_not_planned,
    )
    with pytest.raises(ValueError, match="stale"):
        reconcile_window(incomplete)


def test_rendered_report_states_the_window() -> None:
    text = render_report()
    window_section = text.split("credit-family ladder window")[1]
    for fragment in (
        "3db1d4e",
        "1 simulated_behavior / 33 informational / 32 unsupported — 1/66",
        "3 simulated_behavior / 1 conformance_test / 31 informational / "
        "31 unsupported — 4/66",
        "1 simulated_behavior / 189 informational / 255 unsupported — 1/445",
        "3 simulated_behavior / 1 conformance_test / 187 informational / "
        "254 unsupported — 4/445",
        "BIND-UEC11-FC-R08-L0TFC (11aec6d)",
        "BIND-UEC11-FC-R09-L0TFC (c22e256)",
        "profile checks UEC11-CHK-12/13/14 (9af9e33)",
        "BIND-UEC11-FC-R02-AUTOMATON",
        "0854a13",
        "disposition unchanged",
        "56 of the family's 62 non-executed",
        "31 unsupported + 25 informational",
        "credit_family_inventory.md",
        "honesty outranks coverage",
    ):
        assert fragment in window_section, fragment
    # the window sits inside the report, before the platform total
    assert text.index("credit-family ladder window") < text.index(
        "platform total"
    )


def test_json_report_carries_the_window() -> None:
    data = report_json()
    window = data["credit_family_window"]
    assert window["before_commit"] == "3db1d4e"
    assert window["before_counts"] == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 33,
        "unsupported": 32,
        "simulated_behavior": 1,
    }
    assert window["after_counts"] == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 31,
        "unsupported": 31,
        "simulated_behavior": 3,
        "conformance_test": 1,
    }
    assert window["profile_before_counts"] == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 189,
        "unsupported": 255,
        "simulated_behavior": 1,
    }
    assert window["profile_after_counts"] == dict.fromkeys(DISPOSITIONS, 0) | {
        "informational": 187,
        "unsupported": 254,
        "simulated_behavior": 3,
        "conformance_test": 1,
    }
    changes = {c["requirement"]: c for c in window["changes"]}
    assert set(changes) == {"UEC11-FC-R08", "UEC11-FC-R09", "UEC11-FC-R05"}
    assert changes["UEC11-FC-R05"]["carrier"] == (
        "profile checks UEC11-CHK-12/13/14"
    )
    assert window["binding_re_point"]["requirement"] == "UEC11-FC-R02"
    assert window["binding_re_point"]["before"] == window["binding_re_point"]["after"]
    assert window["stays"] == {"unsupported": 31, "informational": 25, "total": 56}
    assert len(window["capable_not_planned"]) == 6
