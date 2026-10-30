#!/usr/bin/env python3
"""Build ``experiments/uec/semantic_profile.yaml`` (ladder S4, 2026-10-29).

Migrate the UEC 1.1 semantic profile INTO the versioned D2 profile format
(``essun-profile`` v0.1: ``schemas/profile.schema.json`` + loader
:mod:`essun.specir.profile_format`, ladder S3).  The artifact is the
ten-element first-class profile of design doc D2: source identity/revision,
provenance and permissions, interpreted requirements WITH dispositions
(D1), declared implementation freedom, backend capability bindings,
executable checks, supported workloads/observables, calibration scope,
known omissions, versioning rules.

Division of content (the honesty contract of this migration):

- DERIVED, never hand-edited: ``requirements`` (all 445 objects of the
  five stage modules, with their S1 dispositions — the builder READS the
  dispositions from the live registry, it cannot assign or change them:
  this is a migration, not a re-adjudication), ``freedom`` (all 67 free
  parameters), ``bindings`` (the live
  :data:`essun.specir.bindings.BINDINGS` registry, currently
  BIND-UEC11-FC-R02-AUTOMATON, BIND-UEC11-FC-R08-L0TFC and
  BIND-UEC11-FC-R09-L0TFC), and the ``source``/``provenance`` identity
  fields, read from the repo license-gate source record
  ``experiments/uec/source_record.yaml`` (verbatim access class; the PDF
  sha256 travels with the record).  Anchor citations are copied
  UNCHANGED — the anchor registry (``experiments/uec/anchor_registry.yaml``)
  remains the only place anchors are defined.
- CURATED, reviewed editorial content: ``checks``, ``omissions``,
  ``versioning``, and the notes — stated in this script so every sentence
  in the artifact has a source under review.

The builder refuses to write an invalid artifact: it validates the built
document with the S3 loader, resolves every anchor citation against the
live anchor registry, and checks every binding against its declared
backend's CAPABILITIES before writing.  Conformance is then pinned by
``tests/specir/test_uec_semantic_profile.py``, which also re-runs this
builder and requires byte-identical output (no silent hand-edits).

Re-run after any change to the stage modules, the bindings registry, or
the source record::

    .venv/bin/python experiments/uec/build_semantic_profile.py

Usage::

    .venv/bin/python experiments/uec/build_semantic_profile.py [--output PATH]
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
from pathlib import Path

import yaml

from essun.specir.anchors import AnchorRegistry
from essun.specir.bindings import BINDINGS, UEC_REQUIREMENT_MODULES
from essun.specir.profile_format import (
    PROFILE_FORMAT_NAME,
    PROFILE_FORMAT_VERSION,
    check_anchor_refs,
    check_bindings_against,
    profile_from_dict,
    profile_problems,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_RECORD_PATH = REPO_ROOT / "experiments/uec/source_record.yaml"
PROFILE_PATH = REPO_ROOT / "experiments/uec/semantic_profile.yaml"

#: Stable identity of this profile artifact (named-profile comparisons, D4).
PROFILE_ID = "uec-1.1-semantic"

#: The artifact's own version.  Tracks the ARTIFACT, not the UEC source
#: revision (1.1 stays in source.revision); 0.1.0 is the first release of
#: the profile in the essun-profile format.  0.1.0 -> 0.2.0 at G2 stage S2
#: (2026-10-30): the disposition flip (UEC11-FC-R08) plus a new binding is
#: the bump rules' MAJOR class, which on the 0.x line bumps the MINOR
#: component (semver 0.x convention: 0.MINOR is the breaking axis).
#: 0.2.0 -> 0.3.0 at G8 (2026-10-30): the UEC11-FC-R02 binding was
#: RE-POINTED at the credit obligation automaton (its steady-state
#: abstraction declared as the analytical Eq. 3 backend) — again the
#: MAJOR "bindings" class (which backend executes which requirement
#: changed), so the MINOR component bumps once more.  0.3.0 -> 0.4.0 at
#: G2 stage S3 (2026-10-30): the UEC11-FC-R09 disposition flip plus its
#: new binding — the MAJOR class once more (dispositions + bindings).
PROFILE_VERSION = "0.4.0"

#: The executable checks (element 6) — real, existing tests only.  Every
#: entry names a file that must exist; the conformance test enforces that.
CHECKS: list[dict] = [
    {
        "check_id": "UEC11-CHK-01",
        "kind": "golden",
        "requirement_ids": ["UEC11-FC-R02"],
        "description": (
            "window-limited ring AllReduce completion identity t = "
            "2*(r-1)/r * M / min(B, W/(L+L_cr)) + 2*(r-1)*L, and the "
            "convergence anchor: at W >= B*(L+L_cr) the identity equals "
            "the landed L0 ring equation exactly (credits never gate); "
            "all expected values derived in the test by exact Fraction "
            "arithmetic"
        ),
        "location": "tests/golden/test_l0_tfc_golden.py",
    },
    {
        "check_id": "UEC11-CHK-02",
        "kind": "negative",
        "requirement_ids": ["UEC11-FC-R02", "UEC11-FC-R05"],
        "description": (
            "a tfc window not an integral number of 256-byte credit "
            "units is rejected at load time citing UEC11-FC-R05 (the "
            "credit granularity is a binding semantic, not a convention)"
        ),
        "location": "tests/golden/test_l0_tfc_golden.py",
    },
    {
        "check_id": "UEC11-CHK-03",
        "kind": "invariant",
        "requirement_ids": ["UEC11-FC-R02"],
        "description": (
            "admission in-flight bound min(B, W/(L+L_cr)) * (L + L_cr) "
            "<= W always, with equality iff window-limited (re-derived "
            "as an exact Fraction identity for every run)"
        ),
        "location": "tests/golden/test_l0_tfc_golden.py",
    },
    {
        "check_id": "UEC11-CHK-04",
        "kind": "invariant",
        "requirement_ids": ["UEC11-FC-R02"],
        "description": (
            "the UEC11-FC-R02 binding (since G8: the credit automaton "
            "BIND-UEC11-FC-R02-AUTOMATON, its declared steady-state "
            "abstraction checked two-sided) is re-verified against the "
            "live requirement registry, anchor registry, backend module "
            "(capability, config fields, spec-derived constant) and "
            "observable registry — drift is a hard error, not silent"
        ),
        "location": "tests/specir/test_bindings.py",
    },
    {
        "check_id": "UEC11-CHK-05",
        "kind": "golden",
        "requirement_ids": ["UEC11-FC-R08"],
        "description": (
            "cell-quantized ring AllReduce completion identity t = "
            "2*(r-1)/r * M / min(B, (c/cq)*W/(L+L_cr)) + 2*(r-1)*L with "
            "cq = ROUNDUP(c/cell)*cell and the ring chunk c = M/r as "
            "tfc_pkt_size, including the UEC11-FC-R08 worked example's "
            "ROUNDUP arithmetic (4352 B against 512-B cells => 4608 B) "
            "and the zero-waste convergence boundary: c = 0 (mod cell) "
            "gives cq = c and the identity equals the landed R02 "
            "identity exactly; all expected values derived in the test "
            "by exact Fraction arithmetic"
        ),
        "location": "tests/golden/test_l0_tfc_cell_golden.py",
    },
    {
        "check_id": "UEC11-CHK-06",
        "kind": "negative",
        "requirement_ids": ["UEC11-FC-R08", "UEC11-FC-R07"],
        "description": (
            "a tfc.dest_cell_size outside the supported set (below 256 B, "
            "above 9216 B, not an integral 256-B multiple, non-integral) "
            "is rejected at load time citing UEC11-FC-R07 — the cell "
            "domain values are spec-cited, and the closed boundaries 256 "
            "and 9216 load"
        ),
        "location": "tests/golden/test_l0_tfc_cell_golden.py",
    },
    {
        "check_id": "UEC11-CHK-07",
        "kind": "invariant",
        "requirement_ids": ["UEC11-FC-R08"],
        "description": (
            "quantized admission bound: per-op in-flight data bytes "
            "Rd*(L+L_cr) <= (c/cq)*W with equality iff the quantized "
            "window gates, while credit bytes in flight never exceed W "
            "(re-derived as an exact Fraction identity for every run)"
        ),
        "location": "tests/golden/test_l0_tfc_cell_golden.py",
    },
    {
        "check_id": "UEC11-CHK-08",
        "kind": "golden",
        "requirement_ids": ["UEC11-FC-R02"],
        "description": (
            "credit obligation automaton hand-derived golden traces "
            "(G8): the admission machine's burst schedule, the rejected "
            "trace on a credit-less transmit, the Eq. 3 rate law as the "
            "automaton's exact steady state when s | W, the "
            "(W mod s)/D packetization gap at the Eq. 3 convergence "
            "anchor, and the exact finite-collective divergence closed "
            "forms (in (-D, 0] credit-gated, 0 link-limited)"
        ),
        "location": "tests/golden/test_credit_automaton_golden.py",
    },
    {
        "check_id": "UEC11-CHK-09",
        "kind": "golden",
        "requirement_ids": ["UEC11-FC-R09"],
        "description": (
            "per-packet-overhead composed ring AllReduce identity t = "
            "2*(r-1)/r * M / min(B, (c/cq)*W/(L+L_cr)) + 2*(r-1)*L with "
            "tfc_pkt_size = c + tfc_pkt_overhead (default 256 B, "
            "UEC11-FC-R09) inside the ROUNDUP cell law, including the "
            "R08 worked example's native composition (4096 + 256 = 4352 "
            "B against 512-B cells => 4608 B), the overhead-is-cell-"
            "quantized law (any 1..256 B overhead at an aligned 256-B "
            "cell lands the same 9th cell), and the convergence "
            "boundary: tfc_pkt_overhead = 0 recovers the S2 identity "
            "exactly and with c = 0 (mod cell) recovers the landed R02 "
            "identity exactly; all expected values derived in the test "
            "by exact Fraction arithmetic"
        ),
        "location": "tests/golden/test_l0_tfc_pkt_golden.py",
    },
    {
        "check_id": "UEC11-CHK-10",
        "kind": "negative",
        "requirement_ids": ["UEC11-FC-R09", "UEC11-FC-R10"],
        "description": (
            "a tfc.pkt_overhead outside the configurable set (below 0 B, "
            "above 256 B, non-integral) is rejected at load time citing "
            "UEC11-FC-R10 — the overhead bounds are spec-cited, and the "
            "closed boundaries 0 and 256 load — and a declared overhead "
            "without tfc.dest_cell_size is rejected citing the binding "
            "(the ROUNDUP consumption law it feeds is the cell law)"
        ),
        "location": "tests/golden/test_l0_tfc_pkt_golden.py",
    },
    {
        "check_id": "UEC11-CHK-11",
        "kind": "invariant",
        "requirement_ids": ["UEC11-FC-R09"],
        "description": (
            "quantized admission bound with the composed packet: per-op "
            "in-flight data bytes Rd*(L+L_cr) <= (c/cq)*W with equality "
            "iff the quantized window gates, credit bytes in flight "
            "never exceed W, and the wire-byte ledger is unchanged (the "
            "overhead constant gates credit consumption, never byte "
            "count; re-derived as an exact Fraction identity for every "
            "run)"
        ),
        "location": "tests/golden/test_l0_tfc_pkt_golden.py",
    },
]

#: Known omissions (element 9) — stated visibly, honesty over coverage.
OMISSIONS: list[dict] = [
    {
        "what": (
            "255 of 445 requirements carry disposition unsupported: "
            "anchored but executed by no backend today"
        ),
        "reason": (
            "honesty over coverage: per-disposition counts are computed "
            "live (tools/disposition_coverage.py) and frozen in "
            "tests/specir/test_dispositions.py; a promotion is a "
            "reviewed act with a registered binding"
        ),
    },
    {
        "what": (
            "spec sections outside the interpreted mechanism set carry "
            "anchors but no interpreted requirements: chapters 1-2 "
            "(introduction, software layer, libfabric/verbs mapping; "
            "2.4 INC detail IS interpreted), 3.7 TSS, 3.8 references, "
            "chapter 4 overview (4.1 trimmed-packet facts ARE "
            "interpreted), 5.5 idle reduction, 6.2-6.5 PHY detail "
            "(6.1.x rates ARE interpreted), chapter 7 management, "
            "chapter 8 compliance, release notes"
        ),
        "reason": (
            "the S2-S5/S2b ladder interprets transport/link mechanisms "
            "relevant to fabric simulation; software APIs, management, "
            "and compliance chapters are not simulated semantics"
        ),
    },
    {
        "what": (
            "TFC credit request/grant protocol dynamics, retransmission "
            "credit exemption (UEC11-FC-R06), shared-CCC credit pooling "
            "(UEC11-FC-R16), per-direction cell/overhead asymmetry of a "
            "PDC pair (UEC11-FC-R12), and the cell/overhead "
            "configuration-support obligations (UEC11-FC-R07, "
            "UEC11-FC-R10)"
        ),
        "reason": (
            "a steady granted window W is the modeled abstraction; "
            "declared explicitly_unsupported by the analytical_l0_tfc "
            "backend's CAPABILITIES. Since G2 stages S2/S3 the credit-"
            "consumption ARITHMETIC executes — the ROUNDUP cell law "
            "(UEC11-FC-R08) when tfc_dest_cell_size is declared, and "
            "the per-packet overhead constant (UEC11-FC-R09) composing "
            "tfc_pkt_size = payload + tfc_pkt_overhead inside it when "
            "tfc.pkt_overhead is also declared — with the domain values "
            "cited to UEC11-FC-R07 and UEC11-FC-R10 respectively; the "
            "support/configurability obligations themselves do not"
        ),
    },
    {
        "what": (
            "RCCC receiver-driven credit scheduling across multiple "
            "concurrent sources (3.6.14, UEC11-CM-R66/R67)"
        ),
        "reason": (
            "needs multi-flow contention, which no backend models; the "
            "dispositions stay informational (choice record in "
            "src/essun/specir/bindings.py)"
        ),
    },
    {
        "what": "CBFC hop-level link credits (5.2, representative UEC11-FC-R36)",
        "reason": (
            "hop-level backpressure changes outputs only through "
            "queue-occupancy dynamics across hops — a queueing fidelity "
            "the analytical family excludes; disposition stays "
            "informational (choice record in src/essun/specir/bindings.py)"
        ),
    },
    {
        "what": (
            "congestion, packetization/FLIT effects, fill/drain start-up "
            "transients, overlapping collectives"
        ),
        "reason": (
            "excluded by the analytical L0 family's declared fidelity "
            "(explicitly_unsupported in every L0 backend's CAPABILITIES)"
        ),
    },
]

#: Versioning rules (element 10) — which changes bump which component.
BUMP_RULES: dict[str, list[str]] = {
    "major": [
        "dispositions",  # what the profile claims to execute changed
        "bindings",  # which backend executes which requirement changed
        "anchor_ids",  # a changed citation is a new version, never an edit
    ],
    "minor": ["requirements", "freedom", "checks", "supported"],
    "patch": ["notes"],
}

HEADER = f"""\
# UEC 1.1 semantic profile — {PROFILE_FORMAT_NAME} v{PROFILE_FORMAT_VERSION} artifact.
# GENERATED FILE (ladder S4 of the dispositions/profile work, 2026-10-29);
# regenerate with:
#   .venv/bin/python experiments/uec/build_semantic_profile.py
# Dispositions are READ from the live specir registry (the S1 record);
# this migration does not assign or change any disposition.  Anchor
# citations are unchanged from the stage modules and resolve against
# experiments/uec/anchor_registry.yaml.  Conformance gate:
# tests/specir/test_uec_semantic_profile.py (loads, disposition parity
# with the live registry, binding check, corruption rejection,
# byte-identical regeneration).
"""


def _load_source_record() -> dict:
    raw = yaml.safe_load(SOURCE_RECORD_PATH.read_text(encoding="utf-8"))
    missing = [
        key
        for key in ("source_id", "title", "version", "url", "access", "pdf_sha256")
        if not raw.get(key)
    ]
    if missing:
        raise SystemExit(
            f"source record {SOURCE_RECORD_PATH} is missing {missing}; "
            "the profile's provenance is copied verbatim from it"
        )
    return raw


def build_document() -> dict:
    """Build the ten-element artifact from the live registries."""
    record = _load_source_record()

    requirements: list[dict] = []
    freedom: list[dict] = []
    for module_name in UEC_REQUIREMENT_MODULES:
        module = importlib.import_module(module_name)
        short = module_name.rsplit(".", 1)[-1]
        for req in module.requirements():
            requirements.append(
                {
                    "requirement_id": req.requirement_id,
                    "anchor_ids": list(req.anchor_ids),
                    "keyword": req.keyword,
                    "subject": req.subject,
                    "statement": req.statement,
                    "disposition": req.disposition,  # S1 record, read-only
                    "module": short,  # owning stage module (extra, preserved)
                }
            )
        for param in module.free_parameters():
            freedom.append(
                {
                    "parameter_id": param.parameter_id,
                    "name": param.name,
                    "freedom": param.freedom,
                    "anchor_ids": list(param.anchor_ids),
                    "domain": "FREE",
                    "module": short,
                }
            )

    bindings = [
        {
            "binding_id": binding.binding_id,
            "requirement_id": binding.requirement_id,
            "backend": binding.backend_id,
            "capability": binding.capability,
            # Binding parameters whose VALUES the artifact does not fix:
            # free parameters, not standard-derived (the one spec-derived
            # constant is listed under spec_derived_constants).
            "parameters": {name: "FREE" for name in binding.parameters},
            "parameter_effect": binding.parameter_effect,
            "enforced_invariants": list(binding.enforced_invariants),
            "observable_ids": list(binding.observable_ids),
            "spec_derived_constants": [
                {
                    "name": name,
                    "value": value,
                    "requirement_id": source_requirement,
                }
                for name, value, source_requirement in binding.spec_derived_constants
            ],
            "golden_test": binding.golden_test,
            # G8 (2026-10-30): when the binding's backend is an exact
            # machine, the (module, backend_id) of its declared
            # steady-state abstraction ships too — two-sided with the
            # abstraction module's GROUND_TRUTH_AUTOMATON, re-verified
            # live by essun.specir.bindings.check_binding.
            **(
                {
                    "steady_state_abstraction": {
                        "module": binding.steady_state_abstraction[0],
                        "backend_id": binding.steady_state_abstraction[1],
                    }
                }
                if binding.steady_state_abstraction is not None
                else {}
            ),
            "note": binding.notes,
        }
        for binding in BINDINGS
    ]

    return {
        "format": {
            "name": PROFILE_FORMAT_NAME,
            "version": PROFILE_FORMAT_VERSION,
        },
        "profile_id": PROFILE_ID,
        # Element 1 — source identity/revision (from the license-gate record).
        "source": {
            "name": record["title"],
            "document_id": record["source_id"],
            "revision": str(record["version"]),
            "url": record["url"],
        },
        # Element 2 — provenance and permissions (license-gate vocabulary).
        "provenance": {
            "source_record": "experiments/uec/source_record.yaml",
            "access": record["access"],  # verbatim from the registry row
            "pdf_sha256": record["pdf_sha256"],
            "note": (
                "license review preceded ingestion (S0 license gate): the "
                "PDF stays out of git; verbatim spec text in this repo is "
                "limited to the anchor registry's <= 30-word quotes with "
                "attribution (CC BY-ND scope); requirement statements "
                "below are paraphrases in essun's own words"
            ),
        },
        # Element 3 — interpreted requirements WITH S1 dispositions.
        "requirements": {"objects": requirements},
        # Element 4 — declared implementation freedom.
        "freedom": freedom,
        # Element 5 — backend capability bindings (live registry).
        "bindings": bindings,
        # Element 6 — executable checks (curated above).
        "checks": CHECKS,
        # Element 7 — supported workloads/observables: the profile's
        # executable surface today is the flagship binding (W1 decode on
        # the TFC-windowed ring; O-CCT moves, O-CONSERVATION is the
        # byte-accounting self-check).
        "supported": {
            "workloads": ["w1_dense_tp_decode"],
            "observables": ["O-CCT", "O-CONSERVATION"],
        },
        # Element 8 — calibration scope (verification != calibration).
        "calibration": {
            "status": "uncalibrated",
            "targets": [],
            "note": (
                "E0 evidence level: identity and determinism only; no UEC "
                "hardware measurements exist. The free parameters B, L, W, "
                "L_cr (and, for the FC-R08/FC-R09 consumption extensions, "
                "tfc_dest_cell_size within the R07-cited domain and "
                "tfc_pkt_overhead within the R10-cited bounds) are not "
                "standard-derived and not measured; the only spec-derived "
                "constants are the 256-byte credit unit (UEC11-FC-R05), "
                "the cell domain values (UEC11-FC-R07), the overhead "
                "default 256 B (UEC11-FC-R09) and the overhead bounds "
                "0..256 B (UEC11-FC-R10)"
            ),
        },
        # Element 9 — known omissions (curated above).
        "omissions": OMISSIONS,
        # Element 10 — versioning rules.
        "versioning": {
            "profile_version": PROFILE_VERSION,
            "bump_rules": BUMP_RULES,
            "note": (
                "the profile version tracks this ARTIFACT, not the UEC "
                "source revision (source.revision carries 1.1); anchor "
                "citations are immutable — a changed citation is a new "
                "version, never a silent edit"
            ),
        },
    }


def validate_document(document: dict) -> list[str]:
    """Every gate the builder itself enforces before writing; [] = valid.

    Format (S3 loader), anchor citations against the live registry, and
    every binding against its declared backend's CAPABILITIES.  Since G8
    the profile binds MULTIPLE backends (the credit automaton plus the
    analytical ring); ``check_bindings_against`` is single-backend by
    design (the D2 primitive: a profile loading on one engine either
    matches or fails loudly), so the builder filters the profile to each
    backend's own bindings before the check — a binding is never judged
    against a foreign backend's capabilities.
    """
    problems = list(profile_problems(document))
    if problems:
        return problems
    profile = profile_from_dict(document, source="<built document>")
    problems.extend(check_anchor_refs(profile, AnchorRegistry.load()))
    modules = {
        binding.backend_id: importlib.import_module(binding.backend_module)
        for binding in BINDINGS
    }
    for backend_id in sorted({b.backend for b in profile.bindings}):
        own = dataclasses.replace(
            profile,
            bindings=tuple(b for b in profile.bindings if b.backend == backend_id),
        )
        problems.extend(
            check_bindings_against(own, modules[backend_id].CAPABILITIES)
        )
    return problems


def render(document: dict) -> str:
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        width=96,
        allow_unicode=True,
    )
    return HEADER + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=PROFILE_PATH,
        help=f"where to write the artifact (default: {PROFILE_PATH})",
    )
    args = parser.parse_args(argv)

    document = build_document()
    problems = validate_document(document)
    if problems:
        detail = "; ".join(problems[:10])
        more = "" if len(problems) <= 10 else f" (+{len(problems) - 10} more)"
        raise SystemExit(
            f"refusing to write an invalid profile artifact: {detail}{more}"
        )

    profile = profile_from_dict(document, source="<built document>")
    counts = profile.disposition_counts()
    executed = sum(counts[d] for d in ("constraint", "simulated_behavior", "conformance_test"))
    args.output.write_text(render(document), encoding="utf-8")
    print(f"wrote {args.output}")
    print(
        "review record: "
        f"{len(profile.requirements)} requirements "
        f"({counts['informational']} informational / "
        f"{counts['unsupported']} unsupported / "
        f"{counts['simulated_behavior']} simulated_behavior; "
        f"constraint {counts['constraint']}, conformance_test "
        f"{counts['conformance_test']}, not_applicable "
        f"{counts['not_applicable']}; {executed} executed), "
        f"{len(profile.freedom)} free parameters, "
        f"{len(profile.bindings)} binding(s), {len(profile.checks)} check(s)"
    )
    print(
        "dispositions are read from the live registry (S1 record); this "
        "builder cannot assign or change them"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
