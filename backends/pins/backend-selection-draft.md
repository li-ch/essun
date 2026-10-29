# Backend selection draft (DRAFT — NOT ACCEPTED)

> Owner-gated decision record, kept in draft form. This is a **draft
> evaluation**; acceptance is the owner's call (Technical lead role).
> Evidence label for all content herein: `IMPLEMENTED_UNVERIFIED`.

**Decision slot:** "Initial discrete-event backend and exact pinned commit"
(guidance: "Evaluate ASTRA-sim/HTsim first"; choose the smallest verified vertical slice).

**Drafted:** 2026-10-26. **Fuels:** the DES integration step and, through it,
the first cross-backend disagreement milestone.

## Recommendation

Adopt **ASTRA-sim @ `4ce9ecfe746a3ee5fe47559a11d91644d641fa7f`** (MIT) as the initial
discrete-event backend for VS-2, via the **analytical frontend**
(`AstraSim_Analytical_Congestion_Unaware`) as the smallest verified slice, with the
**csg-htsim frontend** (`Broadcom/csg-htsim` @ `67cbbbb1cccdbddc400803414127d044ecd55290`,
integrated by the in-tree `htsim_astrasim.patch`) as the packet-level step-up once the host
build gap is closed. Additionally pin **`ultraethernet/uet-htsim` @
`65ea315b25725df9791a5b93b61cbd6938cba0a8`** (BSD-2-Clause) as the UET congestion-management
reference simulator — separate from the ASTRA-sim DES path until the adapter
strategy is decided.

## Evidence

- Pin + license + evidence-anchored capability matrix: `backends/pins/astra-sim.md`,
  `backends/pins/astra-sim.LICENSE` (MIT, sha256 `6bdafa9b...`).
- UET-HTSim identification + pin: `backends/pins/uet-htsim.md`,
  `backends/pins/uet-htsim.LICENSE-Transport-WG.txt` (BSD-2-Clause, sha256 `5b9f9e79...`).
- Build attempt: `backends/pins/astra-sim-build.log` → **BUILD_GAP** (acceptable under the
  pin bar: PINNED + BUILD_GAP).

## Why this backend (capability fit)

1. Collective-level DES matching VS-2's observables (W1 Dense TP Decode): ComType ops,
   ring/halving-doubling/double-binary-tree algorithms, LLM compute kernels with
   INFERENCE_TOKENGEN/PREFILL phases (`astra-sim/common/AstraComputeAPI.hh:19-20`).
2. Chakra trace input aligns with the workload layer.
3. Clean `AstraNetworkAPI` seam for a essun `BackendAdapter` with pluggable network
   backends (analytical / csg-htsim / ns-3).
4. MIT license — no ingestion constraints (license-review rule satisfied; uet-htsim
   BSD-2-Clause also clean, contribution-side UEC-membership restriction recorded, use
   unrestricted).

## Known gaps carried into the integration step (not blockers for this decision)

- **Host build gap** (`astra-sim-build.log`): documented entry point
  `build/astra_analytical/build.sh` and direct `cmake` both fail — host lacks `nproc`
  (macOS), `protoc`, and `cmake` ≥ 3.22 (plus boost; submodules uninitialized; yaml-cpp is
  fetched from the network at configure time). Cause classification: **environment/toolchain
  gap, not a defect in the pinned commit** — the failure is before any compilation of
  ASTRA-sim code; no in-tree non-cmake build path exists (Dockerfile path needs network +
  docker). Remediation options (owner choice, interacts with the hardware decision):
  (a) build in the provided Docker container, (b) user-local cmake/protobuf/boost installs
  (no sudo needed), (c) designated Linux build host.
- **UET semantics are absent from the ASTRA-sim DES path**: csg-htsim integration is
  TCP-flow-level (patch touches `sim/tcp.cpp` only); UET CMS lives in `ultraethernet/uet-htsim`.
  The integration step must make unsupported capabilities fail explicitly (per its
  acceptance criteria).
- **No scale-up memory semantics / FLITs / credits** in ASTRA-sim — see "What ASTRA-sim does
  NOT provide" in `backends/pins/astra-sim.md`; these stay in essun's SpecIR/L0 domain for
  VS-2 and flag the validity-domain boundary for paper claims.

## Consequences if accepted

- The integration step is unblocked modulo the build gap; the first cross-backend
  disagreement milestone can be scheduled once a build environment exists.
- The source registry should gain rows for both pins (provenance: URLs, hashes, licenses).
- Rejected alternatives: NS-3 frontend first (heavier dependency chain, no collective
  layer advantage), custom DES (reduces to rebuilding ASTRA-sim's value), spcl/HTSIM as the
  UET CMS source (fork of the canonical repo; canonical preferred).
