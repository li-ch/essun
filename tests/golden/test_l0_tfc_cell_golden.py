"""Golden identities for the UEC11-FC-R08 cell-quantization law (G2 stage S2).

Chain under test: anchored requirement UEC11-FC-R08 (UEC 1.1 §3.6.15, TFC
credit consumption, DEFINITIONAL) -> binding BIND-UEC11-FC-R08-L0TFC
(essun.specir.bindings) -> the opt-in tfc_dest_cell_size parameter of
analytical_l0_tfc -> the quantized rate identity -> O-CCT. Expected
values are derived IN THIS FILE by exact Fraction arithmetic from the
stated identities (handoff rule: goldens derive from the specified
identities, never from the implementation's output).

Free parameters under test (registered in
experiments/vertical_slice/assumptions_tfc_cell.yaml; the shared B, L, W,
L_cr reuse the flagship values so the convergence anchor to the landed
R02 identity is meaningful; none measured):

    B    = 64 bytes/ns     (A-TFCC-BW, = A-TFC-BW)
    L    = 200 ns          (A-TFCC-LAT, = A-TFC-LAT)
    L_cr = 200 ns          (A-TFCC-CR, = A-TFC-CR)
    W    = 12800 bytes     (A-TFCC-W, = A-TFC-W; 50 credit units)
    cell = 9216 bytes      (A-TFCC-CELL, the R08-named per-packet strategy)

Standard-derived constants (spec-cited, never invented): the 256-byte
credit unit (UEC11-FC-R05) and the cell domain 256..9216 B in 256-byte
multiples (UEC11-FC-R07 — whose own obligation stays unsupported; the
S2 binding adopts its VALUES as the validated domain).

Derived backbone (all exact): M = 16384, r = 8 => chunk c = 2048;
traffic T = 2*(r-1)/r*M = 28672; RTT = L + L_cr = 400; the R02 rate cap
W/RTT = 32 B/ns (window-limited, B = 64). With cell = 9216:
cq = 9216, efficiency c/cq = 2/9, data rate = 64/9 B/ns, completion
t = 28672/(64/9) + 14*200 = 4032 + 2800 = 6832 ns.
"""

from fractions import Fraction

import pytest

from essun.backends.analytical import l0, l0_tfc
from essun.workload import w1

RANKS = 8
B = Fraction(64)
L = Fraction(200)
LCR = Fraction(200)
W = Fraction(12800)  # 50 x 256-byte credit units (the flagship window)
RTT = L + LCR  # 400 ns, derived
M = 16384
C = M // RANKS  # 2048 B ring chunk = tfc_pkt_size at S2, derived
T = Fraction(2 * (RANKS - 1) * M, RANKS)  # 28672 B/rank, derived
R02_RATE = W / RTT  # 32 B/ns admission cap (derived; < B: window-limited)
R02_TIME = T / R02_RATE + 2 * (RANKS - 1) * L  # 3696 ns, the landed literal


def _infra(cell: Fraction | None = Fraction(9216)) -> l0_tfc.TFCRingConfig:
    return l0_tfc.TFCRingConfig(
        topology_id="ring8_tfc_cell_window_v1",
        ranks=RANKS,
        link_bytes_per_ns=B,
        hop_latency_ns=L,
        tfc_window_bytes=W,
        tfc_credit_return_latency_ns=LCR,
        tfc_dest_cell_size=cell,
    )


def _ops(payload: int = M):
    return w1.generate_w1_ops(
        w1.W1Config(tp_size=RANKS, layers=1, steps=1, allreduce_bytes=payload)
    )


# -- the ROUNDUP law itself -----------------------------------------------------


def test_consumed_credit_matches_the_r08_worked_example():
    # UEC11-FC-R08's own worked example: 4096-B payload + 256-B overhead
    # against 512-B cells => 4608 B of credit. The overhead term is S3's
    # law (FC-R09); here the packet size 4096+256 = 4352 is composed by
    # hand and the ROUNDUP arithmetic is what executes.
    assert 4096 + 256 == 4352
    assert l0_tfc.consumed_credit_bytes(4352, Fraction(512)) == Fraction(4608)
    assert l0_tfc.consumed_credit_bytes(2048, Fraction(9216)) == Fraction(9216)
    assert l0_tfc.consumed_credit_bytes(2048, Fraction(768)) == Fraction(2304)
    # c == cell and cell | c both give cq == c (no rounding up beyond).
    assert l0_tfc.consumed_credit_bytes(2048, Fraction(2048)) == Fraction(2048)
    assert l0_tfc.consumed_credit_bytes(2048, Fraction(256)) == Fraction(2048)


def test_credit_efficiency_is_one_iff_chunk_aligned():
    # c/cq == 1 exactly on the zero-waste boundary, < 1 strictly off it.
    for cell in (Fraction(256), Fraction(512), Fraction(1024), Fraction(2048)):
        assert C % cell == 0  # the boundary premise
        assert l0_tfc.credit_efficiency(C, cell) == Fraction(1)
    assert l0_tfc.credit_efficiency(C, Fraction(9216)) == Fraction(2, 9)
    assert l0_tfc.credit_efficiency(C, Fraction(768)) == Fraction(8, 9)


# -- the quantized identity, waste regime ---------------------------------------


def test_quantized_rate_identity_waste_regime():
    # cell = 9216 (R08's named per-packet strategy): cq = 9216,
    # efficiency 2/9, data rate min(64, (2/9)*32) = 64/9 B/ns.
    infra = _infra(cell=Fraction(9216))
    cq = l0_tfc.consumed_credit_bytes(C, Fraction(9216))
    assert cq == Fraction(9216)
    efficiency = Fraction(C) / cq
    assert efficiency == Fraction(2, 9)
    expected_rate = min(B, efficiency * (W / RTT))
    assert expected_rate == Fraction(64, 9)
    assert l0_tfc.effective_rate_for_chunk(infra, C) == Fraction(64, 9)


def test_completion_time_identity_waste_regime():
    # t = T / min(B, (c/cq)*W/(L+L_cr)) + 2*(r-1)*L = 28672/(64/9) + 2800
    # = 4032 + 2800 = 6832 ns exactly.
    expected = T / Fraction(64, 9) + 2 * (RANKS - 1) * L
    assert expected == Fraction(6832)
    assert (
        l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, _infra(cell=Fraction(9216)))
        == Fraction(6832)
    )
    # A second waste point (cell 768 = 3 units): cq = 2304, eff = 8/9,
    # rate = 256/9, t = 28672*9/256 + 2800 = 1008 + 2800 = 3808 ns.
    expected768 = T / Fraction(256, 9) + 2 * (RANKS - 1) * L
    assert expected768 == Fraction(3808)
    assert (
        l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, _infra(cell=Fraction(768)))
        == Fraction(3808)
    )


def test_quantized_admission_invariant_holds_with_equality_iff_gated():
    # UEC11-FC-R08's structural bound: in-flight DATA bytes Rd*RTT <=
    # (c/cq)*W; credit bytes in flight never exceed W. In the waste
    # regime the quantized cap gates, so equality holds on the data side
    # while the credit side stays strictly below W.
    infra = _infra(cell=Fraction(9216))
    data_in_flight = l0_tfc.admission_invariant_for_chunk(infra, C)
    bound = Fraction(2, 9) * W
    assert data_in_flight == Fraction(25600, 9) == bound  # window-limited
    # The credit-side (R02) invariant is unchanged: Reff*RTT <= W.
    assert l0_tfc.admission_invariant(infra) == W


# -- the zero-waste convergence boundary ----------------------------------------


def test_aligned_chunk_converges_to_the_r02_identity_exactly():
    # c == 0 (mod cell) => cq = c => efficiency 1 => the quantized identity
    # IS the landed R02 identity, for every aligned cell in the domain.
    r02_infra = _infra(cell=None)
    for cell in (256, 512, 1024, 2048):
        aligned = _infra(cell=Fraction(cell))
        assert C % cell == 0
        assert l0_tfc.consumed_credit_bytes(C, Fraction(cell)) == C
        assert (
            l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, aligned)
            == l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, r02_infra)
            == R02_TIME
            == Fraction(3696)  # the flagship golden literal
        )
    # And the largest aligned cell (2048 == c) is the knife edge: the next
    # domain rung up (2304 > c) already wastes — one cell granted per
    # packet, cq = 2304 > c = 2048.
    assert l0_tfc.consumed_credit_bytes(C, Fraction(2304)) == Fraction(2304)
    assert l0_tfc.credit_efficiency(C, Fraction(2304)) == Fraction(8, 9)


def test_declared_cell_is_opt_in_and_undeclared_runs_the_r02_identity():
    # A topology without tfc.dest_cell_size executes the flagship identity
    # only — the chunk-aware rate path must be identity-preserving there.
    none_infra = _infra(cell=None)
    for chunk in (2048, 1024, 333):  # alignment irrelevant without a cell
        assert l0_tfc.effective_rate_for_chunk(none_infra, chunk) == (
            l0_tfc.effective_rate(none_infra)
        )
    assert (
        l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, none_infra)
        == l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, _infra(cell=Fraction(256)))
    )


def test_waste_regime_delta_against_r02_is_the_declared_term():
    # t_cell - t_R02 = T*(1/Rd - 1/R02_rate) = T*(9/64 - 1/32) = 28672*7/64
    # = 3136 ns exactly — the quantization-waste term, derived here.
    expected_gap = T * (1 / Fraction(64, 9) - 1 / R02_RATE)
    assert expected_gap == Fraction(3136)
    gap = l0_tfc.ring_allreduce_time_tfc_ns(
        M, RANKS, _infra(cell=Fraction(9216))
    ) - l0_tfc.ring_allreduce_time_tfc_ns(M, RANKS, _infra(cell=None))
    assert gap == expected_gap


# -- the observable change: O-CCT moves, O-CONSERVATION does not ----------------


def test_execute_moves_cct_and_conserves_bytes_in_the_waste_regime():
    cell_result = l0_tfc.execute(_ops(), _infra(cell=Fraction(9216)))
    r02_result = l0_tfc.execute(_ops(), _infra(cell=None))
    # A cell gates rate, never byte count: wire ledgers identical.
    assert (
        cell_result["observables"]["O-CONSERVATION"]
        == r02_result["observables"]["O-CONSERVATION"]
    )
    assert cell_result["observables"]["O-CONSERVATION"][
        "total_wire_bytes_exact"
    ] == str(Fraction(2 * (RANKS - 1) * M))
    # O-CCT carries the quantized mean and both bindings' provenance.
    cct = cell_result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(6832))
    tfc = cct["tfc"]
    assert tfc["cell"]["requirement_id"] == "UEC11-FC-R08"
    assert tfc["cell"]["binding_id"] == "BIND-UEC11-FC-R08-L0TFC"
    assert tfc["cell"]["dest_cell_size_bytes"] == 9216
    assert tfc["cell"]["chunk_bytes"] == C
    assert tfc["cell"]["credit_used_bytes_exact"] == str(Fraction(9216))
    assert tfc["cell"]["credit_efficiency_exact"] == str(Fraction(2, 9))
    assert tfc["cell"]["effective_data_rate_bytes_per_ns_exact"] == str(
        Fraction(64, 9)
    )
    assert tfc["window_limited"] is True  # the R02 window still gates
    binding_ids = [
        b["binding_id"] for b in cell_result["requirement_bindings"]
    ]
    assert binding_ids == [
        "BIND-UEC11-FC-R02-L0TFC",
        "BIND-UEC11-FC-R08-L0TFC",
    ]
    assert cell_result["backend"]["tfc_dest_cell_size_bytes"] == 9216
    # Without a declared cell the flagship shape: no cell block, one binding.
    r02_cct = r02_result["observables"]["O-CCT"]
    assert "cell" not in r02_cct["tfc"]
    assert r02_result["requirement_bindings"] == [
        {
            "binding_id": "BIND-UEC11-FC-R02-L0TFC",
            "requirement_id": "UEC11-FC-R02",
            "disposition": "simulated_behavior",
            "credit_unit_requirement_id": "UEC11-FC-R05",
        }
    ]
    assert "tfc_dest_cell_size_bytes" not in r02_result["backend"]


# -- load-time semantics: the R07-cited domain -----------------------------------


def test_cell_domain_constants_cite_r07():
    # The validated domain's values are spec-derived (UEC11-FC-R07): an
    # integral 256-B multiple in 256..9216 B. Named constants, not magic.
    assert l0_tfc.TFC_DEST_CELL_SIZE_MIN_BYTES == 256
    assert l0_tfc.TFC_DEST_CELL_SIZE_MAX_BYTES == 9216
    assert l0_tfc.TFC_DEST_CELL_SIZE_GRANULARITY_BYTES == 256


def test_loader_rejects_out_of_domain_cells():
    # Out-of-domain cells are rejected at load time citing UEC11-FC-R07:
    # below the minimum, above the maximum, not a 256-B multiple, and
    # non-integral.
    base = {
        "topology_id": "t",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
        "tfc": {
            "window_bytes": 12800,
            "credit_return_latency_ns": 200,
        },
    }
    for bad in (128, 9472, 1000, 253.5, 0, -256):
        with pytest.raises(ValueError, match="UEC11-FC-R07"):
            l0_tfc.load_tfc_config(
                {**base, "tfc": {**base["tfc"], "dest_cell_size": bad}}
            )


def test_loader_accepts_the_domain_boundaries():
    # 256 (the spec default cell) and 9216 (the per-packet strategy) are
    # the closed boundaries of the supported set — both load.
    base = {
        "topology_id": "t",
        "ranks": 8,
        "link": {"bytes_per_ns": 64, "hop_latency_ns": 200},
        "tfc": {"window_bytes": 12800, "credit_return_latency_ns": 200},
    }
    for good in (256, 768, 9216):
        config = l0_tfc.load_tfc_config(
            {**base, "tfc": {**base["tfc"], "dest_cell_size": good}}
        )
        assert config.tfc_dest_cell_size == Fraction(good)
    absent = l0_tfc.load_tfc_config(dict(base))
    assert absent.tfc_dest_cell_size is None


# -- run path: the evidence manifest executes end-to-end -------------------------


def test_run_path_dispatch_determinism_and_v2_stamp(tmp_path):
    from essun.orchestrator import runs as orchestrator

    manifest = "experiments/vertical_slice/w1_decode_tfc_cell.yaml"
    first = orchestrator.run_experiment(manifest, results_root=tmp_path / "a")
    second = orchestrator.run_experiment(manifest, results_root=tmp_path / "b")
    assert first["run_id"] == second["run_id"]  # deterministic, content-addressed
    record = orchestrator.EvidenceStore(tmp_path / "a").get_run(first["run_id"])
    # The evidence run is v2-stamped with the declared dimensions block.
    assert record["evidence_schema_version"] == 2
    assert record["calibration_target"] == []
    assert record["held_out"] == {"held_out": False, "scope": _HELD_OUT_SCOPE}
    cct = first["observations"]["observables"]["O-CCT"]
    # 6 ops x 16384 B (layers 2 x steps 3): every chunk aligned to nothing
    # under cell 9216 -> mean is the waste-regime literal 6832 ns.
    assert cct["ops"] == 6
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(6832))
    assert first["observations"]["requirement_bindings"][-1] == {
        "binding_id": "BIND-UEC11-FC-R08-L0TFC",
        "requirement_id": "UEC11-FC-R08",
        "disposition": "simulated_behavior",
        "cell_size_range_requirement_id": "UEC11-FC-R07",
        "credit_unit_requirement_id": "UEC11-FC-R05",
    }
    claims = (tmp_path / "a" / "claims_index.jsonl").read_text().strip()
    assert "C-UEC-TFC-R08" in claims and first["run_id"] in claims


_HELD_OUT_SCOPE = (
    "no data withheld; all inputs derive from the identity (E0)"
)
