import copy
from types import SimpleNamespace

import pytest

from core_service.recovery import RecoveryError, TaskRecoveryManager
from core_service.task_state import InMemoryTaskStore, TaskState, TaskStateError


class AtomicMemoryStore(InMemoryTaskStore):
    def __init__(self):
        super().__init__()
        self.atomic_events = {}
        self.atomic_calls = 0

    def save_with_event(self, record, *, expected_version, event_key, event_type, actor, payload):
        self.atomic_calls += 1
        if event_key in self.atomic_events:
            raise TaskStateError(f"duplicate event key: {event_key}")
        self.save(record, expected_version=expected_version)
        self.atomic_events[event_key] = {
            "task_id": record.task_id,
            "event_type": event_type,
            "actor": actor,
            "payload": copy.deepcopy(payload),
        }

    def append_event(self, **kwargs):
        raise AssertionError("non-atomic append_event path must not be used")


class MemoryInvocationLedger:
    def __init__(self, records):
        self.records = list(records)

    def list_unfinished(self):
        return list(self.records)


def running_task(store):
    task = store.create(objective="inspect host", requester="kamara")
    task.transition(TaskState.PLANNED, actor="karmo")
    task.transition(TaskState.READY, actor="karmo")
    task.transition(TaskState.RUNNING, actor="worker-1")
    store.save(task, expected_version=task.state_version)
    return task


def invocation(task_id, *, invocation_id="inv-1", status="STARTED"):
    return SimpleNamespace(
        invocation_id=invocation_id,
        idempotency_key=f"{task_id}:health:1",
        task_id=task_id,
        status=status,
    )


def test_restart_recovery_uses_atomic_state_plus_event_boundary_when_available():
    store = AtomicMemoryStore()
    task = running_task(store)

    recovered = TaskRecoveryManager(store).reconcile_after_restart()

    assert len(recovered) == 1
    assert store.atomic_calls == 1
    restored = store.get(task.task_id)
    assert restored.state == TaskState.RECOVERY_REQUIRED
    event = next(iter(store.atomic_events.values()))
    assert event["event_type"] == "RECOVERY_REQUIRED"
    assert event["payload"]["automatic_replay"] is False


def test_unfinished_invocation_marks_running_task_recovery_required_without_replay():
    store = AtomicMemoryStore()
    task = running_task(store)
    ledger = MemoryInvocationLedger([invocation(task.task_id)])

    reconciled = TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)

    assert len(reconciled) == 1
    restored = store.get(task.task_id)
    assert restored.state == TaskState.RECOVERY_REQUIRED
    event = next(iter(store.atomic_events.values()))
    assert event["payload"]["reason"] == "unfinished_invocation"
    assert event["payload"]["invocation_id"] == "inv-1"
    assert event["payload"]["automatic_replay"] is False


def test_unfinished_invocation_conflicting_with_terminal_task_fails_closed():
    store = AtomicMemoryStore()
    task = running_task(store)
    task.transition(TaskState.VERIFYING, actor="karmo")
    task.transition(TaskState.SUCCEEDED, actor="verifier")
    store.save(task, expected_version=task.state_version)
    ledger = MemoryInvocationLedger([invocation(task.task_id)])

    with pytest.raises(RecoveryError, match="conflicts with task"):
        TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)


def test_unfinished_invocation_without_task_identity_fails_closed():
    store = AtomicMemoryStore()
    ledger = MemoryInvocationLedger([
        SimpleNamespace(
            invocation_id="inv-orphan",
            idempotency_key="orphan",
            task_id=None,
            status="STARTED",
        )
    ])

    with pytest.raises(RecoveryError, match="has no task_id"):
        TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)
