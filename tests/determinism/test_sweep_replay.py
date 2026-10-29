"""P3 sweep determinism, capability gate, and golden table cell.

Three frozen readouts of the sweep runner (prompts/p3_sweep_runner.md):

1. determinism — identical manifest + code version produce byte-identical
   ``table.json`` / ``table.md`` (and the rerun into the SAME root is
   idempotent, never a rewrite);
2. capability gate — a grid referencing an UNKNOWN algorithm fails with an
   explicit error before anything executes (and an undeclared
   algorithm/topology-class pairing is likewise rejected explicitly);
3. golden — one hand-computed table cell pins the runner end-to-end.
"""

import json
from pathlib import Path

import pytest
import yaml

from essun.orchestrator.sweeps import SweepError, run_sweep

REPO = Path(__file__).resolve().parents[2]
SWEEP_MANIFEST = REPO / "experiments" / "sweeps" / "l0_allreduce_design_space_v1.yaml"


def _load_committed_manifest() -> dict:
    return yaml.safe_load(SWEEP_MANIFEST.read_text(encoding="utf-8"))


def _write_manifest(manifest: dict, tmp_path: Path) -> Path:
    path = tmp_path / "sweep.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def _table_bytes(root: Path, sweep_id: str) -> dict[str, bytes]:
    sweep_dir = root / "sweeps" / sweep_id
    return {
        artifact: (sweep_dir / artifact).read_bytes()
        for artifact in ("table.json", "table.md")
    }


def test_rerun_produces_byte_identical_tables(tmp_path):
    first = run_sweep(SWEEP_MANIFEST, results_root=tmp_path / "a")
    second = run_sweep(SWEEP_MANIFEST, results_root=tmp_path / "b")

    assert first["sweep_id"] == second["sweep_id"]
    left = _table_bytes(tmp_path / "a", first["sweep_id"])
    right = _table_bytes(tmp_path / "b", second["sweep_id"])
    for artifact in ("table.json", "table.md"):
        assert left[artifact] == right[artifact], f"{artifact} differs between replays"


def test_rerun_into_same_root_is_idempotent(tmp_path):
    first = run_sweep(SWEEP_MANIFEST, results_root=tmp_path)
    second = run_sweep(SWEEP_MANIFEST, results_root=tmp_path)  # must not rewrite

    assert first["sweep_id"] == second["sweep_id"]
    assert first["sweep_dir"] == second["sweep_dir"]
    assert _table_bytes(tmp_path, first["sweep_id"]) == _table_bytes(
        tmp_path, second["sweep_id"]
    )


def test_unknown_algorithm_rejected_before_execution(tmp_path):
    manifest = _load_committed_manifest()
    manifest["grid"]["algorithms"][0]["algorithm"] = "allreduce_quantum_teleport"
    path = _write_manifest(manifest, tmp_path)

    with pytest.raises(SweepError, match="unknown algorithm.*allreduce_quantum_teleport"):
        run_sweep(path, results_root=tmp_path / "results")

    # Explicit refusal, not a partial sweep: nothing was written.
    assert not (tmp_path / "results" / "sweeps").exists()


def test_undeclared_fabric_pairing_rejected(tmp_path):
    # The ring AllReduce identity is declared for the unidirectional-ring
    # fabric only; running it on the crossbar fabric is a DIFFERENT identity
    # and must be rejected by the per-config capability gate.
    manifest = _load_committed_manifest()
    manifest["grid"]["algorithms"] = [
        {
            "algorithm": "allreduce_ring",
            "topologies": [
                "experiments/topologies/crossbar8_free_params.yaml"
            ],
        }
    ]
    path = _write_manifest(manifest, tmp_path)

    with pytest.raises(SweepError, match="not.*declared for topology_class"):
        run_sweep(path, results_root=tmp_path / "results")

    assert not (tmp_path / "results" / "sweeps").exists()


def test_golden_table_cell_hand_computed(tmp_path):
    """Hand-derived cell: allreduce_ring, ring8_free_v1, M = 16384, r = 8,
    B = 64 bytes/ns, L = 200 ns, workload = 2 layers x 3 steps (6 ops).

    Independent derivation (landed identity, recomputed here):
      per-rank wire  2*(7/8)*16384          = 28672 B
      completion     28672/64 + 2*7*200     = 448 + 2800 = 3248 ns
      total wire     6 * 2*7*16384          = 1376256 B
    Crossbar cell at the same size: t = 2*(14336/64) + 2*200 = 848 ns, so the
    delta vs the ring baseline is (848-3248)/3248 = -2400/3248 = -150/203.
    """
    result = run_sweep(SWEEP_MANIFEST, results_root=tmp_path)
    table = json.loads(
        (result["sweep_dir"] / "table.json").read_text(encoding="utf-8")
    )

    def cell(algorithm: str, payload: int) -> dict:
        return next(
            c
            for c in table["configs"]
            if c["algorithm"] == algorithm and c["payload_bytes"] == payload
        )

    ring = cell("allreduce_ring", 16384)
    assert ring["o_cct"]["completion_time_ns_mean_exact"] == "3248"
    assert ring["o_cct"]["completion_time_ns_mean"] == 3248.0
    assert ring["o_conservation"]["violations"] == 0
    assert ring["o_conservation"]["total_wire_bytes_exact"] == "1376256"
    assert ring["per_rank_wire_bytes_exact"] == "28672"
    assert ring["delta_vs_baseline"]["delta_exact"] == "0"

    crossbar = cell("allreduce_crossbar", 16384)
    assert crossbar["o_cct"]["completion_time_ns_mean_exact"] == "848"
    assert crossbar["delta_vs_baseline"]["delta_exact"] == "-150/203"

    # E0 boundary wording stays in the human table.
    markdown = (result["sweep_dir"] / "table.md").read_text(encoding="utf-8")
    assert "analytical identities, NOT" in markdown
    assert "arithmetic facts" in markdown
