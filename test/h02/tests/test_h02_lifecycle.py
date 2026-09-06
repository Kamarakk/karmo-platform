"""KARMO H0.2 isolated acceptance test: Knowledge Lifecycle & Vector Versioning.

One concise test per requirement group of the frozen H0.2 scope, run against
an in-memory, isolated Qdrant collection (karmo_h02_lifecycle_test) with
synthetic fixture text only. No production host, credential, database,
Qdrant collection, or real document is touched.

Requirement -> test mapping:
  - preserve existing SHA-256 identity            -> test_sha256_identity_preserved
  - add is_active/document_version/pipeline_version/
    embedding_model/chunker_version/superseded_by/
    created_at/deactivated_at                      -> test_v1_lifecycle_fields_present
  - verify document v1 -> v2 lifecycle             -> test_v1_to_v2_supersession_audit_and_retrieval
  - verify v1 remains auditable                    -> test_v1_to_v2_supersession_audit_and_retrieval
  - verify only v2 appears in normal retrieval      -> test_v1_to_v2_supersession_audit_and_retrieval
"""

import hashlib

from document_ingest import (
    CHUNKER_VERSION,
    EMBEDDING_MODEL,
    PIPELINE_VERSION,
    ingest_document,
    text_hash,
)
from document_memory import get_document_history, search_documents

from conftest import deterministic_embedding

DOCUMENT_ID = "policy-handbook"
V1_TEXT = "Employees may take unlimited paid leave with manager approval."
V2_TEXT = "Employees receive twenty-five days of paid leave per calendar year."


def test_sha256_identity_preserved(qdrant_client, collection):
    """document_hash is still SHA-256 of content (the production file_hash
    algorithm), and re-ingesting identical content is recognized as the same
    version rather than creating a spurious new one."""
    result = ingest_document(
        qdrant_client, collection, DOCUMENT_ID, V1_TEXT, deterministic_embedding
    )

    assert result["document_hash"] == text_hash(V1_TEXT)
    assert result["document_hash"] == hashlib.sha256(V1_TEXT.encode("utf-8")).hexdigest()

    duplicate = ingest_document(
        qdrant_client, collection, DOCUMENT_ID, V1_TEXT, deterministic_embedding
    )
    assert duplicate is None


def test_v1_lifecycle_fields_present(qdrant_client, collection):
    """A freshly ingested version carries every H0.2 lifecycle field with the
    correct initial values."""
    ingest_document(qdrant_client, collection, DOCUMENT_ID, V1_TEXT, deterministic_embedding)

    history = get_document_history(qdrant_client, collection, DOCUMENT_ID)
    assert len(history) == 1
    payload = history[0].payload

    assert payload["is_active"] is True
    assert payload["document_version"] == 1
    assert payload["pipeline_version"] == PIPELINE_VERSION
    assert payload["embedding_model"] == EMBEDDING_MODEL
    assert payload["chunker_version"] == CHUNKER_VERSION
    assert payload["superseded_by"] is None
    assert payload["created_at"] is not None
    assert payload["deactivated_at"] is None


def test_v1_to_v2_supersession_audit_and_retrieval(qdrant_client, collection):
    """v1 -> v2 supersedes without deleting; v1 stays auditable; normal
    retrieval returns only the active v2 knowledge."""
    v1 = ingest_document(qdrant_client, collection, DOCUMENT_ID, V1_TEXT, deterministic_embedding)
    v2 = ingest_document(qdrant_client, collection, DOCUMENT_ID, V2_TEXT, deterministic_embedding)

    assert v2["document_version"] == v1["document_version"] + 1
    assert v2["document_hash"] != v1["document_hash"]

    history = get_document_history(qdrant_client, collection, DOCUMENT_ID)
    assert len(history) == 2  # both versions still present -- nothing deleted

    v1_point, v2_point = history
    assert v1_point.payload["document_version"] == 1
    assert v1_point.payload["is_active"] is False
    assert v1_point.payload["deactivated_at"] is not None
    assert v1_point.payload["superseded_by"] == v2["document_hash"]

    assert v2_point.payload["document_version"] == 2
    assert v2_point.payload["is_active"] is True
    assert v2_point.payload["superseded_by"] is None
    assert v2_point.payload["deactivated_at"] is None

    query_vector = deterministic_embedding(V2_TEXT)
    results = search_documents(qdrant_client, collection, query_vector, limit=10)

    assert len(results) > 0
    assert all(result["is_active"] for result in results)
    assert all(result["document_version"] == 2 for result in results)

    result_texts = {result["text"] for result in results}
    assert V2_TEXT in result_texts
    assert V1_TEXT not in result_texts
