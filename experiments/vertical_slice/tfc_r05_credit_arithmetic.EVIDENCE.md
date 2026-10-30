# Credit-family S4 evidence record — UEC11-FC-R05 as conformance_test

G2 credit-window family ladder (milestone v0.2.0 criterion 2) stage S4,
per the S1 plan in `experiments/uec/credit_family_inventory.md`. Date:
2026-10-30. Owner review: pending (the platform-side facts below are what
the owner reviews).

## Labels (read first)

- Platform status: **IMPLEMENTED_UNVERIFIED** (the check executes and its
  golden tests pass; no external review yet).
- Evidence level: **E0** — identity and determinism only. No empirical
  claim is made.
- **`conformance_test` is a claim about the CHECK** (the requirement's
  own arrival arithmetic executes exactly — `credit += (Credit −
  cumulative_credit) >> 8` on increase, `cumulative_credit = Credit`
  then, nothing on a no-op; one unit = 256 B), **not a claim of physical
  validity and not a simulated-behavior claim**: no backend executes
  this law and none was extended — the law demands none. Per the D2
  profile rule a binding may reference only a `simulated_behavior`
  requirement, which is why the carrier is a check
  (`UEC11-CHK-12/13/14`), never a binding.
- Spec-derived values in the chain: the 256-byte credit unit
  (UEC11-FC-R05, `>> 8` — the same constant
  `analytical_l0_tfc.TFC_CREDIT_UNIT_BYTES` and
  `credit_automaton.TFC_CREDIT_UNIT_BYTES` carry, cross-verified live by
  the check) and the 24-bit `pds.credit` field width (UEC11-FC-R01).
  The one modeling choice — reading the `Credit > cumulative_credit`
  guard in the wrapping counter's order (open half range), the ordering
  law the same specification states for CBFC cyclic counters
  (UEC11-FC-R28) — is registered as `A-TFCA-ORDER`
  (`experiments/vertical_slice/assumptions_tfc_credit_arithmetic.yaml`;
  with it `A-TFCA-INIT` initial-state and `A-TFCA-SCOPE`
  source-side-only).

## The chain

| Link | Artifact |
| --- | --- |
| Anchored requirement | **UEC11-FC-R05** (UEC 1.1 §3.6.15, TFC, DEFINITIONAL) — the monotonically increasing wrapping `pds.credit` counter, one bit = 256 bytes, and the on-arrival update law; anchor `UEC11-S3.6.15-TFC` (verified by the anchor registry's re-hash on every registry test) |
| Executed conformance check | `tests/golden/test_credit_arrival_golden.py` — the arrival law executed exactly, 13 tests, every expected value derived in-test by exact integer arithmetic (hand-derived literals in comments, independent expressions in the asserts; no floats, no `random` — the property streams are fixed-constant LCGs) |
| Profile CHECKS entries | `UEC11-CHK-12` (golden), `UEC11-CHK-13` (negative), `UEC11-CHK-14` (invariant) — curated in `experiments/uec/build_semantic_profile.py`, carried by the regenerated `experiments/uec/semantic_profile.yaml` at artifact version **0.5.0** (dispositions = the bump rules' MAJOR class; on the 0.x line that bumps the MINOR); the format itself enforces conformance_test ↔ checks (`essun.specir.profile_format._cross_reference_problems`) |
| Disposition flip (atomic) | `src/essun/specir/uec_credits_flow_control.py` — UEC11-FC-R05 `informational → conformance_test`, with `PROMOTED` + `EXPECTED_COUNTS` in `tests/specir/test_dispositions.py` in the same commit; the binding-coverage property's conformance leg and the promotion-table parity's conformance leg (`tests/specir/test_binding_coverage.py`, `tests/specir/test_bindings.py`) verify the carrier both live and through the built artifact |
| Observable change | **none** — no backend, manifest, topology, or run output changes; earlier run identities reproduce unchanged (no manifest input touched; the assumptions file is NEW, so no hashed input shifted) |
| Modeling choices (registered) | `experiments/vertical_slice/assumptions_tfc_credit_arithmetic.yaml` — A-TFCA-ORDER (wrapping-order comparison, law cited to UEC11-FC-R28), A-TFCA-INIT (zero initial state; R14 bring-up not executed), A-TFCA-SCOPE (source-side credit accumulation only) |
| Evidence run | **none exists — stated exactly:** a conformance check has NO run-record path on this platform. `essun.orchestrator.runs` executes experiment manifests through backend dispatch and stamps content-addressed `evidence_schema_version: 2` run records; a pytest golden is not a manifest execution, so no run id can honestly exist for it (and a claims-index link requires a run id — none is fabricated). The check's execution evidence is its committed golden test at this stage commit: `.venv/bin/python -m pytest -q tests/golden/test_credit_arrival_golden.py` → **13 passed** (recorded 2026-10-30 at this commit; deterministic — fixed LCG constants, no random, no time), with the byte-identical regeneration gate pinning the artifact that carries the check entries |

Re-verify in one line each:

```bash
.venv/bin/python -m pytest -q tests/golden/test_credit_arrival_golden.py
.venv/bin/python -m pytest -q tests/specir/test_dispositions.py tests/specir/test_bindings.py tests/specir/test_binding_coverage.py
.venv/bin/python experiments/uec/build_semantic_profile.py
# -> 187 informational / 254 unsupported / 3 simulated_behavior /
#    conformance_test 1; 4 executed; 14 checks (byte-identical)
```

## What the check pins (the executed law and its boundaries)

- **Whole-unit golden trace**: arrivals 256/768/1024/4096 grant
  1/2/1/12 units (16 total) — derived independently as the floored
  cumulative byte count; per-arrival floors telescope on whole-unit
  streams.
- **Boundary — equal arrival**: a no-op: no grant, cumulative unchanged.
- **Boundary — stale/duplicate/reordered arrivals**: ignored by the
  monotone guard; state untouched; a later genuine increase lands whole.
- **Boundary — sub-unit increase**: grants zero (the `>> 8` floor) while
  `cumulative_credit` DOES advance; and the floors do NOT telescope for
  sub-unit streams (0→199→399→599 grants 0 units vs 2 direct) — the
  algorithm as written, pinned, not repaired; the whole-unit allocation
  discipline of UEC11-FC-R07 (values cited, obligation unexecuted) is
  the regime real grants live in.
- **Boundary — the counter wrap**: an increase spanning the 24-bit wrap
  (cumulative 2²⁴−512, arrival 255) grants its 2 units under the
  wrapping order — a plain-integer comparison would grant 0; difference
  of exactly half the range is NOT an increase (UEC11-FC-R28's law).
- **Loss/reorder tolerance executed**: on whole-unit streams every
  permutation of {256, 768, 1536} and the loss-shortened path grant the
  same 6 units — the "tolerance to credit packet loss" sentence as
  arithmetic.
- **Negative teeth**: each named misreading (plain-integer comparison;
  grant-without-guard; cumulative-updates-on-no-op; `>>7`/`>>9` unit
  misread) is executed for contrast and MUST differ from the pinned
  spec values; out-of-field arrivals are rejected citing UEC11-FC-R01.
- **Invariants over fixed LCG streams** (2000 + 500 arrivals): accepted
  arrivals advance the counter within the open half range and grant
  exactly their floored units; ignored arrivals change nothing; the
  counter stays in field; granted units never exceed the floored total
  advance, with equality at every step on whole-unit streams; the live
  R05 object still carries the law and the 256-B unit equals both landed
  executors' constant.

## Honest limits of this slice (what it does NOT show)

- The check executes the ARRIVAL arithmetic only — the source-side
  credit bookkeeping. It is not a simulation of credit flow: no timing,
  no link, no queueing, no admission coupling (that is R02's executed
  automaton and the analytical family's territory).
- Bring-up (UEC11-FC-R14), the credit request/grant machinery (R15),
  the retransmission exemption (R06), shared-CCC pooling (R16), and the
  credit timer (R19) remain unexecuted (declared exclusions); the CBFC
  counter laws (R28/R34/R39/R43/R45/R46) stay CAPABLE-NOT-PLANNED per
  the S1 inventory.
- The wrapping-order reading of the guard is a REGISTERED modeling
  choice (A-TFCA-ORDER), law-cited to UEC11-FC-R28 — the spec's TFC
  text does not spell out the wrap comparison itself; the check makes
  the choice visible and attackable rather than implicit.
- UEC11-FC-R07's and UEC11-FC-R10's dispositions stay `unsupported`
  (their VALUES are cited as the whole-unit discipline and domain
  bounds; the support obligations are not executed by a check).
- Numbers above are exact-integer arithmetic of the law, not
  measurements of anything.
