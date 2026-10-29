"""W1 Dense TP Decode workload generator (first increment).

Dense tensor-parallel decode issues, per decode step and per transformer
layer, one AllReduce over the TP group whose payload size is fixed by the
model configuration. Sizes are therefore deterministic model parameters, not
random draws; the experiment seed is still recorded in every run so future
stochastic extensions must use partitioned RNG streams (determinism
rules). Integer byte counts only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

WORKLOAD_KIND = "w1_dense_tp_decode"


@dataclass(frozen=True)
class CollectiveOp:
    op_id: str
    collective: str
    comm_ranks: tuple[int, ...]
    payload_bytes: int
    step: int
    layer: int


@dataclass(frozen=True)
class W1Config:
    tp_size: int
    layers: int
    steps: int
    allreduce_bytes: int
    model_name: str = "w1-smoke"


def load_w1_config(path: Path) -> W1Config:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data.get("workload") != WORKLOAD_KIND:
        raise ValueError(
            f"expected workload kind {WORKLOAD_KIND!r}, got {data.get('workload')!r} in {path}"
        )
    config = W1Config(
        tp_size=int(data["tp_size"]),
        layers=int(data["layers"]),
        steps=int(data["steps"]),
        allreduce_bytes=int(data["allreduce_bytes"]),
        model_name=str(data.get("model_name", "w1-smoke")),
    )
    if min(config.tp_size, config.layers, config.steps, config.allreduce_bytes) < 1:
        raise ValueError(f"degenerate W1 configuration: {config}")
    return config


def generate_w1_ops(config: W1Config) -> list[CollectiveOp]:
    """Emit AllReduce ops in a fixed, replayable order: step-major, layer-minor."""
    ranks = tuple(range(config.tp_size))
    return [
        CollectiveOp(
            op_id=f"s{step:06d}-l{layer:06d}-allreduce",
            collective="allreduce",
            comm_ranks=ranks,
            payload_bytes=config.allreduce_bytes,
            step=step,
            layer=layer,
        )
        for step in range(config.steps)
        for layer in range(config.layers)
    ]
