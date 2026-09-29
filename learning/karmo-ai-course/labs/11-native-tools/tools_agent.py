"""Module 11: the same agent, using Ollama's native tool calling.

Instead of parsing JSON out of text, you describe tools with a schema and the
model returns structured tool_calls. This is how KARMO Core offers tools.

Course version: code/sdk-backed-agent/agent.py and code/03-ai-agents/02-openai-functions
Usage: python3 tools_agent.py "What did I pay per Pink Black Velvet and how many sold?"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import LLMError, chat  # noqa: E402
from plant_data import cultivar_summary, list_cultivars  # noqa: E402

MAX_STEPS = 6


def calculate(expression: str) -> dict:
    """Tiny safe calculator: digits, + - * / ( ) and dots only."""
    if not expression or any(ch not in "0123456789+-*/(). " for ch in expression):
        return {"error": "Only numbers and + - * / ( ) are allowed."}
    try:
        return {"result": round(eval(expression, {"__builtins__": {}}, {}), 4)}  # noqa: S307
    except Exception as error:  # noqa: BLE001
        return {"error": str(error)}


FUNCTIONS = {
    "list_cultivars": lambda args: list_cultivars(),
    "get_plant_stock": lambda args: cultivar_summary(args.get("cultivar", "")),
    "calculate": lambda args: calculate(args.get("expression", "")),
}

TOOLS = [
    {"type": "function", "function": {
        "name": "get_plant_stock",
        "description": "Units, status counts, landed cost per unit and sales for one cultivar.",
        "parameters": {"type": "object",
                       "properties": {"cultivar": {"type": "string", "description": "Cultivar name, e.g. Pink Black Velvet"}},
                       "required": ["cultivar"]}}},
    {"type": "function", "function": {
        "name": "list_cultivars",
        "description": "Names of every cultivar in the BloomBoss data.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Evaluate arithmetic like (235 - 54.24) / 54.24.",
        "parameters": {"type": "object",
                       "properties": {"expression": {"type": "string"}},
                       "required": ["expression"]}}},
]

SYSTEM = ("You are KARMO's plant assistant. Use tools for every number. "
          "Never guess. Answer in two sentences or fewer.")


def run(question: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for step in range(1, MAX_STEPS + 1):
        message = chat(messages, tools=TOOLS, temperature=0)["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return message["content"]
        messages.append(message)
        for call in calls:
            name = call["function"]["name"]
            args = call["function"].get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            func = FUNCTIONS.get(name)
            result = func(args) if func else {"error": f"Unknown tool {name}"}
            print(f"[step {step}] {name}({args}) -> {json.dumps(result)[:120]}")
            messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})
    return f"Stopped after {MAX_STEPS} steps without a final answer."


def main() -> int:
    question = " ".join(sys.argv[1:]) or input("Question: ")
    try:
        print("\n" + run(question))
    except (LLMError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
