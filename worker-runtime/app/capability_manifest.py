"""KARMO Worker Runtime — capability manifest (Phase 5).

Integrates directly with the Tool/Capability Registry design
(core-v2-prototypes/tool_registry/registry.py) rather than inventing a
parallel classification: capabilities reuse CapabilityClass verbatim and
follow the same computed-approval-requirement rule (financial_action/
destructive_action can only raise it, never lower it).

Core principle (explicit architectural instruction): a worker's declared
capabilities are AVAILABILITY CLAIMS, not authorization. This module is
the fixed, closed, KARMO-Core-owned definition of what each capability
ID actually means and is authorized to do -- a worker registering support
for a capability_id never gets to redefine what that ID means.
"""

from dataclasses import dataclass, field

from commander_readonly_manifest import COMMANDER_READONLY_CAPABILITIES
from tool_registry_reuse import CapabilityClass, compute_approval_requirement


class CapabilityManifestError(ValueError):
    """Refuse-don't-guess, same discipline as the Tool Registry."""


REQUIRED_CAPABILITY_FIELDS = [
    "capability_id", "version", "authority_class", "side_effect_class",
    "input_schema", "output_schema", "timeout_seconds", "resource_requirements",
    "network_required", "secrets_required", "idempotent", "retry_policy",
]


class SideEffectClass:
    NONE = "NONE"
    LOCAL_WRITE = "LOCAL_WRITE"
    EXTERNAL = "EXTERNAL"


SAFE_CAPABILITIES = {
    "hash_verify": dict(capability_id="hash_verify", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{"path":{"type":"string"}}},
        output_schema={"type":"object","properties":{"sha256":{"type":"string"}}}, timeout_seconds=30,
        resource_requirements={"cpu":"low","memory_mb":64}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":2,"backoff":"none"}),
    "pytest": dict(capability_id="pytest", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.LOCAL_WRITE, input_schema={"type":"object","properties":{"test_dir":{"type":"string"}}},
        output_schema={"type":"object","properties":{"exit_code":{"type":"integer"},"summary":{"type":"string"}}}, timeout_seconds=120,
        resource_requirements={"cpu":"medium","memory_mb":256}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":1,"backoff":"none"}),
    "static_analysis": dict(capability_id="static_analysis", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{"files":{"type":"array"}}},
        output_schema={"type":"object","properties":{"ok":{"type":"boolean"},"errors":{"type":"array"}}}, timeout_seconds=30,
        resource_requirements={"cpu":"low","memory_mb":64}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":2,"backoff":"none"}),
    "repository_analysis": dict(capability_id="repository_analysis", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{"repo_path":{"type":"string"}}},
        output_schema={"type":"object","properties":{"file_count":{"type":"integer"},"total_bytes":{"type":"integer"}}}, timeout_seconds=30,
        resource_requirements={"cpu":"low","memory_mb":64}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":2,"backoff":"none"}),
    "resource_benchmark": dict(capability_id="resource_benchmark", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{"iterations":{"type":"integer"}}},
        output_schema={"type":"object","properties":{"elapsed_seconds":{"type":"number"}}}, timeout_seconds=30,
        resource_requirements={"cpu":"medium","memory_mb":64}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":1,"backoff":"none"}),
    "document_processing_test": dict(capability_id="document_processing_test", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.LOCAL_WRITE, input_schema={"type":"object","properties":{"path":{"type":"string"}}},
        output_schema={"type":"object","properties":{"chunk_count":{"type":"integer"}}}, timeout_seconds=30,
        resource_requirements={"cpu":"low","memory_mb":128}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":2,"backoff":"none"}),
    "embedding_benchmark_test": dict(capability_id="embedding_benchmark_test", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{"vector_count":{"type":"integer"}}},
        output_schema={"type":"object","properties":{"elapsed_seconds":{"type":"number"}}}, timeout_seconds=30,
        resource_requirements={"cpu":"medium","memory_mb":64}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":1,"backoff":"none"}),
    "media_probe_test": dict(capability_id="media_probe_test", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{}},
        output_schema={"type":"object","properties":{"metal_available":{"type":"boolean"}}}, timeout_seconds=15,
        resource_requirements={"cpu":"low","memory_mb":32}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":1,"backoff":"none"}),
    "local_model_probe": dict(capability_id="local_model_probe", version="1.0.0", authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE, input_schema={"type":"object","properties":{}},
        output_schema={"type":"object","properties":{"mlx_installed":{"type":"boolean"},"ollama_installed":{"type":"boolean"}}}, timeout_seconds=15,
        resource_requirements={"cpu":"low","memory_mb":32}, network_required=False, secrets_required=[], idempotent=True,
        retry_policy={"max_attempts":1,"backoff":"none"}),
}
SAFE_CAPABILITIES.update(COMMANDER_READONLY_CAPABILITIES)

FORBIDDEN_CAPABILITY_IDS = {
    "shell_anything", "shell", "ssh", "production_admin", "database_admin",
    "qdrant_admin", "network_admin", "financial_trade", "external_post",
}


def validate_capability_declaration(declaration: dict):
    if "capability_id" not in declaration:
        raise CapabilityManifestError("worker capability declaration missing 'capability_id'")
    capability_id = declaration["capability_id"]
    if capability_id in FORBIDDEN_CAPABILITY_IDS:
        raise CapabilityManifestError(f"capability_id {capability_id!r} is permanently excluded from Worker Runtime v0.1's capability set")
    if capability_id not in SAFE_CAPABILITIES:
        raise CapabilityManifestError(f"unknown capability_id {capability_id!r} -- not part of the closed, allowlisted capability set")
    canonical = SAFE_CAPABILITIES[capability_id]
    missing = [field for field in REQUIRED_CAPABILITY_FIELDS if field not in canonical]
    if missing:
        raise CapabilityManifestError(f"canonical capability missing required fields: {missing}")
    for locked_field in ("authority_class", "side_effect_class", "network_required", "secrets_required"):
        if locked_field in declaration and declaration[locked_field] != canonical[locked_field]:
            raise CapabilityManifestError(f"worker attempted to override locked field {locked_field!r} for capability_id {capability_id!r}")
    return dict(canonical)


def get_canonical_capability(capability_id):
    if capability_id not in SAFE_CAPABILITIES:
        raise CapabilityManifestError(f"unknown capability_id: {capability_id!r}")
    canonical = SAFE_CAPABILITIES[capability_id]
    missing = [field for field in REQUIRED_CAPABILITY_FIELDS if field not in canonical]
    if missing:
        raise CapabilityManifestError(f"canonical capability missing required fields: {missing}")
    return dict(canonical)
