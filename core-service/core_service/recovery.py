"""Restart recovery orchestration for durable KARMO task state.

Recovery is intentionally conservative. Work that was RUNNING or VERIFYING at
process loss is never silently replayed. It is moved to RECOVERY_REQUIRED with
an idempotent event so evidence can be reconciled before any continuation.
Unfinished invocation records are treated as unknown outcomes, not retries.
"""

from __future__ import annotations

from .task_state import TaskState


class RecoveryError(RuntimeError):
    pass


class TaskRecoveryManager:
    def __init__(self, task_store, *, actor="karmo-recovery"):
        self.task_store = task_store
        self.actor = actor

    def _persist_recovery(self, task, *, expected_version, event_key, payload):
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

    def _mark_recovery_required(self, task, *, reason, event_key, extra_payload=None):
        prior_state = task.state
        expected_version = task.state_version
        if prior_state == TaskState.RECOVERY_REQUIRED:
            return task
        if prior_state not in (TaskState.RUNNING, TaskState.VERIFYING):
            raise RecoveryError(
                f"cannot reconcile task {task.task_id} from {prior_state.value}; "
                "manual invariant review required"
            )
        payload = {
            "prior_state": prior_state.value,
            "new_state": TaskState.RECOVERY_REQUIRED.value,
            "reason": reason,
            "automatic_replay": False,
        }
        payload.update(extra_payload or {})
        task.transition(
            TaskState.RECOVERY_REQUIRED,
            actor=self.actor,
            note=f"{reason} observed while task was {prior_state.value}; no automatic replay",
        )
        task.next_action = "reconcile prior execution evidence before continuing"
        self._persist_recovery(
            task,
            expected_version=expected_version,
            event_key=event_key,
            payload=payload,
        )
        return task

    def reconcile_after_restart(self):
        candidates = self.task_store.list_by_states(
            [TaskState.RUNNING, TaskState.VERIFYING]
        )
        recovered = []
        for task in candidates:
            recovered.append(self._mark_recovery_required(
                task,
                reason="process_restart",
                event_key=f"restart-recovery:{task.task_id}:{task.state_version}",
            ))
        return recovered

    def reconcile_unfinished_invocations(self, invocation_ledger):
        """Bind unfinished invocation truth to task recovery without replaying work.

        Preflight the complete unfinished set before the first task write. A
        corrupt/missing task reference later in the ledger must not leave earlier
        tasks partially transitioned merely because iteration order encountered
        those valid rows first. This is not distributed atomicity; concurrent
        changes can still race and are fenced by each task store's version/CAS
        semantics. It does make static ledger/task inconsistencies fail closed
        before recovery mutates durable task state.
        """
        invocations = list(invocation_ledger.list_unfinished())
        candidates = []

        # Validation pass: no task state is changed until every unfinished row
        # is structurally a live STARTED invocation with a resolvable task in a
        # recovery-compatible state. completed_at=NULL with any other status is
        # contradictory durable state and requires operator review rather than
        # being normalized into an ordinary restart recovery path.
        for invocation in invocations:
            if invocation.status != "STARTED":
                raise RecoveryError(
                    f"unfinished invocation {invocation.invocation_id} has invalid status "
                    f"{invocation.status!r}; expected STARTED"
                )
            if invocation.task_id is None:
                raise RecoveryError(
                    f"unfinished invocation {invocation.invocation_id} has no task_id"
                )
            task = self.task_store.get(invocation.task_id)
            if task is None:
                raise RecoveryError(
                    f"unfinished invocation {invocation.invocation_id} references missing task {invocation.task_id}"
                )
            if task.state not in (
                TaskState.RUNNING,
                TaskState.VERIFYING,
                TaskState.RECOVERY_REQUIRED,
            ):
                raise RecoveryError(
                    f"unfinished invocation {invocation.invocation_id} conflicts with task "
                    f"{task.task_id} state {task.state.value}"
                )
            candidates.append((invocation, task))

        reconciled = []
        for invocation, task in candidates:
            if task.state == TaskState.RECOVERY_REQUIRED:
                reconciled.append(task)
                continue
            reconciled.append(self._mark_recovery_required(
                task,
                reason="unfinished_invocation",
                event_key=f"unfinished-invocation:{invocation.invocation_id}",
                extra_payload={
                    "invocation_id": invocation.invocation_id,
                    "invocation_status": invocation.status,
                    "idempotency_key": invocation.idempotency_key,
                },
            ))
        return reconciled
