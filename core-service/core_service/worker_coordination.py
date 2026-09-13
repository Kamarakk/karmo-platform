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

from .control import ApprovalState
from .persistence import _APPROVAL_COLUMNS, PostgresApprovalStore


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

    @staticmethod
    def _append_event(cur, *, event_key, event_type, worker_id=None, job_id=None, payload=None):
        """Append one immutable worker-control event inside the caller transaction.

        Event keys are deterministic for the state transition they describe so a
        duplicate execution path cannot manufacture duplicate audit history.
        """
        cur.execute(
            """
            INSERT INTO public.karmo_worker_events
                (event_id, event_key, worker_id, job_id, event_type, payload)
            VALUES (%s::uuid, %s, %s, %s::uuid, %s, %s::jsonb)
            ON CONFLICT (event_key) DO NOTHING
            RETURNING event_id
            """,
            (
                str(uuid.uuid4()), event_key, worker_id, job_id,
                event_type, _json(payload or {}),
            ),
        )
        if cur.fetchone() is None:
            raise WorkerCoordinationError(f"duplicate worker event key: {event_key}")

    def register_worker(self, *, worker_id, key_id, capabilities=(), metadata=None):
        """First-time enrollment only. Never updates an already-registered worker."""
        if not worker_id or not key_id:
            raise WorkerCoordinationError("worker_id and key_id are required")
        capabilities = sorted(set(capabilities))
        metadata = metadata or {}
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_workers
                    (worker_id, key_id, status, capabilities, metadata)
                VALUES (%s, %s, 'ACTIVE', %s::jsonb, %s::jsonb)
                ON CONFLICT (worker_id) DO NOTHING
                RETURNING credential_version
                """,
                (worker_id, key_id, _json(capabilities), _json(metadata)),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkerCoordinationError(f"worker already registered: {worker_id}")
            credential_version = int(row[0])
            self._append_event(
                cur,
                event_key=f"worker:{worker_id}:registered:v{credential_version}",
                event_type="WORKER_REGISTERED",
                worker_id=worker_id,
                payload={
                    "key_id": key_id,
                    "credential_version": credential_version,
                    "capabilities": capabilities,
                },
            )

    def rotate_key(self, *, worker_id, current_key_id, new_key_id):
        """Rotate an ACTIVE worker key only while the worker is drained.

        Rotation must use a new key identifier. Reusing the same key_id makes
        credential invalidation ambiguous because credentials bind to key_id.
        Active leased work also makes rotation ambiguous, so rotation refuses
        until the worker has no LEASED jobs. A successful rotation increments
        credential_version and clears heartbeat authority; the new key must
        authenticate a fresh heartbeat before new work can be leased.
        """
        if not new_key_id:
            raise WorkerCoordinationError("new_key_id is required")
        if new_key_id == current_key_id:
            raise WorkerCoordinationError("key rotation requires a distinct new_key_id")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key_id, status, credential_version FROM public.karmo_workers "
                "WHERE worker_id=%s FOR UPDATE",
                (worker_id,),
            )
            worker = cur.fetchone()
            if worker is None or worker[1] != "ACTIVE" or worker[0] != current_key_id:
                raise WorkerCoordinationError(
                    "key rotation refused: worker is inactive/revoked, or the "
                    "presented current_key_id does not match the registered key"
                )
            cur.execute(
                "SELECT 1 FROM public.karmo_worker_jobs "
                "WHERE worker_id=%s AND state='LEASED' LIMIT 1 FOR UPDATE",
                (worker_id,),
            )
            if cur.fetchone() is not None:
                raise WorkerCoordinationError(
                    "key rotation refused while worker has leased work; drain or reconcile it first"
                )
            next_version = int(worker[2]) + 1
            cur.execute(
                """
                UPDATE public.karmo_workers
                SET key_id=%s, credential_version=%s,
                    last_seen_at=NULL, lease_expires_at=NULL
                WHERE worker_id=%s AND key_id=%s AND status='ACTIVE'
                RETURNING worker_id
                """,
                (new_key_id, next_version, worker_id, current_key_id),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("worker key changed concurrently")
            self._append_event(
                cur,
                event_key=f"worker:{worker_id}:key-rotated:v{next_version}",
                event_type="WORKER_KEY_ROTATED",
                worker_id=worker_id,
                payload={
                    "old_key_id": current_key_id,
                    "new_key_id": new_key_id,
                    "credential_version": next_version,
                    "heartbeat_reset": True,
                },
            )

    def revoke_worker(self, worker_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE public.karmo_workers SET status='REVOKED', lease_expires_at=NULL "
                "WHERE worker_id=%s AND status<>'REVOKED' RETURNING key_id, credential_version",
                (worker_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkerCoordinationError("worker missing or already revoked")
            self._append_event(
                cur,
                event_key=f"worker:{worker_id}:revoked:v{int(row[1])}",
                event_type="WORKER_REVOKED",
                worker_id=worker_id,
                payload={"key_id": row[0], "credential_version": int(row[1])},
            )

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

    def require_current_key(self, *, worker_id, key_id):
        """Require proof to use the worker's currently registered key."""
        if not key_id:
            raise WorkerCoordinationError("worker key is required")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key_id, status FROM public.karmo_workers WHERE worker_id=%s",
                (worker_id,),
            )
            row = cur.fetchone()
            if row is None or row[1] != "ACTIVE" or row[0] != key_id:
                raise WorkerCoordinationError("worker is not active or key mismatch")
        return True

    def enqueue_job(self, *, idempotency_key, task_id, tool_id, tool_version, arguments_digest, approval_id=None):
        if not idempotency_key:
            raise WorkerCoordinationError("idempotency_key is required to enqueue a worker job")
        job_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_worker_jobs
                    (job_id, idempotency_key, task_id, approval_id, tool_id, tool_version, arguments_digest, state)
                VALUES (%s::uuid, %s, %s::uuid, %s::uuid, %s, %s, %s, 'QUEUED')
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING job_id
                """,
                (job_id, idempotency_key, task_id, approval_id, tool_id, tool_version, arguments_digest),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(f"duplicate worker-job idempotency key: {idempotency_key}")
        return job_id

    def get_job_by_idempotency_key(self, idempotency_key):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT job_id, state FROM public.karmo_worker_jobs WHERE idempotency_key=%s",
                (idempotency_key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {"job_id": str(row[0]), "state": row[1]}

    def lease_job(self, *, job_id, worker_id, lease_seconds=60):
        if lease_seconds <= 0:
            raise WorkerCoordinationError("lease_seconds must be positive")
        now = self._clock()
        lease_expires = now + timedelta(seconds=lease_seconds)
        lease_token = str(uuid.uuid4())
        invocation_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, lease_expires_at FROM public.karmo_workers WHERE worker_id=%s FOR UPDATE",
                (worker_id,),
            )
            worker = cur.fetchone()
            if worker is None or worker[0] != "ACTIVE":
                raise WorkerCoordinationError("worker is not active")
            if worker[1] is None or worker[1] <= now:
                raise WorkerCoordinationError("worker heartbeat lease expired or missing")

            cur.execute(
                "SELECT task_id, tool_id, tool_version, arguments_digest, approval_id, attempt_count "
                "FROM public.karmo_worker_jobs WHERE job_id=%s::uuid AND state='QUEUED' FOR UPDATE",
                (job_id,),
            )
            job = cur.fetchone()
            if job is None:
                raise WorkerCoordinationError("job is not available for lease")
            task_id, tool_id, tool_version, arguments_digest, approval_id, attempt_count = job

            if approval_id is None:
                raise WorkerCoordinationError(
                    "job has no approval_id; worker execution requires a real, approved KARMO authority record"
                )

            cur.execute(
                f"SELECT {_APPROVAL_COLUMNS} FROM public.core_approval_records "
                "WHERE approval_id=%s::uuid FOR UPDATE",
                (approval_id,),
            )
            approval_row = cur.fetchone()
            if approval_row is None:
                raise WorkerCoordinationError(f"no such approval: {approval_id}")
            approval = PostgresApprovalStore._decode(approval_row)
            if approval.state != ApprovalState.APPROVED:
                raise WorkerCoordinationError(
                    f"cannot lease job: approval {approval_id} is {approval.state.value}, not APPROVED"
                )
            if (
                approval.tool_id != tool_id
                or approval.tool_version != tool_version
                or approval.arguments_digest != arguments_digest
            ):
                raise WorkerCoordinationError(
                    "cannot lease job: approval does not match this job's tool/version/arguments"
                )
            if approval.authorized_executor != worker_id:
                raise WorkerCoordinationError(
                    "cannot lease job: this worker is not the approval's authorized executor"
                )

            cur.execute(
                """
                INSERT INTO public.tool_invocation_ledger (
                    invocation_id, idempotency_key, task_id, tool_id, tool_version, requester,
                    model_identity, executor_identity, arguments_digest, authority_decision,
                    approval_id, status
                ) VALUES (
                    %s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid, 'STARTED'
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING invocation_id
                """,
                (
                    invocation_id, f"worker-job:{job_id}", task_id, tool_id, tool_version,
                    approval.requester, None, worker_id, arguments_digest,
                    approval.authority_class, approval_id,
                ),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(f"duplicate lease attempt for job {job_id}")

            approval.execution_binding = invocation_id
            approval.transition(
                ApprovalState.CLAIMED, "system",
                f"execution authority claimed by worker {worker_id}", now,
            )
            cur.execute(
                "UPDATE public.core_approval_records SET state=%s, execution_binding=%s, "
                "audit_trail=%s::jsonb, version=version+1, updated_at=NOW() WHERE approval_id=%s::uuid",
                (approval.state.value, invocation_id, _json(approval.audit_trail), approval_id),
            )

            cur.execute(
                """
                UPDATE public.karmo_worker_jobs
                SET state='LEASED', worker_id=%s, lease_token=%s::uuid,
                    lease_expires_at=%s, attempt_count=attempt_count+1, updated_at=%s
                WHERE job_id=%s::uuid AND state='QUEUED'
                RETURNING attempt_count
                """,
                (worker_id, lease_token, lease_expires, now, job_id),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkerCoordinationError("job is not available for lease")
            attempt_count = int(row[0])
            self._append_event(
                cur,
                event_key=f"job:{job_id}:leased:{lease_token}",
                event_type="JOB_LEASED",
                worker_id=worker_id,
                job_id=job_id,
                payload={
                    "attempt_count": attempt_count,
                    "lease_expires_at": lease_expires.isoformat(),
                    "approval_id": str(approval_id),
                    "invocation_id": invocation_id,
                },
            )
            return WorkerLease(
                job_id=job_id,
                task_id=str(task_id),
                worker_id=worker_id,
                lease_token=lease_token,
                tool_id=tool_id,
                tool_version=tool_version,
                arguments_digest=arguments_digest,
                approval_id=str(approval_id),
                attempt_count=attempt_count,
                lease_expires_at=lease_expires,
            )

    def record_ticket(self, *, token, lease: WorkerLease, expires_at: datetime):
        digest = _digest_token(token)
        now = self._clock()
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_execution_tickets
                    (ticket_digest, job_id, worker_id, expires_at)
                SELECT %s, %s::uuid, %s, %s
                WHERE EXISTS (
                    SELECT 1 FROM public.karmo_worker_jobs j
                    WHERE j.job_id=%s::uuid AND j.state='LEASED'
                      AND j.worker_id=%s AND j.lease_token=%s::uuid
                      AND j.lease_expires_at>%s
                )
                ON CONFLICT (ticket_digest) DO NOTHING
                RETURNING ticket_digest
                """,
                (
                    digest, lease.job_id, lease.worker_id, expires_at,
                    lease.job_id, lease.worker_id, lease.lease_token, now,
                ),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("execution ticket refused: duplicate or job lease is no longer live")
            self._append_event(
                cur,
                event_key=f"ticket:{digest}:issued",
                event_type="EXECUTION_TICKET_ISSUED",
                worker_id=lease.worker_id,
                job_id=lease.job_id,
                payload={"ticket_digest": digest, "expires_at": expires_at.isoformat()},
            )
        return digest

    def _require_active_worker(self, cur, worker_id, now):
        cur.execute(
            "SELECT status, lease_expires_at FROM public.karmo_workers WHERE worker_id=%s FOR UPDATE",
            (worker_id,),
        )
        worker = cur.fetchone()
        if worker is None or worker[0] != "ACTIVE":
            raise WorkerCoordinationError("worker is not active")
        if worker[1] is None or worker[1] <= now:
            raise WorkerCoordinationError("worker heartbeat lease expired or missing")

    def consume_ticket(self, *, token, lease: WorkerLease):
        digest = _digest_token(token)
        now = self._clock()
        with self._connection_factory() as conn, conn.cursor() as cur:
            self._require_active_worker(cur, lease.worker_id, now)
            cur.execute(
                """
                UPDATE public.karmo_execution_tickets AS t
                SET consumed_at=%s
                WHERE t.ticket_digest=%s AND t.job_id=%s::uuid AND t.worker_id=%s
                  AND t.consumed_at IS NULL AND t.expires_at>%s
                  AND EXISTS (
                      SELECT 1 FROM public.karmo_worker_jobs j
                      WHERE j.job_id=t.job_id AND j.state='LEASED'
                        AND j.worker_id=t.worker_id AND j.lease_token=%s::uuid
                        AND j.lease_expires_at>%s
                  )
                RETURNING t.ticket_digest
                """,
                (now, digest, lease.job_id, lease.worker_id, now, lease.lease_token, now),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(
                    "execution ticket invalid, expired, already consumed, or job lease is no longer live"
                )
            self._append_event(
                cur,
                event_key=f"ticket:{digest}:consumed",
                event_type="EXECUTION_TICKET_CONSUMED",
                worker_id=lease.worker_id,
                job_id=lease.job_id,
                payload={"ticket_digest": digest},
            )
        return digest

    def submit_authenticated_result(
        self, *, lease: WorkerLease, ticket_digest: str, result_digest, result_envelope,
    ):
        now = self._clock()
        with self._connection_factory() as conn, conn.cursor() as cur:
            self._require_active_worker(cur, lease.worker_id, now)
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
            self._append_event(
                cur,
                event_key=f"job:{lease.job_id}:result:{result_digest}",
                event_type="RESULT_SUBMITTED",
                worker_id=lease.worker_id,
                job_id=lease.job_id,
                payload={"result_digest": result_digest, "ticket_digest": ticket_digest},
            )

    def finalize_job(self, *, job_id, success: bool, error=None):
        target = "SUCCEEDED" if success else "FAILED"
        approval_state = ApprovalState.EXECUTED if success else ApprovalState.FAILED
        invocation_status = "EXECUTED" if success else "FAILED"
        now = self._clock()
        invocation_key = f"worker-job:{job_id}"

        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT approval_id, result_digest, worker_id FROM public.karmo_worker_jobs "
                "WHERE job_id=%s::uuid AND state='RESULT_SUBMITTED' FOR UPDATE",
                (job_id,),
            )
            job = cur.fetchone()
            if job is None:
                raise WorkerCoordinationError("job is not awaiting finalization")
            approval_id, result_digest, worker_id = job
            if approval_id is None:
                raise WorkerCoordinationError("worker job is missing its approval binding")
            if not result_digest:
                raise WorkerCoordinationError("worker job is missing its authenticated result digest")

            cur.execute(
                "SELECT invocation_id, approval_id FROM public.tool_invocation_ledger "
                "WHERE idempotency_key=%s AND completed_at IS NULL FOR UPDATE",
                (invocation_key,),
            )
            invocation = cur.fetchone()
            if invocation is None:
                raise WorkerCoordinationError("worker invocation audit row is missing or already terminal")
            invocation_id, invocation_approval_id = invocation
            if str(invocation_approval_id) != str(approval_id):
                raise WorkerCoordinationError("worker invocation approval binding mismatch")

            cur.execute(
                f"SELECT {_APPROVAL_COLUMNS} FROM public.core_approval_records "
                "WHERE approval_id=%s::uuid FOR UPDATE",
                (approval_id,),
            )
            approval_row = cur.fetchone()
            if approval_row is None:
                raise WorkerCoordinationError("worker approval record is missing")
            approval = PostgresApprovalStore._decode(approval_row)
            if approval.state != ApprovalState.CLAIMED:
                raise WorkerCoordinationError(
                    f"worker approval is {approval.state.value}, expected CLAIMED"
                )
            if approval.execution_binding != str(invocation_id):
                raise WorkerCoordinationError("worker approval execution binding mismatch")

            cur.execute(
                """
                UPDATE public.karmo_worker_jobs
                SET state=%s, last_error=%s, updated_at=%s
                WHERE job_id=%s::uuid AND state='RESULT_SUBMITTED'
                RETURNING job_id
                """,
                (target, error, now, job_id),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError("job is not awaiting finalization")

            cur.execute(
                "UPDATE public.tool_invocation_ledger SET status=%s, result_digest=%s, "
                "completed_at=%s WHERE invocation_id=%s::uuid AND completed_at IS NULL",
                (invocation_status, result_digest, now, invocation_id),
            )
            if cur.rowcount != 1:
                raise WorkerCoordinationError("worker invocation finalization failed")

            approval.transition(approval_state, "system", f"worker job {target.lower()}", now)
            cur.execute(
                "UPDATE public.core_approval_records SET state=%s, "
                "audit_trail=%s::jsonb, version=version+1, updated_at=%s "
                "WHERE approval_id=%s::uuid AND state=%s AND execution_binding=%s",
                (
                    approval.state.value, _json(approval.audit_trail), now,
                    approval_id, ApprovalState.CLAIMED.value, str(invocation_id),
                ),
            )
            if cur.rowcount != 1:
                raise WorkerCoordinationError("worker approval finalization binding changed")
            self._append_event(
                cur,
                event_key=f"job:{job_id}:final:{target}",
                event_type=f"JOB_{target}",
                worker_id=worker_id,
                job_id=job_id,
                payload={
                    "result_digest": result_digest,
                    "approval_id": str(approval_id),
                    "invocation_id": str(invocation_id),
                },
            )

    def recover_expired_leases(self):
        """Mark unknown leased work for reconciliation; never auto-replay it."""
        now = self._clock()
        recovered = []
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_worker_jobs
                SET state='RECOVERY_REQUIRED', lease_token=NULL,
                    lease_expires_at=NULL, updated_at=%s,
                    last_error='lease expired with unknown execution outcome; reconcile before retry'
                WHERE state='LEASED' AND lease_expires_at<=%s
                RETURNING job_id, worker_id, attempt_count
                """,
                (now, now),
            )
            rows = cur.fetchall()
            for job_id, worker_id, attempt_count in rows:
                job_id = str(job_id)
                self._append_event(
                    cur,
                    event_key=f"job:{job_id}:recovery:attempt-{int(attempt_count)}",
                    event_type="RECOVERY_REQUIRED",
                    worker_id=worker_id,
                    job_id=job_id,
                    payload={
                        "reason": "lease_expired_unknown_outcome",
                        "automatic_replay": False,
                        "attempt_count": int(attempt_count),
                    },
                )
                recovered.append(job_id)
        return recovered

    def purge_terminal_tickets(self, *, retention_seconds=604800):
        """Delete old ticket rows only after their jobs are terminal.

        Recovery evidence is retained: tickets for LEASED, RESULT_SUBMITTED, or
        RECOVERY_REQUIRED jobs are never removed by this cleanup path.
        """
        if int(retention_seconds) < 3600:
            raise WorkerCoordinationError("ticket retention must be at least 3600 seconds")
        cutoff = self._clock() - timedelta(seconds=int(retention_seconds))
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM public.karmo_execution_tickets t
                USING public.karmo_worker_jobs j
                WHERE t.job_id=j.job_id
                  AND j.state IN ('SUCCEEDED','FAILED','CANCELLED')
                  AND t.expires_at<=%s
                """,
                (cutoff,),
            )
            return cur.rowcount

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

    def rotate_worker_key(self, *, credential_token, worker_id, new_key_id):
        payload = self.worker_authenticator.verify(credential_token, expected_worker_id=worker_id)
        self.store.rotate_key(worker_id=worker_id, current_key_id=payload["key_id"], new_key_id=new_key_id)

    def issue_execution_ticket(self, *, credential_token, lease: WorkerLease, ttl_seconds=120):
        credential = self.worker_authenticator.verify(
            credential_token, expected_worker_id=lease.worker_id
        )
        self.store.require_current_key(
            worker_id=lease.worker_id, key_id=credential["key_id"]
        )
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
        self.store.consume_ticket(token=token, lease=lease)
        return True

    def accept_result(self, *, execution_ticket, lease: WorkerLease, result, envelope):
        envelope_payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
        self.store.require_current_key(
            worker_id=lease.worker_id, key_id=envelope_payload.get("key_id")
        )
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
