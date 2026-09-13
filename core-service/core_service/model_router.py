"""Model-agnostic KARMO routing.

Models are replaceable compute resources. They may propose plans or produce
outputs, but they never grant authority, own credentials, or become the source
of truth. Routing is deterministic from KARMO policy and task requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType


class ModelRoutingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelResource:
    model_id: str
    provider: str
    capabilities: frozenset[str]
    trust_tier: int = 0
    local: bool = False
    enabled: bool = True
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ModelRoutingError("model_id must be a non-empty string")
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ModelRoutingError("provider must be a non-empty string")
        try:
            capabilities = frozenset(self.capabilities)
        except TypeError as exc:
            raise ModelRoutingError("capabilities must be an iterable of strings") from exc
        if any(not isinstance(capability, str) or not capability.strip() for capability in capabilities):
            raise ModelRoutingError("capabilities must contain only non-empty strings")
        if isinstance(self.trust_tier, bool) or not isinstance(self.trust_tier, int) or self.trust_tier < 0:
            raise ModelRoutingError("trust_tier must be a non-negative integer")
        if not isinstance(self.local, bool) or not isinstance(self.enabled, bool):
            raise ModelRoutingError("local and enabled must be boolean")
        if not isinstance(self.metadata, dict):
            raise ModelRoutingError("metadata must be a dict")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ModelRouter:
    def __init__(self, resources=None):
        self._resources: dict[str, ModelResource] = {}
        for resource in resources or []:
            self.register(resource)

    def register(self, resource: ModelResource):
        if not isinstance(resource, ModelResource):
            raise ModelRoutingError("resource must be ModelResource")
        if resource.model_id in self._resources:
            raise ModelRoutingError(f"model already registered: {resource.model_id}")
        self._resources[resource.model_id] = resource

    @staticmethod
    def _capability_set(values, *, field_name):
        try:
            normalized = frozenset(values)
        except TypeError as exc:
            raise ModelRoutingError(f"{field_name} must be an iterable of strings") from exc
        if any(not isinstance(value, str) or not value.strip() for value in normalized):
            raise ModelRoutingError(f"{field_name} must contain only non-empty strings")
        return normalized

    def route(
        self,
        *,
        required_capabilities=(),
        prefer_local=False,
        require_local=False,
        minimum_trust_tier=0,
        excluded_models=(),
        excluded_providers=(),
    ):
        """Select one model using Core-owned policy constraints.

        ``prefer_local`` only affects ordering. ``require_local`` and
        ``minimum_trust_tier`` are hard eligibility gates and therefore cannot
        silently fall back to a less-trusted model. Exclusions are also hard
        gates, which lets verifier selection refuse a model/provider when an
        independent implementation is required by the caller's policy.
        """
        if not isinstance(prefer_local, bool) or not isinstance(require_local, bool):
            raise ModelRoutingError("prefer_local and require_local must be boolean")
        if isinstance(minimum_trust_tier, bool) or not isinstance(minimum_trust_tier, int) or minimum_trust_tier < 0:
            raise ModelRoutingError("minimum_trust_tier must be a non-negative integer")
        required = self._capability_set(required_capabilities, field_name="required_capabilities")
        excluded = self._capability_set(excluded_models, field_name="excluded_models")
        excluded_provider_set = self._capability_set(excluded_providers, field_name="excluded_providers")
        candidates = [
            resource for resource in self._resources.values()
            if resource.enabled
            and resource.model_id not in excluded
            and resource.provider not in excluded_provider_set
            and (not require_local or resource.local)
            and resource.trust_tier >= minimum_trust_tier
            and required.issubset(resource.capabilities)
        ]
        if not candidates:
            raise ModelRoutingError(
                "no enabled model satisfies routing policy: "
                f"capabilities={sorted(required)}, require_local={require_local}, "
                f"minimum_trust_tier={minimum_trust_tier}"
            )
        candidates.sort(
            key=lambda resource: (
                1 if prefer_local and resource.local else 0,
                resource.trust_tier,
                resource.model_id,
            ),
            reverse=True,
        )
        return candidates[0]

    def verifier_for(
        self,
        primary_model_id: str,
        *,
        required_capabilities=(),
        require_local=False,
        minimum_trust_tier=0,
        require_distinct_provider=False,
    ):
        """Select an independent verifier and refuse self-verification.

        Distinct-provider verification is opt-in because a local-only deployment
        can legitimately have multiple independent model families behind one
        provider. When requested, it is a hard fail-closed constraint.
        """
        if not isinstance(primary_model_id, str) or not primary_model_id.strip():
            raise ModelRoutingError("primary_model_id must be a non-empty string")
        primary = self._resources.get(primary_model_id)
        if primary is None:
            raise ModelRoutingError(f"primary model is not registered: {primary_model_id}")
        excluded_providers = {primary.provider} if require_distinct_provider else ()
        return self.route(
            required_capabilities=required_capabilities,
            require_local=require_local,
            minimum_trust_tier=minimum_trust_tier,
            excluded_models={primary_model_id},
            excluded_providers=excluded_providers,
        )

    def inventory(self):
        return list(self._resources.values())
