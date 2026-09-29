"""Module 3: few-shot prompting. Same task as Module 2, plus examples of your style.

Run with --no-examples to see the difference.
Course version: code/02-ai-workflows/03-few-shot-prompting/main.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from karmo_llm import LLMError, ask  # noqa: E402

SYSTEM = """You write listing posts for a rare-plant shop that sells variegated Alocasia
in live auctions on Palmstreet. Under 80 words, line breaks, no hashtags,
at most two emojis. Match the tone and structure of the examples.
Never copy facts from the examples; use only facts about the given plant."""


def build_prompt(plant: str, use_examples: bool) -> str:
    parts = []
    if use_examples:
        examples = json.loads((HERE / "examples.json").read_text(encoding="utf-8"))
        for i, ex in enumerate(examples, 1):
            parts.append(f"<example-{i}>\n<plant>{ex['plant']}</plant>\n<post>\n{ex['post']}\n</post>\n</example-{i}>")
    parts.append(f"<plant>{plant}</plant>\nWrite the post.")
    return "\n\n".join(parts)


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-examples"]
    use_examples = "--no-examples" not in sys.argv
    plant = " ".join(args) or input("Which plant is the post about? ")
    try:
        post = ask(build_prompt(plant, use_examples), system=SYSTEM)
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    label = "WITH examples" if use_examples else "WITHOUT examples"
    print(f"--- {label} ---\n{post}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
