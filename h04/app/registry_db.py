"""H0.4 PostgreSQL document registry.

PostgreSQL remains authoritative for structured registry/state (frozen H0.4
architecture requirement). This module owns the connection and the CRUD
surface over ``public.document_registry`` (see
``migrations/001_h04_document_registry.sql``). It performs no Qdrant access
and no archived-file access -- those live in ``reconciliation.py`` and
``archive_integrity.py`` -- and it never deletes or rewrites a row except
through the explicit lifecycle calls a caller makes (register / activate /
deactivate); the auditor (``auditor.py``) only reads through this module, it
never writes.

Connection defaults follow the production shape documented in
``docs/handoff/h04/memory.py`` (127.0.0.1:5433, db/user "karmo", password via
KARMO_DB_PASSWORD). Isolated tests override host/port/db/user via the
KARMO_H04_PG_* environment variables set in h04/conftest.py so this module
is never pointed at a production database.
"""

import os

import psycopg
from psycopg.rows import dict_row

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "5433"
DEFAULT_DB = "karmo"
DEFAULT_USER = "karmo"


def _conninfo():
    host = os.environ.get("KARMO_H04_PG_HOST", DEFAULT_HOST)
    port = os.environ.get("KARMO_H04_PG_PORT", DEFAULT_PORT)
    dbname = os.environ.get("KARMO_H04_PG_DB", DEFAULT_DB)
    user = os.environ.get("KARMO_H04_PG_USER", DEFAULT_USER)
    password = os.environ.get("KARMO_DB_PASSWORD")

    if not password:
        raise RuntimeError("KARMO_DB_PASSWORD is not set")

    return (
        f"host={host} port={port} dbname={dbname} "
        f"user={user} password={password}"
    )


def get_connection():
    return psycopg.connect(_conninfo(), row_factory=dict_row)


def register_document_version(
    conn,
    *,
    document_id,
    document_version,
    document_hash,
    archive_source_location,
    expected_chunk_count,
    pipeline_version,
    embedding_model,
    chunker_version,
    is_active=True,
    superseded_by=None,
    source_path=None,
    deactivated_at=None,
):
    """Insert one registry row for one document version.

    Mirrors the H0.2 ingest lifecycle: registering a new active version does
    not, by itself, deactivate any prior version -- callers that need that
    (e.g. the test fixtures simulating normal ingest) call
    ``deactivate_document_version`` explicitly, the same two-step shape
    production ingest uses (upsert new points, then set_payload the old
    ones inactive).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.document_registry (
                document_id, document_version, document_hash,
                archive_source_location, expected_chunk_count,
                pipeline_version, embedding_model, chunker_version,
                is_active, superseded_by, source_path, deactivated_at
            ) VALUES (
                %(document_id)s, %(document_version)s, %(document_hash)s,
                %(archive_source_location)s, %(expected_chunk_count)s,
                %(pipeline_version)s, %(embedding_model)s, %(chunker_version)s,
                %(is_active)s, %(superseded_by)s, %(source_path)s, %(deactivated_at)s
            )
            RETURNING id
            """,
            {
                "document_id": document_id,
                "document_version": document_version,
                "document_hash": document_hash,
                "archive_source_location": archive_source_location,
                "expected_chunk_count": expected_chunk_count,
                "pipeline_version": pipeline_version,
                "embedding_model": embedding_model,
                "chunker_version": chunker_version,
                "is_active": is_active,
                "superseded_by": superseded_by,
                "source_path": source_path,
                "deactivated_at": deactivated_at,
            },
        )
        return cur.fetchone()["id"]


def deactivate_document_version(conn, document_hash, *, superseded_by, deactivated_at):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.document_registry
            SET is_active = FALSE, superseded_by = %s, deactivated_at = %s
            WHERE document_hash = %s
            """,
            (superseded_by, deactivated_at, document_hash),
        )


def list_registry(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM public.document_registry ORDER BY document_id, document_version")
        return cur.fetchall()


def get_by_hash(conn, document_hash):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM public.document_registry WHERE document_hash = %s",
            (document_hash,),
        )
        return cur.fetchone()


def list_by_document_id(conn, document_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM public.document_registry WHERE document_id = %s "
            "ORDER BY document_version",
            (document_id,),
        )
        return cur.fetchall()
