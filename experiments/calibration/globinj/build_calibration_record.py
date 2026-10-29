"""Build the PROPOSED global-sensitivity record for parameter class
INJECTION BANDWIDTH (Q1 calibration-ladder GLOBAL stage GLOB-INJ, the
third of the four global parameter-class stages.
docs/calibration/CALIBRATION_PLAN.md).

Pure function of immutable artifacts: reads the sweep table and the two
endpoint store-run records produced by this stage (plus the landed W1
smoke store run, the GLOB-BW and GLOB-LAT sweep tables, and the 8r-l05
atlas cell table as cross-artifact twins), recomputes every derived
quantity with exact Fractions, and writes a content-addressed record to
``results/calibration/<record_id>/record.json`` (record_id = SHA-256 of
the canonical record; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce
byte-identical records. Every number in the record is either (a)
transcribed from the assumption registry / calibration plan (declared
with provenance), or (b) computed from the stored sweep/run artifacts by
this script (closed-form cross-checks by exact Fraction string equality
on every executed row). NOTHING is tuned and NO anchor is compared: this
is a global sensitivity stage — it maps the model's own response surface
along the REGISTERED A-L05-INJ axis [1, 1024] B/ns on the W1 smoke
config (the L0.5 serialized ring's per-chunk serialization rate; the
identity that governs the physics is t_L05 - t_L0 = 2*(r-1)/r*M/I).

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
# Stage artifacts (content addresses of this stage's sweep and endpoint
# runs; identical manifests + code reproduce them, so replay reproduces
# this record).
# ---------------------------------------------------------------------------
SWEEP_ID = "0051d0c84bd74b017293ba6f8f81a61536e632a40459e3afc1e054b78a6c7164"
RUN_ID_I1 = "351d00053348fcafad6b40eb91e83028b6bc5ec81525dfe07c492774171eae78"
RUN_ID_I1024 = "ff202dbb1efeb8397898111da212de3707a6c905cc34aecfebacfbaf41d4f7a8"
# Cross-artifact twins (landed by earlier stages; cited, not re-run):
# the W1 smoke store run (EXP-VS-W1-SMOKE-001, analytical_l0 at B=64,
# L=200) — the I -> infinity limit of THIS stage's identity.
RUN_ID_SMOKE_TWIN = "144228d060174a37a27bec733d7bb351504d61478459f4d181c0987f974b3d77"
# the GLOB-BW sweep table (its B=64 row = the smoke point; its B=32 row =
# the series-law image of this stage's I=64 row; its delta family the
# structural counterpart of this stage's).
SWEEP_ID_GLOBBW = "ec08bb06df65c2ac931ef36a514be8eac80e2ab2728e54a0a5987b7938a89452"
# the GLOB-LAT sweep table (its L=200 row = the same smoke point again).
SWEEP_ID_GLOBLAT = "d4fa28321ef14dfb0eb0dfac557726d6982f2eaa35793cd3305a4a0a36fe1ab4"
# the 8r-l05 atlas cell (rank-8 L0.5 at the registry I=64 over the shared
# 12-size ladder — its M=16384 row IS this stage's baseline row).
ATLAS_8R_L05_CELL_ID = "48ede12dc675174f5bb40f4b79932d4163395ed52663e10e711a48ba79b5d0ea"

RESULTS = REPO_ROOT / "results"

# The W1 smoke configuration, verbatim: W1 Dense TP Decode, tp8,
# 2 layers x 3 steps = 6 AllReduce ops, payload M = 16384 B (A-W1-SIZE
# smoke value), serialized ring r=8, B = 64 B/ns and L = 200 ns (the
# shared A-L05-BW / A-L05-LAT registry points, KEEP).
R = 8
M = 16384
L = Fraction(200)
B = Fraction(64)
REGISTRY_I = Fraction(64)
RANGE_LOW = Fraction(1)
RANGE_HIGH = Fraction(1024)
OPS = 6

# Closed-form identities of the executed backend (analytical_l05):
#   wire per rank  w = 2*(r-1)/r * M = 28672 B (independent of I —
#                   serialization moves no bytes)
#   t_L0 (anchor)  = w/B + 2*(r-1)*L = 448 + 2800 = 3248 ns
#   t_L05(I)       = t_L0 + 2*(r-1)/r * M/I = 3248 + 28672/I ns
#   at I -> inf    : the serialization term is exactly 0 and t_L05 == t_L0.
WIRE = Fraction(2 * (R - 1) * M, R)          # 28672
BW_TERM = WIRE / B                           # 448 (the ring's bandwidth term)
LAT_CHAIN = 2 * (R - 1) * L                  # 2800 (14L)
L0_CCT = BW_TERM + LAT_CHAIN                 # 3248
SER = WIRE                                   # serialization coefficient 28672
BASELINE_CCT = L0_CCT + SER / REGISTRY_I     # 3696
TOTAL_WIRE = OPS * 2 * (R - 1) * M           # 1376256 per-config conservation total

# Swept I ladder: 14 registered-range points + the I->inf limit row.
I_LADDER = [1, 2, 4, 8, 16, 32, 64, 128, 256, 448, 512, 720, 900, 1024]
CONTEXT_POINTS = {
    448: "CAL-A7-derived MI300X-class aggregate injection (plan section 2.1 A-L0X-BW)",
    720: "CAL-A12 software-effective ~80% derating of CAL-A2's NVL72 900 B/ns",
    900: "CAL-A2 NVL72-class aggregate injection (plan section 2.1 A-L0X-BW)",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def l05_time(i: Fraction) -> Fraction:
    return L0_CCT + SER / i


def l0_time(b: Fraction) -> Fraction:
    return WIRE / b + LAT_CHAIN


def delta_vs_registry(i: Fraction) -> Fraction:
    return (l05_time(i) - BASELINE_CCT) / BASELINE_CCT


def run_summary(run_id: str, i: Fraction, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    cct = Fraction(per_op["completion_time_ns_exact"])
    payload = per_op["payload_bytes"]
    i_run = Fraction(obs["model"]["injection_bytes_per_ns_exact"])
    # Closed-form cross-checks (exact): identity, anchor, term, wire,
    # conservation — plus the convergence identity itself.
    assert i_run == i
    assert payload == M
    assert cct == l05_time(i), (run_id, cct)
    assert Fraction(per_op["l0_anchor_time_ns_exact"]) == L0_CCT
    assert Fraction(per_op["serialization_term_ns_exact"]) == SER / i
    assert cct - Fraction(per_op["l0_anchor_time_ns_exact"]) == SER / i
    assert Fraction(per_op["per_rank_wire_bytes_exact"]) == WIRE
    assert all(Fraction(p["completion_time_ns_exact"]) == cct for p in obs["per_op"])
    cons = obs["observables"]["O-CONSERVATION"]
    assert cons["violations"] == 0
    assert Fraction(cons["total_wire_bytes_exact"]) == TOTAL_WIRE
    # The store record's execution provenance names the vehicle and the
    # live run-path rejection (both run paths reject analytical_l05).
    assert run["execution"]["vehicle"].endswith("run_globinj_endpoints.py")
    assert "unknown backend(s)" in run["execution"]["live_run_path_rejection"]
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": obs["model"]["ranks"],
            "link_bytes_per_ns_exact": obs["model"]["link_bytes_per_ns_exact"],
            "hop_latency_ns_exact": obs["model"]["hop_latency_ns_exact"],
            "injection_bytes_per_ns_exact": obs["model"]["injection_bytes_per_ns_exact"],
        },
        "payload_bytes": payload,
        "ops": len(obs["per_op"]),
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "l0_anchor_ns_exact": per_op["l0_anchor_time_ns_exact"],
        "serialization_term_ns_exact": per_op["serialization_term_ns_exact"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "o_conservation_violations": cons["violations"],
        "execution": "module-direct vehicle run_globinj_endpoints.py (both "
                     "run-path registries reject analytical_l05; live "
                     "rejection string embedded in the run record)",
        "closed_form_check": "exact equality vs 3248 + 28672/I (asserted in builder)",
    }


def _globbw_row(tag: str) -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID_GLOBBW / "table.json")
    for row in table["configs"]:
        if f"globbw_{tag}_" in row["config_id"]:
            return row
    raise AssertionError(f"GLOB-BW row {tag} not found")


def _globlat_row(tag: str) -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID_GLOBLAT / "table.json")
    for row in table["configs"]:
        if f"globlat_{tag}_" in row["config_id"]:
            return row
    raise AssertionError(f"GLOB-LAT row {tag} not found")


def sensitivity_ladder() -> tuple[dict, dict]:
    """The executed sweep rows + per-I derived facts, all cross-checked."""
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    assert table["sweep"] == "cal_globinj_v1"
    assert len(table["configs"]) == len(I_LADDER) + 1  # + the I->inf limit row
    rows_by_i: dict[Fraction, dict] = {}
    limit_row = None
    for row in table["configs"]:
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        anchor = Fraction(row["l0_anchor_time_ns_exact"])
        term = Fraction(row["serialization_term_ns_exact"])
        # Closed-form cross-checks (exact) on EVERY executed row.
        assert anchor == L0_CCT, (row["config_id"], anchor)
        assert Fraction(row["per_rank_wire_bytes_exact"]) == WIRE
        assert row["o_conservation"]["violations"] == 0
        assert Fraction(row["o_conservation"]["total_wire_bytes_exact"]) == TOTAL_WIRE
        assert row["payload_bytes"] == M
        if row["injection_bytes_per_ns"] is None:
            limit_row = row
            assert cct == L0_CCT and term == 0  # the convergence limit itself
            assert cct - anchor == term
            d = Fraction(row["delta_vs_baseline"]["delta_exact"])
            assert d == -SER / REGISTRY_I / BASELINE_CCT  # -4/33
        else:
            i = Fraction(row["injection_bytes_per_ns"])
            assert cct == l05_time(i), (row["config_id"], cct)
            assert term == SER / i and cct - anchor == term
            # Delta column recomputed independently + the single rational
            # delta family 4*(64/I - 1)/33 holds everywhere.
            d = Fraction(row["delta_vs_baseline"]["delta_exact"])
            assert d == delta_vs_registry(i), (row["config_id"], d)
            assert d == Fraction(4) * (REGISTRY_I / i - 1) / Fraction(33)
            rows_by_i[i] = row
    assert limit_row is not None
    assert sorted(rows_by_i) == sorted(Fraction(i) for i in I_LADDER)
    assert min(rows_by_i) == RANGE_LOW and max(rows_by_i) == RANGE_HIGH

    # Strict monotonicity of t along the in-range grid (decreasing in I).
    grid = sorted(rows_by_i)
    times = [Fraction(rows_by_i[i]["o_cct"]["completion_time_ns_mean_exact"]) for i in grid]
    assert all(x > y for x, y in zip(times, times[1:]))

    # Balance points of the axis (exact):
    #  (a) serialization term == the ring's own bandwidth term iff I == B:
    #      ON the grid at the registry point itself (family convention I=B).
    assert SER / B == BW_TERM and l05_time(B) == LAT_CHAIN + 2 * BW_TERM
    #  (b) serialization term == latency chain iff I = 28672/2800 = 256/25
    #      = 10.24 — the SAME value as GLOB-BW's B* (identical equation
    #      w/x == 14L), bracketed by grid points 8 and 16.
    i_lat = SER / LAT_CHAIN
    assert i_lat == Fraction(256, 25) and SER / i_lat == LAT_CHAIN
    assert Fraction(8) < i_lat < Fraction(16)
    #  (c) serialization term == the whole landed t_L0 iff
    #      I** = 28672/3248 = 256/29 ~ 8.83 — the axis's true half-way
    #      (t = 2*t_L0 there); also bracketed 8 < I** < 16.
    i_star = SER / L0_CCT
    assert i_star == Fraction(256, 29) and SER / i_star == L0_CCT
    assert l05_time(i_star) == 2 * L0_CCT
    assert Fraction(8) < i_star < Fraction(16)
    below = [i for i in grid if i < i_star]
    assert below == [Fraction(x) for x in (1, 2, 4, 8)]  # 4 of 14 below

    ladder = []
    for i in grid:
        row = rows_by_i[i]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        term = SER / i
        entry = {
            "I_bytes_per_ns": str(i),
            "config_id": row["config_id"],
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
            "l0_anchor_ns_exact": row["l0_anchor_time_ns_exact"],
            "serialization_term_ns_exact": row["serialization_term_ns_exact"],
            "serialization_share_of_cct_exact": str(term / cct),
            "regime_vs_balance_point": (
                "serialization-majority (I < I** = 256/29: the serialization "
                "term alone exceeds the whole landed L0 time)"
                if i < i_star
                else "l0-majority (I > I** = 256/29)"
            ),
            "delta_vs_registry_point_exact": row["delta_vs_baseline"]["delta_exact"],
            "delta_vs_registry_point_float": row["delta_vs_baseline"]["delta_float"],
            "role": (
                "registered-range lower endpoint" if i == 1
                else "registered-range upper endpoint" if i == 1024
                else "registry point = smoke value = baseline (= B by the "
                     "family convention; the serialization term exactly "
                     "equals the ring bandwidth term here)" if i == 64
                else f"anchor-informed scale context marker ({CONTEXT_POINTS[int(i)]})"
                if int(i) in CONTEXT_POINTS
                else "powers-of-two ladder interior point"
            ),
        }
        ladder.append(entry)
    limit_entry = {
        "I_bytes_per_ns": "inf (null — outside the registered range [1, 1024])",
        "config_id": limit_row["config_id"],
        "cct_ns_exact": limit_row["o_cct"]["completion_time_ns_mean_exact"],
        "cct_ns_float": limit_row["o_cct"]["completion_time_ns_mean"],
        "l0_anchor_ns_exact": limit_row["l0_anchor_time_ns_exact"],
        "serialization_term_ns_exact": limit_row["serialization_term_ns_exact"],
        "serialization_share_of_cct_exact": "0",
        "regime_vs_balance_point": "the convergence limit — t_L05 == t_L0 exactly",
        "delta_vs_registry_point_exact": limit_row["delta_vs_baseline"]["delta_exact"],
        "delta_vs_registry_point_float": limit_row["delta_vs_baseline"]["delta_float"],
        "role": "I -> infinity convergence limit (the model's own pinned "
                "anchor; executed as the twin cross-check row, not a "
                "registered-range point)",
    }
    facts = {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "execution_vehicle": table["execution_vehicle"],
        "orchestrator_rejections": table["orchestrator_rejections"],
        "baseline": "the A-L05-INJ registry point I=64 (the W1 smoke value)",
        "balance_points": {
            "serialization_equals_bandwidth_term": {
                "I_exact": "64",
                "law": "SER/I == w/B iff I == B — lands ON the grid at the "
                       "registry point itself (the family convention I = B); "
                       "t_L05(64) = 2800 + 2*448: serialization exactly "
                       "doubles the payload-transfer cost",
            },
            "serialization_equals_latency_chain": {
                "I_exact": str(i_lat),
                "I_float": float(i_lat),
                "law": "SER/I == 14L — the SAME balance value 256/25 = 10.24 "
                       "as GLOB-BW's B* (the equations are identical, w/x = "
                       "14L); bracketed by grid points 8 < 256/25 < 16",
            },
            "serialization_equals_whole_l0_time": {
                "I_star_exact": str(i_star),
                "I_star_float": float(i_star),
                "law": "SER/I == t_L0 — the axis's true half-way: t_L05(I**) "
                       "= 2*t_L0 = 6496 ns exactly; bracketed 8 < 256/29 < 16",
                "regime_split_of_grid": "4 of 14 in-range grid points below "
                                        "I** (1, 2, 4, 8) are serialization-"
                                        "majority; 10 of 14 above it (16..1024, "
                                        "incl. the registry point 64 and all "
                                        "three anchored-scale markers "
                                        "448/720/900) are l0-majority",
            },
        },
        "delta_family": {
            "form": "delta(I) = 4*(64/I - 1)/33 exactly, for every swept I",
            "properties": "zero exactly at the registry point; sign change "
                          "exactly there; at the powers of two the column "
                          "reads 84/11, 124/33, 20/11, 28/33, 4/11, 4/33, 0, "
                          "-2/33, -1/11, -7/66, -5/44; the limit row is "
                          "-4/33",
        },
    }
    return (
        {
            "sensitivity_ladder_I_1_to_1024": ladder,
            "convergence_limit_row": limit_entry,
            "sweep_facts": facts,
        },
        rows_by_i,
        limit_row,
    )


def main() -> int:
    ladder_block, rows_by_i, limit_row = sensitivity_ladder()

    # Endpoint store runs + the landed-smoke twin cross-check.
    i1 = run_summary(RUN_ID_I1, Fraction(1),
                     "registered-range LOWER endpoint I=1 (store run)")
    i1024 = run_summary(RUN_ID_I1024, Fraction(1024),
                        "registered-range UPPER endpoint I=1024 (store run)")
    # Twin 1: the I -> inf limit of THIS stage's identity is the landed W1
    # smoke run (analytical_l0 at the same B/L) — cited, not re-run.
    smoke = load_json(RESULTS / RUN_ID_SMOKE_TWIN / "observations.json")
    smoke_cct = Fraction(smoke["observables"]["O-CCT"]["completion_time_ns_mean_exact"])
    assert smoke_cct == L0_CCT == 3248
    assert smoke["model"]["link_bytes_per_ns_exact"] == str(B)
    assert smoke["model"]["hop_latency_ns_exact"] == str(L)
    assert smoke["model"]["ranks"] == R

    # Cross-artifact determinism tie-ins (digit for digit):
    #  (a) the limit row == the landed W1 smoke run == GLOB-BW's B=64 row
    #      == GLOB-LAT's L=200 row — the same smoke point executed
    #      independently FOUR times (one of them as this stage's limit), zero drift.
    assert limit_row["o_cct"]["completion_time_ns_mean_exact"] == "3248"
    assert Fraction(limit_row["o_cct"]["completion_time_ns_mean_exact"]) == smoke_cct
    globbw_b64 = _globbw_row("b64")
    globlat_l200 = _globlat_row("l200")
    assert globbw_b64["o_cct"]["completion_time_ns_mean_exact"] == "3248"
    assert globlat_l200["o_cct"]["completion_time_ns_mean_exact"] == "3248"
    #  (b) the I=64 baseline row == the 8r-l05 atlas cell's M=16384 row
    #      (an INDEPENDENT rank-8 L0.5 execution over the 12-size ladder).
    atlas = load_json(RESULTS / "atlas" / "8r_l05" / ATLAS_8R_L05_CELL_ID / "table.json")
    atlas_row = next(r for r in atlas["rows"] if r["payload_bytes"] == M)
    assert atlas_row["l05_cct_ns_exact"] == "3696"
    assert atlas_row["ring_cct_ns_exact"] == "3248"
    assert atlas_row["serialization_term_ns_exact"] == "448"
    assert atlas_row["delta_vs_baseline"]["delta_exact"] == "4/29"
    assert rows_by_i[REGISTRY_I]["o_cct"]["completion_time_ns_mean_exact"] == "3696"
    #  (c) the series law: t_L05(I=64) == GLOB-BW's B=32 row (B_eff = 32).
    globbw_b32 = _globbw_row("b32")
    assert globbw_b32["o_cct"]["completion_time_ns_mean_exact"] == "3696"
    #  (d) both endpoint runs equal their sweep rows.
    assert i1["cct_ns_exact"] == rows_by_i[Fraction(1)]["o_cct"]["completion_time_ns_mean_exact"]
    assert i1024["cct_ns_exact"] == rows_by_i[Fraction(1024)]["o_cct"]["completion_time_ns_mean_exact"]

    # Asymptotics, convergence, and gains (exact).
    t_low, t_high, t_reg = l05_time(1), l05_time(1024), BASELINE_CCT
    assert t_low == 31920 and t_high == 3276 and t_reg == 3696
    assert SER / RANGE_HIGH == 28  # the residual gap at the upper endpoint
    doubling_gains = []
    for i in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
        gain = l05_time(Fraction(i)) - l05_time(Fraction(2 * i))
        assert gain == SER / Fraction(2 * i)
        doubling_gains.append({"I_to_2I": f"{i}->{2*i}", "cct_gain_ns_exact": str(gain)})
    # Structural asymmetry constant: identical to GLOB-BW's because both
    # axes are [1, 1024] with registry point 64 — the ratio is
    # denominator-free: (64/1 - 1)/(1 - 64/1024) = 63·16/15 = 336/5.
    mine = abs(delta_vs_registry(Fraction(1)) / delta_vs_registry(Fraction(1024)))
    bw_d1 = Fraction(_globbw_row("b1")["delta_vs_baseline"]["delta_exact"])
    bw_d1024 = Fraction(_globbw_row("b1024")["delta_vs_baseline"]["delta_exact"])
    assert mine == abs(bw_d1 / bw_d1024) == Fraction(336, 5)
    asym = {
        "convergence_floor_ns_exact": str(L0_CCT),
        "convergence_floor_meaning": "t_L0 = 3248 ns at the shared B = 64, "
                                     "L = 200 — the landed L0 identity the "
                                     "axis collapses onto as I grows; the "
                                     "floor is a DIFFERENT MODEL's executed "
                                     "output, itself twin-tied to three "
                                     "independent artifacts",
        "upper_endpoint_cct_ns_exact": str(t_high),
        "upper_endpoint_gap_to_floor_exact": "28 (= 28672/1024 = 7/812 = "
                                             "0.86% of the floor)",
        "max_cut_from_infinite_I_exact": "-4/33",
        "max_cut_from_infinite_I_float": float(Fraction(-4, 33)),
        "max_cut_meaning": "no I above the registry point — not 1024, not "
                           "+infinity — can reduce smoke-config L0.5 CCT by "
                           "more than 4/33 = 12.12% (= the registry point's "
                           "own serialization share, 448/3696); the whole "
                           "upper half-axis is capped by the L0 floor",
        "lower_endpoint_delta_exact": str(delta_vs_registry(Fraction(1))),
        "lower_endpoint_delta_float": float(delta_vs_registry(Fraction(1))),
        "full_range_cct_ratio_exact": str(t_low / t_high),
        "full_range_cct_ratio_float": float(t_low / t_high),
        "asymmetry_exact": "336/5",
        "asymmetry_float": 67.2,
        "asymmetry_meaning": "the registered axis is 67.2x more sensitive "
                             "below the registry point (+763.64% at I=1) than "
                             "above it (-11.36% at I=1024) — the SAME "
                             "structural constant as GLOB-BW (verified "
                             "digit-for-digit from both sweep tables): for "
                             "any [1, 1024] axis with point 64 the ratio is "
                             "denominator-free, (64-1)/(1-64/1024) = 336/5",
        "doubling_gains_ns": doubling_gains,
        "doubling_law": "t(I) - t(2I) = 28672/(2I) exactly — each doubling "
                        "buys exactly the new serialization term; gains "
                        "halve with every doubling (448 ns at 32->64, 28 ns "
                        "at 512->1024)",
    }

    # The series (harmonic) law: serialization at I acts exactly like
    # replacing the link bandwidth B by B_eff with 1/B_eff = 1/B + 1/I —
    # the whole I axis is the GLOB-BW map reparametrized.
    b_eff = B * REGISTRY_I / (B + REGISTRY_I)
    assert b_eff == 32 and l0_time(b_eff) == BASELINE_CCT
    series = {
        "law": "t_L05(I) = t_L0(B_eff) with 1/B_eff = 1/B + 1/I exactly "
               "(the series/harmonic law: L0.5's per-chunk serialization at "
               "the transmitting NIC is indistinguishable, at the CCT "
               "identity, from a series link of rate I ahead of a link of "
               "rate B)",
        "at_registry_pair": "B_eff(64, 64) = 64*64/(64+64) = 32 B/ns — "
                            "L0.5 at the registry point IS L0 at B=32: this "
                            "stage's I=64 row (3696 ns) equals GLOB-BW's "
                            "B=32 row digit for digit (asserted)",
        "m_reading": "the same law read on the payload axis: at I = B, "
                     "t_L05(M) = t_L0(2M) exactly — the landed 8r/16r-l05 "
                     "atlas cell identity (this stage's baseline row equals "
                     "the atlas cell's M=16384 row, asserted digit for "
                     "digit)",
    }

    # Anchor-informed scale context (plan section 2.1 A-L0X-BW NARROW
    # (scale) verdict — a DIFFERENT registry id than A-L05-INJ, quoted for
    # scale context only; NO value changed by this stage).
    span = {
        "anchored_scale_bytes_per_ns": ["448", "900"],
        "provenance": "CALIBRATION_PLAN.md section 2.1 row A-L0X-BW: NARROW "
                      "(scale) — 'every modern anchor sits at 448-900 B/ns "
                      "aggregate' (CAL-A7-derived MI300X 448, CAL-A2 NVL72 "
                      "900, CAL-A12 software-effective ~80% -> 720). Those "
                      "anchors speak to a DIFFERENT parameter construction "
                      "(aggregate per-rank injection in the crossbar/"
                      "doubling models) than A-L05-INJ (a per-chunk NIC "
                      "serialization rate in a serialized ring); the three "
                      "values are swept here strictly as scale CONTEXT "
                      "markers, and this stage compares nothing against "
                      "them. It decides nothing.",
        "registry_point_vs_anchored_scale": "the registry point 64 sits 7x "
                                            "below the lowest anchored scale "
                                            "marker (448/64 = 7)",
        "movement_at_anchored_scale_exact": {
            "448": str(delta_vs_registry(Fraction(448))),
            "900": str(delta_vs_registry(Fraction(900))),
        },
        "anchored_scale_span_width": "the entire anchored span 448-900 moves "
                                     "smoke-config t_L05 by only 3312 - "
                                     "737968/225 = 32 ns (< 1%), while the "
                                     "distance from the registry point to "
                                     "the anchored scale is 10.4-11.3% — "
                                     "leaving the anchored scale down to the "
                                     "registry point costs more than the "
                                     "whole anchored span's internal width",
        "serialization_at_anchored_scale": "at every anchored-scale marker "
                                           "the serialization term is <= 64 "
                                           "ns (<= 1.93% of CCT): the "
                                           "anchored region is already within "
                                           "0.86-1.93% of the convergence "
                                           "floor",
    }

    # Local elasticity at the registry point (the 'sensitivity' question).
    share_reg = (SER / REGISTRY_I) / BASELINE_CCT
    assert share_reg == Fraction(4, 33)
    elasticity = {
        "definition": "elasticity = (dt/dI)*(I/t) = serialization share of "
                      "CCT (exact for the hyperbola t = c + k/I)",
        "at_registry_point_64_exact": str(share_reg),
        "at_registry_point_64_float": float(share_reg),
        "meaning": "a +1% I at the registry point lowers smoke-config "
                   "L0.5 CCT by only 0.121%; the registry's declared "
                   "'sensitivity: high for O-CCT (the whole L0-vs-L0.5 "
                   "disagreement is 2*(r-1)/r*M/I)' (A-L05-INJ) materializes "
                   "only deep below the registry point — the share crosses "
                   "1/2 at I** = 256/29 and reaches 89.8% at I=1",
        "share_crosses_half_at": "I** = 256/29 exactly (serialization term "
                                 "== the whole landed t_L0)",
        "at_lower_endpoint_1_exact": str((SER / 1) / l05_time(1)),
        "at_lower_endpoint_1_float": float((SER / 1) / l05_time(1)),
    }

    # O-CONSERVATION invariance (structurally blind to I, as declared).
    conservation = {
        "per_rank_wire_bytes_exact": str(WIRE),
        "total_wire_bytes_exact": str(TOTAL_WIRE),
        "statement": "wire bytes are EXACTLY I-invariant (serialization "
                     "moves no bytes): all 15 sweep rows — including the "
                     "I->inf limit row — and both endpoint store runs emit "
                     "the identical per-rank total 28672 B and per-config "
                     "total 1376256 B with 0 violations, matching the "
                     "registry's declared 'sensitivity: zero for "
                     "O-CONSERVATION' (A-L05-INJ)",
        "o_cct_collapse": "with wire fixed, the WHOLE effect of I on the "
                          "model is the single additive term 28672/I on top "
                          "of the constant t_L0 = 3248 ns — the sensitivity "
                          "map is the hyperbola segment [28, 28672] ns added "
                          "to the landed L0 identity",
    }

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, GLOBAL stage GLOB-INJ (parameter "
                 "class: injection bandwidth; the third of the four global "
                 "parameter-class sensitivity stages)",
        "parameter_class": {
            "class": "injection bandwidth",
            "parameter": "nic.injection_bytes_per_ns",
            "registry_ids": {
                "A-L05-INJ": "the executed axis — the L0.5 serialized "
                             "ring's per-chunk serialization (injection) "
                             "rate, the injection/serialization-related "
                             "input of the W1 smoke config's L0.5 path "
                             "(backend analytical_l05)",
                "A-L0X-BW / A-L0D-BW": "registry relatives: the crossbar / "
                                        "recursive-doubling models' "
                                        "aggregate injection inputs (same "
                                        "parameter name, value 64, range "
                                        "[1,1024]) — NOT part of the smoke "
                                        "config's L0.5 path, not swept in "
                                        "this stage; their anchored-scale "
                                        "context (plan section 2.1) supplies "
                                        "this stage's context markers only",
            },
            "registered_range_bytes_per_ns": ["1", "1024"],
            "registry_point": "64",
            "registry_point_role_in_this_stage": "the W1 smoke config's own "
                                                 "shipped value (equal to B "
                                                 "by the family convention "
                                                 "noted in the A-L05-INJ "
                                                 "rationale) — the sweep "
                                                 "baseline every delta reads "
                                                 "against",
            "null_encoding": "registry value null (or an absent nic block) "
                             "encodes the I -> infinity limit — the "
                             "convergence anchor pinned by tests; executed "
                             "here as the sweep's 15th (twin) row, OUTSIDE "
                             "the registered range",
            "plan_verdict_context": "CALIBRATION_PLAN.md's global-stages "
                                    "clause names the four parameter "
                                    "classes (link BW, hop/pair latency, "
                                    "injection BW, serialization rate); the "
                                    "injection-BW class's smoke-config "
                                    "representative is A-L05-INJ (the plan's "
                                    "section 2.1 tables predate the L0.5 "
                                    "registry split D-031 and carry no "
                                    "A-L05-INJ row of their own; the "
                                    "NARROW-scale context quoted above comes "
                                    "from the A-L0X-BW row)",
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
                "topology_class": "unidirectional_ring_with_serialization "
                                  "(the L0.5 smoke fabric "
                                  "ring8_l05_free_v1's class), r = 8",
                "B_ns": "64 (A-L05-BW registry point, KEEP; the link-BW axis "
                        "was GLOB-BW's own axis)",
                "L_ns": "200 (A-L05-LAT registry point, KEEP; the "
                        "hop/pair-latency axis was GLOB-LAT's own axis)",
                "backend": "analytical_l05 (module-direct execution vehicle; "
                           "both run-path registries reject the id live — "
                           "exact strings in sweep_facts.orchestrator_"
                           "rejections, the 4r/8r/16r-l05 atlas pattern)",
            },
        },
        "model": {
            "backend_ids": ["analytical_l05"],
            "identity": "t_L05(I) = t_L0 + 2*(r-1)/r*M/I = 3248 + 28672/I ns "
                        "at finite I (the soak suite's pinned identity "
                        "t_L05 - t_L0 = 2*(r-1)/r*M/I); at I -> infinity "
                        "exactly t_L0 = 3248 ns; per-rank wire 2*(r-1)/r*M "
                        "= 28672 B (I-independent)",
            "ranks": 8,
            "payload_bytes": M,
            "ops_per_config": OPS,
            "free_parameters": {
                "I_swept_bytes_per_ns": {
                    str(i): rows_by_i[Fraction(i)]["config_id"]
                    for i in I_LADDER
                },
                "I_ladder_design": "the powers of two spanning the whole "
                                   "registered range [1, 1024] (11 points: 1 "
                                   "and 1024 the registered endpoints, 64 the "
                                   "registry point/smoke value/baseline) plus "
                                   "three anchor-informed scale CONTEXT "
                                   "markers 448/720/900 (plan section 2.1 "
                                   "A-L0X-BW anchored aggregate injection "
                                   "scale; context only — the anchor "
                                   "comparisons themselves were the "
                                   "per-anchor stages' job) plus one row "
                                   "OUTSIDE the registered range: the I -> "
                                   "infinity convergence limit (null), the "
                                   "model's own pinned anchor, executed as "
                                   "the twin cross-check row",
                "B_ns": 64,
                "B_provenance": "A-L05-BW registry point (KEEP; equal to the "
                                "L0 ring value by design so the convergence "
                                "anchor is shared)",
                "L_ns": 200,
                "L_provenance": "A-L05-LAT registry point (KEEP)",
            },
            "assumptions": "A-L05-BW / A-L05-LAT / A-L05-INJ / A-L05-SER / "
                           "A-L05-CHUNK / A-L05-DIV from "
                           "experiments/vertical_slice/assumptions_l05.yaml",
        },
        "comparison": {
            "sensitivity_sweep": ladder_block["sensitivity_ladder_I_1_to_1024"],
            "convergence_limit_row": ladder_block["convergence_limit_row"],
            "sweep_facts": ladder_block["sweep_facts"],
            "endpoint_and_twin_runs": {
                "lower_endpoint": i1,
                "upper_endpoint": i1024,
                "registry_twin": {
                    "run_id": RUN_ID_SMOKE_TWIN,
                    "mapping": "the landed W1 smoke store run "
                               "(EXP-VS-W1-SMOKE-001, analytical_l0 at the "
                               "shared B=64/L=200) — the I -> infinity limit "
                               "of this stage's identity, cited as twin "
                               "cross-check",
                    "cct_ns_exact": "3248",
                },
                "twin_check": "the sweep's I->inf limit row equals the landed "
                              "W1 smoke run, GLOB-BW's B=64 row and "
                              "GLOB-LAT's L=200 row — the same smoke point "
                              "executed independently four times, zero "
                              "drift; the I=64 baseline row equals the 8r-l05 "
                              "atlas cell's M=16384 row (3696 ns, term 448, "
                              "delta 4/29) and GLOB-BW's B=32 row (the "
                              "series law); both endpoint runs equal their "
                              "sweep rows — seven independent artifacts, "
                              "one identity, zero drift",
            },
            "asymptotes_and_gains": asym,
            "series_law": series,
            "anchor_informed_scale_context": span,
            "elasticity": elasticity,
            "conservation_invariance": conservation,
        },
        "deviation": {
            "vs_anchor": "UNDEFINED BY CONSTRUCTION — no anchor and no "
                         "external measurement enters a global sensitivity "
                         "stage; the recorded deviations are the sweep's own "
                         "deltas vs the registry point I=64 (the W1 smoke "
                         "value), i.e. placement of the model's output across "
                         "its registered parameter range, never agreement "
                         "with any measurement",
            "summary": "smoke-config L0.5 O-CCT spans 31920 ns (I=1) to 3276 "
                       "ns (I=1024) across the registered range — +763.64% "
                       "above and -11.36% below the registry point's 3696 ns "
                       "(all deltas the one family 4(64/I - 1)/33) — and "
                       "converges exactly onto the landed L0 identity 3248 "
                       "ns as I -> infinity (the pinned convergence anchor, "
                       "twin-tied digit-for-digit to the W1 smoke run and "
                       "both earlier global stages' baseline rows); the axis "
                       "is a hyperbola with the serialization term equal to "
                       "the ring's own bandwidth term exactly at the "
                       "registry point (I = B = 64), equal to the latency "
                       "chain at I = 256/25 = 10.24 (GLOB-BW's B* value), "
                       "and equal to the whole landed t_L0 at I** = 256/29 "
                       "~ 8.83 (the 4-vs-10 regime split); O-CONSERVATION is "
                       "I-blind (0 violations, identical wire at all 15 "
                       "points including the limit)",
        },
        "evidence_levels": {
            "runs_and_sweep": "E0 (analytical executions; deterministic, "
                              "content-addressed, replay-verified "
                              "byte-identical)",
            "candidate": "PROPOSED global sensitivity candidate; no E3/E4 "
                         "language — no external target exists or is claimed",
        },
        "backing": {
            "run_ids": [RUN_ID_I1, RUN_ID_I1024, RUN_ID_SMOKE_TWIN],
            "run_roles": {
                RUN_ID_I1: "registered-range lower endpoint (this stage)",
                RUN_ID_I1024: "registered-range upper endpoint (this stage)",
                RUN_ID_SMOKE_TWIN: "landed W1 smoke run — the I->infinity "
                                   "limit of this stage's identity (vertical "
                                   "slice, cited as twin cross-check)",
            },
            "sweep_ids": [SWEEP_ID],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID}"],
            "twin_artifacts": {
                "GLOB-BW sweep": f"results/sweeps/{SWEEP_ID_GLOBBW} "
                                 "(B=64 row = the convergence floor; B=32 "
                                 "row = the series-law image of the I=64 "
                                 "baseline; its delta family the structural "
                                 "counterpart of this stage's)",
                "GLOB-LAT sweep": f"results/sweeps/{SWEEP_ID_GLOBLAT} "
                                  "(L=200 row = the same smoke point again)",
                "8r-l05 atlas cell": f"results/atlas/8r_l05/"
                                     f"{ATLAS_8R_L05_CELL_ID} "
                                     "(M=16384 row = this stage's I=64 "
                                     "baseline row)",
            },
            "backed_numbers": "every model output in comparison."
                              "sensitivity_sweep, comparison."
                              "convergence_limit_row and comparison."
                              "endpoint_and_twin_runs is backed by the sweep "
                              "id and run ids above (closed-form "
                              "cross-checked by exact Fraction string "
                              "equality on every row and run, asserted in "
                              "the builder); every derived fraction (delta "
                              "family, balance points, shares, elasticity, "
                              "series law, asymmetry) is recomputed from "
                              "those artifacts by the builder, never "
                              "transcribed",
            "inputs": [
                "experiments/calibration/globinj/sweep_globinj_v1.yaml",
                "experiments/calibration/globinj/run_globinj_i1_v1.yaml",
                "experiments/calibration/globinj/run_globinj_i1024_v1.yaml",
                "experiments/calibration/globinj/topologies/ (15 files)",
                "experiments/calibration/globinj/profiles/implementation_profile_l05_ring_cal_globinj_v1.yaml",
                "experiments/calibration/globinj/run_globinj_sweep.py (execution vehicle)",
                "experiments/calibration/globinj/run_globinj_endpoints.py (execution vehicle)",
                "experiments/workloads/w1_dense_tp_decode_small.yaml (the W1 smoke workload, referenced unmodified)",
                "experiments/vertical_slice/assumptions_l05.yaml (referenced unmodified)",
            ],
            "reproduce": ".venv/bin/python experiments/calibration/globinj/run_globinj_sweep.py ; "
                         ".venv/bin/python experiments/calibration/globinj/run_globinj_endpoints.py ; "
                         "python experiments/calibration/globinj/build_calibration_record.py",
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
