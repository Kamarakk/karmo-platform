from __future__ import annotations

import http.server
import json
import threading

import ollama_health


def _serve(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _shutdown(server, thread):
    server.shutdown()
    thread.join(timeout=5)


def test_collect_snapshot_parses_real_api_ps_shape(monkeypatch):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/ps"
            body = json.dumps({"models": [{"name": "qwen3:8b"}, {"name": "granite3.3:2b"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _serve(Handler)
    try:
        monkeypatch.setenv("KARMO_OLLAMA_PS_URL", f"http://127.0.0.1:{server.server_port}/api/ps")
        snapshot = ollama_health.collect_snapshot()
        assert snapshot == {"loaded_models": ["qwen3:8b", "granite3.3:2b"]}
    finally:
        _shutdown(server, thread)


def test_collect_snapshot_returns_none_when_unreachable(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_PS_URL", "http://127.0.0.1:1/api/ps")
    assert ollama_health.collect_snapshot(timeout_seconds=1.0) is None


def test_collect_snapshot_returns_none_on_malformed_response(monkeypatch):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"not json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _serve(Handler)
    try:
        monkeypatch.setenv("KARMO_OLLAMA_PS_URL", f"http://127.0.0.1:{server.server_port}/api/ps")
        assert ollama_health.collect_snapshot() is None
    finally:
        _shutdown(server, thread)


def test_collect_snapshot_refuses_non_loopback_url(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_PS_URL", "http://192.168.1.235:11434/api/ps")
    assert ollama_health.collect_snapshot() is None


def test_collect_snapshot_bounds_model_count(monkeypatch):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"models": [{"name": f"model-{i}"} for i in range(100)]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _serve(Handler)
    try:
        monkeypatch.setenv("KARMO_OLLAMA_PS_URL", f"http://127.0.0.1:{server.server_port}/api/ps")
        snapshot = ollama_health.collect_snapshot()
        assert len(snapshot["loaded_models"]) == ollama_health._MAX_MODELS_REPORTED
    finally:
        _shutdown(server, thread)
