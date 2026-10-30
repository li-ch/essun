# Atlas cell 32r-torus — rank class 32, algorithm family torus

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The torus family factorizes 32 ranks as **1x32, 2x16, or 4x8** (unordered,
plus transposes). The stage sweeps the factorizations; like rank 16 (and
unlike ranks 4 and 8, which had one each), rank 32 has TWO declared,
generatable torus identities — and ONE structural first of its own:

- **1x32 — SKIP (config cannot be generated).** Attempted both through the
  backend loader and through the sweep runner's grid gate (with a real
  topology file present); both reject it with
  `analytical_l0_torus2d: a torus dimension must wrap >= 2 ranks, got 1x32`
  (shape guard, assumption A-L0T-SHAPE). The landed golden
  `tests/golden/test_l0_torus2d_golden.py::test_loader_extracts_exact_fractions_and_rejects_bad_grids`
  asserts the same guard (its bad grid is 1x8 at ranks 8); the rank-32
  strings above were exercised live during this stage. The **32x1
  transpose** is rejected identically by the same guard (`got 32x1`),
  exercised through the loader during the stage. The rejection is also
  arithmetically honest: a degenerate 1x32 grid would evaluate to
  `t_ring(M,1) + t_ring(M,32) = 0 + t_ring(M,32)` — exactly the flat-ring
  identity that already IS this rank class's baseline cell
  ([32r-ring.md](32r-ring.md)) — so 1x32 is not a new identity, and it is
  recorded in the index's Recorded skips, never forced.
- **2x16 — the skewed declared identity** (backend `analytical_l0_torus2d`;
  modeling assumptions A-L0T-SEQ sequential dimensions, A-L0T-UNIF uniform
  links, A-L0T-SHAPE grid shape): `allreduce_torus2d` over a 2x16
  ring-x-ring grid. The **16x2 transpose** loads cleanly and evaluates to
  the IDENTICAL identity (completion time and wire traffic exactly equal
  at every probed size — the module identities are symmetric in
  dim1 x dim2, re-verified through the loader during this stage), so the
  grid carries 2x16 once.
- **4x8 — the closest-to-square declared identity**, the same backend over
  a 4x8 grid (its **8x4 transpose** verified identical through the loader
  during the stage). **32 = 2^5 has an odd exponent, so NO exactly square
  factorization exists: 32 is the FIRST atlas rank class with two declared
  factorizations and no square grid.** The square-family ladder
  (2x2 at rank 4, 4x4 at rank 16) pauses here and revives only at 64 = 8x8;
  4x8 is the most square shape 32 admits, and it is a DISTINCT identity
  from the skew shape — the second consecutive rank class with an
  intra-family torus comparison, now between skew and closest-to-square
  rather than skew and square.

Identities executed (per op, message M, ranks r = 32, exact Fractions;
each dimension runs a full ring AllReduce of the entire M, dimensions
serialized):

    per-dimension kernel       t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L
    2x16 per-rank wire         T(M, 32) = 2*(2 - 1/2 - 1/16) * M = 23M/8
    2x16 completion time       t(M, 32) = t_ring(M,2) + t_ring(M,16) = 23M/512 + 6400 ns   (chain 2*(2+16-2) = 32 hops)
    4x8 per-rank wire          T(M, 32) = 2*(2 - 1/4 - 1/8) * M = 13M/4
    4x8 completion time        t(M, 32) = t_ring(M,4) + t_ring(M,8) = 13M/256 + 4000 ns    (chain 2*(4+8-2) = 20 hops)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 32, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell (ring baseline: T = 31M/16,
t = 31M/1024 + 12400 — [32r-ring.md](32r-ring.md)):

1. **Both declared identities pay more wire than the ring, differently.**
   The 2x16 torus moves 23M/8 per rank = **46/31 of the ring's 31M/16
   (+15/31 at every payload size)**; the 4x8 torus moves 13M/4 = **52/31
   of it (+21/31)**. The closest-to-square grid pays the most wire of the
   cell (26/23 of the skewed grid's bytes) and owns the shortest chain
   (20 hops vs the skewed grid's 32 vs the flat ring's 62): squareness
   trades wire for chain inside the family, exactly as the family trades
   both against the ring (rank-16 read the same fact as +7/15 / +3/5 for
   its 2x8 / 4x4 shapes; the wire-identity ladder of the family climbs
   2M → 5M/2 → 11M/4 → 3M → 23M/8 → **13M/4**, walking toward the
   2*(2 - 0 - 0) = 4M degenerate limit).
2. **Both identities scale the ring's two terms by exact complementary
   factors.** The 2x16 bandwidth term 23M/512 = (46/31)*(the ring's
   31M/1024) with latency 32L = 6400 = (16/31)*(the ring's 62L = 12400);
   the 4x8 bandwidth term 13M/256 = (52/31)*beta with latency 20L = 4000
   = (10/31)*lambda. So each gap collapses to the exact linear form
       t_2x16 - t_ring = (15/31)*(beta - lambda) = 15M/1024 - 6000 ns
       t_4x8  - t_ring = (21/31)*(beta - lambda) = 21M/1024 - 8400 ns
   — the two gaps in exact ratio 15:21 = 5:7 at every payload size
   (rank 16 read 7:9).
3. **The factorization law (from [8r-torus.md](8r-torus.md), confirmed on
   two factorizations at 16r) reproduces both gaps and predicts the whole
   cell.** The law `t_torus - t_ring = 2*(r1-1)*(r2-1) * (M/(B*r) - L)`
   gives coefficients 2*1*15 = 30 and 2*3*7 = 42 (30M/2048 - 6000 and
   42M/2048 - 8400, exactly the gaps above), and the delta identities are
       delta_2x16(M) = (15/31) * (M - 409600)/(M + 409600)
       delta_4x8(M)  = (21/31) * (M - 409600)/(M + 409600)
   with exact envelopes delta(0) = -15/31 and -21/31 (the pure
   latency-term facts 6400/12400 - 1 and 4000/12400 - 1) and delta(inf) =
   +15/31 and +21/31 (the pure bandwidth-term facts 46/31 - 1 and
   52/31 - 1 — at every rank class each shape's envelope magnitude
   equals its extra-wire fraction), and **delta_4x8 = (7/5)*delta_2x16
   exactly at every M**. The law's predicted crossover M* = L*B*r =
   409600 B holds for BOTH factorizations — the stated
   prediction for this cell, confirmed on fresh executions.
4. **The two tori cross each other — and the crossing is the SAME size.**
       t_4x8 - t_2x16 = 3M/512 - 2400 = 2*(21-15) * (M/2048 - 200)
   is itself a difference of two factorization-law gaps (coefficient
   2*Delta[(r1-1)(r2-1)] with Delta = 21-15 = 6, the 16r cell's first
   exercise of this form at Delta = 2): below the balance point the
   CLOSEST-TO-SQUARE grid has the smaller completion time (its chain 20L
   beats 32L; e.g. -864 ns at the 256 KiB grid point), above it the
   SKEWED grid does (its wire 23M/8 beats 13M/4; +3744 ns at the 1 MiB
   grid point).

**The three-way concurrent point.** At M = 409600 B all THREE identities
evaluate to exactly the same completion time, 24800 ns (ring
31*409600/1024 + 12400; 2x16 23*409600/512 + 6400; 4x8 13*409600/256 +
4000): the total order 4x8 < 2x16 < ring below M* reverses completely
(ring < 2x16 < 4x8) above it, a complete order inversion of the three-identity chain
at one exact size — the atlas's SECOND three-way crossing (after
[16r-torus.md](16r-torus.md)), now between skew and closest-to-square
rather than skew and square.

**Rank-class ladder vs [4r-torus.md](4r-torus.md) /
[8r-torus.md](8r-torus.md) / [16r-torus.md](16r-torus.md)** (closed forms,
not measurements): the crossover ladder 51200 -> 102400 -> 204800 ->
409600 B tracks M* = L*B*r exactly (the same sizes as the ring balance
ladder; fourth consecutive exact-2x rung, predicted from the landed 16r
page and confirmed here). The delta-coefficient ladder's skew branch
(r1 = 2, coefficient (r-2)/(2*(r-1))): 1/3 (4r) -> 3/7 (8r) -> 7/15 (16r)
-> **15/31 (32r)**, walking to 1/2 — the fourth consecutive data point of
that branch, exactly as predicted from the landed 16r page. The square
branch (coefficient (sqrt(r)-1)/(sqrt(r)+1), existing only at perfect
squares: 1/3 -> 3/5) PAUSES at 32 — no square grid exists (odd exponent)
— and revives at 64r with 7/9 (8x8). The **closest-to-square branch**
(factorization 2^k x 2^(k+1) at r = 2^(2k+1)): 3/7 (8r 2x4, which is
simultaneously that class's skew shape) -> **21/31 (32r 4x8)** -> 105/127
(128r 8x16). The signed rank-class curves still cross exactly once each:
the 32r 2x16 delta against the 16r 2x8 delta at
M = 25600*(221 + sqrt(48969)) ≈ 11322609 B (between the 8 MiB and 16 MiB
grid points; other root negative), the 32r 4x8 delta against the 16r 2x8
delta at M = 51200*(152 + sqrt(29376))/14 ≈ 1182699 B (between the 1 MiB
and 2 MiB points; other root negative), and against the 16r 4x4 delta at
M = 25600*(66 + sqrt(4484)) ≈ 3403845 B (between the 2 MiB and 4 MiB
points; other root negative) — below those sizes the rank-32 deltas are
the lower curves (more torus-favoring: -5/31 and -7/31 at the rank-16
crossover 204800, -9/31 and -63/155 at the rank-8 crossover 102400,
-35/93 and -49/93 at the rank-4 crossover 51200), above them the higher
ones, the same once-crossing structure as 8r-vs-4r and 16r-vs-8r.
Latency-chain ladder within rank class 32 so far: crossbar 2L < 4x8 torus
20L < 2x16 torus 32L < ring 62L (the 16r ladder read 2L < 12L < 16L <
30L).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by both torus dimension pairs 2/16 and 4/8, so the divisibility guard
`A-L0T-DIV` never rejects a grid point). Ring baseline ladder:
[32r-ring.md](32r-ring.md) (its rows carry delta exactly 0 by
construction; the sweep grid carries the baseline config so the runner
can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire 2x16 = 23M/8 | wire 4x8 = 13M/4 | 2x16 CCT ns = 23M/512 + 6400 | 4x8 CCT ns = 13M/256 + 4000 | ring CCT ns = 31M/1024 + 12400 | delta 2x16 (exact) | delta 2x16 (%) | delta 4x8 (exact) | delta 4x8 (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 11776 | 13312 | 6584 | 4208 | 12524 | -1485/3131 | -47.4289 | -2079/3131 | -66.4005 |
| 8192 | 8 KiB | 23552 | 26624 | 6768 | 4416 | 12648 | -245/527 | -46.4896 | -343/527 | -65.0854 |
| 16384 | 16 KiB | 47104 | 53248 | 7136 | 4832 | 12896 | -180/403 | -44.6650 | -252/403 | -62.5310 |
| 65536 | 64 KiB | 188416 | 212992 | 9344 | 7328 | 14384 | -315/899 | -35.0389 | -441/899 | -49.0545 |
| 131072 | 128 KiB | 376832 | 425984 | 12288 | 10656 | 16368 | -85/341 | -24.9267 | -119/341 | -34.8974 |
| 262144 | 256 KiB | 753664 | 851968 | 18176 | 17312 | 20336 | -135/1271 | -10.6216 | -189/1271 | -14.8702 |
| 1048576 | 1 MiB | 3014656 | 3407872 | 53504 | 57248 | 44144 | 585/2759 | 21.2033 | 819/2759 | 29.6847 |
| 2097152 | 2 MiB | 6029312 | 6815744 | 100608 | 110496 | 75888 | 515/1581 | 32.5743 | 721/1581 | 45.6040 |
| 4194304 | 4 MiB | 12058624 | 13631488 | 194816 | 216992 | 139376 | 3465/8711 | 39.7773 | 4851/8711 | 55.6882 |
| 16777216 | 16 MiB | 48234496 | 54525952 | 760064 | 855968 | 520304 | 14985/32519 | 46.0808 | 20979/32519 | 64.5131 |
| 33554432 | 32 MiB | 96468992 | 109051904 | 1513728 | 1707936 | 1028208 | 10115/21421 | 47.2200 | 14161/21421 | 66.1080 |
| 67108864 | 64 MiB | 192937984 | 218103808 | 3021056 | 3411872 | 2044016 | 61065/127751 | 47.8000 | 85491/127751 | 66.9200 |

Both delta columns climb monotonically toward their exact asymptotes
(+15/31 ≈ +48.39% and +21/31 ≈ +67.74%) — the large-M rows are the
bandwidth-term facts (the tori move 46/31 and 52/31 of the ring's bytes
per rank), the small-M rows are the latency-term facts (their hop chains
are 16/31 and 10/31 of the ring's). The 4x8 column is the more extreme at
BOTH ends (-21/31 ↔ +21/31 vs -15/31 ↔ +15/31): the closest-to-square
shape is the most torus-like identity of the cell in each term's own
direction, as the square grid was at rank 16.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; 2x16: dimension 1 has 16
disjoint rings of 2 x 2*(2-1)*M each = 32M, dimension 2 has 2 disjoint
rings of 16 x 2*(16-1)*M each = 60M, so each op totals 92M = 2*(2r - r1 -
r2)*M; 4x8: dimension 1 has 8 disjoint rings of 4 x 2*3*M each = 48M,
dimension 2 has 4 disjoint rings of 8 x 2*7*M each = 56M, so each op
totals 104M; e.g. total wire bytes at M = 4096: 2x16 2260992 = 6 ops x 92
x 4096, 4x8 2555904 = 6 ops x 104 x 4096; the baseline rows read 1523712
= 6 ops x 62 x 4096, digit-for-digit the 32r-ring ladder, cross-checked
12/12 against the landed 32r-ring sweep table). All 36 rows (two tori and
baseline) rederived independently from the closed forms during stage
verification — wire, time, delta, and conservation totals agree
exact-string-equal with the runner's `table.json`, and both delta
identities (15/31)·(M-409600)/(M+409600) and (21/31)·(M-409600)/(M+409600)
were checked equal to the runner's deltas at all 12 sizes, as were the gap
law 2*(r1-1)*(r2-1)*(M/2048 - 200) for both shapes, the exact delta ratio
delta_4x8 = (7/5)·delta_2x16, and the intra-family gap 12·(M/2048 - 200).

## Crossover message sizes

**Three exact crossovers, all at ONE off-grid size: M = 409600 B
(400 KiB).** Both delta identities change sign there (2x16: -135/1271 at
the 256 KiB grid point → +585/2759 at 1 MiB; 4x8: -189/1271 → +819/2759)
and the intra-family gap t_4x8 - t_2x16 = 3M/512 - 2400 does too (-864 ns
→ +3744 ns) — three pairwise crossovers (ring/2x16, ring/4x8, 2x16/4x8)
coinciding exactly, which is the three-way concurrent point of fact 4
above. 409600 is not a member of the shared ladder (not a power of two;
it lies inside the ladder's x4 interval 2^18 → 2^20), so the grid samples
the crossover without containing it — the page reports the exact size
rather than a bracket alone. By the factorization law every torus
factorization's gap is proportional to (M - L*B*r), so EVERY torus
crossover lands exactly at the ring identity's own balance point M* =
L*B*r = 409600 B — the same size noted on [32r-ring.md](32r-ring.md) and
predicted from the 8r/16r cells' derivations; rank 32 exercises the
prediction on two factorizations at once, the second consecutive rank
class to do so. At the lower rank classes' crossover sizes the 32-rank
deltas are negative and torus-favoring (-5/31 and -7/31 at 204800, -9/31
and -63/155 at 102400, -35/93 and -49/93 at 51200); at 409600 both are 0
by definition.

## Run provenance

- sweep id: `8cbac9d215d29210a2400f787f1b54902aef39d04564eccd49c18b47a4f4277d`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_32r_torus_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_32r_torus_v1.yaml`
  (sha256 `0c111a929e4423f6b5b03da82307f34f9b748f31bd0f7633f9c290444a362630`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp32.yaml`
  (sha256 `170833ec1347c016120a1f9dde5e6b771f0ac643c1f2626b0ebb905653083ea8`,
  the same file the 32r-ring and 32r-crossbar cells used)
- topologies: `experiments/topologies/torus2d32_2x16_free_params.yaml`
  (sha256 `5d957cb5e175ae1e36777abb13b878d69819ad1b0408d9c35ac24329852c135e`)
  and `experiments/topologies/torus2d32_4x8_free_params.yaml`
  (sha256 `e13c95de19850c185aaf6c2011b88d483caa86e5889ad5001286f78f7f639c96`;
  baseline topology `experiments/topologies/ring32_free_params.yaml` sha256
  `90e694ecb6a71bc9ac4b050c8c54de506f76346b242e19b7c63712b758337ac2`,
  the same file the 32r-ring/32r-crossbar cells used)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `de8762082ee67cfae3f2b87fd9aab776b804708e63e8df36e03f4e77c6ea9feb`
  / `43c98fb1a64281bec7eebc083304eed8a042cfda7db1de564c0ef0b241fdfce3`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 580 passed
  (two above the 32r-crossbar stage's 578 — the schema glob's two new
  torus32 files); paper-check PASS.

Catalog: [atlas index](README.md).
