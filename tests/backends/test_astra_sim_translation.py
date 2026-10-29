"""T022 stage S1 golden + negative tests: manifest -> ASTRA-sim translation.

Golden expectations are spelled IN THE TEST, independent of the encoder under
test: an in-test protobuf wire decoder (this file) re-derives the content of
the generated Chakra ET files — op count, message sizes, issue order,
dependency chain, node ids — from first principles of the pinned
et_def.proto. The wire encoder itself is pinned against the upstream
example files committed under tests/fixtures/astra_sim/ (copied verbatim
from the ASTRA-sim checkout at commit 4ce9ecf; provenance in the fixture
README).

Negative tests: every capability gap is rejected explicitly with the gap
named (BackendAdapter contract, IMPLEMENTATION_GUIDE §5).
"""

from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.backends.astra_sim import adapter, chakra_et

REPO = Path(__file__).resolve().parents[2]
ASTRA_MANIFEST = (
    REPO / "experiments" / "vertical_slice" / "w1_decode_smoke_astra.yaml"
)
COMPILED_DIR = REPO / "experiments" / "vertical_slice" / "astra_w1_decode_smoke_astra"
FIXTURES = REPO / "tests" / "fixtures" / "astra_sim"

# Hand-derived from the committed free parameters (ring8_free_params.yaml:
# B = 64 B/ns, L = 200 ns, ranks 8; w1_dense_tp_decode_small.yaml:
# 3 steps x 2 layers, M = 16384 B).
OPS_PER_RANK = 6
PAYLOAD = 16384
BW_GBPS_EXACT = "59.604644775390625"  # 64 * 1e9 / 2^30, finite decimal
EXPECTED_OP_ORDER = [
    f"s{step:06d}-l{layer:06d}-allreduce"
    for step in range(3)
    for layer in range(2)
]


# --- in-test Chakra ET wire decoder (independent of chakra_et.py) ----------


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value, shift = 0, 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7


def _decode_attribute(data: bytes) -> dict:
    attrs, pos = {}, 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if wire == 2:
            length, pos = _read_varint(data, pos)
            payload = data[pos : pos + length]
            pos += length
            if number == 1:
                attrs["name"] = payload.decode("utf-8")
        elif wire == 0:
            value, pos = _read_varint(data, pos)
            if number == 9:  # oneof int64_val
                attrs["int64_val"] = value
            elif number == 27:  # oneof bool_val
                attrs["bool_val"] = bool(value)
        else:
            raise AssertionError(f"unexpected wire type {wire} in attribute")
    return attrs


def _decode_node(data: bytes) -> dict:
    node, pos = {"id": 0, "ctrl_deps": [], "data_deps": [], "attrs": []}, 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value, pos = _read_varint(data, pos)
            if number == 1:
                node["id"] = value
            elif number == 3:
                node["type"] = value
            elif number == 4:
                node["ctrl_deps"].append(value)
            elif number == 5:
                node["data_deps"].append(value)
            else:
                raise AssertionError(f"unexpected varint field {number}")
        elif wire == 2:
            length, pos = _read_varint(data, pos)
            payload = data[pos : pos + length]
            pos += length
            if number == 2:
                node["name"] = payload.decode("utf-8")
            elif number == 10:
                node["attrs"].append(_decode_attribute(payload))
            else:
                raise AssertionError(f"unexpected length-delim field {number}")
        else:
            raise AssertionError(f"unexpected wire type {wire} in node")
    return node


def decode_et_file(path: Path) -> dict:
    data = path.read_bytes()
    pos = 0
    messages = []
    while pos < len(data):
        length, pos = _read_varint(data, pos)
        messages.append(data[pos : pos + length])
        pos += length
    assert pos == len(data), "trailing bytes after last framed message"
    # GlobalMetadata: field 1 (version) string only, per et_def.proto.
    metadata = messages[0]
    version = ""
    mpos = 0
    while mpos < len(metadata):
        tag, mpos = _read_varint(metadata, mpos)
        number, wire = tag >> 3, tag & 7
        if wire == 2 and number == 1:
            length, mpos = _read_varint(metadata, mpos)
            version = metadata[mpos : mpos + length].decode("utf-8")
            mpos += length
        else:
            raise AssertionError(f"unexpected metadata field {number}/{wire}")
    return {"metadata": version, "nodes": [_decode_node(m) for m in messages[1:]]}


# --- golden: wire encoder pinned against upstream example files ------------


@pytest.mark.parametrize("rank", [0, 3])
def test_wire_encoder_reproduces_pinned_upstream_example(rank):
    # Ground truth from the pin: same logical content -> same bytes. Rank 0
    # exercises proto3 default-omission (node id 0 absent); rank 3 the
    # serialized id (`08 03`).
    node = chakra_et.Node(
        id=rank,
        name="all_reduce_8npus_1MB",
        node_type=chakra_et.COMM_COLL_NODE,
        attrs=(
            chakra_et.Attribute(name="is_cpu_op", kind="bool", bool_value=False),
            chakra_et.Attribute(
                name="comm_type", kind="int64", int64_value=chakra_et.ALL_REDUCE
            ),
            chakra_et.Attribute(
                name="comm_size", kind="int64", int64_value=1024 * 1024
            ),
        ),
    )
    encoded = chakra_et.encode_et_file(
        chakra_et.GlobalMetadata(version="0.0.4"), (node,)
    )
    pinned = (FIXTURES / f"all_reduce.{rank}.et").read_bytes()
    assert encoded == pinned


# --- golden: W1 translation content, spelled in the test --------------------


def test_w1_et_workload_content_spelled():
    # Rank 0 file: 6 COMM_COLL nodes, all ALL_REDUCE (comm_type 0) of
    # 16384 B, in step-major layer-minor order, chained by data_deps, node
    # ids rank-major (A-AS1-IDS / A-AS1-CHAIN).
    decoded = decode_et_file(COMPILED_DIR / "workload" / "w1_decode_smoke_astra.0.et")
    assert decoded["metadata"] == "0.0.4"  # GlobalMetadata.version only
    nodes = decoded["nodes"]
    assert len(nodes) == OPS_PER_RANK  # op count: 2 layers x 3 steps

    def attrs(node):
        return {a["name"]: a for a in node["attrs"]}

    for index, node in enumerate(nodes):
        assert node["type"] == 7  # COMM_COLL_NODE
        assert node["name"] == EXPECTED_OP_ORDER[index]  # issue order
        a = attrs(node)
        assert a["is_cpu_op"] == {"name": "is_cpu_op", "bool_val": False}
        assert a["comm_type"]["int64_val"] == 0  # ALL_REDUCE
        assert a["comm_size"]["int64_val"] == PAYLOAD  # message size
        assert node["ctrl_deps"] == []
        if index:
            # serialized on the previous node of THIS rank
            assert node["data_deps"] == [index - 1]
        else:
            assert node["data_deps"] == []
    # Node id 0 omitted on the wire (proto3 default), decoded back to 0.
    assert [node["id"] for node in nodes] == list(range(OPS_PER_RANK))


def test_w1_et_rank_files_and_global_ids():
    # One ET file per rank (8); ids rank-major: rank r op j -> r*6 + j.
    for rank in range(8):
        decoded = decode_et_file(
            COMPILED_DIR / "workload" / f"w1_decode_smoke_astra.{rank}.et"
        )
        assert len(decoded["nodes"]) == OPS_PER_RANK
        assert [node["id"] for node in decoded["nodes"]] == [
            rank * OPS_PER_RANK + j for j in range(OPS_PER_RANK)
        ]
    # The first node of rank 3 has a nonzero id serialized on the wire.
    raw = (COMPILED_DIR / "workload" / "w1_decode_smoke_astra.3.et").read_bytes()
    assert b"\x08\x12" in raw  # field 1 (id) = 18 = 3*6


def test_network_translation_units_and_dimension_order():
    # Single-dimension Ring, dimension order = the written list order;
    # bandwidth converts bit-exactly under the pinned 1 GB = 2^30 B rule.
    text = (COMPILED_DIR / "network.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert data["topology"] == ["Ring"]  # dimension order: one Ring dim
    assert data["npus_count"] == [8]
    assert data["bandwidth"] == [float(BW_GBPS_EXACT)]
    assert data["latency"] == [200.0]
    # Exactness: decimal * 2^30 / 1e9 == 64 B/ns with no rounding at all
    # (dyadic value, exact double, exact products and quotient).
    assert Fraction(BW_GBPS_EXACT) * (1 << 30) / Fraction(10**9) == Fraction(64)
    # The exact decimal string (not a truncated float repr) is committed.
    assert BW_GBPS_EXACT in text


def test_system_and_remote_memory_translation():
    import json

    system = json.loads((COMPILED_DIR / "system.json").read_text(encoding="utf-8"))
    assert system["all-reduce-implementation"] == ["ring"]
    assert system["preferred-dataset-splits"] == 8  # A-AS1-SPLITS (== ranks)
    assert system["active-chunks-per-dimension"] == 1
    assert system["endpoint-delay"] == 10  # A-AS2-DELAY-POS (0 aborts the pin)
    assert system["local-mem-bw"] == 1600  # A-AS2-MEM-BW (absent key hangs)
    # A-AS2-INERT-KEYS: boost/roofline/peak-perf stay omitted (proven inert).
    for inert in ("boost-mode", "roofline-enabled", "peak-perf"):
        assert inert not in system
    remote = json.loads(
        (COMPILED_DIR / "remote_memory.json").read_text(encoding="utf-8")
    )
    assert remote == {"memory-type": "NO_MEMORY_EXPANSION"}


def test_compile_plan_records_provenance_and_free_parameters():
    import json

    plan = json.loads((COMPILED_DIR / "compile_plan.json").read_text(encoding="utf-8"))
    assert plan["backend_id"] == "astra_sim_analytical"
    assert plan["pin"]["astra_sim_commit"] == (
        "4ce9ecfe746a3ee5fe47559a11d91644d641fa7f"
    )
    assert plan["workload"]["ops_per_rank"] == OPS_PER_RANK
    assert plan["workload"]["op_order"] == EXPECTED_OP_ORDER
    assert plan["topology"]["dimension_order"] == ["Ring"]
    assert plan["topology"]["dimensions"][0]["bandwidth_B_per_ns_exact"] == "64"
    free = {p["name"]: p for p in plan["free_parameters"]}
    assert free["link.bytes_per_ns"]["assumption"] == "A-L0-BW"
    assert free["link.hop_latency_ns"]["assumption"] == "A-L0-LAT"
    assert free["workload.allreduce_bytes"]["assumption"] == "A-W1-SIZE"
    assumption_ids = {a["id"] for a in plan["translation_assumptions"]}
    assert {"A-AS1-BW-UNIT", "A-AS1-CHAIN", "A-AS1-IDS"} <= assumption_ids
    # Every recorded file hash matches the file on disk.
    for relative, sha in plan["files"].items():
        assert adapter.contracts.sha256_of(COMPILED_DIR / relative) == sha


def test_translation_snapshot_is_byte_identical_on_regeneration(tmp_path):
    # Snapshot: recompiling the committed manifest reproduces every byte of
    # the committed input set (translation determinism).
    adapter.compile_experiment(ASTRA_MANIFEST, tmp_path)
    committed = sorted(p for p in COMPILED_DIR.rglob("*") if p.is_file())
    assert len(committed) == 12
    for path in committed:
        regenerated = tmp_path / path.relative_to(COMPILED_DIR)
        assert regenerated.is_file(), f"missing {regenerated}"
        assert regenerated.read_bytes() == path.read_bytes(), f"differs: {path}"


# --- capabilities (loud declaration, mirrored from the pin) -----------------


def test_capabilities_declare_gaps_loudly():
    caps = adapter.capabilities()
    assert caps["backend_id"] == "astra_sim_analytical"
    assert caps["transport_model"] == "congestion_unaware_analytical"
    unsupported = set(caps["explicitly_unsupported"])
    # The loud one: congestion-unaware analytical transport.
    assert "congestion_contention_effects" in unsupported
    assert "credit_flow_control" in unsupported
    assert "packetization_flit_effects" in unsupported
    # csg-htsim is integrated, NOT uet-htsim (pins doc lineage note).
    assert "uec_uet_transport_semantics" in unsupported
    # No byte accounting in the analytical output.
    assert "O-CONSERVATION" in unsupported
    assert set(caps["observables"]) == {"O-CCT"}


def test_bandwidth_conversion_rejects_inexact_values():
    # A manifest bandwidth whose GB/s form has no finite decimal (denominator
    # not a power of two) is rejected rather than silently rounded.
    with pytest.raises(adapter.AdapterError, match="no exact finite GB/s decimal"):
        adapter.bandwidth_gb_per_s(Fraction(1, 3))


# --- negative: capability gaps rejected with the gap named ------------------


def _manifest_variant(tmp_path, mutate, name="variant.yaml"):
    data = yaml.safe_load(ASTRA_MANIFEST.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_unsupported_observable_rejected_naming_gap(tmp_path):
    path = _manifest_variant(
        tmp_path, lambda data: data.update(observables=["O-CONSERVATION", "O-CCT"])
    )
    with pytest.raises(adapter.AdapterError, match=r"O-CONSERVATION.*no byte accounting"):
        adapter.validate_experiment(path)


def test_untranslated_workload_kind_rejected(tmp_path):
    path = _manifest_variant(
        tmp_path,
        lambda data: data["workload_ir"].update(
            path="experiments/workloads/w2_dense_tp_prefill_small.yaml"
        ),
    )
    with pytest.raises(
        adapter.AdapterError, match=r"does not translate workload kind 'w2_dense_tp_prefill'"
    ):
        adapter.validate_experiment(path)


def test_untranslated_topology_class_rejected(tmp_path):
    path = _manifest_variant(
        tmp_path,
        lambda data: data["infra_graph"].update(
            path="experiments/topologies/torus2d_8_free_params.yaml"
        ),
    )
    with pytest.raises(adapter.AdapterError, match="torus2d_ring_x_ring"):
        adapter.validate_experiment(path)


def test_rank_mismatch_rejected(tmp_path):
    ring4 = tmp_path / "ring4.yaml"
    ring4.write_text(
        "topology_id: ring4_free_v1\ntopology_class: unidirectional_ring\n"
        "ranks: 4\nlink:\n  bytes_per_ns: 64\n  hop_latency_ns: 200\n",
        encoding="utf-8",
    )
    path = _manifest_variant(
        tmp_path, lambda data: data["infra_graph"].update(path=str(ring4))
    )
    with pytest.raises(adapter.AdapterError, match="tp_size 8 != topology ranks 4"):
        adapter.validate_experiment(path)


def test_wrong_backend_entry_rejected(tmp_path):
    path = _manifest_variant(
        tmp_path, lambda data: data.update(backends=["analytical_l0"])
    )
    with pytest.raises(adapter.AdapterError, match="backends == "):
        adapter.validate_experiment(path)


def test_non_positive_payload_rejected(tmp_path):
    # Zero payload: the shared W1 generator contract rejects degenerate
    # configurations at load time (before the adapter's own chunk_size > 0
    # defense-in-depth gate, which covers future generators with laxer
    # loaders). Either way the rejection is loud and names the gap.
    workload = tmp_path / "w1_zero.yaml"
    workload.write_text(
        "workload: w1_dense_tp_decode\nmodel_name: w1-zero\ntp_size: 8\n"
        "layers: 1\nsteps: 1\nallreduce_bytes: 0\n",
        encoding="utf-8",
    )
    path = _manifest_variant(
        tmp_path, lambda data: data["workload_ir"].update(path=str(workload))
    )
    with pytest.raises(ValueError, match="degenerate W1 configuration"):
        adapter.validate_experiment(path)


def test_execution_surface_exists():
    # Stage S2 replaced the S1 run() gap stub with a full adapter pipeline;
    # the detailed execution tests live in test_astra_sim_execution.py.
    assert callable(adapter.execute_experiment)
    assert callable(adapter.parse_output)
    assert callable(adapter.docker_run_container)
