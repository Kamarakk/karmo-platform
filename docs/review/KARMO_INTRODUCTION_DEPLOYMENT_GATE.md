# KARMO Introduction Deployment Gate

Deploy only after the exact candidate SHA is reviewed and merged.

## WHAT
Activate a local KARMO conversational entry point and one bounded KarmoLab READ capability.

## WHY
Allow Kamara to begin using KARMO directly for conversation and read-only KarmoLab inspection while keeping infrastructure mutation disabled.

## CHANGE
- update `/opt/karmo/core-service` to the approved merged commit
- install `/usr/local/bin/karmo` from `core-service/deploy/karmo-launcher.sh`
- verify `qwen3:8b` and `qwen3:4b` exist locally in Ollama
- verify `python3 -m core_service health`
- verify `python3 -m core_service status`
- verify interactive `karmo` chat starts and exits cleanly

## EXPLICITLY NOT CHANGED
- no PostgreSQL migration
- no Qdrant mutation
- no Worker network listener
- no new daemon/service
- no firewall/Tailscale/SSH change
- no secret rotation
- no arbitrary shell capability
- no write/destructive/financial capability

## RISK
Primary risks are operator CLI regression, missing local Ollama model, or insufficient service/docker read permissions. All must fail closed without granting write authority.

## VERIFY
1. exact merged SHA checked out on AI01
2. `python3 -m core_service health` returns healthy
3. `python3 -m core_service status` returns READ_ONLY evidence
4. primary model is `qwen3:8b`
5. verifier model is `qwen3:4b`
6. write request such as `restart the worker service` is refused
7. existing `karmo-core.service` remains active
8. existing `karmo-worker.service` remains active
9. no new listening socket is introduced by the operator package

## ROLLBACK
- restore `/opt/karmo/core-service` to the immediately previous deployed commit
- remove `/usr/local/bin/karmo` launcher if newly installed
- restart only `karmo-core.service` if required to restore the previous code
- re-run previous health checks

Stop and roll back on any BLOCKER/HIGH security finding, failing required test, unexpected write/migration, service failure, or new network listener.
