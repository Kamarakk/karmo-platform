from __future__ import annotations

from types import SimpleNamespace

from core_service.durable_memory import DurableMemoryBackend


class FakeQdrantClient:
    def __init__(self, points):
        self.points = points
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(points=self.points)


def _point(score, text, **payload):
    return SimpleNamespace(score=score, payload={"text": text, **payload})


def test_semantic_search_applies_threshold_and_returns_bounded_payload():
    client = FakeQdrantClient(
        [
            _point(0.91, "keep me", role="user", extra="ignored"),
            _point(0.20, "drop me", role="user"),
        ]
    )
    backend = DurableMemoryBackend(
        dsn="host=unused",
        qdrant_client=client,
        embedding_function=lambda _text: [0.0] * 768,
    )

    results = backend.semantic_search("worker setup", limit=3, threshold=0.45)

    assert results == ({"text": "keep me", "role": "user", "score": 0.91},)
    assert client.calls[0]["collection_name"] == "karmo_semantic_memory"
    assert client.calls[0]["limit"] == 3
    assert client.calls[0]["with_payload"] is True


def test_document_search_preserves_h02_legacy_active_filter_contract():
    client = FakeQdrantClient(
        [
            _point(
                0.88,
                "active document text",
                source_file="runbook.md",
                chunk_number=4,
                is_active=True,
            )
        ]
    )
    backend = DurableMemoryBackend(
        dsn="host=unused",
        qdrant_client=client,
        embedding_function=lambda _text: [0.0] * 768,
    )

    results = backend.document_search("runbook", limit=3, threshold=0.50)

    assert results == (
        {
            "score": 0.88,
            "text": "active document text",
            "source_file": "runbook.md",
            "chunk_number": 4,
        },
    )
    call = client.calls[0]
    assert call["collection_name"] == "karmo_documents"
    assert call["limit"] == 3
    assert call["with_payload"] is True

    query_filter = call["query_filter"]
    assert len(query_filter.should) == 2
    assert len(query_filter.must_not) == 1

    filter_text = str(query_filter)
    assert "is_active" in filter_text
    assert "True" in filter_text
    assert "False" in filter_text


def test_embedding_dimension_mismatch_fails_before_qdrant_query():
    client = FakeQdrantClient([])
    backend = DurableMemoryBackend(
        dsn="host=unused",
        qdrant_client=client,
        embedding_function=lambda _text: [0.0] * 10,
    )

    try:
        backend.semantic_search("bad embedding")
    except RuntimeError as exc:
        assert "dimension mismatch" in str(exc)
    else:
        raise AssertionError("invalid embedding dimension was accepted")

    assert client.calls == []
