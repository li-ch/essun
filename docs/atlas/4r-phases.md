# Atlas cell 4r-phases — rank class 4, algorithm family phase collectives

Status: **PROPOSED** (atlas content).
Evidence level **E0 only**: every number on this page is the output of a
closed-form L0 analytical identity under explicit free parameters. Nothing
here is measured on hardware, no value is standard-derived, and no claim or
label elsewhere upgrades from this page. Deltas are arithmetic facts of the
identities (same workload shape, same payload size), not performance
comparisons.

## What this cell contains

The phase-collectives family makes ReduceScatter and AllGather FIRST-CLASS
collectives (backend `analytical_l0_phase_collectives`). At rank class 4 it
declares exactly FOUR pairing identities (A-L0P-ALGO, config
`experiments/topologies/phase_collectives4_free_params.yaml`), two per
fabric family, with exactly TWO distinct completion-time identities because
within each family the RS and AG phases are symmetric at equal M:

- **ring family** — `reducescatter_ring` and `allgather_ring` on
  `ring4_free_v1` (assumptions A-L0P-ALGO / A-L0P-MSG / A-L0P-COMP):
  each phase t = 3M/256 + 600 ns;
- **doubling family** — `reducescatter_recursive_halving` and
  `allgather_recursive_doubling` on `rdoubling4_free_v1` (4 = 2² is a power
  of two, k = log2(4) = 2 steps per phase): each phase t = 3M/256 + 400 ns.

Undeclared identities, attempted and recorded (never forced): the crossbar
RS/AG phases as first-class ops are rejected by the pairing gate —
`analytical_l0_phase_collectives: pairing collective='allgather',
algorithm='crossbar' is not a capability-declared identity (A-L0P-ALGO); it
is explicitly unsupported` (live attempt through the loader; that identity
exists arithmetically only inside the S1 crossbar AllReduce decomposition,
phase = 3M/256 + 200 ns — see the latency ladder below; recorded in the
index's Recorded skips). Overlapped RS/AG phases and cross-family fabric
pairings are likewise different, undeclared identities.

Execution reachability (structural note, the mirror of the recorded reachability finding):
the sweep runner registers only the four AllReduce algorithm ids and its
grid expands W1 AllReduce ops, which this backend rejects by capability
contract — a sweep manifest naming a phase id fails the gate explicitly
(live attempt:
`unknown algorithm(s) ['reducescatter_ring']; registered:
['allreduce_crossbar', 'allreduce_recursive_doubling', 'allreduce_ring',
'allreduce_torus2d']`), and the landed golden asserts the backend's refusal
of `allreduce` ops. The RUN path, by contrast, executes this
backend natively (the topology class selects the family; the W2 workload's
bare `reducescatter`/`allgather` names pass the capability gate through the
single-word-suffix entries), so **24 run manifests are this cell's
execution vehicle** — 4-rank doubling was sweep-reachable/run-unreachable
; 4-rank phases are run-reachable/sweep-unreachable. Classified, not
fixed; no src/ change. This page's delta columns are therefore computed by
this stage (exact Fractions) from the executed records, not emitted by a
runner delta column; the baseline ladder is the landed 4r-ring sweep
(sweep id `a7688bb8…`, its rows re-pinned against the closed form during
this stage's verification, exact-string-equal).

Message-size semantics (A-L0P-MSG): M is the per-rank input for
ReduceScatter and the total gathered size for AllGather, so a phase pair
composes exactly — AllReduce(M) = RS(M) + AG(M), serialized (A-L0P-COMP).
The workload is the W2 Dense TP Prefill shape with 3 layers x 1 chunk =
3 RS+AG pairs = 6 phase ops per config (the W1 cells' 6-op convention,
now as phase pairs), one workload file per grid point.

Identity executed (per phase op, message M, ranks r = 4, exact Fractions):

    per-rank wire traffic  T(M, 4)   = (4-1)/4 * M = 3M/4          (all four pairings)
    ring family phase      t(M, 4)   = 3M/4/64 + 3*200 = 3M/256 + 600 ns
    doubling family phase  t(M, 4)   = 3M/4/64 + 2*200 = 3M/256 + 400 ns
    (baseline, ring AllReduce        = 3M/128 + 1200 ns — [4r-ring.md](4r-ring.md))

Free parameters (equal across every config in this cell, and equal to the
other atlas rank classes): B = 64 bytes/ns, L = 200 ns, ranks = 4. All
values are free parameters or model arithmetic — none is measured or
standard-derived.

Four arithmetic facts drive the whole cell, all visible in the identities:

1. **The wire identity is family-independent and exactly half the
   baseline's.** Every declared phase variant moves T = 3M/4 per rank —
   the module's pinned emerging property (phase algorithms differ only in
   the per-phase latency chain) — which is exactly HALF the ring
   AllReduce's 3M/2: one AllReduce's worth of bytes split over two phase
   ops. Per op the total wire is 3M = (r-1)M; per config (6 ops) 18M.
2. **The ring-family delta is the constant -1/2.** Both terms of the ring
   AllReduce halve: bandwidth 3M/256 = half of 3M/128, latency 3L = 600 =
   half of 6L = 1200, so t_ring_phase = t_ring_AR/2 EXACTLY at every M —
   the A-L0P-COMP composition identity read on the grid (symmetric phases
   at equal M are each exactly half the composed AllReduce). This is the
   only 4-rank cell so far whose delta column is a constant.
3. **The doubling-family delta climbs from an exact -2/3 floor toward the
   ring family's -1/2 asymptote.**

       delta_dbl(M) = (t_dbl - t_AR)/t_AR = -(3M/256 + 800)/(3M/128 + 1200)

   is strictly increasing with exact endpoint delta(0) = -2/3 (pure
   latency fact: its chain 2L = 400 against the baseline's 6L = 1200) and
   large-M limit exactly -1/2 (pure bandwidth fact: identical asymptotic
   bytes — the same -1/2 the ring phases sit at exactly, because
   asymptotically all phase variants move the same 3M/4). Grid range:
   -53/81 at 4 KiB climbing to -49202/98379 at 64 MiB.
4. **The family gap is the constant latency-ladder rung
   (r-1-log2(r))·L = 200 ns at every size**, the executed phase-level
   instance of the module's documented per-phase latency ladder at r = 4:
   ring 3L = 600 >= halving/doubling 2L = 400 >= crossbar L = 200 (the
   crossbar rung is not a declared first-class op — fact 0 above). The
   doubling-phase chain 2L = 400 ns is exactly half the 4r-doubling
   AllReduce's 2·log2(4)·L = 800 ns, just as the ring phase's 3L is half
   the ring AllReduce's 6L.

Balance points (bandwidth term = latency term), extending the 4-rank
transition ladder: the ring phase balances at M = 51200 B — the SAME M as
the ring AllReduce's own beta = lambda point and the 4r-torus crossover
([4r-torus.md](4r-torus.md); halving both terms of an identity leaves its
balance point fixed), so 51200 B is now a three-fold special point of the
4-rank atlas; the doubling phase balances at M = 102400/3 ≈ 34133.33 B,
identical to the 4r-doubling AllReduce's own transition
([4r-doubling.md](4r-doubling.md)), inside the ladder's first x4 interval
16 KiB → 64 KiB. The transition ladder across landed 4-rank cells now
reads {51200/3 (crossbar AR), 102400/3 (doubling AR and doubling phase),
51200 (ring AR, ring phase, torus crossover)} B.

Composition, pinned on the grid from the run records' per-op rows at all
12 sizes: RS(M) + AG(M) per chunk pair sums to 3M/128 + 1200 (ring family)
— the 4r-ring baseline identity digit-for-digit — and to 3M/128 + 800
(doubling family) — the 4r-doubling identity. Two phase ops rebuild each
landed AllReduce cell exactly.

## Table — message-size ladder, deltas vs the ring baseline (exact fractions)

Payload grid: the atlas-wide shared 12-size ladder, 4 KiB → 64 MiB
(maximally even power-of-two ladder, exponents
{12,13,14,16,17,18,20,21,22,24,25,26}; every size divisible by 4096, hence
by the rank count 4, so the divisibility guard `A-L0P-DIV` never rejects a
grid point). Ring baseline ladder: [4r-ring.md](4r-ring.md) (its rows
carry delta exactly 0 by construction). Delta semantics on this page:
per-op phase completion vs per-op ring AllReduce completion at the same
payload M under A-L0P-MSG (the same M reading under which the phases
compose into the baseline identity).

| payload (bytes) | payload (human) | wire B/rank = 3M/4 (exact) | ring phase ns = 3M/256 + 600 (exact) | dbl phase ns = 3M/256 + 400 (exact) | ring AR ns = 3M/128 + 1200 | delta ring phase (exact) | delta dbl phase (exact fraction) | delta dbl phase (%) |
|---|---|---|---|---|---|---|---|---|
| 4096 | 4 KiB | 3072 | 648 | 448 | 1296 | -1/2 | -53/81 | -65.4321 |
| 8192 | 8 KiB | 6144 | 696 | 496 | 1392 | -1/2 | -56/87 | -64.3678 |
| 16384 | 16 KiB | 12288 | 792 | 592 | 1584 | -1/2 | -62/99 | -62.6263 |
| 65536 | 64 KiB | 49152 | 1368 | 1168 | 2736 | -1/2 | -98/171 | -57.3099 |
| 131072 | 128 KiB | 98304 | 2136 | 1936 | 4272 | -1/2 | -146/267 | -54.6816 |
| 262144 | 256 KiB | 196608 | 3672 | 3472 | 7344 | -1/2 | -242/459 | -52.7233 |
| 1048576 | 1 MiB | 786432 | 12888 | 12688 | 25776 | -1/2 | -818/1611 | -50.7759 |
| 2097152 | 2 MiB | 1572864 | 25176 | 24976 | 50352 | -1/2 | -1586/3147 | -50.3972 |
| 4194304 | 4 MiB | 3145728 | 49752 | 49552 | 99504 | -1/2 | -3122/6219 | -50.2010 |
| 16777216 | 16 MiB | 12582912 | 197208 | 197008 | 394416 | -1/2 | -12338/24651 | -50.0507 |
| 33554432 | 32 MiB | 25165824 | 393816 | 393616 | 787632 | -1/2 | -24626/49227 | -50.0254 |
| 67108864 | 64 MiB | 50331648 | 787032 | 786832 | 1574064 | -1/2 | -49202/98379 | -50.0127 |

The doubling-phase delta column climbs monotonically toward the exact
-1/2 asymptote and never reaches it at finite M (the residual gap is the
constant 200 ns rung); the denominators 81, 87, 99, 171, 267, 459, 1611,
3147, 6219, 24651, 49227, 98379 are digit-for-digit the crossbar cell's
delta denominators — all three deltas share the baseline denominator
3M/128 + 1200.

O-CONSERVATION: 0 violations at every size in all 24 records (exact
Fraction self-check of the model's byte accounting, 6 ops per config;
per op, per-rank traffic 3M/4 summed over ranks = 3M = (r-1)M — every
sent chunk received once; e.g. total wire bytes at M = 4096: 73728 =
6 ops x 3 x 4096). All 24 records rederived independently from the closed
forms during stage verification (phase rows, per-op wire and total wire,
aggregates, the composition sums, both delta identities, the constant
-1/2 column, the 200 ns family gap, the monotonicity and envelope of the
doubling-phase delta, and the balance points — all agree exact-string-equal
with the stored `observations.json` files and the landed 4r-ring
`table.json`).

## Crossover message sizes

**None in this cell — for structural reasons on both comparison axes.**
Within the cell the two distinct identities share the bandwidth term
3M/256 and differ by the constant 200 ns, so they are translates of each
other in M: the ring phases are slower at every finite M and the orderings
never swap. Against the ring AllReduce baseline the ring-phase delta is
the constant -1/2 (never changes sign) and the doubling-phase delta is
strictly increasing and bounded inside (-2/3, -1/2) — negative at every
finite M, approaching the ring-phase curve asymptotically but never
reaching or crossing it. Recorded honestly; the atlas's non-trivial
crossover remains the 4-rank torus cell's M = 51200 B
([4r-torus.md](4r-torus.md)) — which is also this cell's ring-phase
balance point (fact 4).

## Run provenance

- execution vehicle: 24 run records through the run path
  (`make run EXP=experiments/atlas/4r_phases/run_atlas_4r_phases_{ring,rd}_{M}_v1.yaml`),
  content-addressed in the append-only evidence store under `results/`
  (git-ignored by design — these ids and the committed manifests are the
  provenance record). First and last grid points per family:

  | family | M = 4096 run id | M = 67108864 run id |
  |---|---|---|
  | ring phases | `869df6b2…9bef4f` | `52fc4989…a24b5` |
  | doubling phases | `24e61217…d2b602` | `9b69a2d0…102e0` |

  (all 24 ids are recoverable by replaying the 24 manifests — the store
  is content-addressed, so identical inputs reproduce identical ids.)
- family/algorithm config: `experiments/topologies/phase_collectives4_free_params.yaml`
  (sha256 `77e684b96e4461fba8348df183bd04f3e6812bc39e52f552ed6e1f558fa0a7d1`)
- workloads: `experiments/workloads/w2_dense_tp_prefill_tp4_chunk{4096…67108864}.yaml`,
  12 files, one per grid point (e.g. chunk4096 sha256
  `456b000f94da7cb7ebad80127aa65dbb7f9fb0bb0fdc66ae06811434529aa146`)
- topologies (committed by the earlier 4-rank cells, unchanged):
  `experiments/topologies/ring4_free_params.yaml` (sha256
  `120d0f02a0582bd5f8aa92f53ab692568a28e6ddb5f0f8ca959698a4ca02ebd7`),
  `experiments/topologies/rdoubling4_free_params.yaml` (sha256
  `7558deb402c44af640e5d8e7a8228a52c437d52d626345bc61e606663c3f1865`)
- implementation profile:
  `experiments/vertical_slice/profiles/implementation_profile_l0_phase_collectives.yaml`
  (sha256 `1166627d64f72c41b3e3702d306c822aeea9acffaf1f3658e4aea3624db1bb6c`);
  assumptions: `experiments/vertical_slice/assumptions_l0.yaml`;
  claim_id empty in every manifest (zero claim edits)
- baseline: the landed 4r-ring sweep, sweep id
  `a7688bb88027e3ed33a6fc04801a4b006dce61f4808127694f863115b6c453fe`
  ([4r-ring.md](4r-ring.md))
- code version: 0.1.0; run ids = sha256(canonical run payload)
- determinism bar: ALL 24 manifests rerun immediately — every rerun
  returned the same run id (the store's put is idempotent), and the two
  sampled records' artifacts hash stably (ring 4096: run.json sha256
  `4da6246c8a9ed69bf09e4063e8fb1e66e6f98b3b655ce1ef0fa221eda87c3d71`,
  observations.json `3da747f83bb3a403933b208c89fa1e90b6d06c8712b3226191bce8b08a42058b`;
  doubling 64 MiB: run.json `dcf3dff460f3938bc50dc17c17251944fa6f0c00ff1d05095febecd9efbfbc69`,
  observations.json `61b825f062152a5695b5c2f92de949a12fc741570358d1e270f2c4a6daff5043`);
  `tests/determinism` 13 passed; full suite 541 passed (12 new
  schema-gated workload inputs); paper-check PASS (15 files, 0 violations).

Catalog: [atlas index](README.md).
