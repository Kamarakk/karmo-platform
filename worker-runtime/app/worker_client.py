"""KARMO Worker Runtime -- Worker Client (Phase 7).

Pull-based, exactly as required:
  worker polls coordinator -> coordinator leases one eligible job
    -> worker validates job/capability -> worker executes (sandboxed)
      -> worker submits result -> coordinator finalizes job

Never opens an inbound port. Only ever initiates outbound calls through
its WorkerTransport. Every job is re-validated against the capability
manifest before execution -- a worker never blindly trusts a leased job's
capability_id.
"""

import capabilities  # noqa: F401 -- import for its registration side effect (sandbox._HANDLERS population)
from capability_manifest import CapabilityManifestError, get_canonical_capability
from sandbox import SandboxError, run_capability


class WorkerClientError(RuntimeError):
    pass


class WorkerClient:
    def __init__(self, *, worker_id, transport, allowed_root=None):
        self.worker_id = worker_id
        self._transport = transport
        self._allowed_root = allowed_root

    def register(self, **identity_kwargs):
        return self._transport.register(worker_id=self.worker_id, **identity_kwargs)

    def heartbeat(self, **kwargs):
        return self._transport.heartbeat(self.worker_id, **kwargs)

    def poll_and_execute_once(self, capabilities):
        """One full pull cycle. Returns:
          - the finalized WorkerJob, if a NONE-authority job executed and
            completed;
          - a WorkerJob still in WAITING_FOR_APPROVAL, if the leased job
            requires approval -- parked, NOT executed, NOT failed. Pass
            it to try_resume() on a later poll cycle once it may have
            been approved;
          - None, if no eligible work was available.

        Fixed after independent review: an approval-required job used to
        reach the approval-gated execute() and be refused (correctly --
        approval genuinely wasn't present yet), and this method then
        treated that refusal as a hard failure, permanently marking a
        perfectly legitimate, merely-pending job FAILED. An
        approval-required job is never executed here at all -- it is
        parked via request_approval, and only ever executed later,
        through try_resume(), once actually approved."""
        leased = self._transport.poll(self.worker_id, capabilities)
        if leased is None:
            return None

        # Re-validate the leased job's capability against the manifest --
        # a worker never trusts a capability_id blindly just because the
        # coordinator sent it; if it somehow isn't a real, known
        # capability, refuse rather than attempt execution.
        try:
            canonical = get_canonical_capability(leased.capability_id)
        except CapabilityManifestError as error:
            self._transport.submit_failure(leased.job_id, reason=f"unknown capability at execution time: {error}")
            raise WorkerClientError(str(error)) from error

        if leased.authority_requirement != "NONE":
            # Not a failure -- a legitimate pending state. Nothing is
            # executed; the job is parked in WAITING_FOR_APPROVAL and a
            # real approval request is opened. The caller resumes it
            # later via try_resume() once it has (or hasn't) been
            # approved.
            return self._transport.request_approval(leased.job_id, requester=f"worker:{self.worker_id}")

        def _action():
            return run_capability(
                leased.capability_id, leased.payload,
                timeout_seconds=canonical["timeout_seconds"], allowed_root=self._allowed_root,
            )

        try:
            output, stdout_summary, duration, evidence_files = self._transport.execute(
                leased.job_id, executor_identity=self.worker_id, presented_payload=leased.payload, action=_action,
            )
        except SandboxError as error:
            self._transport.submit_failure(leased.job_id, reason=str(error))
            raise WorkerClientError(str(error)) from error
        except Exception as error:
            # Approval-gating refusal (CoordinatorError/JobProtocolError)
            # or anything else that isn't the handler's own SandboxError
            # -- the job never actually executed; report failure and stop.
            # (This capability is NONE-authority here, so this branch is
            # not the approval-pending case -- that's handled above,
            # before execute() is ever called.)
            self._transport.submit_failure(leased.job_id, reason=str(error))
            raise WorkerClientError(str(error)) from error

        return self._transport.submit_result(
            leased.job_id, output=output, duration_seconds=duration,
            stdout_summary=stdout_summary, evidence_files=evidence_files,
        )

    def try_resume(self, pending_job):
        """Check on -- and execute, if now approved -- a job previously
        parked by poll_and_execute_once(). Safe to call repeatedly while
        waiting: returns None with no side effects (no execution, no
        duplicate approval request, no job-state change) until the
        approval is resolved one way or the other.

        `pending_job` is the WorkerJob poll_and_execute_once() returned
        when it parked the job -- this worker is expected to hold onto
        it locally while waiting, exactly as a real worker would track
        its own in-flight/pending jobs. (Not a new network capability:
        this is worker-local bookkeeping, not a coordinator query verb --
        see transport.py's note on execute()/resume()'s in-process-only
        shape for what WOULD need to change for a real network worker.)"""
        canonical = get_canonical_capability(pending_job.capability_id)

        def _action():
            return run_capability(
                pending_job.capability_id, pending_job.payload,
                timeout_seconds=canonical["timeout_seconds"], allowed_root=self._allowed_root,
            )

        try:
            result = self._transport.resume(
                self.worker_id, pending_job.job_id, presented_payload=pending_job.payload, action=_action,
            )
        except SandboxError as error:
            self._transport.submit_failure(pending_job.job_id, reason=str(error))
            raise WorkerClientError(str(error)) from error
        except Exception as error:
            # Approval ended denied/expired/cancelled (resume() already
            # moved the job to FAILED as part of that, or it was already
            # terminal) -- surface it, do not attempt to fail it again.
            raise WorkerClientError(str(error)) from error

        if result is None:
            return None  # still pending -- call again later, nothing happened

        output, stdout_summary, duration, evidence_files = result
        return self._transport.submit_result(
            pending_job.job_id, output=output, duration_seconds=duration,
            stdout_summary=stdout_summary, evidence_files=evidence_files,
        )
