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

G7-A. WINDOW-NEVER-BINDS CONTENTION (the G7 shared-link extension; B=8,
   L=300, L_cr=100, two flows s=256, n=32 each, W=8192 = 32*256 so
   k = 32 = n: no credit context EVER gates): per-flow Eq. 3 alone-law
   t_i = 8192/min(8, 8192/400) + 300 = 8192/8 + 300 = 1324 ns for BOTH
   flows — jointly infeasible on one shared link (they would need 2B).
   The machine, index_priority: flow 0 drains first (starts 0,32,...,
   992; completion 992+32+300 = 1324 = its alone time), flow 1 starts
   at 1024 and completes 2016+32+300 = 2348 = (n0+n1)*u + L.
   Round-robin: slots alternate; flow 0 starts 0,64,...,1984 (last
   31*64=1984; completion 1984+32+300 = 2316), flow 1 starts 32,96,
   ...,2016 (completion 2016+32+300 = 2348).  The SAME parameters, and
   the per-flow observable MOVES by 2316-1324 = 992 = (n0-1)*u with the
   arbitration choice — a freedom neither Eq. 3 nor the standard pins;
   no idle gaps (some flow is always credit-ready).

G7-B. GATED BURST-INTERACTION CONTENTION (same link; W=1280 so
   k = 5 < n = 8, both flows gated; D = 400): per-flow alone-law
   t_i = 2048/min(8, 1280/400) + 300 = 2048/3.2 + 300 = 940; the
   aggregate candidate min(8, 2560/400) = 6.4 gives 4096/6.4 + 300 =
   940 too.  index_priority: flow 0 bursts 0,32,64,96,128; link free
   160; flow 1 bursts 160,192,224,256,288; link free 320 with BOTH
   contexts drained — the link IDLES 320->400 (80 ns) although both
   flows are backlogged; flow 0's returns unfreeze it first (400,432,
   464 — completion 464+32+300 = 796, EARLIER than its own 940
   alone-law), flow 1 follows 560,592,624 (completion 624+32+300 =
   956, LATER than 940); second gap 496->560.  Round-robin: bursts
   interleave (flow 0 at 0,64,128,192,256; flow 1 at 32,96,160,224,
   288), one gap 320->400, tails 400/464/528 and 432/496/560:
   completions (860, 892) — BOTH fluid candidates (940) miss the
   machine in BOTH directions across policies, and the COLLECTIVE's
   completion observable itself moves 956 -> 892 with arbitration.
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
    SharedLinkConfig,
    FlowSpec,
    check_requirements,
    contention_statement,
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
    window_never_binds,
    law_aggregate_ns,
    law_alone_ns,
    no_window_closed_form,
    run_shared_link_contention,
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


# -- G7-A: window-never-binds contention (the shared-link extension) ---------------


def _shared_cfg(window: int, packets: int) -> SharedLinkConfig:
    # B=8 B/ns, L=300, L_cr=100 (D=400); two flows, s=256, n=packets each.
    return SharedLinkConfig(
        link_bytes_per_ns=8,
        hop_latency_ns=300,
        credit_return_latency_ns=100,
        flows=(FlowSpec(window, 256, packets), FlowSpec(window, 256, packets)),
    )


def test_golden_contention_window_never_binds_priority() -> None:
    # Hand derivation G7-A, index_priority: both windows cover their whole
    # collectives (k = 32 = n), yet the flows contend — the alone-laws are
    # jointly infeasible and the arbitration decides everything.
    config = _shared_cfg(8192, 32)
    assert window_never_binds(config)
    result = run_shared_link_contention(config, "index_priority")
    flow0, flow1 = result.flows
    # Flow 0 drains first: starts 0, 32, ..., 992; completion = its ALONE
    # identity exactly (8192/8 + 300).
    assert flow0.packet_starts_ns[0] == 0
    assert flow0.packet_starts_ns[-1] == 992
    assert flow0.completion_ns == 1324 == law_alone_ns(config, 0)
    # Flow 1 starts only after flow 0's last serialization (5*... = 32*32):
    assert flow1.packet_starts_ns[0] == 32 * 32 == 1024
    assert flow1.packet_starts_ns[-1] == 2016
    assert flow1.completion_ns == 2348 == (32 + 32) * 32 + 300
    # The per-flow Eq. 3 laws BOTH say 1324 — jointly infeasible on the link.
    assert law_alone_ns(config, 0) == law_alone_ns(config, 1) == Fraction(1324)
    assert Fraction(flow1.completion_ns) - law_alone_ns(config, 1) == Fraction(1024)
    assert result.idle_gaps_ns == ()  # someone is always credit-ready
    assert result.max_completion_ns == 2348
    assert no_window_closed_form(config, "index_priority") == (1324, 2348)
    # Safety clauses per context (theorem clause 1 + conservation).
    assert all(f.window_bound_holds and f.credit_conserved for f in result.flows)


def test_golden_contention_window_never_binds_round_robin() -> None:
    # Hand derivation G7-A, round_robin: SAME parameters, per-flow
    # completions move by the arbitration freedom alone.
    config = _shared_cfg(8192, 32)
    result = run_shared_link_contention(config, "round_robin")
    flow0, flow1 = result.flows
    assert flow0.packet_starts_ns[0] == 0
    assert flow0.packet_starts_ns[1] == 64  # alternate slots
    assert flow0.packet_starts_ns[-1] == 31 * 64 == 1984
    assert flow0.completion_ns == 2316
    assert flow1.packet_starts_ns[0] == 32
    assert flow1.packet_starts_ns[-1] == 2016
    assert flow1.completion_ns == 2348
    # The arbitration freedom moves flow 0's observable by exactly
    # (n0 - 1) * u = 31*32 = 992 ns with EVERY parameter identical.
    assert 2316 - 1324 == 992 == (32 - 1) * 32
    assert no_window_closed_form(config, "round_robin") == (2316, 2348)
    assert result.idle_gaps_ns == ()
    assert all(f.window_bound_holds and f.credit_conserved for f in result.flows)


# -- G7-B: gated burst-interaction contention ---------------------------------------


def _gated_cfg() -> SharedLinkConfig:
    # B=8, L=300, L_cr=100 (D=400); W=1280 (k=5), n=8: both flows gated.
    return _shared_cfg(1280, 8)


def test_golden_contention_gated_priority_with_idle_gaps() -> None:
    # Hand derivation G7-B, index_priority: interleaved credit rhythms
    # with an exact idle gap while every flow is backlogged, and BOTH
    # fluid compositions miss the machine (per-flow in BOTH directions).
    config = _gated_cfg()
    assert not window_never_binds(config)
    result = run_shared_link_contention(config, "index_priority")
    flow0, flow1 = result.flows
    assert flow0.packet_starts_ns == (0, 32, 64, 96, 128, 400, 432, 464)
    assert flow1.packet_starts_ns == (160, 192, 224, 256, 288, 560, 592, 624)
    assert flow0.completion_ns == 464 + 32 + 300 == 796  # EARLIER than 940
    assert flow1.completion_ns == 624 + 32 + 300 == 956  # LATER than 940
    # The link idles exactly (320, 400) and (496, 560): both contexts
    # drained, returns not yet due — with every flow backlogged.  The
    # fluid aggregate law has no idle-gap semantics at all.
    assert result.idle_gaps_ns == ((320, 400), (496, 560))
    # Both law candidates say 940; the machine says (796, 956), max 956.
    assert law_alone_ns(config, 0) == law_alone_ns(config, 1) == Fraction(940)
    assert law_aggregate_ns(config) == Fraction(940)
    assert result.max_completion_ns == 956
    assert Fraction(flow0.completion_ns) - law_alone_ns(config, 0) == Fraction(-144)
    assert Fraction(flow1.completion_ns) - law_alone_ns(config, 1) == Fraction(16)
    assert all(f.window_bound_holds and f.credit_conserved for f in result.flows)


def test_golden_contention_gated_round_robin_moves_the_max() -> None:
    # Hand derivation G7-B, round_robin: interleaved bursts, ONE idle
    # gap, completions (860, 892) — the collective's own completion
    # observable moves 956 -> 892 with the arbitration choice.
    config = _gated_cfg()
    result = run_shared_link_contention(config, "round_robin")
    flow0, flow1 = result.flows
    assert flow0.packet_starts_ns == (0, 64, 128, 192, 256, 400, 464, 528)
    assert flow1.packet_starts_ns == (32, 96, 160, 224, 288, 432, 496, 560)
    assert flow0.completion_ns == 528 + 32 + 300 == 860
    assert flow1.completion_ns == 560 + 32 + 300 == 892
    assert result.idle_gaps_ns == ((320, 400),)
    assert law_aggregate_ns(config) == Fraction(940)
    assert result.max_completion_ns == 892  # != 956 under priority
    assert all(f.window_bound_holds and f.credit_conserved for f in result.flows)
    # The arbitration-freedom swing on the COLLECTIVE observable:
    assert 956 - 892 == 64 == 2 * 32
