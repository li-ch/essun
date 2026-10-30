# Credit-family S2 evidence record — UEC11-FC-R08 as simulated_behavior

G2 credit-window family ladder (milestone v0.2.0 criterion 2) stage S2,
per the S1 plan in `experiments/uec/credit_family_inventory.md`. Date:
2026-10-30. Owner review: pending (the platform-side facts below are what
the owner reviews).

## Labels (read first)

- Platform status: **IMPLEMENTED_UNVERIFIED** (the chain executes and its
  golden tests pass; no external review yet).
- Evidence level: **E0** — identity and determinism only. No empirical
  claim is made.
- **`simulated_behavior` is a claim about the BINDING** (the requirement's
  ROUNDUP consumption law causally affects backend outputs through the
  declared, load-checked parameter `tfc_dest_cell_size`), **not a claim of
  physical validity**: nothing here is calibrated against UEC hardware.
  B, L, W, L_cr (flagship values, shared on purpose) and the cell itself
  are FREE parameters — the cell constrained only to the spec-cited
  domain. Spec-derived values in the chain: the 256-byte credit unit
  (UEC11-FC-R05) and the cell domain 256..9216 B in 256-B multiples
  (UEC11-FC-R07 — whose own obligation disposition stays `unsupported`;
  values in, obligation out, same pattern as R05's unit in the flagship).

## The chain

| Link | Artifact |
| --- | --- |
| Anchored requirement | **UEC11-FC-R08** (UEC 1.1 §3.6.15, TFC, DEFINITIONAL) — `credit_used = ROUNDUP(tfc_pkt_size ÷ tfc_dest_cell_size) × tfc_dest_cell_size`; anchor `UEC11-S3.6.15-TFC` (verified by the anchor registry's re-hash on every registry test) |
| Machine-readable binding | `BIND-UEC11-FC-R08-L0TFC` — `src/essun/specir/bindings.py` (registry-gated: requirement, anchors, backend capability/parameter, observables, R07-cited domain constants re-verified live; gate test `tests/specir/test_bindings.py`; binding-coverage property `tests/specir/test_binding_coverage.py`) |
| Backend capability / parameter effect | `analytical_l0_tfc` — `src/essun/backends/analytical/l0_tfc.py`, capability `tfc_credit_windowed_ring`; the OPT-IN parameter `tfc.dest_cell_size` executes the law as per-packet consumed credit `cq = ROUNDUP(c/cell) × cell` with the ring chunk `c = M/r` as `tfc_pkt_size`, and effective data rate `min(B, (c/cq) · W/(L+L_cr))` — quantization waste spends credit without moving bytes; `t = 2*(r-1)/r · M / min(B, (c/cq)·W/(L+L_cr)) + 2*(r-1)*L` |
| Executed golden test | `tests/golden/test_l0_tfc_cell_golden.py` — every expected value derived IN the test by exact `Fraction` arithmetic (waste regime 6832 ns at cell 9216, 3808 ns at cell 768; the R08 worked example's own ROUNDUP arithmetic 4352 B against 512-B cells ⇒ 4608 B; zero-waste convergence to the landed R02 identity exactly at `c ≡ 0 (mod cell)` for cells 256/512/1024/2048; out-of-domain cells rejected at load citing UEC11-FC-R07 with the closed boundaries 256 and 9216 accepted) |
| Observable change | **O-CCT**: 6832 ns mean (cell 9216, efficiency 2/9, rate 64/9 B/ns) vs 3696 ns for the identical B/L/W/L_cr on the flagship R02 run — a +3136 ns exact delta = `T·(1/Rd − 1/R02_rate)` — with **O-CONSERVATION unchanged** (a cell gates rate, never byte count) |
| Modeling choices (registered) | `experiments/vertical_slice/assumptions_tfc_cell.yaml` — A-TFCC-CELL (cell value, free in the R07-cited domain), A-TFCC-CHUNK-PKT (ring chunk = the TFC packet; overhead is S3's FC-R09, deliberately absent), A-TFCC-FLUID (fluid steady-window reading; integer packet-floor effects excluded as packet-granular), plus the shared B/L/W/L_cr/DIV entries |
| Evidence run | run_id `e74ecec28540dcd0eec79f4d8386695bd54c9570220a9c4ee7da0186f3c3315b` (content-addressed, `evidence_schema_version: 2`, `calibration_target: []`, `held_out: false` — E0 identity/determinism only; manifest `experiments/vertical_slice/w1_decode_tfc_cell.yaml`; observations carry provenance for BOTH bindings — R02's window block and R08's cell block); claim link `C-UEC-TFC-R08` in `results/claims_index.jsonl` |

Re-verify in one line each:

```bash
.venv/bin/python -m pytest -q tests/golden/test_l0_tfc_cell_golden.py tests/specir/test_bindings.py
.venv/bin/python -m essun.orchestrator.runs experiments/vertical_slice/w1_decode_tfc_cell.yaml
# -> run_id e74ecec28540dcd0eec79f4d8386695bd54c9570220a9c4ee7da0186f3c3315b (byte-identical)
```

## Design decisions specific to this slice

- **Opt-in parameter, flagship identity frozen.** `tfc.dest_cell_size` is
  declared in the topology (`experiments/topologies/ring8_tfc_cell_window_v1.yaml`),
  and a topology without it runs the flagship R02 identity with
  byte-identical observations: the flagship run `dc7d83b6…` still
  reproduces from its unchanged manifest (pinned by the backfill gate in
  `tests/evidence/test_dimensions.py`), because the cell rides the run
  identity through the infra-graph input hash — a cell never silently
  appears or vanishes.
- **Separate assumptions file.** `assumptions_tfc_cell.yaml` (not an
  append to `assumptions_tfc.yaml`): the assumptions file is a hashed
  manifest input, so appending there would have moved the flagship run's
  identity. Same house rule as the per-model files.
- **R07 cited, not executed.** The domain values 256..9216 B in 256-B
  multiples are carried as named constants citing UEC11-FC-R07 and
  enforced at load; R07's own disposition stays `unsupported`
  (implementation-support obligation — no admissible-config enforcement
  path exists). Same pattern as the 256-byte unit citing R05.
- **9216 B for the evidence run.** The per-packet-buffer-strategy cell the
  R08 statement itself names, and the domain's upper boundary — chosen to
  land the smoke chunk (2048 B) deep in the waste regime (efficiency 2/9)
  and exercise the boundary the loader must accept.

## Honest limits of this slice (what it does NOT show)

- The per-packet overhead constant is NOT modeled: at S2
  `tfc_pkt_size` = the ring chunk (A-TFCC-CHUNK-PKT); the
  `payload + overhead` composition is UEC11-FC-R09, stage S3.
- Fluid steady-window reading only: the identity grants fractional
  cells-in-window (here 12800/9216 = 25/18); integer packet-floor effects
  are packet-granular dynamics, a declared exclusion of the analytical
  family. No credit-request/grant dynamics, no retransmission exemption
  (FC-R06), no shared-CCC pooling (FC-R16), no CBFC hop credits, no RCCC
  multi-source scheduling — all still declared unsupported in the
  backend's CAPABILITIES.
- The numbers are free-parameter arithmetic, not measurements; the cell
  value moves them by design (attack surface, not a hidden constant).
