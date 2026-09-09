"""KARMO Tool/Capability Registry -- ISOLATED PROTOTYPE.

Not wired into any KARMO production path. Implements the manifest schema
and capability-classification enforcement from
docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md, reusing I-09's
5-tier classification verbatim rather than inventing a competing scheme.

Core guarantee this module exists to prove: a tool's required human
approval level is COMPUTED from its capability_class, financial_action,
and destructive_action flags -- it can never be independently declared,
and financial_action/destructive_action can only ever RAISE the computed
requirement, never lower it. See test_authority_cannot_be_lowered.py.
"""

from dataclasses import dataclass, field
from enum import Enum


class CapabilityClass(str, Enum):
    READ = "READ"
    DRAFT_PROPOSE = "DRAFT_PROPOSE"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    DESTRUCTIVE_HIGH_IMPACT = "DESTRUCTIVE_HIGH_IMPACT"


class ApprovalRequirement(str, Enum):
    NONE = "NONE"
    NOTIFY_ONLY = "NOTIFY_ONLY"
    EXPLICIT_PER_SESSION_OR_TASK = "EXPLICIT_PER_SESSION_OR_TASK"
    EXPLICIT_PER_CALL = "EXPLICIT_PER_CALL"


# Ordinal strictness order -- index position is used to compute a MAX
# across candidate requirements. Do not reorder without updating every
# caller of compute_approval_requirement.
_APPROVAL_ORDER = [
    ApprovalRequirement.NONE,
    ApprovalRequirement.NOTIFY_ONLY,
    ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
    ApprovalRequirement.EXPLICIT_PER_CALL,
]

CAPABILITY_FLOOR = {
    CapabilityClass.READ: ApprovalRequirement.NONE,
    CapabilityClass.DRAFT_PROPOSE: ApprovalRequirement.NOTIFY_ONLY,
    CapabilityClass.REVERSIBLE_WRITE: ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
    CapabilityClass.EXTERNAL_ACTION: ApprovalRequirement.EXPLICIT_PER_CALL,
    CapabilityClass.DESTRUCTIVE_HIGH_IMPACT: ApprovalRequirement.EXPLICIT_PER_CALL,
}

# Every field a manifest MUST declare. "human_approval_requirement" is
# deliberately NOT in this list -- it must never appear in an input
# manifest at all; see ManifestValidationError below.
REQUIRED_MANIFEST_FIELDS = [
    "tool_id",
    "domain",
    "version",
    "description",
    "input_schema",
    "output_schema",
    "capability_class",
    "read_scope",
    "write_scope",
    "external_side_effects",
    "financial_action",
    "destructive_action",
    "network_requirements",
    "secret_requirements",
    "invocation_identity",
    "timeout_seconds",
    "retry_policy",
    "idempotent",
    "idempotency_mechanism",
    "rollback_or_compensation",
    "health_check",
    "deprecation_policy",
    "dependencies",
    "observability",
    "failure_isolation",
]

FORBIDDEN_MANIFEST_FIELDS = {
    "human_approval_requirement",  # computed only, never declarable
}


class ManifestValidationError(ValueError):
    """Refuse-don't-guess: raised with the exact missing/forbidden field
    named, never silently defaulted. Mirrors bootstrap_legacy_registry.py's
    and registry_repair.py's refusal pattern."""


def compute_approval_requirement(capability_class, financial_action, destructive_action):
    """The one function that decides required human approval. Never
    settable directly by a manifest -- see register()."""
    candidates = [CAPABILITY_FLOOR[capability_class]]
    if financial_action:
        candidates.append(ApprovalRequirement.EXPLICIT_PER_CALL)
    if destructive_action:
        candidates.append(ApprovalRequirement.EXPLICIT_PER_CALL)
    return max(candidates, key=_APPROVAL_ORDER.index)


@dataclass(frozen=True)
class RegisteredTool:
    """The stored, authoritative record of one registered tool version.
    computed_approval_requirement is derived at registration time and
    frozen -- it is recomputed, never trusted from caller input."""

    manifest: dict
    computed_approval_requirement: ApprovalRequirement
    deprecated_at: str = None
    superseded_by: str = None

    @property
    def tool_id(self):
        return self.manifest["tool_id"]

    @property
    def version(self):
        return self.manifest["version"]

    @property
    def capability_class(self):
        return self.manifest["capability_class"]


class ToolRegistry:
    """In-memory registry (isolated prototype -- a real implementation
    would use public.tool_registry per the architecture doc, following
    document_registry's own PostgreSQL-authoritative pattern)."""

    def __init__(self):
        self._tools = {}  # (tool_id, version) -> RegisteredTool

    def register(self, manifest: dict) -> RegisteredTool:
        for field_name in FORBIDDEN_MANIFEST_FIELDS:
            if field_name in manifest:
                raise ManifestValidationError(
                    f"'{field_name}' must never be declared in a manifest -- "
                    "it is computed by the registry, not settable by a tool author"
                )

        for field_name in REQUIRED_MANIFEST_FIELDS:
            if field_name not in manifest:
                raise ManifestValidationError(f"missing required field: '{field_name}'")

        capability_class = manifest["capability_class"]
        if not isinstance(capability_class, CapabilityClass):
            raise ManifestValidationError(
                f"'capability_class' must be a CapabilityClass member, got {capability_class!r}"
            )

        key = (manifest["tool_id"], manifest["version"])
        if key in self._tools:
            raise ManifestValidationError(
                f"tool_id/version already registered: {key} -- "
                "register a new version, never overwrite one in place"
            )

        computed = compute_approval_requirement(
            capability_class,
            manifest["financial_action"],
            manifest["destructive_action"],
        )

        tool = RegisteredTool(manifest=dict(manifest), computed_approval_requirement=computed)
        self._tools[key] = tool
        return tool

    def get(self, tool_id, version=None):
        if version is not None:
            return self._tools.get((tool_id, version))
        matches = [t for (tid, _), t in self._tools.items() if tid == tool_id and t.deprecated_at is None]
        if not matches:
            return None
        return sorted(matches, key=lambda t: t.version)[-1]

    def deprecate(self, tool_id, version, *, superseded_by=None):
        key = (tool_id, version)
        if key not in self._tools:
            raise ManifestValidationError(f"cannot deprecate unregistered tool: {key}")
        existing = self._tools[key]
        # Append-only lifecycle, mirroring document_registry: replace the
        # frozen record with a deprecated copy, never mutate history.
        self._tools[key] = RegisteredTool(
            manifest=existing.manifest,
            computed_approval_requirement=existing.computed_approval_requirement,
            deprecated_at="deprecated",
            superseded_by=superseded_by,
        )

    def all_tools(self):
        return list(self._tools.values())
