"""Production-shaped backend for the restricted worker SSH/stdio gateway.

This module bridges the wire protocol to the durable coordinator introduced in
PR #41. SSH reachability never grants authority: every operation authenticates
the worker credential, checks the current registered key, and delegates lease,
ticket, result, and finalization state changes to the durable coordinator/store.
"""

from __future__ import annotations

from datetime import datetime

from .worker_coordination import WorkerCoordinationError, WorkerLease


class WorkerGatewayBackendError(RuntimeError):
    pass


_LEASE_FIELDS = {
    "job_id", "task_id", "worker_id", "lease_token", "tool_id",
    "tool_version", "arguments_digest", "approval_id", "attempt_count",
    "lease_expires_at",
}


def lease_to_wire(lease: WorkerLease) -> dict:
    return {
        "job_id": lease.job_id,
        "task_id": lease.task_id,
        "worker_id": lease.worker_id,
        "lease_token": lease.lease_token,
        "tool_id": lease.tool_id,
        "tool_version": lease.tool_version,
        "arguments_digest": lease.arguments_digest,
        "approval_id": lease.approval_id,
        "attempt_count": lease.attempt_count,
        "lease_expires_at": lease.lease_expires_at.isoformat(),
    }


def lease_from_wire(value: dict, *, expected_worker_id: str) -> WorkerLease:
    if not isinstance(value, dict) or set(value) != _LEASE_FIELDS:
        raise WorkerGatewayBackendError("invalid lease schema")
    if value.get("worker_id") != expected_worker_id:
        raise WorkerGatewayBackendError("lease worker identity mismatch")
    for field in (
        "job_id", "task_id", "worker_id", "lease_token", "tool_id",
        "tool_version", "arguments_digest",
    ):
        if not isinstance(value.get(field), str) or not value[field]:
            raise WorkerGatewayBackendError(f"invalid lease {field}")
    approval_id = value.get("approval_id")
    if approval_id is not None and (not isinstance(approval_id, str) or not approval_id):
        raise WorkerGatewayBackendError("invalid lease approval_id")
    if not isinstance(value.get("attempt_count"), int) or value["attempt_count"] < 1:
        raise WorkerGatewayBackendError("invalid lease attempt_count")
    try:
        expires = datetime.fromisoformat(value["lease_expires_at"])
    except (TypeError, ValueError) as exc:
        raise WorkerGatewayBackendError("invalid lease expiry") from exc
    if expires.tzinfo is None:
        raise WorkerGatewayBackendError("lease expiry must be timezone-aware")
    return WorkerLease(
        job_id=value["job_id"],
        task_id=value["task_id"],
        worker_id=value["worker_id"],
        lease_token=value["lease_token"],
        tool_id=value["tool_id"],
        tool_version=value["tool_version"],
        arguments_digest=value["arguments_digest"],
        approval_id=approval_id,
        attempt_count=value["attempt_count"],
        lease_expires_at=expires,
    )


class PostgresWorkerGatewayBackend:
    """Authenticated outbound-worker gateway over the durable Core substrate."""

    def __init__(self, *, store, coordinator, connection_factory, max_poll_candidates: int = 32):
        if not (1 <= int(max_poll_candidates) <= 128):
            raise WorkerGatewayBackendError("max_poll_candidates out of bounds")
        self.store = store
        self.coordinator = coordinator
        self._connection_factory = connection_factory
        self.max_poll_candidates = int(max_poll_candidates)

    def _authenticate(self, *, worker_id: str, credential_token: str):
        payload = self.coordinator.worker_authenticator.verify(
            credential_token, expected_worker_id=worker_id
        )
        self.store.require_current_key(worker_id=worker_id, key_id=payload["key_id"])
        return payload

    def heartbeat(self, *, worker_id: str, credential_token: str, lease_seconds: int):
        expires = self.coordinator.authenticate_heartbeat(
            credential_token=credential_token,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        return {"lease_expires_at": expires.isoformat()}

    def _candidate_job_ids(self, *, worker_id: str, requested_capabilities) -> list[str]:
        """Find bounded candidates; lease_job remains the authoritative CAS gate.

        The worker-supplied capability list can only narrow the registered set.
        It can never add capability authority.
        """
        requested = sorted(set(requested_capabilities))
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT capabilities, status, lease_expires_at "
                "FROM public.karmo_workers WHERE worker_id=%s",
                (worker_id,),
            )
            worker = cur.fetchone()
            if worker is None or worker[1] != "ACTIVE":
                raise WorkerGatewayBackendError("worker is not active")
            registered = worker[0]
            if not isinstance(registered, list):
                raise WorkerGatewayBackendError("worker capability record is invalid")
            eligible = sorted(set(requested).intersection(registered))
            if not eligible:
                return []
            cur.execute(
                """
                SELECT j.job_id
                FROM public.karmo_worker_jobs AS j
                JOIN public.core_approval_records AS a ON a.approval_id=j.approval_id
                WHERE j.state='QUEUED'
                  AND j.tool_id = ANY(%s)
                  AND a.state='APPROVED'
                  AND a.authorized_executor=%s
                  AND a.tool_id=j.tool_id
                  AND a.tool_version=j.tool_version
                  AND a.arguments_digest=j.arguments_digest
                  AND a.expires_at>NOW()
                ORDER BY j.created_at, j.job_id
                LIMIT %s
                """,
                (eligible, worker_id, self.max_poll_candidates),
            )
            return [str(row[0]) for row in cur.fetchall()]

    def poll(self, *, worker_id: str, credential_token: str, capabilities):
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        for job_id in self._candidate_job_ids(
            worker_id=worker_id, requested_capabilities=capabilities
        ):
            try:
                lease = self.store.lease_job(job_id=job_id, worker_id=worker_id)
            except WorkerCoordinationError:
                # A concurrent worker/control transition may have consumed or
                # invalidated this candidate. Never broaden authority; try only
                # the next already-filtered candidate.
                continue
            ticket = self.coordinator.issue_execution_ticket(
                credential_token=credential_token, lease=lease
            )
            return {"lease": lease_to_wire(lease), "execution_ticket": ticket}
        return None

    def authorize_execution(self, *, worker_id: str, credential_token: str,
                            lease: dict, execution_ticket: str):
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        durable_lease = lease_from_wire(lease, expected_worker_id=worker_id)
        self.coordinator.authorize_execution(token=execution_ticket, lease=durable_lease)
        return {"authorized": True}

    def submit_result(self, *, worker_id: str, credential_token: str, lease: dict,
                      execution_ticket: str, result, envelope: dict,
                      success: bool, error: str | None):
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        durable_lease = lease_from_wire(lease, expected_worker_id=worker_id)
        digest = self.coordinator.accept_result(
            execution_ticket=execution_ticket,
            lease=durable_lease,
            result=result,
            envelope=envelope,
        )
        self.store.finalize_job(
            job_id=durable_lease.job_id,
            success=success,
            error=error,
        )
        return {
            "accepted": True,
            "state": "SUCCEEDED" if success else "FAILED",
            "result_digest": digest,
        }
