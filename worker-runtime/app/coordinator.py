"""KARMO Worker Runtime -- Coordinator (Phase 2/10).

The coordinator remains the sole authority: it owns the worker registry
and the job queue, validates every capability, and is the only component
that decides which worker gets which job. Workers never see or touch each
other's leases directly.

Phase 10 (multi-worker) minimum selection logic: eligible = enabled,
AVAILABLE, declares the requested capability. Among eligible workers,
prefer (in order): explicit label match if the job requests one, then
first-registered (stable, simple, easy to reason about) -- deliberately
not a scheduler, per explicit instruction to implement only the minimum
necessary to prove the model.
"""

from capability_manifest import CapabilityManifestError
from job_protocol import JobProtocolError, WorkerJobQueue
from job_model_reuse import JobState
from worker_registry import WorkerRegistry, WorkerRegistryError, WorkerStatus


class CoordinatorError(RuntimeError):
    pass


class Coordinator:
    def __init__(self, *, clock=None):
        self.workers = WorkerRegistry(clock=clock)
        self.jobs = WorkerJobQueue(clock=clock)

    # --- Worker-facing ----------------------------------------------------

    def register_worker(self, **kwargs):
        try:
            return self.workers.register(**kwargs)
        except (WorkerRegistryError, CapabilityManifestError) as error:
            raise CoordinatorError(str(error)) from error

    def heartbeat(self, worker_id, **kwargs):
        try:
            return self.workers.heartbeat(worker_id, **kwargs)
        except WorkerRegistryError as error:
            raise CoordinatorError(str(error)) from error

    def poll_for_job(self, worker_id, capabilities, *, required_label=None):
        """Called by a worker asking for work. Returns a leased WorkerJob
        or None. The worker never picks its own job from a shared queue
        directly -- the coordinator always selects and leases on the
        worker's behalf, the pull-based model's own safety property."""
        record = self.workers.get(worker_id)
        if not record.enabled or record.status != WorkerStatus.AVAILABLE:
            return None

        eligible_capabilities = set(capabilities) & set(record.capabilities)
        if not eligible_capabilities:
            return None

        candidate = self._select_job(eligible_capabilities, required_label, record)
        if candidate is None:
            return None

        leased = self.jobs.lease(
            candidate.job_id, worker_id=worker_id,
            presented_payload=candidate.payload, presented_payload_digest=candidate.payload_digest,
        )
        self.workers.mark_busy(worker_id)
        return leased

    def execute_job(self, job_id, *, executor_identity, presented_payload, action):
        """Approval-gated execution choke point (see job_protocol.py's
        execute()). Only JobProtocolError (approval-gating refusals) is
        wrapped as CoordinatorError here -- an exception raised BY
        `action()` itself (e.g. sandbox.SandboxError from the worker's
        own execution) is intentionally left unwrapped so the worker can
        distinguish "you weren't allowed to run this" from "you ran it
        and it failed"."""
        try:
            return self.jobs.execute(
                job_id, executor_identity=executor_identity, presented_payload=presented_payload, action=action,
            )
        except JobProtocolError as error:
            raise CoordinatorError(str(error)) from error

    def request_approval(self, job_id, *, requester):
        """Parks an approval-required job in WAITING_FOR_APPROVAL and
        opens a real approval request -- NOT a failure path. See
        job_protocol.WorkerJobQueue.request_approval_if_required (a
        no-op, stays RUNNING, if the capability doesn't require
        approval)."""
        try:
            return self.jobs.request_approval_if_required(job_id, requester=requester)
        except JobProtocolError as error:
            raise CoordinatorError(str(error)) from error

    def resume_job(self, job_id, *, worker_id, presented_payload, action):
        """Check on (and execute, if now approved) a job a worker
        previously parked via request_approval. See job_protocol.py's
        resume() for the full contract -- a None return (still pending)
        is NOT an error and passes through unwrapped."""
        try:
            return self.jobs.resume(
                job_id, worker_id=worker_id, presented_payload=presented_payload, action=action,
            )
        except JobProtocolError as error:
            # If this resume() call is what just ended the job (denial
            # already handled by deny_job() below; expiry is detected
            # only lazily, so resume() may be the first thing to notice
            # it), the worker's lease on it is over -- release it back
            # to AVAILABLE. Guarded to the job's actual assigned worker
            # only, and safe to attempt even if already released (a
            # wrong-worker attempt never reaches this -- resume() raises
            # before any job-state change for that case, so job.state
            # here is never FAILED as a result of an imposter's attempt).
            worker_job = self.jobs.get(job_id)
            if worker_job.state == JobState.FAILED and worker_job.assigned_worker_id == worker_id:
                try:
                    self.workers.mark_available(worker_id)
                except WorkerRegistryError:
                    pass
            raise CoordinatorError(str(error)) from error

    def deny_job(self, job_id, *, approver, reason=""):
        """Approver-side action (not a worker/transport verb -- a human
        or system denying a pending approval). deny() itself only knows
        about job/approval state, not the worker registry, so this
        wrapper is what actually releases the assigned worker back to
        AVAILABLE as part of ending the job safely -- without it, a
        denied job would leave its worker stuck BUSY indefinitely."""
        worker_job = self.jobs.deny(job_id, approver=approver, reason=reason)
        if worker_job.assigned_worker_id:
            try:
                self.workers.mark_available(worker_job.assigned_worker_id)
            except WorkerRegistryError:
                pass
        return worker_job

    def _select_job(self, eligible_capabilities, required_label, worker_record):
        """Minimum selection logic -- first-eligible-QUEUED-job by
        capability, no priority, no load balancing, no affinity beyond
        capability + an optional label filter. Deliberately minimal."""
        for worker_job in self.jobs._worker_jobs.values():  # prototype-internal access, isolated module
            if worker_job.job.state != JobState.QUEUED:
                continue
            if worker_job.capability_id not in eligible_capabilities:
                continue
            if required_label is not None and required_label not in worker_record.labels:
                continue
            return worker_job
        return None

    def finalize_success(self, job_id, **kwargs):
        worker_job = self.jobs.complete(job_id, **kwargs)
        if worker_job.assigned_worker_id:
            try:
                self.workers.mark_available(worker_job.assigned_worker_id)
            except WorkerRegistryError:
                pass  # worker may not have gone through poll_for_job's mark_busy path, or is already OFFLINE/DISABLED
        return worker_job

    def finalize_failure(self, job_id, **kwargs):
        worker_job = self.jobs.fail(job_id, **kwargs)
        if worker_job.assigned_worker_id:
            try:
                self.workers.mark_available(worker_job.assigned_worker_id)
            except Exception:
                pass  # worker may already be OFFLINE/DISABLED -- not this call's concern
        return worker_job

    # --- Submission-side (KARMO Core's own callers) ------------------------

    def submit_job(self, *, capability_id, payload, idempotency_key, correlation_id=None):
        try:
            return self.jobs.submit(
                capability_id=capability_id, payload=payload,
                idempotency_key=idempotency_key, correlation_id=correlation_id,
            )
        except JobProtocolError as error:
            raise CoordinatorError(str(error)) from error

    def disable_worker(self, worker_id, *, reason=""):
        return self.workers.disable(worker_id, reason=reason)
