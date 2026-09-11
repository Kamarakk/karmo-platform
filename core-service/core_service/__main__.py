"""Local process/CLI boundary for KARMO Core Service v0.1."""

import json
import sys

from . import __version__
from .control import ApprovalEngine, CapabilityClass, compute_approval_requirement


def health():
    # Exercise the safety-critical boundary without external side effects.
    requirement = compute_approval_requirement(CapabilityClass.READ)
    engine = ApprovalEngine()
    record = engine.request(
        requester="healthcheck",
        tool_id="core.health",
        tool_version=__version__,
        arguments={},
        authority_class=CapabilityClass.READ.value,
    )
    engine.approve(record.approval_id, approver="healthcheck")
    result = engine.execute(
        record.approval_id,
        tool_id="core.health",
        tool_version=__version__,
        arguments={},
        executor_identity="healthcheck",
        action=lambda: "ok",
    )
    payload = {
        "service": "karmo-core",
        "version": __version__,
        "status": "healthy" if result == "ok" else "unhealthy",
        "approval_floor_read": requirement.value,
        "persistence": "in-memory",
        "network_listener": False,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "healthy" else 1


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "health"
    if command != "health":
        print(json.dumps({"status": "error", "reason": f"unsupported command: {command}"}))
        return 2
    return health()


if __name__ == "__main__":
    raise SystemExit(main())
