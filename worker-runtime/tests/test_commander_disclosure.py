import pytest

from commander_disclosure import get_capability_manifest, list_capabilities


def test_level_one_disclosure_returns_summaries_without_schemas():
    items = list_capabilities()
    assert items
    assert all(set(item) == {"capability_id", "summary"} for item in items)
    assert not any("input_schema" in item for item in items)


def test_level_two_disclosure_returns_only_selected_manifest():
    manifest = get_capability_manifest("commander.system_snapshot")
    assert manifest["capability_id"] == "commander.system_snapshot"
    assert manifest["authority_class"] == "READ"
    assert manifest["network_required"] is False
    assert "input_schema" in manifest


def test_unknown_capability_fails_closed():
    with pytest.raises(KeyError):
        get_capability_manifest("commander.shell")
