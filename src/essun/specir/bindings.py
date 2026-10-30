"""Requirement-to-backend bindings: what "simulated_behavior" executes.

Design doc D1 (2026-10-29): a requirement's disposition may become
``simulated_behavior`` only when the requirement is **bound** to a backend
capability/parameter that actually affects outputs. This module is the
machine-readable form of that sentence: a :class:`RequirementBinding`
names the requirement (with its anchors), the backend and the concrete
parameters that carry its semantics, the law the binding executes, the
invariants the backend enforces structurally, and the observables the
binding can move. :func:`check_binding` re-verifies every claim against
the live requirement registry, the live anchor registry, the live backend
module and the observable registry — a binding whose backend lost its
parameter, whose requirement was reworded into a different anchor, or
whose observables fell out of the registry is a HARD ERROR, not a silent
drift.

Honesty contract (the flagship-slice reading of D1): ``simulated_behavior``
is a claim about the BINDING — the requirement's semantics causally
affect backend outputs through a declared parameter — and nothing more.
It is NOT a claim of physical validity: no model here is calibrated
against UEC hardware, and the binding's numeric parameters are FREE
except where a spec-derived constant is named with its requirement id.

The flagship binding (build order item 2, 2026-10-29)
-----------------------------------------------------

**UEC11-FC-R02** — UEC 1.1 §3.6.15 Transport Flow Control, MUST NOT: "a
source must not transmit a packet if it does not have credit" — the
admission law of UEC's end-to-end flow control. Bound to
``analytical_l0_tfc`` (``src/essun/backends/analytical/l0_tfc.py``): a
per-pair credit window ``tfc.window_bytes`` caps each ring neighbor
pair's steady rate at ``W / (L + L_cr)``; the ring AllReduce completion
time (O-CCT) changes exactly when the window falls below the
bandwidth-delay product, and converges to the landed L0 identity exactly
at ``W >= B * (L + L_cr)``.

The credit-family S2 binding (G2 ladder, 2026-10-30)
-----------------------------------------------------

**UEC11-FC-R08** — UEC 1.1 §3.6.15 TFC, DEFINITIONAL: the ROUNDUP
cell-quantization law of credit consumption, ``credit_used =
ROUNDUP(tfc_pkt_size / tfc_dest_cell_size) * tfc_dest_cell_size``. Bound
to the same ``analytical_l0_tfc`` backend through the OPT-IN parameter
``tfc_dest_cell_size`` (a topology that declares no cell runs the
flagship R02 identity with byte-identical observations): per-packet
consumed credit ``cq = ROUNDUP(c/cell) * cell`` with the ring chunk
``c = M/r`` as ``tfc_pkt_size``, and the effective data rate
``min(B, (c/cq) * W/(L+L_cr))`` — quantization waste spends credit
without moving bytes. The convergence anchor is the zero-waste boundary:
``c ≡ 0 (mod cell)`` gives ``cq = c`` and the identity equals the landed
R02 identity EXACTLY. The cell's supported values (integral 256-byte
multiples in 256..9216 B) are cited to **UEC11-FC-R07**, whose own
implementation-support disposition stays ``unsupported`` — the same
pattern as R05's credit unit inside the flagship binding (values in,
obligation out).

Choice record for S2 (decision relevance, per the G2 ladder plan):
destination cell sizing is a real UEC receive-buffer decision the spec
itself names (fine 256-B cells vs per-packet 9216-B cells — R08's own
worked example), and its cost is exactly the quantization waste the law
computes; executable today as an exact closed-form rate identity on the
landed flagship construction. Deferred by design: the per-packet
overhead constant (FC-R09, stage S3 — entering ``tfc_pkt_size``; at S2
the chunk IS the packet, a registered assumption), and FC-R07/R10 as
promotions (no admissible-config enforcement path exists;
implementation-support semantics).

Choice record (decision relevance, not convenience):

- CHOSEN UEC11-FC-R02 because TFC credit provisioning is a real UEC
  deployment decision: granted credit (in 256-byte units, UEC11-FC-R05)
  versus achievable transfer rate is the fabric-architect's
  buffering-vs-throughput trade-off, executable today as an exact
  closed-form identity on the existing ring construction.
- REJECTED UEC11-CM-R66 (§3.6.14 RCCC pull-credit admission, "a source
  cannot send with credit at or below zero"): equally normative in
  spirit and decision-relevant (incast), but RCCC credit is scheduled by
  the destination across MULTIPLE concurrent sources from advertised
  backlog (UEC11-CM-R67); executing it honestly needs multi-flow
  contention, which no backend models. Promoting it now would simulate a
  single-flow shadow of the mechanism — the honest disposition stays
  ``informational`` (DEFINITIONAL keyword).
- REJECTED the CBFC link-credit family (§5.2, representative
  UEC11-FC-R36: credit counters sized by link RTT and receiver buffer):
  hop-level backpressure changes outputs only through queue-occupancy
  dynamics propagating across hops — a queueing fidelity the analytical
  family explicitly excludes (``congestion`` and queueing are declared
  unsupported by every L0 model). An honest binding needs that fidelity
  first; the disposition stays ``informational``.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from .anchors import AnchorRegistry
from .uec_link_transport import DISPOSITIONS

#: The five stage modules that own UEC requirement objects (same set as
#: tests/specir/test_dispositions.py STAGE_MODULES).
UEC_REQUIREMENT_MODULES: tuple[str, ...] = (
    "essun.specir.uec_link_transport",
    "essun.specir.uec_reliability_ordering",
    "essun.specir.uec_congestion_management",
    "essun.specir.uec_credits_flow_control",
    "essun.specir.uec_f07_mechanisms",
)


class BindingError(Exception):
    """A requirement binding is inconsistent with the live registries."""


@dataclass(frozen=True)
class RequirementBinding:
    """One machine-readable requirement -> backend binding (D1)."""

    binding_id: str
    requirement_id: str
    anchor_ids: tuple[str, ...]
    disposition: str  # must equal the requirement object's disposition
    backend_module: str  # import path of the backend module
    backend_id: str  # module.BACKEND_ID
    capability: str  # must equal module.CAPABILITIES["transport_model"]
    #: Config fields (TFCRingConfig-style names) whose values carry the
    #: requirement's semantics; the binding check verifies each exists on
    #: the backend's config dataclass via its ``config_field_names()``.
    parameters: tuple[str, ...]
    #: The exact law the backend executes for this requirement.
    parameter_effect: str
    #: What the backend enforces structurally (never merely checked).
    enforced_invariants: tuple[str, ...]
    #: Observables the binding can move (must be registered AND declared
    #: by the backend's CAPABILITIES).
    observable_ids: tuple[str, ...]
    #: Spec-derived constants the binding uses, each cited by the
    #: requirement id that anchors it (provenance rule: no invented
    #: normative values).
    spec_derived_constants: tuple[tuple[str, str, str], ...]
    #: Where the executed golden test lives.
    golden_test: str
    notes: str = ""


BINDING_UEC11_FC_R02_L0TFC = RequirementBinding(
    binding_id="BIND-UEC11-FC-R02-L0TFC",
    requirement_id="UEC11-FC-R02",
    anchor_ids=("UEC11-S3.6.15-TFC",),
    disposition="simulated_behavior",
    backend_module="essun.backends.analytical.l0_tfc",
    backend_id="analytical_l0_tfc",
    capability="tfc_credit_windowed_ring",
    parameters=("tfc_window_bytes", "tfc_credit_return_latency_ns"),
    parameter_effect=(
        "effective per-link rate = min(B, W / (L + L_cr)); ring AllReduce "
        "completion t = 2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L"
    ),
    enforced_invariants=(
        "peak in-flight bytes toward one CCC destination = "
        "min(B,L_rate-cap) * RTT <= W always (equality iff window-limited)",
        "tfc_window_bytes must be an integral number of 256-byte credit "
        "units; non-grantable windows are rejected at load time",
    ),
    observable_ids=("O-CCT", "O-CONSERVATION"),
    spec_derived_constants=(
        ("tfc_credit_unit_bytes", "256", "UEC11-FC-R05"),
    ),
    golden_test="tests/golden/test_l0_tfc_golden.py",
    notes=(
        "Convergence anchor: at W >= B*(L+L_cr) the identity equals the "
        "landed L0 ring equation exactly (credits never gate). E0 evidence "
        "level: identity and determinism only; free parameters B, L, W, "
        "L_cr are not standard-derived and not measured."
    ),
)

#: The credit-family S2 binding (G2 ladder, 2026-10-30): UEC11-FC-R08's
#: ROUNDUP cell-quantization law as a steady-state rate identity on the
#: same backend. Opt-in parameter: a topology without tfc.dest_cell_size
#: executes the flagship identity only.
BINDING_UEC11_FC_R08_L0TFC = RequirementBinding(
    binding_id="BIND-UEC11-FC-R08-L0TFC",
    requirement_id="UEC11-FC-R08",
    anchor_ids=("UEC11-S3.6.15-TFC",),
    disposition="simulated_behavior",
    backend_module="essun.backends.analytical.l0_tfc",
    backend_id="analytical_l0_tfc",
    capability="tfc_credit_windowed_ring",
    parameters=("tfc_dest_cell_size",),
    parameter_effect=(
        "per-packet consumed credit cq = ROUNDUP(c/cell) * cell with the "
        "ring chunk c = M/r as tfc_pkt_size (overhead deferred to S3's "
        "FC-R09 law); effective data rate = min(B, (c/cq) * W/(L+L_cr)); "
        "ring AllReduce completion t = 2*(r-1)/r * M / min(B, "
        "(c/cq)*W/(L+L_cr)) + 2*(r-1)*L"
    ),
    enforced_invariants=(
        "per-op in-flight data bytes = Rd*(L+L_cr) <= (c/cq)*W with "
        "equality iff the quantized window gates; credit bytes in flight "
        "<= W always (a cell gates rate, never byte count)",
        "tfc_dest_cell_size must be an integral 256-byte multiple in "
        "256..9216 bytes (values cited to UEC11-FC-R07); out-of-domain "
        "cells are rejected at load time citing the requirement",
    ),
    observable_ids=("O-CCT", "O-CONSERVATION"),
    spec_derived_constants=(
        (
            "tfc_dest_cell_size_min_bytes",
            "256",
            "UEC11-FC-R07",
        ),
        (
            "tfc_dest_cell_size_max_bytes",
            "9216",
            "UEC11-FC-R07",
        ),
        (
            "tfc_dest_cell_size_granularity_bytes",
            "256",
            "UEC11-FC-R07",
        ),
    ),
    golden_test="tests/golden/test_l0_tfc_cell_golden.py",
    notes=(
        "Zero-waste convergence anchor: c == 0 (mod cell) => cq = c => "
        "the identity equals the landed R02 identity exactly (cells gate "
        "credit efficiency, the window gates rate). E0 evidence level: "
        "identity and determinism only; the cell is FREE within the "
        "R07-cited domain; B, L, W, L_cr stay the flagship's free "
        "parameters. The chunk-as-packet mapping and the fluid "
        "steady-window reading are registered assumptions "
        "(experiments/vertical_slice/assumptions_tfc_cell.yaml), not "
        "spec facts."
    ),
)

#: The registry of live bindings. Adding one is a reviewed act: the
#: requirement's disposition must be flipped to the binding's disposition
#: in its stage module in the same commit, EXPECTED_COUNTS in
#: tests/specir/test_dispositions.py updated, and the binding's golden
#: test must be green (the no-silent-promotion gate).
BINDINGS: tuple[RequirementBinding, ...] = (
    BINDING_UEC11_FC_R02_L0TFC,
    BINDING_UEC11_FC_R08_L0TFC,
)


def requirement_index() -> dict[str, object]:
    """Live requirement_id -> UECRequirement across the five stage modules."""
    index: dict[str, object] = {}
    for module_name in UEC_REQUIREMENT_MODULES:
        module = importlib.import_module(module_name)
        for req in module.requirements():
            if req.requirement_id in index:
                raise BindingError(
                    f"duplicate requirement id {req.requirement_id} across "
                    f"stage modules"
                )
            index[req.requirement_id] = req
    return index


def check_binding(
    binding: RequirementBinding,
    registry: AnchorRegistry,
    requirements: dict[str, object] | None = None,
) -> list[str]:
    """Re-verify a binding against the live registries; [] = consistent.

    Checks: the requirement exists and its disposition equals the
    binding's; the binding cites exactly the requirement's anchors and
    they resolve; the backend module imports, declares the backend id,
    capability and parameters (via ``config_field_names()``); every named
    observable is registered in the observable registry AND declared by
    the backend's CAPABILITIES; every spec-derived constant matches the
    backend module's constant and cites a real requirement id.
    """
    problems: list[str] = []
    if binding.disposition not in DISPOSITIONS:
        problems.append(
            f"{binding.binding_id}: disposition {binding.disposition!r} not "
            f"in D1 vocabulary {DISPOSITIONS}"
        )
    requirements = requirements if requirements is not None else requirement_index()
    req = requirements.get(binding.requirement_id)
    if req is None:
        problems.append(
            f"{binding.binding_id}: requirement {binding.requirement_id} not "
            "found in the live stage registries"
        )
        return problems
    if req.disposition != binding.disposition:  # type: ignore[attr-defined]
        problems.append(
            f"{binding.binding_id}: requirement {binding.requirement_id} has "
            f"disposition {req.disposition!r} but the binding claims "  # type: ignore[attr-defined]
            f"{binding.disposition!r} — flip the requirement (same commit, "
            "update EXPECTED_COUNTS)"
        )
    if tuple(req.anchor_ids) != binding.anchor_ids:  # type: ignore[attr-defined]
        problems.append(
            f"{binding.binding_id}: anchors {binding.anchor_ids} != "
            f"requirement anchors {tuple(req.anchor_ids)}"  # type: ignore[attr-defined]
        )
    try:
        registry.resolve(list(binding.anchor_ids))
    except Exception as exc:  # AnchorRegistryError
        problems.append(
            f"{binding.binding_id}: anchors do not resolve: {exc}"
        )

    try:
        backend = importlib.import_module(binding.backend_module)
    except ImportError as exc:
        problems.append(
            f"{binding.binding_id}: backend module {binding.backend_module} "
            f"does not import: {exc}"
        )
        return problems
    if getattr(backend, "BACKEND_ID", None) != binding.backend_id:
        problems.append(
            f"{binding.binding_id}: backend id mismatch (module declares "
            f"{getattr(backend, 'BACKEND_ID', None)!r})"
        )
    capabilities = getattr(backend, "CAPABILITIES", {})
    if capabilities.get("transport_model") != binding.capability:
        problems.append(
            f"{binding.binding_id}: backend transport_model "
            f"{capabilities.get('transport_model')!r} != {binding.capability!r}"
        )
    try:
        declared_fields = set(backend.config_field_names())
    except AttributeError:
        problems.append(
            f"{binding.binding_id}: backend {binding.backend_id} does not "
            "expose config_field_names() for parameter checks"
        )
        declared_fields = set()
    for parameter in binding.parameters:
        if parameter not in declared_fields:
            problems.append(
                f"{binding.binding_id}: parameter {parameter!r} is not a "
                f"config field of {binding.backend_id} "
                f"(fields: {sorted(declared_fields)})"
            )

    from ..observables import lookup as lookup_observable

    for observable_id in binding.observable_ids:
        if observable_id not in capabilities.get("observables", ()):
            problems.append(
                f"{binding.binding_id}: observable {observable_id} not "
                f"declared by {binding.backend_id} CAPABILITIES"
            )
        try:
            lookup_observable(observable_id)
        except Exception as exc:  # unknown observable
            problems.append(
                f"{binding.binding_id}: observable {observable_id} not in "
                f"the observable registry: {exc}"
            )

    for name, value, source_requirement in binding.spec_derived_constants:
        module_value = getattr(backend, name.upper(), getattr(backend, name, None))
        if module_value is None or str(module_value) != value:
            problems.append(
                f"{binding.binding_id}: spec-derived constant {name}={value} "
                f"not found on backend (module has {module_value!r})"
            )
        if source_requirement not in requirements:
            problems.append(
                f"{binding.binding_id}: spec-derived constant {name} cites "
                f"unknown requirement {source_requirement}"
            )
    return problems


def check_all(registry: AnchorRegistry) -> list[str]:
    """Check every registered binding; [] = the ladder is consistent."""
    problems: list[str] = []
    seen: dict[str, str] = {}
    for binding in BINDINGS:
        if binding.binding_id in seen:
            problems.append(f"duplicate binding id {binding.binding_id}")
        seen[binding.binding_id] = binding.requirement_id
        problems.extend(check_binding(binding, registry))
    return problems


def assert_valid(registry: AnchorRegistry) -> None:
    problems = check_all(registry)
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise BindingError(
            f"requirement bindings failed consistency: {detail}{more}"
        )
