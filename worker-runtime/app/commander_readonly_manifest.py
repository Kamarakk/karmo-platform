"""Canonical Commander READ Pack v1 manifest fragments for review.

These declarations are intentionally separate from SAFE_CAPABILITIES until
review is complete. Promotion requires explicit integration and tests.
"""

COMMANDER_READONLY_CAPABILITIES = {
    "commander.system_snapshot": {
        "version": "1.0.0", "authority_class": "READ", "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [],
        "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.service_status": {
        "version": "1.0.0", "authority_class": "READ", "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"], "additionalProperties": False},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [],
        "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.listener_snapshot": {
        "version": "1.0.0", "authority_class": "READ", "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [],
        "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.bounded_text_read": {
        "version": "1.0.0", "authority_class": "READ", "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [],
        "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
    "commander.directory_list": {
        "version": "1.0.0", "authority_class": "READ", "side_effect_class": "NONE",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "additionalProperties": False},
        "timeout_seconds": 10, "network_required": False, "secrets_required": [],
        "idempotent": True, "retry_policy": {"max_attempts": 1, "backoff": "none"},
    },
}
