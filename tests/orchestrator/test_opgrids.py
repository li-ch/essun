"""Operating-point grid exactness and range-authority tests (D4).

The registered free-parameter ranges are the AUTHORITY: every coordinate
is an exact Fraction built from written text, floats are rejected, and
out-of-range points are a hard error before any model executes.
"""

from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.orchestrator.opgrids import (
    AssumptionRange,
    GridError,
    build_axis,
    build_fixed,
    expand_operating_points,
    load_numeric_ranges,
    load_ranges,
)

REPO = Path(__file__).resolve().parents[2]
ASSUMPTIONS_L0 = REPO / "experiments" / "vertical_slice" / "assumptions_l0.yaml"


def test_committed_registry_loads_numeric_freedom_only():
    ranges = load_numeric_ranges(ASSUMPTIONS_L0)

    assert ranges["A-L0-BW"].lo == Fraction(1)
    assert ranges["A-L0-BW"].hi == Fraction(1024)
    assert ranges["A-L0-BW"].parameter == "link.bytes_per_ns"
    assert ranges["A-L0-BW"].registry_id == "assumptions_l0_v1"
    # Symbolic identity/behavior choices are NOT numeric freedom.
    assert "A-L0-FD" not in ranges
    assert "A-L0-DIV" not in ranges
    # The workload payload freedom IS numeric.
    assert ranges["A-W1-SIZE"].lo == Fraction(1024)
    assert ranges["A-W1-SIZE"].hi == Fraction(16777216)


def test_all_range_bounds_are_exact_fractions():
    for record in load_numeric_ranges(ASSUMPTIONS_L0).values():
        assert isinstance(record.lo, Fraction) and isinstance(record.hi, Fraction)


def test_float_and_bool_coordinates_are_rejected(tmp_path):
    registry = tmp_path / "assumptions.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "assumptions_id": "t_v1",
                "assumptions": [
                    {
                        "id": "T-BW",
                        "parameter": "link.bytes_per_ns",
                        "value": 64,
                        "range": [1, 1024],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ranges = load_numeric_ranges(registry)
    with pytest.raises(GridError, match="float.*not exact"):
        build_axis(ranges, "T-BW", [1, 64.0, 1024])
    with pytest.raises(GridError, match="boolean"):
        build_axis(ranges, "T-BW", [1, True, 1024])
    with pytest.raises(GridError, match="not an exact 'p/q'"):
        build_axis(ranges, "T-BW", [1, "sixty-four", 1024])


def test_axis_points_must_stay_inside_the_registered_range():
    ranges = load_numeric_ranges(ASSUMPTIONS_L0)
    with pytest.raises(GridError, match="outside the registered range"):
        build_axis(ranges, "A-L0-BW", [1, 2048])  # 2048 > 1024
    with pytest.raises(GridError, match="outside the registered range"):
        build_axis(ranges, "A-L0-LAT", [5, 200])  # 5 < 10


def test_axis_accepts_exact_fraction_strings():
    ranges = load_numeric_ranges(ASSUMPTIONS_L0)
    axis = build_axis(ranges, "A-L0-BW", [1, "1025/2", 1024])  # 512.5 exactly
    assert axis.points == (Fraction(1), Fraction(1025, 2), Fraction(1024))
    assert all(isinstance(point, Fraction) for point in axis.points)


def test_axis_ordering_and_cardinality_gates():
    ranges = load_numeric_ranges(ASSUMPTIONS_L0)
    with pytest.raises(GridError, match="strictly increasing"):
        build_axis(ranges, "A-L0-BW", [64, 64, 128])
    with pytest.raises(GridError, match=">= 2 exact sample"):
        build_axis(ranges, "A-L0-BW", [64])
    with pytest.raises(GridError, match="not a loaded numeric assumption"):
        build_axis(ranges, "A-NOPE", [1, 2])


def test_fixed_parameter_is_range_validated():
    ranges = load_numeric_ranges(ASSUMPTIONS_L0)
    fixed = build_fixed(ranges, "A-L0-BW", 64)
    assert fixed.value == Fraction(64)
    assert fixed.range_lo == Fraction(1) and fixed.range_hi == Fraction(1024)
    with pytest.raises(GridError, match="outside the registered range"):
        build_fixed(ranges, "A-L0-BW", 4096)
    with pytest.raises(GridError, match="float"):
        build_fixed(ranges, "A-L0-BW", 64.5)


def test_registry_collision_is_an_error(tmp_path):
    def write_registry(name: str, assumption_id: str):
        path = tmp_path / name
        path.write_text(
            yaml.safe_dump(
                {
                    "assumptions_id": f"{name}_v1",
                    "assumptions": [
                        {
                            "id": assumption_id,
                            "parameter": "p",
                            "value": 1,
                            "range": [1, 10],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    first = write_registry("a.yaml", "T-SHARED")
    second = write_registry("b.yaml", "T-SHARED")
    with pytest.raises(GridError, match="declared in both"):
        load_ranges([first, second])


def test_mixed_numeric_symbolic_range_is_rejected(tmp_path):
    registry = tmp_path / "mixed.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "assumptions_id": "mixed_v1",
                "assumptions": [
                    {
                        "id": "T-MIXED",
                        "parameter": "p",
                        "value": 1,
                        "range": [1, "half_duplex"],  # numeric-looking, mixed
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(GridError, match="mixed range"):
        load_numeric_ranges(registry)


def test_cartesian_expansion_is_deterministic_and_ordered():
    ranges = {
        "T-ONE": AssumptionRange(
            "r", "T-ONE", "p", "u", "1", Fraction(0), Fraction(10), Path("t.yaml")
        ),
        "T-TWO": AssumptionRange(
            "r", "T-TWO", "q", "u", "2", Fraction(0), Fraction(100), Path("t.yaml")
        ),
        "T-CONST": AssumptionRange(
            "r", "T-CONST", "c", "u", "7", Fraction(0), Fraction(10), Path("t.yaml")
        ),
    }
    axis_one = build_axis(ranges, "T-ONE", [1, 2])
    axis_two = build_axis(ranges, "T-TWO", [10, 20, 30])
    fixed = (build_fixed(ranges, "T-CONST", Fraction(7)),)
    points = expand_operating_points((axis_two, axis_one), fixed)

    assert len(points) == 6
    # Last axis fastest: (10,1), (10,2), (20,1), (20,2), (30,1), (30,2).
    assert [p.axis_values for p in points] == [
        (("T-TWO", Fraction(10)), ("T-ONE", Fraction(1))),
        (("T-TWO", Fraction(10)), ("T-ONE", Fraction(2))),
        (("T-TWO", Fraction(20)), ("T-ONE", Fraction(1))),
        (("T-TWO", Fraction(20)), ("T-ONE", Fraction(2))),
        (("T-TWO", Fraction(30)), ("T-ONE", Fraction(1))),
        (("T-TWO", Fraction(30)), ("T-ONE", Fraction(2))),
    ]
    assert points[0].fixed_value("T-CONST") == Fraction(7)
    assert points[0].axis_value("T-TWO") == Fraction(10)
    assert len({p.point_id for p in points}) == 6
    # Fixed values ride along identically on every point.
    assert {p.fixed_values for p in points} == {
        (("T-CONST", Fraction(7)),)
    }


def test_expansion_gates_duplicate_and_shadowed_axes():
    ranges = {
        "T-ONE": AssumptionRange(
            "r", "T-ONE", "p", "u", "1", Fraction(0), Fraction(10), Path("t.yaml")
        ),
    }
    axis = build_axis(ranges, "T-ONE", [1, 2])
    with pytest.raises(GridError, match="declared twice"):
        expand_operating_points((axis, axis), ())
    with pytest.raises(GridError, match="both as an axis and as a fixed"):
        expand_operating_points((axis,), (build_fixed(ranges, "T-ONE", 1),))
    with pytest.raises(GridError, match="at least one freedom axis"):
        expand_operating_points((), ())
