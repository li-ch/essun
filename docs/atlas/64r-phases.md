# Atlas cell 64r-phases — rank class 64, algorithm family phase collectives

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The rank-64 mirror of [32r-phases.md](32r-phases.md) (and
[16r-phases.md](16r-phases.md), [8r-phases.md](8r-phases.md),
[4r-phases.md](4r-phases.md)): the phase-collectives family makes
ReduceScatter and AllGather FIRST-CLASS collectives (backend
`analytical_l0_phase_collectives`). At rank class 64 it declares exactly
FOUR pairing identities (A-L0P-ALGO, config
`experiments/topologies/phase_collectives64_free_params.yaml` — NEW in this
stage, the rank-64 mirror of the rank-32 config, referencing the two
committed rank-64 fabrics), two per fabric family, with exactly TWO
distinct completion-time identities because within each family the RS and
AG phases are symmetric at equal M:

- **ring family** — `reducescatter_ring` and `allgather_ring` on
  `ring64_free_v1` (assumptions A-L0P-ALGO / A-L0P-MSG / A-L0P-COMP):
  each phase t = 63M/4096 + 12600 ns (63 hops);
- **doubling family** — `reducescatter_recursive_halving` and
  `allgather_recursive_doubling` on `rdoubling64_free_v1` (64 = 2⁶ is a
  power of two, k = log2(64) = 6 steps per phase): each phase
  t = 63M/4096 + 1200 ns. The halving step sends chunks
  {M/2, M/4, M/8, M/16, M/32, M/64} and the doubling step
  {M/64, M/32, M/16, M/8, M/4, M/2} — mirror sequences, equal-cost
  phases; this is the phase-symmetry note recorded on
  [64r-doubling.md](64r-doubling.md) ("each phase 63M/4096 + 1200 ns"),
  now executed as first-class ops (verified through the backend's own
  step functions at all 12 sizes).

Undeclared identities, attempted and recorded (never forced): the crossbar
RS/AG phases as first-class ops are rejected by the pairing gate —
re-exercised through the loader on the RANK-64 config during this stage
(`analytical_l0_phase_collectives: pairing collective='allgather',
algorithm='crossbar' is not a capability-declared identity (A-L0P-ALGO);
it is explicitly unsupported`); the index's Recorded-skips entry predicted
exactly this refusal at every rank count, now exercised at rank classes
4, 8, 16, 32 and 64. That identity exists arithmetically only inside the S1
crossbar AllReduce decomposition, phase = 63M/4096 + 200 ns — the third
rung of the per-phase latency ladder below. Overlapped RS/AG phases and
cross-family fabric pairings are likewise different, undeclared
identities.

Execution reachability (structural, carried from 4r/8r/16r/32r-phases;
re-exercised live at rank 64 during this stage): the sweep runner's
registry holds exactly the four AllReduce algorithm ids
(`allreduce_ring`, `allreduce_crossbar`, `allreduce_recursive_doubling`,
`allreduce_torus2d`) — every phase-vehicle id
(`reducescatter_ring`, `allgather_ring`,
`reducescatter_recursive_halving`, `allgather_recursive_doubling`,
`analytical_l0_phase_collectives`) is UNKNOWN to gate 1 (a rank-64 phase
grid was refused explicitly: `unknown algorithm(s) ['reducescatter_ring'];
registered: ['allreduce_crossbar', 'allreduce_recursive_doubling',
'allreduce_ring', 'allreduce_torus2d']`), so no sweep manifest can carry a
rank-64 phase config either (classified, not fixed; no src/ change). The RUN path, by contrast, executes this backend natively (the
topology class selects the family), so **24 run manifests are this cell's
execution vehicle** — the mirror image of recursive-doubling
(sweep-reachable/run-unreachable ). This page's delta columns are
therefore computed by this stage (exact Fractions) from the executed
records, not emitted by a runner delta column; the baseline ladder is the
landed 64r-ring sweep (sweep id `91450af5…`, its rows re-pinned against
the closed form during this stage's verification, exact-string-equal at
all 12 sizes).

Message-size semantics (A-L0P-MSG): M is the per-rank input for
ReduceScatter and the total gathered size for AllGather, so a phase pair
composes exactly — AllReduce(M) = RS(M) + AG(M), serialized (A-L0P-COMP).
The workload is the W2 Dense TP Prefill shape with tp_size 64, 3 layers x
1 chunk = 3 RS+AG pairs = 6 phase ops per config (the 6-op atlas
convention, now as phase pairs), one workload file per grid point —
every grid size is divisible by 4096, hence by 64, so the divisibility
guard `A-L0P-DIV` never rejects a grid point.

Identity executed (per phase op, message M, ranks r = 64, exact Fractions):

    per-rank wire traffic  T(M, 64)   = (64-1)/64 * M = 63M/64           (all four pairings)
    ring family phase      t(M, 64)   = 63M/64/64 + 63*200 = 63M/4096 + 12600 ns
    doubling family phase  t(M, 64)   = 63M/64/64 + 6*200  = 63M/4096 + 1200 ns
    (baseline, ring AllReduce        = 63M/2048 + 25200 ns — [64r-ring.md](64r-ring.md))

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 64. All
values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell, all visible in the identities:

1. **The wire identity is family-independent and exactly half the
   baseline's.** Every declared phase variant moves T = 63M/64 per rank —
   the module's pinned emerging property (phase algorithms differ only in
   the per-phase latency chain) — which is exactly HALF the ring
   AllReduce's 63M/32: one AllReduce's worth of bytes split over two phase
   ops. Per op the total wire is 63M = (r-1)M; per config (6 ops) 378M.
2. **The ring-family delta is the constant -1/2 — carried at a FIFTH
   rank class, exactly as the landed law predicts.** Both terms of the
   ring AllReduce halve: bandwidth 63M/4096 = half of 63M/2048, latency
   63L = 12600 = half of 126L = 25200, so t_ring_phase = t_ring_AR/2
   EXACTLY at every M — the A-L0P-COMP composition identity read on the
   grid (the ring-phase time column is digit-for-digit half the landed
   64r-ring ladder's). The 8-rank page predicted the constant survives
   the rank ladder; it now holds at r = 4, 8, 16, 32 and 64.
3. **The doubling-family delta climbs from an exact -20/21 floor toward
   the ring family's -1/2 asymptote — the envelope law landed at the
   fifth rank class at its own correct evaluation.**

       delta_dbl(M) = (t_dbl - t_AR)/t_AR = -(63M/4096 + 24000)/(63M/2048 + 25200)

   is strictly increasing with exact endpoint delta(0) = -20/21 (pure
   latency fact: its chain 6L = 1200 against the baseline's 126L = 25200)
   and large-M limit exactly -1/2 (pure bandwidth fact: identical
   asymptotic bytes — the same -1/2 the ring phases sit at exactly,
   because asymptotically all phase variants move the same 63M/64). The
   envelope law -(2(r-1)-log2 r)/(2(r-1)) deepens -2/3 → -11/14 → -13/15
   → -57/62 → **-20/21** at r = 64 — its own correct evaluation is
   -(126-6)/126 = -120/126. (Derivation note, recorded honestly per the
   working note's instruction to derive rather than trust: the law
   subtracts log2 r ONCE from the doubled chain 2(r-1) = 126, giving
   -120/126 = -20/21; the 64r-doubling AR cell's own envelope
   -(r-1-log2 r)/(r-1) = -57/63 = **-19/21** is the adjacent, SHALLOWER
   fraction — the phase envelope is the deeper one at every landed rank
   class, because its latency chain k·L is halved once, not twice,
   against the same 2(r-1)·L baseline.) Grid range: -8021/8442 at 4 KiB
   climbing to -22004/43533 at 64 MiB. At the ring's own balance point
   M* = 819200 B the delta is exactly -61/84 (ladder -7/12 → -9/14 →
   -41/60 → -22/31 → -61/84 at the five landed rank classes; general
   form (log2 r - 3(r-1))/(4(r-1))).
4. **The family gap is the constant latency-ladder rung
   (r-1-log2(r))·L = 57L = 11400 ns at every size** — exactly the rung
   the working note named, evaluated from the landed law — the
   executed phase-level instance of the module's documented per-phase
   latency ladder at r = 64: ring 63L = 12600 >= doubling 6L = 1200 >=
   crossbar L = 200 (the crossbar rung is not a declared first-class op —
   fact above). The doubling phase chain 6L = 1200 ns is exactly half the
   64r-doubling AllReduce's 2·log2(64)·L = 2400 ns, just as the ring
   phase's 63L is half the ring AllReduce's 126L. Rank-ladder note: the
   rung ladder 200 → 800 → 2200 → 5200 → 11400 ns reads 1L → 3L → 11L →
   26L → 57L (the law is the rung VALUE (r-1-log2 r)·L; it quadruples
   only on the 4r→8r leg). The per-phase chain ladder
   {L, log2(r)·L, (r-1)·L} is evenly spaced ONLY where 2·log2(r) = r
   (r in {2, 4} — {1,2,3}L at rank 4); at r = 64 it reads {1, 6, 63}L
   with gaps 5L, 57L, so r = 4 remains the LAST rank class with an
   arithmetic phase ladder — the SAME condition and verdict as the
   8r-doubling/16r-doubling midpoint finding, now exercised at a fifth
   rank class.

Balance points (bandwidth term = latency term), extending the 64-rank
transition ladder: the ring phase balances at M = 819200 B — the SAME M
as the ring AllReduce's own beta = lambda point and the 64r-torus
FOUR-WAY concurrent crossover ([64r-torus.md](64r-torus.md); halving
both terms of an identity leaves its balance point fixed), so 819200 B is
a three-fold special point of the landed 64-rank atlas (the pending 64r-l05
cell would test the fourth fold there, delta = +1/2, the rank-independent
half-point that made 51200/102400/204800/409600 four-fold at the lower
classes); the doubling phase balances at M = 4915200/63 ≈ 78019.05 B,
identical to the 64r-doubling AllReduce's own transition
([64r-doubling.md](64r-doubling.md)). The transition ladder across landed
64-rank cells now reads {819200/63 (crossbar AR), 4915200/63 (doubling AR
and doubling phase), 819200 (ring AR, ring phase, torus four-way
crossover)} B — in units of the crossbar's own balance, {1, 6, 63} =
{1, log2 r, r-1}, the same transition-ratio law the 16r/32r pages
recorded for the AllReduce chains, now with the phase cells riding their
AR twins at a third consecutive rank class.

Composition, pinned on the grid from the run records' per-op rows at all
12 sizes: RS(M) + AG(M) per chunk pair sums to 63M/2048 + 25200 (ring
family) — the 64r-ring baseline identity digit-for-digit, cross-checked
exact-string against the landed 64r-ring sweep table — and to
63M/2048 + 2400 (doubling family) — the 64r-doubling identity
digit-for-digit, cross-checked exact-string against the landed
64r-doubling sweep table. Two phase ops rebuild each landed AllReduce
cell exactly.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}). Ring baseline ladder:
[64r-ring.md](64r-ring.md) (its rows carry delta exactly 0 by
construction). Delta semantics on this page: per-op phase completion vs
per-op ring AllReduce completion at the same payload M under A-L0P-MSG
(the same M reading under which the phases compose into the baseline
identity).

| payload (bytes) | payload (human) | wire B/rank = 63M/64 (exact) | ring phase ns = 63M/4096 + 12600 (exact) | dbl phase ns = 63M/4096 + 1200 (exact) | ring AR ns = 63M/2048 + 25200 | delta ring phase (exact) | delta dbl phase (exact fraction) | delta dbl phase (%) |
|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 4032 | 12663 | 1263 | 25326 | -1/2 | -8021/8442 | -95.0130 |
| 8192 | 8 KiB | 8064 | 12726 | 1326 | 25452 | -1/2 | -4021/4242 | -94.7902 |
| 16384 | 16 KiB | 16128 | 12852 | 1452 | 25704 | -1/2 | -2021/2142 | -94.3511 |
| 65536 | 64 KiB | 64512 | 13608 | 2208 | 27216 | -1/2 | -521/567 | -91.8871 |
| 131072 | 128 KiB | 129024 | 14616 | 3216 | 29232 | -1/2 | -542/609 | -88.9984 |
| 262144 | 256 KiB | 258048 | 16632 | 5232 | 33264 | -1/2 | -584/693 | -84.2713 |
| 1048576 | 1 MiB | 1032192 | 28728 | 17328 | 57456 | -1/2 | -44/63 | -69.8413 |
| 2097152 | 2 MiB | 2064384 | 44856 | 33456 | 89712 | -1/2 | -1172/1869 | -62.7073 |
| 4194304 | 4 MiB | 4128768 | 77112 | 65712 | 154224 | -1/2 | -1844/3213 | -57.3918 |
| 16777216 | 16 MiB | 16515072 | 270648 | 259248 | 541296 | -1/2 | -5876/11277 | -52.1061 |
| 33554432 | 32 MiB | 33030144 | 528696 | 517296 | 1057392 | -1/2 | -11252/22029 | -51.0781 |
| 67108864 | 64 MiB | 66060288 | 1044792 | 1033392 | 2089584 | -1/2 | -22004/43533 | -50.5456 |

The doubling-phase delta column climbs monotonically toward the exact
-1/2 asymptote and never reaches it at finite M (the residual gap is the
constant 11400 ns rung). The structural denominator fact carries from the
lower rank classes: before reduction all three M-dependent 64-rank deltas
— crossbar AR (-24800 over the baseline), doubling AR (-22800), doubling
phase (-(63M/4096 + 24000)) — divide the SAME baseline denominator
63M/2048 + 25200. After reduction the 32r relation between the phase and
doubling-AR cells (phase denominator exactly twice at 11 of 12 sizes)
INVERTS here: the phase's reduced denominator is exactly TWICE the landed
doubling-AR cell's at 4/8/16 KiB and EQUALS it at the other nine sizes —
and at this rank class BOTH cells share one special full reduction, the
1 MiB row: phase -44/63 against doubling-AR -25/63, denominators exactly
r-1 = 63 (the 32-rank analog read -28/31 vs -25/31 at its 16-KiB point;
the -25/63 side was recorded on [64r-doubling.md](64r-doubling.md)). The
crossbar's nine-row -1550/d ladder shares NO reduced denominator with the
phase cell at 64r (0 of 12 sizes; the 16r phase/crossbar 8-of-12
coincidence stays dead at 32r and 64r).

O-CONSERVATION: 0 violations at every size in all 24 records (exact
Fraction self-check of the model's byte accounting, 6 ops per config;
per op, per-rank traffic 63M/64 summed over ranks = 63M = (r-1)M — every
sent chunk received once; e.g. total wire bytes at M = 4096: 1548288 =
6 ops x 63 x 4096, exactly half the ring AR baseline config's 3096576 =
6 x 126 x 4096). All 24 records rederived independently from the closed
forms during stage verification (2,472 per-record field checks — phase
rows including the per-step doubling decomposition, per-op wire and
total wire, aggregates, the composition sums — plus 60 exact-string
cross-table checks against the landed 64r-ring and 64r-doubling sweep
tables, both delta identities, the constant -1/2 column, the 11400 ns
family gap, the monotonicity and envelope of the doubling-phase delta,
the balance points, and the ratio law below against the published 32r
column — all agree exact-string-equal with the stored `observations.json`
files and both landed `table.json` files).

Rank-ladder deltas vs the 32-rank phase cell (same free parameters,
closed forms, not measurements): the wire moves 31M/32 → 63M/64 per
rank; the ring-phase constant -1/2 survives unchanged (fact 2); the
doubling-phase envelope deepens -57/62 → **-20/21** =
-(2(r-1)-log2 r)/(2(r-1)) (fact 3), and the 64-rank delta is more
negative than the 32-rank one at every grid size (verified at all 12;
exact ratio law
delta_64/delta_32 = (63M+98304000)(62M+25395200)/((126M+103219200)(31M+23347200)),
exact at every grid point, from 1240/1197 = (20/21)/(57/62) at M = 0
through 25113751/24190551 at 4 KiB and the grid peak 242792/214767 at
1 MiB — the peak moves 256 KiB → 1 MiB, bracketing the doubling-phase
balance — to the 1 large-M limit), while the doubling AR cell's own
envelope reads -(r-1-log2 r)/(r-1) = -19/21 — the phase envelope is the
deeper one at every landed rank class (fact 3's derivation note); the
family gap rung (r-1-log2 r)·L walks 200 → 800 → 2200 → 5200 → 11400 ns
(the same law as the doubling-AR cell's 2(r-1-log2 r)·L gap 400 → 1600 →
4400 → 10400 → 22800 ns); the delta at the ring's balance point M* reads
-7/12 at 4r (51200 B), -9/14 at 8r (102400 B), -41/60 at 16r (204800 B),
-22/31 at 32r (409600 B), -61/84 at 64r (819200 B).

## Crossover message sizes

**None in this cell — for structural reasons on both comparison axes.**
Within the cell the two distinct identities share the bandwidth term
63M/4096 and differ by the constant 11400 ns, so they are translates of each
other in M: the ring phases are slower at every finite M and the orderings
never swap. Against the ring AllReduce baseline the ring-phase delta is
the constant -1/2 (never changes sign) and the doubling-phase delta is
strictly increasing and bounded inside (-20/21, -1/2) — negative at every
finite M, approaching the ring-phase curve asymptotically but never
reaching or crossing it. Recorded honestly; the rank-class-64 atlas's
non-trivial crossover remains the 64-rank torus cell's four-way
concurrent M = 819200 B ([64r-torus.md](64r-torus.md)) — which is also
this cell's ring-phase balance point (fact 4).

## Run provenance

- execution vehicle: 24 run records through the run path
  (`make run EXP=experiments/atlas/64r_phases/run_atlas_64r_phases_{ring,rd}_{M}_v1.yaml`),
  content-addressed in the append-only evidence store under `results/`
  (git-ignored by design — these ids and the committed manifests are the
  provenance record). First and last grid points per family:

  | family | M = 4096 run id | M = 67108864 run id |
  |---|---|---|
  | ring phases | `107edbd9…e6f94e` | `f1dc70c1…af763e` |
  | doubling phases | `6bb6fa90…f71b77` | `494bc231…884dc3` |

  (all 24 ids are recoverable by replaying the 24 manifests — the store
  is content-addressed, so identical inputs reproduce identical ids.)
- family/algorithm config (NEW in this stage, the rank-64 mirror of the
  rank-32 config): `experiments/topologies/phase_collectives64_free_params.yaml`
  (sha256 `2473a82f6f61f8ea77feea37593402b85dff739ca79f588eaa39bdda567f8a7a`;
  its four declared pairings load through the backend's own
  `load_phase_algorithm_config`, exercised live during this stage)
- workloads: `experiments/workloads/w2_dense_tp_prefill_tp64_chunk{4096…67108864}.yaml`,
  12 files, one per grid point (e.g. chunk4096 sha256
  `46591ee9da8c9175cdf6f468566e13ef460c434f7b4fc290e738929512698753`)
- topologies (committed by the earlier 64-rank cells, unchanged):
  `experiments/topologies/ring64_free_params.yaml` (sha256
  `28b187beb2220eebd3d05ab29e969d49badd517ffdc764b5627607211c34f42b`),
  `experiments/topologies/rdoubling64_free_params.yaml` (sha256
  `b01e8947848c6bbb0aaa50bfd771ab89b358579e35310a2c2f095e31bace0807`)
- implementation profile:
  `experiments/vertical_slice/profiles/implementation_profile_l0_phase_collectives.yaml`
  (sha256 `1166627d64f72c41b3e3702d306c822aeea9acffaf1f3658e4aea3624db1bb6c`);
  assumptions: `experiments/vertical_slice/assumptions_l0.yaml`;
  claim_id empty in every manifest (zero claim edits)
- baselines: the landed 64r-ring sweep, sweep id
  `91450af575d38617f0d31292333ec71b75b317f57482ac823df9b4f0d941b34d`
  ([64r-ring.md](64r-ring.md)); composition cross-check also against the
  landed 64r-doubling sweep, sweep id
  `488df890736cdf0726029b44439cd90791d7d039ac2c926b9385dc1b369856c1`
  ([64r-doubling.md](64r-doubling.md))
- code version: 0.1.0; run ids = sha256(canonical run payload)
- determinism bar: ALL 24 manifests rerun immediately — every rerun
  returned the same run id (the store's put is idempotent), and the two
  sampled records' artifacts hash stably (ring 4096: run.json sha256
  `0e1688c6c9ff65e59a002c2fa1e25478050595c63232d65c4a8f05cbac49777f`,
  observations.json `edda87f815090b0a83e696a7ebe23df608bcfb5c3d0973e1fe773f8941578e79`;
  doubling 64 MiB: run.json `53d118550d711ff92b01a3a6af1f36452f95205eaba1e9fd51aaf01ec40bc986`,
  observations.json `4eb6b2f9ba306440090c53ac8eb7f948b73f4f3c4d3bc42db32db3e9fcb3df00`);
  `tests/determinism` 13 passed; full suite 687 passed at stage time
  (pre-stage 674 measured with this stage's inputs removed; +13
  schema-glob inputs: 12 workloads + the config); paper-check PASS
  (15 files, 0 violations).

Catalog: [atlas index](README.md).
