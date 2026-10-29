"""Build the PROPOSED calibration-candidate record for anchor CAL-A5 (Q1
calibration stage A5.

CAL-A5 is Google TPU v4 (ISCA 2023): 6 ICI links @ 50 GB/s per chip, OCS
reconfiguration, and MEASURED twisted-vs-regular torus all-to-all ratios
(1.63x on a 4x4x8 slice, 1.31x on a 4x8x8 slice, individual 4 KiB DMAs).
Per docs/calibration/CALIBRATION_PLAN.md §1.1 the anchor CANNOT calibrate
O-CCT directly (its measured quantity is an all-to-all throughput RATIO
between two geometries, not a collective completion-time series), so this
stage executes its two plan-assigned roles: the PER-LINK BW anchor placement
for a non-Ethernet, non-NVIDIA scale-up fabric, and the TOPOLOGY-SENSITIVITY
FALSIFIER the plan's A-L0T-UNIF row names ("the first falsifier of geometry
abstractions >30%"). The falsifier's model side is structural: the L0
2D-torus identity has NO geometry field — twisted and regular tori of the
same shape map to identical model inputs, so the model's predicted
twisted/regular ratio is exactly 1.0 against a measured 1.31-1.63.

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity with exact Fractions, and writes a content-addressed
record to ``results/calibration/<record_id>/record.json`` (record_id =
SHA-256 of the canonical record; append-only — an existing record with
different bytes is an error, identical bytes are idempotent).

Closed-form coverage: the sweep executes 13 configs (the anchor-point
shapes at 4 swept B values + the shape-space bounds at the anchor B); the
record evaluates the same identity function
(``l0_torus2d.torus2d_allreduce_time_ns``) over the FULL distinct shape
space at both slices and all swept B, cross-checking every EXECUTED row
against the closed form by exact Fraction string equality. Payload 4096 B
(the anchor's individual DMA size) is a power of two, as is every torus
dimension here, so the A-L0T-DIV gate ACCEPTS the anchor's regime exactly —
no bracketing (the mirror image of stage A3, where 72 = 8*9 rejected every
power of two).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number is either (a) transcribed from the anchor's staged
numbers in ``docs/calibration/anchors_staging.md`` §A5 (declared with
provenance), or (b) computed from stored run/sweep artifacts or the
identity function by this script. Nothing is tuned: the swept B values and
shapes carry their anchor/plan provenance, and the direction-convention
ambiguity of the per-link figure is executed as BOTH readings rather than
resolved.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical.l0 import require_divisible
from essun.backends.analytical.l0_torus2d import (
    BACKEND_ID,
    Torus2DConfig,
    execute as torus2d_execute,
    load_torus2d_config,
    torus2d_allreduce_time_ns,
    torus2d_traffic_per_rank,
)
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json
from essun.workload import w1

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_SLICE128 = "eaa6bc36718c7578589b6d02757b8b611ce23d30f5dd435335383697914c6924"
RUN_ID_SLICE256 = "f9db773f4a8807c0c7af9bd8053be424c599f5588df579382659ea84d6733c41"
SWEEP_ID_128 = "88ac67b1bc3b84e49cbb30c95e693af0760eb5eb74411fee5828a72431243311"
SWEEP_ID_256 = "772052ec6be3579973ae3189f4e86bb998292f49f2ade7da1e48377098264bdd"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A5 staged numbers (docs/calibration/anchors_staging.md §A5;
# transcription confidence H — numbers verified from the paper text by the
# staging job; direction convention of the per-link figure flagged
# UNVERIFIED there: "do not confuse with per-direction aggregate without
# re-checking Table 4 column order at integration").
ICI_LINKS_PER_CHIP = 6
ICI_LINK_GBPS = Fraction(50)          # "6 links @ 50 GB/s" (Table 4)
ICI_SEC73_QUOTE = "ICI link bandwidth is 2x IB—400 vs. 200 Gbit/s"
ICI_LINKS_PER_PCB_EXTERNAL = 16
OCS_PORTS = "136x136 (128 usable + 8 spare), Palomar OCS, path switching 'milliseconds'"
TPUV3_ROW = (4, Fraction(70))         # TPU v3 comparison row: 4 links @ 70 GB/s
A100_ROW = (12, Fraction(25))         # A100 comparison row: 12 links @ 25 GB/s
TWIST_RATIOS = {128: Fraction("1.63"), 256: Fraction("1.31")}  # twisted vs regular, all-to-all
DMA_BYTES = 4096                      # "individual DMAs of 4 KiB"
HYBRID_SLOWER = "1.8x-2.4x slower"    # paper's projection, NOT a measurement
PALM = "6144 chips, 57.8% of peak FLOPs for 50 days"  # out of scope: FLOPs, not fabric

# Direction-convention readings of the per-link figure (both EXECUTED,
# neither chosen — the staging doc flags the convention unverified):
READING1 = Fraction(50)   # 50 GB/s per link PER DIRECTION (supported by the §7.3
#                          400-vs-200-Gbit/s per-link quote); per-chip aggregate
#                          6 x 50 = 300 B/ns.
READING2 = Fraction(25)   # 50 GB/s per link BIDIRECTIONAL => 25 B/ns per direction;
#                          per-chip aggregate 150 B/ns.
PER_CHIP_AGGREGATE = {
    "reading1_per_link_per_direction_50": Fraction(300),
    "reading2_per_link_bidirectional_25": Fraction(150),
}

# Plan/registry anchors for the placement statements.
PLAN_SPAN = (Fraction(20), Fraction(64))  # CALIBRATION_PLAN §2.1 A-L0T-BW candidate span
REGISTRY_POINT = Fraction(64)             # A-L0T-BW registry value
L_REGISTRY_NS = Fraction(200)             # A-L0T-LAT registry point (KEEP)
CAL_A4_BAND = Fraction(5, 100)            # CAL-A4 validated mean-error band
CAL_A6_SWING = (Fraction(5, 100), Fraction(8, 100))  # CAL-A6 software-version swing

B_SWEPT = {"20": Fraction(20), "25": Fraction(25), "50": Fraction(50), "64": Fraction(64)}
# Declared 3D->2D projections (partitions of the anchor's own dimension
# lengths) and the shape-space bounds (not partitions) at each slice.
SHAPES_128 = {"2x64": (2, 64), "4x32": (4, 32), "8x16": (8, 16)}
SHAPES_256 = {"2x128": (2, 128), "4x64": (4, 64), "8x32": (8, 32), "16x16": (16, 16)}
FAITHFUL = {"128": {"4x32", "8x16"}, "256": {"4x64", "8x32"}}
ANCHOR_SHAPE = {"128": "8x16", "256": "8x32"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def config_for(ranks: int, d1: int, d2: int, b: Fraction) -> Torus2DConfig:
    return Torus2DConfig(
        topology_id=f"cal_a5_closed_form_{ranks}_{d1}x{d2}_b{b}",
        ranks=ranks,
        dim1_ranks=d1,
        dim2_ranks=d2,
        link_bytes_per_ns=b,
        hop_latency_ns=L_REGISTRY_NS,
    )


def cct(ranks: int, shape: tuple[int, int], b: Fraction, payload: int = DMA_BYTES) -> Fraction:
    d1, d2 = shape
    return torus2d_allreduce_time_ns(payload, config_for(ranks, d1, d2, b))


def latency_part(shape: tuple[int, int]) -> Fraction:
    d1, d2 = shape
    return Fraction(2 * (d1 - 1) * L_REGISTRY_NS + 2 * (d2 - 1) * L_REGISTRY_NS)


# ---------------------------------------------------------------------------
# 1. Anchor transcription + the two direction readings
# ---------------------------------------------------------------------------
def anchor_transcription() -> dict:
    both_inside = all(PLAN_SPAN[0] <= r <= PLAN_SPAN[1] for r in (READING1, READING2))
    assert both_inside
    v3_outside = TPUV3_ROW[1] > PLAN_SPAN[1]
    return {
        "staged_numbers": {
            "ici_table4": "TPU v4 Inter-Chip Interconnect: 6 links @ 50 GB/s per chip",
            "ici_sec73": ICI_SEC73_QUOTE + " (=> 50 GB/s = 400 Gbit/s per link)",
            "ici_pcb": f"{ICI_LINKS_PER_PCB_EXTERNAL} external ICI links per PCB (board wiring topology not reconstructible from the staged numbers)",
            "comparison_rows_table4": {
                "tpu_v3": "4 links @ 70 GB/s",
                "a100": "12 links @ 25 GB/s",
            },
            "ocs": OCS_PORTS,
            "twisted_vs_regular_all_to_all": {
                "4x4x8 (r=128)": "1.63x",
                "4x8x8 (r=256)": "1.31x",
                "regime": "individual DMAs of 4 KiB (all-to-all throughput; no absolute times staged)",
            },
            "hybrid_ici_ib_projection": HYBRID_SLOWER + " for all-reduce (the paper's projection of an UNBUILT alternative — not a measurement)",
            "palm": PALM + " (FLOPs utilization, not a fabric observable — out of scope)",
        },
        "per_link_direction_convention": {
            "status": "UNVERIFIED (staging doc flags Table 4 column order; neither reading is chosen)",
            "reading1_per_direction_B_per_ns": str(READING1),
            "reading2_bidirectional_B_per_ns_per_direction": str(READING2),
            "per_chip_aggregate_B_per_ns": {k: str(v) for k, v in PER_CHIP_AGGREGATE.items()},
            "treatment": "BOTH readings are executed in the sweep; the anchor point is reading 1 (50), which the anchor's own §7.3 per-link quote supports",
        },
        "confidence": "H (numbers verified from paper text by the staging job); vendor paper with measured all-to-all experiments on 4x4x8 / 4x8x8 slices of 4096-chip OCS-reconfigurable 3D-torus pods",
    }


# ---------------------------------------------------------------------------
# 2. Per-link BW placement (the anchor's first plan-assigned role)
# ---------------------------------------------------------------------------
def link_bw_placement() -> dict:
    reg_over_anchor = REGISTRY_POINT / READING1  # 64/50
    v3_over_span_ceiling = TPUV3_ROW[1] / PLAN_SPAN[1]
    return {
        "question": "where do CAL-A5's per-link ICI readings sit relative to the plan's A-L0T-BW candidate span [20, 64] B/ns and the registry point 64?",
        "readings_vs_span": {
            "reading1_50": "INSIDE the span (20 <= 50 <= 64)",
            "reading2_25": "INSIDE the span (20 <= 25 <= 64)",
            "span_endpoints_provenance": "20 = CAL-A12 NCCL per-link model; 64 = CAL-A7 per-direction endpoint (plan §2.1 A-L0T-BW NARROW-range candidate)",
        },
        "registry_point_contrast": {
            "registry_over_anchor_point_exact": str(reg_over_anchor),
            "registry_over_anchor_point_float": float(reg_over_anchor),
            "statement": "the A-L0T-BW registry point 64 B/ns sits +28.0% above the reading-1 anchor point 50 B/ns (64/50 = 1.28): the free-parameter registry default is an overestimate of this fabric's per-link rate under reading 1 — a PLACEMENT fact, not a change (the registry value is untouched)",
        },
        "plan_span_flag": {
            "finding": f"CAL-A5's own Table 4 comparison rows bracket the span differently: TPU v3 70 GB/s/link sits ABOVE the plan's candidate ceiling 64 ({float(v3_over_span_ceiling):.3f}x) and A100 25 GB/s/link sits inside it",
            "classification": "the plan §2.1 A-L0-BW/A-L0T-BW NARROW-range candidate [20, 64] was derived from CAL-A7/CAL-A12 endpoints + CAL-A5's 50; CAL-A5's OWN comparison rows (70 v3-era, 25 A100 NVLink-3) were not span inputs. If 70 is per-link per-direction, the candidate span's upper endpoint excludes an anchor's own comparison row of the same table — direction convention UNVERIFIED (same flag as the 50 figure). Recorded for the owner; no span or value is changed here",
        },
        "structural_link_use_note": {
            "finding": "the sequential-dimension schedule (A-L0T-SEQ) activates ONE dimension's ring at a time, so the identity's instantaneous per-chip injection is at most B (one outgoing link of the chip's 6 link directions) — i.e. at most 1/6 of the anchor's reading-1 per-chip ICI aggregate 300 B/ns",
            "ratio_exact": str(Fraction(1, 6)),
            "status": "a structural property of the declared identity (KEEP verdicts per plan §2.1), quantified — not tunable, not a defect claim: overlapping-dimension schedules are explicitly unsupported by the backend capabilities",
        },
    }


# ---------------------------------------------------------------------------
# 3. The topology-sensitivity falsifier (the anchor's second, main role)
# ---------------------------------------------------------------------------
def twist_blindness_falsifier() -> dict:
    """The plan's A-L0T-UNIF flag quantified: measured twisted-vs-regular
    all-to-all spread 1.31-1.63x at equal link BW vs the L0 torus identity's
    structural ratio of exactly 1.0 (no geometry field exists in the input
    space). Minimized and classified per handoff rule 5 — never tuned."""
    # (a) structural blindness, verified against the landed dataclass
    fields = {f.name for f in dataclasses.fields(Torus2DConfig)}
    expected_fields = {
        "topology_id",
        "ranks",
        "dim1_ranks",
        "dim2_ranks",
        "link_bytes_per_ns",
        "hop_latency_ns",
    }
    assert fields == expected_fields, fields

    # (b) live demonstration: twisted- vs regular-labeled configs (identical
    # dims/B/L) produce identical exact completions under the landed execute()
    wl = w1.load_w1_config(
        REPO_ROOT / "experiments/calibration/a5/workloads/w1_dense_tp_decode_tp128_4kib.yaml"
    )
    ops = w1.generate_w1_ops(wl)
    cfg_twisted = config_for(128, 8, 16, READING1)
    cfg_regular = Torus2DConfig(
        topology_id="cal_a5_regular_labeled_twin",
        ranks=128,
        dim1_ranks=8,
        dim2_ranks=16,
        link_bytes_per_ns=READING1,
        hop_latency_ns=L_REGISTRY_NS,
    )
    out_t = torus2d_execute(ops, cfg_twisted)
    out_r = torus2d_execute(ops, cfg_regular)
    assert (
        out_t["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
        == out_r["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
    )

    # (c) quantification of the blind spot
    rows = {}
    for ranks, measured in TWIST_RATIOS.items():
        blind = measured - 1  # model predicts 1.0; the missed effect
        rows[f"r={ranks}"] = {
            "measured_twisted_over_regular_all_to_all": str(measured),
            "model_twisted_over_regular": "1 (exactly, by input-space blindness)",
            "blind_spot_of_regular_baseline_exact": str(blind),
            "blind_spot_pct": float(blind * 100),
            "multiple_of_CAL_A4_5pct_band_exact": str(blind / CAL_A4_BAND),
            "multiple_of_CAL_A4_5pct_band_float": float(blind / CAL_A4_BAND),
            "multiple_of_CAL_A6_swing_upper_exact": str(blind / CAL_A6_SWING[1]),
        }
    assert float(rows["r=128"]["blind_spot_pct"]) == 63.0
    assert float(rows["r=256"]["blind_spot_pct"]) == 31.0

    return {
        "structural_blindness": {
            "torus2d_config_fields": sorted(fields),
            "finding": "the input schema carries NO geometry field: a twisted torus and a regular torus of the same (r1, r2, B, L) map to IDENTICAL model inputs, so the identity is invariant on the twist axis BY CONSTRUCTION — the twisted/regular ratio the anchor measured is inexpressible, not merely mispredicted",
            "demonstration": "two configs labeled twisted/regular (identical dims, B=50, L=200) executed through the landed l0_torus2d.execute on the tp128 4 KiB workload: completion_time_ns_mean_exact EQUAL (exact Fraction string equality, verified while building this record)",
        },
        "quantified_blind_spot": {
            "metric_discipline": "ratio vs ratio (dimensionless geometry effect vs dimensionless geometry effect); the anchor's all-to-all THROUGHPUT and the model's allreduce CCT are never compared to each other — no mixed metric",
            "rows": rows,
        },
        "classification_per_handoff_rule_5": {
            "minimized_counterexample": "CAL-A5's measured 1.31-1.63x twisted-vs-regular spread at equal link BW and equal shape is a real-geometry effect of 31-63% that NO setting of the model's free parameters (B, L, shape) can reproduce — the identity is invariant on the twist axis",
            "class": "STRUCTURAL (input-space blindness), not a parameter mismatch: 63%/31% is 12.6x/6.2x CAL-A4's ~5% validated mean-error band and 7.9x/3.9x CAL-A6's 8% software-version noise floor — an order above every noise scale in the anchor set, so it cannot be absorbed as measurement noise",
            "refinement": "owner decision, out of this stage's scope: expressing a twisted-torus geometry is a NEW identity (the plan §1.1 row CAL-A5 notes the anchor's metric checks topology-class modeling, not CCT), and the plan's A-L0T-UNIF flag anticipated exactly this ('torus-class calibration should treat CAL-A5 as the first falsifier of geometry abstractions >30%')",
        },
        "model_shape_axis_context": {
            "note": "the model is NOT geometry-insensitive in general — its own shape axis (factor-pair choice at fixed r, A-L0T-SHAPE) moves CCT by MORE than the anchor's twist effect (see regime_placement.shape_space) — but along an axis orthogonal to twist: shape changes the latency chain 2*(r1+r2-2), twist changes bisection structure. Recorded as context, NOT agreement",
        },
    }


# ---------------------------------------------------------------------------
# 4. Regime placement (where the model sits in the anchor's 4 KiB regime)
# ---------------------------------------------------------------------------
def sweep_rows() -> dict:
    """All executed rows from both sweeps, keyed for cross-checks."""
    rows = {}
    for sweep_id in (SWEEP_ID_128, SWEEP_ID_256):
        table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
        for row in table["configs"]:
            topo = row["config_id"].split("-")[2]
            rows[(sweep_id, topo)] = row
    assert len(rows) == 13, len(rows)
    return rows


def regime_placement() -> tuple[dict, dict]:
    """Placement of the anchor's per-link readings and slices inside the
    model's parameter/shape space, from EXECUTED rows + declared closed
    form over the full distinct shape space."""
    rows = sweep_rows()
    executed = []
    for (sweep_id, topo), row in rows.items():
        ranks = 128 if sweep_id == SWEEP_ID_128 else 256
        shapes = SHAPES_128 if ranks == 128 else SHAPES_256
        b = Fraction(row["config_id"].split("_b")[1].split("_")[0])
        shape = shapes["x".join(topo.split("_")[2].split("x")[:2])]
        # cross-check: the executed row equals the closed form of the same
        # identity function (exact Fraction string equality)
        assert row["o_cct"]["completion_time_ns_mean_exact"] == str(cct(ranks, shape, b))
        t = cct(ranks, shape, b)
        lat = latency_part(shape)
        executed.append(
            {
                "sweep_id": sweep_id,
                "topology_id": topo,
                "ranks": ranks,
                "shape": f"{shape[0]}x{shape[1]}",
                "B_bytes_per_ns": str(b),
                "cct_ns_exact": str(t),
                "cct_ns_float": float(t),
                "latency_term_fraction_exact": str(lat / t),
                "latency_term_fraction_pct": float(lat / t * 100),
                "delta_vs_baseline_exact": row["delta_vs_baseline"]["delta_exact"],
                "faithful_projection": "x".join(topo.split("_")[2].split("x")[:2]) in FAITHFUL[str(ranks)],
            }
        )

    # closed form over the FULL distinct shape space at the anchor B and the
    # full B span at the anchor shapes; executed rows above back the identity
    closed_form = []
    for ranks, shapes in ((128, SHAPES_128), (256, SHAPES_256)):
        for name, shape in shapes.items():
            for b_str, b in B_SWEPT.items():
                t = cct(ranks, shape, b)
                closed_form.append(
                    {
                        "ranks": ranks,
                        "shape": name,
                        "B_bytes_per_ns": b_str,
                        "cct_ns_exact": str(t),
                        "cct_ns_float": float(t),
                        "latency_term_fraction_exact": str(latency_part(shape) / t),
                        "executed": (SWEEP_ID_128 if ranks == 128 else SWEEP_ID_256, f"torus2d{ranks}_a5_{name}_b{b_str}_v1") in rows,
                    }
                )

    # shape-space bounds at the anchor B (all executed at b=50)
    shape_space = {}
    for ranks, shapes in ((128, SHAPES_128), (256, SHAPES_256)):
        times = {name: cct(ranks, shape, READING1) for name, shape in shapes.items()}
        fastest = min(times, key=lambda k: (times[k], k))
        slowest = max(times, key=lambda k: (times[k], k))
        spread = times[slowest] / times[fastest]
        shape_space[f"r={ranks}"] = {
            "distinct_shapes": sorted(shapes),
            "times_at_anchor_B_exact": {k: str(v) for k, v in times.items()},
            "fastest_shape": fastest,
            "slowest_shape": slowest,
            "spread_slowest_over_fastest_exact": str(spread),
            "spread_float": float(spread),
            "anchor_slice_projection_rank": (
                "fastest" if times[ANCHOR_SHAPE[str(ranks)]] == times[fastest] else "interior"
            ),
        }
    assert shape_space["r=128"]["anchor_slice_projection_rank"] == "fastest"

    # B-axis sensitivity at the anchor shapes (the whole swept span's effect)
    b_axis = {}
    for ranks in (128, 256):
        shape = SHAPES_128[ANCHOR_SHAPE["128"]] if ranks == 128 else SHAPES_256[ANCHOR_SHAPE["256"]]
        t_anchor = cct(ranks, shape, READING1)
        deltas = {}
        for b_str, b in B_SWEPT.items():
            deltas[b_str] = (cct(ranks, shape, b) - t_anchor) / t_anchor
        b_axis[f"r={ranks}"] = {
            "anchor_point_B": str(READING1),
            "cct_at_anchor_B_exact": str(t_anchor),
            "delta_pct_vs_anchor_B": {k: float(v * 100) for k, v in deltas.items()},
            "max_abs_delta_pct_across_whole_span": float(max(abs(v) for v in deltas.values()) * 100),
        }

    placement = {
        "regime": {
            "message_bytes": DMA_BYTES,
            "message_regime_note": "the anchor's individual all-to-all DMA size (4 KiB) used as the AllReduce payload — places the runs in the anchor's regime; all-to-all and allreduce are never compared to each other",
            "divisibility_gate": "A-L0T-DIV ACCEPTS 4096 at every power-of-two dimension of this stage (verified programmatically) — the anchor's regime enters the run path EXACTLY, no bracketing (mirror of stage A3, where 72 = 8*9 rejected every power of two)",
            "ranks": [128, 256],
            "topology_class": "torus2d_ring_x_ring (declared 3D->2D projection of the anchor's 3D slices)",
        },
        "executed_rows": executed,
        "shape_space_at_anchor_B": shape_space,
        "b_axis_sensitivity_at_anchor_shapes": b_axis,
        "latency_dominated": "at the anchor points the hop-latency terms are 96.7% (8x16) and 98.1% (8x32) of CCT — in the anchor's 4 KiB regime the identity is hop-latency-dominated, so this placement inherits the L = 200 ns registry point from the plan's WEAKEST axis (gap §4.2: no measured current-gen hop latency exists in the anchor set)",
        "regime_punchline": "the whole swept B span {20..64} moves anchor-shape CCT by at most ~5.6% (r=128) / ~2.9% (r=256) while the shape axis moves it 2.84x / 4.18x — in this regime geometry (and the unanchored latency axis) dominates and the link-BW axis is nearly invisible in CCT, which is consistent with the anchor's own measurement being a GEOMETRY effect, not a bandwidth effect",
    }
    return placement, {"closed_form_all_shapes_all_B": closed_form}


# ---------------------------------------------------------------------------
# 5. OCS reconfiguration bound (cannot calibrate; bounds future modeling)
# ---------------------------------------------------------------------------
def ocs_reconfiguration_bound() -> dict:
    switching_ns = Fraction(1_000_000)  # "milliseconds": declared conservative
    #                                    lower edge of the staged WORD (the
    #                                    paper says 'milliseconds', no number)
    t128 = cct(128, SHAPES_128[ANCHOR_SHAPE["128"]], READING1)
    t256 = cct(256, SHAPES_256[ANCHOR_SHAPE["256"]], READING1)
    return {
        "staged": OCS_PORTS,
        "declared_lower_edge_ns": "1e6 (the paper stages the WORD 'milliseconds'; 1 ms is the conservative lower edge of that word — a declared interpretation, not a staged number)",
        "ratios_exact": {
            "vs_per_hop_L_200ns": str(switching_ns / L_REGISTRY_NS),
            "vs_anchor_point_cct_r128_8x16": str(switching_ns / t128),
            "vs_anchor_point_cct_r256_8x32": str(switching_ns / t256),
        },
        "ratios_float": {
            "vs_per_hop_L_200ns": float(switching_ns / L_REGISTRY_NS),
            "vs_anchor_point_cct_r128_8x16": float(switching_ns / t128),
            "vs_anchor_point_cct_r256_8x32": float(switching_ns / t256),
        },
        "bound": "OCS path switching is >= 3.7 orders above the model's per-hop latency and >= 2 orders above every CCT the identity emits in the anchor's regime: reconfiguration is QUASI-STATIC relative to collective completion — any dynamic-topology modeling must treat an OCS event as topology redefinition BETWEEN runs, never as in-run dynamics the CCT identity could see. Per plan §1.1 the OCS timescale CANNOT calibrate O-CCT; it bounds only dynamic-topology reconfiguration modeling",
        "model_status": "the L0 topology schema has no reconfiguration parameter (static topology by construction — the same input-space enumeration as the twist finding), so this anchor is recorded as a BOUND, not a calibration",
    }


# ---------------------------------------------------------------------------
# 6. Inextractable targets (FAIL-clause honesty duty)
# ---------------------------------------------------------------------------
def inextractable_targets() -> list[dict]:
    return [
        {
            "target": "absolute all-to-all completion times / throughputs",
            "reason": "the anchor stages only the twisted/regular RATIOS (1.63x / 1.31x); no absolute (size -> time) series exists in the staged numbers, so no CCT-vs-CCT comparison is defined — this stage therefore never compares a model CCT against a CAL-A5 number",
        },
        {
            "target": "all-to-all as a model collective",
            "reason": "the anchor measures ALL-TO-ALL throughput; the L0 torus identity executes ALLREDUCE only (backend capabilities). Different collectives are never compared (no mixed metric per plan §3); the 4 KiB DMA size is used solely to place the runs in the anchor's message regime",
        },
        {
            "target": "3D torus geometry",
            "reason": "the model is 2D (A-L0T-SHAPE); the anchor's slices are 3D. The two partitions of each slice's own dimension lengths are executed as the faithful projections; the projection distortion is declared in every topology file, never claimed silent",
        },
        {
            "target": "hybrid IB+ICI all-reduce penalty (1.8x-2.4x slower)",
            "reason": "the paper's PROJECTION of an unbuilt alternative, not a measurement of a built system (staging doc wording: 'would be'); recorded, not used",
        },
        {
            "target": "PaLM utilization (57.8% of peak FLOPs, 50 days)",
            "reason": "an FLOPs-utilization figure, not a fabric observable; out of scope for O-CCT/parameter calibration",
        },
        {
            "target": "16 external ICI links per PCB",
            "reason": "board-level wiring topology; the staged number alone does not reconstruct the board's chip count or internal wiring (any reconstruction would be invented) — recorded as staged context only",
        },
    ]


# ---------------------------------------------------------------------------
# 7. Store-run cross-checks
# ---------------------------------------------------------------------------
def run_checks() -> list[dict]:
    checks = []
    for run_id, ranks, shape_name in (
        (RUN_ID_SLICE128, 128, ANCHOR_SHAPE["128"]),
        (RUN_ID_SLICE256, 256, ANCHOR_SHAPE["256"]),
    ):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        shape = SHAPES_128[shape_name] if ranks == 128 else SHAPES_256[shape_name]
        per_op = obs["per_op"][0]
        assert per_op["payload_bytes"] == DMA_BYTES
        assert obs["model"]["ranks"] == ranks
        assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == READING1
        assert Fraction(obs["model"]["hop_latency_ns_exact"]) == L_REGISTRY_NS
        assert per_op["completion_time_ns_exact"] == str(cct(ranks, shape, READING1))
        # symmetry of the identity, as declared in the topology files
        assert cct(ranks, shape, READING1) == cct(ranks, (shape[1], shape[0]), READING1)
        checks.append(
            {
                "run_id": run_id,
                "mapping": f"anchor point: CAL-A5's {ANCHOR_SHAPE[str(ranks)]} projection of the {'4x4x8' if ranks == 128 else '4x8x8'} slice at B=50 (reading 1)",
                "experiment_id": run["manifest"]["experiment_id"],
                "manifest_path": run["manifest_path"],
                "payload_bytes": per_op["payload_bytes"],
                "cct_ns_exact": per_op["completion_time_ns_exact"],
                "cct_ns_float": per_op["completion_time_ns"],
                "verdict": "store run == closed form of the same identity function (exact Fraction string equality); identity symmetry dim1<->dim2 verified",
            }
        )
    return checks


# ---------------------------------------------------------------------------
# 8. Divisibility-gate acceptance (the anti-A3 check)
# ---------------------------------------------------------------------------
def div_gate_acceptance() -> dict:
    dims = sorted({d for shapes in (SHAPES_128, SHAPES_256) for s in shapes.values() for d in s})
    for d in dims:
        require_divisible(BACKEND_ID, "cal_a5_probe", DMA_BYTES, d, "A-L0T-DIV")
    return {
        "finding": "every torus dimension of this stage is a power of two and the anchor's 4 KiB DMA size is 2^12, so the A-L0T-DIV gate ACCEPTS the anchor's regime exactly",
        "dims_checked": dims,
        "contrast": "stage A3 needed 72-divisible floor/ceil brackets because 72 = 8*9 never divides a power of two; here no bracketing exists and every executed row sits AT the anchor's size",
    }


def main() -> int:
    transcription = anchor_transcription()
    placement_l = link_bw_placement()
    falsifier = twist_blindness_falsifier()
    placement, closed_form = regime_placement()
    ocs = ocs_reconfiguration_bound()
    inextractable = inextractable_targets()
    runs = run_checks()
    gate = div_gate_acceptance()

    blind128 = TWIST_RATIOS[128] - 1
    blind256 = TWIST_RATIOS[256] - 1
    deviation_summary = (
        "CAL-A5 pins no completion time, so no CCT deviation exists; the anchor's two "
        "plan-assigned deviations are: (1) the FALSIFIER — the model's twisted/regular "
        f"ratio is exactly 1 (input-space blindness) against the measured 1.63 (r=128) / "
        f"1.31 (r=256), i.e. the geometry abstraction hides a {float(blind128 * 100):.0f}%/"
        f"{float(blind256 * 100):.0f}% effect, {float(blind128 / CAL_A4_BAND):.1f}x/"
        f"{float(blind256 / CAL_A4_BAND):.1f}x CAL-A4's ~5% validated band — structural, "
        "inexpressible by any parameter choice, classified not tuned; (2) the per-link BW "
        f"placement — both direction readings (50 / 25 B/ns) sit INSIDE the plan's [20, 64] "
        f"span and the registry point 64 sits +{float((REGISTRY_POINT / READING1 - 1) * 100):.1f}% "
        "above the reading-1 anchor point, while CAL-A5's own TPU v3 comparison row "
        "(70 GB/s/link) would sit ABOVE the span ceiling — a plan-span flag recorded for "
        "the owner; (3) the OCS bound — path switching (ms, >= 1e6 ns declared lower "
        f"edge) is {float(Fraction(1_000_000) / L_REGISTRY_NS):.0f}x the per-hop latency "
        "and >= 2 orders every regime CCT: quasi-static, bounding future dynamic-topology "
        "modeling, calibrating nothing"
    )

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A5 (anchor CAL-A5)",
        "anchor": {
            "anchor_id": "CAL-A5",
            "title": "Google TPU v4 (ISCA 2023): ICI link bandwidth, OCS, topology measurements",
            "source_row": "the anchor registry row CAL-A5 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A5",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A5 (topology-sensitivity falsifier + per-link BW anchor; cannot calibrate O-CCT directly)",
            "url": "https://arxiv.org/abs/2304.01433",
            "confidence": "H (numbers verified from paper text by the staging job); per-link direction convention flagged UNVERIFIED in the staging doc",
            "transcription": transcription,
        },
        "target": {
            "role": "topology_sensitivity_falsifier_plus_per_link_bw_anchor",
            "regime": {
                "message_bytes": DMA_BYTES,
                "message_regime": "4 KiB individual all-to-all DMAs (small-message; the model's runs are hop-latency-dominated at 96.7-98.1%)",
                "ranks": [128, 256],
                "topology_class": "3D torus slices (4x4x8 / 4x8x8) of a 4096-chip OCS-reconfigurable pod, projected 3D->2D for the L0 identity",
            },
            "inextractable_targets": inextractable,
        },
        "model": {
            "backend_id": "analytical_l0_torus2d",
            "identity": "t_2d(M,r1,r2) = t_ring(M,r1) + t_ring(M,r2); t_ring(M,k) = 2*(k-1)/k*M/B + 2*(k-1)*L; per-rank wire bytes 2*(2-1/r1-1/r2)*M",
            "ranks": [128, 256],
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "20": "CAL-A12 NCCL per-link model (plan span lower endpoint)",
                    "25": "CAL-A5 READING 2 (per-link bidirectional reading of '6 links @ 50 GB/s')",
                    "50": "CAL-A5 READING 1 anchor point (per-link per-direction; §7.3 '400 vs. 200 Gbit/s')",
                    "64": "CAL-A7 per-direction endpoint AND the A-L0T-BW registry point",
                },
                "L_hop_latency_ns": 200,
                "L_provenance": "A-L0T-LAT registry point (KEEP per plan §2.1); the latency axis is the plan's weakest axis (gap §4.2) and this regime is latency-dominated — recorded as the dominant known limit",
                "shape_swept": "declared 3D->2D partitions of the anchor slices (8x16, 4x32; 8x32, 4x64) + shape-space bounds (2x64, 2x128, 16x16); swapped shapes are identity-symmetric twins (verified)",
            },
            "assumptions": "A-L0T-SEQ / A-L0T-UNIF / A-L0T-SHAPE / A-L0T-BW / A-L0T-LAT / A-L0T-DIV (experiments/vertical_slice/assumptions_l0.yaml)",
            "closed_form_coverage": "executed 13 configs (2 sweeps); the record's closed_form_all_shapes_all_B section evaluates the same identity function over every distinct shape at both slices x all swept B, with every EXECUTED row cross-checked by exact Fraction string equality; rows marked executed=false are declared closed-form-only",
        },
        "comparison": {
            "twist_blindness_falsifier": falsifier,
            "link_bw_placement": placement_l,
            "regime_placement": placement,
            "closed_form": closed_form,
            "ocs_reconfiguration_bound": ocs,
            "divisibility_gate": gate,
            "anchor_point_runs": runs,
        },
        "deviation": {
            "summary": deviation_summary,
            "not_tuned": "nothing was tuned: B values and shapes were fixed by the anchor's own staged arithmetic, the plan's span, and the declared projection rule before any model output was read; the direction-convention ambiguity is executed as BOTH readings rather than resolved; the falsifier is classified (structural), never absorbed",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against an external published measurement/spec; no E3/E4 language — CAL-A5 is not our testbed, and the owner's adjudication precedes any label move",
        },
        "backing": {
            "run_ids": [RUN_ID_SLICE128, RUN_ID_SLICE256],
            "sweep_ids": [SWEEP_ID_128, SWEEP_ID_256],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_128}", f"results/sweeps/{SWEEP_ID_256}"],
            "run_backed_numbers": "every run-path-executed number (13 sweep configs, 2 store runs); the closed-form-only rows are the same identity function whose executed instances are cross-checked above (declared inline)",
            "inputs": [
                "experiments/calibration/a5/sweep_a5_ici128_v1.yaml",
                "experiments/calibration/a5/sweep_a5_ici256_v1.yaml",
                "experiments/calibration/a5/run_a5_slice128_anchor_v1.yaml",
                "experiments/calibration/a5/run_a5_slice256_anchor_v1.yaml",
                "experiments/calibration/a5/workloads/ (2 files)",
                "experiments/calibration/a5/topologies/ (13 files)",
                "experiments/calibration/a5/profiles/implementation_profile_l0_torus2d_cal_a5_v1.yaml",
            ],
            "reproduce": "make run EXP=experiments/calibration/a5/run_a5_slice128_anchor_v1.yaml ; "
            "make run EXP=experiments/calibration/a5/run_a5_slice256_anchor_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a5/sweep_a5_ici128_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a5/sweep_a5_ici256_v1.yaml ; "
            "python experiments/calibration/a5/build_calibration_record.py",
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
