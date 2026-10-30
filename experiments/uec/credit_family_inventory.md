# Credit / flow-control family inventory and ladder plan (S1)

Stage S1 of the credit-window family ladder (milestone v0.2.0 criterion 2:
grow the flagship from one executed UEC requirement to the TFC/credit
family). Date: 2026-10-30. Record class: `no-label` — this is an inventory
and plan; nothing in it executes a requirement and no disposition changes
with it.

Scope: every requirement object of
`src/essun/specir/uec_credits_flow_control.py` — UEC 1.1 §3.6.15 Transport
Flow Control (TFC), the §3.6.14 RCCC pull-credit residue, and §5.2
link-layer Credit-Based Flow Control (CBFC) — **66 requirements** across
six subjects (TFC 19, PULL_CREDIT 3, CBFC 27, CBFC_MSG 5, CBFC_INIT 9,
CBFC_LLR 3) plus **12 free parameters**, over six anchors
(`UEC11-S3.6.14-RCCC`, `UEC11-S3.6.15-TFC`, `UEC11-S5.2-CBFC`,
`UEC11-S5.2.4-CBFC-OVERVIEW`, `UEC11-S5.2.5-CBFC-OPERATION`,
`UEC11-S5.2.10-CBFC-COMPLIANCE`).

## Current state (computed live, not copied)

Source of truth: the stage module and the D1 gates. Re-derive with:

```bash
.venv/bin/python tools/disposition_coverage.py
```

| disposition | count |
| --- | --- |
| informational | 33 |
| unsupported | 32 |
| simulated_behavior | 1 (`UEC11-FC-R02`, binding `BIND-UEC11-FC-R02-L0TFC`) |
| constraint / conformance_test / not_applicable | 0 |
| **total** | **66** |

Frozen in `tests/specir/test_dispositions.py` (`EXPECTED_COUNTS`,
`PROMOTED`); profile-wide the UEC profile stands at 1 executed / 445.
The single executed requirement is the flagship slice
(`experiments/vertical_slice/tfc_r02_flagship.EVIDENCE.md`).

## Executability method (what "honest" means here)

A requirement is **executable** only if a current backend can carry its
semantics causally — `simulated_behavior` needs a binding whose declared
parameter changes outputs through an exact law; `conformance_test` needs
the requirement's own algorithm/checkable rule executable as a golden or
negative check. Following the flagship choice record
(`src/essun/specir/bindings.py`), candidates are ranked by decision
relevance, not convenience, and the `analytical_l0_tfc` fidelity
exclusions (`CAPABILITIES["explicitly_unsupported"]`) are hard walls:
congestion and queue-occupancy dynamics, multi-flow credit scheduling,
packet-header semantics, protocol state machines and timers, bring-up
transients, and the whole CBFC hop-level family are out of reach of the
analytical family today. `unsupported` and `informational` are honest,
visible answers; nothing below upgrades silently — every planned
promotion names its stage, its carrier, and the gates it must pass in the
same commit.

## Inventory — every requirement, disposition, verdict

Verdict codes: **EXECUTED** (live binding today) · **PLANNED-S2/S3/S4**
(staged promotion, one requirement per stage, carrier named in the plan
below) · **CAPABLE-NOT-PLANNED** (the requirement's own arithmetic or
bit-layout law could run as an exact conformance check without physical
claims, but it is link-layer bookkeeping with thin decision relevance for
a fabric architect — recorded so the capability is not lost, not staged)
· **STAYS** (not honestly executable on any current backend; the missing
fidelity is named).

### TFC, §3.6.15 (R01–R19, anchor UEC11-S3.6.15-TFC)

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R01 | DEFINITIONAL | informational | STAYS — definitional overview; no law to execute |
| UEC11-FC-R02 | MUST NOT | simulated_behavior | EXECUTED — admission law; `BIND-UEC11-FC-R02-L0TFC` on `analytical_l0_tfc` |
| UEC11-FC-R03 | MUST | unsupported | STAYS — packet-granular admission decision + destination MTU acceptance; under the steady-window abstraction the acceptance half would be tautological (coverage inflation). Honest future executor: a discrete credit automaton |
| UEC11-FC-R04 | MUST | unsupported | STAYS — PDS header-field law (`pds.ooo_count` = 0xFFFF); no backend carries packet headers |
| UEC11-FC-R05 | DEFINITIONAL | informational | **PLANNED-S4** → `conformance_test`: the credit arithmetic is exact and self-contained (256 B per credit unit; monotone wrapping cumulative counter; `credit += (Credit − cumulative_credit) >> 8` on increase) |
| UEC11-FC-R06 | DEFINITIONAL | informational | STAYS — retransmission credit exemption needs retransmission dynamics (`tfc_retransmission_credit_exempt` explicitly unsupported) |
| UEC11-FC-R07 | MUST | unsupported | STAYS — implementation-support obligation ("cell sizes 256–9216 B in 256-B multiples must be supported"); no backend executes vendor support. NOTE: S2's `tfc_dest_cell_size` adopts its range as a validated modeling domain, assumption-cited — the same pattern as R05's constant inside the R02 binding. A future `constraint` promotion additionally needs the admissible-config enforcement path D1 names (orchestrator compile step), which does not exist yet |
| UEC11-FC-R08 | DEFINITIONAL | informational | **PLANNED-S2** → `simulated_behavior`: `credit_used = ROUNDUP(tfc_pkt_size ÷ cell) × cell` is an exact steady-state law with a causal rate effect (see plan) |
| UEC11-FC-R09 | MUST | unsupported | **PLANNED-S3** → `simulated_behavior`: the per-packet overhead constant `tfc_pkt_overhead` (default 256 B, spec-derived) enters credit consumption causally |
| UEC11-FC-R10 | SHOULD | unsupported | STAYS — configurability recommendation about implementations; S3's parameter realizes 0–256 B configurability as a modeling choice, not as execution of the SHOULD |
| UEC11-FC-R11 | MUST | unsupported | STAYS — receiver buffering property; tautological under the window abstraction |
| UEC11-FC-R12 | MAY | unsupported | STAYS — per-direction cell/overhead asymmetry of a bidirectional PDC pair; the model carries one data direction per neighbor pair |
| UEC11-FC-R13 | MUST | unsupported | STAYS — configure-before-data on an active PDC; PDC lifecycle state machine |
| UEC11-FC-R14 | MUST | unsupported | STAYS — initial-credit bring-up (`ccc.credit ≥ tfc_pkt_overhead`); startup transients are a declared exclusion. Future executor: the discrete automaton |
| UEC11-FC-R15 | DEFINITIONAL | informational | STAYS — credit request/grant machinery (`credit_request_grant_dynamics` explicitly unsupported; the steady granted window W is the modeled abstraction) |
| UEC11-FC-R16 | MUST | unsupported | STAYS — shared-CCC pooling across PDCs (`shared_ccc_credit_pooling` explicitly unsupported; needs multi-flow) |
| UEC11-FC-R17 | DEFINITIONAL | informational | STAYS — CCC shutdown semantics; lifecycle |
| UEC11-FC-R18 | MUST NOT | unsupported | STAYS — close-state-machine reuse race; discrete-event protocol |
| UEC11-FC-R19 | DEFINITIONAL | informational | STAYS — credit timer for lost credit requests needs event dynamics (S4 executes the arrival arithmetic's loss tolerance, not the timer) |

### PULL_CREDIT residue, §3.6.14 (R20–R22, anchor UEC11-S3.6.14-RCCC)

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R20 | SHOULD | unsupported | STAYS — shared pull-credit pool over requests and large responses; multi-flow contention, the flagship rejection class |
| UEC11-FC-R21 | DEFINITIONAL | informational | STAYS — forward/reverse CCC allocation lookup |
| UEC11-FC-R22 | DEFINITIONAL | informational | STAYS — the credit>0 send gate is a discrete admission decision (the one-packet-offset footnote); S2/S3 execute the consumption side of credit, not the gate decision |

### CBFC mechanism and operation, §5.2/5.2.4/5.2.5 (R23–R44)

The flagship choice record already rejected this family for
`simulated_behavior`: hop-level backpressure changes outputs only through
queue-occupancy dynamics propagating across hops, a fidelity the
analytical family explicitly excludes.

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R23 | DEFINITIONAL | informational | STAYS — definition/rationale |
| UEC11-FC-R24 | MUST NOT | unsupported | STAYS — PAUSE/CBFC/PFC link-feature exclusion; no link-configuration backend |
| UEC11-FC-R25 | DEFINITIONAL | informational | STAYS — rationale comparison vs PFC |
| UEC11-FC-R26 | DEFINITIONAL | informational | STAYS — feature list |
| UEC11-FC-R27 | DEFINITIONAL | informational | STAYS — scheduler/credit-return overview loop; queue-occupancy semantics |
| UEC11-FC-R28 | DEFINITIONAL | informational | CAPABLE-NOT-PLANNED — cyclic-counter ordering law (reliable order iff difference < half the range) is exact arithmetic with a crisp boundary |
| UEC11-FC-R29 | DEFINITIONAL | informational | STAYS — CC/CF counter mechanism; output effects need message dynamics |
| UEC11-FC-R30 | DEFINITIONAL | informational | STAYS — link-layer scope |
| UEC11-FC-R31 | DEFINITIONAL | informational | STAYS — Table 5-14 parameter set; no CBFC model exists to carry it |
| UEC11-FC-R32 | MUST NOT | unsupported | STAYS — credit-limit method exclusivity; config rule for a model that does not exist |
| UEC11-FC-R33 | MUST | unsupported | STAYS — packet-header-to-VC mapping; header classification |
| UEC11-FC-R34 | DEFINITIONAL | informational | CAPABLE-NOT-PLANNED — counter widths/state definitions (20-bit CC, 15-bit CF) are width-boundary arithmetic |
| UEC11-FC-R35 | SHALL | unsupported | STAYS — implementation-support obligation |
| UEC11-FC-R36 | DEFINITIONAL | informational | STAYS — counter sizing rationale (the flagship's rejected representative) |
| UEC11-FC-R37 | DEFINITIONAL | informational | STAYS — message-type description |
| UEC11-FC-R38 | MUST | unsupported | STAYS — credit admission `S_VC_CU + pktCredits ≤ S_VC_CL` needs hop-level queue dynamics for output effects; the predicate itself is exact arithmetic and capable of a conformance check in principle, but that execution belongs to a discrete link-credit track, not this ladder |
| UEC11-FC-R39 | DEFINITIONAL | informational | CAPABLE-NOT-PLANNED — counter update laws on send/CF_Update are exact arithmetic |
| UEC11-FC-R40 | MUST | unsupported | STAYS — CC_Update periodicity; timer-driven generation |
| UEC11-FC-R41 | MUST | unsupported | STAYS — receiver-side counters incl. cut-through; receiver pipeline |
| UEC11-FC-R42 | MUST | unsupported | STAYS — CF_Update trigger timers (CF_min/CF_max) |
| UEC11-FC-R43 | DEFINITIONAL | informational | CAPABLE-NOT-PLANNED — CC_Update reception law (LostCredits reclaim + error windows) is exact arithmetic |
| UEC11-FC-R44 | DEFINITIONAL | informational | STAYS — informative non-ideal-credit strategy guidance |

### CBFC message formats, §5.2.6/5.2.7/5.2.11 (R45–R49)

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R45 | DEFINITIONAL | informational | CAPABLE-NOT-PLANNED — 8-byte CF_Update CtlOS bit layout is exactly encodable |
| UEC11-FC-R46 | DEFINITIONAL | informational | CAPABLE-NOT-PLANNED — 64-byte CC_Update MAC-control frame layout is exactly encodable |
| UEC11-FC-R47 | SHALL | unsupported | STAYS — zero S_VC_CC for unused VCs; message-construction rule needing CC_Update generation |
| UEC11-FC-R48 | MUST | unsupported | STAYS — MAC interface rules (CtlOS preemption, MA_DATA ordering) |
| UEC11-FC-R49 | MUST | unsupported | STAYS — CtlOS insertion alignment and ≥400 B spacing; MAC/PCS |

### CBFC initialization, §5.2.8 (R50–R58)

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R50 | DEFINITIONAL | informational | STAYS — network-level config consistency |
| UEC11-FC-R51 | DEFINITIONAL | informational | STAYS — receiver-determined values and conservative inequalities; configuration doctrine for a nonexistent model |
| UEC11-FC-R52 | DEFINITIONAL | informational | STAYS — LLDP TLV init process |
| UEC11-FC-R53 | MUST NOT | unsupported | STAYS — VC usage during init; protocol behavior |
| UEC11-FC-R54 | DEFINITIONAL | informational | STAYS — TLV field inventory |
| UEC11-FC-R55 | SHALL NOT | unsupported | STAYS — RTS/RTR handshake gate; state machine |
| UEC11-FC-R56 | DEFINITIONAL | informational | STAYS — handshake sequence (the wait-condition arithmetic is embedded in protocol dynamics) |
| UEC11-FC-R57 | DEFINITIONAL | informational | STAYS — add-VC constraints |
| UEC11-FC-R58 | DEFINITIONAL | informational | STAYS — VC removal process |

### CBFC × LLR/PFC, §5.2.9 (R59–R61)

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R59 | DEFINITIONAL | informational | STAYS — LLR discard/replay hazards for counters |
| UEC11-FC-R60 | MUST | unsupported | STAYS — LLR windows × credit counters |
| UEC11-FC-R61 | SHALL | unsupported | STAYS — PFC coexistence + LLR windows |

### CBFC compliance, §5.2.10 (R62–R66)

| id | keyword | disposition | verdict |
| --- | --- | --- | --- |
| UEC11-FC-R62 | MUST | unsupported | STAYS — CreditSize support-set obligation (implementation support) |
| UEC11-FC-R63 | SHALL | unsupported | STAYS — PktOvhd range obligation |
| UEC11-FC-R64 | MUST | unsupported | STAYS — VC count support obligation |
| UEC11-FC-R65 | MUST | unsupported | STAYS — parameter/mapping conformance; mapping half needs header classification |
| UEC11-FC-R66 | MUST | unsupported | STAYS — message/timer conformance obligations |

Verdict tally: 1 EXECUTED, 3 PLANNED (R08, R09, R05), 6
CAPABLE-NOT-PLANNED (R28, R34, R39, R43, R45, R46), 56 STAYS.

## The ladder plan — S2, S3, S4 (one requirement per stage)

Common obligations per stage (the no-silent-promotion gate, all in the
same commit): flip the disposition in `uec_credits_flow_control.py`;
update `PROMOTED` and `EXPECTED_COUNTS` in
`tests/specir/test_dispositions.py`; land the carrier (binding and/or
check) with golden tests whose expected values are derived in-test by
exact `Fraction` arithmetic; regenerate
`experiments/uec/semantic_profile.yaml` via
`experiments/uec/build_semantic_profile.py` (bindings list, `CHECKS`
curation, disposition counts); extend
`experiments/vertical_slice/assumptions_tfc.yaml` with one entry per
modeling choice; run the evidence manifest through
`essun.orchestrator.runs` for a content-addressed,
`evidence_schema_version: 2` record (`calibration_target: []`,
`held_out: false` — E0 identity/determinism only) and write the
`*.EVIDENCE.md` record. Suite green throughout.

### S2 — UEC11-FC-R08 → simulated_behavior (cell-quantized credit consumption)

The ROUNDUP law executed as a steady-state rate identity on
`analytical_l0_tfc` (extend only where the law demands):

- new parameter `tfc_dest_cell_size`, validated at load to an integral
  256-B multiple in 256..9216 B (range adopted from R07's stated values,
  cited; R07 itself stays unsupported);
- per-packet consumed credit `cq = ROUNDUP(c / cell) × cell` with the
  ring chunk `c = M/r` as `tfc_pkt_size` (assumption entry for the
  chunk→packet mapping; overhead enters at S3);
- causal law: data rate `= min(B, (c / cq) · W / (L + L_cr))` —
  quantization waste spends credit without moving bytes;
- binding `BIND-UEC11-FC-R08-L0TFC`; observables O-CCT (moves), O-CONSERVATION
  (unchanged: a cell gates rate, never byte count);
- goldens: exact values in the waste regime; **boundary/convergence**:
  `c ≡ 0 (mod cell)` ⇒ `cq = c` ⇒ the identity equals the landed R02
  identity exactly; negative: out-of-domain cell rejected citing the
  R07-anchored range.

### S3 — UEC11-FC-R09 → simulated_behavior (per-packet overhead constant)

- new parameter `tfc_pkt_overhead`, domain 0..256 B, default 256 B
  (spec-derived via R09; the 0..256 configurability bounds are R10's
  stated values, cited; R10 itself stays unsupported);
- `tfc_pkt_size = c + tfc_pkt_overhead` inside S2's ROUNDUP; the
  same-constant-at-both-ends property is structural in one model (stated
  as structure, not claimed as executed);
- binding `BIND-UEC11-FC-R09-L0TFC`; same observable discipline;
- goldens: default-256 case vs the S2 (overhead-less) case;
  **boundary/convergence**: `tfc_pkt_overhead = 0` ∧ `c ≡ 0 (mod cell)`
  ⇒ exact convergence to the landed R02 identity;
- assumption entry for the overhead (covers encapsulation/metadata
  growth as a steady-state constant).

### S4 — UEC11-FC-R05 → conformance_test (credit arithmetic, executed as a check)

Per the D2 profile rule, a profile binding may reference only a
`simulated_behavior` requirement; `conformance_test` is exercised by an
executable checks entry — the check is this stage's carrier (no backend
extension: the law demands none).

- harness executing R05's algorithm exactly: one credit unit = 256 B;
  on credit arrival, `credit += (Credit − cumulative_credit) >> 8` iff
  `Credit > cumulative_credit`, then `cumulative_credit = Credit`
  (monotone wrapping counter, loss-tolerant by construction);
- golden traces with derived exact values; **boundary cases**: arrival
  equal to cumulative (no-op), stale/duplicate arrival (ignored by the
  monotone guard), an increase spanning the counter wrap;
- profile `CHECKS` entry (kind golden + negative) referencing
  UEC11-FC-R05; `PROMOTED`/`EXPECTED_COUNTS` updated; evidence record
  v2. Optional hardening (stage or soak): extend the binding-coverage
  property's legs to `conformance_test` ↔ checks, mirroring the
  simulated_behavior legs.

### Not in this ladder (explicitly)

R07 and R10 as promotions (no admissible-config enforcement path /
implementation-support semantics — their VALUES enter as cited
constants/domains); the CBFC family (flagship rejection stands; the six
capable arithmetic laws are recorded above for a future link-credit
track); everything marked STAYS above. Target counts after S2–S4, if and
only if each stage lands: informational 31, unsupported 31,
simulated_behavior 3, conformance_test 1 — 4 executed in-family,
4/445 profile-wide. S5 extends `docs/reproduce-flagship.md` into the
family reproduction card; S6 regenerates the coverage report with
before/after counts.
