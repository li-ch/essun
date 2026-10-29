"""S2b semantic-object tests: UEC 1.1 F07 mechanism-list extension (T010/T011).

Stage S2b is dispatched under the ladder's pre-authorized continuation rule
(mechanism-list extension only): the five mechanisms S6's finding F07 teed
up — 3.4.9 memory model, 3.5.23 RUDI, 5.3.2.2 CBFC TLV wire clauses, 2.4 INC
detail, 6.1.x PHY rates.

Bars from the stage prompt (S2-S5 pattern): every object's anchors resolve in
the registry, and a negative test rejects an object with a dangling anchor.
Additional stage-specific bars enforced here: objects cite exactly the S2b
anchor map, every S2b anchor is actually used, ids are unique across the
whole ladder (no collision with S2-S5/S6 object ids), typed fields come from
the declared vocabularies, and the load-bearing facts of each of the five
mechanisms are present.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_f07_mechanisms import (
    MAX_STATEMENT_WORDS,
    NORMATIVE_KEYWORDS,
    S2B_ANCHOR_IDS,
    SUBJECTS,
    UECRequirement,
    all_objects,
    anchor_ids,
    assert_valid,
    check_against_registry,
    free_parameters,
    requirements,
)

#: The 14 anchors this stage added to the registry (S1 build script), with
#: their sections — the registry-side half of the S2b deliverable.
NEW_S2B_ANCHORS: tuple[tuple[str, str], ...] = (
    ("UEC11-S2.4.1-INC-ASSUMPTIONS", "2.4.1"),
    ("UEC11-S2.4.3-INC-OPERATIONS", "2.4.3"),
    ("UEC11-S2.4.6-INC-ORDERING-MODES", "2.4.6"),
    ("UEC11-S2.4.10-INC-SWITCH-CAPS", "2.4.10"),
    ("UEC11-S2.4.11-INC-TRANSPORT", "2.4.11"),
    ("UEC11-S3.4.9-MEMORY-MODEL", "3.4.9"),
    ("UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY", "3.4.9.5"),
    ("UEC11-S3.5.23-RUDI", "3.5.23"),
    ("UEC11-S5.3.2.2-CBFC-TLV", "5.3.2.2"),
    ("UEC11-S5.3.2.2-CBFC-TLV-HANDSHAKE", "5.3.2.2"),
    ("UEC11-S6.1.1.1-PHY-MEDIA-100G", "6.1.1.1"),
    ("UEC11-S6.1.1.2-PHY-RATES-100G", "6.1.1.2"),
    ("UEC11-S6.1.2.1-PHY-MEDIA-200G", "6.1.2.1"),
    ("UEC11-S6.1.2.2-PHY-RATES-200G", "6.1.2.2"),
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


def test_new_s2b_anchors_are_registered(registry: AnchorRegistry) -> None:
    # The registry extension landed: each of the 14 new anchors exists with
    # the section it claims (F07's five mechanisms are anchorable).
    by_id = registry.by_id()
    for anchor_id, section in NEW_S2B_ANCHORS:
        assert anchor_id in by_id, anchor_id
        assert by_id[anchor_id].section == section, anchor_id
    assert len(registry.anchors) >= 80


def test_objects_cite_exactly_the_s2b_anchor_map() -> None:
    # Stage discipline: S2b cites exactly its mechanism-to-anchor map (the
    # 14 new anchors plus the pre-existing 2.4 and 6.1 entry anchors); every
    # S2b anchor must back at least one object.
    used = anchor_ids()
    assert used <= S2B_ANCHOR_IDS
    assert used == S2B_ANCHOR_IDS


def test_stage_objects_present_and_unique() -> None:
    reqs = requirements()
    frees = free_parameters()
    assert len(reqs) >= 80
    assert len(frees) >= 14
    ids = [o.requirement_id for o in reqs] + [o.parameter_id for o in frees]
    assert len(ids) == len(set(ids))
    assert all(r.requirement_id.startswith("UEC11-F07-R") for r in reqs)
    assert all(f.parameter_id.startswith("UEC11-F07-F") for f in frees)


def test_object_ids_do_not_collide_with_other_stages() -> None:
    # Ladder-wide uniqueness: S2-S5/S6 object ids live in other modules; the
    # UEC11-F07-* namespace must be disjoint from all of them.
    from essun.specir import (
        uec_congestion_management,
        uec_credits_flow_control,
        uec_link_transport,
        uec_reliability_ordering,
    )

    def ids_of(module) -> set[str]:
        return {
            getattr(o, "requirement_id", None) or getattr(o, "parameter_id", None)
            for o in module.all_objects()
        }

    mine = {
        getattr(o, "requirement_id", None) or getattr(o, "parameter_id", None)
        for o in all_objects()
    }
    others = set()
    for module in (
        uec_link_transport,
        uec_reliability_ordering,
        uec_congestion_management,
        uec_credits_flow_control,
    ):
        others |= ids_of(module)
    assert not (mine & others)


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
    # The RUDI service list, CBFC TLV field semantics tables, INC overview
    # and PHY rate tables carry no RFC-2119 keywords (DEFINITIONAL), while
    # 3.4.9 (memory model), the CBFC TLV handshake, the INC assumptions and
    # 6.1 compliance carry real keywords.
    keywords = {req.keyword for req in requirements()}
    assert "DEFINITIONAL" in keywords
    assert {"MUST", "MUST NOT", "SHALL", "SHALL NOT", "SHOULD", "MAY"} <= keywords
    assert {req.subject for req in requirements()} == set(SUBJECTS)


def test_five_f07_mechanisms_are_encoded(registry: AnchorRegistry) -> None:
    # Load-bearing facts per mechanism, guarded against accidental removal
    # or rewording into ambiguity (statement text checked, anchor section
    # checked).
    stmts = {r.requirement_id: r.statement for r in requirements()}
    by_id = registry.by_id()
    # memory model (3.4.9 / 3.4.9.5)
    assert by_id["UEC11-S3.4.9-MEMORY-MODEL"].section == "3.4.9"
    assert "message processing ordering" in stmts["UEC11-F07-R04"]  # ROD flows
    assert "exactly once" in stmts["UEC11-F07-R18"]  # idempotency
    assert "guarantees idempotency" in stmts["UEC11-F07-R22"]  # Unified Local
    # RUDI (3.5.23)
    assert "idempotent operations" in stmts["UEC11-F07-R26"]
    assert "RTO timer per packet" in stmts["UEC11-F07-R34"]
    assert "never NACK'd" in stmts["UEC11-F07-R33"]
    # CBFC TLV (5.3.2.2)
    assert "shall not set S_VC_RTS" in stmts["UEC11-F07-R39"]
    assert "shall not use CBFC for a VC unless" in stmts["UEC11-F07-R40"]
    assert "212 bytes" in stmts["UEC11-F07-R41"]  # max TLV length
    # INC (2.4)
    assert "lossless fabric" in stmts["UEC11-F07-R60"]
    assert "4096" in stmts["UEC11-F07-R66"]  # CSN space ceiling
    assert "must support reserved PDCs" in stmts["UEC11-F07-R83"]
    # PHY rates (6.1.x)
    assert "shall conform to one of the PHY-type specifications" in stmts[
        "UEC11-F07-R86"
    ]
    assert "1.6TBASE-R" in stmts["UEC11-F07-R89"]  # top of the rate ladder


def test_assert_valid_passes_on_real_registry(registry: AnchorRegistry) -> None:
    assert check_against_registry(registry) == []
    assert_valid(registry)  # must not raise


# -- negative bars: malformed objects and dangling anchors ---------------------


def test_registry_resolve_rejects_dangling_anchor(registry: AnchorRegistry) -> None:
    with pytest.raises(Exception, match="dangling anchor ids"):
        registry.resolve(["UEC11-F07-NOT-A-REGISTRY-ID"])


def test_check_rejects_object_with_dangling_anchor(monkeypatch) -> None:
    # THE stage bar: an object with a dangling anchor is rejected.
    import essun.specir.uec_f07_mechanisms as mod

    rogue = UECRequirement(
        requirement_id="UEC11-F07-ROGUE-1",
        anchor_ids=("UEC11-F07-NO-SUCH-ANCHOR",),
        keyword="MUST",
        subject="RUDI",
        statement="A rogue statement citing nothing.",
    )
    monkeypatch.setattr(mod, "_REQUIREMENTS", mod._REQUIREMENTS + (rogue,))
    registry = AnchorRegistry.load()
    problems = mod.check_against_registry(registry)
    assert any(
        "UEC11-F07-ROGUE-1" in p and "dangling anchor ids" in p
        for p in problems
    )
    with pytest.raises(mod.SemanticObjectError):
        mod.assert_valid(registry)


def test_check_rejects_object_citing_other_stage_anchor() -> None:
    # Anchor-map discipline: an S3-section anchor (RODL) is off the S2b map
    # even though the id resolves in the registry; the stage map itself is
    # guarded by test_objects_cite_exactly_the_s2b_anchor_map above.
    assert "UEC11-S3.5.22-RODL" not in S2B_ANCHOR_IDS


def test_check_rejects_malformed_typed_fields(monkeypatch) -> None:
    import essun.specir.uec_f07_mechanisms as mod

    rogue = UECRequirement(
        requirement_id="UEC11-F07-ROGUE-3",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
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
    import essun.specir.uec_f07_mechanisms as mod

    no_anchor = dataclasses.replace(
        requirements()[0],
        requirement_id="UEC11-F07-ROGUE-4",
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
    # real S2b object cannot resolve against it — citations are load-bearing.
    pages = tmp_path / "pages"
    pages.mkdir()
    text = "3.5.23 RUDI\n\nRUDI provides reliable delivery for idempotent operations.\n"
    (pages / "page_0424.txt").write_text(text, encoding="utf-8")
    digest = hashlib.sha256((pages / "page_0424.txt").read_bytes()).hexdigest()
    entry = {
        "source": {
            "source_id": "SYNTH-S2B",
            "pdf_sha256": "0" * 64,
            "page_count": 1,
            "pages_dir": "unused",
        },
        "anchors": [
            {
                "id": "SYN-S2B-1",
                "section": "3.5.23",
                "title": "synthetic",
                "page": 424,
                "quote": "RUDI provides reliable delivery for idempotent operations.",
                "page_sha256": digest,
            }
        ],
    }
    reg_file = tmp_path / "registry.yaml"
    reg_file.write_text(yaml.safe_dump(entry), encoding="utf-8")
    syn = AnchorRegistry.load(reg_file, pages_dir=pages)
    syn.assert_valid()

    assert syn.resolve(["SYN-S2B-1"])[0].anchor_id == "SYN-S2B-1"
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(["SYN-S2B-1", "UEC11-S3.5.23-RUDI"])  # real id, absent here

    some_req = next(r for r in requirements() if r.subject == "RUDI")
    with pytest.raises(Exception, match="dangling anchor ids"):
        syn.resolve(some_req.anchor_ids)
