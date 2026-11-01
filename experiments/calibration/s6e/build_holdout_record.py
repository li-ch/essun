"""Build the PROPOSED calibration holdout-evaluation record for stage S6e
(the small-message-axis rerun of the S6 holdout check against the SAME
immutable split record 3862e227..., experiments/calibration/split/
anchor_split_v1.json).

What this stage evaluates: the S4e FITTED endpoint-latency placements —
E = 8800 (GF-10 primary pair reading), 600 (CAL-A10 end-to-end reading),
0 (wire-class origin), flagged 9000 alternative — executed UNTOUCHED
against the split record's small-message-axis holdout members' staged
measured rows (transcription sources: the anchors' committed E1 stage
records and the S6 v1 holdout record 89f6256b...):

  GF-11 (GB200-class microbenchmarks, confidence H): the r=2
        decomposition point (SoL 1404 = 2*306 + 792, the anchor's own
        equation) and the r=4 bracket (near-optimal one-shot 2370 ns vs
        stock NCCL ring 11000 ns) at the declared 128-B reading;
  GF-01 (AMD ROCm blog, 8x MI300X 7-hop full-mesh xGMI, RCCL 2.22.3):
        the eager small-message rows 8/32/64 B (16.61-16.74 us) and the
        16/64 KiB reconciling rows (13.54/13.77 us);
  GF-03 (B300-class practitioner data, confidence M): the D2D latency
        points 1400/1600 ns (pair-level arithmetic context; the 2 MiB
        mid-size row is the bandwidth-ramp axis, carried unchanged).

EVALUATION-ONLY: no holdout number enters any fit objective, swept
value, or tolerance; NOTHING IS TUNED. The record's derived
``implied_effective_E`` values are declared diagnostics FROM the
measurements at the registry (B=64, L=200) — no run id, NO parameter is
set to them; they are the input any future endpoint-axis adjudication
must face (the v0.2 proposal section 3.3 discipline, now on the E axis).

Run-backed cross-checks enforced here (a mismatch is a bug, not a
finding): every executed row of both sweeps and both runs equals the
closed form of its own identity at the same (payload, B, L, E) by exact
Fraction string equality; both runs carry v2 dimensions with held_out
TRUE and calibration_target [].

Pure function of immutable artifacts; writes a content-addressed record
to ``results/calibration/<record_id>/record.json`` plus the committed
copy ``experiments/calibration/s6e/holdout_record_v1.json``
(byte-identical; append-only — a change requires holdout_record_v2).
No wall-clock, no host metadata.

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
# Stage artifacts (content addresses; identical manifests + code reproduce).
# ---------------------------------------------------------------------------
SWEEP_ID_GF11_TP4 = "242873ae8a27e76549843f1187ac0275af277ce75b62121acaafc46badbd8d38"
SWEEP_ID_GF01_SMALL = "da3eb61d989663f7f0f7fde0c7e9f26ed6f66c29dd09e1c7b3312662427479e6"
RUN_IDS = {
    "gf11_xbar2_e600": "51fcccd63dee24747eb4a5251fb8d17164cc330c63b976878cab1d3f5f347ec4",
    "gf11_xbar2_e8800": "9ab8dc8fe82a2d61ac586f59b858cab664b83f364281ca3dccde8687247bb2a3",
}
RUN_ROLES = {
    "gf11_xbar2_e600": "GF-11 r=2 decomposition-point evaluation run at E = 600 (held_out: true)",
    "gf11_xbar2_e8800": "GF-11 r=2 decomposition-point evaluation run at E = 8800 (held_out: true)",
}
RUN_EXPERIMENT_IDS = {
    "gf11_xbar2_e600": "EXP-CAL-S6E-GF11-EVAL-XBAR2-E600-001",
    "gf11_xbar2_e8800": "EXP-CAL-S6E-GF11-EVAL-XBAR2-E8800-001",
}

RESULTS = REPO_ROOT / "results"
S6E_DIR = REPO_ROOT / "experiments" / "calibration" / "s6e"
COMMITTED_COPY = S6E_DIR / "holdout_record_v1.json"

# ---------------------------------------------------------------------------
# Staged holdout measured rows (transcription sources: the anchors' E1
# stage records and the S6 v1 holdout record 89f6256b...). Nothing is
# re-fetched; nothing else is read.
# ---------------------------------------------------------------------------
# GF-11: r=2 SoL decomposition and r=4 bracket (ns).
GF11_RTT = Fraction(306)                # LL2 RTT
GF11_STORE = Fraction(792)              # remote store
GF11_SOL_R2 = 2 * GF11_RTT + GF11_STORE # 1404 — the anchor's own equation
GF11_NEAROPT_R4 = Fraction(2370)        # one-shot near-optimal AllReduce, 4 GB200s
GF11_NCCL_R4 = Fraction(11000)          # stock NCCL 2.29.1 ring, 4 GB200s
# GF-01: RCCL eager rows, r=8 (ns) — the reconciling series of the v1 record.
GF01_EAGER = {
    8: Fraction(16610),
    32: Fraction(16740),
    64: Fraction(16610),
    16384: Fraction(13540),
    65536: Fraction(13770),
}
# GF-03: D2D latency points (ns) and the mid-size row (us band), carried.
GF03_D2D = (Fraction(1400), Fraction(1600))
GF03_2MIB_US = (Fraction(42), Fraction(52))

# Registry points (UNCHANGED everywhere in this stage).
B_REG = Fraction(64)
L_REG = Fraction(200)
E_RANGE = (Fraction(0), Fraction(9000))   # A-L0E-LAT declared range

# The S4e fitted placements (carried bit-exact from fit record d91aaf87...).
E_FITS = {
    "wireclass_e0": Fraction(0),
    "a10_e600": Fraction(600),
    "gf10_e8800": Fraction(8800),
    "gf10_alt_e9000_flagged": Fraction(9000),
}

CHAIN = {"ring": lambda r: 2 * (r - 1), "crossbar": lambda r: 2, "exchange": lambda r: 2 * r.bit_length() - 2}


def wire_ns(payload: int, ranks: int) -> Fraction:
    return Fraction(2 * (ranks - 1) * payload, ranks) / B_REG


def closed_form(identity: str, payload: int, ranks: int, e: Fraction) -> Fraction:
    return wire_ns(payload, ranks) + CHAIN[identity](ranks) * L_REG + e


def pct(x: Fraction) -> float:
    return float(x) * 100.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sweep_rows(sweep_id: str) -> list[dict]:
    return load_json(RESULTS / "sweeps" / sweep_id / "table.json")["configs"]


IDENTITY_NAME = {"allreduce_ring": "ring", "allreduce_crossbar": "crossbar",
                 "allreduce_recursive_doubling": "exchange"}


def topo_e_from_id(topo_id: str) -> Fraction:
    stem = topo_id.split("_e", 1)[1].rsplit("_v1", 1)[0]
    return Fraction(stem.replace("_", "/"))


# ---------------------------------------------------------------------------
# GF-11 evaluation.
# ---------------------------------------------------------------------------
def eval_gf11() -> dict:
    # r=2 runs: cross-check the store records against the closed forms.
    run_rows = {}
    for key in RUN_IDS:
        obs = load_json(RESULTS / RUN_IDS[key] / "observations.json")
        run = load_json(RESULTS / RUN_IDS[key] / "run.json")
        per_op = obs["per_op"][0]
        e_value = Fraction(obs["model"]["endpoint_latency_ns_exact"])
        cct = Fraction(per_op["completion_time_ns_exact"])
        assert cct == closed_form("crossbar", per_op["payload_bytes"], 2, e_value)
        assert run["manifest"]["experiment_id"] == RUN_EXPERIMENT_IDS[key]
        assert run.get("evidence_schema_version") == 2
        assert run.get("held_out", {}).get("held_out") is True
        assert run.get("calibration_target") == []
        run_rows[key] = {
            "run_id": RUN_IDS[key],
            "E_ns_exact": str(e_value),
            "cct_ns_exact": str(cct),
            "cct_over_sol_exact": str(cct / GF11_SOL_R2),
            "cct_over_sol_float": float(cct / GF11_SOL_R2),
            "delta_vs_sol_pct": pct((cct - GF11_SOL_R2) / GF11_SOL_R2),
        }

    # the decomposition check (the anchor's own equation, verified here).
    assert GF11_SOL_R2 == Fraction(1404)

    # r=4 sweep rows: cross-check + assemble the bracket table.
    rows = sweep_rows(SWEEP_ID_GF11_TP4)
    bracket = {}
    for row in rows:
        identity = IDENTITY_NAME[row["algorithm"]]
        topo = row["config_id"].split("-")[2]
        e_value = topo_e_from_id(topo)
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        payload = row["payload_bytes"]
        assert payload == 128
        assert cct == closed_form(identity, payload, 4, e_value), (topo, cct)
        bracket[(identity, e_value)] = cct

    def entry(cct: Fraction, target: Fraction) -> dict:
        return {
            "cct_ns_exact": str(cct),
            "ratio_over_target_exact": str(cct / target),
            "ratio_over_target_float": float(cct / target),
            "delta_pct": pct((cct - target) / target),
        }

    table = {}
    for e_label, e_value in (("a10_e600", E_FITS["a10_e600"]), ("gf10_e8800", E_FITS["gf10_e8800"])):
        table[e_label] = {
            identity: {
                "vs_nearopt_2370": entry(bracket[(identity, e_value)], GF11_NEAROPT_R4),
                "vs_nccl_11000": entry(bracket[(identity, e_value)], GF11_NCCL_R4),
            }
            for identity in ("crossbar", "ring", "exchange")
        }

    # implied effective E at the registry pair: solve each chain for E.
    def implied_e(identity: str, ranks: int, payload: int, measured: Fraction) -> Fraction:
        return measured - wire_ns(payload, ranks) - CHAIN[identity](ranks) * L_REG

    implied = {
        "r2_sol_crossbar": implied_e("crossbar", 2, 128, GF11_SOL_R2),          # 1002
        "r4_nearopt_crossbar": implied_e("crossbar", 4, 128, GF11_NEAROPT_R4),  # 1967
        "r4_nearopt_ring": implied_e("ring", 4, 128, GF11_NEAROPT_R4),          # 1167
        "r4_nearopt_exchange": implied_e("exchange", 4, 128, GF11_NEAROPT_R4),  # 1567
        "r4_nccl_crossbar": implied_e("crossbar", 4, 128, GF11_NCCL_R4),        # 10597 (above range)
        "r4_nccl_ring": implied_e("ring", 4, 128, GF11_NCCL_R4),                # 9797 (above range)
        "r4_nccl_exchange": implied_e("exchange", 4, 128, GF11_NCCL_R4),        # 10197 (above range)
    }
    assert implied["r2_sol_crossbar"] == Fraction(1002)
    assert implied["r4_nearopt_crossbar"] == Fraction(1967)

    in_range = [k for k, v in implied.items() if E_RANGE[0] <= v <= E_RANGE[1]]
    above_range = [k for k, v in implied.items() if v > E_RANGE[1]]

    return {
        "anchor": "GF-11 ('Achieving Near Speed-of-Light Latency in GPU Collectives', arXiv:2607.16100; GB200 NVL72 + 2/4-GPU GB200 microbenchmarks; staging anchors_gapfill.md section GF-11; confidence H; NCCL 2.29.1 / NVSHMEM 3.5.21 / MSCCL++ 0.8.0 pins)",
        "r2_decomposition_point": {
            "measured": "LL2 RTT 306 ns + remote store 792 ns close the anchor's own SoL equation 2*306+792 = 1404 EXACTLY (re-verified here, as in S6 v1)",
            "placements": {k: run_rows[k] for k in ("gf11_xbar2_e600", "gf11_xbar2_e8800")},
            "finding": "the A10 end-to-end placement (E=600) lands at 1002/1404 = 0.714 of the 2-GPU SoL (-28.6%); the GF-10 placement (E=8800, V100-era app-level P2P) OVERSHOOTS the current-gen SoL by 6.56x — the two fit-side software-inclusive anchors bracket the point from opposite sides with a 14.7x gap between them, and the decade between them is exactly where the point sits",
            "structure_caveat_unchanged": "the decomposition STRUCTURE (2 RTT + 1 store, asymmetric) still has no expression in the lumped symmetric 2L + E — the endpoint term adds a floor, not a component split (carried from S6 v1)",
        },
        "r4_bracket": {
            "measured": "small-message AllReduce on 4 GB200s at the declared 128-B reading — near-optimal one-shot 2370 ns vs stock NCCL 2.29.1 ring 11000 ns",
            "table": table,
            "finding": "at E=600 the three chains land 1003/1803/1403 ns (0.42-0.76x of the near-optimal leg; 0.09-0.16x of NCCL) — under-predicting; at E=8800 they land 9203/10003/9603 ns (3.9-4.2x the near-optimal leg; 0.84-0.91x of NCCL) — the V100-era figure approximately reproduces the CURRENT stock-NCCL leg (a generation-coincidence of software heaviness, not a validation: the same placement overshoots the near-optimal leg 4x on the same fabric)",
        },
        "implied_effective_E": {
            "definition": "solving each chain for E at the registry (B=64, L=200), wire term removed — declared diagnostics FROM the measurements; no run id; NOTHING is set to them",
            "per_point_exact": {k: str(v) for k, v in implied.items()},
            "per_point_float": {k: float(v) for k, v in implied.items()},
            "in_range_members": in_range,
            "above_range_members": above_range,
            "placement": "every near-optimal-leg implied E (1002-1967 ns across chains and rank counts) sits INSIDE the declared range [0, 9000] — the model CLASS now reaches the measured current-gen floor decade structurally — but the fit-side placements {0, 600, 8800} leave that whole 0.86-1.97 us window UNOCCUPIED; the NCCL-leg implied E (9797-10597) sits ABOVE the range upper the fit set itself defines",
        },
        "matched_fitted_configurations": {
            "configs": "the S4e endpoint-axis placements E in {0, 600, 8800} + the flagged 9000 alternative at B=64/L=200, on the three corpus identities at the anchor's rank counts r=2/4",
            "matching_basis": "the split record's OWN assignment — G3 parameter_axes: small-message O-CCT predicted from the (now endpoint-extended) axis and EXTERNALLY checked on the holdout; GF-11 is the regime-disjoint same-fabric instance (plan 3.5(c))",
        },
    }


# ---------------------------------------------------------------------------
# GF-01 evaluation.
# ---------------------------------------------------------------------------
def eval_gf01() -> dict:
    rows = sweep_rows(SWEEP_ID_GF01_SMALL)
    by = {}
    for row in rows:
        identity = IDENTITY_NAME[row["algorithm"]]
        topo = row["config_id"].split("-")[2]
        e_value = topo_e_from_id(topo)
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == closed_form(identity, row["payload_bytes"], 8, e_value), (topo, row["payload_bytes"])
        by[(identity, e_value, row["payload_bytes"])] = cct

    # placements vs the eager rows (ratio tables), on ring and crossbar.
    ratios = {}
    for identity in ("ring", "crossbar"):
        for e_label in ("wireclass_e0", "a10_e600", "gf10_e8800"):
            e_value = E_FITS[e_label]
            per_size = {}
            for size, measured in GF01_EAGER.items():
                cct = by[(identity, e_value, size)]
                per_size[str(size)] = {
                    "cct_ns_exact": str(cct),
                    "ratio_over_eager_exact": str(cct / measured),
                    "ratio_over_eager_float": float(cct / measured),
                }
            ratios[f"{identity}_{e_label}"] = per_size

    # implied effective E per size per identity (solve for E at registry pair).
    implied = {}
    for identity in ("ring", "crossbar", "exchange"):
        per_size = {}
        for size, measured in GF01_EAGER.items():
            e_implied = measured - wire_ns(size, 8) - CHAIN[identity](8) * L_REG
            per_size[str(size)] = e_implied
        implied[identity] = per_size
    ring_values = [v for v in implied["ring"].values()]
    xbar_values = [v for v in implied["crossbar"].values()]
    all_values = ring_values + xbar_values + [v for v in implied["exchange"].values()]

    # monotonicity: the model at fixed E is strictly monotone in size; the
    # measured eager series is not (v1's finding, restated on executed rows).
    e600_series = [by[("ring", E_FITS["a10_e600"], s)] for s in (8, 32, 64, 16384, 65536)]
    assert all(a < b for a, b in zip(e600_series, e600_series[1:])), "model rows must be monotone"

    return {
        "anchor": "GF-01 (AMD ROCm blog; RCCL 2.22.3/ROCm 6.3 all_reduce_perf on 8 MI300X, 7-hop full-mesh xGMI; staging anchors_gapfill.md section GF-01; confidence M-H)",
        "measured_band": "eager 16.61-16.74 us at 8-64 B and 13.54/13.77 us at 16/64 KiB (the reconciling rows; graph mode 16.38/6.32/9.14 us brackets software launch overhead — a pure software-stack effect)",
        "placement_ratios": ratios,
        "implied_effective_E": {
            "definition": "measured row - wire term - chain*L at the registry (B=64, L=200) — declared diagnostics FROM the measurements; no run id; NOTHING is set to them",
            "per_identity_per_size_exact": {k: {s: str(v) for s, v in per.items()} for k, per in implied.items()},
            "ring_band_exact": [str(min(ring_values)), str(max(ring_values))],
            "ring_band_float": [float(min(ring_values)), float(max(ring_values))],
            "crossbar_band_float": [float(min(xbar_values)), float(max(xbar_values))],
            "placement": "GF-01's whole eager band demands an implied E of "
            f"{float(min(all_values)):.0f}-{float(max(all_values)):.0f} ns across identities — "
            "ENTIRELY ABOVE the declared range upper 9000 (the fit-set anchor GF-10's own P2P figure "
            "defines that upper): the RCCL eager collective floor on MI300X exceeds even the "
            "V100-era app-level P2P figure by 1.02-1.82x; NO in-range E reproduces this floor on ANY identity",
        },
        "findings": {
            "closest_landing_and_its_status": "the closest fit-side landing is the GF-10 placement on the ring at 16 KiB: 12048 vs 13540 ns = 0.890 (-11.0%) — a V100-era P2P figure landing near an MI300X RCCL eager AllReduce floor is a cross-stack magnitude coincidence, NOT a validation (the same placement overshoots the GB200 near-optimal leg 4x, the r4 bracket above)",
            "underprediction_persists_at_a10": "the A10 end-to-end placement (600) under-predicts the eager band 0.09-0.28x across identities and sizes — the assumption-class figure is software-free and it shows",
            "non_monotone_floor_inexpressible": "the measured eager series is NON-monotone in size (t(8 B)=16610 > t(16 KiB)=13540) while every fixed-(B, L, E) identity is strictly monotone (asserted on the executed rows) — an expressiveness limit of the affine-plus-floor family, not a parameter mismatch (carried from S6 v1, unchanged by the endpoint term)",
            "fabric_class_caveat": "the full-mesh class is OUT-OF-DOMAIN for the single-port abstraction (A-L0X-PORT) — carried from S6 v1; the crossbar rows are structure-inadmissible here for the same reason, the ring rows remain the in-domain reading",
        },
    }


# ---------------------------------------------------------------------------
# GF-03 evaluation (arithmetic context, as in S6 v1).
# ---------------------------------------------------------------------------
def eval_gf03() -> dict:
    # pair reading: a D2D access is one pair traversal + one endpoint.
    implied = {str(v): v - L_REG for v in GF03_D2D}
    assert implied["1400"] == Fraction(1200) and implied["1600"] == Fraction(1400)
    return {
        "anchor": "GF-03 (B300/Blackwell-Ultra-class practitioner data, confidence M — a noisy external point, recorded as such; staging anchors_gapfill.md section GF-03)",
        "d2d_points": {
            "measured": "device-to-device latency ~1.4-1.6 us",
            "implied_E_pair_reading_exact": {k: str(v) for k, v in implied.items()},
            "placement": "both implied E (1200 / 1400 ns) sit INSIDE the declared range and INSIDE the same 1.0-2.0 us window GF-11's near-optimal legs demand — a THIRD independent fabric generation pointing at the same unoccupied window; in-range, unreached by any fit-side placement",
        },
        "midsize_row_carried": "the 2 MiB AllReduce row (42-52 us) is the size-dependent software-effective-bandwidth axis finding (the v0.2 proposal's axis 1), carried UNCHANGED — the endpoint term does not address wire-dominated rows, and at registry B the row is wire-dominated",
    }


# ---------------------------------------------------------------------------
# Cross-anchor observations and the sharpened falsification.
# ---------------------------------------------------------------------------
def cross_anchor() -> dict:
    decade = [Fraction(1002), Fraction(1967)]  # GF-11 near-opt legs, crossbar r2/r4
    return {
        "the_implied_E_table": (
            "at the registry pair (B=64, L=200), the holdout small-message rows imply: "
            "GF-11 near-optimal legs 1002-1967 ns (crossbar r2/r4; 1167/1567 on the ring/exchange chains), "
            "GF-03 D2D 1200/1400 ns, GF-11 NCCL leg 9797-10597 ns, GF-01 eager band 9178-16339 ns "
            "(the lowest GF-01 demand is the 64 KiB ring row 9178)"
        ),
        "what_the_term_earned": (
            "the model CLASS now reaches the measured current-generation small-message floor window "
            "(~1.0-2.0 us implied E): every near-optimal-leg and D2D implied value sits INSIDE the declared "
            "range [0, 9000] — where S4 v1 proved the wire-class axis could not reach the floor at ANY "
            "in-range placement, the endpoint-extended class can. The structural omission is FIXED"
        ),
        "the_sharpened_falsification": [
            "1. UNOCCUPIED WINDOW (the evidential gap): the fit-side placements span E in {0, 600, 8800}; "
            "the window the current-gen holdouts demand (1002-1967 ns) lies between 600 and 8800 with NO "
            "fit-side anchor inside it — the fit set stages NO current-generation software/endpoint "
            "measurement (its only measured software-inclusive figure, GF-10, is V100-era DGX-1 app-level "
            "P2P; the current-gen decompositions live in HOLDOUT anchors, which the immutable split "
            "rightly forbids as fit inputs). The gap is no longer structural but EVIDENTIAL: it cannot be "
            "closed by model work, only by a new fit-side anchor (a future split's business, never this one)",
            "2. RANGE-TOP CHALLENGE (the anchors disagree with each other): GF-01's RCCL eager collective "
            "floor demands implied E 9178-16339 ns — ABOVE the declared range upper 9000 that GF-10's own "
            "figure defines — while GF-11's NCCL leg demands 9797-10597 (also above). Across the corpus the "
            "software-inclusive magnitude spans ~10x (SoL 1.4 us to eager 16.7 us): a single uniform E with "
            "one range cannot serve RCCL-eager, stock-NCCL and near-optimal stacks simultaneously — the "
            "anchors demand a software-stack/generation AXIS on the endpoint term (the E-side sibling of "
            "S3's software-version axis), which the model still lacks",
            "3. SHAPE DEMANDS UNCHANGED (carried): the lumped symmetric 2L + E cannot express GF-11's "
            "asymmetric decomposition (2x306 RTT + 792 store); the affine-plus-floor response cannot "
            "express GF-01's non-monotone eager band or a flat-then-rising transition; uniform E cannot "
            "express pair heterogeneity — all carried from S6 v1 unchanged by this term",
        ],
        "generation_span_statement": (
            "the three decades the corpus measures — near-optimal current-gen ~1.0-2.0 us, stock-NCCL "
            "current-gen ~10.5 us, RCCL-eager current-gen ~13.5-16.7 us, V100-era app-P2P 9 us — overlap "
            "across generations and stacks: generation alone does not order them, the software stack does"
        ),
    }


def evidence_dimensions_block() -> dict:
    return {
        "verification": [
            {
                "check": "tests/calibration/test_s6e_holdout.py",
                "scope": "S6e holdout guard — re-executes the stage's evidence chain (two sweeps, two runs) into a scratch store and rebuilds this record byte-identically, checking the nothing-tunes invariants (every executed row equals its closed form; both runs held_out TRUE with calibration_target []; the fit-side placements carried bit-exact from the S4e record)",
            },
            {
                "check": "tests/calibration/test_s4e_fit.py",
                "scope": "the fit-side record's own guard — the placements this stage evaluates",
            },
        ],
        "calibration_target": [],
        "held_out": {
            "held_out": True,
            "scope": "evaluation-only against the split record's small-message-axis holdout members (GF-01 small rows, GF-11, GF-03): every measured row here is an evaluation target; no holdout number enters any fit objective, swept value, or tolerance; the implied_effective_E diagnostics are declared FROM the measurements and nothing is set to them",
        },
        "independent_reproduction": [],
        "known_omissions": [
            "no fit-side anchor stages a current-generation software/endpoint measurement — the demanded E window (1002-1967 ns) is unoccupied by the fit set; closable only by a new fit-side anchor through a future split record, never by tuning",
            "a single uniform E cannot express the ~10x software-stack spread the corpus measures (near-optimal vs stock-NCCL vs RCCL-eager); the endpoints demand a software-stack/generation axis the model lacks",
            "the lumped symmetric 2L + E cannot express measured asymmetric decompositions (GF-11 2x306+792); affine-plus-floor cannot express non-monotone eager floors (GF-01) or flat-then-rising transitions; uniform E cannot express per-pair heterogeneity (GF-10 manual routing)",
            "the full-mesh fabric class stays OUT-OF-DOMAIN for the single-port abstraction (A-L0X-PORT) — the crossbar GF-01 rows are structure-inadmissible; ring rows are the in-domain reading",
            "the torus identity carries no endpoint term (A-L0E-CHG applicability); no torus row exists in this evaluation",
            "no congestion, no credit flow control, no packetization, no multi-port injection, no in-network reduction (analytical L0 transport model only)",
        ],
    }


def build_record() -> dict:
    evidence = evidence_dimensions_block()
    record = {
        "record_kind": "calibration_holdout_evaluation",
        "stage": "calibration holdout-evaluation record, S6e (the small-message-axis rerun of the S6 external check under the same immutable split)",
        "status": "PROPOSED — owner adjudication required; this record evaluates fitted placements against holdout anchors and changes no label, registry value, or claim",
        "evidence_schema_version": 2,
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay reproduces byte-identical artifacts)",
            "evaluation": "PROPOSED holdout evaluation of fit-side placements against external published measurements; no E3/E4 language — none of the anchors is our testbed, and owner adjudication precedes any label move",
        },
        "calibration_target": [],
        "held_out": evidence["held_out"],
        "split_record": {
            "record_id": "3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20",
            "committed_copy": "experiments/calibration/split/anchor_split_v1.json",
            "holdout_members_evaluated": "the split record's small-message-axis holdout members: GF-01 (small rows), GF-11, GF-03 (latency points; the 2 MiB row carried as the mid-size axis); CAL-A4 and GF-06 are NOT this axis's members and are not evaluated here",
            "no_leakage": "no holdout number entered any S4e fit objective, swept value, or tolerance (mechanically asserted there: no holdout anchor id in that record's bytes); this record is the sanctioned evaluation-only use",
        },
        "fitted_configurations_evaluated": {
            "source": "the S4e fit record d91aaf874b983a684a230babe59a38c7ee6c2b5bc88cc39340ddfe481145c8c8 (committed at experiments/calibration/s4e/fit_record_v1.json)",
            "placements": {
                "wireclass_e0": "E = 0 (the registry origin; the landed v1 world in numbers)",
                "a10_e600": "E = 600 (CAL-A10 assumption-class end-to-end reading)",
                "gf10_e8800": "E = 8800 (GF-10 measured V100-era app-level P2P, primary pair reading)",
                "gf10_alt_e9000_flagged": "E = 9000 (flagged whole-figure alternative; carried, never selected — it changes no verdict here: at these rows it shifts predictions by +200 ns)",
            },
            "fixed_pair": "B = 64 and L = 200 at their UNCHANGED registry points on every row",
        },
        "evaluation": {
            "gf11": eval_gf11(),
            "gf01": eval_gf01(),
            "gf03": eval_gf03(),
        },
        "cross_anchor_observations": cross_anchor(),
        "nothing_tuned": "every model-side number in this record is an executed artifact at placements carried bit-exact from the S4e fit record; the implied_effective_E values are declared diagnostics solved FROM the measured rows at the registry pair — no parameter is set to any of them, no range is moved, no anchor output is targeted; the A-L0E-LAT registry value stays 0 and the wire-latency registry values stay 200",
        "verification": evidence["verification"],
        "known_omissions": evidence["known_omissions"],
        "independent_reproduction": evidence["independent_reproduction"],
        "backing": {
            "run_ids": [RUN_IDS[k] for k in RUN_IDS],
            "run_roles": {RUN_IDS[k]: RUN_ROLES[k] for k in RUN_ROLES},
            "sweep_ids": [SWEEP_ID_GF11_TP4, SWEEP_ID_GF01_SMALL],
            "inputs": [
                "experiments/calibration/s6e/sweep_s6e_gf11_tp4_v1.yaml",
                "experiments/calibration/s6e/sweep_s6e_gf01_small_v1.yaml",
                "experiments/calibration/s6e/run_s6e_gf11_eval_xbar2_e600.yaml",
                "experiments/calibration/s6e/run_s6e_gf11_eval_xbar2_e8800.yaml",
                "experiments/calibration/s6e/topologies/ (8 files)",
                "experiments/calibration/s6e/profiles/ (1 file)",
                "experiments/calibration/s4e/topologies/ (the r=8 e0/e600/e8800 rows, committed reuse)",
                "experiments/calibration/gf11/workloads/w1_dense_tp_decode_tp{2,4}_128b.yaml (committed anchor workloads)",
                "experiments/calibration/s4e/fit_record_v1.json (the placements under evaluation)",
                "experiments/calibration/s6/holdout_record_v1.json (89f6256b... — the v1 holdout record, the staged measured rows' committed transcription source)",
            ],
            "reproduce": "make sweep EXP=experiments/calibration/s6e/sweep_s6e_gf11_tp4_v1.yaml ; make sweep EXP=experiments/calibration/s6e/sweep_s6e_gf01_small_v1.yaml ; make run EXP=(each of the two run_s6e_*.yaml manifests) ; python experiments/calibration/s6e/build_holdout_record.py",
        },
        "headline": (
            "the endpoint term made the measured current-gen floor window REACHABLE (every near-optimal-leg implied E 1002-1967 ns sits in range — the S4 v1 structural impossibility is gone), but the window is UNOCCUPIED: the fit-side placements {0, 600, 8800} bracket it from both sides with no anchor inside (the only measured software-inclusive fit anchor is V100-era; the current-gen figures are holdout, and stay holdout). "
            "GF-10's placement reproduces the stock-NCCL leg of the GB200 bracket (0.84-0.91x, a generation-coincidence of software heaviness) while overshooting the near-optimal leg 4x on the same fabric and under-predicting GF-01's eager floor; GF-01's whole eager band demands implied E 9178-16339 ns — ABOVE the range top GF-10 itself defines: the anchors demand a software-stack/generation axis on the endpoint term (~10x spread across stacks), which the model still lacks. "
            "THE DELIVERABLE IS THE SHARPENED FALSIFICATION (cross_anchor_observations): structural omission FIXED; evidential gap (no current-gen fit-side anchor) and software-stack axis REMAIN; shape demands (asymmetric decomposition, non-monotone floor) carried unchanged"
        ),
    }
    return record


def main() -> int:
    record = build_record()
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    record_id = hashlib.sha256(record_bytes).hexdigest()

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

    if COMMITTED_COPY.exists():
        if COMMITTED_COPY.read_bytes() != record_bytes:
            print(
                f"ERROR: committed copy {COMMITTED_COPY} differs from the "
                "rebuilt record — this record is immutable; record a NEW "
                "record (holdout_record_v2) instead of editing",
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
