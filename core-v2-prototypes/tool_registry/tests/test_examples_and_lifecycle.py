"""All 7 required worked examples (A-G) register successfully and land
at the expected computed approval requirement -- the concrete proof
behind the architecture document's worked-examples table."""

import pytest
from registry import ApprovalRequirement, ManifestValidationError, ToolRegistry
from examples import ALL_EXAMPLES


EXPECTED_APPROVAL = {
    "A": ApprovalRequirement.NONE,
    "B": ApprovalRequirement.NONE,
    "C": ApprovalRequirement.EXPLICIT_PER_CALL,  # financial_action forces this even though REVERSIBLE_WRITE alone would only need per-session
    "D": ApprovalRequirement.EXPLICIT_PER_CALL,  # EXTERNAL_ACTION floor
    "E": ApprovalRequirement.EXPLICIT_PER_CALL,  # DESTRUCTIVE_HIGH_IMPACT floor
    "F": ApprovalRequirement.NONE,  # a read, no financial_action
    "G": ApprovalRequirement.EXPLICIT_PER_CALL,  # DESTRUCTIVE_HIGH_IMPACT + financial_action, both forcing it
}


@pytest.mark.parametrize("label", sorted(ALL_EXAMPLES))
def test_each_example_registers_and_computes_expected_approval(label):
    registry = ToolRegistry()
    manifest = ALL_EXAMPLES[label]()

    tool = registry.register(manifest)

    assert tool.computed_approval_requirement == EXPECTED_APPROVAL[label]


def test_no_example_manifest_references_a_real_external_system():
    """All network_requirements in the examples are explicitly labeled
    synthetic/not-connected -- proving this prototype never actually
    reaches a broker, social platform, BloomBoss system, or
    infrastructure, per the program's explicit prohibition."""
    for label, factory in ALL_EXAMPLES.items():
        manifest = factory()
        for requirement in manifest["network_requirements"]:
            assert "example" in requirement or "not connected" in requirement, (
                f"{label}'s network_requirements entry {requirement!r} "
                "must be clearly synthetic"
            )


def test_deprecation_lifecycle_is_additive_not_destructive():
    registry = ToolRegistry()
    manifest_v1 = ALL_EXAMPLES["A"]()
    registry.register(manifest_v1)

    registry.deprecate("karmolab.infra.get_service_status", "1.0.0", superseded_by="1.1.0")

    deprecated = registry.get("karmolab.infra.get_service_status", version="1.0.0")
    assert deprecated is not None  # still present, never deleted
    assert deprecated.deprecated_at is not None
    assert deprecated.superseded_by == "1.1.0"

    # A deprecated-only tool_id has no "current" version.
    assert registry.get("karmolab.infra.get_service_status") is None


def test_deprecating_unregistered_tool_refuses():
    registry = ToolRegistry()
    with pytest.raises(ManifestValidationError, match="unregistered"):
        registry.deprecate("nonexistent.tool", "1.0.0")
