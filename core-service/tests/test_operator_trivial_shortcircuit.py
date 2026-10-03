"""Tests for the trivial-message short-circuit (2026-09-20): a pure
greeting or acknowledgment should never reach the local model at all --
measured live, loading qwen3:8b for even a zero-tool request still costs
~6.2GB RAM and ~30-40 seconds on karmo-ai01.

Deliberately full-message match only. This project has twice shipped a
real bug from a substring keyword match (_STATUS_WORDS catching "memory"
inside unrelated text; "deploy" inside a canary phrase refused as a
write-intent request) -- the negative tests below directly guard against
that same failure class here.
"""

from __future__ import annotations

from core_service.operator import KarmoOperator


class NeverCalledModelClient:
    """Raises if the model is ever actually invoked -- proves the
    short-circuit really skips the model, not just returns fast."""

    def __init__(self):
        self.calls = []

    def chat(self, *, model, messages, temperature=0.2):
        self.calls.append(model)
        raise AssertionError("model should never be called for a trivial message")

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.calls.append(model)
        raise AssertionError("model should never be called for a trivial message")


class ToolCallingRecordingClient:
    """Records every real chat_with_tools call, for the negative tests
    proving a non-trivial message still reaches the model."""

    def __init__(self):
        self.calls = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.calls.append(model)
        return {"content": "a real answer", "tool_calls": None}


def test_pure_greetings_short_circuit_without_calling_the_model():
    client = NeverCalledModelClient()
    operator = KarmoOperator(model_client=client)

    for message in ["hi", "Hello", "HEY", "Good Afternoon!", "yo", "howdy"]:
        response = operator.handle(message)
        assert response["kind"] == "chat"
        assert response["model"] is None
        assert "help" in response["message"].lower()

    assert client.calls == []


def test_greeting_plus_how_are_you_short_circuits():
    client = NeverCalledModelClient()
    operator = KarmoOperator(model_client=client)

    for message in [
        "good afternoon, how are you?",
        "good morning how are you doing",
        "hey, what's up",
        "hello, hows it going",
    ]:
        response = operator.handle(message)
        assert response["kind"] == "chat"
        assert response["model"] is None

    assert client.calls == []


def test_pure_acknowledgments_short_circuit_without_calling_the_model():
    client = NeverCalledModelClient()
    operator = KarmoOperator(model_client=client)

    for message in ["thanks", "Thank you.", "ok", "cool!", "got it", "sounds good", "bye"]:
        response = operator.handle(message)
        assert response["kind"] == "chat"
        assert response["model"] is None
        assert response["message"]

    assert client.calls == []


def test_greeting_with_real_content_does_not_short_circuit():
    """The critical negative test: a message that merely contains a
    trivial word alongside a real request must still reach the model,
    exactly like every other real question. This is a full-message
    match, not a substring match, by design."""
    client = ToolCallingRecordingClient()
    operator = KarmoOperator(model_client=client)

    response = operator.handle("hi, what tasks are open right now?")

    assert response["kind"] == "chat"
    assert client.calls == ["qwen3:8b"]


def test_ordinary_question_is_unaffected():
    client = ToolCallingRecordingClient()
    operator = KarmoOperator(model_client=client)

    response = operator.handle("what does bloomboss say about last month's sales?")

    assert response["kind"] == "chat"
    # 2026-09-29 Stage 3: BloomBoss figures are fetched up front, so the
    # phrasing model answers (see test_operator_phrasing_model.py).
    assert client.calls == ["llama3.2:3b"]


def test_write_words_still_take_priority_check_order_is_safe():
    """Sanity check that adding the trivial short-circuit ahead of the
    write-word refusal didn't accidentally swallow a real write request
    that happens to also look conversational."""
    client = NeverCalledModelClient()
    operator = KarmoOperator(model_client=client)

    response = operator.handle("please restart the worker service")

    assert response["kind"] == "refusal"
    assert client.calls == []
