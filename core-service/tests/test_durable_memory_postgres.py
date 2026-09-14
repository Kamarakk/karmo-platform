"""Real-PostgreSQL contract test for the Core durable-memory write path."""

from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg is required for durable-memory PostgreSQL tests")

from core_service.durable_memory import (  # noqa: E402
    AGGREGATE_TYPE,
    DESTINATION,
    EVENT_TYPE,
    PAYLOAD_SCHEMA_VERSION,
    DurableMemoryBackend,
)

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
def _memory_tables():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.conversation_memory (
                id BIGSERIAL PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS public.karmo_outbox (
                event_id UUID PRIMARY KEY,
                event_type TEXT NOT NULL,
                aggregate_type TEXT NOT NULL,
                aggregate_id BIGINT NOT NULL,
                destination TEXT NOT NULL,
                payload JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            TRUNCATE public.karmo_outbox, public.conversation_memory RESTART IDENTITY;
            """
        )
    yield


def test_remember_exchange_commits_two_turns_and_one_h01_compatible_outbox_event():
    backend = DurableMemoryBackend(dsn=_conninfo())

    backend.remember_exchange("my worker is Worker02", "I will remember that.")

    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, role, content FROM public.conversation_memory ORDER BY id")
        turns = cur.fetchall()
        cur.execute(
            """
            SELECT event_id, event_type, aggregate_type, aggregate_id,
                   destination, payload, status, attempt_count
            FROM public.karmo_outbox
            """
        )
        event = cur.fetchone()

    assert turns == [
        (1, "user", "my worker is Worker02"),
        (2, "assistant", "I will remember that."),
    ]
    assert str(event[0]) == str(backend._event_id_for_user_id(1))
    assert event[1] == EVENT_TYPE
    assert event[2] == AGGREGATE_TYPE
    assert event[3] == 1
    assert event[4] == DESTINATION
    assert event[5]["schema_version"] == PAYLOAD_SCHEMA_VERSION
    assert event[5]["role"] == "user"
    assert len(event[5]["content_sha256"]) == 64
    assert event[6] == "pending"
    assert event[7] == 0


def test_failed_outbox_insert_rolls_back_both_conversation_turns():
    backend = DurableMemoryBackend(dsn=_conninfo())

    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("ALTER TABLE public.karmo_outbox ADD CONSTRAINT reject_test_destination CHECK (destination <> %s)", (DESTINATION,))

    try:
        with pytest.raises(Exception):
            backend.remember_exchange("must rollback", "must rollback too")

        with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.conversation_memory")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT COUNT(*) FROM public.karmo_outbox")
            assert cur.fetchone()[0] == 0
    finally:
        with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("ALTER TABLE public.karmo_outbox DROP CONSTRAINT IF EXISTS reject_test_destination")
