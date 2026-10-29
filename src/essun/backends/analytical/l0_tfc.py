"""Analytical L0-TFC backend: ring AllReduce under a UEC TFC credit window.

Flagship slice of the D1 disposition ladder (design-integration doc
2026-10-29, build order item 2): ONE externally relevant UEC semantic
requirement executed end-to-end as an honest ``simulated_behavior``.

The requirement is **UEC11-FC-R02** (UEC 1.1 section 3.6.15, Transport
Flow Control, keyword MUST NOT): *"a source must not transmit a packet if
it does not have credit — the admission law of the whole TFC mechanism."*
The machine-readable binding lives in
:mod:`essun.specir.bindings` (binding id ``BIND-UEC11-FC-R02-L0TFC``).

Decision relevance (why this requirement and not another): TFC is UEC's
end-to-end flow control — the amount of data a source may have in flight
toward a destination is exactly the credit the destination granted. A
fabric architect provisioning a UEC deployment must decide how much credit
(each credit unit is 256 destination-buffer bytes, UEC11-FC-R05) to grant
per flow; granting less than the bandwidth-delay product throttles every
large transfer below line rate, granting more spends receive buffering.
The model turns that trade-off into an exact closed-form identity, so the
platform answers "what does my credit window cost my AllReduce?" with
arithmetic, not assertion.

Identity. Same fabric and chunked equal-chunk ring schedule as the landed
L0 ring model (:mod:`essun.backends.analytical.l0`): unidirectional ring,
AllReduce = ReduceScatter + AllGather, per-rank wire traffic unchanged.
On top of it, every ring neighbor pair carries a TFC credit context of
``W`` granted bytes; the admission law caps each source's steady-state
sending rate at one window per credit round trip:

    chunk size           c   = M / r                    [c integral: r | M]
    wire traffic/rank    T   = 2 * (r - 1) / r * M       [same as L0]
    credit round trip    RTT = L + L_cr
    admission rate cap   Rmax= W / RTT                   [UEC11-FC-R02]
    effective link rate  Reff= min(B, Rmax)
    AllReduce time       t   = T / Reff + 2 * (r - 1) * L

Reading of the rate cap (the binding's semantics, stated exactly so a
challenger can attack it): a source that may never exceed ``W`` in-flight
bytes cannot sustain more than one full window per credit round trip, and
credit cannot return faster than one round trip of the credit loop (data
forward one hop ``L`` + credit return ``L_cr``); hence ``W / (L + L_cr)``.
When the window covers at least the bandwidth-delay product
``W >= B * (L + L_cr)``, credits never gate and the identity reduces to
the landed L0 ring equation EXACTLY (``Reff = B``; pinned by tests as the
convergence anchor, same discipline as the L0.5 I->infinity anchor).
The admission law is enforced structurally, not checked after the fact:
the completion-time identity is BUILT from ``Reff = min(B, W/RTT)``, and
:func:`admission_invariant` states the in-flight bound
``Reff * RTT <= W`` as an exact-Fraction identity the model re-derives
for every run.

Scope honestly NOT simulated (declared unsupported below): the credit
REQUEST/grant protocol dynamics (a steady granted window is the modeled
abstraction — the source always holds exactly W reusable credit), TFC
retransmission exemptions (UEC11-FC-R06), per-PDC vs shared-CCC credit
pooling (FC-R16), cell-size and packet-overhead accounting (FC-R07..R10),
CBFC hop-level credits (section 5.2), RCCC receiver-driven credit
scheduling across MULTIPLE concurrent sources (3.6.14 — needs contention,
which no analytical backend executes), congestion, packetization/FLIT
effects, fill/drain start-up transients (same exclusion class as the L0
family), and overlapping collectives.

The credit UNIT is the only standard-derived constant in this module:
256 bytes per credit unit (UEC11-FC-R05, anchor ``UEC11-S3.6.15-TFC``).
By the provenance rule it is carried as a named constant citing its
requirement, never invented. Everything else — B, L, W, L_cr — is a FREE
parameter registered in ``experiments/vertical_slice/assumptions_tfc.yaml``
(not standard-derived, not measured). The window W must be an integral
number of credit units; a non-multiple-of-256 window is REJECTED at load
time with the requirement citation — the spec's credit granularity is a
binding semantic, not a convention.

Wire traffic is UNCHANGED from L0 (a window gates rate, it moves no
bytes), so O-CONSERVATION is the same ALGEBRAIC SELF-CHECK of the model's
own byte accounting as in L0 (O6 honesty label: not a physical
measurement). O-CCT is analytical (identity-cited).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from fractions import Fraction

from essun.backends.analytical.l0 import (
    ring_traffic_per_rank,
    require_divisible,
)

BACKEND_ID = "analytical_l0_tfc"

# Distinct from "unidirectional_ring" so no landed backend can silently
# load a TFC topology (l0.load_infra would ignore the tfc block); the
# loader here checks the class explicitly (same discipline as L0.5).
TOPOLOGY_CLASS = "unidirectional_ring_tfc_window"

#: Credit unit: 256 bytes per credit unit (UEC 1.1 §3.6.15, one pds.credit
#: bit == 256 destination bytes). Standard-derived via requirement
#: UEC11-FC-R05, anchor UEC11-S3.6.15-TFC — the ONLY spec-derived value in
#: this module (provenance rule; see essun.specir.bindings).
TFC_CREDIT_UNIT_BYTES = 256

#: The binding id this backend executes (essun.specir.bindings).
BINDING_ID = "BIND-UEC11-FC-R02-L0TFC"
REQUIREMENT_ID = "UEC11-FC-R02"
CREDIT_UNIT_REQUIREMENT_ID = "UEC11-FC-R05"

CAPABILITIES = {
    "backend_id": BACKEND_ID,
    "fidelity": "L0.5",
    "collectives": ("allreduce_ring",),
    "transport_model": "tfc_credit_windowed_ring",
    "observables": ("O-CONSERVATION", "O-CCT"),
    "explicitly_unsupported": (
        "congestion",
        "credit_request_grant_dynamics",  # steady granted window W is the abstraction
        "tfc_retransmission_credit_exempt",  # UEC11-FC-R06
        "shared_ccc_credit_pooling",  # UEC11-FC-R16
        "tfc_cell_size_overhead_accounting",  # UEC11-FC-R07..R10
        "cbfc_link_credits",  # UEC §5.2 hop-level flow control
        "rccc_multi_source_credit_scheduling",  # UEC §3.6.14
        "packetization_flit_effects",
        "in_network_computing",
        "overlapping_collectives",
        "fill_drain_startup_transients",
    ),
}


@dataclass(frozen=True)
class TFCRingConfig:
    topology_id: str
    ranks: int
    link_bytes_per_ns: Fraction
    hop_latency_ns: Fraction
    tfc_window_bytes: Fraction
    tfc_credit_return_latency_ns: Fraction


def load_tfc_config(data: dict) -> TFCRingConfig:
    def frac(value) -> Fraction:
        # str() first so YAML decimals are interpreted exactly, not via float.
        return Fraction(str(value))

    link = data["link"]
    tfc = data["tfc"]
    config = TFCRingConfig(
        topology_id=str(data["topology_id"]),
        ranks=int(data["ranks"]),
        link_bytes_per_ns=frac(link["bytes_per_ns"]),
        hop_latency_ns=frac(link["hop_latency_ns"]),
        tfc_window_bytes=frac(tfc["window_bytes"]),
        tfc_credit_return_latency_ns=frac(tfc["credit_return_latency_ns"]),
    )
    if config.link_bytes_per_ns <= 0:
        raise ValueError(
            f"{BACKEND_ID}: link.bytes_per_ns must be > 0 "
            f"(got {config.link_bytes_per_ns})"
        )
    if config.hop_latency_ns < 0:
        raise ValueError(
            f"{BACKEND_ID}: link.hop_latency_ns must be >= 0 "
            f"(got {config.hop_latency_ns})"
        )
    if config.tfc_credit_return_latency_ns < 0:
        raise ValueError(
            f"{BACKEND_ID}: tfc.credit_return_latency_ns must be >= 0 "
            f"(got {config.tfc_credit_return_latency_ns})"
        )
    if config.tfc_window_bytes <= 0:
        raise ValueError(
            f"{BACKEND_ID}: tfc.window_bytes must be > 0 "
            f"(got {config.tfc_window_bytes})"
        )
    if config.tfc_window_bytes % TFC_CREDIT_UNIT_BYTES != 0:
        # UEC11-FC-R05 (§3.6.15): credit is granted in 256-byte units —
        # one pds.credit bit == 256 destination bytes. A window that is
        # not an integral number of credit units is not a grantable TFC
        # window, so the binding rejects it at load time.
        raise ValueError(
            f"{BACKEND_ID}: tfc.window_bytes {config.tfc_window_bytes} is "
            f"not a multiple of the {TFC_CREDIT_UNIT_BYTES}-byte credit "
            f"unit (UEC11-FC-R05, UEC 1.1 §3.6.15: one pds.credit bit "
            "grants 256 bytes); the TFC admission-law binding only "
            "executes grantable windows"
        )
    return config


def credit_rtt_ns(infra: TFCRingConfig) -> Fraction:
    """One round trip of the credit loop: data forward one hop + credit
    return. Free parameters both (A-TFC-LAT, A-TFC-CR)."""
    return infra.hop_latency_ns + infra.tfc_credit_return_latency_ns


def admission_rate_cap(infra: TFCRingConfig) -> Fraction:
    """UEC11-FC-R02 as a rate law: a source that may never exceed W
    in-flight bytes sustains at most one window per credit round trip."""
    return infra.tfc_window_bytes / credit_rtt_ns(infra)


def effective_rate(infra: TFCRingConfig) -> Fraction:
    """Per-link effective rate: min(link bandwidth, admission rate cap)."""
    return min(infra.link_bytes_per_ns, admission_rate_cap(infra))


def admission_invariant(infra: TFCRingConfig) -> Fraction:
    """Exact in-flight bound implied by the admission law:
    Reff * RTT <= W (with equality iff window-limited). Structural
    consequence of UEC11-FC-R02 — no bytes above the granted window are
    ever in flight in this identity."""
    return effective_rate(infra) * credit_rtt_ns(infra)


def bandwidth_delay_product(infra: TFCRingConfig) -> Fraction:
    """BDP = B * RTT: the window at and above which credits never gate."""
    return infra.link_bytes_per_ns * credit_rtt_ns(infra)


def ring_allreduce_time_tfc_ns(
    message_bytes: int, ranks: int, infra: TFCRingConfig
) -> Fraction:
    traffic = ring_traffic_per_rank(message_bytes, ranks)
    return traffic / effective_rate(infra) + 2 * (ranks - 1) * infra.hop_latency_ns


def execute(ops, infra: TFCRingConfig) -> dict:
    """Execute AllReduce ops on the TFC-windowed ring and emit observations.

    O-CONSERVATION (exact): identical ledger to L0 — the window gates
    rate, never byte count; per op total wire bytes are 2*(r-1)*M exactly.

    O-CCT (analytical): per-op completion under the window identity, mean
    and max aggregates, exact Fractions serialized alongside floats, plus
    the binding provenance block (requirement id, window, credit RTT,
    BDP, effective rate, regime flag) so every stored run names the
    requirement disposition it exercised.
    """
    rtt = credit_rtt_ns(infra)
    rate = effective_rate(infra)
    cap = admission_rate_cap(infra)
    bdp = bandwidth_delay_product(infra)
    # Structural admission check (UEC11-FC-R02): exact identity, a
    # violation would be a model bug, not a tunable outcome.
    in_flight = admission_invariant(infra)
    if not (in_flight <= infra.tfc_window_bytes):
        raise AssertionError(
            f"{BACKEND_ID}: admission invariant Reff*RTT={in_flight} exceeds "
            f"window W={infra.tfc_window_bytes} (UEC11-FC-R02 violated; "
            "this is a model bug, not a tunable parameter)"
        )

    per_op = []
    times: list[Fraction] = []
    total_wire = Fraction(0)
    violations: list[str] = []

    for op in ops:
        if op.collective != "allreduce":
            raise ValueError(
                f"{BACKEND_ID} capability: collective {op.collective!r} not "
                f"supported (op {op.op_id})"
            )
        if len(op.comm_ranks) != infra.ranks:
            raise ValueError(
                f"op {op.op_id}: comm group size {len(op.comm_ranks)} != "
                f"topology ranks {infra.ranks}"
            )
        require_divisible(
            BACKEND_ID, op.op_id, op.payload_bytes, infra.ranks, "A-TFC-DIV"
        )
        per_rank = ring_traffic_per_rank(op.payload_bytes, infra.ranks)
        op_wire = per_rank * infra.ranks  # == 2*(r-1)*M exactly
        expected_wire = Fraction(2 * (infra.ranks - 1) * op.payload_bytes)
        if op_wire != expected_wire:
            violations.append(op.op_id)
        completion = ring_allreduce_time_tfc_ns(
            op.payload_bytes, infra.ranks, infra
        )
        times.append(completion)
        total_wire += op_wire
        per_op.append(
            {
                "op_id": op.op_id,
                "payload_bytes": op.payload_bytes,
                "per_rank_wire_bytes_exact": str(per_rank),
                "total_wire_bytes_exact": str(op_wire),
                "completion_time_ns_exact": str(completion),
                "completion_time_ns": float(completion),
            }
        )

    if violations:
        raise AssertionError(
            f"O-CONSERVATION violated for ops {violations}; this is a model "
            "bug, not a tunable parameter"
        )

    mean_time = (
        sum(times, start=Fraction(0)) / len(times) if times else Fraction(0)
    )
    count = len(per_op)
    return {
        "backend": {
            "backend_id": BACKEND_ID,
            "fidelity": CAPABILITIES["fidelity"],
            "transport_model": CAPABILITIES["transport_model"],
            "topology_id": infra.topology_id,
            "ranks": infra.ranks,
            "link_bytes_per_ns_exact": str(infra.link_bytes_per_ns),
            "hop_latency_ns_exact": str(infra.hop_latency_ns),
            "tfc_window_bytes_exact": str(infra.tfc_window_bytes),
            "tfc_credit_return_latency_ns_exact": str(
                infra.tfc_credit_return_latency_ns
            ),
            "tfc_credit_unit_bytes": TFC_CREDIT_UNIT_BYTES,
            "tfc_credit_units_exact": str(
                infra.tfc_window_bytes / TFC_CREDIT_UNIT_BYTES
            ),
        },
        "requirement_bindings": [
            {
                "binding_id": BINDING_ID,
                "requirement_id": REQUIREMENT_ID,
                "disposition": "simulated_behavior",
                "credit_unit_requirement_id": CREDIT_UNIT_REQUIREMENT_ID,
            }
        ],
        "observables": {
            "O-CONSERVATION": {
                "kind": "exact",
                "ops_checked": count,
                "violations": 0,
                "total_wire_bytes_exact": str(total_wire),
            },
            "O-CCT": {
                "kind": "analytical",
                "ops": count,
                "completion_time_ns_mean_exact": str(mean_time),
                "completion_time_ns_mean": float(mean_time),
                "completion_time_ns_max": float(max(times)) if times else None,
                "tfc": {
                    "requirement_id": REQUIREMENT_ID,
                    "binding_id": BINDING_ID,
                    "window_bytes_exact": str(infra.tfc_window_bytes),
                    "credit_unit_bytes": TFC_CREDIT_UNIT_BYTES,
                    "credit_rtt_ns_exact": str(rtt),
                    "admission_rate_cap_bytes_per_ns_exact": str(cap),
                    "effective_rate_bytes_per_ns_exact": str(rate),
                    "bandwidth_delay_product_bytes_exact": str(bdp),
                    "peak_in_flight_bytes_exact": str(in_flight),
                    "window_limited": bool(cap < infra.link_bytes_per_ns),
                },
            },
        },
    }


# Loader/executor parity for the orchestrator's DISPATCH table: the
# config fields the binding's parameters name (checked at import by
# essun.specir.bindings via config_field_names()).
def config_field_names() -> tuple[str, ...]:
    return tuple(f.name for f in fields(TFCRingConfig))
