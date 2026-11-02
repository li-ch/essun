# Community operating-point submissions (committed copies)

This directory holds the committed copies of operating-point submissions
that came through the door — each file is one submission
(`docs/submission-format.md`, format v0) plus the maintainer `review`
block appended after the door and the store verification ran. It is
empty today: the door shipped with zero submissions, and this README is
the marker that the directory exists and waits.

What may live here (enforced, not asked):

- A file with a `review` block — a pending submission lives on its
  issue thread, not in the tree (`essun.evidence.submissions` rejects a
  review-less committed copy).
- `review.decision: published` only with every cited run id listed in
  `review.verified_run_ids` — the reviewer's record of which ids
  re-executed byte-for-byte from the committed manifests.
- Rejected submissions too: they render in the public table
  (`site/community.html`, via `tools/community_table.py`) with their
  decision, so refusals are as visible as acceptances.

Validate everything here: `python -m essun.evidence.submissions
--community .` from the repo root; re-render the table with
`python3 tools/community_table.py` (the suite fails if the page and
these records drift apart).
