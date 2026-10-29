# UET-HTSim pin — UEC congestion management simulator

Status: `IMPLEMENTED_UNVERIFIED` (repo identified and pinned; not built — same host
toolchain gap as ASTRA-sim, cmake missing).

## Identification (step 4 of the P1 prompt)

The canonical repository was confidently identified by web search:

- **Canonical: `https://github.com/ultraethernet/uet-htsim`** — Ultra Ethernet Consortium
  GitHub org; self-described as "dedicated to the Congestion Management Group"; HTSim-based
  UEC transport layer simulator. Verified public on 2026-10-26.
- Candidates considered and rejected as canonical:
  - `https://github.com/spcl/HTSIM` — ETH Zürich SPCL fork of the official UEC repository
    (public research fork with extra features); upstream research lineage, not the UEC WG repo.
  - `https://github.com/Broadcom/csg-htsim` — Broadcom's HTSim variant; this is the fork
    **ASTRA-sim actually integrates** (submodule pin `67cbbbb1...`), but it is not the UET
    CMS simulator.

## Pin

| Field | Value |
|---|---|
| Repository | `https://github.com/ultraethernet/uet-htsim.git` |
| Pinned commit | **`65ea315b25725df9791a5b93b61cbd6938cba0a8`** (shallow clone, default branch `main`) |
| Commit date / subject | 2026-02-11, "Added Permutation+Incast experiment files for 800Gbps (#142)" |
| Local checkout | `backends/uet-htsim` (untracked; pinned by this hash) |
| License | **BSD-2-Clause** via `LICENSE-Transport-WG.txt` (Copyright (c) 2026 Ultra Ethernet Consortium), copied to `backends/pins/uet-htsim.LICENSE-Transport-WG.txt` |
| License sha256 | `5b9f9e790ae7b60990be7bec176cf2f454e8d366e040b29a65f8bcf6c6c4781b` |

## Scope, from its README only

- Purpose: "support the transport layer working group's work on congestion control
  mechanisms"; platform for continuous implementation/development of the UEC transport
  layer; run topologies/scenarios, estimate throughput/latency (`README.md:19-24`).
- **Explicit non-goals** (`README.md:28-33`): "not a complete implementation of the UEC
  transport specification"; "not a standard ... not part of the official UEC standards
  release"; "There might be discrepancies between the UEC CMS specification and the
  simulator. Only the official CMS specification is significant."
- Build/run (`htsim/README.md`): C++ with "no major dependencies", g++/clang on macOS or
  Linux, **cmake** `-S . -B build`; UEC simulation binary `htsim_uec` driven by traffic
  matrices (`sim/datacenter/connection_matrices`); validation suite
  `sim/datacenter/validation/validate_all.py` + `sim/datacenter/commit_check.sh`; flow output
  includes UET CMS signals (per-flow `fair_inc/prop_inc/fast_inc/eta_inc`, NACK/Pull counters).
- Lineage (`htsim/README.md:3-5`): based on the open-source htsim network simulator
  (Handley/Raiciu lineage; extended for MPTCP, NDP, EQDS, DCTCP/DCQCN, Swift, HPCC, RoCE/PFC).
- Contribution policy: DCO 1.1, contributions from UEC members only (`README.md:4-11`).
  **License-review note:** BSD-2-Clause permits use/modification/redistribution
  with notice retention; the membership restriction covers *contributions*, not use — recorded
  here for the source-registry record.

## Relevance and gap

This is the repository that models UET congestion management (receiver-credit-based
congestion control). ASTRA-sim's integrated HTSim (csg-htsim) does not provide these
semantics; using UET CMS inside the ASTRA-sim DES path later requires either adapting this
fork behind `AstraNetworkAPI` or an explicit decision to defer UET semantics. Not built on
this host (cmake missing; same classification as `astra-sim-build.log`).
