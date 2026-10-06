from __future__ import annotations

import pytest

from core_service.ollama_client import (
    FailoverOllamaClient,
    OllamaChatClient,
    OllamaClientError,
    build_default_model_client,
)


class FakeClient:
    def __init__(self, *, up=True, fail=False, stream=()):
        self.up = up
        self.fail = fail
        self.stream = stream
        self.pings = 0
        self.calls = []

    def ping(self, timeout):
        self.pings += 1
        return self.up

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise OllamaClientError("local model request failed: URLError")
        return "answer"

    def chat_with_tools(self, **kwargs):
        self.calls.append(kwargs)
        for piece in self.stream:
            kwargs["on_token"](piece)
        if self.fail:
            raise OllamaClientError("local model request failed: URLError")
        return {"content": "answer", "tool_calls": None}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_uses_imac_when_it_answers():
    imac, ai01 = FakeClient(), FakeClient()
    client = FailoverOllamaClient(imac, ai01)
    assert client.chat(model="qwen3:8b", messages=[]) == "answer"
    assert len(imac.calls) == 1 and ai01.calls == []
    assert client.last_host == "imac"


def test_asleep_imac_goes_straight_to_ai01_and_is_rechecked_later():
    clock = Clock()
    imac, ai01 = FakeClient(up=False), FakeClient()
    client = FailoverOllamaClient(imac, ai01, clock=clock, down_seconds=60)
    client.chat(model="qwen3:8b", messages=[])
    client.chat(model="qwen3:8b", messages=[])
    assert imac.pings == 1 and imac.calls == [] and len(ai01.calls) == 2
    assert client.last_host == "ai01"
    clock.now = 61
    imac.up = True
    client.chat(model="qwen3:8b", messages=[])
    assert imac.pings == 2 and len(imac.calls) == 1


def test_imac_error_falls_back_with_remaining_time():
    clock = Clock()
    imac, ai01 = FakeClient(fail=True), FakeClient()

    def slow_chat(**kwargs):
        clock.now += 10
        raise OllamaClientError("local model request failed: HTTPError")

    imac.chat = slow_chat
    client = FailoverOllamaClient(imac, ai01, clock=clock)
    assert client.chat(model="qwen3:8b", messages=[], timeout=100) == "answer"
    assert ai01.calls[0]["timeout"] == 90


def test_no_fallback_when_turn_budget_is_spent():
    clock = Clock()
    imac, ai01 = FakeClient(), FakeClient()

    def slow_chat(**kwargs):
        clock.now += 100
        raise OllamaClientError("local model request failed: timeout")

    imac.chat = slow_chat
    client = FailoverOllamaClient(imac, ai01, clock=clock)
    with pytest.raises(OllamaClientError):
        client.chat(model="qwen3:8b", messages=[], timeout=100)
    assert ai01.calls == []


def test_partial_stream_is_cleared_before_ai01_retries():
    imac, ai01 = FakeClient(fail=True, stream=("Hel",)), FakeClient(stream=("Hello",))
    seen = []
    client = FailoverOllamaClient(imac, ai01)
    client.chat_with_tools(model="qwen3:8b", messages=[], tools=[], on_token=seen.append)
    assert seen == ["Hel", None, "Hello"]


def test_off_unless_enabled_file_exists(tmp_path):
    flag = tmp_path / "imac_brain.enabled"
    assert isinstance(build_default_model_client(str(flag)), OllamaChatClient)
    flag.write_text("")
    client = build_default_model_client(str(flag))
    assert isinstance(client, FailoverOllamaClient)
    assert client.primary.base_url == "http://127.0.0.1:11435"
    assert client.fallback.base_url == "http://127.0.0.1:11434"


def test_ping_is_false_when_nothing_listens():
    assert OllamaChatClient("http://127.0.0.1:1").ping(timeout=0.5) is False


def test_missing_model_on_imac_does_not_mark_it_down():
    imac, ai01 = FakeClient(fail=True), FakeClient()
    client = FailoverOllamaClient(imac, ai01)
    client.chat(model="mistral:7b", messages=[])
    assert len(ai01.calls) == 1
    imac.fail = False
    client.chat(model="qwen3:8b", messages=[])
    assert len(imac.calls) == 2 and client.last_host == "imac"
