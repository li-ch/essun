# uet-htsim fixtures — execution provenance

Pin: ultraethernet/uet-htsim commit
`65ea315b25725df9791a5b93b61cbd6938cba0a8` (BSD-2-Clause, see
`backends/pins/uet-htsim.LICENSE-Transport-WG.txt`; pin matrix in
`backends/pins/uet-htsim.md`), Docker image `essun/uet-htsim:s1`
(image id sha256:7eafbdd387fd…, binary
`/opt/uet-htsim/htsim/sim/build/datacenter/htsim_uec`, sha256
`fe5a1c64…`), runbook `backends/docker/uet-htsim-runbook.md`.

- `w1_smoke_8rank_6op_stdout.txt` — the verbatim combined stdout+stderr of
  one real `adapter.execute_experiment` run of the W1 smoke manifest
  (`experiments/vertical_slice/w1_decode_smoke_uet.yaml`) in the pinned
  container on 2026-10-28 . Layout: the
  `ESSUN_BINARY_SHA256=` first line and the `=== OP FILE <name> ===` /
  `UET_EXIT=<n>` markers are the adapter's run-orchestration
  instrumentation (six `htsim_uec` invocations, one per compiled op
  matrix, op order; A-UET1-OPFILE/A-UET2-OPSER); everything between them
  is the pinned binary's own output (config section, per-flow
  `starting at`/`finished at` lines, `New:` summary). Flags executed
  verbatim from the manifest: `-linkspeed 512000` (echoed "Linkspeed set
  to 512Gbps"), `-hop_latency 0.2` (echoed), `-seed 20261026` (echoed);
  every flow finishes by 3.17033 us, far inside the retained `-end 1000`
  window (A-UET1-END verified). Per-op completions (max flow FCT):
  3.17033, 3.17033, 3.16832, 3.16832, 3.17033, 3.17033 us; serialized
  chain O-CCT 19.01796 us = 19017.96 ns exactly. A second fresh-container
  run reproduced this stdout byte-for-byte AND all six `logout.dat`
  traces byte-for-byte (deterministic; content-addressed run_id
  `fbb46d166ea155f514fb74026c13782187ce381d814b51d6f5490bbc2c263129` in
  `results/`, git-ignored by design). Ground truth for
  `parse_output`/`execute_experiment` tests in
  `tests/backends/test_uet_htsim_execution.py`.
