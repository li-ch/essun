# essun / OD-002 — UET-HTSim (UEC congestion management) toolchain image
#
# Purpose: build the pinned uet-htsim commit inside Docker so OD-002 has a
# runnable `htsim_uec` third-backend candidate (pin record:
# backends/pins/uet-htsim.md; mirrors the proven ASTRA-sim ladder,
# backends/docker/astra-sim.Dockerfile).
#
# Upstream uet-htsim pin (see backends/pins/uet-htsim.md):
#   repo   https://github.com/ultraethernet/uet-htsim.git
#   commit 65ea315b25725df9791a5b93b61cbd6938cba0a8  (2026-02-11,
#          "Added Permutation+Incast experiment files for 800Gbps (#142)")
#   license BSD-2-Clause via LICENSE-Transport-WG.txt (Copyright (c) 2026
#          Ultra Ethernet Consortium),
#          sha256 5b9f9e790ae7b60990be7bec176cf2f454e8d366e040b29a65f8bcf6c6c4781b
#          (notice retention: the license file stays in the cloned tree)
#
# Base image: ubuntu:22.04 (jammy), pinned by canonical multi-arch OCI index
# digest — identical digest to the ASTRA-sim S1 image, already verified on
# this host (Hub direct times out; pulled via docker.m.daocloud.io and
# cross-checked against docker.1ms.run, so the pin is mirror-independent).
#   ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b
#
# Toolchain versions (upstream htsim/README.md: C++ with "no major
# dependencies", g++/clang on macOS or Linux, built with cmake from sim/):
#   gcc/g++  11.4.0  (ubuntu jammy apt)
#   make     4.3     (ubuntu jammy apt)
#   cmake    3.22.1  (ubuntu jammy apt; htsim/sim/CMakeLists.txt needs >= 3.16)
#   git      2.34.1  (ubuntu jammy apt)
#   python3  3.10.6  (ubuntu jammy apt; NOT needed to build — included for the
#                     S2 smoke/validation scripts, e.g. validate_all.py)
# No git submodules exist at this pin. ENABLE_TESTS stays OFF (default) so
# the build does NOT FetchContent googletest. matplotlib/pandas/seaborn
# (requirements.txt) are NOT installed: only the validation plot pipeline
# needs them, not this build or the documented htsim_uec example runs.
#
# Build (from the repo root):
#   docker build -f backends/docker/uet-htsim.Dockerfile -t essun/uet-htsim:s1 backends/docker
FROM ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b

ENV DEBIAN_FRONTEND=noninteractive

### System toolchain (apt, jammy versions in comment block above) ###
RUN apt-get update && apt-get install -y --no-install-recommends \
        coreutils ca-certificates git \
        gcc g++ make cmake \
        python3 \
    && rm -rf /var/lib/apt/lists/*

### Clone uet-htsim at the pinned commit (no submodules at this pin) ###
ARG UET_HTSIM_COMMIT=65ea315b25725df9791a5b93b61cbd6938cba0a8
WORKDIR /opt/uet-htsim
RUN git clone https://github.com/ultraethernet/uet-htsim.git . \
    && git checkout --detach "${UET_HTSIM_COMMIT}" \
    && echo "=== pin check ===" \
    && git rev-parse HEAD \
    && sha256sum LICENSE-Transport-WG.txt

### Build per the documented path (htsim/README.md "Building the project"):
### from htsim/sim, `cmake -S . -B build` then `cmake --build build --parallel`.
### The default target set builds htsim_uec (the only datacenter executable
### not EXCLUDE_FROM_ALL), the static libs htsim + htsim_dc, and parse_output.
WORKDIR /opt/uet-htsim/htsim/sim
RUN cmake -S . -B build \
    && cmake --build build --parallel "$(nproc)"

### Verify the binary exists (S1 PASS bar) and record its hash for the log.
### Real binary: build/datacenter/htsim_uec. The CMake post-build step also
### recreates the upstream-documented symlink sim/datacenter/htsim_uec
### (htsim/README.md: "The UEC simulation binary is called htsim_uec and is
### located in sim/datacenter/htsim_uec").
ENV HTSIM_UEC_BIN=/opt/uet-htsim/htsim/sim/build/datacenter/htsim_uec
RUN test -x "${HTSIM_UEC_BIN}" \
    && sha256sum "${HTSIM_UEC_BIN}" \
    && ls -l datacenter/htsim_uec build/datacenter/htsim_uec build/parse_output

WORKDIR /opt/uet-htsim/htsim/sim
