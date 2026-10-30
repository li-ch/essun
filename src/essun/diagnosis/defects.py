"""Synthetic ground-truth defect carriers (G9 leg 3) — measure, never ship.

Four seeded semantic defects, each a small wrapper around a REAL essun
engine, each carrying recorded ground truth (what was seeded, the expected
classification under :mod:`essun.diagnosis.classify`'s taxonomy, and the
exact reason). The harness runs every defect through the SAME pipeline as
a real disagreement — probe -> minimize -> exact form attribution ->
classify — and reports detection and classification HONESTLY: a missed
defect is a finding about the diagnosis engine, reported as such, never
hidden.

The defect engines are deliberately SILENT: each claims the clean
engine's declarations (that is what makes it a defect rather than a
declared variant). They are NOT orchestrator backends, are NOT registered
in ``orchestrator.runs.BACKENDS``, and their outputs NEVER enter the
evidence store as run records — they are diagnostic probes of this
module's own machinery.

Ground truth table (expected labels, with the normative reasoning):

=========================  ==========================================
defect                     expected classification
=========================  ==========================================
``floor_not_roundup_``     specification_violation — the executed
``credit_consumption``     form contradicts UEC11-FC-R08 (ROUNDUP is a
                           MUST-level law the carrier binds), exactly
                           the FLOOR form instead.
``drain_batched_credit_``  permitted_implementation_variation —
``return``                 returns deferred to whole-window batches
                           still satisfy the admission law
                           UEC11-FC-R02 (sliding-window bound holds on
                           the defect's own admission trace, checked
                           mechanically); return timing is not pinned
                           by any bound requirement. The divergence is
                           real, quantified, and STAYS VISIBLE.
``ignored_gb_unit_``       translation_defect — the carrier executes
``conversion``             the manifest's declared GB/s value (1 GB =
                           2^30 B convention, the A-AS1-BW-UNIT
                           analogue) as if it were already B/ns; the
                           executed case is not the declared case.
``latency_omitted_``       specification_violation — the carrier drops
``after_first_op``         the declared 2(r-1)L term for every op
                           after the first, contradicting the L0 ring
                           identity (A-L0-LAT applies per op); the
                           minimizer must certify the reproducer
                           needs >= 2 ops (an op-count-dependent
                           signature).
=========================  ==========================================
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from fractions import Fraction

from essun.backends.analytical import l0
from essun.specir import credit_automaton as ca

GIB = Fraction(2**30)  # the declared 1 GB = 2^30 B convention (A-AS1-BW-UNIT)


# ---------------------------------------------------------------------------
# Case spaces (frozen dataclasses; the minimizer shrinks these)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RingCase:
    """L0 ring chain case: ``ops_count`` AllReduce ops, r | payload.

    ``link_gbps`` is the MANIFEST-DECLARED value under the declared
    convention "GB/s with 1 GB = 2^30 B" (the A-AS1-BW-UNIT analogue);
    the clean engine converts it exactly to B/ns before executing the L0
    identity. A carrier that skips the conversion executes a different
    case — the translation-defect signature.
    """

    ranks: int
    payload_bytes: int
    ops_count: int
    link_gbps: int
    hop_latency_ns: int

    @property
    def link_bytes_per_ns_declared(self) -> Fraction:
        return Fraction(self.link_gbps) * GIB / Fraction(10**9)


@dataclass(frozen=True)
class TfcCase:
    """L0-TFC cell-quantization case (UEC11-FC-R08 leg).

    Single-op ring AllReduce with cell-quantized credit consumption:
    ``cq = QUANT(chunk/cell) * cell`` with QUANT the ROUNDUP law (clean)
    or a seeded defect variant.
    """

    ranks: int
    payload_bytes: int
    cell_bytes: int
    window_bytes: int
    link_bytes_per_ns: int
    hop_latency_ns: int
    credit_return_latency_ns: int


@dataclass(frozen=True)
class LinkCase:
    """Single-link credit-automaton case (UEC11-FC-R02 leg).

    One greedy serialized transfer of ``total_bytes`` (a whole multiple
    of ``packet_bytes``) under a credit window on one link.
    """

    total_bytes: int
    window_bytes: int
    link_bytes_per_ns: int
    hop_latency_ns: int
    credit_return_latency_ns: int
    packet_bytes: int

    def as_automaton_config(self) -> ca.AutomatonConfig:
        return ca.AutomatonConfig(
            window_bytes=self.window_bytes,
            link_bytes_per_ns=self.link_bytes_per_ns,
            hop_latency_ns=self.hop_latency_ns,
            credit_return_latency_ns=self.credit_return_latency_ns,
            packet_bytes=self.packet_bytes,
        )


# ---------------------------------------------------------------------------
# Clean engines (exact; these are the REAL essun laws, reused)
# ---------------------------------------------------------------------------


def ring_chain_completion(case: RingCase) -> tuple[Fraction, ...]:
    """Clean L0 ring per-op completion times under the DECLARED unit
    convention (GB/s, 1 GB = 2^30 B -> B/ns exactly)."""

    class _Infra(l0.InfraConfig):
        pass

    infra = _Infra(
        topology_id="diagnosis_ring_case",
        ranks=case.ranks,
        link_bytes_per_ns=case.link_bytes_per_ns_declared,
        hop_latency_ns=Fraction(case.hop_latency_ns),
    )
    return tuple(
        l0.ring_allreduce_time_ns(case.payload_bytes, case.ranks, infra)
        for _ in range(case.ops_count)
    )


def tfc_cell_completion(case: TfcCase) -> Fraction:
    """Clean L0-TFC cell-quantized completion (UEC11-FC-R08 ROUNDUP law).

    cq = ROUNDUP(c/cell)*cell; Rd = (c/cq)*W/(L+L_cr) capped at B;
    t = T/Rd + 2(r-1)L with T = 2(r-1)/r*M. Exact Fractions.
    """
    r = case.ranks
    M = case.payload_bytes
    chunk = Fraction(M, r)
    cells = -((-chunk) // Fraction(case.cell_bytes))  # ceil exact
    cq = cells * Fraction(case.cell_bytes)  # ROUNDUP law (UEC11-FC-R08)
    rtt = Fraction(case.hop_latency_ns + case.credit_return_latency_ns)
    rd = min(
        Fraction(case.link_bytes_per_ns),
        (chunk / cq) * Fraction(case.window_bytes) / rtt,
    )
    traffic = Fraction(2 * (r - 1) * M, r)
    return traffic / rd + Fraction(2 * (r - 1) * case.hop_latency_ns)


def link_transfer_completion(case: LinkCase) -> int:
    """Clean greedy credit-automaton transfer completion (exact int ns)."""
    return ca.GreedyLinkExecutor(case.as_automaton_config()).run_transfer(
        case.total_bytes
    ).completion_ns


# ---------------------------------------------------------------------------
# Seeded defect carriers (SILENT: they claim the clean declarations)
# ---------------------------------------------------------------------------


def defect_ring_latency_omitted_after_first(case: RingCase) -> tuple[Fraction, ...]:
    """SILENT scheduling omission: drops the 2(r-1)L term for every op
    after the first (op-index-dependent defect)."""

    class _Infra(l0.InfraConfig):
        pass

    infra = _Infra(
        topology_id="diagnosis_ring_case",
        ranks=case.ranks,
        link_bytes_per_ns=case.link_bytes_per_ns_declared,
        hop_latency_ns=Fraction(case.hop_latency_ns),
    )
    values = []
    for index in range(case.ops_count):
        traffic = l0.ring_traffic_per_rank(case.payload_bytes, case.ranks)
        if index == 0:
            values.append(traffic / infra.link_bytes_per_ns + Fraction(
                2 * (case.ranks - 1)
            ) * infra.hop_latency_ns)
        else:  # the omission: the declared latency term silently dropped
            values.append(traffic / infra.link_bytes_per_ns)
    return tuple(values)


def defect_ring_unit_ignored(case: RingCase) -> tuple[Fraction, ...]:
    """IGNORED unit conversion: executes the declared GB/s value as if it
    were already B/ns (skips the declared 1 GB = 2^30 B convention)."""

    class _Infra(l0.InfraConfig):
        pass

    infra = _Infra(
        topology_id="diagnosis_ring_case",
        ranks=case.ranks,
        link_bytes_per_ns=Fraction(case.link_gbps),  # convention skipped
        hop_latency_ns=Fraction(case.hop_latency_ns),
    )
    return tuple(
        l0.ring_allreduce_time_ns(case.payload_bytes, case.ranks, infra)
        for _ in range(case.ops_count)
    )


def defect_tfc_floor_not_roundup(case: TfcCase) -> Fraction:
    """CREDIT-CONSUMPTION bug: FLOOR instead of the ROUNDUP law of
    UEC11-FC-R08 (under-consumes credit; with c % cell != 0 the executed
    law moves the same bytes on less credit)."""
    r = case.ranks
    M = case.payload_bytes
    chunk = Fraction(M, r)
    cells = chunk // Fraction(case.cell_bytes)  # FLOOR (the seeded bug)
    cq = cells * Fraction(case.cell_bytes)
    # cells == 0 (a sub-cell chunk) divides by zero: the carrier CRASHES
    # there — the probe records ERROR_B; the minimizer then certifies the
    # crash boundary instead of silently inventing a zero-credit rate.
    rtt = Fraction(case.hop_latency_ns + case.credit_return_latency_ns)
    rd = min(
        Fraction(case.link_bytes_per_ns),
        (chunk / cq) * Fraction(case.window_bytes) / rtt,
    )
    traffic = Fraction(2 * (r - 1) * M, r)
    return traffic / rd + Fraction(2 * (r - 1) * case.hop_latency_ns)


class _BatchedReturnAutomaton:
    """RETURN-BATCHING error carrier: credit returns are released to the
    sender's balance only in whole-window batches (the destination is
    modeled as returning credit when a FULL window of bytes has been
    received and processed, not per packet).

    The admission law itself is untouched: a transmit still requires the
    balance to cover the packet, so the sliding-window in-flight bound
    holds (checked mechanically on this carrier's own admission trace by
    the harness via :func:`ca.sliding_window_bound_holds`).
    """

    def __init__(self, window_bytes: int, credit_loop_delay_ns: int) -> None:
        self.window_bytes = window_bytes
        self.credit_loop_delay_ns = credit_loop_delay_ns
        self._credit = window_bytes
        self._pending: list[tuple[int, int]] = []  # (due_ns, bytes)
        self._staged = 0  # due bytes not yet released (batched return)
        self._last_time_ns = 0
        self.admissions: list[ca.Admission] = []

    def _apply_returns_due(self, time_ns: int) -> None:
        while self._pending and self._pending[0][0] <= time_ns:
            due_ns, bytes_ = heapq.heappop(self._pending)
            self._staged += bytes_
        releases = self._staged // self.window_bytes  # whole-window batches
        if releases:
            self._credit += releases * self.window_bytes
            self._staged -= releases * self.window_bytes

    def attempt(self, time_ns: int, packet_bytes: int):
        self._apply_returns_due(time_ns)
        self._last_time_ns = time_ns
        if self._credit >= packet_bytes:
            self._credit -= packet_bytes
            due_ns = time_ns + self.credit_loop_delay_ns
            heapq.heappush(self._pending, (due_ns, packet_bytes))
            admission = ca.Admission(time_ns, packet_bytes, due_ns)
            self.admissions.append(admission)
            return admission
        return ca.Rejection(time_ns, packet_bytes, self._credit)


class _BatchedGreedyExecutor(ca.GreedyLinkExecutor):
    """Greedy executor driving the batched-return carrier."""

    def __init__(self, config: ca.AutomatonConfig) -> None:
        self._config = config
        self.machine = _BatchedReturnAutomaton(
            config.window_bytes, config.credit_loop_delay_ns
        )

    def _next_admission_time(self, earliest_ns: int) -> int:
        # Exact integer scan as the clean executor's, but over the
        # batched machine's FUTURE balances: a pending return becomes
        # spendable only as part of a whole-window batch, so the future
        # balance at time t is credit + ((staged + due-by-t) // W) * W.
        s = self._config.packet_bytes
        t_ns = earliest_ns
        if self.machine._credit >= s:
            return t_ns
        staged = self.machine._staged
        for due_ns, bytes_ in sorted(self.machine._pending):
            if due_ns > t_ns:
                t_ns = due_ns
            staged += bytes_
            future = self.machine._credit + (
                staged // self.machine.window_bytes
            ) * self.machine.window_bytes
            if future >= s:
                break
        return t_ns


def defect_link_batched_return_completion(case: LinkCase) -> int:
    """Completion under the batched-return carrier (exact int ns)."""
    return _BatchedGreedyExecutor(case.as_automaton_config()).run_transfer(
        case.total_bytes
    ).completion_ns


# ---------------------------------------------------------------------------
# Ground-truth registry (committed; the harness measures against it)
# ---------------------------------------------------------------------------

GROUND_TRUTH: dict[str, dict] = {
    "floor_not_roundup_credit_consumption": {
        "defect_kind": "credit-consumption bug",
        "carrier": "defect_tfc_floor_not_roundup",
        "expected_label": "specification_violation",
        "expected_reason": (
            "executed form contradicts UEC11-FC-R08 (bound; ROUNDUP is "
            "the law, FLOOR executed)"
        ),
    },
    "drain_batched_credit_return": {
        "defect_kind": "return-batching error",
        "carrier": "defect_link_batched_return_completion",
        "expected_label": "permitted_implementation_variation",
        "expected_reason": (
            "admission law UEC11-FC-R02 intact on the carrier's own trace "
            "(sliding-window bound holds); return timing not normatively "
            "pinned; divergence quantified and stays visible"
        ),
    },
    "ignored_gb_unit_conversion": {
        "defect_kind": "ignored unit conversion",
        "carrier": "defect_ring_unit_ignored",
        "expected_label": "translation_defect",
        "expected_reason": (
            "executed case differs from the declared case: the declared "
            "1 GB = 2^30 B convention (A-AS1-BW-UNIT analogue) was skipped"
        ),
    },
    "latency_omitted_after_first_op": {
        "defect_kind": "silent scheduling omission",
        "carrier": "defect_ring_latency_omitted_after_first",
        "expected_label": "specification_violation",
        "expected_reason": (
            "declared L0 ring identity (latency term per op, A-L0-LAT) "
            "contradicted for every op after the first; reproducer "
            "certified op-count-dependent (>= 2 ops)"
        ),
    },
}
