# CALIBRATED-candidate proposal v0.2 — calibration ladder S7

Status: **PENDING OWNER ADJUDICATION.** This document proposes; the
owner disposes. The program never promotes a label: nothing in any
registry, disposition, claim, README row, status line, tolerance, or
evidence label changes by virtue of this file. Every number below is
cited to its immutable record; nothing was re-run for this proposal.

Date: 2026-10-30. Version v0.2 is the first committed proposal document;
any revision is v0.3 — this file is not edited in place once adjudicated.

Inputs (the ladder's immutable records, all committed under
`experiments/calibration/`, each with its deterministic builder and
byte-rebuild guard test):

| Stage | Record id (sha256 over canonical_json + "\n") | Committed copy |
|---|---|---|
| S1 split | `3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20` | `split/anchor_split_v1.json` (18 calibration / 4 holdout / GF-06 blocked) |
| S2 fit | `31b0d090f918ba486775d204912a1b9cc82a5f2f3b758ccebc0142967e6df24f` | `s2/fit_record_v1.json` (CAL-A3, group G1) |
| S3 fit | `23036816e86f81025853decde3b846809f0560f4e3922619ef9eddb52a6106b5` | `s3/fit_record_v1.json` (CAL-A6, GF-02, GF-04 — group G2) |
| S4 fit | `ef9c4517d18913645a90ee3daa26b1bc365a978a10efdf78d276fbf9418101df` | `s4/fit_record_v1.json` (CAL-A8, CAL-A9, CAL-A10, GF-10 — group G3) |
| S5 fit | `43fca722ff77711d67b2879dca1407510dd6a60132e047d6b34fd7b7ee6bb34b` | `s5/fit_record_v1.json` (CAL-A5, CAL-A11, GF-05..GF-09 — group G4) |
| S6 holdout | `89f6256bb2c367db442670bafa814a58312afc3122aecda4d42cd74e68dedd69` | `s6/holdout_record_v1.json` (CAL-A4, GF-01, GF-03, GF-11) |

House context: the 2026-10-29 E1 adjudication (`ADJUDICATION.md`)
approved the 26 anchor records as candidates and named this proposal as
its own future adjudication. Evidence levels per plan §3: an accepted
candidate is at most **E3-within-domain** — no E4 language; anchors are
external published measurements, not our testbed.

## 1. Summary of candidates

| Observable / axis | Candidate label | Domain in one line |
|---|---|---|
| O-CCT, bandwidth-bound large-message axis (`analytical_l0_crossbar`) | **CALIBRATED within domain** (fallback: VERIFIED, same domain — owner's call, §3.1) | NVSwitch-class switched rack, NVLink-4/5 generation class, out-of-place AllReduce, per-rank 2–8 GiB, at the fitted diagnostic B |
| O-CCT, ring-family large-message axis (hybrid + community fits) | **no change** | degenerate fits; the designated ring holdout staged no series; the full-mesh holdout missed (§3.2) |
| O-CCT, latency-bound small-message axis (all identities) | **no change** | no software-latency term; the measured ~0.86–1.83 µs floor decade is unreached by every wire-class placement (§3.3) |
| O-CCT, torus-geometry axis | **no change** (standing falsification) | twist-blindness 63%/31%, inexpressible on the B axis even unbounded (§3.4) |
| O-CCT, congestion / CM semantics | **no change** (inexpressible by construction) | the model sits at the uncongested origin every envelope is measured against (§3.5) |
| O-CONSERVATION / O-TRAFFIC-IMBALANCE / O-CCT-RELERR | **no change** | not calibratable (algebraic / by-construction / mechanism — plan §1) (§3.6) |

The evidence, not ambition, sets this shape: the bandwidth axis is the
only axis where a fit with held-out reporting exists AND a held-out
anchor point lands inside the measurement noise floor; every other axis
either never produced a fit, or was contradicted by its held-out check.

## 2. How to read a candidate

Each section below states: the candidate label; the exact validity
domain (the sentence the owner would be approving); the evidence (every
number traced to its record id and run id); and the known omissions
that bound the claim. "Held-out evidence actually reaches" is the
standard: a domain edge is drawn where a held-out anchor or held-out
series member was evaluated — including where the evaluation missed
(the miss is the boundary, not a defect of the proposal).

## 3. Per-observable proposals

### 3.1 O-CCT, bandwidth-bound large-message axis — `analytical_l0_crossbar`

**Candidate: CALIBRATED within the following domain** — if accepted, its
evidence level is E3-within-domain (plan §3.6: cites the run ids, no E4
language). Fallback: VERIFIED with the identical domain and evidence, if
the owner judges the single M-flagged external corroboration
insufficient basis for a calibration label — the trade is stated in the
evidence rows below.

**Exact validity domain.** O-CCT for out-of-place AllReduce
(per-rank wire bytes 2(r−1)/r·M) on the `analytical_l0_crossbar`
identity (single-port injection abstraction) at the fitted calibration
configuration B = `19561820264071168/23648730912675` ≈ 827.1827 B/ns
per direction, L = 200 ns (registry point; the latency term is
immaterial here, 2L/t ≤ 7.5e-5), restricted to:

- **Topology class:** switched NVSwitch-style rack fabrics — the class
  where the single-port aggregate abstraction is admissible (plan §2.1
  A-L0X-PORT KEEP class). Explicitly excluded: full-mesh / per-pair-link
  fabrics (GF-01), torus class, hybrid rail-optimized fabrics where
  inter-node legs dominate (the CAL-A6 class carries its own fits).
- **Generation class:** H100/GB200/B300 (NVLink-4/5) era. The fit anchor
  is GB200 NVL72 (NCCL 2.28.3, r=72); the one-generation-forward
  transfer point is B300-class and M-confidence flagged.
- **Message-size regime:** per-rank payloads 2–8 GiB (the split record's
  fit sizes; bandwidth-bound plateau). Explicitly excluded: ≥16 GiB
  (held-out misses, § below), mid-size (MiB-class: a measured 2 MiB row
  collapses 9.5–11.8× below its own generation's plateau), and the
  latency-bound small-message regime (§3.3).
- **Configuration status:** B_fit is a calibration diagnostic recorded in
  fit record `31b0d090…` — never a shipped default (registry A-L0X-BW
  stays 64, range [1, 1024]).

**Evidence.**

| Claim | Number | Record | Run / sweep |
|---|---|---|---|
| In-fit worst case (exact minimax over {2,4,8} GiB) | ±4.735% (exact `194413/4105547`), binding at 2 GiB (−4.735%) and 8 GiB (+4.735%), 4 GiB +0.468% | `31b0d090…` (S2) | run `c32d3c646a5f4acedf054eb219675c7711e5ee3f412e1c2ee9ea5f0c215ce32a` (fit side, held_out: false); sweep `9cf1ed89…` |
| Tolerance-shape context (NOT adopted) | 5% window [825.098, 829.487] B/ns — contains no grid or provenance point; 8% window contains only 832 | `31b0d090…` | — (closed form over the fit points; E0 zero-slack stands) |
| Within-series held-out {16, 32} GiB (reported, never fitted) | +7.634% / +9.642% at B_fit — the boundary that excludes ≥16 GiB from the domain; implied effective B ramps 788.0→866.4 in-fit, 890.3→906.9 out-of-fit | `31b0d090…` | runs `f1f0604853f1ffb712903848624d6afe9b3072a58cb26d741f7297ef9f896140` (16 GiB), `7b2136ae9d09d16cdb4324bcb4d3a66b83261b22560938c10532f18e225fe1d1` (32 GiB), both held_out: true, evaluation-only |
| One-generation-forward transfer (the single positive held-out point) | B_fit/837 = 0.988271 → **−1.17%** of the measured 837 GB/s peak in effective-B (exact `631026460131328/638515734642225`); +1.19% CCT at the declared 16 GiB probe | `89f6256b…` (S6) | run `f99ca410bb13d8e9cd910f7bd8ebf63ca66b59d84f309948b4a64cfc7d81287e`; sweep `f86f189a…` |
| Noise-floor context for the −1.17% | CAL-A6's measured 5–8% software-version swing (fit-set noise-floor anchor; plan §3.4) — the transfer sits well inside it | `23036816…` (S3) | runs `ad7e937c…`, `7d762405…` |
| Domain carve-out: full-mesh class misses | GF-01 16 GiB row: −33.0% / −17.9% / −14.8% (ring GF-04 / A6-2.19.3 / A6-2.20.3), −11.4% (crossbar GF-02, the OUT-OF-DOMAIN class per A-L0X-PORT), −61.4% (S2 crossbar); implied effective B 318.98 below every fitted B | `89f6256b…` | run `d70ef4265dcba35f760f44d2ca617a5fc75d2165c730805f0424b9b29800bb99`; sweeps `e2b96372…` |
| Domain carve-out: mid-size collapse | GF-03's only staged CCT row (2 MiB, 42–52 µs): model 4836.77 ns — 8.68–10.75× miss; implied effective B 71.1–88.2 B/ns (9.5–11.8× below the same anchor's 837 plateau); none of the 210 constructible (chain × B × L) predictions reaches the band | `89f6256b…` | run `f99ca410…` (above) |

**The honest trade for the owner.** The candidate's in-domain evidence
is a 3-point minimax (±4.735%) whose points are all fit-side, plus
exactly ONE held-out corroboration inside the domain class: the GF-03
plateau point at −1.17%, which is M-confidence flagged (a single
headline busbw quote, no series, rank count and NCCL version unstated —
and the same 837 sits inside CAL-A3's own measured band, so it
partially re-measures the fit anchor's fabric generation). If one
M-flagged point is too thin a basis for CALIBRATED, the identical
domain and evidence support **VERIFIED** (the fit and the held-out
error reporting are executed, deterministic, and reproducible); the
difference is only whether the label says "calibrated". Both options
are prepared; nothing else changes between them.

**Known omissions bounding this candidate.** (1) The size-dependent
software-effective-bandwidth ramp (axis 1, §4): the ±4.735% is a minimax
across a ramping series — the fitted B is a compromise, no fixed-B value
does better, and the ramp is why ≥16 GiB is excluded. (2) The
software-version / algorithm-class axis (axis 2): B in this family is a
software-effective rate, not a fabric constant — CAL-A6's −3.66%
fitted-B separation across two NCCL versions and the 32.3% GF-02-vs-
GF-04 span on one fabric class both moved it; the fit anchor's own
algorithm and NVLink-vs-IB path split are unstated in the source.
(3) Single-B structure: no per-link or port structure, so measured
per-link derating (GF-01's 45.1–47.2 of 64 GB/s) is inexpressible.
(4) The transfer point's M flag. (5) The standing L0 transport omissions
(no congestion, no packetization, no in-network reduction) — the domain
is uncongested single-collective AllReduce by construction.

### 3.2 O-CCT, ring-family large-message axis (hybrid + community series)

**Candidate: no change.** The S3 fits are recorded PROPOSED diagnostics;
no promotion is proposed for the ring identity family or any of its
fitted values.

**Evidence and reasoning.**

- The fits are degenerate: CAL-A6 two-point minimax per NCCL version —
  B_fit = 388.7275 B/ns (2.19.3, worst ±0.623%) and 374.5143 B/ns
  (2.20.3, worst ±2.195%), the −3.66% fitted-B separation being the
  anchor's noise-floor role executed on the parameter axis; GF-02
  degenerate at B_fit = 360 exactly (zero residual degrees of freedom;
  residuals are the pure latency terms, worst +0.061%); GF-04
  degenerate on the single 8-GPU point (B_fit = 476.37, residual
  +0.0177%). Record `23036816…`; runs `ad7e937c…`/`7d762405…` (A6),
  `ffdd546d…`/`96d48073…` (GF-02 allreduce + allgather twin),
  `5af31f3b…` (GF-04 fit).
- The holdout evidence that reached this family did not support any
  promotion: CAL-A4 — the designated ring-class holdout — staged no
  hardware (size→time) series, so the plan §3.5(b) check degenerates to
  placement (recorded NON-EVALUATION; every landed ring fit sits
  2.497–3.176× the anchor's own 150 B/s NVLink-3 quote — a
  two-generation gap in the wrong direction; record `89f6256b…`, run
  `e1d2aede889d31c43aa510f86eb7bc4f478f1d82a8b601acdfd29bd07b553b71`,
  sweeps `3a345766…`/`9f8580e5…`). GF-01's 16 GiB plateau row: the ring
  fits over-predict bandwidth by 14.8–33.0% (run `d70ef426…`).
- The one modest positive — GF-04's within-series held-out 16-GPU point
  at −1.37% (run `ed77cce301ef938c5497e936904c01ce9665b1885099fd568e0f006a61ee2b48`,
  held_out: true) — rests on a one-point degenerate fit whose miss is
  itself classified as the fabric-asymmetry omission (axis 2); it
  supports the recorded diagnostic and nothing more.
- The 360-vs-476.37 GB/s audit stays open as classified: a
  software-stack / algorithm-class axis on one fabric class (32.3%
  span), never averaged.

### 3.3 O-CCT, latency-bound small-message axis (all identities)

**Candidate: no change.** No CALIBRATED or VERIFIED is proposed on the
latency axis; the four latency registry entries stay at value 200, range
[10, 2000] ns; the S4 placements stay recorded diagnostics.

**Evidence and reasoning.**

- Every S4 fit is degenerate (the anchors stage latency-axis POINTS, not
  series): CAL-A8's emulated CXL band {64, 140} ns and CAL-A9's budget
  sum 80 ns fit as their own staged values under mappings declared in
  advance; CAL-A10's 800 ns is assumption-class (no L can be falsified
  against it); GF-10's measured app-level P2P requires L = 9000 ns —
  outside the declared range at 4.5× the upper, best in-range L missing
  by −5/9 on the latency floor and −75.89% at the smoke point. Record
  `ef9c4517…`; runs `2ca54ead…` (A8 64), `774cc400…` (A8 140),
  `95222277…` (A9 80), `6c3b7566…` (A10 800), `a54446b6…` (GF-10);
  sweeps `778f67f3…`/`f2afb641…`.
- S6 externally confirms the axis is unreached on three independent
  fabrics: GF-01 small-message rows — the placements land at 0.05–0.94
  of measured, implied effective L 855.6–1195.7 ns, the measured eager
  band non-monotone in size while every fixed-(B, L) identity is
  strictly monotone (run `d70ef426…`, sweep `bb092e47…`); GF-11 — only
  the assumption-class A10 placement (800 ns) reaches the measured
  decade (2L = 1600 ns = 89/78 ≈ +14.1% over the 1404 ns 2-GPU SoL);
  wire-class placements sit 3.5–11× under the decomposition point; the
  implied bracket L 1183.5 / 1832.8 ns is above every fitted placement;
  GF-03's D2D 1400/1600 ns points are in-range but 8–25× above every
  wire-class placement (runs `7eda947ca7025b99bea378719f6ec54c42c85f02753a17777596bebdddf30075`,
  `f99ca410…`).
- The cross-anchor observation (recorded, never cross-derived): the
  implied small-message floor from three generations and two fabric
  classes lands in ONE decade, ~0.86–1.83 µs — above every wire-class
  fitted placement, below GF-10's app-level 9000 ns. The only landed
  configuration in that decade is the assumption-class 800.
- What the ladder earned here is not a label but a measured statement of
  the gap: any future software/endpoint-latency term must place the
  small-message floor in that decade. That statement, not a promotion,
  is this axis's deliverable.

### 3.4 O-CCT, torus-geometry axis

**Candidate: no change** (a standing falsification, not a promotion).

The falsifier executed (record `43fca722…`; runs
`43091e1545280c151bb56769897cff7e538e3c3e8935d8ab11bb5599d49c9458` /
`645e8b4f2a733ab358c60be719c1575757ec21bc6ed0ffd8402c7a146fbbb6b5`):
the torus input space carries no geometry field, so the model's
twisted/regular ratio is exactly 1 against the measured 1.63 (r=128) /
1.31 (r=256) — blind spots of 63%/31%; the required twisted completion
times (5580.96 / 11833.65 ns) lie BELOW the identity's B→∞ latency
floor (8800 / 15200 ns), so no per-link B, finite or infinite, can
produce the geometry speedup — the whole unbounded B axis delivers at
most 5.356%/6.411% of the required gain; the in-range L-absorption
values (120.09 / 151.73 ns) are flagged misattribution, never selected.
Untested-by-holdout: no torus-class holdout anchor exists in the split.
This falsification bounds every geometry-abstraction claim at L0
(the plan §2.1 A-L0T-UNIF flag). Per-link placements 20/25/50 sit inside
the plan span [20, 64]; the registry 64 sits +28% above reading 1 and
CAL-A5's own TPU v3 comparison row (70) would sit above the span
ceiling — flagged for the owner in S5; no span changed here.

### 3.5 O-CCT, congestion / CM semantics

**Candidate: no change** (inexpressible by construction; not a
calibration subject at any executed fidelity).

The identity predicts exactly the uncongested carrier row — the origin
every envelope anchor measures its effects against. Structurally
inexpressible: GF-07's measured 5%→25× collective-slowdown envelope,
CAL-A11's 30–40% production load-balance effects, GF-05's UEC-NSCC
20–50% gains / RoCE 3–6× distances, GF-08's 8×/65% transport deltas
(record `43fca722…`; runs `7f8dfd7f…` carrier, `f96b688c…` GF-05,
`e14917e9…` GF-07, `09cae0bf…` GF-08, `610653fb…` GF-09). The executed
convergence law shows a dimensionless congestion factor enters an
affine identity only as an asymptotic effective-B displacement
(the 25× edge executes at 7.33× at the 8 KiB ladder bottom), so
small-message congestion costs are latency-masked in the current smoke
regime. GF-09's design targets constrain nothing (zero falsification
power; normalization-only class floor). Untested-by-holdout: all four
holdout anchors are uncongested single-collective microbenchmarks.
This axis bounds every congested-regime claim the corpus may make.

### 3.6 Other observables

**Candidate: no change.** O-CONSERVATION is an algebraic self-check of
the model's own byte accounting (no external measurement can move it;
unsupported on the ASTRA-sim analytical backend, which emits no byte
accounting). O-TRAFFIC-IMBALANCE is exactly zero by construction at L0.
O-CCT-RELERR is the comparison mechanism, not an observable; the E0
zero-slack policy stands — **this proposal adopts no tolerance** (the
5%/8% windows in the records are shape context only; a nonzero
tolerance must arrive through CGFR with recorded evidence, plan §3.4).

## 4. The five-axis known-omission list

These five axes bound every candidate above; any claim citing the
calibration ladder must carry the axes that apply to it. (Numbering per
the S7 dispatch; the S6 record's own `known_omissions_for_s7` carries
the same content with S5's two items as axes 4 and 5, both marked
UNTESTED-BY-HOLDOUT.)

1. **S2 — size-dependent software-effective bandwidth.** A fixed-B,
   zero-overhead identity cannot express the effective-B ramp: CAL-A3's
   implied effective B rises 788.0→906.9 B/ns across 2–32 GiB (held-out
   rows +7.63%/+9.64% at B_fit); GF-03's measured 2 MiB row implies
   71.1–88.2 B/ns against its own 837 plateau — a 9.5–11.8× collapse,
   with none of 210 constructible (chain, B, L) predictions reaching
   the 42–52 µs band. Corroborated one generation later with a measured
   mid-size row. The A-AS1-CHUNKS-1 chunk-count declaration duty
   (plan §2.2) is where a channelization/pipelining term would enter.
2. **S3 — fabric asymmetry** (traveling with the software-version /
   algorithm-class axis). The GF-04 held-out 16-GPU point misses −1.37%
   at a B fixed by the 8-GPU leg alone (the 8→16 inter-node crossing
   cost is structurally inexpressible); GF-01's measured per-link
   derating (45.1–47.2 of 64 GB/s) is inexpressible in any single-B
   identity; CAL-A6's −3.66% fitted-B separation across two NCCL
   versions and the 32.3% GF-02-vs-GF-04 span move B as a
   software-effective rate; CAL-A4's placement shows a 2.497–3.176×
   generation gap.
3. **S4 — no software/endpoint latency term.** GF-10's app-level P2P
   sits out-of-range (−75.89% best in-range at the smoke point); S6
   confirms the measured small-message floor decade (~0.86–1.83 µs:
   GF-01 855.6–1195.7, GF-11 1183.5/1832.8, GF-03 1400/1600 ns) above
   every wire-class fitted placement. With it: the lumped symmetric 2L
   cannot express measured asymmetric decompositions (GF-11's
   2×306+792 SoL), affine response cannot express flat-to-saturation
   transitions or non-monotone launch floors, and uniform L cannot
   express measured pair heterogeneity (GF-10 manual routing).
4. **S5 — congestion-envelope inexpressibility + CAL-A5 twist
   blindness.** No congestion, load-balance, incast, CC, loss, or
   retransmission semantics exist anywhere in L0: the whole measured
   5%→25× envelope is inexpressible (the model sits at factor exactly
   1). No geometry field exists in the torus input space: the measured
   31–63% twist effect is unreachable on the B axis even unbounded
   (below the B→∞ latency floor). Both items UNTESTED-BY-HOLDOUT (no
   congested and no torus-class holdout anchor exists in the split) —
   carried as standing structural bounds, stated as such.
5. **S6 — the out-of-domain placements (the holdout's boundary
   findings).** GF-01: the full-mesh class is out-of-domain for the
   single-port abstraction (A-L0X-PORT) — every fitted configuration
   over-predicts its plateau. GF-03: mid-size collapse (axis 1) while
   the plateau transfers; its broadcast/bidirectional quotes have no
   L0 identity (recorded non-evaluations). GF-11: the measured
   implementation span 1100/237 ≈ 4.64× exceeds the identity family's
   full chain ratio 3 at r=4; the rank growth 170/107 ≈ 1.59× (r=2→64)
   matches no chain; the >1 µs barrier class bounds a cost the identity
   does not carry. CAL-A4: non-evaluation (no staged series) — the
   plan §3.5(b) external check is honestly bounded; a future split
   record cannot fix this without new staged numbers.

## 5. Adjudication checklist — what the owner is being asked to decide

1. **Bandwidth-axis candidate (§3.1):** accept CALIBRATED within the
   stated domain, demote to VERIFIED (same domain), or reject. If
   accepted, approve or amend the exact domain sentence — the domain
   wording IS the claim. State whether the label may appear in
   README/status/claims text, and with which wording
   (E3-within-domain, citing records `31b0d090…` and `89f6256b…`).
2. **The fitted-B diagnostic's standing:** it stays a diagnostic in
   `experiments/calibration/s2/` (registry A-L0X-BW stays 64). Decide
   whether calibration-claim manifests and prose may cite
   B_fit ≈ 827.1827 B/ns as the calibration configuration (the
   proposal's assumption: yes, always cited to the record, never as a
   shipped default).
3. **Latency axis (§3.3):** confirm no promotion; confirm the measured
   ~0.86–1.83 µs floor decade is recorded as the standing gap statement
   for the software-latency omission (the input any future
   endpoint-latency term must match).
4. **Ring family, torus, congestion (§3.2, §3.4, §3.5):** confirm no
   promotions; confirm the S5 falsification and envelope findings, and
   the S6 boundary findings, as standing bounds.
5. **The five-axis omission list (§4):** approve as the bounding
   register for every calibration claim — any claim citing the ladder
   carries the axes that apply.
6. **Tolerance policy:** confirm E0 zero-slack stands and that no
   tolerance is adopted by this proposal (5%/8% windows are context).
7. **Downstream updates on approval:** any registry/README/status/claim
   wording changes are executed only in a recorded adjudication entry
   (owner-executed or dispatched) — this document changes nothing by
   itself.
8. **Standing items unchanged:** GF-06 stays blocked (any assignment
   needs a new `split_v2` record); parameter-range narrowing (the
   plan §2 NARROW verdicts) remains a separate future adjudication —
   nothing here narrows a range or moves a value.

## 6. What this document does not do

It promotes no label; changes no registry value, disposition, claim, or
status line; adopts no tolerance; tunes nothing; re-runs nothing (every
number cites its immutable record); touches no anchor material (GF-06
included). It is the ladder's capstone deliverable, not an adjudication
record — the adjudication entry the owner writes against it is the act
that may move labels.
