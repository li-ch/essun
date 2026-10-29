"""T040 first differential-validation engine slice.

Golden section — HERMETIC: the engine reproduces the manual G3-S3
difference report's classification inputs
(``reports/p3_difference_report.md`` /
``results/difference_reports/w1_smoke_l0_vs_astra_sim_analytical.json``)
on synthetic run records built in ``tmp_path`` through the store API
itself (``EvidenceStore.put_run``), in the same canonical shapes as the
recorded W1-smoke pair and with the S3 hand-derived series — no file
under ``results/`` is read:

- reference/L0 shape (per-op series): 6 ops x 3248 ns -> chain 19488 ns
- value/chain shape (whole-chain wall): 144288 ns over the same 6 ops,
  exact per-op division 24048 ns, O-CONSERVATION declared unsupported

so the golden verdicts are the S3 ones: chain delta 124800 ns, ratio
144288/19488 = 1503/203 = 7.403940886699507x; per-op first divergence
3248 vs 24048, delta 20800 ns = 19600 latency + 1200 endpoint (the S3
decomposed terms — consistency targets only, the engine never
re-derives them); O-CCT-RELERR (bounded, E0 zero slack) a finding with
|relerr| = 1300/203; O-CONSERVATION a capability gap -> not_comparable.

One OPTIONAL integration test keeps the S3 reproduction guarantee on
the REAL recorded pair (run ids below) whenever the gitignored
production records are present; a clean checkout without them skips it
with the stated reason instead of failing the suite.

Negative section: contract gates fire loudly (unknown run, unregistered
observable, unknown quantity, uncontrolled comparison, empty runs,
misaligned series, tolerance override, wrong exact-mode spec, baseline
misalignment, relative form with zero reference, append-only rewrite).
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from essun.evidence.store import EvidenceStore, canonical_json
from essun.observables import (
    BOUNDED,
    ObservableSpec,
    RELATIVE,
    ValidityDomain,
    register,
)
from essun.validation.diff_engine import (
    DiffEngine,
    DiffEngineError,
    Obligation,
    write_report,
)

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "results"

# The REAL recorded W1-smoke pair (manual G3-S3 report) — used ONLY by
# the optional integration test at the bottom of this module.
RUN_L0 = "146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1"
RUN_ASTRA = "c6dc87eb58791438a4a9050238bc8347418228fb63e6df428fb27d3c0b35ab0c"

# S3 golden numbers (manual report, P3 stage S3) — hand-derived, and the
# same values the hermetic golden tests below build their synthetic
# records from.
CHAIN_L0 = Fraction(19488)  # 6 ops x 3248 ns
CHAIN_ASTRA = Fraction(144288)
PER_OP_L0 = Fraction(3248)
PER_OP_ASTRA = Fraction(24048)  # 144288 / 6 (exact, zero-gap chain)
RATIO = Fraction(144288, 19488)  # 1503/203 = 7.403940886699507x
RELERR = RATIO - 1  # 1300/203
# Decomposed gap terms from the S3 report (consistency targets only —
# the engine never re-derives them)
TERM_LATENCY_DELTA = Fraction(19600)
TERM_ENDPOINT_DELTA = Fraction(1200)


# --- synthetic fixtures ------------------------------------------------------


def _l0_like_obs(values, wire_bytes="28672"):
    return {
        "backend_id": "analytical_l0_test",
        "observables": {
            "O-CCT": {
                "kind": "analytical",
                "ops": len(values),
                "completion_time_ns_mean_exact": str(values[0]) if values else "0",
            },
            "O-CONSERVATION": {"kind": "exact", "violations": 0},
        },
        "per_op": [
            {
                "op_id": f"op{i}",
                "completion_time_ns_exact": str(v),
                "per_rank_wire_bytes_exact": wire_bytes,
            }
            for i, v in enumerate(values)
        ],
    }


def _chain_like_obs(chain_wall, ops, unsupported=None):
    observations = {
        "backend_id": "chain_backend_test",
        "observables": {
            "O-CCT": {"kind": "analytical", "ops": ops, "completion_time_ns": chain_wall},
        },
    }
    if unsupported is not None:
        observations["unsupported_observables"] = unsupported
    return observations


def _payload(
    experiment_id="EXP-T-A",
    baseline_id=None,
    workload_sha="w" * 64,
    topo_sha="t" * 64,
):
    return {
        "code_version": "0.1.0",
        "manifest": {"experiment_id": experiment_id, "baseline_id": baseline_id},
        "inputs": {
            "workload_ir": {"sha256": workload_sha},
            "infra_graph": {"sha256": topo_sha},
        },
    }


def _synthetic_store(tmp_path, runs):
    """Put (payload, observations) pairs; returns (store, run_ids)."""
    store = EvidenceStore(tmp_path / "results")
    run_ids = [store.put_run(payload, obs) for payload, obs in runs]
    return store, run_ids


def _pair_store(tmp_path, values_a=(3248, 3248), values_b=(24048, 24048)):
    return _synthetic_store(
        tmp_path,
        [
            (_payload(experiment_id="EXP-T-A"), _l0_like_obs(list(values_a))),
            (
                _payload(experiment_id="EXP-T-B", baseline_id="EXP-T-A"),
                _chain_like_obs(sum(values_b), len(values_b)),
            ),
        ],
    )


# --- the hermetic S3-shaped pair (golden fixture) -----------------------------
#
# Same canonical shapes as the recorded W1-smoke pair and the same S3
# hand-derived values (manual G3-S3 report), built through the store API
# into tmp_path: the golden section below therefore reads NOTHING under
# the gitignored production results/ (ADD-G hermeticity bar 1).

S3_L0_PER_OP = (3248, 3248, 3248, 3248, 3248, 3248)  # 6 ops x 3248 ns
S3_ASTRA_CHAIN = 144288  # whole-chain wall over the same 6 ops (= 6 x 24048)
S3_OCONSERVATION_GAP = (
    "no byte accounting in the analytical congestion-unaware output "
    "(S3 canonical capability gap)"
)


def _s3_pair_store(tmp_path):
    """The S3 W1-smoke pair, rebuilt hermetically: L0 per-op-series shape
    (6 x 3248 ns, chain total 19488) vs whole-chain-wall shape (144288,
    exact per-op division 24048), chain side declaring O-CONSERVATION
    unsupported, and shared workload/topology hashes so the pair is a
    controlled comparison."""
    return _synthetic_store(
        tmp_path,
        [
            (
                _payload(experiment_id="EXP-T-S3-L0"),
                _l0_like_obs(list(S3_L0_PER_OP)),
            ),
            (
                _payload(experiment_id="EXP-T-S3-ASTRA", baseline_id="EXP-T-S3-L0"),
                _chain_like_obs(
                    S3_ASTRA_CHAIN,
                    len(S3_L0_PER_OP),
                    unsupported={"O-CONSERVATION": S3_OCONSERVATION_GAP},
                ),
            ),
        ],
    )


# --- golden: the engine reproduces the S3 result on the S3-shaped pair -------
#
# Every asserted value is hand-derived from the manual G3-S3 report and
# documented inline; the records live in tmp_path stores created through
# EvidenceStore.put_run, so a clean checkout with no results/ runs these.


def test_s3_exact_chain_total_reproduces_classification_inputs(tmp_path):
    # The 7.404x classification inputs: chain 19488 vs 144288 ns
    # (6 x 3248 per-op sum vs the whole-chain wall), delta 124800,
    # ratio 1503/203.
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    record = DiffEngine(store).compare(
        run_l0,
        run_astra,
        Obligation(mode="exact", quantity="cct_chain_total_ns", spec_id="O-CCT"),
    )
    assert record["engine"] == "essun.validation.diff_engine"
    assert record["runs"]["a"]["run_id"] == run_l0
    assert record["runs"]["b"]["run_id"] == run_astra
    assert record["runs"]["b"]["baseline_id"] == "EXP-T-S3-L0"
    verdict = record["verdict"]
    assert verdict["status"] == "diverged"
    first = verdict["first_divergence"]
    assert first["observable"] == "O-CCT"
    assert first["value_a_exact"] == "19488"
    assert first["value_b_exact"] == "144288"
    assert Fraction(first["delta_exact"]) == CHAIN_ASTRA - CHAIN_L0 == Fraction(124800)
    assert Fraction(first["ratio_b_over_a_exact"]) == RATIO
    assert first["ratio_b_over_a_float"] == pytest.approx(7.403940886699507, abs=1e-12)
    # Aggregation provenance is recorded, not silently assumed.
    provenance = record["obligation"]["series_provenance"]
    assert any("sum(per_op" in p for p in provenance["a"])
    assert any("completion_time_ns" in p for p in provenance["b"])


def test_s3_exact_per_op_first_divergence(tmp_path):
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    record = DiffEngine(store).compare(
        run_l0,
        run_astra,
        Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
    )
    verdict = record["verdict"]
    assert verdict["status"] == "diverged"
    first = verdict["first_divergence"]
    assert first["location"] == {"op": 0}  # all ops diverge identically; op 0 is first
    assert Fraction(first["value_a_exact"]) == PER_OP_L0
    assert Fraction(first["value_b_exact"]) == PER_OP_ASTRA  # 144288/6 = 24048
    assert Fraction(first["delta_exact"]) == PER_OP_ASTRA - PER_OP_L0
    assert record["obligation"]["series_length"] == 6
    # The chain side is the exact chain/ops division (zero-gap chain), and
    # the record says so.
    assert any("/ ops" in p for p in record["obligation"]["series_provenance"]["b"])


def test_s3_first_divergence_consistent_with_decomposed_terms(tmp_path):
    # The engine does not re-derive the S3 decomposition; its reported
    # per-op delta must simply equal the two classified terms.
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    record = DiffEngine(store).compare(
        run_l0,
        run_astra,
        Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
    )
    delta = Fraction(record["verdict"]["first_divergence"]["delta_exact"])
    assert delta == TERM_LATENCY_DELTA + TERM_ENDPOINT_DELTA == Fraction(20800)


def test_s3_bounded_cct_relerr_is_a_finding_with_margin(tmp_path):
    # Bounded form on the pair: value = chain-side chain, reference = L0
    # chain (the recorded baseline). At E0 zero slack every nonzero
    # relative deviation is a VIOLATION returned as a finding — never raised.
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    record = DiffEngine(store).compare(
        run_l0,
        run_astra,
        Obligation(
            mode="bounded", quantity="cct_chain_total_ns", spec_id="O-CCT-RELERR"
        ),
    )
    verdict = record["verdict"]
    assert verdict["status"] == "violation"
    assert verdict["reference_orientation"].startswith("a = reference")
    assert verdict["tolerance_exact"] == "0"
    assert verdict["form"] == "relative"
    worst = verdict["worst"]
    assert worst["value_a_exact"] == "19488"
    assert worst["value_b_exact"] == "144288"
    assert Fraction(worst["deviation_exact"]) == RELERR == Fraction(1300, 203)
    assert Fraction(worst["margin_exact"]) == RELERR  # tolerance is 0
    assert verdict["violating_locations"] == verdict["locations_checked"] == 1
    assert verdict["validity_domain"]  # registry domain echoed into the verdict


def test_s3_bounded_per_op_evaluates_every_location(tmp_path):
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    record = DiffEngine(store).compare(
        run_l0,
        run_astra,
        Obligation(mode="bounded", quantity="cct_per_op_ns", spec_id="O-CCT-RELERR"),
    )
    verdict = record["verdict"]
    assert verdict["locations_checked"] == 6
    assert verdict["violating_locations"] == 6
    # 24048/3248 - 1 = 20800/3248 = 1300/203 — identical at every op.
    assert Fraction(verdict["worst"]["deviation_exact"]) == RELERR


def test_s3_oconservation_is_a_capability_gap_not_a_difference(tmp_path):
    # S3: O-CONSERVATION is unsupported for the ASTRA analytical backend.
    # The engine records a capability gap verdict, not a numeric verdict.
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    record = DiffEngine(store).compare(
        run_l0,
        run_astra,
        Obligation(
            mode="exact",
            quantity="per_rank_wire_bytes_per_op",
            spec_id="O-CONSERVATION",
        ),
    )
    verdict = record["verdict"]
    assert verdict["status"] == "not_comparable"
    assert "unsupported" in verdict["reason"]
    assert "O-CONSERVATION" in verdict["reason"]


def test_s3_records_are_deterministic_and_writes_idempotent(tmp_path):
    store, (run_l0, run_astra) = _s3_pair_store(tmp_path)
    engine = DiffEngine(store)
    obligation = Obligation(
        mode="bounded", quantity="cct_chain_total_ns", spec_id="O-CCT-RELERR"
    )
    first = engine.compare(run_l0, run_astra, obligation)
    second = engine.compare(run_l0, run_astra, obligation)
    assert first == second  # pure function of the stored runs
    assert first["diff_id"] == second["diff_id"]

    path_one = write_report(first, results_root=tmp_path)
    path_two = write_report(second, results_root=tmp_path)
    assert path_one == path_two
    assert path_one.name == f"{first['diff_id']}.json"
    assert path_one.parent.name == "difference_reports"
    # Round-trips as canonical JSON with a trailing newline, no wall-clock.
    raw = path_one.read_bytes()
    assert raw.endswith(b"\n")
    assert raw.decode("utf-8") == canonical_json(first) + "\n"
    parsed = json.loads(raw)
    assert parsed["diff_id"] == first["diff_id"]
    for banned in ("timestamp", "generated_at", "wall_clock"):
        assert banned not in raw.decode("utf-8").lower()


# --- golden: exact equality and the E0 tolerance edge -------------------------


def test_exact_equal_series_verdict_equal(tmp_path):
    # Both chains total 6496 ns: bit-exact equality across aggregation
    # shapes (per-op series summed vs whole-chain wall).
    store, (run_a, run_b) = _pair_store(tmp_path, (3248, 3248), (6496,))
    record = DiffEngine(store).compare(
        run_a, run_b, Obligation(mode="exact", quantity="cct_chain_total_ns", spec_id="O-CCT")
    )
    verdict = record["verdict"]
    assert verdict["status"] == "equal"
    assert verdict["first_divergence"] is None


def test_bounded_zero_slack_edge_equal_values_pass(tmp_path):
    store, (run_a, run_b) = _pair_store(tmp_path, (3248,), (3248,))
    record = DiffEngine(store).compare(
        run_a, run_b, Obligation(mode="bounded", quantity="cct_per_op_ns", spec_id="O-CCT-RELERR")
    )
    verdict = record["verdict"]
    assert verdict["status"] == "pass"
    assert Fraction(verdict["worst"]["deviation_exact"]) == 0
    assert Fraction(verdict["worst"]["margin_exact"]) == 0  # 0 <= tolerance 0
    assert verdict["violating_locations"] == 0


def test_bounded_zero_slack_edge_one_unit_deviation_violates(tmp_path):
    # Tolerance edge at E0: a single-ns deviation on 3248 ns reference is
    # |3249/3248 - 1| = 1/3248 > 0 -> violation (finding, not a raise).
    store, (run_a, run_b) = _pair_store(tmp_path, (3248,), (3249,))
    record = DiffEngine(store).compare(
        run_a, run_b, Obligation(mode="bounded", quantity="cct_per_op_ns", spec_id="O-CCT-RELERR")
    )
    verdict = record["verdict"]
    assert verdict["status"] == "violation"
    assert Fraction(verdict["worst"]["deviation_exact"]) == Fraction(1, 3248)
    assert Fraction(verdict["worst"]["margin_exact"]) == Fraction(1, 3248)


def test_bounded_nonzero_tolerance_comes_from_the_registry(tmp_path):
    spec = register(
        ObservableSpec(
            observable_id="O-TEST-DIFF-TOL",
            kind=BOUNDED,
            unit="ratio",
            tolerance=Fraction(1, 10),
            form=RELATIVE,
            validity_domain=ValidityDomain(topology="ring8_free_v1"),
        )
    )
    store, run_ids = _synthetic_store(
        tmp_path,
        [
            (_payload(experiment_id="EXP-T-A"), _l0_like_obs([100])),
            (
                _payload(experiment_id="EXP-T-B", baseline_id="EXP-T-A"),
                _chain_like_obs(110, 1),
            ),
        ],
    )
    obligation = Obligation(
        mode="bounded", quantity="cct_per_op_ns", spec_id=spec.observable_id
    )
    # |110/100 - 1| = 1/10 <= 1/10: exactly at the tolerance boundary.
    within = DiffEngine(store).compare(run_ids[0], run_ids[1], obligation)
    assert within["verdict"]["status"] == "pass"
    assert Fraction(within["verdict"]["worst"]["margin_exact"]) == 0
    assert within["verdict"]["tolerance_exact"] == "1/10"
    # |125/100 - 1| = 1/4 > 1/10: a finding with the registered tolerance.
    store2, run_ids2 = _synthetic_store(
        tmp_path / "pair2",
        [
            (_payload(experiment_id="EXP-T-A"), _l0_like_obs([100])),
            (
                _payload(experiment_id="EXP-T-B", baseline_id="EXP-T-A"),
                _chain_like_obs(125, 1),
            ),
        ],
    )
    finding = DiffEngine(store2).compare(run_ids2[0], run_ids2[1], obligation)
    assert finding["verdict"]["status"] == "violation"
    assert Fraction(finding["verdict"]["worst"]["deviation_exact"]) == Fraction(1, 4)


# --- negative: contract gates fire loudly ------------------------------------


def test_unknown_run_id_rejected(tmp_path):
    store, (run_a, _) = _pair_store(tmp_path)
    with pytest.raises(DiffEngineError, match="unknown run"):
        DiffEngine(store).compare(
            run_a,
            "f" * 64,
            Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
        )


def test_unregistered_observable_rejected(tmp_path):
    store, (run_a, run_b) = _pair_store(tmp_path)
    with pytest.raises(DiffEngineError, match="not registered"):
        DiffEngine(store).compare(
            run_a,
            run_b,
            Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-NO-SUCH-OBSERVABLE"),
        )


def test_unknown_quantity_rejected(tmp_path):
    store, (run_a, run_b) = _pair_store(tmp_path)
    with pytest.raises(DiffEngineError, match="unknown quantity"):
        DiffEngine(store).compare(
            run_a,
            run_b,
            Obligation(mode="exact", quantity="cct_percentile_ns", spec_id="O-CCT"),
        )


def test_uncontrolled_comparison_rejected(tmp_path):
    # Rule 6: runs with different workloads are not a controlled ablation.
    store, run_ids = _synthetic_store(
        tmp_path,
        [
            (_payload(experiment_id="EXP-T-A", workload_sha="a" * 64), _l0_like_obs([3248])),
            (
                _payload(experiment_id="EXP-T-B", baseline_id="EXP-T-A", workload_sha="b" * 64),
                _chain_like_obs(24048, 1),
            ),
        ],
    )
    with pytest.raises(DiffEngineError, match="uncontrolled comparison"):
        DiffEngine(store).compare(
            run_ids[0],
            run_ids[1],
            Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
        )


def test_empty_run_rejected(tmp_path):
    store, run_ids = _synthetic_store(
        tmp_path,
        [
            (_payload(experiment_id="EXP-T-A"), _l0_like_obs([3248])),
            (_payload(experiment_id="EXP-T-B", baseline_id="EXP-T-A"), _l0_like_obs([])),
        ],
    )
    with pytest.raises(DiffEngineError, match="EMPTY"):
        DiffEngine(store).compare(
            run_ids[0],
            run_ids[1],
            Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
        )


def test_misaligned_series_lengths_rejected(tmp_path):
    store, (run_a, run_b) = _pair_store(tmp_path, (3248, 3248, 3248), (72000, 72000))
    with pytest.raises(DiffEngineError, match="misaligned series lengths"):
        DiffEngine(store).compare(
            run_a,
            run_b,
            Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
        )


def test_tolerance_override_must_equal_registry(tmp_path):
    store, (run_a, run_b) = _pair_store(tmp_path)
    with pytest.raises(DiffEngineError, match="tuning"):
        DiffEngine(store).compare(
            run_a,
            run_b,
            Obligation(
                mode="bounded",
                quantity="cct_per_op_ns",
                spec_id="O-CCT-RELERR",
                tolerance=Fraction(1, 2),  # registered tolerance is 0
            ),
        )


def test_exact_mode_requires_the_emitted_observable_spec(tmp_path):
    store, (run_a, run_b) = _pair_store(tmp_path)
    with pytest.raises(DiffEngineError, match="emitted observable"):
        DiffEngine(store).compare(
            run_a,
            run_b,
            Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT-RELERR"),
        )


def test_bounded_baseline_misalignment_rejected(tmp_path):
    # Run b declares a baseline that is not run a: the bounded reference
    # orientation would be a lie. The engine refuses.
    store, run_ids = _synthetic_store(
        tmp_path,
        [
            (_payload(experiment_id="EXP-T-A"), _l0_like_obs([3248])),
            (
                _payload(experiment_id="EXP-T-B", baseline_id="EXP-OTHER"),
                _chain_like_obs(24048, 1),
            ),
        ],
    )
    with pytest.raises(DiffEngineError, match="reference misalignment"):
        DiffEngine(store).compare(
            run_ids[0],
            run_ids[1],
            Obligation(mode="bounded", quantity="cct_per_op_ns", spec_id="O-CCT-RELERR"),
        )


def test_relative_form_zero_reference_rejected(tmp_path):
    store, run_ids = _synthetic_store(
        tmp_path,
        [
            (_payload(experiment_id="EXP-T-A"), _l0_like_obs([0])),
            (
                _payload(experiment_id="EXP-T-B", baseline_id="EXP-T-A"),
                _chain_like_obs(5, 1),
            ),
        ],
    )
    with pytest.raises(DiffEngineError, match="zero reference"):
        DiffEngine(store).compare(
            run_ids[0],
            run_ids[1],
            Obligation(mode="bounded", quantity="cct_per_op_ns", spec_id="O-CCT-RELERR"),
        )


def test_report_append_only_guard(tmp_path):
    results_root = tmp_path / "results"
    store, (run_a, run_b) = _pair_store(tmp_path, (3248,), (3248,))
    record = DiffEngine(store).compare(
        run_a, run_b, Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT")
    )
    target = results_root / "difference_reports" / f"{record['diff_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"tampered\n")
    with pytest.raises(DiffEngineError, match="append-only violation"):
        write_report(record, results_root=results_root)


def test_write_report_requires_a_typed_record():
    with pytest.raises(DiffEngineError, match="no diff_id"):
        write_report({"verdict": {"status": "equal"}})


# --- optional integration: the REAL recorded W1-smoke pair --------------------
#
# The S3 reproduction guarantee on the real records (repro-drill bar 3:
# 5/5 byte-match against the stored pair) must not be lost — only made
# conditional. results/ is gitignored and produced by the documented
# runs, so a clean checkout legitimately lacks these files; the test
# then SKIPS with this reason instead of failing the suite. It performs
# comparisons only — nothing is ever written to the production store.


_REAL_PAIR_PRESENT = (
    RESULTS / RUN_L0 / "run.json"
).is_file() and (RESULTS / RUN_ASTRA / "run.json").is_file()


@pytest.mark.skipif(
    not _REAL_PAIR_PRESENT,
    reason=(
        "production W1-smoke run records 146ba565…/c6dc87eb… not present: "
        "results/ is gitignored and created by the documented smoke runs; the "
        "S3 reproduction is exercised hermetically by the synthetic golden "
        "tests above — export the stored pair into results/ to re-exercise "
        "the real pair"
    ),
)
def test_s3_real_w1_smoke_pair_integration():
    # REAL pair, exact obligations, the S3 numbers as recorded: chain
    # 19488 vs 144288 (delta 124800, ratio 1503/203) and per-op first
    # divergence 3248 vs 24048 (delta 20800 = 19600 latency + 1200
    # endpoint, the classified S3 terms).
    engine = DiffEngine(EvidenceStore(RESULTS))
    chain = engine.compare(
        RUN_L0,
        RUN_ASTRA,
        Obligation(mode="exact", quantity="cct_chain_total_ns", spec_id="O-CCT"),
    )
    assert chain["runs"]["a"]["run_id"] == RUN_L0
    assert chain["runs"]["b"]["run_id"] == RUN_ASTRA
    first = chain["verdict"]["first_divergence"]
    assert first["value_a_exact"] == "19488"
    assert first["value_b_exact"] == "144288"
    assert Fraction(first["delta_exact"]) == Fraction(124800)
    assert Fraction(first["ratio_b_over_a_exact"]) == RATIO
    per_op = engine.compare(
        RUN_L0,
        RUN_ASTRA,
        Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
    )
    divergence = per_op["verdict"]["first_divergence"]
    assert Fraction(divergence["value_a_exact"]) == PER_OP_L0
    assert Fraction(divergence["value_b_exact"]) == PER_OP_ASTRA
    assert Fraction(divergence["delta_exact"]) == (
        TERM_LATENCY_DELTA + TERM_ENDPOINT_DELTA
    )
