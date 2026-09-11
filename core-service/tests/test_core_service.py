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
