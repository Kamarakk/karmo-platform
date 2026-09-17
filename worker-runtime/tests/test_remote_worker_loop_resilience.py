"""Proves the root-cause fix for a job silently orphaned in LEASED state:
run_loop must never swallow a poll_once() failure without at least logging
it, since a capability may already have executed by the time the failure
occurs."""

from __future__ import annotations

import remote_worker_runtime


class _StopLoop(KeyboardInterrupt):
    """Distinguish 'test wants to stop the loop' from a real interrupt."""


class FakeClient:
    def __init__(self, *, failures):
        self.failures = list(failures)
        self.heartbeats = 0
        self.poll_calls = 0

    def heartbeat(self, lease_seconds):
        self.heartbeats += 1

    def poll_once(self):
        self.poll_calls += 1
        if self.failures:
            raise self.failures.pop(0)
        raise _StopLoop()


def _cfg():
    return remote_worker_runtime.WorkerRuntimeConfig(
        worker_id="KARMO-WORKER01",
        key_id="worker01-v1",
        ai01_host="192.168.1.235",
        ai01_user="karmo-gateway",
        identity_file="/etc/karmo/worker01/ssh_identity",
        known_hosts_file="/etc/karmo/worker01/known_hosts",
        worker_key_file="/etc/karmo/worker01/worker.key",
        capabilities={"model_chat": "1.0.0"},
        poll_interval_seconds=1,
    )


def test_run_loop_logs_a_swallowed_poll_failure_instead_of_hiding_it(monkeypatch, capsys):
    client = FakeClient(failures=[RuntimeError("gateway request failed")])
    monkeypatch.setattr(remote_worker_runtime, "build_client", lambda cfg, **kw: client)
    monkeypatch.setattr(remote_worker_runtime.time, "sleep", lambda _seconds: None)

    remote_worker_runtime.run_loop(_cfg())  # exits via _StopLoop on the 2nd iteration

    captured = capsys.readouterr()
    assert "KARMO worker poll cycle failed" in captured.err
    assert "RuntimeError" in captured.err
    assert "gateway request failed" in captured.err
    assert client.poll_calls == 2


def test_run_loop_continues_after_a_logged_failure_rather_than_crashing(monkeypatch):
    client = FakeClient(failures=[RuntimeError("first"), RuntimeError("second")])
    monkeypatch.setattr(remote_worker_runtime, "build_client", lambda cfg, **kw: client)
    monkeypatch.setattr(remote_worker_runtime.time, "sleep", lambda _seconds: None)

    remote_worker_runtime.run_loop(_cfg())

    assert client.poll_calls == 3  # two failures survived, third call stops the test loop
