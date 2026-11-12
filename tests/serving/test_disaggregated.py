"""Role-disaggregated two-pool decode step tests (identity math + validation)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from essun.serving import disaggregated


def fabric(exchange_latency_ns=10):
    # deterministic test fabric: payload / 1 byte-per-ns + fixed latency
    return lambda payload: Fraction(payload) / 1 + exchange_latency_ns


def pools():
    attention_card = disaggregated.CardParameters(flops_per_ns=1, hbm_bytes_per_ns=1)
    expert_card = disaggregated.CardParameters(flops_per_ns=2, hbm_bytes_per_ns=2)
    return attention_card, expert_card


def model():
    return disaggregated.DisaggregatedDecodeModel(
        context_tokens=1000,
        kv_bytes_per_token=64,
        attention_flops_per_token=4 * 1000 * 8,     # 32000
        weight_bytes=512,
        active_flops_per_token=64,
        exchange_bytes_per_token=32,                # dispatch + combine payload
    )


class TestTwoPoolIdentity:
    def test_terms_hand_computed(self):
        attention_card, expert_card = pools()
        terms = disaggregated.decode_step_terms_ns(
            attention_card, expert_card, model(),
            ranks_attention=8, ranks_expert=8, batch=1,
            kv_hit_rate=1, exchange_ns=fabric(),
        )
        # attention compute: 1 * 32000 / 8 = 4000 ns
        assert terms["attention_compute_ns"] == Fraction(4000)
        # KV read: 1 * 1000 * 64 * 1 / 8 = 8000 ns
        assert terms["attention_kv_ns"] == Fraction(8000)
        # no remote KV at h=1
        assert terms["kv_remote_ns"] == Fraction(0)
        # weight shard: 512 / (8 * 2) = 32 ns
        assert terms["expert_weights_ns"] == Fraction(32)
        # expert compute: 1 * 64 / (8 * 2) = 4 ns
        assert terms["expert_compute_ns"] == Fraction(4)
        # exchange: dispatch + combine = 2 x (32/1 + 10) = 84 ns
        assert terms["exchange_ns"] == Fraction(84)

    def test_serial_step_sums_terms(self):
        attention_card, expert_card = pools()
        step = disaggregated.decode_step_ns(
            attention_card, expert_card, model(),
            ranks_attention=8, ranks_expert=8, batch=1,
            kv_hit_rate=1, exchange_ns=fabric(),
        )
        assert step == Fraction(4000 + 8000 + 0 + 32 + 4 + 84)

    def test_ratio_changes_pool_terms_independently(self):
        attention_card, expert_card = pools()
        base = disaggregated.decode_step_terms_ns(
            attention_card, expert_card, model(),
            ranks_attention=8, ranks_expert=8, batch=1,
            kv_hit_rate=1, exchange_ns=fabric(),
        )
        shifted = disaggregated.decode_step_terms_ns(
            attention_card, expert_card, model(),
            ranks_attention=16, ranks_expert=4, batch=1,
            kv_hit_rate=1, exchange_ns=fabric(),
        )
        # doubling attention ranks halves the attention-side terms
        assert shifted["attention_kv_ns"] * 2 == base["attention_kv_ns"]
        # halving expert ranks doubles the expert-side terms
        assert shifted["expert_weights_ns"] == 2 * base["expert_weights_ns"]

    def test_report_carries_exact_terms_and_feasibility(self):
        attention_card, expert_card = pools()
        report = disaggregated.decode_slo_report(
            attention_card, expert_card, model(),
            ranks_attention=8, ranks_expert=8, batch=1,
            kv_hit_rate="0.5", exchange_ns=fabric(),
            tpot_limit_ns=12130,
        )
        assert report["observable"] == "SLO-DECODE-DISAG"
        # remote KV: 1 * 1000 * 64 * 0.5 / 8 = 4000 B -> 4000/1 + 10
        assert Fraction(report["terms_exact"]["kv_remote_ns"]) == Fraction(4010)
        # serial sum: 4000 + 4000 + 4010 + 32 + 4 + 84 = 12130 — exactly the limit
        assert Fraction(report["tpot_ns_exact"]) == Fraction(12130)
        assert report["slo_feasible"] is True


class TestValidation:
    def test_zero_pool_ranks_rejected(self):
        attention_card, expert_card = pools()
        with pytest.raises(ValueError, match="ranks_attention"):
            disaggregated.decode_step_terms_ns(
                attention_card, expert_card, model(),
                ranks_attention=0, ranks_expert=8, batch=1,
                kv_hit_rate=1, exchange_ns=fabric(),
            )

    def test_bad_hit_rate_rejected(self):
        attention_card, expert_card = pools()
        with pytest.raises(ValueError, match="kv_hit_rate"):
            disaggregated.decode_step_terms_ns(
                attention_card, expert_card, model(),
                ranks_attention=8, ranks_expert=8, batch=1,
                kv_hit_rate=2,
                exchange_ns=fabric(),
            )

    def test_degenerate_model_rejected(self):
        with pytest.raises(ValueError, match="exchange_bytes_per_token"):
            disaggregated.DisaggregatedDecodeModel(
                context_tokens=10, kv_bytes_per_token=64,
                attention_flops_per_token=100, weight_bytes=512,
                active_flops_per_token=64, exchange_bytes_per_token=0,
            )
