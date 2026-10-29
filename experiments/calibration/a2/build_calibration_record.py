"""Build the PROPOSED calibration-candidate record for anchor CAL-A2 (Q1
calibration stage A2.

Pure function of immutable artifacts: reads the two append-only store run
records and the sweep table produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record, mirroring the evidence-store
addressing discipline; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_staging.md`` §A2
(declared below with provenance; the staging doc paraphrases the product
page, so no "verbatim" quote strings are claimed here), or (b) computed
from the stored run/sweep artifacts by this script, or (c) anchor-anchor
arithmetic in the normalization demonstration (CAL-A3 staged busbw vs the
CAL-A2 line; no model run backs those rows and none is claimed). Nothing
is tuned: the swept B values carry their anchor provenance, and the record
measures where the model output sits relative to the anchor.

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
RUN_ID_CEIL900 = "723fb89f0d13db7a0589a9acfbf347232f2fcfd0f27f0a1a9474217f7677528e"
RUN_ID_DER720 = "2a34a2012733e1c81088227963532671b7c3402c0b289e8d7ccf98241794765e"
SWEEP_ID = "a6d27226c8b9366e9cc5df9bc94bf62538a6722b18569ff16d6b1af7ccdab807"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A2 staged numbers (docs/calibration/anchors_staging.md §A2,
# transcription confidence H; SPEC, not measurement — ceiling only; the
# staging doc states the per-direction split for the per-GPU figure and
# flags it as an interpretation risk if quoted as measured).
# Decimal unit convention of the calibration plan: 1 GB/s = 1 B/ns,
# 1 TB/s = 1000 GB/s.
A2_PER_GPU_BIDIRECTIONAL_TBPS = Fraction("1.8")
A2_RACK_AGGREGATE_BIDIRECTIONAL_TBPS = Fraction("130")
A2_GPUS_PER_RACK = 72
TBPS_TO_GBPS = Fraction(1000)
GBPS_TO_B_PER_NS = Fraction(1)  # decimal: 1 GB/s = 1 B/ns

# CAL-A3 staged out-of-place busbw series (docs/calibration/
# anchors_staging.md §A3, GB/s, measured, NCCL 2.28.3 on 72 GPUs) — used
# ONLY as the normalization-line demonstration (the plan's stated role for
# CAL-A2); the CCT comparison against CAL-A3 belongs to stage A3.
A3_STAGED_OUT_OF_PLACE_BUSBW_GBPS = {
    "2GiB": Fraction("787.95"),
    "4GiB": Fraction("831.03"),
    "8GiB": Fraction("866.36"),
    "16GiB": Fraction("890.32"),
    "32GiB": Fraction("906.94"),
}
A3_STAGED_AVG_BUSBW_GBPS = Fraction("855.949")


def anchor_derived() -> dict:
    """Arithmetic consequences of CAL-A2's own staged numbers (other
    anchors appear only in labeled cross-anchor notes/demonstrations)."""
    per_gpu_per_direction = (
        A2_PER_GPU_BIDIRECTIONAL_TBPS * TBPS_TO_GBPS / 2 * GBPS_TO_B_PER_NS
    )  # 900 B/ns (staging doc states the bidirectional -> per-direction split)
    aggregate_exact_bidirectional_TBps = (
        Fraction(A2_GPUS_PER_RACK) * A2_PER_GPU_BIDIRECTIONAL_TBPS
    )  # 129.6 TB/s
    aggregate_exact_per_direction = (
        aggregate_exact_bidirectional_TBps * TBPS_TO_GBPS / 2
    )  # 64800 B/ns
    aggregate_quoted_per_direction = (
        A2_RACK_AGGREGATE_BIDIRECTIONAL_TBPS * TBPS_TO_GBPS / 2
    )  # 65000 B/ns
    rounding_ratio = (
        A2_RACK_AGGREGATE_BIDIRECTIONAL_TBPS / aggregate_exact_bidirectional_TBps
    )  # 325/324
    per_gpu_implied_by_quoted_aggregate = (
        A2_RACK_AGGREGATE_BIDIRECTIONAL_TBPS / A2_GPUS_PER_RACK
    )  # 65/36 = 1.80555... TB/s bidirectional

    # Self-checks: the staged numbers must produce these exact integers /
    # ratios; anything else is a transcription bug, not a finding.
    assert per_gpu_per_direction == 900, per_gpu_per_direction
    assert aggregate_exact_bidirectional_TBps == Fraction("129.6")
    assert aggregate_exact_per_direction == 64800, aggregate_exact_per_direction
    assert aggregate_quoted_per_direction == 65000
    assert rounding_ratio == Fraction(325, 324), rounding_ratio
    assert per_gpu_implied_by_quoted_aggregate == Fraction(65, 36)

    return {
        "staged_numbers": {
            "per_gpu_nvlink_bidirectional_TB_per_s": "1.8",
            "rack_aggregate_nvlink_bidirectional_TB_per_s": "130",
            "split_note": "staging doc states the split: '= 900 GB/s per direction'; "
            "flagged there as an interpretation risk if quoted as measured",
        },
        "derived_arithmetic": {
            "per_gpu_per_direction_bytes_per_ns": str(per_gpu_per_direction),
            "aggregate_exact_bidirectional_TB_per_s": str(
                aggregate_exact_bidirectional_TBps
            ),
            "aggregate_exact_per_direction_bytes_per_ns": str(
                aggregate_exact_per_direction
            ),
            "aggregate_quoted_per_direction_bytes_per_ns": str(
                aggregate_quoted_per_direction
            ),
            "quote_rounding_ratio_quoted_over_exact": str(rounding_ratio),
            "per_gpu_bidirectional_implied_by_quoted_aggregate_TB_per_s": str(
                per_gpu_implied_by_quoted_aggregate
            ),
        },
        "quote_consistency_finding": {
            "delta_tbps": str(
                A2_RACK_AGGREGATE_BIDIRECTIONAL_TBPS
                - aggregate_exact_bidirectional_TBps
            ),
            "relative_excess_pct_float": float((rounding_ratio - 1) * 100),
            "note": "The anchor's own two quotes agree only up to rounding: reading "
            "130 TB/s as exact implies 1.8055... TB/s per GPU bidirectional, above "
            "the quoted 1.8 TB/s. Normalization fractions shift by the same "
            "+0.3086% depending on which quote defines the line (900 vs 902.78 B/ns "
            "per direction) — recorded, not smoothed; the stage uses the per-GPU "
            "quote's exact 900 as the line and reports the 65000-vs-64800 delta "
            "below.",
        },
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


CEILING = Fraction(900)  # CAL-A2 per-GPU per-direction line used throughout


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    wire = Fraction(per_op["per_rank_wire_bytes_exact"])
    busbw = wire / cct  # NCCL busbw convention: 2(r-1)/r * M / t
    fraction = busbw / CEILING
    model = obs["model"]
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": model["ranks"],
            "injection_bytes_per_ns_exact": model["injection_bytes_per_ns_exact"],
            "pair_latency_ns_exact": model["pair_latency_ns_exact"],
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "implied_busbw_bytes_per_ns_exact": str(busbw),
        "implied_busbw_bytes_per_ns_float": float(busbw),
        "anchor_ceiling_bytes_per_ns": str(CEILING),
        "fraction_of_ceiling_exact": str(fraction),
        "fraction_of_ceiling_float": float(fraction),
        "absolute_delta_busbw_minus_ceiling_exact": str(busbw - CEILING),
    }


def normalization_demonstration() -> dict:
    """The anchor's plan-defined role applied to the anchor set's own
    staged numbers: CAL-A3's measured out-of-place busbw vs the CAL-A2
    900 B/ns per-direction line. Pure anchor-anchor arithmetic — no model
    run backs these rows and none is claimed; the CCT comparison against
    CAL-A3 belongs to stage A3."""
    rows = []
    for size, busbw_gbps in A3_STAGED_OUT_OF_PLACE_BUSBW_GBPS.items():
        fraction = busbw_gbps / CEILING
        rows.append(
            {
                "size": size,
                "cal_a3_staged_busbw_GB_per_s": str(busbw_gbps),
                "fraction_of_cal_a2_line_exact": str(fraction),
                "fraction_of_cal_a2_line_float": float(fraction),
                "above_line": fraction > 1,
            }
        )
    avg_fraction = A3_STAGED_AVG_BUSBW_GBPS / CEILING
    above = [r["size"] for r in rows if r["above_line"]]
    return {
        "role": "normalization line demonstration (CALIBRATION_PLAN.md §1.1 CAL-A2: "
        "'Injection-BW ceiling that every measured fraction (e.g. CAL-A3 busbw) is "
        "normalized against')",
        "line_bytes_per_ns": "900",
        "rows": rows,
        "avg_fraction_of_line_exact": str(avg_fraction),
        "avg_fraction_of_line_float": float(avg_fraction),
        "above_line_sizes": above,
        "interpretation_note": "The 32 GiB out-of-place point (906.94 GB/s busbw) "
        "sits +0.77% ABOVE the derived per-direction line. This is recorded as an "
        "interpretation flag, exactly the risks the staging doc names: (a) the "
        "per-direction 900 is a derived split of the bidirectional quote, (b) the "
        "NVLink-vs-IB path split of that run is unstated (§A3 caveat), (c) busbw "
        "carries the 2(r-1)/r accounting factor. Classification belongs to stage "
        "A3 (minimize then classify per handoff rule 5); nothing here is tuned "
        "and no ceiling is claimed violated — the line itself is a derived "
        "reading of a marketing spec.",
        "provenance": "CAL-A3 staged numbers, anchors_staging.md §A3 (measured, "
        "NCCL 2.28.3 / CUDA 12.9.1, 72 GPUs, out-of-place; confidence M-H); "
        "anchor-anchor arithmetic only, no run ids by construction",
    }


def sweep_comparison() -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    b_by_topology = {
        "crossbar72_a2_span448_v1": Fraction(448),
        "crossbar72_a2_derated720_v1": Fraction(720),
        "crossbar72_a2_ceiling900_v1": Fraction(900),
    }
    by_size: dict[int, list[dict]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        size = row["payload_bytes"]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        busbw = wire / cct
        b = b_by_topology[topo]
        by_size.setdefault(size, []).append(
            {
                "topology_id": topo,
                "config_id": row["config_id"],
                "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
                "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
                "delta_vs_anchor_point_exact": row["delta_vs_baseline"]["delta_exact"],
                "delta_vs_anchor_point_float": row["delta_vs_baseline"]["delta_float"],
                "implied_busbw_bytes_per_ns_exact": str(busbw),
                "fraction_of_cal_a2_line_exact": str(busbw / CEILING),
                "fraction_of_cal_a2_line_float": float(busbw / CEILING),
                "asymptotic_fraction_b_over_900_exact": str(b / CEILING),
            }
        )
    ladder = [
        {
            "payload_bytes": size,
            "rows": sorted(
                entries, key=lambda e: -Fraction(e["implied_busbw_bytes_per_ns_exact"])
            ),
        }
        for size, entries in sorted(by_size.items())
    ]
    return {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "crossbar72_a2_ceiling900_v1 (the CAL-A2 anchor point; delta "
        "columns measure placement vs it)",
        "message_size_ladder": ladder,
    }


def main() -> int:
    derived = anchor_derived()

    # Fabric-aggregate consistency: the model at the anchor point (B=900,
    # r=72) implies a per-direction fabric aggregate that must be checked
    # against BOTH readings of the anchor's aggregate quote.
    aggregate_checks = [
        {
            "reading": "exact (per-GPU quote x 72): 72 x 1.8 TB/s bidir = 129.6",
            "model_implied_fabric_per_direction_bytes_per_ns": str(72 * 900),
            "anchor_aggregate_per_direction_bytes_per_ns": "64800",
            "exact_match": True,
        },
        {
            "reading": "quoted aggregate (130 TB/s bidir => 65000 B/ns per dir)",
            "model_implied_fabric_per_direction_bytes_per_ns": str(72 * 900),
            "anchor_aggregate_per_direction_bytes_per_ns": "65000",
            "exact_match": False,
            "delta_bytes_per_ns_exact": str(Fraction(72 * 900) - 65000),
            "ratio_exact": str(Fraction(72 * 900, 65000)),
            "ratio_float": float(Fraction(72 * 900, 65000)),
            "note": "-200 B/ns = the quote-rounding gap (324/325); a property of "
            "the anchor's rounded 130 vs its own per-GPU arithmetic, not of the "
            "model.",
        },
    ]

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A2 (anchor CAL-A2)",
        "anchor": {
            "anchor_id": "CAL-A2",
            "title": "NVIDIA GB200 NVL72 product page: per-GPU and aggregate NVLink bandwidth",
            "source_row": "the anchor registry row CAL-A2 (PROPOSED)",
            "staging_doc": "docs/calibration/anchors_staging.md §A2",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A2",
            "url": "https://www.nvidia.com/en-us/data-center/gb200-nvl72/",
            "confidence": "H for transcription; SPEC, not measurement — ceiling only, "
            "never an achieved value; the per-direction 900 GB/s is the staging "
            "doc's stated split of the bidirectional quote (interpretation risk if "
            "quoted as measured)",
            "staged_numbers": "1.8 TB/s bidirectional NVLink bandwidth per GPU "
            "(= 900 GB/s per direction); 130 TB/s aggregate NVLink GPU-to-GPU "
            "across the rack — numbers as staged in anchors_staging.md §A2 "
            "(staging-doc transcription; no verbatim product-page quote strings "
            "are claimed by this record)",
        },
        "target": {
            "role": "injection_bw_ceiling_and_normalization_line",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "CAL-A2 is a capacity specification, "
            "not a (size -> time) series; a CCT deviation is undefined against it "
            "(CALIBRATION_PLAN.md §1.1: 'Cannot calibrate O-CCT — specification. "
            "Injection-BW ceiling that every measured fraction (e.g. CAL-A3 busbw) "
            "is normalized against'). The anchor's extractable targets are the "
            "per-GPU per-direction injection ceiling (900 B/ns), the aggregate "
            "ceiling (129.6 exact / 130 quoted TB/s bidirectional), and the "
            "normalization line they define — all recorded here.",
            "regime": {
                "topology_class": "fully_connected_crossbar (L0 abstraction of the NVSwitch fat-tree class)",
                "ranks": 72,
                "message_bytes_ladder": [73728, 294912, 1179648, 4718592, 18874368,
                                         75497472, 301989888, 1207959552, 2415919104,
                                         4831838208, 19327352832, 77309411328],
                "message_regime_note": "n/a (capacity spec); ladder spans latency-bound "
                "(72 KiB) to bandwidth-bound (72 GiB), identical to stage A1's grid "
                "for cross-stage comparability; every size divisible by 72 (A-L0X-DIV)",
            },
        },
        "anchor_derived": derived,
        "model": {
            "backend_id": "analytical_l0_crossbar",
            "identity": "t = 2*(r-1)/r * M/B + 2*L ; per-rank wire bytes = 2*(r-1)/r * M",
            "ranks": 72,
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "448": "aggregate-span lower endpoint (CAL-A7-derived MI300X "
                    "class: 7 links x 64 B/ns per direction)",
                    "720": "CAL-A2 ceiling 900 x CAL-A12 ~80% software derating "
                    "(the spec-to-measured bridge the plan §1.1 CAL-A12 row makes "
                    "mandatory)",
                    "900": "CAL-A2 per-GPU per-direction ceiling (anchor point of "
                    "this stage)",
                },
                "L_pair_latency_ns": 200,
                "L_provenance": "A-L0X-LAT registry point (KEEP per plan §2.1); latency axis deferred to its own global stage",
            },
            "assumptions": "A-L0X-PORT single-port injection, A-L0X-LAT, A-L0X-DIV (experiments/vertical_slice/assumptions_l0.yaml)",
        },
        "comparison": {
            "fabric_aggregate_consistency": aggregate_checks,
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_CEIL900,
                    "ceiling (B=900: the CAL-A2 per-GPU per-direction line itself)",
                ),
                run_summary(
                    RUN_ID_DER720,
                    "derated (B=720 = 0.8 x 900: the CAL-A12 software-effective bridge)",
                ),
            ],
            "normalization_line_demonstration": normalization_demonstration(),
            "reconciled_sweep": sweep_comparison(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — the anchor publishes no "
            "time series; recorded per the stage's FAIL-clause duty instead of skipped "
            "because the anchor's actual role (injection ceiling + normalization "
            "line) IS extractable and is executed above.",
            "injection_ceiling_utilization_summary": "The identity's implied busbw "
            "sits strictly below the 900 B/ns line at every finite size and "
            "converges to exactly 1.0 algebraically as size grows (the +2L latency "
            "term vanishes); at the derated point it converges to exactly 0.8 — "
            "by construction of that swept point (0.8 x 900), which locates where "
            "a CAL-A12-style software-scheduled measurement would sit, NOT an "
            "independent validation of the derating.",
            "span_placement": "CCT ratios vs the anchor point are arithmetic facts "
            "of 1/B (asymptotically exactly +0.25 at B=720 and +113/112 = "
            "+1.008928... at B=448; the sweep table records the exact per-size "
            "values including the latency term).",
            "quote_rounding_finding": "See anchor_derived.quote_consistency_finding: "
            "the anchor's two quotes are mutually consistent only to rounding "
            "(+1/324 = +0.3086%); which quote defines the line moves normalized "
            "fractions by the same 0.31% — far below CAL-A6's 5-8% software noise "
            "floor, recorded for completeness, never smoothed.",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified)",
            "candidate": "PROPOSED calibration candidate targeting the "
            "normalization role; no E3/E4 language — CAL-A2 is an external "
            "published specification, not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_CEIL900, RUN_ID_DER720],
            "sweep_id": SWEEP_ID,
            "sweep_dir": f"results/sweeps/{SWEEP_ID}",
            "run_backed_numbers": "every model output in comparison.anchor_point_runs "
            "and comparison.reconciled_sweep; comparison.normalization_line_demonstration "
            "is anchor-anchor arithmetic by construction (declared inline, no run ids "
            "claimed)",
            "inputs": [
                "experiments/calibration/a2/sweep_a2_injection_v1.yaml",
                "experiments/calibration/a2/run_a2_ceiling_v1.yaml",
                "experiments/calibration/a2/run_a2_derated_v1.yaml",
                "experiments/calibration/workloads/w1_dense_tp_decode_tp72.yaml",
                "experiments/calibration/a2/topologies/ (3 files)",
                "experiments/calibration/a2/profiles/implementation_profile_l0_crossbar_cal_a2_v1.yaml",
            ],
            "reproduce": "make run EXP=experiments/calibration/a2/run_a2_ceiling_v1.yaml ; "
            "make run EXP=experiments/calibration/a2/run_a2_derated_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a2/sweep_a2_injection_v1.yaml ; "
            "python experiments/calibration/a2/build_calibration_record.py",
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
