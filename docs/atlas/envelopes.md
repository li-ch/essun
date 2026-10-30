# Performance envelopes over declared free-parameter ranges

Evidence level **E0 only**: every table and boundary below compares closed-form analytical identities under explicit free parameters at exact operating points — arithmetic facts of the models, never measurements, never hardware claims, never standard-derived values (the one standard-derived constant in the family, the UEC 256-byte credit unit, lives in its backend and appears here only as emitted identity output). A boundary is a statement about the RANKING RELATION OF MODEL IDENTITIES: saturation boundaries tie at and above the threshold and rank strictly worse below it; a two-sided crossing changes sign through zero on both sides. No claim, label, or README status upgrades from this page.

Each section below is generated deterministically from its content-addressed envelope artifact (the committed record under `experiments/envelopes/` carries the artifact identity and reproduction commands; the visualization data series — exact fractions plus display-only float mirrors — live under `envelope-data/`).

## Envelope `uec_vs_ub_window_boundary_v1`

Envelope id `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0` — status PROPOSED at evidence level E0. Manifest `experiments/envelopes/uec_vs_ub_window_boundary_v1.yaml` (sha256 `d7fa81dcc9ca5870eff5bbb919729baf4bb0952f3a28477b89c78bffbcd95165`). Every value below is a closed-form analytical identity executed by its landed backend under declared free parameters; nothing here is measured or says anything about hardware.

Fixed operating point (exact, range-validated):

- A-XDUO-BW = 64 (range [1, 1024])
- A-XDUO-LAT = 200 (range [10, 2000])
- A-TFC-CR = 200 (range [0, 2000])
- A-XDUO-TP = 1024 (range [2, 1024])
- A-XDUO-PAYLOAD = 1048576 (range [1024, 16777216])
- axis A-TFC-W: grid 256, 6400, 12800, 25600, 51200, 102400, 256000, 1048576 inside [256, 1048576]

| A-TFC-W | uec_ring_free | uec_tfc_ring | ub_flat_ring_pod |
|---|---|---|---|
| 256 | 441936 | 3682800 | 441936 |
| 6400 | 441936 | 540144 | 441936 |
| 12800 | 441936 | 474672 | 441936 |
| 25600 | 441936 | 441936 | 441936 |
| 51200 | 441936 | 441936 | 441936 |
| 102400 | 441936 | 441936 | 441936 |
| 256000 | 441936 | 441936 | 441936 |
| 1048576 | 441936 | 441936 | 441936 |

### Pair `uec_tfc_ring` vs `ub_flat_ring_pod`

- Axis A-TFC-W: sign 1 -> 0 on bracket ['12800', '25600']; boundary exactly 25600 (verified, affine-x-verified).
- Region: `uec_tfc_ring` ranks strictly worse than `ub_flat_ring_pod` on [256, 12800].
- Region: `uec_tfc_ring` and `ub_flat_ring_pod` tie exactly on [25600, 1048576].

### Pair `uec_tfc_ring` vs `uec_ring_free`

- Axis A-TFC-W: sign 1 -> 0 on bracket ['12800', '25600']; boundary exactly 25600 (verified, affine-x-verified).
- Region: `uec_tfc_ring` ranks strictly worse than `uec_ring_free` on [256, 12800].
- Region: `uec_tfc_ring` and `uec_ring_free` tie exactly on [25600, 1048576].

### Pair `uec_ring_free` vs `ub_flat_ring_pod`

No ranking boundary at any sampled point: `uec_ring_free` and `ub_flat_ring_pod` tie exactly at every sampled operating point on the whole grid.

---

## Envelope `uec_vs_ub_window_boundary_tp256_v1`

Envelope id `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730` — status PROPOSED at evidence level E0. Manifest `experiments/envelopes/uec_vs_ub_window_boundary_tp256_v1.yaml` (sha256 `eb29f7d568a93192665af42a2c55dcbd5a51f1a11ecabadef5031d5628f16982`). Every value below is a closed-form analytical identity executed by its landed backend under declared free parameters; nothing here is measured or says anything about hardware.

Fixed operating point (exact, range-validated):

- A-XDUO-BW = 64 (range [1, 1024])
- A-XDUO-LAT = 200 (range [10, 2000])
- A-TFC-CR = 200 (range [0, 2000])
- A-XDUO-TP = 256 (range [2, 1024])
- A-XDUO-PAYLOAD = 1048576 (range [1024, 16777216])
- axis A-TFC-W: grid 256, 6400, 12800, 25600, 51200, 102400, 256000, 1048576 inside [256, 1048576]

| A-TFC-W | uec_ring_free | uec_tfc_ring | ub_flat_ring_mid |
|---|---|---|---|
| 256 | 134640 | 3366000 | 134640 |
| 6400 | 134640 | 232560 | 134640 |
| 12800 | 134640 | 167280 | 134640 |
| 25600 | 134640 | 134640 | 134640 |
| 51200 | 134640 | 134640 | 134640 |
| 102400 | 134640 | 134640 | 134640 |
| 256000 | 134640 | 134640 | 134640 |
| 1048576 | 134640 | 134640 | 134640 |

### Pair `uec_tfc_ring` vs `ub_flat_ring_mid`

- Axis A-TFC-W: sign 1 -> 0 on bracket ['12800', '25600']; boundary exactly 25600 (verified, affine-x-verified).
- Region: `uec_tfc_ring` ranks strictly worse than `ub_flat_ring_mid` on [256, 12800].
- Region: `uec_tfc_ring` and `ub_flat_ring_mid` tie exactly on [25600, 1048576].

### Pair `uec_tfc_ring` vs `uec_ring_free`

- Axis A-TFC-W: sign 1 -> 0 on bracket ['12800', '25600']; boundary exactly 25600 (verified, affine-x-verified).
- Region: `uec_tfc_ring` ranks strictly worse than `uec_ring_free` on [256, 12800].
- Region: `uec_tfc_ring` and `uec_ring_free` tie exactly on [25600, 1048576].

### Pair `uec_ring_free` vs `ub_flat_ring_mid`

No ranking boundary at any sampled point: `uec_ring_free` and `ub_flat_ring_mid` tie exactly at every sampled operating point on the whole grid.

---

## Envelope `ring_vs_torus16_bw_boundary_v1`

Envelope id `5e22355aa36dc75fe1900d9b544121705a6d0c12473dc3d0c8cb8ae6d916721d` — status PROPOSED at evidence level E0. Manifest `experiments/envelopes/ring_vs_torus16_bw_boundary_v1.yaml` (sha256 `57d8c92b79db8b3086a2771745e18c33f5368206dc8536d2afb5f08f8d358d20`). Every value below is a closed-form analytical identity executed by its landed backend under declared free parameters; nothing here is measured or says anything about hardware.

Fixed operating point (exact, range-validated):

- A-XDUO-LAT = 200 (range [10, 2000])
- A-XDUO-TP = 16 (range [2, 1024])
- A-XDUO-PAYLOAD = 1048576 (range [1024, 16777216])
- axis A-XDUO-BW: grid 16, 32, 64, 128, 256, 512, 1024 inside [1, 1024]

| A-XDUO-BW | ring16 | torus16_2x8 | torus16_4x4 |
|---|---|---|---|
| 16 | 128880 | 183424 | 199008 |
| 32 | 67440 | 93312 | 100704 |
| 64 | 36720 | 48256 | 51552 |
| 128 | 21360 | 25728 | 26976 |
| 256 | 13680 | 14464 | 14688 |
| 512 | 9840 | 8832 | 8544 |
| 1024 | 7920 | 6016 | 5472 |

### Pair `ring16` vs `torus16_4x4`

- Axis A-XDUO-BW: sign -1 -> 1 on bracket ['256', '512']; boundary exactly 8192/25 (verified, affine-reciprocal-verified).
- Region: `ring16` ranks strictly better than `torus16_4x4` on [16, 256].
- Region: `ring16` ranks strictly worse than `torus16_4x4` on [512, 1024].

### Pair `ring16` vs `torus16_2x8`

- Axis A-XDUO-BW: sign -1 -> 1 on bracket ['256', '512']; boundary exactly 8192/25 (verified, affine-reciprocal-verified).
- Region: `ring16` ranks strictly better than `torus16_2x8` on [16, 256].
- Region: `ring16` ranks strictly worse than `torus16_2x8` on [512, 1024].

### Pair `torus16_4x4` vs `torus16_2x8`

- Axis A-XDUO-BW: sign 1 -> -1 on bracket ['256', '512']; boundary exactly 8192/25 (verified, affine-reciprocal-verified).
- Region: `torus16_4x4` ranks strictly worse than `torus16_2x8` on [16, 256].
- Region: `torus16_4x4` ranks strictly better than `torus16_2x8` on [512, 1024].

---

Generated deterministically from the envelope manifests (canonical JSON, exact Fractions, no wall-clock); byte-identical on replay.
