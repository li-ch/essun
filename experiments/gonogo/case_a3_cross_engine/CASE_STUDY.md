# G7 leg (a) — reproducing one published comparison across two engines: where re-derivation breaks

Date: 2026-10-30. Status: **PROPOSED**. Evidence: exact-Fraction audit
over 17 content-addressed engine executions against one published
external measurement (compared CCT-vs-CCT; no tuning toward the anchor;
no label upgrades). Record: `case_record_v1.json` (built by
`build_case_record.py`, byte-identical regeneration enforced; guard test
`tests/calibration/test_gonogo_case.py`). This is the **motivation case
study** the OSDI review asked for: "Reconstructing even one actual
published comparison — and showing precisely where specification
freedom, omitted assumptions, or observable semantics undermine it."

## What was published

Anchor **CAL-A3** (staged at `docs/calibration/anchors_staging.md` §A3;
public Crusoe Cloud support article; transcription confidence M-H):
`all_reduce_perf` on all 72 GPUs of a GB200 NVL72 rack, NCCL 2.28.3 /
CUDA 12.9.1 / driver 580.82.07, 10 warmup / 20 iterations, out-of-place,
2–32 GiB per rank. Published per-size time and **busbw** (out-of-place
series): 2 GiB 5375.10 µs / 787.95 GB/s; 4 GiB 10193.01 / 831.03; 8 GiB
19555.07 / 866.36; 16 GiB 38056.60 / 890.32; 32 GiB 74718.41 / 906.94.
The article also sets `NCCL_IB_HCA` guidance, so the NVLink-vs-IB path
split of the 72-GPU communicator is not stated (staging caveat) — an
omitted assumption before any modeling begins.

## The two engines

- **Engine A — essun L0** (in-process): the fabric-matched single-port
  crossbar identity `t = 2(r−1)/r·M/B + 2L` at r=72, executed at the S2
  minimax diagnostic **B_fit = 827.1827 B/ns** (fitted on the {2,4,8}
  GiB rows only, carried unchanged) and at the CAL-A2 vendor ceiling
  line **B = 900**; plus the **ring twin** `t = 2(r−1)/r·M/B + 2(r−1)L`
  at **B = 828**.
- **Engine B — ASTRA-sim analytical** (pinned external Docker image
  `essun/astra-sim-analytical:s1`, commit 4ce9ecfe, congestion-unaware
  frontend, native Ring AllReduce): run at B = 828 on the **identical
  topology and workload bytes** as engine A's ring twin.

Payloads are the S2 floor brackets (largest 72-divisible ≤ the published
power-of-two sizes; relative shortfall ≤ 2.7·10⁻⁸ — the identities'
divisibility guards reject the exact sizes at r=72, itself a modeling-
grid freedom the publication is silent on). 17 run records with v2
evidence dimensions (ids in the case record).

## Finding 1 — the published observable is a convention, and the convention's algorithm assumption fails at the top of the series

Re-derived exactly: `algbw = M/t` and `busbw_recomputed = algbw ·
2(r−1)/r` reproduce the published busbw at every size to ≤ 0.024 GB/s
(publication rounding of t). So the published number **is** the NCCL
ring-convention quantity — per-rank wire traffic over time **under the
assumption the collective ran a ring algorithm with per-rank traffic
2(r−1)/r·M**.

Now read it against the vendor line (CAL-A2: 900 GB/s per GPU per
direction). Under the ring reading, the published busbw is **87.55% →
100.77%** of the line across the series — it **crosses 100% between 16
and 32 GiB**: at 32 GiB the ring reading asserts each GPU egressed
906.94 B/ns through a 900 B/ns line (0.77% above the vendor ceiling).
Under a multicast/in-network-reduction reading (per-GPU egress = M/t =
algbw — the shape GB200's NVLink SHARP provides), the same number is
**44.4% → 51.1%** of the line. The publication does not state the
algorithm; the two readings differ by the exact factor **2(r−1)/r =
71/36 = 1.9722**. One published number, two admissible wire-traffic
identities: the fabric-utilization claim is underdetermined by a factor
of ~2 — and the ring reading, taken literally, is excluded by the
vendor line exactly at the largest size.

## Finding 2 — no fabric parameter re-derives the series; the curvature is software

At the S2 minimax **B_fit** (already fitted on the {2,4,8} GiB rows —
the best admissible single fixed-B under the declared freedom), engine
A's deviations run **−4.74% (2 GiB) → +9.64% (32 GiB held out)**. The
published time *falls* with size relative to any fixed-B identity: the
missing term is NCCL 2.28.3's size-dependent software-effective
bandwidth (channel/SM/chunk scheduling), not fabric physics — the S2
known-omission finding, now executed inside a cross-engine record. The
vendor ceiling line itself is crossed by the published series: at
B = 900 engine A is **−1.07% at 16 GiB and +0.77% at 32 GiB** — the
same crossing Finding 1 exposes from the observable side. The article's
own in-place 2 GiB row (5.20 GB/s vs 787.95 out-of-place — a ~151×
software-stack swing acknowledged in the source) bounds how much of the
"bandwidth" belongs to the stack, not the fabric.

## Finding 3 — the two engines disagree with each other by ~the same factor the convention is ambiguous

At **identical topology and workload bytes**, engine B (ASTRA-sim Wall
time) lands **+80.2% (32 GiB) to +118.1% (2 GiB)** above engine A's ring
identity (+96.6% to +108.7% above the published time). This is not an
error: the two "completion times" are different observables. Engine B's
Wall bundles translation knobs with no counterpart in the publication
and no manifest counterpart in engine A: `endpoint-delay = 10`
(A-AS2-DELAY-POS, the pinned binary aborts at 0), `local-mem-bw = 1600`
with per-bundle 3·size/local-mem-bw processing (A-AS2-MEM-BW), and
`active-chunks-per-dimension = 1` (A-AS1-CHUNKS-1) — every one an
omitted assumption the publication cannot arbitrate. And the fitted
optimum itself is **not expressible** in engine B's input convention:
B_fit is a non-integer rational, and the adapter's exact GB/s
translation (A-AS1-BW-UNIT, 1 GB = 2³⁰ B) rejects non-dyadic bandwidths
by design rather than rounding silently — the twin runs at the nearest
admissible integer, +0.0988% above B_fit.

## The audit table (every number exact in the record)

| Size | busbw as % of 900 line (ring / multicast reading) | Engine A crossbar @B_fit dev | Engine A crossbar @900 dev | Engine A ring @828 dev | Engine B ASTRA @828 dev | Twin Δ (B over A-ring) |
|---|---|---|---|---|---|---|
| 2 GiB | 87.55% / 44.39% | −4.74% | — | −4.31% | +108.67% | +118.1% |
| 4 GiB | 92.34% / 46.82% | +0.47% | — | +0.64% | +99.16% | +97.9% |
| 8 GiB | 96.26% / 48.81% | +4.74% | — | +4.78% | +96.77% | +87.8% |
| 16 GiB | 98.92% / 50.16% | +7.63% | −1.07% | +7.60% | +96.62% | +82.7% |
| 32 GiB | **100.77%** / 51.10% | +9.64% | **+0.77%** | +9.57% | +97.41% | +80.2% |

Underdetermined degrees of freedom, each quantified: the
algorithm/traffic identity (1.9722× on inferred utilization; decides
whether the 32 GiB row is above or at half the vendor line); the B
derating and its size ramp (−4.7%…+9.6% at the best fixed B; ceiling
crossed); NCCL channel/SM configuration (151× in-place outlier); the
engine-B translation knobs (+80–118% twin delta); the payload
divisibility grid (2.7·10⁻⁸); the NVLink/IB split (unstated); warmup and
iteration protocol (unstated); in-place vs out-of-place (staged
separately by the article).

## Conclusion (the motivation)

The published comparison re-derives only as a **joint statement about
fabric parameters, one NCCL version's software behavior, and an
observable convention**. Neither engine — nor both together — can land
on it from the published quantities, because the quantities do not fix
the observable's definition, the algorithm, or the software
configuration; and the two engines' own disagreement (~2×) is of the
same order as the convention ambiguity (~2×). This is precisely the
failure mode the platform's observable registry, assumption ledgers,
and translation-obligation declarations exist to make explicit — and
precisely why a "busbw" number cannot be compared against a simulator
without executing the convention alongside the model.
