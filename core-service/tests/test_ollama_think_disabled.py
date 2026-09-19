from __future__ import annotations

import http.server
import json
import threading
import time

import pytest

from core_service.ollama_client import OllamaChatClient, OllamaClientError


def test_ollama_chat_disables_thinking_for_bounded_operator_latency():
    captured = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            captured.update(payload)
            body = b'{"message": {"content": "OK"}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}")
        result = client.chat(
            model="qwen3:8b",
            messages=[{"role": "user", "content": "Reply OK only"}],
            temperature=0.0,
        )
        assert result == "OK"
        assert captured["think"] is False
        assert captured["stream"] is False
        assert captured["model"] == "qwen3:8b"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_chat_with_tools_per_call_timeout_overrides_the_client_default():
    """Model Router Section 3.5 -- a single total per-turn deadline needs
    a per-call timeout override, not the client's fixed construction-time
    default every call used before. A slow handler must time out against
    a short override even though the client itself was built with a much
    longer default."""
    class SlowHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            time.sleep(2.0)
            body = b'{"message": {"content": "too slow"}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}", timeout=120.0)
        with pytest.raises(OllamaClientError):
            client.chat_with_tools(
                model="qwen3:8b",
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                timeout=0.2,
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)
