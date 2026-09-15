import pytest

from core_service.model_router import ModelResource, ModelRouter, ModelRoutingError


def _resources():
    return [
        ModelResource(
            model_id="local-primary",
            provider="ollama-local",
            capabilities={"chat", "summarize"},
            trust_tier=30,
            local=True,
        ),
        ModelResource(
            model_id="local-verifier",
            provider="ollama-local",
            capabilities={"verify"},
            trust_tier=20,
            local=True,
        ),
        ModelResource(
            model_id="remote-verifier",
            provider="separate-provider",
            capabilities={"verify"},
            trust_tier=40,
            local=False,
        ),
    ]


def test_resource_normalizes_capabilities_and_freezes_metadata_copy():
    metadata = {"role": "primary"}
    resource = ModelResource(
        model_id="model-a",
        provider="provider-a",
        capabilities={"chat"},
        metadata=metadata,
    )
    metadata["role"] = "mutated"
    assert resource.capabilities == frozenset({"chat"})
    assert resource.metadata["role"] == "primary"
    with pytest.raises(TypeError):
        resource.metadata["role"] = "changed"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model_id": "", "provider": "provider", "capabilities": {"chat"}},
        {"model_id": "model", "provider": "", "capabilities": {"chat"}},
        {"model_id": "model", "provider": "provider", "capabilities": {""}},
        {"model_id": "model", "provider": "provider", "capabilities": {"chat"}, "trust_tier": -1},
    ],
)
def test_invalid_model_resources_fail_closed(kwargs):
    with pytest.raises(ModelRoutingError):
        ModelResource(**kwargs)


def test_require_local_is_hard_gate_not_preference():
    router = ModelRouter(_resources())
    selected = router.route(required_capabilities={"verify"}, prefer_local=True)
    assert selected.model_id == "local-verifier"

    selected = router.route(required_capabilities={"verify"}, require_local=True)
    assert selected.model_id == "local-verifier"

    with pytest.raises(ModelRoutingError, match="routing policy"):
        router.route(
            required_capabilities={"verify"},
            require_local=True,
            minimum_trust_tier=25,
        )


def test_minimum_trust_tier_is_enforced_before_ranking():
    router = ModelRouter(_resources())
    selected = router.route(required_capabilities={"verify"}, minimum_trust_tier=30)
    assert selected.model_id == "remote-verifier"

    with pytest.raises(ModelRoutingError, match="minimum_trust_tier=50"):
        router.route(required_capabilities={"verify"}, minimum_trust_tier=50)


def test_verifier_refuses_self_and_can_require_distinct_provider():
    router = ModelRouter(_resources())

    verifier = router.verifier_for("local-primary", required_capabilities={"verify"})
    assert verifier.model_id != "local-primary"

    verifier = router.verifier_for(
        "local-primary",
        required_capabilities={"verify"},
        require_distinct_provider=True,
    )
    assert verifier.model_id == "remote-verifier"
    assert verifier.provider != "ollama-local"


def test_distinct_provider_requirement_fails_closed_without_candidate():
    router = ModelRouter(_resources()[:2])
    with pytest.raises(ModelRoutingError, match="routing policy"):
        router.verifier_for(
            "local-primary",
            required_capabilities={"verify"},
            require_distinct_provider=True,
        )


def test_verifier_requires_registered_primary():
    router = ModelRouter(_resources())
    with pytest.raises(ModelRoutingError, match="not registered"):
        router.verifier_for("unknown", required_capabilities={"verify"})


def test_malformed_route_policy_inputs_fail_closed():
    router = ModelRouter(_resources())
    with pytest.raises(ModelRoutingError):
        router.route(required_capabilities={""})
    with pytest.raises(ModelRoutingError):
        router.route(minimum_trust_tier=-1)
    with pytest.raises(ModelRoutingError):
        router.route(require_local="yes")
