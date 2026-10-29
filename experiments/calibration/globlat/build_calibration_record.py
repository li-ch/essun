"""Build the PROPOSED global-sensitivity record for parameter class
HOP/PAIR LATENCY (Q1 calibration-ladder GLOBAL stage GLOB-LAT, the second
of the four global parameter-class stages.
prompts/p1_calibration.md).

Pure function of immutable artifacts: reads the sweep table and the store
run records produced by this stage (plus the landed W1 smoke store run as
the registry-point twin, and the GLOB-BW stage's sweep table for the
cross-stage baseline identity), recomputes every derived quantity with
exact Fractions, and writes a content-addressed record to
``results/calibration/<record_id>/record.json`` (record_id = SHA-256 of
the canonical record; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
assumption registry / calibration plan (declared with provenance), or
(b) computed from the stored sweep/run artifacts by this script
(closed-form cross-checks by exact Fraction string equality on every
executed row). NOTHING is tuned and NO anchor is compared: this is a
global sensitivity stage — it maps the model's own response surface along
the REGISTERED A-L0-LAT axis [10, 2000] ns on the W1 smoke config.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
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
# Stage artifacts (content addresses of this stage's runs/sweep; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_L10 = "e4235bd308520447c7dabbfe07c841cd333b4a0f7ef6e7dabdfea953b5e34a3b"
RUN_ID_L2000 = "8e7e3d60608f376443611809caeb9145198570f01e5c5a2db0c967f1f52e1e2e"
# The landed W1 smoke store run (EXP-VS-W1-SMOKE-001, analytical_l0 on
# ring8_free_params.yaml at the registry point L=200) — cited as the
# registry-point twin cross-check only; produced by the vertical slice,
# not by this stage.
RUN_ID_SMOKE_TWIN = "144228d060174a37a27bec733d7bb351504d61478459f4d181c0987f974b3d77"
SWEEP_ID = "d4fa28321ef14dfb0eb0dfac557726d6982f2eaa35793cd3305a4a0a36fe1ab4"
# The FIRST global stage's sweep (GLOB-BW) — cited for the cross-stage
# baseline identity only (its B=64 row IS this stage's L=200 row: the
# same smoke config point); produced by that stage, not this one.
SWEEP_ID_GLOBBW = "ec08bb06df65c2ac931ef36a514be8eac80e2ab2728e54a0a5987b7938a89452"

RESULTS = REPO_ROOT / "results"

# The W1 smoke configuration, verbatim (experiments/vertical_slice/
# w1_decode_smoke.yaml inputs): W1 Dense TP Decode, tp8, 2 layers x 3
# steps = 6 AllReduce ops, payload M = 16384 B (A-W1-SIZE smoke value),
# unidirectional ring r=8, B = 64 B/ns (A-L0-BW registry point, KEEP —
# the BW axis was the first global stage's).
R = 8
M = 16384
B = Fraction(64)
REGISTRY_L = Fraction(200)
RANGE_LOW = Fraction(10)
RANGE_HIGH = Fraction(2000)
ANCHOR_SPAN_HIGH = Fraction(800)  # plan section 2.1 A-L0-LAT anchored-axis upper
OPS = 6

# Closed-form identity of the executed backend (analytical_l0):
#   wire per rank  w = 2*(r-1)/r * M = 7*M/4 = 28672 B (independent of L)
#   t(L) = w/B + 2*(r-1)*L = 448 + 14L ns   — a straight LINE in L
WIRE = Fraction(2 * (R - 1) * M, R)          # 28672
BW_TERM = WIRE / B                           # 448 (L-independent)
CHAIN_MULT = 2 * (R - 1)                     # 14 (ns of CCT per ns of L)
BASELINE_CCT = BW_TERM + CHAIN_MULT * REGISTRY_L   # 3248
TOTAL_WIRE = OPS * 2 * (R - 1) * M           # 1376256 per-config total

# Swept L ladder (free parameters; provenance in the topology headers).
L_LADDER = [10, 16, 32, 64, 70, 80, 128, 140, 200, 256, 512, 800, 1024, 2000]
CONTEXT_POINTS = {70: "CAL-A9 CXL switch-stage floor alone (at-least wording)",
                  80: "CAL-A9 one-stage pair-across-a-switch sum "
                      "(10 link + 70 switch; plan section 2.1 stated sum)",
                  140: "CAL-A8 emulated added-latency upper point "
                       "(ASPLOS 2023 Pond 64/140 ns pair)",
                  800: "CAL-A10 assumption-class GPU-fabric end-to-end "
                       "0.8 us — the plan section 2.1 anchored-axis upper"}
COINCIDENCES = {10: "numerically CAL-A9's ~10 ns/link CXL design estimate "
                    "(the endpoint itself is registry-defined)",
                64: "numerically CAL-A8's 64 ns emulated added-latency "
                    "lower point (the grid point is powers-of-two-defined)"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ring_time(l: Fraction) -> Fraction:
    return BW_TERM + CHAIN_MULT * l


def delta_vs_registry(l: Fraction) -> Fraction:
    return (ring_time(l) - BASELINE_CCT) / BASELINE_CCT


def run_summary(run_id: str, l: Fraction, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    cct = Fraction(per_op["completion_time_ns_exact"])
    payload = per_op["payload_bytes"]
    l_run = Fraction(obs["model"]["hop_latency_ns_exact"])
    # Closed-form cross-checks (exact): identity, wire, conservation.
    assert l_run == l
    assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == B
    assert payload == M
    assert cct == ring_time(l), (run_id, cct)
    assert Fraction(per_op["per_rank_wire_bytes_exact"]) == WIRE
    assert all(Fraction(p["completion_time_ns_exact"]) == cct for p in obs["per_op"])
    cons = obs["observables"]["O-CONSERVATION"]
    assert cons["violations"] == 0
    assert Fraction(cons["total_wire_bytes_exact"]) == TOTAL_WIRE
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": obs["model"]["ranks"],
            "link_bytes_per_ns_exact": obs["model"]["link_bytes_per_ns_exact"],
            "hop_latency_ns_exact": obs["model"]["hop_latency_ns_exact"],
        },
        "payload_bytes": payload,
        "ops": len(obs["per_op"]),
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "o_conservation_violations": cons["violations"],
        "closed_form_check": "exact equality vs 448 + 14L (asserted in builder)",
    }


def sensitivity_ladder() -> tuple[dict, dict]:
    """The executed sweep rows + per-L derived facts, all cross-checked."""
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    assert table["sweep"] == "cal_globlat_v1"
    assert len(table["configs"]) == len(L_LADDER)
    rows_by_l: dict[Fraction, dict] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        l = Fraction(topo.split("_l")[1].split("_")[0])
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        # Closed-form cross-checks (exact) on EVERY executed row.
        assert cct == ring_time(l), (topo, cct)
        assert Fraction(row["per_rank_wire_bytes_exact"]) == WIRE
        assert row["o_conservation"]["violations"] == 0
        assert Fraction(row["o_conservation"]["total_wire_bytes_exact"]) == TOTAL_WIRE
        assert row["payload_bytes"] == M
        # Delta column recomputed independently.
        d = Fraction(row["delta_vs_baseline"]["delta_exact"])
        assert d == delta_vs_registry(l), (topo, d)
        # The single rational delta family (L - 200)/232 holds everywhere.
        assert d == Fraction(int(l) - 200, 232), (topo, d)
        rows_by_l[l] = row
    assert sorted(rows_by_l) == sorted(Fraction(l) for l in L_LADDER)
    assert min(rows_by_l) == RANGE_LOW and max(rows_by_l) == RANGE_HIGH

    # Balance point of the axis: latency chain == bandwidth term exactly at
    # L* = w/(B*2(r-1)) = M/(r*B) — the atlas ring-balance law
    # M* = L*B*r read on the L axis instead of the M axis. Here L* = 32
    # ns is EXACTLY ON the powers-of-two grid (no bracketing needed).
    l_star = Fraction(M, R * int(B))  # 32
    assert ring_time(l_star) == 2 * BW_TERM  # each term exactly half of t(L*)
    grid = sorted(rows_by_l)
    assert l_star in grid
    below = [l for l in grid if l < l_star]
    assert below == [Fraction(10), Fraction(16)]

    # Strict monotonicity of t along the grid (increasing — a line).
    times = [Fraction(rows_by_l[l]["o_cct"]["completion_time_ns_mean_exact"]) for l in grid]
    assert all(x < y for x, y in zip(times, times[1:]))

    ladder = []
    for l in grid:
        row = rows_by_l[l]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        lat_term = CHAIN_MULT * l
        if l == RANGE_LOW:
            role = ("registered-range lower endpoint "
                    f"({COINCIDENCES[int(l)]} — coincidence, context only)")
        elif l == RANGE_HIGH:
            role = ("registered-range upper endpoint (anchor-free above "
                    "~800-1000 ns per the plan's NARROW-range-upper "
                    "candidate — recorded as such, swept anyway)")
        elif l == REGISTRY_L:
            role = "registry point = smoke value = baseline"
        elif int(l) in CONTEXT_POINTS:
            role = f"anchor-informed axis context marker ({CONTEXT_POINTS[int(l)]})"
        elif l == l_star:
            role = ("powers-of-two ladder interior point — the BALANCE "
                    "POINT of the axis exactly (L* = M/(r*B) = 32 ns is "
                    "ON the grid)")
        elif int(l) in COINCIDENCES:
            role = ("powers-of-two ladder interior point "
                    f"({COINCIDENCES[int(l)]} — coincidence, context only)")
        else:
            role = "powers-of-two ladder interior point"
        entry = {
            "L_ns": str(l),
            "config_id": row["config_id"],
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
            "bandwidth_term_ns_exact": str(BW_TERM),
            "latency_term_ns_exact": str(lat_term),
            "latency_share_of_cct_exact": str(lat_term / cct),
            "bandwidth_share_of_cct_exact": str(BW_TERM / cct),
            "regime_vs_balance_point": (
                "bandwidth-dominated (L < L* = 32)" if l < l_star
                else "latency-dominated (L > L* = 32)"),
            "delta_vs_registry_point_exact": row["delta_vs_baseline"]["delta_exact"],
            "delta_vs_registry_point_float": row["delta_vs_baseline"]["delta_float"],
            "role": role,
        }
        ladder.append(entry)
    facts = {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "the A-L0-LAT registry point L=200 (the W1 smoke value)",
        "balance_point": {
            "L_star_exact": str(l_star),
            "L_star_float": float(l_star),
            "law": "L* = M/(r*B) — the atlas ring-balance law M* = L*B*r "
                   "(docs/atlas ladders, proportional in r) read on the L "
                   "axis at fixed M instead of the M axis at fixed B",
            "property": "t(L*) = 2 x bandwidth term exactly (each term "
                        "exactly half of CCT); L* = 32 ns is EXACTLY ON the "
                        "powers-of-two grid — the first global stage's "
                        "B* = 256/25 needed bracketing (8 < B* < 16), this "
                        "axis's balance point is a grid point",
            "registry_point_placement_exact": str(REGISTRY_L / l_star),
            "registry_point_placement_float": float(REGISTRY_L / l_star),
            "duality_with_GLOB-BW": "the registry point sits 25/4 = 6.25x "
                                    "above L* = 32 EXACTLY as it sits 25/4 "
                                    "above the B axis's B* = 256/25 — both "
                                    "placements equal B*L*r/M = 25/4 at the "
                                    "registry pair (64, 200): the two "
                                    "global axes are duals at the smoke point",
            "regime_split_of_grid": "2 of 14 grid points below L* (10, 16) "
                                    "are bandwidth-dominated; 12 of 14 above "
                                    "it (32..2000, incl. the registry point "
                                    "200 and all four anchor-informed axis "
                                    "markers 70/80/140/800) are "
                                    "latency-dominated",
        },
        "delta_family": {
            "form": "delta(L) = (L - 200)/232 exactly, for every swept L",
            "properties": "zero exactly at the registry point; sign change "
                          "exactly there; at the powers of two the column "
                          "reads -23/29, -21/29, -17/29, -9/29, 0, 7/29, "
                          "39/29, 103/29; the registered endpoints read "
                          "-95/116 (L=10) and 225/29 (L=2000)",
        },
    }
    return {"sensitivity_ladder_L_10_to_2000": ladder, "sweep_facts": facts}, rows_by_l


def main() -> int:
    ladder_block, rows_by_l = sensitivity_ladder()

    # Endpoint store runs + the registry twin cross-check.
    l10 = run_summary(RUN_ID_L10, Fraction(10),
                      "registered-range LOWER endpoint L=10 (store run)")
    l2000 = run_summary(RUN_ID_L2000, Fraction(2000),
                        "registered-range UPPER endpoint L=2000 (store run)")
    twin = run_summary(RUN_ID_SMOKE_TWIN, REGISTRY_L,
                       "registry point L=200 — the LANDED W1 smoke store run "
                       "(EXP-VS-W1-SMOKE-001), cited as twin cross-check")
    # Cross-artifact determinism tie-in: the sweep's L=200 row IS the landed
    # smoke run's CCT, digit for digit — and both endpoint runs equal their
    # sweep rows. Five independent artifacts, one identity, zero drift.
    assert twin["cct_ns_exact"] == rows_by_l[REGISTRY_L][
        "o_cct"]["completion_time_ns_mean_exact"]
    assert twin["per_rank_wire_bytes_exact"] == rows_by_l[REGISTRY_L][
        "per_rank_wire_bytes_exact"]
    # And the endpoint runs agree with their sweep rows.
    assert l10["cct_ns_exact"] == rows_by_l[Fraction(10)][
        "o_cct"]["completion_time_ns_mean_exact"]
    assert l2000["cct_ns_exact"] == rows_by_l[Fraction(2000)][
        "o_cct"]["completion_time_ns_mean_exact"]
    # Cross-stage identity: the FIRST global stage's sweep (GLOB-BW) shares
    # this registry point — its B=64 row IS this sweep's L=200 row.
    globbw = load_json(RESULTS / "sweeps" / SWEEP_ID_GLOBBW / "table.json")
    globbw_b64 = [r for r in globbw["configs"]
                  if "ring8_globbw_b64_v1" in r["config_id"]]
    assert len(globbw_b64) == 1
    assert Fraction(globbw_b64[0]["o_cct"]["completion_time_ns_mean_exact"]) == \
        Fraction(rows_by_l[REGISTRY_L]["o_cct"]["completion_time_ns_mean_exact"])
    assert globbw_b64[0]["per_rank_wire_bytes_exact"] == \
        rows_by_l[REGISTRY_L]["per_rank_wire_bytes_exact"]
    assert globbw_b64[0]["o_conservation"]["violations"] == 0

    # Linear growth, floors and asymmetry (exact).
    t_low, t_high, t_reg = ring_time(10), ring_time(2000), BASELINE_CCT
    assert t_low == 588 and t_high == 28448 and t_reg == 3248
    assert t_low == BW_TERM * Fraction(21, 16)          # floor + 5/16 exactly
    assert t_high == BW_TERM * Fraction(127, 2)         # floor x 63.5 exactly
    assert BW_TERM / t_reg - 1 == Fraction(-25, 29)     # asymptotic max gain
    doubling_costs = []
    for l in (16, 32, 64, 128, 256, 512):
        cost = ring_time(Fraction(2 * l)) - ring_time(Fraction(l))
        assert cost == CHAIN_MULT * Fraction(l)
        doubling_costs.append({
            "L_to_2L": f"{l}->{2*l}",
            "cct_cost_ns_exact": str(cost),
        })
    globbw_range_ratio = Fraction(31472, 2828)  # t(1)/t(1024) of stage GLOB-BW
    asym = {
        "axis_shape": "t(L) = 448 + 14L ns — a STRAIGHT LINE with slope "
                      "2(r-1) = 14: no saturation anywhere on the axis "
                      "(the exact mirror of the first global stage's "
                      "floor-saturating hyperbola 28672/B + 2800)",
        "slope_meaning": "every +1 ns of L costs exactly +14 ns of "
                         "smoke-config CCT — the chain multiplicity charged "
                         "per hop pair (2(r-1) = 14) is the whole slope",
        "bandwidth_floor_ns_exact": str(BW_TERM),
        "bandwidth_floor_meaning": "2(r-1)/r*M/B = 448 ns — the "
                                   "L-independent term the identity "
                                   "collapses onto as L -> 0 (outside the "
                                   "registered range; the range's lower "
                                   "endpoint 10 sits +5/16 = +31.25% above "
                                   "it exactly)",
        "lower_endpoint_cct_ns_exact": str(t_low),
        "upper_endpoint_cct_ns_exact": str(t_high),
        "upper_endpoint_vs_floor_exact": "127/2 (the upper endpoint of the "
                                         "registered range carries the "
                                         "bandwidth floor 63.5x)",
        "max_gain_from_L_to_zero_exact": "-25/29",
        "max_gain_from_L_to_zero_float": float(Fraction(-25, 29)),
        "max_gain_meaning": "no L — not the registered lower endpoint 10, "
                            "not 0, not -infinity — can reduce smoke-config "
                            "CCT by more than 25/29 = 86.21% (= the registry "
                            "point's own latency share, 2800/3248); the "
                            "mirror of GLOB-BW's -4/29 bandwidth-side cap",
        "lower_endpoint_delta_exact": str(delta_vs_registry(Fraction(10))),
        "lower_endpoint_delta_float": float(delta_vs_registry(Fraction(10))),
        "upper_endpoint_delta_exact": str(delta_vs_registry(Fraction(2000))),
        "upper_endpoint_delta_float": float(delta_vs_registry(Fraction(2000))),
        "full_range_cct_ratio_exact": str(t_high / t_low),
        "full_range_cct_ratio_float": float(t_high / t_low),
        "full_range_vs_GLOB-BW_ratio_exact": str((t_high / t_low) / globbw_range_ratio),
        "full_range_vs_GLOB-BW_ratio_float": float((t_high / t_low) / globbw_range_ratio),
        "full_range_meaning": "the registered L range spans a 1016/21 ~ "
                              "48.38x output ratio — ~4.35x wider than the "
                              "B axis's 1124/101 ~ 11.13x (GLOB-BW): at the "
                              "smoke payload the model feels the latency "
                              "axis far more than the bandwidth axis",
        "asymmetry_exact": str(
            delta_vs_registry(Fraction(2000)) / delta_vs_registry(Fraction(10))),
        "asymmetry_float": float(
            delta_vs_registry(Fraction(2000)) / delta_vs_registry(Fraction(10))),
        "asymmetry_meaning": "the registered axis is 180/19 ~ 9.47x more "
                             "sensitive ABOVE the registry point (+775.86% "
                             "at L=2000) than below it (-81.90% at L=10) — "
                             "the exact mirror of GLOB-BW (336/5 = 67.2x "
                             "more sensitive BELOW): the L axis is unbounded "
                             "above, the B axis was floored",
        "doubling_costs_ns": doubling_costs,
        "doubling_law": "t(2L) - t(L) = 14L exactly — each doubling of L "
                        "costs exactly the new latency chain; costs GROW "
                        "linearly with L (224 ns at 16->32, 7168 ns at "
                        "512->1024), where the B axis's doubling gains "
                        "halved",
    }

    # Anchor-informed axis context (plan section 2.1 A-L0-LAT anchored
    # axis ~10-800 ns + NARROW-range-upper candidate, owner-pending; NO
    # value changed by this stage).
    span = {
        "candidate_anchored_axis_ns": ["10", "800"],
        "provenance": "CALIBRATION_PLAN.md section 2.1 row A-L0-LAT: KEEP "
                      "(point) — '200 ns lies inside the anchored axis span "
                      "(~10-800 ns)'; NARROW (range upper) — 'no anchor "
                      "supports >= ~1 us; upper bound 2000 ns is "
                      "anchor-free (candidate ~ <= 800-1000 ns)'. This "
                      "stage quantifies what adopting the anchored axis "
                      "upper would mean at the smoke point; it changes "
                      "nothing.",
        "upper_excursion_at_800_exact": str(delta_vs_registry(ANCHOR_SPAN_HIGH)),
        "upper_excursion_at_800_float": float(delta_vs_registry(ANCHOR_SPAN_HIGH)),
        "upper_excursion_at_registered_2000_exact": str(delta_vs_registry(Fraction(2000))),
        "upper_excursion_at_registered_2000_float": float(
            delta_vs_registry(Fraction(2000))),
        "registered_vs_anchored_upper_ratio_exact": str(
            delta_vs_registry(Fraction(2000)) / delta_vs_registry(ANCHOR_SPAN_HIGH)),
        "registered_vs_anchored_upper_ratio_float": float(
            delta_vs_registry(Fraction(2000)) / delta_vs_registry(ANCHOR_SPAN_HIGH)),
        "movement_inside_anchored_axis_meaning": "trading the anchor-free "
                                                 "registered upper 2000 for "
                                                 "the anchored-axis upper 800 "
                                                 "caps the upper excursion at "
                                                 "+75/29 = +258.62% — exactly "
                                                 "3x tighter than the "
                                                 "registered +225/29 = "
                                                 "+775.86%; the anchored "
                                                 "axis's lower end (CAL-A9's "
                                                 "~10 ns/link) coincides "
                                                 "numerically with the "
                                                 "registered lower endpoint",
        "registry_point_inside_anchored_axis": "the registry point 200 is "
                                               "interior to the anchored "
                                               "axis at exactly 1/4 of its "
                                               "upper end (200/800) and "
                                               "25/4 above the balance point "
                                               "L* = 32 — the KEEP (point) "
                                               "verdict's arithmetic",
    }

    # Local elasticity at the registry point (the 'sensitivity' question).
    lat_share_reg = (CHAIN_MULT * REGISTRY_L) / BASELINE_CCT
    assert lat_share_reg == Fraction(25, 29)
    elasticity = {
        "definition": "elasticity = |(dt/dL)*(L/t)| = latency share of CCT "
                      "(exact for the line t = 14L + c)",
        "at_registry_point_200_exact": str(lat_share_reg),
        "at_registry_point_200_float": float(lat_share_reg),
        "meaning": "a +1% L at the registry point raises smoke-config CCT "
                   "by +0.862%: the registry's declared 'sensitivity: high "
                   "for O-CCT at small messages' (A-L0-LAT) MATERIALIZES at "
                   "the smoke point itself — the exact mirror of GLOB-BW, "
                   "where the B axis's declared high sensitivity was "
                   "locally nearly inert (bandwidth share 4/29 ~ 13.8%)",
        "complementarity_with_GLOB-BW": "the two global stages' "
                                        "registry-point elasticities sum to "
                                        "exactly 1 (4/29 + 25/29 = 29/29): "
                                        "the bandwidth share and the latency "
                                        "share partition the smoke CCT, so "
                                        "the two axes' local sensitivities "
                                        "are complementary halves of the "
                                        "same 3248 ns",
        "share_crosses_half_at": "L* = 32 exactly (the balance point)",
        "at_lower_endpoint_10_exact": str((CHAIN_MULT * 10) / ring_time(10)),
        "at_lower_endpoint_10_float": float((CHAIN_MULT * 10) / ring_time(10)),
        "at_upper_endpoint_2000_exact": str(
            (CHAIN_MULT * 2000) / ring_time(2000)),
        "at_upper_endpoint_2000_float": float(
            (CHAIN_MULT * 2000) / ring_time(2000)),
    }

    # O-CONSERVATION invariance (structurally blind to L, as declared).
    conservation = {
        "per_rank_wire_bytes_exact": str(WIRE),
        "total_wire_bytes_exact": str(TOTAL_WIRE),
        "statement": "wire bytes are EXACTLY L-invariant (2(r-1)/r*M depends "
                     "only on r and M): all 14 sweep rows and all 3 store "
                     "runs emit the identical per-rank total 28672 B and "
                     "per-config total 1376256 B with 0 violations — "
                     "O-CONSERVATION is algebraically blind to the "
                     "hop-latency axis, matching the registry's declared "
                     "'sensitivity: zero for O-CONSERVATION' (A-L0-LAT)",
        "o_cct_collapse": "with wire fixed, the WHOLE effect of L on the "
                          "model is the single additive term 14L — the "
                          "sensitivity map is the line segment [140, 28000] "
                          "ns added to the constant 448 ns",
    }

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, GLOBAL stage GLOB-LAT (parameter "
                 "class: hop/pair latency; the second of the four global "
                 "parameter-class sensitivity stages)",
        "parameter_class": {
            "class": "hop/pair latency",
            "parameter": "link.hop_latency_ns",
            "registry_ids": {
                "A-L0-LAT": "the executed axis — the W1 smoke config's ring "
                            "fabric (analytical_l0)",
                "A-L0T-LAT": "the 2D-torus twin (link.hop_latency_ns, same "
                             "declared value 200 and range [10, 2000], "
                             "values deliberately shared across fabrics) — "
                             "NOT part of the W1 smoke config, not swept in "
                             "this stage",
                "A-L0X-LAT": "the crossbar pair-latency twin "
                             "(link.pair_latency_ns, same declared value "
                             "200 and range [10, 2000]) — different fabric, "
                             "not in the smoke config, not swept here",
                "A-L0D-LAT": "the recursive-doubling pair-latency twin "
                             "(link.pair_latency_ns, same declared value "
                             "200 and range [10, 2000]) — different fabric, "
                             "not in the smoke config, not swept here",
            },
            "registered_range_ns": ["10", "2000"],
            "registry_point": "200",
            "registry_point_role_in_this_stage": "the W1 smoke config's own "
                                                 "shipped value — the sweep "
                                                 "baseline every delta reads "
                                                 "against",
            "plan_verdict_context": "CALIBRATION_PLAN.md section 2.1 A-L0-LAT: "
                                    "KEEP (point) / NARROW (range upper) — "
                                    "anchored axis ~10-800 ns, anchor-free "
                                    "above ~1 us; this stage executes the "
                                    "REGISTERED range and quantifies the "
                                    "difference, changing no value",
        },
        "target": {
            "role": "global sensitivity — WHERE the model's own O-CCT output "
                    "sits across the parameter's registered range on the W1 "
                    "smoke config; never a comparison to an external "
                    "measurement, never a tuning step",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "no anchor is involved: this is "
                                             "the model's response surface "
                                             "(E0 arithmetic facts of the "
                                             "identity); the smoke payload "
                                             "regime (16 KiB) is itself "
                                             "anchor-free (plan section 4.3 "
                                             "small-message gap — the "
                                             "weakest axis of the whole "
                                             "plan per section 4.2), so no "
                                             "external target exists to "
                                             "calibrate against there",
            "observables": ["O-CCT", "O-CONSERVATION"],
            "regime": {
                "workload": "W1 Dense TP Decode smoke configuration, verbatim "
                            "(experiments/workloads/"
                            "w1_dense_tp_decode_small.yaml: tp8, 2 layers x 3 "
                            "steps = 6 AllReduce ops, M = 16384 B = the "
                            "A-W1-SIZE smoke value)",
                "topology_class": "unidirectional_ring (the smoke fabric "
                                  "ring8_free_v1's class), r = 8",
                "B_ns": "64 B/ns (A-L0-BW registry point, KEEP; the link-BW "
                        "axis was the first global stage's)",
                "backend": "analytical_l0",
            },
        },
        "model": {
            "backend_ids": ["analytical_l0"],
            "identity": "t(L) = 2(r-1)/r*M/B + 2(r-1)L = 448 + 14L ns; "
                        "per-rank wire 2(r-1)/r*M = 28672 B (L-independent)",
            "ranks": 8,
            "payload_bytes": M,
            "ops_per_config": OPS,
            "free_parameters": {
                "L_swept_ns": {
                    str(l): rows_by_l[Fraction(l)]["config_id"].split("-")[2]
                    for l in L_LADDER
                },
                "L_ladder_design": "the registered ENDPOINTS 10 and 2000 "
                                   "(each backed by its own append-only "
                                   "store run) + the powers of two inside "
                                   "the range (16, 32, 64, 128, 256, 512, "
                                   "1024; 200 = the registry point = the "
                                   "smoke value = the delta baseline, 32 = "
                                   "the balance point exactly) + the four "
                                   "anchor-informed axis CONTEXT markers "
                                   "70/80/140/800 (plan section 2.1 A-L0-LAT "
                                   "anchored axis ~10-800 ns: CAL-A9 "
                                   "switch-stage floor / CAL-A9 one-stage "
                                   "pair sum / CAL-A8 emulated upper / "
                                   "CAL-A10 assumption-class GPU end-to-end; "
                                   "context only — the anchor comparisons "
                                   "themselves were the per-anchor stages' "
                                   "job). Numerical coincidences noted, not "
                                   "markers: 10 = CAL-A9's ~10 ns/link, 64 = "
                                   "CAL-A8's emulated lower",
                "B_ns": 64,
                "B_provenance": "A-L0-BW registry point (KEEP per plan "
                                "section 2.1); the link-BW axis was the "
                                "first global stage GLOB-BW's own axis",
            },
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV from "
                           "experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "sensitivity_sweep": ladder_block["sensitivity_ladder_L_10_to_2000"],
            "sweep_facts": ladder_block["sweep_facts"],
            "endpoint_and_twin_runs": {
                "lower_endpoint": l10,
                "upper_endpoint": l2000,
                "registry_twin": twin,
                "twin_check": "the sweep's L=200 baseline row equals the landed "
                              "W1 smoke store run's CCT/wire/totals digit for "
                              "digit (3248 ns), and BOTH endpoint runs equal "
                              "their sweep rows — and the FIRST global "
                              "stage's GLOB-BW sweep row at B=64 equals this "
                              "stage's L=200 row (the same smoke config "
                              "point executed independently three times, "
                              "zero drift): five independent artifacts, one "
                              "identity",
            },
            "linear_growth_and_floors": asym,
            "anchor_informed_axis_context": span,
            "elasticity": elasticity,
            "conservation_invariance": conservation,
        },
        "deviation": {
            "vs_anchor": "UNDEFINED BY CONSTRUCTION — no anchor and no "
                         "external measurement enters a global sensitivity "
                         "stage; the recorded deviations are the sweep's own "
                         "deltas vs the registry point L=200 (the W1 smoke "
                         "value), i.e. placement of the model's output across "
                         "its registered parameter range, never agreement "
                         "with any measurement",
            "summary": "smoke-config O-CCT spans 588 ns (L=10) to 28448 ns "
                       "(L=2000) across the registered range — -81.90% below "
                       "and +775.86% above the registry point's 3248 ns; the "
                       "axis is the straight line t = 448 + 14L (slope 14, no "
                       "saturation) with the balance point L* = M/(r*B) = 32 "
                       "ns EXACTLY ON the grid splitting it into a "
                       "bandwidth-dominated 2-of-14 minority and a "
                       "latency-dominated remainder that includes the "
                       "registry point (25/4 above L*, the same exact ratio "
                       "as the B axis's placement — the axes are duals), all "
                       "four anchor-informed markers and an anchor-free upper "
                       "endpoint; O-CONSERVATION is L-blind (0 violations, "
                       "identical wire at all 14 points)",
        },
        "evidence_levels": {
            "runs_and_sweep": "E0 (analytical executions; deterministic, "
                              "content-addressed, replay-verified "
                              "byte-identical)",
            "candidate": "PROPOSED global sensitivity candidate; no E3/E4 "
                         "language — no external target exists or is claimed",
        },
        "backing": {
            "run_ids": [RUN_ID_L10, RUN_ID_L2000, RUN_ID_SMOKE_TWIN],
            "run_roles": {
                RUN_ID_L10: "registered-range lower endpoint (this stage)",
                RUN_ID_L2000: "registered-range upper endpoint (this stage)",
                RUN_ID_SMOKE_TWIN: "landed W1 smoke run at the registry point "
                                   "(vertical slice, cited as twin "
                                   "cross-check)",
            },
            "sweep_ids": [SWEEP_ID],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID}"],
            "cross_stage_check": f"the GLOB-BW stage's sweep {SWEEP_ID_GLOBBW} "
                                 "is read (read-only) for the baseline "
                                 "identity cross-check only",
            "backed_numbers": "every model output in comparison."
                              "sensitivity_sweep and comparison."
                              "endpoint_and_twin_runs is backed by the sweep "
                              "id and run ids above (closed-form cross-checked "
                              "by exact Fraction string equality on every row "
                              "and run, asserted in the builder); every "
                              "derived fraction (delta family, balance point, "
                              "shares, elasticity, anchored-axis movement) is "
                              "recomputed from those artifacts by the builder, "
                              "never transcribed",
            "inputs": [
                "experiments/calibration/globlat/sweep_globlat_v1.yaml",
                "experiments/calibration/globlat/run_globlat_l10_v1.yaml",
                "experiments/calibration/globlat/run_globlat_l2000_v1.yaml",
                "experiments/calibration/globlat/topologies/ (14 files)",
                "experiments/calibration/globlat/profiles/implementation_profile_l0_ring_cal_globlat_v1.yaml",
                "experiments/workloads/w1_dense_tp_decode_small.yaml (the W1 smoke workload, referenced unmodified)",
                "experiments/vertical_slice/assumptions_l0.yaml (referenced unmodified)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/globlat/sweep_globlat_v1.yaml ; "
                         "make run EXP=experiments/calibration/globlat/run_globlat_l10_v1.yaml ; "
                         "make run EXP=experiments/calibration/globlat/run_globlat_l2000_v1.yaml ; "
                         "python experiments/calibration/globlat/build_calibration_record.py",
        },
    }

    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    record_id = hashlib.sha256(record_bytes).hexdigest()
    out_dir = RESULTS / "calibration" / record_id
    if out_dir.exists():
        stored = (out_dir / "record.json").read_bytes()
        if stored != record_bytes:
            print(f"ERROR: record {record_id} exists with different bytes", file=sys.stderr)
            return 1
        print(f"idempotent: record {record_id} already stored byte-identically")
        return 0
    out_dir.mkdir(parents=True)
    (out_dir / "record.json").write_bytes(record_bytes)
    print(f"record_id: {record_id}")
    print(f"path: {out_dir / 'record.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
