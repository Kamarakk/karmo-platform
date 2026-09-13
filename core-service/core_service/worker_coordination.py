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

    def register_worker(self, *, worker_id, key_id, capabilities=(), metadata=None):
        """First-time enrollment only. Never updates an already-registered
        worker's key/capabilities/metadata/status, active or revoked --
        that silently allowed key rotation with no proof of possession of
        the prior key. Rotating an existing worker's key requires
        ``rotate_key`` (or ``WorkerCoordinator.rotate_worker_key``), which
        requires a credential proving possession of the *current* key."""
        if not worker_id or not key_id:
            raise WorkerCoordinationError("worker_id and key_id are required")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_workers
                    (worker_id, key_id, status, capabilities, metadata)
                VALUES (%s, %s, 'ACTIVE', %s::jsonb, %s::jsonb)
                ON CONFLICT (worker_id) DO NOTHING
                RETURNING worker_id
                """,
                (worker_id, key_id, _json(sorted(set(capabilities))), _json(metadata or {})),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(f"worker already registered: {worker_id}")

    def rotate_key(self, *, worker_id, current_key_id, new_key_id):
        """Rotate an ACTIVE worker's key. Only applies if ``current_key_id``
        still matches the worker's presently-registered key -- the caller
        must have already cryptographically proven possession of
        ``current_key_id`` (see WorkerCoordinator.rotate_worker_key)."""
        if not new_key_id:
            raise WorkerCoordinationError("new_key_id is required")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.karmo_workers
                SET key_id=%s
                WHERE worker_id=%s AND key_id=%s AND status='ACTIVE'
                RETURNING worker_id
                """,
                (new_key_id, worker_id, current_key_id),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(
                    "key rotation refused: worker is inactive/revoked, or the "
                    "presented current_key_id does not match the registered key"
                )

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

    def require_current_key(self, *, worker_id, key_id):
        """Require proof to use the worker's currently registered key.

        Cryptographic token validity is insufficient after key rotation: an old
        credential/result envelope may still be inside its TTL and still verify
        against retained key material. The durable registry is authoritative for
        which key may act for a worker now.
        """
        if not key_id:
            raise WorkerCoordinationError("worker key is required")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key_id, status FROM public.karmo_workers WHERE worker_id=%s",
                (worker_id,),
            )
            row = cur.fetchone()
            if row is None or row[1] != "ACTIVE" or row[0] != key_id:
                raise WorkerCoordinationError("worker key mismatch or worker inactive")
        return True

    def enqueue_job(self, *, idempotency_key, task_id, tool_id, tool_version, arguments_digest, approval_id=None):
        """Create a QUEUED job. ``idempotency_key`` is required and must be
        unique per real enqueue attempt (mirroring
        PostgresInvocationLedger.begin()) -- a retried call with the SAME
        key raises rather than silently creating a duplicate job, so a
        caller unsure whether a prior enqueue succeeded (e.g. after a
        network timeout) never doubles real work. A deliberate new attempt
        for the same logical task/tool (e.g. after a FAILED job) uses a new
        idempotency_key -- this is not a permanent per-task/tool lock."""
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
        """Lease a QUEUED job to a worker, and atomically claim the real
        KARMO approval that authorizes it.

        A job's ``approval_id`` is never trusted as an opaque binding
        string. It must resolve to a currently-APPROVED
        ``core_approval_records`` row whose tool_id/tool_version/
        arguments_digest match this job exactly, and whose
        authorized_executor is this worker -- the same authority-claim
        boundary PostgresExecutionCoordinator.claim() enforces for direct
        dispatch, applied here to worker-routed execution. The approval
        claim and the job lease commit as one transaction. A job with no
        approval_id can never be leased -- worker execution is never a
        path around Core's approval engine.
        """
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
                    "job has no approval_id; worker execution requires a real, "
                    "approved KARMO authority record and is never granted implicitly"
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
            return WorkerLease(
                job_id=job_id,
                task_id=str(task_id),
                worker_id=worker_id,
                lease_token=lease_token,
                tool_id=tool_id,
                tool_version=tool_version,
                arguments_digest=arguments_digest,
                approval_id=str(approval_id),
                attempt_count=int(row[0]),
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

    def _require_active_worker(self, cur, worker_id, now):
        """Revocation and heartbeat staleness must be effective against
        in-flight work, not just at heartbeat/lease time -- a worker that
        goes dark or gets revoked after leasing a job must not be able to
        consume its ticket or have a result accepted."""
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
        """Consume a ticket only while its exact job lease is still live.

        Ticket TTL is not an independent grant of execution authority. If the
        job lease expired, was recovered, was reassigned, or its lease token
        changed, execution must fail closed even when the coordinator-signed
        ticket itself has time remaining.
        """
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
                (
                    now, digest, lease.job_id, lease.worker_id, now,
                    lease.lease_token, now,
                ),
            )
            if cur.fetchone() is None:
                raise WorkerCoordinationError(
                    "execution ticket invalid, expired, already consumed, or job lease is no longer live"
                )
        return digest

    def submit_authenticated_result(
        self, *, lease: WorkerLease, ticket_digest: str,
        result_digest, result_envelope,
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

    def finalize_job(self, *, job_id, success: bool, error=None):
        """Finalize a submitted result only when every durable authority/audit
        binding is still intact. Any missing or mismatched invocation/approval
        row fails the transaction closed and leaves the job RESULT_SUBMITTED for
        reconciliation rather than manufacturing a successful terminal state."""
        target = "SUCCEEDED" if success else "FAILED"
        approval_state = ApprovalState.EXECUTED if success else ApprovalState.FAILED
        invocation_status = "EXECUTED" if success else "FAILED"
        now = self._clock()
        invocation_key = f"worker-job:{job_id}"

        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT approval_id, result_digest FROM public.karmo_worker_jobs "
                "WHERE job_id=%s::uuid AND state='RESULT_SUBMITTED' FOR UPDATE",
                (job_id,),
            )
            job = cur.fetchone()
            if job is None:
                raise WorkerCoordinationError("job is not awaiting finalization")
            approval_id, result_digest = job
            if approval_id is None:
                raise WorkerCoordinationError("worker job is missing its approval binding")

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

            approval.transition(
                approval_state, "system", f"worker job {target.lower()}", now,
            )
            cur.execute(
                "UPDATE public.core_approval_records SET state=%s, "
                "audit_trail=%s::jsonb, version=version+1, updated_at=%s "
                "WHERE approval_id=%s::uuid AND state=%s AND execution_binding=%s",
                (
                    approval.state.value,
                    _json(approval.audit_trail),
                    now,
                    approval_id,
                    ApprovalState.CLAIMED.value,
                    str(invocation_id),
                ),
            )
            if cur.rowcount != 1:
                raise WorkerCoordinationError("worker approval finalization binding changed")

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

    def rotate_worker_key(self, *, credential_token, worker_id, new_key_id):
        """Rotate a worker's key. The presented credential must be signed
        with the worker's CURRENT key -- this is what register_worker no
        longer allows to happen without proof."""
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
