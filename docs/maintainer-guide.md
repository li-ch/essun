# Maintainer guide

This guide is for the person taking over maintenance of essun. It assumes
you are a competent developer who has read the [README](../README.md) and
[docs/usage.md](usage.md); it does not re-explain the project, it tells you
how to keep it honest. Every command below was executed against this
repository on 2026-10-30 and the quoted results are the real output of that
run. When a number below drifts, trust the command, not this sentence.

The one-sentence job description: essun trades convenience for
traceability. Every numeric claim traces to a content-addressed run
record, every standard-derived value to a verbatim quoted anchor, every
executed requirement to a checked binding. Most of your work as maintainer
is running the gates that keep those sentences true, and refusing changes
that quiet them down.

## Where everything lives

| Registry | Location | What it is |
|---|---|---|
| JSON schemas | `schemas/*.schema.json` | Draft contracts, one per record type; a schema change is a public interface change — version it and announce it in `CHANGELOG.md` |
| Assumption registries | `experiments/vertical_slice/assumptions_*.yaml` | Every free parameter, one file per model family so unrelated additions cannot shift each other's run ids; the approval overlay is `assumptions_approvals.yaml` |
| Evidence store | `results/` (git-ignored) | Append-only, content-addressed run records; rebuilt by rerunning manifests, never committed, never pruned |
| Goldens | `experiments/vertical_slice/w1_decode_smoke.GOLDEN.md`, per-family `*.EVIDENCE.md` | The pinned run ids a rerun must reproduce; the re-store log records why an id ever changed |
| Dispositions | `tests/specir/test_dispositions.py` | The frozen review record: `EXPECTED_COUNTS` per module plus the `PROMOTED` table of every consciously promoted requirement |
| Bindings | `src/essun/specir/bindings.py` | Machine-readable requirement-to-backend bindings; re-verified live on every test run |
| UEC anchors | `experiments/uec/anchor_registry.yaml` (+ `source/` extracted pages) | Verbatim, page-hash-verified citations; the PDF itself never enters git |
| Source/license records | `experiments/uec/source_record.yaml`, `experiments/unifiedbus/source_record.yaml` | Verbatim provenance rows for ingested documents; re-copied verbatim, never paraphrased |
| Semantic profiles | `experiments/uec/semantic_profile.yaml`, `experiments/unifiedbus/` | Generated artifacts (see below); regenerated, not hand-edited |
| Observables | `src/essun/observables.py` | The observable registry with kinds and failure policies |
| Calibration records | `experiments/calibration/` | Immutable split and fit records, each with its builder and guard test |
| Coverage of profiles | `make disposition-report` (live, from `src/essun/specir/`) | Per-disposition counts; never a stored table |
| Site checks | `tools/site_gates.py` | Link/HTML/forbidden-string gates for `site/` |

Component-by-component status is [docs/status.md](status.md); the
reproduction card for the executed credit/TFC family is
[docs/reproduce-flagship.md](reproduce-flagship.md); the design-space
catalog is [docs/atlas/](atlas/README.md).

## The make targets and what each proves

Run `make` or `make help` for the live target list (it is generated from
the Makefile's `##` comments, so it cannot go stale). Python 3.10+;
Docker is needed only by the two discrete-event legs of `make demo`.

- **`make bootstrap`** — creates `.venv` and installs the package with dev
  extras (`pip install -e ".[dev]"`). Roughly ten seconds with a warm pip
  cache. Never delete a live `.venv` while another gate is running; if you
  must, expect every in-flight leg to break.
- **`make validate-schemas`** — runs only `tests/schema`. Today: `183
  passed` in about a second. Proves: every committed example **and every
  real input file under `experiments/`** validates against the draft
  schemas. This is the fastest meaningful gate; run it before anything
  else after touching YAML.
- **`make test`** — the full pytest suite. Today: `2297 passed, 92
  skipped in 8.52s` (clean clone at the commit this guide landed). Proves,
  per directory: hand-derived golden values
  (`tests/golden/` — expectations are written in the tests, never pasted
  from output), loud rejection of bad inputs (`tests/negative/`),
  byte-identical replay of runs and sweeps (`tests/determinism/`),
  observable behavior (`tests/observables/`), evidence-store integrity
  (`tests/evidence/`), backend contracts (`tests/backends/`), and the
  profile gates — dispositions, bindings, anchors, calibration guards
  (`tests/specir/`, `tests/calibration/`).
- **`make run EXP=path/to/manifest.yaml`** — executes one experiment
  manifest and stores a content-addressed record under
  `results/<run_id>/`. The id is a SHA-256 over the run's content
  (manifest, resolved inputs, emitted observables): same inputs, same id,
  byte-identical record. The golden check:
  `make run EXP=experiments/vertical_slice/w1_decode_smoke.yaml` must
  print `run_id` `146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1`
  (verified today). A rerun that changes this id without a manifest or
  code change is a bug, not a refresh — see the re-store log in the
  GOLDEN doc for the two closed breakage classes.
- **`make sweep EXP=path/to/sweep.yaml`** — runs a parameter grid into one
  comparison table under `results/sweeps/<sweep_id>/table.{json,md}`. The
  design-space grid `experiments/sweeps/l0_allreduce_design_space_v1.yaml`
  reproduces `sweep_id` `12700ede…` (verified today).
- **`make paper-check`** — runs `tools/paper_check.py` over every
  `*.md` under `paper/`. Today: `PASS — 15 file(s) checked, 0
  violations`. Proves the paper-writing rules: no fabricated numbers, no
  frozen claim vocabulary, no dangling `results/` references (details in
  the evidence-labels section below).
- **`make disposition-report`** — prints the per-profile disposition
  coverage report, computed live from `src/essun/specir/` (a stored table
  could drift; this cannot). Today: UEC 1.1 profile 445 requirements —
  187 informational / 254 unsupported / 3 simulated_behavior / 1
  conformance_test, 4 executed (0.9%), 67 free parameters; UnifiedBus
  paper-derived profile 54 requirements, 0 executed; platform total 499 /
  4 executed. `--json` for machine-readable output
  (`.venv/bin/python tools/disposition_coverage.py --json`). The zeros
  and the unsupported column are the point of the report, not an
  embarrassment; do not "improve" them by relabeling.
- **`make coverage`** — installs pytest-cov if needed, runs the full
  suite with line coverage over `src/essun`. Today: `TOTAL … 91%`, suite
  green, ~8 s. (Note: this target has no `##` help comment, so `make
  help` does not list it — it exists and works.)
- **`make ci-local`** — `bootstrap validate-schemas test paper-check`,
  the exact sequence `.github/workflows/ci.yml` runs on every push
  (Python 3.10–3.13 matrix). Run it before pushing if you have touched
  anything CI sees.
- **`make demo`** — the whole public-gate story end to end via
  `tools/gate_demo.sh`: bootstrap-if-needed, schemas, suite, the L0
  golden run (id must equal the GOLDEN doc's), the ASTRA-sim twin run on
  the pinned Docker image (id must equal the `DEFAULT_ASTRA_RUN` pinned
  in `tools/make_figure.py`), the design-space sweep, figure registration
  (`tools/make_figure.py`, renders the provenance-linked O-CCT figure
  from the two run records), and paper-check. First failure stops the run
  with that step's output tail. Without Docker the two Docker-dependent
  legs are skipped with the requirement printed (install Docker, build
  `essun/astra-sim-analytical:s1` per
  `backends/docker/astra-sim-runbook.md`) and the L0-only legs still
  gate; Docker present but the pinned image missing is a hard failure by
  design. Last full-Docker verification: 2026-10-30 at commit `1cefa6e`,
  PASS, all steps green.
- **`make clean`** — removes regenerable Python caches only. It is
  fenced: it never touches `results/` (immutable evidence), `.venv/`
  (bootstrap-owned), `backends/` (pinned, expensive rebuilds), or
  `.cache/` (license-reviewed source material).

## How to review a profile change

A profile is the set of typed requirement objects exported by the stage
modules under `src/essun/specir/` (`uec_link_transport.py`,
`uec_reliability_ordering.py`, `uec_congestion_management.py`,
`uec_credits_flow_control.py`, `uec_f07_mechanisms.py`, and
`unifiedbus_paper_profile.py`). Every requirement carries a **disposition**
from a six-value vocabulary: `constraint`, `simulated_behavior`,
`conformance_test` (the three kinds that count as executed), and
`informational`, `unsupported`, `not_applicable` (carried, not executed).
Declared free parameters carry no disposition by design and are reported
as a separate count.

Review checklist, in the order the gates will hit you:

1. **Disposition changes are conscious.** `tests/specir/test_dispositions.py`
   holds the frozen record: `EXPECTED_COUNTS` (per-module counts) and the
   `PROMOTED` table (requirement id → note, for everything whose
   disposition was ever deliberately moved off its keyword default). If a
   change moves a disposition, both must be updated in the same commit or
   the suite fails. There is no path to a silent promotion; keep it that
   way. Run `make disposition-report` before and after and put the
   before/after counts in the pull request.
2. **`simulated_behavior` requires a binding.** A requirement may claim
   execution only when `src/essun/specir/bindings.py` binds it to a
   backend capability/parameter that causally affects outputs. The
   binding names the requirement (with its anchors), the backend and its
   concrete parameters, the law executed, the structural invariants, and
   the observables it can move; `check_binding` re-verifies every claim
   against the live requirement registry, the live anchor registry, the
   live backend module, and the observable registry on every test run. A
   binding whose backend lost its parameter, whose requirement was
   reworded into a different anchor, or whose observables fell out of the
   registry is a hard error, never a silent drift. The honesty contract:
   `simulated_behavior` is a claim about the binding, not about physical
   validity; numeric parameters stay free except where a spec-derived
   constant is named with its requirement id.
3. **`conformance_test` is a check, not a binding.** Per the profile
   rules, a profile binding may reference only a `simulated_behavior`
   requirement; a conformance disposition is carried by golden tests plus
   the profile's `checks` entries (see `UEC11-CHK-*` in the built profile
   and `tests/golden/test_credit_arrival_golden.py` for the worked
   example).
4. **Anchors must resolve.** Every standard-derived value cites an anchor:
   id, section, page, a verbatim quote of at most 30 words, and the
   sha256 of the extracted page file. The registry
   (`experiments/uec/anchor_registry.yaml`, built by
   `experiments/uec/build_anchor_registry.py` from `experiments/uec/source/`)
   is verified offline by `tests/specir/test_uec_anchor_registry.py`:
   re-hashed pages, re-matched quotes. A hand-edited registry, a stale
   extraction, or a dangling anchor id is a hard error. Never retype spec
   text into code; cite the anchor. Never invent a normative value —
   declare a free parameter instead.
5. **Rebuild the generated profile and require byte-identity.** After any
   change under `src/essun/specir/`, run

   ```bash
   .venv/bin/python experiments/uec/build_semantic_profile.py
   git diff --stat experiments/uec/semantic_profile.yaml   # must be empty
   ```

   (verified today: the rebuild is byte-identical). The builder reads
   dispositions from the live registry and cannot assign or change any;
   if the artifact changed, your change is visible in it — review the
   diff and bump the artifact's version per the bump rules in its header.
6. **Run the suite.** `make test` re-runs all of the above plus the
   binding-coverage and artifact-parity gates.

License fence: ingestion of any standard document is preceded by a license
review recorded verbatim in the `source_record.yaml` files. Restricted
text never enters this repository; if a change proposes to add any, stop.

## How to add a calibration record

The calibration work keeps its data split immutable and its records
append-only. The committed pattern to copy, stage by stage:

- **The split record** (`experiments/calibration/split/`): before any
  fitting, the data split — which anchors are fit targets, which are
  held out for evaluation only, which are blocked — is committed as a
  content-addressed record (`anchor_split_v1.json`) with its
  deterministic builder (`build_anchor_split_record.py`). The record is
  immutable: changing the split requires a new record (`split_v2`), never
  an edit in place.
- **The fit records** (`experiments/calibration/s2/`, `s3/`, `s4/`): each
  fitting stage holds its manifests (`run_*.yaml`, `sweep_*.yaml`),
  topologies and profiles, a deterministic builder (`build_fit_record.py`
  — a pure function: no wall clock, no host metadata, identical reruns
  produce byte-identical records), and the committed record
  (`fit_record_v1.json`, id = sha256 over the canonical JSON + newline).
- **The guard test** (`tests/calibration/test_s4_fit.py`, and the s2/s3
  and split equivalents): re-executes the stage's whole evidence chain
  into a scratch store, rebuilds the record byte-identically, and checks
  the separation invariants — no holdout anchor id or number appears in
  the fit record, every run's v2 evidence dimensions declare their
  calibration target and held-out flag, and the free-parameter registry
  values are untouched by the fit.

To add a new record:

1. Create the stage directory under `experiments/calibration/` with
   schema-valid manifests, topologies, and profiles (copy the naming
   conventions from `s4/`). Fit only against anchors the split record
   assigns to your group; the holdout set is evaluation-only, ever.
2. Write the builder as a pure function that emits the record and its
   content-addressed id. Commit the record bytes.
3. Add the guard test under `tests/calibration/` following
   `test_s4_fit.py`: scratch-store re-execution, byte-identity, and the
   separation invariants for your stage.
4. Register any new modeling choice as an explicit free-parameter entry
   in the right `assumptions_*.yaml` file — a new file if it must not
   shift existing run ids (the per-model split exists for exactly this).
5. Run `make test`, then append a `CHANGELOG.md` entry. Fit candidates
   are `PROPOSED`; a fit record alone upgrades no label and changes no
   shipped parameter value — fitted values are recorded diagnostics
   pending review, and the holdout discipline (calibration and validation
   data stay separate; never validate on the dimension that was fitted)
   is not negotiable. If a fit misses, the miss is the finding; never
   tune parameters until curves look similar.

## How to cut a release

Nothing has been tagged or published yet; this is the mechanics for when
you do. Cutting a release is a maintainer action — do not tag
automatically from CI.

1. **Close the change log.** The `[Unreleased]` section of
   `CHANGELOG.md` is the running draft of the next release's notes.
   Every entry carries an evidence label (or an explicit
   `documentation-only` / `no-label` marker). Under the version heading,
   move the entries unchanged — the section *is* the release notes draft.
2. **Verify from a cold tree.** From a fresh clone: `make bootstrap`,
   `make demo` (with Docker, so the discrete-event and figure legs run),
   `make test`, `make paper-check`. The demo's golden-id checks are the
   release's reproduction guarantee; do not tag over a red or skipped
   leg you cannot explain.
3. **Tag.** `git tag -a vX.Y.Z -m "essun vX.Y.Z"` then
   `git push origin vX.Y.Z`. Versioning intent is SemVer. GitHub release
   notes are derived from the changelog section — keep the labels in.
4. **Site.** `.github/workflows/pages.yml` deploys `site/` to GitHub
   Pages on every push to `main` (and on manual dispatch). Before
   changing site content, run `python3 tools/site_gates.py site` — it
   checks internal link resolution, HTML sanity, and forbidden strings,
   stdlib only. Pages deployment is workflow-based; the one-time enable
   command is recorded in the header of `pages.yml` itself.
5. **Pinned images.** `.github/workflows/docker-pins.yml` rebuilds the
   pinned Docker images weekly on schedule as a drift alarm; a red build
   there means an upstream pin moved, and the fix is a deliberate re-pin,
   never an auto-repair.

The README's honesty sections ("What essun does not do", quality claims)
must be true at the tag. If the release adds a capability, the README
status and the component table in `docs/status.md` move in the same
commit as the tag candidate.

## Evidence labels and the forbidden-claims check

The evidence ladder is `PROPOSED` / `IMPLEMENTED_UNVERIFIED` /
`VERIFIED` / `CALIBRATED` / `EXTERNALLY_REPRODUCED`. Operating rules:

- Never present a designed capability as a completed result; a result may
  carry different labels for different claims.
- Pick the lowest honest rung. Code that exists and passes the suite but
  has not been reproduced outside this tree is `IMPLEMENTED_UNVERIFIED`
  at best — today that is the entire repository's ceiling (the README
  says so; keep it saying so until evidence exists).
- Put the label in the commit title (`... [IMPLEMENTED_UNVERIFIED]`).
  When a commit cites earlier labeled work, reproduce the label it
  carried — a citing party cannot upgrade it.
- Paper-facing numbers stay `[RESULT: metric, experiment, status]`
  placeholders until an immutable run record exists, and a claim without
  a run id is an opinion.

`make paper-check` (`tools/paper_check.py`) mechanically enforces the
prose side of those rules over every `*.md` under `paper/`:

- **R1 — numbers.** A measurement-like number outside a
  `[RESULT: ...]` span or a citation bracket fails. Allowlisted contexts:
  heading numbering, `Section/Figure/Table/rule N` references, semantic
  versions, years, IEEE designators, letter-prefixed identifiers (F5,
  RQ2, W1), and fenced code blocks.
- **R2 — claim words.** The frozen vocabulary (case-insensitive,
  word-boundary) fails outside a `[RESULT: ...]` span: `first`, `novel`
  and its inflections, `validated`, `production-ready`, `SOTA`, the
  spaced and hyphenated state-of-the-art forms, and the hype forms
  (`cutting-edge`, `best-in-class`, `industry-leading`,
  `unprecedented`, `revolutionary`, `groundbreaking`, `world-class`,
  `industrial-grade`, `battle-tested`, `production-proven`, `seamless`,
  `seamlessly`). The tuple in `tools/paper_check.py` is the single
  source of truth; `tests/schema/test_paper_check.py` parametrizes over
  it, so every form planted is asserted flagged and a form added gains a
  test case automatically. Extending the vocabulary is a deliberate,
  recorded decision — never a silent one.
- **R3 — figure references.** Any `results/` path on a line without a
  64-hex run id fails.

The same vocabulary discipline applies to everything public-facing
(README, docs, site, commit messages), even where only `paper/` is
mechanically checked — `tools/site_gates.py` covers the site. When a
backend disagreement surfaces, minimize and classify the counterexample
first; tuning parameters until the curves agree is the prohibited move.
