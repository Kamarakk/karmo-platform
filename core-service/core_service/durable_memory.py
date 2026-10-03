"""Durable conversation and retrieval memory for the KARMO Core operator.

PostgreSQL is authoritative for conversation turns and the transactional
outbox. Qdrant is a derived semantic/document index. The adapter preserves the
verified H0.1 event identity/payload contract so the existing relay can deliver
semantic-memory updates asynchronously.

The module intentionally adds no listener or background daemon. External
clients are lazy/injectable so tests do not require live PostgreSQL, Qdrant, or
Ollama services.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import request


OUTBOX_NAMESPACE = uuid.UUID("30f34a29-d3d9-5222-8dfa-01d9ba8524d6")
EVENT_TYPE = "semantic_memory.upsert.v1"
AGGREGATE_TYPE = "conversation_memory"
DESTINATION = "qdrant:karmo_semantic_memory"
PAYLOAD_SCHEMA_VERSION = 1

DEFAULT_DSN_FILE = "/etc/karmo/core/postgres.dsn"
DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"
DEFAULT_OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"
DEFAULT_EMBED_MODEL = "embeddinggemma"
DEFAULT_VECTOR_SIZE = 768
DEFAULT_SEMANTIC_THRESHOLD = 0.45
DEFAULT_DOCUMENT_THRESHOLD = 0.50
DEFAULT_RECENT_LIMIT = 6
# Older turns are a different conversation; they stay reachable through
# semantic recall instead of being replayed as if just said.
DEFAULT_RECENT_WINDOW_MINUTES = 120
MAX_OWNER_FACT_CHARS = 500
DEFAULT_OWNER_FACT_LIMIT = 50
DEFAULT_RETRIEVAL_LIMIT = 3

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class MemoryConfigurationError(RuntimeError):
    """Raised when durable memory cannot be configured safely."""


@dataclass(frozen=True)
class MemoryContext:
    recent: tuple[tuple[str, str], ...]
    semantic: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]

    def render(self) -> str:
        parts: list[str] = []
        if self.recent:
            parts.append(
                "RECENT CONVERSATION:\n"
                + "\n".join(f"{role.upper()}: {content}" for role, content in self.recent)
            )
        retrieved = self.render_retrieved()
        if retrieved:
            parts.append(retrieved)
        return "\n\n".join(parts)

    def render_retrieved(self) -> str:
        """Semantic recall and document chunks only -- the recent turns are
        given to the model as real conversation turns instead."""
        parts: list[str] = []
        if self.semantic:
            parts.append(
                "RELEVANT LONG-TERM MEMORY:\n"
                + "\n".join(f"- {item['text']}" for item in self.semantic)
            )
        if self.documents:
            parts.append(
                "RETRIEVED PRIVATE DOCUMENTS:\n"
                + "\n\n".join(
                    "SOURCE FILE: {source_file}\nCHUNK: {chunk_number}\nCONTENT:\n{text}".format(**item)
                    for item in self.documents
                )
            )
        return "\n\n".join(parts)


class NullMemoryBackend:
    """Explicit degraded backend used when durable-memory config is absent."""

    status = "DEGRADED_CONFIG_MISSING"

    def build_context(self, _query: str) -> MemoryContext:
        return MemoryContext(recent=(), semantic=(), documents=())

    def remember_exchange(self, _prompt: str, _answer: str) -> None:
        return None

    def owner_facts(self, limit: int = DEFAULT_OWNER_FACT_LIMIT) -> tuple[tuple[int, str], ...]:
        return ()

    def remember_fact(self, _fact: str) -> int:
        raise MemoryConfigurationError("durable memory is not configured")

    def forget_fact(self, _fact_id: int) -> bool:
        raise MemoryConfigurationError("durable memory is not configured")


class DurableMemoryBackend:
    status = "ACTIVE"

    def __init__(
        self,
        *,
        dsn: str,
        connection_factory: Callable[[], Any] | None = None,
        qdrant_client: Any | None = None,
        embedding_function: Callable[[str], list[float]] | None = None,
        qdrant_url: str = DEFAULT_QDRANT_URL,
        semantic_collection: str = "karmo_semantic_memory",
        document_collection: str = "karmo_documents",
        vector_size: int = DEFAULT_VECTOR_SIZE,
    ) -> None:
        if not isinstance(dsn, str) or not dsn.strip():
            raise MemoryConfigurationError("database DSN must be non-empty")
        self._dsn = dsn.strip()
        self._connection_factory = connection_factory
        self._qdrant_client = qdrant_client
        self._embedding_function = embedding_function
        self.qdrant_url = qdrant_url
        self.semantic_collection = semantic_collection
        self.document_collection = document_collection
        self.vector_size = vector_size

    @staticmethod
    def _content_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_id_for_user_id(user_id: int) -> uuid.UUID:
        canonical = f"conversation_memory:{user_id}:{EVENT_TYPE}:{DESTINATION}"
        return uuid.uuid5(OUTBOX_NAMESPACE, canonical)

    def _connection(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        import psycopg

        return psycopg.connect(self._dsn)

    def _client(self):
        if self._qdrant_client is not None:
            return self._qdrant_client
        from qdrant_client import QdrantClient

        self._qdrant_client = QdrantClient(url=self.qdrant_url)
        return self._qdrant_client

    def _embedding(self, text: str) -> list[float]:
        if self._embedding_function is not None:
            vector = self._embedding_function(text)
        else:
            body = json.dumps({"model": DEFAULT_EMBED_MODEL, "input": text}).encode("utf-8")
            req = request.Request(
                DEFAULT_OLLAMA_EMBED_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            vector = payload["embeddings"][0]
        if not isinstance(vector, list) or len(vector) != self.vector_size:
            raise RuntimeError("embedding dimension mismatch")
        return vector

    def recent_turns(
        self,
        limit: int = DEFAULT_RECENT_LIMIT,
        within_minutes: int = DEFAULT_RECENT_WINDOW_MINUTES,
    ) -> tuple[tuple[str, str], ...]:
        if not 1 <= limit <= 50:
            raise ValueError("recent-turn limit must be between 1 and 50")
        if not 1 <= within_minutes <= 7 * 24 * 60:
            raise ValueError("recent-turn window must be between 1 minute and 7 days")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content
                    FROM public.conversation_memory
                    WHERE created_at >= NOW() - make_interval(mins => %s)
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (within_minutes, limit),
                )
                rows = cur.fetchall()
        rows.reverse()
        return tuple((str(role), str(content)) for role, content in rows)

    def semantic_search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
        threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
    ) -> tuple[dict[str, Any], ...]:
        vector = self._embedding(query)
        points = self._client().query_points(
            collection_name=self.semantic_collection,
            query=vector,
            limit=limit,
            with_payload=True,
        ).points
        return tuple(
            {
                "text": point.payload.get("text", ""),
                "role": point.payload.get("role", ""),
                "score": point.score,
            }
            for point in points
            if point.score >= threshold and point.payload.get("text")
        )

    def document_search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
        threshold: float = DEFAULT_DOCUMENT_THRESHOLD,
    ) -> tuple[dict[str, Any], ...]:
        from qdrant_client.models import Filter, FieldCondition, IsEmptyCondition, MatchValue, PayloadField

        vector = self._embedding(query)
        points = self._client().query_points(
            collection_name=self.document_collection,
            query=vector,
            query_filter=Filter(
                should=[
                    FieldCondition(key="is_active", match=MatchValue(value=True)),
                    IsEmptyCondition(is_empty=PayloadField(key="is_active")),
                ],
                must_not=[FieldCondition(key="is_active", match=MatchValue(value=False))],
            ),
            limit=limit,
            with_payload=True,
        ).points
        return tuple(
            {
                "score": point.score,
                "text": point.payload.get("text", ""),
                "source_file": point.payload.get("source_file", "unknown"),
                "chunk_number": point.payload.get("chunk_number"),
            }
            for point in points
            if point.score >= threshold and point.payload.get("text")
        )

    def build_context(self, query: str) -> MemoryContext:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text")
        return MemoryContext(
            recent=self.recent_turns(),
            semantic=self.semantic_search(query),
            documents=self.document_search(query),
        )

    def remember_exchange(self, prompt: str, answer: str) -> None:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be non-empty text")
        if not isinstance(answer, str):
            raise TypeError("answer must be text")

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.conversation_memory (role, content)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    ("user", prompt),
                )
                user_id = int(cur.fetchone()[0])
                cur.execute(
                    """
                    INSERT INTO public.conversation_memory (role, content)
                    VALUES (%s, %s)
                    """,
                    ("assistant", answer),
                )
                event_id = self._event_id_for_user_id(user_id)
                payload = {
                    "schema_version": PAYLOAD_SCHEMA_VERSION,
                    "role": "user",
                    "content_sha256": self._content_sha256(prompt),
                }
                digest = payload["content_sha256"]
                if not _SHA256_PATTERN.fullmatch(digest):
                    raise RuntimeError("invalid content digest")
                cur.execute(
                    """
                    INSERT INTO public.karmo_outbox (
                        event_id, event_type, aggregate_type, aggregate_id,
                        destination, payload
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        event_id,
                        EVENT_TYPE,
                        AGGREGATE_TYPE,
                        user_id,
                        DESTINATION,
                        json.dumps(payload),
                    ),
                )


    def owner_facts(self, limit: int = DEFAULT_OWNER_FACT_LIMIT) -> tuple[tuple[int, str], ...]:
        """Facts Kamara explicitly told KARMO to remember, oldest first."""
        if not 1 <= limit <= 200:
            raise ValueError("owner-fact limit must be between 1 and 200")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, fact
                    FROM public.karmo_owner_facts
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        rows.reverse()
        return tuple((int(fact_id), str(fact)) for fact_id, fact in rows)

    def remember_fact(self, fact: str) -> int:
        if not isinstance(fact, str) or not fact.strip():
            raise ValueError("fact must be non-empty text")
        fact = fact.strip()
        if len(fact) > MAX_OWNER_FACT_CHARS:
            raise ValueError(f"fact must be at most {MAX_OWNER_FACT_CHARS} characters")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.karmo_owner_facts (fact) VALUES (%s) RETURNING id",
                    (fact,),
                )
                return int(cur.fetchone()[0])

    def forget_fact(self, fact_id: int) -> bool:
        if not isinstance(fact_id, int) or isinstance(fact_id, bool) or fact_id <= 0:
            raise ValueError("fact id must be a positive integer")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.karmo_owner_facts WHERE id = %s", (fact_id,))
                return cur.rowcount == 1


def build_default_memory_backend(dsn_file: str = DEFAULT_DSN_FILE):
    path = Path(dsn_file)
    if not path.is_file():
        return NullMemoryBackend()
    mode = path.stat().st_mode & 0o777
    if mode & 0o007:
        raise MemoryConfigurationError("memory DSN file must not be accessible to other users")
    dsn = path.read_text(encoding="utf-8").strip()
    if not dsn:
        raise MemoryConfigurationError("memory DSN file is empty")
    return DurableMemoryBackend(dsn=dsn)
