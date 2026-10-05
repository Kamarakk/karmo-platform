"""Tests for web search: when a question is sent to the worker, what the
model reads back, and the sources line under the answer."""

from __future__ import annotations

import pytest

from core_service.operator import KarmoOperator
from core_service.web_search_capability import (
    is_search_question,
    search_query,
    sources_line,
    wants_the_web,
    web_results_digest,
)
from core_service.worker_dispatch import DispatchOutcome

RESULTS = {"results": [
    {"title": "Alocasia Ninja Albo listings", "url": "https://www.example.com/albo", "snippet": "From $45 to $70."},
    {"title": "Plant forum", "url": "https://forum.plants.org/t/1", "snippet": ""},
    {"title": "Same site again", "url": "https://example.com/other", "snippet": "x"},
]}


class FakeWorkerDispatchClient:
    def __init__(self, *, available=True, outcome=None):
        self.available = available
        self._outcome = outcome
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return self._outcome


class RecordingClient:
    def __init__(self, answer="Listings run $45 to $70."):
        self.requests = []
        self._answer = answer

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        self.requests.append({"model": model, "messages": messages, "tools": tools})
        return {"content": self._answer, "tool_calls": None}


def _succeeded(result=RESULTS):
    return FakeWorkerDispatchClient(outcome=DispatchOutcome(
        outcome="SUCCEEDED", job_id="job-1", elapsed_seconds=3.0, poll_count=1, result=result,
    ))


@pytest.mark.parametrize("text", [
    "search for ninja albo prices", "what's the latest news on the election", "look up begonia care",
    "how much is a Ninja Albo online", "what's the weather this week", "price of bitcoin",
])
def test_search_questions_are_recognised(text):
    assert is_search_question(text)


@pytest.mark.parametrize("text", [
    "how are you", "what are my sales this month", "remember that I like tea", "tell me about my kids",
    "what tasks are open right now?", "what's on today's list",
])
def test_ordinary_questions_are_not_searched(text):
    assert not is_search_question(text)


def test_search_query_drops_the_lead_in():
    assert search_query("KARMO, can you search the web for ninja albo prices?") == "ninja albo prices"
    assert search_query("look up begonia care") == "begonia care"
    assert search_query("what's the latest news") == "what's the latest news"
    assert len(search_query("q" * 500)) == 300


def test_digest_and_sources():
    digest = web_results_digest(RESULTS)
    assert "[1] Alocasia Ninja Albo listings -- https://www.example.com/albo" in digest
    assert "From $45 to $70." in digest
    assert web_results_digest({"results": []}) == "WEB SEARCH: no results found."
    assert sources_line(RESULTS) == "Sources: example.com, forum.plants.org"
    assert sources_line({"results": []}) == ""


def test_a_search_question_runs_on_worker02_first_and_the_answer_names_sources():
    dispatch = _succeeded()
    client = RecordingClient()
    operator = KarmoOperator(model_client=client, worker_dispatch_client=dispatch)

    response = operator.handle("search for ninja albo prices")

    assert dispatch.calls[0]["tool_id"] == "web_search"
    assert dispatch.calls[0]["worker_id"] == "KARMO-WORKER02"
    assert dispatch.calls[0]["arguments"] == {"query": "ninja albo prices"}
    first = client.requests[0]
    assert first["tools"] == []
    assert any(m["role"] == "tool" and "From $45 to $70." in m["content"] for m in first["messages"])
    assert response["message"] == "Listings run $45 to $70.\nSources: example.com, forum.plants.org"


def test_explicit_web_words_beat_bloomboss_but_own_sales_stay_local():
    dispatch = _succeeded()
    operator = KarmoOperator(model_client=RecordingClient(), worker_dispatch_client=dispatch)

    operator.handle("how much is a ninja albo online")
    assert [c["tool_id"] for c in dispatch.calls] == ["web_search"]

    operator.handle("how much is a ninja albo")
    assert [c["tool_id"] for c in dispatch.calls] == ["web_search"]


def test_search_failure_is_told_to_the_model_and_adds_no_sources():
    dispatch = FakeWorkerDispatchClient(available=False)
    client = RecordingClient("I couldn't search the web just now.")
    response = KarmoOperator(model_client=client, worker_dispatch_client=dispatch).handle("latest news")

    tool_messages = [m for m in client.requests[0]["messages"] if m["role"] == "tool"]
    assert "worker dispatch is not activated" in tool_messages[0]["content"]
    assert response["message"] == "I couldn't search the web just now."
