# Calibration anchor list — STAGING

Status: **PROPOSED** (staging document; accepted rows are integrated into the anchor registry by an explicit decision).
Date: 2026-10-27.

Purpose: candidate external, published, citable measurements that can calibrate the
observables (O-CCT; O-CONSERVATION is algebraic and not calibratable) and the L0 model
parameters (link bandwidth, hop/pair latency, injection bandwidth) —
no testbed; calibrate against published external measurements.

Scope rule kept: public sources only; no consortium/specification text was ingested.
UEC 1.0 and UALink 1.0 specification documents were **not** opened — they appear here
only as named references for the documented gap (see "Gaps").

Confidence scale: **H** = primary source, numbers transcribed from the source text;
**M** = public secondary source or numbers partially from search-result quotes of the
source, verify exact wording at integration; **L** = weak/context-only.

---

## Core anchors (12, each with numbers + units + measurement context)

### A1 — NVIDIA DGX GB200/GB300 NVL72 User Guide: NVLink5 switch chip
- **Citation:** "Hardware — NVIDIA DGX GB Rack Scale Systems User Guide", NVIDIA docs,
  https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html (accessed 2026-10-27). Official documentation.
- **Measured/system:** vendor specification of the NVLink5 switch chip in the GB200/GB300 NVL72 rack.
- **Numbers (verbatim from source):** "The NVLink switch system delivers an unprecedented
  **57.6 terabits per second (Tbps)** of full duplex bandwidth" per NVLink switch chip;
  "2x NVLink NVSwitches, each of which has **72 NVLink ports**" per switch tray;
  "**9x 1RU NVLink switch trays**" per NVL72 rack.
- **Anchors:** link-BW / switch-capacity parameter of the fabric model (switch radix 72,
  per-switch full-duplex 7.2 TB/s); topology fan-in check for NVL72-class fabrics.
- **Access:** public web page, no license restriction.
- **Confidence/caveats:** H for the numbers; **spec, not measurement** — use as ceiling,
  never as achieved value.

### A2 — NVIDIA GB200 NVL72 product page: per-GPU and aggregate NVLink bandwidth
- **Citation:** "NVIDIA GB200 NVL72", https://www.nvidia.com/en-us/data-center/gb200-nvl72/ (accessed 2026-10-27).
- **Measured/system:** vendor specification, 72 Blackwell GPUs in one NVLink domain.
- **Numbers:** **1.8 TB/s** bidirectional NVLink bandwidth per GPU (= 900 GB/s per
  direction); **130 TB/s** aggregate NVLink GPU-to-GPU bandwidth across the rack.
- **Anchors:** injection-BW ceiling (per-GPU) and aggregate link-BW ceiling for the L0 model.
- **Access:** public product page.
- **Confidence/caveats:** H for transcription; **spec, not measurement**; per-direction
  900 GB/s is derived from the bidirectional figure — interpretation risk if quoted as
  measured.

### A3 — Crusoe Cloud: NCCL allreduce validation on a GB200 NVL72 rack (MEASURED)
- **Citation:** "How-To: Setup GB200 NVL72 Rack on RKE2 Cluster and Run NCCL Performance
  Validation", Crusoe Cloud support, Nov 5 2025,
  https://support.crusoecloud.com/hc/en-us/articles/41038210396443 (accessed 2026-10-27).
- **Measured/system:** `all_reduce_perf` on all **72 GPUs** of a GB200 NVL72 rack exposed
  as 18 × 4-GPU instances; NCCL 2.28.3, CUDA 12.9.1, driver 580.82.07; `mpirun ... -b 2G -e 32G`,
  float32, 10 warmup/20 iterations. Message regime: **2–32 GiB per rank** (bandwidth-bound).
- **Numbers (out-of-place):** 2 GiB: **5375.10 µs**, busbw **787.95 GB/s**; 4 GiB: 10193.01 µs,
  **831.03 GB/s**; 8 GiB: 19555.07 µs, **866.36 GB/s**; 16 GiB: 38056.60 µs, **890.32 GB/s**;
  32 GiB: 74718.41 µs, **906.94 GB/s**; avg busbw **855.949 GB/s**.
  In-place variant: 2 GiB: 409019.60 µs, **5.20 GB/s** (kernel/SM contention acknowledged in
  the article); 32 GiB: 75675.13 µs, **895.31 GB/s**.
- **Anchors:** **O-CCT, large-message bandwidth-bound regime** on the flagship scale-up
  fabric; NCCL channel/SM-config sensitivity (in-place vs out-of-place spread).
- **Access:** public support article.
- **Confidence/caveats:** M-H. Real measurement with full config context, but (a) vendor
  ops guide, not peer-reviewed; (b) the article also sets `NCCL_IB_HCA` guidance, so the
  split between NVLink-domain and IB paths for this 72-GPU run is not stated explicitly —
  interpretation risk when attributing busbw ≈ 0.9 TB/s purely to NVLink.

### A4 — ASTRA-sim 2.0 (ISPASS 2023): analytical-backend validation vs real V100 systems
- **Citation:** M. Jeon et al., "ASTRA-sim2.0: Modeling Hierarchical Networks and
  Disaggregated Memory Systems for Distributed Deep Learning Training", ISPASS 2023;
  arXiv:2303.14006; PDF: https://astra-sim.github.io/assets/papers/astra-sim2/ASTRA-sim2-ISPASS_2023.pdf.
- **Measured/system:** simulator-vs-hardware validation: "two real systems leverage
  NCCL v2.4.6 which consist of **4 and 16 NVIDIA V100 GPUs** using a Ring topology with
  **150 GB/s NVLink**"; message regime "**64 MB – 1.5 GB** All-Reduce".
- **Numbers:** "the mean error of simulation over all configurations is **5%**";
  speed/fidelity datapoint: 1 MB all-reduce on a 64-NPU (4×4×4) 3D Torus — Garnet
  (cycle-level) **21.42 minutes** vs analytical backend **1.70 s** (**756×** faster);
  analytical backend handles a 4096-NPU (16×16×16) 3D Torus in **3.14 s**.
- **Anchors:** **O-CCT** (medium/large ring-allreduce regime) for the analytical backend;
  defines a validity domain (no congestion/oversubscription modeled) and an error band
  (≈5%) usable as a calibration tolerance; directly relevant since ASTRA-sim is a pinned backend.
- **Access:** arXiv/open venue; public.
- **Confidence/caveats:** H (numbers verified from paper text). Validation is
  small-scale (≤16 GPUs) and NVLink-3-era; extrapolating the 5% band to NVL72-class
  fabrics is out of the validated domain.

### A5 — Google TPU v4 (ISCA 2023): ICI link bandwidth, OCS, topology measurements
- **Citation:** N. P. Jouppi et al., "TPU v4: An Optically Reconfigurable Supercomputer
  for Machine Learning with Hardware Support for Embeddings", ISCA 2023; arXiv:2304.01433.
- **Measured/system:** TPU v4 pods (4096 chips, 3D torus, OCS-reconfigurable), vendor
  paper with measured all-to-all experiments on 4×4×8 and 4×8×8 slices.
- **Numbers (from paper text):** Table 4 — TPU v4 Inter-Chip Interconnect: "**6 links @
  50 GB/s**" per chip (TPU v3: 4 links @ 70 GB/s; A100 comparison row: 12 links @ 25 GB/s);
  §7.3 — "ICI link bandwidth is **2x IB—400 vs. 200 Gbit/s**"; **16 external ICI links per
  PCB**; OCS: Palomar **136×136 ports** (128 usable + 8 spare), path switching
  "**milliseconds**"; measured all-to-all throughput: twisted torus gives **1.63×**
  (4×4×8) and **1.31×** (4×8×8) vs regular torus, individual DMAs of **4 KiB**; a hybrid
  IB+ICI alternative would be "**1.8x–2.4x slower**" for all-reduce; PaLM trained on
  6144 TPU v4 chips sustaining **57.8% of peak FLOPs** for 50 days.
- **Anchors:** link BW for a non-Ethernet, non-NVIDIA scale-up fabric; **O-CCT topology
  sensitivity** (twisted vs regular torus); reconfiguration timescale (OCS, ms — vs
  ns/µs data-path latencies) for dynamic-topology modeling.
- **Access:** arXiv public.
- **Confidence/caveats:** H. Note 50 GB/s = 400 Gbps is the per-link figure; the paper's
  "6 links @ 50 GB/s" is per-chip ICI capacity (300 GB/s/chip per direction class) — do
  not confuse with per-direction aggregate without re-checking Table 4 column order at
  integration.

### A6 — NCCL GitHub issue #1222: 4×8 H100 allreduce over 16×200 Gbps RoCEv2 (MEASURED)
- **Citation:** "Loss or Performance for NCCL test between 2.19.3 and 2.20.3", NVIDIA/nccl
  issue #1222, https://github.com/NVIDIA/nccl/issues/1222 (accessed 2026-10-27).
- **Measured/system:** allreduce, 4 nodes × 8 H100 (SXM), inter-node "16*200Gbps ROCEv2",
  NCCL 2.19.3 vs 2.20.3; sizes 1–16 GiB (bandwidth-bound).
- **Numbers (out-of-place, 2.19.3):** 1 GiB (1073741824 B): **5397.8 µs**, algbw 198.92,
  busbw **385.41 GB/s**; 16 GiB: **85110 µs**, algbw 201.86, busbw **391.10 GB/s**.
  2.20.3: 1 GiB: 5692.2 µs, busbw 353.69; 16 GiB: 86981 µs, busbw 370.33 GB/s.
  NVIDIA (sjeaugey): regression from treating "16x200G ports as 8x400G ports" and DGX
  H100 default tuning using "only **16 SMs** for NCCL operations".
- **Anchors:** **O-CCT** for hybrid NVLink-intra-node + RoCE-inter-node topologies;
  software-version sensitivity band (≈5–8% busbw swing) — motivates pinning software
  config in any calibration comparison.
- **Access:** public GitHub issue.
- **Confidence/caveats:** M-H (numbers are machine-pasted nccl-tests output; credible,
  community-reported, not peer-reviewed).

### A7 — AMD Instinct MI300X: Infinity Fabric scale-up bandwidth
- **Citation:** "AMD Instinct MI300X Platform Data Sheet",
  https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/data-sheets/amd-instinct-mi300x-platform-data-sheet.pdf;
  AMD Hot Chips 2024 presentation (MI300X, A. Smith),
  https://hc2024.hotchips.org/assets/program/conference/day1/23_HC2024.AMD.MI300X.ASmith(MI300X).v1.Final.20240817.pdf;
  Lenovo LP1943 confirms ("128 GB/s between each of the 8 GPUs, for a total of 896 GB/s").
- **Measured/system:** vendor spec of the 8-OAM MI300X baseboard.
- **Numbers:** **7 bidirectional Infinity Fabric links per GPU, each 128 GB/s**, i.e.
  **896 GB/s aggregate bidirectional** per GPU across the 8-GPU fully connected domain;
  PCIe Gen5 x16 (128 GB/s) per GPU to host.
- **Anchors:** link-BW parameter for a non-NVIDIA scale-up fabric (7-link full-mesh OAM
  topology — no switch, 1 hop between any pair; contrasts NVSwitch fat-tree).
- **Access:** public vendor PDFs.
- **Confidence/caveats:** H for transcription; **spec, not measurement**; datasheet
  wording ("8-node ring") vs Hot Chips mesh description differs — treat topology as
  fully connected 7 links/GPU per Hot Chips + Lenovo.

### A8 — Pond (ASPLOS 2023): CXL added-latency tolerance emulation
- **Citation:** H. Li et al., "Pond: CXL-Based Memory Pooling Systems for Cloud
  Platforms", ASPLOS 2023; arXiv:2203.00241; ACM DOI 10.1145/3575693.3578835.
- **Measured/system:** production-trace-driven evaluation on cloud platforms;
  CXL added latency emulated in hardware.
- **Numbers:** "emulating either **64ns or 140ns** of additional memory access overheads
  over same-NUMA-node memory"; with those latencies **43% and 37%** of 158 workloads
  respectively remain within performance goals.
- **Anchors:** hop/pair latency scale for memory-semantic (load/store) scale-up fabrics —
  the CXL-class point on the latency axis; workload-sensitivity context.
- **Access:** arXiv/open PDF (public); ACM version paywalled but arXiv is open.
- **Confidence/caveats:** H. Numbers are *emulated* additions, not a CXL product
  measurement — they bound plausible device latencies rather than measure one.

### A9 — Berger et al. (IEEE Micro 2023): CXL link and switch latency breakdown
- **Citation:** M. S. Berger et al., "Design Tradeoffs in CXL-Based Memory Pools",
  IEEE Micro 2023; public copy: https://pages.cs.wisc.edu/~markhill/papers/ieeemicro23_cxl_memory_pooling.pdf.
- **Measured/system:** analytical/latency-budget study of CXL memory-pool fabrics.
- **Numbers:** CXL links add **~10 ns per direction**; CXL switches add at least **~70 ns**
  (ports, arbitration, NoC) per switch stage.
- **Anchors:** per-hop latency model for switch-based memory-semantic fabrics — the
  switch-hop term for a CXL-class L0 model.
- **Access:** public author copy.
- **Confidence/caveats:** H for transcription; these are design-estimate numbers (from
  the paper's budget analysis), not silicon measurements — pair with A8.

### A10 — HiPC 2025 Workshop: Communication-Centric UALink vs NVLink comparison
- **Citation:** "Communication-Centric UALink and NVLink Comparison for Large Scale AI
  Training", IEEE/ACM HiPC 2025 Workshops; IEEE CSDL 453800a068,
  https://www.computer.org/csdl/proceedings-article/hipcw/2025/453800a068/2fmcmT1r8Jy.
- **Measured/system:** analytical model of UALink vs NVLink/NVSwitch fabrics for
  training collectives at scales to 1024 GPUs.
- **Numbers:** explicit latency assumption for the NVLink side — "NVIDIA does not publish
  end-to-end latency for NVLink Network; we assume **0.8 µs**, consistent with 'sub-µs'
  positioning for NVSwitch hops" (quote via public search snippet of the paper —
  re-verify wording against the paper at integration); result: a flat UALink pod reduces
  the step-time contribution of small-message collectives at scales up to 1024 GPUs,
  while NVLink 5 keeps an advantage in bandwidth-bound scenarios.
- **Anchors:** hop/pair latency for GPU scale-up fabrics in an *assumption-class*
  (peer-reviewed usage) value; UALink-side parameters for the L0 family.
- **Access:** abstract public (CSDL); full text paywalled.
- **Confidence/caveats:** **M** — the 0.8 µs is a stated assumption, not a measurement;
  exact parameter table not yet extracted (paywall).

### A11 — Meta SIGCOMM 2024: RoCE network for distributed AI training (UEC-adjacent)
- **Citation:** A. Gangidi et al., "RDMA over Ethernet for Distributed AI Training at
  Meta Scale", ACM SIGCOMM 2024; public PDF:
  https://engineering.fb.com/wp-content/uploads/2024/08/sigcomm24-final246.pdf;
  blog: https://engineering.fb.com/2024/08/05/data-center-engineering/roce-network-distributed-ai-training-at-scale/.
- **Measured/system:** production RoCEv2 fabric (rail-optimized, multi-plane spine-leaf)
  at Meta; two ~**24,576-GPU** clusters (one InfiniBand, one RoCE); **Llama 3 trained on
  16,000 GPUs** on the RoCE cluster.
- **Numbers:** **400G** single-mode optics between RTSWs and CTSWs; RTSW uplink capacity
  run at **1:2 under-subscription** vs downlink; path-pinning degraded training
  performance "up to more than **30%**"; E-ECMP + QP scaling gave "up to **40%**
  improvement for the AllReduce collective".
- **Anchors:** scale-out/UEC-adjacent fabric sanity anchors (congestion, load-balance
  sensitivity); **secondary** for scale-up — tagged because it is not a GPU-to-GPU
  scale-up fabric.
- **Access:** public PDF + blog.
- **Confidence/caveats:** M-H (production measurements, but the scale-up-relevant
  per-collective throughput tables live in the paper PDF; numbers above verified from
  the public blog + abstract).

### A12 — NCCL GitHub issue #1054: NCCL's internal NVLink bandwidth model
- **Citation:** "The total nvlink bandwidth obtained by NCCL topo is not the actual total
  bandwidth", NVIDIA/nccl issue #1054, https://github.com/NVIDIA/nccl/issues/1054.
- **Measured/system:** NCCL topology detection on an **8-GPU A100** server.
- **Numbers:** NCCL's `system->totalBw` at `ncclTopoSearchInit` computed as only
  **240 GB/s** (= 12 links × **20 GB/s/link**), while the physical NVLink3 peak is
  25 GB/s/link / 300 GB/s per direction and observed bandwidth is higher; maintainer
  guidance (per public reply): NCCL models NVLink at **20 GB/s per link** and
  application-level bandwidth typically reaches **~80% of peak**.
- **Anchors:** injection-BW derating factor — the gap between physical link BW and what
  the software communication stack will actually schedule; essential when comparing
  L0-model predictions (physical-BW-based) against NCCL-driven measurements.
- **Access:** public GitHub issue.
- **Confidence/caveats:** M — the 240 GB/s value and system config are from the issue
  body (verified); the 20 GB/s/link and ~80% figures come from the issue thread via
  search snippet — verify the reply text at integration.

---

## Top-5 picks for a first calibration pass

1. **A3 (Crusoe GB200 NVL72 allreduce)** — the only public *measured* O-CCT series on the
   flagship NVLink scale-up fabric, 2–32 GiB, with exact software pins (NCCL 2.28.3,
   CUDA 12.9.1). Calibrates O-CCT in the bandwidth-bound regime and exposes the
   software-config sensitivity any comparison must control.
2. **A4 (ASTRA-sim 2.0, ISPASS 2023)** — peer-reviewed simulator-vs-hardware validation
   (4/16 V100, ring, 150 GB/s NVLink, 64 MB–1.5 GB, mean error 5%) that supplies both an
   anchor and a methodological template for our analytical-backend calibration; also the
   paper of one pinned backend.
3. **A5 (TPU v4, ISCA 2023)** — independent (non-NVIDIA, non-Ethernet) concrete per-link
   BW (6 × 50 GB/s ICI), plus *measured* topology-effect numbers (twisted torus 1.31–1.63×
   all-to-all) that can falsify topology-modeling assumptions; OCS ms-scale switching
   anchors the dynamic-reconfiguration axis.
4. **A1 + A2 (NVIDIA official NVL72 specs)** — spec ceilings (57.6 Tbps/switch, 72-port
   radix; 1.8 TB/s per GPU, 130 TB/s aggregate) needed to normalize every measured
   fraction above; free of vendor-marketing ambiguity when quoted from docs/datasheet.
5. **A6 (NCCL #1222)** — full measured table (µs and GB/s per size) for the
   NVLink-intra + RoCE-inter hybrid that our UEC-flavored profiles will resemble, and a
   documented 5–8% software-version swing that sets the noise floor for accepting or
   rejecting a calibration match.

Second wave (latency axis): A8/A9 (CXL-class ns-scale hop latency) and A10 (0.8 µs
assumption-class NVLink hop latency) — needed before calibrating small-message O-CCT.

---

## Additional candidates (found, NOT counted toward the ≥10 bar)

- **Li et al., "Evaluating Modern GPU Interconnect: PCIe, NVLink, NV-SLI, NVSwitch and
  GPUDirect"** (IEEE TPDS 2019; arXiv:1903.04611) — canonical P2P latency microbenchmarks
  (P100/V100 DGX-1, DGX-2, Summit; four NUMA effects). PDF text extraction failed twice
  in this pass (arXiv PDF and IEEE author-accepted copy); per-pair µs latencies must be
  extracted at integration. High value as the measured *latency* anchor.
- **Maltenberger et al., "Efficiently Joining Large Relations on Multi-GPU Systems"**
  (VLDB 2025) — DGX H100 NVLink 4.0/NVSwitch P2P microbenchmarks; PDF fetch unsupported
  in this environment.
- **Song, "Survey of Intra-Node GPU Interconnection in Scale-Up Network", Future
  Internet 17(12):537, MDPI 2025** — open-access survey compiling per-generation
  NVLink/PCIe/Infinity Fabric numbers; MDPI page returned 403 from this sandbox.
- **Handley et al., "Re-architecting Data Center Networks and Stacks for Low Latency and
  High Performance" (NDP, SIGCOMM 2017)** — lineage/validation anchor for htsim (a pinned
  backend family); PDF fetch failed in this pass; no numbers captured here.
- **"An Application-centric Network Simulator Toolchain for AI Workloads"** (ACM
  2025, htsim/ATLAHS extension) — 403 from dl.acm.org; abstract-only awareness.
- **arXiv:2502.20965 (intra-node communication impact study, 2025)** — contains
  measured IB EDR microbenchmarks (≈12.1 GiB/s of 12.12 GB/s line rate; ~1.12 µs at
  128 B ib_write) and a compiled per-lane NVLink speed table (4/7.5/15.1 GB/s per lane) —
  useful but simulation-focused; secondary.

## Gaps (explicit, per the FAIL clause documentation duty)

- **No public UEC (Ultra Ethernet) measurement study found** as of 2026-10: UEC 1.0 spec
  (June 2025) is design-only in public sources; nearest citable measurements are
  RoCEv2/IB studies (A6, A11). UEC-specific calibration anchors must wait for product
  measurements or be replaced by RoCE-class proxies, clearly labeled as such.
- **Hop/pair latency for GPU scale-up fabrics is assumption-grade or older-generation**:
  current-gen NVLink/NVSwitch end-to-end latency is not officially published (A10 states
  this explicitly); measured µs-class P2P numbers exist for V100-era (Li et al.) but were
  not extractable in this pass. This is the weakest anchor axis.
- **No UALink silicon measurements exist yet** (spec April 2025; products later) — only
  model assumptions (A10).

---

## Provenance log (research process, 2026-10-27, ~60 min)

Web searches (queries as issued, in order):
1. `GB200 NVL72 NVLink5 1.8 TB/s per GPU 130 TB/s aggregate bandwidth specs`
2. `NVIDIA GB200 NVL72 allreduce bandwidth benchmark measurement`
3. `NVSwitch hop latency nanoseconds measurement DGX A100 H100`
4. `nvbandwidth measured NVLink bandwidth H100 GB/s`
5. `ASTRA-sim 2.0 modeling discrete training paper validation ISPASS`
6. `htsim datacenter network simulator validation paper Hot Interconnects`
7. `TPU v4 ISCA 2023 paper inter-core interconnect ICI bandwidth 3.2 Tbps`
8. `Pond CXL memory pooling paper latency nanoseconds added`
9. `"UALink" NVLink comparison paper communication-centric 2025 latency bandwidth assumptions`
10. `Alibaba UnifiedBus scale-up system LLM inference paper PCIe bandwidth`
11. `nccl-tests allreduce latency 8 bytes H100 NVLink intra-node microseconds`
12. `NVLink SHARP GB200 NVL72 in-network reduction allreduce bandwidth TB/s`
13. `arxiv UALink NVLink analytical comparison latency 0.8 microseconds GPU scale-up paper`
14. `Ultra Ethernet performance evaluation measurement study arxiv RDMA latency`
15. `MDPI survey intra-node GPU interconnection scale-up NVLink latency Song 2025`
16. `AMD MI300X Infinity Fabric xGMI bandwidth 8 GPU measured latency`
17. `AMD Instinct MI300X Infinity Fabric 896 GB/s aggregate bandwidth eight GPUs`
18. `arxiv NVSwitch hop latency measurement P2P GPU remote memory access microseconds DGX H100 characterization`
19. `arxiv survey intra-node GPU interconnect scale-up NVLink latency bandwidth 2025 Song MDPI`
20. `SemiAnalysis GB200 NVL72 NVLink spine bandwidth measured 2.3 TB/s allreduce`
21. `Meta RDMA over Ethernet distributed AI training SIGCOMM 2024 24000 GPU allreduce bandwidth measured`

Page fetches (method → outcome):
- WebFetch `docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html` → OK (A1 numbers).
- WebFetch `arxiv.org/abs/2304.01433` → abstract only (no ICI numbers).
- WebFetch Crusoe article → connect timeout; retried via webReader → OK (A3 table).
- WebFetch `ar5iv.labs.arxiv.org/html/2304.01433` → redirect to abs; webReader on
  `arxiv.org/pdf/2304.01433` → OK (A5 numbers).
- WebFetch `ar5iv.labs.arxiv.org/html/2303.14006` → OK (A4 validation numbers).
- WebFetch `github.com/NVIDIA/nccl/issues/1222` → OK (A6 tables).
- WebFetch `arxiv.org/html/2304.01433` → 404.
- WebFetch `arxiv.org/abs/1903.04611` → abstract only; webReader on
  `arxiv.org/pdf/1903.04611` and IEEE author-copy PDF → extraction failed (candidate deferred).
- WebFetch HPI VLDB'25 PDF → unsupported content type (candidate deferred).
- WebFetch `mdpi.com/1999-5903/17/12/537` → 403 (candidate deferred).
- WebFetch computer.org CSDL HiPCW article → page shell, no text; ResearchGate → 403.
  A10 parameters taken from public search snippet; flagged for verification.
- WebFetch `dl.acm.org/doi/10.1145/3712285.3759838` → 403 (candidate deferred).
- webReader `engineering.fb.com/.../sigcomm24-final246.pdf` → OK (title/authors; blog
  fetched separately for verified numbers in A11).
- webReader `sands.kaust.edu.sa/.../ndp.pdf` (NDP/htsim) → server error (candidate deferred).
- webReader `github.com/NVIDIA/nccl/issues/1054` → title/description OK (A12, partial).

No standard/consortium specification documents were fetched or ingested. No restricted
text entered this research.
