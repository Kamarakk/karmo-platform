from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from core_service.worker_dispatch_client import (
    NullWorkerDispatchClient,
    WorkerDispatchClientError,
    build_default_worker_dispatch_client,
)

psycopg = pytest.importorskip("psycopg")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "worker-runtime" / "app"))
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
    migrations_dir = REPO_ROOT / "core-service" / "core_service" / "migrations"
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        for name in (
            "001_core_v2_substrate.sql", "002_worker_coordination.sql",
            "003_worker_job_payloads.sql", "005_worker_ollama_health.sql",
            "007_worker_job_results.sql", "008_worker_job_lease_duration.sql",
        ):
            cur.execute((migrations_dir / name).read_text())


@pytest.fixture(autouse=True)
def _clean():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE public.karmo_worker_events, public.karmo_execution_tickets, "
            "public.karmo_worker_jobs, public.karmo_workers CASCADE"
        )
    yield


def test_null_client_is_unavailable_and_refuses_dispatch():
    client = NullWorkerDispatchClient()
    assert client.available is False
    with pytest.raises(WorkerDispatchClientError):
        client.dispatch(
            worker_id="KARMO-WORKER01", tool_id="model_chat_tools", tool_version="1.0.0",
            arguments={}, total_deadline_seconds=10.0,
        )


def test_build_default_degrades_to_null_when_dsn_file_missing(tmp_path):
    client = build_default_worker_dispatch_client(dsn_file=str(tmp_path / "does-not-exist.dsn"))
    assert isinstance(client, NullWorkerDispatchClient)
    assert client.available is False


def test_build_default_rejects_a_world_readable_dsn_file(tmp_path):
    dsn_file = tmp_path / "worker-dispatch.dsn"
    dsn_file.write_text("postgresql://example/db\n")
    dsn_file.chmod(0o644)
    with pytest.raises(WorkerDispatchClientError, match="must not be accessible to other users"):
        build_default_worker_dispatch_client(dsn_file=str(dsn_file))


def test_postgres_dispatch_client_round_trips_a_real_job_against_the_real_pipeline():
    """Proves the lightweight, crypto-free client is functionally
    equivalent to the full PostgresWorkerGatewayBackend for exactly the
    operations dispatch_and_wait() needs -- enqueue, attach arguments,
    poll to a terminal state, read back the real result content."""
    from core_service.worker_coordination import PostgresWorkerCoordinatorStore, WorkerCoordinator
    from core_service.worker_gateway_backend import PostgresWorkerGatewayBackend
    from crypto_boundary import ExecutionTicketAuthority, KeyResolver, ResultAuthenticator, WorkerAuthenticator, token_digest

    def _keys(key_id):
        return b"k" * 32

    resolver = KeyResolver(_keys)
    worker_auth = WorkerAuthenticator(resolver)
    tickets = ExecutionTicketAuthority(resolver, signing_key_id="coord-key-v1")
    results = ResultAuthenticator(resolver)

    store = PostgresWorkerCoordinatorStore(_connection_factory)
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    gateway_backend = PostgresWorkerGatewayBackend(store=store, coordinator=coordinator, connection_factory=_connection_factory)

    store.register_worker(worker_id="worker-1", key_id="worker-key-v1", capabilities=["model_chat_tools"])
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1", lease_seconds=120)

    from core_service.worker_dispatch_client import PostgresWorkerDispatchClient
    dispatch_client = PostgresWorkerDispatchClient(connection_factory=_connection_factory)

    real_answer = {"content": "hi there", "tool_calls": None}
    worker_acted = {"done": False}

    def simulate_worker(_seconds):
        if not worker_acted["done"]:
            worker_acted["done"] = True
            polled = gateway_backend.poll(worker_id="worker-1", credential_token=credential, capabilities=["model_chat_tools"])
            assert polled is not None
            gateway_backend.authorize_execution(
                worker_id="worker-1", credential_token=credential,
                lease=polled["lease"], execution_ticket=polled["execution_ticket"],
            )
            envelope = results.sign(
                worker_id="worker-1", key_id="worker-key-v1", task_id=polled["lease"]["task_id"],
                result=real_answer, execution_ticket_digest=token_digest(polled["execution_ticket"]),
            )
            gateway_backend.submit_result(
                worker_id="worker-1", credential_token=credential,
                lease=polled["lease"], execution_ticket=polled["execution_ticket"],
                result=real_answer, envelope=envelope, success=True, error=None,
            )
        import time as _time
        _time.sleep(0.02)

    outcome = dispatch_client.dispatch(
        worker_id="worker-1", tool_id="model_chat_tools", tool_version="1.0.0",
        arguments={"model": "qwen3:8b", "messages": [{"role": "user", "content": "hi"}]},
        total_deadline_seconds=10.0, poll_interval_seconds=0.02, sleep=simulate_worker,
    )

    assert outcome.outcome == "SUCCEEDED"
    assert outcome.result == real_answer
