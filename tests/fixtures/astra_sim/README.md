# ASTRA-sim analytical fixtures — pinned example Chakra ET files.

Provenance: copied verbatim from the ASTRA-sim checkout pinned at commit
`4ce9ecfe746a3ee5fe47559a11d91644d641fa7f` (license MIT, see
`backends/pins/astra-sim.LICENSE`; pin matrix in `backends/pins/astra-sim.md`)
at `examples/workload/microbenchmarks/all_reduce/8npus_1MB/`.

These are ground truth for the pure-Python Chakra ET wire encoder in
`src/essun/backends/astra_sim/chakra_et.py`: encoding the same logical
content (metadata version "0.0.4"; one COMM_COLL_NODE named
`all_reduce_8npus_1MB` with attributes is_cpu_op=false, comm_type=0
(ALL_REDUCE), comm_size=1048576; node id 0 / 3 respectively) must reproduce
these files byte-for-byte.

- `all_reduce.0.et` — rank 0: node id 0 omitted on the wire (proto3 default)
- `all_reduce.3.et` — rank 3: node id 3 serialized as `08 03`

## Execution fixture

- `w1_smoke_8rank_stdout.txt` — the verbatim combined stdout+stderr of one
  real `execute_experiment` run of the W1 smoke manifest
  (`experiments/vertical_slice/w1_decode_smoke_astra.yaml`) in the pinned
  container `essun/astra-sim-analytical:s1` (image id sha256:bb02b612c0dc,
  binary sha256 ecc3a52d..., same pin as above) on 2026-10-27. The
  `ESSUN_BINARY_SHA256=` first line and `ASTRA_EXIT=` last line are the
  docker_run_container preamble/epilogue markers (runbook
  `backends/docker/astra-sim-runbook.md`); the `[statistics] ... Wall time:`
  lines are the pinned binary's own output (all 8 ranks: 144288 ns; a
  second fresh-container run reproduced every number — deterministic).
  Wall-clock timestamps inside the spdlog prefix are run-process wall time
  and are ignored by the parser. Ground truth for
  `parse_output`/`execute_experiment` tests in
  `tests/backends/test_astra_sim_execution.py`.
