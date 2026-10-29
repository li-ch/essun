"""W5 PD/KV event generator.

Prefill/decode (PD) DISAGGREGATED inference moves the KV cache of every
request from the node that prefilled it to the node that decodes it, over
the scale-up fabric with MEMORY semantics (one-sided reads/writes, the
UALink/CXL/UnifiedBus class of traffic — the reason scale-up fabrics carry
KV traffic at all). W5 is the event generator for that traffic: prefill
emits KV-chunk WRITES, decode emits KV-chunk READS with request
dependencies, and KV TRANSFER ops move each chunk from its prefill node to
its decode node.

Node placement (frozen, A-W5-PLACE in
experiments/vertical_slice/assumptions_w5.yaml): ranks ``[0, P)`` are
prefill nodes and ranks ``[P, r)`` are decode nodes — a static role
partition of the ``tp_size``-node group. Request ``q`` is prefilled on node
``q % P`` and decoded on node ``P + (q % D)`` with ``D = r - P``
(deterministic round-robin; interleaved roles or explicit placement tables
are different identities and are not generated).

KV lifecycle (frozen, A-W5-LIFE / A-W5-VIS / A-W5-DAG — the task's
acceptance stages, each a direct-dependency edge unless stated):

    alloc(q, c)  -> write(q, c)  -> transfer(q, c) -> visible(q, c)
                                                     -> read(q, s, c) for
                                                        s = 0..S-1
                                                        -> release(q)

- ``kv_alloc`` (control, 0 bytes): the chunk's slot is allocated on the
  PREFILL node; capacity ``chunk_bytes``. ``alloc(q, c)`` for ``c > 0``
  depends on ``write(q, c-1)`` — prefill produces the sequence chunk by
  chunk (the W5 analogue of W2's chunk chain).
- ``kv_write`` (local write, ``chunk_bytes``): prefill emits the KV-chunk
  write into the allocated slot; depends on the alloc.
- ``kv_transfer`` (fabric, memory-semantic, ``chunk_bytes``): the
  prefill node writes the chunk into the decode node's memory — src !=
  dst by construction, the only op kind that crosses the fabric
  (A-W5-MEM); depends on the write.
- ``kv_visible`` (control, 0 bytes): VISIBILITY barrier on the decode
  node; depends on the transfer. No read of the chunk may be ordered
  before it — asserted as a DAG reachability property in tests, not
  merely by emission position.
- ``kv_read`` (local read, ``chunk_bytes``): decode step ``s`` of request
  ``q`` reads chunk ``c`` from decode-node-local memory. Request
  dependencies (A-W5-DAG): the FIRST read ``read(q, 0, 0)`` depends on
  ``visible(q, c)`` for ALL c — decode of a request starts only after its
  ENTIRE prefill KV is visible (the load-bearing PD dependency); reads
  then form one serialized chain per request, step-major, chunk-minor
  (``read(q, s, c)`` <- ``read(q, s, c-1)``; ``read(q, s, 0)`` <-
  ``read(q, s-1, C-1)``). Requests never depend on each other.
- ``kv_release`` (control, 0 bytes): after the LAST read, the request's
  whole KV (capacity ``C * chunk_bytes``) is released on the decode node;
  depends on the read chain's tail ``read(q, S-1, C-1)``.

Emission order is fixed and replayable: request-major; per request the
prefill phase (chunk-major: alloc, write, transfer, visible), then the
decode phase (step-major, chunk-minor reads), then release. That order is
a topological order of the DAG (Kahn-verified in tests).

HONEST SCOPE (A-W5-SCOPE note in the assumptions registry): W5 issues
MEMORY-SEMANTIC ops (kv_alloc/kv_write/kv_transfer/kv_visible/kv_read/
kv_release) and NO registered backend executes any of them — the L0
family declares only allreduce/reducescatter/allgather collectives, and
both Docker-pinned adapters translate W1 only. A W5 manifest is therefore
REJECTED loudly by the orchestrator's collective capability gate (that
rejection is itself a tested behavior, tests/golden/test_w5_kv_golden.py
and tests/negative/test_dispatch_gates.py); a memory-semantics fabric
model (L1/L2) is required to execute KV traffic. Only the
KV-MIGRATING identity is generated (transfer once, then decode-local
reads); the alternative identity — KV stays on the prefill node and every
decode read is a REMOTE fabric read — is a different model and is NOT
generated. Fixed uniform ``decode_steps`` per request; variable request
lengths and serving scheduling are out of scope for this generator.

Sizes are deterministic model parameters, not random draws; integer byte
counts only (control ops carry payload 0 — no bytes move). The experiment
seed is still recorded by the run path for every run so future
stochastic extensions must use partitioned RNG streams (determinism
rules).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from essun.workload.base import DAGCollectiveOp

WORKLOAD_KIND = "w5_pd_kv_prefill_decode"

OP_KINDS = ("kv_alloc", "kv_write", "kv_transfer", "kv_visible", "kv_read", "kv_release")
CONTROL_KINDS = ("kv_alloc", "kv_visible", "kv_release")
FABRIC_KINDS = ("kv_transfer",)  # the only op kind with src_node != dst_node (A-W5-MEM)


@dataclass(frozen=True)
class W5KVOp(DAGCollectiveOp):
    """One W5 KV-lifecycle op (the ``collective`` field carries the op kind).

    ``src_node`` / ``dst_node`` are the memory endpoints: for the transfer
    they are the prefill and decode nodes (``comm_ranks`` holds both); for
    every other op they are the single owning node (``comm_ranks`` holds
    it once) — writes/reads are node-local, control ops move no bytes.
    ``chunk_bytes`` is the capacity the op touches (the freed request
    total ``C * chunk_bytes`` on release; ``chunk`` is None there and on
    no other op). ``step`` is the decode step index, None off reads.
    ``payload_bytes`` is the bytes MOVED: chunk_bytes on write/transfer/
    read, 0 on the control kinds.
    """

    request: int
    chunk: int | None
    step: int | None
    src_node: int
    dst_node: int
    chunk_bytes: int


@dataclass(frozen=True)
class W5Config:
    tp_size: int  # total nodes r in the PD group (prefill + decode)
    prefill_nodes: int  # P: ranks [0, P) prefill, [P, r) decode (A-W5-PLACE)
    requests: int
    chunks_per_request: int
    chunk_bytes: int
    decode_steps: int
    model_name: str = "w5-smoke"


def prefill_node(config: W5Config, request: int) -> int:
    """Prefill node of ``request``: deterministic round-robin q % P."""
    return request % config.prefill_nodes


def decode_node(config: W5Config, request: int) -> int:
    """Decode node of ``request``: P + q % D over the D = r - P decode ranks."""
    return config.prefill_nodes + (request % (config.tp_size - config.prefill_nodes))


def _validate_w5_config(config: W5Config) -> None:
    positive = (
        config.tp_size,
        config.prefill_nodes,
        config.requests,
        config.chunks_per_request,
        config.chunk_bytes,
        config.decode_steps,
    )
    if min(positive) < 1:
        raise ValueError(f"degenerate W5 configuration: {config}")
    if config.prefill_nodes >= config.tp_size:
        raise ValueError(
            f"degenerate W5 configuration: prefill_nodes {config.prefill_nodes} "
            f"leaves no decode node in a {config.tp_size}-node group (PD needs "
            "both roles; ranks [0, P) prefill, [P, tp_size) decode)"
        )


def load_w5_config(path: Path) -> W5Config:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data.get("workload") != WORKLOAD_KIND:
        raise ValueError(
            f"expected workload kind {WORKLOAD_KIND!r}, got {data.get('workload')!r} in {path}"
        )
    if "layers" in data:
        raise ValueError(
            "degenerate W5 configuration: a 'layers' key is ambiguous on a W5 "
            "document (W5's positional structure is requests/chunks/steps, not "
            "transformer layers)"
        )
    config = W5Config(
        tp_size=int(data["tp_size"]),
        prefill_nodes=int(data["prefill_nodes"]),
        requests=int(data["requests"]),
        chunks_per_request=int(data["chunks_per_request"]),
        chunk_bytes=int(data["chunk_bytes"]),
        decode_steps=int(data["decode_steps"]),
        model_name=str(data.get("model_name", "w5-smoke")),
    )
    _validate_w5_config(config)
    return config


def generate_w5_ops(config: W5Config) -> list[W5KVOp]:
    """Emit the KV-lifecycle op DAG in a fixed, replayable order.

    Request-major; per request: the prefill phase chunk-major (alloc,
    write, transfer, visible), then decode reads step-major/chunk-minor,
    then release. ``depends_on`` encodes the frozen A-W5-LIFE / A-W5-VIS /
    A-W5-DAG semantics (see the module docstring); the emission order is a
    topological order of that DAG.
    """
    _validate_w5_config(config)
    chunks = config.chunks_per_request
    steps = config.decode_steps
    last_chunk = chunks - 1
    ops: list[W5KVOp] = []
    for request in range(config.requests):
        src = prefill_node(config, request)
        dst = decode_node(config, request)
        # --- prefill phase: alloc -> write -> transfer -> visible, per chunk
        for chunk in range(chunks):
            alloc_id = f"q{request:06d}-c{chunk:06d}-kv-alloc"
            write_id = f"q{request:06d}-c{chunk:06d}-kv-write"
            transfer_id = f"q{request:06d}-c{chunk:06d}-kv-transfer"
            visible_id = f"q{request:06d}-c{chunk:06d}-kv-visible"
            alloc_depends = () if chunk == 0 else (
                f"q{request:06d}-c{chunk - 1:06d}-kv-write",
            )
            ops.append(
                W5KVOp(
                    op_id=alloc_id,
                    collective="kv_alloc",
                    comm_ranks=(src,),
                    payload_bytes=0,
                    layer=0,
                    depends_on=alloc_depends,
                    request=request,
                    chunk=chunk,
                    step=None,
                    src_node=src,
                    dst_node=src,
                    chunk_bytes=config.chunk_bytes,
                )
            )
            ops.append(
                W5KVOp(
                    op_id=write_id,
                    collective="kv_write",
                    comm_ranks=(src,),
                    payload_bytes=config.chunk_bytes,
                    layer=0,
                    depends_on=(alloc_id,),
                    request=request,
                    chunk=chunk,
                    step=None,
                    src_node=src,
                    dst_node=src,
                    chunk_bytes=config.chunk_bytes,
                )
            )
            ops.append(
                W5KVOp(
                    op_id=transfer_id,
                    collective="kv_transfer",
                    comm_ranks=(src, dst),
                    payload_bytes=config.chunk_bytes,
                    layer=0,
                    depends_on=(write_id,),
                    request=request,
                    chunk=chunk,
                    step=None,
                    src_node=src,
                    dst_node=dst,
                    chunk_bytes=config.chunk_bytes,
                )
            )
            ops.append(
                W5KVOp(
                    op_id=visible_id,
                    collective="kv_visible",
                    comm_ranks=(dst,),
                    payload_bytes=0,
                    layer=0,
                    depends_on=(transfer_id,),
                    request=request,
                    chunk=chunk,
                    step=None,
                    src_node=dst,
                    dst_node=dst,
                    chunk_bytes=config.chunk_bytes,
                )
            )
        # --- decode phase: reads step-major, chunk-minor, one chain per request
        for step in range(steps):
            for chunk in range(chunks):
                if step == 0 and chunk == 0:
                    # A-W5-VIS request gate: decode of q starts only after its
                    # ENTIRE prefill KV is visible on the decode node.
                    read_depends = tuple(
                        f"q{request:06d}-c{c:06d}-kv-visible" for c in range(chunks)
                    )
                elif chunk == 0:
                    read_depends = (f"q{request:06d}-s{step - 1:06d}-c{last_chunk:06d}-kv-read",)
                else:
                    read_depends = (f"q{request:06d}-s{step:06d}-c{chunk - 1:06d}-kv-read",)
                ops.append(
                    W5KVOp(
                        op_id=f"q{request:06d}-s{step:06d}-c{chunk:06d}-kv-read",
                        collective="kv_read",
                        comm_ranks=(dst,),
                        payload_bytes=config.chunk_bytes,
                        layer=0,
                        depends_on=read_depends,
                        request=request,
                        chunk=chunk,
                        step=step,
                        src_node=dst,
                        dst_node=dst,
                        chunk_bytes=config.chunk_bytes,
                    )
                )
        # --- release: after the read chain's tail (transitively every read)
        ops.append(
            W5KVOp(
                op_id=f"q{request:06d}-kv-release",
                collective="kv_release",
                comm_ranks=(dst,),
                payload_bytes=0,
                layer=0,
                depends_on=(f"q{request:06d}-s{steps - 1:06d}-c{last_chunk:06d}-kv-read",),
                request=request,
                chunk=None,
                step=None,
                src_node=dst,
                dst_node=dst,
                chunk_bytes=chunks * config.chunk_bytes,
            )
        )
    return ops
