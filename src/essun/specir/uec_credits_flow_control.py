"""UEC 1.1 credits / flow-control semantics: stage S5 semantic objects (T010/T011).

Fifth slice of the UEC semantic profile ladder: the credit and flow-control
mechanism family — Transport Flow Control (TFC, section 3.6.15: end-to-end
receive-buffer credits aligned with the RCCC credit machinery), the
RCCC pull-credit residue of 3.6.14 that stage S4 left to this stage, and the
link-layer Credit-Based Flow Control (CBFC, section 5.2 with the anchored
5.2.4 overview, 5.2.5 operation and 5.2.10 compliance subsections).

Stage split with S4 (congestion management): S4 already encoded the RCCC
congestion-control loop of 3.6.14 as objects UEC11-CM-R66..R77 plus the
CC_CREDIT header law (CM-R42); S5 therefore encodes from 3.6.14 only the
pull-credit facts S4 did not encode (shared CCC pool for large responses,
AI-Base reverse-CCC exemption, the credit>0 send-gate simplification) and
does not cite the 3.6 anchor at all — TFC's reuse of the RCCC credit
machinery is grounded on 3.6.15's own pages, per the S4 report's reservation.

Object model, vocabularies and validation follow the S2/S3/S4 pattern
(:mod:`essun.specir.uec_link_transport` is the single source of truth for
the dataclasses and :data:`NORMATIVE_KEYWORDS`/:data:`MAX_STATEMENT_WORDS`):
every object is a mapping ``requirement id -> anchor ids -> typed statement``
(provenance rule).  Keywords are typed exactly as the spec text carries
them (spec "RECOMMENDED" is typed SHOULD); ``DEFINITIONAL`` marks
load-bearing structure/algorithm facts stated without an RFC-2119 keyword —
heavy in the CBFC operation and initialization sections.  Free parameters
are always ``domain="FREE"``.

Statements are paraphrases in our own words (S0 license gate: verbatim spec
text in git remains only the S1 registry's <= 30-word quotes).  Anchors are
section-scoped per the S2/S3/S4 method notes: an anchor pins its section's
entry page/hash; statements may be drawn from the section's full page span,
and subsections without a dedicated anchor cite the parent-section anchor
(the 5.2 anchor p650 grounds 5.2.1-5.2.3 pp. 650-652, 5.2.6-5.2.9
pp. 662-677 and 5.2.11 pp. 680-681; the 5.2.5 anchor p653 grounds
5.2.5.1-5.2.5.8 pp. 653-662; the 5.2.10 anchor p678 grounds 5.2.10.1-5.2.10.3
pp. 678-680; the 3.6.15 anchor p505 grounds 3.6.15.1-3.6.15.4 pp. 505-508).
Dangling anchors are hard errors
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

#: Subjects a stage-S5 statement can bind.  TFC is the end-to-end
#: transport-level credit mechanism (3.6.15); PULL_CREDIT the RCCC
#: pull-credit residue (3.6.14); CBFC the link-layer credit mechanism incl.
#: compliance (5.2/5.2.10); CBFC_MSG the CF_Update/CC_Update messages incl.
#: CtlOS carriage (5.2.6/5.2.7/5.2.11); CBFC_INIT the lossless-VC
#: initialization/removal processes and TLVs (5.2.8); CBFC_LLR the
#: LLR/PFC interaction rules (5.2.9).
SUBJECTS: tuple[str, ...] = (
    "TFC",  # transport flow control (3.6.15)
    "PULL_CREDIT",  # RCCC pull-credit facts S4 left to S5 (3.6.14)
    "CBFC",  # credit-based flow control mechanism + compliance (5.2, 5.2.10)
    "CBFC_MSG",  # CF_Update / CC_Update messages and CtlOS rules (5.2.6-5.2.11)
    "CBFC_INIT",  # lossless VC initialization / removal (5.2.8)
    "CBFC_LLR",  # CBFC x LLR/PFC interaction rules (5.2.9)
)

#: Anchor ids this stage is allowed to cite (mechanism-to-anchor map, S1:
#: 5.2, 5.2.4, 5.2.5, 5.2.10, 3.6.14, 3.6.15).  3.6.14 is shared with S4
#: by design (S4 owns its congestion-control loop, S5 its pull-credit
#: residue); the 3.6 anchor is S4's and is never cited here, so nothing is
#: encoded from 3.6-span pages that live in 3.6.15.
S5_ANCHOR_IDS: frozenset[str] = frozenset(
    {
        "UEC11-S3.6.14-RCCC",
        "UEC11-S3.6.15-TFC",
        "UEC11-S5.2-CBFC",
        "UEC11-S5.2.4-CBFC-OVERVIEW",
        "UEC11-S5.2.5-CBFC-OPERATION",
        "UEC11-S5.2.10-CBFC-COMPLIANCE",
    }
)

_REQUIREMENTS: tuple[UECRequirement, ...] = (
    # -- 3.6.15 Transport Flow Control ----------------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R01",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        disposition="informational",
        statement=(
            "Transport Flow Control lets a destination control the amount "
            "of data transmitted from one or more sources: a point-to-point "
            "credit mechanism with the destination allocating credit and "
            "the source consuming it; credit transfer is aligned with the "
            "RCCC credit mechanism, using the same header fields (the "
            "24-bit pds.credit in PDS Credit CPs or pds.cc_type=CC_CREDIT "
            "acknowledgements)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R02",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST NOT",
        subject="TFC",
        # Promoted unsupported -> simulated_behavior 2026-10-29 (flagship
        # slice, design doc D1 build order item 2): bound to the analytical
        # TFC-window backend by binding BIND-UEC11-FC-R02-L0TFC
        # (essun.specir.bindings); golden test tests/golden/test_l0_tfc_golden.py.
        # The promotion is a claim about the binding (the requirement's
        # admission law causally affects backend outputs through
        # tfc.window_bytes), NOT a physical-validity claim.
        disposition="simulated_behavior",
        statement=(
            "A source must not transmit a packet if it does not have "
            "credit; this is the admission law of the whole TFC mechanism."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R03",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "A TFC source is permitted to send whenever ccc.credit is "
            "greater than zero; since permission does not depend on packet "
            "size, the destination must be able to accept an MTU-sized "
            "packet whenever the source has positive credit."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R04",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "When pds.cc_type=CC_CREDIT is used with TFC, pds.ooo_count "
            "must be set to 0xFFFF (marking the field invalid) and must be "
            "ignored on receipt."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R05",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        disposition="informational",
        statement=(
            "pds.credit is a monotonically increasing wrapping counter; an "
            "increase grants additional credit, giving tolerance to credit "
            "packet loss; one bit represents 256 bytes.  On credit arrival: "
            "if Credit > cumulative_credit then credit += (Credit − "
            "cumulative_credit) >> 8 and cumulative_credit = Credit."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R06",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        disposition="informational",
        statement=(
            "TFC credit protects destination buffering while RCCC manages "
            "network bandwidth, so a TFC source may retransmit without "
            "credit (the buffer was already allocated): CanSend returns "
            "true for retransmissions or positive credit; OnSend subtracts "
            "credit_used only for non-retransmissions; PDC-level "
            "retransmission is conceptually separate from LLR link-level "
            "retry."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R07",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "The destination manages its receive buffer as cells of "
            "tfc_dest_cell_size; credit is allocated in 256-byte units, so "
            "cell sizes from 256 bytes to 9 KB (9216 bytes) in multiples of "
            "256 bytes must be supported; tfc_dest_cell_size defaults to "
            "256 bytes."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R08",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        # Promoted informational -> simulated_behavior 2026-10-30 (G2
        # credit-family ladder stage S2, per the S1 plan in
        # experiments/uec/credit_family_inventory.md): bound to the
        # analytical TFC-window backend by binding BIND-UEC11-FC-R08-L0TFC
        # (essun.specir.bindings) through the opt-in tfc_dest_cell_size
        # parameter; golden test tests/golden/test_l0_tfc_cell_golden.py.
        # The promotion claims the ROUNDUP consumption law causally affects
        # backend outputs as the rate identity min(B, (c/cq)*W/(L+L_cr)),
        # with exact zero-waste convergence to the landed FC-R02 identity
        # at c == 0 (mod cell). The cell DOMAIN values are cited to
        # UEC11-FC-R07, which itself stays unsupported; the per-packet
        # overhead half of tfc_pkt_size is stage S3 (FC-R09), not executed.
        disposition="simulated_behavior",
        statement=(
            "credit_used = ROUNDUP(tfc_pkt_size ÷ tfc_dest_cell_size) × "
            "tfc_dest_cell_size with tfc_pkt_size = UET payload size + "
            "tfc_pkt_overhead; a destination keeping per-packet buffer "
            "structures may use 9216-byte cells so each packet consumes one "
            "cell (worked example: 4096-byte payload, 256-byte overhead, "
            "512-byte cells ⇒ 4608 bytes of credit)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R09",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "Source and destination must use the same constant "
            "tfc_pkt_overhead, which defaults to 256 bytes (one credit "
            "unit); it covers extra destination memory per packet — "
            "Ethernet/IP/UDP/SES headers, FCS and stored metadata — because "
            "packet sizes can change in transit."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R10",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="SHOULD",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "It is recommended that tfc_pkt_overhead be configurable "
            "between 0 and 256 bytes; an implementation may instead use a "
            "constant 256 bytes, in which case the destination may need to "
            "allocate additional buffering when larger encapsulations are "
            "used."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R11",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "The destination must be able to store any valid arriving "
            "packet for which it has allocated credit."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R12",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MAY",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "TFC manages a unidirectional flow from a sending FEP to a "
            "receiving FEP; because tfc_dest_cell_size and tfc_pkt_overhead "
            "are primarily determined by the destination FEP, their values "
            "may differ between the two directions of a bidirectional PDC "
            "pair."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R13",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "tfc_dest_cell_size and tfc_pkt_overhead cannot be modified on "
            "an active PDC: either their default values must be used, or "
            "any non-default values must be configured or communicated out "
            "of band before data is sent on the PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R14",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "A new TFC PDC's ccc.credit must be set to tfc_pkt_overhead or "
            "a larger configured value, never less — enough for an SES "
            "NO_OP carrying a credit request in pds.req_cc_state."
            "credit_target (a NO_OP can bring up a PDC; a Credit Request CP "
            "cannot); if tfc_pkt_overhead is 0, a larger configured value "
            "should be used."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R15",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        disposition="informational",
        statement=(
            "Once established, the source requests more credit via "
            "pds.req_cc_state in PDS Request packets or the pds.payload of "
            "Credit Request CPs, used exactly as in RCCC: a ccc_id "
            "identifying the source CCC context plus a cumulative "
            "credit_target requested since CCC creation; the credit may "
            "return in the NO_OP's ACK or a separate Credit CP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R16",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "Multiple TFC PDCs may share one CCC or use separate CCCs; the "
            "source controls this via pds.req_cc_state.ccc_id — same "
            "CCC_ID between an FEP pair means the destination must "
            "associate those PDCs with the same CCC, different CCC_IDs "
            "mean independent instances; credit granted to one PDC is "
            "usable by any PDC of that CCC; sharing should be "
            "configurable."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R17",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        disposition="informational",
        statement=(
            "When the last PDC sharing a TFC CCC is shut down the CCC is "
            "also shut down: remaining credit is no longer usable for new "
            "data and destination buffers reserved for that credit may be "
            "freed."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R18",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="MUST NOT",
        subject="TFC",
        disposition="unsupported",
        statement=(
            "A TFC CCC must not be reused for a new PDC after its last PDC "
            "has entered the QUIESCE state of the Single PDC Close State "
            "Machine (Figure 3-57) — this prevents the race where the "
            "destination frees the CCC's buffers believing it shut down "
            "while the source starts a new PDC on it."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R19",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        keyword="DEFINITIONAL",
        subject="TFC",
        disposition="informational",
        statement=(
            "Like RCCC, a TFC source needs a credit timer covering lost "
            "credit packets: an active sender (no credit but data to send) "
            "starts a timer with the retransmit timeout; on expiry, "
            "OnSourceCreditTimer returns unless ccc.state == READY, else it "
            "sends send_credit_request(ccc.credit_target)."
        ),
    ),
    # -- 3.6.14 pull-credit residue (not encoded by S4) ------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R20",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="SHOULD",
        subject="PULL_CREDIT",
        disposition="unsupported",
        statement=(
            "There should be one common pool of shared pull-credit CCCs "
            "serving both semantic requests and semantic responses with "
            "payload larger than Max_ACK_Data_Size — the CCC_ID should be "
            "used for both new requests and such responses."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R21",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="DEFINITIONAL",
        subject="PULL_CREDIT",
        disposition="informational",
        statement=(
            "PDC/CCC lookup allocates forward- and reverse-direction CCCs "
            "together when none exist, but AI Base implementations do not "
            "require the reverse-direction CCC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R22",
        anchor_ids=("UEC11-S3.6.14-RCCC",),
        keyword="DEFINITIONAL",
        subject="PULL_CREDIT",
        disposition="informational",
        statement=(
            "The pull-credit send gate is credit > 0, not credit ≥ "
            "nominal_pktsize: the spec's footnote states requiring merely "
            "positive credit is simpler to implement and the one-packet "
            "offset has negligible performance effect — the law TFC's "
            "CanSend reuses."
        ),
    ),
    # -- 5.2 CBFC: definition, rationale, features ------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R23",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "CBFC is the spec-defined protocol, procedures and message "
            "formats enabling credit-based flow control per priority "
            "(virtual channel) on a UE full-duplex link; it is an optional "
            "link-layer feature of an individual point-to-point connection, "
            "an alternative to IEEE 802.1Q PFC for eliminating "
            "congestion-loss at the receiver, and designed to allow "
            "simultaneous operation with PFC to manage multiple chip "
            "resources."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R24",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="MUST NOT",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "When either CBFC or PFC is enabled on a link, the IEEE 802.3 "
            "PAUSE mechanism must not be enabled on that link."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R25",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Lossless hop-by-hop delivery removes end-to-end "
            "retransmission delay; per-traffic-class link flow control "
            "suits small networks, low loads, Torus/Dragonfly, HPC/AI "
            "short messages and low-rate control traffic.  Over PFC: more "
            "lossless VCs per burst buffer, sender-visible credit usage, "
            "insensitivity to cable/frame/response timing "
            "(underestimate ⇒ underuse, not loss), fewer credits for "
            "sub-rate VCs; PFC keeps simpler XOFF/XON, shared burst "
            "buffer, multi-resource and zero-overhead properties."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R26",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Feature list: up to 32 VCs per port, flexible lossless and "
            "best-effort VC assignment, lossless delivery per lossless VC, "
            "receiver port buffer sharing across VCs, forward-progress "
            "guarantee (deadlock avoidance) per VC, configurable credit "
            "units, resiliency to packet loss and CBFC message loss, and "
            "CBFC/PFC together managing separate resources (e.g. main input "
            "buffer vs a second buffering point)."
        ),
    ),
    # -- 5.2.4 CBFC overview ------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R27",
        anchor_ids=("UEC11-S5.2.4-CBFC-OVERVIEW",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "The sender tracks the receiver's available buffer space in "
            "units of credits; the packet scheduler may schedule a packet "
            "from a lossless VC queue only when enough credits are "
            "available at the receiver; CBFC messages return freed credits "
            "from receiver to sender, and credit generation at the receiver "
            "is based on its port buffer availability."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R28",
        anchor_ids=("UEC11-S5.2.4-CBFC-OVERVIEW",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Both sides track credits in always-incrementing cyclic "
            "counters that wrap at the counter's modulus; two cyclic "
            "counter values can be reliably ordered only if they differ by "
            "less than half the counter range, unless one is guaranteed "
            "greater, in which case the full range is usable."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R29",
        anchor_ids=("UEC11-S5.2.4-CBFC-OVERVIEW",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Two counters drive the mechanism: credits consumed (CC), "
            "incremented on transmission and tracked by both sides, and "
            "credits freed (CF), incremented as the receiver drains its "
            "input buffer and reported to the sender; the sender also "
            "holds per-port and per-VC credit limits initialized to the "
            "receiver's available credits; periodic counter "
            "synchronization makes lost CF_Updates and lost packets "
            "(credit leakage) self-correcting."
        ),
    ),
    # -- 5.2.5 CBFC operation ------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R30",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "CBFC is a link-layer function defined only for a pair of "
            "full-duplex MACs connected by one point-to-point link; "
            "although defined mainly at the data link layer it requires "
            "modifications of the standard MAC, RS and PCS sublayers to "
            "forward CBFC CtlOS messages between link partners."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R31",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Configuration parameters (Table 5-14): CreditSize (bytes per "
            "credit, from the receiver's cell size), NumVCs (1 ≤ NumVCs ≤ "
            "32), TotalCredits (positive, from receiver buffer size), "
            "VC_CreditLimit[x], and PktOvhd (per-packet receiver buffer "
            "bytes, possibly negative when part of the packet is not "
            "stored); per-packet buffer need = PktOvhd + frame size "
            "rounded up to the credit size."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R32",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="MUST NOT",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "Two credit-limit methods exist — receiver sets a single "
            "TotalCredits (sender distributes it, implementation-specific, "
            "over dedicated/shared per-VC limits) or receiver sets each "
            "VC_CreditLimit[x] (sender must adhere per-VC); mixing is not "
            "allowed: setting per-VC limits for some lossless VCs requires "
            "limits for all of them with TotalCredits left at zero; per-VC "
            "limits are required to guarantee non-blocking between "
            "lossless VCs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R33",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "A packet-header-to-VC mapping must be configured at sender and "
            "receiver so both assign the same VC number to a given packet; "
            "at minimum a mapping from mac.vlan.pcp_dei, from ip.dscp, or "
            "from any subset of these fields must be supported; when both "
            "fields are used a consistent precedence configuration is "
            "required; VC/PFC-traffic-class mapping at network level is "
            "implementation-specific."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R34",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "State: sender counters S_VC_CC[x] (incremented by packet "
            "credits on transmit) and S_VC_CF[x] (updated on CF_Update); "
            "receiver counters R_VC_CC[x] (on packet receive and CC_Update) "
            "and R_VC_CF[x] (on buffer free); sender variables S_P_CL, "
            "S_P_CU, S_VC_CL[x] and S_VC_CU[x] = S_VC_CC[x] − S_VC_CF[x]; "
            "CC/CL/CU widths are 20 bits, CF widths 15 bits; all cyclic "
            "counters wrap at their modulus."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R35",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="SHALL",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "An implementation shall support at least one lossless VC for "
            "the CBFC mechanism to be enabled, and the widths of S_P_CL, "
            "S_P_CU, S_VC_CL[x] and S_VC_CU[x] must support the 20-bit "
            "per-VC CC counter width."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R36",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Counter sizing rationale: CF/CC width follows update "
            "frequency, link RTT and receiver buffer — 500 m reach, ≈5 µs "
            "RTT, 64 B credits put ≈7.8k credits in flight at 800 GE, so "
            "CF counters are 15 bits; CC_Update is infrequent and 20-bit "
            "CC counters support 2^19 credits (32 MB at 64 B), under "
            "0.01% of link bandwidth."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R37",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Two point-to-point message types: CF_Update (receiver to "
            "sender, 8-byte CtlOS, high frequency, carrying two R_VC_CF[x] "
            "values, returns credits for reuse) and CC_Update (sender to "
            "receiver, 64-byte MAC frame, low frequency, up to 16 "
            "S_VC_CC[x] values, recaptures credits leaked by link-error "
            "packet drops)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R38",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "Credit admission: pktCredits = roundup((pktSize + PktOvhd) ÷ "
            "CreditSize), pktSize being the MAC frame DA through FCS; a "
            "lossless-VC packet may be selected only when S_VC_CU[x] + "
            "pktCredits ≤ S_VC_CL[x] (per-VC method) or S_P_CU + pktCredits "
            "≤ S_P_CL (TotalCredits method, whose limit shall be "
            "observed); best-effort VCs skip the check and consume no "
            "credits; cut-through is not precluded."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R39",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Counter update laws: on selecting a lossless packet S_P_CU, "
            "S_VC_CC[x] and S_VC_CU[x] each += pktCredits; on receiving a "
            "CF_Update with valid R_VC_CF[x]: credits_returned = R_VC_CF[x] "
            "− S_VC_CF[x], then S_P_CU and S_VC_CU[x] −= credits_returned "
            "and S_VC_CF[x] = R_VC_CF[x]."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R40",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "CC_Update packets must be generated periodically covering all "
            "lossless VCs (VCs 0–15 and 16–31 ride two separate packets); "
            "the counters in a CC_Update must include all credits consumed "
            "for packets transmitted before the CC_Update and must not "
            "include any credits for packets transmitted after it; a "
            "configurable interval CC_msg_timer between CC_Update "
            "generations must be provided."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R41",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "Receiver side: compute pktCredits identically and update "
            "R_VC_CC[x] on every received packet — even when cut through "
            "without buffering — and update R_VC_CF[x] by the packet's "
            "credits when it leaves the input buffer or is cut through, "
            "making it eligible for the next CF_Update."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R42",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "CF_Update generation triggers: R_VC_CF[x] updated with "
            "CF_min_timer expired; a single CF_max_timer expired (updates "
            "needed only for VCs without an update in the interval); or a "
            "per-VC CF_max_timer[x] expired; CF_min_timer guarantees "
            "minimum message spacing for bandwidth; at least one CF_max "
            "timer (single or per-VC) must be implemented to re-send "
            "R_VC_CF values in case a CF_Update was lost."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R43",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "CC_Update reception law: for each valid S_VC_CC[x], "
            "LostCredits = S_VC_CC[x] − R_VC_CC[x]; if positive, R_VC_CF[x] "
            "+= LostCredits; then R_VC_CC[x] = S_VC_CC[x] — reclaiming "
            "leaked credits; LostCredits below zero or above 2^14−1 "
            "indicates a serious error and should be reported to the "
            "management entity."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R44",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        keyword="DEFINITIONAL",
        subject="CBFC",
        disposition="informational",
        statement=(
            "Non-ideal credit sizes (informative): pick the largest "
            "commonly supported CreditSize ≤ the receiver cell size and "
            "keep TotalCredits tied to the cell count (an 8000 B/80 B "
            "buffer at CreditSize 64 still uses TotalCredits 100); the "
            "receiver may free surplus credits early when real cell use "
            "is below computed credits, or count natively and reclaim "
            "leakage with a smaller CC_msg_timer."
        ),
    ),
    # -- 5.2.6 / 5.2.7 / 5.2.11 message formats and carriage ---------------------
    UECRequirement(
        requirement_id="UEC11-FC-R45",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_MSG",
        disposition="informational",
        statement=(
            "CF_Update is an 8-byte CtlOS on the xMII: two R_VC_CF values, "
            "each a 5-bit VC index plus 15-bit count (CF1/CF2), O-code 0x6 "
            "in D4[7:4], reserved D7[3:0] sent as zero and ignored on "
            "reception; the PCS encodes it into one 64B/66B block."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R46",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_MSG",
        disposition="informational",
        statement=(
            "CC_Update is a 64-byte MAC frame compatible with 802.3 Clause "
            "31 MAC Control: EtherType 0x8808, extension opcode 0xFFFE, UEC "
            "CID FA-7A-CB, Msg Type 0x01 (VCs 0–15) or 0x02 (VCs 16–31), "
            "sixteen 20-bit S_VC_CC values (40 B) and CRC32 FCS; it is "
            "link-local, identified by EtherType+Opcode+CID+MsgType with "
            "good FCS; MACDA/MACSA/CID configurability is recommended."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R47",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="SHALL",
        subject="CBFC_MSG",
        disposition="unsupported",
        statement=(
            "The S_VC_CC[x] value for any unused or best-effort VC shall be "
            "set to 0 in a CC_Update packet."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R48",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="MUST",
        subject="CBFC_MSG",
        disposition="unsupported",
        statement=(
            "MAC interface rules: the MAC must let CtlOS messages preempt "
            "in-progress packet transmission (enabling frequent CF_Updates) "
            "; CC_Update must be delivered via MA_DATA.request to preserve "
            "its position relative to data packets; a received CC_Update "
            "must be forwarded on MA_DATA.indication in strict packet "
            "order; CF_Update CtlOS should be stripped from the RX data "
            "path and delivered via MA_CONTROL.indication."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R49",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="MUST",
        subject="CBFC_MSG",
        disposition="unsupported",
        statement=(
            "CtlOS insertion rules: 8-byte aligned with the control "
            "character in lane 0; may preempt a packet except within its "
            "first 256 bytes, the preempted packet resuming immediately; "
            "CtlOS must stay under 2% of link bandwidth, enforced by "
            "≥ 400 B minimum spacing (should be under 0.5% normally, "
            "≈1600 B); spacing holds even across IDLE-only gaps."
        ),
    ),
    # -- 5.2.8 initialization and removal -----------------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R50",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "Network-level configuration: NumVCs identical at sender and "
            "receiver, VCs consistently configured lossless or best "
            "effort, and identical packet-property-to-VC mappings at both "
            "ends; the two directions of a link are configured "
            "independently — a station's sender and receiver functions do "
            "not interact."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R51",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "Link-level values are receiver-determined: Receiver.CreditSize "
            "= its cell size and Sender.CreditSize ≤ it as close as "
            "possible; Receiver.TotalCredits = buffer size ÷ cell size with "
            "the sender using the same number; Receiver.PktOvhd = actual "
            "per-packet space with Sender.PktOvhd ≥ it (conservative); "
            "management-software configuration of these must be possible "
            "and a link-level protocol (UE link negotiation) is desirable."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R52",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "On port reset all VCs start best effort; lossless VCs are "
            "then initialized (and later removable) via an LLDP CBFC TLV "
            "exchange without disturbing other VCs; each station keeps "
            "local and remote TLV databases; a station may act as sender "
            "and receiver but the functions are configured separately, "
            "and initialization may run simultaneously and independently "
            "per link direction."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R53",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="MUST NOT",
        subject="CBFC_INIT",
        disposition="unsupported",
        statement=(
            "LLDP packets transmitted during the lossless VC initialization "
            "process must not use any of the lossless VCs being initialized."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R54",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "CBFC TLV fields: receiver side R_NumVCs (2–32), R_TotalCredits "
            "(non-zero = port total; zero selects per-VC limits), "
            "R_CellSize, R_PktOvhd (8-bit two's complement, −16..+127), "
            "R_VC_Want[x], R_VC_RTR[x], optional R_VC_CreditLimit[x] "
            "(valid only when R_TotalCredits=0) and optional PKTID "
            "selection fields; sender side S_VC_RTS 32-bit ready-to-send "
            "bitmap, S_CreditSize (set after the remote R_CellSize) and "
            "S_PktOvhd (after the remote R_PktOvhd)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R55",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="SHALL NOT",
        subject="CBFC_INIT",
        disposition="unsupported",
        statement=(
            "The local sender shall not start sending packets using CBFC "
            "credits until both stations have completed initialization, as "
            "indicated by the sender's ready-to-send (S_VC_RTS) and the "
            "receiver's ready-to-receive (R_VC_RTR) bits in the respective "
            "LLDP databases."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R56",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "Initialization handshake: receiver initializes port + TLVs "
            "(R_VC_Want=1, RTR=0, counters reset) and advertises; sender "
            "configures limits, disables VC transmission, resets counters "
            "and waits until within the new limits (S_P_CU ≤ S_P_CL or "
            "per-VC) before setting S_VC_RTS=1; receiver then sets "
            "R_VC_RTR=1; lossless traffic is enabled where RTS and RTR are "
            "both 1; S_P_CU resets only at port reset."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R57",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "Adding lossless VCs on an active link reruns the "
            "initialization process for the new VCs (updating R_VC_Want, "
            "S_VC_RTS, R_VC_RTR); R_CellSize and R_PktOvhd must not change "
            "while other lossless VCs are active; the credit-limit method "
            "(TotalCredits vs per-VC) must match the one already chosen; "
            "R_TotalCredits may be increased."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R58",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_INIT",
        disposition="informational",
        statement=(
            "Lossless VC removal: receiver clears R_VC_Want[x]; sender "
            "stops enqueuing, drains the VC queues, redistributes credit "
            "limits, waits until within limits and clears S_VC_RTS[x]; "
            "receiver waits until the VC drained and all credits freed "
            "and returned via CF_Update before clearing R_VC_RTR[x]; the "
            "VC may then sit unused or run best effort; the original "
            "buffer is honored until the sender's RTS clears."
        ),
    ),
    # -- 5.2.9 interactions with LLR and PFC --------------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R59",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="DEFINITIONAL",
        subject="CBFC_LLR",
        disposition="informational",
        statement=(
            "LLR retransmission hazards for CBFC counters: sender counters "
            "are already incremented for packets the receiver discards in "
            "the LLR discard window; R_VC_CC must not count those (counted "
            "on accepted retransmission instead); retransmissions in the "
            "LLR replay window must not re-update S_VC_CC; an in-flight "
            "CC_Update during the discard window finds the counters "
            "uncorrelated and must be dropped without changing R_VC_CC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R60",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="MUST",
        subject="CBFC_LLR",
        disposition="unsupported",
        statement=(
            "With LLR+CBFC enabled: CC_Update packets must be "
            "LLR-eligible with a valid sequence number (discarded in the "
            "discard window); LLR-ineligible + CBFC-lossless (type B) is "
            "not allowed and lossless data packets must also be "
            "LLR-eligible; CF_Update received during the discard window "
            "must still update S_VC_CF; in the replay window "
            "S_VC_CC/S_P_CU are not updated on retransmission nor "
            "R_VC_CC for discarded packets."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R61",
        anchor_ids=("UEC11-S5.2-CBFC",),
        keyword="SHALL",
        subject="CBFC_LLR",
        disposition="unsupported",
        statement=(
            "PFC coexistence rules: PFC control packets must be "
            "LLR-ineligible, must belong to a best-effort VC, and must "
            "still be acted upon during the LLR discard window; all "
            "CC_Update packets shall be configured as CBFC best effort and "
            "use no credits; no new CC_Update shall be transmitted during "
            "the LLR replay window."
        ),
    ),
    # -- 5.2.10 compliance requirements ---------------------------------------------
    UECRequirement(
        requirement_id="UEC11-FC-R62",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "CreditSize conformance: a configurable CreditSize must be "
            "supported at least on the power-of-two set {32, 64, 128, 256, "
            "512, 1024, 2048} bytes, with finer granularities recommended "
            "(interval steps from 8 B up to 256 B across the 32–2048 B "
            "range); native cell size support is encouraged; the "
            "programmed sender CreditSize must be conservative: "
            "CreditSize ≤ the receiver's actual cell size."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R63",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        keyword="SHALL",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "PktOvhd conformance: an implementation shall support the "
            "packet overhead parameter over −16 to +127 bytes; it may "
            "quantize to coarser than one-byte granularity provided the "
            "programmed value stays conservative (PktOvhd ≥ the receiver's "
            "actual per-packet overhead)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R64",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "VC conformance (Table 5-27): implementations must support at "
            "least 2 VCs — one lossless and one best-effort — and no more "
            "than 32 (2 ≤ NumVCs ≤ 32); the number of lossless VCs must be "
            "configurable up to NumVCs; every VC must be configurable as "
            "lossless or best effort."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R65",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "Parameter conformance: configurable TotalCredits over "
            "1 ≤ TotalCredits ≤ 2^19−1 and VC_CreditLimit[x] over 1.."
            "TotalCredits; counter ranges S_P_CL/S_VC_CL/S_VC_CC/R_VC_CC "
            "0..2^20−1 and S_VC_CF/R_VC_CF 0..2^15−1; flexible mappings of "
            "{VLAN.PCP, VLAN.DEI} and of ip.dscp to VC number must be "
            "supported, for the full range or any subset."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-FC-R66",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        keyword="MUST",
        subject="CBFC",
        disposition="unsupported",
        statement=(
            "Message/timer conformance: the CF_Update CtlOS format and the "
            "CC_Update packet format must be supported as defined; "
            "CF_min_timer ≥ 800 B of wire time; a single CF_max_timer or a "
            "per-VC CF_max_timer[x] must be supported (16 KB to 1 MB with "
            "1–16384 B granularity); CC_msg_timer configurable over 1 µs "
            "to 250 ms."
        ),
    ),
)

_FREE_PARAMETERS: tuple[UECFreeParameter, ...] = (
    UECFreeParameter(
        parameter_id="UEC11-FC-F01",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        name="tfc_dest_cell_size",
        freedom=(
            "Destination receive-buffer cell sizing is free within the "
            "supported range 256–9216 bytes in 256-byte multiples "
            "(default 256 B): whole-MTU allocation vs per-packet 9216 B "
            "cells vs fine cells are all valid strategies; values are "
            "per-direction and fixed for a PDC's life."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F02",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        name="tfc_pkt_overhead",
        freedom=(
            "The per-packet overhead constant is a deployment/configuration "
            "choice between 0 and 256 bytes (configurability recommended, "
            "default and optional fixed value 256 B), provided source and "
            "destination use the same value and set it out of band before "
            "the PDC carries data."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F03",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        name="tfc_initial_credit",
        freedom=(
            "Initial TFC credit must only be at least tfc_pkt_overhead "
            "(or a larger configured value when the overhead is 0); how "
            "much larger is an implementation/deployment decision."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F04",
        anchor_ids=("UEC11-S3.6.15-TFC",),
        name="tfc_ccc_sharing",
        freedom=(
            "Whether multiple TFC PDCs share one CCC (with a common credit "
            "pool) or get separate CCCs is source-controlled and should be "
            "a configurable option."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F05",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        name="cbfc_creditsize",
        freedom=(
            "Beyond the mandatory power-of-two CreditSize set, which "
            "values an implementation supports (native cell size, "
            "interval-step values) is open, as is the negotiated choice — "
            "constrained only by sender CreditSize ≤ receiver cell size."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F06",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        name="cbfc_pktovhd_quantization",
        freedom=(
            "PktOvhd granularity (1 B up to any conservative coarser "
            "quantization within −16..+127) is an implementation choice."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F07",
        anchor_ids=("UEC11-S5.2-CBFC",),
        name="cbfc_credit_limit_method",
        freedom=(
            "Whether the receiver sets a port-wide TotalCredits (sender "
            "distributes) or per-VC VC_CreditLimit[x] is a per-link, "
            "per-direction choice; it must merely stay consistent across "
            "the link's established lossless VCs (no mixing)."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F08",
        anchor_ids=("UEC11-S5.2-CBFC",),
        name="cbfc_credit_distribution",
        freedom=(
            "Under the TotalCredits method, how the sender distributes "
            "credits across lossless VCs (dedicated limits, shared pools, "
            "combinations) is implementation-specific, bounded only by the "
            "no-blocking requirement between lossless VCs."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F09",
        anchor_ids=("UEC11-S5.2.10-CBFC-COMPLIANCE",),
        name="cbfc_timer_values",
        freedom=(
            "CF_min_timer (≥ 800 B wire time), the CF_max_timer variant "
            "and value (16 KB–1 MB, single or per-VC) and CC_msg_timer "
            "(1 µs–250 ms) are configurable within their conformance "
            "ranges; the chosen values are deployment decisions."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F10",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        name="cbfc_vc_mapping",
        freedom=(
            "Which header fields (VLAN.PCP/DEI, ip.dscp, or subsets) map "
            "to which VC numbers, and the precedence when both are used, "
            "are configuration choices — constrained only by sender/receiver "
            "consistency; network-level VC/PFC-TC mapping mechanisms are "
            "explicitly implementation-specific."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F11",
        anchor_ids=("UEC11-S5.2-CBFC",),
        name="cbfc_pfc_resource_split",
        freedom=(
            "When CBFC and PFC run simultaneously, which switch resource "
            "each mechanism manages (e.g. CBFC the main input buffer, PFC "
            "a second buffering point or per-packet resource) is a "
            "deployment decision."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-FC-F12",
        anchor_ids=("UEC11-S5.2.5-CBFC-OPERATION",),
        name="cbfc_nonideal_credit_strategy",
        freedom=(
            "When CreditSize is below the receiver's native cell size, the "
            "receiver may choose between early credit freeing when real "
            "cell use is below computed credits, or native cell accounting "
            "with more frequent CC_Update (smaller CC_msg_timer) to "
            "reclaim leakage — the informative section presents both."
        ),
    ),
)


def requirements() -> tuple[UECRequirement, ...]:
    """All credits/flow-control requirement objects of this stage."""
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
            f"UEC credits/flow-control semantic objects failed validation: "
            f"{detail}{more}"
        )
