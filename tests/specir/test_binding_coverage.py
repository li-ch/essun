"""Soak seed 1 (2026-10-30): the binding-coverage property.

PROGRAM.md soak section (docs/away/2026-10-30-program/PROGRAM.md): the
property suite continues, "now including binding-coverage properties
(every ``simulated_behavior`` disposition must have a binding and a
golden — a testable invariant)".  This module pins that invariant
directly against the LIVE registries — not through the promotion table
of tests/specir/test_dispositions.py — so a violation is reported with
the offending requirement ids verbatim.

The property has three legs, all deterministic and fast (live imports
plus ``ast``; no subprocess, no network, no fixtures):

1. FORWARD (disposition -> binding): every requirement object of the
   five UEC stage modules whose disposition is ``simulated_behavior``
   is covered by at least one live binding claiming the same
   disposition.
2. EXACTNESS (no shadow bindings): the set of ``simulated_behavior``
   requirement ids equals the set of requirement ids covered by
   ``simulated_behavior`` bindings — a binding may not claim the
   disposition for a requirement that does not carry it.
3. GOLDEN (binding -> golden): every binding that executes a
   ``simulated_behavior`` requirement names a golden test that
   (a) is a repo-relative path under ``tests/`` (so the suite collects
   it — pyproject ``testpaths = ["tests"]``), (b) defines at least one
   top-level ``test_`` function, and (c) cites the binding id or the
   requirement id, keeping the causal chain requirement -> binding ->
   golden greppable.

If leg 1 or 2 fails, the offending ids ARE the finding: record them
(they feed the G2 credit-window ladder) — do not flip dispositions,
goldens, or this module to silence the property.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import pathlib

import pytest

from essun.specir import bindings
from essun.specir.uec_link_transport import UECRequirement

#: Repo root (tests/specir/<this file> -> parents[2] = essun checkout).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


# -- the property, as data -----------------------------------------------------


def simulated_behavior_requirements() -> list[tuple[str, UECRequirement]]:
    """(stage module, requirement) for every live ``simulated_behavior``.

    Walks the same five stage modules as the binding registry
    (:data:`bindings.UEC_REQUIREMENT_MODULES`) and reads the live
    ``requirements()`` tuples, so a tampered or drifted module is seen
    here exactly as the binding gate would see it.
    """
    live: list[tuple[str, UECRequirement]] = []
    for dotted in bindings.UEC_REQUIREMENT_MODULES:
        module = importlib.import_module(dotted)
        for req in module.requirements():  # type: ignore[attr-defined]
            if req.disposition == "simulated_behavior":
                live.append((dotted, req))
    return live


def simulated_behavior_binding_index() -> dict[str, list[str]]:
    """requirement_id -> [binding_id, ...] for every binding claiming
    ``simulated_behavior``."""
    covered: dict[str, list[str]] = {}
    for binding in bindings.BINDINGS:
        if binding.disposition == "simulated_behavior":
            covered.setdefault(binding.requirement_id, []).append(
                binding.binding_id
            )
    return covered


def golden_problems(
    binding: bindings.RequirementBinding,
) -> list[str]:
    """The golden leg of the property; [] = the golden is real.

    A golden that exists but collects nothing, or lives outside the
    suite, or never names the binding/requirement it executes, is not a
    golden — the binding-coverage property fails on it.
    """
    problems: list[str] = []
    path = pathlib.PurePosixPath(binding.golden_test)
    if path.is_absolute() or not path.parts or path.parts[0] != "tests":
        problems.append(
            f"{binding.binding_id}: golden {binding.golden_test!r} is not a "
            "repo-relative path under tests/ (the suite would never "
            "collect it)"
        )
    file = REPO_ROOT / path
    if not file.is_file():
        problems.append(
            f"{binding.binding_id}: golden test {binding.golden_test} does "
            "not exist"
        )
        return problems
    source = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        problems.append(
            f"{binding.binding_id}: golden {binding.golden_test} is not "
            "parseable Python — no test function can collect it"
        )
    else:
        test_functions = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        if not test_functions:
            problems.append(
                f"{binding.binding_id}: golden {binding.golden_test} defines "
                "no top-level test function"
            )
    if (
        binding.binding_id not in source
        and binding.requirement_id not in source
    ):
        problems.append(
            f"{binding.binding_id}: golden {binding.golden_test} never cites "
            f"the binding id or requirement {binding.requirement_id} — the "
            "requirement -> binding -> golden chain is not traceable"
        )
    return problems


# -- the property, pinned ------------------------------------------------------


def conformance_test_requirements() -> list[tuple[str, UECRequirement]]:
    """(stage module, requirement) for every live ``conformance_test``.

    G2 credit-family ladder S4 (2026-10-30) added the second executed
    carrier: a ``conformance_test`` requirement is exercised by an
    executable CHECK of the built profile, not by a binding — this is
    the leg the property extends to below.
    """
    live: list[tuple[str, UECRequirement]] = []
    for dotted in bindings.UEC_REQUIREMENT_MODULES:
        module = importlib.import_module(dotted)
        for req in module.requirements():  # type: ignore[attr-defined]
            if req.disposition == "conformance_test":
                live.append((dotted, req))
    return live


def _built_profile_checks() -> list[tuple[str, tuple[str, ...], str]]:
    """(check_id, requirement_ids, location) for every built-profile check."""
    import yaml

    from essun.specir.profile_format import PROFILE_FORMAT_NAME

    raw = yaml.safe_load(
        (REPO_ROOT / "experiments/uec/semantic_profile.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert raw["format"]["name"] == PROFILE_FORMAT_NAME
    return [
        (c["check_id"], tuple(c["requirement_ids"]), c.get("location", ""))
        for c in raw["checks"]
    ]


def test_every_conformance_test_disposition_has_a_check() -> None:
    # The conformance leg (G2 S4): disposition -> check. Every live
    # conformance_test requirement is referenced by at least one check
    # of the BUILT profile whose location is a real file under tests/
    # citing the requirement — the mirror of legs 1 and 3 for the check
    # carrier (the D2 rule: a binding may carry only simulated_behavior,
    # so conformance_test must be exercised some other way, visibly).
    checks = _built_profile_checks()
    referenced: dict[str, list[str]] = {}
    for check_id, requirement_ids, _ in checks:
        for rid in requirement_ids:
            referenced.setdefault(rid, []).append(check_id)
    problems: list[str] = []
    for module, req in conformance_test_requirements():
        carriers = referenced.get(req.requirement_id, [])
        if not carriers:
            problems.append(
                f"{req.requirement_id} (module {module}): conformance_test "
                "with no check in the built profile referencing it"
            )
            continue
        for check_id, requirement_ids, location in checks:
            if req.requirement_id not in requirement_ids:
                continue
            path = pathlib.PurePosixPath(location)
            file = REPO_ROOT / path
            if (
                path.is_absolute()
                or not path.parts
                or path.parts[0] != "tests"
                or not file.is_file()
                or req.requirement_id
                not in file.read_text(encoding="utf-8")
            ):
                problems.append(
                    f"{req.requirement_id}: check {check_id} names "
                    f"{location!r}, which is not a tests/ file citing the "
                    "requirement it executes"
                )
    assert problems == [], (
        "binding-coverage property violated — conformance_test leg "
        f"failures: {problems}"
    )


def test_every_simulated_behavior_disposition_has_a_binding() -> None:
    # LEG 1 (forward): disposition -> binding. The UEC profile scope is
    # the five stage modules of bindings.UEC_REQUIREMENT_MODULES; the
    # UnifiedBus paper profile has its own zero-executed record.
    covered = simulated_behavior_binding_index()
    unbound = sorted(
        f"{req.requirement_id} (module {module})"
        for module, req in simulated_behavior_requirements()
        if req.requirement_id not in covered
    )
    assert not unbound, (
        "binding-coverage property violated — simulated_behavior "
        "requirements without a binding: "
        f"{unbound}; these ids are the finding (record them; do not flip "
        "dispositions to silence this) — register a binding in "
        "essun.specir.bindings and the PROMOTED table in the same commit"
    )


def test_simulated_behavior_set_is_exactly_the_bound_set() -> None:
    # LEG 2 (exactness): no binding may claim simulated_behavior for a
    # requirement whose live disposition is not simulated_behavior (the
    # shadow-binding direction; the forward direction is leg 1).
    live = {req.requirement_id for _, req in simulated_behavior_requirements()}
    bound = set(simulated_behavior_binding_index())
    shadow = sorted(bound - live)
    assert not shadow, (
        "bindings claim simulated_behavior for requirements that do not "
        f"carry it: {shadow} — flip the requirement's disposition in its "
        "stage module (same commit, update EXPECTED_COUNTS) or fix the "
        "binding"
    )
    assert live == bound, (
        f"simulated_behavior ids {sorted(live)} != bound ids "
        f"{sorted(bound)} — the binding-coverage property is not exact"
    )


def test_each_simulated_behavior_binding_has_a_real_golden() -> None:
    # LEG 3 (golden): binding -> collected, executing, traceable golden.
    problems: list[str] = []
    for binding in bindings.BINDINGS:
        if binding.disposition != "simulated_behavior":
            continue  # the property is about simulated_behavior today
        problems.extend(golden_problems(binding))
    assert problems == [], (
        "binding-coverage property violated — golden leg failures: "
        f"{problems}"
    )


# -- negative: the property fires on tampering (no silent pass) -----------------


def test_property_fires_on_an_unbound_simulated_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A rogue requirement flips to simulated_behavior with no binding:
    # leg 1 must name it verbatim.
    stage = importlib.import_module(
        "essun.specir.uec_credits_flow_control"
    )
    flagship = next(
        req
        for req in stage.requirements()  # type: ignore[attr-defined]
        if req.requirement_id == "UEC11-FC-R02"
    )
    rogue = dataclasses.replace(
        flagship, requirement_id="UEC11-FC-R999"
    )
    monkeypatch.setattr(
        stage, "_REQUIREMENTS", stage._REQUIREMENTS + (rogue,)  # type: ignore[attr-defined]
    )
    covered = simulated_behavior_binding_index()
    unbound = [
        req.requirement_id
        for _, req in simulated_behavior_requirements()
        if req.requirement_id not in covered
    ]
    assert "UEC11-FC-R999" in unbound


def test_property_fires_on_a_shadow_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A rogue binding claims simulated_behavior for a requirement that
    # does not carry it: leg 2 must name it.
    flagship = bindings.BINDINGS[0]
    rogue = dataclasses.replace(
        flagship,
        binding_id="BIND-ROGUE-SHADOW",
        requirement_id="UEC11-FC-R66",  # stays unsupported in the modules
    )
    monkeypatch.setattr(
        bindings, "BINDINGS", bindings.BINDINGS + (rogue,)
    )
    live = {req.requirement_id for _, req in simulated_behavior_requirements()}
    bound = set(simulated_behavior_binding_index())
    assert "UEC11-FC-R66" in bound - live


def test_golden_leg_fires_on_each_tampered_golden() -> None:
    # One rogue per failure mode of golden_problems: a path outside the
    # suite, a missing file, and a real file under tests/ that is no
    # golden (a fixtures README — collects nothing, cites nothing).
    flagship = bindings.BINDINGS[0]
    outside = dataclasses.replace(
        flagship, golden_test="src/essun/backends/analytical/l0_tfc.py"
    )
    missing = dataclasses.replace(
        flagship, golden_test="tests/golden/test_never_created_golden.py"
    )
    not_a_golden = dataclasses.replace(
        flagship, golden_test="tests/fixtures/astra_sim/README.md"
    )
    assert any("not a repo-relative path under tests" in p for p in golden_problems(outside))
    assert any("does not exist" in p for p in golden_problems(missing))
    problems = golden_problems(not_a_golden)
    assert any("is not parseable Python" in p for p in problems)
    assert any("never cites the binding id" in p for p in problems)


# -- soak seed 2 (2026-10-30): the executed set, pinned at HEAD 62efe17 ------------
#
# The legs above prove the property CONSISTENTLY (every executed
# disposition is covered, nothing shadow, goldens real) for whatever
# the registries say today.  This section additionally pins the
# IDENTITY of the executed set at the seed-2 registry — 3
# simulated_behavior + 1 conformance_test after the G2 credit-family
# ladder (FC-R02 re-pointed at the automaton, FC-R08/FC-R09 via the
# L0-TFC bindings, FC-R05 via the built profile's checks) — so an
# identity drift (a disposition silently flipped, a requirement swapped
# in or out, a second binding stacked on an executed requirement)
# fails loudly instead of passing with a different-but-consistent set.
# If the registry moves LEGITIMATELY, move this snapshot in the SAME
# commit and say why in it; never flip a disposition to silence it.


SEED2_SIMULATED_BEHAVIOR = {"UEC11-FC-R02", "UEC11-FC-R08", "UEC11-FC-R09"}
SEED2_CONFORMANCE_TEST = {"UEC11-FC-R05"}
SEED2_BINDINGS = {
    "UEC11-FC-R02": (
        "BIND-UEC11-FC-R02-AUTOMATON",
        "tests/golden/test_credit_automaton_golden.py",
    ),
    "UEC11-FC-R08": (
        "BIND-UEC11-FC-R08-L0TFC",
        "tests/golden/test_l0_tfc_cell_golden.py",
    ),
    "UEC11-FC-R09": (
        "BIND-UEC11-FC-R09-L0TFC",
        "tests/golden/test_l0_tfc_pkt_golden.py",
    ),
}
#: The dedicated carrier checks for the one conformance_test
#: disposition (the built profile may cite the requirement from other
#: checks too — the flagship FC-R02 check UEC11-CHK-02 also names it —
#: so the pin is the floor, not the full referencing set).
SEED2_R05_CARRIER_CHECKS = {"UEC11-CHK-12", "UEC11-CHK-13", "UEC11-CHK-14"}


def test_executed_registry_matches_the_seed2_snapshot() -> None:
    # The re-check against the CURRENT registry: the live executed set
    # IS the seed-2 snapshot (3 simulated_behavior + 1 conformance_test,
    # these exact ids), each simulated_behavior carried by exactly ONE
    # binding naming exactly this golden, and the conformance_test
    # carried by its dedicated profile checks.
    live_sb = {req.requirement_id for _, req in simulated_behavior_requirements()}
    live_ct = {req.requirement_id for _, req in conformance_test_requirements()}
    assert live_sb == SEED2_SIMULATED_BEHAVIOR, (
        "the simulated_behavior set moved from the seed-2 snapshot "
        f"{sorted(SEED2_SIMULATED_BEHAVIOR)} to {sorted(live_sb)} — a "
        "disposition changed; if it is legitimate, move the snapshot in "
        "the same commit and justify it there (never flip a disposition "
        "to silence this)"
    )
    assert live_ct == SEED2_CONFORMANCE_TEST, (
        "the conformance_test set moved from the seed-2 snapshot "
        f"{sorted(SEED2_CONFORMANCE_TEST)} to {sorted(live_ct)} — a "
        "disposition changed; if it is legitimate, move the snapshot in "
        "the same commit and justify it there"
    )
    index = simulated_behavior_binding_index()
    by_id = {b.binding_id: b for b in bindings.BINDINGS}
    for requirement_id, (binding_id, golden) in SEED2_BINDINGS.items():
        assert index.get(requirement_id) == [binding_id], (
            f"{requirement_id} is not carried by exactly one binding "
            f"{binding_id}: {index.get(requirement_id)}"
        )
        assert by_id[binding_id].golden_test == golden
    checks = _built_profile_checks()
    referencing = {
        check_id
        for check_id, requirement_ids, _ in checks
        if "UEC11-FC-R05" in requirement_ids
    }
    assert SEED2_R05_CARRIER_CHECKS <= referencing, (
        f"the dedicated FC-R05 carrier checks {sorted(SEED2_R05_CARRIER_CHECKS)} "
        f"are not all present in the built profile (referencing: {sorted(referencing)})"
    )
