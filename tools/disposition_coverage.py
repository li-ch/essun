#!/usr/bin/env python3
"""disposition_coverage.py — print the per-profile D1 coverage report.

Design doc D1 gate (docs-private design-integration-20261029): "a coverage
report (per-disposition counts) ships with every profile."  This is the
human-runnable form of that gate: it prints, for every profile the platform
ships, how many requirements carry each disposition (constraint /
simulated_behavior / conformance_test / informational / unsupported /
not_applicable) and the executed fraction — including the UnifiedBus
paper-derived profile, whose 54 design parameters were dispositioned at
ladder S5 with zero executed.  Counts are computed live from
``src/essun/specir``; ``unsupported`` is printed plainly, because honesty
outranks coverage.

Usage::

    .venv/bin/python tools/disposition_coverage.py            # text table
    .venv/bin/python tools/disposition_coverage.py --json     # machine-readable
    make disposition-report                                   # same, via Make

Exit status is always 0 (this is a report, not a check); the registry
gate that FAILS on a missing disposition lives in the specir shape
checks and tests/specir/test_dispositions.py.
"""

from __future__ import annotations

import argparse
import json

from essun.specir.disposition_coverage import render_report, report_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the per-profile disposition coverage report "
        "(design doc D1 gate; counts computed live from src/essun/specir)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable report (same counts, zeros kept)",
    )
    args = parser.parse_args(argv)
    if args.json:
        print(json.dumps(report_json(), indent=2, sort_keys=True))
    else:
        print(render_report(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
