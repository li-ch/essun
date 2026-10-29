"""Shared workload-IR op base for dependency-ordered workloads (P5, W2).

W1 landed a flat op dataclass whose execution order is carried entirely by
list position (:class:`essun.workload.w1.CollectiveOp`). W2 prefill ops
instead form an explicit dependency DAG (per-chunk ReduceScatter ->
AllGather pairs chained across chunks and layers), so the DAG-capable op
lives here as a shared base. W1 keeps working unchanged on its own landed
dataclass (P5 boundary: the landed W1 module and its dataclass are not
mutated); this base exists so later dependency-ordered workloads (W3+)
do not each grow a private copy of the field set.

``depends_on`` lists DIRECT predecessors only, by ``op_id``; transitive
ordering is implied and never redundantly restated. Backends that cannot
honor dependencies (e.g. any serialized L0 executor) may treat the DAG as
the emission order, which the generators guarantee to be a topological
order of it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DAGCollectiveOp:
    """One collective op node with explicit direct dependencies."""

    op_id: str
    collective: str
    comm_ranks: tuple[int, ...]
    payload_bytes: int
    layer: int
    depends_on: tuple[str, ...]
