---
name: Bug report
about: Behavior that contradicts what the repo documents or checks — demo tail and run id required
labels: ['bug']
---

Reports in this repo run on the same discipline as its claims: observed
behavior, reproduced from committed inputs, with the run id to prove it.
Two artifacts are required up front — the tail of a `make demo` run
and the run id — because together they let anyone replay what you saw.

House rules for the text you write:

- **Factual observed vs expected.** Anchor the expectation to where it
  is written (a test, a README section, a schema, a closed form in the
  docs). Avoid evaluation adjectives: this repo freezes a claim-word
  vocabulary for its own prose (`tools/paper_check.py`, rule R2) and bug
  text reads better without that vocabulary too.
- **Run ids are content-addressed.** Identical committed inputs must
  reproduce an identical id, byte for byte. Rerun the same command once
  and report both ids: a rerun that changes a run id with no change to a
  manifest, topology, workload, or code is itself the bug being
  reported. If you edited any committed input (even locally, unpushed),
  say so — the id is computed from the inputs, so an uncommitted edit is
  otherwise invisible to whoever reads this report.
- **Status claims carry evidence labels** (`PROPOSED` /
  `IMPLEMENTED_UNVERIFIED` / `VERIFIED` / `CALIBRATED` /
  `EXTERNALLY_REPRODUCED`). If the bug contradicts a labeled status
  line, name the label and where it is stated.

## `make demo` tail (required)

Run `make demo` on the tree where the bug appeared and paste
everything it printed from the failing step onward. On failure the tail
looks like this (step numbers vary with whether bootstrap ran and
whether Docker legs were skipped):

```
demo: FAIL — step 5/9: run W1 smoke (ASTRA-sim analytical, pinned container) failed — command: make run EXP=experiments/vertical_slice/w1_decode_smoke_astra.yaml
---- last 40 lines of 05_run_W1_smoke_ASTRA-sim_analytical__pinned_container_.log ----
…up to forty lines of the failing step's captured output…
--------------------------------------------------------
```

- If demo finished green, paste the final `PASS` status lines and
  the `gate artifacts:` line instead, and name the mode that ran — with
  Docker, or no-Docker. The no-Docker mode (announced by the command)
  skips the DES-run and figure legs by design; that skip is documented
  behavior, not a bug.
- A bug outside the gate chain (your own manifest, a schema, the docs)
  still needs this section: run demo once on your tree and paste
  the tail, so responders can rule the shared chain in or out before
  looking at your part.

Paste the tail here:

```
<paste the demo tail here>
```

## Run id (required)

If the bug involves `make run` or `make sweep`, paste the id the command
printed, and the id from one rerun of the same command (see the
content-addressing rule above). The `make run` output ends with:

```
{
  "run_id": "<64-hex content-addressed id>",
  "run_dir": "results/<the same id, the run-record directory>"
}
```

- For a sweep, paste the `sweep_id` the command printed instead.
- If the bug involves no run at all (schema validation, docs, tools),
  write `n/a` with one line saying why.

Run id, then rerun id:

```
<paste the run ids here>
```

## Steps to reproduce

Exact commands in order, starting from the tree state (a `git status`
note matters when any input was edited):

```
<paste the commands here>
```

## Environment

- OS and CPU arch:
- Python inside the venv (`python --version`):
- Gate-demo mode on this tree (full / no-Docker / Docker not installed):
- Commit (`git rev-parse HEAD`):

## Observed vs expected

- Observed:
- Expected, and where that expectation is written:
