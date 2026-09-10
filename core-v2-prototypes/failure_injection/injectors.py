"""KARMO Core failure-injection framework -- ISOLATED, SYNTHETIC.

Reusable simulation primitives for the 12 failure categories the Core v2
Engineering Blueprint Program names explicitly. No real PostgreSQL,
Qdrant, model, or network dependency is touched by anything in this
module -- every failure is raised by a wrapped, synthetic callable.
"""

import time
from collections import defaultdict


# --- Named failure categories (12, matching the program's own list) -----

class SimulatedFailure(Exception):
    """Base class for every injected failure -- lets a test/production
    caller distinguish 'this is a deliberately simulated condition' from
    a genuine bug in the framework itself."""


class PostgresUnavailable(SimulatedFailure):
    pass


class QdrantUnavailable(SimulatedFailure):
    pass


class ModelUnavailable(SimulatedFailure):
    pass


class NetworkTimeout(SimulatedFailure):
    pass


class ToolTimeout(SimulatedFailure):
    pass


class MalformedResult(SimulatedFailure):
    pass


class PartialWrite(SimulatedFailure):
    pass


class DuplicateEvent(SimulatedFailure):
    pass


class ProcessCrash(SimulatedFailure):
    """Raised by a FlakyCallable to simulate a process dying mid-call --
    the caller never gets a normal return OR a normal exception in
    production, it simply never completes. Modeled here as an exception
    so tests can assert the caller's crash-recovery path (claim-token
    fencing, lease expiry) is what actually handles it, not this
    exception type itself."""


class ApprovalExpired(SimulatedFailure):
    pass


class PermissionDenied(SimulatedFailure):
    pass


class DependencyRateLimited(SimulatedFailure):
    pass


# --- Reusable injection primitives ---------------------------------------

class FlakyCallable:
    """Wraps a callable so it raises a given failure on specific call
    numbers (1-indexed), then behaves normally otherwise. The single
    reusable primitive every failure-injection test in this program
    builds on."""

    def __init__(self, fn, *, fail_on_calls, failure):
        self._fn = fn
        self._fail_on_calls = set(fail_on_calls)
        self._failure = failure
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if self.call_count in self._fail_on_calls:
            raise self._failure(f"synthetic failure injected on call #{self.call_count}")
        return self._fn(*args, **kwargs)


class RateLimiter:
    """Raises DependencyRateLimited once more than `limit` calls happen
    within one synthetic `window`. Time is caller-supplied (a float
    "tick" counter, not wall-clock), so tests stay deterministic."""

    def __init__(self, limit, window):
        self._limit = limit
        self._window = window
        self._calls = []

    def check(self, now):
        self._calls = [t for t in self._calls if now - t < self._window]
        if len(self._calls) >= self._limit:
            raise DependencyRateLimited(f"rate limit ({self._limit}/{self._window}) exceeded")
        self._calls.append(now)


def retry_with_backoff(fn, *, max_attempts, backoff_seconds, sleep=None, retry_on=(SimulatedFailure,)):
    """Same shape as outbox.py's retry_delay_seconds -- reused, not
    reinvented. `sleep` is injectable so tests never actually wait."""
    sleep = sleep or (lambda _seconds: None)
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except retry_on as error:
            last_error = error
            if attempt < max_attempts:
                sleep(backoff_seconds * (2 ** (attempt - 1)))

    raise last_error


def validate_result_shape(result, *, required_keys):
    """A minimal, generic 'malformed result' detector -- a result
    missing any required key raises MalformedResult rather than being
    silently accepted, matching the outbox relay's own
    embedding-shape-validation discipline (_embedding's dimension/finite
    checks) generalized to any tool result."""
    if not isinstance(result, dict):
        raise MalformedResult(f"expected a dict result, got {type(result).__name__}")
    missing = [key for key in required_keys if key not in result]
    if missing:
        raise MalformedResult(f"result missing required keys: {missing}")
    return result
