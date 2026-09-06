from qdrant_client import QdrantClient
from semantic_memory import get_embedding

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION_NAME = "karmo_documents"

client = QdrantClient(url=QDRANT_URL)


def search_documents(query, limit=3):
    vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
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
            }
        )

    return documents
