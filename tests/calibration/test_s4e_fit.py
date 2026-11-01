"""Immutability + fence guard for the stage-S4e calibration fit record
(the endpoint-latency axis — the small-message-axis rerun of S4's group
G3 under the SAME immutable split record, 3862e227...).

The S4e fit runs under the same split as S4 v1: no G3 anchor carries a
within-series split, every executed payload is fit-side, and no
cross-anchor holdout (nor blocked GF-06) may be read by any objective,
swept value, or tolerance.

This guard re-executes the stage's whole evidence chain (the sweep and
the four dimensioned runs) into a scratch store and rebuilds the fit
record BYTE-IDENTICALLY from it, then checks the separation invariants
on the committed record. A drift of the committed copy is an error: the
record is append-only (a change requires fit_record_v2).
"""

from __future__ import annotations

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest

from essun.evidence.dimensions import dimensions_problems
from essun.evidence.store import canonical_json
from essun.orchestrator.runs import run_experiment
from essun.orchestrator.sweeps import run_sweep

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "experiments" / "calibration" / "s4e" / "build_fit_record.py"
COMMITTED_COPY = REPO / "experiments" / "calibration" / "s4e" / "fit_record_v1.json"
SWEEP_MANIFESTS = {
    "e_axis": REPO / "experiments" / "calibration" / "s4e" / "sweep_s4e_e_v1.yaml",
}
RUN_MANIFESTS = {
    "gf10_e8800": REPO / "experiments" / "calibration" / "s4e" / "run_s4e_gf10_fit_e8800.yaml",
    "a10_e600": REPO / "experiments" / "calibration" / "s4e" / "run_s4e_a10_fit_e600.yaml",
    "gf10_alt_e9000": REPO / "experiments" / "calibration" / "s4e" / "run_s4e_gf10_alt_e9000.yaml",
    "wireclass_e0": REPO / "experiments" / "calibration" / "s4e" / "run_s4e_wireclass_e0.yaml",
}

SWEEP_IDS = {
    "e_axis": "f4786367abebab56d33e89d018c425a95dca23cc7d9322e009fa45a32ab22522",
}
RUN_IDS = {
    "gf10_e8800": "607174234709f3173b391e7cdff2f9ced84af1671873721a94463b1aa1489280",
    "a10_e600": "50cb636f75e5b69d823b22d13649c4c7c4d79af5e4007c382ce09ef54d387a9a",
    "gf10_alt_e9000": "dc247a5beec8f0ef0fa64db13b3545b826b27e4c6d5e6401e4e54bbc9906d861",
    "wireclass_e0": "b8a114516d31c29851b34854fbe1e4fbc83fb55874a6fd38ab1711afaf327f93",
}

EXPECTED_GRID_E = {Fraction(v) for v in (0, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 9000)}
EXPECTED_PROV_E = {Fraction(600), Fraction(8800)}
HOLDOUT_ANCHOR_IDS = ("GF-01", "GF-03", "GF-11", "GF-06", "CAL-A4")
SMOKE = 16384


def _load_builder():
    spec = importlib.util.spec_from_file_location("s4e_fit_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the S4e evidence chain into a scratch store and rebuild
    the record from it (the documented reproduce path, end to end)."""
    scratch = tmp_path_factory.mktemp("s4e_scratch_results")
    for name, manifest in SWEEP_MANIFESTS.items():
        result = run_sweep(manifest, results_root=scratch)
        assert result["sweep_id"] == SWEEP_IDS[name], (name, result["sweep_id"])
    run_ids = {}
    for name, manifest in RUN_MANIFESTS.items():
        executed = run_experiment(manifest, results_root=scratch)
        run_ids[name] = executed["run_id"]
    assert run_ids == RUN_IDS
    builder = _load_builder()
    builder.RESULTS = scratch
    record = builder.build_record()
    return record, scratch, run_ids


def _committed_record() -> dict:
    return json.loads(COMMITTED_COPY.read_text(encoding="utf-8"))


def test_scratch_rebuild_is_byte_identical_to_committed_copy(scratch_record):
    record, _, _ = scratch_record
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    assert COMMITTED_COPY.read_bytes() == record_bytes


def test_record_carries_valid_v2_evidence_dimensions(scratch_record):
    record, _, _ = scratch_record
    assert record["evidence_schema_version"] == 2
    assert not dimensions_problems(
        {k: record[k] for k in ("verification", "calibration_target", "held_out",
                                "independent_reproduction", "known_omissions")}
    )
    assert record["calibration_target"] == ["CAL-A8", "CAL-A9", "CAL-A10", "GF-10"]
    assert record["held_out"]["held_out"] is False


def test_no_within_series_holdout_exists_all_runs_fit_side(scratch_record):
    record, _, run_ids = scratch_record
    assert record["held_out"]["held_out"] is False
    for name in RUN_IDS:
        payload = json.loads(
            (scratch_record[1] / run_ids[name] / "run.json").read_text()
        )
        assert payload["evidence_schema_version"] == 2
        assert payload["held_out"]["held_out"] is False, name


def test_run_records_dimensions_declare_their_anchor(scratch_record):
    _, scratch, run_ids = scratch_record
    expected_targets = {
        "gf10_e8800": ["GF-10"],
        "a10_e600": ["CAL-A10"],
        "gf10_alt_e9000": ["GF-10"],
        "wireclass_e0": ["CAL-A8", "CAL-A9"],
    }
    for name, target in expected_targets.items():
        payload = json.loads((scratch / run_ids[name] / "run.json").read_text())
        assert payload["calibration_target"] == target


def test_no_holdout_anchor_numbers_or_ids_in_record(scratch_record):
    record, _, _ = scratch_record
    text = canonical_json(record)
    for anchor_id in HOLDOUT_ANCHOR_IDS:
        assert anchor_id not in text, anchor_id


def test_grid_is_anchor_blind_and_provenance_is_labeled(scratch_record):
    record, _, _ = scratch_record
    per_e = record["executed_sweeps"]["e_axis"]["per_E_table_crossbar"]
    grid_members = {Fraction(row["E_ns"]) for row in per_e if row["grid_member"]}
    assert grid_members == EXPECTED_GRID_E
    non_grid = {Fraction(row["E_ns"]) for row in per_e if not row["grid_member"]}
    assert non_grid == EXPECTED_PROV_E
    for row in per_e:
        if not row["grid_member"]:
            assert row["provenance"].startswith("anchor:"), row
    # 0 and 9000 are grid members by range-endpoint arithmetic; their double
    # roles (registry default / the anchor figure the range was drawn from)
    # are noted inside the labels, never treated as provenance selections
    row0 = next(r for r in per_e if Fraction(r["E_ns"]) == 0)
    assert row0["grid_member"] is True
    assert "registry point" in row0["provenance"]
    row9000 = next(r for r in per_e if Fraction(r["E_ns"]) == 9000)
    assert row9000["grid_member"] is True
    assert "BY CONSTRUCTION" in row9000["provenance"]


def test_placements_are_degenerate_and_never_tuned(scratch_record):
    record, _, _ = scratch_record
    fits = record["fits"]
    assert fits["gf10"]["fitted_E"]["exact"] == "8800"
    assert "9000 - 200" in fits["gf10"]["fitted_E"]["derivation_exact"]
    assert "INSIDE the declared free range" in fits["gf10"]["fitted_E"]["range_membership"]
    assert fits["gf10"]["registry_placements"]["e_fit_over_range_upper_exact"] == "44/45"
    assert fits["cal_a10"]["fitted_E"]["exact"] == "600"
    assert fits["cal_a10"]["registry_placements"]["e_placement_over_gf10_e_fit_exact"] == "3/44"
    # the whole-figure alternative exists, is flagged, never selected
    assert fits["gf10_alt"]["fitted_E"]["exact"] == "9000"
    assert "never selected" in fits["gf10_alt"]["fitted_E"]["status"]
    # the wire-class origin reproduces the landed v1 numbers exactly
    assert fits["wireclass"]["fitted_E"]["exact"] == "0"
    assert fits["wireclass"]["identity"].startswith("the E-axis ORIGIN")
    # no fit claims to tune anything; the registry discipline is explicit
    assert "registry value stays 0" in record["not_tuned"]
    assert "wire-latency registry values stay 200" in record["not_tuned"]


def test_registry_values_untouched(scratch_record):
    record, _, _ = scratch_record
    declared = record["model"]["declared_free_parameters"]
    for param in ("A-L0-LAT", "A-L0X-LAT", "A-L0D-LAT"):
        assert declared[param]["registry_value"] == 200
        assert declared[param]["registry_range"] == [10, 2000]
        assert declared[param]["swept_by"].startswith("NONE") and "fixed at 200" in declared[param]["swept_by"]
    assert declared["A-L0E-LAT"]["registry_value"] == 0
    assert declared["A-L0E-LAT"]["registry_range"] == [0, 9000]
    # and the shipped registry files themselves still say the same
    import yaml

    l0_registry = yaml.safe_load(
        (REPO / "experiments" / "vertical_slice" / "assumptions_l0.yaml").read_text()
    )
    by_id = {e["id"]: e for e in l0_registry["assumptions"]}
    for param in ("A-L0-LAT", "A-L0X-LAT", "A-L0T-LAT", "A-L0D-LAT"):
        assert by_id[param]["value"] == 200, param
        assert list(by_id[param]["range"]) == [10, 2000], param
    e_registry = yaml.safe_load(
        (REPO / "experiments" / "vertical_slice" / "assumptions_l0e.yaml").read_text()
    )
    e_by_id = {e["id"]: e for e in e_registry["assumptions"]}
    assert e_by_id["A-L0E-LAT"]["value"] == 0
    assert list(e_by_id["A-L0E-LAT"]["range"]) == [0, 9000]
    assert e_by_id["A-L0E-CHG"]["value"] == "one_per_collective_op"
    assert "PROPOSED" in record["status"]


def test_chain_laws_recomputed_from_scratch_rows(scratch_record):
    _, scratch, _ = scratch_record
    table = json.loads(
        (scratch / "sweeps" / SWEEP_IDS["e_axis"] / "table.json").read_text()
    )
    by = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        alg = row["algorithm"]
        by[(alg, topo)] = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
    for e in (0, 16, 32, 64, 128, 256, 512, 600, 8800, 1024, 2048, 4096, 8192, 9000):
        ring = by[("allreduce_ring", f"ring8_s4e_e{e}_v1")]
        xbar = by[("allreduce_crossbar", f"crossbar8_s4e_e{e}_v1")]
        rd = by[("allreduce_recursive_doubling", f"exchange8_s4e_e{e}_v1")]
        # E cancels: the landed chain laws hold at every shared E
        assert ring - xbar == Fraction(12 * 200), e
        assert rd - xbar == Fraction(4 * 200), e
        assert ring - rd == Fraction(8 * 200), e


def test_v1_record_stands_unchanged(scratch_record):
    # The S4 v1 record is immutable and untouched by this stage; its guard
    # (tests/calibration/test_s4_fit.py) enforces its own byte-identity.
    v1 = REPO / "experiments" / "calibration" / "s4" / "fit_record_v1.json"
    record, _, _ = scratch_record
    assert v1.is_file()
    assert "the v1 record stands unchanged" in record["headline"]


def test_split_record_id_is_the_immutable_one(scratch_record):
    record, _, _ = scratch_record
    assert (
        record["split_record"]["record_id"]
        == "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20"
    )
    split = json.loads(
        (REPO / "experiments" / "calibration" / "split" / "anchor_split_v1.json").read_text()
    )
    assert split["split_version"] == "split_v1"
    assert record["split_record"]["committed_copy"].endswith("anchor_split_v1.json")
