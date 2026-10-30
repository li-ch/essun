# Saturation-boundary artifact record — UEC TFC window vs UB free ring stand-in at the mid-freedom scale 256 (G4)

G4 (2026-10-30), the window-comparison family's SECOND rank corner: the
landed D4 cell (`uec_vs_ub_window_boundary_v1.yaml`, 1024 ranks, the
pod-scale corner) extended to the MID-FREEDOM scale 256 — a rank count
inside the shared `A-XDUO-TP` range [2, 1024] with NO anchor on either
profile side (the UB-paper side anchors 64 = UBP-P17 and 1024 = UBP-P18;
the UEC side anchors none), so both comparators are equally free
stand-ins. Machinery: `src/essun/orchestrator/opgrids.py`,
`boundaries.py`, `envelopes.py`, `envviz.py`. Manifest:
`experiments/envelopes/uec_vs_ub_window_boundary_tp256_v1.yaml`.

## Labels (read first)

- Status: **PROPOSED**.
- Evidence level: **E0** — exact arithmetic of analytical identities under
  declared freedom. No empirical claim is made.
- This artifact is a statement about the RANKING RELATION OF MODEL
  IDENTITIES at exact operating points, not about any measured system and
  not about chips: every value is a closed-form identity executed by its
  landed backend under FREE parameters (nothing standard-derived except the
  256-byte UEC credit unit, UEC11-FC-R05; nothing measured).

## The claim (decision-readable, one sentence)

Under the declared freedom of the UEC transport-flow-control credit window
(`A-TFC-W`, registered range 256..1048576 bytes) at the stated mid-freedom
operating point — 256 ranks, 1 MiB payload, shared B = 64 bytes/ns,
L = 200 ns, credit-return 200 ns — the UEC profile's admission-law ring
identity ties the UnifiedBus paper profile's free ring stand-in exactly at
every window >= 25600 bytes (100 credit units, exactly the
bandwidth-delay product B*(L+L_cr) = 64*400 — the SAME boundary as at
1024 ranks, because the threshold carries no rank term) and ranks strictly
worse at every window below it: the saturation boundary
(credit-provisioning threshold) sits at exactly W = 25600 bytes, the
windowed comparator is NEVER faster, and only the below-threshold penalty
magnitude changed with the rank count (it scales with the per-rank
traffic T = 2*(r-1)/r * M, here 2088960 bytes).

## Artifact identity (content-addressed)

| Field | Value |
| --- | --- |
| envelope_id (inputs: canonical manifest + code version) | `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730` |
| artifact content sha256 (`boundary.json` bytes) | `17cbc2abac31e6ac5bcd2101cdf3a13b5ed72f72ae934af0792297c74a3cb41d` |
| envelope-data content sha256 (`envelope-data.json` bytes) | `c0c2c3e937f2de3f5425425fea0ea23bf6e5eb612cb608a934b49ff2c37b09eb` |
| manifest sha256 | `eb29f7d568a93192665af42a2c55dcbd5a51f1a11ecabadef5031d5628f16982` |
| code version | 0.1.0 |

Reproduce (byte-identical; the runner refuses a byte drift on replay):

```bash
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_boundary_tp256_v1.yaml
# -> envelope_id 05b4afdf…, artifact sha256 17cbc2ab… (boundary.json.sha256 records it)
.venv/bin/python -m pytest -q tests/orchestrator tests/determinism/test_envelope_replay.py
```

## The operating point (every value range-validated against its registry)

| Parameter | Value (exact) | Registered range | Registry |
| --- | --- | --- | --- |
| ranks r | 256 | [2, 1024] (`A-XDUO-TP`) | `experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml` |
| payload M | 1048576 bytes | [1024, 16777216] (`A-XDUO-PAYLOAD`) | same |
| shared link bandwidth B | 64 bytes/ns | [1, 1024] (`A-XDUO-BW`) | same |
| shared per-hop latency L | 200 ns | [10, 2000] (`A-XDUO-LAT`) | same |
| credit-return latency L_cr | 200 ns | [0, 2000] (`A-TFC-CR`) | `experiments/vertical_slice/assumptions_tfc.yaml` |
| swept window W (grid) | 256, 6400, 12800, 25600, 51200, 102400, 256000, 1048576 | [256, 1048576] (`A-TFC-W`) | same |

Scale honesty: 256 is NOT an anchored scale on either side — the UB
side's anchored identities (rack crossbar at 64, pod-conditional flat
ring at 1024) sit elsewhere in the shared rank freedom; at 256 the UB
comparator is the profile's free transport-agnostic ring stand-in (same
stand-in class the UEC side declares), recorded in
`experiments/topologies/ring256_ub_flat_pod_free_params.yaml`.

## The comparators (named, one same-workload operating point)

| Model | Identity | Backend |
| --- | --- | --- |
| `uec_tfc_ring` | UEC free ring stand-in (`A-XDUO-IDUEC`) + the UEC profile's flagship executed semantic: TFC admission law UEC11-FC-R02, executed by the credit automaton binding `BIND-UEC11-FC-R02-AUTOMATON` with the ring identity `t = 2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L` as its declared steady-state abstraction | `analytical_l0_tfc` |
| `ub_flat_ring_mid` | UnifiedBus paper profile's free ring stand-in at the mid-freedom scale (NOT the anchored rack crossbar, NOT the pod-conditional flat ring); the public UB sources are silent on flow control (UBP-F04), so this side carries no window | `analytical_l0` |
| `uec_ring_free` | the same ring identity WITHOUT the window — the unwindowed control | `analytical_l0` |

Shared-parameter bar unchanged: B and L come from the one shared record
and are consumed by both flavors, so ranking differences may come ONLY
from the window term.

## The boundary (exact fractions, as the detector emitted them)

Per-rank wire traffic T = 2*(r-1)/r * M = 2088960 bytes (same identity
for all three comparators; a window gates rate, never bytes —
O-CONSERVATION identical everywhere, checked per point by the backends).
Unwindowed ring completion time 134640 ns = T/B + 2*(r-1)*L =
32640 + 102000, identical at every grid point.

Detector output for the flagship pair `uec_tfc_ring` vs
`ub_flat_ring_mid`, axis `A-TFC-W`:

- sign of d = t(tfc) - t(flat ring) flips +1 -> 0 on the grid bracket
  [12800, 25600]; **boundary W\* = 25600 exactly**, resolved by exact
  secant and VERIFIED by re-execution (d(25600) = 0; method
  `affine-x-verified`; grid differences d(12800) = 32640 ns > 0,
  d(25600) = 0).
- Regions (grid evidence, exact endpoints): TFC ranks WORSE on
  [256, 12800]; exact TIE on [25600, 1048576]. The windowed identity is
  never faster at ANY sampled window — a saturation boundary
  (penalty-then-tie), never a two-sided ranking crossing.
- Closed form: d(W) = T * ((L+L_cr)/W - 1/B) for W < B*(L+L_cr) and 0
  above — positive for every W < 25600, zero at and above; the flip point
  is exactly the bandwidth-delay product W\* = B*(L+L_cr) = 64*400 =
  25600 bytes = 100 UEC credit units. The threshold carries NO rank term,
  which is why this mid-freedom cell reproduces the 1024-rank cell's
  boundary exactly (the rank-independence prediction stated in the
  manifest BEFORE the run, confirmed by this execution); what r changes is
  only the penalty's magnitude through T — at the worst sampled point
  W = 256 the 256-rank cell's difference is 3231360 ns against the
  1024-rank cell's 3240864 ns (both read off the artifacts' own
  evaluation tables: 3366000 - 134640 and 3682800 - 441936).

Control pairs, same grid:

- `uec_tfc_ring` vs `uec_ring_free`: the SAME sign change at the SAME
  exact boundary 25600 (the unwindowed control behaves identically to the
  UB comparator — the boundary is the admission-law term alone).
- `uec_ring_free` vs `ub_flat_ring_mid`: d = 0 at EVERY grid point — no
  boundary. The honesty anchor (the two profiles' unwindowed ring
  stand-ins are numerically indistinguishable at L0, mirroring the
  committed cross-design sweep's delta-0 anchor).

## What this artifact is NOT

- Not a UEC-vs-UnifiedBus performance verdict: both sides run FREE
  parameters; the UB side is a free stand-in at an unanchored scale, not
  an anchored UB identity; the UEC ring is a free stand-in, not a UEC
  topology claim.
- Not a claim that any UEC or UnifiedBus system's ranking changes
  anywhere: it is the ranking relation of two declared model identities
  under one declared freedom, and within it the windowed side never
  overtakes — it stops being penalized.
- No label beyond PROPOSED/E0 is asserted or implied.
