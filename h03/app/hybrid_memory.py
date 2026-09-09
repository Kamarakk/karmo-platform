"""H0.3 experimental retrieval: dense-only baseline vs. hybrid RRF search.

Both functions query the same isolated collection (hybrid_ingest.COLLECTION_
NAME) so the comparison in test_h03_hybrid_vs_dense_benchmark.py is
apples-to-apples on identical corpus/points. ``search_dense_only`` is the
structural equivalent of production's document_memory.search_documents
(same get_embedding call, same cosine similarity) addressed through the
named "dense" vector field. ``search_hybrid_rrf`` adds a BM25 sparse
prefetch and fuses both rankings with Qdrant's native Reciprocal Rank
Fusion.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector
from semantic_memory import get_embedding

from hybrid_ingest import COLLECTION_NAME, DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from sparse_bm25 import build_sparse_vector

QDRANT_URL = "http://127.0.0.1:6333"

client = QdrantClient(url=QDRANT_URL)


def _format(results):
    return [
        {
            "score": result.score,
            "text": result.payload.get("text", ""),
            "source_file": result.payload.get("source_file", "unknown"),
            "chunk_number": result.payload.get("chunk_number"),
        }
        for result in results
    ]


def search_dense_only(query, limit=3):
    """Dense-only baseline: same embedding + cosine search as production."""
    vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        using=DENSE_VECTOR_NAME,
        limit=limit,
    ).points

    return _format(results)


def search_hybrid_rrf(query, limit=3, prefetch_limit=20):
    """Dense + BM25 sparse, fused with Reciprocal Rank Fusion."""
    dense_vector = get_embedding(query)
    indices, values = build_sparse_vector(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            Prefetch(query=dense_vector, using=DENSE_VECTOR_NAME, limit=prefetch_limit),
            Prefetch(
                query=SparseVector(indices=indices, values=values),
                using=SPARSE_VECTOR_NAME,
                limit=prefetch_limit,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
    ).points

    return _format(results)
