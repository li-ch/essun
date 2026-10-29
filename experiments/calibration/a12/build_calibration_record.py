"""Build the PROPOSED calibration-candidate record for anchor CAL-A12 (Q1
calibration-ladder stage A12, the FINAL core anchor.
docs/calibration/CALIBRATION_PLAN.md).

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_staging.md`` §A12
(declared with provenance) or verified against the primary source thread
on 2026-10-28 (verification method and quotes recorded inline), or (b)
computed from the stored run/sweep artifacts by this script (closed-form
cross-checks by exact Fraction string equality on every executed row), or
(c) anchor-anchor arithmetic in the bridge audit (CAL-A3/A6 staged series
vs the CAL-A12 derating and the ceilings of CAL-A2/A6/A7; no model run
backs those rows and none is claimed). Nothing is tuned: the swept B
values carry their anchor provenance, and the record measures where the
model output sits relative to the anchor.

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
RUN_ID_PHYS300 = "03cef574cd77354e3213e69282c24be66d3d5f4626ffb44e59a998b1eaba5b88"
RUN_ID_NCCL240 = "97c28d7bddfb6ab2cfe8ee018318bea3bbc84aaf04a1d852e0f71e8be275f25d"
SWEEP_ID_AGG = "26e2a68ca126a458988034012ee0f7fb03ab3da01e9132ee552a01f61a6e2f92"
SWEEP_ID_LINK = "3f31262a8605bf61867a176b887dd4c05998a507fb289d29e3349e93980e9a50"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A12 staged numbers (docs/calibration/anchors_staging.md §A12;
# confidence M per the staging doc — the reply text came via search snippet
# there; this stage re-verified the thread on 2026-10-28, see `verification`).
# Decimal unit convention of the calibration plan: 1 GB/s = 1 B/ns.
NVLINK3_LINKS_PER_GPU = 12
PHYSICAL_PER_LINK_GBPS = Fraction(25)   # per link, per direction (nvidia-smi class total 300)
NCCL_MODEL_PER_LINK_GBPS = Fraction(20)  # per link, per direction (src/graph/topo.h)
PHYSICAL_TOTAL_GBPS = Fraction(300)      # nvidia-smi nvlink -s total (issue body)
NCCL_TOTALBW_GBPS = Fraction(240)        # system->totalBw at ncclTopoSearchInit (issue body)

# Closed-form identities at r=8, L=200 ns (the executed configurations):
#   wire bytes per rank  w = 2*(r-1)/r * M = 7*M/4  (identical for both
#   identities — same collective, same r);
#   crossbar  t = w/B + 2L          (L=200 -> +400)
#   ring      t = w/B + 2*(r-1)*L   (L=200 -> +2800)
R = 8
L = Fraction(200)
WIRE_FACTOR = Fraction(2 * (R - 1), R)  # 7/4
CROSSBAR_LAT = 2 * L                    # 400
RING_LAT = 2 * (R - 1) * L              # 2800

# Bridge-audit anchor-anchor arithmetic inputs (staged numbers only):
# CAL-A2 line (stage A2 record: 900 B/ns per GPU per direction, exact from
# the per-GPU quote); CAL-A3 measured out-of-place busbw (GB/s); CAL-A6
# rail 400 B/ns + 2.19.3 time-implied busbw rows (the internally consistent
# series); CAL-A7 aggregate 448 B/ns (7 x 64); the three shipped bridge
# usages 720 / 320 / 358.4.
A2_LINE = Fraction(900)
A3_BUSBW = {
    "2GiB": Fraction("787.95"),
    "4GiB": Fraction("831.03"),
    "8GiB": Fraction("866.36"),
    "16GiB": Fraction("890.32"),
    "32GiB": Fraction("906.94"),
}
A3_BUSBW_AVG = Fraction("855.949")
A6_RAIL = Fraction(400)
A6_BUSBW_2193 = {
    "1GiB": Fraction("385.41"),
    "16GiB": Fraction("391.10"),
}
A7_AGG = Fraction(448)
BRIDGE_USAGES = {
    "stage_A2_crossbar72_derated720": Fraction(720),
    "stage_A6_ring32_derated320": Fraction(320),
    "stage_A7_crossbar8_derated358_4": Fraction("358.4"),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_derived() -> dict:
    """Arithmetic consequences of CAL-A12's own staged numbers."""
    physical_total = NVLINK3_LINKS_PER_GPU * PHYSICAL_PER_LINK_GBPS  # 300
    nccl_total = NVLINK3_LINKS_PER_GPU * NCCL_MODEL_PER_LINK_GBPS    # 240
    derating = NCCL_MODEL_PER_LINK_GBPS / PHYSICAL_PER_LINK_GBPS     # 4/5
    derating_total = nccl_total / physical_total                     # 4/5

    # Self-checks: the staged numbers must produce these exact values;
    # anything else is a transcription bug, not a finding.
    assert physical_total == PHYSICAL_TOTAL_GBPS == 300
    assert nccl_total == NCCL_TOTALBW_GBPS == 240
    assert derating == derating_total == Fraction(4, 5)
    assert Fraction(192) == Fraction(4, 5) ** 2 * physical_total
    assert Fraction(16) == Fraction(4, 5) ** 2 * PHYSICAL_PER_LINK_GBPS

    return {
        "staged_numbers": {
            "links_per_gpu": NVLINK3_LINKS_PER_GPU,
            "physical_per_link_GB_per_s_per_direction": "25",
            "nccl_model_per_link_GB_per_s_per_direction": "20",
            "physical_total_GB_per_s_per_gpu_per_direction": "300",
            "nccl_system_totalBw_GB_per_s": "240",
        },
        "derived_arithmetic": {
            "aggregate_physical_bytes_per_ns": str(physical_total),
            "aggregate_nccl_model_bytes_per_ns": str(nccl_total),
            "derating_per_link_exact": str(derating),
            "derating_aggregate_exact": str(derating_total),
            "derating_float": float(derating),
            "double_application_exact": str(Fraction(4, 5) ** 2),
            "double_application_value_at_aggregate": "192",
            "double_application_value_per_link": "16",
        },
        "derating_semantics": {
            "one_derating_not_two": (
                "The verified maintainer reply (sjeaugey, quoted under "
                "`verification`) explains NCCL's 20 GB/s/link as the app-level "
                "bandwidth: 'Roughly, the app-level bandwidth is 80% of the peak "
                "bandwidth', cause 'an overhead for NVLink packets'. 20/25 = 4/5 "
                "and the ~80% guidance are therefore ONE derating, not a derating "
                "composed with a second one."
            ),
            "cause_class": "NVLink packet overhead (protocol/flit axis, below L0 fidelity)",
            "roughness": "the reply says 'roughly'; 240/300 = 4/5 exactly is the "
            "constant NCCL ships in topo.h, the ~80% is the maintainer's gloss",
        },
    }


def verification() -> dict:
    """The staging doc's M-confidence caveat (reply text via search
    snippet, 'verify the reply text at integration') was worked by this
    stage: the public thread was fetched and the reply wording extracted."""
    return {
        "method": "WebFetch of https://github.com/NVIDIA/nccl/issues/1054 "
        "(thread rendered server-side, issue body + replies), 2026-10-28; "
        "issue body independently cross-checked verbatim by a second fetch "
        "method (web reader) the same day.",
        "issue_body_verified": (
            "8-GPU A100 server; 'the system->totalBw obtained at ncclTopoSearchInit "
            "was only 240GB/s' while 'nvidia-smi nvlink -s' shows a total NVLink "
            "bandwidth of 300GB/s; src/graph/topo.h defines an NVLink at 20GB/s "
            "per link instead of 25GB/s. (Poster: PhdShi, Nov 6 2023.)"
        ),
        "maintainer_reply_verified": (
            "sjeaugey (NVIDIA/NCCL maintainer), Nov 6 2023, sole reply: 'The NVLink "
            "peak bandwidth and the real application-level bandwidth are different, "
            "since there is an overhead for NVLink packets.' / 'Roughly, the app-level "
            "bandwidth is 80% of the peak bandwidth.'"
        ),
        "caveat_resolution": (
            "Staging-doc caveat 'the 20 GB/s/link and ~80% figures come from the "
            "issue thread via search snippet — verify the reply text at integration' "
            "is RESOLVED by this stage's fetch: the reply exists, is the only reply, "
            "and states both facts as one explanation (see derating_semantics). "
            "CALIBRATION_PLAN.md §3 precondition 1 (M-confidence flags re-verified "
            "at owner-gated promotion) is thereby pre-served with evidence the "
            "owner can re-check."
        ),
        "residual_caveat": (
            "The reply text above is a tool extraction of the rendered thread "
            "(two independent methods for the body, one for the reply); the owner "
            "may re-verify wording at adjudication. The thread is a Q&A about "
            "NCCL's internal model, not a benchmark: NO achieved-bandwidth "
            "measurement is staged by this anchor — the derating is a software-"
            "stack model constant plus a maintainer's roughness statement."
        ),
    }


def crossbar_time(payload: int, b: Fraction) -> Fraction:
    return WIRE_FACTOR * payload / b + CROSSBAR_LAT


def ring_time(payload: int, b: Fraction) -> Fraction:
    return WIRE_FACTOR * payload / b + RING_LAT


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    cct = Fraction(per_op["completion_time_ns_exact"])
    payload = per_op["payload_bytes"]
    b = Fraction(obs["model"]["injection_bytes_per_ns_exact"])
    # Closed-form cross-check (exact): the executed value must equal the
    # identity function on the manifest's own inputs.
    assert cct == crossbar_time(payload, b), (run_id, cct)
    wire = Fraction(per_op["per_rank_wire_bytes_exact"])
    assert wire == WIRE_FACTOR * payload
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": obs["model"]["ranks"],
            "injection_bytes_per_ns_exact": obs["model"]["injection_bytes_per_ns_exact"],
            "pair_latency_ns_exact": obs["model"]["pair_latency_ns_exact"],
        },
        "payload_bytes": payload,
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "closed_form_check": "exact equality vs 7/4*M/B + 2L (asserted in builder)",
    }


def sweep_table(sweep_id: str, closed_form, b_by_topo: dict[str, Fraction],
                asymptote_note: str) -> dict:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    by_size: dict[int, dict[str, dict]] = {}
    for row in table["configs"]:
        topo = row["config_id"].split("-")[2]
        payload = row["payload_bytes"]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        b = b_by_topo[topo]
        # Closed-form cross-check (exact) on EVERY executed row.
        assert cct == closed_form(payload, b), (row["config_id"], cct)
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        assert wire == WIRE_FACTOR * payload
        by_size.setdefault(payload, {})[topo] = {
            "topology_id": topo,
            "config_id": row["config_id"],
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
            "delta_vs_physical_point_exact": (
                row["delta_vs_baseline"]["delta_exact"]
                if row["delta_vs_baseline"] else "0"
            ),
            "delta_vs_physical_point_float": (
                row["delta_vs_baseline"]["delta_float"]
                if row["delta_vs_baseline"] else 0.0
            ),
            "latency_share_of_cct_exact": str(
                (CROSSBAR_LAT if closed_form is crossbar_time else RING_LAT) / cct
            ),
        }
    ladder = []
    for payload, topos in sorted(by_size.items()):
        ladder.append({"payload_bytes": payload, "rows": [
            topos[t] for t in sorted(topos, key=lambda t: -b_by_topo[t])
        ]})
    return {
        "sweep_id": sweep_id,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "the PHYSICAL point (delta columns measure placement vs it)",
        "asymptotic_deltas_exact": asymptote_note,
        "message_size_ladder": ladder,
    }


def bridge_execution() -> dict:
    """The bridge executed end-to-end on the anchor's own fabric: two store
    runs differing ONLY in B (300 -> 240), plus both sweep twins."""
    o1 = load_json(RESULTS / RUN_ID_PHYS300 / "observations.json")
    o2 = load_json(RESULTS / RUN_ID_NCCL240 / "observations.json")
    t300 = Fraction(o1["per_op"][0]["completion_time_ns_exact"])
    t240 = Fraction(o2["per_op"][0]["completion_time_ns_exact"])
    ratio = t240 / t300
    pure = Fraction(5, 4)
    # The executed ratio must sit strictly below 5/4 (the +2L latency term
    # is B-independent) and converge to it as M grows.
    assert ratio < pure
    return {
        "store_run_pair": [
            run_summary(RUN_ID_PHYS300,
                        "physical point (B=300 = 12 x 25; the ceiling NCCL derates FROM)"),
            run_summary(RUN_ID_NCCL240,
                        "NCCL topo-model point (B=240 = 12 x 20; the issue's system->totalBw)"),
        ],
        "cct_ratio_nccl_over_physical_exact": str(ratio),
        "cct_ratio_nccl_over_physical_float": float(ratio),
        "asymptotic_ratio_exact": "5/4",
        "asymptotic_ratio_float": 1.25,
        "distance_to_asymptote_exact": str(pure - ratio),
        "note": "identical workload, rank count and L; only B differs, so this "
        "ratio IS the CAL-A12 derating executed through the identity — the "
        "bridge prior stages applied to OTHER fabrics' ceilings, run here on "
        "the anchor's own fabric class and rank count.",
    }


def granularity_axis() -> dict:
    """Ring (per-link axis) vs crossbar (aggregate axis): the anchor's own
    two granularities. Same wire bytes, B differing by exactly the 12-link
    factor, latency chains 2800 vs 400 ns."""
    agg = load_json(RESULTS / "sweeps" / SWEEP_ID_AGG / "table.json")
    lnk = load_json(RESULTS / "sweeps" / SWEEP_ID_LINK / "table.json")
    agg_by_size = {r["payload_bytes"]: Fraction(r["o_cct"]["completion_time_ns_mean_exact"])
                   for r in agg["configs"] if "physical300" in r["config_id"]}
    lnk_by_size = {r["payload_bytes"]: Fraction(r["o_cct"]["completion_time_ns_mean_exact"])
                   for r in lnk["configs"] if "physical25" in r["config_id"]}
    rows = []
    for payload in sorted(agg_by_size):
        ratio = lnk_by_size[payload] / agg_by_size[payload]
        assert ratio < 12  # latency chains soften the pure 12x bandwidth-axis gap
        rows.append({
            "payload_bytes": payload,
            "ring_per_link_over_crossbar_aggregate_exact": str(ratio),
            "ring_per_link_over_crossbar_aggregate_float": float(ratio),
        })
    return {
        "axis": "per-link (ring, B = one NVLink's rate) vs per-GPU aggregate "
        "(crossbar, B = 12-link total) — the two granularities at which the "
        "anchor states its 20-vs-25 figures",
        "bandwidth_term_ratio_exact": "12 (the anchor's own links-per-GPU count)",
        "latency_chain_ratio_exact": "7 (14L vs 2L)",
        "per_size_rows": rows,
        "note": "mirrors stage A7's 7x mesh bracket with the NVSwitch-class "
        "factor 12: the per-link and aggregate readings of one anchor's "
        "numbers differ by exactly the link count in the bandwidth term — "
        "an axis statement, never a tuning choice.",
    }


def double_application_hazard() -> dict:
    """The verified thread forecloses reading CAL-A12 as two composed
    deratings; the hazard rows (192 / 16 B/ns = 0.8^2 x physical) quantify
    what the misreading would do, and the ladder audit checks no shipped
    bridge usage composed it."""
    audits = {}
    for name, value in BRIDGE_USAGES.items():
        base = {"stage_A2_crossbar72_derated720": A2_LINE,
                "stage_A6_ring32_derated320": A6_RAIL,
                "stage_A7_crossbar8_derated358_4": A7_AGG}[name]
        assert value == Fraction(4, 5) * base  # single application, exact
        audits[name] = {
            "bridge_value": str(value),
            "base_ceiling": str(base),
            "applications_of_0.8": 1,
            "check": "value == 4/5 * base exactly (single application)",
        }
    return {
        "hazard_statement": (
            "If NCCL's 20 GB/s/link model were (wrongly) treated as a SECOND "
            "derating on top of the ~80% app-level guidance — the verified reply "
            "states they are the same fact — the effective factor would be "
            "0.64 (busbw 64% of peak instead of 80%) and CCT would be inflated "
            "by 240/192 = 5/4 = +25% relative to the correct bridge point "
            "(asymptotic executed delta vs physical: 9/16 = +56.25% instead of "
            "1/4 = +25%)."
        ),
        "hazard_rows_asymptotic_delta_vs_physical_exact": {
            "correct_bridge (240/300 aggregate, 20/25 per-link)": "1/4",
            "double_application (192/300, 16/25)": "9/16",
        },
        "ladder_usage_audit": audits,
        "audit_conclusion": "all three shipped bridge usages of CAL-A12 in the "
        "calibration ladder (stages A2/A6/A7) are SINGLE applications of 4/5 — "
        "the double-application hazard is quantified here but occurs nowhere.",
    }


def bridge_vs_measured_audit() -> dict:
    """Anchor-anchor arithmetic (no run ids by construction): what the
    anchor set's own measured series say about the 0.8 bridge's realism on
    the fabrics it was used to normalize. CAL-A3 staged busbw vs the CAL-A2
    900 line; CAL-A6 2.19.3 time-implied busbw vs the 400 rail."""
    a3_rows = []
    for size, busbw in A3_BUSBW.items():
        frac = busbw / A2_LINE
        a3_rows.append({
            "size": size,
            "busbw_GB_per_s": str(busbw),
            "fraction_of_900_line_exact": str(frac),
            "fraction_of_900_line_float": float(frac),
            "bridge_0.8_gap_pp_float": float((frac - Fraction(4, 5)) * 100),
        })
    a6_rows = []
    for size, busbw in A6_BUSBW_2193.items():
        frac = busbw / A6_RAIL
        # CCT inflation if the 0.8 bridge (320 B/ns) were used to predict:
        # predicted CCT / measured CCT = measured busbw / bridge busbw.
        inflation = busbw / (Fraction(4, 5) * A6_RAIL)
        a6_rows.append({
            "size": size,
            "time_implied_busbw_GB_per_s_2_19_3": str(busbw),
            "fraction_of_400_rail_exact": str(frac),
            "fraction_of_400_rail_float": float(frac),
            "bridge320_cct_inflation_over_measured_exact": str(inflation - 1),
            "bridge320_cct_inflation_over_measured_float": float(inflation - 1),
        })
    return {
        "role": "the bridge's own realism audit — CAL-A12's plan-assigned role "
        "is mandatory normalization of spec ceilings against measured series; "
        "this measures the measured series against the bridge itself",
        "provenance": "CAL-A3 staged busbw (anchors_staging.md §A3, measured, "
        "NCCL 2.28.3, 72 GPUs, M-H); CAL-A2 line 900 (§A2 derivation); CAL-A6 "
        "2.19.3 time-implied busbw (§A6, internally consistent series); "
        "anchor-anchor arithmetic only, no run ids claimed",
        "cal_a3_vs_cal_a2_900_line": {
            "rows": a3_rows,
            "avg_fraction_exact": str(A3_BUSBW_AVG / A2_LINE),
            "avg_fraction_float": float(A3_BUSBW_AVG / A2_LINE),
        },
        "cal_a6_2193_vs_400_rail": {"rows": a6_rows},
        "finding": (
            "The two measured series the bridge normalizes run at 0.876-1.008 "
            "(avg 0.951) of the CAL-A2 line and 0.964-0.978 of the CAL-A6 rail: "
            "the NVLink-3-derived 0.8 is a CONSERVATIVE ENVELOPE, 15-18 "
            "percentage points below both measured series; using it to predict "
            "CCT would inflate predictions by +20.4-22.2% on the CAL-A6 series "
            "(exact per-row values above). Classification: CAL-A12 supplies a "
            "derating FACT and a mechanism (packet overhead) from one NVLink-3/"
            "NCCL observation; the factor is NOT a validated cross-generation "
            "constant — per-fabric mechanisms differ (context row below)."
        ),
        "cross_fabric_context_row": {
            "source": "gapfill staging doc GF-01 (ROCm blog, MI300X xGMI; NOT a "
            "CAL-A* anchor — context only): per-link usable 48 of 64 GB/s = 75%, "
            "mechanism CRC flits + packet-protocol overhead",
            "statement": "a second fabric's own measured derating (0.75, "
            "different mechanism) — supports 'per-fabric factor', not 0.8",
        },
        "smallest_size_note": (
            "CAL-A3's smallest staged size (2 GiB, fraction 0.8755) is the "
            "closest any measured anchor comes to the 0.8 bridge — one point, "
            "not a validation; A3's caveat class (unstated NVLink/IB path "
            "split) applies unchanged."
        ),
    }


def registry_placements() -> dict:
    per_link_registry = Fraction(64)
    return {
        "A_L0_BW_span_lower_endpoint": {
            "endpoint": "20",
            "owner": "THIS anchor ('20 (CAL-A12 NCCL model)' — CALIBRATION_PLAN.md "
            "§2.1 A-L0-BW numeric-axes preamble); executed by ring8_a12_nccl20_v1 "
            "on the anchor's own fabric class and rank count, so the endpoint is "
            "now backed by an executed artifact of the anchor it came from",
        },
        "registry_point_placements": {
            "A_L0_BW_point_64_over_nccl20_exact": str(per_link_registry / 20),
            "A_L0_BW_point_64_over_physical25_exact": str(per_link_registry / 25),
            "note": "the registry default 64 B/ns is 3.2x NCCL's model rate and "
            "2.56x the physical NVLink-3 per-link rate — placement facts only, "
            "values untouched",
        },
        "A_L0X_BW_scale": "the aggregate axis (240/300) sits inside the plan's "
        "candidate aggregate span [448, 900] scale discussion only partially — "
        "the A100-class aggregate (300) is BELOW that modern span's lower "
        "endpoint (448): a generation fact (NVLink-3 server vs NVLink-5/OAM "
        "racks), recorded, no range edit",
    }


def main() -> int:
    agg_b = {
        "crossbar8_a12_hazard192_v1": Fraction(192),
        "crossbar8_a12_nccl240_v1": Fraction(240),
        "crossbar8_a12_physical300_v1": Fraction(300),
    }
    link_b = {
        "ring8_a12_hazard16_v1": Fraction(16),
        "ring8_a12_nccl20_v1": Fraction(20),
        "ring8_a12_physical25_v1": Fraction(25),
    }
    agg_table = sweep_table(
        SWEEP_ID_AGG, crossbar_time, agg_b,
        "vs physical 300: 240 -> 1/4 (+25%), 192 -> 9/16 (+56.25%); the "
        "B-independent +2L term makes executed deltas strictly smaller",
    )
    link_table = sweep_table(
        SWEEP_ID_LINK, ring_time, link_b,
        "vs physical 25: 20 -> 1/4, 16 -> 9/16; the B-independent +14L term "
        "makes executed deltas strictly smaller (larger latency share than the "
        "crossbar twin at equal size)",
    )
    # Latency-regime vanishing: the smallest ladder size shows the bridge is
    # a bandwidth-axis quantity — pull the executed deltas at 8 KiB.
    small_agg = [e for e in agg_table["message_size_ladder"]
                 if e["payload_bytes"] == 8192][0]["rows"]
    small_link = [e for e in link_table["message_size_ladder"]
                  if e["payload_bytes"] == 8192][0]["rows"]
    vanishing = {
        "statement": "at the smallest ladder size (8 KiB) the derating moves "
        "CCT by far less than its asymptotic +25% — the bridge lives on the "
        "bandwidth axis and is nearly inoperative in the latency-bound regime "
        "(the smoke manifests' 16 KiB sits in exactly this regime: the bridge "
        "cannot be tested there, mirroring the plan's small-message gap §4.3)",
        "aggregate_8KiB_deltas": {
            r["topology_id"]: r["delta_vs_physical_point_exact"] for r in small_agg},
        "per_link_8KiB_deltas": {
            r["topology_id"]: r["delta_vs_physical_point_exact"] for r in small_link},
    }

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, stage A12 (anchor CAL-A12, final core "
        "anchor)",
        "anchor": {
            "anchor_id": "CAL-A12",
            "title": "NCCL GitHub issue #1054: NCCL's internal NVLink bandwidth model",
            "source_row": "the anchor registry row CAL-A12 "
            "(PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A12",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A12",
            "url": "https://github.com/NVIDIA/nccl/issues/1054",
            "confidence": "M per the staging doc (reply text via search snippet); "
            "the thread was re-fetched and the reply verified 2026-10-28 by this "
            "stage — see `verification`",
            "staged_numbers": "8-GPU A100 server; system->totalBw at "
            "ncclTopoSearchInit = 240 GB/s (12 links x 20 GB/s/link from "
            "src/graph/topo.h) vs physical 25 GB/s/link / 300 GB/s per direction "
            "(nvidia-smi nvlink -s); maintainer: app-level bandwidth roughly 80% "
            "of peak, cause NVLink packet overhead",
        },
        "target": {
            "role": "injection_bw_derating_bridge (the spec-to-measured bridge)",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "CALIBRATION_PLAN.md §1.1: 'Cannot "
            "calibrate O-CCT directly — it calibrates the bridge: the derating "
            "between physical-BW-based L0 predictions and what an NCCL-driven "
            "measurement (CAL-A3/A6) can express. Mandatory normalization "
            "whenever spec ceilings (CAL-A1/A2/A7) are compared with measured "
            "series.' The anchor publishes no (size -> time) series and no "
            "achieved-bandwidth measurement; its extractable targets are the "
            "per-link pair (20, 25) B/ns, the aggregate pair (240, 300) B/ns, "
            "the exact derating 4/5 joining them, and the single-derating "
            "semantics — all recorded and executed here.",
            "regime": {
                "topology_class": "NVSwitch fat-tree class of an 8-GPU A100 "
                "server (DGX-A100 class); executed on the L0 crossbar "
                "(aggregate axis) and ring (per-link axis) identities",
                "ranks": 8,
                "message_bytes_ladder": [8192, 32768, 131072, 524288, 2097152,
                                         8388608, 33554432, 134217728,
                                         268435456, 536870912, 2147483648,
                                         8589934592],
                "message_regime_note": "the anchor is regime-free (a model "
                "constant); the ladder is the SAME 12-size 8*2^k grid as stage "
                "A7 (8 KiB -> 8 GiB, r=8 divides every size) for cross-stage "
                "comparability at equal (r, M)",
            },
        },
        "verification": verification(),
        "anchor_derived": anchor_derived(),
        "model": {
            "backend_ids": ["analytical_l0_crossbar", "analytical_l0"],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; per-rank wire 2(r-1)/r*M",
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)L ; per-rank wire 2(r-1)/r*M",
            },
            "ranks": 8,
            "free_parameters": {
                "B_aggregate_swept_bytes_per_ns": {
                    "300": "physical point (12 x 25; nvidia-smi total; baseline)",
                    "240": "NCCL topo-model point (12 x 20; the issue's "
                    "system->totalBw; the 4/5 bridge)",
                    "192": "0.8^2 x 300 double-application hazard bracket "
                    "(never a bridge value)",
                },
                "B_per_link_swept_bytes_per_ns": {
                    "25": "physical per-link point (baseline)",
                    "20": "NCCL per-link model (the A-L0-BW span lower endpoint)",
                    "16": "0.8^2 x 25 hazard bracket (per-link twin of 192)",
                },
                "L_ns": 200,
                "L_provenance": "A-L0X-LAT / A-L0-LAT registry points (KEEP per "
                "plan §2.1); latency axis deferred to its own global stage",
            },
            "assumptions": "A-L0X-PORT/-BW/-LAT/-DIV (crossbar), A-L0-BW/-LAT/"
            "-FD/-DIV (ring) from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "bridge_execution": bridge_execution(),
            "aggregate_granularity_sweep": agg_table,
            "per_link_granularity_sweep": link_table,
            "granularity_axis": granularity_axis(),
            "double_application_hazard": double_application_hazard(),
            "bridge_vs_measured_audit": bridge_vs_measured_audit(),
            "latency_regime_vanishing": vanishing,
            "registry_placements": registry_placements(),
            "structural_expressiveness": {
                "statement": "the L0 input space carries no protocol/packet-"
                "overhead parameter; CAL-A12's mechanism (NVLink packet "
                "overhead) is expressible ONLY as a multiplicative B rescaling "
                "— the protocol axis is below L0's declared fidelity, the same "
                "structural-blindness class as stages A5 (geometry), A6 "
                "(software version/channelization) and A8 (workload tolerance)",
                "classification": "structural, absorbed by the bridge, never "
                "refit; a packet-level mechanism model is a higher-fidelity "
                "backend's job (uet-htsim class)",
            },
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — the anchor "
            "publishes no time series and no achieved bandwidth; recorded per "
            "the stage's FAIL-clause duty instead of skipped because the "
            "anchor's actual role (the derating bridge) IS extractable and is "
            "executed above end-to-end on the anchor's own fabric class.",
            "bridge_summary": "the derating is exactly 4/5 at BOTH granularities "
            "(20/25 per link; 240/300 aggregate — 12 x each per-link figure); "
            "executed through the identity it moves bandwidth-bound CCT by "
            "exactly +25% asymptotically (5/4), +24.997% at the 512 MiB anchor "
            "point, and only +2.7%/+4.2% at 8 KiB (crossbar/ring) — a "
            "bandwidth-axis quantity, nearly inoperative in the latency-bound "
            "regime.",
            "bridge_realism": "the anchor set's own measured series (CAL-A3 vs "
            "900: 0.876-1.008, avg 0.951; CAL-A6 vs 400: 0.964-0.978) sit 15-18 "
            "percentage points ABOVE the 0.8 bridge — the bridge is a "
            "conservative envelope from one NVLink-3/NCCL observation, not a "
            "validated cross-generation constant; all ladder usages (A2 720, "
            "A6 320, A7 358.4) are single applications (audited, consistent).",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, content-addressed, "
            "replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the bridge "
            "role; no E3/E4 language — CAL-A12 is an external published issue "
            "thread, not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_PHYS300, RUN_ID_NCCL240],
            "sweep_ids": [SWEEP_ID_AGG, SWEEP_ID_LINK],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_AGG}",
                           f"results/sweeps/{SWEEP_ID_LINK}"],
            "run_backed_numbers": "every model output in comparison."
            "bridge_execution.store_run_pair and both granularity sweeps "
            "(closed-form cross-checked by exact Fraction string equality on "
            "every executed row, asserted in the builder); comparison."
            "bridge_vs_measured_audit and double_application_hazard."
            "ladder_usage_audit are anchor-anchor arithmetic by construction "
            "(declared inline, no run ids claimed)",
            "inputs": [
                "experiments/calibration/a12/sweep_a12_aggregate_v1.yaml",
                "experiments/calibration/a12/sweep_a12_perlink_v1.yaml",
                "experiments/calibration/a12/run_a12_physical_v1.yaml",
                "experiments/calibration/a12/run_a12_nccl240_v1.yaml",
                "experiments/calibration/a12/workloads/w1_dense_tp_decode_tp8_512mib.yaml",
                "experiments/calibration/a12/topologies/ (6 files)",
                "experiments/calibration/a12/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/a12/run_a12_physical_v1.yaml ; "
            "make run EXP=experiments/calibration/a12/run_a12_nccl240_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a12/sweep_a12_aggregate_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a12/sweep_a12_perlink_v1.yaml ; "
            "python experiments/calibration/a12/build_calibration_record.py",
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
