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

_WORKER_RESULT_ENVELOPE_KEYS = {"output", "stdout_summary", "duration_seconds", "evidence_files"}


class WorkerDispatchError(RuntimeError):
    pass


def _unwrap_worker_result(result):
    """Every real worker (ssh_worker_client.py's SshRemoteWorkerClient,
    the only production worker implementation as of Phase D1) wraps
    whatever a capability handler returns in a fixed envelope --
    {"output": ..., "stdout_summary": ..., "duration_seconds": ...,
    "evidence_files": ...} -- before signing and submitting it, for every
    capability uniformly, not just model_chat_tools. dispatch_and_wait()
    is capability-agnostic and previously returned that whole envelope
    as-is, silently handing callers the wrapper instead of the actual
    capability output (found during a live production investigation, not
    yet confirmed as the cause of a separate submit_result failure, but a
    real bug regardless). A result that doesn't match this exact envelope
    shape is returned unchanged -- e.g. a capability whose result was
    submitted directly via accept_result() rather than through the real
    worker client."""
    if isinstance(result, dict) and set(result) == _WORKER_RESULT_ENVELOPE_KEYS:
        return result["output"]
    return result


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
    lease_seconds: int | None = None,
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

    lease_seconds (Model Router Phase D1 reliability fix -- see
    migration 008): the real gap this session's live proof-run found
    was worker_gateway_backend.py's poll() always leasing jobs for a
    fixed 60 seconds regardless of the capability actually being
    executed, while model_chat/model_chat_tools both allow up to 120 --
    a real call anywhere near that long could never report its own
    success before its lease expired. When not given explicitly here,
    defaults to total_deadline_seconds itself (clamped to the store's
    30-600s bound): if a caller is willing to wait up to X seconds for a
    result, the lease covering that job's execution should be at least
    that long too, by default, rather than needing two separate
    duration parameters that could silently drift apart.
    """
    now = clock or (lambda: datetime.now(timezone.utc))
    start = now()
    digest = arguments_digest(tool_id, tool_version, arguments)
    task_id = str(uuid.uuid4())
    idempotency_key = f"dispatch:{task_id}:{tool_id}:{tool_version}"
    effective_lease_seconds = lease_seconds
    if effective_lease_seconds is None:
        effective_lease_seconds = max(30, min(600, int(total_deadline_seconds)))

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
        lease_seconds_hint=effective_lease_seconds,
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
                    result=_unwrap_worker_result(result_row["result"]) if result_row else None,
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
