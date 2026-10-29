# Release-readiness B12 (2026-10-28): `help` is the default goal, so a bare
# `make` prints the target list instead of silently launching the full
# demo chain (the previous first-target default). Every target carries
# a trailing `## description` that the help target renders — keep new
# targets described or they will not be listed.
.DEFAULT_GOAL := help

PY := .venv/bin/python

.PHONY: help demo ci-local bootstrap validate-schemas test run sweep paper-check disposition-report clean

help: ## Print this target list (the default goal — a bare `make` shows this)
	@echo "essun — Makefile targets (default goal: help; this list is live: make help)"
	@echo
	@awk 'BEGIN { FS = ":" } /^[a-zA-Z0-9_.-]+:.*##/ { split($$0, a, "## "); printf "  %-18s %s\n", $$1, a[2] }' $(MAKEFILE_LIST)

# One-command public-gate story (G7 / decision D-026): bootstrap-if-needed ->
# validate-schemas -> test -> W1 smoke runs (L0 golden + pinned ASTRA-sim
# twin) -> design-space sweep -> figure registration -> paper-check (incl.
# the README honesty section). Any failing leg stops the run
# with that step's output tail; see tools/gate_demo.sh. Without Docker the
# DES-run and figure legs are skipped with the requirement printed
# (no-Docker mode, release-readiness A1) and the L0-only legs still gate.
# (The former verify-handoff leg left HEAD in D-035 stage S3, 2026-10-28.)
demo: ## Full public-gate story end-to-end (tools/gate_demo.sh); no-Docker mode skips the two Docker legs
	bash tools/gate_demo.sh

# Runs the exact sequence of .github/workflows/ci.yml so the workflow is
# testable locally before any remote exists (HUM-01 / D-026).
ci-local: bootstrap validate-schemas test paper-check ## Run the exact .github/workflows/ci.yml sequence locally

bootstrap: ## Create .venv and install the package + dev extras (pip install -e ".[dev]")
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

validate-schemas: ## Run only the draft-schema and example tests (tests/schema)
	$(PY) -m pytest tests/schema -q

test: ## Run the full pytest suite (schema, golden, negative, determinism, observables, evidence, backends)
	$(PY) -m pytest -q

run: ## Run one experiment manifest — make run EXP=path/to/manifest.yaml
	$(PY) -m essun.orchestrator.runs $(EXP)

sweep: ## Run one sweep manifest — make sweep EXP=path/to/sweep.yaml
	$(PY) -m essun.orchestrator.sweeps $(EXP)

paper-check: ## Paper placeholder/claim-word discipline check (tools/paper_check.py)
	$(PY) tools/paper_check.py

# Design doc D1 gate (2026-10-29): a coverage report (per-disposition
# counts) ships with every profile. Counts are computed live from
# src/essun/specir; unsupported is printed plainly (honesty over coverage).
disposition-report: ## Print the per-profile D1 disposition coverage report (tools/disposition_coverage.py)
	$(PY) tools/disposition_coverage.py

# Release-readiness B12 (2026-10-28): clean removes ONLY regenerable Python
# build/test caches. FENCED — deliberately never removed by clean:
#   results/   the append-only evidence store: immutable run records; the
#              evidence rules forbid deleting or pruning runs
#   .venv/     bootstrap-owned (make bootstrap recreates it); deleting a
#              live one breaks any demo/CI leg in flight
#   backends/  pinned upstream checkouts and their build trees — pin-
#              recorded and expensive to rebuild, not caches
#   artifacts/, .cache/  generated outputs and license-reviewed standard
#              source material — not project build products
clean: ## Remove regenerable Python build/test caches; NEVER touches results/, .venv/, backends/, .cache/
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist
	rm -f .coverage .coverage.* coverage.json
	rm -rf *.egg-info src/*.egg-info
	find src tests tools experiments -type d -name '__pycache__' -prune -exec rm -rf {} +
	find src tests tools experiments -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	@echo "clean: removed regenerable Python caches; results/ untouched (fenced evidence store)"

coverage:
	$(PY) -m pip install --quiet pytest-cov
	$(PY) -m pytest --cov=essun --cov-report=term-missing -q 2>&1 | tail -30
