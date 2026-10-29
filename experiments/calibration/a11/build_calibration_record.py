"""Build the PROPOSED calibration-candidate record for anchor CAL-A11 (Q1
calibration stage A11.

Pure function of immutable artifacts: reads the two append-only store run
records and the two sweep tables produced by this stage, recomputes every
derived quantity from them with exact Fractions, and writes a
content-addressed record to ``results/calibration/<record_id>/record.json``
(record_id = SHA-256 of the canonical record, mirroring the evidence-store
addressing discipline; append-only — an existing record with different
bytes is an error, identical bytes are idempotent).

No wall-clock, no host metadata: identical inputs reproduce byte-identical
records. Every number in the record is either (a) transcribed from the
anchor's staged numbers in ``docs/calibration/anchors_staging.md`` §A11
(declared below with provenance; the staging doc paraphrases Gangidi et
al., ACM SIGCOMM 2024 + the Meta engineering blog, so no "verbatim" quote
strings are claimed here), or (b) computed from the stored run/sweep
artifacts by this script, or (c) exact closed-form identity arithmetic
cross-checked against executed artifacts by exact Fraction string equality
(declared inline wherever used). Nothing is tuned: the swept B values and
the executed rank scale carry their anchor/registry provenance, and the
record measures where the model output sits relative to the anchor's link
class, cluster scale, and congestion/load-balance envelope magnitude.

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
RUN_ID_XBAR_ANCHOR50 = "77c573b7d1b17e2ede98f0716e9c673a43d78db7db1154cce5cebaf1715ebd82"
RUN_ID_XBAR_REG64 = "e5fe7e8a35cfb81ad24e430541f428e6cac26ad7d9599dc4956adcf8a6b02377"
SWEEP_ID_BW = "d566e2862f98703ae741cb2611cd3d74311228a8645f239c722c6f335c13fd53"
SWEEP_ID_SCALE = "7a5e3f0e3bcc4c66333fb9be17b92280a5070a49d9c4545abd59dcba09cf5bc2"

RESULTS = REPO_ROOT / "results"

# Anchor CAL-A11 staged numbers (docs/calibration/anchors_staging.md §A11,
# transcription confidence M-H: production measurements, but verified from
# the public blog + abstract — the per-collective throughput tables live in
# the paper PDF and are NOT staged).
A11_OPTICS_GBPS = Fraction(400)      # "400G single-mode optics between RTSWs and CTSWs"
A11_DEGRADE = Fraction(7, 10)        # path pinning degraded training "up to more than 30%"
A11_IMPROVE = Fraction(7, 5)         # E-ECN + QP scaling "up to 40% improvement" (=1.4)
A11_CLUSTER_RANKS = 24576            # two ~24,576-GPU clusters (one RoCE, one IB)
A11_TRAIN_RANKS = 16000              # Llama 3 trained on 16,000 GPUs (RoCE cluster)

# Derived under the DECLARED reading (decimal units, 1 GB/s = 1 B/ns; IEEE
# 400GbE ports are full-duplex per-direction line rate): 400 Gbps = 50 B/ns
# per direction per link. The bidirectional-aggregate alternative (25 B/ns
# per direction) is recorded as a flagged ambiguity, NOT executed.
B_ANCHOR = A11_OPTICS_GBPS / 8                   # 50
B_ANCHOR_ALT_READING = B_ANCHOR / 2              # 25 (recorded, not swept)
B_ENVELOPE = B_ANCHOR * A11_DEGRADE              # 35 = 0.7 x 50
B_ENVELOPE_IMPLIED_BASELINE = B_ANCHOR / A11_IMPROVE  # 250/7 ~ 35.714 (recorded, not swept)
B_REGISTRY = Fraction(64)        # A-L0X-BW / A-L0-BW registry point
L_REGISTRY = Fraction(200)       # A-L0X-LAT / A-L0-LAT registry point (anchor-free axis)

R_SMOKE = 8                      # free smoke-default rank count (B-axis sweep)
R_CLUSTER = A11_CLUSTER_RANKS    # 24576 — the anchor's stated cluster scale (executed)
R_TRAIN = A11_TRAIN_RANKS        # 16000 — the anchor's stated training scale (arithmetic row)

LADDER_BW = [8192, 32768, 131072, 524288, 2097152, 8388608, 33554432,
             134217728, 268435456, 536870912, 2147483648, 8589934592]
LADDER_SCALE = [24576 * 2 ** k for k in range(15)]   # 24 KiB -> 384 MiB
RUN_PAYLOAD = 8589934592         # 8*2^30 (8 GiB), the bandwidth-bound ladder member

TOPO_BY_B = {
    "crossbar8_a11_degraded35_v1": B_ENVELOPE,
    "crossbar8_a11_link50_v1": B_ANCHOR,
    "crossbar8_a11_registry64_v1": B_REGISTRY,
}
TOPO_XBAR_SCALE = "crossbar24576_a11_link50_v1"
TOPO_RING_SCALE = "ring24576_a11_link50_v1"


# ---------------------------------------------------------------------------
# Closed-form identities (exact Fractions; every use against executed
# artifacts is cross-checked by exact string equality).
# ---------------------------------------------------------------------------
def t_xbar(m: int, b: Fraction, ranks: int, l: Fraction = L_REGISTRY) -> Fraction:
    """t = 2(r-1)/r*M/B + 2L  (src/essun/backends/analytical/l0_crossbar.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * l


def t_ring(m: int, b: Fraction, ranks: int, l: Fraction = L_REGISTRY) -> Fraction:
    """t = 2(r-1)/r*M/B + 2(r-1)*L  (src/essun/backends/analytical/l0.py)."""
    return Fraction(2 * (ranks - 1) * m, ranks) / b + 2 * (ranks - 1) * l


def c_rank(ranks: int) -> Fraction:
    """The bandwidth coefficient 2(r-1)/r of both identities."""
    return Fraction(2 * (ranks - 1), ranks)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(run_id: str, mapping: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    per_op = obs["per_op"][0]  # all 6 ops identical by construction; mean == per-op
    cct = Fraction(per_op["completion_time_ns_exact"])
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
            "injection_bytes_per_ns_exact": model["injection_bytes_per_ns_exact"],
            "pair_latency_ns_exact": model["pair_latency_ns_exact"],
        },
        "payload_bytes": per_op["payload_bytes"],
        "cct_ns_exact": per_op["completion_time_ns_exact"],
        "cct_ns_float": per_op["completion_time_ns"],
        "per_rank_wire_bytes_exact": per_op["per_rank_wire_bytes_exact"],
        "latency_term_ns_exact": str(2 * L_REGISTRY),
        "latency_fraction_of_cct_exact": str(2 * L_REGISTRY / cct),
        "latency_fraction_of_cct_float": float(2 * L_REGISTRY / cct),
    }


def _by_cell(sweep_id: str) -> dict[tuple[str, int], Fraction]:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    return {
        (row["config_id"].split("-")[2], row["payload_bytes"]): Fraction(
            row["o_cct"]["completion_time_ns_mean_exact"]
        )
        for row in table["configs"]
    }, table


def sweep_rows(sweep_id: str, name_key: str) -> dict:
    by, table = _by_cell(sweep_id)
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
    # Self-checks: the staged numbers must produce these exact values;
    # anything else is a transcription bug, not a finding.
    assert B_ANCHOR == 50 and B_ANCHOR_ALT_READING == 25
    assert B_ENVELOPE == 35 and B_ENVELOPE_IMPLIED_BASELINE == Fraction(250, 7)
    assert A11_DEGRADE == Fraction(7, 10) and A11_IMPROVE == Fraction(7, 5)
    assert B_ANCHOR / B_ENVELOPE == Fraction(10, 7)        # asymptotic degraded ratio
    assert B_ANCHOR / B_REGISTRY == Fraction(25, 32)       # asymptotic registry ratio
    assert Fraction(1) / A11_DEGRADE == Fraction(10, 7)    # 1/(1-0.3) = 10/7 exactly
    assert (B_ANCHOR / B_ENVELOPE) / A11_IMPROVE == Fraction(50, 49)  # quote consistency
    assert B_ANCHOR / B_ENVELOPE_IMPLIED_BASELINE == A11_IMPROVE  # by construction
    return {
        "staged_numbers": {
            "optics_link_rate": "400G single-mode optics between RTSWs and CTSWs",
            "path_pinning_degradation": "path-pinning degraded training performance "
            "'up to more than 30%' (metric: training performance; baseline config unstaged)",
            "ecmp_qp_improvement": "E-ECMP + QP scaling gave 'up to 40% improvement for "
            "the AllReduce collective' (baseline config unstaged)",
            "fabric": "production RoCEv2, rail-optimized, multi-plane spine-leaf; two "
            "~24,576-GPU clusters (one InfiniBand, one RoCE); Llama 3 trained on "
            "16,000 GPUs on the RoCE cluster",
            "subscription": "RTSW uplink capacity run at '1:2 under-subscription vs "
            "downlink' (direction of the ratio ambiguous in the staging — see "
            "recorded_ambiguities)",
            "provenance_class": "MEASURED production numbers, but verified from the "
            "public blog + abstract (confidence M-H); the scale-up-relevant "
            "per-collective throughput tables live in the paper PDF and are NOT "
            "staged",
        },
        "derived_arithmetic": {
            "link_bw_bytes_per_ns_per_direction_declared_reading": str(B_ANCHOR),
            "declared_reading_derivation": "400 Gbps / 8 = 50 GB/s = 50 B/ns per "
            "direction per link under the DECLARED reading: decimal units (the "
            "plan's convention 1 GB/s = 1 B/ns) + IEEE 802.3 convention that 400G "
            "Ethernet ports are full-duplex per-direction line rate",
            "link_bw_alt_reading_recorded_not_swept": str(B_ANCHOR_ALT_READING),
            "alt_reading_note": "FLAGGED AMBIGUITY: if the '400G' quote were a "
            "bidirectional aggregate, the per-direction figure is 25 B/ns; every "
            "CCT relation is linear in 1/B in the bandwidth term, so a reversal "
            "rescales by closed form; the owner adjudicates at integration. Both "
            "readings sit inside the plan §2.1 A-L0-BW anchored span [20, 64]",
            "envelope_effective_bw_degraded": str(B_ENVELOPE),
            "envelope_derivation": "0.7 x 50 = 35 B/ns — the '>30% path-pinning "
            "degradation' mapped onto the free B axis as an EFFECTIVE-bandwidth "
            "displacement (the mechanism itself — congestion/ECMP/QP state — is "
            "outside the L0 input space; see expressiveness)",
            "envelope_implied_pre_improvement_baseline": str(B_ENVELOPE_IMPLIED_BASELINE),
            "implied_baseline_note": "50/1.4 = 250/7 ~ 35.714 B/ns: the effective "
            "bandwidth the pre-E-ECN baseline must have had IF the improved "
            "configuration reaches the 50 line; recorded arithmetic, NOT swept "
            "(non-integer byte rate)",
            "anchor_internal_consistency": "the two envelope quotes are mutually "
            "consistent as opposite readings of one boundary: 1/(1-0.3) = 10/7 "
            "exactly, and (10/7)/1.4 = 50/49 (~2.04% apart) — consistent ONLY IF "
            "their unstated baselines coincide; both quotes are one-sided ('up "
            "to' / 'more than'), never equated",
            "cross_anchor_coincidence_50": "50 B/ns per direction is numerically "
            "identical to CAL-A1's DERIVED NVLink5 per-port per-direction rate "
            "(57.6 Tbps / 72 ports / 2 directions) and to CAL-A5's staged TPU v4 "
            "ICI per-link 50 GB/s (direction convention flagged in the staging "
            "doc) — three fabric classes (scale-out optics, scale-up NVSwitch "
            "port, torus ICI) at the same per-direction byte rate; coincidence "
            "recorded, never cross-derived",
        },
    }


def recorded_ambiguities() -> dict:
    """The FAIL-clause duty: every ambiguity of this anchor, recorded."""
    return {
        "cct_target_series_inextractable": {
            "ambiguity": "the anchor's per-collective (size -> time / throughput) "
            "tables live in the paper PDF and are NOT staged (staging confidence "
            "M-H: the staged numbers were verified from the public blog + "
            "abstract only)",
            "resolution_followed": "per the stage prompt's FAIL clause the "
            "inextractable CCT target is RECORDED and SKIPPED honestly: no CCT "
            "comparison against CAL-A11 is attempted anywhere in this stage; "
            "the extractable axis numbers (link rate, cluster scale, envelope "
            "magnitude) ARE executed as placement — this is also exactly the "
            "plan §1.1 classification ('cannot calibrate O-CCT for scale-up')",
        },
        "optics_rate_direction_convention": {
            "ambiguity": "'400G single-mode optics' does not state per-direction "
            "vs bidirectional aggregate",
            "resolution_followed": "IEEE 802.3 per-direction line-rate reading "
            "(50 B/ns per direction) executed; the 25 B/ns aggregate reading "
            "recorded — both inside the plan's anchored span [20, 64], all "
            "relations rescale by closed form",
        },
        "link_rate_vs_injection_mapping": {
            "ambiguity": "the staged rate is a SWITCH-SWITCH (RTSW-CTSW) link "
            "rate; the model's B is PER-RANK single-port injection; the anchor "
            "stages NO per-GPU NIC bandwidth",
            "resolution_followed": "declared model-side reading 'one rank = one "
            "rail' of the rail-optimized design (per-rank egress rides its "
            "rail's 400G links); recorded as an interpretation, never a "
            "derivation",
        },
        "envelope_baselines_and_metric": {
            "ambiguity": "the '>30%' quote is about TRAINING performance and the "
            "'up to 40%' quote about the AllReduce collective; neither baseline "
            "configuration nor the metric definition is staged",
            "consequence": "the envelope rows locate MAGNITUDE only (asymptotic "
            "CCT ratio 10/7); no causal claim about Meta's configs is made; the "
            "10/7-vs-1.4 consistency check is conditional on shared baselines",
        },
        "under_subscription_direction": {
            "ambiguity": "'1:2 under-subscription vs downlink' does not state "
            "which side of the ratio is which",
            "consequence": "in either direction the fact is STRUCTURAL (a "
            "capacity ratio between tiers) and inexpressible in the non-blocking "
            "single-stage identity — see expressiveness_loss; nothing executed "
            "depends on the direction",
        },
        "scale_out_not_scale_up": {
            "ambiguity": "CAL-A11 is a scale-out fabric used as the plan's UEC-"
            "adjacent context; the plan itself flags (gap §4.1) that no public "
            "UEC measurement study exists, so RoCE-class anchors are proxies, "
            "clearly labeled",
            "consequence": "everything in this record is tagged scale-out "
            "sanity context; no scale-up (UEC/UALink/NVLink-class) conclusion "
            "is drawn from it",
        },
    }


def registry_placements() -> dict:
    axis_ratio = B_REGISTRY / B_ANCHOR          # 32/25
    cct_ratio = B_ANCHOR / B_REGISTRY           # 25/32
    assert axis_ratio == Fraction(32, 25) and cct_ratio == Fraction(25, 32)
    return {
        "A-L0X-BW_point_64_vs_anchor_link_class_50": {
            "axis_ratio": str(axis_ratio),
            "asymptotic_cct_ratio": str(cct_ratio),
            "asymptotic_cct_ratio_float": float(cct_ratio),
            "statement": "the registry point sits 28% ABOVE the anchor's link "
            "class on the bandwidth axis, i.e. 21.875% FASTER in the "
            "bandwidth-bound limit — a placement fact about where the smoke "
            "default sits on the anchor's axis, never a tuning target; the plan "
            "§2.1 A-L0-BW verdict (KEEP point / NARROW range to the anchored "
            "span [20, 64]) is recorded as the plan states it; the registry "
            "value and range are untouched",
        },
        "A-L0-BW_same_arithmetic": {
            "note": "the ring link-bandwidth registry point is numerically the "
            "same 64 B/ns; the ring row of this stage's scale sweep executes at "
            "the ANCHOR point 50 instead (placement on the anchor's own axis)",
        },
        "A-L0X-LAT_A-L0-LAT_anchor_free_here": {
            "note": "CAL-A11 stages NO latency number; L = 200 ns (registry "
            "point) is FIXED and free on every row of this stage — the exact "
            "mirror of stage A9 (that swept L at fixed B, this sweeps B at "
            "fixed L); the latency axis belongs to stages A8/A9/A10",
        },
        "anchored_span_membership": {
            "note": "every executed and recorded B value of this stage — 35 "
            "(envelope), 50 (anchor, declared reading), 64 (registry top), and "
            "the 25 alternative reading — lies inside the plan §2.1 A-L0-BW "
            "candidate anchored span [20, 64] B/ns per link per direction",
        },
    }


def envelope_mapping(sweep_id: str) -> dict:
    """The anchor's congestion/load-balance envelope mapped onto the free B
    axis, with the executed displacement signature at every ladder size."""
    by, _ = _by_cell(sweep_id)
    rows = []
    for m in LADDER_BW:
        t35 = by[("crossbar8_a11_degraded35_v1", m)]
        t50 = by[("crossbar8_a11_link50_v1", m)]
        t64 = by[("crossbar8_a11_registry64_v1", m)]
        # closed-form cross-checks on every executed row
        assert t35 == t_xbar(m, B_ENVELOPE, R_SMOKE)
        assert t50 == t_xbar(m, B_ANCHOR, R_SMOKE)
        assert t64 == t_xbar(m, B_REGISTRY, R_SMOKE)
        rows.append(
            {
                "payload_bytes": m,
                "t_degraded35_exact": str(t35),
                "t_anchor50_exact": str(t50),
                "t_registry64_exact": str(t64),
                "ratio_degraded_vs_anchor_exact": str(t35 / t50),
                "ratio_degraded_vs_anchor_float": float(t35 / t50),
                "ratio_registry_vs_anchor_exact": str(t64 / t50),
                "ratio_registry_vs_anchor_float": float(t64 / t50),
            }
        )
    smallest = rows[0]
    largest = rows[-1]
    # The asymptotes 10/7 and 25/32 are LIMITS (pure 1/B arithmetic); the
    # finite-size ratios approach them monotonically from below/above as the
    # latency term's share shrinks — an exact-Fraction check, no floats.
    for asymptote, row_small, row_large in [
        (Fraction(10, 7), smallest, largest),
        (Fraction(25, 32), smallest, largest),
    ]:
        r_small = Fraction(row_small["ratio_degraded_vs_anchor_exact"]) if asymptote == Fraction(10, 7) else Fraction(row_small["ratio_registry_vs_anchor_exact"])
        r_large = Fraction(row_large["ratio_degraded_vs_anchor_exact"]) if asymptote == Fraction(10, 7) else Fraction(row_large["ratio_registry_vs_anchor_exact"])
        assert abs(r_large - asymptote) < abs(r_small - asymptote)
    return {
        "claim": "the anchor's 30-40% congestion/load-balance envelope, which "
        "the L0 family declares out of scope BY CONSTRUCTION, can enter these "
        "identities ONLY as a displacement of the free B axis; the executed "
        "envelope row (B=35 = 0.7x50) shows the exact signature: CCT ratio "
        "rises from 1.178938 at 8 KiB to the asymptotic EXACT 10/7 = 1.428571 "
        "(+42.86%) at 8 GiB, while the registry row tends to the exact 25/32 = "
        "0.781250 — both pure 1/B arithmetic with the 2L latency term constant",
        "asymptotic_ratios_exact": {
            "degraded35_vs_anchor50": str(B_ANCHOR / B_ENVELOPE),
            "registry64_vs_anchor50": str(B_ANCHOR / B_REGISTRY),
        },
        "ladder_rows_cross_checked": rows,
        "smallest_member_8kib": smallest,
        "largest_member_8gib": largest,
        "input_space_audit": "the crossbar loader reads exactly "
        "{topology_id, ranks, nic.injection_bytes_per_ns, link.pair_latency_ns} "
        "and the ring loader {topology_id, ranks, link.bytes_per_ns, "
        "link.hop_latency_ns} — no path-count / ECMP / queueing / subscription "
        "key exists anywhere in the input space, and BOTH backends list "
        "'congestion' among their explicitly_unsupported capabilities "
        "(CAPABILITIES in src/essun/backends/analytical/l0_crossbar.py and "
        "l0.py); the closed forms above equal every executed row by exact "
        "Fraction string equality, so no load-balancing term can be hiding in "
        "the arithmetic",
    }


def rank_coefficient(sweep_id: str) -> dict:
    """The structural rank-count effect at the anchor's stated scales,
    cross-checked on executed rows (identity arithmetic for r=16,000)."""
    by, _ = _by_cell(sweep_id)
    for m in LADDER_SCALE:
        assert by[(TOPO_XBAR_SCALE, m)] == t_xbar(m, B_ANCHOR, R_CLUSTER)
    c8, c16k, c24k = c_rank(R_SMOKE), c_rank(R_TRAIN), c_rank(R_CLUSTER)
    assert c8 == Fraction(7, 4) and c16k == Fraction(15999, 8000)
    assert c24k == Fraction(24575, 12288)
    assert c24k / c8 == Fraction(8, 7) * Fraction(R_CLUSTER - 1, R_CLUSTER)
    assert c16k / c8 == Fraction(15999, 14000)
    asymptote_gap = Fraction(8, 7) - c24k / c8
    assert asymptote_gap == Fraction(1, 21504)
    return {
        "claim": "at the anchor's stated cluster scale r = 24,576 the bandwidth "
        "coefficient 2(r-1)/r = 24575/12288 sits within 1/21504 (~0.0047%) of "
        "the algebraic asymptote 2, i.e. exactly (8/7)(r-1)/r = 24575/21504 ~ "
        "1.14281 above the r=8 smoke default (7/4); the structural rank-count "
        "effect versus the smoke default is AT MOST +1/7 (~+14.29%) for ANY r, "
        "reached to within 1/r by both anchor scales (r=16,000: 15999/14000 ~ "
        "1.14279, recorded arithmetic; r=24,576 executed) — a ~14% structural "
        "scale effect and the anchor's 30-40% congestion envelope are the same "
        "order of magnitude and are INSEPARABLE in a raw scale-out CCT "
        "measurement read through an L0 lens",
        "coefficient_values_exact": {
            "c(8)": str(c8),
            "c(16000)": str(c16k),
            "c(24576)": str(c24k),
        },
        "ratios_vs_smoke_default_exact": {
            "c(16000)/c(8)": str(c16k / c8),
            "c(24576)/c(8)": str(c24k / c8),
            "asymptote_8/7": str(Fraction(8, 7)),
            "gap_at_24576": str(asymptote_gap),
        },
        "exact_form": "c(r)/c(8) = (8/7)*(r-1)/r for every r — verified as an "
        "identity and cross-checked on the 15 executed r=24,576 rows (closed "
        "form equals every row by exact Fraction string equality)",
        "ceiling_row_honesty": "the r=24,576 crossbar row is the NON-BLOCKING "
        "single-stage CEILING abstraction of the anchor's two-tier subscribed "
        "spine-leaf (the role CAL-A1/A2 spec ceilings play), never a prediction "
        "of Meta's fabric; the anchor stages no per-collective time series, so "
        "no CCT comparison is attempted",
    }


def schedule_contrast(sweep_id: str) -> dict:
    """The multi-hop schedule contrast at the anchor's scale: schedule
    structure alone moves CCT far beyond the congestion envelope."""
    by, _ = _by_cell(sweep_id)
    chain = 2 * (R_CLUSTER - 1) * L_REGISTRY
    diff_const = 2 * (R_CLUSTER - 2) * L_REGISTRY
    assert chain == 9830000 and diff_const == 9829600
    rows = []
    for m in LADDER_SCALE:
        tx = by[(TOPO_XBAR_SCALE, m)]
        tr = by[(TOPO_RING_SCALE, m)]
        assert tx == t_xbar(m, B_ANCHOR, R_CLUSTER)
        assert tr == t_ring(m, B_ANCHOR, R_CLUSTER)
        assert tr - tx == diff_const, (m, tr - tx)  # identity at every size
        rows.append(
            {
                "payload_bytes": m,
                "xbar_cct_ns_exact": str(tx),
                "ring_cct_ns_exact": str(tr),
                "difference_ns_exact": str(tr - tx),
                "ratio_exact": str(tr / tx),
                "ratio_float": float(tr / tx),
            }
        )
    crossover = L_REGISTRY * B_ANCHOR * R_CLUSTER  # 245,760,000 B
    assert crossover == 245760000
    below = by[(TOPO_XBAR_SCALE, 201326592)]
    r_below = by[(TOPO_RING_SCALE, 201326592)] / below
    above = by[(TOPO_XBAR_SCALE, 402653184)]
    r_above = by[(TOPO_RING_SCALE, 402653184)] / above
    smallest = rows[0]
    return {
        "claim": "at the SAME scale, link class, and B, the multi-hop ring "
        "schedule charges the per-hop latency 2*(r-1) = 49,150 times per "
        "AllReduce (latency chain exactly 9,830,000 ns = 9.83 ms) against the "
        "crossbar ceiling's 2; the ring-minus-crossbar difference is EXACTLY "
        "2*(r-2)*L = 9,829,600 ns at every one of the 15 executed sizes. "
        "Across the ladder members bracketing the exact crossover "
        "M* = L*B*r = 245,760,000 B (234.375 MiB) the ring/crossbar CCT ratio "
        "is 1117671/503321 ~ 2.221 (192 MiB, latency-dominant side) and "
        "1620967/1006617 ~ 1.610 (384 MiB, bandwidth-dominant side) — SCHEDULE "
        "STRUCTURE ALONE, an in-model choice with no congestion, moves CCT by "
        "factors of 1.6-2.2+ (7108x at the 24 KiB member), i.e. beyond the "
        "anchor's 30-40% envelope by multiples",
        "latency_chain_ns_exact": str(chain),
        "difference_identity_ns_exact": str(diff_const),
        "crossover_bytes_exact": str(crossover),
        "crossover_float_mib": float(crossover / 2**20),
        "bracketing_members": {
            "below_192mib_ratio_exact": str(r_below),
            "below_192mib_ratio_float": float(r_below),
            "above_384mib_ratio_exact": str(r_above),
            "above_384mib_ratio_float": float(r_above),
        },
        "ladder_rows_cross_checked": rows,
        "smallest_member_24kib": smallest,
        "no_schedule_claim": "no schedule is claimed to be THE Meta behavior — "
        "the anchor's per-collective tables are unstaged; the ring row exists "
        "to bracket schedule-structure magnitude at the anchor's own scale and "
        "link class (the scale-side analog of stage A9's chain-multiplicity "
        "contrast)",
    }


def confounder_separation() -> dict:
    """The stage's central sanity conclusion, assembled from the executed
    numbers above (anchor-anchor and anchor-registry arithmetic only)."""
    return {
        "role": "the sanity context the calibration plan §1.1 assigns to "
        "CAL-A11: 'Secondary sanity context for exactly the effects L0 "
        "declares out of scope (congestion, load balancing)'",
        "three_confounders": {
            "congestion_load_balance_state_out_of_model": {
                "magnitude": "30-40% production swing (anchor quotes); mapped "
                "on-model as effective-B [35, 50] -> asymptotic CCT factor "
                "10/7 ~ 1.4286",
                "status": "STRUCTURALLY OUT OF SCOPE: no input key, capability-"
                "declared unsupported; visible only as free-scalar displacement",
            },
            "schedule_structure_in_model": {
                "magnitude": "executed ring-vs-crossbar at the anchor's scale: "
                "1.61x (384 MiB) to 2.22x (192 MiB), 7108x at 24 KiB; exact "
                "difference 9,829,600 ns at every size",
                "status": "fully in-model (identity choice), so a raw CCT "
                "comparison MUST pin the schedule before reading anything "
                "else into a delta",
            },
            "rank_count_structure_in_model": {
                "magnitude": "exactly (8/7)(r-1)/r vs the r=8 default: at most "
                "+1/7 ~ +14.29% for ANY r; ~+14.28% at both anchor scales",
                "status": "fully in-model (identity coefficient); confusable "
                "with a fraction of the congestion envelope in raw readings",
            },
        },
        "dominance_over_noise_floors": "the 10/7 envelope factor (+42.86%) "
        "exceeds CAL-A4's ~5% validated error band by ~8.6x and CAL-A6's "
        "5-8% software-version noise floor by ~5.4-8.6x; schedule structure "
        "(1.61-2.22x at bracketing sizes) exceeds it again by ~1.1-1.6x; rank "
        "count (+14.3%) sits at ~1/3 of it — all three are at or above every "
        "other uncertainty in the ladder",
        "conclusion": "any comparison of an L0-family output against a "
        "scale-out measurement (CAL-A6/A11-class, i.e. every labeled "
        "UEC-proxy per plan gap §4.1) must pin THREE states — schedule, rank "
        "scale, and congestion/load-balancing configuration — before a "
        "residual can be attributed to anything calibratable; the anchor's "
        "own 30-40% envelope alone would swamp a CAL-A4-shaped 5% tolerance "
        "several times over",
    }


def expressiveness_loss() -> dict:
    """What the L0 input space cannot express against this anchor's fabric
    structure (anchor-registry arithmetic; no run ids by construction)."""
    return {
        "role": "quantifies what the L0 input space loses against CAL-A11's "
        "fabric structure (a subscribed, rail-optimized, multi-plane, "
        "congestible two-tier fabric)",
        "congestion_load_balancing": "no ECMP/path-count/queueing/QP key "
        "exists in any loader surface; both L0 backends list 'congestion' "
        "among explicitly_unsupported capabilities — the anchor's headline "
        "mechanisms (path pinning, E-ECN, QP scaling) are not unswept, they "
        "are INEXPRESSIBLE; the only in-model trace is the free-scalar B "
        "displacement this stage executes",
        "subscription_ratio": "the 1:2 under-subscription (direction "
        "ambiguous, recorded) is a TIER-TO-TIER capacity ratio: in the "
        "non-blocking identity per-pair available bandwidth is independent "
        "of every other pair's traffic — which is exactly the no-congestion "
        "abstraction — so a subscribed fabric's load-dependent capacity has "
        "no input; the executed r=24,576 row is therefore a CEILING row",
        "rail_plane_structure": "rail-optimized multi-plane topology classes "
        "(per-rail groups, plane count) have no topology_class in the landed "
        "set {unidirectional_ring, fully_connected_crossbar, "
        "fully_connected_exchange, torus2d_ring_x_ring}; modeling them is an "
        "owner design decision for a future scale-out-profile backend (the "
        "plan's uet-htsim third backend is the natural home for congestion "
        "and load balancing)",
        "consequence_for_calibration": "per plan §1.1 this anchor can never "
        "calibrate the L0 family's O-CCT — not because numbers are missing "
        "but because the effects it measures live outside the family's "
        "declared validity domain; its calibrated use is as the SANITY "
        "BRACKET on any future scale-out-proxy comparison (and, at owner "
        "discretion, as the target for the packet-level backend family)",
        "provenance": "anchor-staging structure plus the backends' declared "
        "capability lists and loader surfaces (declared interpretation; the "
        "executed displacement signature is in envelope_mapping above)",
    }


def main() -> int:
    derived = anchor_derived()

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "calibration record, A11 (anchor CAL-A11)",
        "anchor": {
            "anchor_id": "CAL-A11",
            "title": "Meta SIGCOMM 2024: RoCE network for distributed AI training (UEC-adjacent)",
            "source_row": "the anchor registry row CAL-A11 (PROPOSED; history-only since D-035)",
            "staging_doc": "docs/calibration/anchors_staging.md §A11",
            "plan_row": "docs/calibration/CALIBRATION_PLAN.md §1.1 row CAL-A11",
            "urls": [
                "https://engineering.fb.com/wp-content/uploads/2024/08/sigcomm24-final246.pdf",
                "https://engineering.fb.com/2024/08/05/data-center-engineering/roce-network-distributed-ai-training-at-scale/",
            ],
            "confidence": "M-H — production measurements, but verified from the "
            "public blog + abstract; the per-collective throughput tables live "
            "in the paper PDF and are NOT staged (recorded ambiguity, FAIL-"
            "clause duty)",
            "staged_numbers": "400G single-mode optics RTSW-CTSW; 1:2 "
            "under-subscription (direction ambiguous); path-pinning degraded "
            "training 'up to more than 30%'; E-ECN + QP scaling 'up to 40% "
            "improvement for the AllReduce collective'; two ~24,576-GPU "
            "clusters; Llama 3 on 16,000 GPUs — numbers as staged in "
            "anchors_staging.md §A11 (no verbatim quote strings claimed)",
        },
        "target": {
            "role": "scale_out_congestion_load_balance_sanity_context",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "CAL-A11 is a SCALE-OUT "
            "rail-optimized RoCE fabric, not a GPU-to-GPU scale-up fabric; per "
            "CALIBRATION_PLAN.md §1.1: 'Cannot calibrate O-CCT for scale-up — "
            "a scale-out rail-optimized RoCE fabric... Secondary sanity "
            "context for exactly the effects L0 declares out of scope "
            "(congestion, load balancing).' The staged (size -> time) tables "
            "are inextractable (paper PDF, unstaged) — recorded and skipped "
            "honestly; the extractable targets — link class 50 B/ns per "
            "direction (declared reading), cluster scale r=24,576, envelope "
            "magnitude 30-40% — are executed here as placement",
            "regime": {
                "topology_class": "scale-out spine-leaf (rail-optimized, "
                "multi-plane, RoCEv2); executed on the landed NON-BLOCKING "
                "single-switch-stage abstraction (fully_connected_crossbar) as "
                "a ceiling row, plus one multi-hop ring row as the "
                "schedule-structure contrast",
                "ranks": {
                    "executed": [R_SMOKE, R_CLUSTER],
                    "provenance": "r=8 free smoke default for the B-axis sweep; "
                    "r=24,576 the anchor's STATED cluster scale (largest rank "
                    "count any anchor pins) for the scale sweep; r=16,000 (the "
                    "stated Llama-3 training scale) recorded as identity "
                    "arithmetic — c(16000)/c(8) = 15999/14000, within 0.006% "
                    "of the executed 24576 row's coefficient",
                },
                "message_bytes_ladders": {
                    "bw_sweep": LADDER_BW,
                    "scale_sweep": LADDER_SCALE,
                },
                "message_regime_note": "the plan's regime entry for CAL-A11 is "
                "'large' — the store runs execute at the bandwidth-bound 8 GiB "
                "ladder member; the scale ladder 24576*2^k brackets the exact "
                "ring crossover 245,760,000 B with executed rows on both sides",
            },
        },
        "anchor_derived": derived,
        "recorded_ambiguities": recorded_ambiguities(),
        "registry_placements": registry_placements(),
        "model": {
            "backends_executed": [
                "analytical_l0_crossbar (B-axis placement rows at r=8; "
                "anchor-scale ceiling row at r=24,576)",
                "analytical_l0 (ring; one row at r=24,576 — the "
                "schedule-structure contrast at the anchor's scale and link "
                "class)",
            ],
            "identities": {
                "crossbar": "t = 2(r-1)/r*M/B + 2L ; L=200 fixed free, B in "
                "{35, 50, 64} at r=8; B=50, r=24,576 on the scale sweep",
                "ring": "t = 2(r-1)/r*M/B + 2(r-1)*L ; B=50, L=200, r=24,576",
            },
            "free_parameters": {
                "B_injection_swept_ns": {
                    "50": "CAL-A11 400 Gbps optics per direction per link under "
                    "the declared decimal + IEEE per-direction reading — THE "
                    "ANCHOR POINT and both sweeps' baseline (25 B/ns aggregate "
                    "alternative recorded, not swept)",
                    "35": "0.7 x 50 — the '>30% path-pinning degradation' "
                    "mapped onto the free B axis (effective-bandwidth envelope "
                    "row; mechanism out of model scope, magnitude located, "
                    "never tuned)",
                    "64": "A-L0X-BW / A-L0-BW registry point (placement row; "
                    "asymptotic CCT ratio exactly 25/32)",
                },
                "L_pair_and_hop_ns": {
                    "200": "A-L0X-LAT / A-L0-LAT registry point, FIXED and free "
                    "— CAL-A11 stages no latency number (the mirror of stage "
                    "A9: that swept L at fixed B, this sweeps B at fixed L)",
                },
                "ranks": {
                    "8": "free smoke default (B-axis sweep; divides every "
                    "8*2^k ladder size)",
                    "24576": "the anchor's stated cluster scale (scale sweep; "
                    "every grid size 24576*2^k divides exactly)",
                },
            },
            "assumptions": "A-L0X-PORT/A-L0X-BW/A-L0X-LAT/A-L0X-DIV (crossbar); A-L0-BW/A-L0-LAT/A-L0-FD/A-L0-DIV (ring) — all from experiments/vertical_slice/assumptions_l0.yaml",
        },
        "comparison": {
            "anchor_point_runs": [
                run_summary(
                    RUN_ID_XBAR_ANCHOR50,
                    "anchor point (B=50 B/ns = CAL-A11 400 Gbps optics per direction, declared reading; bandwidth-bound 8 GiB ladder member)",
                ),
                run_summary(
                    RUN_ID_XBAR_REG64,
                    "registry point (B=64 B/ns = A-L0X-BW smoke default; the SAME payload isolates the bandwidth axis: asymptotic CCT ratio exactly 25/32 = 0.78125)",
                ),
            ],
            "run_pair_placement": {
                "cct_ratio_registry_vs_anchor_exact": "367002225/469762673",
                "cct_ratio_registry_vs_anchor_float": 0.7812502910379173,
                "cct_delta_registry_minus_anchor_ns_exact": "-1644167168/25",
                "cct_delta_registry_minus_anchor_ns_float": -65766686.72,
                "statement": "at the 8 GiB member the executed pair sits within "
                "3e-7 of the asymptotic exact 25/32 (latency fraction of CCT "
                "~1.3e-6 — the pure bandwidth regime); the registry default is "
                "21.875% faster than the anchor's link class in the "
                "bandwidth-bound limit — placement arithmetic, never a tuning "
                "target",
            },
            "reconciled_sweep_bw": sweep_rows(SWEEP_ID_BW, "ladder"),
            "envelope_mapping": envelope_mapping(SWEEP_ID_BW),
            "reconciled_sweep_scale": sweep_rows(SWEEP_ID_SCALE, "ladder"),
            "rank_coefficient": rank_coefficient(SWEEP_ID_SCALE),
            "schedule_contrast": schedule_contrast(SWEEP_ID_SCALE),
            "confounder_separation": confounder_separation(),
            "expressiveness_loss": expressiveness_loss(),
        },
        "deviation": {
            "cct_deviation_vs_anchor": "UNDEFINED BY CONSTRUCTION — CAL-A11 "
            "stages no per-collective (size -> time) series (its tables live "
            "in the paper PDF); per the stage prompt's FAIL clause the "
            "inextractable target is recorded and skipped honestly, and per "
            "plan §1.1 the anchor cannot calibrate scale-up O-CCT at all — "
            "recorded instead of skipped because the anchor's actual assigned "
            "role (sanity context for congestion/load-balancing effects) IS "
            "executable and is executed above",
            "placement_summary": "the model's bandwidth axis: anchor link "
            "class 50 B/ns per direction (declared reading; 25 alternative "
            "recorded), registry point 64 sits 28% above it on the axis "
            "(asymptotic CCT ratio exactly 25/32), and the anchor's 30-40% "
            "congestion envelope maps to effective-B [35, 50] (asymptotic CCT "
            "factor exactly 10/7, = 1/(1-0.3), consistent with the 'up to 40%' "
            "quote within 50/49 conditional on shared baselines); the anchor's "
            "cluster scale r=24,576 is executed as a non-blocking ceiling row "
            "(coefficient within 0.005% of the asymptote 2; exactly "
            "(8/7)(r-1)/r above the r=8 default), and the multi-hop ring "
            "contrast at the same scale moves CCT by exact differences of "
            "9,829,600 ns (identities), i.e. factors 1.61-2.22 at the "
            "crossover-bracketing sizes — schedule, scale, and congestion "
            "state are three separable confounders each at or above every "
            "noise floor in the anchor set",
            "span_placement": "executed and recorded B values {25 (recorded), "
            "35, 50, 64} all lie inside the plan §2.1 A-L0-BW candidate "
            "anchored span [20, 64] B/ns per link per direction; the latency "
            "axis is anchor-free here (L=200 registry, fixed)",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, content-addressed, replay-verified byte-identical)",
            "candidate": "PROPOSED calibration candidate targeting the "
            "scale-out sanity-context role; no E3/E4 language — CAL-A11 is an "
            "external published production measurement in the WRONG domain "
            "(scale-out), used per plan §1.1 as labeled context only",
        },
        "backing": {
            "run_ids": [RUN_ID_XBAR_ANCHOR50, RUN_ID_XBAR_REG64],
            "sweep_ids": [SWEEP_ID_BW, SWEEP_ID_SCALE],
            "sweep_dirs": [f"results/sweeps/{SWEEP_ID_BW}", f"results/sweeps/{SWEEP_ID_SCALE}"],
            "run_backed_numbers": "every model output in "
            "comparison.anchor_point_runs, comparison.reconciled_sweep_bw and "
            "comparison.reconciled_sweep_scale; comparison.envelope_mapping, "
            "comparison.rank_coefficient and comparison.schedule_contrast "
            "cross-check closed forms against those executed rows by exact "
            "Fraction string equality (declared inline); "
            "comparison.run_pair_placement, confounder_separation and "
            "expressiveness_loss are identity/anchor-registry arithmetic "
            "declared inline (the r=16,000 coefficient row is recorded "
            "arithmetic, not executed)",
            "inputs": [
                "experiments/calibration/a11/sweep_a11_link_bw_v1.yaml",
                "experiments/calibration/a11/sweep_a11_scale24576_v1.yaml",
                "experiments/calibration/a11/run_a11_anchor50_v1.yaml",
                "experiments/calibration/a11/run_a11_registry64_v1.yaml",
                "experiments/calibration/a11/workloads/ (2 files)",
                "experiments/calibration/a11/topologies/ (5 files)",
                "experiments/calibration/a11/profiles/ (2 files)",
            ],
            "reproduce": "make run EXP=experiments/calibration/a11/run_a11_anchor50_v1.yaml ; "
            "make run EXP=experiments/calibration/a11/run_a11_registry64_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a11/sweep_a11_link_bw_v1.yaml ; "
            "make sweep EXP=experiments/calibration/a11/sweep_a11_scale24576_v1.yaml ; "
            "python experiments/calibration/a11/build_calibration_record.py",
        },
    }

    # Exact-value self-checks on the executed run pair (transcription guards).
    obs50 = load_json(RESULTS / RUN_ID_XBAR_ANCHOR50 / "observations.json")
    obs64 = load_json(RESULTS / RUN_ID_XBAR_REG64 / "observations.json")
    t50 = Fraction(obs50["per_op"][0]["completion_time_ns_exact"])
    t64 = Fraction(obs64["per_op"][0]["completion_time_ns_exact"])
    assert t50 == t_xbar(RUN_PAYLOAD, B_ANCHOR, R_SMOKE)
    assert t64 == t_xbar(RUN_PAYLOAD, B_REGISTRY, R_SMOKE)
    assert t64 / t50 == Fraction(367002225, 469762673)
    assert t64 - t50 == Fraction(-1644167168, 25)

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
