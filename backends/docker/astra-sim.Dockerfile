# essun / D-027 — ASTRA-sim analytical (congestion-unaware) toolchain image
#
# Purpose: build the pinned ASTRA-sim commit inside Docker so T022 has a
# runnable `AstraSim_Analytical_Congestion_Unaware` backend (D-028 target).
#
# Upstream ASTRA-sim pin (see backends/pins/astra-sim.md):
#   repo   https://github.com/astra-sim/astra-sim.git
#   commit 4ce9ecfe746a3ee5fe47559a11d91644d641fa7f  (2026-09-19, ASTRA-sim 2.0)
#   license MIT
#
# Base image: ubuntu:22.04 (jammy), pinned by canonical multi-arch OCI index
# digest (same digest served by Docker Hub and by the docker.m.daocloud.io /
# docker.1ms.run mirrors used as transport on this host; Hub direct times out).
#   ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b
# Resolves to linux/arm64 member sha256:a8fb2ba881817... on this arm64 host.
#
# Toolchain versions (matching upstream astra-sim/Dockerfile at the pin):
#   gcc/g++         11.4.0   (ubuntu jammy apt)
#   make            4.3      (ubuntu jammy apt)
#   cmake           3.22.1   (ubuntu jammy apt; top-level CMakeLists needs >= 3.22)
#   boost           1.74.0   (ubuntu jammy apt; libboost-dev, libboost-program-options-dev)
#   zlib            1.2.11   (ubuntu jammy apt; zlib1g-dev — needed by chakra
#                             protoio.hh -> protobuf gzip_stream.h -> <zlib.h>;
#                             missing on attempt 1, see backends/docker/build_s1.log)
#   git             2.34.1   (ubuntu jammy apt)
#   abseil-cpp      20240722.0  (built from source, like upstream Dockerfile)
#   protobuf        29.0 (=v5.29.0, libprotobuf 5.29.0, protoc 29.0; built from source)
#   yaml-cpp        a83cd31  (fetched by top-level CMakeLists FetchContent at configure time)
# Plus git submodules at their pinned commits (recorded in .gitmodules of the pin):
#   chakra, astra-network-analytical, astra-memory-analytical, fmt, spdlog
#   (csg-htsim and ns-3 submodules are NOT initialized: not compiled by the
#    analytical target; keeps the image build small.)
# cxxopts/json/spdlog_setup are vendored in-tree (regular dirs, not submodules).
#
# Build (from the repo root):
#   docker build -f backends/docker/astra-sim.Dockerfile -t essun/astra-sim-analytical:s1 backends/docker
FROM ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a7f9448b2c77a77c9b

ENV DEBIAN_FRONTEND=noninteractive

### System toolchain (apt, jammy versions in comment block above) ###
RUN apt-get update && apt-get install -y --no-install-recommends \
        coreutils wget ca-certificates git \
        gcc g++ make cmake \
        libboost-dev libboost-program-options-dev \
        zlib1g-dev \
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

### Clone ASTRA-sim at the pinned commit (+ the 5 submodules the analytical build compiles) ###
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
    && echo "=== pin check ===" \
    && git rev-parse HEAD \
    && git submodule status

### Build the smallest documented analytical target: congestion_unaware ###
# Documented entry point: build/astra_analytical/build.sh -t congestion_unaware
# (upstream run script examples/run_scripts/analytical/congestion_unaware/*.sh uses it)
WORKDIR /opt/astra-sim/build/astra_analytical
RUN ./build.sh -t congestion_unaware

### Verify the binary exists (S1 PASS bar) and record its hash for the log ###
ENV ASTRA_ANALYTICAL_BIN=/opt/astra-sim/build/astra_analytical/build/bin/AstraSim_Analytical_Congestion_Unaware
RUN test -x "${ASTRA_ANALYTICAL_BIN}" \
    && sha256sum "${ASTRA_ANALYTICAL_BIN}" \
    && ls -l build/AnalyticalAstra/bin/AnalyticalAstra

WORKDIR /opt/astra-sim
