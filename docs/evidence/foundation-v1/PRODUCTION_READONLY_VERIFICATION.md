# Foundation v1 — Production Read-Only Verification

All commands below were executed against `karmo-ai01` under Natalie's
temporary, session-scoped, task-specific Production Access Authorization
(chat message, 2026-09-09, "TEMPORARY TONIGHT-ONLY AUTHORIZATION"), per the
shape defined in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s
Mandatory Production Access Authorization Gate (merged this session, PR
#12). Target system: `karmo-ai01`. Purpose: KARMO Foundation v1
closeout/verification (Workload 2 + directly-necessary supporting checks).
Authority: **READ-ONLY only** — no write, restart, deployment, or
configuration action was requested or performed. Session window:
approximately 2026-09-09T06:07Z–06:21Z UTC. No secret value is displayed
below; `POSTGRES_PASSWORD`/`KARMO_DB_PASSWORD` were sourced into the remote
shell's environment and passed directly to `psql`/the app's own connection
code, never echoed or logged.

## Authorization record

```
PRODUCTION ACCESS AUTHORIZATION
Task: KARMO Foundation v1 closeout (Workload 2 + directly-necessary supporting checks)
Target system/environment: karmo-ai01 (PostgreSQL @ 127.0.0.1:5433 via karmo-postgres container, Qdrant @ 127.0.0.1:6333 via karmo-qdrant container, host filesystem under /home/lofason)
Purpose: Determine whether KARMO FOUNDATION v1 can be truthfully declared COMPLETE
Permitted operations: read-only file/manifest inspection, read-only SQL SELECT/\dt, read-only Qdrant HTTP GET, systemd/docker status queries, py_compile syntax check
Authority: READ-ONLY (no write, restart, deploy, config change, or destructive action authorized or performed)
Commands/command class: file find/sha256sum -c; docker exec ... psql -c "SELECT ..."; docker exec ... psql -c "\dt ..."; curl (Qdrant read API); systemctl/loginctl/docker status commands; run_auditor.py (report-only by construction); python -m py_compile
Granted: 2026-09-09, by Natalie (chat message, this session)
Expires: automatically at session end / Foundation v1 closeout completion / 4 hours, whichever first — already exercised and closed out within this same session
```

## H01-T01 — Manifest presence and hash verification

| Field | Value |
|---|---|
| Timestamp (UTC) | 2026-09-09T06:11–06:13Z |
| Purpose | Confirm H0.0 final manifest and H0.1 isolated-build manifest are present on `karmo-ai01` and every file each manifest covers still hashes correctly |
| Command 1 | `find /home/lofason -maxdepth 8 -iname "*MANIFEST-H0-FINAL*"` |
| Command 2 | `cd <h0.0 baseline dir> && sha256sum -c MANIFEST-H0-FINAL.sha256` |
| Command 3 | `find /home/lofason -maxdepth 6 -iname "MANIFEST-H01-ISOLATED-BUILD.sha256"` |
| Command 4 | `cd <h0.1 implementation dir> && sha256sum -c h01-build-v1/MANIFEST-H01-ISOLATED-BUILD.sha256` |
| Expected | Both manifests present; every listed file hashes to its recorded value |
| Observed | H0.0 manifest found at `/home/lofason/karmo-ai/hardening/h0.0/baseline-20260903T015340Z/workspace/h00-retrieval-harness/MANIFEST-H0-FINAL.sha256` — 7/7 files `OK`, exit 0. H0.1 manifest found at `/home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z/h01-build-v1/MANIFEST-H01-ISOLATED-BUILD.sha256` — 34/34 files `OK`, exit 0 (a first attempt from the wrong working directory produced spurious `FAILED open or read` errors — a command-invocation mistake on my part, corrected by running from the manifest's actual base directory; not a production issue, included in `RUN_SUMMARY.json`'s command count for transparency) |
| Result | **PASS** |
| Evidence source | Direct SSH command output, this session |

## H01-T18 — Baseline count reverification

| Field | Value |
|---|---|
| Timestamp (UTC) | 2026-09-09T06:14–06:17Z |
| Purpose | Reverify live PostgreSQL/Qdrant counts against `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`'s recorded pre-H0.1 baseline |
| Commands | `docker exec -e PGPASSWORD=*** karmo-postgres psql -U karmo -d karmo -t -A -c "SELECT count(*) FROM conversation_memory;" -c "SELECT count(*) FROM karmo_memory;" -c "SELECT count(*) FROM public.karmo_outbox;" -c "SELECT count(*) FROM public.document_registry;"`; `psql ... "\dt public.karmo_outbox"`; `curl http://127.0.0.1:6333/collections/<name>` for each of `karmo_semantic_memory`, `karmo_documents`, `karmo_h00_dense_baseline` |

| Metric | Pre-H0.1 baseline (recorded) | Observed 2026-09-09 | Assessment |
|---|---|---|---|
| `conversation_memory` | 14 | 16 | Growth of 2 — consistent with real usage since the 2026-09-04 baseline plus the H0.1 cutover functional test; not a discrepancy |
| `karmo_memory` | 1 | 1 | Exact match |
| `public.karmo_outbox` | did not exist | exists (`\dt` confirms table, owner `karmo`), 1 row | Expected — this table was intentionally created by the H0.1 cutover migration, already recorded as VERIFIED in `CURRENT_STATE.md`; its prior absence was the *pre-cutover* baseline, not a current expectation |
| `karmo_semantic_memory` (Qdrant) | 4 | 5, status `green` | Growth of 1 — matches "production functional test produced one delivered outbox event" already recorded in `CURRENT_STATE.md` for H0.1 cutover |
| `karmo_documents` (Qdrant) | 8 | 8, status `green` | Exact match — consistent with the H0.2 validation note that this collection "remained green at 8 points" |
| `karmo_h00_dense_baseline` (Qdrant) | 8 | 8, status `green` | Exact match — frozen baseline collection, unchanged as expected |
| `public.document_registry` | (did not exist pre-H0.1/H0.2) | 3 rows | Matches exactly the `REGISTERED_COUNT: 3` already recorded from the legacy registry bootstrap apply run — direct corroboration, not a new fact |

| Result | **PASS** — every observed value is either an exact match to the recorded baseline or a fully-explained delta traceable to an already-recorded event. No unexplained or contradictory value found. |
| Evidence source | Direct SSH command output, this session |

## Additional read-only checks (directly necessary to confirm Foundation v1 state)

### H0.1 relay service state

- `systemctl --user status karmo-h01-relay --no-pager`: **active (running)** since 2026-09-06 22:40:28 UTC (continuous, 2 days at check time). Matches the recorded cutover date.
- `loginctl show-user lofason -p Linger`: **Linger=yes** — confirms the persistent-startup setting recorded in `CURRENT_STATE.md` is still in place. This confirms the *setting*, not an actual reboot; reboot-survival itself remains **NEEDS VERIFICATION** exactly as already flagged (unchanged by this check — no reboot was performed or authorized).

### H0.4 report-only integrity audit (`run_auditor.py --collection karmo_documents`)

Run twice (text summary, then `--json` for full detail) — same single read-only audit, report-only by construction (`auditor.py`'s own module docstring; proven report-only by `test_auditor_is_report_only` in the frozen H0.4 suite).

```
REGISTRY_ROWS: 3
TOTAL_FINDINGS: 23
  ACTIVE_STATE_MISMATCH: 3
  LEGACY_PROVENANCE_UNVERIFIED: 18
  ORPHAN_VECTOR: 2
STATUS: INTEGRITY_FINDINGS_PRESENT (5 non-legacy findings)
```

**Full explanation — every finding is accounted for by already-recorded history, none is new/unexplained production risk:**

- `LEGACY_PROVENANCE_UNVERIFIED` (18): the already-understood, explicitly-honest state for pre-H0.2 points bootstrapped with the legacy provenance label — `reconciliation.py`'s own documented, non-integrity-failure category. Expected, not investigated further.
- `ORPHAN_VECTOR` (2): document_hash `23646203ee...` and `5f98126d...` — these are **exactly** the two `karmo-v05-new.html` hashes already recorded in `CURRENT_STATE.md`/`NEXT_STEPS.md` as intentionally, permanently unresolved (`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`) since the legacy bootstrap dry run. Not a new problem — direct confirmation that the already-documented gap and nothing else is present.
- `ACTIVE_STATE_MISMATCH` (3): for `document_id` values `karmo-test.docx`, `karmo-v05-final-20260901T215023Z.html`, `karmo-v05-unique-20260831T214746Z.html` — these are **exactly** the three `document_hash` values the legacy bootstrap *apply* run registered (`REGISTERED_COUNT: 3`, matching hash-for-hash). **Root cause identified, newly surfaced this session:** `reconciliation.check_active_version_state` compares the registry's `is_active=True` against Qdrant points carrying an explicit `is_active: true` payload field — but legacy (pre-H0.2) points never carry an `is_active` field at all (`bootstrap_legacy_registry.py` never writes to Qdrant, by design), so `qdrant_active_hashes` is structurally always empty for a legacy-bootstrapped document. This is the same class of gap `check_provenance` already special-cases (`LEGACY_PROVENANCE_UNVERIFIED`), but `check_active_version_state` has no equivalent legacy-aware carve-out. **This is an auditor-design gap, not a data-integrity problem** — the underlying data is correct and fully explained by already-recorded events (the same 3 hashes the record already names). No repair was attempted (not authorized; auditor is report-only by design regardless). Recorded as a new, non-blocking follow-up recommendation in the closeout report — not a new Foundation-completion criterion, per explicit instruction not to invent criteria after seeing a result.

This audit was **not** part of Workload 2's own defined acceptance criteria (manifest + baseline counts only) — it was an additional read-only check, directly relevant to confirming Foundation v1 state, explicitly permitted by this session's authorization. It does not change Workload 2's PASS result and does not block Foundation v1, for the reasons above.

### `py_compile` sanity on deployed production files

`python -m py_compile` on all deployed H0.1/H0.2/H0.4 production application files (`karmo.py`, `memory.py`, `outbox.py`, `transactional_memory.py`, `router.py`, `semantic_memory.py`, `document_ingest_h04.py`, `document_memory.py`, `registry_db.py`, `auditor.py`, `reconciliation.py`, `archive_integrity.py`, `run_auditor.py`, `bootstrap_legacy_registry.py`): **exit 0, no syntax errors.**

### Container/service status

`docker ps --filter name=karmo`: `karmo-postgres` up 10 days (healthy), `karmo-qdrant` up 10 days, `karmo-ollama` up 11 days — no unexpected restarts, no status change from the start of this session to its end.

## Summary

| Check | Result |
|---|---|
| H01-T01 (manifest presence/hash) | PASS |
| H01-T18 (baseline counts) | PASS |
| H0.1 relay service state | active, Linger=yes (reboot-survival itself still NEEDS VERIFICATION, unchanged) |
| H0.4 production audit (bonus, not a Workload 2 criterion) | INTEGRITY_FINDINGS_PRESENT, fully explained, non-blocking |
| `py_compile` on deployed files | PASS |
| Container/service status | stable, healthy, no unexpected changes |

**No production write, restart, deployment, configuration change, or destructive action was performed at any point.**
