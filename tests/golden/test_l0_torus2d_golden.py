"""Golden identities for the L0 2D-torus (ring x ring) backend, P2 stage S2.

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the handoff
rule that golden tests derive from the specified identities.

Identity under test (sum over dimensions, each dimension the standard
two-phase reduce-scatter + allgather ring model):

    t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L
    t_2d(M,r1,r2) = t_ring(M, r1) + t_ring(M, r2)
    T_2d(M,r1,r2) = 2*(r1-1)/r1*M + 2*(r2-1)/r2*M = 2*(2 - 1/r1 - 1/r2)*M

Worked cases (derived by hand below, asserted as exact Fractions):

A) r1=2, r2=4 (r=8), M=16384, B=64, L=200:
   dim1 (k=2): T=M=16384; t=16384/64+2*200=256+400=656.
   dim2 (k=4): T=(3/2)M=24576; t=24576/64+6*200=384+1200=1584.
   t_2d=656+1584=2240; T=40960; total wire=8*40960=327680
   (= 2*M*(2r-r1-r2) = 2*16384*10 exactly).
B) r1=2, r2=4, M=1048576, B=64, L=200:
   dim1: t=1048576/64+400=16384+400=16784.
   dim2: t=1572864/64+1200=24576+1200=25776.
   t_2d=42560; T=2621440; total wire=20971520.
C) 2x2 (r=4), M=16384, B=64, L=200: each dim t=656; t_2d=1312;
   T=2*M=32768; total wire=4*32768=131072.
D) 3x3 (r=9), M=1000, B=10, L=1 (non-integer per-dimension traffic):
   each dim: T=(4/3)*1000=4000/3; t=400/3+4=412/3; t_2d=824/3; T=8000/3.
E) r1=2, r2=4, M=1000, B=12.5=25/2, L=0.5 (decimal free parameters):
   dim1 t=1000/(25/2)+1=80+1=81; dim2 t=1500/(25/2)+3=120+3=123; t_2d=204.
F) Design-space cross-check vs the flat ring (r=8, same B, L; hand-derived):
   M=16384: ring=448+2800=3248 > torus 2240 (latency-dominated);
   M=1048576: ring=28672+2800=31472 < torus 42560 (bandwidth-dominated).
"""

from fractions import Fraction

from essun.backends.analytical import l0
from essun.backends.analytical import l0_torus2d as l0t
from essun.workload import w1

SIZES = [16384, 1048576]
RANKS = 8
DIM1, DIM2 = 2, 4


def _infra(dim1=DIM1, dim2=DIM2, bw=64, lat=200, ranks=RANKS):
    return l0t.Torus2DConfig(
        topology_id="torus2d8_free_v1",
        ranks=ranks,
        dim1_ranks=dim1,
        dim2_ranks=dim2,
        link_bytes_per_ns=Fraction(bw),
        hop_latency_ns=Fraction(lat),
    )


def test_traffic_identity_per_dimension_and_sum():
    # T_2d = 2*(2 - 1/r1 - 1/r2)*M; for 2x4 that is (5/2)*M.
    for size in SIZES:
        expected = Fraction(2 * (DIM1 - 1) * size, DIM1) + Fraction(
            2 * (DIM2 - 1) * size, DIM2
        )
        assert l0t.torus2d_traffic_per_rank(size, _infra()) == expected
    assert l0t.torus2d_traffic_per_rank(16384, _infra()) == Fraction(40960)
    assert l0t.torus2d_traffic_per_rank(1048576, _infra()) == Fraction(2621440)
    # Closed form: 2*(2 - 1/2 - 1/4)*16384 = 2*(5/4)*16384 = 40960.
    assert l0t.torus2d_traffic_per_rank(16384, _infra()) == Fraction(5, 2) * 16384


def test_per_dimension_traffic_matches_ring_identity():
    # A 2D torus is two landed rings: dim traffic = ring traffic at k=2, k=4.
    assert l0.ring_traffic_per_rank(16384, 2) == Fraction(16384)
    assert l0.ring_traffic_per_rank(16384, 4) == Fraction(24576)
    assert l0t.torus2d_dim_traffic_per_rank(16384, 1, _infra()) == Fraction(16384)
    assert l0t.torus2d_dim_traffic_per_rank(16384, 2, _infra()) == Fraction(24576)


def test_time_identity_16kib():
    # A: dim1 t=256+400=656; dim2 t=384+1200=1584; total 2240 ns.
    infra = _infra()
    assert l0t.torus2d_dim_time_ns(16384, 1, infra) == Fraction(656)
    assert l0t.torus2d_dim_time_ns(16384, 2, infra) == Fraction(1584)
    assert l0t.torus2d_allreduce_time_ns(16384, infra) == Fraction(2240)


def test_time_identity_1mib():
    # B: dim1 t=16384+400=16784; dim2 t=24576+1200=25776; total 42560 ns.
    infra = _infra()
    assert l0t.torus2d_dim_time_ns(1048576, 1, infra) == Fraction(16784)
    assert l0t.torus2d_dim_time_ns(1048576, 2, infra) == Fraction(25776)
    assert l0t.torus2d_allreduce_time_ns(1048576, infra) == Fraction(42560)


def test_time_noninteger_square_case():
    # D: 3x3, M=1000, B=10, L=1 -> each dim t=400/3+4=412/3; total 824/3.
    infra = _infra(dim1=3, dim2=3, bw=10, lat=1, ranks=9)
    assert l0t.torus2d_dim_time_ns(1000, 1, infra) == Fraction(412, 3)
    assert l0t.torus2d_dim_time_ns(1000, 2, infra) == Fraction(412, 3)
    assert l0t.torus2d_allreduce_time_ns(1000, infra) == Fraction(824, 3)
    assert l0t.torus2d_traffic_per_rank(1000, infra) == Fraction(8000, 3)


def test_time_decimal_parameters_stay_exact():
    # E: B=25/2, L=1/2 -> dim1 81, dim2 123, total 204, exactly.
    infra = _infra(dim1=2, dim2=4, bw=Fraction(25, 2), lat=Fraction(1, 2), ranks=8)
    assert l0t.torus2d_dim_time_ns(1000, 1, infra) == Fraction(81)
    assert l0t.torus2d_dim_time_ns(1000, 2, infra) == Fraction(123)
    assert l0t.torus2d_allreduce_time_ns(1000, infra) == Fraction(204)


def test_shape_symmetry():
    # The identity is symmetric: 2x4 == 4x2 (both 5M/128 + 8L = 2240).
    assert l0t.torus2d_allreduce_time_ns(16384, _infra(2, 4)) == Fraction(2240)
    assert l0t.torus2d_allreduce_time_ns(16384, _infra(4, 2)) == Fraction(2240)


def test_design_space_crosscheck_vs_flat_ring():
    # F: same free parameters on the landed flat ring (hand-derived: ring
    # t = (7/4)M/64 + 2800): latency-dominated 16 KiB -> torus wins;
    # bandwidth-dominated 1 MiB -> flat ring wins (torus moves 2.5M vs 1.75M).
    ring8 = l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )
    ring_small = l0.ring_allreduce_time_ns(16384, RANKS, ring8)
    ring_large = l0.ring_allreduce_time_ns(1048576, RANKS, ring8)
    assert ring_small == Fraction(3248)  # 448 + 2800
    assert ring_large == Fraction(31472)  # 28672 + 2800
    assert l0t.torus2d_allreduce_time_ns(16384, _infra()) == Fraction(2240) < ring_small
    assert (
        l0t.torus2d_allreduce_time_ns(1048576, _infra()) == Fraction(42560)
        > ring_large
    )


def test_loader_extracts_exact_fractions_and_rejects_bad_grids():
    data = {
        "topology_id": "torus2d8_free_v1",
        "ranks": 8,
        "grid": {"dim1_ranks": 2, "dim2_ranks": 4},
        "link": {"bytes_per_ns": "12.5", "hop_latency_ns": "3.5"},  # 25/2, 7/2
    }
    infra = l0t.load_torus2d_config(data)
    assert infra.link_bytes_per_ns == Fraction(25, 2)
    assert infra.hop_latency_ns == Fraction(7, 2)
    assert infra.dim1_ranks == 2 and infra.dim2_ranks == 4

    try:
        l0t.load_torus2d_config(
            {**data, "grid": {"dim1_ranks": 1, "dim2_ranks": 8}}
        )
    except ValueError as exc:
        assert ">= 2" in str(exc)
    else:
        raise AssertionError("expected ValueError for a dimension of size 1")

    try:
        l0t.load_torus2d_config(
            {**data, "grid": {"dim1_ranks": 3, "dim2_ranks": 3}}
        )
    except ValueError as exc:
        assert "does not tile" in str(exc)
    else:
        raise AssertionError("expected ValueError for grid != ranks")


def test_loader_reads_committed_topology_yaml():
    from pathlib import Path

    import yaml

    path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "topologies"
        / "torus2d_8_free_params.yaml"
    )
    infra = l0t.load_torus2d_config(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert infra.topology_id == "torus2d8_free_v1"
    assert infra.ranks == RANKS
    assert (infra.dim1_ranks, infra.dim2_ranks) == (2, 4)
    assert infra.link_bytes_per_ns == Fraction(64)
    assert infra.hop_latency_ns == Fraction(200)


def test_execute_observables_exact_and_clean():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    result = l0t.execute(ops, _infra())
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 1
    assert conservation["violations"] == 0
    # Total wire = 8 * 40960 = 327680 = 2*M*(2r-r1-r2) exactly.
    assert conservation["total_wire_bytes_exact"] == str(Fraction(327680))
    per_op = result["per_op"][0]
    assert per_op["dim1_per_rank_wire_bytes_exact"] == str(Fraction(16384))
    assert per_op["dim2_per_rank_wire_bytes_exact"] == str(Fraction(24576))
    assert per_op["per_rank_wire_bytes_exact"] == str(Fraction(40960))
    # Per-dimension wire: dim1 4 rings * 2*1*M = 131072; dim2 2 rings * 2*3*M.
    assert per_op["dim1_wire_bytes_exact"] == str(Fraction(131072))
    assert per_op["dim2_wire_bytes_exact"] == str(Fraction(196608))
    assert per_op["dim1_time_ns_exact"] == str(Fraction(656))
    assert per_op["dim2_time_ns_exact"] == str(Fraction(1584))
    assert per_op["completion_time_ns_exact"] == str(Fraction(2240))
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(2240))
    assert cct["completion_time_ns_max"] == 2240.0
    model = result["model"]
    assert model["dim1_ranks"] == 2 and model["dim2_ranks"] == 4


def test_execute_rejects_size_mismatch():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=4, layers=1, steps=1, allreduce_bytes=16384)
    )
    try:
        l0t.execute(ops, _infra())
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
        l0t.execute([bogus], _infra())
    except ValueError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported collective")
