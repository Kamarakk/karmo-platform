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
        """One full pull cycle. Returns the finalized WorkerJob, or None
        if no eligible work was available. Execution is routed through
        the transport's approval-gated `execute()` -- a worker can never
        run a capability's handler outside that gate, whether or not the
        capability actually requires approval (for a NONE-requirement
        capability the gate is a pass-through, but it is still the ONLY
        path to actual execution)."""
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
            self._transport.submit_failure(leased.job_id, reason=str(error))
            raise WorkerClientError(str(error)) from error

        return self._transport.submit_result(
            leased.job_id, output=output, duration_seconds=duration,
            stdout_summary=stdout_summary, evidence_files=evidence_files,
        )
