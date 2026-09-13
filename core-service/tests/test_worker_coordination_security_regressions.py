from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "worker-runtime" / "app"))

from crypto_boundary import (  # noqa: E402
    ExecutionTicketAuthority,
    KeyResolver,
    ResultAuthenticator,
    WorkerAuthenticator,
    token_digest,
)
from core_service.control import ApprovalEngine, CapabilityClass  # noqa: E402
from core_service.persistence import PostgresApprovalStore  # noqa: E402
from core_service.worker_coordination import (  # noqa: E402
    PostgresWorkerCoordinatorStore,
    WorkerCoordinationError,
    WorkerCoordinator,
)


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
    migration_1 = REPO_ROOT / "core-service" / "core_service" / "migrations" / "001_core_v2_substrate.sql"
    migration_2 = REPO_ROOT / "core-service" / "core_service" / "migrations" / "002_worker_coordination.sql"
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(migration_1.read_text())
        cur.execute(migration_2.read_text())


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


def _crypto():
    resolver = KeyResolver(_keys)
    return (
        WorkerAuthenticator(resolver),
        ExecutionTicketAuthority(resolver, signing_key_id="coord-key-v1"),
        ResultAuthenticator(resolver),
    )


def _approved_job(store, *, worker_id="worker-1"):
    arguments = {"host": "karmo-ai01"}
    engine = ApprovalEngine(store=PostgresApprovalStore(_connection_factory))
    pending = engine.request(
        requester="kamara",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments=arguments,
        authority_class=CapabilityClass.EXTERNAL_ACTION.value,
    )
    engine.approve(
        pending.approval_id,
        approver="kamara",
        authorized_executor=worker_id,
    )
    task_id = str(uuid.uuid4())
    job_id = store.enqueue_job(
        idempotency_key=f"{task_id}:host_health",
        task_id=task_id,
        approval_id=pending.approval_id,
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments_digest=pending.arguments_digest,
    )
    lease = store.lease_job(job_id=job_id, worker_id=worker_id, lease_seconds=60)
    return job_id, lease


def _coordinator():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store,
        worker_authenticator=worker_auth,
        ticket_authority=tickets,
        result_authenticator=results,
    )
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    old_credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300
    )
    coordinator.authenticate_heartbeat(
        credential_token=old_credential, worker_id="worker-1", lease_seconds=120
    )
    return store, coordinator, worker_auth, results, old_credential


def test_rotated_old_credential_cannot_issue_new_execution_ticket():
    store, coordinator, worker_auth, _results, old_credential = _coordinator()
    _job_id, lease = _approved_job(store)

    coordinator.rotate_worker_key(
        credential_token=old_credential,
        worker_id="worker-1",
        new_key_id="worker-key-v2",
    )

    with pytest.raises(WorkerCoordinationError, match="key"):
        coordinator.issue_execution_ticket(
            credential_token=old_credential,
            lease=lease,
            ttl_seconds=30,
        )


def test_rotated_old_result_key_cannot_submit_result():
    store, coordinator, _worker_auth, results, old_credential = _coordinator()
    _job_id, lease = _approved_job(store)
    ticket = coordinator.issue_execution_ticket(
        credential_token=old_credential, lease=lease, ttl_seconds=60
    )
    coordinator.authorize_execution(token=ticket, lease=lease)

    coordinator.rotate_worker_key(
        credential_token=old_credential,
        worker_id="worker-1",
        new_key_id="worker-key-v2",
    )

    result = {"ok": True}
    stale_envelope = results.sign(
        worker_id="worker-1",
        key_id="worker-key-v1",
        task_id=lease.task_id,
        result=result,
        execution_ticket_digest=token_digest(ticket),
    )

    with pytest.raises(WorkerCoordinationError, match="key"):
        coordinator.accept_result(
            execution_ticket=ticket,
            lease=lease,
            result=result,
            envelope=stale_envelope,
        )


def test_finalize_fails_closed_if_invocation_ledger_row_is_missing():
    store, coordinator, _worker_auth, results, credential = _coordinator()
    job_id, lease = _approved_job(store)
    ticket = coordinator.issue_execution_ticket(
        credential_token=credential, lease=lease, ttl_seconds=60
    )
    coordinator.authorize_execution(token=ticket, lease=lease)

    result = {"ok": True}
    envelope = results.sign(
        worker_id="worker-1",
        key_id="worker-key-v1",
        task_id=lease.task_id,
        result=result,
        execution_ticket_digest=token_digest(ticket),
    )
    coordinator.accept_result(
        execution_ticket=ticket, lease=lease, result=result, envelope=envelope
    )

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM public.tool_invocation_ledger WHERE idempotency_key=%s",
            (f"worker-job:{job_id}",),
        )

    with pytest.raises(WorkerCoordinationError, match="invocation"):
        store.finalize_job(job_id=job_id, success=True)

    assert store.get_job_state(job_id)["state"] == "RESULT_SUBMITTED"
