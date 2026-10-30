"""Soak seed 2 (2026-10-30): the credit automaton's invariants over
randomized legal traces, beyond the landed grids.

Companion of tests/specir/test_credit_automaton.py (machine invariants
on 200 seeded traces + the closed-form grids): this module extends the
soak to what the landed tests do NOT cover —

- the invariants re-derived IN THE TEST: an independent shadow ledger
  mirrors the admission semantics with a plain linear scan (no heap)
  and the machine's full observable state — balance AND the
  pending-return multiset — must equal it at EVERY step of EVERY trace;
  ``0 <= credit <= W`` and ``credit + owed == W`` are asserted from the
  observables directly (the machine's own ``credit_conserved()`` is
  only cross-checked as agreeing with the re-derivation);
- two strata beyond the landed grids: the RAW machine on arbitrary
  positive integers (windows that are NOT multiples of the 256-byte
  credit unit, packet sizes up to 2W — the loader's UEC11-FC-R05
  grantability rule constrains the PROFILE, not the machine, so the
  invariants are exercised on the wider space) and the profile-legal
  stratum (W a whole number of 256-byte credit units, 256-byte
  packets);
- attempt sequences that CONTINUE after rejections — the landed traces
  break at the first refusal — pinning the exact refusal semantics: a
  refused transmit executes NOTHING (no credit consumed, no return
  scheduled, admissions log frozen) while the attempt still advances
  time, applying every return that came due (the landed
  ``test_returns_restore_exactly_what_transmits_consume`` relies on
  exactly this when it probes the post-return balance with a
  rejection);
- ``execute_trace``'s rejected-trace semantics preserved: execution
  stops at the FIRST transmit the shadow ledger refuses, the executed
  prefix and the offending event match the oracle, and the final state
  re-derives from the admissions LOG alone under the return-sweep rule
  (a return scheduled at tau is applied by the first subsequent
  attempt at time >= tau + D, so with D == 0 the final admission's own
  return is still pending when nothing follows it);
- the shared-link contention executor on randomized MULTI-flow
  instances (2..4 flows; the landed grids are 2-flow parametrizations):
  per-context clause-1 safety and byte conservation re-derived from
  the packet starts and the context's own machine, strict
  serialization on the shared link, and byte-identical replay.

Every stream is seeded (``random.Random(<constant>)``); no hypothesis,
no wall clock, no network.  A failure here is a finding about the
machine — never edit the machine, a golden, or a disposition to
silence it.
"""

from __future__ import annotations

import random

from essun.specir import credit_automaton as ca
from essun.specir.credit_automaton import (
    Admission,
    CreditAdmissionAutomaton,
    SharedLinkContentionExecutor,
    execute_trace,
    sliding_window_bound_holds,
)

#: Seed 2 stream constant (2026-10-30, soak seed 2); every trace below
#: is a pure function of this seed.
SEED = 2026103002


class _ShadowLedger:
    """Independent re-implementation of the admission semantics.

    Mirrors :class:`CreditAdmissionAutomaton` with the simplest possible
    data structures (a plain list scanned linearly, balance kept as an
    accumulated integer exactly as the semantics dictates) so that
    agreement between the two is evidence about the machine, not a
    tautology.  The conservation law is NOT built into the ledger: the
    balance is accumulated, and ``credit + owed == W`` is checked as a
    real assertion on both sides.
    """

    def __init__(self, window_bytes: int, credit_loop_delay_ns: int) -> None:
        self.window = window_bytes
        self.delay = credit_loop_delay_ns
        self.credit = window_bytes  # A-CA-INIT: the full grant at t=0
        self.pending: list[tuple[int, int]] = []  # (due_ns, bytes), unsorted

    def attempt(self, time_ns: int, packet_bytes: int) -> str:
        """Apply due returns, then admit or refuse; returns the outcome."""
        still_pending = []
        for due_ns, bytes_ in self.pending:
            if due_ns <= time_ns:
                self.credit += bytes_
            else:
                still_pending.append((due_ns, bytes_))
        self.pending = still_pending
        if self.credit >= packet_bytes:
            self.credit -= packet_bytes
            self.pending.append((time_ns + self.delay, packet_bytes))
            return "admission"
        return "rejection"

    def conserved(self) -> bool:
        owed = sum(bytes_ for _, bytes_ in self.pending)
        return 0 <= self.credit <= self.window and self.credit + owed == self.window


def _assert_invariants(
    machine: CreditAdmissionAutomaton, shadow: _ShadowLedger
) -> None:
    # Re-derived HERE from the observables; the machine's own algebraic
    # self-check must agree with the re-derivation (cross-check).
    owed = machine.pending_return_bytes
    assert 0 <= machine.credit_bytes <= machine.window_bytes, (
        machine.window_bytes,
        machine.credit_bytes,
    )
    assert machine.credit_bytes + owed == machine.window_bytes, (
        machine.window_bytes,
        machine.credit_bytes,
        owed,
    )
    assert machine.credit_conserved()
    assert machine.credit_bytes == shadow.credit, (
        "machine balance diverged from the independent ledger",
        machine.window_bytes,
        machine.credit_bytes,
        shadow.credit,
    )
    assert machine.pending_returns == tuple(sorted(shadow.pending)), (
        "machine pending returns diverged from the independent ledger",
        machine.pending_returns,
        tuple(sorted(shadow.pending)),
    )


def _random_events(
    rng: random.Random, window: int, delay: int, *, profile_legal: bool
) -> list[tuple[int, int]]:
    """A randomized ordered event sequence (non-decreasing times,
    positive sizes).  Profile-legal stratum: 256-byte credit units.
    Raw stratum: arbitrary sizes up to 2W (deliberately including
    never-grantable transmits)."""
    events: list[tuple[int, int]] = []
    t = 0
    for _ in range(rng.randint(0, 40)):
        t += rng.randint(0, 2 * delay + 50)
        if profile_legal:
            size = 256 if (window < 512 or rng.random() < 0.7) else 512
        else:
            size = rng.randint(1, 2 * window)
        events.append((t, size))
    return events


def _owed_from_log(
    admissions: tuple[Admission, ...] | list[Admission],
    events: list[tuple[int, int]],
    delay: int,
) -> int:
    """Bytes still owed, re-derived from the admissions log + the event
    sequence alone (no machine state).

    A return scheduled at tau (due tau + D) is swept by the FIRST
    subsequent attempt at time >= due; event times are non-decreasing,
    so a non-final admission's return survives iff its due exceeds the
    LAST event time, and the final admission's return survives whenever
    no event follows it (the D == 0 tail).  The admissions correspond
    one-to-one, in order, to the events that executed — matching
    (time, size) per event is unambiguous because credit cannot
    increase between attempts at the same instant.
    """
    t_last = events[-1][0] if events else 0
    owed = 0
    k = 0
    for index, (t, size) in enumerate(events):
        if (
            k < len(admissions)
            and admissions[k].time_ns == t
            and admissions[k].packet_bytes == size
        ):
            if t + delay > t_last or index == len(events) - 1:
                owed += size
            k += 1
    assert k == len(admissions), "the log does not align with the events"
    return owed


def _run_attempt_sequence(
    window: int, delay: int, events: list[tuple[int, int]]
) -> None:
    """Drive ``attempt`` through the WHOLE sequence — rejections do not
    stop the driver (a stronger exercise than execute_trace) — checking
    the invariants and the shadow ledger at every step, the exact
    refusal semantics at every refusal, and a final re-derivation of
    the state from the admissions log alone."""
    machine = CreditAdmissionAutomaton(window, delay)
    shadow = _ShadowLedger(window, delay)
    _assert_invariants(machine, shadow)  # step 0: the initial grant
    for t, size in events:
        before = (machine.credit_bytes, machine.pending_returns, len(machine.admissions))
        due_now = tuple(sorted((d, b) for d, b in before[1] if d <= t))
        still_pending = tuple(sorted((d, b) for d, b in before[1] if d > t))
        expected = shadow.attempt(t, size)
        outcome = machine.attempt(t, size)
        _assert_invariants(machine, shadow)
        if expected == "admission":
            assert isinstance(outcome, Admission)
            assert (outcome.time_ns, outcome.packet_bytes) == (t, size)
            assert outcome.return_due_ns == t + delay
        else:
            assert isinstance(outcome, ca.Rejection)
            assert outcome.credit_bytes_at_decision == shadow.credit
            # The refusal executed NOTHING: no credit consumed, no
            # return scheduled, the admissions log frozen.  The attempt
            # still advanced time, so the observable delta is exactly
            # the returns that came due at t.
            assert len(machine.admissions) == before[2]
            assert machine.pending_returns == still_pending, (window, delay, t, size)
            assert machine.credit_bytes == before[0] + sum(b for _, b in due_now), (
                window,
                delay,
                t,
                size,
            )
    # The final state re-derived from the LOG alone (the return-sweep
    # rule above): owed bytes and balance match without reading any
    # machine state.
    owed = _owed_from_log(machine.admissions, events, delay)
    assert owed == machine.pending_return_bytes, (window, delay, events)
    assert window - owed == machine.credit_bytes, (window, delay, events)


def test_raw_machine_invariants_over_randomized_traces() -> None:
    # Stratum A: the machine on arbitrary positive integers — windows
    # NOT multiples of the credit unit, sizes up to 2W, delays 0..600.
    rng = random.Random(SEED)
    for _ in range(300):
        window = rng.randint(1, 4000)
        delay = rng.randint(0, 600)
        events = _random_events(rng, window, delay, profile_legal=False)
        _run_attempt_sequence(window, delay, events)


def test_profile_legal_invariants_over_randomized_traces() -> None:
    # Stratum B: UEC11-FC-R05 grantable windows (whole 256-byte credit
    # units) with 256-byte packets — the profile's own straitjacket,
    # randomized beyond the landed 200-trace grid (windows to 16 units,
    # mixed 256/512 packets, up to 40 events).
    rng = random.Random(SEED + 1)
    for _ in range(300):
        window = 256 * rng.randint(1, 16)
        delay = rng.choice([0, 1, 7, 50, 200, 600])
        events = _random_events(rng, window, delay, profile_legal=True)
        _run_attempt_sequence(window, delay, events)


def test_execute_trace_semantics_over_randomized_events() -> None:
    # execute_trace's rejected-trace semantics, preserved: execution
    # stops at the FIRST transmit the shadow ledger refuses; the prefix
    # is admitted whole and matches the oracle admission-for-admission;
    # the offending event is reported with the post-return balance.
    rng = random.Random(SEED + 2)
    checked = stopped = 0
    for _ in range(300):
        window = rng.choice([256 * k for k in (1, 2, 5, 16)] + [1000, 3844])
        delay = rng.randint(0, 400)
        events = _random_events(rng, window, delay, profile_legal=False)
        result = execute_trace(window, delay, events)
        shadow = _ShadowLedger(window, delay)
        prefix = 0
        for t, size in events:
            if shadow.attempt(t, size) == "rejection":
                assert not result.legal
                assert result.rejection is not None
                assert (result.rejection.time_ns, result.rejection.packet_bytes) == (
                    t,
                    size,
                )
                assert result.rejection.credit_bytes_at_decision == shadow.credit
                stopped += 1
                break
            prefix += 1
        else:
            assert result.legal and result.rejection is None
        assert len(result.admissions) == prefix
        assert [(a.time_ns, a.packet_bytes) for a in result.admissions] == [
            (t, s) for t, s in events[:prefix]
        ]
        checked += 1
    assert checked == 300
    assert stopped > 0, "the randomized stream never exercised a rejected trace"


def test_execute_trace_log_rederivation_is_exact() -> None:
    # The log-only conservation law on BOTH branches: for a refused
    # trace the stop-time sweep of the refusing attempt applied every
    # return due <= t_stop, so owed = {due > t_stop} and the balance
    # read from the rejection report must close the window; for a legal
    # trace the owed bytes follow the return-sweep rule (with D == 0
    # the final admission's own return is still pending) and must match
    # the independent ledger.
    rng = random.Random(SEED + 3)
    refusals = 0
    for _ in range(200):
        window = rng.randint(300, 9000)
        delay = rng.randint(0, 300)
        events = _random_events(rng, window, delay, profile_legal=False)
        result = execute_trace(window, delay, events)
        shadow = _ShadowLedger(window, delay)
        for t, size in events:  # drive the oracle to the same stop point
            if shadow.attempt(t, size) == "rejection":
                break
        if result.rejection is not None:
            t_stop = result.rejection.time_ns
            owed = sum(
                a.packet_bytes for a in result.admissions if a.return_due_ns > t_stop
            )
            balance = result.rejection.credit_bytes_at_decision
            assert balance == shadow.credit
            refusals += 1
        else:
            # legal: the last event is the last admission; its return is
            # pending unless a later attempt swept it — nothing follows.
            owed = _owed_from_log(result.admissions, events, delay)
            balance = window - owed
            assert owed == sum(b for _, b in shadow.pending)
        assert owed + balance == window, (window, delay, events)
        assert 0 <= balance <= window
    assert refusals > 0, "the stream never exercised the refused branch"


# -- the shared-link contention executor on randomized multi-flow instances ----


def _random_contention_config(rng: random.Random) -> ca.SharedLinkConfig:
    link_b = rng.choice([1, 2, 4, 8])
    packet = 256  # a multiple of every link_b in the set (A-CA-SER)
    data = {
        "link": {
            "bytes_per_ns": link_b,
            "hop_latency_ns": rng.choice([0, 50, 300]),
        },
        "tfc": {"credit_return_latency_ns": rng.choice([0, 25, 100])},
        "flows": [
            {
                "window_bytes": 256 * rng.randint(1, 8),  # UEC11-FC-R05
                "packet_bytes": packet,
                "packets": rng.randint(1, 10),
            }
            for _ in range(rng.randint(2, 4))
        ],
    }
    return ca.load_shared_link_config(data)


def test_randomized_contention_holds_per_context_invariants() -> None:
    # Beyond the landed 2-flow grids: 2..4 flows, randomized windows
    # and packet counts, both arbitration policies.  Per context: the
    # clause-1 sliding-window bound re-derived from the packet STARTS
    # (admissions reconstructed here, not trusted from the executor),
    # byte conservation of the context's own machine with the owed
    # bytes re-derived from its log, strictly increasing starts, and
    # the exact completion identity.  On the shared link: strict
    # serialization (no two packets overlap).
    rng = random.Random(SEED + 4)
    for _ in range(60):
        config = _random_contention_config(rng)
        for policy in ca.ARBITRATION_POLICIES:
            executor = SharedLinkContentionExecutor(config, policy)
            result = executor.run()
            busy: list[tuple[int, int]] = []
            for flow_result in result.flows:
                spec = config.flows[flow_result.flow_index]
                starts = flow_result.packet_starts_ns
                assert len(starts) == spec.packets
                assert all(a < b for a, b in zip(starts, starts[1:]))
                u = spec.packet_bytes // config.link_bytes_per_ns
                assert flow_result.completion_ns == starts[-1] + u + config.hop_latency_ns
                # Clause 1 re-derived HERE from the starts: every
                # half-open D-window carries at most W bytes.
                admissions = [
                    Admission(t, spec.packet_bytes, t + config.credit_loop_delay_ns)
                    for t in starts
                ]
                assert sliding_window_bound_holds(
                    admissions, spec.window_bytes, config.credit_loop_delay_ns
                ), (config, policy, flow_result.flow_index)
                # The context's machine: invariants at its own last step
                # (its last admission), plus the log-only re-derivation —
                # the machine's attempts ARE the starts, so the owed
                # bytes follow the return-sweep rule with the last start
                # as the sweep horizon.
                machine = executor.machines[flow_result.flow_index]
                assert 0 <= machine.credit_bytes <= spec.window_bytes
                owed = machine.pending_return_bytes
                assert machine.credit_bytes + owed == spec.window_bytes
                owed_from_log = sum(
                    a.packet_bytes
                    for a in machine.admissions
                    if a.return_due_ns > starts[-1]
                )
                last = machine.admissions[-1]
                if last.return_due_ns <= starts[-1]:  # D == 0: unswept tail
                    owed_from_log += last.packet_bytes
                assert owed_from_log == owed, (config, policy, flow_result.flow_index)
                assert machine.credit_bytes == spec.window_bytes - owed_from_log
                assert flow_result.window_bound_holds and flow_result.credit_conserved
                busy.extend((t, t + u) for t in starts)
            busy.sort()
            for (_, end_a), (start_b, _) in zip(busy, busy[1:]):
                assert start_b >= end_a, (config, policy, busy)
            # Determinism: a fresh executor replays byte-identically.
            assert SharedLinkContentionExecutor(config, policy).run() == result
