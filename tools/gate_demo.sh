#!/usr/bin/env bash
# gate_demo.sh — `make gate-demo`: the one-command public-gate story.
#
# Chains the existing, documented legs of the public-release gate
# end-to-end from any tree, including a cold `git archive HEAD`
# checkout with an empty git-ignored results/ store. Every step is
# summarized inline; the FIRST failure stops the run with the failing
# step's output tail. Full per-step logs live in a scratch directory that
# is removed on exit (nothing outside the repo's documented outputs is
# kept; scratch trees are the caller's to clean).
#
#   1. bootstrap     `make bootstrap`, ONLY when .venv is missing
#   2. schemas       `make validate-schemas` (draft schemas + examples)
#   3. suite         `make test` (golden/negative/determinism/observables/
#                    evidence/backends/anchor-integrity tests)
#   4. run (L0)      W1 smoke manifest on the analytical L0 backend; the
#                    run_id MUST equal the golden pinned in
#                    experiments/vertical_slice/w1_decode_smoke.GOLDEN.md
#   5. run (DES)     the ASTRA-sim twin manifest on the pinned container
#                    backend; the run_id MUST equal the id that
#                    tools/make_figure.py pins as its default source (this
#                    record is what the figure leg needs; without this step
#                    a cold tree has no DES record to plot)
#   6. sweep         `make sweep` on the AllReduce design-space grid
#                    (experiments/sweeps/l0_allreduce_design_space_v1.yaml;
#                    override with SWEEP_MANIFEST=... — the cross-design
#                    grid had not landed when this script was written, and
#                    the script reports what it finds under
#                    experiments/sweeps/)
#   7. figure        tools/make_figure.py — renders the provenance-linked
#                    O-CCT figure from the two run records and registers it
#                    in the append-only figures index (idempotent)
#   8. paper-check   `make paper-check` over paper/, plus the same
#                    placeholder-discipline rules applied to the README's
#                    "Public gate status" section
#
# (A former leg 8, `make verify-handoff`, was removed 2026-10-28
#  together with the internal material it checked.)
#
# Step five needs the pinned Docker image essun/astra-sim-analytical:s1
# (id sha256:bb02b612…, verified by the adapter, which refuses unpinned
# images); if it is absent, build it per backends/docker/astra-sim-runbook.md
# and rerun. Stdlib + the repo's own tools only; no network after bootstrap.
#
# No-Docker mode (release-readiness A1, 2026-10-28): when the docker CLI is
# absent or the daemon is unreachable, the two Docker-dependent legs — the
# DES run (leg 5) and the figure registration that renders from that run's
# record (leg 7) — are SKIPPED, not failed, with the requirement printed
# (what to install/build to get the full gate). Every other leg runs
# unchanged and the script still exits 0: the L0-only legs are the same
# chain CI runs. Docker PRESENT but the pinned image missing/mismatched
# stays a hard leg-5 failure by design — the error names the exact fix
# (rebuild per the runbook), so hiding it as a skip would lose information.

set -u -o pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

L0_MANIFEST=experiments/vertical_slice/w1_decode_smoke.yaml
ASTRA_MANIFEST=experiments/vertical_slice/w1_decode_smoke_astra.yaml
SWEEP_MANIFEST=${SWEEP_MANIFEST:-experiments/sweeps/l0_allreduce_design_space_v1.yaml}
GOLDEN_DOC=experiments/vertical_slice/w1_decode_smoke.GOLDEN.md
PY=.venv/bin/python
TAILN=40

# Expected ids are read from their single sources of truth, never duplicated
# here: the L0 golden from the GOLDEN doc, the ASTRA twin from the figure
# tool's pinned default.
GOLDEN_L0=$(sed -n 's/^Golden run_id: `\([0-9a-f]\{64\}\)`$/\1/p' "$GOLDEN_DOC")
GOLDEN_ASTRA=$(sed -n 's/^DEFAULT_ASTRA_RUN = "\([0-9a-f]\{64\}\)"$/\1/p' tools/make_figure.py)

step=0
LOGFILE=""
LOGDIR=$(mktemp -d "${TMPDIR:-/tmp}/demo-logs.XXXXXX")
trap 'rm -rf "$LOGDIR"' EXIT

if [ -x "$PY" ]; then
  BOOTSTRAP_NEEDED=0
else
  BOOTSTRAP_NEEDED=1
fi
TOTAL=$((7 + BOOTSTRAP_NEEDED))

say() { printf 'demo: %s\n' "$*"; }

die_step() {
  say "FAIL — step ${step}/${TOTAL}: $1"
  if [ -n "$LOGFILE" ] && [ -f "$LOGFILE" ]; then
    echo "---- last ${TAILN} lines of $(basename "$LOGFILE") ----"
    tail -n "$TAILN" "$LOGFILE"
    echo "--------------------------------------------------------"
  fi
  exit 1
}

run_step() {
  step=$((step + 1))
  label=$1
  shift
  LOGFILE="$LOGDIR/$(printf '%02d' "$step")-$(printf '%s' "$label" | tr -c 'A-Za-z0-9._-' '_').log"
  say "[${step}/${TOTAL}] ${label}"
  if ! "$@" >"$LOGFILE" 2>&1; then
    die_step "${label} failed — command: $*"
  fi
}

run_id_from_log() {
  sed -n 's/.*"run_id": "\([0-9a-f]\{64\}\)".*/\1/p' "$1" | head -n 1
}

hex_id_from_log() {
  sed -n 's/.*"'"$2"'": "\([0-9a-f]\{64\}\)".*/\1/p' "$1" | head -n 1
}

pytest_summary() {
  grep -E '[0-9]+ (passed|failed|error|skipped)' "$LOGFILE" | tail -n 1
}

say "repo root: ${REPO_ROOT}"
if command -v git > /dev/null 2>&1 && git rev-parse -q --verify HEAD > /dev/null 2>&1; then
  say "HEAD: $(git rev-parse HEAD)"
else
  say "HEAD: (no git metadata — exported tree)"
fi
[ -n "$GOLDEN_L0" ] || { say "FAIL — cannot read the L0 golden id from ${GOLDEN_DOC}"; exit 1; }
[ -n "$GOLDEN_ASTRA" ] || { say "FAIL — cannot read the ASTRA twin id from tools/make_figure.py (DEFAULT_ASTRA_RUN)"; exit 1; }

# --- Docker precheck (A1): pick full vs no-Docker mode up front ---------------

# Only the DES run and the figure that consumes its record need Docker; the
# requirement text below must stay the single place a stranger reads what
# the skipped legs need. `docker info` (not `docker version`) is the probe:
# it fails exactly when the daemon is unreachable.
DOCKER_MODE="full"
DOCKER_REASON=""
if ! command -v docker > /dev/null 2>&1; then
  DOCKER_MODE="none"
  DOCKER_REASON="docker CLI not found on PATH"
elif ! docker info > /dev/null 2>&1; then
  DOCKER_MODE="none"
  DOCKER_REASON="docker daemon unreachable (docker info failed)"
fi
if [ "$DOCKER_MODE" = "none" ]; then
  say "docker: ${DOCKER_REASON} — no-Docker mode: the DES-run and figure legs will be skipped below (requirement printed at the end); all other legs run unchanged"
fi

# --- 1. bootstrap (only if needed) -------------------------------------------

if [ "$BOOTSTRAP_NEEDED" = "1" ]; then
  run_step "bootstrap (venv missing)" make bootstrap
  say "    -> $(tail -n 1 "$LOGFILE")"
else
  say "[skip] bootstrap — .venv present"
fi

# --- 2. schemas ---------------------------------------------------------------

run_step "validate-schemas" make validate-schemas
say "    -> $(pytest_summary)"

# --- 3. suite -----------------------------------------------------------------

run_step "test suite" make test
say "    -> $(pytest_summary)"

# --- 4. W1 smoke run on L0 + golden check --------------------------------------

run_step "run W1 smoke (analytical L0)" make "run" "EXP=${L0_MANIFEST}"
RUN_L0=$(run_id_from_log "$LOGFILE")
[ -n "$RUN_L0" ] || die_step "no run_id in the L0 run output"
say "    -> run_id ${RUN_L0}"
if [ "$RUN_L0" != "$GOLDEN_L0" ]; then
  die_step "L0 golden mismatch: got ${RUN_L0}, expected ${GOLDEN_L0} (from ${GOLDEN_DOC}) — a rerun that changes this id without a manifest or code change is a bug (see ${GOLDEN_DOC})"
fi
say "    -> golden check OK (equals ${GOLDEN_DOC})"

# --- 5. W1 smoke run on the pinned ASTRA-sim DES backend -----------------------

SKIPPED_LEGS=0
if [ "$DOCKER_MODE" = "none" ]; then
  SKIPPED_LEGS=$((SKIPPED_LEGS + 1))
  say "[skip] run W1 smoke (ASTRA-sim analytical, pinned container) — ${DOCKER_REASON}; this is one of the two legs no-Docker mode skips (requirement printed at the end)"
else
  run_step "run W1 smoke (ASTRA-sim analytical, pinned container)" make "run" "EXP=${ASTRA_MANIFEST}"
  RUN_ASTRA=$(run_id_from_log "$LOGFILE")
  [ -n "$RUN_ASTRA" ] || die_step "no run_id in the ASTRA run output"
  say "    -> run_id ${RUN_ASTRA}"
  if [ "$RUN_ASTRA" != "$GOLDEN_ASTRA" ]; then
    die_step "ASTRA twin mismatch: got ${RUN_ASTRA}, expected ${GOLDEN_ASTRA} (the id tools/make_figure.py pins as its default source) — a rerun that changes this id without a manifest or code change is a bug"
  fi
  say "    -> twin check OK (equals the figure tool's pinned default source run)"
fi

# --- 6. sweep -------------------------------------------------------------------

if ls experiments/sweeps/ 2>/dev/null | grep -iv '^l0_allreduce_design_space_v1\.yaml$' | grep -qi 'cross'; then
  say "[note] additional sweep grid(s) matching 'cross' exist under experiments/sweeps/ — this run still uses SWEEP_MANIFEST=${SWEEP_MANIFEST} (set SWEEP_MANIFEST explicitly to switch grids)"
else
  say "[note] no cross-design sweep grid under experiments/sweeps/ at this tree — running the design-space grid (the cross-design grid is a separate program leg, not landed when this script was written)"
fi
run_step "sweep ${SWEEP_MANIFEST}" make "sweep" "EXP=${SWEEP_MANIFEST}"
SWEEP_ID=$(hex_id_from_log "$LOGFILE" sweep_id)
say "    -> sweep_id ${SWEEP_ID:-?} (table.md + table.json under results/sweeps/)"

# --- 7. figure ------------------------------------------------------------------

if [ "$DOCKER_MODE" = "none" ]; then
  SKIPPED_LEGS=$((SKIPPED_LEGS + 1))
  say "[skip] figure registration (tools/make_figure.py) — its pinned ASTRA source run ${GOLDEN_ASTRA} is produced by the skipped DES leg, so a no-Docker tree has no record to render from (the committed paper/figures/ artifacts are unaffected)"
else
  run_step "figure registration (tools/make_figure.py)" "$PY" tools/make_figure.py
  FIGURE_ID=$(hex_id_from_log "$LOGFILE" figure_id)
  [ -n "$FIGURE_ID" ] || die_step "no figure_id in the make_figure.py output"
  say "    -> figure_id ${FIGURE_ID}"
fi
[ -f paper/figures/w1_smoke_occt_l0_vs_astra.svg ] || die_step "figure SVG missing after make_figure.py"

# --- 8. paper-check discipline (paper/ + docs) ------------------------------

run_step "paper-check (paper/)" make paper-check
say "    -> $(grep 'paper-check:' "$LOGFILE" | tail -n 1)"


# --- done -------------------------------------------------------------------------

if [ "$DOCKER_MODE" = "none" ]; then
  say "PASS (no-Docker mode) — ${step} of ${TOTAL} steps green, ${SKIPPED_LEGS} leg(s) skipped."
  say "skipped: (1) the W1 smoke DES run on the pinned ASTRA-sim analytical container and"
  say "(2) the figure registration that renders from that run's record — both need Docker."
  say "requirement: install Docker (any recent Engine with bind-mount support; verified"
  say "with Docker CLI 29.8.2 / OrbStack on macOS arm64), then build the pinned image"
  say "essun/astra-sim-analytical:s1 (~1.3 GB, local-only, never pushed) per"
  say "backends/docker/astra-sim-runbook.md, then rerun 'make gate-demo' for the full"
  say "gate. See the 'Requirements' section of README.md for versions, sizes and"
  say "measured first-run times."
  say "gate artifacts: L0 run ${RUN_L0}; sweep ${SWEEP_ID}; (DES run + figure legs skipped — no Docker)"
  say "figures index and run records regenerate under the git-ignored results/ store."
  exit 0
fi

say "PASS — all ${TOTAL} steps green."
say "gate artifacts: L0 run ${RUN_L0}; ASTRA run ${RUN_ASTRA}; sweep ${SWEEP_ID};"
say "figure ${FIGURE_ID} (paper/figures/w1_smoke_occt_l0_vs_astra.svg + paper/figures/README.md);"
say "figures index and run records regenerate under the git-ignored results/ store."
