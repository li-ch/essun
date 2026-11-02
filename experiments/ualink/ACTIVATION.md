# UALink activation runbook — permission to profile in five working days

This directory is the UALink **activation kit**: everything that could be
built *before* the license question is answered was built; the remaining
work is scoped, command-level, and rehearsed. The license question
(HUM-02, sent to the UALink Consortium; see the outreach draft in the
private workspace) is: may an independent open-source project derive and
publicly distribute a machine-readable UALink profile — and if not, may a
member organization maintain one internally against public tooling?

**What exists today (honest state, 2026-11-02):**

| Piece | State | Where |
|---|---|---|
| License-gate source record (5 verbatim registry rows, gated row visible) | committed | `experiments/ualink/source_record.yaml` |
| Fetch guard (refuses gated rows + uncleared consortium paths before any fetch) | committed, tested | `experiments/ualink/fetch_sources.py` |
| Two member-public excerpts fetched, sha-pinned, extracted | committed | `experiments/ualink/source/` |
| Worked-example anchor registry (30 verified quotes, both excerpts) | committed, tested | `experiments/ualink/anchor_registry.yaml` |
| Activation skeleton profile (zero requirements, 8 anchored free parameters) | committed, tested | `experiments/ualink/semantic_profile.yaml` |
| Conformance gate | 36 tests | `tests/specir/test_ualink_activation_skeleton.py` |

The skeleton is **not a profile**: it interprets nothing, executes nothing,
and every figure the public excerpts state (200 GT/s per lane, 64B/640B
flits, 1024 endpoints, ...) is a graded candidate under an explicit free
parameter (`UAL-F01..F08`), never a value.

## What counts as "permission"

A written answer from the UALink Consortium (or a member organization
acting within its rights) that is recorded before anything is fetched.
The record must capture, verbatim where possible:

1. **who** answered (name, organization, role) and **date**;
2. **which documents** are covered (Common 2.0 Evaluation Copy; the
   DL/PL, Manageability, Chiplet family — enumerate by exact title);
3. **scope of derivation**: excerpt-quoting vs full-text ingestion;
4. **scope of distribution**: may derived semantics be public, or
   member-internal only;
5. **AI-processing scope**: whether feeding the text to automated
   extraction is permitted (the registry row for the evaluation copy
   explicitly flags "internal evaluation, derivative, implementation and
   AI scope" as requiring review — treat silence as *no*).

If the answer is **"not at this time"**: stop. The platform says publicly
that UALink stays out rather than working from unauthorized text; the kit
stays as the standing readiness record. If the answer permits a
**member-internal profile only** (email question 2): activate the same
plan, but the profile artifacts and anchors live in the member's private
fork — the public repository keeps only this kit and the tooling.

## The five days

Every machine step is a command that already exists in this repository.
"N days" means five focused working days for one person who knows this
codebase; the ordering is the dependency order, not a suggestion.

### Day 0 — record the answer (gate: nothing is fetched yet)

- Add the permission record (fields 1-5 above) to the license-gate source
  registry in the private workspace and copy the affected rows verbatim
  into `experiments/ualink/source_record.yaml`, changing the covered rows
  from `APPROVAL_REQUIRED` to an access value that names the grant
  (e.g. `AUTHORIZED_MEMBER_INTERNAL` or `AUTHORIZED_PUBLIC_DERIVATION`) —
  the verbatim-row rule applies: registry first, copy here, never
  paraphrase.
- Update `HUM_STATUS` in `experiments/ualink/build_semantic_profile.py`
  and the skeleton's `provenance.license_status` to cite the grant.
- Decision point (owner): public vs member-internal distribution scope —
  this decides which repository the activated profile lives in.

### Day 1 — gated fetch and extraction

- Extend `SOURCES` in `experiments/ualink/fetch_sources.py` with the
  authorized documents (kind `pdf`), and extend `UALINK_PUBLIC_PATHS` —
  rename it in the same change to make its meaning exact (it becomes the
  *cleared-paths* set: member-public excerpts + authorized documents).
- Run `.venv/bin/python experiments/ualink/fetch_sources.py`; commit the
  extracted pages and manifest (per-page sha256, deterministic).
- Update the guard tests in `tests/specir/test_ualink_activation_skeleton.py`
  **in the same change** (they enumerate the cleared set on purpose —
  widening the guard without widening the tests must stay a hard error).

### Days 2-3 — anchor and interpret

- Curate anchors into `experiments/ualink/build_anchor_registry.py`
  following the worked example: verbatim quotes, <= 30 words / 200 chars,
  auto-located, category from the closed set (extend the set consciously
  if the specification needs categories the excerpts did not).
- Write the requirement modules `src/essun/specir/ualink_*.py` mirroring
  the UEC family (`uec_link_transport.py`, `uec_credits_flow_control.py`,
  ...): one module per spec volume or concern, dispositions from the
  shared six-value vocabulary, keyword/subject/statement paraphrased in
  essun's own words, every normative value carrying its anchor.
- Evidence grade for spec-derived facts: `AUTHORIZED_SPEC`, alongside
  (never replacing) `MEMBER_PUBLIC_EXCERPT` for the public documents.
- Free parameters: promote an excerpt candidate only when an
  authorized-spec anchor fixes its value; everything the specification
  leaves open stays FREE (`UAL-F01..F08` are pre-registered slots; add
  new ones as the spec text demands — a new slot is a minor bump).

### Day 4 — wire the executable surface

- Platform map: which landed knobs UALink facts feed (mirror
  `essun/specir/unifiedbus_platform_map.py`) — mappings, not bindings.
- L0 flavor for the cross-design comparison if and only if anchored
  facts support one (mirror `unifiedbus_l0_flavors.py`); shared free
  parameters (per-lane rate, latency) stay shared with UEC/UnifiedBus —
  no unequal inputs.
- Any backend capability binding is a reviewed act: disposition
  `simulated_behavior` + binding + golden check land together or not at
  all (the loader enforces this mechanically).

### Day 5 — profile v1.0.0, gates, and the public story

- Replace the skeleton builder's empty step with the live requirement
  modules (the UEC/UnifiedBus builder pattern: dispositions READ from the
  live registry, never assigned by the builder). The skeleton artifact is
  superseded by `ualink-<version>-semantic` at **profile_version 1.0.0**
  (major bump: dispositions, bindings, anchor_ids, sources all change).
- Conformance tests mirroring `tests/specir/test_uec_semantic_profile.py`:
  loads, disposition parity, anchor resolution, bindings honesty,
  corruption rejection, byte-identical regeneration. Goldens arrive with
  the first binding.
- Full suite (`python -m pytest`), `make paper-check` vocabulary, README
  component-table row, status docs. Labels: everything ships
  `IMPLEMENTED_UNVERIFIED` at best; the cross-fabric matrix column is a
  separate decision with its own gate (a column needs a profile).
- If distribution is public: the owner flips the release (the repository
  and its CI are the owner's action, not this runbook's).

## Standing rules the runbook cannot waive

- License review precedes ingestion — Day 0 exists so this is never
  retrospective.
- No invented normative values: every gap is an explicit free parameter,
  and an excerpt figure never promotes without a spec anchor.
- Standard targets, implementation profiles, and modeling assumptions
  stay separated; every standard-derived value keeps its source anchor.
- The honesty fences are mechanical (loader + tests), so bending them
  requires changing code a reviewer can see — that is the point.
