from core_service.control import (
    ApprovalEngine,
    ApprovalRequirement,
    ApprovalState,
    CapabilityClass,
    CoreControlError,
    compute_approval_requirement,
)


def test_approval_floor_cannot_be_lowered_by_high_impact_flags():
    assert compute_approval_requirement(CapabilityClass.READ) == ApprovalRequirement.NONE
    assert compute_approval_requirement(CapabilityClass.READ, financial_action=True) == ApprovalRequirement.EXPLICIT_PER_CALL
    assert compute_approval_requirement(CapabilityClass.REVERSIBLE_WRITE, destructive_action=True) == ApprovalRequirement.EXPLICIT_PER_CALL


def test_exact_binding_and_single_use():
    engine = ApprovalEngine()
    record = engine.request(
        requester="worker-1",
        tool_id="example.safe",
        tool_version="1",
        arguments={"value": 7},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )
    engine.approve(record.approval_id, approver="human", authorized_executor="worker-1")
    assert engine.execute(
        record.approval_id,
        tool_id="example.safe",
        tool_version="1",
        arguments={"value": 7},
        executor_identity="worker-1",
        action=lambda: "done",
    ) == "done"
    assert record.state == ApprovalState.EXECUTED
    try:
        engine.execute(
            record.approval_id,
            tool_id="example.safe",
            tool_version="1",
            arguments={"value": 7},
            executor_identity="worker-1",
            action=lambda: "again",
        )
    except CoreControlError:
        pass
    else:
        raise AssertionError("executed approval was reusable")


def test_changed_arguments_invalidate_approval():
    engine = ApprovalEngine()
    record = engine.request(
        requester="worker-1",
        tool_id="example.safe",
        tool_version="1",
        arguments={"value": 7},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )
    engine.approve(record.approval_id, approver="human")
    try:
        engine.execute(
            record.approval_id,
            tool_id="example.safe",
            tool_version="1",
            arguments={"value": 8},
            executor_identity="worker-1",
            action=lambda: None,
        )
    except CoreControlError:
        pass
    else:
        raise AssertionError("changed arguments were accepted")
    assert record.state == ApprovalState.FAILED


def test_denied_approval_is_terminal_and_cannot_execute_or_be_reapproved():
    engine = ApprovalEngine()
    record = engine.request(
        requester="worker-1",
        tool_id="example.safe",
        tool_version="1",
        arguments={"value": 7},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )

    engine.deny(record.approval_id, approver="human", reason="operator rejected request")
    assert record.state == ApprovalState.DENIED
    assert record.authorized_executor is None
    assert record.audit_trail[-1]["actor"] == "human"
    assert record.audit_trail[-1]["note"] == "operator rejected request"

    for operation in (
        lambda: engine.approve(record.approval_id, approver="other-human"),
        lambda: engine.execute(
            record.approval_id,
            tool_id="example.safe",
            tool_version="1",
            arguments={"value": 7},
            executor_identity="worker-1",
            action=lambda: "must-not-run",
        ),
    ):
        try:
            operation()
        except CoreControlError:
            pass
        else:
            raise AssertionError("denied approval was not terminal")


def test_requester_can_cancel_pending_request_and_terminal_state_blocks_execution():
    engine = ApprovalEngine()
    record = engine.request(
        requester="worker-1",
        tool_id="example.safe",
        tool_version="1",
        arguments={"value": 7},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )

    engine.cancel(record.approval_id, actor="worker-1", reason="request withdrawn")
    assert record.state == ApprovalState.CANCELLED
    assert record.authorized_executor is None

    try:
        engine.execute(
            record.approval_id,
            tool_id="example.safe",
            tool_version="1",
            arguments={"value": 7},
            executor_identity="worker-1",
            action=lambda: "must-not-run",
        )
    except CoreControlError:
        pass
    else:
        raise AssertionError("cancelled approval executed")


def test_approved_request_can_be_revoked_by_requester_or_approver_but_not_arbitrary_worker():
    engine = ApprovalEngine()
    record = engine.request(
        requester="worker-1",
        tool_id="example.safe",
        tool_version="1",
        arguments={"value": 7},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )
    engine.approve(record.approval_id, approver="human", authorized_executor="worker-1")

    try:
        engine.cancel(record.approval_id, actor="worker-2")
    except CoreControlError:
        pass
    else:
        raise AssertionError("unrelated actor cancelled approval")
    assert record.state == ApprovalState.APPROVED

    engine.cancel(record.approval_id, actor="human", reason="approval revoked")
    assert record.state == ApprovalState.CANCELLED
    assert record.authorized_executor is None

    try:
        engine.execute(
            record.approval_id,
            tool_id="example.safe",
            tool_version="1",
            arguments={"value": 7},
            executor_identity="worker-1",
            action=lambda: "must-not-run",
        )
    except CoreControlError:
        pass
    else:
        raise AssertionError("revoked approval executed")
