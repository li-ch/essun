# Atlas cell 16r-ring — rank class 16, algorithm family ring

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

This cell **opens rank class 16** and IS its baseline.

## What this cell contains

The ring family at 16 ranks has exactly ONE declared L0 identity:
`allreduce_ring` over a unidirectional ring (backend `analytical_l0`).
There is no second ring configuration to vary — the free parameters are
shared (below) and bidirectional or ragged-chunk ring variants are
different, undeclared identities. This cell therefore IS the rank-class-16
baseline that the other 16-rank atlas pages (crossbar, torus, doubling,
phases, L0.5) delta against; its delta column is exactly `0` at every
size, recorded as the arithmetic fact it is.

Identity executed (per op, message M, ranks r = 16, exact Fractions):

    per-rank wire traffic  T(M, 16) = 2*(16-1)/16 * M = 15M/8
    completion time        t(M, 16) = T(M,16)/B + 2*(16-1)*L = 15M/512 + 6000 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 16, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Rank-class-16 arithmetic facts vs the 4- and 8-rank baseline pages (same
free parameters, closed forms, not measurements): the wire coefficient
rises 3/2 → 7/4 → 15/8 (walking toward the 2(r−1)/r → 2 asymptote), the
latency chain 2·3·L = 1200 ns → 2·7·L = 2800 ns → 2·15·L = 6000 ns, and
the identity's own balance point (bandwidth term equals latency term,
M* = L·B·r) doubles 51200 B → 102400 B → **204800 B = 200 KiB** — the
M* ∝ r law's third consecutive exact-2x data point. 204800 B sits between
the 128 KiB and 256 KiB grid points here, exactly as 102400 B sits between
the 64 KiB and 128 KiB points at rank 8 and 51200 B between the 16 KiB and
64 KiB points at rank 4.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell).

| payload (bytes) | payload (human) | wire B/rank = 15M/8 (exact) | CCT mean ns = 15M/512 + 6000 (exact) | delta vs ring baseline (exact fraction) |
|---|---|---|---|---|
| 4096 | 4 KiB | 7680 | 6120 | 0 |
| 8192 | 8 KiB | 15360 | 6240 | 0 |
| 16384 | 16 KiB | 30720 | 6480 | 0 |
| 65536 | 64 KiB | 122880 | 7920 | 0 |
| 131072 | 128 KiB | 245760 | 9840 | 0 |
| 262144 | 256 KiB | 491520 | 13680 | 0 |
| 1048576 | 1 MiB | 1966080 | 36720 | 0 |
| 2097152 | 2 MiB | 3932160 | 67440 | 0 |
| 4194304 | 4 MiB | 7864320 | 128880 | 0 |
| 16777216 | 16 MiB | 31457280 | 497520 | 0 |
| 33554432 | 32 MiB | 62914560 | 989040 | 0 |
| 67108864 | 64 MiB | 125829120 | 1972080 | 0 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; e.g. total wire bytes at
M = 4096: 737280 = 6 ops x 2*(16-1)*4096). All 12 rows rederived
independently from the closed form during stage verification — table and
identity agree exactly (exact-string equality on every wire, time, delta,
and conservation-total field).

## Crossover message sizes

**None in this cell.** A crossover is a payload size where two different
identities in one cell swap ordering; this cell contains exactly one
identity (the baseline itself), so no crossover exists by construction —
recorded honestly rather than forced. Crossovers against this reference
ladder are reported on the non-ring 16-rank pages. (Arithmetic fact of the
single identity, not a crossover: its bandwidth term 15M/512 equals its
latency term 6000 at M = 204800 B, between the 128 KiB and 256 KiB grid
points.)

## Run provenance

- sweep id: `f44e7891ddb65e5c875a24496b37047354c41aae02ee89b76e6e85a6bfbb69b8`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_16r_ring_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_16r_ring_v1.yaml`
  (sha256 `b94267dd2bbd3cc464c9edd6911a65b575671b666ab63866703648463e1f2f18`)
- workload: `experiments/workloads/w1_dense_tp_decode_tp16.yaml`
  (sha256 `1602fd4b10fe9ac9b81de3aa7d6a92830e115547b8fb948e3c46f11a81c0fc99`)
- topology: `experiments/topologies/ring16_free_params.yaml`
  (sha256 `f973784db47ebc461da1111eecdcb44accc73c06a06c0daeb86d9e46cab8a119`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `77ed95e922b39c3f9428fd34f0279a532d6dc559a7ac52ee0dab7875f8a6e411`
  / `aae62b9e18f09afd04a8f7867654dfa45ac584c7b3a2dc0cd11a79c072b79e1d`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 557 passed.

Catalog: [atlas index](README.md).
