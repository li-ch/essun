# UET-HTSim (`htsim_uec`) third-backend candidate — container runbook

Audience: anyone running or verifying the `uet_htsim_cms` backend (the
independent third backend — the adapter this runbook once awaited landed as
`src/essun/backends/uet_htsim/adapter.py`). Everything
below was observed at the pinned versions on this host; **every command block
in this runbook was executed at least once**: the §2 smoke commands during
the Docker execution stage (log: `backends/docker/uet_htsim_s2.log`, section
"COMMANDS EXECUTED (host)", lines 18–20) and the §2.1 adapter command surface
once, re-executed verbatim during runbook finalization (log:
`backends/docker/uet_htsim_s4.log`). Anything *not* exercised is stated as
prose or file content and explicitly marked "not executed" — do not treat it
as verified.

Evidence label: the pinned binary executes the W1 smoke manifest
(EXP-VS-W1-SMOKE-UET-001, six matrices) through the ordinary run path with a
reproducible RunRecord (`fbb46d16…`, byte-identical idempotent re-run).
Backend status `IMPLEMENTED_UNVERIFIED`: smoke bar of the Docker ladder only,
no observable validated against another fidelity yet.

## 1. Versions and identity

| Component | Version / identity |
|---|---|
| Docker engine (host) | 29.8.2, darwin arm64 host, `linux/arm64` containers |
| Image | `essun/uet-htsim:s1`, image ID `sha256:7eafbdd387fd521d5531050ae40ab97f0a3b81f3424c95619fbc5095da83d312`, local only (never pushed) |
| Base image | `ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b` (canonical OCI index digest; same pin as the ASTRA-sim S1 image) |
| uet-htsim | commit `65ea315b25725df9791a5b93b61cbd6938cba0a8` (2026-02-11, "Added Permutation+Incast experiment files for 800Gbps (#142)"), BSD-2-Clause — verified in-container during the S1 pin check |
| Toolchain in image | gcc/g++ 11.4.0, cmake 3.22.1, make 4.3, git 2.34.1, python3 3.10.6 (jammy apt; versions recorded in the Dockerfile header) |
| Binary | `/opt/uet-htsim/htsim/sim/build/datacenter/htsim_uec`, 14,608,472 bytes, sha256 `fe5a1c645719b792bb56c631fbd991cf7f6c824af8a97f42971bd59b584cd896`; the CMake post-build step also recreates the upstream-documented symlink `/opt/uet-htsim/htsim/sim/datacenter/htsim_uec` (used as `./htsim_uec` in S2). `build/parse_output` (trace-file reader) is also in the image. |
| Build recipe | `backends/docker/uet-htsim.Dockerfile`; full build log `backends/docker/uet_htsim_s1.log` (build executed in S1, not S2) |

## 2. Smoke commands as executed in the Docker-ladder S2

Host-side wrapper, run 1 (named container, for artifact extraction) —
`uet_htsim_s2.log` line 18:

```bash
docker run --name uet-htsim-s2 essun/uet-htsim:s1 bash -lc 'cd /opt/uet-htsim/htsim/sim/datacenter && ./htsim_uec -tm connection_matrices/one.cm; ec=$?; echo "EXIT_CODE=$ec"; exit $ec'
```

Artifact export out of the stopped container — `uet_htsim_s2.log` line 19:

```bash
docker cp uet-htsim-s2:/opt/uet-htsim/htsim/sim/datacenter/logout.dat backends/docker/uet_htsim_s2_logout.dat
```

Host-side wrapper, run 2 (`--rm`, determinism re-run, same payload) —
`uet_htsim_s2.log` line 20:

```bash
docker run --rm essun/uet-htsim:s1 bash -lc 'cd /opt/uet-htsim/htsim/sim/datacenter && ./htsim_uec -tm connection_matrices/one.cm; ec=$?; echo "EXIT_CODE=$ec"; exit $ec'
```

The in-container payload of both runs is
`cd /opt/uet-htsim/htsim/sim/datacenter && ./htsim_uec -tm connection_matrices/one.cm`;
the trailing `; ec=$?; echo "EXIT_CODE=$ec"; exit $ec` is S2 logging
instrumentation, not part of the tool's interface. Both runs exited 0 and
produced byte-identical stdout (sha256
`7bbf3b6b748943e72ec3fc93274bd2468d29c27c5aee7544fe45f0024fd6bd98`, S2 log
lines 112–113). Wall time ~5 ms for `one.cm`.

Preconditions observed to matter:

- The **CWD must be writable**: the default trace `logout.dat` is written to
  the CWD (hence the `cd` into `sim/datacenter`).
- `-tm` and `-topo` paths are resolved relative to the CWD; `./htsim_uec` is
  the upstream-documented symlink (§1). An absolute path to
  `build/datacenter/htsim_uec` works identically.

### 2.1 The adapter's actual commands (executed, re-executed)

`src/essun/backends/uet_htsim/adapter.py` (backend id `uet_htsim_cms`,
registered in `src/essun/orchestrator/runs.py`) drives the pinned image
through four host-side commands. All four were executed and
re-executed verbatim during finalization
(`backends/docker/uet_htsim_s4.log`, sections 0/A/B/C):

1. Image pin check (first step of `docker_run_container`):

   ```bash
   docker image inspect essun/uet-htsim:s1 --format '{{.Id}}'
   ```

   must print the pinned image id (§1) or the adapter refuses to execute an
   unpinned image.

2. The container run — one container, one `htsim_uec` invocation per
   compiled op matrix, in generator op order (op serialization lives in
   this orchestration, never in invented start times — A-UET1-OPFILE):

   ```bash
   docker run --rm \
     -v <inputs_dir>:/mnt/inputs \
     -v <run_dir>:/mnt/run \
     essun/uet-htsim:s1 bash -c '<script>'
   ```

   `<inputs_dir>` holds the compiled `.cm` set (a scratch copy;
   `compile_plan.json` never enters the container) and `<run_dir>` is a
   scratch trace dir; **both mounts writable** (A-UET2-BINDMOUNT: a read-only
   mount fails on this host's OrbStack virtiofs — the ASTRA-sim S2 finding —
   and the command never writes into the inputs tree anyway). The script is,
   byte-for-byte, a preamble —

   ```bash
   export LC_ALL=C
   echo "ESSUN_BINARY_SHA256=$(sha256sum /opt/uet-htsim/htsim/sim/build/datacenter/htsim_uec | cut -d' ' -f1)"
   cd /mnt/run
   ```

   — then per op file (smoke-twin values shown):

   ```bash
   echo "=== OP FILE w1_decode_smoke_uet.op000000.cm ==="
   /opt/uet-htsim/htsim/sim/build/datacenter/htsim_uec \
     -tm /mnt/inputs/w1_decode_smoke_uet.op000000.cm \
     -o w1_decode_smoke_uet.op000000.logout.dat \
     -linkspeed 512000 -hop_latency 0.2 -seed 20261026
   echo "UET_EXIT=$?"
   ```

   The `ESSUN_BINARY_SHA256` / `=== OP FILE ===` / `UET_EXIT` markers are
   adapter instrumentation around the binary's own output (the ASTRA-sim
   `ASTRA_EXIT` convention) that `parse_output` gates on: an unpinned
   binary, a reordered/partial op sequence, or any non-zero exit is rejected
   loudly, never reinterpreted. Two deltas vs the §2 smoke commands, both
   equivalent per the §2 preconditions: the binary is invoked by its build
   path (not the `./htsim_uec` symlink), and the CWD is `/mnt/run` (not
   `sim/datacenter`) with `-tm`/`-o` resolving absolutely into the mounts.

3. Compile-only surface (the S1 CLI; regenerates the committed compiled set
   byte-identically — verified by hash in S4):

   ```bash
   .venv/bin/python -m essun.backends.uet_htsim.adapter \
     experiments/vertical_slice/w1_decode_smoke_uet.yaml
   ```

4. The ordinary run path — the one command a verifier needs (same as
   `make run EXP=experiments/vertical_slice/w1_decode_smoke_uet.yaml`);
   validate -> compile -> command 2 -> parse -> RunRecord through the
   append-only evidence store:

   ```bash
   .venv/bin/python -m essun.orchestrator.runs \
     experiments/vertical_slice/w1_decode_smoke_uet.yaml
   ```

   The smoke twin re-puts idempotently to run_id
   `fbb46d166ea155f514fb74026c13782187ce381d814b51d6f5490bbc2c263129`
   (byte-identical record; verified on two fresh containers,
   re-verified).

## 3. Command-line interface (verified in source at the pin)

From the `-help` text and argument parser in
`htsim/sim/datacenter/main_uec.cpp` at commit `65ea315b` (help string lines
46–174; parser lines 268–650; read on the host checkout at the same commit).
Only flags relevant to backend integration are listed; the help text in the
source is the complete list.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `-tm FNAME` | string | read from stdin | Traffic/connection matrix input, §4.1 (the only flag S2 passed) |
| `-topo FNAME` | string | auto-generated topology | Topology input, §4.2 — **not exercised in S2; the adapter never passes it (§6)** |
| `-o FNAME` | string | `logout.dat` | Trace log file (CWD-relative), §5.2 |
| `-log STR` | string | `flow_events` | Log item; repeatable. Choices: `flow_events`, `sink`, `nic`, `tor_downqueue`, `tor_upqueue`, `switch`, `traffic`, `queue_usage` |
| `-end UINT` | us | `1000` | Simulation end time |
| `-nodes UINT` | uint | `0` | Node count for the auto-generated topology |
| `-tiers UINT` | 2, 3 | `3` | Fat-tree tiers |
| `-planes UINT` | 1..8 | `1` | Planes/ports per NIC |
| `-linkspeed NUM` | Mbps | `100000` (= `HOST_NIC`, `main.h:9`) | Link speed |
| `-mtu UINT` | bytes | `4150` | Packet size |
| `-seed UINT` | uint | `13` | Random seed — S2's two default runs were byte-identical, consistent with a fixed default seed |
| `-strat STR` | enum | `ecmp_host` | Route strategy (`ecmp_host`, `rr_ecmp`, `ecmp_host_ecn`, `reactive_ecn`, `ecmp_ar`, `ecmp_host_ar`, `ecmp_rr`) |
| `-sender_cc_algo STR` | enum | `nscc` | Sender CC (`dctcp`, `nscc`, `constant`) |
| `-sender_cc` / `-receiver_cc` | bool | `true` / `false` | Enable sender / receiver CC |
| `-cwnd UINT` | packets | `0` (= derived `maxwnd`) | Congestion window limit |
| `-q UINT` | packets | `0` (auto = 1×BDP) | Queue size |
| `-ecn UINT UINT` | bytes | `0 0` (derived) | ECN low/high thresholds |
| `-hop_latency NUM` / `-switch_latency NUM` | us | `1` / `0` | Wire / switching latency |
| `-paths UINT` | uint | `64` | Path entropy size |
| `-help` | — | — | Prints usage; unknown flag values print usage and `exit(1)` (`exit_error`, main_uec.cpp:176–182) |

## 4. Input file formats

### 4.1 Connection matrix (`.cm`) — the input passed verbatim in S2

Full content of `htsim/sim/datacenter/connection_matrices/one.cm` at the pin
(the file `-tm connection_matrices/one.cm` resolves to in the image):

```text
Nodes 16
Connections 1
0->13 start 0 size 2000000

```

Grammar (parser: `htsim/sim/datacenter/connection_matrix.cpp`, lines ~676–800,
at the pin): a whitespace-tokenized header of key-value lines — `Nodes N`,
`Connections M`, optional `Triggers T` and `Failures F` — followed by one line
per connection:

```text
src->dst [start <us>] [size <bytes>] [id <flowid>] [msg <msgid>] [trigger <id>]
```

`#`-comment lines and blank lines are skipped in the header. All key-value
tokens on a connection line are optional (`start` may be fractional us; flow
id 0 is rejected). The S2 run parsed
`Nodes: 16 Connections: 1 Triggers: 0 Failures: 0` (stdout, S2 log line 31).
The adapter-generated matrices of §2.1 (same grammar, `Connections 8`, ids
via A-UET1-IDS) were parsed identically on each execution (each op's stdout opens
`Nodes: 16 Connections: 8 Triggers: 0 Failures: 0`). The image ships ~40
ready matrices (`incast.cm`, `a2a.cm`, `perm_32n_32c_2MB.cm`, …) plus
upstream generator scripts (`gen_incast.py`, `gen_permutation.py`, …) —
**none of those shipped matrices beyond `one.cm` were ever exercised**.

### 4.2 Topology file (`-topo`) — not exercised in S2

Full content of the documented small variant
`htsim/sim/datacenter/topologies/leaf_spine_tiny.topo` at the pin (upstream
README pairs it with `-tm connection_matrices/perm_32n_32c_2MB.cm`):

```text
Nodes 32
Tiers 2
Podsize 32

Tier 0
Downlink_speed_Gbps 100
Radix_Down 8
Radix_Up 2
Downlink_Latency_ns 1000
Switch_Latency_ns 0
Oversubscribed 4

Tier 1
Downlink_speed_Gbps 100
Radix_Down 4
Downlink_Latency_ns 1000
Switch_Latency_ns 0
```

Per-tier parameter blocks (`Downlink_speed_Gbps`, `Radix_Down`/`Radix_Up`,
`Downlink_Latency_ns`, `Switch_Latency_ns`, `Oversubscribed`) as shown; the
larger `topologies/*.topo` files in the image follow the same key set. **This
format was not exercised in S2, and the adapter never passes `-topo` (§6)** —
verify before relying on it.

### 4.3 Default topology actually used in S2

With no `-topo`, the run builds a 3-tier fat tree from `-nodes`/`-tiers` at
100 Gbps (`HOST_NIC` 100000 Mbps), 1 us hop latency, 0 us switching latency,
MTU 4150, auto queue sizing 1×BDP, ECN enabled, NSCC sender CC — all defaults,
echoed in the S2 stdout config section (S2 log lines 25–49, e.g.
`FatTreeTopologyCfg … NSRV=16 … downlink_speeds=100000000000 …`).

## 5. Output formats

### 5.1 stdout

Config/setup section first (matrix parse line, linkspeed, topology cfg,
queue/ECN/RTO setup, static + per-instance NSCC parameters — S2 log lines
25–49), then the runtime section. Line grammar with the S2-observed values
(S2 log lines 50–54):

```text
Starting simulation
Flow Uec_<src>_<dst> flowId <id> uecSrc <src> starting at <us>
Flow Uec_<src>_<dst> flowId <id> uecSrc <src> finished at <us> total messages <n> total packets <n> RTS <n> total bytes <n> in_flight now <n> fair_inc <n> prop_inc <n> fast_inc <n> eta_inc <n> multi_dec <n> quick_dec <n> nack_dec <n>
.Done
New: <n> Rtx: <n> RTS: <n> Bounced: <n> ACKs: <n> NACKs: <n> Pulls: <n> sleek_pkts: <n>
```

S2-observed values for `one.cm`: flow `Uec_0_13` finished at `176.2` (us —
printed via `timeAsUs`, `uec.cpp:824` at the pin; cross-checked against the
trace record time 176.19952 us in §5.2), `490` packets, `2002140` total bytes,
summary `New: 490 Rtx: 0 RTS: 0 Bounced: 0 ACKs: 124 NACKs: 0 Pulls: 0
sleek_pkts: 0`. Parsing notes:

- Per-flow FCT line: match `^Flow .* finished at `; the FCT is the number
  after it (us). The `*_inc`/`*_dec` fields are UET CMS NSCC counters
  (pin-record scope: "flow output includes UET CMS signals").
- Summary line: match `^New: `; `New` = data packets sent, `Rtx` =
  retransmissions, `ACKs`/`NACKs` = receiver feedback counts.
- Exit code 0 on success (observed twice in S2); unknown flag values print
  usage and exit 1 (§3).
- Known deviation from the README snapshot: per-run NSCC counters
  `prop_inc`/`eta_inc` differ from the README snippet (README predates the
  pin); all load-bearing quantities match — see the S2 report for the diff.

### 5.2 Trace log `logout.dat` (htsim `# TRACE` binary format)

Written to the CWD unless overridden by `-o FNAME`. Text preamble, then
fixed-size binary records. Layout verified at the pin in
`htsim/sim/logfile.cpp` (`Logfile::writeRecord`, `transposeLog`):

- Preamble lines: `: <name>=<id>` per logged entity, `# pktsize=<n> bytes`,
  `# hostnicrate = <n> Mbps`, `# numrecords=<n>`, `# transpose=0`, `# TRACE`.
- Then `numrecords` records of **44 bytes** each, host little-endian:
  `double time` (simulated seconds) · `uint32 type` · `uint32 id` ·
  `uint32 ev` · `double val1` · `double val2` · `double val3`. The stored `ev`
  is the raw event code **plus 100×type** (transposeLog).
- Type constants: `loggertypes.h` `Logger::EventType`, notably
  `FLOW_EVENT = 50` with raw events `START = 0` / `FINISH = 1`; for those,
  `id` = logged entity id (resolvable via the preamble name table), `val1` =
  flow id, `val2` = bytes, `val3` = packets (0 at START, total at FINISH) —
  semantics from `FlowEventLoggerSimple::logEvent`/`event_to_str` in
  `loggers.cpp`.

The S2 artifact (209 bytes = 121-byte preamble + 2×44, sha256
`4733da8c5b6261e7610ab9fa2f38c26f2b110065bc0a017631a9e9e0f68a74a6`,
host copy `backends/docker/uet_htsim_s2_logout.dat`)
preamble:

```text
: Uec_0_13=267
: Uec_sink_0_13=269
# pktsize=4150 bytes
# hostnicrate = 100000 Mbps
# numrecords=2
# transpose=0
# TRACE
```

Decoded records (S3 decode of the extracted artifact; consistent with §5.1):

```text
rec0: time=0.0 s           type=50 id=267 ev=5000 (START)  val1=268.0 val2=2000000.0 val3=0.0
rec1: time=0.00017619952 s type=50 id=267 ev=5001 (FINISH) val1=268.0 val2=2000000.0 val3=490.0
```

The image also ships the upstream reader
`/opt/uet-htsim/htsim/sim/build/parse_output` (`usage: parse_output filename
[-show|-verbose|-ascii]`, source `htsim/sim/parse_output.cpp`) — **not
executed in S2, S3, or S4** (the adapter hashes traces into the run record
but does not parse them); verify before relying on it.

## 6. Adapting this for essun runs — the landed adapter route

The "future adapter work" this section originally caveated as "not executed"
now exists and executes (§2.1; backend `uet_htsim_cms`). Former caveats and
their resolution, each executed at least once (verified twice —
`backends/docker/uet_htsim_s4.log`, RunRecord `fbb46d16…`):

- **Bind-mount file route (VERIFIED, A-UET2-BINDMOUNT).** essun-generated
  matrices go in through a writable `-v <inputs>:/mnt/inputs` mount, and
  traces come back through a writable `-v <run>:/mnt/run` mount with each
  invocation's `-o` landing there — no `docker cp` export. Read-only mounts
  fail on this host (OrbStack virtiofs file-open; the ASTRA-sim S2 finding)
  and are never used.
- **Workload generation to `.cm` (LANDED, W1 only).** `compile_experiment`
  translates a validated manifest into one matrix per serialized op — §4.1
  grammar, `Nodes 16` header, flow ids `op_index*r + rank + 1`
  (A-UET1-IDS/A-UET1-OPFILE) — plus a deterministic `compile_plan.json`
  (CLI: §2.1 command 3). The committed smoke-twin set is
  `experiments/vertical_slice/uet_w1_decode_smoke_uet/`, byte-identical on
  regeneration (hash-checked in S4). W2 prefill and every other workload
  kind remain untranslated gaps the adapter **rejects loudly**, never
  approximates.
- **Node counts (GATED).** The adapter accepts ranks 2..16 only
  (A-UET1-FABRIC): the sole smoke-verified fabric shape is the
  auto-generated 3-tier fat tree built from the matrix's `Nodes 16` header
  (§4.3). Larger fabrics need a `-topo` file (§4.2) — still not exercised,
  see below.
- **Explicit `-seed` (IMPLEMENTED, platform rule 6).** The manifest seed is
  written verbatim (A-UET1-SEED; the smoke twin ran `-seed 20261026`, echoed
  by the binary as `random seed 20261026`). Determinism: two fresh
  containers byte-identical on stdout and all six traces; the finalization
  verbatim re-run reproduced the RunRecord's stdout and trace sha256s
  exactly and re-put the same run_id — the explicit seed is honored, so
  **no csg-style `ESSUN_SEED` patch was needed** (unlike the
  deviation on the csg backend).

Still **not executed** (unchanged caveats — verify before relying on any of
these):

- `-topo` files (§4.2). The adapter never passes `-topo`; every compiled
  matrix relies on the auto-generated fat tree, which is why the ranks gate
  above exists.
- The upstream validation suite
  (`sim/datacenter/validation/validate_all.py --config_json_file
  example_validate.json`, `sim/datacenter/commit_check.sh`): the README
  warns these "can take a long time" — deliberately not the bar of any
  stage to date.
- The upstream trace reader `build/parse_output` (§5.2): traces are hashed
  into the run record, not parsed; the 44-byte record layout of §5.2 was
  decoded by essun-side code against the extracted artifact.
- Cross-fidelity comparison of any observable parsed here is
  classify-don't-tune territory (platform rule 5; see
  `docs/backend-independence.md`) — this runbook documents mechanics only.

## 7. Provenance

- Docker-ladder S2 smoke: all executed commands, stdout, exit codes,
  artifact hashes: `backends/docker/uet_htsim_s2.log` (S2)
  and `backends/docker/uet_htsim_s1.log` (S1 build).
- Finalization: every §2.1 command re-executed
  verbatim with cross-checks against the earlier artifacts:
  `backends/docker/uet_htsim_s4.log` — container stdout
  byte-identical to the real-run fixture
  `tests/fixtures/uet_htsim/w1_smoke_8rank_6op_stdout.txt` (sha256
  `87f6f878…`), all six trace sha256s equal to RunRecord
  `fbb46d16…`, byte-identical compile regeneration (0 modified files),
  idempotent evidence-store re-put.
- Pin metadata and license: `backends/pins/uet-htsim.md`,
  `backends/pins/uet-htsim.LICENSE-Transport-WG.txt`.
- Boundaries respected: no remote
  git/registry operations, nothing installed on the host, pinned commit only.
