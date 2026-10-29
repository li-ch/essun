# Atlas cell 4r-crossbar — rank class 4, algorithm family crossbar

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The crossbar family at 4 ranks has exactly ONE declared L0 identity:
`allreduce_crossbar` over a fully-connected single-port fabric (backend
`analytical_l0_crossbar`). The single-port injection model is a modeling
assumption (A-L0X-PORT); a multi-port fabric — every pair link at full B —
is a different identity, explicitly unsupported by the backend, and does
not appear here. Free parameters are shared with every other atlas cell
(below), so the only degrees of freedom are the payload grid.

Identity executed (per op, message M, ranks r = 4, exact Fractions;
reduce-scatter and allgather phases serialized behind one injection port):

    per-rank wire traffic  T(M, 4) = 2*(4-1)/4 * M = 3M/2
    completion time        t(M, 4) = 2*(4-1)/4 * M / B + 2L = 3M/128 + 400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 4, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Two arithmetic facts drive the whole cell, both visible in the identities:

1. **The traffic identity equals the ring's.** T(M, 4) = 3M/2 is the same
   per-rank wire-byte identity as the 4-rank ring (page
   [4r-ring.md](4r-ring.md)) — at r = 4 both factorizations ship 2*(r-1)/r
   bytes per rank, so the wire column below is digit-for-digit the ring
   ladder's. Under this L0 model the crossbar buys no traffic reduction.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (3M/128); the completion times differ only in the constant —
   2L = 400 ns for the crossbar (one L per phase, chunks pipelined behind
   the injection port) versus 2*(r-1)*L = 6L = 1200 ns for the ring (six
   hop latencies around the ring). Hence the exact delta identity

       delta(M) = (t_xb - t_ring) / t_ring = -800 / (3M/128 + 1200)

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell). Ring baseline ladder: [4r-ring.md](4r-ring.md) (its rows carry
delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 3M/2 (exact) | crossbar CCT ns = 3M/128 + 400 (exact) | ring CCT ns = 3M/128 + 1200 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 6144 | 496 | 1296 | -50/81 | -61.7284 |
| 8192 | 8 KiB | 12288 | 592 | 1392 | -50/87 | -57.4713 |
| 16384 | 16 KiB | 24576 | 784 | 1584 | -50/99 | -50.5051 |
| 65536 | 64 KiB | 98304 | 1936 | 2736 | -50/171 | -29.2398 |
| 131072 | 128 KiB | 196608 | 3472 | 4272 | -50/267 | -18.7266 |
| 262144 | 256 KiB | 393216 | 6544 | 7344 | -50/459 | -10.8932 |
| 1048576 | 1 MiB | 1572864 | 24976 | 25776 | -50/1611 | -3.1037 |
| 2097152 | 2 MiB | 3145728 | 49552 | 50352 | -50/3147 | -1.5888 |
| 4194304 | 4 MiB | 6291456 | 98704 | 99504 | -50/6219 | -0.8040 |
| 16777216 | 16 MiB | 25165824 | 393616 | 394416 | -50/24651 | -0.2028 |
| 33554432 | 32 MiB | 50331648 | 786832 | 787632 | -50/49227 | -0.1016 |
| 67108864 | 64 MiB | 100663296 | 1573264 | 1574064 | -50/98379 | -0.0508 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; total wire bytes at
M = 4096: 147456 = 6 ops x 2*(4-1)*4096 — the same conservation identity
as the ring, consistent with the equal traffic identity). All 12 rows
rederived independently from the closed forms during stage verification —
table, delta identity, and identities agree exactly.

## Crossover message sizes

**None — for a structural reason, not a sampling one.** Within this cell
there is exactly one declared identity (single-port crossbar), and against
the ring baseline the two completion-time identities have the SAME
bandwidth term (3M/128) and differ only by a constant (400 ns vs 1200 ns),
so the two curves are translates of each other in M: the crossbar identity
is faster at every finite M, the delta -800/(3M/128 + 1200) never changes
sign, and no payload size exists where the orderings swap. Recorded
honestly; the crossover question becomes non-trivial in cells whose
bandwidth coefficients differ (e.g. torus factorizations at higher ranks).
(Arithmetic fact of the crossbar identity, not a crossover: its bandwidth
term 3M/128 equals its latency term 400 at M = 51200/3 ≈ 17066.67 B, just
above the 16 KiB grid point — the same transition region the ring reaches
at exactly M = 51200 B.)

## Run provenance

- sweep id: `3a99d38111b4b3d91d41e7d7a20350dc78e7030b02643054e416a96005db118c`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_4r_crossbar_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_4r_crossbar_v1.yaml`
  (sha256 `9cc73f8cf716217cd9ace75167f012d6f4e83f1911b0f2d777b3d59c4992b78a`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp4.yaml`
  (sha256 `89b3c85f3c1c2d7102fc8df8f328e766bfb0c2a163bd2e283d63bf45728af2a1`)
- topology: `experiments/topologies/crossbar4_free_params.yaml`
  (sha256 `2ad41bad1037e289b73e8c0e441070b6cc801efc1dea9dc2f3f3d70487d22464`;
  baseline topology `experiments/topologies/ring4_free_params.yaml` sha256
  `120d0f02a0582bd5f8aa92f53ab692568a28e6ddb5f0f8ca959698a4ca02ebd7`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `e408e737ad02dbaba485cde9a77f9130bae0eb7614894e84b4c7e960135987fa`
  / `f5d48bdf3725a67af350437ffdbd3397518c98c5ea871563c817c78a55dff0d0`);
  `tests/determinism/test_sweep_replay.py` 5 passed.

Catalog: [atlas index](README.md).
