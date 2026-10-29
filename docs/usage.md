# Using essun — the 30-minute path from clone to first contribution

This guide is built around one arc, and nothing else: **read the
instructions → run a small analysis → change a parameter → see the
expected effect → submit a small contribution** — all inside 30 minutes,
with no Docker and no compiled dependencies. Everything past the arc
(other models, sweeps, the gate chain) lives in "Beyond 30 minutes" at
the bottom and is not on the timed path.

| stage | you will | budget |
|---|---|---|
| 1 | read how a run works (one diagram, three rules) | ~3 min |
| 2 | run the committed golden smoke analysis, read its record | ~4 min |
| 3 | change ONE free parameter on your own copy of the topology | ~6 min |
| 4 | see the predicted effect, and prove determinism to yourself | ~5 min |
| 5 | contribute your own workload + manifest as a branch | ~10 min |

A cold, timed walkthrough of exactly these stages completed in
**[REHEARSAL: minutes, walkthrough, 2026-10-29, status]** on the
reference Mac; the placeholder is replaced only with a measured number.

Every command below was executed on this repository on 2026-10-29
(reference Mac, development tree at `the tip of main`); every output block is
the real output, not an illustration. Absolute paths appear exactly as
printed on that machine. Evidence label for everything here: **E0** —
deterministic identities and arithmetic, no empirical claim; nothing in
this repo is calibrated against hardware (see the README "Current
state" section).

Prerequisites: `make bootstrap` (Python 3.10+; ~36 MB venv; ~7 s on the
reference machine with a warm pip cache — a first run on a new machine
adds package download time). **Docker is not needed for anything in
this guide** — the analytical L0 backend runs in-process. `results/` is
git-ignored: your runs stay local.

## Stage 1 — read how a run works (3 minutes)

One experiment = one YAML **manifest** that references five input files
by repo-relative path, names one backend, and lists the observables to
emit:

```text
                 ┌─ workload_ir          what collectives run (sizes, steps)
                 ├─ infra_graph          the fabric (topology + free parameters)
experiment ──────├─ standard_profile     standard semantics applied (none today)
 manifest        ├─ implementation_profile  which model implementation runs
                 └─ assumptions          the free-parameter registry
```

Three rules carry the whole guide:

1. **Every numeric fabric value is a free parameter you own.** Nothing
   is standard-derived or measured; the committed registries
   (`experiments/vertical_slice/assumptions_l0.yaml`, 26 entries, all
   PROPOSED) exist to keep that honest. If you change a number, you
   changed an assumption, not a fact.
2. **Runs are content-addressed.** `make run` stores a record under
   `results/<run_id>/` where `run_id` is a SHA-256 over the content —
   the same manifest, inputs, and code always produce the same id and
   byte-identical records. Reruns are replays, not new measurements.
3. **Numbers must hand-check.** The L0 backend is a closed form; every
   stage below includes the arithmetic so you can verify the record
   against your own head-math. If they ever disagree, that is a model
   bug, not a tuning knob — `O-CONSERVATION` violations raise instead
   of degrading.

## Stage 2 — run a small analysis (4 minutes)

```bash
make run EXP=experiments/vertical_slice/w1_decode_smoke.yaml
```

```text
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_smoke.yaml
{
  "run_id": "146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1",
  "run_dir": "/Users/li/simsun/essun/results/146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1"
}
```

This is the repo's golden smoke run (id pinned in
`experiments/vertical_slice/w1_decode_smoke.GOLDEN.md`): the W1 Dense TP
Decode workload — 6 AllReduce ops of 16 KiB — on the committed 8-rank
ring (`bytes_per_ns: 64`, `hop_latency_ns: 200`). Read the record:

```bash
python3 -m json.tool results/146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1/observations.json
```

The interesting parts (the `per_op` list repeats per operation; elided):

```json
{
  "backend_id": "analytical_l0",
  "model": {
    "hop_latency_ns_exact": "200",
    "link_bytes_per_ns_exact": "64",
    "ranks": 8,
    "topology_id": "ring8_free_v1",
    "transport_model": "bandwidth_latency_ring"
  },
  "observables": {
    "O-CCT": {
      "completion_time_ns_max": 3248.0,
      "completion_time_ns_mean": 3248.0,
      "completion_time_ns_mean_exact": "3248",
      "kind": "analytical",
      "ops": 6
    },
    "O-CONSERVATION": {
      "kind": "exact",
      "ops_checked": 6,
      "total_wire_bytes_exact": "1376256",
      "violations": 0
    }
  }
}
```

**Completion time is 3248 ns per op — remember that number.** Exact
fractions ride alongside every float (`*_exact` fields); nothing is
rounded behind your back.

## Stage 3 — change one parameter (6 minutes)

The scenario: *what happens to collective completion time on the 8-rank
ring if link bandwidth is half the committed free parameter?* You touch
no model code: copy one topology file, change one number, point a
copied manifest at it.

```bash
cp experiments/topologies/ring8_free_params.yaml \
   experiments/topologies/ring8_slow_v1.yaml
cp experiments/vertical_slice/w1_decode_smoke.yaml \
   experiments/vertical_slice/w1_decode_smoke_ring8_slow.yaml
```

Edit the topology copy so it reads (changed from the original: the
`topology_id` and `bytes_per_ns`):

```yaml
# Transport-agnostic analytical topology: unidirectional ring of 8 ranks.
# Copy of experiments/topologies/ring8_free_params.yaml with ONE free
# parameter changed: link bandwidth halved, 64 -> 32 bytes/ns. Still an
# explicit FREE PARAMETER (A-L0-BW) — not standard-derived, not measured.
topology_id: ring8_slow_v1
topology_class: unidirectional_ring
ranks: 8
link:
  bytes_per_ns: 32
  hop_latency_ns: 200
notes: >
  One send and one receive direction per neighbor, modeled independently.
  No congestion, no credits, no packetization — L0 transport model only.
```

In the manifest copy, change four things — the `experiment_id`, the
`infra_graph.path`, the `validity_domain.topology` line, and (honest
scratch-run discipline) the `claim_id`:

```yaml
# W1 Dense TP Decode smoke experiment on a user-defined slow ring: same
# workload and model as w1_decode_smoke.yaml, only the topology reference
# changed (bandwidth 64 -> 32 B/ns). Evidence level E0 only: identities and
# determinism, no empirical claim.
experiment_id: EXP-VS-W1-SMOKE-RING8-SLOW-001
research_question: RQ2
claim_id: C-MINE-001
baseline_id: null
workload_ir:
  path: experiments/workloads/w1_dense_tp_decode_small.yaml
infra_graph:
  path: experiments/topologies/ring8_slow_v1.yaml
standard_profile:
  path: experiments/vertical_slice/profiles/standard_profile_none.yaml
implementation_profile:
  path: experiments/vertical_slice/profiles/implementation_profile_l0.yaml
assumptions:
  path: experiments/vertical_slice/assumptions_l0.yaml
backends:
- analytical_l0
seed: 20261026
repetitions: 1
metrics: []
observables:
- O-CONSERVATION
- O-CCT
counterexample_policy: minimize_then_refine
validity_domain:
  topology: ring8_slow_v1 (transport-agnostic, free parameters; bandwidth halved)
  workload: w1_dense_tp_decode smoke configuration
  implementation: analytical L0 free-parameter model, no standard semantics
evidence_level_requested: E0
```

Run it:

```bash
make run EXP=experiments/vertical_slice/w1_decode_smoke_ring8_slow.yaml
```

```text
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_smoke_ring8_slow.yaml
{
  "run_id": "6f17619566e4e7635b3483e5c3a0f2dfa9ff0e32c725d3a39849455e3a018137",
  "run_dir": "/Users/li/simsun/essun/results/6f17619566e4e7635b3483e5c3a0f2dfa9ff0e32c725d3a39849455e3a018137"
}
```

A different `run_id` than the baseline: the input bytes changed, so the
content address changed.

## Stage 4 — see the expected effect (5 minutes)

```bash
python3 -m json.tool results/6f17619566e4e7635b3483e5c3a0f2dfa9ff0e32c725d3a39849455e3a018137/observations.json
```

The interesting parts (`per_op` elided):

```json
{
  "model": {
    "hop_latency_ns_exact": "200",
    "link_bytes_per_ns_exact": "32",
    "ranks": 8,
    "topology_id": "ring8_slow_v1",
    "transport_model": "bandwidth_latency_ring"
  },
  "observables": {
    "O-CCT": {
      "completion_time_ns_max": 3696.0,
      "completion_time_ns_mean": 3696.0,
      "completion_time_ns_mean_exact": "3696",
      "kind": "analytical",
      "ops": 6
    },
    "O-CONSERVATION": {
      "kind": "exact",
      "ops_checked": 6,
      "total_wire_bytes_exact": "1376256",
      "violations": 0
    }
  }
}
```

Check both effects against the L0 ring closed form — the whole point of
an analytical backend is that nothing here is opaque:

```text
t(M) = (2·(r−1)/r · M) / B  +  2·(r−1) · L
       └── transfer term ──┘    └─ latency ─┘

baseline (B=64): 28672 B / 64 B/ns + 2800 ns =  448 + 2800 = 3248 ns
yours    (B=32): 28672 B / 32 B/ns + 2800 ns =  896 + 2800 = 3696 ns
```

(28672 = 2·7/8 · 16384 bytes of per-rank ring traffic; 2800 = 2·7·200 ns.)

| observable | baseline (B=64) | yours (B=32) | closed form predicts |
|---|---|---|---|
| `O-CCT` completion time | 3248 ns | 3696 ns | +448 ns (exactly the extra transfer term) |
| `O-CONSERVATION` wire bytes | 1376256 | 1376256 | unchanged — bandwidth changes time, not traffic |

**Determinism:** run the Stage 3 `make run` again; you get the same
`run_id` (`6f176195…`) and byte-identical records — a rerun is a
replay. Change any input byte (say `hop_latency_ns: 201`) and the id
changes — a run record can never silently refer to inputs it did not
have.

If something is off, the gates fail loudly **before** any model
executes; a bypass is treated as a bug, never a feature. The one you
are most likely to meet: a topology whose `ranks` disagrees with the
workload's `tp_size` exits with
`ExecutionError: workload tp_size 8 != topology ranks 9`. More gates in
"Beyond 30 minutes".

## Stage 5 — submit a small contribution (10 minutes)

The smallest contribution the project actually wants: **a workload you
authored plus its manifest, hand-checked and schema-validated.** Two
new files, nothing copied.

**1. Author the workload** — create
`experiments/workloads/w1_dense_tp_decode_first.yaml`:

```yaml
# My first W1 Dense TP Decode workload: one layer, one decode step, one
# 1 MiB AllReduce. All sizes are integer byte counts; deterministic by
# construction.
workload: w1_dense_tp_decode
model_name: my-first-workload
tp_size: 8          # must equal the topology's ranks
layers: 1           # transformer layers per decode step
steps: 1            # decode steps
allreduce_bytes: 1048576   # 1 MiB per-op payload; must be divisible by tp_size
```

The three rules that matter: `tp_size` must equal the topology's
`ranks`; the payload must be divisible by `tp_size` (L0 equal-chunk
arithmetic, `A-L0-DIV`); all sizes are integer byte counts.

**2. Author the manifest** — create
`experiments/vertical_slice/first_experiment.yaml`:

```yaml
# My first experiment manifest: run the workload above on the committed
# 8-rank ring topology with the analytical L0 ring model. Evidence level
# E0 only: identities and determinism, no empirical claim.
experiment_id: EXP-MY-FIRST-001
research_question: RQ2
claim_id: C-MINE-002
baseline_id: null
workload_ir:
  path: experiments/workloads/w1_dense_tp_decode_first.yaml
infra_graph:
  path: experiments/topologies/ring8_free_params.yaml
standard_profile:
  path: experiments/vertical_slice/profiles/standard_profile_none.yaml
implementation_profile:
  path: experiments/vertical_slice/profiles/implementation_profile_l0.yaml
assumptions:
  path: experiments/vertical_slice/assumptions_l0.yaml
backends:
- analytical_l0
seed: 20261026
repetitions: 1
metrics: []
observables:
- O-CONSERVATION
- O-CCT
counterexample_policy: minimize_then_refine
validity_domain:
  topology: ring8_free_v1 (transport-agnostic, free parameters)
  workload: my-first-workload (1 layer, 1 step, 1 MiB AllReduce)
  implementation: analytical L0 free-parameter model, no standard semantics
evidence_level_requested: E0
```

Use **your own** `claim_id` for scratch runs — never attach your runs
to the repo's claim ids (`C2`, …); the claim link lands in the local,
git-ignored `results/claims_index.jsonl`.

**3. Run it and hand-check it** — a contribution is not done until it
runs and the numbers check:

```bash
make run EXP=experiments/vertical_slice/first_experiment.yaml
```

```text
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/first_experiment.yaml
{
  "run_id": "e0d77db3dbddd3adb5d64b36600a6fb3d40e19c4884235d66369c691903aa196",
  "run_dir": "/Users/li/simsun/essun/results/e0d77db3dbddd3adb5d64b36600a6fb3d40e19c4884235d66369c691903aa196"
}
```

```bash
python3 -m json.tool results/e0d77db3dbddd3adb5d64b36600a6fb3d40e19c4884235d66369c691903aa196/observations.json
```

```json
{
  "observables": {
    "O-CCT": {
      "completion_time_ns_max": 31472.0,
      "completion_time_ns_mean": 31472.0,
      "completion_time_ns_mean_exact": "31472",
      "kind": "analytical",
      "ops": 1
    },
    "O-CONSERVATION": {
      "kind": "exact",
      "ops_checked": 1,
      "total_wire_bytes_exact": "14680064",
      "violations": 0
    }
  },
  "per_op": [
    {
      "completion_time_ns": 31472.0,
      "completion_time_ns_exact": "31472",
      "op_id": "s000000-l000000-allreduce",
      "payload_bytes": 1048576,
      "per_rank_wire_bytes_exact": "1835008",
      "total_wire_bytes_exact": "14680064"
    }
  ]
}
```

Hand-check with the same closed form as Stage 4 (B = 64, L = 200,
r = 8, M = 1048576):

```text
O-CCT :  2·7/8 · 1048576 = 1835008 B;  1835008/64 + 2800 = 28672 + 2800 = 31472 ns  ✓
O-CONSERVATION:  2·(r−1)·M = 14 · 1048576 = 14680064 wire bytes                     ✓
```

**4. Validate** — anything you drop in `experiments/topologies/*.yaml`
or `experiments/workloads/*.yaml` is automatically schema-validated:

```bash
make validate-schemas
```

```text
........................................................................ [ 80%]
....................................                                     [100%]
181 passed in 0.81s
```

(181 = 179 committed cases + your two new files. `make test` runs the
full suite — schema, golden, negative, determinism, observables,
evidence, backends — and takes longer; the contribution bar is
`validate-schemas` green plus your hand-check.)

**5. Branch, commit, open the PR**:

```bash
git checkout -b workload/my-first-experiment
git add experiments/workloads/w1_dense_tp_decode_first.yaml \
        experiments/vertical_slice/first_experiment.yaml
git commit -m "workloads: add my-first-workload (1 MiB single-AllReduce W1 decode) + manifest"
```

```text
[workload/my-first-experiment abaa095] workloads: add my-first-workload (1 MiB single-AllReduce W1 decode) + manifest
 2 files changed, 40 insertions(+)
 create mode 100644 experiments/vertical_slice/first_experiment.yaml
 create mode 100644 experiments/workloads/w1_dense_tp_decode_first.yaml
```

Then push the branch to your fork and open the pull request (these two
lines depend on your fork and `gh` setup, so they are yours to run —
they are the only commands in this guide not captured above):

```bash
git push -u your-fork workload/my-first-experiment
gh pr create --fill
```

A good first PR states the workload's shape (sizes, steps), the run id,
and the hand-check line — exactly the Stage 5 evidence. A bad first PR
tunes a model number to make a curve look different; free parameters
change only with a registry rationale, never inside a contribution.

Your scratch files from Stages 3–5 simply show up as untracked in
`git status` — keep them, commit them (Stage 5), or delete them;
nothing in `results/` is committed either way.

## Beyond 30 minutes

**The other analytical models.** The manifest's `backends:` entry and
the topology's `topology_class` must be a declared pairing — copy the
committed fabric file that matches the model you want and adjust its
free parameters exactly as in Stage 3:

| `backends:` id | requires `topology_class` | committed 8-rank fabric |
|---|---|---|
| `analytical_l0` | `unidirectional_ring` | `experiments/topologies/ring8_free_params.yaml` |
| `analytical_l0_crossbar` | `fully_connected_crossbar` | `experiments/topologies/crossbar8_free_params.yaml` |
| `analytical_l0_torus2d` | `torus2d_ring_x_ring` (needs `grid:`) | `experiments/topologies/torus2d_8_free_params.yaml` |
| `analytical_l0_recursive_doubling` | `fully_connected_exchange` | `experiments/topologies/rdoubling8_free_params.yaml` |
| `analytical_l0_phase_collectives` | `unidirectional_ring` or `fully_connected_exchange` | `experiments/topologies/ring8_free_params.yaml` or `experiments/topologies/rdoubling8_free_params.yaml` |

The first four run W1 (`allreduce`); `analytical_l0_phase_collectives`
implements ReduceScatter + AllGather phases, which is the W2 shape —
the committed worked example is
`experiments/vertical_slice/w2_prefill_smoke.yaml`. Crossbar and
recursive-doubling fabrics carry `nic.injection_bytes_per_ns` and
`link.pair_latency_ns` instead of the ring's `link.bytes_per_ns` /
`hop_latency_ns` — same free-parameter discipline, different closed
forms (golden identities in `tests/golden/`). The Docker-pinned
discrete-event backend `astra_sim_analytical` is also reachable via
`make run` (`experiments/vertical_slice/w1_decode_smoke_astra.yaml`)
and needs the pinned image from the README "Requirements" section.

**Manifest field reference** (schema:
`schemas/experiment.schema.json`). Required fields: `experiment_id`
(yours), `research_question` (free-form; committed manifests use
RQ1–RQ4), `claim_id` (yours for scratch runs), `baseline_id` (`null`
when no baseline), the five input `path`s (repo-relative),
`backends` (exactly one id per run — gate), `seed` (integer, recorded),
`observables` (at least one, each supported by the backend — gate;
`analytical_l0` supports `O-CONSERVATION`, `O-CCT`,
`O-TRAFFIC-IMBALANCE`), `validity_domain` (three required strings:
topology / workload / implementation — write what actually ran, not
what you aspire to), `evidence_level_requested` (`E0`–`E4`; these
examples are `E0`). Optional: `repetitions` (default 1), `metrics`
(may be `[]`), `counterexample_policy` (`minimize_then_refine` = when
backends disagree, minimize and classify before any parameter is
touched).

**Workload generator fields**
(`schemas/workload_ir.schema.json`, generator-params dialect):

| field | W1 decode | W2 prefill | meaning |
|---|---|---|---|
| `workload` | `w1_dense_tp_decode` | `w2_dense_tp_prefill` | selects the generator |
| `model_name` | any name | any name | label carried into records |
| `tp_size` | required | required | tensor-parallel group size = ranks |
| `layers` | required | required | transformer layers per step |
| `steps` | required | — | decode steps (one AllReduce per layer per step) |
| `allreduce_bytes` | required | — | per-op payload M, integer bytes |
| `chunks_per_layer` | — | required | activation chunks per layer |
| `chunk_bytes` | — | required | per-chunk payload, integer bytes |

**More gates you will meet.** Non-integral chunking: L0 models require
the rank count to divide every payload (`A-L0-DIV`); a 7-rank ring with
a 16384-byte op fails with
`ValueError: analytical_l0: op s000000-l000000-allreduce: payload 16384
bytes is not divisible by 7; …`. Undeclared (model, topology_class)
pairings, unknown backends, workloads issuing collectives the model
does not declare, and unsupported observables all fail the same way:
named gap, non-zero exit.

**Sweeps and the gate chain.**
`make sweep EXP=experiments/sweeps/l0_allreduce_design_space_v1.yaml`
runs many runs over a parameter grid into one comparison table under
`results/sweeps/` (byte-identical replay; executed alongside this
guide, sweep id `12700ede…`). `make demo` chains the whole public
gate (schema + tests + golden runs + sweep + figure + paper-check),
with a no-Docker mode. `docs/atlas/README.md` holds the committed
cross-model comparison pages. README "Current state" is what is honest
about these numbers: E0 identities; the UEC 1.1 profile binds
documentation and L1 contracts today, not L0 outputs; nothing is
calibrated against hardware.
