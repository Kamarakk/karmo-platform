from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    IsEmptyCondition,
    PayloadField,
)
from semantic_memory import get_embedding

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION_NAME = "karmo_documents"

client = QdrantClient(url=QDRANT_URL)


def search_documents(query, limit=3):
    """Normal retrieval.

    H0.2: scoped to active knowledge only. Production karmo_documents holds
    pre-H0.2 vectors with no is_active field at all -- those are legacy
    active knowledge and must keep surfacing here, so the filter treats
    is_active=True and a missing is_active field as active, and excludes
    only is_active=False (explicitly superseded). Superseded points are
    never deleted -- see get_document_history for the audit path.
    """
    vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=Filter(
            should=[
                FieldCondition(key="is_active", match=MatchValue(value=True)),
                IsEmptyCondition(is_empty=PayloadField(key="is_active")),
            ],
            must_not=[FieldCondition(key="is_active", match=MatchValue(value=False))],
        ),
        limit=limit,
    ).points

    documents = []

    for result in results:
        documents.append(
            {
                "score": result.score,
                "text": result.payload.get("text", ""),
                "source_file": result.payload.get("source_file", "unknown"),
                "chunk_number": result.payload.get("chunk_number"),
                "document_type": result.payload.get("document_type"),
                "document_id": result.payload.get("document_id"),
                "document_version": result.payload.get("document_version"),
                "is_active": result.payload.get("is_active"),
            }
        )

    return documents


def get_document_history(document_id, limit=10000):
    """H0.2 audit path: every version of a logical document, active and
    superseded. Never filters on is_active -- historical/inactive vectors
    remain fully queryable here; they are excluded only from
    search_documents (normal retrieval).
    """
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    return sorted(
        points,
        key=lambda point: (
            point.payload.get("document_version", 0),
            point.payload.get("chunk_number", 0),
        ),
    )
