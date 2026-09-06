"""Isolated H0.2 retrieval implementation for the knowledge-lifecycle acceptance test.

Adapted from the frozen production reference at
docs/handoff/h02/document_memory.production-reference.py. Normal retrieval
(``search_documents``) is scoped to is_active=True only, per the H0.2
acceptance gate ("normal retrieval uses only the intended active version").
``get_document_history`` is the audit path: it deliberately ignores
is_active so superseded (inactive) versions remain queryable -- never
deleted, per H0.2 scope.
"""

from qdrant_client.models import FieldCondition, Filter, MatchValue


def search_documents(client, collection, query_vector, limit=3):
    """Normal retrieval: active knowledge only."""
    results = client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=Filter(
            must=[FieldCondition(key="is_active", match=MatchValue(value=True))]
        ),
        limit=limit,
    ).points

    return [
        {
            "score": result.score,
            "text": result.payload.get("text", ""),
            "source_file": result.payload.get("source_file", "unknown"),
            "document_id": result.payload.get("document_id"),
            "document_version": result.payload.get("document_version"),
            "chunk_number": result.payload.get("chunk_number"),
            "is_active": result.payload.get("is_active"),
        }
        for result in results
    ]


def get_document_history(client, collection, document_id, limit=1000):
    """Audit retrieval: all versions of a document, active and superseded."""
    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return sorted(
        points,
        key=lambda point: (point.payload["document_version"], point.payload["chunk_number"]),
    )
