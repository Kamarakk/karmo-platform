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
# Isolated test collection only. Never karmo_semantic_memory, karmo_documents,
# or karmo_h00_dense_baseline -- those are production/baseline collection
# names and must not receive writable test activity.
COLLECTION = "karmo_h01_outbox_test"
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


def unavailable_embedding_endpoint(content):
    """Deterministic double for the isolated worker's embedding endpoint
    (Ollama) being unavailable.

    Raises the same exception class a real refused connection to the
    embedding endpoint would, without depending on any real socket/network
    behavior -- unlike connecting to a closed local port, this is reliable
    across sandboxed and CI network policies (no dependency on how the
    environment handles connection attempts to unused ports).
    """
    raise ConnectionRefusedError(
        "isolated test double: embedding endpoint unavailable"
    )


class _UnavailableQdrantClient:
    """Deterministic double for the isolated Qdrant target being
    unavailable. Exposes only what OutboxRelay._upsert calls, and raises the
    same exception class a real connection failure would -- without
    depending on real network/port-refusal behavior."""

    def upsert(self, *args, **kwargs):
        raise ConnectionError("isolated test double: Qdrant target unavailable")


def unavailable_qdrant_client():
    return _UnavailableQdrantClient()


def drain(relay, batch_size=10, max_iterations=50):
    """Repeatedly call ``process_once`` until no more events are claimed.

    Used by restart-recovery/concurrency/latency tests that need a worker to
    run to completion rather than a single batch.
    """
    all_outcomes = []
    for _ in range(max_iterations):
        outcomes = relay.process_once(batch_size=batch_size)
        if not outcomes:
            break
        all_outcomes.extend(outcomes)
    return all_outcomes
