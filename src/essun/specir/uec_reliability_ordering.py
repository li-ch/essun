"""UEC 1.1 reliability & ordering semantics: stage S3 semantic objects (T010/T011).

Third slice of the UEC semantic profile ladder: the reliability and ordering
semantics of the UE transport — the five packet delivery modes and their PDC
bindings (3.5.3/3.5.6), loss detection and recovery incl. trimmed-packet
processing (3.5.15 + 4.1), the per-mode normative services (RUD 3.5.20, ROD
3.5.21, RODL 3.5.22 — RODL being the scale-up-specific mode), and the link
layer retry reliability machinery (LLR 5.1/5.1.3).

Object model, vocabularies and validation follow the S2 pattern
(:mod:`essun.specir.uec_link_transport`): every object is a mapping
``requirement id -> anchor ids -> typed statement`` (provenance rule), and
the dataclasses/:data:`NORMATIVE_KEYWORDS`/:data:`MAX_STATEMENT_WORDS` are
imported from S2 as the single source of truth.  Keywords are typed exactly as
the spec text carries them; ``DEFINITIONAL`` marks load-bearing structure
facts stated without an RFC-2119 keyword (overview sections 3.5.3/3.5.6 are
informative outside 3.3 per the S2 meta-statement R01).  Free parameters are
always ``domain="FREE"``.

Statements are paraphrases in our own words (S0 license gate: verbatim spec
text in git remains only the S1 registry's <= 30-word quotes).  Anchors are
section-scoped per the S2 method notes: an anchor pins its section's entry
page/hash; statements may be drawn from the section's full page span (e.g. the
5.1 anchor pp. 631-649 also grounds 5.1.4 configuration, 5.1.5-5.1.8
transmit/receive/ACK processing and 5.1.10 error propagation).  Dangling
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

#: Subjects a stage-S3 statement can bind.  The per-mode subjects (RUD, ROD,
#: RODL, RUDI, UUD) separate the normative services of sections 3.5.20-3.5.22
#: from the taxonomy (DELIVERY_MODES), the shared loss machinery
#: (LOSS_DETECTION, TRIMMING, ACKING) and the link layer (LLR).
SUBJECTS: tuple[str, ...] = (
    "PDS",  # PDS service interface / scope
    "DELIVERY_MODES",  # mode taxonomy, PDC-mode binding, message mapping
    "RUD",  # reliable unordered delivery services (3.5.20)
    "ROD",  # reliable ordered delivery services (3.5.21)
    "RODL",  # scale-up local variant services (3.5.22)
    "RUDI",  # idempotent reliable delivery (only what anchored spans state)
    "UUD",  # unreliable unordered delivery
    "LOSS_DETECTION",  # 3.5.15 machinery: RTO, early loss, probes
    "TRIMMING",  # 4.1 packet trimming + trimmed-packet processing
    "ACKING",  # ACK/NACK/CLEAR protocol semantics
    "LLR",  # link layer retry reliability (5.1/5.1.3)
)

#: Anchor ids this stage is allowed to cite (mechanism-to-anchor map, S1:
#: 3.5.3, 3.5.6, 3.5.15, 3.5.20, 3.5.21, 3.5.22, 5.1, 5.1.3, 4.1).
S3_ANCHOR_IDS: frozenset[str] = frozenset(
    {
        "UEC11-S3.5.3-PDS-SERVICES",
        "UEC11-S3.5.6-RELIABILITY-ORDERING",
        "UEC11-S3.5.15-LOSS-DETECTION",
        "UEC11-S3.5.20-RUD",
        "UEC11-S3.5.21-ROD",
        "UEC11-S3.5.22-RODL",
        "UEC11-S5.1-LLR",
        "UEC11-S5.1.3-LLR-OPERATION",
        "UEC11-S4.1-PACKET-TRIMMING",
    }
)

_REQUIREMENTS: tuple[UECRequirement, ...] = (
    # -- 3.5.3 packet delivery services (informative overview) ---------------
    UECRequirement(
        requirement_id="UEC11-RO-R01",
        anchor_ids=("UEC11-S3.5.3-PDS-SERVICES",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS processes packets, not messages: SES requests PDS to deliver "
            "each packet with specified ordering and reliability, and PDS "
            "provides those guarantees for packets passed from SES to the "
            "wire and from the wire to SES."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R02",
        anchor_ids=("UEC11-S3.5.3-PDS-SERVICES",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS offers both reliable and unreliable packet delivery and both "
            "ordered and unordered packet delivery; each UET profile defines "
            "which delivery modes and congestion management schemes are "
            "available."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R03",
        anchor_ids=("UEC11-S3.5.3-PDS-SERVICES",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS provides a connectionless interface to SES using dynamically "
            "established ephemeral PDCs, connectionless reliable delivery for "
            "idempotent operations via RUDI (which establishes no "
            "connection), and connection-oriented services via reserved PDCs "
            "configured by the user."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R04",
        anchor_ids=("UEC11-S3.5.3-PDS-SERVICES",),
        keyword="DEFINITIONAL",
        subject="ACKING",
        disposition="informational",
        statement=(
            "SES generates a response for every delivered packet; responses "
            "are carried in PDS ACK packets, and SES indicates which "
            "responses are guaranteed to be delivered."
        ),
    ),
    # -- 3.5.6 reliability and ordering taxonomy --------------------------------
    UECRequirement(
        requirement_id="UEC11-RO-R05",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        keyword="DEFINITIONAL",
        subject="DELIVERY_MODES",
        disposition="informational",
        statement=(
            "Five combinations of reliability and ordering define the packet "
            "delivery modes: RUD, ROD, RODL, RUDI, and UUD. The reliable "
            "modes RUD, ROD, and RODL are defined in the context of a "
            "dynamically established PDC; RUDI and UUD do not use PDCs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R06",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        keyword="DEFINITIONAL",
        subject="DELIVERY_MODES",
        disposition="informational",
        statement=(
            "A PDC's delivery mode remains the same for all packets on that "
            "PDC until it is closed; the delivery mode for a given SES "
            "request is determined by SES, and more than one PDC between a "
            "pair of FEPs is supported."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R07",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        keyword="DEFINITIONAL",
        subject="DELIVERY_MODES",
        disposition="informational",
        statement=(
            "There is no ordering guarantee across packets associated with "
            "different PDCs; applications that want large data transfers "
            "distributed across multiple PDCs must split them into multiple "
            "messages above SES."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R08",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        keyword="DEFINITIONAL",
        subject="DELIVERY_MODES",
        disposition="informational",
        statement=(
            "All packets of a single SES message are sent on the same PDC; "
            "PDS tracks som/eom so a message stays on one PDC and a PDC is "
            "not closed mid-message. Rendezvous and deferrable-send "
            "transactions comprise multiple messages that may use separate "
            "PDCs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R09",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        keyword="DEFINITIONAL",
        subject="DELIVERY_MODES",
        disposition="informational",
        statement=(
            "Packets from different messages are not interleaved on a single "
            "PDC: all packets of one message are on the wire before any "
            "packet of the next message. PDS may establish an additional PDC "
            "to avoid delaying short messages."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R10",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        keyword="DEFINITIONAL",
        subject="UUD",
        disposition="informational",
        statement=(
            "There is no acknowledgement for the unreliable delivery mode."
        ),
    ),
    # -- 3.5.15 loss detection and recovery --------------------------------------
    UECRequirement(
        requirement_id="UEC11-RO-R11",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="MUST",
        subject="LOSS_DETECTION",
        disposition="unsupported",
        statement=(
            "PDS must detect packet loss using the listed methods: trimming "
            "(a trim indicates loss and generates a NACK), NACK reception, "
            "and an RTO timer at the source set on transmit and cleared on "
            "ACK are all required."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R12",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="SHOULD",
        subject="LOSS_DETECTION",
        disposition="unsupported",
        statement=(
            "PDS should provide one or more early loss detection methods for "
            "requests and for ACKs that determine loss sooner than the RTO "
            "timer expires; the methods used are implementation specific."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R13",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "A trimmed packet must be identified by the value of its "
            "ip.dscp field; the IP length and the UDP length of a trimmed "
            "packet must not be verified; the UET CRC may be validated if "
            "present."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R14",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "For a trimmed packet that cannot be validated or authenticated, "
            "the trimmed-packet NACK rules must be used or the packet "
            "dropped; PDS header fields of trimmed packets are not used "
            "beyond NACK generation, except that a trimmed RUDI request is "
            "retransmitted; trimmed control packets are dropped."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R15",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Trimmed-packet NACK rules: trimmed RUD, ROD, RODL, and RUDI "
            "requests generate a NACK (UET_TRIMMED or UET_TRIMMED_LASTHOP); "
            "trimmed RUD and ROD ACKs trigger retransmission of the original "
            "request; a trimmed RUDI response triggers retransmission of the "
            "original RUDI request."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R16",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="MUST",
        subject="LOSS_DETECTION",
        disposition="unsupported",
        statement=(
            "A PDC must maintain an RTO timer (one timer per PDC), set to "
            "RTO_INIT_TIME when a packet is transmitted, and retransmit all "
            "associated unacknowledged packets when the timer expires."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R17",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="SHOULD",
        subject="LOSS_DETECTION",
        disposition="unsupported",
        statement=(
            "A PDC should maintain a timer or timestamp per outstanding "
            "packet and retransmit an unacknowledged packet when its timer "
            "expires; alternatively a per-PDC timer may be used."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R18",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="SHOULD",
        subject="LOSS_DETECTION",
        disposition="unsupported",
        statement=(
            "Exponential backoff between retry attempts should be provided "
            "until Max_RTO_Retx_Cnt is reached; a packet's RTO timer is "
            "restarted to its last value without exponential increase when a "
            "NACK is received for it, and may be suspended during a Probe CP "
            "transmission."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R19",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="DEFINITIONAL",
        subject="LOSS_DETECTION",
        disposition="informational",
        statement=(
            "Example early loss detection methods: OOO-based (out-of-order "
            "byte or PSN thresholds trigger a loss recovery mode), EV-based "
            "(per-entropy-value PSN slots), tail loss (Probe CP driven by a "
            "Tail_Loss_Timer), and receiver-based inference (NACK with code "
            "UET_RCVR_INFER_LOSS)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R20",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="DEFINITIONAL",
        subject="ACKING",
        disposition="informational",
        statement=(
            "Lost ACK packets can often be recovered by monitoring CACK_PSN; "
            "the exceptions are guaranteed-delivery ACKs and the last ACKs "
            "when the PDC goes idle."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R21",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="DEFINITIONAL",
        subject="ACKING",
        disposition="informational",
        statement=(
            "A lost ACK is inferred to carry a guaranteed-delivery response "
            "when the SACK bitmap shows the PSN arrived at the destination "
            "and CACK_PSN equals one less than that PSN."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R22",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="DEFINITIONAL",
        subject="ACKING",
        disposition="informational",
        statement=(
            "For ROD and RODL PDCs a lost ACK is inferred immediately from "
            "the next ACK because ACKs arrive in PSN order; for RUD the ACKs "
            "may arrive out of order, so a timer or ACK bitmap monitoring is "
            "used, with a timeout larger than network RTT plus SES "
            "processing."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R23",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        keyword="MUST",
        subject="ACKING",
        disposition="unsupported",
        statement=(
            "When the source determines an ACK is lost it must transmit an "
            "ACK Request CP or retransmit the original request packet; an "
            "ACK Request CP should be generated unless the missing ACK "
            "carries read response data."
        ),
    ),
    # -- 3.5.20 reliable unordered delivery ---------------------------------------
    UECRequirement(
        requirement_id="UEC11-RO-R24",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="DEFINITIONAL",
        subject="RUD",
        disposition="informational",
        statement=(
            "A RUD PDC is a reliable PDC between a single initiating FEP and "
            "a single target FEP that guarantees packets are delivered once "
            "and only once; PDCs are ephemeral, packets from multiple PIDs "
            "and send queues may share a PDC, and all packets of one message "
            "use a single PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R25",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="RUD",
        disposition="unsupported",
        statement=(
            "RUD must transmit PDS request packets as directed by the source "
            "SES and retransmit up to Max_RTO_Retx_Cnt times, must deliver "
            "each request packet to the destination SES once and only once, "
            "and must support selective retransmission."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R26",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="ACKING",
        disposition="unsupported",
        statement=(
            "The destination must generate ACK packets carrying SES "
            "responses; PDS accepts from SES a guaranteed-delivery "
            "indication per response, must store guaranteed-delivery "
            "responses (excluding read-response data) for ACK retransmission "
            "on a valid duplicate request, and must construct the default "
            "response to retransmit an ACK for a non-guaranteed PSN."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R27",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="ACKING",
        disposition="unsupported",
        statement=(
            "PDS must receive a clear indication for all PSNs with "
            "guaranteed-delivery responses before freeing the associated "
            "response; a stored response is freed when its PSN is cleared."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R28",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="ACKING",
        disposition="unsupported",
        statement=(
            "The source must send CLEAR_PSN to the destination in all PDS "
            "requests (encoded via the clear_psn_offset and psn fields) and "
            "upon a Clear Request CP (or a Clear Command CP carrying it in "
            "the payload); the destination must receive and process "
            "CLEAR_PSN."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R29",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="RUD",
        disposition="unsupported",
        statement=(
            "All read responses of a single message must be sent in the same "
            "direction; if a message is larger than Max_ACK_Data_Size, all "
            "its responses use the return direction even if the last packet "
            "carries less data."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R30",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="RUD",
        disposition="unsupported",
        statement=(
            "On receiving a duplicate request: a PSN outside the valid range "
            "(MP_RANGE) is dropped with no ACK; an in-range already-received "
            "PSN is marked as a retransmission (retx flag) to trigger an "
            "ACK; the target retransmits the stored guaranteed-delivery ACK "
            "or an ACK with the default response."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R31",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="RUD",
        disposition="unsupported",
        statement=(
            "On a PDS NACK (for example, no packet buffer), the request is "
            "dropped at the target; the source waits the configured time per "
            "NACK code and retransmits; if Max_NACK_Retx_Cnt is exceeded PDS "
            "declares an error and SES completes the packet and message in "
            "error."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R32",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="MUST",
        subject="RUD",
        disposition="unsupported",
        statement=(
            "The initiator is responsible for retrying when requests or ACKs "
            "are dropped in the network, even if the NACK itself is lost "
            "(RTO expiry triggers retransmission); ACK state is determined "
            "from CACK_PSN and the SACK bitmap."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R33",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="DEFINITIONAL",
        subject="RUD",
        disposition="informational",
        statement=(
            "Reads with the standard SES header carry a message ID that is "
            "unique per PDC (and should be globally unique across PDCs for "
            "efficient return-direction lookup); medium and small headers "
            "carry the original request PSN instead, in "
            "ses.original_request_psn."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R34",
        anchor_ids=("UEC11-S3.5.20-RUD",),
        keyword="DEFINITIONAL",
        subject="ACKING",
        disposition="informational",
        statement=(
            "CLEAR_PSN is automatically incremented when a PSN needs no "
            "guaranteed delivery; no clear is required when ACK_PSN equals "
            "CACK_PSN; PSN state may be freed once all lower PSNs are in "
            "clear state."
        ),
    ),
    # -- 3.5.21 reliable ordered delivery ------------------------------------------
    UECRequirement(
        requirement_id="UEC11-RO-R35",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="DEFINITIONAL",
        subject="ROD",
        disposition="informational",
        statement=(
            "A ROD PDC is a reliable PDC between a single initiating FEP and "
            "a single target FEP; packets from multiple PIDs and send queues "
            "may share the PDC, and all packets from a single message use a "
            "single ROD PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R36",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST NOT",
        subject="ROD",
        disposition="unsupported",
        statement="Messages must not be interleaved on a ROD PDC.",
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R37",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "ROD must operate on a single network path (a single entropy "
            "value) so packets arrive in transmit order; packets within a "
            "message must be transmitted in order, and the source must "
            "transmit in the order packets were posted to a common send "
            "queue; no ordering is required across separate send queues."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R38",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "ROD must support GoBackN retransmission and must guarantee that "
            "each packet is delivered to the target SES once and only once "
            "in the order of arrival."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R39",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ACKING",
        disposition="unsupported",
        statement=(
            "ROD ACKs must be transmitted in the same order as the packets "
            "they ACK, using the entropy value of the request; ROD read "
            "responses must be transmitted on the wire in the same order as "
            "the corresponding requests."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R40",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="DEFINITIONAL",
        subject="ROD",
        disposition="informational",
        statement=(
            "There are no ordering requirements between PDS ACKs on the "
            "forward direction and read responses on the return direction; "
            "an ACK may be sent and arrive out of order when explicitly "
            "requested (duplicate packet or ACK request CP)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R41",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "A packet received with an out-of-order PSN (not last received "
            "PSN plus one) must be dropped and a NACK generated with "
            "nack_code UET_ROD_OOO, nack_psn set to the out-of-order PSN, "
            "and the payload carrying Expected_PSN; this applies in both "
            "directions."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R42",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "For an in-order packet NACKed for a reason other than an "
            "out-of-order PSN, the NACK carries the corresponding nack_code, "
            "the payload carries Expected_PSN (except UET_NEW_START_PSN), "
            "and nack_psn is the PSN being NACKed, in both directions."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R43",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "On a NACK indicating new packet loss, the source must stop "
            "transmitting higher-PSN packets on the PDC and apply GoBackN: "
            "retransmit all packets starting from the Expected_PSN in the "
            "NACK payload."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R44",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="DEFINITIONAL",
        subject="ROD",
        disposition="informational",
        statement=(
            "NACK classification at the source: an arriving ACK completes "
            "the GoBackN event; NACKs with payload equal to Expected_PSN and "
            "retx=0 belong to the current event; payload beyond "
            "Expected_PSN with retx=0 indicates new loss; retx=1 NACKs mean "
            "retransmitted packets were lost, the first triggering a new "
            "GoBackN."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R45",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "When loss of an ACK with a non-guaranteed response is detected "
            "via CACK_PSN, the PDC must infer a default-response-based "
            "CACK_PSN from the next arriving packet; if the last ACK is "
            "lost with insufficient information, an RTO expiry triggers an "
            "ACK Request CP or retransmission of the original request."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R46",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "When loss of a guaranteed-delivery ACK is detected, one of "
            "three actions must be taken: generate an ACK Request CP "
            "(recommended unless the packet was a read request), retransmit "
            "the original request if it was a read, or fall back to GoBackN "
            "from the missing PSN (least efficient)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R47",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="MUST",
        subject="ROD",
        disposition="unsupported",
        statement=(
            "Because higher-PSN packets may continue while an ACK Request CP "
            "or retransmitted request is outstanding, a destination ROD PDC "
            "must process duplicate packets even though their PSN is out of "
            "order, and must support retransmitting a guaranteed-delivery "
            "ACK when a duplicate PSN arrives out of order."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R48",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        keyword="DEFINITIONAL",
        subject="ROD",
        disposition="informational",
        statement=(
            "ROD standard sequences are the same as RUD except packets "
            "always arrive in order; the PDC tracks the next Expected_PSN, "
            "the last received PSN plus one. On a NACK event the destination "
            "drops all packets beyond the NACKed PSN and the source "
            "retransmits from it."
        ),
    ),
    # -- 3.5.22 reliable ordered delivery for local networks -----------------------
    UECRequirement(
        requirement_id="UEC11-RO-R49",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="DEFINITIONAL",
        subject="RODL",
        disposition="informational",
        statement=(
            "RODL is a variation of ROD optimized for scale-up networks: a "
            "reliable PDC between a pair of FEPs. It runs over a "
            "bidirectional PDC so targets may initiate send, write, or "
            "atomic requests, and only the initiator closes a PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R50",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="DEFINITIONAL",
        subject="RODL",
        disposition="informational",
        statement=(
            "RODL can be implemented without PDS retransmission, saving "
            "state at the trade-off that packet loss closes the PDC; "
            "requests in one direction may carry the CACK_PSN for the other "
            "direction (reverse ACKs) in lieu of ACK packets, or normal ACK "
            "packets may be used."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R51",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "If a packet is lost on a RODL PDC that does not support "
            "retransmission, the PDC must be closed in error; a "
            "retransmit-less PDC that loses or corrupts a packet drops and "
            "completes in error all outstanding messages after the lost "
            "packet."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R52",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "Without retransmission, the target returns a NACK for the "
            "missing PSN and every packet that arrives thereafter (excluding "
            "a Close Command CP), with nack_code UET_UNEXP_EVENT, and "
            "CACK_PSN does not advance beyond the missing PSN minus one."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R53",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "On this loss event the initiator sends a Close Command CP; the "
            "target responds with an ACK and closes the PDC, accepting the "
            "Close Command despite its out-of-order PSN, and both sides "
            "ignore the maximum PSN range for it."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R54",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "On a bidirectional PDC, before requesting the initiator to "
            "close, the target must wait until all transactions it initiated "
            "(including clear processing) complete; when the close command "
            "arrives, the target must complete all active transactions "
            "before acknowledging it."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R55",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="DEFINITIONAL",
        subject="RODL",
        disposition="informational",
        statement=(
            "If two FEPs simultaneously create PDCs between each other, both "
            "PDCs may remain open; RODL standard sequences are the same as "
            "ROD, and lost ACKs are handled as in ROD."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R56",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "ACK packets must be supported (they carry stateful responses "
            "including read data, fetching atomic data, and error state), "
            "the generation of NACK packets must be supported, and accepting "
            "and processing received ACK and NACK packets must be supported."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R57",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "Stateful responses must be transported in an ACK packet; "
            "success responses of writes and non-fetching atomics on a "
            "bidirectional PDC are default responses that can be messaged "
            "via the reverse CACK_PSN field, removing the need for ACK "
            "packets while traffic flows both ways."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R58",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "Both initiator and target maintain full 32-bit PSN, CLEAR_PSN, "
            "and CACK_PSN (as in ROD), with lower bits carried on the wire; "
            "the receiver monitors wrap of the CACK_PSN field and updates "
            "the upper bits."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R59",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "If no request or response is pending and a PDC needs to update "
            "CLEAR_PSN or CACK_PSN, an implementation must send an ACK or a "
            "control packet to exchange this state."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R60",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "For lossless operation (for example CBFC or PFC with LLR) with "
            "deadlock avoidance, responses must use a different traffic "
            "class than requests; ACKs and NACKs are mapped to a second "
            "traffic class distinct from PDS requests and control packets."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R61",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="MUST",
        subject="RODL",
        disposition="unsupported",
        statement=(
            "In the bidirectional lossless configuration Max_ACK_Data_Size "
            "must be set to match the Payload MTU so all response data is "
            "carried in acknowledgements; ACK packets carry response data "
            "for read and fetching atomic operations."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R62",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="DEFINITIONAL",
        subject="RODL",
        disposition="informational",
        statement=(
            "RODL uses GoBackN like ROD when retransmission is supported; "
            "error sequences equal ROD's with retransmission enabled, and a "
            "dropped request without retransmission is a fatal PDC error."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R63",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="DEFINITIONAL",
        subject="RODL",
        disposition="informational",
        statement=(
            "Over UFH_16, RODL compresses the PDS header: 3-bit flags, "
            "24-bit psn_state, 12-bit PDCIDs, 2-bit pdc_info; the 32-bit PSN "
            "is carried implicitly in the CRC once the PDC is established "
            "(24 least significant bits in psn_state during establishment, "
            "start-PSN upper bits zero), limiting outstanding packets per "
            "RODL PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R64",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        keyword="DEFINITIONAL",
        subject="RODL",
        disposition="informational",
        statement=(
            "RODL does not support NSCC or packet trimming, does not support "
            "ACK_CC, ACK_CCX, or NACK_CCX, and supports ACK and NACK."
        ),
    ),
    # -- 4.1 packet trimming (loss signal) -----------------------------------------
    UECRequirement(
        requirement_id="UEC11-RO-R65",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="DEFINITIONAL",
        subject="TRIMMING",
        disposition="informational",
        statement=(
            "Packet trimming is the switch response to buffer shortage: the "
            "switch trims the packet payload and forwards the resulting "
            "header to the destination in a different traffic class; sending "
            "the trimmed packet back toward the source is not part of the "
            "specification."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R66",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Trimming must only be performed on valid IP packets that fail "
            "buffer admission checks; when an incoming trimmable-DSCP packet "
            "fails admission the switch must trim it, and the trimmed packet "
            "size must not be larger than the original packet."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R67",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="SHALL",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Only packets in the trimmable DSCP category shall be trimmed; "
            "each of the trimmable and trimmed categories must include at "
            "least one DSCP value, and the specification places no "
            "constraints on the values used."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R68",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "The network operator must configure a mapping from every "
            "trimmable DSCP to a trimmed DSCP codepoint; multiple trimmable "
            "codepoints may map to the same trimmed codepoint; after "
            "trimming the switch must set the DSCP to the associated "
            "trimmed codepoint."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R69",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Trimming reduces the IP payload to at least MIN_TRIM_SIZE, a "
            "network-wide configuration parameter; for UET it must be large "
            "enough to keep the headers needed to identify the packet: path "
            "entropy, tunnel encapsulation, PSN, and PDC identifiers."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R70",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "A trimmed packet must remain a valid IP packet: the switch "
            "updates the IP total length and header checksum, and the "
            "Ethernet FCS must also be updated to be valid; TTL processing "
            "of a trimmed packet is unchanged."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R71",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "The trimmed packet must be treated as a new incoming packet of "
            "the trimmed DSCP for subsequent processing at the trimming "
            "switch, following the normal queue-overflow procedure if that "
            "queue's admission fails (typically drop)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R72",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MAY",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "A trimmable packet smaller than MIN_TRIM_SIZE that fails "
            "admission may be treated as trimmed (DSCP updated, length "
            "unchanged) or may be dropped; transports should instead mark "
            "small packets non-trimmable because trimming them yields "
            "little data reduction."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R73",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="SHOULD NOT",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "A switch should not perform ECN marking on trimmed packets; "
            "trimming does not change the ECN bits, so trimmed packets "
            "carry the original packet's ECN bits, which remain useful for "
            "congestion control."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R74",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="DEFINITIONAL",
        subject="TRIMMING",
        disposition="informational",
        statement=(
            "Trimming is not a guaranteed notification: a trimmed packet "
            "may still be lost at the trimming switch, at downstream "
            "switches, or at the destination; transport protocols must "
            "implement loss detection mechanisms such as timeouts as a "
            "backstop."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R75",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="SHOULD",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "A trimmed packet should follow the same network path as the "
            "associated original packet, although switches may select "
            "different paths for trimmed packets to the same destination."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R76",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="SHOULD NOT",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Trimmed packets should not be forwarded outside the backend, "
            "datacenter, or enterprise network, and networks should prevent "
            "destinations that do not support trimming from receiving "
            "trimmed packets."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R77",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="SHOULD NOT",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Packet trimming should not change any upper-layer header "
            "fields beyond the outer IP header."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R78",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="MUST",
        subject="TRIMMING",
        disposition="unsupported",
        statement=(
            "Upper-layer protocols must be trimming-aware when trimming is "
            "enabled and must identify the original packet from the trimmed "
            "one; a trimmed packet given to the FEP must carry the trimmed "
            "DSCP regardless of intermediate encapsulations, and with IPv4 "
            "the header checksum must be valid."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R79",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        keyword="DEFINITIONAL",
        subject="TRIMMING",
        disposition="informational",
        statement=(
            "Specified UET MIN_TRIM_SIZE values: 20 B for UET over IP, 24 B "
            "over UDP/IP, 70 B for UET/IPv4 over VXLAN, 74 B for "
            "UET/UDP/IPv4 over VXLAN, and 94 B for UET/UDP/IPv6 over VXLAN; "
            "add 16 B when security is enabled; with multiple encapsulation "
            "types, the maximum applies."
        ),
    ),
    # -- 5.1 / 5.1.3 link layer retry reliability -----------------------------------
    UECRequirement(
        requirement_id="UEC11-RO-R80",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR is frame-based link-level reliability: eligible frames "
            "carry a link sequence number and are held in a replay buffer; "
            "LLR_ACKs free replay space, LLR_NACKs signal missing frames, "
            "and timer expiry guarantees replay; pause and PFC frames are "
            "always LLR-ineligible."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R81",
        anchor_ids=("UEC11-S5.1.3-LLR-OPERATION",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR uses four control ordered sets — LLR_ACK, LLR_NACK, "
            "LLR_INIT, LLR_INIT_ECHO — inserted pre-emptively by the PCS, "
            "oblivious to data frames; this bounds control-message latency "
            "and guarantees their bandwidth; each carries a 20-bit sequence "
            "number (INIT types also 16-bit init data)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R82",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "The LLR transmit state machine has OFF, INIT, ADVANCE, REPLAY, "
            "and FLUSH states: ADVANCE is normal operation, REPLAY is "
            "entered on NACK or replay-timer expiry, and FLUSH is entered "
            "on PCS status loss, data-age expiry, or exhausting replay "
            "attempts."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R83",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "In the INIT and FLUSH states the transmit LLR handles frames "
            "per configured behavior: DISCARD (counted), BLOCK (guarantees "
            "lossless delivery by not accepting frames), or BEST_EFFORT "
            "(frames pass unprotected as LLR-ineligible); after replay "
            "failure, re_init_on_discard TRUE re-initializes, FALSE waits "
            "for management."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R84",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "The transmit LLR will not accept a new eligible frame unless "
            "the state machine is in ADVANCE, outstanding_seq is below "
            "outstanding_seq_max, outstanding_data is below "
            "outstanding_data_max, and replay-buffer space exists for the "
            "entire frame — eligible frames are never truncated."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R85",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="SHOULD",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "outstanding_seq counts unacknowledged frames as (tx_seq - 1 - "
            "acked_seq) mod 2^20 and outstanding_data their byte total; "
            "outstanding_data_max should be set to the link "
            "bandwidth-delay product so the pause and PFC mechanisms "
            "operate correctly."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R86",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "outstanding_seq_max must not exceed 524288 (half the 20-bit "
            "sequence-number space); an implementation may support "
            "considerably less, and configuring a value above its own "
            "maximum is not allowed."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R87",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "On receiving an LLR_NACK the transmitter completes any "
            "in-flight frame, then enters REPLAY and replays eligible "
            "frames from the buffer; new ineligible frames may be "
            "transmitted during REPLAY (recommended for time-sensitive "
            "frames); replay-timer expiry with attempts remaining also "
            "triggers REPLAY."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R88",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "In the FLUSH state the LLR discards all replay-buffer frames "
            "without transmitting them; exceeding replay_ct_max (255 means "
            "no maximum) or pcs_lost_status_timer or data_age_timer expiry "
            "leads to FLUSH."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R89",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "The replay timer is held at zero while no frames are "
            "outstanding, activated at the end of each new or replayed "
            "frame, cleared by an ACK or NACK that acknowledges buffered "
            "frames, and re-armed while frames remain outstanding; it "
            "should resolve better than 10 ns and count about ten expected "
            "round trips."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R90",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "The data_age_timer bounds how long data may sit in the replay "
            "buffer without acknowledgment progress and discards it on "
            "expiry regardless of replay count; the pcs_lost_status_timer "
            "moves the state machine to FLUSH when link status has been "
            "false too long."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R91",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "LLR_ACKs and LLR_NACKs carry the sequence number of the most "
            "recent successfully received eligible frame (FCS good or "
            "poisoned and expected); a missing frame or an expected frame "
            "with bad FCS triggers exactly one LLR_NACK, with no further "
            "ACKs or NACKs until an expected frame with good or poisoned "
            "FCS resumes ACKing."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R92",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "The ACK/NACK transmit state machine has OFF, SEND_ACKS, "
            "SEND_NACK, and NACK_SENT states: in SEND_ACKS an ACK "
            "(next_rx_seq minus one) is sent at each control-ordered-set "
            "opportunity; SEND_NACK sends a single NACK; nothing is sent in "
            "NACK_SENT."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R93",
        anchor_ids=("UEC11-S5.1.3-LLR-OPERATION",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "The LLR must transmit LLR_ACK/LLR_NACK control ordered sets at "
            "a rate between once every 400 bytes and once every 17296 bytes "
            "(except in NACK_SENT); a CtlOS shall not be inserted within "
            "the first 256 bytes of a frame, and two CtlOS in one frame "
            "must be at least 2 KB apart."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R94",
        anchor_ids=("UEC11-S5.1-LLR", "UEC11-S5.1.3-LLR-OPERATION"),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "Receive-path classification: expected_frame requires the "
            "sequence number to equal next_rx_seq; a frame behind within "
            "524288 is duplicate_frame; a frame ahead is missing_frame; "
            "when LLR is ON, eligible frames with expected_frame false are "
            "filtered by the receive LLR."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R95",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "Received ACK/NACK sequence numbers are validated by the window "
            "equation; a failed check increments an error counter, while a "
            "valid newly acknowledged number releases all replay-buffer "
            "frames up to and including it; a NACK sets nack_received and "
            "an ACK clears it."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R96",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "A lost LLR_ACK is tolerable — the next LLR_ACK updates the "
            "acknowledged sequence and the buffer empties; a lost LLR_NACK "
            "means the transmitter keeps sending new frames until the "
            "replay timer expires, and that data is discarded."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R97",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "Initialization: LLR_INIT carries init_seq (equal to tx_seq) "
            "and optional init_data that the receiver must echo in "
            "LLR_INIT_ECHO; the receiver sets next_rx_seq from init_seq; "
            "reception of an INIT_ECHO whose init_seq equals tx_seq exits "
            "the INIT state; INIT is repeated to tolerate loss."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R98",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "Control ordered-set transmission priority is LLR_INIT_ECHO "
            "above LLR_INIT above ACK/NACK; ACK and NACK have equal "
            "priority; with CBFC active, round-robin arbitration is "
            "recommended to avoid starving either."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R99",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "Error propagation: the MAC poisons the FCS of eligible frames "
            "whose data is irrecoverably bad; a poisoned FCS does not "
            "trigger a NACK or replay — the frame advances the sequence "
            "like a good frame — and the frame_bad flag informs the MAC "
            "client for poisoned or bad FCS."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R100",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR_status passes PCS status through unchanged when LLR is "
            "off; when enabled it is true in the ADVANCE and REPLAY states "
            "and false otherwise, and the link stays up during replays "
            "over a PCS loss-of-alignment event."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-RO-R101",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR defines counters including transmitted and received INIT, "
            "INIT_ECHO, ACK, and NACK control ordered sets, tx_ok, "
            "tx_poisoned, tx_discard, tx_replay, rx_ok, and "
            "rx_ack_nack_seq_error."
        ),
    ),
)

_FREE_PARAMETERS: tuple[UECFreeParameter, ...] = (
    UECFreeParameter(
        parameter_id="UEC11-RO-F01",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        name="early_loss_detection_method",
        freedom=(
            "Which early loss detection method(s) a PDS implements for "
            "requests is implementation specific; OOO-based, EV-based, tail "
            "loss (Probe CP), and receiver-based inference are spec "
            "examples, and only the capability itself is SHOULD."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F02",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        name="ack_loss_detection_method",
        freedom=(
            "Which method(s) detect a lost ACK sooner than the RTO timer "
            "are implementation specific; CACK_PSN monitoring, ACK "
            "bitmaps, and timers are the given examples."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F03",
        anchor_ids=("UEC11-S3.5.15-LOSS-DETECTION",),
        name="rto_init_time_value",
        freedom=(
            "RTO_INIT_TIME is programmable between 0 microseconds and 8 "
            "seconds; the chosen value is a deployment decision (the range "
            "and the exponential-backoff behavior are spec-fixed, the value "
            "is not)."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F04",
        anchor_ids=("UEC11-S3.5.20-RUD", "UEC11-S3.5.15-LOSS-DETECTION"),
        name="retry_count_limits",
        freedom=(
            "Max_RTO_Retx_Cnt and Max_NACK_Retx_Cnt are configuration "
            "parameters; the spec fixes only the behavior on exceeding them "
            "(PDS declares an error and SES completes packet and message in "
            "error), not their values."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F05",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        name="multi_pdc_criteria",
        freedom=(
            "The criteria for when to establish multiple PDCs between a "
            "pair of FEPs are implementation specific; PDS may open an "
            "additional PDC to avoid delaying short messages."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F06",
        anchor_ids=("UEC11-S3.5.6-RELIABILITY-ORDERING",),
        name="rendezvous_deferrable_pdc_mapping",
        freedom=(
            "How rendezvous (eager portion versus rest of message) and "
            "deferrable send (RTR initiated by the target, restarted "
            "message) map packets onto separate PDCs is implementation "
            "specific."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F07",
        anchor_ids=("UEC11-S3.5.21-ROD",),
        name="rod_deep_retransmit_handling",
        freedom=(
            "Handling of ROD packets that require more than three "
            "transmissions (initial, retransmit after retx=0 NACK, again "
            "after retx=1 NACK) is implementation specific: RTO fallback or "
            "additional tracked state are the named options."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F08",
        anchor_ids=("UEC11-S3.5.22-RODL",),
        name="rodl_retransmission_support",
        freedom=(
            "Whether a RODL PDC supports PDS retransmission (GoBackN) or "
            "runs retransmit-less, where any packet loss is fatal and "
            "closes the PDC in error, is an implementation/deployment "
            "option the spec explicitly allows."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F09",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        name="dscp_trim_values",
        freedom=(
            "The trimmable and trimmed DSCP values and their operator "
            "mapping are unconstrained by the spec (examples: trimmable "
            "{1,2,3} to trimmed {4,5,6}); only the categories and at-least-"
            "one-value-per-category are fixed."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F10",
        anchor_ids=("UEC11-S4.1-PACKET-TRIMMING",),
        name="min_trim_size_configuration",
        freedom=(
            "MIN_TRIM_SIZE is a network-wide configuration parameter "
            "depending on the transport and tunneling protocols used; the "
            "Table 4-1 values are per-encapsulation lower bounds and "
            "switches may dynamically determine the size per encapsulation "
            "type."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F11",
        anchor_ids=("UEC11-S5.1-LLR",),
        name="llr_timer_and_window_config",
        freedom=(
            "LLR configuration is deployment-chosen: replay_timer_max, "
            "replay_ct_max, data_age_timer_max, pcs_lost_status_timer_max, "
            "ctlos_target_spacing (400-16384, suggested 2048), and the "
            "supported outstanding_seq_max (at most 524288, may be "
            "considerably lower depending on sublayer delays, link length, "
            "and minimum frame size)."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-RO-F12",
        anchor_ids=("UEC11-S5.1-LLR",),
        name="llr_init_flush_behavior",
        freedom=(
            "How the transmit LLR treats frames in the INIT and FLUSH "
            "states (DISCARD, BLOCK, or BEST_EFFORT) and whether it "
            "re-initializes after replay failure (re_init_on_discard) are "
            "configurable behaviors."
        ),
    ),
)


def requirements() -> tuple[UECRequirement, ...]:
    """All reliability & ordering requirement objects of this stage."""
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
            f"UEC reliability & ordering semantic objects failed validation: "
            f"{detail}{more}"
        )
