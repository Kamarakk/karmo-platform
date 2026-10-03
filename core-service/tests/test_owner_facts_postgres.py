"""Real-PostgreSQL tests for Kamara's remembered facts (migration 013) and
the recent-turn time window."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg is required for durable-memory PostgreSQL tests")

from core_service.durable_memory import DurableMemoryBackend  # noqa: E402

PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")
MIGRATION = Path(__file__).resolve().parents[1] / "core_service" / "migrations" / "013_owner_facts.sql"


def _conninfo():
    return f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASSWORD}"


def _reachable():
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _reachable(), reason=f"no reachable PostgreSQL at {PG_HOST}:{PG_PORT}/{PG_DB}")


@pytest.fixture(autouse=True)
def _tables():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS public.karmo_owner_facts")
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
        cur.execute(MIGRATION.read_text(encoding="utf-8"))  # idempotent
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.conversation_memory (
                id BIGSERIAL PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            TRUNCATE public.conversation_memory RESTART IDENTITY;
            """
        )
    yield


def test_remember_list_and_forget_facts():
    backend = DurableMemoryBackend(dsn=_conninfo())

    first = backend.remember_fact("  Kith's soccer is on Tuesdays ")
    second = backend.remember_fact("The tent light runs 14 hours a day")

    assert backend.owner_facts() == ((first, "Kith's soccer is on Tuesdays"), (second, "The tent light runs 14 hours a day"))
    assert backend.forget_fact(first) is True
    assert backend.forget_fact(first) is False
    assert backend.owner_facts() == ((second, "The tent light runs 14 hours a day"),)


def test_oversized_fact_is_rejected_before_the_database():
    backend = DurableMemoryBackend(dsn=_conninfo())

    with pytest.raises(ValueError):
        backend.remember_fact("x" * 501)
    assert backend.owner_facts() == ()


def test_recent_turns_skip_an_earlier_conversation():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.conversation_memory (role, content, created_at) VALUES "
            "('user', 'yesterday question', NOW() - INTERVAL '1 day'), "
            "('assistant', 'yesterday answer', NOW() - INTERVAL '1 day'), "
            "('user', 'just now', NOW()), ('assistant', 'answer now', NOW())"
        )

    turns = DurableMemoryBackend(dsn=_conninfo()).recent_turns()

    assert turns == (("user", "just now"), ("assistant", "answer now"))
