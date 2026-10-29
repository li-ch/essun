"""Build the PROPOSED global-sensitivity record for parameter class LINK
BANDWIDTH (Q1 calibration-ladder GLOBAL stage GLOB-BW, the first of the
four global parameter-class stages;
p1_calibration.md).

Pure function of immutable artifacts: reads the sweep table and the store
run records produced by this stage (plus the landed W1 smoke store run as
the registry-point twin), recomputes every derived quantity with exact
Fractions, and writes a content-addressed record to
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
the REGISTERED A-L0-BW axis [1, 1024] B/ns on the W1 smoke config.

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
RUN_ID_B1 = "5b9725559518f50048a4d7fc903291ca8ce92f1ec06a4468af2a1159a31bb3ba"
RUN_ID_B1024 = "e829d679f50fad54e3b9649d0746271f393532b8899b8e23f9dd068ea5d74ffe"
# The landed W1 smoke store run (EXP-VS-W1-SMOKE-001, analytical_l0 on
# ring8_free_params.yaml at the registry point B=64) — cited as the
# registry-point twin cross-check only; produced by the vertical slice,
# not by this stage.
RUN_ID_SMOKE_TWIN = "144228d060174a37a27bec733d7bb351504d61478459f4d181c0987f974b3d77"
SWEEP_ID = "ec08bb06df65c2ac931ef36a514be8eac80e2ab2728e54a0a5987b7938a89452"

RESULTS = REPO_ROOT / "results"

# The W1 smoke configuration, verbatim (experiments/vertical_slice/
# w1_decode_smoke.yaml inputs): W1 Dense TP Decode, tp8, 2 layers x 3
# steps = 6 AllReduce ops, payload M = 16384 B (A-W1-SIZE smoke value),
# unidirectional ring r=8, L = 200 ns (A-L0-LAT registry point, KEEP).
R = 8
M = 16384
L = Fraction(200)
REGISTRY_B = Fraction(64)
RANGE_LOW = Fraction(1)
RANGE_HIGH = Fraction(1024)
SPAN_LOW = Fraction(20)   # plan section 2.1 A-L0-BW NARROW candidate span
OPS = 6

# Closed-form identity of the executed backend (analytical_l0):
#   wire per rank  w = 2*(r-1)/r * M = 7*M/4 = 28672 B (independent of B)
#   t(B) = w/B + 2*(r-1)*L = 28672/B + 2800 ns
WIRE = Fraction(2 * (R - 1) * M, R)          # 28672
LAT_CHAIN = 2 * (R - 1) * L                  # 2800 (14L)
BASELINE_CCT = WIRE / REGISTRY_B + LAT_CHAIN # 3248
TOTAL_WIRE = OPS * 2 * (R - 1) * M           # 1376256 per-config O-CONSERVATION total

# Swept B ladder (free parameters; provenance in the topology headers).
B_LADDER = [1, 2, 4, 8, 16, 20, 25, 32, 50, 64, 128, 256, 512, 1024]
CONTEXT_POINTS = {20: "CAL-A12 NCCL per-link model (span lower endpoint)",
                  25: "CAL-A12 physical NVLink-3 per-link rate",
                  50: "CAL-A1/A2 NVLink5 per-port per-direction"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ring_time(b: Fraction) -> Fraction:
    return WIRE / b + LAT_CHAIN


def delta_vs_registry(b: Fraction) -> Fraction:
    return (ring_time(b) - BASELINE_CCT) / BASELINE_CCT


def run_summary(run_id: str, b: Fraction, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    cct = Fraction(per_op["completion_time_ns_exact"])
    payload = per_op["payload_bytes"]
    b_run = Fraction(obs["model"]["link_bytes_per_ns_exact"])
    # Closed-form cross-checks (exact): identity, wire, conservation.
    assert b_run == b
    assert payload == M
    assert cct == ring_time(b), (run_id, cct)
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
        "closed_form_check": "exact equality vs 28672/B + 2800 (asserted in builder)",
    }


def sensitivity_ladder() -> tuple[dict, dict]:
    """The executed sweep rows + per-B derived facts, all cross-checked."""
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    assert table["sweep"] == "cal_globbw_v1"
    assert len(table["configs"]) == len(B_LADDER)
    rows_by_b: dict[Fraction, dict] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        b = Fraction(topo.split("_b")[1].split("_")[0])
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        # Closed-form cross-checks (exact) on EVERY executed row.
        assert cct == ring_time(b), (topo, cct)
        assert Fraction(row["per_rank_wire_bytes_exact"]) == WIRE
        assert row["o_conservation"]["violations"] == 0
        assert Fraction(row["o_conservation"]["total_wire_bytes_exact"]) == TOTAL_WIRE
        assert row["payload_bytes"] == M
        # Delta column recomputed independently.
        d = Fraction(row["delta_vs_baseline"]["delta_exact"])
        assert d == delta_vs_registry(b), (topo, d)
        # The single rational delta family 4*(64/B - 1)/29 holds everywhere.
        assert d == Fraction(4) * (REGISTRY_B / b - 1) / Fraction(29)
        rows_by_b[b] = row
    assert sorted(rows_by_b) == sorted(Fraction(b) for b in B_LADDER)
    assert min(rows_by_b) == RANGE_LOW and max(rows_by_b) == RANGE_HIGH

    # Balance point of the axis: bandwidth term == latency term exactly at
    # B* = w / (2(r-1)L) = M/(r*L) — the atlas ring-balance law M* = L*B*r
    # read on the B axis instead of the M axis.
    b_star = Fraction(M, R * int(L))  # 256/25 = 10.24
    assert ring_time(b_star) == 2 * LAT_CHAIN  # each term exactly half of t(B*)
    grid = sorted(rows_by_b)
    below = [b for b in grid if b < b_star]
    assert below[-1] == 8 and grid[grid.index(8) + 1] == 16  # bracketed

    # Strict monotonicity of t along the grid.
    times = [Fraction(rows_by_b[b]["o_cct"]["completion_time_ns_mean_exact"]) for b in grid]
    assert all(x > y for x, y in zip(times, times[1:]))

    ladder = []
    for b in grid:
        row = rows_by_b[b]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        bw_term = WIRE / b
        entry = {
            "B_bytes_per_ns": str(b),
            "config_id": row["config_id"],
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
            "bandwidth_term_ns_exact": str(bw_term),
            "latency_term_ns_exact": str(LAT_CHAIN),
            "latency_share_of_cct_exact": str(LAT_CHAIN / cct),
            "bandwidth_share_of_cct_exact": str(bw_term / cct),
            "regime_vs_balance_point": (
                "bandwidth-dominated (B < B* = 256/25)" if b < b_star
                else "latency-dominated (B > B* = 256/25)"),
            "delta_vs_registry_point_exact": row["delta_vs_baseline"]["delta_exact"],
            "delta_vs_registry_point_float": row["delta_vs_baseline"]["delta_float"],
            "role": (
                "registered-range lower endpoint" if b == 1
                else "registered-range upper endpoint" if b == 1024
                else "registry point = smoke value = baseline" if b == 64
                else f"anchor-informed span context marker ({CONTEXT_POINTS[int(b)]})"
                if int(b) in CONTEXT_POINTS
                else "powers-of-two ladder interior point"),
        }
        ladder.append(entry)
    facts = {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "the A-L0-BW registry point B=64 (the W1 smoke value)",
        "balance_point": {
            "B_star_exact": str(b_star),
            "B_star_float": float(b_star),
            "law": "B* = M/(r*L) — the atlas ring-balance law M* = L*B*r "
                   "(docs/atlas ladders, proportional in r) read on the B axis "
                   "at fixed M instead of the M axis at fixed B",
            "property": "t(B*) = 2 x latency chain exactly (each term exactly "
                        "half of CCT); bracketed by grid points 8 < 256/25 < 16",
            "registry_point_placement_exact": str(REGISTRY_B / b_star),
            "registry_point_placement_float": float(REGISTRY_B / b_star),
            "regime_split_of_grid": "4 of 14 grid points below B* (1, 2, 4, 8) "
                                    "are bandwidth-dominated; 10 of 14 above it "
                                    "(16..1024, incl. the registry point 64 and "
                                    "all three anchor-informed span markers "
                                    "20/25/50) are latency-dominated",
        },
        "delta_family": {
            "form": "delta(B) = 4*(64/B - 1)/29 exactly, for every swept B",
            "properties": "zero exactly at the registry point; sign change "
                          "exactly there; at the powers of two the column reads "
                          "252/29, 124/29, 60/29, 28/29, 12/29, 4/29, 0, "
                          "-2/29, -3/29, -7/58, -15/116",
        },
    }
    return {"sensitivity_ladder_B_1_to_1024": ladder, "sweep_facts": facts}, rows_by_b


def main() -> int:
    ladder_block, rows_by_b = sensitivity_ladder()

    # Endpoint store runs + the registry twin cross-check.
    b1 = run_summary(RUN_ID_B1, Fraction(1),
                     "registered-range LOWER endpoint B=1 (store run)")
    b1024 = run_summary(RUN_ID_B1024, Fraction(1024),
                        "registered-range UPPER endpoint B=1024 (store run)")
    twin = run_summary(RUN_ID_SMOKE_TWIN, REGISTRY_B,
                       "registry point B=64 — the LANDED W1 smoke store run "
                       "(EXP-VS-W1-SMOKE-001), cited as twin cross-check")
    # Cross-artifact determinism tie-in: the sweep's B=64 row IS the landed
    # smoke run's CCT, digit for digit — and both endpoint runs equal their
    # sweep rows. Four independent artifacts, one identity, zero drift.
    assert twin["cct_ns_exact"] == rows_by_b[REGISTRY_B][
        "o_cct"]["completion_time_ns_mean_exact"]
    assert twin["per_rank_wire_bytes_exact"] == rows_by_b[REGISTRY_B][
        "per_rank_wire_bytes_exact"]
    # And the endpoint runs agree with their sweep rows.
    assert b1["cct_ns_exact"] == rows_by_b[Fraction(1)][
        "o_cct"]["completion_time_ns_mean_exact"]
    assert b1024["cct_ns_exact"] == rows_by_b[Fraction(1024)][
        "o_cct"]["completion_time_ns_mean_exact"]

    # Asymptotics and gains (exact).
    t_low, t_high, t_reg = ring_time(1), ring_time(1024), BASELINE_CCT
    assert t_low == 31472 and t_high == 2828 and t_reg == 3248
    max_gain = delta_vs_registry(Fraction(10**9))  # B -> +inf limit sample
    assert LAT_CHAIN / t_reg - 1 == Fraction(-4, 29)  # asymptotic max gain
    assert t_high == LAT_CHAIN * Fraction(101, 100)   # upper endpoint = floor + 1%
    doubling_gains = []
    for b in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
        gain = ring_time(Fraction(b)) - ring_time(Fraction(2 * b))
        assert gain == WIRE / Fraction(2 * b)
        doubling_gains.append({
            "B_to_2B": f"{b}->{2*b}",
            "cct_gain_ns_exact": str(gain),
        })
    asym = {
        "latency_floor_ns_exact": str(LAT_CHAIN),
        "latency_floor_meaning": "2(r-1)L = 14L = 2800 ns — the B-independent "
                                 "chain the identity collapses onto as B grows",
        "upper_endpoint_cct_ns_exact": str(t_high),
        "upper_endpoint_vs_floor_exact": "101/100 (the upper endpoint of the "
                                         "registered range sits exactly 1% "
                                         "above the latency floor)",
        "max_gain_from_infinite_B_exact": "-4/29",
        "max_gain_from_infinite_B_float": float(Fraction(-4, 29)),
        "max_gain_meaning": "no B above the registry point — not 1024, not "
                            "+infinity — can reduce smoke-config CCT by more "
                            "than 4/29 = 13.79% (= the registry point's own "
                            "bandwidth share, 448/3248 = 28/203 = 4/29); the "
                            "whole upper half-axis is capped by the floor",
        "lower_endpoint_delta_exact": str(delta_vs_registry(Fraction(1))),
        "lower_endpoint_delta_float": float(delta_vs_registry(Fraction(1))),
        "full_range_cct_ratio_exact": str(t_low / t_high),
        "full_range_cct_ratio_float": float(t_low / t_high),
        "asymmetry_exact": str(
            delta_vs_registry(Fraction(1)) / delta_vs_registry(Fraction(1024))),
        "asymmetry_float": float(
            delta_vs_registry(Fraction(1)) / delta_vs_registry(Fraction(1024))),
        "asymmetry_meaning": "the registered axis is 67.2x more sensitive "
                             "below the registry point (+869.0% at B=1) than "
                             "above it (-12.93% at B=1024); the sensitivity "
                             "mass of the whole range sits under the registry "
                             "point, on the 4 grid points below B*",
        "doubling_gains_ns": doubling_gains,
        "doubling_law": "t(B) - t(2B) = 28672/(2B) exactly — each doubling "
                        "buys exactly the new bandwidth term; gains halve "
                        "with every doubling (448 ns at 32->64, 28 ns at "
                        "512->1024)",
    }

    # Anchor-informed span context (plan section 2.1 A-L0-BW NARROW
    # candidate, owner-pending; NO value changed by this stage).
    span = {
        "candidate_span_bytes_per_ns": ["20", "64"],
        "provenance": "CALIBRATION_PLAN.md section 2.1 row A-L0-BW: NARROW "
                      "(range) verdict — 'no anchor supports registry "
                      "extremes [1,1024]; candidate anchor-informed span ~ "
                      "[20, 64] B/ns per link per direction pending owner "
                      "acceptance'. This stage quantifies what adopting it "
                      "would mean at the smoke point; it changes nothing.",
        "movement_inside_span_exact": str(delta_vs_registry(SPAN_LOW)),
        "movement_inside_span_float": float(delta_vs_registry(SPAN_LOW)),
        "movement_inside_span_meaning": "the whole candidate span moves "
                                        "smoke-config CCT by at most +30.34% "
                                        "(44/145, at its lower endpoint 20) "
                                        "below the registry point and 0 above "
                                        "it — versus +869.0% at the registered "
                                        "lower endpoint 1",
        "registered_vs_span_lower_ratio_exact": str(
            delta_vs_registry(Fraction(1)) / delta_vs_registry(SPAN_LOW)),
        "registered_vs_span_lower_ratio_float": float(
            delta_vs_registry(Fraction(1)) / delta_vs_registry(SPAN_LOW)),
        "span_vs_balance_point": "the candidate span lies ENTIRELY on the "
                                 "latency-dominated side (20 > B* = 10.24): "
                                 "every anchor-informed B is a latency-term-"
                                 "dominated point at the smoke payload",
    }

    # Local elasticity at the registry point (the 'sensitivity' question).
    bw_share_reg = (WIRE / REGISTRY_B) / BASELINE_CCT
    assert bw_share_reg == Fraction(28, 203) == Fraction(4, 29)
    elasticity = {
        "definition": "elasticity = |(dt/dB)*(B/t)| = bandwidth share of CCT "
                      "(exact for the hyperbola t = w/B + c)",
        "at_registry_point_64_exact": str(bw_share_reg),
        "at_registry_point_64_float": float(bw_share_reg),
        "meaning": "a +1% B at the registry point lowers smoke-config CCT by "
                   "only 0.138%; the registry's declared 'sensitivity: high "
                   "for O-CCT' (A-L0-BW) materializes only on the bandwidth-"
                   "dominated side below B* = 10.24, where the share exceeds "
                   "1/2 (at B=1 it is 28672/31472 = 91.1%)",
        "share_crosses_half_at": "B* = 256/25 exactly (the balance point)",
        "at_lower_endpoint_1_exact": str((WIRE / 1) / ring_time(1)),
        "at_lower_endpoint_1_float": float((WIRE / 1) / ring_time(1)),
    }

    # O-CONSERVATION invariance (structurally blind to B, as declared).
    conservation = {
        "per_rank_wire_bytes_exact": str(WIRE),
        "total_wire_bytes_exact": str(TOTAL_WIRE),
        "statement": "wire bytes are EXACTLY B-invariant (2(r-1)/r*M depends "
                     "only on r and M): all 14 sweep rows and all 3 store "
                     "runs emit the identical per-rank total 28672 B and "
                     "per-config total 1376256 B with 0 violations — "
                     "O-CONSERVATION is algebraically blind to the link-BW "
                     "axis, matching the registry's declared 'sensitivity: "
                     "zero for O-CONSERVATION' (A-L0-BW)",
        "o_cct_collapse": "with wire fixed, the WHOLE effect of B on the "
                          "model is the single additive term 28672/B — "
                          "the sensitivity map is the hyperbola segment "
                          "[28, 28672] ns added to the constant 2800 ns",
    }

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, GLOBAL stage GLOB-BW (parameter "
                 "class: link bandwidth; the first of the four global "
                 "parameter-class sensitivity stages)",
        "parameter_class": {
            "class": "link bandwidth",
            "parameter": "link.bytes_per_ns",
            "registry_ids": {
                "A-L0-BW": "the executed axis — the W1 smoke config's ring "
                           "fabric (analytical_l0)",
                "A-L0T-BW": "the 2D-torus twin (same parameter name, same "
                            "declared value 64 and range [1,1024], values "
                            "deliberately shared across fabrics per its "
                            "rationale) — NOT part of the W1 smoke config, "
                            "not swept in this stage",
            },
            "registered_range_bytes_per_ns": ["1", "1024"],
            "registry_point": "64",
            "registry_point_role_in_this_stage": "the W1 smoke config's own "
                                                 "shipped value — the sweep "
                                                 "baseline every delta reads "
                                                 "against",
            "plan_verdict_context": "CALIBRATION_PLAN.md section 2.1 A-L0-BW: "
                                    "NARROW (range) / KEEP (point) — candidate "
                                    "anchor-informed span [20, 64] pending "
                                    "owner acceptance; this stage executes the "
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
                                             "small-message gap), so no "
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
                "L_ns": "200 (A-L0-LAT registry point, KEEP; the latency axis "
                        "is deferred to its own global stage)",
                "backend": "analytical_l0",
            },
        },
        "model": {
            "backend_ids": ["analytical_l0"],
            "identity": "t(B) = 2(r-1)/r*M/B + 2(r-1)L = 28672/B + 2800 ns; "
                        "per-rank wire 2(r-1)/r*M = 28672 B (B-independent)",
            "ranks": 8,
            "payload_bytes": M,
            "ops_per_config": OPS,
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    str(b): rows_by_b[Fraction(b)]["config_id"].split("-")[2]
                    for b in B_LADDER
                },
                "B_ladder_design": "the powers of two spanning the whole "
                                   "registered range [1, 1024] (11 points: 1 "
                                   "and 1024 the registered endpoints, 64 the "
                                   "registry point/smoke value/baseline) plus "
                                   "three anchor-informed span CONTEXT "
                                   "markers 20/25/50 (plan section 2.1 A-L0-BW "
                                   "candidate span [20, 64] interior; context "
                                   "only — the anchor comparisons themselves "
                                   "were the per-anchor stages' job)",
                "L_ns": 200,
                "L_provenance": "A-L0-LAT registry point (KEEP per plan "
                                "section 2.1); hop/pair latency is the second "
                                "global stage's axis",
            },
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV from "
                           "experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "sensitivity_sweep": ladder_block["sensitivity_ladder_B_1_to_1024"],
            "sweep_facts": ladder_block["sweep_facts"],
            "endpoint_and_twin_runs": {
                "lower_endpoint": b1,
                "upper_endpoint": b1024,
                "registry_twin": twin,
                "twin_check": "the sweep's B=64 baseline row equals the landed "
                              "W1 smoke store run's CCT/wire/totals digit for "
                              "digit (3248 ns), and both endpoint runs equal "
                              "their sweep rows — four independent artifacts, "
                              "one identity, zero drift",
            },
            "asymptotes_and_gains": asym,
            "anchor_informed_span_context": span,
            "elasticity": elasticity,
            "conservation_invariance": conservation,
        },
        "deviation": {
            "vs_anchor": "UNDEFINED BY CONSTRUCTION — no anchor and no "
                         "external measurement enters a global sensitivity "
                         "stage; the recorded deviations are the sweep's own "
                         "deltas vs the registry point B=64 (the W1 smoke "
                         "value), i.e. placement of the model's output across "
                         "its registered parameter range, never agreement "
                         "with any measurement",
            "summary": "smoke-config O-CCT spans 31472 ns (B=1) to 2828 ns "
                       "(B=1024) across the registered range — +869.0% above "
                       "and -12.93% below the registry point's 3248 ns; the "
                       "axis is hyperbolic with the balance point B* = "
                       "M/(r*L) = 256/25 = 10.24 B/ns splitting it into a "
                       "bandwidth-dominated quarter (4 of 14 grid points) and "
                       "a latency-dominated remainder that includes the "
                       "registry point, the whole anchor-informed span, and "
                       "an exactly-1%-above-floor upper endpoint; "
                       "O-CONSERVATION is B-blind (0 violations, identical "
                       "wire at all 14 points)",
        },
        "evidence_levels": {
            "runs_and_sweep": "E0 (analytical executions; deterministic, "
                              "content-addressed, replay-verified "
                              "byte-identical)",
            "candidate": "PROPOSED global sensitivity candidate; no E3/E4 "
                         "language — no external target exists or is claimed",
        },
        "backing": {
            "run_ids": [RUN_ID_B1, RUN_ID_B1024, RUN_ID_SMOKE_TWIN],
            "run_roles": {
                RUN_ID_B1: "registered-range lower endpoint (this stage)",
                RUN_ID_B1024: "registered-range upper endpoint (this stage)",
                RUN_ID_SMOKE_TWIN: "landed W1 smoke run at the registry point "
                                   "(vertical slice, cited as twin "
                                   "cross-check)",
            },
            "sweep_ids": [SWEEP_ID],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID}"],
            "backed_numbers": "every model output in comparison."
                              "sensitivity_sweep and comparison."
                              "endpoint_and_twin_runs is backed by the sweep "
                              "id and run ids above (closed-form cross-checked "
                              "by exact Fraction string equality on every row "
                              "and run, asserted in the builder); every "
                              "derived fraction (delta family, balance point, "
                              "shares, elasticity, span movement) is "
                              "recomputed from those artifacts by the builder, "
                              "never transcribed",
            "inputs": [
                "experiments/calibration/globbw/sweep_globbw_v1.yaml",
                "experiments/calibration/globbw/run_globbw_b1_v1.yaml",
                "experiments/calibration/globbw/run_globbw_b1024_v1.yaml",
                "experiments/calibration/globbw/topologies/ (14 files)",
                "experiments/calibration/globbw/profiles/implementation_profile_l0_ring_cal_globbw_v1.yaml",
                "experiments/workloads/w1_dense_tp_decode_small.yaml (the W1 smoke workload, referenced unmodified)",
                "experiments/vertical_slice/assumptions_l0.yaml (referenced unmodified)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/globbw/sweep_globbw_v1.yaml ; "
                         "make run EXP=experiments/calibration/globbw/run_globbw_b1_v1.yaml ; "
                         "make run EXP=experiments/calibration/globbw/run_globbw_b1024_v1.yaml ; "
                         "python experiments/calibration/globbw/build_calibration_record.py",
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
