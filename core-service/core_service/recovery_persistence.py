"""Atomic PostgreSQL persistence for restart recovery.

This wrapper exists because recovery state and its audit event must either both
commit or both roll back. It reuses PostgresTaskStore decoding/listing semantics
and adds a transaction boundary for the recovery write itself.
"""

from __future__ import annotations

import uuid

from .persistence import PersistenceError, PostgresTaskStore, _json


class PostgresRecoveryStore:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory
        self._tasks = PostgresTaskStore(connection_factory)

    def get(self, task_id):
        return self._tasks.get(task_id)

    def list_by_states(self, states):
        return self._tasks.list_by_states(states)

    def save_with_event(self, record, *, expected_version, event_key, event_type, actor, payload):
        """CAS-update one task and append its recovery event in one transaction."""
        event_id = str(uuid.uuid4())
        with self._connection_factory() as conn, conn.cursor() as cur:
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
            next_version = int(row[0])
            cur.execute(
                """
                INSERT INTO public.karmo_task_events
                    (event_id, event_key, task_id, event_type, actor, payload)
                VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s::jsonb)
                ON CONFLICT (event_key) DO NOTHING
                RETURNING event_id
                """,
                (event_id, event_key, record.task_id, event_type, actor, _json(payload or {})),
            )
            if cur.fetchone() is None:
                raise PersistenceError(f"duplicate task event key: {event_key}")
            record.state_version = next_version
            return next_version
