"""T012 second increment: the logical-traffic class and the statistical
(bounded ratio-vs-bound) builtin.

Policy semantics pinned here, mirroring test_registry.py's per-kind tests:
- logical: FAIL = structural violation of the declared algorithm relation
  (raises: a bug); WARN = advisory value beyond the spec's warn_threshold
  (a returned finding, never a raise); spec and observation must agree on
  whether an advisory quantity exists at all;
- bounded relative form: |value/expected - 1| <= tolerance inside the
  declared validity domain; violations are findings; expected=0 is a
  contract error (undefined ratio), not a finding.

Golden values are hand-derived from the frozen identities and committed
free parameters (r = 8, B = 64 bytes/ns, L = 200 ns, M = 16384, 6 ops):
per-rank wire per op 2*(7/8)*16384 = 28672 B; per-rank total 6*28672 =
172032 B; ring CCT 3248 ns; crossbar CCT 848 ns; relative deviation of the
crossbar vs the ring (848-3248)/3248 = -150/203.
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.backends.analytical import l0
from essun.observables import (
    BOUNDED,
    LOGICAL,
    RELATIVE,
    ObservableSpec,
    ObservableViolationError,
    ValidityDomain,
    O_CCT_RELERR,
    O_TRAFFIC_IMBALANCE,
    check,
    differential_observation,
    lookup,
    register,
)
from essun.orchestrator import runs as orch
from essun.orchestrator.sweeps import run_sweep
from essun.workload import w1

REPO = Path(__file__).resolve().parents[2]
LOGICAL_MANIFEST = REPO / "experiments" / "vertical_slice" / "w1_decode_logical_traffic.yaml"
SWEEP_MANIFEST = REPO / "experiments" / "sweeps" / "l0_allreduce_design_space_v1.yaml"

RANKS = 8
OPS = 6  # 2 layers x 3 steps
PER_RANK_PER_OP = Fraction(2 * 7 * 16384, 8)  # 28672
PER_RANK_TOTAL = OPS * PER_RANK_PER_OP  # 172032
RING_CCT = Fraction(3248)
CROSSBAR_CCT = Fraction(848)


# --- built-in registrations -------------------------------------------------


def test_logical_traffic_builtin_registered():
    assert "O-TRAFFIC-IMBALANCE" in __import__("essun.observables", fromlist=["registered"]).registered()
    spec = lookup("O-TRAFFIC-IMBALANCE")
    assert spec.kind == LOGICAL
    assert spec.unit == "bytes"
    assert spec.failure_policy == "exact_relation_violation_is_bug_with_warn"
    # The relation cites the exact pattern obligation under the declared
    # algorithm, and the description carries the O6 honesty label.
    assert "per-rank" in spec.relation and "0 bytes" in spec.relation
    assert "ALGEBRAIC SELF-CHECK" in spec.description
    assert "NOT an independent physical" in spec.description


def test_cct_relerr_builtin_registered():
    spec = lookup("O-CCT-RELERR")
    assert spec.kind == BOUNDED
    assert spec.unit == "ratio"
    assert spec.form == RELATIVE
    assert spec.failure_policy == "tolerance_and_validity_domain"
    # E0 zero-slack policy: every nonzero relative deviation is a finding.
    assert spec.tolerance == Fraction(0)
    assert spec.validity_domain.is_declared()
    assert spec.validity_domain.parameters


# --- logical kind: failure policy (FAIL vs WARN) -----------------------------


def _logical_observation(**overrides):
    observation = {
        "kind": "logical",
        "ranks": RANKS,
        "per_rank_total_wire_bytes_exact": [str(PER_RANK_TOTAL)] * RANKS,
        "imbalance_bytes_exact": "0",
        "max_over_min_exact": "1",
        "violations": 0,
    }
    observation.update(overrides)
    return observation


def test_logical_clean_observation_passes():
    result = check(O_TRAFFIC_IMBALANCE, _logical_observation())
    assert result.status == "pass"
    assert result.observable_id == "O-TRAFFIC-IMBALANCE"
    assert "per-rank" in result.detail


def test_logical_violation_raises_as_bug():
    # FAIL: a structural pattern violation is a bug, raised — same severity
    # channel as exact observables.
    with pytest.raises(ObservableViolationError, match="bug"):
        check(O_TRAFFIC_IMBALANCE, _logical_observation(violations=1))


def test_logical_observation_missing_violations_field_rejected():
    observation = _logical_observation()
    del observation["violations"]
    with pytest.raises(ValueError, match="violations"):
        check(O_TRAFFIC_IMBALANCE, observation)


def test_logical_without_relation_rejected_at_registration():
    with pytest.raises(ValueError, match="relation"):
        register(ObservableSpec(observable_id="O-TEST-LOGICAL-NOREL", kind=LOGICAL, unit="bytes"))


def test_logical_negative_warn_threshold_rejected_at_registration():
    with pytest.raises(ValueError, match="warn_threshold"):
        register(
            ObservableSpec(
                observable_id="O-TEST-LOGICAL-NEGTOL",
                kind=LOGICAL,
                unit="bytes",
                relation="test relation",
                warn_threshold=Fraction(-1),
            )
        )


def _warn_spec():
    # Class-level WARN channel proven with a test-registered spec (the same
    # pattern test_registry.py uses for the bounded policy): the L0 builtin
    # declares warn_threshold=None, so the channel needs its own spec here.
    return register(
        ObservableSpec(
            observable_id="O-TEST-LOGICAL-WARN",
            kind=LOGICAL,
            unit="ratio",
            relation="test relation: pattern uniform under declared algorithm",
            warn_threshold=Fraction(1, 10),
        )
    )


def test_logical_advisory_beyond_threshold_is_warn_not_raise():
    spec = _warn_spec()
    result = check(spec, {"kind": "logical", "violations": 0, "warn_value": "1/2"})
    assert result.status == "warn"
    assert "1/2" in result.detail and "1/10" in result.detail
    # A WARN is a finding for domain refinement: check must NOT raise.
    assert isinstance(result.detail, str)


def test_logical_advisory_within_threshold_passes():
    spec = _warn_spec()
    result = check(spec, {"kind": "logical", "violations": 0, "warn_value": "1/20"})
    assert result.status == "pass"


def test_logical_warn_value_contract_mismatches_rejected():
    spec = _warn_spec()
    with pytest.raises(ValueError, match="warn_value"):
        check(spec, {"kind": "logical", "violations": 0})  # threshold declared, value missing
    with pytest.raises(ValueError, match="warn_threshold"):
        # the builtin declares no advisory quantity; carrying one is a
        # contract mismatch, not a finding
        check(O_TRAFFIC_IMBALANCE, _logical_observation(warn_value="1/2"))


def test_logical_kind_mismatch_rejected():
    with pytest.raises(ValueError, match="declares kind"):
        check(O_TRAFFIC_IMBALANCE, {"kind": "exact", "violations": 0})


# --- bounded relative form (statistical class, ratio vs bound) ---------------


def test_bounded_relative_within_tolerance_passes_exactly():
    # Class-level pass case with slack: |107/100 - 100/100| = 7/100 <= 1/10,
    # decided by exact Fraction arithmetic on the ratio.
    spec = register(
        ObservableSpec(
            observable_id="O-TEST-RELFORM",
            kind=BOUNDED,
            unit="ratio",
            tolerance=Fraction(1, 10),
            form=RELATIVE,
            validity_domain=ValidityDomain(topology="ring8_free_v1"),
        )
    )
    result = check(spec, {"kind": "bounded", "value": "107/100", "expected": "100/100"})
    assert result.status == "pass"
    assert "7/100" in result.detail


def test_bounded_relative_zero_reference_is_contract_error():
    spec = register(
        ObservableSpec(
            observable_id="O-TEST-RELFORM0",
            kind=BOUNDED,
            unit="ratio",
            tolerance=Fraction(1, 10),
            form=RELATIVE,
            validity_domain=ValidityDomain(topology="ring8_free_v1"),
        )
    )
    with pytest.raises(ValueError, match="expected=0"):
        check(spec, {"kind": "bounded", "value": "5", "expected": "0"})


def test_bounded_unknown_form_rejected_at_registration():
    with pytest.raises(ValueError, match="form"):
        register(
            ObservableSpec(
                observable_id="O-TEST-BADFORM",
                kind=BOUNDED,
                unit="ratio",
                tolerance=Fraction(0),
                form="percentile",
                validity_domain=ValidityDomain(topology="ring8_free_v1"),
            )
        )


def test_cct_relerr_zero_deviation_passes_under_zero_slack():
    # Golden: identical replays of the same backend/config have relative
    # error 0 <= tolerance 0.
    observation = differential_observation(RING_CCT, RING_CCT)
    assert observation["kind"] == "bounded"
    result = check(O_CCT_RELERR, observation)
    assert result.status == "pass"
    assert "relerr" in result.detail and "|relerr|=0" in result.detail


def test_cct_relerr_nonzero_deviation_is_a_finding_not_a_raise():
    # Negative (policy fires): crossbar 848 ns vs ring reference 3248 ns ->
    # |848/3248 - 1| = 150/203 > tolerance 0 -> VIOLATION returned as a
    # counterexample candidate, never raised (bounded policy).
    observation = differential_observation(CROSSBAR_CCT, RING_CCT)
    result = check(O_CCT_RELERR, observation)
    assert result.status == "violation"
    assert "150/203" in result.detail
    assert "tolerance=0" in result.detail


# --- backend emission + wiring through the run path --------------------------


def _ops():
    config = w1.W1Config(tp_size=RANKS, layers=2, steps=3, allreduce_bytes=16384)
    return w1.generate_w1_ops(config)


def _infra():
    return l0.InfraConfig(
        topology_id="ring8_free_v1",
        ranks=RANKS,
        link_bytes_per_ns=Fraction(64),
        hop_latency_ns=Fraction(200),
    )


def test_ring_per_rank_totals_hand_derived():
    # Single op: every rank sends 2*(7/8)*16384 = 28672 B.
    single = l0.ring_per_rank_totals(_ops()[:1], RANKS)
    assert single == (PER_RANK_PER_OP,) * RANKS
    # Full run (6 ops): every rank sends 6*28672 = 172032 B — the pattern
    # the imbalance observable is defined over.
    totals = l0.ring_per_rank_totals(_ops(), RANKS)
    assert totals == (PER_RANK_TOTAL,) * RANKS
    assert max(totals) - min(totals) == 0


def test_l0_execute_emits_logical_traffic_observable():
    result = l0.execute(_ops(), _infra())
    assert "O-TRAFFIC-IMBALANCE" in l0.CAPABILITIES["observables"]
    imbalance = result["observables"]["O-TRAFFIC-IMBALANCE"]
    assert imbalance["kind"] == "logical"
    assert imbalance["ranks"] == RANKS
    assert imbalance["per_rank_total_wire_bytes_exact"] == [str(PER_RANK_TOTAL)] * RANKS
    assert imbalance["imbalance_bytes_exact"] == "0"
    assert imbalance["max_over_min_exact"] == "1"
    assert imbalance["violations"] == 0
    # Existing observables are unchanged by the addition.
    assert result["observables"]["O-CONSERVATION"]["total_wire_bytes_exact"] == str(
        Fraction(OPS * 2 * 7 * 16384)
    )
    assert result["observables"]["O-CCT"]["completion_time_ns_mean_exact"] == str(RING_CCT)


def test_logical_manifest_runs_through_run_path(tmp_path):
    # Wiring: the committed manifest declares O-TRAFFIC-IMBALANCE; the run
    # path dispatches the ring backend, gates the observation through the
    # registry (an exact/logical violation would raise), and persists it.
    first = orch.run_experiment(LOGICAL_MANIFEST, results_root=tmp_path / "a")
    assert first["observations"]["backend_id"] == "analytical_l0"
    imbalance = first["observations"]["observables"]["O-TRAFFIC-IMBALANCE"]
    assert imbalance["kind"] == "logical"
    assert imbalance["per_rank_total_wire_bytes_exact"] == [str(PER_RANK_TOTAL)] * RANKS
    assert imbalance["imbalance_bytes_exact"] == "0"
    assert imbalance["violations"] == 0
    # The run record declares the observable and links to claim C2.
    record = json.loads((first["run_dir"] / "run.json").read_text(encoding="utf-8"))
    assert record["manifest"]["observables"] == [
        "O-CONSERVATION",
        "O-CCT",
        "O-TRAFFIC-IMBALANCE",
    ]
    # Deterministic replay: identical manifest -> identical run_id and bytes.
    second = orch.run_experiment(LOGICAL_MANIFEST, results_root=tmp_path / "b")
    assert second["run_id"] == first["run_id"]
    for artifact in ("observations.json", "run.json"):
        left = (tmp_path / "a" / first["run_id"] / artifact).read_bytes()
        right = (tmp_path / "b" / second["run_id"] / artifact).read_bytes()
        assert left == right


def test_run_path_rejects_logical_observable_on_unsupported_backend(tmp_path):
    # Negative (wiring gate fires): a backend that does not declare the
    # logical observable must reject the manifest loudly, before execution.
    data = yaml.safe_load(LOGICAL_MANIFEST.read_text(encoding="utf-8"))
    data["backends"] = ["analytical_l0_torus2d"]
    variant = tmp_path / "logical_unsupported.yaml"
    variant.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(orch.ExecutionError, match="O-TRAFFIC-IMBALANCE"):
        orch.run_experiment(variant, results_root=tmp_path / "results")


# --- differential-validation usability on real sweep output -------------------


def test_cct_relerr_consumes_real_sweep_output(tmp_path):
    # The ratio-vs-bound builtin is usable by the differential-validation
    # path: run the committed sweep, take two real cells' mean CCT at the
    # same payload size, and check the bounded relative-form observation
    # built from them (sweep deltas are the quantity this observable
    # formalizes).
    result = run_sweep(SWEEP_MANIFEST, results_root=tmp_path)
    table = json.loads((result["sweep_dir"] / "table.json").read_text(encoding="utf-8"))

    def cct_mean(algorithm: str) -> Fraction:
        cell = next(
            c
            for c in table["configs"]
            if c["algorithm"] == algorithm and c["payload_bytes"] == 16384
        )
        return Fraction(cell["o_cct"]["completion_time_ns_mean_exact"])

    ring, crossbar = cct_mean("allreduce_ring"), cct_mean("allreduce_crossbar")
    assert (ring, crossbar) == (RING_CCT, CROSSBAR_CCT)
    observation = differential_observation(crossbar, ring)
    finding = check(O_CCT_RELERR, observation)
    assert finding.status == "violation"  # a finding, not a raise
    assert "150/203" in finding.detail
