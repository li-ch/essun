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

## Envelope `uec_vs_ub_window_boundary_payload16m_v1`

Envelope id `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119` — status PROPOSED at evidence level E0. Manifest `experiments/envelopes/uec_vs_ub_window_boundary_payload16m_v1.yaml` (sha256 `2a222477dfdd4e3be0bc6d038176b04af1283f2ebbb907318d34962150ae8b30`). Every value below is a closed-form analytical identity executed by its landed backend under declared free parameters; nothing here is measured or says anything about hardware.

Fixed operating point (exact, range-validated):

- A-XDUO-BW = 64 (range [1, 1024])
- A-XDUO-LAT = 200 (range [10, 2000])
- A-TFC-CR = 200 (range [0, 2000])
- A-XDUO-TP = 1024 (range [2, 1024])
- A-XDUO-PAYLOAD = 16777216 (range [1024, 16777216])
- axis A-TFC-W: grid 256, 6400, 12800, 25600, 51200, 102400, 256000, 1048576 inside [256, 1048576]

| A-TFC-W | ub_flat_ring_pod | uec_ring_free | uec_tfc_ring |
|---|---|---|---|
| 256 | 932976 | 932976 | 52786800 |
| 6400 | 932976 | 932976 | 2504304 |
| 12800 | 932976 | 932976 | 1456752 |
| 25600 | 932976 | 932976 | 932976 |
| 51200 | 932976 | 932976 | 932976 |
| 102400 | 932976 | 932976 | 932976 |
| 256000 | 932976 | 932976 | 932976 |
| 1048576 | 932976 | 932976 | 932976 |

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
- Region: `uec_ring_free` and `ub_flat_ring_pod` tie exactly on [256, 1048576].


---

## Envelope `uec_vs_ub_window_bw_boundary_v1`

Envelope id `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b` — status PROPOSED at evidence level E0. Manifest `experiments/envelopes/uec_vs_ub_window_bw_boundary_v1.yaml` (sha256 `dad997de55a534e8ee7d9ea7f81d87965b490d08e6e507eecb8a881e2ad1b753`). Every value below is a closed-form analytical identity executed by its landed backend under declared free parameters; nothing here is measured or says anything about hardware.

Fixed operating point (exact, range-validated):

- A-XDUO-LAT = 200 (range [10, 2000])
- A-TFC-CR = 200 (range [0, 2000])
- A-TFC-W = 25600 (range [256, 1048576])
- A-XDUO-TP = 1024 (range [2, 1024])
- A-XDUO-PAYLOAD = 1048576 (range [1024, 16777216])
- axis A-XDUO-BW: grid 8, 16, 32, 64, 128, 256, 512, 1024 inside [1, 1024]

| A-XDUO-BW | ub_flat_ring_pod | uec_ring_free | uec_tfc_ring |
|---|---|---|---|
| 8 | 671088 | 671088 | 671088 |
| 16 | 540144 | 540144 | 540144 |
| 32 | 474672 | 474672 | 474672 |
| 64 | 441936 | 441936 | 441936 |
| 128 | 425568 | 425568 | 441936 |
| 256 | 417384 | 417384 | 441936 |
| 512 | 413292 | 413292 | 441936 |
| 1024 | 411246 | 411246 | 441936 |

### Pair `uec_tfc_ring` vs `ub_flat_ring_pod`

- Axis A-XDUO-BW: sign 0 -> 1 on bracket ['64', '128']; boundary exactly 64 (verified, affine-x-verified).
- Region: `uec_tfc_ring` and `ub_flat_ring_pod` tie exactly on [8, 64].
- Region: `uec_tfc_ring` ranks strictly worse than `ub_flat_ring_pod` on [128, 1024].

### Pair `uec_tfc_ring` vs `uec_ring_free`

- Axis A-XDUO-BW: sign 0 -> 1 on bracket ['64', '128']; boundary exactly 64 (verified, affine-x-verified).
- Region: `uec_tfc_ring` and `uec_ring_free` tie exactly on [8, 64].
- Region: `uec_tfc_ring` ranks strictly worse than `uec_ring_free` on [128, 1024].

### Pair `uec_ring_free` vs `ub_flat_ring_pod`

No ranking boundary at any sampled point: `uec_ring_free` and `ub_flat_ring_pod` tie exactly at every sampled operating point on the whole grid.
- Region: `uec_ring_free` and `ub_flat_ring_pod` tie exactly on [8, 1024].


---

## Envelope `uec_vs_ub_window_lat_boundary_v1`

Envelope id `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554` — status PROPOSED at evidence level E0. Manifest `experiments/envelopes/uec_vs_ub_window_lat_boundary_v1.yaml` (sha256 `470c730d4ed4c1ca23e9c94bbf2bf6c15ff583c24b8ac358c674988e9d1541be`). Every value below is a closed-form analytical identity executed by its landed backend under declared free parameters; nothing here is measured or says anything about hardware.

Fixed operating point (exact, range-validated):

- A-XDUO-BW = 64 (range [1, 1024])
- A-TFC-CR = 200 (range [0, 2000])
- A-TFC-W = 25600 (range [256, 1048576])
- A-XDUO-TP = 1024 (range [2, 1024])
- A-XDUO-PAYLOAD = 1048576 (range [1024, 16777216])
- axis A-XDUO-LAT: grid 25, 50, 100, 200, 400, 800, 1600 inside [10, 2000]

| A-XDUO-LAT | ub_flat_ring_pod | uec_ring_free | uec_tfc_ring |
|---|---|---|---|
| 25 | 83886 | 83886 | 83886 |
| 50 | 135036 | 135036 | 135036 |
| 100 | 237336 | 237336 | 237336 |
| 200 | 441936 | 441936 | 441936 |
| 400 | 851136 | 851136 | 867504 |
| 800 | 1669536 | 1669536 | 1718640 |
| 1600 | 3306336 | 3306336 | 3420912 |

### Pair `uec_tfc_ring` vs `ub_flat_ring_pod`

- Axis A-XDUO-LAT: sign 0 -> 1 on bracket ['200', '400']; boundary exactly 200 (verified, affine-x-verified).
- Region: `uec_tfc_ring` and `ub_flat_ring_pod` tie exactly on [25, 200].
- Region: `uec_tfc_ring` ranks strictly worse than `ub_flat_ring_pod` on [400, 1600].

### Pair `uec_tfc_ring` vs `uec_ring_free`

- Axis A-XDUO-LAT: sign 0 -> 1 on bracket ['200', '400']; boundary exactly 200 (verified, affine-x-verified).
- Region: `uec_tfc_ring` and `uec_ring_free` tie exactly on [25, 200].
- Region: `uec_tfc_ring` ranks strictly worse than `uec_ring_free` on [400, 1600].

### Pair `uec_ring_free` vs `ub_flat_ring_pod`

No ranking boundary at any sampled point: `uec_ring_free` and `ub_flat_ring_pod` tie exactly at every sampled operating point on the whole grid.
- Region: `uec_ring_free` and `ub_flat_ring_pod` tie exactly on [25, 1600].

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
