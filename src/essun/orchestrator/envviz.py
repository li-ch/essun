"""Envelope visualization DATA for the atlas pages (G4, 2026-10-30).

An envelope artifact (``orchestrator/envelopes.py`` → ``boundary.json``)
already carries every evaluation as exact strings, but it is a RUN RECORD:
provenance-first, one row per (operating point, model), not shaped for a
page or a plot. This module derives, deterministically and EXACTLY, the
visualization form of the same envelope:

- per comparator model, one SERIES per freedom axis slice — the exact grid
  coordinates and the exact O-CCT values, each with a float MIRROR for
  plotting (the mirror is display-only; comparisons, boundaries, and
  regions live entirely in the exact strings, the boundary-detector
  policy);
- per declared boundary pair, the exact DIFFERENCE SERIES ``d = a - b``
  with its three-way sign table, the verified exact boundaries, and the
  constant-sign regions — the numbers a boundary chart would shade.

Everything is :class:`fractions.Fraction` under the hood: the data file
carries exact ``"p/q"`` strings (parsed back for every sort and every
difference), and floats appear only as derived mirrors
(``float(Fraction(str))`` — one correctly-rounded conversion, never a
comparison input). Generation is a pure function of the envelope table:
canonical JSON (sort_keys), no wall-clock, no iteration-order dependence
(series are ordered by axis coordinate, models in manifest order), so the
same manifest + code produce byte-identical data forever — the emitted
``envelope-data.json`` is CONTENT-ADDRESSED like the artifact
(``envelope-data.json.sha256`` records the SHA-256 of its exact bytes) and
links itself to its source artifact via the artifact's own content hash.

Evidence level E0 ONLY, status PROPOSED: the data visualizes the ranking
of ANALYTICAL MODEL IDENTITIES under declared freedom — no hardware
claims, no measurement, no standard-derived value enters through this
path (the one standard-derived constant anywhere in the family, the UEC
256-byte credit unit, lives in its backend and reaches the data only as
emitted identity output).
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Iterable

from essun.evidence.store import canonical_json

DATA_FILENAME = "envelope-data.json"
DATA_SHA_FILENAME = "envelope-data.json.sha256"

FRAMING = [
    "E0 evidence only: every value in this data file is the exact output "
    "of a closed-form analytical identity executed by its landed backend "
    "under explicit free parameters at exact operating points.",
    "The *_exact fields are exact fraction strings and are the ONLY "
    "comparison inputs; the *_float fields are display mirrors derived "
    "from them and never feed a boundary, region, or sign.",
    "A boundary stated here is a fact about the RANKING RELATION OF MODEL "
    "IDENTITIES under declared freedom — not about any measured system; "
    "nothing here was run on or says anything about hardware.",
]


def _exact(value_text: str, context: str) -> Fraction:
    """Parse an exact string back to a Fraction (defensive: the artifact
    strings were serialized from Fractions, so this cannot fail — but a
    corrupted field must be an error, never a silent float fallback)."""
    try:
        return Fraction(value_text)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{context}: {value_text!r} is not an exact fraction") from exc


def _slice_key(axis_values: list[list[str]], skip: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (aid, value) for aid, value in axis_values if aid != skip
    )


def build_envelope_data(table: dict) -> dict:
    """Derive the visualization data dict from one envelope table.

    Pure function of ``table`` (the run record emitted by
    ``orchestrator/envelopes.py``): same table in, same dict out — no
    clock, no environment, no dict-iteration dependence in the output
    order (series walk models in manifest order, points in axis order).
    """

    evaluations_by_model_point: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}
    for row in table["evaluations"]:
        key = (row["model"], tuple((aid, value) for aid, value in row["axis_values_exact"]))
        evaluations_by_model_point[key] = row["o_cct_ns_mean_exact"]

    axes_out = []
    for axis in table["freedom_axes"]:
        points = [_exact(p, f"axis {axis['assumption_id']} point") for p in axis["points_exact"]]
        axes_out.append(
            {
                "assumption_id": axis["assumption_id"],
                "parameter": axis["parameter"],
                "unit": axis["unit"],
                "range_exact": list(axis["range_exact"]),
                "points_exact": [str(p) for p in points],
                "points_float": [float(p) for p in points],
            }
        )

    fixed_out = []
    for item in table["operating_point_fixed"]:
        value = _exact(item["value_exact"], f"fixed {item['assumption_id']}")
        fixed_out.append(
            {
                "assumption_id": item["assumption_id"],
                "parameter": item["parameter"],
                "unit": item["unit"],
                "value_exact": str(value),
                "value_float": float(value),
                "range_exact": list(item["range_exact"]),
            }
        )

    models_out = [
        {
            "model": model["model"],
            "algorithm_id": model["algorithm_id"],
            "backend_id": model["backend_id"],
        }
        for model in table["models"]
    ]

    # --- per-model series: one per (model, axis, slice-of-other-axes)
    series: list[dict] = []
    for model in models_out:
        for axis in table["freedom_axes"]:
            slices: dict[tuple[tuple[str, str], ...], list[tuple[str, str]]] = {}
            for row in table["evaluations"]:
                if row["model"] != model["model"]:
                    continue
                slices.setdefault(
                    _slice_key(row["axis_values_exact"], axis["assumption_id"]), []
                ).append(
                    (
                        dict(row["axis_values_exact"])[axis["assumption_id"]],
                        row["o_cct_ns_mean_exact"],
                    )
                )
            for slice_key in sorted(slices, key=lambda k: sorted(k)):
                ordered = sorted(
                    slices[slice_key],
                    key=lambda pair: _exact(pair[0], "series coordinate"),
                )
                values = [
                    _exact(v, f"series value ({model['model']})") for _, v in ordered
                ]
                series.append(
                    {
                        "model": model["model"],
                        "axis": axis["assumption_id"],
                        "slice_values_exact": [[aid, value] for aid, value in slice_key],
                        "points_exact": [p for p, _ in ordered],
                        "points_float": [
                            float(_exact(p, "series coordinate")) for p, _ in ordered
                        ],
                        "values_exact": [str(v) for v in values],
                        "values_float": [float(v) for v in values],
                    }
                )

    # --- per-pair difference series with sign table, boundaries, regions
    pairs_out: list[dict] = []
    for pair_spec in table["boundary_pairs"]:
        for axis in table["freedom_axes"]:
            pair_slices: dict[
                tuple[tuple[str, str], ...], list[tuple[str, str, str]]
            ] = {}
            for row in table["evaluations"]:
                if row["model"] not in pair_spec:
                    continue
                pair_slices.setdefault(
                    _slice_key(row["axis_values_exact"], axis["assumption_id"]), []
                ).append(
                    (
                        row["model"],
                        dict(row["axis_values_exact"])[axis["assumption_id"]],
                        row["o_cct_ns_mean_exact"],
                    )
                )
            for slice_key in sorted(pair_slices, key=lambda k: sorted(k)):
                rows = pair_slices[slice_key]
                by_model_point = {(model, point): value for model, point, value in rows}
                points = sorted(
                    {point for _, point, _ in rows},
                    key=lambda p: _exact(p, "pair coordinate"),
                )
                if len(by_model_point) != 2 * len(points):
                    # Cannot happen: the runner evaluates every model at
                    # every operating point; kept as a fence, not a guess.
                    raise ValueError(
                        f"pair {pair_spec}: incomplete evaluations on axis "
                        f"{axis['assumption_id']} slice {slice_key}"
                    )
                differences = [
                    _exact(by_model_point[(pair_spec[0], p)], "pair value a")
                    - _exact(by_model_point[(pair_spec[1], p)], "pair value b")
                    for p in points
                ]
                boundaries = [
                    {
                        "bracket_exact": list(flip["bracket_exact"]),
                        "difference_at_bracket_exact": list(flip["difference_exact"]),
                        "sign_lo": flip["sign_lo"],
                        "sign_hi": flip["sign_hi"],
                        "boundary_exact": flip["boundary_exact"],
                        "boundary_float": (
                            None
                            if flip["boundary_exact"] is None
                            else float(_exact(flip["boundary_exact"], "boundary"))
                        ),
                        "boundary_verified": flip["boundary_verified"],
                        "boundary_method": flip["boundary_method"],
                    }
                    for flip in table["boundaries"]
                    if flip["pair"] == list(pair_spec)
                    and flip["axis"] == axis["assumption_id"]
                    and tuple((aid, value) for aid, value in flip["slice_values_exact"])
                    == slice_key
                ]
                regions = [
                    {
                        "sign": region["sign"],
                        "sign_reading": region["sign_reading"],
                        "from_exact": region["from_exact"],
                        "to_exact": region["to_exact"],
                    }
                    for region in table["regions"]
                    if region["pair"] == list(pair_spec)
                    and region["axis"] == axis["assumption_id"]
                    and tuple((aid, value) for aid, value in region["slice_values_exact"])
                    == slice_key
                ]
                pairs_out.append(
                    {
                        "pair": list(pair_spec),
                        "axis": axis["assumption_id"],
                        "slice_values_exact": [[aid, value] for aid, value in slice_key],
                        "points_exact": points,
                        "differences_exact": [str(d) for d in differences],
                        "differences_float": [float(d) for d in differences],
                        "signs": [1 if d > 0 else (-1 if d < 0 else 0) for d in differences],
                        "boundaries": boundaries,
                        "regions": regions,
                    }
                )

    return {
        "envelope": table["envelope"],
        "envelope_id": table["envelope_id"],
        "code_version": table["code_version"],
        "evidence_level": table["evidence_level"],
        "status": table["status"],
        "observable": table["observable"],
        "artifact_boundary_json_sha256": hashlib.sha256(
            (canonical_json(table) + "\n").encode("utf-8")
        ).hexdigest(),
        "manifest": {"path": table["manifest_path"], "sha256": table["manifest_sha256"]},
        "fixed": fixed_out,
        "axes": axes_out,
        "models": models_out,
        "series": series,
        "pairs": pairs_out,
        "framing": list(FRAMING),
    }


def envelope_data_bytes(data: dict) -> bytes:
    """Deterministic serialization: canonical JSON + trailing newline."""
    return (canonical_json(data) + "\n").encode("utf-8")


def data_payloads(table: dict) -> dict[str, bytes]:
    """The envelope's data-file bytes: the data JSON and its sha256 sidecar."""
    data_bytes = envelope_data_bytes(build_envelope_data(table))
    return {
        DATA_FILENAME: data_bytes,
        DATA_SHA_FILENAME: (hashlib.sha256(data_bytes).hexdigest() + "\n").encode("utf-8"),
    }


def write_payloads_idempotent(payloads: dict[str, bytes], out_dir: Path, what: str) -> None:
    """Write files byte-check-first: an existing file with different bytes is
    a determinism bug, never a silent rewrite (the runner's own policy); a
    missing file is simply written, so a rerun completes partial state
    instead of failing on it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = out_dir / name
        if path.is_file() and path.read_bytes() != payload:
            raise ValueError(
                f"{what}: {path} already exists with different bytes; "
                "envelope outputs are deterministic — a byte drift is a bug"
            )
    for name, payload in payloads.items():
        (out_dir / name).write_bytes(payload)


def write_envelope_data(table: dict, artifact_dir: Path) -> Path:
    """Emit the data files next to the boundary artifact; returns the dir."""
    artifact_dir = Path(artifact_dir)
    write_payloads_idempotent(
        data_payloads(table), artifact_dir, f"envelope {table['envelope']}"
    )
    return artifact_dir


def write_committed_data(table: dict, data_dir: Path) -> Path:
    """Emit the committed copy for the atlas pages: one file per envelope
    NAME (the page-level key), byte-identical to the artifact copy."""
    data_dir = Path(data_dir)
    payloads = data_payloads(table)
    committed = {
        f"{table['envelope']}.{name}": payload for name, payload in payloads.items()
    }
    write_payloads_idempotent(committed, data_dir, f"envelope {table['envelope']}")
    return data_dir


# ---------------------------------------------------------------------------
# Atlas page rendering (deterministic: derived only from the table dicts)
# ---------------------------------------------------------------------------


def _sign_word(sign_value: int, model_a: str, model_b: str) -> str:
    return {
        1: f"`{model_a}` ranks strictly worse than `{model_b}`",
        0: f"`{model_a}` and `{model_b}` tie exactly",
        -1: f"`{model_a}` ranks strictly better than `{model_b}`",
    }[sign_value]


def render_envelope_section_md(table: dict) -> str:
    """One atlas-page section per envelope: operating point, series table,
    and the mechanically generated boundary statements."""
    lines: list[str] = []
    lines.append(f"## Envelope `{table['envelope']}`")
    lines.append("")
    lines.append(
        f"Envelope id `{table['envelope_id']}` — status {table['status']} at "
        f"evidence level {table['evidence_level']}. Manifest "
        f"`{table['manifest_path']}` (sha256 `{table['manifest_sha256']}`). "
        "Every value below is a closed-form analytical identity executed by "
        "its landed backend under declared free parameters; nothing here is "
        "measured or says anything about hardware."
    )
    lines.append("")
    lines.append("Fixed operating point (exact, range-validated):")
    lines.append("")
    for item in table["operating_point_fixed"]:
        lines.append(
            f"- {item['assumption_id']} = {item['value_exact']} "
            f"(range [{item['range_exact'][0]}, {item['range_exact'][1]}])"
        )
    for axis in table["freedom_axes"]:
        lines.append(
            f"- axis {axis['assumption_id']}: grid {', '.join(axis['points_exact'])} "
            f"inside [{axis['range_exact'][0]}, {axis['range_exact'][1]}]"
        )
    lines.append("")

    for axis in table["freedom_axes"]:
        slice_keys: list[tuple[tuple[str, str], ...]] = []
        coords_by_slice: dict[tuple[tuple[str, str], ...], list[str]] = {}
        for row in table["evaluations"]:
            slice_key = _slice_key(row["axis_values_exact"], axis["assumption_id"])
            if slice_key not in coords_by_slice:
                coords_by_slice[slice_key] = []
                slice_keys.append(slice_key)
            point = dict(row["axis_values_exact"])[axis["assumption_id"]]
            if point not in coords_by_slice[slice_key]:
                coords_by_slice[slice_key].append(point)
        for slice_key in slice_keys:
            coords = sorted(
                coords_by_slice[slice_key], key=lambda p: _exact(p, "table coord")
            )
            model_order = [m["model"] for m in table["models"]]
            if slice_key:
                lines.append(
                    "Slice "
                    + ", ".join(f"{aid} = {value}" for aid, value in slice_key)
                    + ":"
                )
                lines.append("")
            lines.append(f"| {axis['assumption_id']} | " + " | ".join(model_order) + " |")
            lines.append("|" + "---|" * (len(model_order) + 1))
            for point in coords:
                cells = []
                for model in model_order:
                    value_text = next(
                        r["o_cct_ns_mean_exact"] for r in table["evaluations"]
                        if r["model"] == model
                        and dict(r["axis_values_exact"])[axis["assumption_id"]] == point
                    )
                    cells.append(str(_exact(value_text, "table cell")))
                lines.append(f"| {point} | " + " | ".join(cells) + " |")
            lines.append("")

    for pair_spec in table["boundary_pairs"]:
        model_a, model_b = pair_spec
        flips = [f for f in table["boundaries"] if f["pair"] == list(pair_spec)]
        regions = [r for r in table["regions"] if r["pair"] == list(pair_spec)]
        lines.append(f"### Pair `{model_a}` vs `{model_b}`")
        lines.append("")
        if not flips:
            lines.append(
                f"No ranking boundary at any sampled point: "
                f"{_sign_word(regions[0]['sign'], model_a, model_b)} at every "
                "sampled operating point on the whole grid."
            )
        else:
            for flip in flips:
                boundary_text = (
                    f"exactly {flip['boundary_exact']} (verified, "
                    f"{flip['boundary_method']})"
                    if flip["boundary_verified"]
                    else f"unresolved inside the bracket {flip['bracket_exact']}"
                )
                lines.append(
                    f"- Axis {flip['axis']}"
                    + (
                        f", slice {flip['slice_values_exact']}"
                        if flip["slice_values_exact"]
                        else ""
                    )
                    + f": sign {flip['sign_lo']} -> {flip['sign_hi']} on bracket "
                    f"{flip['bracket_exact']}; boundary {boundary_text}."
                )
            for region in regions:
                lines.append(
                    f"- Region: {_sign_word(region['sign'], model_a, model_b)} on "
                    f"[{region['from_exact']}, {region['to_exact']}]."
                )
        lines.append("")
    return "\n".join(lines)


def render_envelopes_page_md(tables: Iterable[dict]) -> str:
    """The atlas envelopes page: E0 fence, then one section per envelope."""
    tables = list(tables)
    lines: list[str] = []
    lines.append("# Performance envelopes over declared free-parameter ranges")
    lines.append("")
    lines.append(
        "Evidence level **E0 only**: every table and boundary below "
        "compares closed-form analytical identities under explicit free "
        "parameters at exact operating points — arithmetic facts of the "
        "models, never measurements, never hardware claims, never "
        "standard-derived values (the one standard-derived constant in "
        "the family, the UEC 256-byte credit unit, lives in its backend "
        "and appears here only as emitted identity output). A boundary is "
        "a statement about the RANKING RELATION OF MODEL IDENTITIES: "
        "saturation boundaries tie at and above the threshold and rank "
        "strictly worse below it; a two-sided crossing changes sign "
        "through zero on both sides. No claim, label, or README status "
        "upgrades from this page."
    )
    lines.append("")
    lines.append(
        "Each section below is generated deterministically from its "
        "content-addressed envelope artifact (the committed record under "
        "`experiments/envelopes/` carries the artifact identity and "
        "reproduction commands; the visualization data series — exact "
        "fractions plus display-only float mirrors — live under "
        "`envelope-data/`)."
    )
    lines.append("")
    for table in tables:
        lines.append(render_envelope_section_md(table))
        lines.append("---")
        lines.append("")
    lines.append(
        "Generated deterministically from the envelope manifests (canonical "
        "JSON, exact Fractions, no wall-clock); byte-identical on replay."
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    from essun.contracts import REPO_ROOT
    from essun.orchestrator.envelopes import run_envelope

    parser = argparse.ArgumentParser(
        description=(
            "Run envelope manifests and emit the visualization data "
            "(and optionally the atlas envelopes page) deterministically"
        )
    )
    parser.add_argument("manifests", nargs="+", help="envelope manifest YAML paths")
    parser.add_argument(
        "--results-root",
        default=None,
        help="results root (default: <repo>/results); the artifact and its "
        "envelope-data.json land under envelopes/<envelope_id>/",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="also write the committed atlas copies "
        "<envelope>.envelope-data.json[.sha256] here "
        "(default: <repo>/docs/atlas/envelope-data)",
    )
    parser.add_argument(
        "--page",
        default=None,
        help="write the atlas envelopes page rendered from all given "
        "manifests (e.g. <repo>/docs/atlas/envelopes.md)",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir) if args.data_dir else REPO_ROOT / "docs/atlas/envelope-data"
    tables = []
    summary = []
    for manifest in args.manifests:
        result = run_envelope(manifest, results_root=args.results_root)
        table = result["table"]
        tables.append(table)
        write_envelope_data(table, result["artifact_dir"])
        write_committed_data(table, data_dir)
        data_sha = hashlib.sha256(
            envelope_data_bytes(build_envelope_data(table))
        ).hexdigest()
        summary.append(
            {
                "envelope": table["envelope"],
                "envelope_id": result["envelope_id"],
                "artifact_sha256": result["artifact_sha256"],
                "envelope_data_sha256": data_sha,
                "data_dir": str(data_dir),
            }
        )
    if args.page:
        page_path = Path(args.page)
        page_path.write_text(render_envelopes_page_md(tables) + "\n", encoding="utf-8")
        summary.append({"page": str(page_path)})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
