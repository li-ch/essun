"""Role-disaggregated serving pools — generic two-pool decode step.

Models one decode step across TWO accelerator pools with different roles
(e.g. an attention-role pool and an expert/FFN-role pool — attention/FFN
disaggregation), each pool with its own card parameters and rank count,
joined by one scale-up fabric. The flexible ``ranks_attention`` :
``ranks_expert`` ratio is the point of the model: callers sweep it.

Serial identity (A-SERVE-DISAG; the disaggregated sibling of
A-SERVE-SER — no overlap, lower bound on performance):

    attention_compute_ns = batch * attention_flops_per_token / (ranks_A * card_A.flops_per_ns)
    attention_kv_ns      = batch * context * kv_bytes_per_token * h / (ranks_A * card_A.hbm_bytes_per_ns)
    kv_remote_ns         = exchange_ns(batch * context * kv_bytes_per_token * (1-h) / ranks_A)
    expert_weights_ns    = weight_bytes / (ranks_B * card_B.hbm_bytes_per_ns)
    expert_compute_ns    = batch * active_flops_per_token / (ranks_B * card_B.flops_per_ns)
    exchange_ns          = 2 * exchange_ns(batch * exchange_bytes_per_token)   [dispatch + combine]

    step_ns = sum of the six terms

Role placement assumptions (named, not silent): the attention pool holds
the KV cache; the expert pool holds the model weights shard; one
dispatch + one combine cross the pools per step at the fabric callable's
identity. Remote-KV fetch uses the SAME exchange callable (one transfer
of the step's aggregate remote bytes). No capacity checks, no
congestion, no overlap — same honesty scope as the roofline module.

Evidence label: [IMPLEMENTED_UNVERIFIED] — exact identities and
validation tested; no claim about real disaggregated serving systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from essun.serving.roofline import CardParameters, _frac, _NS_PER_S


@dataclass(frozen=True)
class DisaggregatedDecodeModel:
    """Two-pool decode free parameters (caller-supplied role split)."""

    context_tokens: int
    kv_bytes_per_token: int
    attention_flops_per_token: int
    weight_bytes: int
    active_flops_per_token: int
    exchange_bytes_per_token: int

    def __post_init__(self) -> None:
        if int(self.context_tokens) < 1:
            raise ValueError(f"context_tokens must be >= 1, got {self.context_tokens}")
        if int(self.kv_bytes_per_token) < 0:
            raise ValueError(f"kv_bytes_per_token must be >= 0, got {self.kv_bytes_per_token}")
        if int(self.attention_flops_per_token) < 0:
            raise ValueError(
                f"attention_flops_per_token must be >= 0, got {self.attention_flops_per_token}"
            )
        if int(self.weight_bytes) < 1:
            raise ValueError(f"weight_bytes must be >= 1, got {self.weight_bytes}")
        if int(self.active_flops_per_token) < 1:
            raise ValueError(
                f"active_flops_per_token must be >= 1, got {self.active_flops_per_token}"
            )
        if int(self.exchange_bytes_per_token) < 1:
            raise ValueError(
                f"exchange_bytes_per_token must be >= 1, got {self.exchange_bytes_per_token}"
            )

    def to_dict(self) -> dict:
        return {
            "context_tokens": int(self.context_tokens),
            "kv_bytes_per_token": int(self.kv_bytes_per_token),
            "attention_flops_per_token": int(self.attention_flops_per_token),
            "weight_bytes": int(self.weight_bytes),
            "active_flops_per_token": int(self.active_flops_per_token),
            "exchange_bytes_per_token": int(self.exchange_bytes_per_token),
        }


def decode_step_terms_ns(
    card_attention: CardParameters,
    card_expert: CardParameters,
    model: DisaggregatedDecodeModel,
    *,
    ranks_attention: int,
    ranks_expert: int,
    batch: int,
    kv_hit_rate,
    exchange_ns: Callable[[Fraction], Fraction],
) -> dict[str, Fraction]:
    """The six two-pool decode terms (exact Fractions)."""
    if int(ranks_attention) < 1:
        raise ValueError(f"ranks_attention must be >= 1, got {ranks_attention}")
    if int(ranks_expert) < 1:
        raise ValueError(f"ranks_expert must be >= 1, got {ranks_expert}")
    if int(batch) < 1:
        raise ValueError(f"batch must be >= 1, got {batch}")
    hit = _frac(kv_hit_rate)
    if not (0 <= hit <= 1):
        raise ValueError(f"kv_hit_rate must be within [0, 1], got {kv_hit_rate}")

    attention_compute = (
        Fraction(model.attention_flops_per_token * batch, ranks_attention)
        / card_attention.flops_per_ns
    )
    kv_total = Fraction(batch * model.context_tokens * model.kv_bytes_per_token)
    attention_kv = (kv_total * hit / ranks_attention) / card_attention.hbm_bytes_per_ns
    remote_bytes = kv_total * (1 - hit) / ranks_attention
    kv_remote = exchange_ns(remote_bytes) if remote_bytes > 0 else Fraction(0)
    expert_weights = (
        Fraction(model.weight_bytes, ranks_expert) / card_expert.hbm_bytes_per_ns
    )
    expert_compute = (
        Fraction(model.active_flops_per_token * batch, ranks_expert)
        / card_expert.flops_per_ns
    )
    exchange = 2 * exchange_ns(Fraction(model.exchange_bytes_per_token * batch))
    return {
        "attention_compute_ns": attention_compute,
        "attention_kv_ns": attention_kv,
        "kv_remote_ns": kv_remote,
        "expert_weights_ns": expert_weights,
        "expert_compute_ns": expert_compute,
        "exchange_ns": exchange,
    }


def decode_step_ns(
    card_attention: CardParameters,
    card_expert: CardParameters,
    model: DisaggregatedDecodeModel,
    *,
    ranks_attention: int,
    ranks_expert: int,
    batch: int,
    kv_hit_rate,
    exchange_ns: Callable[[Fraction], Fraction],
) -> Fraction:
    """One two-pool decode step under the serial disaggregated identity."""
    terms = decode_step_terms_ns(
        card_attention, card_expert, model,
        ranks_attention=ranks_attention, ranks_expert=ranks_expert,
        batch=batch, kv_hit_rate=kv_hit_rate, exchange_ns=exchange_ns,
    )
    return sum(terms.values(), start=Fraction(0))


def decode_slo_report(
    card_attention: CardParameters,
    card_expert: CardParameters,
    model: DisaggregatedDecodeModel,
    *,
    ranks_attention: int,
    ranks_expert: int,
    batch: int,
    kv_hit_rate,
    exchange_ns: Callable[[Fraction], Fraction],
    tpot_limit_ns,
) -> dict:
    """SLO-DECODE-DISAG report: TPOT, per-card tok/s over BOTH pools, feasibility."""
    limit = _frac(tpot_limit_ns)
    if limit <= 0:
        raise ValueError(f"tpot_limit_ns must be > 0, got {tpot_limit_ns}")
    step = decode_step_ns(
        card_attention, card_expert, model,
        ranks_attention=ranks_attention, ranks_expert=ranks_expert,
        batch=batch, kv_hit_rate=kv_hit_rate, exchange_ns=exchange_ns,
    )
    terms = decode_step_terms_ns(
        card_attention, card_expert, model,
        ranks_attention=ranks_attention, ranks_expert=ranks_expert,
        batch=batch, kv_hit_rate=kv_hit_rate, exchange_ns=exchange_ns,
    )
    total_ranks = ranks_attention + ranks_expert
    tps = Fraction(batch) / (step / _NS_PER_S) / total_ranks
    return {
        "kind": "serving_roofline",
        "observable": "SLO-DECODE-DISAG",
        "identity": "serial_two_pool",
        "card_attention": card_attention.to_dict(),
        "card_expert": card_expert.to_dict(),
        "model": model.to_dict(),
        "ranks_attention": int(ranks_attention),
        "ranks_expert": int(ranks_expert),
        "batch": int(batch),
        "kv_hit_rate_exact": str(_frac(kv_hit_rate)),
        "terms_exact": {name: str(value) for name, value in terms.items()},
        "terms_ns": {name: float(value) for name, value in terms.items()},
        "tpot_ns_exact": str(step),
        "tpot_ns": float(step),
        "tpot_limit_ns_exact": str(limit),
        "slo_feasible": bool(step <= limit),
        "headroom_ns_exact": str(limit - step),
        "per_card_tokens_per_s_exact": str(tps),
        "per_card_tokens_per_s": float(tps),
    }
