from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core_service.worker_dispatch import DispatchOutcome, WorkerDispatchError, dispatch_and_wait

NOW = datetime(2026, 9, 19, 0, 0, 0, tzinfo=timezone.utc)


class FakeApproval:
    def __init__(self, approval_id="approval-1"):
        self.approval_id = approval_id


class FakeApprovalEngine:
    def __init__(self):
        self.requested = []
        self.approved = []

    def request(self, **kwargs):
        self.requested.append(kwargs)
        return FakeApproval()

    def approve(self, approval_id, **kwargs):
        self.approved.append((approval_id, kwargs))


class FakeGatewayBackend:
    def __init__(self):
        self.attached = []

    def attach_job_arguments(self, **kwargs):
        self.attached.append(kwargs)


class FakeStore:
    def __init__(self, *, states, result=None):
        """states: list of state strings returned on successive
        get_job_state() calls; the last one repeats once exhausted."""
        self.states = list(states)
        self.result = result
        self.enqueue_calls = []
        self.job_state_calls = 0

    def enqueue_job(self, **kwargs):
        self.enqueue_calls.append(kwargs)
        return "job-1"

    def get_job_state(self, job_id):
        self.job_state_calls += 1
        index = min(self.job_state_calls - 1, len(self.states) - 1)
        state = self.states[index]
        if state is None:
            return None
        return {"state": state, "worker_id": "KARMO-WORKER01", "attempt_count": 1,
                "result_digest": "digest" if state == "SUCCEEDED" else None,
                "last_error": "boom" if state == "FAILED" else None}

    def get_worker_job_result(self, job_id):
        return {"result": self.result, "result_digest": "digest"} if self.result is not None else None


def _clock_and_sleep(start=NOW):
    """A coordinated fake clock/sleep pair: each sleep() call advances the
    fake clock by exactly the requested duration, so a timeout path
    resolves deterministically with zero real wall-clock delay."""
    current = [start]

    def clock():
        return current[0]

    def sleep(seconds):
        current[0] = current[0] + timedelta(seconds=seconds)

    return clock, sleep


def _dispatch(store, *, gateway_backend=None, approval_engine=None, **kwargs):
    clock, sleep = _clock_and_sleep()
    return dispatch_and_wait(
        store=store,
        gateway_backend=gateway_backend or FakeGatewayBackend(),
        approval_engine=approval_engine or FakeApprovalEngine(),
        worker_id="KARMO-WORKER01",
        tool_id="model_chat_tools",
        tool_version="1.0.0",
        arguments={"model": "qwen3:8b", "messages": [{"role": "user", "content": "hi"}]},
        clock=clock,
        sleep=sleep,
        **kwargs,
    )


def test_dispatch_and_wait_returns_succeeded_with_real_result_content():
    store = FakeStore(states=["QUEUED", "LEASED", "SUCCEEDED"], result={"content": "hi there", "tool_calls": None})
    outcome = _dispatch(store)

    assert outcome.outcome == "SUCCEEDED"
    assert outcome.result == {"content": "hi there", "tool_calls": None}
    assert outcome.poll_count == 3
    assert isinstance(outcome, DispatchOutcome)


def test_dispatch_and_wait_returns_failed_with_error():
    store = FakeStore(states=["QUEUED", "FAILED"])
    outcome = _dispatch(store)

    assert outcome.outcome == "FAILED"
    assert outcome.error == "boom"
    assert outcome.result is None


def test_dispatch_and_wait_returns_recovery_required():
    store = FakeStore(states=["RECOVERY_REQUIRED"])
    outcome = _dispatch(store)

    assert outcome.outcome == "RECOVERY_REQUIRED"


def test_dispatch_and_wait_times_out_when_never_terminal():
    store = FakeStore(states=["QUEUED"])  # never advances past QUEUED
    outcome = _dispatch(store, total_deadline_seconds=5.0, poll_interval_seconds=1.0)

    assert outcome.outcome == "TIMED_OUT"
    assert "5.0s" in outcome.error
    assert "QUEUED" in outcome.error
    # Bounded: exactly ceil(deadline / interval) polls, never unbounded.
    assert outcome.poll_count <= 6


def test_dispatch_and_wait_never_retries_the_same_job_internally():
    """Section 3.5 routing-loop protection: exactly one enqueue, exactly
    one attach, regardless of how the job resolves."""
    gateway_backend = FakeGatewayBackend()
    store = FakeStore(states=["QUEUED"])
    _dispatch(store, gateway_backend=gateway_backend, total_deadline_seconds=3.0, poll_interval_seconds=1.0)

    assert len(store.enqueue_calls) == 1
    assert len(gateway_backend.attached) == 1


def test_dispatch_and_wait_propagates_setup_errors_without_wrapping():
    class ExplodingApprovalEngine(FakeApprovalEngine):
        def request(self, **kwargs):
            raise RuntimeError("approval engine unavailable")

    store = FakeStore(states=["SUCCEEDED"])
    with pytest.raises(RuntimeError, match="approval engine unavailable"):
        _dispatch(store, approval_engine=ExplodingApprovalEngine())

    assert store.enqueue_calls == []  # never reached enqueue


def test_dispatch_and_wait_authorizes_the_exact_worker_requested():
    approval_engine = FakeApprovalEngine()
    store = FakeStore(states=["SUCCEEDED"], result={"content": "ok", "tool_calls": None})
    _dispatch(store, approval_engine=approval_engine)

    assert approval_engine.approved[0][1]["authorized_executor"] == "KARMO-WORKER01"


def test_dispatch_and_wait_uses_a_consistent_arguments_digest_for_enqueue_and_attach():
    gateway_backend = FakeGatewayBackend()
    store = FakeStore(states=["SUCCEEDED"], result={"content": "ok", "tool_calls": None})
    _dispatch(store, gateway_backend=gateway_backend)

    enqueue_digest = store.enqueue_calls[0]["arguments_digest"]
    attach_digest = gateway_backend.attached[0]["expected_arguments_digest"]
    assert enqueue_digest == attach_digest
    assert enqueue_digest  # non-empty


def test_dispatch_and_wait_raises_if_job_vanishes_from_durable_state():
    store = FakeStore(states=[None])
    with pytest.raises(WorkerDispatchError, match="vanished"):
        _dispatch(store)
