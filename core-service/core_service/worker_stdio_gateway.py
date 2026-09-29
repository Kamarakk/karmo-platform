"""Fail-closed JSON/stdio gateway for KARMO worker transport.

The gateway is intended to run only as an SSH forced command. It accepts one
bounded JSON request on stdin, dispatches only an allowlisted operation to an
injected coordinator adapter, writes one bounded JSON response, and exits. It
never executes a shell command and never derives authority from SSH reachability.

The forced-command wrapper MUST provide the expected worker identity obtained
from the server-side key/account mapping. Every request is then bound to that
identity before coordinator authentication is attempted.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass


MAX_FRAME_BYTES = 64 * 1024
PROTOCOL_VERSION = 1
_ALLOWED_OPERATIONS = frozenset({
    "heartbeat", "poll", "fetch_arguments", "authorize_execution",
    "upload_result_piece", "submit_result",
})
_SUBMIT_RESULT_FIELDS = frozenset({
    "worker_id", "credential_token", "lease", "execution_ticket",
    "result", "envelope", "success", "error",
})


class WorkerStdioGatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class GatewayRequest:
    request_id: str
    operation: str
    payload: dict


def _parse_request(raw: bytes) -> GatewayRequest:
    if not raw or len(raw) > MAX_FRAME_BYTES:
        raise WorkerStdioGatewayError("invalid_frame")
    try:
        frame = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerStdioGatewayError("invalid_json") from exc
    if not isinstance(frame, dict) or set(frame) != {"version", "request_id", "operation", "payload"}:
        raise WorkerStdioGatewayError("invalid_schema")
    if frame["version"] != PROTOCOL_VERSION:
        raise WorkerStdioGatewayError("unsupported_version")
    request_id = frame["request_id"]
    operation = frame["operation"]
    payload = frame["payload"]
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise WorkerStdioGatewayError("invalid_request_id")
    if operation not in _ALLOWED_OPERATIONS:
        raise WorkerStdioGatewayError("operation_not_allowed")
    if not isinstance(payload, dict):
        raise WorkerStdioGatewayError("invalid_payload")
    return GatewayRequest(request_id=request_id, operation=operation, payload=payload)


def _require_exact(payload: dict, required: set[str]):
    if set(payload) != required:
        raise WorkerStdioGatewayError("invalid_payload_schema")


def _require_bound_worker(payload: dict, expected_worker_id: str):
    worker_id = payload.get("worker_id")
    if not expected_worker_id or not isinstance(worker_id, str) or worker_id != expected_worker_id:
        raise WorkerStdioGatewayError("worker_identity_mismatch")


def _require_token(value, *, label: str, max_length: int = 16384):
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise WorkerStdioGatewayError(f"invalid_{label}")


# Model Router Phase A worker health signal (see
# docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.1). Bounded
# tightly and independently of MAX_FRAME_BYTES -- this field's own shape and
# size are validated here so a malformed/oversized report can only ever
# refuse itself, never the whole heartbeat request (lease renewal must not
# depend on this optional field being well-formed).
_MAX_OLLAMA_SNAPSHOT_MODELS = 32
_MAX_OLLAMA_SNAPSHOT_BYTES = 4096


def _validate_ollama_snapshot(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"loaded_models"}:
        raise WorkerStdioGatewayError("invalid_ollama_snapshot")
    models = value["loaded_models"]
    if (
        not isinstance(models, list)
        or len(models) > _MAX_OLLAMA_SNAPSHOT_MODELS
        or any(not isinstance(m, str) or not m or len(m) > 128 for m in models)
    ):
        raise WorkerStdioGatewayError("invalid_ollama_snapshot")
    if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > _MAX_OLLAMA_SNAPSHOT_BYTES:
        raise WorkerStdioGatewayError("invalid_ollama_snapshot")
    return value


def dispatch_request(request: GatewayRequest, *, backend, expected_worker_id: str):
    payload = request.payload
    _require_bound_worker(payload, expected_worker_id)

    if request.operation == "heartbeat":
        required = {"worker_id", "credential_token", "lease_seconds"}
        optional = {"ollama_snapshot"}
        if not required.issubset(payload) or not set(payload).issubset(required | optional):
            raise WorkerStdioGatewayError("invalid_payload_schema")
        _require_token(payload["credential_token"], label="credential_token")
        lease_seconds = payload["lease_seconds"]
        if not isinstance(lease_seconds, int) or not (1 <= lease_seconds <= 300):
            raise WorkerStdioGatewayError("invalid_lease_seconds")
        ollama_snapshot = _validate_ollama_snapshot(payload.get("ollama_snapshot"))
        return backend.heartbeat(
            worker_id=expected_worker_id,
            credential_token=payload["credential_token"],
            lease_seconds=lease_seconds,
            ollama_snapshot=ollama_snapshot,
        )

    if request.operation == "poll":
        _require_exact(payload, {"worker_id", "credential_token", "capabilities"})
        _require_token(payload["credential_token"], label="credential_token")
        capabilities = payload["capabilities"]
        if (
            not isinstance(capabilities, list)
            or len(capabilities) > 128
            or any(not isinstance(item, str) or not item or len(item) > 128 for item in capabilities)
        ):
            raise WorkerStdioGatewayError("invalid_capabilities")
        return backend.poll(
            worker_id=expected_worker_id,
            credential_token=payload["credential_token"],
            capabilities=capabilities,
        )

    if request.operation == "fetch_arguments":
        _require_exact(payload, {"worker_id", "credential_token", "lease", "offset"})
        _require_token(payload["credential_token"], label="credential_token")
        if not isinstance(payload["lease"], dict):
            raise WorkerStdioGatewayError("invalid_lease")
        offset = payload["offset"]
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise WorkerStdioGatewayError("invalid_offset")
        return backend.fetch_arguments(
            worker_id=expected_worker_id,
            credential_token=payload["credential_token"],
            lease=payload["lease"],
            offset=offset,
        )

    if request.operation == "authorize_execution":
        _require_exact(payload, {"worker_id", "credential_token", "lease", "execution_ticket"})
        _require_token(payload["credential_token"], label="credential_token")
        _require_token(payload["execution_ticket"], label="execution_ticket")
        if not isinstance(payload["lease"], dict):
            raise WorkerStdioGatewayError("invalid_lease")
        return backend.authorize_execution(
            worker_id=expected_worker_id,
            credential_token=payload["credential_token"],
            lease=payload["lease"],
            execution_ticket=payload["execution_ticket"],
        )

    if request.operation == "upload_result_piece":
        _require_exact(payload, {
            "worker_id", "credential_token", "lease", "execution_ticket", "offset", "chunk",
        })
        _require_token(payload["credential_token"], label="credential_token")
        _require_token(payload["execution_ticket"], label="execution_ticket")
        if not isinstance(payload["lease"], dict):
            raise WorkerStdioGatewayError("invalid_lease")
        offset = payload["offset"]
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise WorkerStdioGatewayError("invalid_offset")
        if not isinstance(payload["chunk"], str) or not payload["chunk"]:
            raise WorkerStdioGatewayError("invalid_chunk")
        return backend.upload_result_piece(
            worker_id=expected_worker_id,
            credential_token=payload["credential_token"],
            lease=payload["lease"],
            execution_ticket=payload["execution_ticket"],
            offset=offset,
            chunk=payload["chunk"],
        )

    if request.operation == "submit_result":
        # result_bytes (optional) means the result was sent earlier with
        # upload_result_piece and "result" is null.
        if set(payload) not in (_SUBMIT_RESULT_FIELDS, _SUBMIT_RESULT_FIELDS | {"result_bytes"}):
            raise WorkerStdioGatewayError("invalid_payload_schema")
        extra = {}
        if "result_bytes" in payload:
            result_bytes = payload["result_bytes"]
            if (
                not isinstance(result_bytes, int) or isinstance(result_bytes, bool)
                or result_bytes < 1 or payload["result"] is not None
            ):
                raise WorkerStdioGatewayError("invalid_result_bytes")
            extra["result_bytes"] = result_bytes
        _require_token(payload["credential_token"], label="credential_token")
        _require_token(payload["execution_ticket"], label="execution_ticket")
        if not isinstance(payload["lease"], dict) or not isinstance(payload["envelope"], dict):
            raise WorkerStdioGatewayError("invalid_result_envelope")
        if not isinstance(payload["success"], bool):
            raise WorkerStdioGatewayError("invalid_success")
        if payload["error"] is not None and (
            not isinstance(payload["error"], str) or len(payload["error"]) > 4096
        ):
            raise WorkerStdioGatewayError("invalid_error")
        return backend.submit_result(
            worker_id=expected_worker_id,
            credential_token=payload["credential_token"],
            lease=payload["lease"],
            execution_ticket=payload["execution_ticket"],
            result=payload["result"],
            envelope=payload["envelope"],
            success=payload["success"],
            error=payload["error"],
            **extra,
        )

    raise WorkerStdioGatewayError("operation_not_allowed")


def _response(request_id: str, *, ok: bool, result=None, error=None) -> bytes:
    body = {
        "version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": bool(ok),
    }
    if ok:
        body["result"] = result
    else:
        body["error"] = error or "gateway_refused"
    raw = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_FRAME_BYTES:
        raise WorkerStdioGatewayError("response_too_large")
    return raw


def serve_one(*, backend, expected_worker_id: str, stdin=None, stdout=None) -> int:
    """Serve exactly one request and exit; never disclose backend exceptions."""
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    raw = stdin.read(MAX_FRAME_BYTES + 1)
    request_id = "unknown"
    try:
        request = _parse_request(raw)
        request_id = request.request_id
        result = dispatch_request(request, backend=backend, expected_worker_id=expected_worker_id)
        output = _response(request_id, ok=True, result=result)
        exit_code = 0
    except WorkerStdioGatewayError as exc:
        output = _response(request_id, ok=False, error=str(exc))
        exit_code = 2
    except Exception:
        # Never expose coordinator internals, database errors, stack traces, or
        # credentials across the SSH boundary.
        output = _response(request_id, ok=False, error="coordinator_refused")
        exit_code = 3
    stdout.write(output)
    stdout.flush()
    return exit_code
