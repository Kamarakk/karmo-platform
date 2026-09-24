import pytest

from core_service.audio_transcribe_capability import (
    MAX_AUDIO_BYTES_BASE64,
    AudioTranscribeCapabilityError,
    dispatch_transcribe_audio,
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


def _succeeded(text="the quick brown fox"):
    return DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=3.05, poll_count=1,
        result={"text": text},
    )


def test_manifest_is_read_class_and_flags_worker_dependency():
    m = manifest()
    assert m["capability_class"] == "READ"
    assert "worker_dispatch_client" in m["dependencies"]


def test_successful_dispatch_returns_the_text():
    client = FakeWorkerDispatchClient(outcome=_succeeded("the quick brown fox"))

    text = dispatch_transcribe_audio(client, worker_id="KARMO-WORKER01", audio_base64="ZmFrZQ==")

    assert text == "the quick brown fox"
    assert client.calls == [{
        "worker_id": "KARMO-WORKER01",
        "tool_id": "transcribe_audio",
        "tool_version": "1.0.0",
        "arguments": {"model": "small", "audio_base64": "ZmFrZQ=="},
        "total_deadline_seconds": 30.0,
    }]


def test_unavailable_client_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(available=False)

    with pytest.raises(AudioTranscribeCapabilityError, match="not activated"):
        dispatch_transcribe_audio(client, worker_id="KARMO-WORKER01", audio_base64="ZmFrZQ==")

    assert client.calls == []


def test_empty_audio_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())

    with pytest.raises(AudioTranscribeCapabilityError, match="non-empty"):
        dispatch_transcribe_audio(client, worker_id="KARMO-WORKER01", audio_base64="")

    assert client.calls == []


def test_oversized_audio_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())
    huge = "x" * (MAX_AUDIO_BYTES_BASE64 + 1)

    with pytest.raises(AudioTranscribeCapabilityError, match="exceeds"):
        dispatch_transcribe_audio(client, worker_id="KARMO-WORKER01", audio_base64=huge)

    assert client.calls == []


def test_non_succeeded_outcome_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="TIMED_OUT", job_id="job-2", elapsed_seconds=30.0, poll_count=30,
        result=None, error="deadline exceeded",
    ))

    with pytest.raises(AudioTranscribeCapabilityError, match="TIMED_OUT: deadline exceeded"):
        dispatch_transcribe_audio(client, worker_id="KARMO-WORKER01", audio_base64="ZmFrZQ==")


def test_malformed_result_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-3", elapsed_seconds=3.0, poll_count=1,
        result={"not_text": "oops"},
    ))

    with pytest.raises(AudioTranscribeCapabilityError, match="invalid transcribe_audio result"):
        dispatch_transcribe_audio(client, worker_id="KARMO-WORKER01", audio_base64="ZmFrZQ==")


def test_handler_returns_a_dispatcher_bindable_closure():
    client = FakeWorkerDispatchClient(outcome=_succeeded("hello there"))

    result = handler(client)({"audio_base64": "ZmFrZQ=="})

    assert result == {"text": "hello there"}
    assert client.calls[0]["worker_id"] == "KARMO-WORKER01"
