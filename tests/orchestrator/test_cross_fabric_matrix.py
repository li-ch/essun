"""The cross-fabric comparison matrix (docs/atlas/cross-fabric-matrix.md).

The matrix generator (tools/cross_fabric_matrix.py) derives every
comparable cell from the content-addressed artifacts of the cross-fabric
family; these tests pin SAMPLED CELLS of the committed matrix (verdict,
exact boundary, regions, and artifact citations) against a from-scratch
regeneration into a temporary results root, plus the full-byte pin of the
committed page. The honest empties are pinned too: a cell that says NOT
COMPARABLE or NOT SAMPLED must say WHY, and must cite no artifact.

Pinned sample (three cells, one per comparison structure):

1. the delta-zero cell — the identity-matched crossbar pair ties exactly
   at every payload-grid size (the fairness anchor);
2. the window-boundary cell — the UEC TFC window vs the UB flat ring
   saturates at exactly W* = 25600 bytes at every operating point, and
   the windowed side is never faster;
3. the bandwidth-boundary cell — the same saturation boundary read on the
   shared bandwidth axis sits at exactly B* = 64 bytes/ns.
"""

from pathlib import Path

import pytest

from tools.cross_fabric_matrix import DOC_PATH, build_matrix

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def matrix(tmp_path_factory):
    root = tmp_path_factory.mktemp("cross-fabric-matrix")
    built, _ = build_matrix(results_root=root)
    return built


def _cell(matrix, row_id, col_id):
    row = next(r for r in matrix["rows"] if r["id"] == row_id)
    return row["cells"][col_id]


def _envelope_ids(matrix, key):
    return [matrix["envelopes"][key]["envelope_id"] for key in ([key] if isinstance(key, str) else key)]


def test_committed_page_regenerates_byte_identically(matrix):
    committed = DOC_PATH.read_text(encoding="utf-8")
    from tools.cross_fabric_matrix import render_markdown

    assert committed == render_markdown(matrix) + "\n"


def test_sampled_cell_delta_zero_crossbar_pair(matrix):
    """Cell 1: payload-grid row, identity-matched crossbar pair."""
    cell = _cell(matrix, "occt_payload_grid", "uec_vs_ub_crossbar")
    assert cell.comparable
    assert "TIE (exact) at all 10 payload-grid sizes" in cell.verdict
    assert cell.winner.startswith("neither")
    assert "no flip exists" in cell.flip
    refs = {r.artifact_id for r in cell.refs}
    assert refs == {
        matrix["sweeps"]["payload_grid"]["sweep_id"],
        matrix["sweeps"]["cross_design"]["sweep_id"],
    }
    # The tie claim is re-derived per payload from the sweep table itself.
    table = matrix["sweeps"]["payload_grid"]["table"]
    uec, ub = {}, {}
    for row in table["configs"]:
        if row["topology"]["path"].endswith("crossbar64_uec_free_params.yaml"):
            uec[row["payload_bytes"]] = row["o_cct"]["completion_time_ns_mean_exact"]
        if row["topology"]["path"].endswith("crossbar64_ub_rack_free_params.yaml"):
            ub[row["payload_bytes"]] = row["o_cct"]["completion_time_ns_mean_exact"]
    assert sorted(uec) == [4096, 8192, 16384, 65536, 131072, 262144, 1048576, 2097152, 4194304, 16777216]
    assert uec == ub  # delta exactly 0 at every size


def test_sampled_cell_window_saturation_boundary(matrix):
    """Cell 2: window-axis row, UEC TFC window vs UB flat ring."""
    cell = _cell(matrix, "occt_window_boundary", "uec_window_vs_ub_flat")
    assert cell.comparable
    assert "exact TIE on [25600, 1048576]" in cell.verdict
    assert "strictly worse on [256, 12800]" in cell.verdict
    assert "never better" in cell.verdict
    assert "W >= B*(L+L_cr)" in cell.flip
    expected = _envelope_ids(matrix, ["w_1mib_1024r", "w_1mib_256r", "w_16mib_1024r"])
    assert {r.artifact_id for r in cell.refs} == set(expected)
    # The boundary 25600 is verified exact in each cited artifact, and the
    # payload-invariance claim holds: all three operating points agree.
    for key in ("w_1mib_1024r", "w_1mib_256r", "w_16mib_1024r"):
        table = matrix["envelopes"][key]["table"]
        boundaries = [
            b
            for b in table["boundaries"]
            if tuple(b["pair"]) == ("uec_tfc_ring", "ub_flat_ring_pod")
            or tuple(b["pair"]) == ("uec_tfc_ring", "ub_flat_ring_mid")
        ]
        assert len(boundaries) == 1
        assert boundaries[0]["boundary_exact"] == "25600"
        assert boundaries[0]["boundary_verified"]


def test_sampled_cell_bandwidth_saturation_boundary(matrix):
    """Cell 3: bandwidth-axis row, UEC TFC window vs UB flat ring."""
    cell = _cell(matrix, "occt_bw_axis", "uec_window_vs_ub_flat")
    assert cell.comparable
    assert "exact TIE on [8, 64]" in cell.verdict
    assert "strictly worse on [128, 1024]" in cell.verdict
    assert cell.flip.startswith("exact boundary 64 on A-XDUO-BW")
    assert [r.artifact_id for r in cell.refs] == _envelope_ids(matrix, "bw_axis")
    table = matrix["envelopes"]["bw_axis"]["table"]
    boundary = next(
        b
        for b in table["boundaries"]
        if b["pair"][0] == "uec_tfc_ring" and b["pair"][1] == "ub_flat_ring_pod"
    )
    assert boundary["boundary_exact"] == "64"
    assert boundary["boundary_verified"]
    assert boundary["bracket_exact"] == ["64", "128"]


def test_honest_empties_are_explicit_and_uncited(matrix):
    """The NOT COMPARABLE / NOT SAMPLED cells state why and cite nothing."""
    not_comparable = _cell(matrix, "occt_window_boundary", "uec_vs_ub_crossbar")
    assert not not_comparable.comparable
    assert not_comparable.verdict.startswith("NOT COMPARABLE")
    assert "UBP-F04" in not_comparable.verdict
    for row_id in ("occt_bw_axis", "occt_lat_axis"):
        not_sampled = _cell(matrix, row_id, "uec_vs_ub_crossbar")
        assert not not_sampled.comparable
        assert not_sampled.verdict.startswith("NOT SAMPLED")


def test_every_comparable_cell_cites_artifacts(matrix):
    """Structural: comparable cells carry refs; every ref is a live id."""
    ids = {result["sweep_id"] for result in matrix["sweeps"].values()} | {
        result["envelope_id"] for result in matrix["envelopes"].values()
    }
    for row in matrix["rows"]:
        for column in matrix["columns"]:
            cell = row["cells"][column["id"]]
            if cell.comparable:
                assert cell.refs, f"{row['id']}/{column['id']}: comparable cell cites nothing"
            else:
                assert not cell.refs
            for ref in cell.refs:
                assert ref.artifact_id in ids
                assert ref.kind in ("sweep", "envelope")
