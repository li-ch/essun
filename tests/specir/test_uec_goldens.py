"""S6 golden tests: anchor round-trips + extraction spot-checks (T010/T011).

Bars from the stage prompt: anchor round-trips, and a small extraction
spot-check whose expected quotes are spelled *in this test* — so drift in
the committed extraction, in the anchor registry, or in the section/page
bookkeeping is caught independently of the registry's own self-checks.

The spelled-out quotes are the same <= 30-word citation snippets the S1
registry carries (license-gate scope: short attributed quotes only, the
PDF itself never enters git).  One golden per load-bearing mechanism: the
normative profile core (S2), SES semantic concepts (S2), RODL (S3), LLR
(S3/S5 tension leg), CMS (S4), RCCC (S4/S5 shared anchor), TFC (S5), CBFC
overview and compliance (S5), and the free-dimension topology anchor the
reconciliation cites directly.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest
import yaml

from essun.specir import (
    uec_congestion_management,
    uec_credits_flow_control,
    uec_l0_reconciliation,
    uec_link_transport,
    uec_reliability_ordering,
)
from essun.specir.anchors import (
    Anchor,
    AnchorRegistry,
    DEFAULT_REGISTRY_PATH,
    normalize_whitespace,
)


@pytest.fixture(scope="module")
def registry() -> AnchorRegistry:
    reg = AnchorRegistry.load()
    reg.assert_valid()  # goldens are checked against a verified registry
    return reg


# Golden triplets spelled in the test: (section, page, expected quote).
# Verified against the sha256-gated UEC 1.1 extraction; quotes are the
# registry's own <= 30-word citation snippets (STD-UEC-11, PUBLIC_READ).
GOLDEN_ANCHORS: tuple[tuple[str, int, str, str], ...] = (
    (
        "3.3",
        187,
        "UEC11-S3.3-PROFILES",
        "PDS is responsible for delivering packets from sender to receiver.",
    ),
    (
        "3.4.2",
        194,
        "UEC11-S3.4.2-SEMANTIC-CONCEPTS",
        "This section articulates the semantics provided by the UET to support AI and HPC applications.",
    ),
    (
        "3.5.22",
        420,
        "UEC11-S3.5.22-RODL",
        "RODL is a variation of ROD that is optimized for scale-up networks.",
    ),
    (
        "5.1",
        631,
        "UEC11-S5.1-LLR",
        "The impact of delay on efficiency becomes more significant as network link speeds, utilization, and scale increase.",
    ),
    (
        "3.6",
        439,
        "UEC11-S3.6-CMS",
        "UET defines an end-to-end congestion management solution, UET-CC (UET Congestion Control), "
        "for packet buffer congestion in a best-effort (sometimes called ”lossy”) Ethernet network.",
    ),
    (
        "3.6.14",
        491,
        "UEC11-S3.6.14-RCCC",
        "The UET receiver-credit congestion control (RCCC) service is derived from EQDS[11].",
    ),
    (
        "3.6.15",
        505,
        "UEC11-S3.6.15-TFC",
        "A source MUST NOT transmit a packet if it does not have credit",
    ),
    (
        "5.2.4",
        652,
        "UEC11-S5.2.4-CBFC-OVERVIEW",
        "The sender keeps track of the available buffer space at the receiver in units of credits",
    ),
    (
        "5.2.10",
        678,
        "UEC11-S5.2.10-CBFC-COMPLIANCE",
        "The receiver’s input buffer is typically divided into cells, and the cell size (in bytes) "
        "is the input buffer allocation unit.",
    ),
    (
        "1.5.3.3",
        67,
        "UEC11-S1.5.3.3-TOPOLOGIES",
        "Topology is a critical part of an AI and HPC fabric as it sets the performance bounds "
        "by establishing the network diameter and bisection bandwidth.",
    ),
)


# -- anchor round-trips --------------------------------------------------------


def test_anchor_entry_roundtrips_through_dataclass() -> None:
    # YAML entry -> Anchor dataclass -> entry-shaped dict is lossless for
    # every registry entry (the registry is the round-trip's oracle).
    raw = yaml.safe_load(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    for entry in raw["anchors"]:
        anchor = Anchor(
            anchor_id=entry["id"],
            section=str(entry["section"]),
            page=int(entry["page"]),
            quote=entry["quote"],
            page_sha256=entry["page_sha256"],
            title=entry.get("title", ""),
        )
        rebuilt = {
            "id": anchor.anchor_id,
            "section": anchor.section,
            "title": anchor.title,
            "page": anchor.page,
            "quote": anchor.quote,
            "page_sha256": anchor.page_sha256,
        }
        assert rebuilt == entry, entry["id"]


def test_registry_yaml_roundtrip(tmp_path) -> None:
    # Whole-registry serialization round-trip: dump source + anchors to a
    # fresh YAML file, reload through AnchorRegistry, and require the
    # source block and every anchor to survive unchanged.
    reg = AnchorRegistry.load()
    dumped = {
        "source": reg.source,
        "anchors": [
            {
                "id": a.anchor_id,
                "section": a.section,
                "title": a.title,
                "page": a.page,
                "quote": a.quote,
                "page_sha256": a.page_sha256,
            }
            for a in reg.anchors
        ],
    }
    path = tmp_path / "anchor_registry_roundtrip.yaml"
    path.write_text(yaml.safe_dump(dumped, allow_unicode=True), encoding="utf-8")
    reloaded = AnchorRegistry.load(path)
    assert reloaded.source == reg.source
    assert reloaded.anchors == reg.anchors
    assert reloaded.verify() == []  # still fully verifiable after the trip


def test_cited_anchor_ids_resolve_roundtrip(registry: AnchorRegistry) -> None:
    # Every anchor id cited anywhere in the ladder (S2-S5 objects, S6
    # reconciliation entries and findings) resolves to itself through the
    # registry — the citation spine of the whole profile.  (Requirement
    # citations resolve through their owning modules' objects, whose own
    # anchor citations are thereby in this set too.)
    by_id = registry.by_id()
    modules = (
        uec_link_transport,
        uec_reliability_ordering,
        uec_congestion_management,
        uec_credits_flow_control,
    )
    cited: set[str] = set()
    for module in modules:
        for obj in module.all_objects():
            cited.update(obj.anchor_ids)
    for entry in uec_l0_reconciliation.entries():
        cited.update(entry.anchor_ids)
    for finding in uec_l0_reconciliation.findings():
        cited.update(finding.anchor_ids)
    assert cited, "the ladder must cite anchors"
    for anchor_id in sorted(cited):
        resolved = registry.resolve((anchor_id,))
        assert len(resolved) == 1
        assert resolved[0].anchor_id == anchor_id == by_id[anchor_id].anchor_id


# -- extraction spot-checks (expected quotes spelled in this test) -------------


@pytest.mark.parametrize(
    "section,page,anchor_id,expected_quote",
    GOLDEN_ANCHORS,
    ids=[g[2] for g in GOLDEN_ANCHORS],
)
def test_golden_extraction_spot_check(
    registry: AnchorRegistry, section: str, page: int, anchor_id: str,
    expected_quote: str,
) -> None:
    # Independent of the registry's self-check: the expected quote is
    # spelled here and (a) must appear in the committed extracted page,
    # (b) must equal the registry quote recorded for that section+page,
    # and (c) the page bytes must still hash to the recorded sha256.
    page_path = registry.page_path(page)
    assert page_path.is_file(), page_path
    page_text = page_path.read_text(encoding="utf-8")
    assert normalize_whitespace(expected_quote) in normalize_whitespace(page_text)

    by_id = registry.by_id()
    assert anchor_id in by_id
    anchor = by_id[anchor_id]
    assert anchor.section == section
    assert anchor.page == page
    assert anchor.quote == expected_quote  # registry cannot drift from golden
    assert len(expected_quote.split()) <= 30  # license-gate scope holds

    digest = hashlib.sha256(page_path.read_bytes()).hexdigest()
    assert digest == anchor.page_sha256
    assert dataclasses.is_dataclass(anchor)
