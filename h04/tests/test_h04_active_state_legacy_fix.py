"""Targeted regression coverage for the 2026-09-09 correction to
reconciliation.check_active_version_state's definition of "Qdrant-active".

Two scenarios, both against the real isolated Postgres + Qdrant stack
(h04/docker-compose.yml), proving the fix both removes a spurious
false-positive AND adds detection of a real gap the old, narrower
definition silently missed -- not merely a quieter auditor.
"""

import uuid

import auditor
import registry_db
from qdrant_client.models import PointStruct

from conftest import (
    COLLECTION_NAME,
    DEFAULT_CHUNKER_VERSION,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_PIPELINE_VERSION,
    _deterministic_embedding,
)


def _register(pg_conn, *, document_id, document_hash, is_active, superseded_by=None, deactivated_at=None):
    registry_db.register_document_version(
        pg_conn,
        document_id=document_id,
        document_version=1,
        document_hash=document_hash,
        archive_source_location=f"/tmp/does-not-matter/{document_id}",
        expected_chunk_count=1,
        pipeline_version=DEFAULT_PIPELINE_VERSION,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        chunker_version=DEFAULT_CHUNKER_VERSION,
        is_active=is_active,
        superseded_by=superseded_by,
        source_path=f"/tmp/does-not-matter/{document_id}",
        deactivated_at=deactivated_at,
    )
    pg_conn.commit()


def _upsert_legacy_point(qdrant_client, *, document_id, document_hash):
    """A genuine legacy (pre-H0.2) point: no is_active key at all, exactly
    as bootstrap_legacy_registry.py finds and registers them."""
    text = f"legacy point for {document_id} {uuid.uuid4()}"
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=_deterministic_embedding(text),
                payload={
                    "text": text,
                    "document_id": document_id,
                    "document_hash": document_hash,
                    "chunk_number": 1,
                    # deliberately no "is_active" key -- the legacy shape
                },
            )
        ],
    )


def test_legacy_bootstrapped_document_no_longer_falsely_flagged(qdrant_client, pg_conn):
    """A document exactly like the three the legacy bootstrap already
    registered (registry is_active=True, Qdrant points with no is_active
    field) must produce zero findings -- matching production retrieval,
    which already treats a missing is_active field as active."""
    document_id = "legacy_bootstrapped.docx"
    document_hash = "3" * 64

    _register(pg_conn, document_id=document_id, document_hash=document_hash, is_active=True)
    _upsert_legacy_point(qdrant_client, document_id=document_id, document_hash=document_hash)

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    active_state_findings = [f for f in findings if f["type"] == "ACTIVE_STATE_MISMATCH"]
    assert active_state_findings == []


def test_registry_inactive_qdrant_missing_field_now_detected(qdrant_client, pg_conn):
    """A document the registry marks superseded (is_active=False), but
    whose Qdrant points still lack an explicit is_active=False, is a real
    inconsistency -- production retrieval would still surface those points
    as active. The old, narrower definition never caught this; the fix
    must."""
    document_id = "silently_stale.docx"
    document_hash = "4" * 64

    _register(
        pg_conn,
        document_id=document_id,
        document_hash=document_hash,
        is_active=False,
        superseded_by="5" * 64,
        deactivated_at="2026-09-09T00:00:00+00:00",
    )
    _upsert_legacy_point(qdrant_client, document_id=document_id, document_hash=document_hash)

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "ACTIVE_STATE_MISMATCH"]
    assert len(matches) == 1
    assert matches[0]["document_id"] == document_id
    assert matches[0]["registry_active_hashes"] == []
    assert matches[0]["qdrant_active_hashes"] == [document_hash]
