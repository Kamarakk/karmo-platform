"""Progressive disclosure for Commander capability discovery.

This layer reveals only capability summaries first. Full schemas are returned
only for a selected capability. It does not grant authority or execute work.
"""

from __future__ import annotations

from commander_readonly_manifest import COMMANDER_READONLY_CAPABILITIES

_SUMMARIES = {
    "commander.system_snapshot": "Read host CPU/load, memory, and root-disk summary.",
    "commander.service_status": "Read status of a fixed allowlisted KARMO service.",
    "commander.listener_snapshot": "Read a bounded snapshot of listening TCP/UDP sockets.",
    "commander.bounded_text_read": "Read a small UTF-8 text file inside allowed_root.",
    "commander.directory_list": "List a bounded directory inside allowed_root.",
}


def list_capabilities():
    """Level 1 disclosure: names and one-line descriptions only."""
    return [
        {"capability_id": capability_id, "summary": _SUMMARIES[capability_id]}
        for capability_id in sorted(COMMANDER_READONLY_CAPABILITIES)
    ]


def get_capability_manifest(capability_id):
    """Level 2 disclosure: exact manifest for one already-selected capability."""
    if capability_id not in COMMANDER_READONLY_CAPABILITIES:
        raise KeyError(capability_id)
    manifest = dict(COMMANDER_READONLY_CAPABILITIES[capability_id])
    manifest["capability_id"] = capability_id
    manifest["summary"] = _SUMMARIES[capability_id]
    return manifest
