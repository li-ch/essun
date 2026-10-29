"""UEC 1.1 congestion management semantics: stage S4 semantic objects (T010/T011).

Fourth slice of the UEC semantic profile ladder: the congestion management
sublayer (CMS, section 3.6) and the network-layer congestion signaling
protocol (CSIG, section 4.2) — i.e. the "UET CMS" mechanism family: the
congestion control context (CCC) machinery (3.6.6-3.6.12), the NSCC window
algorithm (3.6.13), the RCCC receiver-credit algorithm (3.6.14, its
pull-credit side shared with S5), multipath path selection (3.6.16), switch
configuration and programmable congestion management (3.6.17-3.6.18), and the
CSIG in-band telemetry protocol incl. profiles and signals (4.2/4.2.7/4.2.9).
TFC (3.6.15) is S5's anchor and is deliberately not cited here.

Object model, vocabularies and validation follow the S2/S3 pattern
(:mod:`essun.specir.uec_link_transport` is the single source of truth for
the dataclasses and :data:`NORMATIVE_KEYWORDS`/:data:`MAX_STATEMENT_WORDS`):
every object is a mapping ``requirement id -> anchor ids -> typed statement``
(provenance rule).  Keywords are typed exactly as the spec text carries
them (spec "REQUIRED" is typed MUST, "NOT RECOMMENDED" as SHOULD NOT);
``DEFINITIONAL`` marks load-bearing structure/algorithm facts stated without
an RFC-2119 keyword — heavy in the pseudocode sections.  Free parameters are
always ``domain="FREE"``.

Statements are paraphrases in our own words (S0 license gate: verbatim spec
text in git remains only the S1 registry's <= 30-word quotes).  Anchors are
section-scoped per the S2/S3 method notes: an anchor pins its section's entry
page/hash; statements may be drawn from the section's full page span, and
subsections without a dedicated anchor cite the parent-section anchor
(e.g. the 3.6 anchor p439 also grounds 3.6.1-3.6.12 pp. 439-476 and
3.6.17-3.6.18 pp. 514-547; the 4.2 anchor p600 grounds 4.2.1-4.2.6,
4.2.8 and 4.2.10).  Dangling anchors are hard errors
(:func:`check_against_registry` / :func:`assert_valid`).
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

#: Subjects a stage-S4 statement can bind.  UET_CC is the solution-wide
#: scope/goals/deployment constraints; TELEMETRY the network signals
#: (3.6.4.1-3.6.4.4); TRAFFIC_CLASS the DSCP/TC mappings (3.6.4.5-3.6.4.7);
#: CCC the congestion control context machinery incl. headers and event
#: processing (3.6.6-3.6.12); NSCC/RCCC/MULTIPATH the three algorithms;
#: SWITCH the switch configuration (3.6.17); PCM the programmable congestion
#: management framework (3.6.18); CSIG the congestion signaling protocol (4.2).
SUBJECTS: tuple[str, ...] = (
    "UET_CC",  # congestion management solution: scope, goals, constraints
    "TELEMETRY",  # ECN, RTT/service time, trimming as congestion signal
    "TRAFFIC_CLASS",  # DSCP codepoints and traffic-class mappings
    "CCC",  # congestion control context: states, API, headers, events
    "NSCC",  # network signal-based congestion control (3.6.13)
    "RCCC",  # receiver-credit congestion control (3.6.14)
    "MULTIPATH",  # multipath path selection / entropy management (3.6.16)
    "SWITCH",  # switch configuration for UET-CC (3.6.17)
    "PCM",  # programmable congestion management (3.6.18)
    "CSIG",  # congestion signaling protocol (4.2)
)

#: Anchor ids this stage is allowed to cite (mechanism-to-anchor map, S1:
#: 3.6, 3.6.13, 3.6.14, 3.6.16, 4.2, 4.2.7, 4.2.9).  3.6.15 (TFC) is S5's.
S4_ANCHOR_IDS: frozenset[str] = frozenset(
    {
        "UEC11-S3.6-CMS",
        "UEC11-S3.6.13-NSCC",
        "UEC11-S3.6.14-RCCC",
        "UEC11-S3.6.16-MULTIPATH",
        "UEC11-S4.2-CSIG",
        "UEC11-S4.2.7-CSIG-PROFILES",
        "UEC11-S4.2.9-CSIG-SIGNALS",
    }
)

_REQUIREMENTS: tuple[UECRequirement, ...] = (
    # -- 3.6 CMS scope and algorithm set --------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R01",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="UET_CC",
        disposition="informational",
        statement=(
            "UET-CC is the end-to-end congestion management solution for "
            "packet-buffer congestion in best-effort (lossy) Ethernet "
            "backend networks, targeting efficiency, low loss, minimal "
            "tail latency and reasonable fairness; it assumes base RTTs "
            "of 1 to 20 microseconds and recommends all traffic sharing "
            "its traffic class run UET-CC, with non-UET control traffic "
            "separate."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R02",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="UET_CC",
        disposition="informational",
        statement=(
            "The Unified Local profile and the RODL delivery mode do not "
            "require support for congestion management."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R03",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="UET_CC",
        disposition="informational",
        statement=(
            "Congestion management decomposes into four components: "
            "telemetry collected at endpoints and in the network, a "
            "sender-based window bounding outstanding unacknowledged bytes, "
            "receiver-credit congestion control pacing transmission per "
            "destination (incast control), and multipath path selection via "
            "adaptive packet spraying at packet granularity."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R04",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="UET_CC",
        disposition="unsupported",
        statement=(
            "Of the three congestion control algorithms for best-effort "
            "networks, Network Signal Congestion Control (NSCC) must be "
            "implemented; Receiver-Credit Congestion Control (RCCC) is "
            "optional and may run with NSCC or stand-alone; Transport Flow "
            "Control (TFC) is an optional point-to-point flow-controlled "
            "channel mechanism."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R05",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="UET_CC",
        disposition="informational",
        statement=(
            "UET-CC design targets are network congestion, incast at the "
            "target, bulk-data messaging larger than one BDP, and "
            "moderate-bandwidth interfering flows, plus TFC for "
            "point-to-point protocols; lossless networks are specifically "
            "not covered by the initial design."
        ),
    ),
    # -- 3.6.4 telemetry --------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R06",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "The only required in-network telemetry is ECN marking; support "
            "for packet trimming is required of UET-CC endpoints but "
            "optional to support or enable in UE switches; endpoint "
            "telemetry such as end-to-end latency and dropped-packet state "
            "is also part of the model."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R07",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "ECN must be supported by UE-compliant endpoints and switches; "
            "switches must support using instantaneous queue depth when "
            "deciding to ECN-mark; when NSCC or ECN-based load balancing is "
            "enabled all UET data packets must be marked ECN-capable "
            "(ECT), otherwise setting ECT is optional; switches should mark "
            "on dequeue, which the NSCC algorithm assumes."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R08",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "The destination is required to measure its service delay "
            "(request arrival to ACK transmission) and report it in ACK "
            "packets in pds.ack_cc_state.service_time; the source "
            "subtracts service time from the measured ACK round trip to "
            "estimate the actual network RTT."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R09",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "UET ACKs, NACKs and control packets should use a higher-priority "
            "traffic class than data packets so return-path congestion is "
            "not misread as forward congestion; service time uses 128 ns "
            "units with an accuracy goal near 500 ns, and implementations "
            "should keep timestamps precise enough to meet that goal."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R10",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "UE FEPs must be capable of receiving trimmed data packets "
            "(identified by ip.dscp) and generating NACKs for them, while "
            "trimming in switches is optional; when used with UET-CC, "
            "MIN_TRIM_SIZE must be configured large enough to keep the UET "
            "PDS request header and any optional CC_State under all "
            "encapsulations."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R11",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MAY",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "A last-hop trim may use a distinct codepoint "
            "DSCP_TRIMMED_LASTHOP; the receiving FEP processes it like a "
            "trimmed packet except it is not an input to load balancing "
            "(no alternate path) and is not used as an NSCC congestion "
            "signal when RCCC is enabled, since RCCC manages last-hop "
            "congestion itself; switches treat it like DSCP_TRIMMED."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R12",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD NOT",
        subject="TELEMETRY",
        disposition="unsupported",
        statement=(
            "Mixing trimmable and non-trimmable data packets within one PDC "
            "is not recommended: either all packets of a PDC (and "
            "preferably of all sprayed PDCs in a traffic class) are marked "
            "trimmable or none are; mixing PDCs in one network requires "
            "care to avoid unfair sharing."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R13",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD NOT",
        subject="UET_CC",
        disposition="unsupported",
        statement=(
            "UET-CC is designed for best-effort operation and assumes PFC "
            "and CBFC are not enabled for end-to-end UET traffic on "
            "switch-to-switch links; PFC should not be used anywhere in a "
            "best-effort network and CBFC should not be used anywhere in a "
            "best-effort network, as flow control violates the CC latency "
            "assumptions."
        ),
    ),
    # -- 3.6.4.7 traffic classes -------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R14",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="TRAFFIC_CLASS",
        disposition="informational",
        statement=(
            "UET-CC operates with two or three traffic classes, each with "
            "independent buffering, ECN marking, trimming and scheduling; "
            "packets are mapped by DSCP using between two and six abstract "
            "DSCP names (for example DSCP_TRIMMABLE, DSCP_CONTROL) whose "
            "concrete values are assigned per network and UET traffic "
            "class."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R15",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="TRAFFIC_CLASS",
        disposition="informational",
        statement=(
            "Without trimming, PDS requests (RUD, ROD, RUDI) and RUDI read "
            "responses use DSCP_NO_TRIM, while ACKs, NACKs, control packets "
            "and RUDI send/write responses use DSCP_CONTROL (control "
            "packets may use DSCP_NO_TRIM when sequencing behind data is "
            "needed); a third codepoint DSCP_TRIMMABLE_RTX may separate "
            "retransmitted requests."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R16",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="TRAFFIC_CLASS",
        disposition="informational",
        statement=(
            "With trimming enabled, PDS requests (RUD, ROD, RODL, RUDI) and "
            "RUDI read responses are trimmable (DSCP_TRIMMABLE), ACKs at "
            "least Trimmable_ACK_Size large are trimmable while smaller "
            "ACKs, NACKs and RUDI send/write responses use DSCP_CONTROL, "
            "trimmed packets carry DSCP_TRIMMED, and last-hop trims may "
            "carry DSCP_TRIMMED_LASTHOP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R17",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="TRAFFIC_CLASS",
        disposition="unsupported",
        statement=(
            "In best-effort networks TC_high should receive priority over "
            "TC_med and TC_med over TC_low (scheduling mechanism "
            "implementation-specific); low-rate TC_high traffic should see "
            "very small queuing delay regardless of TC_med/TC_low load, "
            "and low-rate TC_med traffic should not be significantly "
            "delayed by TC_low."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R18",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="TRAFFIC_CLASS",
        disposition="informational",
        statement=(
            "Recommended best-effort DSCP-to-TC mapping: DSCP_CONTROL to "
            "TC_high; DSCP_TRIMMED and DSCP_TRIMMED_LASTHOP to TC_high "
            "(two-TC) or TC_med (three-TC); DSCP_TRIMMABLE, "
            "DSCP_TRIMMABLE_RTX and DSCP_NO_TRIM to TC_low."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R19",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="TRAFFIC_CLASS",
        disposition="unsupported",
        statement=(
            "RUDI packets are not controlled by UET-CC, and RUDI carrying "
            "substantial bandwidth to a destination should be mapped to a "
            "separate traffic class whose configuration is "
            "network-specific."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R20",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="TRAFFIC_CLASS",
        disposition="unsupported",
        statement=(
            "Retransmitted packets should not be placed in DSCP_CONTROL "
            "(it delays control packets and confuses the congestion "
            "loop); using DSCP_TRIMMABLE_RTX is optional, and switches "
            "should be configured with a higher trim threshold for it "
            "than for DSCP_TRIMMABLE or DSCP_NO_TRIM to protect "
            "retransmissions."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R21",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="TRAFFIC_CLASS",
        disposition="unsupported",
        statement=(
            "In lossless networks two traffic classes should be used: all "
            "UET requests mapped to TC_request and return-direction "
            "packets (ACK/NACK and RUDI responses) to TC_response, so that "
            "pausing requests can never pause responses and deadlock is "
            "avoided; control packets map by type per Table 3-88."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R22",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="TRAFFIC_CLASS",
        disposition="unsupported",
        statement=(
            "On lossless networks, implementations must guarantee that "
            "return data carried in PDS requests from target to initiator "
            "(read responses larger than Max_ACK_Data_Size) can be "
            "accepted from the network unconditionally — its acceptance "
            "and processing must not depend on the ability to send an "
            "acknowledgement."
        ),
    ),
    # -- 3.6.4.8 CSIG in UET (summary; detail on the 4.2 anchors) ----------------
    UECRequirement(
        requirement_id="UEC11-CM-R23",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "CSIG-Reflect() is required in a CSIG-capable FEP and must be "
            "enabled whenever a sender-based algorithm such as NSCC or "
            "sender-based load balancing needs tag information; when "
            "enabled, PDS must generate extended acknowledgements "
            "(ACK_CCX or NACK_CCX) carrying up to 128 bits of congestion "
            "state including the CSIG Reflection Header."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R24",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "A source FEP that needs CSIG information reflected should set "
            "pds.flags.ar on CSIG-tagged packets; with reflection enabled "
            "a positively acknowledged CSIG-tagged packet must produce an "
            "ACK_CCX and a negatively acknowledged one a NACK_CCX, with "
            "ccx_type NSCC_CSIG or RCCC_CSIG selecting the field layout; "
            "reflection policies for unmarked packets are out of scope."
        ),
    ),
    # -- 3.6.5.2/3.6.5.3/3.6.5.4 operation overview --------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R25",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="MULTIPATH",
        disposition="informational",
        statement=(
            "PDS adopts multipath packet transmission at its core via "
            "packet spraying: each packet carries a pseudo-randomly chosen "
            "entropy value; a CCC uses a configurable, typically large "
            "number of entropies (for example 64 to 256) essentially "
            "round-robined, and feedback such as ECN marks or trimmed "
            "packets may make the source reduce traffic on a congested "
            "entropy."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R26",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="UET_CC",
        disposition="informational",
        statement=(
            "NSCC keeps an explicit congestion window: a packet leaves the "
            "network when acknowledged, NACKed, or inferred lost; RCCC "
            "keeps a credit pool refilled by destination credit "
            "(requested via credit target or Credit Request CPs), the "
            "destination pacing credit so sources collectively match its "
            "link; TFC uses credit point-to-point; window-based control "
            "is preferred over rate-based for stability."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R27",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="UET_CC",
        disposition="informational",
        statement=(
            "Startup: MaxWnd is bounded near 1.5 BDP and new flows start "
            "by default at line rate with a window around MaxWnd; during "
            "outcast the FEP scheduler, not the window, limits "
            "transmission, and CC algorithms must not treat the resulting "
            "absence of negative feedback as permission to grow the "
            "window."
        ),
    ),
    # -- 3.6.6-3.6.7 CCC structure -------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R28",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "A congestion control context controls admission of data "
            "packets for a PDC group — the PDCs between two FEPs using one "
            "traffic class — and in a single direction only, so "
            "bidirectional traffic uses two CCCs; reverse-path ACK and "
            "control packets are not congestion controlled and should use "
            "a separate traffic class and queue from data."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R29",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "Because several PDCs may be active inside one CCC, a CCC "
            "cannot assume a shared sequence-number space: it tracks the "
            "total bytes of admitted packets, decremented when packets are "
            "acknowledged, NACKed, or inferred lost with high likelihood."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R30",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "Multiple PDCs sending in the same direction between the same "
            "FEPs in the same traffic class should share one CCC ( "
            "including read-response data on reverse PDCs), so CCCs do not "
            "compete and load balancing sees the aggregate flow."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R31",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "When two PDC groups transfer data from the same source to the "
            "same destination using different traffic classes, a separate "
            "CCC must be used for each PDC group, because congestion "
            "measured on one traffic class cannot safely infer congestion "
            "on another."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R32",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "ROD PDCs send all packets on one path and should use one CCC "
            "per PDC, not shared with other ROD or with RUD flows, so one "
            "flow collision's congestion state does not penalize others; "
            "multiple CCCs between the same FEPs may share some state "
            "such as a baseline RTT estimate."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R33",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD NOT",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "RUDI and UUD do not support UET CC (neither ACK carries CC "
            "state); when they carry significant bandwidth they should not "
            "be mapped to the same traffic class as UET-CC traffic."
        ),
    ),
    # -- 3.6.8 source context and API -----------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R34",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD NOT",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "When multiple CCCs permit sending simultaneously, the source "
            "FEP scheduler decides order and capacity split "
            "(implementation-specific); allowing PDCs to build a "
            "significant output queue downstream of the CCC gate is not "
            "recommended, though small queuing may be needed."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R35",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "The PDS must allocate a CCC when the first PDC to a "
            "destination is created and may deallocate it when the last "
            "PDC is destroyed (a CCC may be retained to cache congestion "
            "state); AllocateCCC takes a sprayed flag distinguishing "
            "sprayed from single-path traffic."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R36",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "A CCC is in one of four states — READY (data to send and CC "
            "permits sending), ACTIVE (data but not permitted), PENDING "
            "(sent data unacknowledged, nothing new), IDLE — with "
            "transitions driven by window space, credit availability (both "
            "required when both algorithms run), ACK/NACK arrival, and "
            "retransmission marking."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R37",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST NOT",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "A CCC must not be removed except in the IDLE state, unless "
            "all PDCs associated with it have been declared failed."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R38",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "The CCC API is stateful: events OnACK, OnNACK, "
            "OnInferredLoss, OnNewData, OnCreditUpdate and OnSend move the "
            "state machine and may emit control packets but do not send "
            "data; GetSendParams late-binds entropy and port when the "
            "scheduler picks a PDC; GetEagerEstimate returns cwnd for "
            "rendezvous eager sizing."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R39",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MAY",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "PDS and congestion control are specified as distinct modules "
            "behind an abstract API, but an optimized implementation may "
            "integrate them provided its externally observable behavior is "
            "indistinguishable from the specified API."
        ),
    ),
    # -- 3.6.9 CC headers ---------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R40",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "Congestion state rides in PDS headers: pds.req_cc_state for "
            "RCCC/TFC requests (32 bits: 8-bit ccc_id plus 24-bit "
            "credit_target in 256-byte units, cumulative and wrapping), "
            "pds.ack_cc_state for ACK_CC (64 bits; 128 bits as ACK_CCX), "
            "with pds.cc_type CC_NSCC or CC_CREDIT selecting the NSCC or "
            "credit layouts."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R41",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "NSCC ACK_CC fields: service_time (16 bits, 128 ns units, "
            "where 0x0 means invalid and must be ignored), restore-cwnd "
            "bit, 7-bit rcv_cwnd_pend, 24-bit cumulative rcvd_bytes in "
            "256-byte units (wrapping), and ooo_count; if out-of-order "
            "counting is implemented per PDC a 16-bit field must be "
            "supported, and a destination not calculating it must set "
            "0xFFFF; ooo_count is not used by the CC algorithms."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R42",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST NOT",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "For CC_CREDIT (TFC and RCCC-without-NSCC), the destination "
            "grants credit in the 24-bit cumulative pds.ack_cc_state "
            "field; the source must stop transmitting when credit is "
            "exhausted and must not transmit more packets than the credit "
            "allocation allows."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R43",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "The 64-bit CSIG Reflection Header rides in "
            "pds.ack_ccx_state (ACK_CCX) and pds.nack_ccx_state "
            "(NACK_CCX): the FEP copies tag data (2 bytes compact, 6 "
            "wide) into the least significant bytes and sets the top 4 "
            "bits to the tag type (0 compact, 1 wide); NSCC_CSIG and "
            "RCCC_CSIG variants combine base CC fields with the "
            "reflection header."
        ),
    ),
    # -- 3.6.10-3.6.12 event processing, modes, pseudocode ---------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R44",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "Entropy is extracted from pds.entropy (native and IPv4 "
            "encapsulation) or udp.source_port (UDP encapsulation); before "
            "ACK CC_STATE processing the source updates path state via "
            "process_ev(Entropy, ECN or NO_ECN) from pds.flags.m — not "
            "applied for TFC or ROD CCCs; rcvd_bytes deltas use modular "
            "arithmetic because the field wraps."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R45",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "Every NACK updates the CCC inflight state regardless of its "
            "nack_code (even one closing the PDC), but only NACKs with "
            "UET_TRIMMED or UET_TRIMMED_LASTHOP elicit a congestion "
            "response; a NACK for an already-acknowledged packet causes no "
            "further CMS action."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R46",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "On retransmission timeout or SACK-inferred loss the source "
            "must look up the packet state, compute the nominal packet "
            "size, and perform OnInferredLoss; when CSIG reflection data "
            "is present the signal value is de-quantized via reverse "
            "bucket lookup (min-of-bucket), honoring max(Delay) precision "
            "rules."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R47",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "TFC credit may be returned in ACKs (pds.ack_cc_state with "
            "CC_CREDIT) or in Credit CP payload fields; TFC is not by "
            "itself a congestion control mechanism — it expects a single "
            "link with congestion managed inside the ingress FEP, and "
            "needs companion mechanisms if used across multiple hops."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R48",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="CCC",
        disposition="unsupported",
        statement=(
            "For ROD or RUD CCCs either NSCC or RCCC may be used alone or "
            "both together, and it is recommended that all CCCs in a "
            "cluster use the same combination; quick adapt is recommended "
            "unless RCCC is enabled."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R49",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "Common CCC state: ccc.backlog, ccc.waiting_rtx, "
            "ccc.rtx_backlog and ccc.inflight_pkts across all PDCs of the "
            "CCC; update_state() computes IDLE/PENDING/ACTIVE/READY and "
            "can_send as the AND of NSCC.CanSend() and RCCC.CanSend() for "
            "the enabled algorithms."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R50",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "nominal_pktsize = transport_pktsize + 40 approximates the "
            "packet size for congestion accounting; the source and "
            "destination must derive the same value and it cannot change "
            "in flight (for example due to network telemetry)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R51",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="CCC",
        disposition="informational",
        statement=(
            "Receiver-side common processing (OnRX): RCCC and NSCC hooks "
            "run first; a trimmed packet triggers a NACK carrying the PSN, "
            "entropy, last-hop-trim indication and ECN bit, otherwise an "
            "ACK is sent when PDS 3.5.12 conditions are met, with CC "
            "algorithms filling the ACK CC_STATE fields."
        ),
    ),
    # -- 3.6.13 NSCC ------------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R52",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "NSCC (based on SMaRTT and Strack) limits outstanding data "
            "with ccc.cwnd: sending is permitted only when ccc.cwnd "
            "exceeds ccc.inflight + MTU; the ACK clock is driven by "
            "pds.ack_cc_state.rcvd_bytes, inflight falls on ACK, NACK or "
            "inferred loss, is resilient to spray reordering, is kept "
            "signed (may go slightly negative), and one cwnd covers all "
            "sprayed paths of the CCC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R53",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "The primary control loop combines ECN with bottleneck "
            "queueing delay (from CSIG max(Delay) or RTT minus base_RTT): "
            "no ECN and delay below target_qdelay — proportional increase; "
            "no ECN and delay at or above target — fair (additive) "
            "increase; ECN with delay below target — no change; ECN with "
            "delay at or above target — multiplicative decrease."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R54",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "Increase actions: proportional_increase scales with "
            "(target_qdelay − delay) and fast_increase turns on an "
            "exponential ramp after sustained underload; fair_increase "
            "adds a constant per acknowledged byte so competing CCCs "
            "converge; multiplicative_decrease reduces cwnd proportional "
            "to the delay excess (bounded by max_md_jump, floored at MTU) "
            "at most once per base_rtt."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R55",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "quick_adapt() runs on detected loss or persistently high "
            "delay: it sets cwnd directly from achieved goodput, runs at "
            "most once per RTT (qa_gate), suppresses multiplicative "
            "decrease until the queued packets are acknowledged, and is "
            "how NSCC handles synchronized incast startups; outcast "
            "handling is left to the implementor."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R56",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="SHOULD",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "The PDC should store a transmit timestamp per packet, "
            "updated on each retransmission; it is recommended to record "
            "whether a packet was retransmitted a second or subsequent "
            "time (for example a two-bit rtx_count) so RTT updates from "
            "ACKs of exactly-once-retransmitted packets remain safe."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R57",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="MUST NOT",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "If the pds.flags.retx bit in an ACK is not set while the "
            "packet has been retransmitted, that ACK must not be used to "
            "update RTT measures; an implementation may also skip RTT "
            "updates when the retx bit is set."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R58",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="MUST",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "Destination flow control: pds.ack_cc_state.rcvr_cwnd_pend "
            "must be 0 to 127 — 0 does not flow control, 127 slows "
            "sources at most (down to one packet per RTT), sustained 64 "
            "halves windows; the rc bit tells the source to save cwnd "
            "when receiver flow control starts and restore it at the "
            "end; computing the value is implementation dependent."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R59",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="SHOULD",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "An implementation should allow configuring all NSCC "
            "parameters of Table 3-97: config_base_rtt, link speeds, MTU "
            "(Payload MTU + transport overhead + 40 bytes), BDP = "
            "min(link speeds) × config_base_rtt, MaxWnd = 1.5 × BDP, "
            "target_qdelay (0.75 × base_rtt with trimming, 1.0 without), "
            "gamma 0.8, alpha/fi/eta scaling formulas, qa_gate 3, and "
            "128 ns time precision."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R60",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "Per-CCC NSCC source state includes cwnd (initialized to "
            "MaxWnd), signed inflight, saved_cwnd, base_rtt (starts at "
            "config_base_rtt, only lowered by samples, with max_wnd "
            "recomputed as 1.5 × sender.linkspeed × base_rtt), "
            "achieved_bytes and received_bytes for quick adapt and "
            "fulfill_adjustment, fi_count, increase_mode, and "
            "csig_missing_cnt."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R61",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="MUST",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "Congestion response rules: on inferred loss or a UET_TRIMMED "
            "NACK — or UET_TRIMMED_LASTHOP only when RCCC is not enabled "
            "— cwnd is reduced to at least (cwnd − nominal_pktsize, MTU) "
            "and quick adapt is triggered; a last-hop trim updates delay "
            "with config_base_rtt; NSCC.CanSend() returns inflight + MTU "
            "<= cwnd."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R62",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "NSCC.AckRequest() asks PDS for an ACK when the remaining "
            "window is under one MTU or cwnd is below ACK_Gen_Trigger "
            "(symmetric configuration assumed); fulfill_adjustment() "
            "applies accumulated inc_bytes divided by cwnd plus eta per "
            "RTT, capped at max_wnd; get_avg_delay() must be callable "
            "several times per RTT with a consistent average."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R63",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="SHOULD",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "When a new NSCC CCC is established the source should send a "
            "Probe CP on the control traffic class (after the first ACK "
            "or NACK, since a Probe cannot bring up a PDC) to seed "
            "base_rtt fairly against pre-existing longer flows; it may be "
            "omitted when base_rtt is cached or the PDC will move little "
            "data."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R64",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="DEFINITIONAL",
        subject="NSCC",
        disposition="informational",
        statement=(
            "The NSCC destination keeps pdc.rcvd_bytes per PDC, "
            "incremented by nominal_pktsize for accepted, untrimmed, "
            "non-duplicate data; the ACK field is Rcvd_Bytes = ceil("
            "pdc.rcvd_bytes / 256) — rounded up so the last sub-256-byte "
            "credit of inflight is still acknowledged."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R65",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        keyword="MUST",
        subject="NSCC",
        disposition="unsupported",
        statement=(
            "When csig_maxdelay_enable is set, the FEP's CSIG policy must "
            "enforce inserting max(Delay) CSIG tags in all packets; ACKs "
            "missing the signal increment csig_missing_cnt and are "
            "ignored, and crossing csig_missing_threshold moves NSCC into "
            "a permanent fallback to RTT-derived delay until the "
            "administrator intervenes."
        ),
    ),
    # -- 3.6.14 RCCC ----------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R66",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="DEFINITIONAL",
        subject="RCCC",
        disposition="informational",
        statement=(
            "RCCC (derived from EQDS): the destination sends end-to-end "
            "pull credit to all concurrent sources, normally at its link "
            "speed; sending consumes credit, a source cannot send with "
            "credit at or below zero, and without outcast a source may "
            "start at line rate with up to a BDP of speculative packets, "
            "removed at the first ACK under outcast."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R67",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="DEFINITIONAL",
        subject="RCCC",
        disposition="informational",
        statement=(
            "After the first RTT the destination schedules credit from "
            "source backlog: sources advertise cumulative demand in "
            "pds.req_cc_state.credit_target (reordering-resilient), "
            "credit packets are paced so the data they elicit arrives at "
            "the destination's line rate, each typically carrying a few "
            "MTUs, and trimming keeps the destination's demand view "
            "accurate under incast."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R68",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="SHOULD",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "It is recommended to enable NSCC alongside RCCC (handling "
            "oversubscription while RCCC handles incast) and to disable "
            "ECN on the last-hop link when RCCC is enabled, keeping the "
            "ECN load-balancing signal clean; when NSCC cannot be "
            "enabled, the RCCC aggregate rate control algorithm may be "
            "used instead."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R69",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="MUST",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "When RCCC or TFC is enabled, request packets must use "
            "pds.type RUD_CC_REQ or ROD_CC_REQ so pds.req_cc_state "
            "carries ccc_id and credit_target; the CCC_ID is assigned by "
            "the source and must be unique among that source's CCCs to "
            "the same destination FEP (it may be reused toward different "
            "FEPs)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R70",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="MUST NOT",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "CCC association: a new RUD PDC should reuse an existing CCC "
            "while a new ROD PDC must not; the destination lookup on "
            "{ip.src_addr, pds.ccc_id} must cover both source and "
            "destination CCC state; one PDC's forward path may share a "
            "CCC with another's return path; one CCC_ID must not denote "
            "different CCC instances to the same FEP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R71",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="MUST NOT",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "If every PDC of an existing CCC is already closing, the "
            "source must not use that CCC and must allocate a new one, "
            "preventing the deadlock of having neither credit nor an "
            "active PDC to request it on; a new PDC on a creditless CCC "
            "should send a Credit Request CP, which must ride an "
            "existing PDC of that CCC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R72",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="MUST",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "An RCCC CCC must be shut down when the last PDC using it is "
            "closed."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R73",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="SHOULD",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "RCCC source state per CCC: credit (initialized to MaxWnd = "
            "1.5 × BDP), cumulative credit_target, cumulative_credit, "
            "credit_target_sent and speculating; implementations need not "
            "follow the pseudocode exactly but should achieve the same "
            "behavior, and a source credit timer with the retransmit "
            "timeout covers lost credit packets."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R74",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="DEFINITIONAL",
        subject="RCCC",
        disposition="informational",
        statement=(
            "Source algorithm: OnSend consumes nominal_pktsize; "
            "OnCreditUpdate adds the delta above cumulative_credit "
            "(shifted from 256-byte units); CanSend is true only with "
            "positive credit, otherwise a Credit Request CP carries the "
            "computed target; computeCreditTarget = min(backlog + "
            "rtx_backlog, max_wnd, cwnd + MTU) − credit, floored at MTU, "
            "cumulative; stopSpeculating zeroes credit, keeping one MTU "
            "when no PDC exists."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R75",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="DEFINITIONAL",
        subject="RCCC",
        disposition="informational",
        statement=(
            "Destination algorithm: a sender is an FEP plus CCC_ID; OnRX "
            "raises sender.credit_target and moves senders between "
            "active and idle lists; one credit timer per FEP per traffic "
            "class fires every k × MTU / (linkspeed × credit_rate), "
            "granting round-robin min(credit_target, cumulative_credit + "
            "k × MTU), with idle senders granted speculative credit up "
            "to MaxWnd; Credit CPs carry cumulative_credit."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R76",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="MAY",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "The destination may dynamically change credit_rate (open "
            "interval (0, 1], default 1 meaning near line rate) for any "
            "implementation-specific purpose, including destination flow "
            "control — RCCC does not use NSCC's Rcv_Cwnd_Pend — with an "
            "example backlog-proportional controller provided as an "
            "option, not a mandate."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R77",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="SHOULD",
        subject="RCCC",
        disposition="unsupported",
        statement=(
            "Without NSCC, the receiver may reduce total credit using the "
            "specified HPCC-derived aggregate rate control (and should "
            "use it when reducing credit from observed congestion): "
            "average delay comes from CSIG max(Delay) or, without CSIG, "
            "from ECN rate and trim status between the ECN thresholds; "
            "CC_INVOCATION_DELTA should not exceed one base RTT (1 "
            "microsecond suggested); credit_rate stays clamped to "
            "[min_rate, 1]."
        ),
    ),
    # -- 3.6.16 multipath --------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R78",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="SHOULD",
        subject="MULTIPATH",
        disposition="unsupported",
        statement=(
            "A UET endpoint should perform multipath load balancing for "
            "RUD and RUDI traffic (per-packet ECMP hashing of header "
            "fields), with the precise implementation left open; switch "
            "self-spraying should not be enabled for UET traffic when "
            "path-aware spraying is used, as it destroys the per-path "
            "congestion signal."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R79",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="DEFINITIONAL",
        subject="MULTIPATH",
        disposition="informational",
        statement=(
            "Three entropy modes are permitted: single path (ROD only; "
            "one EV per CCC at a time), oblivious spraying (pseudo-random "
            "EVs over a large space, typically at least 256 values), and "
            "path-aware spraying (EV choice adapted from destination "
            "feedback about congested EVs)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R80",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="MAY",
        subject="MULTIPATH",
        disposition="unsupported",
        statement=(
            "A single-path CCC may change its entropy value when "
            "congestion not on the final link is observed; to limit "
            "reordering it is recommended to switch during idle periods "
            "or at most every t_reroute round trips (default at least 10 "
            "RTTs, configurable), and multiple single-path PDCs should "
            "get distinct CCCs that coordinate different EVs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R81",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="SHOULD",
        subject="MULTIPATH",
        disposition="unsupported",
        statement=(
            "Oblivious spraying should use entropy values in pseudo-random "
            "order, using each once before repeating, and re-randomize "
            "periodically; a simple modular counter is permitted ( "
            "initialized randomly to avoid synchronization); it is most "
            "effective with trimming, and without trimming it is "
            "discouraged though permitted when the source cannot hold "
            "per-path state."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R82",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="SHOULD",
        subject="MULTIPATH",
        disposition="unsupported",
        statement=(
            "Path-aware spraying should size the EV space adaptively so "
            "each value is reconsidered within two RTTs; destinations "
            "feed back the packet's EV plus pds.flags.m (set on "
            "ip.ecn.ce); on marked feedback the source should avoid "
            "reusing that EV for one RTT, unless most paths are "
            "congested (saturation fraction configurable, default 50 "
            "percent); avoidance methods (REPS-style reuse, bitmaps, "
            "combinations) are implementation-specific."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R83",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="SHOULD NOT",
        subject="MULTIPATH",
        disposition="unsupported",
        statement=(
            "Handling transient path failures is an implementation "
            "decision (path-aware sources may avoid EVs with timeouts or "
            "SACK-inferred loss long enough for rerouting); when the "
            "endpoint does not perform path-aware spraying there is no "
            "stable EV-to-path mapping and load balancing should not "
            "remove EVs on packet loss."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R84",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        keyword="MUST",
        subject="MULTIPATH",
        disposition="unsupported",
        statement=(
            "Of the multi-port options, supported are separate planes "
            "with one shared FEP address and a single plane with one "
            "address (anycast); the CCC holds no addressing information, "
            "so unsupported options should map to single-port FEPs; "
            "GetSendParams() must receive one or more free ports, and "
            "the CCC must map a chosen EV to one outgoing port so "
            "ACK/NACK entropy is unambiguous."
        ),
    ),
    # -- 3.6.17 switch configuration ------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R85",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="SWITCH",
        disposition="informational",
        statement=(
            "Plane_BDP is the bandwidth-delay product of the lowest-"
            "bandwidth core path, typically min(sender.linkspeed, "
            "receiver.linkspeed) × config_base_rtt (per rail on multi-rail "
            "NICs); recommended probabilistic ECN settings are queue_low."
            "min_thresh 0.2 × Plane_BDP and max_thresh 0.8 × Plane_BDP "
            "(deterministic alternative 0.5, probabilistic preferred), "
            "and ECN should be disabled for queue_med and queue_high."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R86",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="SWITCH",
        disposition="unsupported",
        statement=(
            "Recommended queue thresholds with trimming: queue_low."
            "trim_threshold = Plane_BDP (1.5 × Plane_BPD for "
            "DSCP_TRIMMABLE_RTX packets) and queue_med/queue_high "
            "drop_threshold = Plane_BDP; without trimming the tail-drop "
            "threshold should be at least 2 and at most 5 × Plane_BDP; "
            "weighted round robin may replace strict priority, with "
            "queue_med weighted near 75 percent as a default."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R87",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHOULD",
        subject="SWITCH",
        disposition="unsupported",
        statement=(
            "CSIG max(Delay) bucket boundaries should derive from trim "
            "or drop thresholds with a 2-times multiplier on the maximum "
            "queueing time: with trimming, [0, 3 × config_base_rtt] at "
            "trim 1.5 × Plane_BDP; without, between [0, 4 × "
            "config_base_rtt] and [0, 10 × config_base_rtt]; "
            "intermediate buckets should be linear; multiple traffic "
            "classes use the largest thresholds as reference."
        ),
    ),
    # -- 3.6.18 PCM -------------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R88",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="PCM",
        disposition="informational",
        statement=(
            "Programmable congestion management (PCM) supports alternative "
            "CC and load balancing algorithms inside the transport "
            "architecture: CC restricts bytes in flight via window or "
            "credit, optionally plus rate; LB is per-packet or EV-table "
            "based; the architecture comprises incoming signals, the CC "
            "algorithm, the LB algorithm and a per-CCC control table, "
            "with an illustrative (not mandated) load/instantiate/"
            "configure/assign/activate/stop/destroy/unload lifecycle."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R89",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "PCM implementations must offer integer datatypes and may "
            "offer floating point; if floating point is unsupported, "
            "compiling a program that uses it must fail; integer or "
            "fixed-point arithmetic may approximate floating point."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R90",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "Every PCM implementation must support the mandatory signal "
            "set (ACK/NACK/request events, entropy, RTT and service time "
            "in 128 ns units, backlog, cwnd, inflight bytes, RTO, credit "
            "events) and may support optional signals (CSIG fields, "
            "staging buffer occupancy) and vendor signals, which must be "
            "prefixed with a vendor alias; a YAML definition using an "
            "unsupported signal must fail compilation."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R91",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "Any implementation must support all defined accumulation "
            "operations uet_op_sum, uet_op_max, uet_op_min and uet_op_last "
            "(uet_op_ewma optional); signal updates are atomic, update "
            "order is undefined (associative operators assumed), and all "
            "updates from one packet apply simultaneously; uet_signal_get "
            "must be supported while uet_signal_set and "
            "uet_signal_update may be."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R92",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="SHALL",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "CSIG values exposed to PCM algorithms shall carry the "
            "quantized bucket index s as an opaque unsigned integer with "
            "{t, m, d}; PCM implementations shall supply de-quantization "
            "parameters via YAML and should provide a csig_dequantize(t, "
            "s) utility returning the representative raw value."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R93",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "Triggers: the algorithm must be invoked exactly once with "
            "all fired non-deferred triggers (piecemeal delivery is not "
            "allowed); on a successful trigger update the runtime must "
            "reset all trigger working states; per-EV triggers attach "
            "uniformly to every EV-table slot; per-packet LB mode must "
            "support the wildcard count-1 invoke trigger configuration "
            "and does not support runtime trigger modification."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R94",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="DEFINITIONAL",
        subject="PCM",
        disposition="informational",
        statement=(
            "Controls: uet_set_cwnd is mandatory; send rate, "
            "ack-per-packet, ACK-generation thresholds/timers and the RX "
            "cwnd penalty are optional (rate, if supported, should apply "
            "in tandem with the window); algorithms may send probes and "
            "credit control packets through the current CCC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R95",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "Telegrams: fixed-size structures up to 30 bytes (32-byte "
            "control-packet payload minus a 2-byte header), fields "
            "transmitted big-endian and packed per YAML, padding zeroed "
            "and ignored, structures invalidated when the invocation "
            "exits; implementations must support sending local telegrams "
            "and may support peer or collector delivery."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R96",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST NOT",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "PCM error model: a CCC must not operate uncontrolled, "
            "undefined or partially corrupt; fatal conditions (hardware "
            "faults, invalid algorithm operations, uet_ccc_fatal) force "
            "an atomic ACTIVE-to-ERROR transition, erroring all serviced "
            "PDCs, admitting no new packets, logically dropping queued "
            "packets, failing further API calls with -ENOTRECOVERABLE, "
            "and allowing exit only via reinitialization outside PCM (a "
            "reinitialized CCC must appear fresh)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R97",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "A single CCC-scoped fatal error indication (source "
            "IMPLEMENTATION or PCM_ALGORITHM with the algorithm's reason) "
            "must be recorded when a CCC errors, must not be overwritten "
            "by later causes, must remain inspectable until reset, and "
            "must be observable non-destructively by software no later "
            "than the transition itself."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R98",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "All traffic in a PCM-managed UET instance must be controlled "
            "exclusively by a single CC algorithm instance and a single "
            "LB algorithm instance."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R99",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MUST",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "Runtime model PCM algorithms must assume: one invocation "
            "per fired trigger set, EV transmit request or telegram; at "
            "most one active invocation per CCC; TX and RX events in "
            "packet order but may be skipped; TIME events reliably "
            "delivered though possibly delayed; no ordering guarantees "
            "across TX/RX/TIME or local/peer telegrams; EV requests in "
            "generation order; controls in issued order."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R100",
        anchor_ids=("UEC11-S3.6-CMS",),
        keyword="MAY",
        subject="PCM",
        disposition="unsupported",
        statement=(
            "Implementations may advertise PCM eBPF compliance, letting "
            "loaded algorithms be formally verified for safety; compliant "
            "algorithms must use only bounded loops, no recursion, "
            "verifiable pointer accesses, at most 512 bytes of stack, "
            "call depth at most 8 and tail-call depth at most 32."
        ),
    ),
    # -- 4.2 CSIG overview, tag formats, domain functionality --------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R101",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="DEFINITIONAL",
        subject="CSIG",
        disposition="informational",
        statement=(
            "CSIG is an in-band network telemetry method: a single "
            "fixed-size tag carried in layer-2 headers collects one "
            "aggregated congestion signal per packet across all switches "
            "of the path (independent of hop count), transport- and "
            "encapsulation-agnostic, extensible to new signal types; "
            "endpoints consume terminated signals for congestion control, "
            "load balancing and telemetry."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R102",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "All UE-compliant switches and hosts that support CSIG must "
            "support the 4-byte compact CSIG tag, which matches a VLAN "
            "tag in frame offset and field widths so VLAN match-action "
            "hardware can process it; they may additionally support the "
            "8-byte wide tag (16 versus 8 signal types, 2^20 versus 32 "
            "quantized values, 15- versus 6-bit locator metadata)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R103",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Until permanent EtherType assignment, CSIG implementations "
            "must support configurable EtherType values for the compact "
            "and wide tags; the two values must be distinct and must not "
            "conflict with any other EtherType in use in the CSIG domain, "
            "and configurability should remain afterward."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R104",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Signal types: 0 = ABW (aggregation min), 1 = ABW/C (min), "
            "2 = Delay (max), 3 = nQD (max), plus one experimental type "
            "per format (7 compact, 15 wide); UE switches must support "
            "the signals of the CSIG base profile."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R105",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Pre-quantization local values and quantized values must be "
            "integers; compact quantization maps into 32 configured "
            "buckets whose ranges must not overlap and must be "
            "contiguous (inclusive bounds, set per signal type by the "
            "control plane); the raw value is precision-matched by right "
            "shifting, and out-of-range values must clamp to bucket 0 "
            "(low) or 31 (high), with event counters recommended."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R106",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Wide-tag quantization: bucket index i = (v − b) >> e with "
            "exponent e >= 1 and base b zero or a power of two set per "
            "signal type, each bucket spanning 2^e values; values below "
            "b must quantize to bucket 0 and values above b + 2^(e+20) − "
            "1 to bucket 2^20 − 1, with event counters recommended."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R107",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "When a switch updates the signal value in a CSIG tag it must "
            "also update the locator metadata (csig.lm, 6 bits compact / "
            "15 wide) identifying the updating hop — for example link "
            "capacity, orientation, fabric stage, plane or port/TTL "
            "hints."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R108",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST NOT",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "csig.d semantics: with d = 0 a switch must perform "
            "CSIG-Compare-and-Update() per the tag's signal type and "
            "aggregation function; with d = 1 it must not modify the "
            "signal value; initialized tags start with d = 0; a switch "
            "trimming a CSIG-tagged packet must set csig.d and should "
            "change nothing else (mandatory base case), preserving the "
            "pre-trim signal."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R109",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="SHALL",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "The reserved bits csig.r shall be set to 0 by the FEP that "
            "initializes and inserts a CSIG tag, and are ignored on "
            "receipt."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R110",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "A CSIG-capable host or switch must support the compact tag "
            "and base profile, may additionally support wide tags and "
            "the extended profile, must forward tag information through "
            "the switch to any egress port and update it there, and must "
            "strip the tag formats it supports; the LLDP csig-capable "
            "object (CSIG-NO, CSIG-COMPACT, CSIG-COMPACT-WIDE) must be "
            "set consistently with capability and configuration."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R111",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Tag initialization: only FEPs insert and initialize CSIG "
            "tags (switches never do); the inserting FEP must initialize "
            "csig.t and csig.s per Table 4-8 — min-type signals start "
            "all-ones, max-type signals all-zeros — and must set csig.d "
            "and csig.r to zero; the FEP policy may tag every packet, "
            "every Nth packet, or dedicated probes."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R112",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Transit and stripping: a switch receiving a d = 0 tag must "
            "run CSIG-Compare-and-Update() and leave d = 1 tags "
            "unchanged; a switch that learns via LLDP of a non-CSIG peer "
            "must invoke CSIG-Strip-and-Forward() on tagged packets "
            "before sending on that link, regardless of csig.d, so the "
            "peer does not drop them."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R113",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Termination and reflection: the destination FEP's CSIG-Term("
            ") extracts t, s, lm and d, presents them to receiver-based "
            "congestion control or to CSIG-Reflect() for sender-based "
            "control, and strips the tag; implementing CSIG-Reflect() is "
            "required in a CSIG-capable FEP and it must be enabled when "
            "sender-based algorithms need the information, returning it "
            "in ACK/NACK reflection headers."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R114",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="DEFINITIONAL",
        subject="CSIG",
        disposition="informational",
        statement=(
            "The CSIG tag is placed as the last tag of the layer-2 header "
            "before the original EtherType (same relative position with "
            "802.1Q and MACSec); tunneling CSIG-tagged packets at layer "
            "2 or above is out of scope."
        ),
    ),
    # -- 4.2.8 measurement interval (parent 4.2 anchor) --------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R115",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="SHOULD",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Rate signals should use a measurement interval within the "
            "unloaded RTT of the shortest path; a CSIG-capable switch "
            "should support 102.4 microseconds and any supported values "
            "from 128 ns to 1024 ms in 128 ns steps, the same set for "
            "ABW and ABW/C; the fabric must configure the same "
            "intervals across all switches, and approximations must "
            "respect quantization precision."
        ),
    ),
    # -- 4.2.7 profiles -----------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R116",
        anchor_ids=("UEC11-S4.2.7-CSIG-PROFILES",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "All CSIG-enabled devices must support the base profile — "
            "ABW, ABW/C and Delay, the useful inputs to NSCC, whose "
            "support UEC mandates — and may support any subset "
            "(including none) of the extended profile signals, nQD and "
            "Experimental; devices supporting extended-profile signals "
            "must be able to indicate which ones (via the CSIG SAI "
            "specification)."
        ),
    ),
    # -- 4.2.9 signals -------------------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R117",
        anchor_ids=("UEC11-S4.2.9-CSIG-SIGNALS",),
        keyword="DEFINITIONAL",
        subject="CSIG",
        disposition="informational",
        statement=(
            "min(ABW): the tag records, over all switches on the path, "
            "the minimum quantized absolute available bandwidth at any "
            "output port, with A = p − r and r = m/t (port speed minus "
            "measured traffic rate over interval t); all devices in the "
            "CSIG domain should share the same t and quantization "
            "functions per tag format."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R118",
        anchor_ids=("UEC11-S4.2.9-CSIG-SIGNALS",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Load accounting: UE-compliant switches must support a mode "
            "excluding MAC-generated frames from per-port transmit load "
            "accounting for ABW/ABW/C, so only frames subject to FEP "
            "congestion control are counted; PAUSE, LLR, CBFC and PFC "
            "frames should not be included, and other accounting "
            "variations may be supported."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R119",
        anchor_ids=("UEC11-S4.2.9-CSIG-SIGNALS",),
        keyword="DEFINITIONAL",
        subject="CSIG",
        disposition="informational",
        statement=(
            "min(ABW/C) normalizes available bandwidth by output port "
            "capacity — F = 100 × A / p as an integer percentage 0-100 — "
            "so ports of heterogeneous speeds compare correctly; it uses "
            "the min aggregation and the same load-accounting "
            "constraints as min(ABW)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R120",
        anchor_ids=("UEC11-S4.2.9-CSIG-SIGNALS",),
        keyword="MUST",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "max(Delay): a CSIG-capable switch must measure per-packet "
            "delay as the difference between the egress start-of-packet "
            "timestamp and the ingress start-of-packet timestamp (local "
            "clocks only, no cross-switch synchronization), capturing "
            "only queueing and pipeline delay and compatible with "
            "cut-through; a fixed uncongested forwarding delay may be "
            "subtracted."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-CM-R121",
        anchor_ids=("UEC11-S4.2.9-CSIG-SIGNALS",),
        keyword="DEFINITIONAL",
        subject="CSIG",
        disposition="informational",
        statement=(
            "max(nQD): instantaneous queue depth in bytes at dequeue "
            "normalized by output port speed, yielding nanoseconds — a "
            "leading, multi-bit-ECN-like indicator; normalization uses a "
            "base port speed (power-of-two ratios shift, others divide); "
            "its correctness relies on no time-varying higher-priority "
            "load, and multi-traffic-class use is out of scope."
        ),
    ),
    # -- 4.2.10 deployment (parent 4.2 anchor) --------------------------------------------
    UECRequirement(
        requirement_id="UEC11-CM-R122",
        anchor_ids=("UEC11-S4.2-CSIG",),
        keyword="SHOULD",
        subject="CSIG",
        disposition="unsupported",
        statement=(
            "Deployment: a fabric-global setting selects the preferred "
            "tag format and FEPs should follow it, avoiding "
            "mixed-format paths; CSIG should be enabled fabric-wide only "
            "when every switch supports it; new signal types should be "
            "enabled only after universal support; handling of an "
            "unsupported signal type (strip-and-forward or forward "
            "unchanged) is a centrally configured policy, not "
            "discoverable via LLDP."
        ),
    ),
)

_FREE_PARAMETERS: tuple[UECFreeParameter, ...] = (
    UECFreeParameter(
        parameter_id="UEC11-CM-F01",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        name="multipath_implementation_and_entropy_space",
        freedom=(
            "The precise multipath load-balancing implementation is left "
            "open: entropy-space size (typical 256, other sizes allowed), "
            "the pseudo-random sequence generation (a modular counter "
            "suffices), and the per-signal reason handling in process_ev() "
            "are all implementation choices; UET-CC does not prescribe how "
            "feedback is used to load balance."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F02",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        name="single_path_reroute_policy",
        freedom=(
            "t_reroute (default at least 10 RTTs, configurable), the idle "
            "period required before an entropy change, and how long a "
            "path-aware source avoids an EV after loss are configuration/"
            "implementation decisions; the saturation fraction of "
            "congested paths (default 50 percent) should be configurable."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F03",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        name="nscc_tunable_parameters",
        freedom=(
            "NSCC parameters beyond the fixed formulas are deployment "
            "tuned: config_base_rtt and link speeds, disable_quick_adapt, "
            "qa_gate (default 3), csig_missing_threshold, and the "
            "floating-point precision/rounding mode; get_avg_delay()'s "
            "averaging method and outcast handling are "
            "implementation-specific."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F04",
        anchor_ids=("UEC11-S3.6.13-NSCC",),
        name="nscc_receiver_flow_control_computation",
        freedom=(
            "How a destination computes Rcv_Cwnd_Pend (and whether at all "
            "— it may always send 0) is implementation dependent; only "
            "the field range and the source-side penalty response are "
            "specified."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F05",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        name="rccc_credit_grant_policy",
        freedom=(
            "The credit grant quantum k (small, typically four MTUs), the "
            "sharing strategy across active senders (round robin shown, "
            "others allowed), and dynamic credit_rate adaptation "
            "algorithms (destination backlog control, aggregate rate "
            "control parameters of Table 3-104) are implementation/"
            "deployment choices."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F06",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        name="rccc_rud_ccc_sharing",
        freedom=(
            "Whether a new RUD PDC reuses an existing CCC is a SHOULD, "
            "and implementations choose whether to create additional PDCs "
            "to a destination; the spec fixes only that ROD PDCs never "
            "share and that closing CCCs must not be reused."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F07",
        anchor_ids=("UEC11-S3.6-CMS",),
        name="dscp_codepoint_assignment",
        freedom=(
            "UET does not mandate numeric DSCP values: the operator maps "
            "the two-to-six abstract names (DSCP_TRIMMABLE, "
            "DSCP_TRIMMED, DSCP_CONTROL, ...) to values per network and "
            "UET traffic class, and may replicate the set for multiple "
            "UET classes; Trimmable_ACK_Size is likewise a deployment "
            "parameter."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F08",
        anchor_ids=("UEC11-S3.6-CMS",),
        name="switch_queue_thresholds",
        freedom=(
            "Recommended ECN/trim/drop thresholds are factors of "
            "Plane_BDP (0.2/0.8/0.5, 1, 1.5, 2-5); probabilistic versus "
            "deterministic ECN marking, weighted-round-robin weights "
            "(queue_med near 75 percent default) and absolute buffer "
            "sizes remain deployment choices tuned per fabric."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F09",
        anchor_ids=("UEC11-S3.6-CMS",),
        name="source_scheduler_behavior",
        freedom=(
            "How the sending FEP scheduler orders PDCs whose CCCs are "
            "READY and allots transmission capacity among them is "
            "implementation specific, including starvation handling when "
            "cwnd is one MTU."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F10",
        anchor_ids=("UEC11-S3.6-CMS",),
        name="pcm_algorithm_selection_and_configuration",
        freedom=(
            "PCM leaves the CC/LB algorithm choice, instance parameters "
            "(YAML-defined per algorithm), and per-UET-instance "
            "assignment to the administrator; vendor signal extensions "
            "and eBPF-compliance advertisement are optional "
            "implementation freedoms."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F11",
        anchor_ids=("UEC11-S4.2-CSIG",),
        name="csig_ethertypes_and_tag_policy",
        freedom=(
            "CSIG EtherType values are configurable (must be distinct and "
            "non-conflicting) until permanent assignment — and should "
            "remain configurable after; the FEP's tag-insertion policy "
            "(every packet, 1-in-N sampling, or dedicated probes) is a "
            "local policy decision."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F12",
        anchor_ids=("UEC11-S4.2-CSIG",),
        name="csig_measurement_interval",
        freedom=(
            "The traffic-rate measurement interval t is chosen per fabric "
            "(should not exceed the shortest-path unloaded RTT): 102.4 "
            "microseconds is the recommended default, and switches may "
            "support as many of the 128 ns-increment values from 128 ns "
            "to 1024 ms as they can, provided the whole fabric uses the "
            "same intervals."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F13",
        anchor_ids=("UEC11-S4.2-CSIG",),
        name="csig_quantization_buckets",
        freedom=(
            "Compact-tag bucket ranges are fully configured per signal "
            "type by the switch control plane (only non-overlap, "
            "contiguity and inclusivity are fixed); wide-tag parameters "
            "b (zero or power of two) and e (>= 1) are likewise "
            "configuration; locator-metadata contents are "
            "deployment-specific."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F14",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        name="rccc_last_hop_ecn_configuration",
        freedom=(
            "Disabling ECN on the last-hop link when RCCC is enabled is a "
            "deployment recommendation, not a mandate; whether NSCC "
            "complements RCCC or the RCCC aggregate rate control is used "
            "for oversubscription is a per-network decision."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-CM-F15",
        anchor_ids=("UEC11-S3.6.16-MULTIPATH",),
        name="path_failure_handling",
        freedom=(
            "How UET-CC load balancing handles transient path failures "
            "(how long to avoid EVs with timeout/SACK-inferred loss, "
            "rerouting assumptions) is an implementation decision; "
            "static-EV-mapping fabrics and dynamic-routing fabrics admit "
            "different strategies."
        ),
    ),
)


def requirements() -> tuple[UECRequirement, ...]:
    """All congestion management requirement objects of this stage."""
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
            f"UEC congestion management semantic objects failed validation: "
            f"{detail}{more}"
        )
