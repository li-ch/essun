"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-11
(calibration stage GF-11).

GF-11 = "Achieving Near Speed-of-Light Latency in GPU Collectives"
(arXiv:2607.16100; hardware microbenchmarks on GB200 NVL72 and 2/4-GPU
GB200 systems; software pins NCCL 2.29.1 / NVSHMEM 3.5.21 / MSCCL++ 0.8.0 /
vLLM 0.15.1). Stage role (gap-fill doc §GF-11, the LAST gap-fill anchor):
(a) small-message O-CCT on current-gen NVLink5 (plan gap 3) — the measured
4-GB200 bracket NCCL-ring 11.0 µs vs LLBuffer one-shot 2.37 µs, "which
bracket what any model may predict without accusing the fabric", executed
as the corpus's FIRST current-gen measured CCT-vs-CCT small-message
comparison; (b) measured current-gen latency components (plan gap 2): LL2
RTT 306 ns + remote store 792 ns close the anchor's own SoL equation
2*306+792 = 1404 EXACTLY, and the derived per-phase reading L = 702 maps
the decomposition onto the identity's 2L term — the FIRST current-gen
bare-hardware-anchored L in the corpus; (c) multi-rank latency-overhead
scaling (R4): 7%-at-2-GPU -> ~70%-at-64-GPU overhead growth vs the
identity family's 1x/6x/63x latency-chain growth over the same 32x rank
span. The §GF-06 material was neither used nor fetched by this stage (the
standing guard; the staging doc was opened only to read §GF-11).

Pure function of immutable artifacts: reads the four append-only store run
records and the four sweep tables produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_gapfill.md`` §GF-11
(numbers AS STAGED, not re-fetched), or (b) computed from the stored
run/sweep artifacts by this script, or (c) exact closed-form identity /
declared-arithmetic declared inline wherever used. Nothing is tuned:
every swept B/L value carries its anchor/registry provenance, and the
record measures where the model output sits relative to the anchor's
measured bracket (ratios and absolute deltas), never the reverse.

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
RUN_ID_SOL2 = "bc3d39c105a00421d1dd0dcfdb66170cd737443825a2eb72ad74dffff3b0f577"
RUN_ID_ONESHOT4 = "32ec17cf4b00e5d2aec30f5ac0650bca7e87e54e409e5e2dac249261d9c4b17a"
RUN_ID_REGISTRY4 = "be9c572e9ff7c256ba4308a2917d909ca7e8fd15d53d14116bacf0d903ab174d"
RUN_ID_MCAST64 = "dca6a315a550929631a14232aa43dd0b8f40808762b6f367457d735e6b50c47d"
SWEEP_ID_TP2 = "c63851f78c03c90566b8c2148173ec66157051b0c528f3a8c0eab8f8591fee68"
SWEEP_ID_TP4 = "69881b98f9eb1915c5002a8645915f45e2e0e2a9f766c6eb791f5e8ce7d0ad8f"
SWEEP_ID_TP64 = "f8b3b57533fcb4830af5a1f97fb353699569c07dbfe69fd1509d2755eae8544c"
SWEEP_ID_LAT = "af14c4df1dcb0063982876f40f4d6c79277f519489ff1426518da8b4c5c965e7"

RESULTS = REPO_ROOT / "results"

# Anchor GF-11 staged numbers (docs/calibration/anchors_gapfill.md §GF-11;
# confidence H — extracted from HTML, hardware measurements; author-run
# microbenchmarks, preprint; numbers AS STAGED, not re-fetched).
# Latency components — MEASURED on 2 GB200 GPUs (bare hardware, µs -> ns).
L_LL2_RTT_NS = Fraction(306)          # LL2 round-trip time "0.306 µs"
L_REMOTE_STORE_NS = Fraction(792)     # remote store "0.792 µs"
L_SOL_NS = Fraction(1404)             # speed-of-light AllReduce bound "1.404 µs" = 2*306 + 792 (the anchor's own equation)
L_DERIVED_NS = Fraction(702)          # the per-phase identity reading: L_SoL/2 (DECLARED mapping; alternative L=1404 executed as its own row)
BARRIER_LB_NS = Fraction(1000)        # "each barrier will incur more than 1 µs of overhead" — a STRICT LOWER BOUND
# Small-message bracket — MEASURED on 4 GB200s (full software stack).
T_NCCL_RING_4_NS = Fraction(11000)    # "11.0 µs for NCCL ring" (NCCL 2.29.1)
T_ONESHOT_4_NS = Fraction(2370)       # "2.37 µs" (the LLBuffer one-shot kernel)
# Overhead growth — PROSE ("about", "roughly").
OVERHEAD_2GPU = Fraction(7, 100)      # "only about 7% overhead over the SoL bound at 2 GPUs"
OVERHEAD_64GPU = Fraction(7, 10)      # "within roughly 70% overhead" at 64 GPUs
T_ONESHOT_2GPU_DERIVED_NS = Fraction(37557, 25)   # 1.07 * 1404 — derived from the prose 7% ("about")
# System descriptors (recorded, NOT executed — see recorded_ambiguities).
AGG_B_NS = Fraction(130000)           # GB200 NVL72 "130 TB/s aggregate" (2 s.f.; direction split unstated)
NVL72_RANKS = 72

# Registry / cross-anchor reference values (registry and integrated-anchor
# provenance, never GF anchors).
B_REGISTRY = Fraction(64)             # A-L0X-BW / A-L0-BW / A-L0D-BW registry point (executed everywhere)
L_REGISTRY = Fraction(200)            # A-L0X-LAT registry point
L_A10_ASSUMED = Fraction(800)         # CAL-A10 assumption-class 0.8 µs (integrated sources.csv row)
L_RANGE = (Fraction(10), Fraction(2000))   # A-L0X-LAT declared free range
B_RANGE_UPPER = Fraction(1024)        # A-L0X-BW declared free-range upper
# Cross-anchor ties (other stages' recorded values, quoted for coincidences only).
GF01_EAGER_16KIB_NS = Fraction(13540)   # GF-01 MI300X eager 16 KiB row
GF01_EAGER_8B_NS = Fraction(16610)      # GF-01 MI300X eager 8 B row
GF10_APP_P2P_NS = Fraction(9000)        # GF-10 V100-era app-level NVLink direct-pair P2P
GF03_B300_THEO = Fraction(900)          # GF-03 B300 NCCL allreduce "93% of theoretical" with theoretical ~900 GB/s

RANKS = (2, 4, 64)                    # the anchor's three staged rank counts (decomposition / bracket / scaling)
RUN_PAYLOAD = 128                     # the anchor's "128-B cache-line FP32" granularity — the DECLARED size reading
CROSSOVER_ONESHOT_B = 41216           # (2370 - 1404)*64/(3/2) — the exact payload where the crossbar identity at L=702, B=64 crosses the near-optimal leg (executed as a cell)
GRID = [128, 512, 2048, 8192, 32768, 41216, 65536]   # 7-size grid: 128-B reading -> plan small-message boundary, incl. the crossover

# topology_id -> (L, role label) for the latency-component sweep (r=4, B=64).
LAT_ROWS = [
    ("crossbar4_gf11_b64_l200_v1", L_REGISTRY, "A-L0X-LAT registry point (the placement reference)"),
    ("crossbar4_gf11_b64_l306_v1", L_LL2_RTT_NS, "the anchor's MEASURED LL2 RTT component (0.306 µs on 2 GB200s) — the first measured current-gen sub-µs component on the corpus L axis"),
    ("crossbar4_gf11_b64_l702_v1", L_DERIVED_NS, "the DERIVED per-phase reading of the measured SoL (1404/2 — the anchor's own equation closes exactly) — the headline mapping row"),
    ("crossbar4_gf11_b64_l792_v1", L_REMOTE_STORE_NS, "the anchor's MEASURED remote-store component (0.792 µs — the dominant term, 44/17 above the LL2 RTT)"),
    ("crossbar4_gf11_b64_l800_v1", L_A10_ASSUMED, "CAL-A10's assumption-class 0.8 µs check row — the assumption sits only 400/351 above the current-gen derived reading"),
    ("crossbar4_gf11_b64_l1404_v1", L_SOL_NS, "the SoL-total ALTERNATIVE reading (the whole 2-GPU bound as ONE phase's L) — the x2-class mapping ambiguity, both readings executed"),
]


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def t_ring(m: int, b: Fraction, ranks: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2(r-1)*L  (src/essun/backends/analytical/l0.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * (ranks - 1) * l


def t_rd(m: int, b: Fraction, ranks: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2*log2(r)*L  (src/essun/backends/analytical/
    l0_recursive_doubling.py; ranks a power of two)."""
    steps = ranks.bit_length() - 1
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * steps * l


def crossover_xbar_vs(target: Fraction, l: Fraction, b: Fraction, ranks: int) -> Fraction:
    """Payload M* where the crossbar identity at (l, b, ranks) crosses
    `target`: 2(r-1)/r*M*/B = target - 2L  =>  M* = (target - 2L)*B*r/(2(r-1))."""
    return (target - 2 * l) * b * ranks / (2 * (ranks - 1))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    model = obs["model"]
    l_val = Fraction(model["pair_latency_ns_exact"])
    return {
        "run_id": run_id,
        "mapping": mapping,
        "experiment_id": run["manifest"]["experiment_id"],
        "manifest_path": run["manifest_path"],
        "model_params": {
            "ranks": model["ranks"],
            "backend_id": obs["backend_id"],
            "transport_model": model["transport_model"],
            "injection_bytes_per_ns_exact": model["injection_bytes_per_ns_exact"],
            "pair_latency_ns_exact": model["pair_latency_ns_exact"],
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": float(per_op["completion_time_ns"]),
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "latency_term_ns_exact": str(2 * l_val),
        "latency_fraction_of_cct_exact": str(2 * l_val / cct),
        "latency_fraction_of_cct_float": float(2 * l_val / cct),
    }


def _by_cell(sweep_id: str) -> dict[tuple[str, int], Fraction]:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    return {
        (row["config_id"].split("-")[2], row["payload_bytes"]): Fraction(
            row["o_cct"]["completion_time_ns_mean_exact"]
        )
        for row in table["configs"]
    }


def sweep_rows(sweep_id: str, name_key: str) -> dict:
    by = _by_cell(sweep_id)
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    sizes = sorted({m for (_t, m) in by})
    ladder = []
    for m in sizes:
        rows = []
        for (topo, mm), cct in sorted(by.items()):
            if mm != m:
                continue
            rows.append(
                {
                    "topology_id": topo,
                    "cct_ns_exact": str(cct),
                    "cct_ns_float": float(cct),
                }
            )
        ladder.append({"payload_bytes": m, "rows": rows})
    return {
        "sweep_id": sweep_id,
        "sweep_name": table["sweep"],
        "manifest_path": table["manifest_path"],
        name_key: ladder,
    }


def _wire_check(sweep_id: str, ranks: int) -> None:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    wire_ok = all(
        row["per_rank_wire_bytes_exact"] == str(Fraction(2 * (ranks - 1) * row["payload_bytes"], ranks))
        for row in table["configs"]
    )
    assert wire_ok, f"wire conservation failed in {sweep_id}"


def anchor_derived() -> dict:
    # Self-checks: the staged numbers must produce these exact values.
    # The anchor's own SoL equation closes EXACTLY (contrast GF-10's
    # bisection equation, which carried an internal x2).
    assert 2 * L_LL2_RTT_NS + L_REMOTE_STORE_NS == L_SOL_NS      # 612 + 792 = 1404
    assert L_DERIVED_NS * 2 == L_SOL_NS                          # the per-phase reading 702
    assert L_REMOTE_STORE_NS / L_LL2_RTT_NS == Fraction(44, 17)  # the dominant component
    # The bracket and its ratios.
    assert T_NCCL_RING_4_NS / T_ONESHOT_4_NS == Fraction(1100, 237)          # ~4.6414 — the implementation-choice span
    assert T_ONESHOT_4_NS / L_SOL_NS == Fraction(395, 234)                   # ~1.6880 under the constant-SoL reading
    assert T_ONESHOT_4_NS / L_SOL_NS - 1 == Fraction(161, 234)               # ~68.8% derived overhead at r=4
    assert T_NCCL_RING_4_NS / L_SOL_NS == Fraction(2750, 351)                # ~7.8347 — stock stack over SoL
    # The prose-derived 2-GPU point and the barrier bound.
    assert (1 + OVERHEAD_2GPU) * L_SOL_NS == T_ONESHOT_2GPU_DERIVED_NS       # 1.07 * 1404 = 37557/25 = 1502.28
    assert T_ONESHOT_2GPU_DERIVED_NS - L_SOL_NS == Fraction(2457, 25)        # 98.28 ns of derived kernel overhead at r=2
    assert T_ONESHOT_2GPU_DERIVED_NS - L_SOL_NS < BARRIER_LB_NS              # the kernel's whole derived overhead is BELOW one barrier
    assert BARRIER_LB_NS / L_SOL_NS == Fraction(250, 351)                    # ~71.2% of the SoL — the barrier lower bound's share
    # Registry / CAL-A10 / range placements — ALL measured/derived GF-11
    # latency values sit INSIDE the declared range (the first such anchor).
    for v in (L_LL2_RTT_NS, L_DERIVED_NS, L_REMOTE_STORE_NS, L_A10_ASSUMED, L_SOL_NS):
        assert L_RANGE[0] <= v <= L_RANGE[1]
    assert L_DERIVED_NS / L_REGISTRY == Fraction(351, 100)                   # 3.51x the registry point
    assert L_LL2_RTT_NS / L_REGISTRY == Fraction(153, 100)
    assert L_A10_ASSUMED / L_DERIVED_NS == Fraction(400, 351)                # the assumption is only ~1.14x above the derived reading
    assert L_DERIVED_NS / L_RANGE[1] == Fraction(351, 1000)
    assert L_SOL_NS / L_RANGE[1] == Fraction(351, 500)
    # Rank-scaling arithmetic (prose figures, exact ratios).
    assert 64 // 2 == 32                                                     # the anchor's rank span
    assert OVERHEAD_64GPU / OVERHEAD_2GPU == 10                              # the prose overhead-fraction growth, exactly 10x
    assert (1 + OVERHEAD_64GPU) / (1 + OVERHEAD_2GPU) == Fraction(170, 107)  # ~1.5888 total-time growth, constant-SoL reading
    assert (1 + OVERHEAD_64GPU) * L_SOL_NS == Fraction(11934, 5)             # ~2386.8 ns derived envelope at r=64
    # Chain growth factors over r=2 -> 64: ring 63x, doubling 6x, crossbar 1x.
    assert 2 * (64 - 1) // (2 * (2 - 1)) == 63
    assert 12 // 2 == 6
    # Crossover arithmetic (the executed cell).
    assert crossover_xbar_vs(T_ONESHOT_4_NS, L_DERIVED_NS, B_REGISTRY, 4) == CROSSOVER_ONESHOT_B   # 41216
    assert CROSSOVER_ONESHOT_B == 161 * 256 and CROSSOVER_ONESHOT_B % 64 == 0                     # 161/256 of the 64 KiB boundary; a legal r=64 cell
    assert crossover_xbar_vs(T_NCCL_RING_4_NS, L_DERIVED_NS, B_REGISTRY, 4) == Fraction(1228288, 3)   # ~409429 B — NOT an integer, recorded not executed
    # B-axis system-descriptor arithmetic (recorded NOT executed).
    assert AGG_B_NS / NVL72_RANKS == Fraction(16250, 9)                      # ~1805.56 per-GPU aggregate-class
    assert AGG_B_NS / NVL72_RANKS / 2 == Fraction(8125, 9)                   # ~902.78 per-direction-class
    assert (AGG_B_NS / NVL72_RANKS / 2) / B_RANGE_UPPER == Fraction(8125, 9216)   # ~88.2% of the declared range upper — inside
    assert (AGG_B_NS / NVL72_RANKS) / B_RANGE_UPPER == Fraction(8125, 4608)       # ~1.763 — the aggregate reading sits above
    # Grid sanity.
    assert GRID[0] == RUN_PAYLOAD == 128 and GRID[-1] == 65536 and len(GRID) == 7
    assert all(m % r == 0 for m in GRID for r in RANKS)                      # every size legal at every anchor rank
    assert GRID.index(CROSSOVER_ONESHOT_B) == 5 and GRID[4] < CROSSOVER_ONESHOT_B < GRID[6]
    # Cross-anchor coincidences (recorded, never cross-derived).
    assert GF10_APP_P2P_NS / L_DERIVED_NS == Fraction(500, 39)               # ~12.82 — app-level 2018 vs bare-derived 2026
    assert GF01_EAGER_16KIB_NS / T_ONESHOT_4_NS == Fraction(1354, 237)       # ~5.71 — MI300X 16 KiB vs GB200 one-shot
    assert GF01_EAGER_8B_NS / T_NCCL_RING_4_NS == Fraction(151, 100)         # exactly 151/100 — the stock-NCCL small-message floor across two generations
    assert GF03_B300_THEO / (AGG_B_NS / NVL72_RANKS / 2) == Fraction(324, 325)   # ~0.9969 — two independent NVLink5-class per-direction readings within 0.3%
    return {
        "staged_numbers": {
            "system": "hardware microbenchmarks on GB200 NVL72 (72 GPUs, 130 TB/s aggregate) and 2/4-GPU GB200 systems; Alps GH200 nodes as a second system; software pins NCCL 2.29.1, NVSHMEM 3.5.21, MSCCL++ 0.8.0, vLLM 0.15.1; 128-B cache-line FP32 (arXiv:2607.16100)",
            "headline": "on 2 GB200 GPUs: LL2_RTT 0.306 µs and remote-store 0.792 µs measured, speed-of-light AllReduce bound L_SoL = 2*L_LL2_RTT + L_remote_store = 1.404 µs; 'each barrier will incur more than 1 µs of overhead'; small-message AllReduce on 4 GB200s 'from 11.0 µs for NCCL ring to 2.37 µs' (LLBuffer one-shot); kernels 'only about 7% overhead over the SoL bound at 2 GPUs'; 'Even at 64 GPUs, multicast one-shot variants stay within roughly 70% overhead of the SoL bound'; vLLM ITL reduced 7-13% (4 GPUs) / 9-11% (8 GPUs); 'each µs removed from AllReduce latency reduces cost by about 0.9%'",
            "provenance_class": "H confidence — MEASURED hardware microbenchmarks extracted from the paper HTML; author-run, preprint; the per-size latency table lives in a FIGURE (not enumerated in text) — the 128-B size reading of the bracket is a DECLARED ambiguity; the 2-GPU components are bare hardware while the 4-GPU bracket rows are full-stack collective times (mixed quantity classes, declared per row); numbers AS STAGED, not re-fetched",
        },
        "derived_arithmetic": {
            "sol_equation_closes": "the anchor's own decomposition equation closes EXACTLY: 2 x 306 + 792 = 1404 — the first gap-fill anchor whose staged latency equation reconciles to the byte (contrast GF-10's bisection equation, whose quoted operands multiplied to exactly half the stated result)",
            "identity_mapping": "the crossbar identity charges its latency as 2L (one L per phase), so equating the identity's latency term with the measured SoL gives the per-phase reading L = 1404/2 = 702 ns — the DECLARED mapping of the measured decomposition onto the free parameter; the ALTERNATIVE reading (the whole SoL as one phase's L, 1404) is executed as its own sweep row; neither adjudicated",
            "component_structure": "remote store / LL2 RTT = exactly 44/17 (~2.59) — the remote store is the dominant component; both components and the derived reading sit INSIDE the A-L0X-LAT declared free range [10, 2000] (702 at 351/1000 of the upper, 1404 at 351/500) — the FIRST gap-fill anchor with NO above-range latency placement (GF-10's app-level values sat 2.5x-13.5x above)",
            "cal_a10_check": "CAL-A10's assumption-class 800 ns sits only 400/351 (~1.14) above the derived current-gen 702 — vs GF-10's app-level check at exactly 45/4 = 11.25: the assumption survives the BARE-HARDWARE comparison within 14% while being an order below the app-level measurement — a quantity-class contrast (coincidence recorded, never cross-derived; 800 was never derived from any decomposition)",
            "bracket_ratios": "NCCL-ring / one-shot on the same 4-GB200 fabric = exactly 1100/237 (~4.64) — the implementation-choice span; one-shot / SoL = exactly 395/234 (~1.688), i.e. a derived 161/234 (~68.8%) overhead at r=4 under the constant-SoL reading — numerically the 'roughly 70%' the paper quotes at r=64; NCCL-ring / SoL = exactly 2750/351 (~7.83)",
            "prose_derived_points": "the 'about 7%' at 2 GPUs gives 37557/25 = 1502.28 ns, i.e. derived kernel overhead 2457/25 = 98.28 ns at r=2 — BELOW the '> 1 µs' barrier lower bound by more than 10x: the one-shot kernel's entire derived overhead is smaller than ONE barrier, the anchor's own motivation for barrier-free designs (both figures prose-class; the barrier is a strict lower bound at >= 250/351 ~ 71.2% of the whole SoL)",
            "rank_scaling": "overhead fraction 7% -> 70% is a growth of exactly 10x across a rank growth of exactly 32x (2 -> 64); under the constant-SoL reading the total-time growth is (1.7/1.07) = exactly 170/107 (~1.59) and the derived r=64 envelope is 11934/5 = 2386.8 ns; the identity family's latency-chain growth over the same span is exactly 63x (ring), 6x (doubling), 1x (crossbar) — no chain matches the measured growth",
            "crossover_arithmetic": "the crossbar identity at (L=702, B=64, r=4) crosses the anchor's near-optimal leg at exactly M* = 41216 B = 161 x 256 (161/256 of the plan's 64 KiB small-message boundary; divisible by 64, so it is a legal cell at every anchor rank and is EXECUTED); the NCCL-leg crossover is 1228288/3 (~409429 B, not an integer — recorded not executed); under the B=8125/9 per-direction system-descriptor reading the near-optimal crossover moves to 644 x 8125/9 = 5232500/9 (~581389 B), OUTSIDE the small-message regime entirely — the bracket verdict is B-sensitive only through this formula",
            "b_axis_recorded_not_executed": "the NVL72 system descriptor '130 TB/s aggregate' over 72 GPUs gives 16250/9 (~1805.6) B/ns per-GPU aggregate-class or 8125/9 (~902.8) per-direction-class — the direction split is UNSTATED and 130 is 2 significant figures, so no row is executed; the per-direction reading sits at 8125/9216 (~88.2%) of the declared B free-range upper 1024 (inside), the aggregate reading above it (8125/4608 ~ 1.76x); the Alps '150 GB/s NVLink' inter-node figure is a second system with no staged collective series — recorded, not executed",
            "cross_anchor_coincidences_arithmetic": "GF-10's app-level 9000 / derived 702 = exactly 500/39 (~12.8); GF-01's MI300X 16-KiB eager 13540 / one-shot 2370 = exactly 1354/237 (~5.7); GF-01's 8-B eager 16610 / NCCL ring 11000 = exactly 151/100 — the stock-NCCL small-message floor is stable within 1.51x across two GPU generations and fabric classes; GF-03's B300 '900 GB/s theoretical' / the 8125/9 per-direction reading = exactly 324/325 (~0.997) — two independent NVLink5-class per-direction readings within 0.3% (all coincidences recorded, never cross-derived)",
        },
    }


def run_point_placements() -> dict:
    # Exact-value self-checks on the executed run quartet (transcription guards).
    obs = {k: load_json(RESULTS / rid / "observations.json") for k, rid in
           (("sol2", RUN_ID_SOL2), ("oneshot4", RUN_ID_ONESHOT4),
            ("reg4", RUN_ID_REGISTRY4), ("mcast64", RUN_ID_MCAST64))}
    t_sol2 = Fraction(obs["sol2"]["per_op"][0]["completion_time_ns_exact"])
    t_one4 = Fraction(obs["oneshot4"]["per_op"][0]["completion_time_ns_exact"])
    t_reg4 = Fraction(obs["reg4"]["per_op"][0]["completion_time_ns_exact"])
    t_m64 = Fraction(obs["mcast64"]["per_op"][0]["completion_time_ns_exact"])
    assert t_sol2 == t_xbar(RUN_PAYLOAD, B_REGISTRY, 2, L_DERIVED_NS) == 1406
    assert t_sol2 == L_SOL_NS + Fraction(RUN_PAYLOAD, 64)               # SoL + EXACTLY M/B: the mapping residual is the wire term
    assert t_one4 == t_xbar(RUN_PAYLOAD, B_REGISTRY, 4, L_DERIVED_NS) == 1407
    assert t_reg4 == t_xbar(RUN_PAYLOAD, B_REGISTRY, 4, L_REGISTRY) == 403
    assert t_m64 == t_xbar(RUN_PAYLOAD, B_REGISTRY, 64, L_DERIVED_NS) == Fraction(22527, 16)
    assert T_ONESHOT_4_NS / t_one4 == Fraction(790, 469)                # the near-optimal leg sits 790/469 above the model floor
    assert T_NCCL_RING_4_NS / t_one4 == Fraction(11000, 1407)
    assert t_one4 / t_reg4 == Fraction(1407, 403)                       # the L axis alone at the shared point
    assert T_ONESHOT_4_NS / t_reg4 == Fraction(2370, 403)               # the registry defaults under-predict the near-optimal leg ~5.88x
    assert 2 * L_DERIVED_NS / t_one4 == Fraction(468, 469)              # the model floor is 468/469 (~99.8%) latency term at the 128-B reading
    assert t_m64 - t_sol2 == Fraction(63, 16) - Fraction(128, 64)       # rank growth moves the identity ONLY through the wire coefficient
    envelope64 = (1 + OVERHEAD_64GPU) * L_SOL_NS
    assert t_m64 < envelope64 < t_rd(RUN_PAYLOAD, B_REGISTRY, 64, L_DERIVED_NS)
    return {
        "sol2_point": {
            "cct_ns_exact": str(t_sol2),
            "vs_measured_sol": "the identity reproduces the anchor's MEASURED 2-GPU SoL 1404 ns to within exactly M/B = 2 ns (t = 1406): the residual of the SoL-to-L mapping IS the wire term, by construction — demonstrated on a stored run at the algorithm-free rank (all three L0 chains coincide at r=2)",
        },
        "oneshot4_point": {
            "cct_ns_exact": str(t_one4),
            "vs_near_optimal_leg": "2370/1407 = exactly 790/469 (~1.684): the model floor sits 40.6% BELOW the anchor's near-optimal measured leg — the bare-hardware floor the custom kernel approaches from above; the gap is kernel/sync/software, not fabric ('without accusing the fabric' holds)",
            "vs_nccl_leg": "11000/1407 (~7.82): the stock leg sits ~7.8x above the same floor (2750/351 over the SoL)",
            "latency_fraction": "2L/t = exactly 468/469 (~99.8%) at the 128-B reading — the small-message identity is essentially pure latency term",
        },
        "registry4_twin": {
            "cct_ns_exact": str(t_reg4),
            "vs_anchor_point": "1407/403 = exactly 1407/403 (~3.491): the L axis alone (702/200 = 351/100) moves the CCT 3.49x at the shared rank/payload",
            "vs_measurement": "2370/403 (~5.88): the free registry defaults UNDER-PREDICT the anchor's near-optimal small-message leg by ~5.9x at the declared size reading — a placement fact about the free parameter, never a tuning target",
        },
        "multicast64_point": {
            "cct_ns_exact": str(t_m64),
            "vs_envelope": "the derived r=64 envelope 11934/5 = 2386.8 ns (1.7 x the constant-SoL reading) sits ABOVE the identity's 22527/16 = 1407.9375 ns (consistent — the envelope is a bound) and BELOW the doubling chain at the same point: the measured scaling point lands between the two shortest chains, the same two-sided bracket as the r=4 near-optimal leg",
            "rank_flatness": "t(64) - t(2) = exactly 63/16 - 2 ns: over the anchor's 32x rank span the identity moves ONLY through the wire coefficient (3.9375 vs 2 ns at M=128) — the measured 7% -> 70% overhead growth is rank-dependent kernel/multicast overhead the rank-flat identity cannot express",
        },
    }


def identity_coincidence_tp2() -> dict:
    by = _by_cell(SWEEP_ID_TP2)
    # All 21 cells: every algorithm reproduces the SAME closed form at r=2.
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, B_REGISTRY, 2, L_DERIVED_NS)), (tid, m)
        assert str(cct) == str(t_ring(m, B_REGISTRY, 2, L_DERIVED_NS)), (tid, m)
        assert str(cct) == str(t_rd(m, B_REGISTRY, 2, L_DERIVED_NS)), (tid, m)
        checked += 1
    assert checked == 21
    _wire_check(SWEEP_ID_TP2, 2)
    # The executed coincidence: the three topologies' cells agree exactly.
    by_size = {}
    for (tid, m), cct in by.items():
        by_size.setdefault(m, set()).add(str(cct))
    assert all(len(v) == 1 for v in by_size.values())
    # The 41216 member reads exactly 2048 ns at r=2 (644 + 1404).
    assert by[("crossbar2_gf11_b64_l702_v1", CROSSOVER_ONESHOT_B)] == 2048
    assert Fraction(CROSSOVER_ONESHOT_B, 64) + L_SOL_NS == 2048
    return {
        "claim": "at the anchor's DECOMPOSITION rank r=2 all three corpus L0 identities coincide (ring 2(r-1)L = doubling 2*log2(2)L = crossbar 2L = 2L): all 21 executed cells are bit-identical across the three algorithms and reproduce the closed form t = M/64 + 1404 by exact Fraction string equality — algorithm choice vanishes exactly where the anchor measured its algorithm-free speed-of-light bound",
        "rows_cross_checked": checked,
        "closed_form": "t = M/B + 2L = M/64 + 1404 at r=2, B=64, L=702 (the derived reading)",
        "crossover_member_note": f"the {CROSSOVER_ONESHOT_B} B grid member reads exactly 2048 ns at r=2 (644 wire + 1404) — an arithmetic coincidence of the executed grid, recorded not interpreted",
    }


def bracket_mapping_tp4() -> dict:
    by = _by_cell(SWEEP_ID_TP4)
    forms = {
        "ring4_gf11_b64_l702_v1": t_ring,
        "crossbar4_gf11_b64_l702_v1": t_xbar,
        "exchange4_gf11_b64_l702_v1": t_rd,
    }
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(forms[tid](m, B_REGISTRY, 4, L_DERIVED_NS)), (tid, m)
        checked += 1
    assert checked == 21
    _wire_check(SWEEP_ID_TP4, 4)
    # The three chains at the 128-B reading vs the measured pair.
    t_ring_128 = by[("ring4_gf11_b64_l702_v1", 128)]
    t_rd_128 = by[("exchange4_gf11_b64_l702_v1", 128)]
    t_xbar_128 = by[("crossbar4_gf11_b64_l702_v1", 128)]
    assert (t_ring_128, t_rd_128, t_xbar_128) == (4215, 2811, 1407)
    assert t_xbar_128 < T_ONESHOT_4_NS < t_rd_128                 # the near-optimal leg sits BETWEEN the two shortest chains
    assert T_ONESHOT_4_NS / t_xbar_128 == Fraction(790, 469)
    assert t_rd_128 / T_ONESHOT_4_NS == Fraction(937, 790)
    assert t_ring_128 / T_ONESHOT_4_NS == Fraction(281, 158)
    assert T_NCCL_RING_4_NS / t_ring_128 == Fraction(2200, 843)   # the NCCL leg sits 2.61x above its own identity
    # The measured implementation gap EXCEEDS the family's full chain ratio.
    for m in GRID:
        ratio = by[("ring4_gf11_b64_l702_v1", m)] / by[("crossbar4_gf11_b64_l702_v1", m)]
        assert ratio < 3                                           # chain ratio asymptote 6L/2L = 3, from below
        assert Fraction(1100, 237) > 3 > ratio                     # the measured gap exceeds every chain ratio
    # The executed crossover cell.
    assert by[("crossbar4_gf11_b64_l702_v1", CROSSOVER_ONESHOT_B)] == 2370 == T_ONESHOT_4_NS
    return {
        "claim": "the three single-port L0 identities at the SAME (B=64, L=702) bracket the anchor's measured pair: all 21 cells reproduce their closed forms by exact Fraction string equality; the near-optimal leg (2370 ns) lands BETWEEN the crossbar (1407) and doubling (2811) chains — the bare identity family brackets it, no single identity reaches it; the NCCL leg (11000 ns) sits 2200/843 (~2.61x) above its own ring identity (4215)",
        "rows_cross_checked": checked,
        "closed_forms": "ring t = 3M/128 + 4212 (6L); doubling t = 3M/128 + 2808 (4L); crossbar t = 3M/128 + 1404 (2L) — same wire term, chains only",
        "chain_positions_at_128b": {
            "crossbar_vs_near_optimal_exact": "790/469 (model below measurement — the bare floor)",
            "doubling_vs_near_optimal_exact": "937/790 (model above measurement — the first chain to overshoot)",
            "ring_vs_near_optimal_exact": "281/158 (~1.78)",
            "nccl_vs_ring_identity_exact": "2200/843 (~2.61) — the stock stack over its own identity",
            "measured_gap_vs_chain_span": "the measured ring/one-shot ratio 1100/237 (~4.64) EXCEEDS the family's full chain ratio 6L/2L = 3 at r=4 (verified below 3 at every payload): the implementation gap is not spannable by chain choice alone — the extra ~1.55x is kernel/sync/software, inexpressible in the shared-(B, L) identity family",
        },
        "executed_crossover_cell": {
            "payload_bytes": CROSSOVER_ONESHOT_B,
            "cct_ns_exact": "2370",
            "statement": "at M = 41216 B the crossbar identity at (L=702, B=64, r=4) equals the anchor's near-optimal leg EXACTLY (966 wire + 1404 = 2370): if the anchor's true message size were at or above 161/256 of the plan's 64 KiB small-message boundary, the model would sit AT/ABOVE the near-optimal leg; below it, the model is a strict lower bound — the size-reading sensitivity of the bracket verdict, executed",
        },
    }


def rank_scaling_tp64() -> dict:
    by64 = _by_cell(SWEEP_ID_TP64)
    by2 = _by_cell(SWEEP_ID_TP2)
    forms = {
        "ring64_gf11_b64_l702_v1": t_ring,
        "crossbar64_gf11_b64_l702_v1": t_xbar,
        "exchange64_gf11_b64_l702_v1": t_rd,
    }
    checked = 0
    for (tid, m), cct in by64.items():
        assert str(cct) == str(forms[tid](m, B_REGISTRY, 64, L_DERIVED_NS)), (tid, m)
        checked += 1
    assert checked == 21
    _wire_check(SWEEP_ID_TP64, 64)
    # Chain constants and growth factors over the anchor's 32x rank span.
    assert 2 * (64 - 1) * L_DERIVED_NS == 88452                    # ring chain 126L
    assert 2 * 6 * L_DERIVED_NS == 8424                            # doubling chain 12L
    t_x64 = by64[("crossbar64_gf11_b64_l702_v1", 128)]
    t_r64 = by64[("ring64_gf11_b64_l702_v1", 128)]
    t_d64 = by64[("exchange64_gf11_b64_l702_v1", 128)]
    t_x2 = by2[("crossbar2_gf11_b64_l702_v1", 128)]
    t_r2 = by2[("ring2_gf11_b64_l702_v1", 128)]
    t_d2 = by2[("exchange2_gf11_b64_l702_v1", 128)]
    assert t_x64 == Fraction(22527, 16) and t_r64 == Fraction(1415295, 16) and t_d64 == Fraction(134847, 16)
    assert (t_x64 / t_x2, t_d64 / t_d2, t_r64 / t_r2) == (Fraction(22527, 16 * 1406), Fraction(134847, 16 * 1406), Fraction(1415295, 16 * 1406))
    # The envelope sits between crossbar and doubling at the 128-B reading.
    envelope64 = (1 + OVERHEAD_64GPU) * L_SOL_NS
    assert t_x64 < envelope64 < t_d64
    # The measured growth (constant-SoL reading) vs the chains.
    growth_measured = Fraction(170, 107)
    assert t_x64 / t_x2 < growth_measured < t_d64 / t_d2          # crossbar too flat, doubling too steep, ring far steeper
    return {
        "claim": "the identity family's latency-chain growth over the anchor's 32x rank span (r=2 -> 64) is exactly 63x (ring 126L vs 2L), 6x (doubling 12L vs 2L), and 1x (crossbar, rank-flat BY CONSTRUCTION) — all 21 r=64 cells reproduce their closed forms exactly; the measured datum (overhead fraction 7% -> ~70%, a 170/107 ~ 1.59 total-time growth under the constant-SoL reading) sits BETWEEN the crossbar's flatness and the doubling's 6x: no L0 chain matches the measured growth, and the derived r=64 envelope (2386.8 ns) lands between the crossbar and doubling chains at the 128-B reading — the same two-sided bracket as the r=4 near-optimal leg",
        "rows_cross_checked": checked,
        "closed_forms": "ring t = 63M/2048 + 88452 (126L); doubling t = 63M/2048 + 8424 (12L); crossbar t = 63M/2048 + 1404 (2L)",
        "chain_growth_factors_exact": {"ring": "63", "doubling": "6", "crossbar": "1 (rank-flat)"},
        "measured_growth_constant_sol_reading": "170/107 (~1.59, from the prose 7%/70% figures; the SoL's rank-dependence is NOT staged — see recorded_ambiguities.sol_rank_independence)",
        "consequence": "the rank-dependent part of the measured scaling is kernel/multicast overhead (and any rank-dependent SoL recomputation), not anything the bare identity family expresses; a future rank-dependent-latency or overhead capability has here its first measured motivation and its measured magnitude (~1.59x over 32x ranks, or ~70% overhead at the endpoint)",
    }


def latency_axis_mapping() -> dict:
    by = _by_cell(SWEEP_ID_LAT)
    l_by_tid = {tid: l for tid, l, _role in LAT_ROWS}
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, B_REGISTRY, 4, l_by_tid[tid])), (tid, m)
        checked += 1
    assert checked == len(LAT_ROWS) * len(GRID) == 42
    _wire_check(SWEEP_ID_LAT, 4)
    # The additive latency identity: every L row differs from the L=200 row
    # by exactly 2(L - 200) at EVERY size.
    ref_tid = "crossbar4_gf11_b64_l200_v1"
    for tid, l_val, _role in LAT_ROWS:
        if tid == ref_tid:
            continue
        delta = 2 * (l_val - L_REGISTRY)
        for m in GRID:
            assert by[(tid, m)] - by[(ref_tid, m)] == delta, (tid, m)
    # Monotone ordering: at every payload the rows order exactly as their L.
    ordered = sorted(l_by_tid.items(), key=lambda kv: kv[1])
    for i in range(len(ordered) - 1):
        for m in GRID:
            assert by[(ordered[i][0], m)] < by[(ordered[i + 1][0], m)]
    # The 792 and 800 rows are adjacent (16 ns apart) — ordering distinguishes them.
    assert l_by_tid["crossbar4_gf11_b64_l800_v1"] - l_by_tid["crossbar4_gf11_b64_l792_v1"] == 8
    # Crossover placements on the executed rows (exact Fractions).
    cross_derived = crossover_xbar_vs(T_ONESHOT_4_NS, L_DERIVED_NS, B_REGISTRY, 4)
    assert cross_derived == CROSSOVER_ONESHOT_B and GRID[4] < cross_derived < GRID[6]
    # The shared (L=702, r=4) cell across the lat sweep and the tp4 sweep.
    by_tp4 = _by_cell(SWEEP_ID_TP4)
    for m in GRID:
        assert by[("crossbar4_gf11_b64_l702_v1", m)] == by_tp4[("crossbar4_gf11_b64_l702_v1", m)]
    # Latency fractions on the headline row at the regime edges.
    frac_128 = 2 * L_DERIVED_NS / by[("crossbar4_gf11_b64_l702_v1", 128)]
    frac_top = 2 * L_DERIVED_NS / by[("crossbar4_gf11_b64_l702_v1", 65536)]
    assert frac_128 == Fraction(468, 469)                        # ~99.8% at the 128-B reading
    assert frac_top == Fraction(117, 245)                        # ~47.8% at the 64 KiB boundary
    return {
        "claim": "the anchor's measured components and the corpus reference points placed on the free L axis at the bracket rank: every row differs from the registry row by exactly 2(L-200) ns at every size (identity, verified on all 35 non-reference cells of the 42-row sweep), rows order exactly as their L at every payload (the 792/800 pair 16 ns apart stays distinguished), all 42 rows reproduce the closed form by exact Fraction string equality, and the shared (L=702) cells agree exactly with the tp4 sweep",
        "rows_cross_checked": checked,
        "closed_form": "t = 2(r-1)/r*M/B + 2L = 3M/128 + 2L at r=4, B=64",
        "latency_identity": "t(L') - t(200) = 2(L' - 200) exactly, at every payload (the identity's latency term is additive)",
        "headline_row_latency_fractions": {
            "at_128b_exact": str(frac_128),
            "at_64kib_boundary_exact": str(frac_top),
            "note": "at the derived 702 the identity's CCT is 468/469 (~99.8%) pure latency at the 128-B reading and 117/245 (~47.8%) at the plan's 64 KiB small-message boundary — the whole executed regime stays latency-majority on the headline row",
        },
        "crossover_on_headline_row": {
            "near_optimal_leg_exact": str(cross_derived),
            "bracket": "between the 32768 and 65536 grid members (161/256 of the boundary) — EXECUTED as a cell in the tp4 sweep (2370 ns exactly)",
        },
        "range_placement": "EVERY executed GF-11 L value {200, 306, 702, 792, 800, 1404} sits INSIDE the A-L0X-LAT declared free range [10, 2000] — the first gap-fill anchor with no above-range placement; the measured values are BARE-HARDWARE components (no software stack), the closest quantity class to the bare per-pair parameter the corpus has placed (contrast GF-10: app-level, all 2.5x-13.5x above)",
    }


def overhead_and_barrier_class() -> dict:
    return {
        "role": "the anchor's software-class numbers — the barrier bound, the prose overhead figures, the vLLM/cost rows — placed against the identity's expressible surface",
        "barrier_bound": "'each barrier will incur more than 1 µs of overhead' is a STRICT LOWER BOUND: one barrier >= 250/351 (~71.2%) of the entire 2-GPU SoL (1404 ns) — a barrier-charged design cannot approach the SoL; the one-shot kernel's derived 2-GPU overhead (2457/25 = 98.28 ns, from the prose 7%) is more than 10x BELOW the barrier bound, the anchor's own motivation for barrier-free kernels. The identity has NO barrier/sync term at all (its 2L is pure transport): the barrier class is CANNOT-express, bounded here for the first time",
        "overhead_growth": "7% (r=2, prose) -> ~70% (r=64, prose): a 10x overhead-fraction growth over a 32x rank growth; the derived r=4 fraction (161/234 ~ 68.8% under the constant-SoL reading) is numerically the r=64 figure — under that reading the overhead jumps 2 -> 4 ranks and then flattens (a crossbar-like signature), but the reading is NOT staged (see recorded_ambiguities.sol_rank_independence)",
        "vllm_and_cost_rows": "vLLM ITL reductions 7-13% (4 GPUs) / 9-11% (8 GPUs) and 'each µs removed from AllReduce latency reduces cost by about 0.9%' are APPLICATION-level quantities (serving-loop ITL, cost model) with no model surface at any corpus fidelity — recorded as context, never executed; they corroborate that small-message AllReduce latency is the binding quantity at serving scale, nothing more",
        "classification": "the software classes (barrier, launch, sync, multicast fan-out) are the residual between every executed identity row and every measured leg — quantified here as: 2370 - 1407 = 963 ns (near-optimal kernel overhead over the floor at r=4/128B), 11000 - 4215 = 6785 ns (stock stack over its own identity), >= 1000 ns (one barrier), none expressible at L0",
    }


def confounder_separation() -> dict:
    return {
        "role": "order the axes by magnitude at the anchor, from the anchor's own numbers and the executed identities",
        "ordered_by_magnitude": {
            "1_implementation_choice_on_one_fabric": "exactly 1100/237 (~4.64) — NCCL ring vs one-shot kernel on the SAME 4 GB200s: the largest quantified factor at the anchor, and LARGER than the identity family's full chain ratio 3 at r=4 (not spannable by chain choice)",
            "2_stock_stack_over_its_own_identity": "exactly 2200/843 (~2.61) — the NCCL leg over the ring identity at the same (B, L)",
            "3_near_optimal_over_bare_floor": "exactly 790/469 (~1.68) — the best kernel over the crossbar floor; equivalently 161/234 (~68.8%) overhead over the constant-SoL reading",
            "4_bare_component_spread": "exactly 44/17 (~2.59) — remote store over LL2 RTT inside the SoL equation",
            "5_derived_vs_registry_L": "exactly 351/100 (3.51) — the current-gen derived reading over the registry default; the registry twin under-predicts the near-optimal leg by 2370/403 (~5.88)",
            "6_cal_a10_assumption_vs_derived": "exactly 400/351 (~1.14) — the assumption-class value survives within 14% (vs 45/4 = 11.25 against the app-level measurement: the quantity class decides the verdict)",
            "7_barrier_bound_share": ">= 250/351 (~71.2%) of the whole SoL per barrier (strict lower bound)",
            "8_measured_rank_growth": "170/107 (~1.59) over 32x ranks (constant-SoL reading) vs the chains' 63x/6x/1x",
            "9_direction_reading_on_the_aggregate_descriptor": "exactly x2 (unstated for the 130 TB/s figure) — plus the 2-sig-fig rounding; recorded not executed",
        },
        "dominance_over_noise_floors": "every quantified member sits far above the corpus noise floors (CAL-A4 ~5%, CAL-A6 5-8%); the unquantified members are the size reading of the bracket (figure-only table), the SoL's rank-dependence, and the software-stack decomposition — interpretation duties, not tunables",
        "conclusion": "GF-11's placements are the corpus's first CURRENT-GENERATION measured small-message collective bracket with an exact bare-hardware decomposition beneath it: the bracket's own width (4.64x) exceeds every structural lever the L0 family owns (max 3x at r=4), so the dominant confounder at the anchor is implementation, not fabric — the model's honest role is the FLOOR the bracket approaches from above, which is exactly how it is used here",
    }


def expressiveness_classification() -> dict:
    return {
        "CAN_express": {
            "measured_component_placements": "the LL2 RTT (306), remote store (792), derived per-phase reading (702) and the SoL-total alternative reading (1404) as uniform L rows with the additive identity verified on all 35 non-reference cells and the closed form on all 42",
            "cct_bracket_placement": "the measured 4-GPU bracket as a CCT-vs-CCT comparison against all three chains (the first current-gen measured collective anchor in the smoke regime): the family brackets the near-optimal leg between its two shortest chains; the crossover cell executes the size-reading boundary at exactly 41216 B",
            "sol_mapping": "the identity reproduces the measured 2-GPU SoL to within exactly M/B (demonstrated on a stored run); the mapping ambiguity (702 vs 1404) executed as two rows",
            "rank_scaling_bracket": "the 2/4/64 chain ladders (coincidence at r=2; 6L/4L/2L at r=4; 126L/12L/2L at r=64) with the measured growth bracketed between the crossbar and doubling chains",
            "cal_a10_check": "the assumption-vs-derived check as one exact fraction (400/351) on shared axes, beside GF-10's 45/4 app-level check",
        },
        "CANNOT_express": {
            "the_software_stack": "the bracket rows are FULL-STACK collective times (NCCL/LLBuffer kernels, launches, sync); the identity's 2L is bare transport — the residual classes (963 ns near-optimal overhead, 6785 ns stock overhead, >= 1000 ns per barrier) have no model surface",
            "barrier_and_sync_semantics": "no barrier, kernel-launch, or synchronization term exists in any L0 identity; the anchor's '> 1 µs' barrier bound is recorded as a bound only",
            "multicast_and_one_shot_semantics": "the one-shot/multicast mapping onto the crossbar is a DECLARED abstraction — no multicast primitive, no in-network reduction, no NVLink SHARP-class mechanism at L0; LL2/NVLink-C2C memory-hierarchy semantics (LL2 RTT, remote store) are GB200-specific mechanisms with no model surface (their TIMES are placed, their MECHANISMS are not)",
            "rank_dependent_overhead": "the measured 7% -> 70% overhead growth is rank-dependent kernel behavior; the crossbar's latency term is rank-flat by construction and no L0 chain matches the growth",
            "size_series": "the anchor's per-size latency table is a figure — no (size -> time) SERIES is extractable beyond the staged bracket points; the 128-B reading is declared, its sensitivity executed as the crossover arithmetic",
            "reading_semantics": "the SoL-to-L mapping x2 (702 vs 1404), the aggregate-B direction split, and the prose classes ('about 7%', 'roughly 70%', 2-sig-fig 130) are carried unresolved",
            "application_metrics": "vLLM ITL percentages and the cost-per-µs sensitivity have no model surface at any corpus fidelity",
        },
        "consequence_for_calibration": "GF-11 is the small-message O-CCT anchor the plan's gap 3 was missing on current-generation fabric, and the first anchor that calibrates the L axis from BARE-HARDWARE components rather than assumptions (CAL-A10) or app-level measurements (GF-10): it gives the corpus a measured current-gen floor (702-derived), a measured bracket that EXCEEDS every structural lever the L0 family owns (so any L0 prediction inside [1407, 2370] at r=4/128B is consistent with measurement without parameter change), the crossover size (41216 B) below which the model is a strict lower bound, and the rank-scaling datum (7% -> 70%) that motivates any future overhead capability. Its staged calibrated use — (a) the component L placements, (b) the bracket/crossover placements, (c) the chain-scaling bracket — is an owner design decision this record stages, mirroring the GF-05..GF-10 classifications",
    }


def registry_placements() -> dict:
    executed_l = sorted(l for _t, l, _r in LAT_ROWS)
    return {
        "A_L0X_LAT_A_L0_LAT_A_L0D_LAT": {
            "note": f"executed L rows {executed_l}: EVERY value sits INSIDE the declared free range [10, 2000] — the first gap-fill anchor with no above-range latency placement. The derived 702 = 351/1000 of the range upper and 351/100 above the registry point; CAL-A10's assumption 800 = 400/351 above the derived reading (the assumption-class value survives the bare-hardware comparison within 14%, in contrast to its 45/4 gap against GF-10's app-level measurement — quantity class decides). The measured values are BARE-HARDWARE components, the closest quantity class to the bare per-pair parameter yet placed: unlike GF-10's app-level bounds, these CAN inform a range discussion at integration (owner adjudication; the range is untouched by this stage)",
        },
        "A_L0X_BW_A_L0_BW_A_L0D_BW": {
            "note": "B fixed at the registry 64 everywhere; the NVL72 system descriptor '130 TB/s aggregate' is recorded NOT EXECUTED: its direction split is unstated (x2), 130 is 2 significant figures, and 130000/72 = 16250/9 is not an integer byte rate — the per-direction reading (8125/9 ~ 902.8 B/ns) would sit at 8125/9216 (~88%) of the declared free-range upper, the aggregate reading above it (8125/4608 ~ 1.76x); GF-03's B300 '900 GB/s theoretical' agrees with the per-direction reading to 324/325 (~0.3%) — recorded coincidence",
        },
        "rank_count_anchor_provenance": {
            "note": "r=2/4/64 are the anchor's three own systems (decomposition / bracket / scaling) — the widest anchor-pinned rank set in the gap-fill ladder, all powers of two so every backend accepts them; r=8 (the smoke default) and r=72 (NVL72's own GPU count) are recorded NOT executed: the anchor stages no collective number at either (its 8-GPU rows are vLLM ITL percentages; 72 is not a power of two so the exchange fabric rejects it)",
        },
        "cross_anchor_coincidences": {
            "702_ns": "the derived reading = exactly 351/500 of GF-09's 'sub-microsecond' boundary edge 1000 — and exactly 500/39 below GF-10's app-level 9000 (the bare-vs-app quantity-class gap on one axis, ~12.8x)",
            "11000_ns": "GF-01's MI300X 8-B eager row 16610 / this NCCL-ring row = exactly 151/100 — the stock-NCCL small-message floor is stable within 1.51x across MI300X-xGMI and GB200-NVL5, two fabric classes and two GPU generations (coincidence recorded, never cross-derived)",
            "2370_ns": "GF-01's 16-KiB eager row 13540 / this one-shot row = exactly 1354/237 (~5.7) — the custom-kernel era compresses the small-message floor by ~5.7x on current generation",
            "8125_9_B_per_ns": "GF-03's B300 theoretical 900 / this reading = exactly 324/325 — two independent NVLink5-class per-direction rate readings within 0.3%",
            "2048_ns": "the 41216 B crossover cell reads exactly 2048 ns at r=2 (644 + 1404) — a grid arithmetic coincidence, recorded not interpreted",
        },
    }


def recorded_ambiguities() -> dict:
    return {
        "size_reading": {
            "ambiguity": "the anchor's per-message-size latency table lives in a FIGURE (not enumerated in text); the bracket rows (11.0 µs NCCL ring, 2.37 µs one-shot at 4 GB200s) carry no explicit size — '128-B cache-line FP32' is the granularity statement, and the anchor labels the regime 'small-message'",
            "resolution_followed": "128 B executed as the DECLARED size reading at every anchor rank, with the sensitivity executed exactly: the crossbar identity at (702, 64, r=4) crosses the near-optimal leg at exactly 41216 B (executed as a cell hitting 2370 ns on the nose) — below that size the model is a strict lower bound on the measured bracket, above it the model would sit at/above the near-optimal leg; the NCCL-leg crossover is 1228288/3 (~409429 B, recorded not executed); under the B=8125/9 reading the near-optimal crossover leaves the small-message regime entirely (5232500/9 ~ 581389 B)",
        },
        "sol_to_l_mapping": {
            "ambiguity": "the identity charges 2L (one L per phase) while the anchor's SoL is one equation (2 x LL2 RTT + remote store): equating the totals gives L = 702 per phase, but charging the whole 1404 as one phase's L is the alternative reading — a x2-class ambiguity ON the mapping",
            "resolution_followed": "BOTH readings executed as their own rows (702 headline, 1404 alternative); the r=2 anchor run demonstrates the 702-reading residual is exactly M/B; the owner adjudicates at integration",
        },
        "quantity_class_mix": {
            "ambiguity": "the 2-GPU components (306/792/1404) are BARE-HARDWARE microbenchmarks while the 4-GPU bracket rows (11000/2370) are FULL-STACK collective kernel times — different quantity classes inside one anchor; the SoL decomposition is also a 2-GPU measurement charged at r=4/64",
            "resolution_followed": "every row's quantity class declared inline; the mapping of the 2-GPU-derived L to r=4/64 is a DECLARED reading (the identity itself is rank-parameterized); the floor-vs-stack comparison is presented as a bound relationship, never an equality",
        },
        "sol_rank_independence": {
            "ambiguity": "whether the paper's 64-GPU 'SoL bound' recomputes the decomposition at r=64 or reuses the 2-GPU 1404 ns is NOT staged; the derived overhead fractions (161/234 at r=4; 1.7x envelope at r=64) assume the CONSTANT-SoL reading",
            "resolution_followed": "the constant reading declared wherever used; under a rank-dependent SoL the derived fractions change but the executed placements (the chain ladders, the runs) do not — the ranking of confounders is robust to the reading",
        },
        "prose_precision": {
            "ambiguity": "'about 7%', 'roughly 70%', '11.0 µs', '2.37 µs' (3 s.f.), '130 TB/s' (2 s.f.), '> 1 µs' — prose-class figures, no error bars staged",
            "resolution_followed": "values executed at the stated round numbers with the prose provenance carried; the 7%/70%-derived quantities are labeled derived-from-prose; the barrier figure kept as a strict lower bound; no precision claim anywhere",
        },
        "b_axis_descriptor": {
            "ambiguity": "the '130 TB/s aggregate' NVL72 descriptor: direction split unstated (x2), 2 significant figures, and 130000/72 = 16250/9 is non-integral — no clean per-rank single-port B reading exists; the Alps '150 GB/s NVLink' figure is a SECOND system with no staged collective series",
            "resolution_followed": "the B axis recorded NOT EXECUTED (both systems); the arithmetic (16250/9 aggregate-class, 8125/9 per-direction-class, range placements) recorded exactly; the corpus's NVLink5-class B context stays with GF-03",
        },
        "vllm_and_cost_rows": {
            "ambiguity": "vLLM ITL reductions (7-13% / 9-11%) and the cost sensitivity ('each µs removed ... about 0.9%') are application-level quantities with no model surface",
            "resolution_followed": "recorded as context only, never executed, never compared to any model output",
        },
        "generation_and_system_class": {
            "ambiguity": "GB200 NVL72 is current-generation (NVLink5-class) but the paper is a 2026 PREPRINT with author-run microbenchmarks (not peer-review-verified); the decomposition system is 2 GPUs of an NVL72 rack, the bracket system 4 GPUs, the scaling endpoint 64 GPUs — no single system stages all three axes",
            "resolution_followed": "every row's system declared inline; preprint provenance carried on the anchor; no extrapolation beyond the staged systems",
        },
        "multicast_mapping": {
            "ambiguity": "mapping one-shot/multicast kernels onto the single-stage crossbar abstraction is a DECLARED modeling choice — the actual mechanisms (NVLink C2C stores, multicast fan-out, LLBuffer kernels, CTA/thread structure 64x512) have no model surface",
            "resolution_followed": "the mapping declared on every affected row; the alternative mappings (recursive-doubling exchange, ring) executed alongside as the chain family; the residual attributed to software classes, quantified as recorded arithmetic",
        },
        "r8_r72_not_executed": {
            "ambiguity": "the corpus smoke default r=8 and NVL72's own r=72 are tempting ranks with NO staged GF-11 collective number",
            "resolution_followed": "both recorded NOT executed (r=8 would be a free probe; r=72 additionally rejected by the power-of-two exchange fabric and by 128 % 72 != 0 for the payload) — the anchor-pinned 2/4/64 executed instead",
        },
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, stage GF-11 (gap-fill anchor GF-11, the LAST unlanded gap-fill anchor)",
        "anchor": {
            "anchor_id": "GF-11",
            "title": "Speed-of-light GPU collectives (arXiv 2026): GB200 NVL72 small-message latency, decomposed (MEASURED)",
            "source_row": "gap-fill anchor — NOT yet a sources.csv row (the owner integrates accepted rows; this stage made no handoff write)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-11",
            "urls": ["https://arxiv.org/abs/2607.16100", "https://arxiv.org/html/2607.16100v1"],
            "confidence": "H (extracted from HTML; hardware measurements; author-run microbenchmarks, preprint; numbers AS STAGED, not re-fetched). The per-size latency table lives in a figure — the 128-B size reading is a declared ambiguity; the 2-GPU components are bare hardware while the 4-GPU bracket rows are full-stack kernel times (mixed quantity classes, declared per row). The §GF-06 material was neither used nor fetched (standing guard)",
            "staged_numbers": "LL2_RTT 0.306 µs and remote store 0.792 µs on 2 GB200s; SoL AllReduce bound 1.404 µs = 2x0.306+0.792; barrier > 1 µs; 4-GB200 small-message AllReduce 11.0 µs (NCCL 2.29.1 ring) to 2.37 µs (LLBuffer one-shot); ~7% overhead over SoL at 2 GPUs; within roughly 70% at 64 GPUs (multicast one-shot); vLLM ITL -7-13% (4 GPUs) / -9-11% (8 GPUs); ~0.9% cost per µs of AllReduce latency; GB200 NVL72 72 GPUs 130 TB/s aggregate; Alps 4x GH200 via 150 GB/s NVLink; 128-B cache-line FP32; up to 64 CTAs x 512 threads",
        },
        "target": {
            "role": "small_message_o_cct_current_gen_plus_measured_latency_components_plus_rank_scaling",
            "o_cct_calibratable": True,
            "o_cct_target": "the anchor's 4-GB200 small-message bracket [2370, 11000] ns (one-shot / NCCL ring), compared CCT-vs-CCT against all three L0 chains at the derived reading — the FIRST current-gen measured collective anchor in the smoke regime (plan gap 3); the size reading (128-B class, figure-only table) is a declared ambiguity whose sensitivity is executed exactly (the 41216 B crossover)",
            "regime": {
                "topology_class": "executed on the three single-port L0 abstractions (fully_connected_crossbar, unidirectional_ring, fully_connected_exchange) — the latency-chain family that the bracket's implementation question isolates; the anchor's own fabric is GB200 NVL72 (NVLink5-class NVSwitch fabric, 130 TB/s aggregate descriptor recorded not executed)",
                "ranks": {
                    "executed": list(RANKS),
                    "provenance": "r=2 = the decomposition system (2 GB200s), r=4 = the bracket system, r=64 = the scaling endpoint — the anchor's three own rank counts; r=8 and r=72 recorded not executed (no staged collective number at either)",
                },
                "message_bytes_grid": {
                    "grid": GRID,
                    "provenance": "base 128 B = the anchor's '128-B cache-line FP32' granularity (the DECLARED size reading; per-size table is a figure), top 65536 B = the plan's small-message regime boundary, 41216 B = the exact near-optimal crossover (executed); every size divisible by 2/4/64 so the divisibility gates accept the exact sizes",
                },
            },
        },
        "anchor_derived": derived,
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (runs + every sweep; the one-shot/multicast-mapped chain)",
                "analytical_l0 (ring sweeps; the NCCL-leg-mapped chain)",
                "analytical_l0_recursive_doubling (exchange sweeps; the middle chain — sweep-path only, run-path-unreachable by the stage A7 gate finding)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L",
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L",
                "recursive_doubling": "t = 2(r-1)/r*M/B + 2*log2(r)*L",
                "chains_at_anchor_ranks": "r=2: 2L=2L=2L (coincide); r=4: 6L/4L/2L; r=64: 126L/12L/2L (L=702: 1404/2808/4212 at r=4; 88452/8424/1404 at r=64)",
            },
            "free_parameters": {
                "L_swept_ns": "see LAT_ROWS — {200 registry reference, 306 measured LL2 RTT, 702 derived per-phase reading (SoL/2, the headline), 792 measured remote store, 800 CAL-A10 assumption check, 1404 SoL-total alternative reading}",
                "B_fixed_ns": "64 (the registry point everywhere; GF-11 stages no clean per-rank B — the 130 TB/s aggregate descriptor recorded not executed)",
                "ranks": {"2": "decomposition system", "4": "bracket system", "64": "scaling endpoint"},
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar), A-L0/A-L0-BW/A-L0-LAT/A-L0-DIV (ring), A-L0D-POW2/A-L0D-STEP/A-L0D-BW/A-L0D-LAT/A-L0D-DIV (doubling) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_SOL2,
                    "2-GPU decomposition point (B=64 registry, L=702 derived, M=128 declared reading): exact CCT 1406 ns = measured SoL 1404 + exactly M/B = 2 — the identity reproduces the anchor's algorithm-free bound to within the wire term, BY CONSTRUCTION of the mapping (all three L0 chains coincide at r=2)",
                ),
                run_summary(
                    RUN_ID_ONESHOT4,
                    "4-GPU one-shot-mapped point (B=64, L=702, M=128): exact CCT 1407 ns — the bare floor 790/469 BELOW the measured near-optimal leg 2370 ns and 11000/1407 below the NCCL leg; 2L/t = 468/469 (~99.8% latency term)",
                ),
                run_summary(
                    RUN_ID_REGISTRY4,
                    "registry twin at the SAME rank/payload (B=64, L=200): exact CCT 403 ns — the L axis alone moves the CCT 1407/403 (~3.49); the registry defaults under-predict the near-optimal leg by 2370/403 (~5.88)",
                ),
                run_summary(
                    RUN_ID_MCAST64,
                    "64-GPU multicast-mapped scaling endpoint (B=64, L=702, M=128): exact CCT 22527/16 = 1407.9375 ns — rank-flat latency term; sits below the derived r=64 envelope 11934/5 = 2386.8 ns (1.7 x constant-SoL), which itself sits below the doubling chain — the two-sided bracket again",
                ),
            ],
            "run_point_placements": run_point_placements(),
            "reconciled_sweep_tp2": sweep_rows(SWEEP_ID_TP2, "ladder"),
            "identity_coincidence_tp2": identity_coincidence_tp2(),
            "reconciled_sweep_tp4": sweep_rows(SWEEP_ID_TP4, "ladder"),
            "bracket_mapping_tp4": bracket_mapping_tp4(),
            "reconciled_sweep_tp64": sweep_rows(SWEEP_ID_TP64, "ladder"),
            "rank_scaling_tp64": rank_scaling_tp64(),
            "reconciled_sweep_lat": sweep_rows(SWEEP_ID_LAT, "ladder"),
            "latency_axis_mapping": latency_axis_mapping(),
            "overhead_and_barrier_class": overhead_and_barrier_class(),
            "confounder_separation": confounder_separation(),
            "expressiveness_classification": expressiveness_classification(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "the anchor's near-optimal leg vs the model floor at (r=4, M=128): ratio exactly 790/469 (~1.684), absolute delta exactly 963 ns — the model sits BELOW the measured bracket's lower edge (a consistent floor, 'without accusing the fabric'); the NCCL leg vs its own identity: ratio exactly 2200/843 (~2.61), delta exactly 6785 ns; the measured bracket itself spans exactly 1100/237 (~4.64) — wider than the identity family's full chain ratio 3 at r=4; the SoL point: |1406 - 1404| = exactly 2 ns = M/B; the registry twin: 2370/403 (~5.88) under-prediction at free defaults",
            "placement_summary": "the model's axes: the measured components (306/792) and both SoL readings (702/1404) as uniform L rows (additive identity verified on all 35 non-reference cells; closed form on all 42); the CAL-A10 check at exactly 400/351; the bracket comparison across all three chains with the executed 41216 B crossover; the chain-scaling bracket 63x/6x/1x vs the measured 170/107; every executed L value inside the declared range (the first such anchor); the B-axis descriptor arithmetic recorded not executed",
            "span_placement": "executed L values {200, 306, 702, 792, 800, 1404}: ALL inside the declared range [10, 2000] (702 at 35.1% of the upper); executed B = 64 (registry) only; ranks {2, 4, 64} anchor-pinned; all recorded, registry untouched",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the small-message O-CCT role on current-gen fabric plus the measured latency-component axis; no E3/E4 language — GF-11 is an external published measurement study, not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_SOL2, RUN_ID_ONESHOT4, RUN_ID_REGISTRY4, RUN_ID_MCAST64],
            "sweep_ids": [SWEEP_ID_TP2, SWEEP_ID_TP4, SWEEP_ID_TP64, SWEEP_ID_LAT],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_TP2}",
                f"results/sweeps/{SWEEP_ID_TP4}",
                f"results/sweeps/{SWEEP_ID_TP64}",
                f"results/sweeps/{SWEEP_ID_LAT}",
            ],
            "run_backed_numbers": "every model output in comparison.anchor_point_runs and comparison.reconciled_sweep_*; the mapping functions cross-check closed forms against all 105 executed sweep rows by exact Fraction string equality (per-row wire conservation 2(r-1)/r*M at every rank; the additive latency identity on all 35 non-reference lat-sweep cells; the r=2 three-algorithm coincidence on all 21 cells; the shared L=702 cells across the tp4 and lat sweeps); comparison.run_point_placements, bracket_mapping_tp4, rank_scaling_tp64, latency_axis_mapping, overhead_and_barrier_class, confounder_separation, expressiveness_classification, registry_placements, the internal-consistency arithmetic and the recorded-not-executed values are identity/anchor/registry arithmetic declared inline",
            "inputs": [
                "experiments/calibration/gf11/sweep_gf11_tp2_v1.yaml",
                "experiments/calibration/gf11/sweep_gf11_tp4_v1.yaml",
                "experiments/calibration/gf11/sweep_gf11_tp64_v1.yaml",
                "experiments/calibration/gf11/sweep_gf11_lat_v1.yaml",
                "experiments/calibration/gf11/run_gf11_sol2_anchor_v1.yaml",
                "experiments/calibration/gf11/run_gf11_oneshot4_anchor_v1.yaml",
                "experiments/calibration/gf11/run_gf11_registry4_twin_v1.yaml",
                "experiments/calibration/gf11/run_gf11_multicast64_anchor_v1.yaml",
                "experiments/calibration/gf11/workloads/ (3 files)",
                "experiments/calibration/gf11/topologies/ (14 files)",
                "experiments/calibration/gf11/profiles/ (1 file)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf11/run_gf11_sol2_anchor_v1.yaml ; "
            "make run EXP=experiments/calibration/gf11/run_gf11_oneshot4_anchor_v1.yaml ; "
            "make run EXP=experiments/calibration/gf11/run_gf11_registry4_twin_v1.yaml ; "
            "make run EXP=experiments/calibration/gf11/run_gf11_multicast64_anchor_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf11/sweep_gf11_tp2_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf11/sweep_gf11_tp4_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf11/sweep_gf11_tp64_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf11/sweep_gf11_lat_v1.yaml ; "
            "python experiments/calibration/gf11/build_calibration_record.py",
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
