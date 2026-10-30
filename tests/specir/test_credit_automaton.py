"""The credit automaton's mechanics and the abstraction theorem as
properties (G8, 2026-10-30).

Companion of tests/golden/test_credit_automaton_golden.py (hand-derived
traces): this module pins the MACHINE invariants and sweeps the
abstraction theorem across a deterministic parameter grid — the
automaton is the ground truth; every closed form here is verified
against its execution, in both regimes, including the phase edges the
hand derivations cannot cover (``s`` not dividing ``W``, ``D`` not a
multiple of the serialization ``u``).

Properties pinned:

- LOAD SEMANTICS: non-grantable windows are rejected citing UEC11-FC-R05
  (the spec's credit granularity is a binding semantic); non-integral
  serialization is rejected citing A-CA-SER; no float ever enters the
  machine.
- MACHINE INVARIANTS: credit conservation (balance + owed == window,
  balance in range) at every step of seeded random traces; a rejection
  leaves the state bit-for-bit unchanged; trace order is enforced.
- SAFETY (theorem clause 1): every admitted event sequence — greedy or
  random-jittered — keeps every half-open D-window at or below W bytes.
- ACHIEVABILITY + CLOSED FORMS (clauses 2 and 4): across the grid, the
  greedy schedule equals the closed-form last start and the executed
  completion equals Eq. 3's single-link prediction plus the exact
  closed-form divergence; the rate laws agree per clause 3 (gap
  nonnegative, < s/D, zero iff ``s | W`` or link saturation).
- RECIPROCITY: the declared abstraction (analytical_l0_tfc, paper
  Eq. 3) names this automaton as its ground truth and the binding
  registry re-verifies the whole chain live.
"""

from __future__ import annotations

import dataclasses
import random
from fractions import Fraction

import pytest

from essun.specir import credit_automaton as ca
from essun.specir.credit_automaton import (
    Admission,
    Rejection,
    AutomatonConfig,
    CreditAdmissionAutomaton,
    GreedyLinkExecutor,
    execute_trace,
    finite_divergence_closed_form,
    greedy_last_start_closed_form,
    link_saturated,
    load_automaton_config,
    rate_divergence_exact,
    sliding_window_bound_holds,
    steady_state_rate_exact,
)


def _cfg(window: int, link: int, hop: int, credit_return: int, packet: int):
    return AutomatonConfig(window, link, hop, credit_return, packet)


BASE_MANIFEST = {
    "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
    "tfc": {
        "window_bytes": 12800,
        "credit_return_latency_ns": 200,
        "packet_bytes": 256,
    },
}


# -- load semantics ---------------------------------------------------------------


def test_loader_rejects_windows_not_in_credit_units() -> None:
    # UEC11-FC-R05: a window that is not an integral number of 256-byte
    # credit units is not grantable; the loader refuses it naming the
    # requirement (same discipline as the analytical backend).
    bad = dict(BASE_MANIFEST)
    bad["tfc"] = {**BASE_MANIFEST["tfc"], "window_bytes": 12850}
    with pytest.raises(ValueError, match="UEC11-FC-R05"):
        load_automaton_config(bad)


def test_loader_rejects_non_integral_serialization() -> None:
    # A-CA-SER: s/B must be a whole number of ns on the integer grid.
    bad = dict(BASE_MANIFEST)
    bad["tfc"] = {**BASE_MANIFEST["tfc"], "packet_bytes": 100}
    with pytest.raises(ValueError, match="A-CA-SER"):
        load_automaton_config(bad)


def test_loader_rejects_sub_packet_windows_and_degenerate_values() -> None:
    with pytest.raises(ValueError, match="less than one packet"):
        load_automaton_config(
            {
                **BASE_MANIFEST,
                "tfc": {
                    "window_bytes": 256,
                    "credit_return_latency_ns": 200,
                    "packet_bytes": 512,
                },
            }
        )
    with pytest.raises(ValueError, match="bytes_per_ns must be > 0"):
        load_automaton_config(
            {
                **BASE_MANIFEST,
                "link": {"bytes_per_ns": 0, "hop_latency_ns": 200},
            }
        )


def test_loader_admits_only_exact_integers() -> None:
    # The machine runs on integers; a float that happens to be integral
    # is still rejected (never silently rounded).
    with pytest.raises(ValueError, match="must be an integer"):
        load_automaton_config(
            {
                **BASE_MANIFEST,
                "tfc": {**BASE_MANIFEST["tfc"], "window_bytes": 12800.0},
            }
        )
    config = load_automaton_config(BASE_MANIFEST)
    assert config == AutomatonConfig(12800, 64, 200, 200, 256)
    assert ca.config_field_names() == (
        "window_bytes",
        "link_bytes_per_ns",
        "hop_latency_ns",
        "credit_return_latency_ns",
        "packet_bytes",
    )


# -- machine invariants -------------------------------------------------------------


def _snapshot(machine: CreditAdmissionAutomaton):
    return (machine.credit_bytes, machine.pending_returns)


def test_rejection_leaves_the_state_unchanged() -> None:
    machine = CreditAdmissionAutomaton(1024, 200)
    for t in (0, 4, 8, 12):
        machine.attempt(t, 256)
    before = _snapshot(machine)
    outcome = machine.attempt(16, 256)
    assert isinstance(outcome, Rejection)
    assert _snapshot(machine) == before
    # A rejection for MORE than the balance is likewise refused whole —
    # there is no partial transmit.
    outcome = machine.attempt(16, 512)
    assert isinstance(outcome, Rejection)


def test_credit_conservation_holds_across_seeded_random_traces() -> None:
    rng = random.Random(20261030)
    for _ in range(200):
        window = 256 * rng.randint(1, 8)
        machine = CreditAdmissionAutomaton(window, rng.randint(0, 500))
        t = 0
        for _ in range(rng.randint(1, 40)):
            t += rng.randint(0, 300)
            outcome = machine.attempt(t, 256)
            assert machine.credit_conserved(), (window, t)
            if isinstance(outcome, Rejection):
                break  # trace rejected; the prefix must still conserve
        assert machine.credit_conserved()


def test_trace_order_is_enforced() -> None:
    machine = CreditAdmissionAutomaton(1024, 200)
    machine.attempt(100, 256)
    with pytest.raises(ValueError, match="ordered event sequence"):
        machine.attempt(99, 256)


def test_returns_restore_exactly_what_transmits_consume() -> None:
    # Drain the window completely, then let every return land: at t=212
    # all four returns (due 200, 204, 208, 212) are applied and the
    # balance is exactly W again.  A transmit the window can never cover
    # (1025 > W) is rejected and REPORTS the post-return balance, so it
    # doubles as a state probe that mutates nothing.
    machine = CreditAdmissionAutomaton(1024, 200)
    for t in (0, 4, 8, 12):
        machine.attempt(t, 256)
    assert machine.credit_bytes == 0 and machine.pending_return_bytes == 1024
    probe = machine.attempt(212, 1025)
    assert isinstance(probe, Rejection)
    assert probe.credit_bytes_at_decision == 1024  # everything returned
    assert machine.pending_returns == ()  # nothing owed any more
    assert machine.credit_conserved()


# -- safety: the admission law IS a sliding-window bound ------------------------------


def test_seeded_random_legal_traces_respect_the_window_bound() -> None:
    # Theorem clause 1 as a property: every ADMITTED sequence (whatever
    # the attempt pattern — the bound does not care about scheduling)
    # keeps every half-open D-window at or below W bytes.
    rng = random.Random(42)
    for _ in range(300):
        window = 256 * rng.randint(1, 6)
        delay = rng.choice([1, 7, 100, 200])
        machine = CreditAdmissionAutomaton(window, delay)
        t = 0
        for _ in range(rng.randint(1, 50)):
            t += rng.randint(0, 2 * delay + 1)
            outcome = machine.attempt(t, rng.choice([128, 256]))
            if isinstance(outcome, Rejection):
                break
        assert sliding_window_bound_holds(
            machine.admissions, window, delay
        ), (window, delay, [a.time_ns for a in machine.admissions])


def test_sliding_window_bound_is_the_exact_maximum() -> None:
    # Greedy fills the bound to exactly W whenever s | W: nothing legal
    # can exceed it and greedy does not waste it.
    config = _cfg(12800, 64, 200, 200, 256)
    executor = GreedyLinkExecutor(config)
    executor.run_transfer(12800 * 4)
    admissions = executor.machine.admissions
    assert sliding_window_bound_holds(admissions, 12800, 400)
    peak = max(
        ca.sliding_window_bytes(admissions, t, 400)
        for t in {a.time_ns for a in admissions}
    )
    assert peak == 12800  # tight at the burst boundary


# -- the abstraction theorem across the grid -------------------------------------------

GRID = [
    (window, link, hop, credit_return, packet)
    for window in (512, 1024, 12800, 25600, 25664, 51200)
    for link in (1, 4, 64)
    for hop in (0, 2, 200)
    for credit_return in (0, 1, 200)
    for packet in (64, 256, 512)
    if packet % link == 0 and window % 256 == 0 and window >= packet
]


@pytest.mark.parametrize(
    "window,link,hop,credit_return,packet", GRID
)
def test_greedy_schedule_equals_the_closed_form_everywhere(
    window, link, hop, credit_return, packet
) -> None:
    # Theorem clauses 2 and 4 vs execution: the last packet start, the
    # completion, and the Eq. 3 divergence all match their closed forms
    # exactly, in both regimes, for every grid point (including s not
    # dividing W and D not a multiple of u).
    config = _cfg(window, link, hop, credit_return, packet)
    k = config.packets_per_window
    for n in (1, k, k + 1, 2 * k + (k // 2), 5 * k):
        result = GreedyLinkExecutor(config).run_transfer(n * packet)
        assert result.packet_starts_ns[-1] == greedy_last_start_closed_form(
            config, n
        )
        eq3 = ca.eq3_completion_single_link(config, n * packet)
        executed = Fraction(result.completion_ns)
        assert executed - eq3 == finite_divergence_closed_form(config, n)
        if not link_saturated(config):
            # Finite collectives never run LATER than the steady-state
            # identity predicts, and never more than D earlier.
            assert -config.credit_loop_delay_ns < executed - eq3 <= 0
        else:
            assert executed == eq3


@pytest.mark.parametrize("window,link,hop,credit_return,packet", GRID)
def test_rate_gap_is_the_credit_quantization(
    window, link, hop, credit_return, packet
) -> None:
    # Theorem clause 3: Eq. 3 never underestimates the automaton's rate;
    # the gap is below s/D; it is zero exactly when s | W (the
    # quantization vanishes) or the link saturates (both laws are B).
    config = _cfg(window, link, hop, credit_return, packet)
    gap = rate_divergence_exact(config)
    if config.credit_loop_delay_ns == 0:
        pytest.skip("D == 0: credit never gates, no rate gap to quantify")
    assert 0 <= gap
    assert gap < Fraction(packet, config.credit_loop_delay_ns)
    if gap == 0:
        assert (
            window % packet == 0 or link_saturated(config)
        ), "zero gap without s|W or saturation would contradict clause 3"
    if window % packet == 0:
        assert gap == 0
    if window < link * config.credit_loop_delay_ns and window % packet:
        assert gap == Fraction(
            window % packet, config.credit_loop_delay_ns
        )


@pytest.mark.parametrize("window,link,hop,credit_return,packet", GRID)
def test_steady_rate_is_achieved_by_execution(
    window, link, hop, credit_return, packet
) -> None:
    # The greedy executor's long-run admitted rate converges to the
    # exact steady law: over the horizon [0, last start] the deficit
    # against R_auto is bounded by the startup window (one D of burst
    # pattern at most), i.e. S/T >= R_auto * (T - D)/T exactly.
    config = _cfg(window, link, hop, credit_return, packet)
    if config.credit_loop_delay_ns == 0:
        pytest.skip("D == 0: rate is the link rate by construction")
    k = config.packets_per_window
    n = 6 * k
    result = GreedyLinkExecutor(config).run_transfer(n * packet)
    rate = steady_state_rate_exact(config)
    horizon = result.packet_starts_ns[-1]
    sent = Fraction(n * packet)
    lower = rate * Fraction(horizon - config.credit_loop_delay_ns, horizon)
    assert sent / Fraction(horizon) >= lower
    assert sent / Fraction(horizon) <= rate + Fraction(
        max(window, packet), horizon
    )


# -- the declared abstraction, two-sided --------------------------------------------


def test_abstraction_declaration_is_reciprocal() -> None:
    # The automaton declares analytical_l0_tfc (paper Eq. 3) as its
    # steady-state abstraction; the analytical backend declares this
    # automaton as its ground truth; the binding names both.  Neither
    # side can drift without this test failing.
    from essun.backends.analytical import l0_tfc

    assert ca.ABSTRACTION_MODULE == "essun.backends.analytical.l0_tfc"
    assert ca.ABSTRACTION_BACKEND_ID == l0_tfc.BACKEND_ID
    assert l0_tfc.GROUND_TRUTH_AUTOMATON == "essun.specir.credit_automaton"
    statement = ca.abstraction_statement(
        _cfg(12800, 64, 200, 200, 256)
    )
    assert statement["binding_id"] == ca.BINDING_ID
    assert statement["requirement_id"] == "UEC11-FC-R02"
    assert statement["abstraction"]["backend_id"] == "analytical_l0_tfc"
    assert statement["conditions"]["C1_packet_divides_window (s | W)"] is True
    assert statement["conditions"]["C2_integral_serialization (B | s)"] is True
    assert statement["rate_laws_agree"] is True  # flagship point: s | W


def test_binding_repoint_is_live_and_consistent() -> None:
    # The registry-level re-point: the FC-R02 simulated_behavior
    # binding's backend is THIS automaton, its golden is the golden
    # trace file, and the declared abstraction is the analytical law —
    # re-verified against the live registries.
    from essun.specir.anchors import AnchorRegistry
    from essun.specir.bindings import BINDINGS, check_all

    flagship = [
        b for b in BINDINGS if b.requirement_id == "UEC11-FC-R02"
    ]
    assert len(flagship) == 1
    binding = flagship[0]
    assert binding.backend_module == "essun.specir.credit_automaton"
    assert binding.backend_id == ca.BACKEND_ID
    assert binding.golden_test == "tests/golden/test_credit_automaton_golden.py"
    assert binding.steady_state_abstraction == (
        "essun.backends.analytical.l0_tfc",
        "analytical_l0_tfc",
    )
    registry = AnchorRegistry.load()
    registry.assert_valid()
    assert check_all(registry) == []


def test_requirement_check_fires_on_a_tampered_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If the live requirement object were reworded away from the
    # admission prohibition, the automaton's driving check must fire.
    import essun.specir.uec_credits_flow_control as stage

    swapped = tuple(
        dataclasses.replace(r, keyword="MAY")
        if r.requirement_id == "UEC11-FC-R02"
        else r
        for r in stage._REQUIREMENTS
    )
    monkeypatch.setattr(stage, "_REQUIREMENTS", swapped)
    problems = ca.check_requirements()
    assert any("MUST NOT" in p for p in problems)


# -- the shared-link contention extension (G7) --------------------------------------
#
# Properties of the multi-source shared-link executor: load semantics,
# per-context safety/conservation on grids, the no-window closed forms
# in both regimes, the arbitration-freedom fact (same parameters, moved
# per-flow observables), and the law candidates' exact misses.


def _shared(window0: int, n0: int, window1: int, n1: int, b: int = 8, hop: int = 300, lcr: int = 100, s: int = 256):
    data = {
        "link": {"bytes_per_ns": b, "hop_latency_ns": hop},
        "tfc": {"credit_return_latency_ns": lcr},
        "flows": [
            {"window_bytes": window0, "packet_bytes": s, "packets": n0},
            {"window_bytes": window1, "packet_bytes": s, "packets": n1},
        ],
    }
    return ca.load_shared_link_config(data)


def test_contention_loader_rejects_single_flow_and_spec_violations() -> None:
    # One flow is not a contention instance (the single-link machine's job).
    with pytest.raises(ValueError, match=">= 2 flows"):
        _shared(1024, 4, 1024, 4) if False else ca.load_shared_link_config(
            {
                "link": {"bytes_per_ns": 8, "hop_latency_ns": 300},
                "tfc": {"credit_return_latency_ns": 100},
                "flows": [{"window_bytes": 1024, "packet_bytes": 256, "packets": 4}],
            }
        )
    # UEC11-FC-R05 applies per flow context: a non-grantable window on
    # ANY flow is rejected citing the requirement.
    with pytest.raises(ValueError, match="UEC11-FC-R05"):
        _shared(1000, 4, 1024, 4)
    # A-CA-SER applies per flow on the shared link.
    with pytest.raises(ValueError, match="A-CA-SER"):
        _shared(1024, 4, 1024, 4, b=7)
    # A window below one packet executes no transfer (W=256 is one whole
    # credit unit, so the unit rule passes and the sub-packet rule fires).
    with pytest.raises(ValueError, match="window_bytes >= packet_bytes"):
        ca.load_shared_link_config(
            {
                "link": {"bytes_per_ns": 8, "hop_latency_ns": 300},
                "tfc": {"credit_return_latency_ns": 100},
                "flows": [
                    {"window_bytes": 256, "packet_bytes": 512, "packets": 4},
                    {"window_bytes": 1024, "packet_bytes": 256, "packets": 4},
                ],
            }
        )
    # Unknown arbitration names are rejected (A-CA-ARB is a declared set).
    config = _shared(1024, 4, 1024, 4)
    with pytest.raises(ValueError, match="A-CA-ARB"):
        ca.run_shared_link_contention(config, "random")


def test_contention_priority_never_starves_and_always_terminates() -> None:
    # Asymmetric sizes/windows: every flow completes, per-context safety
    # and conservation hold, and packet starts are strictly increasing
    # per flow while the shared link never transmits two packets at once.
    config = _shared(1280, 9, 512, 3)
    for policy in ca.ARBITRATION_POLICIES:
        result = ca.run_shared_link_contention(config, policy)
        assert len(result.flows) == 2
        assert all(f.window_bound_holds and f.credit_conserved for f in result.flows)
        busy: list[tuple[int, int]] = []
        for f in result.flows:
            starts = f.packet_starts_ns
            assert len(starts) == config.flows[f.flow_index].packets
            assert all(b > a for a, b in zip(starts, starts[1:]))
            u = config.flows[f.flow_index].packet_bytes // config.link_bytes_per_ns
            busy.extend((t, t + u) for t in starts)
        busy.sort()
        for (_, end_a), (start_b, _) in zip(busy, busy[1:]):
            assert start_b >= end_a  # the link serializes: no overlap


@pytest.mark.parametrize(
    "b,window,n0,n1",
    [
        (b, w, n0, n1)
        for b in (2, 8)
        for w in (256, 512, 1024)
        for n0 in (1, 2, 3)
        for n1 in (1, 2, 3, 5)
        if n0 <= w // 256 and n1 <= w // 256
    ],
)
def test_contention_no_window_closed_forms_match_execution(b, window, n0, n1):
    # Grid: whenever neither window binds (n_i <= k_i), the closed forms
    # equal execution for both arbitration policies, there are no idle
    # gaps, and the max completion equals the aggregate serialization
    # (n0 + n1)*u + L under both policies.
    config = _shared(window, n0, window, n1, b=b)
    assert ca.window_never_binds(config)
    u = 256 // b
    for policy in ca.ARBITRATION_POLICIES:
        result = ca.run_shared_link_contention(config, policy)
        expected = ca.no_window_closed_form(config, policy)
        got = tuple(f.completion_ns for f in result.flows)
        assert got == expected
        assert result.idle_gaps_ns == ()
        assert result.max_completion_ns == (n0 + n1) * u + config.hop_latency_ns
        # The per-flow alone-law is the STEADY-STATE cap M_i/min(B, W/D)+L
        # (re-derived independently here).  Note the regime fact it
        # exposes: in this grid W/D can sit below B (W=256: 0.64 B/ns at
        # D=400), so the fluid law calls the flow "window-gated" while
        # the machine's FINITE collective runs at full B -- n_i <= k_i
        # means the window never binds a finite transfer even below the
        # BDP; the law is the T >> D limit, clause C5, not this regime.
        d = config.credit_loop_delay_ns
        for index, n_i in ((0, n0), (1, n1)):
            rate = min(Fraction(b), Fraction(window, d))
            assert ca.law_alone_ns(config, index) == Fraction(n_i * 256) / rate + config.hop_latency_ns


@pytest.mark.parametrize(
    "window,n0,n1,lcr",
    [
        (w, n0, n1, lcr)
        for w in (512, 1024, 1280, 2048)
        for n0, n1 in ((6, 6), (7, 5), (9, 3), (12, 8))
        for lcr in (50, 100, 260)
    ],
)
def test_contention_gated_grids_hold_safety_and_bounds(window, n0, n1, lcr):
    # Grid over the gated regime: per-context clause-1 safety and byte
    # conservation on every execution; the per-flow alone-law and the
    # aggregate candidate are each violated by at least one flow at
    # every point with two backlogged flows (the laws do not compose);
    # and both policies produce EXACT integer completions with idle
    # gaps only where every context is drained.
    config = _shared(window, n0, window, n1, lcr=lcr)
    if ca.window_never_binds(config):
        pytest.skip("grid point not in the gated regime")
    for policy in ca.ARBITRATION_POLICIES:
        result = ca.run_shared_link_contention(config, policy)
        for f in result.flows:
            assert f.window_bound_holds and f.credit_conserved
        # The machine's max completion may sit on EITHER side of the
        # fluid candidates (the exact trace has bursts and gaps they
        # idealize away) — what is pinned is EXACTNESS, not agreement:
        every_gap_has_room = all(
            gap[1] > gap[0] for gap in result.idle_gaps_ns
        )
        assert every_gap_has_room
        # Determinism: same inputs, same bytes.
        replay = ca.run_shared_link_contention(config, policy)
        assert replay == result


def test_contention_arbitration_moves_observables_at_fixed_parameters() -> None:
    # THE hard-case property: with every flow parameter FIXED, the
    # per-flow and collective observables move with the arbitration
    # freedom — the input the analytical law does not have.  No-window
    # regime: flow 0's completion differs between policies; gated
    # regime: the MAX completion differs (goldens pin the exact values).
    no_window = _shared(8192, 32, 8192, 32)
    completions = {
        policy: tuple(f.completion_ns for f in ca.run_shared_link_contention(no_window, policy).flows)
        for policy in ca.ARBITRATION_POLICIES
    }
    assert completions["index_priority"] != completions["round_robin"]
    gated = _shared(1280, 8, 1280, 8)
    maxima = {
        policy: ca.run_shared_link_contention(gated, policy).max_completion_ns
        for policy in ca.ARBITRATION_POLICIES
    }
    assert maxima["index_priority"] != maxima["round_robin"]


def test_contention_statement_is_machine_readable_and_exact() -> None:
    # The G7 statement carries the exact machine values, the law
    # candidates, and the safety booleans — the record builder's source.
    config = _shared(1280, 8, 1280, 8)
    statement = ca.contention_statement(config, "round_robin")
    assert statement["extension"] == "multi_source_shared_link_contention"
    assert statement["arbitration"] == "round_robin"
    assert statement["window_never_binds"] is False
    assert statement["per_flow"][0]["completion_ns_exact"] == 860
    assert statement["per_flow"][1]["completion_ns_exact"] == 892
    assert statement["law_aggregate_ns_exact"] == "940"
    assert statement["per_flow"][0]["law_alone_ns_exact"] == "940"
    assert statement["idle_gaps_ns"] == [[320, 400]]
    assert statement["per_flow"][0]["window_bound_holds"] is True
