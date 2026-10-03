"""Tests for KARMO handing questions to Claude/GPT on its own."""

from __future__ import annotations

import uuid

import pytest

from core_service import ask_claude_capability, ask_gpt_capability
from core_service.handoff import is_heavy_task
from core_service.operator import KarmoOperator


class RecordingClient:
    def __init__(self, answer="local answer"):
        self.calls = 0
        self._answer = answer

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.calls += 1
        return {"content": self._answer, "tool_calls": None}


class FailingClient(RecordingClient):
    def chat_with_tools(self, **kwargs):
        from core_service.ollama_client import OllamaClientError
        self.calls += 1
        raise OllamaClientError("model unavailable")


@pytest.fixture
def enabled(tmp_path):
    path = tmp_path / "handoff.enabled"
    path.write_text("")
    return str(path)


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake_claude(question, **kwargs):
        calls.append(("claude", question))
        return "Claude's answer"

    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", fake_claude)
    monkeypatch.setattr(ask_gpt_capability, "_invoke_codex_cli",
                        lambda question: calls.append(("gpt", question)) or "GPT's answer")
    return calls


@pytest.mark.parametrize("text", [
    "write me a short email to my landlord about the leak",
    "draft a caption for my begonia post",
    "make a marketing plan for the plant shop",
    "compare a Mac mini and a used GPU for running local models",
    "explain how DNS works step by step",
    "x " * 250,
])
def test_heavy_tasks_are_recognised(text):
    assert is_heavy_task(text)


@pytest.mark.parametrize("text", ["how are you", "what's 2+2", "who are my kids", "write that down"])
def test_light_questions_stay_local(text):
    assert not is_heavy_task(text)


def test_a_heavy_task_goes_to_claude_with_only_the_question(enabled, sent):
    question = f"write me a short email to my landlord {uuid.uuid4().hex}"
    client = RecordingClient()
    response = KarmoOperator(model_client=client, handoff_enabled_file=enabled).handle(question)

    assert sent == [("claude", question)]
    assert client.calls == 0
    assert response["message"] == "Claude's answer\n(asked Claude)"
    assert response["model"] == "claude (subscription)"


def test_gpt_is_asked_when_claude_fails(enabled, sent, monkeypatch):
    def broken(question, **kwargs):
        raise ask_claude_capability.AskClaudeCapabilityError("not logged in")

    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", broken)
    question = f"draft a caption for my post {uuid.uuid4().hex}"
    response = KarmoOperator(model_client=RecordingClient(), handoff_enabled_file=enabled).handle(question)
    assert response["message"] == "GPT's answer\n(asked GPT)"


def test_a_failed_local_answer_gets_a_second_try_with_claude(enabled, sent):
    question = f"who painted the mona lisa {uuid.uuid4().hex}"
    response = KarmoOperator(model_client=FailingClient(), handoff_enabled_file=enabled).handle(question)
    assert sent == [("claude", question)]
    assert response["message"].endswith("(asked Claude)")


def test_nothing_is_handed_off_without_the_enable_file(tmp_path, sent):
    client = RecordingClient()
    response = KarmoOperator(model_client=client, handoff_enabled_file=str(tmp_path / "missing")).handle(
        "write me a short email to my landlord"
    )
    assert sent == [] and client.calls == 1 and response["message"] == "local answer"


def test_bloomboss_and_search_questions_are_never_handed_off(enabled, sent):
    operator = KarmoOperator(model_client=RecordingClient(), handoff_enabled_file=enabled)
    operator.handle("write a summary of my plant sales this month")
    operator.handle("search for a marketing plan template")
    assert sent == []
