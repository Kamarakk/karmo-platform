"""Exact-match cache for external LLM delegation (ask_claude/ask_gpt).

Real motivation (2026-09-20, Kamara's own question about reducing
unnecessary network traffic for the local models "and gpt"): both
ask_claude and ask_gpt are real network round-trips to Anthropic's/
OpenAI's servers via their CLIs, each several seconds at minimum. An
exact repeat of the same question gains nothing from re-asking -- this
caches successful answers only, keyed by (tool_id, normalized
question), with a bounded TTL so a cached answer can't be served
forever.

Deliberately exact-match, not semantic/embedding-based: KARMO already
has Qdrant in production if semantic caching is ever wanted, but that
adds real complexity (embedding calls, similarity thresholds, staleness
rules) not justified without first measuring how often real repeat
questions actually occur. Start simple; upgrade only if the exact-match
hit rate turns out too low to matter.

In-memory only, not persisted across a karmo-core.service restart --
the simplest safe option, and a restart naturally clears anything that
might have gone stale. Thread-safe, matching circuit_breaker.py's same
discipline for shared mutable state in this service.
"""

from __future__ import annotations

import threading
import time

DEFAULT_TTL_SECONDS = 3600.0
DEFAULT_MAX_ENTRIES = 200


def _normalize(question: str) -> str:
    return " ".join(question.strip().lower().split())


class DelegationCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        time_fn=time.monotonic,
    ):
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._time_fn = time_fn
        self._lock = threading.Lock()
        self._store: dict[tuple[str, str], tuple[str, float]] = {}

    def get(self, tool_id: str, question: str) -> str | None:
        key = (tool_id, _normalize(question))
        now = self._time_fn()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            answer, expires_at = entry
            if now >= expires_at:
                del self._store[key]
                return None
            return answer

    def set(self, tool_id: str, question: str, answer: str) -> None:
        key = (tool_id, _normalize(question))
        now = self._time_fn()
        with self._lock:
            if key not in self._store and len(self._store) >= self._max_entries:
                oldest_key = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest_key]
            self._store[key] = (answer, now + self._ttl_seconds)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


_default_cache = DelegationCache()


def get_default_cache() -> DelegationCache:
    """Process-wide singleton -- ask_claude and ask_gpt each key their own
    entries by tool_id, so sharing one cache instance is safe and avoids
    two separate lock/store pairs for no benefit."""
    return _default_cache
