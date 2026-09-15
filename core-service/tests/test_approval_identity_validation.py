import pytest

from core_service.control import ApprovalEngine, CapabilityClass, CoreControlError


class CountingStore:
    def __init__(self):
        self.save_calls = 0
        self.records = {}

    def save(self, record, *, expected_version=None):
        self.save_calls += 1
        version = 1 if expected_version is None else expected_version + 1
        record.version = version
        self.records[record.approval_id] = record
        return version

    def get(self, approval_id):
        return self.records.get(approval_id)


def request(engine, **overrides):
    values = {
        "requester": "kamara",
        "tool_id": "karmolab.host_health",
        "tool_version": "1",
        "arguments": {"host": "karmo-ai01"},
        "authority_class": CapabilityClass.REVERSIBLE_WRITE.value,
        "ttl_seconds": 60,
    }
    values.update(overrides)
    return engine.request(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requester", ""),
        ("requester", "   "),
        ("requester", None),
        ("tool_id", ""),
        ("tool_version", ""),
        ("authority_class", ""),
        ("arguments", []),
        ("ttl_seconds", 0),
        ("ttl_seconds", -1),
        ("ttl_seconds", True),
        ("ttl_seconds", "60"),
    ],
)
def test_invalid_approval_request_inputs_fail_before_persistence(field, value):
    store = CountingStore()
    engine = ApprovalEngine(store=store)

    with pytest.raises(CoreControlError):
        request(engine, **{field: value})

    assert store.save_calls == 0
    assert store.records == {}


def test_blank_approver_cannot_approve_or_mutate_durable_record():
    store = CountingStore()
    engine = ApprovalEngine(store=store)
    record = request(engine)
    assert store.save_calls == 1

    with pytest.raises(CoreControlError, match="approver"):
        engine.approve(record.approval_id, approver="   ")

    assert store.save_calls == 1
    assert engine.get(record.approval_id).state.value == "REQUESTED"


def test_blank_explicit_executor_is_rejected_instead_of_falling_back_to_requester():
    store = CountingStore()
    engine = ApprovalEngine(store=store)
    record = request(engine)

    with pytest.raises(CoreControlError, match="authorized_executor"):
        engine.approve(
            record.approval_id,
            approver="reviewer-1",
            authorized_executor="",
        )

    assert store.save_calls == 1
    restored = engine.get(record.approval_id)
    assert restored.state.value == "REQUESTED"
    assert restored.authorized_executor is None


def test_blank_denial_or_cancellation_audit_identity_is_rejected_before_transition():
    store = CountingStore()
    engine = ApprovalEngine(store=store)
    denied = request(engine)

    with pytest.raises(CoreControlError):
        engine.deny(denied.approval_id, approver="reviewer-1", reason=" ")
    assert engine.get(denied.approval_id).state.value == "REQUESTED"

    approved = request(engine, tool_id="karmolab.repo_status")
    engine.approve(approved.approval_id, approver="reviewer-1", authorized_executor="worker-1")
    saves_before_cancel = store.save_calls

    with pytest.raises(CoreControlError):
        engine.cancel(approved.approval_id, actor=" ", reason="withdrawn")

    assert store.save_calls == saves_before_cancel
    assert engine.get(approved.approval_id).state.value == "APPROVED"
