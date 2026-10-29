# Atlas cell 8r-phases — rank class 8, algorithm family phase collectives

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The rank-8 mirror of [4r-phases.md](4r-phases.md): the phase-collectives
family makes ReduceScatter and AllGather FIRST-CLASS collectives (backend
`analytical_l0_phase_collectives`). At rank class 8 it declares exactly
FOUR pairing identities (A-L0P-ALGO, config
`experiments/topologies/phase_collectives8_free_params.yaml` — pre-tracked
with the rank-8 fabrics, not modified by this stage), two per fabric
family, with exactly TWO distinct completion-time identities because
within each family the RS and AG phases are symmetric at equal M:

- **ring family** — `reducescatter_ring` and `allgather_ring` on
  `ring8_free_v1` (assumptions A-L0P-ALGO / A-L0P-MSG / A-L0P-COMP):
  each phase t = 7M/512 + 1400 ns (7 hops);
- **doubling family** — `reducescatter_recursive_halving` and
  `allgather_recursive_doubling` on `rdoubling8_free_v1` (8 = 2³ is a
  power of two, k = log2(8) = 3 steps per phase): each phase
  t = 7M/512 + 600 ns. The halving step sends chunks {M/2, M/4, M/8} and
  the doubling step {M/8, M/4, M/2} — mirror sequences, equal-cost
  phases; this is the phase-symmetry note recorded on
  [8r-doubling.md](8r-doubling.md), now executed as first-class ops.

Undeclared identities, attempted and recorded (never forced): the crossbar
RS/AG phases as first-class ops are rejected by the pairing gate —
re-exercised through the loader on the RANK-8 config during this stage
(`analytical_l0_phase_collectives: pairing collective='allgather',
algorithm='crossbar' is not a capability-declared identity (A-L0P-ALGO);
it is explicitly unsupported`); the index's Recorded-skips entry predicted
exactly this refusal at every rank count. That identity exists
arithmetically only inside the S1 crossbar AllReduce decomposition,
phase = 7M/512 + 200 ns — the third rung of the per-phase latency ladder
below. Overlapped RS/AG phases and cross-family fabric pairings are
likewise different, undeclared identities.

Execution reachability (structural, carried from 4r-phases): the sweep
runner registers only the four AllReduce algorithm ids and its grid
expands W1 AllReduce ops, which this backend rejects by capability
contract — the finding is rank-independent, so no sweep manifest can
carry a rank-8 phase config either (classified, not fixed; no src/
change). The RUN path, by contrast, executes this backend
natively (the topology class selects the family), so **24 run manifests
are this cell's execution vehicle** — the mirror image of
recursive-doubling (sweep-reachable/run-unreachable ). This page's
delta columns are therefore computed by this stage (exact Fractions) from
the executed records, not emitted by a runner delta column; the baseline
ladder is the landed 8r-ring sweep (sweep id `ab15366f…`, its rows
re-pinned against the closed form during this stage's verification,
exact-string-equal at all 12 sizes).

Message-size semantics (A-L0P-MSG): M is the per-rank input for
ReduceScatter and the total gathered size for AllGather, so a phase pair
composes exactly — AllReduce(M) = RS(M) + AG(M), serialized (A-L0P-COMP).
The workload is the W2 Dense TP Prefill shape with tp_size 8, 3 layers x
1 chunk = 3 RS+AG pairs = 6 phase ops per config (the 6-op atlas
convention, now as phase pairs), one workload file per grid point —
every grid size is divisible by 4096, hence by 8, so the divisibility
guard `A-L0P-DIV` never rejects a grid point.

Identity executed (per phase op, message M, ranks r = 8, exact Fractions):

    per-rank wire traffic  T(M, 8)   = (8-1)/8 * M = 7M/8            (all four pairings)
    ring family phase      t(M, 8)   = 7M/8/64 + 7*200 = 7M/512 + 1400 ns
    doubling family phase  t(M, 8)   = 7M/8/64 + 3*200 = 7M/512 + 600 ns
    (baseline, ring AllReduce        = 7M/256 + 2800 ns — [8r-ring.md](8r-ring.md))

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 8. All
values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell, all visible in the identities:

1. **The wire identity is family-independent and exactly half the
   baseline's.** Every declared phase variant moves T = 7M/8 per rank —
   the module's pinned emerging property (phase algorithms differ only in
   the per-phase latency chain) — which is exactly HALF the ring
   AllReduce's 7M/4: one AllReduce's worth of bytes split over two phase
   ops. Per op the total wire is 7M = (r-1)M; per config (6 ops) 42M.
2. **The ring-family delta is the constant -1/2.** Both terms of the ring
   AllReduce halve: bandwidth 7M/512 = half of 7M/256, latency 7L = 1400
   = half of 14L = 2800, so t_ring_phase = t_ring_AR/2 EXACTLY at every M
   — the A-L0P-COMP composition identity read on the grid (symmetric
   phases at equal M are each exactly half the composed AllReduce). This
   is the first non-trivial constant delta column in the rank-class-8
   atlas (the baseline's 0 is constant by construction), and the constant
   survives the rank ladder — the same -1/2 held at rank 4
   ([4r-phases.md](4r-phases.md)), structurally at every rank count.
3. **The doubling-family delta climbs from an exact -11/14 floor toward
   the ring family's -1/2 asymptote.**

       delta_dbl(M) = (t_dbl - t_AR)/t_AR = -(7M/512 + 2200)/(7M/256 + 2800)

   is strictly increasing with exact endpoint delta(0) = -11/14 (pure
   latency fact: its chain 3L = 600 against the baseline's 14L = 2800)
   and large-M limit exactly -1/2 (pure bandwidth fact: identical
   asymptotic bytes — the same -1/2 the ring phases sit at exactly,
   because asymptotically all phase variants move the same 7M/8). Grid
   range: -141/182 at 4 KiB climbing to -114963/229726 at 64 MiB. At the
   ring's own balance point M* = 102400 B the delta is exactly -9/14.
4. **The family gap is the constant latency-ladder rung
   (r-1-log2(r))·L = 800 ns at every size**, the executed phase-level
   instance of the module's documented per-phase latency ladder at r = 8:
   ring 7L = 1400 >= doubling 3L = 600 >= crossbar L = 200 (the crossbar
   rung is not a declared first-class op — fact above). The doubling
   phase chain 3L = 600 ns is exactly half the 8r-doubling AllReduce's
   2·log2(8)·L = 1200 ns, just as the ring phase's 7L is half the ring
   AllReduce's 14L. Rank-ladder note: the per-phase chain ladder
   {L, log2(r)·L, (r-1)·L} is evenly spaced ONLY where 2·log2(r) = r
   (r in {2, 4} — {1,2,3}L at rank 4); at r = 8 it reads {1, 3, 7}L with
   gaps 2L, 4L, so r = 4 is the LAST rank class with an arithmetic phase
   ladder — the SAME condition and verdict as the 8r-doubling midpoint
   finding ([8r-doubling.md](8r-doubling.md)).

Balance points (bandwidth term = latency term), extending the 8-rank
transition ladder: the ring phase balances at M = 102400 B — the SAME M
as the ring AllReduce's own beta = lambda point and the 8r-torus
crossover ([8r-torus.md](8r-torus.md); halving both terms of an identity
leaves its balance point fixed), so 102400 B is now a three-fold special
point of the 8-rank atlas — the exact mirror of 51200 B's status at rank
4; the doubling phase balances at M = 307200/7 ≈ 43885.71 B, identical
to the 8r-doubling AllReduce's own transition
([8r-doubling.md](8r-doubling.md)). The transition ladder across landed
8-rank cells now reads {102400/7 (crossbar AR), 307200/7 (doubling AR
and doubling phase), 102400 (ring AR, ring phase, torus crossover)} B.

Composition, pinned on the grid from the run records' per-op rows at all
12 sizes: RS(M) + AG(M) per chunk pair sums to 7M/256 + 2800 (ring
family) — the 8r-ring baseline identity digit-for-digit, cross-checked
against the landed 8r-ring sweep table — and to 7M/256 + 1200 (doubling
family) — the 8r-doubling identity digit-for-digit, cross-checked against
the landed 8r-doubling sweep table. Two phase ops rebuild each landed
AllReduce cell exactly.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}). Ring baseline ladder:
[8r-ring.md](8r-ring.md) (its rows carry delta exactly 0 by
construction). Delta semantics on this page: per-op phase completion vs
per-op ring AllReduce completion at the same payload M under A-L0P-MSG
(the same M reading under which the phases compose into the baseline
identity).

| payload (bytes) | payload (human) | wire B/rank = 7M/8 (exact) | ring phase ns = 7M/512 + 1400 (exact) | dbl phase ns = 7M/512 + 600 (exact) | ring AR ns = 7M/256 + 2800 | delta ring phase (exact) | delta dbl phase (exact fraction) | delta dbl phase (%) |
|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 3584 | 1456 | 656 | 2912 | -1/2 | -141/182 | -77.4725 |
| 8192 | 8 KiB | 7168 | 1512 | 712 | 3024 | -1/2 | -289/378 | -76.4550 |
| 16384 | 16 KiB | 14336 | 1624 | 824 | 3248 | -1/2 | -303/406 | -74.6305 |
| 65536 | 64 KiB | 57344 | 2296 | 1496 | 4592 | -1/2 | -387/574 | -67.4216 |
| 131072 | 128 KiB | 114688 | 3192 | 2392 | 6384 | -1/2 | -499/798 | -62.5313 |
| 262144 | 256 KiB | 229376 | 4984 | 4184 | 9968 | -1/2 | -723/1246 | -58.0257 |
| 1048576 | 1 MiB | 917504 | 15736 | 14936 | 31472 | -1/2 | -2067/3934 | -52.5419 |
| 2097152 | 2 MiB | 1835008 | 30072 | 29272 | 60144 | -1/2 | -3859/7518 | -51.3301 |
| 4194304 | 4 MiB | 3670016 | 58744 | 57944 | 117488 | -1/2 | -7443/14686 | -50.6809 |
| 16777216 | 16 MiB | 14680064 | 230776 | 229976 | 461552 | -1/2 | -28947/57694 | -50.1733 |
| 33554432 | 32 MiB | 29360128 | 460152 | 459352 | 920304 | -1/2 | -57619/115038 | -50.0869 |
| 67108864 | 64 MiB | 58720256 | 918904 | 918104 | 1837808 | -1/2 | -114963/229726 | -50.0435 |

The doubling-phase delta column climbs monotonically toward the exact
-1/2 asymptote and never reaches it at finite M (the residual gap is the
constant 800 ns rung). The structural denominator fact carries from the
4-rank cell but its 4-rank COINCIDENCE does not: before reduction all
three M-dependent 8-rank deltas — crossbar AR (-2400 over the baseline),
doubling AR (-1600), doubling phase (-(7M/512 + 2200)) — divide the SAME
baseline denominator 7M/256 + 2800; at rank 4 the reduced denominators
additionally came out digit-for-digit identical to the crossbar cell's,
an artifact of the rank-4 numerator arithmetic that does not reproduce
at r = 8 (e.g. -141/182 against the crossbar's -75/91 at 4 KiB).

O-CONSERVATION: 0 violations at every size in all 24 records (exact
Fraction self-check of the model's byte accounting, 6 ops per config;
per op, per-rank traffic 7M/8 summed over ranks = 7M = (r-1)M — every
sent chunk received once; e.g. total wire bytes at M = 4096: 172032 =
6 ops x 7 x 4096). All 24 records rederived independently from the closed
forms during stage verification (phase rows including the per-step
doubling decomposition, per-op wire and total wire, aggregates, the
composition sums, both delta identities, the constant -1/2 column, the
800 ns family gap, the monotonicity and envelope of the doubling-phase
delta, and the balance points — all agree exact-string-equal with the
stored `observations.json` files, the landed 8r-ring `table.json`, and
the landed 8r-doubling `table.json`).

Rank-ladder deltas vs the 4-rank phase cell (same free parameters,
closed forms, not measurements): the wire moves 3M/4 → 7M/8 per rank;
the ring-phase constant -1/2 survives unchanged (fact 2); the
doubling-phase envelope deepens -2/3 → -11/14 =
-(2(r-1)-log2 r)/(2(r-1)), and the 8-rank delta is more negative than
the 4-rank one at every grid size (verified at all 12; ratio
(141·81)/(182·53) ≈ 1.184 at 4 KiB → 1 in the large-M limit), while the
doubling AR cell's own envelope reads -(r-1-log2 r)/(r-1) — the phase
envelope is the deeper one at both rank classes because its latency
chain k·L is halved once, not twice, against the same 2(r-1)·L baseline;
the family gap rung (r-1-log2 r)·L quadruples 200 → 800 ns while r
doubles (the same law as the doubling-AR cell's 2(r-1-log2 r)·L gap
400 → 1600 ns); the delta at the ring's balance point M* reads -7/12 at
4r (51200 B) against -9/14 at 8r (102400 B).

## Crossover message sizes

**None in this cell — for structural reasons on both comparison axes.**
Within the cell the two distinct identities share the bandwidth term
7M/512 and differ by the constant 800 ns, so they are translates of each
other in M: the ring phases are slower at every finite M and the orderings
never swap. Against the ring AllReduce baseline the ring-phase delta is
the constant -1/2 (never changes sign) and the doubling-phase delta is
strictly increasing and bounded inside (-11/14, -1/2) — negative at every
finite M, approaching the ring-phase curve asymptotically but never
reaching or crossing it. Recorded honestly; the rank-class-8 atlas's
non-trivial crossover remains the 8-rank torus cell's M = 102400 B
([8r-torus.md](8r-torus.md)) — which is also this cell's ring-phase
balance point (fact 4).

## Run provenance

- execution vehicle: 24 run records through the run path
  (`make run EXP=experiments/atlas/8r_phases/run_atlas_8r_phases_{ring,rd}_{M}_v1.yaml`),
  content-addressed in the append-only evidence store under `results/`
  (git-ignored by design — these ids and the committed manifests are the
  provenance record). First and last grid points per family:

  | family | M = 4096 run id | M = 67108864 run id |
  |---|---|---|
  | ring phases | `2143a25b…6ebf94` | `571d261c…924450` |
  | doubling phases | `20b9bbca…c4c1e2` | `366ea21f…6422c4` |

  (all 24 ids are recoverable by replaying the 24 manifests — the store
  is content-addressed, so identical inputs reproduce identical ids.)
- family/algorithm config (pre-tracked, unchanged by this stage):
  `experiments/topologies/phase_collectives8_free_params.yaml`
  (sha256 `8b5db353134583051f7878711ac20485d4ada66d2b9b30fc9a7a682743622dac`)
- workloads: `experiments/workloads/w2_dense_tp_prefill_tp8_chunk{4096…67108864}.yaml`,
  12 files, one per grid point (e.g. chunk4096 sha256
  `e864b9f435110e4caac665ef8b4da8b2c242af213ec83a813b0f8083659b92c8`)
- topologies (committed by the earlier 8-rank cells, unchanged):
  `experiments/topologies/ring8_free_params.yaml` (sha256
  `34b8aed485253e332423f625412f4b5820f7ddd7999fc4e3c762c79c02f2de84`),
  `experiments/topologies/rdoubling8_free_params.yaml` (sha256
  `455892bcbd5182626b717446ade4a3c104d7acdbb9b191e1b7f25247d7a45bab`)
- implementation profile:
  `experiments/vertical_slice/profiles/implementation_profile_l0_phase_collectives.yaml`
  (sha256 `1166627d64f72c41b3e3702d306c822aeea9acffaf1f3658e4aea3624db1bb6c`);
  assumptions: `experiments/vertical_slice/assumptions_l0.yaml`;
  claim_id empty in every manifest (zero claim edits)
- baselines: the landed 8r-ring sweep, sweep id
  `ab15366f5a0b81f0d6b7b879ea603db0a5352ec2e1b649a2577bd8e8f4176ba2`
  ([8r-ring.md](8r-ring.md)); composition cross-check also against the
  landed 8r-doubling sweep, sweep id
  `7a8d1348d4d25f8bac52644e3eb822aea13a2ee99c81e7466c9e4631ab243f97`
  ([8r-doubling.md](8r-doubling.md))
- code version: 0.1.0; run ids = sha256(canonical run payload)
- determinism bar: ALL 24 manifests rerun immediately — every rerun
  returned the same run id (the store's put is idempotent), and the two
  sampled records' artifacts hash stably (ring 4096: run.json sha256
  `5927d6352e76b1cb1c49453fee098f61227331a197d08779e4c23e34d803cdcc`,
  observations.json `8ecc8c912f095f72677ad76b1214cf6206adb2dfd389fc18883b0cef1bb6a5b8`;
  doubling 64 MiB: run.json `d94e36fc4f0acc3ba3b3794c7fb506b3dfa69fc64580326269bdc7e1eccaffbe`,
  observations.json `0b3c405ee11bf974e74e7d9471af67737524ca824678e51cb547e917bc32d1ac`);
  `tests/determinism` 13 passed; full suite 555 passed (12 new
  schema-gated workload inputs); paper-check PASS (15 files, 0 violations).

Catalog: [atlas index](README.md).
