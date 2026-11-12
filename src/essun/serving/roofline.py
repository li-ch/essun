"""Serving roofline composition — SLO-constrained per-card throughput.

Composes the per-token/per-step time terms of an LLM serving step from
FREE PARAMETERS and wire-time callables wired to the analytical L0-family
identities (ring, crossbar, ...), then evaluates SLO feasibility (decode
TPOT, prefill TTFT) and per-card token throughput. Every quantity is an
exact :class:`fractions.Fraction`; no RNG, no wall-clock, no floats in
the arithmetic path (floats appear only as serialized companions).

Registered identities (anything else is rejected loudly):

* ``serial`` (A-SERVE-SER): step time is the SUM of all terms — no term
  overlaps another. Lower bound on achievable performance.
* ``comm_compute_overlap`` (A-SERVE-CAO): step time is
  ``max(compute + memory terms, communication terms)`` — the collective
  engine (DMA/fabric path) runs concurrently with compute+memory. Upper
  bound under perfect overlap.

Term identities (decode STEP: one token per request, ``batch`` concurrent
requests, ``ranks`` accelerator cards, uniform EP/TP sharding assumed).
The step processes ``batch`` tokens, so compute, KV, and communication
scale with ``batch``; the weight read is ONCE per step (amortized by
batching — the term that makes larger batches more efficient per token):

    compute_ns   = batch * active_flops_per_token / (ranks * card.flops_per_ns)
    weights_ns   = (weight_bytes_per_token / ranks) / card.hbm_bytes_per_ns
    kv_local_ns  = (batch * kv_bytes_per_token * h / ranks) / hbm_bytes_per_ns
    kv_remote_ns = p2p_ns(batch * kv_bytes_per_token * (1-h) / ranks)   [0 if no remote bytes]
    comm_ns      = comm_ops_per_token * collective_ns(batch * comm_bytes_per_token)

``kv_hit_rate`` h in [0,1] splits KV reads between local HBM (at HBM
bandwidth) and remote fetches (one point-to-point transfer per step's
remote bytes at the fabric callable's identity). A remote-bytes value of
exactly 0 skips the p2p call entirely — no latency charged for traffic
that does not exist.

Prefill TTFT (serial identity only in this slice, A-SERVE-PF):

    ttft_ns = prefill_flops / (ranks * flops_per_ns)
            + (weight_bytes / ranks) / hbm_bytes_per_ns
            + chunks * collective_ns(comm_bytes_per_chunk)

Scope honesty (named gaps, NOT silent fallbacks):

* EP dispatch/combine and attention/FFN exchanges are represented by the
  caller-supplied ``comm_bytes_per_token`` over ONE domain group; the
  all-to-all collective itself has no executable L0 backend (see the W3
  generator's declared gap). This module composes; it does not execute
  those collectives.
* Remote KV fetch is ONE p2p transfer of the step's aggregate remote
  bytes — no per-request scheduling, no congestion, no burst effects
  (L0 scope).
* Weights are assumed fully resident; batching is fixed within a step;
  no pipeline bubbles; no capacity check is performed here (callers
  model memory capacity separately when needed).

Evidence label: [IMPLEMENTED_UNVERIFIED] — exact identities and
validation tested; no claim about real serving systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

# The registered overlap identities; anything else is a named gap, not a
# silent fallback.
OVERLAP_IDENTITIES = ("serial", "comm_compute_overlap")

_NS_PER_S = Fraction(10**9)


def _frac(value) -> Fraction:
    # str() first so YAML/JSON decimals are interpreted exactly, matching
    # the platform's arithmetic policy (same rule as the L0 loaders).
    return Fraction(str(value))


@dataclass(frozen=True)
class CardParameters:
    """Per-card free parameters (never standard-derived, never measured)."""

    flops_per_ns: Fraction
    hbm_bytes_per_ns: Fraction

    def __post_init__(self) -> None:
        object.__setattr__(self, "flops_per_ns", _frac(self.flops_per_ns))
        object.__setattr__(self, "hbm_bytes_per_ns", _frac(self.hbm_bytes_per_ns))
        if self.flops_per_ns <= 0:
            raise ValueError(f"flops_per_ns must be > 0, got {self.flops_per_ns}")
        if self.hbm_bytes_per_ns <= 0:
            raise ValueError(f"hbm_bytes_per_ns must be > 0, got {self.hbm_bytes_per_ns}")

    def to_dict(self) -> dict:
        return {
            "flops_per_ns_exact": str(self.flops_per_ns),
            "flops_per_ns": float(self.flops_per_ns),
            "hbm_bytes_per_ns_exact": str(self.hbm_bytes_per_ns),
            "hbm_bytes_per_ns": float(self.hbm_bytes_per_ns),
        }


@dataclass(frozen=True)
class DecodeTokenModel:
    """Decode-step free parameters (caller-supplied model shape)."""

    active_flops_per_token: int
    weight_bytes_per_token: int
    kv_bytes_per_token: int
    comm_bytes_per_token: int
    comm_ops_per_token: int = 1

    def __post_init__(self) -> None:
        if int(self.active_flops_per_token) < 1:
            raise ValueError(
                f"active_flops_per_token must be >= 1, got {self.active_flops_per_token}"
            )
        if int(self.weight_bytes_per_token) < 1:
            raise ValueError(
                f"weight_bytes_per_token must be >= 1, got {self.weight_bytes_per_token}"
            )
        if int(self.kv_bytes_per_token) < 0:
            raise ValueError(
                f"kv_bytes_per_token must be >= 0, got {self.kv_bytes_per_token}"
            )
        if int(self.comm_bytes_per_token) < 0:
            raise ValueError(
                f"comm_bytes_per_token must be >= 0, got {self.comm_bytes_per_token}"
            )
        if int(self.comm_ops_per_token) < 0:
            raise ValueError(
                f"comm_ops_per_token must be >= 0, got {self.comm_ops_per_token}"
            )

    def to_dict(self) -> dict:
        return {
            "active_flops_per_token": int(self.active_flops_per_token),
            "weight_bytes_per_token": int(self.weight_bytes_per_token),
            "kv_bytes_per_token": int(self.kv_bytes_per_token),
            "comm_bytes_per_token": int(self.comm_bytes_per_token),
            "comm_ops_per_token": int(self.comm_ops_per_token),
        }


@dataclass(frozen=True)
class PrefillModel:
    """Prefill free parameters (TTFT identity, serial slice)."""

    prefill_flops: int
    weight_bytes: int
    chunks: int
    comm_bytes_per_chunk: int

    def __post_init__(self) -> None:
        if int(self.prefill_flops) < 1:
            raise ValueError(f"prefill_flops must be >= 1, got {self.prefill_flops}")
        if int(self.weight_bytes) < 1:
            raise ValueError(f"weight_bytes must be >= 1, got {self.weight_bytes}")
        if int(self.chunks) < 1:
            raise ValueError(f"chunks must be >= 1, got {self.chunks}")
        if int(self.comm_bytes_per_chunk) < 0:
            raise ValueError(
                f"comm_bytes_per_chunk must be >= 0, got {self.comm_bytes_per_chunk}"
            )

    def to_dict(self) -> dict:
        return {
            "prefill_flops": int(self.prefill_flops),
            "weight_bytes": int(self.weight_bytes),
            "chunks": int(self.chunks),
            "comm_bytes_per_chunk": int(self.comm_bytes_per_chunk),
        }


def _validate_common(ranks: int, batch: int, kv_hit_rate) -> Fraction:
    if int(ranks) < 1:
        raise ValueError(f"ranks must be >= 1, got {ranks}")
    if int(batch) < 1:
        raise ValueError(f"batch must be >= 1, got {batch}")
    hit = _frac(kv_hit_rate)
    if not (0 <= hit <= 1):
        raise ValueError(f"kv_hit_rate must be within [0, 1], got {kv_hit_rate}")
    return hit


def decode_step_terms_ns(
    card: CardParameters,
    model: DecodeTokenModel,
    *,
    ranks: int,
    batch: int,
    kv_hit_rate,
    collective_ns: Callable[[Fraction], Fraction],
    p2p_ns: Callable[[Fraction], Fraction],
) -> dict[str, Fraction]:
    """The five decode terms (exact Fractions) under the declared identities."""
    hit = _validate_common(ranks, batch, kv_hit_rate)
    compute = Fraction(model.active_flops_per_token * batch, ranks) / card.flops_per_ns
    weights = Fraction(model.weight_bytes_per_token, ranks) / card.hbm_bytes_per_ns
    kv_total = Fraction(batch * model.kv_bytes_per_token)
    kv_local = (kv_total * hit / ranks) / card.hbm_bytes_per_ns
    remote_bytes = kv_total * (1 - hit) / ranks
    kv_remote = p2p_ns(remote_bytes) if remote_bytes > 0 else Fraction(0)
    if model.comm_ops_per_token and model.comm_bytes_per_token:
        comm = model.comm_ops_per_token * collective_ns(
            Fraction(model.comm_bytes_per_token * batch)
        )
    else:
        comm = Fraction(0)
    return {
        "compute_ns": compute,
        "weights_ns": weights,
        "kv_local_ns": kv_local,
        "kv_remote_ns": kv_remote,
        "comm_ns": comm,
    }


def decode_step_ns(
    card: CardParameters,
    model: DecodeTokenModel,
    *,
    ranks: int,
    batch: int,
    kv_hit_rate,
    collective_ns: Callable[[Fraction], Fraction],
    p2p_ns: Callable[[Fraction], Fraction],
    overlap: str = "serial",
) -> Fraction:
    """One decode step's time under a registered overlap identity."""
    if overlap not in OVERLAP_IDENTITIES:
        raise ValueError(
            f"unknown overlap identity {overlap!r}; registered: {list(OVERLAP_IDENTITIES)}"
        )
    terms = decode_step_terms_ns(
        card, model,
        ranks=ranks, batch=batch, kv_hit_rate=kv_hit_rate,
        collective_ns=collective_ns, p2p_ns=p2p_ns,
    )
    if overlap == "serial":
        return sum(terms.values(), start=Fraction(0))
    local_side = (
        terms["compute_ns"] + terms["weights_ns"]
        + terms["kv_local_ns"] + terms["kv_remote_ns"]
    )
    return max(local_side, terms["comm_ns"])


def per_card_tokens_per_s(step_ns: Fraction, *, batch: int, ranks: int) -> Fraction:
    """System tokens/s divided by ranks: batch / (step_s * ranks)."""
    if int(batch) < 1:
        raise ValueError(f"batch must be >= 1, got {batch}")
    if int(ranks) < 1:
        raise ValueError(f"ranks must be >= 1, got {ranks}")
    step_s = Fraction(step_ns) / _NS_PER_S
    return Fraction(batch) / (step_s * ranks)


def decode_slo_report(
    card: CardParameters,
    model: DecodeTokenModel,
    *,
    ranks: int,
    batch: int,
    kv_hit_rate,
    collective_ns: Callable[[Fraction], Fraction],
    p2p_ns: Callable[[Fraction], Fraction],
    tpot_limit_ns,
    overlap: str = "serial",
) -> dict:
    """SLO-DECODE report: TPOT, per-card tok/s, feasibility, exact terms.

    Feasibility tie-breaking: TPOT exactly equal to the limit IS feasible
    (documented fixed tie-breaking; decidable because both are exact).
    """
    limit = _frac(tpot_limit_ns)
    if limit <= 0:
        raise ValueError(f"tpot_limit_ns must be > 0, got {tpot_limit_ns}")
    step = decode_step_ns(
        card, model,
        ranks=ranks, batch=batch, kv_hit_rate=kv_hit_rate,
        collective_ns=collective_ns, p2p_ns=p2p_ns, overlap=overlap,
    )
    tps = per_card_tokens_per_s(step, batch=batch, ranks=ranks)
    terms = decode_step_terms_ns(
        card, model,
        ranks=ranks, batch=batch, kv_hit_rate=kv_hit_rate,
        collective_ns=collective_ns, p2p_ns=p2p_ns,
    )
    return {
        "kind": "serving_roofline",
        "observable": "SLO-DECODE",
        "identity": overlap,
        "card": card.to_dict(),
        "model": model.to_dict(),
        "ranks": int(ranks),
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


def prefill_ttft_ns(
    card: CardParameters,
    model: PrefillModel,
    *,
    ranks: int,
    collective_ns: Callable[[Fraction], Fraction],
) -> Fraction:
    """Prefill TTFT under the serial prefill identity (A-SERVE-PF)."""
    if int(ranks) < 1:
        raise ValueError(f"ranks must be >= 1, got {ranks}")
    compute = Fraction(model.prefill_flops, ranks) / card.flops_per_ns
    weights = Fraction(model.weight_bytes, ranks) / card.hbm_bytes_per_ns
    if model.comm_bytes_per_chunk:
        comm = model.chunks * collective_ns(Fraction(model.comm_bytes_per_chunk))
    else:
        comm = Fraction(0)
    return compute + weights + comm


def prefill_slo_report(
    card: CardParameters,
    model: PrefillModel,
    *,
    ranks: int,
    collective_ns: Callable[[Fraction], Fraction],
    ttft_limit_ns,
) -> dict:
    """SLO-PREFILL report: TTFT and feasibility (exact equality feasible)."""
    limit = _frac(ttft_limit_ns)
    if limit <= 0:
        raise ValueError(f"ttft_limit_ns must be > 0, got {ttft_limit_ns}")
    ttft = prefill_ttft_ns(card, model, ranks=ranks, collective_ns=collective_ns)
    return {
        "kind": "serving_roofline",
        "observable": "SLO-PREFILL",
        "identity": "prefill_serial",
        "card": card.to_dict(),
        "model": model.to_dict(),
        "ranks": int(ranks),
        "ttft_ns_exact": str(ttft),
        "ttft_ns": float(ttft),
        "ttft_limit_ns_exact": str(limit),
        "slo_feasible": bool(ttft <= limit),
        "headroom_ns_exact": str(limit - ttft),
    }
