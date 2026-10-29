# Calibration adjudication record — E1 candidates

Date: 2026-10-29.

## Ruling

All **26 PROPOSED calibration records** (results
under `results/calibration/`) are **APPROVED as E1
calibration candidates**. No public claim, evidence label, README status,
or shipped parameter value changes as a result. The candidates inform a
future parameter-range-narrowing proposal, which will be its own
adjudication.

## Standing items

- **GF-06**: remains a documented gap (26/27). Manual extraction of
  the anchor numbers (~15 min) is the preferred closure; until then no
  record exists and none is paraphrased. Blocked material preserved at
  `experiments/calibration/gf06/` (untracked).
- **Headline read (30–45 min)** still owed on the five headline
  findings (torus twist-blindness falsifier; ±7.02% minimax misfit;
  three-fabric derating brackets 0.712/0.80/0.93; B=100 UEC sim endpoint;
  13.79% gain cap) — the read that later converts candidates into narrowed
  ranges.
- **Ghost-run caveat**: run `144228d0` pins an assumptions version that
  existed only in a working tree and was never committed; the four GLOB
  records citing it carry a non-authoritative-input caveat. Byte-replay
  of those four requires a reconstructed input and is deliberately NOT
  attempted.
