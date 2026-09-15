from datetime import datetime, timedelta, timezone

import pytest

from core_service.control import (
    ApprovalRequirement,
    ApprovalState,
    CoreControlError,
    arguments_digest,
)
from core_service.persistence import PostgresExecutionCoordinator


APPROVAL_ID = "00000000-0000-0000-0000-000000000101"


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class FakeConnectionFactory:
    def __init__(self, cursor):
        self.cursor = cursor
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return FakeConnection(self.cursor)


def _approval_row(*, requester="kamara", authority=None):
    now = datetime.now(timezone.utc)
    authority = authority or ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK.value
    args = {"host": "karmo-ai01"}
    return (
        APPROVAL_ID,
        requester,
        "karmolab.host_health",
        "1",
        arguments_digest("karmolab.host_health", "1", args),
        authority,
        ApprovalState.APPROVED.value,
        "kamara",
        "worker-1",
        None,
        [],
        2,
        now - timedelta(minutes=1),
        now + timedelta(minutes=10),
    )


def _claim(coordinator, **overrides):
    kwargs = {
        "approval_id": APPROVAL_ID,
        "idempotency_key": "task-1:health:1",
        "task_id": None,
        "tool_id": "karmolab.host_health",
        "tool_version": "1",
        "requester": "kamara",
        "model_identity": "qwen3:8b",
        "executor_identity": "worker-1",
        "arguments": {"host": "karmo-ai01"},
        "authority_decision": ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK.value,
    }
    kwargs.update(overrides)
    return coordinator.claim(**kwargs)


def test_claim_rejects_requester_mismatch_before_invocation_insert():
    cursor = FakeCursor([_approval_row()])
    factory = FakeConnectionFactory(cursor)
    coordinator = PostgresExecutionCoordinator(factory)

    with pytest.raises(CoreControlError, match="approval requester mismatch"):
        _claim(coordinator, requester="other-requester")

    assert factory.calls == 1
    assert len(cursor.statements) == 1
    assert "SELECT" in cursor.statements[0][0]
    assert not any("INSERT INTO public.tool_invocation_ledger" in sql for sql, _ in cursor.statements)


def test_claim_rejects_authority_mismatch_before_invocation_insert():
    cursor = FakeCursor([_approval_row()])
    factory = FakeConnectionFactory(cursor)
    coordinator = PostgresExecutionCoordinator(factory)

    with pytest.raises(CoreControlError, match="approval authority requirement mismatch"):
        _claim(coordinator, authority_decision=ApprovalRequirement.EXPLICIT_PER_CALL.value)

    assert factory.calls == 1
    assert len(cursor.statements) == 1
    assert "SELECT" in cursor.statements[0][0]
    assert not any("INSERT INTO public.tool_invocation_ledger" in sql for sql, _ in cursor.statements)


def test_claim_accepts_matching_requester_and_authority_and_claims_once():
    cursor = FakeCursor([_approval_row(), ("inserted",)])
    factory = FakeConnectionFactory(cursor)
    coordinator = PostgresExecutionCoordinator(factory)

    claim = _claim(coordinator)

    assert claim.approval_id == APPROVAL_ID
    assert claim.idempotency_key == "task-1:health:1"
    assert factory.calls == 1
    assert sum("INSERT INTO public.tool_invocation_ledger" in sql for sql, _ in cursor.statements) == 1
    assert sum("UPDATE public.core_approval_records" in sql for sql, _ in cursor.statements) == 1
