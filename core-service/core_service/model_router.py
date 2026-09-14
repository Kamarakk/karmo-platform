"""Model-agnostic KARMO routing.

Models are replaceable compute resources. They may propose plans or produce
outputs, but they never grant authority, own credentials, or become the source
of truth. Routing is deterministic from KARMO policy and task requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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

    def ranked(self, *, required_capabilities=(), prefer_local=False, excluded_models=()):
        required = frozenset(required_capabilities)
        excluded = frozenset(excluded_models)
        candidates = [
            resource for resource in self._resources.values()
            if resource.enabled
            and resource.model_id not in excluded
            and required.issubset(resource.capabilities)
        ]
        candidates.sort(
            key=lambda resource: (
                1 if prefer_local and resource.local else 0,
                resource.trust_tier,
                resource.model_id,
            ),
            reverse=True,
        )
        return candidates

    def route(self, *, required_capabilities=(), prefer_local=False, excluded_models=()):
        candidates = self.ranked(
            required_capabilities=required_capabilities,
            prefer_local=prefer_local,
            excluded_models=excluded_models,
        )
        if not candidates:
            required = frozenset(required_capabilities)
            raise ModelRoutingError(f"no enabled model satisfies capabilities: {sorted(required)}")
        return candidates[0]

    def verifier_for(self, primary_model_id: str, *, required_capabilities=()):
        """Select an independent verifier and refuse self-verification."""
        return self.route(
            required_capabilities=required_capabilities,
            excluded_models={primary_model_id},
        )

    def inventory(self):
        return list(self._resources.values())
