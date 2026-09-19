"""KARMO Model Router -- Phase D2 live routing decision.

Computes which host/model a real chat tool-calling turn should actually
use -- unlike shadow_router.py's compute_shadow_decision() (Phase C,
decision-only, never affects the real answer), a LiveRoutingDecision
returned "eligible" here is one operator.py is expected to actually
dispatch to. See docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md
Section 3.3/3.4 (routing strategy, capability-typed equally-authorized
fallback) and Section 6's D2 exit criteria.

Kept a pure decision function on purpose, mirroring
compute_shadow_decision()'s own discipline: no I/O, every signal
(health, worker-busy, breaker state) is collected by the caller and
passed in, so this is fully testable without a real host, database, or
circuit breaker instance. This also keeps the circuit breaker's own
stateful allow_request() (which has a real side effect: it marks a
HALF_OPEN trial pending) out of decision computation entirely --
breaker_states here is a pre-snapshotted, non-mutating view of state,
consulted only to decide ELIGIBILITY. The actual mutating
allow_request()/record_result() calls belong at operator.py's real
dispatch call site, immediately before/after the real attempt, not
here.

Design note directly from real evidence, not assumed: a worker with a
job already in flight (is_worker_busy) must never be treated as an
eligible routing candidate for a new request -- real load measurement
(docs/project-state/CURRENT_STATE.md, 2026-09-19) showed a second
concurrent request queued behind a busy worker costs 25-40+ seconds on
top of normal processing time, since poll_once() handles exactly one
job per cycle, fully synchronously. Being tool-capable and reachable
(Phase A/B's existing signal) is necessary but not sufficient
eligibility on its own.

Fail-closed throughout (Section 3.9): every signal that's missing,
stale, or ambiguous excludes a candidate rather than including it by
default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

_DEFAULT_MAX_STALENESS_SECONDS = 120
_OPEN = "OPEN"


class LiveRouterError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveRoutingDecision:
    chosen_host: str | None
    chosen_model: str | None
    is_worker: bool
    reason: str
    candidates_considered: tuple = field(default_factory=tuple)
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def compute_live_routing_decision(
    *,
    capability_registry: dict,
    karmo_ai01_reachable: bool,
    karmo_ai01_loaded_models: list,
    worker_snapshots: dict,
    worker_busy: dict,
    breaker_states: dict | None = None,
    required_capability: str = "tool_calling",
    max_staleness_seconds: float = _DEFAULT_MAX_STALENESS_SECONDS,
    now=None,
) -> LiveRoutingDecision:
    """Pure decision function -- no I/O, fully testable.

    capability_registry: {model_id: frozenset(caps)}.
    worker_busy: {worker_id: bool} -- True means mid-processing another
        job right now (see module docstring); missing entries are
        treated as busy (fail-closed, no data means don't trust it).
    breaker_states: {(host, model): "CLOSED"|"OPEN"|"HALF_OPEN"} --
        optional; a missing entry is treated as CLOSED (no observed
        failures yet). Only "OPEN" excludes a candidate -- HALF_OPEN is
        still eligible, since Section 3.5 requires exactly one trial
        request to be allowed through during recovery, and the real
        allow_request() gate (with its side effect) is enforced by the
        caller at actual dispatch time, not here.
    """
    current_time = now or datetime.now(timezone.utc)
    breaker_states = breaker_states or {}

    def tool_capable(model_id):
        return required_capability in capability_registry.get(model_id, frozenset())

    def breaker_open(host, model):
        return breaker_states.get((host, model)) == _OPEN

    candidates = []

    if karmo_ai01_reachable:
        tool_capable_loaded = [m for m in karmo_ai01_loaded_models if tool_capable(m)]
        not_breaker_tripped = [m for m in tool_capable_loaded if not breaker_open("karmo-ai01", m)]
        eligible = bool(not_breaker_tripped)
        reason = None
        if not tool_capable_loaded:
            reason = "no_tool_capable_model_loaded"
        elif not not_breaker_tripped:
            reason = "circuit_breaker_open"
        candidates.append({
            "host": "karmo-ai01", "is_worker": False, "eligible": eligible,
            "loaded_models": list(karmo_ai01_loaded_models),
            "tool_capable_loaded": not_breaker_tripped,
            "reason": reason,
        })
    else:
        candidates.append({
            "host": "karmo-ai01", "is_worker": False, "eligible": False,
            "reason": "unreachable",
        })

    for worker_id, snapshot in worker_snapshots.items():
        if worker_busy.get(worker_id, True):
            candidates.append({
                "host": worker_id, "is_worker": True, "eligible": False,
                "reason": "worker_busy",
            })
            continue
        if not snapshot or snapshot.get("ollama_snapshot") is None or snapshot.get("ollama_snapshot_at") is None:
            candidates.append({
                "host": worker_id, "is_worker": True, "eligible": False,
                "reason": "no_snapshot_yet",
            })
            continue
        snapshot_at = snapshot["ollama_snapshot_at"]
        age_seconds = (current_time - snapshot_at).total_seconds()
        if age_seconds > max_staleness_seconds:
            candidates.append({
                "host": worker_id, "is_worker": True, "eligible": False,
                "reason": "stale_snapshot", "data_age_seconds": age_seconds,
            })
            continue
        loaded_models = snapshot["ollama_snapshot"].get("loaded_models", [])
        tool_capable_loaded = [m for m in loaded_models if tool_capable(m)]
        not_breaker_tripped = [m for m in tool_capable_loaded if not breaker_open(worker_id, m)]
        eligible = bool(not_breaker_tripped)
        reason = None
        if not tool_capable_loaded:
            reason = "no_tool_capable_model_loaded"
        elif not not_breaker_tripped:
            reason = "circuit_breaker_open"
        candidates.append({
            "host": worker_id, "is_worker": True,
            "eligible": eligible,
            "loaded_models": list(loaded_models),
            "tool_capable_loaded": not_breaker_tripped,
            "data_age_seconds": age_seconds,
            "reason": reason,
        })

    eligible_candidates = [c for c in candidates if c["eligible"]]
    if not eligible_candidates:
        return LiveRoutingDecision(
            chosen_host=None, chosen_model=None, is_worker=False,
            reason="no_eligible_host", candidates_considered=tuple(candidates),
            computed_at=current_time,
        )

    workers_eligible = [c for c in eligible_candidates if c["is_worker"]]
    if workers_eligible:
        chosen = workers_eligible[0]
        reason = "worker_preferred_over_contended_karmo_ai01"
    else:
        chosen = eligible_candidates[0]
        reason = "only_karmo_ai01_eligible"

    return LiveRoutingDecision(
        chosen_host=chosen["host"],
        chosen_model=chosen["tool_capable_loaded"][0],
        is_worker=chosen["is_worker"],
        reason=reason,
        candidates_considered=tuple(candidates),
        computed_at=current_time,
    )
