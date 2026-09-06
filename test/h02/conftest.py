"""Fixtures for the isolated H0.2 knowledge-lifecycle acceptance test.

Uses qdrant-client's local in-memory mode (``QdrantClient(":memory:")``) --
no Docker container, no network socket, no production Qdrant instance, and
nothing left behind on disk once the test process exits. This is stronger
isolation than a Docker-based test stack, at the cost of only being usable
for logic (not wire-protocol) verification, which is all this suite needs.
"""

import hashlib
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

APP_DIR = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIR))

# Isolated in-memory collection name only. Never karmo_documents or any other
# production collection name -- this never connects to a real Qdrant server.
COLLECTION = "karmo_h02_lifecycle_test"
VECTOR_SIZE = 32


@pytest.fixture()
def qdrant_client():
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    return client


@pytest.fixture()
def collection():
    return COLLECTION


def deterministic_embedding(text, size=VECTOR_SIZE):
    """Deterministic fake embedding for isolated tests (no real model call)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [(digest[i % len(digest)] / 255.0) * 2.0 - 1.0 for i in range(size)]
