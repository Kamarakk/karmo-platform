from core_service import karmolab
from core_service.control import ApprovalEngine, ApprovalRequirement
from core_service.dispatcher import CapabilityDispatcher
from core_service.registry import CapabilityRegistry


def test_karmolab_status_is_registered_read_only_and_dispatched(monkeypatch):
    registry = CapabilityRegistry()
    approval = ApprovalEngine()
    dispatcher = CapabilityDispatcher(registry=registry, approval_engine=approval)

    monkeypatch.setattr(karmolab, "_memory_status", lambda: {"available": True, "total_bytes": 1})
    monkeypatch.setattr(karmolab, "_disk_status", lambda: {"path": "/", "total_bytes": 2})
    monkeypatch.setattr(karmolab, "_service_status", lambda: {"karmo-core.service": {"state": "active"}})
    monkeypatch.setattr(karmolab, "_container_status", lambda: {"available": True, "containers": []})
    monkeypatch.setattr(karmolab.platform, "node", lambda: "test-host")
    monkeypatch.setattr(karmolab.platform, "system", lambda: "Linux")
    monkeypatch.setattr(karmolab.platform, "release", lambda: "test")
    monkeypatch.setattr(karmolab.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(karmolab.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(karmolab.os, "getloadavg", lambda: (0.1, 0.2, 0.3))

    record = karmolab.register_read_status_capability(registry=registry, dispatcher=dispatcher)

    assert record.computed_approval_requirement is ApprovalRequirement.NONE
    assert record.manifest["capability_class"].value == "READ"
    assert record.manifest["external_side_effects"] is False
    assert record.manifest["network_requirements"] == []
    assert record.manifest["secret_requirements"] == []

    decision = dispatcher.dispatch(
        requester="kamara",
        tool_id=karmolab.KARMOLAB_STATUS_TOOL_ID,
        version=karmolab.KARMOLAB_STATUS_VERSION,
        arguments={},
        executor_identity="core",
    )

    assert decision.executed is True
    assert decision.approval_id is None
    assert decision.result["mode"] == "READ_ONLY"
    assert decision.result["host"]["hostname"] == "test-host"
    assert decision.result["containers"] == {"available": True, "containers": []}


def test_karmolab_status_manifest_refuses_caller_controlled_arguments():
    schema = karmolab.KARMOLAB_STATUS_MANIFEST["input_schema"]
    assert schema == {"type": "object", "additionalProperties": False}
