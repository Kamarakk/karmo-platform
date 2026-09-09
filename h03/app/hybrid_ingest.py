"""H0.3 experimental hybrid ingestion: parallel path, isolated collection.

Frozen-scope compliance:
  - KEEPS EmbeddingGemma / the existing semantic embedding call unchanged:
    ``from semantic_memory import get_embedding`` is the same import and
    call signature used by the production document_ingest.py handoff.
  - KEEPS Docling HybridChunker unchanged: same
    ``docling.document_converter.DocumentConverter`` /
    ``docling.chunking.HybridChunker`` calls as production.
  - Writes only to COLLECTION_NAME below (an isolated H0.3 test collection).
    Never imports or references karmo_documents / karmo_semantic_memory.

This module intentionally does not reuse docs/handoff/h03/document_ingest.py
as a library: that module's ``client`` global targets the production
karmo_documents collection. Keeping H0.3 as a fully separate module (small,
duplicated file_hash/chunk_id helpers) guarantees no accidental write path
to production collections exists in this file.
"""

import hashlib
import uuid
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from semantic_memory import get_embedding

from sparse_bm25 import build_sparse_vector

QDRANT_URL = "http://127.0.0.1:6333"

# Isolated H0.3 test collection. Deliberately distinct from any production
# collection name so a misconfigured client can never fan in production
# data; see test_h03_hybrid_vs_dense_benchmark.py for a hard assertion of
# this invariant.
COLLECTION_NAME = "karmo_h03_hybrid_test"

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"

client = QdrantClient(url=QDRANT_URL)


def file_hash(path):
    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def chunk_id(document_hash, number, text):
    identity = f"{document_hash}:{number}:{text}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def initialize_hybrid_collection(vector_size):
    """Create the isolated H0.3 collection if it doesn't already exist.

    ``Modifier.IDF`` is what makes the "bm25" sparse field BM25 rather than
    plain term-frequency dot product: Qdrant applies IDF weighting from
    corpus statistics at query time on top of the raw term counts stored by
    build_sparse_vector.
    """
    if client.collection_exists(COLLECTION_NAME):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(size=vector_size, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF),
        },
    )


def ingest_document(file_path):
    """Ingest one file into the isolated hybrid collection.

    Mirrors the production chunk/embed loop exactly (DocumentConverter ->
    HybridChunker -> chunker.contextualize -> get_embedding) and adds one
    extra step per chunk: a BM25 sparse vector alongside the dense one.
    Returns the number of chunks upserted.
    """
    path = Path(file_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(path)

    document_hash = file_hash(path)

    result = DocumentConverter().convert(str(path))
    chunker = HybridChunker()
    chunks = list(chunker.chunk(result.document))

    points = []

    for number, chunk in enumerate(chunks, start=1):
        text = chunker.contextualize(chunk)

        if not text.strip():
            continue

        dense_vector = get_embedding(text)
        indices, values = build_sparse_vector(text)

        points.append(
            PointStruct(
                id=chunk_id(document_hash, number, text),
                vector={
                    DENSE_VECTOR_NAME: dense_vector,
                    SPARSE_VECTOR_NAME: SparseVector(indices=indices, values=values),
                },
                payload={
                    "text": text,
                    "source_file": path.name,
                    "document_hash": document_hash,
                    "chunk_number": number,
                },
            )
        )

    if not points:
        raise RuntimeError("Document produced no usable chunks.")

    client.upsert(collection_name=COLLECTION_NAME, points=points)

    return len(points)
