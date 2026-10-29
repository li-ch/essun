"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-10
(calibration stage GF-10).

GF-10 = Li et al., "Evaluating Modern GPU Interconnect: PCIe, NVLink,
NV-SLI, NVSwitch and GPUDirect" (IEEE TPDS 32(1) 2020/2019,
arXiv:1903.04611; extracted from the public ar5iv HTML). Stage role
(gap-fill doc §GF-10): the MEASURED hop/pair-latency axis (plan gap 2 —
"the weakest axis of the whole plan") plus the anchor's measured
per-link/per-pair bandwidth rates. The doc stages this anchor precisely
so CAL-A10's assumption-class 0.8 µs value "can finally be checked
against" a measurement. GF-10 stages P2P/pair-level microbenchmark
measurements, NOT a collective (size -> time) series: per the stage
prompt's FAIL clause the collective CCT target is recorded as
inextractable and skipped honestly — no CCT-vs-CCT comparison is
attempted anywhere; what IS extractable (measured axis placements) is
executed. The §GF-06 material was neither used nor fetched by this
stage (the standing guard; the staging doc was opened only to read
§GF-10).

Pure function of immutable artifacts: reads the two append-only store
run records and the two sweep tables produced by this stage, recomputes
every derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_gapfill.md`` §GF-10
(numbers AS STAGED, not re-fetched), or (b) computed from the stored
run/sweep artifacts by this script, or (c) exact closed-form identity /
declared-arithmetic declared inline wherever used. Nothing is tuned:
every swept B/L value carries its anchor/registry provenance, and the
record measures where the model output sits relative to the anchor's
measured axes.

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
RUN_ID_XBAR_ANCHOR = "e8e69beba664b2d9246a7bc741dbebafea18f543a8f070d77865f20977c2a87e"
RUN_ID_XBAR_REGISTRY = "9b8f09ef4dc6f98210ba954b5e18a4cefdd379d4169b13085909fd8042a307d9"
SWEEP_ID_LATENCY = "3bb1df441d5579a1595e607ab0d070b64ccb19aa5a8af5ca56d74aea30067284"
SWEEP_ID_BANDWIDTH = "5b408539003b7caf01bf881129d3f0a25f4fd7b45f5c920c23cb03db7cb92faf"

RESULTS = REPO_ROOT / "results"

# Anchor GF-10 staged numbers (docs/calibration/anchors_gapfill.md §GF-10;
# confidence M-H — prose numbers extracted verbatim from the ar5iv HTML; the
# full per-pair matrices are heat-map figures, not text-extractable; V100-era
# values, one generation older than CAL-A4's NVLink-3 domain; numbers AS
# STAGED, not re-fetched).
# Latency axis — MEASURED app-level P2P (Tartan suite; µs -> ns exact).
L_NVLINK_DIRECT_NS = Fraction(9000)     # NVLink directly-connected pairs, DGX-1: "around 9 µs"
L_MANUAL_2X_NS = Fraction(18000)        # "increased by about 2x for P100-DGX-1" => ~18 µs (doc's own derivation)
L_MANUAL_3X_NS = Fraction(27000)        # "3x for V100-DGX-1" => ~27 µs (same system as the 9 µs baseline)
L_NVSLI_LOCAL_NS = Fraction(5000)       # NV-SLI local access ~5 µs
L_NVSLI_REMOTE_NS = Fraction(8000)      # NV-SLI remote ~8 µs
L_PCIE_REMOTE_NS = Fraction(13000)      # PCIe remote ~13 µs
# Bandwidth axis — measured/derived rates (decimal convention 1 GB/s = 1 B/ns;
# the anchor STATES the direction split: "50 GB/s bidirectional (25 GB/s per
# direction)" — the x2 direction-ambiguity class does NOT apply here).
B_LINK_PD = Fraction(25)                # per-link per-direction NVLink-2
B_PAIR_PD = Fraction(150)               # "6 switches => 300 GB/s per GPU pair" bidirectional => 6 x 25 per direction
B_RDMA_PEAK = Fraction(12)              # SummitDev GPUDirect-RDMA peak "12 GB/s at 64 MB"
B_PINNED_LB = Fraction(14)              # PinnedMem-GPUDirect "more than 14 GB/s" (strict LOWER BOUND)
BISECTION_B_NS = Fraction(2400)         # DGX-2 baseboard bisection "25 GB/s x 8 links/switch x 6 switches = 2.4 TB/s"
# Regime boundaries.
FLAT_P100_B = 16384                     # latency flat up to 16 KiB (P100)
FLAT_V100_B = 65536                     # latency flat up to 64 KiB (V100)
SATURATION_B = 4194304                  # NVLink V1/V2 bandwidth saturates at "about 2^22 = 4 MB"
RDMA_OPPOINT_B = 67108864               # the RDMA peak's staged operating point, 64 MB = 2^26

# Registry / cross-anchor reference values (registry and integrated-anchor
# provenance, never GF anchors).
B_REGISTRY = Fraction(64)               # A-L0X-BW registry point
L_REGISTRY = Fraction(200)              # A-L0X-LAT registry point
L_A10_ASSUMED = Fraction(800)           # CAL-A10 assumption-class 0.8 µs (integrated sources.csv row)
L_RANGE_UPPER = Fraction(2000)          # A-L0X-LAT declared free-range upper
B_SPAN = (Fraction(20), Fraction(64))   # plan §2.1 A-L0-BW anchored span

R_SMOKE = 8                             # DGX-1's own GPU count (the 9 µs system) — anchor-anchored rank
RUN_PAYLOAD = 2097152                   # 2 MiB ladder member (GF-05/GF-09 run-pair payload)

LADDER = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
          134217728, 268435456, 536870912, 2147483648, 8589934592]  # standard 12-size ladder (A1/A2/A7/A9/A11/GF-05/GF-09)

# topology_id -> (L, role label) for the latency sweep (B fixed at 25).
LAT_ROWS = [
    ("crossbar8_gf10_b25_l200_v1", L_REGISTRY, "A-L0X-LAT registry point (the placement reference)"),
    ("crossbar8_gf10_b25_l800_v1", L_A10_ASSUMED, "CAL-A10's assumption-class 0.8 µs NVLink end-to-end value (integrated anchor) — the check the gap-fill doc stages GF-10 for"),
    ("crossbar8_gf10_b25_l5000_v1", L_NVSLI_LOCAL_NS, "NV-SLI local access ~5 µs — the anchor's LOWEST measured latency (still 2.5x the declared free-range upper)"),
    ("crossbar8_gf10_b25_l8000_v1", L_NVSLI_REMOTE_NS, "NV-SLI remote ~8 µs"),
    ("crossbar8_gf10_b25_l9000_v1", L_NVLINK_DIRECT_NS, "NVLink directly-connected pairs, DGX-1, 'around 9 µs' — THE MEASURED HEADLINE (45x the registry point)"),
    ("crossbar8_gf10_b25_l13000_v1", L_PCIE_REMOTE_NS, "PCIe remote ~13 µs — the anchor's transport-class top (labeled proxy: PCIe is not a GPU scale-up fabric)"),
    ("crossbar8_gf10_b25_l18000_v1", L_MANUAL_2X_NS, "DGX-1 manual-routing pairs 'about 2x' => ~18 µs (the doc's own derivation; P100-baseline caveat recorded)"),
    ("crossbar8_gf10_b25_l27000_v1", L_MANUAL_3X_NS, "DGX-1 manual-routing pairs '3x' for V100-DGX-1 => ~27 µs — exactly 3x within one chassis, the anchor's full pair-heterogeneity spread"),
]
# topology_id -> (B, role label) for the bandwidth sweep (L fixed at 200).
BW_ROWS = [
    ("crossbar8_gf10_b25_l200_v1", B_LINK_PD, "the anchor's per-link per-direction NVLink-2 rate (the carrier twin; direction split STATED by the anchor)"),
    ("crossbar8_gf10_b64_l200_v1", B_REGISTRY, "A-L0X-BW registry point (placement reference; 64/25 = 2.56x above the measured per-link rate)"),
    ("crossbar8_gf10_b150_l200_v1", B_PAIR_PD, "the DGX-2 per-GPU-pair aggregate per direction (6 switches x 25) — the single-port injection reading of a switched fabric"),
    ("crossbar8_gf10_b12_l200_v1", B_RDMA_PEAK, "SummitDev GPUDirect-RDMA peak at its staged 64 MB operating point (labeled proxy: host-path transport)"),
    ("crossbar8_gf10_b14_l200_v1", B_PINNED_LB, "PinnedMem-GPUDirect 'more than 14 GB/s' — a STRICT LOWER BOUND (inequality carried)"),
]


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def crossover_bytes(l: Fraction, b: Fraction, ranks: int) -> Fraction:
    """Payload M* where the identity's latency term equals its wire term:
    2L = 2(r-1)/r*M/B  =>  M* = L*B*r/(r-1).  Above M* the row is
    wire-dominated; below it, latency-dominated."""
    return l * b * ranks / (ranks - 1)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
    model = obs["model"]
    b_val = Fraction(model["injection_bytes_per_ns_exact"])
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


def anchor_derived() -> dict:
    # Self-checks: the staged numbers must produce these exact values.
    assert L_NVSLI_LOCAL_NS == 5000 and L_NVSLI_REMOTE_NS == 8000 and L_PCIE_REMOTE_NS == 13000
    assert L_NVLINK_DIRECT_NS == 9000
    assert L_MANUAL_2X_NS == 2 * L_NVLINK_DIRECT_NS     # the doc's own ~18 µs derivation
    assert L_MANUAL_3X_NS == 3 * L_NVLINK_DIRECT_NS     # the doc's own ~27 µs derivation (same system: V100-DGX-1)
    assert L_MANUAL_3X_NS / L_NVLINK_DIRECT_NS == 3     # exactly 3x within ONE chassis
    # measured envelope order and span.
    meas = sorted([L_NVSLI_LOCAL_NS, L_NVSLI_REMOTE_NS, L_NVLINK_DIRECT_NS,
                   L_PCIE_REMOTE_NS, L_MANUAL_2X_NS, L_MANUAL_3X_NS])
    assert meas == [5000, 8000, 9000, 13000, 18000, 27000]
    assert meas[-1] / meas[0] == Fraction(27, 5)        # the measured envelope spans 5.4x
    # the CAL-A10 check the gap-fill doc stages this anchor for.
    assert L_NVLINK_DIRECT_NS / L_A10_ASSUMED == Fraction(45, 4)   # 11.25 — "an order above", quantified
    # vs registry and the declared free range.
    assert L_NVLINK_DIRECT_NS / L_REGISTRY == 45
    for v in meas:
        assert v > L_RANGE_UPPER                        # EVERY measured latency sits above the declared range upper
    assert L_NVSLI_LOCAL_NS / L_RANGE_UPPER == Fraction(5, 2)
    assert L_PCIE_REMOTE_NS / L_RANGE_UPPER == Fraction(13, 2)
    assert L_MANUAL_3X_NS / L_RANGE_UPPER == Fraction(27, 2)   # 13.5x — the largest above-range placement in the corpus
    assert L_A10_ASSUMED / L_RANGE_UPPER == Fraction(2, 5)     # the assumption-class row sits inside the range
    # transport/system-class spreads (the anchor's own ratios).
    assert L_PCIE_REMOTE_NS / L_NVLINK_DIRECT_NS == Fraction(13, 9)
    assert L_NVSLI_REMOTE_NS / L_NVSLI_LOCAL_NS == Fraction(8, 5)
    assert L_NVLINK_DIRECT_NS / L_NVSLI_LOCAL_NS == Fraction(9, 5)
    # bandwidth axis: the anchor's own arithmetic, exact.
    assert B_LINK_PD * 2 == 50                          # "50 GB/s bidirectional (25 GB/s per direction)" — split STATED
    assert B_PAIR_PD == 6 * B_LINK_PD                   # "6 switches => 300 GB/s per GPU pair" => 150 B/ns per direction
    assert B_PAIR_PD * 2 == 300                         # the staged bidirectional figure
    # The staged bisection equation "25 GB/s x 8 links/switch x 6 switches
    # = 2.4 TB/s" carries a x2 ambiguity INSIDE one equation: its quoted
    # operands multiply to exactly HALF its stated result.
    assert 8 * 6 * B_LINK_PD == 1200                    # the literal quoted-operand product = 1.2 TB/s
    assert BISECTION_B_NS == 2400 and 2 * 8 * 6 * B_LINK_PD == BISECTION_B_NS   # closes only under the bidirectional reading
    assert BISECTION_B_NS == 16 * B_PAIR_PD == 8 * (B_PAIR_PD * 2)              # = per-GPU aggregate x all 16 GPUs, either direction reading
    assert B_REGISTRY / B_LINK_PD == Fraction(64, 25)   # registry placement 2.56x
    assert B_PINNED_LB / B_RDMA_PEAK == Fraction(7, 6)  # the pinned-memory speedup, exactly 7/6
    assert B_LINK_PD / B_RDMA_PEAK == Fraction(25, 12)
    # span membership.
    assert B_SPAN[0] <= B_LINK_PD <= B_SPAN[1]          # 25 lands inside [20, 64] at the low end
    assert B_PAIR_PD > B_SPAN[1]                        # 150 above the span (V100-era aggregate)
    assert B_RDMA_PEAK < B_SPAN[0] and B_PINNED_LB < B_SPAN[0]   # host-path proxies below the span
    # regime boundaries.
    assert FLAT_P100_B == 16384 and FLAT_V100_B == 65536
    assert FLAT_V100_B == 4 * FLAT_P100_B               # the V100 flat region is exactly 4x the P100 one
    assert SATURATION_B == 2 ** 22 == 64 * FLAT_V100_B  # 2^22 = 4 MB, exponent arithmetic only
    assert RDMA_OPPOINT_B == 2 ** 26
    # flat-region bound arithmetic (one-way reading; the P2P transfer model
    # t = M/B_eff + L is flat through 64 KiB => crossover >= 64 KiB).
    assert FLAT_V100_B / L_NVLINK_DIRECT_NS == Fraction(8192, 1125)   # ~7.28 B/ns implied effective-B LOWER bound
    assert L_NVLINK_DIRECT_NS * B_LINK_PD == 225000                     # at 25 B/ns the P2P crossover is 225000 B >= 64 KiB — consistent
    assert FLAT_V100_B < L_NVLINK_DIRECT_NS * B_LINK_PD
    # ladder sanity.
    assert LADDER[0] == 8192 and LADDER[-1] == 8589934592 and len(LADDER) == 12
    assert RUN_PAYLOAD in LADDER
    assert FLAT_P100_B not in LADDER and LADDER[0] < FLAT_P100_B < LADDER[1]   # 16 KiB = 2^14 NOT a ladder member (the ladder hits odd exponents 2^13, 2^15, ...)
    assert FLAT_V100_B not in LADDER and LADDER[1] < FLAT_V100_B < LADDER[2]   # 64 KiB = 2^16 NOT a ladder member either — both flat boundaries bracketed at exactly 2x ladder spacing
    assert SATURATION_B not in LADDER and LADDER[4] < SATURATION_B < LADDER[5]   # 2^22 between 2 MiB and 8 MiB
    assert RDMA_OPPOINT_B not in LADDER and LADDER[6] < RDMA_OPPOINT_B < LADDER[7]  # 2^26 between 32 MiB and 128 MiB
    return {
        "staged_numbers": {
            "system": "Tartan-suite P2P microbenchmarks on P100/V100 DGX-1 (PCIe + NVLink-1/2), an NV-SLI system, DGX-2 (16x V100, 6x NVSwitch), and SummitDev (arXiv:1903.04611 via ar5iv HTML)",
            "headline": "NVLink directly-connected GPU pairs: P2P latency 'around 9 µs' (DGX-1); manual-routing pairs 'increased by about 2x for P100-DGX-1 and 3x for V100-DGX-1' (=> ~18/~27 µs); NV-SLI local ~5 µs, NV-SLI remote ~8 µs, PCIe remote ~13 µs; DGX-2 NVSwitch remote-access latency homogeneous across all pairs, two-hop vs one-hop 'very small, almost negligible'; per-link 50 GB/s bidirectional (25 GB/s per direction), 6 switches => 300 GB/s per GPU pair; DGX-2 baseboard bisection '25 GB/s x 8 links/switch x 6 switches = 2.4 TB/s'; NVLink V1/V2 bandwidth saturates at 'about 2^22 = 4 MB'; latency flat up to 16 KiB (P100) / 64 KiB (V100); SummitDev GPUDirect-RDMA peak '12 GB/s at 64 MB', PinnedMem-GPUDirect 'more than 14 GB/s'",
            "provenance_class": "M-H confidence — MEASURED (microbenchmarks), but APP-LEVEL (P2P latency includes the software stack — bound, not equality; the doc's own interpretation duty); prose numbers verbatim from ar5iv HTML, the per-pair matrices are heat-map figures not text-extractable; V100-era, one generation older than CAL-A4's NVLink-3 domain; numbers AS STAGED, not re-fetched",
        },
        "derived_arithmetic": {
            "measured_latency_envelope_ns": [str(v) for v in meas],
            "cal_a10_check_exact": "measured 9000 vs CAL-A10's assumed 800 = exactly 45/4 = 11.25 — the gap-fill doc's own 'an order above the assumption', quantified for the first time (the staging of this anchor exists precisely for this check)",
            "registry_check_exact": "measured 9000 vs the A-L0X-LAT registry point 200 = exactly 45",
            "range_placement": "EVERY measured GF-10 latency (5000-27000 ns) sits ABOVE the A-L0X-LAT declared free-range upper 2000 ns — by exactly 5/2 (NV-SLI local) up to 27/2 = 13.5 (manual-routing 3x, the largest above-range placement in the corpus); recorded with the app-level-vs-bare quantity-class caveat (the range is untouched; the anchor BOUNDS app-level P2P, it does not measure bare pair latency — see recorded_ambiguities.quantity_class)",
            "heterogeneity_spread_exact": "DGX-1 within one chassis: direct pairs 9000 vs manual-routing 27000 = exactly 3x (and 18000 = 2x) — the anchor's own measured pair-heterogeneity spread, the input to the uniformity bracket",
            "transport_class_spreads_exact": "PCIe/NVLink = 13/9; NV-SLI remote/local = 8/5; NVLink-direct/NV-SLI-local = 9/5; whole measured envelope = 27/5 = 5.4x",
            "bandwidth_internal_consistency": "per-pair 300 = 6 x 50 bidirectional => 150 B/ns per direction = 6 x 25 exactly; the staged bisection headline 2400 B/ns = 16 x 150 = 8 x 300 exactly (the per-GPU aggregate times all 16 DGX-2 GPUs, under either direction reading) — BUT the bisection equation's own quoted operands (25 x 8 x 6) multiply to exactly HALF its stated result (1200, not 2400): the equation closes only under the bidirectional reading (50 x 8 x 6), re-introducing a x2 inside one staged equation — recorded below as bisection_equation_x2, both readings carried, neither adjudicated",
            "direction_split_stated": "this is the FIRST corpus anchor that states its direction split itself ('50 GB/s bidirectional (25 GB/s per direction)') — the x2 direction-reading ambiguity class of GF-05/GF-08/GF-09 does NOT apply to GF-10's LINK rate; the bisection equation, however, quotes the per-direction 25 against a bidirectional 2.4 TB/s result (see bandwidth_internal_consistency) — the ambiguity survives at the aggregate level",
            "flat_region_bound": "one-way P2P t = M/B_eff + L flat through the measured 64 KiB boundary => B_eff >= 65536/9000 = 8192/1125 ~ 7.28 B/ns (a LOWER bound only, under the one-way reading; under a round-trip reading it halves); at the anchor's own per-direction per-link 25 B/ns the P2P crossover would sit at 9000 x 25 = 225000 B (~219.7 KiB) >= 64 KiB — the anchor's numbers are mutually consistent, and the flat region does not pin B_eff above 8192/1125",
            "flat_region_vs_ladder": "NEITHER flat boundary is a standard-ladder member (the ladder hits odd exponents 2^13, 2^15, 2^17, ...; the boundaries are 2^14 and 2^16, each bracketed by adjacent ladder members at exactly 2x spacing) — both boundaries' 9000-row latency fractions are recorded in latency_axis_mapping.recorded_not_executed and small_message_regime as exact Fraction arithmetic, not executed as sweep cells",
            "saturation_vs_ladder": "the staged saturation point 2^22 = 4194304 B falls between ladder members 2^21 (2 MiB) and 2^23 (8 MiB); the RDMA peak's operating point 2^26 = 64 MB falls between 2^25 (32 MiB) and 2^27 (128 MiB) — both bracketed, neither executed (they are P2P/NVLink bandwidth-regime edges, not collective CCT points)",
        },
    }


def latency_axis_mapping(sweep_id: str) -> dict:
    by = _by_cell(sweep_id)
    l_by_tid = {tid: l for tid, l, _role in LAT_ROWS}
    # Cross-check EVERY executed row against the closed form (exact string
    # equality of Fractions).
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, B_LINK_PD, R_SMOKE, l_by_tid[tid])), (tid, m)
        checked += 1
    assert checked == len(LAT_ROWS) * len(LADDER) == 96
    # The latency identity: every L row differs from the L=200 row by
    # exactly 2(L - 200) at EVERY size.
    ref_tid = "crossbar8_gf10_b25_l200_v1"
    for tid, l_val, _role in LAT_ROWS:
        if tid == ref_tid:
            continue
        delta = 2 * (l_val - L_REGISTRY)
        for m in LADDER:
            assert by[(tid, m)] - by[(ref_tid, m)] == delta, (tid, m)
    # Monotone ordering: at every payload the rows order exactly as their L.
    ordered = sorted(l_by_tid.items(), key=lambda kv: kv[1])
    for i in range(len(ordered) - 1):
        for m in LADDER:
            assert by[(ordered[i][0], m)] < by[(ordered[i + 1][0], m)]
    # Crossover placements (exact Fractions).
    cross_head = crossover_bytes(L_NVLINK_DIRECT_NS, B_LINK_PD, R_SMOKE)
    cross_reg = crossover_bytes(L_REGISTRY, B_LINK_PD, R_SMOKE)
    cross_a10 = crossover_bytes(L_A10_ASSUMED, B_LINK_PD, R_SMOKE)
    assert cross_head == Fraction(1800000, 7) and LADDER[2] < cross_head < LADDER[3]
    assert cross_reg == Fraction(40000, 7) and cross_reg < LADDER[0]
    assert cross_a10 == Fraction(160000, 7) and LADDER[0] < cross_a10 < LADDER[1]
    # Latency fractions on the headline row: the ladder base (executed cell)
    # and the first member above the V100 flat boundary (executed cell); the
    # flat boundaries themselves (2^14, 2^16) are off-ladder — recorded
    # closed-form arithmetic below, not sweep cells.
    frac_8k = 2 * L_NVLINK_DIRECT_NS / by[("crossbar8_gf10_b25_l9000_v1", 8192)]
    frac_16k = 2 * L_NVLINK_DIRECT_NS / t_xbar(FLAT_P100_B, B_LINK_PD, R_SMOKE, L_NVLINK_DIRECT_NS)
    frac_64k = 2 * L_NVLINK_DIRECT_NS / t_xbar(FLAT_V100_B, B_LINK_PD, R_SMOKE, L_NVLINK_DIRECT_NS)
    frac_128k = 2 * L_NVLINK_DIRECT_NS / by[("crossbar8_gf10_b25_l9000_v1", 131072)]
    assert frac_8k == Fraction(28125, 29021)   # ~96.9% (executed cell, the ladder base)
    assert frac_16k == Fraction(28125, 29917)  # ~94.0% (the P100 flat boundary, off-ladder closed form)
    assert frac_64k == Fraction(28125, 35293)  # ~79.7% (the V100 flat boundary, off-ladder closed form)
    assert frac_128k == Fraction(28125, 42461) # ~66.2% (the first ladder member ABOVE the V100 flat boundary)
    return {
        "claim": "the anchor's measured app-level P2P latencies placed on the free L axis at the measured per-link carrier: every row differs from the registry row by exactly 2(L-200) ns at every size (identity, verified on all 84 non-reference cells of the 96-row sweep), rows order exactly as their L at every payload, and all 96 rows reproduce the closed form by exact Fraction string equality",
        "rows_cross_checked": checked,
        "closed_form": "t = 2(r-1)/r*M/B + 2L = 7/4*M/25 + 2L = 7M/100 + 2L at r=8, B=25 (the measured per-link carrier)",
        "latency_identity": "t(L') - t(200) = 2(L' - 200) exactly, at every payload (the identity's latency term is additive)",
        "crossovers": {
            "headline_row_9000": {
                "exact": str(cross_head),
                "float": float(cross_head),
                "bracket": "between ladder members 131072 (128 KiB) and 524288 (512 KiB) — at the measured latency the collective identity stays latency-dominated ~4 payload octaves into the ladder",
            },
            "registry_row_200": {
                "exact": str(cross_reg),
                "bracket": "BELOW the ladder base 8192 — at registry latency the carrier row is wire-dominated across the whole ladder: the exact opposite regime of the measured row",
            },
            "a10_row_800": {
                "exact": str(cross_a10),
                "bracket": "between 8192 and 32768 — INSIDE the anchor's own measured flat region (<= 64 KiB); a cross-quantity-class coincidence (collective identity crossover vs P2P flat boundary are different quantities), recorded not adjudicated",
            },
        },
        "headline_row_latency_fractions": {
            "at_8kib_exact": str(frac_8k),
            "at_16kib_p100_flat_boundary_exact": str(frac_16k),
            "at_64kib_v100_flat_boundary_exact": str(frac_64k),
            "at_128kib_first_above_v100_flat_exact": str(frac_128k),
            "note": "at the measured 9 µs the identity's CCT is ~96.9% pure latency at the 8 KiB ladder base, ~94.0% at the P100 flat boundary (16 KiB) and ~79.7% at the V100 flat boundary (64 KiB) — both boundaries off-ladder, recorded as closed-form Fraction arithmetic — under app-level latency the model's small-message CCT is almost entirely the software-stack-inflated L term; even the first ladder member above the V100 flat boundary (128 KiB) remains ~66% latency",
        },
        "recorded_not_executed": {
            "16384": "the P100 flat-region boundary 16 KiB = 2^14 is NOT a standard-ladder member (the ladder hits odd exponents); its 9000-row latency fraction 28125/29917 ~ 94.0% is recorded here as exact closed-form arithmetic, not executed as a sweep cell",
            "65536": "the V100 flat-region boundary 64 KiB = 2^16 is NOT a standard-ladder member either; its 9000-row latency fraction 28125/35293 ~ 79.7% is recorded here as exact closed-form arithmetic, not executed as a sweep cell",
        },
    }


def bandwidth_axis_mapping(sweep_id: str) -> dict:
    by = _by_cell(sweep_id)
    b_by_tid = {tid: b for tid, b, _role in BW_ROWS}
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, b_by_tid[tid], R_SMOKE, L_REGISTRY)), (tid, m)
        checked += 1
    assert checked == len(BW_ROWS) * len(LADDER) == 60
    # Wire-conservation audit: per-rank wire = 2(r-1)/r*M = 7M/4 on r=8.
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    wire_ok = all(
        row["per_rank_wire_bytes_exact"] == str(Fraction(7 * row["payload_bytes"], 4))
        for row in table["configs"]
    )
    assert wire_ok
    # Displacement signature vs the measured per-link carrier (25): slower
    # rows rise toward B_carrier/B_row, faster rows fall toward it.
    carrier_tid = "crossbar8_gf10_b25_l200_v1"
    signature = {}
    for tid in b_by_tid:
        asymptote = B_LINK_PD / b_by_tid[tid]
        prev = None
        for m in LADDER:
            ratio = by[(tid, m)] / by[(carrier_tid, m)]
            if tid == carrier_tid:
                assert ratio == 1, (tid, m)
                prev = ratio
                continue
            if prev is not None:
                if asymptote > 1:
                    assert ratio > prev and ratio < asymptote, (tid, m)
                else:
                    assert ratio < prev and ratio > asymptote, (tid, m)
            else:
                assert (ratio < asymptote) if asymptote > 1 else (ratio > asymptote), (tid, m)
            prev = ratio
        signature[tid] = {
            "asymptotic_ratio_vs_per_link_carrier_exact": str(asymptote),
            "ratio_at_8gib_exact": str(prev),
            "ratio_at_2mib_exact": str(by[(tid, 2097152)] / by[(carrier_tid, 2097152)]),
        }
    # Placement facts.
    assert b_by_tid["crossbar8_gf10_b150_l200_v1"] / B_LINK_PD == 6      # the 6-switch structure, exactly 6
    assert B_REGISTRY / B_LINK_PD == Fraction(64, 25)
    assert B_LINK_PD / b_by_tid["crossbar8_gf10_b12_l200_v1"] == Fraction(25, 12)
    assert b_by_tid["crossbar8_gf10_b14_l200_v1"] / b_by_tid["crossbar8_gf10_b12_l200_v1"] == Fraction(7, 6)
    return {
        "claim": "the anchor's measured rates placed on the free B axis at registry latency: all 60 rows reproduce the closed form by exact Fraction string equality with per-row wire conservation 7M/4, and the displacement signature (slower rows rise strictly monotonically toward B_carrier/B_row, faster rows fall strictly toward it) holds on every row",
        "rows_cross_checked": checked,
        "closed_form": "t = 7/4*M/B + 400 at r=8, L=200 (registry)",
        "signature_by_row": signature,
        "placements": {
            "per_link_25_vs_span": "25 B/ns lands INSIDE the plan §2.1 A-L0-BW anchored span [20, 64] at its lower edge — the plan's span, built from CAL-A12's 20 (NCCL model) and CAL-A7's 64 (MI300X), predicted this scale; the anchor's measured rate confirms the span's lower half for the NVLink-2 generation",
            "aggregate_150_vs_span": "150 B/ns sits ABOVE the span (V100-era aggregate; the plan §2.1 A-L0X-BW note has modern anchors at 448-900 B/ns aggregate — 150 is one generation earlier and inside the declared free range [1, 1024]) — the per-link vs aggregate structure is exactly the A-L0X-PORT single-port abstraction question, executed as two rows",
            "proxy_rows_below_span": "12 and 14 B/ns sit BELOW the span's lower edge 20 — the host-path transport class the span's GPU-fabric anchors deliberately exclude; executed under the CAL-A11/GF-07 labeled-proxy discipline, never scale-up predictions",
            "bisection_recorded_not_executed": "the DGX-2 bisection headline 2400 B/ns is a FABRIC aggregate (16 x 150 = 8 x 300 exactly; its quoted operands alone give 1200 — the x2 recorded ambiguity) — never an L0 per-pair row; recorded as exact arithmetic only",
            "registry_placement": "the registry point 64 sits exactly 64/25 = 2.56x above the measured per-link rate and 32/75 of the measured aggregate — the repo default predicts bandwidth-bound CCTs 2.56x faster than the measured per-link carrier (placement fact, never a tuning target)",
        },
    }


def small_message_regime() -> dict:
    # The anchor's own regime edges against the identity (exact Fractions).
    frac_flat_v100 = 2 * L_NVLINK_DIRECT_NS / (Fraction(7 * FLAT_V100_B, 100) + 2 * L_NVLINK_DIRECT_NS)
    assert frac_flat_v100 == Fraction(28125, 35293)
    by = _by_cell(SWEEP_ID_LATENCY)
    frac_8k_reg = 2 * L_REGISTRY / by[("crossbar8_gf10_b25_l200_v1", 8192)]
    assert frac_8k_reg == Fraction(625, 1521)   # ~41.1% at the measured carrier (B=25)
    return {
        "role": "the anchor's measured regime edges — the latency-flat boundaries (16/64 KiB) and the bandwidth saturation point (2^22 = 4 MB) — placed against the identity at the measured carrier",
        "flat_region_vs_plan_boundary": "the gap-fill doc's own note, quantified: the V100 latency-flat region (<= 64 KiB) empirically matches the small-message regime boundary the plan uses (§1.2 gap row '<= ~64 KiB') — the FIRST measured support for that boundary's scale (P100's 16 KiB is exactly 1/4 of it); the plan's boundary is unchanged, now with a measured ancestor",
        "headline_row_in_flat_region": "at the measured 9 µs the 9000-row's latency fraction is 96.9% at the 8 KiB ladder base, ~94.0% at the P100 flat boundary (16 KiB, off-ladder arithmetic), and exactly 28125/35293 ~ 79.7% at the V100 flat boundary (64 KiB, off-ladder arithmetic) — inside the anchor's own measured flat region the collective identity is 80-97% latency term when L carries the app-level measurement",
        "registry_row_contrast": "the registry-latency row's 8 KiB latency fraction at the measured carrier is exactly 625/1521 ~ 41.1% (GF-09 recorded 625/1073 ~ 58.2% for the same registry latency at ITS 50 B/ns carrier — the small-size latency fraction is carrier-dependent: the slower the carrier, the larger the wire term's share); at registry latency the model sits near the flat-region edge, at the measured latency deep inside it",
        "saturation_point": "the staged NVLink V1/V2 bandwidth saturation 'about 2^22 = 4 MB' is a P2P bandwidth-regime edge, not a collective CCT point — recorded as ladder bracketing (between 2^21 and 2^23) and NOT executed; on the 9000 row the collective latency/wire crossover (1800000/7 ~ 251 KiB) sits a factor 4194304/(1800000/7) = 458752/28125 ~ 16.31x BELOW the P2P saturation point — the two regime edges never coincide because they are different quantities on different rows",
        "bound_arithmetic": "flat-through-64-KiB implies B_eff >= 8192/1125 ~ 7.28 B/ns (one-way reading; halves under round-trip) — an implied app-level EFFECTIVE bandwidth bound three times below the per-link 25: within the flat region the software-stack latency, not the link, is the bottleneck the anchor measures",
    }


def uniformity_bracket() -> dict:
    return {
        "role": "the anchor's own evidence on the uniform-per-pair-latency abstraction (A-L0X-LAT uniformity / A-L0X-PORT single-hop), which the L0 crossbar identity assumes",
        "dgx2_supporting": "DGX-2 (6x NVSwitch, 16 GPUs): 'remote-access latency homogeneous across all pairs, two-hop vs one-hop difference very small, almost negligible' — MEASURED support for the uniform-L, single-hop switch abstraction on NVSwitch-class fabrics (qualitative; no number staged — the finding's magnitude is only 'negligible' at DGX-2 scale)",
        "dgx1_contra": "DGX-1 (hybrid cube, direct + manual-routing pairs): direct pairs at 9 µs vs manual-routing pairs at 'about 2x'/'3x' — measured pair HETEROGENEITY up to exactly 3x within one chassis; 'nonuniform_pair_latency' is explicitly_unsupported at L0, so the DGX-1 structure is inexpressible in one fabric row",
        "bracket_statement": "the anchor brackets the uniformity assumption BY TOPOLOGY CLASS: valid (homogeneous to 'negligible' difference) on switched NVSwitch-class fabrics, violated up to exactly 3x on direct/hybrid-cube topologies — the first measured bracketing of a structural L0 assumption in the corpus",
        "headline_system_caveat": "the 9 µs headline comes from the DIRECT pairs of the NON-uniform system (DGX-1's best pairs): charging 9000 uniformly to all pairs is a DECLARED reading; the heterogeneous tail is executed as its own uniform rows (18000/27000), never mixed into one row",
        "consequence": "any future per-pair-heterogeneity capability (multi-row L) has its first measured motivation and its first measured magnitude (2x-3x, DGX-1-class); until then, uniform-L results on direct/hybrid topologies carry a measured up-to-3x pair-spread caveat that switched-fabric results do not",
    }


def confounder_separation() -> dict:
    return {
        "role": "order the axes by magnitude at the anchor, from the anchor's own numbers and the executed identities",
        "ordered_by_magnitude_L_axis": {
            "1_measured_vs_registry": "exactly 45 (9000 vs 200 ns) — the registry default sits forty-five times below the measured app-level point",
            "2_measured_vs_cal_a10_assumption": "exactly 45/4 = 11.25 — the doc's 'an order above the assumption', now exact",
            "3_measured_envelope_vs_range_upper": "5/2 to 27/2 (2.5x-13.5x) — every measured latency above the declared free-range upper; the largest above-range placement in the corpus",
            "4_dgx1_pair_heterogeneity": "exactly 3 (and 2) within one chassis — the uniform-L abstraction's measured violation magnitude on hybrid-cube topologies",
            "5_system_transport_spread": "13/9 (PCIe vs NVLink), 8/5 (NV-SLI remote/local), 27/5 = 5.4 across the whole measured envelope",
            "6_one_way_vs_round_trip_reading": "exactly x2 — the P2P latency reading is NOT staged (the largest unquantified-resolved ambiguity; both readings bound, neither adjudicated)",
            "7_app_level_vs_bare_quantity_class": "UNQUANTIFIED — the doc's own 'they bound different things': the software-stack share of the 9 µs is not decomposed by the anchor (interpretation duty at integration)",
        },
        "ordered_by_magnitude_B_axis": {
            "1_bisection_vs_per_gpu_aggregate": "exactly 16 (2400/150) — the rank count, and the anchor's internal-consistency check",
            "2_aggregate_vs_per_link": "exactly 6 (150/25) — the 6-switch uplink structure: the single-port abstraction's central scale question, executed as two rows",
            "3_registry_vs_per_link": "exactly 64/25 = 2.56",
            "4_per_link_vs_rdma_proxy": "exactly 25/12 ~ 2.08",
            "5_pinned_vs_rdma_proxy": "exactly 7/6 ~ 1.17 — and the '>14' inequality means the pinned row's true ratio is <= 7/6 (a lower bound on B, an upper bound on the slowdown vs pinned)",
        },
        "dominance_over_noise_floors": "the smallest quantified L-axis member (7/6 ~ 1.17 on the B axis; 13/9 ~ 1.44 on the L axis) sits FAR above the corpus noise floors (CAL-A4 ~5%, CAL-A6 5-8%) — every GF-10 axis placement is resolvable; the two UNQUANTIFIED members (reading x2-class, quantity class) are the residual interpretation duties",
        "conclusion": "GF-10's placements are the strongest-axis findings of the gap-fill ladder so far: measured, mutually consistent to the byte (bisection arithmetic), with the direction split stated. The two open duties are the reading of the P2P latency (one-way vs round-trip, x2) and the app-vs-bare decomposition — both flagged for the owner; neither is tunable",
    }


def expressiveness_classification() -> dict:
    return {
        "CAN_express": {
            "measured_latency_placements": "all six measured app-level latencies as uniform L rows on the measured per-link carrier, with the additive identity t(L')-t(200)=2(L'-200) verified on all 84 non-reference cells and the closed form on all 96",
            "measured_rate_placements": "the per-link (25), aggregate (150), and proxy (12, 14-lower-bound) rates as B rows with the displacement signature verified on all 60 rows",
            "cal_a10_check": "the assumption-vs-measured check as one exact fraction (45/4) on shared axes",
            "regime_edge_arithmetic": "flat-region boundaries and saturation point as exact brackets/bounds against ladder members and the identity (79.7% latency fraction at 64 KiB; crossover brackets; B_eff >= 8192/1125)",
            "internal_consistency": "the anchor's own bisection/per-pair arithmetic verified exactly (2400 = 16 x 150 = 6 x 8 x 25)",
            "uniformity_bracket": "the DGX-1/DGX-2 heterogeneity/homogeneity findings as measured bounds on the uniform-L abstraction's validity domain",
        },
        "CANNOT_express": {
            "the_software_stack": "the measured quantity is APP-LEVEL P2P (CUDA API + driver + link); L is a bare per-pair parameter — the rows bound, they never equal; the stack share is not decomposed by the anchor",
            "p2p_semantics": "the backend models AllReduce only (no P2P collective exists); the placement borrows the collective identity's L axis — a P2P transfer time is a different quantity class than a collective CCT",
            "pair_heterogeneity": "'nonuniform_pair_latency' is explicitly_unsupported — DGX-1's direct-vs-manual-routing structure (1x/2x/3x pair classes in one chassis) cannot live in one fabric row; each class is executed as its own homogeneous row",
            "multi_link_per_pair_structure": "'multi_port_injection' is explicitly_unsupported — the 6-link uplink aggregate is expressed only as the single-port B reading (150); a per-pair dedicated-link identity (CAL-A7's full-mesh class) would be a different model",
            "reading_semantics": "one-way vs round-trip for the P2P numbers is not staged — the x2 ambiguity is carried unresolved; '>14 GB/s' is a bound, not a value",
            "regime_boundary_keys": "no input key exists for latency-flat boundaries or bandwidth saturation points — they enter only as recorded exact arithmetic against the ladder",
            "cuda_nv_sli_pcie_mechanisms": "the mechanisms behind the measured numbers (NV-SLI bridging, PCIe host path, GPUDirect pinning) have no model surface — the proxy rows carry the class mismatch by declaration",
        },
        "consequence_for_calibration": "GF-10 cannot calibrate O-CCT (it stages no collective series), but it is the first MEASURED anchor on the plan's weakest axis: it places every latency-side free-parameter reference (registry 200, CAL-A10 800, range upper 2000) against measured app-level values (45x, 11.25x, 2.5-13.5x gaps), verifies the plan's small-message boundary has a measured ancestor (the 64 KiB flat region), and brackets the uniform-L structural assumption by topology class. Its staged calibrated use — (a) measured L-axis placements at the measured carrier, (b) the per-link/aggregate/proxy B-axis placements, (c) the flat-region and bound arithmetic — is an owner design decision this record stages, mirroring the GF-05..GF-09 classifications",
    }


def registry_placements() -> dict:
    executed_l = sorted(l for _t, l, _r in LAT_ROWS)
    executed_b = sorted(b for _t, b, _r in BW_ROWS)
    return {
        "A_L0X_LAT_A_L0_LAT": {
            "note": f"executed L rows {executed_l}: every measured GF-10 latency (5000-27000) sits ABOVE the declared free-range upper 2000 (2.5x-13.5x); CAL-A10's 800 sits inside at 2/5 of the upper. The plan §2.1 A-L0-LAT NARROW(range upper) verdict was explicitly 'contingent on extracting the deferred V100-era measured P2P series (Li et al.)' — THIS STAGE IS THAT EXTRACTION (the gap-fill doc's §GF-10 title: 'the deferred p7 extraction, DONE'). The honest finding: the extracted values are APP-LEVEL (software stack included), so they cannot directly narrow the registry range — they BOUND the bare per-pair L from above under the app-level reading only. The range is untouched; the owner adjudicates whether an app-vs-bare decomposition is derivable from any public source (none is known)",
        },
        "A_L0X_BW_A_L0_BW": {
            "note": f"executed B rows {executed_b}: the measured per-link 25 lands INSIDE the plan §2.1 anchored span [20, 64] at its lower edge (first measured confirmation of the span's lower half, NVLink-2 generation); the aggregate 150 sits above the span (V100-era, inside the declared free range); the proxy rows 12/14 sit below the span; the registry point 64 sits 64/25 = 2.56x above the measured per-link rate; the bisection 2400 is a fabric aggregate, recorded never executed; all recorded, the registry range untouched",
        },
        "rank_count_anchor_provenance": {
            "note": "r=8 is DGX-1's own GPU count — the 9 µs system — so this stage's rank count carries ANCHOR provenance for the first time in the gap-fill ladder (it is also the free smoke default and the standard ladder's rank). DGX-2's r=16 is recorded NOT executed: its staged numbers (per-link/per-pair rates, qualitative homogeneity) pin no rank-dependent quantity of the identity; executing r=16 would be a free probe, not an anchor target",
        },
        "cross_anchor_coincidences": {
            "25_bytes_per_ns": "numerically identical to CAL-A12's physical per-direction per-link 25 GB/s (NVLink-3), GF-08's Falcon carrier, and GF-09's bidirectional-aggregate alternative reading — the per-link per-direction rate is stable across NVLink-2 and NVLink-3 generations; four independent sources at one number, recorded never cross-derived",
            "800_ns": "CAL-A10's assumption-class value = exactly 4/5 of GF-09's 'sub-microsecond' boundary edge 1000 — and the anchor GF-10 quantifies its gap to measurement at exactly 45/4",
            "5000_ns": "numerically identical to GF-09's RTT-charged L row — a MEASURED app-level NV-SLI local access vs a CC design-reaction timescale: different provenance and quantity class, one number (coincidence recorded)",
            "57744_ns": "the registry twin's exact CCT at 2 MiB is IDENTICAL to the GF-05 and GF-09 registry twins at the same free-parameter point — the cross-stage determinism tie-in (third independent reproduction)",
            "27000_vs_12000": "GF-10's manual-routing 3x (27000) sits 9/4 above GF-05's staged base RTT (12000) — two different quantity classes again; recorded, never cross-derived",
        },
    }


def recorded_ambiguities() -> dict:
    return {
        "bisection_equation_x2": {
            "ambiguity": "the staged DGX-2 bisection equation quotes per-direction operands against a bidirectional result: '25 GB/s x 8 links/switch x 6 switches = 2.4 TB/s' — the operands multiply to 1200 (1.2 TB/s), exactly half the stated 2400; the equation closes only under the bidirectional reading (50 x 8 x 6), which IS exactly consistent with the staged per-pair figure (2400 = 16 x 150 = 8 x 300)",
            "resolution_followed": "BOTH readings recorded with their exact values (1200 per-direction / 2400 bidirectional); the bisection is a fabric aggregate, recorded NOT EXECUTED either way, so no L0 row carries the ambiguity; the owner adjudicates the intended reading at integration",
        },
        "p2p_reading": {
            "ambiguity": "the P2P latency numbers do not state one-way vs round-trip — a factor exactly x2 on every latency row",
            "resolution_followed": "the values executed AS STAGED (µs -> ns, one reading, the doc's own convention); the x2 flagged on every row; the owner pins the reading at integration (Tartan-suite convention is the place to check)",
        },
        "app_level_quantity_class": {
            "ambiguity": "app-level P2P latency includes the software stack (CUDA API, driver); L is a bare per-pair fabric parameter — the doc's own 'they bound different things'",
            "resolution_followed": "every latency row declared a BOUND, never an equality; no registry range change proposed from app-level values (the plan's NARROW contingency answered honestly: the extraction alone cannot narrow the range); decomposition deferred to the owner",
        },
        "prose_precision": {
            "ambiguity": "'around 9 µs', '~5 µs', '~8 µs', '~13 µs', 'about 2x/3x' — prose-level approximations, no error bars staged",
            "resolution_followed": "values executed at the stated round numbers with the 'around/approximately' provenance carried; no precision claim anywhere",
        },
        "manual_routing_derivation": {
            "ambiguity": "'increased by about 2x for P100-DGX-1 and 3x for V100-DGX-1' — the gap-fill doc applies both multipliers to the single staged baseline 9 µs (its own '=> ~18/~27 µs'), but the 2x is the P100 figure while the 9 µs baseline is the V100/DGX-1 value; the P100 direct-pair baseline is NOT staged as a number",
            "resolution_followed": "18000 = 2 x 9000 executed per the doc's own parenthetical with the P100-baseline caveat recorded; 27000 = 3 x 9000 is the same-system derivation (V100 multiplier on V100 baseline) and is exact by construction",
        },
        "pinned_lower_bound": {
            "ambiguity": "PinnedMem-GPUDirect is 'more than 14 GB/s' — an inequality, not a value",
            "resolution_followed": "14 executed as the bound value with the strict-lower-bound semantics carried on the row and in the confounder ordering (the true pinned-vs-RDMA ratio is <= 7/6)",
        },
        "dgx2_homogeneity_qualitative": {
            "ambiguity": "DGX-2's homogeneity finding ('very small, almost negligible' two-hop vs one-hop) carries NO number",
            "resolution_followed": "used only as the qualitative leg of the uniformity bracket (switched fabrics: homogeneous); no magnitude claimed; the quantitative legs are DGX-1's measured 2x/3x spread",
        },
        "heat_map_matrices": {
            "ambiguity": "the full per-pair latency matrices are heat-map figures, not text-extractable (M-H confidence class)",
            "resolution_followed": "prose numbers only, AS STAGED, not re-fetched; re-verification against the paper's figures deferred to owner integration",
        },
        "mixed_system_provenance": {
            "ambiguity": "the latency numbers come from DGX-1/NV-SLI/PCIe systems, the rates from DGX-2/SummitDev — no single system stages both axes",
            "resolution_followed": "every row's system declared inline; the anchor-point run's mixed provenance (V100-era per-link rate + DGX-1 measured latency) declared in the run manifest",
        },
        "generation_gap": {
            "ambiguity": "V100-era values (NVLink-2), one generation older than CAL-A4's NVLink-3 domain and two below current NVLink-5",
            "resolution_followed": "generation labeled on every placement; the 25 B/ns per-link stability across NVLink-2/-3 recorded as the cross-generation coincidence; no extrapolation claimed",
        },
        "proxy_class_rows": {
            "ambiguity": "the PCIe latency row and the RDMA/pinned bandwidth rows are host-path transports, not GPU scale-up fabrics",
            "resolution_followed": "executed under the CAL-A11/GF-07 labeled-proxy discipline (placement context on the axis, never scale-up predictions), the label carried on the rows",
        },
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-10 (gap-fill anchor GF-10)",
        "anchor": {
            "anchor_id": "GF-10",
            "title": "Li et al. (TPDS): V100/NVSwitch-era P2P latency numbers — the deferred p7 extraction (MEASURED hop/pair latency axis)",
            "source_row": "gap-fill anchor — NOT yet a sources.csv row (the owner integrates accepted rows; this stage made no handoff write)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-10",
            "urls": ["https://arxiv.org/abs/1903.04611", "https://ar5iv.labs.arxiv.org/html/1903.04611"],
            "confidence": "M-H (prose numbers extracted verbatim from the ar5iv HTML; the full per-pair matrices are heat-map figures, not text-extractable; V100-era, one generation older than CAL-A4's NVLink-3 domain; numbers AS STAGED, not re-fetched). MEASURED but APP-LEVEL: P2P latency includes the software stack — every latency row is a BOUND, never an equality. The §GF-06 material was neither used nor fetched (standing guard)",
            "staged_numbers": "NVLink direct-pair P2P around 9 µs (DGX-1); manual-routing pairs about 2x (P100-DGX-1) / 3x (V100-DGX-1); NV-SLI local ~5 µs / remote ~8 µs; PCIe remote ~13 µs; DGX-2 NVSwitch homogeneous pair latency, two-hop ~ one-hop; per-link 50 GB/s bidirectional (25 GB/s per direction); 6 switches => 300 GB/s per GPU pair; bisection 25 GB/s x 8 links/switch x 6 switches = 2.4 TB/s; NVLink V1/V2 saturates at about 2^22 = 4 MB; latency flat up to 16 KiB (P100) / 64 KiB (V100); SummitDev GPUDirect-RDMA 12 GB/s at 64 MB; PinnedMem-GPUDirect more than 14 GB/s",
        },
        "target": {
            "role": "measured_hop_pair_latency_axis_plus_rates",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "GF-10 stages P2P/pair-level microbenchmarks — app-level latencies, per-link/per-pair rates, regime boundaries — NOT a collective (size -> time) series. Per the stage prompt's FAIL clause the collective CCT target is recorded as inextractable and skipped honestly: no CCT-vs-CCT comparison is attempted anywhere. The extractable targets — measured placements on the L axis (the plan's weakest axis, gap 2) and the B axis, plus the regime-edge and consistency arithmetic — ARE executed here, which is exactly the role the gap-fill doc assigns ('the µs-class P2P numbers that CAL-A10's 0.8 µs assumption-class value can finally be checked against')",
            "regime": {
                "topology_class": "executed on the NON-BLOCKING single-stage abstraction (fully_connected_crossbar); the anchor's own systems bracket the abstraction: DGX-2 (NVSwitch) measured homogeneous (supports uniform-L), DGX-1 (hybrid cube) measured 2x-3x pair spread (violates it; nonuniform_pair_latency unsupported)",
                "ranks": {
                    "executed": [R_SMOKE],
                    "provenance": "r=8 = DGX-1's own GPU count (the 9 µs system) — the first anchor-anchored rank count of the gap-fill ladder; DGX-2's r=16 recorded not executed (its staged numbers pin no rank-dependent quantity)",
                },
                "message_bytes_ladder": {
                    "grid": LADDER,
                    "provenance": "DECLARED FREE PROBE — GF-10 stages no collective size series; the standard 12-size ladder (8 KiB -> 8 GiB); the run pair executes the 2 MiB member (the GF-05/GF-09 cross-stage comparability payload); the anchor's own regime edges (16/64 KiB flat, 2^22 saturation, 2^26 RDMA operating point) recorded as exact ladder brackets/bounds",
                },
            },
        },
        "anchor_derived": derived,
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (measured-latency rows at the measured per-link carrier, measured-rate rows at registry latency; the run pair)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; latency sweep L in {200, 800, 5000, 8000, 9000, 13000, 18000, 27000} at B=25; bandwidth sweep B in {12, 14, 25, 64, 150} at L=200",
            },
            "free_parameters": {
                "L_pair_swept_ns": "see LAT_ROWS — {200 registry reference, 800 CAL-A10 assumption check, 5000/8000/13000 NV-SLI/PCIe measured, 9000 NVLink direct measured headline, 18000/27000 manual-routing 2x/3x}",
                "B_injection_swept_ns": "{25 measured per-link per-direction carrier, 64 registry reference, 150 DGX-2 aggregate, 12 RDMA peak, 14 pinned lower bound}",
                "ranks": {"8": "DGX-1's own GPU count (the 9 µs system); anchor-anchored, also the smoke default"},
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_ANCHOR,
                    "measured point (B=25 B/ns = the anchor's per-link per-direction NVLink-2 rate; L=9000 ns = the anchor's 'around 9 µs' NVLink direct-pair app-level P2P latency on DGX-1 — BOUND not equality; payload 2 MiB = the GF-05/GF-09 run-pair payload, a declared free probe)",
                ),
                run_summary(
                    RUN_ID_XBAR_REGISTRY,
                    "registry twin (B=64, L=200 — both free registry points; the SAME payload isolates both axes together; exact CCT 57744 ns — the GF-05/GF-09 cross-stage determinism tie-in, third independent reproduction)",
                ),
            ],
            "run_pair_placement": {
                "cct_ratio_anchor_vs_registry_exact": "257501/90225",
                "cct_ratio_anchor_vs_registry_float": float(Fraction(257501, 90225)),
                "cct_delta_anchor_minus_registry_ns_exact": "2676416/25",
                "cct_delta_anchor_minus_registry_ns_float": float(Fraction(2676416, 25)),
                "statement": "at the 2 MiB payload the measured point sits at 4120016/25 = 164800.64 ns vs the registry twin's 57744 ns — ratio exactly 257501/90225 (~2.8534), delta exactly 107056.64 ns; the measured row's latency fraction is 28125/257501 ~ 10.9% at this mid-ladder payload (the placement is 45x on the L axis and 2.56x on the B axis at the same point) — placement arithmetic, never a tuning target",
            },
            "reconciled_sweep_latency": sweep_rows(SWEEP_ID_LATENCY, "ladder"),
            "latency_axis_mapping": latency_axis_mapping(SWEEP_ID_LATENCY),
            "reconciled_sweep_bandwidth": sweep_rows(SWEEP_ID_BANDWIDTH, "ladder"),
            "bandwidth_axis_mapping": bandwidth_axis_mapping(SWEEP_ID_BANDWIDTH),
            "small_message_regime": small_message_regime(),
            "uniformity_bracket": uniformity_bracket(),
            "confounder_separation": confounder_separation(),
            "expressiveness_classification": expressiveness_classification(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — GF-10 stages no collective (size -> time) series: its numbers are P2P microbenchmarks, rates, and regime edges. Per the stage prompt's FAIL clause the inextractable collective CCT target is RECORDED and SKIPPED honestly — no comparison against any anchor collective time is attempted anywhere; the anchor's assigned role (measured axis placement) IS extractable and is executed above",
            "placement_summary": "the model's axes: all six measured app-level latencies as uniform L rows at the measured per-link carrier (additive identity verified on all 84 non-reference cells; closed form on all 96); the CAL-A10 check at exactly 45/4; the registry gap at exactly 45; every measured latency above the declared free-range upper (2.5x-13.5x, bound not equality); the measured rates as B rows (25 inside the anchored span's lower edge, 150 above it, 12/14 proxy below it; displacement signature on all 60 rows); the run-pair ratio 257501/90225 at the cross-stage payload; the small-message regime arithmetic (80-97% latency fractions inside the anchor's own flat region; B_eff >= 8192/1125); the uniformity bracket (DGX-2 homogeneous / DGX-1 3x); and the anchor's internal bisection consistency (2400 = 16 x 150 exactly)",
            "span_placement": "executed B values {12, 14, 25, 64, 150}: 25 inside [20, 64] at the lower edge, 150 above the span (inside the declared free range), 12/14 below the span (host-path proxies), 64 the registry point; executed L values {200, 800, 5000, 8000, 9000, 13000, 18000, 27000}: 200/800 inside the declared range [10, 2000] (800 at 2/5 of the upper), all six measured values above it (2.5x-13.5x); all recorded, registry untouched",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the measured latency-axis role; no E3/E4 language — GF-10 is an external published measurement study, not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_ANCHOR, RUN_ID_XBAR_REGISTRY],
            "sweep_ids": [SWEEP_ID_LATENCY, SWEEP_ID_BANDWIDTH],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_LATENCY}",
                f"results/sweeps/{SWEEP_ID_BANDWIDTH}",
            ],
            "run_backed_numbers": "every model output in comparison.anchor_point_runs and comparison.reconciled_sweep_*; comparison.latency_axis_mapping and bandwidth_axis_mapping cross-check closed forms against all 156 executed sweep rows by exact Fraction string equality (per-row wire conservation 7M/4 on the bandwidth sweep; the additive latency identity on all 84 non-reference latency cells); comparison.run_pair_placement, small_message_regime, uniformity_bracket, confounder_separation, expressiveness_classification, registry_placements, the internal-consistency arithmetic and the recorded-not-executed values are identity/anchor/registry arithmetic declared inline",
            "inputs": [
                "experiments/calibration/gf10/sweep_gf10_latency_v1.yaml",
                "experiments/calibration/gf10/sweep_gf10_bandwidth_v1.yaml",
                "experiments/calibration/gf10/run_gf10_anchor_p2p9us_v1.yaml",
                "experiments/calibration/gf10/run_gf10_registry_v1.yaml",
                "experiments/calibration/gf10/workloads/ (1 file)",
                "experiments/calibration/gf10/topologies/ (12 files)",
                "experiments/calibration/gf10/profiles/ (1 file)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf10/run_gf10_anchor_p2p9us_v1.yaml ; "
            "make run EXP=experiments/calibration/gf10/run_gf10_registry_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf10/sweep_gf10_latency_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf10/sweep_gf10_bandwidth_v1.yaml ; "
            "python experiments/calibration/gf10/build_calibration_record.py",
        },
    }

    # Exact-value self-checks on the executed run pair (transcription guards).
    obs_a = load_json(RESULTS / RUN_ID_XBAR_ANCHOR / "observations.json")
    obs_g = load_json(RESULTS / RUN_ID_XBAR_REGISTRY / "observations.json")
    t_a = Fraction(obs_a["per_op"][0]["completion_time_ns_exact"])
    t_g = Fraction(obs_g["per_op"][0]["completion_time_ns_exact"])
    assert t_a == t_xbar(RUN_PAYLOAD, B_LINK_PD, R_SMOKE, L_NVLINK_DIRECT_NS)
    assert t_g == t_xbar(RUN_PAYLOAD, B_REGISTRY, R_SMOKE, L_REGISTRY)
    assert t_a == Fraction(4120016, 25) and t_g == 57744
    assert t_a / t_g == Fraction(257501, 90225)
    assert t_a - t_g == Fraction(2676416, 25)
    assert 2 * L_NVLINK_DIRECT_NS / t_a == Fraction(28125, 257501)
    assert t_g == 57744  # the GF-05/GF-09 registry-twin cross-stage determinism tie-in
    # The shared (25, 200) cell across the two sweeps must agree exactly.
    by_lat = _by_cell(SWEEP_ID_LATENCY)
    by_bw = _by_cell(SWEEP_ID_BANDWIDTH)
    for m in LADDER:
        assert by_lat[("crossbar8_gf10_b25_l200_v1", m)] == by_bw[("crossbar8_gf10_b25_l200_v1", m)]

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
