"""Build the PROPOSED calibration fit record for stage S4e (the
endpoint-latency axis — the small-message-axis RERUN of S4's group G3
against the SAME immutable split record 3862e227..., experiments/
calibration/split/anchor_split_v1.json; the structural completion the
v0.2 proposal's section 3.3 demanded).

What this stage fits: the DECLARED free range of the NEW endpoint
latency parameter A-L0E-LAT (endpoint.latency_ns; registry value 0,
range [0, 9000] ns, experiments/vertical_slice/assumptions_l0e.yaml) —
the software/endpoint latency charged once per collective op
(A-L0E-CHG) — against the G3 anchors' software-inclusive quantity
classes under mappings declared IN ADVANCE:

  GF-10 (measured app-level P2P, V100-era, the only MEASURED
        software-inclusive anchor in the fit set): t_p2p = L + E at the
        UNCHANGED registry L = 200  ->  E_fit = 8800 ns (PRIMARY);
        the whole-figure reading E = 9000 is executed and FLAGGED,
        never selected;
  CAL-A10 (assumption-class end-to-end 0.8 us): end-to-end = L + E at
        the registry L = 200  ->  E = 600 ns (assumption-class — no
        falsification power, context never target);
  CAL-A8 / CAL-A9 (wire-class / memory-class): E = 0 — their v1 L-axis
        projections are immutable in the S4 v1 record and are
        deliberately NOT re-read onto E (re-reading them toward the
        measured decade would be tuning; the fence forbids it).

B stays at the A-L0*-BW registry point 64 and L at the A-L0*-LAT
registry point 200 on every S4e-authored row (the wire axis was
S2/S3/S4 v1's; this stage owns the endpoint axis). NOTHING IS TUNED:
the A-L0E-LAT registry value stays 0, the four wire-latency registry
entries stay 200/[10, 2000], and every fitted/anchor E is a recorded
diagnostic handed to the S6e holdout evaluation.

Run-backed cross-checks enforced here (a mismatch is a bug, not a
finding):

1. every executed sweep row equals the closed form of its own identity
   function at the same (payload, B, L, E) by exact Fraction string
   equality (42/42);
2. all four store runs equal the same closed forms at their placement
   points, and their stamped evidence dimensions are as declared (v2,
   calibration_target per anchor, held_out FALSE — the split record
   defines NO within-series holdout for any G3 anchor);
3. the chain laws hold EXACTLY at every shared E on executed rows:
   ring - crossbar == 12L == 2400, rd - crossbar == 4L == 800,
   ring - rd == 8L == 1600 (E cancels — the endpoint term is
   identity-invariant structure, the extended battery's own law);
4. the registry arithmetic of the placements is exact (8800 =
   9000 - 200, 600 = 800 - 200, 8800/9000 = 44/45, 600/8800 = 3/44,
   ...) — anything else is a transcription bug;
5. the grid membership is anchor-blind: the 12 grid members are exactly
   the declared-range endpoints {0, 9000} and the powers of two inside
   the range {16..8192}; the registry point 0 IS the lower endpoint
   (noted by construction — the registry value is the term's structural
   default) and 9000 is the range upper the registration itself drew
   from the fit-set anchor GF-10's staged figure (the range's own
   provenance, never a sweep selection); the two provenance members
   {600, 8800} are the anchors' own figures under the declared mappings.

Pure function of immutable artifacts: reads the append-only store sweep
table and the four store run records produced by this stage, recomputes
every derived quantity with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/
record.json`` plus the committed copy
``experiments/calibration/s4e/fit_record_v1.json`` (byte-identical;
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
SWEEP_ID_E = "f4786367abebab56d33e89d018c425a95dca23cc7d9322e009fa45a32ab22522"
RUN_IDS = {
    "gf10_e8800": "607174234709f3173b391e7cdff2f9ced84af1671873721a94463b1aa1489280",
    "a10_e600": "50cb636f75e5b69d823b22d13649c4c7c4d79af5e4007c382ce09ef54d387a9a",
    "gf10_alt_e9000": "dc247a5beec8f0ef0fa64db13b3545b826b27e4c6d5e6401e4e54bbc9906d861",
    "wireclass_e0": "b8a114516d31c29851b34854fbe1e4fbc83fb55874a6fd38ab1711afaf327f93",
}
RUN_ROLES = {
    "gf10_e8800": "GF-10 PRIMARY E-axis placement E=8800 ns fit-side run (crossbar, A-L0E-LAT; t_p2p = L + E at registry L=200; held_out: false)",
    "a10_e600": "CAL-A10 end-to-end reading E=600 ns fit-side run (crossbar, A-L0E-LAT; 800 = L + E at registry L=200; assumption-class context; held_out: false)",
    "gf10_alt_e9000": "GF-10 whole-figure alternative E=9000 ns fit-side run (crossbar, A-L0E-LAT; FLAGGED, never selected; held_out: false)",
    "wireclass_e0": "wire-class origin reference E=0 ns fit-side run (ring, A-L0E-LAT registry point; CAL-A8/A9 quantity class; held_out: false)",
}
RUN_EXPERIMENT_IDS = {
    "gf10_e8800": "EXP-CAL-S4E-GF10-FIT-E8800-001",
    "a10_e600": "EXP-CAL-S4E-A10-FIT-E600-001",
    "gf10_alt_e9000": "EXP-CAL-S4E-GF10-ALT-E9000-001",
    "wireclass_e0": "EXP-CAL-S4E-WIRECLASS-E0-001",
}

RESULTS = REPO_ROOT / "results"
S4E_DIR = REPO_ROOT / "experiments" / "calibration" / "s4e"
COMMITTED_COPY = S4E_DIR / "fit_record_v1.json"

# ---------------------------------------------------------------------------
# Anchor staged numbers (transcription sources: the committed E1 builders
# at experiments/calibration/{a8,a9,a10,gf10}/; staging docs
# anchors_staging.md §A8/§A9/§A10 and anchors_gapfill.md §GF-10).
# Nothing else is read; nothing is re-fetched.
# ---------------------------------------------------------------------------
GF10_L_P2P = Fraction(9000)          # measured app-level P2P headline (V100-era)
A10_ENDTOEND = Fraction(800)         # assumption-class end-to-end (confidence M)
A8_L_LOW, A8_L_HIGH = Fraction(64), Fraction(140)   # emulated CXL band (wire-class here)
A9_PAIR = Fraction(80)               # design-estimate one-stage pair sum (wire-class here)

# Registry / free-parameter discipline (UNCHANGED by this stage).
R8 = 8
M_SMOKE = 16384                 # A-W1-SIZE smoke value (the regime this axis predicts)
B_REG = Fraction(64)            # A-L0*-BW registry point (fixed this stage)
L_REG = Fraction(200)           # A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry value (fixed this stage)
L_RANGE = (Fraction(10), Fraction(2000))   # wire-latency declared range (S4 v1's, unchanged)
E_REG = Fraction(0)             # A-L0E-LAT registry value
E_RANGE = (Fraction(0), Fraction(9000))    # A-L0E-LAT declared range (registration source: GF-10)

# Declared placements (mappings stated in advance in the run manifests).
E_GF10 = GF10_L_P2P - L_REG     # 8800  (t_p2p = L + E, PRIMARY)
E_A10 = A10_ENDTOEND - L_REG    # 600   (end-to-end = L + E, assumption-class)
E_GF10_ALT = GF10_L_P2P         # 9000  (whole-figure reading, FLAGGED)
E_WIRECLASS = Fraction(0)       # wire-class origin (A8/A9 quantity class)

# Grid + provenance (the anchor-blind instrument).
GRID_E = [Fraction(v) for v in (0, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 9000)]
PROV_E = {
    Fraction(600): "anchor: CAL-A10 assumption-class end-to-end 800 read as L + E at the registry L=200 (declared end-to-end reading)",
    Fraction(8800): "anchor: GF-10 measured app-level P2P 9000 read as t_p2p = L + E at the registry L=200 (the PRIMARY pair reading)",
}
ALL_E = sorted(set(GRID_E) | set(PROV_E))

# Wire terms and latency chains at (M=16384, B=64, L=200, r=8).
W_RING = W_XBAR = W_RD = Fraction(2 * (R8 - 1), R8) * M_SMOKE / B_REG   # 448
CHAIN = {"ring": 14, "crossbar": 2, "rd": 6}
TOPO_PREFIX = {"ring": "ring8_s4e", "crossbar": "crossbar8_s4e", "rd": "exchange8_s4e"}
ALGO_NAME = {"ring": "allreduce_ring", "crossbar": "allreduce_crossbar",
             "rd": "allreduce_recursive_doubling"}
IDENTITY_NAME = {"allreduce_ring": "ring", "allreduce_crossbar": "crossbar",
                 "allreduce_recursive_doubling": "rd"}


def closed_form(identity: str, payload: int, b: Fraction, l: Fraction, e: Fraction) -> Fraction:
    """The three endpoint-extended identities' closed forms (exact)."""
    wire = Fraction(2 * (R8 - 1) * payload, R8) / b
    if identity == "ring":
        return wire + 2 * (R8 - 1) * l + e
    if identity == "crossbar":
        return wire + 2 * l + e
    if identity == "rd":
        return wire + 2 * 3 * l + e
    raise ValueError(identity)


def pct(x: Fraction) -> float:
    return float(x) * 100.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def topo_e_from_id(topo_id: str) -> Fraction:
    """E value from an S4e topology id (crossbar8_s4e_e8800_v1)."""
    stem = topo_id.split("_e", 1)[1].rsplit("_v1", 1)[0]
    return Fraction(stem.replace("_", "/"))


def topo_name(identity: str, e_value: Fraction) -> str:
    stem = f"{e_value.numerator}_{e_value.denominator}" if e_value.denominator != 1 else str(e_value.numerator)
    return f"{TOPO_PREFIX[identity]}_e{stem}_v1"


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
    e_value = Fraction(model["endpoint_latency_ns_exact"])
    assert per_op["endpoint_term_ns_exact"] == str(e_value) if "endpoint_term_ns_exact" in per_op else identity == "ring"
    expected = closed_form(identity, payload, B_REG, l_value, e_value)
    assert cct == expected, (run_key, cct, expected)
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "backend_id": obs["backend_id"],
        "identity": f"{identity} (latency chain {CHAIN[identity]}L + E)",
        "payload_bytes": payload,
        "L_ns_exact": str(l_value),
        "E_ns_exact": str(e_value),
        "cct_ns_exact": str(cct),
        "cct_ns_float": float(cct),
        "wire_term_ns_exact": str(W_RING),
        "latency_chain_ns_exact": str(CHAIN[identity] * l_value),
        "endpoint_term_ns_exact": str(e_value),
        "endpoint_share_of_cct_exact": str(e_value / cct),
        "evidence_dimensions": {
            "schema": run.get("evidence_schema_version"),
            "calibration_target": run.get("calibration_target"),
            "held_out": run.get("held_out"),
        },
    }


# ---------------------------------------------------------------------------
# Executed-sweep reconciliation (cross-check 1 + chain laws + the per-E table).
# ---------------------------------------------------------------------------
def e_axis_sweep() -> dict:
    rows = sweep_rows(SWEEP_ID_E)
    by_id: dict[str, dict] = {}
    for row in rows:
        topo = row["config_id"].split("-")[2]
        identity = IDENTITY_NAME[row["algorithm"]]
        e_value = topo_e_from_id(topo)
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == closed_form(identity, row["payload_bytes"], B_REG, L_REG, e_value), (topo, cct)
        by_id[topo] = {"identity": identity, "E": e_value, "cct": cct}

    # chain laws (cross-check 3) at every shared E — E cancels
    law_rows = []
    for e_value in ALL_E:
        r_ = by_id[topo_name("ring", e_value)]
        x = by_id[topo_name("crossbar", e_value)]
        d = by_id[topo_name("rd", e_value)]
        assert r_["cct"] - x["cct"] == 12 * L_REG == Fraction(2400)
        assert d["cct"] - x["cct"] == 4 * L_REG == Fraction(800)
        assert r_["cct"] - d["cct"] == 8 * L_REG == Fraction(1600)
        law_rows.append({
            "E_ns": str(e_value),
            "ring_minus_crossbar_exact": str(r_["cct"] - x["cct"]),
            "rd_minus_crossbar_exact": str(d["cct"] - x["cct"]),
            "ring_minus_rd_exact": str(r_["cct"] - d["cct"]),
        })

    # the placement CCT references on the crossbar (the delta columns' targets)
    ref = {
        "wireclass_e0": by_id[topo_name("crossbar", E_WIRECLASS)]["cct"],
        "a10_e600": by_id[topo_name("crossbar", E_A10)]["cct"],
        "gf10_e8800": by_id[topo_name("crossbar", E_GF10)]["cct"],
    }
    baseline = by_id[topo_name("crossbar", E_REG)]["cct"]

    per_e = []
    for e_value in ALL_E:
        x = by_id[topo_name("crossbar", e_value)]
        share = e_value / x["cct"]
        if e_value in GRID_E:
            if e_value == E_REG:
                provenance = ("grid: 0 is the declared-range lower endpoint AND the registry point "
                              "(the registry value IS the term's structural default — noted by construction, not selection)")
            elif e_value == E_RANGE[1]:
                provenance = ("grid: 9000 is the declared-range upper endpoint — drawn from GF-10's staged figure "
                              "BY CONSTRUCTION of the registration (the range's own provenance); doubles as the "
                              "anchor's flagged whole-figure reading (see fits.gf10_alt)")
            else:
                provenance = f"grid: {int(e_value)} is a power of two inside the declared range [0, 9000] (anchor-blind)"
        else:
            provenance = PROV_E[e_value]
        entry = {
            "E_ns": str(e_value),
            "E_float": float(e_value),
            "grid_member": e_value in GRID_E,
            "provenance": provenance,
            "cct_crossbar_ns_exact": str(x["cct"]),
            "endpoint_share_exact": str(share),
            "endpoint_share_float": float(share),
            "delta_vs_registry_pct": pct((x["cct"] - baseline) / baseline),
        }
        for key, target in ref.items():
            entry[f"delta_vs_{key}_pct"] = pct((x["cct"] - target) / target)
        per_e.append(entry)

    return {
        "sweep_id": SWEEP_ID_E,
        "sweep_name": "cal_s4e_e_v1",
        "manifest_path": "experiments/calibration/s4e/sweep_s4e_e_v1.yaml",
        "grid": "3 identities x (12 grid + 2 provenance) = 42 configs x 6 ops",
        "cross_check": "every executed row equals the closed form of its own identity function at the same (payload, B=64, L=200, E) — exact Fraction string equality (42/42)",
        "payload_fence": "the single executed payload 16384 is the smoke value (A-W1-SIZE) — the regime the split record says this axis predicts; the split record defines NO within-series holdout for any G3 anchor, so every payload is fit-side",
        "torus_boundary": "the torus identity has NO rows in this sweep — A-L0E-CHG applicability excludes it (its endpoint extension is a separate registered step); the v1 torus rows in the S4 record are unchanged",
        "chain_law_table": law_rows,
        "chain_laws_exact": (
            "ring - crossbar = 12L = 2400, rd - crossbar = 4L = 800, ring - rd = 8L = 1600 "
            "at EVERY shared E — the endpoint term cancels because it is charged once per op, "
            "identity-invariant: the extended battery's own law (tests/golden/test_l0_endpoint_golden.py)"
        ),
        "per_E_table_crossbar": per_e,
    }


# ---------------------------------------------------------------------------
# The fits.
# ---------------------------------------------------------------------------
def fit_gf10() -> dict:
    t_placement = closed_form("crossbar", M_SMOKE, B_REG, L_REG, E_GF10)
    assert t_placement == Fraction(9648)
    return {
        "identity": "E-axis placement on A-L0E-LAT (crossbar pair reading, the PRIMARY): a DGX-1 direct P2P access crosses ONE pair AND the app-level figure bundles the software stack, so t_p2p = L + E with L at its UNCHANGED registry point 200 — E_fit = 9000 - 200 = 8800 ns",
        "staged_signal": "measured app-level P2P latency ~9 us for NVLink directly-connected pairs (DGX-1, V100/NVLink-2 era; Tartan suite, Li et al. TPDS 32(1); M-H — prose numbers from the public ar5iv HTML); the anchor's own transport-class spread: NV-SLI local ~5 us, NV-SLI remote ~8 us, PCIe remote ~13 us, manual-routing pairs ~2x/~3x => ~18/~27 us",
        "split_role": "DEGENERATE (now IN range): the split record defines no within-series holdout for GF-10; the anchor's staged figure under the declared mapping IS the fitted E — zero residual degrees of freedom; where S4 v1's L reading sat OUT of [10, 2000] (the miss), the E reading sits INSIDE [0, 9000] at 44/45 of the upper endpoint the anchor itself defines",
        "fitted_E": {
            "exact": "8800",
            "derivation_exact": "9000 - 200 (t_p2p = L + E at the registry L)",
            "degeneracy": "the anchor's own measured figure under a mapping declared in advance IS the fitted E; nothing is tuned and nothing can be",
            "range_membership": "INSIDE the declared free range [0, 9000] at exactly 44/45 of its upper endpoint (the registration drew that upper from this anchor's own figure — the range's provenance, never a tuned enclosure)",
        },
        "what_changed_vs_v1": "S4 v1 read the same 9000 ns onto L (OUT of [10, 2000] at 4.5x its upper — the structural miss); the endpoint term makes the software-inclusive quantity class expressible AS ITSELF, and the miss becomes a placement. The v1 record and its finding stand unchanged; this is the structural completion the v0.2 proposal section 3.3 named",
        "registry_placements": {
            "e_fit_over_registry_exact": str(E_GF10 / E_REG) if E_REG else "undefined (registry 0)",
            "e_fit_over_range_upper_exact": str(E_GF10 / E_RANGE[1]),          # 44/45
            "registry_l_over_e_fit_exact": str(L_REG / E_GF10),                # 1/44
            "wire_share_of_anchor_figure_exact": str(L_REG / GF10_L_P2P),      # 1/45
        },
        "placement_statement": "the wire share of the anchor's own figure is 1/45 (2.2%): under the declared mapping the app-level reading is 97.8% endpoint/software and 2.2% wire at the registry pair — the quantity-class split the term exists to express; at the smoke point the placement's CCT is 9648 ns of which the endpoint term carries 550/603 (91.2%)",
        "quantity_class_caveat": "carried from v1 unchanged: app-level P2P bounds a DIFFERENT thing than bare wire hop latency; this placement maps the software-inclusive class onto E, it does not re-measure the wire axis (the wire-class corpus still tops out at CAL-A10's 800 ns assumption)",
        "generation_caveat": "the figure is V100/NVLink-2 era, one-plus generations older than every current-generation fabric the corpus stages — the placement inherits that generation gap wherever it is evaluated",
        "spread_context": "the anchor's whole transport-class spread (5-27 us) maps onto E as 4800-26800 ns at the same registry L — every reading in the anchor is us-class software-inclusive, consistent with the placement's magnitude class",
    }


def fit_a10() -> dict:
    t_placement = closed_form("crossbar", M_SMOKE, B_REG, L_REG, E_A10)
    assert t_placement == Fraction(1448)
    return {
        "identity": "E-axis placement on A-L0E-LAT (the declared end-to-end reading): the quote's own wording is END-TO-END latency — a pair-level figure that, read on the endpoint-extended identity, decomposes as t_pair = L + E with L at its UNCHANGED registry point 200 — E = 800 - 200 = 600 ns; the v1 primary reading (whole 800 on L) stays immutable in the S4 v1 record",
        "staged_signal": "the stated ASSUMPTION 'NVIDIA does not publish end-to-end latency for NVLink Network; we assume 0.8 us, consistent with sub-us positioning for NVSwitch hops' — HiPC 2025 Workshops; quote via public search snippet of the paywalled paper (confidence M)",
        "split_role": "DEGENERATE: no within-series holdout exists for CAL-A10; the assumption value under the declared reading IS the placement",
        "fitted_E": {
            "exact": "600",
            "derivation_exact": "800 - 200 (end-to-end = L + E at the registry L)",
            "degeneracy": "zero residual degrees of freedom — the anchor's own assumption value under the declared reading",
            "assumption_class_honesty": "peer review certifies the plausibility of the USAGE, never the value; the quote's own premise (NVIDIA publishes no such number) means NO E value can be falsified against it — the placement is context, never a target",
        },
        "interpretation_pair_status": "the anchor now carries TWO recorded readings — v1's whole-800-on-L (registry-distance 1/4) and this end-to-end L+E decomposition (E = 600) — an explicitly carried ambiguity, never silently resolved; the two differ by exactly the registry L placement and do not change any qualitative verdict",
        "registry_placements": {
            "e_placement_over_gf10_e_fit_exact": str(E_A10 / E_GF10),          # 3/44
            "l_share_of_assumption_exact": str(L_REG / A10_ENDTOEND),          # 1/4
        },
    }


def fit_gf10_alt() -> dict:
    t_placement = closed_form("crossbar", M_SMOKE, B_REG, L_REG, E_GF10_ALT)
    assert t_placement == Fraction(9848)
    return {
        "identity": "the WHOLE-FIGURE alternative reading of GF-10's headline onto E (no wire deduction): E = 9000 ns — FLAGGED, never selected",
        "why_flagged": "the PRIMARY mapping (t_p2p = L + E) charges the ONE pair crossing the anchor's own transport reading states; reading the whole 9000 onto E zeroes it — the mirror of S4 v1's flagged 4500/7 schedule-absorption alternative. The two readings differ by exactly the registry L (200 ns, 2.2% of the figure) and no qualitative verdict turns on the choice",
        "fitted_E": {
            "exact": "9000",
            "range_membership": "INSIDE [0, 9000] AT the upper endpoint (the grid membership it holds by construction)",
            "status": "FLAGGED AMBIGUITY — executed so the evaluation stages see the full ambiguity, never selected",
        },
    }


def fit_wireclass() -> dict:
    t_placement = closed_form("ring", M_SMOKE, B_REG, L_REG, E_WIRECLASS)
    assert t_placement == Fraction(3248)
    return {
        "identity": "the E-axis ORIGIN on the ring identity: E = 0 (the A-L0E-LAT registry point), numbers identical to the landed S4 v1 ring row at L = 200 (448 + 14*200 = 3248 ns) — the byte-identity fence the golden battery pins",
        "role": "the wire-class anchors' quantity-class statement: CAL-A8's emulated CXL band {64, 140} ns and CAL-A9's design-estimate budget 80 ns carry no software-stack component, so they place E at 0; their v1 L-axis placements are IMMUTABLE in the S4 v1 record and this stage deliberately does not re-read them onto E (re-reading them toward the measured small-message decade would be tuning toward anchors the fence forbids)",
        "fitted_E": {
            "exact": "0",
            "degeneracy": "the registry origin itself — the pre-extension identity, executed with the term ACTIVE at value 0 (honest bytes, identical numbers)",
        },
    }


# ---------------------------------------------------------------------------
# The L-coupling cross-checks (the mirror of S4 v1's B-sensitivity block).
# ---------------------------------------------------------------------------
def l_sensitivity() -> dict:
    shares = {}
    for label, e_value in (("wireclass_e0", E_WIRECLASS), ("a10_e600", E_A10),
                           ("gf10_e8800", E_GF10), ("gf10_alt_e9000", E_GF10_ALT)):
        t = closed_form("crossbar", M_SMOKE, B_REG, L_REG, e_value)
        shares[label] = str(e_value / t)
    return {
        "the_mirror_statement": "S4 v1 fitted L at fixed B and recorded the fits' B-freedom; this stage fits E at fixed (B, L) and records the fits' L-COUPLING (the declared mappings deduct the registry L from the anchor figures):",
        "check_1_fits_are_l_coupled_exactly": "both E placements carry L at the registry 200 inside their derivation (E_gf10 = 9000 - 200; E_a10 = 800 - 200): moving the registry L to 0 would move them to 9000 / 800 (+2.27% / +33.3%) — the mapping, not the model, owns that coupling; NOTHING is moved (the registry L stays 200)",
        "check_2_predictions_l_coupling_exact": "the smoke-point O-CCT predictions carry L only through the additive chain term (2L = 400 / 14L = 2800 / 6L = 1200 ns at the registry pair) and E additively — the endpoint shares of the smoke-point crossbar O-CCT per placement: "
        + "; ".join(f"{k} = {v}" for k, v in shares.items()),
        "check_3_the_regime_at_the_placements": "at E = 0 the smoke point sits at the v1 crossover (wire 448 vs latency 400 = 28:25); at E = 600 the endpoint term (600) EXCEEDS the whole wire+latency transport (848) — 41.4% of CCT; at E = 8800 the transport is 9.6% of CCT: the endpoint axis, not the wire axis, owns the small-message regime at every software-inclusive placement",
    }


# ---------------------------------------------------------------------------
# Smoke-regime predictions handed to the S6e external check (model-side
# numbers ONLY; the split record's holdout anchor ids stay unlisted).
# ---------------------------------------------------------------------------
def predictions() -> dict:
    rows = sweep_rows(SWEEP_ID_E)
    by = {}
    for row in rows:
        topo = row["config_id"].split("-")[2]
        identity = IDENTITY_NAME[row["algorithm"]]
        by[(identity, topo_e_from_id(topo))] = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
    table = {}
    for label, e_value in (("wireclass_e0", E_WIRECLASS), ("a10_e600", E_A10),
                           ("gf10_e8800", E_GF10), ("gf10_alt_e9000", E_GF10_ALT)):
        entry = {}
        for identity in ("crossbar", "ring", "rd"):
            cct = by[(identity, e_value)]
            entry[f"{identity}_chain{CHAIN[identity]}L_plus_E_ns_exact"] = str(cct)
        table[label] = entry
    return {
        "role": "the split record's parameter_axes for this group: 'small-message O-CCT at the smoke-manifest regime is predicted from this axis and EXTERNALLY checked on the holdout' — these are the model-side predictions at (r=8, M=16384, B=64, L=200) per identity and per fitted/registry E; every number is an executed sweep row",
        "external_check_scope": "the S6e evaluation stage runs these predictions against the split record's cross-anchor holdout (ids deliberately unlisted here per the no-leakage rule); nothing in THIS stage reads, targets, or selects against any holdout number",
        "predictions_table": table,
    }


# ---------------------------------------------------------------------------
# Run cross-checks against the store (cross-check 2).
# ---------------------------------------------------------------------------
def store_run_cross_checks() -> list[dict]:
    mappings = {
        "gf10_e8800": ("GF-10", "fit-side run at the PRIMARY E placement 8800 ns (crossbar identity)"),
        "a10_e600": ("CAL-A10", "fit-side run at the end-to-end reading E = 600 ns (crossbar identity)"),
        "gf10_alt_e9000": ("GF-10", "fit-side run at the FLAGGED whole-figure E = 9000 ns (crossbar identity; never selected)"),
        "wireclass_e0": ("CAL-A8", "fit-side run at the E-axis origin 0 ns (ring identity; the wire-class quantity-class reference)"),
    }
    out = []
    for key, (target, mapping) in mappings.items():
        summary = run_summary(key, mapping)
        run = load_json(RESULTS / RUN_IDS[key] / "run.json")
        assert run["manifest"]["experiment_id"] == RUN_EXPERIMENT_IDS[key]
        assert run.get("evidence_schema_version") == 2
        expected_targets = {"wireclass_e0": ["CAL-A8", "CAL-A9"]}.get(key, [target])
        assert run.get("calibration_target") == expected_targets
        assert run.get("held_out", {}).get("held_out") is False
        out.append({
            "calibration_target": expected_targets,
            "cct_ns_exact": summary["cct_ns_exact"],
            "E_ns_exact": summary["E_ns_exact"],
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
                "check": "tests/calibration/test_s4e_fit.py",
                "scope": "S4e fit guard — re-executes the S4e sweep and the four S4e runs into a scratch store, rebuilds this record byte-identically, and checks the separation invariants (anchor-blind grid membership; no holdout anchor id anywhere in the record bytes; the four wire-latency registry values untouched at 200/[10,2000]; the A-L0E-LAT registry value untouched at 0)",
            },
            {
                "check": "tests/golden/test_l0_endpoint_golden.py",
                "scope": "the endpoint-term identity battery — hand-derived literals for the extended family, the amended phase-composition law, the L0.5 convergence with E, the chain laws at shared E, and the byte-identity fence (absent term = the landed payloads)",
            },
            {
                "check": "tests/calibration/test_anchor_split.py",
                "scope": "the split record's own immutability guard (S1) — the data separation this fit runs under",
            },
        ],
        "calibration_target": ["CAL-A8", "CAL-A9", "CAL-A10", "GF-10"],
        "held_out": {
            "held_out": False,
            "scope": "the S4e fit objectives and every swept/executed value here touch only the group-G3 staged signals under mappings declared in advance: GF-10's measured app-level figure read as t_p2p = L + E (and its flagged whole-figure alternative), CAL-A10's assumption read as end-to-end = L + E, and the wire-class anchors' quantity-class origin E = 0 — the split record defines NO within-series holdout for any of the four, so every row is fit-side and no held-out reporting run exists in this stage",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "the fit set spans the E axis at {0, 600, 8800} (9000 flagged alternative): no fit-side anchor stages a CURRENT-generation software-latency measurement — the only measured software-inclusive figure (GF-10) is V100-era app-level P2P, and the assumption-class figure certifies a usage, never a value; whether any defensible placement lands in the current-generation measured small-message floor decade is the S6e evaluation's question, never this fit's target",
            "the lumped symmetric endpoint term cannot express measured asymmetric latency decompositions (a per-phase 2L + E family has no store/retrieve component split); uniform E cannot express per-pair heterogeneity (GF-10's manual-routing 2x/3x pairs)",
            "the identities' response stays affine in M — no launch-floor-flat region and no bandwidth ramp; the term adds a constant floor, not a flat-then-rising transition",
            "CAL-A8's MEASURED outputs (workload-goal fractions) remain structurally inexpressible (no population/SLO axis; carried from S4 v1)",
            "CAL-A9's (link, switch, stage-count) decomposition remains inexpressible in the lumped L (carried from S4 v1)",
            "the torus identity carries no endpoint term (A-L0E-CHG applicability; a separate registered step) — no torus row exists in this sweep",
            "no congestion, no credit flow control, no packetization, no multi-port injection, no in-network reduction (analytical L0 transport model only)",
        ],
    }


def build_record() -> dict:
    e_axis = e_axis_sweep()
    evidence = evidence_dimensions_block()
    record = {
        "record_kind": "calibration_fit",
        "stage": "calibration fit record, S4e (group G3 — the endpoint-latency axis; the small-message-axis rerun of S4 under the same immutable split)",
        "status": "PROPOSED — owner adjudication required; no claim, label, or shipped parameter value changes; every fitted/anchor E is a recorded diagnostic, never a shipped value",
        "evidence_schema_version": 2,
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay reproduces byte-identical artifacts)",
            "fit": "PROPOSED calibration fit candidates against external published latency-axis points (measured app-level / assumption-class / wire-class-origin); no E3/E4 language — none of the anchors is our testbed, and owner adjudication precedes any label move",
        },
        "calibration_target": ["CAL-A8", "CAL-A9", "CAL-A10", "GF-10"],
        "split_record": {
            "record_id": "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20",
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "group": "G3 — measured/assumption hop-pair latency axis + small-message boundary (fitting stage S4); S4e is the SAME group's endpoint-axis rerun against the SAME split — no re-splitting, no membership change",
            "within_series_rules": "NONE of the four G3 anchors carries a within-series split (the split record's within_series_splits lists only CAL-A3/CAL-A6/GF-02/GF-04); every staged anchor point is fit-side and no held-out reporting run exists in this stage",
            "no_leakage": "none of the split record's cross-anchor holdouts or its blocked anchor is read by any objective, swept value, or tolerance in this record (mechanically asserted: their ids appear nowhere in the record bytes)",
        },
        "model": {
            "backend_ids": ["analytical_l0", "analytical_l0_crossbar", "analytical_l0_recursive_doubling"],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L + E = 3248 + E ns at (M=16384, B=64, L=200, r=8)",
                "crossbar": "t = 2(r-1)/r*M/B + 2L + E = 848 + E ns",
                "rd": "t = 2(r-1)/r*M/B + 2*log2(r)*L + E = 1648 + E ns",
            },
            "endpoint_charging": "E is charged ONCE per collective op, identity-invariant (A-L0E-CHG) — the chain laws survive at every shared E (E cancels); the torus identity is excluded from this registration (separate registered step)",
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV (ring), A-L0X-PORT / A-L0X-BW / A-L0X-LAT / A-L0X-DIV (crossbar), A-L0D-BW / A-L0D-LAT / A-L0D-POW2 / A-L0D-STEP / A-L0D-DIV (doubling) — experiments/vertical_slice/assumptions_l0.yaml; PLUS A-L0E-LAT / A-L0E-CHG — experiments/vertical_slice/assumptions_l0e.yaml (NEW this stage)",
            "declared_free_parameters": {
                "A-L0E-LAT": {"parameter": "endpoint.latency_ns", "registry_value": 0,
                              "registry_range": [0, 9000], "swept_by": "every S4e row (this stage's axis)"},
                "A-L0-LAT": {"parameter": "link.hop_latency_ns", "registry_value": 200,
                             "registry_range": [10, 2000], "swept_by": "NONE (S4 v1's axis; fixed at 200 here)"},
                "A-L0X-LAT": {"parameter": "link.pair_latency_ns", "registry_value": 200,
                              "registry_range": [10, 2000], "swept_by": "NONE (fixed at 200 here)"},
                "A-L0D-LAT": {"parameter": "link.pair_latency_ns", "registry_value": 200,
                              "registry_range": [10, 2000], "swept_by": "NONE (fixed at 200 here)"},
                "registry_note": "the A-L0E-LAT registry VALUE stays 0 and the three wire-latency registry VALUES stay 200 — UNCHANGED by this stage; B stays at the A-L0*-BW registry point 64 on every S4e row; the E range [0, 9000] is the registration's own (drawn from GF-10's fit-set figure; no holdout number enters it)",
            },
        },
        "group_g3_anchors": {
            "fit_targets": [
                "GF-10 — Li et al. (TPDS 32(1) 2020) measured V100-era app-level P2P ~9 us (latency_axis_point_measured; the software-inclusive quantity class; the PRIMARY E-anchor)",
                "CAL-A10 — HiPC 2025 Workshops UALink-vs-NVLink assumption 0.8 us end-to-end (latency_axis_point; assumption-class; the end-to-end E reading, context never target)",
                "CAL-A8 / CAL-A9 — wire-class/memory-class signals (emulated CXL band {64, 140}; design-estimate budget 80): E = 0 by quantity class; v1 L-axis placements immutable, never re-read onto E",
            ],
            "parameter_axes_duty": "A-L0E-LAT range discipline on the new axis; small-message O-CCT at the smoke regime predicted from this axis (predictions_for_s6e) for the EXTERNAL holdout check in S6e",
        },
        "executed_sweeps": {"e_axis": e_axis},
        "fits": {"gf10": fit_gf10(), "cal_a10": fit_a10(), "gf10_alt": fit_gf10_alt(), "wireclass": fit_wireclass()},
        "l_sensitivity_cross_checks": l_sensitivity(),
        "predictions_for_s6e": predictions(),
        "not_tuned": "the sweep grid was fixed by registry-range arithmetic (endpoints, powers of two) and the anchor-provenance points by the anchors' OWN staged figures under mappings declared in advance (t_p2p = L + E; end-to-end = L + E); every fit in this stage is degenerate (the anchor's own figure under the declared mapping IS the fitted E); the whole-figure reading was executed and FLAGGED, never selected; the A-L0E-LAT registry value stays 0, the wire-latency registry values stay 200, and no manifest outside this calibration directory carries any fitted value",
        "held_out": {
            "held_out": False,
            "scope": "all four stage runs and the sweep are fit-side (the split record defines no within-series holdout for any G3 anchor); the placements are recorded diagnostics handed to the S6e evaluation",
        },
        "store_run_cross_checks": store_run_cross_checks(),
        "verification": evidence["verification"],
        "known_omissions": evidence["known_omissions"],
        "independent_reproduction": evidence["independent_reproduction"],
        "backing": {
            "run_ids": [RUN_IDS[k] for k in ("gf10_e8800", "a10_e600", "gf10_alt_e9000", "wireclass_e0")],
            "run_roles": {RUN_IDS[k]: RUN_ROLES[k] for k in RUN_ROLES},
            "sweep_ids": [SWEEP_ID_E],
            "inputs": [
                "experiments/calibration/s4e/sweep_s4e_e_v1.yaml",
                "experiments/calibration/s4e/run_s4e_gf10_fit_e8800.yaml",
                "experiments/calibration/s4e/run_s4e_a10_fit_e600.yaml",
                "experiments/calibration/s4e/run_s4e_gf10_alt_e9000.yaml",
                "experiments/calibration/s4e/run_s4e_wireclass_e0.yaml",
                "experiments/calibration/s4e/topologies/ (42 files)",
                "experiments/calibration/s4e/profiles/ (3 files)",
                "experiments/vertical_slice/assumptions_l0e.yaml (the NEW endpoint-term registry)",
                "experiments/workloads/w1_dense_tp_decode_small.yaml (the committed smoke workload)",
                "experiments/calibration/s4/fit_record_v1.json (the immutable v1 record this stage completes, never edits)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/s4e/sweep_s4e_e_v1.yaml ; make run EXP=(each of the four run_s4e_*.yaml manifests) ; python experiments/calibration/s4e/build_fit_record.py",
            "s6e_handoff": "the fitted configurations this record hands to the S6e holdout evaluation: the endpoint-axis placements E = 8800 (GF-10 primary), 600 (CAL-A10 end-to-end reading), 0 (wire-class origin), and the flagged 9000 alternative — all recorded diagnostics, plus the smoke-regime predictions table (predictions_for_s6e)",
        },
        "headline": (
            "the endpoint term exists and the software-inclusive quantity class fits AS ITSELF: GF-10's measured app-level P2P places E = 8800 ns (IN range at 44/45 of the upper endpoint the anchor itself defines — where the v1 L reading sat OUT of range at 4.5x), CAL-A10's assumption-class end-to-end places E = 600, and the wire-class anchors place E = 0 by their own quantity class. "
            "All fits degenerate, mappings declared in advance, nothing tuned: the registry values stay (B=64, L=200, E=0). The fit-side placements span {0, 600, 8800} — the current-generation measured small-message floor decade is occupied by NO fit-side placement; whether it is REACHED, and what the anchors demand that the model still lacks, is the S6e evaluation's statement (next record). "
            "Chain laws survive at every shared E (the term is identity-invariant); the torus identity is excluded by registration; the v1 record stands unchanged as the wire-axis counterpart"
        ),
    }
    # cross-check 4: registry arithmetic sanity (a transcription bug fails here)
    assert E_GF10 == GF10_L_P2P - L_REG == Fraction(8800)
    assert E_A10 == A10_ENDTOEND - L_REG == Fraction(600)
    assert record["fits"]["gf10"]["fitted_E"]["derivation_exact"] == "9000 - 200 (t_p2p = L + E at the registry L)"
    assert record["fits"]["gf10"]["fitted_E"]["exact"] == "8800"
    assert record["fits"]["gf10"]["registry_placements"]["e_fit_over_range_upper_exact"] == "44/45"
    assert record["fits"]["cal_a10"]["fitted_E"]["derivation_exact"] == "800 - 200 (end-to-end = L + E at the registry L)"
    assert record["fits"]["cal_a10"]["registry_placements"]["e_placement_over_gf10_e_fit_exact"] == "3/44"
    assert record["fits"]["gf10"]["registry_placements"]["wire_share_of_anchor_figure_exact"] == "1/45"
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
