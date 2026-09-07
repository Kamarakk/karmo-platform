"""Fixtures for the H0.4 integrity/reconciliation acceptance suite.

Runs against the real isolated stack from docker-compose.yml (PostgreSQL +
Qdrant, non-default ports, synthetic credentials, container name prefix
"karmo-h04-test"). No mocks for the registry or the vector store: the whole
point of H0.4 is cross-store reconciliation, so the test doubles are limited
to embeddings (deterministic, no real model call) and archived files
(written to tmp_path, never a real document).
"""

import hashlib
import os
import sys
import uuid
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

APP_DIR = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIR))

PG_HOST = os.environ.setdefault("KARMO_H04_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.setdefault("KARMO_H04_PG_PORT", "57432")
PG_DB = os.environ.setdefault("KARMO_H04_PG_DB", "karmo_h04_test")
PG_USER = os.environ.setdefault("KARMO_H04_PG_USER", "karmo_h04_test")
PG_PASSWORD = os.environ.setdefault(
    "KARMO_DB_PASSWORD", "karmo_h04_test_synthetic_local_only"
)

QDRANT_URL = os.environ.get("KARMO_H04_TEST_QDRANT_URL", "http://127.0.0.1:58333")
# Isolated test collection only. Never karmo_documents, karmo_semantic_memory,
# or karmo_h00_dense_baseline -- those are production/baseline collection
# names and must not receive writable test activity.
COLLECTION_NAME = "karmo_h04_test_documents"
VECTOR_SIZE = 8

PG_CONTAINER = "karmo-h04-test-postgres"

import registry_db  # noqa: E402  (must follow sys.path insert above)


@pytest.fixture()
def pg_conn():
    conn = registry_db.get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset the isolated registry table and Qdrant collection before every
    test, so each test's corruption scenario starts from a known-empty,
    healthy baseline."""
    conn = registry_db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE public.document_registry RESTART IDENTITY;")
        conn.commit()
    finally:
        conn.close()

    client = QdrantClient(url=QDRANT_URL)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    yield


@pytest.fixture()
def qdrant_client():
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture()
def archive_root(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    return root


def _deterministic_embedding(text, size=VECTOR_SIZE):
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [(digest[i % len(digest)] / 255.0) * 2.0 - 1.0 for i in range(size)]


def _chunk_point_id(document_hash, chunk_number):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_hash}:{chunk_number}"))


DEFAULT_PIPELINE_VERSION = "h04-test-pipeline-v1"
DEFAULT_EMBEDDING_MODEL = "h04-test-embedding-v1"
DEFAULT_CHUNKER_VERSION = "h04-test-chunker-v1"


@pytest.fixture()
def make_document(pg_conn, qdrant_client, archive_root):
    """Factory fixture: builds one healthy, fully-consistent document
    (archived file + registry row + matching Qdrant chunk points) that a
    test can then selectively corrupt.

    Returns a dict: document_id, document_version, document_hash,
    archive_path (Path), expected_chunk_count, point_ids (list[str]),
    pipeline_version, embedding_model, chunker_version.
    """

    def _make(
        document_id,
        *,
        document_version=1,
        num_chunks=3,
        is_active=True,
        pipeline_version=DEFAULT_PIPELINE_VERSION,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        chunker_version=DEFAULT_CHUNKER_VERSION,
        superseded_by=None,
        deactivated_at=None,
        content=None,
    ):
        content = content or (
            f"synthetic H0.4 test content for {document_id} v{document_version}\n"
            f"chunk-bearing paragraph {uuid.uuid4()}"
        )
        archive_path = archive_root / f"{document_id}__v{document_version}.txt"
        archive_path.write_text(content, encoding="utf-8")

        document_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        registry_db.register_document_version(
            pg_conn,
            document_id=document_id,
            document_version=document_version,
            document_hash=document_hash,
            archive_source_location=str(archive_path),
            expected_chunk_count=num_chunks,
            pipeline_version=pipeline_version,
            embedding_model=embedding_model,
            chunker_version=chunker_version,
            is_active=is_active,
            superseded_by=superseded_by,
            source_path=str(archive_path),
            deactivated_at=deactivated_at,
        )
        pg_conn.commit()

        point_ids = []
        points = []
        for chunk_number in range(1, num_chunks + 1):
            text = f"{content} :: chunk {chunk_number}"
            point_id = _chunk_point_id(document_hash, chunk_number)
            point_ids.append(point_id)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=_deterministic_embedding(text),
                    payload={
                        "text": text,
                        "document_id": document_id,
                        "document_version": document_version,
                        "document_hash": document_hash,
                        "chunk_number": chunk_number,
                        "is_active": is_active,
                        "pipeline_version": pipeline_version,
                        "embedding_model": embedding_model,
                        "chunker_version": chunker_version,
                    },
                )
            )

        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)

        return {
            "document_id": document_id,
            "document_version": document_version,
            "document_hash": document_hash,
            "archive_path": archive_path,
            "expected_chunk_count": num_chunks,
            "point_ids": point_ids,
            "pipeline_version": pipeline_version,
            "embedding_model": embedding_model,
            "chunker_version": chunker_version,
        }

    return _make
