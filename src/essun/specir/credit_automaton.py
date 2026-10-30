"""The credit obligation automaton: UEC11-FC-R02 executed as a discrete state machine.

G8 (2026-10-30, research-track foundation): the platform's one
``simulated_behavior`` requirement is now executed by an EXACT discrete
automaton — the behavioral ground truth — and the analytical steady-state
law that previously executed it directly becomes the automaton's DECLARED
abstraction, with the conditions and exact divergences stated and tested
in this module.  The binding is
``BIND-UEC11-FC-R02-AUTOMATON`` (:mod:`essun.specir.bindings`); the
declared abstraction is the ``analytical_l0_tfc`` identity — equation (3)
of the paper draft (``\\label{eq:tfc}``,
``t = 2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L``).

The machine (integer arithmetic only; exact Fractions in the derived
laws; no floats anywhere):

- ONE credit context per link (one sender toward one neighbor pair), the
  per-link credit balance the requirement guards.  State: ``credit_bytes``
  in ``[0, W]`` plus the multiset of pending return events.
- ``attempt(t, s)`` — a transmit attempt at integer time ``t`` of ``s``
  bytes: all credit returns due at or before ``t`` are applied first,
  then the admission law (UEC 1.1 §3.6.15, MUST NOT: "a source must not
  transmit a packet if it does not have credit") decides: with
  ``credit >= s`` the transmit EXECUTES (``credit -= s``; a return event
  restoring ``s`` is scheduled at ``t + D``), else the transmit does not
  happen and THE TRACE IS REJECTED — the automaton never executes a
  transmit without credit; the rejection names the offending event and
  leaves the state untouched.
- ``D = L + L_cr`` is the credit-loop round trip (data forward one hop
  ``L``, credit return ``L_cr``) measured from the admission instant —
  the same reading the analytical law's rate cap is built on, recorded
  here as assumption A-CA-RT rather than smuggled in.

The greedy executor (the achieving schedule).  A work-conserving sender
serialized on the link at ``B`` bytes/ns transmits whenever the link is
free AND credit admits.  ``serialization u = s / B`` is kept integral
(``B | s``, assumption A-CA-SER) so every event time is an integer.

The abstraction theorem (bound + conditions; every clause tested in
tests/golden/test_credit_automaton_golden.py and
tests/specir/test_credit_automaton.py — the automaton is the ground
truth, the closed forms are verified against its execution):

1. SAFETY (any legal trace).  A transmit is admitted only if the bytes
   with start times in the half-open credit window ``(t - D, t]`` sum to
   at most ``W``.  Hence no legal trace admits more than ``W`` bytes per
   ``D`` — the admission law IS a sliding-window bound, structurally.
2. ACHIEVABILITY (greedy is optimal).  With ``k = floor(W/s)`` packets
   per window, greedy admits exactly ``k`` packets per ``D`` in the
   credit-gated regime and keeps the link continuously busy in the
   link-limited regime, where the criterion is
   ``ceil(D/u) <= floor(W/s)`` (link-paced starts inside one credit
   window must fit the granted window).  The maximum legal steady rate is
   therefore EXACTLY ``R_auto = min(B, k*s / D)`` — the quantized rate
   law.  Eq. 3's ``Reff = min(B, W/D)`` is its ``s -> 0`` limit.
3. RATE ABSTRACTION.  ``Reff >= R_auto`` always (the analytical law is
   optimistic by exactly the credit quantization): the gap is 0 iff the
   automaton saturates the link (which for ``s | W`` coincides with
   Eq. 3's own convergence anchor ``W >= B*(L+L_cr)``), and otherwise
   exactly ``(W mod s) / D`` < ``s/D`` — zero iff ``s | W``.
   So: Eq. 3's rate law equals the automaton's steady state EXACTLY
   when the packet size divides the granted window.
4. FINITE-COLLECTIVE DIVERGENCE (exact).  For a finite transfer of
   ``n = q*k + r`` packets the greedy completion (last start + ``u`` +
   hop latency ``L``) diverges from Eq. 3's single-link reduction
   ``M/Reff + L`` by EXACTLY: ``0`` in the link-limited regime;
   ``k*u - D`` when ``r == 0``; ``r*(u - D/k)`` when ``r >= 1`` — in the
   credit-gated regime strictly between ``-D`` and ``0``: the
   steady-state law overestimates a finite collective's completion by
   less than one credit-loop round trip, and the overestimate vanishes
   relatively as ``n`` grows (the steady-state convergence).

Conditions C1-C5 (each an explicit assumption entry in
experiments/vertical_slice/assumptions_credit_automaton.yaml): C1
``s | W`` (whole-packet credit grants); C2 ``B | s`` (integer
serialization grid); C3 a greedy work-conserving sender (the achieving
schedule); C4 fixed ``D = L + L_cr`` from the admission instant (steady
granted-window reading — no credit-request/grant protocol dynamics);
C5 steady state (``T >> D``; finite transfers diverge exactly as in
clause 4).  Eq. 3 is the automaton's abstraction under C1-C5 — NOT a
consequence of FC-R02's safety rule alone: the safety rule gives the
window bound; the rate law additionally needs C1-C4, and the completion
identity needs C5.  This is the G6 correction stated executable.

Driven by the anchored FC requirements: UEC11-FC-R02 (MUST NOT,
anchor UEC11-S3.6.15-TFC) is the admission transition and the rejection
semantics; UEC11-FC-R05 (DEFINITIONAL, same anchor) supplies the ONLY
standard-derived constant, the 256-byte credit unit – windows are
granted in whole units and non-grantable windows are rejected at load
time citing the requirement (same discipline as the analytical backend).
:func:`check_requirements` re-verifies both objects against the live
stage registry so the automaton cannot drift from its anchors.

G7 (2026-10-30) — the MULTI-SOURCE SHARED-LINK CONTENTION extension
(the p8 pre-registered follow-up): two or more flows (independent
finite collectives, each with its OWN per-source credit context, the
TFC per-PDC-pair shape) serialize on ONE shared link at ``B``.  The
admission machine per flow is unchanged (one
:class:`CreditAdmissionAutomaton` per context); the new executor adds
only the LINK serializer and an ARBITRATION rule among credit-ready
flows (assumption A-CA-ARB: a declared free choice — the standard does
not pin it, and Eq. 3 does not compose across flows).  What this
resolves that the analytical law alone cannot (exact, goldens G7-A/B):

1. THE WINDOW-NEVER-BINDS CASE (golden G7-A).  Two flows whose windows
   never gate (``n_i <= floor(W_i/s_i)``): each flow's per-flow law
   predicts its alone time ``M_i/B + L`` — but the two predictions are
   JOINTLY INFEASIBLE on one shared link.  The machine gives the exact
   per-flow completions, and they MOVE with the arbitration freedom
   while every flow parameter stays identical (per-flow observable
   spread ``(n_0 - 1) * u`` between index-priority and round-robin).
2. THE GATED BURST-INTERACTION CASE (golden G7-B).  Both windows gate:
   the machine's trace interleaves per-flow credit rhythms with the
   shared serializer — the link can go IDLE with every flow backlogged
   (both contexts drained, returns not yet due), and the collective's
   completion lands at an exact value BOTH fluid compositions (per-flow
   ``min(B, W_i/D)`` and aggregate ``min(B, sum(W_i)/D)``) miss, in
   either direction, by exact amounts that depend on the arbitration.

Scope honestly NOT executed (declared unsupported in CAPABILITIES):
credit-request/grant protocol dynamics (a steady granted window is the
modeled abstraction), TFC retransmission credit exemption (FC-R06),
shared-CCC pooling (FC-R16), cell-quantized credit consumption (FC-R08
— staged separately on the analytical backend by the credit-family
ladder), CBFC hop credits (§5.2), RCCC receiver-driven multi-source
credit GRANT scheduling (§3.6.14 — this extension executes contention
among independent granted windows on a shared link, not the receiver's
grant-arbitration algorithm), packet loss and credit-timer recovery
(FC-R19), multi-LINK topologies (multi-hop paths, crossing links), and
variable return timing.  B, L, L_cr, W, s are FREE parameters (not
standard-derived, not measured).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from fractions import Fraction

BACKEND_ID = "credit_admission_automaton"

#: The binding this module executes (essun.specir.bindings).
BINDING_ID = "BIND-UEC11-FC-R02-AUTOMATON"

#: The requirement objects this automaton is driven by (live stage
#: registry essun.specir.uec_credits_flow_control; checked by
#: :func:`check_requirements`).
REQUIREMENT_ID = "UEC11-FC-R02"  # the admission law (MUST NOT)
CREDIT_UNIT_REQUIREMENT_ID = "UEC11-FC-R05"  # one credit unit == 256 bytes

#: Credit unit: 256 destination-buffer bytes per pds.credit bit (UEC 1.1
#: §3.6.15, requirement UEC11-FC-R05, anchor UEC11-S3.6.15-TFC) — the
#: ONLY spec-derived value in this module (provenance rule).  Same
#: constant, same citation, as the declared abstraction backend.
TFC_CREDIT_UNIT_BYTES = 256

#: The declared steady-state abstraction of this automaton: the
#: analytical_l0_tfc credit-window ring identity — paper equation (3)
#: (sections/5.execution.tex, eq:tfc), rate law Reff = min(B, W/(L+L_cr)),
#: completion t = 2*(r-1)/r * M / Reff + 2*(r-1)*L.  The abstraction is
#: declared on BOTH sides: l0_tfc.GROUND_TRUTH_AUTOMATON names this
#: module back, and essun.specir.bindings.check_binding verifies the
#: pair, so neither side can drift silently.
ABSTRACTION_MODULE = "essun.backends.analytical.l0_tfc"
ABSTRACTION_BACKEND_ID = "analytical_l0_tfc"
ABSTRACTION_EQ_LABEL = "eq:tfc (paper Eq. 3)"
ABSTRACTION_RATE_LAW = "Reff = min(B, W/(L+L_cr))"
ABSTRACTION_COMPLETION_LAW = (
    "t = 2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L  "
    "(single-link reduction used here: M / Reff + L)"
)

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "exact_discrete_events",
    "collectives": (
        "single_link_transfer",
        "multi_source_shared_link_transfer",  # G7 contention extension
    ),
    "transport_model": "tfc_credit_admission_automaton",
    "observables": ("O-CCT",),
    "steady_state_abstraction": {
        "backend_id": ABSTRACTION_BACKEND_ID,
        "module": ABSTRACTION_MODULE,
        "equation": ABSTRACTION_EQ_LABEL,
        "rate_law": ABSTRACTION_RATE_LAW,
    },
    "explicitly_unsupported": (
        "credit_request_grant_dynamics",  # steady granted window W is the abstraction
        "tfc_retransmission_credit_exempt",  # UEC11-FC-R06
        "shared_ccc_credit_pooling",  # UEC11-FC-R16
        "cell_quantized_credit_consumption",  # UEC11-FC-R08 (staged on the analytical backend)
        "cbfc_link_credits",  # UEC §5.2 hop-level flow control
        "rccc_grant_scheduling",  # UEC §3.6.14 receiver-driven grant arbitration
        "credit_loss_and_timer_recovery",  # UEC11-FC-R19
        "multi_link_topologies",  # multi-hop paths / crossing links (G7: shared SINGLE link only)
        "variable_credit_return_timing",  # fixed D = L + L_cr (A-CA-RT)
        "overlapping_transfers_within_one_credit_context",  # one context, one flow (G7: contexts are per flow)
    ),
}

#: G7: the arbitration policies among credit-ready flows on the shared
#: link (assumption A-CA-ARB — a declared free choice; the standard does
#: not pin an order and Eq. 3 has no composition operator across flows).
ARBITRATION_POLICIES = ("index_priority", "round_robin")


# -- configuration -------------------------------------------------------------


@dataclass(frozen=True)
class AutomatonConfig:
    """Free parameters of one automaton instance (all integers).

    window_bytes W (whole 256-byte credit units, UEC11-FC-R05),
    link_bytes_per_ns B, hop_latency_ns L, credit_return_latency_ns L_cr
    (the credit loop D = L + L_cr), packet_bytes s (integral
    serialization B | s required, A-CA-SER; the transfer divisibility
    s | M is a run guard, A-CA-DIV).  None of these values is
    standard-derived; the single spec-derived constant is the 256-byte
    credit unit.
    """

    window_bytes: int
    link_bytes_per_ns: int
    hop_latency_ns: int
    credit_return_latency_ns: int
    packet_bytes: int

    @property
    def credit_loop_delay_ns(self) -> int:
        """D = L + L_cr: one round trip of the credit loop (A-CA-RT)."""
        return self.hop_latency_ns + self.credit_return_latency_ns

    @property
    def serialization_ns(self) -> int:
        """u = s / B (A-CA-SER guarantees integrality)."""
        return self.packet_bytes // self.link_bytes_per_ns

    @property
    def packets_per_window(self) -> int:
        """k = floor(W / s): whole packets the granted window covers."""
        return self.window_bytes // self.packet_bytes


def _int(value, name: str) -> int:
    """Strict integer coercion: ints pass, anything else (including
    non-integral floats/strings and bools) is rejected — the automaton
    runs on integers only."""
    if isinstance(value, bool):
        raise ValueError(
            f"{BACKEND_ID}: {name} must be an integer (got bool {value!r})"
        )
    if isinstance(value, int):
        return value
    raise ValueError(
        f"{BACKEND_ID}: {name} must be an integer (got {type(value).__name__} "
        f"{value!r}); the automaton runs on exact integers only"
    )


def load_automaton_config(data: dict) -> AutomatonConfig:
    """Load and validate a configuration dict (manifest-shaped, same
    nesting as the tfc topology files).  Every rejection names its rule
    and, where the rule is spec-derived, the requirement that anchors it.
    """
    link = data["link"]
    tfc = data["tfc"]
    config = AutomatonConfig(
        window_bytes=_int(tfc["window_bytes"], "tfc.window_bytes"),
        link_bytes_per_ns=_int(link["bytes_per_ns"], "link.bytes_per_ns"),
        hop_latency_ns=_int(link["hop_latency_ns"], "link.hop_latency_ns"),
        credit_return_latency_ns=_int(
            tfc["credit_return_latency_ns"], "tfc.credit_return_latency_ns"
        ),
        packet_bytes=_int(tfc["packet_bytes"], "tfc.packet_bytes"),
    )
    if config.link_bytes_per_ns <= 0:
        raise ValueError(
            f"{BACKEND_ID}: link.bytes_per_ns must be > 0 "
            f"(got {config.link_bytes_per_ns})"
        )
    if config.hop_latency_ns < 0:
        raise ValueError(
            f"{BACKEND_ID}: link.hop_latency_ns must be >= 0 "
            f"(got {config.hop_latency_ns})"
        )
    if config.credit_return_latency_ns < 0:
        raise ValueError(
            f"{BACKEND_ID}: tfc.credit_return_latency_ns must be >= 0 "
            f"(got {config.credit_return_latency_ns})"
        )
    if config.packet_bytes <= 0:
        raise ValueError(
            f"{BACKEND_ID}: tfc.packet_bytes must be > 0 "
            f"(got {config.packet_bytes})"
        )
    if config.window_bytes <= 0:
        raise ValueError(
            f"{BACKEND_ID}: tfc.window_bytes must be > 0 "
            f"(got {config.window_bytes})"
        )
    if config.window_bytes % TFC_CREDIT_UNIT_BYTES != 0:
        # UEC11-FC-R05 (§3.6.15): credit is granted in 256-byte units —
        # one pds.credit bit == 256 destination bytes.  A window that is
        # not an integral number of credit units is not a grantable TFC
        # window (same load-time rejection as the analytical backend).
        raise ValueError(
            f"{BACKEND_ID}: tfc.window_bytes {config.window_bytes} is not a "
            f"multiple of the {TFC_CREDIT_UNIT_BYTES}-byte credit unit "
            f"({CREDIT_UNIT_REQUIREMENT_ID}, UEC 1.1 §3.6.15: one "
            "pds.credit bit grants 256 bytes); the admission automaton "
            "only executes grantable windows"
        )
    if config.packet_bytes % config.link_bytes_per_ns != 0:
        # A-CA-SER: the automaton keeps an integer-ns event grid, so one
        # packet's serialization s/B must be a whole number of ns.
        raise ValueError(
            f"{BACKEND_ID}: tfc.packet_bytes {config.packet_bytes} is not a "
            f"multiple of link.bytes_per_ns {config.link_bytes_per_ns} "
            "(A-CA-SER: serialization s/B must be an integral number of "
            "ns on the automaton's integer event grid)"
        )
    if config.window_bytes < config.packet_bytes:
        raise ValueError(
            f"{BACKEND_ID}: tfc.window_bytes {config.window_bytes} covers "
            f"less than one packet ({config.packet_bytes} bytes) — every "
            "transmit would be a rejected trace, so no transfer is "
            "executable (grant at least one whole packet)"
        )
    return config


def config_field_names() -> tuple[str, ...]:
    """Config field names (binding-parameter checks; same surface as the
    analytical backends, verified by essun.specir.bindings)."""
    from dataclasses import fields

    return tuple(f.name for f in fields(AutomatonConfig))


# -- the admission machine ------------------------------------------------------


@dataclass(frozen=True)
class Admission:
    """One executed transmit: start time, size, and the return it owes."""

    time_ns: int
    packet_bytes: int
    return_due_ns: int


@dataclass(frozen=True)
class Rejection:
    """A transmit that did NOT execute (UEC11-FC-R02): the trace carrying
    it is illegal.  The machine state is unchanged by a rejection."""

    time_ns: int
    packet_bytes: int
    credit_bytes_at_decision: int
    requirement_id: str = REQUIREMENT_ID


@dataclass(frozen=True)
class TraceResult:
    """Outcome of executing an event sequence: the admitted prefix and,
    if the trace was illegal, the first offending transmit."""

    admissions: tuple[Admission, ...]
    rejection: Rejection | None

    @property
    def legal(self) -> bool:
        return self.rejection is None


class CreditAdmissionAutomaton:
    """The per-link credit admission machine (UEC11-FC-R02, exact).

    State: ``credit_bytes`` (the credit balance) and the pending return
    events (a return restores exactly the bytes its transmit consumed,
    ``D`` ns after the admission instant).  Invariants, re-derivable at
    every step: ``0 <= credit_bytes <= window_bytes`` and
    ``credit_bytes + pending_return_bytes == window_bytes`` — credit is
    conserved exactly, in integer bytes.
    """

    def __init__(self, window_bytes: int, credit_loop_delay_ns: int) -> None:
        self.window_bytes = _int(window_bytes, "window_bytes")
        self.credit_loop_delay_ns = _int(
            credit_loop_delay_ns, "credit_loop_delay_ns"
        )
        if self.window_bytes <= 0:
            raise ValueError(
                f"{BACKEND_ID}: window_bytes must be > 0 "
                f"(got {self.window_bytes})"
            )
        if self.credit_loop_delay_ns < 0:
            raise ValueError(
                f"{BACKEND_ID}: credit_loop_delay_ns must be >= 0 "
                f"(got {self.credit_loop_delay_ns})"
            )
        self._credit = self.window_bytes  # A-CA-INIT: the full grant at t=0
        self._pending: list[tuple[int, int]] = []  # heap of (due_ns, bytes)
        self._last_time_ns = 0
        self.admissions: list[Admission] = []

    # -- state -----------------------------------------------------------------

    @property
    def credit_bytes(self) -> int:
        """The current credit balance (integer bytes)."""
        return self._credit

    @property
    def pending_returns(self) -> tuple[tuple[int, int], ...]:
        """Pending (due_ns, bytes) return events, ascending by due time."""
        return tuple(sorted(self._pending))

    @property
    def pending_return_bytes(self) -> int:
        return sum(bytes_ for _, bytes_ in self._pending)

    def credit_conserved(self) -> bool:
        """Structural conservation: balance + owed == window, balance in
        range.  True at every step of every legal prefix by construction;
        this is the O-CONSERVATION-style algebraic self-check of the
        machine's own byte accounting."""
        return (
            0 <= self._credit <= self.window_bytes
            and self._credit + self.pending_return_bytes == self.window_bytes
        )

    # -- the admission transition ------------------------------------------------

    def _apply_returns_due(self, time_ns: int) -> None:
        while self._pending and self._pending[0][0] <= time_ns:
            due_ns, bytes_ = heapq.heappop(self._pending)
            self._credit += bytes_
        if self._credit > self.window_bytes:
            raise AssertionError(  # model bug, never a tunable outcome
                f"{BACKEND_ID}: credit balance {self._credit} exceeded the "
                f"window {self.window_bytes} — return accounting is broken "
                "(this is a machine bug, not a parameter)"
            )

    def attempt(self, time_ns: int, packet_bytes: int) -> Admission | Rejection:
        """One transmit attempt at integer time ``time_ns``.

        Returns :class:`Admission` (the transmit executed; credit
        consumed; a return event scheduled) or :class:`Rejection` (the
        transmit did NOT execute — UEC11-FC-R02 — and the state is
        exactly as before the attempt).  Event times must be
        non-decreasing: a trace is an ordered event sequence.
        """
        time_ns = _int(time_ns, "time_ns")
        packet_bytes = _int(packet_bytes, "packet_bytes")
        if packet_bytes <= 0:
            raise ValueError(
                f"{BACKEND_ID}: packet_bytes must be > 0 "
                f"(got {packet_bytes})"
            )
        if time_ns < self._last_time_ns:
            raise ValueError(
                f"{BACKEND_ID}: event time {time_ns} precedes the last "
                f"event time {self._last_time_ns} — a trace is an ordered "
                "event sequence"
            )
        self._apply_returns_due(time_ns)
        self._last_time_ns = time_ns
        if self._credit >= packet_bytes:
            self._credit -= packet_bytes
            due_ns = time_ns + self.credit_loop_delay_ns
            heapq.heappush(self._pending, (due_ns, packet_bytes))
            admission = Admission(time_ns, packet_bytes, due_ns)
            self.admissions.append(admission)
            return admission
        return Rejection(time_ns, packet_bytes, self._credit)


def execute_trace(
    window_bytes: int,
    credit_loop_delay_ns: int,
    events,
) -> TraceResult:
    """Execute an ordered ``[(time_ns, packet_bytes), ...]`` sequence.

    Execution stops at the FIRST transmit without credit: the prefix is
    executed, the offending event is returned in the
    :class:`TraceResult`, and ``legal`` is False — a transmit without
    credit is a rejected trace, never an executed one.
    """
    machine = CreditAdmissionAutomaton(window_bytes, credit_loop_delay_ns)
    for time_ns, packet_bytes in events:
        outcome = machine.attempt(time_ns, packet_bytes)
        if isinstance(outcome, Rejection):
            return TraceResult(tuple(machine.admissions), outcome)
    return TraceResult(tuple(machine.admissions), None)


# -- the greedy executor (the achieving schedule) --------------------------------


@dataclass(frozen=True)
class TransferResult:
    """One finite transfer executed greedily under the admission law."""

    packet_starts_ns: tuple[int, ...]
    packets: int
    packet_bytes: int
    total_bytes: int
    completion_ns: int  # last start + serialization + hop latency


class GreedyLinkExecutor:
    """Work-conserving sender serialized on the link at B bytes/ns.

    Transmits whenever the link is free AND credit admits — never
    earlier than either.  Greedy never violates the admission law (a
    rejection here is a machine bug, raised, not a trace outcome); it is
    the schedule that achieves the maximum legal rate (theorem clause 2).
    """

    def __init__(self, config: AutomatonConfig) -> None:
        self._config = config
        self.machine = CreditAdmissionAutomaton(
            config.window_bytes, config.credit_loop_delay_ns
        )

    def _next_admission_time(self, earliest_ns: int) -> int:
        """Earliest time >= earliest_ns at which credit covers one packet
        (exact integer scan over the pending returns; no state change)."""
        s = self._config.packet_bytes
        t_ns = earliest_ns
        available = self.machine.credit_bytes
        for due_ns, bytes_ in self.machine.pending_returns:
            if available >= s:
                break
            if due_ns > t_ns:
                t_ns = due_ns
            available += bytes_
        return t_ns

    def run_transfer(self, total_bytes: int) -> TransferResult:
        total_bytes = _int(total_bytes, "total_bytes")
        if total_bytes <= 0:
            raise ValueError(
                f"{BACKEND_ID}: total_bytes must be > 0 (got {total_bytes})"
            )
        if total_bytes % self._config.packet_bytes != 0:
            raise ValueError(
                f"{BACKEND_ID}: total_bytes {total_bytes} is not a multiple "
                f"of tfc.packet_bytes {self._config.packet_bytes} "
                "(A-CA-DIV: transfers are whole packets)"
            )
        u = self._config.serialization_ns
        s = self._config.packet_bytes
        n = total_bytes // s
        starts: list[int] = []
        link_free_ns = 0
        for _ in range(n):
            t_ns = self._next_admission_time(link_free_ns)
            outcome = self.machine.attempt(t_ns, s)
            if isinstance(outcome, Rejection):  # greedy must never see this
                raise AssertionError(
                    f"{BACKEND_ID}: greedy executor violated the admission "
                    f"law at t={t_ns} (credit {outcome.credit_bytes_at_decision}, "
                    f"packet {s}) — this is a machine bug, not a trace outcome"
                )
            starts.append(t_ns)
            link_free_ns = t_ns + u
        completion = starts[-1] + u + self._config.hop_latency_ns
        return TransferResult(
            packet_starts_ns=tuple(starts),
            packets=n,
            packet_bytes=s,
            total_bytes=total_bytes,
            completion_ns=completion,
        )


# -- the abstraction theorem: exact laws ------------------------------------------


def link_saturated(config: AutomatonConfig) -> bool:
    """Greedy keeps the link continuously busy iff the largest number of
    link-paced packet starts inside one credit-loop window —
    ``ceil(D / u)`` with ``u = s/B`` — fits the granted window:
    ``ceil(D/u) <= floor(W/s)``.  For ``s | W`` this is exactly Eq. 3's
    own convergence anchor ``W >= B*(L+L_cr)``."""
    u = config.serialization_ns
    window_starts = -(-config.credit_loop_delay_ns // u)  # ceil(D/u)
    return window_starts <= config.packets_per_window


def steady_state_rate_exact(config: AutomatonConfig) -> Fraction:
    """The automaton's exact maximum legal steady rate (theorem clause 2):

    ``R_auto = B`` if the link saturates, else
    ``floor(W/s) * s / D`` — the packet-quantized rate law.  The greedy
    executor achieves it (its bursts carry exactly ``floor(W/s)``
    packets per credit-loop period ``D``)."""
    if link_saturated(config):
        return Fraction(config.link_bytes_per_ns)
    k = config.packets_per_window
    return Fraction(k * config.packet_bytes, config.credit_loop_delay_ns)


def eq3_effective_rate(config: AutomatonConfig) -> Fraction:
    """Eq. 3's rate law, ``Reff = min(B, W/(L+L_cr))`` — the declared
    abstraction's effective-rate cap (paper eq:tfc; identical to
    analytical_l0_tfc.admission rate law).  D == 0 means credit returns
    instantly: the cap is the link rate."""
    if config.credit_loop_delay_ns == 0:
        return Fraction(config.link_bytes_per_ns)
    return min(
        Fraction(config.link_bytes_per_ns),
        Fraction(config.window_bytes, config.credit_loop_delay_ns),
    )


def rate_divergence_exact(config: AutomatonConfig) -> Fraction:
    """Eq. 3 rate minus automaton rate: ``>= 0`` always (the analytical
    law is optimistic by exactly the credit quantization), and ``< s/D``.
    It is ``0`` iff the two laws agree: whenever ``s | W`` (the
    quantization the analytical law idealizes away vanishes — true in
    BOTH regimes) and whenever the automaton saturates the link (then
    both laws are ``B``).  In the credit-gated regime with ``W < B*D``
    it is exactly ``(W mod s)/D``."""
    return eq3_effective_rate(config) - steady_state_rate_exact(config)


def eq3_completion_single_link(config: AutomatonConfig, total_bytes: int) -> Fraction:
    """Eq. 3 reduced to one link (per-rank traffic M over one hop):
    ``t = M / Reff + L`` — the completion identity whose automaton
    divergence clause 4 quantifies."""
    return (
        Fraction(total_bytes) / eq3_effective_rate(config)
        + config.hop_latency_ns
    )


def greedy_last_start_closed_form(config: AutomatonConfig, packets: int) -> int:
    """Exact closed form of the greedy last packet start for ``n``
    packets (theorem clause 4's engine; verified against execution by the
    tests over the parameter grid, both regimes):

    - link-limited: ``t_last = (n-1) * u`` (never gated);
    - credit-gated, ``n = q*k + r``: full bursts ride one per ``D``:
      ``t_last = (q-1)*D + (k-1)*u`` when ``r == 0``, else
      ``q*D + (r-1)*u``.
    """
    if packets < 1:
        raise ValueError(f"{BACKEND_ID}: packets must be >= 1 (got {packets})")
    u = config.serialization_ns
    if link_saturated(config):
        return (packets - 1) * u
    k = config.packets_per_window
    q, r = divmod(packets, k)
    if r == 0:
        return (q - 1) * config.credit_loop_delay_ns + (k - 1) * u
    return q * config.credit_loop_delay_ns + (r - 1) * u


def finite_divergence_closed_form(
    config: AutomatonConfig, packets: int
) -> Fraction:
    """Exact divergence ``t_auto - t_eq3`` for a finite transfer of
    ``packets`` packets (theorem clause 4):

    - link-limited: ``0`` — Eq. 3 is exact, no divergence;
    - credit-gated, ``r == 0``: ``k*u - D``;
    - credit-gated, ``r >= 1``: ``r * (u - D/k)``.

    In the credit-gated regime the value lies strictly between ``-D``
    and ``0``: the steady-state law overestimates a finite collective's
    completion by less than one credit-loop round trip, vanishing
    relatively as ``n`` grows."""
    if packets < 1:
        raise ValueError(f"{BACKEND_ID}: packets must be >= 1 (got {packets})")
    u = config.serialization_ns
    if link_saturated(config):
        return Fraction(0)
    k = config.packets_per_window
    d = config.credit_loop_delay_ns
    q, r = divmod(packets, k)
    if r == 0:
        return Fraction(k * u - d)
    return Fraction(r * (u * k - d), k)


def execute_finite_collective(
    config: AutomatonConfig, total_bytes: int
) -> tuple[int, Fraction, Fraction]:
    """Execute a finite transfer and return
    ``(t_auto, t_eq3, divergence)`` — the executed completion, Eq. 3's
    prediction, and their exact difference (integer execution, exact
    Fractions for the analytical side)."""
    executor = GreedyLinkExecutor(config)
    result = executor.run_transfer(total_bytes)
    eq3 = eq3_completion_single_link(config, total_bytes)
    return result.completion_ns, eq3, Fraction(result.completion_ns) - eq3


# -- the safety bound (theorem clause 1) ------------------------------------------


def sliding_window_bytes(admissions, time_ns: int, delay_ns: int) -> int:
    """Bytes with start times in the half-open credit window
    ``(time_ns - delay_ns, time_ns]``."""
    return sum(
        admission.packet_bytes
        for admission in admissions
        if time_ns - delay_ns < admission.time_ns <= time_ns
    )


def sliding_window_bound_holds(admissions, window_bytes: int, delay_ns: int) -> bool:
    """Theorem clause 1: every legal (fully admitted) event sequence has
    at most ``W`` bytes inside ANY half-open window of length D.  The
    admission law IS this bound, structurally — checked here over every
    event time of the sequence."""
    times = sorted({admission.time_ns for admission in admissions})
    return all(
        sliding_window_bytes(admissions, t_ns, delay_ns) <= window_bytes
        for t_ns in times
    )


# -- the tested statement, machine-readable ----------------------------------------


def abstraction_statement(config: AutomatonConfig) -> dict:
    """The G8 statement as data: under which conditions Eq. 3 is this
    automaton's abstraction, and the exact divergences when a condition
    fails.  Tests pin every field against execution."""
    packet_divides_window = config.window_bytes % config.packet_bytes == 0
    saturated = link_saturated(config)
    return {
        "automaton": BACKEND_ID,
        "binding_id": BINDING_ID,
        "requirement_id": REQUIREMENT_ID,
        "abstraction": {
            "backend_id": ABSTRACTION_BACKEND_ID,
            "equation": ABSTRACTION_EQ_LABEL,
            "rate_law": ABSTRACTION_RATE_LAW,
        },
        "conditions": {
            "C1_packet_divides_window (s | W)": packet_divides_window,
            "C2_integral_serialization (B | s)": (
                config.packet_bytes % config.link_bytes_per_ns == 0
            ),
            "C3_greedy_work_conserving_sender": True,  # the executor
            "C4_fixed_credit_loop_delay (D = L + L_cr)": True,  # A-CA-RT
            "C5_steady_state (T >> D)": "finite transfers diverge exactly below",
        },
        "regime": "link_limited" if saturated else "credit_gated",
        "automaton_rate_exact": steady_state_rate_exact(config),
        "eq3_rate": eq3_effective_rate(config),
        "rate_divergence_exact": rate_divergence_exact(config),
        "rate_laws_agree": rate_divergence_exact(config) == 0,
        "note": (
            "Eq. 3's rate law equals the automaton's steady state exactly "
            "when s | W (both regimes), and whenever credit permits line "
            "rate; in the credit-gated regime with W < B*D the divergence "
            "is exactly (W mod s)/D — the credit quantization Eq. 3 "
            "idealizes away.  Finite collectives additionally complete "
            "EARLIER than the steady-state identity predicts, by the exact "
            "closed forms of clause 4 — both divergences are properties of "
            "the abstraction, not of FC-R02's safety rule."
        ),
    }


def check_requirements() -> list[str]:
    """Re-verify the driving requirement objects against the live stage
    registry; ``[]`` means the automaton still executes what its anchors
    say.  Checks: UEC11-FC-R02 exists, is keyword MUST NOT, subject TFC,
    disposition simulated_behavior (the binding's claim); UEC11-FC-R05
    exists, is DEFINITIONAL, and carries the 256-byte unit in its
    statement."""
    from .uec_credits_flow_control import requirements as fc_requirements

    problems: list[str] = []
    index = {req.requirement_id: req for req in fc_requirements()}
    admission = index.get(REQUIREMENT_ID)
    if admission is None:
        problems.append(
            f"{BACKEND_ID}: driving requirement {REQUIREMENT_ID} not found "
            "in the live stage registry"
        )
    else:
        if admission.keyword != "MUST NOT":
            problems.append(
                f"{BACKEND_ID}: {REQUIREMENT_ID} keyword {admission.keyword!r} "
                "!= 'MUST NOT' (the admission law is a prohibition)"
            )
        if admission.subject != "TFC":
            problems.append(
                f"{BACKEND_ID}: {REQUIREMENT_ID} subject {admission.subject!r} "
                "!= 'TFC'"
            )
        if admission.disposition != "simulated_behavior":
            problems.append(
                f"{BACKEND_ID}: {REQUIREMENT_ID} disposition "
                f"{admission.disposition!r} != 'simulated_behavior' "
                f"(the binding {BINDING_ID} claims it)"
            )
    unit = index.get(CREDIT_UNIT_REQUIREMENT_ID)
    if unit is None:
        problems.append(
            f"{BACKEND_ID}: credit-unit requirement "
            f"{CREDIT_UNIT_REQUIREMENT_ID} not found in the live stage "
            "registry"
        )
    else:
        if unit.keyword != "DEFINITIONAL":
            problems.append(
                f"{BACKEND_ID}: {CREDIT_UNIT_REQUIREMENT_ID} keyword "
                f"{unit.keyword!r} != 'DEFINITIONAL'"
            )
        if "256 bytes" not in unit.statement:
            problems.append(
                f"{BACKEND_ID}: {CREDIT_UNIT_REQUIREMENT_ID} statement no "
                "longer carries the 256-byte credit unit the automaton "
                "enforces at load time"
            )
    return problems


# -- the shared-link contention extension (G7) ------------------------------------
#
# Two or more flows — independent finite collectives, each with its OWN
# credit context (the TFC per-PDC-pair shape) — serialize on ONE shared
# link at B bytes/ns.  The per-flow admission machine is UNCHANGED (one
# CreditAdmissionAutomaton per context, same invariants); this extension
# adds the LINK serializer (work-conserving: it never idles while some
# flow is credit-ready) and an ARBITRATION rule among credit-ready flows
# (A-CA-ARB: a declared free choice — UEC 1.1 pins no order, and Eq. 3
# is a per-flow steady-state cap with NO composition operator across
# flows; that gap is exactly what this extension makes executable).


@dataclass(frozen=True)
class FlowSpec:
    """One flow: a finite collective of ``packets`` x ``packet_bytes``
    under its own credit context of ``window_bytes`` (free parameters,
    same validation as the single-link machine)."""

    window_bytes: int
    packet_bytes: int
    packets: int


@dataclass(frozen=True)
class SharedLinkConfig:
    """Free parameters of one shared-link contention instance (integers).

    One link (B, L, L_cr with D = L + L_cr per flow context) shared by
    ``flows`` (>= 2); per flow: window W_i, packet size s_i (B | s_i,
    A-CA-SER per flow), packet count n_i."""

    link_bytes_per_ns: int
    hop_latency_ns: int
    credit_return_latency_ns: int
    flows: tuple[FlowSpec, ...]

    @property
    def credit_loop_delay_ns(self) -> int:
        """D = L + L_cr: one round trip of the credit loop (A-CA-RT)."""
        return self.hop_latency_ns + self.credit_return_latency_ns


def load_shared_link_config(data: dict) -> SharedLinkConfig:
    """Load and validate a shared-link contention configuration
    (manifest-shaped: the shared ``link``/``tfc`` scalars plus a
    ``flows`` list of per-flow window/packet/count).  Rejections name
    their rule exactly as the single-link loader does; the 256-byte
    credit-unit rule (UEC11-FC-R05) applies to EVERY flow's window."""

    link = data["link"]
    tfc = data["tfc"]
    raw_flows = data["flows"]
    if not isinstance(raw_flows, list) or len(raw_flows) < 2:
        raise ValueError(
            f"{BACKEND_ID}: shared-link contention needs >= 2 flows "
            f"(got {len(raw_flows) if hasattr(raw_flows, '__len__') else raw_flows!r}); "
            "a single flow is the single-link machine's job, not a "
            "contention instance"
        )
    flows: list[FlowSpec] = []
    for index, raw in enumerate(raw_flows):
        window = _int(raw["window_bytes"], f"flows[{index}].window_bytes")
        packet = _int(raw["packet_bytes"], f"flows[{index}].packet_bytes")
        packets = _int(raw["packets"], f"flows[{index}].packets")
        if packets < 1:
            raise ValueError(
                f"{BACKEND_ID}: flows[{index}].packets must be >= 1 "
                f"(got {packets})"
            )
        if window % TFC_CREDIT_UNIT_BYTES != 0:
            # UEC11-FC-R05 (§3.6.15): every granted window is whole credit
            # units — same load-time rejection as the single-link machine,
            # applied per flow context.
            raise ValueError(
                f"{BACKEND_ID}: flows[{index}].window_bytes {window} is not "
                f"a multiple of the {TFC_CREDIT_UNIT_BYTES}-byte credit unit "
                f"({CREDIT_UNIT_REQUIREMENT_ID}, UEC 1.1 §3.6.15: one "
                "pds.credit bit grants 256 bytes); the contention extension "
                "only executes grantable windows"
            )
        if packet <= 0 or window < packet:
            raise ValueError(
                f"{BACKEND_ID}: flows[{index}] needs packet_bytes >= 1 and "
                f"window_bytes >= packet_bytes (got s={packet}, W={window}; "
                "a window below one packet executes no transfer)"
            )
        if packet % _int(link["bytes_per_ns"], "link.bytes_per_ns") != 0:
            # A-CA-SER per flow: integer serialization grid on the shared link.
            raise ValueError(
                f"{BACKEND_ID}: flows[{index}].packet_bytes {packet} is not "
                f"a multiple of link.bytes_per_ns {link['bytes_per_ns']} "
                "(A-CA-SER: serialization s/B must be integral on the "
                "automaton's integer event grid)"
            )
        flows.append(FlowSpec(window_bytes=window, packet_bytes=packet, packets=packets))
    config = SharedLinkConfig(
        link_bytes_per_ns=_int(link["bytes_per_ns"], "link.bytes_per_ns"),
        hop_latency_ns=_int(link["hop_latency_ns"], "link.hop_latency_ns"),
        credit_return_latency_ns=_int(
            tfc["credit_return_latency_ns"], "tfc.credit_return_latency_ns"
        ),
        flows=tuple(flows),
    )
    if config.link_bytes_per_ns <= 0:
        raise ValueError(
            f"{BACKEND_ID}: link.bytes_per_ns must be > 0 "
            f"(got {config.link_bytes_per_ns})"
        )
    if config.hop_latency_ns < 0 or config.credit_return_latency_ns < 0:
        raise ValueError(
            f"{BACKEND_ID}: latencies must be >= 0 (got L="
            f"{config.hop_latency_ns}, L_cr={config.credit_return_latency_ns})"
        )
    return config


@dataclass(frozen=True)
class FlowContentionResult:
    """One flow's executed outcome under contention."""

    flow_index: int
    packet_starts_ns: tuple[int, ...]
    completion_ns: int  # last start + serialization + hop latency
    window_bound_holds: bool  # theorem clause 1 re-derived for this context
    credit_conserved: bool  # per-context byte conservation


@dataclass(frozen=True)
class ContentionResult:
    """The shared-link contention execution (exact, integer ns)."""

    arbitration: str
    flows: tuple[FlowContentionResult, ...]
    idle_gaps_ns: tuple[tuple[int, int], ...]  # (from, to): link idle, every flow gated
    max_completion_ns: int


class SharedLinkContentionExecutor:
    """Work-conserving shared link + one admission machine per flow.

    Loop: at each link-free instant, the flows whose credit covers one
    packet AT that instant are READY; the arbitration rule (A-CA-ARB)
    picks among them; the winner transmits (credit consumed in ITS
    context, return scheduled), and the link is busy for u_i = s_i/B ns.
    If no flow is ready the link IDLES until the earliest return that
    unfreezes one — with every flow backlogged, an exact idle gap the
    steady-state law's fluid picture never produces.  Greedy never
    violates the admission law (a rejection here is a machine bug,
    raised, not a trace outcome)."""

    def __init__(self, config: SharedLinkConfig, arbitration: str = "index_priority") -> None:
        if arbitration not in ARBITRATION_POLICIES:
            raise ValueError(
                f"{BACKEND_ID}: unknown arbitration {arbitration!r}; declared "
                f"policies (A-CA-ARB): {list(ARBITRATION_POLICIES)}"
            )
        self._config = config
        self._arbitration = arbitration
        self.machines = [
            CreditAdmissionAutomaton(flow.window_bytes, config.credit_loop_delay_ns)
            for flow in config.flows
        ]

    def _next_admission_time(self, index: int, earliest_ns: int) -> int:
        """Earliest time >= earliest_ns at which flow index's credit covers
        one packet (exact integer scan over pending returns; no state change)."""
        s = self._config.flows[index].packet_bytes
        t_ns = earliest_ns
        available = self.machines[index].credit_bytes
        for due_ns, bytes_ in self.machines[index].pending_returns:
            if available >= s:
                break
            if due_ns > t_ns:
                t_ns = due_ns
            available += bytes_
        return t_ns

    def run(self) -> ContentionResult:
        config = self._config
        n_flows = len(config.flows)
        remaining = [flow.packets for flow in config.flows]
        starts: list[list[int]] = [[] for _ in range(n_flows)]
        idle_gaps: list[tuple[int, int]] = []
        link_free_ns = 0
        rr_next = 0
        total_packets = sum(remaining)
        done = 0
        while done < total_packets:
            t_ns = link_free_ns
            ready = [
                index
                for index in range(n_flows)
                if remaining[index] > 0
                and self._next_admission_time(index, t_ns) == t_ns
            ]
            if not ready:
                # Every flow with data is credit-gated: the link idles to
                # the earliest unfreezing return (the burst-interaction gap).
                next_ns = min(
                    self._next_admission_time(index, t_ns)
                    for index in range(n_flows)
                    if remaining[index] > 0
                )
                idle_gaps.append((t_ns, next_ns))
                link_free_ns = next_ns
                continue
            if self._arbitration == "index_priority":
                winner = ready[0]
            else:  # round_robin
                winner = next(
                    (rr_next + offset) % n_flows
                    for offset in range(n_flows)
                    if (rr_next + offset) % n_flows in ready
                )
                rr_next = (winner + 1) % n_flows
            flow = config.flows[winner]
            outcome = self.machines[winner].attempt(link_free_ns, flow.packet_bytes)
            if isinstance(outcome, Rejection):  # greedy must never see this
                raise AssertionError(
                    f"{BACKEND_ID}: contention executor violated the admission "
                    f"law for flow {winner} at t={link_free_ns} — this is a "
                    "machine bug, not a trace outcome"
                )
            starts[winner].append(link_free_ns)
            link_free_ns += flow.packet_bytes // config.link_bytes_per_ns
            remaining[winner] -= 1
            done += 1
        flow_results = []
        for index, flow in enumerate(config.flows):
            u = flow.packet_bytes // config.link_bytes_per_ns
            flow_results.append(
                FlowContentionResult(
                    flow_index=index,
                    packet_starts_ns=tuple(starts[index]),
                    completion_ns=starts[index][-1] + u + config.hop_latency_ns,
                    window_bound_holds=sliding_window_bound_holds(
                        self.machines[index].admissions,
                        flow.window_bytes,
                        config.credit_loop_delay_ns,
                    ),
                    credit_conserved=self.machines[index].credit_conserved(),
                )
            )
        return ContentionResult(
            arbitration=self._arbitration,
            flows=tuple(flow_results),
            idle_gaps_ns=tuple(idle_gaps),
            max_completion_ns=max(result.completion_ns for result in flow_results),
        )


def run_shared_link_contention(
    config: SharedLinkConfig, arbitration: str = "index_priority"
) -> ContentionResult:
    """Execute one shared-link contention instance (deterministic)."""
    return SharedLinkContentionExecutor(config, arbitration).run()


# -- the law candidates the contention case defeats (exact) -----------------------


def law_alone_ns(config: SharedLinkConfig, index: int) -> Fraction:
    """Eq. 3's single-link reduction for flow ``index`` ALONE on the link:
    ``M_i / min(B, W_i/D) + L`` — the per-flow steady-state law applied the
    only way it can be applied, per flow in isolation."""
    flow = config.flows[index]
    d = config.credit_loop_delay_ns
    if d == 0:
        rate = Fraction(config.link_bytes_per_ns)
    else:
        rate = min(
            Fraction(config.link_bytes_per_ns),
            Fraction(flow.window_bytes, d),
        )
    return Fraction(flow.packets * flow.packet_bytes) / rate + config.hop_latency_ns


def law_aggregate_ns(config: SharedLinkConfig) -> Fraction:
    """The aggregate-composition candidate: treat the flows as ONE transfer
    of ``sum(M_i)`` bytes under the SUM of the windows —
    ``sum(M_i) / min(B, sum(W_i)/D) + L``.  A plausible ad-hoc composition
    of Eq. 3 across flows; it predicts ONE completion time, says nothing
    about per-flow completions, and (golden G7-B) still misses the exact
    machine time."""
    d = config.credit_loop_delay_ns
    total_bytes = sum(flow.packets * flow.packet_bytes for flow in config.flows)
    if d == 0:
        rate = Fraction(config.link_bytes_per_ns)
    else:
        rate = min(
            Fraction(config.link_bytes_per_ns),
            Fraction(sum(flow.window_bytes for flow in config.flows), d),
        )
    return Fraction(total_bytes) / rate + config.hop_latency_ns


def window_never_binds(config: SharedLinkConfig) -> bool:
    """True iff EVERY flow's window covers its whole finite collective
    (``n_i <= floor(W_i/s_i)``): no credit context ever gates, yet the
    flows still contend for the link — golden G7-A's regime."""
    return all(
        flow.packets <= flow.window_bytes // flow.packet_bytes
        for flow in config.flows
    )


def no_window_closed_form(
    config: SharedLinkConfig, arbitration: str
) -> tuple[int, ...]:
    """Exact closed form of the per-flow completions in the
    window-never-binds regime (verified against execution by the tests):

    - ``index_priority`` (any flow count): flow i waits for every earlier
      flow to drain, ``t_i = sum_{j<=i} n_j * u_j + L`` (flow 0 alone-time).
    - ``round_robin`` (2 flows, equal packet size): the flows alternate
      slots while both have packets, then the larger flow drains alone
      and holds the last slot: ``t_larger = (n_0 + n_1)*u + L``; the
      other flow finishes one slot earlier (``t_0 = (2*n_0 - 1)*u + L``
      when ``n_0 <= n_1``; ``t_1 = 2*n_1*u + L`` when ``n_1 < n_0``).
    """
    if not window_never_binds(config):
        raise ValueError(
            f"{BACKEND_ID}: no-window closed form stated only for the "
            "window-never-binds regime (some flow is credit-gated here)"
        )
    flows = config.flows
    u = [flow.packet_bytes // config.link_bytes_per_ns for flow in flows]
    if arbitration == "index_priority":
        prefix = 0
        out = []
        for index, flow in enumerate(flows):
            prefix += flow.packets * u[index]
            out.append(prefix + config.hop_latency_ns)
        return tuple(out)
    if arbitration == "round_robin":
        if len(flows) != 2 or flows[0].packet_bytes != flows[1].packet_bytes:
            raise ValueError(
                f"{BACKEND_ID}: round-robin closed form stated for 2 flows of "
                "equal packet size (grid tests verify execution generally)"
            )
        n0, n1 = flows[0].packets, flows[1].packets
        larger = (n0 + n1) * u[0] + config.hop_latency_ns
        if n0 <= n1:
            return ((2 * n0 - 1) * u[0] + config.hop_latency_ns, larger)
        return (larger, 2 * n1 * u[0] + config.hop_latency_ns)
    raise ValueError(
        f"{BACKEND_ID}: unknown arbitration {arbitration!r}; declared "
        f"policies (A-CA-ARB): {list(ARBITRATION_POLICIES)}"
    )


def contention_statement(config: SharedLinkConfig, arbitration: str) -> dict:
    """The G7 hard case as data: the per-flow laws, the aggregate
    candidate, and the machine's exact completions/gaps side by side —
    the numbers the analytical law alone cannot produce (it has no
    arbitration operator and no idle-gap semantics)."""
    result = run_shared_link_contention(config, arbitration)
    return {
        "automaton": BACKEND_ID,
        "extension": "multi_source_shared_link_contention",
        "requirement_id": REQUIREMENT_ID,
        "arbitration": arbitration,
        "window_never_binds": window_never_binds(config),
        "per_flow": [
            {
                "flow_index": flow.flow_index,
                "packets": config.flows[flow.flow_index].packets,
                "packet_starts_ns": list(flow.packet_starts_ns),
                "completion_ns_exact": flow.completion_ns,
                "law_alone_ns_exact": str(law_alone_ns(config, flow.flow_index)),
                "divergence_vs_alone_ns_exact": str(
                    Fraction(flow.completion_ns)
                    - law_alone_ns(config, flow.flow_index)
                ),
                "window_bound_holds": flow.window_bound_holds,
                "credit_conserved": flow.credit_conserved,
            }
            for flow in result.flows
        ],
        "idle_gaps_ns": [list(gap) for gap in result.idle_gaps_ns],
        "max_completion_ns_exact": result.max_completion_ns,
        "law_aggregate_ns_exact": str(law_aggregate_ns(config)),
        "note": (
            "Eq. 3 is a per-flow steady-state cap with no composition "
            "operator: applied per flow it predicts jointly infeasible "
            "alone-times on a shared link; composed as an aggregate it "
            "predicts one completion and misses the machine's exact value "
            "(and every per-flow value). The machine resolves the case "
            "exactly — and its per-flow observables MOVE with the "
            "arbitration freedom (A-CA-ARB), which no law input encodes."
        ),
    }
