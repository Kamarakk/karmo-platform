from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core_service.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
)

HOST = "KARMO-WORKER01"
MODEL = "qwen3:8b"


class FakeClock:
    def __init__(self, start=None):
        self.now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def _breaker(clock=None, **overrides):
    return CircuitBreaker(clock=clock or FakeClock(), **overrides)


def test_starts_closed_and_allows_requests():
    breaker = _breaker()
    assert breaker.allow_request(HOST, MODEL) is True
    assert breaker.snapshot(HOST, MODEL).state == "CLOSED"


def test_success_never_trips_the_breaker():
    breaker = _breaker()
    for _ in range(20):
        assert breaker.allow_request(HOST, MODEL) is True
        breaker.record_result(HOST, MODEL, success=True)
    assert breaker.snapshot(HOST, MODEL).state == "CLOSED"


def test_trips_open_on_three_consecutive_failures():
    # A generous min-attempts bound isolates the consecutive-failure path
    # from the independent failure-rate path below (both are legitimate,
    # OR'd trip conditions -- this test targets only one of them).
    breaker = _breaker(failure_rate_min_attempts=100)
    for _ in range(3):
        assert breaker.allow_request(HOST, MODEL) is True
        breaker.record_result(HOST, MODEL, success=False)
    snap = breaker.snapshot(HOST, MODEL)
    assert snap.state == "OPEN"
    assert snap.consecutive_failures == 3
    assert breaker.allow_request(HOST, MODEL) is False


def test_a_success_resets_the_consecutive_failure_count():
    breaker = _breaker(failure_rate_min_attempts=100)
    breaker.record_result(HOST, MODEL, success=False)
    breaker.record_result(HOST, MODEL, success=False)
    breaker.record_result(HOST, MODEL, success=True)  # resets
    breaker.record_result(HOST, MODEL, success=False)
    breaker.record_result(HOST, MODEL, success=False)
    # Only 2 consecutive failures since the reset -- must still be closed.
    assert breaker.snapshot(HOST, MODEL).state == "CLOSED"
    assert breaker.allow_request(HOST, MODEL) is True


def test_trips_open_on_failure_rate_over_trailing_window_without_three_consecutive():
    clock = FakeClock()
    breaker = _breaker(clock=clock)
    # Alternating outcomes never reach 3 consecutive failures, but the
    # failure rate over the trailing window is 50% with >=2 attempts.
    breaker.record_result(HOST, MODEL, success=True)
    clock.advance(1)
    breaker.record_result(HOST, MODEL, success=False)
    clock.advance(1)
    breaker.record_result(HOST, MODEL, success=True)
    clock.advance(1)
    breaker.record_result(HOST, MODEL, success=False)
    assert breaker.snapshot(HOST, MODEL).consecutive_failures == 1  # never hit 3
    assert breaker.snapshot(HOST, MODEL).state == "OPEN"


def test_failure_rate_trip_requires_the_minimum_attempt_count():
    """A single failure alone must never trip the breaker via the rate
    condition -- FAILURE_RATE_MIN_ATTEMPTS exists precisely so one bad
    call doesn't look like a 100% failure rate."""
    breaker = _breaker()
    breaker.record_result(HOST, MODEL, success=False)
    assert breaker.snapshot(HOST, MODEL).state == "CLOSED"


def test_attempts_outside_the_trailing_window_do_not_count_toward_failure_rate():
    clock = FakeClock()
    breaker = _breaker(clock=clock, failure_rate_window_seconds=600.0)
    breaker.record_result(HOST, MODEL, success=False)
    clock.advance(601)  # now outside the 10-minute window
    breaker.record_result(HOST, MODEL, success=True)
    # Only the recent success remains in the window -- 0% failure rate,
    # and consecutive_failures was reset by the success.
    assert breaker.snapshot(HOST, MODEL).state == "CLOSED"
    assert breaker.snapshot(HOST, MODEL).consecutive_failures == 0


def test_open_breaker_denies_requests_until_the_open_duration_elapses():
    clock = FakeClock()
    breaker = _breaker(clock=clock, initial_open_seconds=300.0)
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(299)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(2)  # now past the 300s mark
    assert breaker.allow_request(HOST, MODEL) is True
    assert breaker.snapshot(HOST, MODEL).state == "HALF_OPEN"


def test_half_open_allows_exactly_one_trial_request():
    clock = FakeClock()
    breaker = _breaker(clock=clock, initial_open_seconds=300.0)
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)
    clock.advance(300)
    assert breaker.allow_request(HOST, MODEL) is True  # the one trial
    # A second concurrent caller must be denied while the trial is pending.
    assert breaker.allow_request(HOST, MODEL) is False
    assert breaker.allow_request(HOST, MODEL) is False


def test_half_open_success_closes_the_breaker_and_resets_backoff():
    clock = FakeClock()
    breaker = _breaker(clock=clock, initial_open_seconds=300.0)
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)
    clock.advance(300)
    assert breaker.allow_request(HOST, MODEL) is True
    breaker.record_result(HOST, MODEL, success=True)
    snap = breaker.snapshot(HOST, MODEL)
    assert snap.state == "CLOSED"
    assert snap.consecutive_failures == 0
    assert breaker.allow_request(HOST, MODEL) is True

    # A fresh trip afterward must use the initial open duration again, not
    # a leftover doubled one from any prior cycle.
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(299)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(2)
    assert breaker.allow_request(HOST, MODEL) is True


def test_half_open_failure_reopens_and_doubles_the_backoff_up_to_the_cap():
    clock = FakeClock()
    breaker = _breaker(clock=clock, initial_open_seconds=300.0, max_open_seconds=1800.0)
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)

    # Cycle 1: 300s -> fails trial -> doubles to 600s.
    clock.advance(300)
    assert breaker.allow_request(HOST, MODEL) is True
    breaker.record_result(HOST, MODEL, success=False)
    assert breaker.snapshot(HOST, MODEL).state == "OPEN"
    clock.advance(599)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(2)
    assert breaker.allow_request(HOST, MODEL) is True  # cycle 2 trial, at 600s

    # Cycle 2: fails again -> doubles to 1200s.
    breaker.record_result(HOST, MODEL, success=False)
    clock.advance(1199)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(2)
    assert breaker.allow_request(HOST, MODEL) is True  # cycle 3 trial, at 1200s

    # Cycle 3: fails again -> would double to 2400s, capped at 1800s.
    breaker.record_result(HOST, MODEL, success=False)
    clock.advance(1799)
    assert breaker.allow_request(HOST, MODEL) is False
    clock.advance(2)
    assert breaker.allow_request(HOST, MODEL) is True  # capped at 1800s, not 2400s


def test_pairs_are_tracked_independently():
    breaker = _breaker()
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)
    assert breaker.snapshot(HOST, MODEL).state == "OPEN"
    # A different model on the same host, and the same model on a
    # different host, must both remain unaffected.
    assert breaker.snapshot(HOST, "ministral-3:8b").state == "CLOSED"
    assert breaker.snapshot("karmo-ai01", MODEL).state == "CLOSED"
    assert breaker.allow_request(HOST, "ministral-3:8b") is True
    assert breaker.allow_request("karmo-ai01", MODEL) is True


def test_a_result_recorded_while_open_is_ignored_defensively():
    """Should never happen if callers check allow_request first, but must
    not corrupt trip state if it somehow does."""
    breaker = _breaker()
    for _ in range(3):
        breaker.record_result(HOST, MODEL, success=False)
    assert breaker.snapshot(HOST, MODEL).state == "OPEN"
    breaker.record_result(HOST, MODEL, success=True)  # ignored, not consumed as the trial
    assert breaker.snapshot(HOST, MODEL).state == "OPEN"


@pytest.mark.parametrize("kwargs,match", [
    ({"consecutive_failure_threshold": 0}, "consecutive_failure_threshold"),
    ({"failure_rate_threshold": 0.0}, "failure_rate_threshold"),
    ({"failure_rate_threshold": 1.5}, "failure_rate_threshold"),
    ({"failure_rate_window_seconds": 0}, "failure_rate_window_seconds"),
    ({"failure_rate_min_attempts": 0}, "failure_rate_min_attempts"),
    ({"initial_open_seconds": 0}, "initial_open_seconds"),
    ({"max_open_seconds": 10, "initial_open_seconds": 300}, "max_open_seconds"),
])
def test_constructor_validates_its_tunable_parameters(kwargs, match):
    with pytest.raises(CircuitBreakerError, match=match):
        CircuitBreaker(**kwargs)


def test_snapshot_is_content_safe_and_reflects_current_state():
    breaker = _breaker()
    snap = breaker.snapshot(HOST, MODEL)
    assert snap.host == HOST
    assert snap.model == MODEL
    assert snap.state == "CLOSED"
    assert snap.consecutive_failures == 0
    assert set(snap.__dataclass_fields__) == {"host", "model", "state", "consecutive_failures"}
