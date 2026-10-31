# Case study 01 — a misleading cross-engine comparison, minimized and explained

Date: 2026-10-31. Status: **PROPOSED** (evidence level E0 — identity and
determinism only; nothing in this case is calibrated against hardware,
and no number was tuned toward any published measurement). Machine
record: `experiments/diagnosis/case_twin_l0_vs_astra/case_record_v1.json`
(rebuilt byte-identically by its guard test,
`tests/diagnosis/test_case_twin.py`). Reproduction card, written for a
clean clone: [reproduce-misleading-01.md](reproduce-misleading-01.md).

This document tells one story end to end. Two of our engines, run on
identical inputs, produced completion times that differ by +118% under
the same observable name, and a reader of the two numbers would conclude
that one engine is roughly 2.2x too optimistic. We show why that reading
misleads, what ordinary diffing can and cannot say about it, and how our
diagnosis pipeline converted the gap into a two-rank, two-byte
experiment that explains the dominant part of the difference exactly
while leaving a measured 7.5% visibly unexplained.

## 1. The comparison that misleads

Engine A is our `analytical_l0` backend, a closed-form identity for a
chunked ring AllReduce: with r ranks, per-direction link bandwidth B and
per-hop latency L, it computes `t = 2(r−1)/r · M/B + 2(r−1)·L` for a
payload of M bytes, in exact rational arithmetic
(`src/essun/backends/analytical/l0.py`). The quantity it emits as O-CCT
is wire-only: link serialization of the per-rank traffic plus hop
latency, and nothing else. Engine B is the ASTRA-sim analytical
(congestion-unaware) frontend, pinned to commit `4ce9ecfe` in a Docker
image and driven through our adapter
(`src/essun/backends/astra_sim/adapter.py`); its native Ring AllReduce
reports a wall time for the same collective. That wall is a different
quantity: it bundles link time with a chunk-serialization schedule
(`system.active-chunks-per-dimension`), memory-side processing
(`system.local-mem-bw`), and an endpoint processing delay
(`system.endpoint-delay`) — three knobs the adapter declares as
translation assumptions (A-AS1-CHUNKS-1, A-AS2-MEM-BW, A-AS2-DELAY-POS)
because the pinned binary requires a value for each before it will run
at all.

We ran both engines on one shared topology file and one shared workload:
72 ranks, B = 828 B/ns, L = 200 ns, a single AllReduce of 2,147,483,592
bytes (the largest 72-divisible payload at or below 2 GiB; both
parameters are free parameters of the twin, not measurements). Engine A
reports `2129415031/414` ns ≈ 5,143,514.6 ns; engine B reports
11,216,448 ns. The ratio is exactly `4643609472/2129415031` ≈ 2.1807 —
engine B lands +118.07% above engine A on the numbers produced by run
`82b2296fc18604ad74566246a4bff0249b6055fbd96ac9782cbb3502dc6e76c3`
(engine A) and run
`0c6b8ec4868a8ed440e7883b7a7b2b9498b03bfecd44c7d133891ae3efa8e03f`
(engine B). This pair is not synthetic: it re-derives, digit for digit,
the 2 GiB twin recorded in the earlier cross-engine case record at
`experiments/gonogo/case_a3_cross_engine/case_record_v1.json` (runs
`2e3b54e953b3e8dc8f7b59637ea4fd3cb5b5ced9c57fd4070433841509644c7b` and
`8bcf3697dd731d1c47146ff59ad37c5577e3b6358d6ed4b8eb414f1d19baf252`).

Why does the comparison mislead? Both outputs are named "completion
time of the collective," so the natural reading is that the two engines
disagree about the same physical quantity, and that one of them is
wrong by 2.2x — presumably engine A, the simpler model, missing most of
the cost. The truth we establish below is narrower and more useful: the
two numbers are different observables (a wire-only time versus a wall
time bundling three extra declared terms), the disagreement needs
neither 72 ranks nor 2 GiB to appear, and once the case is small enough
to decompose, the single largest term in the gap is engine B's
single-active-chunk serialization — a declared modeling choice, not a
defect in either engine. The misleading part is not the gap itself; it
is reading a bundle-to-bare comparison as a same-quantity error.

## 2. What ordinary diffing says

Our differential-comparison engine
(`src/essun/validation/diff_engine.py`) is the tool an engineer would
reach for, and it does its job correctly. Asked to compare the two runs
under the exact O-CCT obligation, it returns one divergence record:
op 0, engine A `2129415031/414` ns versus engine B 11,216,448 ns, ratio
2.1807 — diff record
`297adbb36aa92421017aff38d96741ecceba01226caff697e40da2aba20a76da`.
Asked to compare wire bytes (the O-CONSERVATION obligation), it refuses
honestly with `not_comparable`, because engine B's declared capabilities
say it emits no byte accounting at all — diff record
`bcc3797f23f385b1c125c4ddd5a669926b18c5edc0083c1e338623cd81a3b695`.

Both verdicts are recorded verbatim in the case record, and both stop
exactly where a diff must stop. A diff says that the numbers differ and
by how much; it cannot say why they differ, how small the smallest
disagreeing case is, or that the two quantities differ in kind rather
than in accuracy. An engineer holding only the diff record would still
be holding the misleading reading. That gap between "the numbers
differ" and "here is the cause, bounded and labeled" is the space the
diagnosis engine exists to close.

## 3. The distinguishing experiment: make the case small

A disagreement that needs 72 ranks and 2 GiB would be expensive to
explain; a disagreement that survives at the floor of the case space can
be explained exhaustively. Our minimizer
(`src/essun/diagnosis/minimize.py`) therefore shrank the case by
deterministic delta debugging over (ranks, payload): a fixed ladder of
rank divisors and payload halvings, each candidate executed as a real
run pair through the orchestrator — engine A in-process, engine B in the
pinned container — with every probe logged alongside both
content-addressed run ids. The full log is committed in
`experiments/diagnosis/case_twin_l0_vs_astra/minimization_v1.json`
(35 passes, 34 probes, every manifest under
`experiments/diagnosis/case_twin_l0_vs_astra/probes/`).

The result: all 34 probes reproduced the disagreement and were accepted,
because the gap survived every shrink the ladder offers. The minimal
reproducer is **2 ranks and 2 bytes** — 36x fewer ranks and
1,073,741,796x fewer payload bytes than the initial pair, the floor of
the declared ladder (a ring needs at least two ranks, and the payload
halving stops at one byte per rank; at the floor the ladder offers no
further step, so 1-minimality holds with respect to the declared ladder
with an empty final-pass rejection set). At that floor, engine A reports
`165601/414` ns ≈ 400.0024 ns and engine B reports 860 ns — the
disagreement is still +115.0%, produced by runs
`9162fade0942094b80a05fca3df0e35afc07be1801ae98cd6696bdfd2dc68f09` and
`2ce2995beb32db88fb3e813893514934414b071928c2a2e3fb385fb59250bbbf`.
The naive reading is already dead: a difference that persists from 2
GiB down to 2 bytes at a nearly constant relative size is structural,
not an accumulation of per-byte or per-rank error. What remains is to
name the structure.

## 4. Naming the cause: single-knob ablations at the reproducer

At the minimal reproducer we ablated each of engine B's three declared
bundling knobs, one at a time, by patching the pinned binary's
`system.json` and running the container directly (raw stdout for every
ablation is committed under
`experiments/diagnosis/case_twin_l0_vs_astra/localization/r2-m2/`).
The measured decomposition of the 460 ns gap (exactly `190439/414` ns)
between engine B's 860 ns wall and engine A's 400.0024 ns identity:

| knob | ablation | measured effect |
| --- | --- | --- |
| `active-chunks-per-dimension` | 1 → 4 | wall 860 → 430 ns: **430 ns of the 460 ns gap (93.4%, exactly `178020/190439`)** |
| `local-mem-bw` | 1600 → 1600000 | wall 860 → 860 ns: **exactly 0 ns — inert at this case** |
| `endpoint-delay` | 10 → 0 | **infeasible**: the pinned binary aborts (`EventQueue.cpp:33`, exit 134; stdout committed) |
| both feasible knobs relaxed | chunks 4, mem 1600000 | wall 430 ns: **residual `12419/414` ns ≈ 30.0 ns (7.5% of engine A's value) stays unattributed** |

The chunk-serialization row is the answer the diff could not give.
Engine B's pinned configuration serializes the collective through one
active chunk per dimension, so even a two-byte AllReduce pays a full
serialization pipeline; engine A's identity has no such term because it
models wire time only. Relaxing that single knob to 4 removes 430 of
the 460 ns exactly. The memory row is a case-specific negative result
we record rather than generalize: at 2 bytes the memory-bandwidth term
carries no weight, whatever it would carry at 2 GiB — this record does
not extrapolate the decomposition to the initial pair. The endpoint row
is an honest wall: the term cannot be zeroed in the pinned binary at
all (the assertion fires on a zero-delay callback chain), so its
isolated contribution is unmeasurable from below and stays unknown.
After every feasible relaxation, engine B's wall (430 ns) is still not
engine A's closed form; the remaining 30.0 ns belongs to engine B's
native ring pipeline and to the endpoint term together, and the record
does not split what the evidence cannot split.

## 5. Classifying the cause

The diagnosis engine's taxonomy
(`src/essun/diagnosis/classify.py`) has six fixed labels, and each
component of this disagreement was classified by its mechanical rules —
deterministic rule order over an exact fact set, unit-tested per rule,
with nonzero residuals kept visible by construction. The labels
recorded in the case record:

- **chunk-serialization bundling — `abstraction_difference`.** Engine
  B's wall matches its declared different-quantity bundling, and the
  component delta (430 ns) is exactly the measured single-knob effect,
  so the residual for this component is zero. This is the label for
  "two correct engines, two different observables," and it is the
  dominant component.
- **memory-side processing — `abstraction_difference`** (declared
  bundling, measured inert at this case; no stronger claim asserted).
- **endpoint-delay bundling — `unresolved`.** The term is declared and
  certainly contributes, but zeroing it aborts the pinned binary, so no
  exact attribution exists; the honest label is the one that keeps the
  question open.
- **post-relaxation residual — `unresolved`, `12419/414` ns visible.**
  No declared knob accounts for the remaining 30.0 ns, so it is
  recorded as an open fact rather than absorbed into a story.
- **wire-conservation axis — `missing_capability`.** Engine B declares
  O-CONSERVATION unsupported; the diff engine's own `not_comparable`
  verdict is the evidence, recorded rather than worked around.

Read together, the labels say the thing the +118% could not: the gap
was never a 2.2x-wrong model. It was two different observables — a
wire-only identity compared against a wall bundling a dominant
serialization term — plus one unmeasurable term and one visibly
unexplained 7.5%, each with its own name. We classify, and we do not
tune: no parameter was moved anywhere in this chain, and every run
declares `calibration_target: []`.

## 6. What this case claims, and what it does not

Everything above is a claim about our two engines at free-parameter
values (B = 828 B/ns, L = 200 ns) on one shared input — nothing in it
says either engine matches physical hardware, and the PROPOSED (E0)
label keeps that boundary explicit. The decomposition was measured at
the minimal reproducer (2 ranks, 2 bytes) and is stated only there; we
did not measure the per-knob decomposition at the 2 GiB pair, and the
case record says so. The 93.4% figure is exact arithmetic over
committed executions, not an estimate; the 7.5% residual is exact too,
and it is exactly the part we do not explain. We consider the
explanation confirmed because an independent execution reproduces it:
the guard test rebuilds the record byte-identically, re-derives the
decomposition in exact rationals, re-executes the minimal engine-A leg
to its declared run id, and re-parses every committed ablation stdout —
and the reproduction card lets any reader repeat all of it, plus the
Docker legs, from a clean clone.

## 7. Reproduce it

The card at [reproduce-misleading-01.md](reproduce-misleading-01.md)
walks the whole chain from a fresh clone: the misleading pair (one
in-process run, one pinned-container run, expected run ids
byte-for-byte), the ordinary diff and its two verdicts, the minimal
reproducer, the exact decomposition re-derived from committed stdout,
the classifier producing the recorded labels, and the guard test that
holds the whole record honest. The full re-localization (all 34
minimization probes plus the ablations, Docker required) is one command
on the same card.
