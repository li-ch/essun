"""Q6 stage S4 — cross-design flavor-config honesty contract.

The first UEC-vs-UnifiedBus same-workload L0 comparison
(experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml) must stay
honest BY CONSTRUCTION, not by prose:

- equal free parameters across flavors (any single-file drift trips);
- the UB flavor's rank count is ANCHORED (UBP-P17, PAPER_REPORTED), with a
  resolvable anchor chain and an S3-map-backed identity;
- honesty labels ("paper-derived design profile, NOT a normative standard
  profile"; "no UEC-derived numeric value") live in the artifacts
  themselves and cannot be silently dropped;
- the sweep table's coincidence anchor holds: the UB row and the
  identity-matched UEC control produce byte-identical O-CCT (delta
  exactly 0) — differences in the table are anchored structure or free
  identity choices, never unequal free parameters.
"""

import copy
import json
from pathlib import Path

import pytest
import yaml

from essun.orchestrator.sweeps import run_sweep
from essun.specir.unifiedbus_l0_flavors import (
    BASELINE,
    COMPARISON_RANKS,
    FLAVOR_TOPOLOGIES,
    NV_PAPER_TOPOLOGY,
    NV_PROFILE_MARKER,
    NV_RANK_SCALE_MARKER,
    ASSUMPTIONS_PATH,
    SHARED_FREE_B_BYTES_PER_NS,
    SHARED_FREE_L_NS,
    SWEEP_3ARCH_MANIFEST_PATH,
    SWEEP_3ARCH_NAME,
    SWEEP_MANIFEST_PATH,
    THREE_ARCH_PAYLOAD_SIZES,
    THREE_ARCH_TOPOLOGIES,
    UB_PROFILE_MARKER,
    UEC_FREE_MARKER,
    assert_flavors_valid,
    assumptions_problems,
    flavor_file_problems,
    flavor_problems,
    workload_manifest_problems,
)

REPO = Path(__file__).resolve().parents[2]


def _load_yaml(rel_path: str) -> dict:
    return yaml.safe_load((REPO / rel_path).read_text(encoding="utf-8"))


def _flavor(spec_path: str):
    for spec in FLAVOR_TOPOLOGIES:
        if spec.path == spec_path:
            return spec
    raise AssertionError(f"no flavor spec for {spec_path}")


# ---------------------------------------------------------------------------
# The committed contract, checked whole
# ---------------------------------------------------------------------------


def test_flavor_contract_valid_on_committed_artifacts():
    assert_flavors_valid(REPO)


def test_flavor_problems_empty():
    assert flavor_problems(REPO) == []


# ---------------------------------------------------------------------------
# Equal free parameters (mechanical, re-read from the shared record)
# ---------------------------------------------------------------------------


def test_shared_free_parameters_equal_across_all_flavors():
    record = _load_yaml(ASSUMPTIONS_PATH)
    shared_b = next(
        a["value"] for a in record["assumptions"] if a["id"] == "A-XDUO-BW"
    )
    shared_l = next(
        a["value"] for a in record["assumptions"] if a["id"] == "A-XDUO-LAT"
    )
    assert shared_b == SHARED_FREE_B_BYTES_PER_NS
    assert shared_l == SHARED_FREE_L_NS

    for spec in FLAVOR_TOPOLOGIES:
        data = _load_yaml(spec.path)
        assert spec.knob_value(data, spec.bandwidth_knob) == shared_b, (
            f"{spec.path}: bandwidth knob unequal to the shared free parameter"
        )
        assert spec.knob_value(data, spec.latency_knob) == shared_l, (
            f"{spec.path}: latency knob unequal to the shared free parameter"
        )


# ---------------------------------------------------------------------------
# Anchored rank scale + identity (UB flavor is not a free choice)
# ---------------------------------------------------------------------------


def test_ub_rank_scale_anchored_and_resolvable():
    from essun.specir import unifiedbus_paper_profile as profile
    from essun.specir.unifiedbus_sources import PaperAnchorRegistry

    registry = PaperAnchorRegistry.load(repo_root=REPO)
    rank = next(
        p for p in profile.parameters() if p.parameter_id == "UBP-P17"
    )
    assert rank.evidence_grade == "PAPER_REPORTED"
    assert "UBP-UBMESH-3.3.1-RACK-64NPU" in rank.anchor_ids
    for anchor_id in rank.anchor_ids:
        assert anchor_id in registry.by_id()
    data = _load_yaml("experiments/topologies/crossbar64_ub_rack_free_params.yaml")
    assert data["ranks"] == COMPARISON_RANKS == 64


def test_tampered_ub_ranks_flagged():
    spec = _flavor("experiments/topologies/crossbar64_ub_rack_free_params.yaml")
    text = (REPO / spec.path).read_text(encoding="utf-8")
    data = _load_yaml(spec.path)
    tampered = copy.deepcopy(data)
    tampered["ranks"] = 1024  # P18 pod scale smuggled into a same-workload grid
    problems = flavor_file_problems(spec, text, tampered)
    assert any("ranks" in problem and "UBP-P17" in problem for problem in problems)


def test_tampered_bandwidth_breaks_equality():
    spec = _flavor("experiments/topologies/crossbar64_ub_rack_free_params.yaml")
    text = (REPO / spec.path).read_text(encoding="utf-8")
    data = _load_yaml(spec.path)
    tampered = copy.deepcopy(data)
    tampered["nic"]["injection_bytes_per_ns"] = 89  # a "UB-favoring" tune
    problems = flavor_file_problems(spec, text, tampered)
    assert any("shared free parameter" in problem for problem in problems)


# ---------------------------------------------------------------------------
# Honesty labels must stay in the artifacts
# ---------------------------------------------------------------------------


def test_ub_file_requires_paper_profile_marker_and_silence_citations():
    spec = _flavor("experiments/topologies/crossbar64_ub_rack_free_params.yaml")
    text = (REPO / spec.path).read_text(encoding="utf-8")
    data = _load_yaml(spec.path)

    # Strip fold-robustly: break the marker's load-bearing words wherever
    # they wrap in the comment block.
    stripped = text
    for word in ("PAPER-DERIVED", "paper-derived", "NORMATIVE", "normative"):
        stripped = stripped.replace(word, "X")
    problems = flavor_file_problems(spec, stripped, data)
    assert any(UB_PROFILE_MARKER in problem for problem in problems)

    for missing in ("UBP-F01", "UBP-F02", "UBP-P07"):
        problems = flavor_file_problems(spec, text.replace(missing, ""), data)
        assert any(missing in problem for problem in problems)


def test_uec_files_must_disclaim_uec_derived_values():
    spec = _flavor("experiments/topologies/ring64_uec_free_params.yaml")
    text = (REPO / spec.path).read_text(encoding="utf-8")
    data = _load_yaml(spec.path)
    stripped = text.replace("no UEC-derived numeric value", "some value")
    problems = flavor_file_problems(spec, stripped, data)
    assert any(UEC_FREE_MARKER in problem for problem in problems)


# ---------------------------------------------------------------------------
# Manifest / workload gates
# ---------------------------------------------------------------------------


def test_manifest_grid_is_exactly_the_declared_flavor_set():
    workload = _load_yaml("experiments/workloads/w1_dense_tp_decode_rack64.yaml")
    manifest = _load_yaml(SWEEP_MANIFEST_PATH)

    rogue = copy.deepcopy(manifest)
    rogue["grid"]["algorithms"][0]["topologies"].append(
        "experiments/topologies/ring8_free_params.yaml"
    )
    problems = workload_manifest_problems(workload, rogue)
    assert any("flavor grid" in problem for problem in problems)

    swapped = copy.deepcopy(manifest)
    swapped["baseline"] = {
        "algorithm": "allreduce_ring",
        "topology": "experiments/topologies/ring64_uec_free_params.yaml",
    }
    problems = workload_manifest_problems(workload, swapped)
    assert any("baseline" in problem for problem in problems)

    resized = copy.deepcopy(workload)
    resized["tp_size"] = 8
    problems = workload_manifest_problems(resized, manifest)
    assert any("tp_size" in problem for problem in problems)


def test_assumptions_record_shape_enforced():
    record = _load_yaml(ASSUMPTIONS_PATH)

    tuned = copy.deepcopy(record)
    tuned["assumptions"][0]["value"] = 89  # A-XDUO-BW drifted from the files
    problems = assumptions_problems(tuned)
    assert any("A-XDUO-BW.value" in problem for problem in problems)

    promoted = copy.deepcopy(record)
    promoted["status"] = "VERIFIED"
    problems = assumptions_problems(promoted)
    assert any("PROPOSED" in problem for problem in problems)


# ---------------------------------------------------------------------------
# The sweep itself: determinism + the delta-0 coincidence anchor + a
# hand-computed golden cell
# ---------------------------------------------------------------------------


def _run(tmp_path: Path) -> dict:
    return run_sweep(REPO / SWEEP_MANIFEST_PATH, results_root=tmp_path)


def _rows(table: dict) -> dict:
    return {
        (row["config_id"].rsplit("-", 1)[0], row["payload_bytes"]): row
        for row in table["configs"]
    }


def test_sweep_deterministic_and_coincidence_anchor_holds(tmp_path):
    first = _run(tmp_path / "a")
    second = _run(tmp_path / "b")
    assert first["sweep_id"] == second["sweep_id"]

    def artifacts(root: Path) -> dict[str, bytes]:
        sweep_dir = root / "sweeps" / first["sweep_id"]
        return {
            name: (sweep_dir / name).read_bytes()
            for name in ("table.json", "table.md")
        }

    assert artifacts(tmp_path / "a") == artifacts(tmp_path / "b")

    rows = _rows(first["table"])
    for payload in (16384, 1048576):
        ub = rows[("c0002-allreduce_crossbar-ub_rack64_crossbar_v1", payload)]
        uec = rows[("c0001-allreduce_crossbar-uec_free_crossbar64_v1", payload)]
        # The honesty anchor: under equal free parameters and the anchored
        # identity, L0 does not distinguish the flavors at all.
        assert ub["delta_vs_baseline"]["delta_exact"] == "0"
        assert (
            ub["o_cct"]["completion_time_ns_mean_exact"]
            == uec["o_cct"]["completion_time_ns_mean_exact"]
        )
        assert ub["per_rank_wire_bytes_exact"] == uec["per_rank_wire_bytes_exact"]


def test_crossbar_identity_golden_cell(tmp_path):
    # Hand-computed crossbar AllReduce identity at r=64, B=64 B/ns, L=200 ns:
    # t = 2 * ((r-1)/r * M/B + L). M=16384 -> 2*(252+200) = 904 ns;
    # M=1048576 -> 2*(16128+200) = 32656 ns. Both flavors must hit BOTH.
    result = _run(tmp_path)
    rows = _rows(result["table"])
    expected = {16384: "904", 1048576: "32656"}
    for prefix in (
        "c0001-allreduce_crossbar-uec_free_crossbar64_v1",
        "c0002-allreduce_crossbar-ub_rack64_crossbar_v1",
    ):
        for payload, cct in expected.items():
            assert rows[(prefix, payload)]["o_cct"]["completion_time_ns_mean_exact"] == cct


def test_table_json_carries_provenance_hashes(tmp_path):
    result = _run(tmp_path)
    table = result["table"]
    assert table["workload"]["tp_size"] == COMPARISON_RANKS
    assert table["baseline"]["algorithm"] == BASELINE[0]
    for row in table["configs"]:
        assert set(row["input_hashes"]) == {"workload_sha256", "topology_sha256"}
        assert len(row["input_hashes"]["topology_sha256"]) == 64


# ---------------------------------------------------------------------------
# The M1 NVLink-paper flavor (third fabric): matched-free rank scale,
# marker + silence citations, the three-architecture manifest gate, and
# the sweep's three-way delta-0 anchor
# ---------------------------------------------------------------------------


def test_nv_rank_scale_is_matched_free_and_flagged_when_stripped():
    # The anchored NVLink domain is 72 (NVP-P13); the flavor runs at the
    # shared workload's 64 as a STATED matched-free choice. Stripping the
    # statement (in any case or line-wrap form) trips the check.
    import re

    text = (REPO / NV_PAPER_TOPOLOGY.path).read_text(encoding="utf-8")
    data = _load_yaml(NV_PAPER_TOPOLOGY.path)

    stripped = re.sub(r"(?i)matched\s*-\s*free", "X", text)
    problems = flavor_file_problems(NV_PAPER_TOPOLOGY, stripped, data)
    assert any(NV_RANK_SCALE_MARKER in problem for problem in problems)


def test_tampered_nv_ranks_flagged_naming_the_domain_anchor():
    data = _load_yaml(NV_PAPER_TOPOLOGY.path)
    text = (REPO / NV_PAPER_TOPOLOGY.path).read_text(encoding="utf-8")
    tampered = copy.deepcopy(data)
    tampered["ranks"] = 72  # the anchored domain smuggled into a tp=64 grid
    problems = flavor_file_problems(NV_PAPER_TOPOLOGY, text, tampered)
    assert any("ranks" in problem and "NVP-P13" in problem for problem in problems)


def test_nv_file_requires_marker_and_silence_citations():
    text = (REPO / NV_PAPER_TOPOLOGY.path).read_text(encoding="utf-8")
    data = _load_yaml(NV_PAPER_TOPOLOGY.path)

    stripped = text
    for word in ("PAPER-DERIVED", "paper-derived", "NORMATIVE", "normative"):
        stripped = stripped.replace(word, "X")
    problems = flavor_file_problems(NV_PAPER_TOPOLOGY, stripped, data)
    assert any(NV_PROFILE_MARKER in problem for problem in problems)

    for missing in ("NVP-F01", "NVP-F02", "NVP-F03", "NVP-P01", "NVP-P13"):
        problems = flavor_file_problems(
            NV_PAPER_TOPOLOGY, text.replace(missing, ""), data
        )
        assert any(missing in problem for problem in problems)


def test_three_arch_manifest_grid_is_exactly_the_three_crossbars():
    workload = _load_yaml("experiments/workloads/w1_dense_tp_decode_rack64.yaml")
    manifest = _load_yaml(SWEEP_3ARCH_MANIFEST_PATH)

    # positive: the committed manifest is exactly the declared three
    problems = workload_manifest_problems(
        workload,
        manifest,
        sweep_name=SWEEP_3ARCH_NAME,
        expected_topologies=THREE_ARCH_TOPOLOGIES,
        payload_sizes=THREE_ARCH_PAYLOAD_SIZES,
    )
    assert problems == []

    # a fourth, unprovenanced row is rejected
    rogue = copy.deepcopy(manifest)
    rogue["grid"]["algorithms"][0]["topologies"].append(
        "experiments/topologies/ring64_uec_free_params.yaml"
    )
    problems = workload_manifest_problems(
        workload, rogue, sweep_name=SWEEP_3ARCH_NAME,
        expected_topologies=THREE_ARCH_TOPOLOGIES,
        payload_sizes=THREE_ARCH_PAYLOAD_SIZES,
    )
    assert any("flavor grid" in problem for problem in problems)

    # dropping the NV row is rejected too (every declared row required)
    missing = copy.deepcopy(manifest)
    missing["grid"]["algorithms"][0]["topologies"].pop()
    problems = workload_manifest_problems(
        workload, missing, sweep_name=SWEEP_3ARCH_NAME,
        expected_topologies=THREE_ARCH_TOPOLOGIES,
        payload_sizes=THREE_ARCH_PAYLOAD_SIZES,
    )
    assert any("flavor grid" in problem for problem in problems)


def test_nv_provenance_chain_resolves_in_the_m1_registry():
    from essun.specir import nvlink_paper_profile as nv_profile
    from essun.specir.unifiedbus_sources import PaperAnchorRegistry

    registry = PaperAnchorRegistry.load(
        path=REPO / "experiments/nvlink/anchor_registry.yaml", repo_root=REPO
    )
    registry.assert_valid()
    identity = next(
        p for p in nv_profile.parameters() if p.parameter_id == "NVP-P01"
    )
    domain = next(
        p for p in nv_profile.parameters() if p.parameter_id == "NVP-P13"
    )
    assert identity.evidence_grade == "PAPER_REPORTED"
    assert domain.evidence_grade == "VENDOR_CLAIMED"
    assert "72" in domain.as_reported
    for param in (identity, domain):
        for anchor_id in param.anchor_ids:
            assert anchor_id in registry.by_id()


def test_three_arch_sweep_three_way_delta_zero(tmp_path):
    # The M1 honesty anchor: under the one shared B/L record, ALL THREE
    # architectures' crossbar rows tie exactly at every payload size.
    first = run_sweep(REPO / SWEEP_3ARCH_MANIFEST_PATH, results_root=tmp_path / "a")
    second = run_sweep(REPO / SWEEP_3ARCH_MANIFEST_PATH, results_root=tmp_path / "b")
    assert first["sweep_id"] == second["sweep_id"]

    by_topo = {}
    for row in first["table"]["configs"]:
        suffix = row["topology"]["path"].rsplit("/", 1)[-1]
        by_topo.setdefault(suffix, {})[row["payload_bytes"]] = row
    assert len(by_topo) == 3
    sizes = sorted(next(iter(by_topo.values())))
    assert sizes == list(THREE_ARCH_PAYLOAD_SIZES)
    topos = (
        "crossbar64_uec_free_params.yaml",
        "crossbar64_ub_rack_free_params.yaml",
        "crossbar64_nvl_rack_free_params.yaml",
    )
    for size in sizes:
        values = {
            by_topo[topo][size]["o_cct"]["completion_time_ns_mean_exact"]
            for topo in topos
        }
        assert len(values) == 1, f"three-way tie broken at payload {size}"
    for size in sizes:
        wires = {
            by_topo[topo][size]["per_rank_wire_bytes_exact"] for topo in topos
        }
        assert len(wires) == 1  # one wire identity across three fabrics
    for topo in topos:
        for size in sizes:
            row = by_topo[topo][size]
            assert row["delta_vs_baseline"]["delta_exact"] == "0"
            assert row["o_conservation"]["violations"] == 0
