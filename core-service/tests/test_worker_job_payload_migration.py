from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

from core_service.control import arguments_digest
from core_service.worker_gateway_backend import PostgresWorkerGatewayBackend


REPO_ROOT = Path(__file__).resolve().parents[2]
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


def _apply_worker_schema():
    migrations = [
        "001_core_v2_substrate.sql",
        "002_worker_coordination.sql",
        "003_worker_job_payloads.sql",
    ]
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        for migration in migrations:
            cur.execute((REPO_ROOT / "core-service" / "core_service" / "migrations" / migration).read_text())


def test_payload_migration_and_attachment_preserve_exact_arguments_digest():
    _apply_worker_schema()
    job_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    tool_id = "karmolab.host_health"
    tool_version = "1"
    arguments = {"host": "karmo-ai01"}
    digest = arguments_digest(tool_id, tool_version, arguments)

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.karmo_worker_jobs
                (job_id, idempotency_key, task_id, tool_id, tool_version, arguments_digest, state)
            VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, 'QUEUED')
            """,
            (job_id, f"payload-test:{job_id}", task_id, tool_id, tool_version, digest),
        )

    backend = PostgresWorkerGatewayBackend(
        store=object(),
        coordinator=object(),
        connection_factory=_connection_factory,
    )
    assert backend.attach_job_arguments(
        job_id=job_id,
        tool_id=tool_id,
        tool_version=tool_version,
        arguments=arguments,
        expected_arguments_digest=digest,
    ) == digest

    with _connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT arguments, arguments_digest FROM public.karmo_worker_job_payloads "
            "WHERE job_id=%s::uuid",
            (job_id,),
        )
        stored_arguments, stored_digest = cur.fetchone()
        assert stored_arguments == arguments
        assert stored_digest == digest
        cur.execute("DELETE FROM public.karmo_worker_jobs WHERE job_id=%s::uuid", (job_id,))


def test_payload_attachment_refuses_digest_mismatch_before_database_write():
    _apply_worker_schema()
    backend = PostgresWorkerGatewayBackend(
        store=object(),
        coordinator=object(),
        connection_factory=_connection_factory,
    )
    with pytest.raises(Exception, match="digest mismatch"):
        backend.attach_job_arguments(
            job_id=str(uuid.uuid4()),
            tool_id="karmolab.host_health",
            tool_version="1",
            arguments={"host": "karmo-ai01"},
            expected_arguments_digest="f" * 64,
        )
