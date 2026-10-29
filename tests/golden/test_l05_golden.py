"""Golden identities for the L0.5 serialized-ring AllReduce (second frontier
F1, src/essun/backends/analytical/l05.py).

Expected values are recomputed independently here (hand-derived fractions
spelled out, not by calling the implementation under test), per the handoff
rule that golden tests derive from the specified identities. The landed L0
modules (l0, l0_phase_collectives) are used only as CONVERGENCE ANCHORS —
independently landed identities the L0.5 result must reproduce exactly at
the injection limit.

Identity under test (all parameters free; c = M/r):

    one transfer   s = c/I + c/B + L          [one ring hop]
    one phase         = (r-1) * s
    AllReduce (2 phases) = 2 * (r-1) * s
                        = t_L0 + 2*(r-1)/r * M / I      [exact disagreement]

Worked cases (derived by hand below, asserted as exact Fractions):

A) r=8, B=64, L=200, I=64, M=16384 (16 KiB): c=2048, transfer
   32+32+200=264, phase 7*264=1848, AllReduce 3696. Landed L0 3248
   (28672/64 + 14*200); disagreement 448 = 14*2048/64.
B) r=8, B=64, L=200, I=64, M=1048576 (1 MiB): c=131072, transfer
   2048+2048+200=4296, phase 30072, AllReduce 60144. Landed L0 31472;
   disagreement 28672 = 14*131072/64.
C) Injection limit (I -> infinity, config None), M=16384: transfer 232,
   phase 1624 (the landed S4 ring phase), AllReduce 3248 == l0 identity;
   at 1 MiB transfer 2248, phase 15736, AllReduce 31472 == l0 identity.
D) Decimal parameters r=8, M=1000, B=25/2, L=1/2, I=25/2: transfer
   10+10+1/2=41/2, phase 287/2, AllReduce 287; L0 = 147 (S4 case E);
   disagreement 140 = 14*10. Identity functions only (1000 % 8 != 0 —
   execute() rejects non-divisible payloads; the Fraction arithmetic
   itself stays exact).
E) r=4, M=1000, B=10, L=1, I=20 (I != B): c=250, transfer 25/2+25+1=77/2,
   phase 231/2, AllReduce 231; L0 = 156 (S4 case D); disagreement
   75 = 6*250/20.
F) r=2, M=16384, B=64, L=200, I=64: c=8192, transfer 128+128+200=456,
   AllReduce 912; L0 = 656 (the S3/S4 r=2 coincidence) — L0.5 breaks the
   coincidence for finite I (disagreement 256) and restores it exactly at
   the injection limit.
G) Wire traffic unchanged from L0: per rank 2*(r-1)/r*M (28672 at 16 KiB,
   1835008 at 1 MiB), total per op 2*(r-1)*M (229376 / 14680064).
"""

from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from essun.backends.analytical import l0
from essun.backends.analytical import l0_phase_collectives as l0p
from essun.backends.analytical import l05
from essun.workload import w1

RANKS = 8
_TOPO = Path(__file__).resolve().parents[2] / "experiments" / "topologies"


def _config(
    ranks=RANKS, bw=64, lat=200, injection=64, topology_id="ring8_l05_free_v1"
):
    return l05.L05Config(
        topology_id=topology_id,
        ranks=ranks,
        link_bytes_per_ns=Fraction(bw),
        hop_latency_ns=Fraction(lat),
        injection_bytes_per_ns=None if injection is None else Fraction(injection),
    )


def _ops(payload=16384, tp_size=RANKS):
    return w1.generate_w1_ops(
        w1.W1Config(tp_size=tp_size, layers=1, steps=1, allreduce_bytes=payload)
    )


# --- A/B: per-transfer decomposition and the L0.5 identities -----------------


def test_transfer_decomposition_16kib():
    # A: c=2048, transfer 32+32+200=264, phase 1848, AllReduce 3696.
    config = _config()
    chunk = l05.chunk_bytes(16384, 8)
    assert chunk == Fraction(2048)
    assert l05.chunk_serialization_ns(chunk, config.injection_bytes_per_ns) == Fraction(32)
    assert l05.chunk_transfer_time_ns(chunk, config) == Fraction(264)
    assert l05.phase_time_ns(16384, 8, config) == Fraction(1848)
    assert l05.allreduce_time_ns(16384, 8, config) == Fraction(3696)


def test_transfer_decomposition_1mib():
    # B: c=131072, transfer 2048+2048+200=4296, phase 30072, AllReduce 60144.
    config = _config()
    chunk = l05.chunk_bytes(1048576, 8)
    assert chunk == Fraction(131072)
    assert l05.chunk_transfer_time_ns(chunk, config) == Fraction(4296)
    assert l05.phase_time_ns(1048576, 8, config) == Fraction(30072)
    assert l05.allreduce_time_ns(1048576, 8, config) == Fraction(60144)


def test_traffic_identity_unchanged_from_l0():
    # G: serialization moves no bytes — per-rank wire equals the landed L0
    # identity (28672 / 1835008); totals 2*(r-1)*M per op.
    for size, per_rank in ((16384, 28672), (1048576, 1835008)):
        assert l0.ring_traffic_per_rank(size, 8) == Fraction(per_rank)
        assert l0.ring_traffic_per_rank(size, 8) * 8 == Fraction(14 * size)


# --- The convergence identity (the point of F1) ------------------------------


def test_converges_to_landed_l0_at_injection_limit():
    # C: I -> infinity (config None): the L0.5 identity IS the landed L0
    # identity, exactly — at 16 KiB, 1 MiB, and the landed golden literals.
    limit = _config(injection=None)
    assert l05.allreduce_time_ns(16384, 8, limit) == Fraction(3248)
    assert l05.allreduce_time_ns(1048576, 8, limit) == Fraction(31472)
    for size in (16384, 1048576):
        anchor = l0.ring_allreduce_time_ns(
            size, 8, l0.InfraConfig("ring8_l05_free_v1", 8, Fraction(64), Fraction(200))
        )
        assert l05.allreduce_time_ns(size, 8, limit) == anchor
        # Phase level: the limit equals the landed S4 ring phase identities.
        assert l05.phase_time_ns(size, 8, limit) == l0p.ring_reducescatter_time_ns(
            size, 8, l0.InfraConfig("ring8_l05_free_v1", 8, Fraction(64), Fraction(200))
        )
    assert l05.phase_time_ns(16384, 8, limit) == Fraction(1624)
    assert l05.phase_time_ns(1048576, 8, limit) == Fraction(15736)
    # D/E/F at the limit: every hand case collapses onto its L0 value.
    assert l05.allreduce_time_ns(1000, 8, _config(bw=Fraction(25, 2), lat=Fraction(1, 2), injection=None)) == Fraction(147)
    assert l05.allreduce_time_ns(1000, 4, _config(ranks=4, bw=10, lat=1, injection=None)) == Fraction(156)
    assert l05.allreduce_time_ns(16384, 2, _config(ranks=2, injection=None)) == Fraction(656)


def test_exact_disagreement_identity_for_finite_injection():
    # t_L05 - t_L0 == 2*(r-1)/r * M / I recomputed from scratch for every
    # hand case (A 448, B 28672, D 140, E 75, F 256) — the closed-form
    # disagreement holds for every finite I, which is what makes the
    # I -> infinity convergence exact.
    cases = [
        # (M, r, B, L, I, expected disagreement)
        (16384, 8, 64, 200, 64, 448),          # A
        (1048576, 8, 64, 200, 64, 28672),      # B
        (1000, 8, Fraction(25, 2), Fraction(1, 2), Fraction(25, 2), 140),  # D
        (1000, 4, 10, 1, 20, 75),              # E (I != B)
        (16384, 2, 64, 200, 64, 256),          # F
    ]
    for message, ranks, bw, lat, injection, expected in cases:
        config = _config(ranks=ranks, bw=bw, lat=lat, injection=injection)
        t_l05 = l05.allreduce_time_ns(message, ranks, config)
        t_l0 = l0.ring_allreduce_time_ns(
            message, ranks, l0.InfraConfig("ring8_l05_free_v1", ranks, Fraction(bw), Fraction(lat))
        )
        recomputed = Fraction(2 * (ranks - 1) * message, ranks) / Fraction(injection)
        assert recomputed == Fraction(expected)
        assert t_l05 - t_l0 == recomputed
        assert l05.serialization_term_ns(message, ranks, config) == recomputed
    # Hand literals for the cases themselves (B: 60144 vs 31472; D: 287 vs
    # 147; E: 231 vs 156; F: 912 vs 656).
    assert l05.allreduce_time_ns(16384, 8, _config()) == Fraction(3696)
    assert l05.allreduce_time_ns(1048576, 8, _config()) == Fraction(60144)
    assert l05.allreduce_time_ns(1000, 8, _config(bw=Fraction(25, 2), lat=Fraction(1, 2), injection=Fraction(25, 2))) == Fraction(287)
    assert l05.allreduce_time_ns(1000, 4, _config(ranks=4, bw=10, lat=1, injection=20)) == Fraction(231)
    assert l05.allreduce_time_ns(16384, 2, _config(ranks=2)) == Fraction(912)


def test_disagreement_shrinks_montonically_to_zero():
    # Scaling I by 10 divides the exact disagreement by 10 (Fraction-exact),
    # and at I = 10^12 the 16 KiB disagreement is below 1e-6 ns — the
    # convergence is exact in form and numerically vanishing.
    base = l05.serialization_term_ns(16384, 8, _config(injection=1))
    for k in range(1, 10):
        assert l05.serialization_term_ns(16384, 8, _config(injection=10**k)) == base / 10**k
    tiny = l05.serialization_term_ns(16384, 8, _config(injection=10**12))
    assert tiny == base / 10**12
    assert tiny < Fraction(1, 10**6)
    assert l05.serialization_term_ns(16384, 8, _config(injection=None)) == Fraction(0)


# --- Execution with observables ----------------------------------------------


def test_execute_observables_16kib():
    # A: one AllReduce op on the committed L0.5 topology: completion 3696,
    # anchor 3248, serialization term 448, wire bytes identical to L0.
    data = yaml.safe_load(
        (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
    )
    config = l05.load_l05_config(data)
    result = l05.execute(_ops(), config)
    conservation = result["observables"]["O-CONSERVATION"]
    assert conservation["kind"] == "exact"
    assert conservation["ops_checked"] == 1
    assert conservation["violations"] == 0
    assert conservation["total_wire_bytes_exact"] == str(Fraction(229376))
    (op,) = result["per_op"]
    assert op["chunk_bytes_exact"] == str(Fraction(2048))
    assert op["transfers_per_phase"] == 7
    assert op["phases"] == 2
    assert op["per_transfer"] == {
        "serialization_ns_exact": str(Fraction(32)),
        "wire_ns_exact": str(Fraction(32)),
        "hop_latency_ns_exact": str(Fraction(200)),
    }
    assert op["per_rank_wire_bytes_exact"] == str(Fraction(28672))
    assert op["total_wire_bytes_exact"] == str(Fraction(229376))
    assert op["completion_time_ns_exact"] == str(Fraction(3696))
    assert op["completion_time_ns"] == 3696.0
    assert op["l0_anchor_time_ns_exact"] == str(Fraction(3248))
    assert op["serialization_term_ns_exact"] == str(Fraction(448))
    model = result["model"]
    assert model["transport_model"] == "serialized_pipelined_ring"
    assert model["injection_bytes_per_ns_exact"] == str(Fraction(64))
    assert model["at_injection_limit"] is False
    cct = result["observables"]["O-CCT"]
    assert cct["completion_time_ns_mean_exact"] == str(Fraction(3696))
    assert cct["completion_time_ns_max"] == 3696.0


def test_execute_at_injection_limit_equals_l0():
    # C through the observable surface: with I = None the per-op completion
    # equals the L0 anchor exactly and the disagreement term is exactly 0.
    config = _config(injection=None)
    result = l05.execute(_ops(), config)
    (op,) = result["per_op"]
    assert op["completion_time_ns_exact"] == str(Fraction(3248))
    assert op["completion_time_ns_exact"] == op["l0_anchor_time_ns_exact"]
    assert op["serialization_term_ns_exact"] == str(Fraction(0))
    assert result["model"]["at_injection_limit"] is True
    assert result["model"]["injection_bytes_per_ns_exact"] is None


def test_execute_is_deterministic():
    # Same ops + config -> byte-identical result dicts, including via the
    # committed YAML (loader determinism) and across repeated evaluation.
    data = yaml.safe_load(
        (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
    )
    first = l05.execute(_ops(), l05.load_l05_config(data))
    second = l05.execute(_ops(), l05.load_l05_config(yaml.safe_load(
        (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
    )))
    assert first == second
    assert l05.execute(_ops(), l05.load_l05_config(data)) == first
    assert l05.allreduce_time_ns(16384, 8, l05.load_l05_config(data)) == Fraction(3696)


# --- Loader and capability gates ---------------------------------------------


def test_topology_yaml_loads_with_expected_values():
    data = yaml.safe_load(
        (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
    )
    config = l05.load_l05_config(data)
    assert config.topology_id == "ring8_l05_free_v1"
    assert config.ranks == 8
    assert config.link_bytes_per_ns == Fraction(64)
    assert config.hop_latency_ns == Fraction(200)
    assert config.injection_bytes_per_ns == Fraction(64)
    assert l05.CAPABILITIES["backend_id"] == "analytical_l05"
    assert l05.CAPABILITIES["fidelity"] == "L0.5"
    assert l05.CAPABILITIES["collectives"] == ("allreduce_ring",)
    for unsupported in (
        "relay_re_serialization",
        "overlapped_chunk_transfers",
        "free_pipelining_depth",
        "compute_reduce_terms",
    ):
        assert unsupported in l05.CAPABILITIES["explicitly_unsupported"]


def test_loader_rejects_wrong_class_and_degenerate_values():
    landed = yaml.safe_load(
        (_TOPO / "ring8_free_params.yaml").read_text(encoding="utf-8")
    )
    try:
        l05.load_l05_config(landed)
    except ValueError as exc:
        assert "topology_class" in str(exc)
    else:
        raise AssertionError("expected ValueError for landed ring topology")
    data = yaml.safe_load(
        (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
    )
    for mutate, fragment in (
        (lambda d: d.update(ranks=1), "ranks >= 2"),
        (lambda d: d["link"].update(bytes_per_ns=0), "bytes_per_ns must be > 0"),
        (lambda d: d["link"].update(hop_latency_ns=-1), "hop_latency_ns must be >= 0"),
        (lambda d: d["nic"].update(injection_bytes_per_ns=0), "injection_bytes_per_ns must be > 0"),
    ):
        bad = yaml.safe_load(
            (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
        )
        mutate(bad)
        try:
            l05.load_l05_config(bad)
        except ValueError as exc:
            assert fragment in str(exc)
        else:
            raise AssertionError(f"expected ValueError for {fragment}")


def test_topology_yaml_validates_against_repo_contract():
    # The L0.5 topology rides the repo infragraph contract (analytical
    # dialect, extended to unidirectional_ring_with_serialization in
    # contract 0.2.0); the enum stays CLOSED otherwise — an unknown class is
    # rejected by the contract itself, so class extensions can only happen
    # through a schema_version bump.
    import json

    import jsonschema

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas"
            / "infragraph.schema.json"
        )
        .read_text(encoding="utf-8")
    )
    instance = yaml.safe_load(
        (_TOPO / "ring8_l05_free_params.yaml").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(instance)
    unknown = dict(instance, topology_class="store_and_forward_mesh")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(unknown)


def test_execute_rejects_wrong_collective_sizes_and_non_divisible_payloads():
    config = _config()
    bad_collective = w1.CollectiveOp(
        op_id="s000000-l000000-allgather",
        collective="allgather",
        comm_ranks=tuple(range(8)),
        payload_bytes=16384,
        step=0,
        layer=0,
    )
    try:
        l05.execute([bad_collective], config)
    except ValueError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("expected ValueError for allgather op")
    try:
        l05.execute(_ops(tp_size=4), config)
    except ValueError as exc:
        assert "comm group size" in str(exc)
    else:
        raise AssertionError("expected ValueError for rank mismatch")
    try:
        l05.execute(_ops(payload=1001), config)  # 1001 % 8 != 0
    except ValueError as exc:
        assert "A-L05-DIV" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-divisible payload")
