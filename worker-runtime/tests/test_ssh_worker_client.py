import pytest

from ssh_worker_client import (
    SUBMIT_RESULT_MAX_ATTEMPTS,
    RemoteWorkerClientError,
    RemoteWorkerConfig,
    SshRemoteWorkerClient,
    _arguments_digest,
)


ARGS = {"host": "karmo-ai01"}
DIGEST = _arguments_digest("karmolab.host_health", "1", ARGS)


def _work(worker_id="karmo-worker01", digest=DIGEST):
    return {
        "lease": {
            "job_id": "job-1",
            "task_id": "task-1",
            "worker_id": worker_id,
            "lease_token": "lease-1",
            "tool_id": "karmolab.host_health",
            "tool_version": "1",
            "arguments_digest": digest,
            "approval_id": "approval-1",
            "attempt_count": 1,
            "lease_expires_at": "2026-09-13T16:00:00+00:00",
        },
        "arguments": dict(ARGS),
        "execution_ticket": "signed-ticket",
    }


class Transport:
    def __init__(self, *, work=None, authorization=None, events=None):
        self.work = _work() if work is None else work
        self.authorization = {"authorized": True} if authorization is None else authorization
        self.events = events if events is not None else []
        self.submitted = None

    def heartbeat(self, **kwargs):
        return {"lease_expires_at": "soon"}

    def poll(self, **kwargs):
        self.events.append("poll")
        return self.work

    def authorize_execution(self, **kwargs):
        self.events.append("authorize")
        return self.authorization

    def submit_result(self, **kwargs):
        self.events.append("submit")
        self.submitted = kwargs
        return {"accepted": True, "state": "SUCCEEDED" if kwargs["success"] else "FAILED"}


class FlakySubmitTransport(Transport):
    """submit_result fails the first N calls, then behaves normally."""

    def __init__(self, *, fail_times, events=None):
        super().__init__(events=events)
        self.fail_times = fail_times
        self.submit_attempts = 0

    def submit_result(self, **kwargs):
        self.submit_attempts += 1
        if self.submit_attempts <= self.fail_times:
            self.events.append("submit_failed")
            raise RuntimeError("transient gateway hiccup")
        return super().submit_result(**kwargs)


class Signer:
    def __init__(self):
        self.calls = []

    def sign(self, **kwargs):
        self.calls.append(kwargs)
        return {"payload": {"key_id": kwargs["key_id"]}, "signature": "sig"}


def _client(transport, signer, executor):
    return SshRemoteWorkerClient(
        config=RemoteWorkerConfig(
            worker_id="karmo-worker01",
            key_id="worker01-key-v1",
            capability_versions={"karmolab.host_health": "1"},
            timeout_seconds=5,
        ),
        transport=transport,
        credential_provider=lambda: "credential",
        result_authenticator=signer,
        executor=executor,
    )


def test_heartbeat_forwards_ollama_snapshot_to_transport():
    captured = {}

    class CapturingTransport(Transport):
        def heartbeat(self, **kwargs):
            captured.update(kwargs)
            return {"lease_expires_at": "soon"}

    client = _client(CapturingTransport(), Signer(), executor=lambda *a, **kw: None)
    client.heartbeat(lease_seconds=90, ollama_snapshot={"loaded_models": ["qwen3:8b"]})
    assert captured["ollama_snapshot"] == {"loaded_models": ["qwen3:8b"]}


def test_heartbeat_forwards_none_ollama_snapshot_when_not_collected():
    captured = {}

    class CapturingTransport(Transport):
        def heartbeat(self, **kwargs):
            captured.update(kwargs)
            return {"lease_expires_at": "soon"}

    client = _client(CapturingTransport(), Signer(), executor=lambda *a, **kw: None)
    client.heartbeat(lease_seconds=90)
    assert captured["ollama_snapshot"] is None


def test_remote_worker_never_executes_before_core_authorization():
    events = []
    transport = Transport(events=events)
    signer = Signer()

    def executor(*args, **kwargs):
        events.append("execute")
        return {"status": "healthy"}, "healthy", 0.01, []

    result = _client(transport, signer, executor).poll_once()
    assert events == ["poll", "authorize", "execute", "submit"]
    assert result["success"] is True
    assert transport.submitted["result"]["output"] == {"status": "healthy"}
    assert len(signer.calls) == 1


def test_remote_worker_refuses_to_execute_when_core_does_not_authorize():
    events = []
    transport = Transport(authorization={"authorized": False}, events=events)
    signer = Signer()

    def executor(*args, **kwargs):
        events.append("EXECUTION_MUST_NOT_HAPPEN")

    with pytest.raises(RemoteWorkerClientError, match="did not authorize"):
        _client(transport, signer, executor).poll_once()
    assert events == ["poll", "authorize"]
    assert signer.calls == []
    assert transport.submitted is None


def test_remote_worker_refuses_cross_worker_or_tampered_arguments_before_authorization():
    for work in (_work(worker_id="karmo-worker02"), _work(digest="f" * 64)):
        events = []
        transport = Transport(work=work, events=events)
        signer = Signer()
        with pytest.raises(RemoteWorkerClientError):
            _client(transport, signer, lambda *a, **k: None).poll_once()
        assert events == ["poll"]
        assert signer.calls == []


def test_remote_worker_reports_bounded_execution_failure_as_authenticated_result():
    events = []
    transport = Transport(events=events)
    signer = Signer()

    def executor(*args, **kwargs):
        events.append("execute")
        raise RuntimeError("bounded failure")

    result = _client(transport, signer, executor).poll_once()
    assert result["success"] is False
    assert transport.submitted["success"] is False
    assert "bounded failure" in transport.submitted["error"]
    assert signer.calls[0]["result"] == transport.submitted["result"]


def test_submit_result_retries_transient_failure_then_succeeds(monkeypatch):
    """A capability that already finished must not be silently dropped
    because of one momentary gateway hiccup -- this is the root-cause fix
    for a job left permanently orphaned in LEASED state."""
    import ssh_worker_client

    monkeypatch.setattr(ssh_worker_client.time, "sleep", lambda _seconds: None)
    events = []
    transport = FlakySubmitTransport(fail_times=SUBMIT_RESULT_MAX_ATTEMPTS - 1, events=events)
    signer = Signer()

    def executor(*args, **kwargs):
        return {"status": "healthy"}, "healthy", 0.01, []

    result = _client(transport, signer, executor).poll_once()

    assert result["success"] is True
    assert transport.submit_attempts == SUBMIT_RESULT_MAX_ATTEMPTS
    assert events.count("submit_failed") == SUBMIT_RESULT_MAX_ATTEMPTS - 1
    assert events[-1] == "submit"


def test_submit_result_raises_clear_error_after_exhausting_retries(monkeypatch):
    import ssh_worker_client

    monkeypatch.setattr(ssh_worker_client.time, "sleep", lambda _seconds: None)
    events = []
    transport = FlakySubmitTransport(fail_times=SUBMIT_RESULT_MAX_ATTEMPTS + 5, events=events)
    signer = Signer()

    def executor(*args, **kwargs):
        return {"status": "healthy"}, "healthy", 0.01, []

    with pytest.raises(RemoteWorkerClientError, match="submit_result failed after"):
        _client(transport, signer, executor).poll_once()

    assert transport.submit_attempts == SUBMIT_RESULT_MAX_ATTEMPTS


def test_remote_worker_returns_none_without_work_and_does_not_authorize():
    events = []
    transport = Transport(work=None, events=events)
    transport.work = None
    signer = Signer()
    result = _client(transport, signer, lambda *a, **k: None).poll_once()
    assert result is None
    assert events == ["poll"]
