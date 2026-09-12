"""Independent verification gate for KARMO task results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class VerificationError(RuntimeError):
    pass


def canonical_digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerificationRecord:
    verifier_id: str
    subject_digest: str
    passed: bool
    findings: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


class VerificationGate:
    """Require a verifier distinct from the producer for trust elevation."""

    @staticmethod
    def verify(*, producer_id: str, verifier_id: str, subject, check):
        if not producer_id or not verifier_id:
            raise VerificationError("producer_id and verifier_id are required")
        if producer_id == verifier_id:
            raise VerificationError("self-verification is not allowed")
        result = check(subject)
        if not isinstance(result, dict) or "passed" not in result:
            raise VerificationError("verification check must return a dict containing 'passed'")
        findings = tuple(str(item) for item in result.get("findings", ()))
        evidence = tuple(str(item) for item in result.get("evidence", ()))
        return VerificationRecord(
            verifier_id=verifier_id,
            subject_digest=canonical_digest(subject),
            passed=bool(result["passed"]),
            findings=findings,
            evidence=evidence,
        )
