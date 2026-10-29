# Atlas cell 8r-doubling — rank class 8, algorithm family recursive-doubling

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The recursive-doubling family is declared for **power-of-two rank counts
only** (modeling assumption A-L0D-POW2). Rank class 8 = 2³ is a power of
two, so the family **applies** — there is no skip to record. The family
has no factorizations to sweep (unlike torus): the partner schedule is
fully determined (rank XOR 2^(i-1) at step i, k = log2(r) = 3 steps per
phase), so this cell has exactly ONE declared L0 identity:
`allreduce_recursive_doubling` over a fully-connected exchange fabric
(backend `analytical_l0_recursive_doubling`; serialized steps and phases
A-L0D-STEP, power-of-two schedule A-L0D-POW2, divisibility A-L0D-DIV —
every grid size is divisible by 4096, hence by 8, so the halving chunks
M/2^i and doubling chunks 2^(i-1)*M/r stay integral at every grid point).
This is the rank-8 mirror of [4r-doubling.md](4r-doubling.md); one
structure there does NOT survive the mirror, recorded below (fact 3).

Execution reachability (structural note, unchanged from the 4-rank cell):
this backend is run-manifest-unreachable — the run path's
collective-capability gate cannot admit two-word algorithm suffixes (a recorded
reachability finding) — so the sweep runner, which
registers the algorithm id directly, is the execution vehicle for this
cell. Classified, not fixed; no src/ change was made.

Identity executed (per op, message M, ranks r = 8, k = log2(8) = 3, exact
Fractions; recursive-halving reduce phase + recursive-doubling broadcast
phase, serialized, one partner exchange per step):

    per-rank wire traffic  T(M, 8) = 2*(8-1)/8 * M = 7M/4
    completion time        t(M, 8) = 2*(8-1)/8 * M/B + 2*log2(8)*L = 7M/256 + 1200 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 8, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Three arithmetic facts drive the whole cell (ring baseline: T = 7M/4,
t = 7M/256 + 2800 — [8r-ring.md](8r-ring.md)):

1. **The traffic identity equals the ring's.** T(M, 8) = 7M/4 is the same
   per-rank wire-byte identity as the 8-rank ring ([8r-ring.md](8r-ring.md))
   and the 8-rank single-port crossbar ([8r-crossbar.md](8r-crossbar.md)) —
   the module documents that all three L0 designs differ ONLY in the
   latency chain (ring 2*(r-1)*L = 14L, recursive doubling 2*log2(r)*L = 6L,
   pipelined crossbar 2L). The wire column below is digit-for-digit the
   8r-ring ladder's; under this L0 model the doubling schedule buys no
   traffic change over the ring at 8 ranks either, only a shorter hop
   chain.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (7M/256); the completion times differ only in the constant —
   6L = 1200 ns for doubling (two phases x three steps x L) versus
   2*(r-1)*L = 14L = 2800 ns for the ring. Hence the exact delta identity

       delta(M) = (t_rd - t_ring) / t_ring = -1600 / (7M/256 + 2800) = -409600 / (7*(M + 102400))

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities). The
   small-M envelope deepens from the 4-rank cell's -1/3 to **-4/7** — in
   general -(r-1-log2(r))/(r-1) — and the 8-rank delta is more negative
   than the 4-rank delta at every grid size (ratio climbing 162/91 at
   4 KiB toward its 24/7 large-M limit), because the ring's chain doubles
   6L -> 14L while the doubling chain grows only 4L -> 6L: the gap
   2*(r-1-log2(r))*L quadruples 400 -> 1600 ns while r doubles. At the
   ring identity's own balance point M* = L*B*r = 102400 B the delta is
   exactly **-2/7** (general -(r-1-log2(r))/(2*(r-1)); the crossbar cell
   read -3/7 at the same point, [8r-crossbar.md](8r-crossbar.md)).
3. **The 4-rank midpoint pattern does NOT carry — and that is a fact, not
   a gap.** At r = 4 the doubling chain 2*log2(4) = 4 was the exact
   midpoint of the ring/crossbar chain ladder (6L and 2L), so
   t_rd = (t_ring + t_xbar)/2 exactly and the doubling delta was exactly
   HALF the crossbar cell's at every size ([4r-doubling.md](4r-doubling.md)
   fact 3). Midpoint status requires 2*log2(r) = r, which among powers of
   two holds ONLY at r = 2 (where all three identities coincide) and
   r = 4; at r = 8 the doubling chain 6L sits strictly BELOW the midpoint
   8L — closer to the crossbar — so t_rd < (t_ring + t_xbar)/2 at every
   size (verified at all 12 grid sizes). The exact relation replacing
   "half": the doubling delta is exactly **2/3 of the crossbar cell's
   delta** at every size (crossbar delta = -2400/(7M/256 + 2800),
   [8r-crossbar.md](8r-crossbar.md)); in general the ratio is
   (r-1-log2(r))/(r-2) — 1/2 at r = 4, **2/3 at r = 8**, then 11/14 at
   r = 16, 9/10 at r = 32, 59/62 at r = 64, tending to 1 as the doubling
   chain becomes negligible against the ring's. r = 4 is therefore the
   LAST rank class where the midpoint pattern holds. Concretely in the
   table below: the same denominators as the crossbar ladder, numerators
   exactly 2/3 (-50/91 vs -75/91 at 4 KiB; -100/114863 vs -150/114863 at
   64 MiB).

Phase symmetry, visible in the step decomposition at r = 8: the reduce
phase sends chunks {M/2, M/4, M/8} (halving) and the broadcast phase sends
{M/8, M/4, M/2} (doubling) — mirror sequences, each phase costing exactly
7M/512 + 600 ns, so the two phases are equal-cost at this rank count too
(the property is general: both phases sum to (r-1)/r*M/B + k*L).

Chain-ladder context within rank class 8 (arithmetic facts of the
identities, not comparisons): the four landed 8-rank latency chains are
crossbar 2L = 400, doubling 6L = 1200, torus 2x4 8L = 1600, ring 14L =
2800 ns. At r = 4 the doubling chain TIED the torus 2x2 chain (both 4L);
at r = 8 it breaks away strictly below it, and t_torus2x4 - t_rd =
3M/256 + 400 is positive at every M > 0 (the torus moves 10/7 of the wire
AND pays the longer chain). Against the crossbar, t_rd - t_xbar =
2*(log2(r)-1)*L = 4L = 800 ns at every size — the relation exercised live
in the recorded reachability note at the anchor's aggregate point.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by the rank count 8, so the divisibility guard `A-L0D-DIV` never rejects a
grid point). Ring baseline ladder: [8r-ring.md](8r-ring.md) (its rows
carry delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 7M/4 (exact) | doubling CCT ns = 7M/256 + 1200 (exact) | ring CCT ns = 7M/256 + 2800 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 7168 | 1312 | 2912 | -50/91 | -54.9451 |
| 8192 | 8 KiB | 14336 | 1424 | 3024 | -100/189 | -52.9101 |
| 16384 | 16 KiB | 28672 | 1648 | 3248 | -100/203 | -49.2611 |
| 65536 | 64 KiB | 114688 | 2992 | 4592 | -100/287 | -34.8432 |
| 131072 | 128 KiB | 229376 | 4784 | 6384 | -100/399 | -25.0627 |
| 262144 | 256 KiB | 458752 | 8368 | 9968 | -100/623 | -16.0514 |
| 1048576 | 1 MiB | 1835008 | 29872 | 31472 | -100/1967 | -5.0839 |
| 2097152 | 2 MiB | 3670016 | 58544 | 60144 | -100/3759 | -2.6603 |
| 4194304 | 4 MiB | 7340032 | 115888 | 117488 | -100/7343 | -1.3618 |
| 16777216 | 16 MiB | 29360128 | 459952 | 461552 | -100/28847 | -0.3467 |
| 33554432 | 32 MiB | 58720256 | 918704 | 920304 | -100/57519 | -0.1739 |
| 67108864 | 64 MiB | 117440512 | 1836208 | 1837808 | -100/114863 | -0.0871 |

The delta column climbs monotonically from -50/91 toward the exact 0
asymptote — every row is the pure latency-term fact (six hop latencies
against the ring's fourteen at identical wire bytes), shrinking relative
to a completion time whose bandwidth term grows without bound.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; per op, per-rank traffic
7M/4 summed over ranks = 14M = 2*(r-1)*M — every sent byte received once by
the step partner; e.g. total wire bytes at M = 4096: 344064 = 6 ops x
14 x 4096, digit-for-digit the 8r-ring and 8r-crossbar totals, consistent
with the equal traffic identity). All 12 rows rederived independently
from the closed forms during stage verification (doubling rows, baseline
rows, both delta-identity forms, the gap laws t_ring - t_rd = 8L and
t_rd - t_xbar = 4L, the 2/3-of-crossbar-delta relation, the
no-midpoint inequality, the phase-symmetry sums, and the conservation
totals agree exact-string-equal with the runner's `table.json`).

## Crossover message sizes

**None — for the same structural reason as the 4-rank doubling and both
other no-crossover cells, not a sampling one.** Within this cell there is
exactly one declared identity, and against the ring baseline the two
completion-time identities have the SAME bandwidth term (7M/256) and
differ only by a constant (1200 ns vs 2800 ns), so the two curves are
translates of each other in M: the doubling identity has the smaller
completion time at every finite M, the delta -1600/(7M/256 + 2800) never
changes sign, and no payload size exists where the orderings swap.
Recorded honestly; the crossover question stays non-trivial only in cells
whose bandwidth coefficients differ (the 8-rank torus cell is the example,
with its exact crossover at M = 102400 B). (Arithmetic fact of the single
identity, not a crossover: its bandwidth term 7M/256 equals its latency
term 1200 at M = 307200/7 ≈ 43885.71 B, between the 16 KiB and 64 KiB
grid points — exactly 3x the crossbar's own transition 102400/7 and 3/7
of the ring's balance point 102400 B, so the chain ladder {2L, 6L, 14L}
places its transitions in exact 1 : 3 : 7 ratio.)

## Run provenance

- sweep id: `7a8d1348d4d25f8bac52644e3eb822aea13a2ee99c81e7466c9e4631ab243f97`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_8r_rdoubling_v1.yaml`;
  the sweep manifest is the only reachable execution path to this backend
  today — see the reachability note above)
- sweep manifest: `experiments/sweeps/atlas_8r_rdoubling_v1.yaml`
  (sha256 `5bd127787527802c867d982471af0a732d1a9362f8d6ef39f6814fb76f7f4bd3`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp8.yaml`
  (sha256 `130d90384c91bc9f76ac40fea0386d0355355a3f5f57da608f710fd41e66abed`,
  the same file the 8r-ring/8r-crossbar/8r-torus cells used)
- topology: `experiments/topologies/rdoubling8_free_params.yaml`
  (sha256 `455892bcbd5182626b717446ade4a3c104d7acdbb9b191e1b7f25247d7a45bab`,
  pre-tracked from the P2 stage-S3 design-space work and reused as-is —
  B = 64, L = 200 already matched the atlas fairness rule; baseline
  topology `experiments/topologies/ring8_free_params.yaml` sha256
  `34b8aed485253e332423f625412f4b5820f7ddd7999fc4e3c762c79c02f2de84`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `43cd5e50ead4f44af28d86fbede7a4e893f9f980945646ef2937ad3dcbcecf3c`
  / `063f258a1bfce8cee5762e655b8cc4da3e8d0fb31c38e1b7ab39d07ea8b9ebb5`);
  `tests/determinism` 13 passed; full suite 543 passed; paper-check PASS.

Catalog: [atlas index](README.md).
