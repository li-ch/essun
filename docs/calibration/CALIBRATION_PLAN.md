# Calibration plan from the integrated anchors

Status: **PROPOSED** (a plan — no value changes, no empirical runs, no claims).
Date: 2026-10-27.

Inputs:

- The 12 calibration anchors, integrated as PROPOSED rows `CAL-A1..CAL-A12`
  in the calibration anchor registry; full numbers, units and
  measurement context in `docs/calibration/anchors_staging.md` (staging doc
  of 2026-10-27). This plan cites each anchor by its CAL id and
  does not re-transcribe numbers beyond what reconciliation needs.
- The L0 assumption registry
  `experiments/vertical_slice/assumptions_l0.yaml` (`assumptions_l0_v1`,
  26 entries).
- The ASTRA-sim analytical adapter registry `TRANSLATION_ASSUMPTIONS` in
  `src/essun/backends/astra_sim/adapter.py` (10 entries; the S2
  counterexample-revision block is `A-AS2-*`).
- The calibration direction (calibrate against published external
  measurements; no testbed) and the validation framework (parameter
  classes, split strategy, evidence levels E0–E4).

Unit convention used throughout: decimal, so 1 GB/s = 1 B/ns; per-direction
figures are derived from bidirectional ones only where the anchor itself or
the staging doc states the split, and are flagged otherwise.

---

## 1. Per-observable mapping — O-CCT

Calibratable performance observable today: **O-CCT only** (registry
`src/essun/observables.py`). Not calibratable, with reasons:

- **O-CONSERVATION** — an algebraic self-check of the model's own byte
  accounting (exact Fraction equality by construction); no external
  measurement can move it. (The ASTRA-sim analytical backend emits no byte
  accounting at all, so it is unsupported there, not miscalibrated.)
- **O-TRAFFIC-IMBALANCE** — exactly zero by construction at L0; becomes
  meaningful only when a higher-fidelity backend emits it.
- **O-CCT-RELERR** — not an observable to calibrate but the *mechanism* a
  calibration run uses to compare against a reference; its tolerance is
  currently E0 zero-slack and any nonzero tolerance must arrive through
  CGFR with recorded evidence (§3 below).

### 1.1 Anchor-by-anchor mapping

| CAL id | Kind | O-CCT role | Regime covered (message / ranks / topology class) |
|---|---|---|---|
| CAL-A1 | spec (NVLink5 switch chip: 57.6 Tbps full-duplex, 72 ports, 9 trays) | **Cannot calibrate O-CCT** — a capacity specification, not a time series. Normalization ceiling only: per-port per-direction 50 B/ns derived from the anchor's own port count; radix/fan-in check for NVSwitch-class topologies. | n/a (any); NVSwitch fat-tree class, r≈72 |
| CAL-A2 | spec (1.8 TB/s bidirectional per GPU, 130 TB/s aggregate) | **Cannot calibrate O-CCT** — specification. Injection-BW ceiling that every measured fraction (e.g. CAL-A3 busbw) is normalized against. | n/a; NVSwitch class, r=72 |
| CAL-A3 | measured (NCCL 2.28.3 allreduce, 72 GPUs, out-of-place busbw ≈ 788–907 GB/s) | **Primary calibration target**: O-CCT in the bandwidth-bound large-message regime on the flagship NVLink scale-up fabric, with exact software pins. Interpretation risk: NVLink-vs-IB path split not stated in the source. | 2–32 GiB / r=72 / NVSwitch rack |
| CAL-A4 | peer-reviewed sim-vs-hardware (ASTRA-sim 2.0 vs 4/16 V100 NCCL ring, mean error ≈5%) | **Calibration target + methodological template**: O-CCT for the analytical backend family in the medium/large ring-allreduce regime; supplies a validated error-band precedent and the validity-domain caveat (no congestion/oversubscription; ≤16 GPUs; NVLink-3 era). | 64 MB–1.5 GB / r=4,16 / ring (NVLink-3) |
| CAL-A5 | measured + spec (TPU v4: 6×50 GB/s ICI; twisted-torus all-to-all 1.31–1.63×; OCS ms switching) | **Topology-sensitivity falsifier + per-link BW anchor**: measured geometry effect on collective throughput checks topology-class modeling, not CCT directly (all-to-all throughput, individual 4 KiB DMAs). OCS ms-timescale is 3+ orders above CCT — **cannot calibrate O-CCT**, bounds only dynamic-topology reconfiguration modeling. | ~4 KiB DMA (all-to-all) / r=128,256 slices / 3D torus |
| CAL-A6 | measured (NCCL 2.19.3 vs 2.20.3, 32 H100 hybrid NVLink+RoCE, busbw 353–391 GB/s, 5–8% version swing) | **Noise-floor anchor, secondary target**: O-CCT for hybrid rail topologies (intra-node NVLink + inter-node RoCE). Out of the pure scale-up domain — the inter-node legs dominate; sets the software-version noise floor any pass criterion must exceed. | 1–16 GiB / r=32 (4×8) / hybrid rail |
| CAL-A7 | spec (MI300X: 7 IF links × 128 GB/s bidirectional, 896 GB/s aggregate) | **Cannot calibrate O-CCT** — specification. Per-link BW for the non-switched full-mesh class (per-pair dedicated links, no switch hop); contrasts the switch-aggregate structure of CAL-A1/A2. | n/a; full mesh, r=8 |
| CAL-A8 | emulated (CXL added latency 64/140 ns; workload-goal fractions) | **Cannot calibrate O-CCT** — a workload-level latency-tolerance study (fraction of workloads meeting performance goals), not a collective completion time. Locates the CXL-class point on the *latency axis* for L parameters only. | n/a; memory-semantic fabrics |
| CAL-A9 | design-estimate (CXL ~10 ns per link per direction, ≥~70 ns per switch stage) | **Cannot calibrate O-CCT** — no collective measurements; a latency-budget breakdown. Decomposes per-hop latency into link term vs switch term for switch-based memory-semantic fabrics. | n/a; CXL-class switch fabrics |
| CAL-A10 | assumption-class, peer-reviewed usage (0.8 µs NVLink-network end-to-end latency; UALink model) | **Cannot calibrate O-CCT** — a stated assumption, not a measurement (source explicitly notes NVIDIA does not publish the number). Sanity band for GPU-fabric hop latency; UALink-side parameters remain model-only until silicon. | small-message regime implied / UALink pod / analytical |
| CAL-A11 | measured (Meta RoCE production fabric; congestion/load-balance effects up to 30–40%) | **Cannot calibrate O-CCT for scale-up** — a scale-out rail-optimized RoCE fabric, not GPU-to-GPU scale-up. Secondary sanity context for exactly the effects L0 declares out of scope (congestion, load balancing). | large / r≈24k / scale-out spine-leaf |
| CAL-A12 | measured-ish (NCCL internal NVLink model: 20 GB/s/link vs 25 physical; app ≈80% of peak) | **Cannot calibrate O-CCT directly** — it calibrates the *bridge*: the derating between physical-BW-based L0 predictions and what an NCCL-driven measurement (CAL-A3/A6) can express. Mandatory normalization whenever spec ceilings (CAL-A1/A2/A7) are compared with measured series. | n/a / r=8 / NVLink-3 server |

### 1.2 Coverage matrix by regime (where O-CCT can actually be calibrated)

| Regime | Anchors that apply | Status |
|---|---|---|
| Large-message bandwidth-bound (≥ ~1 GiB), switch-fabric scale-up | CAL-A3 (target), CAL-A2/A1 (ceilings), CAL-A12 (derating) | covered, one fabric/generation |
| Medium/large (64 MB–1.5 GB), ring, small r | CAL-A4 (target + template) | covered, NVLink-3 era |
| Large-message hybrid scale-up+scale-out | CAL-A6 (noise floor; UEC-proxy shape) | covered as proxy |
| Small-message latency-bound (≤ ~64 KiB) — where the current smoke manifests live (16 KiB) | **none** | gap (see §4) |
| Torus geometry effects | CAL-A5 (falsifier, all-to-all throughput) | partial, different metric |
| Per-hop latency axis | CAL-A8/A9 (CXL class), CAL-A10 (assumption-class GPU) | latency-axis points only, no CCT series |
| Non-switched full mesh | CAL-A7 (spec ceiling) | spec only |
| UEC / UALink semantics | none (CAL-A11 is scale-out context) | gap (see §4) |

---

## 2. Free-parameter reconciliation (plan only — zero value changes)

Verdict vocabulary: **KEEP** = assumed value/range consistent with anchors,
no action proposed; **NARROW** = anchors support a strictly narrower range
(or a different scale) — proposal recorded, value NOT changed here;
**OUT-OF-DOMAIN** = no anchor speaks to this parameter, or anchors exist
only for a fabric class this parameter does not model. Structural
assumptions (divisibility gates, execution-order semantics, id/dependency
conventions) are marked KEEP as *non-calibratable by construction* — no
external measurement can move an input gate or a declared identity.

### 2.1 L0 assumption registry (`experiments/vertical_slice/assumptions_l0.yaml`)

Numeric axes first. Anchor-measured spans below use per-direction
derivations only where the anchor states the split (CAL-A7's links are
quoted bidirectional: 128 GB/s/link ⇒ 64 B/ns per direction; CAL-A1's
57.6 Tbps full-duplex over 72 ports ⇒ 50 B/ns per port per direction;
CAL-A2's 1.8 TB/s bidirectional per GPU ⇒ 900 B/ns per-direction aggregate
injection; CAL-A12's NCCL model 20 GB/s/link with 25 GB/s physical per
direction per NVLink-3 link; CAL-A5's per-link direction convention is
flagged unverified in the staging doc).

| Id | Parameter (assumed) | Anchor-measured span | Verdict |
|---|---|---|---|
| A-L0-BW | `link.bytes_per_ns` = 64, range [1, 1024] | per-link per-direction: 20 (CAL-A12 NCCL model) – 64 B/ns (CAL-A7 per-direction), with 50 B/ns at NVLink5/ICI (CAL-A1/A2; CAL-A5 pending direction check); no anchor below 20 or above 64 | **NARROW (range)** — no anchor supports registry extremes [1,1024]; candidate anchor-informed span ≈ [20, 64] B/ns per link per direction pending acceptance. **KEEP (point)** — 64 sits inside the anchored span; no anchor selects a different point. |
| A-L0-LAT | `link.hop_latency_ns` = 200, range [10, 2000] | latency axis: ~10 ns/link + ≥~70 ns/switch stage CXL-class design estimates (CAL-A9); 64–140 ns emulated added memory latency (CAL-A8); 800 ns assumption-class GPU-fabric end-to-end (CAL-A10) | **KEEP (point)** — 200 ns lies inside the anchored axis span (~10–800 ns). **NARROW (range upper)** — no anchor supports ≥ ~1 µs; upper bound 2000 ns is anchor-free (candidate ≈ ≤ 800–1000 ns), contingent on extracting the deferred V100-era measured P2P series (Li et al., staging §additional candidates). |
| A-W1-SIZE | `workload.allreduce_bytes` = 16384, range [1 KiB, 16 MiB] | measured CCT series live at 64 MB–1.5 GB (CAL-A4) and 1–32 GiB (CAL-A3/A6); nothing measured ≤ 64 KiB (CAL-A5's 4 KiB are all-to-all DMA components, not collective CCT) | **OUT-OF-DOMAIN** for calibration at the smoke value — no anchor covers O-CCT at 16 KiB. Keep as smoke parameter; calibration manifests (§3) must sweep message size into the anchored regimes. Not a value change — the smoke manifest stays as it is. |
| A-L0-FD | `model.link_duplexity` = full_duplex_uniform_per_direction | CAL-A1 ("full duplex" per switch chip) and CAL-A2 (bidirectional per-GPU) describe exactly this behavior class for NVSwitch fabrics; CAL-A7's per-link bidirectional quotes likewise | **KEEP** — consistent with the spec class of CAL-A1/A2/A7; uniformity across links untested by any anchor (noted, no action). |
| A-L0-DIV | `model.chunk_divisibility` (ring) | input gate | **KEEP** — non-calibratable by construction (structural). |
| A-L0X-PORT | `model.port_assumption` = single_port (one shared B across r−1 peers) | NVSwitch class: per-GPU aggregate cap (CAL-A2: 900 B/ns per direction) supports a shared-aggregate abstraction. Full-mesh class: CAL-A7's 7 dedicated per-pair links contradict single-port as a physical description — per-pair capacity structure is lost | **KEEP for NVSwitch-class** validity domains; **OUT-OF-DOMAIN for full-mesh-class** fabrics (CAL-A7): a multi-port/per-pair identity would be required there. Domain labeling, not a value change. |
| A-L0X-BW | `nic.injection_bytes_per_ns` = 64, range [1, 1024] | per-rank aggregate per-direction injection: 448 B/ns MI300X class (CAL-A7 derived), 900 B/ns NVL72 class (CAL-A2), software-effective ≈80% (CAL-A12) | **NARROW (scale)** — every modern anchor sits at 448–900 B/ns aggregate; the smoke point 64 B/ns is inside the declared free range but an order below the anchored scale, so any NVL72/MI300X-class calibration run must treat injection BW as a swept free parameter at the anchored scale. Value unchanged. |
| A-L0X-LAT | `link.pair_latency_ns` = 200, range [10, 2000] | pair-across-a-switch: ≈80 ns CXL-class (CAL-A9 link+switch sum) to 800 ns GPU-class assumption (CAL-A10) | **KEEP (point)** — 200 ns inside the anchored axis; same **NARROW (range upper)** candidate as A-L0-LAT. |
| A-L0X-DIV | divisibility (crossbar) | input gate | **KEEP** — structural. |
| A-L0T-SEQ | `model.dimension_execution` = sequential_full_message | no anchor measures multi-dimensional collective schedules | **KEEP** — structural, non-calibratable today. |
| A-L0T-UNIF | `model.dimension_uniformity` = uniform | CAL-A5's measured twisted-vs-regular torus spread (1.31–1.63× on all-to-all) shows geometry detail matters at equal link BW — a falsification candidate for torus-class modeling generally, but it constrains geometry, not per-dimension parameter uniformity | **KEEP** — flagged: torus-class calibration (future) should treat CAL-A5 as the first falsifier of geometry abstractions >30%. |
| A-L0T-SHAPE | `grid.dim1_ranks x dim2_ranks` = 2x4 | no anchor pins a factorization at r=8 (CAL-A5's slices are 4×4×8 / 4×8×8, different rank scale and metric) | **KEEP** — free design-space parameter, anchor-free by construction. |
| A-L0T-BW | `link.bytes_per_ns` = 64, range [1, 1024] | same anchors as A-L0-BW (values deliberately shared) | same verdict as **A-L0-BW** (NARROW range / KEEP point). |
| A-L0T-LAT | `link.hop_latency_ns` = 200, range [10, 2000] | same anchors as A-L0-LAT | same verdict as **A-L0-LAT**. |
| A-L0T-DIV | divisibility (2D torus) | input gate | **KEEP** — structural. |
| A-L0D-POW2 | `model.rank_schedule` = power_of_two_doubling | structural requirement of the identity | **KEEP** — structural. |
| A-L0D-STEP | `model.step_execution` = serialized_single_partner_steps | structural identity choice | **KEEP** — structural. |
| A-L0D-BW | `nic.injection_bytes_per_ns` = 64, range [1, 1024] | same anchors as A-L0X-BW | same verdict as **A-L0X-BW** (NARROW scale for modern-fabric runs). |
| A-L0D-LAT | `link.pair_latency_ns` = 200, range [10, 2000] | same anchors as A-L0X-LAT | same verdict as **A-L0X-LAT**. |
| A-L0D-DIV | divisibility (recursive doubling) | input gate | **KEEP** — structural. |
| A-L0P-ALGO | `model.phase_algorithm_fabric_pairing` | CAL-A4 validates precisely a ring-collective-on-ring-NVLink pairing (NCCL ring, 5% band) — consistency support, not a calibration of the assumption itself | **KEEP** — structural; CAL-A4 is the external consistency note. |
| A-L0P-MSG | `model.phase_message_size_semantics` | structural reading of M | **KEEP** — structural. |
| A-L0P-COMP | `model.phase_composition` = serialized_rs_then_ag | structural composition identity | **KEEP** — structural. |
| A-L0P-DIV | divisibility (phase collectives) | input gate | **KEEP** — structural. |
| A-W2-CHUNK | `workload.chunk_bytes` = 16384, range [1 KiB, 16 MiB] | same regime gap as A-W1-SIZE — no anchor ≤ 64 KiB | **OUT-OF-DOMAIN** for calibration at the smoke value (same note as A-W1-SIZE). |
| A-W2-DAG | `model.dependency_semantics` = serialized_rs_ag_chain | anchors measure isolated collectives with warmup (CAL-A3/A6), never a chained multi-op DAG; chain-level CCT would compound per-op errors | **KEEP** — structural; §3 restricts calibration comparisons to per-collective O-CCT precisely because no anchor measures chains. |

### 2.2 ASTRA-sim analytical adapter registry (`TRANSLATION_ASSUMPTIONS`, `src/essun/backends/astra_sim/adapter.py`)

| Id | Parameter (assumed) | Anchor-measured span | Verdict |
|---|---|---|---|
| A-AS1-BW-UNIT | `network.bandwidth` — exact B/ns↔GB/s conversion, 1 GB = 2^30 B | none — pure unit convention, exact by construction | **KEEP** — non-calibratable (mathematics, not physics). |
| A-AS2-DELAY-POS | `system.endpoint-delay` = 10 (feasibility: 0 aborts the pinned binary) | CAL-A9's ~10 ns per link per direction is the only anchor at this numeric scale, and it is a different mechanism (wire delay vs endpoint processing) | **KEEP** — the value is a binary feasibility constraint anchored in-tree (EventQueue.cpp:33; pinned example config), already classified in the S3 difference report; **OUT-OF-DOMAIN** for anchor calibration (no anchor measures NCCL-style endpoint delay). |
| A-AS2-MEM-BW | `system.local-mem-bw` = 1600 (feasibility: absent key never completes) | **no anchor in CAL-A1..A12 measures local/HBM bandwidth** | **OUT-OF-DOMAIN** — uncovered by the anchor set (gap §4); stays an upstream-example convention with its in-tree anchor. |
| A-AS2-INERT-KEYS | `system.{boost-mode,roofline-enabled,peak-perf}` omitted | none — proven inert at the pin (identical Wall time with/without) | **KEEP** — calibration cannot observe an inert key by definition. |
| A-AS1-SPLITS | `system.preferred-dataset-splits` = ranks | consistent with the chunked-ring identity and with how CAL-A4's NCCL ring runs decompose; consistency note only | **KEEP** — structural convention. |
| A-AS1-CHUNKS-1 | `system.active-chunks-per-dimension` = 1 (pinned example value) | real stacks pipeline: CAL-A3's channel sensitivity (in-place vs out-of-place spread) and CAL-A6's SM-count finding (16 SMs) show chunk/channel/SM config moves measured bandwidth-bound CCT by whole factors | **KEEP** (example convention) — **flagged as a first-class sensitivity**: any calibration against CAL-A3/A6 must declare chunk-count treatment explicitly, because pipelining depth interacts with the bandwidth-bound regime the anchors measure. Not a value change. |
| A-AS1-RING-IMPL | `system.all-reduce-implementation` = [ring] | CAL-A4 validates exactly ring-allreduce-on-ring (5% band) | **KEEP** — the pairing CAL-A4 directly exercises. |
| A-AS1-CHAIN | workload ET `data_deps` sequential chain | anchors measure isolated collectives; the chain is our comparability convention | **KEEP** — structural translation convention. |
| A-AS1-IDS | workload ET node ids | none — deterministic bookkeeping | **KEEP** — structural. |
| A-AS1-NO-EXPANSION | `remote-memory-configuration` NO_MEMORY_EXPANSION | CAL-A8/A9 are CXL-class latency studies, not expansion configurations | **KEEP** — structural; no anchor speaks to expansion config. |

**Zero value changes were made.** Every registry entry above keeps its
current value and range; NARROW/OUT-OF-DOMAIN marks are recorded proposals
for future calibration manifests, per this document's plan-only scope.

---

## 3. E2 procedure sketch (what a calibration run looks like when executed)

Evidence-level framing: an executed
calibration run targets **E3** (empirically calibrated, held-out error
reported for named implementations/workloads); the existing
cross-fidelity differential path (L0 vs ASTRA-sim on one manifest) already
provides the E2 layer underneath. Nothing below has been run.

1. **Preconditions.** The `CAL-A*` anchor rows are promoted from PROPOSED
   by an explicit integration decision; confidence flags in
   `docs/calibration/anchors_staging.md` that are marked M (CAL-A3
   path-split wording, CAL-A10 paywalled parameter table, CAL-A12 reply
   text) are re-verified at that point. Target status for the *outputs* is
   `CALIBRATED` only inside the named validity domain; public claims
   are updated alongside, never before.
2. **Manifests.** One new calibration manifest per (backend, anchor
   regime), modeled on `experiments/vertical_slice/w1_decode_smoke.yaml`
   (L0) and `w1_decode_smoke_astra.yaml` (ASTRA-sim): same schema path,
   `counterexample_policy: minimize_then_refine`, observables `[O-CCT]`
   (plus O-CONSERVATION on L0), explicit `validity_domain` naming the
   anchor and its regime. Free parameters (A-L0-BW/A-L0-LAT or
   A-L0X-*/A-L0D-*) enter at the anchor-informed scale of §2 — as swept
   free parameters with provenance, never standard-derived. New topology
   files are required where the anchor fixes a different rank count than
   the existing r=8 set (CAL-A3 pins r=72; CAL-A4 pins r=4/16) — e.g.
   `ring72_free_params.yaml`-style transport-agnostic files with the same
   free-parameter discipline.
3. **Targets.** Each target series is an anchor's (size → time) table with
   the unit/metric conversion declared in the manifest: NCCL `busbw`
   → `algbw` → predicted CCT is an algebraic mapping that must be written
   down per point (NCCL's busbw carries the 2(r−1)/r algorithmic factor),
   so the comparison is CCT-vs-CCT, not mixed metrics. First-pass targets
   per §"Top-5 picks" of the staging doc: CAL-A3 (bandwidth-bound
   scale-up), CAL-A4 (analytical-backend regime + tolerance-shape
   precedent), CAL-A6 (noise floor), normalized by CAL-A1/A2 ceilings and
   the CAL-A12 derating.
4. **Pass-criteria shape.** Per size point: relative error of mean O-CCT
   vs the anchor-derived reference, checked through O-CCT-RELERR. The E0
   zero-slack policy stands until a calibration evidence run proposes a
   nonzero tolerance via CGFR; the *shape* of any such proposal is bounded
   by the anchors themselves — CAL-A4's ≈5% validated mean error (in-domain
   precedent) and CAL-A6's 5–8% software-version swing (noise floor: a
   match criterion tighter than the measured software variance would be
   overfitting). A violation is a FINDING to minimize and classify —
   never tuned away.
5. **Holdout discipline.** Calibration and validation sets stay separate
   along the §8 split dimensions: (a) within a series — fit on a subset of
   message sizes (e.g. CAL-A3's {2, 4, 8} GiB), hold out the rest ({16,
   32} GiB) and report held-out error; (b) across anchors — CAL-A4
   (different generation, scale, and software) is reserved as an external
   check, not a fit target, in the first pass; (c) never validate on the
   dimension that was fitted (a calibration that performs only on the
   fitted AllReduce sizes is not broad validation — §8 verbatim). Software
   config pins (NCCL version, SM/channel config) are recorded with every
   target series because CAL-A3/CAL-A6 show they move results by 5–8%+.
6. **Execution and records.** Same documented path as every run:
   `python -m essun.orchestrator.runs <manifest>` (or `make run EXP=…`) —
   deterministic, content-addressed RunRecords in the append-only store
   with seed/topology/hashes; identical reruns must give identical
   artifacts. The evidence label attached to any figure or claim cites the
   run ids and stays at E3-within-domain (no E4 language: anchors are
   external published measurements, not our testbed).

---

## 4. Gap list (honest empties — what no current anchor covers)

1. **UEC-specific behavior on real hardware**: no public UEC measurement
   study exists as of 2026-10; CAL-A11 is scale-out RoCE context and
   CAL-A6 is a RoCE-interconnect hybrid — usable only as labeled proxies.
2. **Current-gen GPU scale-up hop/pair latency**: assumption-grade
   (CAL-A10, 0.8 µs) or CXL-class design estimates (CAL-A8/A9); the
   measured V100-era P2P series (Li et al.) is found but not yet
   extracted; no measured NVLink5/NVSwitch latency exists in the set.
   Weakest axis of the whole plan.
3. **Small-message O-CCT (≤ ~64 KiB)**: no anchor — exactly the regime of
   the current smoke manifests (16 KiB), which therefore cannot be
   calibrated at all today, only verified (E0–E2).
4. **UALink**: no silicon measurements exist; CAL-A10 parameters are
   model assumptions.
5. **Local-memory bandwidth** (`A-AS2-MEM-BW`): no CAL anchor measures
   HBM/local-mem BW; the adapter value remains an upstream-example
   convention.
6. **Chained multi-op workloads (W2 DAGs)**: all measured anchors are
   isolated collectives with warmup; no anchor for chain-level CCT or
   overlap behavior.
7. **Congestion/contention**: L0 and the pinned analytical ASTRA-sim both
   declare it unsupported; CAL-A11 measures it but in the wrong domain
   (scale-out) — no scale-up congestion anchor.
8. **Rank-count mismatch for direct calibration**: CAL-A3 anchors r=72
   while the manifest set is r=8 (and CAL-A7's r=8 is full-mesh
   spec-only); new topology files are needed before any direct comparison.
9. **Spec-vs-measurement hygiene**: CAL-A1/A2/A7 are ceilings, never
   achieved values; the only achieved-value bridge is CAL-A12's ≈80%
   derating, itself M-confidence pending reply-text verification.
10. **CAL-A3 anomalies**: the in-place 2 GiB outlier (kernel/SM contention
    per the source) and the unstated NVLink/IB path split both remain
    un-resolved interpretation risks; they must be excluded or labeled,
    not smoothed.
