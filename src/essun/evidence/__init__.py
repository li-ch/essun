"""Append-only evidence layer.

Public surface: :class:`essun.evidence.store.EvidenceStore`, plus the D3
orthogonal evidence dimensions (:mod:`essun.evidence.dimensions`) — the
five structured run-record fields, their UNKNOWN-not-false reader, and
the run-record schema version this code writes.
"""

from __future__ import annotations

from .dimensions import (
    EVIDENCE_DIMENSIONS,
    INDEPENDENT_REPRODUCTION_NONE_YET,
    MANIFEST_KEY,
    RUN_RECORD_SCHEMA_VERSION,
    SCHEMA_VERSION_KEY,
    UNKNOWN,
    dimensions_from_manifest,
    read_dimensions,
)
from .store import EvidenceError, EvidenceStore, canonical_json

__all__ = [
    "EVIDENCE_DIMENSIONS",
    "EvidenceError",
    "EvidenceStore",
    "INDEPENDENT_REPRODUCTION_NONE_YET",
    "MANIFEST_KEY",
    "RUN_RECORD_SCHEMA_VERSION",
    "SCHEMA_VERSION_KEY",
    "UNKNOWN",
    "canonical_json",
    "dimensions_from_manifest",
    "read_dimensions",
]
