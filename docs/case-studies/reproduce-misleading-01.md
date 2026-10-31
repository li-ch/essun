# Reproduction card — case study 01, the misleading twin comparison

You are an external engineer with a clean clone. This card reproduces
every leg of
[misleading-comparison-01.md](misleading-comparison-01.md): two engines
disagree by +118% on identical inputs, ordinary diffing reports only the
magnitude, and the diagnosis chain minimizes the case to 2 ranks /
2 bytes, decomposes the gap by single-knob ablations, and classifies the
components. One shared setup (section 0); the legs build the story in
order. Everything except the two engine-B (ASTRA) executions and the
optional full re-localization runs without Docker; those need the pinned
container image, which the runbook at
`backends/docker/astra-sim-runbook.md` builds. The timings in the budget
table at the end were measured on a cold clone.

## 0. Setup (once, ~2 min ceiling; machine time ~10 s with a warm pip cache)

```bash
git clone <this repository> essun && cd essun
make bootstrap          # python3 -m venv .venv; pip install -e ".[dev]"
```

## Part I — the misleading pair (~2 min hands-on)

Run both engines on the shared 72-rank, 2 GiB input. The two manifests
reference ONE topology file and ONE workload file (the same-workload
bar); engine A is in-process, engine B runs in the pinned container.

```bash
.venv/bin/python -m essun.orchestrator.runs \
  experiments/diagnosis/case_twin_l0_vs_astra/probes/r72-m2147483592/run-diag-l0-r72-m2147483592.yaml
.venv/bin/python -m essun.orchestrator.runs \
  experiments/diagnosis/case_twin_l0_vs_astra/probes/r72-m2147483592/run-diag-astra-r72-m2147483592.yaml
```

Expected: `run_id` `82b2296fc18604ad74566246a4bff0249b6055fbd96ac9782cbb3502dc6e76c3`
(engine A, no Docker) and `run_id`
`0c6b8ec4868a8ed440e7883b7a7b2b9498b03bfecd44c7d133891ae3efa8e03f`
(engine B, Docker) — both byte-for-byte, because run ids are
content-addressed over the inputs.

Read the two numbers the way the case study does:

```bash
.venv/bin/python - <<'EOF'
import json, glob, os
for d in sorted(glob.glob("results/*/"), key=os.path.getmtime)[-2:]:
    o = json.load(open(d + "/observations.json"))["observables"]["O-CCT"]
    print(os.path.basename(d.rstrip("/"))[:8], o.get("completion_time_ns_mean_exact")
          or o.get("completion_time_ns"), "ns")
EOF
```

Expected: engine A `2129415031/414` ns (≈ 5,143,514.6) and engine B
`11216448` ns. Sanity-check engine A by hand (no code): per-rank traffic
`2·71/72 · 2147483592` B over B = 828 B/ns plus `2·71·200` ns latency —
the wire-only identity `t = 2(r−1)/r·M/B + 2(r−1)L`. Engine B divided by
engine A is exactly `4643609472/2129415031` ≈ 2.1807: **+118.07%**, the
misleading pair.

## Part II — what ordinary diffing says (~2 min)

Run the differential-comparison engine on the stored pair, under both
obligations:

```bash
.venv/bin/python - <<'EOF'
from essun.evidence.store import EvidenceStore
from essun.validation.diff_engine import DiffEngine, Obligation
L0 = "82b2296fc18604ad74566246a4bff0249b6055fbd96ac9782cbb3502dc6e76c3"
AS = "0c6b8ec4868a8ed440e7883b7a7b2b9498b03bfecd44c7d133891ae3efa8e03f"
e = DiffEngine(EvidenceStore("results"))
for obl in (Obligation(mode="exact", quantity="cct_per_op_ns", spec_id="O-CCT"),
            Obligation(mode="exact", quantity="per_rank_wire_bytes_per_op",
                       spec_id="O-CONSERVATION")):
    v = e.compare(L0, AS, obl)
    print(v["diff_id"][:16], v["verdict"]["status"], "|", v["verdict"]["detail"][:70])
EOF
```

Expected: `297adbb36aa9242101…` `diverged` — one divergence at
`{'op': 0}`: `2129415031/414` vs `11216448` ns (the engine's
`first_divergence` field); then
`bcc3797f23f385b1…` `not_comparable` — engine B declares
O-CONSERVATION unsupported, so the wire-bytes axis is a declared
capability gap, not a numeric difference. Both diff records are
content-addressed and land in `results/difference_reports/`; this is all
a diff can say, and the case study is about what it cannot.

## Part III — the minimal reproducer (~2 min)

The minimizer shrank the case to the floor of its declared ladder:
2 ranks, 2 bytes (36x fewer ranks, 1,073,741,796x fewer bytes; 34 logged
probes, every one reproducing the disagreement —
`minimization_v1.json` holds the full log with run ids). Re-run both
engines at that floor:

```bash
.venv/bin/python -m essun.orchestrator.runs \
  experiments/diagnosis/case_twin_l0_vs_astra/probes/r2-m2/run-diag-l0-r2-m2.yaml
.venv/bin/python -m essun.orchestrator.runs \
  experiments/diagnosis/case_twin_l0_vs_astra/probes/r2-m2/run-diag-astra-r2-m2.yaml
```

Expected: `run_id` `9162fade0942094b80a05fca3df0e35afc07be1801ae98cd6696bdfd2dc68f09`
(engine A) and `run_id`
`2ce2995beb32db88fb3e813893514934414b071928c2a2e3fb385fb59250bbbf`
(engine B). Inspect as in Part I: engine A `165601/414` ns
(≈ 400.0024), engine B `860` ns — the disagreement is still **+115.0%**
at two bytes, which is what makes it structural rather than an
accumulating error.

## Part IV — the decomposition, re-derived from committed stdout (~3 min)

The ablations ran the pinned container directly with one knob patched
per run; the raw stdout of every leg is committed under
`experiments/diagnosis/case_twin_l0_vs_astra/localization/r2-m2/`
(`a0`…`a4`; `a3` is the abort). Re-derive every decomposition number in
exact rationals, Docker-free, from those committed files:

```bash
.venv/bin/python - <<'EOF'
import re
from fractions import Fraction as F
base = "experiments/diagnosis/case_twin_l0_vs_astra/localization/r2-m2/"
def wall(name):
    t = open(base + name + ".stdout").read()
    m = re.search(r"finished, (\d+) cycles", t)
    return F(m.group(1)) if m else None
t_l0 = F(165601, 414)          # engine A at the minimal case (Part III)
a0, a1, a2, a4 = wall("a0_pinned_knobs"), wall("a1_local_mem_bw_relaxed"), \
                 wall("a2_chunks_relaxed"), wall("a4_all_feasible_relaxed")
print("twin delta:", a0 - t_l0, "ns =", float(a0 - t_l0))
print("chunk knob term (a0-a2):", a0 - a2, "| share:", (a0 - a2) / (a0 - t_l0))
print("memory knob term (a0-a1):", a0 - a1, "(inert)")
print("residual after feasible relaxations (a4-t_l0):", a4 - t_l0,
      "=", float(a4 - t_l0), "|", float((a4 - t_l0) / t_l0 * 100), "% of engine A")
print("a3 (endpoint zero):", "ABORTED — see a3_endpoint_delay_zero.stdout")
EOF
```

Expected, exactly: twin delta `190439/414` ns (≈ 460.0); chunk term
`430` with share `178020/190439` (93.4%); memory term `0`; residual
`12419/414` ns (≈ 30.0, 7.5% of engine A's value). Open
`a3_endpoint_delay_zero.stdout` to see the pinned binary's own abort
(`EventQueue.cpp:33` assertion, `ASTRA_EXIT=134`) — the endpoint term
cannot be zeroed, which is why it stays `unresolved`.

## Part V — the classification, through the mechanical classifier (~2 min)

The labels in the case record come from the taxonomy's deterministic
rules (`src/essun/diagnosis/classify.py`; every rule unit-tested in
`tests/diagnosis/test_units.py`). Run three of them on this case's
exact fact set:

```bash
.venv/bin/python - <<'EOF'
from essun.diagnosis.classify import (
    Attribution, EngineFacts, classify_component,
    DECLARED_DIFFERENT_QUANTITY, DECLARED_IDENTITY, NO_MATCH)
A = EngineFacts(engine_id="analytical_l0", observable_definition_id="wire-only")
B = EngineFacts(engine_id="astra_sim_analytical")
# chunk-serialization bundling: declared different quantity, exactly attributed
print(classify_component(
    Attribution("astra_sim_analytical", "chunk_serialized_wall",
                DECLARED_DIFFERENT_QUANTITY, attributed_delta_exact="430"),
    B, A, component="chunk bundling").label)
# same declaration but a nonzero residual remains -> stays unresolved
print(classify_component(
    Attribution("astra_sim_analytical", "chunk_serialized_wall",
                DECLARED_DIFFERENT_QUANTITY, attributed_delta_exact="430"),
    B, A, component="residual", unattributed_residual_exact="12419/414").label)
# wire-conservation axis: engine B declares the observable unsupported
gap = EngineFacts(engine_id="astra_sim_analytical", observable_declared_unsupported=True)
print(classify_component(
    Attribution("astra_sim_analytical", "no_byte_accounting", DECLARED_IDENTITY),
    gap, A, component="O-CONSERVATION axis").label)
# the endpoint term matches no exact variant (unmeasurable) -> unresolved
print(classify_component(
    Attribution("astra_sim_analytical", "endpoint", NO_MATCH),
    B, A, component="endpoint bundling").label)
EOF
```

Expected: `abstraction_difference`, `unresolved`, `missing_capability`,
`unresolved` — the recorded labels, each produced by a mechanical rule
rather than asserted by prose.

## Part VI — the guard test (~10 s, no Docker)

```bash
.venv/bin/python -m pytest -q tests/diagnosis/test_case_twin.py
```

Expected: 5 passed. The guard rebuilds `case_record_v1.json`
byte-identically from the committed blocks, re-derives the decomposition
in exact `Fraction`s, re-executes the minimal engine-A leg into a
scratch store to its declared run id, checks the initial pair equals the
earlier cross-engine record's twin numbers, and re-parses every
committed ablation stdout to the recorded walls.

## Part VII — full re-localization (optional, Docker, minutes)

One command re-executes the entire diagnosis chain end to end — all
minimization probes as real dual-engine run pairs plus the five
ablations:

```bash
.venv/bin/python experiments/diagnosis/case_twin_l0_vs_astra/run_case_study.py execute
git status --porcelain experiments/diagnosis/case_twin_l0_vs_astra/
```

Expected: it prints the minimal case (`ranks: 2, payload_bytes: 2`),
then the five ablation walls (`a0` 860, `a1` 860, `a2` 430, `a3`
ABORTED, `a4` 430). `minimization_v1.json` and `ablations_v1.json`
regenerate byte-identically (deterministic JSON, content-addressed run
ids), so the porcelain listing should show only the raw `localization/
*.stdout` files, whose embedded wall-clock timestamps differ while
parsing to the same walls — which is exactly why the guard replays the
committed stdout instead of trusting regenerated text.

## Attack it (~3 min)

The record is supposed to be impossible to drift silently. Test it:

1. Edit any number in
   `experiments/diagnosis/case_twin_l0_vs_astra/case_record_v1.json`
   (say, the chunk term `430` -> `431`) and re-run Part VI: the
   byte-identity rebuild must fail. Revert.
2. Edit a wall inside a committed stdout (change `finished, 860 cycles`
   to `finished, 861 cycles` in `a0_pinned_knobs.stdout`) and re-run
   Part VI: the stdout-reparse leg must fail (the record's `a0` wall no
   longer matches the committed evidence). Revert.
3. Run Part IV with `t_l0` set to any other value and watch the
   decomposition stop closing (`a0 - t_l0` no longer equals the recorded
   twin delta): every number in the story is fixed by the committed
   artifacts, not chosen to fit.

If you believe a decomposition number is wrong (not merely rounded),
the project's protocol is: minimize the counterexample, do not tune
parameters until curves match — see `CONTRIBUTING.md`.

## Time budget (measured on a cold clone, 2026-10-31)

| Leg | Machine time | Notes |
| --- | --- | --- |
| clone + bootstrap (§0) | 0.3 s + 10 s | file:// clone; warm pip cache |
| Part I (both 72-rank runs + inspect) | ~2 s | run ids byte-identical; engine-B leg needs Docker |
| Part II (diff engine, both obligations) | ~0.3 s | `297adbb3…` diverged; `bcc3797f…` not_comparable |
| Part III (minimal reproducer, both legs) | ~1 s | run ids `9162fade…`, `2ce2995b…` |
| Part IV (decomposition from committed stdout) | ~0.3 s | exact rationals; no Docker |
| Part V (classifier, four calls) | ~0.2 s | recorded labels reproduced mechanically |
| Part VI (guard test) | ~0.2 s | 5 passed |
| Part VII (full re-localization, optional) | minutes | Docker; JSON records regenerate byte-identically |
| Attacks | ~1 s | both tamper legs fail the guard as designed |
