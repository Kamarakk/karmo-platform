"""Re-exports from core-v2-prototypes/tool_registry/registry.py -- reused
directly, not duplicated. See _prototype_paths.py."""

import _prototype_paths  # noqa: F401  (sys.path side effect, must run first)
from registry import (  # noqa: F401
    CAPABILITY_FLOOR,
    CapabilityClass,
    ManifestValidationError,
    ApprovalRequirement,
    compute_approval_requirement,
)
