from __future__ import annotations

import http.server
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

from core_service.host_health import (
    HostHealthError,
    HostHealthTracker,
    check_host,
    poll_loaded_models,
    run_timed_probe,
)


def _serve(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _shutdown(server, thread):
    server.shutdown()
    thread.join(timeout=5)


def _ok_ps_handler(models):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/ps"
            body = json.dumps({"models": [{"name": m} for m in models]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


def test_poll_loaded_models_parses_real_api_ps_shape():
    server, thread = _serve(_ok_ps_handler(["qwen3:8b", "granite3.3:2b"]))
    try:
        result = poll_loaded_models(f"http://127.0.0.1:{server.server_port}")
        assert result == ["qwen3:8b", "granite3.3:2b"]
    finally:
        _shutdown(server, thread)


def test_poll_loaded_models_rejects_non_loopback_url():
    with pytest.raises(HostHealthError):
        poll_loaded_models("http://192.168.1.235:11434")


def test_poll_loaded_models_raises_on_malformed_response():
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
        with pytest.raises(HostHealthError):
            poll_loaded_models(f"http://127.0.0.1:{server.server_port}")
    finally:
        _shutdown(server, thread)


def test_poll_loaded_models_raises_when_unreachable():
    with pytest.raises(HostHealthError):
        # Port 1 is reserved and will refuse the connection immediately.
        poll_loaded_models("http://127.0.0.1:1", timeout=1.0)


def test_run_timed_probe_measures_real_elapsed_time():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            assert payload["model"] == "granite3.3:2b"
            assert payload["stream"] is False
            assert payload["options"]["num_predict"] == 1
            body = b'{"response": "ok"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _serve(Handler)
    try:
        latency = run_timed_probe(f"http://127.0.0.1:{server.server_port}", model="granite3.3:2b")
        assert latency >= 0.0
    finally:
        _shutdown(server, thread)


def test_run_timed_probe_rejects_invalid_model_identifier():
    with pytest.raises(HostHealthError):
        run_timed_probe("http://127.0.0.1:11434", model="qwen3:8b\r\nX-Injected: 1")


def test_run_timed_probe_rejects_non_loopback_url():
    with pytest.raises(HostHealthError):
        run_timed_probe("http://10.0.0.5:11434", model="granite3.3:2b")


def test_tracker_records_success_and_resets_failure_count():
    tracker = HostHealthTracker()
    tracker.record_failure("karmo-ai01", error="boom")
    tracker.record_failure("karmo-ai01", error="boom again")
    assert tracker.snapshot("karmo-ai01").consecutive_failures == 2

    snapshot = tracker.record_success("karmo-ai01", loaded_models=["qwen3:8b"], latency_seconds=1.5)
    assert snapshot.reachable is True
    assert snapshot.consecutive_failures == 0
    assert snapshot.loaded_models == ("qwen3:8b",)
    assert snapshot.recent_latencies_seconds == (1.5,)


def test_tracker_rolling_window_is_bounded():
    tracker = HostHealthTracker(max_samples=3)
    for latency in (1.0, 2.0, 3.0, 4.0, 5.0):
        snapshot = tracker.record_success("karmo-ai01", loaded_models=[], latency_seconds=latency)
    assert snapshot.recent_latencies_seconds == (3.0, 4.0, 5.0)


def test_tracker_p50_p95_from_recent_samples():
    tracker = HostHealthTracker()
    for latency in (1.0, 2.0, 3.0, 4.0, 5.0):
        snapshot = tracker.record_success("karmo-ai01", loaded_models=[], latency_seconds=latency)
    assert snapshot.p50_latency_seconds == 3.0
    assert snapshot.p95_latency_seconds == 5.0


def test_snapshot_age_and_staleness_use_injectable_clock():
    ticks = iter([
        datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 18, 12, 5, 0, tzinfo=timezone.utc),
    ])
    tracker = HostHealthTracker(clock=lambda: next(ticks))
    snapshot = tracker.record_success("karmo-ai01", loaded_models=["qwen3:8b"])
    later = datetime(2026, 9, 18, 12, 5, 0, tzinfo=timezone.utc)
    assert snapshot.age_seconds(now=later) == 300.0
    assert snapshot.is_stale(max_age_seconds=60, now=later) is True
    assert snapshot.is_stale(max_age_seconds=600, now=later) is False


def test_check_host_full_success_path_records_ps_and_probe():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"models": [{"name": "granite3.3:2b"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = b'{"response": "ok"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, thread = _serve(Handler)
    try:
        tracker = HostHealthTracker()
        snapshot = check_host(
            tracker,
            host_id="karmo-ai01",
            base_url=f"http://127.0.0.1:{server.server_port}",
            probe_model="granite3.3:2b",
        )
        assert snapshot.reachable is True
        assert snapshot.loaded_models == ("granite3.3:2b",)
        assert snapshot.probe_latency_seconds is not None
        assert tracker.snapshot("karmo-ai01") is snapshot
    finally:
        _shutdown(server, thread)


def test_check_host_without_probe_model_records_ps_only():
    server, thread = _serve(_ok_ps_handler(["qwen3:8b"]))
    try:
        tracker = HostHealthTracker()
        snapshot = check_host(
            tracker, host_id="karmo-ai01", base_url=f"http://127.0.0.1:{server.server_port}",
        )
        assert snapshot.reachable is True
        assert snapshot.probe_latency_seconds is None
        assert snapshot.recent_latencies_seconds == ()
    finally:
        _shutdown(server, thread)


def test_check_host_records_failure_and_increments_consecutive_count():
    tracker = HostHealthTracker()
    check_host(tracker, host_id="karmo-ai01", base_url="http://127.0.0.1:1", timeout=1.0)
    snapshot = check_host(tracker, host_id="karmo-ai01", base_url="http://127.0.0.1:1", timeout=1.0)
    assert snapshot.reachable is False
    assert snapshot.consecutive_failures == 2
    assert snapshot.error is not None
