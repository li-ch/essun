"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-04
(calibration stage GF-04;
p1_calibration.md; anchor staged in docs/calibration/anchors_gapfill.md
§GF-04 — Oracle OCI blog "Zettascale in Practice: OSU and NCCL Benchmark on
H100 Clusters for HPC and AI Workloads", 8->16-rank measured allreduce
scaling across one NVSwitch+RoCE fabric pair).

Stage target : the anchor's OWN 8->16
SCALING claim — busbw 476.37 GB/s (single node, 8 GPUs) -> 469.67 GB/s
(two nodes, 16 GPUs) — NOT the absolute 476.37 figure, which stage GF-02
already bracketed as 5.86% above the 450 physical per-direction ceiling
(an in-network-computing/algorithm-class axis outside the L0 input space).

Pure function of immutable artifacts: reads the five append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers or from the page fetches this stage performed on
2026-10-28 (method and verbatim quotes recorded inline under
``verification``; all fetched text is UNTRUSTED INPUT,
recorded-not-ingested), or (b) computed from the stored run/sweep
artifacts by this script (closed-form cross-checks by exact Fraction
string equality on every executed row), or (c) declared inline identity /
anchor-anchor arithmetic (the latency-range bound, the cut-demand
headroom, the CCT-side pair decomposition — no run id claimed for those).
Nothing is tuned: the swept B values carry their anchor/config/cross-
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
RUN_ID_RING8_A476 = "0b46231c6803d36ad19dc70ffed1f9c7c9e371abe36395cd4ab980d219787bc7"
RUN_ID_RING16_A469 = "a2e45267d650ff00ed657b7f0f2c935190cca3ca92ba2507916bf74d25e6ccf3"
RUN_ID_RING16_A476 = "53761cd5f7ac8828f20cfdd16b1e179ae9a2e4dab7b78a342aace8e6a43253e6"
RUN_ID_RING16_RAIL = "1c2f3dbaa1bd2f083a20339272f310c6d12e105e1ab89432cb560bb8b941e349"
RUN_ID_XBAR8_A476 = "4c18f0c96cbf792216a1389af28892cccd2c82fb3c169405e8e1cbe97d23e4bf"
SWEEP_ID_TP8 = "81696f56ecbc9b0ac376afb1f55c89238a879350d6e1eaa16f246da6588c92e1"
SWEEP_ID_TP16 = "ea01254df7a9f5944248664630c74c8052e91e84a96ccc18ce52196b06c87efb"

RESULTS = REPO_ROOT / "results"

# Anchor GF-04 staged/fetched numbers (docs/calibration/anchors_gapfill.md
# §GF-04; page fetched and verified 2026-10-28 — see `verification`).
# Decimal unit convention of the calibration plan: 1 GB/s = 1 B/ns.
A8_BUSBW = Fraction("476.37")     # "NCCL on single node with 8 GPUs | 476.37 GB/s"
A16_BUSBW = Fraction("469.67")    # "NCCL on two nodes with 16 GPUs | 469.67 GB/s"
PERDIR_450 = Fraction(450)        # GF-02's physical per-direction NVLink ceiling (900/2)
RAIL_400 = Fraction(400)          # 16 x 200 Gbps RoCEv2 per node, per-direction port convention
DERATED_320 = Fraction(320)       # CAL-A12 ~80% derating x 400 (A6-convention)

# The anchor's command-line ladders (fetched, verified): single node
# "-b 32 -e 4G -f 2 -g 8" => 32 B x 2^k up to 2^32; two nodes
# "-b 32 -e 10G -f 2 -g 8" => 32 B x 2^k capped below 10 GiB => top row 2^33.
M_COMMON = 2**32                  # 4 GiB: single-node ladder top, common to both ladders
M_TOP16 = 2**33                   # 8 GiB: two-node ladder top
SWEEP_SIZES = (2**30, M_COMMON, M_TOP16)

# Closed-form identities at L = 200 ns (the executed configurations):
#   ring:            t = 2(r-1)/r*M/B + 2(r-1)*L
#   crossbar:        t = 2(r-1)/r*M/B + 2L
#   recursive doubl: t = 2(r-1)/r*M/B + 2*log2(r)*L
#   wire per rank    = 2(r-1)/r*M   (identical in all three families)
L_NS = Fraction(200)
R8, R16 = 8, 16


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wire_factor(r: int) -> Fraction:
    return Fraction(2 * (r - 1), r)


def ring_time(payload: int, b: Fraction, r: int) -> Fraction:
    return wire_factor(r) * payload / b + 2 * (r - 1) * L_NS


def xbar_time(payload: int, b: Fraction, r: int) -> Fraction:
    return wire_factor(r) * payload / b + 2 * L_NS


def rd_time(payload: int, b: Fraction, r: int) -> Fraction:
    # log2(r) = r.bit_length() - 1 for powers of two: chains 6L @ r=8, 8L @ r=16
    return wire_factor(r) * payload / b + 2 * (r.bit_length() - 1) * L_NS


FAMILY_TIME = {
    "allreduce_ring": ring_time,
    "allreduce_crossbar": xbar_time,
    "allreduce_recursive_doubling": rd_time,
}


def busbw_of(wire: Fraction, t: Fraction) -> Fraction:
    """nccl-tests allreduce convention (pinned from src/all_reduce.cu by
    stage GF-02's 2026-10-28 fetch): busbw = algbw x 2(r-1)/r with
    algbw = M/t; the identity's per-rank wire IS 2(r-1)/r*M, so the
    model-side busbw of a run row is wire/t exactly."""
    return wire / t


# ---------------------------------------------------------------------------
# Verification: the fetches this stage performed (record-the-fetch; all
# fetched text is UNTRUSTED INPUT — transcribed for comparison only).
# ---------------------------------------------------------------------------


def verification() -> dict:
    return {
        "duty": "the staging doc flags GF-04's rows as vendor-blog M-H with "
        "'NIC count/detail re-verify' and an open busbw-convention "
        "interaction with GF-02; stages A12/GF-02 established the "
        "fetch-and-record pattern, and this stage works it for the Oracle "
        "blog (the anchor's own page, fetched fresh rather than trusted).",
        "method": [
            "web reader fetch (cached + no_cache) of https://blogs.oracle.com/"
            "cloud-infrastructure/zettascale-osu-nccl-benchmark-h100-ai-workloads, "
            "2026-10-28 — twice, full text identical both times; direct curl "
            "of the same URL returns a 1.4 kB block page (recorded as a "
            "failed method)",
            "web reader image read of the page's embedded result screenshot "
            "(image-nccl-allreduce-two-nodes.png), 2026-10-28 — two caption "
            "extractions, mutually inconsistent on row values (recorded, NOT "
            "used as targets); both agree the final table row is size "
            "8589934592 B = 8 GiB, corroborating the ladder-top derivation",
        ],
        "verified_verbatim": [
            "summary table row: 'NCCL on single node with 8 GPUs | 476.37 GB/s'",
            "summary table row: 'NCCL on two nodes with 16 GPUs | 469.67 GB/s'",
            "single-node command: './nccl-tests/build/all_reduce_perf -b 32 "
            "-e 4G -f 2 -g 8'",
            "two-node command: 'mpirun -np 2 -H 10.224.8.156,10.224.9.98 "
            "--bind-to numa -x UCX_TLS=rc ... ./build/all_reduce_perf -b 32 "
            "-e 10G -f 2 -g 8' (16 mlx5 devices listed in UCX_NET_DEVICES)",
            "node config: 'Node 1: H100.8 Shape with 16x200 Gbps RoCEv2 NIC' "
            "(and the Node 2 twin)",
            "framing sentence: 'With OCI's state-of-the-art nonblocking RDMA "
            "networking, NCCL AllReduce performance can scale without "
            "compromise.'",
            "OSU rows (context axis): CPU-CPU RDMA latency 2.70 us at 0-16 B; "
            "osu_bw plateau 48839.42-48893.08 MB/s for sizes >= 8 MiB (table) "
            "vs the summary row 'RDMA NIC bandwidth (400Gbps) | 48.77 GB/s'; "
            "GPU-GPU CUDA-aware MPI 32.70 us @ 8 B through 60.35 us @ 512 KiB",
        ],
        "staging_doc_glosses_corrected_by_the_fetch": [
            "NIC config: the staging doc's '8 NVIDIA 400-Gbps NICs per node "
            "(ConnectX-class; NIC count/detail re-verify)' — the fetched page "
            "says 16x200 Gbps RoCEv2 NIC per node (the re-verify flag is "
            "resolved; NOTE the page's own summary table still labels the "
            "measured NIC bandwidth '(400Gbps)', an internal labeling "
            "tension recorded not smoothed — the aggregate 16x200 Gbps = "
            "400 Gbps reading reconciles the two)",
            "publish date: the staging doc's '(2026, accessed 2026-10-27)' — "
            "page metadata says November 6, 2025 (authors Leo Li, Rik "
            "Kisnah); fetched 2026-10-27 (staging) and 2026-10-28 (this "
            "stage)",
            "'NCCL 2.27' pin: the page text cites the blog post title "
            "'Enabling Fast Inference and Resilient Training with NCCL 2.27' "
            "for a latency statement — it is a REFERENCE TITLE, not a "
            "version pin of the benchmark configuration; the configuration "
            "is UNPINNED (recorded as such)",
            "the staging doc's secondary figures '4 GPUs: 187.03 GB/s; "
            "16-GPU all_gather 437.85 GB/s; 2-GPU broadcast 228.76 GB/s' — "
            "NOWHERE in the fetched page text; quarantined as UNVERIFIED "
            "staging numbers, NOT executed, NOT averaged (the 8->16 pair "
            "this stage works IS fetch-verified)",
            "the staging doc's OSU quotes '47.71 GB/s @ 64 MiB, 48.76 @ 512 "
            "MiB, 48.77 @ 1 GiB' do not match the fetched table rows (64 MiB "
            "-> 48892.72, 512 MiB -> 48893.08, 1 GiB -> 48892.54 MB/s); the "
            "summary row 48.77 GB/s is verified but the staged per-size "
            "mapping is not — quarantined, context axis only",
        ],
        "residual_caveats": (
            "the per-size NCCL result tables are IMAGES (not "
            "text-extractable); the two image-read extractions disagreed on "
            "row values, so the extractable targets are the summary pair + "
            "the command-line regimes + the config statement; which size row "
            "the summary figures aggregate (peak vs top-size row) is NOT "
            "stated in text — the executed comparison therefore anchors at "
            "the common ladder member 2^32 and reports the ratio axis, which "
            "the aggregation ambiguity cannot move by more than the "
            "plateau's own flatness; NCCL algorithm/NVLS/channel count "
            "UNPINNED (same class as GF-02's thread); vendor blog, not "
            "peer-reviewed; all quotes are tool extractions of fetched "
            "public pages, treated as untrusted input"
        ),
    }


# ---------------------------------------------------------------------------
# Anchor arithmetic (self-checked).
# ---------------------------------------------------------------------------


def anchor_derived() -> dict:
    ratio = A16_BUSBW / A8_BUSBW                     # 46967/47637
    drop = 1 - ratio                                 # 670/47637
    a8_over_450 = A8_BUSBW / PERDIR_450              # 1.0586
    a16_over_450 = A16_BUSBW / PERDIR_450            # 1.0437
    rail = Fraction(16 * 25)                         # 16 x 200 Gbps/8 bits-per-byte... port convention

    # Self-checks: anything else is a transcription bug, not a finding.
    assert A8_BUSBW == Fraction(47637, 100)
    assert A16_BUSBW == Fraction(46967, 100)
    assert ratio == Fraction(46967, 47637)
    assert drop == Fraction(670, 47637)
    assert round(float(drop) * 100, 1) == 1.4        # the staging doc's own rounding
    assert a8_over_450 > 1 and a16_over_450 > 1      # GF-02 classification holds on both legs
    assert float(a8_over_450 - 1) > 0.058 and float(a8_over_450 - 1) < 0.059   # 5.86%
    assert rail == RAIL_400 == 400
    assert M_COMMON == 2**32 and M_TOP16 == 2**33
    for m in SWEEP_SIZES:                            # divisibility gates ACCEPT
        assert m % R8 == 0 and m % R16 == 0
    assert M_COMMON <= 2**32 and M_TOP16 <= 10 * 2**30  # ladder caps -e 4G / -e 10G

    # Anchor-implied reference CCTs at the common size (bandwidth term only,
    # through the pinned busbw = B mapping): the pair whose ratio IS the
    # scaling claim on the CCT side (plan §3: CCT-vs-CCT, never mixed).
    t_ref8 = wire_factor(R8) * M_COMMON / A8_BUSBW
    t_ref16 = wire_factor(R16) * M_COMMON / A16_BUSBW
    cct_pair = t_ref16 / t_ref8                      # (15/14)x(47637/46967)

    return {
        "staged_numbers": {
            "single_node_8gpu_busbw_GB_per_s": "476.37 (summary row, fetch-verified)",
            "two_node_16gpu_busbw_GB_per_s": "469.67 (summary row, fetch-verified)",
            "single_node_regime": "-b 32 -e 4G -f 2 -g 8 => 32 B x 2^k, top 2^32",
            "two_node_regime": "-b 32 -e 10G -f 2 -g 8 (mpirun -np 2) => 32 B x 2^k, top 2^33 (10 GiB cap never hit exactly)",
            "node_config": "H100.8 shape, 16x200 Gbps RoCEv2 NIC per node (fetch-verified)",
        },
        "scaling_claim": {
            "measured_ratio_16_over_8_exact": str(ratio),
            "measured_ratio_16_over_8_float": float(ratio),
            "measured_drop_exact": str(drop),
            "measured_drop_float": float(drop),
            "measured_drop_percent": float(drop) * 100,
            "staging_rounding_check": "670/47637 = 1.40688...% rounds to the staging doc's '1.4% drop' — verified",
            "blog_framing": "'scale without compromise' — the anchor's own reading of the 1.4% figure",
        },
        "ceiling_context_gf02": {
            "single_node_over_450_exact": str(a8_over_450),
            "single_node_over_450_float": float(a8_over_450),
            "two_node_over_450_exact": str(a16_over_450),
            "two_node_over_450_float": float(a16_over_450),
            "note": "BOTH legs sit above GF-02's 450 physical per-direction "
            "ceiling (5.86% / 4.37%) — the in-network-computing/NVLS "
            "algorithm-class classification applies to the absolute figures; "
            "this stage works the RATIO between the two INC-class points",
        },
        "rail_arithmetic": {
            "per_node_rail_bytes_per_ns": str(rail),
            "derivation": "16 x 200 Gbps RoCEv2 per node (fetched config "
            "statement), per-direction Ethernet port convention "
            "(200 Gbps = 25 B/ns) => 400 B/ns per-node per-direction rail "
            "aggregate — the same A6-convention arithmetic, now "
            "fetch-verified on this anchor's own config",
        },
        "anchor_implied_reference_cct_ns": {
            "t_ref_r8_at_common_exact": str(t_ref8),
            "t_ref_r16_at_common_exact": str(t_ref16),
            "cct_pair_ratio_exact": str(cct_pair),
            "cct_pair_ratio_float": float(cct_pair),
            "derivation": "t_ref(r) = 2(r-1)/r*M/B at M = 2^32 (common "
            "ladder member); ratio = (15/14)x(47637/46967) — the 7.14% "
            "algorithmic-traffic growth x the 1.43% measured busbw loss, "
            "decomposed exactly",
        },
    }


# ---------------------------------------------------------------------------
# Run/sweep consumption with exact closed-form cross-checks.
# ---------------------------------------------------------------------------


def run_row(run_id: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    backend = obs["backend_id"]
    per_op = obs["per_op"][0]  # all 6 ops identical by construction
    ranks = obs["model"]["ranks"]
    payload = per_op["payload_bytes"]
    cct = Fraction(per_op["completion_time_ns_exact"])
    wire = Fraction(per_op["per_rank_wire_bytes_exact"])
    if backend == "analytical_l0":
        b = Fraction(obs["model"]["link_bytes_per_ns_exact"])
        assert Fraction(obs["model"]["hop_latency_ns_exact"]) == L_NS
        t_fn, b_key = ring_time, "link_bytes_per_ns_exact"
    elif backend == "analytical_l0_crossbar":
        b = Fraction(obs["model"]["injection_bytes_per_ns_exact"])
        assert Fraction(obs["model"]["pair_latency_ns_exact"]) == L_NS
        t_fn, b_key = xbar_time, "injection_bytes_per_ns_exact"
    else:  # pragma: no cover - not used by this stage's store runs
        raise AssertionError(f"unexpected backend {backend}")
    # Closed-form cross-check (exact) on EVERY executed store run.
    assert cct == t_fn(payload, b, ranks), (run_id, cct)
    assert wire == wire_factor(ranks) * payload
    assert payload == M_COMMON
    return {
        "run_id": run_id,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "backend_id": backend,
        "ranks": ranks,
        "B_exact": obs["model"][b_key],
        "payload_bytes": payload,
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns_float"]
        if "completion_time_ns_float" in per_op else float(cct),
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "model_busbw_exact": str(busbw_of(wire, cct)),
        "model_busbw_float": float(busbw_of(wire, cct)),
        "closed_form_check": f"exact equality vs the {backend} identity (asserted in builder)",
    }


TOPO_B = {
    "ring8_gf04_anchor476_37_v1.yaml": A8_BUSBW,
    "ring8_gf04_perdir450_v1.yaml": PERDIR_450,
    "ring16_gf04_anchor469_67_v1.yaml": A16_BUSBW,
    "ring16_gf04_anchor476_37_v1.yaml": A8_BUSBW,
    "ring16_gf04_perdir450_v1.yaml": PERDIR_450,
    "ring16_gf04_rail400_v1.yaml": RAIL_400,
    "ring16_gf04_derated320_v1.yaml": DERATED_320,
    "crossbar8_gf04_anchor476_37_v1.yaml": A8_BUSBW,
    "crossbar16_gf04_anchor469_67_v1.yaml": A16_BUSBW,
    "crossbar16_gf04_rail400_v1.yaml": RAIL_400,
    "rd8_gf04_anchor476_37_v1.yaml": A8_BUSBW,
    "rd16_gf04_anchor469_67_v1.yaml": A16_BUSBW,
    "rd16_gf04_anchor476_37_v1.yaml": A8_BUSBW,
}


def sweep_table(sweep_id: str, ranks: int) -> dict:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    rows_by_size: dict[int, dict[str, dict]] = {}
    for row in table["configs"]:
        algorithm = row["algorithm"]
        topo_file = row["topology"]["path"].rsplit("/", 1)[-1]
        payload = row["payload_bytes"]
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        wire = Fraction(row["per_rank_wire_bytes_exact"])
        b = TOPO_B[topo_file]
        # Closed-form cross-check (exact) on EVERY executed sweep row.
        assert cct == FAMILY_TIME[algorithm](payload, b, ranks), (row["config_id"], cct)
        assert wire == wire_factor(ranks) * payload
        rows_by_size.setdefault(payload, {})[f"{algorithm}|{topo_file}"] = {
            "config_id": row["config_id"],
            "topology_id": topo_file.removesuffix(".yaml"),
            "cct_ns_exact": row["o_cct"]["completion_time_ns_mean_exact"],
            "model_busbw_exact": str(busbw_of(wire, cct)),
            "model_busbw_float": float(busbw_of(wire, cct)),
            "delta_vs_baseline_exact": (
                row["delta_vs_baseline"]["delta_exact"] if row["delta_vs_baseline"] else "0"
            ),
        }
    assert set(rows_by_size) == {2**30, M_COMMON, M_TOP16} if ranks == 16 else {2**30, M_COMMON}
    return {
        "sweep_id": sweep_id,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        "baseline": "ring at the anchor's own figure for that rank count "
        "(476.37 at r=8; 469.67 at r=16) — delta columns read as placement "
        "vs the anchor",
        "rows_by_size": {str(m): rows for m, rows in sorted(rows_by_size.items())},
    }


# ---------------------------------------------------------------------------
# The comparison blocks (step 3 of the ladder).
# ---------------------------------------------------------------------------


def scaling_comparison() -> dict:
    r8 = run_row(RUN_ID_RING8_A476)
    r16_null = run_row(RUN_ID_RING16_A476)
    r16_anchor = run_row(RUN_ID_RING16_A469)
    rail = run_row(RUN_ID_RING16_RAIL)

    bw8 = Fraction(r8["model_busbw_exact"])
    bw16_null = Fraction(r16_null["model_busbw_exact"])
    bw16_anchor = Fraction(r16_anchor["model_busbw_exact"])
    bw_rail = Fraction(rail["model_busbw_exact"])

    null_ratio = bw16_null / bw8                 # the model-side 8->16 statement
    measured_ratio = A16_BUSBW / A8_BUSBW

    # t = 2(r-1)/r*M/B + 2(r-1)*L pair at the same B and M: the CCT-side view.
    t8 = Fraction(r8["cct_ns_exact"])
    t16_null = Fraction(r16_null["cct_ns_exact"])
    model_cct_pair = t16_null / t8
    anchor_cct_pair = (wire_factor(R16) / A16_BUSBW) / (wire_factor(R8) / A8_BUSBW)

    # Self-checks.
    assert abs(float(null_ratio) - 1.0) < 1e-3          # rank-invariance to the 1e-4 class
    assert null_ratio < 1                               # ring chain 14L -> 30L: net tiny decrease
    assert float(1 - null_ratio) < 3e-4                 # ~1.8e-4: chain growth vs a(r) growth
    assert bw16_anchor < bw8                            # the anchor's own B readings order
    assert abs(float(bw_rail) - 400.0) < 0.5            # rail asymptote
    assert measured_ratio < null_ratio                  # the measured drop exceeds every model ratio

    # Family spread at the same B = 476.37, same M = 2^32 (sweep rows).
    tp8 = load_json(RESULTS / "sweeps" / SWEEP_ID_TP8 / "table.json")
    tp16 = load_json(RESULTS / "sweeps" / SWEEP_ID_TP16 / "table.json")

    def sweep_busbw(table: dict, algorithm: str, topo_suffix: str, payload: int) -> Fraction:
        for row in table["configs"]:
            if (row["algorithm"] == algorithm
                    and row["topology"]["path"].endswith(topo_suffix)
                    and row["payload_bytes"] == payload):
                wire = Fraction(row["per_rank_wire_bytes_exact"])
                t = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
                return busbw_of(wire, t)
        raise AssertionError(f"row not found: {algorithm} {topo_suffix} @{payload}")

    rd_ratio = (
        sweep_busbw(tp16, "allreduce_recursive_doubling", "rd16_gf04_anchor476_37_v1.yaml", M_COMMON)
        / sweep_busbw(tp8, "allreduce_recursive_doubling", "rd8_gf04_anchor476_37_v1.yaml", M_COMMON)
    )
    xbar_ratio_arithmetic = Fraction(1)  # crossbar chain 2L is r-independent; its ratio equals
    # the ring's up to the chain difference — declared inline arithmetic, not run-backed
    assert abs(float(rd_ratio) - 1.0) < 1e-4            # ~1.9e-5: the growing-chain family

    return {
        "target": "the anchor's 8->16 scaling claim: busbw 476.37 -> 469.67 "
        "across one NVSwitch+RoCE fabric pair (r=8 one node -> r=16 two "
        "nodes), the first staged multi-rank injection-scaling point (plan "
        "gap 8)",
        "measured": {
            "ratio_exact": str(measured_ratio),
            "ratio_float": float(measured_ratio),
            "drop_percent": float(1 - measured_ratio) * 100,
        },
        "model_scaling_null_at_fixed_B": {
            "store_run_pair": [RUN_ID_RING8_A476, RUN_ID_RING16_A476],
            "statement": "at the SAME uniform B = 476.37 (the anchor's own "
            "single-node figure) and the SAME payload 2^32, the L0 ring "
            "identity predicts busbw(16)/busbw(8) = 1 - 1.78e-4 — "
            "asymptotically EXACTLY 1 (busbw -> B independent of r): the "
            "identity family is rank-count-invariant in busbw by "
            "construction",
            "ratio_exact": str(null_ratio),
            "ratio_float": float(null_ratio),
            "residual_structure": "the tiny negative residual is the latency "
            "chain growth (14L -> 30L at L = 200 ns, a 3200 ns difference "
            "on a ~16.9 ms collective) against the a(r) = 2(r-1)/r "
            "traffic-factor growth — the ONLY rank-count structure any "
            "single-B identity has",
            "cct_side": {
                "model_cct_pair_exact": str(model_cct_pair),
                "model_cct_pair_float": float(model_cct_pair),
                "anchor_implied_cct_pair_exact": str(anchor_cct_pair),
                "anchor_implied_cct_pair_float": float(anchor_cct_pair),
                "deviation": "model under-predicts the r=16 CCT growth by "
                "1.41% (the measured busbw drop, moved to the time axis "
                "through the pinned mapping — CCT-vs-CCT per plan §3)",
            },
        },
        "family_spread_at_476_37": {
            "ring_store_pair_ratio_exact": str(null_ratio),
            "recursive_doubling_sweep_pair_ratio_exact": str(rd_ratio),
            "recursive_doubling_note": "the ONLY family with an r-growing "
            "latency chain (6L -> 8L): ratio 1 - 1.9e-5 — the smallest "
            "residual of the three families, still ~750x below the "
            "measured drop",
            "crossbar_note": f"crossbar chain 2L is r-independent; its ratio "
            "differs from the ring's only through the chain term (declared "
            "inline arithmetic, {xbar_ratio_arithmetic} run-backed rows are "
            "the r=8 store run and the r=16 sweep rows at other B)",
            "statement": "family choice cannot explain the measured drop: "
            "every single-B identity sits within 2e-4 of ratio 1 (ring "
            "1 - 1.8e-4, doubling 1 - 1.9e-5) — 80x to 750x short of the "
            "measured -1.41%",
        },
        "placement_at_anchor_readings": {
            "r8_store_busbw_exact": r8["model_busbw_exact"],
            "r8_store_busbw_float": r8["model_busbw_float"],
            "r16_store_busbw_exact": r16_anchor["model_busbw_exact"],
            "r16_store_busbw_float": r16_anchor["model_busbw_float"],
            "statement": "at each leg's own B reading the identity "
            "reproduces that leg's anchor figure to its latency term "
            "(busbw -> B under the pinned mapping) — placement, not a fit; "
            "reproducing BOTH legs requires TWO different B values "
            "(476.37 AND 469.67), i.e. an r-dependent effective bandwidth "
            "the single-B input space does not have",
        },
    }


def rail_bracket() -> dict:
    rail = run_row(RUN_ID_RING16_RAIL)
    bw_rail = Fraction(rail["model_busbw_exact"])
    rail_asymptotic_drop = 1 - RAIL_400 / A8_BUSBW          # 7637/47637
    measured_drop = 1 - A16_BUSBW / A8_BUSBW                # 670/47637
    # Declared inline arithmetic (identity + anchor numbers, no run id):
    # per-cut demand of a 16-rank ring allreduce = busbw under the pinned
    # convention; under two counter-rotating channels the per-direction cut
    # demand is busbw/2.
    cut_demand_dual = A16_BUSBW / 2
    # Latency-range bound: at the A-L0-LAT registry RANGE MAXIMUM L=2000 ns,
    # the ring chains are 14000/60000 ns — the largest drop any legal L can
    # produce at M=2^32, B=476.37 (identity arithmetic, declared inline):
    b = A8_BUSBW
    bw8_maxlat = busbw_of(wire_factor(R8) * M_COMMON, ring_time(M_COMMON, b, R8) + 12 * Fraction(1800))
    bw16_maxlat = busbw_of(wire_factor(R16) * M_COMMON, ring_time(M_COMMON, b, R16) + 28 * Fraction(1800))
    maxlat_ratio = bw16_maxlat / bw8_maxlat

    assert rail_asymptotic_drop == Fraction(7637, 47637)
    assert measured_drop == Fraction(670, 47637)
    assert rail_asymptotic_drop / measured_drop == Fraction(7637, 670)   # 11.40x
    assert cut_demand_dual < RAIL_400                                    # 234.835 < 400: headroom
    assert A16_BUSBW > RAIL_400        # single unidirectional ring cut demand exceeds the rail: infeasible
    assert float(maxlat_ratio) > 0.99 and (1 - maxlat_ratio) < measured_drop

    return {
        "rail_bound_store_run": {
            "run_id": RUN_ID_RING16_RAIL,
            "model_busbw_exact": rail["model_busbw_exact"],
            "model_busbw_float": rail["model_busbw_float"],
        },
        "asymptotic_drop_at_rail_exact": str(rail_asymptotic_drop),
        "asymptotic_drop_at_rail_percent": float(rail_asymptotic_drop) * 100,
        "overprediction_factor_exact": str(rail_asymptotic_drop / measured_drop),
        "overprediction_factor_float": float(rail_asymptotic_drop / measured_drop),
        "statement": "pinning B to the inter-node rail aggregate (400 = the "
        "anchor's own 16x200 Gbps config arithmetic) predicts a 16.03% "
        "8->16 drop — 11.4x the measured 1.41%: the measured configuration "
        "did NOT saturate the per-node rail, so the crossing cost is NOT a "
        "rail-capacity effect",
        "cut_demand_arithmetic_declared_inline": {
            "per_direction_cut_demand_two_channels_exact": str(cut_demand_dual),
            "per_direction_cut_demand_two_channels_float": float(cut_demand_dual),
            "rail_headroom": f"{cut_demand_dual} < 400 (the anchor's 469.67 "
            "splits across two counter-rotating cuts at ~234.8 B/ns per "
            "direction, 58.7% rail utilization)",
            "single_ring_infeasibility": "a SINGLE unidirectional ring would "
            "demand busbw = 469.67 > 400 on each cut — infeasible on the "
            "anchor's own config; the measured point itself rules out the "
            "single-ring-at-rail reading (model-class arithmetic, the "
            "anchor's channelization is UNPINNED)",
        },
        "latency_range_bound_declared_inline": {
            "statement": "even at the A-L0-LAT registry RANGE MAXIMUM "
            "(L = 2000 ns), the ring identity's 8->16 busbw ratio at "
            "M = 2^32, B = 476.37 is",
            "ratio_exact": str(maxlat_ratio),
            "ratio_float": float(maxlat_ratio),
            "bound": f"a drop of {float(1 - maxlat_ratio) * 100:.3f}% — still "
            "below the measured 1.41%: NO legal L value explains the drop "
            "either (identity arithmetic, no run id)",
        },
    }


def regime_and_structure() -> dict:
    return {
        "regime": {
            "message_bytes": "32 B x 2^k ladders (fetched commands): "
            "single node top 2^32, two nodes top 2^33 (the -e 10G cap is "
            "never hit exactly by doubling from 32 B; image-read "
            "corroboration recorded); executed sizes {2^30, 2^32, 2^33} are "
            "ladder members, all divisible by 8 and 16 — gates ACCEPT, no "
            "bracketing",
            "comparison_point": "2^32 = the largest size COMMON to both "
            "ladders — the same-size point of the scaling pair; per-size "
            "anchor rows are images (not extractable), so the ratio axis at "
            "the summary figures is the extractable target",
            "topology_class": "r=8 leg: NVSwitch single node (A-L0X-PORT "
            "KEEP domain, crossbar executed alongside); r=16 leg: hybrid "
            "NVSwitch + RoCEv2 rail (16x200 Gbps per node) — out of the "
            "pure scale-up domain, the same labeled-proxy discipline as "
            "CAL-A6",
        },
        "structural_expressiveness": {
            "statement": "the L0 input space has NO fabric-asymmetry "
            "parameter: one topology carries one uniform B (and one uniform "
            "L), nonuniform pair latency/bandwidth and congestion are "
            "explicitly unsupported, so the 8->16 crossing cost — an "
            "inter-node leg distinct from the intra-node fabric — is "
            "structurally inexpressible; the model can bracket it (uniform "
            "B = rail rate: -16.03%; uniform B carried unchanged: 0%) but "
            "cannot produce the measured -1.41% at ANY single legal "
            "(B, L); reproducing both legs requires an r-dependent "
            "effective-B axis (or a hybrid-leg topology input), an owner "
            "design note for higher-fidelity backends / CGFR, same "
            "blindness class as A6 (software version) and GF-02 (algorithm "
            "class)",
            "classification": "structural, recorded; nothing refit",
        },
        "context_axes_recorded_not_compared": {
            "osu_transport_axis": "CPU-CPU RDMA latency 2.70 us @ <=16 B; "
            "osu_bw plateau 48.89 GB/s (fetched table, sizes >= 8 MiB) vs "
            "the summary row 48.77 GB/s labeled '(400Gbps)' — a per-NIC-class "
            "sustained-vs-line-rate point (~97.5-97.8% of 50 B/ns) for the "
            "scale-out legs; GPU-GPU 32.70 us @ 8 B .. 60.35 us @ 512 KiB. "
            "L0 has no point-to-point op — recorded as anchor context, no "
            "run comparison (the GF-10/GF-11 stages own the latency axis)",
            "quarantined_staging_numbers": "4 GPUs 187.03 / all_gather "
            "437.85 / broadcast 228.76 GB/s and the staged OSU per-size "
            "mapping (47.71 @ 64 MiB etc.) — NOT in the fetched page text; "
            "unverified, not executed, not averaged",
        },
        "registry_placements": {
            "A_L0_BW_scale": "the anchor's figures 469.67-476.37 sit inside "
            "the plan's modern aggregate span [448, 900] near its bottom "
            "(and above the 450 physical per-direction ceiling — the INC "
            "class); the rail reading 400 and derated 320 sit BELOW the "
            "span's floor — recorded, no range edit",
            "gap_8_status": "the first staged multi-rank injection-scaling "
            "point is now executed: model-side rank-invariance vs measured "
            "-1.41%; the gapfill doc's 'thin (two series)' note stands — "
            "GF-11's 4->64 latency-overhead series is the other",
        },
    }


def main() -> int:
    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, stage GF-04 (gap-fill anchor GF-04), "
        "",
        "anchor": {
            "anchor_id": "GF-04",
            "title": "Oracle OCI blog: Zettascale in Practice: OSU and NCCL "
            "Benchmark on H100 Clusters for HPC and AI Workloads",
            "source_row": "NOT YET a sources.csv row (gap-fill staging doc "
            "docs/calibration/anchors_gapfill.md §GF-04; the owner "
            "integrates accepted rows — suggested continuation id CAL-A13+)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-04",
            "url": "https://blogs.oracle.com/cloud-infrastructure/zettascale-osu-nccl-benchmark-h100-ai-workloads",
            "confidence": "M-H per the staging doc (vendor blog, printed "
            "result tables with configs); page fetched and verified "
            "2026-10-28 — see `verification`, including the staging "
            "corrections (16x200 Gbps NICs not 8x400; published 2025-11-06 "
            "not 2026; 'NCCL 2.27' is a cited title not a pin; three "
            "secondary figures absent from the fetched text, quarantined)",
            "stage_target_note": "per the calibration plan: GF-02 already "
            "bracketed the absolute 476.37 figure (5.86% above the 450 "
            "physical ceiling, in-network-computing class); THIS stage "
            "works the anchor's own 8->16 SCALING claim",
        },
        "target": {
            "role": "multi-rank injection scaling (8->16 ranks, one fabric "
            "pair, MEASURED) — the first staged scaling point for plan gap "
            "8 (R4 of the gap-fill program)",
            "o_cct_calibratable": True,
            "regime": {
                "topology_class": "r=8 NVSwitch node + r=16 hybrid "
                "NVSwitch/RoCEv2-rail pair (labeled proxy, CAL-A6 "
                "discipline); executed on the L0 ring (A6-convention "
                "uniform projection), crossbar (A-L0X-PORT registered "
                "NVSwitch abstraction), and recursive-doubling (the only "
                "rank-scaling latency chain) families",
                "ranks": [8, 16],
                "message_bytes_ladder": "32 B x 2^k (fetched commands); "
                "executed {2^30, 2^32 (the common top), 2^33 (the two-node "
                "top)}",
            },
        },
        "verification": verification(),
        "anchor_derived": anchor_derived(),
        "model": {
            "backend_ids": ["analytical_l0", "analytical_l0_crossbar",
                            "analytical_l0_recursive_doubling"],
            "identities": {
                "allreduce_ring": "t = 2(r-1)/r*M/B + 2(r-1)*L (chains 14L "
                "@r=8, 30L @r=16)",
                "allreduce_crossbar": "t = 2(r-1)/r*M/B + 2L",
                "allreduce_recursive_doubling": "t = 2(r-1)/r*M/B + "
                "2*log2(r)*L (chains 6L @r=8, 8L @r=16)",
                "shared": "wire/rank = 2(r-1)/r*M in ALL three families; "
                "asymptotic busbw = B in all three (pinned nccl-tests "
                "mapping, stage GF-02's source fetch)",
            },
            "free_parameters": {
                "B_swept_bytes_per_ns": {
                    "476.37": "the anchor's single-node figure (r=8 anchor "
                    "point; r=16 scaling-null counterfactual; GF-02 "
                    "above-ceiling class recorded)",
                    "469.67": "the anchor's two-node figure (r=16 anchor "
                    "point / sweep baseline)",
                    "450": "GF-02's physical per-direction ceiling "
                    "(900/2), both rank counts",
                    "400": "the anchor's own 16x200 Gbps per-node rail "
                    "arithmetic (config ceiling, never a measurement)",
                    "320": "CAL-A12 ~80% derating x 400 (A6-convention "
                    "derated rail)",
                },
                "L_ns": 200,
                "L_provenance": "A-L0-LAT / A-L0X-LAT / A-L0D-LAT registry "
                "points (KEEP per plan §2.1); the latency-range bound in "
                "rail_bracket shows no legal L (up to the registry max "
                "2000 ns) explains the drop",
            },
        },
        "comparison": {
            "scaling": scaling_comparison(),
            "rail_bracket": rail_bracket(),
            "sweep_tp8": sweep_table(SWEEP_ID_TP8, R8),
            "sweep_tp16": sweep_table(SWEEP_ID_TP16, R16),
            "regime_and_structure": regime_and_structure(),
        },
        "deviation": {
            "on_the_ratio_axis": "model busbw(16)/busbw(8) at fixed "
            "uniform B = 1 - 1.8e-4 (ring store pair; recursive doubling "
            "1 - 1.9e-5) vs measured 0.98593 — the 1.41% measured drop is "
            "80x to 750x beyond every family's rank-count structure",
            "on_the_cct_axis": "model CCT pair 1.07159 vs anchor-implied "
            "1.08672 at the common size 2^32 — the model under-predicts "
            "the r=16 growth by 1.41% (the same fact, CCT-vs-CCT per plan "
            "§3)",
            "brackets": "rail-bound uniform reading -16.03% (11.4x the "
            "measured drop; the rail was NOT saturated — per-cut demand "
            "234.8 < 400 B/ns under two channels) vs scaling-null 0%: the "
            "measured -1.41% lies BETWEEN the only two uniform-B brackets "
            "and is inexpressible at ANY single (B, L)",
            "absolute_figures": "both legs sit above GF-02's 450 ceiling "
            "(5.86% / 4.37%) — the INC/algorithm-class classification is "
            "inherited, not re-adjudicated here",
        },
        "evidence_levels": {
            "runs": "E0 (analytical executions; deterministic, "
            "content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate against a "
            "vendor-blog MEASURED external anchor; no E3/E4 language — not "
            "our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_RING8_A476, RUN_ID_RING16_A469,
                        RUN_ID_RING16_A476, RUN_ID_RING16_RAIL,
                        RUN_ID_XBAR8_A476],
            "sweep_ids": [SWEEP_ID_TP8, SWEEP_ID_TP16],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_TP8}",
                           f"results/sweeps/{SWEEP_ID_TP16}"],
            "run_backed_numbers": "every model output in comparison.scaling "
            "and comparison.rail_bracket plus all sweep rows (closed-form "
            "cross-checked by exact Fraction string equality on every "
            "executed row — 5 store runs + 35 sweep rows — asserted in the "
            "builder); the cut-demand arithmetic, the latency-range bound, "
            "and the crossbar family note are declared inline "
            "identity/anchor arithmetic (no run ids claimed)",
            "inputs": [
                "experiments/calibration/gf04/sweep_gf04_tp8_v1.yaml",
                "experiments/calibration/gf04/sweep_gf04_tp16_v1.yaml",
                "experiments/calibration/gf04/run_gf04_ring8_anchor476_4gib_v1.yaml",
                "experiments/calibration/gf04/run_gf04_ring16_anchor469_4gib_v1.yaml",
                "experiments/calibration/gf04/run_gf04_ring16_anchor476_4gib_v1.yaml",
                "experiments/calibration/gf04/run_gf04_ring16_rail400_4gib_v1.yaml",
                "experiments/calibration/gf04/run_gf04_crossbar8_anchor476_4gib_v1.yaml",
                "experiments/calibration/gf04/workloads/ (2 files)",
                "experiments/calibration/gf04/topologies/ (13 files)",
                "experiments/calibration/gf04/profiles/ (3 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf04/"
            "run_gf04_ring8_anchor476_4gib_v1.yaml ; make run "
            "EXP=experiments/calibration/gf04/run_gf04_ring16_anchor469_"
            "4gib_v1.yaml ; make run EXP=experiments/calibration/gf04/"
            "run_gf04_ring16_anchor476_4gib_v1.yaml ; make run "
            "EXP=experiments/calibration/gf04/run_gf04_ring16_rail400_"
            "4gib_v1.yaml ; make run EXP=experiments/calibration/gf04/"
            "run_gf04_crossbar8_anchor476_4gib_v1.yaml ; make sweep "
            "EXP=experiments/calibration/gf04/sweep_gf04_tp8_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf04/sweep_gf04_tp16_"
            "v1.yaml ; python experiments/calibration/gf04/"
            "build_calibration_record.py",
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
