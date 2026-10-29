"""D-033 approval overlay: every approved id exists in the assumption
registries (yaml union + code-carried A-AS2-* + UEC spec-anchored trio);
statuses are APPROVED only; the hashed input files remain untouched."""

from pathlib import Path

import yaml

from essun.specir.uec_l0_reconciliation import assumption_ids

REPO = Path(__file__).resolve().parents[2]
OVERLAY = REPO / "experiments/vertical_slice/assumptions_approvals.yaml"
CODE_CARRIED = {"A-AS2-DELAY-POS", "A-AS2-MEM-BW", "A-AS2-INERT-KEYS",
                "UEC-SPEC-ANCHORED-1", "UEC-SPEC-ANCHORED-2", "UEC-SPEC-ANCHORED-3"}


def test_overlay_ids_all_exist_in_registries():
    data = yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))
    known = set(assumption_ids()) | CODE_CARRIED
    approved = set(data["approvals"])
    assert approved <= known, sorted(approved - known)
    assert all(v["status"] == "APPROVED" for v in data["approvals"].values())


def test_overlay_covers_every_registered_assumption():
    data = yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))
    known = set(assumption_ids()) | CODE_CARRIED
    assert known == set(data["approvals"]), sorted(known ^ set(data["approvals"]))
