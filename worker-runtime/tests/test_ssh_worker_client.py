import pytest

from ssh_worker_client import (
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


def test_remote_worker_returns_none_without_work_and_does_not_authorize():
    events = []
    transport = Transport(work=None, events=events)
    transport.work = None
    signer = Signer()
    result = _client(transport, signer, lambda *a, **k: None).poll_once()
    assert result is None
    assert events == ["poll"]
