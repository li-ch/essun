# essun

**Executable Specifications for Scale-Up Networking.**

essun is an open-source simulator for the GPU-to-GPU fabrics that carry LLM
inference traffic — UEC, UALink, UnifiedBus, NVLink-class systems. We built
it because fabric decisions (which standard to adopt, which topology to
wire, which collective algorithm to run) are made today on vendor slides
and one-off simulators, and those comparisons do not reproduce. In essun,
one experiment definition runs the same workload across multiple fabrics
and multiple simulation fidelities, and every number it produces traces to
an immutable run record that anyone can re-derive from a clean clone.

## What you can do today

- **Run a cross-fabric comparison from one file.** A single YAML manifest
  selects the workload, the fabric profile, and the simulator; the output
  is a comparison table with exact-arithmetic deltas.
- **Reproduce everything.** `make demo` chains the full story from a
  fresh clone — install, tests, reference runs, comparison table, figure —
  and reproduces the stored reference runs byte-for-byte.
- **See what a standard actually says.** The UEC 1.1 profile pins 80
  verbatim, hash-verified quotes from the specification and organizes 445
  requirements behind an explicit label: what the spec requires, where it
  leaves implementers free, and what essun does not model.
- **Trust the honesty machinery.** Every result carries an evidence label;
  one axis today is CALIBRATED within a stated domain, everything else stays at or below `IMPLEMENTED_UNVERIFIED` (we say which, plainly);
  `make paper-check` mechanically rejects overclaiming vocabulary in the
  documentation.

## The 60-second demo

```bash
make bootstrap
make demo
```

Requirements: Python 3.10+, and Docker for the discrete-event legs (without
Docker the demo runs the analytical legs and says exactly what it skipped).

## Quality

- **91% line coverage** (`make coverage`; every module in `src/essun`).
- **Property-tested identities:** billions of seeded exact-arithmetic
  checks across the analytical models, with zero model-identity findings.
- **CI on Python 3.10–3.13**, green on every commit.


## What essun does not do

- One calibrated axis, honestly scoped: the crossbar model's large-message
  bandwidth axis is CALIBRATED within a stated domain (owner adjudication
  `docs/calibration/ADJUDICATION_v0.2.md`); every other axis remains a
  model output, not a prediction of any physical system, and the labels
  say so.
- The UEC profile carries one spec-derived constant (a 256-byte credit
  unit, UEC 1.1 §3.6); all performance parameters remain free parameters
  that you set.
- MoE and prefill/decode-disaggregation workloads are implemented at the
  workload layer but are rejected loudly by today's backends — executing
  them needs fabric models we have not built.
- UALink and CXL profiles are license-gated and absent; the UnifiedBus
  profile is derived from public papers and is labeled non-normative.

Detailed component status lives in [docs/status.md](docs/status.md).

## Learn more

- [Website and white paper](https://li-ch.github.io/essun/)
- [Quickstart and usage guide](docs/usage.md)
- [Vision and roadmap](https://li-ch.github.io/essun/roadmap.html)
- [How essun compares to related simulators](https://li-ch.github.io/essun/comparison.html)

## Contributing and license

We review contributions against the same discipline the code lives by:
tests must pin the change, numeric claims need a run id, and commit
messages carry an evidence label. See [CONTRIBUTING.md](CONTRIBUTING.md).
Code is MIT; documentation, figures, and the site are CC-BY-4.0.
