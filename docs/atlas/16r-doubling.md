# Atlas cell 16r-doubling — rank class 16, algorithm family recursive-doubling

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The recursive-doubling family is declared for **power-of-two rank counts
only** (modeling assumption A-L0D-POW2). Rank class 16 = 2⁴ is a power of
two, so the family **applies** — there is no skip to record. The family
has no factorizations to sweep (unlike torus): the partner schedule is
fully determined (rank XOR 2^(i-1) at step i, k = log2(16) = 4 steps per
phase), so this cell has exactly ONE declared L0 identity:
`allreduce_recursive_doubling` over a fully-connected exchange fabric
(backend `analytical_l0_recursive_doubling`; serialized steps and phases
A-L0D-STEP, power-of-two schedule A-L0D-POW2, divisibility A-L0D-DIV —
every grid size is divisible by 4096, hence by 16, so the halving chunks
M/2^i and doubling chunks 2^(i-1)*M/r stay integral at every grid point).
This is the rank-16 mirror of [4r-doubling.md](4r-doubling.md) and
[8r-doubling.md](8r-doubling.md).

Execution reachability (structural note, unchanged from the 4- and 8-rank
cells): this backend is run-manifest-unreachable — the run path's
collective-capability gate cannot admit two-word algorithm suffixes (a recorded
reachability finding) — so the sweep runner, which
registers the algorithm id directly, is the execution vehicle for this
cell. Classified, not fixed; no src/ change was made.

Identity executed (per op, message M, ranks r = 16, k = log2(16) = 4,
exact Fractions; recursive-halving reduce phase + recursive-doubling
broadcast phase, serialized, one partner exchange per step):

    per-rank wire traffic  T(M, 16) = 2*(16-1)/16 * M = 15M/8
    completion time        t(M, 16) = 2*(16-1)/16 * M/B + 2*log2(16)*L = 15M/512 + 1600 ns   (B = 64 bytes/ns, L = 200 ns)

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 16, W1
Dense TP Decode shape (layers 2 x steps 3 = 6 AllReduce ops per config).
All values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell (ring baseline: T = 15M/8,
t = 15M/512 + 6000 — [16r-ring.md](16r-ring.md)):

1. **The traffic identity equals the ring's.** T(M, 16) = 15M/8 is the same
   per-rank wire-byte identity as the 16-rank ring
   ([16r-ring.md](16r-ring.md)) and the 16-rank single-port crossbar
   ([16r-crossbar.md](16r-crossbar.md)) — the module documents that all
   three L0 designs differ ONLY in the latency chain (ring 2*(r-1)*L =
   30L, recursive doubling 2*log2(r)*L = 8L, pipelined crossbar 2L). The
   wire column below is digit-for-digit the 16r-ring ladder's (verified
   against the landed 16r-ring sweep table); under this L0 model the
   doubling schedule buys no traffic change over the ring at 16 ranks
   either, only a shorter hop chain.
2. **The entire delta is a latency-term fact.** The bandwidth terms are
   identical (15M/512); the completion times differ only in the constant —
   8L = 1600 ns for doubling (two phases x four steps x L) versus
   2*(r-1)*L = 30L = 6000 ns for the ring. Hence the exact delta identity

       delta(M) = (t_rd - t_ring) / t_ring = -4400 / (15M/512 + 6000) = -2252800 / (15*(M + 204800))

   which is negative at every finite M and monotonically approaches 0
   from below (large-M limit: identical bandwidth-bound identities). The
   small-M envelope deepens from the 8-rank cell's -4/7 to **-11/15** —
   in general -(r-1-log2(r))/(r-1) — and the 16-rank delta is more
   negative than the 8-rank delta at every grid size (exact ratio law
   delta_16/delta_8 = (77/30)*(M + 102400)/(M + 204800), climbing
   77/59 at 4 KiB through 77/60 at M = 0 toward its 77/30 large-M limit),
   because the ring's chain more than doubles 14L -> 30L while the
   doubling chain grows only 6L -> 8L: the gap 2*(r-1-log2(r))*L goes
   1600 -> 4400 ns while r doubles. At the ring identity's own balance
   point M* = L*B*r = 204800 B the delta is exactly **-11/30** (general
   -(r-1-log2(r))/(2*(r-1)); the crossbar cell read -7/15 = -14/30 at the
   same point, [16r-crossbar.md](16r-crossbar.md)).
3. **The 8-rank cell's ratio law PREDICTED this cell's delta — and the
   prediction lands exactly.** [8r-doubling.md](8r-doubling.md) fact 3
   derived the general law: the doubling delta is exactly
   (r-1-log2(r))/(r-2) times the crossbar cell's delta at every size
   (ladder 1/2 at r = 4, 2/3 at r = 8, then **11/14 at r = 16**, 9/10 at
   r = 32, 59/62 at r = 64, tending to 1). Verified here against the
   landed 16r-crossbar sweep table: delta_rd = (11/14)*delta_xb holds
   EXACTLY at all 12 grid sizes (e.g. -110/153 vs -140/153 at 4 KiB;
   -55/24651-reduced vs -70/24651 at 64 MiB) — the atlas's first rank-class
   ratio prediction to be confirmed on fresh executions at a third
   consecutive rank class. The same law kills the midpoint pattern at
   this rank class as it did at 8: midpoint status needs 2*log2(r) = r,
   which among powers of two holds only at r = 2 and r = 4; at r = 16 the
   doubling chain 8L sits strictly BELOW the midpoint 16L — closer to the
   crossbar — so t_rd < (t_ring + t_xbar)/2 at every size (verified at
   all 12 grid sizes).
4. **The doubling chain breaks strictly below BOTH torus chains — the
   family's clean sweep of the middle of the ladder.** The landed 16-rank
   chain ladder reads crossbar 2L = 400 < doubling 8L = 1600 < torus 4x4
   12L = 2400 < torus 2x8 16L = 3200 < ring 30L = 6000 ns. At r = 4 the
   doubling chain TIED the torus 2x2 chain (both 4L); at r = 8 it broke
   strictly below the single 2x4 chain; at r = 16 it is below BOTH torus
   factorizations at every M > 0, verified against both landed 16r-torus
   tables: t_torus2x8 - t_rd = 7M/512 + 1600 and t_torus4x4 - t_rd =
   9M/512 + 800, each positive at every M — both torus factorizations pay
   MORE wire than doubling at this rank class (11M/4 and 3M vs 15M/8 per
   rank) AND a longer chain, so there is no size at which either catches
   up. Against the crossbar, t_rd - t_xbar = 2*(log2(r)-1)*L = 6L =
   1200 ns at every size — the relation exercised live at
   rank 8, now at rank 16.

Phase symmetry, visible in the step decomposition at r = 16: the reduce
phase sends chunks {M/2, M/4, M/8, M/16} (halving) and the broadcast phase
sends {M/16, M/8, M/4, M/2} (doubling) — mirror sequences, each phase
costing exactly 15M/1024 + 800 ns, so the two phases are equal-cost at
this rank count too (the property is general: both phases sum to
(r-1)/r*M/B + k*L; verified at all 12 grid sizes through the backend's own
step functions).

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by the rank count 16, so the divisibility guard `A-L0D-DIV` never rejects
a grid point). Ring baseline ladder: [16r-ring.md](16r-ring.md) (its rows
carry delta exactly 0 by construction; the sweep grid carries the baseline
config so the runner can match per-size deltas — see provenance below).

| payload (bytes) | payload (human) | wire B/rank = 15M/8 (exact) | doubling CCT ns = 15M/512 + 1600 (exact) | ring CCT ns = 15M/512 + 6000 | delta vs ring baseline (exact fraction) | delta (%) |
|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 7680 | 1720 | 6120 | -110/153 | -71.8954 |
| 8192 | 8 KiB | 15360 | 1840 | 6240 | -55/78 | -70.5128 |
| 16384 | 16 KiB | 30720 | 2080 | 6480 | -55/81 | -67.9012 |
| 65536 | 64 KiB | 122880 | 3520 | 7920 | -5/9 | -55.5556 |
| 131072 | 128 KiB | 245760 | 5440 | 9840 | -55/123 | -44.7154 |
| 262144 | 256 KiB | 491520 | 9280 | 13680 | -55/171 | -32.1637 |
| 1048576 | 1 MiB | 1966080 | 32320 | 36720 | -55/459 | -11.9826 |
| 2097152 | 2 MiB | 3932160 | 63040 | 67440 | -55/843 | -6.5243 |
| 4194304 | 4 MiB | 7864320 | 124480 | 128880 | -55/1611 | -3.4140 |
| 16777216 | 16 MiB | 31457280 | 493120 | 497520 | -55/6219 | -0.8844 |
| 33554432 | 32 MiB | 62914560 | 984640 | 989040 | -55/12363 | -0.4449 |
| 67108864 | 64 MiB | 125829120 | 1967680 | 1972080 | -5/2241 | -0.2231 |

The delta column climbs monotonically from -110/153 toward the exact 0
asymptote — every row is the pure latency-term fact (eight hop latencies
against the ring's thirty at identical wire bytes), shrinking relative to
a completion time whose bandwidth term grows without bound.

O-CONSERVATION: 0 violations at every size (exact Fraction self-check of
the model's byte accounting, 6 ops per config; per op, per-rank traffic
15M/8 summed over ranks = 30M = 2*(r-1)*M — every sent byte received once
by the step partner; e.g. total wire bytes at M = 4096: 737280 = 6 ops x
30 x 4096, digit-for-digit the 16r-ring and 16r-crossbar totals, consistent
with the equal traffic identity). All 12 rows rederived independently
from the closed forms during stage verification (doubling rows, baseline
rows, both delta-identity forms, the gap laws t_ring - t_rd = 4400 and
t_rd - t_xbar = 1200 ns, the 11/14-of-crossbar-delta relation against the
landed 16r-crossbar table, the no-midpoint inequality, the
delta_16/delta_8 ratio law (77/30)*(M + 102400)/(M + 204800) against the
landed 8r-doubling table, both torus ordering inequalities against the
landed 16r-torus tables, the phase-symmetry sums, and the conservation
totals agree exact-string-equal with the runner's `table.json`).

An arithmetic aside of the reduction (mirroring the 16r-crossbar note):
because 80 divides both -4400 and 15M/512 + 6000 at every grid size from
8 KiB up (and never at 4 KiB), the reduced delta reads exactly -55/d for
eleven consecutive grid points — with exactly TWO further reductions
where d shares the factor 11 with 55: at 64 KiB, d = 99 = 9*11, the delta
reduces to **-5/9**; at 64 MiB, d = 24651 = 27*11*83, it reduces to
**-5/2241**. The crossbar cell's "-70/d from 16 KiB up" ladder shares
denominators with this one wherever both stay reduced (its 8 KiB row
reduces further to -35/39; its 64 KiB and 64 MiB rows stay -70/99 and
-70/24651 because 70 shares no factor with d).

## Crossover message sizes

**None — for the same structural reason as the 4- and 8-rank doubling
cells, not a sampling one.** Within this cell there is exactly one
declared identity, and against the ring baseline the two completion-time
identities have the SAME bandwidth term (15M/512) and differ only by a
constant (1600 ns vs 6000 ns), so the two curves are translates of each
other in M: the doubling identity has the smaller completion time at
every finite M, the delta -4400/(15M/512 + 6000) never changes sign, and
no payload size exists where the orderings swap. Recorded honestly; the
crossover question stays non-trivial only in cells whose bandwidth
coefficients differ (the 16-rank torus cell is the example, with its
three-way concurrent point at M = 204800 B). (Arithmetic fact of the
single identity, not a crossover: its bandwidth term 15M/512 equals its
latency term 1600 at M = 819200/15 ≈ 54613.33 B, between the 16 KiB and
64 KiB grid points — exactly 4x the crossbar's own transition 204800/15
≈ 13653.33 B and 1/4 of the ring's balance point 204800 B, so the chain
ladder {2L, 8L, 30L} places its transitions in exact 1 : 4 : 15 ratio.)

## Run provenance

- sweep id: `7ac3f27aaf6f49dde6fc506f903bc218ce81535bf4fd363f7527f6c1e0a14b95`
  (content-addressed under `results/sweeps/`, git-ignored by design;
  reproduce with `make sweep EXP=experiments/sweeps/atlas_16r_rdoubling_v1.yaml`;
  the sweep manifest is the only reachable execution path to this backend
  today — see the reachability note above)
- sweep manifest: `experiments/sweeps/atlas_16r_rdoubling_v1.yaml`
  (sha256 `3c31afbf68e5cf7582f9d194ed3286aa6216f5527d48eabf0f5fb7ca702ed206`;
  the grid carries the ring baseline config `c0000-allreduce_ring-…` at
  every size — its delta rows are exactly 0 — because the runner requires
  the baseline in-grid to match deltas per payload size)
- workload: `experiments/workloads/w1_dense_tp_decode_tp16.yaml`
  (sha256 `1602fd4b10fe9ac9b81de3aa7d6a92830e115547b8fb948e3c46f11a81c0fc99`,
  the same file the 16r-ring/16r-crossbar/16r-torus cells used)
- topology: `experiments/topologies/rdoubling16_free_params.yaml`
  (sha256 `2c0643a5eec0dde061e53be07c5dc65b9a600b8d85bacef90a150c179281d679`,
  new in this stage — the rank-16 mirror of rdoubling4/rdoubling8_free_params,
  same B and L; baseline topology `experiments/topologies/ring16_free_params.yaml`
  sha256 `f973784db47ebc461da1111eecdcb44accc73c06a06c0daeb86d9e46cab8a119`,
  the 16r-ring cell's own file)
- code version: 0.1.0; sweep id = sha256(canonical manifest + code version)
- determinism bar: immediate rerun of the same manifest produced the same
  sweep id and byte-identical `table.json` / `table.md`
  (sha256 `4e95f1424f43fba69d3b409eed98c84fc09f800ce8b41df4fdaf0f9a854f74f5`
  / `6abb1fb8cdc0b8337740d73c532746e2b9e79fef6184ed55f79fa62e19e15ded`);
  `tests/determinism` 13 passed; full suite 561 passed (one above the
  16r-torus baseline 560: the schema test's glob picks up the new topology
  file); paper-check PASS.

Catalog: [atlas index](README.md).
