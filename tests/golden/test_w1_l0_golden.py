"""Golden identities for the W1 generator and the L0 ring backend.

Expected values are recomputed independently here (not by calling the
implementation under test), per the handoff rule that golden tests derive
from the specified identities, not from the implementation's output.
"""

from fractions import Fraction

from essun.backends.analytical import l0
from essun.workload import w1

# 16 KiB and 1 MiB are the T020 acceptance cases.
SIZES = [16384, 1048576]
RANKS = 8


def _infra():
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )


def test_w1_ops_count_order_and_sizes():
    config = w1.W1Config(tp_size=RANKS, layers=2, steps=3, allreduce_bytes=16384)
    ops = w1.generate_w1_ops(config)
    assert len(ops) == 6
    expected_ids = [
        f"s{step:06d}-l{layer:06d}-allreduce"
        for step in range(3)
        for layer in range(2)
    ]
    assert [op.op_id for op in ops] == expected_ids
    assert all(op.collective == "allreduce" for op in ops)
    assert all(op.comm_ranks == tuple(range(RANKS)) for op in ops)
    assert all(op.payload_bytes == 16384 for op in ops)


def test_w1_identity_16kib_and_1mib():
    for size in SIZES:
        config = w1.W1Config(tp_size=RANKS, layers=2, steps=3, allreduce_bytes=size)
        ops = w1.generate_w1_ops(config)
        assert len(ops) == 6
        assert all(op.payload_bytes == size for op in ops)


def test_ring_traffic_identity_16kib_and_1mib():
    # T(M, r) = 2*(r-1)/r * M: for r=8 that is 7/4 * M.
    for size in SIZES:
        expected = Fraction(2 * (RANKS - 1) * size, RANKS)
        assert l0.ring_traffic_per_rank(size, RANKS) == expected
    assert l0.ring_traffic_per_rank(16384, RANKS) == Fraction(28672)
    assert l0.ring_traffic_per_rank(1048576, RANKS) == Fraction(1835008)


def test_ring_completion_time_identity_16kib():
    # t = T/B + 2*(r-1)*L = 28672/64 + 14*200 = 448 + 2800 = 3248 ns.
    assert l0.ring_allreduce_time_ns(16384, RANKS, _infra()) == Fraction(3248)


def test_conservation_observable_exact_and_clean():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=16384)
    )
    result = l0.execute(ops, _infra())
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 1
    assert conservation["violations"] == 0
    # Total wire bytes = 2*(r-1)*M = 229376.
    assert conservation["total_wire_bytes_exact"] == str(Fraction(229376))
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3248))


def test_execute_rejects_size_mismatch():
    ops = w1.generate_w1_ops(
        w1.W1Config(tp_size=4, layers=1, steps=1, allreduce_bytes=16384)
    )
    try:
        l0.execute(ops, _infra())
    except ValueError as exc:
        assert "comm group size" in str(exc)
    else:
        raise AssertionError("expected ValueError for rank mismatch")
