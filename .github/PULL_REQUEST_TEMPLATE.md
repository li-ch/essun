# Pull request

Commits on this branch each carry an evidence label in the title
(`PROPOSED` / `IMPLEMENTED_UNVERIFIED` / `VERIFIED` / `CALIBRATED` /
`EXTERNALLY_REPRODUCED`, per `CONTRIBUTING.md`), and no number enters
prose while only a placeholder can back it. This form keeps the PR in
the same discipline. CI runs the gate chain on push; `make ci-local` is
the exact local equivalent.

## What changes and why

One paragraph: the behavior change, the input or contract it touches,
and the effect a user sees. Interface-affecting decisions (public
schemas, research claims, source permissions, paper scope) additionally
need a short decision record (context, options, decision) — add it here.

## Which tests pin the change (required)

Name the tests that fail before this branch and pass after it, and
where each expected value comes from. The golden rule applies:
expectations are written in the test source — a closed form, a schema
rule, or a pinned id — and never derived from the implementation under
test.

- Test file / case:
- Source of its expected values:
- Schema or contract changes: the negative cases that ship alongside
  (a draft-schema change without negative tests is incomplete here):
- If nothing pins the change, say why — that is information, not a
  failure state, but an untested change cannot carry an evidence label
  above `PROPOSED`.

## Determinism impact (required)

Run ids are content-addressed over committed inputs; reruns must
reproduce them byte for byte. State plainly:

- Do any run ids or pinned goldens change? (Compare the ids printed by
  `make run` and the pinned goldens before and after this branch.)
- If yes: the exact input difference that produces the new id — a
  change to a manifest, topology, workload, or code. A parameter moved
  to make two backends agree is not an acceptable cause: a
  disagreement is minimized and classified as a counterexample before
  any parameter moves (classify-don't-tune).
- If no: write `ids unchanged` and name the rerun check that shows it.

## Gates (paste each summary line)

- `make test`:
- `make demo` (name the mode that ran — full or no-Docker):
- `make paper-check`:

## Paper and README impact

Does any README status line, evidence label, or paper `[RESULT: ...]`
placeholder move because of this change? Numbers stay placeholders
until an immutable run record exists to cite.
