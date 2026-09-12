import os

import pytest

from capabilities import _safe_subprocess_env
from crypto_boundary import (
    CryptoBoundaryError,
    ExecutionTicketAuthority,
    KeyResolver,
    ResultAuthenticator,
    WorkerAuthenticator,
)
from sandbox import PathTraversalError, resolve_within_sandbox


WORKER_KEY = b"w" * 32
COORDINATOR_KEY = b"c" * 32


def keys(key_id):
    values = {"worker-key": WORKER_KEY, "coordinator-key": COORDINATOR_KEY}
    return values.get(key_id)


def test_subprocess_environment_is_allowlisted_and_secret_free():
    source = {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "AWS_SECRET_ACCESS_KEY": "never-pass-this",
        "GITHUB_TOKEN": "never-pass-this-either",
        "SSH_AUTH_SOCK": "/tmp/agent.sock",
        "PYTHONPATH": "/sensitive/injection/path",
    }
    env = _safe_subprocess_env(source)
    assert env["PATH"] == "/usr/bin"
    assert env["LANG"] == "C.UTF-8"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "SSH_AUTH_SOCK" not in env
    assert "PYTHONPATH" not in env


def test_symlink_escape_is_refused(tmp_path):
    root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    (root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathTraversalError):
        resolve_within_sandbox(root, "escape/secret.txt")


def test_worker_credential_proves_identity_and_expires():
    now = [1_000]
    auth = WorkerAuthenticator(KeyResolver(keys), clock=lambda: now[0])
    token = auth.issue(worker_id="KARMO-DEV01", key_id="worker-key", ttl_seconds=60)
    assert auth.verify(token, expected_worker_id="KARMO-DEV01")["worker_id"] == "KARMO-DEV01"
    with pytest.raises(CryptoBoundaryError):
        auth.verify(token, expected_worker_id="rogue-worker")
    now[0] = 1_061
    with pytest.raises(CryptoBoundaryError):
        auth.verify(token, expected_worker_id="KARMO-DEV01")


def test_execution_ticket_binds_exact_approval_arguments_worker_and_task():
    now = [2_000]
    authority = ExecutionTicketAuthority(
        KeyResolver(keys), signing_key_id="coordinator-key", clock=lambda: now[0]
    )
    token = authority.issue(
        approval_id="approval-1",
        arguments_digest="abc123",
        executor_identity="worker-1",
        task_id="task-1",
        ttl_seconds=30,
    )
    verified = authority.verify(
        token,
        approval_id="approval-1",
        arguments_digest="abc123",
        executor_identity="worker-1",
        task_id="task-1",
    )
    assert verified["approval_id"] == "approval-1"
    with pytest.raises(CryptoBoundaryError):
        authority.verify(
            token,
            approval_id="approval-1",
            arguments_digest="tampered",
            executor_identity="worker-1",
            task_id="task-1",
        )


def test_result_authenticity_is_worker_and_task_bound():
    authenticator = ResultAuthenticator(KeyResolver(keys))
    result = {"status": "ok", "count": 3}
    envelope = authenticator.sign(
        worker_id="worker-1", key_id="worker-key", task_id="task-1", result=result
    )
    assert authenticator.verify(
        envelope, worker_id="worker-1", task_id="task-1", result=result
    ) is True
    with pytest.raises(CryptoBoundaryError):
        authenticator.verify(
            envelope, worker_id="worker-1", task_id="task-1", result={"status": "fake"}
        )
