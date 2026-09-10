# KARMO AI Learning Environment Setup

## Goal
Prepare KARMO-DEV01 for safe, isolated AI/agent engineering labs without touching KARMO production.

## Existing tools already verified on KARMO-DEV01
- Apple Command Line Tools
- Homebrew 6.0.21
- Apple Git 2.39.5
- Claude Code 2.1.236
- GitHub CLI authenticated as `Kamarakk`
- Local KARMO repository at `~/KARMO-DEV`

## Learning toolchain to verify/install locally

### Core Python
- Python 3.11+
- `venv`
- `pip`
- JupyterLab
- pytest
- Pydantic
- httpx

### Local AI/model tooling
- Ollama
- Qwen family model appropriate for 8 GB M3
- Llama 3.2 3B or similarly small local model
- EmbeddingGemma

### Model experimentation
- PyTorch
- Hugging Face Transformers
- tokenizers
- sentence-transformers
- datasets
- accelerate
- PEFT
- safetensors

### Apple Silicon / representation experiments
- MLX and MLX-LM when compatible with the lesson and M3 memory limits

### Retrieval / data
- Qdrant client
- PostgreSQL client library (`psycopg`)
- optional local Docker containers for disposable lab databases only

### Agent / tool integration
- MCP Python SDK
- JSON Schema/Pydantic validation
- local tool-calling examples

### Engineering and security
- Git/GitHub
- Claude Code
- ChatGPT
- Docker Desktop or another approved local Docker runtime when needed
- shell/zsh
- logging/profiling/debugging tools

## Isolation rules
1. Learning environment lives on KARMO-DEV01.
2. Use a dedicated virtual environment under the learning workspace.
3. Do not reuse production databases, Qdrant collections, secrets, backups, private documents, or model data.
4. Do not connect learning code to `karmo-ai01` unless a separate production-access approval is granted.
5. Use synthetic or explicitly approved sample data.
6. Any Docker services used for learning are local/disposable and clearly named as lab services.
7. Secrets belong in local environment variables or approved secret stores and are never committed.

## Recommended local layout

```text
~/KARMO-DEV/
  docs/learning/
  learning-labs/
    .venv/
    day01/
    day02/
    ...
    shared/
```

## Setup acceptance criteria
The environment is ready for Day 1 when:
- Python 3.11+ works.
- A dedicated `learning-labs/.venv` exists.
- `pytest`, `pydantic`, `httpx`, and Jupyter import successfully.
- Ollama responds locally.
- At least one small Qwen model and one small Llama model are available locally, or are explicitly queued for later model-comparison labs.
- A small embedding model is available locally.
- No connection to KARMO production was required.

## Deferred until the relevant lesson
Do not install the entire advanced stack on Day 1 if it is not needed. Add heavier packages such as PyTorch, Transformers, PEFT, sentence-transformers, MLX, and MCP when their first lab arrives. This keeps the environment understandable and reduces dependency churn.
