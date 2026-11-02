---
name: Comparison submission
about: Submit a scale-up fabric operating point for the community table — format v0, machine-checked before review
labels: ['submission']
---

This template is the door for **comparison submission v0**: one
operating point — a workload, the shared free-parameter record, one or
two arms over committed topology files, and results that cite run ids.
The full spec is
[`docs/submission-format.md`](../blob/main/docs/submission-format.md);
the worked example is
[`examples/submission.example.yaml`](../blob/main/examples/submission.example.yaml).

Before posting, validate locally from a clone (the door rejects
malformed input by design; the error names the field):

```
make check-submission FILE=your-submission.yaml          # format + fairness
make check-submission FILE=your-submission.yaml VERIFY=1 # + store gates
```

House rules that shape the review:

- **Run id or it didn't happen.** Every reported value cites
  content-addressed run ids and must equal the stored observation
  exactly at review. Numbers that trace to nothing are refused.
- **Fairness is checked, not asserted.** The arms may differ only on
  the axes you declare; shared parameters are read out of the committed
  topology files; a `control: true` pair must report exactly equal
  values.
- **Committed inputs only.** Topology files, workload files, and
  manifests must be reachable from the public tree (new files land by
  PR first; license review precedes ingestion of any standard document).
- **No self-review.** Post the submission fields only; the maintainer
  appends the review block after re-executing the cited runs.

## The submission document (required)

Paste the full YAML (same fields as the example; no `review` block):

```yaml
<paste the submission YAML here>
```

## Validation output (required)

Paste what `make check-submission` printed (both runs if you ran
`VERIFY=1`):

```
<paste the validator output here>
```

## What the operating point shows (one sentence, factual)

<one sentence: which arms, which axis, what the numbers are — no claim words>

## Environment

- Commit the runs were executed at (`git rev-parse HEAD` in that tree):
- OS and CPU arch:
- Python inside the venv (`python --version`):
