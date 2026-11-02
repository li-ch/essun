"""Comparison submissions v0: the community's operating-point door.

Anyone can submit an OPERATING POINT — one workload, one shared
free-parameter record, one or two arms over committed topology files,
and results that cite content-addressed run ids — through the submission
issue (``.github/ISSUE_TEMPLATE/comparison-submission.md``).  This module
is the door's machinery: a document format (``docs/submission-format.md``
is the spec), a validator that REJECTS malformed input by design, and a
fairness check in the delta-zero style of the cross-fabric matrix
(``docs/atlas/cross-fabric-matrix.md`` §"What a fair comparison
requires"): everything the arms share must be verified equal — inputs,
not intentions — and only the declared axis may differ.

Three gates, in the order a submission meets them:

1. DOOR (this module, no store needed) —
   :func:`submission_problems` checks structure (exact field sets,
   vocabularies, patterns) plus the DECLARED fairness gates
   (:func:`fairness_problems`): the actual differences between the two
   arm blocks must be exactly the declared ``differs_on`` axes (an
   undeclared difference is a smuggled asymmetry; a declared axis that
   does not differ is a mislabeled comparison); arm parameters may not
   shadow the shared record; two-arm results must be paired across arms
   (observable + metric); and a ``control: true`` pair — the delta-zero
   anchor, arms claimed numerically identical — must report EXACTLY
   equal values.  A document carrying a ``review`` block is rejected at
   the door: a review is appended by the maintainer path, never
   self-written (the same refusal :mod:`essun.evidence.reproductions`
   applies to self-judged independence).

2. TREE (door, with the repo present) — the cited topology files and
   the shared record must be committed, repo-relative paths, and every
   shared parameter id must resolve to a knob that each arm's declared
   topology actually carries with the declared value (equal inputs
   verified from the files, not from the prose).  Implemented inside
   :func:`submission_problems` as ``tree_problems``.

3. STORE (:func:`verify_against_store`, the maintainer/reviewer step) —
   every cited run id must exist in the local evidence store; the stored
   observation must match the submitted value EXACTLY (Fractions; a
   submitted number that traces to nothing is rejected — no invented
   numbers at the door); all runs cited by one arm must share one
   operating point; across arms, ``workload_ir`` / ``assumptions`` /
   ``implementation_profile`` inputs must be IDENTICAL (the
   same-workload and identical-open-choices rules read off the run
   records themselves), ``infra_graph`` may differ only when the
   topology/parameters axis is declared, ``standard_profile`` only when
   the profile axis is declared; the run's manifest must be a committed
   path (public re-runnability); and the declared workload parameters
   must match the run's workload file.

Lifecycle: SUBMITTED at the door (the issue); the maintainer transcribes
into ``experiments/community/<name>.yaml`` and appends a ``review`` block
(``published`` requires every cited run id re-verified byte-for-byte —
checked mechanically as ``verified_run_ids`` covering the cited set).
``tools/community_table.py`` renders the public table from that
directory; the suite fails if the page and the records drift.

Identity: ``submission_id`` is the SHA-256 of the canonical-JSON
submission fields (review excluded), so the review never rewrites the
submission's identity — the same separation :func:`reproductions.reproduction_id`
draws for adjudications.

v0 limits (deliberate, documented in the spec): one or two arms; arms
compare through committed inputs only; the profile vocabulary is
``("none",)`` because ``standard_profile_none.yaml`` is the only
standard-profile input any landed backend consumes today — fabric
semantics enter through the committed topology file's honesty headers,
and widening the vocabulary is a code change with a spec bump, not a
 YAML edit.
"""

from __future__ import annotations

import hashlib
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .reproductions import AUTHOR_IDENTITIES

#: The format version this module validates; a document stating any
#: other version is rejected rather than guessed at.
FORMAT_VERSION = 0

#: Exactly the keys a submission document may carry (review excluded —
#: it is maintainer-appended and allowed only off the door path).
SUBMISSION_FIELDS = (
    "format_version",
    "submitted",
    "submitter",
    "source_url",
    "essun_commit",
    "backend",
    "workload",
    "shared_parameters",
    "arms",
    "comparison",
    "results",
)

#: Exactly the keys an arm block may carry.
ARM_FIELDS = ("label", "profile", "topology", "parameters")

#: Exactly the keys a comparison block may carry.
COMPARISON_FIELDS = ("differs_on", "control")

#: Exactly the keys a review block may carry.
REVIEW_FIELDS = ("decision", "reviewer", "date", "basis", "verified_run_ids")

#: The axes a two-arm comparison may declare as THE difference.  Anything
#: else the arms differ on is an undeclared asymmetry and the submission
#: is rejected.  At the run-record level: ``topology`` and ``parameters``
#: map to ``infra_graph`` inputs, ``profile`` to ``standard_profile``
#: inputs (see :func:`verify_against_store`).
DIFF_AXES = ("profile", "topology", "parameters")

#: Review decisions.  ``published`` is gated: every cited run id must
#: appear in ``verified_run_ids`` (the reviewer's re-execution record).
DECISIONS = ("published", "rejected")

#: Backend ids accepted at the door.  Mirrors the BACKEND_ID constants of
#: the backend modules; tests/evidence/test_submissions.py asserts the
#: equality so the tuple cannot drift silently.  Importing the adapters
#: here (docker-backed) would couple the evidence layer to the backend
#: layer, so the vocabulary is a constant with a drift guard instead.
BACKENDS = (
    "analytical_l0",
    "analytical_l0_crossbar",
    "analytical_l0_torus2d",
    "analytical_l0_recursive_doubling",
    "analytical_l0_phase_collectives",
    "analytical_l0_tfc",
    "analytical_l05",
    "astra_sim_analytical",
    "uet_htsim_cms",
)

#: Standard-profile vocabulary accepted at the door.  ``"none"`` is the
#: honesty artifact ``experiments/vertical_slice/profiles/standard_profile_none.yaml``
#: — the only standard-profile input any landed backend consumes today;
#: fabric semantics at L0 enter through the committed topology file's
#: honesty headers.  The semantic profile documents
#: (``experiments/uec/semantic_profile.yaml``,
#: ``experiments/unifiedbus/semantic_profile.yaml``) are anchor
#: registries, not run inputs; the vocabulary widens only when a backend
#: consumes one (code change + spec bump; drift-guarded by test).
PROFILES = ("none",)

#: Workload kinds accepted at the door, imported live from the generator
#: modules so the vocabulary cannot drift from the code that runs them.
from ..workload.w1 import WORKLOAD_KIND as _W1  # noqa: E402 (near use)
from ..workload.w2 import WORKLOAD_KIND as _W2  # noqa: E402
from ..workload.w3 import WORKLOAD_KIND as _W3  # noqa: E402
from ..workload.w5 import WORKLOAD_KIND as _W5  # noqa: E402

WORKLOAD_KINDS = (_W1, _W2, _W3, _W5)

#: Required integer parameters per workload kind (the generator configs'
#: positional fields), plus optional string parameters.  W3's
#: expert-share/placement/routing TABLES are not submittable through the
#: door at v0 — they are file artifacts, and the workload file itself is
#: the cited input (spec §limits).
WORKLOAD_PARAMETERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    _W1: (("tp_size", "layers", "steps", "allreduce_bytes"), ("model_name",)),
    _W2: (("tp_size", "layers", "chunks_per_layer", "chunk_bytes"), ("model_name",)),
    _W3: (
        ("tp_size", "layers", "experts_per_layer", "top_k", "tokens_per_rank", "token_bytes"),
        ("model_name", "routing"),
    ),
    _W5: (
        ("tp_size", "prefill_nodes", "requests", "chunks_per_request", "chunk_bytes", "decode_steps"),
        ("model_name",),
    ),
}

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_URL_RE = re.compile(r"^https?://")
_REPO_PATH_RE = re.compile(r"^[\w./-]+$")

#: Run-record input keys that must NEVER differ across arms (the
#: same-workload and identical-open-choices rules, read off the runs).
_ALWAYS_ZERO_INPUTS = ("workload_ir", "assumptions", "implementation_profile")
#: Run-record input keys a declared axis exempts.
_AXIS_EXEMPT_INPUTS = {
    "topology": ("infra_graph",),
    "parameters": ("infra_graph", "assumptions"),
    "profile": ("standard_profile",),
}


class SubmissionError(ValueError):
    """Raised when a submission document (or its review) is malformed.

    A ``ValueError`` subclass, matching the house pattern of
    :class:`essun.evidence.reproductions.ReproductionError`.
    """


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _str_problems(field: str, value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"submission: {field} must be a non-empty string"]
    return []


def _date_problems(field: str, value: Any) -> list[str]:
    problems = _str_problems(field, value)
    if problems:
        return problems
    if not _DATE_RE.match(value):
        return [f"submission: {field} must be an ISO date (YYYY-MM-DD), got {value!r}"]
    return []


def _hex_problems(field: str, value: Any, length: int) -> list[str]:
    problems = _str_problems(field, value)
    if problems:
        return problems
    pattern = {40: _COMMIT_RE, 64: _RUN_ID_RE}[length]
    if not pattern.match(value):
        return [
            f"submission: {field} must be {length} lowercase hex characters, got {value!r}"
        ]
    return []


def _fraction(value: Any) -> Fraction | None:
    """Exact Fraction of a result value; None when not interpretable.

    Accepts ints and strings (decimal or fraction strings, read exactly);
    floats enter via ``str()`` per the observables module's arithmetic
    policy, so ``3696.0`` and ``"3696"`` are the same number.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Fraction(str(value))
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError):
            return None
    return None


def _mapping_problems(field: str, value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"submission: {field} must be a mapping"]
    return []


def _int_parameters_problems(field: str, value: Any, *, required: bool) -> list[str]:
    """A {name: positive int} mapping; empty allowed only when not required."""
    problems = _mapping_problems(field, value)
    if problems:
        return problems
    problems = []
    if required and not value:
        problems.append(f"submission: {field} must not be empty")
    for name, item in value.items():
        if not isinstance(name, str) or not name:
            problems.append(f"submission: each key of {field} must be a non-empty string")
            continue
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            problems.append(
                f"submission: {field}[{name!r}] must be a positive integer, got {item!r}"
            )
    return problems


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------


def _workload_problems(workload: Any) -> list[str]:
    problems = _mapping_problems("workload", workload)
    if problems:
        return problems
    unknown = [key for key in workload if key not in ("kind", "parameters")]
    if unknown:
        return [f"submission: workload has unknown field(s): {', '.join(sorted(unknown))}"]
    missing = [key for key in ("kind", "parameters") if key not in workload]
    if missing:
        return [f"submission: workload is missing field(s): {', '.join(missing)}"]
    problems = []
    kind = workload["kind"]
    if kind not in WORKLOAD_KINDS:
        problems.append(
            f"submission: workload.kind must be one of {WORKLOAD_KINDS}, got {kind!r}"
        )
        return problems
    required, optional = WORKLOAD_PARAMETERS[kind]
    parameters = workload["parameters"]
    problems.extend(
        _int_parameters_problems("workload.parameters", parameters, required=True)
    )
    if isinstance(parameters, Mapping):
        for name in parameters:
            if name in required:
                if isinstance(parameters[name], bool) or not isinstance(parameters[name], int):
                    problems.append(
                        f"submission: workload.parameters[{name!r}] must be an integer"
                    )
            elif name not in optional:
                problems.append(
                    f"submission: workload.parameters has unknown key {name!r} for kind "
                    f"{kind!r} (allowed: {', '.join(required + optional)})"
                )
            elif not isinstance(parameters[name], str) or not parameters[name]:
                problems.append(
                    f"submission: workload.parameters[{name!r}] must be a non-empty string"
                )
    return problems


def _arm_problems(arm: Any, index: int) -> list[str]:
    where = f"arms[{index}]"
    problems = _mapping_problems(where, arm)
    if problems:
        return problems
    unknown = [key for key in arm if key not in ARM_FIELDS]
    if unknown:
        return [f"submission: {where} has unknown field(s): {', '.join(sorted(unknown))}"]
    missing = [key for key in ARM_FIELDS if key not in arm]
    if missing:
        return [f"submission: {where} is missing field(s): {', '.join(missing)}"]
    problems = []
    problems.extend(_str_problems(f"{where}.label", arm["label"]))
    if arm["profile"] not in PROFILES:
        problems.append(
            f"submission: {where}.profile must be one of {PROFILES}, got {arm['profile']!r} "
            "(the standard-profile vocabulary widens only when a backend consumes a "
            "semantic profile as a run input; see docs/submission-format.md)"
        )
    topology = arm["topology"]
    problems.extend(_str_problems(f"{where}.topology", topology))
    if isinstance(topology, str) and topology and not _REPO_PATH_RE.match(topology):
        problems.append(
            f"submission: {where}.topology must be a repo-relative committed path, "
            f"got {topology!r}"
        )
    problems.extend(
        _int_parameters_problems(f"{where}.parameters", arm["parameters"], required=False)
    )
    return problems


def _results_problems(results: Any, labels: set[str]) -> list[str]:
    if not isinstance(results, list) or not results:
        return ["submission: results must be a non-empty list"]
    problems = []
    for index, row in enumerate(results):
        where = f"results[{index}]"
        if not isinstance(row, Mapping):
            problems.append(f"submission: {where} must be a mapping")
            continue
        unknown = [key for key in row if key not in ("arm", "observable", "metric", "value", "run_ids")]
        if unknown:
            problems.append(
                f"submission: {where} has unknown field(s): {', '.join(sorted(unknown))}"
            )
            continue
        missing = [key for key in ("arm", "observable", "metric", "value", "run_ids") if key not in row]
        if missing:
            problems.append(f"submission: {where} is missing field(s): {', '.join(missing)}")
            continue
        if row["arm"] not in labels:
            problems.append(
                f"submission: {where}.arm must name a declared arm label, "
                f"got {row['arm']!r} (declared: {', '.join(sorted(labels)) or 'none'})"
            )
        if not isinstance(row["metric"], str) or not row["metric"]:
            problems.append(f"submission: {where}.metric must be a non-empty string")
        if _fraction(row["value"]) is None:
            problems.append(
                f"submission: {where}.value must be a number or an exact numeric "
                f"string, got {row['value']!r}"
            )
        run_ids = row["run_ids"]
        if not isinstance(run_ids, list) or not run_ids:
            problems.append(
                f"submission: {where}.run_ids must be a non-empty list of run ids "
                "(a result without a run id is an opinion)"
            )
        else:
            if len(set(run_ids)) != len(run_ids):
                problems.append(f"submission: {where}.run_ids has duplicate entries")
            for position, run_id in enumerate(run_ids):
                problems.extend(
                    _hex_problems(f"{where}.run_ids[{position}]", run_id, 64)
                )
    return problems


def _observable_problems(results: Any) -> list[str]:
    """Every cited observable must be in the registry (import registers)."""
    from .. import observables  # noqa: F401 (import runs the registrations)

    registered = set(observables.registered())
    problems = []
    for index, row in enumerate(results) if isinstance(results, list) else []:
        if isinstance(row, Mapping) and "observable" in row:
            if row["observable"] not in registered:
                problems.append(
                    f"submission: results[{index}].observable {row['observable']!r} is "
                    f"not registered (registered: {', '.join(sorted(registered))})"
                )
    return problems


def submission_problems(
    record: Any,
    *,
    at_door: bool = True,
    repo_root: Path | str | None = None,
) -> list[str]:
    """All problems of a submission document; empty means it passes the door.

    Structure, vocabularies, and patterns first; then the fairness gates
    (:func:`fairness_problems`); then, when ``repo_root`` is given, the
    tree gates (committed paths + shared parameters verified against the
    declared topology files).  ``at_door`` refuses a ``review`` block —
    reviews are appended by the maintainer path, never self-written.
    Messages are ``submission:``-prefixed per the house style.
    """
    if not isinstance(record, Mapping):
        return ["submission: must be a mapping"]
    problems: list[str] = []
    if at_door and "review" in record:
        problems.append(
            "submission: a review block is appended by the maintainer path, never "
            "accepted at the door (remove the 'review' key)"
        )
    if not at_door and "review" not in record:
        problems.append(
            "submission: committed copies under experiments/community/ must carry a "
            "review block (pending submissions live on the issue)"
        )
    known = set(SUBMISSION_FIELDS) | {"review"}
    unknown = [key for key in record if key not in known]
    if unknown:
        problems.append(
            f"submission: unknown field(s): {', '.join(sorted(unknown))}"
        )
    required = SUBMISSION_FIELDS if len(record.get("arms") or []) == 2 else tuple(
        field for field in SUBMISSION_FIELDS if field != "comparison"
    )
    missing = [field for field in required if field not in record]
    if missing:
        problems.append(f"submission: missing field(s): {', '.join(missing)}")
    if problems:
        return problems

    if record["format_version"] != FORMAT_VERSION:
        problems.append(
            f"submission: format_version must be {FORMAT_VERSION}, "
            f"got {record['format_version']!r}"
        )
    problems.extend(_date_problems("submitted", record["submitted"]))
    problems.extend(_str_problems("submitter", record["submitter"]))
    if not _URL_RE.match(record["source_url"]):
        problems.append(
            f"submission: source_url must be a public http(s) URL, got {record['source_url']!r}"
        )
    problems.extend(_hex_problems("essun_commit", record["essun_commit"], 40))
    if record["backend"] not in BACKENDS:
        problems.append(
            f"submission: backend must be one of {BACKENDS}, got {record['backend']!r}"
        )
    problems.extend(_workload_problems(record["workload"]))

    shared = record["shared_parameters"]
    problems.extend(_mapping_problems("shared_parameters", shared))
    if isinstance(shared, Mapping):
        unknown = [key for key in shared if key not in ("record", "values")]
        if unknown:
            problems.append(
                f"submission: shared_parameters has unknown field(s): {', '.join(sorted(unknown))}"
            )
        else:
            if not isinstance(shared["record"], str) or not _REPO_PATH_RE.match(
                shared["record"] or ""
            ):
                problems.append(
                    "submission: shared_parameters.record must be a repo-relative "
                    f"committed path, got {shared['record']!r}"
                )
            problems.extend(
                _int_parameters_problems(
                    "shared_parameters.values", shared["values"], required=True
                )
            )

    arms = record["arms"]
    if not isinstance(arms, list) or not 1 <= len(arms) <= 2:
        problems.append(
            f"submission: arms must be a list of one or two arm blocks, got {arms!r}"
        )
        return problems
    if len(arms) == 1 and "comparison" in record:
        problems.append(
            "submission: comparison is a two-arm field; a single-arm operating point "
            "must not carry one"
        )
    labels: list[str] = []
    for index, arm in enumerate(arms):
        problems.extend(_arm_problems(arm, index))
        if isinstance(arm, Mapping) and isinstance(arm.get("label"), str):
            labels.append(arm["label"])
    if len(set(labels)) != len(labels):
        problems.append("submission: arm labels must be unique")

    comparison = record.get("comparison")
    if len(arms) == 2:
        problems.extend(_mapping_problems("comparison", comparison))
        if isinstance(comparison, Mapping):
            unknown = [key for key in comparison if key not in COMPARISON_FIELDS]
            if unknown:
                problems.append(
                    f"submission: comparison has unknown field(s): {', '.join(sorted(unknown))}"
                )
            else:
                differs_on = comparison["differs_on"]
                if not isinstance(differs_on, list) or not differs_on:
                    problems.append(
                        "submission: comparison.differs_on must be a non-empty list of axes "
                        f"from {DIFF_AXES}"
                    )
                else:
                    if len(set(differs_on)) != len(differs_on):
                        problems.append("submission: comparison.differs_on has duplicate axes")
                    for axis in differs_on:
                        if axis not in DIFF_AXES:
                            problems.append(
                                f"submission: comparison.differs_on axis {axis!r} is not one "
                                f"of {DIFF_AXES}"
                            )
                if not isinstance(comparison["control"], bool):
                    problems.append("submission: comparison.control must be a boolean")
    if not problems:
        problems.extend(_observable_problems(record["results"]))
        problems.extend(_results_problems(record["results"], set(labels)))
    if not problems:
        problems.extend(fairness_problems(record))
    if not problems and repo_root is not None:
        problems.extend(tree_problems(record, Path(repo_root)))
    return problems


def validate_submission(
    record: Any,
    *,
    at_door: bool = True,
    repo_root: Path | str | None = None,
) -> None:
    """Validate a submission document; raise :class:`SubmissionError`."""
    problems = submission_problems(record, at_door=at_door, repo_root=repo_root)
    if problems:
        raise SubmissionError("; ".join(problems))


# ---------------------------------------------------------------------------
# the fairness gates (declared level)
# ---------------------------------------------------------------------------


def fairness_problems(submission: Mapping) -> list[str]:
    """The delta-zero fairness gates over the DECLARED document.

    For a two-arm submission:

    - F1 axis exactness: the arm blocks' actually-differing fields must
      be exactly the declared ``differs_on`` axes — an undeclared
      difference is a smuggled asymmetry; a declared axis that does not
      differ is a mislabeled comparison.
    - F2 no shadowing: an arm's ``parameters`` may not name an id in the
      shared record's ``values`` (a per-arm override of a declared-shared
      parameter is how unequal inputs hide).
    - F3 paired results: every (observable, metric) reported for one arm
      is reported for the other — a table that shows only one arm's
      number is not a comparison.
    - F4 control/delta-zero: when ``control: true`` declares the arms
      numerically identical (the honesty-anchor pattern of the
      cross-fabric matrix), every paired value must be EXACTLY equal.

    Single-arm submissions have no comparison block and no fairness
    pairing; the gates that apply to them live in the structure checks.
    """
    problems: list[str] = []
    arms = submission.get("arms")
    if not isinstance(arms, list) or len(arms) != 2:
        return problems  # single-arm: nothing to compare; structure covers it
    arm_a, arm_b = arms
    if not (isinstance(arm_a, Mapping) and isinstance(arm_b, Mapping)):
        return problems
    comparison = submission.get("comparison")
    if not isinstance(comparison, Mapping):
        return problems

    # F1 — the declared axis set must equal the actual difference set.
    actual: set[str] = set()
    if arm_a.get("profile") != arm_b.get("profile"):
        actual.add("profile")
    if arm_a.get("topology") != arm_b.get("topology"):
        actual.add("topology")
    if arm_a.get("parameters") != arm_b.get("parameters"):
        actual.add("parameters")
    declared = set(comparison.get("differs_on") or [])
    undeclared = sorted(actual - declared)
    not_actual = sorted(declared - actual)
    if undeclared:
        problems.append(
            "submission: unfair comparison — the arms differ on undeclared axis(es) "
            f"{', '.join(undeclared)}; declare them in comparison.differs_on or make "
            "the arms equal there (a fair comparison changes only what it names)"
        )
    if not_actual:
        problems.append(
            "submission: mislabeled comparison — axis(es) "
            f"{', '.join(not_actual)} declared in differs_on but the arms do not "
            "differ there"
        )

    # F2 — per-arm parameters may not shadow the shared record.
    shared = submission.get("shared_parameters")
    shared_ids = set()
    if isinstance(shared, Mapping) and isinstance(shared.get("values"), Mapping):
        shared_ids = set(shared["values"])
    for index, arm in enumerate(arms):
        arm_ids = set(arm.get("parameters") or {})
        shadowed = sorted(arm_ids & shared_ids)
        if shadowed:
            problems.append(
                f"submission: arms[{index}].parameters shadows shared parameter id(s) "
                f"{', '.join(shadowed)}; a parameter declared shared cannot carry a "
                "per-arm value"
            )

    # F3 — paired results across arms.
    results = submission.get("results")
    per_arm: dict[str, set[tuple[str, str]]] = {"a": set(), "b": set()}
    if isinstance(results, list):
        for row in results:
            if not isinstance(row, Mapping):
                continue
            key = (str(row.get("observable", "")), str(row.get("metric", "")))
            if row.get("arm") == arm_a.get("label"):
                per_arm["a"].add(key)
            elif row.get("arm") == arm_b.get("label"):
                per_arm["b"].add(key)
    only_a = sorted(per_arm["a"] - per_arm["b"])
    only_b = sorted(per_arm["b"] - per_arm["a"])
    for side, keys in (("first", only_a), ("second", only_b)):
        if keys:
            problems.append(
                f"submission: unpaired result(s) — the {side} arm reports "
                f"{', '.join(f'{obs}/{metric}' for obs, metric in keys)} with no "
                "matching row for the other arm; a comparison shows both sides"
            )

    # F4 — the delta-zero control: claimed-identical arms report equal values.
    if comparison.get("control") is True and isinstance(results, list):
        values: dict[tuple[str, str, str], Fraction] = {}
        for row in results:
            if not isinstance(row, Mapping):
                continue
            exact = _fraction(row.get("value"))
            if exact is None:
                continue
            key = (str(row.get("observable", "")), str(row.get("metric", "")), str(row.get("arm", "")))
            values[key] = exact
        for observable, metric in sorted(per_arm["a"] & per_arm["b"]):
            value_a = values.get((observable, metric, str(arm_a.get("label"))))
            value_b = values.get((observable, metric, str(arm_b.get("label"))))
            if value_a is not None and value_b is not None and value_a != value_b:
                problems.append(
                    "submission: control pair violated — comparison.control declares "
                    f"the arms numerically identical, but {observable}/{metric} "
                    f"reports {value_a} vs {value_b} (delta must be exactly zero)"
                )
    return problems


# ---------------------------------------------------------------------------
# the tree gates (door + repo present)
# ---------------------------------------------------------------------------


def _knob_value(topology: Mapping, spelling: str) -> Any:
    """Dotted-path lookup of one knob spelling in a topology mapping."""
    node: Any = topology
    for part in spelling.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def tree_problems(submission: Mapping, repo_root: Path) -> list[str]:
    """Door gates that need the tree: committed paths + equal shared inputs.

    Every declared topology file and the shared record must exist as
    committed files (a submission is re-runnable from the public tree or
    it is not submittable), and every id in ``shared_parameters.values``
    must resolve — through the shared record's ``parameter`` spellings —
    to a knob that EACH arm's declared topology file carries with the
    declared value.  This is the delta-zero check on inputs at the door:
    the numbers the submission claims are shared are read out of the
    files, not taken on prose.
    """
    import yaml

    problems: list[str] = []
    record_path = repo_root / submission["shared_parameters"]["record"]
    if not record_path.is_file():
        return [
            f"submission: shared_parameters.record is not a committed file: "
            f"{submission['shared_parameters']['record']}"
        ]
    record_doc = yaml.safe_load(record_path.read_text(encoding="utf-8")) or {}
    spellings_by_id = {
        entry.get("id"): [
            spelling.strip()
            for spelling in str(entry.get("parameter", "")).split("|")
            if spelling.strip()
        ]
        for entry in record_doc.get("assumptions", [])
        if isinstance(entry, Mapping)
    }

    topologies: list[tuple[str, Mapping]] = []
    for index, arm in enumerate(submission["arms"]):
        path = repo_root / arm["topology"]
        if not path.is_file():
            problems.append(
                f"submission: arms[{index}].topology is not a committed file: "
                f"{arm['topology']}"
            )
            continue
        topologies.append((arm["topology"], yaml.safe_load(path.read_text(encoding="utf-8")) or {}))

    for parameter_id, declared_value in sorted(submission["shared_parameters"]["values"].items()):
        spellings = spellings_by_id.get(parameter_id)
        if spellings is None:
            problems.append(
                f"submission: shared_parameters.values names unknown id {parameter_id!r} "
                f"(not in {submission['shared_parameters']['record']})"
            )
            continue
        for topology_path, topology in topologies:
            found = [(s, _knob_value(topology, s)) for s in spellings]
            present = [(s, v) for s, v in found if v is not None]
            if not present:
                problems.append(
                    f"submission: shared parameter {parameter_id!r} carries none of its "
                    f"spellings ({', '.join(spellings)}) in {topology_path}; a declared-"
                    "shared input must exist in every arm's topology"
                )
                continue
            for spelling, value in present:
                if value != declared_value:
                    problems.append(
                        f"submission: shared parameter {parameter_id!r} is declared "
                        f"{declared_value} but {topology_path} carries {spelling}="
                        f"{value!r} — the arms would not share it"
                    )
    return problems


# ---------------------------------------------------------------------------
# the store gates (reviewer step)
# ---------------------------------------------------------------------------


def verify_against_store(
    submission: Mapping,
    store: Any,
    repo_root: Path | str,
) -> list[str]:
    """The reviewer's verification: cited runs must back every number.

    Requires an :class:`essun.evidence.store.EvidenceStore` root that
    holds the cited run ids (rebuild via the cited committed manifests —
    ``make run EXP=<manifest>``); every gate below is mechanical:

    - V1 every cited run id exists in the store;
    - V2 the stored observation's value for (observable, metric) equals
      the submitted value EXACTLY (Fractions; floats via ``str()``), and
      the stored run executed on the declared backend;
    - V3 all runs cited by one arm share one operating point (identical
      ``inputs`` blocks);
    - V4 across arms, ``workload_ir`` / ``assumptions`` /
      ``implementation_profile`` inputs are IDENTICAL (same workload,
      identical open choices), and ``infra_graph`` / ``standard_profile``
      inputs differ only under a declared axis (the delta-zero check on
      the run records' own content);
    - V5 each run's manifest is a committed path (public re-runnability);
    - V6 the declared workload kind and integer parameters match the
      runs' workload file;
    - V7 each arm's declared topology is the run's actual ``infra_graph``
      input, and the standard-profile input matches the declared profile.
    """
    root = Path(repo_root)
    problems: list[str] = []
    label_to_arm = {arm["label"]: arm for arm in submission["arms"]}

    # V1 + V2 + per-run facts
    run_inputs: dict[str, dict[str, Any]] = {}
    run_observations: dict[str, Any] = {}
    missing: set[str] = set()
    for row in submission["results"]:
        for run_id in row["run_ids"]:
            if run_id in run_inputs or run_id in missing:
                continue
            if not (store.run_dir(run_id) / "run.json").is_file():
                missing.add(run_id)
                continue
            record = store.get_run(run_id)
            run_inputs[run_id] = {
                key: record["inputs"][key]
                for key in (
                    "workload_ir",
                    "assumptions",
                    "standard_profile",
                    "implementation_profile",
                    "infra_graph",
                )
                if key in record.get("inputs", {})
            }
            run_observations[run_id] = _load_observations(store, run_id)
    for run_id in sorted(missing):
        problems.append(
            f"submission: cited run {run_id} is not in the local store — rebuild it "
            "from its committed manifest before review (no invented numbers at the door)"
        )

    for index, row in enumerate(submission["results"]):
        where = f"results[{index}]"
        for run_id in row["run_ids"]:
            if run_id in missing:
                continue
            observations = run_observations.get(run_id)
            if observations is None:
                continue
            if observations.get("backend_id") != submission["backend"]:
                problems.append(
                    f"submission: {where} cites run {run_id} executed on backend "
                    f"{observations.get('backend_id')!r}, not the declared "
                    f"{submission['backend']!r}"
                )
            observable = observations.get("observables", {}).get(row["observable"])
            if not isinstance(observable, Mapping) or row["metric"] not in observable:
                problems.append(
                    f"submission: {where} cites run {run_id} which does not report "
                    f"{row['observable']}/{row['metric']}"
                )
                continue
            stored = _fraction(observable[row["metric"]])
            declared = _fraction(row["value"])
            if stored is None or declared is None or stored != declared:
                problems.append(
                    f"submission: {where}.value {row['value']!r} does not match run "
                    f"{run_id}, whose stored {row['observable']}/{row['metric']} is "
                    f"{observable[row['metric']]!r} — submitted numbers must trace to "
                    "the cited run exactly"
                )
    if problems:
        return problems

    # V3 — one operating point per arm.
    def canonical(value: Any) -> str:
        from .store import canonical_json

        return canonical_json(value)

    per_arm_inputs: dict[str, dict[str, Any]] = {}
    for row in submission["results"]:
        for run_id in row["run_ids"]:
            arm_label = row["arm"]
            held = per_arm_inputs.setdefault(arm_label, {})
            for key, value in run_inputs[run_id].items():
                if key in held and canonical(held[key]) != canonical(value):
                    problems.append(
                        f"submission: arm {arm_label!r} cites runs with different {key} "
                        f"inputs ({held[key].get('path')} vs {value.get('path')}); one "
                        "arm is one operating point"
                    )
                held[key] = value
    if problems:
        return problems

    # V5 + V6 — manifests and workload file consistency.
    for run_id, inputs in run_inputs.items():
        manifest = store.get_run(run_id).get("manifest_path", "")
        if not manifest or not (root / manifest).is_file():
            problems.append(
                f"submission: run {run_id} names manifest {manifest!r} which is not a "
                "committed path; a submission must be re-runnable from the public tree"
            )
    workload_path = None
    for inputs in per_arm_inputs.values():
        if "workload_ir" in inputs:
            workload_path = root / inputs["workload_ir"]["path"]
            break
    if workload_path is not None and workload_path.is_file():
        import yaml

        workload_doc = yaml.safe_load(workload_path.read_text(encoding="utf-8")) or {}
        if workload_doc.get("workload") != submission["workload"]["kind"]:
            problems.append(
                f"submission: workload.kind {submission['workload']['kind']!r} does not "
                f"match the runs' workload file {workload_path.name} "
                f"(kind {workload_doc.get('workload')!r})"
            )
        else:
            for name, value in submission["workload"]["parameters"].items():
                if name in workload_doc and workload_doc[name] != value:
                    problems.append(
                        f"submission: workload.parameters[{name!r}]={value!r} does not "
                        f"match the runs' workload file ({name}={workload_doc[name]!r} "
                        f"in {workload_path.name})"
                    )
    elif workload_path is not None:
        problems.append(
            f"submission: the runs' workload file is not committed: {workload_path}"
        )
    if problems:
        return problems

    # V4 — cross-arm input delta-zero (two-arm submissions only).
    if len(submission["arms"]) == 2:
        arm_labels = [arm["label"] for arm in submission["arms"]]
        inputs_a = per_arm_inputs.get(arm_labels[0], {})
        inputs_b = per_arm_inputs.get(arm_labels[1], {})
        declared = set(submission["comparison"]["differs_on"])
        exempt: set[str] = set()
        for axis in declared:
            exempt.update(_AXIS_EXEMPT_INPUTS.get(axis, ()))
        for key in sorted(set(inputs_a) | set(inputs_b)):
            same = canonical(inputs_a.get(key)) == canonical(inputs_b.get(key))
            if key in _ALWAYS_ZERO_INPUTS and not same:
                problems.append(
                    f"submission: unfair comparison — the arms' runs differ on {key} "
                    f"({inputs_a.get(key, {}).get('path')} vs "
                    f"{inputs_b.get(key, {}).get('path')}); {key} must be identical on "
                    "both sides (same workload, identical open choices)"
                )
            elif key not in _ALWAYS_ZERO_INPUTS and not same and key not in exempt:
                problems.append(
                    f"submission: unfair comparison — the arms' runs differ on {key} "
                    "but no declared axis exempts it; declare the axis or equalize the "
                    "input"
                )
            # a declared axis MAY leave its exempt input equal (tie regions exist)
        # V7 — declared topology/profile vs the runs' actual inputs.
        for arm in submission["arms"]:
            inputs = per_arm_inputs.get(arm["label"], {})
            infra = inputs.get("infra_graph", {}).get("path")
            if infra is not None and infra != arm["topology"]:
                problems.append(
                    f"submission: arm {arm['label']!r} declares topology {arm['topology']!r} "
                    f"but its cited runs consumed {infra!r}"
                )
            std = inputs.get("standard_profile", {}).get("path", "")
            expected_std = "experiments/vertical_slice/profiles/standard_profile_none.yaml"
            if arm["profile"] == "none" and std and not std.endswith(
                "standard_profile_none.yaml"
            ):
                problems.append(
                    f"submission: arm {arm['label']!r} declares profile 'none' but its "
                    f"cited runs consumed standard profile {std!r}"
                )
    return problems


def _load_observations(store: Any, run_id: str) -> Any:
    import json

    path = store.run_dir(run_id) / "observations.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# review, identity, loading, rendering, CLI
# ---------------------------------------------------------------------------


def review_problems(review: Any, submission: Mapping) -> list[str]:
    """All problems of a maintainer review block against its submission.

    The ``published`` gate is mechanical: every run id cited anywhere in
    the submission's results must appear in ``verified_run_ids`` — the
    reviewer's record of which ids re-executed byte-for-byte.  A review
    naming runs the submission does not cite, or covering less than the
    whole cited set while publishing, is rejected.
    """
    if not isinstance(review, Mapping):
        return ["review: must be a mapping"]
    missing = [field for field in REVIEW_FIELDS if field not in review]
    if missing:
        return [f"review: missing field(s): {', '.join(missing)}"]
    unknown = [key for key in review if key not in REVIEW_FIELDS]
    if unknown:
        return [f"review: unknown field(s): {', '.join(sorted(unknown))}"]
    problems: list[str] = []
    if review["decision"] not in DECISIONS:
        problems.append(f"review: decision must be one of {DECISIONS}, got {review['decision']!r}")
    for field in ("reviewer", "basis"):
        if not isinstance(review[field], str) or not review[field]:
            problems.append(f"review: {field} must be a non-empty string")
    if isinstance(review["date"], str) and review["date"]:
        if not _DATE_RE.match(review["date"]):
            problems.append(
                f"review: date must be an ISO date (YYYY-MM-DD), got {review['date']!r}"
            )
    else:
        problems.append("review: date must be an ISO date (YYYY-MM-DD)")
    cited = {run_id for row in submission.get("results", []) for run_id in row.get("run_ids", [])}
    verified = review["verified_run_ids"]
    if not isinstance(verified, list):
        problems.append("review: verified_run_ids must be a list of run ids")
        verified = []
    else:
        for run_id in verified:
            problems.extend(_hex_problems("review.verified_run_ids entry", run_id, 64))
    if review["decision"] == "published" and not problems:
        unverified = sorted(cited - set(verified))
        if unverified:
            problems.append(
                "review: decision published requires every cited run id re-verified "
                f"(unverified: {', '.join(unverified)})"
            )
    extra = sorted(set(verified) - cited)
    if extra:
        problems.append(
            "review: verified_run_ids names run id(s) the submission does not cite: "
            f"{', '.join(extra)}"
        )
    return problems


def submission_id(submission: Mapping) -> str:
    """Content address: SHA-256 over the canonical-JSON submission fields.

    The review is outside the address on purpose — appending one never
    rewrites the submission's identity (the same separation the
    reproduction record draws for adjudications).
    """
    from .store import canonical_json

    body = {key: value for key, value in submission.items() if key != "review"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def load_submission_file(
    path: Path | str,
    *,
    at_door: bool = True,
    repo_root: Path | str | None = None,
) -> tuple[dict, dict | None]:
    """Parse and validate one submission YAML file.

    Returns ``(submission, review or None)``.  ``at_door`` refuses a
    review block (the submitter's pre-check); the maintainer path
    (``at_door=False``, used for ``experiments/community/*.yaml``)
    requires one and cross-checks it against the submission.
    """
    path = Path(path)
    import yaml

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SubmissionError(f"{path.name}: unreadable ({error})") from error
    except yaml.YAMLError as error:
        raise SubmissionError(f"{path.name}: invalid YAML ({error})") from error
    if not isinstance(document, dict):
        raise SubmissionError(f"{path.name}: must be a mapping of submission fields")

    if at_door and "review" in document:
        raise SubmissionError(
            f"{path.name}: submission: a review block is appended by the maintainer "
            "path, never accepted at the door (remove the 'review' key)"
        )
    had_review = "review" in document
    review = document.pop("review", None)
    if not at_door and not had_review:
        raise SubmissionError(
            f"{path.name}: submission: committed copies under experiments/community/ "
            "must carry a review block (pending submissions live on the issue)"
        )
    problems = submission_problems(document, repo_root=repo_root)
    if problems:
        raise SubmissionError(f"{path.name}: " + "; ".join(problems))
    if review is not None:
        problems = review_problems(review, document)
        if problems:
            raise SubmissionError(f"{path.name}: " + "; ".join(problems))
    return dict(document), dict(review) if review is not None else None


def render_table_rows(records: list[tuple[dict, dict | None]]) -> str:
    """Deterministic HTML for the community table, one row per submission.

    Input order is ignored: rows sort by (submitted, submission_id), so
    two renders of the same record set are byte-identical.  Author-held
    submissions are marked as maintainer rows in the submitter column —
    the table does not launder who submitted what.
    """
    import html

    def escape(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def short(run_id: str) -> str:
        return f"{run_id[:8]}…" if len(run_id) > 8 else run_id

    ordered = sorted(
        records,
        key=lambda pair: (pair[0].get("submitted", ""), submission_id(pair[0])),
    )
    if not ordered:
        return (
            '      <p class="note">No operating-point submissions recorded yet. '
            "The door is open: submit through the comparison-submission issue "
            "template, and a reviewed record lands here on the next table render — "
            "published and rejected alike, nothing filtered.</p>\n"
        )
    from .. import observables

    units = {
        spec.observable_id: spec.unit for spec in (observables.lookup(oid) for oid in observables.registered())
    }
    lines = [
        '      <table class="board">',
        "        <thead>",
        "          <tr><th>Submitted</th><th>Submitter</th><th>Arms</th>"
        "<th>Workload</th><th>Results</th><th>Decision</th></tr>",
        "        </thead>",
        "        <tbody>",
    ]
    for submission, review in ordered:
        labels = [arm["label"] for arm in submission["arms"]]
        if len(labels) == 2:
            arms_text = (
                f"{escape(labels[0])} vs {escape(labels[1])}"
                f" (differs on: {escape(', '.join(submission['comparison']['differs_on']))}"
                f"{'&#8202;·&#8202;control' if submission['comparison']['control'] else ''})"
            )
        else:
            arms_text = escape(labels[0])
        workload = submission["workload"]
        workload_text = (
            f"{escape(workload['kind'])}, tp_size {escape(workload['parameters'].get('tp_size', '—'))}"
        )
        by_pair: dict[tuple[str, str], list[str]] = {}
        for row in sorted(
            submission["results"],
            key=lambda row: (row["observable"], row["metric"], row["arm"]),
        ):
            run_ids = ", ".join(short(run_id) for run_id in row["run_ids"])
            value = f"{escape(row['value'])} {escape(units.get(row['observable'], ''))}".strip()
            by_pair.setdefault((row["observable"], row["metric"]), []).append(
                f"{value} <code>{escape(run_ids)}</code>"
            )
        result_lines = [
            f"{escape(observable)}/{escape(metric)}: " + " / ".join(values)
            for (observable, metric), values in sorted(by_pair.items())
        ]
        results_text = "<br>".join(result_lines)
        submitter = submission["submitter"]
        if submitter.lstrip("@").lower() in AUTHOR_IDENTITIES:
            submitter += " (maintainer)"
        decision = review["decision"] if review else "pending"
        decision_class = "label label-verified" if decision == "published" else "label label-proposed"
        lines.append(
            "          <tr>"
            f"<td>{escape(submission['submitted'])}</td>"
            f"<td>{escape(submitter)}</td>"
            f"<td>{arms_text}</td>"
            f"<td>{escape(workload_text)}</td>"
            f"<td>{results_text}</td>"
            f'<td><span class="{decision_class}">{escape(decision)}</span></td>'
            "</tr>"
        )
    lines.append("        </tbody>")
    lines.append("      </table>")
    return "\n".join(lines) + "\n"


def _cli(argv: list[str] | None = None) -> int:
    """CLI: validate submission file(s) at the door, or against the store.

    Usage (repo root)::

        python -m essun.evidence.submissions FILE... [--verify]
        python -m essun.evidence.submissions --community [repo-root]

    Default (door mode): structure + fairness + tree gates; a file with a
    review block is refused (the maintainer path uses --community).
    ``--verify`` adds the store gates (every cited run id must be rebuilt
    locally and match the submitted numbers exactly).
    ``--community`` validates the committed records (review required) and
    prints the rendered table state without touching the site.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="comparison-submission door (v0)")
    parser.add_argument("paths", nargs="*", help="submission YAML file(s)")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="also run the store gates (cited run ids must exist locally and match)",
    )
    parser.add_argument(
        "--community",
        action="store_true",
        help="validate experiments/community/*.yaml (review required) instead of files",
    )
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    args = parser.parse_args(argv)

    root = Path(args.repo_root)
    failures = 0

    def check(path: Path, at_door: bool) -> None:
        nonlocal failures
        try:
            submission, review = load_submission_file(
                path, at_door=at_door, repo_root=root
            )
        except SubmissionError as error:
            print(f"INVALID {path.name}: {error}", file=sys.stderr)
            failures += 1
            return
        note = "door-pass" if at_door else f"review={review['decision']}"
        if args.verify:
            from .store import EvidenceStore

            problems = verify_against_store(submission, EvidenceStore(root / "results"), root)
            if problems:
                print(f"INVALID {path.name}: " + "; ".join(problems), file=sys.stderr)
                failures += 1
                return
            note += " store-verified"
        print(f"OK {path.name} [{note}] id={submission_id(submission)[:12]}…")

    if args.community:
        records_dir = root / "experiments" / "community"
        paths = sorted(records_dir.glob("*.yaml")) if records_dir.is_dir() else []
        for path in paths:
            check(path, at_door=False)
        if not paths:
            print("community: no committed records yet (the directory waits empty)")
    else:
        if not args.paths:
            parser.error("provide at least one submission file, or --community")
        for raw in args.paths:
            check(Path(raw), at_door=True)
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shell
    raise SystemExit(_cli())
