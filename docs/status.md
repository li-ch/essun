# Detailed component status (moved from the README front page)

Executable Specifications for Scale-Up Networking.

Code is MIT — see [LICENSE](LICENSE); docs, figures, and the site are
CC-BY-4.0 — see [LICENSES.md](LICENSES.md). Upstream simulator licenses
(MIT, BSD-2-Clause) are recorded in `backends/pins/`.

Specification-driven, multi-fidelity simulator for **Scale-up networks** — the
GPU-to-GPU fabrics used in LLM inference (UEC, UALink, UnifiedBus, NVLink,
CXL, …). Product thesis: *fair cross-SUN-standard comparison that
guides future SUN designs and optimizes architecture, topology and collective
(CCL) algorithm choices*. The research paper is a by-product; every
number it may someday contain must still trace to an immutable run record.

Status labels follow the project evidence vocabulary (`PROPOSED` /
`IMPLEMENTED_UNVERIFIED` / `VERIFIED` / `CALIBRATED` /
`EXTERNALLY_REPRODUCED`).

Component-by-component status, 2026-10-29. The README summarizes; this file keeps the detail.

`make test` — 718 tests green (schema, golden, negative, determinism,
observables, evidence, backends, specir). Nothing is calibrated against
hardware; evidence labels below follow the same vocabulary.

| Component | Status | What exists |
|---|---|---|
| Schema/example validation | IMPLEMENTED_UNVERIFIED | `tests/schema/` — all 7 examples validate: the 3 previously schema-less pairs (assumptions, infragraph, workload_ir) are covered by schemas promoted per ADR-0002 (ACCEPTED 2026-10-28), now at repo level in `schemas/` + `examples/`; the same schemas validate the real inputs under `experiments/` |
| W1 Dense TP Decode generator | IMPLEMENTED_UNVERIFIED | `src/essun/workload/w1.py` — deterministic ops; 16 KiB / 1 MiB identities in tests |
| W2 Dense TP Prefill generator | IMPLEMENTED_UNVERIFIED | `src/essun/workload/w2.py` + shared DAG base — RS/AG dependency chain (A-W2-DAG) |
| W3 MoE Dispatch/Combine generator | IMPLEMENTED_UNVERIFIED | `src/essun/workload/w3.py` on the shared DAG base — deterministic routing-table/shares input (skew is a free-parameter matrix, no learned routing), dispatch+combine all-to-all per layer (A-W3-*); NO registered backend executes all-to-all: W3 manifests are rejected loudly by the capability gates (tested) — executing MoE traffic needs an L1/L2 backend |
| W5 PD/KV event generator | IMPLEMENTED_UNVERIFIED | `src/essun/workload/w5.py` on the shared DAG base — prefill KV-chunk writes, decode reads with request dependencies, memory-semantic KV transfer ops between prefill and decode nodes (A-W5-*); lifecycle alloc→write→transfer→visible→reads→release asserted as a DAG reachability property in tests; NO registered backend executes memory-semantic KV ops: W5 manifests are rejected loudly by the capability gates (tested) — executing PD/KV traffic needs an L1/L2 memory-semantics fabric model |
| Analytical L0 backend family (5) + L0.5 | IMPLEMENTED_UNVERIFIED | ring, crossbar, recursive-doubling, 2D torus, phase collectives (RS/AG) — exact-Fraction identities, capability-declared limits, golden tests per model; plus the L0.5 serialized-ring compute-term model (`backends/analytical/l05.py`, golden-tested incl. the I→∞ convergence anchor to the L0 identity and its own assumptions file `assumptions_l05.yaml`; run-path wiring for `make run` not yet in place) |
| Sweep runner + comparison tables | IMPLEMENTED_UNVERIFIED | `make sweep` → `results/sweeps/<id>/table.{json,md}`; byte-identical rerun; two grids — the AllReduce design space and the first cross-standard grid (UEC vs paper-derived UnifiedBus on shared L0 free parameters, delta zero by construction, `experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml`) |
| Run-path backend selection | IMPLEMENTED_UNVERIFIED | `src/essun/orchestrator/runs.py` — the manifest selects topology (file ref) + model (`backends` id) + workload (kind); the 5 L0 models, W1/W2, and `astra_sim_analytical` reachable via `make run`; capability gates fail loudly |
| Observables registry | IMPLEMENTED_UNVERIFIED | `src/essun/observables.py` — exact / logical / bounded / analytical kinds with failure policies (logical kind with FAIL/WARN policies, O-TRAFFIC-IMBALANCE on the L0 ring, bounded O-CCT-RELERR for differential validation with `differential_observation()`); O-CONSERVATION and O-TRAFFIC-IMBALANCE are labeled algebraic self-checks of model accounting, not independent physical checks |
| Evidence store | IMPLEMENTED_UNVERIFIED | `src/essun/evidence/store.py` — append-only, content-addressed, claim links (every stored run claim-linked after the 2026-10-28 backfill of legacy run `6aa873d8…` → C2); `put_counterexample` (production `counterexamples.jsonl` holds the 2 classified ASTRA-sim cases, linked to run `c6dc87eb…`), content-addressed `register_figure` (id = sha256 over referenced artifact bytes + sorted run-set binding; claims are provenance, not identity), `export_reproduction_bundle`; D3 orthogonal evidence dimensions (`src/essun/evidence/dimensions.py`, run-record schema v2): the five structured fields `verification` / `calibration_target` (anchor ids) / `held_out` / `independent_reproduction` / `known_omissions` on run records, declared via the manifest's `evidence_dimensions` block, absent = UNKNOWN never false, old v1 records still load (backfill-safe; site evidence-page display deferred to the owner) |
| Paper-check tooling | IMPLEMENTED_UNVERIFIED | `make paper-check` — flags fabricated numbers/claim words in the prose-free skeleton; the frozen vocabulary = 4 original words + 8 hype forms + 3 review-round-2 forms (SOTA, `novelty`, spaced `state of the art`) + 6 later additions (`industrial-grade`, `battle-tested`, `production-proven`, `seamless`, and the inflections `seamlessly`/`novelties`), with a parametrized test planting every form |
| UEC 1.1 semantic profile | IMPLEMENTED_UNVERIFIED (specification complete; expert review passed 2026-10-28) | license-gated ingestion under `experiments/uec/` + `src/essun/specir/uec_*`: 80 anchors (page-hash and verbatim-quote verified, permanent license gate) and 445 typed requirement objects + 67 free parameters across five mechanism modules (link transport, reliability/ordering, congestion management, credits/flow control, F07 mechanisms), each carrying a D1 `disposition` (188 informational / 255 unsupported / 2 executed — registry-gated, no silent promotions); reconciliation ladder S0–S6 complete over all 32 L0/L0.5 assumption ids: 24 STAYS_FREE / 3 SPEC_ANCHORED / 5 OUT_OF_SCOPE / 0 CONTRADICTED |
| Requirement→backend bindings (flagship slice + credit-family S2) | IMPLEMENTED_UNVERIFIED | `src/essun/specir/bindings.py` — machine-readable bindings that make a `simulated_behavior` disposition checkable: requirement + anchors + backend capability/parameters + observables re-verified live against every registry. Two bindings today: **UEC11-FC-R02** (UEC 1.1 §3.6.15 TFC admission law) → the `analytical_l0_tfc` credit-window ring (`t = 2*(r-1)/r*M/min(B, W/(L+L_cr)) + 2*(r-1)*L`, exact Fractions, goldens derived in-test incl. exact convergence to the L0 identity at W ≥ BDP; run record `dc7d83b6…` claim-linked as `C-UEC-TFC-R02`), and **UEC11-FC-R08** (G2 ladder S2, 2026-10-30: ROUNDUP cell-quantized credit consumption) → the same backend's opt-in `tfc.dest_cell_size` parameter (`t = 2*(r-1)/r*M/min(B, (c/cq)·W/(L+L_cr)) + 2*(r-1)*L` with `cq = ROUNDUP(c/cell)·cell`, domain 256..9216 B in 256-B multiples cited to UEC11-FC-R07; zero-waste convergence to the R02 identity exactly at `c ≡ 0 (mod cell)`; run record `e74ecec2…` claim-linked as `C-UEC-TFC-R08`, evidence record `experiments/vertical_slice/tfc_r08_cell.EVIDENCE.md`); the 256-byte credit unit (UEC11-FC-R05) and the cell domain values (UEC11-FC-R07) are the spec-derived constants. External reproduction path: `docs/reproduce-flagship.md` |
| UnifiedBus paper-derived profile | IMPLEMENTED_UNVERIFIED (not normative; public-gate leg 2) | `experiments/unifiedbus/` + `src/essun/specir/unifiedbus_*` — PUBLIC_READ-only paper sources with the same anchor-integrity tests, L0 flavor and platform maps; feeds the first cross-standard comparison table |
| Discrete-event backends | IMPLEMENTED_UNVERIFIED | ASTRA-sim @ 4ce9ecf analytical adapter in Docker (`backends/docker/astra-sim.Dockerfile`): first DES RunRecord `c6dc87eb…` with 2 counterexamples classified, not tuned; csg-htsim built in Docker (`backends/docker/astra-csg-htsim.Dockerfile` + runbook/logs; no essun adapter yet); uet-htsim @ 65ea315b pinned, built + smoke-tested in Docker, and adapted as the **ratified third backend** `uet_htsim_cms` (ADR-0004, 2026-10-29; registered in the run path, RunRecord `fbb46d16…`, execution-verified runbook `backends/docker/uet-htsim-runbook.md`, independence matrix recorded at ratification) |
| Cross-backend difference reports | IMPLEMENTED_UNVERIFIED (the opening report was manual; the systematic engine has since landed) | the manual L0-vs-DES report on the W1 smoke pair (RunRecords `146ba565…`/`c6dc87eb…`): the full 7.404x O-CCT gap decomposes with zero residual into 2 declared modeling differences, no parameter tuned; machine-readable copy in `results/difference_reports/`; the systematic comparison engine is built with hermetic goldens (`tests/validation/test_diff_engine.py`) |

Nothing here is calibrated against hardware, and after the UEC 1.1
reconciliation still no numeric model value is standard-derived (ladder
headline F08): the profile anchors message-level bounds and mechanism
laws, while link bandwidth/latency and workload sizes remain explicit
free parameters (`experiments/vertical_slice/assumptions_l0.yaml`, 26
entries, and `assumptions_l05.yaml`, 6 entries — split per model so
unrelated additions cannot shift each other's run ids; all PROPOSED
pending review; 3 of the 32 reconciled ids
carry SPEC_ANCHORED verdicts with values unchanged). Divisibility: every
L0 model requires the rank count (per dimension, where applicable) to
divide the payload and rejects non-integral chunking at execution time
(O1, `A-L*-DIV` entries).

## Requirements

Numbers below are measured on the reference machine (Apple-silicon Mac,
2026-10-28, warm pip download cache — a first run on a new machine adds
package download time), evidence label `IMPLEMENTED_UNVERIFIED`:

- **Python 3.10+** (`pyproject.toml` `requires-python`; CI matrix runs
  3.10–3.13) — needed by `make bootstrap`.
- **Docker** — needed only by the two DES legs of `make demo` (the
  ASTRA-sim container run and the figure registration that renders from
  its record). Any recent Docker Engine with bind-mount support works;
  verified with Docker CLI/Engine 29.8.2 (OrbStack) on macOS arm64. When
  the `docker` CLI is absent or the daemon is unreachable, `make
  demo` runs in **no-Docker mode**: every L0-only leg runs
  unchanged, the two Docker-dependent legs are skipped with exactly what
  was skipped and the requirement printed, and the command exits 0. A
  present-but-missing pinned image is not skipped — the run stops there
  naming the rebuild step.
- **The pinned image** `essun/astra-sim-analytical:s1` (id
  `sha256:bb02b612…`, ~1.3 GB, linux/arm64, local-only — never pushed):
  build it from `backends/docker/astra-sim.Dockerfile` per
  `backends/docker/astra-sim-runbook.md`. The recorded build log
  (`backends/docker/build_s1.log`) sums to about five minutes of step
  time on the reference Mac. On x86-64 hosts, rebuild from the same
  Dockerfile (the pinned `ubuntu:22.04` base is multi-arch).
- **Disk:** repo export ~48 MB of tracked blobs (47.8 MB measured
  2026-10-29; the `git archive` zip is ~8 MB) + venv ~36 MB + content-addressed
  `results/` < 1 MB after a gate run + the ~1.3 GB image when built.
- **First-run time** (fresh `git archive HEAD` tree, image already
  built): `make demo` completes in ~11 s with Docker (bootstrap ~7 s
  + all legs), ~10 s in no-Docker mode (bootstrap + the L0-only legs).

## Commands

```bash
make help               # list all make targets (the default goal — a bare `make` prints this)
make bootstrap          # create .venv and install the package + dev deps
make validate-schemas   # draft schemas and examples
make test               # schema, golden, negative, determinism, observables, evidence, backends tests
make run EXP=experiments/vertical_slice/w1_decode_smoke.yaml
make run EXP=experiments/vertical_slice/w2_prefill_smoke.yaml
make run EXP=experiments/vertical_slice/w1_decode_torus2d.yaml
make run EXP=experiments/vertical_slice/w1_decode_smoke_astra.yaml
make sweep EXP=experiments/sweeps/l0_allreduce_design_space_v1.yaml
make paper-check        # placeholder-discipline check over paper/
make demo          # the public-gate story end-to-end (see "Public gate status" below)
make ci-local           # CI-equivalent chain: bootstrap + validate-schemas + test + paper-check
make clean              # remove regenerable Python build/test caches (never touches results/)
```

The 30-minute guided path — run a small analysis, change a free parameter,
see the predicted effect, submit a workload contribution — is in
[docs/usage.md](docs/usage.md).

## Public gate status

One documented command produces the public-release gate's evidence chain
end-to-end:

```bash
make demo          # tools/gate_demo.sh — every step summarized, any failure stops the run
```

The command chains: venv bootstrap (only when `.venv` is missing) →
`make validate-schemas` → `make test` → the W1 smoke run on the analytical
L0 backend, checked against the golden run id pinned in
`experiments/vertical_slice/w1_decode_smoke.GOLDEN.md` → the same W1 smoke
workload on the pinned ASTRA-sim analytical container backend (checked
against the run id that `tools/make_figure.py` pins as its default source)
→ `make sweep` on the AllReduce design-space grid → figure rendering +
registration via `tools/make_figure.py` → `make paper-check`, which also
applies the placeholder-discipline rules to
this README section. The sweep leg runs
`experiments/sweeps/l0_allreduce_design_space_v1.yaml` by default; the
cross-design grid (UEC vs paper-derived UnifiedBus,
`experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml`) has since
landed and runs via the same `SWEEP_MANIFEST=…` override. The ASTRA leg
needs the pinned Docker image
`essun/astra-sim-analytical:s1` (verified by id; build it per
`backends/docker/astra-sim-runbook.md` if absent). When the `docker` CLI
is absent or the daemon is unreachable, the same command runs in
no-Docker mode: the L0-only legs run unchanged and the two
Docker-dependent legs are skipped, with exactly what was skipped and the
  requirement printed (see Requirements above). The full chain,
  including the cold `git archive HEAD` verification, is exercised by the
  command itself on every run.

Gate legs demonstrated by `make demo` (all evidence level E0, label
`IMPLEMENTED_UNVERIFIED` — identities and determinism, no empirical claim):

- **Fidelities — demonstrated.** The same W1 Dense TP Decode workload runs
  through an analytical closed-form backend (L0 ring) and a discrete-event
  backend (pinned ASTRA-sim analytical in Docker), producing two
  content-addressed run records that the cross-backend difference engine
  compares (`tests/validation/test_diff_engine.py`, exercised by the
  `make test` leg when the records are present).
- **Reproducibility — demonstrated.** Every artifact the command emits is
  a deterministic function of committed inputs: both run records
  regenerate byte-identically (the L0 golden check runs inside the
  command), the sweep table replays byte-identically, and the figure plus
  its provenance README regenerate byte-identically from the run records.
  The evidence store itself is git-ignored and rebuilt by these commands.
- **Anchors — demonstrated.** The `make test` leg includes the
  anchor-integrity suites: the license-gated UEC source registry
  (`experiments/uec/anchor_registry.yaml`, page-hash and verbatim-quote
  recomputation, permanent license-gate test) and the paper-derived
  UnifiedBus registry (`experiments/unifiedbus/anchor_registry.yaml`,
  PUBLIC_READ-only sources).

Gate legs still open:

- **A normative second standard.** As of 2026-10-28 the
  paper-derived UnifiedBus profile carries public-gate leg 2 with its
  honest not-normative label; UEC remains the only license-cleared
  normative profile, and the normative upgrade of leg 2 stays blocked on
  the license review (covering UALink/OCP/CXL and restricted texts).
- **Calibration execution.** No observable is calibrated against hardware;
  the calibration plan (`docs/calibration/CALIBRATION_PLAN.md`) is PROPOSED
  and no E2/E3 step has run. The anchor split for the execution ladder is
  recorded (2026-10-30): 18-anchor calibration set vs 4-anchor holdout
  (CAL-A4, GF-01, GF-03, GF-11), content-addressed record `3862e227…`
  committed before any fitting (`experiments/calibration/split/`).

Run-record pointers (content-addressed store, regenerated by the commands
above, not committed): L0 golden
`146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1`;
ASTRA twin
`c6dc87eb58791438a4a9050238bc8347418228fb63e6df428fb27d3c0b35ab0c`.

## What the demo does not show

The UEC profile's semantics bind documentation and L1 contracts today; they
do not yet change any L0 number — every numeric model value stays an
explicit free parameter. The cross-standard table (UEC vs paper-derived
UnifiedBus) is parameter-flavored: both columns share the same free
parameters, so its delta is zero by construction, not a measured
difference between standards. Nothing is calibrated against hardware: the
evidence ceiling is `IMPLEMENTED_UNVERIFIED` and the calibration plan
(`docs/calibration/CALIBRATION_PLAN.md`) is `PROPOSED`, unexecuted. Softening any line
above while the state is unchanged is what would make this dishonest —
each line flips only with an evidence record to cite.

## Layout

What ships in HEAD:

```text
src/essun/            contracts, W1/W2/W3/W5 workloads, analytical L0 family (5 models) + L0.5,
                       specir UEC 1.1 / UnifiedBus-paper profiles + reconciliation,
                       observables registry, evidence store, orchestrator + sweeps
experiments/           experiment manifests, workloads, topologies, sweep grids,
                       UEC/UnifiedBus anchor registries (immutable inputs)
tests/                 schema / golden / negative / determinism / observables / evidence / backends / specir
paper/sections/        heading-only skeleton with [RESULT: ...] placeholders
backends/pins/         pinned external backends: commit, license, capability matrix, build log
backends/docker/       Docker builds + runbooks: ASTRA-sim analytical, csg-htsim, uet-htsim (build/smoke logs)
results/               generated, content-addressed run records and sweep tables (git-ignored)
docs/usage.md         the 30-minute path: run an analysis, change a free
                       parameter, see the effect, submit a contribution
docs/calibration/      calibration plan and anchor records
schemas/               draft JSON Schemas + examples/ input pairs (promotion
                       history in ADR-0002)
```
