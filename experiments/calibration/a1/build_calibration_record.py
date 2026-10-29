"""Build the PROPOSED calibration-candidate record for anchor CAL-A1 (Q1
calibration stage A1.

Pure function of immutable artifacts: reads the two append-only store run
records and the sweep table produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record, mirroring the evidence-store
addressing discipline; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed verbatim
from the anchor's published quotes (declared below with provenance), or
(b) computed from the stored run/sweep artifacts by this script. Nothing
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
RUN_ID_PORT50 = "2edd5a4879d913f3a246d8ee2f3e9abbe75662fc83c068a6328c1d94eb0d3b7a"
RUN_ID_AGG900 = "9e017859682cac26b1439268adc44b96c0c9a8657c8eb10746bdf8d1142e3a81"
SWEEP_ID = "577733fd4d1d0d25a5c2fdbb02ac9349dc7ea19842fa2646c5ed72c1e6430b7b"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A1 verbatim numbers (docs/calibration/anchors_staging.md §A1,
# transcribed from the NVIDIA DGX GB200/GB300 NVL72 User Guide; confidence
# H; SPEC, not measurement — ceiling only).
A1_FULL_DUPLEX_TBPS_PER_CHIP = Fraction("57.6")  # Tbps, full duplex, per NVLink5 switch chip
A1_PORTS_PER_CHIP = 72
A1_CHIPS_PER_TRAY = 2
A1_TRAYS_PER_RACK = 9
A1_GPUS_PER_RACK = 72

# Decimal unit convention of the calibration plan: 1 GB/s = 1 B/ns.
# 1 Tbps = 1000 Gbit/s = 125 GB/s (decimal, /8 bits per byte).
TBPS_TO_GBPS = Fraction(1000, 8)
GBPS_TO_B_PER_NS = Fraction(1)  # decimal: 1 GB/s = 1 B/ns


def anchor_derived() -> dict:
    """Arithmetic consequences of CAL-A1's own quoted numbers (no other
    anchor enters; cross-anchor coincidences are recorded as notes only)."""
    per_chip_full_duplex_GBps = A1_FULL_DUPLEX_TBPS_PER_CHIP * TBPS_TO_GBPS  # 7200
    per_chip_per_direction_GBps = per_chip_full_duplex_GBps / 2  # full duplex = both directions summed
    per_port_per_direction = (
        per_chip_per_direction_GBps * GBPS_TO_B_PER_NS / A1_PORTS_PER_CHIP
    )  # 50 B/ns
    chips_per_rack = A1_CHIPS_PER_TRAY * A1_TRAYS_PER_RACK  # 18
    ports_per_rack = chips_per_rack * A1_PORTS_PER_CHIP  # 1296
    per_gpu_links_frac = Fraction(ports_per_rack, A1_GPUS_PER_RACK)  # exact 18
    assert per_gpu_links_frac.denominator == 1, per_gpu_links_frac
    per_gpu_links = per_gpu_links_frac.numerator  # int 18
    per_gpu_aggregate = per_gpu_links_frac * per_port_per_direction  # exact Fraction 900
    rack_full_duplex_TBps = (
        Fraction(chips_per_rack) * per_chip_full_duplex_GBps / 1000
    )  # 129.6 TB/s (decimal), exact Fraction 648/5

    # Self-checks: the transcription constants must be self-consistent
    # integers; a wrong constant is a bug, not a finding.
    assert per_port_per_direction == 50, per_port_per_direction
    assert per_gpu_links == 18 and per_gpu_aggregate == 900
    assert rack_full_duplex_TBps == Fraction("129.6")

    def s(x: Fraction) -> str:
        return str(x)

    return {
        "quoted_verbatim": {
            "full_duplex_tbps_per_switch_chip": "57.6",
            "nvlink_ports_per_switch_chip": A1_PORTS_PER_CHIP,
            "nvswitches_per_switch_tray": A1_CHIPS_PER_TRAY,
            "switch_trays_per_nvl72_rack": A1_TRAYS_PER_RACK,
        },
        "derived_arithmetic": {
            "per_chip_full_duplex_GB_per_s_decimal": s(per_chip_full_duplex_GBps),
            "per_chip_per_direction_GB_per_s_decimal": s(per_chip_per_direction_GBps),
            "per_port_per_direction_bytes_per_ns": s(per_port_per_direction),
            "chips_per_rack": chips_per_rack,
            "ports_per_rack": ports_per_rack,
            "per_gpu_links": s(per_gpu_links),
            "per_gpu_aggregate_per_direction_bytes_per_ns": s(per_gpu_aggregate),
            "rack_full_duplex_TB_per_s_decimal": s(rack_full_duplex_TBps),
        },
        "cross_anchor_consistency_notes": [
            "A1's own arithmetic gives 18 chips x 7.2 TB/s = 129.6 TB/s rack full-duplex "
            "and 18 links x 50 GB/s = 900 GB/s per GPU per direction; both coincide with "
            "CAL-A2's rounded quotes (130 TB/s; 1.8 TB/s bidirectional per GPU => 900 GB/s "
            "per direction). Consistency notes only — CAL-A2 is its own ladder stage.",
        ],
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str, ceiling: Fraction) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    wire = Fraction(per_op["per_rank_wire_bytes_exact"])
    busbw = wire / cct  # NCCL busbw convention: 2(r-1)/r * M / t
    fraction = busbw / ceiling
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
        "anchor_ceiling_bytes_per_ns": str(ceiling),
        "fraction_of_ceiling_exact": str(fraction),
        "fraction_of_ceiling_float": float(fraction),
        "absolute_delta_busbw_minus_ceiling_exact": str(busbw - ceiling),
    }


def sweep_comparison() -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID / "table.json")
    ceiling_by_topology = {
        "crossbar72_a1_span20_v1": Fraction(20),
        "crossbar72_a1_port50_v1": Fraction(50),
        "crossbar72_a1_span64_v1": Fraction(64),
        "crossbar72_a1_agg900_v1": Fraction(900),
    }
    by_size: dict[int, list[dict]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        size = row["payload_bytes"]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        busbw = wire / cct
        ceiling = ceiling_by_topology[topo]
        by_size.setdefault(size, []).append(
            {
                "topology_id": topo,
                "config_id": row["config_id"],
                "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
                "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
                "delta_vs_anchor_point_exact": row["delta_vs_baseline"]["delta_exact"],
                "delta_vs_anchor_point_float": row["delta_vs_baseline"]["delta_float"],
                "implied_busbw_bytes_per_ns_exact": str(busbw),
                "fraction_of_ceiling_exact": str(busbw / ceiling),
                "fraction_of_ceiling_float": float(busbw / ceiling),
            }
        )
    ladder = [
        {
            "payload_bytes": size,
            "rows": sorted(entries, key=lambda e: -Fraction(e["implied_busbw_bytes_per_ns_exact"])),
        }
        for size, entries in sorted(by_size.items())
    ]
    return {
        "sweep_id": SWEEP_ID,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "crossbar72_a1_port50_v1 (the CAL-A1 anchor point; delta columns measure placement vs it)",
        "message_size_ladder": ladder,
    }


def main() -> int:
    derived = anchor_derived()
    ceiling_port = Fraction(50)
    ceiling_agg = Fraction(900)

    # Fan-in / radix check (computed, not asserted into the record).
    radix_check = {
        "anchor_radix_ports_per_chip": A1_PORTS_PER_CHIP,
        "model_ranks": 72,
        "fan_in_fits_single_chip": 72 <= A1_PORTS_PER_CHIP,
        "slack_ports": A1_PORTS_PER_CHIP - 72,
        "note": "r=72 exactly fills a 72-port radix; ranks>72 would need a multi-chip "
        "fabric abstraction — outside this identity's single-chip per-port mapping "
        "(the agg900 mapping below IS the all-18-chips abstraction).",
    }

    # Fabric-aggregate consistency: model-implied per-direction aggregate
    # (ranks x B at full injection) vs the anchor's own aggregates.
    aggregate_checks = [
        {
            "mapping": "per_port (one switch chip as the fabric)",
            "B_bytes_per_ns": 50,
            "model_implied_fabric_per_direction_bytes_per_ns": str(72 * 50),
            "anchor_aggregate_per_direction_bytes_per_ns": derived["derived_arithmetic"][
                "per_chip_per_direction_GB_per_s_decimal"
            ],
            "exact_match": str(72 * 50)
            == derived["derived_arithmetic"]["per_chip_per_direction_GB_per_s_decimal"],
        },
        {
            "mapping": "aggregate (all 18 chips as one non-blocking fabric)",
            "B_bytes_per_ns": 900,
            "model_implied_fabric_per_direction_bytes_per_ns": str(72 * 900),
            "anchor_aggregate_per_direction_bytes_per_ns": str(18 * 3600),
            "exact_match": 72 * 900 == 18 * 3600,
        },
    ]

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A1 (anchor CAL-A1)",
        "anchor": {
            "anchor_id": "CAL-A1",
            "title": "NVIDIA DGX GB200/GB300 NVL72 User Guide: NVLink5 switch chip",
            "source_row": "the anchor registry row CAL-A1 (PROPOSED)",
            "staging_doc": "docs/calibration/anchors_staging.md §A1",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A1",
            "url": "https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html",
            "confidence": "H for the numbers; SPEC, not measurement — ceiling only, never an achieved value",
            "quotes_verbatim": [
                "The NVLink switch system delivers an unprecedented 57.6 terabits per second (Tbps) of full duplex bandwidth",
                "2x NVLink NVSwitches, each of which has 72 NVLink ports",
                "9x 1RU NVLink switch trays",
            ],
        },
        "target": {
            "role": "normalization_ceiling_and_radix_fanin_check",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "CAL-A1 is a capacity specification, not a "
            "(size -> time) series; a CCT deviation is undefined against it "
            "(CALIBRATION_PLAN.md §1.1: 'Cannot calibrate O-CCT — normalization ceiling "
            "only'). The anchor's extractable targets are the per-port per-direction "
            "ceiling, the radix/fan-in constraint, and the fabric aggregates — all recorded here.",
            "regime": {
                "topology_class": "fully_connected_crossbar (L0 abstraction of the NVSwitch fat-tree class)",
                "ranks": 72,
                "message_bytes_ladder": [73728, 294912, 1179648, 4718592, 18874368,
                                         75497472, 301989888, 1207959552, 2415919104,
                                         4831838208, 19327352832, 77309411328],
                "message_regime_note": "any (capacity spec); ladder spans latency-bound "
                "(72 KiB) to bandwidth-bound (72 GiB); every size divisible by 72 (A-L0X-DIV)",
            },
        },
        "anchor_derived": derived,
        "model": {
            "backend_id": "analytical_l0_crossbar",
            "identity": "t = 2*(r-1)/r * M/B + 2*L ; per-rank wire bytes = 2*(r-1)/r * M",
            "ranks": 72,
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "20": "span lower endpoint (CAL-A12 NCCL NVLink model 20 GB/s/link; plan §2.1 A-L0-BW candidate span)",
                    "50": "CAL-A1 per-port per-direction (anchor point of this stage)",
                    "64": "span upper endpoint (CAL-A7 128 GB/s/link bidirectional => 64 B/ns per direction)",
                    "900": "CAL-A1-derived per-GPU aggregate (18 ports x 50 B/ns)",
                },
                "L_pair_latency_ns": 200,
                "L_provenance": "A-L0X-LAT registry point (KEEP per plan §2.1); latency axis deferred to its own global stage",
            },
            "assumptions": "A-L0X-PORT single-port injection, A-L0X-LAT, A-L0X-DIV (experiments/vertical_slice/assumptions_l0.yaml)",
        },
        "comparison": {
            "radix_fan_in_check": radix_check,
            "fabric_aggregate_consistency": aggregate_checks,
            "anchor_point_runs": [
                run_summary(RUN_ID_PORT50, "per_port (B=50: one switch-chip port per rank)", ceiling_port),
                run_summary(RUN_ID_AGG900, "aggregate (B=900: 18 ports per rank, whole-rack fabric)", ceiling_agg),
            ],
            "reconciled_sweep": sweep_comparison(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — the anchor publishes no "
            "time series; recorded per the stage's FAIL-clause duty instead of skipped "
            "because the anchor's actual role (ceiling/radix) IS extractable and is "
            "executed above.",
            "ceiling_utilization_summary": "The identity's implied busbw sits strictly below "
            "the anchor ceiling at every finite size and converges to exactly 1.0 "
            "algebraically as size grows (the +2L latency term vanishes): the model can "
            "never exceed a spec ceiling, so any future measured series above this line "
            "falsifies the mapping, not the ceiling.",
            "span_placement": "CCT ratios vs the anchor point are arithmetic facts of 1/B "
            "(asymptotically exactly +1.5 at B=20, -0.21875 at B=64, -0.944... at "
            "B=900; the sweep table records the exact per-size values including the "
            "latency term).",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified)",
            "candidate": "PROPOSED calibration candidate targeting the normalization role; "
            "no E3/E4 language — CAL-A1 is an external published specification, not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_PORT50, RUN_ID_AGG900],
            "sweep_id": SWEEP_ID,
            "sweep_dir": f"results/sweeps/{SWEEP_ID}",
            "inputs": [
                "experiments/calibration/a1/sweep_a1_ceiling_v1.yaml",
                "experiments/calibration/a1/run_a1_anchor_point_v1.yaml",
                "experiments/calibration/a1/run_a1_aggregate_v1.yaml",
                "experiments/calibration/workloads/w1_dense_tp_decode_tp72.yaml",
                "experiments/calibration/a1/topologies/ (4 files)",
                "experiments/calibration/a1/profiles/implementation_profile_l0_crossbar_free.yaml",
            ],
            "reproduce": "make run EXP=experiments/calibration/a1/run_a1_anchor_point_v1.yaml ; "
            "make run EXP=experiments/calibration/a1/run_a1_aggregate_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a1/sweep_a1_ceiling_v1.yaml ; "
            "python experiments/calibration/a1/build_calibration_record.py",
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
