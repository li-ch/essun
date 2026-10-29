# Calibration anchor gap-fill — STAGING

Status: **PROPOSED** (staging document; accepted rows are integrated into
the anchor registry by an explicit decision, suggested continuation ids
CAL-A13… below).
Date: 2026-10-27/28. Sources: `anchors_staging.md` "Gaps",
`CALIBRATION_PLAN.md` §4.

Purpose: stage NEW anchors for exactly the regimes the 12 integrated anchors
(CAL-A1…A12) leave uncovered, per the gate's named gap regimes:

- **R1 — UEC-class transport measurements** (plan gap 1, 4)
- **R2 — large-message AllReduce on scale-up fabrics** (+ spec-vs-measured
  derating, plan gaps 9/10 adjacent)
- **R3 — congestion-management effects on collective time** (plan gap 7)
- **R4 — multi-rank injection scaling** (plan gap 8 adjacent)
- bonus axes pulled in where the same source covers them: **small-message
  O-CCT ≤ 64 KiB** (plan gap 3) and **measured hop/pair latency** (plan gap 2).

Scope rule kept and strengthened: public sources only; **no consortium or
specification text was ingested** — `ultraethernet.org` pages appeared in
search results (UEC 1.1 announcement) and were deliberately NOT opened; UEC
1.0/1.1 and UALink spec documents remain un-opened. Everything below is
third-party papers (arXiv/peer-reviewed), vendor engineering blogs, public
GitHub issues, or an independent practitioner blog — same license discipline
as `anchors_staging.md`.

Confidence scale (same): **H** = primary source, numbers transcribed from the
source text (or its official mirror/abstract); **M** = public secondary source
or numbers partially from search-result quotes/snippets, verify exact wording
at integration; **L** = weak/context-only.

Eleven anchors staged (GF-01…GF-11). Regime coverage: R1 ×4, R2 ×3(+1),
R3 ×3, R4 ×2, small-message ×3, measured-latency ×3. None duplicates
CAL-A1…A12 (different sources; CAL-A3 remains the only Crusoe row).

---

## R2 + small-message + derating — the anchor with the widest regime span

### GF-01 — AMD ROCm blog: RCCL/xGMI on MI300X, full measured tables (MEASURED)
- **Citation:** "Understanding RCCL Bandwidth and xGMI Performance on AMD
  Instinct™ MI300X", ROCm Blogs (published 2025-03),
  https://github.com/ROCm/rocm-blogs/discussions/598 (mirror:
  https://rocm.blogs.amd.com/software-tools-optimization/mi300x-rccl-xgmi/README.html)
  (accessed 2026-10-27).
- **Measured/system:** `all_reduce_perf` on all **8 GPUs** of an MI300X node
  (7-hop full-mesh xGMI); **RCCL 2.22.3-develop:f5b15f2, ROCm 6.3.0.0**,
  MI300X (28 CDUs, 1 graphics compute die); per-pair link measurements via
  TransferBench; eager and CUDA-graph modes; `NCCL_GRAPH_MIX_SUPPORT=1`.
- **Numbers (verbatim):** "While each xGMI link has a raw unidirectional
  bandwidth of **64 GB/s**, only about **48 GB/s (or 75%)** is usable for data
  transfer" — the blog attributes the gap to CRC flits ("reserves 4 of every
  64 flits") and packet-protocol overhead ("consumes another 16 of 64 bytes")
  (flag: the quoted percentages did not arithmetically reconcile during
  extraction — re-verify wording at integration; the 48 GB/s usable figure and
  the measured tables below are consistent with each other).
  Link measurements: per-link **45.1–47.2 GB/s** unidirectional observed;
  "the slowest link caps the achievable bandwidth at ~**45 GB/s**;
  7 × 45 = **315 GB/s**" expected aggregate; "Sum of Average Bandwidth Across
  All GPU Pairs: **325.6 GB/s** (average across all links: 45.8 GB/s)".
  RCCL allreduce (eager, GPU 0, 4 channels, op out): 8 B: **16.61 µs**;
  32 B: 16.74 µs; 64 B: 16.61 µs; 16 KiB: **13.54 µs**, busbw **2.12 GB/s**;
  64 KiB: **13.77 µs**, busbw **8.33 GB/s**; 128 KiB: 14.71 µs, 35.98 GB/s;
  1 MiB: 26.71 µs, 160.45 GB/s; 8 MiB: 99.18 µs, 251.22 GB/s; 16 MiB: 176.23
  µs, 264.26 GB/s; 128 MiB: 1264.98 µs, **293.11 GB/s**; 1 GiB: 9926.44 µs,
  **314.44 GB/s**; 16 GiB: 94254.55 µs, **318.98 GB/s**. Graph mode improves
  small sizes (8 B: 16.38 µs; 32 B: **6.32 µs**; 64 KiB: **9.14 µs**) and
  reaches **319.22 GB/s** busbw at 16 GiB (graph-table mid rows: re-verify at
  integration).
- **Anchors:** **O-CCT small-message regime (≤ 64 KiB) — the first measured
  staged anchor in exactly the smoke-manifest regime** (13–17 µs per
  allreduce at 8–64 KiB); **O-CCT large-message on a non-NVIDIA scale-up
  fabric** (busbw plateau 314–319 GB/s vs the CAL-A7-derived 448 GB/s
  unidirectional ceiling ⇒ measured/spec ratio ≈ 0.71); **injection derating**
  on the xGMI class (75% per-link usable; 45 GB/s worst-link cap) to pair
  with CAL-A12 on the NVLink class.
- **Access:** public vendor blog + GitHub mirror.
- **Confidence/caveats:** **M-H** — real measured output with full software
  pins, but vendor blog (not peer-reviewed); per-pair table row-level values
  and the overhead-percentage sentences flagged for re-verification; busbw
  carries NCCL's 2(r−1)/r convention (same caveat class as CAL-A3/A6).

## R2 — large-message AllReduce, additional measured scale-up series

### GF-02 — NCCL GitHub issue #326: 8×H100 NVLink allreduce/allgather (MEASURED)
- **Citation:** "all gather / all reduce showing unidirectional bandwidth peak
  performance", NVIDIA/nccl-tests issue #326,
  https://github.com/NVIDIA/nccl-tests/issues/326 (accessed 2026-10-27).
- **Measured/system:** `all_reduce_perf`/`all_gather_perf` on **8 H100 GPUs
  with NVLink** (NVLink-4 class), NCCL ≥ 2.27.1.
- **Numbers (verbatim):** busbw "saturated at **~360 GB/s**" for large
  messages (**128 MiB–16 GiB**) for both collectives, against the poster's
  expectation of the ~480 GB/s per-direction class; thread identifies this as
  the expected ceiling given NVLink bidirectional counting conventions
  ("half of 480 in each direction"), i.e. a measurement-vs-spec
  unit-convention case.
- **Anchors:** O-CCT large-message regime on the H100 NVSwitch class —
  a *community* measured series at a different point than GF-04's 476 GB/s
  (below); documents the bidirectional/unidirectional interpretation hazard
  that any CCT-vs-CCT comparison must settle first (extends CAL-A12's
  derating-bridge need).
- **Access:** public GitHub issue.
- **Confidence/caveats:** **M-H** (machine-pasted nccl-tests output;
  community-reported). Exact per-size table rows and the full maintainer reply
  were not cleanly extractable in this pass — title/summary verified, rows
  re-verify at integration. **Open discrepancy to resolve at integration:**
  360 GB/s (this issue) vs 476 GB/s (GF-04, Oracle) on nominally the same
  8×H100 NVLink class — NCCL version, NVLS on/off, and counting convention
  are candidate explanations; do not average them.

### GF-03 — B300 field notes (independent practitioner): next-gen scale-up AllReduce (MEASURED)
- **Citation:** "B300 Field Notes (for the AI Infra/Performance Engineer)",
  sixrackunits Substack,
  https://sixrackunits.substack.com/p/b300-field-notes-for-the-ai-infraperformance
  (accessed 2026-10-27).
- **Measured/system:** NCCL allreduce/broadcast and `nvbandwidth` on a B300
  (Blackwell Ultra, NVLink-5-class) system; independent engineer's blog.
- **Numbers (verbatim):** NCCL allreduce peak **~837 GB/s** ("**93% of
  theoretical**" — theoretical quoted as 900 GB/s class); broadcast ~**682
  GB/s** (~76%); `nvbandwidth` device-to-device: unidirectional **782 / 717
  GB/s** (per direction), bidirectional **1.35 / 1.41 TB/s**; D2D latency
  **~1.6 µs**; PCIe H2D/D2H latency **~1.4 µs**; NCCL AllReduce completes
  2 MiB "in as little as **42–52 µs**".
- **Anchors:** O-CCT large-message on the *post-NVL72* generation (extends
  CAL-A3's GB200 series by one generation); measured D2D microbenchmark
  latency (~1.4–1.6 µs) for the latency axis; another measured/spec derating
  point (93% / 76%).
- **Access:** public blog (partial paywall possible).
- **Confidence/caveats:** **M** — independent, methodology context light
  (rank count, NCCL version not cleanly captured); useful as a corroboration
  point, not a primary series; re-verify numbers and config at integration.

## R4 — multi-rank injection scaling + RoCE-proxy transport (UEC-adjacent)

### GF-04 — Oracle OCI: OSU/NCCL on H100 clusters, 8→16-rank measured scaling (MEASURED)
- **Citation:** "Zettascale in Practice: OSU and NCCL Benchmark on H100
  Clusters for HPC and AI Workloads", Oracle blog,
  https://blogs.oracle.com/cloud-infrastructure/zettascale-osu-nccl-benchmark-h100-ai-workloads
  (2026, accessed 2026-10-27).
- **Measured/system:** OCI H100 cluster: nodes with **8 NVIDIA H100 80 GB
  HBM3 (112 SMs)** and 8 NVIDIA 400-Gbps NICs per node (ConnectX-class;
  NIC count/detail re-verify), RoCEv2 fabric; OSU microbenchmarks (MPI,
  CUDA-aware) + nccl-tests; "NCCL 2.27" cited for latency behavior.
- **Numbers (verbatim):** CPU↔CPU RDMA latency: **2.70 µs @ 8 B**, flat to
  ~1 KiB; OSU bandwidth: 64 MiB **47.71 GB/s**, 512 MiB 48.76, 1 GiB
  **48.77 GB/s** sustained ("sustained network bandwidth is 48.77 GB/s on an
  NVIDIA 400-Gbps network interface" ⇒ ~97.5% of line rate);
  GPU↔GPU (CUDA-aware MPI over network): **32.37 µs @ 8 B** through
  **32.70 µs @ 1 KiB**, 60.35 µs @ 512 KiB. NCCL summary: "**NCCL on single
  node with 8 GPUs | 476.37 GB/s**", "NCCL on two nodes with 16 GPUs |
  **469.67 GB/s**" (allreduce busbw) — a **1.4% drop when doubling ranks and
  crossing onto the RoCE legs**; 4 GPUs: 187.03 GB/s; 16-GPU all_gather
  437.85 GB/s; 2-GPU broadcast 228.76 GB/s.
- **Anchors:** **multi-rank injection scaling** (8→16 ranks, one fabric
  pair, measured) — the first staged scaling point for plan gap 8; measured
  small-message transport latencies on a 400G RoCE fabric (UEC-proxy class,
  same labeled-proxy discipline as CAL-A6/A11); per-NIC sustained-vs-line-rate
  (97.5%) derating for scale-out legs.
- **Access:** public vendor blog.
- **Confidence/caveats:** **M-H** — printed result tables with configs, but
  vendor blog; the 476 GB/s busbw figure interacts with the bidirectional-
  counting caveat (see GF-02) and exceeds GF-02's 360 GB/s — unresolved
  interpretation risk, staged as-is.

## R1 — UEC-class transport (sim + hardware), and R3 — congestion effects

### GF-05 — SMaRTT + REPS (NSDI 2025): the congestion control UEC standardized, evaluated in uet-htsim + hardware
- **Citation:** "SMaRTT and REPS: Near-Optimal Congestion Control and Load
  Balancing for Data Centers", arXiv:2404.01630 (NSDI 2025 per paper text);
  https://arxiv.org/html/2404.01630; simulator code public at
  github.com/ultraethernet/uet-htsim (accessed 2026-10-27).
- **Measured/system:** packet-level simulation extending **htsim** (the same
  uet-htsim family pre-pinned as our third backend); 4 fat trees incl.
  1,024-node non-blocking and 2:1/4:1/8:1 oversubscribed; "**4KiB MTU size,
  a 800 Gbps network bandwidth, and a 400ns switch traversal latency**",
  link latency 600 ns; baselines EQDS, Swift, MPRDMA, RoCEv2; plus a DPDK
  **hardware** testbed: 2 Broadcom Trident 4 switches, Broadcom Thor
  2×100 Gbps NICs at 50 Gbps.
- **Numbers (verbatim):** SMaRTT is "the algorithm that forms the basis of
  the UEC NSCC specification"; REPS is cited "as a reference load-balancing
  mechanism for Ultra Ethernet Transport (UET)" by the 1.0 spec; "SMaRTT
  outperforms existing datacenter congestion control algorithms like Swift,
  RoCE, and MPRDMA by **up to 50%**"; alltoall "only up to **6%** behind the
  ideal time and up to **20% better** than other sender-based schemes";
  fairness: under Swift "the FCT of the slowest flow is **65% longer** than
  the fastest flow" (2 MiB permutation, 1,024 nodes, 8:1 oversubscription);
  trimming learns loss in "**roughly 84 us = 7 base RTTs**" vs ~half-to-one
  base RTT with trimming; EQDS "can generate up to **155x** more trimmed
  packets"; hardware: large-flow permutation "within **20% of optimal**"
  while "RoCE … are **3-5 times slower** than optimal"; alltoall "within
  **1.5x** of optimal, while RoCEv2 is **3-6x slower**"; per-flow state
  "**19 bytes**", "**59 … to 94** instructions per packet"; window clamped
  to 1.5 BDP; target RTT 1.5× base RTT.
- **Anchors:** **R1 + R3 in one row**: the UEC-standardized congestion
  behavior (NSCC) with quantified sim+HW deltas vs RoCE/Swift/EQDS — direct
  calibration context for the UEC-profile backends (uet-htsim parameters:
  800 Gbps, 400 ns switch traversal, 4 KiB MTU are themselves anchor-able
  sim-config provenance); congestion-management effect sizes (20–50% FCT
  improvements; RoCE 3–6× from optimal) bound what CM can move.
- **Access:** public arXiv + public simulator repo.
- **Confidence/caveats:** **H** (numbers extracted from paper HTML). Caveat:
  peer-reviewed *simulation* + small HW testbed, not UEC silicon; FCT (not
  collective-CCT) metric — regime bridge must be explicit.

### GF-06 — PCM (arXiv Oct 2026): programmable congestion management on an Ultra Ethernet simulator, UCCL, ConnectX-8
- **Citation:** "Programmable Congestion Management for Terabit RDMA",
  arXiv:2610.13130 (Oct 2026); https://arxiv.org/html/2610.13130v1
  (accessed 2026-10-27).
- **Measured/system:** PCM deployed on "the packet-level Ultra Ethernet
  transport simulator (**UET-htsim**)" (1,024-host three-tier fat tree,
  100 Gbit/s links, 4,150 B packets), CPU-based **UCCL** (2 AMD EpYC 9124
  servers, 2× 800 Gbit/s ConnectX-8 each), CX-8 DOCA PCC (RoCEv2), and
  Microsoft 1P DPUs (2×200 Gbit/s, Arista DCS-7060X6).
- **Numbers (verbatim):** "In UCCL, it matches native Swift's **1.56 Tbit/s**
  goodput with 64 KiB chunk-level control"; incast-tuned initial windows
  give "**a 3× speedup of maximum FCT**" and "avoids **98.6%** of baseline
  packet drops"; "REPS+ECMP improves maximum FCT by **1.51–2.61×**"; CC cost:
  TX callbacks "from **214 to 246 ns (1.15×)**", RTT callbacks "**392 to
  676 ns (1.72×)**"; scheduling: fairness "at or above 0.99 from N=1 through
  N=32", "degrades to **0.818 at N=256 and 0.782 at N=512**, corresponding
  to reaction delays of **291 and 582 µs**", "Maximum FCT increases by
  **1.11× and 1.32×**"; scale: "With 64 of the DPA's 256 hardware threads
  and 3072 flows, PCM-Swift sustains **11.83 Mcalls/s**"; "48 DPA threads
  sustain **9.5–15.1 million CC calls/s**"; microbench "35 million events/s
  (**1.15 Tbit/s**)" CPU vs "75 million events/s (**2.5 Tbit/s**)" DPA;
  incast setup "RTT of ≈**15 µs**".
- **Anchors:** **R3 (congestion-management effects)** at UEC scale — quantified
  FCT sensitivity to CM reaction delay (291–582 µs → 1.11–1.32× FCT), CM
  processing budgets (ns-scale per-event costs vs Tbit/s line rates), and
  REPS-class LB gains (1.51–2.61×) — effect-size priors for what any
  congestion-management semantics modeling must reproduce; also a UET-htsim
  second user (sim-config cross-check with GF-05).
- **Access:** public arXiv.
- **Confidence/caveats:** **H** (extracted from HTML). No collectives
  benchmarked (workloads: incast/RDMA-writes/permutation, 150 KB–16 MiB) —
  FCT→CCT bridging is an explicit extrapolation; very recent, not yet
  peer-review-verified.

### GF-07 — Congestion impact characterization (arXiv 2026): measured collective slowdowns across 5 HPC fabrics
- **Citation:** "Characterizing the Impact of Congestion in Modern HPC
  Interconnects", arXiv:2604.11432; https://arxiv.org/html/2604.11432v1
  (accessed 2026-10-27).
- **Measured/system:** production/testbed allocations on **Leonardo** (HDR
  IB Dragonfly+, 400 Gb/s/node), **CRESCO8** (NDR IB, 1.67:1 blocking fat
  tree), **LUMI** (Cray Slingshot Dragonfly, 4×200 Gb/s), HAICGU (EDR IB +
  RoCE CE8850), Nanjing (RoCE NSLB CE9855); victim collectives 1,000
  iterations, 100 warmup discarded; vectors 8 B–16 MiB.
- **Numbers (verbatim):** CRECO8 steady incast, AlltoAll victims: "slowdowns
  up to **25×**"; steady incast: "performance dropping to **60%** of the
  uncongested case"; bursty incast 64 nodes: "a ratio of approximately
  **0.08 (i.e., 12× slower)**"; bursty alltoall "drops to **70%** of its
  uncongested baseline"; Leonardo incast: ratios "collapse to **0.2** (more
  than a 5× slowdown)" at 32–64 nodes; LUMI (per-flow HW CM + global-aware
  adaptive routing): "always within **5%** of the uncongested case";
  Nanjing: victim AlltoAll "**180 Gb/s**" peak, "**drops to 120 Gb/s**" with
  NSLB disabled (~33% loss); "Open MPI AllReduce showed up to a **25%
  bandwidth loss** compared to AlltoAll"; congestion effects appear "even at
  … ~**2% of a partition**"; RoCE/DCQCN "recurring sawtooth pattern … larger
  than **16 MiB**".
- **Anchors:** **R3 measured magnitudes** for collective-time degradation
  under congestion across fabric classes — the falsification envelope (5% →
  25×) any congestion-effect model must fall inside; direct evidence for the
  plan's gap 7 (no scale-up congestion anchor exists — these are scale-out
  HPC fabrics, staged under the same labeled-proxy rule as CAL-A11).
- **Access:** public arXiv.
- **Confidence/caveats:** **H** (extracted from HTML). Scale-out fabrics, not
  GPU scale-up; metrics are collective bandwidth ratios, not O-CCT series.

### GF-08 — Falcon (SIGCOMM 2025): a real UEC-class hardware transport, measured
- **Citation:** A. Singhvi et al., "Falcon: A Reliable, Low Latency Hardware
  Transport", ACM SIGCOMM 2025, https://dl.acm.org/doi/10.1145/3718958.3754353;
  abstract verified via
  https://www.microsoft.com/en-us/research/publication/falcon-a-reliable-low-latency-hardware-transport;
  Google blog (OCP open-sourcing, Intel IPU E2000 implementation):
  https://cloud.google.com/blog/topics/systems/introducing-falcon-a-reliable-low-latency-hardware-transport
  (all accessed 2026-10-27).
- **Measured/system:** Google's hardware reliable transport on commodity
  (lossy, PFC-free) Ethernet, multi-ULP (RDMA, NVMe); delay-based HW
  congestion control + multipath packet spraying + selective retransmission —
  architecturally the closest shipped relative of UEC's UET design points.
- **Numbers (verbatim, from the official abstract via MSR mirror):** "peak
  performance of **200 Gbps, 120 Mops/sec**"; operation completion times
  "**8×** lower than CX-7 RoCE under network congestion"; "**up to 65%
  higher goodput** under lossy conditions".
- **Anchors:** **R1 (UEC-class transport on real hardware)** — measured
  transport endpoint capability (200 Gbps / 120 Mops/s ⇒ ~6 ns/operation
  amortized) and the congestion/loss sensitivity deltas (8×, 65%) that
  UET-class transports claim over RoCE; pairs with GF-05/06 (sim) as the
  hardware bookend.
- **Access:** ACM DL paywalled; abstract public (MSR mirror); blog public.
- **Confidence/caveats:** **M-H** — headline numbers verified against the
  official abstract mirror; full paper tables (latency µs, message-rate
  curves) not extracted (ACM 403 in this sandbox; NetDev 0x18 slides PDF
  fetch failed URL validation) — extract at integration.

## R1 (design-target class) — UEC transport targets, third-party paper

### GF-09 — Ultra Ethernet 1.0 design-principles paper: transport design targets and protocol constants
- **Citation:** "Ultra Ethernet's Design Principles and Architectural
  Innovations", arXiv:2508.08906 (Aug 2025, Hoefler et al.);
  https://arxiv.org/html/2508.08906v1 (accessed 2026-10-27). Public arXiv
  paper by UEC participants — NOT a specification document; nothing was
  ingested from ultraethernet.org.
- **Numbers (verbatim):** UE "is designed to operate at high bandwidths
  (**400+ Gbps**) over medium-length (**10-150m**) links"; local networks
  target "**sub-microsecond latency**"; CC discussion assumes "target
  round-trip times of **10 µs**"; receiver ACKs carry "a **64-bit SACK
  bitmap**"; NSCC receiver feedback is "an **8B** congestion window penalty
  value"; CBFC uses "two **20-bit** cyclic counters"; worked congestion
  examples: RCCC "assigns **25%** of the bandwidth to each" of 4 incast
  flows; oversubscription example bottleneck "can only satisfy **33%** of
  the bandwidth"; UEC CM "is designed and tested in simulation" (evaluation
  deferred to GF-05's paper, which it cites).
- **Anchors:** **R1 design-target class** (use as ceiling/target anchors the
  same way CAL-A1/A2 are used, never as achieved values); protocol-constant
  scale (SACK bitmap, feedback sizes) for UEC-profile transport modeling.
- **Access:** public arXiv.
- **Confidence/caveats:** **M** — design targets and worked examples, not
  measurements; authored by consortium participants but published as a
  public paper (license-clean); no spec text ingested.

## Bonus axis — measured hop/pair latency (plan gap 2), extracted

### GF-10 — Li et al. (TPDS): V100/NVSwitch-era P2P latency numbers — the deferred p7 extraction, DONE
- **Citation:** W. Li A. Li et al., "Evaluating Modern GPU Interconnect:
  PCIe, NVLink, NV-SLI, NVSwitch and GPUDirect", IEEE TPDS 32(1), 2020/2019;
  arXiv:1903.04611; extracted from https://ar5iv.labs.arxiv.org/html/1903.04611
  (accessed 2026-10-27). (Listed in anchors_staging "additional candidates"
  as "per-pair µs latencies must be extracted at integration" — extracted
  here.)
- **Measured/system:** P100/V100 DGX-1 (PCIe + NVLink-1/2), DGX-2 (16× V100,
  6× NVSwitch), Summit; Tartan-suite P2P microbenchmarks.
- **Numbers (verbatim, prose-level):** NVLink directly-connected GPU pairs:
  P2P latency "around **9 µs**" (DGX-1); pairs needing manual routing:
  "increased by about **2x** for P100-DGX-1 and **3x** for V100-DGX-1"
  (⇒ ~18/~27 µs); NV-SLI system: local access ~**5 µs**, NV-SLI remote
  ~**8 µs**, PCIe remote ~**13 µs**; DGX-2 NVSwitch: remote-access latency
  homogeneous across all pairs, two-hop vs one-hop difference "very small,
  almost negligible"; per-link **50 GB/s bidirectional (25 GB/s per
  direction)**, 6 switches ⇒ 300 GB/s per GPU pair; DGX-2 baseboard
  bisection "25 GB/s × 8 links/switch × 6 switches = **2.4 TB/s**";
  NVLink V1/V2 bandwidth saturates at "about **2^22 = 4 MB**"; latency flat
  up to **16 KiB (P100) / 64 KiB (V100)**; SummitDev GPUDirect-RDMA peak
  "**12 GB/s at 64 MB**", PinnedMem-GPUDirect "**more than 14 GB/s**".
- **Anchors:** **measured hop/pair latency axis** (plan gap 2) — the µs-class
  P2P numbers that CAL-A10's 0.8 µs assumption-class value can finally be
  checked against (measured app-level P2P ≈ 9 µs on 2018-era NVLink — an
  order above the assumption; note app-level P2P includes software stack,
  so they bound different things — interpretation duty at integration);
  latency-flat region (≤ 64 KiB) empirically matches the small-message
  regime boundary used in the plan.
- **Access:** public arXiv/ar5iv.
- **Confidence/caveats:** **M-H** — prose numbers extracted verbatim from
  ar5iv HTML; the full per-pair matrices are heat-map figures (not
  text-extractable); V100-era values, one generation older than CAL-A4's
  domain.

### GF-11 — Speed-of-light GPU collectives (arXiv 2026): GB200 NVL72 small-message latency, decomposed (MEASURED)
- **Citation:** "Achieving Near Speed-of-Light Latency in GPU Collectives",
  arXiv:2607.16100 (2026); https://arxiv.org/html/2607.16100v1
  (accessed 2026-10-27).
- **Measured/system:** hardware microbenchmarks on **GB200 NVL72** (72 GPUs,
  130 TB/s aggregate) and Alps GH200 nodes ("four … GH200 … connected via
  150 GB/s NVLink"); baselines NCCL 2.29.1, NVSHMEM 3.5.21, MSCCL++ 0.8.0,
  vLLM 0.15.1 custom AllReduce; 128-B cache-line FP32; up to 64 CTAs × 512
  threads.
- **Numbers (verbatim):** on 2 GB200 GPUs "we measured the **LL2_RTT** and
  **Lremote_store** as **0.306 µs** and **0.792 µs**, respectively" ⇒
  speed-of-light AllReduce bound "**1.404 µs**" (L_SoL = 2·L_LL2_RTT +
  L_remote_store); "each barrier will incur more than **1 µs** of overhead";
  small-message AllReduce on 4 GB200s: "from **11.0 µs** for NCCL ring to
  **2.37 µs**" (new LLBuffer one-shot kernel); kernels "incur only about
  **7%** overhead over the SoL bound at 2 GPUs"; "Even at **64 GPUs**,
  multicast one-shot variants stay within roughly **70%** overhead of the
  SoL bound"; vLLM: "reduces ITL by **7–13%** on 4 GPUs and **9–11%** on 8
  GPUs"; "each μs removed from AllReduce latency reduces cost by about
  **0.9%**".
- **Anchors:** **small-message O-CCT on current-gen NVLink5 with exact
  software pins** (plan gap 3) — both a stock-NCCL point (11.0 µs) and a
  near-optimal point (2.37 µs), which bracket what any model may predict
  without accusing the fabric; **measured current-gen latency components**
  (plan gap 2): LL2 RTT 0.306 µs and remote store 0.792 µs are the first
  *current-generation* measured decomposition numbers staged — directly
  constrains `link.hop_latency_ns` / `pair_latency_ns` scale assumptions;
  4→64-GPU scaling of the overhead (7%→70%) is a multi-rank latency-scaling
  point.
- **Access:** public arXiv.
- **Confidence/caveats:** **H** (extracted from HTML; hardware measurements).
  Per-message-size latency table lives in a figure (not enumerated in text);
  author-run microbenchmarks, preprint.

---

## Coverage map (gap regime → staged anchors)

| Gap regime (gate/plan) | Staged anchors | Status after this pass |
|---|---|---|
| R1 UEC-class transport measurements | GF-05 (sim, NSCC basis, uet-htsim), GF-06 (UET-htsim + UCCL + CX-8), GF-08 (Falcon HW), GF-09 (design targets) | covered by simulation + one shipped non-UEC HW transport + design-target class; **UEC-1.x silicon measurements still do not exist publicly** |
| R2 large-message AllReduce, scale-up | GF-01 (MI300X), GF-02 (H100), GF-03 (B300) | covered on three GPU generations/fabrics beyond CAL-A3 |
| R3 congestion-management effects | GF-05, GF-06, GF-07 | covered (sim effect sizes + measured collective slowdown envelope 5%→25×); still no *scale-up-domain* congestion measurement |
| R4 multi-rank injection scaling | GF-04 (8→16), GF-11 (4→64 latency overhead) | first measured points; thin — only two series |
| Small-message O-CCT ≤ 64 KiB (plan gap 3) | GF-01 (13–17 µs MI300X), GF-11 (2.37–11 µs GB200), GF-04 (32 µs GPU↔GPU RoCE) | covered on both fabric classes |
| Measured hop/pair latency (plan gap 2) | GF-10 (9 µs-class V100-era), GF-11 (0.306/0.792 µs NVLink5 components), GF-03 (1.4–1.6 µs D2D) | measured axis now populated at component, microbenchmark, and collective levels |

## Additional candidates (found, NOT counted toward the ≥8 bar)

- **"High-speed Networking for Giga-Scale AI Factories"** (arXiv:2605.21187)
  — uses the NSX GPU-accelerated simulator for AI-factory networks; not
  extracted this pass; potential UEC-class simulation cross-check.
- **"PICO: Performance Insights for Collective Operations"** (arXiv:2508.16809)
  — reproducible collective performance evaluation methodology; not fetched.
- **UEC in-network-collectives position/analysis paper** (arXiv:2601.19132) —
  contains only a modeling example ("ring Allreduce 352 ms → 151 ms, ~60%
  speedup potential", Amdahl-capped at 11–34%), no experiments — excluded
  from anchors on the no-measurement rule; noted because it bounds INC
  expectations.
- **vpbenchmarking repo (Voltage Park, 32×H100 cluster)** —
  github.com/aigatech/vpbenchmarking; nvbandwidth/nccl tables likely inside;
  not fetched this pass.
- **Falcon NetDev 0x18 slides** —
  netdevconf.info/0x18/... Introduction_to_Falcon_Reliable_Transport.pdf;
  fetch failed URL validation in this sandbox; candidate for GF-08 expansion.

## Gaps that remain (FAIL-clause honesty)

1. **No public UEC 1.0/1.1 hardware measurements** — unchanged; R1 is covered
   by simulation (uet-htsim ×2), one shipped UEC-*class* hardware transport
   (Falcon), and design-target papers. A real UEC transport measurement study
   still does not exist as of 2026-10.
2. **No scale-up-domain congestion measurement** — GF-07's 5%→25× envelope is
   measured on scale-out HPC fabrics; NVSwitch/xGMI-domain congestion effects
   remain publicly unmeasured.
3. **Multi-rank injection scaling is thin** — two series (GF-04 8→16 GPU;
   GF-11 4→64 GPU latency overhead); no dense rank sweep (8/16/32/64/72) on
   one fabric.
4. **GF-02 vs GF-04 busbw discrepancy (360 vs 476 GB/s on 8×H100)** — staged
   unresolved; a counting-convention/NVLS/version audit is a required
   integration step before either is used as a calibration target.
5. **UALink silicon** — still nothing (unchanged from staging doc).

---

## Provenance log (research process, 2026-10-27, ~60 min, inside the 90-min box)

Web searches (queries as issued, in order):
1. `Ultra Ethernet transport performance evaluation arxiv`
2. `Falcon Google RDMA transport paper SIGCOMM latency lossless`
3. `MI300X NCCL allreduce busbw measured GB/s 8 GPUs benchmark`
4. `Benchmarking NVIDIA DGX H100 paper NCCL allreduce latency bandwidth arxiv`
5. `nvbandwidth H100 device to device bandwidth GB/s measured results`
6. `Ultra Ethernet congestion management evaluation simulation arxiv 2026`
7. `Evaluating Modern GPU Interconnect PCIe NVLink NVSwitch P2P latency microseconds Li TPDS`
8. `allreduce busbw scaling number of GPUs NVLink measured 8 16 32 ranks injection`
   (backend retried under the hood as `nccl-tests allreduce busbw NVLink scaling 8 16 32 GPUs injection` after one rate-limit)
9. `B300 NVLink allreduce nvbandwidth benchmark blog` (verification round)
10. `NVLink SHARP NVLS allreduce busbw GB200 measured` (verification round)

Page fetches (method → outcome):
- WebFetch `arxiv.org/html/2508.08906v1` → OK (GF-09 design targets; no
  measurement section exists — confirmed).
- WebFetch `arxiv.org/html/2610.13130v1` → OK (GF-06 full numbers).
- WebFetch `github.com/ROCm/rocm-blogs/discussions/598` → timeout; webReader
  same URL → partial; webReader `rocm.blogs.amd.com/.../README.html` mirror →
  OK (GF-01 full tables; overhead-percentage sentence flagged).
- WebFetch `blogs.oracle.com/...` → 403; webReader → OK ×2 (GF-04 tables).
- WebFetch `arxiv.org/html/2607.16100v1` → OK ×2 (GF-11).
- WebFetch `arxiv.org/html/2604.11432v1` → OK ×2 (GF-07).
- WebFetch `github.com/NVIDIA/nccl-tests/issues/326` → timeout ×2; webReader
  → OK (GF-02 title/saturation figure; body rows partially garbled — flagged).
- WebFetch `ar5iv.labs.arxiv.org/html/1903.04611` → OK (GF-10 prose numbers;
  per-pair matrices are heat-map figures, not extractable).
- WebFetch `cloud.google.com/.../introducing-falcon...` → timeout; webReader
  → qualitative only; WebFetch MSR publication mirror → OK (GF-08 abstract
  numbers).
- webReader NetDev Falcon slides PDF → URL-validation error (deferred to
  additional candidates).
- WebFetch `arxiv.org/html/2601.19132v1` → OK (no experiments — excluded from
  anchors, kept as context note).
- WebFetch `arxiv.org/html/2404.01630` → OK (GF-05).
- webReader `sixrackunits.substack.com/p/b300-field-notes...` → OK (GF-03).

License/scope discipline: no consortium or specification documents were
fetched or ingested (ultraethernet.org announcement appeared in search
results and was deliberately not opened; UEC/UALink spec documents remain
un-opened). No restricted text entered this research. All sources are public
web pages or public arXiv papers.
