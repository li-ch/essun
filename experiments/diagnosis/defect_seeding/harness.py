#!/usr/bin/env python3
"""Flag-driven fault-injection harness over the seeded-defect pipeline.

Every committed semantic defect sits behind a flag: select injections
with ``--inject <defect_id>`` (repeatable; ``--inject all`` = the four
committed trials).  With ``--clean-baseline`` the SAME probes, minimizer,
and classifier run with the injection OFF (clean engine vs clean engine)
over every case space — the initial case plus every candidate the
committed shrink ladder generates — and must detect NOTHING: a false
alarm is a finding about the diagnosis engine and fails the run.

The injected carriers are wrappers/copies over the REAL essun engines
(`essun.diagnosis.defects`): no production code path is mutated at
runtime, the carriers are never registered as backends, and nothing
here writes to the evidence store or the committed record (that stays
the job of ``build_record.py``, byte-identical under its guard test).
Ground truth is the committed ``essun.diagnosis.defects.GROUND_TRUTH``
registry; misses and misclassifications are reported honestly, never
hidden and never tuned away.

Exit status: 0 = every selected injection was detected and classified
to ground truth AND every requested clean baseline stayed silent;
1 = a finding (missed defect, misclassification, or false alarm);
2 = usage error.

Usage::

    .venv/bin/python experiments/diagnosis/defect_seeding/harness.py
    .venv/bin/python experiments/diagnosis/defect_seeding/harness.py \
        --inject ignored_gb_unit_conversion --inject drain_batched_credit_return
    .venv/bin/python experiments/diagnosis/defect_seeding/harness.py \
        --clean-baseline --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]


def _load_builder():
    """Load build_record.py (same trial machinery the committed record
    uses; loaded by path like tests/diagnosis/test_defect_seeding.py)."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec = importlib.util.spec_from_file_location("g9_defect_builder", HERE / "build_record.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_injected(builder, name: str) -> dict:
    """One flagged injection through the full pipeline
    (probe -> minimize -> attribute -> classify), same as the record."""
    return builder._run_trial(name, builder._trial_specs()[name])


def run_clean_baseline(builder, name: str) -> dict:
    """Injection OFF for one case space: clean engine vs clean engine.

    Probes the committed initial case AND every candidate the shrink
    ladder generates from it (the exact candidate set the minimizer
    would probe), then hands the same probe+ladder to the minimizer.
    Any REPRODUCES outcome is a FALSE ALARM — an engine finding.
    """
    spec = builder._trial_specs()[name]
    probe = builder._probe_pair(spec["clean_fn"], spec["clean_fn"], spec["quantity"])
    initial = spec["initial"]
    false_alarms = []
    initial_result = probe(initial)
    if initial_result.is_reproducer:
        false_alarms.append(
            {"case": "initial", "evidence": initial_result.evidence}
        )
    candidates = 1  # the initial case probe above
    for delta in spec["ladder"](initial):
        try:
            candidate = delta.apply(initial)
        except builder.InfeasibleDelta:
            continue
        if candidate == initial:
            continue
        candidates += 1
        result = probe(candidate)
        if result.is_reproducer:
            false_alarms.append(
                {
                    "case": delta.description,
                    "candidate": builder._public(candidate),
                    "evidence": result.evidence,
                }
            )
    minimized = builder.minimize_case(initial, probe, spec["ladder"])
    if minimized.reproducer_found:
        false_alarms.append({"case": "minimizer", "evidence": "clean probe reproduced"})
    return {
        "case_space": name,
        "injection": "off (clean engine vs clean engine)",
        "initial_outcome": initial_result.outcome,
        "candidates_probed": candidates,
        "false_alarm_count": len(false_alarms),
        "false_alarms": false_alarms,
        "minimizer_reproducer_found": minimized.reproducer_found,
    }


def _table_row(trial: dict) -> str:
    minimal = trial.get("minimal_case")
    if minimal is None:
        return f"{trial['defect_id']}: NOT DETECTED (finding)"
    size = ",".join(
        f"{key}={minimal[key]}"
        for key in sorted(minimal)
    )
    minimization = trial.get("minimization", {})
    probes = minimization.get("probes", "?")
    passes = minimization.get("passes", "?")
    return (
        f"{trial['defect_id']}\n"
        f"    detected: yes | reproducer: {size} ({probes} probes / {passes} passes)\n"
        f"    classification: {trial['classification']['label']}\n"
        f"    ground truth:  {trial['expected_label']} | "
        f"correct: {trial['classification_matches_ground_truth']}"
    )


def main(argv=None) -> int:
    builder = _load_builder()
    parser = argparse.ArgumentParser(
        prog="harness.py",
        description=(
            "Flag-driven fault injection over the seeded-defect diagnosis "
            "pipeline (probe -> minimize -> attribute -> classify)."
        ),
    )
    parser.add_argument(
        "--inject",
        action="append",
        choices=(*builder.TRIAL_ORDER, "all"),
        metavar="DEFECT",
        help=(
            "inject this semantic defect (repeatable; 'all' = the four "
            "committed trials; default: all)"
        ),
    )
    parser.add_argument(
        "--clean-baseline",
        action="store_true",
        help=(
            "also run every case space with the injection OFF (clean vs "
            "clean): any detected disagreement is a false alarm and fails"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable output instead of the text table",
    )
    args = parser.parse_args(argv)

    injections = args.inject or ["all"]
    selected = list(builder.TRIAL_ORDER) if "all" in injections else injections

    trials = [run_injected(builder, name) for name in selected]
    findings = [
        trial["defect_id"]
        for trial in trials
        if not trial.get("detected") or not trial.get("classification_matches_ground_truth")
    ]
    baselines = []
    if args.clean_baseline:
        baselines = [run_clean_baseline(builder, name) for name in builder.TRIAL_ORDER]
        baselines_with_alarms = [b for b in baselines if b["false_alarm_count"]]
        findings.extend(
            f"clean_baseline:{b['case_space']}" for b in baselines_with_alarms
        )

    detected = sum(1 for t in trials if t.get("detected"))
    classified = sum(1 for t in trials if t.get("classification_matches_ground_truth"))

    if args.json:
        print(
            json.dumps(
                {
                    "injected": selected,
                    "trials": trials,
                    "clean_baselines": baselines,
                    "summary": {
                        "injections_run": len(trials),
                        "detected": detected,
                        "classification_matches_ground_truth": classified,
                        "clean_baselines_run": len(baselines),
                        "false_alarms": sum(b["false_alarm_count"] for b in baselines),
                        "findings": findings,
                    },
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
    else:
        print(f"injections: {', '.join(selected)}")
        for trial in trials:
            print(_table_row(trial))
        if baselines:
            print("clean baselines (injection off, clean vs clean):")
            for b in baselines:
                print(
                    f"    {b['case_space']}: {b['candidates_probed']} candidates "
                    f"probed, {b['false_alarm_count']} false alarms "
                    f"(initial outcome: {b['initial_outcome']})"
                )
        print(
            f"summary: detected {detected}/{len(trials)}, correctly classified "
            f"{classified}/{len(trials)}, false alarms "
            f"{sum(b['false_alarm_count'] for b in baselines)}/{len(baselines) or 'n/a'}"
        )
        if findings:
            print(f"FINDINGS (honest, never hidden): {', '.join(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
