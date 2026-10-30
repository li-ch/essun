# Reproduction card — the UEC11-FC-R02 flagship slice

You are an external engineer with a clean clone. This card reproduces and
lets you attack ONE specific platform statement in under 10 minutes, with
no Docker and no network beyond the clone and a pip install.

**The statement under test.** UEC requirement **UEC11-FC-R02** (UEC 1.1
§3.6.15, Transport Flow Control: "A source MUST NOT transmit a packet if
it does not have credit") is executed by this platform as an honest
`simulated_behavior`: it is bound (machine-readable binding
`BIND-UEC11-FC-R02-AUTOMATON`) to the credit admission/return state
machine `src/essun/specir/credit_automaton.py` — an exact discrete
automaton, integer arithmetic, a transmit without credit a rejected
trace — and the analytical `analytical_l0_tfc` credit-window identity
(Eq. 3 below) is that automaton's DECLARED steady-state abstraction,
with tested conditions and exact divergences (section 3). The binding
causally changes the O-CCT observable. Evidence level E0 — identity and
determinism only. This is a claim about the binding, NOT about physical
validity: the numeric parameters are free (not standard-derived, not
measured), and the only standard-derived constant is the 256-byte
credit unit (UEC11-FC-R05).

The full evidence record with labels and honest limits:
`experiments/vertical_slice/tfc_r02_flagship.EVIDENCE.md`.

## 0. Setup (~2 min)

```bash
git clone <this repository> essun && cd essun
make bootstrap          # python3 -m venv .venv; pip install -e ".[dev]"
```

## 1. Re-execute the stored evidence run (~1 min)

```bash
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_tfc.yaml
```

Expected output (the run record is content-addressed; a rerun on this
commit must reproduce the id byte-for-byte):

```json
{
  "run_id": "dc7d83b6afa23ef33fd87512eb637bd737ab8ad905a6802bc6d0965be1da21d9",
  "run_dir": "results/dc7d83b6afa23ef33fd87512eb637bd737ab8ad905a6802bc6d0965be1da21d9"
}
```

Check what the run claims to have exercised:

```bash
.venv/bin/python - <<'EOF'
import json
import glob, os; d = sorted(glob.glob("results/*/"), key=os.path.getmtime)[-1]  # the run you just executed
obs = json.load(open(d + "/observations.json"))
print(obs["requirement_bindings"])
print(obs["observables"]["O-CCT"]["completion_time_ns_mean_exact"], "ns")
print(obs["observables"]["O-CCT"]["tfc"])
EOF
```

Expected: the binding block names `UEC11-FC-R02`; O-CCT mean is exactly
`3696` ns; the `tfc` block shows `window_bytes_exact = 12800`,
`credit_rtt_ns_exact = 400`, `effective_rate_bytes_per_ns_exact = 32`,
`bandwidth_delay_product_bytes_exact = 25600`, `window_limited: true`,
`peak_in_flight_bytes_exact = 12800`.

Sanity-check that number by hand (no code): with B = 64 B/ns, L = 200 ns,
credit return L_cr = 200 ns and window W = 12800 B, the admission law
caps the rate at W/(L+L_cr) = 12800/400 = 32 B/ns < 64 B/ns, so
t = 2*(8-1)/8 * 16384 / 32 + 2*(8-1)*200 = 28672/32 + 2800 = 3696 ns.
The unbound L0 ring gives 28672/64 + 2800 = 3248 ns — the binding costs
exactly 448 ns on this workload.

## 2. Re-run the golden tests (~10 s)

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_golden.py tests/specir/test_bindings.py
```

Expected: all pass. The expected values are derived inside the test file
by exact `Fraction` arithmetic (not copied from the model's output), and
the binding gate re-verifies the binding against the live requirement
registry, the anchor registry, the backend module and the observable
registry.

## 3. The automaton leg — the exact machine beneath Eq. 3 (G8)

Since 2026-10-30 the binding's backend is not the closed form but an
exact discrete machine: the **credit obligation automaton**
(`src/essun/specir/credit_automaton.py`), and Eq. 3 above is its
DECLARED steady-state abstraction. The machine: one credit context per
link, integer bytes and integer nanoseconds; `attempt(t, s)` applies
returns due, transmits iff `credit >= s` (consumes `s`, schedules a
return at `t + (L + L_cr)`); a transmit without credit is a REJECTED
trace — the requirement's MUST NOT, executed, never checked after the
fact. The abstraction statement is tested, not asserted:

- **Safety (any legal trace):** at most `W` bytes start inside any
  half-open window of length `L + L_cr` — the admission law IS a
  sliding-window bound.
- **Exact steady rate:** `min(B, floor(W/s)*s/(L+L_cr))`, achieved by
  the greedy work-conserving sender (link saturates iff
  `ceil((L+L_cr)*B/s) <= floor(W/s)`). Eq. 3's `min(B, W/(L+L_cr))`
  equals it exactly when the packet size divides the window; otherwise
  Eq. 3 is optimistic by exactly `(W mod s)/(L+L_cr)` — the
  packetization the closed form idealizes away.
- **Finite collectives:** a transfer of `n = q*k + r` packets
  (`k = floor(W/s)`) completes EARLIER than Eq. 3 predicts by exact
  closed forms (`k*u - D` when `r = 0`, else `r*(u - D/k)`; always
  inside `(-D, 0]` in the credit-gated regime) — the steady-state law
  charges a finite collective for a full credit pipeline it does not
  use.

```bash
.venv/bin/python -m pytest -q tests/golden/test_credit_automaton_golden.py
```

Expected: pass — every value hand-derived in the test's docstring
(burst schedules, a rejected trace, the BDP anchor, the flagship
operating point, the quantization boundary).

Then watch the abstraction diverge exactly as claimed (no code to
trust, ~1 min):

```bash
.venv/bin/python - <<'EOF'
from fractions import Fraction
from essun.specir import credit_automaton as ca

# The flagship operating point (run dc7d83b6's parameters), one 256-B
# packet: Eq. 3's rate law IS the automaton's steady state (s | W).
cfg = ca.AutomatonConfig(12800, 64, 200, 200, 256)
print("rate:", ca.steady_state_rate_exact(cfg), "== eq3:", ca.eq3_effective_rate(cfg))
print("finite M=28672: auto", ca.GreedyLinkExecutor(cfg).run_transfer(28672).completion_ns,
      "ns vs eq3", ca.eq3_completion_single_link(cfg, 28672), "ns")

# One credit unit past the BDP with D=401: Eq. 3 says line rate at its
# own convergence anchor; the automaton cannot use the ragged unit.
cfg2 = ca.AutomatonConfig(64*401, 64, 200, 201, 256)
print("gap:", ca.rate_divergence_exact(cfg2), "== (W mod s)/D:", Fraction(25664 % 256, 401))

# And the MUST NOT itself: a transmit without credit never executes.
print("legal:", ca.execute_trace(1024, 200, [(0,256),(4,256),(8,256),(12,256),(16,256)]).legal)
EOF
```

Expected: `32 == 32`; `1048 ns vs 1096 ns` (the finite collective
finishes 48 ns early — exactly `r*(u - D/k)`); `64/401 == 64/401`; and
`legal: False` (the t=16 transmit had no credit; the four-admission
prefix stands). Productive lines of attack are the declared assumptions
`experiments/vertical_slice/assumptions_credit_automaton.yaml`
(A-CA-RT return timing, A-CA-INIT initial grant, A-CA-GREEDY the
achieving schedule) and the conditions C1–C5 in the module docstring —
cell-quantized consumption is deliberately not assumed here; it is the
separate FC-R08 binding on the analytical backend.

## 4. Attack it

### Attack A — vary the binding's parameter (~2 min)

Edit `experiments/topologies/ring8_tfc_window_v1.yaml`:

- `window_bytes: 25600` (100 credit units = exactly the BDP). Predict
  first: 32 B/ns cap becomes min(64, 25600/400) = 64 B/ns — credits no
  longer gate, so O-CCT must equal the L0 identity 3248 ns and
  `window_limited` must be false. Rerun step 1: new `run_id` (inputs
  changed), `completion_time_ns_mean_exact == "3248"`.
- `window_bytes: 6400` (25 units). Predict: rate 6400/400 = 16 B/ns,
  t = 28672/16 + 2800 = 4592 ns. Rerun and check `"4592"`.
- `window_bytes: 250`. Not an integral number of 256-byte credit units:
  the loader must REFUSE the run with a `ValueError` citing
  `UEC11-FC-R05` (the spec's credit granularity is a binding semantic,
  not a convention). Confirm the error names the requirement.

`git checkout -- experiments/topologies/ring8_tfc_window_v1.yaml` to
restore (rerunning step 1 afterwards must give the original run_id
again — content addressing, nothing stale on disk).

### Attack B — break the binding, see the right failure (~2 min)

The promotion is supposed to be impossible to do silently. Test it:

1. In `src/essun/specir/uec_credits_flow_control.py`, change
   `UEC11-FC-R02`'s `disposition="simulated_behavior"` back to
   `"unsupported"`. Run
   `pytest -q tests/specir/test_bindings.py tests/specir/test_dispositions.py tests/specir/test_binding_coverage.py`:
   seven tests must fail — the binding gate ("requirement ... has
   disposition 'unsupported' but the binding claims 'simulated_behavior'"),
   the flagship-object check, the frozen-count record (EXPECTED_COUNTS)
   and the honest-rule check, the binding-coverage exactness property,
   and two negative fixtures whose premises the tamper breaks. The
   promotion cannot be undone silently. Revert.
2. In `src/essun/specir/bindings.py`, add a bogus parameter name (e.g.
   `"window_bites"`) to the FC-R02 binding's `parameters`. The binding
   gate must report "not a config field" (the automaton's config fields
   are checked live, exactly like a backend's). Revert.
3. Edit a quote inside `experiments/uec/anchor_registry.yaml` by one
   word. `pytest -q tests/specir/test_uec_anchor_registry.py` must fail
   the integrity check (quote not found in the extracted page). Revert.
   The anchored requirement cannot drift away from the source document.

### Attack C — attack the identity itself (read + argue, ~3 min)

The model is one file: `src/essun/backends/analytical/l0_tfc.py`. Its
identity is stated in the docstring and its honest limits are declared in
`CAPABILITIES["explicitly_unsupported"]` and in the evidence record.
Productive lines of attack (each is a deliberate scope boundary, so a
challenge means proposing the next model, not finding a bug):

- the rate law reads the admission law as a steady state — no fill/drain
  transient is modeled; with few chunks per phase the start-up burst
  matters and this identity ignores it;
- credit return is a single free latency (L_cr), not a scheduled
  credit-request/grant protocol (UEC §3.6.15 dynamics);
- one window per neighbor pair models per-PDC credit, not shared CCC
  pooling across PDCs (UEC11-FC-R16).

If you believe the identity is WRONG (not merely coarse), the project's
protocol is: minimize the counterexample, do not tune parameters until
curves match — see `CONTRIBUTING.md`.

## 5. Full-suite check (optional, ~1 min)

```bash
.venv/bin/python -m pytest -q
```

Expected: green (the count grows with the project). The live disposition
coverage report (`.venv/bin/python tools/disposition_coverage.py`, also
`make disposition-report`) prints the honest executed fraction of the
UEC profile — `2/445` today (UEC11-FC-R02 via the automaton binding,
UEC11-FC-R08 via the analytical cell law), computed from the live
registry, never a stored table.

## Time budget

| Step | Time |
| --- | --- |
| clone + bootstrap | ~2 min |
| re-execute run + inspect | ~1 min |
| golden + binding tests | ~10 s |
| automaton leg (golden + divergence REPL) | ~2 min |
| Attack A (parameter) | ~2 min |
| Attack B (binding) | ~2 min |
| Attack C (read/argue) | ~3 min |

Total: ~10 minutes without Attack C, ~12 with it.
