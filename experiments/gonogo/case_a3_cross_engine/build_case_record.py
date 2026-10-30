#!/usr/bin/env python3
"""Build the G7 leg-(a) motivation case record (exact, committed).

G7 go/no-go leg (a): reproduce ONE actual published comparison — anchor
CAL-A3, the plan's primary O-CCT calibration target (Crusoe Cloud GB200
NVL72 ``all_reduce_perf``, NCCL 2.28.3, 72 GPUs, 2-32 GiB per rank,
out-of-place; staged at docs/calibration/anchors_staging.md §A3; numbers
carried by the committed S2 fit record) — across TWO engines:

- engine A: essun L0 (in-process analytical identities; the
  fabric-matched crossbar view at the S2 B_fit diagnostic and the CAL-A2
  ceiling line, plus the RING twin at B=828), and
- engine B: ASTRA-sim analytical (the pinned external Docker engine
  4ce9ecfe..., congestion-unaware frontend, native Ring AllReduce).

The record audits, in exact Fractions, WHERE re-derivation of the
published comparison is underdetermined: the observable-definition
freedom (NCCL's busbw ring convention vs any wire-rate reading), the
algorithm freedom (the ring reading of the 32 GiB row implies per-GPU
egress 0.77% ABOVE the vendor per-direction line; the multicast reading
implies 51.1% — a factor 2(r-1)/r = 71/36 swing), the parameter freedom
(no single fixed B covers the series: -4.7% .. +9.6% at the S2 minimax
B_fit; even the 900 B/ns ceiling line is crossed), and the engine-level
freedoms (engine B's fitted optimum is not even representable in its
input convention: B_fit is non-integer and the adapter rejects non-dyadic
bandwidths by design; engine B's Wall observable bundles endpoint and
local-memory processing knobs the publication does not state — its twin
delta against the L0 ring identity at IDENTICAL inputs is +80.2% to
+118.1%).

Run inventory (content-addressed; results/ store, reproducing via the
committed manifests): 12 essun-L0 runs (5 crossbar B_fit, 2 crossbar
ceiling-900, 5 ring B=828) + 5 ASTRA-sim runs (ring B=828), all with v2
evidence dimensions, calibration_target [CAL-A3], split-record held_out
flags mirrored from S2.

Usage: ``.venv/bin/python experiments/gonogo/case_a3_cross_engine/build_case_record.py``
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_COPY = Path(__file__).resolve().parent / "case_record_v1.json"

RANKS = 72
RING_FACTOR = Fraction(2 * (RANKS - 1), RANKS)  # busbw = algbw * 2(r-1)/r
CEILING_LINE = Fraction(900)  # CAL-A2 per-GPU per-direction line (B/ns)
B_FIT = Fraction(19561820264071168, 23648730912675)  # S2 minimax diagnostic
B_TWIN = 828  # nearest ASTRA-representable integer above B_fit

# Anchor CAL-A3 staged numbers (docs/calibration/anchors_staging.md §A3,
# via the committed S2 fit record; confidence M-H; out-of-place series).
# Units: times in us (2-decimal publication rounding), busbw in GB/s
# decimal (1 GB/s == 1 B/ns exactly in the decimal convention).
PUBLISHED = {
    "2GiB": (2**31, "5375.10", "787.95", False),
    "4GiB": (2**32, "10193.01", "831.03", False),
    "8GiB": (2**33, "19555.07", "866.36", False),
    "16GiB": (2**34, "38056.60", "890.32", True),
    "32GiB": (2**35, "74718.41", "906.94", True),
}

# Executed runs (content-addressed ids from the local results/ store;
# the in-process L0 legs re-execute deterministically to the same ids —
# the guard test proves it; the ASTRA legs need Docker, reproducing via
# the committed manifests).
RUN_IDS = {
    ("l0x_fitb", "2GiB"): "814205157899023c81d9c4ae389ea999ba540317001c14d4f6d38f2576c13c5d",
    ("l0x_fitb", "4GiB"): "df3984790bd77001c30a3d3d2fc37ab7ad5cc8a1751b2afa51a79f5e1fa6cbc4",
    ("l0x_fitb", "8GiB"): "377becad758853611657acf5b900b4381553350ed5996a2f914260a39124fde2",
    ("l0x_fitb", "16GiB"): "a05af5225d0cc36c018cc2aaf3cb097a4525604b54227b4dfeec976e47cd52ef",
    ("l0x_fitb", "32GiB"): "a90f5cdd3e9efe292b6fe530506398a3e1a80ce83de4438c8d00958b4868518e",
    ("l0x_ceil900", "16GiB"): "6fdf1aad91da6edb41e95ddeeb8f8febbf6aac6a3f5adc77827a17b87c706e49",
    ("l0x_ceil900", "32GiB"): "131b1cabf73d8bd05631e099391d93e3e9fcaa86e77ba200bbd2430d9eec0f53",
    ("l0ring_b828", "2GiB"): "2e3b54e953b3e8dc8f7b59637ea4fd3cb5b5ced9c57fd4070433841509644c7b",
    ("l0ring_b828", "4GiB"): "bddc5ff768fb6c7572d5f6d98ad002fac599c753e0aa563af8e56a3dffd2afda",
    ("l0ring_b828", "8GiB"): "2e0ecb8d795e7f43ce711992448b3302d0e61f6cc23cc9711ec9c6d39dcb6ca7",
    ("l0ring_b828", "16GiB"): "d80f10199d8d33050abd9686a157dc6e63e35c3e4fc13a79f9214653bc0ab94e",
    ("l0ring_b828", "32GiB"): "afd865d0cba88066df991c6aa5d54277cb95987f368fa491ddf4acc995cdd5f0",
    ("astra_b828", "2GiB"): "8bcf3697dd731d1c47146ff59ad37c55c7e3b6358d6ed4b8eb414f1d19baf252",
    ("astra_b828", "4GiB"): "bde216093a09836fd5aae15d04704a190c1535d2bfa20dec00bac20e170f5f19",
    ("astra_b828", "8GiB"): "0906c3b869ce4f878a233d1e51093c52572545d9bb82629fcf28aecaf310d3aa",
    ("astra_b828", "16GiB"): "c69f128540cabeba00d072286d3717fb22d90284c728d8d9950a58e6f500cd22",
    ("astra_b828", "32GiB"): "39ea43357b47c192dd1d2ead799255c2fe9d6e6a1780227fa493f371a1b7e15b",
}

# Exact completion-time observations of the executed runs (the committed
# record's raw columns; constants so the record rebuilds byte-identically
# on a cold clone — ``main()`` verifies them against the local results/
# store when the copies exist, and the guard test re-executes the twelve
# in-process legs into a scratch store and checks the same values).
OBSERVED_EXACT = {
    ("l0x_fitb", "2GiB"): "705405959366175212275/137759297634304",
    ("l0x_fitb", "4GiB"): "1410756838662027615625/137759297634304",
    ("l0x_fitb", "8GiB"): "91014793459797820075/4443848310784",
    ("l0x_fitb", "16GiB"): "91013904690135663275/2221924155392",
    ("l0x_fitb", "32GiB"): "91013460305304584875/1110962077696",
    ("l0x_ceil900", "16GiB"): "8470719937/225",
    ("l0x_ceil900", "32GiB"): "16941349874/225",
    ("l0ring_b828", "2GiB"): "2129415031/414",
    ("l0ring_b828", "4GiB"): "4247072533/414",
    ("l0ring_b828", "8GiB"): "8482387537/414",
    ("l0ring_b828", "16GiB"): "8476508737/207",
    ("l0ring_b828", "32GiB"): "16947138674/207",
    ("astra_b828", "2GiB"): "11216448",
    ("astra_b828", "4GiB"): "20300472",
    ("astra_b828", "8GiB"): "38478744",
    ("astra_b828", "16GiB"): "74825064",
    ("astra_b828", "32GiB"): "147502368",
}

MANIFEST_FOR = {
    "l0x_fitb": "run_a3-l0x-fitb-{s}.yaml",
    "l0x_ceil900": "run_a3-l0x-ceil900-{s}.yaml",
    "l0ring_b828": "run_a3-l0ring-b828-{s}.yaml",
    "astra_b828": "run_a3-astra-b828-{s}.yaml",
}


def _read_observation(run_id: str) -> str:
    """Exact completion time from the local store copy (verification
    only; ``build()`` itself reads the constants so the record is
    store-independent)."""
    path = REPO_ROOT / "results" / run_id / "observations.json"
    if not path.is_file():
        return ""  # cold clone: nothing to verify against
    obs = json.loads(path.read_text(encoding="utf-8"))["observables"]["O-CCT"]
    if "per_op" in obs:
        return obs["per_op"][0]["completion_time_ns_exact"]
    if "completion_time_ns_mean_exact" in obs:  # essun L0 family aggregate
        return obs["completion_time_ns_mean_exact"]
    # ASTRA-sim: its Wall time is an integer ns parse (no exact-Fraction
    # form exists in that output; the integer IS exact).
    return str(obs["completion_time_ns"])


def _verify_against_store() -> list[str]:
    """Every run whose local store copy exists must agree with the
    recorded constant (a mismatch is an error, never a re-record)."""
    problems = []
    for (leg, size), run_id in RUN_IDS.items():
        observed = _read_observation(run_id)
        if observed and observed != OBSERVED_EXACT[(leg, size)]:
            problems.append(f"{leg} {size}: store {observed} != recorded constant")
    return problems


def build() -> dict:
    rows = []
    for size, (payload, t_us, busbw_pub, held_out) in PUBLISHED.items():
        t_ns = Fraction(t_us) * 1000  # publication rounds to 0.01 us
        algbw = Fraction(payload) / t_ns
        busbw_recomputed = algbw * RING_FACTOR
        row = {
            "size": size,
            "payload_bytes_exact": payload,
            "published_time_us": t_us,
            "published_busbw_gb_per_s": busbw_pub,
            "held_out_from_fit": held_out,
            "algbw_bytes_per_ns_exact": str(algbw),
            "busbw_recomputed_exact": str(busbw_recomputed),  # = algbw*2(r-1)/r
            "busbw_convention_check": {
                "convention": "busbw == algbw * 2*(r-1)/r (NCCL ring convention; 2(r-1)/r = 71/36 at r=72)",
                "recomputed_minus_published_exact": str(
                    busbw_recomputed - Fraction(busbw_pub)
                ),
                "note": (
                    "agrees to the publication's 2-decimal rounding at every "
                    "size — the published observable IS the ring-convention "
                    "quantity, not a wire-rate measurement"
                ),
            },
            "ceiling_audit": {
                "cal_a2_line_bytes_per_ns": "900",
                "ring_reading_pct_of_line_exact": str(
                    busbw_recomputed / CEILING_LINE * 100
                ),
                "multicast_reading_pct_of_line_exact": str(
                    algbw / CEILING_LINE * 100
                ),
                "algorithm_convention_swing_exact": str(RING_FACTOR),
            },
            "engines": {},
        }
        for leg in ("l0x_fitb", "l0x_ceil900", "l0ring_b828", "astra_b828"):
            run_id = RUN_IDS.get((leg, size))
            if run_id is None:
                continue
            observed = OBSERVED_EXACT[(leg, size)]
            exact = Fraction(observed)
            entry = {
                "run_id": run_id,
                "manifest": MANIFEST_FOR[leg].format(s=size.lower()),
                "completion_time_ns_exact": observed,
                "deviation_vs_published_pct_exact": str((exact / t_ns - 1) * 100),
            }
            if leg == "l0ring_b828":
                astra_obs = OBSERVED_EXACT[("astra_b828", size)]
                entry["twin_delta_astra_over_l0ring_pct_exact"] = str(
                    (Fraction(astra_obs) / exact - 1) * 100
                )
            row["engines"][leg] = entry
        rows.append(row)

    record = {
        "record_id": "gonogo-lega-case-a3-cross-engine-v1",
        "date": "2026-10-30",
        "program": "G7 go/no-go leg (a)",
        "status": "PROPOSED",
        "evidence_level": "E0/E1 (exact arithmetic + engine executions of free parameters against a published external measurement, compared CCT-vs-CCT as PROPOSED evidence; no tuning toward the anchor, no label upgrades)",
        "anchor": {
            "id": "CAL-A3",
            "citation": "docs/calibration/anchors_staging.md §A3 (Crusoe Cloud support article, public; numbers transcribed there with confidence M-H)",
            "series": "out-of-place all_reduce_perf, NCCL 2.28.3, 72 GPUs (18x4) of one GB200 NVL72 rack, 2-32 GiB per rank",
            "split_record_role": "fit_target_primary of group G1 (split record 3862e227...); the {16,32} GiB rows are within-series held-out from the fit (reported, never fitted)",
        },
        "engines": {
            "engine_a": "essun L0 (analytical_l0_crossbar at the S2 B_fit diagnostic and the CAL-A2 ceiling-900 line; analytical_l0 ring twin at B=828)",
            "engine_b": "ASTRA-sim analytical, pinned Docker 4ce9ecfe (essun/astra-sim-analytical:s1), native Ring AllReduce, congestion-unaware",
            "same_workload_bar": "identical workload bytes (floor-bracket payloads) and identical topology file (ring72_gonogo_b828_v1) for the twin legs; ASTRA observables are its Wall time only (no byte accounting)",
        },
        "parameter_provenance": {
            "B_fit_exact": str(B_FIT),
            "B_twin": B_TWIN,
            "b_twin_minus_b_fit_pct_exact": str((Fraction(B_TWIN) / B_FIT - 1) * 100),
            "representability": (
                "B_fit is NOT representable in engine B's input convention: "
                "the ASTRA adapter (A-AS1-BW-UNIT, 1 GB = 2^30 B) rejects "
                "any bandwidth whose GB/s decimal is non-finite — the exact "
                "fitted rational is refused by design, never silently "
                "rounded; the twin runs at the nearest admissible integer"
            ),
            "L_ns": 200,
            "L_provenance": "A-L0X-LAT / A-L0-LAT registry point; the publication states no latency",
        },
        "rows": rows,
        "audit_findings": {
            "observable_definition": (
                "The published busbw re-derives EXACTLY as algbw*2(r-1)/r "
                "(ring convention) at every size — it is an algorithm-"
                "convention quantity, not a wire-rate measurement. Read as "
                "per-GPU egress under the ring traffic identity it reaches "
                "100.77% of the CAL-A2 900 B/ns per-direction line at 32 GiB "
                "(and crosses 100% between 16 and 32 GiB); read under a "
                "multicast/in-network reduction identity the same number is "
                "51.10% of the line. The publication does not state the "
                "algorithm, so the fabric-utilization claim swings by the "
                "exact factor 2(r-1)/r = 71/36 = 1.9722."
            ),
            "parameter_freedom": (
                "No single fixed-B identity covers the series: at the S2 "
                "minimax B_fit (fitted on {2,4,8} GiB only) the deviations "
                "run -4.7% (2 GiB) to +9.6% (32 GiB held out) — the "
                "software-effective bandwidth ramps with size, which a "
                "fabric-parameter model cannot express by construction "
                "(the S2 known-omission finding, executed here for the "
                "record). Even the vendor ceiling line B=900 is CROSSED: "
                "at 32 GiB the ceiling-fixed identity is -0.77% off the "
                "published time — the published point is faster than the "
                "spec-ceiling fabric model, mirroring the busbw>900 "
                "crossing of the observable audit."
            ),
            "engine_freedom": (
                "Engine B's fitted optimum is not even expressible in its "
                "input convention (B_fit rejected as non-dyadic; twin at "
                "+0.0988% above it), and its completion observable bundles "
                "translation knobs with no counterpart in the publication: "
                "endpoint-delay 10 (A-AS2-DELAY-POS), local-mem-bw 1600 with "
                "per-bundle 3*size/local-mem-bw processing (A-AS2-MEM-BW), "
                "active-chunks-per-dimension 1 (A-AS1-CHUNKS-1). Against the "
                "essun L0 ring identity at IDENTICAL topology/workload "
                "bytes, engine B's Wall time is +80.2% (32 GiB) to +118.1% "
                "(2 GiB) higher — an exactly recorded engine-vs-engine "
                "disagreement of the same order as the algorithm-convention "
                "ambiguity itself."
            ),
            "omitted_assumptions": (
                "Publication-side quantities no engine can pin: the "
                "communicator's algorithm at each size (ring vs NVLS/tree), "
                "NCCL channel/SM configuration (the same article's in-place "
                "2 GiB row collapses to 5.20 GB/s — a 151x software-stack "
                "effect acknowledged in the source), warmup/iteration "
                "protocol, and the NVLink-vs-IB path split of the 72-GPU "
                "communicator (the article's own NCCL_IB_HCA guidance; "
                "staging caveat). None is standard-derived; each moves the "
                "re-derived number."
            ),
            "conclusion": (
                "The published comparison re-derives only as a JOINT "
                "(fabric-parameter, software-version, observable-convention) "
                "statement. Two engines sharing every declared parameter "
                "disagree with each other by 80-118% on completion time "
                "(observables differ by definition), and each misses the "
                "published series for reasons the publication cannot "
                "arbitrate. A comparison without executable observable "
                "definitions and declared assumptions is not re-derivable "
                "— this is the motivation case for the platform's "
                "observable registry and assumption ledgers."
            ),
        },
    }
    return record


def main() -> int:
    problems = _verify_against_store()
    if problems:
        print("ERROR: local store disagrees with the recorded constants:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    record = build()
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if COMMITTED_COPY.is_file():
        if COMMITTED_COPY.read_text(encoding="utf-8") == payload:
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            print(f"case_record_v1.json reproduces byte-identically ({digest[:12]}...)")
            return 0
        print(
            "ERROR: regenerated case record differs from the committed copy; "
            "a change requires a NEW record version (case_record_v2), never "
            "an edit",
            file=sys.stderr,
        )
        return 1
    COMMITTED_COPY.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(f"wrote case_record_v1.json ({digest[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
