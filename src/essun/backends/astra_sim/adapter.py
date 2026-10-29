"""ASTRA-sim analytical adapter — translation, capabilities, execution.

BackendAdapter (IMPLEMENTATION_GUIDE §5) surface for the ASTRA-sim
**analytical congestion-unaware frontend** at the pinned commit
4ce9ecfe746a3ee5fe47559a11d91644d641fa7f (pin matrix: backends/pins/astra-sim.md;
Docker image essun/astra-sim-analytical:s1, image id sha256:bb02b612c0dc).

Stage S1 delivered ``capabilities()`` -> ``validate_experiment()`` ->
``compile_experiment()``. Stage S2 adds execution:
:func:`execute_experiment` compiles the manifest's input set, runs the
pinned binary in the container per ``backends/docker/astra-sim-runbook.md``
(bind-mounted run directory; image id and binary sha256 verified against
PIN), parses the result lines, and returns observations plus deterministic
execution provenance. The orchestrator (``orchestrator/runs.py``) persists
both through the evidence store, so one command runs the same manifest on
L0 or on this backend and yields a normal content-addressed RunRecord.

Two S2 counterexamples forced translation revisions (minimized and
classified, never tuned):

- ``endpoint-delay: 0`` aborts the pinned binary (EventQueue.cpp:33 asserts
  strictly increasing event times; a zero-delay callback chain schedules an
  event at the current time). Reproduced on the *upstream example config*
  itself, so it is a genuine backend constraint, not a translation bug.
  Revised to the pinned example's value 10 (A-AS2-DELAY-POS).
- A system config without ``local-mem-bw`` never completes any collective:
  ``PacketBundle::call`` divides by ``sys->local_mem_bw`` (default 0 when
  the key is absent, Sys.cc:167), the division-by-zero delay never fires,
  and every rank ends with "unreleased nodes" criticals while the process
  still exits 0. Revised to the pinned example's value 1600 (A-AS2-MEM-BW);
  ``boost-mode``/``roofline-enabled``/``peak-perf`` are proven inert at
  this pin (identical Wall time with and without) and stay omitted
  (A-AS2-INERT-KEYS).

What this backend models (mirrored from backends/pins/astra-sim.md, all
anchors inside the pinned tree):

- collective-level discrete-event simulation with the native Ring
  AllReduce algorithm over a single-dimension Ring logical topology;
- a congestion-UNAWARE analytical transport: per-message delay is
  ``hops * latency + chunk_size / bandwidth`` (congestion_unaware/
  basic-topology/BasicTopology.cpp at the pin) — no queueing, no contention
  between concurrent messages;
- Chakra ET workloads; analytical NO_MEMORY_EXPANSION remote memory.

What it loudly does NOT model (explicitly_unsupported below): congestion
and contention effects, credit-based flow control, packetization/FLIT
effects, UEC/UET transport semantics (the HTSim variant ASTRA-sim
integrates is Broadcom csg-htsim, NOT ultraethernet/uet-htsim), scale-up
memory semantics (UALink/CXL/UnifiedBus load-store), and any
standard-specific semantics. The analytical output carries no byte
accounting, so the O-CONSERVATION observable is explicitly unsupported
here — an honest per-backend gap, not a silent omission.

Free parameters flow from the experiment manifest (topology file's
``link.bytes_per_ns`` / ``link.hop_latency_ns``, workload file's byte
sizes). Nothing standard-derived is invented; every ASTRA-sim-side knob
with no manifest counterpart is recorded in TRANSLATION_ASSUMPTIONS with
its in-tree source anchor (provenance rule).
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from essun import contracts
from essun.backends.astra_sim import chakra_et
from essun.workload import w1

BACKEND_ID = "astra_sim_analytical"

# Provenance of everything this adapter targets (never a moving HEAD).
PIN = {
    "astra_sim_commit": "4ce9ecfe746a3ee5fe47559a11d91644d641fa7f",
    "chakra_commit": "0e3cd40c569f0a4cacb6d961bb56be53407abd2f",
    "astra_network_analytical_commit": "e8c5119f8d5a690b955e25c37a74359f23ac64cc",
    "docker_image": "essun/astra-sim-analytical:s1",
    "docker_image_id": "sha256:bb02b612c0dcd13eaa388a0ba05616b1c89e83468702a54f523f7742b02c9c8b",
    "binary_path_in_image": (
        "/opt/astra-sim/build/astra_analytical/build/bin/"
        "AstraSim_Analytical_Congestion_Unaware"
    ),
    "binary_sha256": (
        "ecc3a52d44c7134ce353ed03b8cb0076e5bfdbf2659bcdbb0cc5f2d760749ea4"
    ),
    "license": "MIT (backends/pins/astra-sim.LICENSE)",
    "capability_matrix": "backends/pins/astra-sim.md",
}

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "DES: collective-level event simulation on a congestion-unaware analytical transport",
    # Translated and (once S2 lands) executed by this adapter. The pinned
    # binary additionally supports AllGather/ReduceScatter/AllToAll with
    # Ring/HalvingDoubling/DoubleBinaryTree native algorithms and Chakra
    # compute phases (pins doc "Supported collectives") — declared here as
    # untranslated until a manifest needs them, never silently assumed.
    "collectives": ("allreduce_ring",),
    "topology_classes": ("unidirectional_ring",),
    "workload_kinds": ("w1_dense_tp_decode",),
    "transport_model": "congestion_unaware_analytical",
    # O-CCT only: parsed completion time. The analytical output has no byte
    # accounting, so O-CONSERVATION cannot be emitted honestly.
    "observables": ("O-CCT",),
    "explicitly_unsupported": (
        "congestion_contention_effects",
        "credit_flow_control",
        "packetization_flit_effects",
        "uec_uet_transport_semantics",
        "scale_up_memory_semantics",
        "standard_specific_semantics",
        "O-CONSERVATION",
    ),
}

# ASTRA-sim-side knobs with no manifest counterpart. Each is a free
# parameter or an upstream-example convention — none is standard-derived —
# and each carries its in-tree source anchor at the pin.
TRANSLATION_ASSUMPTIONS = (
    {
        "id": "A-AS1-BW-UNIT",
        "parameter": "network.bandwidth",
        "value": "manifest link.bytes_per_ns converted exactly to GB/s",
        "rationale": (
            "The analytical backend parses bandwidth in GB/s with 1 GB = "
            "2^30 B and converts to B/ns via bw * 2^30 / 1e9 "
            "(common/NetworkFunction.cpp at the pin). The adapter emits the "
            "exact finite decimal so the round trip is bit-exact: for B = 64 "
            "B/ns it writes 59.604644775390625 GB/s."
        ),
        "anchor": "extern/network_backend/analytical/common/NetworkFunction.cpp",
    },
    {
        "id": "A-AS2-DELAY-POS",
        "parameter": "system.endpoint-delay",
        "value": 10,
        "rationale": (
            "Supersedes A-AS1-DELAY-0 (stage S2 counterexample): the pinned "
            "congestion-unaware binary aborts with the EventQueue.cpp:33 "
            "assertion 'current_event_list.get_event_time() > current_time' "
            "when endpoint-delay is 0 — a zero-delay callback chain "
            "schedules an event at the current simulated time. Reproduced "
            "on the upstream Ring_reducescatter_4npus example itself with "
            "only this key changed, so it is a backend feasibility "
            "constraint, not a translation choice. The value 10 mirrors "
            "examples/system/native_collectives/Ring_4chunks.json; the "
            "per-message endpoint delay it introduces is a declared "
            "modeling-assumption difference vs the L0 model (which has no "
            "memory-side send delay) — classified in the S3 difference "
            "report, never tuned away."
        ),
        "anchor": (
            "extern/network_backend/analytical/common/event-queue/EventQueue."
            "cpp:33; astra-sim/system/Sys.cc:176,366; examples/system/"
            "native_collectives/Ring_4chunks.json"
        ),
    },
    {
        "id": "A-AS2-MEM-BW",
        "parameter": "system.local-mem-bw",
        "value": 1600,
        "rationale": (
            "Stage S2 counterexample: without this key Sys.cc:167 defaults "
            "local_mem_bw to 0 and PacketBundle::call divides by it "
            "(delay = 3 * size / local_mem_bw); the resulting broken event "
            "time means no collective ever completes — every rank reports "
            "'unreleased nodes' criticals while the process still exits 0. "
            "The value 1600 (GB/s) mirrors the pinned example config and is "
            "an upstream-example convention, NOT standard-derived. The "
            "memory-side processing delay it adds per packet is a declared "
            "modeling-assumption difference vs L0 — classified in S3, "
            "never tuned."
        ),
        "anchor": (
            "astra-sim/system/PacketBundle.cc:50-62; astra-sim/system/Sys."
            "cc:167,387-389; examples/system/native_collectives/"
            "Ring_4chunks.json"
        ),
    },
    {
        "id": "A-AS2-INERT-KEYS",
        "parameter": "system.{boost-mode,roofline-enabled,peak-perf}",
        "value": "omitted",
        "rationale": (
            "The pinned example also carries boost-mode: 0, "
            "roofline-enabled: 0 and peak-perf: 900. Measured inert at this "
            "pin for pure-collective workloads: the 4-rank probe run "
            "produced an identical Wall time (12736 ns) with and without "
            "them (roofline_enabled only gates Statistics paths, "
            "Statistics.cc:206,284 and Workload.cc:175,240; boost_mode has "
            "no consumer outside Sys.cc). They stay omitted so every "
            "written knob has a demonstrated effect."
        ),
        "anchor": (
            "astra-sim/workload/Statistics.cc:206,284; astra-sim/workload/"
            "Workload.cc:175,240"
        ),
    },
    {
        "id": "A-AS1-SPLITS",
        "parameter": "system.preferred-dataset-splits",
        "value": "ranks (8 for the W1 smoke)",
        "rationale": (
            "Mirrors the pinned example convention that pairs the split "
            "count with the rank count (Ring_4chunks.json declares "
            "preferred-dataset-splits: 4 for a 4-NPU ring)."
        ),
        "anchor": "examples/system/native_collectives/Ring_4chunks.json",
    },
    {
        "id": "A-AS1-CHUNKS-1",
        "parameter": "system.active-chunks-per-dimension",
        "value": 1,
        "rationale": "Value of the pinned Ring example config.",
        "anchor": "examples/system/native_collectives/Ring_4chunks.json",
    },
    {
        "id": "A-AS1-RING-IMPL",
        "parameter": "system.all-reduce-implementation",
        "value": ["ring"],
        "rationale": (
            "Native Ring algorithm on the Ring logical topology — the "
            "algorithm/topology pairing the L0 ring identity describes, per "
            "the pins doc vertical-slice fit."
        ),
        "anchor": "examples/system/native_collectives/Ring_4chunks.json",
    },
    {
        "id": "A-AS1-CHAIN",
        "parameter": "workload ET data_deps",
        "value": "sequential chain per rank, ops in generator order",
        "rationale": (
            "Chakra nodes without dependencies all issue at t=0 and would "
            "overlap (Workload::issue_dep_free_nodes at the pin); W1 decode "
            "steps are serialized in the L0 interpretation, so each rank's "
            "ops are chained via data_deps in the generator's fixed order "
            "(step-major, layer-minor) to keep the two backends' issue "
            "semantics comparable. This is a translation convention, not a "
            "standard-derived value."
        ),
        "anchor": "astra-sim/workload/Workload.cc:136 (issue_dep_free_nodes)",
    },
    {
        "id": "A-AS1-IDS",
        "parameter": "workload ET node ids",
        "value": "rank * ops_per_rank + op_index",
        "rationale": (
            "Extends the pinned generator's rank-major global id counter "
            "(all_reduce.py increments node_id once per NPU) to multiple ops "
            "per rank; ids stay globally unique and replayable."
        ),
        "anchor": (
            "examples/workload/microbenchmarks/generator_scripts/all_reduce.py"
        ),
    },
    {
        "id": "A-AS1-NO-EXPANSION",
        "parameter": "remote-memory-configuration",
        "value": {"memory-type": "NO_MEMORY_EXPANSION"},
        "rationale": (
            "The only remote-memory backend at the pin is analytical; the "
            "pinned congestion-unaware example uses no memory expansion."
        ),
        "anchor": "examples/remote_memory/analytical/no_memory_expansion.json",
    },
)


class AdapterError(Exception):
    """Raised when an experiment cannot be translated for this backend
    (capability or translation gap) — always names the gap."""


def _rel(path: Path) -> str:
    """Repo-relative path when possible (same convention as
    orchestrator/runs.py), so compiled plans are location-independent."""
    try:
        return str(Path(path).resolve().relative_to(contracts.REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


@dataclass(frozen=True)
class ValidatedExperiment:
    """Outputs of validate_experiment: everything compile needs."""

    manifest: dict
    manifest_path: Path
    manifest_sha256: str
    workload_config: w1.W1Config
    ops: tuple[w1.CollectiveOp, ...]
    topology_id: str
    ranks: int
    link_bytes_per_ns: Fraction
    hop_latency_ns: Fraction
    free_parameters: tuple[dict, ...]


def capabilities() -> dict:
    """CapabilitySet of this backend (IMPLEMENTATION_GUIDE §5)."""
    return dict(CAPABILITIES)


def _frac(value) -> Fraction:
    # str() first so YAML decimals are interpreted exactly (same policy as
    # the L0 backends).
    return Fraction(str(value))


def _finite_decimal(value: Fraction) -> str:
    """Exact finite decimal string for a fraction whose denominator is
    2^a * 5^b (true for B * 1e9 / 2^30 with integer B)."""
    with localcontext() as ctx:
        ctx.prec = 60
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def bandwidth_gb_per_s(bytes_per_ns: Fraction) -> tuple[str, Fraction]:
    """Convert manifest bandwidth (B/ns) to the network file's GB/s value.

    Inverse of the pinned ``bw_GBps_to_Bpns`` (bw * 2^30 / 1e9). Returns
    the exact decimal string to write and the exact Fraction it denotes;
    for B = 64 B/ns: 64 * 1e9 / 2^30 = 59.604644775390625 GB/s, and the
    backend's double conversion of that string is bit-exact back to 64.
    """
    gb_per_s = bytes_per_ns * 10**9 / (1 << 30)
    denominator = gb_per_s.denominator
    if denominator & (denominator - 1):  # not a power of two -> non-dyadic
        raise AdapterError(
            f"bandwidth {bytes_per_ns} B/ns has no exact finite GB/s decimal "
            "under the pinned 1 GB = 2^30 B convention (A-AS1-BW-UNIT); "
            "refusing to write an inexact value that would silently perturb "
            "the translation"
        )
    return _finite_decimal(gb_per_s), gb_per_s


def validate_experiment(manifest_path) -> ValidatedExperiment:
    """Load and gate the experiment manifest against this backend.

    Every rejection names the gap explicitly (BackendAdapter contract: an
    adapter must reject unsupported required semantics explicitly).
    """
    manifest_path = Path(manifest_path)
    manifest = contracts.load_experiment_manifest(manifest_path)
    inputs = contracts.resolve_inputs(manifest)

    if manifest["backends"] != [BACKEND_ID]:
        # The shared W1 smoke manifest names its executing backend; the
        # compiled ASTRA-sim view describes the same experiment, but an
        # adapter entry must be unambiguous.
        raise AdapterError(
            f"adapter {BACKEND_ID} requires backends == [{BACKEND_ID!r}], "
            f"got {manifest['backends']!r}"
        )

    missing = set(manifest["observables"]) - set(CAPABILITIES["observables"])
    if missing:
        unsupported = sorted(missing & set(CAPABILITIES["explicitly_unsupported"]))
        detail = ""
        if unsupported:
            detail = (
                f" — {unsupported}: the analytical congestion-unaware "
                "frontend emits no byte accounting, so conservation "
                "observables cannot be emitted honestly for this backend"
            )
        raise AdapterError(
            f"backend {BACKEND_ID} does not support observable(s) "
            f"{sorted(missing)}{detail}; capabilities: {CAPABILITIES}"
        )

    topology_data = contracts.load_yaml(inputs["infra_graph"]["path"])
    topology_class = topology_data.get("topology_class")
    if topology_class not in CAPABILITIES["topology_classes"]:
        raise AdapterError(
            f"backend {BACKEND_ID} has no ASTRA-sim analytical translation "
            f"declared for topology_class {topology_class!r} "
            f"({manifest['infra_graph']['path']}); declared classes: "
            f"{list(CAPABILITIES['topology_classes'])} — single-dimension "
            "Ring only at this stage"
        )

    workload_data = contracts.load_yaml(inputs["workload_ir"]["path"])
    workload_kind = workload_data.get("workload")
    if workload_kind not in CAPABILITIES["workload_kinds"]:
        raise AdapterError(
            f"backend {BACKEND_ID} does not translate workload kind "
            f"{workload_kind!r} ({manifest['workload_ir']['path']}); "
            f"translated kinds: {list(CAPABILITIES['workload_kinds'])} — "
            "W2 prefill phases and other generators are untranslated gaps, "
            "not silently approximated"
        )
    workload_config = w1.load_w1_config(inputs["workload_ir"]["path"])

    ranks = int(topology_data["ranks"])
    if workload_config.tp_size != ranks:
        raise AdapterError(
            f"workload tp_size {workload_config.tp_size} != topology ranks "
            f"{ranks} ({manifest['infra_graph']['path']})"
        )

    ops = tuple(w1.generate_w1_ops(workload_config))
    unsupported = sorted({op.collective for op in ops} - {"allreduce"})
    if unsupported:
        raise AdapterError(
            f"backend {BACKEND_ID} does not translate collective(s) "
            f"{unsupported} issued by workload kind {workload_kind!r}; "
            f"declared collective capabilities: "
            f"{list(CAPABILITIES['collectives'])}"
        )
    for op in ops:
        if op.payload_bytes < 1:
            raise AdapterError(
                f"op {op.op_id}: payload {op.payload_bytes} bytes; the "
                "analytical backend asserts chunk_size > 0 (BasicTopology."
                "cpp at the pin), so non-positive payloads are rejected"
            )

    link = topology_data["link"]
    free_parameters = (
        {
            "name": "link.bytes_per_ns",
            "value": str(_frac(link["bytes_per_ns"])),
            "unit": "bytes_per_ns",
            "assumption": "A-L0-BW",
            "source": str(manifest["infra_graph"]["path"]),
        },
        {
            "name": "link.hop_latency_ns",
            "value": str(_frac(link["hop_latency_ns"])),
            "unit": "ns",
            "assumption": "A-L0-LAT",
            "source": str(manifest["infra_graph"]["path"]),
        },
        {
            "name": "workload.allreduce_bytes",
            "value": str(workload_config.allreduce_bytes),
            "unit": "bytes",
            "assumption": "A-W1-SIZE",
            "source": str(manifest["workload_ir"]["path"]),
        },
    )
    return ValidatedExperiment(
        manifest=manifest,
        manifest_path=manifest_path,
        manifest_sha256=contracts.sha256_of(manifest_path),
        workload_config=workload_config,
        ops=ops,
        topology_id=str(topology_data["topology_id"]),
        ranks=ranks,
        link_bytes_per_ns=_frac(link["bytes_per_ns"]),
        hop_latency_ns=_frac(link["hop_latency_ns"]),
        free_parameters=free_parameters,
    )


def compile_experiment(manifest_path, out_dir) -> dict:
    """Translate the validated experiment into the ASTRA-sim input set.

    Writes exactly the four configuration kinds the pinned binary's CLI
    takes (workload ET files, system JSON, network YAML, remote-memory
    JSON; examples/run_scripts/analytical/congestion_unaware/
    Ring_reducescatter_4npus.sh at the pin) plus a deterministic
    ``compile_plan.json`` recording provenance, free parameters,
    translation assumptions, and per-file hashes. Pure function of the
    manifest: identical inputs produce byte-identical files (no
    wall-clock, no environment leakage).
    """
    experiment = validate_experiment(manifest_path)
    out_dir = Path(out_dir)
    (out_dir / "workload").mkdir(parents=True, exist_ok=True)

    # --- workload: one Chakra ET file per rank -----------------------------
    # A-AS1-IDS: rank-major global ids; A-AS1-CHAIN: per-rank data_deps
    # chain in generator order (step-major, layer-minor).
    ops = experiment.ops
    workload_prefix = experiment.manifest_path.stem
    for rank in range(experiment.ranks):
        nodes = []
        for index, op in enumerate(ops):
            node_id = rank * len(ops) + index
            nodes.append(
                chakra_et.Node(
                    id=node_id,
                    name=op.op_id,
                    node_type=chakra_et.COMM_COLL_NODE,
                    data_deps=(node_id - 1,) if index else (),
                    attrs=(
                        chakra_et.Attribute(
                            name="is_cpu_op", kind="bool", bool_value=False
                        ),
                        chakra_et.Attribute(
                            name="comm_type",
                            kind="int64",
                            int64_value=chakra_et.COLLECTIVE_COMM_TYPES[op.collective],
                        ),
                        chakra_et.Attribute(
                            name="comm_size",
                            kind="int64",
                            int64_value=op.payload_bytes,
                        ),
                    ),
                )
            )
            assert op.comm_ranks == tuple(range(experiment.ranks))
        path = out_dir / "workload" / f"{workload_prefix}.{rank}.et"
        path.write_bytes(
            chakra_et.encode_et_file(
                chakra_et.GlobalMetadata(), tuple(nodes)
            )
        )

    # --- network: single-dimension Ring (dimension order is the written
    # list order; one dimension here) --------------------------------------
    bw_decimal, bw_exact = bandwidth_gb_per_s(experiment.link_bytes_per_ns)
    latency = experiment.hop_latency_ns
    latency_decimal = _finite_decimal(latency)
    if latency_decimal.isdigit():  # mirror the pinned example's float style
        latency_decimal += ".0"
    network_yaml = (
        "# Generated by essun.backends.astra_sim.adapter (T022 stage S1) from\n"
        f"# {experiment.manifest_path.name}; free parameters A-L0-BW/A-L0-LAT.\n"
        "# Bandwidth unit convention at the pin: 1 GB = 2^30 B, converted to\n"
        "# B/ns via bw * 2^30 / 1e9 (A-AS1-BW-UNIT); the exact decimal below\n"
        f"# converts bit-exactly to the manifest value {experiment.link_bytes_per_ns} B/ns.\n"
        f"topology: [ Ring ]\n"
        f"npus_count: [ {experiment.ranks} ]\n"
        f"bandwidth: [ {bw_decimal} ]  # GB/s (exact {bw_exact}) -> {experiment.link_bytes_per_ns} B/ns\n"
        f"latency: [ {latency_decimal} ]  # ns (exact {latency})\n"
    )
    (out_dir / "network.yml").write_text(network_yaml, encoding="utf-8")

    # --- system: native Ring collective implementations (A-AS1-RING-IMPL,
    # A-AS1-SPLITS, A-AS1-CHUNKS-1, A-AS2-DELAY-POS, A-AS2-MEM-BW) -----------
    system = {
        "scheduling-policy": "LIFO",
        "endpoint-delay": 10,  # A-AS2-DELAY-POS (0 aborts the pinned binary)
        "active-chunks-per-dimension": 1,
        "preferred-dataset-splits": experiment.ranks,
        "all-reduce-implementation": ["ring"],
        "all-gather-implementation": ["ring"],
        "reduce-scatter-implementation": ["ring"],
        "all-to-all-implementation": ["ring"],
        "collective-optimization": "localBWAware",
        "local-mem-bw": 1600,  # A-AS2-MEM-BW (absent key never completes)
    }
    (out_dir / "system.json").write_text(
        json.dumps(system, indent=4) + "\n", encoding="utf-8"
    )

    # --- remote memory: analytical, no expansion (A-AS1-NO-EXPANSION) ------
    remote_memory = {"memory-type": "NO_MEMORY_EXPANSION"}
    (out_dir / "remote_memory.json").write_text(
        json.dumps(remote_memory, indent=4) + "\n", encoding="utf-8"
    )

    # --- deterministic compile plan (the BackendPlan) -----------------------
    files = {}
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "compile_plan.json":
            files[str(path.relative_to(out_dir))] = contracts.sha256_of(path)
    plan = {
        "backend_id": BACKEND_ID,
        "stage": "T022-S2 translation (executable; stage S2 counterexample revisions A-AS2-*)",
        "experiment_id": experiment.manifest["experiment_id"],
        "source_manifest": {
            "path": _rel(experiment.manifest_path),
            "sha256": experiment.manifest_sha256,
        },
        "pin": PIN,
        "binary_cli": {
            "--workload-configuration": f"<run-dir>/workload/{workload_prefix}",
            "--system-configuration": "system.json",
            "--remote-memory-configuration": "remote_memory.json",
            "--network-configuration": "network.yml",
            "anchor": (
                "examples/run_scripts/analytical/congestion_unaware/"
                "Ring_reducescatter_4npus.sh at the pin"
            ),
        },
        "workload": {
            "kind": "w1_dense_tp_decode",
            "ops_per_rank": len(ops),
            "op_order": [op.op_id for op in ops],
            "comm_type": "ALL_REDUCE (0)",
            "comm_size_bytes": [
                {"op_id": op.op_id, "bytes": op.payload_bytes} for op in ops
            ],
            "node_id_rule": "rank * ops_per_rank + op_index (A-AS1-IDS)",
            "dependency_rule": "data_deps chain per rank (A-AS1-CHAIN)",
            "et_version": "0.0.4",
        },
        "topology": {
            "topology_id": experiment.topology_id,
            "ranks": experiment.ranks,
            "dimension_order": ["Ring"],
            "dimensions": [
                {
                    "basic_topology": "Ring",
                    "npus_count": experiment.ranks,
                    "bandwidth_GB_per_s_exact": bw_decimal,
                    "bandwidth_B_per_ns_exact": str(experiment.link_bytes_per_ns),
                    "latency_ns_exact": str(latency),
                }
            ],
        },
        "free_parameters": list(experiment.free_parameters),
        "translation_assumptions": list(TRANSLATION_ASSUMPTIONS),
        "files": files,
    }
    (out_dir / "compile_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return plan


# ---------------------------------------------------------------------------
# Stage S2: execution in the pinned container + output parsing
# ---------------------------------------------------------------------------

# Result-line grammar at the pin (runbook §5; spdlog stdout == log/log.log).
# Wall-clock timestamp prefixes are wall time of the simulation process and
# are ignored by the parser; the numeric fields are simulated ns
# (EventTime = uint64_t, "Event time in ns",
# extern/network_backend/analytical/include/astra-network-analytical/common/
# Type.h at the pin; wall_time = max node end_time, Statistics.cc:273-284).
_WALL_RE = re.compile(r"\[statistics\].*sys\[(\d+)\], Wall time: (\d+)\s*$")
_COMM_RE = re.compile(r"\[statistics\].*sys\[(\d+)\], Comm time: (\d+)\s*$")
_FINISHED_RE = re.compile(
    r"\[workload\].*sys\[(\d+)\] finished, (\d+) cycles, "
    r"exposed communication (\d+) cycles\."
)
_CRITICAL_RE = re.compile(r"\[critical\]")
_BINARY_SHA_LINE_RE = re.compile(r"^ESSUN_BINARY_SHA256=([0-9a-f]{64})\s*$", re.M)


def parse_output(stdout: str, exit_code: int, ranks: int) -> dict:
    """Parse the pinned binary's stdout into per-rank simulated times.

    Deterministic pure function of the text. Rejects loudly (never guesses):

    - non-zero container exit or simulated-process exit code;
    - any ``[critical]`` log line — at this pin failure modes like
      "unreleased nodes" are logged CRITICAL while the process still exits
      0, so criticals are a hard parse error, not a warning;
    - a missing or mismatched binary sha256 marker line;
    - any rank of ``0..ranks-1`` missing its finished/Wall/Comm lines, or a
      rank reporting more than once;
    - a Wall time below that rank's Comm time (wall is a max over all node
      end times; comm is a subset of it).
    """
    if exit_code != 0:
        raise AdapterError(
            f"container exited with code {exit_code}; the pinned binary or "
            "docker failed before results could be parsed"
        )
    binary_sha = _BINARY_SHA_LINE_RE.search(stdout)
    if binary_sha is None:
        raise AdapterError(
            "output carries no ESSUN_BINARY_SHA256 marker; the container "
            "command did not run the pinned verification preamble"
        )
    if binary_sha.group(1) != PIN["binary_sha256"]:
        raise AdapterError(
            f"container binary sha256 {binary_sha.group(1)} != pinned "
            f"{PIN['binary_sha256']}; refusing results from an unpinned binary"
        )
    if re.search(r"ASTRA_EXIT=(\d+)", stdout) is None:
        raise AdapterError("output carries no ASTRA_EXIT= marker line")
    astra_exit = int(re.search(r"ASTRA_EXIT=(-?\d+)", stdout).group(1))
    if astra_exit != 0:
        raise AdapterError(
            f"ASTRA-sim process exited with code {astra_exit} (see its "
            "stdout/stderr in the run log); refusing to parse a failed run"
        )
    critical = [line for line in stdout.splitlines() if _CRITICAL_RE.search(line)]
    if critical:
        raise AdapterError(
            f"output contains {len(critical)} [critical] log line(s); at "
            "this pin 'unreleased nodes'/'did not finish' failures exit 0 "
            "and are only visible as criticals — first: {critical[0].strip()}"
        )

    per_rank: dict[int, dict[str, int]] = {}

    def _record(rank_s: str, field: str, value_s: str, line: str) -> None:
        rank, value = int(rank_s), int(value_s)
        if not 0 <= rank < ranks:
            raise AdapterError(
                f"parsed sys[{rank}] outside declared ranks 0..{ranks - 1} "
                f"(line: {line.strip()!r})"
            )
        entry = per_rank.setdefault(rank, {})
        if field in entry:
            raise AdapterError(
                f"sys[{rank}] reported {field} twice; ambiguous output "
                f"(lines {entry[field]} and {value})"
            )
        entry[field] = value

    for line in stdout.splitlines():
        match = _WALL_RE.search(line)
        if match:
            _record(match.group(1), "wall_time_ns", match.group(2), line)
        match = _COMM_RE.search(line)
        if match:
            _record(match.group(1), "comm_time_ns", match.group(2), line)
        match = _FINISHED_RE.search(line)
        if match:
            _record(match.group(1), "finished_cycles", match.group(2), line)
            # third group (exposed communication cycles) is informational at
            # this pin; recorded via finished/exposed pair below
            _record(match.group(1), "exposed_comm_cycles", match.group(3), line)

    missing = [rank for rank in range(ranks) if rank not in per_rank]
    if missing:
        raise AdapterError(
            f"no result lines parsed for rank(s) {missing} of 0..{ranks - 1}; "
            "the workload did not finish on every NPU"
        )
    incomplete = sorted(
        rank
        for rank, entry in per_rank.items()
        if not {"wall_time_ns", "comm_time_ns", "finished_cycles"} <= set(entry)
    )
    if incomplete:
        raise AdapterError(
            f"rank(s) {incomplete} lack Wall/Comm/finished lines; ambiguous "
            "output is rejected rather than partially parsed"
        )
    inverted = sorted(
        rank
        for rank, entry in per_rank.items()
        if entry["wall_time_ns"] < entry["comm_time_ns"]
    )
    if inverted:
        raise AdapterError(
            f"rank(s) {inverted} report Wall time < Comm time; wall_time is "
            "a max over all node end times so this cannot be valid output"
        )
    return {
        "ranks": ranks,
        "per_rank": [
            {
                "rank": rank,
                "wall_time_ns": per_rank[rank]["wall_time_ns"],
                "comm_time_ns": per_rank[rank]["comm_time_ns"],
                "finished_cycles": per_rank[rank]["finished_cycles"],
                "exposed_comm_cycles": per_rank[rank]["exposed_comm_cycles"],
            }
            for rank in sorted(per_rank)
        ],
        "completion_time_ns": max(e["wall_time_ns"] for e in per_rank.values()),
        "units": "ns (EventTime, astra-network-analytical common/Type.h at the pin)",
    }


def docker_run_container(inputs_dir: Path, workload_prefix: str, ranks: int) -> dict:
    """Run the compiled inputs in the pinned container per the runbook.

    Bind-mount route (runbook §6, verified in S2): the inputs directory and
    a scratch run directory (the binary creates ``log/`` in its CWD) are
    bind-mounted and the exact four-flag CLI of the pinned
    congestion-unaware example is invoked. S2 finding: the mounts must NOT
    be read-only — on this host (OrbStack virtiofs) the binary's file open
    fails on a :ro mount even though shell tools can read the same file
    (reproduced deterministically), so both mounts are writable and the
    command never writes into the inputs tree. The command first prints
    the container-side binary sha256 marker so the parser can prove the
    executed binary is the pinned one, and ends with an ``ASTRA_EXIT=``
    marker carrying the simulator's own exit code.
    """
    import shutil
    import subprocess
    import tempfile

    inputs_dir = Path(inputs_dir).resolve()
    if shutil.which("docker") is None:
        raise AdapterError(
            "docker CLI not found on PATH; backend astra_sim_analytical "
            "executes the pinned binary in container "
            f"{PIN['docker_image']} and cannot run without it"
        )
    inspect = subprocess.run(
        ["docker", "image", "inspect", PIN["docker_image"], "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
    )
    if inspect.returncode != 0:
        raise AdapterError(
            f"docker image {PIN['docker_image']} not available locally: "
            f"{inspect.stderr.strip()}; build it per "
            "backends/docker/astra-sim-runbook.md before running this backend"
        )
    image_id = inspect.stdout.strip()
    if image_id != PIN["docker_image_id"]:
        raise AdapterError(
            f"docker image id {image_id} != pinned {PIN['docker_image_id']}; "
            "refusing to execute an unpinned image"
        )

    with tempfile.TemporaryDirectory(prefix="essun-astra-run-") as scratch:
        run_dir = (Path(scratch) / "run").resolve()
        run_dir.mkdir()
        script = (
            "cd /mnt/run && "
            "echo ESSUN_BINARY_SHA256=$(sha256sum "
            f"{PIN['binary_path_in_image']} | cut -d' ' -f1) && "
            f"{PIN['binary_path_in_image']}"
            f" --workload-configuration=/mnt/inputs/workload/{workload_prefix}"
            " --system-configuration=/mnt/inputs/system.json"
            " --remote-memory-configuration=/mnt/inputs/remote_memory.json"
            " --network-configuration=/mnt/inputs/network.yml"
            " ; rc=$? ; echo ASTRA_EXIT=$rc"
        )
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{inputs_dir}:/mnt/inputs",
                "-v",
                f"{run_dir}:/mnt/run",
                PIN["docker_image"],
                "bash",
                "-c",
                script,
            ],
            capture_output=True,
            text=True,
        )
        # stdout carries the result lines; stderr carries docker-level noise
        # only — both are joined so parser errors quote the failure cause.
        return {"exit_code": proc.returncode, "stdout": proc.stdout + proc.stderr}


def execute_experiment(manifest_path, *, run_container=None) -> dict:
    """Full BackendAdapter run: validate -> compile -> execute -> parse.

    Returns ``{"observations": ..., "execution": ...}``. The orchestrator
    persists both through the evidence store (``orchestrator/runs.py``);
    every field is a deterministic function of (manifest, inputs, pin) —
    no wall-clock, no host paths, no container-internal timestamps — so an
    identical rerun yields byte-identical RunRecords.

    ``run_container`` overrides the container invocation (tests replay a
    recorded real output through it; the default runs the pinned image via
    the docker CLI and is resolved at call time so it stays patchable).

    O-CONSERVATION is recorded as explicitly unsupported for this backend:
    the analytical congestion-unaware output carries no byte accounting
    (runbook §5 lists every emitted line kind), which is an honest
    per-backend gap, not a silent omission.
    """
    if run_container is None:
        run_container = docker_run_container
    experiment = validate_experiment(manifest_path)
    workload_prefix = experiment.manifest_path.stem
    with tempfile.TemporaryDirectory(prefix="essun-astra-inputs-") as tmp:
        inputs_dir = Path(tmp) / "inputs"
        plan = compile_experiment(manifest_path, inputs_dir)
        # compile_plan.json is a essun provenance artifact, not a binary
        # input; keep the container's view of the inputs minimal.
        (inputs_dir / "compile_plan.json").unlink()
        result = run_container(inputs_dir, workload_prefix, experiment.ranks)
    parsed = parse_output(result["stdout"], result["exit_code"], experiment.ranks)

    observations = {
        "backend_id": BACKEND_ID,
        "model": {
            "fidelity": CAPABILITIES["fidelity"],
            "transport_model": CAPABILITIES["transport_model"],
            "topology_id": experiment.topology_id,
            "ranks": experiment.ranks,
            "link_bytes_per_ns_exact": str(experiment.link_bytes_per_ns),
            "hop_latency_ns_exact": str(experiment.hop_latency_ns),
            "units": parsed["units"],
            "pin": {
                "astra_sim_commit": PIN["astra_sim_commit"],
                "docker_image": PIN["docker_image"],
                "docker_image_id": PIN["docker_image_id"],
                "binary_sha256": PIN["binary_sha256"],
            },
            "executed_input_files": dict(plan["files"]),
            "translation_assumption_ids": [
                a["id"] for a in TRANSLATION_ASSUMPTIONS
            ],
        },
        "observables": {
            "O-CCT": {
                # kind matches the registry spec (ANALYTICAL); the values are
                # PARSED simulator output, not a closed form — see "method".
                "kind": "analytical",
                "method": (
                    "parsed from the pinned binary's [statistics] "
                    "'sys[i], Wall time:' lines (simulated ns; runbook §5); "
                    "not a closed-form identity"
                ),
                "ops": len(experiment.ops),
                "ops_per_rank": len(experiment.ops),
                "aggregation": (
                    "per-rank wall time of the full data_deps-serialized "
                    "op chain (A-AS1-CHAIN); completion_time_ns = max over "
                    "ranks; no per-op decomposition exists in this output"
                ),
                "per_rank": [
                    {
                        "rank": entry["rank"],
                        "wall_time_ns": entry["wall_time_ns"],
                        "comm_time_ns": entry["comm_time_ns"],
                    }
                    for entry in parsed["per_rank"]
                ],
                "completion_time_ns": parsed["completion_time_ns"],
            },
        },
        "unsupported_observables": {
            "O-CONSERVATION": (
                "the analytical congestion-unaware output has no byte "
                "accounting (only per-NPU cycle/time lines, runbook §5), so "
                "wire-conservation cannot be emitted honestly for this "
                "backend; explicitly declared unsupported, matching "
                "CAPABILITIES['explicitly_unsupported']"
            ),
        },
    }
    execution = {
        "backend_id": BACKEND_ID,
        "container": {
            "route": "docker bind-mount run dir (runbook §6, verified in S2)",
            "image": PIN["docker_image"],
            "image_id_verified": True,
            "binary_sha256_verified": True,
            "cli_anchor": (
                "examples/run_scripts/analytical/congestion_unaware/"
                "Ring_reducescatter_4npus.sh at the pin (four-flag CLI)"
            ),
        },
        "parsed": parsed,
    }
    return {"observations": observations, "execution": execution}


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Compile an experiment manifest into ASTRA-sim analytical "
            "input files (T022 stage S1: translation only, no execution)"
        )
    )
    parser.add_argument("manifest", help="path to the experiment manifest YAML")
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "output directory (default: "
            "experiments/vertical_slice/astra_<manifest stem>)"
        ),
    )
    args = parser.parse_args(argv)
    manifest = Path(args.manifest)
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else contracts.REPO_ROOT
        / "experiments"
        / "vertical_slice"
        / f"astra_{manifest.stem}"
    )
    plan = compile_experiment(manifest, out_dir)
    print(
        json.dumps(
            {"out_dir": str(out_dir), "files": sorted(plan["files"])}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
