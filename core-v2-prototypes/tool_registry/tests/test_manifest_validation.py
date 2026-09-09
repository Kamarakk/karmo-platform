"""Contract tests: the registry must refuse a manifest missing any
required field, one test per field, per the Core v2 Test Strategy's own
acceptance-gate requirement -- not one aggregate test."""

import pytest
from registry import REQUIRED_MANIFEST_FIELDS, ManifestValidationError, ToolRegistry
from examples import example_a_harmless_read_only


@pytest.fixture()
def registry():
    return ToolRegistry()


@pytest.mark.parametrize("missing_field", REQUIRED_MANIFEST_FIELDS)
def test_refuses_manifest_missing_each_required_field(registry, missing_field):
    manifest = example_a_harmless_read_only()
    del manifest[missing_field]

    with pytest.raises(ManifestValidationError, match=missing_field):
        registry.register(manifest)


def test_accepts_a_complete_valid_manifest(registry):
    manifest = example_a_harmless_read_only()
    tool = registry.register(manifest)
    assert tool.tool_id == "karmolab.infra.get_service_status"


def test_refuses_duplicate_tool_id_and_version(registry):
    manifest = example_a_harmless_read_only()
    registry.register(manifest)

    with pytest.raises(ManifestValidationError, match="already registered"):
        registry.register(manifest)


def test_refuses_unknown_fields_not_part_of_the_schema(registry):
    """Found by this program's own adversarial review: an unrecognized
    field (e.g. a misnamed override attempt like
    'required_approval_override') used to be silently accepted and
    stored rather than refused."""
    manifest = example_a_harmless_read_only()
    manifest["totally_made_up_field"] = "sneaky"

    with pytest.raises(ManifestValidationError, match="totally_made_up_field"):
        registry.register(manifest)


def test_registering_a_new_version_of_same_tool_id_succeeds(registry):
    manifest_v1 = example_a_harmless_read_only()
    registry.register(manifest_v1)

    manifest_v2 = dict(manifest_v1)
    manifest_v2["version"] = "2.0.0"
    tool_v2 = registry.register(manifest_v2)

    assert tool_v2.version == "2.0.0"
    assert registry.get("karmolab.infra.get_service_status", version="1.0.0") is not None
