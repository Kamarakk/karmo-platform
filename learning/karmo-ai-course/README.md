# KARMO AI Agents & Workflows Course

Your course, rebuilt from Maximilian Schwarzmüller's **AI Agents & Workflows** (the Udemy course cloned at `~/KARMO-DEV/ai-agents-workflows-course`). Every lab runs on **Ollama on your Mac** (no OpenAI, no API keys) and uses **your real BloomBoss data**.

## How to use this folder

1. Open the modules in order: `modules/00-setup.md`, then `01`, `02`, ...
2. Every module has 5 to 8 numbered steps. Each step has one command to copy and paste, and says what you should see.
3. Every command starts from a full path, so you can open a fresh Terminal at any step.
4. When a module's "Done when" boxes are all true, tick it in the table below.

Each module takes about 30 to 45 minutes, which fits a lunch block.

## Where things are

| Folder | What's in it |
| --- | --- |
| `modules/` | The 22 step-by-step guides (00 to 21) |
| `labs/` | Working code for each module, tested before delivery |
| `templates/` | Worksheets for Modules 20 and 21 |
| `labs/common/` | `karmo_llm.py` (the Ollama client every lab uses) and `plant_data.py` (reads your BloomBoss CSV) |
| `~/KARMO-DEV/ai-agents-workflows-course/code/` | The original course code, for comparison |

## Change the model for any lab

```bash
export KARMO_MODEL=qwen3:8b      # default is llama3.2:3b (Module 01 uses --model instead)
```

## Progress

| # | Module | Part | Done |
| --- | --- | --- | --- |
| 00 | Setup | Start | [ ] |
| 01 | Workflows vs agents | 1 · Workflows | [ ] |
| 02 | Your first workflow | 1 · Workflows | [ ] |
| 03 | Few-shot prompting | 1 · Workflows | [ ] |
| 04 | Multi-step, multi-model | 1 · Workflows | [ ] |
| 05 | Local models on your hardware | 1 · Workflows | [ ] |
| 06 | Structured output | 1 · Workflows | [ ] |
| 07 | Control flow and human in the loop | 1 · Workflows | [ ] |
| 08 | Visual workflows (n8n) | 1 · Workflows | [ ] |
| 09 | Claude Code as a power user | 2 · Agentic tools | [ ] |
| 10 | The agent loop from scratch | 3 · Agents | [ ] |
| 11 | Native tool calling | 3 · Agents | [ ] |
| 12 | Multi-agent | 3 · Agents | [ ] |
| 13 | General agents and their risks | 3 · Agents | [ ] |
| 14 | Sandboxing and approvals | 3 · Agents | [ ] |
| 15 | Agent frameworks (LangGraph) | 3 · Agents | [ ] |
| 16 | MCP | 4 · Beyond the course | [ ] |
| 17 | RAG with citations | 4 · Beyond the course | [ ] |
| 18 | Evals | 4 · Beyond the course | [ ] |
| 19 | Model routing | 4 · Beyond the course | [ ] |
| 20 | Productizing KARMO | 4 · Beyond the course | [ ] |
| 21 | Staying current | 4 · Beyond the course | [ ] |

## Safety rules for every lab

- Labs run only on your Mac. Nothing here touches KARMO-AI01 or the workers.
- Nothing here needs a password, key, or cloud account.
- Module 13's agent never executes shell commands; it only logs what it tried.
