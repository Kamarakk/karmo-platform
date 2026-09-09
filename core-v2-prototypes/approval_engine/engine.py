"""KARMO Approval Engine -- ISOLATED PROTOTYPE.

Not wired into any KARMO production path; no real external action is
ever performed by this module. Implements the generic human-approval
mechanism future Core v2 tools will use, per
docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md's authorization-record
shape (itself reused from the Mandatory Production Access Authorization
Gate).

Critical guarantees this module exists to prove:
- Approval for action A must not authorize action B (enforced by binding
  an approval to an exact arguments digest, recomputed and compared at
  execution time -- not merely trusted from what was requested).
- Changing material arguments after approval invalidates the approval
  (a digest mismatch at execution time consumes the approval into FAILED,
  it does not leave it usable for a later, correct attempt).
- Single-use: one execute() call per approval, ever. A second attempt --
  win or lose on the first -- is refused, not silently retried.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


class ApprovalState(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = {
    ApprovalState.DENIED,
    ApprovalState.EXPIRED,
    ApprovalState.EXECUTED,
    ApprovalState.FAILED,
    ApprovalState.CANCELLED,
}


class ApprovalStateError(RuntimeError):
    """Refuse-don't-guess: raised whenever a transition is attempted from
    a state that does not permit it, or an execution's arguments don't
    match what was actually approved."""


def arguments_digest(tool_id, tool_version, arguments):
    """Deterministic, canonical digest binding an approval to an exact
    tool + version + argument set. Same sha256-of-canonical-content
    pattern already used throughout KARMO (H0.1's content_sha256, H0.2's
    document_hash) -- reused, not reinvented."""
    canonical = json.dumps(
        {"tool_id": tool_id, "tool_version": tool_version, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ApprovalRecord:
    approval_id: str
    requester: str
    tool_id: str
    tool_version: str
    arguments_digest: str
    authority_class: str  # the tool's capability_class at request time
    created_at: datetime
    expires_at: datetime
    state: ApprovalState = ApprovalState.REQUESTED
    approver: str = None
    execution_binding: str = None  # deterministic invocation id, set only on EXECUTED
    audit_trail: list = field(default_factory=list)

    def _record(self, from_state, to_state, actor, note, now):
        self.audit_trail.append(
            {
                "timestamp": now.isoformat(),
                "from_state": from_state.value,
                "to_state": to_state.value,
                "actor": actor,
                "note": note,
            }
        )
        self.state = to_state


class ApprovalEngine:
    """In-memory prototype (a real implementation would use a
    public.approval_ledger table, append-only, mirroring every other
    KARMO audit-trail design)."""

    def __init__(self, *, clock=None, default_ttl_seconds=3600):
        self._approvals = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._default_ttl_seconds = default_ttl_seconds

    def _now(self):
        return self._clock()

    def _get_or_raise(self, approval_id):
        record = self._approvals.get(approval_id)
        if record is None:
            raise ApprovalStateError(f"no such approval: {approval_id}")
        self._apply_lazy_expiry(record)
        return record

    def _apply_lazy_expiry(self, record):
        """Expiry is checked lazily, on every access -- not by a
        background timer this prototype doesn't need. A record still
        REQUESTED or APPROVED past its expires_at is transitioned to
        EXPIRED before any other logic runs against it."""
        if record.state in (ApprovalState.REQUESTED, ApprovalState.APPROVED):
            now = self._now()
            if now >= record.expires_at:
                record._record(record.state, ApprovalState.EXPIRED, "system", "ttl elapsed", now)

    def request(self, *, requester, tool_id, tool_version, arguments, authority_class, ttl_seconds=None):
        now = self._now()
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
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
        record.audit_trail.append(
            {
                "timestamp": now.isoformat(),
                "from_state": None,
                "to_state": ApprovalState.REQUESTED.value,
                "actor": requester,
                "note": "requested",
            }
        )
        self._approvals[record.approval_id] = record
        return record

    def approve(self, approval_id, *, approver):
        record = self._get_or_raise(approval_id)
        if record.state != ApprovalState.REQUESTED:
            raise ApprovalStateError(
                f"cannot approve from state {record.state.value} (must be REQUESTED)"
            )
        record.approver = approver
        record._record(ApprovalState.REQUESTED, ApprovalState.APPROVED, approver, "approved", self._now())
        return record

    def deny(self, approval_id, *, approver, reason=""):
        record = self._get_or_raise(approval_id)
        if record.state != ApprovalState.REQUESTED:
            raise ApprovalStateError(
                f"cannot deny from state {record.state.value} (must be REQUESTED)"
            )
        record._record(ApprovalState.REQUESTED, ApprovalState.DENIED, approver, reason or "denied", self._now())
        return record

    def cancel(self, approval_id, *, actor, reason=""):
        record = self._get_or_raise(approval_id)
        if record.state not in (ApprovalState.REQUESTED, ApprovalState.APPROVED):
            raise ApprovalStateError(
                f"cannot cancel from state {record.state.value}"
            )
        record._record(record.state, ApprovalState.CANCELLED, actor, reason or "cancelled", self._now())
        return record

    def execute(self, approval_id, *, tool_id, tool_version, arguments, executor):
        """executor: a zero-argument callable performing the (synthetic,
        in this prototype) action. Its return value becomes the result;
        an exception it raises transitions the approval to FAILED and is
        re-raised.

        Single-use, by construction: this function only ever transitions
        a record OUT of APPROVED, exactly once. Any second call against
        the same approval_id finds a non-APPROVED state and refuses.
        """
        record = self._get_or_raise(approval_id)

        if record.state != ApprovalState.APPROVED:
            raise ApprovalStateError(
                f"cannot execute from state {record.state.value} (must be APPROVED) -- "
                "either not yet approved, already used, or the approval was denied/"
                "expired/cancelled"
            )

        # Approval for action A must not authorize action B: recompute
        # the digest from what is ACTUALLY about to run, compare against
        # what was actually approved. Any mismatch -- different tool,
        # different version, or ANY changed argument -- invalidates the
        # approval rather than merely refusing this one call.
        attempted_digest = arguments_digest(tool_id, tool_version, arguments)
        if attempted_digest != record.arguments_digest:
            record._record(
                ApprovalState.APPROVED,
                ApprovalState.FAILED,
                "system",
                "arguments/tool mismatch at execution time -- approval invalidated, not merely refused",
                self._now(),
            )
            raise ApprovalStateError(
                "execution arguments do not match what was approved -- "
                "approval has been invalidated"
            )

        invocation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"approval:{approval_id}"))

        try:
            result = executor()
        except Exception as error:
            record._record(
                ApprovalState.APPROVED,
                ApprovalState.FAILED,
                "system",
                f"execution raised: {error}",
                self._now(),
            )
            raise

        record.execution_binding = invocation_id
        record._record(ApprovalState.APPROVED, ApprovalState.EXECUTED, "system", "executed", self._now())
        return result

    def get(self, approval_id):
        return self._get_or_raise(approval_id)
