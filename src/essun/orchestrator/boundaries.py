"""Exact-Fraction ranking-boundary detection over operating-point grids (D4).

A BOUNDARY is an exact coordinate on a freedom axis where the ranking
relation of two named comparators (profiles, algorithms, or model
identities) CHANGES: the exact three-way sign of ``d = value_a - value_b``
differs between adjacent grid points, with every other axis held at its
exact value. Most boundaries in the landed L0 family are SATURATION
BOUNDARIES (credit-provisioning thresholds), not two-sided ranking
crossings: on one side comparator A ranks strictly worse (``d > 0`` for
the completion-time observable O-CCT), on the other side the two tie
exactly (``d == 0``) — A is never faster than B there. The detector
reports the sign table and never names a saturation boundary a
``reversal``: a true rank-order crossing (strictly worse to strictly
better) requires ``d`` to change sign through zero on BOTH sides, which
the exact sign table distinguishes by construction.

Renamed from ``reversals.py`` (G6, 2026-10-30): the landed window
comparison is a penalty-then-tie saturation boundary — tie at and above
W* = B*(L+L_cr), strictly worse below — and the former name claimed a
crossing the arithmetic never produced. Detection semantics, exact
arithmetic, and all outputs are unchanged; only the name is honest now.

Everything here is :class:`fractions.Fraction` arithmetic — there are NO
floats in the identity math (floats appear only downstream, as display
mirrors in artifacts, never in comparisons, boundaries, or regions).

Detector semantics (stated so a challenger can attack them):

1. GRID EVIDENCE ONLY. The detector reports what the grid shows: signs of
   ``d`` at exact sample points, and the bracketing interval of every sign
   change. It never interpolates and never assumes smoothness.
2. EXACT BOUNDARY RESOLUTION, VERIFIED. For a bracketing pair
   ``(x1, x2)`` with ``d(x1) != d(x2)``, the secant root
   ``x* = x1 - d(x1)*(x2-x1)/(d(x2)-d(x1))`` is computed exactly. If the
   difference is affine in the axis coordinate (or in ``1/x`` — every
   landed L0-family rate term is affine in ``1/B``), the secant root IS
   the root; the detector then RE-EVALUATES ``d`` at ``x*`` and accepts
   the boundary only if ``d(x*) == 0`` exactly and ``x*`` lies inside the
   bracket. Both the ``x`` and the ``1/x`` reading are tried; a root that
   fails exact verification is reported as unresolved (bracket only), so
   the detector can never launder an assumed functional form into a fake
   exact boundary.
3. SIGN CONVENTION. ``sign > 0`` means comparator A ranks WORSE on the
   metric (A's value minus B's value is positive — for the completion-time
   observable O-CCT, larger is worse). ``sign == 0`` is an exact TIE at
   the grid point, itself evidence (two identities numerically equal).

Evidence level E0 ONLY: a boundary is a statement about the RANKING OF
ANALYTICAL MODEL IDENTITIES under declared freedom — never a statement
about measured behavior on any system, and never hardware language.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

ExactMetric = Callable[[Fraction], Fraction]


def sign(value: Fraction) -> int:
    """Exact three-way sign: -1, 0, or +1."""
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


@dataclass(frozen=True)
class Flip:
    """One sign change of ``d = value_a - value_b`` along one axis."""

    axis: str
    slice_values: tuple[tuple[str, Fraction], ...]  # other axes, exact
    x_lo: Fraction  # bracketing grid coordinate (smaller)
    x_hi: Fraction  # bracketing grid coordinate (larger)
    d_lo: Fraction  # exact difference at x_lo
    d_hi: Fraction  # exact difference at x_hi
    sign_lo: int
    sign_hi: int
    boundary: Fraction | None  # exact root, only when verified below
    boundary_verified: bool
    boundary_method: str  # "affine-x-verified" | "affine-reciprocal-verified" | "unresolved"

    def as_dict(self) -> dict:
        return {
            "axis": self.axis,
            "slice_values_exact": [
                [aid, str(value)] for aid, value in self.slice_values
            ],
            "bracket_exact": [str(self.x_lo), str(self.x_hi)],
            "difference_exact": [str(self.d_lo), str(self.d_hi)],
            "sign_lo": self.sign_lo,
            "sign_hi": self.sign_hi,
            "boundary_exact": None if self.boundary is None else str(self.boundary),
            "boundary_verified": self.boundary_verified,
            "boundary_method": self.boundary_method,
        }


@dataclass(frozen=True)
class Region:
    """A maximal span of consecutive grid points with one exact sign."""

    axis: str
    slice_values: tuple[tuple[str, Fraction], ...]
    sign_value: int
    from_x: Fraction
    to_x: Fraction

    def as_dict(self) -> dict:
        return {
            "axis": self.axis,
            "slice_values_exact": [
                [aid, str(value)] for aid, value in self.slice_values
            ],
            "sign": self.sign_value,
            "sign_reading": {
                1: "comparator_a_ranks_worse",
                0: "exact_tie",
                -1: "comparator_a_ranks_better",
            }[self.sign_value],
            "from_exact": str(self.from_x),
            "to_exact": str(self.to_x),
        }


def _try(f: ExactMetric, x: Fraction) -> Fraction | None:
    """Evaluate the real difference at x; None when the models reject x.

    A secant candidate that a comparator's own gates refuse (e.g. a TFC
    window that is not an integral number of credit units) cannot be
    verified, so it is treated as unverifiable — never an error and never
    a fabricated zero.
    """
    try:
        return f(x)
    except Exception:
        return None


def _secant_root(
    f: ExactMetric, x1: Fraction, x2: Fraction
) -> tuple[Fraction | None, bool, str]:
    """Exact secant root with mandatory re-verification, in x or in 1/x.

    Returns ``(root, verified, method)``. ``root`` is None when no
    candidate root verifies exactly. The reciprocal reading covers the
    L0-family structure (rate terms affine in 1/B, 1/W, ...); trying both
    is safe precisely because acceptance requires an exact zero check.
    """
    d1, d2 = _try(f, x1), _try(f, x2)
    if d1 is None or d2 is None or d1 == d2:
        return None, False, "unresolved"  # no comparable bracket

    # Reading 1: affine in x.
    root = x1 - d1 * (x2 - x1) / (d2 - d1)
    if x1 <= root <= x2:
        checked = _try(f, root)
        if checked == 0:
            return root, True, "affine-x-verified"

    # Reading 2: affine in 1/x (x > 0 on every declared freedom axis).
    if x1 > 0 and x2 > 0:
        u1, u2 = 1 / x1, 1 / x2
        e1, e2 = d1, d2  # same values, at u1/u2 respectively
        if e1 != e2:
            u_root = u1 - e1 * (u2 - u1) / (e2 - e1)
            if u_root > 0:
                x_root = 1 / u_root
                if x1 <= x_root <= x2:
                    checked = _try(f, x_root)
                    if checked == 0:
                        return x_root, True, "affine-reciprocal-verified"
    return None, False, "unresolved"


def detect_flips(
    axis: str,
    coordinates: list[Fraction],
    differences: list[Fraction],
    slice_values: tuple[tuple[str, Fraction], ...] = (),
) -> tuple[list[Flip], list[Region]]:
    """Find sign changes of an exact difference along ONE ordered axis.

    ``coordinates`` must be strictly increasing and aligned with
    ``differences``. Returns the flips (with verified exact boundaries when
    resolvable) and the maximal constant-sign regions over the grid.
    """
    if len(coordinates) != len(differences):
        raise ValueError("coordinates and differences must align")
    if len(coordinates) < 2:
        raise ValueError("an axis needs >= 2 grid points")

    flips: list[Flip] = []
    for (x_lo, d_lo), (x_hi, d_hi) in zip(
        zip(coordinates, differences), zip(coordinates[1:], differences[1:])
    ):
        sign_lo, sign_hi = sign(d_lo), sign(d_hi)
        if sign_lo == sign_hi:
            continue

        # Boundary resolution happens in resolve_flip_boundary, which needs
        # the REAL difference function (not just the grid samples); here we
        # record the grid evidence only.
        flips.append(
            Flip(
                axis=axis,
                slice_values=slice_values,
                x_lo=x_lo,
                x_hi=x_hi,
                d_lo=d_lo,
                d_hi=d_hi,
                sign_lo=sign_lo,
                sign_hi=sign_hi,
                boundary=None,
                boundary_verified=False,
                boundary_method="unresolved",
            )
        )

    regions: list[Region] = []
    start = 0
    for index in range(1, len(coordinates) + 1):
        changed = index == len(coordinates) or sign(differences[index]) != sign(
            differences[start]
        )
        if changed:
            regions.append(
                Region(
                    axis=axis,
                    slice_values=slice_values,
                    sign_value=sign(differences[start]),
                    from_x=coordinates[start],
                    to_x=coordinates[index - 1],
                )
            )
            start = index
    return flips, regions


def resolve_flip_boundary(
    flip: Flip, difference_at: Callable[[Fraction], Fraction]
) -> Flip:
    """Return a copy of ``flip`` with the boundary resolved exactly, if possible.

    ``difference_at`` evaluates the real comparator difference at ANY exact
    coordinate (it calls the underlying identity functions, so verification
    is exact, not an approximation of the grid).
    """
    root, verified, method = _secant_root(difference_at, flip.x_lo, flip.x_hi)
    if root is None:
        return flip
    return Flip(
        axis=flip.axis,
        slice_values=flip.slice_values,
        x_lo=flip.x_lo,
        x_hi=flip.x_hi,
        d_lo=flip.d_lo,
        d_hi=flip.d_hi,
        sign_lo=flip.sign_lo,
        sign_hi=flip.sign_hi,
        boundary=root,
        boundary_verified=verified,
        boundary_method=method,
    )


def detect_boundaries(
    axis: str,
    coordinates: list[Fraction],
    values_a: list[Fraction],
    values_b: list[Fraction],
    difference_at: Callable[[Fraction], Fraction] | None = None,
    slice_values: tuple[tuple[str, Fraction], ...] = (),
) -> tuple[list[Flip], list[Region]]:
    """Full detector for one axis slice: flips + regions + exact boundaries.

    ``values_a``/``values_b`` are the two comparators' exact metric values
    at the grid ``coordinates``; ``difference_at`` (optional) evaluates the
    difference at arbitrary exact coordinates so boundaries can be
    resolved and VERIFIED exactly. Without it, flips report the bracket
    only (method "unresolved") — grid evidence, no assumed form.
    """
    differences = [a - b for a, b in zip(values_a, values_b)]
    flips, regions = detect_flips(axis, coordinates, differences, slice_values)
    if difference_at is not None:
        flips = [
            resolve_flip_boundary(flip, difference_at) for flip in flips
        ]
    return flips, regions
