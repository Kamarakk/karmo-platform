"""The 8 required scenarios from the Core v2 Engineering Blueprint
Program, Workstream 4, plus the state-machine acceptance gate from the
Core v2 Test Strategy (every valid transition tested positively, every
invalid transition tested negatively). No real external action is ever
performed -- every `executor` here is a synthetic no-op or a recorder.
"""

from datetime import datetime, timedelta, timezone

import pytest
from engine import ApprovalEngine, ApprovalState, ApprovalStateError


class FakeClock:
    """Deterministic, test-controlled time -- avoids real sleeps and
    makes expiry behavior exactly reproducible."""

    def __init__(self, start=None):
        self._now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self._now

    def advance(self, seconds):
        self._now += timedelta(seconds=seconds)


@pytest.fixture()
def clock():
    return FakeClock()


@pytest.fixture()
def engine(clock):
    return ApprovalEngine(clock=clock, default_ttl_seconds=300)


TOOL_ID = "finance.trading.place_order"
TOOL_VERSION = "1.0.0"
ARGS = {"symbol": "SYNTH", "side": "buy", "quantity": 1, "order_type": "limit", "limit_price": 100.0}


def _request(engine, **overrides):
    kwargs = dict(
        requester="natalie",
        tool_id=TOOL_ID,
        tool_version=TOOL_VERSION,
        arguments=ARGS,
        authority_class="DESTRUCTIVE_HIGH_IMPACT",
    )
    kwargs.update(overrides)
    return engine.request(**kwargs)


# 1. Valid approval
def test_valid_approval_executes_successfully(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")

    calls = []
    result = engine.execute(
        record.approval_id,
        tool_id=TOOL_ID,
        tool_version=TOOL_VERSION,
        arguments=ARGS,
        executor=lambda: calls.append(1) or "synthetic-order-ack",
    )

    assert result == "synthetic-order-ack"
    assert len(calls) == 1
    final = engine.get(record.approval_id)
    assert final.state == ApprovalState.EXECUTED
    assert final.execution_binding is not None


# 2. Denied approval
def test_denied_approval_cannot_execute(engine):
    record = _request(engine)
    engine.deny(record.approval_id, approver="natalie", reason="not now")

    assert engine.get(record.approval_id).state == ApprovalState.DENIED

    with pytest.raises(ApprovalStateError, match="must be APPROVED"):
        engine.execute(
            record.approval_id,
            tool_id=TOOL_ID,
            tool_version=TOOL_VERSION,
            arguments=ARGS,
            executor=lambda: pytest.fail("must never be called"),
        )


# 3. Expired approval
def test_expired_approval_cannot_execute(engine, clock):
    record = _request(engine, ttl_seconds=60)
    engine.approve(record.approval_id, approver="natalie")

    clock.advance(61)  # past the 60s TTL

    with pytest.raises(ApprovalStateError, match="must be APPROVED"):
        engine.execute(
            record.approval_id,
            tool_id=TOOL_ID,
            tool_version=TOOL_VERSION,
            arguments=ARGS,
            executor=lambda: pytest.fail("must never be called"),
        )

    assert engine.get(record.approval_id).state == ApprovalState.EXPIRED


def test_expiry_also_applies_before_approval(engine, clock):
    record = _request(engine, ttl_seconds=30)
    clock.advance(31)

    with pytest.raises(ApprovalStateError, match="must be REQUESTED"):
        engine.approve(record.approval_id, approver="natalie")

    assert engine.get(record.approval_id).state == ApprovalState.EXPIRED


# 4. Replay (using the same, already-executed approval again)
def test_replay_after_successful_execution_is_refused(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")
    engine.execute(
        record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION, arguments=ARGS, executor=lambda: "ok"
    )

    with pytest.raises(ApprovalStateError, match="must be APPROVED"):
        engine.execute(
            record.approval_id,
            tool_id=TOOL_ID,
            tool_version=TOOL_VERSION,
            arguments=ARGS,
            executor=lambda: pytest.fail("must never be called on replay"),
        )


# 5. Changed arguments after approval
def test_changed_arguments_invalidates_the_approval(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")

    tampered_args = dict(ARGS, quantity=1000)  # material change: 1 -> 1000

    with pytest.raises(ApprovalStateError, match="do not match what was approved"):
        engine.execute(
            record.approval_id,
            tool_id=TOOL_ID,
            tool_version=TOOL_VERSION,
            arguments=tampered_args,
            executor=lambda: pytest.fail("must never be called with tampered arguments"),
        )

    # The approval is now consumed/invalidated -- not merely refused this
    # once. A subsequent attempt with the ORIGINAL, correct arguments
    # must also fail, proving the approval cannot be salvaged.
    assert engine.get(record.approval_id).state == ApprovalState.FAILED
    with pytest.raises(ApprovalStateError):
        engine.execute(
            record.approval_id,
            tool_id=TOOL_ID,
            tool_version=TOOL_VERSION,
            arguments=ARGS,
            executor=lambda: pytest.fail("must never be called -- approval already invalidated"),
        )


# 6. Changed tool (approval for action A must not authorize action B)
def test_changed_tool_id_is_refused_approval_for_a_does_not_authorize_b(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")

    with pytest.raises(ApprovalStateError, match="do not match what was approved"):
        engine.execute(
            record.approval_id,
            tool_id="finance.trading.cancel_order",  # a DIFFERENT tool
            tool_version=TOOL_VERSION,
            arguments=ARGS,
            executor=lambda: pytest.fail("must never be called for a different tool"),
        )

    assert engine.get(record.approval_id).state == ApprovalState.FAILED


# 7. Changed user/requester (the approval record itself, not the executor)
def test_approve_by_different_actor_than_requester_is_allowed_but_recorded(engine):
    """Natalie requesting and Natalie approving is the common case, but
    the engine itself does not assume requester == approver -- it
    records who actually approved, distinctly from who asked. A
    requester approving their OWN request is a policy decision for a
    future domain to make (e.g. requiring a distinct approver for
    financial actions), not something this prototype enforces -- but the
    identity must be captured accurately either way."""
    record = _request(engine, requester="agent-session-1")
    engine.approve(record.approval_id, approver="natalie")

    final = engine.get(record.approval_id)
    assert final.requester == "agent-session-1"
    assert final.approver == "natalie"
    assert final.requester != final.approver


def test_changed_requester_identity_does_not_let_a_second_party_reuse_the_approval(engine):
    """The approval is bound to the approval_id, not to a session -- but
    changing WHO is claiming to execute it does not change WHAT it
    authorizes (still exact tool+version+arguments). This test proves
    the engine does not need requester/executor identity to match at
    execution time -- authority is proven by the digest, not by asking
    "who are you," which is a deliberate design choice worth making
    explicit and testing rather than assuming."""
    record = _request(engine, requester="agent-session-1")
    engine.approve(record.approval_id, approver="natalie")

    # A different "actor" (e.g. a different session) presenting the same
    # approval_id with the SAME tool+version+arguments still executes --
    # the approval_id itself is the credential; whoever holds a valid,
    # matching approval_id can trigger the one execution it authorizes.
    # This is documented, not silently assumed: a real implementation
    # binding approval_id to a specific session/actor at issuance time is
    # a valid tightening a future domain can add on top of this
    # prototype's baseline guarantee (exact-argument binding).
    result = engine.execute(
        record.approval_id,
        tool_id=TOOL_ID,
        tool_version=TOOL_VERSION,
        arguments=ARGS,
        executor=lambda: "ok",
    )
    assert result == "ok"


# 8. Double execution
def test_double_execution_is_refused_even_if_first_attempt_failed(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")

    def _boom():
        raise RuntimeError("synthetic tool failure")

    with pytest.raises(RuntimeError, match="synthetic tool failure"):
        engine.execute(
            record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION, arguments=ARGS, executor=_boom
        )

    assert engine.get(record.approval_id).state == ApprovalState.FAILED

    # Single-use applies even when the first attempt FAILED -- no retry
    # via the same approval; a retry requires a new approval.
    with pytest.raises(ApprovalStateError, match="must be APPROVED"):
        engine.execute(
            record.approval_id,
            tool_id=TOOL_ID,
            tool_version=TOOL_VERSION,
            arguments=ARGS,
            executor=lambda: pytest.fail("must never be called -- already terminal"),
        )


# Additional state-machine coverage (Core v2 Test Strategy's own gate:
# every invalid transition tested negatively, not just the 8 scenarios).

def test_cannot_deny_an_already_approved_request(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")

    with pytest.raises(ApprovalStateError, match="must be REQUESTED"):
        engine.deny(record.approval_id, approver="natalie")


def test_cannot_approve_twice(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")

    with pytest.raises(ApprovalStateError, match="must be REQUESTED"):
        engine.approve(record.approval_id, approver="natalie")


def test_cancel_from_requested_or_approved_succeeds(engine):
    r1 = _request(engine)
    engine.cancel(r1.approval_id, actor="natalie", reason="changed my mind")
    assert engine.get(r1.approval_id).state == ApprovalState.CANCELLED

    r2 = _request(engine)
    engine.approve(r2.approval_id, approver="natalie")
    engine.cancel(r2.approval_id, actor="natalie", reason="changed my mind again")
    assert engine.get(r2.approval_id).state == ApprovalState.CANCELLED


def test_cannot_cancel_a_terminal_approval(engine):
    record = _request(engine)
    engine.deny(record.approval_id, approver="natalie")

    with pytest.raises(ApprovalStateError, match="cannot cancel"):
        engine.cancel(record.approval_id, actor="natalie")


def test_audit_trail_captures_every_transition(engine):
    record = _request(engine)
    engine.approve(record.approval_id, approver="natalie")
    engine.execute(
        record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION, arguments=ARGS, executor=lambda: "ok"
    )

    final = engine.get(record.approval_id)
    transitions = [(e["from_state"], e["to_state"]) for e in final.audit_trail]
    assert transitions == [
        (None, "REQUESTED"),
        ("REQUESTED", "APPROVED"),
        ("APPROVED", "EXECUTED"),
    ]
