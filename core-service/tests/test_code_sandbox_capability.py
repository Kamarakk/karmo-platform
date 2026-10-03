"""Tests for KARMO's code sandbox flow: get the code, run it on Worker02,
send failures back for a fix, show code and output."""

from __future__ import annotations

import pytest

from core_service import ask_claude_capability
from core_service.code_sandbox_capability import code_in, is_run_request
from core_service.operator import KarmoOperator
from core_service.worker_dispatch import DispatchOutcome


class SandboxDispatch:
    """Worker dispatch double: code_run returns queued results; model_chat
    (the local coder on Worker01) returns queued answers."""

    def __init__(self, runs, coder=()):
        self.available = True
        self.calls = []
        self._runs = list(runs)
        self._coder = list(coder)

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["tool_id"] == "code_run":
            return DispatchOutcome(outcome="SUCCEEDED", job_id="j", elapsed_seconds=1, poll_count=1,
                                   result=self._runs.pop(0))
        return DispatchOutcome(outcome="SUCCEEDED", job_id="j", elapsed_seconds=1, poll_count=1,
                               result={"response": self._coder.pop(0)})


OK = {"exit_code": 0, "stdout": "7\n", "stderr": "", "timed_out": False, "seconds": 1.2}
FAIL = {"exit_code": 1, "stdout": "", "stderr": "NameError: name 'x' is not defined", "timed_out": False}


class NoModel:
    def chat_with_tools(self, **kwargs):
        raise AssertionError("the chat model is not used for a code run")


@pytest.mark.parametrize("text", [
    "write and run a script that adds 3 and 4",
    "calculate the compound interest on $1000 at 5% for 10 years using python",
    "use python to count the days until Christmas",
    "run this:\n```python\nprint(3+4)\n```",
])
def test_run_requests_are_recognised(text):
    assert is_run_request(text)


@pytest.mark.parametrize("text", ["write a python function to sort a list", "how do I run faster",
                                  "what's a python", "run the numbers on my sales"])
def test_other_messages_are_not(text):
    assert not is_run_request(text)


def test_pasted_code_runs_as_is_on_worker02():
    dispatch = SandboxDispatch([OK])
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch).handle(
        "run this:\n```python\nprint(3+4)\n```")
    run = dispatch.calls[0]
    assert run["tool_id"] == "code_run" and run["worker_id"] == "KARMO-WORKER02"
    assert run["arguments"] == {"code": "print(3+4)"}
    assert "code by you" in response["message"] and "7" in response["message"]


def test_the_local_coder_writes_and_fixes_when_handoff_is_off(tmp_path):
    dispatch = SandboxDispatch([FAIL, OK], coder=["```python\nprint(x)\n```", "```python\nprint(3+4)\n```"])
    operator = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch,
                             handoff_enabled_file=str(tmp_path / "off"))
    response = operator.handle("write and run a script that adds 3 and 4")

    tools = [c["tool_id"] for c in dispatch.calls]
    assert tools == ["model_chat", "code_run", "model_chat", "code_run"]
    assert "NameError" in dispatch.calls[2]["arguments"]["prompt"]
    assert "KARMO's local coder, 2 tries" in response["message"]
    assert "print(3+4)" in response["message"] and "7" in response["message"]


def test_claude_writes_the_code_when_handoff_is_on(tmp_path, monkeypatch):
    enabled = tmp_path / "on"
    enabled.write_text("")
    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli",
                        lambda question, **kw: "Here:\n```python\nprint(sum([3, 4]))\n```")
    dispatch = SandboxDispatch([OK])
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch,
                             handoff_enabled_file=str(enabled)).handle("use python to add 3 and 4 for KARMO test")
    assert dispatch.calls[0]["arguments"] == {"code": "print(sum([3, 4]))"}
    assert "code by Claude" in response["message"]


def test_runs_stop_after_three_tries():
    coder = ["```python\nprint(x)\n```"] * 3
    dispatch = SandboxDispatch([FAIL, FAIL, FAIL], coder=coder)
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch).handle(
        "write and run a script that adds 3 and 4")
    assert [c["tool_id"] for c in dispatch.calls].count("code_run") == 3
    assert "It still failed" in response["message"]


def test_a_sandbox_outage_is_reported():
    dispatch = SandboxDispatch([])
    dispatch.available = False
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch).handle(
        "run this:\n```python\nprint(1)\n```")
    assert "It didn't run:" in response["message"]


def test_code_in_reads_the_first_python_block():
    assert code_in("x\n```python\nprint(1)\n```\n```python\nprint(2)\n```") == "print(1)"
    assert code_in("no code here") is None
