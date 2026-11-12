"""W6 RL rollout workload generator.

Reinforcement-learning rollout loops drive a third scale-up traffic class
next to serving (W1/W2 decode/prefill) and disaggated KV movement (W5):
the rollout engine generates tokens on the current policy weights (a burst
of decode-style steps), then the updated policy weights are synchronized
across the training/rollout group (one weight-sync phase per round). W6 is
the event generator for that loop:

- one rollout round = ``gen_steps`` decode-style steps x ``layers``
  AllReduces over the TP group, payload ``gen_bytes`` each — structurally
  the W1 decode burst, scoped to the round;
- followed by ONE weight-sync phase = ``sync_allreduces`` AllReduces,
  payload ``sync_bytes`` each, op-id prefix ``sync-``.

Emission order is fixed and replayable: round-major, then step, then
layer for the generation ops; the sync ops come last within each round
(the rollout loop's barrier: generation of round ``r+1`` is not modeled to
overlap round ``r``'s sync). All ops are plain AllReduces over the full
group ``[0, tp_size)`` — unlike W3/W5, every AllReduce-capable backend can
execute W6; every other rollout-loop detail (actor/learner split, local
SGD steps before sync, async rollouts, overlapping rounds) is out of
scope for this generator.

Sizes are deterministic model parameters, not random draws; integer byte
counts only. The experiment seed is still recorded by the run path for
every run so future stochastic extensions must use partitioned RNG
streams (determinism rules).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

WORKLOAD_KIND = "w6_rollout"

PHASE_GENERATION = "generation"
PHASE_WEIGHT_SYNC = "weight_sync"
PHASES = (PHASE_GENERATION, PHASE_WEIGHT_SYNC)


@dataclass(frozen=True)
class W6Op:
    """One W6 rollout op (an AllReduce in one of the two phases).

    ``round`` is the rollout round index; ``phase`` is ``"generation"``
    (``step`` = decode-style step within the round, ``layer`` =
    transformer layer) or ``"weight_sync"`` (``step``/``layer`` are None —
    the sync AllReduces have no decode step or layer, only their order,
    which the op-id carries as ``a{i}``).
    """

    op_id: str
    collective: str
    comm_ranks: tuple[int, ...]
    payload_bytes: int
    round: int
    phase: str
    step: int | None
    layer: int | None


@dataclass(frozen=True)
class W6Config:
    tp_size: int
    layers: int
    gen_steps: int
    gen_bytes: int
    sync_allreduces: int
    sync_bytes: int
    rounds: int
    model_name: str = "w6-smoke"


def _validate_w6_config(config: W6Config) -> None:
    positive = (
        config.tp_size,
        config.layers,
        config.gen_steps,
        config.gen_bytes,
        config.sync_allreduces,
        config.sync_bytes,
        config.rounds,
    )
    if min(positive) < 1:
        raise ValueError(f"degenerate W6 configuration: {config}")


def load_w6_config(path: Path) -> W6Config:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data.get("workload") != WORKLOAD_KIND:
        raise ValueError(
            f"expected workload kind {WORKLOAD_KIND!r}, got {data.get('workload')!r} in {path}"
        )
    config = W6Config(
        tp_size=int(data["tp_size"]),
        layers=int(data["layers"]),
        gen_steps=int(data["gen_steps"]),
        gen_bytes=int(data["gen_bytes"]),
        sync_allreduces=int(data["sync_allreduces"]),
        sync_bytes=int(data["sync_bytes"]),
        rounds=int(data["rounds"]),
        model_name=str(data.get("model_name", "w6-smoke")),
    )
    _validate_w6_config(config)
    return config


def generate_w6_ops(config: W6Config) -> list[W6Op]:
    """Emit rollout ops in a fixed, replayable order.

    Round-major; per round the generation burst (step-major, layer-minor),
    then the weight-sync AllReduces with the ``sync-`` op-id prefix.
    """
    _validate_w6_config(config)
    ranks = tuple(range(config.tp_size))
    ops: list[W6Op] = []
    for rnd in range(config.rounds):
        for step in range(config.gen_steps):
            for layer in range(config.layers):
                ops.append(
                    W6Op(
                        op_id=f"r{rnd:06d}-s{step:06d}-l{layer:06d}-allreduce",
                        collective="allreduce",
                        comm_ranks=ranks,
                        payload_bytes=config.gen_bytes,
                        round=rnd,
                        phase=PHASE_GENERATION,
                        step=step,
                        layer=layer,
                    )
                )
        for index in range(config.sync_allreduces):
            ops.append(
                W6Op(
                    op_id=f"sync-r{rnd:06d}-a{index:06d}-allreduce",
                    collective="allreduce",
                    comm_ranks=ranks,
                    payload_bytes=config.sync_bytes,
                    round=rnd,
                    phase=PHASE_WEIGHT_SYNC,
                    step=None,
                    layer=None,
                )
            )
    return ops
