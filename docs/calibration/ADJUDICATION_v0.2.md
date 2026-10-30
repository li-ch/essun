# Calibration adjudication v0.2 — owner decision record

Date: 2026-10-30. Owner: Li Chen. Decision: **ACCEPT** the single
candidate in CALIBRATION_PROPOSAL_v0.2.md.

- **O-CCT, bandwidth-bound large-message axis (`analytical_l0_crossbar`):
  CALIBRATED within domain.** Domain: NVSwitch-class switched rack,
  NVLink-4/5 generation class, out-of-place AllReduce, per-rank 2–8 GiB,
  at the fitted diagnostic B. Evidence: the S2 fit transferring to the
  unseen holdout anchor at -1.17%, inside that anchor's own noise floor
  (records cited in the proposal; S1 split 3862e227..., S6 holdout
  89f6256b...). Evidence level: E3-within-domain; no E4 language.
- **All other axes: NO CHANGE**, confirming the proposal's own no-change
  rows (ring degenerate fits; small-message latency floor unreached; torus
  twist-blindness stands; congestion inexpressible; non-calibratable
  observables unchanged).

Consequence executed with this record: the repository label ceiling for
this axis is CALIBRATED-within-domain; the global ceiling for every other
claim remains IMPLEMENTED_UNVERIFIED; EXTERNALLY_REPRODUCED remains
unattained. This file is immutable once committed; further changes are
v0.3 proposals.
