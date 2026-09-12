from __future__ import annotations

from types import SimpleNamespace

import pytest

from core_service import karmolab
from core_service.ollama_client import OllamaChatClient, OllamaClientError
from core_service.operator import KarmoOperator


class FakeModelClient:
    def __init__(self, verifier_reply="PASS"):
        self.calls = []
        self.verifier_reply = verifier_reply

    def chat(self, *, model, messages, temperature=0.2):
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        if model == "qwen3:4b":
            return self.verifier_reply
        if "Summarize only" in messages[0]["content"]:
            return "KarmoLab is online and the supplied read evidence was collected."
        return "KARMO conversational response"


def fake_status(_arguments=None):
    return {
        "host": {"hostname": "karmo-test", "cpu_count": 8},
        "memory": {"available": True},
        "disk": {"path": "/", "free_bytes": 123},
        "services": {"karmo-core.service": {"state": "active"}},
        "containers": {"available": True, "containers": []},
        "mode": "READ_ONLY",
    }


def test_operator_read_status_routes_dispatches_and_independently_verifies():
    client = FakeModelClient()
    operator = KarmoOperator(model_client=client, status_reader=fake_status)

    response = operator.handle("How is KarmoLab status this morning?")

    assert response["kind"] == "karmolab_read"
    assert response["tool_id"] == "karmolab.read_status"
    assert response["tool_version"] == "1.0.0"
    assert response["approval_requirement"] == "NONE"
    assert response["primary_model"] == "qwen3:8b"
    assert response["verifier_model"] == "qwen3:4b"
    assert response["primary_model"] != response["verifier_model"]
    assert response["verification"] == "PASS"
    assert response["evidence"]["mode"] == "READ_ONLY"
    assert [call["model"] for call in client.calls] == ["qwen3:8b", "qwen3:4b"]


def test_verifier_failure_withholds_unverified_model_summary():
    operator = KarmoOperator(model_client=FakeModelClient(verifier_reply="FAIL unsupported claim"), status_reader=fake_status)

    response = operator.handle("show system health")

    assert response["verification"] == "FAIL"
    assert response["message"] == "KarmoLab READ completed; showing verified raw evidence."
    assert response["evidence"]["host"]["hostname"] == "karmo-test"


def test_write_request_is_refused_before_model_or_tool_execution():
    calls = {"status": 0}

    def status_reader(_arguments=None):
        calls["status"] += 1
        return fake_status()

    client = FakeModelClient()
    operator = KarmoOperator(model_client=client, status_reader=status_reader)

    response = operator.handle("restart the worker service")

    assert response["kind"] == "refusal"
    assert "READ-only" in response["message"]
    assert calls["status"] == 0
    assert client.calls == []


def test_general_chat_uses_local_model_router_without_tool_execution():
    calls = {"status": 0}

    def status_reader(_arguments=None):
        calls["status"] += 1
        return fake_status()

    client = FakeModelClient()
    operator = KarmoOperator(model_client=client, status_reader=status_reader)

    response = operator.handle("Good morning Karmo")

    assert response == {
        "kind": "chat",
        "message": "KARMO conversational response",
        "model": "qwen3:8b",
    }
    assert calls["status"] == 0
    assert [call["model"] for call in client.calls] == ["qwen3:8b"]


def test_ollama_client_rejects_non_loopback_endpoint():
    with pytest.raises(OllamaClientError, match="loopback"):
        OllamaChatClient("http://192.168.1.50:11434")


def test_karmolab_subprocesses_are_fixed_read_only_and_never_shell(monkeypatch):
    observed = []

    def fake_run(argv, **kwargs):
        observed.append((tuple(argv), kwargs))
        if tuple(argv[:2]) == ("docker", "ps"):
            return SimpleNamespace(returncode=0, stdout="karmo-postgres\tUp 1 day\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="active\n", stderr="")

    monkeypatch.setattr(karmolab.subprocess, "run", fake_run)

    result = karmolab.read_status({})

    assert result["mode"] == "READ_ONLY"
    assert [item[0] for item in observed] == [
        ("systemctl", "is-active", "karmo-core.service"),
        ("systemctl", "is-active", "karmo-worker.service"),
        ("docker", "ps", "--format", "{{.Names}}\t{{.Status}}"),
    ]
    assert all(kwargs["shell"] is False for _, kwargs in observed)
    assert all(kwargs["timeout"] == 3.0 for _, kwargs in observed)
