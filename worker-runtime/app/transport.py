"""KARMO Worker Runtime -- transport abstraction (Phase 7).

The worker never talks to the coordinator's internals directly -- only
through this interface. LocalTransport implements it in-process (function
calls) for this isolated prototype. A future network transport (e.g. over
Tailscale) implements the exact same interface with real requests,
without worker_client.py's own logic changing at all. No inbound port is
opened on the worker by anything in this module -- the worker only ever
initiates outbound calls (poll, heartbeat, submit), matching the
pull-based architecture explicitly required.
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

    def submit_result(self, job_id, **kwargs):
        return self._coordinator.finalize_success(job_id, **kwargs)

    def submit_failure(self, job_id, **kwargs):
        return self._coordinator.finalize_failure(job_id, **kwargs)
