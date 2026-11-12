"""Profile-surface matrix tool tests (generic; neutral fixture profile)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.profile_matrix import build_rows, render_markdown


@pytest.fixture()
def fixture_profile(tmp_path: Path) -> Path:
    """A minimal, schema-valid neutral profile (no real fabric's values)."""
    import yaml

    profile = {
        "format": {"name": "essun-profile", "version": "0.1"},
        "profile_id": "fixture-fabric-1.0-semantic",
        "source": {"name": "Fixture Fabric Spec 1.0", "document_id": "FIX-1", "revision": "1.0"},
        "provenance": {"source_record": "n/a", "access": "PUBLIC_READ",
                       "pdf_sha256": "0" * 64, "note": "test fixture"},
        "requirements": {"objects": [
            {"requirement_id": "FIX-R01", "anchor_ids": ["FIX-S1"], "keyword": "DEFINITIONAL",
             "subject": "fabric", "statement": "Fixture statement one.", "disposition": "informational"},
            {"requirement_id": "FIX-R02", "anchor_ids": ["FIX-S1"], "keyword": "MECHANISM",
             "subject": "fabric", "statement": "Fixture statement two.", "disposition": "simulated_behavior"},
        ]},
        "freedom": [
            {"parameter_id": "FIX-F01", "name": "bandwidth", "freedom": "free",
             "anchor_ids": ["FIX-S1"], "domain": "FREE"},
        ],
        "bindings": [
            {"requirement_id": "FIX-R02", "backend": "analytical_l0",
             "capability": "fixture binding"},
        ],
        "checks": [
            {"check_id": "FIX-C01", "kind": "invariant", "requirement_ids": ["FIX-R02"],
             "description": "fixture invariant"},
        ],
        "supported": {"workloads": ["w1_dense_tp_decode"], "observables": ["O-CCT"]},
        "calibration": {"status": "uncalibrated", "targets": [], "note": "fixture"},
        "omissions": [{"what": "fixture gap", "why": "fixture"}],
        "versioning": {"profile_version": "0.1.0",
                       "bump_rules": {"major": ["format.version"], "minor": ["requirements"], "patch": []}},
    }
    path = tmp_path / "semantic_profile.yaml"
    path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return path


def test_fixture_profile_rows(tmp_path, fixture_profile):
    rows = build_rows([fixture_profile])
    assert len(rows) == 1
    row = rows[0]
    assert row["profile_id"] == "fixture-fabric-1.0-semantic"
    assert row["access"] == "PUBLIC_READ"
    assert row["requirements"] == 2
    assert row["dispositions"]["informational"] == 1
    assert row["dispositions"]["simulated_behavior"] == 1
    assert row["free_parameters"] == 1
    assert row["bindings"] == 1
    assert row["calibration"] == "uncalibrated"
    assert row["omissions"] == 1
    assert row["workloads"] == ["w1_dense_tp_decode"]


def test_render_markdown_contains_every_row(tmp_path, fixture_profile):
    markdown = render_markdown(build_rows([fixture_profile]))
    assert "fixture-fabric-1.0-semantic" in markdown
    assert "uncalibrated" in markdown
    assert "w1_dense_tp_decode" in markdown


def test_repo_public_profiles_load(tmp_path):
    """The tool works against the repo's real, public profiles today."""
    repo = Path(__file__).resolve().parents[2]
    profiles = sorted(
        (repo / "experiments").glob("*/semantic_profile.yaml")
    )
    assert profiles, "no public profiles found in the repo"
    rows = build_rows(profiles)
    assert len(rows) == len(profiles)
    ids = {r["profile_id"] for r in rows}
    assert any("uec" in pid for pid in ids)
