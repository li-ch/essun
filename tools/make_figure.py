#!/usr/bin/env python3
"""make_figure.py — provenance-linked figure from evidence-store run records.

Renders ``paper/figures/w1_smoke_occt_l0_vs_astra.svg`` — O-CCT bars for the
W1 smoke pair (analytical L0 golden run vs the pinned ASTRA-sim analytical
twin) — reading ONLY immutable run records under ``results/``:

* every plotted number is taken from ``<run_id>/observations.json`` (or, for
  the ASTRA per-op bar, derived by exact division of the recorded whole-chain
  wall time by the recorded op count — the chain is dependency-serialized, so
  the division is exact; a non-exact division aborts);
* the figure embeds its source run ids, code version(s), the evidence label
  ``IMPLEMENTED_UNVERIFIED``, and the manifests' validity domains;
* provenance is registered through the append-only evidence store
  (``EvidenceStore.register_figure``), which content-addresses the figure by
  the bytes of everything under the two run dirs; registration is idempotent;
* the companion README (``paper/figures/README.md``) carries every
  measurement inside ``[RESULT: ...]`` placeholders, so ``make paper-check``
  keeps passing.

Deterministic by construction: no wall-clock, host, or random input; the SVG
and README are pure functions of the run-record bytes, so replay from a cold
tree reproduces both byte-for-byte. Stdlib only.

Usage::

    .venv/bin/python tools/make_figure.py            # defaults: W1 smoke pair
    .venv/bin/python tools/make_figure.py --runs ID1 ID2 --out PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from essun.evidence.store import EvidenceStore  # noqa: E402

# The documented default pair (difference report
# results/difference_reports/w1_smoke_l0_vs_astra_sim_analytical.json): the
# L0 golden run and its pinned ASTRA-sim analytical twin.
DEFAULT_L0_RUN = "146ba565d2cac8e613435e548caba4f606e0abbb149beaf6404935d4f92199a1"
DEFAULT_ASTRA_RUN = "c6dc87eb58791438a4a9050238bc8347418228fb63e6df428fb27d3c0b35ab0c"

EVIDENCE_LABEL = "IMPLEMENTED_UNVERIFIED"

SANS = "font-family=\"Helvetica, Arial, sans-serif\""
MONO = "font-family=\"Menlo, Consolas, monospace\""


class FigureError(Exception):
    """Raised when the run records do not support an honest figure."""


def load_run(results_root: Path, run_id: str) -> dict:
    run_dir = results_root / run_id
    record_path = run_dir / "run.json"
    if not record_path.is_file():
        raise FigureError(f"run {run_id} is not in the store ({record_path} missing)")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    observations = json.loads((run_dir / "observations.json").read_text(encoding="utf-8"))
    manifest = record["manifest"]
    oct_obs = observations["observables"].get("O-CCT")
    if oct_obs is None:
        raise FigureError(f"run {run_id} records no O-CCT observable")
    return {
        "run_id": run_id,
        "backend_id": observations["backend_id"],
        "experiment_id": manifest["experiment_id"],
        "claim_id": manifest.get("claim_id"),
        "code_version": record["code_version"],
        "validity_domain": manifest["validity_domain"],
        "model": observations["model"],
        "oct": oct_obs,
        "per_op": observations.get("per_op"),
    }


def oct_ns_pair(run: dict) -> dict:
    """Per-op and whole-chain O-CCT in ns, integers, from the record only.

    L0-family records carry per-op exact values (mean = max; all ops
    identical) plus a per-op list; the chain total is their exact sum.
    The ASTRA record carries the whole-chain wall time only; the per-op
    equivalent is exact division by the recorded op count (dependency-
    serialized chain — a remainder would make the division dishonest, so
    it aborts).
    """
    oct_obs = run["oct"]
    ops = oct_obs["ops"]
    if run["per_op"]:
        per_op_values = [int(op["completion_time_ns_exact"]) for op in run["per_op"]]
        if len(per_op_values) != ops:
            raise FigureError(f"run {run['run_id']}: per_op length != ops")
        mean_exact = int(oct_obs["completion_time_ns_mean_exact"])
        if any(value != mean_exact for value in per_op_values):
            raise FigureError(
                f"run {run['run_id']}: per-op values are not identical; "
                "bar rendering from mean would misrepresent the record"
            )
        return {
            "per_op_ns": mean_exact,
            "chain_ns": sum(per_op_values),
            "per_op_derivation": "per-op closed-form identity (mean = max)",
        }
    chain = int(oct_obs["completion_time_ns"])
    if chain % ops:
        raise FigureError(
            f"run {run['run_id']}: chain {chain} ns does not divide exactly "
            f"by ops {ops}; per-op equivalent would not be exact"
        )
    return {
        "per_op_ns": chain // ops,
        "chain_ns": chain,
        "per_op_derivation": f"whole-chain wall / ops (exact division, {chain}/{ops})",
    }


def check_shared_configuration(l0: dict, astra: dict) -> None:
    """The bars are comparable only on identical declared free parameters."""
    for key in ("topology_id", "ranks", "hop_latency_ns_exact", "link_bytes_per_ns_exact"):
        if l0["model"].get(key) != astra["model"].get(key):
            raise FigureError(
                f"free parameter {key!r} differs between the runs "
                f"({l0['model'].get(key)!r} vs {astra['model'].get(key)!r}); "
                "bars would not be comparable"
            )
    if l0["oct"]["ops"] != astra["oct"]["ops"]:
        raise FigureError("op counts differ between the runs; bars would not be comparable")


def _nice_step(value: float) -> int:
    """Smallest 1/2/5 x 10^k integer >= value (tick step, plot headroom)."""
    import math

    if value <= 0:
        raise FigureError("tick step must be positive")
    exponent = math.floor(math.log10(value))
    for mult in (1, 2, 5):
        candidate = mult * 10**exponent
        if candidate >= value:
            return candidate
    return 10 ** (exponent + 1)


def render_svg(path: Path, l0: dict, astra: dict, values_l0: dict, values_astra: dict,
               figure_id: str) -> None:
    width, height = 980, 670
    panels = [
        {
            "title": "O-CCT per op (ns)",
            "x0": 90, "x1": 465,
            "bars": [
                ("analytical L0", values_l0["per_op_ns"], "#4869a8", False),
                ("ASTRA-sim analytical*", values_astra["per_op_ns"], "#c46f33", True),
            ],
        },
        {
            "title": f"O-CCT, {l0['oct']['ops']}-op chain (ns)",
            "x0": 565, "x1": 940,
            "bars": [
                ("analytical L0", values_l0["chain_ns"], "#4869a8", False),
                ("ASTRA-sim analytical", values_astra["chain_ns"], "#c46f33", False),
            ],
        },
    ]
    baseline, top = 386, 104
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]

    ratio = values_astra["per_op_ns"] / values_l0["per_op_ns"]
    parts.append(f'<text x="{width / 2}" y="32" text-anchor="middle" {SANS} '
                 f'font-size="17" font-weight="bold">W1 Dense TP Decode smoke: O-CCT, '
                 f'analytical L0 vs pinned ASTRA-sim analytical</text>')
    parts.append(f'<text x="{width / 2}" y="54" text-anchor="middle" {SANS} font-size="13" '
                 f'fill="#444444">same workload, topology and free parameters: '
                 f'ring8_free_v1, r = {l0["model"]["ranks"]}, '
                 f'B = {l0["model"]["link_bytes_per_ns_exact"]} B/ns, '
                 f'L = {l0["model"]["hop_latency_ns_exact"]} ns</text>')
    parts.append(f'<text x="{width / 2}" y="74" text-anchor="middle" {SANS} font-size="13" '
                 f'fill="#444444">ratio ASTRA/L0 = {ratio:.2f}x on both panels; the gap is '
                 f'classified as a modeling-assumption difference, not a defect '
                 f'(difference report DIFF-VS-W1-SMOKE-001)</text>')

    for panel in panels:
        x0, x1 = panel["x0"], panel["x1"]
        peak = max(value for _, value, _, _ in panel["bars"])
        step = _nice_step(peak / 4)
        top_tick = 4 * step
        scale = (baseline - top) / top_tick
        for index in range(5):  # gridlines + ticks at 0..4 steps
            value = step * index
            y = baseline - value * scale
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                         f'stroke="#dddddd" stroke-width="1"/>')
            parts.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" text-anchor="end" {SANS} '
                         f'font-size="11" fill="#666666">{value:,}</text>')
        parts.append(f'<line x1="{x0}" y1="{baseline}" x2="{x1}" y2="{baseline}" '
                     f'stroke="#333333" stroke-width="1.5"/>')
        parts.append(f'<text x="{(x0 + x1) / 2}" y="{baseline + 62}" text-anchor="middle" '
                     f'{SANS} font-size="14" font-weight="bold">{escape(panel["title"])}</text>')
        # bars: two per panel, evenly placed
        span = x1 - x0 - 60
        for index, (label, value, color, derived) in enumerate(panel["bars"]):
            bar_w = 96
            cx = x0 + 30 + span * index / 2 + (span / 2 - bar_w) / 2
            bar_h = value * scale
            parts.append(f'<rect x="{cx:.1f}" y="{baseline - bar_h:.1f}" width="{bar_w}" '
                         f'height="{bar_h:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{cx + bar_w / 2:.1f}" y="{baseline - bar_h - 8:.1f}" '
                         f'text-anchor="middle" {SANS} font-size="13" '
                         f'font-weight="bold">{value:,}</text>')
            parts.append(f'<text x="{cx + bar_w / 2:.1f}" y="{baseline + 22}" '
                         f'text-anchor="middle" {SANS} font-size="12.5" '
                         f'fill="#333333">{escape(label)}</text>')
            if derived:
                parts.append(f'<text x="{cx + bar_w / 2:.1f}" y="{baseline - bar_h - 26:.1f}" '
                             f'text-anchor="middle" {SANS} font-size="11" '
                             f'fill="#888888">derived</text>')

    # provenance footer: run ids, code version, evidence label, validity domain
    versions = sorted({l0["code_version"], astra["code_version"]})
    version_note = "code version " + " = ".join(versions) if len(versions) == 1 else \
        " / ".join(f"{run['backend_id']} {run['code_version']}" for run in (l0, astra))
    footer = [
        f"provenance — figure_id {figure_id} (results/figures_index.jsonl, append-only)",
        f"L0 run {l0['run_id']} ({l0['experiment_id']}, {l0['backend_id']})",
        f"ASTRA run {astra['run_id']} ({astra['experiment_id']}, {astra['backend_id']})",
        f"{version_note} | evidence label: {EVIDENCE_LABEL} | claims: "
        f"{', '.join(sorted({c for c in (l0['claim_id'], astra['claim_id']) if c}))}",
        f"validity domain - topology: {l0['validity_domain']['topology']}; "
        f"workload: {l0['validity_domain']['workload']}",
        f"implementation L0: {l0['validity_domain']['implementation']}",
        f"implementation ASTRA: {astra['validity_domain']['implementation']}",
        f"* ASTRA per-op bar = {values_astra['per_op_derivation']}; "
        f"L0 per-op bar = {values_l0['per_op_derivation']}",
        "numbers are read from the run records only; regenerate deterministically: "
        ".venv/bin/python tools/make_figure.py",
    ]
    for line_no, line in enumerate(footer):
        mono = line_no in (1, 2)  # run-id lines render in monospace
        style = MONO if mono else SANS
        size = 10 if mono else 11
        parts.append(f'<text x="24" y="{472 + 19 * line_no}" {style} '
                     f'font-size="{size}" fill="#333333">{escape(line)}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def render_readme(path: Path, l0: dict, astra: dict, values_l0: dict, values_astra: dict,
                  figure_id: str, svg_name: str) -> None:
    ratio = values_astra["per_op_ns"] / values_l0["per_op_ns"]
    l0_id, astra_id = l0["run_id"], astra["run_id"]
    text = f"""# paper/figures — generated from evidence-store run records only

Every figure here is rendered by `tools/make_figure.py` from immutable run
records under `results/` — source runs {l0_id} and {astra_id} — whose
ids, code versions, evidence label and validity domain are embedded in the
image. Its provenance is registered in the append-only index
`results/figures_index.jsonl` under figure_id `{figure_id}`.
Registration is idempotent, and the SVG and this README are pure
functions of the run-record bytes: replaying the script over identical
records reproduces both byte-for-byte (run records themselves are
reproduced by the documented manifest commands, not stored in git). All
measurements appear inside [RESULT: ...] placeholders; none is externally
reproduced yet.

## {svg_name} — O-CCT, analytical L0 vs pinned ASTRA-sim analytical (W1 smoke pair)

- figure_id `{figure_id}` — index line in `results/figures_index.jsonl` (source runs {l0_id}, {astra_id})
- claim links: both runs are linked to claim {l0['claim_id']} in `results/claims_index.jsonl` (run ids {l0_id}, {astra_id})
- source run L0: `{l0_id}` — {l0['experiment_id']} — record `results/{l0_id}/run.json` (code {l0['code_version']})
- source run ASTRA: `{astra_id}` — {astra['experiment_id']} — record `results/{astra_id}/run.json` (code {astra['code_version']})
- evidence label: {EVIDENCE_LABEL} (replay-pinned run records; not externally
  reproduced; no calibration)
- [RESULT: O-CCT per op, analytical L0 = {values_l0['per_op_ns']:,} ns, run {l0_id}, {l0['experiment_id']}, {EVIDENCE_LABEL}]
- [RESULT: O-CCT per op (chain/ops, exact division), ASTRA-sim analytical = {values_astra['per_op_ns']:,} ns, run {astra_id}, {astra['experiment_id']}, {EVIDENCE_LABEL}]
- [RESULT: O-CCT whole {l0['oct']['ops']}-op chain, L0 = {values_l0['chain_ns']:,} ns vs ASTRA-sim = {values_astra['chain_ns']:,} ns, runs {l0_id} + {astra_id}, {EVIDENCE_LABEL}]
- [RESULT: O-CCT ratio ASTRA/L0 = {ratio:.2f}x, runs {l0_id} + {astra_id}, classified as modeling-assumption difference (see results/difference_reports/w1_smoke_l0_vs_astra_sim_analytical.json)]
- validity domain: topology {l0['validity_domain']['topology']}; workload
  {l0['validity_domain']['workload']}; implementations — L0:
  {l0['validity_domain']['implementation']}; ASTRA:
  {astra['validity_domain']['implementation']}.
- regenerate: `.venv/bin/python tools/make_figure.py` (deterministic; no
  network, no wall-clock input).
"""
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--runs", nargs=2, metavar=("L0_RUN_ID", "ASTRA_RUN_ID"),
        default=[DEFAULT_L0_RUN, DEFAULT_ASTRA_RUN],
        help="the two source run ids (default: the W1 smoke L0 golden + ASTRA twin)",
    )
    parser.add_argument("--results-root", type=Path, default=REPO_ROOT / "results")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "paper" / "figures" / "w1_smoke_occt_l0_vs_astra.svg")
    parser.add_argument("--readme", type=Path, default=REPO_ROOT / "paper" / "figures" / "README.md")
    parser.add_argument("--no-register", action="store_true",
                        help="render only; skip the evidence-store registration")
    args = parser.parse_args(argv)

    l0 = load_run(args.results_root, args.runs[0])
    astra = load_run(args.results_root, args.runs[1])
    check_shared_configuration(l0, astra)
    values_l0 = oct_ns_pair(l0)
    values_astra = oct_ns_pair(astra)

    figure_id = None
    if not args.no_register:
        store = EvidenceStore(args.results_root)
        claim_ids = sorted({c for c in (l0["claim_id"], astra["claim_id"]) if c})
        figure_id = store.register_figure([l0["run_id"], astra["run_id"]], claim_ids)
    else:
        figure_id = "(not registered --no-register)"

    render_svg(args.out, l0, astra, values_l0, values_astra, figure_id)
    render_readme(args.readme, l0, astra, values_l0, values_astra, figure_id, args.out.name)
    print(json.dumps({
        "figure_id": figure_id,
        "svg": str(args.out.relative_to(REPO_ROOT)),
        "readme": str(args.readme.relative_to(REPO_ROOT)),
        "source_run_ids": [l0["run_id"], astra["run_id"]],
        "o_cct_ns": {
            "per_op": {"l0": values_l0["per_op_ns"], "astra": values_astra["per_op_ns"]},
            "chain": {"l0": values_l0["chain_ns"], "astra": values_astra["chain_ns"]},
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
