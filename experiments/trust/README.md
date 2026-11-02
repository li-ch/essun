# Trust dashboard state (generated)

This directory holds the trust dashboard's only state:

- `indicators.yaml` — the snapshot `site/trust.html` renders from.
  Its `repo` section (reproduction attempts, adjudicated external
  reproductions, community submissions) is re-derived from the
  committed tree by every render; its `github` and `citations` sections
  are fetched from their public APIs by `tools/trust_dashboard.py
  --fetch` (CI, weekly — see `.github/workflows/trust-dashboard.yml`).
  Do not edit numbers by hand: the render is a pure function of this
  file, the suite fails on page/snapshot/tree drift, and a hand-edited
  count has no source behind it.
- `sources.yaml` — the source pointers (which GitHub repository, which
  arXiv id). The one human input the dashboard accepts; a pointer,
  never a number.

Zeros in the snapshot are real zeros read from a source; unknowns
(currently: citations, because no paper is public yet) are real
unknowns with their reason recorded. Refresh the fetched sections:
`make trust-dashboard FETCH=1`. The freshness gate runs with the suite
(`tests/evidence/test_trust_dashboard.py`).
