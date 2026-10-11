"""Per-turn trace (karmo_turn_trace): every answer records how it was made."""

from __future__ import annotations

import json

from core_service.durable_memory import NullMemoryBackend
from core_service.ollama_client import OllamaChatClient
from core_service.operator import KarmoOperator


class TraceMemory(NullMemoryBackend):
    status = "ACTIVE"

    def __init__(self, fail=False):
        self.traces, self.ratings, self.fail = [], [], fail

    def record_turn(self, trace):
        if self.fail:
            raise RuntimeError("database down")
        self.traces.append(trace)
        return len(self.traces)

    def rate_turn(self, trace_id, rating):
        self.ratings.append((trace_id, rating))
        return True


class RouterModel:
    def __init__(self, reply):
        self.reply, self.usage = reply, []

    def chat(self, *, model, messages, temperature=0.2, timeout=None):
        self.usage.append({"model": model, "prompt_tokens": 600, "output_tokens": 2, "model_ms": 400})
        return self.reply


class BrainClient:
    def __init__(self, route="chat", answer="Bright, indirect light."):
        self.primary = RouterModel(route)
        self.answer, self.usage, self.last_host = answer, [], None

    def primary_available(self):
        return True

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None, on_token=None):
        self.usage.append({"model": model, "prompt_tokens": 1500, "output_tokens": 40, "model_ms": 3000})
        self.last_host = "imac"
        return {"content": self.answer, "tool_calls": None}


def test_a_model_answer_is_traced_with_route_model_host_and_tokens():
    memory = TraceMemory()
    result = KarmoOperator(model_client=BrainClient(), memory_backend=memory).handle(
        "Is morning sun good for Alocasia?")
    assert result["trace_id"] == 1
    trace = memory.traces[0]
    assert trace["question"] == "Is morning sun good for Alocasia?"
    assert trace["answer"].startswith("Bright, indirect light.")
    assert trace["route"] == "chat"
    assert trace["host"] == "imac"
    assert trace["model_calls"] == 2
    assert trace["prompt_tokens"] == 2100
    assert trace["output_tokens"] == 42
    assert trace["model_ms"] == 3400
    assert trace["latency_ms"] >= 0


def test_usage_from_a_previous_turn_is_not_counted_again():
    memory, client = TraceMemory(), BrainClient()
    operator = KarmoOperator(model_client=client, memory_backend=memory)
    operator.handle("Is morning sun good for Alocasia?")
    operator.handle("And for Monstera?")
    assert memory.traces[1]["prompt_tokens"] == 2100


def test_a_shortcut_answer_is_traced_without_a_model():
    memory = TraceMemory()
    KarmoOperator(model_client=BrainClient(), memory_backend=memory).handle("hello")
    assert memory.traces[0]["route"] == "shortcut"
    assert memory.traces[0]["model_calls"] == 0


def test_a_failed_trace_never_costs_the_answer():
    result = KarmoOperator(model_client=BrainClient(), memory_backend=TraceMemory(fail=True)).handle(
        "Is morning sun good for Alocasia?")
    assert result["message"].startswith("Bright, indirect light.")
    assert "trace_id" not in result


def test_rating_goes_to_the_memory_backend():
    memory = TraceMemory()
    assert KarmoOperator(model_client=BrainClient(), memory_backend=memory).rate_turn(7, -1) is True
    assert memory.ratings == [(7, -1)]


def test_ollama_client_records_token_counts_from_the_response():
    client = OllamaChatClient()
    client._record_usage("qwen3:8b", {"prompt_eval_count": 812, "eval_count": 55,
                                      "prompt_eval_duration": 1_200_000_000, "eval_duration": 2_300_000_000})
    client._record_usage("qwen3:8b", {"eval_count": True})
    assert client.usage[0] == {"model": "qwen3:8b", "prompt_tokens": 812, "output_tokens": 55, "model_ms": 3500}
    assert client.usage[1] == {"model": "qwen3:8b", "prompt_tokens": None, "output_tokens": None, "model_ms": None}


def test_ollama_client_records_usage_on_a_plain_call(monkeypatch):
    client = OllamaChatClient()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, _n):
            return json.dumps({"message": {"content": "hi"}, "prompt_eval_count": 10, "eval_count": 3}).encode()

    monkeypatch.setattr(client._opener, "open", lambda request, timeout: Response())
    assert client.chat(model="qwen3:8b", messages=[{"role": "user", "content": "hi"}]) == "hi"
    assert client.usage[-1]["prompt_tokens"] == 10


def test_health_reports_brain_and_memory():
    health = KarmoOperator(model_client=BrainClient(), memory_backend=TraceMemory()).health()
    assert health["ok"] is True
    assert health["brain"] == "imac"
    assert health["memory_status"] == "ACTIVE"
    assert "deployed_sha" in health


def test_tailnet_actor_names_the_device_and_login():
    from types import SimpleNamespace

    from core_service.webui import _ACTOR_CACHE, tailnet_actor
    _ACTOR_CACHE.clear()
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=json.dumps(
            {"Node": {"ComputedName": "iphone-15"}, "UserProfile": {"LoginName": "kamarakk@gmail.com"}}))

    assert tailnet_actor("100.64.0.9", runner=runner) == "iphone-15 (kamarakk@gmail.com)"
    assert tailnet_actor("100.64.0.9", runner=runner) == "iphone-15 (kamarakk@gmail.com)"
    assert len(calls) == 1  # cached
    assert tailnet_actor("127.0.0.1", runner=runner) is None


def test_actor_is_recorded_on_the_trace():
    memory = TraceMemory()
    KarmoOperator(model_client=BrainClient(), memory_backend=memory).handle("hello", actor="iphone-15 (k)")
    assert memory.traces[0]["actor"] == "iphone-15 (k)"
