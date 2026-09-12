"""KARMO-owned capability registry.

This module promotes the already-verified Core v2 registry semantics behind the
production ``core_service`` package boundary. It is side-effect free by itself;
persistence adapters may store the validated records, but callers can never
supply or lower the approval requirement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .control import ApprovalRequirement, CapabilityClass, compute_approval_requirement


REQUIRED_MANIFEST_FIELDS = (
    "tool_id", "domain", "version", "description", "input_schema", "output_schema",
    "capability_class", "read_scope", "write_scope", "external_side_effects",
    "financial_action", "destructive_action", "network_requirements",
    "secret_requirements", "invocation_identity", "timeout_seconds", "retry_policy",
    "idempotent", "idempotency_mechanism", "rollback_or_compensation", "health_check",
    "deprecation_policy", "dependencies", "observability", "failure_isolation",
)
FORBIDDEN_MANIFEST_FIELDS = frozenset({"human_approval_requirement", "approval_requirement"})


class ManifestValidationError(ValueError):
    """Closed-schema refusal. KARMO refuses ambiguity rather than guessing."""


@dataclass(frozen=True)
class RegisteredCapability:
    manifest: dict
    computed_approval_requirement: ApprovalRequirement
    deprecated: bool = False
    superseded_by: str | None = None

    @property
    def tool_id(self) -> str:
        return self.manifest["tool_id"]

    @property
    def version(self) -> str:
        return self.manifest["version"]

    @property
    def capability_class(self) -> CapabilityClass:
        return self.manifest["capability_class"]


class CapabilityRegistry:
    """Authoritative in-process registry facade with optional persistence.

    The persistence object, when supplied, must expose ``put(record)``,
    ``get(tool_id, version)``, and ``list(tool_id=None)``. Keeping the interface
    tiny allows PostgreSQL to remain the production authority without forcing
    database access into unit tests.
    """

    def __init__(self, persistence=None):
        self._persistence = persistence
        self._records: dict[tuple[str, str], RegisteredCapability] = {}

    @staticmethod
    def validate_manifest(manifest: dict) -> dict:
        if not isinstance(manifest, dict):
            raise ManifestValidationError("manifest must be a mapping")
        forbidden = set(manifest) & FORBIDDEN_MANIFEST_FIELDS
        if forbidden:
            raise ManifestValidationError(f"approval fields are computed by KARMO: {sorted(forbidden)}")
        missing = [name for name in REQUIRED_MANIFEST_FIELDS if name not in manifest]
        if missing:
            raise ManifestValidationError(f"missing required field(s): {missing}")
        unknown = set(manifest) - set(REQUIRED_MANIFEST_FIELDS)
        if unknown:
            raise ManifestValidationError(f"unknown manifest field(s): {sorted(unknown)}")
        normalized = dict(manifest)
        try:
            normalized["capability_class"] = CapabilityClass(normalized["capability_class"])
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError("invalid capability_class") from exc
        if not normalized["tool_id"] or not normalized["version"]:
            raise ManifestValidationError("tool_id and version must be non-empty")
        if not isinstance(normalized["financial_action"], bool) or not isinstance(normalized["destructive_action"], bool):
            raise ManifestValidationError("financial_action and destructive_action must be booleans")
        timeout = normalized["timeout_seconds"]
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise ManifestValidationError("timeout_seconds must be a positive integer")
        return normalized

    def register(self, manifest: dict) -> RegisteredCapability:
        normalized = self.validate_manifest(manifest)
        key = (normalized["tool_id"], normalized["version"])
        if self.get(*key) is not None:
            raise ManifestValidationError(f"tool_id/version already registered: {key}")
        approval = compute_approval_requirement(
            normalized["capability_class"],
            financial_action=normalized["financial_action"],
            destructive_action=normalized["destructive_action"],
        )
        record = RegisteredCapability(normalized, approval)
        if self._persistence is not None:
            self._persistence.put(record)
        else:
            self._records[key] = record
        return record

    def get(self, tool_id: str, version: str | None = None):
        if self._persistence is not None:
            if version is not None:
                return self._persistence.get(tool_id, version)
            matches = [r for r in self._persistence.list(tool_id) if not r.deprecated]
        else:
            if version is not None:
                return self._records.get((tool_id, version))
            matches = [r for (tid, _), r in self._records.items() if tid == tool_id and not r.deprecated]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.version)[-1]

    def all(self):
        if self._persistence is not None:
            return list(self._persistence.list())
        return list(self._records.values())
