"""Multi-plane switched topology backend tests (identity math + validation).

Hand-computed cases: every expected value is derived from first principles
with exact Fractions.
"""

from __future__ import annotations

from fractions import Fraction

import pytest
import yaml

from essun.backends.analytical import l0_multiplane
from essun.backends.analytical.l0_multiplane import (
    MultiplaneConfig,
    load_multiplane_config,
    multiplane_allreduce_time_ns,
    multiplane_traffic_per_rank,
)
from essun.workload.w1 import CollectiveOp


def make_ops(payload: int, ranks: int, count: int = 1):
    return [
        CollectiveOp(
            op_id=f"op-{i}",
            collective="allreduce",
            comm_ranks=tuple(range(ranks)),
            payload_bytes=payload,
            step=i,
            layer=0,
        )
        for i in range(count)
    ]


def make_infra(**overrides) -> MultiplaneConfig:
    params = dict(
        topology_id="multiplane-test",
        ranks=8,
        planes=4,
        port_bytes_per_ns=Fraction(2),
        pair_latency_ns=Fraction(100),
        endpoint_latency_ns=None,
    )
    params.update(overrides)
    return MultiplaneConfig(**params)


class TestIdentities:
    def test_traffic_identity_matches_crossbar(self):
        # per-rank wire traffic is the same 2*(r-1)/r * M regardless of planes
        assert multiplane_traffic_per_rank(4096, 8) == Fraction(2 * 7 * 4096, 8)

    def test_time_identity_hand_computed(self):
        infra = make_infra()  # N=8, P=4, B=2 B/ns, L=100 ns
        # t = 2*(8-1)/8 * (4096/4)/2 + 2*100 = (14/8 * 512) + 200 = 896 + 200
        t = multiplane_allreduce_time_ns(4096, 8, 4, infra)
        assert t == Fraction(896 + 200)

    def test_planes_divide_bandwidth_term_not_latency(self):
        one_plane = multiplane_allreduce_time_ns(4096, 8, 1, make_infra(planes=1))
        four_planes = multiplane_allreduce_time_ns(4096, 8, 4, make_infra(planes=4))
        b_one = four_planes - 2 * 100
        # bandwidth term with 4 planes is one quarter of the 1-plane term
        assert b_one * 4 == (one_plane - 2 * 100)

    def test_degenerate_single_plane_equals_crossbar_identity(self):
        from essun.backends.analytical.l0_crossbar import CrossbarConfig
        from essun.backends.analytical.l0_crossbar import (
            crossbar_allreduce_time_ns,
        )

        infra = make_infra(planes=1)
        cross = CrossbarConfig(
            topology_id="x",
            ranks=8,
            injection_bytes_per_ns=Fraction(2),
            pair_latency_ns=Fraction(100),
        )
        assert multiplane_allreduce_time_ns(4096, 8, 1, infra) == (
            crossbar_allreduce_time_ns(4096, 8, cross)
        )

    def test_endpoint_term_charged_once(self):
        with_e = multiplane_allreduce_time_ns(
            4096, 8, 4, make_infra(endpoint_latency_ns=Fraction(50))
        )
        without_e = multiplane_allreduce_time_ns(4096, 8, 4, make_infra())
        assert with_e - without_e == Fraction(50)


class TestExecute:
    def test_execute_emits_observables_and_conserves(self):
        infra = make_infra()  # 8 ranks * 4 planes; 4096 % (8*4) == 0
        result = l0_multiplane.execute(make_ops(4096, 8), infra)
        assert result["backend_id"] == "analytical_l0_multiplane"
        obs = result["observables"]
        assert obs["O-CONSERVATION"]["violations"] == 0
        # total wire = 2*(r-1)*M exactly
        assert Fraction(obs["O-CONSERVATION"]["total_wire_bytes_exact"]) == Fraction(
            2 * 7 * 4096
        )
        assert obs["O-CCT"]["ops"] == 1
        assert Fraction(obs["O-CCT"]["completion_time_ns_mean_exact"]) == Fraction(
            896 + 200
        )
        assert result["model"]["planes"] == 4
        assert result["model"]["aggregate_injection_bytes_per_ns_exact"] == "8"

    def test_non_divisible_payload_rejected(self):
        infra = make_infra()  # divisor = ranks * planes = 32
        with pytest.raises(ValueError, match="divisible"):
            l0_multiplane.execute(make_ops(33, 8), infra)

    def test_non_allreduce_rejected(self):
        infra = make_infra()
        op = CollectiveOp(
            op_id="bad", collective="allgather",
            comm_ranks=tuple(range(8)), payload_bytes=32, step=0, layer=0,
        )
        with pytest.raises(ValueError, match="not supported"):
            l0_multiplane.execute([op], infra)


class TestLoader:
    def test_loads_topology_file(self):
        data = yaml.safe_load(
            """
topology_id: multiplane16_free_v1
topology_class: multiplane_switch
ranks: 16
planes: 4
nic:
  port_bytes_per_ns: 16
link:
  pair_latency_ns: 200
"""
        )
        infra = load_multiplane_config(data)
        assert infra.ranks == 16
        assert infra.planes == 4
        assert infra.port_bytes_per_ns == Fraction(16)
        assert infra.endpoint_latency_ns is None

    def test_wrong_topology_class_rejected(self):
        data = {
            "topology_id": "x",
            "topology_class": "fully_connected_crossbar",
            "ranks": 8,
            "planes": 4,
            "nic": {"port_bytes_per_ns": 2},
            "link": {"pair_latency_ns": 100},
        }
        with pytest.raises(ValueError, match="topology_class"):
            load_multiplane_config(data)

    def test_degenerate_rejected(self):
        data = {
            "topology_id": "x",
            "topology_class": "multiplane_switch",
            "ranks": 1,
            "planes": 4,
            "nic": {"port_bytes_per_ns": 2},
            "link": {"pair_latency_ns": 100},
        }
        with pytest.raises(ValueError, match="ranks"):
            load_multiplane_config(data)
        data["ranks"] = 8
        data["planes"] = 0
        with pytest.raises(ValueError, match="planes"):
            load_multiplane_config(data)


class TestTopologyFiles:
    def test_landed_topology_files_load(self):
        from pathlib import Path

        topologies = Path(__file__).resolve().parents[2] / "experiments/topologies"
        files = sorted(topologies.glob("multiplane_switch*_free_params.yaml"))
        assert files, "no multi-plane topology files landed"
        for path in files:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            infra = load_multiplane_config(data)
            # the plane arithmetic identity holds by construction in every file:
            # aggregate = planes * port rate; planes >= 1; ranks >= 2
            assert infra.planes >= 1
            assert infra.ranks >= 2
