from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "worker-runtime" / "app"))

from crypto_boundary import (  # noqa: E402
    CryptoBoundaryError,
    ExecutionTicketAuthority,
    KeyResolver,
    ResultAuthenticator,
    WorkerAuthenticator,
    token_digest,
)
from core_service.worker_coordination import (  # noqa: E402
    OutboundTransportPolicy,
    PostgresWorkerCoordinatorStore,
    WorkerCoordinationError,
    WorkerCoordinator,
)

import os  # noqa: E402

PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")


def _conninfo():
    return (
        f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
        f"user={PG_USER} password={PG_PASSWORD}"
    )


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


WORKER_KEY = b"w" * 32
COORDINATOR_KEY = b"c" * 32


def _keys(key_id):
    return {"worker-key-v1": WORKER_KEY, "coord-key-v1": COORDINATOR_KEY}.get(key_id)


def _crypto():
    resolver = KeyResolver(_keys)
    return (
        WorkerAuthenticator(resolver),
        ExecutionTicketAuthority(resolver, signing_key_id="coord-key-v1"),
        ResultAuthenticator(resolver),
    )


def _setup_leased_job(store, worker_auth, coordinator, *, arguments_digest="a" * 64):
    store.register_worker(
        worker_id="worker-1",
        key_id="worker-key-v1",
        capabilities=["karmolab.host_health"],
        metadata={"transport": "outbound-only"},
    )
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(
        credential_token=credential,
        worker_id="worker-1",
        lease_seconds=120,
    )
    job_id = store.enqueue_job(
        task_id=str(uuid.uuid4()),
        approval_id=str(uuid.uuid4()),
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments_digest=arguments_digest,
    )
    lease = store.lease_job(job_id=job_id, worker_id="worker-1", lease_seconds=60)
    return credential, job_id, lease


def test_full_worker_identity_ticket_result_lifecycle_is_durable_and_single_use():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store,
        worker_authenticator=worker_auth,
        ticket_authority=tickets,
        result_authenticator=results,
    )
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator)
    assert lease.attempt_count == 1

    token = coordinator.issue_execution_ticket(
        credential_token=credential,
        lease=lease,
        ttl_seconds=30,
    )
    verified = tickets.verify(
        token,
        approval_id=lease.approval_id,
        arguments_digest=lease.arguments_digest,
        executor_identity=lease.worker_id,
        task_id=lease.task_id,
        tool_id=lease.tool_id,
        tool_version=lease.tool_version,
    )
    assert verified["tool_id"] == "karmolab.host_health"
    assert verified["tool_version"] == "1"

    assert coordinator.authorize_execution(token=token, lease=lease) is True
    with pytest.raises(WorkerCoordinationError, match="already consumed"):
        coordinator.authorize_execution(token=token, lease=lease)

    result = {"host": "karmo-ai01", "status": "healthy"}
    envelope = results.sign(
        worker_id="worker-1",
        key_id="worker-key-v1",
        task_id=lease.task_id,
        result=result,
        execution_ticket_digest=token_digest(token),
    )
    digest = coordinator.accept_result(
        execution_ticket=token,
        lease=lease,
        result=result,
        envelope=envelope,
    )
    assert digest == results.result_digest(result)
    assert store.get_job_state(job_id)["state"] == "RESULT_SUBMITTED"

    store.finalize_job(job_id=job_id, success=True)
    durable = store.get_job_state(job_id)
    assert durable["state"] == "SUCCEEDED"
    assert durable["result_digest"] == digest

    restarted_store = PostgresWorkerCoordinatorStore(_connection_factory)
    assert restarted_store.get_job_state(job_id)["state"] == "SUCCEEDED"


def test_result_is_refused_until_ticket_has_been_consumed():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store,
        worker_authenticator=worker_auth,
        ticket_authority=tickets,
        result_authenticator=results,
    )
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator)
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)
    result = {"ok": True}
    envelope = results.sign(
        worker_id=lease.worker_id,
        key_id="worker-key-v1",
        task_id=lease.task_id,
        result=result,
        execution_ticket_digest=token_digest(token),
    )
    with pytest.raises(WorkerCoordinationError, match="was not consumed"):
        coordinator.accept_result(
            execution_ticket=token,
            lease=lease,
            result=result,
            envelope=envelope,
        )
    assert store.get_job_state(job_id)["state"] == "LEASED"


def test_worker_identity_key_mismatch_and_revocation_fail_closed():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store,
        worker_authenticator=worker_auth,
        ticket_authority=tickets,
        result_authenticator=results,
    )
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")

    wrong_key_credential = WorkerAuthenticator(
        KeyResolver(lambda key_id: b"x" * 32 if key_id == "other" else _keys(key_id))
    ).issue(worker_id="worker-1", key_id="other", ttl_seconds=60)
    with pytest.raises(WorkerCoordinationError, match="identity/key mismatch"):
        coordinator.authenticate_heartbeat(
            credential_token=wrong_key_credential,
            worker_id="worker-1",
        )

    store.revoke_worker("worker-1")
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=60)
    with pytest.raises(WorkerCoordinationError):
        coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1")


def test_tampered_ticket_tool_binding_and_result_are_refused():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store,
        worker_authenticator=worker_auth,
        ticket_authority=tickets,
        result_authenticator=results,
    )
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator, arguments_digest="b" * 64)
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)

    with pytest.raises(CryptoBoundaryError):
        tickets.verify(
            token,
            approval_id=lease.approval_id,
            arguments_digest="tampered",
            executor_identity=lease.worker_id,
            task_id=lease.task_id,
            tool_id=lease.tool_id,
            tool_version=lease.tool_version,
        )
    with pytest.raises(CryptoBoundaryError):
        tickets.verify(
            token,
            approval_id=lease.approval_id,
            arguments_digest=lease.arguments_digest,
            executor_identity=lease.worker_id,
            task_id=lease.task_id,
            tool_id="karmolab.other",
            tool_version=lease.tool_version,
        )

    coordinator.authorize_execution(token=token, lease=lease)
    result = {"ok": True}
    envelope = results.sign(
        worker_id="worker-1",
        key_id="worker-key-v1",
        task_id=lease.task_id,
        result=result,
        execution_ticket_digest=token_digest(token),
    )
    with pytest.raises(CryptoBoundaryError):
        coordinator.accept_result(
            execution_ticket=token,
            lease=lease,
            result={"ok": False},
            envelope=envelope,
        )

    other_token_digest = hashlib.sha256(b"different-ticket").hexdigest()
    wrong_ticket_envelope = results.sign(
        worker_id="worker-1",
        key_id="worker-key-v1",
        task_id=lease.task_id,
        result=result,
        execution_ticket_digest=other_token_digest,
    )
    with pytest.raises(CryptoBoundaryError, match="execution-ticket binding mismatch"):
        coordinator.accept_result(
            execution_ticket=token,
            lease=lease,
            result=result,
            envelope=wrong_ticket_envelope,
        )
    assert store.get_job_state(job_id)["state"] == "LEASED"


def test_expired_lease_moves_to_recovery_required_and_never_requeues_automatically():
    class Clock:
        def __init__(self):
            self.now = datetime.now(timezone.utc)

        def __call__(self):
            return self.now

    clock = Clock()
    store = PostgresWorkerCoordinatorStore(_connection_factory, clock=clock)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    store.heartbeat(worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=120)
    job_id = store.enqueue_job(
        task_id=str(uuid.uuid4()),
        approval_id=None,
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments_digest="c" * 64,
    )
    store.lease_job(job_id=job_id, worker_id="worker-1", lease_seconds=5)
    clock.now += timedelta(seconds=6)

    recovered = store.recover_expired_leases()
    assert recovered == [job_id]
    state = store.get_job_state(job_id)
    assert state["state"] == "RECOVERY_REQUIRED"
    assert "unknown execution outcome" in state["last_error"]
    with pytest.raises(WorkerCoordinationError):
        store.lease_job(job_id=job_id, worker_id="worker-1")


def test_outbound_transport_policy_forbids_inbound_or_reachability_authority():
    assert OutboundTransportPolicy().validate() is True
    with pytest.raises(WorkerCoordinationError):
        OutboundTransportPolicy(worker_inbound_listener=True).validate()
    with pytest.raises(WorkerCoordinationError):
        OutboundTransportPolicy(reachability_grants_authority=True).validate()
    with pytest.raises(WorkerCoordinationError):
        OutboundTransportPolicy(require_encrypted_transport=False).validate()
