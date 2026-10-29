"""Build the PROPOSED cross-class synthesis record for parameter class
SERIALIZATION RATE (Q1 calibration-ladder GLOBAL stage GLOB-SER, the
FOURTH and FINAL of the four global parameter-class stages.
docs/calibration/CALIBRATION_PLAN.md).

Why this stage is a synthesis, not a fourth sweep (the duplication
finding, established live below): the prompt's ladder names four
parameter classes — link BW, hop/pair latency, injection BW,
serialization rate — but on the registry and the backend the THIRD and
FOURTH names resolve onto ONE registered numeric axis. The L0.5
registry's own A-L05-INJ rationale names the parameter "the per-chunk
serialization (injection) rate I": one registered free parameter
(nic.injection_bytes_per_ns, range [1, 1024]) carrying both class
names. Global stage GLOB-INJ already executed exactly that axis across
its full registered range plus the I -> infinity null encoding
(sweep 0051d0c8…, 15 rows). The only registered parameter UNIQUE to
the serialization-rate class is A-L05-SER (model.
per_transfer_service_time) — an ENUMERATED IDENTITY CHOICE, not a
numeric rate, and one with NO executable surface: the L0.5 loader
reads no such key, all three registered enum values execute
byte-identically (the identity is the code, not an input), and the two
alternatives are declared in the backend's explicitly_unsupported
capabilities. Sweeping it would mean IMPLEMENTING new model identities
(relay re-serialization, overlapped transfers) — a capability-gated
step, never a sensitivity stage. The stage therefore does NOT
re-run the numeric axis and instead consolidates the three executed
global stages' sensitivity constants into the parameter-class
sensitivity table the plan asked for.

Pure function of immutable artifacts: the three landed global stages'
sweep tables, endpoint store runs, and content-addressed records, plus
live re-execution of the no-surface facts (module-direct, deterministic
analytical executions only — no new parameter points, no new store
runs, nothing tuned). Every derived fraction is recomputed with exact
Fractions and asserted; the record is content-addressed (record_id =
SHA-256 of the canonical record; append-only — different bytes under
an existing id is an error, identical bytes are idempotent).

Status of everything this script writes: PROPOSED — owner adjudication
required; no claim or label is changed anywhere by this stage.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from fractions import Fraction
from pathlib import Path

import yaml

from essun.contracts import REPO_ROOT
from essun.evidence.store import canonical_json

RESULTS = REPO_ROOT / "results"

# ---------------------------------------------------------------------------
# Stage artifacts — every id LOADED from the landed sibling builders
# (imported, never re-typed hex), then verified on disk.
# ---------------------------------------------------------------------------
CAL = REPO_ROOT / "experiments" / "calibration"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BW = _load(CAL / "globbw" / "build_calibration_record.py", "globbw_consts")
LAT = _load(CAL / "globlat" / "build_calibration_record.py", "globlat_consts")
INJ = _load(CAL / "globinj" / "build_calibration_record.py", "globinj_consts")

SWEEP_GLOBBW = BW.SWEEP_ID
SWEEP_GLOBLAT = LAT.SWEEP_ID
SWEEP_GLOBINJ = INJ.SWEEP_ID
RUN_B1, RUN_B1024 = BW.RUN_ID_B1, BW.RUN_ID_B1024
RUN_L10, RUN_L2000 = LAT.RUN_ID_L10, LAT.RUN_ID_L2000
RUN_I1, RUN_I1024 = INJ.RUN_ID_I1, INJ.RUN_ID_I1024
RUN_SMOKE = BW.RUN_ID_SMOKE_TWIN  # == LAT's == INJ's (asserted below)
assert BW.RUN_ID_SMOKE_TWIN == LAT.RUN_ID_SMOKE_TWIN == INJ.RUN_ID_SMOKE_TWIN

# The three landed stages' content-addressed records (transcribed from
# their reports; existence + stage field verified at build time).
RECORD_GLOBBW = "c74263577a330633c2248e9d85bed111a49e2c1108fe9911714762ad3e272591"
RECORD_GLOBLAT = "049cdfebd6d7d93858999befee205c636e93bb5ec1cef1f2c06cd39ee30745ca"
RECORD_GLOBINJ = "cfca2f45c9117e91b633d7440b45d3234658f6be50311d0439d80266fa3fcb59"

# The W1 smoke configuration, verbatim (identical in all three stages).
R = 8
M = 16384
OPS = 6
B = Fraction(64)    # A-L0-BW / A-L05-BW registry point
L = Fraction(200)   # A-L0-LAT / A-L05-LAT registry point
I_REG = Fraction(64)  # A-L05-INJ registry point

# Exact closed forms shared by the three executed axes.
WIRE = Fraction(2 * (R - 1) * M, R)      # 28672 B per rank per op
BW_TERM = WIRE / B                       # 448 ns (the ring's bandwidth term at B=64)
LAT_CHAIN = 2 * (R - 1) * L              # 2800 ns (the 14L latency chain)
L0_CCT = BW_TERM + LAT_CHAIN             # 3248 ns (the landed L0 identity)
SER_COEF = WIRE                          # 28672 (serialization coefficient)
L05_BASE = L0_CCT + SER_COEF / I_REG     # 3696 ns (the L0.5 smoke point)
TOTAL_WIRE = OPS * 2 * (R - 1) * M       # 1376256 B per config


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sweep_row(sweep_id: str, tag: str) -> dict:
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    for row in table["configs"]:
        if f"_{tag}_" in row["config_id"]:
            return row
    raise AssertionError(f"row {tag} not found in sweep {sweep_id}")


def sweep_facts(
    sweep_id: str,
    sweep_name: str,
    n_configs: int,
    closed_form,          # callable(value) -> Fraction (None-safe for limits)
    base_cct: Fraction,   # the axis's registry-point CCT (delta baseline)
    ladder_tags: list[str],
    endpoints: dict,      # tag -> expected exact CCT string
    deltas: dict,         # tag -> expected exact delta string
    value_of,             # callable(row) -> Fraction | None (None = limit row)
) -> dict:
    """Load one landed global sweep, assert every closed form, return facts."""
    table = load_json(RESULTS / "sweeps" / sweep_id / "table.json")
    assert table["sweep"] == sweep_name
    assert len(table["configs"]) == n_configs
    for row in table["configs"]:
        v = value_of(row)
        if v is None:  # an out-of-range limit row (only the I axis has one)
            continue
        cct = Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
        assert cct == closed_form(v), (row["config_id"], cct)
        assert Fraction(row["per_rank_wire_bytes_exact"]) == WIRE
        assert row["o_conservation"]["violations"] == 0
        assert Fraction(row["o_conservation"]["total_wire_bytes_exact"]) == TOTAL_WIRE
        assert row["payload_bytes"] == M and row["ops"] == OPS
        # The delta column recomputed independently: (cct - baseline)/baseline.
        d = Fraction(row["delta_vs_baseline"]["delta_exact"])
        assert d == (cct - base_cct) / base_cct, (row["config_id"], d)
    for tag, want_cct in endpoints.items():
        row = sweep_row(sweep_id, tag)
        assert row["o_cct"]["completion_time_ns_mean_exact"] == want_cct, (tag, row)
        assert row["delta_vs_baseline"]["delta_exact"] == deltas[tag], (tag, row)
    return {
        "sweep_id": sweep_id,
        "sweep_name": sweep_name,
        "rows": n_configs,
        "ladder_tags": ladder_tags,
        "sweep_dir": f"results/sweeps/{sweep_id}",
    }


def endpoint_run(run_id: str, want_cct: str) -> dict:
    obs = load_json(RESULTS / run_id / "observations.json")
    run = load_json(RESULTS / run_id / "run.json")
    cct = obs["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
    assert cct == want_cct, (run_id, cct)
    assert obs["observables"]["O-CONSERVATION"]["violations"] == 0
    assert Fraction(obs["observables"]["O-CONSERVATION"]["total_wire_bytes_exact"]) == TOTAL_WIRE
    assert all(Fraction(p["per_rank_wire_bytes_exact"]) == WIRE for p in obs["per_op"])
    assert len(obs["per_op"]) == OPS
    return {
        "run_id": run_id,
        "experiment_id": run["manifest"]["experiment_id"],
        "cct_ns_exact": cct,
    }


# ---------------------------------------------------------------------------
# The serialization-rate class resolution — live facts, no transcription.
# ---------------------------------------------------------------------------


def axis_resolution_facts() -> dict:
    from essun.backends.analytical import l05

    # Registry texts (the axis-name duplication is IN the registry itself).
    reg05 = yaml.safe_load((CAL.parent / "vertical_slice" / "assumptions_l05.yaml").read_text())
    rows = {a["id"]: a for a in reg05["assumptions"]}
    ser = rows["A-L05-SER"]
    inj = rows["A-L05-INJ"]
    assert ser["parameter"] == "model.per_transfer_service_time"
    assert ser["value"] == "serialize_push_latency_per_transfer"
    assert ser["range"] == [
        "serialize_push_latency_per_transfer",
        "relay_re_serialization",
        "overlapped_chunk_transfers",
    ]
    assert "serialization (injection) rate" in inj["rationale"]
    reg0 = yaml.safe_load((CAL.parent / "vertical_slice" / "assumptions_l0.yaml").read_text())
    assert all(a["parameter"] != "model.per_transfer_service_time" for a in reg0["assumptions"])

    # Backend declarations: the two alternative identities are unsupported.
    unsup = l05.CAPABILITIES["explicitly_unsupported"]
    assert "relay_re_serialization" in unsup and "overlapped_chunk_transfers" in unsup

    # The enum has NO input surface: injecting any registered value into a
    # topology executes byte-identically (the identity is the code).
    topo_path = REPO_ROOT / "experiments" / "topologies" / "ring8_l05_free_params.yaml"
    base = yaml.safe_load(topo_path.read_text())
    assert "model" not in base
    assert Fraction(str(base["nic"]["injection_bytes_per_ns"])) == I_REG

    class Op:
        def __init__(self, oid: str):
            self.op_id = oid
            self.collective = "allreduce"
            self.comm_ranks = list(range(R))
            self.payload_bytes = M

    ops = [Op(f"op{k}") for k in range(OPS)]
    outs = {}
    for enum_val in ser["range"]:
        d = copy.deepcopy(base)
        d["model"] = {"per_transfer_service_time": enum_val}
        out = l05.execute(ops, l05.load_l05_config(d))
        outs[enum_val] = json.dumps(out, sort_keys=True)
    assert len(set(outs.values())) == 1
    common = json.loads(next(iter(outs.values())))
    cct = common["observables"]["O-CCT"]["completion_time_ns_mean_exact"]
    assert cct == str(L05_BASE)  # 3696 — the shipped L0.5 smoke point
    # …and that executed point IS the landed GLOB-INJ baseline row (the
    # numeric axis this class collapses onto was already executed there).
    assert sweep_row(SWEEP_GLOBINJ, "i64")["o_cct"]["completion_time_ns_mean_exact"] == cct

    # Plan provenance: the plan's tables predate the L0.5 registry split
    # (D-031) and define no serialization-rate numeric axis of their own;
    # the four-class list lives in the ladder prompt.
    plan = (REPO_ROOT / "docs" / "calibration" / "CALIBRATION_PLAN.md").read_text()
    assert "A-L05" not in plan and "per_transfer_service_time" not in plan
    prompt = (
        REPO_ROOT / "docs" / "away" / "2026-10-28-" / "prompts" / "p1_calibration.md"
    ).read_text()
    assert "link BW, hop/pair latency, injection BW, serialization rate" in prompt

    return {
        "class_name_source": "the calibration prompt "
        "(the four global parameter classes: link BW, hop/pair latency, "
        "injection BW, serialization rate)",
        "numeric_axis": {
            "registry_id": "A-L05-INJ",
            "parameter": "nic.injection_bytes_per_ns",
            "registry_text": "the A-L05-INJ rationale names the parameter "
            "'the per-chunk serialization (injection) rate I' — ONE "
            "registered numeric free parameter carrying BOTH class names "
            "(injection bandwidth and serialization rate are the same "
            "physical axis: the rate at which the transmitting NIC "
            "serializes bytes onto the fabric)",
            "registered_range": ["1", "1024"],
            "already_executed_by": "GLOB-INJ (stage 3 of 4): sweep "
            f"{SWEEP_GLOBINJ}, 15 rows = the 14 registered-range points "
            "plus the I -> infinity null encoding — NOT re-run here",
        },
        "identity_entry": {
            "registry_id": "A-L05-SER",
            "parameter": "model.per_transfer_service_time",
            "registered_range": ser["range"],
            "value": ser["value"],
            "kind": "enumerated identity choice (unit: none) — NOT a "
            "numeric rate; the class's only registry entry that is not "
            "the A-L05-INJ axis",
            "executable_surface": "NONE — verified live at build time: "
            "(1) the L0.5 loader (load_l05_config) reads no such key; "
            "(2) topologies carrying each of the three registered enum "
            "values under model.per_transfer_service_time execute "
            f"BYTE-IDENTICALLY (common O-CCT {cct} ns, JSON-equal "
            "observations) — the identity is the code, not an input; "
            "(3) both alternatives appear verbatim in the backend's "
            "CAPABILITIES['explicitly_unsupported'] "
            "(relay_re_serialization, overlapped_chunk_transfers); "
            "(4) the registry's own A-L05-SER rationale declares the "
            "alternatives unsupported and notes the relay reading fails "
            "the pre-registered convergence bar",
            "consequence": "sweeping the identity enum would require "
            "IMPLEMENTING new model identities (relay re-serialization, "
            "overlapped fill+drain transfers) — a capability-gated "
            "step per the GLOB-INJ precedent, never a sensitivity "
            "stage; this stage records the fact instead",
        },
        "plan_provenance": "CALIBRATION_PLAN.md section 2.1 predates the "
        "L0.5 registry split (D-031): it contains no A-L05 row and no "
        "per_transfer_service_type parameter — the plan defines no "
        "serialization-rate numeric axis distinct from "
        "nic.injection_bytes_per_ns (its only 'serial*' strings are the "
        "L0 family's structural KEEP identities: "
        "serialized_single_partner_steps / serialized_rs_then_ag / "
        "serialized_rs_ag_chain)",
        "duplication_statement": "the ladder's four class names resolve "
        "onto THREE executed numeric axes plus ONE identity declaration: "
        "link BW -> A-L0-BW (GLOB-BW), hop/pair latency -> A-L0-LAT "
        "(GLOB-LAT), injection BW and serialization rate -> the single "
        "axis A-L05-INJ (GLOB-INJ executed it once; this stage does not "
        "re-run it), identity enum A-L05-SER -> no executable surface. "
        "Recorded as a finding for the owner's adjudication of the "
        "ladder's class list; no registry text is changed.",
    }


# ---------------------------------------------------------------------------
# The three executed axes, re-verified from their landed artifacts.
# ---------------------------------------------------------------------------


def executed_axes() -> tuple[dict, dict, dict]:
    # --- GLOB-BW: t(B) = 28672/B + 2800 on [1, 1024], point 64 ---
    t_bw = lambda b: WIRE / b + LAT_CHAIN
    b_low, b_high, b_base = Fraction(31472), Fraction(2828), Fraction(3248)
    bw = sweep_facts(
        SWEEP_GLOBBW, "cal_globbw_v1", 14, t_bw, b_base,
        ["b1", "b2", "b4", "b8", "b16", "b20", "b25", "b32", "b50", "b64", "b128", "b256", "b512", "b1024"],
        {"b1": "31472", "b64": "3248", "b1024": "2828"},
        {"b1": "252/29", "b64": "0", "b1024": "-15/116"},
        lambda row: Fraction(row["config_id"].split("globbw_b")[1].split("_")[0]),
    )
    e_bw = (WIRE / B) / b_base                     # 448/3248 = 4/29
    assert e_bw == Fraction(4, 29)
    asym_bw = abs(Fraction(252, 29) / Fraction(-15, 116))   # 336/5
    assert asym_bw == Fraction(336, 5)
    b_star = WIRE / LAT_CHAIN                      # 28672/2800 = 256/25
    assert b_star == Fraction(256, 25)
    bw_axis = {
        "class": "link bandwidth",
        "registry_id": "A-L0-BW",
        "parameter": "link.bytes_per_ns",
        "backend": "analytical_l0 (ring)",
        "registered_range": ["1", "1024"],
        "registry_point": "64",
        "closed_form": "t(B) = 28672/B + 2800 ns",
        "cct_at_endpoints": {"1": "31472", "1024": "2828"},
        "baseline_cct": "3248",
        "elasticity_at_registry_point": {"exact": "4/29", "float": float(Fraction(4, 29))},
        "full_range_span": {"exact": str(b_low / b_high), "float": float(b_low / b_high)},
        "asymmetry": {
            "exact": "336/5", "float": 67.2,
            "direction": "more sensitive BELOW the registry point "
                         "(+869.0% at B=1 vs -12.93% at B=1024)",
        },
        "balance_point": {
            "B_star": {"exact": "256/25", "float": 10.24,
                       "law": "bandwidth term == latency chain "
                              "(28672/B == 2800; the atlas M* = L·B·r law "
                              "inverted onto the B axis)",
                       "on_grid": False, "bracket": "8 < 256/25 < 16",
                       "split": "4 of 14 grid points bandwidth-dominated / 10 latency-dominated"},
        },
        "saturation": "hyperbola with floor 2800 ns (the latency chain); "
                      "upper endpoint sits exactly 1% above it",
        "conservation": "B-blind: 28672 B/rank, 0 violations on all 14 rows + 3 runs",
        "stage": {"report": "reports/p1_stageGLOB-BW.md",
                  "record": f"results/calibration/{RECORD_GLOBBW}/record.json"},
        "artifacts": {**bw,
                      "endpoint_runs": [endpoint_run(RUN_B1, "31472"),
                                        endpoint_run(RUN_B1024, "2828")]},
    }

    # --- GLOB-LAT: t(L) = 448 + 14L on [10, 2000], point 200 ---
    t_lat = lambda l: BW_TERM + 2 * (R - 1) * l
    lat = sweep_facts(
        SWEEP_GLOBLAT, "cal_globlat_v1", 14, t_lat, b_base,
        ["l10", "l16", "l32", "l64", "l70", "l80", "l128", "l140", "l200", "l256", "l512", "l800", "l1024", "l2000"],
        {"l10": "588", "l200": "3248", "l2000": "28448"},
        {"l10": "-95/116", "l200": "0", "l2000": "225/29"},
        lambda row: Fraction(row["config_id"].split("globlat_l")[1].split("_")[0]),
    )
    l_low = Fraction(588)
    l_high = Fraction(28448)
    e_lat = LAT_CHAIN / b_base                    # 2800/3248 = 25/29
    assert e_lat == Fraction(25, 29)
    asym_lat = abs(Fraction(225, 29) / Fraction(-95, 116))  # 180/19
    assert asym_lat == Fraction(180, 19)
    l_star = BW_TERM / (2 * (R - 1))              # 448/14 = 32
    assert l_star == 32
    lat_axis = {
        "class": "hop/pair latency",
        "registry_id": "A-L0-LAT",
        "parameter": "link.hop_latency_ns",
        "backend": "analytical_l0 (ring)",
        "registered_range": ["10", "2000"],
        "registry_point": "200",
        "closed_form": "t(L) = 448 + 14L ns (a straight line, slope 2(r-1) = 14)",
        "cct_at_endpoints": {"10": "588", "2000": "28448"},
        "baseline_cct": "3248",
        "elasticity_at_registry_point": {"exact": "25/29", "float": float(Fraction(25, 29))},
        "full_range_span": {"exact": str(l_high / l_low), "float": float(l_high / l_low)},
        "asymmetry": {
            "exact": "180/19", "float": float(Fraction(180, 19)),
            "direction": "more sensitive ABOVE the registry point "
                         "(+775.86% at L=2000 vs -81.90% at L=10) — the "
                         "structural mirror of the B axis (unbounded "
                         "above, bounded below by the 448 ns floor)",
        },
        "balance_point": {
            "L_star": {"exact": "32",
                       "law": "latency chain == bandwidth term (14L == 448; "
                              "the atlas law inverted onto the L axis)",
                       "on_grid": True, "bracket": None,
                       "split": "2 of 14 grid points bandwidth-dominated / 12 latency-dominated"},
        },
        "saturation": "NONE — no ceiling anywhere; every +1 ns of L costs "
                      "exactly +14 ns of CCT",
        "conservation": "L-blind: 28672 B/rank, 0 violations on all 14 rows + 3 runs",
        "stage": {"report": "reports/p1_stageGLOB-LAT.md",
                  "record": f"results/calibration/{RECORD_GLOBLAT}/record.json"},
        "artifacts": {**lat,
                      "endpoint_runs": [endpoint_run(RUN_L10, "588"),
                                        endpoint_run(RUN_L2000, "28448")]},
    }

    # --- GLOB-INJ (= the serialization-RATE axis): t(I) = 3248 + 28672/I ---
    t_inj = lambda i: L0_CCT + SER_COEF / i
    i_low, i_high, i_base = Fraction(31920), Fraction(3276), Fraction(3696)
    inj = sweep_facts(
        SWEEP_GLOBINJ, "cal_globinj_v1", 15, t_inj, i_base,
        ["i1", "i2", "i4", "i8", "i16", "i32", "i64", "i128", "i256", "i448", "i512", "i720", "i900", "i1024"],
        {"i1": "31920", "i64": "3696", "i1024": "3276"},
        {"i1": "84/11", "i64": "0", "i1024": "-5/44"},
        lambda row: (Fraction(row["injection_bytes_per_ns"])
                     if row["injection_bytes_per_ns"] is not None else None),
    )
    e_inj = (SER_COEF / I_REG) / i_base            # 448/3696 = 4/33
    limit_row = None
    tbl = load_json(RESULTS / "sweeps" / SWEEP_GLOBINJ / "table.json")
    for row in tbl["configs"]:
        if row["injection_bytes_per_ns"] is None:
            limit_row = row
    assert limit_row is not None
    assert limit_row["o_cct"]["completion_time_ns_mean_exact"] == "3248"
    assert limit_row["serialization_term_ns_exact"] == "0"
    # Closed form re-verified on every finite row with the L0 anchor column.
    for row in tbl["configs"]:
        if row["injection_bytes_per_ns"] is None:
            continue
        i = Fraction(row["injection_bytes_per_ns"])
        assert Fraction(row["l0_anchor_time_ns_exact"]) == L0_CCT
        assert Fraction(row["serialization_term_ns_exact"]) == SER_COEF / i
        assert (Fraction(row["o_cct"]["completion_time_ns_mean_exact"])
                - Fraction(row["l0_anchor_time_ns_exact"])
                == Fraction(row["serialization_term_ns_exact"]))

    assert e_inj == Fraction(4, 33)
    asym_inj = abs(Fraction(84, 11) / Fraction(-5, 44))   # 336/5 again
    assert asym_inj == Fraction(336, 5) == asym_bw
    i_eq_bw = SER_COEF / BW_TERM                   # 28672/448 = 64 (== B)
    i_eq_lat = SER_COEF / LAT_CHAIN                # 256/25 (== B*)
    i_star = SER_COEF / L0_CCT                     # 256/29
    assert i_eq_bw == 64 and i_eq_lat == Fraction(256, 25) and i_star == Fraction(256, 29)
    assert t_inj(i_star) == 2 * L0_CCT
    inj_axis = {
        "class": "injection bandwidth == serialization rate (ONE axis, two class names)",
        "registry_id": "A-L05-INJ",
        "parameter": "nic.injection_bytes_per_ns",
        "backend": "analytical_l05 (serialized ring; module-direct vehicle)",
        "registered_range": ["1", "1024"],
        "registry_point": "64",
        "closed_form": "t_L05(I) = 3248 + 28672/I ns (finite I); the soak "
                       "suite's pinned identity t_L05 - t_L0 = "
                       "2(r-1)/r·M/I; I -> infinity (null) = t_L0 exactly",
        "cct_at_endpoints": {"1": "31920", "1024": "3276"},
        "baseline_cct": "3696",
        "elasticity_at_registry_point": {"exact": "4/33", "float": float(Fraction(4, 33))},
        "full_range_span": {"exact": str(i_low / i_high), "float": float(i_low / i_high)},
        "asymmetry": {
            "exact": "336/5", "float": 67.2,
            "direction": "more sensitive BELOW the registry point "
                         "(+763.64% at I=1 vs -11.36% at I=1024) — the SAME "
                         "structural constant as the B axis, verified "
                         "digit-for-digit from both landed sweep tables "
                         "(denominator-free: both axes are [1, 1024] with "
                         "registry point 64)",
        },
        "balance_points": {
            "serialization_equals_bandwidth_term": {
                "exact": "64", "law": "28672/I == 448 iff I == B — ON the "
                "grid at the registry point itself (the family convention "
                "I = B); serialization exactly doubles the payload-transfer "
                "cost there"},
            "serialization_equals_latency_chain": {
                "exact": "256/25", "float": 10.24,
                "law": "28672/I == 2800 — the SAME value as the B axis's B* "
                "(the equations are identical); bracketed 8 < 256/25 < 16"},
            "serialization_equals_whole_l0_time": {
                "exact": "256/29", "float": float(Fraction(256, 29)),
                "law": "28672/I == 3248 — the axis's true half-way "
                "(t_L05 = 2·t_L0 = 6496 ns exactly); bracketed "
                "8 < 256/29 < 16; splits the grid 4-vs-10 "
                "(serialization-majority minority below it)"},
        },
        "saturation": "hyperbola with floor 3248 ns — the floor is the "
                      "landed L0 IDENTITY itself (a different model's "
                      "executed output), reached exactly at I -> infinity; "
                      "upper endpoint 0.86% (28 ns) above it",
        "conservation": "I-blind (serialization moves no bytes): 28672 "
                        "B/rank, 0 violations on all 15 rows (incl. the "
                        "limit) + 2 runs",
        "stage": {"report": "reports/p1_stageGLOB-INJ.md",
                  "record": f"results/calibration/{RECORD_GLOBINJ}/record.json"},
        "artifacts": {**inj,
                      "endpoint_runs": [endpoint_run(RUN_I1, "31920"),
                                        endpoint_run(RUN_I1024, "3276")]},
    }
    return bw_axis, lat_axis, inj_axis


# ---------------------------------------------------------------------------
# Cross-class laws, each recomputed and asserted from the landed tables.
# ---------------------------------------------------------------------------


def cross_class_laws(bw: dict, lat: dict, inj: dict) -> dict:
    # (1) Complementarity: the two L0 axes' registry-point elasticities are
    #     complementary halves of the same CCT (bandwidth + latency share).
    assert Fraction(4, 29) + Fraction(25, 29) == 1
    # (2) Duality: both L0 axes place the registry point equally above
    #     their balance point: 64/B* == 200/L* == B·L·r/M == 25/4.
    duality = B / Fraction(256, 25)
    assert duality == L / 32 == B * L * R / M == Fraction(25, 4)
    # (3) The shared asymmetry constant 336/5, digit-for-digit from BOTH
    #     landed rate-axis tables (and the latency axis's mirror 180/19).
    assert (Fraction(sweep_row(SWEEP_GLOBBW, "b1")["delta_vs_baseline"]["delta_exact"])
            / Fraction(sweep_row(SWEEP_GLOBBW, "b1024")["delta_vs_baseline"]["delta_exact"]
                       )) == Fraction(-336, 5)
    assert (Fraction(sweep_row(SWEEP_GLOBINJ, "i1")["delta_vs_baseline"]["delta_exact"])
            / Fraction(sweep_row(SWEEP_GLOBINJ, "i1024")["delta_vs_baseline"]["delta_exact"]
                       )) == Fraction(-336, 5)
    assert (Fraction(sweep_row(SWEEP_GLOBLAT, "l2000")["delta_vs_baseline"]["delta_exact"])
            / Fraction(sweep_row(SWEEP_GLOBLAT, "l10")["delta_vs_baseline"]["delta_exact"]
                       )) == Fraction(-180, 19)  # |180/19| mirrored above
    # (4) The series law: t_L05(I) = t_L0(B_eff) with 1/B_eff = 1/B + 1/I;
    #     at the registry pair B_eff = 32 and the two landed tables agree
    #     digit for digit.
    b_eff = B * I_REG / (B + I_REG)
    assert b_eff == 32
    assert (sweep_row(SWEEP_GLOBBW, "b32")["o_cct"]["completion_time_ns_mean_exact"]
            == sweep_row(SWEEP_GLOBINJ, "i64")["o_cct"]["completion_time_ns_mean_exact"]
            == "3696")
    # (5) The balance-point coincidence: the I axis's serialization==
    #     latency-chain value equals B* exactly (identical equation).
    assert SER_COEF / LAT_CHAIN == WIRE / LAT_CHAIN == Fraction(256, 25)
    # (6) The four-way smoke-point identity: the same shipped config point
    #     executed independently four times, zero drift.
    smoke = load_json(RESULTS / RUN_SMOKE / "observations.json")
    assert smoke["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == "3248"
    assert (sweep_row(SWEEP_GLOBBW, "b64")["o_cct"]["completion_time_ns_mean_exact"]
            == sweep_row(SWEEP_GLOBLAT, "l200")["o_cct"]["completion_time_ns_mean_exact"]
            == "3248")
    # (7) Elasticity ordering + exact dilution relation: the L0.5 axis's
    #     elasticity is the B axis's diluted by its own serialization term
    #     ((4/29)/(4/33) == 33/29 == 3696/3248).
    assert (Fraction(4, 29)) / (Fraction(4, 33)) == Fraction(33, 29) == L05_BASE / L0_CCT
    assert Fraction(25, 29) > Fraction(4, 29) > Fraction(4, 33)
    # (8) Range-span ordering (exact): L 1016/21 > B 1124/101 > I 380/39.
    span_lat = Fraction(28448, 588)
    span_bw = Fraction(31472, 2828)
    span_inj = Fraction(31920, 3276)
    assert span_lat == Fraction(1016, 21)
    assert span_bw == Fraction(1124, 101)
    assert span_inj == Fraction(380, 39)
    assert span_lat > span_bw > span_inj

    return {
        "complementarity": {
            "law": "4/29 + 25/29 = 1 exactly — the link-BW and "
                   "hop/pair-latency axes' registry-point elasticities are "
                   "complementary halves of the same L0 CCT (the bandwidth "
                   "share and the latency share)",
            "asserted_from": f"sweeps {SWEEP_GLOBBW} / {SWEEP_GLOBLAT} "
                             "baseline rows (3248 = 448 + 2800)",
        },
        "duality": {
            "law": "64/B* == 200/L* == B·L·r/M == 25/4 — both L0 axes place "
                   "the registry point exactly 6.25x above their balance "
                   "point; the two axes are duals at the smoke point",
            "asserted_from": "registry constants + both sweeps' balance "
                             "points (B* = 256/25 bracketed, L* = 32 on-grid)",
        },
        "shared_asymmetry_constant": {
            "law": "|delta(1)/delta(1024)| == 336/5 == 67.2 on BOTH rate "
                   "axes (B and I) — a denominator-free structural constant "
                   "of any [1, 1024] axis with registry point 64: "
                   "(64-1)/(1-64/1024) = 336/5; the latency axis mirrors it "
                   "in the opposite direction at 180/19 ≈ 9.47 above",
            "asserted_from": "all three landed sweep tables' endpoint delta "
                             "columns, digit for digit",
        },
        "series_law": {
            "law": "t_L05(I) = t_L0(B_eff) with 1/B_eff = 1/B + 1/I — the "
                   "entire injection/serialization axis IS the link-BW axis "
                   "reparametrized (L0.5's per-chunk NIC serialization is "
                   "indistinguishable, at the CCT identity, from a series "
                   "link of rate I ahead of the link of rate B)",
            "at_registry_pair": "B_eff(64, 64) = 32: the GLOB-INJ I=64 row "
                                "equals the GLOB-BW B=32 row digit for digit "
                                "(3696 ns)",
            "asserted_from": f"sweeps {SWEEP_GLOBINJ} (i64) and {SWEEP_GLOBBW} (b32)",
        },
        "balance_point_coincidence": {
            "law": "the serialization-rate axis's serialization==latency-"
                   "chain balance value (256/25 = 10.24) EQUALS the link-BW "
                   "axis's B* — the equations are identical (w/x == 14L); "
                   "the I axis adds the on-grid point I = B = 64 (term == "
                   "the ring's own bandwidth term) and I** = 256/29 ≈ 8.83 "
                   "(term == the whole landed t_L0, the 4-vs-10 split)",
            "asserted_from": "exact Fractions recomputed from the shared "
                             "constants 28672 / 448 / 2800 / 3248",
        },
        "smoke_point_four_way_identity": {
            "law": "the shipped smoke point (B=64, L=200, I=null/inf) "
                   "evaluates to 3248 ns identically in the GLOB-BW B=64 "
                   "row, the GLOB-LAT L=200 row, the GLOB-INJ limit row and "
                   "the landed W1 smoke store run — the same point executed "
                   "independently four times, zero drift",
            "asserted_from": f"sweeps {SWEEP_GLOBBW}/{SWEEP_GLOBLAT}/"
                             f"{SWEEP_GLOBINJ} + run {RUN_SMOKE}",
        },
        "elasticity_ordering": {
            "law": "25/29 (86.21%, L) > 4/29 (13.79%, B) > 4/33 (12.12%, I) "
                   "— only the latency axis's registry-declared 'high' "
                   "sensitivity materializes AT the registry point; both "
                   "rate axes are locally near-inert there, and the I axis "
                   "is the B axis's elasticity diluted by its own "
                   "serialization term: (4/29)/(4/33) = 33/29 = 3696/3248",
            "asserted_from": "exact Fractions from the three baseline rows",
        },
        "range_span_ordering": {
            "law": "full-registered-range CCT spans: L 1016/21 ≈ 48.38x > "
                   "B 1124/101 ≈ 11.13x > I 380/39 ≈ 9.74x — the smoke "
                   "observable feels the latency axis ~4.35x more than the "
                   "link-BW axis and ~4.97x more than the injection/serial-"
                   "ization axis; the serialization-rate axis is the "
                   "NARROWEST executed axis",
            "asserted_from": "endpoint CCTs of all three sweeps (588/28448, "
                             "31472/2828, 31920/3276)",
        },
    }


def main() -> int:
    resolution = axis_resolution_facts()
    bw, lat, inj = executed_axes()
    laws = cross_class_laws(bw, lat, inj)

    # Sibling records verified (existence + stage identity).
    for rid, name in [(RECORD_GLOBBW, "GLOB-BW"), (RECORD_GLOBLAT, "GLOB-LAT"),
                      (RECORD_GLOBINJ, "GLOB-INJ")]:
        rec = load_json(RESULTS / "calibration" / rid / "record.json")
        assert name in rec["stage"], (rid, name)
        assert rec["status"].startswith("PROPOSED")

    record = {
        "record_kind": "calibration_candidate",
        "status": "PROPOSED — owner adjudication required; no claim or label changed",
        "stage": "Q1 calibration ladder, GLOBAL stage GLOB-SER (parameter "
                 "class: serialization rate; the FOURTH and FINAL global "
                 "parameter-class stage),  — landed as "
                 "the cross-class SYNTHESIS: the class's numeric axis is "
                 "A-L05-INJ, already executed by GLOB-INJ (the duplication "
                 "finding); this stage re-runs nothing and consolidates",
        "parameter_class": {
            "class": "serialization rate",
            "axis_resolution": resolution,
        },
        "target": {
            "role": "cross-class synthesis — the parameter-class "
                    "sensitivity table the ladder asked for: WHERE the "
                    "model's own O-CCT output sits across each executed "
                    "parameter class's registered range on the W1 smoke "
                    "config; never a comparison to an external measurement, "
                    "never a tuning step",
            "o_cct_calibratable": False,
            "o_cct_not_calibratable_reason": "no anchor is involved in any "
                                             "of the four global stages; "
                                             "every number below is an E0 "
                                             "arithmetic fact of an executed "
                                             "identity (the smoke payload "
                                             "regime, 16 KiB, is itself "
                                             "anchor-free per plan gap 4.3)",
            "observables": ["O-CCT", "O-CONSERVATION"],
            "regime": {
                "workload": "W1 Dense TP Decode smoke configuration, "
                            "verbatim (experiments/workloads/"
                            "w1_dense_tp_decode_small.yaml: tp8, 2 layers x "
                            "3 steps = 6 AllReduce ops, M = 16384 B)",
                "ranks": 8,
                "fixed_at_registry_points": "B = 64 B/ns, L = 200 ns on all "
                                            "three executed axes; each axis "
                                            "swept its own registered range "
                                            "with the others at KEEP",
            },
        },
        "comparison": {
            "parameter_class_sensitivity_table": [bw, lat, inj],
            "identity_enum_row": {
                "class": "serialization rate — identity dimension",
                "registry_id": "A-L05-SER",
                "parameter": "model.per_transfer_service_time",
                "registered_range": resolution["identity_entry"]["registered_range"],
                "executable_values": "1 of 3 (serialize_push_latency_per_"
                                     "transfer — the only implemented "
                                     "identity; the code, not an input)",
                "sensitivity_verdict": "NOT SWEEPABLE under existing "
                                       "machinery: no input surface "
                                       "(byte-identical execution under all "
                                       "three enum values), both "
                                       "alternatives in "
                                       "CAPABILITIES['explicitly_"
                                       "unsupported']; implementing them is "
                                       "a capability-gated step, not a "
                                       "sensitivity stage. The registry "
                                       "marks A-L05-SER 'sensitivity: high "
                                       "for O-CCT' — at the level of WHICH "
                                       "identity is implemented, which is "
                                       "exactly why the enum matters and "
                                       "cannot be silently swapped",
            },
            "cross_class_laws": laws,
        },
        "deviation": {
            "vs_anchor": "UNDEFINED BY CONSTRUCTION — no anchor and no "
                         "external measurement enters any global stage; the "
                         "consolidated table records each axis's placement "
                         "deltas against its own registry point, never "
                         "agreement with any measurement",
            "summary": "on the W1 smoke config the three executed global "
                       "axes are two hyperbolas and one line — t(B) = "
                       "28672/B + 2800 (span 11.13x, elasticity 4/29, "
                       "floor 2800), t(L) = 448 + 14L (span 48.38x, "
                       "elasticity 25/29, no saturation), t_L05(I) = 3248 + "
                       "28672/I (span 9.74x, elasticity 4/33, floor = the "
                       "L0 identity itself) — with the two L0 elasticities "
                       "complementary (4/29 + 25/29 = 1), both axes' "
                       "registry points 25/4 above their balance points "
                       "(duals), both rate axes sharing the asymmetry "
                       "constant 336/5 (the latency axis mirroring it at "
                       "180/19), the whole I axis the B axis reparametrized "
                       "(series law, B_eff(64,64) = 32), the smoke point "
                       "itself four-way identical at 3248 ns, and the "
                       "fourth class name (serialization rate) resolving "
                       "onto the third's axis (A-L05-INJ) plus an "
                       "unsweepable identity enum (A-L05-SER)",
        },
        "evidence_levels": {
            "runs_and_sweeps": "E0 (analytical executions; deterministic, "
                               "content-addressed, landed by stages GLOB-BW/"
                               "GLOB-LAT/GLOB-INJ and cited, not re-run)",
            "live_checks": "E0 module-direct re-executions at build time "
                           "(the no-surface facts; deterministic, "
                           "byte-identical replay)",
            "candidate": "PROPOSED cross-class synthesis candidate; no "
                         "E3/E4 language — no external target exists or is "
                         "claimed",
        },
        "backing": {
            "run_ids": [RUN_B1, RUN_B1024, RUN_L10, RUN_L2000, RUN_I1, RUN_I1024, RUN_SMOKE],
            "run_roles": {
                RUN_B1: "GLOB-BW registered-range lower endpoint (B=1)",
                RUN_B1024: "GLOB-BW registered-range upper endpoint (B=1024)",
                RUN_L10: "GLOB-LAT registered-range lower endpoint (L=10)",
                RUN_L2000: "GLOB-LAT registered-range upper endpoint (L=2000)",
                RUN_I1: "GLOB-INJ registered-range lower endpoint (I=1)",
                RUN_I1024: "GLOB-INJ registered-range upper endpoint (I=1024)",
                RUN_SMOKE: "landed W1 smoke run (analytical_l0 at B=64, "
                           "L=200) — the common four-way identity twin",
            },
            "sweep_ids": [SWEEP_GLOBBW, SWEEP_GLOBLAT, SWEEP_GLOBINJ],
            "sweep_dirs": [f"results/sweeps/{SWEEP_GLOBBW}",
                           f"results/sweeps/{SWEEP_GLOBLAT}",
                           f"results/sweeps/{SWEEP_GLOBINJ}"],
            "stage_records": {
                "GLOB-BW": f"results/calibration/{RECORD_GLOBBW}/record.json",
                "GLOB-LAT": f"results/calibration/{RECORD_GLOBLAT}/record.json",
                "GLOB-INJ": f"results/calibration/{RECORD_GLOBINJ}/record.json",
            },
            "backed_numbers": "every constant in the table and the laws is "
                              "recomputed from the landed sweep tables and "
                              "run records by this builder (exact Fraction "
                              "string equality asserted on every cited row "
                              "and run); nothing is transcribed from the "
                              "stage reports except their content addresses, "
                              "which are themselves verified",
            "inputs": [
                "experiments/calibration/globser/build_calibration_record.py (this builder; "
                "the ONLY new artifact of this stage)",
                "experiments/calibration/globbw/ (GLOB-BW stage, referenced unmodified)",
                "experiments/calibration/globlat/ (GLOB-LAT stage, referenced unmodified)",
                "experiments/calibration/globinj/ (GLOB-INJ stage, referenced unmodified)",
                "experiments/vertical_slice/assumptions_l05.yaml (read-only; A-L05-INJ / A-L05-SER rows)",
                "experiments/vertical_slice/assumptions_l0.yaml (read-only; no serialization-rate axis)",
                "experiments/topologies/ring8_l05_free_params.yaml (read-only; the live no-surface execution)",
                "docs/calibration/CALIBRATION_PLAN.md (read-only; provenance)",
                "the calibration prompt (read-only; the four-class list)",
            ],
            "reproduce": "python experiments/calibration/globser/build_calibration_record.py",
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
