from __future__ import annotations

import http.server
import json
import threading

import pytest

from core_service.ollama_client import OllamaChatClient, OllamaClientError


def test_local_operator_request_has_generation_limit():
    captured = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            captured.update(json.loads(self.rfile.read(length).decode("utf-8")))
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
        result = client.chat(model="qwen3:8b", messages=[{"role": "user", "content": "Reply OK"}])
        assert result == "OK"
        assert captured["options"]["num_predict"] == 300
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_num_predict_is_configurable_per_client_2026_09_20():
    """The generation cap was previously a hardcoded literal in
    _request_message; it's now a constructor default (DEFAULT_NUM_PREDICT,
    300 since 2026-09-27) so a future tuning pass can construct
    OllamaChatClient(num_predict=...) without editing ollama_client.py."""
    captured = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            captured.update(json.loads(self.rfile.read(length).decode("utf-8")))
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
        client = OllamaChatClient(f"http://127.0.0.1:{server.server_port}", num_predict=256)
        client.chat(model="qwen3:8b", messages=[{"role": "user", "content": "Reply OK"}])
        assert captured["options"]["num_predict"] == 256
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.parametrize("bad_value", [0, -1, 96.0, True, "96"])
def test_invalid_num_predict_is_refused_at_construction(bad_value):
    with pytest.raises(OllamaClientError, match="num_predict"):
        OllamaChatClient(num_predict=bad_value)
