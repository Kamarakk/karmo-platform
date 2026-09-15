from types import SimpleNamespace

import pytest

from core_service.control import ApprovalEngine, ApprovalRequirement, CapabilityClass
from core_service.dispatcher import CapabilityDispatcher, DispatchError


class Registry:
    def get(self, tool_id, version):
        if (tool_id, version) != ("karmolab.host_health", "1"):
            return None
        return SimpleNamespace(
            deprecated=False,
            computed_approval_requirement=ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
        )


def _dispatcher(handler):
    return CapabilityDispatcher(
        registry=Registry(),
        approval_engine=ApprovalEngine(),
        handlers={("karmolab.host_health", "1"): handler},
    )


def test_approval_cannot_be_reused_by_different_requester():
    calls = []
    dispatcher = _dispatcher(lambda args: calls.append(dict(args)) or {"ok": True})

    pending = dispatcher.dispatch(
        requester="alice",
        tool_id="karmolab.host_health",
        version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
    )
    dispatcher.approval_engine.approve(
        pending.approval_id,
        approver="operator",
        authorized_executor="worker-1",
    )

    with pytest.raises(DispatchError, match="approval requester mismatch"):
        dispatcher.dispatch(
            requester="bob",
            tool_id="karmolab.host_health",
            version="1",
            arguments={"host": "karmo-ai01"},
            executor_identity="worker-1",
            approval_id=pending.approval_id,
        )

    assert calls == []
    assert dispatcher.approval_engine.get(pending.approval_id).requester == "alice"


def test_approval_cannot_cross_computed_authority_requirement():
    calls = []
    dispatcher = _dispatcher(lambda args: calls.append(dict(args)) or {"ok": True})
    approval = dispatcher.approval_engine.request(
        requester="alice",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments={"host": "karmo-ai01"},
        authority_class=ApprovalRequirement.EXPLICIT_PER_CALL.value,
    )
    dispatcher.approval_engine.approve(
        approval.approval_id,
        approver="operator",
        authorized_executor="worker-1",
    )

    with pytest.raises(DispatchError, match="approval authority requirement mismatch"):
        dispatcher.dispatch(
            requester="alice",
            tool_id="karmolab.host_health",
            version="1",
            arguments={"host": "karmo-ai01"},
            executor_identity="worker-1",
            approval_id=approval.approval_id,
        )

    assert calls == []
    assert dispatcher.approval_engine.get(approval.approval_id).state.value == "APPROVED"


def test_original_requester_can_use_same_approved_authority():
    calls = []
    dispatcher = _dispatcher(lambda args: calls.append(dict(args)) or {"ok": True})

    pending = dispatcher.dispatch(
        requester="alice",
        tool_id="karmolab.host_health",
        version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
    )
    dispatcher.approval_engine.approve(
        pending.approval_id,
        approver="operator",
        authorized_executor="worker-1",
    )

    decision = dispatcher.dispatch(
        requester="alice",
        tool_id="karmolab.host_health",
        version="1",
        arguments={"host": "karmo-ai01"},
        executor_identity="worker-1",
        approval_id=pending.approval_id,
    )

    assert decision.executed is True
    assert calls == [{"host": "karmo-ai01"}]
    assert dispatcher.approval_engine.get(pending.approval_id).state.value == "EXECUTED"
