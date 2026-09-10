"""KARMO Worker Runtime -- transport abstraction (Phase 7).

The worker never talks to the coordinator's internals directly -- only
through this interface. LocalTransport implements it in-process (function
calls) for this isolated prototype. A future network transport (e.g. over
Tailscale) implements the exact same interface with real requests,
without worker_client.py's own logic changing at all. No inbound port is
opened on the worker by anything in this module -- the worker only ever
initiates outbound calls (poll, heartbeat, submit), matching the
pull-based architecture explicitly required.

NOTE on `execute()`/`resume()` and the in-process prototype limitation:
both take a local Python callable (`action`) so that approval-gating
(which only the coordinator's ApprovalEngine can decide) and the actual
sandboxed execution (which only the worker can perform) happen as a
single atomic step, with the approval consumed exactly if and only if
`action()` actually ran. That is trivial to express in-process, as
`LocalTransport` does below. A real network transport CANNOT send a
callable over the wire -- it will need a different shape (e.g. the
coordinator returns a signed "execution ticket" bound to the exact
approval + arguments digest, the worker executes locally and presents the
ticket back with its result, and the coordinator's ApprovalEngine.execute
validates+consumes the ticket against the presented result at that point)
before Phase 15's network plan can be implemented. This limitation is
unchanged and still explicitly not redesigned by `resume()`'s addition --
it inherits `execute()`'s exact same callable-based shape and the exact
same network gap. See KARMO_WORKER_RUNTIME_NETWORK_PLAN.md.
"""

from abc import ABC, abstractmethod


class WorkerTransport(ABC):
    @abstractmethod
    def register(self, **kwargs):
        ...

    @abstractmethod
    def heartbeat(self, worker_id, **kwargs):
        ...

    @abstractmethod
    def poll(self, worker_id, capabilities):
        """Returns a leased WorkerJob, or None if no eligible job exists."""

    @abstractmethod
    def execute(self, job_id, *, executor_identity, presented_payload, action):
        """Runs `action()` (the worker's local sandboxed execution) only
        if approval-gating (coordinator-owned) allows it. See the module
        docstring's note on this method's in-process-only shape."""

    @abstractmethod
    def request_approval(self, job_id, *, requester):
        """Parks an approval-required job in WAITING_FOR_APPROVAL and
        opens a real approval request. NOT a failure path -- a job
        legitimately waiting on a human is not a broken job. A no-op
        (job stays RUNNING) for a NONE-authority-requirement job."""

    @abstractmethod
    def resume(self, worker_id, job_id, *, presented_payload, action):
        """Checks on (and executes, if now approved) a job previously
        parked via request_approval. Returns None if still pending --
        not an error, safe to call again later. See the module
        docstring's note on this method's in-process-only shape (same
        limitation as execute())."""

    @abstractmethod
    def submit_result(self, job_id, **kwargs):
        ...

    @abstractmethod
    def submit_failure(self, job_id, **kwargs):
        ...


class LocalTransport(WorkerTransport):
    """In-process transport: the worker and coordinator run in the same
    Python process, communicating only through this class's methods --
    never through shared mutable state accessed directly. This is
    deliberate: even though a network hop isn't needed yet, the worker
    code is written as if it always talks through a boundary, so swapping
    in a real network transport later is a drop-in replacement."""

    def __init__(self, coordinator):
        self._coordinator = coordinator

    def register(self, **kwargs):
        return self._coordinator.register_worker(**kwargs)

    def heartbeat(self, worker_id, **kwargs):
        return self._coordinator.heartbeat(worker_id, **kwargs)

    def poll(self, worker_id, capabilities):
        return self._coordinator.poll_for_job(worker_id, capabilities)

    def execute(self, job_id, *, executor_identity, presented_payload, action):
        return self._coordinator.execute_job(
            job_id, executor_identity=executor_identity, presented_payload=presented_payload, action=action,
        )

    def request_approval(self, job_id, *, requester):
        return self._coordinator.request_approval(job_id, requester=requester)

    def resume(self, worker_id, job_id, *, presented_payload, action):
        return self._coordinator.resume_job(
            job_id, worker_id=worker_id, presented_payload=presented_payload, action=action,
        )

    def submit_result(self, job_id, **kwargs):
        return self._coordinator.finalize_success(job_id, **kwargs)

    def submit_failure(self, job_id, **kwargs):
        return self._coordinator.finalize_failure(job_id, **kwargs)
