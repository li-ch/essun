"""Build the PROPOSED calibration re-fit record for stage TWIST (the H2
wiring-axis re-fit of the CAL-A5 falsifier after the wrap-edge wiring
model change, under the SAME immutable split record 3862e227...,
experiments/calibration/split/anchor_split_v1.json, group G4).

What this stage fits: NO O-CCT fit is claimed, exactly as at S5. CAL-A5
still stages no absolute (size -> time) series — its signal is the
dimensionless twisted-vs-regular geometry ratio. What CHANGED is the
model: the torus input space now carries the wrap-edge wiring factor
(link.wrap_wiring_factor, free parameter A-L0T-WIRE, declared range
[1/2, 2], registry point 1 — experiments/vertical_slice/
assumptions_l0tw.yaml), so the S5 falsification's STRUCTURAL leg ("the
input schema carries NO geometry field", record 43fca722...) is closed
as input blindness. This stage re-executes the falsifier against the
now-existing axis and measures WHAT THE ANCHOR DEMANDS OF IT:

1. ONE-SIDED LAW (executed): the wiring term enters through the pipeline
   min-link bound rate = B*min(1, w), so every w >= 1 row equals the w=1
   row EXACTLY (the ring's k-1 non-wrap edges bound its rate — the
   twist's capacity-gain direction is inert on this identity) and every
   w < 1 row equals the landed identity at per-link B*w exactly (the
   derating side coincides with a B displacement) — asserted as exact
   Fraction string equality on every executed row of both sweeps;
2. IMMUTABILITY BRIDGE (executed): the declared w=1 row and the
   committed stage-A5 anchor-point row (undeclared wiring) execute
   byte-equal CCTs, and the active-side rows equal the S5 record's own
   committed B=25/B=32-class rows at the faithful shapes — this stage
   re-derives S5's arithmetic from a superset schema without moving it;
3. THE DEMAND (exact arithmetic, the S5 metric discipline unchanged):
   the anchor's ratios 1.63 (r=128) / 1.31 (r=256) read onto the model's
   own anchor-point CCT demand twisted CCTs 909696/163 / 1550208/131 ns —
   BELOW the identity's B->infinity latency-chain floors (8800 / 15200
   ns), so the unbounded B axis delivers at most 5.356%/6.411% of the
   required gain (S5's numbers, re-derived exactly here), and the wiring
   axis delivers EXACTLY 0% of it: the axis's whole envelope (every
   admissible w, in or out of the declared range) has minimum CCT equal
   to the regular CCT — the demand lies below the axis's entire range,
   both directions (w < 1 only makes the ring slower);
4. MISATTRIBUTION LEGS (cited from S5, never selected): the only
   single-parameter routes to the demanded CCT remain the in-range
   L-absorption values 5383072/44825 (~120.09) / 9441472/62225
   (~151.73) ns — charging a bisection-structure effect to per-hop
   latency — and the B-axis displacement rows (81.5 / 65.5) S5 already
   executed and classified. The wiring field's arrival changes none of
   them.

The finding is a SHARPENED FALSIFICATION, not a fit: the missing
expressiveness was never the FIELD, it is the COLLECTIVE — the anchor's
observable class is bisection-bound ALL-TO-ALL throughput, which no L0
identity in this repo executes; on every identity the torus family
executes (per-dimension ring-decomposed AllReduce) a wiring-capacity gain
is provably inert (the min-link bound). NOTHING IS TUNED: the registry
point of A-L0T-WIRE stays 1 (regular), A-L0T-BW stays 64, no anchor
value selects any parameter value, and the anchor's ratios 1.63/1.31 are
NOT members of the swept uniform grid.

Run-backed cross-checks enforced here (a mismatch is a bug, not a
finding): every executed row of both sweeps equals the closed form of the
wiring-extended identity at the same (payload, shape, B, L, w) by exact
Fraction string equality; both store runs equal the same closed forms,
carry the declared v2 evidence dimensions (calibration_target CAL-A5,
held_out FALSE), record the declared factor in their model payloads, and
execute CCTs byte-equal in every time field to the stage-A5 anchor runs.

Pure function of immutable artifacts: reads the two append-only store
sweep tables and the two store run records produced by this stage,
recomputes every derived quantity with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/
record.json`` plus the committed copy
``experiments/calibration/twist/twist_record_v1.json`` (byte-identical;
append-only — an existing record with different bytes is an error, a
change requires twist_record_v2). No wall-clock, no host metadata.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim, label, or shipped parameter value changes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical.l0_torus2d import Torus2DConfig
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
SWEEP_ID_TORUS128 = "4328bb00dd7dcae76a342d60d0fec306e707ca66c991e6affcbe295a21cd03f3"
SWEEP_ID_TORUS256 = "b6e40ab682800841306618730a49c4e3c07f1d319f3d8c6ae0982103f3aac86a"
RUN_IDS = {
    "twist128": "6197d3adf776ab8479caa2ec88e5c7acd325c1b78a183935ff8d1bcbf5dc5da8",
    "twist256": "1e55ccfa2d10ca5a113b4263d91f76d6b83bd5808599c3b3deadee257634f0f1",
}
RUN_ROLES = {
    "twist128": "twist-direction executed-invariance reference run (torus 8x16, B=50 reading 1, w=2 range ceiling; held_out: false)",
    "twist256": "twist-direction executed-invariance reference run (torus 8x32, B=50 reading 1, w=2 range ceiling; held_out: false)",
}
RUN_EXPERIMENT_IDS = {
    "twist128": "EXP-CAL-TWIST-A5-REFIT-128-001",
    "twist256": "EXP-CAL-TWIST-A5-REFIT-256-001",
}

RESULTS = REPO_ROOT / "results"
TWIST_DIR = REPO_ROOT / "experiments" / "calibration" / "twist"
COMMITTED_COPY = TWIST_DIR / "twist_record_v1.json"
S5_RECORD = REPO_ROOT / "experiments" / "calibration" / "s5" / "fit_record_v1.json"

# ---------------------------------------------------------------------------
# Anchor staged numbers (transcription sources unchanged from S5: the
# committed E1 builders at experiments/calibration/a5/ and the staging
# doc anchors_staging.md §A5). Nothing else is read; nothing is re-fetched.
# ---------------------------------------------------------------------------
A5_TWIST = {128: Fraction(163, 100), 256: Fraction(131, 100)}  # twisted vs regular, all-to-all
A5_READING1 = Fraction(50)   # per-link per-direction ("400 vs. 200 Gbit/s")
A5_DMA_BYTES = 4096          # "individual DMAs of 4 KiB"
FAITHFUL = {128: (8, 16), 256: (8, 32)}        # declared 3D->2D projections

# Registry / free-parameter discipline (UNCHANGED by this stage).
L_REG = Fraction(200)                  # A-L0T-LAT registry point (fixed this stage)
B_REG = Fraction(64)                   # A-L0T-BW registry value
W_REG = Fraction(1)                    # A-L0T-WIRE registry point: the regular torus
W_RANGE = (Fraction(1, 2), Fraction(2))
W_GRID = [Fraction(1, 2), Fraction(3, 4), Fraction(1), Fraction(5, 4),
          Fraction(3, 2), Fraction(7, 4), Fraction(2)]  # uniform quarter steps
CAL_A6_SWING_UPPER = Fraction(8, 100)  # CAL-A6 software-version swing upper (fit-set anchor, G2)

# S5's own committed values this stage re-derives as the immutability
# bridge (read from the committed S5 record, never re-fitted):
S5_IDS = {
    "s5_fit_record": "43fca722ff77711d67b2879dca1407510dd6a60132e047d6b34fd7b7ee6bb34b",
    "s5_run_slice128": "43091e1545280c151bb56769897cff7e538e3c3e8935d8ab11bb5599d49c9458",
    "s5_run_slice256": "645e8b4f2a733ab358c60be719c1575757ec21bc6ed0ffd8402c7a146fbbb6b5",
    "split": "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20",
}
S5_L_ABSORPTION = {  # flagged misattribution values, cited never selected
    128: (Fraction(5383072, 44825), "120.090842163971"),
    256: (Fraction(9441472, 62225), "151.73116914423463"),
}
S5_B_DELIVERED = {  # unbounded-B delivered fraction of the required gain
    128: Fraction(928, 17325),   # 5.356%
    256: Fraction(944, 14725),   # 6.411%
}


def pct(x: Fraction) -> float:
    return float(x) * 100.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Closed forms (exact) — the wiring-extended identity.
# ---------------------------------------------------------------------------
def rate_limit(w: Fraction) -> Fraction:
    """The pipeline min-link factor min(1, w) on the ring rate."""
    return min(Fraction(1), w)


def t_torus(payload: int, r1: int, r2: int, b: Fraction, w: Fraction,
            l: Fraction = L_REG) -> Fraction:
    """t_2d with the wiring term: each ring runs at B*min(1, w).

    t_ring(M, k) = 2*(k-1)/k*M/(B*min(1,w)) + 2*(k-1)*L; t_2d = sum of dims.
    """
    def ring(k: int) -> Fraction:
        return Fraction(2 * (k - 1) * payload, k) / (b * rate_limit(w)) + 2 * (k - 1) * l
    return ring(r1) + ring(r2)


def torus_latency_chain(r1: int, r2: int, l: Fraction = L_REG) -> Fraction:
    return 2 * (r1 - 1) * l + 2 * (r2 - 1) * l


def torus_bandwidth_bytes(payload: int, r1: int, r2: int) -> Fraction:
    """Per-rank wire bytes = the bandwidth-term bytes: 2*(2 - 1/r1 - 1/r2)*M."""
    return Fraction(2 * (r1 - 1) * payload, r1) + Fraction(2 * (r2 - 1) * payload, r2)


def parse_twist_topo(topo_id: str) -> tuple[Fraction, Fraction, tuple[int, int], int]:
    """torus2d128_tw_8x16_b50_w1_5_v1 -> (B, w, shape, ranks)."""
    parts = topo_id.split("_")
    assert parts[1] == "tw", topo_id  # twist-stage files only
    ranks = int(parts[0].removeprefix("torus2d"))
    shape = (int(parts[2].split("x")[0]), int(parts[2].split("x")[1]))
    # stem "b50_w1_5" (the w value itself contains the underscore we split on)
    stem = topo_id.split("_b", 1)[1].rsplit("_v1", 1)[0]
    b_part, w_part = stem.split("_w", 1)
    # "_" -> "." so "1_5" reads as 1.5 exactly (never as the digit separator
    # Python's Fraction would accept inside "1_5")
    return Fraction(b_part.replace("_", ".")), Fraction(w_part.replace("_", ".")), shape, ranks


def parse_a5_topo(topo_id: str) -> tuple[Fraction, tuple[int, int], int]:
    """torus2d128_a5_8x16_b50_v1 -> (B, shape, ranks) (undeclared wiring)."""
    parts = topo_id.split("_")
    ranks = int(parts[0].removeprefix("torus2d"))
    shape = (int(parts[2].split("x")[0]), int(parts[2].split("x")[1]))
    return Fraction(parts[3].removeprefix("b")), shape, ranks


def sweep_rows(sweep_id: str) -> list[dict]:
    return load_json(RESULTS / "sweeps" / sweep_id / "table.json")["configs"]


# ---------------------------------------------------------------------------
# 1. The wiring-law sweep blocks (executed-sweep reconciliation).
# ---------------------------------------------------------------------------
def twist_sweep_block(sweep_id: str, ranks: int, name: str, manifest: str) -> dict:
    faithful = FAITHFUL[ranks]
    rows = []
    by_w: dict[Fraction, Fraction] = {}
    bridge_b: dict[Fraction, Fraction] = {}
    n = 0
    for row in sweep_rows(sweep_id):
        topo = row["config_id"].split("-")[2]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        assert row["payload_bytes"] == A5_DMA_BYTES
        if topo.startswith(f"torus2d{ranks}_tw_"):
            b, w, shape, r = parse_twist_topo(topo)
            assert r == ranks and shape == faithful, topo
            # closed-form reconciliation at the declared (B, w)
            assert cct == t_torus(A5_DMA_BYTES, shape[0], shape[1], b, w), topo
            # wire traffic is wiring-invariant: 2*(2 - 1/r1 - 1/r2)*M
            assert wire == torus_bandwidth_bytes(A5_DMA_BYTES, shape[0], shape[1]), topo
            if b == A5_READING1:
                by_w[w] = cct
            rows.append({
                "topology_id": topo,
                "B_exact": str(b),
                "w_exact": str(w),
                "shape": f"{shape[0]}x{shape[1]}",
                "family": ("anchor_w_grid" if b == A5_READING1 else "registry_B64_triangle"),
                "cct_ns_exact": str(cct),
                "cct_ns_float": float(cct),
                "min_link_rate_factor_exact": str(rate_limit(w)),
                "effective_rate_exact": str(b * rate_limit(w)),
                "wire_bytes_per_rank_exact": str(wire),
            })
        else:
            # the committed stage-A5 anchor-point row (undeclared wiring)
            b, shape, r = parse_a5_topo(topo)
            assert r == ranks and shape == faithful and b == A5_READING1, topo
            assert cct == t_torus(A5_DMA_BYTES, shape[0], shape[1], b, Fraction(1)), topo
            bridge_b[b] = cct
            rows.append({
                "topology_id": topo,
                "B_exact": str(b),
                "w_exact": "1 (UNDECLARED — the landed identity)",
                "shape": f"{shape[0]}x{shape[1]}",
                "family": "immutable_s5_bridge",
                "cct_ns_exact": str(cct),
                "cct_ns_float": float(cct),
                "min_link_rate_factor_exact": "1",
                "effective_rate_exact": str(b),
                "delta_vs_w1_exact": "0",
                "wire_bytes_per_rank_exact": str(wire),
            })
        n += 1
    assert n == 11, n
    # THE ONE-SIDED LAW, executed and asserted:
    base = by_w[Fraction(1)]
    assert bridge_b[A5_READING1] == base  # declared-1 == undeclared == S5 anchor point
    for w in W_GRID:
        assert w in by_w, (ranks, w)
        if w >= 1:
            assert by_w[w] == base, (ranks, w)  # EXACTLY inert in the gain direction
        else:
            assert by_w[w] > base, (ranks, w)   # the derating side is strictly slower
            # ... and coincides exactly with the landed identity at B*w
            assert by_w[w] == t_torus(A5_DMA_BYTES, faithful[0], faithful[1],
                                       A5_READING1 * w, Fraction(1)), (ranks, w)
    # the registry-point triangle executed the same law at B=64
    b64_rows = {Fraction(r["w_exact"]): Fraction(r["cct_ns_exact"])
                for r in rows if r["family"] == "registry_B64_triangle"}
    assert set(b64_rows) == {Fraction(1, 2), Fraction(1), Fraction(2)}
    assert b64_rows[Fraction(1)] == b64_rows[Fraction(2)]
    assert b64_rows[Fraction(1, 2)] == t_torus(A5_DMA_BYTES, faithful[0], faithful[1],
                                               B_REG * Fraction(1, 2), Fraction(1))
    return {
        "sweep_id": sweep_id,
        "sweep_name": name,
        "manifest_path": manifest,
        "grid": "11 configs x 6 ops at payload 4096 (the anchor's DMA size)",
        "cross_check": "every executed row equals the wiring-extended closed form at the same (payload, shape, B, L=200, w) — exact Fraction string equality; wire bytes equal 2*(2-1/r1-1/r2)*M at EVERY w (wiring moves rates, never bytes)",
        "payload_fence": "single payload 4096 = the anchor's individual DMA size (fit-side; no within-series holdout exists for CAL-A5)",
        "one_sided_law_executed": {
            "statement": f"every w >= 1 row equals the w=1 row EXACTLY ({str(base)} ns) — the twist's capacity-gain direction is inert on this identity (the ring's k-1 non-wrap edges bound its rate); every w < 1 row is strictly slower and equals the landed identity at per-link B*w exactly (the derating side coincides with a B displacement)",
            "inert_rows_exact": [str(by_w[w]) for w in W_GRID if w >= 1],
            "active_rows_exact": {str(w): str(by_w[w]) for w in W_GRID if w < 1},
            "bridge_row_exact": str(bridge_b[A5_READING1]),
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 2. The CAL-A5 wiring-axis re-fit (the falsifier re-executed).
# ---------------------------------------------------------------------------
def fit_cal_a5_twist() -> dict:
    # (a) the structural leg is CLOSED as input blindness: the landed
    # schema now carries the field (exact pin of the live schema).
    fields = {f.name for f in dataclasses.fields(Torus2DConfig)}
    assert fields == {"topology_id", "ranks", "dim1_ranks", "dim2_ranks",
                      "link_bytes_per_ns", "hop_latency_ns",
                      "wrap_wiring_factor"}, fields

    per_slice = {}
    for ranks, faithful in FAITHFUL.items():
        r1, r2 = faithful
        anchor_cct = t_torus(A5_DMA_BYTES, r1, r2, A5_READING1, Fraction(1))
        floor = torus_latency_chain(r1, r2)
        ratio = A5_TWIST[ranks]
        required = anchor_cct / ratio
        # the whole wiring axis's minimum is the regular CCT (both sides)
        axis_min = anchor_cct  # w>=1: exactly anchor; w<1: strictly above
        # demanded throughput gain vs the axis's best (w in the gain direction)
        demanded_gain = ratio - 1                     # 63% / 31%
        b_axis_gain = anchor_cct / floor - 1          # B -> infinity
        b_delivered = b_axis_gain / demanded_gain
        w_delivered = Fraction(0)                     # exactly 0, both directions
        assert b_delivered == S5_B_DELIVERED[ranks]   # S5's numbers, re-derived
        assert required < floor < anchor_cct
        per_slice[ranks] = {
            "anchor_point_cct_ns_exact": str(anchor_cct),
            "b_to_infinity_latency_chain_floor_ns_exact": str(floor),
            "measured_twisted_over_regular_all_to_all_exact": str(ratio),
            "required_twisted_cct_ns_exact": str(required),
            "required_twisted_cct_ns_float": float(required),
            "demanded_cct_cut_pct": pct(demanded_gain),
            "wiring_axis_verdict": {
                "axis_minimum_cct_ns_exact": str(axis_min),
                "statement": (
                    f"the wiring axis's ENTIRE envelope (every admissible w, in or out "
                    f"of the declared range [1/2, 2]) has minimum CCT exactly the "
                    f"regular CCT {str(anchor_cct)} ns: w >= 1 is exactly inert (the "
                    f"min-link bound) and w < 1 only derates — the demanded "
                    f"{str(required)} ns lies BELOW the axis's whole range, so the "
                    f"axis delivers EXACTLY 0% of the demanded gain"
                ),
                "delivered_fraction_of_required_gain_exact": str(w_delivered),
                "delivered_fraction_pct": pct(w_delivered),
                "versus_unbounded_b_axis": {
                    "delivered_fraction_exact": str(b_delivered),
                    "delivered_fraction_pct": pct(b_delivered),
                    "note": "the B axis at least delivers its bandwidth-term share even unbounded (S5's 928/17325 and 944/14725, re-derived exactly here); the wiring axis delivers exactly 0 — strictly less expressible, and in the WRONG place to matter",
                },
            },
            "l_absorption_misattribution_leg": {
                "value_exact": str(S5_L_ABSORPTION[ranks][0]),
                "value_float": S5_L_ABSORPTION[ranks][1],
                "in_declared_range": True,
                "status": "STANDS UNCHANGED from S5 (record 43fca722...): the only single-parameter routes to the demanded CCT are the L-absorption values — charging a bisection-structure effect to per-hop latency — and the B displacement rows S5 already executed and classified (81.5 / 65.5); the wiring field's arrival changes none of them; recorded, never selected",
            },
            "floor_margin_exact": str(required / floor),
        }

    return {
        "role": "topology-sensitivity FALSIFIER, re-executed on the now-existing wiring axis (plan §1.1 row CAL-A5; A-L0T-WIRE is the honest expressiveness added; the anchor's ratio still selects NOTHING)",
        "split_role": "DEGENERATE (no series) — unchanged: the anchor's whole staged signal is fit-side; the split record defines NO within-series holdout for CAL-A5",
        "staged_signal": "TPU v4 measured twisted-vs-regular torus all-to-all ratios 1.63x (4x4x8, r=128) / 1.31x (4x8x8, r=256) at individual 4 KiB DMAs; per-link ICI 6 links @ 50 GB/s (direction convention UNVERIFIED — both readings remain executed from S5, neither chosen); NO absolute (size -> time) series exists, so no CCT-vs-CCT comparison is defined",
        "metric_discipline": "ratio vs ratio, the S5 discipline UNCHANGED: all-to-all throughput and AllReduce CCT are never compared; the anchor's ratio is read onto the model's OWN anchor-point CCT only to compute what the ratio demands of the model",
        "structural_leg_status": {
            "s5_claim": "the input schema carries NO geometry field (verified against the landed Torus2DConfig) — twisted and regular tori of the same (r1, r2, B, L) map to IDENTICAL model inputs (record 43fca722..., falsification_1_structural)",
            "now": "CLOSED AS INPUT BLINDNESS: the schema carries link.wrap_wiring_factor (A-L0T-WIRE) and the executed sweeps distinguish the inputs — but the model's OUTPUT is exactly invariant in the twist's capacity-gain direction (the min-link bound), so the model's twisted/regular AllReduce-CCT ratio is STILL exactly 1 for every w >= 1",
            "why": "a uniform-ring AllReduce has no bottleneck link: its rate is set by its k-1 non-wrap edges, and the twist's mechanism (wrap/bisection capacity redistribution) cannot speed a balanced ring — it acts on collectives whose bottleneck is the CUT (all-to-all), which no L0 identity in this repo executes",
        },
        "per_slice": {str(k): v for k, v in per_slice.items()},
        "sharpened_falsification": (
            "CAL-A5's 63%/31% geometry effect remains INEXPRESSIBLE, now with the "
            "field present: the missing expressiveness is not a geometry FIELD (that "
            "is added, registered free, and never tuned) but a geometry-SENSITIVE "
            "TERM — an all-to-all / bisection-bound collective identity. On every "
            "identity the torus family executes (per-dimension ring-decomposed "
            "AllReduce), a wiring-capacity gain is provably inert (min-link bound, "
            "executed at both slices and at the registry B), the unbounded B axis "
            "delivers at most 5.356%/6.411% of the demanded gain (S5, re-derived), "
            "and the only single-parameter routes to the demand are the flagged "
            "L-absorption misattributions (120.09/151.73 ns). Any future absorption "
            "of this anchor requires a new COLLECTIVE identity (all-to-all with a "
            "bisection/wiring term), recorded here as the standing requirement — "
            "building one NOW to reach 1.63/1.31 would be tuning toward the anchor, "
            "and is out of bounds by the program fence"
        ),
        "per_link_placement": {
            "readings_vs_plan_span_20_64": "UNCHANGED from S5 (20/25/50 inside, 70 above, both readings executed, neither chosen); the registry point 64 sits +28% above reading 1 — a PLACEMENT fact, the registry value untouched",
            "registry_wiring_point": {
                "value": "1 (the regular torus — every existing topology)",
                "statement": "the A-L0T-WIRE registry point stays 1: no anchor value selects any wiring value, and the anchor's ratios 1.63/1.31 are NOT members of the swept uniform grid (membership is pure registry-range arithmetic)",
            },
        },
        "noise_scale_comparison_provenance": (
            "the demanded cuts (63%/31%) remain 7.875x / 3.875x CAL-A6's 8% "
            "software-version swing upper (a FIT-SET anchor, group G2) — an order "
            "above every noise scale in the anchor set, so the effect cannot be "
            "absorbed as measurement noise (unchanged from S5)"
        ),
    }


# ---------------------------------------------------------------------------
# 3. Store-run cross-checks.
# ---------------------------------------------------------------------------
def run_summary(run_key: str, mapping: str) -> dict:
    run_id = RUN_IDS[run_key]
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]
    payload = per_op["payload_bytes"]
    cct = Fraction(per_op["completion_time_ns_exact"])
    model = obs["model"]
    b = Fraction(model["link_bytes_per_ns_exact"])
    l_val = Fraction(model["hop_latency_ns_exact"])
    w = Fraction(model["wrap_wiring_factor_exact"])  # declared -> recorded
    shape = (model["dim1_ranks"], model["dim2_ranks"])
    assert model["wrap_rate_limit_exact"] == "1"  # min(1, 2): the executed law
    expected = t_torus(payload, shape[0], shape[1], b, w, l_val)
    assert cct == expected, (run_key, cct, expected)
    # the invariance: this w=2 run's CCT equals the regular anchor point EXACTLY
    regular = t_torus(payload, shape[0], shape[1], b, Fraction(1), l_val)
    assert cct == regular, (run_key, cct, regular)
    assert run["manifest"]["experiment_id"] == RUN_EXPERIMENT_IDS[run_key]
    assert run.get("evidence_schema_version") == 2
    assert run.get("calibration_target") == ["CAL-A5"]
    assert run.get("held_out", {}).get("held_out") is False
    return {
        "run_id": run_id,
        "calibration_target": ["CAL-A5"],
        "mapping": mapping,
        "experiment_id": RUN_EXPERIMENT_IDS[run_key],
        "identity": f"torus2d {shape[0]}x{shape[1]} (B={b}, L={l_val}, w={w} declared at the range ceiling)",
        "payload_bytes": payload,
        "cct_ns_exact": str(cct),
        "cct_ns_float": float(cct),
        "held_out": False,
        "verdict": (
            "store run == closed form of the wiring-extended identity (exact Fraction "
            "string equality) AND == the regular anchor-point CCT exactly (the "
            "executed invariance at the range ceiling); v2 dimensions as declared "
            "(held_out: false); the model payload records the declared factor with "
            "its min-link rate limit 1"
        ),
    }


def store_run_cross_checks() -> list[dict]:
    return [
        run_summary(
            "twist128",
            "twist-direction executed-invariance reference: the faithful 8x16 projection at B=50 (reading 1), L=200, w=2, payload 4096 — CCT byte-equal in every time field to the S5 anchor run 43091e15...",
        ),
        run_summary(
            "twist256",
            "twist-direction executed-invariance reference: the faithful 8x32 projection at B=50 (reading 1), L=200, w=2, payload 4096 — CCT byte-equal in every time field to the S5 anchor run 645e8b4f...",
        ),
    ]


# ---------------------------------------------------------------------------
# 4. The S5 immutability bridge: this stage's active-side rows re-derive
# S5's own committed B-displacement rows (read from the committed record).
# ---------------------------------------------------------------------------
def s5_bridge() -> dict:
    s5 = load_json(S5_RECORD)
    checks = []
    for ranks, sweep in (("128", "torus128"), ("256", "torus256")):
        s5_rows = {
            Fraction(r["B_exact"]): Fraction(r["cct_ns_exact"])
            for r in s5["executed_sweeps"][sweep]["rows"]
            if r["faithful_projection"]
        }
        faithful = FAITHFUL[int(ranks)]
        # our active-side rows equal S5's executed rows at B = 50*w
        for w in (Fraction(1, 2), Fraction(3, 4)):
            b_equiv = A5_READING1 * w
            ours = t_torus(A5_DMA_BYTES, faithful[0], faithful[1], A5_READING1, w)
            theirs = s5_rows.get(b_equiv)
            if theirs is not None:
                assert ours == theirs, (ranks, w, ours, theirs)
                checks.append({
                    "slice": ranks,
                    "w_exact": str(w),
                    "equivalent_B_exact": str(b_equiv),
                    "twist_stage_cct_exact": str(ours),
                    "s5_committed_row_cct_exact": str(theirs),
                })
            else:
                ours_closed = t_torus(A5_DMA_BYTES, faithful[0], faithful[1],
                                      b_equiv, Fraction(1))
                assert ours == ours_closed
                checks.append({
                    "slice": ranks,
                    "w_exact": str(w),
                    "equivalent_B_exact": str(b_equiv),
                    "twist_stage_cct_exact": str(ours),
                    "s5_committed_row_cct_exact": None,
                    "note": "no committed S5 row at this B (the S5 grid was {64k}); the equality with the landed identity at B*w is asserted against the closed form",
                })
        # the anchor point itself: S5's B=50 row == our w=1 row
        assert s5_rows[A5_READING1] == t_torus(A5_DMA_BYTES, faithful[0], faithful[1],
                                               A5_READING1, Fraction(1))
        checks.append({
            "slice": ranks,
            "w_exact": "1",
            "equivalent_B_exact": str(A5_READING1),
            "twist_stage_cct_exact": str(t_torus(A5_DMA_BYTES, faithful[0], faithful[1],
                                                 A5_READING1, Fraction(1))),
            "s5_committed_row_cct_exact": str(s5_rows[A5_READING1]),
            "note": "the anchor point: S5's committed B=50 row == the declared w=1 row == the undeclared bridge row",
        })
    return {
        "statement": "the wiring axis's ACTIVE side is exactly the B axis it displaces: this stage's w<1 rows equal the S5 record's own committed rows at B = 50*w where such rows exist (exact Fraction equality against the committed S5 copy, never re-fitted) — the re-fit re-derives S5's arithmetic from a superset schema without moving it",
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# 5. Evidence dimensions + assembly.
# ---------------------------------------------------------------------------
def evidence_dimensions_block() -> dict:
    return {
        "verification": [
            {
                "check": "tests/calibration/test_twist_fit.py",
                "scope": "TWIST-stage guard — re-executes the stage's two sweeps and two runs into a scratch store, rebuilds this record byte-identically, and checks the invariants (the one-sided law exact at every executed row; the anchor-point/bridge-row equality; no holdout anchor id anywhere in the record bytes; the A-L0T-WIRE registry point untouched at 1 and A-L0T-BW at 64; the demanded-CCT-below-the-whole-wiring-axis arithmetic exact at both slices)",
            },
            {
                "check": "tests/golden/test_l0_torus2d_wiring_golden.py",
                "scope": "the wiring term's golden identities (hand-derived): the one-sided law, the B-displacement equivalence of the active side, wiring-invariant conservation and traffic, the loader's declared/undeclared payload contract",
            },
            {
                "check": "tests/calibration/test_anchor_split.py",
                "scope": "the split record's own immutability guard (S1) — the data separation this re-fit runs under",
            },
            {
                "check": "tests/calibration/test_s5_fit.py",
                "scope": "the S5 record's byte-immutability guard — the historical falsification this stage sharpens (its Torus2DConfig check is now a superset check on the six v1 fields; the S5 record bytes are unchanged)",
            },
        ],
        "calibration_target": ["CAL-A5"],
        "held_out": {
            "held_out": False,
            "scope": "this re-fit touches only CAL-A5's staged geometry ratios and per-link readings; the split record defines NO within-series holdout for CAL-A5, every row is fit-side, and no held-out anchor id appears anywhere in this record's bytes",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "the identity's OUTPUT is exactly invariant in the twist's capacity-gain direction (min-link bound): the measured 1.63x/1.31x is unreachable on the wiring axis at any admissible w — the axis's whole envelope has minimum CCT equal to the regular CCT",
            "the demanded twisted CCTs (5580.96 / 11833.65 ns) lie BELOW the identity's B->infinity latency-chain floors (8800 / 15200 ns) — unreachable on the unbounded B axis (S5) and on the whole wiring axis (this stage)",
            "the anchor's observable class is bisection-bound ALL-TO-ALL throughput: no L0 identity in this repo executes all-to-all, so the geometry effect has no observable to land on — the standing requirement is a new COLLECTIVE identity (all-to-all with a bisection/wiring term), not a new parameter",
            "the L-absorption values (120.09 / 151.73 ns) remain the only single-parameter routes to the demand — misattribution class, recorded never selected (unchanged from S5)",
            "3D slices projected 3D->2D (declared projection, distortion declared in every topology file); per-link direction convention UNVERIFIED (both readings remain executed from S5, neither chosen)",
            "no software/endpoint latency term on this backend yet (the parallel H1 program owns that axis); the 4 KiB regime is hop-latency-dominated (96.7% / 98.1% at the faithful shapes)",
            "no congestion, no credits, no packetization, no reconfiguration (static topology; OCS ms-scale switching is quasi-static and bounds only dynamic-topology modeling)",
        ],
    }


def build_record() -> dict:
    torus128 = twist_sweep_block(SWEEP_ID_TORUS128, 128, "cal_twist_torus128_v1",
                                 "experiments/calibration/twist/sweep_twist_torus128_v1.yaml")
    torus256 = twist_sweep_block(SWEEP_ID_TORUS256, 256, "cal_twist_torus256_v1",
                                 "experiments/calibration/twist/sweep_twist_torus256_v1.yaml")
    a5 = fit_cal_a5_twist()
    runs = store_run_cross_checks()
    bridge = s5_bridge()
    evidence = evidence_dimensions_block()
    record = {
        "record_kind": "calibration_fit",
        "stage": "calibration re-fit record, TWIST (the H2 wiring-axis re-fit of the CAL-A5 falsifier after the wrap-edge wiring model change; group G4)",
        "status": "PROPOSED — owner adjudication required; no claim, label, or shipped parameter value changes; NO O-CCT fit exists on this axis and none is claimed — the deliverable is a SHARPENED FALSIFICATION (docs/calibration/TORUS_TWIST_REFIT.md)",
        "evidence_schema_version": 2,
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay reproduces byte-identical artifacts)",
            "fit": "PROPOSED wiring-axis falsification re-execution against one external published ratio pair; no E3/E4 language — the anchor is not our testbed, and owner adjudication precedes any label move",
        },
        "calibration_target": ["CAL-A5"],
        "split_record": {
            "record_id": S5_IDS["split"],
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "group": "G4 — torus-geometry falsifier + UEC-class transport / congestion-management envelopes (fitting stage S5; this stage re-fits that group's falsifier axis after a model change, per the S7 dispatch's model-fix-then-refit pattern)",
            "within_series_rules": "CAL-A5 carries NO within-series split (the split record's within_series_splits lists only CAL-A3/CAL-A6/GF-02/GF-04); the anchor's whole staged signal is fit-side and no held-out reporting run exists in this stage",
            "immutability": "the split record is IMMUTABLE and untouched: same split, same group assignment, same holdout set (the holdout stays holdout); the re-fit changes the MODEL's input space, never the data separation",
            "no_leakage": "none of the split record's cross-anchor holdouts or its blocked anchor is read by any objective, swept value, or tolerance in this record (mechanically asserted: their ids appear nowhere in the record bytes)",
        },
        "model": {
            "backend_ids": ["analytical_l0_torus2d"],
            "identity": "t_2d(M, r1, r2) = t_ring(M, r1) + t_ring(M, r2) with t_ring(M, k) = 2*(k-1)/k*M/(B*min(1, w)) + 2*(k-1)*L — the landed identity at the min-link effective rate; w is the wrap-edge wiring factor (link.wrap_wiring_factor, free parameter A-L0T-WIRE, registry point 1 = the regular torus, declared range [1/2, 2] structural bounds)",
            "one_sided_law": "rate = B*min(1, w): every w >= 1 equals w = 1 EXACTLY (the ring's k-1 non-wrap edges bound its rate — the twist's capacity-gain direction is inert on this identity); every w < 1 equals the landed identity at B*w (the derating side coincides with a per-link-B displacement); wire counts, hop latency, and O-CONSERVATION never move",
            "assumptions": {
                "landed": "A-L0T-SEQ / A-L0T-UNIF / A-L0T-SHAPE / A-L0T-BW / A-L0T-LAT / A-L0T-DIV (experiments/vertical_slice/assumptions_l0.yaml, untouched)",
                "new": "A-L0T-WIRE (experiments/vertical_slice/assumptions_l0tw.yaml — a SEPARATE file so the hashed assumptions_l0.yaml inputs of the landed ladder do not re-hash)",
            },
        },
        "backing": {
            "inputs": [
                "experiments/calibration/twist/sweep_twist_torus128_v1.yaml",
                "experiments/calibration/twist/sweep_twist_torus256_v1.yaml",
                "experiments/calibration/twist/run_twist_a5_slice128.yaml",
                "experiments/calibration/twist/run_twist_a5_slice256.yaml",
                "experiments/calibration/twist/topologies/ (20 files)",
                "experiments/calibration/twist/profiles/implementation_profile_l0_torus2d_cal_twist_v1.yaml",
                "experiments/calibration/a5/workloads/w1_dense_tp_decode_tp{128,256}_4kib.yaml (committed stage-A5 workloads, reused)",
                "experiments/calibration/a5/topologies/torus2d{128,256}_a5_{8x16,8x32}_b50_v1.yaml (the committed stage-A5 anchor-point files, reused as the immutable-S5 bridge rows)",
                "experiments/calibration/s5/fit_record_v1.json (the committed S5 record, READ for the immutability bridge — never re-fitted, never edited)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/twist/sweep_twist_torus128_v1.yaml ; make sweep EXP=experiments/calibration/twist/sweep_twist_torus256_v1.yaml ; make run EXP=experiments/calibration/twist/run_twist_a5_slice128.yaml ; make run EXP=experiments/calibration/twist/run_twist_a5_slice256.yaml ; python experiments/calibration/twist/build_twist_record.py",
            "run_ids": [RUN_IDS[k] for k in RUN_IDS],
            "run_roles": {k: RUN_ROLES[k] for k in RUN_IDS},
            "sweep_ids": [SWEEP_ID_TORUS128, SWEEP_ID_TORUS256],
        },
        "executed_sweeps": {
            "torus128": torus128,
            "torus256": torus256,
        },
        "fits": {
            "cal_a5_twist_refit": a5,
        },
        "store_run_cross_checks": runs,
        "s5_immutability_bridge": bridge,
        "prior_records": {
            "s5_fit_record_id": S5_IDS["s5_fit_record"],
            "s5_run_ids": {"slice128": S5_IDS["s5_run_slice128"],
                            "slice256": S5_IDS["s5_run_slice256"]},
            "relationship": "this record SHARPENS the S5 falsification (structural input blindness -> output invariance on a now-existing axis + the collective-class gap); it does not replace, edit, or re-fit the S5 record, whose bytes and committed copy are unchanged",
        },
        "evidence_dimensions": evidence,
        "registry_state_unchanged": {
            "A-L0T-WIRE": {"value": "1", "range": "[1/2, 2] (declared, structural bounds)"},
            "A-L0T-BW": {"value": "64", "range": "[1, 1024]"},
            "statement": "no registry value or range moves in this stage; no anchor output selects any parameter value; the anchor's ratios 1.63/1.31 are not sweep-grid members",
        },
    }
    # fence: no holdout anchor id may appear anywhere in the record bytes
    for holdout_id in ("GF-01", "GF-03", "GF-11", "GF-06", "CAL-A4"):
        assert holdout_id not in canonical_json(record), holdout_id
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

    # committed copy — the immutability anchor of this record
    if COMMITTED_COPY.exists():
        if COMMITTED_COPY.read_bytes() != record_bytes:
            print(
                f"ERROR: committed copy {COMMITTED_COPY} differs from the "
                "rebuilt record — this record is immutable; record a "
                "NEW record (twist_record_v2) instead of editing",
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
