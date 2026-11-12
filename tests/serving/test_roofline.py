"""Serving roofline composition tests (identity math + validation).

Hand-computed cases only: every expected value below is derived in the
test from first principles (exact Fractions), not by running the module
under test twice.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from essun.serving import roofline


def fixed_fabric(collective_latency_ns=100, p2p_latency_ns=10):
    """Deterministic test fabric: payload/1 byte-per-ns + fixed latency."""
    return (
        lambda payload: Fraction(payload) / 1 + collective_latency_ns,
        lambda payload: Fraction(payload) / 1 + p2p_latency_ns,
    )


def base_card():
    # 1 FLOP/ns, 1 byte/ns HBM: units chosen so hand math is trivial.
    return roofline.CardParameters(flops_per_ns=1, hbm_bytes_per_ns=1)


def base_decode_model():
    return roofline.DecodeTokenModel(
        active_flops_per_token=64,
        weight_bytes_per_token=512,
        kv_bytes_per_token=64,
        comm_bytes_per_token=64,
        comm_ops_per_token=2,
    )


class TestDecodeStepTerms:
    def test_serial_identity_hand_computed(self):
        collective_ns, p2p_ns = fixed_fabric()
        terms = roofline.decode_step_terms_ns(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=1,
            kv_hit_rate=1,
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
        )
        # compute: 64 / (8 * 1) = 8 ns
        assert terms["compute_ns"] == Fraction(8)
        # weights: (512 / 8) / 1 = 64 ns
        assert terms["weights_ns"] == Fraction(64)
        # kv local: (1 * 64 * 1 / 8) / 1 = 8 ns
        assert terms["kv_local_ns"] == Fraction(8)
        # no remote traffic at h=1: p2p never called, term exactly 0
        assert terms["kv_remote_ns"] == Fraction(0)
        # comm: 2 ops x (64/1 + 100) = 328 ns
        assert terms["comm_ns"] == Fraction(328)

    def test_serial_step_sums_terms(self):
        collective_ns, p2p_ns = fixed_fabric()
        step = roofline.decode_step_ns(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=1,
            kv_hit_rate=1,
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
            overlap="serial",
        )
        assert step == Fraction(8 + 64 + 8 + 0 + 328)

    def test_kv_hit_rate_splits_local_and_remote(self):
        collective_ns, p2p_ns = fixed_fabric()
        terms = roofline.decode_step_terms_ns(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=2,
            kv_hit_rate=Fraction(1, 2),
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
        )
        # local: (2 * 64 * 1/2 / 8) / 1 = 8 ns
        assert terms["kv_local_ns"] == Fraction(8)
        # remote bytes per rank: 2 * 64 * 1/2 / 8 = 8 B; p2p: 8/1 + 10 = 18 ns
        assert terms["kv_remote_ns"] == Fraction(18)

    def test_overlap_identity_takes_max(self):
        collective_ns, p2p_ns = fixed_fabric()
        step = roofline.decode_step_ns(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=1,
            kv_hit_rate=1,
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
            overlap="comm_compute_overlap",
        )
        # local side: 8 + 64 + 8 + 0 = 80; comm side: 328 -> max = 328
        assert step == Fraction(328)

    def test_context_scales_kv_read_and_attention_adds_compute(self):
        # Every decode step attends over the request's WHOLE context:
        # KV read = context * kv_bytes_per_token; attention flops add to compute.
        collective_ns, p2p_ns = fixed_fabric()
        model = roofline.DecodeTokenModel(
            active_flops_per_token=64,
            weight_bytes_per_token=512,
            kv_bytes_per_token=64,
            comm_bytes_per_token=64,
            comm_ops_per_token=2,
            context_tokens=1000,
            attention_flops_per_token=4 * 1000 * 8,
        )
        terms = roofline.decode_step_terms_ns(
            base_card(), model,
            ranks=8, batch=1, kv_hit_rate=1,
            collective_ns=collective_ns, p2p_ns=p2p_ns,
        )
        # compute: (64 + 32000) / 8 = 4008 ns
        assert terms["compute_ns"] == Fraction(4008)
        # kv local: (1 * 1000 * 64 * 1 / 8) / 1 = 8000 ns
        assert terms["kv_local_ns"] == Fraction(8000)

    def test_context_remote_bytes_feed_p2p(self):
        collective_ns, p2p_ns = fixed_fabric()
        model = roofline.DecodeTokenModel(
            active_flops_per_token=64,
            weight_bytes_per_token=512,
            kv_bytes_per_token=64,
            comm_bytes_per_token=64,
            comm_ops_per_token=0,
            context_tokens=1000,
        )
        terms = roofline.decode_step_terms_ns(
            base_card(), model,
            ranks=8, batch=2, kv_hit_rate=Fraction(1, 2),
            collective_ns=collective_ns, p2p_ns=p2p_ns,
        )
        # remote bytes: 2 * 1000 * 64 * 1/2 / 8 = 8000 B; p2p: 8000/1 + 10
        assert terms["kv_remote_ns"] == Fraction(8010)

    def test_zero_context_rejected(self):
        with pytest.raises(ValueError, match="context_tokens"):
            roofline.DecodeTokenModel(
                active_flops_per_token=64,
                weight_bytes_per_token=512,
                kv_bytes_per_token=64,
                comm_bytes_per_token=64,
                context_tokens=0,
            )

    def test_batch_scales_compute_and_comm_not_weights(self):
        # A decode STEP processes `batch` tokens: compute and the collective
        # payload scale with batch; the weight read is once per step.
        collective_ns, p2p_ns = fixed_fabric()
        one = roofline.decode_step_terms_ns(
            base_card(), base_decode_model(),
            ranks=8, batch=1, kv_hit_rate=1,
            collective_ns=collective_ns, p2p_ns=p2p_ns,
        )
        two = roofline.decode_step_terms_ns(
            base_card(), base_decode_model(),
            ranks=8, batch=2, kv_hit_rate=1,
            collective_ns=collective_ns, p2p_ns=p2p_ns,
        )
        assert two["compute_ns"] == 2 * one["compute_ns"]
        assert two["weights_ns"] == one["weights_ns"]
        # comm payload 64 -> 128 bytes per op: 2*(128+100) = 456 vs 328
        assert two["comm_ns"] == Fraction(456)
        assert one["comm_ns"] == Fraction(328)

    def test_unknown_overlap_identity_rejected(self):
        collective_ns, p2p_ns = fixed_fabric()
        with pytest.raises(ValueError, match="overlap identity"):
            roofline.decode_step_ns(
                base_card(),
                base_decode_model(),
                ranks=8,
                batch=1,
                kv_hit_rate=1,
                collective_ns=collective_ns,
                p2p_ns=p2p_ns,
                overlap="partial",
            )


class TestThroughputAndSLO:
    def test_per_card_tokens_per_s_exact(self):
        # step 408 ns, batch 1, ranks 8: 1 / (408e-9 * 8) tokens/s/card
        step = Fraction(408)
        tps = roofline.per_card_tokens_per_s(step, batch=1, ranks=8)
        expected = Fraction(1) / (Fraction(408, 10**9) * 8)
        assert tps == expected

    def test_slo_boundary_exact_equality_is_feasible(self):
        collective_ns, p2p_ns = fixed_fabric()
        report = roofline.decode_slo_report(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=1,
            kv_hit_rate=1,
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
            tpot_limit_ns=408,
            overlap="serial",
        )
        assert report["tpot_ns_exact"] == "408"
        assert report["slo_feasible"] is True
        assert report["headroom_ns_exact"] == "0"

    def test_slo_miss_reports_negative_headroom(self):
        collective_ns, p2p_ns = fixed_fabric()
        report = roofline.decode_slo_report(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=1,
            kv_hit_rate=1,
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
            tpot_limit_ns=407,
            overlap="serial",
        )
        assert report["slo_feasible"] is False
        assert Fraction(report["headroom_ns_exact"]) == Fraction(-1)

    def test_report_carries_exact_and_float_and_params(self):
        collective_ns, p2p_ns = fixed_fabric()
        report = roofline.decode_slo_report(
            base_card(),
            base_decode_model(),
            ranks=8,
            batch=2,
            kv_hit_rate="0.5",
            collective_ns=collective_ns,
            p2p_ns=p2p_ns,
            tpot_limit_ns=500,
            overlap="serial",
        )
        assert report["kind"] == "serving_roofline"
        assert report["observable"] == "SLO-DECODE"
        assert report["identity"] == "serial"
        assert report["batch"] == 2
        assert report["ranks"] == 8
        assert report["kv_hit_rate_exact"] == "1/2"
        assert isinstance(report["tpot_ns"], float)
        assert set(report["terms_exact"]) == {
            "compute_ns", "weights_ns", "kv_local_ns", "kv_remote_ns", "comm_ns"
        }

    def test_report_deterministic_and_canonicalizable(self):
        from essun.evidence.store import canonical_json

        collective_ns, p2p_ns = fixed_fabric()
        kwargs = dict(
            ranks=8, batch=3, kv_hit_rate=0.95,
            collective_ns=collective_ns, p2p_ns=p2p_ns,
            tpot_limit_ns=1000, overlap="serial",
        )
        first = roofline.decode_slo_report(
            base_card(), base_decode_model(), **kwargs
        )
        second = roofline.decode_slo_report(
            base_card(), base_decode_model(), **kwargs
        )
        assert first == second
        assert (
            canonical_json(first) == canonical_json(second)
        )  # no floats drift the canonical form apart unexpectedly


class TestPrefill:
    def test_ttft_serial_hand_computed(self):
        collective_ns, p2p_ns = fixed_fabric()
        model = roofline.PrefillModel(
            prefill_flops=2 * 100 * 150000,   # 30,000,000
            weight_bytes=512,
            chunks=2,
            comm_bytes_per_chunk=64,
        )
        ttft = roofline.prefill_ttft_ns(
            base_card(), model, ranks=8, collective_ns=collective_ns
        )
        # compute: 30e6 / 8 = 3,750,000; weights: 512/8 = 64; comm: 2*(64+100) = 328
        assert ttft == Fraction(3_750_000 + 64 + 328)

    def test_prefill_slo_report(self):
        collective_ns, p2p_ns = fixed_fabric()
        model = roofline.PrefillModel(
            prefill_flops=2 * 100 * 150000,
            weight_bytes=512,
            chunks=2,
            comm_bytes_per_chunk=64,
        )
        report = roofline.prefill_slo_report(
            base_card(), model, ranks=8, collective_ns=collective_ns,
            ttft_limit_ns=3_750_392,
        )
        assert report["observable"] == "SLO-PREFILL"
        assert report["slo_feasible"] is True


class TestValidation:
    def test_kv_hit_rate_above_one_rejected(self):
        collective_ns, p2p_ns = fixed_fabric()
        with pytest.raises(ValueError, match="kv_hit_rate"):
            roofline.decode_step_terms_ns(
                base_card(), base_decode_model(),
                ranks=8, batch=1, kv_hit_rate=1.5,
                collective_ns=collective_ns, p2p_ns=p2p_ns,
            )

    def test_negative_kv_hit_rate_rejected(self):
        collective_ns, p2p_ns = fixed_fabric()
        with pytest.raises(ValueError, match="kv_hit_rate"):
            roofline.decode_step_terms_ns(
                base_card(), base_decode_model(),
                ranks=8, batch=1, kv_hit_rate=-0.1,
                collective_ns=collective_ns, p2p_ns=p2p_ns,
            )

    def test_zero_batch_rejected(self):
        collective_ns, p2p_ns = fixed_fabric()
        with pytest.raises(ValueError, match="batch"):
            roofline.decode_step_terms_ns(
                base_card(), base_decode_model(),
                ranks=8, batch=0, kv_hit_rate=1,
                collective_ns=collective_ns, p2p_ns=p2p_ns,
            )

    def test_zero_ranks_rejected(self):
        collective_ns, p2p_ns = fixed_fabric()
        with pytest.raises(ValueError, match="ranks"):
            roofline.decode_step_terms_ns(
                base_card(), base_decode_model(),
                ranks=0, batch=1, kv_hit_rate=1,
                collective_ns=collective_ns, p2p_ns=p2p_ns,
            )

    def test_zero_card_flops_rejected(self):
        with pytest.raises(ValueError, match="flops_per_ns"):
            roofline.CardParameters(flops_per_ns=0, hbm_bytes_per_ns=1)

    def test_zero_card_hbm_rejected(self):
        with pytest.raises(ValueError, match="hbm_bytes_per_ns"):
            roofline.CardParameters(flops_per_ns=1, hbm_bytes_per_ns=0)

    def test_degenerate_decode_model_rejected(self):
        with pytest.raises(ValueError, match="active_flops_per_token"):
            roofline.DecodeTokenModel(
                active_flops_per_token=0,
                weight_bytes_per_token=512,
                kv_bytes_per_token=64,
                comm_bytes_per_token=64,
            )

    def test_degenerate_prefill_model_rejected(self):
        with pytest.raises(ValueError, match="chunks"):
            roofline.PrefillModel(
                prefill_flops=100, weight_bytes=512, chunks=0,
                comm_bytes_per_chunk=64,
            )
