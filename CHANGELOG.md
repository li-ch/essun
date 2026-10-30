# Changelog

All notable changes to essun. Format adapted from [Keep a Changelog](https://keepachangelog.com/); versioning intent is SemVer.

**Evidence labels are house law**: every entry below carries one of `PROPOSED` / `IMPLEMENTED_UNVERIFIED` / `VERIFIED` / `CALIBRATED` / `EXTERNALLY_REPRODUCED`, or an explicit `documentation-only` / `no-label` marker where no measurement or capability claim is made. The frozen claim vocabulary of `make paper-check` is avoided throughout.

## [Unreleased]

### Project — 2026-10-29

- **Renamed to essun (Executable Specifications for Scale-Up Networking)** from the working title; package, docs, site, and Docker image names follow. Run ids embed input hashes and the image name, so the W1-smoke goldens were re-stored: L0 916bfc86… -> 146ba565…, ASTRA fb283970… -> c6dc87eb…, uet 65868d02… -> fbb46d16…; no model or observable changed. `documentation-only`.

### Governance — 2026-10-29

- **ADR-0004 — third backend ratified**: `uet_htsim_cms` joins the L0 family and ASTRA-sim paths; 0.976× attribution probe named as follow-up. `IMPLEMENTED_UNVERIFIED`.
- **Calibration candidates approved (E1)**: all 26 records approved as E1 candidates with zero claim/label upgrades; GF-06 remains a documented gap pending manual extraction; one exploratory run marked non-authoritative. See `docs/calibration/ADJUDICATION.md`. `no-label` (adjudication record).
- **Atlas approved as E0 product content**: 30/30 catalog pages. `no-label`.

### Governance — 2026-10-30

- **Calibration anchor split recorded (S1)**: the 23 integrated anchors partitioned into an 18-anchor calibration set (four regime groups, one per fitting stage S2–S5) and a 4-anchor holdout — CAL-A4 (plan §3.5(b) external check), GF-01 (only measured full-mesh series), GF-03 (next-generation point), GF-11 (current-gen small-message + latency decomposition) — spanning four-plus regimes; GF-06 stays blocked (no numbers exist). Content-addressed record `3862e227…` committed at `experiments/calibration/split/` BEFORE any fitting, with within-series held-out sizes declared (CAL-A3 {16, 32} GiB; GF-04's 16-GPU point) and an immutability guard test; calibration and validation data stay separate. `no-label` (split record; no observable calibrated).

Everything the repository has ever shipped lives in this section for now: activity spans 2026-10-26 through 2026-10-30, and no release has been cut. This section is the running draft of the v0.1.0 release notes; when v0.1.0 is tagged, the entries below move under that heading unchanged. Nothing in this file is `CALIBRATED` or `EXTERNALLY_REPRODUCED` — the evidence ceiling today is `IMPLEMENTED_UNVERIFIED` (see README, "What the demo does not show").

### Added — simulator core

- **Deterministic simulation core (vertical slice)** — contracts, the W1 Dense TP Decode workload generator, the analytical L0 ring AllReduce backend, and a run-path orchestrating content-addressed run records; exact-`Fraction` arithmetic throughout. `IMPLEMENTED_UNVERIFIED`.
- **L0 analytical model family (5 models)** — crossbar, 2D torus, recursive-doubling, and phase collectives (ReduceScatter/AllGather, ring + halving/doubling) join the ring; divisibility capability gates (`A-L*-DIV`) reject non-integral chunking loudly. `IMPLEMENTED_UNVERIFIED`.
- **L0.5 compute-term model** — serialized-ring AllReduce identity t = 2(r−1)(c/I + c/B + L) with c = M/r, exact convergence to the L0 identity as I→∞, traffic unchanged; carries its own assumptions file. `IMPLEMENTED_UNVERIFIED`.
- **W2 Dense TP Prefill workload generator** — per-chunk ReduceScatter/AllGather dependency chain (A-W2-DAG) on the shared DAG base. `IMPLEMENTED_UNVERIFIED`.
- **Run-path backend selection** — the experiment manifest selects topology (file ref), model (`backends` id), and workload; the 5 L0 models, W1/W2, and the ASTRA-sim analytical backend are reachable via `make run`. `IMPLEMENTED_UNVERIFIED`.
- **Sweep runner** — design-space grids with per-config capability gates and exact-`Fraction` delta tables vs a named baseline (E0); byte-identical replay. `IMPLEMENTED_UNVERIFIED`.
- **Observables registry** — exact / logical / bounded / analytical kinds with failure policies; O-CCT, O-CONSERVATION, O-TRAFFIC-IMBALANCE, and O-CCT-RELERR for differential comparison; conservation observables are labeled algebraic self-checks of model accounting, not independent physical checks. `IMPLEMENTED_UNVERIFIED`.
- **Append-only evidence store** — content-addressed run records with claim links, plus `put_counterexample`, content-addressed `register_figure`, and `export_reproduction_bundle`. `IMPLEMENTED_UNVERIFIED`.
- **Cross-backend difference engine** — exact and bounded obligations with an anti-tuning gate (registered tolerances only), controlled-comparison gate (workload/topology hashes must match), and capability-gap `not_comparable` verdicts; hermetic golden tests; end-to-end it reproduces the L0-vs-ASTRA analysis (7.404x chain O-CCT gap decomposed with zero residual into 2 declared modeling differences, nothing tuned). `IMPLEMENTED_UNVERIFIED`.
- **Serving feedback controller** — deterministic O-CCT-threshold controller over the decode batch size (run-to-run and within-run variants). `IMPLEMENTED_UNVERIFIED`.
- **Draft JSON Schemas + example pairs** — assumptions, infragraph, workload_ir; promoted per ADR-0002 and now at repo level in `schemas/` + `examples/`. `IMPLEMENTED_UNVERIFIED`.

### Added — standard profiles

- **UEC 1.1 semantic profile** — license-gated ingestion (`experiments/uec/`, permanent license-gate test, sha256-gated deterministic extractor) yielding 80 page-hash- and verbatim-quote-verified anchors, 445 typed requirement objects, and 67 free parameters across five mechanism modules (link/transport, reliability/ordering, congestion management, credits/flow control, F07 mechanisms). Reconciliation ladder S0–S6 complete over all 32 L0/L0.5 assumption ids: 24 STAYS_FREE / 3 SPEC_ANCHORED / 5 OUT_OF_SCOPE / 0 CONTRADICTED; reconciliation headline — no L0 numeric model value is standard-derived. `IMPLEMENTED_UNVERIFIED`.
- **UnifiedBus paper-derived profile (not normative)** — PUBLIC_READ-only sources with the same anchor-integrity tests: 53 anchors, 54 typed parameters each carrying a mechanical evidence grade (PAPER_REPORTED / VENDOR_CLAIMED / OFFICIAL_PUBLIC_PAGE — vendor figures cannot launder as measurements), and a code-enforced platform map (L0_READY 8 / L1_L2_REQUIRED 28 / UNSUPPORTED 26). Feeds the cross-standard comparison grid, in which the UnifiedBus row coincides exactly with the identity-matched UEC control — delta 0 by construction, an arithmetic fact of shared free parameters, not a measured difference between standards. Public-gate leg 2 with its not-normative label. `IMPLEMENTED_UNVERIFIED`.

### Added — discrete-event backends

- **Backend pins** — ASTRA-sim @ `4ce9ecf` and uet-htsim @ `65ea315b` pinned with capability matrices and license review preceding ingestion (MIT / BSD-2 recorded in `backends/pins/`). `IMPLEMENTED_UNVERIFIED`.
- **ASTRA-sim analytical adapter** — Docker image pinned and verified by id (`backends/docker/`), W1 manifest translation, producing the DES twin RunRecord `c6dc87eb…` for the W1 smoke workload; 2 counterexamples vs L0 classified, not tuned (A-AS2-DELAY-POS, A-AS2-MEM-BW). `IMPLEMENTED_UNVERIFIED`.
- **uet-htsim container** — digest-pinned Docker build at the pre-pinned commit, smoke run reproducing all five upstream README output markers byte-identically across reruns, plus an execution-verified runbook. `IMPLEMENTED_UNVERIFIED`.
- **csg-htsim packet-level frontend** — Docker build, smoke run, and runbook (upstream `run_htsim.sh` defects documented by line number); run-to-run nondeterminism root-caused (`srand(time(NULL))` feeding queue-drop decisions) — classified, not tuned — and an env-seeded one-line Dockerfile patch added; the patch's narrow claim (two-run byte-identity at seeds 1 and 2) is `VERIFIED`, the surrounding build/runbook material `IMPLEMENTED_UNVERIFIED`.
- csg-htsim remains built + runbooked with no essun adapter; the uet-htsim half of this line (previously no adapter) was superseded 2026-10-28/29 by the `uet_htsim_cms` adapter, ratified as the third backend in ADR-0004.

### Added — verification, tooling, CI

- **Paper skeleton + `make paper-check`** — heading-only skeleton with `[RESULT: ...]` placeholder discipline; the checker enforces number, frozen claim-word, and figure-reference rules, with a vocabulary extended through successive review rounds. `IMPLEMENTED_UNVERIFIED`.
- **`make demo` one-command public-gate story** — bootstrap-if-needed → validate-schemas → test → L0 golden equality → pinned ASTRA twin equality → design-space sweep → figure registration → paper-check; cold-tree (`git archive HEAD`) and fresh-clone drills reproduce the goldens byte-identically. `IMPLEMENTED_UNVERIFIED`.
- **CI workflow + `make ci-local`** — the exact target sequence, testable locally before any remote exists. `IMPLEMENTED_UNVERIFIED`.
- **Seeded property-checking campaign, seed 1** — 5,682,410 distinct valid configs / 86,042,719 exact-`Fraction` property checks across 34 properties (traffic/time identities, phase composition, L0.5 convergence, conservation exactness, byte-identical replay, manifest fuzz) in a time-boxed run; zero model-identity findings; one environment-class finding classified not a model/contract defect. `IMPLEMENTED_UNVERIFIED`.
- **External URL census** — 214/214 occurrences re-probed (54 unique URLs), 0 dead; read-only hygiene, no content ingested. `no-label` (repo hygiene, read-only).

### Added — calibration ladder and design-space atlas (records only)

- **Calibration plan** — per-observable O-CCT anchor mapping and regime matrix from 12 integrated anchors, plus 11 later gap-fill anchors covering small-message latencies, CM effects, and multi-rank injection. `PROPOSED`.
- **CAL-A1 — NVLink5 switch chip spec ceiling** — untuned free-parameter sweep at r=72 over injection B; record `d1f5f1ee`. `PROPOSED`.
- **CAL-A2 — GB200 NVL72 aggregate NVLink bandwidth** — 900 B/ns per GPU per direction extracted as the normalization line; untuned sweep over aggregate injection B; record `794ed363`. `PROPOSED`.
- **CAL-A3 — Crusoe Cloud GB200 NVL72 NCCL 2.28.3 AllReduce (measured O-CCT anchor)** — untuned sweep at B=900 brackets the measured series at −12.44%…+0.77%; fixed-B minimax misfit ±7.02%; exact power-of-two anchor sizes handled through divisibility brackets cross-checked by exact string equality; record `335b1bb3`; zero shipped-manifest or claim changes — review required before any claim change. `PROPOSED`.
- **Design-space atlas, opening cell 4r-ring** — `docs/atlas/` catalog + page; delta-vs-baseline 0 everywhere because the cell is itself its rank-class-4 baseline (declared identity, no crossovers). `PROPOSED`.

### Added — release readiness

- **Public-HEAD cleanup landed** — see Removed below for what left HEAD; schemas/examples relocation and gate rewiring recorded here. `no-label` (repository structure; authority ADR-0003).
- **No-Docker `demo` mode + README Requirements** — Docker prechecks; the two Docker-dependent legs are skipped with exactly what was skipped and the requirement printed, L0-only legs unchanged, exit 0; present-but-missing pinned image remains a hard failure naming the rebuild step; README Requirements section (Python 3.10+ and CI matrix, Docker Engine verified 29.8.2/OrbStack, ~1.3 GB local-only image, disk figures, measured cold-start ~11 s with Docker / ~10 s without). Tested via PATH shim on fresh export trees. `IMPLEMENTED_UNVERIFIED`.
- **Usage guide `docs/usage.md`** — two worked examples (run your own topology; write your own experiment), every documented command executed with real outputs pasted. `documentation-only`.
- **Wayfinding page `docs/wayfinding.md`** — one signpost paragraph per less-usual directory; linked from the README. `documentation-only`.
- **README "What the demo does not show"** — the honest-limits paragraph (UEC semantics bind documentation and L1 contracts today; cross-standard delta 0 by construction; nothing calibrated against hardware). `documentation-only`.
- **Content license `LICENSES.md`** — the repo license map: code MIT, docs/figures/site CC-BY-4.0 (attribution line included), with carve-outs keeping third-party pin licenses and extracted standard text outside both grants; README license block names both. `documentation-only`.
- **This changelog.**
- **Promo package DRAFT (unpublished)** — white paper, blog post, thread, copy snippets, dependency-free static site + Pages workflow kept behind an enable-at-flip note; claims audit 62/62 against disk artifacts; nothing published — review before any publication. `no-label` (draft material).
- **MIT `LICENSE`**. `no-label` (license fact).
- **Weekly Docker-pin CI** — `.github/workflows/docker-pins.yml`: schedule-only weekly job (no push/PR triggers, so per-push CI stays fast) rebuilding the three repo-owned pinned Docker images from scratch (`docker build --pull --no-cache` over a fail-fast:false matrix); a red build is the alarm — no auto-repair, no push; structural checks only (actionlint + PyYAML assertions), never executed on GitHub Actions yet (no remote exists). `IMPLEMENTED_UNVERIFIED`.
- **Issue/PR templates, CONTRIBUTING, make targets** — issue/PR templates aligned with the evidence discipline; CONTRIBUTING expanded to the four review rules; `make help` (default goal) + `make clean` (regenerable caches only; `results/` fenced). `documentation-only`.

### Added — third backend, workload generators, calibration records, atlas, property campaign

- **uet-htsim CMS adapter — the third backend** — manifest translation + capability declaration, Docker execution + RunRecord `fbb46d16…` through the ordinary run path, independence and capability matrix `docs/backend-independence.md`, execution-verified runbook; registered as `uet_htsim_cms`; ratified per ADR-0004 (the 0.976× attribution probe ladder named as follow-up). `IMPLEMENTED_UNVERIFIED`.
- **W3 MoE Dispatch/Combine + W5 PD/KV event generators** — deterministic MoE dispatch+combine all-to-all per layer (routing table + shares input, skew as a free-parameter matrix) and the prefill/decode KV event DAG (alloc→write→transfer→visible→reads→release as a reachability property) on the shared DAG base; both registered-but-gated with loud rejections tested at generator, schema, and run-path levels until an L1/L2 backend exists. `IMPLEMENTED_UNVERIFIED`.
- **Vertical-slice test-suite consolidation** — suite audit with one gap found and closed; +61 tests net across the two generators above. `IMPLEMENTED_UNVERIFIED`.
- **Calibration ladder executed (GF-01..GF-05, GF-07..GF-11, GLOB-BW/INJ/LAT/SER + synthesis)** — 26 `PROPOSED` content-addressed records under `results/calibration/` over 23 integrated public-measurement anchors (12 core + 11 gap-fill; GF-06 blocked by a provider-side content filter — documented gap, material preserved untracked) plus the four global parameter-class sweeps and the four-class sensitivity synthesis; zero shipped-manifest, claim, or label changes. `PROPOSED` (approved 2026-10-29 as E1 candidates).
- **Design-space atlas, cells 2–30 (4r-crossbar through 64r-l05)** — completes the 5 rank-class × 6 family grid = 30 pages + index under `docs/atlas/`, exact-`Fraction` law families carried across rank classes (M* = L·B·r crossovers, envelope laws, the −1/2 phase constant, half-saturation shifts, factorization gaps, the four-way concurrent point); recorded skips stay inside landed cells. `PROPOSED` (approved as E0 product content).
- **Seeded property-checking campaign, seeds 2–25** — extends the seed-1 entry above to 25 seeds: cumulative **169,193,578 distinct valid configs / 2,561,989,637 exact-`Fraction` property checks** across the same 34 properties, zero model-identity findings (the single seed-1 finding was environment-class). `IMPLEMENTED_UNVERIFIED`.
- **Release polish** — release-notes draft, 1280×640 social preview, and honest downgrades across the promo package, every number re-verified against disk artifacts. `no-label` (draft material).
- **Whitepaper fact refresh** — the whitepaper's facts refreshed to the current fact sheet (718 tests, third backend per ADR-0004, 30/30 E0 atlas, 26 E1 calibration candidates). `no-label`.

### Changed

- **Run identity pinned to manifest-declared observables** — golden `146ba565…` restored at HEAD after two run-id breakage classes, each root-caused and closed as a class rather than patched per test.
- **Assumption registries split per model** — `assumptions_l0.yaml` (26 entries) and `assumptions_l05.yaml` (6 entries), all `PROPOSED`; 38-entry approval overlay recorded without touching the hashed inputs; 3 of 32 reconciled ids carry SPEC_ANCHORED verdicts with values unchanged.
- **CI Python matrix 3.10–3.13** — the single-version job becomes a `fail-fast: false` matrix; `requires-python >=3.10` unchanged because no version failed (verified on scratch venvs for 3.10–3.13 plus 3.14/3.15 beyond the claim; the workflow itself remains unexecuted remotely — no remote exists). `IMPLEMENTED_UNVERIFIED`.
- **`make demo` 9 → 8 legs** — one verification leg was retired along with the internal material it checked; the no-Docker mode above covers the two Docker-dependent legs.

### Removed

- **Internal working documents out of the public tree** — planning notes, per-stage build reports, prompt logs, and work-log receipts left HEAD; the public-HEAD structure is recorded in ADR-0003, and git history retains everything. `no-label` (repository structure).

## [0.1.0] — not yet cut

v0.1.0 is the current release target. It has not been tagged and nothing has been published; when it is cut, the `[Unreleased]` entries above move here unchanged and the release-notes draft is derived from them.
