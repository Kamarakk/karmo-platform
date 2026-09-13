import pytest

from core_service.persistence import PersistenceError
from core_service.recovery_persistence import PostgresRecoveryStore
from core_service.task_state import TaskRecord, TaskState


class FakeCursor:
    def __init__(self):
        self._rows = [(2,), ("event-id",)]

    def execute(self, _sql, _params):
        return None

    def fetchone(self):
        return self._rows.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class CommitFailConnection:
    def __init__(self):
        self._cursor = FakeCursor()

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise RuntimeError("synthetic commit failure")
        return False


def record():
    return TaskRecord(
        task_id="00000000-0000-0000-0000-000000000001",
        objective="recover safely",
        requester="kamara",
        risk="LOW",
        allowed_capabilities=[],
        state=TaskState.RECOVERY_REQUIRED,
        state_version=1,
        next_action="reconcile prior execution evidence before continuing",
    )


def test_commit_failure_does_not_advance_callers_task_version():
    task = record()
    store = PostgresRecoveryStore(lambda: CommitFailConnection())

    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        store.save_with_event(
            task,
            expected_version=1,
            event_key="restart-recovery:task:1",
            event_type="RECOVERY_REQUIRED",
            actor="karmo-recovery",
            payload={"automatic_replay": False},
        )

    assert task.state_version == 1


def test_recovery_event_identity_fields_are_required_before_database_access():
    def forbidden_connection():
        raise AssertionError("database should not be opened for malformed audit event")

    store = PostgresRecoveryStore(forbidden_connection)
    task = record()

    for field, value in (("event_key", ""), ("event_type", ""), ("actor", "")):
        kwargs = {
            "event_key": "event-key",
            "event_type": "RECOVERY_REQUIRED",
            "actor": "karmo-recovery",
        }
        kwargs[field] = value
        with pytest.raises(PersistenceError, match="required"):
            store.save_with_event(
                task,
                expected_version=1,
                payload={},
                **kwargs,
            )
