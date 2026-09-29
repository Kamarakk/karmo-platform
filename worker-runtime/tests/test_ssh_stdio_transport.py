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


def _success_runner(seen=None, result=None):
    def runner(argv, **kwargs):
        if seen is not None:
            seen["argv"] = argv
            seen.update(kwargs)
        request = json.loads(kwargs["input"].decode())
        response = {
            "version": 1,
            "request_id": request["request_id"],
            "ok": True,
            "result": result,
        }
        return Completed(stdout=(json.dumps(response) + "\n").encode())
    return runner


def test_ssh_transport_uses_strict_no_shell_no_forwarding_controls():
    seen = {}
    transport = SshStdioTransport(_config(), runner=_success_runner(seen, {"lease_expires_at": "soon"}))
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


def test_heartbeat_omits_ollama_snapshot_key_when_not_given():
    """Model Router Phase A: a caller that never collects a snapshot (or an
    older worker binary that doesn't know about the parameter) must send
    the exact same three-key payload as before the field existed -- the
    gateway's schema validation requires this for old/new workers to
    heartbeat successfully during a non-atomic rollout."""
    seen = {}
    transport = SshStdioTransport(_config(), runner=_success_runner(seen, {"lease_expires_at": "soon"}))
    transport.heartbeat(worker_id="karmo-worker01", credential_token="credential", lease_seconds=90)
    sent = json.loads(seen["input"].decode())
    assert set(sent["payload"]) == {"worker_id", "credential_token", "lease_seconds"}


def test_heartbeat_includes_ollama_snapshot_when_given():
    seen = {}
    transport = SshStdioTransport(_config(), runner=_success_runner(seen, {"lease_expires_at": "soon"}))
    transport.heartbeat(
        worker_id="karmo-worker01", credential_token="credential", lease_seconds=90,
        ollama_snapshot={"loaded_models": ["qwen3:8b"]},
    )
    sent = json.loads(seen["input"].decode())
    assert sent["payload"]["ollama_snapshot"] == {"loaded_models": ["qwen3:8b"]}


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


def test_transport_rejects_ambiguous_response_schema():
    def runner(argv, **kwargs):
        request = json.loads(kwargs["input"].decode())
        response = {
            "version": 1,
            "request_id": request["request_id"],
            "ok": True,
            "result": {},
            "error": "should-not-coexist",
        }
        return Completed(stdout=json.dumps(response).encode())

    with pytest.raises(SshStdioTransportError, match="successful gateway response"):
        SshStdioTransport(_config(), runner=runner).heartbeat(
            worker_id="karmo-worker01", credential_token="credential"
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


def test_transport_surfaces_bound_gateway_refusal_on_nonzero_exit():
    """serve_one() (worker_stdio_gateway.py) always writes one bounded,
    already-redacted JSON response before exiting -- even when it caught an
    internal exception and is exiting non-zero (exit 2/3) to signal an
    application-level refusal. Discarding that body just because the SSH
    process exited non-zero collapsed a real, safe, structured refusal
    into an opaque "SSH gateway request failed" indistinguishable from a
    genuine transport failure -- found while investigating a real
    production submit_result failure that gave no usable signal."""
    def runner(argv, **kwargs):
        request = json.loads(kwargs["input"].decode())
        response = {
            "version": 1,
            "request_id": request["request_id"],
            "ok": False,
            "error": "coordinator_refused",
        }
        return Completed(returncode=3, stdout=json.dumps(response).encode())

    with pytest.raises(SshStdioTransportError, match="gateway refused request: coordinator_refused"):
        SshStdioTransport(_config(), runner=runner).submit_result(
            worker_id="karmo-worker01",
            credential_token="credential",
            lease={},
            execution_ticket="ticket",
            result={"content": "hi"},
            envelope={},
            success=True,
        )


def test_transport_ignores_unbound_body_on_nonzero_exit():
    """A non-zero exit whose stdout doesn't parse, or doesn't bind to this
    exact request_id/version, must still fail generically -- it is not
    safe to trust a body that isn't provably this request's own response
    (e.g. stray output from a misconfigured forced command)."""
    def runner(argv, **kwargs):
        return Completed(returncode=255, stdout=json.dumps({"version": 1, "request_id": "not-this-one", "ok": False, "error": "x"}).encode())

    with pytest.raises(SshStdioTransportError, match="SSH gateway request failed"):
        SshStdioTransport(_config(), runner=runner).heartbeat(
            worker_id="karmo-worker01", credential_token="credential"
        )


def test_transport_nonzero_exit_with_ok_true_body_still_fails_generically():
    """An ok:true body paired with a non-zero exit is a contradiction
    (serve_one() only ever exits non-zero on a refusal), not a success --
    must not be trusted as a real result."""
    def runner(argv, **kwargs):
        request = json.loads(kwargs["input"].decode())
        response = {"version": 1, "request_id": request["request_id"], "ok": True, "result": {}}
        return Completed(returncode=3, stdout=json.dumps(response).encode())

    with pytest.raises(SshStdioTransportError, match="SSH gateway request failed"):
        SshStdioTransport(_config(), runner=runner).heartbeat(
            worker_id="karmo-worker01", credential_token="credential"
        )


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
            success=True,
        )
    assert called is False


def test_transport_has_explicit_pre_execution_authorization_round_trip():
    seen = {}
    transport = SshStdioTransport(_config(), runner=_success_runner(seen, {"authorized": True}))
    result = transport.authorize_execution(
        worker_id="karmo-worker01",
        credential_token="credential",
        lease={"job_id": "job", "lease_token": "lease"},
        execution_ticket="ticket",
    )
    request = json.loads(seen["input"].decode())
    assert request["operation"] == "authorize_execution"
    assert request["payload"]["execution_ticket"] == "ticket"
    assert result == {"authorized": True}


def test_transport_timeout_fails_closed():
    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=1)

    with pytest.raises(SshStdioTransportError, match="timed out"):
        SshStdioTransport(_config(), runner=runner).heartbeat(
            worker_id="karmo-worker01", credential_token="credential"
        )


def test_submit_result_sends_result_bytes_only_for_uploaded_results():
    kwargs = dict(worker_id="karmo-worker01", credential_token="credential", lease={},
                  execution_ticket="ticket", envelope={}, success=True)
    seen = {}
    transport = SshStdioTransport(_config(), runner=_success_runner(seen, {"accepted": True}))
    transport.submit_result(result={"ok": True}, **kwargs)
    assert "result_bytes" not in json.loads(seen["input"].decode())["payload"]
    transport.submit_result(result=None, result_bytes=90_000, **kwargs)
    assert json.loads(seen["input"].decode())["payload"]["result_bytes"] == 90_000


def test_upload_result_piece_frame():
    seen = {}
    transport = SshStdioTransport(_config(), runner=_success_runner(seen, {"offset": 0}))
    transport.upload_result_piece(worker_id="karmo-worker01", credential_token="credential",
                                  lease={"job_id": "job"}, execution_ticket="ticket",
                                  offset=0, chunk="abc")
    sent = json.loads(seen["input"].decode())
    assert sent["operation"] == "upload_result_piece"
    assert set(sent["payload"]) == {"worker_id", "credential_token", "lease",
                                    "execution_ticket", "offset", "chunk"}
