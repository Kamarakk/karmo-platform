"""Durable KARMO Worker coordination.

Core remains the authority boundary. This module stores Worker identity metadata,
leases, job state, execution-ticket consumption, authenticated result state, and
recovery evidence. It does not open a network listener or grant authority based
on reachability.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class WorkerCoordinationError(RuntimeError):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, default=str)


def _digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkerLease:
    job_id: str
    task_id: str
    worker_id: str
    lease_token: str
    tool_id: str
    tool_version: str
    arguments_digest: str
    approval_id: str | None
    attempt_count: int
    lease_expires_at: datetime


class PostgresWorkerCoordinatorStore:
    def __init__(self, connection_factory, *, clock=None):
        self._connection_factory = connection_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def register_worker(self, *, worker_id, key_id, capabilities=(), metadata=None):
        if not worker_id or not key_id:
            raise WorkerCoordinationError("worker_id and key_id are required")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_workers
                    (worker_id, key_id, status, capabilities, metadata)
                VALUES (%s, %s, 'ACTIVE', %s::jsonb, %s::jsonb)
                ON CONFLICT (worker_id) DO UPDATE SET
                    key_id=EXCLUDED.key_id,
                    capabilities=EXCLUDED.capabilities,
                    metadata=EXCLUDED.metadata,
                    status=CASE WHEN public.karmo_workers.status='REVOKED'
                                THEN 'REVOKED' ELSE 'ACTIVE' END
                RETURNING status
                """,
                (worker_id, key_id, _json(sorted(set(capabilities))), _json(metadata or {})),
            )
            status = cur.fetchone()[0]
            if status != "ACTIVE":
                raise WorkerCoordinationError("revoked worker cannot be reactivated implicitly")

    def revoke_worker(self, worker_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE public.karmo_workers SET status='REVOKED', lease_expires_at=NULL "
                "WHERE worker_id=%s AND status<>'REVOKED'",
                (worker_id,),
            )
            if cur.rowcount != 1:
                raise WorkerCoordinationError("worker missing or already revoked")

    def heartbeat(self, *, worker_id, credential_key_id, lease_seconds=90):
        if lease_seconds <= 0:
            raise WorkerCoordinationError("lease_seconds must be positive")
        now = self._clock()
        expires = now + timedelta(seconds=lease_seconds)
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_workers
                SET last_seen_at=%s, lease_expires_at=%s
                WHERE worker_id=%s AND key_id=%s AND status='ACTIVE'
                RETURNING worker_id
                """,
                (now, expires, worker_id, credential_key_id),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("worker identity/key mismatch or worker inactive")
        return expires

    def enqueue_job(self, *, task_id, tool_id, tool_version, arguments_digest, approval_id=None):
        job_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_worker_jobs
                    (job_id, task_id, approval_id, tool_id, tool_version, arguments_digest, state)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, 'QUEUED')
                """,
                (job_id, task_id, approval_id, tool_id, tool_version, arguments_digest),
            )
        return job_id

    def lease_job(self, *, job_id, worker_id, lease_seconds=60):
        if lease_seconds <= 0:
            raise WorkerCoordinationError("lease_seconds must be positive")
        now = self._clock()
        lease_expires = now + timedelta(seconds=lease_seconds)
        lease_token = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, lease_expires_at FROM public.karmo_workers WHERE worker_id=%s FOR UPDATE",
                (worker_id,),
            )
            worker = cur.fetchone()
            if worker is None or worker[0] != "ACTIVE":
                raise WorkerCoordinationError("worker is not active")
            if worker[1] is not None and worker[1] <= now:
                raise WorkerCoordinationError("worker heartbeat lease expired")
            cur.execute(
                """
                UPDATE public.karmo_worker_jobs
                SET state='LEASED', worker_id=%s, lease_token=%s::uuid,
                    lease_expires_at=%s, attempt_count=attempt_count+1, updated_at=%s
                WHERE job_id=%s::uuid AND state='QUEUED'
                RETURNING task_id, tool_id, tool_version, arguments_digest,
                          approval_id, attempt_count
                """,
                (worker_id, lease_token, lease_expires, now, job_id),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkerCoordinationError("job is not available for lease")
            return WorkerLease(
                job_id=job_id,
                task_id=str(row[0]),
                worker_id=worker_id,
                lease_token=lease_token,
                tool_id=row[1],
                tool_version=row[2],
                arguments_digest=row[3],
                approval_id=str(row[4]) if row[4] is not None else None,
                attempt_count=int(row[5]),
                lease_expires_at=lease_expires,
            )

    def record_ticket(self, *, token, lease: WorkerLease, expires_at: datetime):
        digest = _digest_token(token)
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_execution_tickets
                    (ticket_digest, job_id, worker_id, expires_at)
                VALUES (%s, %s::uuid, %s, %s)
                ON CONFLICT (ticket_digest) DO NOTHING
                RETURNING ticket_digest
                """,
                (digest, lease.job_id, lease.worker_id, expires_at),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("duplicate execution ticket")
        return digest

    def consume_ticket(self, *, token, job_id, worker_id):
        digest = _digest_token(token)
        now = self._clock()
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_execution_tickets
                SET consumed_at=%s
                WHERE ticket_digest=%s AND job_id=%s::uuid AND worker_id=%s
                  AND consumed_at IS NULL AND expires_at>%s
                RETURNING ticket_digest
                """,
                (now, digest, job_id, worker_id, now),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("execution ticket invalid, expired, or already consumed")
        return digest

    def submit_authenticated_result(
        self, *, lease: WorkerLease, ticket_digest: str,
        result_digest, result_envelope,
    ):
        now = self._clock()
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_worker_jobs AS j
                SET state='RESULT_SUBMITTED', result_digest=%s,
                    result_envelope=%s::jsonb, lease_token=NULL,
                    lease_expires_at=NULL, updated_at=%s
                WHERE j.job_id=%s::uuid AND j.state='LEASED' AND j.worker_id=%s
                  AND j.lease_token=%s::uuid AND j.lease_expires_at>%s
                  AND EXISTS (
                      SELECT 1 FROM public.karmo_execution_tickets t
                      WHERE t.ticket_digest=%s AND t.job_id=j.job_id
                        AND t.worker_id=j.worker_id AND t.consumed_at IS NOT NULL
                  )
                RETURNING j.job_id
                """,
                (
                    result_digest, _json(result_envelope), now, lease.job_id,
                    lease.worker_id, lease.lease_token, now, ticket_digest,
                ),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(
                    "result rejected: lease stale/mismatched or execution ticket was not consumed"
                )

    def finalize_job(self, *, job_id, success: bool, error=None):
        target = "SUCCEEDED" if success else "FAILED"
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_worker_jobs
                SET state=%s, last_error=%s, updated_at=NOW()
                WHERE job_id=%s::uuid AND state='RESULT_SUBMITTED'
                RETURNING job_id
                """,
                (target, error, job_id),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("job is not awaiting finalization")

    def recover_expired_leases(self):
        """Mark unknown leased work for reconciliation; never auto-replay it."""
        now = self._clock()
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_worker_jobs
                SET state='RECOVERY_REQUIRED', lease_token=NULL,
                    lease_expires_at=NULL, updated_at=%s,
                    last_error='lease expired with unknown execution outcome; reconcile before retry'
                WHERE state='LEASED' AND lease_expires_at<=%s
                RETURNING job_id
                """,
                (now, now),
            )
            return [str(row[0]) for row in cur.fetchall()]

    def get_job_state(self, job_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT state, worker_id, attempt_count, result_digest, last_error "
                "FROM public.karmo_worker_jobs WHERE job_id=%s::uuid",
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "state": row[0], "worker_id": row[1], "attempt_count": int(row[2]),
                "result_digest": row[3], "last_error": row[4],
            }


class WorkerCoordinator:
    """Coordinator facade around durable state and cryptographic verification."""

    def __init__(self, store, *, worker_authenticator, ticket_authority, result_authenticator, clock=None):
        self.store = store
        self.worker_authenticator = worker_authenticator
        self.ticket_authority = ticket_authority
        self.result_authenticator = result_authenticator
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def authenticate_heartbeat(self, *, credential_token, worker_id, lease_seconds=90):
        payload = self.worker_authenticator.verify(credential_token, expected_worker_id=worker_id)
        return self.store.heartbeat(
            worker_id=worker_id,
            credential_key_id=payload["key_id"],
            lease_seconds=lease_seconds,
        )

    def issue_execution_ticket(self, *, credential_token, lease: WorkerLease, ttl_seconds=120):
        self.worker_authenticator.verify(credential_token, expected_worker_id=lease.worker_id)
        token = self.ticket_authority.issue(
            approval_id=lease.approval_id or "none",
            arguments_digest=lease.arguments_digest,
            executor_identity=lease.worker_id,
            task_id=lease.task_id,
            tool_id=lease.tool_id,
            tool_version=lease.tool_version,
            ttl_seconds=ttl_seconds,
        )
        expires = self.clock() + timedelta(seconds=ttl_seconds)
        self.store.record_ticket(token=token, lease=lease, expires_at=expires)
        return token

    def authorize_execution(self, *, token, lease: WorkerLease):
        self.ticket_authority.verify(
            token,
            approval_id=lease.approval_id or "none",
            arguments_digest=lease.arguments_digest,
            executor_identity=lease.worker_id,
            task_id=lease.task_id,
            tool_id=lease.tool_id,
            tool_version=lease.tool_version,
        )
        self.store.consume_ticket(token=token, job_id=lease.job_id, worker_id=lease.worker_id)
        return True

    def accept_result(self, *, execution_ticket, lease: WorkerLease, result, envelope):
        ticket_digest = _digest_token(execution_ticket)
        self.result_authenticator.verify(
            envelope,
            worker_id=lease.worker_id,
            task_id=lease.task_id,
            result=result,
            execution_ticket_digest=ticket_digest,
        )
        digest = self.result_authenticator.result_digest(result)
        self.store.submit_authenticated_result(
            lease=lease,
            ticket_digest=ticket_digest,
            result_digest=digest,
            result_envelope=envelope,
        )
        return digest


@dataclass(frozen=True)
class OutboundTransportPolicy:
    """Transport-readiness contract. This object does not open a socket."""

    worker_inbound_listener: bool = False
    require_encrypted_transport: bool = True
    require_coordinator_authentication: bool = True
    reachability_grants_authority: bool = False
    max_connect_timeout_seconds: int = 10
    max_backoff_seconds: int = 60

    def validate(self):
        if self.worker_inbound_listener:
            raise WorkerCoordinationError("Worker inbound listener is forbidden")
        if not self.require_encrypted_transport or not self.require_coordinator_authentication:
            raise WorkerCoordinationError("encrypted authenticated coordinator transport is required")
        if self.reachability_grants_authority:
            raise WorkerCoordinationError("network reachability must never grant KARMO authority")
        if not (1 <= self.max_connect_timeout_seconds <= 30):
            raise WorkerCoordinationError("connect timeout out of bounds")
        if not (1 <= self.max_backoff_seconds <= 300):
            raise WorkerCoordinationError("backoff out of bounds")
        return True
