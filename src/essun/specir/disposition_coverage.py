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

Since the credit-family ladder's stage S6 (2026-10-30) the report also
states the **G2 credit-family ladder window**: the family's disposition
counts at program start (frozen at commit ``3db1d4e``, re-verified live
against that tree) versus the counts computed live now, every disposition
change in the window justified by naming the landed binding or check that
earned it, and — the point of the section, not an embarrassment — what did
NOT change: the inventory's STAYS keep their dispositions with the missing
fidelity named.  The window record is pinned against drift exactly like
the frozen counts: :func:`credit_family_window` refuses to render when the
frozen BEFORE plus the named changes no longer reconcile with the live
registries, so a later promotion must consciously edit the record.
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

#: Dotted module of the credit/flow-control family — the G2 ladder window.
CREDIT_FAMILY_WINDOW_MODULE = "essun.specir.uec_credits_flow_control"

#: One disposition change inside the G2 window: what flipped, and the
#: landed binding or check (plus its commit) that earned the flip.
@dataclass(frozen=True)
class DispositionChange:
    requirement: str  # requirement id that changed disposition
    before: str  # disposition before the window
    after: str  # disposition after the change landed
    carrier: str  # the binding id or check list that earned it
    commit: str  # short hash of the commit that landed the carrier


#: The program-start record (pre-S2) of the credit/flow-control family:
#: disposition counts frozen at the S1 inventory commit ``3db1d4e``
#: (2026-10-30).  S1 changed no disposition, so that tree IS the
#: pre-ladder state; the counts were re-verified live for the S6 report by
#: running this same tool on a worktree of that commit.  A stored BEFORE is
#: unavoidable — history is not importable — but it is pinned against drift:
#: :func:`credit_family_window` derives the AFTER side live and refuses to
#: render when BEFORE plus the named changes disagree with the registries
#: (a later promotion must consciously edit this record, exactly like
#: ``EXPECTED_COUNTS`` in tests/specir/test_dispositions.py).
CREDIT_FAMILY_BEFORE_COMMIT = "3db1d4e"
CREDIT_FAMILY_BEFORE_COUNTS: dict[str, int] = {
    "constraint": 0,
    "simulated_behavior": 1,  # the flagship, UEC11-FC-R02
    "conformance_test": 0,
    "informational": 33,
    "unsupported": 32,
    "not_applicable": 0,
}

#: The three disposition changes of the window (S2, S3, S4), each with the
#: binding or check that earned it.  UEC11-FC-R05's carrier is the profile
#: CHECKS entries, not a binding — the D2 rule keeps conformance_test
#: requirements out of the bindings registry.
CREDIT_FAMILY_CHANGES: tuple[DispositionChange, ...] = (
    DispositionChange(
        requirement="UEC11-FC-R08",
        before="informational",
        after="simulated_behavior",
        carrier="binding BIND-UEC11-FC-R08-L0TFC",
        commit="11aec6d",
    ),
    DispositionChange(
        requirement="UEC11-FC-R09",
        before="unsupported",
        after="simulated_behavior",
        carrier="binding BIND-UEC11-FC-R09-L0TFC",
        commit="c22e256",
    ),
    DispositionChange(
        requirement="UEC11-FC-R05",
        before="informational",
        after="conformance_test",
        carrier="profile checks UEC11-CHK-12/13/14",
        commit="9af9e33",
    ),
)

#: The window's one disposition-preserving event: the flagship's binding
#: was re-pointed at the exact credit automaton (G8) — before == after, so
#: the counts do not move, but the executed semantics did, and the report
#: says so rather than staying silent about it.
CREDIT_FAMILY_RE_POINT = DispositionChange(
    requirement="UEC11-FC-R02",
    before="simulated_behavior",
    after="simulated_behavior",
    carrier="binding BIND-UEC11-FC-R02-AUTOMATON (re-pointed from "
    "BIND-UEC11-FC-R02-L0TFC)",
    commit="0854a13",
)

#: The inventory's six CAPABLE-NOT-PLANNED ids: exact arithmetic laws
#: recorded for a future link-credit track, deliberately not staged in the
#: G2 ladder.  They are informational today; the window's stays count
#: subtracts them live and the reconciliation refuses a silent drift.
CREDIT_FAMILY_CAPABLE_NOT_PLANNED: tuple[str, ...] = (
    "UEC11-FC-R28",
    "UEC11-FC-R34",
    "UEC11-FC-R39",
    "UEC11-FC-R43",
    "UEC11-FC-R45",
    "UEC11-FC-R46",
)


#: The assembled G2 window record (see :func:`credit_family_window`).
@dataclass(frozen=True)
class LadderWindow:
    module: str  # the family's dotted module name
    before_commit: str  # where the frozen BEFORE was taken
    before: dict[str, int]  # family counts at program start (frozen)
    after: dict[str, int]  # family counts now (computed live)
    profile_before: dict[str, int]  # UEC-profile-wide counts, derived live
    profile_after: dict[str, int]  # UEC-profile-wide counts, computed live
    changes: tuple[DispositionChange, ...]  # what moved, and what earned it
    re_point: DispositionChange  # what did NOT move (binding re-pointed)
    stays_unsupported: int  # inventory STAYS that remain unsupported
    stays_informational: int  # inventory STAYS that remain informational
    capable_not_planned: tuple[str, ...]  # exact laws recorded, not staged

    @property
    def requirements_total(self) -> int:
        return sum(self.after.values())

    @property
    def executed(self) -> int:
        return sum(self.after[d] for d in EXECUTED_DISPOSITIONS)

    @property
    def stays_total(self) -> int:
        return self.stays_unsupported + self.stays_informational


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


def reconcile_window(window: LadderWindow) -> LadderWindow:
    """Drift gate for the G2 window record — the S6 section's teeth.

    Recomputes everything from the live registries and raises ValueError
    on any disagreement with the record's frozen side: the BEFORE counts
    plus the named changes must land exactly on the live family row (so a
    promotion that did not consciously edit the record fails loudly), the
    profile-wide BEFORE must equal the live profile totals minus the same
    deltas (asserting nothing outside the family flipped during the
    window), every named change's disposition must be what the live
    registry says, and the capable-not-planned ids must still be
    informational.  Returns the window unchanged.
    """
    uec = uec_profile_coverage()
    family = next(
        m for m in uec.modules if m.module == CREDIT_FAMILY_WINDOW_MODULE
    )
    live = family.counts

    delta = dict.fromkeys(DISPOSITIONS, 0)
    for change in window.changes:
        delta[change.before] -= 1
        delta[change.after] += 1
    reconciled = {d: window.before[d] + delta[d] for d in DISPOSITIONS}
    if reconciled != live:
        raise ValueError(
            "credit-family window record is stale: the frozen BEFORE at "
            f"{window.before_commit} + the named changes give "
            f"{reconciled}, the live registries say {live} — update "
            "CREDIT_FAMILY_BEFORE_COUNTS/CREDIT_FAMILY_CHANGES "
            "consciously, never silently"
        )

    dispositions = {
        req.requirement_id: req.disposition
        for req in importlib.import_module(CREDIT_FAMILY_WINDOW_MODULE).requirements()
    }
    for change in (*window.changes, window.re_point):
        actual = dispositions[change.requirement]
        if actual != change.after:
            raise ValueError(
                f"window record says {change.requirement} is "
                f"{change.after!r} after {change.commit}, the live "
                f"registry says {actual!r} — conscious edit required"
            )
    stray_capable = [
        req
        for req in window.capable_not_planned
        if dispositions[req] != "informational"
    ]
    if stray_capable:
        raise ValueError(
            f"capable-not-planned ids are no longer informational: "
            f"{stray_capable}"
        )
    derived_profile_before = {
        d: uec.total_counts()[d] - delta[d] for d in DISPOSITIONS
    }
    if derived_profile_before != window.profile_before:
        raise ValueError(
            "credit-family window's profile-wide BEFORE no longer "
            f"derives: {window.profile_before} vs live-derived "
            f"{derived_profile_before} — a disposition outside the "
            "family moved; conscious edit required"
        )
    return window


def credit_family_window(
    profiles: tuple[ProfileCoverage, ...] | None = None,
) -> LadderWindow:
    """The G2 credit-family ladder window: frozen BEFORE vs live AFTER.

    Every number the S6 section states is derived here, not copied: the
    AFTER side comes from the live module row inside the report's own UEC
    profile coverage, the profile-wide BEFORE is the live profile totals
    minus the named changes' deltas, and the stays counts subtract the six
    capable-not-planned ids from the live informational column.  The
    assembled record is then handed to :func:`reconcile_window`, so a
    stored table could drift but this cannot.
    """
    profiles = coverage_report() if profiles is None else profiles
    uec = next(
        (
            p
            for p in profiles
            if any(m.module == CREDIT_FAMILY_WINDOW_MODULE for m in p.modules)
        ),
        None,
    )
    if uec is None:
        uec = uec_profile_coverage()
    family = next(m for m in uec.modules if m.module == CREDIT_FAMILY_WINDOW_MODULE)
    live = family.counts

    return reconcile_window(
        LadderWindow(
            module=CREDIT_FAMILY_WINDOW_MODULE,
            before_commit=CREDIT_FAMILY_BEFORE_COMMIT,
            before=dict(CREDIT_FAMILY_BEFORE_COUNTS),
            after=dict(live),
            profile_before={
                d: uec.total_counts()[d] - _change_delta(d) for d in DISPOSITIONS
            },
            profile_after=dict(uec.total_counts()),
            changes=CREDIT_FAMILY_CHANGES,
            re_point=CREDIT_FAMILY_RE_POINT,
            stays_unsupported=live["unsupported"],
            stays_informational=live["informational"]
            - len(CREDIT_FAMILY_CAPABLE_NOT_PLANNED),
            capable_not_planned=CREDIT_FAMILY_CAPABLE_NOT_PLANNED,
        )
    )


def _change_delta(disposition: str) -> int:
    """Signed count of the named changes into/out of one disposition."""
    delta = 0
    for change in CREDIT_FAMILY_CHANGES:
        if change.before == disposition:
            delta -= 1
        if change.after == disposition:
            delta += 1
    return delta


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


def _counts_phrase(counts: dict[str, int]) -> str:
    """'33 informational / 32 unsupported / 1 simulated_behavior — 1/66
    executed' — nonzero dispositions in registry order plus the executed
    fraction; the tables above and ``--json`` keep all six columns."""
    parts = [f"{counts[d]} {d}" for d in DISPOSITIONS if counts[d]]
    executed = sum(counts[d] for d in EXECUTED_DISPOSITIONS)
    total = sum(counts.values())
    return f"{' / '.join(parts)} — {executed}/{total} executed"


def render_credit_family_window(window: LadderWindow) -> list[str]:
    """The G2 window section of the printable report (S6, 2026-10-30)."""
    family_name = window.module.rsplit(".", 1)[-1]
    changes = [
        f"{c.requirement}: {c.before} -> {c.after}, earned by "
        f"{c.carrier} ({c.commit})"
        for c in window.changes
    ]
    out = [
        "credit-family ladder window (G2, 2026-10-30): before/after, and "
        "what earned each change",
        "  the BEFORE is the frozen program-start record at commit "
        f"{window.before_commit} (the S1",
        "  inventory; S1 changed no disposition), re-verified live "
        "against that tree for",
        "  this report; the AFTER is computed live now and the section "
        "refuses to render if",
        "  the two sides do not reconcile. Zero columns are omitted from "
        "these summary lines",
        "  only.",
        f"  family {family_name} ({window.requirements_total} requirements):",
        f"    before: {_counts_phrase(window.before)}",
        f"    after:  {_counts_phrase(window.after)}",
        f"  profile-wide UEC 1.1 ({sum(window.profile_after.values())} "
        "requirements):",
        f"    before: {_counts_phrase(window.profile_before)}",
        f"    after:  {_counts_phrase(window.profile_after)}",
        "  every disposition change in the window, justified by what landed:",
        *(f"    {line}" for line in changes),
        f"    {window.re_point.requirement}: {window.re_point.after} "
        "(disposition unchanged); executed semantics re-pointed at "
        f"{window.re_point.carrier} ({window.re_point.commit})",
        "  what did NOT change is the point of this section, not an "
        "embarrassment:",
        f"    {window.stays_total} of the family's "
        f"{window.requirements_total - window.executed} non-executed "
        "requirements are the inventory's STAYS —",
        f"    {window.stays_unsupported} unsupported + "
        f"{window.stays_informational} informational, every one with its "
        "missing fidelity named",
        "    in experiments/uec/credit_family_inventory.md. The other "
        f"{len(window.capable_not_planned)} are the capable-not-planned",
        "    exact arithmetic laws ("
        + ", ".join(req.replace("UEC11-", "") for req in window.capable_not_planned)
        + ") recorded for a future",
        "    link-credit track.",
        "    Unsupported is a valid, visible answer; honesty outranks coverage.",
    ]
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
    lines.append("")
    lines.extend(render_credit_family_window(credit_family_window(profiles)))
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
    window = credit_family_window(profiles)
    return {
        "dispositions": list(DISPOSITIONS),
        "executed_dispositions": list(EXECUTED_DISPOSITIONS),
        "credit_family_window": {
            "module": window.module,
            "before_commit": window.before_commit,
            "before_counts": {d: window.before[d] for d in DISPOSITIONS},
            "after_counts": {d: window.after[d] for d in DISPOSITIONS},
            "profile_before_counts": {
                d: window.profile_before[d] for d in DISPOSITIONS
            },
            "profile_after_counts": {
                d: window.profile_after[d] for d in DISPOSITIONS
            },
            "changes": [
                {
                    "requirement": c.requirement,
                    "before": c.before,
                    "after": c.after,
                    "carrier": c.carrier,
                    "commit": c.commit,
                }
                for c in window.changes
            ],
            "binding_re_point": {
                "requirement": window.re_point.requirement,
                "before": window.re_point.before,
                "after": window.re_point.after,
                "carrier": window.re_point.carrier,
                "commit": window.re_point.commit,
            },
            "stays": {
                "unsupported": window.stays_unsupported,
                "informational": window.stays_informational,
                "total": window.stays_total,
            },
            "capable_not_planned": list(window.capable_not_planned),
        },
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
