#!/usr/bin/env python3
"""cross_fabric_matrix.py — the cross-fabric comparison matrix generator.

Builds ``docs/atlas/cross-fabric-matrix.md`` deterministically from the
content-addressed sweep and envelope artifacts of the cross-fabric family:

- sweeps: the committed cross-design grid (UEC free stand-ins vs the
  UnifiedBus-paper rack crossbar at 64 ranks) and its payload-grid
  extension (the same configs on the 10-size ladder the shared payload
  registry permits);
- envelopes: the UEC-TFC-window vs UB-flat-ring boundary family — the
  window axis at two payload corners and two rank corners, plus the
  shared-bandwidth and shared-hop-latency readings of the same
  saturation boundary.

Every comparable cell is DERIVED from its artifacts (no hand-typed
verdicts): verdicts come from the exact evaluation tables, boundaries,
and regions the orchestrator emits, and every cell cites the artifact id
it was derived from. Cells the platform cannot honestly fill carry an
explicit ``NOT COMPARABLE`` (mechanism absent or license-blocked) or
``NOT SAMPLED`` (comparable in principle, no artifact yet) verdict with
the reason — honest empties are part of the matrix.

Evidence level E0 only: every value behind a cell is the output of a
closed-form analytical identity under declared free parameters. The
matrix ranks MODEL IDENTITIES, never hardware, and no claim label may be
upgraded from this page.

Usage:

    .venv/bin/python tools/cross_fabric_matrix.py            # write the doc
    .venv/bin/python tools/cross_fabric_matrix.py --check    # verify the
        committed doc regenerates byte-identically (exit 1 on drift)

Determinism: same policy as the orchestrator (exact Fractions, canonical
order, no wall-clock). The rendered markdown depends only on the
committed manifests and the code version.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from essun.orchestrator.envelopes import run_envelope  # noqa: E402
from essun.orchestrator.sweeps import run_sweep  # noqa: E402

DOC_PATH = REPO / "docs" / "atlas" / "cross-fabric-matrix.md"

SWEEP_MANIFESTS = {
    "cross_design": REPO / "experiments" / "sweeps" / "cross_design_uec_vs_ub_paper_l0_v1.yaml",
    "payload_grid": REPO / "experiments" / "sweeps" / "cross_fabric_payload_grid_v1.yaml",
}
ENVELOPE_MANIFESTS = {
    # window axis (A-TFC-W) at three operating points
    "w_1mib_1024r": REPO / "experiments" / "envelopes" / "uec_vs_ub_window_boundary_v1.yaml",
    "w_1mib_256r": REPO / "experiments" / "envelopes" / "uec_vs_ub_window_boundary_tp256_v1.yaml",
    "w_16mib_1024r": REPO / "experiments" / "envelopes" / "uec_vs_ub_window_boundary_payload16m_v1.yaml",
    # shared-parameter readings of the same saturation boundary
    "bw_axis": REPO / "experiments" / "envelopes" / "uec_vs_ub_window_bw_boundary_v1.yaml",
    "lat_axis": REPO / "experiments" / "envelopes" / "uec_vs_ub_window_lat_boundary_v1.yaml",
}
WINDOW_AXIS_KEYS = ("w_1mib_1024r", "w_1mib_256r", "w_16mib_1024r")

UEC_CROSSBAR_TOPO = "crossbar64_uec_free_params.yaml"
UB_CROSSBAR_TOPO = "crossbar64_ub_rack_free_params.yaml"

# Pair selectors (resolved per artifact: the mid-freedom envelope names its
# UnifiedBus stand-in `ub_flat_ring_mid`, the pod-scale ones
# `ub_flat_ring_pod`, so cells key on the ROLE, never on a literal name).
PAIR_FLAGSHIP = "flagship"      # windowed UEC ring vs the UB flat ring
PAIR_ABLATION = "ablation"      # windowed UEC ring vs unwindowed UEC ring
PAIR_ANCHOR = "anchor"          # unwindowed UEC ring vs the UB flat ring


def _resolve_pair(table: dict, selector: str) -> tuple[str, str]:
    models = sorted({row["model"] for row in table["evaluations"]})
    tfc = "uec_tfc_ring"
    free = "uec_ring_free"
    others = [m for m in models if m not in (tfc, free)]
    if len(models) != 3 or len(others) != 1:
        raise AssertionError(f"unexpected model set {models} in envelope artifact")
    if selector == PAIR_FLAGSHIP:
        return tfc, others[0]
    if selector == PAIR_ABLATION:
        return tfc, free
    if selector == PAIR_ANCHOR:
        return free, others[0]
    raise AssertionError(f"unknown pair selector {selector!r}")

NOT_COMPARABLE_WINDOW = (
    "NOT COMPARABLE — the window axis does not exist for this pair: both "
    "comparators are unwindowed (the public UnifiedBus sources are silent "
    "on any flow-control mechanism, UBP-F04; the UEC crossbar stand-in "
    "declares no TFC binding at L0), so there is no window term to rank"
)
NOT_SAMPLED_SHARED_AXIS = (
    "NOT SAMPLED — the axis is shared and comparable in principle (both "
    "identities consume the same bind), but no envelope sweeps it for this "
    "pair; the two identities are the same function of the shared "
    "parameters, so the tie is an arithmetic identity, sampled only at the "
    "payload grid's fixed operating point"
)


@dataclass
class Ref:
    """One artifact citation: id plus kind (sweep or envelope)."""

    artifact_id: str
    kind: str


@dataclass
class Cell:
    """One matrix cell: derived verdict or an explicit honest empty."""

    verdict: str
    refs: list[Ref] = field(default_factory=list)
    winner: str | None = None
    flip: str | None = None
    detail_lines: list[str] = field(default_factory=list)

    @property
    def comparable(self) -> bool:
        return bool(self.refs)


# --- helpers -------------------------------------------------------------------


def _short(artifact_id: str) -> str:
    return artifact_id[:8] + "…" + artifact_id[-6:]


def _fmt_fraction(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else str(value)


def _sweep_rows_by_topo(table: dict, topo_suffix: str) -> dict[int, dict]:
    return {
        row["payload_bytes"]: row
        for row in table["configs"]
        if row["topology"]["path"].endswith(topo_suffix)
    }


def _pair_evals(table: dict, selector: str) -> list[dict]:
    """Per grid point: axis value, both models' exact values, exact sign."""
    pair = _resolve_pair(table, selector)
    axis_id = table["freedom_axes"][0]["assumption_id"]
    by_point: dict[str, dict[str, str]] = {}
    for row in table["evaluations"]:
        key = "-".join(f"{aid}={v}" for aid, v in row["axis_values_exact"])
        by_point.setdefault(key, {})[row["model"]] = row["o_cct_ns_mean_exact"]
    out = []
    for key, models in by_point.items():
        a, b = models[pair[0]], models[pair[1]]
        diff = Fraction(a) - Fraction(b)
        out.append(
            {
                "point": key,
                "axis": axis_id,
                "a": a,
                "b": b,
                "diff": diff,
                "sign": 1 if diff > 0 else (-1 if diff < 0 else 0),
            }
        )
    return out


def _pair_boundaries(table: dict, selector: str) -> list[dict]:
    pair = _resolve_pair(table, selector)
    return [b for b in table["boundaries"] if tuple(b["pair"]) == pair]


def _pair_regions(table: dict, selector: str) -> list[dict]:
    pair = _resolve_pair(table, selector)
    return [r for r in table["regions"] if tuple(r["pair"]) == pair]


def _envelope_op_point(table: dict) -> str:
    return "ranks {}, payload {} B".format(
        table["workload"]["tp_size"],
        table["workload"]["payload_bytes_at_operating_point"],
    )


# --- cell builders (verdicts derived from artifacts, never typed) ---------------


def _cell_crossbar_payload_grid(sweeps: dict) -> Cell:
    """Row 1, identity-matched crossbar pair: the delta-zero result."""
    grid = sweeps["payload_grid"]["table"]
    design = sweeps["cross_design"]["table"]
    uec = _sweep_rows_by_topo(grid, UEC_CROSSBAR_TOPO)
    ub = _sweep_rows_by_topo(grid, UB_CROSSBAR_TOPO)
    for size in sorted(uec):
        if Fraction(uec[size]["o_cct"]["completion_time_ns_mean_exact"]) != Fraction(
            ub[size]["o_cct"]["completion_time_ns_mean_exact"]
        ):
            raise AssertionError(
                f"identity-matched crossbar rows differ at payload {size}; "
                "the delta-zero anchor is broken"
            )
    design_uec = _sweep_rows_by_topo(design, UEC_CROSSBAR_TOPO)
    design_ub = _sweep_rows_by_topo(design, UB_CROSSBAR_TOPO)
    for size in sorted(design_uec):
        if Fraction(design_uec[size]["o_cct"]["completion_time_ns_mean_exact"]) != Fraction(
            design_ub[size]["o_cct"]["completion_time_ns_mean_exact"]
        ):
            raise AssertionError("cross-design delta-zero anchor is broken")
    return Cell(
        verdict=(
            f"TIE (exact) at all {len(uec)} payload-grid sizes and both "
            "committed cross-design sizes (delta exactly 0 everywhere)"
        ),
        refs=[
            Ref(sweeps["payload_grid"]["sweep_id"], "sweep"),
            Ref(sweeps["cross_design"]["sweep_id"], "sweep"),
        ],
        winner="neither (delta exactly 0 by construction)",
        flip=(
            "no flip exists: the two rows are the same identity under the "
            "one shared B/L record (A-XDUO-BW / A-XDUO-LAT), so every "
            "payload size ties; the UB side's only anchored difference "
            "(rack scale 64, UBP-P17) is matched by the UEC stand-in's "
            "chosen scale"
        ),
        detail_lines=[
            "Payload grid (bytes): "
            + ", ".join(str(s) for s in sorted(uec))
            + "; per-rank wire ledger and completion time identical at "
            "every size (see the sweep tables' delta columns, all exactly 0)."
        ],
    )


def _cell_window_payload_row(envelopes: dict, selector: str) -> Cell:
    """Row 1, window pairs: payload sampled at corners by the W-axis family."""
    arts = [envelopes[k] for k in WINDOW_AXIS_KEYS]
    op_points = []
    payloads = set()
    for art in arts:
        table = art["table"]
        payloads.add(table["workload"]["payload_bytes_at_operating_point"])
        evals = _pair_evals(table, selector)
        if any(entry["sign"] < 0 for entry in evals):
            raise AssertionError("windowed side ranked strictly better somewhere")
        boundaries = _pair_boundaries(table, selector)
        op_points.append(
            {
                "op": _envelope_op_point(table),
                "worse": sum(1 for e in evals if e["sign"] > 0),
                "tie": sum(1 for e in evals if e["sign"] == 0),
                "worst": _fmt_fraction(max(e["diff"] for e in evals)),
                "boundary": boundaries[0]["boundary_exact"],
            }
        )
    if len({p["boundary"] for p in op_points}) != 1:
        raise AssertionError("boundary moved with payload or rank count")
    boundary = op_points[0]["boundary"]
    return Cell(
        verdict=(
            f"unwindowed side wins or ties at every sampled point ({len(arts)} "
            f"artifacts: {len(payloads)} payload corners x 2 rank corners); "
            f"the exact boundary {boundary} does not move with payload or "
            "rank count"
        ),
        refs=[Ref(art["envelope_id"], "envelope") for art in arts],
        winner="unwindowed side, strictly, at every window below the boundary; TIE at and above",
        flip=(
            "flip condition independent of payload and rank count: tie iff "
            "W >= B*(L+L_cr) (the threshold carries no M and no r term); the "
            "below-boundary penalty scales with the per-rank traffic "
            "T = 2*(r-1)/r * M"
        ),
        detail_lines=[
            "Per operating point (strictly-worse / tie window points, worst "
            "penalty ns, exact boundary): "
            + "; ".join(
                f"{p['op']}: {p['worse']} / {p['tie']}, {p['worst']} ns, "
                f"{p['boundary']}"
                for p in op_points
            )
            + "."
        ],
    )


def _cell_window_axis(envelopes: dict, selector: str, keys: tuple[str, ...]) -> Cell:
    """Window-pair ranking cells on one swept axis: sign counts, verified
    exact boundaries, and regions derived from the artifacts."""
    arts = [envelopes[k] for k in keys]
    boundaries = []
    sign_counts = {"worse": 0, "tie": 0, "better": 0}
    for art in arts:
        table = art["table"]
        for boundary in _pair_boundaries(table, selector):
            if not boundary["boundary_verified"]:
                raise AssertionError(
                    f"unverified boundary in {art['envelope_id']}; the matrix "
                    "only reports verified exact boundaries"
                )
            boundaries.append((table, boundary, art["envelope_id"]))
        for entry in _pair_evals(table, selector):
            if entry["sign"] == 1:
                sign_counts["worse"] += 1
            elif entry["sign"] == 0:
                sign_counts["tie"] += 1
            else:
                sign_counts["better"] += 1
    if sign_counts["better"] != 0:
        raise AssertionError(
            "windowed comparator ranked strictly better somewhere; the "
            "saturation-boundary structure is violated"
        )
    distinct = sorted({b["boundary_exact"] for _, b, _ in boundaries})
    if len(distinct) != 1:
        raise AssertionError(f"boundary values disagree across artifacts: {distinct}")
    boundary_value = distinct[0]
    axis_name = boundaries[0][1]["axis"]
    region_lines = []
    for table, boundary, artifact_id in boundaries:
        for region in _pair_regions(table, selector):
            region_lines.append(
                f"{_envelope_op_point(table)}, axis {region['axis']}: "
                f"{region['sign_reading']} on [{region['from_exact']}, "
                f"{region['to_exact']}] (artifact {artifact_id})"
            )
    # Direction (which side of the boundary each region lies on) is DERIVED
    # from the region endpoints, never assumed: the windowed side's
    # strictly-worse region sits below the boundary on the window axis and
    # above it on the bandwidth and latency axes.
    worse_spans: list[tuple[Fraction, Fraction]] = []
    tie_spans: list[tuple[Fraction, Fraction]] = []
    for table, boundary, _ in boundaries:
        for region in _pair_regions(table, selector):
            span = (Fraction(region["from_exact"]), Fraction(region["to_exact"]))
            if region["sign_reading"] == "comparator_a_ranks_worse":
                worse_spans.append(span)
            elif region["sign_reading"] == "exact_tie":
                tie_spans.append(span)
            else:
                raise AssertionError(
                    "windowed comparator ranks strictly better somewhere; "
                    "the saturation-boundary structure is violated"
                )
    if not worse_spans or not tie_spans:
        raise AssertionError("expected both a strictly-worse and a tie region")
    worse_side = "below" if worse_spans[0][0] < Fraction(boundary_value) else "above"
    tie_side = "above" if tie_spans[0][1] > Fraction(boundary_value) else "below"
    return Cell(
        verdict=(
            f"exact TIE on [{tie_spans[0][0]}, {tie_spans[0][1]}] (at and "
            f"{tie_side} the boundary {boundary_value} on {axis_name}); "
            f"windowed side strictly worse on [{worse_spans[0][0]}, "
            f"{worse_spans[0][1]}] (at and {worse_side} it; never better at "
            f"any sampled point: {sign_counts['worse']} strictly-worse / "
            f"{sign_counts['tie']} tie grid points across this cell's "
            "artifacts)"
        ),
        refs=[Ref(art["envelope_id"], "envelope") for art in arts],
        winner=(
            f"unwindowed side on [{worse_spans[0][0]}, {worse_spans[0][1]}]; "
            f"neither on the tie region [{tie_spans[0][0]}, {tie_spans[0][1]}]"
        ),
        flip=(
            f"exact boundary {boundary_value} on {axis_name}, secant-resolved "
            "and verified by re-execution in every artifact of this cell; "
            "closed form: the windowed identity ties iff the granted window "
            "covers the bandwidth-delay product W >= B*(L+L_cr) — the same "
            "boundary W* = B*(L+L_cr) read in whichever variable the "
            "artifact sweeps (W itself, B at fixed W, or L at fixed W)"
        ),
        detail_lines=[
            "Verified exact boundaries (bracket, method, artifact): "
            + "; ".join(
                f"{_envelope_op_point(table)}: {b['boundary_exact']} on "
                f"bracket {b['bracket_exact']} ({b['boundary_method']}, "
                f"{artifact_id})"
                for table, b, artifact_id in boundaries
            )
            + ".",
            "Ranking regions (grid evidence, exact endpoints): "
            + "; ".join(region_lines)
            + ".",
        ],
    )


def _cell_conservation(sweeps: dict, envelopes: dict, col: str) -> Cell:
    if col == "crossbar_pair":
        for name in ("payload_grid", "cross_design"):
            table = sweeps[name]["table"]
            for row in table["configs"]:
                if row["o_conservation"]["violations"] != 0:
                    raise AssertionError("conservation violation in a sweep row")
        grid = sweeps["payload_grid"]["table"]
        uec = _sweep_rows_by_topo(grid, UEC_CROSSBAR_TOPO)
        ub = _sweep_rows_by_topo(grid, UB_CROSSBAR_TOPO)
        for size in sorted(uec):
            if uec[size]["per_rank_wire_bytes_exact"] != ub[size]["per_rank_wire_bytes_exact"]:
                raise AssertionError("wire ledgers differ between flavors")
        return Cell(
            verdict=(
                "TIE (exact): identical per-rank wire ledger "
                "2*(r-1)/r * M at every payload, 0 conservation violations "
                "in every row"
            ),
            refs=[
                Ref(sweeps["payload_grid"]["sweep_id"], "sweep"),
                Ref(sweeps["cross_design"]["sweep_id"], "sweep"),
            ],
            winner="neither; the flavor labels move no bytes",
            flip=(
                "no flip can exist: both identities emit the same wire "
                "traffic per rank; the sweep runner checks the ledger per "
                "row and the backends self-check it structurally"
            ),
        )
    # Window pairs: every envelope evaluation executes the backend's
    # structural conservation self-check (an AssertionError on violation),
    # and the identity keeps wire traffic unchanged by construction.
    return Cell(
        verdict=(
            "TIE (exact): the window gates rate, never bytes — per-rank wire "
            "traffic is the same identity on both sides of every pair"
        ),
        refs=[
            Ref(envelopes[key]["envelope_id"], "envelope")
            for key in ENVELOPE_MANIFESTS
        ],
        winner="neither",
        flip=(
            "no flip can exist at L0: the admission law (and its cell and "
            "overhead constants) spend credit without moving modeled bytes; "
            "every envelope evaluation re-runs the backend's structural "
            "conservation self-check"
        ),
    )


def _not_comparable(reason: str) -> Cell:
    return Cell(verdict=reason)


# --- matrix assembly -------------------------------------------------------------


def build_matrix(results_root: Path | None = None) -> tuple[dict, str]:
    sweeps = {}
    for name, path in SWEEP_MANIFESTS.items():
        sweeps[name] = run_sweep(path, results_root=results_root)
    envelopes = {}
    for name, path in ENVELOPE_MANIFESTS.items():
        envelopes[name] = run_envelope(path, results_root=results_root)

    columns = [
        {
            "id": "uec_window_vs_ub_flat",
            "name": "UEC TFC window vs UnifiedBus-paper flat",
            "description": (
                "the two-profile pair: the UEC profile's flagship executed "
                "semantic (TFC admission law UEC11-FC-R02) on the free ring "
                "stand-in vs the UnifiedBus paper profile's ring stand-in "
                "with no window (public-source silence, UBP-F04)"
            ),
        },
        {
            "id": "uec_window_on_vs_off",
            "name": "UEC window-on vs window-off (mechanism ablation)",
            "description": (
                "the same-profile control: the windowed ring vs the "
                "identical unwindowed ring, isolating the admission-law term"
            ),
        },
        {
            "id": "uec_vs_ub_crossbar",
            "name": "UEC crossbar stand-in vs UB-paper rack crossbar",
            "description": (
                "the identity-matched unwindowed pair at the UB-anchored rack "
                "scale 64 (UBP-P17): the delta-zero fairness anchor"
            ),
        },
    ]
    rows = [
        {
            "id": "occt_payload_grid",
            "name": "O-CCT — large-message completion across the payload grid",
            "cells": {
                "uec_window_vs_ub_flat": _cell_window_payload_row(
                    envelopes, PAIR_FLAGSHIP
                ),
                "uec_window_on_vs_off": _cell_window_payload_row(
                    envelopes, PAIR_ABLATION
                ),
                "uec_vs_ub_crossbar": _cell_crossbar_payload_grid(sweeps),
            },
        },
        {
            "id": "occt_window_boundary",
            "name": "O-CCT — saturation boundary on the window axis (A-TFC-W)",
            "cells": {
                "uec_window_vs_ub_flat": _cell_window_axis(
                    envelopes, PAIR_FLAGSHIP, WINDOW_AXIS_KEYS
                ),
                "uec_window_on_vs_off": _cell_window_axis(
                    envelopes, PAIR_ABLATION, WINDOW_AXIS_KEYS
                ),
                "uec_vs_ub_crossbar": _not_comparable(NOT_COMPARABLE_WINDOW),
            },
        },
        {
            "id": "occt_bw_axis",
            "name": "O-CCT — ranking under swept shared bandwidth (A-XDUO-BW)",
            "cells": {
                "uec_window_vs_ub_flat": _cell_window_axis(
                    envelopes, PAIR_FLAGSHIP, ("bw_axis",)
                ),
                "uec_window_on_vs_off": _cell_window_axis(
                    envelopes, PAIR_ABLATION, ("bw_axis",)
                ),
                "uec_vs_ub_crossbar": _not_comparable(NOT_SAMPLED_SHARED_AXIS),
            },
        },
        {
            "id": "occt_lat_axis",
            "name": "O-CCT — ranking under swept shared hop latency (A-XDUO-LAT)",
            "cells": {
                "uec_window_vs_ub_flat": _cell_window_axis(
                    envelopes, PAIR_FLAGSHIP, ("lat_axis",)
                ),
                "uec_window_on_vs_off": _cell_window_axis(
                    envelopes, PAIR_ABLATION, ("lat_axis",)
                ),
                "uec_vs_ub_crossbar": _not_comparable(NOT_SAMPLED_SHARED_AXIS),
            },
        },
        {
            "id": "oconservation",
            "name": "O-CONSERVATION — wire-byte ledger",
            "cells": {
                "uec_window_vs_ub_flat": _cell_conservation(
                    sweeps, envelopes, "window_pair"
                ),
                "uec_window_on_vs_off": _cell_conservation(
                    sweeps, envelopes, "window_pair"
                ),
                "uec_vs_ub_crossbar": _cell_conservation(
                    sweeps, envelopes, "crossbar_pair"
                ),
            },
        },
    ]
    matrix = {"columns": columns, "rows": rows, "sweeps": sweeps, "envelopes": envelopes}
    return matrix, render_markdown(matrix)


# --- markdown rendering (deterministic, a pure function of the matrix) ------------


def render_markdown(matrix: dict) -> str:
    lines: list[str] = []
    lines.append(
        "# Cross-fabric comparison matrix — which profile outperforms which, "
        "under stated assumptions"
    )
    lines.append("")
    lines.append(
        "Status **PROPOSED**, evidence level **E0 only**. Every comparable "
        "cell below is derived programmatically from content-addressed "
        "artifacts by `tools/cross_fabric_matrix.py` (verdicts, boundaries, "
        "and regions come from the orchestrator's own output, never from "
        "hand-typed conclusions; the tool's `--check` mode refuses a drift "
        "against this committed copy). Every value behind a cell is the "
        "output of a closed-form analytical identity under declared free "
        "parameters; the matrix ranks MODEL IDENTITIES, not hardware, and "
        "nothing here was measured on any system. No claim label upgrades "
        "from this page."
    )
    lines.append("")
    lines.append("## What a fair comparison requires (the fairness bar)")
    lines.append("")
    lines.append(
        "- **Identical open choices.** Both profiles consume the ONE shared "
        "free-parameter record "
        "(`experiments/unifiedbus/assumptions_uec_vs_ub_l0.yaml`): B = 64 "
        "bytes/ns and L = 200 ns are one record's values fed unchanged to "
        "every flavor file. No public source on either side anchors a "
        "per-lane rate or per-hop latency usable at L0 (UBP-F01/UBP-F02 "
        "mark the UnifiedBus silence; UEC 1.1 fixes neither), so any ranking "
        "that differed through B or L would be an artifact of unequal inputs."
    )
    lines.append(
        "- **Pinned sources.** The UEC side runs the public-read UEC 1.1 "
        "semantic profile (license-cleared ingestion, 80 anchors); the "
        "UnifiedBus side is a PAPER-DERIVED design profile from five public "
        "papers (53 anchors) — not a normative standard profile (the "
        "specification track stays license-gated). UALink and CXL have no "
        "profile at all (license-blocked, never ingested)."
    )
    lines.append(
        "- **Mechanisms stated, not smuggled.** The one executed mechanism "
        "asymmetry is the UEC TFC credit window (admission law "
        "UEC11-FC-R02; the exact 256-byte credit unit is the family's only "
        "standard-derived constant). The UnifiedBus side carries no window "
        "because its public sources are silent on flow control (UBP-F04) — "
        "declared silence, not a modeling shortcut."
    )
    lines.append(
        "- **Same workload, one operating point per artifact.** The "
        "platform's same-workload gate pins one W1 Dense TP Decode shape "
        "(2 layers x 3 steps = 6 AllReduce ops) and one tp_size per "
        "artifact, so every delta compares the same work."
    )
    lines.append("")
    lines.append("## The pairs (columns)")
    lines.append("")
    for column in matrix["columns"]:
        lines.append(f"- **{column['name']}** — {column['description']}.")
    lines.append("")
    lines.append("## The matrix")
    lines.append("")
    header = ["observable / axis"] + [c["name"] for c in matrix["columns"]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for row in matrix["rows"]:
        cells = []
        for column in matrix["columns"]:
            cell = row["cells"][column["id"]]
            refs = ", ".join(_short(r.artifact_id) for r in cell.refs) or "—"
            cells.append(f"{cell.verdict} [{refs}]")
        lines.append("| **" + row["name"] + "** | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Artifact ids (full, content-addressed)")
    lines.append("")
    lines.append("| short ref | artifact id | kind |")
    lines.append("|---|---|---|")
    seen: list[Ref] = []
    for row in matrix["rows"]:
        for column in matrix["columns"]:
            for ref in row["cells"][column["id"]].refs:
                if ref not in seen:
                    seen.append(ref)
    for ref in seen:
        lines.append(f"| `{_short(ref.artifact_id)}` | `{ref.artifact_id}` | {ref.kind} |")
    lines.append("")
    lines.append("## Per-row evidence")
    lines.append("")
    for row in matrix["rows"]:
        lines.append(f"### {row['name']}")
        lines.append("")
        for column in matrix["columns"]:
            cell = row["cells"][column["id"]]
            lines.append(f"**{column['name']}.**")
            lines.append("")
            lines.append(f"- Verdict: {cell.verdict}.")
            if cell.winner:
                lines.append(f"- Winner: {cell.winner}.")
            if cell.flip:
                lines.append(f"- Flip condition: {cell.flip}.")
            if cell.refs:
                lines.append(
                    "- Artifacts: "
                    + ", ".join(f"`{r.artifact_id}`" for r in cell.refs)
                    + "."
                )
            for line in cell.detail_lines:
                lines.append(f"- {line}")
            lines.append("")
    lines.append("## Scope: what this matrix does NOT compare (and why)")
    lines.append("")
    lines.append(
        "- **UALink and CXL: no column.** Their specification documents are "
        "license-restricted and were never ingested (license review "
        "precedes ingestion); there is no profile, so no pair and no cell "
        "exists. Any UALink or CXL comparison number from this platform "
        "would be fabricated."
    )
    lines.append(
        "- **UnifiedBus normative semantics: license-blocked.** The "
        "UnifiedBus column is a paper-derived design profile; cells name it "
        "as such everywhere."
    )
    lines.append(
        "- **Hierarchy and multi-level fabrics: NOT COMPARABLE (fidelity).** "
        "The UnifiedBus paper's hierarchical full-mesh with asymmetric "
        "per-level widths, memory semantics, APR routing, and the "
        "pod-of-racks hierarchy need L1 fidelity, which no landed backend "
        "executes; the envelope same-workload gate also pins one tp_size "
        "per artifact."
    )
    lines.append(
        "- **Credit-cell and packet-overhead laws (UEC11-FC-R08/R09): NOT "
        "COMPARABLE cross-profile.** These UEC-side refinements of the "
        "credit-consumption law have no UnifiedBus counterpart (UBP-F04 "
        "silence); they refine the windowed side only and appear in no "
        "cross cell."
    )
    lines.append(
        "- **Congestion, packetization, collective overlap: out of scope at "
        "L0** (declared unsupported by every backend involved)."
    )
    lines.append(
        "- **Shared-axis cells for the identity-matched crossbar pair are "
        "NOT SAMPLED** (see matrix): the tie is an arithmetic identity "
        "there, and the payload grid samples it at ten payloads; sweeping B "
        "or L for that pair would add no information the identity does not "
        "already fix."
    )
    lines.append("")
    lines.append("## How to reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append(
        "# every artifact the matrix cites (deterministic; byte-identical on replay)"
    )
    lines.append(".venv/bin/python -m essun.orchestrator.sweeps \\")
    lines.append("  experiments/sweeps/cross_design_uec_vs_ub_paper_l0_v1.yaml")
    lines.append(".venv/bin/python -m essun.orchestrator.sweeps \\")
    lines.append("  experiments/sweeps/cross_fabric_payload_grid_v1.yaml")
    lines.append(".venv/bin/python -m essun.orchestrator.envelopes \\")
    lines.append("  experiments/envelopes/uec_vs_ub_window_boundary_v1.yaml")
    lines.append(".venv/bin/python -m essun.orchestrator.envelopes \\")
    lines.append("  experiments/envelopes/uec_vs_ub_window_boundary_tp256_v1.yaml")
    lines.append(".venv/bin/python -m essun.orchestrator.envelopes \\")
    lines.append("  experiments/envelopes/uec_vs_ub_window_boundary_payload16m_v1.yaml")
    lines.append(".venv/bin/python -m essun.orchestrator.envelopes \\")
    lines.append("  experiments/envelopes/uec_vs_ub_window_bw_boundary_v1.yaml")
    lines.append(".venv/bin/python -m essun.orchestrator.envelopes \\")
    lines.append("  experiments/envelopes/uec_vs_ub_window_lat_boundary_v1.yaml")
    lines.append("# regenerate this page and refuse a drift against the committed copy")
    lines.append(".venv/bin/python tools/cross_fabric_matrix.py --check")
    lines.append("```")
    lines.append("")
    lines.append(
        "Generated deterministically from the committed manifests (exact "
        "Fractions, canonical order, no wall-clock); byte-identical on "
        "replay."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed doc regenerates byte-identically (exit 1 on drift)",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=None,
        help="results root for artifact generation (default: <repo>/results)",
    )
    args = parser.parse_args(argv)

    _, markdown = build_matrix(args.results_root)

    if args.check:
        committed = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.is_file() else None
        if committed == markdown + "\n":
            print(
                "cross-fabric-matrix: PASS — committed doc regenerates byte-identically"
            )
            return 0
        print(
            "cross-fabric-matrix: FAIL — committed doc differs from the "
            "regenerated matrix; rerun tools/cross_fabric_matrix.py and commit"
        )
        return 1

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(markdown + "\n", encoding="utf-8")
    print(f"cross-fabric-matrix: wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
