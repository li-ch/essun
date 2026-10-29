"""UEC 1.1 F07 mechanism-list extension: stage S2b semantic objects (T010/T011).

Dispatched under the ladder's pre-authorized continuation rule ("If extraction
reveals a mechanism not in S2-S5 ... the planner MAY dispatch it as S2b/S3b
... citing this rule — mechanism list extension is pre-authorized, nothing
else").  Stage S6's finding F07 (``uec_l0_reconciliation``) teed exactly these
uncovered mechanisms, and this stage extracts all five:

- the 3.4.9 UE transport **memory model** (ordering, consistency/atomicity,
  global observability, idempotency, the Unified Local variant 3.4.9.5, and
  synchronized operations 3.4.9.6) — S3's flagged gap;
- **RUDI** full semantics (3.5.23: idempotent per-packet reliable delivery,
  pkt_id rules, per-packet RTO, no UET congestion control);
- the **CBFC TLV wire clauses** (5.3.2.2: the LLDP negotiation state machine
  and every S_/R_ field's normative constraints);
- **INC detail** (2.4: assumptions, operations, datatypes/operators, ordering
  and rounding modes, switch capabilities, inc_info transport encoding);
- the **PHY rates** (6.1.1/6.1.2: in-scope Ethernet PHY rate/type families,
  media, and attachment-unit interfaces per lane-signaling generation).

Object model, vocabularies and validation follow the S2-S5 pattern
(:mod:`essun.specir.uec_link_transport`): every object is a mapping
``requirement id -> anchor ids -> typed statement`` (provenance rule),
dataclasses/:data:`NORMATIVE_KEYWORDS`/:data:`MAX_STATEMENT_WORDS` are
imported from S2 as the single source of truth, keywords are typed exactly as
the spec text carries them, and ``DEFINITIONAL`` marks load-bearing facts
stated without an RFC-2119 keyword (e.g. the RUDI service-list items and the
PHY "in scope for UE" rate tables).  Free parameters are always
``domain="FREE"``.

Statements are paraphrases in our own words (S0 license gate: verbatim spec
text in git remains only the S1 registry's <= 30-word quotes; the gate stays
enforced — sha256-pinned extraction, PUBLIC_READ source only).  Anchors are
section-scoped per the S2 method notes: an anchor pins its section's entry
page/hash; statements may be drawn from the section's full page span (e.g.
the 3.4.9 anchor p. 283 also grounds 3.4.9.1-3.4.9.4 on pp. 283-285; the
2.4.11 anchor p. 162 also grounds 2.4.11.2-2.4.11.3 on p. 163).  Dangling
anchors are hard errors (:func:`check_against_registry` /
:func:`assert_valid`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .uec_link_transport import (
    MAX_STATEMENT_WORDS,
    NORMATIVE_KEYWORDS,
    SemanticObjectError,
    UECFreeParameter,
    UECRequirement,
    disposition_problems,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .anchors import AnchorRegistry

#: Subjects an S2b statement can bind — one per extended mechanism.
SUBJECTS: tuple[str, ...] = (
    "MEMORY_MODEL",  # 3.4.9 transport memory model (incl. 3.4.9.5/3.4.9.6)
    "RUDI",  # 3.5.23 reliable idempotent delivery
    "CBFC_TLV",  # 5.3.2.2 CBFC negotiation TLV wire clauses
    "INC",  # 2.4 in-network collectives detail
    "PHY",  # 6.1.x PHY rates, media, AUIs
)

#: Anchor ids this stage is allowed to cite (mechanism-to-anchor map; the 14
#: S2b registry anchors plus the pre-existing 2.4 and 6.1 entry anchors for
#: the same mechanisms).
S2B_ANCHOR_IDS: frozenset[str] = frozenset(
    {
        "UEC11-S2.4-INC",
        "UEC11-S2.4.1-INC-ASSUMPTIONS",
        "UEC11-S2.4.3-INC-OPERATIONS",
        "UEC11-S2.4.6-INC-ORDERING-MODES",
        "UEC11-S2.4.10-INC-SWITCH-CAPS",
        "UEC11-S2.4.11-INC-TRANSPORT",
        "UEC11-S3.4.9-MEMORY-MODEL",
        "UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY",
        "UEC11-S3.5.23-RUDI",
        "UEC11-S5.3.2.2-CBFC-TLV",
        "UEC11-S5.3.2.2-CBFC-TLV-HANDSHAKE",
        "UEC11-S6.1-PHY-SUPPORT",
        "UEC11-S6.1.1.1-PHY-MEDIA-100G",
        "UEC11-S6.1.1.2-PHY-RATES-100G",
        "UEC11-S6.1.2.1-PHY-MEDIA-200G",
        "UEC11-S6.1.2.2-PHY-RATES-200G",
    }
)

_REQUIREMENTS: tuple[UECRequirement, ...] = (
    # -- 3.4.9 memory model ------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-F07-R01",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "The AI Base, AI Full, and HPC profiles provide a memory model "
            "consistent with options available through the libfabric API: a "
            "set of minimal requirements expected of all implementations "
            "plus controls to be stronger for implementations that choose "
            "so. It covers ordering, consistency, atomicity, global "
            "observability, and idempotency."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R02",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "The memory model for the Unified Local profile is largely "
            "implementation-dependent; its supported options and "
            "capabilities are detailed in section 3.4.9.5."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R03",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "Ordering consists of message ordering and data ordering; both "
            "are tightly tied to the underlying transport layer. The RUD "
            "and RUDI protocols make no message ordering guarantees and no "
            "data ordering guarantees."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R04",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "ROD implementations must provide message processing ordering "
            "for a given flow between the initiator SES and the target SES; "
            "at minimum a flow is traffic from one PIDonFEP at the "
            "initiator to a specific Resource Index of a PIDonFEP at the "
            "target, and one or more flows may map onto a single PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R05",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "When using ROD, SES must process messages in the order "
            "presented to it at the target FEP for a specific JobID, "
            "PIDonFEP, Resource Index tuple."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R06",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "If requested, implementations must deliver completion "
            "notifications at the target only after all data has been "
            "placed."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R07",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST NOT",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "Messages marked with the delivery-complete bit must not "
            "deliver the target completion until the corresponding global "
            "observability has been achieved."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R08",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "The wire protocol provides no direct support for fully ordered "
            "completions at the target: rendezvous transactions use a "
            "different sequence-number space for payload delivery than for "
            "request processing, and deferrable-send completion order "
            "follows the order in which matching receives are provided. "
            "Stronger completion ordering is vendor-defined."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R09",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "Data ordering describes the order in which two messages "
            "accessing a single memory address from a single source become "
            "globally observable; ordering between bytes within a message "
            "is not defined — the last byte may become globally observable "
            "in host memory before the first."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R10",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MAY",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "Implementations may provide stronger ordering semantics than "
            "the data-ordering minimum, but those are beyond the scope of "
            "the specification and are not likely to be portable."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R11",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MAY",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "ROD implementations supporting atomic operations may provide "
            "an option for RAW, WAW, and WAR data ordering on ATOMIC and "
            "FETCHING_ATOMIC operations of 16 bytes or less, at a "
            "granularity limited to a single datatype element; "
            "implementations may combine atomic operations at the target so "
            "not every update is globally observable."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R12",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "If atomic operations are supported, atomicity must be "
            "guaranteed at the granularity of a single element of the size "
            "of the datatype."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R13",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "If supported, concurrent atomic operations must be consistent "
            "at the target at single-element granularity. Concurrent "
            "operations target the same FA, JobID, PIDonFEP, Resource "
            "Index, Memory Key/Match Bits, Offset tuple, may be initiated "
            "from the same or different FEPs, and include ATOMIC versus "
            "FETCHING_ATOMIC and AMO_WRITE/AMO_READ versus other atomics."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R14",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "Consistency between concurrent send, write, read, and atomic "
            "operations may be supported but is not required; users "
            "needing write or read semantics consistent with atomic "
            "operations must use the atomic versions of those operations."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R15",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MAY",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "Implementations may support stronger atomicity; the "
            "UET_AMO_CPU_COHERENT semantic control requests atomic "
            "operations coherent with and atomic relative to CPU accesses, "
            "and if the requested semantics cannot be provided the target "
            "FEP returns RC_AMO_UNSUPPORTED_OP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R16",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST NOT",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "The default for global observability is that it is not "
            "guaranteed: a FEP must not indicate that a message has "
            "completed until all packets have been acknowledged by PDS, "
            "and it must wait until a semantic response is received before "
            "indicating completion (sufficient for libfabric transmit-"
            "complete semantics)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R17",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "With the DC (delivery complete) bit set, an implementation "
            "may reject the transaction as unsupported with a semantic "
            "failure; if it does not, it must defer the semantic response "
            "until it can guarantee that the data is globally observable "
            "at the target."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R18",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "Operations performed using the ROD or RUD protocol must "
            "appear in memory at the target and at the initiator as if "
            "performed exactly once."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R19",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "A target implementing FETCHING_ATOMIC operations must buffer "
            "the old data value to handle the case where the response is "
            "lost; this holds for both the ROD and RUD protocols."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R20",
        anchor_ids=("UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "Unified Local transactions are ordered for the ROD or RODL "
            "delivery modes and unordered for the RUD delivery modes; the "
            "data ordering model is defined by the implementation."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R21",
        anchor_ids=("UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "The Unified Local profile follows the same consistency and "
            "atomicity guarantees, but the definition of concurrent "
            "operations is narrowed to two operations targeting the same "
            "FA, JobID, Offset; global observability semantics leverage "
            "the DC bit to optionally offer a global observability "
            "guarantee."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R22",
        anchor_ids=("UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "The transport for the Unified Local profile is defined only "
            "over the RODL delivery mode; it therefore guarantees "
            "idempotency."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R23",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="DEFINITIONAL",
        subject="MEMORY_MODEL",
        disposition="informational",
        statement=(
            "Synchronized operations add no ordering expectations between "
            "two UET_SYNC_WRITE messages (even when one is the "
            "synchronized completing operation with ses.hd set) and do not "
            "change completion-notification ordering with respect to other "
            "completion notifications."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R24",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "The completion notification, if requested, for a "
            "UET_SYNC_WRITE with ses.hd set must follow the payload "
            "delivery for every UET_SYNC_WRITE message in the "
            "ses.sync_group, including the payload in the synchronized "
            "completing operation; that notification has no defined "
            "ordering with respect to other completion notifications."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R25",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        keyword="MUST",
        subject="MEMORY_MODEL",
        disposition="unsupported",
        statement=(
            "Synchronized completing operations using UET_SYNC_ATOMIC must "
            "perform the atomic operation after the payload delivery for "
            "every UET_SYNC_WRITE message in the sync group."
        ),
    ),
    # -- 3.5.23 RUDI -------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-F07-R26",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "RUDI sequences are specified for RMA writes and RMA reads and "
            "provide reliable delivery for idempotent operations: no PDCs "
            "are used and each packet is handled individually without "
            "maintaining sequence numbers."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R27",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "The pds.pkt_id field is a locally assigned number echoed back "
            "in the RUDI response so the response can be associated with "
            "the request. RUDI maintains no PDS or SES state at the target "
            "— all state resides at the initiator — so no clear-protocol "
            "exchanges are required, and SES responses are not retained "
            "for retransmission."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R28",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "RUDI service list: each packet is guaranteed delivered to SES "
            "at least once; RUDI is used only for idempotent operations; "
            "the source assigns a unique pds.pkt_id to each transmitted "
            "packet."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R29",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "PDS at the target waits for semantic processing to complete "
            "before transmitting the response for each packet; there is no "
            "message completion at the target, and RUDI Requests are "
            "acknowledged by RUDI Response packets."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R30",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "Retransmitted RUDI packets set pds.flags.retx; an ECN-marked "
            "RUDI Request sets pds.flags.m on the corresponding response; "
            "each RUDI Request packet results in one and only one RUDI "
            "Response packet, and each response uses the pds.pkt_id of its "
            "request."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R31",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="MUST",
        subject="RUDI",
        disposition="unsupported",
        statement=(
            "The destination transmits a NACK if a trimmed RUDI Request is "
            "received; the source processes NACKs for RUDI Requests and "
            "retransmits the request, and retransmits also on receipt of "
            "trimmed RUDI Responses — the initiator retransmits the "
            "request to recover from all packet-loss events."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R32",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="SHOULD",
        subject="RUDI",
        disposition="unsupported",
        statement=(
            "The destination should transmit a NACK when a RUDI packet is "
            "dropped, for example due to limited resources."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R33",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "RUDI Response packets are never NACK'd: there is no state at "
            "the target to handle a NACK for a RUDI response."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R34",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="MUST",
        subject="RUDI",
        disposition="unsupported",
        statement=(
            "Loss recovery is provided by the initiator: an RTO timer per "
            "packet is required."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R35",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        keyword="DEFINITIONAL",
        subject="RUDI",
        disposition="informational",
        statement=(
            "RUDI does not use UET congestion control; packet loss is "
            "determined by the initiator RTO, NACKs from the target, and "
            "trimmed RUDI responses."
        ),
    ),
    # -- 5.3.2.2 CBFC TLV wire clauses ---------------------------------------------
    UECRequirement(
        requirement_id="UEC11-F07-R36",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "The CBFC TLV is an LLDP organizationally specific TLV; CBFC "
            "support is determined by the presence or absence of the CBFC "
            "TLV in both the local and remote LLDP databases."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R37",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "The CBFC TLV exchanges receiver buffer parameters (cell size, "
            "per-packet overhead, total credits), negotiates sender credit "
            "size and packet overhead, identifies each VC with identifier, "
            "state, queue, packet-stream selector and optional credit "
            "limit, signals sender and receiver readiness, and supports "
            "per-VC credit-limit modification plus per-VC stop and "
            "reactivation; VC configuration is independent per direction."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R38",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV-HANDSHAKE",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "Initialization begins when the receiver sets R_VC_WANT for "
            "VCs desiring CBFC service; the sender seeing R_VC_WANT in its "
            "remote database configures the requested VCs and acknowledges "
            "by setting S_VC_RTS; the receiver seeing S_VC_RTS configures "
            "itself from the sender-provided parameters and indicates "
            "readiness by setting R_VC_RTR; from then on the sender uses "
            "CBFC for transmissions on the configured VCs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R39",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV-HANDSHAKE",),
        keyword="SHALL NOT",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "The sender shall not set S_VC_RTS for a VC unless the remote "
            "receiver has set R_VC_WANT for that VC, and the receiver "
            "shall not set R_VC_RTR for a VC unless the remote sender has "
            "set S_VC_RTS for that VC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R40",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV-HANDSHAKE",),
        keyword="SHALL NOT",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "The sender shall not use CBFC for a VC unless the remote "
            "receiver has set R_VC_RTR for that VC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R41",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "Wire format: 7-bit TLV type 127 (organizationally specific); "
            "9-bit TLV information string length equal to n*6+20 for 0 <= "
            "n <= 32 receive VCs; maximum information string length 212 "
            "bytes and maximum total TLV length 214 bytes."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R42",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "Identification fields: the 24-bit UEC Company ID FA-7A-CB "
            "identifies UE TLVs; the 5-bit subtype 1 identifies the CBFC "
            "TLV, with subtype 0x1F reserved for extending the UE TLV "
            "subtype field; the 3-bit version is 0."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R43",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "Future versions of the CBFC TLV shall be backward-compatible "
            "with version 0; they can extend the TLV length to add "
            "information and definitions for reserved fields, and older "
            "versions ignore updated reserved fields, code points, or TLV "
            "length extensions."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R44",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "The 4-bit Error_Code signals sender-side conditions: 0x0 no "
            "error; 0x1 cannot support the receiver cell size; 0x2 cannot "
            "support a requested VC; 0x3 cannot support the credit pool "
            "size; 0x4 cannot support a requested VC credit limit; 0x5 "
            "sender and receiver packet identification do not match; 0x6 "
            "other; 0x7-0xF reserved."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R45",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "S_CreditSize (12 bits, bytes per credit at the sending port; "
            "0 means not yet set) shall be valid when any S_VC_RTS flag "
            "is TRUE and shall not change while any S_VC_RTS flag is "
            "TRUE; the sending port waits to see the receiver's R_CellSize "
            "in the remote LLDP database before selecting its credit "
            "size."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R46",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "S_PacketOverhead (8 bits, overhead bytes per packet at the "
            "sending port) shall be valid when any S_VC_RTS flag is TRUE "
            "and shall not change while any S_VC_RTS flag is TRUE."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R47",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "S_VC_RTS holds 32 ready-to-send flags, bit 0 for VC0; when "
            "TRUE the sender is ready to send but shall wait to begin "
            "until the receiver sets R_VC_RTR to TRUE."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R48",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "R_VCnLength (4 bits) specifies the length of each per-VC "
            "R_VCn element — 6 bytes for version 0 — and version 0 shall "
            "skip over any bytes beyond 6 when reading the R_VCn fields."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R49",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "Receiver fields: R_CellSize (12 bits, bytes per credit at the "
            "receiving port); R_PacketOverhead (8 bits, overhead bytes at "
            "the receiver); R_TotalCredits (24 bits, total credits of "
            "credit size available for all VCs at the receiver); R_NumVCs "
            "(6 bits, number of following R_VCn subfields)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R50",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "R_VC_Want TRUE means this port wants CBFC lossless receiver "
            "service for this VC; FALSE means the VC is best effort."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R51",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "When R_VC_Want transitions to FALSE, the sender shall stop "
            "using CBFC credits to qualify transmission on that VC, set "
            "the corresponding S_VC_RTS flag to FALSE, and return to "
            "best-effort forwarding."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R52",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="SHALL NOT",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "R_VC_RTR shall not be set TRUE until after the corresponding "
            "S_VC_RTS is set TRUE by the remote link partner; when "
            "R_VC_RTR transitions to FALSE, the sender shall stop using "
            "CBFC credits to qualify transmission on that VC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R53",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "R_VcID (5 bits) indicates the receive VC number configured by "
            "the R_VCn parameters; VC numbers range from 0 to 31 and "
            "implementations are not required to support all 32 possible "
            "VCs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R54",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "R_PktID_Sel (4 bits) selects the optional packet-to-VC "
            "identification service — assurance that both link partners "
            "count credits on the same packets, without which credit "
            "counts are incorrect and the link can lose packets even with "
            "CBFC: 0x0 disable; 0x1 PCP/DEI with R_MaskPcpDei; 0x2 DSCP "
            "with R_MaskDSCP; 0x3 a 12-bit stream handle per IEEE "
            "802.1CBdb-2021; 0x4-0xF reserved."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R55",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="MAY",
        subject="CBFC_TLV",
        disposition="unsupported",
        statement=(
            "The sender may ignore the receiver-provided packet-to-VC "
            "mapping, compare it against its own sending VC configuration "
            "to verify agreement, or dynamically install it; if the "
            "receiver disables packet identification while the sender is "
            "configured for dynamic mapping, the sender disables the VC "
            "and reports an error."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R56",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        keyword="DEFINITIONAL",
        subject="CBFC_TLV",
        disposition="informational",
        statement=(
            "For PCP/DEI selection the set of packets that are members of "
            "the VC is those where (PcpDei & R_MaskPcpDei) == R_PcpDei is "
            "true, with the DEI bit the least significant bit of both the "
            "mask and value fields."
        ),
    ),
    # -- 2.4 INC -------------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-F07-R57",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC enables network switches to perform computational tasks "
            "directly for group operations, accelerating collective "
            "operations defined by MPI and collective communication "
            "libraries; groups are communicators whose processes are ranks "
            "with integer IDs from 0 to r-1."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R58",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC offers acceleration for Barrier, Broadcast, Allreduce, "
            "and Reduce; these basic operations can accelerate more "
            "complex operations such as reduce-scatter. A collective is "
            "active from the first call issued by a rank until the final "
            "completion notification is received by a rank."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R59",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "UE INC operates on a single logical switch with a single "
            "switch endpoint (SEP); vendors may offer solutions where the "
            "single logical switch is a distributed set of switches, "
            "provided it adheres to the specified behavior."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R60",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "UE INC must operate over a lossless fabric (using PFC or "
            "CBFC) over the UET ROD transport between the FEP and the "
            "SEP, and each FEP must be directly connected to a port "
            "associated with a SEP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R61",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "Packets carrying INC reduction operations (allreduce and "
            "reduce) must carry full elements of the specified datatype — "
            "a single element of the operation must be carried in one "
            "packet."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R62",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        keyword="MUST NOT",
        subject="INC",
        disposition="unsupported",
        statement=(
            "All FEPs in an INC communicator are associated with the same "
            "job; operands carried in the payload must use little-endian "
            "byte order and must not be padded (composite operands such "
            "as MINLOC and MAXLOC may contain internal padding, but no "
            "padding is added before or after operands)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R63",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC components: the INC manager (IM) daemon that facilitates "
            "collective offload; UET services — SES deferrable send, PDS "
            "reserved ROD service, non-interleaved messages, optional TFC, "
            "optional TSS; groups of FEPs called communicators; and one or "
            "more logical SEPs, each supporting the INC switch."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R64",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "The IM establishes a communicator by grouping member FEPs, "
            "associating the group with a SEP, and assigning a unique "
            "collective ID (CID, 20 bits) on creation; the INC switch uses "
            "the CID to disambiguate communicators and filters packets on "
            "JobID/CID combinations."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R65",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "The collective sequence number (CSN, 12 bits) is set to 0 on "
            "communicator creation; a rank starting an operation uses the "
            "current CSN and increments it by one, wrapping from the "
            "maximum 12-bit value back to 0, and issues a "
            "UET_DEFERRABLE_SEND carrying the INC field that encodes the "
            "CSN, operation type, and parameters."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R66",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="MUST NOT",
        subject="INC",
        disposition="unsupported",
        statement=(
            "The number of outstanding collective operations — operations "
            "a rank may initiate without waiting for a completion — is "
            "subject to the SEP's capabilities and must not exceed the "
            "CSN space, i.e. 4096 total outstanding collective operations."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R67",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC communicator ranks may post a receive buffer identified "
            "by a tag with the inc_info format before sending input data; "
            "ranks issue operations asynchronously and the switch blocks "
            "an operation until all ranks have contributed their data."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R68",
        anchor_ids=("UEC11-S2.4-INC",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "Output routing depends on the operation: allreduce requires "
            "the SEP to send data to all ranks; reduce sends to one "
            "specified root; broadcast sends to all ranks except the root, "
            "which also receives output if forced output is requested in "
            "the INC operation."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R69",
        anchor_ids=("UEC11-S2.4.3-INC-OPERATIONS",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC operations and opcodes: UET_INC_REDUCE 0x00 (MUST), "
            "UET_INC_ALLREDUCE 0x01 (MUST), UET_INC_BCAST 0x02, "
            "UET_INC_BARRIER 0x03 (MUST), UET_INC_EXSCAN 0x04, "
            "UET_INC_SYNCBCAST 0x05; 0x06-0xEF reserved; 0xF0-0xFF "
            "vendor-defined."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R70",
        anchor_ids=("UEC11-S2.4.3-INC-OPERATIONS",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "An implementation must support at least one broadcast "
            "implementation: UET_INC_BCAST, where non-root FEPs do not "
            "synchronize with the SEP (enabling pipelining of multiple "
            "BCAST operations), or UET_INC_SYNCBCAST, where non-root FEPs "
            "synchronize with the SEP using a zero-sized message before "
            "starting the operation."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R71",
        anchor_ids=("UEC11-S2.4.6-INC-ORDERING-MODES",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC reduction operators: MIN, MAX, SUM, SUM_SCALE (divide by "
            "a 32-bit unsigned factor configured by the IM), PROD, LOR, "
            "LAND, BOR, BAND, LXOR, BXOR, MINLOC and MAXLOC on paired "
            "types (location is UET_TYPE_UINT32, the smaller of value and "
            "location is padded after the element); 0x0D-0xEF reserved, "
            "0xF0-0xFE vendor-defined."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R72",
        anchor_ids=("UEC11-S2.4.6-INC-ORDERING-MODES",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "Required datatype combinations: INT32 and UINT32 must "
            "support MIN, MAX, SUM, LOR, LAND, BOR, BAND, LXOR and BXOR; "
            "BF16 and FP16 must support MIN, MAX and SUM."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R73",
        anchor_ids=("UEC11-S2.4.6-INC-ORDERING-MODES",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "INC implementations must support at least one operator "
            "ordering mode when configured through the IM: no ordering; "
            "consistent ordering in the same communicator; across "
            "different communicators; across different communicators and "
            "jobs; or natural ordering (ranks 0 to p-1, which limits "
            "parallelism and may lower performance)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R74",
        anchor_ids=("UEC11-S2.4.6-INC-ORDERING-MODES",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "INC implementations must support the round-to-nearest, "
            "ties-to-even floating-point rounding mode; they may "
            "additionally support ties-away-from-zero, toward zero, "
            "toward plus infinity, and toward minus infinity."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R75",
        anchor_ids=("UEC11-S2.4.10-INC-SWITCH-CAPS",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "An INC-compliant switch must support SES functions — header "
            "types UET_HDR_REQUEST_STD and UET_RESPONSE, opcodes "
            "UET_DEFERRABLE_SEND and UET_DEFERRABLE_RTR — and PDS "
            "functions — reserved ROD PDCs (ROD_REQ, ACK, NACK, CP close "
            "commands) and UET CRC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R76",
        anchor_ids=("UEC11-S2.4.10-INC-SWITCH-CAPS",),
        keyword="MAY",
        subject="INC",
        disposition="unsupported",
        statement=(
            "A switch may support CMS functions (TFC) and TSS functions; "
            "no special PDS, CMS, or TSS features are required to support "
            "INC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R77",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC uses UET_DEFERRABLE_SEND and UET_DEFERRABLE_RTR "
            "operations; all collective information is encoded in the "
            "64-bit ses.inc_info field, which replaces ses.match_bits in "
            "UET_HDR_REQUEST_STD packets — the SEP can interpret it "
            "because it knows the FA, JobID, PIDonFEP, RI tuple of the "
            "request."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R78",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "ses.inc_info encoding: ver (2 bits, set to 0x00); rt (1 bit, "
            "set by the rank that solely receives the output or provides "
            "the input of single-output/input operations); ip (1 bit, "
            "in-place); fo (1 bit, forced output); rsvd (3 bits); op_type "
            "(8 bits); cid (20 bits); csn (12 bits); data_type (8 bits, "
            "0x00 without reduction); reduce_op (8 bits, 0x00 without "
            "reduction)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R79",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "The CSN is incremented by broadcast collective operations "
            "even when no message is received — non-root FEPs increment "
            "the expected CSN without receiving a message — so subsequent "
            "CSNs align; every rank increments the CSN for each new "
            "collective operation."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R80",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "If data arrives at an FEP without a posted buffer, the FEP "
            "responds indicating the event; deferred packets are "
            "retransmitted with new pds.psn values when delivered to SES "
            "and acknowledged, and no NACK is generated for a deferral — "
            "it is communicated via the SES response in an ACK. "
            "UET_DEFERRABLE_RTR triggers retransmission sooner than the "
            "buffer-not-ready timer."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R81",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "An SEP receiving a message with an unknown ses.inc_info.ver "
            "must ignore the rest of ses.inc_info, reject the message, "
            "and return RC_UNSUPPORTED_OP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R82",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC uses reserved ROD PDCs, which provide in-order delivery "
            "of requests and responses; reserved PDCs simplify the SEP "
            "and each INC communicator is allocated an individual PDC. "
            "INC PDCs may optionally use TFC so the receiving SEP or FEP "
            "can constrain in-flight data on a PDC based on buffer "
            "availability."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R83",
        anchor_ids=("UEC11-S2.4.11-INC-TRANSPORT",),
        keyword="MUST",
        subject="INC",
        disposition="unsupported",
        statement=(
            "UET profiles supporting INC must support reserved PDCs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R84",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        keyword="DEFINITIONAL",
        subject="INC",
        disposition="informational",
        statement=(
            "INC error categories are transmission errors, format errors "
            "(unexpected CSN, datatype mismatch, unsupported type), "
            "member failure, SEP failure, and IM failure; transmission "
            "errors are avoided by the lossless transport with FEC and "
            "LLR and otherwise recovered by PDS retransmission, and "
            "uncorrectable errors are reported to the IM, which destroys "
            "the INC communicator and notifies all ranks and switches "
            "involved."
        ),
    ),
    # -- 6.1.x PHY rates -------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-F07-R85",
        anchor_ids=("UEC11-S6.1-PHY-SUPPORT",),
        keyword="DEFINITIONAL",
        subject="PHY",
        disposition="informational",
        statement=(
            "UE PHYs are a subset of Ethernet PHYs with 100 Gb/s or 200 "
            "Gb/s per-lane signaling, as defined in IEEE 802.3-2022, "
            "802.3db-2022, 802.3ck-2022, 802.3df-2024, and P802.3dj; "
            "other Ethernet PHYs may support some UE specifications but "
            "are not UE-compliant."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R86",
        anchor_ids=("UEC11-S6.1-PHY-SUPPORT",),
        keyword="SHALL",
        subject="PHY",
        disposition="unsupported",
        statement=(
            "A device compliant with the UE PHY specifications shall "
            "conform to one of the PHY-type specifications listed in "
            "6.1.1.2 (100 Gb/s per lane) or 6.1.2.2 (200 Gb/s per lane)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R87",
        anchor_ids=("UEC11-S6.1.1.2-PHY-RATES-100G",),
        keyword="DEFINITIONAL",
        subject="PHY",
        disposition="informational",
        statement=(
            "In-scope PHY rates for 100 Gb/s-per-lane signaling: "
            "100GBASE-R family (KR1, CR1, VR1, SR1, DR, FR1); 200GBASE-R "
            "(KR2, CR2, VR2, SR2); 400GBASE-R (KR4, CR4, VR4, SR4, DR4, "
            "FR4); 800GBASE-R (KR8, CR8, VR8, SR8, DR8)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R88",
        anchor_ids=("UEC11-S6.1.1.2-PHY-RATES-100G",),
        keyword="DEFINITIONAL",
        subject="PHY",
        disposition="informational",
        statement=(
            "In-scope 100 Gb/s-per-lane attachment unit interfaces: "
            "100GAUI-1, 200GAUI-2, 400GAUI-4, 800GAUI-8, and 1.6TAUI-16 "
            "in both chip-to-chip (C2C, Annex 120F) and chip-to-module "
            "(C2M, Annex 120G) variants."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R89",
        anchor_ids=("UEC11-S6.1.2.2-PHY-RATES-200G",),
        keyword="DEFINITIONAL",
        subject="PHY",
        disposition="informational",
        statement=(
            "In-scope PHY rates for 200 Gb/s-per-lane signaling: "
            "200GBASE-R family (KR1, CR1, DR1); 400GBASE-R (KR2, CR2); "
            "800GBASE-R (KR4, CR4, DR4, FR4-500); 1.6TBASE-R (KR8, CR8, "
            "DR8); plus 200GAUI-1, 400GAUI-2, 800GAUI-4, and 1.6TAUI-8 "
            "C2C (Annex 176C) and C2M (Annex 176D) interfaces."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R90",
        anchor_ids=("UEC11-S6.1.1.1-PHY-MEDIA-100G",),
        keyword="DEFINITIONAL",
        subject="PHY",
        disposition="informational",
        statement=(
            "Supported physical media for 100 Gb/s-per-lane signaling: "
            "backplane (KR, clause 163); copper cable (CR, 162); MMF to "
            "50 m (VR, 167) and 100 m (SR, 167); parallel SMF to 500 m "
            "(DR, 124/140); WDM SMF to 2 km (FR, 140/151). DR-2 (2 km), "
            "LR (10 km), and coherent ZR are beyond UE scope."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-F07-R91",
        anchor_ids=("UEC11-S6.1.2.1-PHY-MEDIA-200G",),
        keyword="DEFINITIONAL",
        subject="PHY",
        disposition="informational",
        statement=(
            "Supported physical media for 200 Gb/s-per-lane signaling: "
            "backplane (KR, clause 178); copper cable (CR, 179); parallel "
            "SMF to 500 m (DR, 180); WDM SMF to 500 m (FR4-500, 181). "
            "These PHYs all use the same RS-FEC (544,514) with "
            "interleaving of 10-bit symbols from four codewords, without "
            "inner FEC or a separate FEC sublayer."
        ),
    ),
)

_FREE_PARAMETERS: tuple[UECFreeParameter, ...] = (
    UECFreeParameter(
        parameter_id="UEC11-F07-F01",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        name="memory_model_strength",
        freedom=(
            "Implementations may provide stronger message/data ordering, "
            "completion ordering, global observability, or atomicity than "
            "the minimal memory model; the stronger options are vendor-"
            "defined, beyond spec scope, and not likely to be portable."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F02",
        anchor_ids=("UEC11-S3.4.9.5-UNIFIED-LOCAL-MEMORY",),
        name="unified_local_memory_model_options",
        freedom=(
            "The Unified Local memory model is largely implementation-"
            "dependent: wire ordering is fixed (ROD/RODL ordered, RUD "
            "unordered) but the data ordering model and the optionally "
            "offered global-observability guarantee are implementation "
            "choices."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F03",
        anchor_ids=("UEC11-S3.4.9-MEMORY-MODEL",),
        name="coherent_atomics_implementation",
        freedom=(
            "How UET_AMO_CPU_COHERENT semantics are implemented is open "
            "(the spec's example is PCI Express atomic operations); only "
            "the fallback behavior RC_AMO_UNSUPPORTED_OP is fixed."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F04",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        name="rudi_rto_timer_value",
        freedom=(
            "RUDI requires an RTO timer per packet but fixes no timer "
            "value or backoff policy; the value is a deployment decision."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F05",
        anchor_ids=("UEC11-S3.5.23-RUDI",),
        name="rudi_nack_on_resource_drop",
        freedom=(
            "Whether the destination transmits a NACK when a RUDI packet "
            "is dropped for limited resources is a SHOULD — a deployment/"
            "implementation choice; the trimmed-request NACK is "
            "unconditional."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F06",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        name="cbfc_vc_count",
        freedom=(
            "The number of CBFC virtual channels a port supports is free "
            "within 0..32 (R_NumVCs, 6 bits); implementations are not "
            "required to support all 32 possible VCs."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F07",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        name="cbfc_credit_and_overhead_values",
        freedom=(
            "S_CreditSize, R_CellSize, S_PacketOverhead, and "
            "R_PacketOverhead values are negotiated per link via the CBFC "
            "TLV; the spec fixes field widths and stability rules, not "
            "the values."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F08",
        anchor_ids=("UEC11-S5.3.2.2-CBFC-TLV",),
        name="cbfc_packet_to_vc_identification",
        freedom=(
            "The packet-to-VC identification mode (disable, PCP/DEI, "
            "DSCP, or stream handle) is a receiver choice, and the sender "
            "may ignore, verify, or dynamically install the mapping; "
            "per-VC credit limits are optional and receiver-modifiable."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F09",
        anchor_ids=("UEC11-S2.4-INC",),
        name="inc_outstanding_ops_capacity",
        freedom=(
            "How many collective operations may be outstanding is subject "
            "to the SEP's capabilities; the spec fixes only the ceiling "
            "of 4096 (the 12-bit CSN space)."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F10",
        anchor_ids=("UEC11-S2.4.6-INC-ORDERING-MODES",),
        name="inc_operator_ordering_mode",
        freedom=(
            "Which operator ordering mode(s) an INC implementation "
            "supports is free as long as at least one of the five modes "
            "is offered; the mode is selected through the IM."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F11",
        anchor_ids=("UEC11-S2.4.6-INC-ORDERING-MODES",),
        name="inc_accumulator_and_rounding_extras",
        freedom=(
            "The internal accumulator datatype length is not mandated "
            "(a sufficiently large datatype is recommended), and the four "
            "floating-point rounding modes beyond ties-to-even are "
            "optional."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F12",
        anchor_ids=("UEC11-S2.4-INC",),
        name="inc_sum_scale_factor",
        freedom=(
            "The UET_INC_SUM_SCALE divisor is a 32-bit unsigned integer "
            "configured by the IM per communicator (setting it to the "
            "rank count yields average); the value is not spec-fixed."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F13",
        anchor_ids=("UEC11-S2.4.1-INC-ASSUMPTIONS",),
        name="inc_logical_switch_implementation",
        freedom=(
            "How the single logical INC switch is realized (single device "
            "or a distributed set of switches, e.g. tree topologies) is a "
            "vendor choice provided the specified behavior is preserved."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F14",
        anchor_ids=("UEC11-S2.4.3-INC-OPERATIONS",),
        name="inc_vendor_operations",
        freedom=(
            "Opcodes 0xF0-0xFF and reduction operators 0xF0-0xFE are "
            "vendor-defined; UET_INC_EXSCAN (0x04) and the choice between "
            "BCAST and SYNCBCAST are implementation choices."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F15",
        anchor_ids=("UEC11-S6.1.1.2-PHY-RATES-100G", "UEC11-S6.1.2.2-PHY-RATES-200G"),
        name="phy_rate_selection",
        freedom=(
            "The spec enumerates the admissible PHY rate/type families "
            "(100/200 Gb/s per lane, 100G-1.6T ports) but a deployment's "
            "actual link rate stays a configured input — no rate becomes "
            "standard-derived (consistent with S6 finding F08)."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-F07-F16",
        anchor_ids=("UEC11-S6.1-PHY-SUPPORT",),
        name="phy_lane_generation",
        freedom=(
            "Whether a device uses the 100 Gb/s or 200 Gb/s per-lane "
            "signaling generation (6.1.1 versus 6.1.2) is an "
            "implementation choice; both lists satisfy UE PHY compliance."
        ),
    ),
)


def requirements() -> tuple[UECRequirement, ...]:
    """All F07-extension requirement objects of this stage."""
    return _REQUIREMENTS


def free_parameters() -> tuple[UECFreeParameter, ...]:
    """All free-parameter objects of this stage."""
    return _FREE_PARAMETERS


def all_objects() -> tuple[UECRequirement | UECFreeParameter, ...]:
    """Requirements and free parameters together."""
    return _REQUIREMENTS + _FREE_PARAMETERS


def anchor_ids() -> frozenset[str]:
    """Every anchor id cited by any object of this stage."""
    return frozenset(aid for obj in all_objects() for aid in obj.anchor_ids)


def _shape_problems(obj: UECRequirement | UECFreeParameter) -> list[str]:
    problems: list[str] = []
    oid = getattr(obj, "requirement_id", None) or getattr(
        obj, "parameter_id", None
    )
    if not obj.anchor_ids:
        problems.append(f"{oid}: no anchor ids")
    if isinstance(obj, UECRequirement):
        if obj.keyword not in NORMATIVE_KEYWORDS:
            problems.append(
                f"{oid}: unknown keyword {obj.keyword!r} "
                f"(not in {NORMATIVE_KEYWORDS})"
            )
        if obj.subject not in SUBJECTS:
            problems.append(
                f"{oid}: unknown subject {obj.subject!r} (not in {SUBJECTS})"
            )
        problems.extend(disposition_problems(oid, obj.disposition))
        words = len(obj.statement.split())
        if words == 0:
            problems.append(f"{oid}: empty statement")
        elif words > MAX_STATEMENT_WORDS:
            problems.append(
                f"{oid}: statement has {words} words "
                f"(> {MAX_STATEMENT_WORDS})"
            )
    else:
        if not obj.name.strip():
            problems.append(f"{oid}: empty free-parameter name")
        if obj.domain != "FREE":
            problems.append(f"{oid}: free parameter must stay domain=FREE")
        if not obj.freedom.strip():
            problems.append(f"{oid}: empty freedom description")
    return problems


def check_against_registry(registry: "AnchorRegistry") -> list[str]:
    """Validate every object against the anchor registry.

    Checks: unique object ids, structural shape, and that every cited
    anchor id resolves in the registry (dangling anchors are hard errors).
    Returns all problems; empty list means valid.
    """
    problems: list[str] = []
    seen: dict[str, int] = {}
    for obj in all_objects():
        oid = getattr(obj, "requirement_id", None) or getattr(
            obj, "parameter_id", None
        )
        seen[oid] = seen.get(oid, 0) + 1
        problems.extend(_shape_problems(obj))
        try:
            registry.resolve(obj.anchor_ids)
        except Exception as exc:  # AnchorRegistryError on dangling ids
            problems.append(f"{oid}: {exc}")
    problems.extend(
        f"duplicate object id {oid} ({count} entries)"
        for oid, count in sorted(seen.items())
        if count > 1
    )
    return problems


def assert_valid(registry: "AnchorRegistry") -> None:
    """Raise :class:`SemanticObjectError` if any check fails."""
    problems = check_against_registry(registry)
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise SemanticObjectError(
            f"UEC F07-extension semantic objects failed validation: "
            f"{detail}{more}"
        )
