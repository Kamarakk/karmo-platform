"""Long-running local-only runner for KARMO Core Service v0.1."""

from __future__ import annotations

import json
import signal
import time

from . import __version__
from .control import ApprovalEngine, CapabilityClass, compute_approval_requirement


def startup_health() -> dict:
    """Exercise the control boundary without external side effects."""
    requirement = compute_approval_requirement(CapabilityClass.READ)
    engine = ApprovalEngine()
    record = engine.request(
        requester="startup-healthcheck",
        tool_id="core.health",
        tool_version=__version__,
        arguments={},
        authority_class=CapabilityClass.READ.value,
    )
    engine.approve(record.approval_id, approver="startup-healthcheck")
    result = engine.execute(
        record.approval_id,
        tool_id="core.health",
        tool_version=__version__,
        arguments={},
        executor_identity="startup-healthcheck",
        action=lambda: "ok",
    )
    return {
        "service": "karmo-core",
        "version": __version__,
        "status": "healthy" if result == "ok" else "unhealthy",
        "approval_floor_read": requirement.value,
        "persistence": "in-memory",
        "network_listener": False,
        "persistent_writes": False,
        "worker_transport": False,
    }


def main() -> None:
    health = startup_health()
    print(json.dumps(health, sort_keys=True), flush=True)
    if health["status"] != "healthy":
        raise SystemExit(1)

    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while running:
        time.sleep(5)


if __name__ == "__main__":
    main()
