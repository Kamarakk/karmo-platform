from __future__ import annotations

import os
from pathlib import Path

import pytest

from core_service.router_decision_audit import (
    NullRouterDecisionRecorder,
    PostgresRouterDecisionRecorder,
    RouterDecisionAuditError,
    _validate_candidates_content_safe,
)
from core_service.shadow_router import ShadowDecision

psycopg = pytest.importorskip("psycopg")

REPO_ROOT = Path(__file__).resolve().parents[2]
PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")


def _conninfo():
    return (
        f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
        f"user={PG_USER} password={PG_PASSWORD}"
    )


def _connection_factory():
    return psycopg.connect(_conninfo())


def _reachable():
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _reachable(), reason="no isolated Core PostgreSQL available")


@pytest.fixture(scope="module", autouse=True)
def _schema():
    migrations_dir = REPO_ROOT / "core-service" / "core_service" / "migrations"
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute((migrations_dir / "010_router_decisions.sql").read_text())


def _decision(**overrides):
    defaults = dict(
        chosen_host="KARMO-WORKER01",
        chosen_model="qwen3:8b",
        reason="worker_preferred_over_contended_karmo_ai01",
        candidates_considered=(
            {"host": "karmo-ai01", "is_worker": False, "eligible": False, "reason": "unreachable"},
            {
                "host": "KARMO-WORKER01", "is_worker": True, "eligible": True,
                "loaded_models": ["qwen3:8b"], "tool_capable_loaded": ["qwen3:8b"],
                "data_age_seconds": 4.2,
            },
        ),
    )
    defaults.update(overrides)
    return ShadowDecision(**defaults)


def test_null_recorder_never_raises_and_returns_none():
    recorder = NullRouterDecisionRecorder()
    assert recorder.record_decision(correlation_id="c1", decision_kind="shadow", decision=_decision()) is None
    assert recorder.record_outcome(decision_id="does-not-exist", outcome="success") is None


def test_content_safe_candidates_pass_validation():
    _validate_candidates_content_safe(_decision().candidates_considered)  # must not raise


def test_disallowed_candidate_field_is_refused_not_silently_written():
    """Section 4's audit-log content restriction, enforced in code: a
    candidate dict carrying anything outside the fixed signal-only
    allowlist (e.g. a hypothetical future bug that attaches prompt text
    or a tool result to a candidate) must be refused, never durably
    written."""
    poisoned = (
        {"host": "karmo-ai01", "is_worker": False, "eligible": True, "reason": None,
         "prompt_text": "what is the weather"},
    )
    with pytest.raises(RouterDecisionAuditError, match="disallowed fields"):
        _validate_candidates_content_safe(poisoned)


def test_oversized_candidates_payload_is_refused_not_truncated():
    huge = tuple(
        {"host": f"host-{i}", "is_worker": False, "eligible": False, "reason": "x" * 200}
        for i in range(200)
    )
    with pytest.raises(RouterDecisionAuditError, match="content-safety size bound"):
        _validate_candidates_content_safe(huge)


def test_non_dict_candidate_is_refused():
    with pytest.raises(RouterDecisionAuditError, match="must be a dict"):
        _validate_candidates_content_safe(("not-a-dict",))


def test_postgres_recorder_round_trips_decision_and_outcome_against_real_db():
    recorder = PostgresRouterDecisionRecorder(connection_factory=_connection_factory)
    decision = _decision()

    recorded = recorder.record_decision(correlation_id="turn-abc-123", decision_kind="shadow", decision=decision)
    assert recorded.decision_id

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT correlation_id, decision_kind, chosen_host, chosen_model, reason, "
            "candidates, outcome FROM public.karmo_router_decisions WHERE decision_id=%s::uuid",
            (recorded.decision_id,),
        )
        row = cur.fetchone()
    assert row[0] == "turn-abc-123"
    assert row[1] == "shadow"
    assert row[2] == "KARMO-WORKER01"
    assert row[3] == "qwen3:8b"
    assert row[4] == "worker_preferred_over_contended_karmo_ai01"
    assert row[5] == list(decision.candidates_considered)
    assert row[6] is None  # no outcome recorded yet

    recorder.record_outcome(decision_id=recorded.decision_id, outcome="success", latency_ms=19268)

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT outcome, outcome_latency_ms, outcome_recorded_at FROM public.karmo_router_decisions "
            "WHERE decision_id=%s::uuid",
            (recorded.decision_id,),
        )
        outcome_row = cur.fetchone()
    assert outcome_row[0] == "success"
    assert outcome_row[1] == 19268
    assert outcome_row[2] is not None


def test_postgres_recorder_rejects_invalid_decision_kind():
    recorder = PostgresRouterDecisionRecorder(connection_factory=_connection_factory)
    with pytest.raises(RouterDecisionAuditError, match="invalid decision_kind"):
        recorder.record_decision(correlation_id="turn-1", decision_kind="not-a-real-kind", decision=_decision())


def test_postgres_recorder_rejects_missing_correlation_id():
    recorder = PostgresRouterDecisionRecorder(connection_factory=_connection_factory)
    with pytest.raises(RouterDecisionAuditError, match="correlation_id is required"):
        recorder.record_decision(correlation_id="", decision_kind="shadow", decision=_decision())


def test_postgres_recorder_rejects_invalid_outcome():
    recorder = PostgresRouterDecisionRecorder(connection_factory=_connection_factory)
    recorded = recorder.record_decision(correlation_id="turn-2", decision_kind="shadow", decision=_decision())
    with pytest.raises(RouterDecisionAuditError, match="invalid outcome"):
        recorder.record_outcome(decision_id=recorded.decision_id, outcome="not-a-real-outcome")


def test_postgres_recorder_refuses_poisoned_candidates_before_any_write():
    recorder = PostgresRouterDecisionRecorder(connection_factory=_connection_factory)
    poisoned_decision = _decision(candidates_considered=(
        {"host": "karmo-ai01", "is_worker": False, "eligible": True, "reason": None,
         "tool_result": {"secret": "leaked"}},
    ))
    with pytest.raises(RouterDecisionAuditError, match="disallowed fields"):
        recorder.record_decision(correlation_id="turn-3", decision_kind="shadow", decision=poisoned_decision)
