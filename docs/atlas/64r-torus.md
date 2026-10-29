# Atlas cell 64r-torus — rank class 64, algorithm family torus

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The torus family factorizes 64 ranks as **1x64, 2x32, 4x16, or 8x8**
(unordered, plus transposes). The stage sweeps the factorizations; **64 is
the FIRST atlas rank class with THREE declared, generatable torus
identities** (ranks 4 and 8 had one each; ranks 16 and 32 two each) — and
with a structural first of its own, an INTERIOR factorization:

- **1x64 — SKIP (config cannot be generated).** Attempted both through the
  backend loader and through the sweep runner's grid gate (with a real
  topology file present); both reject it with
  `analytical_l0_torus2d: a torus dimension must wrap >= 2 ranks, got 1x64`
  (shape guard, assumption A-L0T-SHAPE). The landed golden
  `tests/golden/test_l0_torus2d_golden.py::test_loader_extracts_exact_fractions_and_rejects_bad_grids`
  asserts the same guard (its bad grid is 1x8 at ranks 8); the rank-64
  strings above were exercised live during this stage. The **64x1
  transpose** is rejected identically by the same guard (`got 64x1`),
  exercised through the loader during the stage. The rejection is also
  arithmetically honest: a degenerate 1x64 grid would evaluate to
  `t_ring(M,1) + t_ring(M,64) = 0 + t_ring(M,64)` — exactly the flat-ring
  identity that already IS this rank class's baseline cell
  ([64r-ring.md](64r-ring.md)) — so 1x64 is not a new identity, and it is
  recorded in the index's Recorded skips, never forced.
- **2x32 — the skewed declared identity** (backend `analytical_l0_torus2d`;
  modeling assumptions A-L0T-SEQ sequential dimensions, A-L0T-UNIF uniform
  links, A-L0T-SHAPE grid shape): `allreduce_torus2d` over a 2x32
  ring-x-ring grid. The **32x2 transpose** loads cleanly and evaluates to
  the IDENTICAL identity (completion time and wire traffic exactly equal
  at every probed size — the module identities are symmetric in
  dim1 x dim2, re-verified through the loader during this stage), so the
  grid carries 2x32 once.
- **4x16 — the INTERIOR declared identity**, the same backend over a 4x16
  grid (its **16x4 transpose** verified identical through the loader during
  the stage). **No interior factorization (neither r1 = 2 nor r1 = r2)
  exists below rank 64**, so this is the atlas's first non-extreme shape —
  the first data point between the skew and square branch extremes of the
  family's coefficient law (fact 3).
- **8x8 — the square declared identity**, the same backend over an 8x8 grid
  (its own transpose). The square-family ladder (2x2 at rank 4, 4x4 at rank
  16) PAUSED at rank 32 (odd exponent, no square grid) and **revives here:
  8x8 is the first square grid since 4x4 at rank 16**. 64 is therefore the
  FIRST — and only planned — rank class where the skew, interior and square
  shapes coexist as distinct identities, the widest intra-family torus
  comparison in the atlas.

Identities executed (per op, message M, ranks r = 64, exact Fractions;
each dimension runs a full ring AllReduce of the entire M, dimensions
serialized):

    per-dimension kernel       t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L
    2x32 per-rank wire         T(M, 64) = 2*(2 - 1/2 - 1/32) * M = 47M/16
    2x32 completion time       t(M, 64) = t_ring(M,2) + t_ring(M,32) = 47M/1024 + 12800 ns   (chain 2*(2+32-2) = 64 hops)
    4x16 per-rank wire         T(M, 64) = 2*(2 - 1/4 - 1/16) * M = 27M/8
    4x16 completion time       t(M, 64) = t_ring(M,4) + t_ring(M,16) = 27M/512 + 7200 ns     (chain 2*(4+16-2) = 36 hops)
    8x8 per-rank wire          T(M, 64) = 2*(2 - 1/8 - 1/8) * M = 7M/2
    8x8 completion time        t(M, 64) = 2*t_ring(M,8) = 7M/128 + 5600 ns                   (chain 2*(8+8-2) = 28 hops)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 64, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell (ring baseline: T = 63M/32,
t = 63M/2048 + 25200 — [64r-ring.md](64r-ring.md)):

1. **All three declared identities pay more wire than the ring, ordered by
   squareness.** The 2x32 torus moves 47M/16 per rank = **94/63 of the
   ring's 63M/32 (+31/63 at every payload size)**; the 4x16 torus moves
   27M/8 = 108/63 of it (+45/63 = +5/7); the 8x8 torus moves 7M/2 = 112/63
   = 16/9 (+49/63 = +7/9). The square grid pays the most wire of the cell
   (the interior pays 54/47 of the skewed grid's bytes for 9/16 of its
   chain; the square pays 28/27 of the interior's for 7/9 of its chain)
   and owns the shortest chain (28 hops vs 36 vs 64 vs the flat ring's
   126): squareness trades wire for chain inside the family, exactly as
   the family trades both against the ring (ranks 16 and 32 read the same
   fact for their two shapes; the family's wire-identity ladder climbs
   2M → 5M/2 → 11M/4 → 3M → 23M/8 → 13M/4 → **47M/16 → 27M/8 → 7M/2**,
   walking toward the 2*(2 - 0 - 0) = 4M degenerate limit, the skew
   sub-ladder being the closed form 3M − 4M/r).
2. **All three identities scale the ring's two terms by exact
   complementary factors.** The 2x32 bandwidth term 47M/1024 =
   (94/63)*(the ring's 63M/2048) with latency 64L = 12800 = (32/63)*(the
   ring's 126L = 25200); the 4x16 bandwidth term 27M/512 = (108/63)*beta
   with latency 36L = 7200 = (18/63)*lambda; the 8x8 bandwidth term
   7M/128 = (112/63)*beta with latency 28L = 5600 = (14/63)*lambda — each
   pair summing to 2 exactly (94+32 = 108+18 = 112+14 = 126). So each gap
   collapses to the exact linear form
       t_2x32 - t_ring = (31/63)*(beta - lambda) = 31M/2048 - 12400 ns
       t_4x16 - t_ring = (45/63)*(beta - lambda) = 45M/2048 - 18000 ns
       t_8x8  - t_ring = (49/63)*(beta - lambda) = 49M/2048 - 19600 ns
   — the three gaps in exact ratio 31:45:49 at every payload size (rank 16
   read 7:9, rank 32 15:21 = 5:7).
3. **The factorization law (from [8r-torus.md](8r-torus.md), confirmed on
   two factorizations at 16r and at 32r) reproduces all three gaps and
   UNIFIES the branch ladders.** The law
   `t_torus - t_ring = 2*(r1-1)*(r2-1) * (M/(B*r) - L)` gives coefficients
   2*1*31 = 62, 2*3*15 = 90 and 2*7*7 = 98 (31M/2048 − 12400,
   45M/2048 − 18000 and 49M/2048 − 19600, exactly the gaps above), and the
   delta identities are
       delta_2x32(M) = (31/63) * (M - 819200)/(M + 819200)
       delta_4x16(M) = (5/7)  * (M - 819200)/(M + 819200)
       delta_8x8(M)  = (7/9)  * (M - 819200)/(M + 819200)
   with exact envelopes delta(0) = -31/63, -5/7 and -7/9 (the pure
   latency-term facts 12800/25200 − 1, 7200/25200 − 1, 5600/25200 − 1) and
   delta(inf) = +31/63, +5/7 and +7/9 (the pure bandwidth-term facts
   94/63 − 1, 108/63 − 1, 112/63 − 1 — at every rank class each shape's
   envelope magnitude equals its extra-wire fraction), and
   **delta_4x16 = (45/31)*delta_2x32 and delta_8x8 = (49/45)*delta_4x16 =
   (49/31)*delta_2x32 exactly at every M**. The law's delta coefficient
   (r1-1)(r2-1)/(r-1) = (r − (r1+r2) + 1)/(r-1) is strictly increasing as
   r1+r2 falls (AM–GM: r1+r2 >= 2*sqrt(r), equality iff square), so
   squareness orders the envelopes within the class — 31/63 < 45/63 <
   49/63 — and the two landed branch laws are exactly its EXTREMES,
   re-derived here from the law itself rather than carried as forward
   notes: the skew branch (r1 = 2) is (r−2)/(2(r−1)) = **31/63**
   (ladder 1/3 → 3/7 → 7/15 → 15/31 → 31/63, fifth consecutive rung,
   walking to 1/2) and the square branch is (√r−1)/(√r+1) = **7/9**
   (ladder 1/3 → 3/5 → 7/9, the 32r page's stated revival — the law
   evaluated at √64 = 8, confirmed on fresh executions). The interior
   factorization contributes the law's FIRST non-extreme data point,
   3(r−4)/(4(r−1)) = **5/7** at 4x16 — whose r = 16 evaluation 3/5
   coincides with the square branch there because 4x4 is simultaneously
   the middle and the square factorization of 16 = 2^4 (only two
   factorizations exist); the next interior rung is 63/85 at 256r. The
   closest-to-square branch (2^k x 2^(k+1) at r = 2^(2k+1): 3/7 → 21/31)
   PAUSES at 64 — an even exponent, where the closest-to-square shape IS
   the square — reviving at 105/127 (128r). The law's predicted crossover
   M* = L*B*r = 819200 B holds for ALL THREE factorizations — the
   stated prediction for this cell, confirmed on fresh
   executions.
4. **All three tori cross pairwise — and every crossing is the SAME
   size.** The intra-family gaps are themselves differences of two
   factorization-law gaps (coefficient 2*Delta[(r1-1)(r2-1)]):
       t_4x16 - t_2x32 = 7M/1024 - 5600  = 2*(45-31) * (M/4096 - 200)
       t_8x8  - t_4x16 = M/512 - 1600    = 2*(49-45) * (M/4096 - 200)
       t_8x8  - t_2x32 = 9M/1024 - 7200  = 2*(49-31) * (M/4096 - 200)
   Below the balance point the SQUARE grid has the smallest completion
   time (its chain 28L beats 36L beats 64L; e.g. −4896 ns vs the skewed
   grid at the 256 KiB grid point), above it the SKEWED grid does (its
   wire 47M/16 beats 27M/8 beats 7M/2; +2016 ns at the 1 MiB grid point).

**The four-way concurrent point.** At M = 819200 B all FOUR identities
evaluate to exactly the same completion time, 50400 ns (ring
63*819200/2048 + 25200; 2x32 47*819200/1024 + 12800; 4x16
27*819200/512 + 7200; 8x8 7*819200/128 + 5600): the total order
8x8 < 4x16 < 2x32 < ring below M* reverses completely
(ring < 2x32 < 4x16 < 8x8) above it, a full reversal of a FOUR-identity
chain at one exact size — the atlas's FIRST four-way concurrent point
([16r-torus.md](16r-torus.md) and [32r-torus.md](32r-torus.md) had
three-way).

**Rank-class ladder vs [4r-torus.md](4r-torus.md) /
[8r-torus.md](8r-torus.md) / [16r-torus.md](16r-torus.md) /
[32r-torus.md](32r-torus.md)** (closed forms, not measurements): the
crossover ladder 51200 -> 102400 -> 204800 -> 409600 -> **819200 B**
tracks M* = L*B*r exactly (the same sizes as the ring balance ladder;
fifth consecutive rung, predicted from the landed 32r page and confirmed
here — cross-checked 409600*2 = 819200 and 819200/1024 = 800 exactly).
819200 B sits between the 256 KiB and 1 MiB grid points — the same
bracket as 409600 B at rank 32, because the shared ladder's x4 step spans
2^18 → 2^20. The signed rank-class curves cross the 32-rank deltas
exactly once each (one positive root per pairing — the product of the two
roots is −L²B²r₆₄r₃₂ < 0 at every pairing; other roots negative):
the 64r 2x32 delta against the 32r 2x16 delta at
M = 25600*(953 + 3*sqrt(100969)) ≈ 48800476 B (between the 32 MiB and
64 MiB grid points), the 64r 2x32 delta against the 32r 4x8 delta at
M = (409600/181)*(3*sqrt(43507) − 571) ≈ 123898 B (between the 64 KiB and
128 KiB points), the 64r 4x16 delta against the 32r 2x16 delta at
M = 81920*(13 + sqrt(219)) ≈ 2277265 B (between 2 MiB and 4 MiB), the
64r 4x16 delta against the 32r 4x8 delta at
M = 51200*(151 + sqrt(22929)) ≈ 15484070 B (between 4 MiB and 16 MiB),
the 64r 8x8 delta against the 32r 2x16 delta at
M = (409600/41)*(88 + 3*sqrt(1234)) ≈ 1931963 B (between 1 MiB and
2 MiB), and the 64r 8x8 delta against the 32r 4x8 delta at
M = 51200*(58 + 6*sqrt(97)) ≈ 5995169 B (between 4 MiB and 16 MiB).
Five of the six keep the atlas's standing orientation (the higher-rank
delta is the lower, more torus-favoring curve below the crossing); the
sixth — 64r 2x32 vs 32r 4x8 — is the atlas's FIRST FLIPPED-ORIENTATION
rank-class pairing: the 64-rank skew delta starts ABOVE the 32-rank
closest-to-square delta (delta(0) = −31/63 > −21/31) and ends below it
(+31/63 < +21/31), because shape, not rank, sets the vertical order when
the classes compare different squareness. At the lower rank classes'
crossover sizes the 64-rank deltas are negative and torus-favoring
(−31/189, −5/21 and −7/27 at 409600; −31/105, −3/7 and −7/15 at 204800;
−31/81, −5/9 and −49/81 at 102400; −155/357, −75/119 and −35/51 at
51200); at 819200 all three are 0 by definition. Latency-chain ladder
within rank class 64 so far: crossbar 2L < 8x8 torus 28L < 4x16 torus 36L
< 2x32 torus 64L < ring 126L (the 32r ladder read 2L < 20L < 32L < 62L);
the pending 64r-doubling cell's law-derived chain 2*log2(64) = 12 hops =
2400 ns slots between the crossbar and the square torus.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by every torus dimension pair 2/32, 4/16 and 8/8, so the divisibility
guard `A-L0T-DIV` never rejects a grid point). Ring baseline ladder:
[64r-ring.md](64r-ring.md) (its rows carry delta exactly 0 by
construction; the sweep grid carries the baseline config so the runner
can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire 2x32 = 47M/16 | wire 4x16 = 27M/8 | wire 8x8 = 7M/2 | 2x32 CCT ns = 47M/1024 + 12800 | 4x16 CCT ns = 27M/512 + 7200 | 8x8 CCT ns = 7M/128 + 5600 | ring CCT ns = 63M/2048 + 25200 | delta 2x32 (exact) | delta 2x32 (%) | delta 4x16 (exact) | delta 4x16 (%) | delta 8x8 (exact) | delta 8x8 (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 12032 | 13824 | 14336 | 12988 | 7416 | 5824 | 25326 | -6169/12663 | -48.7167 | -995/1407 | -70.7178 | -1393/1809 | -77.0039 |
| 8192 | 8 KiB | 24064 | 27648 | 28672 | 13176 | 7632 | 6048 | 25452 | -341/707 | -48.2320 | -495/707 | -70.0141 | -77/101 | -76.2376 |
| 16384 | 16 KiB | 48128 | 55296 | 57344 | 13552 | 8064 | 6496 | 25704 | -217/459 | -47.2767 | -35/51 | -68.6275 | -343/459 | -74.7277 |
| 65536 | 64 KiB | 192512 | 221184 | 229376 | 15808 | 10656 | 9184 | 27216 | -713/1701 | -41.9165 | -115/189 | -60.8466 | -161/243 | -66.2551 |
| 131072 | 128 KiB | 385024 | 442368 | 458752 | 18816 | 14112 | 12768 | 29232 | -31/87 | -35.6322 | -15/29 | -51.7241 | -49/87 | -56.3218 |
| 262144 | 256 KiB | 770048 | 884736 | 917504 | 24832 | 21024 | 19936 | 33264 | -527/2079 | -25.3487 | -85/231 | -36.7965 | -119/297 | -40.0673 |
| 1048576 | 1 MiB | 3080192 | 3538944 | 3670016 | 60928 | 62496 | 62944 | 57456 | 31/513 | 6.0429 | 5/57 | 8.7719 | 49/513 | 9.5517 |
| 2097152 | 2 MiB | 6160384 | 7077888 | 7340032 | 109056 | 117792 | 120288 | 89712 | 403/1869 | 21.5623 | 195/623 | 31.3002 | 91/267 | 34.0824 |
| 4194304 | 4 MiB | 12320768 | 14155776 | 14680064 | 205312 | 228384 | 234976 | 154224 | 3193/9639 | 33.1258 | 515/1071 | 48.0859 | 721/1377 | 52.3602 |
| 16777216 | 16 MiB | 49283072 | 56623104 | 58720256 | 782848 | 891936 | 923104 | 541296 | 15097/33831 | 44.6248 | 2435/3759 | 64.7779 | 3409/4833 | 70.5359 |
| 33554432 | 32 MiB | 98566144 | 113246208 | 117440512 | 1552896 | 1776672 | 1840608 | 1057392 | 3441/7343 | 46.8610 | 4995/7343 | 68.0240 | 777/1049 | 74.0705 |
| 67108864 | 64 MiB | 197132288 | 226492416 | 234881024 | 3092992 | 3546144 | 3675616 | 2089584 | 8959/18657 | 48.0195 | 1445/2073 | 69.7057 | 14161/18657 | 75.9018 |

All three delta columns climb monotonically toward their exact asymptotes
(+31/63 ≈ +49.21%, +5/7 ≈ +71.43% and +7/9 ≈ +77.78%) — the large-M rows
are the bandwidth-term facts (the tori move 94/63, 108/63 and 112/63 of
the ring's bytes per rank), the small-M rows are the latency-term facts
(their hop chains are 32/63, 18/63 and 14/63 of the ring's). The 8x8
column is the most extreme at BOTH ends (−77.00% ↔ +77.78%): the square
shape is the most torus-like identity of the cell in each term's own
direction, as the square grid was at rank 16 and the closest-to-square at
rank 32 — and the three columns stay in exact ratio 31:45:49 at every
row.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; 2x32: dimension 1 has 32
disjoint rings of 2 x 2*(2-1)*M each = 64M, dimension 2 has 2 disjoint
rings of 32 x 2*31*M each = 124M, so each op totals 188M = 2*(2r - r1 -
r2)*M; 4x16: dimension 1 has 16 disjoint rings of 4 x 2*3*M each = 96M,
dimension 2 has 4 disjoint rings of 16 x 2*15*M each = 120M, so each op
totals 216M; 8x8: each dimension has 8 disjoint rings of 8 x 2*7*M each
= 112M, so each op totals 224M; e.g. total wire bytes at M = 4096: 2x32
4620288 = 6 ops x 188 x 4096, 4x16 5308416 = 6 ops x 216 x 4096, 8x8
5505024 = 6 ops x 224 x 4096; the baseline rows read 3096576 = 6 ops x
126 x 4096, digit-for-digit the 64r-ring ladder, cross-checked 12/12
against the landed 64r-ring sweep table). All 48 rows (three tori and
baseline) rederived independently from the closed forms during stage
verification — wire, time, delta, and conservation totals agree
exact-string-equal with the runner's `table.json`, and all three delta
identities (31/63)·(M-819200)/(M+819200), (5/7)·(M-819200)/(M+819200)
and (7/9)·(M-819200)/(M+819200) were checked equal to the runner's deltas
at all 12 sizes, as were the gap law 2*(r1-1)*(r2-1)*(M/4096 - 200) for
all three shapes, the exact delta ratios 45/31, 49/45 and 49/31, the
intra-family gaps 28·(M/4096 − 200), 8·(M/4096 − 200) and 36·(M/4096 −
200), and the four-way equality of all identities at M = 819200.

## Crossover message sizes

**Six exact crossovers, all at ONE off-grid size: M = 819200 B
(800 KiB).** All three delta identities change sign there (2x32:
−527/2079 at the 256 KiB grid point → +31/513 at 1 MiB; 4x16: −85/231 →
+5/57; 8x8: −119/297 → +49/513) and all three intra-family gaps do too
(−3808, −1088 and −4896 ns at 256 KiB → +1568, +448 and +2016 ns at
1 MiB) — six pairwise crossovers (ring/2x32, ring/4x16, ring/8x8,
2x32/4x16, 2x32/8x8, 4x16/8x8) coinciding exactly, which is the four-way
concurrent point above. 819200 is not a member of the shared ladder (not
a power of two; it lies inside the ladder's x4 interval 2^18 → 2^20 — the
same bracket as 409600 B at rank 32), so the grid samples the crossover
without containing it — the page reports the exact size rather than a
bracket alone. By the factorization law every torus factorization's gap
is proportional to (M - L*B*r), so EVERY torus crossover lands exactly at
the ring identity's own balance point M* = L*B*r = 819200 B — the same
size noted on [64r-ring.md](64r-ring.md) and predicted from the
8r/16r/32r cells' derivations; rank 64 exercises the prediction on three
factorizations at once, the third consecutive multi-factorization rank
class and the first with three. At the lower rank classes' crossover
sizes the 64-rank deltas are negative and torus-favoring (listed in the
ladder paragraph above); at 819200 all three are 0 by definition.

## Run provenance

- sweep id: `75ff1c25e6825c57dab1d7a08d7982b6a0e186338c6f948e52ca50796ac7eeaa`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_64r_torus_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_64r_torus_v1.yaml`
  (sha256 `e58e04a20a6fd79eaee973e450d5fcbf5503311f8c4870a8fa05d5c9dbf5d420`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp64.yaml`
  (sha256 `e3930d1e8a2c651e893882b0085e3222c932dfae6e83ffd32e8838a667c05898`,
  the same file the 64r-ring and 64r-crossbar cells used)
- topologies: `experiments/topologies/torus2d64_2x32_free_params.yaml`
  (sha256 `b279a4f0200ba594d952080d31a7bbe22ab1c75b9e29130baa48162a6c8053e6`),
  `experiments/topologies/torus2d64_4x16_free_params.yaml`
  (sha256 `0139c84580a0e8f0b3b6d7e7f84c0e9cc58271d624118d2b4ec54bce70f2317c`)
  and `experiments/topologies/torus2d64_8x8_free_params.yaml`
  (sha256 `49f8be8ea0d04837b8bf0c3f5c9236328e5d62d5db8aadf7216fcd36930a6f03`);
  baseline topology `experiments/topologies/ring64_free_params.yaml` sha256
  `28b187beb2220eebd3d05ab29e969d49badd517ffdc764b5627607211c34f42b`,
  the same file the 64r-ring/64r-crossbar cells used)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `f26a3df13a3629f10a3668c2b2d2b66c12b736445bafccf8fe20c667ee9aa6cd`
  / `8f171682d32be93ebc7524630836394691db2f6305acadf8577256e9a0d75b22`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 643 passed
  (three above the 64r-ring stage's 639 — the schema glob's three new
  torus64 files); paper-check PASS.

Catalog: [atlas index](README.md).
