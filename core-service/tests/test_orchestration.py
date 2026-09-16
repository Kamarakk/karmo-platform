from __future__ import annotations

import pytest

from core_service.control import CapabilityClass
from core_service.orchestration import (
    CLAIM_TASK_TOOL,
    COMPLETE_TASK_TOOL,
    CREATE_TASK_TOOL,
    LIST_TASKS_TOOL,
    MAX_TEXT_CHARS,
    OrchestrationConfigurationError,
    TaskStore,
    manifests,
)


def test_task_store_rejects_empty_dsn():
    with pytest.raises(OrchestrationConfigurationError):
        TaskStore(dsn="   ")


def test_create_task_rejects_empty_objective():
    store = TaskStore(dsn="host=unused")
    with pytest.raises(ValueError):
        store.create_task(objective="   ", context=None, requested_by="kamara")


def test_create_task_rejects_oversized_objective():
    store = TaskStore(dsn="host=unused")
    with pytest.raises(ValueError):
        store.create_task(objective="x" * (MAX_TEXT_CHARS + 1), context=None, requested_by="kamara")


def test_list_tasks_rejects_invalid_status():
    store = TaskStore(dsn="host=unused")
    with pytest.raises(ValueError):
        store.list_tasks(status="NOT_A_REAL_STATUS")


def test_list_tasks_rejects_out_of_range_limit():
    store = TaskStore(dsn="host=unused")
    with pytest.raises(ValueError):
        store.list_tasks(limit=0)
    with pytest.raises(ValueError):
        store.list_tasks(limit=101)


def test_manifests_are_well_formed_and_approval_requirements_match_i09():
    from core_service.registry import CapabilityRegistry

    registry = CapabilityRegistry()
    registered = {m["tool_id"]: registry.register(m) for m in manifests()}

    assert set(registered) == {CREATE_TASK_TOOL, LIST_TASKS_TOOL, CLAIM_TASK_TOOL, COMPLETE_TASK_TOOL}

    assert registered[LIST_TASKS_TOOL].capability_class == CapabilityClass.READ
    assert registered[LIST_TASKS_TOOL].computed_approval_requirement.value == "NONE"

    for write_tool in (CREATE_TASK_TOOL, CLAIM_TASK_TOOL, COMPLETE_TASK_TOOL):
        assert registered[write_tool].capability_class == CapabilityClass.REVERSIBLE_WRITE
        assert registered[write_tool].computed_approval_requirement.value == "EXPLICIT_PER_SESSION_OR_TASK"

    for manifest_record in registered.values():
        assert manifest_record.manifest["financial_action"] is False
        assert manifest_record.manifest["destructive_action"] is False
