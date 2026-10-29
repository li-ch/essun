#!/usr/bin/env python3
"""paper_check.py — placeholder-discipline checker for paper/ markdown.

Enforces the paper-writing rules
on every ``*.md`` under the paper directory (default ``paper/``):

R1 numbers — a measurement-like number outside a ``[RESULT: ...]`` span or a
   citation bracket (``[12]``, ``[3,7]``, ``[S4]``) fails. Allowlist: heading
   section numbering, ``Section/Figure/Table/rule N`` references (incl. ranges
   like ``rules 2-4`` and dotted subsections), semantic versions (x.y.z),
   years, IEEE standard numbers, letter-prefixed identifiers (F5, T1, M9, RQ2,
   B3, W1), and fenced code blocks. Measurement-like = number+unit (ns, MiB,
   %, Gbps, ...), number+x factor, decimal, comma-grouped integer, or a bare
   integer of two or more digits.
R2 claim words — the frozen vocabulary (case-insensitive, word-boundary)
   outside a ``[RESULT: ...]`` span fails: the 4 original words (``first``,
   ``novel``, ``validated``, ``production-ready``), 8 hype forms
   (``state-of-the-art``, ``cutting-edge``, ``best-in-class``,
   ``industry-leading``, ``unprecedented``, ``revolutionary``,
   ``groundbreaking``, ``world-class``), 3 documented bypass candidates
   adopted 2026-10-28 (the ``SOTA`` short form, the ``novelty`` inflection,
   spaced ``state of the art``), and 6 forms adopted 2026-10-29
   (``industrial-grade``, ``battle-tested``, ``production-proven``,
   ``seamless``; plus the inflection variants ``seamlessly`` and
   ``novelties``). Spaced ``production ready`` and the spaced twins of
   the other hyphenated forms (``best in class``, ``cutting edge``)
   remain outside the vocabulary — further extension is a deliberate
   decision, never a silent one.
R3 figure refs — any ``results/`` path reference on a line without a run_id
   (64-hex content-addressed run id, the format produced by
   ``src/essun/evidence/store.py``) fails.

Exit status: 0 pass, 1 violations found (or no markdown files to check).
Stdlib only; runnable as ``.venv/bin/python tools/paper_check.py``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --- R1: span stripping and allowlist --------------------------------------

RESULT_SPAN = re.compile(r"\[RESULT:[^\]]*\]")

CITATION = re.compile(
    r"\[(?:[A-Za-z]{1,3}\d{1,4}|\d{1,4})"
    r"(?:\s*[,;\u2013\u2014-]\s*(?:[A-Za-z]{1,3}\d{1,4}|\d{1,4}))*\]"
)

HEADING_NUM = re.compile(r"^(#{1,6}\s*)(\d+(?:\.\d+)*\.?)(\s+)")

ALLOW_STRIP = [
    # semantic versions x.y[.z[...]] before the decimal rule sees them
    re.compile(r"\b\d+\.\d+(?:\.\d+)+\b"),
    # numbered references: Section 7.2, Fig. 5, rules 2-4, §4, Table T3, step 2
    re.compile(
        r"(?i)(?:\b(?:section|sec|paragraph|figure|fig|table|tab|rule|rules|"
        r"baseline|claim|workload|mechanism|experiment|stage|step|question)"
        r"\b|\u00a7)\.?\s*\d+(?:\.\d+)*(?:\s*[\u2013\u2014-]\s*\d+(?:\.\d+)*)?"
    ),
    # years / dates are not measurements
    re.compile(r"\b(?:19|20)\d{2}\b"),
    # IEEE-style standard designators
    re.compile(r"(?i)\bIEEE\s*\d{2,4}\b"),
]

# digit must not be preceded by a word char, dot, micro sign or hyphen, so
# letter-prefixed identifiers (F5, T1, M9, RQ2, B3, A-W2-DAG, p99) are exempt
GUARD = r"(?<![\w.\u00b5-])"

UNITS = (
    r"(?:ns|\u00b5s|us|ms|s|KiB|MiB|GiB|TiB|KB|MB|GB|TB|kB|B|"
    r"Hz|kHz|MHz|GHz|bps|Kbps|Mbps|Gbps|Tbps|percent|%)"
)

MEASUREMENT_PATTERNS = [
    ("number/unit", re.compile(GUARD + r"\d+(?:\.\d+)?\s*" + UNITS + r"(?![\w])")),
    ("number/factor", re.compile(GUARD + r"\d+(?:\.\d+)?\s*[x\u00d7](?![\w.])")),
    ("number/grouped", re.compile(GUARD + r"\d{1,3}(?:,\d{3})+(?!\w)")),
    ("number/decimal", re.compile(GUARD + r"\d+\.\d+(?!\d)")),
    ("number/int", re.compile(GUARD + r"\d{2,}(?![\w.])")),
]

# --- R2: forbidden claim vocabulary (frozen; tests parametrize over it) ---
#
# 4 original words + 8 hype forms + 3 documented bypass candidates
# adopted 2026-10-28 (SOTA, novelty, spaced "state of the art") + 6 forms
# adopted 2026-10-29 (industrial-grade, battle-tested, production-proven,
# seamless; plus the inflection variants seamlessly, novelties). The
# tuple is the single source of truth — tests parametrize over it, so
# every form planted is asserted flagged and a form added here gains a
# test case automatically.

CLAIM_WORD_FORMS = (
    "first",
    "novel",
    "novelty",
    "validated",
    "production-ready",
    "state-of-the-art",
    r"state\s+of\s+the\s+art",
    "SOTA",
    "cutting-edge",
    "best-in-class",
    "industry-leading",
    "unprecedented",
    "revolutionary",
    "groundbreaking",
    "world-class",
    "industrial-grade",
    "battle-tested",
    "production-proven",
    "seamless",
    "seamlessly",
    "novelties",
)

CLAIM_WORDS = re.compile(
    r"\b(?:" + "|".join(CLAIM_WORD_FORMS) + r")\b", re.IGNORECASE
)

# --- R3: results/ references need a run_id on the same line -----------------

RESULTS_REF = re.compile(r"(?<![\w/])results/[\w./+-]*")
RUN_ID = re.compile(r"\b[0-9a-fA-F]{64}\b")

FENCE = re.compile(r"^\s*```")


def strip_for_number_scan(line: str, is_heading: bool) -> str:
    """Return the line with legitimate contexts blanked out (spaces)."""
    if is_heading:
        m = HEADING_NUM.match(line)
        if m:
            line = m.group(1) + " " * len(m.group(2)) + m.group(3) + line[m.end():]
    line = RESULT_SPAN.sub(lambda m: " " * len(m.group(0)), line)
    line = CITATION.sub(lambda m: " " * len(m.group(0)), line)
    for allow in ALLOW_STRIP:
        line = allow.sub(lambda m: " " * len(m.group(0)), line)
    return line


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    in_fence = False
    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue  # code blocks are illustrative, not paper prose
        rel = path.name
        # R3 first, on the raw line (RESULT spans may legally carry a run_id)
        for ref in RESULTS_REF.findall(raw):
            if not RUN_ID.search(raw):
                violations.append(
                    f"{rel}:{lineno}: [fig-ref] results/ reference "
                    f"'{ref.rstrip('/ .')}' has no run_id (64-hex) on the line"
                )
        # R1: measurement-like numbers outside allowed contexts; each number
        # is reported once, under its most specific pattern (most specific
        # patterns run first and blank their spans before later ones scan)
        scanned = strip_for_number_scan(raw, raw.lstrip().startswith("#"))
        for tag, pat in MEASUREMENT_PATTERNS:
            matches = list(pat.finditer(scanned))
            for m in matches:
                violations.append(
                    f"{rel}:{lineno}: [{tag}] measurement-like number "
                    f"'{m.group(0).strip()}' outside a [RESULT: ...] placeholder"
                )
            if matches:
                chars = list(scanned)
                for m in matches:
                    for i in range(*m.span()):
                        chars[i] = " "
                scanned = "".join(chars)
        # R2: forbidden claim words outside [RESULT: ...] spans
        word_scan = RESULT_SPAN.sub(lambda m: " " * len(m.group(0)), raw)
        for m in CLAIM_WORDS.finditer(word_scan):
            violations.append(
                f"{rel}:{lineno}: [claim-word] forbidden claim word "
                f"'{m.group(0)}' outside a [RESULT: ...] placeholder"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--paper-dir",
        type=Path,
        default=repo_root / "paper",
        help="directory scanned recursively for *.md (default: <repo>/paper)",
    )
    args = parser.parse_args(argv)

    md_files = sorted(args.paper_dir.rglob("*.md"))
    if not md_files:
        print(f"paper-check: FAIL — no markdown files under {args.paper_dir}")
        return 1

    all_violations: list[str] = []
    for path in md_files:
        all_violations.extend(check_file(path))

    for v in all_violations:
        print(f"paper-check: {v}")
    if all_violations:
        print(
            f"paper-check: FAIL — {len(all_violations)} violation(s) across "
            f"{len(md_files)} file(s)"
        )
        return 1
    print(f"paper-check: PASS — {len(md_files)} file(s) checked, 0 violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
