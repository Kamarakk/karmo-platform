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
