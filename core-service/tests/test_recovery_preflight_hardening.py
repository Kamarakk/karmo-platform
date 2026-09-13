from types import SimpleNamespace

import pytest

from core_service.recovery import RecoveryError, TaskRecoveryManager
from core_service.task_state import InMemoryTaskStore, TaskState


class Ledger:
    def __init__(self, *rows):
        self.rows = list(rows)

    def list_unfinished(self):
        return list(self.rows)


def invocation(invocation_id, task_id, *, status="STARTED"):
    return SimpleNamespace(
        invocation_id=invocation_id,
        task_id=task_id,
        status=status,
        idempotency_key=f"key:{invocation_id}",
    )


def running_task(store, objective):
    task = store.create(objective=objective, requester="kamara")
    task.transition(TaskState.PLANNED, actor="karmo")
    task.transition(TaskState.READY, actor="karmo")
    task.transition(TaskState.RUNNING, actor="worker-1")
    store.save(task, expected_version=task.state_version)
    return task


def ready_task(store, objective):
    task = store.create(objective=objective, requester="kamara")
    task.transition(TaskState.PLANNED, actor="karmo")
    task.transition(TaskState.READY, actor="karmo")
    store.save(task, expected_version=task.state_version)
    return task


def test_missing_task_later_in_ledger_causes_zero_recovery_writes():
    store = InMemoryTaskStore()
    valid = running_task(store, "valid first row")
    missing_task_id = "00000000-0000-0000-0000-000000000099"

    ledger = Ledger(
        invocation("inv-1", valid.task_id),
        invocation("inv-2", missing_task_id),
    )

    with pytest.raises(RecoveryError, match="references missing task"):
        TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)

    restored = store.get(valid.task_id)
    assert restored.state == TaskState.RUNNING
    assert restored.next_action is None


def test_conflicting_task_state_later_in_ledger_causes_zero_recovery_writes():
    store = InMemoryTaskStore()
    valid = running_task(store, "valid first row")
    conflict = ready_task(store, "incompatible second row")

    ledger = Ledger(
        invocation("inv-1", valid.task_id),
        invocation("inv-2", conflict.task_id),
    )

    with pytest.raises(RecoveryError, match="conflicts with task"):
        TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)

    assert store.get(valid.task_id).state == TaskState.RUNNING
    assert store.get(conflict.task_id).state == TaskState.READY


def test_taskless_row_later_in_ledger_causes_zero_recovery_writes():
    store = InMemoryTaskStore()
    valid = running_task(store, "valid first row")

    ledger = Ledger(
        invocation("inv-1", valid.task_id),
        invocation("inv-2", None),
    )

    with pytest.raises(RecoveryError, match="has no task_id"):
        TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)

    assert store.get(valid.task_id).state == TaskState.RUNNING


def test_multiple_unfinished_rows_for_same_task_recover_once_without_stale_cas():
    store = InMemoryTaskStore()
    task = running_task(store, "two unknown invocation outcomes")
    ledger = Ledger(
        invocation("inv-a", task.task_id),
        invocation("inv-b", task.task_id),
    )

    recovered = TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)

    assert len(recovered) == 1
    assert recovered[0].task_id == task.task_id
    restored = store.get(task.task_id)
    assert restored.state == TaskState.RECOVERY_REQUIRED
    assert restored.next_action == "reconcile prior execution evidence before continuing"


def test_multiple_unfinished_rows_for_same_task_are_all_preserved_in_recovery_event():
    class EventfulStore(InMemoryTaskStore):
        def __init__(self):
            super().__init__()
            self.events = []

        def append_event(self, **kwargs):
            self.events.append(kwargs)
            return kwargs["event_key"]

    store = EventfulStore()
    task = running_task(store, "audit all unknown outcomes")
    ledger = Ledger(
        invocation("inv-a", task.task_id),
        invocation("inv-b", task.task_id),
    )

    TaskRecoveryManager(store).reconcile_unfinished_invocations(ledger)

    assert len(store.events) == 1
    event = store.events[0]
    assert event["event_type"] == "RECOVERY_REQUIRED"
    assert event["payload"]["unfinished_invocation_count"] == 2
    assert event["payload"]["invocation_ids"] == ["inv-a", "inv-b"]
    assert event["payload"]["idempotency_keys"] == ["key:inv-a", "key:inv-b"]
    assert event["payload"]["automatic_replay"] is False
