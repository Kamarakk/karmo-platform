"""Module 7: control flow, human in the loop, and an outside service.

1. Model writes a draft plant-care card.
2. Model grades the draft against a checklist (JSON).
3. Code loops: rewrite until the grade passes or 3 tries are used.
4. You approve, give feedback, or quit.
5. On approval the card is saved and your Mac shows a notification.

Course version: code/02-ai-workflows/10-control-flow ... 13-final-version
Usage: python3 review_loop.py "Alocasia Frydek Variegata"
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from karmo_llm import LLMError, ask, ask_json  # noqa: E402

MAX_ROUNDS = 3
CHECKLIST = ("mentions light, watering, humidity and temperature; under 120 words; "
             "no claims about pests or diseases the plant does not have")
GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "passes": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
    "required": ["passes", "feedback"],
}


def write_draft(plant: str, previous: str = "", feedback: str = "") -> str:
    prompt = f"Write a short care card for {plant}. Requirements: {CHECKLIST}."
    if previous:
        prompt += f"\n\nImprove this draft:\n{previous}\n\nFeedback to apply:\n{feedback}"
    return ask(prompt)


def grade(draft: str) -> dict:
    return ask_json(
        f"Grade this care card against the checklist: {CHECKLIST}.\n\n<card>\n{draft}\n</card>",
        GRADE_SCHEMA,
    )


def notify(message: str) -> None:
    """The 'outside service'. On a Mac, a system notification; elsewhere, a printout."""
    if platform.system() == "Darwin":
        subprocess.run(["osascript", "-e",
                        f'display notification "{message}" with title "KARMO course"'],
                       check=False)
    print(f"[notification] {message}")


def main() -> int:
    plant = " ".join(sys.argv[1:]) or input("Plant: ")
    try:
        draft = write_draft(plant)
        for round_no in range(1, MAX_ROUNDS + 1):
            result = grade(draft)
            print(f"\n--- Round {round_no}: passes={result['passes']} ---\n{draft}")
            if result["passes"]:
                break
            print(f"Grader feedback: {result['feedback']}")
            draft = write_draft(plant, draft, result["feedback"])
        while True:
            answer = input("\nType 'accept', 'quit', or feedback to rewrite: ").strip()
            if answer.lower() == "quit":
                print("Stopped. Nothing saved.")
                return 0
            if answer.lower() == "accept":
                break
            if answer:
                draft = write_draft(plant, draft, answer)
                print(f"\n--- Rewritten ---\n{draft}")
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    out = HERE / "out" / "care_card.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(draft + "\n", encoding="utf-8")
    notify(f"Care card for {plant} approved and saved")
    print(f"Saved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
