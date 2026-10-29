"""Q3 stage S1 golden + negative tests: manifest -> uet-htsim translation.

Golden expectations are spelled IN THE TEST, independent of the compiler
under test: an in-test connection-matrix parser (this file) re-derives the
content of the generated ``.cm`` files — node count, connection count, ring
successor mapping, flow sizes, flow ids, per-op totals — from first
principles of the pinned grammar (runbook §4.1), and the exact bytes of the
first and last op files are pinned as literals. All sizes are hand-derived
from the committed free parameters (ring8_free_params.yaml: B = 64 B/ns,
L = 200 ns, ranks 8; w1_dense_tp_decode_small.yaml: 3 steps x 2 layers,
M = 16384 B): per-rank wire bytes 2*(r-1)/r*M = 2*7/8*16384 = 28672, per-op
total 8*28672 = 229376 = 2*(r-1)*M (the O-CONSERVATION identity), flow ids
op_index*8 + rank + 1 (id 0 is rejected by the pinned parser).

Negative tests: every capability gap is rejected explicitly with the gap
named (BackendAdapter contract, IMPLEMENTATION_GUIDE §5).
"""

from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.backends.uet_htsim import adapter

REPO = Path(__file__).resolve().parents[2]
UET_MANIFEST = (
    REPO / "experiments" / "vertical_slice" / "w1_decode_smoke_uet.yaml"
)
COMPILED_DIR = REPO / "experiments" / "vertical_slice" / "uet_w1_decode_smoke_uet"

# Hand-derived from the committed free parameters (see module docstring).
RANKS = 8
OPS = 6  # 3 steps x 2 layers, step-major layer-minor
PAYLOAD = 16384
PER_RANK_WIRE = 28672  # 2*7/8*16384
PER_OP_TOTAL = 229376  # 8*28672 == 2*(r-1)*M
FABRIC_NODES = 16
EXPECTED_OP_ORDER = [
    f"s{step:06d}-l{layer:06d}-allreduce"
    for step in range(3)
    for layer in range(2)
]


# --- in-test connection-matrix parser (independent of adapter.py) ----------


def parse_cm(path: Path) -> dict:
    """Parse the runbook section 4.1 grammar from first principles:
    `Nodes N` / `Connections M` header, then `src->dst [k v]...` lines."""
    header: dict[str, int] = {}
    connections = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        if "->" in tokens[0]:
            src, dst = tokens[0].split("->")
            fields: dict[str, str] = {}
            rest = tokens[1:]
            for key, value in zip(rest[0::2], rest[1::2]):
                assert key in ("start", "size", "id", "msg", "trigger"), (
                    f"unknown connection token {key!r}"
                )
                fields[key] = value
            connections.append(
                {"src": int(src), "dst": int(dst), **fields}
            )
        else:
            assert len(tokens) == 2, f"header line is key-value: {line!r}"
            header[tokens[0]] = int(tokens[1])
    return {"header": header, "connections": connections}


# --- golden: W1 translation content, spelled in the test --------------------


def test_w1_cm_first_and_last_op_bytes_pinned():
    # Exact bytes of the first and last op files, spelled literally.
    first = (
        "Nodes 16\n"
        "Connections 8\n"
        "0->1 start 0 size 28672 id 1\n"
        "1->2 start 0 size 28672 id 2\n"
        "2->3 start 0 size 28672 id 3\n"
        "3->4 start 0 size 28672 id 4\n"
        "4->5 start 0 size 28672 id 5\n"
        "5->6 start 0 size 28672 id 6\n"
        "6->7 start 0 size 28672 id 7\n"
        "7->0 start 0 size 28672 id 8\n"
    )
    last = (
        "Nodes 16\n"
        "Connections 8\n"
        "0->1 start 0 size 28672 id 41\n"
        "1->2 start 0 size 28672 id 42\n"
        "2->3 start 0 size 28672 id 43\n"
        "3->4 start 0 size 28672 id 44\n"
        "4->5 start 0 size 28672 id 45\n"
        "5->6 start 0 size 28672 id 46\n"
        "6->7 start 0 size 28672 id 47\n"
        "7->0 start 0 size 28672 id 48\n"
    )
    stem = COMPILED_DIR / "w1_decode_smoke_uet"
    assert (stem.with_name(stem.name + ".op000000.cm")).read_text(
        encoding="utf-8"
    ) == first
    assert (stem.with_name(stem.name + ".op000005.cm")).read_text(
        encoding="utf-8"
    ) == last


def test_w1_cm_structure_all_ops():
    # One matrix per op (6), each: Nodes 16 fabric header (A-UET1-FABRIC),
    # 8 connections = one flow per rank to its ring SUCCESSOR with wrap
    # 7->0 (A-UET1-WIRE), every size 28672 = 2*(r-1)/r*M, start 0
    # (A-UET1-OPFILE), flow ids op_index*8+rank+1 — never 0 (A-UET1-IDS).
    for op_index in range(OPS):
        parsed = parse_cm(
            COMPILED_DIR / f"w1_decode_smoke_uet.op{op_index:06d}.cm"
        )
        assert parsed["header"] == {
            "Nodes": FABRIC_NODES,
            "Connections": RANKS,
        }
        assert len(parsed["connections"]) == RANKS
        for rank in range(RANKS):
            conn = parsed["connections"][rank]
            assert conn["src"] == rank
            assert conn["dst"] == (rank + 1) % RANKS  # ring successor, wraps
            assert conn["start"] == "0"
            assert conn["size"] == str(PER_RANK_WIRE)
            assert conn["id"] == str(op_index * RANKS + rank + 1)
            assert int(conn["id"]) != 0  # parser rejects flow id 0


def test_w1_cm_emits_the_declared_conservation_pattern():
    # The emitted traffic IS the L0 ring identity's declared logical wire
    # pattern: per-op total over all flows = 2*(r-1)*M exactly (229376),
    # and every rank sends exactly 2*(r-1)/r*M (O-TRAFFIC-IMBALANCE's
    # relation) — exact Fraction arithmetic in the test.
    assert 2 * (RANKS - 1) * PAYLOAD // RANKS == PER_RANK_WIRE
    for op_index in range(OPS):
        parsed = parse_cm(
            COMPILED_DIR / f"w1_decode_smoke_uet.op{op_index:06d}.cm"
        )
        total = sum(int(c["size"]) for c in parsed["connections"])
        assert Fraction(total) == Fraction(2 * (RANKS - 1)) * PAYLOAD
        assert total == PER_OP_TOTAL


def test_compile_plan_records_provenance_and_exact_conversions():
    import json

    plan = json.loads(
        (COMPILED_DIR / "compile_plan.json").read_text(encoding="utf-8")
    )
    assert plan["backend_id"] == "uet_htsim_cms"
    assert plan["pin"]["uet_htsim_commit"] == (
        "65ea315b25725df9791a5b93b61cbd6938cba0a8"
    )
    assert plan["pin"]["binary_sha256"] == (
        "fe5a1c645719b792bb56c631fbd991cf7f6c824af8a97f42971bd59b584cd896"
    )
    assert plan["workload"]["ops_per_rank"] == OPS
    assert plan["workload"]["op_order"] == EXPECTED_OP_ORDER
    assert plan["workload"]["per_rank_wire_bytes"] == PER_RANK_WIRE
    assert plan["workload"]["per_op_wire_bytes_total"] == PER_OP_TOTAL
    assert "none in the simulator" in plan["workload"]["collective_semantics"]
    # Exact CLI conversions, spelled: B = 64 B/ns -> 512000 Mbps (8000*B),
    # L = 200 ns -> 0.2 us, manifest seed explicit (default is 13).
    flags = plan["binary_cli"]["flags_from_manifest"]
    assert flags["-linkspeed"].startswith("512000 (")
    assert flags["-hop_latency"].startswith("0.2 (")
    assert flags["-seed"].startswith("20261026 (")
    assert plan["binary_cli"]["flags_at_upstream_defaults"]["-sender_cc_algo"] == "nscc"
    assert plan["binary_cli"]["flags_at_upstream_defaults"]["-mtu"] == 4150
    assert "stage S2" in plan["binary_cli"]["verification_status"]
    assert plan["fabric"] == {
        "nodes": FABRIC_NODES,
        "ranks_placed": RANKS,
        "idle_hosts": FABRIC_NODES - RANKS,
        "auto_topology": (
            "3-tier fat tree at pinned defaults, 100 Gbps unless "
            "-linkspeed overrides (A-UET1-FABRIC)"
        ),
    }
    assert plan["topology"]["realization"].startswith("logical traffic pattern")
    free = {p["name"]: p for p in plan["free_parameters"]}
    assert free["link.bytes_per_ns"]["assumption"] == "A-L0-BW"
    assert free["link.hop_latency_ns"]["assumption"] == "A-L0-LAT"
    assert free["workload.allreduce_bytes"]["assumption"] == "A-W1-SIZE"
    assumption_ids = {a["id"] for a in plan["translation_assumptions"]}
    assert {
        "A-UET1-WIRE",
        "A-UET1-OPFILE",
        "A-UET1-FABRIC",
        "A-UET1-BW",
        "A-UET1-LAT",
        "A-UET1-SEED",
        "A-UET1-IDS",
    } <= assumption_ids
    # Every recorded file hash matches the file on disk.
    for relative, sha in plan["files"].items():
        assert adapter.contracts.sha256_of(COMPILED_DIR / relative) == sha


def test_translation_snapshot_is_byte_identical_on_regeneration(tmp_path):
    # Snapshot: recompiling the committed manifest reproduces every byte of
    # the committed input set (translation determinism; no wall-clock, no
    # environment leakage).
    adapter.compile_experiment(UET_MANIFEST, tmp_path)
    committed = sorted(p for p in COMPILED_DIR.rglob("*") if p.is_file())
    assert len(committed) == OPS + 1  # 6 matrices + compile_plan.json
    for path in committed:
        regenerated = tmp_path / path.relative_to(COMPILED_DIR)
        assert regenerated.is_file(), f"missing {regenerated}"
        assert regenerated.read_bytes() == path.read_bytes(), f"differs: {path}"


def test_exact_unit_conversions():
    # 64 B/ns == 512000 Mbps exactly (1 B/ns = 8000 Mbit/s); 200 ns ==
    # 0.2 us exactly. Exactness asserted as Fractions in the test.
    assert adapter.bandwidth_mbps(Fraction(64)) == 512000
    assert Fraction(adapter.bandwidth_mbps(Fraction(64))) == Fraction(64) * 8000
    assert adapter.hop_latency_us(Fraction(200)) == "0.2"
    assert Fraction(adapter.hop_latency_us(Fraction(200))) == Fraction(1, 5)


# --- capabilities (loud declaration, mirrored from the pin) -----------------


def test_capabilities_declare_gaps_loudly():
    caps = adapter.capabilities()
    assert caps["backend_id"] == "uet_htsim_cms"
    # THE loud one: no collective semantics exist in this simulator.
    assert caps["collectives"] == ()
    unsupported = set(caps["explicitly_unsupported"])
    assert "native_collective_semantics" in unsupported
    # The README's own non-goals: research platform, not the CMS spec.
    assert "normative_uec_cms_semantics" in unsupported
    assert "non-normative" in caps["transport_model"]
    # The fabric is a fat tree; a physical ring is not expressible.
    assert "ring_fabric_topology" in unsupported
    assert "compute_model" in unsupported
    assert "scale_up_memory_semantics" in unsupported
    assert "standard_specific_semantics" in unsupported
    # No honest byte ledger: conservation unsupported at this stage.
    assert "O-CONSERVATION" in unsupported
    assert set(caps["observables"]) == {"O-CCT"}


def test_execution_surface_landed_with_stage_s2():
    # Stage S1 pinned the ABSENCE of execute_experiment so stage S2 had to
    # land execution deliberately; it did (container execution, stdout FCT
    # parsing, orchestrator registration — see
    # tests/backends/test_uet_htsim_execution.py). The boundary assertion
    # is now the positive one.
    assert callable(adapter.execute_experiment)
    assert callable(adapter.docker_run_container)
    assert callable(adapter.parse_output)
    assert callable(adapter.capabilities)
    assert callable(adapter.validate_experiment)
    assert callable(adapter.compile_experiment)


# --- negative: capability gaps rejected with the gap named ------------------


def _manifest_variant(tmp_path, mutate, name="variant.yaml"):
    data = yaml.safe_load(UET_MANIFEST.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_unsupported_observable_rejected_naming_gap(tmp_path):
    path = _manifest_variant(
        tmp_path, lambda data: data.update(observables=["O-CONSERVATION", "O-CCT"])
    )
    with pytest.raises(
        adapter.AdapterError,
        match=r"O-CONSERVATION.*byte counters.*include packet overhead",
    ):
        adapter.validate_experiment(path)


def test_unsupported_logical_observable_rejected(tmp_path):
    # O-TRAFFIC-IMBALANCE is registered platform-wide but not emitted by
    # this backend — also rejected, named, without the conservation detail.
    path = _manifest_variant(
        tmp_path,
        lambda data: data.update(observables=["O-TRAFFIC-IMBALANCE"]),
    )
    with pytest.raises(
        adapter.AdapterError, match=r"does not support observable\(s\) \['O-TRAFFIC-IMBALANCE'\]"
    ):
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


def test_ranks_beyond_verified_fabric_rejected(tmp_path):
    # ranks 32: only the Nodes-16 smoke-verified fat-tree shape is
    # declared; larger fabrics are an untranslated gap (A-UET1-FABRIC).
    topo = tmp_path / "ring32.yaml"
    topo.write_text(
        "topology_id: ring32_free_v1\ntopology_class: unidirectional_ring\n"
        "ranks: 32\nlink:\n  bytes_per_ns: 64\n  hop_latency_ns: 200\n",
        encoding="utf-8",
    )
    workload = tmp_path / "w1_tp32.yaml"
    workload.write_text(
        "workload: w1_dense_tp_decode\nmodel_name: w1-tp32\ntp_size: 32\n"
        "layers: 1\nsteps: 1\nallreduce_bytes: 16384\n",
        encoding="utf-8",
    )
    path = _manifest_variant(
        tmp_path,
        lambda data: (
            data["infra_graph"].update(path=str(topo)),
            data["workload_ir"].update(path=str(workload)),
        ),
    )
    with pytest.raises(
        adapter.AdapterError, match=r"outside the translatable range 2\.\.16"
    ):
        adapter.validate_experiment(path)


def test_non_divisible_payload_rejected(tmp_path):
    # M = 16388 is not divisible by r = 8: no equal-chunk wire pattern, so
    # no integral flow size 2*(r-1)/r*M exists (A-UET1-WIRE, mirroring the
    # L0 divisibility gate A-L0-DIV).
    workload = tmp_path / "w1_ragged.yaml"
    workload.write_text(
        "workload: w1_dense_tp_decode\nmodel_name: w1-ragged\ntp_size: 8\n"
        "layers: 1\nsteps: 1\nallreduce_bytes: 16388\n",
        encoding="utf-8",
    )
    path = _manifest_variant(
        tmp_path, lambda data: data["workload_ir"].update(path=str(workload))
    )
    with pytest.raises(
        adapter.AdapterError, match=r"not divisible by ranks 8.*A-UET1-WIRE"
    ):
        adapter.validate_experiment(path)


def test_inexact_bandwidth_rejected(tmp_path):
    # B = 1/3 B/ns has no exact integral -linkspeed Mbps value (A-UET1-BW):
    # rejected rather than silently rounded — through the full validate
    # path (the conversion is a validation gate, not a silent write).
    topo = tmp_path / "ring_third.yaml"
    topo.write_text(
        "topology_id: ring_third_v1\ntopology_class: unidirectional_ring\n"
        "ranks: 8\nlink:\n  bytes_per_ns: 1/3\n  hop_latency_ns: 200\n",
        encoding="utf-8",
    )
    path = _manifest_variant(
        tmp_path, lambda data: data["infra_graph"].update(path=str(topo))
    )
    with pytest.raises(adapter.AdapterError, match="no exact integral -linkspeed"):
        adapter.validate_experiment(path)


def test_inexact_hop_latency_rejected(tmp_path):
    # L = 1/3 ns has no exact finite decimal us form (A-UET1-LAT).
    topo = tmp_path / "ring_thirdlat.yaml"
    topo.write_text(
        "topology_id: ring_thirdlat_v1\ntopology_class: unidirectional_ring\n"
        "ranks: 8\nlink:\n  bytes_per_ns: 64\n  hop_latency_ns: 1/3\n",
        encoding="utf-8",
    )
    path = _manifest_variant(
        tmp_path, lambda data: data["infra_graph"].update(path=str(topo))
    )
    with pytest.raises(
        adapter.AdapterError, match="no exact finite decimal us form"
    ):
        adapter.validate_experiment(path)


def test_seed_out_of_uint_range_rejected(tmp_path):
    path = _manifest_variant(tmp_path, lambda data: data.update(seed=2**33))
    with pytest.raises(adapter.AdapterError, match="outside the -seed UINT range"):
        adapter.validate_experiment(path)


def test_wrong_backend_entry_rejected(tmp_path):
    path = _manifest_variant(
        tmp_path, lambda data: data.update(backends=["analytical_l0"])
    )
    with pytest.raises(adapter.AdapterError, match="backends == "):
        adapter.validate_experiment(path)
