import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core_service.control import ApprovalEngine, ApprovalState, CapabilityClass, CoreControlError


class MemoryApprovalStore:
    """Persistence double that survives ApprovalEngine replacement."""

    def __init__(self):
        self.records = {}

    def save(self, record):
        self.records[record.approval_id] = copy.deepcopy(record)

    def get(self, approval_id):
        record = self.records.get(approval_id)
        return copy.deepcopy(record) if record is not None else None


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def request(engine):
    return engine.request(
        requester="kamara",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments={"host": "karmo-ai01"},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
        ttl_seconds=60,
    )


def test_approved_record_survives_engine_restart_and_executes_once():
    store = MemoryApprovalStore()
    clock = Clock()
    first = ApprovalEngine(store=store, clock=clock)
    record = request(first)
    first.approve(record.approval_id, approver="kamara", authorized_executor="worker-1")

    restarted = ApprovalEngine(store=store, clock=clock)
    restored = restarted.get(record.approval_id)
    assert restored.state == ApprovalState.APPROVED
    assert restored.authorized_executor == "worker-1"

    assert restarted.execute(
        record.approval_id,
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
        action=lambda: {"ok": True},
    ) == {"ok": True}

    second_restart = ApprovalEngine(store=store, clock=clock)
    assert second_restart.get(record.approval_id).state == ApprovalState.EXECUTED
    with pytest.raises(CoreControlError):
        second_restart.execute(
            record.approval_id,
            tool_id="karmolab.host_health",
            tool_version="1",
            arguments={"host": "karmo-ai01"},
            executor_identity="worker-1",
            action=lambda: {"should": "not run"},
        )


def test_denial_and_cancellation_remain_terminal_after_restart():
    store = MemoryApprovalStore()
    clock = Clock()

    denied_engine = ApprovalEngine(store=store, clock=clock)
    denied = request(denied_engine)
    denied_engine.deny(denied.approval_id, approver="kamara", reason="not authorized")
    restarted = ApprovalEngine(store=store, clock=clock)
    assert restarted.get(denied.approval_id).state == ApprovalState.DENIED
    with pytest.raises(CoreControlError):
        restarted.approve(denied.approval_id, approver="kamara")

    cancelled_engine = ApprovalEngine(store=store, clock=clock)
    cancelled = request(cancelled_engine)
    cancelled_engine.approve(cancelled.approval_id, approver="kamara", authorized_executor="worker-1")
    cancelled_engine.cancel(cancelled.approval_id, actor="kamara", reason="withdrawn")
    restarted_again = ApprovalEngine(store=store, clock=clock)
    restored = restarted_again.get(cancelled.approval_id)
    assert restored.state == ApprovalState.CANCELLED
    assert restored.authorized_executor is None
    with pytest.raises(CoreControlError):
        restarted_again.execute(
            cancelled.approval_id,
            tool_id="karmolab.host_health",
            tool_version="1",
            arguments={"host": "karmo-ai01"},
            executor_identity="worker-1",
            action=lambda: None,
        )


def test_expired_approval_does_not_revive_after_restart():
    store = MemoryApprovalStore()
    clock = Clock()
    engine = ApprovalEngine(store=store, clock=clock)
    record = request(engine)
    engine.approve(record.approval_id, approver="kamara", authorized_executor="worker-1")
    clock.advance(61)

    restarted = ApprovalEngine(store=store, clock=clock)
    assert restarted.get(record.approval_id).state == ApprovalState.EXPIRED
    assert store.get(record.approval_id).state == ApprovalState.EXPIRED
    with pytest.raises(CoreControlError):
        restarted.execute(
            record.approval_id,
            tool_id="karmolab.host_health",
            tool_version="1",
            arguments={"host": "karmo-ai01"},
            executor_identity="worker-1",
            action=lambda: None,
        )


def test_nonpositive_ttl_is_refused():
    engine = ApprovalEngine(store=MemoryApprovalStore(), clock=Clock())
    with pytest.raises(CoreControlError):
        engine.request(
            requester="kamara",
            tool_id="example.safe",
            tool_version="1",
            arguments={},
            authority_class=CapabilityClass.READ.value,
            ttl_seconds=0,
        )


def test_staged_schema_contains_restart_and_replay_controls():
    migration = Path(__file__).parents[1] / "core_service" / "migrations" / "001_core_v2_substrate.sql"
    sql = migration.read_text()
    assert "idempotency_key TEXT NOT NULL UNIQUE" in sql
    assert "audit_trail JSONB NOT NULL" in sql
    assert "idx_core_approval_state_expiry" in sql
    assert "evidence_digest TEXT" in sql
    assert "verification_state TEXT" in sql
