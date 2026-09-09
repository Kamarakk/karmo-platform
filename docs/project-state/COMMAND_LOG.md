# KARMO Command Log

Commands materially necessary to reproduce or undo H0.1–H0.4. Isolated
commands are reproducible directly from this repo (**VERIFIED** by evidence
reports). Production commands are recorded by description/path per operator
attestation, with no secret values, per SECURITY.md and `AGENTS.md`
("do not request secrets"). See MASTER_INDEX.md for status-tag definitions.

## H0.1 — isolated reproduction (VERIFIED, repo-evidenced)

```
cd test/h01
./scripts/teardown_test_env.sh   # if an older stack is running
./scripts/setup_test_env.sh      # postgres:17-alpine + karmo_h01_outbox_test
venv/bin/python -m pytest -v     # H01-T01..T18 (T01/T18 SKIPPED — blocked, not failed)
./scripts/teardown_test_env.sh   # removes only karmo-h01-test-* resources
```

## H0.1 — production cutover (VERIFIED, operator-attested; exact command
text/flags not transcribed here — no secret values were requested)

- Applied `karmo_outbox` migration to production PostgreSQL.
- Created and enabled `karmo-h01-relay` as a systemd **user** service for
  `lofason` (`systemctl --user enable --now karmo-h01-relay`, or equivalent —
  exact unit file path **NEEDS VERIFICATION**).
- `loginctl enable-linger lofason`.
- Ran a production functional test that produced one delivered outbox event.

## H0.2 — isolated reproduction (VERIFIED, repo-evidenced)

```
cd test/h02
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
```

## H0.2 — production install (VERIFIED, operator-attested; exact transfer
commands not transcribed — no secret values)

- Backed up production `document_ingest.py` and `document_memory.py` before
  replacement.
- Installed the H0.2 lifecycle-aware implementation.
- Confirmed `karmo_documents` remained green at 8 points post-install.

## H0.3 — isolated benchmark (VERIFIED, but see CURRENT_STATE.md gap note:
this code is currently untracked)

```
cd h03
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m pytest -v   # runs the hybrid-vs-dense benchmark suite
```

## H0.4 — isolated reproduction (VERIFIED, repo-evidenced)

```
cd h04
./scripts/setup_test_env.sh
venv/bin/python -m pytest -v
./scripts/teardown_test_env.sh
```

Pagination-fix targeted test only (post-approval, not the full suite):

```
cd h04
./scripts/setup_test_env.sh
venv/bin/python -m pytest -v tests/test_h04_pagination.py
./scripts/teardown_test_env.sh
```

## H0.4 — production cutover (VERIFIED, operator-attested; exact command
text not transcribed where it would include host paths beyond what is
already recorded, or credentials)

- Created cutover backup directory:
  `/home/lofason/karmo-ai/hardening/h0.4/cutover-20260907T063744Z/`
  containing `core-app-pre-h04.tar.gz` (tar of the core app pre-H0.4) and
  `karmo-postgres-pre-h04.dump` (`pg_dump`-style backup, pre-H0.4).
- Created a Qdrant snapshot of `karmo_documents` before H0.4 changes.
- Applied `h04/app/migrations/001_h04_document_registry.sql` to production
  PostgreSQL.
- Transferred H0.4 production modules, verified SHA-256, installed, ran
  `py_compile` validation on each.
- Verified `public.document_registry` exists in production.

## Legacy registry bootstrap — production run (VERIFIED, operator-attested)

Dry run (report-only, no writes — this is the script's default mode):

```
python3 h04/app/bootstrap_legacy_registry.py \
  --qdrant-url <production-qdrant-url> \
  --collection karmo_documents \
  --processed-dir <production-processed-dir>
```
Result: `READY_TO_REGISTER: 3`, `REFUSED: 2` (both `karmo-v05-new.html`,
`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`).

Apply run (writes only the verified-unambiguous groups):

```
python3 h04/app/bootstrap_legacy_registry.py \
  --qdrant-url <production-qdrant-url> \
  --collection karmo_documents \
  --processed-dir <production-processed-dir> \
  --apply
```
Result: `REGISTERED_COUNT: 3`, `REGISTER_FAILED_COUNT: 0`. The 2 refused
records were never re-run with a guessed ordering and remain unresolved — do
not construct or run a command that forces their registration without an
explicit human decision recorded in CURRENT_STATE.md first.

## Spec Kit — inspection only (VERIFIED, this session; no command executed
against this repository)

Commands identified but **not run** (initialization requires Natalie's
approval):

```
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.4
specify init --here --force --integration claude
```
