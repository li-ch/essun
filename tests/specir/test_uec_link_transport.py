"""S2 semantic-object tests: UEC 1.1 link/transport semantics (T010/T011).

Bars from the stage prompt: every object's anchors resolve in the registry,
and a negative test rejects an object with a dangling anchor. Additional
stage-specific bars enforced here: objects cite only the S2 anchor map,
every S2 anchor is actually used, ids are unique, and typed fields
(keyword/subject) come from the declared vocabularies.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_link_transport import (
    MAX_STATEMENT_WORDS,
    NORMATIVE_KEYWORDS,
    S2_ANCHOR_IDS,
    SUBJECTS,
    UECRequirement,
    all_objects,
    anchor_ids,
    assert_valid,
    check_against_registry,
    free_parameters,
    requirements,
)


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()  # objects are checked against a verified registry
    return reg


# -- positive bars -------------------------------------------------------------


def test_all_object_anchors_resolve_in_registry(registry: AnchorRegistry) -> None:
    # The core bar: every requirement and free parameter resolves fully.
    for obj in all_objects():
        resolved = registry.resolve(obj.anchor_ids)
        assert len(resolved) == len(obj.anchor_ids)
        assert [
            anchor.anchor_id for anchor in resolved
        ] == list(obj.anchor_ids)


def test_objects_cite_exactly_the_s2_anchor_map() -> None:
    # Stage discipline: S2 cites exactly the mechanism-to-anchor map S1
    # assigned to link/transport semantics; S3/S4/S5 anchors are off-limits,
    # and every S2 anchor must back at least one object.
    used = anchor_ids()
    assert used <= S2_ANCHOR_IDS
    assert used == S2_ANCHOR_IDS


def test_stage_objects_present_and_unique() -> None:
    reqs = requirements()
    frees = free_parameters()
    assert len(reqs) >= 40
    assert len(frees) >= 10
    ids = [o.requirement_id for o in reqs] + [o.parameter_id for o in frees]
    assert len(ids) == len(set(ids))
    assert all(r.requirement_id.startswith("UEC11-LT-R") for r in reqs)
    assert all(f.parameter_id.startswith("UEC11-LT-F") for f in frees)


def test_typed_fields_use_declared_vocabularies() -> None:
    for req in requirements():
        assert req.keyword in NORMATIVE_KEYWORDS, req.requirement_id
        assert req.subject in SUBJECTS, req.requirement_id
        assert 0 < len(req.statement.split()) <= MAX_STATEMENT_WORDS


def test_free_parameters_are_marked_free() -> None:
    for param in free_parameters():
        assert param.domain == "FREE"
        assert param.freedom.strip()


def test_normative_vs_definitional_split_is_real() -> None:
    # The spec states its chapter 3 overview is informative outside 3.3, so
    # S2 must carry DEFINITIONAL facts as well as normative profile rows.
    keywords = {req.keyword for req in requirements()}
    assert "DEFINITIONAL" in keywords
    assert {"MUST", "SHALL"} <= keywords
    assert any(
        req.subject == "PROFILES" and req.keyword == "MUST"
        for req in requirements()
    )


def test_assert_valid_passes_on_real_registry(registry: AnchorRegistry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- negative bars: malformed objects and dangling anchors ---------------------


def test_registry_resolve_rejects_dangling_anchor(registry: AnchorRegistry) -> None:
    with pytest.raises(Exception, match="dangling anchor ids"):
        registry.resolve(["UEC11-LT-NOT-A-REGISTRY-ID"])


def test_check_rejects_object_with_dangling_anchor(monkeypatch) -> None:
    # THE stage bar: an object with a dangling anchor is rejected.
    import essun.specir.uec_link_transport as mod

    rogue = UECRequirement(
        requirement_id="UEC11-LT-ROGUE-1",
        anchor_ids=("UEC11-LT-NO-SUCH-ANCHOR",),
        keyword="MUST",
        subject="UET",
        statement="A rogue statement citing nothing.",
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", mod._REQUIREMENTS + (rogue,))
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UEC11-LT-ROGUE-1" in p and "dangling anchor ids" in p
        for p in problems
    )
    with pytest.raises(mod.SemanticObjectError):
        mod.assert_valid(registry)


def test_check_rejects_malformed_typed_fields(monkeypatch) -> None:
    import essun.specir.uec_link_transport as mod

    rogue = UECRequirement(
        requirement_id="UEC11-LT-ROGUE-2",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="SHALL POSSIBLY",  # not in vocabulary
        subject="QUIRKS",  # not in vocabulary
        statement="word " * (MAX_STATEMENT_WORDS + 1),  # too long
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", (rogue,))
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any("unknown keyword" in p for p in problems)
    assert any("unknown subject" in p for p in problems)
    assert any("words" in p for p in problems)


def test_check_rejects_empty_and_duplicate_objects(monkeypatch) -> None:
    import essun.specir.uec_link_transport as mod

    no_anchor = dataclasses.replace(
        requirements()[0],
        requirement_id="UEC11-LT-ROGUE-3",
        anchor_ids=(),
    )
    duplicate = dataclasses.replace(requirements()[0])  # same id twice in set
    monkeypatch.setattr(
        mod,
        "_REQUIREMENTS",
        (no_anchor,) + mod._REQUIREMENTS + (duplicate,),
    )
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any("no anchor ids" in p for p in problems)
    assert any("duplicate object id" in p for p in problems)


def test_real_object_against_synthetic_registry_is_dangling(tmp_path: Path) -> None:
    # End-to-end: a one-anchor synthetic registry validates like S1's, and a
    # real S2 object cannot resolve against it — citations are load-bearing.
    pages = tmp_path / "pages"
    pages.mkdir()
    text = "3.3 Profiles and Capabilities\n\nUET defines four profiles.\n"
    (pages / "page_0187.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0187.txt").read_bytes()).hexdigest()
    entry = {
        "source": {
            "source_id": "SYNTH-2",
            "pdf_sha256": "0" * 64,
            "page_count": 1,
            "pages_dir": "unused",
        },
        "anchors": [
            {
                "id": "SYN-S2-1",
                "section": "3.3",
                "title": "synthetic",
                "page": 187,
                "quote": "UET defines four profiles.",
                "page_sha256": digest,
            }
        ],
    }
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    syn = AnchorRegistry.load(reg_file, pages_dir=pages)
    syn.assert_valid()

    assert syn.resolve(["SYN-S2-1"])[0].anchor_id == "SYN-S2-1"
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(["SYN-S2-1", "UEC11-S3.4-SES"])  # real id, absent here

    some_req = next(r for r in requirements() if r.subject == "PROFILES")
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(some_req.anchor_ids)
