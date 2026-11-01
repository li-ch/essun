"""Golden identities for the L0 2D-torus wrap-edge wiring factor
(A-L0T-WIRE, experiments/vertical_slice/assumptions_l0tw.yaml; stage
TWIST — the calibration twist-axis model change).

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the
handoff rule that golden tests derive from the specified identities.

Identity under test (the landed identity plus the wiring term):

    rate(w) = B * min(1, w)
    t_ring(M, k; w) = 2*(k-1)/k * M / (B * min(1, w)) + 2*(k-1)*L
    t_2d(M, r1, r2; w) = t_ring(M, r1; w) + t_ring(M, r2; w)
    T_2d(M, r1, r2) unchanged by w (wiring moves rates, never bytes)

ONE-SIDED LAW (asserted on every executed case): w >= 1 is EXACTLY inert
(t == t(w=1) identically — the k-1 non-wrap edges bound the ring rate);
w < 1 is active and coincides exactly with a per-link-B displacement
(t(M; w) == t(M; B*w) for w < 1).

Worked cases, extending the landed torus goldens' case A/B base
(r1=2, r2=4, r=8, M=16384, B=64, L=200 -> t=2240 with bandwidth terms
256 + 384 and latency 1600):

W) w=1/2 (declared): rate 32; dim1 t=16384/32+400=512+400=912;
   dim2 t=24576/32+1200=768+1200=1968; t_2d=2880; traffic still 40960.
X) w=1/4 (declared, deliberately OUTSIDE the registered range [1/2, 2] —
   the loader executes it so the miss is visible, same rule as B/L):
   rate 16; dim1 t=1024+400=1424; dim2 t=1536+1200=2736; t_2d=4160
   == the landed identity at B=16 exactly (the B-displacement side).
Y) w=3/2 and w=2 (declared): t_2d=2240 EXACTLY (inert); at M=1048576
   (landed case B, t=42560): every w >= 1 gives 42560 EXACTLY.
Z) w=1 (declared): t_2d=2240 (same as undeclared) — a declared value
   ACTIVATES the payload record, never the time term above 1.
"""

from fractions import Fraction

from essun.backends.analytical.l0_torus2d import (
    Torus2DConfig,
    execute,
    load_torus2d_config,
    torus2d_allreduce_time_ns,
    torus2d_traffic_per_rank,
)
from essun.workload import w1

RANKS = 8
DIM1, DIM2 = 2, 4


def _infra(w=None):
    return Torus2DConfig(
        topology_id="torus2d8_free_v1",
        ranks=RANKS,
        dim1_ranks=DIM1,
        dim2_ranks=DIM2,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
        wrap_wiring_factor=w,
    )


def test_wiring_below_one_binds_the_bandwidth_term():
    # W: rate 32 -> dim1 912, dim2 1968, total 2880.
    infra = _infra(Fraction(1, 2))
    assert torus2d_allreduce_time_ns(16384, infra) == Fraction(2880)
    # Traffic is UNCHANGED by wiring (rates, never bytes).
    assert torus2d_traffic_per_rank(16384, infra) == Fraction(40960)


def test_wiring_out_of_range_low_still_executes_and_equals_b_displacement():
    # X: w=1/4 (outside the registered range [1/2, 2]) executes at rate 16;
    # the active side coincides EXACTLY with the landed identity at B=16.
    infra = _infra(Fraction(1, 4))
    assert torus2d_allreduce_time_ns(16384, infra) == Fraction(4160)
    b16 = Torus2DConfig(
        topology_id="torus2d8_free_v1",
        ranks=RANKS,
        dim1_ranks=DIM1,
        dim2_ranks=DIM2,
        link_bytes_per_ns=Fraction(16),
        hop_latency_ns=Fraction(200),
    )
    assert torus2d_allreduce_time_ns(16384, infra) == torus2d_allreduce_time_ns(
        16384, b16
    )
    for size in (16384, 1048576, 4096):
        for w in (Fraction(1, 2), Fraction(3, 4), Fraction(1, 8)):
            at_w = torus2d_allreduce_time_ns(size, _infra(w))
            at_b = torus2d_allreduce_time_ns(
                size,
                Torus2DConfig(
                    topology_id="torus2d8_free_v1",
                    ranks=RANKS,
                    dim1_ranks=DIM1,
                    dim2_ranks=DIM2,
                    link_bytes_per_ns=Fraction(64) * w,
                    hop_latency_ns=Fraction(200),
                ),
            )
            assert at_w == at_b  # the B-displacement side, exactly


def test_one_sided_law_w_above_one_is_exactly_inert():
    # Y: every w >= 1 gives the landed identity's time EXACTLY, at both
    # the latency-dominated (16 KiB, 2240) and bandwidth-dominated
    # (1 MiB, 42560) sizes.
    for size, landed in ((16384, Fraction(2240)), (1048576, Fraction(42560))):
        assert torus2d_allreduce_time_ns(size, _infra(None)) == landed
        for w in (
            Fraction(1),
            Fraction(5, 4),
            Fraction(3, 2),
            Fraction(7, 4),
            Fraction(2),
            Fraction(100),  # unbounded-gain direction stays inert
        ):
            assert torus2d_allreduce_time_ns(size, _infra(w)) == landed, (w, size)


def test_declared_one_matches_undeclared_time_but_records_the_field():
    # Z: a declared value (even 1) activates the payload record, not a
    # time change above 1.
    assert torus2d_allreduce_time_ns(16384, _infra(Fraction(1))) == Fraction(2240)
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    undeclared = execute(ops, _infra(None))
    declared = execute(ops, _infra(Fraction(1)))
    # Legacy payload bytes: an UNDECLARED factor emits exactly the landed
    # model block (byte-identity of every existing torus run).
    assert undeclared["model"] == {
        "transport_model": "bandwidth_latency_torus2d_sequential_dims",
        "topology_id": "torus2d8_free_v1",
        "ranks": 8,
        "dim1_ranks": 2,
        "dim2_ranks": 4,
        "link_bytes_per_ns_exact": "64",
        "hop_latency_ns_exact": "200",
    }
    # A declared factor is recorded with its min-link rate limit.
    assert declared["model"]["wrap_wiring_factor_exact"] == "1"
    assert declared["model"]["wrap_rate_limit_exact"] == "1"
    half = execute(ops, _infra(Fraction(1, 2)))
    assert half["model"]["wrap_wiring_factor_exact"] == "1/2"
    assert half["model"]["wrap_rate_limit_exact"] == "1/2"
    assert half["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == str(
        Fraction(2880)
    )
    # The undeclared and declared-1 payloads differ ONLY by the record.
    assert {
        k: v for k, v in declared["model"].items()
        if k not in ("wrap_wiring_factor_exact", "wrap_rate_limit_exact")
    } == undeclared["model"]


def test_conservation_is_wiring_invariant():
    # Wiring never moves bytes: O-CONSERVATION totals are identical at
    # w=1/2, w=1 and w=2 (2*M*(2r-r1-r2) = 327680 exactly).
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    totals = {
        execute(ops, _infra(w))["observables"]["O-CONSERVATION"][
            "total_wire_bytes_exact"
        ]
        for w in (Fraction(1, 2), None, Fraction(1), Fraction(2))
    }
    assert totals == {str(Fraction(327680))}


def _data(**link):
    link_block = {"bytes_per_ns": 64, "hop_latency_ns": 200, **link}
    return {
        "topology_id": "torus2d8_free_v1",
        "ranks": 8,
        "grid": {"dim1_ranks": 2, "dim2_ranks": 4},
        "link": link_block,
    }


def test_loader_reads_wiring_exactly_and_defaults_to_undeclared():
    assert load_torus2d_config(_data()).wrap_wiring_factor is None
    assert load_torus2d_config(_data(wrap_wiring_factor="1.5")).wrap_wiring_factor == Fraction(3, 2)
    assert load_torus2d_config(_data(wrap_wiring_factor="0.5")).wrap_wiring_factor == Fraction(1, 2)
    # A declared 1 is a DECLARED value (recorded), not the default None.
    assert load_torus2d_config(_data(wrap_wiring_factor="1")).wrap_wiring_factor == Fraction(1)
    # Decimal YAML values are interpreted exactly, not via float.
    assert load_torus2d_config(_data(wrap_wiring_factor="1.75")).wrap_wiring_factor == Fraction(7, 4)


def test_loader_rejects_non_positive_wiring():
    for bad in ("0", "-0.5", "-2"):
        try:
            load_torus2d_config(_data(wrap_wiring_factor=bad))
        except ValueError as exc:
            assert "> 0" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for wiring {bad}")
