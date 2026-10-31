# Saturation-boundary artifact record — UEC TFC window vs UB flat-ring pod at the 16 MiB payload corner (matrix input)

Matrix build (2026-10-31), the window-comparison family's SECOND payload
corner: the landed D4 cell (`uec_vs_ub_window_boundary_v1.yaml`, 1 MiB)
extended to 16 MiB — the TOP of the registered payload range
`A-XDUO-PAYLOAD` [1024, 16777216] — so the cross-fabric matrix
(`docs/atlas/cross-fabric-matrix.md`) can state the payload invariance of
the saturation boundary as a SAMPLED fact at two payload corners, not only
as the closed form's no-M-term argument. Machinery:
`src/essun/orchestrator/opgrids.py`, `boundaries.py`, `envelopes.py`,
`envviz.py`. Manifest:
`experiments/envelopes/uec_vs_ub_window_boundary_payload16m_v1.yaml`.

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
(`A-TFC-W`, registered range 256..1048576 bytes) at the stated operating
point — 1024 ranks, 16 MiB payload, shared B = 64 bytes/ns, L = 200 ns,
credit-return 200 ns — the UEC profile's admission-law ring identity ties
the UnifiedBus paper profile's permitted flat-ring pod identity exactly at
every window >= 25600 bytes (100 credit units, exactly the
bandwidth-delay product B*(L+L_cr) = 64*400 — the SAME boundary as at the
1 MiB cell, because the threshold carries no payload term) and ranks
strictly worse at every window below it: the saturation boundary sits at
exactly W = 25600 bytes, the windowed comparator is NEVER faster, and only
the below-threshold penalty magnitude changed with the payload (it is
proportional to the per-rank traffic T = 2*(r-1)/r * M, 16x the 1 MiB
cell's).

## Artifact identity (content-addressed)

| Field | Value |
| --- | --- |
| envelope_id (inputs: canonical manifest + code version) | `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119` |
| artifact content sha256 (`boundary.json` bytes) | `bead3d61a7a65c8b5b1cfd59e72a7aec31b9703bff053e3f95b8450c59a27f98` |
| envelope-data content sha256 (`envelope-data.json` bytes) | `cc2f42733a9aef1c6c825f711ab5455c458658c597c78d3d28ba67a25634e8ce` |
| manifest sha256 | `2a222477dfdd4e3be0bc6d038176b04af1283f2ebbb907318d34962150ae8b30` |
| code version | 0.1.0 |

Reproduce (byte-identical; the runner refuses a byte drift on replay):

```bash
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_boundary_payload16m_v1.yaml
# -> envelope_id 6d9a30db…, artifact sha256 bead3d61… (boundary.json.sha256 records it)
```

## The operating point (every value range-validated against its registry)

| Parameter | Value (exact) | Registered range | Registry |
| --- | --- | --- | --- |
| ranks r | 1024 | [2, 1024] (`A-XDUO-TP`) | `experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml` |
| payload M | 16777216 bytes | [1024, 16777216] (`A-XDUO-PAYLOAD`) | same |
| shared link bandwidth B | 64 bytes/ns | [1, 1024] (`A-XDUO-BW`) | same |
| shared per-hop latency L | 200 ns | [10, 2000] (`A-XDUO-LAT`) | same |
| credit-return latency L_cr | 200 ns | [0, 2000] (`A-TFC-CR`) | `experiments/vertical_slice/assumptions_tfc.yaml` |
| swept window W (grid) | 256, 6400, 12800, 25600, 51200, 102400, 256000, 1048576 | [256, 1048576] (`A-TFC-W`) | same |

Comparators and shared-parameter bar: unchanged from
`uec_vs_ub_window_boundary_v1.BOUNDARY.md` (`uec_tfc_ring` with the TFC
admission law UEC11-FC-R02, `ub_flat_ring_pod` with no window per UBP-F04,
`uec_ring_free` as the unwindowed control; B and L from the one shared
record, so ranking differences may come ONLY from the window term).

## The boundary (exact fractions, as the detector emitted them)

Per-rank wire traffic T = 2*(r-1)/r * M = 33552384 bytes (same identity
for all three comparators; a window gates rate, never bytes).
Unwindowed ring completion time 932976 ns = T/B + 2*(r-1)*L =
524256 + 408720, identical at every grid point.

Detector output for the flagship pair `uec_tfc_ring` vs
`ub_flat_ring_pod`, axis `A-TFC-W`:

- sign of d = t(tfc) - t(flat ring) flips +1 -> 0 on the grid bracket
  [12800, 25600]; **boundary W\* = 25600 exactly**, resolved by exact
  secant and VERIFIED by re-execution (d(25600) = 0; method
  `affine-x-verified`; grid differences d(12800) = 523776 ns > 0,
  d(25600) = 0).
- Regions (grid evidence, exact endpoints): TFC ranks WORSE on
  [256, 12800]; exact TIE on [25600, 1048576]. The windowed identity is
  never faster at ANY sampled window — a saturation boundary
  (penalty-then-tie), never a two-sided ranking crossing.
- Closed form: d(W) = T * ((L+L_cr)/W - 1/B) for W < B*(L+L_cr) and 0
  above — positive for every W < 25600, zero at and above; the flip point
  is exactly the bandwidth-delay product W\* = B*(L+L_cr) = 64*400 =
  25600 bytes = 100 UEC credit units. The threshold carries NO payload
  term, which is why this 16 MiB cell reproduces the 1 MiB cell's boundary
  exactly (the payload-invariance prediction stated in the manifest
  BEFORE the run, confirmed by this execution); what M changes is only the
  penalty's magnitude through T — at the worst sampled point W = 256 the
  16 MiB cell's difference is 51853824 ns against the 1 MiB cell's
  3240864 ns (read off the artifacts' own evaluation tables:
  52786800 - 932976 and 3682800 - 441936).

Control pairs, same grid:

- `uec_tfc_ring` vs `uec_ring_free`: the SAME sign change at the SAME
  exact boundary 25600 (the unwindowed control behaves identically to the
  UB comparator — the boundary is the admission-law term alone).
- `uec_ring_free` vs `ub_flat_ring_pod`: d = 0 at EVERY grid point — no
  boundary. The honesty anchor (the two profiles' unwindowed ring
  identities are numerically indistinguishable at L0, mirroring the
  committed cross-design sweep's delta-0 anchor).

## What this artifact is NOT

- Not a UEC-vs-UnifiedBus performance verdict: both sides run FREE
  parameters; the UB side is the profile's declared permitted stand-in at
  pod scale, not the anchored 4D full-mesh (L1_REQUIRED per the platform
  map); the UEC ring is a free stand-in, not a UEC topology claim.
- Not a claim that any UEC or UnifiedBus system's ranking changes
  anywhere: it is the ranking relation of two declared model identities
  under one declared freedom, and within it the windowed side never
  overtakes — it stops being penalized.
- No label beyond PROPOSED/E0 is asserted or implied.
