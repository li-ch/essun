# Atlas cell 4r-doubling — rank class 4, algorithm family recursive-doubling

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The recursive-doubling family is declared for **power-of-two rank counts
only** (modeling assumption A-L0D-POW2; the ragged/non-power splitting
variants are different, undeclared identities). Rank class 4 = 2² is a
power of two, so the family **applies** — the catalog's "include 4?"
question resolves to include, and there is no skip to record. The family
has no factorizations to sweep (unlike torus): the partner schedule is
fully determined (rank XOR 2^(i-1) at step i, k = log2(r) = 2 steps per
phase), so this cell has exactly ONE declared L0 identity:
`allreduce_recursive_doubling` over a fully-connected exchange fabric
(backend `analytical_l0_recursive_doubling`; serialized steps and phases
A-L0D-STEP, power-of-two schedule A-L0D-POW2, divisibility A-L0D-DIV —
every grid size is divisible by 4096, hence by 4, so the halving chunks
M/2^i and doubling chunks 2^(i-1)*M/r stay integral at every grid point).

Execution reachability (structural note): this backend is currently
run-manifest-unreachable — the run path's collective-capability
gate cannot admit two-word algorithm suffixes (a recorded reachability finding) — so the sweep runner, which registers the
algorithm id directly, is the execution vehicle for this cell, exactly as
in the doubling reachability note. Classified, not fixed; no src/ change was made.

Identity executed (per op, message M, ranks r = 4, k = log2(4) = 2, exact
Fractions; recursive-halving reduce phase + recursive-doubling broadcast
phase, serialized, one partner exchange per step):

    per-rank wire traffic  T(M, 4) = 2*(4-1)/4 * M = 3M/2
    completion time        t(M, 4) = 2*(4-1)/4 * M/B + 2*log2(4)*L = 3M/128 + 800 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 4, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Three arithmetic facts drive the whole cell, all visible in the identities
(ring baseline: T = 3M/2, t = 3M/128 + 1200 — [4r-ring.md](4r-ring.md)):

1. **The traffic identity equals the ring's.** T(M, 4) = 3M/2 is the same
   per-rank wire-byte identity as the 4-rank ring and (as recorded on
   [4r-crossbar.md](4r-crossbar.md)) the single-port crossbar — the module
   documents that all three L0 designs differ ONLY in the latency chain
   (ring 2*(r-1)*L = 6L, recursive doubling 2*log2(r)*L = 4L, pipelined
   crossbar 2L). The wire column below is digit-for-digit the ring
   ladder's; under this L0 model the doubling schedule buys no traffic
   change over the ring, only a shorter hop chain.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (3M/128); the completion times differ only in the constant —
   4L = 800 ns for doubling (two phases x two steps x L) versus
   2*(r-1)*L = 6L = 1200 ns for the ring. Hence the exact delta identity

       delta(M) = (t_rd - t_ring) / t_ring = -400 / (3M/128 + 1200)

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities).
3. **At r = 4 the doubling chain is the exact midpoint of the latency
   chain ladder.** 2*log2(4) = 4 = (6 + 2)/2 hops, so the doubling
   identity satisfies t_rd = (t_ring + t_xbar)/2 exactly (verified at all
   12 grid sizes), and its delta is exactly HALF the crossbar cell's
   delta at every size (crossbar delta = -800/(3M/128 + 1200),
   [4r-crossbar.md](4r-crossbar.md)) — which is why every delta below is
   -25/(odd) where the crossbar cell's are -50/(odd): the same
   denominators, half the numerator. The three latency chains also place
   the bandwidth-term-equals-latency-term transition at the exact 1:2:3
   ladder M* = {51200/3, 102400/3, 51200} B for chains {2L, 4L, 6L}
   (doubling's own transition, 102400/3 ≈ 34133.33 B, sits inside the
   ladder's first x4 interval, 16 KiB → 64 KiB).

Phase symmetry, visible in the step decomposition at r = 4: the reduce
phase sends chunks {M/2, M/4} (halving) and the broadcast phase sends
{M/4, M/2} (doubling) — mirror sequences, each phase costing exactly
3M/256 + 400 ns, so the two phases are equal-cost at this rank count.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by the rank count 4, so the divisibility guard `A-L0D-DIV` never rejects a
grid point). Ring baseline ladder: [4r-ring.md](4r-ring.md) (its rows
carry delta exactly 0 by construction; the sweep grid carries the
baseline config so the runner can match per-size deltas — see provenance
below).

| payload (bytes) | payload (human) | wire B/rank = 3M/2 (exact) | doubling CCT ns = 3M/128 + 800 (exact) | ring CCT ns = 3M/128 + 1200 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 6144 | 896 | 1296 | -25/81 | -30.8642 |
| 8192 | 8 KiB | 12288 | 992 | 1392 | -25/87 | -28.7356 |
| 16384 | 16 KiB | 24576 | 1184 | 1584 | -25/99 | -25.2525 |
| 65536 | 64 KiB | 98304 | 2336 | 2736 | -25/171 | -14.6199 |
| 131072 | 128 KiB | 196608 | 3872 | 4272 | -25/267 | -9.3633 |
| 262144 | 256 KiB | 393216 | 6944 | 7344 | -25/459 | -5.4466 |
| 1048576 | 1 MiB | 1572864 | 25376 | 25776 | -25/1611 | -1.5518 |
| 2097152 | 2 MiB | 3145728 | 49952 | 50352 | -25/3147 | -0.7944 |
| 4194304 | 4 MiB | 6291456 | 99104 | 99504 | -25/6219 | -0.4020 |
| 16777216 | 16 MiB | 25165824 | 394016 | 394416 | -25/24651 | -0.1014 |
| 33554432 | 32 MiB | 50331648 | 787232 | 787632 | -25/49227 | -0.0508 |
| 67108864 | 64 MiB | 100663296 | 1573664 | 1574064 | -25/98379 | -0.0254 |

The delta column climbs monotonically from -25/81 toward the exact 0
asymptote — every row is the pure latency-term fact (four hop latencies
against the ring's six at identical wire bytes), shrinking relative to a
completion time whose bandwidth term grows without bound.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; per op, per-rank traffic
3M/2 summed over ranks = 6M = 2*(r-1)*M — every sent byte received once by
the step partner; e.g. total wire bytes at M = 4096: 147456 = 6 ops x
6 x 4096, the same conservation identity as the ring and crossbar cells,
consistent with the equal traffic identity). All 12 rows rederived
independently from the closed forms during stage verification (doubling
rows, baseline rows, the delta identity, the midpoint relation
t_rd = (t_ring + t_xbar)/2, the half-of-crossbar-delta relation, and the
conservation totals agree exact-string-equal with the runner's
`table.json`).

## Crossover message sizes

**None — for the same structural reason as the crossbar cell, not a
sampling one.** Within this cell there is exactly one declared identity,
and against the ring baseline the two completion-time identities have the
SAME bandwidth term (3M/128) and differ only by a constant (800 ns vs
1200 ns), so the two curves are translates of each other in M: the
doubling identity has the smaller completion time at every finite M, the
delta -400/(3M/128 + 1200) never changes sign, and no payload size exists
where the orderings swap. Recorded honestly; as on the crossbar page, the
crossover question becomes non-trivial only in cells whose bandwidth
coefficients differ (the 4-rank torus cell is the example, with its exact
crossover at M = 51200 B). Cross-cell catalog context, an arithmetic fact
not a comparison: at r = 4 the torus 2x2 identity shares this cell's exact
latency constant (its chain 2*(2+2-2) = 4 hops = 4L = 800 ns) but moves
4/3 of the bytes, so t_torus - t_rd = M/128 exactly — positive at every
M > 0.

## Run provenance

- sweep id: `8b526718152f3cca84fd9784b4ec148242046c2b5427e1274b85a7bdd85aec45`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_4r_rdoubling_v1.yaml`;
  the sweep manifest is the only reachable execution path to this backend
  today — see the reachability note above)
- sweep manifest: `experiments/sweeps/atlas_4r_rdoubling_v1.yaml`
  (sha256 `80cdf7c809982c2f3ba7090b33494ace9298eb90b624d922c194f9b7a786dbea`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp4.yaml`
  (sha256 `89b3c85f3c1c2d7102fc8df8f328e766bfb0c2a163bd2e283d63bf45728af2a1`)
- topology: `experiments/topologies/rdoubling4_free_params.yaml`
  (sha256 `7558deb402c44af640e5d8e7a8228a52c437d52d626345bc61e606663c3f1865`;
  baseline topology `experiments/topologies/ring4_free_params.yaml` sha256
  `120d0f02a0582bd5f8aa92f53ab692568a28e6ddb5f0f8ca959698a4ca02ebd7`)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `62ab74989ebecb4a8fb618bd6b73d79d9fb062949c9e95b6985eeace68e98242`
  / `a852dd1f4a52b4fe149431837f44870363f2e1f029430b2357d17190916086bc`);
  `tests/determinism/test_sweep_replay.py` 5 passed; full suite 528
  passed; paper-check PASS (15 files, 0 violations).

Catalog: [atlas index](README.md).
