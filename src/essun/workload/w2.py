"""W2 Dense TP Prefill workload generator.

Dense tensor-parallel PREFILL differs from decode in its collective shape:
instead of one AllReduce per (step, layer), each transformer layer processes
its activation as a fixed sequence of byte chunks, and every chunk issues a
ReduceScatter(chunk) followed by an AllGather(chunk) — the two first-class
phase collectives landed as P2 stage S4. Under the S4 message-size semantics
(A-L0P-MSG) both phases carry the same M = chunk_bytes, so one chunk pair
composes exactly AllReduce(M) (A-L0P-COMP); the workload's point is the
dependency structure between the phases, not a new collective.

Dependency semantics (frozen here, recorded as assumption A-W2-DAG in
experiments/vertical_slice/assumptions_l0.yaml):

- Phase pair:      AG(k, c) depends on RS(k, c)            — the AllGather
  consumes the ReduceScatter's reduced chunks; serialized phases, no overlap.
- Chunk chain:     RS(k, c) depends on AG(k, c-1) for c>0  — chunks within a
  layer execute back-to-back on the same group.
- Layer chain:     RS(k, 0) depends on AG(k-1, C-1) for k>0 — a layer's first
  chunk starts after the previous layer's last chunk finished.

Every op except the first therefore has exactly one direct predecessor, and
the DAG is the chain following the emission order. The emission order is
fixed and replayable: layer-major, chunk-minor, ReduceScatter before
AllGather within each chunk (the W2 analogue of W1's step-major/layer-minor
rule), and it is a topological order of the DAG. Overlapped or chunk-parallel
schedules are different identities and are not generated.

Sizes are deterministic model parameters, not random draws; integer byte
counts only. The experiment seed is still recorded by the orchestrator for
every run so future stochastic extensions must use partitioned RNG streams
(determinism rules).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from essun.workload.base import DAGCollectiveOp

WORKLOAD_KIND = "w2_dense_tp_prefill"


@dataclass(frozen=True)
class W2CollectiveOp(DAGCollectiveOp):
    """One W2 prefill collective op: a phase of chunk ``chunk`` in ``layer``."""

    chunk: int


@dataclass(frozen=True)
class W2Config:
    tp_size: int
    layers: int
    chunks_per_layer: int
    chunk_bytes: int
    model_name: str = "w2-smoke"


def load_w2_config(path: Path) -> W2Config:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data.get("workload") != WORKLOAD_KIND:
        raise ValueError(
            f"expected workload kind {WORKLOAD_KIND!r}, got {data.get('workload')!r} in {path}"
        )
    config = W2Config(
        tp_size=int(data["tp_size"]),
        layers=int(data["layers"]),
        chunks_per_layer=int(data["chunks_per_layer"]),
        chunk_bytes=int(data["chunk_bytes"]),
        model_name=str(data.get("model_name", "w2-smoke")),
    )
    if min(config.tp_size, config.layers, config.chunks_per_layer, config.chunk_bytes) < 1:
        raise ValueError(f"degenerate W2 configuration: {config}")
    return config


def generate_w2_ops(config: W2Config) -> list[W2CollectiveOp]:
    """Emit ReduceScatter/AllGather chunk pairs in a fixed, replayable order.

    Layer-major, chunk-minor, ReduceScatter then AllGather per chunk. The
    ``depends_on`` field encodes the frozen A-W2-DAG semantics (phase pair,
    chunk chain, layer chain); see the module docstring.
    """
    if min(config.tp_size, config.layers, config.chunks_per_layer, config.chunk_bytes) < 1:
        raise ValueError(f"degenerate W2 configuration: {config}")
    ranks = tuple(range(config.tp_size))
    last_chunk = config.chunks_per_layer - 1
    ops: list[W2CollectiveOp] = []
    for layer in range(config.layers):
        for chunk in range(config.chunks_per_layer):
            rs_id = f"l{layer:06d}-c{chunk:06d}-reducescatter"
            ag_id = f"l{layer:06d}-c{chunk:06d}-allgather"
            if chunk > 0:
                rs_depends = (f"l{layer:06d}-c{chunk - 1:06d}-allgather",)
            elif layer > 0:
                rs_depends = (f"l{layer - 1:06d}-c{last_chunk:06d}-allgather",)
            else:
                rs_depends = ()
            ops.append(
                W2CollectiveOp(
                    op_id=rs_id,
                    collective="reducescatter",
                    comm_ranks=ranks,
                    payload_bytes=config.chunk_bytes,
                    layer=layer,
                    depends_on=rs_depends,
                    chunk=chunk,
                )
            )
            ops.append(
                W2CollectiveOp(
                    op_id=ag_id,
                    collective="allgather",
                    comm_ranks=ranks,
                    payload_bytes=config.chunk_bytes,
                    layer=layer,
                    depends_on=(rs_id,),
                    chunk=chunk,
                )
            )
    return ops
