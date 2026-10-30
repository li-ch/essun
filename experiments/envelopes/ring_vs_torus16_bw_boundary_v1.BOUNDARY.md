# Boundary artifact record — ring vs torus on the declared bandwidth freedom at rank 16 (G4)

G4 (2026-10-30): the boundary detector's FIRST cells on the BANDWIDTH
axis and its FIRST catalogued TWO-SIDED ranking crossings — the contrast
class of the window family's saturation boundaries (tie at and above,
strictly worse below): here every pairwise difference changes sign
through zero on BOTH sides. Three sweep-registered algorithm identities of
the atlas's landed 16-rank cells — the flat-ring baseline and both
declared torus factorizations (2x8 skewed, 4x4 square) — under the ONE
shared freedom axis `A-XDUO-BW`. Machinery:
`src/essun/orchestrator/{opgrids,boundaries,envelopes,envviz}.py`.
Manifest: `experiments/envelopes/ring_vs_torus16_bw_boundary_v1.yaml`.

## Labels (read first)

- Status: **PROPOSED**.
- Evidence level: **E0** — exact arithmetic of analytical identities under
  declared freedom. No empirical claim is made.
- This artifact is a statement about the RANKING RELATION OF MODEL
  IDENTITIES at exact operating points, not about any measured system and
  not about hardware: every value is a closed-form identity executed by
  its landed backend under FREE parameters (nothing standard-derived,
  nothing measured).

## The claim (decision-readable, one sentence)

Under the declared shared per-link bandwidth freedom (`A-XDUO-BW`,
registered range 1..1024 bytes/ns) at 16 ranks, 1 MiB payload, shared
L = 200 ns, ALL THREE pairwise ranking relations among the flat-ring,
2x8-torus, and 4x4-torus identities change sign at exactly the same
bandwidth B\* = M/(L\*r) = 8192/25 = 327.68 bytes/ns (between the 256 and
512 grid points, resolved exactly and verified by re-execution): the flat
ring ranks strictly better than both torus factorizations below B\*
(wire-dominated regime — it moves the least per-rank wire, 15M/8 against
11M/4 and 3M) and strictly worse above (chain-dominated regime — its 30L
latency chain against 16L and 12L), and the square torus ranks strictly
worse than the skew below B\* and strictly better above — every
transition here is a TRUE two-sided crossing through exact zero, never a
tie, the structural opposite of the window family's penalty-then-tie
saturation boundary.

## Artifact identity (content-addressed)

| Field | Value |
| --- | --- |
| envelope_id (inputs: canonical manifest + code version) | `5e22355aa36dc75fe1900d9b544121705a6d0c12473dc3d0c8cb8ae6d916721d` |
| artifact content sha256 (`boundary.json` bytes) | `89dad19e0cf6108fefb12789b47a2def67aaa29e9e54d16b50c94cee7824e94a` |
| envelope-data content sha256 (`envelope-data.json` bytes) | `28b15abfb3d9f6d57a48cb6dcfbcca75443b0894c7e8a7feaa739a0a1da61462` |
| manifest sha256 | `57d8c92b79db8b3086a2771745e18c33f5368206dc8536d2afb5f08f8d358d20` |
| code version | 0.1.0 |

Reproduce (byte-identical; the runner refuses a byte drift on replay):

```bash
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/ring_vs_torus16_bw_boundary_v1.yaml
# -> envelope_id 5e22355a…, artifact sha256 89dad19e… (boundary.json.sha256 records it)
.venv/bin/python -m pytest -q tests/orchestrator tests/determinism/test_envelope_replay.py
```

## The operating point (every value range-validated against its registry)

| Parameter | Value (exact) | Registered range | Registry |
| --- | --- | --- | --- |
| swept bandwidth B (grid) | 16, 32, 64, 128, 256, 512, 1024 | [1, 1024] (`A-XDUO-BW`) | `experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml` |
| ranks r | 16 | [2, 1024] (`A-XDUO-TP`) | same |
| payload M | 1048576 bytes | [1024, 16777216] (`A-XDUO-PAYLOAD`) | same |
| shared per-hop latency L | 200 ns | [10, 2000] (`A-XDUO-LAT`) | same |

## The comparators (named, one same-workload operating point)

| Model | Identity (exact, B the axis) | Backend |
| --- | --- | --- |
| `ring16` | flat unidirectional ring: t = 15M/(8B) + 30L = 1966080/B + 6000 ns | `analytical_l0` |
| `torus16_2x8` | 2x8 torus: t = 11M/(4B) + 16L = 2883584/B + 3200 ns | `analytical_l0_torus2d` |
| `torus16_4x4` | 4x4 torus: t = 3M/B + 12L = 3145728/B + 2400 ns | `analytical_l0_torus2d` |

All three bind the SAME shared assumptions (`A-XDUO-BW` ->
`link.bytes_per_ns`, `A-XDUO-LAT` -> `link.hop_latency_ns`), so ranking
differences come only from the identities' own wire/chain terms.

## The boundaries (exact fractions, as the detector emitted them)

Closed forms (differences affine in 1/B — every identity's rate term):

- d(ring16 - torus16_4x4) = -1179648/B + 3600 = -18\*(M/(16B) - 200)
- d(ring16 - torus16_2x8) = -917504/B + 2800 = -14\*(M/(16B) - 200)
- d(torus16_4x4 - torus16_2x8) = 262144/B - 800 = 4\*(M/(16B) - 200)

Each is the atlas 16r-torus FACTORIZATION LAW gap = 2(r1-1)(r2-1)
(M/(Br) - L) (coefficients 18 and 14 for the ring pairs; their difference
4 for the intra-family pair), read on the B axis at fixed M.

Detector output, axis `A-XDUO-BW`:

- `ring16` vs `torus16_4x4`: sign -1 -> +1 on bracket [256, 512], grid
  differences -1008 / +1296 ns; **boundary exactly 8192/25**, method
  `affine-reciprocal-verified` (affine in 1/B, root re-executed at the
  exact Fraction and returned exactly zero).
- `ring16` vs `torus16_2x8`: sign -1 -> +1 on [256, 512], differences
  -784 / +1008 ns; boundary exactly 8192/25, `affine-reciprocal-verified`.
- `torus16_4x4` vs `torus16_2x8`: sign +1 -> -1 on [256, 512],
  differences +224 / -288 ns; boundary exactly 8192/25,
  `affine-reciprocal-verified`.
- Regions (grid evidence, exact endpoints): ring better than both torus
  factorizations on [16, 256], strictly worse on [512, 1024]; the square
  torus worse than the skew on [16, 256], better on [512, 1024]. At the
  boundary all three identities take the same value 12000 ns — a
  THREE-WAY concurrent crossing at one exact coordinate.

Why the boundary is exact and rank-closed: the atlas's payload-axis law
puts the same three identities' crossovers at M\* = L\*B\*r (204800 bytes
at B = 64 — the landed 16r-torus three-way point); solving the same law
for B at fixed M puts them at B\* = M/(L\*r) = 1048576/3200 = 8192/25 —
the SAME coincidence read on the bandwidth axis, with the SAME three-way
value 12000 ns. The prediction was stated in the manifest BEFORE the run
(all three boundaries exactly at 8192/25, strictly two-sided, no tie) and
the execution confirmed it on every pair.

## What this artifact is NOT

- Not a claim that any fabric's ranking changes anywhere: it is the
  ranking relation of three declared model identities under one declared
  freedom; B and L are free parameters, not properties of any system.
- Not an atlas payload-axis result restated: the grid, the axis, and the
  content-addressed artifact are new; the closed-form agreement it shows
  is exactly the check that the detector's exact resolution is consistent
  with the landed atlas law.
- No label beyond PROPOSED/E0 is asserted or implied.
