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
    CLAIMED = "CLAIMED"
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
    version: int = 0

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
    """KARMO approval engine with optional injected durable persistence.

    The engine owns approval semantics. A persistence adapter may be supplied
    to make approval truth survive process restart; the adapter never decides
    authority or transitions. With no adapter the engine remains suitable for
    isolated unit/dev use.
    """

    def __init__(self, *, clock=None, default_ttl_seconds=3600, store=None):
        self._records: dict[str, ApprovalRecord] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._default_ttl_seconds = default_ttl_seconds
        self._store = store

    @staticmethod
    def _require_nonempty_text(label, value):
        if not isinstance(value, str) or not value.strip():
            raise CoreControlError(f"{label} must be a non-empty string")
        return value

    def _persist(self, record: ApprovalRecord, *, expected_version):
        """Compare-and-swap write. ``expected_version`` is the version this
        record held immediately before the mutation being persisted; ``None``
        means "must not already exist" (first save). A stale writer -- one
        whose expected_version no longer matches durable truth because
        another writer committed first -- fails closed with CoreControlError
        rather than silently overwriting newer state."""
        if self._store is not None:
            record.version = self._store.save(record, expected_version=expected_version)
        else:
            current = self._records.get(record.approval_id)
            current_version = current.version if current is not None else None
            if current_version != expected_version:
                raise CoreControlError(
                    f"approval version conflict for {record.approval_id}: "
                    f"expected {expected_version}, found {current_version}"
                )
            record.version = 1 if expected_version is None else expected_version + 1
        self._records[record.approval_id] = record

    def request(self, *, requester, tool_id, tool_version, arguments, authority_class, ttl_seconds=None):
        self._require_nonempty_text("requester", requester)
        self._require_nonempty_text("tool_id", tool_id)
        self._require_nonempty_text("tool_version", tool_version)
        self._require_nonempty_text("authority_class", authority_class)
        if not isinstance(arguments, dict):
            raise CoreControlError("arguments must be an object")

        now = self._clock()
        ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or ttl <= 0:
            raise CoreControlError("ttl_seconds must be a positive number")
        record = ApprovalRecord(
            approval_id=str(uuid.uuid4()),
            requester=requester,
            tool_id=tool_id,
            tool_version=tool_version,
            arguments_digest=arguments_digest(tool_id, tool_version, arguments),
            authority_class=authority_class,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        record.audit_trail.append({
            "timestamp": now.isoformat(),
            "from_state": None,
            "to_state": "REQUESTED",
            "actor": requester,
            "note": "requested",
        })
        self._persist(record, expected_version=None)
        return record

    def _get(self, approval_id):
        if self._store is not None:
            # Durable truth may have moved under a cached local copy (another
            # writer/process, or the atomic execution-claim coordinator
            # writing directly). Always defer to the store rather than trust
            # a potentially stale in-process cache.
            record = self.refresh(approval_id)
        else:
            record = self._records.get(approval_id)
            if record is None:
                raise CoreControlError(f"no such approval: {approval_id}")
        if record.state in (ApprovalState.REQUESTED, ApprovalState.APPROVED) and self._clock() >= record.expires_at:
            expected_version = record.version
            record.transition(ApprovalState.EXPIRED, "system", "ttl elapsed", self._clock())
            self._persist(record, expected_version=expected_version)
        return record

    def refresh(self, approval_id):
        """Reload durable approval truth after an external transactional coordinator updates it."""
        if self._store is None:
            return self._get(approval_id)
        record = self._store.get(approval_id)
        if record is None:
            raise CoreControlError(f"no such approval: {approval_id}")
        self._records[approval_id] = record
        return record

    def approve(self, approval_id, *, approver, authorized_executor=None):
        self._require_nonempty_text("approver", approver)
        if authorized_executor is not None:
            self._require_nonempty_text("authorized_executor", authorized_executor)
        record = self._get(approval_id)
        if record.state != ApprovalState.REQUESTED:
            raise CoreControlError(f"cannot approve from {record.state.value}")
        expected_version = record.version
        record.approver = approver
        record.authorized_executor = authorized_executor or record.requester
        record.transition(ApprovalState.APPROVED, approver, "approved", self._clock())
        self._persist(record, expected_version=expected_version)
        return record

    def deny(self, approval_id, *, approver, reason="denied"):
        self._require_nonempty_text("approver", approver)
        self._require_nonempty_text("reason", reason)
        record = self._get(approval_id)
        if record.state != ApprovalState.REQUESTED:
            raise CoreControlError(f"cannot deny from {record.state.value}")
        expected_version = record.version
        record.approver = approver
        record.authorized_executor = None
        record.transition(ApprovalState.DENIED, approver, reason, self._clock())
        self._persist(record, expected_version=expected_version)
        return record

    def cancel(self, approval_id, *, actor, reason="cancelled"):
        self._require_nonempty_text("actor", actor)
        self._require_nonempty_text("reason", reason)
        record = self._get(approval_id)
        if record.state not in (ApprovalState.REQUESTED, ApprovalState.APPROVED):
            raise CoreControlError(f"cannot cancel from {record.state.value}")
        allowed_actors = {record.requester}
        if record.approver:
            allowed_actors.add(record.approver)
        if actor not in allowed_actors:
            raise CoreControlError("actor is not authorized to cancel this approval")
        expected_version = record.version
        record.authorized_executor = None
        record.transition(ApprovalState.CANCELLED, actor, reason, self._clock())
        self._persist(record, expected_version=expected_version)
        return record

    def execute(self, approval_id, *, tool_id, tool_version, arguments, executor_identity, action):
        record = self._get(approval_id)
        if record.state != ApprovalState.APPROVED:
            raise CoreControlError(f"cannot execute from {record.state.value}")
        expected_version = record.version
        if executor_identity != record.authorized_executor:
            record.transition(ApprovalState.FAILED, "system", "executor identity mismatch", self._clock())
            self._persist(record, expected_version=expected_version)
            raise CoreControlError("executor identity mismatch; approval invalidated")
        if arguments_digest(tool_id, tool_version, arguments) != record.arguments_digest:
            record.transition(ApprovalState.FAILED, "system", "tool/argument mismatch", self._clock())
            self._persist(record, expected_version=expected_version)
            raise CoreControlError("tool/argument mismatch; approval invalidated")

        record.execution_binding = str(uuid.uuid5(uuid.NAMESPACE_URL, f"approval:{approval_id}"))
        record.transition(ApprovalState.CLAIMED, "system", "execution authority claimed", self._clock())
        self._persist(record, expected_version=expected_version)
        expected_version = record.version
        try:
            result = action()
        except Exception as exc:
            record.transition(ApprovalState.FAILED, "system", f"execution raised: {exc}", self._clock())
            self._persist(record, expected_version=expected_version)
            raise
        record.transition(ApprovalState.EXECUTED, "system", "executed", self._clock())
        self._persist(record, expected_version=expected_version)
        return result

    def get(self, approval_id):
        return self._get(approval_id)
