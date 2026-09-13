# KARMO Activation Checkpoint — 2026-09-13

## Status
Activation gate: PASS

Deployed merge commit: `074f20a0d05ce296f4eb7d78c35f7f22adb58de4`

Production host: `karmo-ai01`

Launcher: `/usr/local/bin/karmo`

Rollback copy: `/opt/karmo/backups/activation-20260913T004905Z/core-service-before`

## Verified live state
- `karmo-core.service`: active
- `karmo-worker.service`: active
- Core health: healthy
- KarmoLab mode: `READ_ONLY`
- Primary activation model: `qwen3:8b`
- Independent activation verifier: `llama3.2:3b`
- Live status verification: `PASS`
- Interactive `karmo` chat: PASS
- Write-intent refusal: PASS
- PostgreSQL remains loopback-only on `127.0.0.1:5433`
- Qdrant remains loopback-only on `127.0.0.1:6333-6334`
- Ollama remains loopback-only on `127.0.0.1:11434`
- No new KARMO application listener was introduced

## Resource note
KARMO-AI01 has approximately 8 GB RAM. Loading both local activation models materially saturates available memory. This is accepted for the bounded activation checkpoint only and is the reason the next infrastructure phase is the two approved HP worker nodes.

## Approved next sequence
1. Add the two HP worker nodes after read-only identification and enrollment checks.
2. Activate the approved worker-model target: Qwen + DeepSeek + Gemini + Mistral.
3. Build Commander capabilities in bulk through the existing Core registry/approval/dispatcher boundary.
4. Complete durable memory and operational state.

The activation pair Qwen3:8B + Llama3.2:3B is a temporary bounded local arrangement. Llama is not part of the approved long-term four-model worker target.
