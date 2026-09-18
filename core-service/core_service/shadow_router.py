"""KARMO Model Router -- Phase C shadow routing.

Decision-only: computes what the eventual Phase D routing policy would
choose for a real chat request, WITHOUT ever affecting the real answer or
the real candidate selection in operator.py's _chat(). See
docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.8 -- the
plan's own explicit correction (from GPT's review of the first draft)
that shadow mode must default to shadowing the DECISION only, never
duplicating real inference, since that would itself add load to the
exact contention problem this whole design exists to relieve. This is
also why this module only ever polls Ollama's /api/ps (a cheap,
non-inference GET) for karmo-ai01's signal -- never a timed generate
probe -- on every real chat request would itself be a meaningful load
source.

This module's output is logged for later analysis, never returned to a
caller and never consumed by anything that could act on it. Every
function here is fail-safe: any error degrades to "no data for this
host" rather than raising, so shadow observability can never break the
real chat response it rides alongside.

Design limitation, stated explicitly rather than left implicit: a host
counts as shadow-eligible only when a tool-calling-capable model is
currently LOADED (per /api/ps), not merely present in Ollama's model
library. This is deliberately the stricter signal -- Phase C is trying
to identify hosts that would answer FAST right now, matching the
contention-relief goal the whole plan exists for, not merely "could
eventually serve this after a cold load." Also stated explicitly: the
"prefer a worker over karmo-ai01" tiebreak below is a heuristic, not a
tuned weighted score -- Section 3.3 calls for weights "derived from real
telemetry," and no scheduled poller collecting that telemetry over time
exists yet (Phase A built the plumbing, not a running collector). This
heuristic is the honest starting point, not a claim of empirical
precision it doesn't have.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .host_health import DEFAULT_LOCAL_OLLAMA_BASE_URL, HostHealthError, poll_loaded_models

DEFAULT_WORKER_HEALTH_DSN_FILE = "/etc/karmo/core/postgres.dsn"
# Same DSN core-service already reads for durable memory -- same database
# (public.karmo_workers lives alongside conversation_memory/karmo_outbox),
# different tables. Reuse, not a new credential path (System-Fit Review).
KNOWN_WORKER_IDS = ("KARMO-WORKER01", "KARMO-WORKER02")
_DEFAULT_MAX_STALENESS_SECONDS = 120


class ShadowRouterError(RuntimeError):
    pass


class NullWorkerHealthReader:
    """Explicit degraded reader, mirroring durable_memory.NullMemoryBackend,
    used when worker-health DB config is absent. Shadow decisions simply
    treat every worker as having no data rather than failing."""

    status = "DEGRADED_CONFIG_MISSING"

    def get_worker_ollama_health(self, _worker_id: str):
        return None


def build_default_worker_health_reader(dsn_file: str = DEFAULT_WORKER_HEALTH_DSN_FILE):
    path = Path(dsn_file)
    if not path.is_file():
        return NullWorkerHealthReader()
    mode = path.stat().st_mode & 0o777
    if mode & 0o007:
        raise ShadowRouterError("worker health DSN file must not be accessible to other users")
    dsn = path.read_text(encoding="utf-8").strip()
    if not dsn:
        raise ShadowRouterError("worker health DSN file is empty")

    import psycopg

    from .worker_coordination import PostgresWorkerCoordinatorStore

    def connection_factory():
        return psycopg.connect(dsn)

    return PostgresWorkerCoordinatorStore(connection_factory)


@dataclass(frozen=True)
class ShadowDecision:
    chosen_host: str | None
    chosen_model: str | None
    reason: str
    candidates_considered: tuple = field(default_factory=tuple)
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def collect_shadow_signals(
    *,
    worker_health_reader,
    worker_ids: tuple = KNOWN_WORKER_IDS,
    karmo_ai01_base_url: str = DEFAULT_LOCAL_OLLAMA_BASE_URL,
    timeout: float = 2.0,
):
    """Gathers current signals for a shadow decision. Never raises --
    karmo-ai01 unreachable, or the worker reader failing, each degrade to
    "no data for this host" independently."""
    try:
        karmo_ai01_loaded_models = poll_loaded_models(karmo_ai01_base_url, timeout=timeout)
        karmo_ai01_reachable = True
    except HostHealthError:
        karmo_ai01_loaded_models = []
        karmo_ai01_reachable = False

    worker_snapshots = {}
    for worker_id in worker_ids:
        try:
            worker_snapshots[worker_id] = worker_health_reader.get_worker_ollama_health(worker_id)
        except Exception:
            worker_snapshots[worker_id] = None

    return karmo_ai01_reachable, karmo_ai01_loaded_models, worker_snapshots


def compute_shadow_decision(
    *,
    capability_registry: dict,
    karmo_ai01_reachable: bool,
    karmo_ai01_loaded_models: list,
    worker_snapshots: dict,
    required_capability: str = "tool_calling",
    max_staleness_seconds: float = _DEFAULT_MAX_STALENESS_SECONDS,
    now=None,
) -> ShadowDecision:
    """Pure decision function -- no I/O, fully testable without a real
    host or database. capability_registry: {model_id: frozenset(caps)}."""
    current_time = now or datetime.now(timezone.utc)

    def tool_capable(model_id):
        return required_capability in capability_registry.get(model_id, frozenset())

    candidates = []

    if karmo_ai01_reachable:
        tool_capable_loaded = [m for m in karmo_ai01_loaded_models if tool_capable(m)]
        candidates.append({
            "host": "karmo-ai01",
            "is_worker": False,
            "eligible": bool(tool_capable_loaded),
            "loaded_models": list(karmo_ai01_loaded_models),
            "tool_capable_loaded": tool_capable_loaded,
            "reason": None if tool_capable_loaded else "no_tool_capable_model_loaded",
        })
    else:
        candidates.append({
            "host": "karmo-ai01", "is_worker": False, "eligible": False,
            "reason": "unreachable",
        })

    for worker_id, snapshot in worker_snapshots.items():
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
        candidates.append({
            "host": worker_id, "is_worker": True,
            "eligible": bool(tool_capable_loaded),
            "loaded_models": list(loaded_models),
            "tool_capable_loaded": tool_capable_loaded,
            "data_age_seconds": age_seconds,
            "reason": None if tool_capable_loaded else "no_tool_capable_model_loaded",
        })

    eligible = [c for c in candidates if c["eligible"]]
    if not eligible:
        return ShadowDecision(
            chosen_host=None, chosen_model=None, reason="no_eligible_host",
            candidates_considered=tuple(candidates), computed_at=current_time,
        )

    workers_eligible = [c for c in eligible if c["is_worker"]]
    if workers_eligible:
        chosen = workers_eligible[0]
        reason = "worker_preferred_over_contended_karmo_ai01"
    else:
        chosen = eligible[0]
        reason = "only_karmo_ai01_eligible"

    return ShadowDecision(
        chosen_host=chosen["host"],
        chosen_model=chosen["tool_capable_loaded"][0],
        reason=reason,
        candidates_considered=tuple(candidates),
        computed_at=current_time,
    )


def log_shadow_decision(decision: ShadowDecision) -> None:
    """Structured, content-free log line -- host/model/reason/candidate
    shape only, per Section 3.6: never prompt content, secrets, or full
    tool results. Never raises."""
    try:
        summary = ", ".join(
            f"{c['host']}={'eligible' if c['eligible'] else 'excluded(' + str(c.get('reason')) + ')'}"
            for c in decision.candidates_considered
        )
        print(
            f"KARMO shadow-route decision: chosen={decision.chosen_host!r} "
            f"model={decision.chosen_model!r} reason={decision.reason!r} candidates=[{summary}]",
            file=sys.stderr, flush=True,
        )
    except Exception:
        pass
