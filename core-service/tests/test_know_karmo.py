"""KARMO knowing Kamara (2026-10-03 review): his profile and remembered facts
reach the model, his memory commands work without a model, and ordinary
questions are no longer hijacked by the refusal, status or BloomBoss
keyword shortcuts."""

from __future__ import annotations

import pytest

import core_service.operator as operator_module
from core_service.durable_memory import MemoryContext, MemoryConfigurationError, NullMemoryBackend
from core_service.identity import MAX_OWNER_PROFILE_CHARS, load_owner_profile
from core_service.operator import KarmoOperator, _is_bloomboss_question


class FakeModelClient:
    def __init__(self):
        self.calls = []

    def chat(self, *, model, messages, temperature=0.2):
        self.calls.append(messages)
        return "ok"

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
        return {"content": self.chat(model=model, messages=messages, temperature=temperature), "tool_calls": None}


class FactMemory:
    status = "ACTIVE"

    def __init__(self, facts=()):
        self.facts = dict(facts)
        self.next_id = max(self.facts, default=0) + 1

    def build_context(self, _query):
        return MemoryContext(recent=(), semantic=(), documents=())

    def remember_exchange(self, _prompt, _answer):
        return None

    def owner_facts(self, limit=50):
        return tuple(sorted(self.facts.items()))

    def remember_fact(self, fact):
        fact_id, self.next_id = self.next_id, self.next_id + 1
        self.facts[fact_id] = fact
        return fact_id

    def forget_fact(self, fact_id):
        return self.facts.pop(fact_id, None) is not None


def _status(_args=None):
    return {"mode": "READ_ONLY"}


@pytest.fixture
def no_profile(monkeypatch):
    monkeypatch.setattr(operator_module, "load_owner_profile", lambda: "")


def test_load_owner_profile_missing_file_is_empty(tmp_path):
    assert load_owner_profile(str(tmp_path / "missing.md")) == ""


def test_load_owner_profile_is_bounded(tmp_path):
    path = tmp_path / "profile.md"
    path.write_text("x" * (MAX_OWNER_PROFILE_CHARS * 2), encoding="utf-8")
    assert len(load_owner_profile(str(path))) == MAX_OWNER_PROFILE_CHARS


def test_profile_and_facts_reach_the_system_prompt(monkeypatch):
    monkeypatch.setattr(operator_module, "load_owner_profile", lambda: "Children: Tamara, Kith, Karii, Karmo Jr.")
    client = FakeModelClient()
    operator = KarmoOperator(model_client=client, memory_backend=FactMemory({1: "Kith's soccer is on Tuesdays"}))

    operator.handle("What are my kids' names?")

    system_prompt = client.calls[0][0]["content"]
    assert "ABOUT KAMARA (written by Kamara):\nChildren: Tamara, Kith, Karii, Karmo Jr." in system_prompt
    assert "FACTS KAMARA ASKED YOU TO REMEMBER:\n- Kith's soccer is on Tuesdays" in system_prompt


def test_facts_read_failure_does_not_break_chat(no_profile):
    class BrokenFacts(FactMemory):
        def owner_facts(self, limit=50):
            raise RuntimeError("db down")

    client = FakeModelClient()
    response = KarmoOperator(model_client=client, memory_backend=BrokenFacts()).handle("hello Karmo")

    assert response["message"] == "ok"
    assert "FACTS KAMARA ASKED YOU TO REMEMBER" not in client.calls[0][0]["content"]


def test_remember_list_and_forget_commands_need_no_model(no_profile):
    client = FakeModelClient()
    memory = FactMemory()
    operator = KarmoOperator(model_client=client, memory_backend=memory)

    stored = operator.handle("Remember that Kith's soccer practice is on Tuesdays.")
    listed = operator.handle("list my facts")
    forgotten = operator.handle("forget fact 1")
    missing = operator.handle("forget #1")

    assert "Kith's soccer practice is on Tuesdays" in stored["message"]
    assert "fact #1" in stored["message"]
    assert "#1: Kith's soccer practice is on Tuesdays" in listed["message"]
    assert forgotten["message"] == "Forgotten: fact #1."
    assert missing["message"] == "I don't have a fact #1."
    assert memory.facts == {}
    assert client.calls == []


def test_remember_question_goes_to_the_model(no_profile):
    client = FakeModelClient()
    memory = FactMemory()

    KarmoOperator(model_client=client, memory_backend=memory).handle("remember when we fixed the mic?")

    assert memory.facts == {}
    assert len(client.calls) == 1


def test_remember_without_configured_memory_says_nothing_changed(no_profile):
    operator = KarmoOperator(model_client=FakeModelClient(), memory_backend=NullMemoryBackend())

    response = operator.handle("remember that the tent light runs 14 hours")

    assert "Nothing was changed" in response["message"]
    assert response["error"] == MemoryConfigurationError.__name__


@pytest.mark.parametrize(
    "text",
    [
        "Should I upgrade my iPhone?",
        "How do I kill weeds in my yard?",
        "Can you merge these two lists?",
        "How do I enable dark mode on Windows?",
        "What is the status of my Amazon order?",
        "Any health tips for running?",
        "Is Palmstreet online right now?",
        "How much RAM should I buy for a Mac mini?",
    ],
)
def test_ordinary_questions_reach_chat(no_profile, text):
    operator = KarmoOperator(model_client=FakeModelClient(), memory_backend=FactMemory(), status_reader=_status)

    assert operator.handle(text)["kind"] == "chat"


@pytest.mark.parametrize(
    "text",
    [
        "How is the stock market doing today?",
        "What sold out at Costco?",
        "How much profit does Apple make?",
        "Help me write an email to a vendor about invoices",
    ],
)
def test_generic_business_words_are_not_bloomboss(text):
    assert not _is_bloomboss_question(text)


@pytest.mark.parametrize(
    "text",
    [
        "What were my sales last month?",
        "How many Alocasia did I sell?",
        "How much did we sell this week?",
        "how is bloomboss doing",
        "which plants are my best sellers",
    ],
)
def test_own_business_questions_are_still_bloomboss(text):
    assert _is_bloomboss_question(text)


@pytest.mark.parametrize(
    "text",
    [
        "What humidity does a variegated alocasia need?",
        "How often should I water my Alocasia?",
        "Why are my monstera leaves turning yellow?",
        "Best soil for anthuriums",
    ],
)
def test_plant_care_questions_are_not_bloomboss(text):
    assert not _is_bloomboss_question(text)


@pytest.mark.parametrize(
    "text",
    ["How much stock of the Alocasia do I have?", "Does bloomboss care about humidity sales?"],
)
def test_care_words_with_business_words_are_still_bloomboss(text):
    assert _is_bloomboss_question(text)
