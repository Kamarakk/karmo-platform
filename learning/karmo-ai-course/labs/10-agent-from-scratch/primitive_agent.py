"""Module 10: an agent loop written by hand, with no tool-calling API.

The model asks for a tool by replying with JSON. Your code parses it, runs the
tool, sends the result back, and repeats until the model gives a final answer.

Course version: code/primitive-agent/agent.py and code/03-ai-agents/01-tool-use-from-scratch
Usage: python3 primitive_agent.py "How many Pink Black Velvet do I have left?"
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import LLMError, chat  # noqa: E402
from plant_data import cultivar_summary, list_cultivars  # noqa: E402

MAX_STEPS = 5
TOOLS = {
    "list_cultivars": lambda args: list_cultivars(),
    "get_plant_stock": lambda args: cultivar_summary(args.get("cultivar", "")),
}
SYSTEM = """You are KARMO's plant assistant. You can use these tools:

- list_cultivars(): names of every cultivar in the BloomBoss data
- get_plant_stock(cultivar): units, status counts, cost and sales for one cultivar

To use a tool, reply with ONLY one line of JSON and nothing else, for example:
{"tool": "get_plant_stock", "arguments": {"cultivar": "Pink Black Velvet"}}

When you have what you need, reply with a normal sentence for the user.
Never invent numbers. Use only tool results."""

_JSON = re.compile(r"\{.*\}", re.DOTALL)


def parse_tool_request(text: str):
    """Return (name, arguments) if the reply is a tool request, else None."""
    match = _JSON.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("tool") in TOOLS:
        return data["tool"], data.get("arguments") or {}
    return None


def run(question: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for step in range(1, MAX_STEPS + 1):
        reply = chat(messages, temperature=0)["message"]["content"]
        request = parse_tool_request(reply)
        if request is None:
            return reply
        name, arguments = request
        result = TOOLS[name](arguments)
        print(f"[step {step}] model asked for {name}({arguments})")
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": f"TOOL RESULT for {name}:\n{json.dumps(result)}"})
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
