# ASTRA-sim analytical backend — container runbook

Audience: the adapter code. Everything below was observed at the
pinned versions on this host; **every command block in this runbook was
executed at least once** (log:
`backends/docker/smoke_s2.log`, sections "EXECUTED COMMAND").
Anything *not* exercised in S2 is stated as prose and explicitly marked
"not executed" — do not treat it as verified.

Evidence label: the binary runs the documented example (`IMPLEMENTED_UNVERIFIED`
backend status; no observable validated against another fidelity yet).

## 1. Versions and identity

| Component | Version / identity |
|---|---|
| Docker engine (host) | 29.8.2, darwin arm64 (OrbStack) |
| Image | `essun/astra-sim-analytical:s1`, image ID `sha256:bb02b612c0dcd13eaa388a0ba05616b1c89e83468702a54f523f7742b02c9c8b`, platform `linux/arm64`, local only (never pushed) |
| Base image | `ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b` (canonical OCI index digest) |
| ASTRA-sim | commit `4ce9ecfe746a3ee5fe47559a11d91644d641fa7f` (2.0, 2026-09-19, MIT) — verified in-container during S1 pin check |
| Submodules (in image) | chakra `0e3cd40`, astra-network-analytical `e8c5119`, astra-memory-analytical `641cce8`, fmt `7e73566`, spdlog `63f0875`; `csg-htsim` and `ns-3` NOT initialized (not compiled by this target) |
| Toolchain in image | gcc/g++ 11.4.0, cmake 3.22.1, make 4.3, boost 1.74.0, zlib 1.2.11, git 2.34.1 (jammy apt); abseil 20240722.0 and protobuf 29.0 (protoc 29.0) from source; yaml-cpp `a83cd31` via CMake FetchContent |
| Binary | `/opt/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Unaware` (compat symlink `.../build/AnalyticalAstra/bin/AnalyticalAstra`), sha256 `ecc3a52d44c7134ce353ed03b8cb0076e5bfdbf2659bcdbb0cc5f2d760749ea4` |
| Build recipe | `backends/docker/astra-sim.Dockerfile`; full build log `backends/docker/build_s1.log` (the S1 build command is recorded in the Dockerfile header comment — it was executed in S1, not S2) |

## 2. Exact docker run command (as executed in S2)

Host-side wrapper (smoke log line 15 records it; `...` abbreviations there are
spelled out below from the log's exact in-container section, lines 18–23):

```bash
docker run --name essun-s2 essun/astra-sim-analytical:s1 bash -c 'mkdir -p /tmp/astra-s2 && cd /tmp/astra-s2 && \
  /opt/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Unaware \
    --workload-configuration=/opt/astra-sim/examples/workload/microbenchmarks/reduce_scatter/4npus_1MB/reduce_scatter \
    --system-configuration=/opt/astra-sim/examples/system/native_collectives/Ring_4chunks.json \
    --remote-memory-configuration=/opt/astra-sim/examples/remote_memory/analytical/no_memory_expansion.json \
    --network-configuration=/opt/astra-sim/examples/network/analytical/Ring_4npus.yml ; rc=$? ; echo ASTRA_EXIT=$rc'
```

In-container payload exactly as logged (smoke log lines 18–23); the trailing
`; rc=$? ; echo ASTRA_EXIT=$rc` is S2 logging instrumentation, not part of the
tool's interface:

```bash
mkdir -p /tmp/astra-s2 && cd /tmp/astra-s2 &&
  /opt/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Unaware \
    --workload-configuration=/opt/astra-sim/examples/workload/microbenchmarks/reduce_scatter/4npus_1MB/reduce_scatter \
    --system-configuration=/opt/astra-sim/examples/system/native_collectives/Ring_4chunks.json \
    --remote-memory-configuration=/opt/astra-sim/examples/remote_memory/analytical/no_memory_expansion.json \
    --network-configuration=/opt/astra-sim/examples/network/analytical/Ring_4npus.yml ; rc=$? ; echo ASTRA_EXIT=$rc
```

This is the documented upstream example
`examples/run_scripts/analytical/congestion_unaware/Ring_reducescatter_4npus.sh`
at the pin, minus its `build.sh` preamble (already baked into the S1 image).
An identical second run in a fresh container (`essun-s2b`) was executed during
S2's determinism spot-check and reproduced the same numeric results.

Preconditions observed to matter:

- The run directory (`/tmp/astra-s2` above) must be writable: the binary
  creates a `log/` directory in its CWD.
- Only the four `--*-configuration` flags are required; everything else has
  defaults (section 3).

## 3. Command-line interface (verified in source at the pin)

From `astra-sim/network_frontend/analytical/common/CmdLineParser.cc` at commit
`4ce9ecf` (read on the host checkout, same commit):

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `--workload-configuration` | string | (required) | Workload **prefix**, see §4.1 |
| `--system-configuration` | string | (required) | System JSON, §4.2 |
| `--remote-memory-configuration` | string | (required) | Remote-memory JSON, §4.4 |
| `--network-configuration` | string | (required) | Analytical network YAML, §4.3 |
| `--comm-group-configuration` | string | `empty` | Communicator group config |
| `--logging-configuration` | string | `empty` | Logging config |
| `--logging-folder` | string | `log` | Where `log.log`/`err.log` go (relative to CWD) |
| `--num-queues-per-dim` | int | `1` | Queues per dimension |
| `--compute-scale` | double | `1` | Compute scale |
| `--comm-scale` | double | `1` | Communication scale |
| `--injection-scale` | double | `1` | Injection scale |
| `--rendezvous-protocol` | bool | `false` | Rendezvous protocol |

## 4. Input file formats

### 4.1 Workload — Chakra protobuf traces, addressed by prefix

`--workload-configuration` is a **prefix, not a single file**. At the pin
(`astra-sim/workload/Workload.cc`, constructor): the binary opens
`<prefix>.<npus_id>.et` per NPU, i.e. for the 4-NPU example the prefix
`.../4npus_1MB/reduce_scatter` resolves to `reduce_scatter.0.et`,
`reduce_scatter.1.et`, `reduce_scatter.2.et`, `reduce_scatter.3.et`
(one file per NPU id, 85–87 bytes each in the example).

Each `.et` file is a binary Chakra execution trace — serialized protobuf
messages defined by `et_def.proto`, present in the image at
`/opt/astra-sim/extern/graph_frontend/chakra/schema/protobuf/et_def.proto`
(chakra pin `0e3cd40`; the host checkout's chakra submodule is uninitialized,
read it in the image or at any chakra `0e3cd40` checkout). Schema essentials:
a `GlobalMetadata` record first (the example traces carry version string
`0.0.4L`, visible in the file header), then `Node` records with fields
`id, name, type (NodeType enum), ctrl_deps[], data_deps[],
start_time_micros, duration_micros, inputs, outputs, attr[]`
(`AttributeProto` key/value bags; the example traces use attribute names
`is_cpu_op`, `comm_type`, `comm_size`). `NodeType` values include
`COMP_NODE`, `COMM_SEND_NODE`, `COMM_RECV_NODE`, `COMM_COLL_NODE`;
`CollectiveCommType` values include `ALL_REDUCE` … `REDUCE_SCATTER`, `BARRIER`.
Traces are generated upstream by Chakra's converter tools from e.g. PyTorch
exports — for essun, W1/W2 workload generation to `.et` is the adapter's job and
is NOT yet done (this runbook only documents the consumed format).

### 4.2 System configuration — JSON

Example: `examples/system/native_collectives/Ring_4chunks.json` (full
content; passed verbatim in S2):

```json
{
    "scheduling-policy": "LIFO",
    "endpoint-delay": 10,
    "active-chunks-per-dimension": 1,
    "preferred-dataset-splits": 4,
    "all-reduce-implementation": ["ring"],
    "all-gather-implementation": ["ring"],
    "reduce-scatter-implementation": ["ring"],
    "all-to-all-implementation": ["ring"],
    "collective-optimization": "localBWAware",
    "local-mem-bw": 1600,
    "boost-mode": 0,
    "roofline-enabled": 0,
    "peak-perf": 900
}
```

### 4.3 Network configuration — YAML (analytical backend)

Example: `examples/network/analytical/Ring_4npus.yml` (full content; passed
verbatim in S2). Lists are per-dimension:

```yaml
topology: [ Ring ]
npus_count: [ 4 ]
bandwidth: [ 50.0 ]  # GB/s
latency: [ 500.0 ]  # ns
```

### 4.4 Remote-memory configuration — JSON

Example: `examples/remote_memory/analytical/no_memory_expansion.json`
(full content; passed verbatim in S2):

```json
{
    "memory-type": "NO_MEMORY_EXPANSION"
}
```

(Other memory types exist for the memory-expansion backend; not exercised
here.)

## 5. Output format

There is **no CSV/JSON result file**. ASTRA-sim 2.0 analytical reports
through spdlog to (a) stdout and (b) rotating file sinks in
`<logging-folder>/` under the CWD — `log/log.log` (INFO and up; same lines as
stdout) and `log/err.log` (ERROR and up; 0 bytes in the S2 run). Sink set
confirmed in `astra-sim/common/Logging.cc` at the pin; artifacts exported
during S2 live at `backends/docker/smoke_s2_artifacts/log/`
(`log.log` sha256 `fb93012c…ad484`, `err.log` empty).

Line grammar for the result lines (one group per NPU `sys[i]`; exact strings
from the S2 run, wall-clock timestamps stripped):

```text
[workload] [info] sys[i] finished, <N> cycles, exposed communication <M> cycles.
[statistics] [info] sys[i]. Post statistics processing start.
[statistics] [info] sys[i]. Post statistics processing end.
[statistics] [info] sys[i], Wall time: <N>
[statistics] [info] sys[i], Comm time: <M>
...
[system] [warning] Exiting
```

For the reference command above, all four NPUs reported
`Wall time: 22240` and `Comm time: 22240` (S2 log lines 30–50). Units: the
lines are labeled cycles; the execution record documents that in the analytical
frontend these correspond to ns of simulated time (carried from S2, not
independently re-derived here — re-confirm before parsing
semantics are frozen). Practical parsing notes:

- Result lines are identifiable by the `[statistics]` channel plus the literal
  `, Wall time: ` / `, Comm time: ` suffixes; per-NPU id is `sys[<id>]`.
- `Wall time` = total simulated completion time of that NPU's workload;
  `Comm time` = time in communication (in this pure-collective example it
  equals wall time; with compute nodes in the trace it will differ).
- Exit status: process exits 0 on success (S2 observed `ASTRA_EXIT=0` twice);
  CLI parse errors exit `-1` per `CmdLineParser.cc`.
- Timestamps inside the log lines are wall-clock of the simulation process,
  not simulated time — ignore them when parsing; the numeric results were
  identical across the two S2 runs.

## 6. Adapting this for essun runs

Not executed in S2 — parameters to vary against the interface above:

- Swap the four configuration paths for essun-generated inputs (same
  formats as §4). NPU count must agree across `npus_count` (network YAML),
  the number of `<prefix>.<id>.et` files, and any communicator-group config.
- To get `log/` onto the host without a post-run copy, bind-mount a host
  directory as the container run directory (`docker run` volume semantics);
  S2 instead exported artifacts out of the stopped container, and the exact
  export command was not preserved in the log, so prefer the mount route —
  but verify it before relying on it.
- The image contains the full pinned source tree under `/opt/astra-sim`
  (including `examples/`) — inputs can be mounted over or placed in a
  writable run dir; only the run dir needs to be writable.

## 7. Provenance

- All executed commands, stdout, exit codes, artifact hashes:
  `backends/docker/smoke_s2.log` (S2) and
  `backends/docker/build_s1.log` (S1).
- Pin metadata and capability matrix: `backends/pins/astra-sim.md`.
- Boundaries respected: no remote
  git/registry operations, nothing installed on the host.
