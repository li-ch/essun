"""Golden identities for the UEC11-FC-R09 per-packet overhead constant (G2 S3).

Chain under test: anchored requirement UEC11-FC-R09 (UEC 1.1 §3.6.15, TFC
per-packet overhead constant, MUST) -> binding BIND-UEC11-FC-R09-L0TFC
(essun.specir.bindings) -> the opt-in tfc.pkt_overhead parameter of
analytical_l0_tfc -> tfc_pkt_size = c + tfc_pkt_overhead composed INSIDE
the S2 ROUNDUP cell law -> the quantized rate identity -> O-CCT. Expected
values are derived IN THIS FILE by exact Fraction arithmetic from the
stated identities (handoff rule: goldens derive from the specified
identities, never from the implementation's output).

Free parameters under test (registered in
experiments/vertical_slice/assumptions_tfc_pkt.yaml; the shared B, L, W,
L_cr, cell reuse the flagship/S2 values so the convergence anchors are
meaningful; none measured):

    B    = 64 bytes/ns     (A-TFCP-BW, = A-TFC-BW)
    L    = 200 ns          (A-TFCP-LAT, = A-TFC-LAT)
    L_cr = 200 ns          (A-TFCP-CR, = A-TFC-CR)
    W    = 12800 bytes     (A-TFCP-W, = A-TFC-W; 50 credit units)
    cell = 256 bytes       (A-TFCP-CELL, the UEC11-FC-R07 default cell)
    ovh  = 256 bytes       (A-TFCP-PKT-OVH, the UEC11-FC-R09 default)

Standard-derived constants (spec-cited, never invented): the 256-byte
credit unit (UEC11-FC-R05); the cell domain 256..9216 B in 256-byte
multiples (UEC11-FC-R07); the overhead DEFAULT 256 B (UEC11-FC-R09) and
its configurability bounds 0..256 B (UEC11-FC-R10 — whose own
recommendation disposition stays unsupported; the S3 binding adopts the
VALUES as the validated domain, the S2/R07 pattern).

Derived backbone (all exact): M = 16384, r = 8 => chunk c = 2048;
traffic T = 2*(r-1)/r*M = 28672; RTT = L + L_cr = 400; the R02 rate cap
W/RTT = 32 B/ns (window-limited, B = 64); the landed R02 time 3696 ns.
At the spec's own default point (cell 256, ovh 256): tfc_pkt_size
2048+256 = 2304 = exactly 9 cells => cq = 2304, efficiency 2048/2304 =
8/9, rate 256/9 B/ns, t = 28672*9/256 + 2800 = 1008 + 2800 = 3808 ns —
+112 ns/op over the overhead-less S2 identity at the same aligned cell
(3696 ns): the spec-default constant costs one credit unit per packet.
"""

from fractions import Fraction

import pytest

from essun.backends.analytical import l0_tfc
from essun.workload import w1

RANKS = 8
B = Fraction(64)
L = Fraction(200)
LCR = Fraction(200)
W = Fraction(12800)  # 50 x 256-byte credit units (the flagship window)
RTT = L + LCR  # 400 ns, derived
M = 16384
C = M // RANKS  # 2048 B ring chunk = the UET payload of tfc_pkt_size
T = Fraction(2 * (RANKS - 1) * M, RANKS)  # 28672 B/rank, derived
R02_RATE = W / RTT  # 32 B/ns admission cap (derived; < B: window-limited)
R02_TIME = T / R02_RATE + 2 * (RANKS - 1) * L  # 3696 ns, the landed literal


def _infra(
    cell: Fraction | None = Fraction(256),
    ovh: Fraction | None = Fraction(256),
) -> l0_tfc.TFCRingConfig:
    return l0_tfc.TFCRingConfig(
        topology_id="ring8_tfc_pkt_window_v1",
        ranks=RANKS,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
        tfc_window_bytes=W,
        tfc_credit_return_latency_ns=LCR,
        tfc_dest_cell_size=cell,
        tfc_pkt_overhead=ovh,
    )


def _ops(payload: int = M):
    return w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=payload)
    )


def _pkt_rate(cell: Fraction, ovh: Fraction) -> Fraction:
    # The composed law, derived here: cq = ROUNDUP((c+ovh)/cell)*cell,
    # useful-data rate = min(B, (c/cq) * W/RTT).
    cq = -((-Fraction(C + ovh)) // cell) * cell
    return min(B, Fraction(C) / cq * (W / RTT))


def _pkt_time(cell: Fraction, ovh: Fraction) -> Fraction:
    return T / _pkt_rate(cell, ovh) + 2 * (RANKS - 1) * L


# -- the composition law itself -------------------------------------------------


def test_composed_packet_matches_the_r08_worked_example():
    # UEC11-FC-R08's own worked example is an FC-R09 composition: 4096-B
    # payload + 256-B overhead => tfc_pkt_size 4352, against 512-B cells
    # => 4608 B of credit. S2 verified the ROUNDUP half with the packet
    # composed by hand; S3's parameter composes it natively.
    assert l0_tfc.tfc_packet_size(4096, Fraction(256)) == Fraction(4352)
    assert (
        l0_tfc.consumed_credit_bytes(
            l0_tfc.tfc_packet_size(4096, Fraction(256)), Fraction(512)
        )
        == Fraction(4608)
    )
    # The evidence-run shape: chunk 2048, default overhead => packet 2304.
    assert l0_tfc.tfc_packet_size(C, Fraction(256)) == Fraction(2304)


def test_overhead_domain_constants_cite_r09_and_r10():
    # The default constant is spec-derived via UEC11-FC-R09; the
    # configurability bounds 0..256 B are UEC11-FC-R10's stated values
    # (whose SHOULD disposition itself stays unsupported). Named
    # constants, not magic.
    assert l0_tfc.TFC_PKT_OVERHEAD_DEFAULT_BYTES == 256
    assert l0_tfc.TFC_PKT_OVERHEAD_MIN_BYTES == 0
    assert l0_tfc.TFC_PKT_OVERHEAD_MAX_BYTES == 256


# -- the composed identity: the spec's default point -----------------------------


def test_spec_default_point_moves_the_identity():
    # cell 256 (the R07 default) with overhead 256 (the R09 default):
    # the packet is exactly 9 cells, cq = 2304, efficiency 8/9, data rate
    # 256/9 B/ns, completion 3808 ns exactly.
    infra = _infra(cell=Fraction(256), ovh=Fraction(256))
    cq = l0_tfc.consumed_credit_bytes(
        l0_tfc.tfc_packet_size(C, Fraction(256)), Fraction(256)
    )
    assert cq == Fraction(2304)
    assert (
        l0_tfc.credit_efficiency_for_packet(C, Fraction(256), Fraction(256))
        == Fraction(8, 9)
    )
    expected_rate = _pkt_rate(Fraction(256), Fraction(256))
    assert expected_rate == Fraction(256, 9)
    assert l0_tfc.effective_rate_for_chunk(infra, C) == Fraction(256, 9)
    expected = _pkt_time(Fraction(256), Fraction(256))
    assert expected == Fraction(3808)
    assert (
        l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, infra) == Fraction(3808)
    )


def test_default_overhead_delta_against_s2_is_the_declared_term():
    # At the aligned cell 256 the S2 (overhead-less) identity is the R02
    # identity 3696 ns; the default overhead adds exactly
    # T*(1/Rd - 1/R02_rate) = 28672*(9/256 - 8/256) = 112 ns per op.
    s2_time = l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, _infra(ovh=None))
    assert s2_time == R02_TIME == Fraction(3696)
    expected_gap = T * (1 / Fraction(256, 9) - 1 / R02_RATE)
    assert expected_gap == Fraction(112)
    gap = l0_tfc.ring_allreduce_time_tfc_ns(
        M, RANKS, _infra(cell=Fraction(256), ovh=Fraction(256))
    ) - s2_time
    assert gap == expected_gap == Fraction(112)


def test_overhead_is_itself_cell_quantized_at_alignment():
    # With c == 0 (mod cell) the overhead cannot spend less than one
    # whole cell: ANY declared overhead in 1..256 B at cell 256 lands the
    # packet in cell 9, cq 2304, efficiency 8/9, time 3808 — the overhead
    # constant enters the law through the same ROUNDUP as the payload.
    for ovh in (1, 64, 128, 200, 256):
        infra = _infra(cell=Fraction(256), ovh=Fraction(ovh))
        assert l0_tfc.consumed_credit_bytes(
            l0_tfc.tfc_packet_size(C, Fraction(ovh)), Fraction(256)
        ) == Fraction(2304)
        assert (
            l0_tfc.credit_efficiency_for_packet(C, Fraction(256), Fraction(ovh))
            == Fraction(8, 9)
        )
        assert (
            l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, infra)
            == Fraction(3808)
        )
    # and overhead 0 is the no-overhead law (cq = c: 8 exact cells).
    assert (
        l0_tfc.consumed_credit_bytes(
            l0_tfc.tfc_packet_size(C, Fraction(0)), Fraction(256)
        )
        == Fraction(2048)
    )


def test_causal_move_at_a_larger_aligned_cell():
    # cell 2048 (== c, aligned): overhead 0 => one cell, efficiency 1,
    # the R02 identity 3696; overhead 1..2048 => two cells, cq 4096,
    # efficiency 1/2, rate 16, time 4592 — a +896 ns exact move
    # = T*(1/16 - 1/32) = 28672/32.
    zero = _infra(cell=Fraction(2048), ovh=Fraction(0))
    assert l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, zero) == R02_TIME
    for ovh in (1, 256, 2048):
        infra = _infra(cell=Fraction(2048), ovh=Fraction(ovh))
        assert l0_tfc.consumed_credit_bytes(
            l0_tfc.tfc_packet_size(C, Fraction(ovh)), Fraction(2048)
        ) == Fraction(4096)
        assert (
            l0_tfc.effective_rate_for_chunk(infra, C) == Fraction(16)
        )
        assert (
            l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, infra)
            == Fraction(4592)
        )
    expected_gap = T * (1 / Fraction(16) - 1 / Fraction(32))
    assert expected_gap == Fraction(896)


def test_per_packet_strategy_cell_absorbs_the_default_overhead():
    # cell 9216 (the R08-named per-packet strategy): the composed packet
    # 2304 still rounds up to one cell, cq 9216, efficiency 2/9 — the
    # S3 time equals the S2 (overhead-less) time 6832 ns exactly. A
    # per-packet cell large enough for payload+overhead absorbs the
    # overhead constant entirely: decision-relevant, and exact.
    s3 = _infra(cell=Fraction(9216), ovh=Fraction(256))
    s2 = _infra(cell=Fraction(9216), ovh=None)
    assert l0_tfc.consumed_credit_bytes(
        l0_tfc.tfc_packet_size(C, Fraction(256)), Fraction(9216)
    ) == Fraction(9216)
    assert (
        l0_tfc.credit_efficiency_for_packet(C, Fraction(9216), Fraction(256))
        == Fraction(2, 9)
    )
    assert l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, s3) == (
        l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, s2)
    ) == Fraction(6832)


# -- the convergence anchors ------------------------------------------------------


def test_zero_overhead_converges_to_the_r02_identity_exactly():
    # overhead = 0 with c == 0 (mod cell) => cq = c => efficiency 1 =>
    # the composed identity IS the landed R02 identity, for every aligned
    # cell in the domain (the S2 convergence anchor, now through the
    # declared-zero parameter rather than absence).
    for cell in (256, 512, 1024, 2048):
        aligned = _infra(cell=Fraction(cell), ovh=Fraction(0))
        assert C % cell == 0
        assert (
            l0_tfc.credit_efficiency_for_packet(C, Fraction(cell), Fraction(0))
            == Fraction(1)
        )
        assert (
            l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, aligned)
            == l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, _infra(None, None))
            == R02_TIME
            == Fraction(3696)  # the flagship golden literal
        )


def test_zero_overhead_converges_to_the_s2_law_off_alignment_too():
    # Declared overhead 0 recovers the S2 identity exactly at EVERY cell,
    # not just aligned ones: the waste-regime literals (cell 768 => 3808,
    # cell 9216 => 6832) are reproduced with the parameter declared.
    for cell, s2_time in ((768, 3808), (9216, 6832)):
        assert l0_tfc.ring_allreduce_time_tfc_ns(
            M, RANKS, _infra(cell=Fraction(cell), ovh=Fraction(0))
        ) == l0_tfc.ring_allreduce_time_tfc_ns(
            M, RANKS, _infra(cell=Fraction(cell), ovh=None)
        ) == Fraction(s2_time)


def test_declared_zero_equals_absent_in_law_not_in_provenance():
    # Declaring tfc.pkt_overhead = 0 gives byte-identical LAW outputs to
    # not declaring it (the convergence statement above, at run scope) —
    # but the declared parameter is live provenance: the run names the
    # R09 binding with its value 0. The laws agree; the records differ by
    # exactly the provenance of the declared parameter.
    declared = l0_tfc.execute(_ops(), _infra(cell=Fraction(256), ovh=Fraction(0)))
    absent = l0_tfc.execute(_ops(), _infra(cell=Fraction(256), ovh=None))
    assert (
        declared["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
        == absent["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
        == str(Fraction(3696))
    )
    assert (
        declared["observables"]["O-CONSERVATION"]
        == absent["observables"]["O-CONSERVATION"]
    )
    declared_ids = [b["binding_id"] for b in declared["requirement_bindings"]]
    absent_ids = [b["binding_id"] for b in absent["requirement_bindings"]]
    assert declared_ids == [
        "BIND-UEC11-FC-R02-L0TFC",
        "BIND-UEC11-FC-R08-L0TFC",
        "BIND-UEC11-FC-R09-L0TFC",
    ]
    assert absent_ids == ["BIND-UEC11-FC-R02-L0TFC", "BIND-UEC11-FC-R08-L0TFC"]


# -- the invariant, with the overhead term ----------------------------------------


def test_quantized_admission_invariant_holds_with_overhead():
    # UEC11-FC-R08's structural bound with the composed packet: in-flight
    # DATA bytes Rd*RTT <= (c/cq)*W, equality iff the quantized window
    # gates; credit bytes in flight never exceed W. At cell 2048 with
    # overhead 256 the efficiency is 1/2, so data in flight is exactly
    # W/2 while the credit-side invariant stays W (window-limited).
    infra = _infra(cell=Fraction(2048), ovh=Fraction(256))
    data_in_flight = l0_tfc.admission_invariant_for_chunk(infra, C)
    bound = Fraction(1, 2) * W
    assert data_in_flight == Fraction(6400) == bound  # window-limited
    assert l0_tfc.admission_invariant(infra) == W  # credit side unchanged
    # At the spec-default point (cell 256, efficiency 8/9): same shape.
    infra_default = _infra(cell=Fraction(256), ovh=Fraction(256))
    assert l0_tfc.admission_invariant_for_chunk(infra_default, C) == (
        Fraction(8, 9) * W
    )


# -- the observable change: O-CCT moves, O-CONSERVATION does not ------------------


def test_execute_moves_cct_and_conserves_bytes_with_the_overhead():
    pkt_result = l0_tfc.execute(
        _ops(), _infra(cell=Fraction(256), ovh=Fraction(256))
    )
    s2_result = l0_tfc.execute(_ops(), _infra(cell=Fraction(256), ovh=None))
    r02_result = l0_tfc.execute(_ops(), _infra(None, None))
    # The overhead constant gates credit consumption, never byte count:
    # wire ledgers identical across all three regimes.
    assert (
        pkt_result["observables"]["O-CONSERVATION"]
        == s2_result["observables"]["O-CONSERVATION"]
        == r02_result["observables"]["O-CONSERVATION"]
    )
    assert pkt_result["observables"]["O-CONSERVATION"][
        "total_wire_bytes_exact"
    ] == str(Fraction(2 * (RANKS - 1) * M))
    # O-CCT carries the composed-law mean and all three bindings.
    cct = pkt_result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3808))
    tfc = cct["tfc"]
    assert tfc["cell"]["pkt"]["requirement_id"] == "UEC11-FC-R09"
    assert tfc["cell"]["pkt"]["binding_id"] == "BIND-UEC11-FC-R09-L0TFC"
    assert tfc["cell"]["pkt"]["overhead_bytes"] == 256
    assert tfc["cell"]["pkt"]["tfc_pkt_size_bytes_exact"] == str(
        Fraction(2304)
    )
    assert tfc["cell"]["credit_used_bytes_exact"] == str(Fraction(2304))
    assert tfc["cell"]["credit_efficiency_exact"] == str(Fraction(8, 9))
    assert tfc["cell"]["effective_data_rate_bytes_per_ns_exact"] == str(
        Fraction(256, 9)
    )
    assert tfc["window_limited"] is True  # the R02 window still gates
    binding_ids = [b["binding_id"] for b in pkt_result["requirement_bindings"]]
    assert binding_ids == [
        "BIND-UEC11-FC-R02-L0TFC",
        "BIND-UEC11-FC-R08-L0TFC",
        "BIND-UEC11-FC-R09-L0TFC",
    ]
    assert pkt_result["backend"]["tfc_dest_cell_size_bytes"] == 256
    assert pkt_result["backend"]["tfc_pkt_overhead_bytes"] == 256
    # Without a declared overhead the S2 shape: no pkt block, two bindings.
    assert "pkt" not in s2_result["observables"]["O-CCT"]["tfc"]["cell"]
    assert "tfc_pkt_overhead_bytes" not in s2_result["backend"]


def test_one_overhead_constant_structurally_across_ops():
    # UEC11-FC-R09's MUST is that source and destination use the SAME
    # constant. One model carries one constant: every op's composed
    # packet uses the same declared overhead. Structural fact of this
    # backend (stated as structure, not claimed as an executed protocol
    # property — no two-endpoint protocol is simulated).
    result = l0_tfc.execute(
        _ops(), _infra(cell=Fraction(256), ovh=Fraction(256))
    )
    per_op = result["observables"]["O-CCT"]["tfc"]["cell"]["per_op"]
    assert per_op
    for op in per_op:
        assert op["pkt_overhead_bytes"] == 256
        assert op["tfc_pkt_size_bytes_exact"] == str(Fraction(2304))
        assert op["chunk_bytes"] == C  # payload unchanged by the constant


# -- load-time semantics: the R10-cited domain and the cell requirement ------------


def test_loader_rejects_out_of_domain_overheads():
    # Out-of-domain overheads are rejected at load time citing
    # UEC11-FC-R10: below 0, above 256, and non-integral byte counts.
    base = {
        "topology_id": "t",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
        "tfc": {
            "window_bytes": 12800,
            "credit_return_latency_ns": 200,
            "dest_cell_size": 256,
        },
    }
    for bad in (-1, 257, 512, 100.5, "1e-3"):
        with pytest.raises(ValueError, match="UEC11-FC-R10"):
            l0_tfc.load_tfc_config(
                {**base, "tfc": {**base["tfc"], "pkt_overhead": bad}}
            )


def test_loader_accepts_the_domain_boundaries():
    # 0 (the convergence boundary) and 256 (the spec default) are the
    # closed boundaries of the configurable set — both load.
    base = {
        "topology_id": "t",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
        "tfc": {
            "window_bytes": 12800,
            "credit_return_latency_ns": 200,
            "dest_cell_size": 256,
        },
    }
    for good in (0, 1, 128, 256):
        config = l0_tfc.load_tfc_config(
            {**base, "tfc": {**base["tfc"], "pkt_overhead": good}}
        )
        assert config.tfc_pkt_overhead == Fraction(good)
    absent = l0_tfc.load_tfc_config(dict(base))
    assert absent.tfc_pkt_overhead is None


def test_loader_rejects_overhead_without_a_cell():
    # The overhead constant feeds the ROUNDUP cell law; declaring it
    # without tfc.dest_cell_size is rejected citing the binding.
    data = {
        "topology_id": "t",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
        "tfc": {
            "window_bytes": 12800,
            "credit_return_latency_ns": 200,
            "pkt_overhead": 256,
        },
    }
    with pytest.raises(ValueError, match="BIND-UEC11-FC-R09-L0TFC"):
        l0_tfc.load_tfc_config(data)


# -- run path: the evidence manifest executes end-to-end ---------------------------


def test_run_path_dispatch_determinism_and_v2_stamp(tmp_path):
    from essun.orchestrator import runs as orchestrator

    manifest = "experiments/vertical_slice/w1_decode_tfc_pkt.yaml"
    first = orchestrator.run_experiment(manifest, results_root=tmp_path / "a")
    second = orchestrator.run_experiment(manifest, results_root=tmp_path / "b")
    assert first["run_id"] == second["run_id"]  # deterministic, content-addressed
    record = orchestrator.EvidenceStore(tmp_path / "a").get_run(first["run_id"])
    # The evidence run is v2-stamped with the declared dimensions block.
    assert record["evidence_schema_version"] == 2
    assert record["calibration_target"] == []
    assert record["held_out"] == {"held_out": False, "scope": _HELD_OUT_SCOPE}
    cct = first["observations"]["observables"]["O-CCT"]
    # 6 ops x 16384 B (layers 2 x steps 3): every op is the spec-default
    # point (chunk 2048, cell 256, overhead 256) -> mean 3808 ns exactly.
    assert cct["ops"] == 6
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3808))
    assert first["observations"]["requirement_bindings"][-1] == {
        "binding_id": "BIND-UEC11-FC-R09-L0TFC",
        "requirement_id": "UEC11-FC-R09",
        "disposition": "simulated_behavior",
        "pkt_overhead_range_requirement_id": "UEC11-FC-R10",
        "credit_unit_requirement_id": "UEC11-FC-R05",
    }
    claims = (tmp_path / "a" / "claims_index.jsonl").read_text().strip()
    assert "C-UEC-TFC-R09" in claims and first["run_id"] in claims


_HELD_OUT_SCOPE = (
    "no data withheld; all inputs derive from the identity (E0)"
)
