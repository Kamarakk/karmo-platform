"""Production-shaped backend for the restricted worker SSH/stdio gateway.

This module bridges the wire protocol to the durable coordinator introduced in
PR #41. SSH reachability never grants authority: every operation authenticates
the worker credential, checks the current registered key, and delegates lease,
ticket, result, and finalization state changes to the durable coordinator/store.
"""

from __future__ import annotations

import json
from datetime import datetime

from .control import arguments_digest
from .worker_coordination import WorkerLease


class WorkerGatewayBackendError(RuntimeError):
    pass


_LEASE_FIELDS = {
    "job_id", "task_id", "worker_id", "lease_token", "tool_id",
    "tool_version", "arguments_digest", "approval_id", "attempt_count",
    "lease_expires_at",
}
_MAX_ARGUMENT_BYTES = 48 * 1024


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

    def attach_job_arguments(self, *, job_id: str, tool_id: str, tool_version: str,
                             arguments: dict, expected_arguments_digest: str):
        """Attach the exact immutable arguments needed by a remote worker.

        This is deliberately separate from PR #41's job row. If attachment
        fails, the queued job is simply not remotely dispatchable; it is never
        executed with missing, guessed, or mismatched arguments.
        """
        if not isinstance(arguments, dict):
            raise WorkerGatewayBackendError("remote job arguments must be an object")
        serialized = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
        if len(serialized.encode("utf-8")) > _MAX_ARGUMENT_BYTES:
            raise WorkerGatewayBackendError("remote job arguments exceed transport bound")
        computed = arguments_digest(tool_id, tool_version, arguments)
        if computed != expected_arguments_digest:
            raise WorkerGatewayBackendError("remote job arguments digest mismatch")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tool_id, tool_version, arguments_digest, state "
                "FROM public.karmo_worker_jobs WHERE job_id=%s::uuid FOR UPDATE",
                (job_id,),
            )
            row = cur.fetchone()
            if row is None or row[3] != "QUEUED":
                raise WorkerGatewayBackendError("remote job is missing or no longer queued")
            if row[0] != tool_id or row[1] != tool_version or row[2] != computed:
                raise WorkerGatewayBackendError("remote job binding mismatch")
            cur.execute(
                """
                INSERT INTO public.karmo_worker_job_payloads
                    (job_id, arguments, arguments_digest)
                VALUES (%s::uuid, %s::jsonb, %s)
                ON CONFLICT (job_id) DO NOTHING
                RETURNING job_id
                """,
                (job_id, serialized, computed),
            )
            if cur.fetchone() is None:
                cur.execute(
                    "SELECT arguments, arguments_digest FROM public.karmo_worker_job_payloads "
                    "WHERE job_id=%s::uuid",
                    (job_id,),
                )
                existing = cur.fetchone()
                if existing is None or existing[0] != arguments or existing[1] != computed:
                    raise WorkerGatewayBackendError("remote job arguments already differ")
        return computed

    def _candidate_jobs(self, *, worker_id: str, requested_capabilities):
        """Find bounded candidates; lease_job remains the authoritative CAS gate.

        The worker-supplied capability list can only narrow the registered set.
        It can never add capability authority. Jobs without an immutable payload
        row are intentionally invisible to remote workers.
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
                SELECT j.job_id, p.arguments
                FROM public.karmo_worker_jobs AS j
                JOIN public.core_approval_records AS a ON a.approval_id=j.approval_id
                JOIN public.karmo_worker_job_payloads AS p ON p.job_id=j.job_id
                WHERE j.state='QUEUED'
                  AND j.tool_id = ANY(%s)
                  AND p.arguments_digest=j.arguments_digest
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
            return [(str(row[0]), row[1]) for row in cur.fetchall()]

    def poll(self, *, worker_id: str, credential_token: str, capabilities):
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        candidates = self._candidate_jobs(
            worker_id=worker_id, requested_capabilities=capabilities
        )
        if not candidates:
            return None
        job_id, arguments = candidates[0]
        if not isinstance(arguments, dict):
            raise WorkerGatewayBackendError("remote job arguments record is invalid")
        lease = self.store.lease_job(job_id=job_id, worker_id=worker_id)
        if arguments_digest(lease.tool_id, lease.tool_version, arguments) != lease.arguments_digest:
            raise WorkerGatewayBackendError("leased job arguments no longer match digest")
        ticket = self.coordinator.issue_execution_ticket(
            credential_token=credential_token, lease=lease
        )
        return {
            "lease": lease_to_wire(lease),
            "arguments": arguments,
            "execution_ticket": ticket,
        }

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
