"""D4 envelope determinism and the committed reversal artifact.

1. determinism — identical manifest + code version produce byte-identical
   ``reversal.json`` / ``reversal.md`` / ``reversal.json.sha256`` (and a
   rerun into the SAME root is idempotent, never a rewrite);
2. content addressing — the recomputed SHA-256 of ``reversal.json`` equals
   the hash recorded in the committed artifact record
   ``experiments/envelopes/uec_vs_ub_window_reversal_v1.REVERSAL.md``;
3. the committed reversal itself — the two-profile flip boundary is
   exactly 25600 bytes (the bandwidth-delay product), verified exact, and
   the honesty-anchor pair stays delta-exactly-0 across the whole grid.
"""

import hashlib
import re
from pathlib import Path

from essun.orchestrator.envelopes import run_envelope

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "experiments" / "envelopes" / "uec_vs_ub_window_reversal_v1.yaml"
REVERSAL_RECORD = (
    REPO / "experiments" / "envelopes" / "uec_vs_ub_window_reversal_v1.REVERSAL.md"
)


def _artifact_bytes(root: Path, envelope_id: str) -> dict[str, bytes]:
    artifact_dir = root / "envelopes" / envelope_id
    return {
        name: (artifact_dir / name).read_bytes()
        for name in ("reversal.json", "reversal.md", "reversal.json.sha256")
    }


def test_rerun_produces_byte_identical_artifacts(tmp_path):
    first = run_envelope(MANIFEST, results_root=tmp_path / "a")
    second = run_envelope(MANIFEST, results_root=tmp_path / "b")

    assert first["envelope_id"] == second["envelope_id"]
    left = _artifact_bytes(tmp_path / "a", first["envelope_id"])
    right = _artifact_bytes(tmp_path / "b", second["envelope_id"])
    for name in ("reversal.json", "reversal.md", "reversal.json.sha256"):
        assert left[name] == right[name], f"{name} differs between replays"

    # The sidecar is the hash of the exact artifact bytes.
    assert (
        hashlib.sha256(left["reversal.json"]).hexdigest() + "\n"
        == left["reversal.json.sha256"].decode("utf-8")
    )


def test_rerun_into_same_root_is_idempotent(tmp_path):
    first = run_envelope(MANIFEST, results_root=tmp_path)
    second = run_envelope(MANIFEST, results_root=tmp_path)  # must not rewrite

    assert first["envelope_id"] == second["envelope_id"]
    assert first["artifact_sha256"] == second["artifact_sha256"]


def test_committed_record_carries_the_live_content_hash(tmp_path):
    result = run_envelope(MANIFEST, results_root=tmp_path)
    record = REVERSAL_RECORD.read_text(encoding="utf-8")

    expected = result["artifact_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", expected)
    # The committed record must carry exactly this content hash.
    match = re.search(
        r"artifact content sha256.*?`([0-9a-f]{64})`", record, re.DOTALL
    )
    assert match, "committed REVERSAL.md does not state the artifact content sha256"
    assert match.group(1) == expected
    # And the input-addressed envelope id.
    assert result["envelope_id"] in record


def test_committed_reversal_is_the_stated_exact_boundary(tmp_path):
    result = run_envelope(MANIFEST, results_root=tmp_path)
    table = result["table"]

    # Flagship pair: UEC TFC admission-law ring vs UB permitted flat ring.
    flagship = [
        r for r in table["reversals"] if r["pair"] == ["uec_tfc_ring", "ub_flat_ring_pod"]
    ]
    assert len(flagship) == 1
    assert flagship[0]["boundary_exact"] == "25600"  # B*(L+L_cr) = 64*400
    assert flagship[0]["boundary_verified"] is True
    assert flagship[0]["sign_lo"] == 1 and flagship[0]["sign_hi"] == 0

    # UEC-side control: same flip against the unwindowed stand-in.
    control = [
        r for r in table["reversals"] if r["pair"] == ["uec_tfc_ring", "uec_ring_free"]
    ]
    assert len(control) == 1
    assert control[0]["boundary_exact"] == "25600"
    assert control[0]["boundary_verified"] is True

    # Honesty anchor: the two unwindowed ring identities tie everywhere.
    anchor_flips = [
        r for r in table["reversals"] if r["pair"] == ["uec_ring_free", "ub_flat_ring_pod"]
    ]
    assert anchor_flips == []
    anchor_regions = [
        r for r in table["regions"] if r["pair"] == ["uec_ring_free", "ub_flat_ring_pod"]
    ]
    assert [(r["sign"], r["from_exact"], r["to_exact"]) for r in anchor_regions] == [
        (0, "256", "1048576")
    ]

    # Regions of the flagship pair: worse below the boundary, tie above.
    regions = [
        r for r in table["regions"] if r["pair"] == ["uec_tfc_ring", "ub_flat_ring_pod"]
    ]
    assert [(r["sign"], r["from_exact"], r["to_exact"]) for r in regions] == [
        (1, "256", "12800"),
        (0, "25600", "1048576"),
    ]

    # Operating point recorded in the artifact, exactly as committed.
    fixed = {
        item["assumption_id"]: item["value_exact"]
        for item in table["operating_point_fixed"]
    }
    assert fixed == {
        "A-XDUO-BW": "64",
        "A-XDUO-LAT": "200",
        "A-TFC-CR": "200",
        "A-XDUO-TP": "1024",
        "A-XDUO-PAYLOAD": "1048576",
    }
    axis = table["freedom_axes"][0]
    assert axis["assumption_id"] == "A-TFC-W"
    assert axis["points_exact"] == [
        "256", "6400", "12800", "25600", "51200", "102400", "256000", "1048576"
    ]
