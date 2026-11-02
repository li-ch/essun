# Comparison submission v0: format, door, and fairness procedure

Status: **PROPOSED** (the machinery is implemented and tested; the door
has never been walked through — zero submissions exist, so every
statement below about the table is about what *would* happen, not what
has). Scope: how ANYONE submits a scale-up fabric operating point —
workload, shared free parameters, arms, results with run ids — what the
door checks before a human looks at it, and how a submission reaches the
community table. This is a CONTRIBUTING path plus an issue template,
not an institution: no membership, no committee, no calendar. Companion
pieces: [submission-format example](../examples/submission.example.yaml)
(the worked instance), the
[comparison-submission issue template](../.github/ISSUE_TEMPLATE/comparison-submission.md)
(the door), the site's Community page (where the table renders), and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) §"Submitting an operating point".

## The one rule

A number enters the table only if it traces, exactly, to a run id that
regenerates from the public tree. Concretely: every result row cites
content-addressed run ids; the review step re-executes the cited
manifests and refuses any submitted value that does not equal the stored
observation exactly. No run id, no number; no match, no row. The
validator (`src/essun/evidence/submissions.py`) rejects malformed input
by design — the malformed classes are pinned by tests, and the error
messages name the field.

## The document

One YAML mapping, exactly these fields (schema:
`schemas/submission.schema.json`; worked example:
`examples/submission.example.yaml`). Unknown fields are rejected — the
format cannot grow silently.

| Field | What it is |
| --- | --- |
| `format_version` | `0` (this spec) |
| `submitted` | ISO date the submission was posted |
| `submitter` | public identity, as declared in the source thread |
| `source_url` | public, auditable pointer to the submission (issue/PR) |
| `essun_commit` | full hash of the public tree the cited runs were executed at |
| `backend` | a backend id (`essun.evidence.submissions.BACKENDS`, the `BACKEND_ID` constants of the backend modules) |
| `workload` | `{kind, parameters}` — a workload generator kind (`w1_dense_tp_decode`, `w2_dense_tp_prefill`, `w3_moe_dispatch_combine`, `w5_pd_kv_prefill_decode`) with its integer shape parameters |
| `shared_parameters` | `{record, values}` — ONE free-parameter record both arms consume unchanged, and the shared `{id: value}` binds |
| `arms` | one or two arm blocks: `{label, profile, topology, parameters}` |
| `comparison` | two arms only: `{differs_on, control}` |
| `results` | non-empty list of `{arm, observable, metric, value, run_ids}` |
| `review` | maintainer-appended only; refused at the door |

Arm blocks:

- `label` — unique within the submission; results reference it.
- `profile` — the standard-profile vocabulary. At v0 this is `("none",)`
  because `experiments/vertical_slice/profiles/standard_profile_none.yaml`
  is the only standard-profile input any landed backend consumes; fabric
  semantics at L0 enter through the topology file's honesty headers.
  The semantic profile documents (`experiments/uec/semantic_profile.yaml`,
  `experiments/unifiedbus/semantic_profile.yaml`) are anchor registries,
  not run inputs — the vocabulary widens only when a backend consumes
  one, which is a code change with a spec bump to v1 (a drift-guard
  test keeps the vocabulary and the tree honest with each other).
- `topology` — a repo-relative COMMITTED topology file path. Not a URL:
  a submission must be re-runnable from the public tree.
- `parameters` — arm-local free-parameter binds (`{id: positive int}`),
  possibly empty; may not shadow an id in `shared_parameters.values`.

Results rows: `observable` must be registered in the observables
registry (`src/essun/observables.py`); `metric` names the field of the
observation holding the value (e.g. `completion_time_ns_max`); `value`
is exact — an integer or an exact numeric string; `run_ids` is a
non-empty list of 64-hex content-addressed ids ("a result without a run
id is an opinion").

## The three gate layers

**1. Door (no store needed).** `submission_problems()` checks structure
and vocabularies, then the declared fairness gates
(`fairness_problems()`), then — with the repo present — the tree gates.
Run it: `make check-submission FILE=your-submission.yaml`, or
`python -m essun.evidence.submissions your-submission.yaml`.

**2. Tree (door, repo present).** `tree_problems()`: the declared
topology files and the shared record must be committed files, and every
id in `shared_parameters.values` must resolve — through the record's
`parameter` spellings — to a knob each arm's topology file carries with
the declared value. This is the delta-zero check on inputs at the door:
the numbers claimed shared are read out of the files, not taken on
prose.

**3. Store (reviewer step).** `verify_against_store()`: every cited run
id exists locally (rebuild from the cited committed manifests); the
stored observation equals the submitted value EXACTLY; the stored run
executed on the declared backend; all runs cited by one arm share one
operating point; across arms `workload_ir`/`assumptions`/
`implementation_profile` inputs are IDENTICAL (the same-workload and
identical-open-choices rules read off the run records), while
`infra_graph`/`standard_profile` may differ only under a declared axis;
the run's manifest is a committed path; the declared workload
parameters match the runs' workload file; and the arm's declared
topology is the run's actual `infra_graph` input.

## Fairness, delta-zero-style

The bar is the cross-fabric matrix's own
("What a fair comparison requires",
[`docs/atlas/cross-fabric-matrix.md`](atlas/cross-fabric-matrix.md)),
enforced mechanically:

- **F1 — one axis, named.** The validator recomputes the fields the two
  arm blocks actually differ on and requires exact equality with
  `comparison.differs_on`. An undeclared difference is a smuggled
  asymmetry ("a comparison across different workloads is not a
  controlled ablation"); a declared axis that does not differ is a
  mislabeled comparison.
- **F2 — no shadowing.** An arm's `parameters` may not name a
  shared-record id: a per-arm override of a declared-shared parameter is
  how unequal inputs hide.
- **F3 — paired results.** Every (observable, metric) reported for one
  arm is reported for the other. A table that shows only one arm's
  number is not a comparison.
- **F4 — the delta-zero control.** `comparison.control: true` declares
  the arms numerically identical (the honesty-anchor pattern: the
  identity-matched pair whose delta must be exactly 0). The validator
  requires every paired value EXACTLY equal, and any reader can re-check
  by re-running the two manifests.

Single-arm submissions (one operating point, no comparison) skip F1–F4;
the structure, tree, and store gates still apply in full.

## Lifecycle

1. **SUBMITTED** — the issue (template above) carries the document.
   Pre-validate locally; the door's refusal names the field.
2. **REVIEWED** — the maintainer transcribes into
   `experiments/community/<name>.yaml`, runs
   `python -m essun.evidence.submissions <file> --verify` from a tree
   holding the rebuilt runs, and appends the `review` block:
   `{decision: published|rejected, reviewer, date, basis,
   verified_run_ids}`. `published` requires every cited run id in
   `verified_run_ids` (mechanically checked); a review naming runs the
   submission does not cite is refused; a submission may never carry a
   self-written review (refused at the door, like self-judged
   independence in reproduction records).
3. **TABLE** — `tools/community_table.py` renders
   `site/community.html` from the directory; the test suite fails if
   the page and the records drift, so the display cannot lag the
   evidence. Published and rejected rows render alike; nothing is
   filtered. A table row is not an evidence-label upgrade — these are
   analytical operating points under declared free parameters, ranked
   nowhere (the ladder in `CONTRIBUTING.md` is unchanged by this door).

The submission's identity is content-addressed
(`submission_id`: SHA-256 of the canonical-JSON fields, review
excluded), so appending a review never rewrites what was submitted.

## What v0 does not do (limits, deliberate)

- **One or two arms.** Three-way comparisons are two pairwise
  submissions or a format bump.
- **Fabric semantics ride committed files.** A new fabric enters by PR
  (topology file + honesty headers; license review precedes ingestion
  of any standard document — never paraphrase restricted text). The
  door accepts operating points over what the tree can run; it is not a
  profile-registry bypass.
- **W3's routing tables are not submittable parameters** (file
  artifacts, not scalars); submit the workload file by PR and cite the
  run.
- **The parameters axis covers free-parameter binds that live in
  topology or assumptions files**; there is no separate run-level
  parameter input at L0 today. If a future fidelity adds one, the axis
  mapping (`_AXIS_EXEMPT_INPUTS`) grows with it.
- **The table ranks nothing.** Ordering is (date, id); winners are a
  matrix question, not a submission one.

## How to reproduce this page's machinery

```bash
# the door on the worked example (format + fairness + tree gates)
.venv/bin/python -m essun.evidence.submissions examples/submission.example.yaml
# + the store gates (rebuild the cited runs first: make run EXP=...)
.venv/bin/python -m essun.evidence.submissions examples/submission.example.yaml --verify
# the committed records and the public table
.venv/bin/python -m essun.evidence.submissions --community .
python3 tools/community_table.py --check
```

Validator and renderer are deterministic (no wall-clock, no host state);
the suite holds the malformed-rejection, fairness-negative, and
store-refusal cases that pin this spec
(`tests/evidence/test_submissions.py`,
`tests/schema/test_submission_schema.py`,
`tests/evidence/test_community_table.py`).
