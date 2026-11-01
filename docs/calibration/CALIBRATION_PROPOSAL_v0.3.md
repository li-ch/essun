# CALIBRATION_PROPOSAL v0.3 — section 3.3 revision (small-message axis)

Status: **PENDING OWNER ADJUDICATION.** This document proposes; the
owner disposes. It revises ONE section of the v0.2 proposal
(`CALIBRATION_PROPOSAL_v0.2.md` §3.3, the latency-bound small-message
axis) and changes nothing else there: every other axis candidate, the
tolerance policy, and the five-axis omission list of v0.2 stand as
written, with one addition to axis 4 noted in §5 below. Nothing in any
registry, disposition, claim, README row, status line, tolerance, or
evidence label changes by virtue of this file. Every number below is
cited to its immutable record.

Date: 2026-10-31/11-01. v0.2 said any revision is v0.3 and is not edited
in place; this is that revision, scoped to the one axis the 2026-11-01
H1 program was dispatched to earn or re-falsify.

## 0. What happened since v0.2 §3.3

v0.2 §3.3 said: *"any future software/endpoint-latency term must place
the small-message floor in that decade. That statement, not a promotion,
is this axis's deliverable."* The term now exists; the ladder for the
axis was rerun end to end against the SAME immutable split. The result
is **a sharpened falsification, not a CALIBRATED candidate** — the
structural omission is fixed, and the fix is what makes the remaining
gaps exactly statable.

| Artifact | Record id (sha256 over canonical_json + "\n") | Committed copy |
|---|---|---|
| S1 split (unchanged, immutable) | `3862e227327afe98562e17a32b9498278552c3bf55fe5b6715d7a4e0e9d94f20` | `split/anchor_split_v1.json` |
| S4e fit (endpoint axis) | `d91aaf874b983a684a230babe59a38c7ee6c2b5bc88cc39340ddfe481145c8c8` | `s4e/fit_record_v1.json` |
| S6e holdout evaluation | `60cd4059dc6e9200159772fa2be6eabe3216569a287e2e1aec36d8696c7869e6` | `s6e/holdout_record_v1.json` |

## 1. The model change (fix the model, not the label)

An explicit **endpoint latency term E** — a free software/endpoint
latency charged ONCE per collective op — is now part of the L0 family
identities (ring, crossbar, recursive doubling, phase collectives, L0.5;
the torus identity is excluded by registration, see §6):

    ring       t = 2(r-1)/r·M/B + 2(r-1)·L + E
    crossbar   t = 2(r-1)/r·M/B + 2L + E
    doubling   t = 2(r-1)/r·M/B + 2·log2(r)·L + E

Registered as **A-L0E-LAT** (value 0, range [0, 9000] ns — the upper
endpoint is GF-10's measured app-level P2P figure, the only MEASURED
software-inclusive anchor the fit set stages; no holdout number enters
the range) and **A-L0E-CHG** (charging: once per issued collective op;
per-phase/per-transfer charging are declared different identities) in a
new per-model registry `experiments/vertical_slice/assumptions_l0e.yaml`
(the house per-model-file rule — the shared `assumptions_l0.yaml` is
byte-unchanged, so every already-stored run id reproduces).

Identity/golden battery rerun and extended
(`tests/golden/test_l0_endpoint_golden.py`): hand-derived literals for
the extended family; the amended phase-composition law (RS + AG =
AllReduce + E when E is declared — two issued calls carry two endpoint
terms); the L0.5 convergence identity unchanged (E cancels); the chain
laws (ring − crossbar = 12L, etc.) hold at every shared E — the term is
identity-invariant structure; and the **byte-identity fence**: a
topology that declares no `endpoint:` block produces byte-identical
payloads to the pre-change backends (pinned by the full suite, 2537
tests green, including every S2..S6 v1 guard re-execution).

## 2. The fit (S4e, degenerate placements under mappings declared in advance)

- **GF-10** (measured app-level P2P ~9 µs, V100-era, the only measured
  software-inclusive fit anchor): declared primary mapping `t_p2p =
  L + E` at the UNCHANGED registry L = 200 → **E_fit = 8800 ns** — IN
  range at 44/45 of the upper endpoint the anchor itself defines, where
  the v1 L-reading sat OUT of range at 4.5×. The software-inclusive
  quantity class now fits as itself. Whole-figure alternative E = 9000
  executed and flagged, never selected (they differ by the registry L,
  2.2%).
- **CAL-A10** (assumption-class end-to-end 0.8 µs): declared end-to-end
  reading `L + E` → E = 600 ns — assumption-class, no falsification
  power, context never target; the v1 whole-800-on-L reading stays
  immutable in the v1 record (an explicitly carried interpretation
  pair).
- **CAL-A8 / CAL-A9** (wire-class): E = 0 by their own quantity class;
  their v1 L-axis placements are deliberately NOT re-read onto E
  (re-reading them toward the measured decade would be tuning — the
  fence).
- The A-L0E-LAT registry value stays 0; the wire-latency registry
  values stay 200/[10, 2000]; nothing tuned. Run-backed: 42-row sweep +
  4 dimensioned runs, every row equal to its closed form by exact
  Fraction equality (record `d91aaf87…`).

## 3. The evaluation (S6e, evaluation-only on the same split)

Executed against the holdout small-message rows at placements carried
bit-exact (runs + sweeps, all held_out: true, v2 dimensions; record
`60cd4059…`):

- **GF-11 (GB200-class, confidence H):** at E = 600 the model lands
  0.71× of the 2-GPU SoL point (1002 vs 1404 ns) and 0.42–0.76× of the
  r=4 near-optimal leg; at E = 8800 it overshoots the SoL point 6.56×
  but approximately reproduces the stock-NCCL leg (0.84–0.91× of 11000
  ns) — a generation-coincidence of software heaviness, not a
  validation (the same placement overshoots the near-optimal leg 4× on
  the same fabric).
- **GF-01 (MI300X/RCCL, r=8):** the closest fit-side landing is E = 8800
  on the ring at 16 KiB (12048 vs 13540 ns = 0.890, −11.0%) — a
  cross-stack magnitude coincidence, NOT a validation; the whole eager
  band demands an implied E of 9178–16339 ns, ENTIRELY above the
  declared range upper 9000.
- **GF-03 (B300-class, confidence M):** the D2D points imply E =
  1200/1400 ns — in range, unoccupied.

## 4. The deliverable: the sharpened falsification

The three-part statement the anchors leave (record `60cd4059…`,
`cross_anchor_observations`), superseding v0.2 §3.3's single-sentence
gap statement:

1. **UNOCCUPIED WINDOW (evidential gap).** The model class now REACHES
   the measured current-generation floor window: every near-optimal-leg
   implied E (GF-11: 1002–1967 ns across chains and rank counts; GF-03:
   1200/1400 ns) sits INSIDE the declared range — the v1 structural
   impossibility ("no wire-class placement reaches the floor decade")
   is gone. But the window is UNOCCUPIED: the fit-side placements span
   {0, 600, 8800} and the window lies between 600 and 8800 with no
   fit-side anchor inside it. **What the anchors demand that the model
   still lacks: a current-generation software/endpoint-latency
   measurement IN THE FIT SET** — the only measured software-inclusive
   fit anchor (GF-10) is V100-era DGX-1 app-level P2P; the
   current-generation decompositions live in HOLDOUT anchors, which the
   immutable split rightly forbids as fit inputs. This gap cannot be
   closed by model work, only by a new fit-side anchor (a future
   split's business, never split_v1's).
2. **RANGE-TOP CHALLENGE (the anchors disagree with each other).**
   GF-01's RCCL eager collective floor demands implied E 9178–16339 ns —
   ABOVE the range upper that GF-10's own figure defines — and GF-11's
   stock-NCCL leg demands 9797–10597 ns (also above). Across the corpus
   the software-inclusive magnitude spans ~10× (near-optimal ~1.0–2.0
   µs, V100 P2P ~9 µs, stock-NCCL ~10.5 µs, RCCL-eager ~13.5–16.7 µs).
   **A single uniform E with one range cannot serve near-optimal,
   stock-NCCL and RCCL-eager stacks simultaneously: the anchors demand
   a software-stack/generation AXIS on the endpoint term** (the E-side
   sibling of the S3 software-version axis), which the model still
   lacks.
3. **SHAPE DEMANDS UNCHANGED (carried).** The lumped symmetric 2L + E
   cannot express GF-11's asymmetric decomposition (2×306 RTT + 792
   store); the affine-plus-floor response cannot express GF-01's
   non-monotone eager band or a flat-then-rising transition; uniform E
   cannot express per-pair heterogeneity — all carried from v0.2/S6 v1
   unchanged by this term.

## 5. What the owner is being asked to decide

1. **Accept the sharpened falsification as the axis's standing
   statement** (replacing v0.2 §3.3's "no software-latency term" gap
   statement; the axis's label stays whatever v0.2 adjudication leaves
   it at — this proposal promotes nothing).
2. **Adjudicate the model change itself**: the endpoint term E
   (A-L0E-LAT/A-L0E-CHG) as a registered free parameter of the L0
   family (torus excluded), with the byte-identity fence and the
   extended golden battery as its verification story.
3. **Adjudicate the recorded placements' standing**: E = 8800 / 600 / 0
   stay recorded diagnostics in `experiments/calibration/s4e/` (the
   A-L0E-LAT registry value stays 0), citable to record `d91aaf87…`.
4. **Note the two future-item classes the falsification names** (no
   action possible on this split): a current-generation
   software-latency anchor for a future fit set (any assignment needs
   new anchor staging + a new split record), and a software-stack axis
   on the endpoint term (a model question, CGFR's business, with the
   ~10× measured span as its input).
5. **v0.2 §4 axis 4 amendment** (additive only): axis 4's first
   sentence becomes "no software/endpoint latency term existed; the
   term now exists (A-L0E-*) with the E-axis falsification above as its
   standing bound" — the axis's other content is unchanged.

## 6. What this document does not do

It promotes no label; changes no registry value, disposition, claim, or
status line; adopts no tolerance; tunes nothing (every fit is a
degenerate placement under a mapping declared in advance); touches no
anchor material (GF-06 included); touches no holdout anchor as a fit
input (the S6e record is the sanctioned evaluation-only use); and does
not extend the endpoint term to the torus identity (its extension is a
separate registered step, owned by the concurrent torus-expressiveness
program). The S4/S6 v1 records stand immutable as the wire-axis
counterparts.
