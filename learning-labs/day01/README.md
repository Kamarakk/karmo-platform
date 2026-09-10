# Day 1 — LLMs + Python Control Layer (workspace)

Full lesson: `../../docs/learning/DAY_01_LLM_PYTHON_CONTROL.md`

This directory holds the code you write for Day 1. Nothing here solves the
lesson for you — the starter files below only give you a place to start and
a reminder of what each part needs. Run `check_environment.py` first; write
everything else yourself.

## Files

- `check_environment.py` — run this first. Verifies Python/venv, the Day-1
  packages, and local Ollama connectivity. This is a helper, not part of the
  lesson exercise.
- `model_client.py` — **you write this.** Starter stub for Part 2 (first
  real model call) and Part 3 (asking for a structured tool proposal).
- `tool_validator.py` — **you write this.** Starter stub for Part 4
  (deterministic validation/control code — the actual security boundary).
- `break_it_notes.md` — the 5 adversarial cases from Part 5, as a checklist
  to predict against before you run each one. Not answers.

## How to run things

From the repo root:

```bash
learning-labs/.venv/bin/python learning-labs/day01/check_environment.py
learning-labs/.venv/bin/python learning-labs/day01/model_client.py
learning-labs/.venv/bin/python learning-labs/day01/tool_validator.py
```

Or activate the venv first:

```bash
source learning-labs/.venv/bin/activate
python learning-labs/day01/check_environment.py
```

## Boundary reminder

No production access. No `karmo-ai01`. Ollama stays on `127.0.0.1` only.
Synthetic data only — nothing from real KARMO documents or production.
