# Atlas cell 8r-ring — rank class 8, algorithm family ring

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

This cell **opens rank class 8** and IS its baseline.

## What this cell contains

The ring family at 8 ranks has exactly ONE declared L0 identity:
`allreduce_ring` over a unidirectional ring (backend `analytical_l0`).
There is no second ring configuration to vary — the free parameters are
shared (below) and bidirectional or ragged-chunk ring variants are
different, undeclared identities. This cell therefore IS the rank-class-8
baseline that the other 8-rank atlas pages (crossbar, torus, doubling,
phases, L0.5) delta against; its delta column is exactly `0` at every
size, recorded as the arithmetic fact it is.

Identity executed (per op, message M, ranks r = 8, exact Fractions):

    per-rank wire traffic  T(M, 8) = 2*(8-1)/8 * M = 7M/4
    completion time        t(M, 8) = T(M,8)/B + 2*(8-1)*L = 7M/256 + 2800 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 8, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Rank-class-8 arithmetic facts vs the 4-rank baseline page (same free
parameters, closed forms, not measurements): the wire coefficient rises
from 3/2 to 7/4, the latency chain from 2*3*L = 1200 ns to 2*7*L = 2800
ns, and the identity's own balance point (bandwidth term equals latency
term, M* = L*B*r) doubles from 51200 B to 102400 B = 100 KiB — between
the 64 KiB and 128 KiB grid points here, exactly as 51200 B sits between
the 16 KiB and 64 KiB points at rank 4.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell).

| payload (bytes) | payload (human) | wire B/rank = 7M/4 (exact) | CCT mean ns = 7M/256 + 2800 (exact) | delta vs ring baseline (exact fraction) |
|---|---|---|---|---|
| 4096 | 4 KiB | 7168 | 2912 | 0 |
| 8192 | 8 KiB | 14336 | 3024 | 0 |
| 16384 | 16 KiB | 28672 | 3248 | 0 |
| 65536 | 64 KiB | 114688 | 4592 | 0 |
| 131072 | 128 KiB | 229376 | 6384 | 0 |
| 262144 | 256 KiB | 458752 | 9968 | 0 |
| 1048576 | 1 MiB | 1835008 | 31472 | 0 |
| 2097152 | 2 MiB | 3670016 | 60144 | 0 |
| 4194304 | 4 MiB | 7340032 | 117488 | 0 |
| 16777216 | 16 MiB | 29360128 | 461552 | 0 |
| 33554432 | 32 MiB | 58720256 | 920304 | 0 |
| 67108864 | 64 MiB | 117440512 | 1837808 | 0 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; e.g. total wire bytes at
M = 4096: 344064 = 6 ops x 2*(8-1)*4096). All 12 rows rederived
independently from the closed form during stage verification — table and
identity agree exactly (exact-string equality on every wire, time, delta,
and conservation-total field).

## Crossover message sizes

**None in this cell.** A crossover is a payload size where two different
identities in one cell swap ordering; this cell contains exactly one
identity (the baseline itself), so no crossover exists by construction —
recorded honestly rather than forced. Crossovers against this reference
ladder are reported on the non-ring 8-rank pages. (Arithmetic fact of the
single identity, not a crossover: its bandwidth term 7M/256 equals its
latency term 2800 at M = 102400 B, between the 64 KiB and 128 KiB grid
points.)

## Run provenance

- sweep id: `ab15366f5a0b81f0d6b7b879ea603db0a5352ec2e1b649a2577bd8e8f4176ba2`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_8r_ring_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_8r_ring_v1.yaml`
  (sha256 `583f6c97e6fa5efd1c8b300ae7bd415a8d21fd151db9fe1f3e392f65afc7b215`)
- workload: `experiments/workloads/w1_dense_tp_decode_tp8.yaml`
  (sha256 `130d90384c91bc9f76ac40fea0386d0355355a3f5f57da608f710fd41e66abed`)
- topology: `experiments/topologies/ring8_free_params.yaml`
  (sha256 `34b8aed485253e332423f625412f4b5820f7ddd7999fc4e3c762c79c02f2de84`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `6757fbc3c59b12e6c55266118da3b1b9b14fb73548e2420bf98a61005ed7ab3a`
  / `891559b279e96e6749230e05ad3141ab7fb4daa1b549868c6628416ae0f6c09c`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 543 passed.

Catalog: [atlas index](README.md).
