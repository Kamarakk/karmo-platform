from types import SimpleNamespace

import pytest

from core_service.recovery import RecoveryError, TaskRecoveryManager


class UnexpectedTaskStoreAccess:
    def get(self, task_id):
        raise AssertionError("contradictory invocation status must fail before task access")


class Ledger:
    def __init__(self, status):
        self.status = status

    def list_unfinished(self):
        return [
            SimpleNamespace(
                invocation_id="inv-contradictory",
                task_id="task-1",
                status=self.status,
                idempotency_key="task-1:tool:1",
            )
        ]


@pytest.mark.parametrize("status", ["EXECUTED", "FAILED", "UNKNOWN", ""])
def test_unfinished_invocation_requires_started_status_before_task_mutation(status):
    manager = TaskRecoveryManager(UnexpectedTaskStoreAccess())

    with pytest.raises(RecoveryError, match="invalid status"):
        manager.reconcile_unfinished_invocations(Ledger(status))


def test_unfinished_started_invocation_reaches_normal_recovery_validation():
    class MissingTaskStore:
        def __init__(self):
            self.lookups = []

        def get(self, task_id):
            self.lookups.append(task_id)
            return None

    store = MissingTaskStore()
    manager = TaskRecoveryManager(store)

    with pytest.raises(RecoveryError, match="references missing task"):
        manager.reconcile_unfinished_invocations(Ledger("STARTED"))

    assert store.lookups == ["task-1"]
