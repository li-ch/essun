# Saturation-boundary artifact record — the window comparison swept on the shared hop-latency axis (matrix input)

Matrix build (2026-10-31): the UEC-vs-UB window comparison swept on the
SHARED hop-latency axis `A-XDUO-LAT` (range [10, 2000]) with the window
held at W = 25600 bytes — the third reading of the same saturation
boundary: latency stretches the credit round trip (L + L_cr), so the fixed
window covers the bandwidth-delay product only while B*(L+L_cr) <= W,
i.e. L <= W/B - L_cr. Machinery: `src/essun/orchestrator/opgrids.py`,
`boundaries.py`, `envelopes.py`, `envviz.py`. Manifest:
`experiments/envelopes/uec_vs_ub_window_lat_boundary_v1.yaml`.

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

Under the declared freedom of the shared per-hop latency (`A-XDUO-LAT`,
registered range 10..2000 ns) at the stated operating point — 1024 ranks,
1 MiB payload, window W = 25600 bytes, shared B = 64 bytes/ns,
credit-return 200 ns — the UEC profile's admission-law ring identity ties
the UnifiedBus paper profile's permitted flat-ring pod identity exactly at
every latency with L <= W/B - L_cr = 200 ns and ranks strictly worse at
every latency above it: the saturation boundary sits at exactly
L\* = 200 ns, and the windowed comparator is NEVER faster.

## Artifact identity (content-addressed)

| Field | Value |
| --- | --- |
| envelope_id (inputs: canonical manifest + code version) | `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554` |
| artifact content sha256 (`boundary.json` bytes) | `ef0577a3e8def41b26bfe0affc81761d9d2ee4184c9a0906301710c32fa6b147` |
| envelope-data content sha256 (`envelope-data.json` bytes) | `d33badd14f84fda14ca815c2eedbf6c8012d00e89d116d6de40463efbd348171` |
| manifest sha256 | `470c730d4ed4c1ca23e9c94bbf2bf6c15ff583c24b8ac358c674988e9d1541be` |
| code version | 0.1.0 |

Reproduce (byte-identical; the runner refuses a byte drift on replay):

```bash
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_lat_boundary_v1.yaml
# -> envelope_id 81f555ea…, artifact sha256 ef0577a3… (boundary.json.sha256 records it)
```

## The operating point (every value range-validated against its registry)

| Parameter | Value (exact) | Registered range | Registry |
| --- | --- | --- | --- |
| ranks r | 1024 | [2, 1024] (`A-XDUO-TP`) | `experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml` |
| payload M | 1048576 bytes | [1024, 16777216] (`A-XDUO-PAYLOAD`) | same |
| shared link bandwidth B | 64 bytes/ns | [1, 1024] (`A-XDUO-BW`) | same |
| swept per-hop latency L (grid) | 25, 50, 100, 200, 400, 800, 1600 | [10, 2000] (`A-XDUO-LAT`) | same |
| window W (fixed) | 25600 bytes | [256, 1048576] (`A-TFC-W`) | `experiments/vertical_slice/assumptions_tfc.yaml` |
| credit-return latency L_cr | 200 ns | [0, 2000] (`A-TFC-CR`) | same |

Comparators and shared-parameter bar: unchanged from
`uec_vs_ub_window_boundary_v1.BOUNDARY.md` (`uec_tfc_ring` with the TFC
admission law UEC11-FC-R02, `ub_flat_ring_pod` with no window per UBP-F04,
`uec_ring_free` as the unwindowed control; B and L from the one shared
record — here L is the swept axis BOTH flavors bind to, so ranking
differences may still come ONLY from the window term).

## The boundary (exact fractions, as the detector emitted them)

Per-rank wire traffic T = 2*(r-1)/r * M = 2095104 bytes (same identity for
all three comparators). The per-hop latency term 2*(r-1)*L cancels in the
difference (both identities carry the same chain), so above the boundary
the penalty grows in exact proportion to the credit round trip alone:
16368 ns at L = 400, 59104 ns at L = 800, 114576 ns at L = 1600.

Detector output for the flagship pair `uec_tfc_ring` vs
`ub_flat_ring_pod`, axis `A-XDUO-LAT`:

- sign of d = t(tfc) - t(flat ring) flips 0 -> +1 on the grid bracket
  [200, 400]; **boundary L\* = 200 exactly**, resolved by exact secant and
  VERIFIED by re-execution (d(200) = 0; method `affine-x-verified`; grid
  differences d(200) = 0, d(400) = 16368 ns > 0).
- Regions (grid evidence, exact endpoints): exact TIE on [25, 200]; TFC
  ranks WORSE on [400, 1600]. The windowed identity is never faster at
  ANY sampled latency — the same saturation structure as the window-axis
  artifact, read in the third variable.
- Closed form: d(L) = 0 for B*(L+L_cr) <= W and
  T*((L+L_cr)/W - 1/B) above — zero at and below 200 ns, positive above;
  the flip point is exactly L\* = W/B - L_cr = 25600/64 - 200 = 200 ns,
  the SAME arithmetic object as the window-axis boundary W\* = B*(L+L_cr)
  solved for L. Longer hops stretch the credit loop, so one fixed window
  stops covering the bandwidth-delay product exactly when the loop's
  round trip exceeds W/B.

Control pairs, same grid:

- `uec_tfc_ring` vs `uec_ring_free`: the SAME sign change at the SAME
  exact boundary 200 (the unwindowed control behaves identically to the UB
  comparator — the boundary is the admission-law term alone).
- `uec_ring_free` vs `ub_flat_ring_pod`: d = 0 at EVERY grid point — no
  boundary. The honesty anchor (the two profiles' unwindowed ring
  identities are numerically indistinguishable at L0 under every shared
  latency, mirroring the committed cross-design sweep's delta-0 anchor).

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
