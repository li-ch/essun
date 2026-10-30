"""UEC11-FC-R05 executed as a conformance check: the credit-arrival law.

G2 credit-family ladder stage S4 (2026-10-30, per the S1 plan in
experiments/uec/credit_family_inventory.md).  UEC 1.1 §3.6.15, requirement
UEC11-FC-R05 (DEFINITIONAL, anchor UEC11-S3.6.15-TFC): ``pds.credit`` is a
monotonically increasing wrapping counter; one unit (bit) represents 256
bytes; on credit arrival, ``if Credit > cumulative_credit`` then
``credit += (Credit − cumulative_credit) >> 8`` and
``cumulative_credit = Credit``.

Per the D2 profile rule a profile BINDING may reference only a
``simulated_behavior`` requirement — so this law's carrier is NOT a
binding and NOT a backend extension (the law demands none): it is a
``conformance_test``, exercised by the executable PROFILE CHECKS entries
UEC11-CHK-12/13/14 (experiments/uec/build_semantic_profile.py), all
pointing at THIS file.  The promotion is atomic with the disposition flip
in src/essun/specir/uec_credits_flow_control.py and the PROMOTED /
EXPECTED_COUNTS update in tests/specir/test_dispositions.py.

The executed law, exactly as the requirement statement carries it:

- one credit unit = 256 destination-buffer bytes (``>> 8``); the SAME
  spec-derived constant the landed executors carry
  (analytical_l0_tfc.TFC_CREDIT_UNIT_BYTES and
  credit_automaton.TFC_CREDIT_UNIT_BYTES, both citing UEC11-FC-R05) —
  cross-verified live below so the three cannot drift apart;
- the counter field is 24 bits wide (UEC11-FC-R01's own statement names
  "the 24-bit pds.credit"), so the counter wraps at 2**24;
- "``Credit > cumulative_credit``" is read in the WRAPPING counter's
  order, not as a plain integer comparison: the modular difference
  ``d = (Credit − cumulative_credit) mod 2**24`` is an increase iff
  ``0 < d < 2**23`` — the cyclic-counter ordering law the SAME
  specification states for its CBFC counters (UEC11-FC-R28: two cyclic
  counter values can be reliably ordered only if they differ by less
  than half the counter range).  Applying that family-wide ordering law
  to TFC's ``pds.credit`` is this check's one registered modeling choice
  (assumption A-TFCA-ORDER, experiments/vertical_slice/
  assumptions_tfc_credit_arithmetic.yaml); a plain integer comparison
  would silently drop every legitimate increase that spans the counter
  wrap (the boundary case below pins the difference);
- on a NO-OP (arrival equal to, stale against, or order-ambiguous with
  the cumulative counter) NEITHER statement executes: no credit and no
  cumulative update — loss/reorder tolerance comes from the guard, and
  the source keeps its place in the counter's order.

Expected values are derived IN THIS TEST by exact integer arithmetic
(hand-derived literals in the comments, independent expressions in the
assertions); there is no float, no random module (the pseudo-random
stream is a fixed-constant LCG), and no oracle but the law itself.
"""

from __future__ import annotations

from itertools import permutations

from essun.specir.credit_automaton import TFC_CREDIT_UNIT_BYTES as AUTOMATON_UNIT
from essun.specir.uec_credits_flow_control import requirements as fc_requirements
from essun.backends.analytical.l0_tfc import (
    TFC_CREDIT_UNIT_BYTES as ANALYTICAL_UNIT,
)

REQUIREMENT_ID = "UEC11-FC-R05"
WIDTH_REQUIREMENT_ID = "UEC11-FC-R01"  # "the 24-bit pds.credit"
ORDER_REQUIREMENT_ID = "UEC11-FC-R28"  # cyclic-counter ordering law (CBFC)

#: One credit unit grants 256 bytes: the >> 8 of the arrival law.
CREDIT_UNIT_SHIFT = 8
CREDIT_UNIT_BYTES = 1 << CREDIT_UNIT_SHIFT  # 256

#: The pds.credit field is 24 bits wide (UEC11-FC-R01); the counter wraps.
PDS_CREDIT_BITS = 24
COUNTER_MODULUS = 1 << PDS_CREDIT_BITS  # 16_777_216
#: Reliable-order half range (UEC11-FC-R28's law): an increase iff
#: 0 < modular difference < 2**23.
ORDER_HALF_RANGE = 1 << (PDS_CREDIT_BITS - 1)  # 8_388_608


class CreditArrival:
    """The R05 arrival step, executed exactly (the check's harness).

    State: ``credit`` — granted credit UNITS (one unit = 256 B), the
    source's balance; ``cumulative_credit`` — the source's copy of the
    monotonically increasing wrapping ``pds.credit`` counter, in BYTES.
    Initial state is set at construction and is a free fixture of the
    check (assumption A-TFCA-INIT): bring-up (UEC11-FC-R14) is not
    executed here.  ``on_arrival`` returns the units granted by the
    arrival (0 for a no-op) — integers only.
    """

    def __init__(self, cumulative_credit: int = 0) -> None:
        self.credit = 0
        self.cumulative_credit = cumulative_credit

    def on_arrival(self, credit_field: int) -> int:
        if not 0 <= credit_field < COUNTER_MODULUS:
            raise ValueError(
                f"{REQUIREMENT_ID}: credit_field {credit_field} does not "
                f"fit the {PDS_CREDIT_BITS}-bit pds.credit counter "
                f"({WIDTH_REQUIREMENT_ID})"
            )
        difference = (credit_field - self.cumulative_credit) % COUNTER_MODULUS
        if 0 < difference < ORDER_HALF_RANGE:
            granted = difference >> CREDIT_UNIT_SHIFT
            self.credit += granted
            self.cumulative_credit = credit_field
            return granted
        return 0  # equal, stale/duplicate, or order-ambiguous: a no-op


# -- the requirement object and the shared constant stay live --------------------


def test_r05_object_and_shared_unit_constant_are_live() -> None:
    # The check executes what the live registry says, and the 256-byte
    # unit it enforces is the SAME constant the landed executors carry:
    # drift on either side is a hard error, never a silent edit.
    index = {req.requirement_id: req for req in fc_requirements()}
    r05 = index[REQUIREMENT_ID]
    assert r05.keyword == "DEFINITIONAL"
    assert r05.disposition == "conformance_test"  # this check is the carrier
    for phrase in (">> 8", "256 bytes", "wrapping", "cumulative_credit"):
        assert phrase in r05.statement, (
            f"{REQUIREMENT_ID}: statement no longer carries {phrase!r} — "
            "the executed law and its anchor drifted apart"
        )
    # The field width the wrap boundary needs (a modeling input, cited).
    assert "24-bit pds.credit" in index[WIDTH_REQUIREMENT_ID].statement
    assert CREDIT_UNIT_BYTES == 256 == ANALYTICAL_UNIT == AUTOMATON_UNIT


# -- golden traces: whole-unit grants, hand-derived ------------------------------


def test_golden_trace_whole_unit_grants() -> None:
    # Arrivals (pds.credit values): 256, 768, 1024, 4096.
    # Deltas: 256, 512, 256, 3072 -> grants 1, 2, 1, 12 units;
    # running credit 1, 3, 4, 16; cumulative ends at 4096.
    machine = CreditArrival()
    arrivals = (256, 768, 1024, 4096)
    grants = []
    for arrival in arrivals:
        grants.append(machine.on_arrival(arrival))
    assert grants == [1, 2, 1, 12]
    assert machine.credit == 16
    assert machine.cumulative_credit == 4096
    # Independent derivation: every delta is a whole 256-B multiple, so
    # the per-arrival floors telescope and the balance equals the floored
    # cumulative byte count (loss-tolerance identity of this regime).
    assert machine.credit == 4096 // CREDIT_UNIT_BYTES
    assert machine.credit == sum(
        (b - a) // CREDIT_UNIT_BYTES
        for a, b in zip((0,) + arrivals[:-1], arrivals)
    )


def test_boundary_equal_arrival_is_a_noop() -> None:
    # An arrival EQUAL to the cumulative counter is not an increase:
    # no grant, and the cumulative does not move.
    machine = CreditArrival()
    machine.on_arrival(1024)
    assert (machine.credit, machine.cumulative_credit) == (4, 1024)
    granted = machine.on_arrival(1024)  # duplicate of the current value
    assert granted == 0
    assert (machine.credit, machine.cumulative_credit) == (4, 1024)


def test_boundary_stale_and_reordered_arrivals_are_ignored() -> None:
    # Stale (older) and duplicate-of-older arrivals carry a modular
    # difference at or above the half range: ignored by the guard, state
    # unchanged — reordering and duplication cannot double-grant.
    machine = CreditArrival()
    machine.on_arrival(1024)
    for stale in (512, 0, 1023):  # 1023 is stale-by-one, still stale
        assert machine.on_arrival(stale) == 0
        assert (machine.credit, machine.cumulative_credit) == (4, 1024)
    # A genuine increase after the ignored staleness still lands whole.
    assert machine.on_arrival(1536) == 2  # (1536-1024) >> 8 = 2
    assert machine.credit == 6


def test_boundary_subunit_increase_grants_zero_but_advances() -> None:
    # A positive increase of less than one unit: the >> 8 floor grants 0
    # units while cumulative_credit DOES advance (the guard passed).
    machine = CreditArrival()
    assert machine.on_arrival(255) == 0  # 255 >> 8 = 0
    assert machine.cumulative_credit == 255  # advanced by the arrival
    assert machine.credit == 0
    assert machine.on_arrival(511) == 1  # (511-255) = 256 -> exactly 1
    assert machine.credit == 1


def test_subunit_slivers_do_not_telelescope() -> None:
    # The spec algorithm grants per arrival, so sub-unit slivers are NOT
    # carried forward: 0 -> 199 -> 399 -> 599 grants 0+0+0 = 0 units
    # (deltas 199, 200, 200 each below one unit), while the direct
    # arrival 0 -> 599 grants 2 units.  This is the algorithm's own
    # exact arithmetic, pinned as executed — NOT repaired.  Under the
    # destination allocation discipline (UEC11-FC-R07: credit is
    # allocated in 256-byte units) real deltas are whole units and the
    # sliver regime never occurs; the loss-tolerance identity below
    # holds exactly in precisely that regime.
    sequential = CreditArrival()
    for arrival in (199, 399, 599):
        sequential.on_arrival(arrival)
    assert sequential.credit == 0
    assert sequential.cumulative_credit == 599
    direct = CreditArrival()
    assert direct.on_arrival(599) == 599 // CREDIT_UNIT_BYTES == 2
    assert direct.credit == 2


def test_boundary_increase_spanning_the_counter_wrap() -> None:
    # Cumulative sits at 2**24 - 512 = 16_776_704 (a whole-unit point,
    # 65_533 units in); the counter wraps and the next arrival carries
    # Credit = 255 (true cumulative 2**24 + 255).  Modular difference
    # (255 - 16_776_704) mod 2**24 = 767 -> an increase (767 < 2**23),
    # granting 767 >> 8 = 2 units; cumulative becomes 255.
    # A NAIVE plain-integer comparison (255 > 16_776_704 -> False) would
    # drop the grant: the wrapping order (A-TFCA-ORDER, law cited to
    # UEC11-FC-R28) is what keeps the monotone counter working past the
    # wrap.
    machine = CreditArrival(cumulative_credit=COUNTER_MODULUS - 512)
    assert machine.cumulative_credit == 16_776_704
    granted = machine.on_arrival(255)
    assert granted == 2
    assert machine.credit == 2
    assert machine.cumulative_credit == 255
    # The naive-integer misreading, executed for contrast, grants 0.
    assert not (255 > COUNTER_MODULUS - 512)  # the misreading's test


def test_order_ambiguous_arrivals_are_ignored() -> None:
    # UEC11-FC-R28: values differing by half the range or more are not
    # reliably ordered — equality with the half range is NOT an increase.
    machine = CreditArrival()
    assert machine.on_arrival(ORDER_HALF_RANGE) == 0  # exactly half
    assert machine.on_arrival(COUNTER_MODULUS - 1) == 0  # almost stale
    assert (machine.credit, machine.cumulative_credit) == (0, 0)


def test_out_of_field_arrival_is_rejected() -> None:
    # A value that does not fit the 24-bit field is a malformed arrival,
    # rejected loudly citing the field-width fact (UEC11-FC-R01).
    machine = CreditArrival()
    for bad in (-1, COUNTER_MODULUS, 2**32):
        try:
            machine.on_arrival(bad)
        except ValueError as exc:
            assert WIDTH_REQUIREMENT_ID in str(exc)
        else:  # pragma: no cover - the rejection above is the contract
            raise AssertionError(f"arrival {bad} was not rejected")


# -- loss / reorder tolerance: the executed claim and its exact regime ------------


def test_loss_and_reorder_tolerance_on_whole_unit_streams() -> None:
    # "An increase grants additional credit, giving tolerance to credit
    # packet loss" — EXECUTED: for whole-unit streams the granted total
    # depends only on the FINAL cumulative value, never on the path.
    # Every permutation of {256, 768, 1536} grants exactly 6 units, the
    # direct single arrival 0 -> 1536 grants the same 6, and dropping
    # the intermediate arrivals entirely changes nothing.
    finals = []
    for order in permutations((256, 768, 1536)):
        machine = CreditArrival()
        for arrival in order:
            machine.on_arrival(arrival)
        finals.append(machine.credit)
    assert finals == [6] * 6
    direct = CreditArrival()
    direct.on_arrival(1536)
    assert direct.credit == 1536 // CREDIT_UNIT_BYTES == 6
    # Dropping the middle arrival (loss): 0 -> 1536 directly, same total.
    dropped = CreditArrival()
    dropped.on_arrival(256)
    dropped.on_arrival(1536)  # 768 was lost in flight
    assert dropped.credit == 6


# -- negative: the pinned boundaries distinguish the law from misreadings ---------


def _naive_comparison_machine(cumulative_credit: int = 0):
    """Misreading A: '>' as a plain integer comparison (no wrap order)."""

    class Naive:
        def __init__(self) -> None:
            self.credit = 0
            self.cumulative_credit = cumulative_credit

        def on_arrival(self, credit_field: int) -> int:
            if credit_field > self.cumulative_credit:
                granted = (credit_field - self.cumulative_credit) >> 8
                self.credit += granted
                self.cumulative_credit = credit_field
                return granted
            return 0

    return Naive()


def _guardless_machine():
    """Misreading B: grant on every arrival (absolute difference, no
    monotone guard) — duplicates and reordering double-grant."""

    class Guardless:
        def __init__(self) -> None:
            self.credit = 0
            self.cumulative_credit = 0

        def on_arrival(self, credit_field: int) -> int:
            granted = abs(credit_field - self.cumulative_credit) >> 8
            self.credit += granted
            self.cumulative_credit = credit_field
            return granted

    return Guardless()


def _cumulative_always_updates_machine():
    """Misreading C: execute cumulative_credit = Credit even on a no-op —
    a stale arrival then corrupts the place in the counter's order."""

    class UpdatesAlways:
        def __init__(self) -> None:
            self.credit = 0
            self.cumulative_credit = 0

        def on_arrival(self, credit_field: int) -> int:
            granted = 0
            if credit_field > self.cumulative_credit:
                granted = (credit_field - self.cumulative_credit) >> 8
                self.credit += granted
            self.cumulative_credit = credit_field
            return granted

    return UpdatesAlways()


def test_negative_misreadings_are_distinguished_by_the_pins() -> None:
    # Each pinned boundary case separates the R05 algorithm from a named
    # misreading — the check has teeth on every clause of the law.
    # (A) wrap boundary: the naive comparison drops the wrap-spanning
    # increase the law grants (2 units).
    naive = _naive_comparison_machine(COUNTER_MODULUS - 512)
    assert naive.on_arrival(255) == 0  # spec: 2 (pinned above)
    # (B) reorder boundary: granting without the guard pays duplicates.
    spec = CreditArrival()
    guardless = _guardless_machine()
    for arrival in (1536, 256, 768):  # stale 256 and 768 after 1536
        spec.on_arrival(arrival)
        guardless.on_arrival(arrival)
    assert spec.credit == 6
    assert guardless.credit == 13  # 6 + 5 + 2: double-granted staleness
    # (C) no-op boundary: updating the cumulative on a no-op corrupts
    # the next genuine increase (512 bytes counted twice).
    spec = CreditArrival()
    spec.on_arrival(1024)
    spec.on_arrival(512)  # stale no-op
    after_spec = spec.on_arrival(1536)  # (1536-1024) >> 8 = 2
    corrupt = _cumulative_always_updates_machine()
    corrupt.on_arrival(1024)
    corrupt.on_arrival(512)  # no-op grant, but cumulative moves to 512
    after_corrupt = corrupt.on_arrival(1536)  # (1536-512) >> 8 = 4
    assert after_spec == 2
    assert after_corrupt == 4
    # (D) the unit shift: >> 7 (128-B) and >> 9 (512-B) units misread
    # the same 256-B delta the law prices at exactly one unit.
    assert 256 >> CREDIT_UNIT_SHIFT == 1
    assert 256 >> 7 == 2
    assert 256 >> 9 == 0


# -- invariant: structural properties over a fixed deterministic stream -----------


def _lcg_arrivals(count: int, seed: int):
    """A fixed-constant LCG stream mod 2**24 — deterministic, no random."""
    state = seed
    for _ in range(count):
        state = (state * 1103515245 + 12345) % (1 << 31)
        yield state % COUNTER_MODULUS


def test_invariant_stream_properties() -> None:
    # 2000 arrivals from the fixed LCG: every ACCEPTED arrival advances
    # the cumulative counter by a difference in the open half range (the
    # wrapping-order monotonicity) and grants exactly its floored units;
    # every ignored arrival leaves the state untouched; the counter
    # stays in field; granted units never exceed the floored byte
    # advance (floor superadditivity — equality exactly on whole-unit
    # streams, pinned below); and both paths actually occur.
    machine = CreditArrival()
    accepted = ignored = 0
    advance_bytes = 0
    for arrival in _lcg_arrivals(2000, seed=20261030):
        before = machine.cumulative_credit
        difference = (arrival - before) % COUNTER_MODULUS
        granted = machine.on_arrival(arrival)
        assert 0 <= machine.cumulative_credit < COUNTER_MODULUS
        if 0 < difference < ORDER_HALF_RANGE:  # accepted by the law
            accepted += 1
            assert granted == difference >> CREDIT_UNIT_SHIFT
            assert machine.cumulative_credit == arrival
            advance_bytes += difference
        else:  # equal, stale/duplicate, or order-ambiguous: a no-op
            ignored += 1
            assert granted == 0
            assert machine.cumulative_credit == before
    assert accepted > 0 and ignored > 0
    assert machine.credit <= advance_bytes >> CREDIT_UNIT_SHIFT


def test_invariant_whole_unit_stream_telescopes_exactly() -> None:
    # Whole-unit stream (every arrival a 256-B multiple): per-arrival
    # floors telescope exactly — the balance equals the floored TOTAL
    # accepted byte advance at every step, which is the arithmetic form
    # of the loss-tolerance claim (what a lost intermediate arrival
    # would have granted is recovered by the next one that arrives).
    machine = CreditArrival()
    advance_bytes = 0
    accepted = 0
    for arrival in _lcg_arrivals(500, seed=424242):
        field = (arrival % (COUNTER_MODULUS // CREDIT_UNIT_BYTES)) * (
            CREDIT_UNIT_BYTES
        )  # quantized to whole units, still within the 24-bit field
        before = machine.cumulative_credit
        difference = (field - before) % COUNTER_MODULUS
        machine.on_arrival(field)
        if 0 < difference < ORDER_HALF_RANGE:  # accepted, whole-unit
            accepted += 1
            advance_bytes += difference
            assert difference % CREDIT_UNIT_BYTES == 0
            assert machine.cumulative_credit == field
        else:
            assert machine.cumulative_credit == before
        assert machine.credit == advance_bytes >> CREDIT_UNIT_SHIFT
    assert accepted > 0
