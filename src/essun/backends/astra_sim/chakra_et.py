"""Deterministic Chakra ET (execution trace) protobuf wire encoder.

ASTRA-sim 2.0 at the pinned commit reads workloads ONLY as Chakra ET files
(``<prefix>.<npu_id>.et``): one ``GlobalMetadata`` message followed by a
stream of ``Node`` messages, each prefixed by its serialized length as a
32-bit varint. Source anchors (pinned tree, commit
4ce9ecfe746a3ee5fe47559a11d91644d641fa7f):

- message/enum schema: ``extern/graph_frontend/chakra/schema/protobuf/
  et_def.proto`` (chakra submodule pin 0e3cd40c569f0a4cacb6d961bb56be53407abd2f)
- length framing: ``extern/graph_frontend/chakra/src/third_party/utils/
  protolib.py`` — ``encodeMessage`` writes ``_EncodeVarint32(len(payload))``
  followed by ``message.SerializeToString()``
- attribute usage for collective nodes:
  ``examples/workload/microbenchmarks/generator_scripts/all_reduce.py``
  (sets ``is_cpu_op`` bool, ``comm_type`` int64 enum, ``comm_size`` int64 bytes)

This module implements exactly that subset in pure Python (no protobuf
dependency, no generated code) so translation is deterministic and testable
byte-for-byte. Wire-format rules implemented:

- proto3 default omission for plain scalar fields (``Node.id == 0`` and
  ``Node.type == 0`` are not serialized; confirmed against the pinned
  example files ``all_reduce.0.et`` / ``all_reduce.3.et``);
- oneof presence semantics for ``AttributeProto.value``: a oneof member
  that is explicitly set IS serialized even at its default value (this is
  why the pinned example carries ``bool_val=false`` and ``comm_type=0``);
- fields serialized in field-number order (the order the pinned generator's
  protobuf runtime emits).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# NodeType enum (et_def.proto).
COMM_COLL_NODE = 7

# CollectiveCommType enum (et_def.proto).
ALL_REDUCE = 0
REDUCE = 1
ALL_GATHER = 2
GATHER = 3
SCATTER = 4
BROADCAST = 5
ALL_TO_ALL = 6
REDUCE_SCATTER = 7
REDUCE_SCATTER_BLOCK = 8
BARRIER = 9

COLLECTIVE_COMM_TYPES = {
    "allreduce": ALL_REDUCE,
    "reduce": REDUCE,
    "allgather": ALL_GATHER,
    "gather": GATHER,
    "scatter": SCATTER,
    "broadcast": BROADCAST,
    "alltoall": ALL_TO_ALL,
    "reducescatter": REDUCE_SCATTER,
    "reducescatter_block": REDUCE_SCATTER_BLOCK,
    "barrier": BARRIER,
}

# AttributeProto oneof member tags (field number << 3 | wire type).
_WIRE_VARINT = 0
_WIRE_LEN = 2
_TAG_BOOL_VAL = 27 << 3 | _WIRE_VARINT  # 216 -> varint bytes d8 01
_TAG_INT64_VAL = 9 << 3 | _WIRE_VARINT  # 72 -> 0x48


def _varint(value: int) -> bytes:
    """Base-128 varint (little-endian 7-bit groups), as protoc emits."""
    if value < 0:
        raise ValueError(f"varint requires a non-negative integer, got {value}")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field_varint(number: int, value: int) -> bytes:
    return _varint(number << 3 | _WIRE_VARINT) + _varint(value)


def _field_string(number: int, value: str) -> bytes:
    payload = value.encode("utf-8")
    return _varint(number << 3 | _WIRE_LEN) + _varint(len(payload)) + payload


def _field_message(number: int, payload: bytes) -> bytes:
    return _varint(number << 3 | _WIRE_LEN) + _varint(len(payload)) + payload


def _length_prefix(payload: bytes) -> bytes:
    """protolib.encodeMessage framing: 32-bit varint length prefix."""
    if len(payload) >= 1 << 32:
        raise ValueError("message too large for varint32 framing")
    return _varint(len(payload)) + payload


@dataclass(frozen=True)
class Attribute:
    """One AttributeProto with an explicitly set oneof member."""

    name: str
    kind: str  # "int64" | "bool" — which oneof member is set
    int64_value: int = 0
    bool_value: bool = False

    def serialize(self) -> bytes:
        # name (field 1, string); the set oneof member is always emitted,
        # matching protobuf oneof presence semantics at the pin.
        out = _field_string(1, self.name) if self.name else b""
        if self.kind == "int64":
            out += _field_varint(9, self.int64_value)  # int64_val
        elif self.kind == "bool":
            out += _field_varint(27, 1 if self.bool_value else 0)  # bool_val
        else:
            raise ValueError(f"unsupported attribute kind {self.kind!r}")
        return out


@dataclass(frozen=True)
class Node:
    """One Chakra ET Node (subset used for collective nodes)."""

    id: int
    name: str
    node_type: int
    ctrl_deps: tuple[int, ...] = ()
    data_deps: tuple[int, ...] = ()
    attrs: tuple[Attribute, ...] = field(default=())

    def serialize(self) -> bytes:
        out = b""
        if self.id != 0:  # proto3 default omission
            out += _field_varint(1, self.id)
        if self.name:
            out += _field_string(2, self.name)
        if self.node_type != 0:  # proto3 default omission (enum default 0)
            out += _field_varint(3, self.node_type)
        for dep in self.ctrl_deps:  # field 4, repeated uint64
            out += _field_varint(4, dep)
        for dep in self.data_deps:  # field 5, repeated uint64
            out += _field_varint(5, dep)
        for attr in self.attrs:  # field 10, repeated AttributeProto
            out += _field_message(10, attr.serialize())
        return out


@dataclass(frozen=True)
class GlobalMetadata:
    """Chakra ET file metadata (version string only, as at the pin)."""

    version: str = "0.0.4"

    def serialize(self) -> bytes:
        if not self.version:
            return b""
        return _field_string(1, self.version)


def encode_et_file(metadata: GlobalMetadata, nodes: tuple[Node, ...]) -> bytes:
    """Serialize one rank's ET file: metadata, then nodes, each framed."""
    out = bytearray(_length_prefix(metadata.serialize()))
    for node in nodes:
        out += _length_prefix(node.serialize())
    return bytes(out)
