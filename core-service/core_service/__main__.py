"""Local process/CLI boundary for KARMO Core Service v0.1."""

from __future__ import annotations

import json
import os
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


def task() -> int:
    """KARMO orchestration task board -- see core_service.orchestration.

    Not automated model dispatch: this CLI is meant to be run by a human,
    or by an AI session under the human's explicit direction (set
    KARMO_ACTOR to identify who/what is actually acting, e.g.
    'claude-code-session', so the durable task record never misattributes
    an action to the wrong actor).
    """
    from .operator import KarmoOperator

    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "reason": "usage: task <create|list|claim|complete> ..."}))
        return 2
    action = sys.argv[2]
    actor = os.environ.get("KARMO_ACTOR", os.environ.get("USER", "unknown"))
    operator = KarmoOperator()
    try:
        if action == "create":
            if len(sys.argv) < 4:
                print(json.dumps({"status": "error", "reason": "usage: task create <objective> [context]"}))
                return 2
            context = sys.argv[4] if len(sys.argv) > 4 else None
            result = operator.create_task(objective=sys.argv[3], context=context, actor=actor)
        elif action == "list":
            status_filter = sys.argv[3] if len(sys.argv) > 3 else None
            result = {"tasks": operator.list_tasks(status=status_filter)}
        elif action == "claim":
            if len(sys.argv) < 4:
                print(json.dumps({"status": "error", "reason": "usage: task claim <task_id>"}))
                return 2
            result = operator.claim_task(task_id=sys.argv[3], actor=actor)
        elif action == "complete":
            if len(sys.argv) < 5:
                print(json.dumps({"status": "error", "reason": "usage: task complete <task_id> <result>"}))
                return 2
            result = operator.complete_task(task_id=sys.argv[3], result=sys.argv[4], actor=actor)
        else:
            print(json.dumps({"status": "error", "reason": f"unsupported task action: {action}"}))
            return 2
    except Exception as exc:
        print(json.dumps({"status": "error", "reason": str(exc), "type": type(exc).__name__}))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


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
    if command == "task":
        return task()
    print(json.dumps({"status": "error", "reason": f"unsupported command: {command}"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
