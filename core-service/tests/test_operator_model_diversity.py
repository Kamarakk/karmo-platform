from core_service.operator import default_model_resources


def test_default_activation_models_use_qwen_primary_and_llama_verifier_only():
    resources = {resource.model_id: resource for resource in default_model_resources()}
    assert set(resources) == {"qwen3:8b", "llama3.2:3b"}
    assert resources["qwen3:8b"].capabilities == frozenset({"chat", "summarize"})
    assert resources["llama3.2:3b"].capabilities == frozenset({"verify"})
