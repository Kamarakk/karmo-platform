import pytest

from core_service.code_assist_capability import (
    ASK_LOCAL_CODER_TOOL,
    ASK_LOCAL_CODER_TOOL_VERSION,
    CODE_ASSIST_MODEL,
    MAX_QUESTION_CHARS,
    CodeAssistCapabilityError,
    dispatch_code_assist,
    handler,
    manifest,
)
from core_service.control import ApprovalRequirement
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


def _succeeded(response="def foo(): pass"):
    return DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=45.0, poll_count=1,
        result={"response": response},
    )


def test_manifest_is_read_class_and_flags_worker_dependency():
    m = manifest()
    assert m["capability_class"] == "READ"
    assert "worker_dispatch_client" in m["dependencies"]


def test_successful_dispatch_returns_the_response():
    client = FakeWorkerDispatchClient(outcome=_succeeded("def foo(): pass"))

    response = dispatch_code_assist(client, worker_id="KARMO-WORKER01", question="write a no-op function")

    assert response == "def foo(): pass"
    assert client.calls == [{
        "worker_id": "KARMO-WORKER01",
        "tool_id": "model_chat",
        "tool_version": "1.0.0",
        "arguments": {"model": CODE_ASSIST_MODEL, "prompt": "write a no-op function"},
        "total_deadline_seconds": 90.0,
    }]


def test_unavailable_client_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(available=False)

    with pytest.raises(CodeAssistCapabilityError, match="not activated"):
        dispatch_code_assist(client, worker_id="KARMO-WORKER01", question="write a function")

    assert client.calls == []


def test_empty_question_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())

    with pytest.raises(CodeAssistCapabilityError, match="non-empty"):
        dispatch_code_assist(client, worker_id="KARMO-WORKER01", question="   ")

    assert client.calls == []


def test_oversized_question_is_refused_without_dispatching():
    client = FakeWorkerDispatchClient(outcome=_succeeded())
    huge = "x" * (MAX_QUESTION_CHARS + 1)

    with pytest.raises(CodeAssistCapabilityError, match="exceeds"):
        dispatch_code_assist(client, worker_id="KARMO-WORKER01", question=huge)

    assert client.calls == []


def test_non_succeeded_outcome_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="TIMED_OUT", job_id="job-2", elapsed_seconds=90.0, poll_count=90,
        result=None, error="deadline exceeded",
    ))

    with pytest.raises(CodeAssistCapabilityError, match="TIMED_OUT: deadline exceeded"):
        dispatch_code_assist(client, worker_id="KARMO-WORKER01", question="write a function")


def test_malformed_result_raises_clean_error():
    client = FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-3", elapsed_seconds=45.0, poll_count=1,
        result={"not_response": "oops"},
    ))

    with pytest.raises(CodeAssistCapabilityError, match="invalid model_chat result"):
        dispatch_code_assist(client, worker_id="KARMO-WORKER01", question="write a function")


def test_handler_closure_dispatches_to_the_bound_worker_and_returns_an_answer():
    client = FakeWorkerDispatchClient(outcome=_succeeded("def foo(): pass"))
    bound_handler = handler(client, worker_id="KARMO-WORKER02")

    result = bound_handler({"question": "write a no-op function"})

    assert result == {"answer": "def foo(): pass"}
    assert client.calls[0]["worker_id"] == "KARMO-WORKER02"


def test_capability_is_wired_into_the_exposed_tool_list_as_read_only():
    """Real, live-verified 2026-09-20: unlike vision/ears/voice,
    ask_local_coder is registered and bound in KarmoOperator.__init__
    since a coding question is plain text with no client-surface gap."""
    operator = KarmoOperator(model_client=object(), task_store=None)
    record = operator.registry.get(ASK_LOCAL_CODER_TOOL, ASK_LOCAL_CODER_TOOL_VERSION)
    assert record is not None
    assert record.computed_approval_requirement == ApprovalRequirement.NONE
