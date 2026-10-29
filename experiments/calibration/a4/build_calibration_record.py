"""Build the PROPOSED calibration-candidate record for anchor CAL-A4 (Q1
calibration stage A4.

CAL-A4 is the ASTRA-sim 2.0 (ISPASS 2023) simulator-vs-hardware validation
anchor: "two real systems leverage NCCL v2.4.6 which consist of 4 and 16
NVIDIA V100 GPUs using a Ring topology with 150 GB/s NVLink", message
regime 64 MB - 1.5 GB All-Reduce, "the mean error of simulation over all
configurations is 5%". It is the paper of one PINNED BACKEND of this repo,
so this stage does what no earlier stage could: it places BOTH the L0 ring
identity AND the pinned ASTRA-sim analytical instantiation inside the
anchor's own validated regime (B = 150 B/ns anchor point, r in {4, 16},
six-size 64 MiB - 1.5 GiB ladder) and measures where they sit relative to
each other and to the anchor's own numbers. Nothing is tuned — the anchor
stages NO hardware (size -> time) series, so there is nothing to tune
toward; its extractable numbers are the regime, the ~5% mean error (a
tolerance-shape precedent per CALIBRATION_PLAN.md §3.4, NOT applied), and
the validity-domain caveat (no congestion/oversubscription; <= 16 GPUs;
NVLink-3 era).

Pure function of immutable artifacts: reads this stage's append-only store
run records (2 L0 + 12 pinned-ASTRA-sim) and sweep tables, recomputes
every derived quantity with exact Fractions / integers, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

Run-backed cross-checks enforced here (a mismatch is a bug, not a finding):

1. every L0 sweep row (36 = 2 ranks x 3 B x 6 sizes) equals the closed form
   of the run path's own identity function
   (``l0.ring_allreduce_time_ns``) by exact Fraction string equality;
2. both L0 store runs equal the same closed form at their payloads;
3. every pinned-ASTRA-sim run reports ONE unique wall time across all
   ranks with wall == comm (perfectly symmetric), divisible by the 6-op
   chain (zero inter-op gap, convention A-AS1-CHAIN);
4. the per-op wall time equals, EXACTLY (integer equality, zero residual),
   the difference-report S3 decomposition laws extended with the
   local-mem processing term:
       t_astra/op = s*2(r-1)*L + s*2(r-1)*floor(msg/B)
                    + s*(2r-1)*d + s*(r-1)*3*floor(msg/mem_bw)
   with s = r (A-AS1-SPLITS), d = 10 ns (A-AS2-DELAY-POS), mem_bw = 1600
   GB/s (A-AS2-MEM-BW), msg = M/(s*r); source: difference report
   DIFF-VS-W1-SMOKE-001 (results/difference_reports/) D-S3-1/D-S3-2/U-S3-1.
   All 12 configs close with zero unattributed residue — the U-S3-1
   processing-visibility unknown is thereby extended (not "resolved": its
   11-ns anomaly lived at s = 1, outside these s = r configs).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number is either (a) transcribed from the anchor's staged
numbers in ``docs/calibration/anchors_staging.md`` §A4 (declared with
provenance), or (b) computed from stored run/sweep artifacts or the
identity/decomposition functions by this script.

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from essun.backends.analytical.l0 import (
    BACKEND_ID,
    InfraConfig,
    require_divisible,
    ring_allreduce_time_ns,
)
from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

# ---------------------------------------------------------------------------
# Stage artifacts (content addresses of this stage's runs/sweeps; identical
# manifests + code reproduce them, so replay reproduces this record).
# ---------------------------------------------------------------------------
L0_RUNS = {  # ranks -> run id (anchor point B=150, payload 3*2^29)
    4: "4c43973a72b83551445b0cb1db74a0fc6e2d39fd794263d8eb67fb9a4fa3a6a9",
    16: "bbc8fbe7efc3c91423fc1ca31d4e0ed9fdbd7f82fb9b24fd3d4661f0417ffebd",
}
ASTRA_RUNS = {  # (ranks, payload) -> run id (pinned ASTRA-sim, B=150)
    (4, 2**26): "dff5376c91ae237d71ffe95f4f13198a9802c0474b660222bfa96b967e0fcc85",
    (4, 2**27): "75a29a7f676c5a10f69a42520dbde1d9afecb06c080ecd8ef93f1c813a280d60",
    (4, 2**28): "a42e40f2af20a71e385139c77eb5b0b63b0e30cceeb70193b8351d311c20b276",
    (4, 2**29): "0475ee7cb607e4fb7e0dd83b9244c6dd46d5bdbd58bb1a8cdc7d09de8ba51e82",
    (4, 2**30): "27579c8816301436d72c4daf6f8c2c9e58c0a90df9fd32fa2fdf822ffbff9f42",
    (4, 3 * 2**29): "5d87cb6c9e6c79d9ae5060798ea216fe30ca43236577b215a3d656ec65a42fc3",
    (16, 2**26): "1d6a2535966c9c776dd534d85985eb646d5b8c35bd2c3a3709d299f5960d38d1",
    (16, 2**27): "89822b83dbbbb2cf77b206cd7eec241dfd5bd1d8e6d04a884b66b14f800dad51",
    (16, 2**28): "3f2c97b2ce9612b8f21bfe7ae24515fb88cf6f4cb5f9e0614c1aff6b729635af",
    (16, 2**29): "945e764fc9358635803e677002728088c11eed830716d762a9ffbb1450ef7eb3",
    (16, 2**30): "53f91ce9bf2552f5ebf72839c2b3948ac39176cbf2022f95183dc17d674c0bb2",
    (16, 3 * 2**29): "86f1b5069efeb61e897e0e8bcbb0a449a3af9f6d08782ee8720dcc0662b07044",
}
SWEEPS = {  # ranks -> sweep id
    4: "d6eaf74ef85ca73bcb4ff7d9cd80e6688074e47448fdcbc1d63f79546ee07f0e",
    16: "fd3c7cf975232eaee1b28f6bb17b9545b134cd1f7eed8d856fb19311bd11b11e",
}

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A4 staged numbers (docs/calibration/anchors_staging.md §A4,
# transcription confidence H — numbers verified from the paper text).
# Jeon et al., "ASTRA-sim2.0: Modeling Hierarchical Networks and
# Disaggregated Memory Systems for Distributed Deep Learning Training",
# ISPASS 2023, arXiv:2303.14006.
STAGED = {
    "systems": "two real systems, NCCL v2.4.6, 4 and 16 NVIDIA V100 GPUs, "
    "Ring topology, 150 GB/s NVLink (verbatim: '150 GB/s NVLink')",
    "message_regime": "64 MB - 1.5 GB All-Reduce",
    "mean_error": "the mean error of simulation over all configurations "
    "is 5% (exact reading 1/20)",
    "speed_datapoints": (
        "Garnet (cycle-level) 21.42 minutes vs analytical backend 1.70 s "
        "(756x faster) for 1 MB all-reduce on a 64-NPU (4x4x4) 3D Torus; "
        "analytical backend handles a 4096-NPU (16x16x16) 3D Torus in 3.14 s"
    ),
    "validity_domain": "no congestion/oversubscription modeled; validation "
    "small-scale (<= 16 GPUs) and NVLink-3 era; extrapolating the 5% band "
    "to NVL72-class fabrics is out of the validated domain (staging caveat)",
}
STAGED_MEAN_ERROR = Fraction(5, 100)  # exact reading of the staged 5%

# Declared readings of the anchor's staged text (interpretation
# conventions, recorded — never silently assumed):
CONVENTIONS = {
    "bandwidth_reading": "150 GB/s read as the per-GPU per-direction "
    "NVLink rate feeding the single ring successor link (decimal units, "
    "1 GB/s = 1 B/ns; on a ring the link B and the per-rank injection "
    "rate coincide). Supporting hardware context (declared, external to "
    "the staged text): a V100 carries 6 NVLink-2 links at 25 GB/s per "
    "direction = 150 GB/s per direction per GPU. FLAGGED ALTERNATIVE: the "
    "staged text does not state the direction convention; a bidirectional "
    "reading would halve the anchor point to 75 B/ns and double every "
    "bandwidth-term time. The anchor point row is the only thing that "
    "moves — B stays a swept free parameter either way.",
    "size_reading": "64 MB and 1.5 GB read as 64 MiB = 2^26 and "
    "1.5 GiB = 3*2^29 (binary), matching the repo's integer-byte-count "
    "discipline; the staged text pins only the regime endpoints, the "
    "interior ladder points are this stage's declared choice. A decimal "
    "reading of the endpoints (6.4e7 / 1.5e9 B) would shift sizes ~5% "
    "and every bandwidth-term time proportionally; not executed.",
    "divisibility": "r = 4 and r = 16 are powers of two and divide every "
    "ladder size exactly, so the A-L0-DIV structural input gate ACCEPTS "
    "the exact anchor regime — the positive structural contrast with "
    "stage A3, where r = 72 = 8*9 never divides a power of two and the "
    "exact sizes had to be bracketed (verified programmatically below).",
}

# Model free parameters of this stage (A-L0-BW swept, A-L0-LAT registry).
SIZES = [2**26, 2**27, 2**28, 2**29, 2**30, 3 * 2**29]
SIZE_LABELS = {
    2**26: "64MiB", 2**27: "128MiB", 2**28: "256MiB",
    2**29: "512MiB", 2**30: "1GiB", 3 * 2**29: "1.5GiB",
}
RANKS = (4, 16)
B_VALUES = {
    "25": Fraction(25),   # per-link split 150/6 (V100 NVLink-2 6 links/GPU)
    "50": Fraction(50),   # CAL-A1 NVLink5 per-port endpoint
    "150": Fraction(150),  # CAL-A4 anchor point
}
L_HOP_LATENCY_NS = Fraction(200)
ANCHOR_POINT_B = Fraction(150)

# Pinned-ASTRA-sim translation conventions (adapter constants at the pin;
# every one is a recorded TRANSLATION_ASSUMPTION, never tuned here).
ASTRA_SPLITS_RULE = "s = ranks (A-AS1-SPLITS)"
ASTRA_ENDPOINT_DELAY_NS = 10          # A-AS2-DELAY-POS (0 aborts the binary)
ASTRA_LOCAL_MEM_BW_GB_PER_S = 1600    # A-AS2-MEM-BW (absent key never completes)
OPS_PER_RUN = 6                       # W1 shape: 3 steps x 2 layers


def infra_for(ranks: int, b: Fraction) -> InfraConfig:
    return InfraConfig(
        topology_id=f"cal_a4_closed_form_r{ranks}",
        ranks=ranks,
        link_bytes_per_ns=b,
        hop_latency_ns=L_HOP_LATENCY_NS,
    )


def l0_time(payload: int, ranks: int, b: Fraction) -> Fraction:
    """Closed form of the run-path-executed identity (l0 backend)."""
    return ring_allreduce_time_ns(payload, ranks, infra_for(ranks, b))


def wire_bytes(payload: int, ranks: int) -> Fraction:
    return Fraction(2 * (ranks - 1) * payload, ranks)


def astra_decomposition(payload: int, ranks: int, b: int | Fraction) -> dict:
    """Difference-report S3 decomposition laws (D-S3-1/D-S3-2/U-S3-1),
    extended to the multi-MiB-chunk regime; exact integer ns.

    msg = M/(s*r) is the per-message chunk; the per-message link delay is
    hops*L + chunk/B with integer truncation, one MemBus endpoint delay d
    per message plus one per sub-stream, and the local-mem processing term
    3*floor(msg/mem_bw) sits ON the critical path for msg >= 2048 B
    (U-S3-1's visibility condition — every stage-A4 chunk is >= 256 KiB).
    """
    s = ranks  # A-AS1-SPLITS
    msg = payload // (s * ranks)
    lat = s * 2 * (ranks - 1) * int(L_HOP_LATENCY_NS)
    ser = s * 2 * (ranks - 1) * (msg // int(b))
    endpoint = s * (2 * ranks - 1) * ASTRA_ENDPOINT_DELAY_NS
    processing = (
        s * (ranks - 1) * 3 * (msg // ASTRA_LOCAL_MEM_BW_GB_PER_S)
    )
    return {
        "s": s,
        "msg_bytes": msg,
        "latency_term_ns": lat,            # law D-S3-1: s serialized ring passes
        "serialization_term_ns": ser,      # truncated per message (law C-S3-1)
        "endpoint_term_ns": endpoint,      # law D-S3-2
        "local_mem_processing_term_ns": processing,  # law U-S3-1 (on path here)
        "predicted_total_ns": lat + ser + endpoint + processing,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Target extraction (what the anchor's numbers do and do not pin)
# ---------------------------------------------------------------------------
def target_extraction() -> dict:
    calibratable = {
        "regime": {
            "message_bytes": SIZES,
            "message_regime": "64 MB - 1.5 GB All-Reduce (staged), executed "
            "as the declared binary ladder 2^26 .. 3*2^29",
            "ranks": list(RANKS),
            "topology_class": "unidirectional_ring (L0 abstraction of the "
            "anchor's Ring topology; plan §1.1 row CAL-A4: medium/large "
            "ring-allreduce regime)",
            "software_pins": "NCCL v2.4.6 (the HARDWARE side of the anchor's "
            "validation); our runs pin ASTRA-sim commit 4ce9ecf + Docker "
            "image + binary sha256 instead",
        },
        "error_band_precedent": {
            "staged_quote": "the mean error of simulation over all "
            "configurations is 5%",
            "role_per_plan": "CALIBRATION_PLAN §3.4: a tolerance-SHAPE "
            "precedent bounding any future nonzero O-CCT-RELERR tolerance "
            "proposal; §3.5b: CAL-A4 is reserved as an external check, not "
            "a fit target",
            "applied_here": "NO — O-CCT-RELERR stays at its E0 zero-slack "
            "policy; this stage proposes no tolerance anywhere (that is an "
            "owner CGFR decision, and see band_placement below for why "
            "transplanting it onto the pinned instantiation is not "
            "justified by anything staged)",
        },
        "validity_domain": STAGED["validity_domain"],
    }
    not_calibratable = [
        {
            "numbers": "756x (Garnet 21.42 min vs analytical 1.70 s, 1 MB "
            "all-reduce, 64-NPU 4x4x4 3D Torus); 3.14 s for a 4096-NPU "
            "(16x16x16) 3D Torus",
            "reason": "these are ASTRA-sim's own SIMULATION-SPEED "
            "measurements (wall-clock of running the simulator), not "
            "collective completion times: no observable of this platform "
            "measures another simulator's execution speed, no cycle-level "
            "Garnet backend exists here, and no 3D-Torus topology class is "
            "registered — recorded as anchor context, excluded from "
            "calibration",
        },
        {
            "numbers": "no hardware (size -> time) series is staged",
            "reason": "the anchor's 5% mean error is a SUMMARY over "
            "configurations whose per-point hardware times the staging doc "
            "does not carry, so no CCT-vs-CCT comparison against the V100 "
            "systems is constructible from the staged numbers; what this "
            "stage CAN do (and does) is execute the anchor's REGIME on our "
            "two backends and measure their mutual placement plus the "
            "model's normalization consistency with the 150 B/ns quote",
        },
    ]
    return {
        "calibratable": calibratable,
        "not_calibratable": not_calibratable,
        "declared_conventions": CONVENTIONS,
        "staged_numbers": STAGED,
    }


# ---------------------------------------------------------------------------
# 2. Structural gate acceptance (the A3 contrast, verified programmatically)
# ---------------------------------------------------------------------------
def gate_acceptance() -> dict:
    rows = []
    for ranks in RANKS:
        for size in SIZES:
            try:
                require_divisible(BACKEND_ID, "cal_a4_probe", size, ranks, "A-L0-DIV")
                accepted = True
            except ValueError:
                accepted = False
            assert accepted, (ranks, size)
            rows.append({"ranks": ranks, "payload_bytes": size, "accepted": True})
    return {
        "finding": "the A-L0-DIV input gate (structural KEEP, "
        "non-calibratable by construction per plan §2.1) ACCEPTS every "
        "stage-A4 (r, size) pair exactly — r = 4 and r = 16 are powers of "
        "two dividing every ladder payload, so unlike stage A3 (r = 72) no "
        "bracketing and no closed-form substitution is needed: every "
        "number below is run-path-executed at the anchor's exact "
        "regime points",
        "rows": rows,
        "gate_check": "require_divisible accepted for all 12 (r, size) "
        "pairs (verified programmatically while building this record)",
    }


# ---------------------------------------------------------------------------
# 3. L0 identity vs executed artifacts (sweep rows + store runs)
# ---------------------------------------------------------------------------
def l0_crosschecks() -> tuple[dict, dict, dict]:
    """Closed form vs all 36 sweep rows and both L0 store runs."""
    topo_b = {
        "ring4_a4_b25_v1": Fraction(25),
        "ring4_a4_b50_v1": Fraction(50),
        "ring4_a4_b150_v1": Fraction(150),
        "ring16_a4_b25_v1": Fraction(25),
        "ring16_a4_b50_v1": Fraction(50),
        "ring16_a4_b150_v1": Fraction(150),
    }
    sweep_rows = {}
    sweep_meta = {}
    for ranks, sweep_id in SWEEPS.items():
        table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
        assert table["workload"]["tp_size"] == ranks
        sweep_meta[ranks] = {
            "sweep_id": sweep_id,
            "manifest_path": table["manifest_path"],
            "grid": "6 sizes x 3 B {25, 50, 150} = 18 configs x 6 ops",
            "baseline": table["baseline"]["topology"],
        }
        for row in table["configs"]:
            topo = row["config_id"].split("-")[2]
            payload = row["payload_bytes"]
            expected = str(l0_time(payload, ranks, topo_b[topo]))
            assert row["o_cct"]["completion_time_ns_mean_exact"] == expected, (
                ranks, topo, payload,
            )
            sweep_rows[(ranks, topo, payload)] = row
    assert len(sweep_rows) == 36, len(sweep_rows)

    run_checks = []
    for ranks, run_id in L0_RUNS.items():
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        per_op = obs["per_op"][0]
        assert per_op["payload_bytes"] == 3 * 2**29
        assert obs["model"]["ranks"] == ranks
        assert Fraction(obs["model"]["hop_latency_ns_exact"]) == L_HOP_LATENCY_NS
        assert Fraction(obs["model"]["link_bytes_per_ns_exact"]) == ANCHOR_POINT_B
        assert per_op["completion_time_ns_exact"] == str(
            l0_time(3 * 2**29, ranks, ANCHOR_POINT_B)
        )
        assert obs["observables"]["O-CONSERVATION"]["violations"] == 0
        run_checks.append(
            {
                "run_id": run_id,
                "ranks": ranks,
                "experiment_id": run["manifest"]["experiment_id"],
                "manifest_path": run["manifest_path"],
                "payload_bytes": per_op["payload_bytes"],
                "cct_ns_exact": per_op["completion_time_ns_exact"],
                "cct_ns_float": per_op["completion_time_ns"],
                "verdict": "store run == closed form of the identity "
                "(exact equality); conservation 0 violations",
            }
        )
    return (
        {
            "finding": "all 36 sweep rows (2 ranks x 3 B x 6 sizes) equal "
            "the closed form of the run path's own identity function "
            "by exact Fraction string equality",
            "sweeps": sweep_meta,
        },
        {"anchor_point_runs": run_checks},
        {"sweep_rows": sweep_rows},
    )


# ---------------------------------------------------------------------------
# 4. Pinned-ASTRA-sim runs + the zero-residual decomposition
# ---------------------------------------------------------------------------
def astra_placement() -> tuple[dict, dict]:
    checks = []
    per_op_by_config = {}
    for (ranks, payload), run_id in sorted(ASTRA_RUNS.items()):
        obs = load_json(RESULTS / run_id / "observations.json")
        run = load_json(RESULTS / run_id / "run.json")
        occt = obs["observables"]["O-CCT"]
        wall = occt["completion_time_ns"]
        walls = {e["wall_time_ns"] for e in occt["per_rank"]}
        comms = {e["comm_time_ns"] for e in occt["per_rank"]}
        assert walls == {wall} and comms == {wall}, (run_id, walls, comms)
        assert wall % OPS_PER_RUN == 0, (run_id, wall)
        per_op = wall // OPS_PER_RUN
        dec = astra_decomposition(payload, ranks, ANCHOR_POINT_B)
        residual = per_op - dec["predicted_total_ns"]
        assert residual == 0, (ranks, payload, residual)
        per_op_by_config[(ranks, payload)] = per_op
        checks.append(
            {
                "run_id": run_id,
                "ranks": ranks,
                "payload_bytes": payload,
                "size": SIZE_LABELS[payload],
                "experiment_id": run["manifest"]["experiment_id"],
                "wall_ns": wall,
                "wall_per_op_ns": per_op,
                "symmetric_ranks": f"all {ranks} ranks report one unique "
                f"wall time == comm time == {wall}",
                "decomposition": dec,
                "residual_ns": 0,
            }
        )
    law = {
        "law": "t_astra/op = s*2(r-1)*L + s*2(r-1)*floor((M/(s*r))/B) + "
        "s*(2r-1)*d + s*(r-1)*3*floor((M/(s*r))/mem_bw)",
        "constants": {
            "s": "ranks (A-AS1-SPLITS)",
            "L_ns": str(L_HOP_LATENCY_NS),
            "d_ns": ASTRA_ENDPOINT_DELAY_NS,
            "mem_bw_GB_per_s": ASTRA_LOCAL_MEM_BW_GB_PER_S,
        },
        "provenance": "difference report DIFF-VS-W1-SMOKE-001 laws D-S3-1 "
        "(s serialized ring latency passes), C-S3-1/D-S3-1 (per-message "
        "truncated serialization), D-S3-2 (endpoint events s*(2r-1)), "
        "U-S3-1 (local-mem processing 3 ns steps, on the critical path "
        "for per-message chunks >= 2048 B — every stage-A4 chunk is "
        ">= 256 KiB)",
        "verdict": "EXACT integer equality (zero unattributed residual) at "
        "ALL 12 executed configs — the S3 decomposition laws extend "
        "unchanged into the anchor's multi-MiB-chunk regime, and the "
        "U-S3-1 processing term closes exactly at s = r (its 11-ns "
        "anomaly lived at s = 1, outside these configs; the unknown is "
        "EXTENDED to this regime, not claimed resolved)",
    }
    return {"runs": checks, "law": law}, per_op_by_config


# ---------------------------------------------------------------------------
# 5. The L0-vs-pinned-ASTRA-sim comparison (where the two backends sit)
# ---------------------------------------------------------------------------
def l0_vs_astra(per_op_by_config: dict) -> dict:
    rows = []
    for ranks in RANKS:
        for payload in SIZES:
            t_l0 = l0_time(payload, ranks, ANCHOR_POINT_B)
            t_astra = Fraction(per_op_by_config[(ranks, payload)])
            dec = astra_decomposition(payload, ranks, ANCHOR_POINT_B)
            gap = t_astra - t_l0
            lat_inflation = dec["latency_term_ns"] - 2 * (ranks - 1) * L_HOP_LATENCY_NS
            trunc = Fraction(dec["serialization_term_ns"]) - (
                wire_bytes(payload, ranks) / ANCHOR_POINT_B
            )
            endpoint = Fraction(dec["endpoint_term_ns"])
            processing = Fraction(dec["local_mem_processing_term_ns"])
            assert gap == lat_inflation + trunc + endpoint + processing
            ratio = t_astra / t_l0
            rows.append(
                {
                    "ranks": ranks,
                    "size": SIZE_LABELS[payload],
                    "payload_bytes": payload,
                    "l0_cct_ns_exact": str(t_l0),
                    "l0_cct_ns_float": float(t_l0),
                    "astra_cct_ns_exact": str(t_astra),
                    "astra_cct_ns_float": float(t_astra),
                    "ratio_astra_over_l0_exact": str(ratio),
                    "ratio_astra_over_l0_float": float(ratio),
                    "delta_pct_float": float((ratio - 1) * 100),
                    "gap_accounting_ns": {
                        "latency_inflation (s=r serialized ring passes)"
                        "_exact": str(lat_inflation),
                        "serialization_truncation_exact": str(trunc),
                        "endpoint_events_exact": str(endpoint),
                        "local_mem_processing_exact": str(processing),
                        "total_gap_exact": str(gap),
                        "residual": 0,
                    },
                    "gap_shares_pct": {
                        "latency_inflation": float(lat_inflation / gap * 100),
                        "truncation": float(trunc / gap * 100),
                        "endpoint": float(endpoint / gap * 100),
                        "processing": float(processing / gap * 100),
                    },
                }
            )
    ratios = [Fraction(r["ratio_astra_over_l0_exact"]) for r in rows]
    lo, hi = min(ratios), max(ratios)
    # asymptotic structural overhead of the recorded conventions over any
    # bandwidth-only identity: processing/serialization = 3B/(2*mem_bw)
    asym = 1 + Fraction(3 * int(ANCHOR_POINT_B), 2 * ASTRA_LOCAL_MEM_BW_GB_PER_S)
    band = STAGED_MEAN_ERROR
    return {
        "metric": "per-op CCT vs per-op CCT at the anchor point (B = 150 "
        "B/ns, L = 200 ns, s = r, d = 10 ns, mem-bw = 1600 GB/s); L0 side "
        "is the exact identity (sweep- and run-verified), ASTRA side is "
        "the parsed wall time of the same 6-op data_deps-serialized chain "
        "divided by 6 (exact division, zero remainder, symmetric ranks)",
        "rows": rows,
        "span": {
            "min_ratio_exact": str(lo),
            "max_ratio_exact": str(hi),
            "min_delta_pct": float((lo - 1) * 100),
            "max_delta_pct": float((hi - 1) * 100),
            "where": "min at r=4/1.5 GiB, max at r=16/64 MiB (the s-fold "
            "latency term is size-independent, so it dominates at small "
            "sizes and washes out as M grows)",
        },
        "asymptotic_structural_overhead": {
            "value_exact": str(asym),
            "value_float": float(asym),
            "derivation": "as M -> inf the ratio tends to 1 + "
            "3B/(2*mem_bw) = 1 + 450/3200: the local-mem processing term "
            "alone (A-AS2-MEM-BW at the pinned example value 1600 GB/s) "
            "puts the pinned instantiation structurally +14.0625% above "
            "any bandwidth-only identity at B = 150, INDEPENDENT of r and "
            "M — an arithmetic property of the recorded translation "
            "conventions, not a hardware claim",
        },
        "band_placement": {
            "anchor_band": "5% mean simulation error (the AUTHORS' "
            "ASTRA-sim configuration vs real V100 hardware)",
            "mutual_deviation_vs_band": f"the L0<->pinned-ASTRA-sim mutual "
            f"deviation at the anchor point is +{float((lo - 1) * 100):.2f}% "
            f"to +{float((hi - 1) * 100):.2f}% — "
            f"{float((lo - 1) / band):.2f}x to {float((hi - 1) / band):.2f}x "
            "the anchor's band",
            "verdict": "the anchor's 5% band is a scale precedent ONLY. "
            "It is not reproducible against our runs (no hardware series "
            "is staged), and it cannot be transplanted onto the pinned "
            "instantiation: the recorded translation conventions alone "
            "(s = ranks latency passes, forced endpoint delay, local-mem "
            "processing at multi-MiB chunks) move outputs by "
            f"{float((lo - 1) / band):.2f}x-{float((hi - 1) / band):.2f}x "
            "the band, every nanosecond attributed with zero residual. "
            "Whether any tolerance of the anchor's shape may ever be "
            "proposed for this backend pair is an owner decision "
            "contingent on the D-S3-1 splits ADR; this stage proposes no "
            "tolerance and changes no label",
        },
    }


# ---------------------------------------------------------------------------
# 6. Normalization consistency: the identity's busbw ceiling at the anchor
# ---------------------------------------------------------------------------
def normalization() -> dict:
    """Where the L0 identity sits relative to the anchor's own 150 B/ns
    quote: the ring busbw ceiling (algbw * 2(r-1)/r) tends to B exactly,
    so at the anchor point the identity's asymptotic busbw IS the anchor's
    NVLink quote — the same normalization structure as stages A1/A2."""
    rows = []
    for ranks in RANKS:
        for payload in SIZES:
            t = l0_time(payload, ranks, ANCHOR_POINT_B)
            algbw = Fraction(payload) / t
            busbw = algbw * Fraction(2 * (ranks - 1), ranks)
            rows.append(
                {
                    "ranks": ranks,
                    "size": SIZE_LABELS[payload],
                    "l0_implied_busbw_B_per_ns_exact": str(busbw),
                    "l0_implied_busbw_fraction_of_150_exact": str(
                        busbw / ANCHOR_POINT_B
                    ),
                }
            )
    small = {
        r: Fraction(rows[i * len(SIZES)]["l0_implied_busbw_fraction_of_150_exact"])
        for i, r in enumerate(RANKS)
    }
    large = {
        r: Fraction(rows[(i + 1) * len(SIZES) - 1]["l0_implied_busbw_fraction_of_150_exact"])
        for i, r in enumerate(RANKS)
    }
    return {
        "role": "the anchor's 150 B/s quote is a LINK CAPABILITY, not a "
        "completion time; the identity approaches it from below and can "
        "never exceed it (same structure as stage A1's per-port and stage "
        "A2's injection ceilings)",
        "rows": rows,
        "asymptote": "busbw -> B = 150 B/ns = the anchor's quote exactly "
        f"(algebraic limit; 64 MiB already sits at "
        f"{float(small[4]):.5f} (r=4) / {float(small[16]):.5f} (r=16), "
        f"1.5 GiB at {float(large[4]):.5f} / {float(large[16]):.5f} "
        "— computed, not transcribed)",
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def main() -> int:
    target = target_extraction()
    gate = gate_acceptance()
    sweep_checks, run_checks, _ = l0_crosschecks()
    astra, per_op_by_config = astra_placement()
    comparison = l0_vs_astra(per_op_by_config)
    norm = normalization()

    span = comparison["span"]
    asym = comparison["asymptotic_structural_overhead"]
    deviation_summary = (
        f"at the anchor point (B = 150 B/ns, r in {{4, 16}}, 64 MiB-1.5 GiB) "
        f"the pinned ASTRA-sim instantiation sits "
        f"+{span['min_delta_pct']:.2f}% to +{span['max_delta_pct']:.2f}% "
        "above the L0 ring identity, and the ENTIRE gap is attributed with "
        "zero residual to the recorded translation conventions: the s = "
        "ranks serialized ring latency passes (A-AS1-SPLITS), the forced "
        "10 ns endpoint delay (A-AS2-DELAY-POS), and the local-mem "
        "processing term at multi-MiB chunks (A-AS2-MEM-BW, 1600 GB/s "
        "pinned-example value) which ALONE imposes an asymptotic "
        f"+{float((Fraction(asym['value_exact']) - 1) * 100):.4f}% "
        "(exactly 1 + 3B/(2*1600) at B = 150) structural overhead over any "
        "bandwidth-only identity, independent of r and M"
    )
    band_verdict = comparison["band_placement"]["verdict"]

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A4 (anchor CAL-A4)",
        "anchor": {
            "anchor_id": "CAL-A4",
            "title": "ASTRA-sim 2.0 (ISPASS 2023): analytical-backend validation vs real V100 systems",
            "source_row": "the anchor registry row CAL-A4 (PROPOSED)",
            "staging_doc": "docs/calibration/anchors_staging.md §A4",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A4 (calibration target + methodological template for the analytical-backend family)",
            "citation": "M. Jeon et al., ISPASS 2023, arXiv:2303.14006",
            "confidence": "H (numbers verified from paper text); validation "
            "small-scale (<= 16 GPUs) and NVLink-3 era; the paper's build "
            "and system configuration are NOT this repo's pinned commit "
            "and translation conventions",
        },
        "target": target,
        "anchor_derived": {
            "divisibility_gate": gate,
            "note": "the anchor's own numbers only: regime endpoints, the "
            "150 B/ns quote (declared per-direction reading, alternative "
            "flagged), and the 5% summary error; no hardware series exists "
            "to derive further",
        },
        "model": {
            "backends_compared": {
                "l0": {
                    "backend_id": "analytical_l0",
                    "identity": "t = 2*(r-1)/r*M/B + 2*(r-1)*L ; per-rank "
                    "wire bytes = 2*(r-1)/r*M",
                    "free_parameters": {
                        "B_swept_bytes_per_ns": {
                            "25": "per-link per-direction split 150/6 "
                            "(V100 NVLink-2 6 links/GPU hardware context, "
                            "consistent with CAL-A12's 25 GB/s/link scale)",
                            "50": "CAL-A1 NVLink5 per-port cross-generation endpoint",
                            "150": "CAL-A4 anchor point (the paper's staged quote)",
                        },
                        "L_hop_latency_ns": 200,
                        "L_provenance": "A-L0-LAT registry point (KEEP per "
                        "plan §2.1); latency axis deferred to its own "
                        "global stage",
                    },
                },
                "astra_sim_analytical": {
                    "pin": "commit 4ce9ecfe746a3ee5fe47559a11d91644d641fa7f, "
                    "image essun/astra-sim-analytical:s1, binary sha256 "
                    "ecc3a52d44c7134ce353ed03b8cb0076e5bfdbf2659bcdbb0cc5f2d760749ea4",
                    "translation_conventions": "A-AS1-SPLITS s = ranks, "
                    "A-AS1-CHUNKS-1, A-AS2-DELAY-POS d = 10 ns, A-AS2-MEM-BW "
                    "1600 GB/s (all recorded in src/essun/backends/"
                    "astra_sim/adapter.py with in-tree anchors; NOT the "
                    "paper's configuration)",
                    "executed_at": "anchor point B = 150 B/ns only (the B "
                    "sweep is the L0-side free-parameter span)",
                },
            },
            "assumptions": "A-L0-BW / A-L0-LAT / A-L0-FD / A-L0-DIV "
            "(experiments/vertical_slice/assumptions_l0.yaml); plan §2.1 "
            "A-L0P-ALGO note applies: ring-on-ring is exactly the pairing "
            "CAL-A4's NCCL ring runs exercise",
        },
        "comparison": {
            "l0_vs_astra_sim": comparison,
            "pinned_backend_runs": astra,
            "l0_executed_artifact_checks": {
                **sweep_checks,
                **run_checks,
            },
            "normalization_consistency": norm,
        },
        "deviation": {
            "summary": deviation_summary,
            "band_verdict": band_verdict,
            "not_tuned": "nothing was tuned: the anchor stages no hardware "
            "completion-time series, so there is nothing to tune toward; "
            "the swept B values carry anchor provenance fixed before any "
            "stage output was read; the decomposition constants are the "
            "adapter's recorded translation assumptions, not fitted values",
        },
        "evidence_levels": {
            "runs": "E0 (2 L0 analytical executions + 12 pinned-DES "
            "executions; deterministic, content-addressed, replay-verified "
            "byte-identical)",
            "candidate": "PROPOSED calibration placement inside a "
            "peer-reviewed validated regime; no E3/E4 language — CAL-A4's "
            "hardware is not our testbed, and the owner's adjudication "
            "precedes any label move",
        },
        "backing": {
            "l0_run_ids": [L0_RUNS[4], L0_RUNS[16]],
            "astra_run_ids": [ASTRA_RUNS[k] for k in sorted(ASTRA_RUNS)],
            "sweep_ids": [SWEEPS[4], SWEEPS[16]],
            "run_backed_numbers": "every number: L0 values are the "
            "identity function cross-checked against all 36 sweep rows and "
            "both store runs by exact Fraction string equality; ASTRA "
            "values are parsed wall times of the 12 stored runs, "
            "decomposed with zero residual by the cited difference-report "
            "laws",
            "inputs": [
                "experiments/calibration/a4/sweep_a4_ring4_v1.yaml",
                "experiments/calibration/a4/sweep_a4_ring16_v1.yaml",
                "experiments/calibration/a4/run_a4_ring4_anchor_v1.yaml",
                "experiments/calibration/a4/run_a4_ring16_anchor_v1.yaml",
                "experiments/calibration/a4/run_a4_astra_ring4_*_v1.yaml (6)",
                "experiments/calibration/a4/run_a4_astra_ring16_*_v1.yaml (6)",
                "experiments/calibration/a4/topologies/ (6 files)",
                "experiments/calibration/a4/workloads/ (12 files)",
                "experiments/calibration/a4/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/a4/"
            "run_a4_ring4_anchor_v1.yaml ; make run EXP=experiments/"
            "calibration/a4/run_a4_ring16_anchor_v1.yaml ; make run "
            "EXP=experiments/calibration/a4/run_a4_astra_ring4_64mib_v1.yaml "
            "(.. all 12 astra manifests ..) ; make sweep EXP=experiments/"
            "calibration/a4/sweep_a4_ring4_v1.yaml ; make sweep "
            "EXP=experiments/calibration/a4/sweep_a4_ring16_v1.yaml ; "
            "python experiments/calibration/a4/build_calibration_record.py",
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
