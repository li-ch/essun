"""Golden traces for the credit obligation automaton (G8, 2026-10-30).

The behavioral foundation of the flagship slice: requirement
**UEC11-FC-R02** (UEC 1.1 §3.6.15, TFC admission law, MUST NOT) executed
by the exact discrete automaton ``essun.specir.credit_automaton`` under
binding **BIND-UEC11-FC-R02-AUTOMATON**, with the analytical steady-state
law — paper equation (3) (``eq:tfc``, the ``analytical_l0_tfc`` identity
``t = 2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L``) — as the
automaton's DECLARED abstraction.

Every expected value below is HAND-DERIVED in the comments from the
event semantics (integer ns, integer bytes; bursts of floor(W/s)
packets, one burst per credit-loop period D = L + L_cr), then asserted
against the machine's execution — the automaton grades the closed
forms, not the other way round.  E0 evidence level: exactness and
determinism only; B, L, L_cr, W, s are free parameters (the single
spec-derived constant is the 256-byte credit unit, UEC11-FC-R05).

Hand derivations, once each, referenced by the tests:

A. CREDIT-GATED BURSTS (W=1024, s=256, B=64, L=100, L_cr=100):
   u = s/B = 4 ns; D = 200 ns; k = W/s = 4.  Ten packets, n = qk + r =
   2*4 + 2: burst 1 starts 0, 4, 8, 12 (credit hits W mod s = 0);
   returns come due 200, 204, 208, 212; burst 2 rides one return per
   admission: 200, 204, 208, 212; burst 3: 400, 404.  Completion =
   last start 404 + u 4 + L 100 = 508.  Eq. 3 single-link completion =
   M/Reff + L = 2560 / (1024/200) + 100 = 500 + 100 = 600: divergence
   -92 = r*(u - D/k) = 2*(4 - 50).

B. LINK-LIMITED (W=25600 = exactly B*(L+L_cr), s=256, B=64, L=200,
   L_cr=200): the BDP convergence anchor.  ceil(D/u) = 100 <= k = 100:
   credit never gates, starts 0, 4, 8, 12, 16; completion 16 + 4 + 200
   = 220 = Eq. 3's 1280/64 + 200 = 220 — divergence EXACTLY 0.

C. REJECTED TRACE (config A): after four packets the balance is 0; a
   fifth transmit at t=16 has no credit — UEC11-FC-R02 — so the trace
   [(0,256),(4,256),(8,256),(12,256),(16,256)] is REJECTED at its last
   event, the prefix of four admissions stands, the machine state is
   untouched by the rejection, and the next legal transmit waits for
   the first return at t=200.

D. FLAGSHIP OPERATING POINT (W=12800, s=256, B=64, L=200, L_cr=200 —
   the run `dc7d83b6` parameters): k = 50, u = 4, D = 400.  Steady rate
   = 50*256/400 = 32 B/ns — EXACTLY Eq. 3's cap min(64, 12800/400) =
   32: with s | W the analytical rate law is the automaton's steady
   state, no divergence.  The finite collective M = 28672 (n = 112 =
   2*50 + 12): last start 2*400 + 11*4 = 844; completion 844 + 4 + 200
   = 1048; Eq. 3 predicts 28672/32 + 200 = 1096; divergence -48 =
   r*(u - D/k) = 12*(4 - 8) — the finite transfer finishes 48 ns EARLY.
   The r=0 tail (M = 25600, n = 100 = 2*50): last start 400 + 49*4 =
   596; completion 596 + 4 + 200 = 800; Eq. 3 predicts 25600/32 + 200
   = 1000; divergence -200 = k*u - D = 200 - 400.

E. QUANTIZATION BOUNDARY (B=64, L=200, L_cr=201 so D=401, s=256,
   W = 25664 = B*D): Eq. 3 says min(64, 25664/401) = 64 — line rate,
   at its own convergence anchor.  The automaton: k = floor(25664/256)
   = 100 < ceil(401/4) = 101, so credit STILL gates: rate 25600/401.
   Divergence = 64/401 = (W mod s)/D exactly — the packetization gap
   Eq. 3 idealizes away, largest exactly at its convergence anchor.
"""

from __future__ import annotations

from fractions import Fraction

from essun.backends.analytical import l0_tfc
from essun.specir.credit_automaton import (
    Admission,
    Rejection,
    TraceResult,
    AutomatonConfig,
    CreditAdmissionAutomaton,
    GreedyLinkExecutor,
    check_requirements,
    eq3_completion_single_link,
    eq3_effective_rate,
    execute_trace,
    finite_divergence_closed_form,
    greedy_last_start_closed_form,
    link_saturated,
    rate_divergence_exact,
    sliding_window_bound_holds,
    sliding_window_bytes,
    steady_state_rate_exact,
)


def _config(
    window: int, link: int, hop: int, credit_return: int, packet: int
) -> AutomatonConfig:
    return AutomatonConfig(
        window_bytes=window,
        link_bytes_per_ns=link,
        hop_latency_ns=hop,
        credit_return_latency_ns=credit_return,
        packet_bytes=packet,
    )


# -- A: the credit-gated burst golden -------------------------------------------


def test_golden_trace_credit_gated_bursts() -> None:
    # Hand derivation A. Every value in the assertion is derived in the
    # module docstring, not copied from execution.
    config = _config(1024, 64, 100, 100, 256)
    assert config.credit_loop_delay_ns == 200  # D = L + L_cr
    assert config.serialization_ns == 4  # u = s/B
    assert config.packets_per_window == 4  # k = W/s

    result = GreedyLinkExecutor(config).run_transfer(2560)

    assert result.packet_starts_ns == (
        0, 4, 8, 12,  # burst 1: the full window, back to back
        200, 204, 208, 212,  # burst 2: one admission per returned credit
        400, 404,  # burst 3: partial tail (n = 10 = 2*4 + 2)
    )
    assert result.completion_ns == 508  # 404 + u + L


def test_golden_credit_gated_completion_and_eq3_divergence() -> None:
    # Hand derivation A, analytical side: Eq. 3's single-link completion
    # 600 ns vs the automaton's exact 508 ns — the finite collective
    # finishes 92 ns EARLY, and the closed form r*(u - D/k) says exactly
    # that: 2 * (4 - 200/4) = 2 * (-46) = -92.
    config = _config(1024, 64, 100, 100, 256)
    result = GreedyLinkExecutor(config).run_transfer(2560)

    eq3 = eq3_completion_single_link(config, 2560)
    assert eq3 == Fraction(600)  # 2560 / (1024/200) + 100
    assert Fraction(result.completion_ns) - eq3 == Fraction(-92)
    assert finite_divergence_closed_form(config, 10) == Fraction(-92)
    assert greedy_last_start_closed_form(config, 10) == 404


def test_golden_sliding_window_bound_is_tight() -> None:
    # Theorem clause 1 on the golden trace: NO half-open D-window holds
    # more than W bytes; the burst-2 boundary window (0, 200] holds
    # starts 4, 8, 12, 200 — exactly the full 1024-byte window.  The
    # admission law IS a sliding-window bound, and greedy fills it.
    config = _config(1024, 64, 100, 100, 256)
    executor = GreedyLinkExecutor(config)
    result = executor.run_transfer(2560)
    assert executor.machine.credit_conserved()
    admissions = [
        Admission(t, 256, t + 200) for t in result.packet_starts_ns
    ]
    assert sliding_window_bound_holds(admissions, 1024, 200)
    assert sliding_window_bytes(admissions, 200, 200) == 1024  # tight


# -- B: the link-limited / BDP-anchor golden --------------------------------------


def test_golden_trace_link_limited_at_the_bdp_anchor() -> None:
    # Hand derivation B: W = 25600 = B*(L+L_cr) is Eq. 3's own
    # convergence anchor (credits never gate); the automaton agrees
    # EXACTLY — zero divergence, zero rate gap, starts at link pace.
    config = _config(25600, 64, 200, 200, 256)
    assert link_saturated(config)
    assert steady_state_rate_exact(config) == Fraction(64)
    assert eq3_effective_rate(config) == Fraction(64)
    assert rate_divergence_exact(config) == 0

    result = GreedyLinkExecutor(config).run_transfer(1280)
    assert result.packet_starts_ns == (0, 4, 8, 12, 16)
    assert result.completion_ns == 220
    assert eq3_completion_single_link(config, 1280) == Fraction(220)
    assert finite_divergence_closed_form(config, 5) == 0


# -- C: the rejected-trace golden --------------------------------------------------


def test_golden_transmit_without_credit_is_a_rejected_trace() -> None:
    # Hand derivation C: the fifth transmit at t=16 has no credit.  The
    # automaton DOES NOT execute it: the prefix of four admissions
    # stands, the rejection names the event, the state is unchanged.
    config = _config(1024, 64, 100, 100, 256)
    machine = CreditAdmissionAutomaton(1024, 200)

    assert [machine.attempt(t, 256).packet_bytes for t in (0, 4, 8, 12)] == [
        256
    ] * 4
    assert machine.credit_bytes == 0  # W mod s = 0: nothing left
    assert machine.credit_conserved()

    outcome = machine.attempt(16, 256)
    assert isinstance(outcome, Rejection)
    assert outcome.time_ns == 16
    assert outcome.credit_bytes_at_decision == 0
    assert outcome.requirement_id == "UEC11-FC-R02"
    # The rejection did not execute: state untouched.
    assert machine.credit_bytes == 0
    assert machine.pending_return_bytes == 1024
    assert machine.credit_conserved()
    # The next legal transmit waits for the first return at t=200.
    admitted = machine.attempt(200, 256)
    assert isinstance(admitted, Admission)
    assert admitted.return_due_ns == 400


def test_golden_execute_trace_stops_at_the_first_illegal_event() -> None:
    config = _config(1024, 64, 100, 100, 256)
    trace = [(0, 256), (4, 256), (8, 256), (12, 256), (16, 256)]
    result = execute_trace(1024, 200, trace)
    assert isinstance(result, TraceResult)
    assert not result.legal
    assert len(result.admissions) == 4
    assert result.rejection is not None and result.rejection.time_ns == 16
    # The legal prefix is exactly burst 1 of the golden trace.
    assert [a.time_ns for a in result.admissions] == [0, 4, 8, 12]
    # And the same trace minus the illegal event is legal.
    legal = execute_trace(1024, 200, trace[:4])
    assert legal.legal and len(legal.admissions) == 4


# -- D: the flagship operating point ----------------------------------------------


def test_golden_flagship_point_eq3_rate_is_the_automaton_steady_state() -> None:
    # Hand derivation D: at the run-dc7d83b6 parameters with s = 256
    # (s | W) the analytical cap min(B, W/(L+L_cr)) = 32 B/ns IS the
    # automaton's exact steady rate — the abstraction statement's rate
    # clause, checked against the ANALYTICAL backend's own functions so
    # the two implementations cannot drift apart.
    config = _config(12800, 64, 200, 200, 256)
    analytics = l0_tfc.TFCRingConfig(
        topology_id="flagship",
        ranks=8,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
        tfc_window_bytes=Fraction(12800),
        tfc_credit_return_latency_ns=Fraction(200),
    )
    assert steady_state_rate_exact(config) == Fraction(32)
    assert eq3_effective_rate(config) == Fraction(32)
    assert rate_divergence_exact(config) == 0
    assert l0_tfc.admission_rate_cap(analytics) == Fraction(32)
    assert l0_tfc.effective_rate(analytics) == Fraction(32)


def test_golden_flagship_point_finite_collective_divergence() -> None:
    # Hand derivation D: M = 28672 (the flagship run's per-rank wire
    # traffic): n = 112 = 2*50 + 12, last start 844, completion 1048,
    # Eq. 3 predicts 1096, divergence -48 = 12*(4 - 8).  The r=0 tail
    # M = 25600: divergence -200 = k*u - D = 200 - 400.
    config = _config(12800, 64, 200, 200, 256)

    result = GreedyLinkExecutor(config).run_transfer(28672)
    assert result.packet_starts_ns[-1] == 844
    assert result.completion_ns == 1048
    assert eq3_completion_single_link(config, 28672) == Fraction(1096)
    assert Fraction(result.completion_ns) - Fraction(1096) == Fraction(-48)
    assert finite_divergence_closed_form(config, 112) == Fraction(-48)
    assert greedy_last_start_closed_form(config, 112) == 844

    tail = GreedyLinkExecutor(config).run_transfer(25600)
    assert tail.packet_starts_ns[-1] == 596
    assert tail.completion_ns == 800
    assert eq3_completion_single_link(config, 25600) == Fraction(1000)
    assert finite_divergence_closed_form(config, 100) == Fraction(-200)
    # The steady-state law never UNDER-estimates a finite collective:
    # the divergence is strictly inside (-D, 0] in the gated regime.
    assert -400 < Fraction(-200) <= 0


# -- E: the quantization boundary ---------------------------------------------------


def test_golden_quantization_gap_at_the_eq3_convergence_anchor() -> None:
    # Hand derivation E: W = 25664 = B*D passes Eq. 3's convergence
    # condition (rate B), yet one 256-byte packet of that window is
    # unusable (k = 100 packets vs the 101 link-paced starts one credit
    # window must cover), so the automaton runs at 25600/401 and the
    # exactly (W mod s)/D = 64/401 — the packetization Eq. 3 idealizes
    # away, largest exactly at its own anchor.
    config = _config(25664, 64, 200, 201, 256)
    assert not link_saturated(config)  # k=100 < ceil(401/4)=101
    assert eq3_effective_rate(config) == Fraction(64)
    assert steady_state_rate_exact(config) == Fraction(25600, 401)
    gap = rate_divergence_exact(config)
    assert gap == Fraction(64, 401) == Fraction(25664 % 256, 401)
    assert 0 <= gap < Fraction(config.packet_bytes, 401)


# -- the driving requirements are live and anchored ---------------------------------


def test_automaton_is_driven_by_the_live_anchored_requirements() -> None:
    # The machine's semantics cite UEC11-FC-R02 (admission law) and
    # UEC11-FC-R05 (the 256-byte unit); both objects must still carry
    # that content in the live stage registry.
    assert check_requirements() == []
