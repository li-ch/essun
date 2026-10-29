# essun / D-028 — ASTRA-sim csg-htsim (packet-level) toolchain image
#
# Purpose: build the csg-htsim frontend of the SAME pinned ASTRA-sim commit
# inside Docker, stepping up from the analytical frontend image
# (essun/astra-sim-analytical:s1, D-027) to a packet/flow-level network
# model (Broadcom/csg-htsim, TCP-style; NOT UET — see backends/pins/astra-sim.md).
#
# Upstream pins (see backends/pins/astra-sim.md):
#   astra-sim  https://github.com/astra-sim/astra-sim.git
#              commit 4ce9ecfe746a3ee5fe47559a11d91644d641fa7f  (2026-09-19,
#              ASTRA-sim 2.0) — identical to the analytical image
#   csg-htsim  submodule extern/network_backend/csg-htsim ->
#              https://github.com/Broadcom/csg-htsim.git
#              commit 67cbbbb1cccdbddc400803414127d044ecd55290 (2023-12-11,
#              recorded in the pin's .gitmodules state; BSD-2-Clause,
#              LICENSE sha256 c550c0ba42ecce0a5a55af4faaf4be1cfd6d7f3410feb088cca23955b6978585,
#              copied to backends/pins/csg-htsim.LICENSE; notice retention:
#              the license file stays in the cloned tree)
#
# Documented build path (per the pinned tree):
#   build/astra_htsim/build.sh — compiles the chakra et_def.proto via protoc,
#   applies build/astra_htsim/htsim_astrasim.patch to the csg-htsim submodule
#   (patch -p1 --forward; verified to apply cleanly at the pinned commit:
#   dry-run exit 0 on sim/tcp.cpp + sim/tcp.h), then cmake+build in
#   build/astra_htsim/build. The frontend (astra-sim/network_frontend/htsim/
#   CMakeLists.txt) links the analytical congestion-unaware backend library,
#   compiles 4 csg-htsim datacenter sources itself, and builds libhtsim.a via
#   plain `make` in extern/network_backend/csg-htsim/sim (Makefile needs only
#   g++/make/ar — no bison/flex at this pin). Result binary:
#   build/astra_htsim/build/bin/AstraSim_HTSim (consumed by
#   examples/run_scripts/htsim/run_htsim.sh).
#
# Deltas vs backends/docker/astra-sim.Dockerfile (the analytical mirror):
#   + apt `patch` (build.sh patch_htsim; absent from the analytical image)
#   + submodule extern/network_backend/csg-htsim initialized
#   + build entry point build/astra_htsim/build.sh (no -t flag) instead of
#     build/astra_analytical/build.sh -t congestion_unaware
#   + verify step targets AstraSim_HTSim (+ libhtsim.a hash: the patched
#     tcp.o lives inside it, so the hash proves the patch is in the build)
#
# Base image: ubuntu:22.04 (jammy), pinned by canonical multi-arch OCI index
# digest — identical digest to the analytical and uet-htsim S1 images, already
# verified on this host (Hub direct times out; the digest was pulled via
# docker.m.daocloud.io and cross-checked against docker.1ms.run).
#   ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b
#
# Toolchain versions (same as the analytical image; jammy apt unless noted):
#   gcc/g++ 11.4.0, make 4.3, cmake 3.22.1 (top-level CMakeLists needs >= 3.22,
#   build/astra_htsim needs >= 3.15), boost 1.74.0 (libboost-dev,
#   libboost-program-options-dev — the htsim frontend links the analytical
#   backend, which needs boost), zlib 1.2.11 (zlib1g-dev, chakra protoio),
#   git 2.34.1, patch 2.7.1 (NEW for this image), abseil-cpp 20240722.0 and
#   protobuf 29.0 (protoc 29.0) built from source, yaml-cpp a83cd31 via
#   FetchContent at configure time. csg-htsim itself declares "no dependencies"
#   (README) and needs no extra packages.
#
# D-032/4a DEVIATION FROM PIN (recorded in backends/pins/astra-sim.md): one
# source line of the pinned ASTRA-sim tree is modified in-image before the
# build — srand(time(NULL)) -> env-seeded srand (ESSUN_SEED, default 1) at
# astra-sim/network_frontend/htsim/proto/HTSimProtoTcp.cc:102. Reason: at the
# pin the only live RNG seeding in the compiled path is the wall clock, so
# identical runs differ (runbook §6). No seed flag exists on this path (the
# standalone csg-htsim mains accept -seed, but the ASTRA-sim integration
# parses no such sub-flag). csg-htsim sim/rng.cpp overrides srand/rand/
# random/srandom with one mt19937 engine, so this call site seeds every RNG
# consumer in the binary. Default 1, not 0: seed 0 deterministically trips
# an upstream assertion on the documented example (HTSimSession.cc:143
# "Cannot find send_event in sent_hash"; runbook §6) while seed 1 completes
# cleanly.
# The unmodified image remains essun/astra-csg-htsim:s1.
#
# Build (from the repo root):
#   docker build -f backends/docker/astra-csg-htsim.Dockerfile -t essun/astra-csg-htsim:s1-seeded backends/docker
FROM ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b

ENV DEBIAN_FRONTEND=noninteractive

### System toolchain (apt, jammy versions in comment block above) ###
RUN apt-get update && apt-get install -y --no-install-recommends \
        coreutils wget ca-certificates git \
        gcc g++ make cmake \
        libboost-dev libboost-program-options-dev \
        zlib1g-dev \
        patch \
    && rm -rf /var/lib/apt/lists/*

### Abseil 20240722.0 (protobuf dependency; from source as in upstream Dockerfile) ###
ARG ABSL_VER=20240722.0
WORKDIR /opt
RUN wget -q "https://github.com/abseil/abseil-cpp/releases/download/${ABSL_VER}/abseil-cpp-${ABSL_VER}.tar.gz" \
    && tar -xf "abseil-cpp-${ABSL_VER}.tar.gz" \
    && rm "abseil-cpp-${ABSL_VER}.tar.gz"
WORKDIR /opt/abseil-cpp-${ABSL_VER}/build
RUN cmake .. \
        -DCMAKE_CXX_STANDARD=14 \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="/opt/abseil-cpp-${ABSL_VER}/install" \
    && cmake --build . --target install --config Release --parallel "$(nproc)"
ENV absl_DIR="/opt/abseil-cpp-${ABSL_VER}/install"

### Protobuf 29.0 (= v5.29.0; from source, provides protoc + CONFIG package) ###
ARG PROTOBUF_VER=29.0
WORKDIR /opt
RUN wget -q "https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOBUF_VER}/protobuf-${PROTOBUF_VER}.tar.gz" \
    && tar -xf "protobuf-${PROTOBUF_VER}.tar.gz" \
    && rm "protobuf-${PROTOBUF_VER}.tar.gz"
WORKDIR /opt/protobuf-${PROTOBUF_VER}/build
RUN cmake .. \
        -DCMAKE_CXX_STANDARD=14 \
        -DCMAKE_BUILD_TYPE=Release \
        -Dprotobuf_BUILD_TESTS=OFF \
        -Dprotobuf_ABSL_PROVIDER=package \
        -DCMAKE_INSTALL_PREFIX="/opt/protobuf-${PROTOBUF_VER}/install" \
    && cmake --build . --target install --config Release --parallel "$(nproc)"
ENV PATH="/opt/protobuf-${PROTOBUF_VER}/install/bin:$PATH"
ENV protobuf_DIR="/opt/protobuf-${PROTOBUF_VER}/install"
# Tells astra-sim's top-level CMakeLists to use find_package(protobuf CONFIG REQUIRED)
ENV PROTOBUF_FROM_SOURCE="True"

### Clone ASTRA-sim at the pinned commit (+ the 6 submodules this build compiles) ###
# csg-htsim is the new one vs the analytical image; the analytical network
# backend is still required (the htsim frontend links
# Analytical_Congestion_Unaware); ns-3 stays uninitialized.
ARG ASTRA_SIM_COMMIT=4ce9ecfe746a3ee5fe47559a11d91644d641fa7f
WORKDIR /opt/astra-sim
RUN git clone https://github.com/astra-sim/astra-sim.git . \
    && git checkout --detach "${ASTRA_SIM_COMMIT}" \
    && git submodule update --init --recursive \
        extern/graph_frontend/chakra \
        extern/network_backend/analytical \
        extern/remote_memory_backend/analytical \
        extern/helper/fmt \
        extern/helper/spdlog \
        extern/network_backend/csg-htsim \
    && echo "=== pin check ===" \
    && git rev-parse HEAD \
    && git submodule status \
    && echo "=== csg-htsim license (BSD-2, stays in tree) ===" \
    && sha256sum extern/network_backend/csg-htsim/LICENSE

### D-032/4a: deterministic RNG seeding (deviation from pin — see header) ###
# Replaces the single wall-clock seeding site of the compiled integration
# path: srand(time(NULL)) at HTSimProtoTcp.cc:102. getenv/atoi need no new
# include (atoi is already used in the same TU, lines 70/73). The trailing
# grep makes the build FAIL LOUDLY if the sed does not apply (line moved or
# already patched upstream).
RUN sed -i 's/srand(time(NULL));/{ const char* s = getenv("ESSUN_SEED"); srand(s ? atoi(s) : 1); }/' \
        /opt/astra-sim/astra-sim/network_frontend/htsim/proto/HTSimProtoTcp.cc \
    && grep -n "ESSUN_SEED" /opt/astra-sim/astra-sim/network_frontend/htsim/proto/HTSimProtoTcp.cc \
    && sed -n '100,104p' /opt/astra-sim/astra-sim/network_frontend/htsim/proto/HTSimProtoTcp.cc

### Build via the documented entry point: build/astra_htsim/build.sh ###
# (build.sh: protoc et_def.proto -> patch htsim_astrasim.patch onto csg-htsim
#  -> cmake configure + parallel build; caps itself at 16 threads)
WORKDIR /opt/astra-sim/build/astra_htsim
RUN ./build.sh

### Verify the binary exists (S1 PASS bar) and hash build evidence ###
# - AstraSim_HTSim: the deliverable binary (path per the frontend CMake
#   RUNTIME_OUTPUT_DIRECTORY ../bin/ and examples/run_scripts/htsim/run_htsim.sh).
# - extern/network_backend/csg-htsim/sim/libhtsim.a: contains the patched
#   tcp.o; its hash + the grep marker prove the integration patch is compiled in.
ENV ASTRA_HTSIM_BIN=/opt/astra-sim/build/astra_htsim/build/bin/AstraSim_HTSim
RUN test -x "${ASTRA_HTSIM_BIN}" \
    && sha256sum "${ASTRA_HTSIM_BIN}" \
    && sha256sum /opt/astra-sim/extern/network_backend/csg-htsim/sim/libhtsim.a \
    && grep -c "astrasim_flow_finish_send_cb" /opt/astra-sim/extern/network_backend/csg-htsim/sim/tcp.h
RUN ls -l /opt/astra-sim/build/astra_htsim/build/bin/ \
    && ls -l /opt/astra-sim/extern/network_backend/csg-htsim/sim/libhtsim.a

WORKDIR /opt/astra-sim
