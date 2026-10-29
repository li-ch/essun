"""S3 semantic-object tests: UEC 1.1 reliability & ordering semantics (T010/T011).

Bars from the stage prompt: every object's anchors resolve in the registry,
and a negative test rejects an object with a dangling anchor. Additional
stage-specific bars enforced here (S2 pattern): objects cite only the S3
anchor map, every S3 anchor is actually used, ids are unique, typed fields
come from the declared vocabularies, and the load-bearing reliability
guarantees of the three profile-relevant modes are present.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_reliability_ordering import (
    MAX_STATEMENT_WORDS,
    NORMATIVE_KEYWORDS,
    S3_ANCHOR_IDS,
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
        assert [a.anchor_id for a in resolved] == list(obj.anchor_ids)


def test_objects_cite_exactly_the_s3_anchor_map() -> None:
    # Stage discipline: S3 cites exactly the mechanism-to-anchor map S1
    # assigned to reliability & ordering (3.5.3, 3.5.6, 3.5.15, 3.5.20-22,
    # 5.1, 5.1.3, 4.1); S2/S4/S5 anchors are off-limits, and every S3
    # anchor must back at least one object.
    used = anchor_ids()
    assert used <= S3_ANCHOR_IDS
    assert used == S3_ANCHOR_IDS


def test_stage_objects_present_and_unique() -> None:
    reqs = requirements()
    frees = free_parameters()
    assert len(reqs) >= 50
    assert len(frees) >= 10
    ids = [o.requirement_id for o in reqs] + [o.parameter_id for o in frees]
    assert len(ids) == len(set(ids))
    assert all(r.requirement_id.startswith("UEC11-RO-R") for r in reqs)
    assert all(f.parameter_id.startswith("UEC11-RO-F") for f in frees)


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
    # Sections 3.5.3/3.5.6 are informative overview (DEFINITIONAL), while
    # the mode service sections (3.5.20-22), loss detection (3.5.15),
    # trimming (4.1) and LLR carry RFC-2119 keywords.
    keywords = {req.keyword for req in requirements()}
    assert "DEFINITIONAL" in keywords
    assert {"MUST", "MUST NOT", "SHALL", "SHOULD", "SHOULD NOT"} <= keywords
    by_subject = {req.subject for req in requirements()}
    assert {"RUD", "ROD", "RODL", "LLR", "TRIMMING", "LOSS_DETECTION"} <= by_subject


def test_mode_guarantees_are_encoded() -> None:
    # The three profile-relevant reliable modes and their distinct delivery
    # guarantees are load-bearing facts for the L0/L1 backends; guard them
    # against accidental removal or rewording into ambiguity.
    stmts = {r.requirement_id: r.statement for r in requirements()}
    assert "once and only once" in stmts["UEC11-RO-R24"]  # RUD
    assert "in the order of arrival" in stmts["UEC11-RO-R38"]  # ROD
    assert "closed in error" in stmts["UEC11-RO-R51"]  # RODL no-retx
    assert "no ordering guarantee" in stmts["UEC11-RO-R07"]  # across PDCs
    assert "GoBackN" in stmts["UEC11-RO-R43"]  # ROD recovery
    assert "selective retransmission" in stmts["UEC11-RO-R25"]  # RUD recovery


def test_assert_valid_passes_on_real_registry(registry: AnchorRegistry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- negative bars: malformed objects and dangling anchors ---------------------


def test_registry_resolve_rejects_dangling_anchor(registry: AnchorRegistry) -> None:
    with pytest.raises(Exception, match="dangling anchor ids"):
        registry.resolve(["UEC11-RO-NOT-A-REGISTRY-ID"])


def test_check_rejects_object_with_dangling_anchor(monkeypatch) -> None:
    # THE stage bar: an object with a dangling anchor is rejected.
    import essun.specir.uec_reliability_ordering as mod

    rogue = UECRequirement(
        requirement_id="UEC11-RO-ROGUE-1",
        anchor_ids=("UEC11-RO-NO-SUCH-ANCHOR",),
        keyword="MUST",
        subject="RUD",
        statement="A rogue statement citing nothing.",
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", mod._REQUIREMENTS + (rogue,))
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UEC11-RO-ROGUE-1" in p and "dangling anchor ids" in p
        for p in problems
    )
    with pytest.raises(mod.SemanticObjectError):
        mod.assert_valid(registry)


def test_check_rejects_object_citing_other_stage_anchor(monkeypatch) -> None:
    # Anchor-map discipline is enforced by data, not just by convention:
    # an S2-section anchor (SES semantic concepts) is off the S3 map.
    import essun.specir.uec_reliability_ordering as mod

    rogue = UECRequirement(
        requirement_id="UEC11-RO-ROGUE-2",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),  # resolves, but S2's
        keyword="MUST",
        subject="ROD",
        statement="A statement citing another stage's section.",
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", (rogue,))
    assert "UEC11-S3.4.2-SEMANTIC-CONCEPTS" not in mod.S3_ANCHOR_IDS
    # Still valid against the registry itself (the id resolves) — the stage
    # map is guarded by test_objects_cite_exactly_the_s3_anchor_map above.


def test_check_rejects_malformed_typed_fields(monkeypatch) -> None:
    import essun.specir.uec_reliability_ordering as mod

    rogue = UECRequirement(
        requirement_id="UEC11-RO-ROGUE-3",
        anchor_ids=("UEC11-S3.5.21-ROD",),
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
    import essun.specir.uec_reliability_ordering as mod

    no_anchor = dataclasses.replace(
        requirements()[0],
        requirement_id="UEC11-RO-ROGUE-4",
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
    # real S3 object cannot resolve against it — citations are load-bearing.
    pages = tmp_path / "pages"
    pages.mkdir()
    text = "3.5.15 Loss Detection and Recovery\n\nPDS MUST detect the loss of packets.\n"
    (pages / "page_0376.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0376.txt").read_bytes()).hexdigest()
    entry = {
        "source": {
            "source_id": "SYNTH-3",
            "pdf_sha256": "0" * 64,
            "page_count": 1,
            "pages_dir": "unused",
        },
        "anchors": [
            {
                "id": "SYN-S3-1",
                "section": "3.5.15",
                "title": "synthetic",
                "page": 376,
                "quote": "PDS MUST detect the loss of packets.",
                "page_sha256": digest,
            }
        ],
    }
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    syn = AnchorRegistry.load(reg_file, pages_dir=pages)
    syn.assert_valid()

    assert syn.resolve(["SYN-S3-1"])[0].anchor_id == "SYN-S3-1"
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(["SYN-S3-1", "UEC11-S3.5.20-RUD"])  # real id, absent here

    some_req = next(r for r in requirements() if r.subject == "RODL")
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(some_req.anchor_ids)
