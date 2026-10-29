# Atlas cell 64r-doubling — rank class 64, algorithm family recursive-doubling

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The recursive-doubling family is declared for **power-of-two rank counts
only** (modeling assumption A-L0D-POW2). Rank class 64 = 2⁶ is a power of
two, so the family **applies** — there is no skip to record. The family
has no factorizations to sweep (unlike torus): the partner schedule is
fully determined (rank XOR 2^(i-1) at step i, k = log2(64) = 6 steps per
phase), so this cell has exactly ONE declared L0 identity:
`allreduce_recursive_doubling` over a fully-connected exchange fabric
(backend `analytical_l0_recursive_doubling`; serialized steps and phases
A-L0D-STEP, power-of-two schedule A-L0D-POW2, divisibility A-L0D-DIV —
every grid size is divisible by 4096, hence by 64, so the halving chunks
M/2^i and doubling chunks 2^(i-1)*M/r stay integral at every grid point).
This is the rank-64 mirror of [4r-doubling.md](4r-doubling.md),
[8r-doubling.md](8r-doubling.md), [16r-doubling.md](16r-doubling.md) and
[32r-doubling.md](32r-doubling.md).

Execution reachability (structural note, re-exercised live at rank 64 in
this stage): this backend is run-manifest-unreachable — the run path's collective-capability gate derives the collective name by
`rsplit("_", 1)` on the declared id `allreduce_recursive_doubling`, so the
gate advertises `allreduce_recursive` and the W1 `allreduce` op is never
admitted (a recorded reachability finding; the mismatch was
reproduced here through the gate function itself on this cell's backend
entry, with the tp64 workload's 6 generated ops read back as
`{'allreduce'}` against the gate's `{'allreduce_recursive'}`). The sweep
runner, which registers the algorithm id directly, is the execution
vehicle for this cell. Classified, not fixed; no src/ change was made.

Identity executed (per op, message M, ranks r = 64, k = log2(64) = 6,
exact Fractions; recursive-halving reduce phase + recursive-doubling
broadcast phase, serialized, one partner exchange per step):

    per-rank wire traffic  T(M, 64) = 2*(64-1)/64 * M = 63M/32
    completion time        t(M, 64) = 2*(64-1)/64 * M/B + 2*log2(64)*L = 63M/2048 + 2400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 64, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell (ring baseline: T = 63M/32,
t = 63M/2048 + 25200 — [64r-ring.md](64r-ring.md)):

1. **The traffic identity equals the ring's.** T(M, 64) = 63M/32 is the
   same per-rank wire-byte identity as the 64-rank ring
   ([64r-ring.md](64r-ring.md)) and the 64-rank single-port crossbar
   ([64r-crossbar.md](64r-crossbar.md)) — the module documents that all
   three L0 designs differ ONLY in the latency chain (ring 2*(r-1)*L =
   126L, recursive doubling 2*log2(r)*L = 12L, pipelined crossbar 2L). The
   wire column below is digit-for-digit the 64r-ring ladder's (verified
   exact-string against the landed 64r-ring sweep table); under this L0
   model the doubling schedule buys no traffic change over the ring at 64
   ranks either, only a shorter hop chain.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (63M/2048); the completion times differ only in the constant —
   12L = 2400 ns for doubling (two phases x six steps x L) versus
   2*(r-1)*L = 126L = 25200 ns for the ring. Hence the exact delta identity

       delta(M) = (t_rd - t_ring) / t_ring = -22800 / (63M/2048 + 25200) = -46694400 / (63*(M + 819200))

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities). The
   small-M envelope deepens from the 32-rank cell's -26/31 to
   **-57/63 = -19/21** — in general -(r-1-log2(r))/(r-1), the envelope
   law's fifth consecutive data point (-1/3 → -4/7 → -11/15 → -26/31 →
   -57/63, exactly as predicted from the landed 32r page and confirmed on
   this fresh execution) — and the 64-rank delta is more negative than the
   32-rank delta at every grid size (exact ratio law
   delta_64/delta_32 = (22800/10400)*(2048/1024)*(31M + 12697600)/(63M + 51609600)
   = (57/13)*(31M + 12697600)/(63M + 51609600), climbing 589/546 at M = 0
   through 59489/54873 at 4 KiB toward the 589/273 large-M limit — exactly
   twice the M = 0 rung, because the M = 0 rung divides by the ring's
   latency chain 126L = 2*(r-1)*L where the large-M rung divides by its
   wire coefficient r - 1 = 63 — because the ring's chain more than
   doubles 62L → 126L while the doubling chain grows only 10L → 12L: the
   constant gap 2*(r-1-log2(r))*L goes 400 → 1600 → 4400 → 10400 →
   **22800 ns** down the rank ladder. At the ring identity's own balance
   point M* = L·B·r = 819200 B the delta is exactly **-19/42 = -57/126**
   (general -(r-1-log2(r))/(2*(r-1)); the crossbar cell read -31/63 =
   -62/126 at the same point, [64r-crossbar.md](64r-crossbar.md); the
   doubling rungs at the lower classes' balance points read -304/357 at
   51200 B, -152/189 at 102400 B, -76/105 at 204800 B, -38/63 at
   409600 B).
3. **THE 57/62 RUNG LANDS — the 64r-crossbar forward prediction is
   confirmed on fresh execution.** The landed 64r-crossbar page recorded
   the forward prediction that the doubling delta is exactly
   (r-1-log2(r))/(r-2) = (64-1-6)/(64-2) = **57/62** of the crossbar
   cell's delta at every size (log2 64 = 6 — the rung the 32r-doubling
   page derived when it corrected the frozen-log2 slips into the ladder
   1/2 → 2/3 → 11/14 → 13/15 → 57/62 → 1). Verified here against the
   landed 64r-crossbar sweep table: delta_rd = (57/62)*delta_xb holds
   EXACTLY at all 12 grid sizes (e.g. -3800/4221 vs -12400/12663 at
   4 KiB, where (57/62)*(-12400/12663) = -3800/4221; -475/43533 vs
   -1550/130599 at 64 MiB, where (57/62)*(-1550/130599) = -475/43533),
   and the ratio is constant in M by construction — both deltas share the
   denominator 63M/2048 + 25200, so the rung is the gap ratio
   22800/24800 = 57/62 at every size. The midpoint pattern stays dead
   exactly as at ranks 8, 16 and 32: midpoint status needs 2*log2(r) = r,
   which among powers of two holds only at r = 2 and r = 4; at r = 64 the
   doubling chain 12L sits strictly BELOW the midpoint 64L — closer to
   the crossbar — so t_rd < (t_ring + t_xbar)/2 at every size (verified
   at all 12 grid sizes).
4. **The doubling chain breaks strictly below ALL THREE torus chains —
   the family's clean sweep of the middle of the ladder completes, in the
   slot the 64r-torus cell law-derived for it.** The landed 64-rank chain
   ladder reads crossbar 2L = 400 < doubling 12L = 2400 < torus8x8 28L =
   5600 < torus4x16 36L = 7200 < torus2x32 64L = 12800 < ring 126L =
   25200 ns — exactly where the 64r-torus index row placed the pending
   doubling chain ("12L = 2400 ns between crossbar and the square torus"),
   now tested on fresh execution. Verified against all three landed
   64r-torus tables: t_2x32 - t_rd = 31M/2048 + 10400,
   t_4x16 - t_rd = 45M/2048 + 4800 and t_8x8 - t_rd = 49M/2048 + 3200,
   each positive at every M — all three torus factorizations pay MORE
   wire than doubling at this rank class (47M/16, 27M/8 and 7M/2 vs
   63M/32 per rank) AND a longer chain, so there is no size at which any
   catches up (tied the 2x2 chain at r = 4, broke strictly below the
   single chain at r = 8, below both at r = 16 and r = 32, below all
   three at r = 64). The three M-coefficients {31, 45, 49} are the torus
   cells' own extra-wire ladder over the ring (the per-rank wire gaps in
   units of M/32) and the three constants are the chain differences
   52L/24L/16L. Against the crossbar, t_rd - t_xbar = 2*(log2(r)-1)*L =
   10L = 2000 ns at every size (ladder 2L → 4L → 6L → 8L → 10L at ranks
   4 → 8 → 16 → 32 → 64).

Phase symmetry, visible in the step decomposition at r = 64: the reduce
phase sends chunks {M/2, M/4, M/8, M/16, M/32, M/64} (halving) and the
broadcast phase sends {M/64, M/32, M/16, M/8, M/4, M/2} (doubling) —
mirror sequences, each phase costing exactly 63M/4096 + 1200 ns, so the
two phases are equal-cost at this rank count too (the property is
general: both phases sum to (r-1)/r*M/B + k*L; verified at all 12 grid
sizes through the backend's own step functions).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by the rank count 64, so the divisibility guard `A-L0D-DIV` never rejects
a grid point). Ring baseline ladder: [64r-ring.md](64r-ring.md) (its rows
carry delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 63M/32 (exact) | doubling CCT ns = 63M/2048 + 2400 (exact) | ring CCT ns = 63M/2048 + 25200 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 8064 | 2526 | 25326 | -3800/4221 | -90.0261 |
| 8192 | 8 KiB | 16128 | 2652 | 25452 | -1900/2121 | -89.5804 |
| 16384 | 16 KiB | 32256 | 2904 | 25704 | -950/1071 | -88.7021 |
| 65536 | 64 KiB | 129024 | 4416 | 27216 | -475/567 | -83.7743 |
| 131072 | 128 KiB | 258048 | 6432 | 29232 | -475/609 | -77.9967 |
| 262144 | 256 KiB | 516096 | 10464 | 33264 | -475/693 | -68.5426 |
| 1048576 | 1 MiB | 2064384 | 34656 | 57456 | -25/63 | -39.6825 |
| 2097152 | 2 MiB | 4128768 | 66912 | 89712 | -475/1869 | -25.4147 |
| 4194304 | 4 MiB | 8257536 | 131424 | 154224 | -475/3213 | -14.7837 |
| 16777216 | 16 MiB | 33030144 | 518496 | 541296 | -475/11277 | -4.2121 |
| 33554432 | 32 MiB | 66060288 | 1034592 | 1057392 | -475/22029 | -2.1562 |
| 67108864 | 64 MiB | 132120576 | 2066784 | 2089584 | -475/43533 | -1.0911 |

The delta column climbs monotonically from -3800/4221 toward the exact 0
asymptote — every row is the pure latency-term fact (twelve hop latencies
against the ring's one hundred twenty-six at identical wire bytes),
shrinking relative to a completion time whose bandwidth term grows
without bound.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; per op, per-rank traffic
63M/32 summed over ranks = 126M = 2*(r-1)*M — every sent byte received once
by the step partner; e.g. total wire bytes at M = 4096: 3096576 = 6 ops x
126 x 4096, digit-for-digit the 64r-ring and 64r-crossbar totals, consistent
with the equal traffic identity). All 12 rows rederived independently
from the closed forms during stage verification (doubling rows, baseline
rows, both delta-identity forms, the gap laws t_ring - t_rd = 22800 and
t_rd - t_xbar = 2000 ns, the 57/62-of-crossbar-delta relation against the
landed 64r-crossbar table, the no-midpoint inequality, the
delta_64/delta_32 ratio law against the landed 32r-doubling table, all
three torus ordering inequalities against the landed 64r-torus tables, the
phase-symmetry sums, and the conservation totals agree exact-string-equal
with the runner's `table.json`).

An arithmetic aside of the reduction (mirroring the 32r note): the gcd of
-22800 and the denominator 63M/2048 + 25200 steps 6, 12, 24 at the 4/8/16
KiB points and locks at 48 from the 64 KiB point up, so eight of the nine
large rows read exactly -475/d (d = 567, 609, 693, 1869, 3213, 11277,
22029, 43533) with exactly ONE further reduction: at 1 MiB,
M/2048 + 400 = 912 = 48*19 shares the factor 19 with the numerator
(22800 = 48*475 = 48*25*19), and the delta reduces fully to **-25/63** —
its denominator exactly r - 1 = 63 (the 32-rank cell's analog read -25/31
at its own 16 KiB point). The crossbar cell's "-1550/d" nine-row ladder
maps onto this one through the rung as exactly (57/62)*(-1550/d) =
-475/(d/3): the crossbar's reduced d is exactly 3 times the doubling's at
every one of the nine rows (1701 = 3*567 … 130599 = 3*43533) — at this
rank class the factor 3 enters the mapping because the crossbar numerator
24800 = 2^5*5^2*31 carries no 3 while (57/62)*1550 = 1425 = 3*475 does
(at 32r the mapping preserved denominators, (13/15)*(-750/d) = -650/d) —
and the crossbar's own 1 MiB row -1550/3591 maps to the same -25/63, the
special size shared by both cells.

## Crossover message sizes

**None — for the same structural reason as the 4-, 8-, 16- and 32-rank
doubling cells, not a sampling one.** Within this cell there is exactly
one declared identity, and against the ring baseline the two
completion-time identities have the SAME bandwidth term (63M/2048) and
differ only by a constant (2400 ns vs 25200 ns), so the two curves are
translates of each other in M: the doubling identity has the smaller
completion time at every finite M, the delta -22800/(63M/2048 + 25200)
never changes sign, and no payload size exists where the orderings swap.
Recorded honestly; the crossover question stays non-trivial only in cells
whose bandwidth coefficients differ (the 64-rank torus cell is the
example, with its four-way concurrent point at M = 819200 B).
(Arithmetic fact of the single identity, not a crossover: its bandwidth
term 63M/2048 equals its latency term 2400 at
M = 4915200/63 = 1638400/21 ≈ 78019.05 B, between the 64 KiB and 128 KiB
grid points — exactly log2(64) = 6 times the crossbar's own transition
819200/63 ≈ 13003.17 B, while the ring's own balance point 819200 B is
exactly r - 1 = 63 times the crossbar's: the chains {2L, 12L, 126L} place
their transitions in exact 1 : 6 : 63 = {1, log2 r, r - 1} ratio — the
rank-16 cell read 1 : 4 : 15 and the rank-32 cell 1 : 5 : 31, so the
transition-ratio law of the chain ladder holds at a third consecutive
rank class.)

## Run provenance

- sweep id: `488df890736cdf0726029b44439cd90791d7d039ac2c926b9385dc1b369856c1`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_64r_rdoubling_v1.yaml`;
  the sweep manifest is the only reachable execution path to this backend
  today — see the reachability note above)
- sweep manifest: `experiments/sweeps/atlas_64r_rdoubling_v1.yaml`
  (sha256 `07d1bd8a9ebc8576a24eeb68356ecb96270e52aa58aa9391c510f58093fbd9d0`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp64.yaml`
  (sha256 `e3930d1e8a2c651e893882b0085e3222c932dfae6e83ffd32e8838a667c05898`,
  the same file the 64r-ring/64r-crossbar/64r-torus cells used)
- topology: `experiments/topologies/rdoubling64_free_params.yaml`
  (sha256 `b01e8947848c6bbb0aaa50bfd771ab89b358579e35310a2c2f095e31bace0807`,
  new in this stage — the rank-64 mirror of
  rdoubling4/rdoubling8/rdoubling16/rdoubling32_free_params, same B and L;
  baseline topology `experiments/topologies/ring64_free_params.yaml`
  sha256 `28b187beb2220eebd3d05ab29e969d49badd517ffdc764b5627607211c34f42b`,
  the 64r-ring cell's own file)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `704467a0aaa5398199c3d078678de7a3e9e73b2da7eefeff7f6cc7b21acc1409`
  / `9408bdcb40067362cf6c3083ccdfbed511fd3ecbdddf3e5ef1e676e0b218535b`,
  byte-compared on consecutive reruns);
  `tests/determinism` 13 passed; full suite 650 passed (one above the
  pre-stage 649 measured with this stage's input files removed — the
  schema test's glob picks up the new topology file); paper-check PASS.

Catalog: [atlas index](README.md).
