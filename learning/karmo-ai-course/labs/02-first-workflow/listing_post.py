"""Module 2: your first workflow. Plant name in, listing post out.

Course version: code/02-ai-workflows/01-first-workflow-openai-api/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import LLMError, ask  # noqa: E402

PROMPT = """You write short, high-energy listing posts for a rare-plant shop that sells
variegated Alocasia in live auctions on Palmstreet.

Write one post for this plant. Keep it under 80 words, use line breaks,
no hashtags, at most two emojis.

<plant>
{plant}
</plant>
"""


def main() -> int:
    plant = " ".join(sys.argv[1:]) or input("Which plant is the post about? ")
    if not plant.strip():
        print("Error: give a plant name.", file=sys.stderr)
        return 1
    try:
        post = ask(PROMPT.format(plant=plant.strip()))
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    out = Path(__file__).resolve().parent / "out" / "post.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(post + "\n", encoding="utf-8")
    print(post)
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
