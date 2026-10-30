# Saturation-boundary artifact record — UEC TFC window vs UB flat-ring pod identity (D4)

Design doc (2026-10-29) D4, build order item 4: the FIRST named-profile
comparison with envelopes and exact ranking-boundary detection. Date:
2026-10-29; saturation-boundary renaming (G6) 2026-10-30. Machinery:
`src/essun/orchestrator/opgrids.py` (operating-point grids over declared
freedom ranges), `src/essun/orchestrator/boundaries.py` (exact-Fraction
boundary detector), `src/essun/orchestrator/envelopes.py` (envelope
runner). Manifest:
`experiments/envelopes/uec_vs_ub_window_boundary_v1.yaml`.

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
point — 1024 ranks, 1 MiB payload, shared B = 64 bytes/ns, L = 200 ns,
credit-return 200 ns — the UEC profile's admission-law ring identity ties
the UnifiedBus paper profile's permitted flat-ring pod identity exactly at
every window >= 25600 bytes (100 credit units, exactly the
bandwidth-delay product B*(L+L_cr) = 64*400) and ranks strictly worse at
every window below it: the saturation boundary (the credit-provisioning
threshold) sits at exactly W = 25600 bytes, and the windowed comparator is
NEVER faster — the transition is strictly-worse-below to exact-tie-above,
not a two-sided ranking crossing (the "reversal" name this artifact
carried before 2026-10-30 overstated the sign structure; the arithmetic
was and is exactly as stated here).

## Artifact identity (content-addressed)

| Field | Value |
| --- | --- |
| envelope_id (inputs: canonical manifest + code version) | `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0` |
| artifact content sha256 (`boundary.json` bytes) | `8b5eac95ca24a46b105853128a34c5cc654914876ae38debbcb3b2cc35a9f853` |
| manifest sha256 | `d7fa81dcc9ca5870eff5bbb919729baf4bb0952f3a28477b89c78bffbcd95165` |
| code version | 0.1.0 |

**Rename record (G6, 2026-10-30).** The pre-rename artifact
(`uec_vs_ub_window_reversal_v1`, module `reversals.py`, artifact files
`reversal.json`/`reversal.md`/`reversal.json.sha256`, manifest key
`reversal_pairs`) had envelope_id
`e3fb4c817dd6ca802d82b56533f60522fb4f4b3b067921869966a97518791084`,
artifact content sha256
`430a7f94c9364936c3242a32f25a3d9c5a24843625f6ab1d7c0d68780b03ea33`, and
manifest sha256
`fa663c4124fcddce67de20801f9b7d92e600927d4b206c98c877a9ebb41372bf`.
The rename changed ONLY names and framing language (module, identifiers,
artifact filenames, manifest key and comments); every evaluation,
difference, sign, bracket, and boundary value is bit-identical, and both
content hashes changed solely because the artifact bytes and manifest
bytes embed the renamed strings. (The artifact also embeds the sha256 of
the workload and topology input files, whose header comments point at the
renamed manifest path — a comment-only change to those files, with no
config value touched.)

Reproduce (byte-identical; the runner refuses a byte drift on replay):

```bash
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_boundary_v1.yaml
# -> envelope_id 9a5f1296…, artifact sha256 8b5eac95… (boundary.json.sha256 records it)
.venv/bin/python -m pytest -q tests/orchestrator tests/determinism/test_envelope_replay.py
```

## The operating point (every value range-validated against its registry)

| Parameter | Value (exact) | Registered range | Registry |
| --- | --- | --- | --- |
| ranks r | 1024 | [2, 1024] (`A-XDUO-TP`) | `experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml` |
| payload M | 1048576 bytes | [1024, 16777216] (`A-XDUO-PAYLOAD`) | same |
| shared link bandwidth B | 64 bytes/ns | [1, 1024] (`A-XDUO-BW`) | same |
| shared per-hop latency L | 200 ns | [10, 2000] (`A-XDUO-LAT`) | same |
| credit-return latency L_cr | 200 ns | [0, 2000] (`A-TFC-CR`) | `experiments/vertical_slice/assumptions_tfc.yaml` |
| swept window W (grid) | 256, 6400, 12800, 25600, 51200, 102400, 256000, 1048576 | [256, 1048576] (`A-TFC-W`) | same |

## The comparators (named, one same-workload operating point)

| Model | Identity | Backend |
| --- | --- | --- |
| `uec_tfc_ring` | UEC free ring stand-in (`A-XDUO-IDUEC`) + the UEC profile's flagship executed semantic: TFC admission law UEC11-FC-R02, executed since G8 (2026-10-30) by the credit automaton binding `BIND-UEC11-FC-R02-AUTOMATON` with THIS ring identity `t = 2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L` as its declared steady-state abstraction | `analytical_l0_tfc` |
| `ub_flat_ring_pod` | UnifiedBus paper profile's PERMITTED pod-scale flat-ring stand-in (`A-XDUO-IDUB` range value `flat_ring_pod_when_scale_allows`) at the anchored pod scale 1024 (UBP-P18); the public UB sources are silent on flow control (UBP-F04), so this side carries no window | `analytical_l0` |
| `uec_ring_free` | the same ring identity WITHOUT the window — the unwindowed control | `analytical_l0` |

The UB profile's rack-scale anchored identity (crossbar @ 64, UBP-P17) is
excluded from THIS artifact by the same-workload gate itself (one workload
= one tp_size); the pod-scale corner of the declared rank freedom is where
BOTH profiles' declared freedom contains a ring identity, which is what
makes this a within-freedom comparison. Shared-parameter bar unchanged:
B and L come from the one shared record and are consumed by both flavors,
so ranking differences may come ONLY from the window term.

## The boundary (exact fractions, as the detector emitted them)

Per-rank wire traffic T = 2*(r-1)/r * M = 2095104 bytes (same identity for
all three comparators; a window gates rate, never bytes — O-CONSERVATION
identical everywhere, checked per point by the backends).

Detector output for the flagship pair `uec_tfc_ring` vs `ub_flat_ring_pod`,
axis `A-TFC-W`:

- sign of d = t(tfc) - t(flat ring) flips +1 -> 0 on the grid bracket
  [12800, 25600]; **boundary W\* = 25600 exactly**, resolved by exact
  secant and VERIFIED by re-execution (d(25600) = 0; method
  `affine-x-verified`; grid differences d(12800) = 32736 ns > 0,
  d(25600) = 0).
- Regions (grid evidence, exact endpoints): TFC ranks WORSE on
  [256, 12800]; exact TIE on [25600, 1048576]. The windowed identity is
  never faster at ANY sampled window — this is the saturation boundary
  (credit-provisioning threshold), not a ranking reversal.
- Closed form (why the boundary is exact, an arithmetic fact of the two
  identities): d(W) = T * ((L+L_cr)/W - 1/B) for W < B*(L+L_cr) and 0
  above — positive for every W < 25600, zero at and above; the flip point
  is exactly the bandwidth-delay product W\* = B*(L+L_cr) = 64*400 =
  25600 bytes = 100 UEC credit units. Provisioning at least one
  bandwidth-delay product of credits makes the admission law free at this
  operating point; below it, the penalty grows in proportion to the
  shortfall.

Control pairs, same grid:

- `uec_tfc_ring` vs `uec_ring_free`: the SAME sign change at the SAME
  exact boundary 25600 (the UEC-side unwindowed control behaves
  identically to the UB comparator — the boundary is the admission-law
  term alone).
- `uec_ring_free` vs `ub_flat_ring_pod`: d = 0 at EVERY grid point — no
  boundary. This is the artifact's honesty anchor (the two profiles'
  unwindowed ring identities are numerically indistinguishable at L0,
  mirroring the committed cross-design sweep's delta-0 anchor).

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
