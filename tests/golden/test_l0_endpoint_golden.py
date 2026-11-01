"""Golden identities for the L0 endpoint (software) latency term.

Worked by hand, not by calling the implementation under test (the house
golden rule). Constants on every case unless stated:

    r = 8, M = 16384 B, B = 64 B/ns, L = 200 ns, E = 1000 ns
    wire term (all three AllReduce identities) = 2*(7/8)*16384/64 = 448 ns

Extended identities (E charged once per collective op, A-L0E-CHG):

    ring       t = 448 + 14*L + E = 3248 + E = 4248
    crossbar   t = 448 +  2*L + E =  848 + E = 1848
    doubling   t = 448 +  6*L + E = 1648 + E = 2648   (6 = 2*log2(8))

Phase collectives (each phase is ONE issued op, so each carries +E):

    ring RS = 224 + 7*200 + E = 1624 + E = 2624 (AG symmetric)
    dbl  RS = 224 + 3*200 + E =  824 + E = 1824 (AG symmetric)
    RS + AG = AllReduce + E (the fused op carries ONE E; A-L0P-COMP as
    amended by A-L0E-CHG): ring 5248 - 4248 = 1000 = E exactly.

L0.5 at the injection limit converges to the L0 ring identity WITH the same
E; at finite I the exact disagreement stays 2*(r-1)*c/I (E cancels):

    I = 64: c = 2048; s = 2048/64 + 2048/64 + 200 = 264;
    t_L05 = 2*7*264 + E = 3696 + E = 4696; l0 anchor = 4248; diff = 448.

Chain laws at shared E (E cancels — it is identity-invariant structure):

    ring - crossbar = 12L = 2400; doubling - crossbar = 4L = 800;
    ring - doubling = 8L = 1600.
"""

from fractions import Fraction

import pytest

from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar as l0x
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.backends.analytical import l0_recursive_doubling as l0d
from essun.backends.analytical import l05
from essun.workload import w1

RANKS = 8
SIZE = 16384
B = Fraction(64)
L = Fraction(200)
E = Fraction(1000)

# Legacy landed literals (endpoint term absent) — the byte-identity anchor.
RING_L0 = Fraction(3248)  # 448 + 14*200
XBAR_L0 = Fraction(848)  # 448 + 2*200
RD_L0 = Fraction(1648)  # 448 + 6*200


def _ring(endpoint=E):
    return l0.InfraConfig(
        topology_id="ring8_endpoint_golden",
        ranks=RANKS,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
        endpoint_latency_ns=endpoint,
    )


def _xbar(endpoint=E):
    return l0x.CrossbarConfig(
        topology_id="crossbar8_endpoint_golden",
        ranks=RANKS,
        injection_bytes_per_ns=B,
        pair_latency_ns=L,
        endpoint_latency_ns=endpoint,
    )


def _rd(endpoint=E):
    return l0d.RecursiveDoublingConfig(
        topology_id="exchange8_endpoint_golden",
        ranks=RANKS,
        injection_bytes_per_ns=B,
        pair_latency_ns=L,
        steps=3,
        endpoint_latency_ns=endpoint,
    )


def _l05(endpoint=E, injection=None):
    return l05.L05Config(
        topology_id="ring8_l05_endpoint_golden",
        ranks=RANKS,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
        injection_bytes_per_ns=injection,
        endpoint_latency_ns=endpoint,
    )


# ---------------------------------------------------------------------------
# Identity literals with the term declared
# ---------------------------------------------------------------------------


def test_ring_identity_with_endpoint():
    assert l0.ring_allreduce_time_ns(SIZE, RANKS, _ring()) == Fraction(4248)
    assert l0.ring_allreduce_time_ns(SIZE, RANKS, _ring()) == RING_L0 + E


def test_crossbar_identity_with_endpoint():
    assert l0x.crossbar_allreduce_time_ns(SIZE, RANKS, _xbar()) == Fraction(1848)
    # phases stay endpoint-free (A-L0E-CHG: once per op, never per phase)
    assert l0x.crossbar_reduce_scatter_time_ns(SIZE, RANKS, _xbar()) == Fraction(424)
    assert l0x.crossbar_allgather_time_ns(SIZE, RANKS, _xbar()) == Fraction(424)


def test_recursive_doubling_identity_with_endpoint():
    assert l0d.rd_allreduce_time_ns(SIZE, _rd()) == Fraction(2648)
    assert l0d.rd_reduce_phase_time_ns(SIZE, _rd()) == Fraction(824)
    assert l0d.rd_broadcast_phase_time_ns(SIZE, _rd()) == Fraction(824)


def test_chain_laws_survive_the_endpoint_term():
    # E is identity-invariant: the landed chain laws hold at every shared E.
    ring = l0.ring_allreduce_time_ns(SIZE, RANKS, _ring())
    xbar = l0x.crossbar_allreduce_time_ns(SIZE, RANKS, _xbar())
    rd = l0d.rd_allreduce_time_ns(SIZE, _rd())
    assert ring - xbar == Fraction(12 * 200)
    assert rd - xbar == Fraction(4 * 200)
    assert ring - rd == Fraction(8 * 200)


# ---------------------------------------------------------------------------
# Phase collectives: one E per issued phase op; composition = AllReduce + E
# ---------------------------------------------------------------------------


def test_phase_collectives_ring_phases_carry_one_e_each():
    rs = l0p.ring_reducescatter_time_ns(SIZE, RANKS, _ring())
    ag = l0p.ring_allgather_time_ns(SIZE, RANKS, _ring())
    assert rs == Fraction(2624)  # 224 + 1400 + 1000
    assert ag == Fraction(2624)
    assert l0p.ring_allreduce_from_phases_time_ns(SIZE, RANKS, _ring()) == Fraction(
        5248
    )
    # the amended composition identity: phases = fused AllReduce + E
    assert (
        l0p.ring_allreduce_from_phases_time_ns(SIZE, RANKS, _ring())
        == l0.ring_allreduce_time_ns(SIZE, RANKS, _ring()) + E
    )


def test_phase_collectives_doubling_phases_carry_one_e_each():
    rs = l0p.halving_reducescatter_time_ns(SIZE, _rd())
    ag = l0p.doubling_allgather_time_ns(SIZE, _rd())
    assert rs == Fraction(1824)  # 224 + 600 + 1000
    assert ag == Fraction(1824)
    assert l0p.rd_allreduce_from_phases_time_ns(SIZE, _rd()) == Fraction(3648)
    assert (
        l0p.rd_allreduce_from_phases_time_ns(SIZE, _rd())
        == l0d.rd_allreduce_time_ns(SIZE, _rd()) + E
    )


def test_phase_composition_is_exact_when_the_term_is_absent():
    # A-L0P-COMP unamended at E absent: RS + AG == AllReduce exactly.
    assert (
        l0p.ring_allreduce_from_phases_time_ns(SIZE, RANKS, _ring(endpoint=None))
        == l0.ring_allreduce_time_ns(SIZE, RANKS, _ring(endpoint=None))
        == RING_L0
    )
    assert (
        l0p.rd_allreduce_from_phases_time_ns(SIZE, _rd(endpoint=None))
        == l0d.rd_allreduce_time_ns(SIZE, _rd(endpoint=None))
        == RD_L0
    )


# ---------------------------------------------------------------------------
# L0.5 convergence with the endpoint term
# ---------------------------------------------------------------------------


def test_l05_converges_to_l0_with_endpoint_at_injection_limit():
    assert l05.allreduce_time_ns(SIZE, RANKS, _l05()) == l0.ring_allreduce_time_ns(
        SIZE, RANKS, _ring()
    )
    assert l05.allreduce_time_ns(SIZE, RANKS, _l05()) == Fraction(4248)
    assert l05.serialization_term_ns(SIZE, RANKS, _l05()) == Fraction(0)


def test_l05_disagreement_stays_exact_with_endpoint_at_finite_injection():
    config = _l05(injection=Fraction(64))
    assert l05.allreduce_time_ns(SIZE, RANKS, config) == Fraction(4696)
    assert l05.serialization_term_ns(SIZE, RANKS, config) == Fraction(448)
    anchor = l0.ring_allreduce_time_ns(
        SIZE, RANKS, l05._l0_anchor_config(config)
    )
    assert (
        l05.allreduce_time_ns(SIZE, RANKS, config) - anchor
        == l05.serialization_term_ns(SIZE, RANKS, config)
        == Fraction(448)  # 2*(r-1)*c/I = 14*2048/64 — E cancels
    )


# ---------------------------------------------------------------------------
# Byte-identity fence: absent term keeps the landed payloads byte-for-byte
# ---------------------------------------------------------------------------


def _ops():
    return w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=SIZE)
    )


def test_absent_term_keeps_landed_literals_and_payload_shape():
    ring_result = l0.execute(_ops(), _ring(endpoint=None))
    assert "endpoint_latency_ns_exact" not in ring_result["model"]
    assert ring_result["per_op"][0]["completion_time_ns_exact"] == str(RING_L0)
    xbar_result = l0x.execute(_ops(), _xbar(endpoint=None))
    assert "endpoint_latency_ns_exact" not in xbar_result["model"]
    assert "endpoint_term_ns_exact" not in xbar_result["per_op"][0]
    assert xbar_result["per_op"][0]["completion_time_ns_exact"] == str(XBAR_L0)
    rd_result = l0d.execute(_ops(), _rd(endpoint=None))
    assert "endpoint_latency_ns_exact" not in rd_result["model"]
    assert rd_result["per_op"][0]["completion_time_ns_exact"] == str(RD_L0)


def test_declared_zero_term_same_numbers_but_honest_bytes():
    # A declared 0 keeps every landed number and says so in the payload:
    # distinct bytes from the absent-term run — never a silent default.
    ring_result = l0.execute(_ops(), _ring(endpoint=Fraction(0)))
    assert ring_result["model"]["endpoint_latency_ns_exact"] == "0"
    assert ring_result["per_op"][0]["completion_time_ns_exact"] == str(RING_L0)


def test_declared_term_appears_in_payloads():
    ring_result = l0.execute(_ops(), _ring())
    assert ring_result["model"]["endpoint_latency_ns_exact"] == "1000"
    assert ring_result["per_op"][0]["completion_time_ns_exact"] == "4248"
    xbar_result = l0x.execute(_ops(), _xbar())
    assert xbar_result["model"]["endpoint_latency_ns_exact"] == "1000"
    assert xbar_result["per_op"][0]["endpoint_term_ns_exact"] == "1000"
    assert xbar_result["per_op"][0]["completion_time_ns_exact"] == "1848"
    rd_result = l0d.execute(_ops(), _rd())
    assert rd_result["model"]["endpoint_latency_ns_exact"] == "1000"
    assert rd_result["per_op"][0]["endpoint_term_ns_exact"] == "1000"
    assert rd_result["per_op"][0]["completion_time_ns_exact"] == "2648"
    l05_result = l05.execute(_ops(), _l05(injection=Fraction(64)))
    assert l05_result["model"]["endpoint_latency_ns_exact"] == "1000"
    assert l05_result["per_op"][0]["completion_time_ns_exact"] == "4696"


# ---------------------------------------------------------------------------
# Loader contract
# ---------------------------------------------------------------------------


def test_loader_reads_optional_endpoint_exactly():
    base = {
        "topology_id": "crossbar4_endpoint_loader",
        "ranks": 4,
        "nic": {"injection_bytes_per_ns": "12.5"},
        "link": {"pair_latency_ns": "3.5"},
    }
    assert l0x.load_crossbar_config(base).endpoint_latency_ns is None
    declared = l0x.load_crossbar_config(
        {**base, "endpoint": {"latency_ns": "8800"}}
    )
    assert declared.endpoint_latency_ns == Fraction(8800)
    # decimals stay exact Fractions
    fractional = l0x.load_crossbar_config(
        {**base, "endpoint": {"latency_ns": "4500/7"}}
    )
    assert fractional.endpoint_latency_ns == Fraction(4500, 7)
    # a declared 0 is an ACTIVE term with value zero (not "absent")
    zero = l0x.load_crossbar_config({**base, "endpoint": {"latency_ns": 0}})
    assert zero.endpoint_latency_ns == Fraction(0)
    assert zero.endpoint_latency_ns is not None


def test_loader_rejects_negative_and_partial_endpoint_blocks():
    base = {
        "topology_id": "ring4_endpoint_loader",
        "ranks": 4,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
    }
    with pytest.raises(ValueError, match=">= 0"):
        l0.load_infra({**base, "endpoint": {"latency_ns": -1}})
    with pytest.raises(ValueError, match="latency_ns"):
        l0.load_infra({**base, "endpoint": {"other": 1}})
    with pytest.raises(ValueError, match="latency_ns"):
        l0.load_infra({**base, "endpoint": {}})


def test_l05_loader_reads_endpoint():
    base = {
        "topology_id": "ring8_l05_endpoint_loader",
        "topology_class": l05.TOPOLOGY_CLASS,
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
    }
    assert l05.load_l05_config(base).endpoint_latency_ns is None
    config = l05.load_l05_config(
        {**base, "endpoint": {"latency_ns": 600}, "nic": {"injection_bytes_per_ns": 64}}
    )
    assert config.endpoint_latency_ns == Fraction(600)


def test_torus_input_space_does_not_read_the_term():
    # Boundary statement (A-L0E-CHG applicability): the torus loader accepts
    # its own fields only and no torus topology in the tree declares the
    # term; this pins that the l0 ring kernel the torus reuses stays
    # endpoint-free in the torus dimension views (E absent -> exact landed
    # torus behavior, byte-for-byte).
    from essun.backends.analytical import l0_torus2d

    data = {
        "topology_id": "torus8_endpoint_boundary",
        "topology_class": "torus2d_ring_x_ring",
        "ranks": 8,
        "grid": {"dim1_ranks": 2, "dim2_ranks": 4},
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
    }
    config = l0_torus2d.load_torus2d_config(data)
    view = config.dim_ring_view(1)
    assert view.endpoint_latency_ns is None
    assert l0.ring_allreduce_time_ns(SIZE, view.ranks, view) == Fraction(
        2 * (2 - 1) * SIZE, 2
    ) / B + 2 * (2 - 1) * L
