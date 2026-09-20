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
    "capability_id",
    "version",
    "authority_class",
    "side_effect_class",
    "input_schema",
    "output_schema",
    "timeout_seconds",
    "resource_requirements",
    "network_required",
    "secrets_required",
    "idempotent",
    "retry_policy",
]


class SideEffectClass:
    """What a capability does to the world beyond returning a value.
    Distinct from (and orthogonal to) capability_class, same pattern as
    the Tool Registry's financial_action/destructive_action flags."""

    NONE = "NONE"  # pure computation / read-only inspection
    LOCAL_WRITE = "LOCAL_WRITE"  # writes only inside the job's own temp workspace
    EXTERNAL = "EXTERNAL"  # not permitted in this workload's initial capability set


# The closed, allowlisted set of SAFE capabilities for Worker Runtime v0.1.
# Every one is capability_class=READ or REVERSIBLE_WRITE (scoped to the
# job's own temp workspace), side_effect_class=NONE or LOCAL_WRITE,
# network_required=False, secrets_required=[]. Nothing here is
# EXTERNAL_ACTION or DESTRUCTIVE_HIGH_IMPACT -- explicit instruction.
SAFE_CAPABILITIES = {
    "hash_verify": dict(
        capability_id="hash_verify",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"sha256": {"type": "string"}}},
        timeout_seconds=30,
        resource_requirements={"cpu": "low", "memory_mb": 64},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 2, "backoff": "none"},
    ),
    "pytest": dict(
        capability_id="pytest",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.LOCAL_WRITE,  # pytest cache files in the temp workspace
        input_schema={"type": "object", "properties": {"test_dir": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"exit_code": {"type": "integer"}, "summary": {"type": "string"}}},
        timeout_seconds=120,
        resource_requirements={"cpu": "medium", "memory_mb": 256},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
    "static_analysis": dict(
        capability_id="static_analysis",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {"files": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}, "errors": {"type": "array"}}},
        timeout_seconds=30,
        resource_requirements={"cpu": "low", "memory_mb": 64},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 2, "backoff": "none"},
    ),
    "repository_analysis": dict(
        capability_id="repository_analysis",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {"repo_path": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"file_count": {"type": "integer"}, "total_bytes": {"type": "integer"}}},
        timeout_seconds=30,
        resource_requirements={"cpu": "low", "memory_mb": 64},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 2, "backoff": "none"},
    ),
    "resource_benchmark": dict(
        capability_id="resource_benchmark",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {"iterations": {"type": "integer"}}},
        output_schema={"type": "object", "properties": {"elapsed_seconds": {"type": "number"}}},
        timeout_seconds=30,
        resource_requirements={"cpu": "medium", "memory_mb": 64},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
    "document_processing_test": dict(
        capability_id="document_processing_test",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.LOCAL_WRITE,
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"chunk_count": {"type": "integer"}}},
        timeout_seconds=30,
        resource_requirements={"cpu": "low", "memory_mb": 128},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 2, "backoff": "none"},
    ),
    "embedding_benchmark_test": dict(
        capability_id="embedding_benchmark_test",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {"vector_count": {"type": "integer"}}},
        output_schema={"type": "object", "properties": {"elapsed_seconds": {"type": "number"}}},
        timeout_seconds=30,
        resource_requirements={"cpu": "medium", "memory_mb": 64},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
    "media_probe_test": dict(
        capability_id="media_probe_test",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {"metal_available": {"type": "boolean"}}},
        timeout_seconds=15,
        resource_requirements={"cpu": "low", "memory_mb": 32},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
    "local_model_probe": dict(
        capability_id="local_model_probe",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {"mlx_installed": {"type": "boolean"}, "ollama_installed": {"type": "boolean"}}},
        timeout_seconds=15,
        resource_requirements={"cpu": "low", "memory_mb": 32},
        network_required=False,
        secrets_required=[],
        idempotent=True,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
    # See docs/architecture/KARMO_WORKER_MODEL_INFERENCE_ROUTING.md for the
    # full design/System-Fit/Invariant review this capability implements.
    # READ, not EXTERNAL_ACTION: a chat completion has no persistent side
    # effect, same classification principle as local_model_probe and
    # karmolab.read_status. network_required stays False -- the handler
    # calls the worker's OWN loopback Ollama (127.0.0.1:11434), never a
    # remote endpoint; the prompt/response reach Core only over the
    # existing authenticated SSH-stdio job transport.
    "model_chat": dict(
        capability_id="model_chat",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": ["qwen3:8b", "mistral:7b"]},
                "prompt": {"type": "string", "maxLength": 8000},
            },
            "required": ["model", "prompt"],
        },
        output_schema={"type": "object", "properties": {"response": {"type": "string"}}},
        timeout_seconds=120,
        resource_requirements={"cpu": "high", "memory_mb": 8192},
        network_required=False,
        secrets_required=[],
        idempotent=False,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
    # Model Router Phase D1 (docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md
    # Section 6) -- a SEPARATE capability from model_chat above, not a version
    # bump of it. model_chat 1.0.0 is already declared active in production
    # worker configs (/etc/karmo/worker0{1,2}.json); bumping its version in
    # place would require the deployed config and the manifest to change in
    # lockstep or the next config validation fails closed for the WHOLE
    # worker, not just this capability. Adding a new capability instead is
    # strictly additive -- model_chat 1.0.0 is completely untouched.
    #
    # Calls Ollama's /api/chat (messages + optional tools), not /api/generate
    # -- this is the actual missing piece that's blocked worker-hosted
    # tool-calling since it was first scoped. Same READ/NONE classification
    # and resource profile as model_chat: no persistent side effect, the
    # handler calls the worker's own loopback Ollama only, and proposing a
    # tool call here is not the same as it being allowed to run -- Core's
    # existing dispatcher/approval path (unchanged by this capability) is
    # still the only thing that can ever execute one.
    "model_chat_tools": dict(
        capability_id="model_chat_tools",
        version="1.0.0",
        authority_class=CapabilityClass.READ,
        side_effect_class=SideEffectClass.NONE,
        input_schema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": ["qwen3:8b", "mistral:7b"]},
                "messages": {"type": "array"},
                "tools": {"type": "array"},
            },
            "required": ["model", "messages"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "tool_calls": {"type": ["array", "null"]},
            },
        },
        timeout_seconds=120,
        resource_requirements={"cpu": "high", "memory_mb": 8192},
        network_required=False,
        secrets_required=[],
        idempotent=False,
        retry_policy={"max_attempts": 1, "backoff": "none"},
    ),
}
SAFE_CAPABILITIES.update(COMMANDER_READONLY_CAPABILITIES)

# Explicitly, permanently excluded from this workload's capability set --
# named here so their absence is a deliberate, visible design choice, not
# an oversight. Registering any of these raises CapabilityManifestError.
FORBIDDEN_CAPABILITY_IDS = {
    "shell_anything", "shell", "ssh", "production_admin", "database_admin",
    "qdrant_admin", "network_admin", "financial_trade", "external_post",
}


def validate_capability_declaration(declaration: dict):
    """A worker claims support for a capability by ID; this function is
    the ONLY authority on what that ID actually means. The worker's own
    declaration may include metadata (e.g. measured performance) but may
    NEVER override authority_class, side_effect_class, or any other
    fixed field -- exactly the Tool Registry's "computed, never
    declarable" discipline, applied to capability identity itself."""
    if "capability_id" not in declaration:
        raise CapabilityManifestError("worker capability declaration missing 'capability_id'")

    capability_id = declaration["capability_id"]

    if capability_id in FORBIDDEN_CAPABILITY_IDS:
        raise CapabilityManifestError(
            f"capability_id {capability_id!r} is permanently excluded from Worker Runtime v0.1's "
            "capability set -- not a bug, a deliberate boundary"
        )

    if capability_id not in SAFE_CAPABILITIES:
        raise CapabilityManifestError(
            f"unknown capability_id {capability_id!r} -- not part of the closed, allowlisted "
            "capability set; a worker cannot invent a new capability and have it trusted"
        )

    canonical = SAFE_CAPABILITIES[capability_id]

    # The worker may declare it SUPPORTS this capability; it may never
    # redeclare what the capability's authority/side-effect class is.
    for locked_field in ("authority_class", "side_effect_class", "network_required", "secrets_required"):
        if locked_field in declaration and declaration[locked_field] != canonical[locked_field]:
            raise CapabilityManifestError(
                f"worker attempted to override locked field {locked_field!r} for "
                f"capability_id {capability_id!r} -- capability authority is fixed by KARMO "
                "Core, not settable by a worker's declaration"
            )

    return dict(canonical)


def get_canonical_capability(capability_id):
    if capability_id not in SAFE_CAPABILITIES:
        raise CapabilityManifestError(f"unknown capability_id: {capability_id!r}")
    return dict(SAFE_CAPABILITIES[capability_id])
