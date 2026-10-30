"""Build the PROPOSED calibration fit record for stage S4 (group G3, the
latency-axis fit stage: CAL-A8 + CAL-A9 + CAL-A10 + GF-10 per the
immutable split record 3862e227..., experiments/calibration/split/
anchor_split_v1.json).

What this stage fits: the DECLARED free ranges of the four latency
parameters — A-L0-LAT (ring link.hop_latency_ns), A-L0X-LAT (crossbar
link.pair_latency_ns), A-L0T-LAT (torus link.hop_latency_ns), A-L0D-LAT
(recursive-doubling link.pair_latency_ns); registry value 200 ns, range
[10, 2000] ns (experiments/vertical_slice/assumptions_l0.yaml) — against
the G3 anchors' staged latency-axis points. B stays at the A-L0*-BW
registry point 64 B/ns on every S4-authored row (the bandwidth axis was
S2/S3's; this stage owns the latency axis — the mirror of S3 sweeping B
at L=200 ns). The G3 anchors stage latency-axis POINTS, not collective
(size -> time) series, so every fit in this record is either DEGENERATE
(the anchor's own staged value IS the fitted L under the declared
mapping, zero residual degrees of freedom) or OUT-OF-RANGE (GF-10's
measured app-level figure — the miss IS the finding). NOTHING IS TUNED:
the registry values stay 200 and every fitted/anchor L is a recorded
diagnostic handed to the S6 holdout evaluation.

Run-backed cross-checks enforced here (a mismatch is a bug, not a
finding):

1. every executed row of BOTH sweeps equals the closed form of its own
   identity function at the same (payload, B, L) by exact Fraction
   string equality;
2. all five store runs equal the same closed forms at their anchor
   points, and their stamped evidence dimensions are as declared
   (v2, calibration_target per anchor, held_out FALSE — the split record
   defines NO within-series holdout for any G3 anchor);
3. the latency-chain laws hold EXACTLY at every shared L on executed
   rows: ring - crossbar == 12L, doubling - crossbar == 4L,
   ring - doubling == 8L, torus - crossbar == 192 + 6L (ns at the smoke
   payload 16384, B=64; the torus carries a different wire term — the
   192 ns offset is its sequential-dims wire delta, itself L-free);
4. the registry arithmetic of the placements is exact (200/140 = 10/7,
   200/80 = 5/2, 200/800 = 1/4, 2000/9000 = 2/9, ...) — anything else
   is a transcription bug;
5. the grid membership is anchor-blind: the 10 grid members are exactly
   the declared-range endpoints {10, 2000}, the powers of two inside the
   range {16, 32, 64, 128, 256, 512, 1024}, and the registry point 200;
   64 is grid member AND (noted coincidence) numerically CAL-A8's lower
   emulated point.

Pure function of immutable artifacts: reads the two append-only store
sweep tables and the five store run records produced by this stage,
recomputes every derived quantity with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/
record.json`` plus the committed copy
``experiments/calibration/s4/fit_record_v1.json`` (byte-identical;
append-only — an existing record with different bytes is an error, a
change requires fit_record_v2). No wall-clock, no host metadata.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim, label, or shipped parameter value changes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
SWEEP_ID_LAT = "778f67f319e8771f525a929b6ef698b11b938c6188c2ed521a5edc4ebee1aeab"
SWEEP_ID_BOUNDARY = "f2afb64120237a1fdb2e788769de48239a3f8ce11fd579ae7bcab559729324a7"
RUN_IDS = {
    "a8_l64": "2ca54ead178cd0a361be29124c3e4c37053d1e75125ac02600792384dc5e905d",
    "a8_l140": "774cc400a6446bd77d4f28e0a297462a0bbfee84e6c8b1e7d8fe3803c964a66d",
    "a9_l80": "95222277ecad82b9dd8f063465d13b9ad2733b50338fa772e059163749a8808d",
    "a10_l800": "6c3b7566eeedd0595bc197cb21bacd3a03f9ce45ea69dd803bd1e43e27d02ce2",
    "gf10_l9000": "a54446b6d774d7853fef7a84e08bb0230cd9bb8a28e4f3a35601f3cbb54f4080",
}
RUN_ROLES = {
    "a8_l64": "CAL-A8 lower emulated point L=64 ns fit-side run (ring, A-L0-LAT; held_out: false)",
    "a8_l140": "CAL-A8 upper emulated point L=140 ns fit-side run (ring, A-L0-LAT; held_out: false)",
    "a9_l80": "CAL-A9 one-stage pair sum L=80 ns fit-side run (crossbar, A-L0X-LAT; held_out: false)",
    "a10_l800": "CAL-A10 assumption-class L=800 ns fit-side run (crossbar, A-L0X-LAT; held_out: false)",
    "gf10_l9000": "GF-10 measured app-level headline L=9000 ns fit-side run (crossbar, A-L0X-LAT; OUT of the declared range — the miss executed; held_out: false)",
}
RUN_EXPERIMENT_IDS = {
    "a8_l64": "EXP-CAL-S4-A8-FIT-L64-001",
    "a8_l140": "EXP-CAL-S4-A8-FIT-L140-001",
    "a9_l80": "EXP-CAL-S4-A9-FIT-PAIR80-001",
    "a10_l800": "EXP-CAL-S4-A10-FIT-PAIR800-001",
    "gf10_l9000": "EXP-CAL-S4-GF10-ANCHOR-L9000-001",
}

RESULTS = REPO_ROOT / "results"
S4_DIR = REPO_ROOT / "experiments" / "calibration" / "s4"
COMMITTED_COPY = S4_DIR / "fit_record_v1.json"

# ---------------------------------------------------------------------------
# Anchor staged numbers (transcription sources: the committed E1 builders
# at experiments/calibration/{a8,a9,a10,gf10}/; staging docs
# anchors_staging.md §A8/§A9/§A10 and anchors_gapfill.md §GF-10).
# Nothing else is read; nothing is re-fetched.
# ---------------------------------------------------------------------------
# CAL-A8 (Pond, ASPLOS 2023; emulated CXL added latency, H transcription):
A8_L_LOW, A8_L_HIGH = Fraction(64), Fraction(140)
A8_GOAL_FRACS = {"64ns": Fraction(43, 100), "140ns": Fraction(37, 100)}
A8_POPULATION = 158
# CAL-A9 (Berger et al., IEEE Micro 2023; design-estimate budget, H):
A9_LINK, A9_SWITCH = Fraction(10), Fraction(70)
A9_PAIR = A9_LINK + A9_SWITCH                       # 80, plan-stated sum
A9_PAIR_TWO_LINK = 2 * A9_LINK + A9_SWITCH          # 90, flagged ambiguity
# CAL-A10 (HiPC 2025 Workshops; assumption-class usage, confidence M):
A10_L = Fraction(800)
# GF-10 (Li et al., TPDS; measured app-level P2P, M-H, V100-era):
GF10_L = Fraction(9000)
GF10_SPREAD = {
    "nv_sli_local_5000": Fraction(5000),
    "nv_sli_remote_8000": Fraction(8000),
    "nvlink_direct_9000": Fraction(9000),
    "pcie_remote_13000": Fraction(13000),
    "manual_routing_2x_18000": Fraction(18000),
    "manual_routing_3x_27000": Fraction(27000),
}
GF10_B_LINK = Fraction(25)      # per-link per-direction NVLink-2 (split STATED by the anchor)
GF10_FLAT_P100 = 16384          # latency flat up to 16 KiB (P100)
GF10_FLAT_V100 = 65536          # latency flat up to 64 KiB (V100)
GF10_SATURATION = 4194304       # NVLink V1/V2 bandwidth saturates ~2^22 = 4 MiB
GF10_RING_ALT = Fraction(4500, 7)   # 14L = 9000 (schedule-absorption reading)

# Registry / free-parameter discipline (UNCHANGED by this stage).
R8 = 8
M_SMOKE = 16384                 # A-W1-SIZE smoke value (the regime this axis predicts)
B_REG = Fraction(64)            # A-L0*-BW registry point (fixed this stage)
L_REG = Fraction(200)           # A-L0-LAT / A-L0X-LAT / A-L0T-LAT / A-L0D-LAT registry value
L_RANGE = (Fraction(10), Fraction(2000))
PLAN_SPAN = (Fraction(10), Fraction(800))   # plan §2.1 anchored-axis span (~10..800 ns)

# Grid + provenance (the anchor-blind instrument; membership = registry-range
# arithmetic only — 64's numerical coincidence with CAL-A8 is noted, never
# a provenance).
GRID_L = [Fraction(v) for v in (10, 16, 32, 64, 128, 200, 256, 512, 1024, 2000)]
PROV_L = {
    Fraction(80): "anchor: CAL-A9 one-stage pair sum 10+70 (the plan-stated reading; one-sided floor)",
    Fraction(140): "anchor: CAL-A8 upper emulated added-latency point",
    Fraction(800): "anchor: CAL-A10 assumption-class 0.8 us end-to-end figure",
    Fraction(9000): "anchor: GF-10 measured app-level P2P headline — OUT of the declared range (the miss executed)",
}
ALL_L = GRID_L + [Fraction(80), Fraction(140), Fraction(800), Fraction(9000)]

# Wire terms and latency chains at (M=16384, B=64, r=8 / torus 2x4):
W_RING = W_XBAR = W_RD = Fraction(2 * (R8 - 1), R8) * M_SMOKE / B_REG   # 448
W_TORUS = (Fraction(2 * 1, 2) + Fraction(2 * 3, 4)) * M_SMOKE / B_REG   # 640
CHAIN = {"ring": 14, "crossbar": 2, "torus2d": 8, "rd": 6}
TOPO_PREFIX = {"ring": "ring8_s4", "crossbar": "crossbar8_s4",
               "torus2d": "torus8_s4", "rd": "exchange8_s4"}
ALGO_NAME = {"ring": "allreduce_ring", "crossbar": "allreduce_crossbar",
             "torus2d": "allreduce_torus2d", "rd": "allreduce_recursive_doubling"}
BACKEND_NAME = {"ring": "analytical_l0", "crossbar": "analytical_l0_crossbar",
                "torus2d": "analytical_l0_torus2d", "rd": "analytical_l0_recursive_doubling"}


def closed_form(identity: str, payload: int, b: Fraction, l: Fraction) -> Fraction:
    """The four identities' closed forms (exact)."""
    if identity == "ring":
        return Fraction(2 * (R8 - 1) * payload, R8) / b + 2 * (R8 - 1) * l
    if identity == "crossbar":
        return Fraction(2 * (R8 - 1) * payload, R8) / b + 2 * l
    if identity == "torus2d":
        dim1 = Fraction(2 * (2 - 1), 2) * payload / b + 2 * (2 - 1) * l
        dim2 = Fraction(2 * (4 - 1), 4) * payload / b + 2 * (4 - 1) * l
        return dim1 + dim2
    if identity == "rd":
        return Fraction(2 * (R8 - 1) * payload, R8) / b + 2 * 3 * l
    raise ValueError(identity)


def pct(x: Fraction) -> float:
    return float(x) * 100.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def topo_l_from_id(topo_id: str) -> Fraction:
    """L value from an S4 topology id (ring8_s4_l64_v1, ring8_s4_l4500_7_v1)."""
    stem = topo_id.split("_l", 1)[1].rsplit("_v1", 1)[0]
    return Fraction(stem.replace("_", "/"))


def sweep_rows(sweep_id: str) -> list[dict]:
    return load_json(RESULTS / "sweeps" / sweep_id / "table.json")["configs"]


def run_summary(run_key: str, mapping: str) -> dict:
    run_id = RUN_IDS[run_key]
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    identity = {"analytical_l0": "ring", "analytical_l0_crossbar": "crossbar"}[obs["backend_id"]]
    cct = Fraction(per_op["completion_time_ns_exact"])
    payload = per_op["payload_bytes"]
    model = obs["model"]
    l_value = Fraction(model.get("pair_latency_ns_exact") or model["hop_latency_ns_exact"])
    expected = closed_form(identity, payload, B_REG, l_value)
    assert cct == expected, (run_key, cct, expected)
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "backend_id": obs["backend_id"],
        "identity": f"{identity} (latency chain {CHAIN[identity]}L)",
        "payload_bytes": payload,
        "L_ns_exact": str(l_value),
        "cct_ns_exact": str(cct),
        "cct_ns_float": float(cct),
        "latency_term_ns_exact": str(CHAIN[identity] * l_value),
        "latency_share_of_cct_exact": str(Fraction(CHAIN[identity] * l_value, 1) / cct),
        "evidence_dimensions": {
            "schema": run.get("evidence_schema_version"),
            "calibration_target": run.get("calibration_target"),
            "held_out": run.get("held_out"),
        },
    }


# ---------------------------------------------------------------------------
# Executed-sweep reconciliation (cross-check 1 + the per-L table).
# ---------------------------------------------------------------------------
def lat_axis_sweep() -> dict:
    rows = sweep_rows(SWEEP_ID_LAT)
    by_id: dict[str, dict] = {}
    for row in rows:
        topo = row["config_id"].split("-")[2]
        identity = {"allreduce_ring": "ring", "allreduce_crossbar": "crossbar",
                    "allreduce_torus2d": "torus2d",
                    "allreduce_recursive_doubling": "rd"}[row["algorithm"]]
        l_value = topo_l_from_id(topo)
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == closed_form(identity, row["payload_bytes"], B_REG, l_value), (topo, cct)
        by_id[topo] = {"identity": identity, "L": l_value, "cct": cct}

    # chain laws (cross-check 3) at every shared L
    law_rows = []
    for l_value in ALL_L:
        r_ = by_id[topo_name("ring", l_value)]
        x = by_id[topo_name("crossbar", l_value)]
        t = by_id[topo_name("torus2d", l_value)]
        d = by_id[topo_name("rd", l_value)]
        assert r_["cct"] - x["cct"] == 12 * l_value
        assert d["cct"] - x["cct"] == 4 * l_value
        assert r_["cct"] - d["cct"] == 8 * l_value
        assert t["cct"] - x["cct"] == W_TORUS - W_XBAR + 6 * l_value == Fraction(192) + 6 * l_value
        law_rows.append({
            "L_ns": str(l_value),
            "ring_minus_crossbar_exact": str(r_["cct"] - x["cct"]),
            "rd_minus_crossbar_exact": str(d["cct"] - x["cct"]),
            "torus_minus_crossbar_exact": str(t["cct"] - x["cct"]),
        })

    # the anchor-point CCT references on the crossbar (the delta columns' targets)
    ref = {
        "a8_64": by_id[topo_name("crossbar", A8_L_LOW)]["cct"],
        "a8_140": by_id[topo_name("crossbar", A8_L_HIGH)]["cct"],
        "a9_80": by_id[topo_name("crossbar", A9_PAIR)]["cct"],
        "a10_800": by_id[topo_name("crossbar", A10_L)]["cct"],
        "gf10_9000": by_id[topo_name("crossbar", GF10_L)]["cct"],
    }
    baseline = by_id[topo_name("crossbar", L_REG)]["cct"]

    per_l = []
    for l_value in sorted(ALL_L):
        x = by_id[topo_name("crossbar", l_value)]
        share = Fraction(CHAIN["crossbar"] * l_value, 1) / x["cct"]
        entry = {
            "L_ns": str(l_value),
            "L_float": float(l_value),
            "grid_member": l_value in GRID_L,
            "provenance": (
                f"grid: {int(l_value)} is a declared-range endpoint / power of two / the registry point"
                + (" (NUMERICAL COINCIDENCE only: also CAL-A8's lower emulated point)" if l_value == 64 else "")
                if l_value in GRID_L else PROV_L[l_value]
            ),
            "cct_crossbar_ns_exact": str(x["cct"]),
            "latency_share_exact": str(share),
            "latency_share_float": float(share),
            "delta_vs_registry_pct": pct((x["cct"] - baseline) / baseline),
        }
        for key, target in ref.items():
            entry[f"delta_vs_{key}_pct"] = pct((x["cct"] - target) / target)
        per_l.append(entry)

    # the ring schedule-absorption alternative row (ring-only)
    alt = by_id["ring8_s4_l4500_7_v1"]
    assert alt["cct"] == closed_form("ring", M_SMOKE, B_REG, GF10_RING_ALT)
    assert Fraction(CHAIN["ring"], 1) * GF10_RING_ALT == GF10_L  # 14 * 4500/7 == 9000

    return {
        "sweep_id": SWEEP_ID_LAT,
        "sweep_name": "cal_s4_lat_v1",
        "manifest_path": "experiments/calibration/s4/sweep_s4_lat_v1.yaml",
        "grid": "4 identities x (10 grid + 4 provenance) + 1 ring-only derived alternative = 57 configs x 6 ops",
        "cross_check": "every executed row equals the closed form of its own identity function at the same (payload, B=64, L) — exact Fraction string equality (57/57)",
        "payload_fence": "the single executed payload 16384 is the smoke value (A-W1-SIZE) — the regime the split record says this axis predicts; the split record defines NO within-series holdout for any G3 anchor, so every payload is fit-side",
        "chain_law_table": law_rows,
        "chain_laws_exact": (
            "ring - crossbar = 12L, rd - crossbar = 4L, ring - rd = 8L, "
            "torus - crossbar = 192 + 6L (the 192 ns is the torus's sequential-dims wire "
            "delta 640-448, itself L-free) — verified on executed rows at all 13 shared L values"
        ),
        "schedule_absorption_alternative": {
            "topology": "ring8_s4_l4500_7_v1 (ring-only)",
            "L_exact": "4500/7",
            "L_float": float(GF10_RING_ALT),
            "chain_equals_gf10_exact": "14 * 4500/7 = 9000 = GF-10's headline EXACTLY",
            "cct_ns_exact": str(alt["cct"]),
            "status": "FLAGGED AMBIGUITY, never selected: a DGX-1 direct P2P access crosses ONE pair (no switch, no chain), so the pair reading (L=9000, OUT of range) is the anchor-faithful primary; reading the 9000 ns onto the ring chain puts an IN-range L on the axis only by absorbing a software-stack reading into the schedule multiplier — recorded so S6/S7 see the full ambiguity, not a tuned-away one",
        },
        "per_L_table_crossbar": per_l,
    }


def topo_name(identity: str, l_value: Fraction) -> str:
    stem = f"{l_value.numerator}_{l_value.denominator}" if l_value.denominator != 1 else str(l_value.numerator)
    return f"{TOPO_PREFIX[identity]}_l{stem}_v1"


# ---------------------------------------------------------------------------
# The boundary sweep (GF-10's small-message boundary role).
# ---------------------------------------------------------------------------
def boundary_sweep() -> dict:
    rows = sweep_rows(SWEEP_ID_BOUNDARY)
    parsed = []
    for row in rows:
        topo = row["config_id"].split("-")[2]
        identity = "ring" if row["algorithm"] == "allreduce_ring" else "crossbar"
        if "_s4_" in topo:
            b, l_value = B_REG, topo_l_from_id(topo)
            src = "S4 topology (B = registry 64)"
        else:  # committed stage-GF-10 file crossbar8_gf10_b25_lXXX_v1
            b = GF10_B_LINK
            l_value = Fraction(topo.split("_l")[1].split("_")[0])
            src = "committed stage-GF-10 topology (B = the anchor's own measured per-link rate 25)"
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == closed_form(identity, row["payload_bytes"], b, l_value), (topo, cct)
        wire = Fraction(2 * (R8 - 1) * row["payload_bytes"], R8) / b
        chain = CHAIN[identity] * l_value
        parsed.append({
            "config": topo,
            "payload_bytes": row["payload_bytes"],
            "identity": identity,
            "B": str(b),
            "L_ns": str(l_value),
            "source": src,
            "cct_ns_exact": str(cct),
            "wire_term_ns_exact": str(wire),
            "latency_chain_ns_exact": str(chain),
            "latency_governed": bool(chain > wire),
        })

    def m_star(identity: str, l_value: Fraction, b: Fraction) -> Fraction:
        # wire == latency chain  =>  M* = chain * B * r / (2(r-1))
        return Fraction(CHAIN[identity] * l_value * b * R8, 2 * (R8 - 1))

    anchor_own = m_star("crossbar", GF10_L, GF10_B_LINK)
    registry_pair = m_star("crossbar", L_REG, B_REG)
    anchor_own_b64 = m_star("crossbar", GF10_L, B_REG)
    registry_pair_ring = m_star("ring", L_REG, B_REG)
    assert anchor_own == Fraction(8 * GF10_L * GF10_B_LINK, 7)
    assert registry_pair == Fraction(102400, 7)
    assert Fraction(M_SMOKE) / registry_pair == Fraction(28, 25)
    return {
        "sweep_id": SWEEP_ID_BOUNDARY,
        "sweep_name": "cal_s4_boundary_v1",
        "manifest_path": "experiments/calibration/s4/sweep_s4_boundary_v1.yaml",
        "grid": "7 topologies x 3 payloads = 21 configs x 6 ops",
        "cross_check": "every executed row equals its closed form at the same (payload, B, L) — exact Fraction string equality (21/21)",
        "executed_rows": parsed,
        "crossover_spectrum_exact": {
            "identity": "M*(L,B) = chain * B * r/(2(r-1)) — the payload at which the identity's wire term equals its latency chain; below M* the latency axis GOVERNS O-CCT (crossbar 16LB/7, ring 8LB, torus 16LB/5, rd 24LB/7 at r=8)",
            "gf10_own_numbers_crossbar": {
                "L_ns": "9000", "B": "25",
                "M_star_exact": str(anchor_own),
                "M_star_float": float(anchor_own),
                "flat_p100_16384_inside": GF10_FLAT_P100 < anchor_own,
                "flat_v100_65536_inside": GF10_FLAT_V100 < anchor_own,
                "statement": "at the anchor's OWN measured (L,B) the model's latency-governed region extends to ~251 KiB — BOTH staged flat boundaries (16 KiB P100, 64 KiB V100) sit INSIDE it: the one-sided consistency check passes (a measured flat region must be latency-governed in the model too; the converse is not claimed — the model's affine response is never literally flat)",
            },
            "gf10_at_registry_B_crossbar": {
                "L_ns": "9000", "B": "64",
                "M_star_exact": str(anchor_own_b64),
                "M_star_float": float(anchor_own_b64),
            },
            "registry_pair_crossbar": {
                "L_ns": "200", "B": "64",
                "M_star_exact": str(registry_pair),
                "M_star_float": float(registry_pair),
                "smoke_sits_above_by_exact": "16384 / (102400/7) = 28/25 (+12%) — at the registry pair the smoke payload is WIRE-governed by an exact 28:25 (wire 448 vs latency 400 ns)",
            },
            "registry_pair_ring": {
                "L_ns": "200", "B": "64",
                "M_star_exact": str(registry_pair_ring),
                "M_star_float": float(registry_pair_ring),
                "statement": "on the ring the SAME registry pair keeps the smoke payload latency-governed (M* = 8LB = 100 KiB >> 16 KiB; chain 2800 vs wire 448) — which identity governs the smoke regime is itself L-dependent structure the axis carries",
            },
        },
        "saturation_boundary_check": {
            "anchor_staged": "NVLink V1/V2 bandwidth saturates at about 2^22 = 4 MiB",
            "model_fact": {
                "statement": "the identities' response is affine in M (no ramp, no plateau onset): at the anchor's own (L=9000, B=25) the 4 MiB row is wire-governed and sits far above the crossover M*",
                "wire_term_4mib_exact": str(Fraction(2 * (R8 - 1) * GF10_SATURATION, R8) / GF10_B_LINK),
                "latency_chain_4mib_exact": str(2 * GF10_L),
                "saturation_over_crossover_exact": str(Fraction(GF10_SATURATION) / anchor_own),
                "saturation_over_crossover_float": float(Fraction(GF10_SATURATION) / anchor_own),
            },
            "classification": "the anchor's two boundaries (flat-to-{16,64} KiB, saturates-at-4 MiB) bracket a transition region the identity structurally LACKS — the latency-side mirror of S2's size-dependent software-effective-bandwidth finding, now on measured small-message data; recorded as a known omission, never tuned",
        },
    }


# ---------------------------------------------------------------------------
# Tolerance-SHAPE windows (context only; the sole admitted holdout scalar).
# ---------------------------------------------------------------------------
def tau_window(l_anchor: Fraction, tau: Fraction, grid: list[Fraction]) -> dict:
    t_a = closed_form("crossbar", M_SMOKE, B_REG, l_anchor)
    low = ((1 - tau) * t_a - W_XBAR) / 2
    high = ((1 + tau) * t_a - W_XBAR) / 2
    inside = [str(g) for g in grid if low < g < high]
    return {
        "L_anchor_ns": str(l_anchor),
        "anchor_cct_ns_exact": str(t_a),
        "L_low_exact": str(low),
        "L_low_float": float(low),
        "L_high_exact": str(high),
        "L_high_float": float(high),
        "uniform_grid_members_inside": inside,
    }


# ---------------------------------------------------------------------------
# The four fits.
# ---------------------------------------------------------------------------
def fit_a8() -> dict:
    reg = L_REG
    placements = {
        "registry_200_over_a8_low_64_exact": str(reg / A8_L_LOW),      # 25/8
        "registry_200_over_a8_high_140_exact": str(reg / A8_L_HIGH),   # 10/7
        "registry_in_anchor_band": A8_L_LOW <= reg <= A8_L_HIGH,
        "registry_in_declared_range": L_RANGE[0] <= reg <= L_RANGE[1],
        "registry_in_plan_span": PLAN_SPAN[0] <= reg <= PLAN_SPAN[1],
    }
    assert reg / A8_L_LOW == Fraction(25, 8) and reg / A8_L_HIGH == Fraction(10, 7)
    return {
        "identity": "L-axis placement on A-L0-LAT (ring rows; the stage-A8 declared projection: the per-access added-latency ns-scale read onto the collective per-hop L); executed identically on all four identities by the sweep",
        "staged_signal": "the two emulated added-latency points 64 / 140 ns (Pond, ASPLOS 2023; EMULATED study inputs bounding plausible CXL-class device latency, not device measurements); the anchor's MEASURED outputs are the workload-goal fractions 43% / 37% of 158 workloads",
        "split_role": "DEGENERATE: the split record defines no within-series holdout for CAL-A8 — the whole two-point band is the fit signal; the two points are carried SEPARATELY, never averaged",
        "fitted_L": {
            "low_exact": "64", "high_exact": "140",
            "degeneracy": "zero residual degrees of freedom — under the declared projection the anchor's own staged values ARE the fitted L values; nothing is tuned and nothing can be",
        },
        "registry_placements": placements,
        "placement_statement": "the registry point 200 ns sits ABOVE the anchor's whole emulated band: +150% over the lower point (25/8) and +42.857% over the upper (10/7) — in the declared range and the plan span but OUTSIDE the anchor band [64, 140]; consistent-with (the anchor bounds, it does not measure the collective hop latency) and selected by NO anchor — the plan's KEEP (point) verdict stands on span membership alone",
        "inexpressible_outputs": {
            "workload_goal_fractions": {"64ns": "43/100", "140ns": "37/100"},
            "population": A8_POPULATION,
            "finding": "the anchor's MEASURED outputs (fractions of a 158-workload population meeting performance goals) are STRUCTURALLY INEXPRESSIBLE in the L0 input space — no population/SLO axis exists (stage A8's enumeration, carried forward as a known omission); never smoothed",
        },
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance is adopted (the E0 zero-slack policy stands; a nonzero tolerance must arrive through CGFR with recorded evidence, plan §3.4); the L-window is where the model's smoke-point O-CCT stays within tau of the anchor-point O-CCT (the identity is affine in L, so the window is exact)",
            "tau_5pct": {
                **tau_window(A8_L_LOW, Fraction(5, 100), GRID_L),
                "note": "the window (248/5, 392/5) contains the grid member 64 (the anchor point itself, also a grid member by the noted coincidence) — no OTHER grid member lies inside",
            },
            "tau_5pct_high_point": {
                **tau_window(A8_L_HIGH, Fraction(5, 100), GRID_L),
                "note": "the window (609/5, 791/5) contains the grid member 128 — the anchor point 140 itself is a provenance member, not grid",
            },
            "shape_provenance": "CAL-A4's ~5% validated mean-error SCALAR admitted solely as tolerance-shape context per the split record's sole recorded exception (plan §3.4, in-plan since 2026-10-27; the anchor's series and per-configuration errors are NOT fit inputs)",
        },
    }


def fit_a9() -> dict:
    assert A9_PAIR == 80 and A9_PAIR_TWO_LINK == 90
    return {
        "identity": "L-axis placement on A-L0X-LAT (crossbar pair reading, the plan §2.1 stated sum); a ring-hop reading (each hop one link+switch traversal) and the torus/doubling chains are executed by the same sweep (chain laws)",
        "staged_signal": "the design-estimate budget: ~10 ns per CXL link per direction + AT LEAST ~70 ns per switch stage (ports, arbitration, NoC) — Berger et al., IEEE Micro 2023; budget-analysis numbers, NOT silicon measurements; the switch term is one-sided (a floor)",
        "split_role": "DEGENERATE: the split record defines no within-series holdout for CAL-A9 — the budget IS the fit signal",
        "fitted_L": {
            "one_stage_pair_exact": "80",
            "derivation": "10 (link) + 70 (switch stage), summed exactly as the calibration plan states (§2.1 row A-L0X-LAT: 'pair-across-a-switch: ~80 ns CXL-class (CAL-A9 link+switch sum)') — the plan is the reconciliation authority this stage follows",
            "degeneracy": "zero residual degrees of freedom — the anchor's own plan-stated sum IS the fitted L",
            "one_sided_floor": "the switch term is worded AT LEAST ~70 ns: any one-stage CXL-class pair latency >= 80 ns is consistent-with the budget and any value < 80 ns CONTRADICTS it; the falsification direction is one-sided and no upper bound follows from this anchor",
        },
        "registry_placements": {
            "registry_200_over_pair_80_exact": str(L_REG / A9_PAIR),   # 5/2
            "consistency": "200 >= 80 — consistent-with the one-sided floor",
            "registry_in_declared_range": True,
            "registry_in_plan_span": True,
        },
        "placement_statement": "the registry point 200 ns = exactly 5/2 x the one-stage pair sum (+150%); the two-link reading 2*10 + 70 = 90 ns is a FLAGGED interpretation risk (recorded, not swept — action if reversed: re-point the anchor topology at 90; every identity relation is linear in L); a cascaded second stage doubles the sum (160 = 2 x 80, anchor arithmetic) and a multi-hop schedule amplifies it (ring charges 14L vs the crossbar's 2L — the executed chain-law table)",
        "component_isolation_on_executed_rows": {
            "statement": "on the executed crossbar rows at the smoke payload: t(80) - t(10) = 140 = 2 x 70 isolates the SWITCH component exactly (the 10 ns row is the declared-range lower endpoint = the link term alone); the identity charges every budget component once per phase (2x)",
            "t80_minus_t10_exact": str(closed_form("crossbar", M_SMOKE, B_REG, A9_PAIR)
                                       - closed_form("crossbar", M_SMOKE, B_REG, A9_LINK)),
        },
        "expressiveness_loss": "carried forward from stage A9: the lumped link.pair_latency_ns cannot express the (link, switch, stage-count) decomposition — a k-stage chain enters only as the lumped arithmetic L = 80k, and the backend itself declares nonuniform_pair_latency unsupported (structural, recorded)",
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance adopted (E0 zero-slack stands)",
            "tau_5pct": {
                **tau_window(A9_PAIR, Fraction(5, 100), GRID_L),
                "note": "the window (324/5, 476/5) contains NO grid member — 64 misses from below by 0.8 ns and 128 from above by 32.8 ns; the exact boundaries are the finding, the grid is the anchor-blind instrument (same posture as S2's empty window)",
            },
            "shape_provenance": "the ~5% mean-error SCALAR admitted solely as tolerance-shape context per the split record's sole recorded exception",
        },
    }


def fit_a10() -> dict:
    assert L_REG / A10_L == Fraction(1, 4)
    return {
        "identity": "L-axis placement on A-L0X-LAT (crossbar pair reading, the stage-A10 declared PRIMARY: the quote's own wording is END-TO-END latency for NVLink Network — pair-level across the fabric, charged exactly 2L per AllReduce, rank-count-independent); the per-hop ring reading (A-L0-LAT) and the log-chain doubling reading (A-L0D-LAT) are executed by the same sweep (stage A10's secondary mappings)",
        "staged_signal": "the stated ASSUMPTION 'NVIDIA does not publish end-to-end latency for NVLink Network; we assume 0.8 us, consistent with sub-us positioning for NVSwitch hops' — HiPC 2025 Workshops; quote via public search snippet of the paywalled paper (confidence M; wording re-verification at owner integration is an open item)",
        "split_role": "DEGENERATE: the split record defines no within-series holdout for CAL-A10 — the assumption value IS the fit signal",
        "fitted_L": {
            "exact": "800",
            "degeneracy": "zero residual degrees of freedom — the anchor's own assumption value IS the fitted L",
            "assumption_class_honesty": "peer review certifies the plausibility of the USAGE, never the value; the quote's own premise (NVIDIA publishes no such number) means NO L value can be falsified against it — the placement is context, never a target",
        },
        "registry_placements": {
            "registry_200_over_assumption_800_exact": str(L_REG / A10_L),  # 1/4
            "assumption_over_registry_exact": str(A10_L / L_REG),          # 4
            "assumption_over_range_upper_exact": str(A10_L / L_RANGE[1]),  # 2/5
            "assumption_is_plan_span_upper": A10_L == PLAN_SPAN[1],
        },
        "placement_statement": "the registry point 200 ns is exactly 1/4 of the assumption (the repo-wide latency default is 4x more optimistic than the peer-reviewed assumption-class usage on the same axis); 800 ns IS the plan §2.1 anchored-span upper endpoint and sits inside the declared range [10, 2000] at exactly 40% of its upper endpoint — unlike every other G3 anchor, this anchor OWNS the span's upper end",
        "chain_multipliers_of_the_800ns_figure_per_allreduce_at_r8": {
            "crossbar_2L_exact": str(2 * A10_L),
            "rd_6L_exact": str(6 * A10_L),
            "torus_8L_exact": str(8 * A10_L),
            "ring_14L_exact": str(14 * A10_L),
            "note": "the same assumption, read onto the four declared latency parameters, spans 1.6-11.2 us per AllReduce at r=8 — the schedule multiplier is identity-side structure, anchor-free (stage A10 executed the rank scaling of exactly this bracket to r=1024)",
        },
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance adopted (E0 zero-slack stands)",
            "tau_5pct": {
                **tau_window(A10_L, Fraction(5, 100), GRID_L),
                "note": "the window (3744/5, 4256/5) contains NO grid member (512 and 1024 bracket it from outside) — the power-of-two grid resolves the 0.5-1 us region only at 512/1024; reported, not densified",
            },
            "shape_provenance": "the ~5% mean-error SCALAR admitted solely as tolerance-shape context per the split record's sole recorded exception",
        },
    }


def fit_gf10() -> dict:
    t_anchor = closed_form("crossbar", M_SMOKE, B_REG, GF10_L)
    t_best = closed_form("crossbar", M_SMOKE, B_REG, L_RANGE[1])
    floor_best = 2 * L_RANGE[1]
    assert Fraction(-14000, 18448) == (t_best - t_anchor) / t_anchor == Fraction(-875, 1153)
    assert floor_best / GF10_L == Fraction(4, 9)
    spread_over_upper = {k: str(v / L_RANGE[1]) for k, v in GF10_SPREAD.items()}
    return {
        "identity": "L-axis placement on A-L0X-LAT (crossbar pair reading — the PRIMARY): a P2P pair access on DGX-1 DIRECTLY-CONNECTED NVLink pairs crosses ONE pair (no switch, no chain), so the model's link.pair_latency_ns is the direct parameter analog of the anchor's measured per-pair figure",
        "staged_signal": "measured app-level P2P latency ~9 us for NVLink directly-connected pairs (DGX-1, V100/NVLink-2 era; Tartan suite; M-H — prose numbers from the public ar5iv HTML, per-pair matrices are heat maps); the anchor's own transport-class spread: NV-SLI local ~5 us, NV-SLI remote ~8 us, PCIe remote ~13 us, manual-routing pairs ~2x/~3x => ~18/~27 us",
        "split_role": "DEGENERATE + OUT-OF-RANGE: the split record defines no within-series holdout for GF-10; the anchor's staged points are all fit-side signal, and the headline lies OUTSIDE the declared free range",
        "fitted_L": {
            "required_exact": "9000",
            "range_membership": "OUTSIDE the declared free range [10, 2000]: 4.5x the upper endpoint (9/2), 45x the registry point",
            "degeneracy": "the anchor's own measured figure IS the required L under the primary pair reading — the fit has zero residual degrees of freedom AND no admissible solution: THE MISS IS THE FINDING",
            "best_in_range": {
                "L_exact": "2000 (the declared-range upper endpoint)",
                "cct_miss_at_smoke_exact": str((t_best - t_anchor) / t_anchor),
                "cct_miss_at_smoke_pct": pct((t_best - t_anchor) / t_anchor),
                "floor_miss_exact": "-5/9",
                "floor_miss_pct": pct(Fraction(-5, 9)),
                "statement": "even the range endpoint reaches only 4/9 of the anchor's floor (4000 vs 9000 ns) and 875/1153 of its smoke-point O-CCT (4448 vs 18448 ns): -77.78% on the floor, -75.89% in CCT",
            },
            "spread_over_range_upper": spread_over_upper,
            "spread_statement": "the anchor's WHOLE transport-class spread sits 2.5x-13.5x above the declared range upper — this is not one odd number; every app-level reading in the anchor is us-class",
        },
        "classification": {
            "finding": "app-level P2P latency bundles the software stack (CUDA API, driver, copy-engine queueing) — every L0 identity carries ZERO software/endpoint latency terms, so the measured axis point is STRUCTURALLY inexpressible: the latency-axis sibling of S2's size-dependent software-effective bandwidth and S3's software-version/algorithm axes (the third structural-omission axis of the fit family)",
            "quantity_class_caveat": "the staging doc's own interpretation duty: app-level P2P bounds a DIFFERENT thing than bare wire hop latency — the miss does NOT falsify the wire-axis range by itself; the wire-class corpus (CAL-A9 10-70 ns components, CAL-A10 800 ns assumption) still tops out at 800 ns",
            "narrow_range_upper_status": "the plan §2.1 NARROW (range upper) candidate (<= 800-1000 ns) was stated CONTINGENT on extracting this anchor's series: now extracted, GF-10 does NOT validate the narrowing — on the app-level axis the measured points sit ABOVE 2000 (the candidate would move the range the wrong way), and on the wire axis GF-10 contributes no wire-class point at all; the candidate's support remains CAL-A9's floor + CAL-A10's assumption ONLY. The registry range is NOT changed by this stage",
            "ring_chain_alternative": "14L = 9000 at L = 4500/7 ns (642.857...) — IN range; FLAGGED schedule-absorption (a software-stack reading absorbed into the schedule multiplier), executed for the record, never selected (see executed_sweeps.lat_axis.schedule_absorption_alternative)",
        },
        "registry_placements": {
            "registry_200_over_9000_exact": str(L_REG / GF10_L),        # 1/45
            "range_upper_2000_over_9000_exact": str(L_RANGE[1] / GF10_L),  # 2/9
            "headline_over_cal_a10_800_exact": str(GF10_L / A10_L),     # 45/4 = 11.25
        },
        "small_message_boundary_role": "see small_message_boundary block — the anchor's flat-to-{16,64} KiB boundaries and 4 MiB saturation point are checked against the model's crossover spectrum at the anchor's OWN (L,B) numbers",
        "tolerance_shape_windows": {
            "status": "SHAPE CONTEXT ONLY — no tolerance adopted (E0 zero-slack stands)",
            "tau_5pct": {
                **tau_window(GF10_L, Fraction(5, 100), GRID_L),
                "note": "the window (42694/5, 47306/5) lies ENTIRELY above the declared range — NO admissible L is inside it: the executed statement of the miss",
            },
            "shape_provenance": "the same tolerance-shape scalar and the same sole-recorded-exception provenance as fits.cal_a8.tolerance_shape_windows.tau_5pct.shape_provenance",
        },
    }


# ---------------------------------------------------------------------------
# The S2-mirror cross-checks (B-sensitivity of a latency-axis fit).
# ---------------------------------------------------------------------------
def b_sensitivity() -> dict:
    shares = {}
    for label, l_value in (("registry_200", L_REG), ("a8_64", A8_L_LOW),
                           ("a8_140", A8_L_HIGH), ("a9_80", A9_PAIR),
                           ("a10_800", A10_L), ("gf10_9000", GF10_L),
                           ("range_upper_2000", L_RANGE[1])):
        t = closed_form("crossbar", M_SMOKE, B_REG, l_value)
        shares[label] = str(Fraction(2 * l_value) / t)
    return {
        "the_mirror_statement": "S2 fitted B at the A-L0X-LAT registry point 200 ns and recorded L-INSENSITIVITY there (2L/t <= 7.5e-5 at every fit size; L 200->0 moves the minimax B by 0.0047%); this stage's mirror cross-checks are the B-coupling of a LATENCY-axis fit:",
        "check_1_fits_are_b_free": "the four fitted L values are parameter-axis placements — the anchors' staged ns figures are read onto L directly, so NO B enters any fitted value (exactly B-free, not merely insensitive); the degenerate fits cannot move with B",
        "check_2_predictions_b_coupling_exact": "the smoke-point O-CCT predictions carry B only through the additive wire term 2(r-1)/r*M/B (448 ns at the registry B=64; 16..16384 ns across the DECLARED B range [1, 1024]); the latency shares of the smoke-point O-CCT at B=64, per anchor L: "
        + "; ".join(f"{k} = {v}" for k, v in shares.items()),
        "check_3_the_regime_is_mixed_at_the_registry_pair": "at (B=64, L=200) the smoke point sits at the crossover (wire 448 vs latency 400 = 28:25 on the crossbar; the ring keeps it latency-governed, M* = 8LB = 100 KiB) — unlike the S2/S3 large-message regime where the latency term was negligible, the smoke regime couples BOTH axes at the registry pair; the crossover spectrum (small_message_boundary.crossover_spectrum_exact) is the exact statement of that coupling",
    }


# ---------------------------------------------------------------------------
# Smoke-regime predictions handed to the S6 external check (model-side
# numbers ONLY; the split record's holdout anchor ids stay unlisted).
# ---------------------------------------------------------------------------
def predictions() -> dict:
    rows = sweep_rows(SWEEP_ID_LAT)
    by = {}
    for row in rows:
        topo = row["config_id"].split("-")[2]
        identity = {"allreduce_ring": "ring", "allreduce_crossbar": "crossbar",
                    "allreduce_torus2d": "torus2d",
                    "allreduce_recursive_doubling": "rd"}[row["algorithm"]]
        by[(identity, topo_l_from_id(topo))] = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
    table = {}
    for label, l_value in (("registry_200", L_REG), ("a8_64", A8_L_LOW),
                           ("a8_140", A8_L_HIGH), ("a9_80", A9_PAIR),
                           ("a10_800", A10_L), ("gf10_9000", GF10_L)):
        entry = {}
        for identity in ("crossbar", "ring", "rd", "torus2d"):
            cct = by[(identity, l_value)]
            entry[f"{identity}_chain{CHAIN[identity]}L_ns_exact"] = str(cct)
        table[label] = entry
    return {
        "role": "the split record's parameter_axes for this group: 'small-message O-CCT at the smoke-manifest regime is predicted from this axis and EXTERNALLY checked on the holdout' — these are the model-side predictions at (r=8, M=16384, B=64) per identity and per fitted/registry L; every number is an executed sweep row",
        "external_check_scope": "S6 evaluates these predictions against the split record's cross-anchor holdout (ids deliberately unlisted here per the no-leakage rule); nothing in THIS stage reads, targets, or selects against any holdout number",
        "predictions_table": table,
    }


# ---------------------------------------------------------------------------
# Run cross-checks against the store (cross-check 2).
# ---------------------------------------------------------------------------
def store_run_cross_checks() -> list[dict]:
    mappings = {
        "a8_l64": ("CAL-A8", "fit-side run at the lower emulated point L=64 ns (ring identity)"),
        "a8_l140": ("CAL-A8", "fit-side run at the upper emulated point L=140 ns (ring identity)"),
        "a9_l80": ("CAL-A9", "fit-side run at the one-stage pair sum L=80 ns (crossbar identity)"),
        "a10_l800": ("CAL-A10", "fit-side run at the assumption point L=800 ns (crossbar identity)"),
        "gf10_l9000": ("GF-10", "fit-side run at the measured headline L=9000 ns (crossbar identity; OUT of the declared range — the miss executed)"),
    }
    out = []
    for key, (target, mapping) in mappings.items():
        summary = run_summary(key, mapping)
        run = load_json(RESULTS / RUN_IDS[key] / "run.json")
        assert run["manifest"]["experiment_id"] == RUN_EXPERIMENT_IDS[key]
        assert run.get("evidence_schema_version") == 2
        assert run.get("calibration_target") == [target]
        assert run.get("held_out", {}).get("held_out") is False
        out.append({
            "calibration_target": [target],
            "cct_ns_exact": summary["cct_ns_exact"],
            "experiment_id": RUN_EXPERIMENT_IDS[key],
            "held_out": False,
            "mapping": mapping,
            "run_id": RUN_IDS[key],
            "verdict": "store run == closed form of the same identity function (exact Fraction string equality); v2 dimensions as declared (held_out: false)",
        })
    return out


def evidence_dimensions_block() -> dict:
    return {
        "verification": [
            {
                "check": "tests/calibration/test_s4_fit.py",
                "scope": "S4 fit guard — re-executes the two S4 sweeps and the five S4 runs into a scratch store, rebuilds this record byte-identically, and checks the separation invariants (anchor-blind grid membership; no holdout anchor id anywhere in the record bytes; the four latency registry values untouched at 200/[10,2000]; GF-10's required L outside the declared range with the miss reported, never tuned)",
            },
            {
                "check": "tests/calibration/test_anchor_split.py",
                "scope": "the split record's own immutability guard (S1) — the data separation this fit runs under",
            },
        ],
        "calibration_target": ["CAL-A8", "CAL-A9", "CAL-A10", "GF-10"],
        "held_out": {
            "held_out": False,
            "scope": "the S4 fit objectives and every swept/executed value here touch only the group-G3 staged latency-axis signals: CAL-A8's two emulated points {64, 140} ns, CAL-A9's one-stage budget sum 80 ns, CAL-A10's assumption 800 ns, GF-10's measured app-level points (headline 9000 ns; the transport-class spread carried as staged facts) — the split record defines NO within-series holdout for any of the four, so every row is fit-side and no held-out reporting run exists in this stage",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "no software/endpoint latency term exists in ANY L0 identity — GF-10's measured app-level P2P (9 us headline; 5-27 us transport-class spread) sits 2.5-13.5x above the declared range upper with the best in-range L missing by -5/9 on the floor and -75.9% at the smoke point: the third structural-omission axis of the fit family (with S2's size-dependent software-effective bandwidth and S3's software-version/algorithm axes), reported never tuned",
            "CAL-A8's MEASURED outputs (43%/37% of 158 workloads meeting goals) are structurally inexpressible — no population/SLO axis exists (stage A8's enumeration)",
            "CAL-A9's (link, switch, stage-count) decomposition is not expressible in the lumped L (k-stage chains only as L = 80k; nonuniform pair latency declared unsupported) — stage A9's expressiveness loss, carried",
            "the identities' response is affine in M — no latency-flat region and no bandwidth ramp: GF-10's flat-to-{16,64} KiB and saturates-at-4 MiB boundaries bracket a transition region the model lacks (the latency-side mirror of S2's ramp finding)",
            "GF-10's manual-routing pair heterogeneity (2x/3x within one chassis) is inexpressible under uniform L (per-pair nonuniformity unsupported)",
            "no congestion, no credit flow control, no packetization, no multi-port injection, no in-network reduction (analytical L0 transport model only)",
        ],
    }


def build_record() -> dict:
    lat = lat_axis_sweep()
    boundary = boundary_sweep()
    evidence = evidence_dimensions_block()
    record = {
        "record_kind": "calibration_fit",
        "stage": "calibration fit record, S4 (group G3 — latency axis + small-message boundary)",
        "status": "PROPOSED — owner adjudication required; no claim, label, or shipped parameter value changes; every fitted/anchor L is a recorded diagnostic, never a shipped value",
        "evidence_schema_version": 2,
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay reproduces byte-identical artifacts)",
            "fit": "PROPOSED calibration fit candidates against external published latency-axis points (emulated / design-estimate / assumption-class / measured app-level); no E3/E4 language — none of the anchors is our testbed, and owner adjudication precedes any label move",
        },
        "calibration_target": ["CAL-A8", "CAL-A9", "CAL-A10", "GF-10"],
        "split_record": {
            "record_id": "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20",
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "group": "G3 — measured/assumption hop-pair latency axis + small-message boundary (fitting stage S4)",
            "within_series_rules": "NONE of the four G3 anchors carries a within-series split (the split record's within_series_splits lists only CAL-A3/CAL-A6/GF-02/GF-04); every staged anchor point is fit-side and no held-out reporting run exists in this stage",
            "no_leakage": "none of the split record's cross-anchor holdouts or its blocked anchor is read by any objective, swept value, or tolerance in this record (mechanically asserted: their ids appear nowhere in the record bytes); sole recorded exception used: the ~5% mean-error scalar as tolerance-SHAPE context only — the ids stay unlisted here by design",
        },
        "model": {
            "backend_ids": ["analytical_l0", "analytical_l0_crossbar",
                            "analytical_l0_torus2d", "analytical_l0_recursive_doubling"],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L = 448 + 14L ns at (M=16384, B=64, r=8)",
                "crossbar": "t = 2(r-1)/r*M/B + 2L = 448 + 2L ns",
                "torus2d": "t = sum dims [2(k-1)/k*M/B + 2(k-1)*L] = 640 + 8L ns (2x4 registry shape)",
                "rd": "t = 2(r-1)/r*M/B + 2*log2(r)*L = 448 + 6L ns",
            },
            "latency_chain_bracket": "the four declared latency parameters share value 200 / range [10, 2000] and differ only in the identity's chain multiplier: {2, 6, 8, 14} x L per AllReduce at r=8 (crossbar / recursive doubling / torus / ring) — executed and law-checked at every shared L",
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV (ring), A-L0X-PORT / A-L0X-BW / A-L0X-LAT / A-L0X-DIV (crossbar), A-L0T-BW / A-L0T-LAT / A-L0T-SEQ / A-L0T-UNIF / A-L0T-SHAPE / A-L0T-DIV (torus), A-L0D-BW / A-L0D-LAT / A-L0D-POW2 / A-L0D-STEP / A-L0D-DIV (doubling) — experiments/vertical_slice/assumptions_l0.yaml",
            "declared_free_parameters": {
                "A-L0-LAT": {"parameter": "link.hop_latency_ns", "registry_value": 200,
                             "registry_range": [10, 2000], "swept_by": "the S4 ring rows"},
                "A-L0X-LAT": {"parameter": "link.pair_latency_ns", "registry_value": 200,
                              "registry_range": [10, 2000], "swept_by": "the S4 crossbar rows (the PRIMARY pair-reading identity)"},
                "A-L0T-LAT": {"parameter": "link.hop_latency_ns", "registry_value": 200,
                              "registry_range": [10, 2000], "swept_by": "the S4 torus rows (range-discipline duty)"},
                "A-L0D-LAT": {"parameter": "link.pair_latency_ns", "registry_value": 200,
                              "registry_range": [10, 2000], "swept_by": "the S4 recursive-doubling rows (range-discipline duty)"},
                "registry_note": "all four registry VALUES stay 200 ns — UNCHANGED by this stage; the grid is anchor-blind (declared-range endpoints + powers of two + the registry point); B stays at the A-L0*-BW registry point 64 on every S4-authored row (the GF-10 B=25 boundary rows are the anchor's own measured rate, labeled config provenance, never fitted)",
            },
        },
        "group_g3_anchors": {
            "fit_targets": [
                "CAL-A8 — Pond (ASPLOS 2023) emulated CXL added-latency points 64/140 ns (latency_axis_point; staging §A8; H transcription, emulated-not-measured caveat)",
                "CAL-A9 — Berger et al. (IEEE Micro 2023) CXL latency-budget decomposition ~10 ns/link + >=~70 ns/switch (latency_axis_point; staging §A9; design-estimate, one-sided floor)",
                "CAL-A10 — HiPC 2025 Workshops UALink-vs-NVLink assumption 0.8 us end-to-end (latency_axis_point; staging §A10; assumption-class, confidence M)",
                "GF-10 — Li et al. (TPDS 32(1) 2020) measured V100-era app-level P2P ~9 us + flat-to-{16,64} KiB boundaries + 4 MiB saturation (latency_axis_point_measured; staging §GF-10; M-H, the interpretation duty: bounds a different thing than wire hop latency)",
            ],
            "parameter_axes_duty": "A-L0-LAT / A-L0X-LAT / A-L0T-LAT / A-L0D-LAT range discipline (plan §2.1 KEEP-point / NARROW-range-upper verdicts) — executed on all four parameters; small-message O-CCT at the smoke regime predicted from this axis (predictions_for_s6) for the EXTERNAL holdout check in S6",
        },
        "executed_sweeps": {"lat_axis": lat, "boundary": boundary},
        "fits": {"cal_a8": fit_a8(), "cal_a9": fit_a9(), "cal_a10": fit_a10(), "gf10": fit_gf10()},
        "b_sensitivity_cross_checks": b_sensitivity(),
        "predictions_for_s6": predictions(),
        "registry_discipline": {
            "keep_point_verdicts": "the plan §2.1 KEEP (point) verdicts for all four latency parameters stand on SPAN MEMBERSHIP alone (200 ns lies inside the anchored axis span ~10-800 ns): this stage's placements make that explicit — the registry point sits ABOVE every CXL-class point (64/80/140), at exactly 1/4 of the GPU-class assumption (800), and selected by NO anchor",
            "narrow_range_upper_candidate": "the plan's NARROW (range upper) candidate (<= 800-1000 ns, contingent on extracting the V100-era measured P2P series) is now evaluated against that series: GF-10's app-level points (5-27 us) sit ABOVE the declared upper 2000, so the candidate does NOT validate on the app-level axis, and GF-10 contributes no wire-class point; the narrowing's support remains CAL-A9's floor + CAL-A10's assumption ONLY. The registry range [10, 2000] is NOT changed; the free range's upper half (800-2000) remains without a wire-class anchor, and above it lies the un-modelable app-level regime — the honest shape of this axis as the anchors leave it",
        },
        "not_tuned": "the sweep grid was fixed by registry-range arithmetic (endpoints, powers of two, the registry point) and the anchor-provenance points by the anchors' OWN staged figures before any deviation was computed; every fit in this stage is degenerate (the anchor's own value IS the fitted/required L under a declared mapping recorded in advance) or out-of-range (GF-10 — the miss is the finding); the GF-10 ring-chain alternative was executed and FLAGGED, never selected; the registry values stay 200 across A-L0-LAT / A-L0X-LAT / A-L0T-LAT / A-L0D-LAT; no manifest outside this calibration directory carries any fitted value",
        "held_out": {
            "held_out": False,
            "scope": "all five stage runs and both sweeps are fit-side (the split record defines no within-series holdout for any G3 anchor); the stage's known-omission findings (the GF-10 miss above all) are REPORTED deviations at anchor points fixed before evaluation, never tuned targets",
        },
        "store_run_cross_checks": store_run_cross_checks(),
        "verification": evidence["verification"],
        "known_omissions": evidence["known_omissions"],
        "independent_reproduction": evidence["independent_reproduction"],
        "backing": {
            "run_ids": [RUN_IDS[k] for k in ("a8_l64", "a8_l140", "a9_l80", "a10_l800", "gf10_l9000")],
            "run_roles": {RUN_IDS[k]: RUN_ROLES[k] for k in RUN_ROLES},
            "sweep_ids": [SWEEP_ID_LAT, SWEEP_ID_BOUNDARY],
            "inputs": [
                "experiments/calibration/s4/sweep_s4_lat_v1.yaml",
                "experiments/calibration/s4/sweep_s4_boundary_v1.yaml",
                "experiments/calibration/s4/run_s4_a8_fit_l64.yaml",
                "experiments/calibration/s4/run_s4_a8_fit_l140.yaml",
                "experiments/calibration/s4/run_s4_a9_fit_pair80.yaml",
                "experiments/calibration/s4/run_s4_a10_fit_pair800.yaml",
                "experiments/calibration/s4/run_s4_gf10_anchor_l9000.yaml",
                "experiments/calibration/s4/topologies/ (57 files)",
                "experiments/calibration/s4/profiles/ (4 files)",
                "experiments/calibration/gf10/topologies/{crossbar8_gf10_b25_l200_v1,crossbar8_gf10_b25_l9000_v1}.yaml (committed stage-GF-10 files, reused as anchor-config provenance)",
                "experiments/workloads/w1_dense_tp_decode_small.yaml (the committed smoke workload)",
                "experiments/calibration/{a8,a9,a10,gf10}/ committed E1 stage records (transcription sources, reused)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/s4/sweep_s4_lat_v1.yaml ; make sweep EXP=experiments/calibration/s4/sweep_s4_boundary_v1.yaml ; make run EXP=(each of the five run_s4_*.yaml manifests) ; python experiments/calibration/s4/build_fit_record.py",
            "s6_handoff": "the fitted configurations this record hands to the S6 holdout evaluation: the four latency-axis placements L = 64 / 140 (CAL-A8 band, carried separately), 80 (CAL-A9), 800 (CAL-A10), and GF-10's required-but-out-of-range 9000 with the in-range alternative 4500/7 flagged — all recorded diagnostics, plus the smoke-regime predictions table (predictions_for_s6)",
        },
        "headline": (
            "group G3 fits (all degenerate or out-of-range — the anchors stage latency-axis POINTS, not series): "
            "CAL-A8's emulated CXL band {64, 140} ns and CAL-A9's one-stage budget sum 80 ns fit exactly as their own staged values; the registry point 200 ns sits +150%/+42.9%/+150% ABOVE the CXL-class points at exactly 1/4 of CAL-A10's 800 ns assumption (which owns the plan-span upper end, in-range at 40% of the range endpoint). "
            "GF-10's measured app-level P2P 9 us lies OUTSIDE the declared free range [10, 2000] at 4.5x its upper endpoint — the best in-range L misses by -5/9 on the floor and -75.9% at the smoke point, and the whole transport-class spread (5-27 us) sits 2.5-13.5x above: THE MISS IS THE FINDING (no software/endpoint latency term exists in any L0 identity — the third structural-omission axis of the fit family); the in-range ring-chain reading (L = 4500/7, 14L = 9000) is executed and flagged as schedule-absorption, never selected. "
            "The small-message boundary check passes one-sidedly at GF-10's own numbers (both staged flat boundaries inside the model's latency-governed region, M* = 1800000/7 B at (9000, 25)); at the registry pair the smoke payload sits exactly at the crossover (28:25 wire:latency) — and the plan's NARROW-range-upper candidate does NOT validate against the now-extracted measured series (app-level points move the wrong way; wire-class support unchanged at A9+A10 only)"
        ),
    }
    # cross-check 4: registry arithmetic sanity (a transcription bug fails here)
    fits_gf10 = record["fits"]["gf10"]
    assert record["fits"]["cal_a8"]["registry_placements"]["registry_200_over_a8_low_64_exact"] == "25/8"
    assert fits_gf10["fitted_L"]["best_in_range"]["floor_miss_exact"] == "-5/9"
    return record


def main() -> int:
    record = build_record()
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    record_id = hashlib.sha256(record_bytes).hexdigest()

    # append-only store copy (house convention; results/ is untracked)
    store_dir = RESULTS / "calibration" / record_id
    store_path = store_dir / "record.json"
    if store_path.exists():
        if store_path.read_bytes() != record_bytes:
            print(f"ERROR: store record {record_id} exists with different bytes",
                  file=sys.stderr)
            return 1
        print(f"idempotent: store record {record_id} already byte-identical")
    else:
        store_dir.mkdir(parents=True)
        store_path.write_bytes(record_bytes)
        print(f"stored: results/calibration/{record_id}/record.json")

    # committed copy — the immutability anchor of this fit record
    if COMMITTED_COPY.exists():
        if COMMITTED_COPY.read_bytes() != record_bytes:
            print(
                f"ERROR: committed copy {COMMITTED_COPY} differs from the "
                "rebuilt record — this fit record is immutable; record a "
                "NEW record (fit_record_v2) instead of editing",
                file=sys.stderr,
            )
            return 1
        print(f"immutable: committed copy matches record {record_id}")
    else:
        COMMITTED_COPY.write_bytes(record_bytes)
        print(f"wrote committed copy: {COMMITTED_COPY}")

    print(f"record_id: {record_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
