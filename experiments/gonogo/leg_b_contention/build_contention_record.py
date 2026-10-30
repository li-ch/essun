#!/usr/bin/env python3
"""Build the G7 leg-(b) contention-case record (exact, committed).

G7 go/no-go leg (b): ONE hard credit-and-contention case the exact
automaton resolves that the analytical law alone cannot — the
multi-source shared-link extension of the credit obligation automaton
(``essun.specir.credit_automaton``, landed G8 2026-10-30, extended G7).
Pure function of the live module: this script executes the two showcase
configurations under BOTH declared arbitration policies, emits every
exact trace, and writes ``contention_record_v1.json``; regenerating with
different bytes is an error (a change requires a NEW record version).
Nothing here is a run record (the automaton is not a run-producing
backend) and nothing changes a disposition: the automaton stays E0
evidence.

The two cases (parameters free; integer-exact):

- NO-WINDOW (G7-A): two 32-packet collectives whose windows never bind;
  the per-flow Eq. 3 laws are jointly infeasible on the shared link and
  the arbitration freedom moves a per-flow observable by (n-1)*u.
- GATED (G7-B): two 8-packet collectives under gating windows; the
  exact trace interleaves per-flow credit rhythms with the shared
  serializer (idle gaps with every flow backlogged), and BOTH fluid
  compositions — per-flow ``min(B, W_i/D)`` and aggregate
  ``min(B, sum W_i /D)`` — miss the machine in both directions, with
  the collective completion itself moving between policies.

Usage: ``.venv/bin/python experiments/gonogo/leg_b_contention/build_contention_record.py``
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from essun.specir import credit_automaton as ca

COMMITTED_COPY = (
    Path(__file__).resolve().parent / "contention_record_v1.json"
)

# The shared link of both cases: B=8 B/ns, L=300 ns, L_cr=100 ns (D=400 ns),
# packets of 256 B (u = 32 ns). Free parameters, integer-exact.
CASE_NO_WINDOW = {
    "link": {"bytes_per_ns": 8, "hop_latency_ns": 300},
    "tfc": {"credit_return_latency_ns": 100},
    "flows": [
        {"window_bytes": 8192, "packet_bytes": 256, "packets": 32},
        {"window_bytes": 8192, "packet_bytes": 256, "packets": 32},
    ],
}
CASE_GATED = {
    "link": {"bytes_per_ns": 8, "hop_latency_ns": 300},
    "tfc": {"credit_return_latency_ns": 100},
    "flows": [
        {"window_bytes": 1280, "packet_bytes": 256, "packets": 8},
        {"window_bytes": 1280, "packet_bytes": 256, "packets": 8},
    ],
}


def case_block(name: str, data: dict) -> dict:
    config = ca.load_shared_link_config(data)
    statements = {
        policy: ca.contention_statement(config, policy)
        for policy in ca.ARBITRATION_POLICIES
    }
    block = {
        "case": name,
        "config": {
            "link_bytes_per_ns": config.link_bytes_per_ns,
            "hop_latency_ns": config.hop_latency_ns,
            "credit_return_latency_ns": config.credit_return_latency_ns,
            "credit_loop_delay_ns_D": config.credit_loop_delay_ns,
            "flows": [
                {
                    "window_bytes": f.window_bytes,
                    "packet_bytes": f.packet_bytes,
                    "packets": f.packets,
                    "packets_per_window_k": f.window_bytes // f.packet_bytes,
                }
                for f in config.flows
            ],
        },
        "window_never_binds": ca.window_never_binds(config),
        "law_candidates": {
            "per_flow_alone_ns_exact": {
                f"flow_{i}": str(ca.law_alone_ns(config, i))
                for i in range(len(config.flows))
            },
            "aggregate_ns_exact": str(ca.law_aggregate_ns(config)),
        },
        "executions": statements,
    }
    if ca.window_never_binds(config):
        block["no_window_closed_forms"] = {
            policy: list(ca.no_window_closed_form(config, policy))
            for policy in ca.ARBITRATION_POLICIES
        }
    return block


def build() -> dict:
    record = {
        "record_id": "gonogo-legb-contention-v1",
        "date": "2026-10-30",
        "program": "G7 go/no-go leg (b)",
        "status": "PROPOSED",
        "evidence_level": "E0 (exact integer execution of free parameters; nothing measured, nothing standard-derived except the 256-byte credit unit UEC11-FC-R05)",
        "source_module": "essun.specir.credit_automaton (G8 + the G7 shared-link contention extension)",
        "assumptions": "experiments/vertical_slice/assumptions_credit_automaton.yaml (A-CA-* incl. the new A-CA-ARB / A-CA-SHARE)",
        "goldens": "tests/golden/test_credit_automaton_golden.py (G7-A/G7-B), tests/specir/test_credit_automaton.py (grids)",
        "what_the_law_alone_cannot_do": (
            "Eq. 3 is a per-flow steady-state cap min(B, W/(L+L_cr)) with NO "
            "composition operator across flows. Applied per flow on a shared "
            "link it predicts jointly infeasible alone-times; composed as an "
            "aggregate min(B, sum(W_i)/D) it predicts one completion, no "
            "per-flow values, and no idle-gap semantics — and it still "
            "misses the machine's exact time. The machine resolves the case "
            "exactly; its per-flow and collective observables MOVE with the "
            "arbitration freedom (A-CA-ARB), an input no law term encodes."
        ),
        "cases": [
            case_block("no_window_never_binds", CASE_NO_WINDOW),
            case_block("gated_burst_interaction", CASE_GATED),
        ],
    }
    return record


def main() -> int:
    record = build()
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if COMMITTED_COPY.is_file():
        current = COMMITTED_COPY.read_text(encoding="utf-8")
        if current == payload:
            print(f"contention_record_v1.json reproduces byte-identically ({digest[:12]}...)")
            return 0
        print(
            "ERROR: regenerated record differs from the committed copy; a "
            "change requires a NEW record version (contention_record_v2), "
            "never an edit",
            file=sys.stderr,
        )
        return 1
    COMMITTED_COPY.write_text(payload, encoding="utf-8")
    print(f"wrote contention_record_v1.json ({digest[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
