"""Build the calibration anchor-split record (stage S1 of the calibration
execution ladder).

Splits the 23 integrated public-measurement anchors (12 core CAL-A1..A12 +
11 gap-fill GF-01..GF-11) into a CALIBRATION SET (18 anchors, four regime
groups that the fitting stages exercise one group per stage) and a HOLDOUT
SET (4 anchors, evaluation-only), with GF-06 BLOCKED (no record exists —
documented gap, ADJUDICATION.md standing item). Records the split
content-addressed and COMMITS the record bytes BEFORE any fitting stage
reads an anchor number.

Authority (all in-tree):

- ``docs/calibration/CALIBRATION_PLAN.md`` §3.5 — holdout discipline:
  (a) within a series, fit a size subset and hold out the rest (the plan's
  own example: CAL-A3 fit {2,4,8} GiB, hold out {16,32} GiB);
  (b) across anchors, CAL-A4 is reserved as an external check, not a fit
  target, in the first pass (mandated holdout);
  (c) never validate on the dimension that was fitted.
- §1.2 regime coverage matrix + ``docs/calibration/anchors_gapfill.md``
  coverage map (R1..R4, small-message, latency axis) — the plan's grouping
  the four calibration groups follow.
- House rule: calibration and validation data stay separate.

Holdout choice (>= 4 anchors spanning regimes; every one disjoint from the
fit set in generation, fabric class, software, or regime):

- CAL-A4 — plan-mandated (§3.5(b)); ring regime, r=4/16, NVLink-3/V100
  era, NCCL 2.4.6-class software, peer-reviewed sim-vs-hardware.
- GF-01 — the only MEASURED full-mesh (MI300X xGMI) series, spanning BOTH
  the small-message (8 B..64 KiB) and large-message (1..16 GiB plateau)
  regimes on a non-NVIDIA fabric with the 75%-class per-link derating.
- GF-03 — next-generation (B300-class) large-message point plus measured
  us-scale D2D latency; one generation beyond every fit anchor.
- GF-11 — current-generation GB200 NVL72 small-message AllReduce and the
  only measured current-gen latency decomposition; same fabric class as
  fit target CAL-A3 but the DISJOINT (latency-bound) regime — the §3.5(c)
  instance.

No anchor number is re-transcribed here beyond size/point labels already
declared in the plan and the committed per-anchor E1 record builders; the
record cites each anchor by id into ``docs/calibration/anchors_staging.md``
(§A1..A12) and ``docs/calibration/anchors_gapfill.md`` (§GF-01..GF-11).

Pure function of this script: no wall-clock, no host metadata, identical
reruns produce byte-identical records. Content addressing follows the
calibration-record convention (``experiments/calibration/a3/`` builder):
record_id = sha256 over (canonical_json(record) + newline). The record is
APPEND-ONLY: the committed copy at
``experiments/calibration/split/anchor_split_v1.json`` must always hash to
the recorded id; changing the split requires a NEW record (split_v2) — this
file is never edited in place.

Status of everything this script writes: PROPOSED — binding for the
calibration fitting stages (S2..S5) and holdout evaluation (S6) as the
recorded data split; no claim, label, or shipped parameter value changes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

RESULTS = REPO_ROOT / "results"
COMMITTED_COPY = (
    REPO_ROOT / "experiments" / "calibration" / "split" / "anchor_split_v1.json"
)

SPLIT_VERSION = "split_v1"
SPLIT_DATE = "2026-10-30"

# ---------------------------------------------------------------------------
# The split (anchor ids only; numbers live in the staging docs and the
# per-anchor E1 record builders, cited by id).
# ---------------------------------------------------------------------------

CALIBRATION_GROUPS = [
    {
        "group_id": "G1",
        "fitting_stage": "S2",
        "title": "Large-message bandwidth-bound switched scale-up + spec "
        "ceilings + spec-to-measured derating bridge",
        "plan_grouping": [
            "CALIBRATION_PLAN.md §1.2 row 'Large-message bandwidth-bound "
            "(>= ~1 GiB), switch-fabric scale-up' (CAL-A3 target, CAL-A2/A1 "
            "ceilings, CAL-A12 derating)",
            "staging 'Top-5 picks' #1 (A3) and #4 (A1+A2)",
        ],
        "parameter_axes": "A-L0X-BW scale sweep (plan §2.1 NARROW-scale "
        "verdict) at the anchored 448..900 B/ns span, A-L0X-LAT registry "
        "context; A-L0X-PORT domain labels (KEEP for NVSwitch-class)",
        "anchors": [
            ("CAL-A3", "fit_target_primary",
             "Crusoe GB200 NVL72 NCCL 2.28.3 allreduce, 2-32 GiB, r=72 — the "
             "plan's primary O-CCT calibration target (out-of-place series; "
             "in-place rows excluded per plan §4.10)"),
            ("CAL-A1", "normalization_ceiling",
             "NVLink5 switch chip spec — radix/full-duplex ceiling only, "
             "never an achieved value"),
            ("CAL-A2", "normalization_ceiling",
             "GB200 NVL72 per-GPU/aggregate NVLink spec — the 900 B/ns "
             "per-direction normalization line"),
            ("CAL-A7", "normalization_ceiling",
             "MI300X Infinity Fabric full-mesh spec — non-switched-class "
             "ceiling (single-port identity flagged OUT-OF-DOMAIN there, "
             "plan §2.1 A-L0X-PORT)"),
            ("CAL-A12", "derating_bridge",
             "NCCL internal NVLink model (~80% of peak) — mandatory "
             "normalization between spec ceilings and measured series"),
        ],
    },
    {
        "group_id": "G2",
        "fitting_stage": "S3",
        "title": "H100-class community series + hybrid scale-up/scale-out + "
        "multi-rank injection scaling",
        "plan_grouping": [
            "CALIBRATION_PLAN.md §1.2 row 'Large-message hybrid "
            "scale-up+scale-out' (CAL-A6)",
            "anchors_gapfill.md coverage map R4 (multi-rank injection "
            "scaling: GF-04) and R2 additions (GF-02)",
            "staging 'Top-5 picks' #5 (A6 noise floor)",
        ],
        "parameter_axes": "A-L0X-BW derating axis against community-measured "
        "saturation bands; rail/hybrid projection conventions; "
        "A-AS1-CHUNKS-1 chunk-count declaration duty (plan §2.2) for any "
        "CAL-A3/A6-class comparison",
        "anchors": [
            ("CAL-A6", "fit_target_noise_floor",
             "4x8 H100 hybrid NVLink+RoCE, NCCL 2.19.3 vs 2.20.3, 1-16 GiB — "
             "sets the 5-8% software-version noise floor any pass criterion "
             "must exceed"),
            ("GF-02", "fit_target",
             "8xH100 NVLink community busbw saturation ~360 GB/s "
             "(128 MiB-16 GiB); carries the open 360-vs-476 GB/s counting-"
             "convention discrepancy with GF-04 — the integration audit "
             "duty stays with this group"),
            ("GF-04", "fit_target",
             "Oracle OCI H100 cluster: single-node 8-GPU NCCL point plus "
             "OSU/RDMA latency rows and 8->16 rank scaling (16-GPU point "
             "held out within-series, see within_series_splits)"),
        ],
    },
    {
        "group_id": "G3",
        "fitting_stage": "S4",
        "title": "Measured/assumption hop-pair latency axis + small-message "
        "boundary",
        "plan_grouping": [
            "CALIBRATION_PLAN.md §1.2 row 'Per-hop latency axis' "
            "(CAL-A8/A9 CXL-class, CAL-A10 assumption-class GPU)",
            "plan gap 2 (measured hop/pair latency) closed by GF-10",
            "staging 'second wave (latency axis)'",
        ],
        "parameter_axes": "A-L0-LAT / A-L0X-LAT / A-L0T-LAT / A-L0D-LAT "
        "range discipline (plan §2.1 KEEP-point / NARROW-range-upper "
        "verdicts); small-message O-CCT at the smoke-manifest regime is "
        "predicted from this axis and EXTERNALLY checked on the holdout "
        "(GF-01 small rows, GF-11)",
        "anchors": [
            ("CAL-A8", "latency_axis_point",
             "Pond CXL emulated added latency 64/140 ns — workload-goal "
             "fractions locate the CXL-class point only"),
            ("CAL-A9", "latency_axis_point",
             "CXL design estimates ~10 ns/link + >= ~70 ns/switch stage — "
             "per-hop decomposition, no CCT series"),
            ("CAL-A10", "latency_axis_point",
             "0.8 us NVLink-network end-to-end ASSUMPTION-class value "
             "(peer-reviewed usage, not a measurement)"),
            ("GF-10", "latency_axis_point_measured",
             "Li et al. TPDS V100/NVSwitch-era P2P latency (us-class, "
             "app-level; interpretation duty: bounds a different thing "
             "than wire hop latency)"),
        ],
    },
    {
        "group_id": "G4",
        "fitting_stage": "S5",
        "title": "Torus-geometry falsifier + UEC-class transport / "
        "congestion-management envelopes",
        "plan_grouping": [
            "CALIBRATION_PLAN.md §1.2 rows 'Torus geometry effects' "
            "(CAL-A5 falsifier) and the plan §4 gap rows for UEC semantics "
            "and congestion",
            "anchors_gapfill.md coverage map R1 (GF-05, GF-08, GF-09), R3 "
            "(GF-05, GF-07), scale-out context (CAL-A11)",
        ],
        "parameter_axes": "A-L0T-UNIF geometry-abstraction falsification "
        "duty (plan §2.1 flag: CAL-A5 is the first >30% falsifier); "
        "CM effect-size envelopes bound what congestion semantics modeling "
        "must reproduce — envelope/context checks, not O-CCT fits; "
        "A-AS2-* adapter entries stay in their own registry",
        "anchors": [
            ("CAL-A5", "falsifier",
             "TPU v4 ICI per-link spec + measured twisted-vs-regular torus "
             "all-to-all ratios (1.31-1.63x); no absolute (size -> time) "
             "series exists, so no CCT-vs-CCT comparison is defined"),
            ("CAL-A11", "context_proxy",
             "Meta RoCE production fabric (scale-out, labeled proxy only) — "
             "sanity context for effects L0 declares out of scope"),
            ("GF-05", "envelope_sim_plus_hw",
             "SMaRTT/REPS (NSDI 2025): UEC-standardized congestion control "
             "in uet-htsim + hardware testbed — effect sizes 20-50%, RoCE "
             "3-6x from optimal; sim-config provenance for the UEC profile"),
            ("GF-07", "envelope_measured",
             "Congestion impact across 5 HPC fabrics (scale-out labeled "
             "proxy): the 5% -> 25x collective-slowdown falsification "
             "envelope"),
            ("GF-08", "envelope_hw_transport",
             "Falcon (SIGCOMM 2025): shipped UEC-class hardware transport "
             "headline capability (200 Gbps, 120 Mops/s) and congestion/"
             "loss deltas (8x, 65%)"),
            ("GF-09", "design_target_ceiling",
             "Ultra Ethernet design-principles paper targets (400+ Gbps, "
             "sub-us latency, 10 us CC RTT) — ceiling/target class, same "
             "discipline as CAL-A1/A2: never achieved values"),
        ],
    },
]

HOLDOUT = [
    {
        "anchor_id": "CAL-A4",
        "mandate": "plan-mandated holdout (CALIBRATION_PLAN.md §3.5(b): "
        "'reserved as an external check, not a fit target, in the first "
        "pass')",
        "regime_tags": ["R_RING_SMALL_R"],
        "regime": "medium/large ring AllReduce, r=4/16, NVLink-3/V100 era, "
        "64 MB-1.5 GB; peer-reviewed simulator-vs-hardware mean error ~5%",
        "external_check_dimensions": [
            "generation: NVLink-3/V100 vs the fit set's H100/GB200/MI300X "
            "classes",
            "rank scale and collective topology: ring at r=4/16 vs "
            "crossbar rack r=72, full-mesh r=8, hybrid r=32",
            "software: NCCL 2.4.6-era vs 2.19-2.28-era pins",
        ],
        "leakage_note": "the ~5% mean-error SCALAR is admitted as "
        "noise-floor/tolerance-shape context per plan §3.4 (as already "
        "recorded in the plan itself); the anchor's (size -> time) series "
        "and per-configuration errors are NOT fit inputs",
    },
    {
        "anchor_id": "GF-01",
        "mandate": "fabric-class generalization holdout (the only MEASURED "
        "full-mesh series)",
        "regime_tags": ["R_FULL_MESH", "R_SMALL_MESSAGE", "R_LARGE_MESSAGE"],
        "regime": "MI300X 7-hop full-mesh xGMI, r=8: small-message "
        "8 B-64 KiB (13.5-16.7 us) AND large-message 1-16 GiB plateau "
        "(314-319 GB/s) with per-link usable derating (45-47 of 64 GB/s)",
        "external_check_dimensions": [
            "fabric class: non-switched full mesh, where plan §2.1 "
            "(A-L0X-PORT) already flags the single-port identity "
            "OUT-OF-DOMAIN — a miss here is a known-omission finding, "
            "never a tuning target",
            "software stack: RCCL 2.22.3/ROCm 6.3 vs the NCCL-pinned fit "
            "targets",
            "message regime: measured small-message tables exist only in "
            "the holdout (GF-01, GF-11)",
        ],
        "leakage_note": "the CAL-A7 spec ceiling (fit set, normalization "
        "only) is the spec side of this fabric class; GF-01's measured "
        "numbers never enter any fit objective",
    },
    {
        "anchor_id": "GF-03",
        "mandate": "generation-extrapolation holdout (next-generation point)",
        "regime_tags": ["R_LARGE_MESSAGE", "R_NEXT_GEN", "R_LATENCY_AXIS"],
        "regime": "B300/Blackwell-Ultra-class: large-message allreduce "
        "~837 GB/s (~93% of the 900-class line), broadcast ~682, measured "
        "D2D latency ~1.4-1.6 us, 2 MiB allreduce 42-52 us",
        "external_check_dimensions": [
            "generation: one generation beyond every fit anchor (the fit "
            "set tops out at H100/GB200-era)",
            "measured derating point (93%/76%) on a fabric no fit anchor "
            "measures",
        ],
        "leakage_note": "confidence M (independent practitioner blog, "
        "methodology context light) — a noisy external point, recorded as "
        "such; noise status does not move it into the fit set",
    },
    {
        "anchor_id": "GF-11",
        "mandate": "regime-disjoint same-fabric holdout (plan §3.5(c) "
        "instance: never validate on the dimension that was fitted)",
        "regime_tags": [
            "R_SMALL_MESSAGE",
            "R_LATENCY_AXIS",
            "R_MULTI_RANK",
            "R_LARGE_MESSAGE_FABRIC",
        ],
        "regime": "GB200 NVL72 (same fabric class as fit target CAL-A3), "
        "latency-bound regime: small-message AllReduce 2.37-11.0 us at 4 "
        "GPUs, measured latency decomposition (LL2 RTT 0.306 us, remote "
        "store 0.792 us), overhead scaling 7%->70% from 2 to 64 GPUs",
        "external_check_dimensions": [
            "regime: latency-bound small-message vs the bandwidth-bound "
            "large-message series the fit uses — same rack class, disjoint "
            "axis",
            "latency axis: the only MEASURED current-generation latency "
            "decomposition; the fit set's latency axis is CXL-class / "
            "assumption-class / V100-era points only",
        ],
        "leakage_note": "evaluation-only; brackets what any model may "
        "predict at small sizes without accusing the fabric (stock-NCCL "
        "11.0 us vs near-optimal 2.37 us)",
    },
]

BLOCKED = [
    {
        "anchor_id": "GF-06",
        "reason": "no record exists: manual extraction blocked during the "
        "E1 pass (provider-side content filter); documented gap and "
        "standing item in docs/calibration/ADJUDICATION.md; blocked "
        "material preserved untracked at experiments/calibration/gf06/",
        "assignment": "belongs to NEITHER set; if numbers are ever "
        "extracted, the assignment is made by a NEW split record "
        "(split_v2) — this record is immutable and does not guess",
    },
]

WITHIN_SERIES_SPLITS = [
    {
        "anchor_id": "CAL-A3",
        "basis": "plan §3.5(a) literal example",
        "series": "out-of-place allreduce, 5 sizes, 2-32 GiB per rank "
        "(in-place rows excluded per plan §4.10, labeled not smoothed)",
        "fit_sizes": ["2GiB", "4GiB", "8GiB"],
        "held_out_sizes": ["16GiB", "32GiB"],
        "rule": "held-out sizes are excluded from every S2 fit objective "
        "and reported as held-out error",
    },
    {
        "anchor_id": "CAL-A6",
        "basis": "plan §3.5(a) applied where a split is defined",
        "series": "two staged endpoint sizes per NCCL version (1 GiB and "
        "16 GiB); the version pair itself measures the noise floor",
        "fit_sizes": ["1GiB", "16GiB"],
        "held_out_sizes": [],
        "rule": "degenerate — no within-series holdout exists at two "
        "points; the anchor's role is the version-swing noise floor, and "
        "the 5-8% band bounds pass-criterion shape (plan §3.4), never a "
        "fitted value",
    },
    {
        "anchor_id": "GF-02",
        "basis": "plan §3.5(a) audit",
        "series": "community busbw saturation band ~360 GB/s across "
        "128 MiB-16 GiB (per-size rows not cleanly extracted at staging)",
        "fit_sizes": ["saturation-band (128MiB-16GiB)"],
        "held_out_sizes": [],
        "rule": "degenerate — the usable staged signal is a single "
        "saturation band; a within-series split would hold out noise",
    },
    {
        "anchor_id": "GF-04",
        "basis": "plan §3.5(a)/(c) on the scaling dimension (coverage map "
        "R4)",
        "series": "NCCL allreduce busbw: 8 GPUs 476.37 GB/s (single node), "
        "16 GPUs 469.67 GB/s (two nodes, RoCE legs); plus OSU/RDMA "
        "latency rows",
        "fit_sizes": ["8-GPU single-node point"],
        "held_out_sizes": ["16-GPU two-node point"],
        "rule": "the multi-rank scaling dimension is validated, not "
        "fitted: the 1.4% 8->16 drop is a held-out prediction target; OSU "
        "latency rows serve the S4 latency axis",
    },
]

NO_LEAKAGE_RULES = [
    "No S2..S5 fit objective, swept-value provenance, tolerance, or "
    "record may read, target, or select against any holdout anchor's "
    "numbers. Sole recorded exception: CAL-A4's ~5% mean-error scalar as "
    "tolerance-shape context (plan §3.4, in-plan since 2026-10-27).",
    "Held-out within-series sizes (CAL-A3 {16GiB, 32GiB}; GF-04's 16-GPU "
    "point) never enter a fit objective; stages report them as held-out "
    "error.",
    "S6 runs the fitted configuration against the four holdout anchors "
    "and records errors; nothing tunes in S6 either.",
    "GF-06's blocked material is not paraphrased or estimated from "
    "memory; no number is fabricated to fill the gap.",
    "Changing this split (including any GF-06 assignment) requires a new "
    "content-addressed record (split_v2); this one is append-only.",
]


def build_record() -> dict:
    calibration_ids: list[str] = []
    group_entries = []
    for group in CALIBRATION_GROUPS:
        anchors = []
        for anchor_id, role, note in group["anchors"]:
            anchors.append(
                {
                    "anchor_id": anchor_id,
                    "role": role,
                    "note": note,
                    "staged_at": (
                        "docs/calibration/anchors_staging.md §"
                        + anchor_id.replace("CAL-", "")
                        if anchor_id.startswith("CAL-")
                        else "docs/calibration/anchors_gapfill.md §"
                        + anchor_id
                    ),
                }
            )
            calibration_ids.append(anchor_id)
        entry = {k: v for k, v in group.items() if k != "anchors"}
        entry["anchors"] = anchors
        group_entries.append(entry)

    holdout_ids = [h["anchor_id"] for h in HOLDOUT]
    blocked_ids = [b["anchor_id"] for b in BLOCKED]
    all_ids = calibration_ids + holdout_ids + blocked_ids

    # -- mechanical invariants (fail loudly at build time, not at review) --
    assert len(all_ids) == 23, len(all_ids)
    assert len(calibration_ids) == 18, len(calibration_ids)
    assert len(set(all_ids)) == 23, "anchor ids must be unique"
    assert not (set(calibration_ids) & set(holdout_ids)), "calibration/holdout overlap"
    assert not (set(calibration_ids) | set(holdout_ids)) & set(blocked_ids)
    assert "CAL-A4" in holdout_ids, "plan §3.5(b) mandates CAL-A4 holdout"
    assert len(holdout_ids) >= 4, "holdout must have at least 4 anchors"
    holdout_regimes = {t for h in HOLDOUT for t in h["regime_tags"]}
    assert len(holdout_regimes) >= 4, "holdout must span at least 4 regimes"
    expected_23 = {f"CAL-A{i}" for i in range(1, 13)} | {
        f"GF-{i:02d}" for i in range(1, 12)
    }
    assert set(all_ids) == expected_23, set(all_ids) ^ expected_23
    # within-series held-out sizes must be disjoint from fit sizes
    for split in WITHIN_SERIES_SPLITS:
        assert not (set(split["fit_sizes"]) & set(split["held_out_sizes"]))
    assert {s["anchor_id"] for s in WITHIN_SERIES_SPLITS} <= set(calibration_ids)

    return {
        "record_kind": "calibration_anchor_split",
        "status": "PROPOSED — binding for calibration stages S2..S6 as the "
        "recorded data split; owner adjudication precedes any label move; "
        "no claim, label, or shipped parameter value changes",
        "stage": "calibration split record S1 — committed BEFORE any "
        "fitting stage runs",
        "split_version": SPLIT_VERSION,
        "date": SPLIT_DATE,
        "authority": [
            "docs/calibration/CALIBRATION_PLAN.md §3.5 (holdout "
            "discipline a/b/c) and §3.4 (tolerance-shape context)",
            "docs/calibration/CALIBRATION_PLAN.md §1.2 + docs/calibration/"
            "anchors_gapfill.md coverage map (regime grouping)",
            "house rule: calibration and validation data stay separate",
        ],
        "precondition_statement": "no fitting has occurred before this "
        "record: the E1 calibration-candidate records of 2026-10-27..29 "
        "were untuned sweeps with zero parameter changes (approved as E1 "
        "candidates 2026-10-29, docs/calibration/ADJUDICATION.md); this "
        "split is therefore committed before the first fit",
        "anchors_total": 23,
        "calibration_set": {
            "size": len(calibration_ids),
            "definition": "anchors whose published numbers the fitting "
            "stages (S2..S5, one group per stage) may sweep the declared "
            "free-parameter ranges against; normalization ceilings and "
            "context anchors inside the set fix scales and provenance but "
            "are never measured values",
            "groups": group_entries,
        },
        "holdout": {
            "size": len(holdout_ids),
            "definition": "evaluation-only anchors reserved for the S6 "
            "holdout run of the fitted configuration; no number from "
            "these anchors enters any fit objective, swept-value "
            "provenance, or tolerance before S6 completes",
            "regime_span": sorted(holdout_regimes),
            "anchors": HOLDOUT,
        },
        "blocked": {
            "size": len(blocked_ids),
            "anchors": BLOCKED,
        },
        "within_series_splits": {
            "basis": "plan §3.5(a): fit on a subset of message sizes, "
            "hold out the rest and report held-out error",
            "splits": WITHIN_SERIES_SPLITS,
        },
        "no_leakage_rules": NO_LEAKAGE_RULES,
        "immutability": {
            "content_address_convention": "record_id = sha256 over "
            "(canonical_json(record) + '\\n').encode('utf-8') — same "
            "convention as the per-anchor calibration records "
            "(experiments/calibration/a3/build_calibration_record.py)",
            "committed_copy": "experiments/calibration/split/"
            "anchor_split_v1.json — must always hash to the recorded id; "
            "regenerating with different bytes is an error",
            "append_only": "any change to the split (including a GF-06 "
            "assignment) is a NEW record (split_v2) with a new id; this "
            "record is never edited in place",
            "builder": "experiments/calibration/split/"
            "build_anchor_split_record.py (deterministic, no wall-clock, "
            "no host metadata)",
            "guard": "tests/calibration/test_anchor_split.py rebuilds the "
            "record and fails on any byte drift or invariant violation",
        },
        "provenance": {
            "anchor_numbers": "not re-transcribed here; every anchor cites "
            "its staging row by id (docs/calibration/anchors_staging.md "
            "§A1..A12, docs/calibration/anchors_gapfill.md §GF-01..GF-11) "
            "and its committed E1 builder "
            "(experiments/calibration/<id>/)",
            "confidence_flags": "per-anchor confidence classes (H/M/M-H/L) "
            "stay as staged; holdout anchors carry theirs in-line "
            "(GF-03 is M, GF-01 M-H, GF-11 H, CAL-A4 H)",
        },
    }


def main() -> int:
    record = build_record()
    record_bytes = (canonical_json(record) + "\n").encode("utf-8")
    record_id = hashlib.sha256(record_bytes).hexdigest()

    # append-only store copy (house convention; results/ is untracked)
    store_dir = RESULTS / "calibration" / record_id
    store_path = store_dir / "record.json"
    if store_path.exists():
        if store_path.read_bytes() != record_bytes:
            print(
                f"ERROR: store record {record_id} exists with different "
                "bytes",
                file=sys.stderr,
            )
            return 1
        print(f"idempotent: store record {record_id} already byte-identical")
    else:
        store_dir.mkdir(parents=True)
        store_path.write_bytes(record_bytes)
        print(f"stored: results/calibration/{record_id}/record.json")

    # committed copy — the immutability anchor of this split
    if COMMITTED_COPY.exists():
        if COMMITTED_COPY.read_bytes() != record_bytes:
            print(
                f"ERROR: committed copy {COMMITTED_COPY} differs from the "
                "rebuilt record — the split is immutable; record a NEW "
                "split (split_v2) instead of editing",
                file=sys.stderr,
            )
            return 1
        print(f"immutable: committed copy matches record {record_id}")
    else:
        COMMITTED_COPY.parent.mkdir(parents=True, exist_ok=True)
        COMMITTED_COPY.write_bytes(record_bytes)
        print(f"wrote committed copy: {COMMITTED_COPY}")

    print(f"record_id: {record_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
