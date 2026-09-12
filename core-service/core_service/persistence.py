"""PostgreSQL persistence adapters for KARMO Core.

These adapters accept a DB-API compatible connection factory. The module does
not own credentials or open connections at import time; production wiring must
supply the already-governed database connection.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from .control import ApprovalRequirement, CapabilityClass
from .registry import RegisteredCapability
from .task_state import TaskRecord, TaskState


class PersistenceError(RuntimeError):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, default=str)


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
        manifest = row[2]
        if isinstance(manifest, str):
            manifest = json.loads(manifest)
        manifest = dict(manifest)
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
        def obj(value, default):
            if value is None:
                return default
            return json.loads(value) if isinstance(value, str) else value
        return TaskRecord(
            task_id=str(row[0]), objective=row[1], requester=row[2], risk=row[3],
            allowed_capabilities=list(obj(row[4], [])), state=TaskState(row[5]),
            model=row[6], tool=row[7], inputs=dict(obj(row[8], {})),
            evidence=list(obj(row[9], [])), actions=list(obj(row[10], [])),
            checkpoints=list(obj(row[11], [])), failures=list(obj(row[12], [])),
            retries=int(row[13]), approvals=list(obj(row[14], [])),
            verification=list(obj(row[15], [])), rollback=obj(row[16], None),
            result=obj(row[17], None), next_action=row[18],
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
