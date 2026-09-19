"""KARMO Model Router -- Phase E decision auditing.

Durably records routing decisions -- which host, which model, what
signal values were read, and why -- as a routing trace, never a
transcript. See docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md
Section 3.6 and Section 4's audit-log content restriction.

The content restriction is enforced here, not just documented: every
candidate dict in a decision's `candidates_considered` is validated
against a fixed field allowlist before it is ever serialized into the
durable record, and the whole payload is size-bounded. A future caller
that accidentally attached prompt text, a tool result, or anything else
unexpected to a candidate dict gets a raised, refused write here --
never a silent write of content this table must never hold.

Reuses core-service's existing durable-memory DSN (karmo_core_memory
role) rather than a new credential path, mirroring shadow_router.py's
own worker-health read for the same System-Fit Review reasoning: same
database, different table, explicit least-privilege grant per migration
010.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MEMORY_DSN_FILE = "/etc/karmo/core/postgres.dsn"

_ALLOWED_CANDIDATE_KEYS = frozenset({
    "host", "is_worker", "eligible", "reason", "loaded_models",
    "tool_capable_loaded", "data_age_seconds",
})
_MAX_CANDIDATES_JSON_BYTES = 8192
_VALID_DECISION_KINDS = frozenset({"shadow", "live"})
_VALID_OUTCOMES = frozenset({"success", "failure", "timeout"})


class RouterDecisionAuditError(RuntimeError):
    pass


def _validate_candidates_content_safe(candidates: tuple) -> None:
    """Structural enforcement of Section 4's audit-log content
    restriction -- not a convention, a refusal. Raises rather than
    silently writing anything outside the fixed, content-safe shape
    every candidate dict from compute_shadow_decision()/its future
    Phase D2 counterpart is built from."""
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise RouterDecisionAuditError("candidate must be a dict")
        unexpected = set(candidate) - _ALLOWED_CANDIDATE_KEYS
        if unexpected:
            raise RouterDecisionAuditError(
                f"candidate contains disallowed fields: {sorted(unexpected)}"
            )
    serialized = json.dumps(candidates, default=str)
    if len(serialized.encode("utf-8")) > _MAX_CANDIDATES_JSON_BYTES:
        raise RouterDecisionAuditError(
            "candidates payload exceeds the content-safety size bound -- refused, not truncated"
        )


class NullRouterDecisionRecorder:
    """Explicit degraded recorder, mirroring NullMemoryBackend/
    NullWorkerHealthReader, used when the memory DSN config is absent.
    Decisions are computed and (for shadow mode) still logged to stderr
    by the caller; only the durable record is skipped."""

    status = "DEGRADED_CONFIG_MISSING"

    def record_decision(self, *, correlation_id, decision_kind, decision):
        return None

    def record_outcome(self, *, decision_id, outcome, latency_ms=None):
        return None


@dataclass(frozen=True)
class RecordedDecision:
    decision_id: str


class PostgresRouterDecisionRecorder:
    def __init__(self, *, connection_factory):
        self._connection_factory = connection_factory

    def record_decision(self, *, correlation_id, decision_kind, decision) -> RecordedDecision:
        if decision_kind not in _VALID_DECISION_KINDS:
            raise RouterDecisionAuditError(f"invalid decision_kind: {decision_kind!r}")
        if not correlation_id or not isinstance(correlation_id, str):
            raise RouterDecisionAuditError("correlation_id is required")
        _validate_candidates_content_safe(decision.candidates_considered)

        decision_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_router_decisions
                    (decision_id, correlation_id, decision_kind, chosen_host,
                     chosen_model, reason, candidates)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    decision_id, correlation_id, decision_kind,
                    decision.chosen_host, decision.chosen_model, decision.reason,
                    json.dumps(list(decision.candidates_considered), default=str),
                ),
            )
        return RecordedDecision(decision_id=decision_id)

    def record_outcome(self, *, decision_id, outcome, latency_ms=None) -> None:
        if outcome not in _VALID_OUTCOMES:
            raise RouterDecisionAuditError(f"invalid outcome: {outcome!r}")
        if latency_ms is not None and (not isinstance(latency_ms, int) or latency_ms < 0):
            raise RouterDecisionAuditError("latency_ms must be a non-negative integer")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_router_decisions
                SET outcome=%s, outcome_latency_ms=%s, outcome_recorded_at=NOW()
                WHERE decision_id=%s::uuid
                """,
                (outcome, latency_ms, decision_id),
            )


def build_default_router_decision_recorder(dsn_file: str = DEFAULT_MEMORY_DSN_FILE):
    path = Path(dsn_file)
    if not path.is_file():
        return NullRouterDecisionRecorder()
    mode = path.stat().st_mode & 0o777
    if mode & 0o007:
        raise RouterDecisionAuditError("memory DSN file must not be accessible to other users")
    dsn = path.read_text(encoding="utf-8").strip()
    if not dsn:
        raise RouterDecisionAuditError("memory DSN file is empty")

    import psycopg

    def connection_factory():
        return psycopg.connect(dsn)

    return PostgresRouterDecisionRecorder(connection_factory=connection_factory)


def new_correlation_id() -> str:
    """One correlation ID per chat turn (Section 4), carried across
    routing, inference, authorization, tool execution, and the final
    response. Generated once at the top of _chat(), never derived from
    or containing any request content."""
    return str(uuid.uuid4())


def log_decision_recording_failure(exc: Exception) -> None:
    """Content-free failure log -- mirrors shadow_router.log_shadow_decision's
    own fail-safe stderr pattern. Never raises."""
    try:
        print(
            f"KARMO router decision audit write failed (chat response unaffected): "
            f"{type(exc).__name__}",
            file=sys.stderr, flush=True,
        )
    except Exception:
        pass
