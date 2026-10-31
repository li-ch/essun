# Cross-fabric comparison matrix — which profile outperforms which, under stated assumptions

Status **PROPOSED**, evidence level **E0 only**. Every comparable cell below is derived programmatically from content-addressed artifacts by `tools/cross_fabric_matrix.py` (verdicts, boundaries, and regions come from the orchestrator's own output, never from hand-typed conclusions; the tool's `--check` mode refuses a drift against this committed copy). Every value behind a cell is the output of a closed-form analytical identity under declared free parameters; the matrix ranks MODEL IDENTITIES, not hardware, and nothing here was measured on any system. No claim label upgrades from this page.

## What a fair comparison requires (the fairness bar)

- **Identical open choices.** Both profiles consume the ONE shared free-parameter record (`experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml`): B = 64 bytes/ns and L = 200 ns are one record's values fed unchanged to every flavor file. No public source on either side anchors a per-lane rate or per-hop latency usable at L0 (UBP-F01/UBP-F02 mark the UnifiedBus silence; UEC 1.1 fixes neither), so any ranking that differed through B or L would be an artifact of unequal inputs.
- **Pinned sources.** The UEC side runs the public-read UEC 1.1 semantic profile (license-cleared ingestion, 80 anchors); the UnifiedBus side is a PAPER-DERIVED design profile from five public papers (53 anchors) — not a normative standard profile (the specification track stays license-gated). UALink and CXL have no profile at all (license-blocked, never ingested).
- **Mechanisms stated, not smuggled.** The one executed mechanism asymmetry is the UEC TFC credit window (admission law UEC11-FC-R02; the exact 256-byte credit unit is the family's only standard-derived constant). The UnifiedBus side carries no window because its public sources are silent on flow control (UBP-F04) — declared silence, not a modeling shortcut.
- **Same workload, one operating point per artifact.** The platform's same-workload gate pins one W1 Dense TP Decode shape (2 layers x 3 steps = 6 AllReduce ops) and one tp_size per artifact, so every delta compares the same work.

## The pairs (columns)

- **UEC TFC window vs UnifiedBus-paper flat** — the two-profile pair: the UEC profile's flagship executed semantic (TFC admission law UEC11-FC-R02) on the free ring stand-in vs the UnifiedBus paper profile's ring stand-in with no window (public-source silence, UBP-F04).
- **UEC window-on vs window-off (mechanism ablation)** — the same-profile control: the windowed ring vs the identical unwindowed ring, isolating the admission-law term.
- **UEC crossbar stand-in vs UB-paper rack crossbar** — the identity-matched unwindowed pair at the UB-anchored rack scale 64 (UBP-P17): the delta-zero fairness anchor.

## The matrix

| observable / axis | UEC TFC window vs UnifiedBus-paper flat | UEC window-on vs window-off (mechanism ablation) | UEC crossbar stand-in vs UB-paper rack crossbar |
|---|---|---|---|
| **O-CCT — large-message completion across the payload grid** | unwindowed side wins or ties at every sampled point (3 artifacts: 2 payload corners x 2 rank corners); the exact boundary 25600 does not move with payload or rank count [9a5f1296…f016e0, 05b4afdf…02e730, 6d9a30db…bab119] | unwindowed side wins or ties at every sampled point (3 artifacts: 2 payload corners x 2 rank corners); the exact boundary 25600 does not move with payload or rank count [9a5f1296…f016e0, 05b4afdf…02e730, 6d9a30db…bab119] | TIE (exact) at all 10 payload-grid sizes and both committed cross-design sizes (delta exactly 0 everywhere) [242bacc4…64e985, 9d07ec4a…f72fb9] |
| **O-CCT — saturation boundary on the window axis (A-TFC-W)** | exact TIE on [25600, 1048576] (at and above the boundary 25600 on A-TFC-W); windowed side strictly worse on [256, 12800] (at and below it; never better at any sampled point: 9 strictly-worse / 15 tie grid points across this cell's artifacts) [9a5f1296…f016e0, 05b4afdf…02e730, 6d9a30db…bab119] | exact TIE on [25600, 1048576] (at and above the boundary 25600 on A-TFC-W); windowed side strictly worse on [256, 12800] (at and below it; never better at any sampled point: 9 strictly-worse / 15 tie grid points across this cell's artifacts) [9a5f1296…f016e0, 05b4afdf…02e730, 6d9a30db…bab119] | NOT COMPARABLE — the window axis does not exist for this pair: both comparators are unwindowed (the public UnifiedBus sources are silent on any flow-control mechanism, UBP-F04; the UEC crossbar stand-in declares no TFC binding at L0), so there is no window term to rank [—] |
| **O-CCT — ranking under swept shared bandwidth (A-XDUO-BW)** | exact TIE on [8, 64] (at and below the boundary 64 on A-XDUO-BW); windowed side strictly worse on [128, 1024] (at and above it; never better at any sampled point: 4 strictly-worse / 4 tie grid points across this cell's artifacts) [f2019c52…e4814b] | exact TIE on [8, 64] (at and below the boundary 64 on A-XDUO-BW); windowed side strictly worse on [128, 1024] (at and above it; never better at any sampled point: 4 strictly-worse / 4 tie grid points across this cell's artifacts) [f2019c52…e4814b] | NOT SAMPLED — the axis is shared and comparable in principle (both identities consume the same bind), but no envelope sweeps it for this pair; the two identities are the same function of the shared parameters, so the tie is an arithmetic identity, sampled only at the payload grid's fixed operating point [—] |
| **O-CCT — ranking under swept shared hop latency (A-XDUO-LAT)** | exact TIE on [25, 200] (at and below the boundary 200 on A-XDUO-LAT); windowed side strictly worse on [400, 1600] (at and above it; never better at any sampled point: 3 strictly-worse / 4 tie grid points across this cell's artifacts) [81f555ea…3b8554] | exact TIE on [25, 200] (at and below the boundary 200 on A-XDUO-LAT); windowed side strictly worse on [400, 1600] (at and above it; never better at any sampled point: 3 strictly-worse / 4 tie grid points across this cell's artifacts) [81f555ea…3b8554] | NOT SAMPLED — the axis is shared and comparable in principle (both identities consume the same bind), but no envelope sweeps it for this pair; the two identities are the same function of the shared parameters, so the tie is an arithmetic identity, sampled only at the payload grid's fixed operating point [—] |
| **O-CONSERVATION — wire-byte ledger** | TIE (exact): the window gates rate, never bytes — per-rank wire traffic is the same identity on both sides of every pair [9a5f1296…f016e0, 05b4afdf…02e730, 6d9a30db…bab119, f2019c52…e4814b, 81f555ea…3b8554] | TIE (exact): the window gates rate, never bytes — per-rank wire traffic is the same identity on both sides of every pair [9a5f1296…f016e0, 05b4afdf…02e730, 6d9a30db…bab119, f2019c52…e4814b, 81f555ea…3b8554] | TIE (exact): identical per-rank wire ledger 2*(r-1)/r * M at every payload, 0 conservation violations in every row [242bacc4…64e985, 9d07ec4a…f72fb9] |

## Artifact ids (full, content-addressed)

| short ref | artifact id | kind |
|---|---|---|
| `9a5f1296…f016e0` | `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0` | envelope |
| `05b4afdf…02e730` | `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730` | envelope |
| `6d9a30db…bab119` | `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119` | envelope |
| `242bacc4…64e985` | `242bacc4eb94acb3d94f6b8c00d59aabf64a649785be4c3883c5c48f4c64e985` | sweep |
| `9d07ec4a…f72fb9` | `9d07ec4a460535f6509ea62083ea73c8302ba8e178ecbc2746e5a71f18f72fb9` | sweep |
| `f2019c52…e4814b` | `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b` | envelope |
| `81f555ea…3b8554` | `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554` | envelope |

## Per-row evidence

### O-CCT — large-message completion across the payload grid

**UEC TFC window vs UnifiedBus-paper flat.**

- Verdict: unwindowed side wins or ties at every sampled point (3 artifacts: 2 payload corners x 2 rank corners); the exact boundary 25600 does not move with payload or rank count.
- Winner: unwindowed side, strictly, at every window below the boundary; TIE at and above.
- Flip condition: flip condition independent of payload and rank count: tie iff W >= B*(L+L_cr) (the threshold carries no M and no r term); the below-boundary penalty scales with the per-rank traffic T = 2*(r-1)/r * M.
- Artifacts: `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0`, `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730`, `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119`.
- Per operating point (strictly-worse / tie window points, worst penalty ns, exact boundary): ranks 1024, payload 1048576 B: 3 / 5, 3240864 ns, 25600; ranks 256, payload 1048576 B: 3 / 5, 3231360 ns, 25600; ranks 1024, payload 16777216 B: 3 / 5, 51853824 ns, 25600.

**UEC window-on vs window-off (mechanism ablation).**

- Verdict: unwindowed side wins or ties at every sampled point (3 artifacts: 2 payload corners x 2 rank corners); the exact boundary 25600 does not move with payload or rank count.
- Winner: unwindowed side, strictly, at every window below the boundary; TIE at and above.
- Flip condition: flip condition independent of payload and rank count: tie iff W >= B*(L+L_cr) (the threshold carries no M and no r term); the below-boundary penalty scales with the per-rank traffic T = 2*(r-1)/r * M.
- Artifacts: `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0`, `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730`, `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119`.
- Per operating point (strictly-worse / tie window points, worst penalty ns, exact boundary): ranks 1024, payload 1048576 B: 3 / 5, 3240864 ns, 25600; ranks 256, payload 1048576 B: 3 / 5, 3231360 ns, 25600; ranks 1024, payload 16777216 B: 3 / 5, 51853824 ns, 25600.

**UEC crossbar stand-in vs UB-paper rack crossbar.**

- Verdict: TIE (exact) at all 10 payload-grid sizes and both committed cross-design sizes (delta exactly 0 everywhere).
- Winner: neither (delta exactly 0 by construction).
- Flip condition: no flip exists: the two rows are the same identity under the one shared B/L record (A-XDUO-BW / A-XDUO-LAT), so every payload size ties; the UB side's only anchored difference (rack scale 64, UBP-P17) is matched by the UEC stand-in's chosen scale.
- Artifacts: `242bacc4eb94acb3d94f6b8c00d59aabf64a649785be4c3883c5c48f4c64e985`, `9d07ec4a460535f6509ea62083ea73c8302ba8e178ecbc2746e5a71f18f72fb9`.
- Payload grid (bytes): 4096, 8192, 16384, 65536, 131072, 262144, 1048576, 2097152, 4194304, 16777216; per-rank wire ledger and completion time identical at every size (see the sweep tables' delta columns, all exactly 0).

### O-CCT — saturation boundary on the window axis (A-TFC-W)

**UEC TFC window vs UnifiedBus-paper flat.**

- Verdict: exact TIE on [25600, 1048576] (at and above the boundary 25600 on A-TFC-W); windowed side strictly worse on [256, 12800] (at and below it; never better at any sampled point: 9 strictly-worse / 15 tie grid points across this cell's artifacts).
- Winner: unwindowed side on [256, 12800]; neither on the tie region [25600, 1048576].
- Flip condition: exact boundary 25600 on A-TFC-W, secant-resolved and verified by re-execution in every artifact of this cell; closed form: the windowed identity ties iff the granted window covers the bandwidth-delay product W >= B*(L+L_cr) — the same boundary W* = B*(L+L_cr) read in whichever variable the artifact sweeps (W itself, B at fixed W, or L at fixed W).
- Artifacts: `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0`, `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730`, `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119`.
- Verified exact boundaries (bracket, method, artifact): ranks 1024, payload 1048576 B: 25600 on bracket ['12800', '25600'] (affine-x-verified, 9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0); ranks 256, payload 1048576 B: 25600 on bracket ['12800', '25600'] (affine-x-verified, 05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730); ranks 1024, payload 16777216 B: 25600 on bracket ['12800', '25600'] (affine-x-verified, 6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119).
- Ranking regions (grid evidence, exact endpoints): ranks 1024, payload 1048576 B, axis A-TFC-W: comparator_a_ranks_worse on [256, 12800] (artifact 9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0); ranks 1024, payload 1048576 B, axis A-TFC-W: exact_tie on [25600, 1048576] (artifact 9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0); ranks 256, payload 1048576 B, axis A-TFC-W: comparator_a_ranks_worse on [256, 12800] (artifact 05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730); ranks 256, payload 1048576 B, axis A-TFC-W: exact_tie on [25600, 1048576] (artifact 05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730); ranks 1024, payload 16777216 B, axis A-TFC-W: comparator_a_ranks_worse on [256, 12800] (artifact 6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119); ranks 1024, payload 16777216 B, axis A-TFC-W: exact_tie on [25600, 1048576] (artifact 6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119).

**UEC window-on vs window-off (mechanism ablation).**

- Verdict: exact TIE on [25600, 1048576] (at and above the boundary 25600 on A-TFC-W); windowed side strictly worse on [256, 12800] (at and below it; never better at any sampled point: 9 strictly-worse / 15 tie grid points across this cell's artifacts).
- Winner: unwindowed side on [256, 12800]; neither on the tie region [25600, 1048576].
- Flip condition: exact boundary 25600 on A-TFC-W, secant-resolved and verified by re-execution in every artifact of this cell; closed form: the windowed identity ties iff the granted window covers the bandwidth-delay product W >= B*(L+L_cr) — the same boundary W* = B*(L+L_cr) read in whichever variable the artifact sweeps (W itself, B at fixed W, or L at fixed W).
- Artifacts: `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0`, `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730`, `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119`.
- Verified exact boundaries (bracket, method, artifact): ranks 1024, payload 1048576 B: 25600 on bracket ['12800', '25600'] (affine-x-verified, 9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0); ranks 256, payload 1048576 B: 25600 on bracket ['12800', '25600'] (affine-x-verified, 05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730); ranks 1024, payload 16777216 B: 25600 on bracket ['12800', '25600'] (affine-x-verified, 6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119).
- Ranking regions (grid evidence, exact endpoints): ranks 1024, payload 1048576 B, axis A-TFC-W: comparator_a_ranks_worse on [256, 12800] (artifact 9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0); ranks 1024, payload 1048576 B, axis A-TFC-W: exact_tie on [25600, 1048576] (artifact 9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0); ranks 256, payload 1048576 B, axis A-TFC-W: comparator_a_ranks_worse on [256, 12800] (artifact 05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730); ranks 256, payload 1048576 B, axis A-TFC-W: exact_tie on [25600, 1048576] (artifact 05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730); ranks 1024, payload 16777216 B, axis A-TFC-W: comparator_a_ranks_worse on [256, 12800] (artifact 6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119); ranks 1024, payload 16777216 B, axis A-TFC-W: exact_tie on [25600, 1048576] (artifact 6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119).

**UEC crossbar stand-in vs UB-paper rack crossbar.**

- Verdict: NOT COMPARABLE — the window axis does not exist for this pair: both comparators are unwindowed (the public UnifiedBus sources are silent on any flow-control mechanism, UBP-F04; the UEC crossbar stand-in declares no TFC binding at L0), so there is no window term to rank.

### O-CCT — ranking under swept shared bandwidth (A-XDUO-BW)

**UEC TFC window vs UnifiedBus-paper flat.**

- Verdict: exact TIE on [8, 64] (at and below the boundary 64 on A-XDUO-BW); windowed side strictly worse on [128, 1024] (at and above it; never better at any sampled point: 4 strictly-worse / 4 tie grid points across this cell's artifacts).
- Winner: unwindowed side on [128, 1024]; neither on the tie region [8, 64].
- Flip condition: exact boundary 64 on A-XDUO-BW, secant-resolved and verified by re-execution in every artifact of this cell; closed form: the windowed identity ties iff the granted window covers the bandwidth-delay product W >= B*(L+L_cr) — the same boundary W* = B*(L+L_cr) read in whichever variable the artifact sweeps (W itself, B at fixed W, or L at fixed W).
- Artifacts: `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b`.
- Verified exact boundaries (bracket, method, artifact): ranks 1024, payload 1048576 B: 64 on bracket ['64', '128'] (affine-x-verified, f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b).
- Ranking regions (grid evidence, exact endpoints): ranks 1024, payload 1048576 B, axis A-XDUO-BW: exact_tie on [8, 64] (artifact f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b); ranks 1024, payload 1048576 B, axis A-XDUO-BW: comparator_a_ranks_worse on [128, 1024] (artifact f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b).

**UEC window-on vs window-off (mechanism ablation).**

- Verdict: exact TIE on [8, 64] (at and below the boundary 64 on A-XDUO-BW); windowed side strictly worse on [128, 1024] (at and above it; never better at any sampled point: 4 strictly-worse / 4 tie grid points across this cell's artifacts).
- Winner: unwindowed side on [128, 1024]; neither on the tie region [8, 64].
- Flip condition: exact boundary 64 on A-XDUO-BW, secant-resolved and verified by re-execution in every artifact of this cell; closed form: the windowed identity ties iff the granted window covers the bandwidth-delay product W >= B*(L+L_cr) — the same boundary W* = B*(L+L_cr) read in whichever variable the artifact sweeps (W itself, B at fixed W, or L at fixed W).
- Artifacts: `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b`.
- Verified exact boundaries (bracket, method, artifact): ranks 1024, payload 1048576 B: 64 on bracket ['64', '128'] (affine-x-verified, f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b).
- Ranking regions (grid evidence, exact endpoints): ranks 1024, payload 1048576 B, axis A-XDUO-BW: exact_tie on [8, 64] (artifact f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b); ranks 1024, payload 1048576 B, axis A-XDUO-BW: comparator_a_ranks_worse on [128, 1024] (artifact f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b).

**UEC crossbar stand-in vs UB-paper rack crossbar.**

- Verdict: NOT SAMPLED — the axis is shared and comparable in principle (both identities consume the same bind), but no envelope sweeps it for this pair; the two identities are the same function of the shared parameters, so the tie is an arithmetic identity, sampled only at the payload grid's fixed operating point.

### O-CCT — ranking under swept shared hop latency (A-XDUO-LAT)

**UEC TFC window vs UnifiedBus-paper flat.**

- Verdict: exact TIE on [25, 200] (at and below the boundary 200 on A-XDUO-LAT); windowed side strictly worse on [400, 1600] (at and above it; never better at any sampled point: 3 strictly-worse / 4 tie grid points across this cell's artifacts).
- Winner: unwindowed side on [400, 1600]; neither on the tie region [25, 200].
- Flip condition: exact boundary 200 on A-XDUO-LAT, secant-resolved and verified by re-execution in every artifact of this cell; closed form: the windowed identity ties iff the granted window covers the bandwidth-delay product W >= B*(L+L_cr) — the same boundary W* = B*(L+L_cr) read in whichever variable the artifact sweeps (W itself, B at fixed W, or L at fixed W).
- Artifacts: `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554`.
- Verified exact boundaries (bracket, method, artifact): ranks 1024, payload 1048576 B: 200 on bracket ['200', '400'] (affine-x-verified, 81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554).
- Ranking regions (grid evidence, exact endpoints): ranks 1024, payload 1048576 B, axis A-XDUO-LAT: exact_tie on [25, 200] (artifact 81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554); ranks 1024, payload 1048576 B, axis A-XDUO-LAT: comparator_a_ranks_worse on [400, 1600] (artifact 81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554).

**UEC window-on vs window-off (mechanism ablation).**

- Verdict: exact TIE on [25, 200] (at and below the boundary 200 on A-XDUO-LAT); windowed side strictly worse on [400, 1600] (at and above it; never better at any sampled point: 3 strictly-worse / 4 tie grid points across this cell's artifacts).
- Winner: unwindowed side on [400, 1600]; neither on the tie region [25, 200].
- Flip condition: exact boundary 200 on A-XDUO-LAT, secant-resolved and verified by re-execution in every artifact of this cell; closed form: the windowed identity ties iff the granted window covers the bandwidth-delay product W >= B*(L+L_cr) — the same boundary W* = B*(L+L_cr) read in whichever variable the artifact sweeps (W itself, B at fixed W, or L at fixed W).
- Artifacts: `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554`.
- Verified exact boundaries (bracket, method, artifact): ranks 1024, payload 1048576 B: 200 on bracket ['200', '400'] (affine-x-verified, 81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554).
- Ranking regions (grid evidence, exact endpoints): ranks 1024, payload 1048576 B, axis A-XDUO-LAT: exact_tie on [25, 200] (artifact 81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554); ranks 1024, payload 1048576 B, axis A-XDUO-LAT: comparator_a_ranks_worse on [400, 1600] (artifact 81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554).

**UEC crossbar stand-in vs UB-paper rack crossbar.**

- Verdict: NOT SAMPLED — the axis is shared and comparable in principle (both identities consume the same bind), but no envelope sweeps it for this pair; the two identities are the same function of the shared parameters, so the tie is an arithmetic identity, sampled only at the payload grid's fixed operating point.

### O-CONSERVATION — wire-byte ledger

**UEC TFC window vs UnifiedBus-paper flat.**

- Verdict: TIE (exact): the window gates rate, never bytes — per-rank wire traffic is the same identity on both sides of every pair.
- Winner: neither.
- Flip condition: no flip can exist at L0: the admission law (and its cell and overhead constants) spend credit without moving modeled bytes; every envelope evaluation re-runs the backend's structural conservation self-check.
- Artifacts: `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0`, `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730`, `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119`, `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b`, `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554`.

**UEC window-on vs window-off (mechanism ablation).**

- Verdict: TIE (exact): the window gates rate, never bytes — per-rank wire traffic is the same identity on both sides of every pair.
- Winner: neither.
- Flip condition: no flip can exist at L0: the admission law (and its cell and overhead constants) spend credit without moving modeled bytes; every envelope evaluation re-runs the backend's structural conservation self-check.
- Artifacts: `9a5f1296b5616f5bac356482bb4156bb8a2e65b631e1dd5b52915f962af016e0`, `05b4afdf531014bbed50174b8ad8ead6a777ef9994bdd23ff3e9331e7302e730`, `6d9a30db5a3861de7ca4b7932e52c12e741eae345fd88cc1787f3a8ccabab119`, `f2019c52dcee5392cd8b5dec6925bff47178e65e6147fd03b6f0764f68e4814b`, `81f555ea055c204b12d70a87aab929b0357c77412033fdc85c92f4230d3b8554`.

**UEC crossbar stand-in vs UB-paper rack crossbar.**

- Verdict: TIE (exact): identical per-rank wire ledger 2*(r-1)/r * M at every payload, 0 conservation violations in every row.
- Winner: neither; the flavor labels move no bytes.
- Flip condition: no flip can exist: both identities emit the same wire traffic per rank; the sweep runner checks the ledger per row and the backends self-check it structurally.
- Artifacts: `242bacc4eb94acb3d94f6b8c00d59aabf64a649785be4c3883c5c48f4c64e985`, `9d07ec4a460535f6509ea62083ea73c8302ba8e178ecbc2746e5a71f18f72fb9`.

## Scope: what this matrix does NOT compare (and why)

- **UALink and CXL: no column.** Their specification documents are license-restricted and were never ingested (license review precedes ingestion); there is no profile, so no pair and no cell exists. Any UALink or CXL comparison number from this platform would be fabricated.
- **UnifiedBus normative semantics: license-blocked.** The UnifiedBus column is a paper-derived design profile; cells name it as such everywhere.
- **Hierarchy and multi-level fabrics: NOT COMPARABLE (fidelity).** The UnifiedBus paper's hierarchical full-mesh with asymmetric per-level widths, memory semantics, APR routing, and the pod-of-racks hierarchy need L1 fidelity, which no landed backend executes; the envelope same-workload gate also pins one tp_size per artifact.
- **Credit-cell and packet-overhead laws (UEC11-FC-R08/R09): NOT COMPARABLE cross-profile.** These UEC-side refinements of the credit-consumption law have no UnifiedBus counterpart (UBP-F04 silence); they refine the windowed side only and appear in no cross cell.
- **Congestion, packetization, collective overlap: out of scope at L0** (declared unsupported by every backend involved).
- **Shared-axis cells for the identity-matched crossbar pair are NOT SAMPLED** (see matrix): the tie is an arithmetic identity there, and the payload grid samples it at ten payloads; sweeping B or L for that pair would add no information the identity does not already fix.

## How to reproduce

```bash
# every artifact the matrix cites (deterministic; byte-identical on replay)
.venv/bin/python -m essun.orchestrator.sweeps \
  experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml
.venv/bin/python -m essun.orchestrator.sweeps \
  experiments/sweeps/cross_fabric_payload_grid_v1.yaml
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_boundary_v1.yaml
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_boundary_tp256_v1.yaml
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_boundary_payload16m_v1.yaml
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_bw_boundary_v1.yaml
.venv/bin/python -m essun.orchestrator.envelopes \
  experiments/envelopes/uec_vs_ub_window_lat_boundary_v1.yaml
# regenerate this page and refuse a drift against the committed copy
.venv/bin/python tools/cross_fabric_matrix.py --check
```

Generated deterministically from the committed manifests (exact Fractions, canonical order, no wall-clock); byte-identical on replay.
