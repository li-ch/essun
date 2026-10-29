"""UEC 1.1 link/transport semantics: stage S2 semantic objects (T010/T011).

First mechanism slice of the UEC semantic profile ladder: the structural
semantics of the UE transport (UET) and the UE link layer — layering, sublayer
responsibilities, profiles, SES semantic concepts, packetization, LLR, link
negotiation, and optimized headers (UFH).  Reliability/ordering mode semantics
(S3), congestion management (S4) and credits/flow control (S5) get their own
modules in later stages.

Every object is a mapping ``requirement id -> anchor ids -> typed statement``
(provenance rule: every standard-derived value keeps a source anchor).
Two object kinds exist:

- :class:`UECRequirement` — a statement the spec attaches a normative keyword
  to (MUST / SHALL / SHOULD / MAY variants), or a ``DEFINITIONAL`` statement
  (load-bearing structure facts; §3 itself states its overview is informative
  outside §3.3, so overview facts are typed DEFINITIONAL, never MUST).
  Every requirement also carries a ``disposition`` (:data:`DISPOSITIONS`,
  design doc D1): how the platform executes it — an anchored requirement
  count is not executable coverage, so "not executed" is an explicit,
  visible value (``informational`` / ``unsupported``), never silence.
- :class:`UECFreeParameter` — a degree of freedom the spec explicitly leaves
  open (provenance rule: "never invent normative values — use an explicit
  free parameter").  Always marked ``FREE``.

Statements are concise paraphrases in our own words, not reproduced spec text
(S0 license gate: only the anchor registry carries <= 30-word verbatim quotes).
Anchors resolve through :class:`~essun.specir.anchors.AnchorRegistry`; a
dangling anchor id is a hard error, never a silent citation
(:func:`check_against_registry` / :func:`assert_valid`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .anchors import AnchorRegistry

#: Normative keywords a requirement statement may be typed with.  DEFINITIONAL
#: covers spec text that defines structure/scope without an RFC-2119 keyword.
NORMATIVE_KEYWORDS: tuple[str, ...] = (
    "MUST",
    "MUST NOT",
    "SHALL",
    "SHALL NOT",
    "SHOULD",
    "SHOULD NOT",
    "MAY",
    "DEFINITIONAL",
)

#: Requirement dispositions (design doc D1, 2026-10-29): how the platform
#: executes an anchored requirement.  The six values are the complete set;
#: ``informational`` and ``unsupported`` are honest, visible answers.
DISPOSITIONS: tuple[str, ...] = (
    "constraint",  # admissible-config rule, enforced at compile time
    "simulated_behavior",  # bound to a backend capability/parameter; affects outputs
    "conformance_test",  # executable golden/negative check
    "informational",  # carried for understanding; deliberately not executed
    "unsupported",  # anchored but executed by no backend today
    "not_applicable",  # outside this profile's/platform's scope
)

#: Components a statement can bind ("subject" of the typed statement).
SUBJECTS: tuple[str, ...] = (
    "UET",  # transport as a whole / scope
    "PROFILES",  # profile matrix requirements
    "SES",  # semantics sublayer
    "ADDRESSING",  # SES addressing concepts
    "AUTHZ",  # SES authorization (JobID, SDI)
    "PACKETIZATION",  # payload MTU / message construction
    "PDS",  # packet delivery sublayer structure
    "LINK",  # UE link layer as a whole
    "LLR",  # link layer retry
    "NEGOTIATION",  # UE link negotiation
    "UFH",  # unified forwarding header
)

#: Statements are paraphrases, but kept crisp so objects stay reviewable.
MAX_STATEMENT_WORDS = 60

#: Anchor ids this stage is allowed to cite (mechanism-to-anchor map, S1).
S2_ANCHOR_IDS: frozenset[str] = frozenset(
    {
        "UEC11-S1.6-LAYERS-OVERVIEW",
        "UEC11-S3-TRANSPORT-LAYER",
        "UEC11-S3.1-UET-SCOPE",
        "UEC11-S3.2-UET-COMPONENTS",
        "UEC11-S3.3-PROFILES",
        "UEC11-S3.4-SES",
        "UEC11-S3.4.2-SEMANTIC-CONCEPTS",
        "UEC11-S3.5-PDS",
        "UEC11-S5-LINK-LAYER",
        "UEC11-S5.1-LLR",
        "UEC11-S5.1.3-LLR-OPERATION",
        "UEC11-S5.3-LINK-NEGOTIATION",
        "UEC11-S5.4-OPTIMIZED-HEADERS",
    }
)


@dataclass(frozen=True)
class UECRequirement:
    """One typed statement: requirement id -> anchor ids -> typed statement.

    ``disposition`` (design doc D1) records how the platform executes the
    requirement.  It is required at the registry gate: the shape check
    calls :func:`disposition_problems`, and the empty string means
    "missing", so a requirement without a disposition fails validation.
    """

    requirement_id: str
    anchor_ids: tuple[str, ...]
    keyword: str  # element of NORMATIVE_KEYWORDS
    subject: str  # element of SUBJECTS
    statement: str  # concise paraphrase, own words
    disposition: str = ""  # element of DISPOSITIONS; "" = missing (invalid)


#: Initial honest disposition of a requirement, used by the migration
#: (tools/migrate_dispositions.py) and reviewed with it: DEFINITIONAL
#: structure facts are informational; every normative statement is
#: unsupported until a binding that actually executes it exists and is
#: reviewed.  No requirement becomes simulated_behavior silently.
def initial_disposition(keyword: str) -> str:
    """Honest initial D1 disposition for a requirement of this keyword."""
    if keyword == "DEFINITIONAL":
        return "informational"
    return "unsupported"


def disposition_problems(oid: str, disposition: str) -> list[str]:
    """D1 registry gate: a requirement without a disposition is invalid.

    Every stage module's shape check calls this, so a requirement missing
    its disposition — or carrying a value outside :data:`DISPOSITIONS` —
    fails ``check_against_registry`` and with it the stage registry test.
    """
    if not disposition:
        return [f"{oid}: missing disposition (one of {DISPOSITIONS})"]
    if disposition not in DISPOSITIONS:
        return [
            f"{oid}: unknown disposition {disposition!r} "
            f"(not in {DISPOSITIONS})"
        ]
    return []


@dataclass(frozen=True)
class UECFreeParameter:
    """A degree of freedom the spec explicitly leaves open (marked FREE)."""

    parameter_id: str
    anchor_ids: tuple[str, ...]
    name: str
    freedom: str  # what the spec leaves to implementation/deployment
    domain: str = "FREE"  # always FREE by construction; never a spec value


_REQUIREMENTS: tuple[UECRequirement, ...] = (
    # -- structure and scope of the UE transport ---------------------------
    UECRequirement(
        requirement_id="UEC11-LT-R01",
        anchor_ids=("UEC11-S3-TRANSPORT-LAYER",),
        keyword="DEFINITIONAL",
        subject="UET",
        disposition="informational",
        statement=(
            "The chapter 3 overview declares that it contains no normative "
            "text outside Section 3.3; the normative requirements live in "
            "the sublayer sections (3.4 SES, 3.5 PDS, 3.6 CMS, 3.7 TSS)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R02",
        anchor_ids=("UEC11-S3-TRANSPORT-LAYER",),
        keyword="DEFINITIONAL",
        subject="UET",
        disposition="informational",
        statement=(
            "UET targets AI/HPC workloads with minimal tail latency and "
            "highest network utilization, supporting up to millions of "
            "endpoints (NIC ports) and addressing up to billions of "
            "processes."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R03",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        keyword="DEFINITIONAL",
        subject="UET",
        disposition="informational",
        statement=(
            "UET is built from four largely independent sublayers: the "
            "semantics sublayer (SES), packet delivery sublayer (PDS), "
            "congestion management sublayer (CMS), and transport security "
            "sublayer (TSS)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R04",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        keyword="DEFINITIONAL",
        subject="SES",
        disposition="informational",
        statement=(
            "SES defines addressing, authorization, message types, "
            "protocols, and semantic header formats between endpoints; it "
            "works at transaction level and packetizes messages for "
            "transmission by PDS."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R05",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        keyword="DEFINITIONAL",
        subject="SES",
        disposition="informational",
        statement=(
            "SES defines two protocols for large messages: rendezvous "
            "(sender chooses eager vs rendezvous before sending; target "
            "triggers a read once a matching receive is posted) and "
            "deferrable send (receiver defers via stop/resume when the "
            "receive buffer is not posted)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R06",
        anchor_ids=("UEC11-S3.5-PDS",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS is the part of UET responsible for delivering packets over "
            "IP/Ethernet networks; it offers reliability and ordering "
            "capabilities and sits between SES and CMS."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R07",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS generates and interprets ACK and NACK packets and uses "
            "ephemeral state; retained NIC state scales with concurrently "
            "active communications, not with total endpoint count."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R08",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS defines five packet delivery modes combining reliable/"
            "unreliable and ordered/unordered: RUD, ROD, RODL, RUDI, UUD. "
            "RODL is a ROD variation for the Unified Local profile that "
            "may omit PDS-layer retransmission, relying on mechanisms such "
            "as LLR."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R09",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "Packet delivery contexts (PDCs) are created dynamically as "
            "part of normal packet transmission without additional round "
            "trips and can be kept alive for extended periods (up to 2^31 "
            "packets)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R10",
        anchor_ids=("UEC11-S3.5-PDS",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "PDS Requests carry SES requests in the forward direction and "
            "SES responses with data in the return direction; PDS ACKs "
            "carry only SES responses; congestion control is not applied "
            "to PDS ACKs."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R11",
        anchor_ids=("UEC11-S3.5-PDS",),
        keyword="DEFINITIONAL",
        subject="PDS",
        disposition="informational",
        statement=(
            "A PDC includes a forward and a return direction with "
            "initiator and target roles fixed for its lifetime; header "
            "PDCIDs are interpreted as source/destination relative to the "
            "transmitting FEP; duplicate packets in RUD/ROD/RODL are not "
            "passed to SES and may be acknowledged."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R12",
        anchor_ids=("UEC11-S1.6-LAYERS-OVERVIEW", "UEC11-S5-LINK-LAYER"),
        keyword="DEFINITIONAL",
        subject="LINK",
        disposition="informational",
        statement=(
            "The UE link layer additions (LLR, CBFC, idle reduction/IPGR, "
            "UFH, link negotiation) are optional to implement; all UE link "
            "layer features are optional for UE compliance."
        ),
    ),
    # -- profiles (normative core of the chapter 3 overview) -----------------
    UECRequirement(
        requirement_id="UEC11-LT-R13",
        anchor_ids=("UEC11-S3.3-PROFILES", "UEC11-S3-TRANSPORT-LAYER"),
        keyword="DEFINITIONAL",
        subject="PROFILES",
        disposition="informational",
        statement=(
            "UET defines four profiles: HPC (most comprehensive), AI Base "
            "(minimal *CCL and unreliable datagram support), AI Full (all "
            "AI training/inference requirements), and Unified Local "
            "(efficient headers for local scale-up networking with write/"
            "read/atomic operations)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R14",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="SHALL",
        subject="PROFILES",
        disposition="unsupported",
        statement=(
            "An endpoint may implement any single profile or any "
            "combination; communication between two endpoints requires "
            "that both support the same profile, and interoperation "
            "within a profile shall be possible through the least common "
            "denominator feature set."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R15",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="PACKETIZATION",
        disposition="unsupported",
        statement=(
            "Multi-packet transactions such as UET_WRITE, UET_READ, and "
            "UET_SEND must use a consistent Payload MTU size; a deployment "
            "must use a consistent Payload MTU across all FEPs "
            "communicating in a fabric."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R16",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="PROFILES",
        disposition="unsupported",
        statement=(
            "Per the profile matrix, all four profiles must support NO_OP, "
            "RMA write, and non-fetching atomic transactions; required "
            "maximum write/read message size is 4GB-1 for the scale-out "
            "profiles and 16KB-1 for Unified Local."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R17",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="PROFILES",
        disposition="unsupported",
        statement=(
            "Profile matrix transaction requirements: send (max size 1 MTU "
            "for AI Base, 4GB-1 for AI Full/HPC), datagram send, and "
            "write-immediate must be supported by AI Base, AI Full, and "
            "HPC; fetching atomics including CAS must be supported by AI "
            "Full, HPC, and Unified Local; tagged send exact match "
            "by AI Full and HPC; wildcard match and tagged atomics by HPC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R18",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="PROFILES",
        disposition="unsupported",
        statement=(
            "Deferrable send and deferrable tagged send must be supported "
            "by AI Full; rendezvous with unexpected-message support must "
            "be supported by HPC; RMA read must be supported by AI Full, "
            "HPC, and Unified Local."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R19",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="ADDRESSING",
        disposition="unsupported",
        statement=(
            "Implementations of all profiles must conform to all basic "
            "buffer addressing schemes except matching; all profiles must "
            "support memory keys for UET_WRITE, and for UET_READ and "
            "UET_ATOMIC if RMA read is supported; exact matching may be "
            "implemented using wildcard matching."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R20",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="ADDRESSING",
        disposition="unsupported",
        statement=(
            "Relative addressing {FA, JobID, PIDonFEP, RI} and absolute "
            "addressing {FA, PIDonFEP, RI} must be supported by AI Base, "
            "AI Full, and HPC; direct memory addressing {FA, JobID} (RODL "
            "operations with the local request header) must be supported "
            "by Unified Local."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R21",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="AUTHZ",
        disposition="unsupported",
        statement=(
            "All profiles must implement the authorization semantics, "
            "must be able to insert the JobID, must check the JobID "
            "before allowing buffer access, and must support at least one "
            "JobID per FEP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R22",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "All fields and flags in the supported SES headers must be "
            "supported unless the profile table lists an exception; all "
            "four profiles must support the 44-byte standard header, the "
            "atomic extension, compare-and-swap, the 16-byte header "
            "response, and delivery complete with global observability."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R23",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "Profile-specific header formats: optimized non-matching (20 "
            "B) and optimized small-message (32 B) headers must be "
            "supported by AI Base; deferrable-send headers by AI Full; "
            "the optimized local transaction headers (12 B/8 B) and 4 B "
            "optimized local response by Unified Local; a Unified Local "
            "FEP must accept and process up to 16 packed messages per "
            "packet."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R24",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="MUST",
        subject="PDS",
        disposition="unsupported",
        statement=(
            "Profile matrix for PDS ordering modes: RUD, ROD, and UUD "
            "must be supported by AI Base, AI Full, and HPC; RUDI must be "
            "supported by HPC; RODL must be supported by Unified Local."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R25",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        keyword="SHOULD",
        subject="UET",
        disposition="unsupported",
        statement=(
            "An implementation should use consistent lower-layer "
            "encapsulations (IPv4 vs IPv6, UFH_16 vs UFH_32, native UET "
            "vs UDP) on all packets of a FEP, PDC, and TSS security "
            "domain."
        ),
    ),
    # -- SES semantic concepts ------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-LT-R26",
        anchor_ids=("UEC11-S3.4-SES",),
        keyword="DEFINITIONAL",
        subject="SES",
        disposition="informational",
        statement=(
            "A transaction comprises all packets that deliver one "
            "libfabric request; a message is the set of packets sharing "
            "one message ID; an operation is endpoint behavior encoded "
            "in the opcode."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R27",
        anchor_ids=("UEC11-S3.4-SES",),
        keyword="DEFINITIONAL",
        subject="SES",
        disposition="informational",
        statement=(
            "A service encapsulates the resources of a higher-level "
            "library; a Resource Index selects an addressable resource "
            "set within a service, and three Resource Index spaces exist "
            "corresponding to RMA, SEND, and TAGGED operation types."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R28",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="DEFINITIONAL",
        subject="ADDRESSING",
        disposition="informational",
        statement=(
            "Addressing selects a target endpoint and buffer via three "
            "types: relative addressing (PIDonFEP scoped by the JobID, "
            "for parallel jobs), absolute addressing (PIDonFEP without "
            "JobID, for client/server), and direct memory addressing "
            "({FA, JobID})."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R29",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="ADDRESSING",
        disposition="unsupported",
        statement=(
            "An RMA operation using an optimized header must select "
            "exactly one Resource Index, which may target a Resource "
            "Index that has exactly one RMA resource."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R30",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="ADDRESSING",
        disposition="unsupported",
        statement=(
            "The JobID must be unique for all concurrently executing jobs "
            "within the reachable network; two entities that can reach "
            "each other must have different JobIDs unless they are "
            "allowed to communicate."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R31",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="AUTHZ",
        disposition="unsupported",
        statement=(
            "The target FEP must use the JobID for isolation; the JobID "
            "must be assigned or validated by a trusted layer in the "
            "initiating node; every buffer access must validate the "
            "JobID; implementations must support at least one JobID."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R32",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="ADDRESSING",
        disposition="unsupported",
        statement=(
            "Each entity using the network stack must have a different "
            "PIDonFEP; a PIDonFEP must have a scope either relative to a "
            "JobID (relative addressing) or absolute."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R33",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "Buffer selection: a nonmatching operation must use the "
            "{JobID, PIDonFEP, Resource Index} tuple to select one "
            "buffer; a matching operation must use {JobID, PIDonFEP, "
            "Resource Index, Match Criteria}; without a memory key the "
            "tuple must select the buffer."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R34",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="ADDRESSING",
        disposition="unsupported",
        statement=(
            "Memory key namespaces must comply with the memory key "
            "structure definition; on violation the RC_BAD_MKEY error "
            "must be returned; match bits may carry a memory key, and "
            "implementations must map such a key into the match bits on "
            "the wire."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R35",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST NOT",
        subject="AUTHZ",
        disposition="unsupported",
        statement=(
            "With encryption enabled the FEP must validate that the SDI "
            "may access the endpoint; on failure the message must be "
            "dropped and reported, and neither an SES response nor a PDS "
            "NACK may be sent."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R36",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="PACKETIZATION",
        disposition="unsupported",
        statement=(
            "Implementations must break data into packets conforming to a "
            "Payload MTU; FEPs must support 4096 bytes (the default); "
            "packets must fit the path Ethernet MTU; IPv4 packets must "
            "set the don't-fragment bit; non-final packets carry exactly "
            "Payload MTU bytes; FEPs must not further fragment."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R37",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="SHOULD",
        subject="PACKETIZATION",
        disposition="unsupported",
        statement=(
            "FEP implementations should additionally support Payload MTU "
            "values of 1024, 2048, and 8192 bytes; the Payload MTU is "
            "configured out of band to one of 1024/2048/4096/8192."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R38",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="PACKETIZATION",
        disposition="unsupported",
        statement=(
            "Message construction: the first packet must carry the first "
            "PSN with som set and offset 0; packet N carries PSN = A + "
            "N - 1 and offset (N-1) * Payload MTU; the final packet sets "
            "eom; packets of one message are contiguous in PSN space; "
            "two messages must not interleave per PDC."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R39",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="PDS",
        disposition="unsupported",
        statement=(
            "For ROD, packets must be delivered to the wire in sequence "
            "number order; for RUD, packets may be delivered to the wire "
            "in any order."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R40",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "Multi-packet requests using the standard header must include "
            "a message ID; the message ID must be unique across all "
            "in-flight messages from one initiator FEP to a given target "
            "FEP per PDC; datagram sends set it to 0; it may be globally "
            "unique."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R41",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "Operations that require resolution ordering must use a ROD "
            "PDC to transport buffer-resolution information; mixed "
            "RMA/messaging ordering may use a ROD PDC, otherwise must "
            "use source-side fencing; WAR ordering via ROD requires "
            "target-side buffering."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R42",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "When wildcard matching is used with ROD, the message must "
            "consume match entries in FIFO order; with RUD the matching "
            "process should consume entries in FIFO order."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R43",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST",
        subject="SES",
        disposition="unsupported",
        statement=(
            "HPC-profile target implementations must include support for "
            "tagged operations using the matching criteria, and must "
            "support using the match-bit field of a packet as a memory "
            "key."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R44",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="MUST NOT",
        subject="SES",
        disposition="unsupported",
        statement=(
            "Use-once buffers: once a message has targeted the buffer, "
            "it may not be accessed by other messages and may not be "
            "released back to the application until the targeting "
            "operation completes; target FEPs must support use-once "
            "behavior as part of the tagged API."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R45",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        keyword="SHOULD",
        subject="SES",
        disposition="unsupported",
        statement=(
            "Target-side FEP implementations should implement support "
            "for a multi-receive capability; RMA use-once semantics are "
            "optional (MAY)."
        ),
    ),
    # -- link layer retry ------------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-LT-R46",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR is frame-based: each LLR-eligible frame gets a sequence "
            "number in the link preamble and is stored in a replay "
            "buffer; LLR_ACKs free replay space; LLR_NACKs signal missing "
            "frames; timeouts guarantee replay of eligible frames."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R47",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR sits between the MAC client and MAC control layers; "
            "pause and PFC requests/indications bypass LLR, and received "
            "pause stops only new frames from the MAC client, never the "
            "replay of previously sent frames."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R48",
        anchor_ids=("UEC11-S5.1-LLR",),
        keyword="MUST",
        subject="LLR",
        disposition="unsupported",
        statement=(
            "All frames must begin with the 8-byte UE link frame "
            "preamble; LLR-eligible frames are indicated by 0x7 in byte "
            "1 and carry a 20-bit sequence number in bytes 1-3; "
            "LLR-ineligible frames carry the standard preamble; without "
            "UE features, frames are standard 802.3 frames."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R49",
        anchor_ids=("UEC11-S5.1.3-LLR-OPERATION",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "LLR has OFF and ON modes: OFF removes LLR so the port "
            "behaves as a standard IEEE 802.3 port (no replay buffer, no "
            "sequence numbers, no filtering); ON provides lossless "
            "link-level behavior for LLR-eligible frames and standard "
            "behavior for ineligible frames."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R50",
        anchor_ids=("UEC11-S5.1.3-LLR-OPERATION",),
        keyword="DEFINITIONAL",
        subject="LLR",
        disposition="informational",
        statement=(
            "In ON mode the receive LLR filters unexpected LLR-eligible "
            "frames (missed or duplicated sequence number) and passes "
            "expected eligible and ineligible frames through; control "
            "uses four ordered-set types (LLR_ACK, LLR_NACK, LLR_INIT, "
            "LLR_INIT_ECHO) inserted pre-emptively by the PCS."
        ),
    ),
    # -- UE link negotiation ----------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-LT-R51",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="DEFINITIONAL",
        subject="NEGOTIATION",
        disposition="informational",
        statement=(
            "UE link negotiation runs over LLDP using UE organizationally "
            "specific TLVs and negotiates LLR, CBFC, IPGR, CSIG, and "
            "UFH; if a device does not support the UE TLVs the optional "
            "features are disabled (802.3 backward compatibility); "
            "configuration management may override negotiation."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R52",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="SHALL",
        subject="NEGOTIATION",
        disposition="unsupported",
        statement=(
            "LLDPDUs carrying UE TLVs shall use the nearest bridge group "
            "address; after setting a local enable flag a port shall wait "
            "for the remote enable flag before using a feature; a "
            "negotiated feature becomes operational only when both local "
            "and remote enables are TRUE."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R53",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="SHALL",
        subject="NEGOTIATION",
        disposition="unsupported",
        statement=(
            "A version 1 Options-TLV port seeing a version 0 remote shall "
            "operate with only the version 0 feature set and shall not "
            "enable any feature outside the scope of version 0; future "
            "TLV versions shall be backward-compatible with version 0 "
            "and 1."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R54",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="SHALL NOT",
        subject="NEGOTIATION",
        disposition="unsupported",
        statement=(
            "A port shall not set LLR-W to the reserved values 1 or 2; a "
            "port receiving LLR-W of 0, 1, or 2 shall disable LLR; a "
            "local port shall not begin using LLR until the remote "
            "partner sets its LLR-E flag; both partners shall enable LLR "
            "before the feature is operational."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R55",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="SHALL NOT",
        subject="NEGOTIATION",
        disposition="unsupported",
        statement=(
            "A port shall not transmit reduced idle bytes unless the "
            "remote IPGR-C flag is TRUE; a port seeing remote IPGR-C "
            "TRUE shall enable idle reduction on transmission if "
            "capable; a NULL or version 0 Options TLV behaves as "
            "IPGR-C = 0."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R56",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="SHALL NOT",
        subject="NEGOTIATION",
        disposition="unsupported",
        statement=(
            "A CSIG-capable link end facing a non-capable partner "
            "(CSIG-C = 0) shall not transmit packets with CSIG tags; a "
            "NULL or version 0 Options TLV behaves as CSIG-C = 0. "
            "(CSIG signal semantics are staged in S4.)"
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R57",
        anchor_ids=("UEC11-S5.3-LINK-NEGOTIATION",),
        keyword="SHALL",
        subject="NEGOTIATION",
        disposition="unsupported",
        statement=(
            "A port shall discard all UFH-encoded frames before "
            "transmitting onto the link until it has both partners' UFH "
            "configuration parameters; it shall choose a common operating "
            "mode if one exists; link partners shall not transmit UFH "
            "packets outside the agreed mode, and matching V/UFH "
            "parameters are required for each encoding."
        ),
    ),
    # -- optimized headers / UFH -------------------------------------------------
    UECRequirement(
        requirement_id="UEC11-LT-R58",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="DEFINITIONAL",
        subject="UFH",
        disposition="informational",
        statement=(
            "UFH is an optimized header supplementing Ethernet MAC + IP: "
            "it removes redundancies and fields unneeded in controlled "
            "fabrics while retaining coexistence with standard Ethernet "
            "and extensibility; two variations serve scale-up and "
            "scale-out fabrics; it targets well-contained domains, not a "
            "generic Ethernet+IP replacement."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R59",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="MUST",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "The UFH definition must support header stacking, must be "
            "compatible with LLR and CBFC, and must support scale-out "
            "fabrics with at least 256k endpoints (stretch goal beyond)."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R60",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="SHOULD",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "The UFH definition should support stateless translation to "
            "standard Ethernet + IP headers; the ECN field encoding "
            "should be retained to enable stateless translation between "
            "UFH and IP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R61",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="MUST",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "Packets or flows requiring unsupported features (such as IP "
            "fragmentation or tunnels) or not benefiting from header "
            "optimization must continue to use standard Ethernet and IP "
            "headers; UFH usage is optional per flow."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R62",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="MUST",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "A transmitter generating a UFH frame must set the V field "
            "to 0 (receivers verify V and W bits); UFH opaque bits can "
            "be overlaid with end-to-end data and switches must ignore "
            "them when forwarding."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R63",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="MUST",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "Tag ordering in the UFH header stack must follow Ethernet "
            "ordering rules (a VLAN tag, if present, must be the first "
            "tag at offset 12); the UFH DSCP code point of trimmed "
            "packets must be updated per the packet trimming "
            "specification."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R64",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="MAY",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "A sender may set the transport header checksum to zero for "
            "the special case of UDP over IPv4; the checksum must be "
            "ignored by a receiver; checksum calculation otherwise "
            "proceeds as if carried over IP."
        ),
    ),
    UECRequirement(
        requirement_id="UEC11-LT-R65",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        keyword="MUST",
        subject="UFH",
        disposition="unsupported",
        statement=(
            "UFH usage within a domain must be explicitly enabled using "
            "a suitable administrative approach; a UFH domain is a set "
            "of network elements that support UFH on all paths between "
            "them."
        ),
    ),
)

_FREE_PARAMETERS: tuple[UECFreeParameter, ...] = (
    UECFreeParameter(
        parameter_id="UEC11-LT-F01",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        name="multipath_path_selection",
        freedom=(
            "UET does not mandate any path selection or load-balancing "
            "algorithm (vendor differentiation); ECMP with entropy in the "
            "UDP source port / pds.entropy is an example; same-entropy "
            "packets are assumed to follow the same path."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F02",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        name="implementation_modularity",
        freedom=(
            "Implementations may choose any internal modularity as long "
            "as the external observable behavior complies with the "
            "normative directives; sublayer boundaries specify roles, "
            "not implementation structure."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F03",
        anchor_ids=("UEC11-S3.1-UET-SCOPE",),
        name="virtualization_tunnels",
        freedom=(
            "Tunneling/encapsulation details are beyond UET scope: the "
            "system administrator must ensure correct encapsulation, ECN "
            "propagation into tunnels, and entropy copying for load "
            "balancing."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F04",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS", "UEC11-S3.3-PROFILES"),
        name="payload_mtu_value",
        freedom=(
            "Payload MTU is configured out of band to 1024/2048/4096/"
            "8192 bytes (4096 default and mandatory, others should-support); "
            "the chosen value is a deployment decision constrained only by "
            "fabric-wide consistency and the path Ethernet MTU."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F05",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        name="rma_size_limit",
        freedom=(
            "Individual implementations may limit the size of RMA "
            "operations and send operations below the profile-required "
            "maxima."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F06",
        anchor_ids=("UEC11-S3.4.2-SEMANTIC-CONCEPTS",),
        name="memory_key_mechanism",
        freedom=(
            "How a memory key maps to a memory-region descriptor is "
            "solely a receiving-FEP (vendor-defined) function; hash "
            "tables and limited key ranges are permitted; FI_MR_VIRT_ADDR "
            "support is optional and FI_MR_ENDPOINT is user-settable."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F07",
        anchor_ids=("UEC11-S3.2-UET-COMPONENTS",),
        name="pdc_retention_policy",
        freedom=(
            "PDC keep-alive and cache-like management policy (up to 2^31 "
            "packets per PDC) depends on resource availability and is "
            "implementation-defined."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F08",
        anchor_ids=("UEC11-S5.1-LLR",),
        name="llr_replay_buffer_sizing",
        freedom=(
            "LLR replay-buffer sizing relative to the link bandwidth-"
            "delay product is outside the specification and is the "
            "implementer's responsibility; a configuration limits the "
            "maximum data held in the replay buffer."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F09",
        anchor_ids=("UEC11-S5.1-LLR",),
        name="llr_frame_eligibility",
        freedom=(
            "Which frames are LLR-eligible is signaled by the MAC client "
            "(frame_desire_llr) or link classification; pause and PFC "
            "frames are always LLR-ineligible."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F10",
        anchor_ids=("UEC11-S3.3-PROFILES",),
        name="profile_feature_extension",
        freedom=(
            "An empty profile-matrix cell means the feature is not "
            "required, but vendors are free to support it in enhanced "
            "profiles (e.g., AI Base + read), tracking dependencies; "
            "encryption is optional in all profiles."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F11",
        anchor_ids=("UEC11-S1.6-LAYERS-OVERVIEW",),
        name="traffic_class_configuration",
        freedom=(
            "Traffic-class configuration in the network (separating flows "
            "with different requirements) is the responsibility of the "
            "network operator, not the specification."
        ),
    ),
    UECFreeParameter(
        parameter_id="UEC11-LT-F12",
        anchor_ids=("UEC11-S5.4-OPTIMIZED-HEADERS",),
        name="ufh_flow_selection",
        freedom=(
            "UFH usage is optional; an initiator decides per data flow "
            "whether to use UFH, and should use it only for flows that "
            "benefit from header optimization."
        ),
    ),
)


class SemanticObjectError(Exception):
    """Raised when a UEC semantic object fails validation."""


def requirements() -> tuple[UECRequirement, ...]:
    """All link/transport requirement objects of this stage."""
    return _REQUIREMENTS


def free_parameters() -> tuple[UECFreeParameter, ...]:
    """All free-parameter objects of this stage."""
    return _FREE_PARAMETERS


def all_objects() -> tuple[UECRequirement | UECFreeParameter, ...]:
    """Requirements and free parameters together."""
    return _REQUIREMENTS + _FREE_PARAMETERS


def anchor_ids() -> frozenset[str]:
    """Every anchor id cited by any object of this stage."""
    return frozenset(
        aid for obj in all_objects() for aid in obj.anchor_ids
    )


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


def check_against_registry(
    registry: "AnchorRegistry",
) -> list[str]:
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
            f"UEC link/transport semantic objects failed validation: "
            f"{detail}{more}"
        )
