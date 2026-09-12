import pytest

from core_service.control import ApprovalEngine, ApprovalRequirement, CapabilityClass
from core_service.dispatcher import CapabilityDispatcher, DispatchError
from core_service.model_router import ModelResource, ModelRouter, ModelRoutingError
from core_service.registry import CapabilityRegistry, ManifestValidationError
from core_service.task_state import InMemoryTaskStore, TaskState, TaskStateError
from core_service.verification import VerificationError, VerificationGate


def manifest(tool_id="repo.read", capability_class="READ", **overrides):
    value = {
        "tool_id": tool_id,
        "domain": "karmolab",
        "version": "1.0.0",
        "description": "test capability",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "capability_class": capability_class,
        "read_scope": ["repo"],
        "write_scope": [],
        "external_side_effects": False,
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": [],
        "secret_requirements": [],
        "invocation_identity": "worker",
        "timeout_seconds": 30,
        "retry_policy": {"max_attempts": 1},
        "idempotent": True,
        "idempotency_mechanism": "arguments_digest",
        "rollback_or_compensation": "not required",
        "health_check": "local",
        "deprecation_policy": "versioned",
        "dependencies": [],
        "observability": ["correlation_id"],
        "failure_isolation": "per invocation",
    }
    value.update(overrides)
    return value


def test_registry_computes_authority_and_refuses_override():
    registry = CapabilityRegistry()
    record = registry.register(manifest())
    assert record.computed_approval_requirement is ApprovalRequirement.NONE

    financial = registry.register(manifest(
        tool_id="finance.research",
        version="1.0.0",
        financial_action=True,
    ))
    assert financial.computed_approval_requirement is ApprovalRequirement.EXPLICIT_PER_CALL

    poisoned = manifest(tool_id="bad.tool")
    poisoned["human_approval_requirement"] = "NONE"
    with pytest.raises(ManifestValidationError):
        registry.register(poisoned)


def test_dispatcher_refuses_unregistered_and_gates_write():
    registry = CapabilityRegistry()
    approval = ApprovalEngine()
    dispatcher = CapabilityDispatcher(registry=registry, approval_engine=approval)

    with pytest.raises(DispatchError):
        dispatcher.dispatch(
            requester="kamara", tool_id="missing", version="1.0.0",
            arguments={}, executor_identity="worker-1",
        )

    registry.register(manifest(tool_id="repo.read"))
    dispatcher.bind("repo.read", "1.0.0", lambda args: {"value": args["value"]})
    decision = dispatcher.dispatch(
        requester="kamara", tool_id="repo.read", version="1.0.0",
        arguments={"value": 7}, executor_identity="worker-1",
    )
    assert decision.executed is True
    assert decision.result == {"value": 7}

    registry.register(manifest(tool_id="repo.write", capability_class="REVERSIBLE_WRITE"))
    dispatcher.bind("repo.write", "1.0.0", lambda args: {"written": args["path"]})
    pending = dispatcher.dispatch(
        requester="kamara", tool_id="repo.write", version="1.0.0",
        arguments={"path": "x"}, executor_identity="worker-1",
    )
    assert pending.executed is False
    assert pending.approval_id

    approval.approve(pending.approval_id, approver="kamara", authorized_executor="worker-1")
    completed = dispatcher.dispatch(
        requester="kamara", tool_id="repo.write", version="1.0.0",
        arguments={"path": "x"}, executor_identity="worker-1",
        approval_id=pending.approval_id,
    )
    assert completed.executed is True
    assert completed.result == {"written": "x"}


def test_task_state_is_explicit_and_fail_closed():
    store = InMemoryTaskStore()
    task = store.create(objective="inspect system", requester="kamara", allowed_capabilities=["repo.read"])
    task.transition(TaskState.PLANNED, actor="karmo")
    task.transition(TaskState.READY, actor="karmo")
    task.transition(TaskState.RUNNING, actor="worker-1")
    task.transition(TaskState.VERIFYING, actor="karmo")
    task.transition(TaskState.SUCCEEDED, actor="verifier")
    assert task.state is TaskState.SUCCEEDED
    with pytest.raises(TaskStateError):
        task.transition(TaskState.RUNNING, actor="worker-1")


def test_model_router_requires_independent_verifier():
    router = ModelRouter([
        ModelResource("ollama:qwen3", "ollama", frozenset({"code", "review"}), trust_tier=1, local=True),
        ModelResource("claude", "anthropic", frozenset({"code", "review"}), trust_tier=3),
        ModelResource("chatgpt", "openai", frozenset({"code", "review"}), trust_tier=2),
    ])
    primary = router.route(required_capabilities={"code"})
    verifier = router.verifier_for(primary.model_id, required_capabilities={"review"})
    assert verifier.model_id != primary.model_id

    with pytest.raises(ModelRoutingError):
        ModelRouter([ModelResource("only", "local", frozenset({"code"}))]).verifier_for(
            "only", required_capabilities={"code"}
        )


def test_verification_gate_refuses_self_verification():
    subject = {"result": "ok"}
    with pytest.raises(VerificationError):
        VerificationGate.verify(
            producer_id="claude", verifier_id="claude", subject=subject,
            check=lambda value: {"passed": True},
        )

    record = VerificationGate.verify(
        producer_id="claude", verifier_id="chatgpt", subject=subject,
        check=lambda value: {"passed": value["result"] == "ok", "evidence": ["test"]},
    )
    assert record.passed is True
    assert record.verifier_id == "chatgpt"
