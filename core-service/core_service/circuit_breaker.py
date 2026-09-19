"""KARMO Model Router -- circuit breaker (Section 3.5 of
docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md).

Prerequisite for Phase D2: a per-(host, model) breaker so a failing
candidate is skipped for a cooldown period instead of being retried on
every single request, and so recovery is proven with exactly one trial
request rather than a thundering herd once the cooldown ends.

Windows are time-based and small, not resilience4j's default 100-call
sliding window -- KARMO will not see 100 tool-calling calls in any
reasonable evaluation period. The trip/half-open/backoff shape below is
seeded from resilience4j's ratio/cooldown pattern, resized for KARMO's
volume, and is explicitly the plan's own "initial acceptance criteria...
to be validated and tuned against real Phase A telemetry before Phase D
ships -- not asserted as final tuned constants." All of it is therefore
exposed as constructor parameters with these values only as defaults.

State is held in memory, per process, not durably persisted. A breaker
resets to CLOSED on a router restart -- a deliberate simplification: the
cost of an unnecessary restart-triggered retry is low (one extra failed
attempt within the request's own total deadline), while durable breaker
state would need its own migration/table for a component the plan
itself says is not yet tuned. Revisit if restart-triggered retry storms
are ever observed in practice.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

CONSECUTIVE_FAILURE_THRESHOLD = 3
FAILURE_RATE_THRESHOLD = 0.5
FAILURE_RATE_WINDOW_SECONDS = 600.0  # 10 minutes
FAILURE_RATE_MIN_ATTEMPTS = 2
INITIAL_OPEN_SECONDS = 300.0  # 5 minutes
MAX_OPEN_SECONDS = 1800.0  # 30 minutes

_STATE_CLOSED = "CLOSED"
_STATE_OPEN = "OPEN"
_STATE_HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(RuntimeError):
    pass


@dataclass
class _PairState:
    state: str = _STATE_CLOSED
    consecutive_failures: int = 0
    # (timestamp, success) pairs within the trailing failure-rate window --
    # only ever consulted while CLOSED; pruned on every record_result call.
    attempts: list = field(default_factory=list)
    opened_at: datetime | None = None
    open_duration_seconds: float = INITIAL_OPEN_SECONDS
    half_open_trial_pending: bool = False


@dataclass(frozen=True)
class BreakerSnapshot:
    """Content-safe view of one pair's state -- host/model identifiers
    and breaker state only, suitable for Section 3.6's decision audit
    ("breaker state" is one of the signal values that record is meant to
    carry) with no risk of leaking anything beyond that."""
    host: str
    model: str
    state: str
    consecutive_failures: int


class CircuitBreaker:
    """Thread-safe, per-(host, model) circuit breaker."""

    def __init__(
        self,
        *,
        consecutive_failure_threshold: int = CONSECUTIVE_FAILURE_THRESHOLD,
        failure_rate_threshold: float = FAILURE_RATE_THRESHOLD,
        failure_rate_window_seconds: float = FAILURE_RATE_WINDOW_SECONDS,
        failure_rate_min_attempts: int = FAILURE_RATE_MIN_ATTEMPTS,
        initial_open_seconds: float = INITIAL_OPEN_SECONDS,
        max_open_seconds: float = MAX_OPEN_SECONDS,
        clock=None,
    ):
        if consecutive_failure_threshold < 1:
            raise CircuitBreakerError("consecutive_failure_threshold must be at least 1")
        if not (0.0 < failure_rate_threshold <= 1.0):
            raise CircuitBreakerError("failure_rate_threshold must be in (0, 1]")
        if failure_rate_window_seconds <= 0:
            raise CircuitBreakerError("failure_rate_window_seconds must be positive")
        if failure_rate_min_attempts < 1:
            raise CircuitBreakerError("failure_rate_min_attempts must be at least 1")
        if initial_open_seconds <= 0:
            raise CircuitBreakerError("initial_open_seconds must be positive")
        if max_open_seconds < initial_open_seconds:
            raise CircuitBreakerError("max_open_seconds must be >= initial_open_seconds")

        self._consecutive_failure_threshold = consecutive_failure_threshold
        self._failure_rate_threshold = failure_rate_threshold
        self._failure_rate_window_seconds = failure_rate_window_seconds
        self._failure_rate_min_attempts = failure_rate_min_attempts
        self._initial_open_seconds = initial_open_seconds
        self._max_open_seconds = max_open_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._pairs: dict[tuple[str, str], _PairState] = {}

    def _now(self) -> datetime:
        return self._clock()

    def _pair(self, host: str, model: str) -> _PairState:
        key = (host, model)
        pair = self._pairs.get(key)
        if pair is None:
            pair = _PairState()
            self._pairs[key] = pair
        return pair

    def allow_request(self, host: str, model: str) -> bool:
        """True if a candidate attempt for (host, model) may proceed right
        now. In HALF_OPEN, exactly one caller is ever told True until that
        trial's result is recorded -- every other concurrent caller sees
        False, matching Section 3.5's "allow exactly 1 trial request"."""
        with self._lock:
            now = self._now()
            pair = self._pair(host, model)

            if pair.state == _STATE_CLOSED:
                return True

            if pair.state == _STATE_OPEN:
                if pair.opened_at is not None and now >= pair.opened_at + timedelta(
                    seconds=pair.open_duration_seconds
                ):
                    pair.state = _STATE_HALF_OPEN
                    pair.half_open_trial_pending = True
                    return True
                return False

            # HALF_OPEN: only the one pending trial is allowed through.
            return False

    def record_result(self, host: str, model: str, *, success: bool) -> None:
        """Must be called exactly once for every attempt allow_request
        returned True for -- never for an attempt that was denied."""
        with self._lock:
            now = self._now()
            pair = self._pair(host, model)

            if pair.state == _STATE_HALF_OPEN:
                pair.half_open_trial_pending = False
                if success:
                    pair.state = _STATE_CLOSED
                    pair.consecutive_failures = 0
                    pair.attempts = []
                    pair.open_duration_seconds = self._initial_open_seconds
                else:
                    pair.state = _STATE_OPEN
                    pair.opened_at = now
                    pair.open_duration_seconds = min(
                        pair.open_duration_seconds * 2, self._max_open_seconds
                    )
                return

            if pair.state == _STATE_OPEN:
                # A result arriving for a pair already OPEN should never
                # happen if every caller checks allow_request first --
                # ignored defensively rather than corrupting trip state.
                return

            # CLOSED: track toward the two independent trip conditions.
            if success:
                pair.consecutive_failures = 0
            else:
                pair.consecutive_failures += 1

            pair.attempts.append((now, success))
            window_start = now - timedelta(seconds=self._failure_rate_window_seconds)
            pair.attempts = [a for a in pair.attempts if a[0] >= window_start]

            tripped_by_consecutive = pair.consecutive_failures >= self._consecutive_failure_threshold
            tripped_by_rate = False
            if len(pair.attempts) >= self._failure_rate_min_attempts:
                failures_in_window = sum(1 for _, ok in pair.attempts if not ok)
                failure_rate = failures_in_window / len(pair.attempts)
                tripped_by_rate = failure_rate >= self._failure_rate_threshold

            if tripped_by_consecutive or tripped_by_rate:
                pair.state = _STATE_OPEN
                pair.opened_at = now
                pair.open_duration_seconds = self._initial_open_seconds

    def snapshot(self, host: str, model: str) -> BreakerSnapshot:
        with self._lock:
            pair = self._pair(host, model)
            return BreakerSnapshot(
                host=host, model=model, state=pair.state,
                consecutive_failures=pair.consecutive_failures,
            )
