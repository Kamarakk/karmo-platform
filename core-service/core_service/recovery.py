"""Restart recovery orchestration for durable KARMO task state.

Recovery is intentionally conservative. Work that was RUNNING or VERIFYING at
process loss is never silently replayed. It is moved to RECOVERY_REQUIRED with
an idempotent event so evidence can be reconciled before any continuation.
"""

from __future__ import annotations

from .task_state import TaskState


class RecoveryError(RuntimeError):
    pass


class TaskRecoveryManager:
    def __init__(self, task_store, *, actor="karmo-recovery"):
        self.task_store = task_store
        self.actor = actor

    def reconcile_after_restart(self):
        candidates = self.task_store.list_by_states(
            [TaskState.RUNNING, TaskState.VERIFYING]
        )
        recovered = []
        for task in candidates:
            prior_state = task.state
            expected_version = task.state_version
            event_key = f"restart-recovery:{task.task_id}:{expected_version}"
            payload = {
                "prior_state": prior_state.value,
                "new_state": TaskState.RECOVERY_REQUIRED.value,
                "reason": "process_restart",
                "automatic_replay": False,
            }
            task.transition(
                TaskState.RECOVERY_REQUIRED,
                actor=self.actor,
                note=f"process restart observed while task was {prior_state.value}; no automatic replay",
            )
            task.next_action = "reconcile prior execution evidence before continuing"

            if hasattr(self.task_store, "save_with_event"):
                self.task_store.save_with_event(
                    task,
                    expected_version=expected_version,
                    event_key=event_key,
                    event_type="RECOVERY_REQUIRED",
                    actor=self.actor,
                    payload=payload,
                )
            else:
                self.task_store.save(task, expected_version=expected_version)
                if hasattr(self.task_store, "append_event"):
                    self.task_store.append_event(
                        event_key=event_key,
                        task_id=task.task_id,
                        event_type="RECOVERY_REQUIRED",
                        actor=self.actor,
                        payload=payload,
                    )
            recovered.append(task)
        return recovered
