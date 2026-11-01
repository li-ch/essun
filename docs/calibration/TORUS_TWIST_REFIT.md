# Torus twist re-fit (stage TWIST) — a SHARPENED FALSIFICATION

Status: **PENDING OWNER ADJUDICATION.** This document proposes; the
owner disposes. It is the H2 deliverable under the 2026-11-01 morning
program: the torus axis's standing falsification (twist-blindness, S5
record `43fca722…`, proposal v0.2 §3.4) was ordered re-fit after the
model gained the missing expressiveness honestly — a twist/wiring
parameter in the topology model, registered free. The outcome is NOT a
calibration-candidate proposal: the axis stays a standing falsification,
now a sharper one. No registry label, claim, README row, status line, or
tolerance changes by virtue of this file.

Date: 2026-11-01. Record: `25f3d8880755c9315b7dd8fa2f27624f821e237aab5d1e66f848a9f13bd4f200`
(committed copy `experiments/calibration/twist/twist_record_v1.json`,
deterministic builder + byte-rebuild guard
`tests/calibration/test_twist_fit.py`). Same immutable split as every
ladder stage: S1 `3862e227…`; CAL-A5 stays the group-G4 falsifier
anchor; the holdout stays holdout (mechanically asserted: no holdout
anchor id appears anywhere in the record bytes).

## 1. What changed in the model (the honest expressiveness, added)

- **Input space:** a torus topology MAY declare
  `link.wrap_wiring_factor` = w — the effective rate of each dimension
  ring's single wrap (bisection-crossing) edge as a multiple of the
  uniform link rate B. Registered free parameter **A-L0T-WIRE**
  (`experiments/vertical_slice/assumptions_l0tw.yaml`), registry point 1
  (the regular torus — every existing topology), declared range
  **[1/2, 2]**. The range endpoints are STRUCTURAL bounds, declared, not
  measured and not standard-derived: a torus wrap cut carries each
  ring's forward flow on one dedicated wrap link per direction, so
  reallocating wrap capacity across the cut's two link directions can at
  most double an edge's rate (upper 2), and sharing an edge between two
  flows at worst halves it (lower 1/2).
- **Identity term:** the wiring enters through the pipeline min-link
  bound — a ring's steady-state rate is set by its slowest edge:
  `rate(w) = B·min(1, w)`; `t_ring(M,k) = 2(k−1)/k·M/(B·min(1,w)) +
  2(k−1)·L`. Wire counts, hop latency, and O-CONSERVATION never move.
  An UNDECLARED factor keeps the landed identity and every existing
  torus run payload byte-identical (the S5 rebuild guard passes
  unchanged); a DECLARED value — including 1 — is recorded in the model
  payload. Schema: `infragraph.schema.json` link block (contract 0.4.0
  additive extension). Goldens extended:
  `tests/golden/test_l0_torus2d_wiring_golden.py`.
- **Nothing was tuned:** the anchor's ratios 1.63/1.31 are NOT members
  of the swept grid (uniform quarter steps over the declared range,
  fixed before any deviation was computed); no anchor output selects any
  parameter value; the registry points stay 1 (A-L0T-WIRE) and 64
  (A-L0T-BW).

## 2. What the re-fit executed (record `25f3d888…`)

Two sweeps (11 configs x 6 ops each, payload 4096 = the anchor's
individual DMA size, L = the 200 ns registry point) at CAL-A5's faithful
projections: the uniform w grid {1/2, 3/4, 1, 5/4, 3/2, 7/4, 2} at the
anchor point B = 50 (reading 1), the committed stage-A5 anchor topology
as the immutable-S5 bridge row, and the {1/2, 1, 2} triangle at the
A-L0T-BW registry point B = 64 — sweeps `4328bb00…` (r=128, 8x16) and
`b6e40ab6…` (r=256, 8x32). Two v2-dimensioned runs
(`6197d3ad…`, `1e55ccfa…`, `calibration_target: [CAL-A5]`,
`held_out: false`) execute the twist-direction range ceiling w = 2 at
the anchor points. Every executed row equals the wiring-extended closed
form by exact Fraction string equality.

**The one-sided law, executed at both slices and both B points:** every
w >= 1 row equals the w = 1 row EXACTLY (9096.96 / 15502.08 ns), and
every w < 1 row equals the landed identity at per-link B·w exactly —
re-deriving the S5 record's own committed rows at the equivalent B
(the immutability bridge: this stage's w = 1/2 rows equal S5's B = 25
rows bit-for-bit; the declared w = 1 row, the undeclared bridge row, and
S5's anchor point are one number).

## 3. The sharpened falsification (what the anchor demands that the model still lacks)

1. **The structural leg is closed as INPUT blindness.** S5's
   falsification_1 said the input schema carries NO geometry field —
   twisted and regular tori of the same (r1, r2, B, L) mapped to
   IDENTICAL model inputs. That is fixed: the schema carries
   `wrap_wiring_factor`, and the executed sweeps distinguish the inputs.
2. **The OUTPUT is provably invariant in the twist's direction.** The
   model's twisted/regular AllReduce-CCT ratio is STILL exactly 1 — now
   for a proven reason instead of an absent field: a uniform-ring
   AllReduce has no bottleneck link, so its rate is set by its k−1
   non-wrap edges, and a wrap/bisection capacity gain (the twist's
   mechanism) cannot speed a balanced ring. The min-link bound is the
   identity's own structure, not a tuning choice.
3. **The demand lies below the axis's ENTIRE range.** Reading the
   anchor's ratios onto the model's own anchor-point CCT (the unchanged
   S5 metric discipline) demands twisted CCTs 5580.96 ns (r=128) /
   11833.65 ns (r=256) — below the B→∞ latency-chain floors 8800 /
   15200 ns (S5's leg, re-derived exactly), and below the wiring axis's
   whole envelope: the axis's minimum CCT is exactly the regular CCT
   (w >= 1 inert; w < 1 strictly slower). The wiring axis delivers
   **exactly 0%** of the demanded 63%/31% gain — strictly less than the
   unbounded B axis's 5.356%/6.411%, and in the wrong direction to
   matter. The only single-parameter routes to the demand remain the
   S5-flagged misattributions: L-absorption at 120.09/151.73 ns
   (charging bisection structure to hop latency) and the executed B
   displacement rows. All recorded, none selected.
4. **The residual gap is the COLLECTIVE, not a parameter.** CAL-A5's
   observable class is bisection-bound ALL-TO-ALL throughput ("twisted
   torus gives 1.63×/1.31× vs regular torus, individual DMAs of 4 KiB").
   No L0 identity in this repo executes all-to-all; the S5/S6 fence
   (never compare all-to-all throughput against AllReduce CCT) stands.
   Absorbing this anchor requires a NEW collective identity — all-to-all
   with a bisection/wiring term — which is recorded here as the standing
   requirement. Building one NOW in order to reach 1.63/1.31 would be
   tuning toward the anchor, and is out of bounds by the program fence.

**The one-sentence owner summary:** the twist axis's falsification moves
from "the input space has no geometry field" (S5, fixed honestly) to
"the geometry field exists, is registered free, and is provably
output-inert in the twist's direction on every collective identity the
L0 family executes; the measured 1.63×/1.31× demands an all-to-all /
bisection-bound identity the family does not carry" — a sharper bound
on every geometry-abstraction claim at L0 (plan §2.1 A-L0T-UNIF flag).

## 4. What the owner is being asked to decide

1. **Adjudicate this sharpened falsification** as the replacement
   wording for the torus-geometry axis in the next calibration-proposal
   revision (v0.2 §3.4's "no geometry field exists" is now historical;
   the axis still proposes NO label change — no-change stands, with the
   sharper reason).
2. **Accept the model addition's standing** (A-L0T-WIRE, registry point
   1, range [1/2, 2]): a landed free parameter of the torus identity
   whose gain-direction invariance is a guard-tested property — or
   direct its removal/rework.
3. **Note the standing requirement** for any future absorption of
   CAL-A5: an all-to-all identity with a bisection/wiring term (a new
   identity and its own falsifier duty, owner-gated, never built to
   order toward this anchor).
4. **Confirm nothing else moved:** registry values 64/200/1 unchanged;
   the S5 record, the split record, and every prior run id
   byte-identical (guard-tested); no holdout touched; no label promoted.

## 5. Reproduce

```bash
make sweep EXP=experiments/calibration/twist/sweep_twist_torus128_v1.yaml
make sweep EXP=experiments/calibration/twist/sweep_twist_torus256_v1.yaml
make run EXP=experiments/calibration/twist/run_twist_a5_slice128.yaml
make run EXP=experiments/calibration/twist/run_twist_a5_slice256.yaml
python experiments/calibration/twist/build_twist_record.py
V=.venv && "$V/bin/python" -m pytest tests/calibration/test_twist_fit.py \
  tests/golden/test_l0_torus2d_wiring_golden.py -q
```
