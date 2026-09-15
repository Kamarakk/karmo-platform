from core_service.model_router import ModelResource
from core_service.operator import KarmoOperator


class RecordingClient:
    def __init__(self):
        self.calls = []

    def chat(self, *, model, messages, temperature=0.2):
        self.calls.append(model)
        return "PASS" if "verify" in model else "ok"


def _resource(model_id, capabilities, *, trust_tier, local, provider="test-provider"):
    return ModelResource(
        model_id=model_id,
        provider=provider,
        capabilities=capabilities,
        trust_tier=trust_tier,
        local=local,
    )


def test_operator_hard_requires_local_primary_and_verifier_even_when_remote_is_higher_trust():
    operator = KarmoOperator(
        model_client=RecordingClient(),
        resources=[
            _resource("local-primary", {"chat", "summarize"}, trust_tier=30, local=True),
            _resource("remote-primary", {"chat", "summarize"}, trust_tier=99, local=False),
            _resource("local-verifier", {"verify"}, trust_tier=20, local=True),
            _resource("remote-verifier", {"verify"}, trust_tier=99, local=False),
        ],
        status_reader=lambda _args=None: {"mode": "READ_ONLY"},
    )

    models = operator._models()

    assert models.primary.model_id == "local-primary"
    assert models.verifier.model_id == "local-verifier"


def test_status_read_is_not_executed_when_only_remote_models_satisfy_capabilities():
    calls = {"status": 0}

    def status_reader(_args=None):
        calls["status"] += 1
        return {"mode": "READ_ONLY"}

    client = RecordingClient()
    operator = KarmoOperator(
        model_client=client,
        resources=[
            _resource("remote-primary", {"chat", "summarize"}, trust_tier=99, local=False),
            _resource("remote-verifier", {"verify"}, trust_tier=99, local=False),
        ],
        status_reader=status_reader,
    )

    response = operator.handle("show KarmoLab status")

    assert response["verification"] == "DEGRADED_MODEL_POLICY"
    assert response["error"] == "ModelRoutingError"
    assert calls["status"] == 0
    assert client.calls == []


def test_chat_still_uses_local_model_below_verification_trust_floor():
    """Ordinary chat has no trust-tier gate -- only the KarmoLab status/
    verification path (via _models()) enforces OPERATOR_PRIMARY_MIN_TRUST_TIER.
    A local, low-trust model remains a valid chat fallback rather than
    causing chat to fail closed, so degrading to a lower-trust local model
    beats refusing to answer at all when no higher-trust model is available.
    """
    client = RecordingClient()
    operator = KarmoOperator(
        model_client=client,
        resources=[
            _resource("local-low", {"chat"}, trust_tier=5, local=True),
            _resource("remote-high", {"chat"}, trust_tier=99, local=False),
        ],
    )

    response = operator.handle("hello")

    assert response["kind"] == "chat"
    assert response.get("model") == "local-low"
    assert client.calls == ["local-low"]


def test_status_read_fails_closed_when_verifier_is_below_verifier_trust_floor():
    calls = {"status": 0}

    def status_reader(_args=None):
        calls["status"] += 1
        return {"mode": "READ_ONLY"}

    operator = KarmoOperator(
        model_client=RecordingClient(),
        resources=[
            _resource("local-primary", {"summarize"}, trust_tier=30, local=True),
            _resource("local-verifier-low", {"verify"}, trust_tier=19, local=True),
        ],
        status_reader=status_reader,
    )

    response = operator.handle("system health")

    assert response["verification"] == "DEGRADED_MODEL_POLICY"
    assert calls["status"] == 0
