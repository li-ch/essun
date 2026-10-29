"""Build the PROPOSED calibration-candidate record for anchor CAL-A7 (Q1
calibration stage A7.

Pure function of immutable artifacts: reads the two append-only store run
records and the three sweep tables produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record, mirroring the evidence-store
addressing discipline; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_staging.md`` §A7
(declared below with provenance; the staging doc paraphrases the AMD
datasheet / Hot Chips slides / Lenovo note, so no "verbatim" quote strings
are claimed here), or (b) computed from the stored run/sweep artifacts by
this script, or (c) exact closed-form identity arithmetic cross-checked
against executed artifacts by exact Fraction string equality (declared
inline wherever used). Nothing is tuned: the swept B values carry their
anchor provenance, and the record measures where the model output sits
relative to the anchor.

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
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
RUN_ID_RING_LINK64 = "9ff3bf4b38cad10b6e01af39605a96e96919ddf1d8a2e1c897886fa7d00ee670"
RUN_ID_XBAR_AGG448 = "7dd2c513001d97c7daf5915947d0ffbe47a91662355c8e350750f3ca1a50847a"
SWEEP_ID_LINK = "b74430f193154c8e89b2778db723bda56e0fa716230ba56d4b360edacc254c94"
SWEEP_ID_AGG = "393acf4a9bf8282c50d084c07fd5e79b3ba803b32a15f8576bedfb7c24695984"
SWEEP_ID_DOUBLING = "81abeef70d4d0074bef7bf64e4c63330fe1a97d2d61a0f345c6e1d9779e3dae0"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A7 staged numbers (docs/calibration/anchors_staging.md §A7,
# transcription confidence H; SPEC, not measurement — ceiling only). The
# per-direction split is the calibration plan's stated convention for this
# anchor (§2.1: "CAL-A7's links are quoted bidirectional: 128 GB/s/link
# => 64 B/ns per direction"). Decimal units: 1 GB/s = 1 B/ns.
A7_LINKS_PER_GPU = 7
A7_LINK_BIDIRECTIONAL_GBPS = Fraction(128)
A7_AGGREGATE_BIDIRECTIONAL_GBPS = Fraction(896)   # quoted "896 GB/s" total
A7_GPUS_PER_BASEBOARD = 8
A7_PCIE_HOST_BIDIRECTIONAL_GBPS = Fraction(128)   # per GPU to HOST (out of scale-up domain)

R = 8                                # the anchor's own rank count
B_PER_LINK_PER_DIR = Fraction(64)    # 128/2 — plan-stated split
B_AGGREGATE_PER_DIR = Fraction(448)  # 7 * 64
L = Fraction(200)                    # A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry point

LADDER = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
          134217728, 268435456, 536870912, 2147483648, 8589934592]
ANCHOR_POINT_SIZE = 536870912        # 8*2^26 (512 MiB), a ladder member

RING_CEILING = B_PER_LINK_PER_DIR    # 64 B/ns — per-link reading ceiling
XBAR_CEILING = B_AGGREGATE_PER_DIR   # 448 B/ns — aggregate reading ceiling


def anchor_derived() -> dict:
    """Arithmetic consequences of CAL-A7's own staged numbers."""
    aggregate_check = (
        A7_LINKS_PER_GPU * A7_LINK_BIDIRECTIONAL_GBPS
    )  # 7 * 128 = 896 GB/s bidirectional
    per_link_per_dir = A7_LINK_BIDIRECTIONAL_GBPS / 2
    aggregate_per_dir = A7_LINKS_PER_GPU * per_link_per_dir
    pairs = A7_GPUS_PER_BASEBOARD * (A7_GPUS_PER_BASEBOARD - 1) // 2  # 28

    # Self-checks: the staged numbers must produce these exact values;
    # anything else is a transcription bug, not a finding.
    assert aggregate_check == A7_AGGREGATE_BIDIRECTIONAL_GBPS == 896
    assert per_link_per_dir == 64
    assert aggregate_per_dir == 448
    assert pairs == 28
    assert all(size % R == 0 for size in LADDER)  # A-L0-DIV / A-L0X-DIV / A-L0D-DIV accept

    return {
        "staged_numbers": {
            "if_links_per_gpu_bidirectional": "7",
            "if_link_bidirectional_GB_per_s": "128",
            "aggregate_bidirectional_GB_per_s_per_gpu": "896",
            "gpus_per_baseboard": "8",
            "pcie_gen5_x16_to_host_bidirectional_GB_per_s": "128",
            "split_note": "links are quoted BIDIRECTIONAL; the calibration "
            "plan states the split for CAL-A7 exactly (§2.1: '128 GB/s/link "
            "=> 64 B/ns per direction') — per-direction figures below are "
            "STAGED DERIVATIONS under that convention, flagged as "
            "interpretation risk if quoted as measured",
        },
        "derived_arithmetic": {
            "per_link_per_direction_bytes_per_ns": str(per_link_per_dir),
            "per_gpu_aggregate_per_direction_bytes_per_ns": str(aggregate_per_dir),
            "fabric_bidirectional_aggregate_GB_per_s": str(
                aggregate_check * A7_GPUS_PER_BASEBOARD / 2
            ),  # 8 GPUs x 448 per dir = 3584 GB/s one way... see note below
            "fabric_note": "8 x 448 = 3584 GB/s per direction summed over GPUs "
            "(a bisection-style aggregate, not a quote from the anchor; the "
            "anchor quotes only the per-GPU 896 GB/s bidirectional figure)",
            "dedicated_pairs_per_baseboard": str(pairs),
        },
    }


def topology_ambiguity() -> dict:
    """The anchor's own recorded wording conflict + the out-of-domain host leg."""
    return {
        "wording_conflict": {
            "conflict": "the AMD datasheet wording describes an '8-node ring' "
            "while the Hot Chips 2024 presentation describes the mesh; the "
            "staging doc records the discrepancy and sets the resolution rule",
            "staging_resolution": "treat as FULLY CONNECTED 7 links/GPU per "
            "Hot Chips + the Lenovo LP1943 confirmation ('128 GB/s between "
            "each of the 8 GPUs, for a total of 896 GB/s') — followed by this "
            "stage",
            "consistency_check": "a ring has degree 2, contradicting the "
            "anchor's own '7 links per GPU' quote; the full-mesh reading is "
            "the only one consistent with ALL staged numbers",
            "stage_consequence": "the ring identity executed by this stage is "
            "the ring ALGORITHM EMBEDDED in the full mesh (every hop a "
            "dedicated 1-hop pair at 64 B/ns per direction), never a claim "
            "that the anchor's topology is a ring",
        },
        "out_of_domain": {
            "pcie_gen5_host_link": "128 GB/s bidirectional per GPU to HOST — "
            "a host-attach leg, not the GPU-to-GPU scale-up fabric this "
            "platform models; recorded, not modeled (no observable consumes "
            "it)",
        },
    }


def registry_coincidences() -> dict:
    """Placement facts against the free-parameter registry points (values
    untouched — these are placements, not changes)."""
    return {
        "A-L0-BW_point_64_equals_anchor_per_link_per_direction": {
            "registry_point_bytes_per_ns": "64",
            "anchor_per_link_per_direction_bytes_per_ns": "64",
            "offset": "0 (exact)",
            "note": "the smoke default of the free per-link axis sits ON this "
            "anchor's per-direction per-link rate — the only core anchor in "
            "the set whose per-link rate coincides with a registry default; "
            "KEEP (point) verdict of plan §2.1 A-L0-BW needs no change for "
            "this anchor",
        },
        "A-L0X-BW_span_endpoint_448_equals_anchor_aggregate": {
            "span_endpoint_bytes_per_ns": "448",
            "anchor_aggregate_per_direction_bytes_per_ns": "448",
            "offset": "0 (exact)",
            "note": "stage A2 already swept this 448 as the lower endpoint of "
            "its [448, 900] aggregate span (crossbar72_a2_span448_v1); THIS "
            "stage works the anchor itself and derives 448 from CAL-A7's own "
            "numbers (7 x 64) at the anchor's own r=8 — the two stages' "
            "derivations agree exactly, a cross-stage consistency note",
        },
    }


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_ring(m: int, b: Fraction) -> Fraction:
    """t = 2(r-1)/r * M/B + 2(r-1)*L  (src/essun/backends/analytical/l0.py)."""
    return Fraction(2 * (R - 1) * m, R) / b + 2 * (R - 1) * L


def t_xbar(m: int, b: Fraction) -> Fraction:
    """t = 2(r-1)/r * M/B + 2*L  (l0_crossbar.py)."""
    return Fraction(2 * (R - 1) * m, R) / b + 2 * L


def t_doubling(m: int, b: Fraction) -> Fraction:
    """t = 2(r-1)/r * M/B + 2*log2(r)*L  (l0_recursive_doubling.py)."""
    return Fraction(2 * (R - 1) * m, R) / b + 2 * 3 * L  # log2(8) = 3


def t_multiport_mesh(m: int, b: Fraction) -> Fraction:
    """DECLARED (unimplemented) multi-port full-mesh identity: RS and AG each
    send r-1 chunks of M/r over DEDICATED per-pair links in parallel, so a
    phase costs (M/r)/b + L and AllReduce costs 2*(M/r)/b + 2L."""
    return 2 * Fraction(m, R) / b + 2 * L


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str, ceiling: Fraction) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    wire = Fraction(per_op["per_rank_wire_bytes_exact"])
    busbw = wire / cct  # NCCL busbw convention: 2(r-1)/r * M / t
    model = obs["model"]
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": model["ranks"],
            "backend_id": obs["backend_id"],
            "transport_model": model["transport_model"],
            "bandwidth_param_exact": model.get("link_bytes_per_ns_exact")
            or model.get("injection_bytes_per_ns_exact"),
            "latency_param_exact": model.get("hop_latency_ns_exact")
            or model.get("pair_latency_ns_exact"),
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "implied_busbw_bytes_per_ns_exact": str(busbw),
        "implied_busbw_bytes_per_ns_float": float(busbw),
        "anchor_ceiling_bytes_per_ns": str(ceiling),
        "fraction_of_ceiling_exact": str(busbw / ceiling),
        "fraction_of_ceiling_float": float(busbw / ceiling),
        "absolute_delta_busbw_minus_ceiling_exact": str(busbw - ceiling),
    }


def sweep_rows(sweep_id: str, b_by_topology: dict[str, tuple[Fraction, str]]) -> dict:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    rows_by_size: dict[int, list[dict]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        b, label = b_by_topology[topo]
        size = row["payload_bytes"]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        busbw = wire / cct
        rows_by_size.setdefault(size, []).append(
            {
                "topology_id": topo,
                "config_id": row["config_id"],
                "reading": label,
                "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
                "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
                "delta_vs_anchor_point_exact": row["delta_vs_baseline"]["delta_exact"],
                "delta_vs_anchor_point_float": row["delta_vs_baseline"]["delta_float"],
                "implied_busbw_bytes_per_ns_exact": str(busbw),
                "implied_busbw_bytes_per_ns_float": float(busbw),
            }
        )
    ladder = [
        {"payload_bytes": size, "rows": rows}
        for size, rows in sorted(rows_by_size.items())
    ]
    return {
        "sweep_id": sweep_id,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "ladder": ladder,
    }


def equivalence_and_relations() -> dict:
    """The stage's central exact-arithmetic findings, every one cross-checked
    against EXECUTED artifacts (run store + sweep tables) by exact Fraction
    string equality; closed-form-only statements are declared inline."""
    # --- 1. aggregate-reading coincidence with the multi-port mesh identity ---
    coincidences = []
    for m in LADDER:
        t_mp = t_multiport_mesh(m, B_PER_LINK_PER_DIR)
        t_x = t_xbar(m, B_AGGREGATE_PER_DIR)
        assert t_mp == t_x, (m, t_mp, t_x)  # term-by-term equality, exact
        coincidences.append(
            {"payload_bytes": m,
             "multiport_mesh_closed_form_ns_exact": str(t_mp),
             "crossbar_agg448_closed_form_ns_exact": str(t_x)}
        )
    # cross-check the closed form against the EXECUTED agg-sweep baseline rows
    agg = load_json(RESULTS / "sweeps" / SWEEP_ID_AGG / "table.json")
    for row in agg["configs"]:
        if row["config_id"].split("-")[2] == "crossbar8_a7_agg448_v1":
            m = row["payload_bytes"]
            assert row["o_cct"]["completion_time_ns_mean_exact"] == str(
                t_xbar(m, B_AGGREGATE_PER_DIR)
            ), (m, row["config_id"])

    # --- 2. ring 7x relation: t_ring(64) == 7 * t_xbar(448), every size ---
    link = load_json(RESULTS / "sweeps" / SWEEP_ID_LINK / "table.json")
    ring_rows = {
        row["payload_bytes"]: row["o_cct"]["completion_time_ns_mean_exact"]
        for row in link["configs"]
        if row["config_id"].split("-")[2] == "ring8_a7_link64_v1"
    }
    xbar_rows = {
        row["payload_bytes"]: row["o_cct"]["completion_time_ns_mean_exact"]
        for row in agg["configs"]
        if row["config_id"].split("-")[2] == "crossbar8_a7_agg448_v1"
    }
    seven_fold = []
    for m in LADDER:
        lhs = Fraction(ring_rows[m])
        rhs = 7 * Fraction(xbar_rows[m])
        assert lhs == rhs, (m, lhs, rhs)  # executed artifacts, exact equality
        assert lhs == t_ring(m, B_PER_LINK_PER_DIR)  # and matches closed form
        seven_fold.append(
            {"payload_bytes": m,
             "ring_link64_cct_ns_exact": ring_rows[m],
             "seven_times_crossbar_agg448_ns_exact": str(rhs)}
        )

    # --- 3. latency-chain spectrum at equal aggregate B=448 ---
    doubling = load_json(RESULTS / "sweeps" / SWEEP_ID_DOUBLING / "table.json")
    chain_rows = []
    for row in doubling["configs"]:
        m = row["payload_bytes"]
        t_d = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert t_d == t_doubling(m, B_AGGREGATE_PER_DIR)  # closed-form cross-check
        t_x = Fraction(xbar_rows[m])
        assert t_d - t_x == 4 * L, (m, t_d - t_x)  # 2*(log2(r)-1)*L = 4L = 800 ns
        chain_rows.append(
            {"payload_bytes": m,
             "doubling_agg448_cct_ns_exact": str(t_d),
             "crossbar_agg448_cct_ns_exact": xbar_rows[m],
             "difference_exact": str(t_d - t_x)}
        )

    # --- 4. per-pair expressiveness loss (anchor-anchor arithmetic; no run) ---
    s = Fraction(2**20)  # a representative single-pair transfer, 1 MiB
    pair_time_physical = s / B_PER_LINK_PER_DIR + L
    pair_time_xbar448 = s / B_AGGREGATE_PER_DIR + L

    return {
        "aggregate_reading_multiport_equivalence": {
            "claim": "for the symmetric uniform-chunk reduce-scatter + "
            "allgather AllReduce identity at r=8, the single-port crossbar "
            "identity at B=(r-1)*64=448 B/ns coincides TERM BY TERM with the "
            "declared (unimplemented) multi-port full-mesh identity at "
            "per-pair 64 B/ns: both t = 2*M/(r*64) + 2L",
            "proof_shape": "single-port phase: (r-1)/r*M/((r-1)*64) = M/(r*64); "
            "multi-port phase: r-1 chunks of M/r over dedicated links in "
            "parallel = M/(r*64) — identical bandwidth terms, identical one-"
            "per-phase pair latency 2L",
            "verified_at_all_12_ladder_sizes": coincidences,
            "cross_check": "the closed form equals every executed "
            "crossbar8_a7_agg448_v1 sweep row by exact Fraction string "
            "equality (36 rows include the baseline at all 12 sizes)",
            "scope_limit": "the equivalence holds for THIS symmetric "
            "collective only — it is not a claim that the single-port "
            "abstraction equals the mesh; the expressiveness loss is "
            "quantified below",
        },
        "ring_seven_fold_relation": {
            "claim": "the ring ALGORITHM embedded in the mesh at the per-pair "
            "rate 64 B/ns takes exactly 7x the completion time of the "
            "aggregate-reading crossbar at 448 B/ns, at every payload size: "
            "t_ring(64) = (r-1) * t_xbar((r-1)*64) is an identity (both the "
            "bandwidth term and the latency chain scale by r-1=7: 2(r-1)L = "
            "7*2L)",
            "verified_at_all_12_ladder_sizes": seven_fold,
            "cross_check": "both sides are EXECUTED sweep rows (ring sweep "
            "c0002 rows vs agg sweep c0002 rows); equality is exact Fraction "
            "equality on artifacts, not only closed forms",
            "note": "a ring uses 1 of the 7 outgoing per-pair links per rank, "
            "so its implied-busbw ceiling is exactly 1/7 of the aggregate "
            "reading (64 vs 448 B/ns) — the two available L0 readings of one "
            "anchor bracket the fabric's usable capacity by exactly 7x",
        },
        "latency_chain_spectrum_at_agg448": {
            "claim": "at equal aggregate B=448, the three single-port "
            "identities share the bandwidth term and differ only in the "
            "latency chain: crossbar 2L=400 ns, doubling 2*log2(8)*L=1200 ns, "
            "and the doubling-minus-crossbar difference is exactly "
            "2*(log2(r)-1)*L = 4L = 800 ns at every size — the backend's own "
            "declared design-space relation, here verified against executed "
            "artifacts (and reachable only through the sweep path; see "
            "run_path_gate_finding)",
            "verified_at_all_12_ladder_sizes": chain_rows,
        },
        "per_pair_expressiveness_loss": {
            "role": "quantifies plan §2.1 A-L0X-PORT OUT-OF-DOMAIN for this "
            "fabric class — what the aggregate reading cannot express",
            "example_single_pair_transfer_bytes": str(s),
            "physical_per_pair_time_ns_exact": str(pair_time_physical),
            "crossbar_agg448_time_ns_exact": str(pair_time_xbar448),
            "bandwidth_term_overestimate_factor": "7 (exact: (r-1)) — the "
            "aggregate abstraction predicts a single-pair transfer 7x faster "
            "than any dedicated pair can carry",
            "mirror_note": "conversely the per-pair-cap conservative reading "
            "(crossbar8_a7_pair64_v1, one shared 64 B/ns port) understates "
            "the mesh's parallel injection capability by exactly 7x in the "
            "symmetric identity — the true per-pair structure lies BETWEEN "
            "the two rows and is inexpressible in the single-port input space",
            "provenance": "anchor-anchor arithmetic on CAL-A7's own staged "
            "numbers (declared interpretation); no run id by construction",
        },
    }


def run_path_gate_finding() -> dict:
    """Structural finding discovered by this stage (classified, not fixed)."""
    return {
        "finding": "the run path's collective-capability gate "
        "(_supported_collectives in src/essun/orchestrator/runs.py) strips "
        "exactly one '_'-segment from declared capability names, so the "
        "two-word algorithm suffixes 'allreduce_recursive_doubling' (and the "
        "phase-collectives 'reducescatter_recursive_halving' / "
        "'allgather_recursive_doubling') normalize to 'allreduce_recursive' "
        "etc. and can never match the bare 'allreduce'/'reducescatter' the "
        "W1/W2 generators issue — although the doubling backend's own "
        "execute() accepts exactly 'allreduce'",
        "classification": "STRUCTURAL (naming-convention mismatch between "
        "capability declarations and the gate's suffix-strip normalization), "
        "not a parameter mismatch; no manifest or parameter choice can route "
        "a W1 run manifest to the doubling backend today",
        "consequence_for_this_stage": "the doubling anchor point was executed "
        "through the SWEEP path (which registers the algorithm id "
        "directly and generates its own ops), sweep_a7_doubling_v1.yaml — "
        "content-addressed rows, same gates otherwise",
        "scope_discipline": "no src/ change was made by this stage (p1 stage "
        "boundary: new files under experiments/calibration/ only); the fix "
        "decision belongs to the owner",
    }


def main() -> int:
    derived = anchor_derived()

    link_sweep = sweep_rows(
        SWEEP_ID_LINK,
        {
            "ring8_a7_link20_v1": (Fraction(20), "span lower endpoint (CAL-A12 NCCL per-link software model; cross-fabric transfer, labeled)"),
            "ring8_a7_link50_v1": (Fraction(50), "cross-generation endpoint (CAL-A1 NVLink5 per-port = CAL-A5 ICI reading-1)"),
            "ring8_a7_link64_v1": (Fraction(64), "CAL-A7 anchor point (per-link per-direction; = A-L0-BW registry point)"),
        },
    )
    agg_sweep = sweep_rows(
        SWEEP_ID_AGG,
        {
            "crossbar8_a7_pair64_v1": (Fraction(64), "per-pair-cap conservative reading (one shared 64 B/ns port)"),
            "crossbar8_a7_derated358_4_v1": (Fraction("358.4"), "CAL-A12 ~80% software-derating bridge (cross-fabric transfer, labeled)"),
            "crossbar8_a7_agg448_v1": (Fraction(448), "CAL-A7 aggregate anchor point (7 x 64 B/ns per direction)"),
        },
    )
    doubling_sweep = sweep_rows(
        SWEEP_ID_DOUBLING,
        {"exchange8_a7_agg448_v1": (Fraction(448), "CAL-A7 aggregate anchor point, recursive-doubling identity")},
    )

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A7 (anchor CAL-A7)",
        "anchor": {
            "anchor_id": "CAL-A7",
            "title": "AMD Instinct MI300X: Infinity Fabric scale-up bandwidth",
            "source_row": "the anchor registry row CAL-A7 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A7",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A7",
            "urls": [
                "https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/data-sheets/amd-instinct-mi300x-platform-data-sheet.pdf",
                "https://hc2024.hotchips.org/assets/program/conference/day1/23_HC2024.AMD.MI300X.ASmith(MI300X).v1.Final.20240817.pdf",
                "Lenovo LP1943 (confirmation quote, as staged)",
            ],
            "confidence": "H for transcription; SPEC, not measurement — ceiling "
            "only, never an achieved value; the per-direction split is the "
            "calibration plan's stated convention for this anchor; the "
            "datasheet-vs-Hot-Chips topology wording differs (see "
            "topology_ambiguity)",
            "staged_numbers": "7 bidirectional Infinity Fabric links per GPU, "
            "each 128 GB/s; 896 GB/s aggregate bidirectional per GPU across "
            "the 8-GPU fully connected domain; PCIe Gen5 x16 (128 GB/s) per "
            "GPU to host — numbers as staged in anchors_staging.md §A7 "
            "(staging-doc transcription; no verbatim quote strings are "
            "claimed by this record)",
        },
        "target": {
            "role": "per_link_bw_and_fabric_class_anchor_nonswitched_full_mesh",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "CAL-A7 is a capacity "
            "specification, not a (size -> time) series; a CCT deviation is "
            "undefined against it (CALIBRATION_PLAN.md §1.1: 'Cannot "
            "calibrate O-CCT — specification. Per-link BW for the non-"
            "switched full-mesh class (per-pair dedicated links, no switch "
            "hop)'). The anchor's extractable targets are the per-link "
            "per-direction rate (64 B/ns), the per-GPU aggregate per "
            "direction (448 B/ns), the fabric class (non-switched full mesh, "
            "r=8, dedicated per-pair capacity), and the topology-wording "
            "ambiguity — all recorded here",
            "regime": {
                "topology_class": "non-switched full mesh (7 dedicated per-pair "
                "links per GPU); executed through the available L0 identities "
                "as TWO readings — ring (per-link, algorithm embedding) and "
                "single-port crossbar/doubling (aggregate; OUT-OF-DOMAIN as a "
                "physical description per plan §2.1 A-L0X-PORT, exact-"
                "equivalence arithmetic recorded)",
                "ranks": 8,
                "message_bytes_ladder": LADDER,
                "message_regime_note": "n/a (capacity spec); ladder spans 8 KiB "
                "(latency-bound) to 8 GiB (bandwidth-bound), every size 8*2^k "
                "so r=8 divides all (A-L0-DIV / A-L0X-DIV / A-L0D-DIV accept; "
                "r=8 is a power of two so A-L0D-POW2 accepts)",
            },
        },
        "anchor_derived": derived,
        "topology_ambiguity": topology_ambiguity(),
        "registry_coincidences": registry_coincidences(),
        "model": {
            "backends_executed": [
                "analytical_l0 (ring; per-link reading)",
                "analytical_l0_crossbar (aggregate reading)",
                "analytical_l0_recursive_doubling (aggregate reading, third "
                "latency chain; sweep path only — see "
                "run_path_gate_finding)",
            ],
            "identities": {
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L ; B=64 (per-link), L=200",
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; B in {64, 358.4, 448}, L=200",
                "doubling": "t = 2(r-1)/r*M/B + 2*log2(r)*L ; B=448, L=200",
                "multiport_mesh_declared_unimplemented": "t = 2*(M/r)/b + 2L ; "
                "b=64 — the per-pair structure itself; inexpressible in the "
                "landed single-port input space (closed form only, "
                "cross-checked against executed crossbar rows)",
            },
            "free_parameters": {
                "B_per_link_swept_bytes_per_ns": {
                    "20": "CAL-A12 NCCL per-link software model (span lower endpoint; cross-fabric transfer, labeled)",
                    "50": "CAL-A1 NVLink5 per-port = CAL-A5 ICI reading-1 (cross-generation endpoint)",
                    "64": "CAL-A7 anchor point (also exactly the A-L0-BW registry point)",
                },
                "B_injection_swept_bytes_per_ns": {
                    "64": "per-pair rate as a shared single port (per-pair-cap conservative reading)",
                    "358.4": "0.8 x 448 CAL-A12 derating bridge (cross-fabric transfer, labeled)",
                    "448": "CAL-A7 aggregate anchor point",
                },
                "L_ns": 200,
                "L_provenance": "A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry points (KEEP; latency axis deferred to its own global stage — the plan's weakest, anchor-free axis, gap §4.2)",
            },
            "assumptions": "A-L0-BW/A-L0-LAT/A-L0-FD/A-L0-DIV (ring); A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar); A-L0D-POW2/A-L0D-STEP/A-L0D-BW/A-L0D-LAT/A-L0D-DIV (doubling) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_RING_LINK64,
                    "per-link reading (ring algorithm embedded in the mesh; B=64 = the anchor's per-pair per-direction rate)",
                    RING_CEILING,
                ),
                run_summary(
                    RUN_ID_XBAR_AGG448,
                    "aggregate reading (single-port crossbar at B=448 = 7 x 64; exact-equivalent to the declared multi-port mesh identity for this symmetric collective)",
                    XBAR_CEILING,
                ),
            ],
            "reconciled_sweeps": {
                "link_per_link_reading": link_sweep,
                "aggregate_reading": agg_sweep,
                "doubling_anchor_point": doubling_sweep,
            },
            "equivalence_and_relations": equivalence_and_relations(),
            "run_path_gate_finding": run_path_gate_finding(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — the anchor "
            "publishes no time series; recorded per the stage's FAIL-clause "
            "duty instead of skipped because the anchor's actual role "
            "(per-link BW + fabric-class anchor of the non-switched full "
            "mesh) IS extractable and is executed above",
            "placement_summary": "both readings approach but never exceed "
            "their respective spec ceilings (at the 512 MiB anchor point the "
            "ring sits at 131072/131097 = 0.99981 of 64 B/ns and the "
            "crossbar at the IDENTICAL fraction of 448 — same wire bytes, "
            "CCT ratio exactly 7); asymptotic busbw ceilings are exactly 64 "
            "(per-link reading) and 448 (aggregate reading), ratio exactly 7 "
            "= r-1; the derated row converges to exactly 0.8 x 448 = 358.4 "
            "by construction of that swept point (locates where a "
            "CAL-A12-style software-scheduled measurement would sit IF the "
            "derating transferred across fabrics — not an independent "
            "validation)",
            "span_placement": "CCT ratios vs the anchor points are arithmetic "
            "facts of 1/B (asymptotically exactly +2.2 at B=20 and +0.28 at "
            "B=50 for the ring; +6.0 at B=64-pair and +0.25 at 358.4 for the "
            "crossbar; the sweep tables record exact per-size values "
            "including the latency terms)",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the "
            "per-link/fabric-class role; no E3/E4 language — CAL-A7 is an "
            "external published specification, not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_RING_LINK64, RUN_ID_XBAR_AGG448],
            "sweep_ids": [SWEEP_ID_LINK, SWEEP_ID_AGG, SWEEP_ID_DOUBLING],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_LINK}",
                f"results/sweeps/{SWEEP_ID_AGG}",
                f"results/sweeps/{SWEEP_ID_DOUBLING}",
            ],
            "run_backed_numbers": "every model output in "
            "comparison.anchor_point_runs and comparison.reconciled_sweeps; "
            "comparison.equivalence_and_relations cross-checks closed forms "
            "against those executed artifacts by exact Fraction string "
            "equality (declared inline); per_pair_expressiveness_loss is "
            "anchor-anchor arithmetic by construction (no run ids claimed)",
            "inputs": [
                "experiments/calibration/a7/sweep_a7_link_v1.yaml",
                "experiments/calibration/a7/sweep_a7_agg_v1.yaml",
                "experiments/calibration/a7/sweep_a7_doubling_v1.yaml",
                "experiments/calibration/a7/run_a7_link_anchor_v1.yaml",
                "experiments/calibration/a7/run_a7_agg_anchor_v1.yaml",
                "experiments/calibration/a7/workloads/w1_dense_tp_decode_tp8_512mib.yaml",
                "experiments/calibration/a7/topologies/ (7 files)",
                "experiments/calibration/a7/profiles/ (3 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/a7/run_a7_link_anchor_v1.yaml ; "
            "make run EXP=experiments/calibration/a7/run_a7_agg_anchor_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a7/sweep_a7_link_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a7/sweep_a7_agg_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a7/sweep_a7_doubling_v1.yaml ; "
            "python experiments/calibration/a7/build_calibration_record.py",
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
