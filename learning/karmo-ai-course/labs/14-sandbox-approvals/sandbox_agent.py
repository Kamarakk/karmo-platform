"""Module 14: an agent that can act, fenced in by code-owned rules.

- File tools only work inside ./sandbox (rules.sandbox_path).
- Refunds are checked by code (rules.check_refund), never by the model.
- Refunds over $50 stop and ask YOU. Anything but "y" is a no.

Course version: code/sandbox-approval/
Usage: python3 sandbox_agent.py "Read ticket.txt and handle the refund it asks for."
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from karmo_llm import LLMError, chat  # noqa: E402
import rules  # noqa: E402

MAX_STEPS = 6


def read_file(path: str) -> dict:
    try:
        return {"ok": True, "content": rules.sandbox_path(path).read_text(encoding="utf-8")}
    except (ValueError, OSError) as error:
        return {"ok": False, "error": str(error)}


def write_file(path: str, content: str) -> dict:
    try:
        rules.sandbox_path(path).write_text(content, encoding="utf-8")
        return {"ok": True}
    except (ValueError, OSError) as error:
        return {"ok": False, "error": str(error)}


def issue_refund(order_id: str) -> dict:
    decision = rules.check_refund(order_id)
    if not decision["allowed"]:
        return {"ok": False, "error": decision["reason"]}
    if decision["needs_approval"]:
        answer = input(f"\nAPPROVAL NEEDED: refund ${decision['amount']:.2f} on {order_id}? [y/N] ")
        if answer.strip().lower() != "y":
            return {"ok": False, "error": "Human denied the refund."}
    rules.mark_refunded(order_id)
    return {"ok": True, "refunded": decision["amount"], "order_id": order_id}


FUNCTIONS = {
    "read_file": lambda a: read_file(a.get("path", "")),
    "write_file": lambda a: write_file(a.get("path", ""), a.get("content", "")),
    "issue_refund": lambda a: issue_refund(a.get("order_id", "")),
}
TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file in the sandbox.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a file in the sandbox.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "issue_refund", "description": "Refund an order by id, e.g. A-1002.",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}},
]
SYSTEM = ("You are a support agent for a plant shop. Use tools. Never claim a refund "
          "happened unless the tool result says ok=true.")


def main() -> int:
    task = " ".join(sys.argv[1:]) or input("Task: ")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    try:
        for step in range(1, MAX_STEPS + 1):
            message = chat(messages, tools=TOOLS, temperature=0)["message"]
            calls = message.get("tool_calls") or []
            if not calls:
                print(f"\nAgent: {message['content']}")
                return 0
            messages.append(message)
            for call in calls:
                name = call["function"]["name"]
                args = call["function"].get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args or "{}")
                func = FUNCTIONS.get(name)
                result = func(args) if func else {"ok": False, "error": "unknown tool"}
                print(f"[step {step}] {name}({args}) -> {json.dumps(result)[:120]}")
                messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("Stopped: step limit reached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
