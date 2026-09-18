from __future__ import annotations

import uuid

import pytest

from core_service.dispatcher import DispatchError
from core_service.operator import KarmoOperator
from core_service.orchestration import TaskStateError


class FakeModelClient:
    def chat(self, *, model, messages, temperature=0.2):
        return "unused in these tests"

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2):
        return {"content": self.chat(model=model, messages=messages, temperature=temperature), "tool_calls": None}


class FakeTaskStore:
    """In-memory stand-in matching TaskStore's exact public contract."""

    def __init__(self):
        self._tasks: dict[str, dict] = {}

    def create_task(self, *, objective, context, requested_by):
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id, "objective": objective, "context": context,
            "status": "OPEN", "requested_by": requested_by, "claimed_by": None,
            "result": None, "created_at": "2026-01-01T00:00:00", "claimed_at": None,
            "completed_at": None,
        }
        self._tasks[task_id] = task
        return dict(task)

    def list_tasks(self, *, status=None, limit=20):
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t["status"] == status]
        return tuple(dict(t) for t in tasks[:limit])

    def claim_task(self, *, task_id, claimed_by):
        task = self._tasks.get(task_id)
        if task is None or task["status"] != "OPEN":
            raise TaskStateError(f"task {task_id} is not OPEN or does not exist")
        task["status"] = "CLAIMED"
        task["claimed_by"] = claimed_by
        return dict(task)

    def complete_task(self, *, task_id, result, completed_by):
        task = self._tasks.get(task_id)
        if task is None or task["status"] != "CLAIMED" or task["claimed_by"] != completed_by:
            raise TaskStateError(f"task {task_id} is not CLAIMED by {completed_by!r} or does not exist")
        task["status"] = "DONE"
        task["result"] = result
        return dict(task)


def _operator():
    return KarmoOperator(model_client=FakeModelClient(), task_store=FakeTaskStore())


def test_create_task_returns_open_task_attributed_to_actor():
    operator = _operator()

    task = operator.create_task(objective="reconcile PR #26", actor="kamara")

    assert task["status"] == "OPEN"
    assert task["objective"] == "reconcile PR #26"
    assert task["requested_by"] == "kamara"


def test_write_tools_require_approval_before_executing():
    """Directly proves the REVERSIBLE_WRITE floor is real, not bypassed by the
    operator's request+approve+execute convenience wrapper -- an unapproved
    dispatch call must return a pending decision, never an executed one."""
    operator = _operator()

    pending = operator.dispatcher.dispatch(
        requester="kamara",
        tool_id="karmo.orchestration.create_task",
        version="1.0.0",
        arguments={"objective": "x", "context": None, "requested_by": "kamara"},
        executor_identity="karmo-core-operator",
    )

    assert pending.executed is False
    assert pending.approval_id is not None


def test_list_tasks_filters_by_status():
    operator = _operator()
    operator.create_task(objective="task one", actor="kamara")
    claimed = operator.create_task(objective="task two", actor="kamara")
    operator.claim_task(task_id=claimed["task_id"], actor="claude-code")

    open_tasks = operator.list_tasks(status="OPEN")
    claimed_tasks = operator.list_tasks(status="CLAIMED")

    assert len(open_tasks) == 1
    assert open_tasks[0]["objective"] == "task one"
    assert len(claimed_tasks) == 1
    assert claimed_tasks[0]["objective"] == "task two"


def test_claim_then_complete_full_lifecycle():
    operator = _operator()
    task = operator.create_task(objective="write a report", actor="kamara")

    claimed = operator.claim_task(task_id=task["task_id"], actor="claude-code")
    assert claimed["status"] == "CLAIMED"
    assert claimed["claimed_by"] == "claude-code"

    done = operator.complete_task(task_id=task["task_id"], result="report written", actor="claude-code")
    assert done["status"] == "DONE"
    assert done["result"] == "report written"


def test_cannot_claim_an_already_claimed_task():
    operator = _operator()
    task = operator.create_task(objective="one at a time", actor="kamara")
    operator.claim_task(task_id=task["task_id"], actor="claude-code")

    with pytest.raises(TaskStateError):
        operator.claim_task(task_id=task["task_id"], actor="chatgpt")


def test_cannot_complete_a_task_claimed_by_someone_else():
    operator = _operator()
    task = operator.create_task(objective="mine, not yours", actor="kamara")
    operator.claim_task(task_id=task["task_id"], actor="claude-code")

    with pytest.raises(TaskStateError):
        operator.complete_task(task_id=task["task_id"], result="sneaky", actor="chatgpt")


def test_orchestration_unavailable_fails_closed_with_clear_reason():
    operator = KarmoOperator(model_client=FakeModelClient())  # no task_store injected, no DSN on this machine

    assert operator.task_store is None
    assert operator.orchestration_status.startswith("DEGRADED_CONFIG_ERROR:")
    with pytest.raises(DispatchError, match="orchestration task board unavailable"):
        operator.create_task(objective="anything", actor="kamara")
