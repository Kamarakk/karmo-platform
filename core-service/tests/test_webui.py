from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from core_service import webui


class FakeOperator:
    def __init__(self):
        self.calls = []
        self.vision_calls = []
        self.transcribe_calls = []
        self.speak_calls = []
        self.vision_result = {"answer": "a red square"}
        self.transcribe_result = {"text": "hello there"}
        self.speak_result = {"audio_base64": "ZmFrZS1hdWRpbw=="}

    def handle(self, text):
        self.calls.append(text)
        return {"kind": "chat", "message": f"echo: {text}", "memory_status": "ACTIVE"}

    def dispatch_vision(self, *, question, image_base64):
        self.vision_calls.append((question, image_base64))
        return self.vision_result

    def dispatch_transcribe(self, *, audio_base64):
        self.transcribe_calls.append(audio_base64)
        return self.transcribe_result

    def dispatch_speak(self, *, text):
        self.speak_calls.append(text)
        return self.speak_result


@pytest.fixture
def running_server():
    from http.server import HTTPServer

    fake = FakeOperator()
    webui._Handler.operator = fake
    server = HTTPServer(("127.0.0.1", 0), webui._Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, fake
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _url(server, path):
    return f"http://127.0.0.1:{server.server_port}{path}"


def test_root_serves_html_page(running_server):
    server, _ = running_server
    with urllib.request.urlopen(_url(server, "/")) as resp:
        assert resp.status == 200
        assert resp.headers["Content-Type"].startswith("text/html")
        assert b"<html" in resp.read()


def test_unknown_get_path_is_404(running_server):
    server, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(_url(server, "/nope"))
    assert exc.value.code == 404


def test_chat_post_routes_through_operator_handle(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/chat"),
        data=json.dumps({"text": "hello karmo"}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body["message"] == "echo: hello karmo"
    assert body["memory_status"] == "ACTIVE"
    assert fake.calls == ["hello karmo"]


def test_chat_post_rejects_malformed_body(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/chat"),
        data=b"not json",
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    assert fake.calls == []


def test_chat_post_rejects_non_string_text(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/chat"),
        data=json.dumps({"text": 12345}).encode("utf-8"),
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    assert fake.calls == []


def test_chat_post_rejects_oversized_body(running_server):
    server, fake = running_server
    huge = json.dumps({"text": "x" * (webui.MAX_BODY_BYTES + 1)}).encode("utf-8")
    req = urllib.request.Request(_url(server, "/chat"), data=huge, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    assert fake.calls == []


def test_vision_post_routes_through_operator_and_returns_the_answer(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/vision"),
        data=json.dumps({"question": "what color?", "image_base64": "ZmFrZQ=="}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body == {"answer": "a red square"}
    assert fake.vision_calls == [("what color?", "ZmFrZQ==")]


def test_vision_post_returns_400_when_operator_reports_an_error(running_server):
    server, fake = running_server
    fake.vision_result = {"error": "worker dispatch is not activated -- no worker-dispatch DSN configured"}
    req = urllib.request.Request(
        _url(server, "/vision"),
        data=json.dumps({"question": "what color?", "image_base64": "ZmFrZQ=="}).encode("utf-8"),
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    body = json.loads(exc.value.read())
    assert "not activated" in body["error"]


def test_vision_post_rejects_missing_image_base64(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/vision"),
        data=json.dumps({"question": "what color?"}).encode("utf-8"),
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    assert fake.vision_calls == []


def test_transcribe_post_routes_through_operator_and_returns_the_text(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/transcribe"),
        data=json.dumps({"audio_base64": "ZmFrZQ=="}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body == {"text": "hello there"}
    assert fake.transcribe_calls == ["ZmFrZQ=="]


def test_speak_post_routes_through_operator_and_returns_the_audio(running_server):
    server, fake = running_server
    req = urllib.request.Request(
        _url(server, "/speak"),
        data=json.dumps({"text": "hello there"}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body == {"audio_base64": "ZmFrZS1hdWRpbw=="}
    assert fake.speak_calls == ["hello there"]


def test_serve_refuses_unsupported_mode():
    with pytest.raises(ValueError):
        webui.serve(mode="everywhere")


def test_resolve_tailscale_ip_uses_tailscale_cli(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            stdout = "100.75.239.44\n"

        return Result()

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    ip = webui._resolve_tailscale_ip()

    assert ip == "100.75.239.44"
    assert calls == [["tailscale", "ip", "-4"]]


def test_resolve_tailscale_ip_rejects_empty_output(monkeypatch):
    def fake_run(cmd, **kwargs):
        class Result:
            stdout = ""

        return Result()

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        webui._resolve_tailscale_ip()
