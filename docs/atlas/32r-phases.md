# Atlas cell 32r-phases — rank class 32, algorithm family phase collectives

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The rank-32 mirror of [16r-phases.md](16r-phases.md) (and
[8r-phases.md](8r-phases.md), [4r-phases.md](4r-phases.md)): the
phase-collectives family makes ReduceScatter and AllGather FIRST-CLASS
collectives (backend `analytical_l0_phase_collectives`). At rank class 32
it declares exactly FOUR pairing identities (A-L0P-ALGO, config
`experiments/topologies/phase_collectives32_free_params.yaml` — NEW in this
stage, the rank-32 mirror of the rank-16 config, referencing the two
committed rank-32 fabrics), two per fabric family, with exactly TWO
distinct completion-time identities because within each family the RS and
AG phases are symmetric at equal M:

- **ring family** — `reducescatter_ring` and `allgather_ring` on
  `ring32_free_v1` (assumptions A-L0P-ALGO / A-L0P-MSG / A-L0P-COMP):
  each phase t = 31M/2048 + 6200 ns (31 hops);
- **doubling family** — `reducescatter_recursive_halving` and
  `allgather_recursive_doubling` on `rdoubling32_free_v1` (32 = 2⁵ is a
  power of two, k = log2(32) = 5 steps per phase): each phase
  t = 31M/2048 + 1000 ns. The halving step sends chunks
  {M/2, M/4, M/8, M/16, M/32} and the doubling step
  {M/32, M/16, M/8, M/4, M/2} — mirror sequences, equal-cost phases; this
  is the phase-symmetry note recorded on [32r-doubling.md](32r-doubling.md)
  ("each phase 31M/2048 + 1000 ns"), now executed as first-class ops
  (verified through the backend's own step functions at all 12 sizes).

Undeclared identities, attempted and recorded (never forced): the crossbar
RS/AG phases as first-class ops are rejected by the pairing gate —
re-exercised through the loader on the RANK-32 config during this stage
(`analytical_l0_phase_collectives: pairing collective='allgather',
algorithm='crossbar' is not a capability-declared identity (A-L0P-ALGO);
it is explicitly unsupported`); the index's Recorded-skips entry predicted
exactly this refusal at every rank count, now exercised at rank classes
4, 8, 16 and 32. That identity exists arithmetically only inside the S1
crossbar AllReduce decomposition, phase = 31M/2048 + 200 ns — the third
rung of the per-phase latency ladder below. Overlapped RS/AG phases and
cross-family fabric pairings are likewise different, undeclared
identities.

Execution reachability (structural, carried from 4r/8r/16r-phases;
re-exercised live at rank 32 during this stage): the sweep runner's
registry holds exactly the four AllReduce algorithm ids
(`allreduce_ring`, `allreduce_crossbar`, `allreduce_recursive_doubling`,
`allreduce_torus2d`) — every phase-vehicle id
(`reducescatter_ring`, `allgather_ring`,
`reducescatter_recursive_halving`, `allgather_recursive_doubling`,
`analytical_l0_phase_collectives`) is UNKNOWN to gate 1, so no sweep
manifest can carry a rank-32 phase config either (classified, not fixed;
no src/ change). The RUN path, by contrast, executes this
backend natively (the topology class selects the family), so **24 run
manifests are this cell's execution vehicle** — the mirror image of
recursive-doubling (sweep-reachable/run-unreachable ). This page's
delta columns are therefore computed by this stage (exact Fractions) from
the executed records, not emitted by a runner delta column; the baseline
ladder is the landed 32r-ring sweep (sweep id `d363e9f7…`, its rows
re-pinned against the closed form during this stage's verification,
exact-string-equal at all 12 sizes).

Message-size semantics (A-L0P-MSG): M is the per-rank input for
ReduceScatter and the total gathered size for AllGather, so a phase pair
composes exactly — AllReduce(M) = RS(M) + AG(M), serialized (A-L0P-COMP).
The workload is the W2 Dense TP Prefill shape with tp_size 32, 3 layers x
1 chunk = 3 RS+AG pairs = 6 phase ops per config (the 6-op atlas
convention, now as phase pairs), one workload file per grid point —
every grid size is divisible by 4096, hence by 32, so the divisibility
guard `A-L0P-DIV` never rejects a grid point.

Identity executed (per phase op, message M, ranks r = 32, exact Fractions):

    per-rank wire traffic  T(M, 32)   = (32-1)/32 * M = 31M/32           (all four pairings)
    ring family phase      t(M, 32)   = 31M/32/64 + 31*200 = 31M/2048 + 6200 ns
    doubling family phase  t(M, 32)   = 31M/32/64 + 5*200  = 31M/2048 + 1000 ns
    (baseline, ring AllReduce        = 31M/1024 + 12400 ns — [32r-ring.md](32r-ring.md))

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 32. All
values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell, all visible in the identities:

1. **The wire identity is family-independent and exactly half the
   baseline's.** Every declared phase variant moves T = 31M/32 per rank —
   the module's pinned emerging property (phase algorithms differ only in
   the per-phase latency chain) — which is exactly HALF the ring
   AllReduce's 31M/16: one AllReduce's worth of bytes split over two phase
   ops. Per op the total wire is 31M = (r-1)M; per config (6 ops) 186M.
2. **The ring-family delta is the constant -1/2 — carried at a FOURTH
   rank class.** Both terms of the ring AllReduce halve: bandwidth
   31M/2048 = half of 31M/1024, latency 31L = 6200 = half of 62L =
   12400, so t_ring_phase = t_ring_AR/2 EXACTLY at every M — the
   A-L0P-COMP composition identity read on the grid. The 8-rank page
   predicted the constant survives the rank ladder; it now holds at
   r = 4, 8, 16 and 32.
3. **The doubling-family delta climbs from an exact -57/62 floor toward
   the ring family's -1/2 asymptote — the 16r-phases envelope law landed
   at the fourth rank class.**

       delta_dbl(M) = (t_dbl - t_AR)/t_AR = -(31M/2048 + 11400)/(31M/1024 + 12400)

   is strictly increasing with exact endpoint delta(0) = -57/62 (pure
   latency fact: its chain 5L = 1000 against the baseline's 62L = 12400)
   and large-M limit exactly -1/2 (pure bandwidth fact: identical
   asymptotic bytes — the same -1/2 the ring phases sit at exactly,
   because asymptotically all phase variants move the same 31M/32). The
   envelope law -(2(r-1)-log2 r)/(2(r-1)) deepens -2/3 → -11/14 → -13/15
   → **-57/62** at r = 32 — its own correct evaluation is -(62-5)/62.
   (Prediction-provenance note, recorded honestly: an earlier working note stated the law correctly but evaluated it as
   "-(57-5)/62 = -26/31"; the 5 is subtracted twice there — the quoted
   -26/31 is instead the 32r-doubling AR cell's own envelope
   -(r-1-log2 r)/(r-1), already landed on [32r-doubling.md](32r-doubling.md).
   The executed phase envelope -57/62 is the deeper one, as the phase
   envelope is at every landed rank class, because its latency chain k·L
   is halved once, not twice, against the same 2(r-1)·L baseline.) Grid
   range: -5731/6262 at 4 KiB climbing to -9877/19654 at 64 MiB. At the
   ring's own balance point M* = 409600 B the delta is exactly -22/31
   (ladder -7/12 → -9/14 → -41/60 → -22/31 at the four landed rank
   classes; general form (log2 r - 3(r-1))/(4(r-1))).
4. **The family gap is the constant latency-ladder rung
   (r-1-log2(r))·L = 26L = 5200 ns at every size** — exactly the
   predicted rung — the executed phase-level instance of the
   module's documented per-phase latency ladder at r = 32: ring 31L =
   6200 >= doubling 5L = 1000 >= crossbar L = 200 (the crossbar rung is
   not a declared first-class op — fact above). The doubling phase chain
   5L = 1000 ns is exactly half the 32r-doubling AllReduce's
   2·log2(32)·L = 2000 ns, just as the ring phase's 31L is half the ring
   AllReduce's 62L. Rank-ladder note: the rung ladder 200 → 800 → 2200 →
   5200 ns reads 1L → 3L → 11L → 26L (the law is the rung VALUE
   (r-1-log2 r)·L; it quadruples only on the 4r→8r leg). The per-phase
   chain ladder {L, log2(r)·L, (r-1)·L} is evenly spaced ONLY where
   2·log2(r) = r (r in {2, 4} — {1,2,3}L at rank 4); at r = 32 it reads
   {1, 5, 31}L with gaps 4L, 26L, so r = 4 remains the LAST rank class
   with an arithmetic phase ladder — the SAME condition and verdict as
   the 8r-doubling/16r-doubling midpoint finding, now exercised at a
   fourth rank class.

Balance points (bandwidth term = latency term), extending the 32-rank
transition ladder: the ring phase balances at M = 409600 B — the SAME M
as the ring AllReduce's own beta = lambda point and the 32r-torus
THREE-WAY concurrent crossover ([32r-torus.md](32r-torus.md); halving
both terms of an identity leaves its balance point fixed), so 409600 B is
a three-fold special point of the landed 32-rank atlas — the rank-32
mirror of 204800 B's status at rank 16 (the pending 32r-l05 cell would
test the fourth fold there, delta = +1/2, the rank-independent half-point
that made 51200/102400/204800 four-fold at the lower classes); the
doubling phase balances at M = 2048000/31 ≈ 66064.52 B, identical to the
32r-doubling AllReduce's own transition
([32r-doubling.md](32r-doubling.md)). The transition ladder across landed
32-rank cells now reads {409600/31 (crossbar AR), 2048000/31 (doubling AR
and doubling phase), 409600 (ring AR, ring phase, torus three-way
crossover)} B — in units of the crossbar's own balance, {1, 5, 31} =
{1, log2 r, r-1}, the same transition-ratio law the 32r-doubling page
recorded for the AllReduce chains.

Composition, pinned on the grid from the run records' per-op rows at all
12 sizes: RS(M) + AG(M) per chunk pair sums to 31M/1024 + 12400 (ring
family) — the 32r-ring baseline identity digit-for-digit, cross-checked
against the landed 32r-ring sweep table — and to 31M/1024 + 2000
(doubling family) — the 32r-doubling identity digit-for-digit,
cross-checked against the landed 32r-doubling sweep table. Two phase ops
rebuild each landed AllReduce cell exactly.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}). Ring baseline ladder:
[32r-ring.md](32r-ring.md) (its rows carry delta exactly 0 by
construction). Delta semantics on this page: per-op phase completion vs
per-op ring AllReduce completion at the same payload M under A-L0P-MSG
(the same M reading under which the phases compose into the baseline
identity).

| payload (bytes) | payload (human) | wire B/rank = 31M/32 (exact) | ring phase ns = 31M/2048 + 6200 (exact) | dbl phase ns = 31M/2048 + 1000 (exact) | ring AR ns = 31M/1024 + 12400 | delta ring phase (exact) | delta dbl phase (exact fraction) | delta dbl phase (%) |
|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 3968 | 6262 | 1062 | 12524 | -1/2 | -5731/6262 | -91.5203 |
| 8192 | 8 KiB | 7936 | 6324 | 1124 | 12648 | -1/2 | -2881/3162 | -91.1132 |
| 16384 | 16 KiB | 15872 | 6448 | 1248 | 12896 | -1/2 | -28/31 | -90.3226 |
| 65536 | 64 KiB | 63488 | 7192 | 1992 | 14384 | -1/2 | -1549/1798 | -86.1513 |
| 131072 | 128 KiB | 126976 | 8184 | 2984 | 16368 | -1/2 | -1673/2046 | -81.7693 |
| 262144 | 256 KiB | 253952 | 10168 | 4968 | 20336 | -1/2 | -1921/2542 | -75.5704 |
| 1048576 | 1 MiB | 1015808 | 22072 | 16872 | 44144 | -1/2 | -3409/5518 | -61.7796 |
| 2097152 | 2 MiB | 2031616 | 37944 | 32744 | 75888 | -1/2 | -5393/9486 | -56.8522 |
| 4194304 | 4 MiB | 4063232 | 69688 | 64488 | 139376 | -1/2 | -9361/17422 | -53.7309 |
| 16777216 | 16 MiB | 16252928 | 260152 | 254952 | 520304 | -1/2 | -33169/65038 | -50.9994 |
| 33554432 | 32 MiB | 32505856 | 514104 | 508904 | 1028208 | -1/2 | -64913/128526 | -50.5057 |
| 67108864 | 64 MiB | 65011712 | 1022008 | 1016808 | 2044016 | -1/2 | -9877/19654 | -50.2544 |

The doubling-phase delta column climbs monotonically toward the exact
-1/2 asymptote and never reaches it at finite M (the residual gap is the
constant 5200 ns rung). The structural denominator fact carries from the
lower rank classes: before reduction all three M-dependent 32-rank deltas
— crossbar AR (-12000 over the baseline), doubling AR (-10400), doubling
phase (-(31M/2048 + 11400)) — divide the SAME baseline denominator
31M/1024 + 12400. After reduction the 16r phase/crossbar coincidence
(sharing the reduced denominator at 8 of 12 sizes) does NOT carry to
32r; what carries instead is a doubling-AR relation: the phase delta's
reduced denominator is exactly TWICE the landed doubling-AR cell's at 11
of 12 sizes (the 2 from the halved bandwidth term survives every
reduction there), the lone exception 16 KiB — where BOTH reduce to
denominator 31 (phase -28/31 against doubling-AR -25/31, the same
16-KiB special size the 32r-doubling row recorded for its own -25/31);
the crossbar shares the doubling-AR reduced denominator at 6 sizes
(4 KiB, 64 KiB, 256 KiB, 1 MiB, 4 MiB, 16 MiB) and the phase is exactly
twice that shared denominator at every one of them.

O-CONSERVATION: 0 violations at every size in all 24 records (exact
Fraction self-check of the model's byte accounting, 6 ops per config;
per op, per-rank traffic 31M/32 summed over ranks = 31M = (r-1)M — every
sent chunk received once; e.g. total wire bytes at M = 4096: 761856 =
6 ops x 31 x 4096, exactly half the ring AR baseline config's 1523712 =
6 x 62 x 4096). All 24 records rederived independently from the closed
forms during stage verification (phase rows including the per-step
doubling decomposition, per-op wire and total wire, aggregates, the
composition sums, both delta identities, the constant -1/2 column, the
5200 ns family gap, the monotonicity and envelope of the doubling-phase
delta, and the balance points — all agree exact-string-equal with the
stored `observations.json` files, the landed 32r-ring `table.json`, and
the landed 32r-doubling `table.json`).

Rank-ladder deltas vs the 16-rank phase cell (same free parameters,
closed forms, not measurements): the wire moves 15M/16 → 31M/32 per
rank; the ring-phase constant -1/2 survives unchanged (fact 2); the
doubling-phase envelope deepens -13/15 → **-57/62** =
-(2(r-1)-log2 r)/(2(r-1)) (fact 3), and the 32-rank delta is more
negative than the 16-rank one at every grid size (verified at all 12;
exact ratio law
delta_32/delta_16 = (31M+23347200)(15M+3072000)/((31M+12697600)(15M+5324800)),
exact at every grid point, from 855/806 = (57/62)/(13/15) at M = 0
through 876843/823453 at 4 KiB and the grid peak 2907/2542 at 256 KiB to
the 1 large-M limit), while the doubling AR cell's own envelope reads
-(r-1-log2 r)/(r-1) = -26/31 — the phase envelope is the deeper one at
every landed rank class (fact 3's provenance note); the family gap rung
(r-1-log2 r)·L walks 200 → 800 → 2200 → 5200 ns (the same law as the
doubling-AR cell's 2(r-1-log2 r)·L gap 400 → 1600 → 4400 → 10400 ns);
the delta at the ring's balance point M* reads -7/12 at 4r (51200 B),
-9/14 at 8r (102400 B), -41/60 at 16r (204800 B), -22/31 at 32r
(409600 B).

## Crossover message sizes

**None in this cell — for structural reasons on both comparison axes.**
Within the cell the two distinct identities share the bandwidth term
31M/2048 and differ by the constant 5200 ns, so they are translates of each
other in M: the ring phases are slower at every finite M and the orderings
never swap. Against the ring AllReduce baseline the ring-phase delta is
the constant -1/2 (never changes sign) and the doubling-phase delta is
strictly increasing and bounded inside (-57/62, -1/2) — negative at every
finite M, approaching the ring-phase curve asymptotically but never
reaching or crossing it. Recorded honestly; the rank-class-32 atlas's
non-trivial crossover remains the 32-rank torus cell's three-way
concurrent M = 409600 B ([32r-torus.md](32r-torus.md)) — which is also
this cell's ring-phase balance point (fact 4).

## Run provenance

- execution vehicle: 24 run records through the run path
  (`make run EXP=experiments/atlas/32r_phases/run_atlas_32r_phases_{ring,rd}_{M}_v1.yaml`),
  content-addressed in the append-only evidence store under `results/`
  (git-ignored by design — these ids and the committed manifests are the
  provenance record). First and last grid points per family:

  | family | M = 4096 run id | M = 67108864 run id |
  |---|---|---|
  | ring phases | `fcc510c4…688c1` | `1887c4e2…0ae2db` |
  | doubling phases | `436d4013…73dd8a` | `cf9875dd…1f57b2` |

  (all 24 ids are recoverable by replaying the 24 manifests — the store
  is content-addressed, so identical inputs reproduce identical ids.)
- family/algorithm config (NEW in this stage, the rank-32 mirror of the
  rank-16 config): `experiments/topologies/phase_collectives32_free_params.yaml`
  (sha256 `e42878d45d808d0803a46a61c22a9afcfe08c43ccf1108582bd973f26e826cb8`;
  its four declared pairings load through the backend's own
  `load_phase_algorithm_config`, exercised live during this stage)
- workloads: `experiments/workloads/w2_dense_tp_prefill_tp32_chunk{4096…67108864}.yaml`,
  12 files, one per grid point (e.g. chunk4096 sha256
  `7bec37a172750e9fc2b8efbddf2e6e92174f21d58a2fc7462402d9419aed7458`)
- topologies (committed by the earlier 32-rank cells, unchanged):
  `experiments/topologies/ring32_free_params.yaml` (sha256
  `90e694ecb6a71bc9ac4b050c8c54de506f76346b242e19b7c63712b758337ac2`),
  `experiments/topologies/rdoubling32_free_params.yaml` (sha256
  `ba18470b0f9328ff17b2175dabe4acefed31760053bf1edb4cac0dccf7bdb578`)
- implementation profile:
  `experiments/vertical_slice/profiles/implementation_profile_l0_phase_collectives.yaml`
  (sha256 `1166627d64f72c41b3e3702d306c822aeea9acffaf1f3658e4aea3624db1bb6c`);
  assumptions: `experiments/vertical_slice/assumptions_l0.yaml`;
  claim_id empty in every manifest (zero claim edits)
- baselines: the landed 32r-ring sweep, sweep id
  `d363e9f7ceeb07cd497fdabe4833705729abd81d133f17b97e5d6ac5e9a43fe3`
  ([32r-ring.md](32r-ring.md)); composition cross-check also against the
  landed 32r-doubling sweep, sweep id
  `18aa1a57f69630cd060defcd36cc75cec4248cc1311eacd1f68be9f734278081`
  ([32r-doubling.md](32r-doubling.md))
- code version: 0.1.0; run ids = sha256(canonical run payload)
- determinism bar: ALL 24 manifests rerun immediately — every rerun
  returned the same run id (the store's put is idempotent), and the two
  sampled records' artifacts hash stably (ring 4096: run.json sha256
  `6968d6ad71c1f86dec780746bad144a3d8f559d176478a1e04294405112193a6`,
  observations.json `400b18df416a37d64ee62cff55b01089dab1534aa0633f34d92fd3fe96aea3db`;
  doubling 64 MiB: run.json `21d1c269c8f04b92cf186fca23c54ac9ea086dcc11a5d59f9976d97e6e7012bb`,
  observations.json `84732b3692b4490b74784a65b878844ead26c7f394d1582024fc79b13356c41a`);
  `tests/determinism` 13 passed; full suite 613 passed (13 new
  schema-glob inputs: 12 workloads + the config); paper-check PASS
  (15 files, 0 violations).

Catalog: [atlas index](README.md).
