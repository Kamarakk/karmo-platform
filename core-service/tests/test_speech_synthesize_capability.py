import pytest

from core_service.speech_synthesize_capability import (
    MAX_TEXT_CHARS,
    SpeechSynthesizeCapabilityError,
    dispatch_synthesize_speech,
    handler,
    manifest,
)
from core_service.worker_dispatch import DispatchOutcome


class FakeWorkerDispatchClient:
    def __init__(self, *, available=True, outcome=None):
        self.available = available
        self._outcome = outcome
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return self._outcome


def _succeeded(audio_base64="ZmFrZS1hdWRpbw=="):
    return DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=0.5, poll_count=1,
        result={"audio_base64": audio_base64},
    )


def test_manifest_is_read_class_and_flags_worker_dependency():
    m = manifest()
    assert m["capability_class"] == "READ"
    assert "worker_dispatch_client" in m["dependencies"]


def test_successful_dispatch_returns_the_audio():
    client = FakeWorkerDispatchClient(outcome=_succeeded("ZmFrZS1hdWRpbw=="))

    audio = dispatch_synthesize_speech(client, worker_id="KARMO-WORKER01", text="hello there")

    assert audio == "ZmFrZS1hdWRpbw=="
    assert client.calls == [{
        "worker_id": "KARMO-WORKER01",
        "tool_id": "synthesize_speech",
        "tool_version": "1.0.0",
        "arguments": {"text": "hello there", "voice": "en_US-amy-medium"},
        "total_deadline_seconds": 30.0,
    }]


def test_unavailable_client_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(available=False)

    with pytest.raises(SpeechSynthesizeCapabilityError, match="not activated"):
        dispatch_synthesize_speech(client, worker_id="KARMO-WORKER01", text="hello")

    assert client.calls == []


def test_empty_text_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())

    with pytest.raises(SpeechSynthesizeCapabilityError, match="non-empty"):
        dispatch_synthesize_speech(client, worker_id="KARMO-WORKER01", text="   ")

    assert client.calls == []


def test_oversized_text_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())
    huge = "x" * (MAX_TEXT_CHARS + 1)

    with pytest.raises(SpeechSynthesizeCapabilityError, match="exceeds"):
        dispatch_synthesize_speech(client, worker_id="KARMO-WORKER01", text=huge)

    assert client.calls == []


def test_non_succeeded_outcome_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="TIMED_OUT", job_id="job-2", elapsed_seconds=30.0, poll_count=30,
        result=None, error="deadline exceeded",
    ))

    with pytest.raises(SpeechSynthesizeCapabilityError, match="TIMED_OUT: deadline exceeded"):
        dispatch_synthesize_speech(client, worker_id="KARMO-WORKER01", text="hello")


def test_malformed_result_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-3", elapsed_seconds=0.5, poll_count=1,
        result={"not_audio": "oops"},
    ))

    with pytest.raises(SpeechSynthesizeCapabilityError, match="invalid synthesize_speech result"):
        dispatch_synthesize_speech(client, worker_id="KARMO-WORKER01", text="hello")


def test_handler_returns_a_dispatcher_bindable_closure():
    client = FakeWorkerDispatchClient(outcome=_succeeded("ZmFrZS1hdWRpbw=="))

    result = handler(client)({"text": "hello there"})

    assert result == {"audio_base64": "ZmFrZS1hdWRpbw=="}
    assert client.calls[0]["worker_id"] == "KARMO-WORKER01"


def test_handler_gives_long_text_a_longer_deadline():
    client = FakeWorkerDispatchClient(outcome=_succeeded())

    handler(client)({"text": "short"})
    handler(client)({"text": "x" * MAX_TEXT_CHARS})

    short, long = (call["total_deadline_seconds"] for call in client.calls)
    assert 30.0 <= short < 31.0
    assert long == pytest.approx(30.0 + 0.15 * MAX_TEXT_CHARS)
