from __future__ import annotations

import pytest

from core_service.operator import KarmoOperator


class FakeModelClient:
    def chat(self, *, model, messages, temperature=0.2):
        return "ok"

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2):
        return {"content": self.chat(model=model, messages=messages, temperature=temperature), "tool_calls": None}


def _status(_args=None):
    return {"mode": "READ_ONLY"}


@pytest.mark.parametrize(
    "text",
    [
        "can you write me a short poem about my garden",
        "let's start over, I misspoke",
        "please stop for a second, I have a question",
        "remove the word 'very' from this sentence for me",
        "I want to change my mind about something",
        "create a list of plant names for me",
        "give me an update on how you're doing",
        "can you patch together a summary of this",
        "please recall this exact phrase for later: pr43-deploy-canary-final",
        "can you help me install confidence in my public speaking",
        "delete this thought, it's not important",
        "my disk of pasta salad is empty, can you remind me to buy more",
        "the host of the party asked me a question",
        "I'm running late today",
        "the service at that restaurant was great",
        "my healthy breakfast this morning was oatmeal",
        "what's my container garden looking like this week",
        "please recall this exact phrase for later: durable-memory-canary-2026-09-15",
    ],
)
def test_common_english_phrases_reach_chat_not_refusal_or_status(text):
    """Real phrases found to false-positive before this fix (see
    KARMO_DEVELOPER_NOTES.md 2026-09-15). None of these express any
    actual intent to change/inspect KARMO-operational state; all must
    reach ordinary chat.
    """
    operator = KarmoOperator(model_client=FakeModelClient(), status_reader=_status)

    response = operator.handle(text)

    assert response["kind"] == "chat"


@pytest.mark.parametrize(
    "text",
    [
        "restart the worker service",
        "please reboot karmo-ai01",
        "enable the new capability",
        "disable that feature",
        "uninstall the old package",
        "modify the config file",
        "upgrade the model stack",
        "kill the hung process",
        "terminate that job",
        "merge the pending branch",
    ],
)
def test_genuine_write_intent_is_still_refused(text):
    operator = KarmoOperator(model_client=FakeModelClient(), status_reader=_status)

    response = operator.handle(text)

    assert response["kind"] == "refusal"


@pytest.mark.parametrize(
    "text",
    [
        "show KarmoLab status",
        "what's the system health",
        "check cpu and ram usage",
        "list running services",
        "is docker healthy",
        "show me the containers",
        "are you online",
    ],
)
def test_genuine_status_intent_is_still_dispatched(text):
    operator = KarmoOperator(model_client=FakeModelClient(), status_reader=_status)

    response = operator.handle(text)

    assert response["kind"] == "karmolab_read"
