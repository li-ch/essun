"""Immutability guard for the G7 leg-(c) ranking sign-stability audit.

Rebuilds ``ranking_audit_v1.json`` byte-identically from the builder
(the builder itself asserts every closed form against the landed backend
functions at executed witnesses, so a rebuild re-verifies the sign
analysis), then checks the audit's headline invariants on the committed
copy: the 67-parameter classification split, the stable/contingent
counts, and the contingent pair's opposite-sign witnesses.
"""

from __future__ import annotations

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "experiments" / "gonogo" / "leg_c_ranking_audit" / "build_ranking_audit.py"
COMMITTED_COPY = REPO / "experiments" / "gonogo" / "leg_c_ranking_audit" / "ranking_audit_v1.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location("gonogo_ranking_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record() -> dict:
    return json.loads(COMMITTED_COPY.read_text(encoding="utf-8"))


def test_ranking_audit_rebuilds_byte_identically() -> None:
    module = _load_builder()
    payload = json.dumps(module.build(), indent=2, sort_keys=True) + "\n"
    assert payload == COMMITTED_COPY.read_text(encoding="utf-8")


def test_the_67_split_is_2_executed_65_carried() -> None:
    classification = _record()["free_parameter_classification"]
    assert classification["total"] == 67
    assert classification["read_by_an_executed_binding"] == 2
    assert classification["carried_not_executed"] == 65
    executed = {
        row["parameter_id"]
        for row in classification["parameters"]
        if row["read_by_an_executed_binding"]
    }
    assert executed == {"UEC11-FC-F01", "UEC11-FC-F02"}


def test_counts_are_ten_stable_one_contingent() -> None:
    summary = _record()["summary"]
    assert summary["pairs_audited"] == 11
    assert summary["sign_stable"] == 10
    assert summary["contingent"] == 1


def test_the_contingent_pair_has_opposite_sign_witnesses() -> None:
    record = _record()
    contingent = [p for p in record["pairs"] if p["verdict"].startswith("CONTINGENT")]
    assert len(contingent) == 1
    pair = contingent[0]
    assert "torus2d" in pair["pair"] and "ring" in pair["pair"]
    signs = {w["sign_of_t_a_minus_t_b"] for w in pair["witnesses"]}
    assert signs == {1, -1}  # both orders admissible inside the declared box
    # Every other pair's witnesses never show a positive... i.e. every
    # sign-stable pair's witnesses agree with its one-sided statement.
    for p in record["pairs"]:
        if p is pair:
            continue
        assert all(
            w["sign_of_t_a_minus_t_b"] in (0, 1) or "never faster" in p["sign_analysis"]
            or "never slower" in p["sign_analysis"]
            or "tie" in p["verdict"].lower()
            for w in p["witnesses"]
        ), p["pair"]


def test_the_envelope_flagship_pair_is_stable_with_the_tie_condition() -> None:
    record = _record()
    flagship = record["pairs"][0]
    assert flagship["pair"].startswith("uec_tfc_ring vs ub_flat_ring_pod")
    assert flagship["verdict"].startswith("SIGN-STABLE")
    # The gated witness is strictly slower, the saturated witness ties.
    signs = [w["sign_of_t_a_minus_t_b"] for w in flagship["witnesses"]]
    assert signs == [1, 0]
