"""KARMO Model Router -- Phase D1 Core-side dispatch/wait glue.

Proves a worker can serve a request end to end: enqueues a job for a
specific worker's capability, waits (bounded, polling) for it to reach a
terminal state, and returns the durably-verified result content or a
clear failure/timeout outcome.

This is explicitly a PROOF/MEASUREMENT harness for Phase D1 (see
docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 6) -- it is
NOT wired into operator.py's real _chat() candidate loop. Making a
worker an actual candidate for real chat traffic is Phase D2, a
separate, later, explicit decision this module exists to inform with
real measured numbers (queue delay under load) rather than a guess.

Building this surfaced a real gap in the existing worker job/ticket/
result system (PR #41/#42): it only ever durably stored a result's
DIGEST and signature envelope, proving a claimed result is authentic,
never the actual content -- fine for a benchmark-style capability with
a known expected output, impossible for chat, where the answer is
unknowable in advance. Closed by worker_coordination.py's
submit_authenticated_result()/get_worker_job_result() (migration 007,
karmo_worker_job_results) -- additive, every existing caller unaffected.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .control import CapabilityClass, arguments_digest

_TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "RECOVERY_REQUIRED"})
DEFAULT_REQUESTER = "karmo-model-router-phase-d1-harness"


class WorkerDispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class DispatchOutcome:
    outcome: str  # "SUCCEEDED" | "FAILED" | "RECOVERY_REQUIRED" | "TIMED_OUT"
    job_id: str
    elapsed_seconds: float
    poll_count: int
    result: dict | None = None
    error: str | None = None


def dispatch_and_wait(
    *,
    store,
    gateway_backend,
    approval_engine,
    worker_id: str,
    tool_id: str,
    tool_version: str,
    arguments: dict,
    requester: str = DEFAULT_REQUESTER,
    total_deadline_seconds: float = 90.0,
    poll_interval_seconds: float = 1.0,
    clock=None,
    sleep=time.sleep,
) -> DispatchOutcome:
    """Dispatches exactly ONE job to worker_id and waits, bounded by
    total_deadline_seconds, for a terminal state.

    Deliberately never retries internally (Section 3.5's routing-loop
    protection: a caller that wants to try a different worker/model on
    timeout or failure makes that decision itself -- this function does
    not silently repeat the same dispatch).

    Setup failures (a malformed request, an unapproved worker, a digest
    mismatch) raise the real underlying error type
    (CoreControlError/WorkerCoordinationError/WorkerGatewayBackendError)
    -- those are programming/configuration errors, not a possible job
    outcome. Once the job is actually enqueued, every subsequent
    situation (success, failure, timeout) is a real, expected outcome of
    dispatching work to an independent process and is returned as a
    DispatchOutcome, never raised.
    """
    now = clock or (lambda: datetime.now(timezone.utc))
    start = now()
    digest = arguments_digest(tool_id, tool_version, arguments)
    task_id = str(uuid.uuid4())
    idempotency_key = f"dispatch:{task_id}:{tool_id}:{tool_version}"

    pending = approval_engine.request(
        requester=requester,
        tool_id=tool_id,
        tool_version=tool_version,
        arguments=arguments,
        authority_class=CapabilityClass.READ.value,
    )
    approval_engine.approve(pending.approval_id, approver=requester, authorized_executor=worker_id)

    job_id = store.enqueue_job(
        idempotency_key=idempotency_key,
        task_id=task_id,
        tool_id=tool_id,
        tool_version=tool_version,
        arguments_digest=digest,
        approval_id=pending.approval_id,
    )
    gateway_backend.attach_job_arguments(
        job_id=job_id,
        tool_id=tool_id,
        tool_version=tool_version,
        arguments=arguments,
        expected_arguments_digest=digest,
    )

    poll_count = 0
    while True:
        state = store.get_job_state(job_id)
        if state is None:
            raise WorkerDispatchError(f"dispatched job {job_id} vanished from durable state")
        poll_count += 1

        if state["state"] in _TERMINAL_STATES:
            elapsed = (now() - start).total_seconds()
            if state["state"] == "SUCCEEDED":
                result_row = store.get_worker_job_result(job_id)
                return DispatchOutcome(
                    outcome="SUCCEEDED",
                    job_id=job_id,
                    elapsed_seconds=elapsed,
                    poll_count=poll_count,
                    result=result_row["result"] if result_row else None,
                )
            return DispatchOutcome(
                outcome=state["state"],
                job_id=job_id,
                elapsed_seconds=elapsed,
                poll_count=poll_count,
                error=state.get("last_error"),
            )

        elapsed = (now() - start).total_seconds()
        if elapsed >= total_deadline_seconds:
            return DispatchOutcome(
                outcome="TIMED_OUT",
                job_id=job_id,
                elapsed_seconds=elapsed,
                poll_count=poll_count,
                error=f"no terminal state within {total_deadline_seconds}s (last observed: {state['state']!r})",
            )
        sleep(poll_interval_seconds)
