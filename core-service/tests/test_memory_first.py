"""Facts Kamara saved answer his questions before routing (live miss 2026-10-11)."""

from __future__ import annotations

from core_service.durable_memory import NullMemoryBackend
from core_service.operator import KarmoOperator, _fact_words

ARISA = ("Arisa's Aug 30 shipment was 5 boxes; box WBOX#2 60x32x26, cargo $228 plus UPS. "
         "I asked Arisa to keep my balance as credit for the next order.")


class FactMemory(NullMemoryBackend):
    status = "ACTIVE"

    def owner_facts(self, limit=50):
        return ((3, ARISA), (4, "My dog's name is Rex."))


class RouterModel:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, *, model, messages, temperature=0.2, timeout=None):
        return self.reply


class BrainClient:
    def __init__(self, route):
        self.primary, self.requests = RouterModel(route), []

    def primary_available(self):
        return True

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None, on_token=None):
        self.requests.append({"messages": list(messages), "tools": [t["function"]["name"] for t in tools]})
        return {"content": "5 boxes, cargo $228 plus UPS.", "tool_calls": None}


def test_a_saved_fact_beats_a_web_route():
    client = BrainClient("web")
    KarmoOperator(model_client=client, memory_backend=FactMemory()).handle(
        "What do you know about Arisa's Aug 30 shipment?")
    request = client.requests[0]
    assert "web_search" not in request["tools"]
    assert not any(m.get("role") == "tool" for m in request["messages"])
    system = request["messages"][0]["content"]
    assert "FACTS KAMARA TOLD YOU THAT ANSWER THIS QUESTION" in system
    assert "WBOX#2" in system.split("FACTS KAMARA TOLD YOU THAT ANSWER THIS QUESTION")[1]


def test_unrelated_question_gets_no_matched_facts_block():
    client = BrainClient("chat")
    KarmoOperator(model_client=client, memory_backend=FactMemory()).handle("How does a VLAN work?")
    assert "THAT ANSWER THIS QUESTION" not in client.requests[0]["messages"][0]["content"]


def test_fact_words_drop_filler_and_keep_names_and_numbers():
    assert _fact_words("What do you know about Arisa's Aug 30 shipment?") == {"arisa", "aug", "30", "shipment"}
