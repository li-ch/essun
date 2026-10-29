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
  honest 445 = 189 informational + 255 unsupported + 1 executed
  (simulated_behavior, the flagship promotion of UEC11-FC-R02 via
  binding BIND-UEC11-FC-R02-L0TFC, 2026-10-29), with the
  67 free parameters reported OUTSIDE the table (declared freedom is not a
  requirement);
- the UnifiedBus paper-derived profile reports REAL per-disposition counts
  since ladder S5 (2026-10-29): 54 requirements = 32 informational +
  22 unsupported, ZERO executed (no reviewed binding exists for
  UnifiedBus), 8 free parameters outside the table.  Ladder-internal
  change, declared: S2 pinned an explicit-absence note here; the S5
  dispositions resolved the absence and the pin moved from the note to
  the counts (which say the same thing more strongly: nothing executed);
- the rendered report prints ``unsupported`` and the executed fraction
  plainly, and the CLI artifact runs and prints the same numbers
  (``--json`` round-trips).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

from essun.specir.disposition_coverage import (
    EXECUTED_DISPOSITIONS,
    UEC_STAGE_MODULES,
    UNIFIEDBUS_PROFILE_MODULE,
    coverage_report,
    module_disposition_counts,
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
    assert totals["informational"] == 189
    assert totals["unsupported"] == 255
    assert totals["simulated_behavior"] == 1  # UEC11-FC-R02, BIND-UEC11-FC-R02-L0TFC
    assert set(totals) == set(DISPOSITIONS)
    assert uec.executed == 1  # the flagship promotion (was 0 at the D1 start)
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
    assert " 255 " in uec_section.replace("\n", " ")  # the plain count
    assert "1/445 = 0.2%" in uec_section  # the executed fraction
    assert "67" in uec_section  # free parameters stated, outside the table
    ub_section = text.split("Profile: UnifiedBus paper-derived profile")[1]
    assert " 22 " in ub_section.replace("\n", " ")  # unsupported, plainly
    assert "0/54 = 0.0%" in ub_section  # zero executed, plainly
    assert "8" in ub_section  # free parameters outside the table
    assert "445" in text and "1 executed" in text  # platform total line
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
    assert "255" in result.stdout  # unsupported, printed plainly
    assert "1/445 = 0.2%" in result.stdout


def test_cli_json_flag_round_trips() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["profiles"][0]["requirements_total"] == 445
    assert data["profiles"][0]["executed"] == 1
