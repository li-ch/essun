# External reproduction: record type and verification procedure

Status: **PROPOSED** (the machinery is implemented and tested; the
procedure has never been exercised — no external reproduction exists, so
every statement below about labels is about what *would* happen, not
what has). Scope: how a public reproduction report becomes a record,
what makes a reproduction **independent**, and the only path by which
the `EXTERNALLY_REPRODUCED` label can land. Companion pieces:
[reproduce-flagship.md](reproduce-flagship.md) and the case-study cards
(what to run), the funnel issue
[#1](https://github.com/li-ch/essun/issues/1) (where reports land), the
site's Reproductions page (where attempts are displayed).

## The one rule

The record defaults to **unknown** and can never assert the label by
itself. Concretely:

- an **attempt** (the transcription of a public report) carries no
  judgment: its `independence` block is all `null` — a report about
  oneself is not a judgment about oneself. The validators reject a
  record that arrives with a self-judged criterion;
- an **adjudication** (maintainer action, below) is the only thing that
  changes the effective label away from `UNKNOWN`, and the mechanical
  gate in `src/essun/evidence/reproductions.py` refuses a verdict of
  `externally_reproduced` unless the attempt's outcome is
  `byte_identical`, the reproducer is not a repository author identity,
  and all four independence criteria are judged met with a note each.

Nothing in this repository may write `EXTERNALLY_REPRODUCED` anywhere —
page, README, paper — except as a rendering of an adjudicated record.
Until one exists, every surface states it as not yet attained.

## What a report must contain (the attempt fields)

A reproduction report on the funnel issue is transcribed into
`experiments/reproductions/<descriptive-name>.yaml` with exactly these
facts (schema: `schemas/reproduction.schema.json`):

| Field | What it is |
| --- | --- |
| `reported` | date the public report was posted |
| `report_url` | the public, auditable pointer (issue comment or equivalent) |
| `reproducer` | the public identity that ran it, as declared in the report |
| `reproduced_at_commit` | full hash of the public commit used |
| `environment` | machine / OS / Python / Docker facts as reported |
| `outcome` | `byte_identical`, `diverged`, or `incomplete` |
| `divergence_notes` | required when the outcome is not `byte_identical`: what diverged, and where the minimized/classified case lives |
| `reproduced_run_ids` | the stored run ids the attempt re-executed |

A report that only measures friction (the funnel issue's main ask) is
welcome and needs no record; a record is made when runs were actually
re-executed and ids compared.

## What counts as independent (the four criteria)

Independence is a property of the *attempt*, judged once, in an
adjudication, with a note per criterion stating what was checked:

1. **`distinct_hands`** — the reproducer is not one of the people whose
   work is being reproduced: the filing identity has no commits in this
   repository's history and is not a co-author of the reproduced runs.
   Mechanical floor: the reproducer must not match a repository author
   identity (the gate refuses otherwise — an author's own re-run is at
   best `VERIFIED`, the rung below). Limits, stated plainly: an
   adjudicator checks the public trail (account history, report
   contents) and can be fooled by a second account; the judgment and
   its basis are recorded precisely so others can re-derive or contest
   it.
2. **`distinct_machine`** — executed on hardware and an OS that are not
   the authors' working environment, from a fresh clone at the named
   commit. The environment field is the evidence; cross-platform
   agreement is itself signal (the store's determinism is
   platform-independent by construction, so a `byte_identical` outcome
   on a different platform is the meaningful version of this claim).
3. **`released_artifacts_only`** — nothing outside the public repository
   state was used: every reproduced run id, expected value, and command
   is derivable from the public tree at the named commit (the
   reproduction cards pin the expected ids, so this is checkable by
   reading).
4. **`public_report`** — the attempt and its raw outputs are publicly
   visible at `report_url`, so any third party can audit the report
   itself.

A criterion that cannot be established is judged `met: false` with the
reason in its note — unknown is never rounded up to met.

## The verification procedure (adjudication)

1. **Transcribe.** A maintainer turns the report into an attempt file
   (fields above, `independence` all null) and renders the board
   (`python3 tools/reproduction_board.py`). The page now shows the
   attempt with label `UNKNOWN` — visible before any judgment, which is
   the point.
2. **Check mechanically.** `python -m essun.evidence.reproductions
   <repo-root>` validates every committed record and, for attempts
   whose run ids are rebuilt in the local store, appends them to the
   append-only `results/reproductions.jsonl` (the store refuses run ids
   it does not hold — only immutable runs may be cited, the same rule
   as counterexamples and figures).
3. **Judge.** The maintainer writes the `adjudication` block: verdict,
   adjudicator, date, a basis an auditor can re-derive, and the four
   judgments. For `externally_reproduced` the gate additionally demands
   `outcome: byte_identical` and a non-author reproducer; a refusal
   names the unmet criterion.
4. **Handle divergences separately.** A `diverged` outcome never
   becomes a reproduction data point. It enters the standing
   counterexample policy — minimize, then classify, never tune until
   curves match — and its `divergence_notes` point at the minimized
   case. `incomplete` attempts (the walk stopped early) stay on the
   board as friction data with label `NOT_COUNTED` once adjudicated,
   which is wanted signal, not failure.
5. **Propagate.** Only after an adjudicated `externally_reproduced`
   record exists may any surface state the label: the site's
   Reproductions page and Evidence page flip their attainment marks,
   the README ceiling sentence moves, and new run manifests may cite
   the reproduction id in the `independent_reproduction` evidence
   dimension (`src/essun/evidence/dimensions.py`). Stored run records
   are immutable and are never edited to carry it — the citation lives
   forward, in new records.

## What this is not

- Not a certification of physical validity: a reproduced result repeats
  the modeling choices it inherits. Reproduction is orthogonal to
  calibration (the D3 dimensions); landing this label changes nothing
  about what the numbers mean.
- Not an institution: no submission portal, no fees, no listing rules
  beyond this file. The funnel issue, the cards, and this procedure are
  the whole apparatus.
- Not retroactive: reports pre-dating this policy can be transcribed
  and adjudicated like any other, but the label still lands only
  through the gate.
