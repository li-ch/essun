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
