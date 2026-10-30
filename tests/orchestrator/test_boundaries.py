"""Boundary-detector tests: PLANTED boundaries must be found EXACTLY.

The detector works on exact Fractions only; boundaries are accepted only
when re-evaluation at the secant root returns exactly zero (in the x or
the 1/x reading), so a planted affine flip must be recovered bit-exactly
and a non-affine difference must stay unresolved (bracket only, never a
fabricated boundary).
"""

from fractions import Fraction

import pytest

from essun.orchestrator.boundaries import (
    detect_flips,
    detect_boundaries,
    resolve_flip_boundary,
    sign,
)

F = Fraction


def test_sign_exact_three_way():
    assert sign(F(3, 7)) == 1
    assert sign(F(-3, 7)) == -1
    assert sign(F(0)) == 0


def test_planted_affine_two_sided_flip_found_exactly():
    """PLANTED: comparator A minus B is d(x) = 12 - 2x, root exactly x = 6.

    The detector must find exactly this flip, resolve the boundary to
    exactly 6, and verify it.
    """
    grid = [F(x) for x in (0, 3, 5, 7, 12)]
    values_a = [F(12) - 2 * x for x in grid]
    values_b = [F(0) for _ in grid]
    difference_at = lambda x: F(12) - 2 * x  # noqa: E731 - the planted metric

    flips, regions = detect_boundaries(
        "T-X", grid, values_a, values_b, difference_at=difference_at
    )

    assert len(flips) == 1
    flip = flips[0]
    assert flip.x_lo == F(5) and flip.x_hi == F(7)
    assert flip.boundary == F(6)
    assert flip.boundary_verified is True
    assert flip.boundary_method == "affine-x-verified"
    assert flip.sign_lo == 1 and flip.sign_hi == -1
    # Regions: A worse on [0, 5], A better on [7, 12].
    assert [(r.sign_value, r.from_x, r.to_x) for r in regions] == [
        (1, F(0), F(5)),
        (-1, F(7), F(12)),
    ]


def test_planted_boundary_landing_on_a_grid_point():
    """Same planted flip with the root exactly ON a grid point."""
    grid = [F(x) for x in (0, 3, 6, 9, 12)]
    values_a = [F(12) - 2 * x for x in grid]
    difference_at = lambda x: F(12) - 2 * x  # noqa: E731

    flips, _ = detect_boundaries(
        "T-X", grid, values_a, [F(0)] * 5, difference_at=difference_at
    )

    # Two adjacent sign changes (+ -> 0 -> -), both resolving to exactly 6.
    assert {flip.boundary for flip in flips} == {F(6)}
    assert all(flip.boundary_verified for flip in flips)


def test_planted_tie_to_worse_flip():
    """PLANTED: ranking goes exact tie -> strictly worse at x = 6.

    d(x) = 6 - x for x < 6 and exactly 0 from x = 6 on: the saturation
    boundary (tie to loss, never a two-sided crossing) must be detected
    with boundary exactly 6.
    """

    def planted(x: Fraction) -> Fraction:
        return F(6) - x if x < 6 else F(0)

    grid = [F(x) for x in (0, 3, 6, 9)]
    values_a = [planted(x) for x in grid]
    flips, regions = detect_boundaries(
        "T-X", grid, values_a, [F(0)] * 4, difference_at=planted
    )

    assert len(flips) == 1
    assert flips[0].sign_lo == 1 and flips[0].sign_hi == 0
    assert flips[0].boundary == F(6)
    assert flips[0].boundary_verified is True
    assert [(r.sign_value, r.from_x, r.to_x) for r in regions] == [
        (1, F(0), F(3)),
        (0, F(6), F(9)),
    ]


def test_no_false_positive_on_one_sided_or_constant_differences():
    grid = [F(x) for x in (1, 2, 3, 4)]
    # Strictly one-sided: A always worse.
    flips, regions = detect_boundaries("T-X", grid, [F(10)] * 4, [F(1)] * 4)
    assert flips == [] and len(regions) == 1 and regions[0].sign_value == 1
    # Exact ties everywhere: no boundary, one tie region.
    flips, regions = detect_boundaries("T-X", grid, [F(5)] * 4, [F(5)] * 4)
    assert flips == [] and regions[0].sign_value == 0


def test_planted_reciprocal_axis_boundary_is_exact():
    """PLANTED: d(B) = 1/B - 1/64 — affine in 1/B, NOT in B.

    On a grid where the plain-x secant candidate misses the root, the
    detector must resolve the boundary through the reciprocal reading and
    verify it at exactly B = 64.
    """

    def planted(b: Fraction) -> Fraction:
        return F(1) / b - F(1, 64)

    grid = [F(24), F(40), F(100)]
    values_a = [planted(b) for b in grid]
    flips, _ = detect_boundaries(
        "T-B", grid, values_a, [F(0)] * 3, difference_at=planted
    )

    assert len(flips) == 1
    flip = flips[0]
    assert flip.boundary == F(64)
    assert flip.boundary_verified is True
    assert flip.boundary_method == "affine-reciprocal-verified"


def test_non_affine_difference_stays_unresolved_bracket_only():
    """PLANTED: d(x) = 4 - (x-6)^2 — curved; no fabricated exact boundary.

    The detector must report both sign changes with their brackets and
    differences, but boundary None / verified False (the secant root does
    not re-evaluate to zero).
    """

    def planted(x: Fraction) -> Fraction:
        return F(4) - (x - 6) ** 2

    grid = [F(0), F(6), F(10)]
    values_a = [planted(x) for x in grid]
    flips, regions = detect_boundaries(
        "T-X", grid, values_a, [F(0)] * 3, difference_at=planted
    )

    assert len(flips) == 2
    assert {flip.boundary for flip in flips} == {None}
    assert all(flip.boundary_verified is False for flip in flips)
    assert all(flip.boundary_method == "unresolved" for flip in flips)
    assert [(flip.x_lo, flip.x_hi) for flip in flips] == [(F(0), F(6)), (F(6), F(10))]
    # Sign table preserved: - on [0,0], + at [6,6], - on [10,10].
    assert [(r.sign_value, r.from_x, r.to_x) for r in regions] == [
        (-1, F(0), F(0)),
        (1, F(6), F(6)),
        (-1, F(10), F(10)),
    ]


def test_grid_only_mode_reports_bracket_without_difference_function():
    grid = [F(1), F(2), F(4)]
    values_a = [F(3), F(1), F(-1)]
    flips, _ = detect_boundaries("T-X", grid, values_a, [F(0)] * 3)
    assert flips and flips[0].boundary is None
    assert flips[0].boundary_method == "unresolved"


def test_rejected_candidate_counts_as_unverifiable():
    """A difference function that RAISES at a candidate root (a model gate
    refusing the coordinate) must not crash and must not verify."""

    def awkward(x: Fraction) -> Fraction:
        if x == F(7, 2):
            raise ValueError("gate refused")
        return x - F(7, 2)

    grid = [F(1), F(6)]
    flips, _ = detect_boundaries(
        "T-X", grid, [awkward(x) for x in grid], [F(0)] * 2, difference_at=awkward
    )
    assert len(flips) == 1
    assert flips[0].boundary is None
    assert flips[0].boundary_verified is False


def test_detect_flips_validates_alignment():
    with pytest.raises(ValueError, match="align"):
        detect_flips("T-X", [F(1), F(2)], [F(1)])
    with pytest.raises(ValueError, match=">= 2"):
        detect_flips("T-X", [F(1)], [F(1)])


def test_resolve_flip_boundary_leaves_unresolved_flip_untouched():
    def curved(x: Fraction) -> Fraction:
        return F(4) - (x - 6) ** 2

    grid = [F(0), F(6)]
    flips, _ = detect_flips("T-X", grid, [curved(x) for x in grid], [F(0), F(0)])
    resolved = resolve_flip_boundary(flips[0], curved)
    assert resolved.boundary is None and resolved.boundary_verified is False
