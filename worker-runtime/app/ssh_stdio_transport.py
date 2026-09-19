"""Restricted SSH/stdio transport for KARMO workers.

This client opens no listener. Each request creates one outbound SSH session to
an AI01 account whose authorized key is expected to use a forced command for the
KARMO stdio gateway. The transport never invokes a local shell and never sends a
remote command string; SSH host-key verification therefore remains mandatory
and the server decides the only program that may run.
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import dataclass


class SshStdioTransportError(RuntimeError):
    pass


_SAFE_USER = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_SAFE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
_MAX_FRAME_BYTES = 64 * 1024


@dataclass(frozen=True)
class SshStdioConfig:
    host: str
    user: str
    identity_file: str
    known_hosts_file: str
    connect_timeout_seconds: int = 10
    request_timeout_seconds: int = 30
    ssh_binary: str = "/usr/bin/ssh"

    def validate(self):
        if not _SAFE_USER.fullmatch(self.user):
            raise SshStdioTransportError("invalid SSH user")
        if not _SAFE_HOST.fullmatch(self.host) or self.host.startswith("-"):
            raise SshStdioTransportError("invalid SSH host")
        if not (1 <= int(self.connect_timeout_seconds) <= 30):
            raise SshStdioTransportError("connect timeout out of bounds")
        if not (1 <= int(self.request_timeout_seconds) <= 120):
            raise SshStdioTransportError("request timeout out of bounds")
        for label, value in (
            ("identity_file", self.identity_file),
            ("known_hosts_file", self.known_hosts_file),
            ("ssh_binary", self.ssh_binary),
        ):
            if not value or "\x00" in value:
                raise SshStdioTransportError(f"invalid {label}")
        return True


class SshStdioTransport:
    """One-request-per-session outbound transport with strict SSH controls."""

    def __init__(self, config: SshStdioConfig, *, runner=subprocess.run):
        config.validate()
        self.config = config
        self._runner = runner

    def _argv(self):
        cfg = self.config
        return [
            cfg.ssh_binary,
            "-T",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={cfg.known_hosts_file}",
            "-o", "IdentitiesOnly=yes",
            "-o", "ClearAllForwardings=yes",
            "-o", "ForwardAgent=no",
            "-o", "RequestTTY=no",
            "-o", f"ConnectTimeout={int(cfg.connect_timeout_seconds)}",
            "-i", cfg.identity_file,
            "--",
            f"{cfg.user}@{cfg.host}",
        ]

    @staticmethod
    def _encode(operation: str, payload: dict):
        if not isinstance(operation, str) or not operation or len(operation) > 64:
            raise SshStdioTransportError("invalid operation")
        if not isinstance(payload, dict):
            raise SshStdioTransportError("payload must be an object")
        request_id = str(uuid.uuid4())
        frame = {
            "version": 1,
            "request_id": request_id,
            "operation": operation,
            "payload": payload,
        }
        raw = (json.dumps(frame, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if len(raw) > _MAX_FRAME_BYTES:
            raise SshStdioTransportError("request frame too large")
        return request_id, raw

    def request(self, operation: str, payload: dict):
        request_id, raw = self._encode(operation, payload)
        try:
            completed = self._runner(
                self._argv(),
                input=raw,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=int(self.config.request_timeout_seconds),
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SshStdioTransportError("SSH gateway request timed out") from exc
        except OSError as exc:
            raise SshStdioTransportError("SSH gateway could not be started") from exc

        if len(completed.stdout) > _MAX_FRAME_BYTES:
            if completed.returncode != 0:
                # Do not surface stderr: OpenSSH diagnostics can reveal local
                # paths, account names, or deployment details that callers do
                # not need.
                raise SshStdioTransportError("SSH gateway request failed")
            raise SshStdioTransportError("response frame too large")

        if completed.returncode != 0:
            # A non-zero SSH exit does not by itself mean the gateway never
            # ran: serve_one() always writes one bounded, already-redacted
            # JSON response before exiting, even when it caught an internal
            # exception and is exiting non-zero to signal an application-
            # level refusal (see worker_stdio_gateway.py's serve_one -- exit
            # 2/3 still carries a valid {"ok": false, "error": ...} body).
            # Peek for that body -- bound to this exact request_id/version,
            # the same way a zero-exit response is validated below -- so a
            # real application refusal is distinguishable from a genuine SSH
            # transport failure (bad host key, dropped connection, network
            # partition) instead of both collapsing into one opaque message.
            # Do not surface stderr in either case: OpenSSH diagnostics can
            # reveal local paths, account names, or deployment details that
            # callers do not need.
            candidate = None
            if completed.stdout:
                try:
                    candidate = json.loads(completed.stdout.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    candidate = None
            if (
                isinstance(candidate, dict)
                and candidate.get("version") == 1
                and candidate.get("request_id") == request_id
                and candidate.get("ok") is False
            ):
                code = candidate.get("error")
                if not isinstance(code, str) or not code:
                    code = "gateway_refused"
                raise SshStdioTransportError(f"gateway refused request: {code}")
            raise SshStdioTransportError("SSH gateway request failed")

        try:
            response = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SshStdioTransportError("invalid gateway response") from exc
        if not isinstance(response, dict):
            raise SshStdioTransportError("invalid gateway response")
        if response.get("version") != 1 or response.get("request_id") != request_id:
            raise SshStdioTransportError("gateway response binding mismatch")
        if response.get("ok") is True:
            if set(response) != {"version", "request_id", "ok", "result"}:
                raise SshStdioTransportError("invalid successful gateway response")
            return response.get("result")
        if response.get("ok") is False:
            if set(response) != {"version", "request_id", "ok", "error"}:
                raise SshStdioTransportError("invalid failed gateway response")
            code = response.get("error")
            if not isinstance(code, str) or not code:
                code = "gateway_refused"
            raise SshStdioTransportError(f"gateway refused request: {code}")
        raise SshStdioTransportError("invalid gateway response")

    def heartbeat(self, *, worker_id: str, credential_token: str, lease_seconds: int = 90,
                  ollama_snapshot: dict | None = None):
        # ollama_snapshot is included only when present (Model Router Phase A,
        # see docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.1)
        # so a caller that never collects one (or an older worker binary that
        # doesn't know about it) sends the exact same three-key payload as
        # before -- required for the gateway's schema validation to accept
        # both old and new workers during a non-atomic rollout across
        # Worker01/Worker02.
        payload = {
            "worker_id": worker_id,
            "credential_token": credential_token,
            "lease_seconds": int(lease_seconds),
        }
        if ollama_snapshot is not None:
            payload["ollama_snapshot"] = ollama_snapshot
        return self.request("heartbeat", payload)

    def poll(self, *, worker_id: str, credential_token: str, capabilities):
        return self.request("poll", {
            "worker_id": worker_id,
            "credential_token": credential_token,
            "capabilities": sorted(set(capabilities)),
        })

    def authorize_execution(self, *, worker_id: str, credential_token: str,
                            lease: dict, execution_ticket: str):
        return self.request("authorize_execution", {
            "worker_id": worker_id,
            "credential_token": credential_token,
            "lease": lease,
            "execution_ticket": execution_ticket,
        })

    def submit_result(self, *, worker_id: str, credential_token: str, lease: dict,
                      execution_ticket: str, result, envelope: dict,
                      success: bool, error: str | None = None):
        return self.request("submit_result", {
            "worker_id": worker_id,
            "credential_token": credential_token,
            "lease": lease,
            "execution_ticket": execution_ticket,
            "result": result,
            "envelope": envelope,
            "success": bool(success),
            "error": error,
        })
