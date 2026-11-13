"""Conformance gate for the ODS 1.0 semantic profile.

Checks (mirroring the other public-profile gates):
- the artifact loads through the essun profile loader;
- every anchor quote is a verbatim substring of its page text and
  every page file's sha256 matches the registry;
- every quote is <= 120 characters;
- zero-binding honesty: no simulated_behavior disposition exists, so
  the empty bindings list is consistent;
- corruption rejection: a mutated artifact fails the loader;
- byte-identical regeneration from the builder.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

import pytest
import yaml

from essun.specir.profile_format import ProfileFormatError, load_profile

REPO = pathlib.Path(__file__).resolve().parents[2]
PROFILE = REPO / "experiments" / "ods" / "semantic_profile.yaml"
REGISTRY = REPO / "experiments" / "ods" / "anchor_registry.yaml"
PAGES = REPO / "experiments" / "ods" / "source" / "pages"
BUILDER = REPO / "experiments" / "ods" / "build_semantic_profile.py"


def test_loads_with_expected_shape():
    loaded = load_profile(PROFILE)
    assert loaded.profile_id == "ods-1.0-semantic" or "ods" in str(loaded.profile_id)


def test_anchor_quotes_resolve_verbatim_and_short():
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    anchors = {a["id"]: a for a in data["anchors"]}
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    cited = set()
    for module in profile["requirements"].values():
        for req in module:
            cited.update(req["anchor_ids"])
    for param in profile["freedom"]:
        cited.update(param["anchor_ids"])
    assert cited, "profile cites no anchors"
    assert cited <= set(anchors), f"unknown anchors: {cited - set(anchors)}"
    for aid in sorted(cited):
        anchor = anchors[aid]
        assert len(anchor["quote"]) <= 120, f"{aid}: quote longer than 120 chars"
        page_file = PAGES / f"page_{anchor['page']:04d}.txt"
        # extracted text wraps lines mid-word; quotes are matched against the
        # newline-stripped page text so a wrap inside a quote is not a mismatch
        page_text = page_file.read_text(encoding="utf-8").replace("\n", "")
        assert anchor["quote"] in page_text, f"{aid}: quote not verbatim on page"
        digest = hashlib.sha256(page_file.read_bytes()).hexdigest()
        assert digest == anchor["page_sha256"], f"{aid}: page sha256 drift"


def test_zero_binding_honesty():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    dispositions = [
        req["disposition"]
        for module in profile["requirements"].values()
        for req in module
    ]
    assert "simulated_behavior" not in dispositions
    assert profile["bindings"] == []
    assert profile["checks"] == []


def test_corruption_rejected(tmp_path: pathlib.Path):
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    profile.pop("freedom")  # remove a required key
    bad = tmp_path / "bad_ods_profile.yaml"
    bad.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ProfileFormatError):
        load_profile(bad)


def test_byte_identical_regeneration(tmp_path: pathlib.Path):
    out = tmp_path / "regen_semantic_profile.yaml"
    code = (
        "import importlib.util, pathlib; "
        f"spec = importlib.util.spec_from_file_location('b', {str(BUILDER)!r}); "
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
        f"pathlib.Path({str(out)!r}).write_text(m.build(), encoding='utf-8')"
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=str(REPO))
    assert out.read_bytes() == PROFILE.read_bytes()
