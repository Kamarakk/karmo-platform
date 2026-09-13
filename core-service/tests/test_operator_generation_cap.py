from __future__ import annotations

import http.server
import json
import threading

from core_service.ollama_client import OllamaChatClient


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
        assert captured["options"]["num_predict"] == 96
    finally:
        server.shutdown()
        thread.join(timeout=5)
