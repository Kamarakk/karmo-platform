# Day 1 Local Learning Environment — Setup Verification

Date: 2026-09-10
Machine: KARMO-DEV01 (Apple M3, arm64, macOS 14.8.7)
Branch: `learning/ai-agent-engineering-program` (PR #26, not merged)

## Verified toolchain versions

| Tool | Version | Notes |
|---|---|---|
| macOS | 14.8.7 (arm64) | already current |
| Homebrew | 6.0.22 | already installed |
| git | 2.55.0 | already installed |
| gh | 2.100.0 | already authenticated as `Kamarakk` |
| Claude Code | 2.1.236 | already installed |
| Python | 3.12.14 | **newly installed** via `brew install python@3.12` — system Python was 3.9.6, did not meet the 3.11+ requirement |
| pip | 26.2.1 | installed with Python 3.12, upgraded in the venv |
| Ollama | 0.33.3 | **newly installed** via `brew install ollama` (Homebrew formula, not the desktop app) |
| Docker | 29.8.0 | already present (Homebrew), not required for Day 1 |

## Python executable / virtual environment

- Interpreter used to create the venv: `/opt/homebrew/bin/python3.12`
- Virtual environment path: `~/KARMO-DEV/learning-labs/.venv`
- Venv Python executable: `~/KARMO-DEV/learning-labs/.venv/bin/python` → Python 3.12.14
- System Python packages are **not** used for the course; the venv is isolated.

## Installed Day-1 packages (in the venv)

| Package | Version |
|---|---|
| pytest | 9.1.1 |
| pydantic | 2.13.5 |
| httpx | 0.28.1 |
| jupyterlab | 4.6.3 |

All four imported successfully (verified via `learning-labs/day01/check_environment.py`, see smoke test below). Per `SETUP_AND_TOOLCHAIN.md`'s explicit deferral note, heavier packages (PyTorch, Transformers, PEFT, sentence-transformers, MLX, MCP, etc.) were **not** installed — they're scoped to later lessons.

## Ollama status

- Installed via Homebrew formula `ollama` (0.33.3), not the desktop app or any other installer.
- Running as a `brew services` background service (`sh.brew.ollama`, auto-starts at login for this user).
- **Localhost-only, verified**: `lsof -nP -iTCP:11434 -sTCP:LISTEN` shows the listener bound to `127.0.0.1:11434` only — not `0.0.0.0`, not reachable from the LAN. `OLLAMA_HOST` was left unset (Ollama's own localhost-only default), not overridden.
- API reachability confirmed: `GET http://127.0.0.1:11434/api/version` → `{"version":"0.33.3"}`.

## Installed local models

| Model tag | Disk size | Purpose | Why this variant |
|---|---|---|---|
| `qwen2.5:1.5b` | 986 MB | small Qwen generative model | Deliberately the smallest well-supported Qwen instruct tag, to guarantee comfortable headroom on this machine's 8 GB unified memory while other apps (Claude Code, editor, browser) are also running during the lesson. |
| `llama3.2:3b` | 2.0 GB | small Llama generative model | The exact variant `SETUP_AND_TOOLCHAIN.md` names explicitly ("Llama 3.2 3B or similarly small local model"). Still comfortably small; Ollama loads one model into memory at a time for a single request, so running either model individually stays well within 8 GB. |
| `embeddinggemma:latest` | 621 MB | small embedding model | Google's EmbeddingGemma, the smallest/only variant Ollama's library offers under this name — 768-dim embeddings, well under any memory concern. |

Total model disk footprint: **3.4 GB** (`du -sh ~/.ollama/models`). All models live under `~/.ollama/models`, entirely outside the KARMO-DEV git repository — no risk of accidentally committing model weights.

**Not copied from KARMO production** — all three were pulled fresh from Ollama's public model library over a normal internet connection, not from any production system.

## Localhost-only verification

- `lsof -nP -iTCP:11434 -sTCP:LISTEN` → `127.0.0.1:11434` only.
- No `OLLAMA_HOST`, firewall, or Tailscale configuration was touched.
- No LAN or remote exposure of any kind was introduced.

## Day-1 smoke test result

Ran `learning-labs/.venv/bin/python learning-labs/day01/check_environment.py`:

```
=== Day 1 environment check ===

Python executable: /Users/sdcity/KARMO-DEV/learning-labs/.venv/bin/python
Python version:    3.12.14
Python >= 3.11:    OK
Running from learning-labs/.venv: OK

pytest: OK (version 9.1.1)
pydantic: OK (version 2.13.5)
httpx: OK (version 0.28.1)
jupyterlab: OK (version 4.6.3)

Ollama reachable at http://127.0.0.1:11434: OK (version 0.33.3)
Local models available: ['embeddinggemma:latest', 'llama3.2:3b', 'qwen2.5:1.5b']

Environment check: READY
```

Additionally verified directly (outside the lesson exercise, setup-only):
- `qwen2.5:1.5b` answered a harmless test prompt ("Reply with exactly one word: hello" → `"Hello!"`).
- `llama3.2:3b` answered the same harmless test prompt (→ `"Hello"`).
- `embeddinggemma` returned a real 768-dimension embedding vector for a harmless test string.

**The Day 1 tool-router exercise itself (Parts 2-7 of the lesson) was explicitly NOT completed on Natalie's behalf.** `model_client.py` and `tool_validator.py` contain only starter stubs with `TODO`s and `NotImplementedError` — Natalie writes the actual model-calling and validation logic during the lesson.

## Deferred to later lessons

Per `SETUP_AND_TOOLCHAIN.md`'s own deferral guidance, not installed tonight (queued for when their lesson arrives): PyTorch, Hugging Face Transformers, tokenizers, sentence-transformers, datasets, accelerate, PEFT, safetensors, MLX/MLX-LM, Qdrant client, `psycopg`, MCP Python SDK, disposable lab Docker containers.

## Git hygiene review (see `.gitignore` — no changes made)

The existing root `.gitignore` already covers everything created tonight:
- `.venv/` (no leading slash — matches `learning-labs/.venv/` at any depth) — confirmed via `git check-ignore -v`.
- `.env`, `.env.*`, `*.pem`, `*.key`, `secrets/` — no such files created.
- `models/`, `data/`, `backups/`, `logs/`, `documents/` — not applicable; Ollama's own models live entirely outside the repo under `~/.ollama/models`.
- `__pycache__/`, `*.py[cod]` — will catch any bytecode the starter scripts generate.

**Two small gaps exist but were deliberately left for Natalie to approve, not fixed automatically** (neither is a secret/model/venv risk, so neither met the "obviously necessary" bar for an unprompted `.gitignore` edit):
1. `.ipynb_checkpoints/` — not covered. Will matter once JupyterLab notebooks are actually created (Day 1 doesn't require one, but it's used in the toolchain).
2. Local database files (`*.db`, `*.sqlite3`) — not covered. `*.dump`/`*.sql.gz` only catch Postgres-shaped dumps, not SQLite files a future lab might create.

Proposed addition (not applied — awaiting approval):
```gitignore
# Learning lab additions
.ipynb_checkpoints/
*.db
*.sqlite3
```

## Production access: 0

No SSH to any host. No connection to `karmo-ai01`. No production PostgreSQL, Qdrant, Ollama, documents, backups, secrets, or models were accessed, copied, or referenced. No production networking, Tailscale, firewall, Docker services, or configuration were touched. `docs/project-state/` was not modified. No KARMO production code was modified.
