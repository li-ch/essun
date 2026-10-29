# Atlas cell 8r-torus — rank class 8, algorithm family torus

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The torus family factorizes 8 ranks as **1x8 or 2x4** (unordered, plus
transposes). The stage sweeps the factorizations; exactly one is a declared,
generatable identity:

- **1x8 — SKIP (config cannot be generated).** Attempted both through the
  backend loader and through the sweep runner's grid gate (with a real
  topology file present); both reject it with
  `analytical_l0_torus2d: a torus dimension must wrap >= 2 ranks, got 1x8`
  (shape guard, assumption A-L0T-SHAPE). The landed golden
  `tests/golden/test_l0_torus2d_golden.py::test_loader_extracts_exact_fractions_and_rejects_bad_grids`
  asserts literally this rank-8 rejection (its bad grid is 1x8 at ranks 8).
  The **8x1 transpose** is rejected identically by the same guard
  (`got 8x1`), exercised through the loader during the stage. The rejection
  is also arithmetically honest: a degenerate 1x8 grid would evaluate to
  `t_ring(M,1) + t_ring(M,8) = 0 + t_ring(M,8)` — exactly the flat-ring
  identity that already IS this rank class's baseline cell
  ([8r-ring.md](8r-ring.md)) — so 1x8 is not a new identity, and it is
  recorded in the index's Recorded skips, never forced.
- **2x4 — the one declared identity**: `allreduce_torus2d` over a 2x4
  ring-x-ring grid with sequential dimensions (backend `analytical_l0_torus2d`;
  modeling assumptions A-L0T-SEQ sequential dimensions, A-L0T-UNIF uniform
  links, A-L0T-SHAPE grid shape). The **4x2 transpose** loads cleanly and
  evaluates to the IDENTICAL identity — completion time and wire traffic
  exactly equal at every probed size (module identities are symmetric in
  dim1 x dim2, as the topology file documents) — so it is the same identity,
  not a second one, and the grid carries 2x4 once. Overlapped dimensions and
  the interleaved reduce-scatter/allgather decomposition are different,
  undeclared identities, explicitly unsupported by the backend.

Identity executed (per op, message M, ranks r = 8 = 2x4, exact Fractions;
each dimension runs a full ring AllReduce of the entire M, dimensions
serialized):

    per-dimension kernel       t_ring(M, k) = 2*(k-1)/k * M/B + 2*(k-1)*L
    per-rank wire traffic      T(M, 8) = 2*(2 - 1/2 - 1/4) * M = 5M/2
    completion time            t(M, 8) = t_ring(M,2) + t_ring(M,4) = 5M/128 + 1600 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 8, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Three arithmetic facts drive the whole cell, the rank-8 mirrors of the
4-rank cell's (ring baseline: T = 7M/4, t = 7M/256 + 2800 —
[8r-ring.md](8r-ring.md)):

1. **The traffic identity differs from the ring's, by more than at rank 4.**
   T = 5M/2 per rank versus the ring's 7M/4 — exactly 10/7 of it, i.e.
   **+3/7 more per-rank wire bytes at every payload size** (at rank 4 the
   same fact read +1/3; the naive full-M-per-dimension composition pays
   relatively more extra wire as the ranks grow). The 2x4 torus pays one
   full M per dimension: shorter latency chain against more wire bytes —
   the module's documented trade, now deeper on the wire side.
2. **Both terms scale by exact reciprocal-shaped factors: 10/7 and 4/7.**
   The bandwidth term is 5M/128 = (10/7)*(the ring's 7M/256); the latency
   term is 8L = 1600 = (4/7)*(the ring's 14L = 2800) — the chain is
   2*(r1 + r2 - 2) = 8 hops versus the flat ring's 2*(r-1) = 14. So
   `t_torus = (10/7)*beta + (4/7)*lambda` where beta and lambda are the
   ring's bandwidth and latency terms, and the gap collapses to the exact
   linear form
       t_torus - t_ring = (3/7)*(beta - lambda) = 3M/256 - 1200 ns.
3. **The delta identity and its exact envelope.**
       delta(M) = (t_torus - t_ring)/t_ring = (3M - 307200)/(7M + 716800)
                = (3/7) * (M - 102400)/(M + 102400)
   is strictly increasing in M with exact endpoints **delta(0) = -3/7**
   (the pure latency-term fact 1600/2800 - 1 = -3/7) and
   **delta(inf) = +3/7** (the pure bandwidth-term fact 10/7 - 1 = 3/7):
   same magnitude at both ends, swapped between terms — as at rank 4, but
   the envelope deepens from +-1/3 to +-3/7.

**The factorization law behind both cells** (closed forms, exact): for ANY
factorization r = r1 x r2 the gap against the flat ring is

    t_torus - t_ring = 2*(r1-1)*(r2-1) * (M/(B*r) - L)

so the delta is `((r1-1)*(r2-1)/(r-1)) * (M - L*B*r)/(M + L*B*r)` —
coefficient (1*1)/3 = 1/3 at 4r 2x2 (reproducing the 4r-torus page's
identity exactly) and (1*3)/7 = 3/7 here. The crossover is at
M = L*B*r for EVERY factorization — precisely the ring identity's own
balance point, which is why it landed there at rank 4 "not by coincidence"
and lands there again at rank 8.

**Rank-class ladder vs [4r-torus.md](4r-torus.md)** (closed forms, not
measurements): every constant deepens — extra wire +1/3 -> +3/7, chain
ratio 2/3 -> 4/7, envelope +-1/3 -> +-3/7, crossover 51200 B -> 102400 B
(scaling with L*B*r). Unlike the crossbar family's ladder (where the 8-rank
delta is uniformly more negative than the 4-rank one), the signed torus
deltas cross ONCE: the exact crossing of (3/7)(M-102400)/(M+102400) with
(1/3)(M-51200)/(M+51200) is at M = 204800 + 153600*sqrt(2) ≈ 422023 B
(between the 256 KiB and 1 MiB grid points; the other root,
204800 - 153600*sqrt(2), is negative and outside the physical domain).
Below it the rank-8 delta is the lower curve — including the whole
negative band, where the 2x4 torus is even better value at 8 ranks than
2x2 is at 4 (e.g. at the rank-4 crossover size M = 51200 the rank-8
delta is exactly -1/7); above it the rank-8 delta is the higher one —
the 2x4 torus pays its +3/7 wire more dearly at 8 ranks than 2x2 pays
its +1/3 at 4 (in the 128-256 KiB band both deltas are positive and the
rank-4 one is larger precisely because its crossover sits an octave
lower).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by both torus dimension sizes 2 and 4, so the divisibility guard `A-L0T-DIV`
never rejects a grid point). Ring baseline ladder: [8r-ring.md](8r-ring.md)
(its rows carry delta exactly 0 by construction; the sweep grid carries the
baseline config so the runner can match per-size deltas — see provenance
below).

| payload (bytes) | payload (human) | wire B/rank = 5M/2 (exact) | torus CCT ns = 5M/128 + 1600 (exact) | ring CCT ns = 7M/256 + 2800 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 10240 | 1760 | 2912 | -36/91 | -39.5604 |
| 8192 | 8 KiB | 20480 | 1920 | 3024 | -23/63 | -36.5079 |
| 16384 | 16 KiB | 40960 | 2240 | 3248 | -9/29 | -31.0345 |
| 65536 | 64 KiB | 163840 | 4160 | 4592 | -27/287 | -9.4077 |
| 131072 | 128 KiB | 327680 | 6720 | 6384 | 1/19 | 5.2632 |
| 262144 | 256 KiB | 655360 | 11840 | 9968 | 117/623 | 18.7801 |
| 1048576 | 1 MiB | 2621440 | 42560 | 31472 | 99/281 | 35.2313 |
| 2097152 | 2 MiB | 5242880 | 83520 | 60144 | 487/1253 | 38.8667 |
| 4194304 | 4 MiB | 10485760 | 165440 | 117488 | 2997/7343 | 40.8144 |
| 16777216 | 16 MiB | 41943040 | 656960 | 461552 | 12213/28847 | 42.3372 |
| 33554432 | 32 MiB | 83886080 | 1312320 | 920304 | 8167/19173 | 42.5964 |
| 67108864 | 64 MiB | 167772160 | 2623040 | 1837808 | 7011/16409 | 42.7266 |

The delta column climbs monotonically from -36/91 toward the exact +3/7
asymptote — the large-M rows are the bandwidth-term fact (the torus moves
10/7 of the ring's bytes per rank), the small-M rows are the latency-term
fact (its hop chain is 4/7 of the ring's).

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; dimension 1 has 4 disjoint
rings of 2 x 2*(2-1)*M each = 8M, dimension 2 has 2 disjoint rings of 4 x
2*(4-1)*M each = 12M, so each op totals 20M = 2*(2r - r1 - r2)*M; e.g.
total wire bytes at M = 4096: 491520 = 6 ops x 20 x 4096). All 24 rows
(torus and baseline) rederived independently from the closed forms during
stage verification — wire, time, delta, and conservation totals agree
exact-string-equal with the runner's `table.json`, and the delta identity
(3/7)*(M-102400)/(M+102400) was checked equal to the runner's delta at
all 12 sizes.

## Crossover message sizes

**One exact crossover, and it is off-grid.** The delta identity
(3/7)*(M-102400)/(M+102400) changes sign at exactly **M = 102400 B
(100 KiB)** — strictly between the 64 KiB grid point (delta = -27/287, the
2x4 torus identity has the smaller completion time) and the 128 KiB grid
point (delta = +1/19, the ring identity has the smaller one). 102400 is
not a member of the shared ladder (not a power of two; it lies inside the
ladder's x2 interval 2^16 → 2^17), so the grid samples the crossover
without containing it — the page reports the exact size rather than a
bracket alone. This is the atlas's second crossover (the first was the
4r-torus cell's); by the factorization law above it lands exactly at the
ring identity's own balance point M* = L*B*r = 102400 B — noted as the
rank-4 coincidence on [8r-ring.md](8r-ring.md) and now derived, not just
observed: the gap is (3/7)*(beta - lambda), which vanishes exactly where
beta = lambda. At the rank-4 crossover size M = 51200 the rank-8 delta is
-1/7 (still torus-favoring); at its own crossover it is 0 by definition.

## Run provenance

- sweep id: `7b1e2030afcbd4a1ef3a64285ffc007a914c880eca3a0dc18fac09c8c26e2700`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_8r_torus_v1.yaml`)
- sweep manifest: `experiments/sweeps/atlas_8r_torus_v1.yaml`
  (sha256 `29c600f77c3911c081aa38c3d7aa11cc8ad59037d40709c913f5d43bc4f45c6d`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp8.yaml`
  (sha256 `130d90384c91bc9f76ac40fea0386d0355355a3f5f57da608f710fd41e66abed`,
  the same file the 8r-ring and 8r-crossbar cells used)
- topology: `experiments/topologies/torus2d_8_free_params.yaml`
  (sha256 `ea5a0ec67f3d0775ead2945908e634e3d8742d3548fa5a5b3a17cd19b3d103cd`,
  pre-tracked from the earlier design-space work and reused as-is; baseline
  topology `experiments/topologies/ring8_free_params.yaml` sha256
  `34b8aed485253e332423f625412f4b5820f7ddd7999fc4e3c762c79c02f2de84`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `167a15c5459bbf6eb1070e94755fc7136105ca6b5121f115b85a5ab982e707f6`
  / `a7c2634abb946d0843f1b97254e63b602e1921fdc7b96d9e8fc9f7f50994cbb9`);
  `tests/determinism` 13 passed; full suite 543 passed; paper-check PASS.

Catalog: [atlas index](README.md).
