"""PostgreSQL persistence adapters for KARMO Core.

These adapters accept a DB-API compatible connection factory. The module does
not own credentials or open connections at import time; production wiring must
supply the already-governed database connection.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from .control import ApprovalRecord, ApprovalRequirement, ApprovalState, CapabilityClass
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


class PostgresApprovalStore:
    """Durable approval records; policy/transition authority remains in ApprovalEngine."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def save(self, record: ApprovalRecord):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.core_approval_records (
                    approval_id, requester, tool_id, tool_version, arguments_digest,
                    authority_class, state, approver, authorized_executor,
                    execution_binding, audit_trail, created_at, expires_at, updated_at
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::timestamptz, %s::timestamptz, NOW()
                )
                ON CONFLICT (approval_id) DO UPDATE SET
                    state=EXCLUDED.state,
                    approver=EXCLUDED.approver,
                    authorized_executor=EXCLUDED.authorized_executor,
                    execution_binding=EXCLUDED.execution_binding,
                    audit_trail=EXCLUDED.audit_trail,
                    expires_at=EXCLUDED.expires_at,
                    updated_at=NOW()
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
            created_at=row[11],
            expires_at=row[12],
        )

    def get(self, approval_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT approval_id, requester, tool_id, tool_version, arguments_digest, authority_class, "
                "state, approver, authorized_executor, execution_binding, audit_trail, created_at, expires_at "
                "FROM public.core_approval_records WHERE approval_id=%s::uuid",
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


class PostgresTaskStore:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def save(self, record: TaskRecord):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_tasks (
                    task_id, objective, requester, risk, allowed_capabilities, state, model, tool,
                    inputs, evidence, actions, checkpoints, failures, retries, approvals,
                    verification, rollback, result, next_action, created_at, updated_at
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s::jsonb, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::timestamptz, %s::timestamptz
                )
                ON CONFLICT (task_id) DO UPDATE SET
                    objective=EXCLUDED.objective,
                    requester=EXCLUDED.requester,
                    risk=EXCLUDED.risk,
                    allowed_capabilities=EXCLUDED.allowed_capabilities,
                    state=EXCLUDED.state,
                    model=EXCLUDED.model,
                    tool=EXCLUDED.tool,
                    inputs=EXCLUDED.inputs,
                    evidence=EXCLUDED.evidence,
                    actions=EXCLUDED.actions,
                    checkpoints=EXCLUDED.checkpoints,
                    failures=EXCLUDED.failures,
                    retries=EXCLUDED.retries,
                    approvals=EXCLUDED.approvals,
                    verification=EXCLUDED.verification,
                    rollback=EXCLUDED.rollback,
                    result=EXCLUDED.result,
                    next_action=EXCLUDED.next_action,
                    updated_at=EXCLUDED.updated_at
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

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        return TaskRecord(
            task_id=str(row[0]), objective=row[1], requester=row[2], risk=row[3],
            allowed_capabilities=list(_obj(row[4], [])), state=TaskState(row[5]),
            model=row[6], tool=row[7], inputs=dict(_obj(row[8], {})),
            evidence=list(_obj(row[9], [])), actions=list(_obj(row[10], [])),
            checkpoints=list(_obj(row[11], [])), failures=list(_obj(row[12], [])),
            retries=int(row[13]), approvals=list(_obj(row[14], [])),
            verification=list(_obj(row[15], [])), rollback=_obj(row[16], None),
            result=_obj(row[17], None), next_action=row[18],
            created_at=str(row[19]), updated_at=str(row[20]),
        )

    def get(self, task_id):
        with self._connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, objective, requester, risk, allowed_capabilities, state, model, tool, "
                "inputs, evidence, actions, checkpoints, failures, retries, approvals, verification, "
                "rollback, result, next_action, created_at, updated_at "
                "FROM public.karmo_tasks WHERE task_id=%s::uuid",
                (task_id,),
            )
            return self._decode(cur.fetchone())
