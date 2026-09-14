# PROJECT SAVE — Local Open Model Stack Activation

Date: 2026-09-13
Status: **VERIFIED**
Scope: Production KARMO model-stack activation on `karmo-ai01` following the dual-worker checkpoint.

## Decision

The previously planned Qwen + DeepSeek + Gemini + Mistral composition was revised before final activation. DeepSeek was removed from the active target because its reasoning path did not fit KARMO's current bounded Ollama generation behavior cleanly, and Gemini was dropped because the operator does not want provider credentials or external API dependence for this stack.

The approved production model roles are now:

- `qwen3:8b` — primary local chat/summarization/reasoning model.
- `ministral-3:8b` — independent secondary local chat/summarization/reasoning model.
- `mistral:7b` — independent verifier.
- `granite3.3:2b` — fast local fallback.

All active model resources use the existing loopback-only Ollama provider; no cloud model, provider credential, paid API, or new application listener was introduced.

## Repository implementation

PR #45, `feat: activate local open model stack`, merged into `main` at:

`37cfc110b32fde9898b7d90aa1855b1f608ab18f`

The merge adds deterministic ranked routing and fail-closed chat fallback:

`qwen3:8b -> ministral-3:8b -> granite3.3:2b`

The independent verifier is `mistral:7b`.

CI gates passed before deployment:

- Core Productionization #117 — SUCCESS.
- KARMO Full Predeploy #210 — SUCCESS.

## Production activation

A staged continuous deployment was prepared on `karmo-ai01` with source-drift checks, SHA-256 validation, syntax/import validation, one controlled `karmo-core.service` restart, post-restart routing/model checks, listener regression checks, and automatic source rollback on failure.

Deployment completed with all required markers:

- `SOURCE_DEPLOY_PASS`
- `CORE_RESTART_PASS`
- `ROUTING_IMPORT_PASS`
- `qwen3:8b MODEL_SMOKE_PASS`
- `ministral-3:8b MODEL_SMOKE_PASS`
- `mistral:7b MODEL_SMOKE_PASS`
- `granite3.3:2b MODEL_SMOKE_PASS`
- `MODEL_STACK_CONTINUOUS_DEPLOY_PASS`

Independent post-deployment recheck confirmed:

- `karmo-core.service` is active.
- active chat order is exactly `qwen3:8b`, `ministral-3:8b`, `granite3.3:2b`.
- active verifier is exactly `mistral:7b`.
- Ollama remains loopback-only on `127.0.0.1:11434`.
- no new KARMO application listener appeared.
- deployed source hashes match the staged validated build.

Production source hashes after activation:

- `/opt/karmo/core-service/core_service/operator.py` — `cf0164b1bdd133b694c19e054740f7003ce7d2bfec30d1f599697f8df34de44c`
- `/opt/karmo/core-service/core_service/model_router.py` — `54d5fa403449d7f1327397b60f50038d4b8a73e25dbf7d5cb965efab2cd153cb`

## Model inventory / cleanup state

The required active models are installed and validated. The temporary DeepSeek evaluation models `deepseek-r1:7b` and `deepseek-r1:8b` were removed from AI01 before final activation.

`llama3.2:3b` and `qwen3:4b` remain physically installed but are not part of active routing. They were intentionally not deleted during this checkpoint because removing inactive models is a separate cleanup decision.

## Rollback / deployment artifacts

Pre-deployment backup and staging were preserved under:

`/home/lofason/karmo-deploys/model-stack-20260914T042749Z`

An earlier rollback backup also exists at:

`/home/lofason/karmo-backups/model-stack-20260914T034937Z`

Continuous deployment script:

`/home/lofason/karmo-deploys/deploy-model-stack.sh`

## Gate result

**PASS.** The local open model stack is production-active on `karmo-ai01` with existing KARMO authority boundaries unchanged.

The dual-worker activation checkpoint remains intact. The next approved sequence item is bulk Commander capability work, followed by durable memory/operations. Any future authoritative project-record change still requires explicit operator approval under the existing KARMO document-governance rule.
