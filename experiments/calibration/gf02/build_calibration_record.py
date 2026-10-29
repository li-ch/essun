"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-02
(calibration stage GF-02;
p1_calibration.md; anchor staged in docs/calibration/anchors_gapfill.md
§GF-02 — NCCL nccl-tests GitHub issue #326, 8xH100 NVLink
allreduce/allgather measured plateau).

Pure function of immutable artifacts: reads the four append-only store run
records and the sweep table produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers or from the thread/source fetches this stage
performed on 2026-10-28 (method and verbatim quotes recorded inline under
``verification`` / ``busbw_conventions``; all fetched text is UNTRUSTED
INPUT, recorded-not-ingested), or (b) computed from the stored run/sweep
artifacts by this script (closed-form cross-checks by exact Fraction
string equality on every executed row), or (c) anchor-anchor arithmetic in
the bridge-realism context (staged numbers of CAL-A3/A6/A12 and GF-04; no
model run backs those rows and none is claimed). Nothing is tuned: the
swept B values carry their anchor/staging provenance, and the record
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
RUN_ID_AR_PLATEAU360 = "b8a8af91394d8b4d844cd2d71fcf8518a0012d8ad4a062179bc65927c96ed933"
RUN_ID_AR_PERDIR450 = "c4983ee8567fda5695df49341f7e20e1d11a6bcc97b615f23550436c650a9b46"
RUN_ID_AG_RING360 = "5cb734abed53d351e01d1850355d4fc1bb193b3cb80b834451d7fad6697f37c9"
RUN_ID_AG_RING450 = "1bdd9bca10eac872aea7e33b6f3ffd1afe1ad2bcd3555491afd98682da61824e"
SWEEP_ID_AR = "6d3eeef80ce834acb46e7a0dda4e3984b9f3972b38daef353ea8ef86810968f5"

RESULTS = REPO_ROOT / "results"

# Anchor GF-02 staged/fetched numbers (docs/calibration/anchors_gapfill.md
# §GF-02; thread fetched and verified 2026-10-28 — see `verification`).
# Decimal unit convention of the calibration plan: 1 GB/s = 1 B/ns.
PLATEAU_GBPS = Fraction(360)        # "~360 GB/s" busbw, BOTH collectives (issue body)
BIDIR_PEAK_GBPS = Fraction(900)     # "NVLink's peak bi-directional bandwidth is 900 GB/s" (issue body)
PERDIR_PHYSICAL_GBPS = Fraction(450)  # = 900/2, the per-direction split the poster's own gloss invokes
GF04_BUSBW = Fraction("476.37")     # gapfill staging doc §GF-04 (open discrepancy vs 360)

# The anchor's command-line size ladder: -b 128M -e 16384M -f 2 (verified)
# => 128 MiB x 2^k, k = 0..7  (2^27 .. 2^34).
LADDER = [128 * 1024 * 1024 * 2**k for k in range(8)]
M_TOP = LADDER[-1]                  # 2^34 = 16 GiB (the plateau row)
M_TOTAL_AG = 8 * M_TOP              # AllGather TOTAL gathered size (A-L0P-MSG):
# every rank contributes 2^34 (the anchor's 16 GiB all_gather row), result 2^37.

# Closed-form identities at r=8, L=200 ns (the executed configurations):
#   allreduce crossbar: t = 2*(r-1)/r*M/B + 2L       -> wire/rank 7/4*M, +400 ns
#   allgather ring:     t = (r-1)/r*M_total/B + (r-1)L -> wire/rank 7/8*M_total, +1400 ns
R = 8
L = Fraction(200)
AR_WIRE_FACTOR = Fraction(2 * (R - 1), R)        # 7/4
AG_WIRE_FACTOR = Fraction(R - 1, R)              # 7/8
AR_LAT = 2 * L                                   # 400
AG_LAT = (R - 1) * L                             # 1400

# Bridge-realism context inputs (staged numbers only, anchor-anchor arithmetic):
# CAL-A12 derating 4/5; CAL-A3 measured busbw vs the CAL-A2 900 line; CAL-A6
# 2.19.3 time-implied busbw vs the 400 rail (all as recorded in stage A12's
# record from anchors_staging.md; nothing here is backed by a model run).
A12_DERATING = Fraction(4, 5)
A3_BUSBW_OVER_900 = {
    "2GiB": Fraction("787.95") / Fraction(900),
    "4GiB": Fraction("831.03") / Fraction(900),
    "8GiB": Fraction("866.36") / Fraction(900),
    "16GiB": Fraction("890.32") / Fraction(900),
    "32GiB": Fraction("906.94") / Fraction(900),
}
A6_BUSBW_OVER_400 = {
    "1GiB": Fraction("385.41") / Fraction(400),
    "16GiB": Fraction("391.10") / Fraction(400),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ar_time(payload: int, b: Fraction) -> Fraction:
    return AR_WIRE_FACTOR * payload / b + AR_LAT


def ag_time(m_total: int, b: Fraction) -> Fraction:
    return AG_WIRE_FACTOR * m_total / b + AG_LAT


# ---------------------------------------------------------------------------
# Verification: the fetches this stage performed (record-the-fetch; all
# fetched text is UNTRUSTED INPUT — transcribed for comparison only).
# ---------------------------------------------------------------------------


def verification() -> dict:
    return {
        "duty": "the gapfill staging doc flags GF-02's rows as 'not cleanly "
        "extractable in this pass — title/summary verified, rows re-verify at "
        "integration'; the A12 stage established the fetch-and-record pattern "
        "for NCCL GitHub anchors, and this stage works it for issue #326.",
        "method": [
            "web reader fetch of https://github.com/NVIDIA/nccl-tests/issues/326 "
            "(rendered page), 2026-10-28 — returned the issue title and full "
            "body text; comments are not rendered in that view",
            "GitHub REST API (api.github.com, unauthenticated, public repo), "
            "2026-10-28: issue JSON (body cross-checked verbatim against the "
            "rendered-page method; created 2025-06-23; state open; poster "
            "asdfvg123) and comments JSON (2 comments total, both bodies)",
            "WebFetch of the rendered issue page — TIMED OUT (recorded as a "
            "failed attempt; two methods above succeeded)",
            "GitHub REST API contents endpoint for NVIDIA/nccl-tests "
            "src/all_reduce.cu and src/all_gather.cu (master), 2026-10-28 — "
            "the getBw implementations quoted under `busbw_conventions`",
        ],
        "issue_body_verified": (
            "8 H100 GPUs, NVLink; 'I ran all_gather and all_reduce benchmark on "
            "the system (8 H100 GPU, NVlink) and the results show that the "
            "bandwidth is saturated at ~360 GB/s for busbw although I am using "
            "fairly large data size (16GB).'; 'Given that NVLink's peak "
            "bi-directional bandwidth is 900 GB/s, the measured 360 GB/s "
            "suggests I am only achieving uni-directional bandwidth.'; command "
            "lines './build/all_gather_perf -b 128M -e 16384M -f 2 -g 8' and "
            "'./build/all_reduce_perf -b 128M -e 16384M -f 2 -g 8'; results "
            "posted as two SCREENSHOT images."
        ),
        "maintainer_reply_verified": (
            "sjeaugey (NVIDIA/NCCL maintainer), 2025-06-24, first of two "
            "comments: '360 GB/s is exactly what we'd expect on H100. See my "
            "GTC talk every year on NVIDIA on demand, there is always a slide "
            "with the expected NCCL performance on DGX platforms.'"
        ),
        "second_comment": (
            "BitCalSaul (unaffiliated), 2025-06-27: an unrelated follow-up "
            "question about all_gather_perf semantics on 6 GPUs — 'each rank "
            "has 80MB of data ... after the operation, each rank ends up with "
            "480MB (80MB x 6)'. NOTE: the only '480' anywhere in the thread is "
            "this TOTAL-BYTES figure, not a bandwidth figure. Unanswered; "
            "issue remains open."
        ),
        "staging_doc_glosses_corrected_by_the_fetch": [
            "the staging doc's 'the poster's expectation of the ~480 GB/s "
            "per-direction class' — NOT FOUND in the fetched thread: the "
            "poster's stated expectation basis is the 900 GB/s bidirectional "
            "peak figure, and their gloss is that 360 looks 'uni-directional' "
            "(arithmetically loose: the per-direction figure is 450, and 360 "
            "< 450); no 480 GB/s bandwidth expectation exists anywhere in the "
            "thread",
            "the staging doc's thread-resolution quote 'half of 480 in each "
            "direction' — NOT FOUND in the fetched thread; the actual "
            "resolution is the maintainer's one-line '360 GB/s is exactly "
            "what we'd expect on H100' (expected-value statement, mechanism "
            "unstated in this thread — the NVLink-packet-overhead mechanism "
            "belongs to CAL-A12's issue #1054 reply, NOT to this one)",
            "the staging doc's 'NCCL >= 2.27.1' software pin — NOT FOUND in "
            "the fetched thread: no NCCL version is stated in the body or "
            "either comment; the software configuration is UNPINNED and is "
            "recorded as such (the 2025-06-23 date makes >=2.27 plausible but "
            "is NOT a pin and is not asserted)",
        ],
        "residual_caveats": (
            "the per-size result tables are screenshots — NOT text-extractable "
            "by any method available to this stage, so '~360 GB/s' remains the "
            "anchor's own approximate summary (the extractable targets are the "
            "plateau statement, the command-line regime 128 MiB-16 GiB, r=8, "
            "and both collectives); all quotes above are tool extractions of "
            "fetched public pages, treated as untrusted input; the GTC talk "
            "slides the maintainer points to were NOT fetched (external video "
            "platform, out of scope)."
        ),
    }


def busbw_conventions() -> dict:
    """The counting-convention mapping, pinned from the nccl-tests source
    (fetched 2026-10-28) — the hazard this anchor exists for, settled by
    source rather than memory, per CALIBRATION_PLAN.md §3's rule that the
    busbw->CCT mapping be written down per point."""
    return {
        "why": "GF-02's own subject is a counting-convention confusion; every "
        "CCT-vs-CCT comparison in this stage goes through these pinned "
        "algebraic mappings, never mixed metrics",
        "source_all_reduce": "NVIDIA/nccl-tests src/all_reduce.cu (master, "
        "fetched 2026-10-28): AllReduceGetBw: baseBw = count*typesize/1e9/sec; "
        "factor = 2*(nranks-1)/nranks; busBw = baseBw*factor",
        "source_all_gather": "NVIDIA/nccl-tests src/all_gather.cu (master, "
        "fetched 2026-10-28): AllGatherGetBw: baseBw = "
        "count*typesize*nranks/1e9/sec (RESULT-size basis); factor = "
        "(nranks-1)/nranks; busBw = baseBw*factor",
        "mapping_allreduce": "algbw = M/t; busbw = algbw*2(r-1)/r. L0 "
        "identity: t = 2(r-1)/r*M/B + 2L => asymptotic busbw = B. The "
        "anchor's plateau reads directly as B = 360.",
        "mapping_allgather": "algbw = M_total/t (result basis); busbw = "
        "algbw*(r-1)/r. L0 ring identity: t = (r-1)/r*M_total/B + (r-1)L => "
        "asymptotic busbw = B. SAME reading as allreduce — one B point for "
        "both collectives, exactly as the anchor states its plateau.",
        "hazard_statement": "the raw bandwidth figure (per-direction "
        "injection) and the busbw convention agree in the large-message "
        "limit for BOTH collectives, but ONLY after the factor and the "
        "algbw basis are settled per collective; the poster's own confusion "
        "(reading 360 against a 900 BIDIRECTIONAL figure as "
        "'uni-directional') is the documented instance of the hazard, and "
        "the bidir900 sweep row quantifies its cost (2.5x) through the "
        "identity.",
    }


# ---------------------------------------------------------------------------
# Anchor arithmetic (self-checked).
# ---------------------------------------------------------------------------


def anchor_derived() -> dict:
    perdir = BIDIR_PEAK_GBPS / 2  # 450
    plateau_over_perdir = PLATEAU_GBPS / perdir  # 4/5 exactly
    gf04_over_perdir = GF04_BUSBW / perdir  # > 1: inexpressible class

    # Self-checks: anything else is a transcription bug, not a finding.
    assert perdir == PERDIR_PHYSICAL_GBPS == 450
    assert plateau_over_perdir == Fraction(4, 5)
    assert PLATEAU_GBPS / BIDIR_PEAK_GBPS == Fraction(2, 5)
    assert gf04_over_perdir > 1
    assert BIDIR_PEAK_GBPS / PLATEAU_GBPS == Fraction(5, 2)
    # The executed payload sizes must be members of the anchor's own ladder.
    sweep_sizes = {128 * 1024 * 1024, 1024**3, M_TOP}
    assert sweep_sizes <= set(LADDER)
    assert M_TOP == 2**34 and M_TOTAL_AG == 2**37

    # Anchor-implied reference CCTs (bandwidth term ONLY — nccl-tests times
    # at 16 GiB carry no L0 latency term; derived purely from the anchor's
    # own numbers through the pinned conventions):
    ar_ref = AR_WIRE_FACTOR * M_TOP / PLATEAU_GBPS
    ag_ref = AG_WIRE_FACTOR * M_TOTAL_AG / PLATEAU_GBPS

    return {
        "staged_numbers": {
            "plateau_busbw_GB_per_s": "360 (~, both allreduce and allgather)",
            "nvlink_peak_bidirectional_GB_per_s": "900 (the poster's own figure)",
            "command_line_regime": "-b 128M -e 16384M -f 2 -g 8 "
            "(verified): sizes 128 MiB x 2^k, k=0..7; r=8",
            "gf04_busbw_GB_per_s": "476.37 (staging-doc bracket, NOT this anchor's number)",
        },
        "derived_arithmetic": {
            "per_direction_physical_bytes_per_ns": str(perdir),
            "plateau_over_per_direction_exact": str(plateau_over_perdir),
            "plateau_over_per_direction_float": float(plateau_over_perdir),
            "per_direction_over_gf04_exact": str(perdir / GF04_BUSBW),
            "gf04_over_per_direction_exact": str(gf04_over_perdir),
            "gf04_over_per_direction_float": float(gf04_over_perdir),
            "bidir_misread_speedup_exact": str(BIDIR_PEAK_GBPS / PLATEAU_GBPS),
        },
        "anchor_implied_reference_cct_ns": {
            "allreduce_16gib_exact": str(ar_ref),
            "allreduce_16gib_float": float(ar_ref),
            "allgather_total128gib_exact": str(ag_ref),
            "allgather_total128gib_float": float(ag_ref),
            "derivation": "t_ref = wire/plateau with wire = 2(r-1)/r*M "
            "(allreduce, M = 2^34) and (r-1)/r*M_total (allgather, M_total = "
            "8 x 2^34 = 2^37 per A-L0P-MSG); the anchor's busbw maps to the "
            "identity B asymptotically under the pinned conventions",
        },
        "derating_semantics": {
            "statement": "the measured plateau sits at exactly 4/5 of the "
            "per-direction physical aggregate (to the anchor's '~' precision)",
            "relation_to_cal_a12": "4/5 IS the CAL-A12 derating bridge factor "
            "(NVLink-3 20/25, cause NVLink packet overhead per issue #1054's "
            "verified reply) — GF-02 supplies the measured NVLink-4 point "
            "that anchor lacked; NOTE the mechanism is NOT stated in THIS "
            "thread (the maintainer says only that 360 is expected on H100), "
            "so mechanism attribution stays with CAL-A12",
        },
    }


# ---------------------------------------------------------------------------
# Run/sweep consumption with exact closed-form cross-checks.
# ---------------------------------------------------------------------------


def ar_run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    cct = Fraction(per_op["completion_time_ns_exact"])
    payload = per_op["payload_bytes"]
    b = Fraction(obs["model"]["injection_bytes_per_ns_exact"])
    assert cct == ar_time(payload, b), (run_id, cct)
    wire = Fraction(per_op["per_rank_wire_bytes_exact"])
    assert wire == AR_WIRE_FACTOR * payload
    assert payload == M_TOP
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


def ag_run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    ag = next(p for p in obs["per_op"] if p["collective"] == "allgather")
    cct = Fraction(ag["completion_time_ns_exact"])
    m_total = ag["payload_bytes"]
    b = Fraction(obs["model"]["link_bytes_per_ns_exact"])
    assert cct == ag_time(m_total, b), (run_id, cct)
    wire = Fraction(ag["per_rank_wire_bytes_exact"])
    assert wire == AG_WIRE_FACTOR * m_total
    assert m_total == M_TOTAL_AG
    assert Fraction(ag["result_bytes_per_rank_exact"]) == m_total  # A-L0P-MSG
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "op_id": ag["op_id"],
        "model_params": {
            "ranks": obs["model"]["ranks"],
            "link_bytes_per_ns_exact": obs["model"]["link_bytes_per_ns_exact"],
            "hop_latency_ns_exact": obs["model"]["hop_latency_ns_exact"],
            "algorithm_family": obs["model"]["algorithm_family"],
        },
        "m_total_gathered_bytes": m_total,
        "result_bytes_per_rank_exact": ag["result_bytes_per_rank_exact"],
        "cct_ns_exact": ag["completion_time_ns_exact"],
        "cct_ns_float": ag["completion_time_ns"],
        "per_rank_wire_bytes_exact": ag["per_rank_wire_bytes_exact"],
        "paired_reducescatter_note": "the W2 pair's RS op carries the same M "
        "and the identical ring identity (recorded in the run); the AG row is "
        "the target, per the plan's per-collective comparability convention",
        "closed_form_check": "exact equality vs 7/8*M_total/B + 14L (asserted in builder)",
    }


def sweep_table() -> dict:
    table = load_json(RESULTS / "sweeps" / SWEEP_ID_AR / "table.json")
    b_by_topo = {
        "crossbar8_gf02_gf04_476_37_v1.yaml": GF04_BUSBW,
        "crossbar8_gf02_perdir450_v1.yaml": Fraction(450),
        "crossbar8_gf02_plateau360_v1.yaml": Fraction(360),
        "crossbar8_gf02_bidir900_v1.yaml": Fraction(900),
    }
    label_by_topo = {
        "crossbar8_gf02_gf04_476_37_v1.yaml": "gf04_476_37 (open-discrepancy bracket)",
        "crossbar8_gf02_perdir450_v1.yaml": "perdir450 (physical per-direction = 900/2)",
        "crossbar8_gf02_plateau360_v1.yaml": "plateau360 (the anchor's measured busbw; BASELINE)",
        "crossbar8_gf02_bidir900_v1.yaml": "bidir900 (bidirectional-misread hazard)",
    }
    by_size: dict[int, dict[str, dict]] = {}
    for row in table["configs"]:
        topo_file = row["topology"]["path"].rsplit("/", 1)[-1]
        payload = row["payload_bytes"]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        b = b_by_topo[topo_file]
        # Closed-form cross-check (exact) on EVERY executed row.
        assert cct == ar_time(payload, b), (row["config_id"], cct)
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        assert wire == AR_WIRE_FACTOR * payload
        by_size.setdefault(payload, {})[topo_file] = {
            "topology_id": topo_file.removesuffix(".yaml"),
            "reading": label_by_topo[topo_file],
            "config_id": row["config_id"],
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "cct_ns_float": row["o_cct"]["completion_time_ns_mean"],
            "delta_vs_plateau_exact": (
                row["delta_vs_baseline"]["delta_exact"]
                if row["delta_vs_baseline"] else "0"
            ),
            "delta_vs_plateau_float": (
                row["delta_vs_baseline"]["delta_float"]
                if row["delta_vs_baseline"] else 0.0
            ),
            "latency_share_of_cct_exact": str(AR_LAT / cct),
        }
    ladder = []
    for payload, topos in sorted(by_size.items()):
        ladder.append({
            "payload_bytes": payload,
            "anchor_ladder_member": True,
            "rows": [topos[t] for t in sorted(topos, key=lambda t: -b_by_topo[t])],
        })
    return {
        "sweep_id": SWEEP_ID_AR,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "the anchor's own plateau reading (B=360) — delta columns "
        "measure placement vs the anchor, positive = slower than the plateau",
        "asymptotic_deltas_vs_plateau_exact": {
            "perdir450": str(Fraction(360, 450) - 1),   # -1/5
            "gf04_476_37": str(Fraction(360) / GF04_BUSBW - 1),
            "bidir900": str(Fraction(360, 900) - 1),    # -3/5
        },
        "message_size_ladder": ladder,
    }


def plateau_placement() -> dict:
    """Model output vs the anchor-implied reference: at B=360 the identity
    reproduces the anchor's implied CCT with the registry latency term as
    the ENTIRE residual; at B=450 (physical) it runs 20% fast."""
    ar360 = Fraction(
        load_json(RESULTS / RUN_ID_AR_PLATEAU360 / "observations.json")["per_op"][0][
            "completion_time_ns_exact"
        ]
    )
    ag360_obs = load_json(RESULTS / RUN_ID_AG_RING360 / "observations.json")
    ag360 = Fraction(
        next(p for p in ag360_obs["per_op"] if p["collective"] == "allgather")[
            "completion_time_ns_exact"
        ]
    )
    ar_ref = AR_WIRE_FACTOR * M_TOP / PLATEAU_GBPS
    ag_ref = AG_WIRE_FACTOR * M_TOTAL_AG / PLATEAU_GBPS
    # The residuals are exactly the L terms.
    assert ar360 - ar_ref == AR_LAT == 400
    assert ag360 - ag_ref == AG_LAT == 1400
    return {
        "allreduce_at_plateau": {
            "model_cct_ns_exact": str(ar360),
            "anchor_implied_reference_ns_exact": str(ar_ref),
            "absolute_deviation_ns_exact": str(ar360 - ar_ref),
            "relative_deviation_exact": str((ar360 - ar_ref) / ar_ref),
            "relative_deviation_float": float((ar360 - ar_ref) / ar_ref),
            "statement": "the identity at the anchor's own B reading "
            "reproduces the anchor-implied CCT to within the fixed +2L "
            "registry term (4.8e-6 relative at 16 GiB) — the anchor's "
            "plateau and the identity's B are the same quantity under the "
            "pinned convention",
        },
        "allgather_at_plateau": {
            "model_cct_ns_exact": str(ag360),
            "anchor_implied_reference_ns_exact": str(ag_ref),
            "absolute_deviation_ns_exact": str(ag360 - ag_ref),
            "relative_deviation_exact": str((ag360 - ag_ref) / ag_ref),
            "relative_deviation_float": float((ag360 - ag_ref) / ag_ref),
            "statement": "same structure on the allgather identity (+14L = "
            "4.2e-6 relative at the 128 GiB-total row) — BOTH collectives of "
            "the anchor land on the same B point, as staged",
        },
        "physical_reading_vs_anchor": {
            "asymptotic_cct_ratio_plateau_over_physical_exact": str(
                Fraction(450, 360)
            ),
            "statement": "at the physical per-direction reading (450 = 900/2) "
            "the model predicts busbw 450 vs the measured plateau 360 — i.e. "
            "it runs 20% fast (CCT 4/5 of the anchor-implied time); the "
            "reconciling factor is exactly the CAL-A12 4/5 bridge, executed "
            "below",
        },
    }


def executed_bridge() -> dict:
    """The 360-vs-450 relation executed through the identity on BOTH
    collectives: two run pairs differing ONLY in B."""
    out = {}
    for label, plateau_id, physical_id, kind in (
        ("allreduce_crossbar", RUN_ID_AR_PLATEAU360, RUN_ID_AR_PERDIR450, "ar"),
        ("allgather_ring", RUN_ID_AG_RING360, RUN_ID_AG_RING450, "ag"),
    ):
        if kind == "ar":
            def cct(run_id):
                return Fraction(
                    load_json(RESULTS / run_id / "observations.json")["per_op"][0][
                        "completion_time_ns_exact"
                    ]
                )
        else:
            def cct(run_id):
                return Fraction(
                    next(
                        p for p in load_json(RESULTS / run_id / "observations.json")[
                            "per_op"
                        ] if p["collective"] == "allgather"
                    )["completion_time_ns_exact"]
                )
        t360, t450 = cct(plateau_id), cct(physical_id)
        ratio = t360 / t450
        pure = Fraction(5, 4)
        assert ratio < pure  # the B-independent latency term keeps it under 5/4
        out[label] = {
            "store_run_pair": [
                plateau_id,
                physical_id,
            ],
            "cct_ratio_plateau_over_physical_exact": str(ratio),
            "cct_ratio_plateau_over_physical_float": float(ratio),
            "asymptotic_ratio_exact": "5/4",
            "distance_to_asymptote_exact": str(pure - ratio),
            "note": "identical workload, rank count and L; only B differs "
            "(360 -> 450), so this ratio IS the measured-plateau-vs-ceiling "
            "relation executed through the identity — the CAL-A12 bridge "
            "factor 4/5 in bandwidth, 5/4 in time, one NVLink generation "
            "after CAL-A12's own 300-vs-240 execution",
        }
    return out


def hazard_brackets() -> dict:
    """The two declared brackets, executed in the sweep (never bridges,
    never targets): the bidirectional misread and the GF-04 discrepancy."""
    return {
        "bidirectional_misread": {
            "hazard": "using the poster's 900 GB/s BIDIRECTIONAL figure as the "
            "per-direction B — the convention confusion the anchor's own body "
            "documents ('the measured 360 GB/s suggests I am only achieving "
            "uni-directional bandwidth')",
            "asymptotic_cct_delta_vs_plateau_exact": str(Fraction(360, 900) - 1),
            "asymptotic_cct_delta_vs_plateau_float": float(Fraction(360, 900) - 1),
            "statement": "predictions 2.5x too fast (CCT at 40% of the "
            "anchor-implied time); executed per size in the sweep's bidir900 "
            "rows — any CCT-vs-CCT use of busbw-class anchors must settle the "
            "conventions first (pinned in busbw_conventions above)",
        },
        "gf04_open_discrepancy": {
            "staging_rule": "anchors_gapfill.md §GF-02 flags 360 (GF-02) vs "
            "476.37 (GF-04, Oracle OCI H100) as an OPEN discrepancy — 'do not "
            "average them'; this stage brackets it, never merges it",
            "gf04_over_physical_per_direction_exact": str(GF04_BUSBW / Fraction(450)),
            "gf04_over_physical_per_direction_float": float(GF04_BUSBW / Fraction(450)),
            "asymptotic_cct_delta_vs_plateau_exact": str(Fraction(360) / GF04_BUSBW - 1),
            "asymptotic_cct_delta_vs_plateau_float": float(Fraction(360) / GF04_BUSBW - 1),
            "structural_classification": "476.37 EXCEEDS the 450 per-direction "
            "physical aggregate by 5.86%: no physical B <= 450 can produce it "
            "under the single-port injection abstraction, and every L0 "
            "backend declares 'in_network_computing' explicitly unsupported — "
            "the 360-vs-476.37 split is an ALGORITHM-CLASS axis "
            "(ring/simple vs NVLS-class in-switch reduction), outside the L0 "
            "input space; GF-02's thread itself pins only that 360 is the "
            "expected H100 figure for the poster's (unpinned) configuration",
        },
    }


def bridge_realism_context() -> dict:
    """Anchor-anchor arithmetic (no run ids by construction): where GF-02's
    plateau sits in the derating picture stage A12 audited."""
    a3 = A3_BUSBW_OVER_900
    a6 = A6_BUSBW_OVER_400
    gf02 = PLATEAU_GBPS / Fraction(450)
    return {
        "role": "extends stage A12's bridge-vs-measured audit with the first "
        "MEASURED NVLink-4 point (CAL-A12 itself staged no achieved-bandwidth "
        "number; its audit borrowed CAL-A3/A6)",
        "provenance": "CAL-A12 derating 4/5 (verified #1054 reply, stage "
        "A12); CAL-A3 measured busbw vs CAL-A2 900 line and CAL-A6 2.19.3 "
        "vs 400 rail as recorded in stage A12's record; GF-02 = 360/450 this "
        "anchor; anchor-anchor arithmetic only, no run ids claimed",
        "cal_a3_fractions_of_900": {k: str(v) for k, v in a3.items()},
        "cal_a3_fractions_range": "0.8755-1.0077 (avg 0.951)",
        "cal_a6_fractions_of_400": {k: str(v) for k, v in a6.items()},
        "gf02_fraction_of_450_exact": str(gf02),
        "gf02_fraction_of_450_float": float(gf02),
        "finding": (
            "stage A12 classified the 0.8 bridge as a conservative envelope "
            "sitting 15-18 percentage points BELOW every measured series it "
            "normalized (A3: 0.876-1.008 of 900; A6: 0.964-0.978 of 400); "
            "GF-02's community H100 plateau sits AT exactly 4/5 of its own "
            "450 per-direction ceiling (to the anchor's '~' precision) — the "
            "first measured point ON the bridge rather than above it. "
            "Classification: the per-fabric/software-config derating factor "
            "is not a constant; it spans [0.8, ~1.0] across the staged "
            "NVLink points, with GF-02 (ring-class, unpinned software) at "
            "the bottom and CAL-A3's largest sizes at the top. NOT a new "
            "derating proposal — a placement fact for the owner's "
            "adjudication."
        ),
        "gf04_not_on_this_axis": "GF-04's 476.37 is ABOVE its 450 ceiling "
        "(1.0586) — it does not sit on the derating axis at all; it belongs "
        "to the in-network-computing class (see hazard_brackets)",
    }


def regime_and_structure() -> dict:
    ar360 = Fraction(
        load_json(RESULTS / RUN_ID_AR_PLATEAU360 / "observations.json")["per_op"][0][
            "completion_time_ns_exact"
        ]
    )
    return {
        "latency_axis_untestable": {
            "latency_share_at_16gib_exact": str(AR_LAT / ar360),
            "statement": "the anchor's regime (>= 128 MiB) is fully "
            "bandwidth-bound — the L term is ~5e-6 of CCT at the plateau "
            "row, so GF-02 cannot test L=200 ns (the plan's weakest-axis gap "
            "§4.2 is unchanged; same regime-boundary class as stage A12)",
        },
        "structural_expressiveness": {
            "statement": "the L0 input space has no algorithm-class "
            "parameter: NVLS/in-network computing is declared explicitly "
            "unsupported by every L0 backend, so the GF-04 side of the "
            "discrepancy is inexpressible at physical B, and the anchor's "
            "(unpinned) NCCL algorithm choice cannot be represented — the "
            "same structural-blindness class as A6 (software "
            "version/channelization) and A12 (protocol overhead); a "
            "collective-algorithm axis belongs to higher-fidelity backends",
            "classification": "structural, recorded; nothing refit",
        },
        "registry_placements": {
            "A_L0X_BW_scale": "the anchor's aggregate points 360/450 sit "
            "inside the plan's modern aggregate span [448, 900] only at 450; "
            "the measured plateau 360 is BELOW the span's lower endpoint "
            "(448) — a software-effective-rate fact, recorded, no range edit",
            "bridge_registry": "the 4/5 bridge now has BOTH an executed "
            "model-constant basis (stage A12: 300->240 on NVLink-3) and an "
            "executed measured basis (this stage: 450->360 on NVLink-4, to "
            "'~' precision)",
        },
    }


def main() -> int:
    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, stage GF-02 (gap-fill anchor GF-02), "
        "",
        "anchor": {
            "anchor_id": "GF-02",
            "title": "NCCL nccl-tests GitHub issue #326: all gather / all "
            "reduce showing unidirectional bandwidth peak performance",
            "source_row": "NOT YET a sources.csv row (gap-fill staging doc "
            "docs/calibration/anchors_gapfill.md §GF-02; the owner "
            "integrates accepted rows — suggested continuation id CAL-A13+)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-02",
            "url": "https://github.com/NVIDIA/nccl-tests/issues/326",
            "confidence": "M-H per the staging doc (community machine-pasted "
            "nccl-tests output); thread fetched and verified 2026-10-28 — "
            "see `verification`, including the staging-doc glosses the fetch "
            "CORRECTED (no 480 GB/s expectation; no 'half of 480' quote; no "
            "NCCL pin)",
            "staged_numbers": "8xH100 + NVLink; all_reduce_perf and "
            "all_gather_perf, -b 128M -e 16384M -f 2 -g 8; busbw saturated at "
            "~360 GB/s for both collectives; poster's ceiling figure: 900 "
            "GB/s bidirectional; maintainer: 360 is exactly expected on H100",
        },
        "target": {
            "role": "measured large-message O-CCT placement on the H100 "
            "NVSwitch class (R2: large-message AllReduce on scale-up "
            "fabrics), BOTH collectives of the anchor",
            "o_cct_calibratable": True,
            "regime": {
                "topology_class": "8xH100 NVLink/NVSwitch server (NVLink-4 "
                "generation); executed on the L0 crossbar identity "
                "(allreduce, the KEEP domain of A-L0X-PORT) and the L0 "
                "phase-collectives ring identity (allgather, A-L0P-ALGO)",
                "ranks": 8,
                "message_bytes_ladder": LADDER,
                "message_regime_note": "128 MiB-16 GiB (the command-line "
                "regime, verified); executed payload sizes are ladder "
                "members {2^27, 2^30, 2^34}; per-size anchor rows are "
                "screenshots (not text-extractable) — the plateau + regime "
                "endpoints are the extractable targets, per the stage's "
                "FAIL-clause duty",
            },
        },
        "verification": verification(),
        "busbw_conventions": busbw_conventions(),
        "anchor_derived": anchor_derived(),
        "model": {
            "backend_ids": ["analytical_l0_crossbar",
                            "analytical_l0_phase_collectives"],
            "identities": {
                "allreduce_crossbar": "t = 2(r-1)/r*M/B + 2L ; wire/rank "
                "2(r-1)/r*M",
                "allgather_ring": "t = (r-1)/r*M_total/B + (r-1)L ; wire/rank "
                "(r-1)/r*M_total (M_total = total gathered size, A-L0P-MSG)",
            },
            "ranks": 8,
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "360": "the anchor's measured busbw plateau (baseline; "
                    "anchor's own figure read through the pinned busbw = B "
                    "mapping)",
                    "450": "physical per-direction = 900/2 (the poster's own "
                    "bidirectional figure split; no link-count claim "
                    "load-bearing)",
                    "476.37": "GF-04's staged 8-GPU H100 busbw (open-"
                    "discrepancy bracket; exceeds 450 — in-network-computing "
                    "class; never averaged)",
                    "900": "bidirectional figure used unsplit (declared "
                    "counting-convention hazard bracket; never a bridge)",
                },
                "L_ns": 200,
                "L_provenance": "A-L0X-LAT / A-L0-LAT registry points (KEEP "
                "per plan §2.1); the anchor's regime cannot test L (see "
                "regime_and_structure)",
            },
            "assumptions": "A-L0X-PORT/-BW/-LAT/-DIV (crossbar), A-L0-BW/"
            "-LAT/-DIV + A-L0P-ALGO/-MSG/-DIV (ring phases) from "
            "experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "plateau_placement": plateau_placement(),
            "executed_bridge": executed_bridge(),
            "allreduce_sweep": sweep_table(),
            "hazard_brackets": hazard_brackets(),
            "bridge_realism_context": bridge_realism_context(),
            "regime_and_structure": regime_and_structure(),
        },
        "deviation": {
            "at_anchor_reading": "model CCT at B=360 deviates from the "
            "anchor-implied reference by exactly the fixed latency term "
            "(+2L allreduce, +14L allgather; 4.8e-6 / 4.2e-6 relative at the "
            "16 GiB rows) — same quantity, different convention",
            "at_physical_reading": "model at B=450 (900/2) predicts busbw "
            "450 vs measured 360: measured/spec = 4/5 exactly (to the "
            "anchor's '~' precision) = the CAL-A12 bridge factor; executed "
            "CCT ratio 5/4 asymptotically on BOTH collectives",
            "hazard_summary": "bidirectional misread: 2.5x too fast; GF-04 "
            "bracket: 476.37 is 5.86% ABOVE the physical per-direction "
            "aggregate — inexpressible at physical B (in-network-computing "
            "class), discrepancy kept open, never averaged",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, "
            "content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against a "
            "community-measured, maintainer-confirmed external anchor; no "
            "E3/E4 language — not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_AR_PLATEAU360, RUN_ID_AR_PERDIR450,
                        RUN_ID_AG_RING360, RUN_ID_AG_RING450],
            "sweep_ids": [SWEEP_ID_AR],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_AR}"],
            "run_backed_numbers": "every model output in comparison."
            "plateau_placement, comparison.executed_bridge and "
            "comparison.allreduce_sweep (closed-form cross-checked by exact "
            "Fraction string equality on every executed row — 4 store-run "
            "ops + 12 sweep rows — asserted in the builder); comparison."
            "bridge_realism_context and hazard_brackets are anchor-anchor "
            "arithmetic by construction (declared inline, no run ids claimed)",
            "inputs": [
                "experiments/calibration/gf02/sweep_gf02_allreduce_v1.yaml",
                "experiments/calibration/gf02/run_gf02_ar_plateau360_v1.yaml",
                "experiments/calibration/gf02/run_gf02_ar_perdir450_v1.yaml",
                "experiments/calibration/gf02/run_gf02_ag_ring360_v1.yaml",
                "experiments/calibration/gf02/run_gf02_ag_ring450_v1.yaml",
                "experiments/calibration/gf02/workloads/ (2 files)",
                "experiments/calibration/gf02/topologies/ (6 files)",
                "experiments/calibration/gf02/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf02/"
            "run_gf02_ar_plateau360_v1.yaml ; make run EXP=experiments/"
            "calibration/gf02/run_gf02_ar_perdir450_v1.yaml ; make run "
            "EXP=experiments/calibration/gf02/run_gf02_ag_ring360_v1.yaml ; "
            "make run EXP=experiments/calibration/gf02/run_gf02_ag_ring450_"
            "v1.yaml ; make sweep EXP=experiments/calibration/gf02/"
            "sweep_gf02_allreduce_v1.yaml ; python experiments/calibration/"
            "gf02/build_calibration_record.py",
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
