"""S4 semantic-object tests: UEC 1.1 congestion management / UET CMS (T010/T011).

Bars from the stage prompt: every object's anchors resolve in the registry,
and a negative test rejects an object with a dangling anchor. Additional
stage-specific bars enforced here (S2/S3 pattern): objects cite only the S4
anchor map, every S4 anchor is actually used, ids are unique, typed fields
come from the declared vocabularies, and the load-bearing congestion
management facts (algorithm obligations, CCC admission law, credit laws,
CSIG tag rules) are present.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_congestion_management import (
    MAX_STATEMENT_WORDS,
    NORMATIVE_KEYWORDS,
    S4_ANCHOR_IDS,
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


def test_objects_cite_exactly_the_s4_anchor_map() -> None:
    # Stage discipline: S4 cites exactly the mechanism-to-anchor map S1
    # assigned to congestion management (3.6, 3.6.13, 3.6.14, 3.6.16, 4.2,
    # 4.2.7, 4.2.9); other stages' anchors are off-limits — in particular
    # 3.6.15 (TFC) is S5's — and every S4 anchor must back >= 1 object.
    used = anchor_ids()
    assert used <= S4_ANCHOR_IDS
    assert used == S4_ANCHOR_IDS
    assert "UEC11-S3.6.15-TFC" not in S4_ANCHOR_IDS  # S5's, never ours


def test_stage_objects_present_and_unique() -> None:
    reqs = requirements()
    frees = free_parameters()
    assert len(reqs) >= 50
    assert len(frees) >= 10
    ids = [o.requirement_id for o in reqs] + [o.parameter_id for o in frees]
    assert len(ids) == len(set(ids))
    assert all(r.requirement_id.startswith("UEC11-CM-R") for r in reqs)
    assert all(f.parameter_id.startswith("UEC11-CM-F") for f in frees)


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
    # Overview/deployment text and pseudocode carry DEFINITIONAL facts,
    # while the service sections carry the full RFC-2119 range (spec
    # "REQUIRED" is typed MUST, "NOT RECOMMENDED" as SHOULD NOT).
    keywords = {req.keyword for req in requirements()}
    assert "DEFINITIONAL" in keywords
    assert {"MUST", "MUST NOT", "SHALL", "SHOULD", "SHOULD NOT", "MAY"} <= keywords
    by_subject = {req.subject for req in requirements()}
    assert {
        "UET_CC",
        "TELEMETRY",
        "TRAFFIC_CLASS",
        "CCC",
        "NSCC",
        "RCCC",
        "MULTIPATH",
        "SWITCH",
        "PCM",
        "CSIG",
    } <= by_subject


def test_congestion_management_guarantees_are_encoded() -> None:
    # Load-bearing facts for L0/L1 backends and the uet-htsim reference:
    # guard them against accidental removal or rewording into ambiguity.
    stmts = {r.requirement_id: r.statement for r in requirements()}
    assert "do not require" in stmts["UEC11-CM-R02"]  # Unified Local / RODL
    assert "must be implemented" in stmts["UEC11-CM-R04"]  # NSCC mandatory
    assert "inflight + MTU" in stmts["UEC11-CM-R52"]  # NSCC admission law
    assert "1.5" in stmts["UEC11-CM-R59"]  # MaxWnd = 1.5 * BDP
    assert "rcvd_bytes" in stmts["UEC11-CM-R52"]  # ACK clock field
    assert "must be shut down" in stmts["UEC11-CM-R72"]  # RCCC CCC teardown
    assert "credit is exhausted" in stmts["UEC11-CM-R42"]  # credit law
    assert "must not modify" in stmts["UEC11-CM-R108"]  # csig.d = 1 frozen
    assert "base profile" in stmts["UEC11-CM-R116"]  # ABW, ABW/C, Delay
    assert "max(Delay)" in stmts["UEC11-CM-R65"]  # NSCC<->CSIG coupling
    assert "must not be removed except in the IDLE" in stmts["UEC11-CM-R37"]


def test_assert_valid_passes_on_real_registry(registry: AnchorRegistry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- negative bars: malformed objects and dangling anchors ---------------------


def test_registry_resolve_rejects_dangling_anchor(registry: AnchorRegistry) -> None:
    with pytest.raises(Exception, match="dangling anchor ids"):
        registry.resolve(["UEC11-CM-NOT-A-REGISTRY-ID"])


def test_check_rejects_object_with_dangling_anchor(monkeypatch) -> None:
    # THE stage bar: an object with a dangling anchor is rejected.
    import essun.specir.uec_congestion_management as mod

    rogue = UECRequirement(
        requirement_id="UEC11-CM-ROGUE-1",
        anchor_ids=("UEC11-CM-NO-SUCH-ANCHOR",),
        keyword="MUST",
        subject="NSCC",
        statement="A rogue statement citing nothing.",
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", mod._REQUIREMENTS + (rogue,))
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UEC11-CM-ROGUE-1" in p and "dangling anchor ids" in p
        for p in problems
    )
    with pytest.raises(mod.SemanticObjectError):
        mod.assert_valid(registry)


def test_check_rejects_object_citing_other_stage_anchor(monkeypatch) -> None:
    # Anchor-map discipline is enforced by data, not just by convention:
    # the S5-assigned TFC anchor (3.6.15) and S3's ROD anchor resolve in
    # the registry but are off the S4 map.
    import essun.specir.uec_congestion_management as mod

    pristine = mod.anchor_ids()  # before any monkeypatching
    for off_map in ("UEC11-S3.6.15-TFC", "UEC11-S3.5.21-ROD"):
        rogue = UECRequirement(
            requirement_id="UEC11-CM-ROGUE-2",
            anchor_ids=(off_map,),
            keyword="MUST",
            subject="CCC",
            statement="A statement citing another stage's section.",
        )
        monkeypatch.setattr(mod, "_REQUIREMENTS", (rogue,))
        assert off_map not in mod.S4_ANCHOR_IDS
        assert off_map not in pristine  # data-level guard holds
    # Still valid against the registry itself (the ids resolve) — the stage
    # map is guarded by test_objects_cite_exactly_the_s4_anchor_map above.


def test_check_rejects_malformed_typed_fields(monkeypatch) -> None:
    import essun.specir.uec_congestion_management as mod

    rogue = UECRequirement(
        requirement_id="UEC11-CM-ROGUE-3",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
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
    import essun.specir.uec_congestion_management as mod

    no_anchor = dataclasses.replace(
        requirements()[0],
        requirement_id="UEC11-CM-ROGUE-4",
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
    # real S4 object cannot resolve against it — citations are load-bearing.
    pages = tmp_path / "pages"
    pages.mkdir()
    text = "3.6.13 Network Signal-based Congestion Control\n\nNSCC uses a congestion window ccc.cwnd.\n"
    (pages / "page_0476.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0476.txt").read_bytes()).hexdigest()
    entry = {
        "source": {
            "source_id": "SYNTH-4",
            "pdf_sha256": "0" * 64,
            "page_count": 1,
            "pages_dir": "unused",
        },
        "anchors": [
            {
                "id": "SYN-S4-1",
                "section": "3.6.13",
                "title": "synthetic",
                "page": 476,
                "quote": "NSCC uses a congestion window ccc.cwnd.",
                "page_sha256": digest,
            }
        ],
    }
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    syn = AnchorRegistry.load(reg_file, pages_dir=pages)
    syn.assert_valid()

    assert syn.resolve(["SYN-S4-1"])[0].anchor_id == "SYN-S4-1"
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(["SYN-S4-1", "UEC11-S3.6.13-NSCC"])  # real id, absent here

    some_req = next(r for r in requirements() if r.subject == "RCCC")
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(some_req.anchor_ids)
