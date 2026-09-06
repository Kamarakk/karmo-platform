# KARMO Handoff — 2026-09-04

## Verified current checkpoint

KARMO v0.5 remains frozen and production remains unchanged. H0.0 is complete and verified. H0.1 Transactional Outbox has completed its isolated implementation build and has **not** been cut over to production.

## Authoritative Knowledge Base

- `Karmo Knowledge Base/01_KARMO_HOME_LAB/CURRENT_STATE.md` — version 16
- `Karmo Knowledge Base/01_KARMO_HOME_LAB/MASTER_BUILD_LOG.md` — version 20
- `Karmo Knowledge Base/01_KARMO_HOME_LAB/KARMO_FOUNDATION_HARDENING_PLAN.md` — version 8

## Server and access

- Hostname: `karmo-ai01`
- LAN address: `192.168.1.235`
- User: `lofason`
- Tailscale is not installed on KARMO at this checkpoint. Do not use the Wazuh Tailscale address for KARMO.

## Protected baseline

- H0.0 baseline: `/home/lofason/karmo-ai/hardening/h0.0/baseline-20260903T015340Z`
- H0.0 final harness manifest: `workspace/h00-retrieval-harness/MANIFEST-H0-FINAL.sha256`
- Protected v0.5 reference: `workspace/app-v05-reference`
- Production PostgreSQL baseline: `conversation_memory=14`, `karmo_memory=1`, no `public.karmo_outbox`.
- Production Qdrant baseline: `karmo_semantic_memory=4`, `karmo_documents=8`, `karmo_h00_dense_baseline=8`.

## H0.1 evidence and rollback

- Preparation recovery: `/home/lofason/karmo-ai/hardening/h0.1/implementation-prep-20260903T044818Z`
- Preparation recovery manifest: `MANIFEST-H01-IMPLEMENTATION-PREP-RECOVERY.sha256`
- Source-only rollback app archive: `rollback/karmo-core-app-pre-h01-source-only.tar.gz`
- PostgreSQL rollback archive: `rollback/karmo-postgres-pre-h01.dump`
- Isolated writable app: `/home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z/app`

## H0.1 isolated build — verified PASS

Build evidence:

- Directory: `/home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z/h01-build-v1`
- Manifest: `MANIFEST-H01-ISOLATED-BUILD.sha256` — PASS
- Isolated artifacts: `migrations/001_h01_karmo_outbox.sql`, `transactional_memory.py`, `outbox.py`, and H0.1 static/pure contract tests.
- Static contract: PASS.
- Pure UUID5/retry contract: PASS.
- Reported production database writes, schema changes, Qdrant writes, live-app changes, container restarts, and service installations: all `0`.

The isolated runtime uses `remember_exchange(prompt, answer)` rather than independent `remember_turn()` and `remember_semantic()` calls. The H0.1 design remains user-prompt-only semantic promotion, deterministic UUID5 event/point identity, claim-token fencing, and Qdrant `wait=True`.

## Current stop point

Next phase is the isolated H01-T01 through H01-T18 failure matrix using a separate PostgreSQL test schema and a separate Qdrant test collection. Production migration, live-code copy, worker service installation, container restart, and cutover remain unauthorized.

An attempted failure-harness preflight did not complete because command transport/paste methods failed. Treat any `h01-failure-harness-v1` directory or `h01_failure_harness_preflight*.sh` file as unverified partial isolated artifacts: inspect or remove only after an explicit targeted recovery command. No production mutation was reported by those attempts.

## Operating rule for the next AI

Use the existing frozen design and test matrix. Keep commands native to the KARMO SSH terminal, in small batches when needed. Before any database/Qdrant integration test, reverify the H0.1 isolated build manifest and the 14/1 + 4/8/8 production baseline. Do not modify `public` tables or production collections until all H01-T01 through H01-T18 acceptance tests have passed and a separate cutover approval is granted.
