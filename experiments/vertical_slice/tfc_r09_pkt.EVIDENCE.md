# Credit-family S3 evidence record — UEC11-FC-R09 as simulated_behavior

G2 credit-window family ladder (milestone v0.2.0 criterion 2) stage S3,
per the S1 plan in `experiments/uec/credit_family_inventory.md`. Date:
2026-10-30. Owner review: pending (the platform-side facts below are what
the owner reviews).

## Labels (read first)

- Platform status: **IMPLEMENTED_UNVERIFIED** (the chain executes and its
  golden tests pass; no external review yet).
- Evidence level: **E0** — identity and determinism only. No empirical
  claim is made.
- **`simulated_behavior` is a claim about the BINDING** (the requirement's
  per-packet overhead constant causally affects backend outputs through
  the declared, load-checked parameter `tfc.pkt_overhead` composing
  `tfc_pkt_size = payload + overhead` inside the S2 ROUNDUP law),
  **not a claim of physical validity**: nothing here is calibrated
  against UEC hardware. B, L, W, L_cr (flagship values, shared on
  purpose), the cell (S2's free parameter, domain R07-cited) and the
  overhead value itself are FREE — the overhead constrained only to the
  spec-cited bounds. Spec-derived values in the chain: the 256-byte
  credit unit (UEC11-FC-R05), the overhead DEFAULT 256 B (UEC11-FC-R09)
  and the overhead configurability bounds 0..256 B (UEC11-FC-R10 — whose
  recommendation disposition stays `unsupported`; values in, obligation
  out, the S2/R07 pattern). The MUST's same-constant-at-both-ends
  property is STRUCTURAL in one model (one constant), stated as
  structure, not claimed as executed.

## The chain

| Link | Artifact |
| --- | --- |
| Anchored requirement | **UEC11-FC-R09** (UEC 1.1 §3.6.15, TFC, MUST) — source and destination must use the same constant `tfc_pkt_overhead` (default 256 B, one credit unit), covering extra destination memory per packet because packet sizes can change in transit; anchor `UEC11-S3.6.15-TFC` (verified by the anchor registry's re-hash on every registry test) |
| Machine-readable binding | `BIND-UEC11-FC-R09-L0TFC` — `src/essun/specir/bindings.py` (registry-gated: requirement, anchors, backend capability/parameter, observables, R09/R10-cited constants re-verified live; gate test `tests/specir/test_bindings.py`; binding-coverage property `tests/specir/test_binding_coverage.py`) |
| Backend capability / parameter effect | `analytical_l0_tfc` — `src/essun/backends/analytical/l0_tfc.py`, capability `tfc_credit_windowed_ring`; the OPT-IN parameter `tfc.pkt_overhead` (requires a declared cell — the ROUNDUP it feeds is the cell law) composes the packet `tfc_pkt_size = c + tfc_pkt_overhead` (ring chunk `c = M/r` as the UET payload), so `cq = ROUNDUP(tfc_pkt_size/cell) × cell` and the effective data rate is `min(B, (c/cq) · W/(L+L_cr))` — the overhead spends credit without moving modeled bytes; `t = 2*(r-1)/r · M / min(B, (c/cq)·W/(L+L_cr)) + 2*(r-1)*L` |
| Executed golden test | `tests/golden/test_l0_tfc_pkt_golden.py` — every expected value derived IN the test by exact `Fraction` arithmetic (the R08 worked example's native composition 4096+256 = 4352 B against 512-B cells ⇒ 4608 B; the spec-default point cell 256/overhead 256 ⇒ 3808 ns with the +112 ns/op exact delta vs the overhead-less S2 identity; the overhead-is-cell-quantized law — any 1..256 B overhead at an aligned 256-B cell lands the same 9th cell; the causal move at cell 2048 ⇒ 4592 ns (+896 exact); the per-packet strategy cell 9216 absorbing the whole default overhead ⇒ exactly the S2 6832 ns; convergence `overhead = 0` ⇒ the S2 identity at every cell, and `overhead = 0 ∧ c ≡ 0 (mod cell)` ⇒ the landed R02 identity 3696 ns exactly; out-of-domain overheads rejected at load citing UEC11-FC-R10 with boundaries 0/256 accepted, and overhead-without-cell rejected citing the binding) |
| Observable change | **O-CCT**: 3808 ns mean at the spec-default point (cell 256, overhead 256: packet 2304 = 9 cells, efficiency 2048/2304 = 8/9, rate 256/9 B/ns) vs 3696 ns for the identical B/L/W/L_cr on the overhead-less S2 identity — a +112 ns exact per-op delta = `T·(1/Rd − 1/R02_rate)` — with **O-CONSERVATION unchanged** (the overhead constant gates credit consumption, never wire byte count) |
| Modeling choices (registered) | `experiments/vertical_slice/assumptions_tfc_pkt.yaml` — A-TFCP-PKT-OVH (the overhead value, free in the R10-cited bounds; 256 = the spec default), A-TFCP-OVH-BUFFER (overhead-as-destination-buffer-accounting only — header wire serialization is the packetization exclusion; wire ledger unchanged), A-TFCP-CHUNK-PKT (ring chunk = the UET payload of the composition), A-TFCP-FLUID, A-TFCP-CELL, plus the shared B/L/W/L_cr/DIV entries |
| Evidence run | run_id `834c1ffe94689654753727186039f08486e09030328da880ad0ae23724f83484` (content-addressed, `evidence_schema_version: 2`, `calibration_target: []`, `held_out: false` — E0 identity/determinism only; manifest `experiments/vertical_slice/w1_decode_tfc_pkt.yaml`; observations carry provenance for ALL THREE bindings — R02's window block, R08's cell block, R09's pkt block); claim link `C-UEC-TFC-R09` in `results/claims_index.jsonl` |

Re-verify in one line each:

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_pkt_golden.py tests/specir/test_bindings.py
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_tfc_pkt.yaml
# -> run_id 834c1ffe94689654753727186039f08486e09030328da880ad0ae23724f83484 (byte-identical)
```

## Design decisions specific to this slice

- **Opt-in parameter; earlier run identities frozen.** `tfc.pkt_overhead`
  is declared in the topology (`experiments/topologies/ring8_tfc_pkt_window_v1.yaml`);
  topologies without it run the S2 law byte-identically (the flagship run
  `dc7d83b6…` and the S2 cell run `e74ecec2…` both reproduce unchanged
  from their unchanged manifests — re-verified at this commit). The
  parameter rides run identity through the infra-graph input hash; an
  overhead never silently appears or vanishes.
- **Separate assumptions file.** `assumptions_tfc_pkt.yaml` (not an append
  to `assumptions_tfc.yaml` or `assumptions_tfc_cell.yaml`): the
  assumptions file is a hashed manifest input, so appending would have
  shifted an earlier run's identity. Same house rule as S2.
- **R10 cited, not executed.** The configurability bounds 0..256 B are
  carried as named constants citing UEC11-FC-R10 and enforced at load;
  R10's SHOULD disposition stays `unsupported` (configurability
  recommendation for implementations — no admissible-config enforcement
  path exists). The default 256 B cites R09's own text. Same pattern as
  S2's R07 domain.
- **The spec-default point for the evidence run.** Cell 256 B (R07's
  default) + overhead 256 B (R09's default): the run prices the DEFAULT
  configuration — every packet spends exactly one extra credit unit at
  the aligned cell (efficiency 8/9, +112 ns/op over the overhead-less
  identity) — and exercises both closed domain boundaries at once.
- **Overhead declared without a cell is rejected.** The constant only has
  a law to move inside the ROUNDUP cell arithmetic (the dispatch's
  `tfc_pkt_size = c + overhead` inside S2's ROUNDUP); an overhead on a
  cell-less topology would be a second, different consumption law, so
  the loader rejects the state citing the binding rather than inventing
  semantics.

## Honest limits of this slice (what it does NOT show)

- The overhead is destination-buffer accounting only: it spends credit,
  never wire bytes (registered assumption A-TFCP-OVH-BUFFER). Header
  serialization on the wire belongs to the analytical family's declared
  packetization/FLIT exclusion; O-CONSERVATION is unchanged by
  construction.
- Per-direction asymmetry of cell/overhead on a bidirectional PDC pair
  (UEC11-FC-R12) is not modeled — one data direction per neighbor pair,
  one constant; R12 stays unsupported. R10's configurability obligation
  stays unsupported (values in, obligation out).
- Fluid steady-window reading only (integer packet-floor effects of a
  partially-filled window are packet-granular dynamics, a declared
  exclusion); no credit-request/grant dynamics, no retransmission
  exemption (FC-R06), no shared-CCC pooling (FC-R16), no CBFC hop
  credits, no RCCC multi-source scheduling — all still declared
  unsupported in the backend's CAPABILITIES.
- The numbers are free-parameter arithmetic, not measurements; the
  overhead and cell values move them by design (attack surface, not
  hidden constants).
