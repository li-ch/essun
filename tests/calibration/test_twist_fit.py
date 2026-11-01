"""Immutability + fence guard for the stage-TWIST calibration re-fit
record (the H2 wiring-axis re-fit of the CAL-A5 falsifier after the
wrap-edge wiring model change, under the immutable split record S1
``3862e227…``, group G4).

The TWIST re-fit runs under the SAME immutable split record as S5: none
of the G4 anchors carries a within-series split, every executed payload
is fit-side, and no held-out reporting run exists in this stage. No
cross-anchor holdout (the split's four holdout anchors, plus blocked
GF-06) may be read by any objective, swept value, or tolerance — the
TWIST record carries ZERO holdout anchor ids in its bytes.

This guard re-executes the stage's whole evidence chain (the two sweeps
and the two dimensioned runs) into a scratch store and rebuilds the
record BYTE-IDENTICALLY from it, then checks the separation invariants
on the committed record. A drift of the committed copy is an error: the
record is append-only (a change requires twist_record_v2).
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
TWIST = REPO / "experiments" / "calibration" / "twist"
BUILDER = TWIST / "build_twist_record.py"
COMMITTED_COPY = TWIST / "twist_record_v1.json"
SWEEP_MANIFESTS = {
    "torus128": TWIST / "sweep_twist_torus128_v1.yaml",
    "torus256": TWIST / "sweep_twist_torus256_v1.yaml",
}
RUN_MANIFESTS = {
    "twist128": TWIST / "run_twist_a5_slice128.yaml",
    "twist256": TWIST / "run_twist_a5_slice256.yaml",
}

SWEEP_IDS = {
    "torus128": "4328bb00dd7dcae76a342d60d0fec306e707ca66c991e6affcbe295a21cd03f3",
    "torus256": "b6e40ab682800841306618730a49c4e3c07f1d319f3d8c6ae0982103f3aac86a",
}
RUN_IDS = {
    "twist128": "6197d3adf776ab8479caa2ec88e5c7acd325c1b78a183935ff8d1bcbf5dc5da8",
    "twist256": "1e55ccfa2d10ca5a113b4263d91f76d6b83bd5808599c3b3deadee257634f0f1",
}
RECORD_ID = "25f3d8880755c9315b7dd8fa2f27624f821e237aab5d1e66f848a9f13bd4f200"

HOLDOUT_ANCHOR_IDS = ("GF-01", "GF-03", "GF-11", "GF-06", "CAL-A4")
ANCHOR_IDS = ["CAL-A5"]
S5_RECORD_ID = "43fca722ff77711d67b2879dca1407510dd6a60132e047d6b34fd7b7ee6bb34b"
SPLIT_RECORD_ID = "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20"
W_GRID = {Fraction(1, 2), Fraction(3, 4), Fraction(1), Fraction(5, 4),
          Fraction(3, 2), Fraction(7, 4), Fraction(2)}
A5_TWIST = {128: Fraction(163, 100), 256: Fraction(131, 100)}
ANCHOR_CCT = {128: Fraction(227424, 25), 256: Fraction(387552, 25)}
LATENCY_FLOOR = {128: Fraction(8800), 256: Fraction(15200)}
S5_B_DELIVERED = {128: Fraction(928, 17325), 256: Fraction(944, 14725)}


def _load_builder():
    spec = importlib.util.spec_from_file_location("twist_record_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scratch_record(tmp_path_factory):
    """Re-execute the TWIST evidence chain into a scratch store and
    rebuild the record from it (the documented reproduce path)."""
    scratch = tmp_path_factory.mktemp("twist_scratch_results")
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


# ---------------------------------------------------------------------------
# byte identity + evidence dimensions
# ---------------------------------------------------------------------------

def test_scratch_rebuild_is_byte_identical_to_committed_copy(scratch_record):
    record, _, _ = scratch_record
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    assert COMMITTED_COPY.read_bytes() == record_bytes


def test_record_carries_valid_v2_evidence_dimensions(scratch_record):
    record, _, _ = scratch_record
    problems = dimensions_problems(record["evidence_dimensions"])
    assert problems == []
    assert record["evidence_schema_version"] == 2
    assert record["calibration_target"] == ANCHOR_IDS


def test_no_holdout_anchor_id_anywhere_in_record_bytes(scratch_record):
    # The separation fence, mechanically: the split record's holdout
    # anchors and its blocked anchor appear NOWHERE in the record bytes.
    record, _, _ = scratch_record
    blob = canonical_json(record)
    for holdout_id in HOLDOUT_ANCHOR_IDS:
        assert holdout_id not in blob, holdout_id


# ---------------------------------------------------------------------------
# the one-sided law, executed
# ---------------------------------------------------------------------------

def test_one_sided_law_exact_on_every_executed_row(scratch_record):
    record, _, _ = scratch_record
    for ranks in (128, 256):
        block = record["executed_sweeps"][f"torus{ranks}"]
        law = block["one_sided_law_executed"]
        base = Fraction(law["bridge_row_exact"])
        assert base == ANCHOR_CCT[ranks]
        # every inert row is the anchor point EXACTLY (5 declared + bridge)
        assert len(law["inert_rows_exact"]) == 5
        assert {Fraction(x) for x in law["inert_rows_exact"]} == {ANCHOR_CCT[ranks]}
        # the active side is strictly slower and equals the landed identity
        # at per-link B*w (the B-displacement side)
        for w_str, cct_str in law["active_rows_exact"].items():
            w = Fraction(w_str)
            assert Fraction(cct_str) > base
            b_equiv = Fraction(50) * w
            bw_bytes = {
                128: Fraction(14848),
                256: Fraction(15104),
            }[ranks]
            assert Fraction(cct_str) == bw_bytes / b_equiv + LATENCY_FLOOR[ranks]


def test_registry_triangle_executes_the_law_at_b64(scratch_record):
    record, _, _ = scratch_record
    for ranks in (128, 256):
        rows = record["executed_sweeps"][f"torus{ranks}"]["rows"]
        b64 = {
            Fraction(r["w_exact"]): Fraction(r["cct_ns_exact"])
            for r in rows if r["family"] == "registry_B64_triangle"
        }
        assert set(b64) == {Fraction(1, 2), Fraction(1), Fraction(2)}
        assert b64[Fraction(1)] == b64[Fraction(2)]  # inert at the ceiling
        bw_bytes = {128: Fraction(14848), 256: Fraction(15104)}[ranks]
        # the active side equals the landed identity at B=32 exactly
        assert b64[Fraction(1, 2)] == bw_bytes / 32 + LATENCY_FLOOR[ranks]


# ---------------------------------------------------------------------------
# the demand: exact falsification arithmetic, re-derived
# ---------------------------------------------------------------------------

def test_demanded_cct_lies_below_the_whole_wiring_axis(scratch_record):
    record, _, _ = scratch_record
    per_slice = record["fits"]["cal_a5_twist_refit"]["per_slice"]
    for ranks_str, demanded, floor, ratio in (
        ("128", Fraction(909696, 163), Fraction(8800), Fraction(163, 100)),
        ("256", Fraction(1550208, 131), Fraction(15200), Fraction(131, 100)),
    ):
        sl = per_slice[ranks_str]
        assert Fraction(sl["anchor_point_cct_ns_exact"]) == ANCHOR_CCT[int(ranks_str)]
        assert Fraction(sl["required_twisted_cct_ns_exact"]) == demanded
        assert Fraction(sl["b_to_infinity_latency_chain_floor_ns_exact"]) == floor
        assert demanded < floor  # below the B->infinity floor (S5 leg)
        verdict = sl["wiring_axis_verdict"]
        # the wiring axis's minimum IS the regular CCT: the demand lies
        # below the axis's ENTIRE range, and the axis delivers exactly 0%.
        assert Fraction(verdict["axis_minimum_cct_ns_exact"]) == ANCHOR_CCT[int(ranks_str)]
        assert Fraction(verdict["delivered_fraction_of_required_gain_exact"]) == 0
        assert float(verdict["delivered_fraction_pct"]) == 0.0
        # the unbounded-B leg is S5's own number, re-derived exactly
        b_leg = Fraction(verdict["versus_unbounded_b_axis"]["delivered_fraction_exact"])
        assert b_leg == S5_B_DELIVERED[int(ranks_str)]


def test_l_absorption_misattribution_legs_stand_unchanged(scratch_record):
    record, _, _ = scratch_record
    per_slice = record["fits"]["cal_a5_twist_refit"]["per_slice"]
    expected = {
        "128": Fraction(5383072, 44825),
        "256": Fraction(9441472, 62225),
    }
    for ranks_str, value in expected.items():
        leg = per_slice[ranks_str]["l_absorption_misattribution_leg"]
        assert Fraction(leg["value_exact"]) == value
        assert leg["in_declared_range"] is True
        assert "never selected" in leg["status"]


# ---------------------------------------------------------------------------
# the S5 immutability bridge
# ---------------------------------------------------------------------------

def test_s5_bridge_rows_equal_the_committed_s5_record(scratch_record):
    record, _, _ = scratch_record
    bridge = record["s5_immutability_bridge"]
    s5 = json.loads(
        (REPO / "experiments" / "calibration" / "s5" / "fit_record_v1.json").read_text(
            encoding="utf-8"
        )
    )
    committed_rows = {}
    for sweep in ("torus128", "torus256"):
        committed_rows[sweep] = {
            Fraction(r["B_exact"]): Fraction(r["cct_ns_exact"])
            for r in s5["executed_sweeps"][sweep]["rows"]
            if r["faithful_projection"]
        }
    checked = 0
    for check in bridge["checks"]:
        if check["s5_committed_row_cct_exact"] is not None:
            sweep = f"torus{check['slice']}"
            committed = committed_rows[sweep][Fraction(check["equivalent_B_exact"])]
            assert Fraction(check["s5_committed_row_cct_exact"]) == committed
            assert Fraction(check["twist_stage_cct_exact"]) == committed
            checked += 1
    # at least the B=25 equivalence at BOTH slices plus both anchor points
    assert checked >= 4, checked


# ---------------------------------------------------------------------------
# registry discipline + prior records
# ---------------------------------------------------------------------------

def test_registry_state_unchanged_and_split_cited(scratch_record):
    record, _, _ = scratch_record
    reg = record["registry_state_unchanged"]
    assert Fraction(reg["A-L0T-WIRE"]["value"]) == 1
    assert Fraction(reg["A-L0T-BW"]["value"]) == 64
    assert record["split_record"]["record_id"] == SPLIT_RECORD_ID
    assert record["prior_records"]["s5_fit_record_id"] == S5_RECORD_ID
    # the anchor's ratios (1.63 / 1.31) are NOT sweep-grid members: every
    # swept w is a uniform quarter step — the anchor selects nothing
    for ranks in (128, 256):
        ws = {
            Fraction(r["w_exact"])
            for r in record["executed_sweeps"][f"torus{ranks}"]["rows"]
            if r["family"] == "anchor_w_grid"
        }
        assert ws == W_GRID
        assert A5_TWIST[ranks] not in ws


def test_record_id_matches_committed_copy(scratch_record):
    import hashlib

    record, _, _ = scratch_record
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    assert hashlib.sha256(record_bytes).hexdigest() == RECORD_ID


def test_committed_s5_record_bytes_unchanged():
    # the sharpening never touches the S5 record: its committed copy still
    # hashes to its own recorded id (append-only discipline).
    import hashlib

    s5_bytes = (
        REPO / "experiments" / "calibration" / "s5" / "fit_record_v1.json"
    ).read_bytes()
    assert hashlib.sha256(s5_bytes).hexdigest() == S5_RECORD_ID
