# G9 — Diagnosis experiments (minimize, localize, classify)

Status: PROPOSED (E0/identity-determinism evidence only; nothing tuned
toward any anchor; no disposition changes; no label upgrades). Every
number in the records below is exact-Fraction arithmetic over committed
execution blocks, and every block rebuilds byte-identically under its
guard test.

The diagnosis engine itself lives in `src/essun/diagnosis/`
(`minimize.py` — deterministic delta debugging with logged probes and
1-minimality certificates; `classify.py` — the fixed six-label taxonomy
and its mechanical classifier; `defects.py` — the synthetic ground-truth
defect carriers, never registered as backends, never stored as runs).

## Layout

```text
defect_seeding/           leg 3 — seeded-defect detection/classification
  build_record.py           record builder: probe -> minimize -> attribute -> classify
  harness.py                flag-driven runner: one --inject flag per defect, --clean-baseline
  defect_seeding_record_v1.json   4/4 detected, 4/4 classified (committed)
case_twin_l0_vs_astra/    leg 4 — the misleading twin comparison case study
  run_case_study.py         executor (Docker): minimization + knob ablations
  build_case_record.py      pure assembler of case_record_v1.json
  case_record_v1.json       the complete story (committed)
  ordinary_diff_demo.json   the S3 diff engine's own verdicts (the failure mode)
  minimization_v1.json      full probe log with content-addressed run ids
  ablations_v1.json         knob-ablation runs at the minimal reproducer
  probes/                   committed manifests/topologies/workloads per probe
  localization/             raw pinned-binary stdout per ablation (committed)
```

Guard tests: `tests/diagnosis/` (minimizer/classifier units,
`test_defect_seeding.py`, `test_case_twin.py`, and `test_defect_harness.py`
— injections change outputs; clean runs detect nothing; the CLI's exit
codes fail honestly on findings).

## Leg 3 — seeded defects (ground truth)

Four silent carriers over real essun engines; the pipeline measured
**4/4 detected, 4/4 classified to ground truth**, and with every
injection flag off (clean vs clean) **0 false alarms over 52 clean
probes** (4 case spaces x initial case + every shrink-ladder
candidate):

```
.venv/bin/python experiments/diagnosis/defect_seeding/harness.py            # all four flags
.venv/bin/python experiments/diagnosis/defect_seeding/harness.py \
    --inject ignored_gb_unit_conversion                                     # one flag
.venv/bin/python experiments/diagnosis/defect_seeding/harness.py --clean-baseline
```

Exit status 1 on any miss, misclassification, or false alarm (the
finding is printed, never hidden).

| seeded defect | minimal reproducer | classification |
| --- | --- | --- |
| credit-consumption bug (FLOOR vs UEC11-FC-R08 ROUNDUP) | r=2, M=896 B (chunk = 1.75 cells); shrinks below hit the carrier's crash boundary (sub-cell chunk) | specification_violation |
| return-batching error (whole-window batches) | 3 packets at W=2 packets; vanishes at 2 packets or W=1 packet; admission law UEC11-FC-R02 provably intact on the carrier's own trace | permitted_implementation_variation |
| ignored unit conversion (GB 2^30 skipped) | r=2, M=2 B, 1 op (case-space floor) | translation_defect |
| silent scheduling omission (latency term after op 1) | r=2, M=2 B, 2 ops; vanishes at 1 op | specification_violation |

## Leg 4 — the twin case study

Engine A (essun `analytical_l0`) vs engine B (ASTRA-sim analytical,
pinned Docker) at identical inputs: **+118.07%** disagreement (exactly
the G7 case record's twin delta). Ordinary diffing reports the magnitude
and stops. The diagnosis engine shrinks the reproducer **72 ranks / 2
GiB -> 2 ranks / 2 bytes** (34 probes, all logged with run ids), then
localizes at the reproducer by single-knob ablations of the pinned
binary:

- chunk-serialization knob (A-AS1-CHUNKS-1): **430 of the 460 ns** twin
  delta, exactly measured — `abstraction_difference`;
- memory knob (A-AS2-MEM-BW): measured **inert** (exactly 0 ns) at the
  minimal case — localization is case-specific and the record does not
  extrapolate;
- endpoint knob (A-AS2-DELAY-POS): **infeasible to zero** (the pinned
  binary aborts, EventQueue.cpp:33 — raw stdout committed) — its isolated
  contribution is unknown: `unresolved`;
- after every feasible relaxation an exact **12419/414 ns (7.5%)
  residual stays visible**: `unresolved`;
- the wire-conservation axis is a declared gap: `missing_capability`
  (the ordinary diff engine's own `not_comparable` verdict).

Reproduce (clean clone): see `verification` in
`case_twin_l0_vs_astra/case_record_v1.json` (in-process L0 legs need no
Docker; ASTRA legs and re-localization need the pinned container).
