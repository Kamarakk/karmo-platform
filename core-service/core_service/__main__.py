"""Local process/CLI boundary for KARMO Core Service v0.1."""

from __future__ import annotations

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


def _render_operator_response(response: dict) -> None:
    print(f"KARMO> {response.get('message', '')}")
    if response.get("memory_status"):
        print(f"KARMO> memory={response['memory_status']}")
    if response.get("kind") == "karmolab_read":
        print(
            "KARMO> verification="
            f"{response.get('verification')} primary={response.get('primary_model')} "
            f"verifier={response.get('verifier_model')}"
        )
        print("KARMO> evidence=" + json.dumps(response.get("evidence"), sort_keys=True))


def operator_status() -> int:
    from .operator import KarmoOperator

    response = KarmoOperator().handle("KarmoLab status")
    _render_operator_response(response)
    evidence = response.get("evidence") or {}
    return 0 if evidence.get("mode") == "READ_ONLY" else 1


def chat() -> int:
    from .operator import KarmoOperator

    operator = KarmoOperator()
    print("KARMO> online — bounded READ-only activation mode. Type 'exit' to leave.")
    while True:
        try:
            text = input("Kamara> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if text.strip().lower() in {"exit", "quit", "/exit", "/quit"}:
            return 0
        response = operator.handle(text)
        _render_operator_response(response)


def webui() -> int:
    from .webui import serve

    mode = sys.argv[2] if len(sys.argv) > 2 else "loopback"
    return serve(mode=mode)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "health"
    if command == "health":
        return health()
    if command == "status":
        return operator_status()
    if command == "chat":
        return chat()
    if command == "webui":
        return webui()
    print(json.dumps({"status": "error", "reason": f"unsupported command: {command}"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
