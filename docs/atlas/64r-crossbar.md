# Atlas cell 64r-crossbar — rank class 64, algorithm family crossbar

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The crossbar family at 64 ranks has exactly ONE declared L0 identity:
`allreduce_crossbar` over a fully-connected single-port fabric (backend
`analytical_l0_crossbar`). The single-port injection model is a modeling
assumption (A-L0X-PORT); a multi-port fabric — every pair link at full B —
is a different identity, explicitly unsupported by the backend, and does
not appear here. Free parameters are shared with every other atlas cell
(below), so the only degrees of freedom are the payload grid. This is the
rank-64 mirror of [4r-crossbar.md](4r-crossbar.md),
[8r-crossbar.md](8r-crossbar.md), [16r-crossbar.md](16r-crossbar.md) and
[32r-crossbar.md](32r-crossbar.md); every structure there recurs here with
deeper constants.

Identity executed (per op, message M, ranks r = 64, exact Fractions;
reduce-scatter and allgather phases serialized behind one injection port):

    per-rank wire traffic  T(M, 64) = 2*(64-1)/64 * M = 63M/32
    completion time        t(M, 64) = 2*(64-1)/64 * M / B + 2L = 63M/2048 + 400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 64, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Two arithmetic facts drive the whole cell, the rank-64 mirrors of the 4-,
8-, 16- and 32-rank cells':

1. **The traffic identity equals the ring's.** T(M, 64) = 63M/32 is the same
   per-rank wire-byte identity as the 64-rank ring (page
   [64r-ring.md](64r-ring.md)) — at r = 64 both factorizations ship 2*(r-1)/r
   bytes per rank, so the wire column below is digit-for-digit the 64r-ring
   ladder's (verified exact-string against the landed 64r-ring sweep table).
   Under this L0 model the crossbar buys no traffic reduction at 64 ranks
   either.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (63M/2048); the completion times differ only in the constant —
   2L = 400 ns for the crossbar (one L per phase, chunks pipelined behind
   the injection port) versus 2*(r-1)*L = 126L = 25200 ns for the ring
   (one hundred twenty-six hop latencies around the ring). Hence the exact
   delta identity

       delta(M) = (t_xb - t_ring) / t_ring = -24800 / (63M/2048 + 25200)

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities).

Rank-class ladder vs [32r-crossbar.md](32r-crossbar.md) (closed forms, not
measurements): the constant gap 2*(r-2)*L grows from 12000 ns to 24800 ns
(ladder 800 → 2400 → 5600 → 12000 → 24800 ns), so the small-M delta
envelope deepens from -30/31 to **-62/63** — in general -(r-2)/(r-1),
the envelope law's fifth consecutive data point
(-2/3 → -6/7 → -14/15 → -30/31 → -62/63, **exactly as predicted** from the
landed 32r page and confirmed on this fresh execution) — and at every grid
size the 64-rank delta is more negative than the 32-rank delta (exact ratio
law delta_64/delta_32 = (62/15)*(31M + 12697600)/(63M + 51609600), climbing
from its 961/945 ≈ 1.0169 floor at M = 0 through 194122/189945 ≈ 1.0220 at
the 4 KiB point toward its 1922/945 ≈ 2.0339 large-M limit): the ring's
latency chain grows with r while the crossbar's stays 2L. At the ring
identity's own balance point M* = L*B*r = 819200 B the delta is exactly
**-31/63** (general: -(r-2)/(2(r-1)); at ranks 4, 8, 16 and 32 the same fact
read -1/3, -3/7, -7/15 and -15/31). The crossbar identity's own balance
point (bandwidth term equals latency term) sits at 819200/63 ≈ 13003.17 B —
exactly (r-1) = 63 times below the ring's, between the 8 KiB and 16 KiB
grid points here.

Forward prediction recorded for the next cell (an arithmetic fact of the
landed laws, to be tested by the 64r-doubling stage, not by this page): the
crossbar/doubling ratio law confirmed on the landed 16r, 32r tables — the
doubling delta is exactly (r-1-log2 r)/(r-2) of this cell's delta at every
size — puts the r = 64 rung at **57/62**, because log2 64 = 6; the 32r
-doubling page already corrected the frozen-log2 "59/62" slip into the
ladder 1/2 → 2/3 → 11/14 → 13/15 → 57/62 → 1, and the next stage tests the
57/62 rung on fresh execution.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell). Ring baseline ladder: [64r-ring.md](64r-ring.md) (its rows carry
delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 63M/32 (exact) | crossbar CCT ns = 63M/2048 + 400 (exact) | ring CCT ns = 63M/2048 + 25200 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 8064 | 526 | 25326 | -12400/12663 | -97.9231 |
| 8192 | 8 KiB | 16128 | 652 | 25452 | -6200/6363 | -97.4383 |
| 16384 | 16 KiB | 32256 | 904 | 25704 | -3100/3213 | -96.4830 |
| 65536 | 64 KiB | 129024 | 2416 | 27216 | -1550/1701 | -91.1229 |
| 131072 | 128 KiB | 258048 | 4432 | 29232 | -1550/1827 | -84.8385 |
| 262144 | 256 KiB | 516096 | 8464 | 33264 | -1550/2079 | -74.5551 |
| 1048576 | 1 MiB | 2064384 | 32656 | 57456 | -1550/3591 | -43.1635 |
| 2097152 | 2 MiB | 4128768 | 64912 | 89712 | -1550/5607 | -27.6440 |
| 4194304 | 4 MiB | 8257536 | 129424 | 154224 | -1550/9639 | -16.0805 |
| 16777216 | 16 MiB | 33030144 | 516496 | 541296 | -1550/33831 | -4.5816 |
| 33554432 | 32 MiB | 66060288 | 1032592 | 1057392 | -1550/66087 | -2.3454 |
| 67108864 | 64 MiB | 132120576 | 2064784 | 2089584 | -1550/130599 | -1.1868 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; total wire bytes at
M = 4096: 3096576 = 6 ops x 2*(64-1)*4096 — the same conservation identity
and the same total as the 64-rank ring, consistent with the equal traffic
identity). All 12 rows rederived independently from the closed forms
during stage verification — table, delta identity, and identities agree
exactly (exact-string equality on every wire, time, delta, and
conservation-total field; the wire column and the ring CCT rows
additionally verified digit-for-digit against the landed 64r-ring sweep
table). An arithmetic aside of the reduction: the power-of-two common
factor of -24800 and the denominator 63M/2048 + 25200 steps 2, 4, 8 at the
4/8/16 KiB points and locks at 16 from the 64 KiB point up (the jump skips
a 32-value because the shared grid has no 32 KiB point), so nine of the
twelve reduced deltas read exactly -1550/d (d = 1701, 1827, 2079, 3591,
5607, 9639, 33831, 66087, 130599) with no further reduction anywhere: the
unreduced denominator is divisible by 9 at every grid size (63 ≡ 0 and
25200 = 9*2800) but no numerator (12400, 6200, 3100, 1550 — none carries a
factor 3) can cancel it — so the 32r cell's "-250/d at the three
x2-after-x4 sizes" pattern, driven by the factor 3 its numerator 750
carried, dies at rank 64; what carries is the shared unreduced
denominator, as at every rank class.

## Crossover message sizes

**None — for a structural reason, not a sampling one.** Within this cell
there is exactly one declared identity (single-port crossbar), and against
the ring baseline the two completion-time identities have the SAME
bandwidth term (63M/2048) and differ only by a constant (400 ns vs
25200 ns), so the two curves are translates of each other in M: the
crossbar identity is faster at every finite M, the delta
-24800/(63M/2048 + 25200) never changes sign, and no payload size exists
where the orderings swap. Recorded honestly, exactly as in the 4-, 8-,
16- and 32-rank cells; the crossover question stays non-trivial only in
cells whose bandwidth coefficients differ (e.g. the torus factorizations —
at rank 64 the 8x8 square grid revives on the next pages).
(Arithmetic fact of the crossbar identity, not a crossover: its bandwidth
term 63M/2048 equals its latency term 400 at M = 819200/63 ≈ 13003.17 B,
between the 8 KiB and 16 KiB grid points — exactly (r-1) = 63 times below
the ring's own balance point 819200 B, which sits between the 256 KiB and
1 MiB points.)

## Run provenance

- sweep id: `602d4a40763e376afdfd9a12f77f0c2d64d857339dcde7eca4b8137676bea2c1`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_64r_crossbar_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_64r_crossbar_v1.yaml`
  (sha256 `5d2b96588cc6cfe9274f08bf8ed5cac2008a714b3efbe49e4176c2cfcbe2a89c`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp64.yaml`
  (sha256 `e3930d1e8a2c651e893882b0085e3222c932dfae6e83ffd32e8838a667c05898`,
  the same file the 64r-ring cell used)
- topology: `experiments/topologies/crossbar64_free_params.yaml`
  (sha256 `b47f44d3ef0a81d08184186b12944735d5f1b8f17c84d9b98a7fb828ca424f42`,
  new in this stage — the rank-64 mirror of
  crossbar4/crossbar8/crossbar16/crossbar32_free_params, same B and L;
  baseline topology `experiments/topologies/ring64_free_params.yaml`
  sha256 `28b187beb2220eebd3d05ab29e969d49badd517ffdc764b5627607211c34f42b`,
  the 64r-ring cell's own file)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `d58b57e5960f9309e1bacf96f9db6e82302471b5ba34d297f6c897bff3751834`
  / `8e8a300ab421c9aac80b52ad3d5045baa8c7b528b5e96dfd122772cdf5909078`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 640 passed
  (one above the 64r-ring baseline 639: the schema test's glob picks up the
  new topology file); paper-check PASS.

Catalog: [atlas index](README.md).
