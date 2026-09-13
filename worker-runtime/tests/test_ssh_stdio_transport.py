import json
import subprocess

import pytest

from ssh_stdio_transport import SshStdioConfig, SshStdioTransport, SshStdioTransportError


class Completed:
    def __init__(self, *, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _config():
    return SshStdioConfig(
        host="192.168.1.235",
        user="karmo-worker-gateway",
        identity_file="/etc/karmo/worker01_ed25519",
        known_hosts_file="/etc/karmo/known_hosts",
    )


def test_ssh_transport_uses_strict_no_shell_no_forwarding_controls():
    seen = {}

    def runner(argv, **kwargs):
        seen["argv"] = argv
        seen.update(kwargs)
        request = json.loads(kwargs["input"].decode())
        response = {
            "version": 1,
            "request_id": request["request_id"],
            "ok": True,
            "result": {"lease_expires_at": "soon"},
        }
        return Completed(stdout=(json.dumps(response) + "\n").encode())

    transport = SshStdioTransport(_config(), runner=runner)
    result = transport.heartbeat(
        worker_id="karmo-worker01", credential_token="credential", lease_seconds=90
    )
    assert result == {"lease_expires_at": "soon"}
    argv = seen["argv"]
    assert seen["shell"] is False
    assert "StrictHostKeyChecking=yes" in argv
    assert "BatchMode=yes" in argv
    assert "IdentitiesOnly=yes" in argv
    assert "ClearAllForwardings=yes" in argv
    assert "ForwardAgent=no" in argv
    assert "RequestTTY=no" in argv
    assert argv[-2] == "--"
    assert argv[-1] == "karmo-worker-gateway@192.168.1.235"
    assert not any("StrictHostKeyChecking=no" in item for item in argv)
    assert not any("ProxyCommand" in item for item in argv)


def test_transport_sends_no_remote_command_string():
    transport = SshStdioTransport(_config(), runner=lambda *a, **k: None)
    argv = transport._argv()
    destination_index = argv.index("--") + 1
    assert argv[destination_index:] == ["karmo-worker-gateway@192.168.1.235"]


@pytest.mark.parametrize("host", ["-oProxyCommand=evil", "host name", "$(id)"])
def test_transport_rejects_unsafe_hosts(host):
    with pytest.raises(SshStdioTransportError):
        SshStdioTransport(SshStdioConfig(
            host=host,
            user="karmo-worker-gateway",
            identity_file="/key",
            known_hosts_file="/known_hosts",
        ))


def test_transport_binds_response_to_request_id():
    def runner(argv, **kwargs):
        response = {"version": 1, "request_id": "wrong", "ok": True, "result": {}}
        return Completed(stdout=json.dumps(response).encode())

    with pytest.raises(SshStdioTransportError, match="binding mismatch"):
        SshStdioTransport(_config(), runner=runner).poll(
            worker_id="karmo-worker01", credential_token="credential", capabilities=["read"]
        )


def test_transport_rejects_nonzero_ssh_without_leaking_stderr():
    secret = "PRIVATE-DEPLOYMENT-DETAIL"

    def runner(argv, **kwargs):
        return Completed(returncode=255, stderr=secret.encode())

    with pytest.raises(SshStdioTransportError) as exc:
        SshStdioTransport(_config(), runner=runner).heartbeat(
            worker_id="karmo-worker01", credential_token="credential"
        )
    assert secret not in str(exc.value)


def test_transport_rejects_oversized_request_before_starting_ssh():
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True

    with pytest.raises(SshStdioTransportError, match="too large"):
        SshStdioTransport(_config(), runner=runner).submit_result(
            worker_id="karmo-worker01",
            credential_token="credential",
            lease={},
            execution_ticket="ticket",
            result={"blob": "x" * (70 * 1024)},
            envelope={},
        )
    assert called is False


def test_transport_timeout_fails_closed():
    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=1)

    with pytest.raises(SshStdioTransportError, match="timed out"):
        SshStdioTransport(_config(), runner=runner).heartbeat(
            worker_id="karmo-worker01", credential_token="credential"
        )
