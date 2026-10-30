# Reproduction card — the UEC 1.1 credit/TFC family

You are an external engineer with a clean clone. This card reproduces
and lets you attack the platform's executed **credit/TFC family**: four
requirements of UEC 1.1 §3.6.15, each one reproducible in under 10
minutes on its own, with no Docker and no network beyond the clone and a
pip install. One shared setup (section 0); one part per requirement; the
timings in the budget table at the end were measured on a cold clone.

| Part | Requirement (UEC 1.1 §3.6.15) | Executed as | Carrier | Evidence record |
| --- | --- | --- | --- | --- |
| I | **UEC11-FC-R02** — "A source MUST NOT transmit a packet if it does not have credit" | `simulated_behavior` | binding `BIND-UEC11-FC-R02-AUTOMATON` → the exact credit automaton `src/essun/specir/credit_automaton.py`, with the analytical `analytical_l0_tfc` identity (Eq. 3) as its DECLARED steady-state abstraction | `experiments/vertical_slice/tfc_r02_flagship.EVIDENCE.md` |
| II | **UEC11-FC-R08** — `credit_used = ROUNDUP(tfc_pkt_size ÷ tfc_dest_cell_size) × tfc_dest_cell_size` | `simulated_behavior` | binding `BIND-UEC11-FC-R08-L0TFC` → the opt-in `tfc.dest_cell_size` parameter of `analytical_l0_tfc` | `experiments/vertical_slice/tfc_r08_cell.EVIDENCE.md` |
| III | **UEC11-FC-R09** — source and destination use the same `tfc_pkt_overhead` constant (default 256 B) | `simulated_behavior` | binding `BIND-UEC11-FC-R09-L0TFC` → the opt-in `tfc.pkt_overhead` parameter, composed inside the R08 ROUNDUP | `experiments/vertical_slice/tfc_r09_pkt.EVIDENCE.md` |
| IV | **UEC11-FC-R05** — the credit-arrival arithmetic (256-B units, wrapping `pds.credit` counter) | `conformance_test` | profile checks `UEC11-CHK-12/13/14` → golden test `tests/golden/test_credit_arrival_golden.py` (no binding, no backend — a check, per the D2 profile rule) | `experiments/vertical_slice/tfc_r05_credit_arithmetic.EVIDENCE.md` |

All four carry evidence level **E0 — identity and determinism only**.
Every `simulated_behavior` here is a claim about the BINDING (the
requirement's law causally affects outputs through a declared,
load-checked parameter or an exact machine), NOT about physical
validity: nothing is calibrated against hardware. B, L, W, L_cr (shared
on purpose across the family), the cell value and the overhead value
are FREE parameters. The standard-derived constants in the family are:
the 256-byte credit unit (UEC11-FC-R05), the cell domain 256..9216 B in
256-B multiples (values cited to UEC11-FC-R07, whose own obligation
stays unsupported), and the overhead default 256 B with bounds 0..256 B
(cited to UEC11-FC-R09/R10, whose obligations stay unsupported).

## 0. Setup (once for the whole card, ~2 min)

```bash
git clone <this repository> essun && cd essun
make bootstrap          # python3 -m venv .venv; pip install -e ".[dev]"
```

## Part I — UEC11-FC-R02, the admission law (the flagship slice)

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
causally changes the O-CCT observable. This is a claim about the
binding, NOT about physical validity: the numeric parameters are free
(not standard-derived, not measured), and the only standard-derived
constant on this leg is the 256-byte credit unit (UEC11-FC-R05).

The full evidence record with labels and honest limits:
`experiments/vertical_slice/tfc_r02_flagship.EVIDENCE.md`.

### 1. Re-execute the stored evidence run (~1 min)

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

### 2. Re-run the golden tests (~10 s)

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_golden.py tests/specir/test_bindings.py
```

Expected: all pass. The expected values are derived inside the test file
by exact `Fraction` arithmetic (not copied from the model's output), and
the binding gate re-verifies the binding against the live requirement
registry, the anchor registry, the backend module and the observable
registry.

### 3. The automaton leg — the exact machine beneath Eq. 3 (G8)

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
separate FC-R08 binding on the analytical backend (Part II).

### 4. Attack it

#### Attack A — vary the binding's parameter (~2 min)

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

#### Attack B — break the binding, see the right failure (~2 min)

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
   promotion cannot be undone silently. Revert. (This failure list was
   re-verified at the 2026-10-30 automaton re-point and again by the
   2026-10-30 family-card cold verification: still seven.)
2. In `src/essun/specir/bindings.py`, add a bogus parameter name (e.g.
   `"window_bites"`) to the FC-R02 binding's `parameters`. The binding
   gate must report "not a config field" (the automaton's config fields
   are checked live, exactly like a backend's). Revert.
3. Edit a quote inside `experiments/uec/anchor_registry.yaml` by one
   word. `pytest -q tests/specir/test_uec_anchor_registry.py` must fail
   the integrity check (quote not found in the extracted page). Revert.
   The anchored requirement cannot drift away from the source document.

#### Attack C — attack the identity itself (read + argue, ~3 min)

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

## Part II — UEC11-FC-R08, the cell law

**The statement under test.** UEC requirement **UEC11-FC-R08** (UEC 1.1
§3.6.15, DEFINITIONAL): `credit_used = ROUNDUP(tfc_pkt_size ÷
tfc_dest_cell_size) × tfc_dest_cell_size` — a destination's credit is
consumed in whole cells, so a packet that does not fill its last cell
still pays for it. Executed as `simulated_behavior` via binding
`BIND-UEC11-FC-R08-L0TFC`: the opt-in parameter `tfc.dest_cell_size`
(validated at load to the UEC11-FC-R07-cited domain 256..9216 B in
256-B multiples) makes the analytical law consume `cq =
ROUNDUP(c/cell) × cell` of credit per packet (ring chunk `c` as
`tfc_pkt_size`), so the useful-data rate becomes
`min(B, (c/cq) · W/(L+L_cr))` — quantization waste spends credit
without moving bytes. Full record:
`experiments/vertical_slice/tfc_r08_cell.EVIDENCE.md`.

### 5. Re-execute the stored evidence run (~1 min)

```bash
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_tfc_cell.yaml
```

Expected: `run_id e74ecec28540dcd0eec79f4d8386695bd54c9570220a9c4ee7da0186f3c3315b`,
byte-for-byte. The same B, L, W, L_cr as the flagship — the ONE new
input is the cell (9216 B, the per-packet strategy cell the
requirement's own text names).

Inspect the run the same way as step 1 (latest `results/*/`):

```bash
.venv/bin/python - <<'EOF'
import json
import glob, os; d = sorted(glob.glob("results/*/"), key=os.path.getmtime)[-1]
obs = json.load(open(d + "/observations.json"))
print([b["requirement_id"] for b in obs["requirement_bindings"]])
print(obs["observables"]["O-CCT"]["completion_time_ns_mean_exact"], "ns")
cell = obs["observables"]["O-CCT"]["tfc"]["cell"]
print({k: cell[k] for k in ("dest_cell_size_bytes", "chunk_bytes",
      "credit_used_bytes_exact", "credit_efficiency_exact",
      "effective_data_rate_bytes_per_ns_exact")})
EOF
```

Expected: bindings `['UEC11-FC-R02', 'UEC11-FC-R08']`; O-CCT mean
exactly `"6832"` ns; the cell block shows `dest_cell_size_bytes = 9216`,
`chunk_bytes = 2048`, `credit_used_bytes_exact = "9216"`,
`credit_efficiency_exact = "2/9"`,
`effective_data_rate_bytes_per_ns_exact = "64/9"`.

Sanity-check by hand (no code): chunk c = 16384/8 = 2048 B; one 9216-B
cell per packet, cq = 9216, efficiency 2/9; the admission cap
W/(L+L_cr) = 32 B/ns now moves useful data at (2/9)·32 = 64/9 B/ns;
t = 28672/(64/9) + 2800 = 4032 + 2800 = **6832 ns**. The waste costs
exactly 28672·(9/64 − 1/32) = 3136 ns over the R02 identity 3696 ns,
and O-CONSERVATION is unchanged — a cell gates rate, never byte count
(check `obs["observables"]["O-CONSERVATION"]` in the same REPL: still
green, same bytes moved).

### 6. Re-run the golden tests (~10 s)

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_cell_golden.py tests/specir/test_bindings.py
```

Expected: all pass, every expected value derived in-test by exact
`Fraction` arithmetic, including the requirement's own worked example
(4352 B against 512-B cells ⇒ 4608 B of credit), the zero-waste
convergence boundary (`c ≡ 0 (mod cell)` ⇒ the R02 identity 3696 ns
exactly, cells 256/512/1024/2048), and the out-of-domain negatives
(128, 9472, 1000, 253.5, 0, −256 all rejected citing UEC11-FC-R07; the
closed boundaries 256 and 9216 load).

#### Attack D — vary the cell (~2 min)

Edit `experiments/topologies/ring8_tfc_cell_window_v1.yaml`:

- `dest_cell_size: 2048`. Predict first: the chunk exactly fills one
  cell, cq = 2048, efficiency 1, rate back to 32 B/ns — O-CCT must
  equal the R02 identity `"3696"` exactly and
  `credit_efficiency_exact` must be `"1"` (zero waste converges to the
  un-quantized law). Rerun step 5 and check.
- `dest_cell_size: 768`. Predict: cq = ROUNDUP(2048/768)·768 = 3 cells
  = 2304 B, efficiency 8/9, rate 256/9 B/ns,
  t = 28672·9/256 + 2800 = 3808 ns. Rerun and check `"3808"`.
- `dest_cell_size: 1000`. Not an integral number of 256-B credit units
  inside the domain: the loader must REFUSE with a `ValueError` citing
  `UEC11-FC-R07` (the cell domain is a binding semantic). Confirm the
  error names the requirement.

`git checkout -- experiments/topologies/ring8_tfc_cell_window_v1.yaml`
to restore; rerunning step 5 gives the original run_id again.

#### Attack E — break the promotion, see the right failure (~2 min)

1. In `src/essun/specir/uec_credits_flow_control.py`, change
   `UEC11-FC-R08`'s `disposition="simulated_behavior"` back to
   `"informational"`. Run
   `pytest -q tests/specir/test_bindings.py tests/specir/test_dispositions.py tests/specir/test_binding_coverage.py`:
   four tests must fail — the binding gate ("bindings claim
   simulated_behavior for requirements that do not carry it:
   ['UEC11-FC-R08']"), the frozen-count record (EXPECTED_COUNTS) and
   the honest-rule check, and the binding-coverage exactness property.
   (Measured on the cold clone: 4 failed, 51 passed.) The un-promotion
   cannot happen silently. Revert.
2. In `src/essun/specir/bindings.py`, add a bogus parameter name (e.g.
   `"tfc_dest_cell_bites"`) to the FC-R08 binding's `parameters`. The
   binding gate must report "not a config field" (the parameter is
   checked against the backend's live config fields). Revert.
3. The anchor-tamper leg is Attack B.3 — one registry covers the whole
   family; it is not repeated here.

#### Attack F — attack the law itself (read + argue, ~2 min)

The law is one ROUNDUP inside `src/essun/backends/analytical/l0_tfc.py`
(cell provenance blocks in the O-CCT observable). Productive lines of
attack (deliberate scope boundaries — a challenge means proposing the
next model, not finding a bug):

- waste spends credit, never wire bytes: O-CONSERVATION is unchanged
  by construction (you checked it in step 5). If you think quantization
  should also serialize bytes on the wire, that is the packetization
  exclusion of the analytical family, not this law;
- the fluid steady-window reading grants fractional cells-in-window
  (12800/9216 = 25/18): integer packet-floor effects are the declared
  exclusion; the exact machine to argue about quantized ADMISSION is
  the Part I automaton, which deliberately does not assume cells;
- one cell per neighbor pair: per-direction cell asymmetry
  (UEC11-FC-R12) is declared unsupported.

If you believe the law is WRONG (not merely coarse): minimize the
counterexample, do not tune — `CONTRIBUTING.md`.

## Part III — UEC11-FC-R09, the overhead law

**The statement under test.** UEC requirement **UEC11-FC-R09** (UEC 1.1
§3.6.15, MUST): source and destination must use the same constant
`tfc_pkt_overhead` — extra destination memory per packet — which
defaults to 256 B (one credit unit). Executed as `simulated_behavior`
via binding `BIND-UEC11-FC-R09-L0TFC`: the opt-in parameter
`tfc.pkt_overhead` (bounds 0..256 B cited to UEC11-FC-R10, whose own
recommendation stays unsupported; requires a declared cell — the
ROUNDUP it feeds is the R08 law) composes the packet as
`tfc_pkt_size = c + tfc_pkt_overhead` inside the cell law, so
`cq = ROUNDUP((c + overhead)/cell) × cell`. The overhead spends credit
without moving modeled bytes. Full record:
`experiments/vertical_slice/tfc_r09_pkt.EVIDENCE.md`.

### 7. Re-execute the stored evidence run (~1 min)

```bash
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_tfc_pkt.yaml
```

Expected: `run_id 834c1ffe94689654753727186039f08486e09030328da880ad0ae23724f83484`,
byte-for-byte. This topology sits at the SPEC'S DEFAULT POINT: cell 256
(R07's default) + overhead 256 (R09's default).

Inspect (same latest-results REPL as before):

```bash
.venv/bin/python - <<'EOF'
import json
import glob, os; d = sorted(glob.glob("results/*/"), key=os.path.getmtime)[-1]
obs = json.load(open(d + "/observations.json"))
print([b["requirement_id"] for b in obs["requirement_bindings"]])
print(obs["observables"]["O-CCT"]["completion_time_ns_mean_exact"], "ns")
cell = obs["observables"]["O-CCT"]["tfc"]["cell"]
print(cell["pkt"], "|", cell["credit_used_bytes_exact"],
      cell["credit_efficiency_exact"], cell["effective_data_rate_bytes_per_ns_exact"])
EOF
```

Expected: bindings `['UEC11-FC-R02', 'UEC11-FC-R08', 'UEC11-FC-R09']`;
O-CCT mean exactly `"3808"` ns; the pkt block shows
`overhead_bytes = 256`, `tfc_pkt_size_bytes_exact = "2304"`; the cell
block shows `credit_used_bytes_exact = "2304"`,
`credit_efficiency_exact = "8/9"`,
`effective_data_rate_bytes_per_ns_exact = "256/9"`.

Sanity-check by hand (no code): payload c = 2048 B + default overhead
256 B = tfc_pkt_size 2304 B = exactly 9 aligned 256-B cells, cq = 2304;
efficiency 2048/2304 = 8/9; rate (8/9)·32 = 256/9 B/ns;
t = 28672·9/256 + 2800 = 1008 + 2800 = **3808 ns**. The default
constant costs exactly 28672·(9/256 − 8/256) = 112 ns per op over the
overhead-less identity 3696 ns — one extra credit unit per packet.
O-CONSERVATION unchanged: the overhead spends credit, never wire bytes.

### 8. Re-run the golden tests (~10 s)

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_pkt_golden.py tests/specir/test_bindings.py
```

Expected: all pass, every expected value derived in-test, including
the R08 worked example composed natively (4096 + 256 = 4352 B against
512-B cells ⇒ 4608 B), the overhead-is-cell-quantized law (any 1..256 B
overhead at an aligned 256-B cell lands the same ninth cell), the
per-packet 9216-B cell absorbing the whole default overhead (6832 ns =
the Part II literal), the convergence boundaries (overhead 0 ⇒ the
Part II law at every cell; overhead 0 with `c ≡ 0 (mod cell)` ⇒ the
R02 identity 3696 ns exactly), and the negatives (out-of-domain
overheads rejected citing UEC11-FC-R10; overhead without a cell
rejected citing the binding).

#### Attack G — vary the overhead and the cell (~2 min)

Edit `experiments/topologies/ring8_tfc_pkt_window_v1.yaml`:

- `pkt_overhead: 0`. Predict: tfc_pkt_size = 2048, cell-aligned at 256,
  cq = 2048, efficiency 1 — O-CCT must equal the R02 identity `"3696"`
  exactly (declared zero behaves like an absent parameter in the LAW;
  only the run id and the R09 provenance entry differ). Rerun step 7.
- `pkt_overhead: 1`. Predict: tfc_pkt_size = 2049 still needs the ninth
  256-B cell, cq = 2304, efficiency 8/9 — O-CCT stays `"3808"`
  (the overhead itself is cell-quantized: at this aligned cell any
  1..256 B overhead costs the same one extra cell). Rerun and check.
- `dest_cell_size: 9216` (keep `pkt_overhead: 256`). Predict: the whole
  2304-B packet fits one 9216-B cell, cq = 9216, efficiency 2/9 —
  O-CCT = `"6832"`, exactly the Part II waste-regime literal: the
  per-packet strategy cell absorbs the default overhead entirely. Rerun
  and check.
- `pkt_overhead: 257`. Outside the 0..256 B bounds: the loader must
  REFUSE with a `ValueError` citing `UEC11-FC-R10`. Confirm the error
  names the requirement.
- Delete the `dest_cell_size:` line (keep `pkt_overhead: 256`). An
  overhead without a cell has no ROUNDUP law to move — the loader must
  REFUSE citing the binding (`BIND-UEC11-FC-R09-L0TFC`) rather than
  inventing a second consumption law. Confirm the error names the
  binding.

`git checkout -- experiments/topologies/ring8_tfc_pkt_window_v1.yaml`
to restore; rerunning step 7 gives the original run_id again.

#### Attack H — break the promotion, see the right failure (~2 min)

1. In `src/essun/specir/uec_credits_flow_control.py`, change
   `UEC11-FC-R09`'s `disposition="simulated_behavior"` back to
   `"unsupported"`. Run
   `pytest -q tests/specir/test_bindings.py tests/specir/test_dispositions.py tests/specir/test_binding_coverage.py`:
   four tests must fail for exactly the same classes of reason as
   Attack E.1 — the binding gate, the frozen counts, and the coverage
   exactness property. (Measured on the cold clone: 4 failed, 51
   passed.) Revert.
2. In `src/essun/specir/bindings.py`, add a bogus parameter name (e.g.
   `"tfc_pkt_overhede"`) to the FC-R09 binding's `parameters`. The
   binding gate must report "not a config field". Revert.

#### Attack I — attack the law itself (read + argue, ~2 min)

- the overhead is destination-buffer accounting only (registered
  assumption `A-TFCP-OVH-BUFFER` in
  `experiments/vertical_slice/assumptions_tfc_pkt.yaml`): it spends
  credit, never wire bytes — header serialization on the wire is the
  analytical family's packetization exclusion, and O-CONSERVATION is
  unchanged by construction (check it in step 7);
- the MUST's same-constant-at-both-ends property is STRUCTURAL here
  (one model, one constant), stated as structure, not an executed
  protocol claim — a two-constant split would be the shape of a real
  counterexample, and it needs a protocol model, not this identity;
- per-direction asymmetry (UEC11-FC-R12) and the R10 configurability
  OBLIGATION are cited (values in), never executed.

If you believe the law is WRONG (not merely coarse): minimize the
counterexample, do not tune — `CONTRIBUTING.md`.

## Part IV — UEC11-FC-R05, the arrival arithmetic (a conformance check)

**The statement under test.** UEC requirement **UEC11-FC-R05** (UEC 1.1
§3.6.15, DEFINITIONAL): one credit unit is 256 bytes (`>> 8`);
`pds.credit` is a monotonically increasing wrapping counter (24-bit
field, UEC11-FC-R01); on an arriving Credit value,
`credit += (Credit − cumulative_credit) >> 8` if `Credit >
cumulative_credit`, then `cumulative_credit = Credit` — nothing on a
no-op. Executed as `conformance_test` — the platform's first: the
carrier is the golden test `tests/golden/test_credit_arrival_golden.py`
(13 tests, every expected value derived in-test by exact integer
arithmetic; no floats, no `random`), carried by the profile CHECKS
entries `UEC11-CHK-12/13/14`. Per the D2 profile rule a binding may
reference only a `simulated_behavior` requirement, so the carrier is a
check, NEVER a binding; no backend was extended — the law demands none.

**Stated up front, honestly:** a check has NO run record on this
platform. The orchestrator stamps content-addressed run records for
manifest executions only, and a claims-index link requires a run id —
none is fabricated (see
`experiments/vertical_slice/tfc_r05_credit_arithmetic.EVIDENCE.md`).
The check's execution evidence is the committed golden itself,
deterministic (fixed LCG constants, no clock, no RNG).

### 9. Re-execute the check and its gates (~1 min)

```bash
.venv/bin/python -m pytest -q tests/golden/test_credit_arrival_golden.py
.venv/bin/python -m pytest -q tests/specir/test_dispositions.py tests/specir/test_bindings.py tests/specir/test_binding_coverage.py
```

Expected: 13 passed; then the gates pass — the frozen disposition
counts, the promotion-table parity, and the conformance leg of the
binding-coverage property (checks ↔ `conformance_test`, verified both
live and through the built artifact). Then rebuild the profile the
check lives in and watch it come out byte-identical:

```bash
.venv/bin/python experiments/uec/build_semantic_profile.py
git diff --stat experiments/uec/semantic_profile.yaml     # expected: NO output
```

Expected review record: `445 requirements (187 informational / 254
unsupported / 3 simulated_behavior; constraint 0, conformance_test 1,
not_applicable 0; 4 executed), 67 free parameters, 3 binding(s), 14
check(s)` — and no diff, because the committed artifact IS the
regeneration of the live registry.

### 10. Hand-execute the law (no code to trust, ~2 min)

Re-derive the pins from the spec sentence itself — this snippet is the
law as written, not an import of the implementation:

```bash
.venv/bin/python - <<'EOF'
FIELD = 1 << 24                    # pds.credit width (UEC11-FC-R01)
def step(credit, cumulative, arrival):
    d = (arrival - cumulative) % FIELD   # the counter's wrapping order
    if 0 < d < FIELD // 2:               # an increase; half-range is not
        return credit + (d >> 8), arrival
    return credit, cumulative            # no-op: nothing changes

print(step(0, 0, 256))            # one whole unit arrives
print(step(0, 0, 2**23))          # exactly half the range: NOT an increase
print(step(0, 2**24 - 512, 255))  # an increase SPANNING the 24-bit wrap
credit, cumulative = 0, 0
for a in (256, 768, 1024, 4096):  # the golden's whole-unit trace
    credit, cumulative = step(credit, cumulative, a)
print("whole-unit total:", credit)
credit, cumulative = 0, 0
for a in (199, 399, 599):         # sub-unit slivers
    credit, cumulative = step(credit, cumulative, a)
print("sub-unit total:", credit, "| direct (599-0)>>8:", 599 >> 8)
EOF
```

Expected: `(1, 256)`; `(0, 0)`; `(2, 255)` — the wrapped difference is
(255 + 512) = 767 = 2·256 + 255, so 2 units cross the wrap;
`whole-unit total: 16` (grants 1+2+1+12); `sub-unit total: 0 | direct
(599-0)>>8: 2` — each sub-unit increase is below one unit and the
per-arrival floors do NOT telescope: the algorithm as written, pinned,
not repaired (whole-unit allocation is the R07-cited discipline real
grants live in). These are the same values the committed golden pins.

#### Attack J — misread the arithmetic, see the pins bite (~2 min)

The golden executes four named misreadings for contrast and each MUST
differ from the pinned spec values. Run that tooth directly:

```bash
.venv/bin/python -m pytest -q "tests/golden/test_credit_arrival_golden.py::test_negative_misreadings_are_distinguished_by_the_pins"
```

Then break the law yourself in the REPL and watch each misreading
diverge from step 10's values:

```bash
.venv/bin/python - <<'EOF'
FIELD = 1 << 24
# Misreading 1 — plain-integer comparison (no wrapping order):
print("plain-integer at the wrap:", 255 - (2**24 - 512) if 255 > 2**24 - 512 else "no increase -> 0 units (spec: 2)")
# Misreading 2 — wrong unit constant (>>7 = a 512-B unit):
print(">>7 unit:", 256 >> 7, "units (spec: 1)")
# Misreading 3 — grant without the monotone guard, on a reordered arrival:
print("no-guard grant on stale 256 after cumulative 4096:", (256 - 4096) >> 8, "units (spec: ignore)")
EOF
```

Expected: the plain-integer reading loses the wrap-spanning increase
entirely (0 units vs the spec's 2); the `>>7` reading doubles the
whole-unit grant; the unguarded reading books a NEGATIVE grant on a
reordered arrival the spec's guard must ignore. That is what "the pins
have teeth" means: a wrong law cannot pass as the right one.

#### Attack K — un-promote the disposition (~1 min)

In `src/essun/specir/uec_credits_flow_control.py`, change
`UEC11-FC-R05`'s `disposition="conformance_test"` back to
`"informational"`. Run
`pytest -q tests/specir/test_dispositions.py tests/specir/test_bindings.py tests/specir/test_binding_coverage.py tests/specir/test_disposition_coverage.py tests/specir/test_uec_semantic_profile.py`:
eleven tests must fail — the frozen counts (EXPECTED_COUNTS and the
honest rule), the promotion-table parity's conformance leg
(`test_conformance_promotions_are_carried_by_profile_checks`), the five
coverage-report gates (module counts, profile totals, and the rendered
and CLI forms), and the three profile-artifact gates (live-registry
match, live totals, byte-identical rebuild — the committed artifact
says `conformance_test: 1`; the tampered registry rebuilds 0).
(Measured on the cold clone: 11 failed, 92 passed.) The platform's
first conformance count cannot be undone silently. Revert.

#### Attack L — attack the one modeling choice (read + argue, ~2 min)

The check's single genuine modeling choice is `A-TFCA-ORDER`
(`experiments/vertical_slice/assumptions_tfc_credit_arithmetic.yaml`):
the spec's TFC text states the monotone WRAPPING counter but does not
spell out the wrap comparison, so the check reads the `>` guard in the
wrapping counter's order (open half range), citing the ordering law the
same specification states for CBFC cyclic counters (UEC11-FC-R28). The
productive challenge is textual, not empirical: cite the spec if you
read the order differently — and note that the plain-integer
alternative is exactly Attack J's misreading 1, which loses every
increase spanning the wrap. Scope fences (each a deliberate exclusion,
not a defect): the check is source-side bookkeeping only — no timing,
no link, no admission coupling (that is Part I's automaton); bring-up
(R14), credit request/grant (R15), the retransmission exemption (R06)
and shared-CCC pooling (R16) stay unexecuted.

If you believe the check is WRONG (not merely narrow): minimize the
counterexample, do not tune — `CONTRIBUTING.md`.

## 11. Full-suite check and the demo gate (optional, ~2 min)

```bash
.venv/bin/python -m pytest -q
```

Expected: green (the count grows with the project). The live disposition
coverage report (`.venv/bin/python tools/disposition_coverage.py`, also
`make disposition-report`) prints the honest executed fraction of the
UEC profile — `4/445 = 0.9%` today (UEC11-FC-R02 via the automaton
binding; UEC11-FC-R08 and UEC11-FC-R09 via the analytical cell and
overhead laws; UEC11-FC-R05 via the conformance check — in the
credits/flow-control module: 3 simulated_behavior + 1 conformance_test
of 66), computed from the live registry, never a stored table. For the
one-command public-gate story (suite + golden run ids + sweep + figure
+ paper-check; the two Docker legs auto-skip when no daemon is
reachable), run `make demo`.

## Time budget (measured on a cold clone, 2026-10-30)

Every leg above was executed verbatim on a fresh `git clone` (file://
transport) of this repository on an Apple-silicon Mac (darwin 27,
arm64); the machine times below are command wall-times with a warm pip
cache (a first bootstrap on a new machine adds package download time —
the ~2 min label on section 0 is that ceiling). The per-step "~" labels
in the section headers are hands-on ceilings including your reading,
predicting and editing; the machine does its part in seconds:

| Leg | Machine time | Notes |
| --- | --- | --- |
| clone + bootstrap (once, §0) | 0.3 s + 10 s | file:// clone; warm pip cache |
| Part I §1 (flagship run + inspect) | 0.3 s | run_id byte-identical: `dc7d83b6…` |
| Part I §2 (goldens + binding gate) | 0.4 s | 23 passed |
| Part I §3 (automaton golden + REPL) | 0.2 s | 10 passed; 4 divergence lines |
| Attack A (R02 parameter, 3 edits) | 0.4 s | 3248/False, 4592, R05 refusal, id restored |
| Attack B (R02 binding; B.1 = 7 failed) | 1.0 s | B.2 "not a config field"; B.3 quote not found |
| Part II §5–§6 (R08 run + inspect + goldens) | 0.4 s | run_id `e74ecec2…`; 23 passed |
| Attack D (R08 cell, 3 edits) | 0.4 s | 3696/eff 1, 3808/eff 8/9, R07 refusal, id restored |
| Attack E (R08 promotion; E.1 = 4 failed) | 0.8 s | E.2 "not a config field of analytical_l0_tfc" |
| Part III §7–§8 (R09 run + inspect + goldens) | 0.5 s | run_id `834c1ffe…`; 27 passed |
| Attack G (R09 overhead/cell, 5 edits) | 0.6 s | 3696, 3808, 6832, R10 + binding refusals, id restored |
| Attack H (R09 promotion; H.1 = 4 failed) | 0.7 s | H.2 "not a config field" |
| Part IV §9–§10 (check + gates + rebuild + REPL) | 0.8 s | 13 + 55 passed; artifact byte-identical |
| Attack J (R05 misreadings) | 0.2 s | 1 pin test + REPL contrast |
| Attack K (R05 un-promotion = 11 failed) | 1.0 s | counts, parity, coverage, artifact gates |
| full suite (§11, optional) | 7.4 s | 2297 passed, 92 skipped |
| `make demo` (§11, optional) | 9.0 s | PASS — all 7 steps green (full Docker mode) |

Per-requirement machine-time totals: Part I ≈ 2.3 s, Part II ≈ 1.6 s,
Part III ≈ 1.8 s, Part IV ≈ 2.0 s — every part reproduces in well under
10 minutes even doubled for hands-on time on an unfamiliar machine, as
the family ladder requires. The read+argue attacks (C, F, I, L) add
~2–3 min of reading each and need no machine.
