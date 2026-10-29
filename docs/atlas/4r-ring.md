# Atlas cell 4r-ring — rank class 4, algorithm family ring

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The ring family at 4 ranks has exactly ONE declared L0 identity:
`allreduce_ring` over a unidirectional ring (backend `analytical_l0`).
There is no second ring configuration to vary — the free parameters are
shared (below) and bidirectional or ragged-chunk ring variants are
different, undeclared identities. This cell therefore IS the rank-class-4
baseline that the other 4-rank atlas pages (crossbar, torus, doubling,
phases, L0.5) delta against; its delta column is exactly `0` at every
size, recorded as the arithmetic fact it is.

Identity executed (per op, message M, ranks r = 4, exact Fractions):

    per-rank wire traffic  T(M, 4) = 2*(4-1)/4 * M = 3M/2
    completion time        t(M, 4) = T(M,4)/B + 2*(4-1)*L = 3M/128 + 1200 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 4, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell).

| payload (bytes) | payload (human) | wire B/rank = 3M/2 (exact) | CCT mean ns = 3M/128 + 1200 (exact) | delta vs ring baseline (exact fraction) |
|---|---|---|---|---|
| 4096 | 4 KiB | 6144 | 1296 | 0 |
| 8192 | 8 KiB | 12288 | 1392 | 0 |
| 16384 | 16 KiB | 24576 | 1584 | 0 |
| 65536 | 64 KiB | 98304 | 2736 | 0 |
| 131072 | 128 KiB | 196608 | 4272 | 0 |
| 262144 | 256 KiB | 393216 | 7344 | 0 |
| 1048576 | 1 MiB | 1572864 | 25776 | 0 |
| 2097152 | 2 MiB | 3145728 | 50352 | 0 |
| 4194304 | 4 MiB | 6291456 | 99504 | 0 |
| 16777216 | 16 MiB | 25165824 | 394416 | 0 |
| 33554432 | 32 MiB | 50331648 | 787632 | 0 |
| 67108864 | 64 MiB | 100663296 | 1574064 | 0 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; e.g. total wire bytes at
M = 4096: 147456 = 6 ops x 2*(4-1)*4096). All 12 rows rederived
independently from the closed form during stage verification — table and
identity agree exactly.

## Crossover message sizes

**None in this cell.** A crossover is a payload size where two different
identities in one cell swap ordering; this cell contains exactly one
identity (the baseline itself), so no crossover exists by construction —
recorded honestly rather than forced. Crossovers against this reference
ladder are reported on the non-ring 4-rank pages. (Arithmetic fact of the
single identity, not a crossover: its bandwidth term 3M/128 equals its
latency term 1200 at M = 51200 B, between the 16 KiB and 64 KiB grid
points.)

## Run provenance

- sweep id: `a7688bb88027e3ed33a6fc04801a4b006dce61f4808127694f863115b6c453fe`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_4r_ring_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_4r_ring_v1.yaml`
  (sha256 `0f348fa37f34c62cfea6ea11cc59255741dbcc2848908ab6551673f6edc15608`)
- workload: `experiments/workloads/w1_dense_tp_decode_tp4.yaml`
  (sha256 `89b3c85f3c1c2d7102fc8df8f328e766bfb0c2a163bd2e283d63bf45728af2a1`)
- topology: `experiments/topologies/ring4_free_params.yaml`
  (sha256 `120d0f02a0582bd5f8aa92f53ab692568a28e6ddb5f0f8ca959698a4ca02ebd7`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `f5c4b98019e6e0d255a31387b7386c3b711ac84e9160b0cd44d4e33d3af0f02e`
  / `c6d625fc5140a89ad0c3d05ca84862a9ade88cdf7f6c1d081cc36b7d14a3919e`);
  `tests/determinism/test_sweep_replay.py` 5 passed.

Catalog: [atlas index](README.md).
