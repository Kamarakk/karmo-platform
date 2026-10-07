"""Model-chosen routing while the iMac answers; keyword rules otherwise."""

from __future__ import annotations

import pytest
from core_service.intent_router import ROUTES, classify, fast_client, parse_route
from core_service.operator import KarmoOperator


class RouterModel:
    def __init__(self, reply="chat", fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    def chat(self, *, model, messages, temperature=0.2, timeout=None):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("down")
        return self.reply


class BrainClient:
    """Stands in for FailoverOllamaClient: a router-capable primary plus the
    chat_with_tools the operator's answer path uses."""

    def __init__(self, route="chat", up=True, answer="answer"):
        self.primary = RouterModel(route)
        self.up, self.answer, self.requests = up, answer, []

    def primary_available(self):
        return self.up

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None, on_token=None):
        self.requests.append({"messages": list(messages), "tools": [t["function"]["name"] for t in tools]})
        return {"content": self.answer, "tool_calls": None}


def _tool_calls(messages):
    return [c["function"]["name"] for m in messages for c in (m.get("tool_calls") or [])]


@pytest.mark.parametrize("reply,expected", [
    ("bloomboss", "bloomboss"), ("  Web.", "web"), ("-> run_code", "run_code"), ("route: chat", "chat"),
    ("chat or web", None), ("I think this is about plants", None), ("", None), ("delete", None),
])
def test_parse_route_accepts_only_one_known_route(reply, expected):
    assert parse_route(reply) == expected


def test_every_route_is_named_in_the_prompt():
    from core_service.intent_router import ROUTER_PROMPT
    for route in ROUTES:
        assert f"\n{route}:" in ROUTER_PROMPT


def test_classify_returns_none_when_the_model_fails():
    assert classify(RouterModel(fail=True), "hello there") is None


def test_previous_question_is_passed_for_follow_ups():
    model = RouterModel("bloomboss")
    classify(model, "and the albos?", "how are my anthuriums selling?")
    assert "how are my anthuriums selling?" in model.calls[0][1]["content"]


def test_fast_client_only_while_the_imac_answers():
    assert fast_client(object()) is None
    brain = BrainClient(up=False)
    assert fast_client(brain) is None
    brain.up = True
    assert fast_client(brain) is brain.primary


def test_plant_care_routed_to_chat_gets_no_bloomboss_figures():
    client = BrainClient(route="chat")
    response = KarmoOperator(model_client=client).handle("What humidity does a variegated Alocasia need?")
    assert response["message"] == "answer"
    assert _tool_calls(client.requests[0]["messages"]) == []
    assert "bloomboss_report" not in client.requests[0]["tools"]


def test_bloomboss_route_puts_real_figures_in_front_of_the_model():
    client = BrainClient(route="bloomboss")
    KarmoOperator(model_client=client).handle("which plants made me money?")
    first = client.requests[0]["messages"]
    assert _tool_calls(first) == ["bloomboss_report"]
    assert any("emgarden_invoice_2026040040.csv" in m["content"] for m in first if m["role"] == "tool")


def test_bloomboss_route_answers_from_data_without_the_small_phrasing_model():
    client = BrainClient(route="bloomboss")
    response = KarmoOperator(model_client=client).handle("which plants made me money?")
    assert response["model"] == "qwen3:8b"


def test_change_route_is_refused_without_a_model_answer():
    client = BrainClient(route="change")
    response = KarmoOperator(model_client=client).handle("turn off the search thing on the second worker")
    assert response["kind"] == "refusal"
    assert client.requests == []


def test_how_to_question_with_a_change_verb_is_answered_when_routed_to_chat():
    client = BrainClient(route="chat")
    response = KarmoOperator(model_client=client).handle("How do I restart my home router?")
    assert response["kind"] == "chat"


def test_tasks_tool_offered_only_on_the_tasks_route():
    client = BrainClient(route="code_help")
    KarmoOperator(model_client=client).handle("write me a function that lists my tasks")
    assert "ask_local_coder" in client.requests[0]["tools"]
    assert "list_tasks" not in client.requests[0]["tools"]


def test_unusable_router_reply_falls_back_to_keyword_rules():
    client = BrainClient(route="no idea")
    KarmoOperator(model_client=client).handle("how many plants did we sell?")
    assert _tool_calls(client.requests[0]["messages"]) == ["bloomboss_report"]


def test_imac_down_uses_keyword_rules_and_never_asks_the_router():
    client = BrainClient(route="chat", up=False)
    KarmoOperator(model_client=client).handle("how many plants did we sell?")
    assert client.primary.calls == []
    assert _tool_calls(client.requests[0]["messages"]) == ["bloomboss_report"]
