import uuid
import requests

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

QDRANT_URL = "http://127.0.0.1:6333"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"

COLLECTION_NAME = "karmo_semantic_memory"
EMBED_MODEL = "embeddinggemma"
VECTOR_SIZE = 768

client = QdrantClient(url=QDRANT_URL)


def get_embedding(text):
    response = requests.post(
        OLLAMA_EMBED_URL,
        json={
            "model": EMBED_MODEL,
            "input": text,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()
    return data["embeddings"][0]


def initialize_semantic_memory():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )


def remember_semantic(text, role="memory"):
    vector = get_embedding(text)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": text,
                    "role": role,
                },
            )
        ],
    )


def search_semantic(query, limit=3):
    vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=limit,
        with_payload=True,
    ).points

    return [
        {
            "text": point.payload.get("text", ""),
            "role": point.payload.get("role", ""),
            "score": point.score,
        }
        for point in results
    ]
