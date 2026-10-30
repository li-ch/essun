# G9 case study — the misleading twin comparison, minimized and classified

Date: 2026-10-30. Status: **PROPOSED** (E0). Machine record:
`case_record_v1.json` (pure builder `build_case_record.py`; guard test
`tests/diagnosis/test_case_twin.py` rebuilds it byte-identically,
re-executes the in-process legs, and re-parses the committed ablation
stdout). Every number below is exact-Fraction arithmetic over committed
execution blocks; nothing was tuned toward any anchor, no disposition
changed, no label upgraded.

## The misleading comparison

Engine A — essun `analytical_l0`, the ring identity `t = 2(r−1)/r·M/B +
2(r−1)L`. Engine B — ASTRA-sim analytical (pinned Docker `4ce9ecfe`,
congestion-unaware frontend, native Ring AllReduce). **Identical
topology file, identical workload bytes**: r=72, B=828 B/ns, L=200 ns,
one 2 GiB-class AllReduce (the CAL-A3 2 GiB floor bracket — the same
twin as the G7 case study).

Engine A says 514,346.6 ns. Engine B says 11,216,448 ns. **+118.07%**
(exactly the G7 record's +118.1% twin delta — this study's initial pair
re-derives it, run ids in the record).

## How ordinary diffing fails

The S3 differential-validation engine, asked to compare the pair, does
exactly its job: one first-divergence record (O-CCT, op 0, ratio
2.1807) and — on the wire-bytes obligation — an honest `not_comparable`
(engine B declares O-CONSERVATION unsupported). A diff reports *that*
the numbers differ and *by how much*. It cannot say *why*, cannot say
*how small the disagreement really is*, and cannot tell the engineer
that the two "completion times" are different observables. Both diff
records are committed (`ordinary_diff_demo.json`).

## MINIMIZE

The diagnosis engine shrinks the case with a deterministic ladder
(ranks: divisor chain; payload: halving to the divisibility floor).
Every candidate is a real dual-engine execution through the
orchestrator — 34 logged probes, each with both content-addressed run
ids, all manifests committed under `probes/`.

**Minimal reproducer: 2 ranks, 2 bytes, one op.** The case-space floor:
1,073,741,796× fewer payload bytes, 36× fewer ranks, and the
disagreement is still +115.0% (wall 860 ns vs identity 165601/414 ≈
400.0024 ns). The final pass's rejections — with their exact deviations
and run ids — are the 1-minimality certificate.

## LOCALIZE

At the reproducer, single-knob ablations of the pinned binary's
translation knobs (the S2-counterexample precedent: direct container
runs, patched `system.json`, raw stdout committed):

| knob | ablation | measured effect on the twin delta |
|---|---|---|
| `active-chunks-per-dimension` (A-AS1-CHUNKS-1) | 1 → 4 | **−430 ns of the 460 ns delta (93.4%)** — the dominant bundling term |
| `local-mem-bw` (A-AS2-MEM-BW) | 1600 → 1600000 | **exactly 0 ns — inert at the minimal case** (a bundling term at 2 GiB carries no weight at 2 bytes; this record does not extrapolate) |
| `endpoint-delay` (A-AS2-DELAY-POS) | 10 → 0 | **infeasible** — the pinned binary aborts (`EventQueue.cpp:33`, exit 134, stdout committed); the term cannot be zeroed, so its isolated contribution is unknown |
| after all feasible relaxations | both | **exact residual 12419/414 ≈ 30.0 ns (7.5% of engine A's value) remains** |

## CLASSIFY

Components, through the mechanical classifier (`src/essun/diagnosis/classify.py`):

- **chunk-serialization bundling — `abstraction_difference`**: engine
  B's Wall bundles a declared serialization term with no counterpart in
  engine A's declared wire-only identity; the component delta is
  exactly the measured single-knob effect.
- **memory-side processing — `abstraction_difference`** (declared
  bundling; measured inert here).
- **endpoint-delay bundling — `unresolved`**: certainly present,
  unmeasurable from below (zeroing aborts the binary).
- **post-relaxation residual — `unresolved`, 12419/414 ns VISIBLE**:
  engine B's native ring pipeline at relaxed knobs is not engine A's
  closed form; no declared knob accounts for it.
- **wire-conservation axis — `missing_capability`**: engine B's
  declared gap, recorded by the ordinary diff engine itself.

**The +118% was never a 2×-wrong model. It was two different
observables** — and the diagnosis says exactly which parts are declared
semantics, which are infeasible to isolate, and which 7.5% stays
unexplained.

## Independent check (the reproducer pipeline)

From a clean clone: `tests/diagnosis/test_case_twin.py` rebuilds the
record, re-derives the decomposition arithmetic, re-executes the
minimal reproducer's L0 leg to its declared run id, and re-parses every
committed ablation stdout — no Docker. With the pinned container: the
verification block in `case_record_v1.json` lists the one-command
re-executions (the minimal ASTRA leg, and `run_case_study.py execute`
for the full re-localization).
