"""Streaming the answer's words to the web UI as the CPU model writes them
(2026-09-27): the client streams from Ollama, and the operator forwards the
pieces, clearing them when a later round replaces an earlier one."""

from __future__ import annotations

import http.server
import json
import threading

import pytest

from core_service.ollama_client import OllamaChatClient, OllamaClientError
from core_service.operator import KarmoOperator


def _serve(lines):
    captured = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            captured.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for line in lines:
                self.wfile.write(json.dumps(line).encode() + b"\n")
                self.wfile.flush()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, captured


def test_client_streams_pieces_and_returns_the_same_message_shape():
    server, captured = _serve([
        {"message": {"content": "Ninja "}, "done": False},
        {"message": {"content": "Albo."}, "done": False},
        {"message": {"content": ""}, "done": True},
    ])
    try:
        pieces = []
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        message = client.chat_with_tools(model="qwen3:8b", messages=[], tools=[], on_token=pieces.append)
    finally:
        server.shutdown()

    assert captured["stream"] is True
    assert pieces == ["Ninja ", "Albo."]
    assert message == {"content": "Ninja Albo.", "tool_calls": None}


def test_client_collects_streamed_tool_calls():
    call = {"function": {"name": "list_tasks", "arguments": {}}}
    server, _ = _serve([{"message": {"content": "", "tool_calls": [call]}, "done": True}])
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        message = client.chat_with_tools(model="qwen3:8b", messages=[], tools=[], on_token=lambda p: None)
    finally:
        server.shutdown()

    assert message["tool_calls"] == [call]


def test_client_without_on_token_does_not_stream():
    server, captured = _serve([{"message": {"content": "ok"}, "done": True}])
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        assert client.chat(model="qwen3:8b", messages=[]) == "ok"
    finally:
        server.shutdown()

    assert captured["stream"] is False


def test_client_stream_refuses_invalid_json():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not json\n")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        with pytest.raises(OllamaClientError):
            client.chat_with_tools(model="qwen3:8b", messages=[], tools=[], on_token=lambda p: None)
    finally:
        server.shutdown()


class StreamingClient:
    """First round writes text then asks for list_tasks; second round writes
    the final answer."""

    def __init__(self):
        self.rounds = 0

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None, on_token=None):
        self.rounds += 1
        if self.rounds == 1:
            on_token("Checking")
            return {"content": "Checking", "tool_calls": [{"function": {"name": "list_tasks", "arguments": {}}}]}
        on_token("Done.")
        return {"content": "Done.", "tool_calls": None}


def test_operator_forwards_pieces_and_clears_before_a_later_round():
    events = []
    response = KarmoOperator(model_client=StreamingClient()).handle("what tasks are open?", on_token=events.append)

    assert events == ["Checking", None, "Done."]
    assert response["message"] == "Done."


def test_operator_without_on_token_calls_the_client_as_before():
    class PlainClient:
        def chat_with_tools(self, *, model, messages, tools, temperature=0.2, timeout=None):
            return {"content": "plain", "tool_calls": None}

    assert KarmoOperator(model_client=PlainClient()).handle("what's the weather on mars?")["message"] == "plain"
