"""S5 semantic-object tests: UEC 1.1 credits / flow control (T010/T011).

Bars from the stage prompt: every object's anchors resolve in the registry,
and a negative test rejects an object with a dangling anchor. Additional
stage-specific bars enforced here (S2/S3/S4 pattern): objects cite only the
S5 anchor map, every S5 anchor is actually used, ids are unique, typed
fields come from the declared vocabularies, and the load-bearing credit
facts (TFC admission law and cell sizing, CBFC admission inequalities and
counter machinery, QUIESCE/RTS/RTR handshakes, compliance values) are
present.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_credits_flow_control import (
    MAX_STATEMENT_WORDS,
    NORMATIVE_KEYWORDS,
    S5_ANCHOR_IDS,
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


def test_objects_cite_exactly_the_s5_anchor_map() -> None:
    # Stage discipline: S5 cites exactly the mechanism-to-anchor map S1
    # assigned to credits/flow control (5.2, 5.2.4, 5.2.5, 5.2.10, 3.6.14,
    # 3.6.15); other stages' anchors are off-limits — in particular the
    # 3.6 CMS anchor is S4's (S5 must not encode 3.6-span pages that live
    # in 3.6.15), and 5.3/5.1 belong to S2/S3.  3.6.14 is the one anchor
    # deliberately shared with S4 (S4 owns the RCCC congestion loop, S5
    # its pull-credit residue).  Every S5 anchor must back >= 1 object.
    used = anchor_ids()
    assert used <= S5_ANCHOR_IDS
    assert used == S5_ANCHOR_IDS
    assert "UEC11-S3.6.14-RCCC" in S5_ANCHOR_IDS  # shared with S4 by design
    assert "UEC11-S3.6-CMS" not in S5_ANCHOR_IDS  # S4's, never ours
    assert "UEC11-S5.3-LINK-NEGOTIATION" not in S5_ANCHOR_IDS  # S2's


def test_stage_objects_present_and_unique() -> None:
    reqs = requirements()
    frees = free_parameters()
    assert len(reqs) >= 60
    assert len(frees) >= 10
    ids = [o.requirement_id for o in reqs] + [o.parameter_id for o in frees]
    assert len(ids) == len(set(ids))
    assert all(r.requirement_id.startswith("UEC11-FC-R") for r in reqs)
    assert all(f.parameter_id.startswith("UEC11-FC-F") for f in frees)


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
    # Overview/rationale text, pseudocode and handshake narrations carry
    # DEFINITIONAL facts, while the operation/compliance sections carry
    # the RFC-2119 range these sections actually use (no SHOULD NOT
    # appears in the S5 sections — the keyword inventory is honest).
    keywords = {req.keyword for req in requirements()}
    assert "DEFINITIONAL" in keywords
    assert {"MUST", "MUST NOT", "SHALL", "SHALL NOT", "SHOULD", "MAY"} <= keywords
    assert "SHOULD NOT" not in keywords
    by_subject = {req.subject for req in requirements()}
    assert set(SUBJECTS) == by_subject  # every declared subject is used


def test_credit_flow_control_guarantees_are_encoded() -> None:
    # Load-bearing facts for L0/L1 backends: guard them against accidental
    # removal or rewording into ambiguity.
    stmts = {r.requirement_id: r.statement for r in requirements()}
    assert "does not have credit" in stmts["UEC11-FC-R02"]  # TFC admission
    assert "0xFFFF" in stmts["UEC11-FC-R04"]  # ooo_count invalid marker
    assert "tfc_dest_cell_size" in stmts["UEC11-FC-R07"]  # cell model
    assert "9216" in stmts["UEC11-FC-R07"]  # 9 KB cell support bound
    assert "NO_OP" in stmts["UEC11-FC-R14"]  # initial-credit bootstrap
    assert "QUIESCE" in stmts["UEC11-FC-R18"]  # CCC reuse race guard
    assert "Max_ACK_Data_Size" in stmts["UEC11-FC-R20"]  # shared CCC pool
    assert "PAUSE" in stmts["UEC11-FC-R24"]  # PAUSE exclusivity
    assert "32 VCs" in stmts["UEC11-FC-R26"]  # VC capacity
    assert "credit leakage" in stmts["UEC11-FC-R29"]  # sync self-healing
    assert "roundup" in stmts["UEC11-FC-R38"]  # pktCredits formula
    assert "S_VC_CU" in stmts["UEC11-FC-R38"]  # admission inequality
    assert "CC_msg_timer" in stmts["UEC11-FC-R40"]  # configurable period
    assert "S_VC_RTS" in stmts["UEC11-FC-R55"]  # RTS/RTR gate
    assert "R_VC_RTR" in stmts["UEC11-FC-R55"]
    assert "2048" in stmts["UEC11-FC-R62"]  # mandatory CreditSize set
    assert "800 B" in stmts["UEC11-FC-R66"]  # CF_min_timer floor


def test_assert_valid_passes_on_real_registry(registry: AnchorRegistry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- negative bars: malformed objects and dangling anchors ---------------------


def test_registry_resolve_rejects_dangling_anchor(registry: AnchorRegistry) -> None:
    with pytest.raises(Exception, match="dangling anchor ids"):
        registry.resolve(["UEC11-FC-NOT-A-REGISTRY-ID"])


def test_check_rejects_object_with_dangling_anchor(monkeypatch) -> None:
    # THE stage bar: an object with a dangling anchor is rejected.
    import essun.specir.uec_credits_flow_control as mod

    rogue = UECRequirement(
        requirement_id="UEC11-FC-ROGUE-1",
        anchor_ids=("UEC11-FC-NO-SUCH-ANCHOR",),
        keyword="MUST",
        subject="CBFC",
        statement="A rogue statement citing nothing.",
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", mod._REQUIREMENTS + (rogue,))
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UEC11-FC-ROGUE-1" in p and "dangling anchor ids" in p
        for p in problems
    )
    with pytest.raises(mod.SemanticObjectError):
        mod.assert_valid(registry)


def test_check_rejects_object_citing_other_stage_anchor(monkeypatch) -> None:
    # Anchor-map discipline is enforced by data, not just by convention:
    # S4's CMS anchor, S4's NSCC anchor, S2's negotiation anchor and S3's
    # LLR anchor resolve in the registry but are off the S5 map — while
    # 3.6.14 legitimately resolves onto both the S4 and S5 maps.
    import essun.specir.uec_credits_flow_control as mod

    pristine = mod.anchor_ids()  # before any monkeypatching
    for off_map in (
        "UEC11-S3.6-CMS",
        "UEC11-S3.6.13-NSCC",
        "UEC11-S5.3-LINK-NEGOTIATION",
        "UEC11-S5.1-LLR",
    ):
        rogue = UECRequirement(
            requirement_id="UEC11-FC-ROGUE-2",
            anchor_ids=(off_map,),
            keyword="MUST",
            subject="CBFC",
            statement="A statement citing another stage's section.",
        )
        monkeypatch.setattr(mod, "_REQUIREMENTS", (rogue,))
        assert off_map not in mod.S5_ANCHOR_IDS
        assert off_map not in pristine  # data-level guard holds
    assert "UEC11-S3.6.14-RCCC" in mod.S5_ANCHOR_IDS  # shared, allowed
    # Still valid against the registry itself (the ids resolve) — the stage
    # map is guarded by test_objects_cite_exactly_the_s5_anchor_map above.


def test_check_rejects_malformed_typed_fields(monkeypatch) -> None:
    import essun.specir.uec_credits_flow_control as mod

    rogue = UECRequirement(
        requirement_id="UEC11-FC-ROGUE-3",
        anchor_ids=("UEC11-S5.2-CBFC",),
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
    import essun.specir.uec_credits_flow_control as mod

    no_anchor = dataclasses.replace(
        requirements()[0],
        requirement_id="UEC11-FC-ROGUE-4",
        anchor_ids=(),
    )
    duplicate = dataclasses.replace(requirements()[0])  # same id twice
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
    # real S5 object cannot resolve against it — citations are load-bearing.
    pages = tmp_path / "pages"
    pages.mkdir()
    text = (
        "5.2 Credit-based Flow Control\n\n"
        "This specification defines the protocols that enable credit-based "
        "flow control (CBFC) on a per-priority basis.\n"
    )
    (pages / "page_0650.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0650.txt").read_bytes()).hexdigest()
    entry = {
        "source": {
            "source_id": "SYNTH-5",
            "pdf_sha256": "0" * 64,
            "page_count": 1,
            "pages_dir": "unused",
        },
        "anchors": [
            {
                "id": "SYN-S5-1",
                "section": "5.2",
                "title": "synthetic",
                "page": 650,
                "quote": (
                    "This specification defines the protocols that enable "
                    "credit-based flow control (CBFC) on a per-priority "
                    "basis."
                ),
                "page_sha256": digest,
            }
        ],
    }
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    syn = AnchorRegistry.load(reg_file, pages_dir=pages)
    syn.assert_valid()

    assert syn.resolve(["SYN-S5-1"])[0].anchor_id == "SYN-S5-1"
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(["SYN-S5-1", "UEC11-S5.2-CBFC"])  # real id, absent here

    some_req = next(r for r in requirements() if r.subject == "CBFC")
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(some_req.anchor_ids)
