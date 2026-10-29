"""Build the PROPOSED calibration-candidate record for gap-fill anchor GF-09
(calibration stage GF-09).

GF-09 = "Ultra Ethernet's Design Principles and Architectural Innovations"
(Hoefler et al., arXiv:2508.08906, Aug 2025) — the UEC consortium's own
public design-principles paper (NOT a specification document; nothing was
ingested from ultraethernet.org). Stage role (gap-fill doc §GF-09):
R1 DESIGN-TARGET class — transport design targets ("400+ Gbps" over
"10-150m" links, "sub-microsecond latency", "target round-trip times of
10 us"), protocol constants (64-bit SACK bitmap, 8B NSCC receiver
feedback, two 20-bit CBFC cyclic counters), and worked examples (RCCC
assigns 25% to each of 4 incast flows; an oversubscription bottleneck
"can only satisfy 33% of the bandwidth"). Used exactly the way CAL-A1/A2
spec ceilings are used — never as achieved values — with CAL-A10's
assumption-class discipline (zero falsification power; placement only).
The paper's CM evaluation is deferred to the simulation study it cites
(the GF-05 material, which this stage does not open); NO measurement of
any kind is staged, and NO comparison against any anchor time is
attempted anywhere.

Pure function of immutable artifacts: reads the two append-only store
run records and the two sweep tables produced by this stage, recomputes
every derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record; append-only — an existing
record with different bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_gapfill.md`` §GF-09
(numbers AS STAGED, not re-fetched), or (b) computed from the stored
run/sweep artifacts by this script, or (c) exact closed-form identity /
declared-physics arithmetic declared inline wherever used. Nothing is
tuned: every swept B/L value carries its anchor/registry/declared-physics
provenance, and the record measures where the model output sits relative
to the anchor's design-target axes.

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
RUN_ID_XBAR_UEC50 = "e74f1edc6c2fbf6be40305648049d8fd7097b266ca899794bda857c8f62139d7"
RUN_ID_XBAR_REGISTRY = "55467745b0e88062803a0378e6f4a25137ae86adee041ac91d722cc200acecf6"
SWEEP_ID_ENVELOPE = "0ce7251a8015914f02df9632b1e8e5672097fd89b81b3f88211ece0a59f92c52"
SWEEP_ID_LATENCY = "59592c06bfaccdaa23d40ebb3d3a22599b27a5811994ad698f28dd92ac969a70"

RESULTS = REPO_ROOT / "results"

# Anchor GF-09 staged numbers (docs/calibration/anchors_gapfill.md §GF-09;
# confidence M — design targets and worked examples, not measurements;
# public arXiv paper by UEC participants, not a spec document; no spec
# text ingested, nothing from ultraethernet.org; numbers AS STAGED, not
# re-fetched).
GF09_DESIGN_CLASS_GBPS = Fraction(400)      # "designed to operate at high bandwidths (400+ Gbps)"
GF09_LINK_MIN_M = Fraction(10)              # "over medium-length (10-150m) links"
GF09_LINK_MAX_M = Fraction(150)
GF09_SUBUS_BOUNDARY_NS = Fraction(1000)     # local networks target "sub-microsecond latency"
GF09_TARGET_RTT_NS = Fraction(10 * 1000)    # "target round-trip times of 10 µs"
GF09_SACK_BITMAP_BITS = 64                  # receiver ACKs carry "a 64-bit SACK bitmap"
GF09_NSCC_FEEDBACK_BYTES = Fraction(8)      # NSCC receiver feedback is "an 8B congestion window penalty value"
GF09_CBFC_COUNTER_BITS = 20                 # CBFC uses "two 20-bit cyclic counters"
GF09_RCCC_SHARE = Fraction(25, 100)         # RCCC "assigns 25% of the bandwidth to each" of 4 incast flows
GF09_RCCC_FLOWS = 4
GF09_OVERSUB_SATISFY = Fraction(33, 100)    # bottleneck "can only satisfy 33% of the bandwidth"

# Declared physical context constants (NEVER anchor- or standard-derived;
# flagged as declared everywhere they are used).
C_VACUUM_M_PER_S = Fraction(299792458)      # SI exact (defines the metre)
FIBER_NS_PER_M = Fraction(5)                # engineering round value (~2/3 c), typical glass fiber / copper

# Derived under the DECLARED readings (decimal convention 1 GB/s = 1 B/ns;
# the design class mapped onto the per-rank single-port injection B —
# A-L0X-PORT first-order). Ethernet link rates are conventionally quoted
# per direction on full-duplex links (primary reading); the "+"
# makes the value the FLOOR of an open-ended design class.
B_UEC = GF09_DESIGN_CLASS_GBPS / 8                    # 50 B/ns (primary per-direction reading)
B_ALT = GF09_DESIGN_CLASS_GBPS / 2 / 8                # 25 B/ns (bidirectional-aggregate reading)
B_REGISTRY = Fraction(64)                             # A-L0X-BW / A-L0-BW registry point
L_REGISTRY = Fraction(200)                            # A-L0X-LAT / A-L0-LAT registry point

# Worked-example displacements at the design-class carrier (representable
# finite decimals EXECUTED; the 1/3 reading recorded not executed).
B_RCCC = B_UEC * GF09_RCCC_SHARE                       # 50/4 = 12.5
B_OVERSUB_EXACT = B_UEC * GF09_OVERSUB_SATISFY         # 50*33/100 = 16.5
B_OVERSUB_THIRD = B_UEC / 3                            # 50/3 = 16.666... NON-representable
F_RCCC = 1 / GF09_RCCC_SHARE                           # 4 exactly
F_OVERSUB_EXACT = 1 / GF09_OVERSUB_SATISFY             # 100/33 exactly (~3.0303)

# Latency-axis rows (B fixed at the carrier 50).
L_PROP_MIN = GF09_LINK_MIN_M * FIBER_NS_PER_M          # 10 m -> 50 ns
L_PROP_MAX = GF09_LINK_MAX_M * FIBER_NS_PER_M          # 150 m -> 750 ns
L_SUBUS = GF09_SUBUS_BOUNDARY_NS                       # 1000 (the target boundary edge)
L_RTT_CHARGED = GF09_TARGET_RTT_NS / 2                 # 5000 (target RTT charged as the identity's 2L)

# Vacuum-c exact propagation bounds (recorded only, exact Fractions).
T_VAC_10M_NS = GF09_LINK_MIN_M * 10 ** 9 / C_VACUUM_M_PER_S     # 5000000000/149896229 ~ 33.356
T_VAC_150M_NS = GF09_LINK_MAX_M * 10 ** 9 / C_VACUUM_M_PER_S    # 75000000000/149896229 ~ 500.346

# Protocol-constant arithmetic (recorded only; exact Fractions).
BDP_AT_TARGET = GF09_TARGET_RTT_NS * B_UEC             # 10000 ns x 50 B/ns = 500000 B
FEEDBACK_SHARE = GF09_NSCC_FEEDBACK_BYTES / BDP_AT_TARGET        # 8/500000 = 1/62500
CBFC_WRAP = 2 ** GF09_CBFC_COUNTER_BITS                # 2^20 = 1048576
CBFC_VS_BDP = Fraction(CBFC_WRAP, 1) / BDP_AT_TARGET   # 65536/31250 = 2.097152 exactly

R_SMOKE = 8                                            # free smoke default (GF-09 stages NO rank count)
RUN_PAYLOAD = 2097152                                  # 2 MiB ladder member (GF-05's run-pair payload)

LADDER = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
          134217728, 268435456, 536870912, 2147483648, 8589934592]  # standard 12-size ladder (A1/A2/A7/A9/A11/GF-05)

# topology_id -> (B, L, role label) for the closed-form cross-checks.
ENV_ROWS = [
    ("crossbar8_gf09_uec50_l200_v1", B_UEC, "carrier: the '400+ Gbps' design-class floor, per-direction Ethernet-rate reading (an open-ended class floor, never an achieved rate)"),
    ("crossbar8_gf09_agg25_l200_v1", B_ALT, "bidirectional-aggregate alternative reading of the same '400+ Gbps' (reading ambiguity exactly x2)"),
    ("crossbar8_gf09_reg64_l200_v1", B_REGISTRY, "A-L0X-BW registry point (placement; no GF-09 provenance; the registry default sits 32/25 above the design-class floor)"),
    ("crossbar8_gf09_rccc4x12_5_l200_v1", B_RCCC, "RCCC worked example: 4 incast flows x exactly 25% each => per-flow share 1/4 => 50/4 = 12.5 (asymptote exactly 4)"),
    ("crossbar8_gf09_oversub33x16_5_l200_v1", B_OVERSUB_EXACT, "oversubscription worked example, exact-33% reading => 50 x 33/100 = 16.5 (asymptote exactly 100/33; the 1/3 reading 50/3 recorded not executed)"),
]
LAT_ROWS = [
    ("crossbar8_gf09_uec50_l200_v1", L_REGISTRY, "A-L0X-LAT registry point (the placement reference)"),
    ("crossbar8_gf09_uec50_l50_v1", L_PROP_MIN, "10 m x 5 ns/m (DECLARED fiber-class constant) — propagation floor at the design class's MINIMUM reach"),
    ("crossbar8_gf09_uec50_l750_v1", L_PROP_MAX, "150 m x 5 ns/m — propagation floor at the MAXIMUM reach (15/16 of the plan's NARROW-candidate range upper ~800 ns)"),
    ("crossbar8_gf09_uec50_l1000_v1", L_SUBUS, "the 'sub-microsecond latency' target BOUNDARY edge (a target upper bound, never an achieved value; reading ambiguity recorded)"),
    ("crossbar8_gf09_uec50_l5000_v1", L_RTT_CHARGED, "the '10 µs' target RTT charged as the identity's 2L term (quantity-class caveat, GF-05 precedent; 2.5x above the declared free-range upper 2000)"),
]


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def c_rank(ranks: int) -> Fraction:
    """The bandwidth coefficient 2(r-1)/r of the identity."""
    return Fraction(2 * (ranks - 1), ranks)


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


def anchor_derived() -> dict:
    # Self-checks: the staged numbers must produce these exact values.
    assert GF09_DESIGN_CLASS_GBPS / 8 == B_UEC == 50
    assert B_ALT == 25 and B_ALT * 2 == B_UEC            # direction-reading ambiguity exactly x2
    assert B_RCCC == Fraction("12.5") == Fraction(50, 4) and F_RCCC == 4
    assert B_OVERSUB_EXACT == Fraction("16.5") == Fraction(33, 2) and F_OVERSUB_EXACT == Fraction(100, 33)
    assert B_OVERSUB_THIRD == Fraction(50, 3)            # non-representable finite decimal
    # the two 33% readings: share difference 1/300 of total; relative 1/99.
    assert abs(Fraction(1, 3) - GF09_OVERSUB_SATISFY) == Fraction(1, 300)
    assert Fraction(1, 3) / GF09_OVERSUB_SATISFY - 1 == Fraction(1, 99)
    # latency-axis targets.
    assert L_PROP_MIN == 50 and L_PROP_MAX == 750
    assert GF09_SUBUS_BOUNDARY_NS / L_PROP_MAX == Fraction(4, 3)   # one-way margin at 150 m: exactly 1/4 slack
    assert (2 * L_PROP_MAX) / GF09_SUBUS_BOUNDARY_NS == Fraction(3, 2)  # RTT reading FAILS by exactly 1/2
    assert GF09_TARGET_RTT_NS == 10000
    assert L_RTT_CHARGED == 5000 and L_RTT_CHARGED * 2 == GF09_TARGET_RTT_NS
    assert GF09_TARGET_RTT_NS / GF09_SUBUS_BOUNDARY_NS == 10        # exactly 10x the sub-µs boundary
    assert GF09_TARGET_RTT_NS / (2 * L_REGISTRY) == 25              # exactly 25x the registry pair-RTT
    assert L_RTT_CHARGED / 2000 == Fraction(5, 2)                   # 2.5x above the declared free-range upper
    assert L_SUBUS / L_REGISTRY == 5                                # the registry point is exactly 1/5 of the boundary
    # propagation shares of the CC design RTT budget.
    assert (2 * L_PROP_MIN) / GF09_TARGET_RTT_NS == Fraction(1, 100)   # 10 m RTT: 1% of the target RTT
    assert (2 * L_PROP_MAX) / GF09_TARGET_RTT_NS == Fraction(3, 20)    # 150 m RTT: 15% of the target RTT
    # vacuum-c exact bounds.
    assert T_VAC_10M_NS == Fraction(5000000000, 149896229)
    assert T_VAC_150M_NS == Fraction(75000000000, 149896229)
    assert T_VAC_10M_NS < L_PROP_MIN and T_VAC_150M_NS < L_PROP_MAX   # fiber slower than vacuum, as declared
    assert GF09_LINK_MIN_M / C_VACUUM_M_PER_S * 10 ** 9 == T_VAC_10M_NS  # constant algebra tie: t[s] -> ns
    assert GF09_LINK_MAX_M / C_VACUUM_M_PER_S * 10 ** 9 == T_VAC_150M_NS
    # protocol constants.
    assert GF09_SACK_BITMAP_BITS == 64 and GF09_SACK_BITMAP_BITS / 8 == GF09_NSCC_FEEDBACK_BYTES  # both 8 B (coincidence, never composed)
    assert BDP_AT_TARGET == 500000
    assert FEEDBACK_SHARE == Fraction(1, 62500)
    assert CBFC_WRAP == 1048576 and CBFC_VS_BDP == Fraction(65536, 31250) == Fraction("2.097152")
    # the r=5 structural twin of the RCCC worked example.
    assert 5 - 1 == GF09_RCCC_FLOWS and c_rank(5) == Fraction(8, 5)
    # ladder sanity.
    assert LADDER[0] == 8192 and LADDER[-1] == 8589934592 and len(LADDER) == 12
    assert RUN_PAYLOAD in LADDER
    return {
        "staged_numbers": {
            "system": "the UEC consortium's own public design-principles paper (Ultra Ethernet 1.0 era; Hoefler et al.) — NOT a specification document; nothing ingested from ultraethernet.org; the paper's CM evaluation is deferred to the simulation study it cites (the GF-05 material, not opened by this stage)",
            "headline": "design targets: 'designed to operate at high bandwidths (400+ Gbps) over medium-length (10-150m) links'; local networks target 'sub-microsecond latency'; CC discussion assumes 'target round-trip times of 10 µs'. protocol constants: receiver ACKs carry 'a 64-bit SACK bitmap'; NSCC receiver feedback is 'an 8B congestion window penalty value'; CBFC uses 'two 20-bit cyclic counters'. worked examples: RCCC 'assigns 25% of the bandwidth to each' of 4 incast flows; oversubscription bottleneck 'can only satisfy 33% of the bandwidth'",
            "provenance_class": "M confidence — DESIGN TARGETS AND WORKED EXAMPLES, NOT MEASUREMENTS; authored by consortium participants but published as a public paper (license-clean; no spec text ingested). R1 design-target class: used the way CAL-A1/A2 spec ceilings are (never as achieved values); CAL-A10's assumption-class discipline applies (zero falsification power against model outputs; placement only)",
        },
        "derived_arithmetic": {
            "design_class_rate_bytes_per_ns_declared_reading": str(B_UEC),
            "design_class_rate_derivation": "400 Gb/s / 8 = 50 B/ns (decimal convention 1 GB/s = 1 B/ns; Ethernet rates conventionally quoted per direction on full-duplex links — DECLARED reading, no direction split staged; the '+' makes 50 the FLOOR of an open-ended class, never a per-link achieved rate)",
            "alternative_reading_bytes_per_ns": str(B_ALT),
            "direction_ambiguity_note": "the two readings differ by exactly x2 — the GF-05/GF-08 ambiguity class; the whole GF-09 rate pair (50, 25) is exactly 2x GF-08's (25, 12.5) — coincidence recorded, never cross-derived",
            "rccc_factor_exact": str(F_RCCC),
            "rccc_note": "'assigns 25% of the bandwidth to each' of 4 incast flows — per-flow share exactly 1/4; displacement 50/4 = 12.5 EXECUTED (asymptote exactly 4); structural twin: the single-port identity at r=5 has exactly r-1 = 4 peers sharing the one port (coefficient 2(r-1)/r = 8/5) — a DECLARED structural correspondence, recorded identity arithmetic",
            "oversub_factor_exact": str(F_OVERSUB_EXACT),
            "oversub_note": "'can only satisfy 33% of the bandwidth' — exact-33/100 reading: displacement 50 x 33/100 = 16.5 EXECUTED (asymptote exactly 100/33 ~ 3.0303); 3:1-oversubscription reading 1/3: displacement 50/3 NON-representable, RECORDED NOT EXECUTED; the readings differ by 1/300 of total bandwidth (1/99 relative, ~1%) — below every corpus noise floor",
            "recorded_not_executed": {str(B_OVERSUB_THIRD): "the 1/3 (3:1-oversubscription) reading of the 33% worked example"},
            "subus_boundary_note": "'sub-microsecond latency' — a target UPPER bound; executed AT the boundary edge 1000 ns so the placement arithmetic is exact (never 'below', never an achieved value); the end-to-end vs per-pair reading is ambiguous (A10's declared-reading duty) — both recorded, neither adjudicated; the registry point 200 is exactly 1/5 of the boundary and CAL-A10's assumed 800 exactly 4/5 of it",
            "target_rtt_note": "'target round-trip times of 10 µs' = 10000 ns — a CC DESIGN POINT, not a static per-pair latency; charged as the identity's 2L term (L = 5000) with the GF-05 quantity-class caveat (a path round-trip is a different quantity class than a per-pair parameter; GF-05 executed its staged 12000 ns base RTT the same way — cross-anchor 12000/10000 = exactly 6/5, two independently staged UEC-family RTT scales one fifth apart); L = 5000 sits 2.5x ABOVE the A-L0X-LAT declared free-range upper 2000 — recorded, the range untouched",
            "propagation_floor_note": "the anchor stages a REACH CLASS (10-150 m), not latencies; rows execute 10/150 m x 5 ns/m = 50/750 ns under the DECLARED fiber-class engineering constant (~2/3 c; a free physical context constant, never anchor/standard-derived, never a measurement); vacuum-c exact bounds recorded as Fractions: " + str(T_VAC_10M_NS) + " ~ 33.356 ns (10 m) and " + str(T_VAC_150M_NS) + " ~ 500.346 ns (150 m)",
            "no_measurement_section": "the paper's CM is 'designed and tested in simulation' with the evaluation deferred to the simulation paper it cites (the GF-05 material) — NO measurement of any kind is staged; NO comparison against any anchor time is attempted anywhere in this stage",
            "no_size_regime": "GF-09 stages NO message-size regime — the payload grid is a DECLARED free probe (the standard 12-size ladder of stages A1/A2/A7/A9/A11/GF-05)",
            "no_rank_count": "GF-09 stages NO rank count — r=8 is the free smoke default; no scale sweep is executed (executing an un-staged scale would invent an axis the anchor does not speak to)",
        },
    }


def design_target_table() -> dict:
    # Self-checks: every executed displacement times its factor equals the
    # carrier exactly.
    assert B_RCCC * F_RCCC == B_UEC
    assert B_OVERSUB_EXACT * F_OVERSUB_EXACT == B_UEC
    assert B_ALT * 2 == B_UEC
    assert B_OVERSUB_THIRD * 3 == B_UEC
    assert B_REGISTRY / B_UEC == Fraction(32, 25)
    rows = [
        {
            "topology_id": "crossbar8_gf09_uec50_l200_v1",
            "kind": "carrier",
            "quote": "designed to operate at high bandwidths (400+ Gbps)",
            "B_executed": str(B_UEC),
            "asymptotic_cct_ratio_vs_carrier_exact": "1",
            "note": "the design-CLASS floor under the declared per-direction Ethernet-rate reading; '+' = open-ended class (the GF-05 uet-htsim 800 Gbps = 100 B/ns config is an example INSIDE the class at 2x the floor — cross-anchor context, never cross-derived)",
        },
        {
            "topology_id": "crossbar8_gf09_agg25_l200_v1",
            "kind": "direction-reading",
            "quote": "the same '400+ Gbps' read as a bidirectional aggregate",
            "B_executed": str(B_ALT),
            "factor_exact": str(Fraction(2)),
            "asymptotic_cct_ratio_vs_carrier_exact": "2",
            "note": "NOT a worked example: the reading-ambiguity displacement — an unpinned direction convention moves the row by exactly x2, LESS than either worked-example factor (4, 100/33) but more than the registry placement (32/25)",
        },
        {
            "topology_id": "crossbar8_gf09_reg64_l200_v1",
            "kind": "registry-placement",
            "quote": "(no GF-09 provenance)",
            "B_executed": str(B_REGISTRY),
            "asymptotic_cct_ratio_vs_carrier_exact": str(B_UEC / B_REGISTRY),
            "note": "the registry default predicts bandwidth-bound CCTs 64/50 = 32/25 = 1.28x FASTER than the design-class floor — the repo default sits 28% above the class UEC transport is designed for; the observed ratio vs the carrier falls strictly monotonically toward 25/32 (< 1) from 1",
        },
        {
            "topology_id": "crossbar8_gf09_rccc4x12_5_l200_v1",
            "kind": "worked-example-displacement",
            "quote": "RCCC assigns 25% of the bandwidth to each (of 4 incast flows)",
            "B_executed": str(B_RCCC),
            "factor_exact": str(F_RCCC),
            "asymptotic_cct_ratio_vs_carrier_exact": str(F_RCCC),
        },
        {
            "topology_id": "crossbar8_gf09_oversub33x16_5_l200_v1",
            "kind": "worked-example-displacement",
            "quote": "the bottleneck can only satisfy 33% of the bandwidth",
            "B_executed": str(B_OVERSUB_EXACT),
            "factor_exact": str(F_OVERSUB_EXACT),
            "asymptotic_cct_ratio_vs_carrier_exact": str(F_OVERSUB_EXACT),
            "note": "exact-33% reading; the 1/3 reading would give asymptote exactly 3 (readings differ by 1/99 relative)",
        },
    ]
    return {
        "carrier_point": f"B_ref = {B_UEC} B/ns = the '400+ Gbps' design-class floor (declared per-direction Ethernet-rate reading; an open-ended class floor, never an achieved rate)",
        "mapping_technique": "the A11/GF-05/GF-07/GF-08 effective-bandwidth displacement technique: each dimensionless fraction enters the AllReduce identity's B axis as carrier x fraction; the anchor's worked examples are DESIGN-DOC ALGEBRA (fair-share/capacity arithmetic), not measurements — the class mismatch is carried on every row (an incast fair-share is not a collective CCT)",
        "rows": rows,
        "recorded_not_executed": {
            str(B_OVERSUB_THIRD): "the 1/3 (3:1-oversubscription) reading of the 33% example — non-representable as a finite decimal (asymptote would be exactly 3); readings differ by 1/300 of total bandwidth, 1/99 relative",
        },
        "executed_rows_provenance": {str(b): role for _tid, b, role in ENV_ROWS},
    }


def design_target_mapping(sweep_id: str) -> dict:
    by = _by_cell(sweep_id)
    b_by_tid = {tid: b for tid, b, _role in ENV_ROWS}
    # Cross-check EVERY executed row against the closed form (exact string
    # equality of Fractions).
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, b_by_tid[tid], R_SMOKE, L_REGISTRY)), (tid, m)
        checked += 1
    assert checked == len(ENV_ROWS) * len(LADDER) == 60
    # Displacement signature: rows SLOWER than the carrier (25, 16.5, 12.5)
    # have CCT ratios vs the carrier rising strictly monotonically with
    # payload toward the exact asymptote B_carrier/B_row; the FASTER
    # registry row (64) falls strictly monotonically toward 25/32 from 1.
    carrier_tid = "crossbar8_gf09_uec50_l200_v1"
    signature = {}
    for tid in b_by_tid:
        asymptote = B_UEC / b_by_tid[tid]
        prev = None
        for m in LADDER:
            ratio = by[(tid, m)] / by[(carrier_tid, m)]
            if tid == carrier_tid:
                # the carrier row's ratio is EXACTLY 1 at every size.
                assert ratio == 1, (tid, m)
                prev = ratio
                continue
            if prev is not None:
                if asymptote > 1:
                    assert ratio > prev, (tid, m)
                    assert ratio < asymptote, (tid, m)
                else:
                    assert ratio < prev, (tid, m)
                    assert ratio > asymptote, (tid, m)
            else:
                if asymptote > 1:
                    assert ratio < asymptote, (tid, m)
                else:
                    assert ratio > asymptote, (tid, m)
            prev = ratio
        signature[tid] = {
            "asymptotic_ratio_exact": str(asymptote),
            "ratio_at_8gib_exact": str(prev),
            "ratio_at_8gib_float": float(prev),
            "ratio_at_2mib_exact": str(by[(tid, 2097152)] / by[(carrier_tid, 2097152)]),
            "ratio_at_8kib_exact": str(by[(tid, 8192)] / by[(carrier_tid, 8192)]),
        }
    # Wire-conservation audit: per-rank wire = 2(r-1)/r*M = 7M/4 on r=8.
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    wire_ok = all(
        row["per_rank_wire_bytes_exact"] == str(Fraction(7 * row["payload_bytes"], 4))
        for row in table["configs"]
    )
    assert wire_ok
    return {
        "claim": "the anchor's design-class rate and worked-example fractions map onto the L0 B axis as exact-fraction rows; the executed rows reproduce the ordering and the A11/GF-05/GF-07/GF-08 displacement signature (slower rows rise strictly monotonically toward their exact asymptotes; the faster registry row falls strictly toward 25/32) on all 60 rows, cross-checked against the closed form by exact Fraction string equality",
        "rows_cross_checked": checked,
        "closed_form": "t = 2(r-1)/r*M/B + 2L = 7/4*M/B + 400 at r=8, L=200 (registry)",
        "signature_by_row": signature,
        "small_message_note": {
            "latency_fraction_at_8kib_carrier_exact": str(2 * L_REGISTRY / by[(carrier_tid, 8192)]),
            "note": "at the 8 KiB ladder base the carrier row's latency fraction is 625/1073 ~ 58.2% — the design-target envelope's small-size end is latency-dominated, exactly the regime where the anchor's latency targets (swept separately) live",
        },
        "monotonicity_note": "every slower-than-carrier row's ratio is strictly increasing over the ladder and strictly below its exact asymptote at every size; the registry row's ratio is strictly decreasing and strictly above 25/32 — at finite size an observed displacement is ALWAYS below its bandwidth-bound limit on the slow side, and above it on the fast side",
    }


def latency_axis_mapping(sweep_id: str) -> dict:
    by = _by_cell(sweep_id)
    l_by_tid = {tid: l for tid, l, _role in LAT_ROWS}
    # Cross-check EVERY executed row against the closed form.
    checked = 0
    for (tid, m), cct in by.items():
        assert str(cct) == str(t_xbar(m, B_UEC, R_SMOKE, l_by_tid[tid])), (tid, m)
        checked += 1
    assert checked == len(LAT_ROWS) * len(LADDER) == 60
    # The latency identity: every L row differs from the L=200 row by
    # exactly 2(L - 200) at EVERY size.
    ref_tid = "crossbar8_gf09_uec50_l200_v1"
    for tid, l_val, _role in LAT_ROWS:
        if tid == ref_tid:
            continue
        delta = 2 * (l_val - L_REGISTRY)
        for m in LADDER:
            assert by[(tid, m)] - by[(ref_tid, m)] == delta, (tid, m)
    # Placement facts (exact Fractions).
    assert L_PROP_MAX / 800 == Fraction(15, 16)          # 93.75% of the plan's NARROW-candidate ~800
    assert L_SUBUS / (2 * L_REGISTRY) == Fraction(5, 2)  # boundary = 2.5x registry pair-RTT
    # Latency fraction of CCT on the RTT row at 2 MiB.
    rtt_row_2mib = by[("crossbar8_gf09_uec50_l5000_v1", 2097152)]
    assert 2 * L_RTT_CHARGED / rtt_row_2mib == Fraction(15625, 130313)
    return {
        "claim": "the anchor's three latency-side targets placed on the free L axis at the design-class carrier: every row differs from the registry row by exactly 2(L-200) ns at every size (identity, verified on all 60 rows)",
        "rows_cross_checked": checked,
        "latency_identity": "t(L') - t(200) = 2(L' - 200) exactly, at every payload (the identity's latency term is additive)",
        "placements": {
            "propagation_floor_vs_narrow_candidate": "750 ns (150 m fiber-class) = 15/16 = 93.75% of the plan §2.1 NARROW(range upper) candidate ~800 ns — pure propagation at the UEC design max reach nearly exhausts the plan's proposed range upper BEFORE any switching or processing; independent support for the plan's NARROW verdict (recorded; the registry range is untouched)",
            "internal_design_target_consistency": "the anchor's OWN targets checked against each other: a ONE-WAY reading of 'sub-microsecond' holds at 150 m (750 < 1000, slack exactly 1/4 since 1000/750 = 4/3) but a same-link ROUND-TRIP reading FAILS at 150 m (1500 > 1000, exceeding the boundary by exactly 1/2) — the two staged targets are mutually consistent only under a one-way (or single-crossing) reading at fiber velocity; at 10 m both readings hold (50 / 100 ns)",
            "rtt_budget_decomposition": "propagation consumes exactly 1/100 (10 m) to 3/20 = 15% (150 m) of the 10 µs target RTT — 85-99% of the CC design budget is non-propagation (queueing, processing, serialization), by the anchor's own reach class and declared physics",
            "rtt_vs_registry": "the target RTT 10000 ns = exactly 25x the registry pair-RTT 2L = 400 ns and exactly 10x the sub-µs boundary; L = 5000 sits 2.5x ABOVE the A-L0X-LAT declared free-range upper 2000 (quantity-class caveat: a path round-trip is not a per-pair parameter — GF-05 precedent)",
            "latency_fraction_span_on_carrier": {
                "at_8kib_exact": str(2 * L_REGISTRY / by[(ref_tid, 8192)]),
                "at_2mib_exact": str(2 * L_REGISTRY / by[(ref_tid, 2097152)]),
                "at_2mib_rtt_row_exact": str(2 * L_RTT_CHARGED / rtt_row_2mib),
                "note": "the registry-latency fraction of CCT on the carrier row falls from 625/1073 ~ 58.2% (8 KiB) to 625/115313 ~ 0.54% (2 MiB); charging the design RTT instead makes it 15625/130313 ~ 12.0% at 2 MiB — the CC timescale, if charged as static latency, is a first-order mid-size effect (in reality it is a reaction bound, not a per-pair latency — inexpressible)",
            },
        },
        "recorded_not_executed": {
            str(T_VAC_10M_NS): "vacuum-c exact one-way bound at 10 m (~33.356 ns) — the absolute physics floor",
            str(T_VAC_150M_NS): "vacuum-c exact one-way bound at 150 m (~500.346 ns)",
        },
    }


def protocol_constants_axis() -> dict:
    # All identity arithmetic (no L0 input key exists for any of it).
    assert Fraction(GF09_SACK_BITMAP_BITS, 8) == GF09_NSCC_FEEDBACK_BYTES == 8
    assert FEEDBACK_SHARE == Fraction(1, 62500)
    assert CBFC_VS_BDP == Fraction(65536, 31250)
    assert CBFC_WRAP == 2 ** 20
    return {
        "role": "the protocol-constant scale the gap-fill doc stages 'for UEC-profile transport modeling' — recorded as EXACT ARITHMETIC for the UEC-profile backend family (uet-htsim class; GF-05's sim-config provenance): no L0 input key exists for ANY of these ('credit_flow_control', 'packetization_flit_effects', 'standard_specific_semantics' are among explicitly_unsupported)",
        "sack_bitmap": "receiver ACKs carry a 64-bit SACK bitmap = 8 B of selective-ack bitmap per ACK",
        "nscc_feedback": "NSCC receiver feedback is an 8 B congestion-window penalty value — numerically also 8 B (coincidence with the SACK bitmap size; DIFFERENT messages, never composed)",
        "feedback_bandwidth_share_exact": str(FEEDBACK_SHARE),
        "feedback_share_statement": "8 B of feedback per 10 µs target RTT at the 50 B/ns design rate consumes exactly 8/(10000 x 50) = 1/62500 ~ 0.0016% of the link — the protocol-constant feedback overhead is SIX ORDERS below any CCT effect; second-order on the B axis",
        "cbfc_counters": "CBFC uses two 20-bit cyclic counters: wrap at 2^20 = 1048576 units; under the DECLARED byte-credit hypothetical (granularity NOT staged — ambiguity recorded), a full counter covers 2^20 B vs the design BDP 10000 ns x 50 B/ns = 500000 B — exactly 65536/31250 = 2.097152 target BDPs; if credit granularity is coarser (e.g. MTU-class units), coverage grows proportionally",
        "rccc_structural_twin": "the RCCC worked example's arithmetic (4 incast flows x exactly 25% each) is EXACTLY the single-port identity's serialization structure at r=5 (r-1 = 4 peers share the one port; bandwidth coefficient 2(r-1)/r = 8/5) — a DECLARED structural correspondence recorded as identity arithmetic; the allreduce reduce-scatter phase is not an incast workload",
    }


def confounder_separation() -> dict:
    return {
        "role": "the R1 design-target classification the stage was assigned: order the axes by magnitude at the anchor, from the anchor's own numbers and the executed identities",
        "ordered_by_magnitude_B_axis": {
            "1_rccc_worked_example": "4 (exactly — '25% of the bandwidth to each' of 4 flows)",
            "2_oversubscription_worked_example": "100/33 ~ 3.0303 (exactly; 3 under the 1/3 reading)",
            "3_direction_reading_ambiguity": "exactly x2 (50 vs 25 B/ns) — an UNPINNED direction convention moves the row more than the registry placement but less than either worked example",
            "4_registry_placement": "exactly 64/50 = 32/25 = 1.28 (the model at registry defaults vs at the design-class floor, bandwidth-bound asymptote; observed 115313/90225 ~ 1.278 at the 2 MiB run-pair payload)",
            "5_reading_ambiguity_of_33pct": "1/99 relative between the exact-33% and 1/3 readings (~1%) — BELOW every corpus noise floor (CAL-A4 ~5% validated band, CAL-A6 5-8% software swing): the smallest ambiguity in the corpus to date",
            "6_protocol_constants": "1/62500 — the feedback-overhead share; six orders below any CCT effect",
        },
        "ordered_by_magnitude_L_axis": {
            "1_target_rtt_vs_registry_pair_rtt": "exactly 25 (10000 vs 400 ns)",
            "2_target_rtt_vs_subus_boundary": "exactly 10 (10000 vs 1000 ns)",
            "3_max_reach_propagation_vs_registry": "3.75 (750 vs 200 ns; = 15/16 of the plan's NARROW-candidate ~800)",
            "4_subus_boundary_vs_registry_pair_rtt": "5/2 = 2.5",
            "5_min_reach_propagation_vs_registry": "1/4 (50 vs 200 ns — the registry default carries 4x the 10 m propagation floor)",
        },
        "dominance_over_noise_floors": "the design-target envelope's SMALLEST B-axis ambiguity (1/99 ~ 1%) sits BELOW the anchor set's noise floors (CAL-A4 ~5%, CAL-A6 5-8%) — a first: every prior anchor's smallest ambiguity was at or above them; the design class itself (x2 reading, factors 4 / 100/33, placement 32/25) is far outside",
        "conclusion": "any future UEC-profile backend comparison must pin (a) the direction convention (x2) and (b) the 33% reading (1/99 — likely immaterial) before any residual is attributable to a calibratable axis; on the latency side the anchor's own three targets are mutually consistent only under a one-way sub-µs reading, and its CC design RTT is a quantity class the per-pair L parameter does not carry — the design targets CONSTRAIN the UEC-profile backend's config space (rate >= 50 B/ns class, RTT scale 10 µs, sub-µs local latency) far more than they constrain L0-family CCT",
    }


def expressiveness_classification() -> dict:
    return {
        "CAN_express": {
            "design_rate_placement": "the design-class floor on the B axis under BOTH direction readings (50 carrier, 25 alternative — the ambiguity quantified at exactly x2 and executed)",
            "worked_example_magnitudes": "the RCCC and oversubscription fractions as exact-fraction displacements (12.5 and 16.5 EXECUTED with the monotone signature on all 60 envelope rows; 50/3 recorded non-representable)",
            "latency_target_boundaries": "the sub-µs boundary edge (L=1000), the 10 µs target RTT charged as 2L (L=5000), and the 10/150 m propagation floors (L=50/750) as executed L rows with the additive-difference identity verified on all 60 rows",
            "internal_consistency": "the anchor's own targets checked against each other by exact arithmetic (one-way vs round-trip sub-µs consistency at 150 m; propagation share 1/100 to 3/20 of the target RTT)",
            "registry_placement": "the A-L0X-BW point 64 against the design-class floor (asymptote exactly 32/25 = 1.28; observed 115313/90225 at the run-pair payload)",
        },
        "CANNOT_express": {
            "the_uec_transport_itself": "NSCC congestion control, the CBFC credit loop, SACK-based selective retransmission, UET packet semantics — no input keys; 'congestion', 'credit_flow_control', 'packetization_flit_effects', 'standard_specific_semantics' are all in explicitly_unsupported; the design paper's SUBJECT (the transport) is the same axis GF-05 declared out of scope, now from the design-target side",
            "the_open_class_ceiling": "'400+' has no upper member — the class is open-ended; 50 is its floor, and no single B value represents the class (the GF-05 sim config 100 is one in-class instance)",
            "achieved_latency": "'sub-microsecond' and '10 µs' are TARGETS — the anchor has zero falsification power against any model L (A10 discipline); the boundary/RTT rows are placement edges, never achieved values",
            "link_media_and_reach": "no cable-length or medium key exists; the 10-150 m reach enters only through DECLARED physics constants (SI vacuum c exact; fiber-class 5 ns/m an engineering round value) — never through anchor- or standard-derived latency values",
            "cc_mechanism_and_state": "the target RTT is a congestion-control reaction timescale, not a static latency; windows, penalties, trimming, counter state have no input keys",
            "congested_oversubscribed_dynamics": "the worked examples are fair-share ALGEBRA; queueing under oversubscription is inexpressible (the displacement rows are first-order capacity abstractions, GF-05's declared reading)",
        },
        "consequence_for_calibration": "GF-09 can never calibrate L0-family O-CCT: it stages NO measurement and NO (size -> time) series (its CM evaluation is deferred to the simulation paper it cites). Its staged calibrated use — (a) the UEC design-class rate floor 50 B/ns (inside the plan §2.1 anchored span [20, 64], numerically equal to CAL-A1's NVLink5 per-port rate — coincidence recorded), (b) the latency-target constellation (sub-µs boundary, 10 µs CC RTT, 10-150 m propagation floors) that constrains the UEC-profile backend's config space, and (c) the protocol-constant scale (8 B feedback = 1/62500 of the design rate; 2^20 CBFC wrap = 2.097152 BDPs) for the uet-htsim-class backend family — is an owner design decision this record stages, mirroring the GF-05/GF-08 classifications and the CAL-A1/A2 ceiling discipline",
    }


def registry_placements() -> dict:
    executed_b = sorted(b for _t, b, _r in ENV_ROWS)
    executed_l = sorted(l for _t, l, _r in LAT_ROWS)
    return {
        "A-L0X-BW_point_64_vs_design_class_floor_50": {
            "asymptotic_cct_ratio_exact": "32/25",
            "asymptotic_cct_ratio_float": 1.28,
            "statement": "the model at registry defaults predicts bandwidth-bound CCTs exactly 32/25 = 1.28x faster than at the UEC design-class floor (placement fact, never a tuning target)",
        },
        "anchored_span_membership": {
            "note": f"the design-class floor 50 B/ns lands INSIDE the plan §2.1 A-L0-BW anchored span [20, 64] (numerically equal to CAL-A1's derived NVLink5 per-port per-direction rate and CAL-A5's ICI per-link rate — coincidences recorded, never cross-derived); the alternative reading 25 also lands inside; the worked-example displacements {executed_b} extend BELOW the span (as GF-05's oversubscription rows did); the class is OPEN-ENDED upward ('400+'), so the span's interior placement constrains the floor, never the ceiling; recorded, the registry range is untouched",
        },
        "A-L0X-LAT_A-L0-LAT": {
            "note": f"executed L rows {executed_l}: the propagation floors 50/750 and the sub-µs boundary 1000 sit inside the declared free range [10, 2000] (1000 = exactly 50% of the upper bound; 750 = 15/16 of the plan's NARROW-candidate ~800 — pure max-reach propagation nearly exhausts it); the RTT-charged 5000 sits 2.5x ABOVE the range upper (quantity-class caveat, GF-05's 12000 precedent); all recorded, the registry range untouched",
        },
        "cross_anchor_coincidences": {
            "50_bytes_per_ns": "numerically identical to CAL-A1's derived NVLink5 per-port per-direction rate, CAL-A5's ICI per-link rate, and GF-05's flagged alternative reading of the uet-htsim 800 Gbps line rate — four independent sources at one number; recorded, never cross-derived",
            "25_bytes_per_ns": "numerically identical to GF-08's Falcon carrier (the whole GF-09 rate pair is exactly 2x GF-08's) and GF-05's 4:1-oversubscription displacement — recorded, never cross-derived",
            "12_5_bytes_per_ns": "numerically identical to GF-05's 8:1-oversubscription displacement value (100/8) — same class, never cross-derived",
            "1000_ns": "numerically identical to GF-05's uet-htsim per-hop anchor point (600 link + 400 switch traversal); CAL-A10's assumed 800 ns = exactly 4/5 of it — the sub-µs boundary is the round number three independent anchors orbit",
            "10000_vs_12000_ns": "the GF-09 target RTT and GF-05's staged base RTT differ by exactly 6/5 — two independently staged UEC-family RTT scales one fifth apart (consistency context only)",
            "57744_ns": "the registry-twin run's exact CCT at 2 MiB is IDENTICAL to GF-05's registry twin at the same point (B=64, L=200, M=2 MiB) — the intended cross-stage determinism tie-in (same identity, same free-parameter values, different provenance files)",
        },
    }


def recorded_ambiguities() -> dict:
    return {
        "direction_convention": {
            "ambiguity": "the staged '400+ Gbps' design class carries no direction split; the per-direction Ethernet-rate reading (50 B/ns) and the bidirectional-aggregate reading (25 B/ns) differ by exactly x2",
            "resolution_followed": "BOTH readings executed (the primary as the envelope carrier, the alternative as its own row); the ambiguity quantified at x2 and placed in the confounder ordering below both worked-example factors but above the registry placement — the owner pins the reading at integration",
        },
        "open_class_floor": {
            "ambiguity": "'400+' is an open-ended design CLASS: 50 B/ns is its floor, and no per-link value exists (the anchor states no rate, only the class the transport is designed for)",
            "resolution_followed": "50 executed as the class FLOOR with the open-endedness declared on every row; GF-05's 800 Gbps sim config cited as an in-class instance at 2x the floor (cross-anchor context, never cross-derived); no ceiling claim is made anywhere",
        },
        "pct33_readings": {
            "ambiguity": "'can only satisfy 33%' — exactly 33/100, or the 3:1-oversubscription rounding 1/3? The readings differ by 1/300 of total bandwidth (1/99 ~ 1% relative)",
            "resolution_followed": "the representable exact-33% reading EXECUTED (16.5); the 1/3 reading recorded not executed (50/3, asymptote would be exactly 3); the difference is BELOW every corpus noise floor (CAL-A4 ~5%, CAL-A6 5-8%) — the smallest ambiguity in the corpus to date, recorded with its magnitude",
        },
        "subus_reading": {
            "ambiguity": "'sub-microsecond latency' for local networks — end-to-end, per-hop, or per-pair? The paper's phrasing does not settle it (CAL-A10's own reading duty for the same phrase class)",
            "resolution_followed": "the boundary edge 1000 ns executed (AT the boundary, never below — targets are upper bounds, never achieved values); both readings recorded, neither adjudicated; the anchor's own reach class supplies the internal-consistency check (one-way holds at 150 m, same-link round-trip does not)",
        },
        "rtt_quantity_class": {
            "ambiguity": "'target round-trip times of 10 µs' is a CONGESTION-CONTROL design point (a reaction timescale), not a static per-pair latency; charging it as the identity's 2L term is a declared quantity-class transfer",
            "resolution_followed": "executed as the L=5000 row with the GF-05 precedent caveat carried on every comparison (GF-05 executed its 12000 ns base RTT the same way); it sits 2.5x above the declared free-range upper 2000 — recorded, the range untouched",
        },
        "declared_physics": {
            "ambiguity": "the anchor stages a reach CLASS in metres (10-150 m), not latencies; converting to nanoseconds requires a propagation constant the anchor does not give",
            "resolution_followed": "the fiber-class engineering round value 5 ns/m (~2/3 c) DECLARED as a free physical context constant on every row it touches (never anchor- or standard-derived, never a measurement); the SI vacuum-c exact bounds recorded alongside as absolute physics floors (33.356 / 500.346 ns); both constants flagged for owner review",
        },
        "protocol_constant_granularity": {
            "ambiguity": "the CBFC counter's credit granularity (bytes? MTU-class units?) is NOT staged; the 2.097152-BDP coverage figure holds only under the declared byte-credit hypothetical",
            "resolution_followed": "recorded as conditional arithmetic with the hypothetical declared inline; the SACK/feedback sizes carry no granularity issue (bits and bytes are staged directly)",
        },
        "worked_example_class": {
            "ambiguity": "the RCCC 25%-each and oversubscription 33% numbers are WORKED EXAMPLES of the design doc's own algebra — pedagogical fair-share/capacity arithmetic, not measurements and not targets",
            "resolution_followed": "executed with the A11/GF-05/GF-07/GF-08 declared dimensionless-proxy technique, the class mismatch carried on every row (an incast fair-share is not a collective CCT); never compared to any anchor time",
        },
        "confidence_class": {
            "ambiguity": "M confidence: design targets and worked examples transcribed from the staged gap-fill extraction; authored by consortium participants but published as a public paper — license-clean, NOT a spec document, nothing ingested from ultraethernet.org",
            "resolution_followed": "numbers used AS STAGED, not re-fetched; re-verification against the paper's own wording deferred to owner integration (the staging doc's instruction)",
        },
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, GF-09 (gap-fill anchor GF-09)",
        "anchor": {
            "anchor_id": "GF-09",
            "title": "Ultra Ethernet 1.0 design-principles paper: transport design targets and protocol constants (R1 design-target class)",
            "source_row": "gap-fill anchor — NOT yet a sources.csv row (the owner integrates accepted rows; this stage made no handoff write)",
            "staging_doc": "docs/calibration/anchors_gapfill.md §GF-09",
            "urls": ["https://arxiv.org/html/2508.08906v1"],
            "confidence": "M (design targets and worked examples, not measurements; public arXiv paper by UEC participants — NOT a specification document; license-clean; no spec text ingested, nothing from ultraethernet.org; numbers AS STAGED, not re-fetched). Caveat classes carried: R1 design-target class used the way CAL-A1/A2 ceilings are (never as achieved values); CAL-A10 assumption-class discipline applies (zero falsification power, placement only); the paper's CM evaluation is deferred to the simulation study it cites (the GF-05 material, not opened by this stage)",
            "staged_numbers": "designed for 400+ Gbps over 10-150 m links; local networks target sub-microsecond latency; CC assumes target round-trip times of 10 µs; receiver ACKs carry a 64-bit SACK bitmap; NSCC receiver feedback is an 8 B congestion-window penalty value; CBFC uses two 20-bit cyclic counters; RCCC worked example assigns 25% of the bandwidth to each of 4 incast flows; oversubscription worked example: bottleneck can only satisfy 33% of the bandwidth; UEC CM designed and tested in simulation (evaluation deferred to the cited simulation paper)",
        },
        "target": {
            "role": "r1_design_target_class",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "GF-09 stages NO measurement and NO (size -> time) series: its numbers are design targets, protocol constants, and worked examples. The extractable targets — the design-class rate under both direction readings, the worked-example fractions as exact-fraction displacements, the latency-target constellation (sub-µs boundary, 10 µs CC RTT, 10-150 m propagation floors), and the protocol-constant scale — ARE executed here as placement and exact arithmetic, which is exactly the R1 design-target role the gap-fill doc assigns (the CAL-A1/A2 ceiling discipline with A10's assumption-class discipline)",
            "regime": {
                "topology_class": "no UEC system (no public UEC 1.x silicon measurement exists — gap-fill doc 'Gaps that remain' #1); executed on the NON-BLOCKING single-stage abstraction (fully_connected_crossbar) as placement rows",
                "ranks": {
                    "executed": [R_SMOKE],
                    "provenance": "r=8 free smoke default — GF-09 stages NO rank count; no scale sweep is executed (an un-staged scale would invent an axis the anchor does not speak to)",
                },
                "message_bytes_ladder": {
                    "grid": LADDER,
                    "provenance": "DECLARED FREE PROBE — GF-09 stages no size regime; the standard 12-size ladder of stages A1/A2/A7/A9/A11/GF-05 (8 KiB -> 8 GiB); the run pair executes the 2 MiB member (GF-05's run-pair payload — the R1 cross-stage comparability point)",
                },
            },
        },
        "anchor_derived": derived,
        "design_target_table": design_target_table(),
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (design-target envelope and latency rows at r=8; the run pair)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; envelope sweep B in {50, 25, 64, 12.5, 16.5} at L=200; latency sweep L in {200, 50, 750, 1000, 5000} at B=50",
            },
            "free_parameters": {
                "B_injection_swept_ns": "see design_target_table.executed_rows_provenance — {50 design-class floor primary reading (the carrier), 25 bidirectional-aggregate reading, 64 registry placement, 12.5 = 50/4 (RCCC worked example), 16.5 = 50 x 33/100 (oversubscription worked example, exact-33% reading)}",
                "L_pair_swept_ns": "{200 (A-L0X-LAT registry), 50 = 10 m x 5 ns/m, 750 = 150 m x 5 ns/m (DECLARED fiber-class constant), 1000 (the sub-µs target boundary edge), 5000 (the 10 µs target RTT charged as 2L — quantity-class caveat)}",
                "ranks": {"8": "free smoke default (GF-09 stages no rank count)"},
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_UEC50,
                    "design-class carrier point (B=50 B/ns = the staged '400+ Gbps' class floor under the declared per-direction Ethernet-rate reading; L=200 ns registry; payload 2 MiB = a standard-ladder member and GF-05's run-pair payload, a declared free probe)",
                ),
                run_summary(
                    RUN_ID_XBAR_REGISTRY,
                    "registry twin (B=64 B/ns, L=200 ns — both free registry points; the SAME payload isolates the B axis; both latency terms exactly 400 ns; exact CCT 57744 ns — the GF-05 registry-twin cross-stage determinism tie-in)",
                ),
            ],
            "run_pair_placement": {
                "cct_ratio_anchor_vs_registry_exact": "115313/90225",
                "cct_ratio_anchor_vs_registry_float": float(Fraction(115313, 90225)),
                "cct_delta_anchor_minus_registry_ns_exact": "401408/25",
                "cct_delta_anchor_minus_registry_ns_float": float(Fraction(401408, 25)),
                "statement": "at the 2 MiB payload the design-class row sits at 1845008/25 = 73,800.32 ns vs the registry twin's 57744 ns — ratio exactly 115313/90225 (~1.278), strictly below the pure-B asymptote 64/50 = 1.28 (the design row's latency fraction is 625/115313 ~ 0.54%): the model at the UEC design-class floor is ~1.28x slower than at registry defaults — placement arithmetic, never a tuning target",
            },
            "reconciled_sweep_envelope": sweep_rows(SWEEP_ID_ENVELOPE, "ladder"),
            "design_target_mapping": design_target_mapping(SWEEP_ID_ENVELOPE),
            "reconciled_sweep_latency": sweep_rows(SWEEP_ID_LATENCY, "ladder"),
            "latency_axis_mapping": latency_axis_mapping(SWEEP_ID_LATENCY),
            "protocol_constants_axis": protocol_constants_axis(),
            "confounder_separation": confounder_separation(),
            "expressiveness_classification": expressiveness_classification(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — GF-09 stages NO measurement and NO (size -> time) series: design targets, protocol constants, and worked examples only; its CM evaluation is deferred to the simulation study it cites. Per the stage prompt's FAIL clause the inextractable time target is RECORDED and SKIPPED honestly — no comparison against any anchor time is attempted anywhere; the anchor's assigned role (R1 design-target placement) IS extractable and is executed above",
            "placement_summary": "the model's axes: the design-class floor on the B axis under both direction readings (50 carrier, 25 alternative — exactly x2); the worked-example fractions as exact-fraction displacements (12.5, 16.5 executed with the monotone signature on all 60 envelope rows; 50/3 recorded); the registry placement 32/25 = 1.28 (observed 115313/90225 at the run-pair payload); the latency-target constellation (boundary 1000, RTT-as-2L 5000, propagation floors 50/750 executed with the additive identity on all 60 latency rows); the internal design-target consistency check (one-way sub-µs holds at 150 m, round-trip does not); and the protocol-constant scale (feedback 1/62500, CBFC wrap 2.097152 BDPs) as exact arithmetic for the UEC-profile backend family",
            "span_placement": "executed B values {12.5, 16.5, 25, 50, 64}: the design-class floor 50 lands INSIDE the plan §2.1 anchored span [20, 64] (numerically equal to CAL-A1/A5 values — coincidence recorded; the class is open-ended upward, so the span constrains the floor only); the worked-example displacements 12.5/16.5 extend BELOW the span; executed L values {50, 200, 750, 1000, 5000}: 750 = 15/16 of the plan's NARROW-candidate ~800 (max-reach propagation nearly exhausts it), 1000 = 50% of the free-range upper, 5000 = 2.5x above it (quantity-class caveat); recorded, registry untouched",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the R1 design-target role; no E3/E4 language — GF-09 is an external published design-principles paper, not a measurement study and not our testbed",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_UEC50, RUN_ID_XBAR_REGISTRY],
            "sweep_ids": [SWEEP_ID_ENVELOPE, SWEEP_ID_LATENCY],
            "sweep_dirs": [
                f"results/sweeps/{SWEEP_ID_ENVELOPE}",
                f"results/sweeps/{SWEEP_ID_LATENCY}",
            ],
            "run_backed_numbers": "every model output in comparison.anchor_point_runs and comparison.reconciled_sweep_*; comparison.design_target_mapping and latency_axis_mapping cross-check closed forms against all 120 executed sweep rows by exact Fraction string equality (declared inline; per-row wire conservation 7M/4); comparison.run_pair_placement, protocol_constants_axis, confounder_separation, expressiveness_classification, registry_placements, the internal-consistency arithmetic and the recorded-not-executed values are identity/anchor-registry/declared-physics arithmetic declared inline",
            "inputs": [
                "experiments/calibration/gf09/sweep_gf09_envelope_v1.yaml",
                "experiments/calibration/gf09/sweep_gf09_latency_v1.yaml",
                "experiments/calibration/gf09/run_gf09_uec50_v1.yaml",
                "experiments/calibration/gf09/run_gf09_registry_v1.yaml",
                "experiments/calibration/gf09/workloads/ (1 file)",
                "experiments/calibration/gf09/topologies/ (9 files)",
                "experiments/calibration/gf09/profiles/ (1 file)",
            ],
            "reproduce": "make run EXP=experiments/calibration/gf09/run_gf09_uec50_v1.yaml ; "
            "make run EXP=experiments/calibration/gf09/run_gf09_registry_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf09/sweep_gf09_envelope_v1.yaml ; "
            "make sweep EXP=experiments/calibration/gf09/sweep_gf09_latency_v1.yaml ; "
            "python experiments/calibration/gf09/build_calibration_record.py",
        },
    }

    # Exact-value self-checks on the executed run pair (transcription guards).
    obs50 = load_json(RESULTS / RUN_ID_XBAR_UEC50 / "observations.json")
    obsreg = load_json(RESULTS / RUN_ID_XBAR_REGISTRY / "observations.json")
    t50 = Fraction(obs50["per_op"][0]["completion_time_ns_exact"])
    treg = Fraction(obsreg["per_op"][0]["completion_time_ns_exact"])
    assert t50 == t_xbar(RUN_PAYLOAD, B_UEC, R_SMOKE, L_REGISTRY)
    assert treg == t_xbar(RUN_PAYLOAD, B_REGISTRY, R_SMOKE, L_REGISTRY)
    assert t50 == Fraction(1845008, 25) and treg == 57744
    assert t50 / treg == Fraction(115313, 90225)
    assert t50 - treg == Fraction(401408, 25)
    assert 2 * L_REGISTRY / t50 == Fraction(625, 115313)
    assert treg == 57744  # the GF-05 registry-twin cross-stage determinism tie-in (identical free-parameter point)

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
