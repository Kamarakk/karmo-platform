import hashlib
import os
import sys
from pathlib import Path

import psycopg
import pytest
from qdrant_client import QdrantClient

APP_DIR = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIR))

PG_HOST = os.environ.get("KARMO_H01_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_H01_TEST_PG_PORT", "55432")
PG_DB = os.environ.get("KARMO_H01_TEST_PG_DB", "karmo_h01_test")
PG_USER = os.environ.get("KARMO_H01_TEST_PG_USER", "karmo_h01_test")
PG_PASSWORD = os.environ.get(
    "KARMO_H01_TEST_PG_PASSWORD", "karmo_h01_test_synthetic_local_only"
)
QDRANT_URL = os.environ.get("KARMO_H01_TEST_QDRANT_URL", "http://127.0.0.1:56333")
COLLECTION = "karmo_semantic_memory"
VECTOR_SIZE = 768


def _conninfo():
    return (
        f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
        f"user={PG_USER} password={PG_PASSWORD}"
    )


@pytest.fixture()
def pg_conn():
    conn = psycopg.connect(_conninfo(), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean_state(pg_conn):
    """Reset the isolated schema and Qdrant collection before every test."""
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE public.karmo_outbox;")
        cur.execute("TRUNCATE public.conversation_memory RESTART IDENTITY CASCADE;")
    client = QdrantClient(url=QDRANT_URL)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"size": VECTOR_SIZE, "distance": "Cosine"},
    )
    yield


@pytest.fixture()
def qdrant_client():
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture()
def insert_conversation(pg_conn):
    def _insert(role, content):
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.conversation_memory (role, content) "
                "VALUES (%s, %s) RETURNING id",
                (role, content),
            )
            return cur.fetchone()[0]

    return _insert


def deterministic_embedding(content, size=VECTOR_SIZE):
    """Deterministic fake embedding for isolated tests (no real model call)."""
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    values = []
    for i in range(size):
        byte = digest[i % len(digest)]
        values.append((byte / 255.0) * 2.0 - 1.0)
    return values
