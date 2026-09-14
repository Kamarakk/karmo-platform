"""KARMO operator entry point for the first bounded operational slice.

Authority stays in KARMO Core. Models may summarize or converse, but they do
not select arbitrary tools, mint approval, execute shell commands, or turn
network reachability into authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .control import ApprovalEngine, CapabilityClass
from .dispatcher import CapabilityDispatcher
from .karmolab import read_status
from .model_router import ModelResource, ModelRouter
from .ollama_client import OllamaChatClient, OllamaClientError
from .registry import CapabilityRegistry

KARMOLAB_STATUS_TOOL = "karmolab.read_status"
KARMOLAB_STATUS_VERSION = "1.0.0"

_WRITE_WORDS = re.compile(
    r"\b(restart|reboot|stop|start|enable|disable|install|uninstall|delete|remove|"
    r"change|modify|write|create|update|upgrade|patch|kill|terminate|deploy|merge)\b",
    re.IGNORECASE,
)
_STATUS_WORDS = re.compile(
    r"\b(status|health|healthy|karmolab|host|cpu|memory|ram|disk|service|services|"
    r"docker|container|containers|running|online)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OperatorModels:
    primary: ModelResource
    verifier: ModelResource


def _status_manifest() -> dict:
    return {
        "tool_id": KARMOLAB_STATUS_TOOL,
        "domain": "karmolab",
        "version": KARMOLAB_STATUS_VERSION,
        "description": "Read bounded host, resource, KARMO service, and container status.",
        "input_schema": {"type": "object", "additionalProperties": False},
        "output_schema": {"type": "object"},
        "capability_class": CapabilityClass.READ.value,
        "read_scope": "host identity, CPU/load, memory, root disk, fixed KARMO service state, docker ps",
        "write_scope": "none",
        "external_side_effects": "none",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none; local process inspection only",
        "secret_requirements": "none",
        "invocation_identity": "karmo-core-operator",
        "timeout_seconds": 10,
        "retry_policy": "none",
        "idempotent": True,
        "idempotency_mechanism": "pure bounded read",
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke and require mode=READ_ONLY",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "standard library; systemctl/docker optional for read visibility",
        "observability": "structured operator response",
        "failure_isolation": "individual fixed reads degrade independently",
    }


def default_model_resources() -> list[ModelResource]:
    return [
        ModelResource(
            model_id="qwen3:8b",
            provider="ollama-local",
            capabilities=frozenset({"chat", "summarize", "reason"}),
            trust_tier=40,
            local=True,
            metadata={"role": "primary"},
        ),
        ModelResource(
            model_id="ministral-3:8b",
            provider="ollama-local",
            capabilities=frozenset({"chat", "summarize", "reason"}),
            trust_tier=35,
            local=True,
            metadata={"role": "secondary"},
        ),
        ModelResource(
            model_id="mistral:7b",
            provider="ollama-local",
            capabilities=frozenset({"verify"}),
            trust_tier=30,
            local=True,
            metadata={"role": "verifier"},
        ),
        ModelResource(
            model_id="granite3.3:2b",
            provider="ollama-local",
            capabilities=frozenset({"chat", "summarize", "fast"}),
            trust_tier=20,
            local=True,
            metadata={"role": "fast_fallback"},
        ),
    ]


class KarmoOperator:
    def __init__(self, *, model_client=None, resources=None, status_reader=None):
        self.model_client = model_client or OllamaChatClient()
        self.router = ModelRouter(resources or default_model_resources())
        self.status_reader = status_reader or read_status
        self.registry = CapabilityRegistry()
        self.registry.register(_status_manifest())
        self.dispatcher = CapabilityDispatcher(
            registry=self.registry,
            approval_engine=ApprovalEngine(),
        )
        self.dispatcher.bind(KARMOLAB_STATUS_TOOL, KARMOLAB_STATUS_VERSION, self.status_reader)

    def _models(self) -> OperatorModels:
        primary = self.router.route(required_capabilities={"summarize"}, prefer_local=True)
        verifier = self.router.verifier_for(primary.model_id, required_capabilities={"verify"})
        if primary.model_id == verifier.model_id:
            raise RuntimeError("primary and verifier must be distinct")
        return OperatorModels(primary=primary, verifier=verifier)

    def _summarize_status(self, evidence: dict, models: OperatorModels) -> tuple[str | None, str]:
        evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        try:
            summary = self.model_client.chat(
                model=models.primary.model_id,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Use only exact values present in the supplied KarmoLab evidence. "
                            "Report hostname, mode, each KARMO service state, and each container name/status. "
                            "Do not infer health, causes, percentages, recommendations, or extra labels. "
                            "Use at most three short sentences."
                        ),
                    },
                    {"role": "user", "content": evidence_json},
                ],
            )
            verdict = self.model_client.chat(
                model=models.verifier.model_id,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Check only whether every factual claim in the summary appears directly in the evidence. "
                            "Reply PASS if all claims are directly supported. Otherwise reply FAIL followed by one short reason."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({"evidence": evidence, "summary": summary}, sort_keys=True),
                    },
                ],
                temperature=0.0,
            )
        except (OllamaClientError, RuntimeError) as exc:
            return None, f"DEGRADED_MODEL_UNAVAILABLE:{type(exc).__name__}"
        if verdict.strip().upper().startswith("PASS"):
            return summary, "PASS"
        return None, "FAIL"

    def _read_status(self) -> dict:
        models = self._models()
        decision = self.dispatcher.dispatch(
            requester="kamara",
            tool_id=KARMOLAB_STATUS_TOOL,
            version=KARMOLAB_STATUS_VERSION,
            arguments={},
            executor_identity="karmo-core-operator",
            model_identity=models.primary.model_id,
        )
        evidence = decision.result
        summary, verification = self._summarize_status(evidence, models)
        return {
            "kind": "karmolab_read",
            "message": summary or "KarmoLab READ completed; showing verified raw evidence.",
            "verification": verification,
            "primary_model": models.primary.model_id,
            "verifier_model": models.verifier.model_id,
            "tool_id": decision.tool_id,
            "tool_version": decision.version,
            "approval_requirement": decision.approval_requirement.value,
            "evidence": evidence,
        }

    def _chat(self, text: str) -> dict:
        candidates = self.router.ranked(required_capabilities={"chat"}, prefer_local=True)
        if not candidates:
            return {
                "kind": "chat",
                "message": "No enabled local chat model is available. KARMO control plane remains fail-closed.",
                "error": "ModelRoutingError",
            }
        last_error = None
        for candidate in candidates:
            try:
                answer = self.model_client.chat(
                    model=candidate.model_id,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are KARMO, Kamara's local AI control-plane interface. "
                                "You are currently in bounded activation mode. You may converse and explain, "
                                "but you have no write, deployment, financial, destructive, arbitrary shell, "
                                "or secret-reading authority. Never imply otherwise."
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                )
                return {"kind": "chat", "message": answer, "model": candidate.model_id}
            except OllamaClientError as exc:
                last_error = type(exc).__name__
        return {
            "kind": "chat",
            "message": "Local chat models are unavailable. KARMO control plane remains fail-closed.",
            "error": last_error or "OllamaClientError",
        }

    def handle(self, text: str) -> dict:
        text = text.strip()
        if not text:
            return {"kind": "system", "message": "Ask KARMO a question or request KarmoLab status."}
        if _WRITE_WORDS.search(text):
            return {
                "kind": "refusal",
                "message": (
                    "KARMO is in READ-only activation mode. I can inspect and explain, but I will not "
                    "change services, files, software, network state, or infrastructure."
                ),
            }
        if _STATUS_WORDS.search(text):
            return self._read_status()
        return self._chat(text)
