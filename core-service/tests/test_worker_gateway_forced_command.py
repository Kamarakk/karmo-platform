import io
import json

import pytest

from core_service.worker_gateway_forced_command import (
    ForcedCommandError,
    authorized_keys_options,
    serve_forced_command,
)


class Backend:
    def heartbeat(self, **kwargs):
        return {"ok": "heartbeat"}


def _frame():
    return (json.dumps({
        "version": 1,
        "request_id": "req-1",
        "operation": "heartbeat",
        "payload": {
            "worker_id": "karmo-worker01",
            "credential_token": "credential",
            "lease_seconds": 90,
        },
    }) + "\n").encode()


def test_forced_command_refuses_client_supplied_remote_command():
    with pytest.raises(ForcedCommandError, match="forbidden"):
        serve_forced_command(
            backend=Backend(),
            expected_worker_id="karmo-worker01",
            environ={"SSH_ORIGINAL_COMMAND": "id"},
            stdin=io.BytesIO(_frame()),
            stdout=io.BytesIO(),
        )


def test_forced_command_serves_stdio_when_original_command_is_empty():
    stdout = io.BytesIO()
    code = serve_forced_command(
        backend=Backend(),
        expected_worker_id="karmo-worker01",
        environ={"SSH_ORIGINAL_COMMAND": ""},
        stdin=io.BytesIO(_frame()),
        stdout=stdout,
    )
    response = json.loads(stdout.getvalue())
    assert code == 0
    assert response["ok"] is True


def test_authorized_keys_options_are_restrictive_and_worker_bound():
    options = authorized_keys_options(
        forced_command_path="/usr/local/libexec/karmo-worker-gateway",
        expected_worker_id="karmo-worker01",
    )
    assert 'command="/usr/local/libexec/karmo-worker-gateway karmo-worker01"' in options
    assert "restrict" in options
    assert "no-agent-forwarding" in options
    assert "no-port-forwarding" in options
    assert "no-X11-forwarding" in options
    assert "no-pty" in options
    assert "no-user-rc" in options


def test_authorized_keys_options_reject_injectable_identity():
    with pytest.raises(ForcedCommandError):
        authorized_keys_options(
            forced_command_path="/usr/local/libexec/karmo-worker-gateway",
            expected_worker_id="karmo-worker01;id",
        )
