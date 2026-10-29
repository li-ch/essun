# Atlas cell 16r-crossbar — rank class 16, algorithm family crossbar

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The crossbar family at 16 ranks has exactly ONE declared L0 identity:
`allreduce_crossbar` over a fully-connected single-port fabric (backend
`analytical_l0_crossbar`). The single-port injection model is a modeling
assumption (A-L0X-PORT); a multi-port fabric — every pair link at full B —
is a different identity, explicitly unsupported by the backend, and does
not appear here. Free parameters are shared with every other atlas cell
(below), so the only degrees of freedom are the payload grid. This is the
rank-16 mirror of [4r-crossbar.md](4r-crossbar.md) and
[8r-crossbar.md](8r-crossbar.md); every structure there recurs here with
deeper constants.

Identity executed (per op, message M, ranks r = 16, exact Fractions;
reduce-scatter and allgather phases serialized behind one injection port):

    per-rank wire traffic  T(M, 16) = 2*(16-1)/16 * M = 15M/8
    completion time        t(M, 16) = 2*(16-1)/16 * M / B + 2L = 15M/512 + 400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 16, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Two arithmetic facts drive the whole cell, the rank-16 mirrors of the 4-
and 8-rank cells':

1. **The traffic identity equals the ring's.** T(M, 16) = 15M/8 is the same
   per-rank wire-byte identity as the 16-rank ring (page
   [16r-ring.md](16r-ring.md)) — at r = 16 both factorizations ship 2*(r-1)/r
   bytes per rank, so the wire column below is digit-for-digit the 16r-ring
   ladder's. Under this L0 model the crossbar buys no traffic reduction at
   16 ranks either.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (15M/512); the completion times differ only in the constant —
   2L = 400 ns for the crossbar (one L per phase, chunks pipelined behind
   the injection port) versus 2*(r-1)*L = 30L = 6000 ns for the ring
   (thirty hop latencies around the ring). Hence the exact delta identity

       delta(M) = (t_xb - t_ring) / t_ring = -5600 / (15M/512 + 6000)

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities).

Rank-class ladder vs [8r-crossbar.md](8r-crossbar.md) (closed forms, not
measurements): the constant gap 2*(r-2)*L grows from 2400 ns to 5600 ns, so
the small-M delta envelope deepens from -6/7 to **-14/15** — in general
-(r-2)/(r-1), the envelope law's third consecutive data point
(-2/3 → -6/7 → -14/15, as predicted from [8r-crossbar.md](8r-crossbar.md))
— and at every grid size the 16-rank delta is more
negative than the 8-rank delta (ratio climbing 2548/2295 ≈ 1.110 toward
its 98/45 ≈ 2.178 large-M limit, above the 49/45 ≈ 1.109 floor at every
size): the ring's latency chain grows with r while the crossbar's stays
2L. At the ring identity's own balance point M* = L*B*r = 204800 B the
delta is exactly -7/15 (general: -(r-2)/(2(r-1)); at ranks 4 and 8 the
same fact read -1/3 and -3/7).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell). Ring baseline ladder: [16r-ring.md](16r-ring.md) (its rows carry
delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 15M/8 (exact) | crossbar CCT ns = 15M/512 + 400 (exact) | ring CCT ns = 15M/512 + 6000 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 7680 | 520 | 6120 | -140/153 | -91.5033 |
| 8192 | 8 KiB | 15360 | 640 | 6240 | -35/39 | -89.7436 |
| 16384 | 16 KiB | 30720 | 880 | 6480 | -70/81 | -86.4198 |
| 65536 | 64 KiB | 122880 | 2320 | 7920 | -70/99 | -70.7071 |
| 131072 | 128 KiB | 245760 | 4240 | 9840 | -70/123 | -56.9106 |
| 262144 | 256 KiB | 491520 | 8080 | 13680 | -70/171 | -40.9357 |
| 1048576 | 1 MiB | 1966080 | 31120 | 36720 | -70/459 | -15.2505 |
| 2097152 | 2 MiB | 3932160 | 61840 | 67440 | -70/843 | -8.3037 |
| 4194304 | 4 MiB | 7864320 | 123280 | 128880 | -70/1611 | -4.3451 |
| 16777216 | 16 MiB | 31457280 | 491920 | 497520 | -70/6219 | -1.1256 |
| 33554432 | 32 MiB | 62914560 | 983440 | 989040 | -70/12363 | -0.5662 |
| 67108864 | 64 MiB | 125829120 | 1966480 | 1972080 | -70/24651 | -0.2840 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; total wire bytes at
M = 4096: 737280 = 6 ops x 2*(16-1)*4096 — the same conservation identity
and the same total as the 16-rank ring, consistent with the equal traffic
identity). All 12 rows rederived independently from the closed forms
during stage verification — table, delta identity, and identities agree
exactly (exact-string equality on every wire, time, delta, and
conservation-total field; the wire column additionally verified
digit-for-digit against the landed 16r-ring sweep table, and the ring CCT
rows against the same). An arithmetic aside of the reduction: because 80
divides both -5600 and 15M/512 + 6000 at every grid size from 16 KiB up
(and never below), the reduced delta reads exactly -70/d for ten
consecutive grid points (d = 81, 99, 123, 171, 459, 843, 1611, 6219,
12363, 24651).

## Crossover message sizes

**None — for a structural reason, not a sampling one.** Within this cell
there is exactly one declared identity (single-port crossbar), and against
the ring baseline the two completion-time identities have the SAME
bandwidth term (15M/512) and differ only by a constant (400 ns vs 6000 ns),
so the two curves are translates of each other in M: the crossbar identity
is faster at every finite M, the delta -5600/(15M/512 + 6000) never changes
sign, and no payload size exists where the orderings swap. Recorded
honestly, exactly as in the 4- and 8-rank cells; the crossover question
stays non-trivial only in cells whose bandwidth coefficients differ (e.g.
the 16-rank torus factorizations). (Arithmetic fact of the crossbar
identity, not a crossover: its bandwidth term 15M/512 equals its latency
term 400 at M = 204800/15 ≈ 13653.33 B, between the 8 KiB and 16 KiB grid
points — exactly (r-1) = 15 times below the ring's own balance point
204800 B, which sits between the 128 KiB and 256 KiB points.)

## Run provenance

- sweep id: `219831ec8ccf65e45204528f8f0d188f24fb8fa996a954e893f3cc868c4a4397`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_16r_crossbar_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_16r_crossbar_v1.yaml`
  (sha256 `87bce28047c9987e6571012a379bd87b164305a3872e7569b595038696c5e04e`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp16.yaml`
  (sha256 `1602fd4b10fe9ac9b81de3aa7d6a92830e115547b8fb948e3c46f11a81c0fc99`,
  the same file the 16r-ring cell used)
- topology: `experiments/topologies/crossbar16_free_params.yaml`
  (sha256 `deea55e4be9fcf854cafd623d4ffc7044a64974f38df3114356ded85a34d8e74`,
  new in this stage — the rank-16 mirror of crossbar4/crossbar8_free_params,
  same B and L; baseline topology `experiments/topologies/ring16_free_params.yaml`
  sha256 `f973784db47ebc461da1111eecdcb44accc73c06a06c0daeb86d9e46cab8a119`,
  the 16r-ring cell's own file)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `065cca46402df646dfc594c4b73a1d3f7261a9885f00597cce04a2c87c60a7b2`
  / `ba2af8fb80458cd0ca0dce9e694cd78830ecd62c9b73f1aa7ac9e589dc6ceccd`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 558 passed
  (one above the 16r-ring baseline 557: the schema test's glob picks up the
  new topology file); paper-check PASS.

Catalog: [atlas index](README.md).
