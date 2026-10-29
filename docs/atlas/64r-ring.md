# Atlas cell 64r-ring — rank class 64, algorithm family ring

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

This cell **opens rank class 64 — the FINAL rank class of the atlas
ladder — and IS its baseline**.

## What this cell contains

The ring family at 64 ranks has exactly ONE declared L0 identity:
`allreduce_ring` over a unidirectional ring (backend `analytical_l0`).
There is no second ring configuration to vary — the free parameters are
shared (below) and bidirectional or ragged-chunk ring variants are
different, undeclared identities. This cell therefore IS the rank-class-64
baseline that the other 64-rank atlas pages (crossbar, torus, doubling,
phases, L0.5) delta against; its delta column is exactly `0` at every
size, recorded as the arithmetic fact it is.

Identity executed (per op, message M, ranks r = 64, exact Fractions):

    per-rank wire traffic  T(M, 64) = 2*(64-1)/64 * M = 63M/32
    completion time        t(M, 64) = T(M,64)/B + 2*(64-1)*L = 63M/2048 + 25200 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 64, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Rank-class-64 arithmetic facts vs the 4-, 8-, 16- and 32-rank baseline
pages (same free parameters, closed forms, not measurements): the wire
coefficient rises 3/2 → 7/4 → 15/8 → 31/16 → **63/32** (walking toward the
2(r−1)/r → 2 asymptote), the latency chain 2·3·L = 1200 ns → 2·7·L =
2800 ns → 2·15·L = 6000 ns → 2·31·L = 12400 ns → **2·63·L = 25200 ns**,
and the identity's own balance point (bandwidth term equals latency term,
M* = L·B·r) doubles 51200 B → 102400 B → 204800 B → 409600 B →
**819200 B = 800 KiB** — the M* ∝ r law's fifth consecutive exact-2x data
point, its fourth consecutive doubling, so the ring balance ladder reads
50/100/200/400/800 KiB (predicted from the landed 32r page and confirmed
on this fresh execution; derived from the law itself, M* = 200·64·64 B,
with the ladder cross-checked 51200·2⁴ = 819200 and 819200/1024 = 800
exactly). 819200 B sits between the 256 KiB and 1 MiB grid points here —
the same bracket as 409600 B at rank 32, because the shared ladder's x4
step spans 2^18 → 2^20 — whereas 204800 B sat between the 128 KiB and
256 KiB points at rank 16, 102400 B between the 64 KiB and 128 KiB points
at rank 8, and 51200 B between the 16 KiB and 64 KiB points at rank 4.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, so
the divisibility guards `A-L*-DIV` never reject a grid point in any atlas
cell).

| payload (bytes) | payload (human) | wire B/rank = 63M/32 (exact) | CCT mean ns = 63M/2048 + 25200 (exact) | delta vs ring baseline (exact fraction) |
|---|---|---|---|---|
| 4096 | 4 KiB | 8064 | 25326 | 0 |
| 8192 | 8 KiB | 16128 | 25452 | 0 |
| 16384 | 16 KiB | 32256 | 25704 | 0 |
| 65536 | 64 KiB | 129024 | 27216 | 0 |
| 131072 | 128 KiB | 258048 | 29232 | 0 |
| 262144 | 256 KiB | 516096 | 33264 | 0 |
| 1048576 | 1 MiB | 2064384 | 57456 | 0 |
| 2097152 | 2 MiB | 4128768 | 89712 | 0 |
| 4194304 | 4 MiB | 8257536 | 154224 | 0 |
| 16777216 | 16 MiB | 33030144 | 541296 | 0 |
| 33554432 | 32 MiB | 66060288 | 1057392 | 0 |
| 67108864 | 64 MiB | 132120576 | 2089584 | 0 |

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; e.g. total wire bytes at
M = 4096: 3096576 = 6 ops x 2*(64-1)*4096). All 12 rows rederived
independently from the closed form during stage verification — table and
identity agree exactly (exact-string equality on every wire, time, delta,
and conservation-total field).

## Crossover message sizes

**None in this cell.** A crossover is a payload size where two different
identities in one cell swap ordering; this cell contains exactly one
identity (the baseline itself), so no crossover exists by construction —
recorded honestly rather than forced. Crossovers against this reference
ladder are reported on the non-ring 64-rank pages. (Arithmetic fact of the
single identity, not a crossover: its bandwidth term 63M/2048 equals its
latency term 25200 at M = 819200 B, between the 256 KiB and 1 MiB grid
points.)

## Run provenance

- sweep id: `91450af575d38617f0d31292333ec71b75b317f57482ac823df9b4f0d941b34d`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_64r_ring_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_64r_ring_v1.yaml`
  (sha256 `ecc861241b6a9bab1f85da1e012605b72fdff4b0387309f1729613630665f87e`)
- workload: `experiments/workloads/w1_dense_tp_decode_tp64.yaml`
  (sha256 `e3930d1e8a2c651e893882b0085e3222c932dfae6e83ffd32e8838a667c05898`)
- topology: `experiments/topologies/ring64_free_params.yaml`
  (sha256 `28b187beb2220eebd3d05ab29e969d49badd517ffdc764b5627607211c34f42b`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `89d634d4e6effde6c2222b12dc28998a14aa6fdb3e68b3a26140fe92976af9c1`
  / `ceedd579b5205bf48b6daccbd6b61f9b33b7fcb44cfd4b4c262345959032f9ec`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 639 passed.

Catalog: [atlas index](README.md).
