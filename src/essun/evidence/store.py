"""Content-addressed, append-only evidence store over ``results/``.

Implements the ``EvidenceStore`` contract (IMPLEMENTATION_GUIDE §5: run
records and evidence links are append-only): ``put_run`` /
``link_run_to_claim`` / ``list_runs``, plus the counterexample, figure,
and reproduction-bundle operations — ``put_counterexample``,
``register_figure``, ``export_reproduction_bundle``.

Layout (identical to the run-record format the run path already
wrote, so existing artifacts remain valid store content):

    results/
      claims_index.jsonl              # append-only claim links, one per line
      counterexamples.jsonl           # append-only counterexample records
      figures_index.jsonl             # append-only figure provenance entries
      <run_id>/run.json               # run payload + run_id, canonical JSON
      <run_id>/observations.json      # observations, canonical JSON

``run_id`` is the SHA-256 of the canonical-JSON run payload — the store is
content-addressed, and ``put_run`` never overwrites: an existing run_id
with different bytes is an error; with identical bytes the put is
idempotent (no rewrite, no error). ``counterexample_id`` is likewise the
SHA-256 of the canonical-JSON counterexample record, and ``figure_id`` is
the SHA-256 of the canonical-JSON binding of the sorted source-run set to
the SHA-256 of every artifact byte in those run dirs: identical referenced
content re-registers idempotently, different content is a different id (a
new figure, appended, never a conflict), and re-registering the same
content with different ``claim_ids`` is an append-only violation.
Every index or run reference (claim links, counterexample run_ids, figure
source runs, bundle exports) may only name runs already in the store. No
wall-clock or host metadata is ever written, so identical manifest +
inputs + code version reproduce byte-identical artifacts
(tests/determinism) — including reproduction bundles, which are pure
functions of the stored bytes.

D3 orthogonal evidence dimensions (2026-10-29, run-record schema version
1 -> 2, :mod:`essun.evidence.dimensions`): a run payload MAY carry the
five structured fields ``verification`` / ``calibration_target`` /
``held_out`` / ``independent_reproduction`` / ``known_omissions``; a
payload carrying any of them MUST stamp ``evidence_schema_version: 2``.
``put_run`` validates the fields and the version stamp at the door and
rejects malformed ones (an ``EvidenceError`` naming the dimension).
Backfill-safe: version-1 records — every record stored before D3, with
none of these keys — load unchanged, and their absent dimensions read as
UNKNOWN, never as a silently defaulted ``False``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .dimensions import RUN_RECORD_SCHEMA_VERSION as RUN_RECORD_SCHEMA_VERSION
from .dimensions import run_record_problems

CLAIMS_INDEX = "claims_index.jsonl"
COUNTEREXAMPLES_INDEX = "counterexamples.jsonl"
FIGURES_INDEX = "figures_index.jsonl"
RUN_RECORD = "run.json"
OBSERVATIONS = "observations.json"
BUNDLE_MANIFEST = "manifest.json"

# Typed, minimal counterexample record schema (IMPLEMENTATION_GUIDE §5 /
# VALIDATION_AND_CGFR: a counterexample names the runs that disagreed, the
# observable that differed, a free-text description, its classified cause,
# and where the minimized case lives once minimization has run —
# ``None`` until then).
COUNTEREXAMPLE_FIELDS = (
    "run_ids",
    "observable",
    "description",
    "cause_class",
    "minimized_case_ref",
)


class EvidenceError(Exception):
    """Raised when an append-only or provenance invariant of the store is violated."""


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)


def _index_line(entry: dict) -> str:
    """One-line canonical JSON for the JSONL indexes (indent would
    split records across lines)."""
    return json.dumps(entry, sort_keys=True, ensure_ascii=False)


def _read_index(path: Path) -> list[dict]:
    """All entries of a JSONL index, in append order (missing file → empty)."""
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _append_index(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_index_line(entry) + "\n")


def _require_str(value: Any, where: str, allow_none: bool = False) -> None:
    if allow_none and value is None:
        return
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"{where} must be a non-empty string")


def _require_str_list(value: Any, where: str, allow_empty: bool = False) -> None:
    if not isinstance(value, list):
        raise EvidenceError(f"{where} must be a list of strings")
    if not value and not allow_empty:
        raise EvidenceError(f"{where} must not be empty")
    for item in value:
        _require_str(item, f"each entry of {where}")


class EvidenceStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    # ------------------------------------------------------------------
    # runs
    # ------------------------------------------------------------------

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def compute_run_id(self, run_payload: dict) -> str:
        return hashlib.sha256(canonical_json(run_payload).encode("utf-8")).hexdigest()

    def put_run(self, run_payload: dict, observations: dict) -> str:
        """Persist a run record; returns the content-addressed run_id.

        The record format is exactly the pre-existing one: ``run.json`` is
        the payload extended with ``run_id``; both files end with a single
        newline. Overwrites are forbidden — a repeated run_id must carry
        byte-identical artifacts or the store rejects it.

        D3 dimensions gate (schema version 2): any of the five evidence
        dimension fields present in the payload must be structurally
        valid and the payload must stamp ``evidence_schema_version: 2``
        (see :mod:`essun.evidence.dimensions`). Payloads without the
        fields — every pre-D3 record — pass through untouched.
        """
        problems = run_record_problems(run_payload)
        if problems:
            raise EvidenceError("; ".join(problems))
        run_id = self.compute_run_id(run_payload)
        record = {**run_payload, "run_id": run_id}
        observations_bytes = (canonical_json(observations) + "\n").encode("utf-8")
        record_bytes = (canonical_json(record) + "\n").encode("utf-8")

        directory = self.run_dir(run_id)
        expected = {
            OBSERVATIONS: observations_bytes,
            RUN_RECORD: record_bytes,
        }
        if directory.exists():
            for name, payload in expected.items():
                path = directory / name
                if not path.is_file():
                    raise EvidenceError(
                        f"append-only violation: run {run_id} exists but "
                        f"{name} is missing; the store never repairs records"
                    )
                if path.read_bytes() != payload:
                    raise EvidenceError(
                        f"append-only violation: run {run_id} already exists "
                        f"with different {name} bytes"
                    )
            return run_id  # idempotent: identical content, no rewrite

        directory.mkdir(parents=True, exist_ok=True)
        (directory / OBSERVATIONS).write_bytes(observations_bytes)
        (directory / RUN_RECORD).write_bytes(record_bytes)
        return run_id

    def get_run(self, run_id: str) -> dict:
        path = self.run_dir(run_id) / RUN_RECORD
        if not path.is_file():
            raise EvidenceError(f"no run record for run_id {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[str]:
        """All run_ids present under the store root, sorted."""
        if not self.root.is_dir():
            return []
        return sorted(
            entry.name
            for entry in self.root.iterdir()
            if entry.is_dir() and (entry / RUN_RECORD).is_file()
        )

    # ------------------------------------------------------------------
    # claim links (append-only index)
    # ------------------------------------------------------------------

    def link_run_to_claim(self, run_id: str, claim_id: str, relation: str = "supports") -> None:
        """Append a run→claim link to ``results/claims_index.jsonl``.

        Append-only and idempotent per exact (run_id, claim_id, relation)
        triple: replaying the same link writes nothing; a different claim
        or relation for the same run appends a new line. Links may only
        reference runs already in the store.
        """
        if not (self.run_dir(run_id) / RUN_RECORD).is_file():
            raise EvidenceError(
                f"cannot link claim {claim_id}: run {run_id} is not in the store"
            )
        entry = {
            "run_id": run_id,
            "claim_id": claim_id,
            "relation": relation,
        }
        index_path = self.root / CLAIMS_INDEX
        if any(stored == entry for stored in _read_index(index_path)):
            return  # idempotent append: the identical link is already recorded
        _append_index(index_path, entry)

    def claim_links(self) -> list[dict]:
        """All recorded run→claim links, in append order."""
        return _read_index(self.root / CLAIMS_INDEX)

    # ------------------------------------------------------------------
    # counterexamples (append-only index)
    # ------------------------------------------------------------------

    def put_counterexample(self, record: dict) -> str:
        """Append a counterexample record; returns its content hash id.

        The record schema is minimal but typed — exactly the keys
        ``run_ids`` (non-empty list of run_ids in this store),
        ``observable``, ``description``, ``cause_class`` (non-empty
        strings) and ``minimized_case_ref`` (non-empty string or ``None``
        until minimization has run). ``counterexample_id`` is the SHA-256
        of the canonical-JSON record, so recording the identical record
        again is idempotent; a different record is a new append, never an
        overwrite.
        """
        if not isinstance(record, dict):
            raise EvidenceError("counterexample record must be a dict")
        missing = [field for field in COUNTEREXAMPLE_FIELDS if field not in record]
        if missing:
            raise EvidenceError(
                f"counterexample record is missing field(s): {', '.join(missing)}"
            )
        unknown = [key for key in record if key not in COUNTEREXAMPLE_FIELDS]
        if unknown:
            raise EvidenceError(
                f"counterexample record has unknown field(s): {', '.join(sorted(unknown))}"
            )
        _require_str_list(record["run_ids"], "counterexample record field 'run_ids'")
        for field in ("observable", "description", "cause_class"):
            _require_str(record[field], f"counterexample record field {field!r}")
        _require_str(
            record["minimized_case_ref"],
            "counterexample record field 'minimized_case_ref'",
            allow_none=True,
        )
        for run_id in record["run_ids"]:
            if not (self.run_dir(run_id) / RUN_RECORD).is_file():
                raise EvidenceError(
                    f"cannot record counterexample: run {run_id} is not in the store"
                )

        counterexample_id = hashlib.sha256(
            canonical_json(record).encode("utf-8")
        ).hexdigest()
        entry = {**record, "counterexample_id": counterexample_id}
        index_path = self.root / COUNTEREXAMPLES_INDEX
        for stored in _read_index(index_path):
            if stored.get("counterexample_id") == counterexample_id:
                if stored == entry:
                    return counterexample_id  # idempotent: identical record
                raise EvidenceError(
                    f"append-only violation: counterexample {counterexample_id} "
                    f"is already recorded with different bytes"
                )
        _append_index(index_path, entry)
        return counterexample_id

    def counterexamples(self) -> list[dict]:
        """All recorded counterexample entries, in append order."""
        return _read_index(self.root / COUNTEREXAMPLES_INDEX)

    # ------------------------------------------------------------------
    # figure provenance (append-only index; consumed by the figure gate)
    # ------------------------------------------------------------------

    def register_figure(
        self, source_run_ids: list[str], claim_ids: list[str]
    ) -> str:
        """Register a figure's provenance; returns the content-addressed
        ``figure_id``.

        The id is not caller-chosen: it is the SHA-256 of the
        canonical-JSON binding of the sorted source-run set to the SHA-256
        of every artifact byte in those run dirs — a figure's identity is
        exactly the content it references. Identical content therefore
        re-registers idempotently (same figure_id, no second entry,
        independent of argument order); different source runs — or
        different bytes under them — produce a different figure_id, i.e. a
        new figure appended, never a conflict. ``claim_ids`` are recorded
        provenance but do not enter the id: re-registering the same
        content with different claims would rewrite the stored entry's
        history and is an append-only violation. Every ``source_run_ids``
        entry must already exist in the store — the figure-provenance gate
        The figure gate: a figure may only be built from immutable runs.
        """
        _require_str_list(source_run_ids, "source_run_ids")
        _require_str_list(claim_ids, "claim_ids", allow_empty=True)
        runs = sorted(set(source_run_ids))
        artifact_hashes: dict[str, dict[str, str]] = {}
        for run_id in runs:
            run_dir = self.run_dir(run_id)
            if not (run_dir / RUN_RECORD).is_file():
                raise EvidenceError(
                    f"cannot register figure: run {run_id} is not in the store"
                )
            artifact_hashes[run_id] = {
                source.relative_to(self.root).as_posix(): hashlib.sha256(
                    source.read_bytes()
                ).hexdigest()
                for source in sorted(run_dir.rglob("*"))
                if source.is_file()
            }

        binding = {
            "artifact_sha256": artifact_hashes,
            "source_run_ids": runs,
        }
        figure_id = hashlib.sha256(canonical_json(binding).encode("utf-8")).hexdigest()
        entry = {
            "figure_id": figure_id,
            "source_run_ids": runs,
            "claim_ids": sorted(set(claim_ids)),
        }
        index_path = self.root / FIGURES_INDEX
        for stored in _read_index(index_path):
            if stored.get("figure_id") == figure_id:
                if stored == entry:
                    return figure_id  # idempotent: identical registration
                raise EvidenceError(
                    f"append-only violation: figure {figure_id} is already "
                    f"registered with different claims"
                )
        _append_index(index_path, entry)
        return figure_id

    def figures(self) -> list[dict]:
        """All registered figure entries, in append order."""
        return _read_index(self.root / FIGURES_INDEX)

    # ------------------------------------------------------------------
    # reproduction bundles (deterministic export)
    # ------------------------------------------------------------------

    def export_reproduction_bundle(self, run_ids: list[str], out_dir: Path | str) -> Path:
        """Copy the named run dirs plus a hash manifest into ``out_dir``.

        The bundle is self-contained and deterministic: ``out_dir`` holds
        one directory per run (byte-identical copies of every file in the
        store's run dir) and a ``manifest.json`` listing the bundled
        run_ids and the SHA-256 of every bundled file, keyed by the
        run-relative path. Nothing time- or host-dependent is written, so
        two exports of the same run set — in any order, at any time —
        produce byte-identical bundles.
        """
        _require_str_list(run_ids, "run_ids")
        bundled = sorted(set(run_ids))
        hashes: dict[str, str] = {}
        out = Path(out_dir)
        for run_id in bundled:
            run_dir = self.run_dir(run_id)
            if not (run_dir / RUN_RECORD).is_file():
                raise EvidenceError(
                    f"cannot export reproduction bundle: run {run_id} is not in the store"
                )
            for source in sorted(run_dir.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(self.root).as_posix()
                destination = out / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()

        manifest = {"run_ids": bundled, "hashes": hashes}
        out.mkdir(parents=True, exist_ok=True)
        (out / BUNDLE_MANIFEST).write_bytes((canonical_json(manifest) + "\n").encode("utf-8"))
        return out
