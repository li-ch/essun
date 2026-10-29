# Atlas cell 8r-crossbar — rank class 8, algorithm family crossbar

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The crossbar family at 8 ranks has exactly ONE declared L0 identity:
`allreduce_crossbar` over a fully-connected single-port fabric (backend
`analytical_l0_crossbar`). The single-port injection model is a modeling
assumption (A-L0X-PORT); a multi-port fabric — every pair link at full B —
is a different identity, explicitly unsupported by the backend, and does
not appear here. Free parameters are shared with every other atlas cell
(below), so the only degrees of freedom are the payload grid. This is the
rank-8 mirror of [4r-crossbar.md](4r-crossbar.md); every structure there
recurs here with deeper constants.

Identity executed (per op, message M, ranks r = 8, exact Fractions;
reduce-scatter and allgather phases serialized behind one injection port):

    per-rank wire traffic  T(M, 8) = 2*(8-1)/8 * M = 7M/4
    completion time        t(M, 8) = 2*(8-1)/8 * M / B + 2L = 7M/256 + 400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 8, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Two arithmetic facts drive the whole cell, the rank-8 mirrors of the
4-rank cell's:

1. **The traffic identity equals the ring's.** T(M, 8) = 7M/4 is the same
   per-rank wire-byte identity as the 8-rank ring (page
   [8r-ring.md](8r-ring.md)) — at r = 8 both factorizations ship 2*(r-1)/r
   bytes per rank, so the wire column below is digit-for-digit the 8r-ring
   ladder's. Under this L0 model the crossbar buys no traffic reduction at
   8 ranks either.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (7M/256); the completion times differ only in the constant —
   2L = 400 ns for the crossbar (one L per phase, chunks pipelined behind
   the injection port) versus 2*(r-1)*L = 14L = 2800 ns for the ring
   (fourteen hop latencies around the ring). Hence the exact delta identity

       delta(M) = (t_xb - t_ring) / t_ring = -2400 / (7M/256 + 2800)

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities).

Rank-class ladder vs [4r-crossbar.md](4r-crossbar.md) (closed forms, not
measurements): the constant gap 2*(r-2)*L grows from 800 ns to 2400 ns, so
the small-M delta envelope deepens from -2/3 to **-6/7** — in general
-(r-2)/(r-1) — and at every grid size the 8-rank delta is more negative
than the 4-rank delta (ratio climbing 9/7 toward its 18/7 large-M limit):
the ring's latency chain grows with r while the crossbar's stays 2L. At
the ring identity's own balance point M* = L*B*r = 102400 B the delta is
exactly -3/7 (general: -(r-2)/(2(r-1)); at rank 4 the same fact read
-1/3).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell). Ring baseline ladder: [8r-ring.md](8r-ring.md) (its rows carry
delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 7M/4 (exact) | crossbar CCT ns = 7M/256 + 400 (exact) | ring CCT ns = 7M/256 + 2800 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 7168 | 512 | 2912 | -75/91 | -82.4176 |
| 8192 | 8 KiB | 14336 | 624 | 3024 | -50/63 | -79.3651 |
| 16384 | 16 KiB | 28672 | 848 | 3248 | -150/203 | -73.8916 |
| 65536 | 64 KiB | 114688 | 2192 | 4592 | -150/287 | -52.2648 |
| 131072 | 128 KiB | 229376 | 3984 | 6384 | -50/133 | -37.5940 |
| 262144 | 256 KiB | 458752 | 7568 | 9968 | -150/623 | -24.0770 |
| 1048576 | 1 MiB | 1835008 | 29072 | 31472 | -150/1967 | -7.6258 |
| 2097152 | 2 MiB | 3670016 | 57744 | 60144 | -50/1253 | -3.9904 |
| 4194304 | 4 MiB | 7340032 | 115088 | 117488 | -150/7343 | -2.0428 |
| 16777216 | 16 MiB | 29360128 | 459152 | 461552 | -150/28847 | -0.5200 |
| 33554432 | 32 MiB | 58720256 | 917904 | 920304 | -50/19173 | -0.2608 |
| 67108864 | 64 MiB | 117440512 | 1835408 | 1837808 | -150/114863 | -0.1306 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; total wire bytes at
M = 4096: 344064 = 6 ops x 2*(8-1)*4096 — the same conservation identity
and the same total as the 8-rank ring, consistent with the equal traffic
identity). All 12 rows rederived independently from the closed forms
during stage verification — table, delta identity, and identities agree
exactly (exact-string equality on every wire, time, delta, and
conservation-total field).

## Crossover message sizes

**None — for a structural reason, not a sampling one.** Within this cell
there is exactly one declared identity (single-port crossbar), and against
the ring baseline the two completion-time identities have the SAME
bandwidth term (7M/256) and differ only by a constant (400 ns vs 2800 ns),
so the two curves are translates of each other in M: the crossbar identity
is faster at every finite M, the delta -2400/(7M/256 + 2800) never changes
sign, and no payload size exists where the orderings swap. Recorded
honestly, exactly as in the 4-rank cell; the crossover question stays
non-trivial only in cells whose bandwidth coefficients differ (e.g. torus
factorizations). (Arithmetic fact of the crossbar identity, not a
crossover: its bandwidth term 7M/256 equals its latency term 400 at
M = 102400/7 ≈ 14628.57 B, between the 8 KiB and 16 KiB grid points —
exactly (r-1) = 7 times below the ring's own balance point 102400 B, which
sits between the 64 KiB and 128 KiB points.)

## Run provenance

- sweep id: `cb9112025d994bc8ce1dbd4da09a1ceb2b961039596805ed9b6027cd95ac6ec0`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_8r_crossbar_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_8r_crossbar_v1.yaml`
  (sha256 `db48330a770edeb9c323dd25a975a70d38b89ec74d3a24792b07afddc3d84ff9`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp8.yaml`
  (sha256 `130d90384c91bc9f76ac40fea0386d0355355a3f5f57da608f710fd41e66abed`,
  the same file the 8r-ring cell used)
- topology: `experiments/topologies/crossbar8_free_params.yaml`
  (sha256 `4c3f09632289b8b690d2006baac6e71f488ec3b3b24ea3ff496418365e908967`,
  pre-tracked from the earlier design-space work and reused as-is; baseline
  topology `experiments/topologies/ring8_free_params.yaml` sha256
  `34b8aed485253e332423f625412f4b5820f7ddd7999fc4e3c762c79c02f2de84`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `eaa09790ea3eba2841db40af44528b29826dd0f9232a4a21642dc61565dfc19c`
  / `fc81ee50d2c086bae3f417c0e8f019e84ad37bc5a5c465db2ab53ac2c4f14f17`);
  `tests/determinism` 13 passed; full suite 543 passed; paper-check PASS.

Catalog: [atlas index](README.md).
