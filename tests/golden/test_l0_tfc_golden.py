"""Golden identities for the analytical L0-TFC backend (flagship slice).

Expected values are derived IN THIS FILE by exact Fraction arithmetic from
the stated identities (handoff rule: goldens derive from the specified
identities, never from the implementation's output). The chain under test
is the full flagship slice: anchored requirement UEC11-FC-R02 (UEC 1.1
§3.6.15, TFC admission law) -> binding BIND-UEC11-FC-R02-L0TFC
(essun.specir.bindings) -> parameters tfc.window_bytes /
tfc.credit_return_latency_ns of analytical_l0_tfc -> O-CCT change.

Free parameters under test (all registered in
experiments/vertical_slice/assumptions_tfc.yaml; none standard-derived,
none measured):

    B    = 64 bytes/ns     (A-TFC-BW, same value as the L0 ring anchor)
    L    = 200 ns          (A-TFC-LAT, same value as the L0 ring anchor)
    L_cr = 200 ns          (A-TFC-CR)
    W    = 12800 bytes     (A-TFC-W = 50 credit units of 256 bytes)

The only standard-derived constant is the 256-byte credit unit
(UEC11-FC-R05, anchor UEC11-S3.6.15-TFC).
"""

from fractions import Fraction

import pytest

from essun.backends.analytical import l0, l0_tfc
from essun.workload import w1

RANKS = 8
B = Fraction(64)
L = Fraction(200)
LCR = Fraction(200)
W = Fraction(12800)  # 50 x 256-byte credit units
RTT = L + LCR  # 400 ns, derived
RMAX = W / RTT  # 32 bytes/ns, the admission-law rate cap, derived
BDP = B * RTT  # 25600 bytes = 100 credit units, derived


def _infra(window: Fraction = W, credit_return: Fraction = LCR) -> l0_tfc.TFCRingConfig:
    return l0_tfc.TFCRingConfig(
        topology_id="ring8_tfc_window_v1",
        ranks=RANKS,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
        tfc_window_bytes=window,
        tfc_credit_return_latency_ns=credit_return,
    )


def _l0_infra() -> l0.InfraConfig:
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
    )


def _ops(payload: int = 16384):
    return w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=payload)
    )


# -- the identity, window-limited regime --------------------------------------


def test_admission_rate_cap_is_one_window_per_credit_rtt():
    # UEC11-FC-R02 as a rate law: W / (L + L_cr) = 12800 / 400 = 32 B/ns.
    assert l0_tfc.credit_rtt_ns(_infra()) == Fraction(400)
    assert l0_tfc.admission_rate_cap(_infra()) == Fraction(12800, 400)
    assert l0_tfc.admission_rate_cap(_infra()) == Fraction(32)
    assert l0_tfc.effective_rate(_infra()) == min(B, Fraction(32)) == Fraction(32)


def test_bandwidth_delay_product_is_100_credit_units():
    # BDP = B * RTT = 64 * 400 = 25600 bytes = 100 x 256-byte units.
    assert l0_tfc.bandwidth_delay_product(_infra()) == Fraction(25600)
    assert l0_tfc.bandwidth_delay_product(_infra()) / 256 == Fraction(100)


def test_completion_time_identity_window_limited():
    # t = T / min(B, W/RTT) + 2*(r-1)*L with T = 2*(r-1)/r*M = 7/4*16384
    # = 28672: t = 28672/32 + 14*200 = 896 + 2800 = 3696 ns exactly.
    T = Fraction(2 * (RANKS - 1) * 16384, RANKS)
    assert T == Fraction(28672)
    expected = T / min(B, W / RTT) + 2 * (RANKS - 1) * L
    assert expected == Fraction(3696)
    assert (
        l0_tfc.ring_allreduce_time_tfc_ns(16384, RANKS, _infra())
        == Fraction(3696)
    )


def test_admission_inflight_bound_holds_with_equality_iff_window_limited():
    # Structural admission invariant (UEC11-FC-R02): Reff*RTT <= W.
    window_limited = l0_tfc.effective_rate(_infra()) * RTT
    assert window_limited == W  # equality in the window-limited regime
    at_bdp = l0_tfc.effective_rate(_infra(window=BDP)) * RTT
    assert at_bdp == BDP  # knife edge: still equality, but Reff == B
    assert l0_tfc.effective_rate(_infra(window=BDP)) == B
    above = l0_tfc.effective_rate(_infra(window=BDP + 256)) * RTT
    assert above == BDP < BDP + 256  # strictly below the window
    below = l0_tfc.effective_rate(_infra(window=BDP - 256)) * RTT
    assert below == BDP - 256  # equality again (window-limited)


# -- the convergence anchor to the landed L0 identity -------------------------


def test_converges_to_l0_exactly_at_and_above_bdp():
    # W >= B*(L+L_cr) => credits never gate => t_TFC == t_L0 EXACTLY.
    for window in (BDP, BDP + 256, BDP * 4):
        assert l0_tfc.ring_allreduce_time_tfc_ns(
            16384, RANKS, _infra(window=window)
        ) == l0.ring_allreduce_time_ns(16384, RANKS, _l0_infra())
    # and t_L0 for these parameters is the landed golden literal 3248 ns.
    assert l0.ring_allreduce_time_ns(16384, RANKS, _l0_infra()) == Fraction(3248)


def test_window_below_bdp_is_strictly_slower():
    # One credit unit below the BDP the completion time strictly increases;
    # the gap is exactly T*(RTT/W - 1/B) — derived here, not from outputs.
    T = Fraction(2 * (RANKS - 1) * 16384, RANKS)
    expected_gap = T * (1 / (W / RTT) - 1 / B)
    gap = l0_tfc.ring_allreduce_time_tfc_ns(
        16384, RANKS, _infra()
    ) - l0.ring_allreduce_time_ns(16384, RANKS, _l0_infra())
    assert gap == expected_gap == Fraction(448)


# -- the observable change: O-CCT moves, O-CONSERVATION does not --------------


def test_execute_moves_cct_and_conserves_bytes():
    result = l0_tfc.execute(_ops(), _infra())
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["violations"] == 0
    # The window gates rate, never byte count: 2*(r-1)*M = 229376.
    assert conservation["total_wire_bytes_exact"] == str(
        Fraction(2 * (RANKS - 1) * 16384)
    )
    cct = result["observables"]["O-CCT"]
    assert cct["kind"] == "analytical"
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3696))
    # Provenance block names the requirement the run exercised.
    tfc = cct["tfc"]
    assert tfc["requirement_id"] == "UEC11-FC-R02"
    assert tfc["binding_id"] == "BIND-UEC11-FC-R02-L0TFC"
    assert tfc["window_limited"] is True
    assert tfc["peak_in_flight_bytes_exact"] == str(W)
    assert result["requirement_bindings"][0]["requirement_id"] == "UEC11-FC-R02"


def test_observable_change_against_l0_is_the_declared_delta():
    # The binding's observable claim: O-CCT differs from the unbound L0 run
    # by exactly the admission-law term; derived independently per backend.
    tfc_mean = Fraction(
        l0_tfc.execute(_ops(), _infra())["observables"]["O-CCT"][
            "completion_time_ns_mean_exact"
        ]
    )
    l0_mean = Fraction(
        l0.execute(_ops(), _l0_infra())["observables"]["O-CCT"][
            "completion_time_ns_mean_exact"
        ]
    )
    T = Fraction(2 * (RANKS - 1) * 16384, RANKS)
    assert tfc_mean - l0_mean == T / Fraction(32) - T / B == Fraction(448)


# -- the binding's load-time semantics: grantable windows only ----------------


def test_loader_rejects_windows_not_in_credit_units():
    # UEC11-FC-R05: credit is granted in 256-byte units; a window that is
    # not an integral number of units is not grantable and the binding
    # refuses it at load time, naming the requirement.
    with pytest.raises(ValueError, match="UEC11-FC-R05"):
        l0_tfc.load_tfc_config(
            {
                "topology_id": "t",
                "ranks": 8,
                "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
                "tfc": {"window_bytes": 250, "credit_return_latency_ns": 200},
            }
        )


def test_loader_rejects_degenerate_values():
    base = {
        "topology_id": "t",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
    }
    with pytest.raises(ValueError, match="window_bytes must be > 0"):
        l0_tfc.load_tfc_config(
            {**base, "tfc": {"window_bytes": 0, "credit_return_latency_ns": 200}}
        )
    with pytest.raises(ValueError, match="bytes_per_ns must be > 0"):
        l0_tfc.load_tfc_config(
            {
                **base,
                "link": {"bytes_per_ns": 0, "hop_latency_ns": 200},
                "tfc": {"window_bytes": 256, "credit_return_latency_ns": 200},
            }
        )


def test_execute_rejects_non_divisible_payload():
    # Same equal-chunk construction as the L0 family: r | M required.
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=8, layers=1, steps=1, allreduce_bytes=16383)
    )
    with pytest.raises(ValueError, match="A-TFC-DIV"):
        l0_tfc.execute(ops, _infra())


def test_execute_rejects_rank_mismatch_and_foreign_collective():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=4, layers=1, steps=1, allreduce_bytes=16384)
    )
    with pytest.raises(ValueError, match="comm group size"):
        l0_tfc.execute(ops, _infra())


# -- run path: the manifest executes end-to-end through the orchestrator ------


def test_run_path_dispatch_and_determinism(tmp_path):
    from essun.orchestrator import runs as orchestrator

    manifest = "experiments/vertical_slice/w1_decode_tfc.yaml"
    first = orchestrator.run_experiment(manifest, results_root=tmp_path / "a")
    second = orchestrator.run_experiment(manifest, results_root=tmp_path / "b")
    assert first["run_id"] == second["run_id"]  # deterministic, content-addressed
    cct = first["observations"]["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3696))
    assert first["observations"]["requirement_bindings"] == [
        {
            "binding_id": "BIND-UEC11-FC-R02-L0TFC",
            "requirement_id": "UEC11-FC-R02",
            "disposition": "simulated_behavior",
            "credit_unit_requirement_id": "UEC11-FC-R05",
        }
    ]
    # The stored run record carries the manifest declaring the binding's
    # observables; the claim link was appended by the run path.
    claims = (tmp_path / "a" / "claims_index.jsonl").read_text().strip()
    assert "C-UEC-TFC-R02" in claims and first["run_id"] in claims
