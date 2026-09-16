"""KARMO orchestration task board.

Durable, approval-gated tasks a human-operated Claude Code or ChatGPT
session reads and completes manually. This is deliberately NOT automated
model dispatch: nothing in this module makes an outbound model API call,
holds a model API key, or grants a model standing authority merely
because it can reach a tool. KARMO remains the durable source of truth;
every write goes through the existing CapabilityRegistry + ApprovalEngine
+ CapabilityDispatcher already proven for the KarmoLab tool -- no
separate authority path, no new governance mechanism.

Failure isolation: this domain uses its own least-privilege DB role and
DSN file, never the durable-memory or worker-coordination credentials --
a failure or compromise here cannot reach another domain's data.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable

from .control import CapabilityClass

DEFAULT_DSN_FILE = "/etc/karmo/core/orchestration_postgres.dsn"
MAX_TEXT_CHARS = 4000

CREATE_TASK_TOOL = "karmo.orchestration.create_task"
LIST_TASKS_TOOL = "karmo.orchestration.list_tasks"
CLAIM_TASK_TOOL = "karmo.orchestration.claim_task"
COMPLETE_TASK_TOOL = "karmo.orchestration.complete_task"
TOOL_VERSION = "1.0.0"

VALID_STATUSES = ("OPEN", "CLAIMED", "DONE", "CANCELLED")

_TASK_COLUMNS = (
    "task_id", "objective", "context", "status", "requested_by",
    "claimed_by", "result", "created_at", "claimed_at", "completed_at",
)
_TASK_SELECT_COLUMNS = ", ".join(_TASK_COLUMNS)


class OrchestrationConfigurationError(RuntimeError):
    pass


class TaskNotFoundError(ValueError):
    pass


class TaskStateError(ValueError):
    pass


def _task_dict(row) -> dict:
    d = dict(zip(_TASK_COLUMNS, row))
    d["task_id"] = str(d["task_id"])
    for key in ("created_at", "claimed_at", "completed_at"):
        if d[key] is not None:
            d[key] = d[key].isoformat()
    return d


def _bounded_text(label: str, value: str, *, required: bool) -> str:
    if value is None:
        if required:
            raise ValueError(f"{label} must be non-empty text")
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{label} must be non-empty text")
    text = value.strip()
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"{label} exceeds {MAX_TEXT_CHARS} characters")
    return text


class TaskStore:
    def __init__(self, *, dsn: str, connection_factory: Callable[[], Any] | None = None):
        if not isinstance(dsn, str) or not dsn.strip():
            raise OrchestrationConfigurationError("database DSN must be non-empty")
        self._dsn = dsn.strip()
        self._connection_factory = connection_factory

    def _connection(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        import psycopg

        return psycopg.connect(self._dsn)

    def create_task(self, *, objective: str, context: str | None, requested_by: str) -> dict:
        objective = _bounded_text("objective", objective, required=True)
        context = _bounded_text("context", context, required=False)
        requested_by = _bounded_text("requested_by", requested_by, required=True)
        task_id = uuid.uuid4()
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO public.karmo_orchestration_tasks
                        (task_id, objective, context, status, requested_by)
                    VALUES (%s, %s, %s, 'OPEN', %s)
                    RETURNING {_TASK_SELECT_COLUMNS}
                    """,
                    (task_id, objective, context, requested_by),
                )
                row = cur.fetchone()
        return _task_dict(row)

    def list_tasks(self, *, status: str | None = None, limit: int = 20) -> tuple[dict, ...]:
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connection() as conn:
            with conn.cursor() as cur:
                if status is not None:
                    cur.execute(
                        f"""
                        SELECT {_TASK_SELECT_COLUMNS} FROM public.karmo_orchestration_tasks
                        WHERE status = %s ORDER BY created_at DESC LIMIT %s
                        """,
                        (status, limit),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT {_TASK_SELECT_COLUMNS} FROM public.karmo_orchestration_tasks
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()
        return tuple(_task_dict(row) for row in rows)

    def claim_task(self, *, task_id: str, claimed_by: str) -> dict:
        claimed_by = _bounded_text("claimed_by", claimed_by, required=True)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE public.karmo_orchestration_tasks
                    SET status = 'CLAIMED', claimed_by = %s, claimed_at = NOW()
                    WHERE task_id = %s AND status = 'OPEN'
                    RETURNING {_TASK_SELECT_COLUMNS}
                    """,
                    (claimed_by, task_id),
                )
                row = cur.fetchone()
        if row is None:
            raise TaskStateError(f"task {task_id} is not OPEN or does not exist")
        return _task_dict(row)

    def complete_task(self, *, task_id: str, result: str, completed_by: str) -> dict:
        result = _bounded_text("result", result, required=True)
        completed_by = _bounded_text("completed_by", completed_by, required=True)
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE public.karmo_orchestration_tasks
                    SET status = 'DONE', result = %s, completed_at = NOW()
                    WHERE task_id = %s AND status = 'CLAIMED' AND claimed_by = %s
                    RETURNING {_TASK_SELECT_COLUMNS}
                    """,
                    (result, task_id, completed_by),
                )
                row = cur.fetchone()
        if row is None:
            raise TaskStateError(f"task {task_id} is not CLAIMED by {completed_by!r} or does not exist")
        return _task_dict(row)


def build_default_task_store(dsn_file: str = DEFAULT_DSN_FILE) -> TaskStore:
    path = Path(dsn_file)
    if not path.is_file():
        raise OrchestrationConfigurationError(f"orchestration DSN file not found: {dsn_file}")
    mode = path.stat().st_mode & 0o777
    if mode & 0o007:
        raise OrchestrationConfigurationError("orchestration DSN file must not be accessible to other users")
    dsn = path.read_text(encoding="utf-8").strip()
    if not dsn:
        raise OrchestrationConfigurationError("orchestration DSN file is empty")
    return TaskStore(dsn=dsn)


def _manifest(tool_id: str, capability_class: CapabilityClass, *, description: str,
              read_scope: str, write_scope: str) -> dict:
    return {
        "tool_id": tool_id,
        "domain": "karmo-orchestration",
        "version": TOOL_VERSION,
        "description": description,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "capability_class": capability_class.value,
        "read_scope": read_scope,
        "write_scope": write_scope,
        "external_side_effects": "none",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none; internal PostgreSQL only",
        "secret_requirements": "orchestration.db.credential_ref",
        "invocation_identity": "karmo-core-operator",
        "timeout_seconds": 10,
        "retry_policy": "none",
        "idempotent": capability_class == CapabilityClass.READ,
        "idempotency_mechanism": "pure bounded read" if capability_class == CapabilityClass.READ
        else "not idempotent; each call is a distinct durable state transition",
        "rollback_or_compensation": "not applicable" if capability_class == CapabilityClass.READ
        else "no automated rollback; a task can be re-opened only by a new explicit action, never in place",
        "health_check": "table reachable via configured DSN",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "public.karmo_orchestration_tasks",
        "observability": "structured task row returned; task history durable in the table itself",
        "failure_isolation": "own least-privilege DB role/DSN; a failure here cannot reach any other domain's data",
    }


def create_task_handler(store: TaskStore):
    def handler(arguments: dict) -> dict:
        return store.create_task(
            objective=arguments["objective"],
            context=arguments.get("context"),
            requested_by=arguments["requested_by"],
        )

    return handler


def list_tasks_handler(store: TaskStore):
    def handler(arguments: dict) -> dict:
        tasks = store.list_tasks(status=arguments.get("status"), limit=arguments.get("limit", 20))
        return {"tasks": list(tasks)}

    return handler


def claim_task_handler(store: TaskStore):
    def handler(arguments: dict) -> dict:
        return store.claim_task(task_id=arguments["task_id"], claimed_by=arguments["claimed_by"])

    return handler


def complete_task_handler(store: TaskStore):
    def handler(arguments: dict) -> dict:
        return store.complete_task(
            task_id=arguments["task_id"],
            result=arguments["result"],
            completed_by=arguments["completed_by"],
        )

    return handler


def manifests() -> tuple[dict, ...]:
    return (
        _manifest(
            CREATE_TASK_TOOL, CapabilityClass.REVERSIBLE_WRITE,
            description="Create a durable orchestration task for a human-operated Claude/GPT session to pick up.",
            read_scope="none", write_scope="karmo_orchestration_tasks",
        ),
        _manifest(
            LIST_TASKS_TOOL, CapabilityClass.READ,
            description="List orchestration tasks, optionally filtered by status.",
            read_scope="karmo_orchestration_tasks", write_scope="none",
        ),
        _manifest(
            CLAIM_TASK_TOOL, CapabilityClass.REVERSIBLE_WRITE,
            description="Claim an OPEN orchestration task.",
            read_scope="karmo_orchestration_tasks", write_scope="karmo_orchestration_tasks",
        ),
        _manifest(
            COMPLETE_TASK_TOOL, CapabilityClass.REVERSIBLE_WRITE,
            description="Complete a task this actor already claimed, recording its result.",
            read_scope="karmo_orchestration_tasks", write_scope="karmo_orchestration_tasks",
        ),
    )
