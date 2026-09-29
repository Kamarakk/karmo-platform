"""Module 5: measure local models on your own hardware.

Runs the same prompt twice per model (first run includes loading the model).
Usage: python3 bench.py llama3.2:1b llama3.2:3b
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import LLMError, timed_ask  # noqa: E402

PROMPT = ("In 5 bullet points, explain how to keep a variegated Alocasia healthy "
          "indoors in a grow tent.")


def main() -> int:
    models = sys.argv[1:] or ["llama3.2:1b", "llama3.2:3b"]
    print(f"{'model':32} {'run':>4} {'total s':>8} {'load s':>7} {'tokens':>7} {'tok/s':>7}")
    for model in models:
        for run in (1, 2):
            try:
                r = timed_ask(PROMPT, model=model)
            except LLMError as error:
                print(f"{model:32} error: {error}")
                break
            print(f"{model:32} {run:>4} {r['seconds']:>8} {r['load_seconds']:>7} "
                  f"{r['tokens']:>7} {r['tokens_per_second']:>7}")
    print("\nRun 1 includes loading the model into memory. Run 2 is the real speed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
