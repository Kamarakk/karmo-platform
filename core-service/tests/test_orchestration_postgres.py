"""Real-PostgreSQL contract test for the orchestration task board."""

from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg is required for orchestration PostgreSQL tests")

from core_service.orchestration import TaskStateError, TaskStore  # noqa: E402

PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")


def _conninfo():
    return f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASSWORD}"


def _reachable():
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason=f"no reachable PostgreSQL at {PG_HOST}:{PG_PORT}/{PG_DB}",
)


@pytest.fixture(autouse=True)
def _orchestration_table():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.karmo_orchestration_tasks (
                task_id UUID PRIMARY KEY,
                objective TEXT NOT NULL,
                context TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLAIMED','DONE','CANCELLED')),
                requested_by TEXT NOT NULL,
                claimed_by TEXT,
                result TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                claimed_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            );
            TRUNCATE public.karmo_orchestration_tasks;
            """
        )
    yield


def test_create_task_persists_open_task():
    store = TaskStore(dsn=_conninfo())

    task = store.create_task(objective="reconcile PR #26", context="predates main", requested_by="kamara")

    assert task["status"] == "OPEN"
    assert task["objective"] == "reconcile PR #26"
    assert task["context"] == "predates main"
    assert task["requested_by"] == "kamara"
    assert task["claimed_by"] is None
    assert task["created_at"] is not None


def test_full_lifecycle_create_claim_complete():
    store = TaskStore(dsn=_conninfo())
    task = store.create_task(objective="write a report", context=None, requested_by="kamara")

    claimed = store.claim_task(task_id=task["task_id"], claimed_by="claude-code")
    assert claimed["status"] == "CLAIMED"
    assert claimed["claimed_by"] == "claude-code"
    assert claimed["claimed_at"] is not None

    done = store.complete_task(task_id=task["task_id"], result="report written", completed_by="claude-code")
    assert done["status"] == "DONE"
    assert done["result"] == "report written"
    assert done["completed_at"] is not None


def test_claim_is_atomic_second_claim_refused():
    store = TaskStore(dsn=_conninfo())
    task = store.create_task(objective="one at a time", context=None, requested_by="kamara")
    store.claim_task(task_id=task["task_id"], claimed_by="claude-code")

    with pytest.raises(TaskStateError):
        store.claim_task(task_id=task["task_id"], claimed_by="chatgpt")


def test_complete_refuses_wrong_claimant():
    store = TaskStore(dsn=_conninfo())
    task = store.create_task(objective="mine, not yours", context=None, requested_by="kamara")
    store.claim_task(task_id=task["task_id"], claimed_by="claude-code")

    with pytest.raises(TaskStateError):
        store.complete_task(task_id=task["task_id"], result="sneaky", completed_by="chatgpt")


def test_list_tasks_filters_by_status_and_orders_newest_first():
    store = TaskStore(dsn=_conninfo())
    first = store.create_task(objective="first", context=None, requested_by="kamara")
    second = store.create_task(objective="second", context=None, requested_by="kamara")
    store.claim_task(task_id=second["task_id"], claimed_by="claude-code")

    open_tasks = store.list_tasks(status="OPEN")
    claimed_tasks = store.list_tasks(status="CLAIMED")
    all_tasks = store.list_tasks()

    assert [t["task_id"] for t in open_tasks] == [first["task_id"]]
    assert [t["task_id"] for t in claimed_tasks] == [second["task_id"]]
    assert [t["task_id"] for t in all_tasks] == [second["task_id"], first["task_id"]]
