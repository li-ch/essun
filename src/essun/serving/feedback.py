"""Network-to-serving feedback loop (first slice).

One or more emitted network
observations from run N deterministically alter the serving/decode state
used by run N+1 (and, inside a run, from one collective to the next).

Serving-state knob chosen (the bar says pick ONE and document it):
**decode batch size**. In dense TP decode the per-op AllReduce payload is
the activation tensor, whose size is linear in the decode batch:
``payload_bytes = decode_batch_size * per_sample_bytes`` where
``per_sample_bytes`` is an explicit FREE PARAMETER (hidden size x dtype
bytes per sample would be model-derived; this slice keeps it free and
never standard-derived; provenance rules). To keep the
L0 equal-chunk construction valid (divisibility assumption A-L0-DIV),
``per_sample_bytes`` should be a multiple of the TP group size; the
backend's own :func:`essun.backends.analytical.l0.require_divisible`
gate fires loudly otherwise, and that gate still guards this module.

Driver observable chosen: **O-CCT** (the registered analytical completion
time, emitted with exact Fractions). The run-level mean drives the
no-overlap case (feedback between runs); per-op completion times drive
the overlap case (feedback within a run). Alternatives and why they were
not picked are recorded in the module notes.

Policy (deterministic threshold controller, the only registered policy id
in this slice): compare the observed O-CCT value against an exact
threshold — above, decrease the decode batch by one; below, increase it
by one; EXACTLY EQUAL, hold (fixed tie-breaking; decidable because O-CCT
carries exact Fractions). The new batch is clamped to
``[min_batch, max_batch]``. Same inputs -> same feedback -> same
downstream values by construction: no RNG, no wall-clock, list-position
ordering.

"Overlap" naming honesty note: the overlap case means feedback whose
latency is shorter than one run — the observation of collective k shapes
collective k+1 *within* run N. It does NOT mean overlapped collective
execution, which the L0 backend explicitly declares unsupported; ops
still execute sequentially under the L0 per-op identity. Because the L0
identity is per-op (completion of op k does not depend on op k-1),
executing each rewritten op through the real backend one at a time is
equivalent to batch execution for per-op values, while every backend
gate (O-CONSERVATION, A-L0-DIV divisibility, O-TRAFFIC-IMBALANCE) still
fires per op.

Evidence label: [IMPLEMENTED_UNVERIFIED] — identities and determinism
tested (golden + negative + replay), no empirical claim about real
serving systems.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Mapping

from essun.backends.analytical import l0
from essun.evidence.store import canonical_json
from essun.workload import w1

# The only policy/driver pair registered in this slice; anything else is a
# named gap, not a silent fallback.
POLICY_ID = "cct_threshold_batch"
POLICY_IDS = (POLICY_ID,)
DRIVER_OBSERVABLE = "O-CCT"
DRIVER_OBSERVABLES = (DRIVER_OBSERVABLE,)

# O-CCT observation field carrying the exact run-level mean.
_CCT_MEAN_FIELD = "completion_time_ns_mean_exact"


def _as_fraction(value: Any) -> Fraction:
    # str() first so floats/decimal strings are interpreted exactly,
    # matching the platform's arithmetic policy.
    return Fraction(str(value))


@dataclass(frozen=True)
class ServingState:
    """The serving/decode state one feedback step acts on (knob: batch size)."""

    decode_batch_size: int

    def __post_init__(self) -> None:
        if int(self.decode_batch_size) < 1:
            raise ValueError(f"decode_batch_size must be >= 1, got {self.decode_batch_size}")

    def to_dict(self) -> dict:
        return {"decode_batch_size": int(self.decode_batch_size)}


@dataclass(frozen=True)
class BatchCCTPolicy:
    """Deterministic O-CCT-threshold controller over the decode batch size.

    ``next_state`` applies: observed cct > threshold -> batch-1;
    observed cct < threshold -> batch+1; observed cct == threshold -> hold
    (fixed tie-breaking). The result is clamped to [min_batch, max_batch].
    ``payload_bytes`` maps state to the W1 AllReduce payload
    ``decode_batch_size * per_sample_bytes`` (free parameters throughout).
    """

    threshold_ns: Fraction
    min_batch: int
    max_batch: int
    per_sample_bytes: int
    policy_id: str = POLICY_ID
    driver_observable: str = DRIVER_OBSERVABLE

    def __post_init__(self) -> None:
        object.__setattr__(self, "threshold_ns", _as_fraction(self.threshold_ns))
        self.validate()

    def validate(self) -> None:
        if self.policy_id not in POLICY_IDS:
            raise ValueError(
                f"unknown feedback policy_id {self.policy_id!r}; registered: {list(POLICY_IDS)}"
            )
        if self.driver_observable not in DRIVER_OBSERVABLES:
            raise ValueError(
                f"unknown driver observable {self.driver_observable!r}; registered: "
                f"{list(DRIVER_OBSERVABLES)} (O-TRAFFIC-IMBALANCE is identically 0 "
                "at L0 — an algebraic self-check — so it cannot drive feedback at "
                "this fidelity)"
            )
        if self.threshold_ns < 0:
            raise ValueError(f"threshold_ns must be >= 0, got {self.threshold_ns}")
        if self.min_batch < 1:
            raise ValueError(f"min_batch must be >= 1, got {self.min_batch}")
        if self.max_batch < self.min_batch:
            raise ValueError(
                f"max_batch {self.max_batch} < min_batch {self.min_batch}"
            )
        if self.per_sample_bytes < 1:
            raise ValueError(
                f"per_sample_bytes must be >= 1, got {self.per_sample_bytes}"
            )

    def payload_bytes(self, state: ServingState) -> int:
        return int(state.decode_batch_size) * self.per_sample_bytes

    def next_state(self, state: ServingState, observed_cct_exact: Any) -> ServingState:
        """One deterministic feedback step from an exact O-CCT value."""
        cct = _as_fraction(observed_cct_exact)
        batch = int(state.decode_batch_size)
        if cct > self.threshold_ns:
            target = batch - 1
        elif cct < self.threshold_ns:
            target = batch + 1
        else:  # exact equality: hold — the documented tie-breaking
            target = batch
        clamped = max(self.min_batch, min(self.max_batch, target))
        return ServingState(clamped)

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "driver_observable": self.driver_observable,
            "threshold_ns_exact": str(self.threshold_ns),
            "threshold_ns": float(self.threshold_ns),
            "min_batch": self.min_batch,
            "max_batch": self.max_batch,
            "per_sample_bytes": self.per_sample_bytes,
        }


def policy_from_config(data: Mapping[str, Any]) -> BatchCCTPolicy:
    """Build the policy from a configuration mapping (YAML-shaped).

    Required keys: ``policy_id``, ``threshold_ns``, ``min_batch``,
    ``max_batch``, ``per_sample_bytes``. Optional: ``driver_observable``
    (default ``O-CCT``). Unknown policy ids or drivers are rejected loudly
    with the registered set named — a silent fallback would fabricate a
    feedback semantic nobody declared.
    """
    missing = [
        key
        for key in ("policy_id", "threshold_ns", "min_batch", "max_batch", "per_sample_bytes")
        if key not in data
    ]
    if missing:
        raise ValueError(f"feedback policy config missing key(s) {missing}")
    return BatchCCTPolicy(
        policy_id=str(data["policy_id"]),
        threshold_ns=_as_fraction(data["threshold_ns"]),
        min_batch=int(data["min_batch"]),
        max_batch=int(data["max_batch"]),
        per_sample_bytes=int(data["per_sample_bytes"]),
        driver_observable=str(data.get("driver_observable", DRIVER_OBSERVABLE)),
    )


# ---------------------------------------------------------------------------
# No-overlap case: feedback applies only BETWEEN runs
# ---------------------------------------------------------------------------


def cct_mean_exact(observations: Mapping[str, Any]) -> Fraction:
    """Extract the exact run-level O-CCT mean from a backend observations dict."""
    try:
        cct = observations["observables"][DRIVER_OBSERVABLE]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"observations carry no {DRIVER_OBSERVABLE!r} entry; cannot drive "
            f"feedback from observables {sorted(observations.get('observables', {}))}"
        ) from exc
    if cct.get("kind") != "analytical":
        raise ValueError(
            f"{DRIVER_OBSERVABLE} observation declares kind {cct.get('kind')!r}; "
            "expected 'analytical' (registry mismatch)"
        )
    if _CCT_MEAN_FIELD not in cct:
        raise ValueError(f"O-CCT observation missing {_CCT_MEAN_FIELD!r}")
    return _as_fraction(cct[_CCT_MEAN_FIELD])


def apply_between_runs(
    policy: BatchCCTPolicy, state: ServingState, observations: Mapping[str, Any]
) -> ServingState:
    """No-overlap feedback: run N's O-CCT mean -> run N+1's serving state."""
    return policy.next_state(state, cct_mean_exact(observations))


def next_w1_config(
    policy: BatchCCTPolicy, state: ServingState, base_config: w1.W1Config
) -> w1.W1Config:
    """Run N+1's workload config: the AllReduce payload implied by the state."""
    return dataclasses.replace(base_config, allreduce_bytes=policy.payload_bytes(state))


def no_overlap_rounds(
    policy: BatchCCTPolicy,
    initial_state: ServingState,
    base_config: w1.W1Config,
    infra: l0.InfraConfig,
    rounds: int,
    execute: Callable = l0.execute,
) -> dict:
    """Drive the between-runs loop for ``rounds`` rounds (round 0 is run N).

    Round i: write the state's payload into the W1 config, generate ops
    (deterministic step-major/layer-minor order), execute on the backend,
    observe the exact O-CCT mean, then apply the policy for round i+1.
    Returns a JSON-serializable record (exact strings alongside floats,
    per-op digests for replay); identical inputs yield identical records.
    """
    if rounds < 1:
        raise ValueError(f"rounds must be >= 1, got {rounds}")
    state = initial_state
    records = []
    for index in range(rounds):
        config = next_w1_config(policy, state, base_config)
        ops = w1.generate_w1_ops(config)
        observations = execute(ops, infra)
        cct = cct_mean_exact(observations)
        records.append(
            {
                "round": index,
                "decode_batch_size": state.decode_batch_size,
                "allreduce_bytes": config.allreduce_bytes,
                "cct_mean_ns_exact": str(cct),
                "cct_mean_ns": float(cct),
                "observations_sha256": _digest(observations),
            }
        )
        state = apply_between_runs(policy, state, observations)
    return {
        "policy": policy.to_dict(),
        "initial_state": initial_state.to_dict(),
        "rounds": records,
        "final_state": state.to_dict(),
    }


# ---------------------------------------------------------------------------
# Overlap case: feedback applies WITHIN a run, collective -> next collective
# ---------------------------------------------------------------------------


def apply_within_run(
    policy: BatchCCTPolicy,
    initial_state: ServingState,
    ops: list,
    infra: l0.InfraConfig,
    execute: Callable = l0.execute,
) -> dict:
    """In-run feedback: op k's O-CCT shapes op k+1's payload.

    Walks ``ops`` in list order (the generators' deterministic topological
    emission order — fixed tie-breaking by construction). For each op the
    current state's payload is written into the op, the op is executed
    through the real backend (single-op call, so every backend gate —
    conservation, divisibility, imbalance — fires), the exact completion
    time is observed, and the policy advances the state for the NEXT op.
    """
    if not ops:
        raise ValueError("apply_within_run requires a non-empty op list")
    state = initial_state
    trace = []
    for op in ops:
        batch_before = state.decode_batch_size
        payload = policy.payload_bytes(state)
        rewritten = dataclasses.replace(op, payload_bytes=payload)
        result = execute([rewritten], infra)
        cct = _as_fraction(result["per_op"][0]["completion_time_ns_exact"])
        state = policy.next_state(state, cct)
        trace.append(
            {
                "op_id": op.op_id,
                "batch_size": batch_before,
                "payload_bytes": payload,
                "cct_ns_exact": str(cct),
                "cct_ns": float(cct),
                "next_batch_size": state.decode_batch_size,
            }
        )
    return {
        "policy": policy.to_dict(),
        "initial_state": initial_state.to_dict(),
        "ops": len(ops),
        "trace": trace,
        "final_state": state.to_dict(),
    }


def _digest(observations: Mapping[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(observations).encode("utf-8")).hexdigest()
