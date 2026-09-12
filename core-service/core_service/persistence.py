"""PostgreSQL persistence adapters for KARMO Core.

These adapters accept a DB-API compatible connection factory. The module does
not own credentials or open connections at import time; production wiring must
supply the already-governed database connection.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .control import (
    ApprovalRecord,
    ApprovalRequirement,
    ApprovalState,
    CapabilityClass,
    CoreControlError,
    arguments_digest,
)
from .registry import RegisteredCapability
from .task_state import TaskRecord, TaskState


class PersistenceError(RuntimeError):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, default=str)


def _obj(value, default):
    if value is None:
        return default
    return json.loads(value) if isinstance(value, str) else value


class PostgresCapabilityStore:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def put(self, record: RegisteredCapability):
        manifest = dict(record.manifest)
        manifest["capability_class"] = record.capability_class.value
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.tool_registry
                    (tool_id, version, manifest, computed_approval_requirement, deprecated, superseded_by)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    record.tool_id,
                    record.version,
                    _json(manifest),
                    record.computed_approval_requirement.value,
                    record.deprecated,
                    record.superseded_by,
                ),
            )

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        manifest = dict(_obj(row[2], {}))
        manifest["capability_class"] = CapabilityClass(manifest["capability_class"])
        return RegisteredCapability(
            manifest=manifest,
            computed_approval_requirement=ApprovalRequirement(row[3]),
            deprecated=bool(row[4]),
            superseded_by=row[5],
        )

    def get(self, tool_id, version):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tool_id, version, manifest, computed_approval_requirement, deprecated, superseded_by "
                "FROM public.tool_registry WHERE tool_id=%s AND version=%s",
                (tool_id, version),
            )
            return self._decode(cur.fetchone())

    def list(self, tool_id=None):
        with self._connection_factory() as conn, conn.cursor() as cur:
            if tool_id is None:
                cur.execute(
                    "SELECT tool_id, version, manifest, computed_approval_requirement, deprecated, superseded_by "
                    "FROM public.tool_registry ORDER BY tool_id, version"
                )
            else:
                cur.execute(
                    "SELECT tool_id, version, manifest, computed_approval_requirement, deprecated, superseded_by "
                    "FROM public.tool_registry WHERE tool_id=%s ORDER BY version",
                    (tool_id,),
                )
            return [self._decode(row) for row in cur.fetchall()]


_APPROVAL_COLUMNS = (
    "approval_id, requester, tool_id, tool_version, arguments_digest, authority_class, "
    "state, approver, authorized_executor, execution_binding, audit_trail, version, "
    "created_at, expires_at"
)


class PostgresApprovalStore:
    """Durable approval records; policy/transition authority remains in ApprovalEngine.

    ``save`` is compare-and-swap: ``expected_version=None`` means "must not
    already exist" (first save of a new approval); an int means the write is
    only applied if the row's current ``version`` still matches, so a stale
    writer -- one that read an older state and would otherwise silently
    overwrite a newer one -- fails closed with CoreControlError instead.
    """

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def save(self, record: ApprovalRecord, *, expected_version=None):
        with self._connection_factory() as conn, conn.cursor() as cur:
            if expected_version is None:
                cur.execute(
                    """
                    INSERT INTO public.core_approval_records (
                        approval_id, requester, tool_id, tool_version, arguments_digest,
                        authority_class, state, approver, authorized_executor,
                        execution_binding, audit_trail, version, created_at, expires_at, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, 1, %s::timestamptz, %s::timestamptz, NOW()
                    )
                    ON CONFLICT (approval_id) DO NOTHING
                    RETURNING version
                    """,
                    (
                        record.approval_id,
                        record.requester,
                        record.tool_id,
                        record.tool_version,
                        record.arguments_digest,
                        record.authority_class,
                        record.state.value,
                        record.approver,
                        record.authorized_executor,
                        record.execution_binding,
                        _json(record.audit_trail),
                        record.created_at,
                        record.expires_at,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise CoreControlError(f"approval already exists: {record.approval_id}")
                return int(row[0])

            cur.execute(
                """
                UPDATE public.core_approval_records SET
                    state=%s, approver=%s, authorized_executor=%s,
                    execution_binding=%s, audit_trail=%s::jsonb, version=version+1,
                    expires_at=%s::timestamptz, updated_at=NOW()
                WHERE approval_id=%s::uuid AND version=%s
                RETURNING version
                """,
                (
                    record.state.value,
                    record.approver,
                    record.authorized_executor,
                    record.execution_binding,
                    _json(record.audit_trail),
                    record.expires_at,
                    record.approval_id,
                    expected_version,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise CoreControlError(
                    f"approval version conflict for {record.approval_id}: expected {expected_version}"
                )
            return int(row[0])

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        return ApprovalRecord(
            approval_id=str(row[0]),
            requester=row[1],
            tool_id=row[2],
            tool_version=row[3],
            arguments_digest=row[4],
            authority_class=row[5],
            state=ApprovalState(row[6]),
            approver=row[7],
            authorized_executor=row[8],
            execution_binding=row[9],
            audit_trail=list(_obj(row[10], [])),
            version=int(row[11]),
            created_at=row[12],
            expires_at=row[13],
        )

    def get(self, approval_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {_APPROVAL_COLUMNS} FROM public.core_approval_records WHERE approval_id=%s::uuid",
                (approval_id,),
            )
            return self._decode(cur.fetchone())


@dataclass(frozen=True)
class InvocationRecord:
    invocation_id: str
    idempotency_key: str
    task_id: str | None
    tool_id: str
    tool_version: str
    requester: str
    model_identity: str | None
    executor_identity: str | None
    arguments_digest: str
    authority_decision: str
    approval_id: str | None
    status: str
    result_digest: str | None = None
    evidence_digest: str | None = None
    verification_state: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class PostgresInvocationLedger:
    """Append-first invocation ledger with idempotency-key replay protection."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def begin(self, *, idempotency_key, task_id, tool_id, tool_version, requester,
              model_identity, executor_identity, arguments_digest, authority_decision,
              approval_id=None):
        invocation_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
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
                    invocation_id, idempotency_key, task_id, tool_id, tool_version, requester,
                    model_identity, executor_identity, arguments_digest, authority_decision, approval_id,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise PersistenceError(f"duplicate invocation idempotency key: {idempotency_key}")
        return invocation_id

    def complete(self, invocation_id, *, status, result_digest=None, evidence_digest=None,
                 verification_state=None):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.tool_invocation_ledger
                SET status=%s, result_digest=%s, evidence_digest=%s,
                    verification_state=%s, completed_at=NOW()
                WHERE invocation_id=%s::uuid AND completed_at IS NULL
                """,
                (status, result_digest, evidence_digest, verification_state, invocation_id),
            )
            if cur.rowcount != 1:
                raise PersistenceError("invocation is missing or already terminal")

    def get_by_idempotency_key(self, idempotency_key):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT invocation_id, idempotency_key, task_id, tool_id, tool_version, requester, "
                "model_identity, executor_identity, arguments_digest, authority_decision, approval_id, status, "
                "result_digest, evidence_digest, verification_state, created_at, completed_at "
                "FROM public.tool_invocation_ledger WHERE idempotency_key=%s",
                (idempotency_key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return InvocationRecord(
                invocation_id=str(row[0]), idempotency_key=row[1],
                task_id=str(row[2]) if row[2] is not None else None,
                tool_id=row[3], tool_version=row[4], requester=row[5],
                model_identity=row[6], executor_identity=row[7], arguments_digest=row[8],
                authority_decision=row[9], approval_id=str(row[10]) if row[10] is not None else None,
                status=row[11], result_digest=row[12], evidence_digest=row[13],
                verification_state=row[14], created_at=row[15], completed_at=row[16],
            )

    def list_unfinished(self):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT invocation_id, idempotency_key, task_id, tool_id, tool_version, requester, "
                "model_identity, executor_identity, arguments_digest, authority_decision, approval_id, status, "
                "result_digest, evidence_digest, verification_state, created_at, completed_at "
                "FROM public.tool_invocation_ledger WHERE completed_at IS NULL ORDER BY created_at"
            )
            return [
                InvocationRecord(
                    invocation_id=str(row[0]), idempotency_key=row[1],
                    task_id=str(row[2]) if row[2] is not None else None,
                    tool_id=row[3], tool_version=row[4], requester=row[5],
                    model_identity=row[6], executor_identity=row[7], arguments_digest=row[8],
                    authority_decision=row[9], approval_id=str(row[10]) if row[10] is not None else None,
                    status=row[11], result_digest=row[12], evidence_digest=row[13],
                    verification_state=row[14], created_at=row[15], completed_at=row[16],
                ) for row in cur.fetchall()
            ]


@dataclass(frozen=True)
class TaskEventRecord:
    event_id: str
    event_key: str
    task_id: str
    event_type: str
    actor: str
    payload: dict
    created_at: datetime | None = None


class PostgresTaskStore:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def save(self, record: TaskRecord, *, expected_version=None):
        with self._connection_factory() as conn, conn.cursor() as cur:
            if expected_version is None:
                cur.execute(
                    """
                    INSERT INTO public.karmo_tasks (
                        task_id, objective, requester, risk, allowed_capabilities, state, state_version,
                        model, tool, inputs, evidence, actions, checkpoints, failures, retries, approvals,
                        verification, rollback, result, next_action, created_at, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s::jsonb, %s, 1,
                        %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb,
                        %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::timestamptz, %s::timestamptz
                    )
                    ON CONFLICT (task_id) DO NOTHING
                    RETURNING state_version
                    """,
                    (
                        record.task_id, record.objective, record.requester, record.risk,
                        _json(record.allowed_capabilities), record.state.value, record.model, record.tool,
                        _json(record.inputs), _json(record.evidence), _json(record.actions),
                        _json(record.checkpoints), _json(record.failures), record.retries,
                        _json(record.approvals), _json(record.verification), _json(record.rollback),
                        _json(record.result), record.next_action, record.created_at, record.updated_at,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise PersistenceError("task already exists; expected_version is required for update")
                record.state_version = int(row[0])
                return record.state_version

            cur.execute(
                """
                UPDATE public.karmo_tasks SET
                    objective=%s, requester=%s, risk=%s, allowed_capabilities=%s::jsonb,
                    state=%s, state_version=state_version+1, model=%s, tool=%s,
                    inputs=%s::jsonb, evidence=%s::jsonb, actions=%s::jsonb,
                    checkpoints=%s::jsonb, failures=%s::jsonb, retries=%s, approvals=%s::jsonb,
                    verification=%s::jsonb, rollback=%s::jsonb, result=%s::jsonb,
                    next_action=%s, updated_at=%s::timestamptz
                WHERE task_id=%s::uuid AND state_version=%s
                RETURNING state_version
                """,
                (
                    record.objective, record.requester, record.risk, _json(record.allowed_capabilities),
                    record.state.value, record.model, record.tool, _json(record.inputs),
                    _json(record.evidence), _json(record.actions), _json(record.checkpoints),
                    _json(record.failures), record.retries, _json(record.approvals),
                    _json(record.verification), _json(record.rollback), _json(record.result),
                    record.next_action, record.updated_at, record.task_id, expected_version,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise PersistenceError(
                    f"task version conflict for {record.task_id}: expected {expected_version}"
                )
            record.state_version = int(row[0])
            return record.state_version

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        return TaskRecord(
            task_id=str(row[0]), objective=row[1], requester=row[2], risk=row[3],
            allowed_capabilities=list(_obj(row[4], [])), state=TaskState(row[5]),
            state_version=int(row[6]), model=row[7], tool=row[8], inputs=dict(_obj(row[9], {})),
            evidence=list(_obj(row[10], [])), actions=list(_obj(row[11], [])),
            checkpoints=list(_obj(row[12], [])), failures=list(_obj(row[13], [])),
            retries=int(row[14]), approvals=list(_obj(row[15], [])),
            verification=list(_obj(row[16], [])), rollback=_obj(row[17], None),
            result=_obj(row[18], None), next_action=row[19],
            created_at=str(row[20]), updated_at=str(row[21]),
        )

    @staticmethod
    def _select_columns():
        return (
            "task_id, objective, requester, risk, allowed_capabilities, state, state_version, model, tool, "
            "inputs, evidence, actions, checkpoints, failures, retries, approvals, verification, "
            "rollback, result, next_action, created_at, updated_at"
        )

    def get(self, task_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._select_columns()} FROM public.karmo_tasks WHERE task_id=%s::uuid",
                (task_id,),
            )
            return self._decode(cur.fetchone())

    def list_by_states(self, states):
        values = [TaskState(value).value for value in states]
        if not values:
            return []
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._select_columns()} FROM public.karmo_tasks WHERE state = ANY(%s) ORDER BY updated_at",
                (values,),
            )
            return [self._decode(row) for row in cur.fetchall()]

    def append_event(self, *, event_key, task_id, event_type, actor, payload=None):
        event_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_task_events
                    (event_id, event_key, task_id, event_type, actor, payload)
                VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s::jsonb)
                ON CONFLICT (event_key) DO NOTHING
                RETURNING event_id
                """,
                (event_id, event_key, task_id, event_type, actor, _json(payload or {})),
            )
            row = cur.fetchone()
            if row is None:
                raise PersistenceError(f"duplicate task event key: {event_key}")
        return event_id

    def list_events(self, task_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT event_id, event_key, task_id, event_type, actor, payload, created_at "
                "FROM public.karmo_task_events WHERE task_id=%s::uuid ORDER BY created_at, event_id",
                (task_id,),
            )
            return [
                TaskEventRecord(
                    event_id=str(row[0]), event_key=row[1], task_id=str(row[2]),
                    event_type=row[3], actor=row[4], payload=dict(_obj(row[5], {})),
                    created_at=row[6],
                ) for row in cur.fetchall()
            ]


@dataclass(frozen=True)
class ExecutionClaim:
    invocation_id: str
    approval_id: str
    idempotency_key: str


class PostgresExecutionCoordinator:
    """Atomically bind an approval to one invocation before a side effect.

    The database transaction can make authority consumption + invocation start
    atomic. It cannot make an external side effect exactly-once. If KARMO dies
    after the handler acts but before finish(), the STARTED invocation is left
    unfinished for reconciliation and MUST NOT be silently replayed.
    """

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def claim(self, *, approval_id, idempotency_key, task_id, tool_id, tool_version,
              requester, model_identity, executor_identity, arguments, authority_decision):
        if not idempotency_key:
            raise PersistenceError("idempotency_key is required for durable execution claim")
        now = datetime.now(timezone.utc)
        invocation_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {_APPROVAL_COLUMNS} FROM public.core_approval_records "
                "WHERE approval_id=%s::uuid FOR UPDATE",
                (approval_id,),
            )
            record = PostgresApprovalStore._decode(cur.fetchone())
            if record is None:
                raise CoreControlError(f"no such approval: {approval_id}")
            if record.state != ApprovalState.APPROVED:
                raise CoreControlError(f"cannot claim from {record.state.value}")
            if now >= record.expires_at:
                record.transition(ApprovalState.EXPIRED, "system", "ttl elapsed before claim", now)
                cur.execute(
                    "UPDATE public.core_approval_records SET state=%s, audit_trail=%s::jsonb, "
                    "version=version+1, updated_at=NOW() WHERE approval_id=%s::uuid",
                    (record.state.value, _json(record.audit_trail), approval_id),
                )
                raise CoreControlError("approval expired before execution claim")
            if executor_identity != record.authorized_executor:
                raise CoreControlError("executor identity mismatch")
            digest = arguments_digest(tool_id, tool_version, arguments)
            if tool_id != record.tool_id or tool_version != record.tool_version or digest != record.arguments_digest:
                raise CoreControlError("tool/argument mismatch")

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
                    invocation_id, idempotency_key, task_id, tool_id, tool_version, requester,
                    model_identity, executor_identity, digest, authority_decision, approval_id,
                ),
            )
            if cur.fetchone() is None:
                raise PersistenceError(f"duplicate invocation idempotency key: {idempotency_key}")

            record.execution_binding = invocation_id
            record.transition(ApprovalState.CLAIMED, "system", "execution authority claimed", now)
            cur.execute(
                "UPDATE public.core_approval_records SET state=%s, execution_binding=%s, "
                "audit_trail=%s::jsonb, version=version+1, updated_at=NOW() WHERE approval_id=%s::uuid",
                (record.state.value, invocation_id, _json(record.audit_trail), approval_id),
            )
        return ExecutionClaim(invocation_id, approval_id, idempotency_key)

    def finish(self, claim: ExecutionClaim, *, status, result_digest=None,
               evidence_digest=None, verification_state=None):
        terminal_approval_state = ApprovalState.EXECUTED if status == "EXECUTED" else ApprovalState.FAILED
        now = datetime.now(timezone.utc)
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT state, execution_binding, audit_trail FROM public.core_approval_records "
                "WHERE approval_id=%s::uuid FOR UPDATE",
                (claim.approval_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise PersistenceError("claimed approval disappeared")
            if ApprovalState(row[0]) != ApprovalState.CLAIMED or row[1] != claim.invocation_id:
                raise PersistenceError("approval claim binding mismatch or already terminal")
            audit_trail = list(_obj(row[2], []))
            audit_trail.append({
                "timestamp": now.isoformat(),
                "from_state": ApprovalState.CLAIMED.value,
                "to_state": terminal_approval_state.value,
                "actor": "system",
                "note": f"invocation {status.lower()}",
            })
            cur.execute(
                """
                UPDATE public.tool_invocation_ledger
                SET status=%s, result_digest=%s, evidence_digest=%s,
                    verification_state=%s, completed_at=NOW()
                WHERE invocation_id=%s::uuid AND completed_at IS NULL AND approval_id=%s::uuid
                """,
                (
                    status, result_digest, evidence_digest, verification_state,
                    claim.invocation_id, claim.approval_id,
                ),
            )
            if cur.rowcount != 1:
                raise PersistenceError("invocation is missing or already terminal")
            cur.execute(
                "UPDATE public.core_approval_records SET state=%s, audit_trail=%s::jsonb, "
                "version=version+1, updated_at=NOW() WHERE approval_id=%s::uuid",
                (terminal_approval_state.value, _json(audit_trail), claim.approval_id),
            )
