import pytest

from core_service.vision_capability import (
    MAX_IMAGE_BYTES_BASE64,
    MAX_QUESTION_CHARS,
    VisionCapabilityError,
    dispatch_vision_describe,
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


def _succeeded(answer="a red square"):
    return DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=8.1, poll_count=1,
        result={"answer": answer},
    )


def test_manifest_is_read_class_and_flags_worker_dependency():
    m = manifest()
    assert m["capability_class"] == "READ"
    assert "worker_dispatch_client" in m["dependencies"]


def test_successful_dispatch_returns_the_answer():
    client = FakeWorkerDispatchClient(outcome=_succeeded("a red square"))

    answer = dispatch_vision_describe(
        client, worker_id="KARMO-WORKER01", question="what color is this?", image_base64="ZmFrZQ==",
    )

    assert answer == "a red square"
    assert client.calls == [{
        "worker_id": "KARMO-WORKER01",
        "tool_id": "vision_describe",
        "tool_version": "1.0.0",
        "arguments": {"model": "moondream", "question": "what color is this?", "image_base64": "ZmFrZQ=="},
        "total_deadline_seconds": 60.0,
    }]


def test_unavailable_client_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(available=False)

    with pytest.raises(VisionCapabilityError, match="not activated"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question="what is this?", image_base64="ZmFrZQ==")

    assert client.calls == []


def test_empty_question_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())

    with pytest.raises(VisionCapabilityError, match="non-empty"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question="   ", image_base64="ZmFrZQ==")

    assert client.calls == []


def test_oversized_question_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())
    huge = "x" * (MAX_QUESTION_CHARS + 1)

    with pytest.raises(VisionCapabilityError, match="exceeds"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question=huge, image_base64="ZmFrZQ==")

    assert client.calls == []


def test_empty_image_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())

    with pytest.raises(VisionCapabilityError, match="non-empty"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question="what is this?", image_base64="")

    assert client.calls == []


def test_oversized_image_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())
    huge = "x" * (MAX_IMAGE_BYTES_BASE64 + 1)

    with pytest.raises(VisionCapabilityError, match="exceeds"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question="what is this?", image_base64=huge)

    assert client.calls == []


def test_non_succeeded_outcome_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="TIMED_OUT", job_id="job-2", elapsed_seconds=60.0, poll_count=60,
        result=None, error="deadline exceeded",
    ))

    with pytest.raises(VisionCapabilityError, match="TIMED_OUT: deadline exceeded"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question="what is this?", image_base64="ZmFrZQ==")


def test_malformed_result_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-3", elapsed_seconds=8.0, poll_count=1,
        result={"not_answer": "oops"},
    ))

    with pytest.raises(VisionCapabilityError, match="invalid vision_describe result"):
        dispatch_vision_describe(client, worker_id="KARMO-WORKER01", question="what is this?", image_base64="ZmFrZQ==")
