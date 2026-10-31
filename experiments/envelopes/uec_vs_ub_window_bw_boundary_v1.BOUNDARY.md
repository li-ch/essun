# Saturation-boundary artifact record — the window comparison swept on the shared bandwidth axis (matrix input)

Matrix build (2026-10-31): the UEC-vs-UB window comparison swept on the
SHARED bandwidth axis `A-XDUO-BW` (range [1, 1024]) with the window held
at the 1 MiB cell's boundary value W = 25600 bytes — the mirror reading of
the landed D4 cell (`uec_vs_ub_window_boundary_v1.yaml`, which sweeps W at
fixed B): instead of asking which windows saturate at fixed bandwidth, it
asks which bandwidths one fixed window covers. Machinery:
`src/essun/orchestrator/opgrids.py`, `boundaries.py`, `envelopes.py`,
`envviz.py`. Manifest:
`experiments/envelopes/uec_vs_ub_window_bw_boundary_v1.yaml`.

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

Under the declared freedom of the shared link bandwidth (`A-XDUO-BW`,
registered range 1..1024 bytes/ns) at the stated operating point — 1024
ranks, 1 MiB payload, window W = 25600 bytes, shared L = 200 ns,
credit-return 200 ns — the UEC profile's admission-law ring identity ties
the UnifiedBus paper profile's permitted flat-ring pod identity exactly at
every bandwidth with B <= W/(L+L_cr) = 64 bytes/ns (the window covers the
bandwidth-delay product) and ranks strictly worse at every bandwidth above
it: the saturation boundary sits at exactly B\* = 64 bytes/ns, and the
windowed comparator is NEVER faster.

## Artifact identity (content-addressed)

| Field | Value |
| --- | --- |
| envelope_id (inputs: canonical manifest + code version) | `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b` |
| artifact content sha256 (`boundary.json` bytes) | `8cabc876ef35e7f1079e07676b3c5fec821b57d4651b838d2747bb4f38de9111` |
| envelope-data content sha256 (`envelope-data.json` bytes) | `855e62ad6a3bfe46a4efd8c57910c14843d2b74d821b3b88a0db99b28aaf014c` |
| manifest sha256 | `dad997de55a534e8ee7d9ea7f81d87965b490d08e6e507eecb8a881e2ad1b753` |
| code version | 0.1.0 |

Reproduce (byte-identical; the runner refuses a byte drift on replay):

```bash
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_bw_boundary_v1.yaml
# -> envelope_id f2019c52…, artifact sha256 8cabc876… (boundary.json.sha256 records it)
```

## The operating point (every value range-validated against its registry)

| Parameter | Value (exact) | Registered range | Registry |
| --- | --- | --- | --- |
| ranks r | 1024 | [2, 1024] (`A-XDUO-TP`) | `experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml` |
| payload M | 1048576 bytes | [1024, 16777216] (`A-XDUO-PAYLOAD`) | same |
| swept link bandwidth B (grid) | 8, 16, 32, 64, 128, 256, 512, 1024 | [1, 1024] (`A-XDUO-BW`) | same |
| shared per-hop latency L | 200 ns | [10, 2000] (`A-XDUO-LAT`) | same |
| window W (fixed) | 25600 bytes | [256, 1048576] (`A-TFC-W`) | `experiments/vertical_slice/assumptions_tfc.yaml` |
| credit-return latency L_cr | 200 ns | [0, 2000] (`A-TFC-CR`) | same |

Comparators and shared-parameter bar: unchanged from
`uec_vs_ub_window_boundary_v1.BOUNDARY.md` (`uec_tfc_ring` with the TFC
admission law UEC11-FC-R02, `ub_flat_ring_pod` with no window per UBP-F04,
`uec_ring_free` as the unwindowed control; B and L from the one shared
record — here B is the swept axis BOTH flavors bind to, so ranking
differences may still come ONLY from the window term).

## The boundary (exact fractions, as the detector emitted them)

Per-rank wire traffic T = 2*(r-1)/r * M = 2095104 bytes (same identity for
all three comparators). Above the boundary the windowed time is PINNED at
T/(W/(L+L_cr)) + 2*(r-1)*L = 441936 ns (the effective rate stops growing
with B), while the flat ring keeps improving: 425568 ns at B = 128 down to
411246 ns at B = 1024.

Detector output for the flagship pair `uec_tfc_ring` vs
`ub_flat_ring_pod`, axis `A-XDUO-BW`:

- sign of d = t(tfc) - t(flat ring) flips 0 -> +1 on the grid bracket
  [64, 128]; **boundary B\* = 64 exactly**, resolved by exact secant and
  VERIFIED by re-execution (d(64) = 0; method `affine-x-verified`; grid
  differences d(64) = 0, d(128) = 16368 ns > 0).
- Regions (grid evidence, exact endpoints): exact TIE on [8, 64]; TFC
  ranks WORSE on [128, 1024]. The windowed identity is never faster at
  ANY sampled bandwidth — the same saturation structure as the window-axis
  artifact, read in the other variable.
- Closed form: d(B) = 0 for B*(L+L_cr) <= W and
  T*((L+L_cr)/W - 1/B) above — zero at and below 64, positive above; the
  flip point is exactly B\* = W/(L+L_cr) = 25600/400 = 64 bytes/ns, the
  SAME arithmetic object as the window-axis boundary W\* = B*(L+L_cr).
  Provisioning one bandwidth-delay product of credits makes the admission
  law free for every bandwidth at or below the granted rate; above it, the
  penalty grows in exact proportion to the rate excess.

Control pairs, same grid:

- `uec_tfc_ring` vs `uec_ring_free`: the SAME sign change at the SAME
  exact boundary 64 (the unwindowed control behaves identically to the UB
  comparator — the boundary is the admission-law term alone).
- `uec_ring_free` vs `ub_flat_ring_pod`: d = 0 at EVERY grid point — no
  boundary. The honesty anchor (the two profiles' unwindowed ring
  identities are numerically indistinguishable at L0 under every shared
  bandwidth, mirroring the committed cross-design sweep's delta-0 anchor).

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
