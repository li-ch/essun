# Flagship slice evidence record — UEC11-FC-R02 as simulated_behavior

Design doc (2026-10-29) build order item 2: ONE externally relevant UEC
semantic requirement executed end-to-end. Date: 2026-10-29. Owner review:
pending (the platform-side facts below are what the owner reviews).

## Labels (read first)

- Platform status: **IMPLEMENTED_UNVERIFIED** (the chain executes and its
  golden tests pass; no external review yet).
- Evidence level: **E0** — identity and determinism only. No empirical
  claim is made.
- **`simulated_behavior` is a claim about the BINDING** (the requirement's
  admission law causally affects backend outputs through a declared,
  load-checked parameter), **not a claim of physical validity**: nothing
  here is calibrated against UEC hardware, and B, L, W, L_cr are FREE
  parameters (not standard-derived, not measured). The single
  standard-derived constant is the 256-byte credit unit (UEC11-FC-R05).

## The chain

| Link | Artifact |
| --- | --- |
| Anchored requirement | **UEC11-FC-R02** (UEC 1.1 §3.6.15, TFC, MUST NOT) — "A source MUST NOT transmit a packet if it does not have credit"; anchor `UEC11-S3.6.15-TFC` (page 505, page sha256 `288f1855…`, quote verified by the anchor registry's re-hash on every registry test) |
| Machine-readable binding | `BIND-UEC11-FC-R02-L0TFC` — `src/essun/specir/bindings.py` (registry-gated: requirement, anchors, backend capability/parameters, observables, spec constants re-verified live; gate test `tests/specir/test_bindings.py`) |
| Backend capability / parameter effect | `analytical_l0_tfc` — `src/essun/backends/analytical/l0_tfc.py`, capability `tfc_credit_windowed_ring`; parameters `tfc.window_bytes` (W) and `tfc.credit_return_latency_ns` (L_cr) execute the admission law as the rate identity `R_eff = min(B, W/(L+L_cr))`, so `t = 2*(r-1)/r * M / R_eff + 2*(r-1)*L` |
| Executed golden test | `tests/golden/test_l0_tfc_golden.py` — every expected value derived IN the test by exact `Fraction` arithmetic from the identity (3696 ns window-limited; +448 ns vs L0 = `T*(1/R_eff − 1/B)`; convergence to the landed L0 identity exactly at `W ≥ B*(L+L_cr)` = 25600 B = 100 credit units; window not in 256-byte units rejected at load citing UEC11-FC-R05) |
| Observable change | **O-CCT**: 3696 ns mean (window-limited, 50 credit units) vs 3248 ns for the identical workload on the unbound L0 ring — a +448 ns exact delta with **O-CONSERVATION unchanged** (1376256 bytes = 6 ops × 2·7·16384: a window gates rate, never byte count) |
| Evidence run | run_id `dc7d83b6afa23ef33fd87512eb637bd737ab8ad905a6802bc6d0965be1da21d9` (content-addressed; manifest `experiments/vertical_slice/w1_decode_tfc.yaml`; observations carry the binding provenance block naming UEC11-FC-R02); claim link `C-UEC-TFC-R02` in `results/claims_index.jsonl` |

Re-verify in one line each:

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_golden.py tests/specir/test_bindings.py
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_tfc.yaml
# -> run_id dc7d83b6afa23ef33fd87512eb637bd737ab8ad905a6802bc6d0965be1da21d9 (byte-identical)
```

The full ≤10-minute reproduction-and-challenge path for an external
engineer (clean clone, no Docker) is `docs/reproduce-flagship.md`.

## Why this requirement (choice record)

TFC is UEC's end-to-end flow control, and its admission law is the
mechanism that turns destination buffering into throughput: granted
credit versus the bandwidth-delay product decides whether large
transfers run at line rate. That is a real deployment decision (how many
256-byte credit units to grant per flow), it is executable TODAY as an
exact closed-form identity on the existing ring construction, and its
counterfactual is sharp — the same run with `W ≥ BDP` reproduces the
unbound L0 identity exactly.

Rejected candidates (recorded in full in `src/essun/specir/bindings.py`):

1. **UEC11-CM-R66** (§3.6.14 RCCC pull-credit admission, "a source cannot
   send with credit at or below zero") — equally decision-relevant
   (incast), but RCCC credit is scheduled by the destination across
   multiple concurrent sources from advertised backlog (UEC11-CM-R67);
   executing that honestly needs multi-flow contention, which no backend
   models. Disposition stays `informational`.
2. **CBFC link-credit family** (§5.2; representative UEC11-FC-R36, credit
   counters sized by link RTT and receiver buffer) — hop-level
   backpressure changes outputs only through queue-occupancy dynamics
   across hops, a queueing fidelity the analytical family explicitly
   excludes. An honest binding needs that fidelity first. Disposition
   stays `informational`.

## Honest limits of this slice (what it does NOT show)

- No credit-request/grant protocol dynamics (a steady granted window is
  the modeled abstraction); no TFC retransmission exemption (FC-R06), no
  shared-CCC pooling (FC-R16), no cell-size/overhead accounting
  (FC-R07..R10), no CBFC hop credits, no RCCC multi-source scheduling —
  all declared unsupported in the backend's CAPABILITIES.
- Start-up/fill/drain transients are excluded (same exclusion class as
  the L0 family); the rate law is the steady-state reading of the
  admission law.
- The credit-return latency L_cr is a FREE parameter: UEC does not fix
  credit-return timing, and the slice's numbers move with it (that is a
  feature to attack, not a hidden constant — see the reproduction card).

## Addendum 2026-10-30 — G8: the binding re-pointed at the credit automaton

The chain table above is the 2026-10-29 record of the ORIGINAL landing
and stands unchanged as history. Since G8 (2026-10-30) the executed
semantics live one level down:

| Link | Artifact (post-G8) |
| --- | --- |
| Anchored requirement | **UEC11-FC-R02** — unchanged (anchor `UEC11-S3.6.15-TFC`, MUST NOT) |
| Machine-readable binding | `BIND-UEC11-FC-R02-AUTOMATON` — `src/essun/specir/bindings.py`; backend `credit_admission_automaton` (`src/essun/specir/credit_automaton.py`): exact discrete credit admission/return state machine, integer arithmetic, transmit-without-credit = rejected trace |
| Declared steady-state abstraction | `analytical_l0_tfc` — the Eq. 3 identity of the table above, now the automaton's DECLARED abstraction (`steady_state_abstraction` field, two-sided with `l0_tfc.GROUND_TRUTH_AUTOMATON`, re-verified live by the binding gate) |
| Executed golden test (the machine) | `tests/golden/test_credit_automaton_golden.py` — hand-derived burst traces, a rejected trace, the BDP anchor, the flagship point (rate 32 B/ns == Eq. 3 exactly, finite M=28672 completes 48 ns early), the quantization gap (W mod s)/D at Eq. 3's own convergence anchor |
| Abstraction statement (tested) | rate `min(B, floor(W/s)*s/(L+L_cr))` exact; Eq. 3 equals it iff `s \| W`; finite-collective divergence exact closed forms in `(-D, 0]` (credit-gated) / `0` (link-limited); conditions C1–C5 and modeling choices registered in `experiments/vertical_slice/assumptions_credit_automaton.yaml` |
| Evidence run (the abstraction layer) | run_id `dc7d83b6…` reproduces UNCHANGED — the analytical backend's outputs are untouched by the re-point; its golden test and claim link `C-UEC-TFC-R02` stand |

Why: the G6 review correction, made executable — Eq. 3's rate law is an
abstraction of the admission law with explicit conditions (return
timing, initial credit, batching/packetization, greedy sender), not a
consequence of FC-R02's safety rule alone. The automaton is the
behavioral ground truth; the closed form is its steady-state summary
with the exact divergence laws above. Disposition counts unchanged
(FC-R02 stays `simulated_behavior`); labels unchanged (everything here
stays E0 / IMPLEMENTED_UNVERIFIED).
