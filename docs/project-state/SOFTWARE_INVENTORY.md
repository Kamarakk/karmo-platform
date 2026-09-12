# KARMO Software Inventory

See MASTER_INDEX.md for status-tag definitions. Credential *locations* only are noted where known; no secret values appear in this file, per SECURITY.md.

## Production services (host: karmo-ai01, user: lofason)

| Component | Status | Detail |
|---|---|---|
| `tailscaled` | **VERIFIED active** | Official Tailscale client installed/enrolled 2026-09-11. KARMO-AI01 tailnet IP `100.75.239.44`; DNS acceptance disabled; Tailscale SSH/subnet-routing/exit-node features not enabled. Verified active after the controlled reboot into kernel `6.8.0-139-generic`. |
| `karmo-core.service` | **VERIFIED active + enabled** | Production KARMO Control & Approval Layer installed at `/opt/karmo/core-service`; local-only, no network listener. Verified active after the controlled reboot. |
| `karmo-worker.service` | **VERIFIED active + enabled** | Production-local Trusted Computer Worker service installed at `/opt/karmo/worker-service`; requires Core, no network listener, no real worker network transport, no capability execution, no persistent writes. Verified active after the controlled reboot. |
| `karmo-h01-relay` | **VERIFIED active after reboot** | systemd **user** service for `lofason` delivering transactional outbox events (`public.karmo_outbox` → Qdrant `karmo_semantic_memory`). After the controlled reboot, `loginctl show-user lofason` reported `Linger=yes` and the relay process was present as `/home/lofason/karmo-ai/core/venv/bin/python outbox.py --loop --worker-id karmo-h01-relay`. |
| Persistent user-service startup | **VERIFIED after reboot** | `loginctl enable-linger lofason` is effective; the `karmo-h01-relay` process was present after the 2026-09-11 controlled reboot without requiring an interactive user session to launch it. |
| H0.2 document ingest/memory (production) | **VERIFIED** | Production lifecycle-aware document ingest/memory implementation installed. |
| H0.4 document ingest/registry/auditor/reconciliation (production) | **VERIFIED** | Production H0.4 modules and `public.document_registry` migration installed. |
| H0.3 hybrid retrieval (dense + BM25 + RRF) | **VERIFIED not in production** | Evaluated and explicitly approved as NO-PROMOTION. |

## Host maintenance state

- KARMO-AI01 completed the approved controlled reboot on 2026-09-11.
- Running kernel is now **`6.8.0-139-generic`**.
- Post-reboot verification confirmed `tailscaled`, `karmo-core.service`, `karmo-worker.service`, and `docker.service` are active.
- Tailscale retained IP `100.75.239.44` after reboot.
- Existing `karmo-h01-relay` persistence was verified by `Linger=yes` plus the live relay process after reboot.

## Data stores (production)

| Store | Status | Detail |
|---|---|---|
| PostgreSQL — `conversation_memory`, `karmo_memory` | **HISTORICAL baseline** | Pre-H0.1 counts 14 / 1; current counts **NEEDS VERIFICATION**. |
| PostgreSQL — `public.karmo_outbox` | **VERIFIED** | Created by H0.1 migration. |
| PostgreSQL — `public.document_registry` | **VERIFIED** | Created by H0.4 migration; exact current row count **NEEDS VERIFICATION**. |
| Qdrant — `karmo_semantic_memory` | **HISTORICAL baseline** | Pre-H0.1 count 4; current count **NEEDS VERIFICATION**. |
| Qdrant — `karmo_documents` | **VERIFIED at 8 points during H0.2 validation** | Current count after later activity **NEEDS VERIFICATION**. |
| Qdrant — `karmo_h00_dense_baseline` | **HISTORICAL baseline** | Pre-H0.1 count 8; frozen reference. |

## Production service boundaries added 2026-09-11

### KARMO Core
- path: `/opt/karmo/core-service`
- systemd unit: `karmo-core.service`
- Python runtime: `/usr/bin/python3`
- persistence: in-memory
- network listener: none
- DB/Qdrant mutation: none

### KARMO Worker
- path: `/opt/karmo/worker-service`
- systemd unit: `karmo-worker.service`
- depends on: `karmo-core.service`
- network listener: none
- real worker network transport: disabled
- capability execution: disabled
- persistent writes: none

## Isolated/test-only software

- `h02/`, `h03/`, `h04/` — isolated hardening/research code and environments.
- `test/h01/`, `test/h02/` — isolated acceptance harnesses.
- `h04/docker-compose.yml` — isolated PostgreSQL/Qdrant acceptance stack only.

## Credential locations (location only, no values)

- Production OpenSSH operator identity reference: `~/.ssh/karmo_admin_ed25519` on KARMO-DEV01. Never commit or print the private key.
- Tailscale enrollment uses its approved browser/device login flow; no auth key/token is stored in this repository.
- Production `KARMO_DB_PASSWORD` persistent source remains **NEEDS VERIFICATION**; do not expose the value.

## Development toolchain

KARMO-DEV01 remains the dedicated development/learning workstation with Git, GitHub CLI, Claude Code, VS Code, and OpenSSH. See the access registry and bootstrap files for current details.
