from core_service import operator as operator_module
from core_service.model_router import ModelResource
from core_service.ollama_client import OllamaClientError
from core_service.operator import KarmoOperator


class RecordingClient:
    def __init__(self):
        self.calls = []

    def chat(self, *, model, messages, temperature=0.2):
        self.calls.append(model)
        return "PASS" if "verify" in model else "ok"

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2):
        return {"content": self.chat(model=model, messages=messages, temperature=temperature), "tool_calls": None}


class SelectivelyFailingClient:
    """Like RecordingClient, but raises OllamaClientError for a chosen set
    of models -- for proving fallback/fail-closed behavior against real
    per-candidate failure, not just successful routing order."""

    def __init__(self, *, failing_models):
        self.failing_models = set(failing_models)
        self.calls = []

    def chat_with_tools(self, *, model, messages, tools, temperature=0.2):
        self.calls.append(model)
        if model in self.failing_models:
            raise OllamaClientError(f"simulated failure for {model}")
        return {"content": "ok", "tool_calls": None}


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
            _resource("local-low", {"chat", "tool_calling"}, trust_tier=5, local=True),
            _resource("remote-high", {"chat", "tool_calling"}, trust_tier=99, local=False),
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


def test_chat_excludes_models_that_are_not_tagged_tool_calling():
    """Model Router Phase B (docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md
    Section 3.4): "chat" alone is no longer sufficient -- a chat turn
    always offers tools, so only tool_calling-tagged models are ever
    real candidates. A model with "chat" but not "tool_calling" (the
    exact shape of granite3.3:2b in default_model_resources()) must
    never be selected, even as the only other option."""
    client = RecordingClient()
    operator = KarmoOperator(
        model_client=client,
        resources=[
            _resource("chat-only-no-tools", {"chat"}, trust_tier=99, local=True),
        ],
    )

    response = operator.handle("hello")

    assert response["error"] == "ModelRoutingError"
    assert client.calls == []


def test_chat_fails_closed_honestly_instead_of_falling_back_to_a_non_tool_calling_model():
    """Direct regression test for the real 2026-09-18 production incident:
    both tool-calling candidates fail (matching qwen3:8b and
    ministral-3:8b both timing out under contention), and a non-tool-
    calling model is registered (matching granite3.3:2b) with a higher
    trust tier than either failing candidate. Before this fix, chat would
    have fallen through to it and returned a fluent, confident, WRONG
    answer. After this fix, it must never be called at all."""
    client = SelectivelyFailingClient(failing_models={"primary-tools", "secondary-tools"})
    operator = KarmoOperator(
        model_client=client,
        resources=[
            _resource("primary-tools", {"chat", "tool_calling"}, trust_tier=40, local=True),
            _resource("secondary-tools", {"chat", "tool_calling"}, trust_tier=35, local=True),
            _resource("fast-fallback-no-tools", {"chat"}, trust_tier=99, local=True),
        ],
    )

    response = operator.handle("what does bloomboss say about last month")

    assert response["kind"] == "chat"
    assert response["message"] == "Local chat models are unavailable. KARMO control plane remains fail-closed."
    assert response["error"] == "OllamaClientError"
    assert client.calls == ["primary-tools", "secondary-tools"]
    assert "fast-fallback-no-tools" not in client.calls


def test_chat_fallback_never_retries_the_same_candidate_twice_in_one_request():
    """Model Router Phase B routing-loop protection (Section 3.5): a
    single chat turn must try each eligible candidate at most once."""
    client = SelectivelyFailingClient(failing_models={"primary-tools"})
    operator = KarmoOperator(
        model_client=client,
        resources=[
            _resource("primary-tools", {"chat", "tool_calling"}, trust_tier=40, local=True),
            _resource("secondary-tools", {"chat", "tool_calling"}, trust_tier=35, local=True),
        ],
    )

    response = operator.handle("hello")

    assert response["kind"] == "chat"
    assert response["model"] == "secondary-tools"
    assert client.calls == ["primary-tools", "secondary-tools"]
    assert len(client.calls) == len(set(client.calls))


def test_shadow_routing_failure_never_affects_the_real_chat_response(monkeypatch):
    """Model Router Phase C's hard safety property (Section 3.8): shadow
    routing is observability, not authority -- a failure anywhere inside
    it must never change, delay-fail, or otherwise touch the real answer.
    Forces compute_shadow_decision itself to raise, proving the outer
    guard in _chat() (not just shadow_router's own internal try/excepts)
    is what actually protects the real response."""

    def _boom(**_kwargs):
        raise RuntimeError("shadow routing exploded")

    monkeypatch.setattr(operator_module, "compute_shadow_decision", _boom)

    client = RecordingClient()
    operator = KarmoOperator(
        model_client=client,
        resources=[_resource("local-only", {"chat", "tool_calling"}, trust_tier=40, local=True)],
    )

    response = operator.handle("hello")

    assert response["kind"] == "chat"
    assert response["model"] == "local-only"
    assert response["message"] == "ok"
