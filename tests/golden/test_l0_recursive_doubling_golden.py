"""Golden identities for the L0 recursive-doubling backend, P2 stage S3.

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the handoff
rule that golden tests derive from the specified identities.

Identity under test (standard two-phase recursive halving + recursive
doubling; k = log2(r), one partner per step, per-step cost chunk_i/B + L):

    reduce (halving):   chunk_i = M/2^i,          i = 1..k
    broadcast (double): chunk_i = 2^(i-1)*M/r,    i = 1..k
    t_phase = sum_i chunk_i/B + k*L = (r-1)/r * M/B + k*L
    t(M, r) = 2*(r-1)/r * M/B + 2*log2(r)*L
    T(M, r) = 2*(r-1)/r * M ;  total wire = 2*(r-1)*M

Worked cases (derived by hand below, asserted as exact Fractions):

A) r=8 (k=3), M=16384, B=64, L=200:
   reduce steps: 8192/64+200=328; 4096/64+200=264; 2048/64+200=232 -> 824
   (= (7/8)*16384/64 + 3*200 = 224+600). broadcast steps mirror: 232,264,328
   -> 824. t=1648. T=2*(7/8)*16384=28672; total wire=8*28672=229376.
B) r=8, M=1048576: (7/8)*1048576/64=14336; +600 -> phase 14936; t=29872.
   T=1835008; total wire=14680064.
C) r=2 (k=1), M=16384: phase = 8192/64+200=328; t=656=M/B+2L — ring(2),
   crossbar(2) and recursive-doubling(2) coincide at r=2.
D) r=4 (k=2), M=1000, B=10, L=1: reduce 500/10+1=51, 250/10+1=26 -> 77
   (= 750/10+2); broadcast 26+51 -> 77; t=154; T=1500; total wire=6000.
E) r=8, M=1000, B=12.5=25/2, L=0.5=1/2 (decimal free parameters):
   phase = 875/(25/2) + 3/2 = 70+3/2 = 143/2; t=143, exactly.
F) Design-space cross-checks under shared free parameters (hand-derived):
   ring(16 KiB)=448+2800=3248, ring(1 MiB)=28672+2800=31472;
   crossbar(16 KiB)=848, crossbar(1 MiB)=29072.
   rd beats the flat ring by 2*(r-1-log2 r)*L (1600 ns at r=8) at both sizes;
   the pipelined crossbar beats rd by 2*(log2 r -1)*L = 800 ns at both sizes;
   same per-rank wire 2*(r-1)/r*M for all three.
"""

from fractions import Fraction

from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar as l0x
from essun.backends.analytical import l0_recursive_doubling as l0d
from essun.workload import w1

RANKS = 8
STEPS = 3  # log2(8)


def _infra(ranks=RANKS, bw=64, lat=200):
    return l0d.RecursiveDoublingConfig(
        topology_id="rdoubling8_free_v1",
        ranks=ranks,
        injection_bytes_per_ns=Fraction(bw),
        pair_latency_ns=Fraction(lat),
        steps=l0d._log2_steps(ranks),
    )


def test_step_chunks_halve_then_double():
    # Reduce: M/2, M/4, M/8 for r=8, M=16384 -> 8192, 4096, 2048.
    assert l0d.reduce_step_chunk(16384, 1, 8) == Fraction(8192)
    assert l0d.reduce_step_chunk(16384, 2, 8) == Fraction(4096)
    assert l0d.reduce_step_chunk(16384, 3, 8) == Fraction(2048)
    # Broadcast: M/8, M/4, M/2 -> 2048, 4096, 8192 (doubling).
    assert l0d.broadcast_step_chunk(16384, 1, 8) == Fraction(2048)
    assert l0d.broadcast_step_chunk(16384, 2, 8) == Fraction(4096)
    assert l0d.broadcast_step_chunk(16384, 3, 8) == Fraction(8192)
    # Halving+double step chunks telescope: sum = (r-1)/r*M per phase.
    assert sum(
        l0d.reduce_step_chunk(16384, i, 8) for i in (1, 2, 3)
    ) == Fraction(7 * 16384, 8)
    assert sum(
        l0d.broadcast_step_chunk(16384, i, 8) for i in (1, 2, 3)
    ) == Fraction(7 * 16384, 8)


def test_phase_times_16kib_step_by_step():
    # A: reduce steps 328, 264, 232 -> 824; broadcast steps 232, 264, 328 -> 824.
    infra = _infra()
    reduce_times = [
        l0d.reduce_step_chunk(16384, i, 8) / infra.injection_bytes_per_ns
        + infra.pair_latency_ns
        for i in (1, 2, 3)
    ]
    assert reduce_times == [Fraction(328), Fraction(264), Fraction(232)]
    assert l0d.rd_reduce_phase_time_ns(16384, infra) == Fraction(824)
    assert l0d.rd_broadcast_phase_time_ns(16384, infra) == Fraction(824)


def test_time_identity_16kib():
    # A: t = 824 + 824 = 1648 ns; per-rank wire 28672.
    infra = _infra()
    assert l0d.rd_allreduce_time_ns(16384, infra) == Fraction(1648)
    assert l0d.rd_traffic_per_rank(16384, 8) == Fraction(28672)


def test_time_identity_1mib():
    # B: phase = 14336 + 600 = 14936; t = 29872; wire 1835008, total 14680064.
    infra = _infra()
    assert l0d.rd_reduce_phase_time_ns(1048576, infra) == Fraction(14936)
    assert l0d.rd_broadcast_phase_time_ns(1048576, infra) == Fraction(14936)
    assert l0d.rd_allreduce_time_ns(1048576, infra) == Fraction(29872)
    assert l0d.rd_traffic_per_rank(1048576, 8) == Fraction(1835008)
    assert l0d.rd_traffic_per_rank(1048576, 8) * 8 == Fraction(14680064)


def test_time_noninteger_case_r4():
    # D: r=4, M=1000, B=10, L=1 -> phases 77 each, t=154, T=1500, wire=6000.
    infra = _infra(ranks=4, bw=10, lat=1)
    assert l0d.rd_reduce_phase_time_ns(1000, infra) == Fraction(77)
    assert l0d.rd_broadcast_phase_time_ns(1000, infra) == Fraction(77)
    assert l0d.rd_allreduce_time_ns(1000, infra) == Fraction(154)
    assert l0d.rd_traffic_per_rank(1000, 4) == Fraction(1500)
    assert l0d.rd_traffic_per_rank(1000, 4) * 4 == Fraction(6000)


def test_time_decimal_parameters_stay_exact():
    # E: B=25/2, L=1/2, r=8 -> phase 143/2, total 143, exactly.
    infra = _infra(ranks=8, bw=Fraction(25, 2), lat=Fraction(1, 2))
    assert l0d.rd_reduce_phase_time_ns(1000, infra) == Fraction(143, 2)
    assert l0d.rd_broadcast_phase_time_ns(1000, infra) == Fraction(143, 2)
    assert l0d.rd_allreduce_time_ns(1000, infra) == Fraction(143)


def test_step_sum_matches_closed_form_literal():
    # Closed form 2*(r-1)/r*M/B + 2k*L spelled out literally (r=8, M=16384):
    # 2*(7/8)*16384/64 + 6*200 = 448 + 1200 = 1648.
    closed_form = (
        2 * Fraction(7 * 16384, 8) / Fraction(64) + 6 * Fraction(200)
    )
    assert closed_form == Fraction(1648)
    assert l0d.rd_allreduce_time_ns(16384, _infra()) == closed_form


def test_all_backends_coincide_at_two_ranks():
    # C: at r=2 every identity degenerates to M/B + 2L = 256+400 = 656.
    rd2 = _infra(ranks=2)
    assert l0d.rd_allreduce_time_ns(16384, rd2) == Fraction(656)
    ring2 = l0.InfraConfig(
        topology_id="ring2",
        ranks=2,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )
    assert l0.ring_allreduce_time_ns(16384, 2, ring2) == Fraction(656)
    cb2 = l0x.CrossbarConfig(
        topology_id="cb2",
        ranks=2,
        injection_bytes_per_ns=Fraction(64),
        pair_latency_ns=Fraction(200),
    )
    assert l0x.crossbar_allreduce_time_ns(16384, 2, cb2) == Fraction(656)


def test_design_space_crosscheck_vs_ring_and_crossbar():
    # F: shared B=64, L=200, r=8; ring and crossbar values hand-derived.
    ring8 = l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )
    cb8 = l0x.CrossbarConfig(
        topology_id="crossbar8_free_v1",
        ranks=RANKS,
        injection_bytes_per_ns=Fraction(64),
        pair_latency_ns=Fraction(200),
    )
    rd = _infra()
    # Same per-rank wire bytes for all three designs.
    assert l0d.rd_traffic_per_rank(16384, 8) == l0.ring_traffic_per_rank(16384, 8)
    assert l0d.rd_traffic_per_rank(16384, 8) == l0x.crossbar_traffic_per_rank(
        16384, 8
    )
    # Ring: rd shorter by 2*(r-1-log2 r)*L = 1600 ns at both sizes.
    assert l0.ring_allreduce_time_ns(16384, 8, ring8) == Fraction(3248)
    assert l0.ring_allreduce_time_ns(1048576, 8, ring8) == Fraction(31472)
    assert l0d.rd_allreduce_time_ns(16384, rd) == Fraction(1648) == Fraction(
        3248
    ) - Fraction(1600)
    assert l0d.rd_allreduce_time_ns(1048576, rd) == Fraction(29872) == (
        Fraction(31472) - Fraction(1600)
    )
    # Crossbar: pipelined chunks charge 2L per phase; rd pays 2*(log2 r)*L,
    # so the crossbar is faster by 2*(log2 r - 1)*L = 800 ns at both sizes.
    assert l0x.crossbar_allreduce_time_ns(16384, 8, cb8) == Fraction(848)
    assert l0x.crossbar_allreduce_time_ns(1048576, 8, cb8) == Fraction(29072)
    assert l0d.rd_allreduce_time_ns(16384, rd) - Fraction(848) == Fraction(800)
    assert l0d.rd_allreduce_time_ns(1048576, rd) - Fraction(29072) == Fraction(800)


def test_loader_rejects_non_powers_and_degenerates():
    data = {
        "topology_id": "rd8_free_v1",
        "ranks": 8,
        "nic": {"injection_bytes_per_ns": 64},
        "link": {"pair_latency_ns": 200},
    }
    assert l0d.load_recursive_doubling_config(data).steps == STEPS
    assert l0d.load_recursive_doubling_config({**data, "ranks": 2}).steps == 1
    for bad in (6, 12):
        try:
            l0d.load_recursive_doubling_config({**data, "ranks": bad})
        except ValueError as exc:
            assert "power-of-two" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for ranks={bad}")
    try:
        l0d.load_recursive_doubling_config({**data, "ranks": 1})
    except ValueError as exc:
        assert ">= 2" in str(exc)
    else:
        raise AssertionError("expected ValueError for ranks=1")


def test_loader_extracts_exact_fractions():
    data = {
        "topology_id": "rd8_free_v1",
        "ranks": 8,
        "nic": {"injection_bytes_per_ns": "12.5"},  # 25/2
        "link": {"pair_latency_ns": "3.5"},  # 7/2
    }
    infra = l0d.load_recursive_doubling_config(data)
    assert infra.injection_bytes_per_ns == Fraction(25, 2)
    assert infra.pair_latency_ns == Fraction(7, 2)
    assert infra.ranks == 8 and infra.steps == 3


def test_loader_reads_committed_topology_yaml():
    from pathlib import Path

    import yaml

    path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "topologies"
        / "rdoubling8_free_params.yaml"
    )
    infra = l0d.load_recursive_doubling_config(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert infra.topology_id == "rdoubling8_free_v1"
    assert infra.ranks == RANKS
    assert infra.steps == STEPS
    assert infra.injection_bytes_per_ns == Fraction(64)
    assert infra.pair_latency_ns == Fraction(200)


def test_execute_observables_exact_and_clean():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    result = l0d.execute(ops, _infra())
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 1
    assert conservation["violations"] == 0
    # Total wire = 8 * 28672 = 229376 = 2*(r-1)*M exactly.
    assert conservation["total_wire_bytes_exact"] == str(Fraction(229376))
    per_op = result["per_op"][0]
    assert per_op["steps_per_phase"] == STEPS
    assert per_op["per_rank_wire_bytes_exact"] == str(Fraction(28672))
    assert per_op["total_wire_bytes_exact"] == str(Fraction(229376))
    assert per_op["reduce_phase_time_ns_exact"] == str(Fraction(824))
    assert per_op["broadcast_phase_time_ns_exact"] == str(Fraction(824))
    assert per_op["completion_time_ns_exact"] == str(Fraction(1648))
    # Per-step decomposition: halving 8192/4096/2048 then doubling 2048/4096/8192.
    assert [s["chunk_bytes_exact"] for s in per_op["reduce_steps"]] == [
        str(Fraction(8192)),
        str(Fraction(4096)),
        str(Fraction(2048)),
    ]
    assert [s["chunk_bytes_exact"] for s in per_op["broadcast_steps"]] == [
        str(Fraction(2048)),
        str(Fraction(4096)),
        str(Fraction(8192)),
    ]
    assert [s["time_ns_exact"] for s in per_op["reduce_steps"]] == [
        str(Fraction(328)),
        str(Fraction(264)),
        str(Fraction(232)),
    ]
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(1648))
    assert cct["completion_time_ns_max"] == 1648.0
    model = result["model"]
    assert model["steps_log2_ranks"] == STEPS and model["ranks"] == RANKS


def test_execute_rejects_size_mismatch():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=4, layers=1, steps=1, allreduce_bytes=16384)
    )
    try:
        l0d.execute(ops, _infra())
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
        l0d.execute([bogus], _infra())
    except ValueError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported collective")
