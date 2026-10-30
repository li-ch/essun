"""Envelope runner tests: capability gates, exact grid identities, and the
REAL two-sided rank crossing between the L0.5 serialized ring and the TFC
credit-window ring (both at r = 8, closed-form boundary 12800 bytes).

Every expected value in the happy-path tests is derived HERE by exact
Fraction arithmetic from the landed identities, so a drift in either the
runner or the backends fails the test.
"""

from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.contracts import load_yaml
from essun.orchestrator import envelopes
from essun.orchestrator.envelopes import (
    ENVELOPE_MODELS,
    EnvelopeError,
    _evaluate_model,
    ModelEntry,
    run_envelope,
)
from essun.orchestrator.sweeps import ALGORITHMS
from essun.workload import w1

REPO = Path(__file__).resolve().parents[2]
F = Fraction

TP8_WORKLOAD = "experiments/workloads/w1_dense_tp_decode_tp8.yaml"
REGISTRIES = [
    "experiments/vertical_slice/assumptions_l0.yaml",
    "experiments/vertical_slice/assumptions_l05.yaml",
    "experiments/vertical_slice/assumptions_tfc.yaml",
]


def base_manifest() -> dict:
    return {
        "envelope": "test_envelope_r8",
        "workload": TP8_WORKLOAD,
        "assumption_registries": list(REGISTRIES),
        "observable": "O-CCT",
        "fixed": [
            {"assumption": "A-L0-BW", "value": 64},
            {"assumption": "A-L0-LAT", "value": 200},
            {"assumption": "A-L05-BW", "value": 64},
            {"assumption": "A-L05-LAT", "value": 200},
            {"assumption": "A-L05-INJ", "value": 64},
            {"assumption": "A-TFC-BW", "value": 64},
            {"assumption": "A-TFC-LAT", "value": 200},
            {"assumption": "A-TFC-CR", "value": 200},
        ],
        "axes": [
            {"assumption": "A-TFC-W", "points": [256, 6400, 12800, 25600, 51200]}
        ],
        "models": [
            {
                "model": "ring",
                "algorithm": "allreduce_ring",
                "topology": "experiments/topologies/ring8_free_params.yaml",
                "binds": {
                    "A-L0-BW": "link.bytes_per_ns",
                    "A-L0-LAT": "link.hop_latency_ns",
                },
            },
            {
                "model": "l05",
                "algorithm": "envelope_l05_ring",
                "topology": "experiments/topologies/ring8_l05_free_params.yaml",
                "binds": {
                    "A-L05-BW": "link.bytes_per_ns",
                    "A-L05-LAT": "link.hop_latency_ns",
                    "A-L05-INJ": "nic.injection_bytes_per_ns",
                },
            },
            {
                "model": "tfc",
                "algorithm": "envelope_tfc_ring",
                "topology": "experiments/topologies/ring8_tfc_window_v1.yaml",
                "binds": {
                    "A-TFC-BW": "link.bytes_per_ns",
                    "A-TFC-LAT": "link.hop_latency_ns",
                    "A-TFC-W": "tfc.window_bytes",
                    "A-TFC-CR": "tfc.credit_return_latency_ns",
                },
            },
        ],
        "boundary_pairs": [["tfc", "l05"], ["tfc", "ring"]],
    }


def write_manifest(manifest: dict, tmp_path: Path) -> Path:
    path = tmp_path / "envelope.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def test_registry_cannot_drift_from_the_sweep_runner():
    assert set(ENVELOPE_MODELS) >= set(ALGORITHMS)
    for algorithm_id, spec in ALGORITHMS.items():
        assert ENVELOPE_MODELS[algorithm_id].backend_id == spec.module.BACKEND_ID
        assert ENVELOPE_MODELS[algorithm_id].topology_classes == spec.topology_classes
    # The two envelope-only ring refinements.
    assert ENVELOPE_MODELS["envelope_l05_ring"].backend_id == "analytical_l05"
    assert ENVELOPE_MODELS["envelope_tfc_ring"].backend_id == "analytical_l0_tfc"


def test_happy_path_values_are_exact_and_hand_computed(tmp_path):
    """r=8, M=16384, B=64, L=200, I=64, L_cr=200 — closed forms:

    T   = 2*(r-1)/r * M = 28672 bytes (all three comparators)
    ring:  T/B + 2*(r-1)*L        =  448 + 2800 = 3248 ns
    l05:   ring + T/I             = 3696 ns
    tfc:   T/min(B, W/400) + 2800 for W in {256, 6400, 12800, 25600, 51200}
    """
    result = run_envelope(
        write_manifest(base_manifest(), tmp_path), results_root=tmp_path / "results"
    )
    table = result["table"]

    by_model_point = {
        (row["model"], row["axis_values_exact"][0][1]): row["o_cct_ns_mean_exact"]
        for row in table["evaluations"]
    }
    for window in ("256", "6400", "12800", "25600", "51200"):
        assert by_model_point[("ring", window)] == "3248"
        assert by_model_point[("l05", window)] == "3696"
    assert by_model_point[("tfc", "256")] == "47600"
    assert by_model_point[("tfc", "6400")] == "4592"
    assert by_model_point[("tfc", "12800")] == "3696"  # tie with l05: the boundary
    assert by_model_point[("tfc", "25600")] == "3248"  # convergence to the ring
    assert by_model_point[("tfc", "51200")] == "3248"

    # The runner evaluated through the real backends: backend ids present.
    assert {m["backend_id"] for m in table["models"]} == {
        "analytical_l0",
        "analytical_l05",
        "analytical_l0_tfc",
    }
    # Framing fences on the artifact.
    assert table["evidence_level"] == "E0"
    assert table["status"] == "PROPOSED"


def test_real_two_sided_crossing_l05_vs_tfc_at_exact_boundary(tmp_path):
    """The REAL planted-in-code two-sided crossing: TFC ring vs L0.5 ring flip at
    exactly W* = (L+L_cr) * B*I/(B+I) = 400 * 2048/128 = 12800 bytes.

    TFC ranks worse below W* (window-limited), ties AT W* (both rates
    equal 1/32 per ns), and ranks better above (window ungated, L0.5 keeps
    paying T/I).
    """
    result = run_envelope(
        write_manifest(base_manifest(), tmp_path), results_root=tmp_path / "results"
    )
    flips = [
        r for r in result["table"]["boundaries"] if r["pair"] == ["tfc", "l05"]
    ]
    regions = [
        r for r in result["table"]["regions"] if r["pair"] == ["tfc", "l05"]
    ]

    assert len(flips) == 2  # + -> 0 -> - : two sign changes, one boundary
    assert {flip["boundary_exact"] for flip in flips} == {"12800"}
    assert all(flip["boundary_verified"] for flip in flips)
    # Regions: worse on [256, 6400], tie at 12800, better on [25600, 51200].
    assert [
        (region["sign"], region["from_exact"], region["to_exact"])
        for region in regions
    ] == [
        (1, "256", "6400"),
        (0, "12800", "12800"),
        (-1, "25600", "51200"),
    ]


def test_tfc_vs_ring_flips_at_the_bandwidth_delay_product(tmp_path):
    result = run_envelope(
        write_manifest(base_manifest(), tmp_path), results_root=tmp_path / "results"
    )
    flips = [
        r for r in result["table"]["boundaries"] if r["pair"] == ["tfc", "ring"]
    ]
    assert len(flips) == 1
    assert flips[0]["boundary_exact"] == "25600"  # B*(L+L_cr) = 64*400
    assert flips[0]["boundary_verified"] is True
    regions = [
        r for r in result["table"]["regions"] if r["pair"] == ["tfc", "ring"]
    ]
    assert [(r["sign"], r["from_exact"], r["to_exact"]) for r in regions] == [
        (1, "256", "12800"),
        (0, "25600", "51200"),
    ]


# ---------------------------------------------------------------------------
# Capability and validation gates (each fires BEFORE anything executes)
# ---------------------------------------------------------------------------


def test_unknown_algorithm_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["models"][0]["algorithm"] = "allreduce_quantum"
    with pytest.raises(EnvelopeError, match="unknown algorithm"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_undeclared_fabric_pairing_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["models"][0]["topology"] = "experiments/topologies/crossbar8_free_params.yaml"
    with pytest.raises(EnvelopeError, match="not.*declared for topology_class"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_ranks_mismatch_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["models"][0]["topology"] = "experiments/topologies/ring16_free_params.yaml"
    with pytest.raises(EnvelopeError, match="tp_size 8 != topology ranks 16"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_out_of_range_axis_point_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["axes"][0]["points"] = [200, 6400]  # 200 < registered floor 256
    with pytest.raises(EnvelopeError, match="outside the registered range"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_float_axis_point_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["axes"][0]["points"] = [256.5, 6400]
    with pytest.raises(EnvelopeError, match="float.*not exact"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_bind_to_absent_knob_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["models"][2]["binds"]["A-TFC-W"] = "tfc.not_a_knob"
    with pytest.raises(EnvelopeError, match="not a knob of topology"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_axis_reaching_no_model_is_rejected(tmp_path):
    manifest = base_manifest()
    # A-W1-SIZE is registered numeric freedom (assumptions_l0.yaml) that no
    # model in this manifest binds as a knob — the axis would vary nothing.
    manifest["axes"][0] = {"assumption": "A-W1-SIZE", "points": [1024, 16384]}
    with pytest.raises(EnvelopeError, match="bound by no model"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_fixed_parameter_reaching_nothing_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["fixed"].append({"assumption": "A-W1-SIZE", "value": 16384})
    with pytest.raises(EnvelopeError, match="reaches no model"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_boundary_pair_gates(tmp_path):
    unknown = base_manifest()
    unknown["boundary_pairs"] = [["tfc", "ghost"]]
    with pytest.raises(EnvelopeError, match="unknown model"):
        run_envelope(write_manifest(unknown, tmp_path), results_root=tmp_path)

    self_pair = base_manifest()
    self_pair["boundary_pairs"] = [["tfc", "tfc"]]
    with pytest.raises(EnvelopeError, match="two distinct models"):
        run_envelope(write_manifest(self_pair, tmp_path), results_root=tmp_path)

    duplicate = base_manifest()
    duplicate["boundary_pairs"] = [["tfc", "ring"], ["ring", "tfc"]]
    with pytest.raises(EnvelopeError, match="duplicate boundary pair"):
        run_envelope(write_manifest(duplicate, tmp_path), results_root=tmp_path)


def test_unsupported_observable_is_rejected(tmp_path):
    manifest = base_manifest()
    manifest["observable"] = "O-CONSERVATION"
    with pytest.raises(EnvelopeError, match="O-CCT only"):
        run_envelope(write_manifest(manifest, tmp_path), results_root=tmp_path)


def test_non_divisible_payload_is_rejected_by_the_evaluation_gate(tmp_path):
    entry = ModelEntry(
        model_id="tfc",
        model=ENVELOPE_MODELS["envelope_tfc_ring"],
        topology_path=REPO / "experiments/topologies/ring8_tfc_window_v1.yaml",
        topology_sha256="0" * 64,
        binds={
            "A-TFC-BW": ("link", "bytes_per_ns"),
            "A-TFC-LAT": ("link", "hop_latency_ns"),
            "A-TFC-W": ("tfc", "window_bytes"),
            "A-TFC-CR": ("tfc", "credit_return_latency_ns"),
        },
    )
    workload_config = w1.load_w1_config(REPO / TP8_WORKLOAD)
    with pytest.raises(EnvelopeError, match="not divisible"):
        _evaluate_model(
            entry,
            {"A-TFC-W": F(12800)},
            {"A-TFC-BW": F(64), "A-TFC-LAT": F(200), "A-TFC-CR": F(200)},
            payload_bytes=16385,  # 8 does not divide 16385
            workload_config=workload_config,
        )


def test_rerun_into_the_same_root_is_idempotent(tmp_path):
    manifest_path = write_manifest(base_manifest(), tmp_path)
    first = run_envelope(manifest_path, results_root=tmp_path)
    second = run_envelope(manifest_path, results_root=tmp_path)
    assert first["envelope_id"] == second["envelope_id"]
    assert first["artifact_sha256"] == second["artifact_sha256"]


def test_manifest_yaml_must_be_a_mapping(tmp_path):
    path = tmp_path / "not_a_map.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(EnvelopeError, match="not a mapping"):
        run_envelope(path, results_root=tmp_path)
