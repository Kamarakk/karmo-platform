"""Kamara's "good morning" brief: real readings only, no model call."""

from __future__ import annotations

from datetime import datetime

import pytest

from core_service.morning_brief import build_morning_brief, is_morning_brief_request
from core_service.operator import KarmoOperator

GIB = 1024 ** 3


class NoModelClient:
    def chat(self, **_kwargs):
        raise AssertionError("the brief must not call a model")

    def chat_with_tools(self, **_kwargs):
        raise AssertionError("the brief must not call a model")


class FactMemory:
    status = "ACTIVE"

    def build_context(self, _query):
        raise AssertionError("not used")

    def remember_exchange(self, *_args):
        return None

    def owner_facts(self, limit=50):
        return ((1, "trash goes out Thursday"), (2, "tent light runs 14 hours"))


STATUS = {
    "host": {"load_average": (0.42, 0.3, 0.2)},
    "memory": {"available": True, "total_bytes": 11 * GIB, "available_bytes": 4 * GIB},
    "disk": {"total_bytes": 100, "free_bytes": 40},
    "services": {
        "karmo-core.service": {"available": True, "state": "active"},
        "karmo-worker.service": {"available": True, "state": "failed"},
    },
    "containers": {"containers": [{"name": "karmo-ollama", "status": "Up 2 days"}, {"name": "x", "status": "Exited"}]},
}


@pytest.mark.parametrize(
    "text", ["good morning", "Good morning, Karmo!", "morning", "brief me", "daily briefing", "catch me up"]
)
def test_brief_requests_are_recognized(text):
    assert is_morning_brief_request(text)


@pytest.mark.parametrize("text", ["good morning, what should I focus on today?", "brief me on Alocasia care"])
def test_questions_that_start_like_a_greeting_are_not_briefs(text):
    assert not is_morning_brief_request(text)


def test_brief_uses_only_real_readings():
    brief = build_morning_brief(
        local_now=datetime(2026, 10, 3, 6, 5),
        status=STATUS,
        bloomboss={"reports": [{"business_summary": {
            "unit_count": 75, "sale_count": 5, "total_revenue": 1090, "active_inventory_units": 70,
        }}]},
        open_tasks=2,
        facts=((1, "trash goes out Thursday"),),
    )

    assert brief.splitlines() == [
        "Good morning, Karmo. It's Saturday, October 3, 6:05 AM.",
        "Lab: 4.0 of 11.0 GB memory free; disk 60% used; load 0.42; FAILED: karmo-worker.service; 1 containers running.",
        "BloomBoss: 75 units on record, 5 sold ($1,090.00 revenue), 70 still in inventory.",
        "KARMO tasks: 2 open.",
        "You asked me to remember: trash goes out Thursday.",
    ]


def test_missing_sources_just_drop_their_lines():
    assert build_morning_brief(local_now=datetime(2026, 10, 3, 19, 0)) == "Good evening, Karmo. It's Saturday, October 3, 7:00 PM."


def test_operator_brief_needs_no_model_and_survives_a_failed_status_read():
    def broken_status(_args=None):
        raise RuntimeError("systemctl unavailable")

    operator = KarmoOperator(model_client=NoModelClient(), memory_backend=FactMemory(), status_reader=broken_status)

    response = operator.handle("good morning")

    assert response["kind"] == "chat"
    assert response["model"] is None
    assert response["message"].startswith("Good ")
    assert "You asked me to remember: trash goes out Thursday; tent light runs 14 hours." in response["message"]
    assert "Lab:" not in response["message"]
