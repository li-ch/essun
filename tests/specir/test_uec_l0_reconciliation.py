"""S6 reconciliation tests: UEC 1.1 profile vs the L0 assumption registry.

Bars from the stage prompt: the profile is mapped against
experiments/vertical_slice/assumptions_l0.yaml — every assumption id gets
exactly one verdict, citations resolve (S2-S5 requirement/free-parameter
ids and S1 registry anchors), the teed-up S4/S5 items are adjudicated as
findings, and negatives (dangling citations, unknown/duplicate assumption
ids, uncited non-free verdicts, bad vocabulary) are rejected.
"""

from __future__ import annotations

import pytest

from essun.specir.anchors import AnchorRegistry
from essun.specir.uec_l0_reconciliation import (
    MAX_FINDING_WORDS,
    MAX_NOTE_WORDS,
    VERDICTS,
    ReconciliationEntry,
    ReconciliationError,
    ReconciliationFinding,
    assumption_ids,
    assert_valid,
    check,
    entries,
    findings,
    free_parameter_index,
    requirement_index,
    verdict_counts,
)


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()  # reconciliation is checked against a verified registry
    return reg


# -- positive bars -------------------------------------------------------------


def test_reconciliation_is_sound(registry: AnchorRegistry) -> None:
    assert check(registry) == []
    assert_valid(registry)  # does not raise


def test_every_assumption_is_reconciled_exactly_once() -> None:
    # Completeness in both directions against the live YAML registry
    # (32 entries incl. tonight's F1 A-L05-* additions).
    yaml_ids = assumption_ids()
    entry_ids = [entry.assumption_id for entry in entries()]
    assert len(entry_ids) == len(yaml_ids)
    assert sorted(entry_ids) == sorted(yaml_ids)
    assert len(entry_ids) == len(set(entry_ids))  # no duplicates
    assert "A-L05-INJ" in entry_ids  # F1's newest entry is covered too


def test_all_citations_resolve(registry: AnchorRegistry) -> None:
    req_index = requirement_index()
    free_index = free_parameter_index()
    anchor_index = registry.by_id()
    for entry in entries() + findings():
        assert all(rid in req_index for rid in entry.requirement_ids), entry
        assert all(fid in free_index for fid in entry.free_parameter_ids), entry
        assert all(aid in anchor_index for aid in entry.anchor_ids), entry


def test_verdict_distribution_is_the_recorded_finding() -> None:
    # The reconciliation's recorded outcome (also finding UEC11-S6-F08):
    # 24 stay free, 3 gain anchors, 5 have anchored-but-scoped-away
    # bounds, and ZERO are contradicted — L0 models no UEC mechanism,
    # so nothing in it can contradict the profile.
    counts = verdict_counts()
    assert counts == {
        "STAYS_FREE": 24,
        "SPEC_ANCHORED": 3,
        "OUT_OF_SCOPE": 5,
        "CONTRADICTED": 0,
    }
    assert sum(counts.values()) == len(entries())


def test_load_bearing_verdicts_are_pinned() -> None:
    # Goldens of the mapping itself: the verdicts the teed-up items hang on.
    by_id = {entry.assumption_id: entry for entry in entries()}

    workload = by_id["A-W1-SIZE"]
    assert workload.verdict == "SPEC_ANCHORED"
    assert "UEC11-LT-R16" in workload.requirement_ids  # 16 KB-1 bound

    chunk = by_id["A-W2-CHUNK"]
    assert chunk.verdict == "SPEC_ANCHORED"
    assert "16383" in chunk.note  # the one-byte-over edge is spelled out

    duplexity = by_id["A-L0-FD"]
    assert duplexity.verdict == "SPEC_ANCHORED"
    assert "UEC11-FC-R30" in duplexity.requirement_ids  # full-duplex support

    for latency_id in ("A-L0-LAT", "A-L0X-LAT", "A-L0T-LAT",
                       "A-L0D-LAT", "A-L05-LAT"):
        entry = by_id[latency_id]
        assert entry.verdict == "OUT_OF_SCOPE", latency_id
        assert {"UEC11-CM-R01", "UEC11-CM-R02"} <= set(entry.requirement_ids)

    injection = by_id["A-L05-INJ"]
    assert injection.verdict == "STAYS_FREE"
    assert "UEC11-CM-R27" in injection.requirement_ids  # context, not bound

    dag = by_id["A-W2-DAG"]
    assert dag.verdict == "STAYS_FREE"
    assert "UEC11-RO-R07" in dag.requirement_ids  # client-side ordering

    for free_id in ("A-L0-BW", "A-L05-BW", "A-L0X-BW", "A-L0T-BW", "A-L0D-BW"):
        assert by_id[free_id].verdict == "STAYS_FREE", free_id


def test_notes_are_crisp_and_findings_are_bounded() -> None:
    for entry in entries():
        assert 0 < len(entry.note.split()) <= MAX_NOTE_WORDS
        assert entry.verdict in VERDICTS
    for finding in findings():
        assert finding.finding_id.startswith("UEC11-S6-F")
        assert 0 < len(finding.adjudication.split()) <= MAX_FINDING_WORDS


def test_teed_up_items_are_adjudicated(registry: AnchorRegistry) -> None:
    # Every item S3/S4/S5 teed for S6 exists, with its load-bearing
    # citations on both sides of each tension.
    by_id = {finding.finding_id: finding for finding in findings()}

    tension = by_id["UEC11-S6-F01"]  # PFC/CBFC vs RODL lossless, both legs
    assert "UEC11-RO-R60" in tension.requirement_ids  # leg 1: RODL lossless
    assert "UEC11-CM-R13" in tension.requirement_ids  # leg 2: SHOULD NOT
    assert "UEC11-CM-R02" in tension.requirement_ids  # the scoping fact

    tfc_law = by_id["UEC11-S6-F02"]  # retransmit is credit-free
    assert "UEC11-FC-R06" in tfc_law.requirement_ids
    assert "uet-htsim" in tfc_law.adjudication  # binds the third backend

    shape = by_id["UEC11-S6-F03"]  # credit-shape unification
    assert {"UEC11-FC-R05", "UEC11-FC-R43"} <= set(shape.requirement_ids)

    typo = by_id["UEC11-S6-F04"]  # Table 5-27 PktOvhd + neighbors
    assert "12" in typo.adjudication and "127" in typo.adjudication
    assert "9216" in typo.adjudication
    assert "sources.csv" in typo.adjudication  # owner-write tee is explicit

    cross_check = by_id["UEC11-S6-F05"]  # CM-R02 vs Tables 3-6/3-7
    assert "UEC11-S3.3-PROFILES" in cross_check.anchor_ids

    tfc_matrix = by_id["UEC11-S6-F06"]  # TFC vs Table 3-8
    assert "UEC11-S3.3-PROFILES" in tfc_matrix.anchor_ids
    assert "UEC11-CM-R04" in tfc_matrix.requirement_ids

    assert "3.4.9" in by_id["UEC11-S6-F07"].adjudication  # unanchored gaps
    headline = by_id["UEC11-S6-F08"]  # no L0 number becomes standard-derived
    assert "nothing to replace" in headline.adjudication


# -- negatives -----------------------------------------------------------------


def _entry(**overrides) -> ReconciliationEntry:
    base = dict(
        assumption_id="A-L0-BW",
        verdict="STAYS_FREE",
        note="A valid synthetic note for negative testing.",
    )
    base.update(overrides)
    return ReconciliationEntry(**base)


def test_check_rejects_dangling_requirement_citation(registry) -> None:
    rogue = (_entry(requirement_ids=("UEC11-S6-NO-SUCH-R",)),)
    problems = check(registry, reconciliation=rogue + entries()[1:])
    assert any("dangling requirement ids" in p for p in problems)
    with pytest.raises(ReconciliationError):
        assert_valid(registry, reconciliation=rogue + entries()[1:])


def test_check_rejects_dangling_anchor_citation(registry) -> None:
    rogue = _entry(anchor_ids=("UEC11-S6-NO-SUCH-ANCHOR",))
    problems = check(
        registry, reconciliation=(rogue,) + entries()[1:]
    )
    assert any("dangling anchor ids" in p for p in problems)


def test_check_rejects_dangling_free_parameter_citation(registry) -> None:
    rogue = _entry(free_parameter_ids=("UEC11-S6-NO-SUCH-F",))
    problems = check(registry, reconciliation=(rogue,) + entries()[1:])
    assert any("dangling free-parameter ids" in p for p in problems)


def test_check_rejects_unknown_assumption_id(registry) -> None:
    rogue = _entry(assumption_id="A-NO-SUCH-ASSUMPTION")
    problems = check(registry, reconciliation=(rogue,) + entries())
    assert any("not an assumption id" in p for p in problems)


def test_check_rejects_missing_and_duplicate_assumption_ids(registry) -> None:
    # dropping one entry -> incompleteness; doubling one -> duplicate
    dropped = check(registry, reconciliation=entries()[:-1])
    assert any("no reconciliation entry" in p for p in dropped)
    doubled = check(registry, reconciliation=entries() + (entries()[0],))
    assert any("duplicate reconciliation entry" in p for p in doubled)


def test_check_rejects_uncited_non_free_verdict(registry) -> None:
    rogue = _entry(verdict="SPEC_ANCHORED", requirement_ids=())
    problems = check(registry, reconciliation=(rogue,) + entries()[1:])
    assert any("carries no citation" in p for p in problems)


def test_check_rejects_bad_verdict_vocabulary(registry) -> None:
    rogue = _entry(verdict="SPEC_ALIGNMENT")
    problems = check(registry, reconciliation=(rogue,) + entries()[1:])
    assert any("verdict" in p and "not in" in p for p in problems)


def test_check_rejects_malformed_notes(registry) -> None:
    empty = _entry(note="   ")
    problems = check(registry, reconciliation=(empty,) + entries()[1:])
    assert any("note has 0 words" in p for p in problems)
    long_note = _entry(note=" ".join(["word"] * (MAX_NOTE_WORDS + 1)))
    problems = check(registry, reconciliation=(long_note,) + entries()[1:])
    assert any(f"note has {MAX_NOTE_WORDS + 1} words" in p for p in problems)


def test_check_rejects_malformed_finding(registry) -> None:
    good = findings()[0]
    bad_id = ReconciliationFinding(
        finding_id="UEC11-S6-F99",
        title=good.title,
        adjudication=good.adjudication,
        requirement_ids=good.requirement_ids,
    )
    dangling = ReconciliationFinding(
        finding_id="UEC11-S6-F98",
        title="t",
        adjudication="t",
        requirement_ids=("UEC11-RO-NO-SUCH",),
    )
    problems = check(registry, finding_set=(bad_id, dangling))
    assert any("dangling requirement ids" in p for p in problems)
    with pytest.raises(ReconciliationError):
        assert_valid(registry, finding_set=(bad_id, dangling))
