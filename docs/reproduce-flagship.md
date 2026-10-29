# Reproduction card — the UEC11-FC-R02 flagship slice

You are an external engineer with a clean clone. This card reproduces and
lets you attack ONE specific platform statement in under 10 minutes, with
no Docker and no network beyond the clone and a pip install.

**The statement under test.** UEC requirement **UEC11-FC-R02** (UEC 1.1
§3.6.15, Transport Flow Control: "A source MUST NOT transmit a packet if
it does not have credit") is executed by this platform as an honest
`simulated_behavior`: it is bound (machine-readable binding
`BIND-UEC11-FC-R02-L0TFC`) to the credit-window parameter of the
`analytical_l0_tfc` backend, and the binding causally changes the
O-CCT observable. Evidence level E0 — identity and determinism only.
This is a claim about the binding, NOT about physical validity: the
numeric parameters are free (not standard-derived, not measured), and the
only standard-derived constant is the 256-byte credit unit (UEC11-FC-R05).

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

## 3. Attack it

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
   `pytest -q tests/specir/test_bindings.py tests/specir/test_dispositions.py`:
   five tests must fail — the binding gate ("requirement ... has
   disposition 'unsupported' but the binding claims 'simulated_behavior'"),
   the frozen-count record (EXPECTED_COUNTS), the promotion-table rule
   (PROMOTED), and two negative fixtures whose tampered bindings now
   accidentally match the tampered requirement. The promotion cannot be
   undone silently. Revert.
2. In `src/essun/specir/bindings.py`, add a bogus parameter name (e.g.
   `"tfc_window_bites"`) to the binding's `parameters`. The binding gate
   must report "not a config field". Revert.
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

## 4. Full-suite check (optional, ~1 min)

```bash
.venv/bin/python -m pytest -q
```

Expected: green (the count grows with the project). If exactly the four
tests in `tests/specir/test_disposition_coverage.py` fail on the literals
`256` / `0 executed` / `0/445 = 0.0%`, you are on a commit where this
promotion landed before the coverage-report literal refresh — the report
itself (`.venv/bin/python tools/disposition_coverage.py`) is computed
live and prints `1/445 = 0.2%` executed with `unsupported 255`; the four
test literals are the stale pre-promotion record.

## Time budget

| Step | Time |
| --- | --- |
| clone + bootstrap | ~2 min |
| re-execute run + inspect | ~1 min |
| golden + binding tests | ~10 s |
| Attack A (parameter) | ~2 min |
| Attack B (binding) | ~2 min |
| Attack C (read/argue) | ~3 min |

Total: under 10 minutes without Attack C, ~10 with it.
