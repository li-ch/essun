# Atlas cell 32r-ring — rank class 32, algorithm family ring

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

This cell **opens rank class 32** and IS its baseline.

## What this cell contains

The ring family at 32 ranks has exactly ONE declared L0 identity:
`allreduce_ring` over a unidirectional ring (backend `analytical_l0`).
There is no second ring configuration to vary — the free parameters are
shared (below) and bidirectional or ragged-chunk ring variants are
different, undeclared identities. This cell therefore IS the rank-class-32
baseline that the other 32-rank atlas pages (crossbar, torus, doubling,
phases, L0.5) delta against; its delta column is exactly `0` at every
size, recorded as the arithmetic fact it is.

Identity executed (per op, message M, ranks r = 32, exact Fractions):

    per-rank wire traffic  T(M, 32) = 2*(32-1)/32 * M = 31M/16
    completion time        t(M, 32) = T(M,32)/B + 2*(32-1)*L = 31M/1024 + 12400 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 32, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Rank-class-32 arithmetic facts vs the 4-, 8- and 16-rank baseline pages
(same free parameters, closed forms, not measurements): the wire
coefficient rises 3/2 → 7/4 → 15/8 → **31/16** (walking toward the
2(r−1)/r → 2 asymptote), the latency chain 2·3·L = 1200 ns → 2·7·L =
2800 ns → 2·15·L = 6000 ns → **2·31·L = 12400 ns**, and the identity's
own balance point (bandwidth term equals latency term, M* = L·B·r) doubles
51200 B → 102400 B → 204800 B → **409600 B = 400 KiB** — the M* ∝ r law's
fourth consecutive exact-2x data point, the third consecutive doubling, so
the ring balance ladder reads 50/100/200/400 KiB (predicted from the
landed 16r page and confirmed on this fresh execution). 409600 B sits
between the 256 KiB and 1 MiB grid points here, exactly as 204800 B sits
between the 128 KiB and 256 KiB points at rank 16, 102400 B between the
64 KiB and 128 KiB points at rank 8, and 51200 B between the 16 KiB and
64 KiB points at rank 4.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell).

| payload (bytes) | payload (human) | wire B/rank = 31M/16 (exact) | CCT mean ns = 31M/1024 + 12400 (exact) | delta vs ring baseline (exact fraction) |
|---|---|---|---|---|
| 4096 | 4 KiB | 7936 | 12524 | 0 |
| 8192 | 8 KiB | 15872 | 12648 | 0 |
| 16384 | 16 KiB | 31744 | 12896 | 0 |
| 65536 | 64 KiB | 126976 | 14384 | 0 |
| 131072 | 128 KiB | 253952 | 16368 | 0 |
| 262144 | 256 KiB | 507904 | 20336 | 0 |
| 1048576 | 1 MiB | 2031616 | 44144 | 0 |
| 2097152 | 2 MiB | 4063232 | 75888 | 0 |
| 4194304 | 4 MiB | 8126464 | 139376 | 0 |
| 16777216 | 16 MiB | 32505856 | 520304 | 0 |
| 33554432 | 32 MiB | 65011712 | 1028208 | 0 |
| 67108864 | 64 MiB | 130023424 | 2044016 | 0 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; e.g. total wire bytes at
M = 4096: 1523712 = 6 ops x 2*(32-1)*4096). All 12 rows rederived
independently from the closed form during stage verification — table and
identity agree exactly (exact-string equality on every wire, time, delta,
and conservation-total field).

## Crossover message sizes

**None in this cell.** A crossover is a payload size where two different
identities in one cell swap ordering; this cell contains exactly one
identity (the baseline itself), so no crossover exists by construction —
recorded honestly rather than forced. Crossovers against this reference
ladder are reported on the non-ring 32-rank pages. (Arithmetic fact of the
single identity, not a crossover: its bandwidth term 31M/1024 equals its
latency term 12400 at M = 409600 B, between the 256 KiB and 1 MiB grid
points.)

## Run provenance

- sweep id: `d363e9f7ceeb07cd497fdabe4833705729abd81d133f17b97e5d6ac5e9a43fe3`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_32r_ring_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_32r_ring_v1.yaml`
  (sha256 `24f070e3130ae042b3138d67295f17521e99bfd7235c711ad3aab61a682c7c5e`)
- workload: `experiments/workloads/w1_dense_tp_decode_tp32.yaml`
  (sha256 `170833ec1347c016120a1f9dde5e6b771f0ac643c1f2626b0ebb905653083ea8`)
- topology: `experiments/topologies/ring32_free_params.yaml`
  (sha256 `90e694ecb6a71bc9ac4b050c8c54de506f76346b242e19b7c63712b758337ac2`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `43216476cb5a6e624a2f8aed390cfdf708736575b0b836b0ed04d1010724b5e0`
  / `38ffaf896768d4f0b123925b6c078e83a6a65eb40abb335bf020cb0430ce405f`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 577 passed.

Catalog: [atlas index](README.md).
