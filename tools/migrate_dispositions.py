#!/usr/bin/env python3
"""Assign the initial D1 dispositions to every UEC requirement object.

Design doc D1 (docs-private design-integration-20261029): every requirement
object carries a required ``disposition`` — one of constraint /
simulated_behavior / conformance_test / informational / unsupported /
not_applicable — and the registry gate
(:func:`essun.specir.uec_link_transport.disposition_problems`, wired into
every stage module's shape check) fails on a requirement without one.

This migration assigns the initial honest values to the requirement
constructors of the five specir stage modules, using exactly two rules
(mirroring :func:`essun.specir.uec_link_transport.initial_disposition`):

- ``DEFINITIONAL`` statements -> ``informational``: load-bearing
  structure/scope facts the spec states without RFC-2119 force; carried for
  understanding, deliberately not executed.
- every normative keyword (MUST/SHALL/SHOULD/MAY variants) ->
  ``unsupported``: anchored, but no backend binding, compile-time
  constraint check, or conformance test executes it today.

The script NEVER assigns ``constraint``, ``simulated_behavior``,
``conformance_test`` or ``not_applicable``: each of those requires a
per-requirement review with a binding that actually exists.  In particular
no requirement silently becomes ``simulated_behavior`` — that promotion is
the flagship slice's explicit, reviewed change.  The per-module counts
printed below are the review record; tests/specir/test_dispositions.py
freezes them so any later change is loud.

Usage::

    .venv/bin/python tools/migrate_dispositions.py            # apply
    .venv/bin/python tools/migrate_dispositions.py --dry-run  # report only

The rewrite is AST-located but text-inserted (one ``disposition=...``
keyword line per UECRequirement(...) call, after the ``subject=`` line), so
formatting is otherwise untouched.  The script is idempotent: calls that
already carry a disposition are left alone and counted as skipped.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The five stage modules that own UEC requirement objects (S2 model home
#: plus the four satellite stages that reuse UECRequirement).
MODULES: tuple[str, ...] = (
    "src/essun/specir/uec_link_transport.py",
    "src/essun/specir/uec_reliability_ordering.py",
    "src/essun/specir/uec_congestion_management.py",
    "src/essun/specir/uec_credits_flow_control.py",
    "src/essun/specir/uec_f07_mechanisms.py",
)


def initial_disposition(keyword: str) -> str:
    """The one honest scripted assignment (kept local so the tool is
    standalone): DEFINITIONAL -> informational, else unsupported."""
    return "informational" if keyword == "DEFINITIONAL" else "unsupported"


def _call_keyword(call: ast.Call, name: str) -> ast.Constant | None:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return kw.value
    return None


def migrate_source(text: str, path: Path) -> tuple[str, Counter, Counter]:
    """Insert disposition= into every UECRequirement call of one module.

    Returns (new_text, assigned_counts, skipped_counts).  Raises on any
    structural surprise (no keyword=, no subject= line anchor) so the tool
    never guesses.
    """
    tree = ast.parse(text, filename=str(path))
    insertions: list[tuple[int, str, str]] = []  # (subject lineno, value, req id)
    assigned: Counter = Counter()
    skipped: Counter = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "UECRequirement"):
            continue
        rid = _call_keyword(node, "requirement_id")
        keyword = _call_keyword(node, "keyword")
        if rid is None or not isinstance(rid.value, str):
            raise SystemExit(f"{path}: UECRequirement call without literal requirement_id")
        already = _call_keyword(node, "disposition")
        if already is not None and isinstance(already.value, str):
            skipped[already.value] += 1
            continue
        if keyword is None or not isinstance(keyword.value, str):
            raise SystemExit(f"{path}: {rid.value} has no literal keyword=")
        value = initial_disposition(keyword.value)
        subject = _call_keyword(node, "subject")
        if subject is None:
            raise SystemExit(f"{path}: {rid.value} has no subject= to anchor on")
        insertions.append((subject.lineno, value, rid.value))
        assigned[value] += 1

    lines = text.splitlines(keepends=True)
    # bottom-up so earlier line numbers stay valid as lines are inserted
    for lineno, value, rid in sorted(insertions, reverse=True):
        subject_line = lines[lineno - 1]  # 1-based; insertions below don't shift it
        indent = subject_line[: len(subject_line) - len(subject_line.lstrip())]
        assert f"subject=" in subject_line, f"{path}: {rid} line {lineno} is not a subject line"
        lines.insert(lineno, f'{indent}disposition="{value}",\n')
    return "".join(lines), assigned, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = parser.parse_args(argv)

    total_assigned: Counter = Counter()
    total_skipped: Counter = Counter()
    for rel in MODULES:
        path = REPO_ROOT / rel
        text = path.read_text(encoding="utf-8")
        new_text, assigned, skipped = migrate_source(text, path)
        ast.parse(new_text, filename=str(path))  # rewritten source must parse
        total_assigned.update(assigned)
        total_skipped.update(skipped)
        counts = ", ".join(f"{k}={v}" for k, v in sorted(assigned.items())) or "-"
        skips = ", ".join(f"{k}={v}" for k, v in sorted(skipped.items())) or "-"
        print(f"{path.name}: assigned [{counts}] skipped-already-set [{skips}]")
        if new_text != text and not args.dry_run:
            path.write_text(new_text, encoding="utf-8")
    print(
        f"TOTAL: assigned {sum(total_assigned.values())} "
        f"(informational={total_assigned['informational']}, "
        f"unsupported={total_assigned['unsupported']}, "
        f"other=0 by construction); "
        f"skipped {sum(total_skipped.values())} already-set"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
