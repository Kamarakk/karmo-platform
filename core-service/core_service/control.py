"""Bounded production Core control semantics.

No network, database, Qdrant, secrets, or external side effects live here.
The implementation adopts the already-verified Core v2 prototype semantics
behind a stable package boundary without importing the prototype tree at
runtime.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


class CapabilityClass(str, Enum):
    READ = "READ"
    DRAFT_PROPOSE = "DRAFT_PROPOSE"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    DESTRUCTIVE_HIGH_IMPACT = "DESTRUCTIVE_HIGH_IMPACT"


class ApprovalRequirement(str, Enum):
    NONE = "NONE"
    NOTIFY_ONLY = "NOTIFY_ONLY"
    EXPLICIT_PER_SESSION_OR_TASK = "EXPLICIT_PER_SESSION_OR_TASK"
    EXPLICIT_PER_CALL = "EXPLICIT_PER_CALL"


_APPROVAL_ORDER = [
    ApprovalRequirement.NONE,
    ApprovalRequirement.NOTIFY_ONLY,
    ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
    ApprovalRequirement.EXPLICIT_PER_CALL,
]

_CAPABILITY_FLOOR = {
    CapabilityClass.READ: ApprovalRequirement.NONE,
    CapabilityClass.DRAFT_PROPOSE: ApprovalRequirement.NOTIFY_ONLY,
    CapabilityClass.REVERSIBLE_WRITE: ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
    CapabilityClass.EXTERNAL_ACTION: ApprovalRequirement.EXPLICIT_PER_CALL,
    CapabilityClass.DESTRUCTIVE_HIGH_IMPACT: ApprovalRequirement.EXPLICIT_PER_CALL,
}


class CoreControlError(RuntimeError):
    pass


def compute_approval_requirement(capability_class: CapabilityClass, *, financial_action=False, destructive_action=False):
    candidates = [_CAPABILITY_FLOOR[capability_class]]
    if financial_action or destructive_action:
        candidates.append(ApprovalRequirement.EXPLICIT_PER_CALL)
    return max(candidates, key=_APPROVAL_ORDER.index)


def arguments_digest(tool_id: str, tool_version: str, arguments: dict) -> str:
    canonical = json.dumps(
        {"tool_id": tool_id, "tool_version": tool_version, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ApprovalState(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ApprovalRecord:
    approval_id: str
    requester: str
    tool_id: str
    tool_version: str
    arguments_digest: str
    authority_class: str
    created_at: datetime
    expires_at: datetime
    state: ApprovalState = ApprovalState.REQUESTED
    approver: str | None = None
    authorized_executor: str | None = None
    execution_binding: str | None = None
    audit_trail: list[dict] = field(default_factory=list)

    def transition(self, to_state: ApprovalState, actor: str, note: str, now: datetime):
        self.audit_trail.append({
            "timestamp": now.isoformat(),
            "from_state": self.state.value,
            "to_state": to_state.value,
            "actor": actor,
            "note": note,
        })
        self.state = to_state


class ApprovalEngine:
    """Local in-memory v0.1 approval engine.

    Persistence is intentionally deferred rather than silently added to the
    approved no-database-migration rollout.
    """

    def __init__(self, *, clock=None, default_ttl_seconds=3600):
        self._records: dict[str, ApprovalRecord] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._default_ttl_seconds = default_ttl_seconds

    def request(self, *, requester, tool_id, tool_version, arguments, authority_class, ttl_seconds=None):
        now = self._clock()
        record = ApprovalRecord(
            approval_id=str(uuid.uuid4()),
            requester=requester,
            tool_id=tool_id,
            tool_version=tool_version,
            arguments_digest=arguments_digest(tool_id, tool_version, arguments),
            authority_class=authority_class,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds or self._default_ttl_seconds),
        )
        record.audit_trail.append({"timestamp": now.isoformat(), "from_state": None, "to_state": "REQUESTED", "actor": requester, "note": "requested"})
        self._records[record.approval_id] = record
        return record

    def _get(self, approval_id):
        try:
            record = self._records[approval_id]
        except KeyError as exc:
            raise CoreControlError(f"no such approval: {approval_id}") from exc
        if record.state in (ApprovalState.REQUESTED, ApprovalState.APPROVED) and self._clock() >= record.expires_at:
            record.transition(ApprovalState.EXPIRED, "system", "ttl elapsed", self._clock())
        return record

    def approve(self, approval_id, *, approver, authorized_executor=None):
        record = self._get(approval_id)
        if record.state != ApprovalState.REQUESTED:
            raise CoreControlError(f"cannot approve from {record.state.value}")
        record.approver = approver
        record.authorized_executor = authorized_executor or record.requester
        record.transition(ApprovalState.APPROVED, approver, "approved", self._clock())
        return record

    def execute(self, approval_id, *, tool_id, tool_version, arguments, executor_identity, action):
        record = self._get(approval_id)
        if record.state != ApprovalState.APPROVED:
            raise CoreControlError(f"cannot execute from {record.state.value}")
        if executor_identity != record.authorized_executor:
            record.transition(ApprovalState.FAILED, "system", "executor identity mismatch", self._clock())
            raise CoreControlError("executor identity mismatch; approval invalidated")
        if arguments_digest(tool_id, tool_version, arguments) != record.arguments_digest:
            record.transition(ApprovalState.FAILED, "system", "tool/argument mismatch", self._clock())
            raise CoreControlError("tool/argument mismatch; approval invalidated")
        try:
            result = action()
        except Exception as exc:
            record.transition(ApprovalState.FAILED, "system", f"execution raised: {exc}", self._clock())
            raise
        record.execution_binding = str(uuid.uuid5(uuid.NAMESPACE_URL, f"approval:{approval_id}"))
        record.transition(ApprovalState.EXECUTED, "system", "executed", self._clock())
        return result

    def get(self, approval_id):
        return self._get(approval_id)
