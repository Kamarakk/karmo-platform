"""Outbound-only KARMO remote worker client.

The worker does not receive Core/coordinator signing authority. It heartbeats and
polls through the restricted SSH/stdio transport, validates the exact workload
binding locally, then asks Core to consume/authorize the signed execution ticket
*before* invoking the bounded local sandbox. Results are signed with only the
worker's own key and returned to Core for durable verification/finalization.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

import capabilities  # noqa: F401 -- registers fixed sandbox handlers
from crypto_boundary import token_digest
from sandbox import run_capability


class RemoteWorkerClientError(RuntimeError):
    pass


# A capability may already have finished (successfully or not) by the time
# submit_result runs -- that outcome must never be silently dropped because
# of one transient SSH hiccup. Each attempt is already individually bounded
# by SshStdioTransport's own subprocess timeout (<=120s), so this retry can
# never itself hang; it can only add a few bounded, short waits before
# finally surfacing a clear error if the gateway is genuinely unreachable.
SUBMIT_RESULT_MAX_ATTEMPTS = 3
SUBMIT_RESULT_RETRY_DELAY_SECONDS = 2


@dataclass(frozen=True)
class RemoteWorkerConfig:
    worker_id: str
    key_id: str
    capability_versions: dict[str, str]
    timeout_seconds: int = 30
    allowed_root: str | None = None

    def validate(self):
        if not self.worker_id or not self.key_id:
            raise RemoteWorkerClientError("worker identity and key_id are required")
        if not isinstance(self.capability_versions, dict) or not self.capability_versions:
            raise RemoteWorkerClientError("at least one capability/version is required")
        for capability_id, version in self.capability_versions.items():
            if not isinstance(capability_id, str) or not capability_id:
                raise RemoteWorkerClientError("invalid capability id")
            if not isinstance(version, str) or not version:
                raise RemoteWorkerClientError("invalid capability version")
        if not (1 <= int(self.timeout_seconds) <= 300):
            raise RemoteWorkerClientError("timeout out of bounds")
        return True


def _arguments_digest(tool_id: str, tool_version: str, arguments: dict) -> str:
    canonical = json.dumps(
        {"tool_id": tool_id, "tool_version": tool_version, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SshRemoteWorkerClient:
    def __init__(self, *, config: RemoteWorkerConfig, transport,
                 credential_provider, result_authenticator,
                 executor=run_capability):
        config.validate()
        if not callable(credential_provider):
            raise RemoteWorkerClientError("credential_provider must be callable")
        if not callable(executor):
            raise RemoteWorkerClientError("executor must be callable")
        self.config = config
        self.transport = transport
        self.credential_provider = credential_provider
        self.result_authenticator = result_authenticator
        self.executor = executor

    def _credential(self) -> str:
        token = self.credential_provider()
        if not isinstance(token, str) or not token:
            raise RemoteWorkerClientError("credential provider returned no credential")
        return token

    def heartbeat(self, *, lease_seconds: int = 90):
        return self.transport.heartbeat(
            worker_id=self.config.worker_id,
            credential_token=self._credential(),
            lease_seconds=lease_seconds,
        )

    def _validate_work(self, work: dict):
        if not isinstance(work, dict) or set(work) != {"lease", "arguments", "execution_ticket"}:
            raise RemoteWorkerClientError("invalid work envelope")
        lease = work["lease"]
        arguments = work["arguments"]
        ticket = work["execution_ticket"]
        if not isinstance(lease, dict) or not isinstance(arguments, dict):
            raise RemoteWorkerClientError("invalid work payload")
        if not isinstance(ticket, str) or not ticket:
            raise RemoteWorkerClientError("missing execution ticket")
        if lease.get("worker_id") != self.config.worker_id:
            raise RemoteWorkerClientError("work is bound to a different worker")
        tool_id = lease.get("tool_id")
        tool_version = lease.get("tool_version")
        expected_version = self.config.capability_versions.get(tool_id)
        if expected_version is None or tool_version != expected_version:
            raise RemoteWorkerClientError("tool/version is not enabled on this worker")
        digest = _arguments_digest(tool_id, tool_version, arguments)
        if digest != lease.get("arguments_digest"):
            raise RemoteWorkerClientError("work arguments digest mismatch")
        return lease, arguments, ticket

    def poll_once(self):
        work = self.transport.poll(
            worker_id=self.config.worker_id,
            credential_token=self._credential(),
            capabilities=sorted(self.config.capability_versions),
        )
        if work is None:
            return None
        lease, arguments, ticket = self._validate_work(work)

        # Critical ordering invariant: no capability code runs until Core has
        # verified and consumed the exact ticket against the still-live lease.
        # Use a fresh credential for each authority round trip so a credential
        # that was near expiry at poll time cannot silently weaken recovery.
        authorization = self.transport.authorize_execution(
            worker_id=self.config.worker_id,
            credential_token=self._credential(),
            lease=lease,
            execution_ticket=ticket,
        )
        if authorization != {"authorized": True}:
            raise RemoteWorkerClientError("Core did not authorize execution")

        success = True
        error = None
        try:
            output, stdout_summary, duration_seconds, evidence_files = self.executor(
                lease["tool_id"],
                arguments,
                timeout_seconds=int(self.config.timeout_seconds),
                allowed_root=self.config.allowed_root,
            )
            result = {
                "output": output,
                "stdout_summary": stdout_summary,
                "duration_seconds": duration_seconds,
                "evidence_files": evidence_files,
            }
        except Exception as exc:  # noqa: BLE001 -- report bounded terminal failure to Core
            success = False
            error = f"{type(exc).__name__}: {exc}"[:2000]
            result = {"error": error}

        envelope = self.result_authenticator.sign(
            worker_id=self.config.worker_id,
            key_id=self.config.key_id,
            task_id=lease["task_id"],
            result=result,
            execution_ticket_digest=token_digest(ticket),
        )
        final = None
        submit_error = None
        for attempt in range(SUBMIT_RESULT_MAX_ATTEMPTS):
            try:
                final = self.transport.submit_result(
                    worker_id=self.config.worker_id,
                    credential_token=self._credential(),
                    lease=lease,
                    execution_ticket=ticket,
                    result=result,
                    envelope=envelope,
                    success=success,
                    error=error,
                )
                submit_error = None
                break
            except Exception as exc:  # noqa: BLE001 -- bounded retry; never silently drop a finished result
                submit_error = exc
                if attempt + 1 < SUBMIT_RESULT_MAX_ATTEMPTS:
                    time.sleep(SUBMIT_RESULT_RETRY_DELAY_SECONDS)
        if submit_error is not None:
            raise RemoteWorkerClientError(
                f"submit_result failed after {SUBMIT_RESULT_MAX_ATTEMPTS} attempts "
                f"(capability outcome success={success} was never reported to Core): "
                f"{type(submit_error).__name__}: {submit_error}"
            ) from submit_error
        return {
            "job_id": lease["job_id"],
            "success": success,
            "core": final,
        }
