"""UEC 1.1 profile vs L0 assumption reconciliation (final ladder stage).

The S6 capstone of the UEC semantic profile ladder (S1 anchors, S2-S5
mechanism objects): map the finished profile against the L0/L0.5 analytical
assumption registry ``experiments/vertical_slice/assumptions_l0.yaml`` and
adjudicate every item the earlier stages teed up.

Two object kinds:

- :class:`ReconciliationEntry` — one entry per assumption id in the registry
  file, with a verdict from :data:`VERDICTS`:

  * ``STAYS_FREE`` — the anchored profile (S2-S5 sections) states nothing
    that constrains the assumption; it remains a declared free parameter.
    Entries may still cite supporting context (e.g. topology is a declared
    free design dimension, INC is optional).
  * ``SPEC_ANCHORED`` — an anchored statement now attaches to the
    assumption: it supports the chosen value and/or bounds the assumption's
    validity domain (e.g. the Unified Local 16 KB-1 required message-size
    support vs the workload payload).  The value stays a parameter; the
    anchor must travel with it.
  * ``OUT_OF_SCOPE`` — an anchored statement would bound the parameter, but
    the mechanism it belongs to is scoped away for the profile a scale-up
    slice models (the UET-CC 1-20 us base-RTT envelope vs a Unified Local /
    RODL fabric, which does not require congestion management).
  * ``CONTRADICTED`` — an anchored statement forbids or disagrees with the
    assumption.  Recorded count for this reconciliation: zero — itself a
    finding (the L0 family deliberately models no UEC mechanism, so nothing
    in it can contradict the profile; the profile changes L0's *validity
    domains*, not its numbers).

- :class:`ReconciliationFinding` — adjudications of the items S3/S4/S5 teed
  up (PFC/CBFC vs RODL lossless tension, TFC credit-free retransmission,
  credit-shape unification, the Table 5-27 numeric discrepancies, the
  Tables 3-6/3-7/3-8 profile-matrix cross-checks, and the remaining
  unanchored gaps).

Headline result (also finding UEC11-S6-F08): no numeric value in the L0
registry becomes standard-derived.  The UEC 1.1 profile fixes no link
bandwidth, hop latency or injection rate in the anchored S2-S5 sections
(rates are configuration inputs there), so the assumptions file's note that
placeholders "give way to profile values" resolves at L0 to: nothing to
replace — what the profile contributes are message-level bounds (16 KB-1,
the Payload MTU set) and mechanism-level laws (credit admission, lossless
traffic-class split) that live below L0's abstraction line and bind the
L1+ backends instead.

Citations are machine-checked: requirement ids resolve in the union of the
S2-S5 object sets, free-parameter ids in the union of their FREE sets,
anchor ids in the verified S1 registry, and assumption ids in the YAML
registry itself (:func:`check` / :func:`assert_valid`).  The
Tables 3-6/3-7/3-8 cell alignment (plain-text extraction collapses matrix
columns) was verified ad hoc from the sha256-gated PDF in layout mode —
the same technique S2 used for Tables 3-1/3-5; nothing from that read is
committed except the adjudication text here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .anchors import AnchorRegistry

from . import (
    uec_congestion_management as _s4,
    uec_credits_flow_control as _s5,
    uec_link_transport as _s2,
    uec_reliability_ordering as _s3,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ASSUMPTIONS_PATH = REPO_ROOT / "experiments/vertical_slice/assumptions_l0.yaml"
# Assumptions live in per-model files; the registry is their union.
ASSUMPTIONS_PATHS = (
    ASSUMPTIONS_PATH,
    REPO_ROOT / "experiments/vertical_slice/assumptions_l05.yaml",
)

#: Verdict vocabulary (see module docstring for semantics).
VERDICTS: tuple[str, ...] = (
    "STAYS_FREE",
    "SPEC_ANCHORED",
    "OUT_OF_SCOPE",
    "CONTRADICTED",
)

#: Reconciliation notes are our own adjudications, kept reviewable.
MAX_NOTE_WORDS = 140
#: Findings may run longer (they carry the teed-up adjudications).
MAX_FINDING_WORDS = 240


@dataclass(frozen=True)
class ReconciliationEntry:
    """One L0/L0.5 assumption mapped against the UEC 1.1 profile."""

    assumption_id: str
    verdict: str  # element of VERDICTS
    note: str
    requirement_ids: tuple[str, ...] = ()
    free_parameter_ids: tuple[str, ...] = ()
    anchor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconciliationFinding:
    """One teed-up cross-stage item, adjudicated (S3/S4/S5 -> S6)."""

    finding_id: str
    title: str
    adjudication: str
    requirement_ids: tuple[str, ...] = ()
    free_parameter_ids: tuple[str, ...] = ()
    anchor_ids: tuple[str, ...] = ()


# -- assumption registry (L0 side of the mapping) -----------------------------

def load_assumption_registry(path: Path | str = ASSUMPTIONS_PATH) -> dict:
    """Load assumptions_l0.yaml; minimal shape check (ids present)."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "assumptions_id" not in raw:
        raise ValueError(f"assumption registry {path} lacks assumptions_id")
    entries = raw.get("assumptions")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"assumption registry {path} has no assumptions")
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry:
            raise ValueError(f"assumption registry {path} has a malformed entry")
    return raw


def assumption_ids(path: Path | str | None = None) -> list[str]:
    paths = (path,) if path is not None else ASSUMPTIONS_PATHS
    ids: list[str] = []
    for one in paths:
        ids.extend(entry["id"] for entry in load_assumption_registry(one)["assumptions"])
    return ids


# -- S2-S5 object indexes (spec side of the mapping) ---------------------------

def requirement_index() -> dict[str, object]:
    """All S2-S5 requirement objects by id (dangling-free by construction)."""
    index: dict[str, object] = {}
    for module in (_s2, _s3, _s4, _s5):
        for req in module.requirements():
            index[req.requirement_id] = req
    return index


def free_parameter_index() -> dict[str, object]:
    index: dict[str, object] = {}
    for module in (_s2, _s3, _s4, _s5):
        for param in module.free_parameters():
            index[param.parameter_id] = param
    return index


# -- the reconciliation --------------------------------------------------------

_RECONCILIATION: tuple[ReconciliationEntry, ...] = (
    # == ring (L0) =========================================================
    ReconciliationEntry(
        assumption_id="A-L0-BW",
        verdict="STAYS_FREE",
        free_parameter_ids=("UEC11-CM-F03",),
        note=(
            "No anchored S2-S5 statement fixes a link data rate: UET-CC "
            "treats link speeds as configured inputs (NSCC Plane_BDP "
            "configuration), and the PHY chapter where rates would live is "
            "outside the anchor map. The 64 B/ns value stays a declared "
            "free parameter with no anchor."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0-LAT",
        verdict="OUT_OF_SCOPE",
        requirement_ids=("UEC11-CM-R01", "UEC11-CM-R02"),
        note=(
            "The only anchored fabric-latency statement is the UET-CC "
            "design envelope (base RTT 1-20 us), and UET-CC is a "
            "best-effort scale-out mechanism the Unified Local profile "
            "does not require, so no anchored bound reaches this "
            "parameter. The committed smoke value stays free; its latency "
            "chain 2*(r-1)*200 ns = 2.8 us at r=8 sits inside the envelope "
            "regardless."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0-DIV",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-LT-R38",),
        note=(
            "Divisibility-by-r is an input gate of the analytical "
            "equal-chunk construction, not a transport property; the spec "
            "is silent on collective chunking (in-network collectives are "
            "optional). Message construction is byte-granular (offset = "
            "(N-1) * Payload MTU), so any integral chunk is representable."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0-FD",
        verdict="SPEC_ANCHORED",
        requirement_ids=("UEC11-FC-R30", "UEC11-FC-R23"),
        note=(
            "Supports the assumption within its domain: CBFC is defined "
            "only for a pair of full-duplex MACs on a point-to-point UE "
            "link, so the L0 full-duplex-per-direction bandwidth term "
            "matches the only anchored UE link-layer duplexity statement. "
            "The half-duplex range alternative leaves the CBFC/LLR link "
            "model (and remains a different identity). The spec mandates "
            "duplexity nowhere else in the anchored map."
        ),
    ),
    # == crossbar (L0X) ====================================================
    ReconciliationEntry(
        assumption_id="A-L0X-PORT",
        verdict="STAYS_FREE",
        note=(
            "Port sharing at NIC injection into a non-blocking crossbar is "
            "not a UEC concept: the anchored multipath obligations are "
            "switch-side (spraying across uplink entropy), and nothing in "
            "the S2-S5 map constrains a shared-injection-port model. Both "
            "range values remain modeling identities."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0X-BW",
        verdict="STAYS_FREE",
        free_parameter_ids=("UEC11-CM-F03",),
        note=(
            "Same posture as A-L0-BW: rates are configuration inputs "
            "wherever they appear in the anchored sections; no statement "
            "fixes or bounds a per-rank injection bandwidth."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0X-LAT",
        verdict="OUT_OF_SCOPE",
        requirement_ids=("UEC11-CM-R01", "UEC11-CM-R02"),
        note=(
            "Per-pair variant of A-L0-LAT: the UET-CC 1-20 us base-RTT "
            "envelope would be the only anchored bound and is scoped away "
            "for a Unified Local / RODL fabric (no congestion management "
            "required). Value stays free."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0X-DIV",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-LT-R38",),
        note=(
            "Same as A-L0-DIV: byte-granular message offsets make any "
            "integral chunk representable; equal-chunk divisibility is an "
            "analytical input gate, spec-silent."
        ),
    ),
    # == 2D torus (L0T) ====================================================
    ReconciliationEntry(
        assumption_id="A-L0T-SEQ",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        note=(
            "Collective-schedule decomposition is host/client territory: "
            "the profile matrices require no in-network collective "
            "support (INC is optional, Table 3-8 rows blank), so "
            "sequential per-dimension execution stays a free modeling "
            "identity."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0T-UNIF",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S1.5.3.3-TOPOLOGIES",),
        note=(
            "Topology is an explicitly free design dimension that sets "
            "performance bounds (network diameter, bisection bandwidth) — "
            "anchored support for the analytical design-space program, "
            "not a constraint; per-dimension uniformity itself is "
            "spec-silent and stays free."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0T-SHAPE",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S1.5.3.3-TOPOLOGIES",),
        note=(
            "Grid factorization is a topology design choice; the anchored "
            "topology section declares topology a free dimension. No "
            "constraint attaches."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0T-BW",
        verdict="STAYS_FREE",
        free_parameter_ids=("UEC11-CM-F03",),
        note=(
            "Same posture as A-L0-BW (rates are configuration inputs); "
            "sharing one B across dimensions is a modeling identity, "
            "spec-silent."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0T-LAT",
        verdict="OUT_OF_SCOPE",
        requirement_ids=("UEC11-CM-R01", "UEC11-CM-R02"),
        note=(
            "Same as A-L0-LAT: the only anchored latency bound (UET-CC "
            "base-RTT envelope) is scoped away for Unified Local / RODL."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0T-DIV",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-LT-R38",),
        note=(
            "Same as A-L0-DIV: byte-granular offsets; divisibility is an "
            "analytical input gate."
        ),
    ),
    # == recursive doubling (L0D) ==========================================
    ReconciliationEntry(
        assumption_id="A-L0D-POW2",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        note=(
            "The halving/doubling partner schedule is a client-side "
            "collective algorithm; no profile requires or constrains it "
            "(INC optional). Power-of-two gating stays a modeling "
            "identity."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0D-STEP",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        note=(
            "Serialized single-partner steps are a schedule identity; "
            "spec-silent for the same reason as A-L0D-POW2."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0D-BW",
        verdict="STAYS_FREE",
        free_parameter_ids=("UEC11-CM-F03",),
        note=(
            "Same posture as A-L0-BW / A-L0X-BW: no anchored statement "
            "fixes an injection rate."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0D-LAT",
        verdict="OUT_OF_SCOPE",
        requirement_ids=("UEC11-CM-R01", "UEC11-CM-R02"),
        note=(
            "Same as A-L0-LAT: UET-CC envelope scoped away for the "
            "scale-up profile reading."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0D-DIV",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-LT-R38",),
        note=(
            "Same as A-L0-DIV: divisibility is an analytical input gate; "
            "byte-granular message offsets."
        ),
    ),
    # == phase collectives (L0P) ===========================================
    ReconciliationEntry(
        assumption_id="A-L0P-ALGO",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        note=(
            "Which collective algorithm runs on which fabric is a "
            "client/design choice; the transport is agnostic to it and "
            "the profile matrices mandate no in-network collectives."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0P-MSG",
        verdict="STAYS_FREE",
        note=(
            "The per-rank-input / total-gathered reading of M is a "
            "workload-side convention for phase composition; no anchored "
            "statement speaks to collective semantics at all."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0P-COMP",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        note=(
            "Phase composition (serialized RS then AG, no overlap) is a "
            "schedule identity; the spec neither requires nor forbids "
            "overlap between client-issued operations."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L0P-DIV",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-LT-R38",),
        note=(
            "Same as A-L0-DIV: divisibility is an analytical input gate; "
            "byte-granular message offsets."
        ),
    ),
    # == workloads =========================================================
    ReconciliationEntry(
        assumption_id="A-W1-SIZE",
        verdict="SPEC_ANCHORED",
        requirement_ids=("UEC11-LT-R16", "UEC11-LT-R36", "UEC11-RO-R07"),
        free_parameter_ids=("UEC11-LT-F04", "UEC11-LT-F05"),
        note=(
            "The payload stays workload-derived (free in origin), but its "
            "on-the-wire expression is now anchored-bounded: the Unified "
            "Local profile's required write/read message-size support "
            "tops out at 16 KB-1 (16383 B; implementations may support "
            "less), messages packetize at a Payload MTU of 1024-8192 "
            "(4096 default), and payloads above the profile bound are "
            "expressible only as multiple messages split above SES — "
            "which the spec sanctions. The committed 16 KiB payload "
            "travels as M/r = 2048 B pieces at r=8, inside every bound; "
            "the assumption range's upper region leaves the "
            "Unified-Local-native single-message domain."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-W2-CHUNK",
        verdict="SPEC_ANCHORED",
        requirement_ids=("UEC11-LT-R16", "UEC11-LT-R36", "UEC11-RO-R07"),
        free_parameter_ids=("UEC11-LT-F04", "UEC11-LT-F05"),
        note=(
            "Same anchored packetization context as A-W1-SIZE. Sharp "
            "edge: the chunk value 16384 B sits exactly one byte above "
            "the Unified Local required message-size support (16383 B) — "
            "as a single UET message under Unified Local it leaves the "
            "profile-guaranteed domain, though the W2 construction only "
            "ever puts M/r = 2048 B pieces on the wire at r=8. A "
            "single-message reading of the full chunk needs an SES-level "
            "split (sanctioned) or a chunk value <= 16383."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-W2-DAG",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-RO-R07",),
        note=(
            "The serialized-chain dependency semantics are stronger than "
            "the transport requires: there is no ordering guarantee "
            "across PDCs and splitting/ordering of large transfers above "
            "SES is explicitly the client's job — the chain is such a "
            "client choice, free by spec posture."
        ),
    ),
    # == L0.5 (F1) =========================================================
    ReconciliationEntry(
        assumption_id="A-L05-BW",
        verdict="STAYS_FREE",
        free_parameter_ids=("UEC11-CM-F03",),
        note=(
            "Same posture as A-L0-BW (deliberately shared value and "
            "identity): rates are configuration inputs in the anchored "
            "sections; nothing fixes B."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L05-LAT",
        verdict="OUT_OF_SCOPE",
        requirement_ids=("UEC11-CM-R01", "UEC11-CM-R02"),
        note=(
            "Same as A-L0-LAT (deliberately shared value): UET-CC "
            "envelope scoped away for the scale-up profile reading; the "
            "L0.5 per-transfer latency charge stays free."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L05-INJ",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-CM-R27",),
        free_parameter_ids=("UEC11-CM-F03",),
        note=(
            "No anchored statement names a NIC serialization rate. The "
            "nearest spec statement (line-rate startup with a window "
            "near 1.5 BDP) is a congestion-control behavior, not an "
            "injection-rate bound, and CC is scoped away for Unified "
            "Local; the I parameter stays free, including the I -> "
            "infinity convergence limit."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L05-SER",
        verdict="STAYS_FREE",
        note=(
            "The per-transfer service-time decomposition (serialize + "
            "occupy link + hop latency) is an analytical accounting "
            "identity. The profile's flow-control admission laws (TFC "
            "credit gate, CBFC credit inequalities) are mechanism-level "
            "gates L0.5 deliberately abstracts away; no anchored "
            "statement constrains the decomposition."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L05-CHUNK",
        verdict="STAYS_FREE",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        note=(
            "Pinning c = M/r to the landed equal-chunk construction is a "
            "client-side schedule choice (in-network collectives "
            "optional); neither equal chunking nor a free pipelining "
            "depth is constrained by the anchored sections."
        ),
    ),
    ReconciliationEntry(
        assumption_id="A-L05-DIV",
        verdict="STAYS_FREE",
        requirement_ids=("UEC11-LT-R38",),
        note=(
            "Same as A-L0-DIV: byte-granular offsets; divisibility is an "
            "analytical input gate."
        ),
    ),
)

_FINDINGS: tuple[ReconciliationFinding, ...] = (
    ReconciliationFinding(
        finding_id="UEC11-S6-F01",
        title="PFC/CBFC vs RODL-lossless tension: both legs, adjudicated",
        requirement_ids=(
            "UEC11-RO-R60",
            "UEC11-RO-R51",
            "UEC11-RO-R83",
            "UEC11-CM-R13",
            "UEC11-CM-R02",
            "UEC11-CM-R21",
            "UEC11-CM-R22",
        ),
        free_parameter_ids=("UEC11-RO-F08",),
        adjudication=(
            "Not a spec contradiction — a scoped disjunction. Leg 1 "
            "(S3): RODL lossless operation assumes CBFC or PFC with LLR, "
            "requires responses on a separate traffic class from "
            "requests, and its retransmit-less option (itself a free "
            "choice) makes any packet loss fatal to the PDC; LLR BLOCK "
            "behavior is the link-level lossless mechanism. Leg 2 (S4): "
            "UET-CC assumes PFC and CBFC are not enabled for end-to-end "
            "UET traffic in a best-effort network. The spec reconciles "
            "the legs by scoping them to different fabrics/traffic "
            "classes, and the Unified Local profile is not required to "
            "run UET-CC at all. L0 mapping: no L0/L0.5 assumption "
            "encodes flow control or loss; the L0 identities' "
            "lossless-by-omission stance is valid exactly inside leg 1's "
            "domain — recorded as a validity-domain statement, no "
            "assumption change. Lossless deployments additionally carry "
            "the TC_request/TC_response split and the "
            "unconditional-return-sink law."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F02",
        title="TFC retransmission is credit-free (law for L1+)",
        requirement_ids=("UEC11-FC-R06", "UEC11-FC-R05", "UEC11-CM-R66"),
        adjudication=(
            "Binding constraint on any backend that models TFC: "
            "retransmissions must not consume credit (the destination "
            "buffer was already allocated), while RCCC charges credit "
            "for sends as bandwidth. A TFC-modeling backend that debits "
            "retransmits against credit violates the anchored law — this "
            "binds the planned uet-htsim third backend whenever TFC is "
            "exercised. Vacuous at L0/L0.5, which model no loss and no "
            "retransmission."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F03",
        title="Credit-shape unification: TFC and CBFC share one abstraction",
        requirement_ids=(
            "UEC11-FC-R05",
            "UEC11-FC-R29",
            "UEC11-FC-R43",
            "UEC11-FC-R38",
        ),
        adjudication=(
            "The two receive-buffer-protection mechanisms use the same "
            "credit shape — monotonically increasing cumulative "
            "counters, compared and wrapped — at different layers and "
            "units: TFC end-to-end per CCC (256 B per credit bit, "
            "wrapping with loss tolerance), CBFC hop-by-hop per VC "
            "(cell-granular roundup admission, cyclic counters with "
            "half-range comparison). CBFC credit leakage self-heals "
            "through periodic CC_Update (LostCredits reclaim), so an "
            "L1 abstraction may collapse the shape to 'credits are "
            "never lost' without misrepresenting either mechanism's "
            "steady state; the transient leakage/reclaim is an L2 "
            "detail."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F04",
        title="Table 5-27 numeric discrepancies: provenance note",
        requirement_ids=("UEC11-FC-R63", "UEC11-FC-R64", "UEC11-FC-R31"),
        adjudication=(
            "Three spec-internal numeric discrepancies, verified against "
            "the gated PDF: (a) Table 5-27 (p679) prints the PktOvhd "
            "conformance range as -16 <= PktOvhd <= 12, while section "
            "5.2.10.2 (p678) and the 8-bit two's-complement TLV encoding "
            "give -16..+127 — R63 encodes -16..+127; (b) the p507 worked "
            "example writes a '9126-byte cell' where 9 KB = 9216 is "
            "meant — R07/R08 encode 9216; (c) Table 5-14 gives NumVCs "
            "1-32 while Table 5-27 conformance says 2-32 with a minimum "
            "of one lossless plus one best-effort VC — R31 and R64 "
            "encode both as stated. Recorded here as the repo-level "
            "provenance note; carrying it into the handoff "
            "data/sources.csv row STD-UEC-11 is an owner write (handoff "
            "fence) and is teed up for adjudication."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F05",
        title="CM-R02 cross-check vs Tables 3-6/3-7: confirmed",
        requirement_ids=("UEC11-CM-R02",),
        anchor_ids=("UEC11-S3.3-PROFILES",),
        free_parameter_ids=("UEC11-LT-F10",),
        adjudication=(
            "Layout-mode read of p192 (gated PDF; plain-text extraction "
            "collapses the matrix columns) confirms: Table 3-6 "
            "(best-effort) marks NSCC MUST for AI Base, AI Full and HPC "
            "with Unified Local blank, and RCCC blank for all; Table 3-7 "
            "(lossless) requires nothing for any profile. This matches "
            "CM-R02 (Unified Local and RODL do not require congestion "
            "management); an empty cell means not-required, not "
            "forbidden. Coverage note: S2 encoded Tables 3-1..3-5 but "
            "not the 3.3.7/3.3.8 rows — this cross-check closes that "
            "gap at reconciliation level; lossless CC obligations "
            "surface instead as the TC-split and deadlock rules cited "
            "in F01."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F06",
        title="TFC profile obligations vs Table 3-8: consistent",
        requirement_ids=("UEC11-CM-R04",),
        anchor_ids=("UEC11-S3.3-PROFILES",),
        adjudication=(
            "Layout-mode read of p192 confirms Table 3-8 (INC): Reserved "
            "PDCs and TFC rows are blank for all four profiles and INC "
            "is an optional feature — so TFC is never required by any "
            "profile, matching CM-R04 (TFC optional, point-to-point "
            "channels) and S5's framing. Consequence: the F02 law and "
            "the S5 TFC objects bind implementations only when TFC is "
            "actually deployed."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F07",
        title="Unanchored gaps the reconciliation depends on",
        adjudication=(
            "Open gaps, listed for planner-approved mechanism extensions "
            "per the continuation rules: 3.4.9 memory model (fencing/"
            "ordering of SES operations — S3's flag), 3.5.23 RUDI full "
            "semantics, 5.3.2.2 CBFC TLV wire clauses, 2.4 INC detail, "
            "and the PHY chapter (6.x) where link rates would live. None "
            "of the S6 verdicts leans on these sections; the first two "
            "are the likeliest to matter for an L1 backend."
        ),
    ),
    ReconciliationFinding(
        finding_id="UEC11-S6-F08",
        title="No L0 numeric value becomes standard-derived",
        free_parameter_ids=("UEC11-CM-F03", "UEC11-LT-F04"),
        adjudication=(
            "Answer to the assumptions-registry note 'placeholders give "
            "way to profile values': at L0/L0.5 nothing to replace. The "
            "anchored profile fixes no link bandwidth, hop latency or "
            "injection rate — rates appear only as configured inputs — "
            "so all 32 assumptions keep free values. What the profile "
            "contributes is structural: message-size bounds (16 KB-1 "
            "Unified Local), the Payload MTU set, and mechanism laws "
            "(credit admission, lossless traffic-class split) that live "
            "below L0's abstraction line and bind L1+ backends and the "
            "validity domains of the L0 identities instead."
        ),
    ),
)


def entries() -> tuple[ReconciliationEntry, ...]:
    return _RECONCILIATION


def findings() -> tuple[ReconciliationFinding, ...]:
    return _FINDINGS


def verdict_counts() -> dict[str, int]:
    counts = {verdict: 0 for verdict in VERDICTS}
    for entry in _RECONCILIATION:
        counts[entry.verdict] += 1
    return counts


class ReconciliationError(Exception):
    """Raised when the reconciliation fails an integrity check."""


def check(
    registry: "AnchorRegistry",
    reconciliation: tuple[ReconciliationEntry, ...] | None = None,
    finding_set: tuple[ReconciliationFinding, ...] | None = None,
) -> list[str]:
    """Return all problems (empty = the reconciliation is sound).

    Checks: one entry per assumption id in the YAML registry (exactly —
    no missing, no unknown, no duplicates), verdict vocabulary, note
    length, citation integrity (requirement ids in the S2-S5 union, free
    parameter ids in their union, anchor ids in the verified registry),
    and that non-STAYS_FREE verdicts carry at least one citation.  The
    optional arguments let tests inject synthetic entries/findings for
    negative checks (the defaults are the module data).
    """
    problems: list[str] = []
    yaml_ids = assumption_ids()
    yaml_set = set(yaml_ids)

    checked_entries = _RECONCILIATION if reconciliation is None else reconciliation
    checked_findings = _FINDINGS if finding_set is None else finding_set

    seen: dict[str, int] = {}
    req_index = requirement_index()
    free_index = free_parameter_index()
    anchor_index = registry.by_id()

    for entry in checked_entries:
        seen[entry.assumption_id] = seen.get(entry.assumption_id, 0) + 1
        if entry.assumption_id not in yaml_set:
            problems.append(
                f"{entry.assumption_id}: not an assumption id in "
                f"{ASSUMPTIONS_PATH}"
            )
        if entry.verdict not in VERDICTS:
            problems.append(
                f"{entry.assumption_id}: verdict {entry.verdict!r} not in "
                f"{VERDICTS}"
            )
        words = len(entry.note.split())
        if not (0 < words <= MAX_NOTE_WORDS):
            problems.append(
                f"{entry.assumption_id}: note has {words} words "
                f"(1..{MAX_NOTE_WORDS})"
            )
        dangling_reqs = [
            rid for rid in entry.requirement_ids if rid not in req_index
        ]
        if dangling_reqs:
            problems.append(
                f"{entry.assumption_id}: dangling requirement ids "
                f"{dangling_reqs}"
            )
        dangling_frees = [
            fid for fid in entry.free_parameter_ids if fid not in free_index
        ]
        if dangling_frees:
            problems.append(
                f"{entry.assumption_id}: dangling free-parameter ids "
                f"{dangling_frees}"
            )
        dangling_anchors = [
            aid for aid in entry.anchor_ids if aid not in anchor_index
        ]
        if dangling_anchors:
            problems.append(
                f"{entry.assumption_id}: dangling anchor ids "
                f"{dangling_anchors}"
            )
        if entry.verdict != "STAYS_FREE" and not (
            entry.requirement_ids or entry.free_parameter_ids or entry.anchor_ids
        ):
            problems.append(
                f"{entry.assumption_id}: verdict {entry.verdict} carries no "
                f"citation (only STAYS_FREE may)"
            )

    for aid, count in sorted(seen.items()):
        if count > 1:
            problems.append(f"duplicate reconciliation entry {aid} ({count})")
    missing = [aid for aid in yaml_ids if aid not in seen]
    if missing:
        problems.append(f"assumptions with no reconciliation entry: {missing}")

    fseen: dict[str, int] = {}
    for finding in checked_findings:
        fseen[finding.finding_id] = fseen.get(finding.finding_id, 0) + 1
        if not finding.finding_id.startswith("UEC11-S6-F"):
            problems.append(f"finding id {finding.finding_id!r} lacks prefix")
        if not finding.title.strip():
            problems.append(f"{finding.finding_id}: empty title")
        words = len(finding.adjudication.split())
        if not (0 < words <= MAX_FINDING_WORDS):
            problems.append(
                f"{finding.finding_id}: adjudication has {words} words "
                f"(1..{MAX_FINDING_WORDS})"
            )
        dangling_reqs = [
            rid for rid in finding.requirement_ids if rid not in req_index
        ]
        if dangling_reqs:
            problems.append(
                f"{finding.finding_id}: dangling requirement ids "
                f"{dangling_reqs}"
            )
        dangling_frees = [
            fid for fid in finding.free_parameter_ids if fid not in free_index
        ]
        if dangling_frees:
            problems.append(
                f"{finding.finding_id}: dangling free-parameter ids "
                f"{dangling_frees}"
            )
        dangling_anchors = [
            aid for aid in finding.anchor_ids if aid not in anchor_index
        ]
        if dangling_anchors:
            problems.append(
                f"{finding.finding_id}: dangling anchor ids "
                f"{dangling_anchors}"
            )
    for fid, count in sorted(fseen.items()):
        if count > 1:
            problems.append(f"duplicate finding id {fid} ({count})")

    return problems


def assert_valid(
    registry: "AnchorRegistry",
    reconciliation: tuple[ReconciliationEntry, ...] | None = None,
    finding_set: tuple[ReconciliationFinding, ...] | None = None,
) -> None:
    problems = check(registry, reconciliation, finding_set)
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise ReconciliationError(
            f"UEC/L0 reconciliation failed integrity: {detail}{more}"
        )
