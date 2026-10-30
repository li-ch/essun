"""Envelope visualization-data tests (G4): EXACTNESS and DETERMINISM.

The data file is the atlas pages' plot source, so it is held to the same
fences as the artifact itself: every ``*_exact`` field must parse as an
exact Fraction and agree with the artifact's evaluations; floats appear
only as derived mirrors; generation is a pure function of the table, so
two runs of the same manifest produce byte-identical data, an existing
file is never silently rewritten, and the sha256 sidecar is the hash of
the exact bytes.
"""

import hashlib
from fractions import Fraction
from pathlib import Path

import yaml

from essun.orchestrator.envviz import (
    DATA_FILENAME,
    DATA_SHA_FILENAME,
    build_envelope_data,
    envelope_data_bytes,
    render_envelopes_page_md,
    write_committed_data,
    write_envelope_data,
)
from essun.orchestrator.envelopes import run_envelope

REPO = Path(__file__).resolve().parents[2]
F = Fraction

TP8_WORKLOAD = "experiments/workloads/w1_dense_tp_decode_tp8.yaml"
REGISTRIES = [
    "experiments/vertical_slice/assumptions_l0.yaml",
    "experiments/vertical_slice/assumptions_l05.yaml",
    "experiments/vertical_slice/assumptions_tfc.yaml",
]


def manifest(tmp_path: Path) -> Path:
    """The test_envelope_r8 shape (r=8 ring/l05/tfc, window axis): one
    saturation boundary (tfc vs ring at 25600) and one two-sided crossing
    (tfc vs l05 through the exact tie at 12800)."""
    body = {
        "envelope": "test_envviz_r8",
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
    path = tmp_path / "envelope.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def _run(tmp_path: Path, subdir: str):
    return run_envelope(manifest(tmp_path), results_root=tmp_path / subdir)


def test_data_generation_is_deterministic_across_runs(tmp_path):
    first = _run(tmp_path, "a")
    second = _run(tmp_path, "b")

    left = first["artifact_dir"] / DATA_FILENAME
    right = second["artifact_dir"] / DATA_FILENAME
    assert left.read_bytes() == right.read_bytes()
    assert (
        first["artifact_dir"] / DATA_SHA_FILENAME
    ).read_bytes() == (second["artifact_dir"] / DATA_SHA_FILENAME).read_bytes()

    # The sidecar is the hash of the exact data bytes.
    data_bytes = left.read_bytes()
    assert (
        hashlib.sha256(data_bytes).hexdigest() + "\n"
        == (first["artifact_dir"] / DATA_SHA_FILENAME).read_text()
    )

    # And so is re-derivation from the table alone (pure function).
    assert envelope_data_bytes(build_envelope_data(first["table"])) == data_bytes


def test_run_envelope_emits_the_data_files(tmp_path):
    result = _run(tmp_path, "results")
    names = {p.name for p in result["artifact_dir"].iterdir()}
    assert {DATA_FILENAME, DATA_SHA_FILENAME} <= names


def test_write_is_idempotent_and_refuses_a_byte_drift(tmp_path):
    result = _run(tmp_path, "results")
    # Same bytes again: no error, no rewrite.
    write_envelope_data(result["table"], result["artifact_dir"])
    # Different table bytes at the same place: refused loudly.
    drifted = dict(result["table"])
    drifted["envelope"] = "drifted_name"
    try:
        write_envelope_data(drifted, result["artifact_dir"])
    except ValueError as exc:
        assert "different bytes" in str(exc)
    else:
        raise AssertionError("a byte drift must be refused, not rewritten")


def test_exact_fields_are_exact_and_match_the_artifact(tmp_path):
    result = _run(tmp_path, "results")
    data = build_envelope_data(result["table"])

    # Every *_exact value parses as an exact Fraction.
    for series in data["series"]:
        points = [F(p) for p in series["points_exact"]]
        values = [F(v) for v in series["values_exact"]]
        assert points == sorted(points)  # axis order
        assert len(points) == len(values) == 5
    # The exact values agree with the artifact's own evaluations.
    artifact_rows = {
        (
            row["model"],
            dict(row["axis_values_exact"])["A-TFC-W"],
        ): row["o_cct_ns_mean_exact"]
        for row in result["table"]["evaluations"]
    }
    for series in data["series"]:
        for point, value in zip(series["points_exact"], series["values_exact"]):
            assert F(artifact_rows[(series["model"], point)]) == F(value)

    # Difference series are exact differences of the exact values.
    by_model_point = {
        (row["model"], dict(row["axis_values_exact"])["A-TFC-W"]): row[
            "o_cct_ns_mean_exact"
        ]
        for row in result["table"]["evaluations"]
    }
    for pair in data["pairs"]:
        model_a, model_b = pair["pair"]
        for point, difference in zip(pair["points_exact"], pair["differences_exact"]):
            expected = F(by_model_point[(model_a, point)]) - F(
                by_model_point[(model_b, point)]
            )
            assert F(difference) == expected
        # The sign table is the exact three-way sign of the differences.
        assert pair["signs"] == [
            1 if F(d) > 0 else (-1 if F(d) < 0 else 0)
            for d in pair["differences_exact"]
        ]


def test_boundaries_and_regions_are_carried_verbatim(tmp_path):
    result = _run(tmp_path, "results")
    data = build_envelope_data(result["table"])

    by_pair = {}
    for pair in data["pairs"]:
        by_pair.setdefault(tuple(pair["pair"]), []).append(pair)

    # Saturation boundary: tfc vs ring flips + -> 0 at exactly 25600.
    tfc_ring = by_pair[("tfc", "ring")][0]
    assert [b["boundary_exact"] for b in tfc_ring["boundaries"]] == ["25600"]
    assert tfc_ring["boundaries"][0]["boundary_verified"] is True
    assert tfc_ring["signs"] == [1, 1, 1, 0, 0]
    assert [r["sign"] for r in tfc_ring["regions"]] == [1, 0]

    # Two-sided crossing: tfc vs l05 goes + -> 0 -> - through 12800.
    tfc_l05 = by_pair[("tfc", "l05")][0]
    assert tfc_l05["signs"] == [1, 1, 0, -1, -1]
    assert {b["boundary_exact"] for b in tfc_l05["boundaries"]} == {"12800"}

    # The data file pins itself to the artifact's exact bytes.
    assert (
        data["artifact_boundary_json_sha256"] == result["artifact_sha256"]
    )


def test_committed_data_copies_are_byte_identical_to_the_artifact_copy(tmp_path):
    result = _run(tmp_path, "results")
    data_dir = write_committed_data(result["table"], tmp_path / "committed")
    for name in (DATA_FILENAME, DATA_SHA_FILENAME):
        committed = data_dir / f"{result['table']['envelope']}.{name}"
        assert committed.read_bytes() == (result["artifact_dir"] / name).read_bytes()


def test_page_rendering_is_deterministic_and_e0_framed(tmp_path):
    first = _run(tmp_path, "a")
    second = _run(tmp_path, "b")

    page_left = render_envelopes_page_md([first["table"]])
    page_right = render_envelopes_page_md([second["table"]])
    assert page_left == page_right

    assert "E0" in page_left
    for fence in ("measured", "hardware"):
        # The fence statements say what the page is NOT.
        assert fence in page_left
    # Boundary language only: the G6-renamed concept never appears.
    assert "reversal" not in page_left.lower()
    # The decision-relevant numbers render.
    assert "25600" in page_left  # tfc-vs-ring saturation boundary
    assert "12800" in page_left  # tfc-vs-l05 crossing
