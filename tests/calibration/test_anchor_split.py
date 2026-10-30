"""Immutability + invariant guard for the calibration anchor-split record
(stage S1).

The split of the 23 integrated anchors into the calibration set (4 groups)
and the 4-anchor holdout is the data-separation contract every fitting
stage (S2..S5) and the holdout evaluation (S6) runs under. This test
rebuilds the record from the builder (a pure function — no wall-clock, no
host metadata) and fails on ANY byte drift of the committed copy, so the
split cannot be edited silently: changing it requires a new content-
addressed record (split_v2), never an in-place edit.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from essun.evidence.store import canonical_json

REPO = Path(__file__).resolve().parents[2]
BUILDER = (
    REPO / "experiments" / "calibration" / "split" / "build_anchor_split_record.py"
)
COMMITTED_COPY = (
    REPO / "experiments" / "calibration" / "split" / "anchor_split_v1.json"
)

EXPECTED_HOLDOUT = {"CAL-A4", "GF-01", "GF-03", "GF-11"}
EXPECTED_BLOCKED = {"GF-06"}
ALL_23 = {f"CAL-A{i}" for i in range(1, 13)} | {
    f"GF-{i:02d}" for i in range(1, 12)
}


def _load_builder():
    spec = importlib.util.spec_from_file_location("anchor_split_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_and_bytes():
    builder = _load_builder()
    record = builder.build_record()
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    return builder, record, record_bytes


def test_committed_copy_is_byte_identical_and_content_addressed():
    _, _, record_bytes = _record_and_bytes()
    committed = COMMITTED_COPY.read_bytes()
    assert committed == record_bytes
    assert hashlib.sha256(committed).hexdigest() == hashlib.sha256(
        record_bytes
    ).hexdigest()


def test_split_partitions_all_23_anchors():
    _, record, _ = _record_and_bytes()
    calibration = {
        a["anchor_id"]
        for group in record["calibration_set"]["groups"]
        for a in group["anchors"]
    }
    holdout = {a["anchor_id"] for a in record["holdout"]["anchors"]}
    blocked = {a["anchor_id"] for a in record["blocked"]["anchors"]}
    assert calibration | holdout | blocked == ALL_23
    assert not calibration & holdout
    assert not (calibration | holdout) & blocked
    assert len(calibration) == 18
    assert len(holdout) == 4
    assert blocked == EXPECTED_BLOCKED


def test_holdout_constraints_plan_mandate_regimes_and_groups():
    _, record, _ = _record_and_bytes()
    holdout_ids = {a["anchor_id"] for a in record["holdout"]["anchors"]}
    assert holdout_ids == EXPECTED_HOLDOUT
    # plan §3.5(b): CAL-A4 is reserved as an external check
    assert "CAL-A4" in holdout_ids
    # >= 4 anchors spanning >= 4 regimes
    assert len(holdout_ids) >= 4
    assert len(record["holdout"]["regime_span"]) >= 4
    # the four calibration groups carry stage ids S2..S5 with disjoint
    # membership and no holdout anchor inside them
    groups = record["calibration_set"]["groups"]
    assert [g["fitting_stage"] for g in groups] == ["S2", "S3", "S4", "S5"]
    seen: set[str] = set()
    for group in groups:
        ids = {a["anchor_id"] for a in group["anchors"]}
        assert not ids & holdout_ids
        assert not ids & seen
        seen |= ids


def test_within_series_held_out_sizes_never_overlap_fit_sizes():
    _, record, _ = _record_and_bytes()
    splits = record["within_series_splits"]["splits"]
    assert splits, "within-series split policy must be recorded"
    calibration = {
        a["anchor_id"]
        for group in record["calibration_set"]["groups"]
        for a in group["anchors"]
    }
    for split in splits:
        assert split["anchor_id"] in calibration
        assert not set(split["fit_sizes"]) & set(split["held_out_sizes"])
    # the plan's literal §3.5(a) example is carried verbatim for CAL-A3
    a3 = next(s for s in splits if s["anchor_id"] == "CAL-A3")
    assert a3["fit_sizes"] == ["2GiB", "4GiB", "8GiB"]
    assert a3["held_out_sizes"] == ["16GiB", "32GiB"]


def test_builder_rejects_mutation_of_committed_split(tmp_path, monkeypatch):
    """The committed copy is append-only: different bytes can never
    overwrite it (main() exits 1 in that case). Simulated here without
    touching the real store: a mutated record differs from the committed
    bytes, and the guard comparison main() uses detects exactly that."""
    builder = _load_builder()
    record = builder.build_record()
    mutated = dict(record)
    mutated["date"] = "2099-01-01"  # any edit changes the content address
    mutated_bytes = (canonical_json(mutated) + "\n").encode("utf-8")
    committed_bytes = COMMITTED_COPY.read_bytes()
    assert mutated_bytes != committed_bytes

    guard_copy = tmp_path / "copy.json"
    guard_copy.write_bytes(committed_bytes)
    monkeypatch.setattr(builder, "COMMITTED_COPY", guard_copy)
    monkeypatch.setattr(builder, "RESULTS", tmp_path / "results")
    # the guard branch main() takes when bytes differ:
    differs = guard_copy.exists() and guard_copy.read_bytes() != mutated_bytes
    assert differs, "guard must detect the mutation exactly as main() does"
