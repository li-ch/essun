"""Golden identities for the L0 crossbar (fully-connected) backend, P2 stage S1.

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the handoff
rule that golden tests derive from the specified identities.

Identity under test (single-port crossbar, reduce-scatter + allgather):

    t_rs = t_ag = (r-1)/r * M / B + L
    t    = 2*(r-1)/r * M / B + 2L
    T    = 2*(r-1)/r * M   (per-rank wire bytes)

Worked cases (derived by hand below, asserted as exact Fractions):

A) r=8, M=16384,  B=64, L=200:
   M/r=2048; 7*2048=14336; 14336/64=224; t_rs=224+200=424; t=848;
   T=2*14336=28672; total wire=8*28672=229376.
B) r=8, M=1048576, B=64, L=200:
   M/r=131072; 7*131072=917504; 917504/64=14336; t_rs=14536; t=29072;
   T=1835008; total wire=14680064.
C) r=4, M=1000, B=10, L=1 (non-integer per-phase traffic):
   (3/4)*1000=750; 750/10=75; t_rs=76; t=152; T=1500; total wire=6000.
D) r=4, M=1000, B=12.5=25/2, L=1 (decimal free parameter stays exact):
   750/(25/2)=60; t_rs=61; t=122.
"""

from fractions import Fraction

from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar as l0x
from essun.workload import w1

SIZES = [16384, 1048576]
RANKS = 8


def _infra():
    return l0x.CrossbarConfig(
        topology_id="crossbar8_free_v1",
        ranks=RANKS,
        injection_bytes_per_ns=Fraction(64),
        pair_latency_ns=Fraction(200),
    )


def test_traffic_identity_16kib_and_1mib():
    # T(M, r) = 2*(r-1)/r * M: for r=8 that is 7/4 * M.
    for size in SIZES:
        expected = Fraction(2 * (RANKS - 1) * size, RANKS)
        assert l0x.crossbar_traffic_per_rank(size, RANKS) == expected
    assert l0x.crossbar_traffic_per_rank(16384, RANKS) == Fraction(28672)
    assert l0x.crossbar_traffic_per_rank(1048576, RANKS) == Fraction(1835008)


def test_traffic_identity_matches_ring_closed_form():
    # Both backends share the per-rank conservation identity 2*(r-1)/r*M.
    shared = Fraction(28672)  # hand-derived for r=8, M=16384
    assert l0.ring_traffic_per_rank(16384, RANKS) == shared
    assert l0x.crossbar_traffic_per_rank(16384, RANKS) == shared


def test_phase_and_completion_time_identity_16kib():
    # t_rs = t_ag = 14336/64 + 200 = 224 + 200 = 424; t = 848 ns.
    assert (
        l0x.crossbar_reduce_scatter_time_ns(16384, RANKS, _infra()) == Fraction(424)
    )
    assert l0x.crossbar_allgather_time_ns(16384, RANKS, _infra()) == Fraction(424)
    assert l0x.crossbar_allreduce_time_ns(16384, RANKS, _infra()) == Fraction(848)


def test_completion_time_identity_1mib():
    # t = 2 * 917504/64 + 2*200 = 2*14336 + 400 = 29072 ns.
    assert l0x.crossbar_allreduce_time_ns(1048576, RANKS, _infra()) == Fraction(29072)


def test_completion_time_noninteger_chunk_case():
    # r=4, M=1000, B=10, L=1: t_rs = 750/10 + 1 = 76; t = 152. Exact Fractions.
    infra = l0x.CrossbarConfig(
        topology_id="crossbar4_frac_v1",
        ranks=4,
        injection_bytes_per_ns=Fraction(10),
        pair_latency_ns=Fraction(1),
    )
    assert l0x.crossbar_traffic_per_rank(1000, 4) == Fraction(1500)
    assert l0x.crossbar_reduce_scatter_time_ns(1000, 4, infra) == Fraction(76)
    assert l0x.crossbar_allreduce_time_ns(1000, 4, infra) == Fraction(152)


def test_composition_identity_phase_sum():
    # t == t_rs + t_ag as an identity, checked on the spelled values (424+424).
    infra = _infra()
    rs = l0x.crossbar_reduce_scatter_time_ns(16384, RANKS, infra)
    ag = l0x.crossbar_allgather_time_ns(16384, RANKS, infra)
    total = l0x.crossbar_allreduce_time_ns(16384, RANKS, infra)
    assert rs + ag == total == Fraction(848)


def test_loader_extracts_exact_fractions_and_rejects_degenerate():
    data = {
        "topology_id": "crossbar4_frac_v1",
        "ranks": 4,
        "nic": {"injection_bytes_per_ns": "12.5"},  # 25/2 exactly
        "link": {"pair_latency_ns": "3.5"},  # 7/2 exactly
    }
    infra = l0x.load_crossbar_config(data)
    assert infra.injection_bytes_per_ns == Fraction(25, 2)
    assert infra.pair_latency_ns == Fraction(7, 2)
    # D: r=4, M=1000, B=25/2, L=1 -> t_rs = 750/(25/2) + 1 = 61; t = 122.
    infra_l1 = l0x.CrossbarConfig(
        topology_id="crossbar4_frac_v1",
        ranks=4,
        injection_bytes_per_ns=Fraction(25, 2),
        pair_latency_ns=Fraction(1),
    )
    assert l0x.crossbar_allreduce_time_ns(1000, 4, infra_l1) == Fraction(122)

    try:
        l0x.load_crossbar_config({**data, "ranks": 1})
    except ValueError as exc:
        assert "ranks >= 2" in str(exc)
    else:
        raise AssertionError("expected ValueError for ranks < 2")


def test_loader_reads_committed_topology_yaml():
    from pathlib import Path

    import yaml

    path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "topologies"
        / "crossbar8_free_params.yaml"
    )
    infra = l0x.load_crossbar_config(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert infra.topology_id == "crossbar8_free_v1"
    assert infra.ranks == RANKS
    assert infra.injection_bytes_per_ns == Fraction(64)
    assert infra.pair_latency_ns == Fraction(200)


def test_conservation_observable_exact_and_clean():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    result = l0x.execute(ops, _infra())
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 1
    assert conservation["violations"] == 0
    # Total wire bytes = 2*(r-1)*M = 229376.
    assert conservation["total_wire_bytes_exact"] == str(Fraction(229376))
    per_op = result["per_op"][0]
    assert per_op["per_rank_wire_bytes_exact"] == str(Fraction(28672))
    assert per_op["reduce_scatter_time_ns_exact"] == str(Fraction(424))
    assert per_op["allgather_time_ns_exact"] == str(Fraction(424))
    assert per_op["completion_time_ns_exact"] == str(Fraction(848))
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(848))
    assert cct["completion_time_ns_max"] == 848.0


def test_execute_rejects_size_mismatch():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=4, layers=1, steps=1, allreduce_bytes=16384)
    )
    try:
        l0x.execute(ops, _infra())
    except ValueError as exc:
        assert "comm group size" in str(exc)
    else:
        raise AssertionError("expected ValueError for rank mismatch")


def test_execute_rejects_unsupported_collective():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    op = ops[0]
    bogus = w1.CollectiveOp(
        op_id=op.op_id,
        collective="allgather",  # first-class only from stage S4
        comm_ranks=op.comm_ranks,
        payload_bytes=op.payload_bytes,
        step=op.step,
        layer=op.layer,
    )
    try:
        l0x.execute([bogus], _infra())
    except ValueError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported collective")
