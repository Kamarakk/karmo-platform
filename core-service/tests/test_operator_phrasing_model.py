"""Stage 3 (2026-09-29): once BloomBoss figures are fetched up front and no
tool is left to choose, the small phrasing model words the answer; qwen3:8b
keeps every turn that still has a tool decision, and takes over if the
phrasing model fails."""

from __future__ import annotations

from core_service.model_router import ModelRouter
from core_service.ollama_client import OllamaClientError
from core_service.operator import KarmoOperator, default_model_resources


class RecordingClient:
    def __init__(self, fail_models=()):
        self.fail_models = set(fail_models)
        self.calls = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None, on_token=None):
        self.calls.append((model, [t["function"]["name"] for t in tools]))
        if model in self.fail_models:
            raise OllamaClientError("local model request failed: HTTPError")
        return {"content": f"answer from {model}", "tool_calls": None}


def test_prefetched_business_question_is_phrased_by_the_small_model_without_tools():
    client = RecordingClient()
    response = KarmoOperator(model_client=client).handle("should I restock the Ninja Albos?")

    assert client.calls == [("llama3.2:3b", [])]
    assert response["model"] == "llama3.2:3b"
    assert response["message"] == "answer from llama3.2:3b"


def test_phrasing_model_failure_falls_back_to_qwen3_in_the_same_turn():
    client = RecordingClient(fail_models={"llama3.2:3b"})
    response = KarmoOperator(model_client=client).handle("should I restock the Ninja Albos?")

    assert [model for model, _ in client.calls] == ["llama3.2:3b", "qwen3:8b"]
    assert response["model"] == "qwen3:8b"
    assert response["message"] == "answer from qwen3:8b"


def test_empty_phrasing_answer_falls_back_to_qwen3():
    class EmptySmall(RecordingClient):
        def chat_with_tools(self, *, model, **kwargs):
            result = super().chat_with_tools(model=model, **kwargs)
            return {"content": "", "tool_calls": None} if model == "llama3.2:3b" else result

    client = EmptySmall()
    response = KarmoOperator(model_client=client).handle("should I restock the Ninja Albos?")

    assert response["model"] == "qwen3:8b"


def test_non_business_question_still_goes_to_qwen3_with_its_tools():
    client = RecordingClient()
    response = KarmoOperator(model_client=client).handle("tell me a joke about clouds")

    assert [model for model, _ in client.calls] == ["qwen3:8b"]
    assert "bloomboss_report" in client.calls[0][1]
    assert response["model"] == "qwen3:8b"


def test_business_question_with_another_tool_left_keeps_qwen3():
    client = RecordingClient()
    KarmoOperator(model_client=client).handle("write a python script for my plant sales")

    assert [model for model, _ in client.calls] == ["qwen3:8b"]
    assert client.calls[0][1] == ["ask_local_coder"]


def test_phrasing_model_is_never_a_chat_or_tool_calling_candidate():
    router = ModelRouter(default_model_resources())
    assert [r.model_id for r in router.ranked(required_capabilities={"tool_calling"})] == ["qwen3:8b"]
    assert [r.model_id for r in router.ranked(required_capabilities={"chat"})] == ["qwen3:8b"]
