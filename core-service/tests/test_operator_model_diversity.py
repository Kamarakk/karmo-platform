from core_service.operator import default_model_resources


def test_default_activation_models_use_local_open_four_model_stack():
    resources = {resource.model_id: resource for resource in default_model_resources()}
    assert set(resources) == {
        "qwen3:8b",
        "ministral-3:8b",
        "mistral:7b",
        "granite3.3:2b",
    }
    assert resources["qwen3:8b"].capabilities == frozenset({"chat", "summarize", "reason"})
    assert resources["ministral-3:8b"].capabilities == frozenset({"chat", "summarize", "reason"})
    assert resources["mistral:7b"].capabilities == frozenset({"verify"})
    assert resources["granite3.3:2b"].capabilities == frozenset({"chat", "summarize", "fast"})
    assert all(resource.local for resource in resources.values())


def test_default_roles_are_explicit_and_cloud_free():
    resources = {resource.model_id: resource for resource in default_model_resources()}
    assert resources["qwen3:8b"].metadata["role"] == "primary"
    assert resources["ministral-3:8b"].metadata["role"] == "secondary"
    assert resources["mistral:7b"].metadata["role"] == "verifier"
    assert resources["granite3.3:2b"].metadata["role"] == "fast_fallback"
    assert {resource.provider for resource in resources.values()} == {"ollama-local"}
