"""Cryptographic boundary primitives for future KARMO Worker networking.

Secrets are injected by the trusted runtime and are never stored in source.
This module uses versioned HMAC-SHA256 envelopes to provide proof-of-possession
worker credentials, short-lived execution tickets, and worker-bound result
authenticity without granting any authority by network position alone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


class CryptoBoundaryError(RuntimeError):
    pass


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sign(secret: bytes, payload: dict) -> str:
    return hmac.new(secret, _canonical(payload), hashlib.sha256).hexdigest()


def _encode(payload: dict, secret: bytes) -> str:
    envelope = {"payload": payload, "signature": _sign(secret, payload)}
    return _b64encode(_canonical(envelope))


def _decode(token: str) -> dict:
    try:
        envelope = json.loads(_b64decode(token).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 -- all malformed input must fail closed
        raise CryptoBoundaryError("malformed cryptographic envelope") from exc
    if set(envelope) != {"payload", "signature"} or not isinstance(envelope["payload"], dict):
        raise CryptoBoundaryError("invalid cryptographic envelope schema")
    return envelope


class KeyResolver:
    """Resolve key bytes by key_id without exposing how secrets are stored."""

    def __init__(self, resolver):
        if not callable(resolver):
            raise CryptoBoundaryError("key resolver must be callable")
        self._resolver = resolver

    def get(self, key_id: str) -> bytes:
        secret = self._resolver(key_id)
        if not isinstance(secret, (bytes, bytearray)) or len(secret) < 32:
            raise CryptoBoundaryError("unknown or insufficient key material")
        return bytes(secret)


class WorkerAuthenticator:
    def __init__(self, key_resolver: KeyResolver, *, clock=time.time):
        self.keys = key_resolver
        self.clock = clock

    def issue(self, *, worker_id: str, key_id: str, ttl_seconds=3600) -> str:
        now = int(self.clock())
        payload = {
            "type": "worker_credential",
            "version": 1,
            "worker_id": worker_id,
            "key_id": key_id,
            "issued_at": now,
            "expires_at": now + int(ttl_seconds),
            "nonce": secrets.token_hex(16),
        }
        return _encode(payload, self.keys.get(key_id))

    def verify(self, token: str, *, expected_worker_id: str) -> dict:
        envelope = _decode(token)
        payload = envelope["payload"]
        required = {"type", "version", "worker_id", "key_id", "issued_at", "expires_at", "nonce"}
        if set(payload) != required or payload["type"] != "worker_credential" or payload["version"] != 1:
            raise CryptoBoundaryError("invalid worker credential payload")
        secret = self.keys.get(payload["key_id"])
        if not hmac.compare_digest(envelope["signature"], _sign(secret, payload)):
            raise CryptoBoundaryError("worker credential signature mismatch")
        if payload["worker_id"] != expected_worker_id:
            raise CryptoBoundaryError("worker credential identity mismatch")
        now = int(self.clock())
        if now < int(payload["issued_at"]) or now >= int(payload["expires_at"]):
            raise CryptoBoundaryError("worker credential expired or not yet valid")
        return dict(payload)


class ExecutionTicketAuthority:
    """Coordinator-issued, short-lived execution authorization envelope."""

    def __init__(self, key_resolver: KeyResolver, *, signing_key_id: str, clock=time.time):
        self.keys = key_resolver
        self.signing_key_id = signing_key_id
        self.clock = clock

    def issue(self, *, approval_id: str, arguments_digest: str, executor_identity: str, task_id: str, ttl_seconds=120):
        now = int(self.clock())
        payload = {
            "type": "execution_ticket",
            "version": 1,
            "key_id": self.signing_key_id,
            "approval_id": approval_id,
            "arguments_digest": arguments_digest,
            "executor_identity": executor_identity,
            "task_id": task_id,
            "issued_at": now,
            "expires_at": now + int(ttl_seconds),
            "nonce": secrets.token_hex(16),
        }
        return _encode(payload, self.keys.get(self.signing_key_id))

    def verify(self, token: str, *, approval_id: str, arguments_digest: str, executor_identity: str, task_id: str):
        envelope = _decode(token)
        payload = envelope["payload"]
        if payload.get("type") != "execution_ticket" or payload.get("version") != 1:
            raise CryptoBoundaryError("invalid execution ticket")
        secret = self.keys.get(payload.get("key_id"))
        if not hmac.compare_digest(envelope["signature"], _sign(secret, payload)):
            raise CryptoBoundaryError("execution ticket signature mismatch")
        expected = {
            "approval_id": approval_id,
            "arguments_digest": arguments_digest,
            "executor_identity": executor_identity,
            "task_id": task_id,
        }
        for field, value in expected.items():
            if payload.get(field) != value:
                raise CryptoBoundaryError(f"execution ticket {field} mismatch")
        now = int(self.clock())
        if now < int(payload["issued_at"]) or now >= int(payload["expires_at"]):
            raise CryptoBoundaryError("execution ticket expired or not yet valid")
        return dict(payload)


class ResultAuthenticator:
    """Bind reported output to a worker credential key without trusting a digest supplied by the worker."""

    def __init__(self, key_resolver: KeyResolver):
        self.keys = key_resolver

    @staticmethod
    def result_digest(result) -> str:
        return hashlib.sha256(_canonical({"result": result})).hexdigest()

    def sign(self, *, worker_id: str, key_id: str, task_id: str, result) -> dict:
        payload = {
            "type": "worker_result",
            "version": 1,
            "worker_id": worker_id,
            "key_id": key_id,
            "task_id": task_id,
            "result_digest": self.result_digest(result),
        }
        return {"payload": payload, "signature": _sign(self.keys.get(key_id), payload)}

    def verify(self, envelope: dict, *, worker_id: str, task_id: str, result):
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise CryptoBoundaryError("invalid result-authentication envelope")
        payload = envelope["payload"]
        if payload.get("worker_id") != worker_id or payload.get("task_id") != task_id:
            raise CryptoBoundaryError("result identity/task mismatch")
        if payload.get("result_digest") != self.result_digest(result):
            raise CryptoBoundaryError("result digest mismatch")
        secret = self.keys.get(payload.get("key_id"))
        if not hmac.compare_digest(envelope["signature"], _sign(secret, payload)):
            raise CryptoBoundaryError("result signature mismatch")
        return True
