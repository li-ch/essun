# ASTRA-sim csg-htsim (packet-level) backend — container runbook

Audience: the future essun backend-adapter decision (analysis only — no
adapter code is written here). This runbook mirrors
`backends/docker/astra-sim-runbook.md` (the analytical
frontend) and adds a delta section (§8) against it. The exact run
command below was executed once (log:
`backends/docker/astra_csg_s2.log`, sections "EXECUTED
COMMAND"); every source and input fact cited here was re-verified this stage in the
pinned in-image tree (log: `backends/docker/astra_csg_s3.log`,
sections A–Z3). Anything *not* exercised is prose and marked "not executed".

Evidence label: the binary runs the documented example
(`IMPLEMENTED_UNVERIFIED` backend status). **Determinism status: the
unpatched image `:s1` is NOT run-to-run reproducible (time-seeded RNG, §6);
the patched image `:s1-seeded` (one env-seeded `srand` line, §6.1)
IS run-reproducible per seed — byte-identical state artifacts across fresh
containers at seeds 1 and 2.**

## 1. Versions and identity

| Component | Version / identity |
|---|---|
| Docker engine (host) | 29.8.2, darwin arm64 (OrbStack) |
| Image | `essun/astra-csg-htsim:s1`, image ID `sha256:e18b4fd1061c924b354b455eea2e7108ca4cf7a752e2471a322ffb8e8e2e2900`, platform `linux/arm64`, 1.74 GB, local only (never pushed) |
| Base image | `ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b` — same digest as the analytical image |
| ASTRA-sim | commit `4ce9ecfe746a3ee5fe47559a11d91644d641fa7f` (2.0, 2026-09-19, MIT) — identical commit to the analytical image |
| Submodules (in image) | chakra `0e3cd40`, astra-network-analytical `e8c5119`, astra-memory-analytical `641cce8`, fmt `7e73566`, spdlog `63f0875`, **csg-htsim `67cbbbb1cccdbddc400803414127d044ecd55290`** (2023-12-11, BSD-2-Clause; LICENSE sha256 `c550c0ba…978585`, copy at `backends/pins/csg-htsim.LICENSE`); ns-3 NOT initialized |
| Toolchain in image | identical to the analytical image plus `patch` 2.7.1 (needed by `build.sh patch_htsim`); see the Dockerfile header for the full version list |
| Binary | `/opt/astra-sim/build/astra_htsim/build/bin/AstraSim_HTSim`, 12,242,008 bytes, sha256 `fe36ee2aae16e7bf43c074f80fa2c7064653b751d9e3178b2075ee0ef5404216` |
| Patched htsim lib | `extern/network_backend/csg-htsim/sim/libhtsim.a`, sha256 `f9271372054e61dfee4e65caef2865ebd8bd1feb6fc823d0170a8871a5bee877` (contains the patched `tcp.o`; the integration patch `build/astra_htsim/htsim_astrasim.patch` adds ASTRA flow-finish callbacks to `sim/tcp.cpp`/`sim/tcp.h`) |
| Build recipe / log | `backends/docker/astra-csg-htsim.Dockerfile`; full build log `backends/docker/astra_csg_s1.log` (S1; `BUILD_EXIT=0`) |
| Linkage note | the htsim frontend **links `Analytical_Congestion_Unaware`** (`network_frontend/htsim/CMakeLists.txt:47`) and compiles the analytical `common/*.cc` sources itself (`CMakeLists.txt:22-24`) — the analytical network backend is a build dependency of this binary |

## 2. Exact docker run command (as executed in S2)

Host side (S2 log lines 20–21):

```bash
docker run --name essun-csg-s2 essun/astra-csg-htsim:s1 bash -c '<payload below>'
```

In-container payload exactly as logged (S2 log lines 23–35; `SECONDS`/`rc`
echoes are S2 logging instrumentation, not part of the tool interface):

```bash
SECONDS=0
cd /opt/astra-sim/build/astra_htsim/build &&
  /opt/astra-sim/build/astra_htsim/build/bin/AstraSim_HTSim \
    --workload-configuration=/opt/astra-sim/examples/workload/microbenchmarks/all_reduce/8npus_1MB/all_reduce \
    --system-configuration=/opt/astra-sim/examples/system/native_collectives/Ring_4chunks.json \
    --remote-memory-configuration=/opt/astra-sim/examples/remote_memory/analytical/no_memory_expansion.json \
    --network-configuration=/opt/astra-sim/examples/network/analytical/Ring_8npus.yml \
    --htsim_opts -topo /opt/astra-sim/examples/network/htsim/8nodes.topo
rc=$? ; echo ASTRA_EXIT=$rc ; echo ELAPSED_SECONDS=$SECONDS
```

Result: `ASTRA_EXIT=0`, `ELAPSED_SECONDS=0` (well under 1 s wall clock);
a second fresh container also exited 0 (S2 determinism spot-check).

This is the documented upstream example
`examples/run_scripts/htsim/run_htsim.sh` at the pin, **minus the script
itself**, which has two defects at this commit (S3 log §E, line numbers from
the in-image file):

1. Line 13–16: `${EXAMPLE_DIR:?}` is required but never defined in the
   script — running it verbatim aborts (`EXAMPLE_DIR: parameter null or not
   set`). The S2 payload substitutes `EXAMPLE_DIR := /opt/astra-sim/examples`.
2. Line 17: `TOPO="${SCRIPT_DIR:?}"/network/htsim/8nodes.topo` resolves to
   `examples/run_scripts/htsim/network/htsim/8nodes.topo`, which does **not
   exist**; the file actually ships at
   `examples/network/htsim/8nodes.topo` (verified in-container in S2).

Preconditions observed to matter:

- The run directory must be writable: besides `log/`, the binary writes
  **`logout.dat` (8.6 MB per run of this example!) and `idmap.txt` into its
  CWD**. The upstream script `cd`s into `build/astra_htsim/build` first
  (mirrored above).
- `--htsim_opts` must be the **last** flag: `HTSimMain.cc:83-88` passes
  everything from the first `--htsim_opts` occurrence to the end of `argv`
  verbatim to the htsim session — any later ASTRA flag would be swallowed as
  an htsim option.

## 3. Command-line interface (verified in source at the pin)

The htsim frontend compiles the analytical frontend's shared parser
(`CMakeLists.txt:22-24` globs `../analytical/common/*.cc`, including
`CmdLineParser.cc`), so the **analytical runbook §3 flag table applies
verbatim** (the four required `--*-configuration` flags plus
`comm-group-configuration`, `logging-configuration`, `logging-folder`,
`num-queues-per-dim`, `compute-scale`, `comm-scale`, `injection-scale`,
`rendezvous-protocol`). Two additions and one consumption caveat:

| Flag | Type / default | Meaning (anchor) |
|---|---|---|
| `--htsim-proto` | string, default `tcp` | network protocol selector; enum `HTSimProto {None, Tcp}` (`HTSimSession.hh:15-18`) — `tcp` is the only implemented value |
| `--htsim_opts <args…>` | tail of argv | not parsed by cxxopts; forwarded verbatim to the htsim session (`HTSimMain.cc:83-88`) |

`--htsim_opts` sub-flags (parsed by the classic htsim loop,
`network_frontend/htsim/proto/HTSimProtoTcp.cc:63-101`):

| Sub-flag | Default | Meaning |
|---|---|---|
| `-topo <file>` | (none → synthesized fat tree at `HOST_NIC` = 100000 Mbps, `datacenter/main.h:9`) | fat-tree topology file, §4.5; node count must equal the YAML's `npus_count` or the process `exit(1)` (`HTSimProtoTcp.cc:146-150`) |
| `-o <file>` | `logout.dat` | binary event-log filename (§5) |
| `-sub <n>` | `1` | subflow count per flow (stdout: "Using subflow count 1") |
| `-nodes <n>` | `npus_count` from the network YAML | node-count override (stdout: "requested nodes 8") |
| `UNCOUPLED` / `COUPLED_INC` / `FULLY_COUPLED` / `COUPLED_TCP` / `COUPLED_SCALABLE_TCP` / `COUPLED_EPSILON <eps>` | `COUPLED_EPSILON` (=5) with `epsilon=1` (stdout: "Using algo=5 epsilon=1") | multipath-scheduling coupling algorithm |

Exit semantics (differ from analytical — adapter-relevant):

- **`main` returns 0 on completion AND on simulation timeout** — a timeout
  only prints `Warning: Simulation timed out.` (`HTSimMain.cc:110-112`). Exit
  code 0 alone does not prove all ranks finished; check for that warning or
  the completion line in `log/log.log` (§5).
- `exit(1)` on `.topo`-nodes vs requested-nodes mismatch
  (`HTSimProtoTcp.cc:146-150`).
- CLI parse errors exit `-1` per the shared `CmdLineParser.cc` (as analytical).
- Consumption caveat: `HTSimMain.cc:26-38` fetches `comm-scale`,
  `injection-scale`, `rendezvous-protocol`, `num-queues-per-dim` — but **not**
  `compute-scale` (accepted by the shared parser, unused by this main).
- Event horizon: the TCP proto glue sets an initial simulated-time end of
  4 s (`HTSimProtoTcp.cc:55`, `timeFromSec(4)`); `HTSimSession.cc:200` also
  sets an end time at shutdown. The observed run's event log ends at 2.0 s
  (§5). Horizon mechanics beyond this were not traced (bounded probe).

## 4. Input file formats

Four of the five inputs use the **same formats as the analytical frontend**
(analytical runbook §4); only the `.topo` file is new.

### 4.1 Workload — Chakra protobuf traces, addressed by prefix

Identical mechanism (analytical §4.1): `<prefix>.<npus_id>.et` per NPU. The
documented example resolves `all_reduce.0.et` … `all_reduce.7.et` (81–83 bytes
each; S3 log §F). Schema `et_def.proto` at chakra `0e3cd40`, in-image under
`/opt/astra-sim/extern/graph_frontend/chakra/schema/protobuf/`.

### 4.2 System configuration — JSON

Same file as the analytical example (`Ring_4chunks.json`): scheduling-policy
LIFO, endpoint-delay 10, active-chunks-per-dimension 1, ring implementations
for all four collectives, `collective-optimization localBWAware`,
`local-mem-bw 1600`, `peak-perf 900`. Full content in S3 log §C; field
discussion in analytical §4.2.

### 4.3 Network configuration — analytical YAML, **still required** (dual description)

The htsim frontend does not replace the analytical network YAML — it parses it
(`HTSimMain.cc:43-44`, `NetworkParser` + `construct_topology`) to build the
system/collective layer's topology, and `npus_count` from the YAML flows into
the packet layer (`htsim_info.nodes`, `HTSimMain.cc:97`) and into the
consistency check against the `.topo` file. Example
(`examples/network/analytical/Ring_8npus.yml`, full content, S3 log §B):

```yaml
topology: [ Ring ]
npus_count: [ 8 ]
bandwidth: [ 50.0 ]  # GB/s
latency: [ 500.0 ]  # ns
```

Verified consumers of the YAML here are **structural** (ring dimension, NPU
count). No path was found this stage by which its `bandwidth`/`latency` values
enter the packet layer's timing — observed link speeds come from the `.topo`
file (§4.5). Treating the YAML bw/lat as no-ops for this backend is a
reasonable working hypothesis but was **not** exhaustively verified; flag for
the adapter decision.

### 4.4 Remote-memory configuration — JSON

Same `no_memory_expansion.json` as analytical §4.4; the analytical
remote-memory backend is the only one at this pin and is linked into this
binary too (`HTSimMain.cc:58-59`).

### 4.5 NEW: htsim fat-tree topology — `.topo` text file

Full content of the documented example
(`examples/network/htsim/8nodes.topo`, S3 log §A):

```text
Nodes 8
Tiers 3
Podsize 4

Tier 0
Downlink_speed_Gbps 200
Radix_Down 2
Radix_Up 2
Downlink_Latency_ns 1000

Tier 1
Downlink_speed_Gbps 200
Radix_Down 2
Radix_Up 4
Downlink_Latency_ns 1000
Bundle 1

Tier 2
Downlink_speed_Gbps 100
Radix_Down 4
Downlink_Latency_ns 1000
Bundle 2
```

Field semantics (from `FatTreeTopology::load` and the observed startup
stdout): `Nodes` = hosts (must equal `npus_count` in the YAML, else exit 1);
`Tiers` = 3 fabric levels (Src↔ToR, ToR↔Agg, Agg↔Core); `Podsize` = hosts per
pod; per tier: `Downlink_speed_Gbps`, `Radix_Down`, `Radix_Up` (absent in the
top tier), `Downlink_Latency_ns`, `Bundle` (parallel links). For this file the
constructor prints: 8 nodes, 2 pods, 4 hosts/pod, 2 ToR + 2 Agg switches per
pod, 4 core switches, 1 µs on all three link classes, 0 ns switch latencies.
Switch queue capacity is not in the file — the glue passes `memFromPkt(8)` =
8 × 1500 B = **12,000 B per tier and direction**
(`HTSimProtoTcp.cc:142`; stdout: "Tier N QueueSize Down/Up 12000 bytes").

Consistency rule: `npus_count` (YAML) = `Nodes` (.topo) = number of
`<prefix>.<id>.et` files.

## 5. Output format

### 5.1 stdout — two interleaved streams

1. **ASTRA-sim spdlog lines**, same line grammar as the analytical frontend
   (`[workload]/[statistics] sys[i] … , Wall time: <N>` / `, Comm time: <M>`;
   analytical runbook §5). Same parsing recipe applies.
2. **Plain iostream htsim lines** (these are NOT spdlog and do NOT enter
   `log/log.log`): fat-tree construction block; `pathcount <n>` per route
   (`fat_tree_topology.cpp:1123,1239`); `Send flow <id> from <src> to <dst>
   with size <bytes>`; `Finish receiving/sending flow <id>` (patched
   `tcp.cpp:700`); `Flow tcpsrc finished at <t>` with **t in milliseconds**
   (`tcp.cpp:187`, `timeAsMs`); retransmission-timer lines `At <t_ms> RTO
   <ms> MDEV … CWND … Flow ID mtcp_<…>` (`tcp.cpp:548-551` — the time is
   `now/1e9` of the picosecond event clock, i.e. ms).

### 5.2 `log/log.log` and `log/err.log`

Same spdlog file sinks as analytical (`log/log.log` INFO-level ASTRA lines
only — the htsim printfs above are absent; `log/err.log` empty in the smoke
run). One addition the analytical file did not have: a final
`[network] [debug] All ranks have finished. Exiting simulation.` line that
did **not** appear on stdout — a grep-able completion marker. Exported
artifacts: `backends/docker/astra_csg_s2_artifacts/log/`
(`log.log` 4349 B sha256 `6ea0f8b1…8933`, `err.log` empty).

### 5.3 `idmap.txt` (new file, CWD)

Text map `id name` per logged entity (`loggers.cpp:17-21`). Deterministic
across runs (S2: bit-identical sha256 `2b791fa6…c598a`). Names reflect the
fat-tree + glue: `PacketFlow`, `clock`, `SinkSampling`, `RtxScanner`,
`Switch_LowerPod_0..3`, `Switch_UpperPod_0..3`, `Switch_Core_0..3`, `pipe`s,
`QueuelogSampling`, per-link queues (`LS0->DST0(0)`, `SRC0->LS0(0)`,
`US0->CS0(0)`, …), and 8 × `astraSimSrc` (one per NPU).

### 5.4 `logout.dat` (new file, CWD; rename with `-o`)

Binary event log written by `Logfile::writeRecord` (`logfile.cpp:67-80`):
**44-byte records from offset 0, no header** —
`[double time_s][uint32 type][uint32 id][uint32 ev][double val1][double
val2][double val3]`, little-endian, `time_s` = event-clock seconds
(`timeAsSec`). `type` codes come from `Logger::EventType`
(`loggertypes.h:56-71`: QUEUE_EVENT=0 … TCP_SINK=11, MTCP=12 … FLOW_EVENT=44);
`id` resolves via `idmap.txt`. Decoded this stage on the exported S2 artifact
(read-only struct walk): **8,632,976 B = exactly 196,204 records**; type
counts QUEUE_APPROX(5)=129,608, QUEUE_RECORD(4)=64,804, TCP_SINK(11)=896,
MTCP(12)=896; time range 0.001–2.0 s; 960 distinct ids. Queue sampling
(1 ms period, `HTSimProtoTcp.cc:129-130`) dominates the file; sink/MTCP
sampling at 1 s boundaries (896 = 448 flows × 2 samples).

Format caveat: `logfile.cpp:83-150` (`transposeLog`) would rewrite the file on
`Logfile` destruction with a text preamble and `ev` offset by `100*type` —
that rewrite did **not** run in the observed artifact (records carry raw
per-type `ev`, no preamble), so expect the raw appended format from this
integration. An upstream reader exists prebuilt in the image
(`csg-htsim/sim/parse_output`, takes `-idmap`); not executed.

## 6. Determinism and what a run record means (S2 finding; root cause)

- **Observation** (S2 log "DETERMINISM SPOT-CHECK"): identical command, same
  image/binary/inputs, two fresh containers → **all 16 Wall/Comm values
  differ**, the ~1040M-cycle straggler NPU changes (run 1: sys[0]; run 2:
  sys[4], sys[5]), `logout.dat` and `log.log` hashes differ; `idmap.txt` is
  bit-identical; `err.log` empty both times. Contrast: the analytical smoke
  reproduced identical numbers across two runs.
- **Root cause** (source at the pin; S2 probe + S3 strengthening): the
  frontend glue seeds the RNG from wall-clock time — `srand(time(NULL))` at
  `HTSimProtoTcp.cc:102`. Consumers found in the compiled path:
  1. the glue's own multipath route choice `rand() % net_paths[src][dst]->size()`
     (`HTSimProtoTcp.cc:246,250,257,261,286` — found in S3; this is why
     `pathcount` routes differ per run),
  2. queue drop decisions `if ((uint64_t)random() < p)`
     (`compositequeue.cpp:72`, `aeolusqueue.cpp:81`),
  3. `config.cpp:9-22` `drand()`/`rand()` distribution helpers.
  Time-seeded RNG → per-run routes/drops/RTO patterns → different
  retransmission tails → different straggler NPUs and Wall times. Upstream
  property of the integration at this pin, not a recipe error.
- **Implication (hard rule 6, determinism):** until seeding is controlled —
  candidate mechanisms: an upstream patch at `HTSimProtoTcp.cc:102` to a
  fixed/configurable seed, or interception of `srand`/`time` (e.g.
  `LD_PRELOAD` shim) — packet-level runs are **stochastic samples**. An
  immutable run record for this backend cannot mean replay-identical numeric
  outputs; record inputs + hashes as usual and either compare at distribution
  level (N-run envelopes) or gate replay verification on seeding control.
  This is an adapter-decision input; **no adapter code here**.

### 6.1 RESOLVED for recorded evidence: seeded image `essun/astra-csg-htsim:s1-seeded` (2026-10-28)

The first candidate mechanism above is now implemented at the image level
(no adapter code): the Dockerfile patches exactly one line of the pinned
tree before `build.sh` —

```c
// HTSimProtoTcp.cc:102, was: srand(time(NULL));
{ const char* s = getenv("ESSUN_SEED"); srand(s ? atoi(s) : 1); }
```

deviation recorded in `backends/pins/astra-sim.md` §"Deviations from pin".
Image `essun/astra-csg-htsim:s1-seeded` (ID `sha256:6cc48e30efa8…02aa2f`,
binary sha256 `a36f981cb919…bb8a94`; `libhtsim.a` hash unchanged vs `s1`,
so only the frontend TU differs). Verified (log
`backends/docker/astra_csg_d032_smoke.log`, same §2 command, fresh
containers):

- **Seeds 1 (default, no env) and 2 (ESSUN_SEED=2), two runs each**:
  `logout.dat` (6,500,032 B and 8,701,616 B resp.), `idmap.txt`, `err.log`
  byte-identical per seed; `log/log.log` identical after stripping the
  wall-clock `[YYYY-MM-DD HH:MM:SS.mmm]` spdlog prefix (that prefix is
  output formatting time, present in the unpatched pin too); stdout
  identical as a line multiset (`sort`-hash equal) — the residual
  byte-level stdout difference is the interleaving order of the two stdout
  streams (plain `cout` htsim lines vs spdlog console sink), a buffer-flush
  timing artifact, not simulation state.
- **Seed knob effective:** different seeds produce different outputs
  (logout.dat hashes differ between seeds 1 and 2).
- **Seed policy for essun runs: record `ESSUN_SEED` with every run record
  (default 1). N-run envelopes are reproducible per seed.**
- **Latent upstream bugs exposed (findings, not patch effects; seeds that
  abort are themselves deterministic and byte-identical):** seeds 0 and 42
  abort on `HTSimSession.cc:143` ("Cannot find send_event in sent_hash" —
  flow-finish bookkeeping lookup miss); seed 2026 aborts on
  `eventlist.cpp:69` (`when>=now()` causality assertion); seeds 1, 2, 13
  complete. 3 of 7 probed seeds abort — expect aborted seeds in envelope
  studies and treat each as a counterexample finding (CGFR input), not
  retry noise. The unpatched `:s1` nightly runs completing twice was luck
  of the time-seeded draw.

## 7. Runtime and scale (observed)

- 8-NPU 1 MB all_reduce → 448 htsim flows (one per ASTRA send:
  `HTSimNetworkApi.cc:70-86`, `sim_send` → `send_flow`; flow size = chunk
  size, 32,768 B here), 196,204 log records, 8.6 MB `logout.dat`; whole run
  **well under 1 s wall clock** in-container (S2: ~21 ms of process time for
  the reporting phase; `ELAPSED_SECONDS=0`).
- Analytical comparison point: the 4-NPU analytical smoke was also
  sub-second. At microbenchmark scale both are effectively free;
  packet-level cost grows with flows × simulated duration (1 ms queue
  sampling dominates `logout.dat` growth), and long workloads risk the 4 s
  event horizon (§3).

## 8. Delta vs the analytical frontend — adapter-decision input

| Dimension | Analytical (`astra-sim-runbook.md`) | csg-htsim (this runbook) |
|---|---|---|
| Inputs | 4 configs (workload prefix, system JSON, remote-memory JSON, network YAML) | same 4, **plus** `--htsim-proto` and `--htsim_opts` tail (`-topo`, `-o`, `-sub`, `-nodes`, coupling algo); network YAML stays but becomes **structural/dual-description** (§4.3); `.topo` adds a physical fabric description (per-tier Gbps/radix/ns/Bundle) |
| Input consistency | `npus_count` = #`.et` files (+ comm-group cfg) | additionally = `.topo` `Nodes`, else `exit(1)` |
| CLI consumption | all parser flags used by the analytical main | `compute-scale` accepted but not fetched by `HTSimMain`; `--htsim_opts` must be last (argv-tail swallowing) |
| Outputs | stdout spdlog + `log/log.log`/`err.log` | + plain-iostream htsim stdout stream (per-flow events, RTO lines, `pathcount`), + `logout.dat` (binary 44-B records, §5.4), + `idmap.txt`; `log.log` gains a `[network][debug]` completion line absent from stdout |
| Result lines | same `sys[i], Wall/Comm time` grammar; deterministic values | same grammar; **stochastic values** (§6); straggler NPUs arise from packet dynamics (RTO at 1040 ms in the example) |
| Time units | "cycles" ≈ ns (carried from the analytical runbook; re-confirm before freezing parser semantics) | ASTRA lines consistent with ns 1:1 (flow-finish 1040.01 ms ↔ Wall 1,040,007,384); htsim stdout flow/RTO times in **ms** |
| Exit code | 0 on success, `-1` on parse error | 0 on success **and on timeout** (warning printed); 1 on node-count mismatch |
| Runtime | sub-second (4-NPU smoke) | sub-second (8-NPU smoke); scales with events; initial 4 s event horizon |
| Determinism | bit-identical across runs | not run-to-run reproducible (time-seeded RNG, §6) |

**Capabilities that appear** (absent analytically): switch queues with
probabilistic drops (composite/aeolus queues), TCP-style congestion control
with RTO/fast recovery and retransmission tails, multipath fat-tree routing
with coupling algorithms and subflows, per-flow event telemetry
(`logout.dat`/`idmap.txt`), and — most relevant to essun — **congestion
effects becoming visible in collective completion time** (the example's ring
all-reduce completion is dominated by a retransmission straggler, not by
bandwidth arithmetic).

**Capabilities unchanged:** Chakra ET workloads, collective algorithm/system
JSON knobs, the analytical remote-memory backend (still the only one), spdlog
reporting and result-line grammar.

**Capabilities still absent** (unchanged from `backends/pins/astra-sim.md`):
no UEC/UET transport semantics (this is TCP-style csg-htsim, not uet-htsim),
no FLIT/credit-lane level, no scale-up memory semantics. Only the fat-tree
topology family is wired into this frontend
(`CMakeLists.txt:32-36`); other htsim datacenter topologies exist in-tree but
are standalone entry points, not integrated.

## 9. Adapting this for essun runs (not executed — analysis only)

- Same mounting strategy as analytical §6, plus decide per-run policy for
  `logout.dat` (8.6 MB/run at microbench scale, unique per run — keep with
  `-o <run-id>.dat`, or let it overwrite) and archive `idmap.txt` (stable).
- Determinism prerequisite (§6) before any replay-verified claim on this
  backend; also decide the completion check (parse the timeout warning /
  `[network][debug]` line; exit code is insufficient).
- Keep the NPU-count triple-consistency (YAML = `.et` count = `.topo Nodes`)
  in any manifest generator.
- If `logout.dat` observables are needed (queue occupancy, per-flow times),
  budget a decode step (44-B record walk per §5.4, or the in-tree
  `parse_output`).

## 10. Provenance

- Executed smoke run, determinism spot-check, bounded root-cause probe:
  `backends/docker/astra_csg_s2.log` (S2).
- Executed source/input inspection (sections A–Z3): 
  `backends/docker/astra_csg_s3.log` (S3).
- Build evidence: `backends/docker/astra_csg_s1.log` (S1);
  recipe `astra-csg-htsim.Dockerfile`.
- Seeded-image build + two-run byte-identity evidence:
  `backends/docker/astra_csg_d032_build.log`,
  `backends/docker/astra_csg_d032_smoke.log`,
  artifacts `backends/docker/astra_csg_d032_artifacts/`;
  owner-decision report
- Pins and capability matrix: `backends/pins/astra-sim.md`
  (incl. §"Deviations from pin" for the seeding patch); license
  `backends/pins/csg-htsim.LICENSE`.
- Stage reports: `reports/p3_stage{1,2,3}.md`.
- Boundaries respected: pinned image
  only, read-only inspection in `--rm` containers, nothing installed on the
  host, no remote git/registry operations.
