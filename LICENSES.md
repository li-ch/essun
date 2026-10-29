# Licenses

Two grants cover this repository's own content; third-party material and
extracted standard text keep their own terms and are carved out below. This
file is the map; the MIT full text lives in [LICENSE](LICENSE).

| Content | License |
|---|---|
| Code (perimeter in §1) | MIT — [LICENSE](LICENSE) |
| Documentation, figures, and the site (§2) | CC-BY-4.0 |

## 1. Code — MIT

Copyright (c) 2026 Li Chen. Licensed under the MIT License; full text in
[LICENSE](LICENSE). The MIT perimeter is this repository's own content that
is not listed in §2 and not carved out in §3 or §4: `src/`, `tests/`,
`tools/`, `schemas/` and `examples/`, `experiments/` (manifests, workloads,
topologies, sweep grids, and the registry build scripts — machine-consumed
inputs; the §4 carve-out still applies to extracted text and quotes),
`backends/docker/`, `Makefile`, `.github/`, `pyproject.toml`.

## 2. Documentation, figures, and the site — CC-BY-4.0

Copyright (c) 2026 Li Chen. Licensed under the Creative Commons Attribution
4.0 International License (CC-BY-4.0). To view a copy of the license, visit
<https://creativecommons.org/licenses/by/4.0/legalcode>. Suggested
attribution: "essun project, Li Chen", linked to this repository.

Applies to: `docs/` (ADRs, atlas, calibration notes, usage and wayfinding
pages), the root-level prose files (`README.md`, `CHANGELOG.md`,
`CONTRIBUTING.md`, `LICENSES.md`), `paper/figures/`
(rendered figures and their provenance README), and `site/` (page,
stylesheet, and assets).

## 3. Third-party code — keeps its own license

- `backends/pins/` records the pinned upstream simulators with their license
  texts: ASTRA-sim (MIT), csg-htsim (BSD-2-Clause), uet-htsim (BSD-2-Clause,
  Ultra Ethernet Transport-WG notice). Those projects' code and license
  texts remain under their own licenses; nothing here relicenses them.
- The checked-out upstream trees (`backends/astra-sim/`, `backends/uet-htsim/`)
  are local, git-ignored build trees (pinned by commit hash, see
  `backends/pins/`), not distributed content of this repository.

## 4. Standard and paper text — never relicensed here

The extracted page text under `experiments/uec/source/` and
`experiments/unifiedbus/source/`, and the verbatim quotes inside the anchor
registries (`experiments/*/anchor_registry.yaml`), come from externally
copyrighted sources (the Ultra Ethernet Specification 1.1 and public
UnifiedBus material) used under the recorded PUBLIC_READ citation terms
(`experiments/*/source_record.yaml`; every quote carries a source anchor).
That text remains the property of its respective copyright holders; no
grant on this page applies to it. The source PDFs themselves never enter
git.

## 5. Manuscript drafts — not covered by either grant

`paper/sections/`, `paper/notes/`, and `the site white-paper asset (site/assets/)` are unpublished
manuscript drafts. Neither grant above covers them; the author reserves all
rights, and a license will be recorded when and where the paper is
published.

## 6. Historical content

Earlier revisions of this repository (as retrievable from git history)
carry the grant of their category: prose, figures, and documentation
CC-BY-4.0; code MIT.
