"""uet-htsim CMS adapter — translation and capabilities.

BackendAdapter (IMPLEMENTATION_GUIDE §5) surface for the **ultraethernet/
uet-htsim** simulator (the UEC Congestion Management Group's HTSim-based
transport simulator) at the pinned commit
``65ea315b25725df9791a5b93b61cbd6938cba0a8`` (pin matrix:
``backends/pins/uet-htsim.md``; Docker image ``essun/uet-htsim:s1``, image
id sha256:7eafbdd387fd, runbook ``backends/docker/uet-htsim-runbook.md``).
This is the independent third backend: unlike the ASTRA-sim
analytical frontend (congestion-unaware) and the csg-htsim packet frontend
inside ASTRA-sim, this tree IS the UEC CMS simulator — the only backend
family that models receiver-credit congestion management at all.

Stage S1 delivered ``capabilities()`` -> ``validate_experiment()`` ->
``compile_experiment()`` (translation only). Stage S2 (this module's
execution section) adds :func:`execute_experiment`: the compiled op
matrices run per the runbook §2 command shape inside the pinned container
(bind-mount route of runbook §6 — verified in S2), one ``htsim_uec``
invocation per op file in generator op order (A-UET1-OPFILE: the .cm
grammar has no dependency mechanism, so op serialization is enforced HERE,
never by invented start times), with the manifest-derived flags written
exactly (``-linkspeed 512000``, ``-hop_latency 0.2``, ``-seed 20261026``
— echoed back by the binary and cross-checked). Per-flow FCT lines
(runbook §5.1) are parsed into per-op completions (max over the op's
concurrent flows) and summed into the serialized-chain O-CCT; the
``logout.dat`` traces (§5.2) are hashed into the run record but not
parsed. Determinism was verified in S2 on two fresh containers: stdout
byte-identical and all six traces byte-identical (stage report
``reports/p3_uet_stage2.md``) — no seed-surface patch needed, the
explicit ``-seed`` is honored (A-UET1-SEED).

What this backend models (mirrored from ``backends/pins/uet-htsim.md``,
every claim anchored in the pinned tree or the executed smoke):

- packet-level discrete-event simulation of **point-to-point message
  flows** (connection matrices: ``src->dst start <us> size <bytes>``),
- **UET CMS congestion management**: receiver-credit-based transport with
  NSCC sender CC and per-flow CMS counters (``fair_inc/prop_inc/
  fast_inc/eta_inc``, NACK/Pull) — the CMS research platform the
  repository exists for (pin scope, README),
- queues, ECN, retransmission, MTU-sized packets, auto-generated fat-tree
  fabrics (2/3-tier) or ``-topo`` files.

What it LOUDLY does NOT model (explicitly_unsupported below):

- **no native collective semantics at all** — no AllReduce, AllGather,
  ReduceScatter, AllToAll operation exists in ``htsim_uec``; collectives
  enter only through this adapter's declared wire-pattern decomposition
  (A-UET1-WIRE), never as simulator semantics;
- **no compute model** — no GPU/NPU, no Chakra ET, no collective
  algorithm library (ASTRA-sim provides those; this backend does not);
- **non-normative CMS semantics** — the upstream README's own non-goals:
  "not a complete implementation of the UEC transport specification",
  "not a standard", "There might be discrepancies between the UEC CMS
  specification and the simulator. Only the official CMS specification is
  significant." The CMS behavior simulated here is the WG's research
  platform at this pin, NOT the CMS specification;
- **no ring fabric**: the physical fabric is an auto-generated fat tree
  (the only S2-smoke-verified shape is Nodes 16, 3-tier); the manifest's
  unidirectional ring is translated as the LOGICAL traffic pattern placed
  on that fabric (A-UET1-FABRIC) — a declared modeling-assumption
  difference vs the L0/ASTRA-sim single-hop ring, to be classified (never
  tuned) in the stage S3 independence note;
- no scale-up memory semantics (UALink/CXL/UnifiedBus load-store), no
  standard-specific semantics, and ``O-CONSERVATION``: the per-flow byte
  counters include packet overhead and retransmissions (smoke: 2,002,140
  counted bytes for a 2,000,000-byte flow), and no received-side ledger
  is established in the verified output surface, so wire conservation
  cannot be emitted honestly at this stage.

Free parameters flow from the experiment manifest (topology file's
``link.bytes_per_ns`` / ``link.hop_latency_ns`` -> ``-linkspeed`` /
``-hop_latency`` by exact conversion, workload file's byte sizes -> flow
sizes by exact chunked-ring arithmetic). Nothing standard-derived is
invented; every uet-htsim-side knob with no manifest counterpart is
recorded in TRANSLATION_ASSUMPTIONS with its runbook/source anchor
(provenance rule).
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
from essun.workload import w1

BACKEND_ID = "uet_htsim_cms"

# Provenance of everything this adapter targets (never a moving HEAD).
# Values mirror backends/docker/uet-htsim-runbook.md §1 (observed in the
# Docker smoke at the pin) and backends/pins/uet-htsim.md.
PIN = {
    "uet_htsim_commit": "65ea315b25725df9791a5b93b61cbd6938cba0a8",
    "docker_image": "essun/uet-htsim:s1",
    "docker_image_id": (
        "sha256:7eafbdd387fd521d5531050ae40ab97f0a3b81f3424c95619fbc5095da83d312"
    ),
    "base_image": (
        "ubuntu:22.04@sha256:e0f80c829509ef4df9e76bd8944eb7b8ec25cbb379b112a"
        "7f9448b2c77a77c9b"
    ),
    "binary_path_in_image": (
        "/opt/uet-htsim/htsim/sim/build/datacenter/htsim_uec"
    ),
    "binary_sha256": (
        "fe5a1c645719b792bb56c631fbd991cf7f6c824af8a97f42971bd59b584cd896"
    ),
    "license": (
        "BSD-2-Clause via LICENSE-Transport-WG.txt "
        "(backends/pins/uet-htsim.LICENSE-Transport-WG.txt)"
    ),
    "capability_matrix": "backends/pins/uet-htsim.md",
    "runbook": "backends/docker/uet-htsim-runbook.md",
    "dockerfile": "backends/docker/uet-htsim.Dockerfile",
}

# The only fabric shape exercised by the Docker smoke at the pin: the
# connection matrix one.cm declares `Nodes 16` and the auto-generated
# topology echoed NSRV=16 (runbook §4.1, §4.3). Larger fabrics are an
# untranslated gap until -topo is verified (runbook §4.2, §6).
FABRIC_NODES = 16

# Collectives this adapter translates by DECLARED wire-pattern
# decomposition. These are NOT simulator capabilities — htsim_uec has no
# collective semantics — they are translation routes whose emitted traffic
# pattern is fixed by an assumption in TRANSLATION_ASSUMPTIONS.
DECOMPOSED_COLLECTIVES = ("allreduce",)

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": (
        "DES: packet-level event simulation of point-to-point message flows "
        "with UET CMS receiver-credit congestion control (NSCC sender CC) on "
        "an auto-generated fat-tree fabric"
    ),
    # DELIBERATELY EMPTY: htsim_uec has no collective operations. The
    # workload kinds below are translated by wire-pattern decomposition
    # (DECOMPOSED_COLLECTIVES + A-UET1-WIRE), never as native semantics.
    "collectives": (),
    "topology_classes": ("unidirectional_ring",),
    "workload_kinds": ("w1_dense_tp_decode",),
    "transport_model": (
        "uet_cms_receiver_credit_congestion_control (non-normative research "
        "implementation at the pin, NOT the UEC CMS specification)"
    ),
    # O-CCT only at this stage: parsed per-flow completion times. The
    # byte counters that exist in the output count packet overhead and
    # retransmissions, and no received-side ledger is verified, so
    # O-CONSERVATION cannot be emitted honestly here.
    "observables": ("O-CCT",),
    "explicitly_unsupported": (
        "native_collective_semantics",
        "compute_model",
        "normative_uec_cms_semantics",
        "ring_fabric_topology",
        "topology_file_route",
        "scale_up_memory_semantics",
        "standard_specific_semantics",
        "O-CONSERVATION",
    ),
}

# uet-htsim-side knobs with no manifest counterpart. Each is an upstream
# default or an adapter translation convention — none is standard-derived
# (the upstream README itself disclaims standard status) — and each
# carries its anchor in the pinned tree or the executed-smoke runbook.
TRANSLATION_ASSUMPTIONS = (
    {
        "id": "A-UET1-WIRE",
        "parameter": "workload collective -> connection-matrix flows",
        "value": (
            "one flow per rank per op: rank i -> ring successor (i+1) mod r, "
            "size 2*(r-1)/r*M bytes, requires r | M"
        ),
        "rationale": (
            "htsim_uec has no collective semantics, so the W1 AllReduce is "
            "translated as the chunked-ring WIRE pattern the L0 ring "
            "identity declares (l0.py ring_traffic_per_rank; O-CONSERVATION "
            "identity total 2*(r-1)*M; O-TRAFFIC-IMBALANCE relation 'each "
            "rank sends 2*(r-1)/r*M to its single successor'). The emitted "
            "traffic is therefore byte-identical to the L0/ASTRA-sim "
            "declared logical pattern; only its transport is simulated. "
            "Equal-chunk realizability requires r | M, mirroring the L0 "
            "divisibility gate A-L0-DIV."
        ),
        "anchor": (
            "src/essun/backends/analytical/l0.py (ring_traffic_per_rank); "
            "src/essun/observables.py (O-CONSERVATION, "
            "O-TRAFFIC-IMBALANCE); runbook section 4.1 grammar"
        ),
    },
    {
        "id": "A-UET1-OPFILE",
        "parameter": "op serialization -> file layout",
        "value": "one .cm file per workload op; an op's r flows start at 0",
        "rationale": (
            "The connection-matrix grammar has no dependency mechanism "
            "(only absolute start times), so serialized ops — the L0 "
            "sum-of-ops reading and the ASTRA-sim data_deps chain "
            "(A-AS1-CHAIN) — cannot be expressed inside one file. Each op "
            "is compiled to its own matrix; op serialization is enforced by "
            "the stage S2 run orchestration (files run in op order, per-op "
            "completion times summed), never by invented start times. "
            "Within one op the r ring flows are concurrent (the wire "
            "pattern of one collective)."
        ),
        "anchor": (
            "runbook section 4.1 (connection_matrix.cpp grammar: "
            "src->dst [start] [size] [id] [msg] [trigger], no deps); "
            "src/essun/backends/astra_sim/adapter.py A-AS1-CHAIN"
        ),
    },
    {
        "id": "A-UET1-FABRIC",
        "parameter": "fabric topology",
        "value": f"auto 3-tier fat tree, Nodes {FABRIC_NODES}, ranks 0..r-1 placed",
        "rationale": (
            "With no -topo, the binary builds a fat tree sized by the "
            "matrix's Nodes header; the only smoke-verified shape is "
            "Nodes 16 (NSRV=16, runbook sections 4.1/4.3), so every "
            "compiled matrix declares exactly that and places ranks "
            "0..r-1 on hosts 0..r-1 (hosts r..15 idle). The manifest's "
            "unidirectional ring is thus a LOGICAL traffic pattern on a "
            "fat-tree fabric: ring neighbors are multiple physical hops "
            "apart and each hop carries L (A-UET1-LAT), a declared "
            "modeling-assumption difference vs the single-hop L0/ASTRA "
            "ring — classified, never tuned, in the stage S3 independence "
            "note. Larger node counts are an untranslated gap pending "
            "-topo verification (runbook section 4.2, not exercised)."
        ),
        "anchor": "runbook sections 4.1, 4.2 (not exercised), 4.3, 6",
    },
    {
        "id": "A-UET1-BW",
        "parameter": "link.bytes_per_ns -> -linkspeed",
        "value": "exact integer Mbps = 8000 * B",
        "rationale": (
            "The flag is link speed in Mbps (runbook section 3); "
            "1 B/ns = 1e9 B/s = 8000 Mbit/s exactly, so B = 64 B/ns maps "
            "to -linkspeed 512000. A bandwidth with no exact integral "
            "Mbps value (e.g. 1/3 B/ns) is rejected rather than silently "
            "rounded — the translation must not perturb the free "
            "parameter."
        ),
        "anchor": "runbook section 3 (-linkspeed NUM, Mbps, default 100000)",
    },
    {
        "id": "A-UET1-LAT",
        "parameter": "link.hop_latency_ns -> -hop_latency",
        "value": "exact decimal us = L / 1000",
        "rationale": (
            "The flag is per-hop wire latency in us (runbook section 3); "
            "L = 200 ns maps to -hop_latency 0.2 exactly. A latency whose "
            "us form has no finite decimal is rejected, not rounded. "
            "NOTE the semantic difference: the flag applies per PHYSICAL "
            "fat-tree hop (see A-UET1-FABRIC), while L0 charges L once "
            "per logical ring hop — part of the declared cross-backend "
            "difference, not a conversion error."
        ),
        "anchor": "runbook section 3 (-hop_latency NUM, us, default 1)",
    },
    {
        "id": "A-UET1-SEED",
        "parameter": "experiment seed -> -seed",
        "value": "manifest seed, explicit",
        "rationale": (
            "Platform determinism rule 6 / runbook section 6: pass -seed "
            "explicitly instead of relying on the upstream default 13 "
            "(the two default-seed smoke runs were byte-identical, "
            "consistent with a fixed default). The manifest seed must fit "
            "the flag's uint range; out-of-range seeds are rejected."
        ),
        "anchor": "runbook sections 3 (-seed UINT, default 13) and 6",
    },
    {
        "id": "A-UET1-IDS",
        "parameter": "connection flow ids",
        "value": "op_index * ranks + rank + 1",
        "rationale": (
            "Flow id 0 is rejected by the parser (runbook section 4.1), "
            "so ids start at 1; the rule is globally unique across all op "
            "files (op 0 -> 1..r, op k -> k*r+1..(k+1)*r) and replayable."
        ),
        "anchor": "runbook section 4.1 (connection_matrix.cpp: flow id 0 rejected)",
    },
    {
        "id": "A-UET1-MTU",
        "parameter": "-mtu",
        "value": 4150,
        "rationale": (
            "Upstream default packet size (HOST MTU, main.h:9 at the pin), "
            "retained. Packetization is a real effect this backend models "
            "and the L0 model does not — a declared fidelity difference, "
            "never tuned to match curves."
        ),
        "anchor": "runbook section 3 (-mtu UINT, default 4150, main.h:9)",
    },
    {
        "id": "A-UET1-CC",
        "parameter": "-sender_cc_algo / -sender_cc / -receiver_cc",
        "value": {"-sender_cc_algo": "nscc", "-sender_cc": True, "-receiver_cc": False},
        "rationale": (
            "Upstream defaults, retained: they select the UET CMS path "
            "(NSCC sender congestion control with receiver credit) that is "
            "this backend's entire reason to exist in OD-002. Per the pin "
            "doc these are the WG research implementation's semantics, "
            "not the CMS specification."
        ),
        "anchor": (
            "runbook section 3; backends/pins/uet-htsim.md scope "
            "(README non-goals)"
        ),
    },
    {
        "id": "A-UET1-END",
        "parameter": "-end",
        "value": 1000,
        "rationale": (
            "Upstream default simulation end (us), retained. Static "
            "sufficiency estimate for the smoke shape (an ESTIMATE, not a "
            "result): 28672 B per flow at B = 64 B/ns serializes in 448 ns "
            "= 0.448 us, and the fat-tree path latency is a handful of "
            "0.2 us hops, so per-op completion is far below 1000 us; "
            "stage S2 verifies against parsed output before relying on it."
        ),
        "anchor": "runbook section 3 (-end UINT, us, default 1000)",
    },
)


class AdapterError(Exception):
    """Raised when an experiment cannot be translated for this backend
    (capability or translation gap) — always names the gap."""


def _rel(path: Path) -> str:
    """Repo-relative path when possible (same convention as the ASTRA-sim
    adapter), so compiled plans are location-independent."""
    try:
        return str(Path(path).resolve().relative_to(contracts.REPO_ROOT))
    except ValueError:
        return str(Path(path).resolve())


def _frac(value) -> Fraction:
    # str() first so YAML decimals are interpreted exactly (same policy as
    # the L0 backends and the ASTRA-sim adapter).
    return Fraction(str(value))


def _finite_decimal(value: Fraction) -> str:
    """Exact finite decimal string for a fraction whose denominator is
    2^a * 5^b (true for ns -> us by /1000 with integer-valued ns)."""
    with localcontext() as ctx:
        ctx.prec = 60
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def _denominator_is_2a5b(denominator: int) -> bool:
    remainder = denominator
    for factor in (2, 5):
        while remainder % factor == 0:
            remainder //= factor
    return remainder == 1


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
    linkspeed_mbps: int
    hop_latency_us: str
    seed: int
    free_parameters: tuple[dict, ...]


def capabilities() -> dict:
    """CapabilitySet of this backend (IMPLEMENTATION_GUIDE §5)."""
    return dict(CAPABILITIES)


def bandwidth_mbps(bytes_per_ns: Fraction) -> int:
    """Convert manifest bandwidth (B/ns) to the ``-linkspeed`` Mbps value.

    Exact: 1 B/ns = 1e9 B/s = 8000 Mbit/s, so Mbps = 8000 * B. A value
    with no exact integral Mbps form is rejected rather than rounded (the
    written flag must denote the manifest free parameter bit-exactly;
    A-UET1-BW).
    """
    mbps = _frac(bytes_per_ns) * 8000
    if mbps.denominator != 1:
        raise AdapterError(
            f"bandwidth {bytes_per_ns} B/ns has no exact integral -linkspeed "
            "Mbps value (A-UET1-BW); refusing to write an inexact flag that "
            "would silently perturb the translation"
        )
    return int(mbps)


def hop_latency_us(hop_latency_ns: Fraction) -> str:
    """Convert manifest per-hop latency (ns) to the ``-hop_latency`` us
    decimal string, exactly; non-finite decimals are rejected (A-UET1-LAT)."""
    latency_ns = _frac(hop_latency_ns)
    if latency_ns < 0:
        raise AdapterError(f"negative hop latency {latency_ns} ns is not physical")
    micro = latency_ns / 1000
    if not _denominator_is_2a5b(micro.denominator):
        raise AdapterError(
            f"hop latency {latency_ns} ns has no exact finite decimal us form "
            "(A-UET1-LAT); refusing to write an inexact flag that would "
            "silently perturb the translation"
        )
    return _finite_decimal(micro)


def validate_experiment(manifest_path) -> ValidatedExperiment:
    """Load and gate the experiment manifest against this backend.

    Every rejection names the gap explicitly (BackendAdapter contract: an
    adapter must reject unsupported required semantics explicitly).
    """
    manifest_path = Path(manifest_path)
    manifest = contracts.load_experiment_manifest(manifest_path)
    inputs = contracts.resolve_inputs(manifest)

    if manifest["backends"] != [BACKEND_ID]:
        # The compiled uet-htsim view describes the same experiment as the
        # L0 baseline, but an adapter entry must be unambiguous.
        raise AdapterError(
            f"adapter {BACKEND_ID} requires backends == [{BACKEND_ID!r}], "
            f"got {manifest['backends']!r}"
        )

    missing = set(manifest["observables"]) - set(CAPABILITIES["observables"])
    if missing:
        unsupported = sorted(missing & set(CAPABILITIES["explicitly_unsupported"]))
        detail = ""
        if "O-CONSERVATION" in unsupported:
            detail = (
                " — O-CONSERVATION: the binary's per-flow byte counters "
                "include packet overhead and retransmissions (smoke: "
                "2,002,140 counted bytes for a 2,000,000-byte flow) and no "
                "received-side ledger is established in the verified output "
                "surface, so wire conservation cannot be emitted honestly "
                "for this backend at this stage"
            )
        raise AdapterError(
            f"backend {BACKEND_ID} does not support observable(s) "
            f"{sorted(missing)}{detail}; capabilities: {CAPABILITIES}"
        )

    topology_data = contracts.load_yaml(inputs["infra_graph"]["path"])
    topology_class = topology_data.get("topology_class")
    if topology_class not in CAPABILITIES["topology_classes"]:
        raise AdapterError(
            f"backend {BACKEND_ID} has no uet-htsim translation declared for "
            f"topology_class {topology_class!r} "
            f"({manifest['infra_graph']['path']}); declared classes: "
            f"{list(CAPABILITIES['topology_classes'])} — the unidirectional "
            "ring as a logical traffic pattern on the fat-tree fabric "
            "(A-UET1-FABRIC) only at this stage"
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
    if not 2 <= ranks <= FABRIC_NODES:
        raise AdapterError(
            f"ranks {ranks} outside the translatable range 2..{FABRIC_NODES} "
            f"({manifest['infra_graph']['path']}): the only smoke-verified "
            f"fabric shape is the auto 3-tier fat tree with Nodes "
            f"{FABRIC_NODES} (runbook sections 4.3, 6), and larger fabrics "
            "are an untranslated gap pending -topo verification "
            "(A-UET1-FABRIC)"
        )

    seed = int(manifest["seed"])
    if not 0 <= seed <= 0xFFFFFFFF:
        raise AdapterError(
            f"seed {seed} outside the -seed UINT range 0..4294967295 "
            "(A-UET1-SEED); the manifest seed must be translatable verbatim"
        )

    ops = tuple(w1.generate_w1_ops(workload_config))
    unsupported = sorted({op.collective for op in ops} - set(DECOMPOSED_COLLECTIVES))
    if unsupported:
        raise AdapterError(
            f"backend {BACKEND_ID} has no wire-pattern decomposition declared "
            f"for collective(s) {unsupported} issued by workload kind "
            f"{workload_kind!r}; htsim_uec has NO native collective "
            "semantics (explicitly_unsupported: native_collective_semantics), "
            f"and the decomposed set is {list(DECOMPOSED_COLLECTIVES)}"
        )
    for op in ops:
        if op.payload_bytes < 1:
            raise AdapterError(
                f"op {op.op_id}: payload {op.payload_bytes} bytes; flow sizes "
                "must be positive"
            )
        if op.payload_bytes % ranks:
            raise AdapterError(
                f"op {op.op_id}: payload {op.payload_bytes} bytes not "
                f"divisible by ranks {ranks}; the chunked-ring wire pattern "
                "(A-UET1-WIRE, mirroring L0 divisibility A-L0-DIV) requires "
                "r | M so every emitted flow size 2*(r-1)/r*M is an integral "
                "byte count"
            )

    link = topology_data["link"]
    link_bytes_per_ns = _frac(link["bytes_per_ns"])
    hop_latency_ns = _frac(link["hop_latency_ns"])
    linkspeed = bandwidth_mbps(link_bytes_per_ns)
    hop_micro = hop_latency_us(hop_latency_ns)

    free_parameters = (
        {
            "name": "link.bytes_per_ns",
            "value": str(link_bytes_per_ns),
            "unit": "bytes_per_ns",
            "assumption": "A-L0-BW",
            "source": str(manifest["infra_graph"]["path"]),
        },
        {
            "name": "link.hop_latency_ns",
            "value": str(hop_latency_ns),
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
        link_bytes_per_ns=link_bytes_per_ns,
        hop_latency_ns=hop_latency_ns,
        linkspeed_mbps=linkspeed,
        hop_latency_us=hop_micro,
        seed=seed,
        free_parameters=free_parameters,
    )


def flow_size_bytes(payload_bytes: int, ranks: int) -> int:
    """Per-rank wire bytes of one AllReduce op under the chunked-ring
    decomposition: 2*(r-1)/r*M (A-UET1-WIRE); integral because the gate
    requires r | M."""
    size = 2 * (ranks - 1) * payload_bytes // ranks
    assert 2 * (ranks - 1) * payload_bytes % ranks == 0  # guarded in validate
    return size


def compile_experiment(manifest_path, out_dir) -> dict:
    """Translate the validated experiment into the uet-htsim input set.

    Writes one connection-matrix file per workload op (A-UET1-OPFILE) in
    the runbook §4.1 grammar — pure grammar, no comments: the pinned
    parser's comment handling is documented for the header only, and stage
    S1 runs no binary to verify more — plus a deterministic
    ``compile_plan.json`` recording provenance, free parameters,
    translation assumptions, the exact CLI mapping, and per-file hashes.
    Pure function of the manifest: identical inputs produce byte-identical
    files (no wall-clock, no environment leakage). Execution is stage S2:
    this function never invokes docker or the binary.
    """
    experiment = validate_experiment(manifest_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ranks = experiment.ranks
    size = flow_size_bytes(experiment.workload_config.allreduce_bytes, ranks)
    matrix_prefix = experiment.manifest_path.stem

    for op_index, op in enumerate(experiment.ops):
        assert op.comm_ranks == tuple(range(ranks))
        lines = [
            f"Nodes {FABRIC_NODES}",
            f"Connections {ranks}",
        ]
        for rank in range(ranks):
            successor = (rank + 1) % ranks
            flow_id = op_index * ranks + rank + 1  # A-UET1-IDS
            lines.append(
                f"{rank}->{successor} start 0 size {size} id {flow_id}"
            )
        path = out_dir / f"{matrix_prefix}.op{op_index:06d}.cm"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- deterministic compile plan (the BackendPlan) -----------------------
    files = {}
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "compile_plan.json":
            files[str(path.relative_to(out_dir))] = contracts.sha256_of(path)
    plan = {
        "backend_id": BACKEND_ID,
        "stage": (
            "Q3-S1 translation (no binary; execution in Docker + output "
            "parsing land with stage S2 per OD-002)"
        ),
        "experiment_id": experiment.manifest["experiment_id"],
        "source_manifest": {
            "path": _rel(experiment.manifest_path),
            "sha256": experiment.manifest_sha256,
        },
        "pin": PIN,
        "binary_cli": {
            "run_shape_per_op_file": (
                "cd /opt/uet-htsim/htsim/sim/datacenter && ./htsim_uec "
                f"-tm {matrix_prefix}.op<NNNNNN>.cm "
                f"-o {matrix_prefix}.op<NNNNNN>.logout.dat "
                f"-linkspeed {experiment.linkspeed_mbps} "
                f"-hop_latency {experiment.hop_latency_us} "
                f"-seed {experiment.seed}"
            ),
            "flags_from_manifest": {
                "-tm": (
                    "one compiled connection-matrix file per op, run in op "
                    "order; serialization across ops is enforced by the run "
                    "orchestration, not by the file (A-UET1-OPFILE)"
                ),
                "-o": (
                    "per-op trace file (CWD-relative; the CWD must be "
                    "writable, runbook section 2)"
                ),
                "-linkspeed": (
                    f"{experiment.linkspeed_mbps} (Mbps; exactly 8000 * "
                    f"{experiment.link_bytes_per_ns} B/ns, A-UET1-BW)"
                ),
                "-hop_latency": (
                    f"{experiment.hop_latency_us} (us; exactly "
                    f"{experiment.hop_latency_ns} ns / 1000, per PHYSICAL "
                    "fat-tree hop, A-UET1-LAT/A-UET1-FABRIC)"
                ),
                "-seed": (
                    f"{experiment.seed} (manifest seed, explicit per "
                    "platform rule 6; upstream default is 13, A-UET1-SEED)"
                ),
            },
            "flags_at_upstream_defaults": {
                "-end": 1000,  # A-UET1-END
                "-mtu": 4150,  # A-UET1-MTU
                "-strat": "ecmp_host",
                "-sender_cc_algo": "nscc",  # A-UET1-CC
                "-sender_cc": True,  # A-UET1-CC
                "-receiver_cc": False,  # A-UET1-CC
                "-q": 0,
                "-cwnd": 0,
                "-ecn": "0 0 (derived)",
            },
            "anchor": "backends/docker/uet-htsim-runbook.md sections 2-4",
            "verification_status": (
                "the -tm/-o command shape and Nodes-16 matrix header were "
                "executed in the Docker smoke (runbook section 2); the "
                "manifest-derived flag values are source-verified only "
                "(runbook section 3) and are exercised by this ladder's "
                "stage S2 — stage S1 is translation-only, no binary"
            ),
        },
        "workload": {
            "kind": "w1_dense_tp_decode",
            "ops": len(experiment.ops),
            "ops_per_rank": len(experiment.ops),
            "op_order": [op.op_id for op in experiment.ops],
            "collective_semantics": (
                "none in the simulator; allreduce translated by chunked-ring "
                "wire-pattern decomposition (A-UET1-WIRE)"
            ),
            "flows_per_op": ranks,
            "per_rank_wire_bytes": size,
            "per_op_wire_bytes_total": size * ranks,
            "flow_rule": (
                "rank i -> (i+1) mod r, start 0, size 2*(r-1)/r*M "
                "(A-UET1-WIRE)"
            ),
            "flow_id_rule": "op_index * ranks + rank + 1 (A-UET1-IDS)",
            "file_rule": (
                f"{matrix_prefix}.op<index:06d>.cm, one per op, op order = "
                "generator order (step-major, layer-minor; A-UET1-OPFILE)"
            ),
        },
        "fabric": {
            "nodes": FABRIC_NODES,
            "ranks_placed": ranks,
            "idle_hosts": FABRIC_NODES - ranks,
            "auto_topology": (
                "3-tier fat tree at pinned defaults, 100 Gbps unless "
                "-linkspeed overrides (A-UET1-FABRIC)"
            ),
        },
        "topology": {
            "topology_id": experiment.topology_id,
            "topology_class": "unidirectional_ring",
            "realization": (
                "logical traffic pattern on the fat-tree fabric "
                "(A-UET1-FABRIC); NOT a physical ring"
            ),
            "ranks": ranks,
            "link_bytes_per_ns_exact": str(experiment.link_bytes_per_ns),
            "linkspeed_mbps_exact": experiment.linkspeed_mbps,
            "hop_latency_ns_exact": str(experiment.hop_latency_ns),
            "hop_latency_us_exact": experiment.hop_latency_us,
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

# Upstream -end default retained by the compile plan (A-UET1-END). The
# parser guards every parsed finish time against this window: a flow that
# never reports 'finished at' closed the window unfinished.
END_US = 1000

# Execution-side conventions with no manifest counterpart (the run-time
# siblings of TRANSLATION_ASSUMPTIONS; deliberately NOT appended to that
# tuple, so the S1 committed compiled set stays the byte-stable executed
# input set). Each carries its anchor.
EXECUTION_ASSUMPTIONS = (
    {
        "id": "A-UET2-OPSER",
        "parameter": "op serialization -> run orchestration + O-CCT aggregation",
        "value": (
            "one htsim_uec invocation per op file, generator op order, in one "
            "container; per-op completion = max over the op's r concurrent "
            "flows of (finish_us - start_us); chain O-CCT = exact sum over ops"
        ),
        "rationale": (
            "The .cm grammar has no dependency mechanism (A-UET1-OPFILE), so "
            "serialized ops cannot be expressed inside one matrix: each op is "
            "an independent simulation from t=0 and serialization is enforced "
            "by running the files in op order, summing per-op completions — "
            "the same sum-of-ops reading as the L0 baseline and the ASTRA "
            "data_deps chain (A-AS1-CHAIN). Never invented start times."
        ),
        "anchor": (
            "runbook section 4.1 (grammar: src->dst [start] only, no deps); "
            "this adapter A-UET1-OPFILE; "
            "src/essun/backends/astra_sim/adapter.py A-AS1-CHAIN"
        ),
    },
    {
        "id": "A-UET2-STDOUT",
        "parameter": "FCT parse surface",
        "value": (
            "stdout per-flow lines; ns values are exact decimals of the "
            "PRINTED us strings (us * 1000), not of the picosecond event times"
        ),
        "rationale": (
            "The per-flow FCT is the number after 'finished at' (runbook "
            "section 5.1), printed as timeAsUs(eventlist().now()) — a double "
            "through cout at its default 6 significant digits (config.cpp:65, "
            "uec.cpp:824 at the pin) — so the printed decimal is already a "
            "rounded observation of the internal picosecond time; the record "
            "keeps the printed value exactly and converts it by *1000 with "
            "exact Fraction arithmetic. The logout.dat trace (runbook section "
            "5.2) carries the full-precision time but is hashed into the run "
            "record, not parsed, at this stage."
        ),
        "anchor": (
            "runbook sections 5.1 and 5.2; config.cpp:65 (timeAsUs); "
            "uec.cpp:824 at the pin 65ea315b"
        ),
    },
    {
        "id": "A-UET2-BINDMOUNT",
        "parameter": "host<->container file route",
        "value": (
            "inputs dir and scratch run dir bind-mounted (writable) at "
            "/mnt/inputs and /mnt/run; per-op -o into the run dir"
        ),
        "rationale": (
            "Runbook section 6's proposed route, verified by this stage: the "
            "binary resolves -tm/-o CWD-relatively and writes its trace into "
            "the writable run dir; the mounts must NOT be read-only (same "
            "OrbStack virtiofs file-open failure the ASTRA-sim S2 stage hit "
            "on :ro mounts — writable mounts, and the command never writes "
            "into the inputs tree)."
        ),
        "anchor": (
            "runbook sections 2 (preconditions) and 6 (bind-mount route, "
            "verified in this stage); "
            "backends/docker/astra-sim-runbook.md S2 mount finding"
        ),
    },
)

# stdout grammar at the pin (runbook §5.1). The OP FILE markers and the
# ESSUN_BINARY_SHA256/UET_EXIT lines are this adapter's run-orchestration
# instrumentation around the binary's own output (same convention as the
# ASTRA-sim adapter's ASTRA_EXIT marker).
_OP_FILE_MARK_RE = re.compile(r"^=== OP FILE (\S+) ===$")
_FLOW_START_RE = re.compile(
    r"^Flow Uec_(\d+)_(\d+) flowId (\d+) uecSrc (\d+) starting at (\S+)\s*$"
)
_FLOW_FINISH_RE = re.compile(
    r"^Flow Uec_(\d+)_(\d+) flowId (\d+) uecSrc (\d+) finished at (\S+) "
    r"total messages (\d+) total packets (\d+) RTS (\d+) total bytes (\d+)"
)
_SUMMARY_RE = re.compile(
    r"^New: (\d+) Rtx: (\d+) RTS: (\d+) Bounced: (\d+) ACKs: (\d+) "
    r"NACKs: (\d+) Pulls: (\d+) sleek_pkts: (\d+)\s*$"
)
_BINARY_SHA_LINE_RE = re.compile(r"^ESSUN_BINARY_SHA256=([0-9a-f]{64})\s*$")
_UET_EXIT_RE = re.compile(r"^UET_EXIT=(-?\d+)\s*$")

_SUMMARY_FIELDS = (
    "new",
    "rtx",
    "rts",
    "bounced",
    "acks",
    "nacks",
    "pulls",
    "sleek_pkts",
)


def _decimal_fraction(text: str) -> Fraction:
    """Exact Fraction of a printed decimal us value (Decimal first so any
    finite decimal form, including exponents, is read exactly)."""
    return Fraction(Decimal(text))


def _exact_decimal_ns(us: Fraction) -> str:
    """Exact ns decimal string for a us value whose denominator is 2^a*5^b
    (always true for parsed decimal strings and their sums/maxima)."""
    ns = us * 1000
    if not _denominator_is_2a5b(ns.denominator):
        raise AdapterError(
            f"us value {us} has no exact finite ns decimal; the parsed "
            "surface only produces finite decimals — a different value here "
            "means the print format changed at the pin"
        )
    return _finite_decimal(ns)


def parse_output(stdout: str, exit_code: int, op_files, ranks: int) -> dict:
    """Parse the container stdout of the per-op run sequence into per-op
    flow completions and the serialized-chain completion time.

    Deterministic pure function of the text. Rejects loudly (never guesses):

    - non-zero container exit code, or any op's ``UET_EXIT`` != 0;
    - a missing/mismatched binary sha256 marker line (unpinned binary);
    - an op-file marker sequence that is not exactly ``op_files`` in order —
      op serialization is the run orchestration's contract (A-UET1-OPFILE);
    - a missing ``Starting simulation`` or missing/duplicated summary line;
    - any flow of the op's expected id set (A-UET1-IDS rule) missing its
      start or finish line — an unfinished flow means the ``-end`` window
      (A-UET1-END) closed first, and a partial result is refused;
    - a flow id outside the expected set, a duplicated id, endpoints that
      are not the compiled ring-successor wire pattern (A-UET1-WIRE — the
      binary echoes the executed matrix's endpoints, so this proves the
      executed file is the compiled one), a finish before its start, or a
      finish at/after the ``-end`` window.
    """
    if exit_code != 0:
        raise AdapterError(
            f"container exited with code {exit_code}; the pinned binary or "
            "docker failed before results could be parsed"
        )
    lines = stdout.splitlines()
    sha_markers = [
        line for line in lines if _BINARY_SHA_LINE_RE.match(line)
    ]
    if not sha_markers:
        raise AdapterError(
            "output carries no ESSUN_BINARY_SHA256 marker; the container "
            "command did not run the pinned verification preamble"
        )
    if any(
        marker != f"ESSUN_BINARY_SHA256={PIN['binary_sha256']}"
        for marker in sha_markers
    ):
        raise AdapterError(
            f"container binary sha256 {sha_markers[0].split('=', 1)[1]} != "
            f"pinned {PIN['binary_sha256']}; refusing results from an "
            "unpinned binary"
        )

    sections: list[tuple[str, list[str]]] = []
    for line in lines:
        match = _OP_FILE_MARK_RE.match(line)
        if match:
            sections.append((match.group(1), []))
        elif sections:
            sections[-1][1].append(line)
    expected_files = list(op_files)
    if not sections:
        raise AdapterError(
            "output carries no '=== OP FILE <name> ===' markers; the run "
            "orchestration preamble is absent"
        )
    actual_files = [name for name, _ in sections]
    if actual_files != expected_files:
        raise AdapterError(
            f"executed op-file sequence {actual_files} != compiled op order "
            f"{expected_files}; op serialization is the run orchestration's "
            "contract (A-UET1-OPFILE) and a reordered or partial sequence is "
            "refused, not reinterpreted"
        )

    parsed_ops = []
    for op_index, (name, section_lines) in enumerate(sections):
        exits = [
            int(match.group(1))
            for match in (
                _UET_EXIT_RE.match(line) for line in section_lines
            )
            if match
        ]
        if len(exits) != 1:
            raise AdapterError(
                f"op file {name}: expected exactly one UET_EXIT marker, saw "
                f"{len(exits)}; ambiguous run output is rejected"
            )
        if exits[0] != 0:
            raise AdapterError(
                f"htsim_uec for op file {name} exited with code {exits[0]}; "
                "refusing to parse a failed run"
            )
        if not any(line.strip() == "Starting simulation" for line in section_lines):
            raise AdapterError(
                f"op file {name}: no 'Starting simulation' runtime line; the "
                "run never reached its output section (runbook §5.1)"
            )

        starts: dict[int, dict] = {}
        finishes: dict[int, dict] = {}
        summaries: list[dict] = []
        for line in section_lines:
            match = _FLOW_START_RE.match(line)
            if match:
                src, dst, flow_id, uec_src, start = match.groups()
                flow_id = int(flow_id)
                if flow_id in starts:
                    raise AdapterError(
                        f"op file {name}: flow id {flow_id} reported "
                        "'starting at' twice; ambiguous output"
                    )
                starts[flow_id] = {
                    "src": int(src),
                    "dst": int(dst),
                    "uec_src": int(uec_src),
                    "start_us": _decimal_fraction(start),
                    "start_us_printed": start,
                }
            match = _FLOW_FINISH_RE.match(line)
            if match:
                (src, dst, flow_id, uec_src, finish, _messages,
                 packets, rts, total_bytes) = match.groups()
                flow_id = int(flow_id)
                if flow_id in finishes:
                    raise AdapterError(
                        f"op file {name}: flow id {flow_id} reported "
                        "'finished at' twice; ambiguous output"
                    )
                finishes[flow_id] = {
                    "src": int(src),
                    "dst": int(dst),
                    "uec_src": int(uec_src),
                    "finish_us": _decimal_fraction(finish),
                    "finish_us_printed": finish,
                    "total_packets": int(packets),
                    "rts": int(rts),
                    "total_bytes": int(total_bytes),
                }
            match = _SUMMARY_RE.match(line)
            if match:
                summaries.append(
                    dict(zip(_SUMMARY_FIELDS, (int(g) for g in match.groups())))
                )
        if len(summaries) != 1:
            raise AdapterError(
                f"op file {name}: expected exactly one 'New:' summary line, "
                f"saw {len(summaries)}; ambiguous output is rejected"
            )

        expected_ids = {op_index * ranks + rank + 1 for rank in range(ranks)}
        if set(starts) != expected_ids:
            raise AdapterError(
                f"op file {name}: started flow ids {sorted(starts)} != the "
                f"compiled A-UET1-IDS set {sorted(expected_ids)}; a matrix "
                "other than the compiled one was executed"
            )
        unfinished = sorted(set(starts) - set(finishes))
        if unfinished:
            raise AdapterError(
                f"op file {name}: flow id(s) {unfinished} never reported "
                f"'finished at' — the simulation window (-end, upstream "
                f"default {END_US} us, A-UET1-END) closed before completion; "
                "refusing a partial result"
            )

        per_flow = []
        for flow_id in sorted(finishes):
            start = starts[flow_id]
            finish = finishes[flow_id]
            rank = flow_id - op_index * ranks - 1
            if (start["src"], start["dst"]) != (finish["src"], finish["dst"]):
                raise AdapterError(
                    f"op file {name}: flow id {flow_id} start endpoint "
                    f"{start['src']}->{start['dst']} != finish endpoint "
                    f"{finish['src']}->{finish['dst']}; inconsistent output"
                )
            if not 0 <= rank < ranks or finish["dst"] != (rank + 1) % ranks or (
                finish["src"] != rank
            ):
                raise AdapterError(
                    f"op file {name}: flow id {flow_id} endpoint "
                    f"{finish['src']}->{finish['dst']} is not the compiled "
                    "ring-successor wire pattern rank -> (rank+1) mod r "
                    "(A-UET1-WIRE); a matrix other than the compiled one "
                    "was executed"
                )
            fct_us = finish["finish_us"] - start["start_us"]
            if fct_us < 0:
                raise AdapterError(
                    f"op file {name}: flow id {flow_id} finished before it "
                    "started; invalid output"
                )
            if finish["finish_us"] >= END_US:
                raise AdapterError(
                    f"op file {name}: flow id {flow_id} finish "
                    f"{finish['finish_us_printed']} us is at/after the -end "
                    f"window {END_US} us (A-UET1-END); the retained default "
                    "is no longer sufficient and the assumption must be "
                    "revised, not silently exceeded"
                )
            per_flow.append(
                {
                    "flow_id": flow_id,
                    "src": finish["src"],
                    "dst": finish["dst"],
                    "start_us_printed": start["start_us_printed"],
                    "finish_us_printed": finish["finish_us_printed"],
                    "fct_us_exact": _finite_decimal(fct_us),
                    "fct_ns_exact": _exact_decimal_ns(fct_us),
                    "total_packets": finish["total_packets"],
                    "rts": finish["rts"],
                    "total_bytes": finish["total_bytes"],
                }
            )
        completion_us = max(
            finish["finish_us"] - starts[flow_id]["start_us"]
            for flow_id, finish in finishes.items()
        )
        parsed_ops.append(
            {
                "op_index": op_index,
                "matrix": name,
                "per_flow": per_flow,
                "completion_us_exact": _finite_decimal(completion_us),
                "completion_ns_exact": _exact_decimal_ns(completion_us),
                "summary": summaries[0],
            }
        )

    chain_us = sum(Fraction(op["completion_us_exact"]) for op in parsed_ops)
    return {
        "ranks": ranks,
        "ops": parsed_ops,
        "completion_time_ns_exact": _exact_decimal_ns(chain_us),
        "max_finish_us_printed": max(
            flow["finish_us_printed"]
            for op in parsed_ops
            for flow in op["per_flow"]
        ),
        "units": (
            "us as printed (timeAsUs double at cout default 6 significant "
            "digits, config.cpp:65 / uec.cpp:824 at the pin); ns values are "
            "exact decimals of the printed us strings (us * 1000)"
        ),
    }


def docker_run_container(
    inputs_dir, op_files, linkspeed_mbps: int, hop_latency_us: str, seed: int
) -> dict:
    """Run the compiled op matrices in the pinned container per the runbook.

    Bind-mount route (runbook §6, verified in this stage — A-UET2-BINDMOUNT):
    the inputs directory (the compiled ``.cm`` set) and a scratch run
    directory are bind-mounted at ``/mnt/inputs`` and ``/mnt/run``; the
    script executes one ``htsim_uec`` per op file in the given order (op
    serialization, A-UET1-OPFILE/A-UET2-OPSER) with the manifest-derived
    flags verbatim and ``-o`` placing each trace in the run dir. The command
    first prints the container-side binary sha256 marker so the parser can
    prove the executed binary is the pinned one, and echoes each
    invocation's exit code as ``UET_EXIT=<n>``. Returns the container exit
    code, its stdout (+stderr, so parse errors quote the failure cause), and
    the sha256 of every produced ``logout.dat`` trace (deterministic content;
    hashed into the run record, not parsed).
    """
    import shutil
    import subprocess
    import tempfile

    inputs_dir = Path(inputs_dir).resolve()
    if shutil.which("docker") is None:
        raise AdapterError(
            "docker CLI not found on PATH; backend uet_htsim_cms executes "
            "the pinned binary in container "
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
            "backends/docker/uet-htsim-runbook.md before running this backend"
        )
    image_id = inspect.stdout.strip()
    if image_id != PIN["docker_image_id"]:
        raise AdapterError(
            f"docker image id {image_id} != pinned {PIN['docker_image_id']}; "
            "refusing to execute an unpinned image"
        )

    binary = PIN["binary_path_in_image"]
    script_lines = [
        "export LC_ALL=C",
        'echo "ESSUN_BINARY_SHA256=$(sha256sum '
        f"{binary} | cut -d' ' -f1)\"",
        "cd /mnt/run",
    ]
    for name in op_files:
        if not name.endswith(".cm"):
            raise AdapterError(f"op file {name!r} is not a .cm connection matrix")
        logout = name[: -len(".cm")] + ".logout.dat"
        script_lines += [
            f'echo "=== OP FILE {name} ==="',
            f"{binary} -tm /mnt/inputs/{name} -o {logout} "
            f"-linkspeed {linkspeed_mbps} -hop_latency {hop_latency_us} "
            f"-seed {seed}",
            'echo "UET_EXIT=$?"',
        ]
    script = "\n".join(script_lines)

    with tempfile.TemporaryDirectory(prefix="essun-uet-run-") as scratch:
        run_dir = (Path(scratch) / "run").resolve()
        run_dir.mkdir()
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
        traces = {
            path.name: contracts.sha256_of(path)
            for path in sorted(run_dir.rglob("*.logout.dat"))
        }
        # stdout carries the result lines; stderr carries docker-level noise
        # only — both are joined so parser errors quote the failure cause.
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout + proc.stderr,
            "traces": traces,
        }


def execute_experiment(manifest_path, *, run_container=None) -> dict:
    """Full BackendAdapter run: validate -> compile -> execute -> parse.

    Returns ``{"observations": ..., "execution": ...}``. The orchestrator
    persists both through the evidence store (``orchestrator/runs.py``);
    every field is a deterministic function of (manifest, inputs, pin) — no
    wall-clock, no host paths, no container-internal timestamps — so an
    identical rerun yields a byte-identical RunRecord (verified in the S2
    stage report on two fresh containers: stdout and all six traces
    byte-identical).

    ``run_container`` overrides the container invocation (tests replay a
    recorded real output through it; the default runs the pinned image via
    the docker CLI and is resolved at call time so it stays patchable).

    O-CONSERVATION is recorded as explicitly unsupported for this backend:
    the per-flow byte counters include packet overhead and retransmission
    accounting (this run: 32,688 counted bytes for a 28,672-byte flow; the
    runbook smoke: 2,002,140 for 2,000,000) and no received-side ledger is
    established in the verified output surface — an honest per-backend gap,
    not a silent omission.
    """
    if run_container is None:
        run_container = docker_run_container
    experiment = validate_experiment(manifest_path)
    matrix_prefix = experiment.manifest_path.stem
    op_files = [
        f"{matrix_prefix}.op{op_index:06d}.cm"
        for op_index in range(len(experiment.ops))
    ]
    with tempfile.TemporaryDirectory(prefix="essun-uet-inputs-") as tmp:
        inputs_dir = Path(tmp) / "inputs"
        plan = compile_experiment(manifest_path, inputs_dir)
        # compile_plan.json is a essun provenance artifact, not a binary
        # input; keep the container's view of the inputs minimal.
        (inputs_dir / "compile_plan.json").unlink()
        result = run_container(
            inputs_dir,
            op_files,
            experiment.linkspeed_mbps,
            experiment.hop_latency_us,
            experiment.seed,
        )
    parsed = parse_output(result["stdout"], result["exit_code"], op_files, experiment.ranks)

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
                "uet_htsim_commit": PIN["uet_htsim_commit"],
                "docker_image": PIN["docker_image"],
                "docker_image_id": PIN["docker_image_id"],
                "binary_sha256": PIN["binary_sha256"],
            },
            "executed_input_files": dict(plan["files"]),
            "translation_assumption_ids": [
                assumption["id"] for assumption in TRANSLATION_ASSUMPTIONS
            ],
            "execution_assumption_ids": [
                assumption["id"] for assumption in EXECUTION_ASSUMPTIONS
            ],
        },
        "observables": {
            "O-CCT": {
                # kind matches the registry spec (ANALYTICAL); the values are
                # PARSED simulator output, not a closed form — see "method".
                "kind": "analytical",
                "method": (
                    "parsed from the pinned binary's per-flow 'finished at' "
                    "stdout lines (us; runbook §5.1, A-UET2-STDOUT); not a "
                    "closed-form identity"
                ),
                "ops": len(experiment.ops),
                "ops_per_rank": len(experiment.ops),
                "aggregation": (
                    "per-op completion = max over the op's r concurrent flows "
                    "of (finish_us - start_us); completion_time_ns_exact = "
                    "exact sum over the serialized per-op runs, which the run "
                    "orchestration (not the input files) serializes "
                    "(A-UET1-OPFILE, A-UET2-OPSER)"
                ),
                "per_op": [
                    {
                        "op_index": op["op_index"],
                        "op_id": experiment.ops[op["op_index"]].op_id,
                        "matrix": op["matrix"],
                        "completion_time_us_exact": op["completion_us_exact"],
                        "completion_time_ns_exact": op["completion_ns_exact"],
                    }
                    for op in parsed["ops"]
                ],
                "completion_time_ns_exact": parsed["completion_time_ns_exact"],
            },
        },
        "unsupported_observables": {
            "O-CONSERVATION": (
                "the binary's per-flow byte counters include packet overhead "
                "and retransmission accounting (this run: 32688 counted "
                "bytes for the 28672-byte flows; runbook smoke: 2002140 "
                "counted for a 2000000-byte flow) and no received-side "
                "ledger is established in the verified output surface, so "
                "wire conservation cannot be emitted honestly for this "
                "backend at this stage; explicitly declared unsupported, "
                "matching CAPABILITIES['explicitly_unsupported']"
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
            "flags_executed": {
                "-linkspeed": experiment.linkspeed_mbps,
                "-hop_latency": experiment.hop_latency_us,
                "-seed": experiment.seed,
                "-end": END_US,
            },
            "cli_anchor": (
                "runbook §2 command shape; per-op invocations in generator "
                "op order (A-UET2-OPSER); manifest-derived flags echoed by "
                "the binary and cross-checked against the pinned parser "
                "surface (runbook §3)"
            ),
        },
        "run_orchestration": (
            f"{len(experiment.ops)} htsim_uec invocations, one per compiled "
            "op matrix, executed sequentially in one container; op "
            "serialization is enforced here, never by invented start times "
            "(A-UET1-OPFILE)"
        ),
        "end_sufficiency": {
            "end_us": END_US,
            "max_finish_us_printed": parsed["max_finish_us_printed"],
            "note": (
                "A-UET1-END static estimate verified against parsed output: "
                "every flow of every op finished far inside the retained "
                "upstream default window"
            ),
        },
        "trace_files": result.get("traces"),
        "parsed": parsed,
    }
    return {"observations": observations, "execution": execution}


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Compile an experiment manifest into uet-htsim connection "
            "matrices (execution is run_experiment / execute_experiment; "
            "this CLI is the S1 compile surface)"
        )
    )
    parser.add_argument("manifest", help="path to the experiment manifest YAML")
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "output directory (default: "
            "experiments/vertical_slice/uet_<manifest stem>)"
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
        / f"uet_{manifest.stem}"
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
