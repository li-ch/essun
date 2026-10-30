# G7 leg (b) — the hard credit-and-contention case: exact traces vs the law

Date: 2026-10-30. Status: **PROPOSED**, evidence level **E0** (exact
integer execution of free parameters; nothing measured, nothing
standard-derived except the 256-byte credit unit, UEC11-FC-R05).
Record: `contention_record_v1.json` (built by
`build_contention_record.py`; byte-identical regeneration enforced).
Module: `src/essun/specir/credit_automaton.py` — the G8 credit
obligation automaton plus the G7 **multi-source shared-link contention
extension** (the p8 pre-registered follow-up). Goldens:
`tests/golden/test_credit_automaton_golden.py` (G7-A/G7-B, hand-derived
values), `tests/specir/test_credit_automaton.py` (load semantics,
safety/conservation grids, closed forms vs execution on 100+ grid
points). Assumptions ledger:
`experiments/vertical_slice/assumptions_credit_automaton.yaml`
(including the new A-CA-ARB arbitration entry and A-CA-SHARE).

## The case

Two flows — two independent finite collectives, each with its OWN
credit context (the TFC per-PDC-pair shape: one
`CreditAdmissionAutomaton` per flow, windows W_i, packets s_i, counts
n_i) — serialize on ONE shared link at B = 8 B/ns (u = s/B = 32 ns per
256-B packet), hop latency L = 300 ns, credit return L_cr = 100 ns
(D = L + L_cr = 400 ns). All parameters free; all arithmetic integer.

What the analytical law (paper Eq. 3, the per-flow steady-state cap
`min(B, W/(L+L_cr))`, completion `M/Reff + L`) can say about two flows
on one link: **nothing composed**. It is defined per flow; applied per
flow it ignores the shared link; the only plausible composition — an
aggregate `min(B, sum(W_i)/D)` — is an ad-hoc extension the law does
not provide. The machine executes the case exactly, and the outcome
moves with a freedom (which credit-ready flow gets the freed link)
that neither the law nor the standard pins.

### Case G7-A — the windows never bind (the review's own example)

W_0 = W_1 = 8192 B, s = 256 B, n_0 = n_1 = 32: each window covers its
whole collective (k = 32 = n), so **no credit context ever gates**.
Per-flow Eq. 3 alone-law, both flows: `8192/min(8, 8192/400) + 300` =
`8192/8 + 300` = **1324 ns each** — but the two predictions are
jointly infeasible on one 8 B/ns link (they would need 16 B/ns).

The machine, arbitration = index-priority (flow 0 transmits whenever
ready): flow 0 drains first, starts 0, 32, …, 992 ns, completes
**1324 ns** (its alone time — the law happens to be right for the flow
that wins the link); flow 1 starts at 1024 ns, completes
**(32+32)·32 + 300 = 2348 ns**. Arbitration = round-robin: flow 0
starts 0, 64, …, 1984, completes **2316 ns**; flow 1 completes
**2348 ns**.

**Same parameters in all four cells.** Flow 0's completion observable
moves 1324 → 2316 ns (exactly `(n-1)·u` = 992 ns) with the arbitration
choice alone. The analytical law cannot produce either pair — it has
no arbitration operator — and no per-flow input encodes the choice.
The standard does not pin it (UEC 1.1 prescribes no source order on a
shared egress); it is declared freedom (A-CA-ARB), and here is the
exact trace of what that freedom decides.

### Case G7-B — gated burst interaction (idle gaps, both laws miss)

W_0 = W_1 = 1280 B (k = 5 < n = 8: both contexts gate), same link.
Per-flow alone-law, both flows: `2048/min(8, 1280/400) + 300` = 640 +
300 = **940 ns**. The aggregate candidate: `4096/min(8, 2560/400) +
300` = 640 + 300 = **940 ns** too.

The machine, index-priority: flow 0 bursts 0–128 ns; link free at 160;
flow 1 bursts 160–288; link free at 320 with **both contexts drained
and both flows backlogged — the link idles 320→400 ns** (an exact
80-ns gap the fluid laws cannot even express; steady state has no
gaps). Flow 0's returns unfreeze it at 400/432/464 → completes
**796 ns, EARLIER than its own 940-ns law** (finite-collective effect
+ first-mover burst); flow 1 follows at 560/592/624 → completes
**956 ns, LATER than 940**; a second idle gap 496→560. The machine,
round-robin: bursts interleave, one gap 320→400, completions
**(860, 892) ns** — the aggregate's single number 940 is wrong for
both policies, and the **collective's completion observable itself
moves 956 → 892 ns** (exactly 2u) with the arbitration freedom.

Per-context safety and conservation hold at every event of every run
(theorem clause 1 re-derived per context; grid-tested beyond the
goldens).

## Why this is not "the cap has the expected threshold"

The G8 single-link theorem already quantified where the steady-state
law is exact (`s | W`) and by how much it overestimates finite
collectives (< one credit-loop round trip, closed forms). The
contention case is a different failure class: with TWO flows the law
has **no statement at all** — no composition operator, no arbitration,
no idle gaps — so there is no threshold to check. The machine's exact
traces are the only executable answer, and they show the observable
decided by declared freedom, not by any law term. That is the leg-(b)
deliverable: a case the automaton resolves and the analytical law
alone cannot even pose.

## Honest limits

- E0 only; every parameter free; nothing calibrated, nothing measured.
- The contention machine is ONE shared link (multi-link topologies and
  multi-hop paths stay explicitly unsupported in CAPABILITIES); the
  receiver's grant-arbitration algorithm (RCCC, UEC §3.6.14) is NOT
  executed — this extension arbitrates among independently granted
  windows, which is why the RCCC grant-scheduling entry stays in the
  unsupported list (renamed from the G8 umbrella entry).
- Two deterministic arbitration policies are declared and tested; the
  freedom is larger (any deterministic order, priorities, weights) —
  the two suffice to pin the observable's movement exactly.
