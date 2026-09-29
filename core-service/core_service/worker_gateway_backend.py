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
from .worker_coordination import WorkerLease, _digest_token


class WorkerGatewayBackendError(RuntimeError):
    pass


_LEASE_FIELDS = {
    "job_id", "task_id", "worker_id", "lease_token", "tool_id",
    "tool_version", "arguments_digest", "approval_id", "attempt_count",
    "lease_expires_at",
}
# Arguments are stored in Postgres, not sent in one frame, so this cap is
# about sane job size (a phone photo or voice note), not the 64 KiB SSH
# frame. Anything above _INLINE_ARGUMENT_BYTES is left out of the poll
# response and fetched by the worker in bounded pieces (fetch_arguments),
# so every frame stays within worker_stdio_gateway.MAX_FRAME_BYTES.
_MAX_ARGUMENT_BYTES = 16 * 1024 * 1024
_INLINE_ARGUMENT_BYTES = 32 * 1024
_ARGUMENT_CHUNK_CHARS = 32 * 1024
_ARGUMENT_CHUNK_ENCODED_BYTES = 48 * 1024
# Result direction of the same fix: a result too big for one frame (a long
# spoken reply) is uploaded in pieces with upload_result_piece and assembled
# by submit_result. Same overall cap as arguments.
_MAX_RESULT_BYTES = 16 * 1024 * 1024


def _serialize_arguments(arguments: dict) -> str:
    """Canonical ASCII-only form (json.dumps' default ensure_ascii), so one
    character is always one byte and offsets are stable across calls."""
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)


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


def attach_job_arguments(connection_factory, *, job_id: str, tool_id: str, tool_version: str,
                         arguments: dict, expected_arguments_digest: str):
    """Attach the exact immutable arguments needed by a remote worker.

    Deliberately a standalone function, not a method requiring the full
    PostgresWorkerGatewayBackend (and the crypto-dependent WorkerCoordinator
    its constructor requires): this operation is pure database access, no
    cryptographic material of any kind, needed identically by the SSH
    forced-command gateway (whose backend calls this from its own method
    below) and by Core's own dispatch-origination code (Model Router Phase
    D2's worker_dispatch_client.py, which enqueues/attaches jobs directly
    as a database client and never touches worker/ticket/result signing
    keys at all -- those only matter to the gateway process actually
    receiving a worker's SSH connection).

    This is deliberately separate from PR #41's job row. If attachment
    fails, the queued job is simply not remotely dispatchable; it is never
    executed with missing, guessed, or mismatched arguments."""
    if not isinstance(arguments, dict):
        raise WorkerGatewayBackendError("remote job arguments must be an object")
    serialized = _serialize_arguments(arguments)
    if len(serialized.encode("utf-8")) > _MAX_ARGUMENT_BYTES:
        raise WorkerGatewayBackendError("remote job arguments exceed transport bound")
    computed = arguments_digest(tool_id, tool_version, arguments)
    if computed != expected_arguments_digest:
        raise WorkerGatewayBackendError("remote job arguments digest mismatch")
    with connection_factory() as conn, conn.cursor() as cur:
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

    def heartbeat(self, *, worker_id: str, credential_token: str, lease_seconds: int,
                  ollama_snapshot: dict | None = None):
        expires = self.coordinator.authenticate_heartbeat(
            credential_token=credential_token,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            ollama_snapshot=ollama_snapshot,
        )
        return {"lease_expires_at": expires.isoformat()}

    def attach_job_arguments(self, *, job_id: str, tool_id: str, tool_version: str,
                             arguments: dict, expected_arguments_digest: str):
        """Attach the exact immutable arguments needed by a remote worker.

        This is deliberately separate from PR #41's job row. If attachment
        fails, the queued job is simply not remotely dispatchable; it is never
        executed with missing, guessed, or mismatched arguments."""
        return attach_job_arguments(
            self._connection_factory, job_id=job_id, tool_id=tool_id, tool_version=tool_version,
            arguments=arguments, expected_arguments_digest=expected_arguments_digest,
        )

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
        arguments_bytes = len(_serialize_arguments(arguments))
        if arguments_bytes > _INLINE_ARGUMENT_BYTES:
            # Too big for one frame: the worker fetches it with
            # fetch_arguments under this same live lease, then checks the
            # assembled arguments against lease.arguments_digest as usual.
            return {
                "lease": lease_to_wire(lease),
                "arguments": None,
                "arguments_bytes": arguments_bytes,
                "execution_ticket": ticket,
            }
        return {
            "lease": lease_to_wire(lease),
            "arguments": arguments,
            "execution_ticket": ticket,
        }

    def fetch_arguments(self, *, worker_id: str, credential_token: str, lease: dict, offset: int):
        """One bounded piece of a leased job's canonical arguments.

        Only the worker holding the job's live lease (same worker, same
        lease token, not expired, digest unchanged) can read it -- the same
        binding record_ticket()/consume_ticket() require. Read-only: no job,
        ticket, or approval state changes here."""
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        durable_lease = lease_from_wire(lease, expected_worker_id=worker_id)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise WorkerGatewayBackendError("invalid arguments offset")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.arguments
                FROM public.karmo_worker_jobs AS j
                JOIN public.karmo_worker_job_payloads AS p ON p.job_id=j.job_id
                WHERE j.job_id=%s::uuid
                  AND j.state='LEASED'
                  AND j.worker_id=%s
                  AND j.lease_token=%s::uuid
                  AND j.lease_expires_at>NOW()
                  AND j.arguments_digest=%s
                  AND p.arguments_digest=j.arguments_digest
                """,
                (
                    durable_lease.job_id, worker_id, durable_lease.lease_token,
                    durable_lease.arguments_digest,
                ),
            )
            row = cur.fetchone()
        if row is None or not isinstance(row[0], dict):
            raise WorkerGatewayBackendError("no live lease for these job arguments")
        serialized = _serialize_arguments(row[0])
        if offset >= len(serialized):
            raise WorkerGatewayBackendError("invalid arguments offset")
        size = _ARGUMENT_CHUNK_CHARS
        chunk = serialized[offset:offset + size]
        # JSON escaping can grow a piece (e.g. quotes in a question); shrink
        # until it safely fits one response frame.
        while len(json.dumps(chunk)) > _ARGUMENT_CHUNK_ENCODED_BYTES:
            size //= 2
            chunk = serialized[offset:offset + size]
        return {"offset": offset, "total_bytes": len(serialized), "chunk": chunk}

    def authorize_execution(self, *, worker_id: str, credential_token: str,
                            lease: dict, execution_ticket: str):
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        durable_lease = lease_from_wire(lease, expected_worker_id=worker_id)
        self.coordinator.authorize_execution(token=execution_ticket, lease=durable_lease)
        return {"authorized": True}

    def upload_result_piece(self, *, worker_id: str, credential_token: str, lease: dict,
                            execution_ticket: str, offset: int, chunk: str):
        """Stage one piece of a result too big for one frame.

        Only the worker holding the job's live lease, after Core consumed its
        execution ticket, can stage pieces -- the same binding
        submit_authenticated_result() requires. Pieces are untrusted until
        submit_result assembles them and accept_result() checks them against
        the worker's signed envelope. Re-sending an identical piece is a
        no-op, so the worker can retry a whole upload."""
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        durable_lease = lease_from_wire(lease, expected_worker_id=worker_id)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise WorkerGatewayBackendError("invalid result offset")
        if not isinstance(chunk, str) or not chunk or offset + len(chunk) > _MAX_RESULT_BYTES:
            raise WorkerGatewayBackendError("invalid result piece")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_worker_job_result_pieces
                    (job_id, lease_token, offset_chars, chunk)
                SELECT j.job_id, j.lease_token, %s, %s
                FROM public.karmo_worker_jobs AS j
                WHERE j.job_id=%s::uuid
                  AND j.state='LEASED'
                  AND j.worker_id=%s
                  AND j.lease_token=%s::uuid
                  AND j.lease_expires_at>NOW()
                  AND EXISTS (
                      SELECT 1 FROM public.karmo_execution_tickets t
                      WHERE t.ticket_digest=%s AND t.job_id=j.job_id
                        AND t.worker_id=j.worker_id AND t.consumed_at IS NOT NULL
                  )
                ON CONFLICT (job_id, lease_token, offset_chars) DO NOTHING
                RETURNING job_id
                """,
                (
                    offset, chunk, durable_lease.job_id, worker_id,
                    durable_lease.lease_token, _digest_token(execution_ticket),
                ),
            )
            if cur.fetchone() is None:
                # Either no live, authorized lease, or this piece is already
                # staged. Only an identical retry is accepted.
                cur.execute(
                    """
                    SELECT p.chunk
                    FROM public.karmo_worker_job_result_pieces AS p
                    JOIN public.karmo_worker_jobs AS j
                      ON j.job_id=p.job_id AND j.lease_token=p.lease_token
                    WHERE p.job_id=%s::uuid AND p.lease_token=%s::uuid
                      AND p.offset_chars=%s
                      AND j.state='LEASED' AND j.worker_id=%s
                      AND j.lease_expires_at>NOW()
                    """,
                    (durable_lease.job_id, durable_lease.lease_token, offset, worker_id),
                )
                row = cur.fetchone()
                if row is None or row[0] != chunk:
                    raise WorkerGatewayBackendError("no live authorized lease for this result piece")
        return {"offset": offset, "stored_chars": len(chunk)}

    def _assemble_result(self, *, worker_id: str, lease: WorkerLease, result_bytes: int):
        """Join the staged pieces for this exact lease. Must cover
        [0, result_bytes) with no gap or overlap; otherwise refuse."""
        if (
            not isinstance(result_bytes, int) or isinstance(result_bytes, bool)
            or not (1 <= result_bytes <= _MAX_RESULT_BYTES)
        ):
            raise WorkerGatewayBackendError("invalid result size")
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.offset_chars, p.chunk
                FROM public.karmo_worker_job_result_pieces AS p
                JOIN public.karmo_worker_jobs AS j
                  ON j.job_id=p.job_id AND j.lease_token=p.lease_token
                WHERE p.job_id=%s::uuid AND p.lease_token=%s::uuid
                  AND j.state='LEASED' AND j.worker_id=%s
                ORDER BY p.offset_chars
                """,
                (lease.job_id, lease.lease_token, worker_id),
            )
            rows = cur.fetchall()
        pieces = []
        expected = 0
        for offset, chunk in rows:
            if offset != expected:
                raise WorkerGatewayBackendError("result pieces are incomplete")
            pieces.append(chunk)
            expected += len(chunk)
        if expected != result_bytes:
            raise WorkerGatewayBackendError("result pieces are incomplete")
        try:
            return json.loads("".join(pieces))
        except json.JSONDecodeError as exc:
            raise WorkerGatewayBackendError("assembled result is not valid JSON") from exc

    def _discard_result_pieces(self, job_id: str):
        # Best-effort cleanup: the accepted result is already durable in
        # karmo_worker_job_results, and the pieces cascade with the job.
        try:
            with self._connection_factory() as conn, conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.karmo_worker_job_result_pieces WHERE job_id=%s::uuid",
                    (job_id,),
                )
        except Exception:  # noqa: BLE001 -- never fail an accepted result over cleanup
            pass

    def submit_result(self, *, worker_id: str, credential_token: str, lease: dict,
                      execution_ticket: str, result, envelope: dict,
                      success: bool, error: str | None, result_bytes: int | None = None):
        """result_bytes set (and result None) means the result was uploaded
        with upload_result_piece; it is assembled here and then verified by
        accept_result exactly like an inline result."""
        self._authenticate(worker_id=worker_id, credential_token=credential_token)
        durable_lease = lease_from_wire(lease, expected_worker_id=worker_id)
        if result_bytes is not None:
            if result is not None:
                raise WorkerGatewayBackendError("result must be inline or in pieces, not both")
            result = self._assemble_result(
                worker_id=worker_id, lease=durable_lease, result_bytes=result_bytes
            )
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
        if result_bytes is not None:
            self._discard_result_pieces(durable_lease.job_id)
        return {
            "accepted": True,
            "state": "SUCCEEDED" if success else "FAILED",
            "result_digest": digest,
        }
