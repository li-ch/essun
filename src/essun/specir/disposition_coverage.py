"""Per-profile disposition coverage report (design doc D1 gate; S2 of the
dispositions/profile ladder, 2026-10-29).

D1 requires that "a coverage report (per-disposition counts) ships with
every profile": an anchored requirement count is not executable coverage,
so each profile must state, per disposition value, how many of its
requirements the platform actually executes — with ``unsupported`` shown
plainly, never folded away.  Honesty over coverage: the zeros and the
unsupported column are the point of this report, not an embarrassment
to hide.

The report is COMPUTED from the live specir modules on every call
(:func:`uec_profile_coverage` walks the five stage modules'
``requirements()`` tuples), so it cannot drift from the source the way a
stored table could.  The frozen review record stays where the D1 migration
put it (``EXPECTED_COUNTS`` in tests/specir/test_dispositions.py); the
tests of THIS module pin the agreement between the computed report and
that record, so a promotion is loud in both places at once.

Profiles known today:

- **UEC 1.1 semantic profile** — 445 disposition-bearing requirement
  objects across the five mechanism modules, plus 67 free parameters
  (declared freedom carries no disposition by design: a free parameter is
  not a requirement, so it is reported as a separate count, never inside
  the disposition table).
- **UnifiedBus paper-derived profile** — since ladder S5 (2026-10-29) its
  54 design parameters (``unifiedbus_paper_profile.requirements()``) carry
  D1 dispositions (the S5 initial rule: paper-stated structure facts
  informational, everything else unsupported; zero executed, because no
  reviewed binding exists for UnifiedBus), plus 8 free parameters outside
  the table.  Before S5 this section reported an explicit absence; the
  absence note resolved when the dispositions landed — a conscious,
  ladder-internal change recorded in the S5 report.

Render with :func:`render_report` (printable text table), get the raw
structure with :func:`coverage_report`, or run the CLI artifact:
``.venv/bin/python tools/disposition_coverage.py`` (``--json`` for
machine-readable output; also ``make disposition-report``).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from .uec_link_transport import DISPOSITIONS

#: Dispositions that mean the platform EXECUTES the requirement today;
#: the other three (informational / unsupported / not_applicable) are
#: carried, not executed.  Names follow the D1 text.
EXECUTED_DISPOSITIONS: tuple[str, ...] = (
    "constraint",
    "simulated_behavior",
    "conformance_test",
)

#: The five specir modules that own UEC requirement objects, with their
#: human-readable ladder labels (same set as STAGE_MODULES in
#: tests/specir/test_dispositions.py — the coverage tests pin the
#: agreement).
UEC_STAGE_MODULES: tuple[tuple[str, str], ...] = (
    ("essun.specir.uec_link_transport", "link/transport S2"),
    ("essun.specir.uec_reliability_ordering", "reliability/ordering S3"),
    ("essun.specir.uec_congestion_management", "congestion management S4"),
    ("essun.specir.uec_credits_flow_control", "credits/flow control S5"),
    ("essun.specir.uec_f07_mechanisms", "F07 mechanisms S2b"),
)

#: Dotted name of the UnifiedBus paper profile module (its design
#: parameters are the family's disposition-bearing requirement objects
#: since ladder S5; see the module's ``requirements()`` alias).
UNIFIEDBUS_PROFILE_MODULE = "essun.specir.unifiedbus_paper_profile"

#: One-line status note for the UnifiedBus section (paper-derived family;
#: the table itself carries the honest counts, zeros kept).
UNIFIEDBUS_NOTE = (
    "paper-derived, not normative; the family's requirement objects are "
    "its design parameters (UBP-P01..P54), dispositioned at ladder S5 "
    "with zero executed — no reviewed binding exists for UnifiedBus"
)


def module_disposition_counts(module: object) -> dict[str, int]:
    """Per-disposition counts for one stage module.

    All six :data:`DISPOSITIONS` keys are always present, zeros kept —
    a dropped column would be a silent claim.  A requirement whose
    disposition is outside the vocabulary raises KeyError here; the D1
    registry gate (S1) rejects those earlier and louder.
    """
    counts = dict.fromkeys(DISPOSITIONS, 0)
    for req in module.requirements():  # type: ignore[attr-defined]
        counts[req.disposition] += 1
    return counts


@dataclass(frozen=True)
class ModuleCoverage:
    """One module row: dotted module name, label, per-disposition counts."""

    module: str  # dotted module path (identity)
    label: str  # human-readable ladder label
    counts: dict[str, int]  # every DISPOSITIONS key -> count (zeros kept)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


@dataclass(frozen=True)
class ProfileCoverage:
    """One profile section of the coverage report."""

    profile: str  # profile name (identity)
    label: str  # one-line honest description
    modules: tuple[ModuleCoverage, ...]  # empty = no disposition-bearing objects
    free_parameters: int = 0  # declared freedom; never inside the table
    note: str = ""  # visible-absence note; empty when the table speaks

    def total_counts(self) -> dict[str, int]:
        """Dispositions summed over the profile's modules (zeros kept)."""
        totals = dict.fromkeys(DISPOSITIONS, 0)
        for mod in self.modules:
            for disposition in DISPOSITIONS:
                totals[disposition] += mod.counts[disposition]
        return totals

    @property
    def requirements_total(self) -> int:
        return sum(self.total_counts().values())

    @property
    def executed(self) -> int:
        """Requirements executed today (constraint / simulated_behavior /
        conformance_test) — the honest numerator of the D1 gate."""
        totals = self.total_counts()
        return sum(totals[d] for d in EXECUTED_DISPOSITIONS)


def uec_profile_coverage() -> ProfileCoverage:
    """Coverage of the UEC 1.1 semantic profile, computed live."""
    modules = tuple(
        ModuleCoverage(
            module=dotted,
            label=label,
            counts=module_disposition_counts(importlib.import_module(dotted)),
        )
        for dotted, label in UEC_STAGE_MODULES
    )
    free = sum(
        len(importlib.import_module(dotted).free_parameters())
        for dotted, _ in UEC_STAGE_MODULES
    )
    return ProfileCoverage(
        profile="UEC 1.1 semantic profile",
        label=(
            "license-gated UEC 1.1 specification (experiments/uec/); "
            "five mechanism modules"
        ),
        modules=modules,
        free_parameters=free,
    )


def unifiedbus_profile_coverage() -> ProfileCoverage:
    """Coverage of the UnifiedBus paper-derived profile, computed live.

    Since ladder S5 the profile's design parameters carry D1 dispositions
    (structure facts informational, everything else unsupported; zero
    executed), so the section reports REAL per-disposition counts.  Before
    S5 it reported an explicit absence; the dispositions landed and the
    absence resolved — the counts, not a note, now say what is executed
    (nothing) and what is not.
    """
    module = importlib.import_module(UNIFIEDBUS_PROFILE_MODULE)
    return ProfileCoverage(
        profile="UnifiedBus paper-derived profile",
        label=(
            "paper-derived, not normative; public-gate leg 2 "
            "(experiments/unifiedbus/)"
        ),
        modules=(
            ModuleCoverage(
                module=UNIFIEDBUS_PROFILE_MODULE,
                label="paper profile (design parameters)",
                counts=module_disposition_counts(module),
            ),
        ),
        free_parameters=len(module.free_parameters()),
        note=UNIFIEDBUS_NOTE,
    )


def coverage_report() -> tuple[ProfileCoverage, ...]:
    """Every profile the platform ships, in report order."""
    return (uec_profile_coverage(), unifiedbus_profile_coverage())


def _wrap_note(note: str, width: int, indent: str) -> list[str]:
    words, lines, current = note.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(f"{indent}{current}")
            current = word
        else:
            current = candidate
    if current:
        lines.append(f"{indent}{current}")
    return lines


def render_profile(profile: ProfileCoverage) -> list[str]:
    """One profile section of the printable report (no trailing newline)."""
    out = [f"Profile: {profile.profile} — {profile.label}"]
    if profile.note:
        out.extend(_wrap_note(profile.note, width=76, indent="  "))
    if profile.modules:
        header = ("module",) + DISPOSITIONS + ("total",)
        rows: list[tuple[str, ...]] = [
            (
                f"{mod.module.rsplit('.', 1)[-1]} ({mod.label})",
                *(str(mod.counts[d]) for d in DISPOSITIONS),
                str(mod.total),
            )
            for mod in profile.modules
        ]
        totals = profile.total_counts()
        rows.append(
            (
                "profile total",
                *(str(totals[d]) for d in DISPOSITIONS),
                str(profile.requirements_total),
            )
        )
        widths = [
            max(len(header[i]), *(len(row[i]) for row in rows))
            for i in range(len(header))
        ]
        out.append(
            "  "
            + "  ".join(
                h.ljust(widths[i]) if i == 0 else h.rjust(widths[i])
                for i, h in enumerate(header)
            )
        )
        for row in rows:
            out.append(
                "  "
                + "  ".join(
                    cell.rjust(widths[i]) if i else cell.ljust(widths[i])
                    for i, cell in enumerate(row)
                )
            )
        executed, total = profile.executed, profile.requirements_total
        fraction = (executed / total * 100) if total else 0.0
        out.append(
            f"  executed ({'+'.join(EXECUTED_DISPOSITIONS)}): "
            f"{executed}/{total} = {fraction:.1f}%"
        )
    else:
        out.append(
            "  disposition-bearing requirements: 0 "
            "(no per-disposition table is printed for an absent set)"
        )
    if profile.free_parameters:
        out.append(
            f"  free parameters (declared freedom, no disposition by "
            f"design): {profile.free_parameters}"
        )
    return out


def render_report(profiles: tuple[ProfileCoverage, ...] | None = None) -> str:
    """The full printable coverage report (D1 gate artifact)."""
    profiles = coverage_report() if profiles is None else profiles
    executed = sum(p.executed for p in profiles)
    total = sum(p.requirements_total for p in profiles)
    lines = [
        "essun — per-profile disposition coverage report (design doc D1)",
        "counts computed live from src/essun/specir; a stored table could "
        "drift,",
        "this cannot. Unsupported is a valid, visible answer.",
    ]
    for profile in profiles:
        lines.append("")
        lines.extend(render_profile(profile))
    lines.extend(
        [
            "",
            f"platform total: {total} disposition-bearing requirements, "
            f"{executed} executed",
            "promotions are conscious changes to the frozen counts "
            "(tests/specir/test_dispositions.py), never silent.",
        ]
    )
    return "\n".join(lines) + "\n"


def report_json(profiles: tuple[ProfileCoverage, ...] | None = None) -> dict:
    """Machine-readable form of the same report (no rounding, zeros kept)."""
    profiles = coverage_report() if profiles is None else profiles
    return {
        "dispositions": list(DISPOSITIONS),
        "executed_dispositions": list(EXECUTED_DISPOSITIONS),
        "profiles": [
            {
                "profile": p.profile,
                "label": p.label,
                "modules": [
                    {
                        "module": m.module,
                        "label": m.label,
                        "counts": {d: m.counts[d] for d in DISPOSITIONS},
                        "total": m.total,
                    }
                    for m in p.modules
                ],
                "total_counts": p.total_counts(),
                "requirements_total": p.requirements_total,
                "executed": p.executed,
                "free_parameters": p.free_parameters,
                **({"note": p.note} if p.note else {}),
            }
            for p in profiles
        ],
    }
