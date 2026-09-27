"""BloomBoss questions get real BloomBoss data whether or not the model
chooses to call the tool (live finding 2026-09-27: qwen3:8b told Kamara to
"use the bloomboss_report tool" instead of calling it)."""

from __future__ import annotations

import pytest

from core_service.bloomboss_capability import known_cultivar_names
from core_service.operator import KarmoOperator


class ScriptedClient:
    """Returns the scripted answers in order (repeating the last), never
    proposing a tool call; records every request's messages."""

    def __init__(self, *answers):
        self.answers = list(answers) or ["ok"]
        self.requests = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.requests.append(list(messages))
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return {"content": self.answers[index], "tool_calls": None}


def _tool_results(messages):
    return [m["content"] for m in messages if m["role"] == "tool"]


def test_imported_cultivar_names_are_known():
    assert "ninja albo" in known_cultivar_names()


@pytest.mark.parametrize(
    "text",
    [
        "how are the Ninja Albos doing?",
        "how many plants did we sell?",
        "what's my profit so far?",
        "what does bloomboss say about suppliers?",
    ],
)
def test_bloomboss_question_gets_real_report_before_the_model_answers(text):
    client = ScriptedClient("answer")
    response = KarmoOperator(model_client=client).handle(text)

    first = client.requests[0]
    calls = [c["function"]["name"] for m in first for c in (m.get("tool_calls") or [])]
    assert calls == ["bloomboss_report"]
    results = _tool_results(first)
    assert len(results) == 1
    assert not results[0].startswith('{"error"')
    assert "emgarden_invoice_2026040040.csv" in results[0]
    assert response["message"] == "answer"
    assert len(client.requests) == 1


def test_non_business_question_is_not_prefetched():
    client = ScriptedClient("hi")
    KarmoOperator(model_client=client).handle("tell me a joke about clouds")

    assert _tool_results(client.requests[0]) == []


def test_answer_that_names_the_tool_instead_of_calling_it_runs_the_tool_and_asks_again():
    client = ScriptedClient("Please use the bloomboss_report tool for that.", "Real answer from data.")
    response = KarmoOperator(model_client=client).handle("tell me something interesting")

    assert len(client.requests) == 2
    assert any("emgarden_invoice_2026040040.csv" in r for r in _tool_results(client.requests[1]))
    assert response["message"] == "Real answer from data."


def test_naming_the_tool_again_after_it_ran_does_not_loop():
    client = ScriptedClient("Please use the bloomboss_report tool.")
    KarmoOperator(model_client=client).handle("tell me something interesting")

    assert len(client.requests) == 2


def test_prerun_report_is_a_short_digest_of_the_named_cultivar():
    """Live measurement (2026-09-27): the 6000-char report took 2.5-3 minutes
    of prompt reading on karmo-ai01's CPU. The model now gets a few lines."""
    client = ScriptedClient("answer")
    KarmoOperator(model_client=client).handle("how are the Ninja Albos doing?")

    digest = _tool_results(client.requests[0])[0]
    assert len(digest) < 1000
    assert "- Ninja Albo: 10 units, 1 sold, 0 lost, revenue $350, profit $250.91, margin 72%" in digest
    assert "Melo Albo" not in digest


def test_digest_lists_every_cultivar_when_none_is_named():
    client = ScriptedClient("answer")
    KarmoOperator(model_client=client).handle("what should I restock for BloomBoss?")

    digest = _tool_results(client.requests[0])[0]
    assert "Totals: 75 units, 5 sold, revenue $1090" in digest
    assert "- Melo Albo: 5 units, 0 sold" in digest
    assert len(digest) < 2000
