from capability_manifest import SAFE_CAPABILITIES, get_canonical_capability
from commander_readonly_manifest import COMMANDER_READONLY_CAPABILITIES
from sandbox import _HANDLERS
import capabilities  # noqa: F401


def test_commander_pack_is_canonical_and_read_only():
    for capability_id in COMMANDER_READONLY_CAPABILITIES:
        canonical = get_canonical_capability(capability_id)
        assert canonical["authority_class"] == "READ"
        assert canonical["side_effect_class"] == "NONE"
        assert canonical["network_required"] is False
        assert canonical["secrets_required"] == []
        assert capability_id in SAFE_CAPABILITIES


def test_commander_pack_has_fixed_registered_handlers():
    for capability_id in COMMANDER_READONLY_CAPABILITIES:
        assert capability_id in _HANDLERS


def test_forbidden_shell_is_still_absent():
    assert "shell" not in SAFE_CAPABILITIES
    assert "commander.shell" not in SAFE_CAPABILITIES
    assert "shell" not in _HANDLERS
    assert "commander.shell" not in _HANDLERS
