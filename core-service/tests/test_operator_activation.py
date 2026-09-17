from __future__ import annotations

import http.server
import threading
from types import SimpleNamespace

import pytest

from core_service import karmolab
from core_service.ollama_client import OllamaChatClient, OllamaClientError
from core_service.operator import KarmoOperator


class FakeModelClient:
    def __init__(self, verifier_reply="PASS", fail_models=()):
        self.calls = []
        self.verifier_reply = verifier_reply
        self.fail_models = set(fail_models)

    def chat(self, *, model, messages, temperature=0.2):
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        if model in self.fail_models:
            raise OllamaClientError("simulated model failure")
        if model == "mistral:7b":
            return self.verifier_reply
        if "Summarize only" in messages[0]["content"]:
            return "KarmoLab is online and the supplied read evidence was collected."
        return "KARMO conversational response"

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2):
        content = self.chat(model=model, messages=messages, temperature=temperature)
        return {"content": content, "tool_calls": None}


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
    assert response["verifier_model"] == "mistral:7b"
    assert response["primary_model"] != response["verifier_model"]
    assert response["verification"] == "PASS"
    assert response["evidence"]["mode"] == "READ_ONLY"
    assert [call["model"] for call in client.calls] == ["qwen3:8b", "mistral:7b"]


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


def test_general_chat_falls_back_to_ministral_then_granite():
    client = FakeModelClient(fail_models={"qwen3:8b", "ministral-3:8b"})
    operator = KarmoOperator(model_client=client, status_reader=fake_status)

    response = operator.handle("Good morning Karmo")

    assert response["kind"] == "chat"
    assert response["model"] == "granite3.3:2b"
    assert [call["model"] for call in client.calls] == [
        "qwen3:8b",
        "ministral-3:8b",
        "granite3.3:2b",
    ]


def test_general_chat_fails_closed_when_all_chat_models_fail():
    client = FakeModelClient(fail_models={"qwen3:8b", "ministral-3:8b", "granite3.3:2b"})
    operator = KarmoOperator(model_client=client, status_reader=fake_status)

    response = operator.handle("Good morning Karmo")

    assert response["kind"] == "chat"
    assert response["message"] == "Local chat models are unavailable. KARMO control plane remains fail-closed."
    assert "model" not in response


def test_ollama_client_rejects_non_loopback_endpoint():
    with pytest.raises(OllamaClientError, match="loopback"):
        OllamaChatClient("http://192.168.1.50:11434")


def test_ollama_client_refuses_to_follow_redirect_to_non_loopback_host():
    class RedirectingHandler(http.server.BaseHTTPRequestHandler):
        request_count = 0

        def do_POST(self):
            RedirectingHandler.request_count += 1
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(307)
            self.send_header("Location", "http://93.184.216.34/api/chat")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), RedirectingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        with pytest.raises(OllamaClientError, match="local model request failed"):
            client.chat(model="qwen3:8b", messages=[{"role": "user", "content": "hi"}])
        assert RedirectingHandler.request_count == 1
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_ollama_client_still_handles_a_normal_non_redirecting_response():
    class OkHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = b'{"message": {"content": "hello"}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), OkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        result = client.chat(model="qwen3:8b", messages=[{"role": "user", "content": "hi"}])
        assert result == "hello"
    finally:
        server.shutdown()
        thread.join(timeout=5)


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
