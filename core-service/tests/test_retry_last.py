"""'Answer my last question' re-runs the previous question through KARMO's
normal routing instead of letting the chat model guess."""

from __future__ import annotations

import pytest

from core_service.operator import KarmoOperator
from core_service.worker_dispatch import DispatchOutcome


class Memory:
    def __init__(self, turns):
        self.turns = list(turns)
        self.saved = []

    def recent_turns(self):
        return tuple(self.turns)

    def build_context(self, _query):
        raise AssertionError("retry reads recent turns only")

    def remember_exchange(self, prompt, answer):
        self.saved.append((prompt, answer))


class Sandbox:
    available = True

    def __init__(self):
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return DispatchOutcome(outcome="SUCCEEDED", job_id="j", elapsed_seconds=1, poll_count=1,
                               result={"exit_code": 0, "stdout": "80\n", "stderr": "", "timed_out": False})


class NoModel:
    def chat_with_tools(self, **kwargs):
        raise AssertionError("the chat model is not asked")


@pytest.mark.parametrize("text", ["Answer my last question", "try again", "redo that"])
def test_retry_reruns_the_previous_question(text):
    memory = Memory([("user", "run this:\n```python\nprint(80)\n```"), ("assistant", "...")])
    sandbox = Sandbox()
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=sandbox,
                             memory_backend=memory).handle(text)
    assert sandbox.calls[0]["tool_id"] == "code_run"
    assert "80" in response["message"]


def test_retry_skips_earlier_retries_and_says_so_when_nothing_is_left():
    memory = Memory([("user", "try again"), ("assistant", "x")])
    response = KarmoOperator(model_client=NoModel(), memory_backend=memory).handle("answer my last question")
    assert "ask it again" in response["message"]
