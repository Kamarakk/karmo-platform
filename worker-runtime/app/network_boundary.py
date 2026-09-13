"""Authenticated boundary for future KARMO distributed workers.

This module deliberately does not open a socket. It hardens the coordinator-facing
contract first so a later HTTPS/pull transport can reuse one authenticated boundary
instead of duplicating authorization logic in a network handler.

Network reachability never grants KARMO authority. Every worker-originated call is
bound to a short-lived worker credential; successful results additionally require a
worker-bound result-authentication envelope.
"""

from __future__ import annotations

from crypto_boundary import CryptoBoundaryError


class NetworkBoundaryError(RuntimeError):
    """Fail-closed error exposed by the authenticated worker boundary."""


class SecureCoordinatorBoundary:
    """Authenticate worker-originated coordinator operations."""

    def __init__(self, coordinator, *, worker_authenticator, result_authenticator):
        self._coordinator = coordinator
        self._worker_authenticator = worker_authenticator
        self._result_authenticator = result_authenticator

    def _authenticate(self, worker_id: str, credential: str):
        if not worker_id or not credential:
            raise NetworkBoundaryError("worker identity and credential are required")
        try:
            return self._worker_authenticator.verify(
                credential, expected_worker_id=worker_id
            )
        except CryptoBoundaryError as exc:
            raise NetworkBoundaryError("worker authentication failed") from exc

    def register(self, *, worker_id: str, credential: str, **identity):
        self._authenticate(worker_id, credential)
        return self._coordinator.register_worker(worker_id=worker_id, **identity)

    def heartbeat(self, worker_id: str, *, credential: str, **kwargs):
        self._authenticate(worker_id, credential)
        return self._coordinator.heartbeat(worker_id, **kwargs)

    def poll(self, worker_id: str, capabilities, *, credential: str):
        self._authenticate(worker_id, credential)
        return self._coordinator.poll_for_job(worker_id, capabilities)

    def request_approval(self, worker_id: str, job_id: str, *, credential: str):
        self._authenticate(worker_id, credential)
        job = self._coordinator.jobs.get(job_id)
        if job.assigned_worker_id != worker_id:
            raise NetworkBoundaryError("job is not assigned to authenticated worker")
        return self._coordinator.request_approval(
            job_id, requester=f"worker:{worker_id}"
        )

    def submit_failure(
        self, worker_id: str, job_id: str, *, credential: str, reason: str
    ):
        self._authenticate(worker_id, credential)
        job = self._coordinator.jobs.get(job_id)
        if job.assigned_worker_id != worker_id:
            raise NetworkBoundaryError("job is not assigned to authenticated worker")
        return self._coordinator.finalize_failure(job_id, reason=reason)

    def submit_result(
        self,
        worker_id: str,
        job_id: str,
        *,
        credential: str,
        result_authentication: dict,
        output: dict,
        duration_seconds: float,
        stdout_summary: str,
        evidence_files=None,
        execution_ticket_digest: str | None = None,
    ):
        self._authenticate(worker_id, credential)
        job = self._coordinator.jobs.get(job_id)
        if job.assigned_worker_id != worker_id:
            raise NetworkBoundaryError("job is not assigned to authenticated worker")
        try:
            self._result_authenticator.verify(
                result_authentication,
                worker_id=worker_id,
                task_id=job_id,
                result=output,
                execution_ticket_digest=execution_ticket_digest,
            )
        except CryptoBoundaryError as exc:
            raise NetworkBoundaryError("worker result authentication failed") from exc
        return self._coordinator.finalize_success(
            job_id,
            output=output,
            duration_seconds=duration_seconds,
            stdout_summary=stdout_summary,
            evidence_files=evidence_files or [],
        )
