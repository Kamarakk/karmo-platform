"""Tests for KarmoOperator.dispatch_vision/dispatch_transcribe/dispatch_speak
-- the webui's entry points into vision/ears/voice, going through the same
CapabilityDispatcher/ApprovalEngine authority path as every other KARMO
capability. These are deliberately NOT part of _CHAT_EXPOSED_TOOLS (see
vision_capability.py's module docstring); this file only covers the
direct-dispatch path a real client surface uses.
"""

from __future__ import annotations

from core_service.operator import KarmoOperator
from core_service.worker_dispatch import DispatchOutcome


class FakeWorkerDispatchClient:
    def __init__(self, *, available=True, outcome=None):
        self.available = available
        self._outcome = outcome
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return self._outcome


def _operator(worker_dispatch_client):
    return KarmoOperator(worker_dispatch_client=worker_dispatch_client)


def test_dispatch_vision_routes_through_the_dispatcher_and_returns_the_answer():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=8.1, poll_count=1,
        result={"answer": "a red square"},
    ))
    operator = _operator(client)

    result = operator.dispatch_vision(question="what color?", image_base64="ZmFrZQ==")

    assert result == {"answer": "a red square"}
    assert client.calls[0]["tool_id"] == "vision_describe"


def test_dispatch_transcribe_routes_through_the_dispatcher_and_returns_the_text():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-2", elapsed_seconds=3.0, poll_count=1,
        result={"text": "hello there"},
    ))
    operator = _operator(client)

    result = operator.dispatch_transcribe(audio_base64="ZmFrZQ==")

    assert result == {"text": "hello there"}
    assert client.calls[0]["tool_id"] == "transcribe_audio"


def test_dispatch_speak_routes_through_the_dispatcher_and_returns_the_audio():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-3", elapsed_seconds=0.5, poll_count=1,
        result={"audio_base64": "ZmFrZS1hdWRpbw=="},
    ))
    operator = _operator(client)

    result = operator.dispatch_speak(text="hello there")

    assert result == {"audio_base64": "ZmFrZS1hdWRpbw=="}
    assert client.calls[0]["tool_id"] == "synthesize_speech"


def test_dispatch_vision_never_raises_when_worker_dispatch_unavailable():
    operator = _operator(FakeWorkerDispatchClient(available=False))

    result = operator.dispatch_vision(question="what is this?", image_base64="ZmFrZQ==")

    assert "error" in result
    assert "not activated" in result["error"]


def test_dispatch_transcribe_never_raises_when_worker_dispatch_unavailable():
    operator = _operator(FakeWorkerDispatchClient(available=False))

    result = operator.dispatch_transcribe(audio_base64="ZmFrZQ==")

    assert "error" in result
    assert "not activated" in result["error"]


def test_dispatch_speak_never_raises_when_worker_dispatch_unavailable():
    operator = _operator(FakeWorkerDispatchClient(available=False))

    result = operator.dispatch_speak(text="hello")

    assert "error" in result
    assert "not activated" in result["error"]


def test_dispatch_vision_never_raises_on_a_dispatch_timeout():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="TIMED_OUT", job_id="job-4", elapsed_seconds=60.0, poll_count=60,
        result=None, error="deadline exceeded",
    ))
    operator = _operator(client)

    result = operator.dispatch_vision(question="what is this?", image_base64="ZmFrZQ==")

    assert "error" in result
    assert "TIMED_OUT" in result["error"]
