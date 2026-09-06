"""Targeted backward-compatibility check for search_documents (H0.2 fix).

Production karmo_documents holds pre-H0.2 vectors with no is_active field.
This is a single, narrow check -- not a rerun of the full H0.2 lifecycle
suite -- confirming search_documents (h02/app/document_memory.py) now
treats:
  - a legacy point with no is_active field as active (returned),
  - an H0.2 point with is_active=True as active (returned),
  - an H0.2 point with is_active=False as inactive (excluded).
"""

from qdrant_client.models import PointStruct

VECTOR_SIZE = 32


def test_legacy_active_inactive_compat(lifecycle_modules):
    document_ingest, document_memory = lifecycle_modules

    vector = document_memory.get_embedding("compat check query")

    document_ingest.client.upsert(
        collection_name=document_ingest.COLLECTION_NAME,
        points=[
            PointStruct(
                id=1001,
                vector=vector,
                payload={"text": "legacy pre-H0.2 knowledge", "document_id": "legacy.md"},
            ),
            PointStruct(
                id=1002,
                vector=vector,
                payload={
                    "text": "H0.2 active knowledge",
                    "document_id": "active.md",
                    "is_active": True,
                },
            ),
            PointStruct(
                id=1003,
                vector=vector,
                payload={
                    "text": "H0.2 superseded knowledge",
                    "document_id": "inactive.md",
                    "is_active": False,
                },
            ),
        ],
    )

    results = document_memory.search_documents("compat check query", limit=10)
    texts = {result["text"] for result in results}

    assert "legacy pre-H0.2 knowledge" in texts
    assert "H0.2 active knowledge" in texts
    assert "H0.2 superseded knowledge" not in texts
