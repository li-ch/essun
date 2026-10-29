"""Golden identities for the L0 phase collectives, P2 stage S4.

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the handoff
rule that golden tests derive from the specified identities.

Identities under test (ReduceScatter / AllGather as first-class collectives):

    ring family (fabric ring8: B=64, L=200):
        t_rs = t_ag = (r-1)/r*M/B + (r-1)*L ; wire/rank (r-1)/r*M ; total (r-1)*M
        RS result M/r per rank; AG result M per rank.
    doubling family (fabric rdoubling8: B=64, L=200, k=log2 r):
        t_rs = sum_i (M/2^i)/B + k*L ; t_ag = sum_i (2^(i-1)*M/r)/B + k*L
        each sum = (r-1)/r*M/B + log2(r)*L ; wire/rank (r-1)/r*M ; total (r-1)*M.
    composition (A-L0P-COMP): RS(M) + AG(M) = landed AllReduce(M) exactly.

Worked cases (derived by hand below, asserted as exact Fractions):

A) r=8, M=16384, B=64, L=200: phase wire 7/8*16384=14336; ring phase
   t=14336/64+7*200=224+1400=1624; total wire 8*14336=114688=7*16384;
   RS+AG=3248=landed ring AllReduce (28672/64+14*200=448+2800).
B) r=8, M=1048576: phase wire 917504; ring phase t=14336+1400=15736;
   total wire 7340032; RS+AG=31472. Doubling phase steps 8392/4296/2248
   -> 14936 (halving) and mirrored (doubling); RS+AG=29872.
C) r=8, M=16384 doubling: halving steps 328/264/232 -> 824 (chunks
   8192/4096/2048); doubling AG mirrored 232/264/328 -> 824; RS+AG=1648
   (= landed recursive-doubling AllReduce, S3 case A).
D) r=4, M=1000, B=10, L=1: ring phase 750/10+3=78, total wire 3000,
   RS+AG=156; halving 51+26=77, doubling AG 26+51=77, RS+AG=154 (S3 case D);
   crossbar RS (S1, oracle with pinned literal) = 76. Latency ladder per
   phase: ring (r-1)L=3 >= halving log2(r)L=2 >= crossbar L=1, wire/rank
   750 IDENTICAL for all three.
E) r=8, M=1000, B=12.5=25/2, L=0.5=1/2 (decimal free parameters): ring
   phase 875/(25/2)+7*(1/2)=70+7/2=147/2, composition 147; halving steps
   81/2, 41/2, 21/2 -> 143/2, doubling AG mirrored, composition 143; the
   families differ by (r-1-log2 r)*L = 2, exactly.
F) r=2, M=16384: every phase degenerates to M/(2B)+L=128+200=328; RS+AG=656
   = M/B+2L (the three-way AllReduce coincidence at r=2, S3 case C).
G) Result bytes: RS(16384,8)=2048, AG(16384,8)=16384, RS(1000,4)=250.
"""

from fractions import Fraction
from pathlib import Path

import yaml

from essun.backends.analytical import l0
from essun.backends.analytical import l0_crossbar as l0x
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.backends.analytical import l0_recursive_doubling as l0d
from essun.workload import w1

RANKS = 8
_TOPO = Path(__file__).resolve().parents[2] / "experiments" / "topologies"


def _ring_infra(ranks=RANKS, bw=64, lat=200):
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=ranks,
        link_bytes_per_ns=Fraction(bw),
        hop_latency_ns=Fraction(lat),
    )


def _rd_infra(ranks=RANKS, bw=64, lat=200):
    return l0d.RecursiveDoublingConfig(
        topology_id="rdoubling8_free_v1",
        ranks=ranks,
        injection_bytes_per_ns=Fraction(bw),
        pair_latency_ns=Fraction(lat),
        steps=l0d._log2_steps(ranks),
    )


def _phase_ops(collectives=("reducescatter", "allgather"), tp_size=RANKS, payload=16384):
    base = w1.generate_w1_ops(
        w1.W1Config(tp_size=tp_size, layers=1, steps=1, allreduce_bytes=payload)
    )[0]
    return [
        w1.CollectiveOp(
            op_id=f"s000000-l000000-{c}",
            collective=c,
            comm_ranks=base.comm_ranks,
            payload_bytes=base.payload_bytes,
            step=base.step,
            layer=base.layer,
        )
        for c in collectives
    ]


# --- A/B: ring family identities -------------------------------------------


def test_phase_traffic_is_half_the_landed_allreduce():
    # Phase wire 7/8*M; two phases make the landed ring/doubling AllReduce
    # traffic 2*(r-1)/r*M = 28672 at M=16384, r=8 (hand-derived).
    assert l0p.phase_traffic_per_rank(16384, 8) == Fraction(14336)
    assert 2 * l0p.phase_traffic_per_rank(16384, 8) == Fraction(28672)
    assert 2 * l0p.phase_traffic_per_rank(16384, 8) == l0.ring_traffic_per_rank(16384, 8)
    assert 2 * l0p.phase_traffic_per_rank(16384, 8) == l0d.rd_traffic_per_rank(16384, 8)
    assert l0p.phase_traffic_per_rank(1048576, 8) == Fraction(917504)
    # Conservation per op: r * (r-1)/r*M = (r-1)*M = 7*16384.
    assert l0p.phase_traffic_per_rank(16384, 8) * 8 == Fraction(7 * 16384)


def test_ring_phases_16kib():
    # A: t_rs = t_ag = 14336/64 + 7*200 = 224 + 1400 = 1624.
    infra = _ring_infra()
    assert l0p.ring_reducescatter_time_ns(16384, 8, infra) == Fraction(1624)
    assert l0p.ring_allgather_time_ns(16384, 8, infra) == Fraction(1624)


def test_ring_phases_1mib():
    # B: t = 917504/64 + 1400 = 14336 + 1400 = 15736; total wire 7340032.
    infra = _ring_infra()
    assert l0p.ring_reducescatter_time_ns(1048576, 8, infra) == Fraction(15736)
    assert l0p.ring_allgather_time_ns(1048576, 8, infra) == Fraction(15736)
    assert l0p.phase_traffic_per_rank(1048576, 8) * 8 == Fraction(7340032)


def test_ring_phases_compose_to_landed_ring_allreduce():
    # A/B: RS+AG = 3248 at 16 KiB and 31472 at 1 MiB — exactly the landed
    # ring AllReduce identity (hand-derived: 448+2800 and 28672+2800).
    infra = _ring_infra()
    assert l0p.ring_allreduce_from_phases_time_ns(16384, 8, infra) == Fraction(3248)
    assert l0p.ring_allreduce_from_phases_time_ns(1048576, 8, infra) == Fraction(31472)
    assert l0p.ring_allreduce_from_phases_time_ns(16384, 8, infra) == (
        l0.ring_allreduce_time_ns(16384, 8, infra)
    )
    assert l0p.ring_allreduce_from_phases_time_ns(1048576, 8, infra) == (
        l0.ring_allreduce_time_ns(1048576, 8, infra)
    )


# --- C: doubling family identities ------------------------------------------


def test_doubling_phases_16kib_step_by_step():
    # C: halving RS chunks 8192/4096/2048 -> 328/264/232 -> 824; doubling AG
    # mirrored 232/264/328 -> 824.
    infra = _rd_infra()
    halving_chunks = [l0d.reduce_step_chunk(16384, i, 8) for i in (1, 2, 3)]
    halving_times = [
        c / infra.injection_bytes_per_ns + infra.pair_latency_ns
        for c in halving_chunks
    ]
    assert halving_times == [Fraction(328), Fraction(264), Fraction(232)]
    assert l0p.halving_reducescatter_time_ns(16384, infra) == Fraction(824)
    doubling_times = [
        l0d.broadcast_step_chunk(16384, i, 8) / infra.injection_bytes_per_ns
        + infra.pair_latency_ns
        for i in (1, 2, 3)
    ]
    assert doubling_times == [Fraction(232), Fraction(264), Fraction(328)]
    assert l0p.doubling_allgather_time_ns(16384, infra) == Fraction(824)


def test_doubling_phases_1mib():
    # B: steps 8392/4296/2248 -> 14936 per phase (halving chunks
    # 524288/262144/131072 over B=64); composition 29872.
    infra = _rd_infra()
    assert l0p.halving_reducescatter_time_ns(1048576, infra) == Fraction(14936)
    assert l0p.doubling_allgather_time_ns(1048576, infra) == Fraction(14936)
    assert l0p.rd_allreduce_from_phases_time_ns(1048576, infra) == Fraction(29872)


def test_doubling_phases_compose_to_landed_rd_allreduce():
    # C: RS+AG = 1648 at 16 KiB, 29872 at 1 MiB — exactly the S3 identity.
    infra = _rd_infra()
    assert l0p.rd_allreduce_from_phases_time_ns(16384, infra) == Fraction(1648)
    assert l0p.rd_allreduce_from_phases_time_ns(16384, infra) == (
        l0d.rd_allreduce_time_ns(16384, infra)
    )
    assert l0p.rd_allreduce_from_phases_time_ns(1048576, infra) == (
        l0d.rd_allreduce_time_ns(1048576, infra)
    )


# --- D: non-integer case + design-space latency ladder -----------------------


def test_ring_phase_noninteger_r4():
    # D: ring phase 750/10 + 3 = 78; total wire 3000; composition 156
    # (= 2*750/10 + 2*3, the landed ring AllReduce at r=4).
    infra = _ring_infra(ranks=4, bw=10, lat=1)
    assert l0p.phase_traffic_per_rank(1000, 4) == Fraction(750)
    assert l0p.phase_traffic_per_rank(1000, 4) * 4 == Fraction(3000)
    assert l0p.ring_reducescatter_time_ns(1000, 4, infra) == Fraction(78)
    assert l0p.ring_allgather_time_ns(1000, 4, infra) == Fraction(78)
    assert l0p.ring_allreduce_from_phases_time_ns(1000, 4, infra) == Fraction(156)
    assert l0p.ring_allreduce_from_phases_time_ns(1000, 4, infra) == (
        l0.ring_allreduce_time_ns(1000, 4, infra)
    )


def test_doubling_phase_noninteger_r4():
    # D: halving 51+26=77; doubling AG 26+51=77; composition 154 (S3 case D).
    infra = _rd_infra(ranks=4, bw=10, lat=1)
    assert l0p.halving_reducescatter_time_ns(1000, infra) == Fraction(77)
    assert l0p.doubling_allgather_time_ns(1000, infra) == Fraction(77)
    assert l0p.rd_allreduce_from_phases_time_ns(1000, infra) == Fraction(154)
    assert l0p.rd_allreduce_from_phases_time_ns(1000, infra) == (
        l0d.rd_allreduce_time_ns(1000, infra)
    )


def test_phase_latency_ladder_same_wire_bytes():
    # D: per-phase latency ladder at r=4, M=1000, B=10, L=1 — ring 78,
    # halving 77, crossbar 76, each differing by exactly 1*L; per-rank wire
    # 750 IDENTICAL across all three algorithms (the S4 emerging property).
    ring4 = _ring_infra(ranks=4, bw=10, lat=1)
    rd4 = _rd_infra(ranks=4, bw=10, lat=1)
    cb4 = l0x.CrossbarConfig(
        topology_id="cb4",
        ranks=4,
        injection_bytes_per_ns=Fraction(10),
        pair_latency_ns=Fraction(1),
    )
    assert l0p.ring_reducescatter_time_ns(1000, 4, ring4) == Fraction(78)
    assert l0p.halving_reducescatter_time_ns(1000, rd4) == Fraction(77)
    assert l0x.crossbar_reduce_scatter_time_ns(1000, 4, cb4) == Fraction(76)
    assert l0p.ring_reducescatter_time_ns(1000, 4, ring4) - (
        l0p.halving_reducescatter_time_ns(1000, rd4)
    ) == Fraction(1)  # (r-1-log2 r)*L = 1
    assert l0p.halving_reducescatter_time_ns(1000, rd4) - (
        l0x.crossbar_reduce_scatter_time_ns(1000, 4, cb4)
    ) == Fraction(1)  # (log2 r - 1)*L = 1
    assert l0p.phase_traffic_per_rank(1000, 4) == Fraction(750)


# --- E/F: exactness under decimals and degenerate r=2 ------------------------


def test_decimal_parameters_stay_exact():
    # E: B=25/2, L=1/2, r=8, M=1000: ring phase 875/(25/2)+7*(1/2)=70+7/2=147/2
    # (latency chain (r-1)*L = 7/2); halving steps 81/2, 41/2, 21/2 -> 143/2
    # (chain k*L = 3/2); compositions 147 and 143 respectively — the two
    # families differ by exactly (r-1-log2 r)*L = 2 at decimal parameters.
    ring8 = _ring_infra(ranks=8, bw=Fraction(25, 2), lat=Fraction(1, 2))
    assert l0p.ring_reducescatter_time_ns(1000, 8, ring8) == Fraction(147, 2)
    assert l0p.ring_allgather_time_ns(1000, 8, ring8) == Fraction(147, 2)
    assert l0p.ring_allreduce_from_phases_time_ns(1000, 8, ring8) == Fraction(147)
    rd8 = _rd_infra(ranks=8, bw=Fraction(25, 2), lat=Fraction(1, 2))
    halving_steps = [
        l0d.reduce_step_chunk(1000, i, 8) / rd8.injection_bytes_per_ns
        + rd8.pair_latency_ns
        for i in (1, 2, 3)
    ]
    assert halving_steps == [Fraction(81, 2), Fraction(41, 2), Fraction(21, 2)]
    assert l0p.halving_reducescatter_time_ns(1000, rd8) == Fraction(143, 2)
    assert l0p.doubling_allgather_time_ns(1000, rd8) == Fraction(143, 2)
    assert l0p.rd_allreduce_from_phases_time_ns(1000, rd8) == Fraction(143)
    assert l0p.ring_reducescatter_time_ns(1000, 8, ring8) - (
        l0p.halving_reducescatter_time_ns(1000, rd8)
    ) == Fraction(2)  # (r-1-log2 r)*L = 4*(1/2)


def test_r2_degenerate_coincidence():
    # F: every phase at r=2 is M/(2B)+L = 128+200 = 328; RS+AG = 656 = M/B+2L,
    # matching the landed ring / crossbar / recursive-doubling coincidence.
    ring2 = _ring_infra(ranks=2)
    rd2 = _rd_infra(ranks=2)
    assert l0p.ring_reducescatter_time_ns(16384, 2, ring2) == Fraction(328)
    assert l0p.ring_allgather_time_ns(16384, 2, ring2) == Fraction(328)
    assert l0p.halving_reducescatter_time_ns(16384, rd2) == Fraction(328)
    assert l0p.doubling_allgather_time_ns(16384, rd2) == Fraction(328)
    assert l0p.ring_allreduce_from_phases_time_ns(16384, 2, ring2) == Fraction(656)
    assert l0p.rd_allreduce_from_phases_time_ns(16384, rd2) == Fraction(656)


# --- G: result-bytes semantics ------------------------------------------------


def test_result_bytes_semantics():
    # G: ReduceScatter leaves M/r; AllGather leaves the full gathered M.
    assert l0p.reducescatter_result_bytes(16384, 8) == Fraction(2048)
    assert l0p.allgather_result_bytes(16384, 8) == Fraction(16384)
    assert l0p.reducescatter_result_bytes(1000, 4) == Fraction(250)
    assert l0p.allgather_result_bytes(1000, 4) == Fraction(1000)


# --- Execution with observables ----------------------------------------------


def test_execute_ring_phases_observables():
    # A: one RS + one AG op on the committed ring fabric: each 1624 ns,
    # wire 114688 per op, conservation total 229376, composed sum 3248.
    data = yaml.safe_load(
        (_TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8")
    )
    infra = l0.load_infra(data)
    result = l0p.execute_ring_phases(_phase_ops(), infra)
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 2
    assert conservation["violations"] == 0
    assert conservation["total_wire_bytes_exact"] == str(Fraction(2 * 114688))
    rs, ag = result["per_op"]
    assert rs["collective"] == "reducescatter" and rs["algorithm"] == "ring"
    assert ag["collective"] == "allgather" and ag["algorithm"] == "ring"
    for op in (rs, ag):
        assert op["chunk_bytes_exact"] == str(Fraction(2048))
        assert op["hops"] == 7
        assert op["per_rank_wire_bytes_exact"] == str(Fraction(14336))
        assert op["total_wire_bytes_exact"] == str(Fraction(114688))
        assert op["completion_time_ns_exact"] == str(Fraction(1624))
    assert rs["result_bytes_per_rank_exact"] == str(Fraction(2048))
    assert ag["result_bytes_per_rank_exact"] == str(Fraction(16384))
    # Phase composition through the observable surface: RS + AG = AllReduce.
    composed = Fraction(rs["completion_time_ns_exact"]) + Fraction(
        ag["completion_time_ns_exact"]
    )
    assert composed == Fraction(3248)
    assert composed == l0.ring_allreduce_time_ns(16384, 8, infra)
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(1624))
    assert cct["completion_time_ns_max"] == 1624.0


def test_execute_doubling_phases_observables():
    # C: one RS + one AG op on the committed doubling fabric: each 824 ns,
    # per-step decomposition recorded, conservation total 229376, sum 1648.
    data = yaml.safe_load(
        (_TOPO / "rdoubling8_free_params.yaml").read_text(encoding="utf-8")
    )
    infra = l0d.load_recursive_doubling_config(data)
    result = l0p.execute_doubling_phases(_phase_ops(), infra)
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["ops_checked"] == 2
    assert conservation["violations"] == 0
    assert conservation["total_wire_bytes_exact"] == str(Fraction(229376))
    rs, ag = result["per_op"]
    assert rs["algorithm"] == "recursive_halving"
    assert ag["algorithm"] == "recursive_doubling"
    assert [s["chunk_bytes_exact"] for s in rs["steps"]] == [
        str(Fraction(8192)),
        str(Fraction(4096)),
        str(Fraction(2048)),
    ]
    assert [s["time_ns_exact"] for s in rs["steps"]] == [
        str(Fraction(328)),
        str(Fraction(264)),
        str(Fraction(232)),
    ]
    assert [s["chunk_bytes_exact"] for s in ag["steps"]] == [
        str(Fraction(2048)),
        str(Fraction(4096)),
        str(Fraction(8192)),
    ]
    for op in (rs, ag):
        assert op["steps_log2_ranks"] == 3
        assert op["per_rank_wire_bytes_exact"] == str(Fraction(14336))
        assert op["completion_time_ns_exact"] == str(Fraction(824))
    assert rs["result_bytes_per_rank_exact"] == str(Fraction(2048))
    assert ag["result_bytes_per_rank_exact"] == str(Fraction(16384))
    composed = Fraction(rs["completion_time_ns_exact"]) + Fraction(
        ag["completion_time_ns_exact"]
    )
    assert composed == Fraction(1648)
    assert composed == l0d.rd_allreduce_time_ns(16384, infra)
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(824))


def test_execute_rejects_allreduce_and_mismatched_sizes():
    # Phase entry points refuse whole-AllReduce ops and wrong comm sizes.
    ring_ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    for execute, infra in (
        (l0p.execute_ring_phases, _ring_infra()),
        (l0p.execute_doubling_phases, _rd_infra()),
    ):
        try:
            execute(ring_ops, infra)
        except ValueError as exc:
            assert "not supported" in str(exc)
        else:
            raise AssertionError("expected ValueError for allreduce op")
    small = _phase_ops(tp_size=4)
    for execute, infra in (
        (l0p.execute_ring_phases, _ring_infra()),
        (l0p.execute_doubling_phases, _rd_infra()),
    ):
        try:
            execute(small, infra)
        except ValueError as exc:
            assert "comm group size" in str(exc)
        else:
            raise AssertionError("expected ValueError for rank mismatch")


# --- Algorithm config YAML (stage config artifact) ----------------------------


def test_algorithm_config_yaml_loads_and_matches_capabilities():
    data = yaml.safe_load(
        (_TOPO / "phase_collectives8_free_params.yaml").read_text(encoding="utf-8")
    )
    entries = l0p.load_phase_algorithm_config(data)
    assert len(entries) == 4
    assert [(e["collective"], e["algorithm"]) for e in entries] == [
        ("reducescatter", "ring"),
        ("allgather", "ring"),
        ("reducescatter", "recursive_halving"),
        ("allgather", "recursive_doubling"),
    ]
    # Capability names are the pairings, single source of truth.
    assert l0p.CAPABILITIES["collectives"] == (
        "reducescatter_ring",
        "allgather_ring",
        "reducescatter_recursive_halving",
        "allgather_recursive_doubling",
    )
    # Each referenced topology exists on disk and loads through its landed
    # loader (ring family -> l0.load_infra, doubling family -> l0d loader).
    assert {e["topology"] for e in entries} == {"ring8_free_v1", "rdoubling8_free_v1"}
    ring_data = yaml.safe_load(
        (_TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8")
    )
    rd_data = yaml.safe_load(
        (_TOPO / "rdoubling8_free_params.yaml").read_text(encoding="utf-8")
    )
    assert l0.load_infra(ring_data).topology_id == "ring8_free_v1"
    assert l0d.load_recursive_doubling_config(rd_data).ranks == RANKS


def test_algorithm_config_rejects_undeclared_pairings():
    data = yaml.safe_load(
        (_TOPO / "phase_collectives8_free_params.yaml").read_text(encoding="utf-8")
    )
    bad = {**data, "collectives": data["collectives"][:1] + [
        {
            "collective": "allgather",
            "algorithm": "ring_overlap",  # not a capability-declared identity
            "topology": "ring8_free_v1",
        }
    ]}
    try:
        l0p.load_phase_algorithm_config(bad)
    except ValueError as exc:
        assert "explicitly unsupported" in str(exc)
    else:
        raise AssertionError("expected ValueError for undeclared pairing")
    try:
        l0p.load_phase_algorithm_config({**data, "collectives": []})
    except ValueError as exc:
        assert "no pairings" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty pairing list")
