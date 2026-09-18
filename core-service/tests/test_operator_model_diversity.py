from core_service.model_router import ModelRouter
from core_service.operator import default_model_resources


def test_default_activation_models_use_local_open_four_model_stack():
    resources = {resource.model_id: resource for resource in default_model_resources()}
    assert set(resources) == {
        "qwen3:8b",
        "ministral-3:8b",
        "mistral:7b",
        "granite3.3:2b",
    }
    assert resources["qwen3:8b"].capabilities == frozenset({"chat", "summarize", "reason", "tool_calling"})
    assert resources["ministral-3:8b"].capabilities == frozenset({"chat", "summarize", "reason", "tool_calling"})
    assert resources["mistral:7b"].capabilities == frozenset({"verify"})
    assert resources["granite3.3:2b"].capabilities == frozenset({"chat", "summarize", "fast"})
    assert all(resource.local for resource in resources.values())


def test_tool_calling_tag_is_evidence_based_not_guessed():
    """Model Router Phase A (docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md
    Section 3.2): only tag a model "tool_calling" where real evidence
    supports it. granite3.3:2b confirmed NOT reliably tool-calling
    (2026-09-18 live testing); mistral:7b never exercised via the chat
    tool-calling path at all (verify-only role) -- neither gets the tag."""
    resources = {resource.model_id: resource for resource in default_model_resources()}
    assert "tool_calling" not in resources["granite3.3:2b"].capabilities
    assert "tool_calling" not in resources["mistral:7b"].capabilities


def test_tool_calling_tag_does_not_change_chat_candidate_selection_yet():
    """Phase A is observability/data only -- adding the "tool_calling" tag
    must NOT by itself change which models _chat() selects as candidates.
    _chat() (core_service/operator.py) filters on
    required_capabilities={"chat"}, not {"tool_calling"} -- that filter
    change is Phase B's job. This test locks in that Phase A alone
    changes no behavior, matching the plan's own claim."""
    router = ModelRouter(default_model_resources())
    candidates = [r.model_id for r in router.ranked(required_capabilities={"chat"}, prefer_local=True)]
    assert candidates == ["qwen3:8b", "ministral-3:8b", "granite3.3:2b"]


def test_default_roles_are_explicit_and_cloud_free():
    resources = {resource.model_id: resource for resource in default_model_resources()}
    assert resources["qwen3:8b"].metadata["role"] == "primary"
    assert resources["ministral-3:8b"].metadata["role"] == "secondary"
    assert resources["mistral:7b"].metadata["role"] == "verifier"
    assert resources["granite3.3:2b"].metadata["role"] == "fast_fallback"
    assert {resource.provider for resource in resources.values()} == {"ollama-local"}
