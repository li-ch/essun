# Contributing

This file states the day-one basics of the project's operating rules. For
directories a new contributor will not recognize — `paper/`,
`docs/calibration/`, `docs/atlas/` — see `docs/usage.md` and the layout
map in the README; this file does not repeat them.

Four rules below shape every change here: golden tests, determinism,
evidence labels, run ids. Each is unpacked to its day-to-day meaning with a
pointer at the machinery that enforces it.

## Bootstrap

    make bootstrap      # .venv + editable install with dev extras (pytest)
    make test           # full suite
    make ci-local       # exact target sequence the CI workflow runs

Python >= 3.10 (CI matrix: 3.10–3.13).

## Test conventions

### Golden tests: expected values are written in the test

Golden tests spell expected values in the test source; expectations are
never derived from the implementation under test. What that requires:

- Derive the number by hand — a closed-form identity, a conservation law,
  independent arithmetic — and write it as a literal in the test
  (`tests/golden/`). `tests/golden/test_w1_l0_golden.py` is the pattern:
  its docstring pins the rule, and every expected value is recomputed from
  the stated identity, never from the implementation's output.
- Never run the code and paste its output back in as the expectation. A
  golden produced that way certifies whatever the code already does;
  "treating a compile or a plausible curve as semantic correctness" is
  prohibited conduct.
- If a deliberate change legitimately shifts a golden (e.g. a model's
  emitted-observable set changes), re-derive the expectation by hand,
  update the pinned id, and record why the old value ceased to be correct
  in the commit message and the golden's reference doc —
  `experiments/vertical_slice/w1_decode_smoke.GOLDEN.md` is the worked
  precedent.
- Schema and contract changes ship with negative tests alongside golden
  ones (`tests/negative/`): show the input being rejected and the error
  class, not only the happy path.

### Determinism is required

House rule, verbatim: "fixed tie-breaking, partitioned RNG streams, integer
byte counts; store seed/topology/hashes/config with every run. Runs with
different workloads are not controlled ablations."

For new code that means: no unseeded randomness and no wall-clock inputs;
any new ordering needs a fixed tie-break; byte counts stay integers; the
run record carries seed/topology/hashes/config. A rerun of the same
manifest must reproduce the same content-addressed id —
`tests/determinism/` replays runs and sweeps, and `make demo` fails
outright if a rerun's id differs from the pinned golden. The rule's last
clause cuts the other way: when comparing two configurations, change
exactly one input and name it — a comparison across different workloads
is not a controlled ablation.

## Commits carry an evidence label

The evidence ladder is `PROPOSED` / `IMPLEMENTED_UNVERIFIED` / `VERIFIED` /
`CALIBRATED` / `EXTERNALLY_REPRODUCED`, with the operating sentence: "Never
present a designed capability as a completed result. A result may carry
different labels for different claims."

- Put the label in the commit title, e.g. `... [IMPLEMENTED_UNVERIFIED]`;
  commits are read as claims, so label them like claims.
- Pick the lowest honest rung: code that exists and passes the suite but
  has not been reproduced outside this tree is `IMPLEMENTED_UNVERIFIED`
  at best — today that is the entire repository's ceiling (README,
  "What the demo does not show").
- When a commit or document cites earlier labeled work, reproduce the
  label it carried. Labels are evidence statements; a citing party cannot
  upgrade them.
- Paper-facing numbers stay `[RESULT: metric, experiment, status]`
  placeholders until an immutable run record exists, and the frozen
  claim-word vocabulary in `tools/paper_check.py` is enforced by
  `make paper-check`.

## Run id discipline: run_id or it didn't happen

Every execution — a manifest through `make run`, a grid through
`make sweep` — stores a content-addressed record under
`results/<run_id>/` (`run.json` + `observations.json`); the id is a
SHA-256 over the run's content (manifest, resolved inputs, emitted
observables; `src/essun/evidence/store.py`). Same inputs, same id,
byte-identical records; a different id means different inputs. That
property is what makes an id citable:

- Any behavioral claim — in a commit message, a bug report, or a golden
  change — cites a run id plus the manifest and commit that reproduce it.
  A claim without an id is an opinion.
- `results/` is git-ignored and rebuilt, never distributed; the durable
  citation is run id + manifest + commit, so anyone can regenerate the
  record and compare ids. `docs/usage.md` walks this end to end with
  real outputs.
- The public gate is this discipline under load: `make demo` fails
  unless the L0 run reproduces the golden id pinned in
  `experiments/vertical_slice/w1_decode_smoke.GOLDEN.md` and the DES
  twin reproduces the id pinned in `tools/make_figure.py`. A rerun that
  changes an id without a manifest or code change is a bug, not a
  refresh.
- A task is complete only when tests and generated artifacts are linked
  from the result.

## Interface-affecting decisions

Decisions that affect public interfaces, research claims, source permissions
or paper scope require a short decision record in the pull request —
context, options considered, the decision, and the affected source records
(`experiments/*/source_record.yaml`) — so the reasoning survives the change.
