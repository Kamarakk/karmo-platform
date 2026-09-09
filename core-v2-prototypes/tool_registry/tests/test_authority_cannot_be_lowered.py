"""Authority/security tests: the core guarantee this whole prototype
exists to prove. human_approval_requirement is computed, never
declarable, and financial_action/destructive_action can only ever RAISE
it, never lower it."""

import itertools

import pytest
from registry import (
    CapabilityClass,
    ApprovalRequirement,
    ManifestValidationError,
    ToolRegistry,
    compute_approval_requirement,
)
from examples import example_a_harmless_read_only, example_g_proposed_trade_execution


@pytest.fixture()
def registry():
    return ToolRegistry()


def test_manifest_cannot_declare_human_approval_requirement_directly(registry):
    manifest = example_a_harmless_read_only()
    manifest["human_approval_requirement"] = ApprovalRequirement.NONE  # attempted override

    with pytest.raises(ManifestValidationError, match="human_approval_requirement"):
        registry.register(manifest)


def test_attempting_to_declare_a_lower_requirement_is_still_refused_outright(registry):
    """Not merely ignored -- refused. A tool author cannot even attempt
    to smuggle a lower requirement through; the whole manifest is
    rejected, forcing the field's removal, not a silent override."""
    manifest = example_g_proposed_trade_execution()
    manifest["human_approval_requirement"] = ApprovalRequirement.NONE

    with pytest.raises(ManifestValidationError):
        registry.register(manifest)


@pytest.mark.parametrize(
    "capability_class,financial_action,destructive_action",
    list(itertools.product(
        list(CapabilityClass),
        [False, True],
        [False, True],
    )),
)
def test_computed_requirement_matrix(capability_class, financial_action, destructive_action):
    """Every combination of capability_class x financial_action x
    destructive_action -- per Workstream 13's own acceptance gate: a
    small combinatorial matrix, not one example."""
    result = compute_approval_requirement(capability_class, financial_action, destructive_action)

    floor = {
        CapabilityClass.READ: ApprovalRequirement.NONE,
        CapabilityClass.DRAFT_PROPOSE: ApprovalRequirement.NOTIFY_ONLY,
        CapabilityClass.REVERSIBLE_WRITE: ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
        CapabilityClass.EXTERNAL_ACTION: ApprovalRequirement.EXPLICIT_PER_CALL,
        CapabilityClass.DESTRUCTIVE_HIGH_IMPACT: ApprovalRequirement.EXPLICIT_PER_CALL,
    }[capability_class]

    if financial_action or destructive_action:
        # financial/destructive always force at least EXPLICIT_PER_CALL,
        # regardless of how low the base capability_class floor was.
        assert result == ApprovalRequirement.EXPLICIT_PER_CALL
    else:
        assert result == floor

    # The result is NEVER weaker than the base floor, no matter what the
    # flags are -- the central "cannot be lowered" guarantee, checked on
    # every single combination.
    order = [
        ApprovalRequirement.NONE,
        ApprovalRequirement.NOTIFY_ONLY,
        ApprovalRequirement.EXPLICIT_PER_SESSION_OR_TASK,
        ApprovalRequirement.EXPLICIT_PER_CALL,
    ]
    assert order.index(result) >= order.index(floor)


def test_trade_execution_example_requires_explicit_per_call(registry):
    """G's specific requirement, named explicitly by the program
    instruction: trade execution MUST require EXPLICIT_PER_CALL."""
    manifest = example_g_proposed_trade_execution()
    tool = registry.register(manifest)

    assert tool.computed_approval_requirement == ApprovalRequirement.EXPLICIT_PER_CALL


def test_harmless_read_only_example_requires_no_approval(registry):
    manifest = example_a_harmless_read_only()
    tool = registry.register(manifest)

    assert tool.computed_approval_requirement == ApprovalRequirement.NONE
