from __future__ import annotations

import json
import os
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

    def handle(self, text, on_token=None):
        self.calls.append(text)
        if on_token is not None:
            on_token("draft")
            on_token(None)
            on_token("echo: ")
            on_token(text)
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


def test_page_script_keeps_escaped_newline():
    # A bare '\n' in the Python source becomes a real line break inside a
    # JS string literal, a syntax error that kills the whole script (text
    # box and mic stop responding).
    assert b"indexOf('\\n')" in webui._PAGE


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


def test_chat_stream_sends_words_then_the_final_answer(running_server):
    server, fake = running_server
    request = urllib.request.Request(
        _url(server, "/chat/stream"), data=json.dumps({"text": "hello"}).encode(), method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.headers["Content-Type"] == "application/x-ndjson"
        events = [json.loads(line) for line in response.read().decode().splitlines() if line.strip()]

    assert events[:4] == [{"t": "draft"}, {"reset": True}, {"t": "echo: "}, {"t": "hello"}]
    assert events[-1] == {"kind": "chat", "message": "echo: hello", "memory_status": "ACTIVE", "done": True}
    assert fake.calls == ["hello"]


def test_chat_stream_rejects_malformed_body(running_server):
    server, _ = running_server
    request = urllib.request.Request(_url(server, "/chat/stream"), data=b"not json", method="POST")
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=5)
    assert excinfo.value.code == 400


def test_server_answers_the_page_while_a_chat_turn_is_running():
    """A slow turn must not queue every other request behind it."""
    started, release = threading.Event(), threading.Event()

    class SlowOperator(FakeOperator):
        def handle(self, text, on_token=None):
            started.set()
            release.wait(5)
            return super().handle(text)

    webui._Handler.operator = SlowOperator()
    server = webui.ThreadingHTTPServer(("127.0.0.1", 0), webui._Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        chat = threading.Thread(target=lambda: urllib.request.urlopen(urllib.request.Request(
            _url(server, "/chat"), data=json.dumps({"text": "slow"}).encode(), method="POST"), timeout=10).read())
        chat.start()
        assert started.wait(5)
        with urllib.request.urlopen(_url(server, "/"), timeout=2) as response:
            assert response.status == 200
        release.set()
        chat.join(timeout=5)
    finally:
        release.set()
        server.shutdown()
        thread.join(timeout=5)


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


def test_speak_post_accepts_max_length_text_that_max_body_bytes_would_have_rejected(running_server):
    server, fake = running_server
    # speech_synthesize_capability.MAX_TEXT_CHARS is 2000 -- a legitimate
    # max-length request made of 4-byte UTF-8 characters (e.g. emoji)
    # serializes to 8000+ bytes once JSON-wrapped, over the old
    # MAX_BODY_BYTES (8000) that /speak used to reuse from /chat. This
    # is exactly the request the review found would have been wrongly
    # rejected before MAX_SPEAK_BODY_BYTES was introduced.
    text = "\U0001F600" * webui._SPEAK_MAX_TEXT_CHARS
    # ensure_ascii=False matches a real browser's fetch() body: raw
    # UTF-8 bytes, not \uXXXX-escaped -- json.dumps()'s ensure_ascii
    # default would otherwise balloon each 4-byte emoji into a 12-byte
    # escape sequence, which isn't the real-world shape this bound is
    # sized for.
    req = urllib.request.Request(
        _url(server, "/speak"),
        data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body == {"audio_base64": "ZmFrZS1hdWRpbw=="}
    assert fake.speak_calls == [text]


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


def test_resolve_tailscale_dns_name_uses_tailscale_status_json(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            stdout = json.dumps({"Self": {"DNSName": "karmo-ai01.tail1234.ts.net."}})

        return Result()

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    dns_name = webui._resolve_tailscale_dns_name()

    assert dns_name == "karmo-ai01.tail1234.ts.net"
    assert calls == [["tailscale", "status", "--json"]]


def test_resolve_tailscale_dns_name_rejects_missing_dns_name(monkeypatch):
    def fake_run(cmd, **kwargs):
        class Result:
            stdout = json.dumps({"Self": {}})

        return Result()

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        webui._resolve_tailscale_dns_name()


def test_ensure_tailscale_cert_writes_under_cert_dir_and_creates_it(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    cert_dir = str(tmp_path / "tailscale-tls")

    cert_path, key_path = webui._ensure_tailscale_cert("karmo-ai01.tail1234.ts.net", cert_dir)

    assert cert_path == str(tmp_path / "tailscale-tls" / "karmo-ai01.tail1234.ts.net.crt")
    assert key_path == str(tmp_path / "tailscale-tls" / "karmo-ai01.tail1234.ts.net.key")
    assert os.path.isdir(cert_dir)
    assert calls == [[
        "tailscale", "cert",
        "--cert-file", cert_path,
        "--key-file", key_path,
        "karmo-ai01.tail1234.ts.net",
    ]]


def test_ensure_tailscale_cert_fixes_permissions_on_a_preexisting_looser_directory(monkeypatch, tmp_path):
    # Real bug found by review, 2026-09-24: os.makedirs(mode=0o700) only
    # applies that mode when it actually creates the directory --
    # exist_ok=True silently leaves a pre-existing looser-permission
    # directory untouched. Simulate exactly that: create the directory
    # by hand first, with obviously looser permissions, before calling
    # the function under test.
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    cert_dir = str(tmp_path / "tailscale-tls")
    os.makedirs(cert_dir, mode=0o755)
    assert os.stat(cert_dir).st_mode & 0o777 == 0o755

    webui._ensure_tailscale_cert("karmo-ai01.tail1234.ts.net", cert_dir)

    assert os.stat(cert_dir).st_mode & 0o777 == 0o700


def test_serve_tailscale_https_mode_fails_clean_when_tailscale_unavailable(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("tailscale not installed")

    monkeypatch.setattr(webui.subprocess, "run", fake_run)
    with pytest.raises(FileNotFoundError):
        webui.serve(mode="tailscale-https")


def test_mic_sends_the_transcript_to_karmo_without_waiting_for_enter():
    page = webui._PAGE.decode()
    assert "await send(data.text)" in page
    assert "box.value = data.text" not in page


def test_spoken_reply_reuses_a_player_unlocked_during_the_tap():
    page = webui._PAGE.decode()
    assert page.count("unlockAudio();") == 2  # Enter and mic tap
    assert "player.play().catch(" in page
    assert "new Audio('data:audio/wav" not in page
