# Atlas cell 4r-torus — rank class 4, algorithm family torus

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The torus family factorizes 4 ranks as **1x4 or 2x2** — the stage sweeps
both factorizations, and exactly one is a declared, generatable identity:

- **1x4 — SKIP (config cannot be generated).** Attempted both through the
  backend loader and through the sweep runner's grid gate (with a real
  topology file present); both reject it with
  `analytical_l0_torus2d: a torus dimension must wrap >= 2 ranks, got 1x4`
  (shape guard, assumption A-L0T-SHAPE; the landed golden
  `tests/golden/test_l0_torus2d_golden.py::test_loader_extracts_exact_fractions_and_rejects_bad_grids`
  asserts the same rejection). The rejection is also arithmetically honest:
  a degenerate 1x4 grid would evaluate to
  `t_ring(M,1) + t_ring(M,4) = 0 + t_ring(M,4)` — exactly the flat-ring
  identity that already IS this rank class's baseline cell
  ([4r-ring.md](4r-ring.md)) — so 1x4 is not a new identity, and it is
  recorded in the index's Recorded skips, never forced.
- **2x2 — the one declared identity**: `allreduce_torus2d` over a 2x2
  ring-x-ring grid with sequential dimensions (backend `analytical_l0_torus2d`;
  modeling assumptions A-L0T-SEQ sequential dimensions, A-L0T-UNIF uniform
  links, A-L0T-SHAPE grid shape). Overlapped dimensions and the interleaved
  reduce-scatter/allgather decomposition are different, undeclared identities,
  explicitly unsupported by the backend.

Identity executed (per op, message M, ranks r = 4 = 2x2, exact Fractions;
each dimension runs a full ring AllReduce of the entire M, dimensions
serialized):

    per-dimension kernel       t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L
    per-rank wire traffic      T(M, 4) = 2*(2 - 1/2 - 1/2) * M = 2M
    completion time            t(M, 4) = 2 * t_ring(M, 2) = M/32 + 800 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 4, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Three arithmetic facts drive the whole cell, all visible in the identities
(ring baseline: T = 3M/2, t = 3M/128 + 1200 — [4r-ring.md](4r-ring.md)):

1. **This is the first 4-rank atlas cell whose traffic identity differs
   from the ring's.** T = 2M per rank versus the ring's 3M/2 — exactly 4/3
   of it, i.e. **+1/3 more per-rank wire bytes at every payload size** (the
   crossbar cell's traffic identity equaled the ring's; this one does not).
   The 2x2 torus pays one full M per dimension: the module's documented
   trade — shorter latency chain against more wire bytes — is the whole
   content of this cell.
2. **Both terms scale by exact reciprocal-shaped factors: 4/3 and 2/3.**
   The bandwidth term is M/32 = 4M/128 = (4/3) * (the ring's 3M/128); the
   latency term is 4L = 800 = (2/3) * (the ring's 6L = 1200) — the chain is
   2*(r1 + r2 - 2) = 4 hops versus the flat ring's 2*(r-1) = 6. So
   `t_torus = (4/3)*beta(M) + (2/3)*lambda` where beta and lambda are the
   ring's bandwidth and latency terms, and the gap collapses to the exact
   linear form
       t_torus - t_ring = (beta - lambda)/3 = (M - 51200)/128 ns.
3. **The delta identity and its exact envelope.**
       delta(M) = (t_torus - t_ring)/t_ring = (M - 51200)/(3*(M + 51200))
   is strictly increasing in M with exact endpoints **delta(0) = -1/3**
   (the pure latency-term fact 800/1200 - 1 = -1/3) and
   **delta(inf) = +1/3** (the pure bandwidth-term fact 4/3 - 1 = 1/3):
   the two endpoints are the same 1/3, swapped between terms.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by both torus dimension sizes, so the divisibility guard `A-L0T-DIV` never
rejects a grid point). Ring baseline ladder: [4r-ring.md](4r-ring.md) (its
rows carry delta exactly 0 by construction; the sweep grid carries the
baseline config so the runner can match per-size deltas — see provenance
below).

| payload (bytes) | payload (human) | wire B/rank = 2M (exact) | torus CCT ns = M/32 + 800 (exact) | ring CCT ns = 3M/128 + 1200 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 8192 | 928 | 1296 | -23/81 | -28.3951 |
| 8192 | 8 KiB | 16384 | 1056 | 1392 | -7/29 | -24.1379 |
| 16384 | 16 KiB | 32768 | 1312 | 1584 | -17/99 | -17.1717 |
| 65536 | 64 KiB | 131072 | 2848 | 2736 | 7/171 | 4.0936 |
| 131072 | 128 KiB | 262144 | 4896 | 4272 | 13/89 | 14.6067 |
| 262144 | 256 KiB | 524288 | 8992 | 7344 | 103/459 | 22.4401 |
| 1048576 | 1 MiB | 2097152 | 33568 | 25776 | 487/1611 | 30.2297 |
| 2097152 | 2 MiB | 4194304 | 66336 | 50352 | 333/1049 | 31.7445 |
| 4194304 | 4 MiB | 8388608 | 131872 | 99504 | 2023/6219 | 32.5293 |
| 16777216 | 16 MiB | 33554432 | 525088 | 394416 | 8167/24651 | 33.1305 |
| 33554432 | 32 MiB | 67108864 | 1049376 | 787632 | 5453/16409 | 33.2318 |
| 67108864 | 64 MiB | 134217728 | 2097952 | 1574064 | 32743/98379 | 33.2825 |

The delta column climbs monotonically from -23/81 toward the exact +1/3
asymptote — the large-M rows are the bandwidth-term fact (the torus moves
4/3 of the ring's bytes per rank), the small-M rows are the latency-term
fact (its hop chain is 2/3 of the ring's).

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; per dimension d of size 2:
r/2 = 2 disjoint rings x 2*(2-1)*M each, so each dimension wires 4M and the
op totals 8M = 2*(2r - r1 - r2)*M per op; e.g. total wire bytes at
M = 4096: 196608 = 6 ops x 8 x 4096). All 12 rows rederived independently
from the closed forms during stage verification (torus rows, baseline rows,
the delta identity, and the conservation totals agree exact-string-equal
with the runner's `table.json`).

## Crossover message sizes

**One exact crossover, and it is off-grid.** The delta identity
(M - 51200)/(3*(M + 51200)) changes sign at exactly **M = 51200 B (50 KiB)**
— strictly between the 16 KiB grid point (delta = -17/99, the 2x2 torus
identity has the smaller completion time) and the 64 KiB grid point
(delta = +7/171, the ring identity has the smaller one). 51200 is not a
member of the shared ladder (it is not a power of two; it lies inside the
ladder's first x4 interval 2^14 → 2^16), so the grid samples the crossover
without containing it — the page reports the exact size rather than a
bracket alone. This is the first crossover in the atlas (the crossbar cell
has none — parallel bandwidth terms); it exists here because fact 2 scales
the two terms in opposite directions (4/3 bandwidth, 2/3 latency). The
crossover lands exactly at the M where the ring's own bandwidth term equals
its latency term (3M/128 = 1200 at M = 51200, noted on
[4r-ring.md](4r-ring.md)) — not a coincidence: the gap is (beta - lambda)/3,
which vanishes exactly where beta = lambda.

## Run provenance

- sweep id: `f1a425bbca7cbcf8d0a2b944e45ca33ab13298bf7807debdeaa495ebd19c7e8c`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_4r_torus_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_4r_torus_v1.yaml`
  (sha256 `d23c86659164e8aa1138b038a92b77732fe07e44b45934ce3c6d7ee6376dbdb9`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp4.yaml`
  (sha256 `89b3c85f3c1c2d7102fc8df8f328e766bfb0c2a163bd2e283d63bf45728af2a1`)
- topology: `experiments/topologies/torus2d4_free_params.yaml`
  (sha256 `d574a95f0f2fcafced5d7ac7d39cd5d7be4f46659ebc0ebd6b68dd67f5df9a0c`;
  baseline topology `experiments/topologies/ring4_free_params.yaml` sha256
  `120d0f02a0582bd5f8aa92f53ab692568a28e6ddb5f0f8ca959698a4ca02ebd7`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `1be65fafaa5b1996585e5ba776e1b4d75601dd87f7aae5bf1fc2cac33a0c50c8`
  / `c662bf38aa5ad65b73f0a2e3120307678b35dffe6b50ce50d0d7af52b4ee4a31`);
  `tests/determinism/test_sweep_replay.py` 5 passed.

Catalog: [atlas index](README.md).
