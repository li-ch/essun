"""T023 consolidation: the csg-htsim path stays wired as DOCUMENTED, not
as a backend.

The csg path (packet-level ASTRA-sim + Broadcom csg-htsim, D-028) is the
one member of the current DES-path set with deliberately ZERO adapter code
(runbook header: "analysis only — this program writes no adapter code").
Its golden/negative/determinism obligations therefore cannot attach to an
executor; they attach to the documented state this repo pins. These tests
guard exactly that state:

1. NON-REGISTRATION (the negative obligation): no backend id containing
   "csg" is registered in the orchestrator and no csg adapter module
   exists — the packet path cannot be silently routed; the only route is
   the documented manual container command.
2. DOCUMENTED ARTIFACTS exist: runbook, pinned license copy, Dockerfile,
   and the S1/S2/S3 + D-032/4a execution logs are in-tree.
3. PINNED IDENTITIES stay pinned (golden-by-citation): the runbook's
   version table keeps the executed image/binary/submodule/lib sha256
   pins. Drift requires a deliberate runbook edit plus a deliberate test
   edit — never a silent change.
4. DETERMINISM STATUS stays stated (hard rule 6 material, the finding the
   2026-10-27 registry audit called out): unpatched ':s1' is NOT
   run-to-run reproducible (time-seeded RNG, srand(time(NULL)) at
   HTSimProtoTcp.cc:102); patched ':s1-seeded' (D-032/4a) IS
   run-reproducible per seed.
5. The registered ASTRA face stays the ANALYTICAL image, not the csg
   packet image (lineage separation the pins doc records).
6. The independence inventory (docs/backend-independence.md, Q3 S3
   deliverable) keeps the csg row: three DES paths incl. csg packet.

This module deliberately tests NO csg behavior: with no adapter, a
behavior "test" here would be theater. Everything asserted is a fact of
committed documents, each string verified against the current files.
"""

from pathlib import Path

import pytest

from essun.orchestrator import runs as orch

REPO = Path(__file__).resolve().parents[2]
RUNBOOK = REPO / "backends" / "docker" / "astra-csg-runbook.md"
INDEPENDENCE = REPO / "docs" / "backend-independence.md"
_INDEPENDENCE_PRESENT = INDEPENDENCE.is_file()

# Pinned identities as spelled in the runbook §1 table (S2-executed image)
# and §6.1 (seeded variant, D-032/4a). Full hashes where the runbook spells
# full hashes; the seeded image id appears there truncated, so the stable
# full-prefix "6cc48e30efa8" is pinned instead.
CSG_IMAGE = "essun/astra-csg-htsim:s1"
CSG_IMAGE_ID = "sha256:e18b4fd1061c924b354b455eea2e7108ca4cf7a752e2471a322ffb8e8e2e2900"
CSG_BINARY_SHA256 = "fe36ee2aae16e7bf43c074f80fa2c7064653b751d9e3178b2075ee0ef5404216"
CSG_HTSIM_SUBMODULE = "67cbbbb1cccdbddc400803414127d044ecd55290"
CSG_PATCHED_LIB_SHA256 = "f9271372054e61dfee4e65caef2865ebd8bd1feb6fc823d0170a8871a5bee877"
CSG_SEEDED_IMAGE_ID_PREFIX = "6cc48e30efa8"


def test_csg_backend_not_silently_registered():
    # The negative obligation: the csg packet path has NO adapter, so it
    # must not appear in the orchestrator registries under any name.
    assert not any("csg" in backend_id for backend_id in orch.BACKENDS)
    assert not any("csg" in backend_id for backend_id in orch.DISPATCH)
    # And no adapter module exists to import by accident.
    backends_pkg = REPO / "src" / "essun" / "backends"
    modules = [p.name for p in backends_pkg.iterdir() if p.is_dir()]
    assert not any("csg" in name for name in modules)


def test_documented_csg_artifacts_exist():
    # The path's provenance is in-tree, not memory: runbook, license pin,
    # Dockerfiles, and the S1 (build) / S2 (execute) / S3 (re-verify) /
    # D-032-4a (seeded determinism) logs.
    for rel in (
        "backends/docker/astra-csg-runbook.md",
        "backends/pins/csg-htsim.LICENSE",
        "backends/docker/astra-csg-htsim.Dockerfile",
        "backends/docker/astra_csg_s1.log",
        "backends/docker/astra_csg_s2.log",
        "backends/docker/astra_csg_s3.log",
        "backends/docker/astra_csg_d032_smoke.log",
    ):
        assert (REPO / rel).is_file(), f"missing documented csg artifact {rel}"


def test_runbook_pins_the_executed_identities():
    text = RUNBOOK.read_text(encoding="utf-8")
    # §1 version/identity table: image, image id, binary, submodule, lib.
    assert CSG_IMAGE in text
    assert CSG_IMAGE_ID in text
    assert CSG_BINARY_SHA256 in text
    assert CSG_HTSIM_SUBMODULE in text
    assert CSG_PATCHED_LIB_SHA256 in text
    # License lineage: the BSD-2-Clause pin whose copy is committed at
    # backends/pins/csg-htsim.LICENSE (runbook §1 cites its sha prefix).
    assert "c550c0ba" in text


def test_runbook_states_the_determinism_finding():
    # Hard rule 6 material: the unpatched binary seeds its RNG from
    # wall-clock time, so run records from it are NOT reproducible; the
    # seeded image (one env-seeded srand line, D-032/4a) restores
    # per-seed reproducibility. Both halves must stay stated.
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "NOT run-to-run reproducible" in text
    assert "time-seeded RNG" in text
    assert "srand(time(NULL))" in text
    assert "HTSimProtoTcp.cc:102" in text
    assert "s1-seeded" in text
    assert "IS run-reproducible per seed" in text
    assert "ESSUN_SEED" in text
    assert CSG_SEEDED_IMAGE_ID_PREFIX in text


def test_registered_astra_face_is_not_the_csg_image():
    # Lineage separation: the orchestrator's astra_sim_analytical pins the
    # ANALYTICAL image (D-027); the csg packet image stays unregistered.
    # A quiet swap of the registered face to the packet image would change
    # the backend's identity (and its declared capabilities) silently.
    from essun.backends.astra_sim import adapter

    assert adapter.PIN["docker_image"] == "essun/astra-sim-analytical:s1"
    assert adapter.PIN["docker_image_id"].startswith("sha256:bb02b612")
    assert adapter.PIN["docker_image_id"] != CSG_IMAGE_ID


@pytest.mark.skipif(
    not _INDEPENDENCE_PRESENT,
    reason=(
        "docs/backend-independence.md is a design document kept out of this tree; "
        "the inventory check runs where the doc is present"
    ),
)
def test_independence_inventory_keeps_the_csg_row():
    # docs/backend-independence.md (Q3 S3) is the deliverable that binds
    # the csg path into the CURRENT backend set's comparison story: the
    # three DES paths, the csg image (+ seeded variant) and its submodule
    # pin, with the runbook as its execution provenance.
    text = INDEPENDENCE.read_text(encoding="utf-8")
    assert "csg packet" in text
    assert CSG_IMAGE in text
    assert "s1-seeded" in text
    # The doc's table truncates ids harder than the runbook (8 hex chars).
    assert CSG_SEEDED_IMAGE_ID_PREFIX[:8] in text
    assert CSG_HTSIM_SUBMODULE[:8] in text  # truncated pin in the table
    assert "astra-csg-runbook" in text
