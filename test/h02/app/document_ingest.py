"""Isolated H0.2 ingest implementation for the knowledge-lifecycle acceptance test.

Adapted from the frozen production reference at
docs/handoff/h02/document_ingest.production-reference.py. Preserves the
production SHA-256 document-hash identity and uuid5 chunk-id scheme
verbatim, and adds the H0.2 lifecycle/version metadata required by the
acceptance gate: is_active, document_version, pipeline_version,
embedding_model, chunker_version, superseded_by, created_at, deactivated_at.

This isolated copy takes already-extracted text and a caller-supplied
embedding function instead of importing docling/DocumentConverter or the
live semantic_memory.get_embedding endpoint, so H0.2 lifecycle logic can be
exercised against synthetic fixtures only -- no production dependency,
model weights, or network access.

``document_id`` is a new H0.2 concept: the stable identity of a *logical*
document across versions (e.g. a filename or slug), distinct from
``document_hash``, which remains the frozen per-version content identity.
Version lineage (v1 -> v2 supersession) is tracked by document_id; content
identity/dedup is still tracked by document_hash exactly as in production.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

PIPELINE_VERSION = "h02-lifecycle-v1"
EMBEDDING_MODEL = "h02-local-deterministic-v1"
CHUNKER_VERSION = "h02-paragraph-chunker-v1"


def text_hash(text):
    """SHA-256 content identity -- same algorithm as the production file_hash."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_id(document_hash, number, text):
    """Deterministic uuid5 chunk id -- verbatim from the production reference."""
    identity = f"{document_hash}:{number}:{text}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def chunk_text(text):
    """Minimal deterministic chunker: split on blank lines, drop empties."""
    parts = [part.strip() for part in text.split("\n\n")]
    return [part for part in parts if part]


def active_chunks_for_document(client, collection, document_id):
    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                FieldCondition(key="is_active", match=MatchValue(value=True)),
            ]
        ),
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    return points


def ingest_document(client, collection, document_id, text, embed, source_file=None):
    """Ingest one version of a logical document into an isolated collection.

    Returns a result dict on success, or None if this exact content is
    already the active version for document_id (duplicate, matching the
    production reference's hash-based dedup).

    If an active version already exists under document_id with a different
    document_hash, its chunks are superseded in place (is_active=False,
    deactivated_at set, superseded_by set to the new document_hash) -- never
    deleted -- and the new chunks become the sole active version.
    """
    document_hash = text_hash(text)
    existing_active = active_chunks_for_document(client, collection, document_id)

    if existing_active and existing_active[0].payload["document_hash"] == document_hash:
        return None

    now = datetime.now(timezone.utc).isoformat()

    if existing_active:
        previous_version = existing_active[0].payload["document_version"]
        new_version = previous_version + 1
        client.set_payload(
            collection_name=collection,
            payload={
                "is_active": False,
                "deactivated_at": now,
                "superseded_by": document_hash,
            },
            points=[point.id for point in existing_active],
        )
    else:
        new_version = 1

    chunks = chunk_text(text)
    points = [
        PointStruct(
            id=chunk_id(document_hash, number, chunk),
            vector=embed(chunk),
            payload={
                "text": chunk,
                "source_file": source_file or document_id,
                "document_id": document_id,
                "document_hash": document_hash,
                "document_version": new_version,
                "chunk_number": number,
                "pipeline_version": PIPELINE_VERSION,
                "embedding_model": EMBEDDING_MODEL,
                "chunker_version": CHUNKER_VERSION,
                "is_active": True,
                "superseded_by": None,
                "created_at": now,
                "deactivated_at": None,
            },
        )
        for number, chunk in enumerate(chunks, start=1)
    ]

    if not points:
        raise RuntimeError("Document produced no usable chunks.")

    client.upsert(collection_name=collection, points=points, wait=True)

    return {
        "document_id": document_id,
        "document_hash": document_hash,
        "document_version": new_version,
        "chunk_count": len(points),
    }
