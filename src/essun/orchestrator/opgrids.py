"""Operating-point grids over DECLARED freedom ranges (design doc D4, 2026-10-29).

The registered free-parameter ranges are the authority: an assumption
registry (YAML, e.g. ``experiments/vertical_slice/assumptions_l0.yaml``,
``assumptions_l05.yaml``, ``assumptions_tfc.yaml``,
``experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml``) declares, per
assumption id, a nominal ``value`` and a ``range``.  This module reads those
registries and expands explicit, EXACT operating-point grids over them:

- every grid coordinate is a :class:`fractions.Fraction` built from the
  written text (``int`` or ``"p/q"`` string).  Floats are REJECTED at
  construction — there are no floats in identity math anywhere in this
  module, so a grid point can never silently round;
- every sampled point must lie INSIDE the registered range (inclusive).
  The registered range is the envelope's authority: a point outside it is
  a hard error before any model executes, never a silently widened
  envelope;
- entries whose declared ``range`` is symbolic (identity/behavior choices
  such as ``[full_duplex_uniform_per_direction, half_duplex]``) are not
  numeric freedom and are simply not offered as axes; they stay where the
  profiles declared them (identity choice is a profile statement, not a
  coordinate).

Determinism follows the sweep-runner policy (``orchestrator/sweeps.py``):
ordered axes, Cartesian expansion in manifest order (last axis fastest),
stable ``point_id`` strings, no wall-clock anywhere.

Evidence level E0 ONLY: a grid is a set of exact coordinates at which
closed-form analytical identities are evaluated; nothing here is measured
on any system, and no grid output may be read as a statement about
hardware behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from essun.contracts import load_yaml


class GridError(Exception):
    """An assumption registry or grid violates the exactness/range contract.

    Raised for float coordinates, out-of-range points, unordered axes,
    unknown assumption ids, and colliding registry entries — always BEFORE
    any model executes, so an envelope either runs whole or fails loudly.
    """


@dataclass(frozen=True)
class AssumptionRange:
    """One NUMERIC free-parameter declaration from an assumption registry.

    ``lo``/``hi`` are exact Fractions parsed from the registry's ``range``
    pair; ``value_text`` keeps the nominal value as written (display only —
    the nominal value is NOT an operating point until validated).
    """

    registry_id: str
    assumption_id: str
    parameter: str
    unit: str
    value_text: str
    lo: Fraction
    hi: Fraction
    source: Path


def _exact_fraction(value, context: str) -> Fraction:
    """Parse one grid/registry number EXACTLY; floats are a hard error."""
    if isinstance(value, bool):
        raise GridError(f"{context}: boolean {value!r} is not an exact number")
    if isinstance(value, float):
        raise GridError(
            f"{context}: float {value!r} is not exact; write the value as an "
            "int or a 'p/q' string so grid coordinates stay Fractions"
        )
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise GridError(
                f"{context}: {value!r} is not an exact 'p/q' fraction string"
            ) from exc
    raise GridError(f"{context}: {value!r} is not an exact number (int or 'p/q')")


def _is_numeric(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _bound_kind(value) -> str:
    """"numeric" (int, float, or exact fraction string) vs "symbolic".

    Floats are numeric KIND (so a float bound reaches the exact parser,
    which rejects it with a clear message rather than silently skipping
    the whole entry as symbolic — a silent narrowing).
    """
    if _is_numeric(value):
        return "numeric"
    if isinstance(value, str) and _looks_numeric(value):
        return "numeric"
    return "symbolic"


def load_numeric_ranges(path: Path) -> dict[str, AssumptionRange]:
    """Load one assumption registry, keeping only NUMERIC freedom entries.

    Symbolic ranges (identity/behavior enumerations) are skipped: they are
    profile statements, not coordinates.  A registry entry whose ``range``
    is not a 2-element numeric pair is either symbolic (skipped) or malformed
    (a ``lo``/``hi`` that is not a number is a hard error — never a guess).
    Duplicate assumption ids inside one registry are a hard error.
    """
    path = Path(path)
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise GridError(f"assumption registry {path} is not a mapping")
    registry_id = str(data.get("assumptions_id", path.stem))
    entries = data.get("assumptions")
    if not isinstance(entries, list):
        raise GridError(f"assumption registry {path} has no 'assumptions' list")

    ranges: dict[str, AssumptionRange] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise GridError(f"assumption registry {path}: entry {entry!r} is not a mapping")
        assumption_id = entry.get("id")
        if not isinstance(assumption_id, str) or not assumption_id:
            raise GridError(f"assumption registry {path}: entry {entry!r} has no 'id'")
        rng = entry.get("range")
        if not isinstance(rng, list) or len(rng) != 2:
            continue  # symbolic/undeclared freedom — not a numeric axis
        kinds = [_bound_kind(side) for side in rng]
        if all(kind == "numeric" for kind in kinds):
            pass  # a numeric freedom range — parsed below
        elif any(kind == "numeric" for kind in kinds):
            raise GridError(
                f"assumption registry {path}: {assumption_id} has a mixed "
                f"range {rng!r}; a numeric freedom range needs BOTH bounds "
                "numeric (symbolic enumerations have neither)"
            )
        else:
            continue  # symbolic enumeration — not a numeric axis
        lo = _exact_fraction(rng[0], f"{path}:{assumption_id}.range[0]")
        hi = _exact_fraction(rng[1], f"{path}:{assumption_id}.range[1]")
        if lo > hi:
            raise GridError(
                f"assumption registry {path}: {assumption_id} range [{lo}, {hi}] "
                "is inverted (lo > hi)"
            )
        if assumption_id in ranges:
            raise GridError(
                f"assumption registry {path}: duplicate assumption id {assumption_id}"
            )
        ranges[assumption_id] = AssumptionRange(
            registry_id=registry_id,
            assumption_id=assumption_id,
            parameter=str(entry.get("parameter", "")),
            unit=str(entry.get("unit", "")),
            value_text=str(entry.get("value", "")),
            lo=lo,
            hi=hi,
            source=path,
        )
    return ranges


def load_ranges(paths) -> dict[str, AssumptionRange]:
    """Load several registries into one id -> range map (collision = error)."""
    merged: dict[str, AssumptionRange] = {}
    for path in paths:
        for assumption_id, record in load_numeric_ranges(path).items():
            if assumption_id in merged:
                raise GridError(
                    f"assumption id {assumption_id} declared in both "
                    f"{merged[assumption_id].source} and {path}; envelope "
                    "registries must be disjoint or merged explicitly"
                )
            merged[assumption_id] = record
    return merged


def _looks_numeric(text: str) -> bool:
    try:
        Fraction(text)
    except (ValueError, ZeroDivisionError):
        return False
    return True


@dataclass(frozen=True)
class GridAxis:
    """One freedom axis: an assumption's registered range plus EXACT samples."""

    assumption_id: str
    parameter: str
    unit: str
    lo: Fraction
    hi: Fraction
    points: tuple[Fraction, ...]

    def as_dict(self) -> dict:
        return {
            "assumption_id": self.assumption_id,
            "parameter": self.parameter,
            "unit": self.unit,
            "range_exact": [str(self.lo), str(self.hi)],
            "points_exact": [str(point) for point in self.points],
        }


def build_axis(
    ranges: dict[str, AssumptionRange], assumption_id: str, points
) -> GridAxis:
    """Validate and freeze one axis against its REGISTERED range.

    Gates: the assumption id must be a loaded numeric freedom; every point
    must be exact (no floats), inside [lo, hi] inclusive, strictly
    increasing, and at least two points must be given (one point is not a
    grid — it is an operating-point value, declared as such instead).
    """
    record = ranges.get(assumption_id)
    if record is None:
        raise GridError(
            f"axis {assumption_id!r} is not a loaded numeric assumption; "
            f"loaded: {sorted(ranges)}"
        )
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise GridError(
            f"axis {assumption_id}: a freedom axis needs >= 2 exact sample "
            f"points, got {points!r}"
        )
    exact = tuple(
        _exact_fraction(point, f"axis {assumption_id} point #{index}")
        for index, point in enumerate(points)
    )
    for point in exact:
        if not (record.lo <= point <= record.hi):
            raise GridError(
                f"axis {assumption_id}: point {point} lies outside the "
                f"registered range [{record.lo}, {record.hi}] "
                f"({record.source}); the registered range is the authority — "
                "widen the registry, never the grid"
            )
    for left, right in zip(exact, exact[1:]):
        if not left < right:
            raise GridError(
                f"axis {assumption_id}: points must be strictly increasing, "
                f"got {left} then {right}"
            )
    return GridAxis(
        assumption_id=assumption_id,
        parameter=record.parameter,
        unit=record.unit,
        lo=record.lo,
        hi=record.hi,
        points=exact,
    )


@dataclass(frozen=True)
class FixedParameter:
    """One fixed exact operating-point value, validated in its range."""

    assumption_id: str
    parameter: str
    unit: str
    value: Fraction
    range_lo: Fraction
    range_hi: Fraction

    def as_dict(self) -> dict:
        return {
            "assumption_id": self.assumption_id,
            "parameter": self.parameter,
            "unit": self.unit,
            "value_exact": str(self.value),
            "range_exact": [str(self.range_lo), str(self.range_hi)],
        }


def build_fixed(
    ranges: dict[str, AssumptionRange], assumption_id: str, value
) -> FixedParameter:
    """Validate one fixed operating-point value against its registered range."""
    record = ranges.get(assumption_id)
    if record is None:
        raise GridError(
            f"fixed parameter {assumption_id!r} is not a loaded numeric "
            f"assumption; loaded: {sorted(ranges)}"
        )
    exact = _exact_fraction(value, f"fixed parameter {assumption_id}")
    if not (record.lo <= exact <= record.hi):
        raise GridError(
            f"fixed parameter {assumption_id}: value {exact} lies outside the "
            f"registered range [{record.lo}, {record.hi}] ({record.source})"
        )
    return FixedParameter(
        assumption_id=assumption_id,
        parameter=record.parameter,
        unit=record.unit,
        value=exact,
        range_lo=record.lo,
        range_hi=record.hi,
    )


@dataclass(frozen=True)
class OperatingPoint:
    """One grid cell: exact values for every axis and fixed parameter."""

    index: int
    point_id: str
    axis_values: tuple[tuple[str, Fraction], ...]
    fixed_values: tuple[tuple[str, Fraction], ...]

    def axis_value(self, assumption_id: str) -> Fraction:
        for aid, value in self.axis_values:
            if aid == assumption_id:
                return value
        raise KeyError(f"axis {assumption_id} not part of this operating point")

    def fixed_value(self, assumption_id: str) -> Fraction:
        for aid, value in self.fixed_values:
            if aid == assumption_id:
                return value
        raise KeyError(f"fixed parameter {assumption_id} not part of this operating point")

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "point_id": self.point_id,
            "axis_values_exact": [
                [aid, str(value)] for aid, value in self.axis_values
            ],
            "fixed_values_exact": [
                [aid, str(value)] for aid, value in self.fixed_values
            ],
        }


def expand_operating_points(
    axes: tuple[GridAxis, ...], fixed: tuple[FixedParameter, ...]
) -> tuple[OperatingPoint, ...]:
    """Cartesian expansion of the axes, in manifest order, last axis fastest.

    Deterministic by construction: the point order depends only on the
    axes' order and their points, never on dict iteration or wall-clock.
    """
    if not axes:
        raise GridError("an envelope needs at least one freedom axis")
    fixed_values = tuple((item.assumption_id, item.value) for item in fixed)
    seen: set[str] = set()
    for axis in axes:
        if axis.assumption_id in seen:
            raise GridError(f"axis {axis.assumption_id} declared twice")
        seen.add(axis.assumption_id)
    for item in fixed:
        if item.assumption_id in seen:
            raise GridError(
                f"{item.assumption_id} is declared both as an axis and as a "
                "fixed parameter — choose one"
            )
        seen.add(item.assumption_id)

    points: list[OperatingPoint] = []
    index = 0
    stacks = [axis.points for axis in axes]
    def _recurse(prefix: tuple[tuple[str, Fraction], ...], depth: int) -> None:
        nonlocal index
        if depth == len(axes):
            point_id = "op{:05d}-".format(index) + "-".join(
                f"{aid}={value}" for aid, value in prefix
            )
            points.append(
                OperatingPoint(
                    index=index,
                    point_id=point_id,
                    axis_values=prefix,
                    fixed_values=fixed_values,
                )
            )
            index += 1
            return
        for value in stacks[depth]:
            _recurse(prefix + ((axes[depth].assumption_id, value),), depth + 1)

    _recurse((), 0)
    return tuple(points)
