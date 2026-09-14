"""Canonical Commander READ Pack v1 manifest fragments for review.

These declarations remain separate from SAFE_CAPABILITIES until promotion.
"""

from tool_registry_reuse import CapabilityClass

COMMANDER_READONLY_CAPABILITIES = {
    "commander.system_snapshot": {
        "capability_id": "commander.system_snapshot", "version": "1.0.0", "authority_class": CapabilityClass.READ, "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "object"}, "resource_requirements": {"cpu": "low", "memory_mb": 64},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [], "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.service_status": {
        "capability_id": "commander.service_status", "version": "1.0.0", "authority_class": CapabilityClass.READ, "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"], "additionalProperties": False},
        "output_schema": {"type": "object"}, "resource_requirements": {"cpu": "low", "memory_mb": 64},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [], "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.listener_snapshot": {
        "capability_id": "commander.listener_snapshot", "version": "1.0.0", "authority_class": CapabilityClass.READ, "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "output_schema": {"type": "object"}, "resource_requirements": {"cpu": "low", "memory_mb": 64},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [], "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.bounded_text_read": {
        "capability_id": "commander.bounded_text_read", "version": "1.0.0", "authority_class": CapabilityClass.READ, "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False},
        "output_schema": {"type": "object"}, "resource_requirements": {"cpu": "low", "memory_mb": 96},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [], "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.directory_list": {
        "capability_id": "commander.directory_list", "version": "1.0.0", "authority_class": CapabilityClass.READ, "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "additionalProperties": False},
        "output_schema": {"type": "object"}, "resource_requirements": {"cpu": "low", "memory_mb": 64},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [], "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
}
