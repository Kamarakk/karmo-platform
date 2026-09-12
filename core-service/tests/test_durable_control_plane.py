import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from core_service.control import (
    ApprovalEngine,
    ApprovalRequirement,
    ApprovalState,
    CapabilityClass,
    CoreControlError,
)
from core_service.dispatcher import CapabilityDispatcher, DispatchError
from core_service.persistence import PersistenceError
from core_service.recovery import TaskRecoveryManager
from core_service.task_state import InMemoryTaskStore, TaskState, TaskStateError


class MemoryApprovalStore:
    """Persistence double that survives ApprovalEngine replacement."""

    def __init__(self):
        self.records = {}

    def save(self, record):
        self.records[record.approval_id] = copy.deepcopy(record)

    def get(self, approval_id):
        record = self.records.get(approval_id)
        return copy.deepcopy(record) if record is not None else None


class MemoryLedger:
    def __init__(self):
        self.by_key = {}
        self.completed = {}
        self.counter = 0

    def begin(self, **kwargs):
        key = kwargs["idempotency_key"]
        if key in self.by_key:
            raise PersistenceError(f"duplicate invocation idempotency key: {key}")
        self.counter += 1
        invocation_id = f"inv-{self.counter}"
        self.by_key[key] = {"invocation_id": invocation_id, **kwargs}
        return invocation_id

    def complete(self, invocation_id, **kwargs):
        if invocation_id in self.completed:
            raise PersistenceError("invocation is already terminal")
        self.completed[invocation_id] = dict(kwargs)


class MemoryExecutionCoordinator:
    """Transaction-boundary double for dispatcher tests."""

    def __init__(self, approval_engine):
        self.approval_engine = approval_engine
        self.claims = {}
        self.finished = {}
        self.counter = 0

    def claim(self, **kwargs):
        key = kwargs["idempotency_key"]
        if key in self.claims:
            raise PersistenceError(f"duplicate invocation idempotency key: {key}")
        record = self.approval_engine.get(kwargs["approval_id"])
        if record.state != ApprovalState.APPROVED:
            raise CoreControlError(f"cannot claim from {record.state.value}")
        if record.authorized_executor != kwargs["executor_identity"]:
            raise CoreControlError("executor identity mismatch")
        self.counter += 1
        claim = SimpleNamespace(
            invocation_id=f"claim-{self.counter}",
            approval_id=kwargs["approval_id"],
            idempotency_key=key,
        )
        record.execution_binding = claim.invocation_id
        record.transition(ApprovalState.CLAIMED, "system", "execution authority claimed", datetime.now(timezone.utc))
        self.approval_engine._persist(record)
        self.claims[key] = claim
        return claim

    def finish(self, claim, **kwargs):
        record = self.approval_engine.get(claim.approval_id)
        if record.state != ApprovalState.CLAIMED:
            raise PersistenceError("approval is not claimed")
        target = ApprovalState.EXECUTED if kwargs["status"] == "EXECUTED" else ApprovalState.FAILED
        record.transition(target, "system", kwargs["status"].lower(), datetime.now(timezone.utc))
        self.approval_engine._persist(record)
        self.finished[claim.invocation_id] = dict(kwargs)


class EventfulMemoryTaskStore(InMemoryTaskStore):
    def __init__(self):
        super().__init__()
        self.events = {}

    def append_event(self, *, event_key, task_id, event_type, actor, payload=None):
        if event_key in self.events:
            raise TaskStateError(f"duplicate event key: {event_key}")
        self.events[event_key] = {
            "task_id": task_id,
            "event_type": event_type,
            "actor": actor,
            "payload": dict(payload or {}),
        }
        return event_key


class Registry:
    def __init__(self, requirement):
        self.record = SimpleNamespace(
            deprecated=False,
            computed_approval_requirement=requirement,
        )

    def get(self, tool_id, version):
        return self.record if (tool_id, version) == ("karmolab.host_health", "1") else None


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

    observed = []

    def action():
        observed.append(restarted.get(record.approval_id).state)
        with pytest.raises(CoreControlError):
            restarted.execute(
                record.approval_id,
                tool_id="karmolab.host_health",
                tool_version="1",
                arguments={"host": "karmo-ai01"},
                executor_identity="worker-1",
                action=lambda: {"duplicate": True},
            )
        return {"ok": True}

    assert restarted.execute(
        record.approval_id,
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
        action=action,
    ) == {"ok": True}
    assert observed == [ApprovalState.CLAIMED]

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


def test_dispatcher_requires_idempotency_key_when_durable_ledger_enabled():
    dispatcher = CapabilityDispatcher(
        registry=Registry(ApprovalRequirement.NONE),
        approval_engine=ApprovalEngine(),
        handlers={("karmolab.host_health", "1"): lambda args: {"host": args["host"], "ok": True}},
        invocation_ledger=MemoryLedger(),
    )
    with pytest.raises(DispatchError):
        dispatcher.dispatch(
            requester="kamara",
            tool_id="karmolab.host_health",
            version="1",
            arguments={"host": "karmo-ai01"},
            executor_identity="worker-1",
        )


def test_dispatcher_records_actual_execution_and_refuses_replay_key():
    ledger = MemoryLedger()
    dispatcher = CapabilityDispatcher(
        registry=Registry(ApprovalRequirement.NONE),
        approval_engine=ApprovalEngine(),
        handlers={("karmolab.host_health", "1"): lambda args: {"host": args["host"], "ok": True}},
        invocation_ledger=ledger,
    )
    kwargs = dict(
        requester="kamara",
        tool_id="karmolab.host_health",
        version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
        task_id=None,
        model_identity="qwen3:8b",
        idempotency_key="task-1:karmolab.host_health:1",
    )
    decision = dispatcher.dispatch(**kwargs)
    assert decision.executed is True
    assert decision.invocation_id == "inv-1"
    assert ledger.completed["inv-1"]["status"] == "EXECUTED"
    assert ledger.completed["inv-1"]["result_digest"]

    with pytest.raises(PersistenceError):
        dispatcher.dispatch(**kwargs)


def test_approved_dispatch_claims_authority_before_handler_and_blocks_replay():
    approvals = ApprovalEngine(store=MemoryApprovalStore())
    pending = request(approvals)
    approvals.approve(pending.approval_id, approver="kamara", authorized_executor="worker-1")
    coordinator = MemoryExecutionCoordinator(approvals)
    observed = []

    def handler(args):
        observed.append(approvals.get(pending.approval_id).state)
        return {"host": args["host"], "ok": True}

    dispatcher = CapabilityDispatcher(
        registry=Registry(ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK),
        approval_engine=approvals,
        handlers={("karmolab.host_health", "1"): handler},
        execution_coordinator=coordinator,
    )
    kwargs = dict(
        requester="kamara",
        tool_id="karmolab.host_health",
        version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
        approval_id=pending.approval_id,
        idempotency_key="task-2:health:1",
    )
    decision = dispatcher.dispatch(**kwargs)
    assert decision.executed is True
    assert observed == [ApprovalState.CLAIMED]
    assert approvals.get(pending.approval_id).state == ApprovalState.EXECUTED
    with pytest.raises((PersistenceError, DispatchError)):
        dispatcher.dispatch(**kwargs)


def test_restart_moves_running_work_to_recovery_required_without_replay():
    store = EventfulMemoryTaskStore()
    task = store.create(
        objective="inspect host",
        requester="kamara",
        allowed_capabilities=["karmolab.host_health"],
    )
    task.transition(TaskState.PLANNED, actor="karmo")
    task.transition(TaskState.READY, actor="karmo")
    task.transition(TaskState.RUNNING, actor="worker-1")
    store.save(task, expected_version=task.state_version)

    recovered = TaskRecoveryManager(store).reconcile_after_restart()
    assert len(recovered) == 1
    restored = store.get(task.task_id)
    assert restored.state == TaskState.RECOVERY_REQUIRED
    assert restored.next_action == "reconcile prior execution evidence before continuing"
    assert len(store.events) == 1
    event = next(iter(store.events.values()))
    assert event["payload"]["automatic_replay"] is False
    assert event["payload"]["prior_state"] == TaskState.RUNNING.value

    assert TaskRecoveryManager(store).reconcile_after_restart() == []
    assert len(store.events) == 1


def test_stale_task_writer_is_rejected():
    store = InMemoryTaskStore()
    task = store.create(objective="inspect", requester="kamara")
    first = store.get(task.task_id)
    second = store.get(task.task_id)
    assert first.state_version == second.state_version

    first.transition(TaskState.PLANNED, actor="karmo")
    store.save(first, expected_version=first.state_version)

    second.transition(TaskState.PLANNED, actor="stale-karmo")
    with pytest.raises(TaskStateError):
        store.save(second, expected_version=second.state_version)


def test_recovery_required_cannot_jump_back_to_running():
    store = InMemoryTaskStore()
    task = store.create(objective="inspect", requester="kamara")
    task.transition(TaskState.PLANNED, actor="karmo")
    task.transition(TaskState.READY, actor="karmo")
    task.transition(TaskState.RUNNING, actor="worker")
    task.transition(TaskState.RECOVERY_REQUIRED, actor="recovery")
    with pytest.raises(TaskStateError):
        task.transition(TaskState.RUNNING, actor="worker")


def test_staged_schema_contains_restart_race_and_replay_controls():
    migration = Path(__file__).parents[1] / "core_service" / "migrations" / "001_core_v2_substrate.sql"
    sql = migration.read_text()
    assert "idempotency_key TEXT NOT NULL UNIQUE" in sql
    assert "audit_trail JSONB NOT NULL" in sql
    assert "state_version BIGINT NOT NULL" in sql
    assert "event_key TEXT NOT NULL UNIQUE" in sql
    assert "idx_core_approval_state_expiry" in sql
    assert "idx_tool_invocation_unfinished" in sql
    assert "evidence_digest TEXT" in sql
    assert "verification_state TEXT" in sql
