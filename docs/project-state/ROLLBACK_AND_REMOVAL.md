# KARMO Rollback and Removal

See MASTER_INDEX.md for status-tag definitions. This file preserves
rollback/backup information already recorded in existing evidence/handoff
docs and adds what this session's reconciliation confirmed. It does not
invent new rollback procedures beyond what those sources already describe.

## H0.0 baseline (VERIFIED, preserved from H0.1 handoff doc)

- Baseline archive: `/home/lofason/karmo-ai/hardening/h0.0/baseline-20260903T015340Z`
- Final harness manifest: `workspace/h00-retrieval-harness/MANIFEST-H0-FINAL.sha256`
- Protected v0.5 reference: `workspace/app-v05-reference`
- Baseline data counts to reverify against: PostgreSQL
  `conversation_memory=14`, `karmo_memory=1`, no `public.karmo_outbox`;
  Qdrant `karmo_semantic_memory=4`, `karmo_documents=8`,
  `karmo_h00_dense_baseline=8`.

## H0.1 (VERIFIED, preserved from H0.1 handoff doc + this session)

- Preparation recovery: `/home/lofason/karmo-ai/hardening/h0.1/implementation-prep-20260903T044818Z`
- Preparation recovery manifest: `MANIFEST-H01-IMPLEMENTATION-PREP-RECOVERY.sha256`
- Source-only rollback app archive: `rollback/karmo-core-app-pre-h01-source-only.tar.gz`
- PostgreSQL rollback archive: `rollback/karmo-postgres-pre-h01.dump`
- Isolated writable app (pre-cutover): `/home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z/app`
- **Removal of `karmo-h01-relay` (if ever required):**
  `systemctl --user disable --now karmo-h01-relay` for user `lofason`, then
  reverse `loginctl enable-linger lofason` (`loginctl disable-linger lofason`)
  only if no other user service depends on linger. Rolling back the
  `karmo_outbox` migration/table itself is a separate, more disruptive
  action not covered by evidence in this repo — treat as **NEEDS
  VERIFICATION** / requires its own explicit plan before attempting.
- Outstanding: H01-T01/H01-T18 production-baseline/manifest reverification
  was accepted as a residual risk by Kamara (2026-09-06), not performed,
  not waived as a future requirement (see NEXT_STEPS.md).

## H0.2 (VERIFIED, operator-attested)

- Production `document_ingest.py` and `document_memory.py` were backed up
  before the H0.2 install. Exact backup path: **NEEDS VERIFICATION** (not
  stated in the reconciliation input for this session — only that a backup
  was made).
- Rollback approach if needed: restore the pre-H0.2 backups of those two
  files; H0.2's design never deleted or rewrote legacy vectors, so no data
  rollback should be required on the Qdrant side for a code-only revert.

## H0.3 (VERIFIED — NOT deployed, so no production rollback applies)

- No production rollback needed: H0.3 was evaluated and explicitly approved
  as NO-PROMOTION; it was never installed to production.
- Local removal (if ever desired): delete the untracked `h03/` working
  directory and `docs/evidence/h03/` — see CURRENT_STATE.md gap note that
  these are not currently committed to git, so "removal" here means deleting
  local files, not reverting a commit.

## H0.4 (VERIFIED, operator-attested)

- **Cutover backup:** `/home/lofason/karmo-ai/hardening/h0.4/cutover-20260907T063744Z/`
  - `core-app-pre-h04.tar.gz` — core app archive, pre-H0.4.
  - `karmo-postgres-pre-h04.dump` — PostgreSQL dump, pre-H0.4.
- **Qdrant snapshot** of `karmo_documents` created before H0.4 changes
  (snapshot identifier/location: **NEEDS VERIFICATION** — not stated beyond
  "a snapshot was created").
- **Rollback approach:**
  1. Stop/rollback any H0.4 production module that needs reverting.
  2. Restore `core-app-pre-h04.tar.gz` for application code.
  3. Restore `karmo-postgres-pre-h04.dump` for PostgreSQL state (this would
     also remove `public.document_registry` and its rows, including the 3
     legacy-bootstrapped rows — a one-way loss of the bootstrap work unless
     re-applied afterward).
  4. Restore the pre-H0.4 Qdrant snapshot if Qdrant-side changes must also
     be reverted.
  5. Per I-06 (Migration & Rollback Compatibility), confirm whether any
     H0.4-registered document was ingested *after* cutover and would not
     exist in the pre-H0.4 backup — such documents would need separate
     handling, not a blind restore.
- `h04/app/recovery.py` provides the isolated-tested mechanism (Qdrant
  snapshot create/list/recover; `pg_dump`/`psql`-based backup/restore) that
  the production backup above is modeled on, per
  `docs/evidence/h04/H04_INTEGRITY_RECONCILIATION_REPORT.md`.

## Legacy registry bootstrap (VERIFIED — additive only, low rollback risk)

- The bootstrap only ever inserts new `document_registry` rows for
  previously-unregistered legacy documents; it never updates or deletes
  existing rows. Rollback of the 3 registered rows, if ever needed:
  `DELETE FROM public.document_registry WHERE document_hash IN (...)` for
  the 3 hashes listed in CURRENT_STATE.md — **NEEDS VERIFICATION**/explicit
  approval before running, since this file is documentation-only and does
  not authorize that action.
- The 2 refused (`karmo-v05-new.html`) records require no rollback — nothing
  was written for them.

## Spec Kit (VERIFIED, this session — nothing installed yet)

- No installation has occurred; there is nothing to roll back.
- If/when initialized: rollback is `git branch -D <adoption-branch>` before
  merge, or a revert of the single additive init commit after merge (see the
  Spec Kit inspection report from this session for the full plan). `uv tool
  uninstall specify-cli` removes the local CLI only, not repo files.
