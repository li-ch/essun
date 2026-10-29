# ASTRA-sim pin — capability matrix

Status: `IMPLEMENTED_UNVERIFIED` (pin recorded; host build attempted, gap classified — see
`astra-sim-build.log`). This document is the input to the backend-selection decision
(see `backend-selection-draft.md`); it is not an accepted decision.

## Pin

| Field | Value |
|---|---|
| Repository | `https://github.com/astra-sim/astra-sim.git` |
| Pinned commit | **`4ce9ecfe746a3ee5fe47559a11d91644d641fa7f`** |
| Commit date / subject | 2026-09-19, "Fix NS-3 receive tracking for concurrent receives (#383)" |
| Describe string | `tutorial-micro2024-ns3fix250204-101-g4ce9ecf` |
| Upstream version | ASTRA-sim **2.0** ("∫", per `README.md`) |
| Local checkout | `backends/astra-sim` (untracked; pinned by this hash) |
| License | **MIT** — `LICENSE` (Copyright (c) 2023 Georgia Institute of Technology; Facebook Inc), copied to `backends/pins/astra-sim.LICENSE` |
| LICENSE sha256 | `6bdafa9b438d97b3d440653340f18b09088a401e63ccf994e98b32edc1ba9026` |

Hash cross-reference: every claim below cites a path (and line where useful) inside the
checkout of commit `4ce9ecfe746a3ee5fe47559a11d91644d641fa7f`. No claim is derived from
sources outside the clone's public README/docs and its tracked files.

## Capability matrix (evidence-anchored to the pinned tree)

### Supported collectives

- Collective operations (`astra-sim/common/Common.hh:43`, enum `ComType`): `Reduce_Scatter`,
  `All_Gather`, `All_Reduce`, `All_to_All`, `All_Reduce_All_to_All`.
- Native algorithms (`astra-sim/system/astraccl/native_collectives/collective_algorithm/`):
  `Ring`, `HalvingDoubling` (recursive halving–doubling), `DoubleBinaryTreeAllReduce`, `AllToAll`.
- Logical topologies (`.../logical_topology/`): Ring, BinaryTree, DoubleBinaryTree,
  LocalRingGlobalBinaryTree, Torus3D, LocalRingNodeA2AGlobalDBT, GeneralComplexTopology.
- Custom/user-supplied collectives: `.../custom_collectives/CustomAlgorithm.{cc,hh}` plus
  Chakra execution traces as workload input (`README.md`: "ASTRA-sim accepts MLCommons
  Chakra Execution Traces as workload-layer inputs").
- Scheduling knobs (`Common.hh:54-73`): blocking/non-blocking collectives, FIFO/LIFO/EXPLICIT
  scheduling, intra/inter-dimension scheduling, injection policies.
- Compute kernels (`astra-sim/common/AstraComputeAPI.hh:19-20`): GEMM, Batch_GEMM, Softmax,
  LLM_RMSNorm, LLM_Residual_Addition, Llama_Attn, Llama_MLP; phases FWD/BCKWD/
  **INFERENCE_TOKENGEN / INFERENCE_PREFILL** — directly relevant to the W1 decode /
  W2 prefill workloads.

### Integrated network backends

Declared as submodules (`.gitmodules`) with build targets under `build/`; frontend adapters
under `astra-sim/network_frontend/{analytical,htsim,ns3}`; `BackendType` enum also lists
Garnet (`astra-sim/common/AstraNetworkAPI.hh:15`):

| Backend | Submodule / source | Pin recorded in `.gitmodules` state | Notes |
|---|---|---|---|
| Analytical | `extern/network_backend/analytical` → `astra-sim/astra-network-analytical` | `e8c5119f8d5a690b955e25c37a74359f23ac64cc` | congestion-aware and congestion-unaware variants (`build/astra_analytical/build.sh`) |
| HTSim | `extern/network_backend/csg-htsim` → `Broadcom/csg-htsim` | `67cbbbb1cccdbddc400803414127d044ecd55290` | integrated via `build/astra_htsim/htsim_astrasim.patch` (adds flow-finish callbacks to `sim/tcp.cpp`; TCP flow-level, not UET) |
| ns-3 | `extern/network_backend/ns-3` → `astra-sim/astra-network-ns3` | `f764bed27630ee45368c03e22e4f952b69fab30a` | HEAD commit fixes NS-3 receive tracking |
| Garnet | `build/astra_garnet/` | — | build target present; not evaluated here |

Note the lineage distinction: the HTSim that ASTRA-sim integrates is **Broadcom/csg-htsim**
(TCP-style flow simulator), *not* the UEC congestion-management simulator
(`ultraethernet/uet-htsim`, see `uet-htsim.md` in this directory).

### Memory / remote-memory backends

- Remote memory backend: analytical only (`extern/remote_memory_backend/analytical` →
  `astra-sim/astra-memory-analytical`, pin `641cce854d256bfd288b1de9607b6757313363f9`).
- Intra-node memory event model exists in the system layer (`MemBus.cc`, `MemMovRequest.cc`,
  `UsageTracker.cc` under `astra-sim/system/`).

### Chakra support

- `extern/graph_frontend/chakra` → `mlcommons/chakra` (pin `0e3cd40c569f0a4cacb6d961bb56be53407abd2f`),
  protobuf schema `schema/protobuf/et_def.proto`, feeder v3 compiled into the library
  (`CMakeLists.txt:62-64`); workload traces are Chakra ETs per `README.md`.

### Build system

- CMake ≥ 3.22 top-level (`CMakeLists.txt:9`), C++17, ≥ 3.15 per-frontend trees; `build.sh`
  wrappers per frontend are the documented entry points.
- Dependencies (top-level `CMakeLists.txt`, `build/*/build.sh`, `Dockerfile`): fmt + spdlog
  (vendored submodules), yaml-cpp (**fetched from network at configure time**, `CMakeLists.txt:29-34`),
  protobuf (REQUIRED, with `protoc` needed pre-cmake to compile Chakra `et_def.proto`),
  boost (per `Dockerfile`), OpenMPI + ns-3 for the ns-3 target.
- Documented container path: `Dockerfile` (ubuntu:22.04; abseil 20240722.0 + protobuf 29.0
  built from source; `utils/build_docker_image.sh`).
- Submodules required at build time (7 declared in `.gitmodules`).

## What ASTRA-sim does NOT provide for Scale-up semantics

Stated as gaps for later planning; each is an absence of evidence in the pinned tree's
public docs, not a claim about unreleased code:

1. **Scale-up memory semantics**: no UALink/CXL/UnifiedBus-style load-store or memory-side
   semantics; the only remote-memory backend is analytical. Memory semantics beyond
   intra-node MemBus modeling would have to come from essun's SpecIR layer, not ASTRA-sim.
2. **FLIT-level simulation**: nothing FLIT/credit-lane level is documented in-tree; the
   analytical backend is bandwidth/latency/dimension-based and the csg-htsim path is a
   packet/flow-level TCP-style simulator (the integration patch touches `sim/tcp.cpp` only).
3. **UEC/UET transport semantics**: the integrated HTSim variant (csg-htsim) does not model
   UET congestion management (receiver credits, NACK/pull, per the UET spec); those live in
   the separately-pinned `ultraethernet/uet-htsim`. Bridging ASTRA-sim workloads to UET CMS
   is unsolved and must be an explicit scope decision for the integration step.
4. **Scale-up fabric topologies**: logical collective topologies (ring/tree/torus) exist, but
   scale-out network topology modeling is delegated to the chosen network backend submodule
   (not initialized at this pin); no all-to-all/NVLink-like scale-up fabric is documented.
5. **Standard-derived values**: no UEC/UALink normative parameters are encoded; essun rule 4
   (separate standard targets vs modeling assumptions, free parameters where normative values
   are unavailable) applies unchanged.

## Vertical-slice fit (VS-2)

Fits: collective-level DES with an analytical network (congestion-unaware ≈ the L0 backend's
domain), Chakra-trace or built-in workloads, LLM tokengen/prefill compute phases, explicit
`AstraNetworkAPI` seam for a `BackendAdapter`. The smallest verified slice remains
"ASTRA-sim analytical frontend on one W1 Dense TP Decode manifest, cross-run against L0"
— blocked on the host build gap below, not on capability.

## Build status at this pin

`BUILD_GAP` — see `astra-sim-build.log` (this directory). One build attempted from the
documented entry point `build/astra_analytical/build.sh` and one direct `cmake` configure
into `build-local/`; both failed on host-side toolchain absence (`nproc`, `protoc`, `cmake`
all missing on this macOS host; no sudo/brew permitted). Cause classification paragraph is
in the log and in `backend-selection-draft.md`.

Submodules intentionally left uninitialized at this pin (recorded states above are from
`git submodule status`); initializing them cannot remove the host-side blockers.

## Deviations from pin (csg-htsim determinism patch)

One source line of the pinned tree is modified at image-build time; the pin
record above still describes the pristine upstream commit `4ce9ecf…`.

- **What changed:** `astra-sim/network_frontend/htsim/proto/HTSimProtoTcp.cc:102`
  `srand(time(NULL));` →
  `{ const char* s = getenv("ESSUN_SEED"); srand(s ? atoi(s) : 1); }`
  applied by `sed` in `backends/docker/astra-csg-htsim.Dockerfile` (layer
  between the clone and `build.sh`; a trailing grep fails the build if the
  sed stops matching upstream). Nothing else in the pinned tree is touched:
  the resulting image's `extern/network_backend/csg-htsim/sim/libhtsim.a`
  hash `f9271372054e61dfee4e65caef2865ebd8bd1feb6fc823d0170a8871a5bee877`
  is bit-identical to the unpatched `s1` image's.
- **Why:** at the pin, that line is the only live RNG seeding in the compiled
  integration path, and it uses the wall clock, so identical runs differ
  (csg runbook §6; every Wall/Comm value, `logout.dat`, `log.log` differed
  across two fresh containers in the 2026-10-27 nightly). No seed flag
  exists on this path: the `--htsim_opts` loop (`HTSimProtoTcp.cc:63-101`)
  parses `-o/-sub/-nodes/-topo` and coupling algorithms only — the
  standalone csg-htsim `datacenter/main_*.cpp` entry points accept `-seed`
  but are not compiled into `AstraSim_HTSim`. `sim/rng.cpp` overrides
  `srand/rand/random/srandom` with one shared `mt19937`, so this single
  call site seeds every RNG consumer in the binary.
- **Default 1, not 0:** seed 0 deterministically aborts the documented
  example on an upstream assertion (`HTSimSession.cc:143` "Cannot find
  send_event in sent_hash"); seeds 42 (same assertion) and 2026
  (`eventlist.cpp:69` `when>=now()`) also abort; seeds 1, 2, 13 complete.
  These are latent upstream bugs exposed by fixing the seed, not effects of
  the patch.
- **Scope/evidence:** image `essun/astra-csg-htsim:s1-seeded`
  (ID `sha256:6cc48e30efa8b6829a7d7da62e30e49678c7c8b7ee0f995af5fe397e4702aa2f`,
  binary sha256 `a36f981cb91992a02fd59d6216ab88a9fc52458ceb51c9d43fdf798733bb8a94`);
  the unpatched image remains tagged `essun/astra-csg-htsim:s1`. Two-run
  byte-identity at seeds 1 and 2:
  `backends/docker/astra_csg_d032_smoke.log`. The analytical-frontend image
  is not affected by this deviation.
