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
standard-derived constant, the 256-byte credit unit — windows are
granted in whole units and non-grantable windows are rejected at load
time citing the requirement (same discipline as the analytical backend).
:func:`check_requirements` re-verifies both objects against the live
stage registry so the automaton cannot drift from its anchors.

Scope honestly NOT executed (declared unsupported in CAPABILITIES):
credit-request/grant protocol dynamics (a steady granted window is the
modeled abstraction), TFC retransmission credit exemption (FC-R06),
shared-CCC pooling (FC-R16), cell-quantized credit consumption (FC-R08
— staged separately on the analytical backend by the credit-family
ladder), CBFC hop credits (§5.2), RCCC multi-source scheduling
(§3.6.14), packet loss and credit-timer recovery (FC-R19), multi-link
contention, and variable return timing.  B, L, L_cr, W, s are FREE
parameters (not standard-derived, not measured).
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
    "collectives": ("single_link_transfer",),
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
        "rccc_multi_source_credit_scheduling",  # UEC §3.6.14
        "credit_loss_and_timer_recovery",  # UEC11-FC-R19
        "multi_link_contention",
        "variable_credit_return_timing",  # fixed D = L + L_cr (A-CA-RT)
        "overlapping_transfers",
    ),
}


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
