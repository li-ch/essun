# Atlas cell 32r-crossbar — rank class 32, algorithm family crossbar

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The crossbar family at 32 ranks has exactly ONE declared L0 identity:
`allreduce_crossbar` over a fully-connected single-port fabric (backend
`analytical_l0_crossbar`). The single-port injection model is a modeling
assumption (A-L0X-PORT); a multi-port fabric — every pair link at full B —
is a different identity, explicitly unsupported by the backend, and does
not appear here. Free parameters are shared with every other atlas cell
(below), so the only degrees of freedom are the payload grid. This is the
rank-32 mirror of [4r-crossbar.md](4r-crossbar.md),
[8r-crossbar.md](8r-crossbar.md) and [16r-crossbar.md](16r-crossbar.md);
every structure there recurs here with deeper constants.

Identity executed (per op, message M, ranks r = 32, exact Fractions;
reduce-scatter and allgather phases serialized behind one injection port):

    per-rank wire traffic  T(M, 32) = 2*(32-1)/32 * M = 31M/16
    completion time        t(M, 32) = 2*(32-1)/32 * M / B + 2L = 31M/1024 + 400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 32, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Two arithmetic facts drive the whole cell, the rank-32 mirrors of the 4-,
8- and 16-rank cells':

1. **The traffic identity equals the ring's.** T(M, 32) = 31M/16 is the same
   per-rank wire-byte identity as the 32-rank ring (page
   [32r-ring.md](32r-ring.md)) — at r = 32 both factorizations ship 2*(r-1)/r
   bytes per rank, so the wire column below is digit-for-digit the 32r-ring
   ladder's. Under this L0 model the crossbar buys no traffic reduction at
   32 ranks either.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (31M/1024); the completion times differ only in the constant —
   2L = 400 ns for the crossbar (one L per phase, chunks pipelined behind
   the injection port) versus 2*(r-1)*L = 62L = 12400 ns for the ring
   (sixty-two hop latencies around the ring). Hence the exact delta identity

       delta(M) = (t_xb - t_ring) / t_ring = -12000 / (31M/1024 + 12400)

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities).

Rank-class ladder vs [16r-crossbar.md](16r-crossbar.md) (closed forms, not
measurements): the constant gap 2*(r-2)*L grows from 5600 ns to 12000 ns, so
the small-M delta envelope deepens from -14/15 to **-30/31** — in general
-(r-2)/(r-1), the envelope law's fourth consecutive data point
(-2/3 → -6/7 → -14/15 → -30/31, **exactly as predicted** from the landed
16r page and confirmed on this fresh execution) — and at every grid size
the 32-rank delta is more negative than the 16-rank delta (exact ratio law
delta_32/delta_16 = (30/7)*(15M + 3072000)/(31M + 12697600), climbing from
its 225/217 ≈ 1.037 floor at M = 0 through 22950/21917 ≈ 1.047 at the
4 KiB point toward its 450/217 ≈ 2.074 large-M limit): the ring's latency
chain grows with r while the crossbar's stays 2L. At the ring identity's
own balance point M* = L*B*r = 409600 B the delta is exactly -15/31
(general: -(r-2)/(2(r-1)); at ranks 4, 8 and 16 the same fact read -1/3,
-3/7 and -7/15). The crossbar identity's own balance point (bandwidth term
equals latency term) sits at 409600/31 ≈ 13212.90 B — exactly (r-1) = 31
times below the ring's, between the 8 KiB and 16 KiB grid points here.

Forward prediction recorded for the next cell (an arithmetic fact of the
landed laws, to be tested by the 32r-doubling stage, not by this page): the
crossbar/doubling ratio law confirmed on the landed 16r tables — the
doubling delta is exactly (r-1-log2 r)/(r-2) of this cell's delta at every
size (verified 11/14 at rank 16 against the landed
[16r-crossbar.md](16r-crossbar.md) sweep table) — puts the r = 32 rung at
**26/30 = 13/15**, because log2 32 = 5. The forward rungs "9/10 at 32r" and
"59/62 at 64r" written into the 8r- and 16r-doubling index rows (and any
26/29-style figure) freeze log2 r at 4 and disagree with the law's own
closed form; the correct ladder is 1/2 → 2/3 → 11/14 → **13/15** → 57/62 →
1. Recorded honestly here without editing the landed pages.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell). Ring baseline ladder: [32r-ring.md](32r-ring.md) (its rows carry
delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 31M/16 (exact) | crossbar CCT ns = 31M/1024 + 400 (exact) | ring CCT ns = 31M/1024 + 12400 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 7936 | 524 | 12524 | -3000/3131 | -95.8160 |
| 8192 | 8 KiB | 15872 | 648 | 12648 | -500/527 | -94.8767 |
| 16384 | 16 KiB | 31744 | 896 | 12896 | -375/403 | -93.0521 |
| 65536 | 64 KiB | 126976 | 2384 | 14384 | -750/899 | -83.4260 |
| 131072 | 128 KiB | 253952 | 4368 | 16368 | -250/341 | -73.3138 |
| 262144 | 256 KiB | 507904 | 8336 | 20336 | -750/1271 | -59.0087 |
| 1048576 | 1 MiB | 2031616 | 32144 | 44144 | -750/2759 | -27.1838 |
| 2097152 | 2 MiB | 4063232 | 63888 | 75888 | -250/1581 | -15.8128 |
| 4194304 | 4 MiB | 8126464 | 127376 | 139376 | -750/8711 | -8.6098 |
| 16777216 | 16 MiB | 32505856 | 508304 | 520304 | -750/32519 | -2.3063 |
| 33554432 | 32 MiB | 65011712 | 1016208 | 1028208 | -250/21421 | -1.1671 |
| 67108864 | 64 MiB | 130023424 | 2032016 | 2044016 | -750/127751 | -0.5871 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; total wire bytes at
M = 4096: 1523712 = 6 ops x 2*(32-1)*4096 — the same conservation identity
and the same total as the 32-rank ring, consistent with the equal traffic
identity). All 12 rows rederived independently from the closed forms
during stage verification — table, delta identity, and identities agree
exactly (exact-string equality on every wire, time, delta, and
conservation-total field; the wire column and the ring CCT rows
additionally verified digit-for-digit against the landed 32r-ring sweep
table). An arithmetic aside of the reduction: 16 divides both -12000 and
31M/1024 + 12400 at every grid size from 16 KiB up (and never below), so
nine of those ten reduced deltas read exactly -750/d (six of them: d =
899, 1271, 2759, 8711, 32519, 127751) or -250/d (the three sizes one x2
step after a x4 step of the grid — 128 KiB, 2 MiB, 32 MiB — a further
exact division by 3: d = 341, 1581, 21421); the 16 KiB point reduces once
more by 2 to -375/403.

## Crossover message sizes

**None — for a structural reason, not a sampling one.** Within this cell
there is exactly one declared identity (single-port crossbar), and against
the ring baseline the two completion-time identities have the SAME
bandwidth term (31M/1024) and differ only by a constant (400 ns vs
12400 ns), so the two curves are translates of each other in M: the
crossbar identity is faster at every finite M, the delta
-12000/(31M/1024 + 12400) never changes sign, and no payload size exists
where the orderings swap. Recorded honestly, exactly as in the 4-, 8- and
16-rank cells; the crossover question stays non-trivial only in cells
whose bandwidth coefficients differ (e.g. the torus factorizations).
(Arithmetic fact of the crossbar identity, not a crossover: its bandwidth
term 31M/1024 equals its latency term 400 at M = 409600/31 ≈ 13212.90 B,
between the 8 KiB and 16 KiB grid points — exactly (r-1) = 31 times below
the ring's own balance point 409600 B, which sits between the 256 KiB and
1 MiB points.)

## Run provenance

- sweep id: `ee874a38124b150f617d7e91aa413c142fcd5d6d87b1ac3de0df36336fca6317`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_32r_crossbar_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_32r_crossbar_v1.yaml`
  (sha256 `1a95fc4e3c1c5d2939839ee2e20258acc457c78f918cf6c42122057b89d85c24`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp32.yaml`
  (sha256 `170833ec1347c016120a1f9dde5e6b771f0ac643c1f2626b0ebb905653083ea8`,
  the same file the 32r-ring cell used)
- topology: `experiments/topologies/crossbar32_free_params.yaml`
  (sha256 `86f79b28a7b040f5270612324da7fa2d30191956aa45ed984ff755279304366f`,
  new in this stage — the rank-32 mirror of
  crossbar4/crossbar8/crossbar16_free_params, same B and L; baseline
  topology `experiments/topologies/ring32_free_params.yaml`
  sha256 `90e694ecb6a71bc9ac4b050c8c54de506f76346b242e19b7c63712b758337ac2`,
  the 32r-ring cell's own file)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `b71624777c3bf099ba582527667eab9549303ea5c9982330c97a310e881e63f2`
  / `c03aceb2d8e366f13758474437b672c0a23487852ced3e609f1873504360793a`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 578 passed
  (one above the 32r-ring baseline 577: the schema test's glob picks up the
  new topology file); paper-check PASS.

Catalog: [atlas index](README.md).
