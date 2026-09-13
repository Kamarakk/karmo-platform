from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "worker-runtime" / "app"))

from crypto_boundary import ExecutionTicketAuthority, KeyResolver, ResultAuthenticator, WorkerAuthenticator
from core_service.control import ApprovalEngine, CapabilityClass
from core_service.persistence import PostgresApprovalStore
from core_service.worker_coordination import PostgresWorkerCoordinatorStore, WorkerCoordinationError, WorkerCoordinator

PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")


def _conninfo():
    return f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASSWORD}"


def _connection_factory():
    return psycopg.connect(_conninfo())


def _reachable():
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _reachable(), reason="no isolated Core PostgreSQL available")


@pytest.fixture(scope="module", autouse=True)
def _schema():
    for name in ("001_core_v2_substrate.sql", "002_worker_coordination.sql"):
        path = REPO_ROOT / "core-service" / "core_service" / "migrations" / name
        with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(path.read_text())


@pytest.fixture(autouse=True)
def _clean():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE public.karmo_worker_events, public.karmo_execution_tickets, "
            "public.karmo_worker_jobs, public.karmo_workers CASCADE"
        )
    yield


WORKER_KEY_V1 = b"w" * 32
WORKER_KEY_V2 = b"n" * 32
COORDINATOR_KEY = b"c" * 32


def _keys(key_id):
    return {
        "worker-key-v1": WORKER_KEY_V1,
        "worker-key-v2": WORKER_KEY_V2,
        "coord-key-v1": COORDINATOR_KEY,
    }.get(key_id)


def _crypto(clock=None):
    resolver = KeyResolver(_keys)
    worker_auth = WorkerAuthenticator(resolver, clock=clock or __import__("time").time)
    tickets = ExecutionTicketAuthority(
        resolver, signing_key_id="coord-key-v1", clock=clock or __import__("time").time
    )
    return worker_auth, tickets, ResultAuthenticator(resolver)


def _approve(worker_id="worker-1"):
    engine = ApprovalEngine(store=PostgresApprovalStore(_connection_factory))
    pending = engine.request(
        requester="kamara",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments={"host": "karmo-ai01"},
        authority_class=CapabilityClass.EXTERNAL_ACTION.value,
    )
    engine.approve(pending.approval_id, approver="kamara", authorized_executor=worker_id)
    return pending


def _lease(store, worker_id="worker-1"):
    pending = _approve(worker_id)
    task_id = str(uuid.uuid4())
    job_id = store.enqueue_job(
        idempotency_key=f"lifecycle:{uuid.uuid4()}",
        task_id=task_id,
        approval_id=pending.approval_id,
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments_digest=pending.arguments_digest,
    )
    return store.lease_job(job_id=job_id, worker_id=worker_id, lease_seconds=60)


def _event_types():
    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM public.karmo_worker_events ORDER BY created_at, event_type")
        return [row[0] for row in cur.fetchall()]


def test_registration_and_rotation_are_audited_and_rotation_requires_new_key_and_drain():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store, worker_authenticator=worker_auth,
        ticket_authority=tickets, result_authenticator=results,
    )
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1")

    with pytest.raises(WorkerCoordinationError, match="distinct new_key_id"):
        coordinator.rotate_worker_key(
            credential_token=credential, worker_id="worker-1", new_key_id="worker-key-v1"
        )

    _lease(store)
    with pytest.raises(WorkerCoordinationError, match="leased work"):
        coordinator.rotate_worker_key(
            credential_token=credential, worker_id="worker-1", new_key_id="worker-key-v2"
        )

    assert "WORKER_REGISTERED" in _event_types()


def test_rotation_resets_heartbeat_and_increments_credential_version():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store, worker_authenticator=worker_auth,
        ticket_authority=tickets, result_authenticator=results,
    )
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    old_credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(credential_token=old_credential, worker_id="worker-1")
    coordinator.rotate_worker_key(
        credential_token=old_credential, worker_id="worker-1", new_key_id="worker-key-v2"
    )

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT key_id, credential_version, lease_expires_at FROM public.karmo_workers WHERE worker_id='worker-1'"
        )
        key_id, version, lease_expires_at = cur.fetchone()
    assert key_id == "worker-key-v2"
    assert version == 2
    assert lease_expires_at is None
    assert "WORKER_KEY_ROTATED" in _event_types()

    new_credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v2", ttl_seconds=300)
    coordinator.authenticate_heartbeat(credential_token=new_credential, worker_id="worker-1")


def test_ticket_issue_requires_exact_live_lease_and_transitions_are_audited():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store, worker_authenticator=worker_auth,
        ticket_authority=tickets, result_authenticator=results,
    )
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1")
    lease = _lease(store)
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)
    coordinator.authorize_execution(token=token, lease=lease)

    event_types = _event_types()
    assert "JOB_LEASED" in event_types
    assert "EXECUTION_TICKET_ISSUED" in event_types
    assert "EXECUTION_TICKET_CONSUMED" in event_types


def test_terminal_ticket_cleanup_preserves_nonterminal_recovery_evidence():
    now = [datetime.now(timezone.utc)]
    store = PostgresWorkerCoordinatorStore(_connection_factory, clock=lambda: now[0])

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.karmo_workers(worker_id,key_id,status) VALUES ('worker-1','worker-key-v1','ACTIVE')"
        )
        terminal_job = str(uuid.uuid4())
        recovery_job = str(uuid.uuid4())
        task1, task2 = str(uuid.uuid4()), str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.karmo_worker_jobs(job_id,idempotency_key,task_id,tool_id,tool_version,arguments_digest,state,worker_id) "
            "VALUES (%s::uuid,'terminal',%s::uuid,'x','1','a','SUCCEEDED','worker-1'),"
            "(%s::uuid,'recovery',%s::uuid,'x','1','b','RECOVERY_REQUIRED','worker-1')",
            (terminal_job, task1, recovery_job, task2),
        )
        old_expiry = now[0] - timedelta(days=8)
        cur.execute(
            "INSERT INTO public.karmo_execution_tickets(ticket_digest,job_id,worker_id,issued_at,expires_at) "
            "VALUES ('terminal-ticket',%s::uuid,'worker-1',%s,%s),"
            "('recovery-ticket',%s::uuid,'worker-1',%s,%s)",
            (
                terminal_job, old_expiry - timedelta(minutes=1), old_expiry,
                recovery_job, old_expiry - timedelta(minutes=1), old_expiry,
            ),
        )

    assert store.purge_terminal_tickets(retention_seconds=7 * 24 * 3600) == 1
    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute("SELECT ticket_digest FROM public.karmo_execution_tickets ORDER BY ticket_digest")
        assert [row[0] for row in cur.fetchall()] == ["recovery-ticket"]

    with pytest.raises(WorkerCoordinationError, match="at least 3600"):
        store.purge_terminal_tickets(retention_seconds=60)
