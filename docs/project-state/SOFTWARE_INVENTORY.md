# KARMO Software Inventory

See MASTER_INDEX.md for status-tag definitions. Credential *locations* only
are noted where known; no secret values appear in this file, per SECURITY.md.

## Production services (host: karmo-ai01, user: lofason)

| Component | Status | Detail |
|---|---|---|
| `karmo-h01-relay` | **VERIFIED** | systemd **user** service, created and enabled for `lofason` during H0.1 cutover. Delivers transactional outbox events (`public.karmo_outbox` → Qdrant `karmo_semantic_memory`). One production functional test produced a delivered event. |
| Persistent user-service startup | **VERIFIED** | `loginctl enable-linger lofason` set, so `karmo-h01-relay` starts without an active login session. Reboot persistence: **NEEDS VERIFICATION** (not re-checked this session). |
| H0.2 document ingest/memory (production) | **VERIFIED** | Production `document_ingest.py`/`document_memory.py` backed up, then replaced with the H0.2 lifecycle-aware implementation (is_active/versioning/provenance fields). Reference copy: `docs/handoff/h02/*.production-reference.py` (committed). |
| H0.4 document ingest/registry/auditor/reconciliation (production) | **VERIFIED** | Production modules transferred, SHA-256 verified, installed, `py_compile`-validated. Source: `h04/app/{document_ingest_h04.py, registry_db.py, auditor.py, reconciliation.py, archive_integrity.py, recovery.py, bootstrap_legacy_registry.py, run_auditor.py}` (committed). |
| `public.document_registry` (PostgreSQL, production) | **VERIFIED** | Migration `h04/app/migrations/001_h04_document_registry.sql` applied to production; table existence verified. Note: the migration file's own header comment ("Isolated build artifact only. Not applied to any production database.") is now stale — flagged in CURRENT_STATE.md, not edited in this documentation-only pass. |
| H0.3 hybrid retrieval (dense + BM25 + RRF) | **VERIFIED not in production** | Evaluated and explicitly approved as NO-PROMOTION. Not installed, not running against production data. |

## Data stores (production)

| Store | Status | Detail |
|---|---|---|
| PostgreSQL — `conversation_memory`, `karmo_memory` | **HISTORICAL baseline** | Pre-H0.1: 14 / 1 rows respectively (H0.1 handoff doc). Current counts: **NEEDS VERIFICATION**. |
| PostgreSQL — `public.karmo_outbox` | **VERIFIED** | Created by the H0.1 migration; did not exist pre-H0.1. |
| PostgreSQL — `public.document_registry` | **VERIFIED** | Created by the H0.4 migration; contains 3 bootstrapped legacy rows plus any rows written by H0.2/H0.4 ingest since cutover (exact current count: **NEEDS VERIFICATION**). |
| Qdrant — `karmo_semantic_memory` | **HISTORICAL baseline** | Pre-H0.1: 4 points (H0.1 handoff doc). Current count: **NEEDS VERIFICATION**. |
| Qdrant — `karmo_documents` | **VERIFIED at 8 points during H0.2 validation** | Matches pre-H0.1 baseline of 8 (H0.1 handoff doc). Current count after H0.4 cutover + legacy bootstrap: **NEEDS VERIFICATION**. |
| Qdrant — `karmo_h00_dense_baseline` | **HISTORICAL baseline** | Pre-H0.1: 8 points (H0.1 handoff doc). Frozen H0.0 reference; not expected to change. |

## Isolated/test-only software (this repository, not production)

- `h02/`, `h03/`, `h04/` — isolated app code + `venv/` (per-directory Python
  virtualenvs; **NEEDS VERIFICATION** whether these venvs should be
  `.gitignore`d — currently tracked/untracked status not audited in this
  pass, see NEXT_STEPS.md).
- `test/h01/`, `test/h02/` — isolated acceptance test harnesses, Docker
  Compose stacks (`postgres:17-alpine`, `qdrant/qdrant:v1.9.7` for H0.1/H0.4;
  in-memory `qdrant-client` for H0.2/H0.3). Container name prefixes
  `karmo-h0N-test-*` only; never a production container name.
- `h04/docker-compose.yml` — isolated PostgreSQL (port `57432`) + Qdrant
  (ports `58333`/`58334`) for H0.4 acceptance testing only.

## Credential locations (location only, no values)

- H0.1/H0.4 isolated test credentials: hardcoded synthetic values scoped to
  Docker Compose test stacks (`karmo_h01_test`/`karmo_h04_test` family) —
  not usable against production, not secrets.
- Production `KARMO_DB_PASSWORD`: per `docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`
  (I-02), must be supplied via a persistent mechanism (systemd
  `EnvironmentFile` or equivalent), never an interactively-exported shell
  variable. Exact current source/file path for this credential: **NEEDS
  VERIFICATION** — not confirmed in this session (no production access).

## Development toolchain (this session, local machine only)

- `git 2.55.0`.
- `uv`/`uvx`/`pipx`: **not installed** on this development machine as of
  this reconciliation — required before Spec Kit's CLI (`specify`) can be
  installed. Not a KARMO production dependency.
