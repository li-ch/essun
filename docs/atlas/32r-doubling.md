# Atlas cell 32r-doubling — rank class 32, algorithm family recursive-doubling

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The recursive-doubling family is declared for **power-of-two rank counts
only** (modeling assumption A-L0D-POW2). Rank class 32 = 2⁵ is a power of
two, so the family **applies** — there is no skip to record. The family
has no factorizations to sweep (unlike torus): the partner schedule is
fully determined (rank XOR 2^(i-1) at step i, k = log2(32) = 5 steps per
phase), so this cell has exactly ONE declared L0 identity:
`allreduce_recursive_doubling` over a fully-connected exchange fabric
(backend `analytical_l0_recursive_doubling`; serialized steps and phases
A-L0D-STEP, power-of-two schedule A-L0D-POW2, divisibility A-L0D-DIV —
every grid size is divisible by 4096, hence by 32, so the halving chunks
M/2^i and doubling chunks 2^(i-1)*M/r stay integral at every grid point).
This is the rank-32 mirror of [4r-doubling.md](4r-doubling.md),
[8r-doubling.md](8r-doubling.md) and [16r-doubling.md](16r-doubling.md).

Execution reachability (structural note, re-exercised live at rank 32 in
this stage): this backend is run-manifest-unreachable — the run path's collective-capability gate derives the collective name by
`rsplit("_", 1)` on the declared id `allreduce_recursive_doubling`, so the
gate advertises `allreduce_recursive` and the W1 `allreduce` op is never
admitted (a recorded reachability finding; the mismatch was
reproduced here through the gate function itself on this cell's backend
entry). The sweep runner, which registers the algorithm id directly, is
the execution vehicle for this cell. Classified, not fixed; no src/ change
was made.

Identity executed (per op, message M, ranks r = 32, k = log2(32) = 5,
exact Fractions; recursive-halving reduce phase + recursive-doubling
broadcast phase, serialized, one partner exchange per step):

    per-rank wire traffic  T(M, 32) = 2*(32-1)/32 * M = 31M/16
    completion time        t(M, 32) = 2*(32-1)/32 * M/B + 2*log2(32)*L = 31M/1024 + 2000 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 32, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell (ring baseline: T = 31M/16,
t = 31M/1024 + 12400 — [32r-ring.md](32r-ring.md)):

1. **The traffic identity equals the ring's.** T(M, 32) = 31M/16 is the
   same per-rank wire-byte identity as the 32-rank ring
   ([32r-ring.md](32r-ring.md)) and the 32-rank single-port crossbar
   ([32r-crossbar.md](32r-crossbar.md)) — the module documents that all
   three L0 designs differ ONLY in the latency chain (ring 2*(r-1)*L =
   62L, recursive doubling 2*log2(r)*L = 10L, pipelined crossbar 2L). The
   wire column below is digit-for-digit the 32r-ring ladder's (verified
   against the landed 32r-ring sweep table); under this L0 model the
   doubling schedule buys no traffic change over the ring at 32 ranks
   either, only a shorter hop chain.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (31M/1024); the completion times differ only in the constant —
   10L = 2000 ns for doubling (two phases x five steps x L) versus
   2*(r-1)*L = 62L = 12400 ns for the ring. Hence the exact delta identity

       delta(M) = (t_rd - t_ring) / t_ring = -10400 / (31M/1024 + 12400) = -10649600 / (31*(M + 409600))

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities). The
   small-M envelope deepens from the 16-rank cell's -11/15 to **-26/31**
   — in general -(r-1-log2(r))/(r-1), the envelope law's fourth
   consecutive data point (-1/3 → -4/7 → -11/15 → -26/31, exactly as
   predicted from the landed 16r page and confirmed on this fresh
   execution) — and the 32-rank delta is more negative than the 16-rank
   delta at every grid size (exact ratio law
   delta_32/delta_16 = (10400/4400)*(1024/512)*(15M + 3072000)/(31M + 12697600)
   = (52/11)*(15M + 3072000)/(31M + 12697600), climbing 390/341 at M = 0
   through 39780/34441 at 4 KiB toward the 780/341 large-M limit — exactly
   twice the M = 0 rung, because the M = 0 rung divides by the ring's
   latency chain 62L = 2*(r-1)*L where the large-M rung divides by its
   wire coefficient r - 1 = 31 — because the ring's chain more than
   doubles 30L →
   62L while the doubling chain grows only 8L → 10L: the constant gap
   2*(r-1-log2(r))*L goes 400 → 1600 → 4400 → **10400 ns** down the rank
   ladder. At the ring identity's own balance point M* = L·B·r = 409600 B
   the delta is exactly **-13/31** (general -(r-1-log2(r))/(2*(r-1)); the
   crossbar cell read -15/31 at the same point,
   [32r-crossbar.md](32r-crossbar.md); the doubling rungs at the lower
   classes' balance points read -208/279 at 51200 B, -104/155 at
   102400 B, -52/93 at 204800 B).
3. **The corrected 13/15 rung LANDS — the 32r-crossbar forward prediction
   is confirmed on fresh execution.** The landed 32r-crossbar page
   recorded the forward prediction that the doubling delta is exactly
   (r-1-log2(r))/(r-2) = (31-5)/30 = **26/30 = 13/15** of the crossbar
   cell's delta at every size (log2 32 = 5). Verified here against the
   landed 32r-crossbar sweep table: delta_rd = (13/15)*delta_xb holds
   EXACTLY at all 12 grid sizes (e.g. -2600/3131 vs -3000/3131 at 4 KiB;
   -50/9827 vs -750/127751 at 64 MiB), and the ratio is constant in M by
   construction — both deltas share the denominator 31M/1024 + 12400, so
   the rung is the gap ratio 10400/12000 = 13/15 at every size. The
   frozen-log2 26/29 variant (log2 r stuck at 4) satisfies NO grid size.
   The correct ratio ladder reads 1/2 → 2/3 → 11/14 → **13/15** → 57/62
   → 1: the "9/10 at 32r" and "59/62 at 64r" rungs written forward in
   the 8r- and 16r-doubling index rows are arithmetic slips against the
   law's own closed form (at 64r the rung is (64-1-6)/(64-2) = 57/62);
   recorded here honestly without editing the landed rows. The midpoint
   pattern stays dead exactly as at ranks 8 and 16: midpoint status needs
   2*log2(r) = r, which among powers of two holds only at r = 2 and
   r = 4; at r = 32 the doubling chain 10L sits strictly BELOW the
   midpoint 32L — closer to the crossbar — so t_rd < (t_ring + t_xbar)/2
   at every size (verified at all 12 grid sizes).
4. **The doubling chain breaks strictly below BOTH torus chains — the
   family's clean sweep of the middle of the ladder continues.** The
   landed 32-rank chain ladder reads crossbar 2L = 400 < doubling 10L =
   2000 < torus4x8 20L = 4000 < torus2x16 32L = 6400 < ring 62L =
   12400 ns. Verified against both landed 32r-torus tables:
   t_2x16 - t_rd = 15M/1024 + 4400 and t_4x8 - t_rd = 21M/1024 + 2000,
   each positive at every M — both torus factorizations pay MORE wire
   than doubling at this rank class (23M/8 and 13M/4 vs 31M/16 per rank)
   AND a longer chain, so there is no size at which either catches up
   (tied the 2x2 chain at r = 4, broke strictly below the single chain
   at r = 8, below both at r = 16 and again at r = 32). Against the
   crossbar, t_rd - t_xbar = 2*(log2(r)-1)*L = 8L = 1600 ns at every
   size (ladder 2L → 4L → 6L → 8L at ranks 4 → 8 → 16 → 32).

Phase symmetry, visible in the step decomposition at r = 32: the reduce
phase sends chunks {M/2, M/4, M/8, M/16, M/32} (halving) and the broadcast
phase sends {M/32, M/16, M/8, M/4, M/2} (doubling) — mirror sequences, each
phase costing exactly 31M/2048 + 1000 ns, so the two phases are equal-cost
at this rank count too (the property is general: both phases sum to
(r-1)/r*M/B + k*L; verified at all 12 grid sizes through the backend's own
step functions).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by the rank count 32, so the divisibility guard `A-L0D-DIV` never rejects
a grid point). Ring baseline ladder: [32r-ring.md](32r-ring.md) (its rows
carry delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 31M/16 (exact) | doubling CCT ns = 31M/1024 + 2000 (exact) | ring CCT ns = 31M/1024 + 12400 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 7936 | 2124 | 12524 | -2600/3131 | -83.0406 |
| 8192 | 8 KiB | 15872 | 2248 | 12648 | -1300/1581 | -82.2264 |
| 16384 | 16 KiB | 31744 | 2496 | 12896 | -25/31 | -80.6452 |
| 65536 | 64 KiB | 126976 | 3984 | 14384 | -650/899 | -72.3026 |
| 131072 | 128 KiB | 253952 | 5968 | 16368 | -650/1023 | -63.5386 |
| 262144 | 256 KiB | 507904 | 9936 | 20336 | -650/1271 | -51.1408 |
| 1048576 | 1 MiB | 2031616 | 33744 | 44144 | -650/2759 | -23.5593 |
| 2097152 | 2 MiB | 4063232 | 65488 | 75888 | -650/4743 | -13.7044 |
| 4194304 | 4 MiB | 8126464 | 128976 | 139376 | -650/8711 | -7.4618 |
| 16777216 | 16 MiB | 32505856 | 509904 | 520304 | -650/32519 | -1.9988 |
| 33554432 | 32 MiB | 65011712 | 1017808 | 1028208 | -650/64263 | -1.0115 |
| 67108864 | 64 MiB | 130023424 | 2033616 | 2044016 | -50/9827 | -0.5088 |

The delta column climbs monotonically from -2600/3131 toward the exact 0
asymptote — every row is the pure latency-term fact (ten hop latencies
against the ring's sixty-two at identical wire bytes), shrinking relative
to a completion time whose bandwidth term grows without bound.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; per op, per-rank traffic
31M/16 summed over ranks = 62M = 2*(r-1)*M — every sent byte received once
by the step partner; e.g. total wire bytes at M = 4096: 1523712 = 6 ops x
62 x 4096, digit-for-digit the 32r-ring and 32r-crossbar totals, consistent
with the equal traffic identity). All 12 rows rederived independently
from the closed forms during stage verification (doubling rows, baseline
rows, both delta-identity forms, the gap laws t_ring - t_rd = 10400 and
t_rd - t_xbar = 1600 ns, the 13/15-of-crossbar-delta relation against the
landed 32r-crossbar table, the no-midpoint inequality, the
delta_32/delta_8-era ratio law against the landed 16r-doubling table, both
torus ordering inequalities against the landed 32r-torus tables, the
phase-symmetry sums, and the conservation totals agree exact-string-equal
with the runner's `table.json`).

An arithmetic aside of the reduction (mirroring the 16r note): 16 divides
both -10400 and 31M/1024 + 12400 at every grid size from 16 KiB up (and
never below — the gcd is 4 at 4 KiB and 8 at 8 KiB), so the reduced delta
reads exactly -650/d for eight consecutive points from 64 KiB through
32 MiB, with exactly TWO further reductions: at 16 KiB, d = 806 shares the
factor 26 with 650, the delta reducing fully to **-25/31**; at 64 MiB,
d = 127751 = 13*31*317 shares the factor 13, reducing to **-50/9827**.
The crossbar cell's "-750/d / -250/d" ladder maps onto this one as exactly
(13/15)*(-750/d) = -650/d and (13/15)*(-250/d) = -650/(3d) — the same
ratio law visible at reduced denominators (its 128 KiB, 2 MiB and 32 MiB
rows are the three 3d points: 1023, 4743, 64263).

## Crossover message sizes

**None — for the same structural reason as the 4-, 8- and 16-rank doubling
cells, not a sampling one.** Within this cell there is exactly one declared
identity, and against the ring baseline the two completion-time identities
have the SAME bandwidth term (31M/1024) and differ only by a constant
(2000 ns vs 12400 ns), so the two curves are translates of each other in M:
the doubling identity has the smaller completion time at every finite M,
the delta -10400/(31M/1024 + 12400) never changes sign, and no payload size
exists where the orderings swap. Recorded honestly; the crossover question
stays non-trivial only in cells whose bandwidth coefficients differ (the
32-rank torus cell is the example, with its three-way concurrent point at
M = 409600 B). (Arithmetic fact of the single identity, not a crossover:
its bandwidth term 31M/1024 equals its latency term 2000 at
M = 2048000/31 ≈ 66064.52 B, between the 64 KiB and 128 KiB grid points —
exactly log2(32) = 5 times the crossbar's own transition 409600/31 ≈
13212.90 B, while the ring's own balance point 409600 B is exactly
r - 1 = 31 times the crossbar's: the chains {2L, 10L, 62L} place their
transitions in exact 1 : 5 : 31 = {1, log2 r, r - 1} ratio — the rank-16
cell read 1 : 4 : 15, so the transition-ratio law of the chain ladder is
{1, log2 r, r - 1} at every rank class.)

## Run provenance

- sweep id: `18aa1a57f69630cd060defcd36cc75cec4248cc1311eacd1f68be9f734278081`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_32r_rdoubling_v1.yaml`;
  the sweep manifest is the only reachable execution path to this backend
  today — see the reachability note above)
- sweep manifest: `experiments/sweeps/atlas_32r_rdoubling_v1.yaml`
  (sha256 `f6e67acfab9f5904a09308e7c456a820fc874259e941f908cf7a321ab62e34a1`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp32.yaml`
  (sha256 `170833ec1347c016120a1f9dde5e6b771f0ac643c1f2626b0ebb905653083ea8`,
  the same file the 32r-ring/32r-crossbar/32r-torus cells used)
- topology: `experiments/topologies/rdoubling32_free_params.yaml`
  (sha256 `ba18470b0f9328ff17b2175dabe4acefed31760053bf1edb4cac0dccf7bdb578`,
  new in this stage — the rank-32 mirror of
  rdoubling4/rdoubling8/rdoubling16_free_params, same B and L; baseline
  topology `experiments/topologies/ring32_free_params.yaml`
  sha256 `90e694ecb6a71bc9ac4b050c8c54de506f76346b242e19b7c63712b758337ac2`,
  the 32r-ring cell's own file)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `7de52254f0531fea568a7de46bd685f33810948f05080beac54647d3a9ace15a`
  / `525e86ca35e27608507c428a82f3c60becdb51127f28c7ef67a71b5e32232e63`,
  byte-compared on consecutive reruns);
  `tests/determinism` 13 passed; full suite 581 passed (one above the
  pre-stage 580 measured with this stage's input files removed — the
  schema test's glob picks up the new topology file); paper-check PASS.

Catalog: [atlas index](README.md).
