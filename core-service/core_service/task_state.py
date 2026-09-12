"""Durable KARMO task-state model.

Models do not own task truth. KARMO owns the task record, transitions, evidence,
approvals, verification and final state. Persistence is injected so the same
state machine can be tested without a database and backed by PostgreSQL later.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TaskState(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_ALLOWED_TRANSITIONS = {
    TaskState.CREATED: {TaskState.PLANNED, TaskState.CANCELLED},
    TaskState.PLANNED: {TaskState.WAITING_FOR_APPROVAL, TaskState.READY, TaskState.CANCELLED},
    TaskState.WAITING_FOR_APPROVAL: {TaskState.READY, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.READY: {TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.VERIFYING, TaskState.RECOVERY_REQUIRED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.VERIFYING: {TaskState.SUCCEEDED, TaskState.RECOVERY_REQUIRED, TaskState.FAILED},
    # Recovery never silently retries execution. Evidence must be reconciled
    # first, then the task may continue to verification or terminate.
    TaskState.RECOVERY_REQUIRED: {TaskState.VERIFYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.SUCCEEDED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


class TaskStateError(RuntimeError):
    pass


@dataclass
class TaskRecord:
    task_id: str
    objective: str
    requester: str
    risk: str
    allowed_capabilities: list[str]
    state: TaskState = TaskState.CREATED
    state_version: int = 0
    model: str | None = None
    tool: str | None = None
    inputs: dict = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    checkpoints: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    retries: int = 0
    approvals: list[str] = field(default_factory=list)
    verification: list[dict] = field(default_factory=list)
    rollback: dict | None = None
    result: dict | None = None
    next_action: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def transition(self, target: TaskState, *, actor: str, note: str = ""):
        target = TaskState(target)
        if target not in _ALLOWED_TRANSITIONS[self.state]:
            raise TaskStateError(f"illegal transition {self.state.value} -> {target.value}")
        self.actions.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "kind": "state_transition",
            "from": self.state.value,
            "to": target.value,
            "note": note,
        })
        self.state = target
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self


class InMemoryTaskStore:
    """Test/dev store with copy-on-read semantics to prevent hidden mutation."""

    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}

    def create(self, *, objective, requester, risk="LOW", allowed_capabilities=None, inputs=None):
        record = TaskRecord(
            task_id=str(uuid.uuid4()),
            objective=objective,
            requester=requester,
            risk=risk,
            allowed_capabilities=list(allowed_capabilities or []),
            inputs=dict(inputs or {}),
        )
        self.save(record)
        return copy.deepcopy(record)

    def save(self, record: TaskRecord, *, expected_version=None):
        existing = self._tasks.get(record.task_id)
        if expected_version is not None:
            actual = existing.state_version if existing is not None else 0
            if actual != expected_version:
                raise TaskStateError(
                    f"task version conflict: expected {expected_version}, found {actual}"
                )
        stored = copy.deepcopy(record)
        stored.state_version = (existing.state_version + 1) if existing is not None else 1
        record.state_version = stored.state_version
        self._tasks[record.task_id] = stored
        return stored.state_version

    def get(self, task_id: str):
        record = self._tasks.get(task_id)
        return copy.deepcopy(record) if record is not None else None

    def list(self):
        return [copy.deepcopy(record) for record in self._tasks.values()]

    def list_by_states(self, states):
        wanted = {TaskState(value) for value in states}
        return [copy.deepcopy(record) for record in self._tasks.values() if record.state in wanted]
