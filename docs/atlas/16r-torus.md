# Atlas cell 16r-torus — rank class 16, algorithm family torus

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The torus family factorizes 16 ranks as **1x16, 2x8, or 4x4** (unordered,
plus transposes). The stage sweeps the factorizations; **16 is the FIRST
atlas rank class with TWO declared, generatable torus identities** (at
rank 4 the only one was 2x2; at rank 8 only 2x4):

- **1x16 — SKIP (config cannot be generated).** Attempted both through the
  backend loader and through the sweep runner's grid gate (with a real
  topology file present); both reject it with
  `analytical_l0_torus2d: a torus dimension must wrap >= 2 ranks, got 1x16`
  (shape guard, assumption A-L0T-SHAPE). The landed golden
  `tests/golden/test_l0_torus2d_golden.py::test_loader_extracts_exact_fractions_and_rejects_bad_grids`
  asserts the same guard (its bad grid is 1x8 at ranks 8); the rank-16
  strings above were exercised live during this stage. The **16x1
  transpose** is rejected identically by the same guard (`got 16x1`),
  exercised through the loader during the stage. The rejection is also
  arithmetically honest: a degenerate 1x16 grid would evaluate to
  `t_ring(M,1) + t_ring(M,16) = 0 + t_ring(M,16)` — exactly the flat-ring
  identity that already IS this rank class's baseline cell
  ([16r-ring.md](16r-ring.md)) — so 1x16 is not a new identity, and it is
  recorded in the index's Recorded skips, never forced.
- **2x8 — the skewed declared identity** (backend `analytical_l0_torus2d`;
  modeling assumptions A-L0T-SEQ sequential dimensions, A-L0T-UNIF uniform
  links, A-L0T-SHAPE grid shape): `allreduce_torus2d` over a 2x8
  ring-x-ring grid. The **8x2 transpose** loads cleanly and evaluates to
  the IDENTICAL identity (completion time and wire traffic exactly equal
  at every probed size — the module identities are symmetric in
  dim1 x dim2, re-verified through the loader during this stage), so the
  grid carries 2x8 once.
- **4x4 — the square declared identity**, the same backend over a 4x4
  grid (its own transpose). At rank 4 the single 2x2 grid was
  simultaneously the skewed AND the square factorization; 16 = 2x8 = 4x4
  is the first rank class where the two shapes are distinct identities,
  so this is the atlas's first intra-family torus comparison.

Identities executed (per op, message M, ranks r = 16, exact Fractions;
each dimension runs a full ring AllReduce of the entire M, dimensions
serialized):

    per-dimension kernel       t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L
    2x8 per-rank wire          T(M, 16) = 2*(2 - 1/2 - 1/8) * M = 11M/4
    2x8 completion time        t(M, 16) = t_ring(M,2) + t_ring(M,8) = 11M/256 + 3200 ns   (chain 2*(2+8-2) = 16 hops)
    4x4 per-rank wire          T(M, 16) = 2*(2 - 1/4 - 1/4) * M = 3M
    4x4 completion time        t(M, 16) = t_ring(M,4) + t_ring(M,4) = 3M/64 + 2400 ns      (chain 2*(4+4-2) = 12 hops)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 16, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell (ring baseline: T = 15M/8,
t = 15M/512 + 6000 — [16r-ring.md](16r-ring.md)):

1. **Both declared identities pay more wire than the ring, differently.**
   The 2x8 torus moves 11M/4 per rank = **22/15 of the ring's 15M/8
   (+7/15 at every payload size)**; the 4x4 torus moves 3M = **8/5 of it
   (+3/5)**. The square grid pays the most wire of the cell (12/11 of the
   skewed grid's bytes) and owns the shortest chain (12 hops vs the skewed
   grid's 16 vs the flat ring's 30): squareness trades wire for chain
   inside the family, exactly as the family trades both against the ring
   (rank-8 read the same fact as +3/7 for its single 2x4 shape).
2. **Both identities scale the ring's two terms by exact complementary
   factors.** The 2x8 bandwidth term 11M/256 = (22/15)*(the ring's
   15M/512) with latency 16L = 3200 = (8/15)*(the ring's 30L = 6000); the
   4x4 bandwidth term 3M/64 = (8/5)*beta with latency 12L = 2400 =
   (2/5)*lambda. So each gap collapses to the exact linear form
       t_2x8 - t_ring = (7/15)*(beta - lambda) = 7M/512 - 2800 ns
       t_4x4 - t_ring = (3/5)*(beta - lambda) = 9M/512 - 3600 ns
   — the two gaps in exact ratio 7:9 at every payload size.
3. **The factorization law (from [8r-torus.md](8r-torus.md)) reproduces
   both gaps and is exercised on two factorizations for the first time.**
   The law `t_torus - t_ring = 2*(r1-1)*(r2-1) * (M/(B*r) - L)` gives
   coefficients 2*1*7 = 14 and 2*3*3 = 18 (14M/1024 - 2800 and
   18M/1024 - 3600, exactly the gaps above), and the delta identities are
       delta_2x8(M) = (7/15) * (M - 204800)/(M + 204800)
       delta_4x4(M) = (3/5) * (M - 204800)/(M + 204800)
   with exact envelopes delta(0) = -7/15 and -3/5 (the pure latency-term
   facts 3200/6000 - 1 and 2400/6000 - 1) and delta(inf) = +7/15 and
   +3/5 (the pure bandwidth-term facts 22/15 - 1 and 8/5 - 1), and
   **delta_4x4 = (9/7)*delta_2x8 exactly at every M**. The law's
   predicted crossover M* = L*B*r = 204800 B holds for BOTH
   factorizations — the stated prediction, confirmed.
4. **The two tori cross each other — and the crossing is the SAME size.**
       t_4x4 - t_2x8 = M/256 - 800 = 2*(9-7) * (M/1024 - 200)
   is itself a difference of two factorization-law gaps (coefficient
   2*Delta[(r1-1)(r2-1)] with Delta = 9-7 = 2): below the balance point
   the SQUARE grid has the smaller completion time (its chain 12L beats
   16L; e.g. -288 ns at the 128 KiB grid point), above it the SKEWED grid
   does (its wire 11M/4 beats 3M; +224 ns at the 256 KiB grid point).

**The three-way concurrent point.** At M = 204800 B all THREE identities
evaluate to exactly the same completion time, 12000 ns (ring
15*204800/512 + 6000; 2x8 11*204800/256 + 3200; 4x4 3*204800/64 + 2400):
the total order 4x4 < 2x8 < ring below M* reverses completely (ring <
2x8 < 4x4) above it, a full reversal of the three-identity chain at one
exact size — the atlas's first three-way crossing.

**Rank-class ladder vs [4r-torus.md](4r-torus.md) /
[8r-torus.md](8r-torus.md)** (closed forms, not measurements): the
crossover ladder 51200 -> 102400 -> 204800 B tracks M* = L*B*r exactly
(the same sizes as the ring balance ladder). The delta-coefficient ladder
splits into two branches at this rank class — the skewed family
(r1 = 2, coefficient (r-2)/(2*(r-1))): 1/3 (4r 2x2) -> 3/7 (8r 2x4) ->
7/15 (16r 2x8), walking to 1/2; the square family (coefficient
(sqrt(r)-1)/(sqrt(r)+1)): 1/3 (4r 2x2, simultaneously both) -> 3/5 (16r
4x4) -> 7/9 at 64r. The signed rank-class curves still cross exactly
once each: the 16r 2x8 delta against the 8r 2x4 delta at
M = 1203200 + 25600*sqrt(2241) ≈ 2415084 B (between the 2 MiB and 4 MiB
grid points; other root negative), the 16r 4x4 delta against the 8r 2x4
delta at M = 307200 + 102400*sqrt(11) ≈ 646822 B (between the 256 KiB
and 1 MiB points; other root negative) — below those sizes the rank-16
deltas are the lower curves (more torus-favoring: -7/25 and -9/25 at the
rank-4 crossover 51200, -7/45 and -1/5 at the rank-8 crossover 102400),
above them the higher ones, the same once-crossing structure as 8r-vs-4r.
Latency-chain ladder within rank class 16 so far: crossbar 2L < 4x4 torus
12L < 2x8 torus 16L < ring 30L (the 8r ladder read 2L < 6L < 8L < 14L).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by both torus dimension sizes 2/8 and 4/4, so the divisibility guard
`A-L0T-DIV` never rejects a grid point). Ring baseline ladder:
[16r-ring.md](16r-ring.md) (its rows carry delta exactly 0 by
construction; the sweep grid carries the baseline config so the runner
can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire 2x8 = 11M/4 | wire 4x4 = 3M | 2x8 CCT ns = 11M/256 + 3200 | 4x4 CCT ns = 3M/64 + 2400 | ring CCT ns = 15M/512 + 6000 | delta 2x8 (exact) | delta 2x8 (%) | delta 4x4 (exact) | delta 4x4 (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 11264 | 12288 | 3376 | 2592 | 6120 | -343/765 | -44.8366 | -49/85 | -57.6471 |
| 8192 | 8 KiB | 22528 | 24576 | 3552 | 2784 | 6240 | -28/65 | -43.0769 | -36/65 | -55.3846 |
| 16384 | 16 KiB | 45056 | 49152 | 3904 | 3168 | 6480 | -161/405 | -39.7531 | -23/45 | -51.1111 |
| 65536 | 64 KiB | 180224 | 196608 | 6016 | 5472 | 7920 | -119/495 | -24.0404 | -17/55 | -30.9091 |
| 131072 | 128 KiB | 360448 | 393216 | 8832 | 8544 | 9840 | -21/205 | -10.2439 | -27/205 | -13.1707 |
| 262144 | 256 KiB | 720896 | 786432 | 14464 | 14688 | 13680 | 49/855 | 5.7310 | 7/95 | 7.3684 |
| 1048576 | 1 MiB | 2883584 | 3145728 | 48256 | 51552 | 36720 | 721/2295 | 31.4161 | 103/255 | 40.3922 |
| 2097152 | 2 MiB | 5767168 | 6291456 | 93312 | 100704 | 67440 | 539/1405 | 38.3630 | 693/1405 | 49.3238 |
| 4194304 | 4 MiB | 11534336 | 12582912 | 183424 | 199008 | 128880 | 3409/8055 | 42.3215 | 487/895 | 54.4134 |
| 16777216 | 16 MiB | 46137344 | 50331648 | 724096 | 788832 | 497520 | 14161/31095 | 45.5411 | 2023/3455 | 58.5528 |
| 33554432 | 32 MiB | 92274688 | 100663296 | 1444992 | 1575264 | 989040 | 9499/20605 | 46.1005 | 12213/20605 | 59.2720 |
| 67108864 | 64 MiB | 184549376 | 201326592 | 2886784 | 3148128 | 1972080 | 57169/123255 | 46.3827 | 8167/13695 | 59.6349 |

Both delta columns climb monotonically toward their exact asymptotes
(+7/15 ≈ +46.67% and +3/5 = +60%) — the large-M rows are the
bandwidth-term facts (the tori move 22/15 and 8/5 of the ring's bytes per
rank), the small-M rows are the latency-term facts (their hop chains are
8/15 and 2/5 of the ring's). The 4x4 column is the more extreme at BOTH
ends (-3/5 ↔ +3/5 vs -7/15 ↔ +7/15): the square shape is the most
torus-like identity of the cell in each term's own direction.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; 2x8: dimension 1 has 8
disjoint rings of 2 x 2*(2-1)*M each = 16M, dimension 2 has 2 disjoint
rings of 8 x 2*(8-1)*M each = 28M, so each op totals 44M = 2*(2r - r1 -
r2)*M; 4x4: each dimension has 4 disjoint rings of 4 x 2*3*M each = 24M,
so each op totals 48M; e.g. total wire bytes at M = 4096: 2x8 1081344 =
6 ops x 44 x 4096, 4x4 1179648 = 6 ops x 48 x 4096; the baseline rows
read 737280 = 6 ops x 30 x 4096, digit-for-digit the 16r-ring ladder).
All 36 rows (two tori and baseline) rederived independently from the
closed forms during stage verification — wire, time, delta, and
conservation totals agree exact-string-equal with the runner's
`table.json`, and both delta identities (7/15)·(M-204800)/(M+204800) and
(3/5)·(M-204800)/(M+204800) were checked equal to the runner's deltas at
all 12 sizes, as was the gap law 2*(r1-1)*(r2-1)*(M/1024 - 200).

## Crossover message sizes

**Three exact crossovers, all at ONE off-grid size: M = 204800 B
(200 KiB).** Both delta identities change sign there (2x8: -21/205 at the
128 KiB grid point → +49/855 at 256 KiB; 4x4: -27/205 → +7/95) and the
intra-family gap t_4x4 - t_2x8 = M/256 - 800 does too (-288 ns →
+224 ns) — three pairwise crossovers (ring/2x8, ring/4x4, 2x8/4x4)
coinciding exactly, which is the three-way concurrent point of fact 4
above. 204800 is not a member of the shared ladder (not a power of two;
it lies inside the ladder's x2 interval 2^17 → 2^18), so the grid samples
the crossover without containing it — the page reports the exact size
rather than a bracket alone. By the factorization law every torus
factorization's gap is proportional to (M - L*B*r), so EVERY torus
crossover lands exactly at the ring identity's own balance point M* =
L*B*r = 204800 B — the same size noted on [16r-ring.md](16r-ring.md) and
predicted from the 8r cell's derivation; rank 16 exercises the
prediction on two factorizations at once. At the lower rank classes'
crossover sizes the 16-rank deltas are negative and torus-favoring
(-7/25 and -9/25 at 51200, -7/45 and -1/5 at 102400); at 204800 both are
0 by definition.

## Run provenance

- sweep id: `212317980620cf26a6324d39d07bcd940e96751775424ef0aabe49e87259161a`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_16r_torus_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_16r_torus_v1.yaml`
  (sha256 `ce0aba484d6e4444916a90eb673da788a387acacdf0c4cc0631f59e5cb1f1e30`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp16.yaml`
  (sha256 `1602fd4b10fe9ac9b81de3aa7d6a92830e115547b8fb948e3c46f11a81c0fc99`,
  the same file the 16r-ring and 16r-crossbar cells used)
- topologies: `experiments/topologies/torus2d16_2x8_free_params.yaml`
  (sha256 `3138af999ad1fcfdc1ead15f758d7c5beff343229f63446806a83d2a9f7c55b7`)
  and `experiments/topologies/torus2d16_4x4_free_params.yaml`
  (sha256 `85cff24688d3d35ab4ffd36acf3bd4db1b3fccf5208edfa79ec480d14d42e192`;
  baseline topology `experiments/topologies/ring16_free_params.yaml` sha256
  `f973784db47ebc461da1111eecdcb44accc73c06a06c0daeb86d9e46cab8a119`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `b499f25392026b7332e6663b5a888fa3da8879f959f412562f99b7383a30dcd4`
  / `fb19b2e9a2fecc0cfb8c2de4988a72e1a41bb9ed2d2e67f0314613e77c00f08a`);
  `tests/determinism` 13 passed; full suite 560 passed (two above the
  16r-crossbar stage's 558 — the schema glob's two new torus16 files);
  paper-check PASS.

Catalog: [atlas index](README.md).
