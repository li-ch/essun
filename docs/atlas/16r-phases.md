# Atlas cell 16r-phases — rank class 16, algorithm family phase collectives

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The rank-16 mirror of [8r-phases.md](8r-phases.md) (and
[4r-phases.md](4r-phases.md)): the phase-collectives family makes
ReduceScatter and AllGather FIRST-CLASS collectives (backend
`analytical_l0_phase_collectives`). At rank class 16 it declares exactly
FOUR pairing identities (A-L0P-ALGO, config
`experiments/topologies/phase_collectives16_free_params.yaml` — NEW in this
stage, the rank-16 mirror of the rank-8 config, referencing the two
committed rank-16 fabrics), two per fabric family, with exactly TWO
distinct completion-time identities because within each family the RS and
AG phases are symmetric at equal M:

- **ring family** — `reducescatter_ring` and `allgather_ring` on
  `ring16_free_v1` (assumptions A-L0P-ALGO / A-L0P-MSG / A-L0P-COMP):
  each phase t = 15M/1024 + 3000 ns (15 hops);
- **doubling family** — `reducescatter_recursive_halving` and
  `allgather_recursive_doubling` on `rdoubling16_free_v1` (16 = 2⁴ is a
  power of two, k = log2(16) = 4 steps per phase): each phase
  t = 15M/1024 + 800 ns. The halving step sends chunks
  {M/2, M/4, M/8, M/16} and the doubling step {M/16, M/8, M/4, M/2} —
  mirror sequences, equal-cost phases; this is the phase-symmetry note
  recorded on [16r-doubling.md](16r-doubling.md), now executed as
  first-class ops (each phase exactly 15M/1024 + 800 ns, verified through
  the backend's own step functions at all 12 sizes).

Undeclared identities, attempted and recorded (never forced): the crossbar
RS/AG phases as first-class ops are rejected by the pairing gate —
re-exercised through the loader on the RANK-16 config during this stage
(`analytical_l0_phase_collectives: pairing collective='allgather',
algorithm='crossbar' is not a capability-declared identity (A-L0P-ALGO);
it is explicitly unsupported`); the index's Recorded-skips entry predicted
exactly this refusal at every rank count, now exercised at rank classes
4, 8 and 16. That identity exists arithmetically only inside the S1
crossbar AllReduce decomposition, phase = 15M/1024 + 200 ns — the third
rung of the per-phase latency ladder below. Overlapped RS/AG phases and
cross-family fabric pairings are likewise different, undeclared
identities.

Execution reachability (structural, carried from 4r-phases and 8r-phases;
re-exercised live at rank 16 during this stage): the sweep runner's
registry holds exactly the four AllReduce algorithm ids
(`allreduce_ring`, `allreduce_crossbar`, `allreduce_recursive_doubling`,
`allreduce_torus2d`) — every phase-vehicle id
(`reducescatter_ring`, `allgather_ring`,
`reducescatter_recursive_halving`, `allgather_recursive_doubling`,
`analytical_l0_phase_collectives`) is UNKNOWN to gate 1, so no sweep
manifest can carry a rank-16 phase config either (classified, not fixed;
no src/ change). The RUN path, by contrast, executes this
backend natively (the topology class selects the family), so **24 run
manifests are this cell's execution vehicle** — the mirror image of
recursive-doubling (sweep-reachable/run-unreachable ). This page's
delta columns are therefore computed by this stage (exact Fractions) from
the executed records, not emitted by a runner delta column; the baseline
ladder is the landed 16r-ring sweep (sweep id `f44e7891…`, its rows
re-pinned against the closed form during this stage's verification,
exact-string-equal at all 12 sizes).

Message-size semantics (A-L0P-MSG): M is the per-rank input for
ReduceScatter and the total gathered size for AllGather, so a phase pair
composes exactly — AllReduce(M) = RS(M) + AG(M), serialized (A-L0P-COMP).
The workload is the W2 Dense TP Prefill shape with tp_size 16, 3 layers x
1 chunk = 3 RS+AG pairs = 6 phase ops per config (the 6-op atlas
convention, now as phase pairs), one workload file per grid point —
every grid size is divisible by 4096, hence by 16, so the divisibility
guard `A-L0P-DIV` never rejects a grid point.

Identity executed (per phase op, message M, ranks r = 16, exact Fractions):

    per-rank wire traffic  T(M, 16)   = (16-1)/16 * M = 15M/16           (all four pairings)
    ring family phase      t(M, 16)   = 15M/16/64 + 15*200 = 15M/1024 + 3000 ns
    doubling family phase  t(M, 16)   = 15M/16/64 + 4*200  = 15M/1024 + 800 ns
    (baseline, ring AllReduce        = 15M/512 + 6000 ns — [16r-ring.md](16r-ring.md))

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 16. All
values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell, all visible in the identities:

1. **The wire identity is family-independent and exactly half the
   baseline's.** Every declared phase variant moves T = 15M/16 per rank —
   the module's pinned emerging property (phase algorithms differ only in
   the per-phase latency chain) — which is exactly HALF the ring
   AllReduce's 15M/8: one AllReduce's worth of bytes split over two phase
   ops. Per op the total wire is 15M = (r-1)M; per config (6 ops) 90M.
2. **The ring-family delta is the constant -1/2 — the 8r-phases
   prediction CONFIRMED at a third rank class.** Both terms of the ring
   AllReduce halve: bandwidth 15M/1024 = half of 15M/512, latency 15L =
   3000 = half of 30L = 6000, so t_ring_phase = t_ring_AR/2 EXACTLY at
   every M — the A-L0P-COMP composition identity read on the grid. The
   8-rank page predicted the constant survives the rank ladder
   ("structurally at every rank count"); it now holds at r = 4, 8 and 16.
3. **The doubling-family delta climbs from an exact -13/15 floor toward
   the ring family's -1/2 asymptote — the 8r-phases envelope prediction
   CONFIRMED, shifted exactly as the general law says.**

       delta_dbl(M) = (t_dbl - t_AR)/t_AR = -(15M/1024 + 5200)/(15M/512 + 6000)

   is strictly increasing with exact endpoint delta(0) = -13/15 (pure
   latency fact: its chain 4L = 800 against the baseline's 30L = 6000)
   and large-M limit exactly -1/2 (pure bandwidth fact: identical
   asymptotic bytes — the same -1/2 the ring phases sit at exactly,
   because asymptotically all phase variants move the same 15M/16). The
   8-rank page's envelope law -(2(r-1)-log2 r)/(2(r-1)) deepens
   -2/3 → -11/14 → **-13/15** at r = 16 — the second named 8r-phases
   prediction, landing exactly. Grid range: -263/306 at 4 KiB climbing to
   -1123/2241 at 64 MiB. At the ring's own balance point M* = 204800 B
   the delta is exactly -41/60 (ladder -7/12 → -9/14 → -41/60 at the
   three landed rank classes; general form
   (log2 r - 3(r-1))/(4(r-1))).
4. **The family gap is the constant latency-ladder rung
   (r-1-log2(r))·L = 11L = 2200 ns at every size**, the executed
   phase-level instance of the module's documented per-phase latency
   ladder at r = 16: ring 15L = 3000 >= doubling 4L = 800 >= crossbar
   L = 200 (the crossbar rung is not a declared first-class op — fact
   above). The doubling phase chain 4L = 800 ns is exactly half the
   16r-doubling AllReduce's 2·log2(16)·L = 1600 ns, just as the ring
   phase's 15L is half the ring AllReduce's 30L. Rank-ladder note: the
   rung ladder 200 → 800 → 2200 ns quadruples 4r → 8r but only
   multiplies by 11/4 from 8r to 16r — the law is the rung VALUE
   (r-1-log2 r)·L, and the 8r page's "quadruples while r doubles" was the
   r ∈ {4, 8} coincidence of it. The per-phase chain ladder
   {L, log2(r)·L, (r-1)·L} is evenly spaced ONLY where 2·log2(r) = r
   (r in {2, 4} — {1,2,3}L at rank 4); at r = 16 it reads {1, 4, 15}L
   with gaps 3L, 11L, so r = 4 remains the LAST rank class with an
   arithmetic phase ladder — the SAME condition and verdict as the
   8r-doubling/16r-doubling midpoint finding, now exercised at a third
   rank class.

Balance points (bandwidth term = latency term), extending the 16-rank
transition ladder: the ring phase balances at M = 204800 B — the SAME M
as the ring AllReduce's own beta = lambda point and the 16r-torus
THREE-WAY concurrent crossover ([16r-torus.md](16r-torus.md); halving
both terms of an identity leaves its balance point fixed), so 204800 B is
a three-fold special point of the 16-rank atlas — the rank-16 mirror of
102400 B's status at rank 8; the doubling phase balances at
M = 819200/15 ≈ 54613.33 B, identical to the 16r-doubling AllReduce's
own transition ([16r-doubling.md](16r-doubling.md)). The transition
ladder across landed 16-rank cells now reads {204800/15 (crossbar AR),
819200/15 (doubling AR and doubling phase), 204800 (ring AR, ring phase,
torus three-way crossover)} B.

Composition, pinned on the grid from the run records' per-op rows at all
12 sizes: RS(M) + AG(M) per chunk pair sums to 15M/512 + 6000 (ring
family) — the 16r-ring baseline identity digit-for-digit, cross-checked
against the landed 16r-ring sweep table — and to 15M/512 + 1600 (doubling
family) — the 16r-doubling identity digit-for-digit, cross-checked against
the landed 16r-doubling sweep table. Two phase ops rebuild each landed
AllReduce cell exactly.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}). Ring baseline ladder:
[16r-ring.md](16r-ring.md) (its rows carry delta exactly 0 by
construction). Delta semantics on this page: per-op phase completion vs
per-op ring AllReduce completion at the same payload M under A-L0P-MSG
(the same M reading under which the phases compose into the baseline
identity).

| payload (bytes) | payload (human) | wire B/rank = 15M/16 (exact) | ring phase ns = 15M/1024 + 3000 (exact) | dbl phase ns = 15M/1024 + 800 (exact) | ring AR ns = 15M/512 + 6000 | delta ring phase (exact) | delta dbl phase (exact fraction) | delta dbl phase (%) |
|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 3840 | 3060 | 860 | 6120 | -1/2 | -263/306 | -85.9477 |
| 8192 | 8 KiB | 7680 | 3120 | 920 | 6240 | -1/2 | -133/156 | -85.2564 |
| 16384 | 16 KiB | 15360 | 3240 | 1040 | 6480 | -1/2 | -68/81 | -83.9506 |
| 65536 | 64 KiB | 61440 | 3960 | 1760 | 7920 | -1/2 | -7/9 | -77.7778 |
| 131072 | 128 KiB | 122880 | 4920 | 2720 | 9840 | -1/2 | -89/123 | -72.3577 |
| 262144 | 256 KiB | 245760 | 6840 | 4640 | 13680 | -1/2 | -113/171 | -66.0819 |
| 1048576 | 1 MiB | 983040 | 18360 | 16160 | 36720 | -1/2 | -257/459 | -55.9913 |
| 2097152 | 2 MiB | 1966080 | 33720 | 31520 | 67440 | -1/2 | -449/843 | -53.2622 |
| 4194304 | 4 MiB | 3932160 | 64440 | 62240 | 128880 | -1/2 | -833/1611 | -51.7070 |
| 16777216 | 16 MiB | 15728640 | 248760 | 246560 | 497520 | -1/2 | -3137/6219 | -50.4422 |
| 33554432 | 32 MiB | 31457280 | 494520 | 492320 | 989040 | -1/2 | -6209/12363 | -50.2224 |
| 67108864 | 64 MiB | 62914560 | 986040 | 983840 | 1972080 | -1/2 | -1123/2241 | -50.1116 |

The doubling-phase delta column climbs monotonically toward the exact
-1/2 asymptote and never reaches it at finite M (the residual gap is the
constant 2200 ns rung). The structural denominator fact carries from the
8-rank cell: before reduction all three M-dependent 16-rank deltas —
crossbar AR (-5600 over the baseline), doubling AR (-4400), doubling
phase (-(15M/1024 + 5200)) — divide the SAME baseline denominator
15M/512 + 6000. After reduction the phase delta SHARES its denominator
with the landed crossbar cell's at 8 of 12 sizes (16 KiB through 32 MiB,
e.g. -68/81 against -70/81, -113/171 against -70/171); the exceptions are
4/8 KiB (the phase denominator exactly twice the crossbar's: 306 vs 153,
156 vs 78) and 64 KiB/64 MiB (the phase fraction reduces further: -7/9
vs -70/99; -1123/2241 vs -70/24651 — at 64 MiB the phase numerator's
factor 11 cancels where the crossbar's gcd 80 does not, the SAME 11 the
16r-doubling AR cell found in its -5/2241).

O-CONSERVATION: 0 violations at every size in all 24 records (exact
Fraction self-check of the model's byte accounting, 6 ops per config;
per op, per-rank traffic 15M/16 summed over ranks = 15M = (r-1)M — every
sent chunk received once; e.g. total wire bytes at M = 4096: 368640 =
6 ops x 15 x 4096, exactly half the ring AR baseline config's 737280 =
6 x 30 x 4096). All 24 records rederived independently from the closed
forms during stage verification (phase rows including the per-step
doubling decomposition, per-op wire and total wire, aggregates, the
composition sums, both delta identities, the constant -1/2 column, the
2200 ns family gap, the monotonicity and envelope of the doubling-phase
delta, and the balance points — all agree exact-string-equal with the
stored `observations.json` files, the landed 16r-ring `table.json`, and
the landed 16r-doubling `table.json`).

Rank-ladder deltas vs the 8-rank phase cell (same free parameters,
closed forms, not measurements): the wire moves 7M/8 → 15M/16 per rank;
the ring-phase constant -1/2 survives unchanged (fact 2); the
doubling-phase envelope deepens -11/14 → **-13/15** =
-(2(r-1)-log2 r)/(2(r-1)) (fact 3), and the 16-rank delta is more
negative than the 8-rank one at every grid size (verified at all 12;
exact ratio law
delta_16/delta_8 = (15M+5324800)(7M+716800)/((15M+3072000)(7M+1126400)),
exact at every grid point, from 182/165 = (13/15)/(11/14) at M = 0
through 23933/21573 ≈ 1.109 at 4 KiB and the grid peak 23674/20459 ≈
1.157 at 128 KiB to the 1 large-M limit), while the doubling AR cell's
own envelope reads -(r-1-log2 r)/(r-1) = -11/15 — the phase envelope is
the deeper one at every landed rank class because its latency chain k·L
is halved once, not twice, against the same 2(r-1)·L baseline; the
family gap rung (r-1-log2 r)·L walks 200 → 800 → 2200 ns (the same law
as the doubling-AR cell's 2(r-1-log2 r)·L gap 400 → 1600 → 4400 ns); the
delta at the ring's balance point M* reads -7/12 at 4r (51200 B), -9/14
at 8r (102400 B), -41/60 at 16r (204800 B).

## Crossover message sizes

**None in this cell — for structural reasons on both comparison axes.**
Within the cell the two distinct identities share the bandwidth term
15M/1024 and differ by the constant 2200 ns, so they are translates of each
other in M: the ring phases are slower at every finite M and the orderings
never swap. Against the ring AllReduce baseline the ring-phase delta is
the constant -1/2 (never changes sign) and the doubling-phase delta is
strictly increasing and bounded inside (-13/15, -1/2) — negative at every
finite M, approaching the ring-phase curve asymptotically but never
reaching or crossing it. Recorded honestly; the rank-class-16 atlas's
non-trivial crossover remains the 16-rank torus cell's three-way
concurrent M = 204800 B ([16r-torus.md](16r-torus.md)) — which is also
this cell's ring-phase balance point (fact 4).

## Run provenance

- execution vehicle: 24 run records through the run path
  (`make run EXP=experiments/atlas/16r_phases/run_atlas_16r_phases_{ring,rd}_{M}_v1.yaml`),
  content-addressed in the append-only evidence store under `results/`
  (git-ignored by design — these ids and the committed manifests are the
  provenance record). First and last grid points per family:

  | family | M = 4096 run id | M = 67108864 run id |
  |---|---|---|
  | ring phases | `243fcbcc…84f8ec` | `18e457bf…d5014` |
  | doubling phases | `49550fac…71ebcc` | `0d51424b…752dd0` |

  (all 24 ids are recoverable by replaying the 24 manifests — the store
  is content-addressed, so identical inputs reproduce identical ids.)
- family/algorithm config (NEW in this stage, the rank-16 mirror of the
  pre-tracked rank-8 config): `experiments/topologies/phase_collectives16_free_params.yaml`
  (sha256 `c0ab047cefdb2ec48aace8cb1c81d05d8538f36f5e83a87e645e6e7bdef41596`;
  its four declared pairings load through the backend's own
  `load_phase_algorithm_config`, exercised live during this stage)
- workloads: `experiments/workloads/w2_dense_tp_prefill_tp16_chunk{4096…67108864}.yaml`,
  12 files, one per grid point (e.g. chunk4096 sha256
  `afe75948a43feda7de181c9da87ebe6542c9481d39b0ded36392a6ddde8564de`)
- topologies (committed by the earlier 16-rank cells, unchanged):
  `experiments/topologies/ring16_free_params.yaml` (sha256
  `f973784db47ebc461da1111eecdcb44accc73c06a06c0daeb86d9e46cab8a119`),
  `experiments/topologies/rdoubling16_free_params.yaml` (sha256
  `2c0643a5eec0dde061e53be07c5dc65b9a600b8d85bacef90a150c179281d679`)
- implementation profile:
  `experiments/vertical_slice/profiles/implementation_profile_l0_phase_collectives.yaml`
  (sha256 `1166627d64f72c41b3e3702d306c822aeea9acffaf1f3658e4aea3624db1bb6c`);
  assumptions: `experiments/vertical_slice/assumptions_l0.yaml`;
  claim_id empty in every manifest (zero claim edits)
- baselines: the landed 16r-ring sweep, sweep id
  `f44e7891ddb65e5c875a24496b37047354c41aae02ee89b76e6e85a6bfbb69b8`
  ([16r-ring.md](16r-ring.md)); composition cross-check also against the
  landed 16r-doubling sweep, sweep id
  `7ac3f27aaf6f49dde6fc506f903bc218ce81535bf4fd363f7527f6c1e0a14b95`
  ([16r-doubling.md](16r-doubling.md))
- code version: 0.1.0; run ids = sha256(canonical run payload)
- determinism bar: ALL 24 manifests rerun immediately — every rerun
  returned the same run id (the store's put is idempotent), and the two
  sampled records' artifacts hash stably (ring 4096: run.json sha256
  `322da844199b2b279017d6c08795693e5f5e1b0ecfc6fd1241601015049f919a`,
  observations.json `048dd944b825ed58947ae771ceabcee98b78608010ecc6e64a4b131641266c44`;
  doubling 64 MiB: run.json `20f360b68184264241caa400906896a429327a9c030d2aa2038dc58139e326f3`,
  observations.json `584c4c327b031612c752dc14164cfd679945ca1d95a9537651cbe710488a99fb`);
  `tests/determinism` 13 passed; full suite 574 passed (13 new
  schema-glob inputs: 12 workloads + the config); paper-check PASS
  (15 files, 0 violations).

Catalog: [atlas index](README.md).
