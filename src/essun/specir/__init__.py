"""SpecIR: source-anchored representation of standard semantics (WS1)."""

from __future__ import annotations

from .anchors import (
    MAX_QUOTE_WORDS,
    Anchor,
    AnchorRegistry,
    AnchorRegistryError,
    normalize_whitespace,
)
from .uec_link_transport import (
    DISPOSITIONS,
    NORMATIVE_KEYWORDS,
    S2_ANCHOR_IDS,
    SUBJECTS,
    UECFreeParameter,
    UECRequirement,
    SemanticObjectError,
    all_objects,
    anchor_ids,
    assert_valid,
    check_against_registry,
    disposition_problems,
    free_parameters,
    initial_disposition,
    requirements,
)

# S2 keeps its direct package-root exports above (established surface).  The
# S3 stage module (reliability & ordering) reuses the S2 object model and
# vocabularies and defines its own object tuples and check functions with the
# same names; import it as a module rather than re-exporting its helpers to
# avoid shadowing: essun.specir.uec_reliability_ordering.<helper>.
from . import uec_reliability_ordering  # noqa: E402,F401  (S3, name-addressable)

# The S4 stage module (congestion management / UET CMS / CSIG) follows the
# same rule: essun.specir.uec_congestion_management.<helper>.
from . import uec_congestion_management  # noqa: E402,F401  (S4, name-addressable)

# The S5 stage module (credits / flow control: TFC, RCCC pull-credit
# residue, CBFC) follows the same rule:
# essun.specir.uec_credits_flow_control.<helper>.
from . import uec_credits_flow_control  # noqa: E402,F401  (S5, name-addressable)

# The S6 capstone (profile vs L0 assumption reconciliation) follows the
# same rule: essun.specir.uec_l0_reconciliation.<helper>.
from . import uec_l0_reconciliation  # noqa: E402,F401  (S6, name-addressable)

# The F07 mechanism-list extension (added under the ladder's
# continuation rule: 3.4.9 memory model, 3.5.23 RUDI, 5.3.2.2
# CBFC TLV, 2.4 INC detail, 6.1.x PHY rates) follows the same rule:
# essun.specir.uec_f07_mechanisms.<helper>.
from . import uec_f07_mechanisms  # noqa: E402,F401  (S2b, name-addressable)

# Per-profile disposition coverage report (design doc D1 gate; ladder S2
# of the dispositions/profile work): computed live, printable via
# tools/disposition_coverage.py or make disposition-report.
from . import disposition_coverage  # noqa: E402,F401  (D1 report)

# The versioned D2 profile format: schema + loader for the ten-element
# artifact (ladder S3; UEC/UnifiedBus migration is S4/S5, not done here).
from . import profile_format  # noqa: E402,F401  (D2 format)

__all__ = [
    "MAX_QUOTE_WORDS",
    "Anchor",
    "AnchorRegistry",
    "AnchorRegistryError",
    "normalize_whitespace",
    "DISPOSITIONS",
    "NORMATIVE_KEYWORDS",
    "S2_ANCHOR_IDS",
    "SUBJECTS",
    "UECFreeParameter",
    "UECRequirement",
    "SemanticObjectError",
    "all_objects",
    "anchor_ids",
    "assert_valid",
    "check_against_registry",
    "disposition_problems",
    "free_parameters",
    "initial_disposition",
    "requirements",
    "uec_reliability_ordering",
    "uec_congestion_management",
    "uec_credits_flow_control",
    "uec_l0_reconciliation",
    "uec_f07_mechanisms",
    "disposition_coverage",
    "profile_format",
]
