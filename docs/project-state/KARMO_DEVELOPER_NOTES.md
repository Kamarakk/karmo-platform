# KARMO Developer Notes

Append-only engineering journal. Not a replacement for `CURRENT_STATE.md`,
`CHANGE_LOG.md`, evidence files, or governance records — those remain
authoritative. This file exists so a future session can see, in one
place, exactly what happened, in what order, with what evidence, without
reconstructing it from chat.

Status tags used below: `VERIFIED`, `HISTORICAL`, `NEEDS VERIFICATION`.

---

## 2026-09-15 — Durable Memory Core integration: merge, deploy, and 3 real fixes

**Change ID / commits:** PR #48 (`feat/durable-memory-core-integration`,
merge commit `7b50a381b2e19e1b12aecd59182df3fd4215216b`); PR #49
(`fix/durable-memory-deploy-gaps`, merge commit
`6cee676e5516075f2c81b6be2f2480f24c0042c0`).

**Purpose:** wire the existing PostgreSQL `conversation_memory` +
`karmo_outbox` (H0.1) and Qdrant `karmo_semantic_memory` / `karmo_documents`
(H0.2) memory stack into the Core `chat` operator, so conversation
recall/semantic/document retrieval work without adding any new service,
listener, or datastore.

**Machine/environment:** developed on KARMO-DEV01 (this Mac); deployed to
`karmo-ai01` (Ubuntu, `lofason` account) over Tailscale SSH.

### PR #48 — merge and CI (VERIFIED)
- CI green pre-merge: Core Productionization + all 4 KARMO Full Predeploy
  jobs (core-tests, worker-service-tests, worker-tests,
  core-v2-prototype-regression).
- Independent security review performed before merge (this session): no
  HIGH/MEDIUM findings — parameterized SQL throughout, DSN file
  permission-gated before read, embedding dimension validated before use,
  retrieved memory/document text isolated as explicitly untrusted
  reference data in the prompt, context length bounded
  (`MAX_MEMORY_CONTEXT_CHARS`), rollback proven atomic by a real-Postgres
  failure-injection test.
- Merged, then re-verified locally on merged `main`: core-service 79
  passed/33 skipped (Postgres-dependent tests skip locally, no local PG;
  they ran and passed in CI against a real container), worker-runtime 109
  passed, core-v2-prototypes 161 passed, worker-service 2 passed + healthy
  CLI.

### Production deployment attempt 1 (2026-09-15, PARTIAL — 3 real gaps found)
Read-only production audit first (`docs/review/KARMO_DURABLE_MEMORY_DEPLOYMENT_GATE.md`),
confirming: `karmo-core.service` runs as root; `/etc/karmo/core/` did not
exist; `karmo-postgres` DB name/admin user is `karmo`/`karmo`; baseline
listeners were loopback-only (5433/6333/6334/11434) plus SSH/DNS/Tailscale.

Deployed merge commit `7b50a381` via tarball + SHA-256 verification
(matched). Created scoped least-privilege role `karmo_core_memory`
(`SELECT, INSERT` on `conversation_memory`, `INSERT` on `karmo_outbox`
only — deliberately not `karmo_gateway`). Wrote
`/etc/karmo/core/postgres.dsn`.

**Canary run 1** surfaced real defects (not paste artifacts — reproduced
cleanly on a fresh SSH session):

1. **Dispatch hijack (pre-existing code, not part of PR #48's diff):**
   `operator.py`'s `_STATUS_WORDS` regex included the bare word `memory`.
   Because regex `\b` treats hyphens as word boundaries, the canary
   phrase `durable-memory-canary-...` matched, silently routing the
   message to the KarmoLab status tool instead of `_chat()` — the new
   memory feature was never reached at all on the first attempt.
2. **DSN file/directory ownership mismatch:** `/etc/karmo/core` was
   created `root:root` mode `700`. `chat` is a manual, interactive CLI
   run directly by `lofason` (via `/usr/local/bin/karmo` or
   `python3 -m core_service chat`) — it is **not** invoked by
   `karmo-core.service` itself, so `User=` being empty (root) on the
   *service* was the wrong signal to design the DSN file's ownership
   around. Fixed: `chown -R lofason:lofason /etc/karmo/core`.
3. **Missing sequence grant:** `conversation_memory.id` is `BIGSERIAL`;
   granting `INSERT` on the table does not grant `USAGE` on
   `conversation_memory_id_seq`. Write failed `InsufficientPrivilege`
   until `GRANT USAGE, SELECT ON SEQUENCE public.conversation_memory_id_seq
   TO karmo_core_memory` was applied.
4. **Missing runtime dependency on production:** `qdrant_client` was not
   installed for `/usr/bin/python3` (the interpreter `chat` actually
   runs under). PR #48's own System-Fit Review had assumed production
   already had it — true only for an unrelated, separate venv
   (`/home/lofason/karmo-ai/core/`), not for `/opt/karmo/core-service`.
   This was masked on the first fully-read-succeeding attempt because a
   *simultaneous* write failure (#3, before the sequence grant) was
   overwriting the read-failure status in `memory_status` — see fix #2
   below. Root cause: `core-service` had no `requirements.txt` at all.

None of these were caught by the isolated test suite, which mocks the
memory backend and therefore never exercised the real system
interpreter, a real regex match against a realistic phrase, or real file
ownership.

### Fix PR #49 (VERIFIED, merged)
- Added `core-service/requirements.txt` (`psycopg[binary]`,
  `qdrant-client`); predeploy CI now installs from it instead of an
  inline package list.
- Fixed status masking: a write failure no longer silently overwrites a
  prior read failure — both now surface
  (`DEGRADED_READ_FAILED:X+DEGRADED_WRITE_FAILED:Y`) via a new
  `_combine_memory_status` helper.
- Removed `memory` from `_STATUS_WORDS`.
- Updated `core-service/README.md`'s stale v0.1 boundary section (still
  claimed "no Qdrant access, no secrets" after PR #48 changed both).
- 2 new tests: `test_read_and_write_failure_are_both_visible_not_masked`,
  `test_message_mentioning_memory_still_reaches_chat_not_karmolab_status`.
- CI: all 5 checks green (targeted-tests, core-tests, worker-tests,
  worker-service-tests, core-v2-prototype-regression). Local re-run: 81
  passed, 33 skipped.

### Production deployment attempt 2 (2026-09-15, VERIFIED — successful)
Redeployed merge commit `6cee676e5516075f2c81b6be2f2480f24c0042c0` via
tarball + SHA-256 verification (matched:
`e0ebbf8ebdbadb5ff51a263fcb152b15a3d6d111a3b4ad379c0083c01e9644e4`).
Installed `qdrant-client`/`psycopg` for `lofason`'s user site-packages
(`pip install --user --break-system-packages`, required by Ubuntu
24.04's PEP 668 externally-managed-environment guard — a narrowly-scoped,
reversible install, not a system-wide change). Restarted
`karmo-core.service` (`active`).

**Canary run 2 result: PASS, clean.**
- `memory=ACTIVE` on both a write turn and a separate, freshly-started
  `chat` process's read turn (proves persistence survives process
  exit/reopen, not just a single in-process write).
- `conversation_memory`: 2 new rows (`user`/`assistant`) with the exact
  canary phrase.
- `karmo_outbox`: 1 new `semantic_memory.upsert.v1` row, status
  `delivered` (the existing H0.1 relay picked it up during the session —
  faster than the "pending" originally expected).
- Retrieval proof: a second, independent `chat` invocation correctly
  recalled the exact canary phrase from recent-turn memory.
- `ss -H -lntu`: identical to the pre-deploy baseline (5433/6333/6334/11434
  loopback, 22/DNS/Tailscale) — no new listener introduced.
- `karmo-worker.service`: unaffected, `active` throughout.

**Production status: DEPLOYED, VERIFIED.**

**Risk/known limitations:**
- `qdrant-client`/`psycopg` are now installed per-user (`lofason`) via
  pip, not via a project-pinned venv or apt package — acceptable for this
  scale/boundary but worth a dedicated venv if `core-service` gains more
  dependencies.
- Two backup trees now exist under `/opt/karmo/core-service.bak.*`
  (attempt 1 and attempt 2) — not cleaned up; harmless, but note for
  later housekeeping.
- Document retrieval (`karmo_documents`) was exercised by the code path
  but not independently re-canaried with a real document match in this
  session (production `document_registry` count is 3 per prior evidence;
  no document-specific canary was run) — the read path succeeded
  end-to-end regardless, and this is the same reused H0.2 filter contract
  already covered by unit tests.

**Rollback (not needed, recorded for completeness):**
`sudo systemctl stop karmo-core.service && sudo rm -rf /opt/karmo/core-service
&& sudo mv /opt/karmo/core-service.bak.<latest-timestamp> /opt/karmo/core-service
&& sudo systemctl start karmo-core.service`. The `karmo_core_memory` DB
role and `/etc/karmo/core/postgres.dsn` may remain — the prior code never
reads them.

**Operator/agent responsible:** Claude Code (this session), all
production writes explicitly authorized by Kamara in-session
(read-only audit authorization, then write/deploy authorization), per
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s Mandatory Production
Access Authorization Gate. See authorization record in `CURRENT_STATE.md`.

**Next action:** none required for this workstream — durable memory is
deployed and verified. See `NEXT_STEPS.md` for what's next.

---

## 2026-09-15 (continued) — Registry-repair dry run, dashboard staleness fix, and PR #43 reconciliation

**Change ID / commits:** PR #52 (docs, dashboard fix), evidence commit
`7554c25` (H0.4 dry-run + audit record, PR #53), PR #54 (code merge,
`f2ba1a49ebe8baf664a93cf59dc74693506db42a`).

### Dashboard staleness found and fixed (VERIFIED)
While auditing "merged but not running" items at Kamara's request,
found `KARMO_DASHBOARD.md` still claimed real Worker network transport
was disabled and listed 5 security items as still deferred. Verified in
code that all 5 are closed (`crypto_boundary.py`, subprocess env
allowlisting, symlink tests, `ResultAuthenticator`,
`PostgresWorkerCoordinatorStore`) and a real SSH-stdio transport has
been live since ~2026-09-13/14. Corrected; no production change.

### `registry_repair.py` deployed and run — the one real "merged but never run" gap (VERIFIED)
Deployed the reviewed, tested `h04/app/registry_repair.py` (merged
2026-09-09, never executed against production) as a new file alongside
the existing H0.4 modules at `/home/lofason/karmo-ai/core/app/`, SHA-256
verified before use, run in default dry-run mode (no `--apply`, zero
writes by the tool's own construction). Also ran a fresh full
`auditor.py` pass via a small one-off wrapper. Result:
`READY_TO_REGISTER: 0`, and every finding across both runs (18
`LEGACY_PROVENANCE_UNVERIFIED`, 2 `ORPHAN_VECTOR`, 3
`ACTIVE_STATE_MISMATCH`) traced to the same 5 known pre-H0.2 legacy
documents, behaving exactly as already documented on 2026-09-09. No new
or real data-integrity problem. Full detail:
`docs/evidence/h04/H04_2026-09-15_FULL_AUDIT_AND_REPAIR_DRY_RUN.md`.
Two lessons recorded in that evidence file for next time: the DSN-file
*directory* permissions matter as much as the file's own (mode 700 on
`/etc/karmo/core` blocked traversal even after the file itself was
readable), and `KARMO_DB_PASSWORD` for the older H0.4 stack comes from
`/home/lofason/karmo-ai/compose/.env`'s `POSTGRES_PASSWORD`, not a
separate credential.

### PR #43 reconciled into `main` (VERIFIED, merged, NOT deployed)
Kamara asked what PR #43 was and why it hadn't been merged — checked the
full comment history (10 comments, 12+ iterations): **no rejection was
ever recorded.** It was an open-ended staging/hardening exploration that
kept finding and fixing real issues (each iteration's own note ended
"keep draft, next safe action is X") and simply never reached a
promotion decision before other work took priority. By 2026-09-15 the
branch (29 real commits) had diverged 94 commits behind `main` (common
ancestor `879b242c`, the PR #41 merge point).

**What actually shipped in it** (verified by reading every file in full,
not just the diff):
- **The real security fix**: an approval could be reused across a
  different requester or a different computed authority-requirement
  class than it was issued under. Closed at both the shared
  `CapabilityDispatcher` (`_require_approval_authority_binding`) and,
  independently, `PostgresExecutionCoordinator.claim()` — two layers,
  no gap between them (confirmed by reading both call paths end to end).
- `ModelResource`/`ModelRouter` input validation and hard
  `require_local`/`minimum_trust_tier`/`excluded_providers` eligibility
  gates (previously `prefer_local` only affected ordering).
- KarmoLab wired through the authoritative registry + dispatcher with a
  closed manifest.
- Verifier acceptance changed from `startswith("PASS")` to exact
  normalized `PASS` — closes a prior false-accept path.
- Durable recovery: a full validation pass over the unfinished-invocation
  set before any task write (previously a bad ledger row could mutate
  earlier valid tasks before being detected); atomic commit semantics
  (in-memory `state_version` only advances after the DB transaction
  actually commits, not before).
- Terminal invocation status allowlisting (`EXECUTED`/`FAILED` only)
  before ledger/coordinator writes.
- Worker document-processing size cap (8 MB, checked before
  `read_text()`).

**Merge conflicts (3 files), each resolved by combining both branches'
work rather than picking one side:**
- `model_router.py`: kept PR #43's validation/hard-gate `route()`/
  `verifier_for()` as a strict superset; re-added `ranked()` (absent on
  the staging branch entirely) so `main`'s multi-candidate chat fallback
  chain still has a list to iterate, with `route()`/`verifier_for()`
  both delegating to it.
- `operator.py`: combined PR #43's routing-policy enforcement with
  `main`'s durable-memory integration (`_memory_context`,
  `remember_exchange`, `_combine_memory_status`) in one `_chat()`.
- `capabilities.py`: trivial — PR #43 predates Commander entirely, kept
  `main`'s handler registrations.

**A real policy conflict surfaced and was resolved by explicit decision,
not silently:** PR #43's `OPERATOR_PRIMARY_MIN_TRUST_TIER=30`, applied
uniformly, would have silently excluded `granite3.3:2b` (trust_tier 20,
the deliberate "fast fallback") from ordinary chat's fallback chain
entirely — narrowing live production resilience from 3-way to 2-way
fallback without anyone deciding that on purpose. **Kamara's explicit
call, asked directly rather than assumed**: the trust floor governs only
the KarmoLab status/verification path (`_models()`); ordinary chat keeps
its full fallback chain. Proven by a replacement test
(`test_chat_still_uses_local_model_below_verification_trust_floor`)
in place of one that asserted the rejected behavior.

**One stale test found and fixed** (diagnosed, not silently patched):
`test_operator_verifier_strictness.py`'s fake verifier client checked
`model == "llama3.2:3b"` — the verifier *before* the 2026-09-13
model-stack activation (PR #45) switched it to `mistral:7b`. The
branch's last update predated that switch.

**Independent security review** (this session, before push): read every
changed file in full. No HIGH/MEDIUM findings — the authority-binding
fix is correctly scoped and doubly enforced; every other change is
strictly additive validation or internal consistency/atomicity hardening
over non-attacker-facing data.

**Validation**: all four suites green post-merge — core-service 148
passed/33 skipped, worker-runtime 111 passed, core-v2-prototypes 161
passed, worker-service 2 passed + healthy CLI. CI on PR #54: 5/5 green.

**Production status at merge time: NOT DEPLOYED.** GitHub auto-marked
PR #43 itself as merged once its commits became ancestors of `main` via
this reconciliation. See the next entry for the actual deployment.

---

## 2026-09-15 (continued) — PR #43 deployed; a real keyword false-positive found and fixed via BloomBoss reconciliation and canary

**Change ID / commits:** PR #56 (BloomBoss reconciliation, not merged —
awaiting Kamara's decision), PR #57 (`fbaf42752e7a4a124379778b9c7a3ea55fdc62c4`,
keyword false-positive fix), two production deploys to `karmo-ai01`.

### BloomBoss Phase 1 (PR #32) reconciled — VERIFIED, not merged
Kamara asked to work BloomBoss in parallel with the PR #43 deploy.
Branch had diverged 147 commits ahead / 238 behind `main`, but only one
file actually conflicted (`KARMO_DASHBOARD.md`, docs-only) — all 60+
other files were BloomBoss-only additions main never touched. Resolved
the one conflict (kept main's accurate current status, folded in
BloomBoss's still-relevant notes), ran all 62 BloomBoss tests (pass),
scanned `bloomboss/*.py` for risky patterns (none found). Opened **PR
#56**. **Deliberately not merged** — PR #32's own text reserves that for
Kamara's "separate high-level merge/promotion decision" given real
financial/business logic is involved; a general "go ahead" doesn't
override an explicit human-decision gate like that.

### PR #43 deployed to `karmo-ai01` — VERIFIED
Deployed merge commit `de16b6e959a0ccec30444abea6b1005f6cccd101` via the
established tarball/SHA-256/backup pattern (matched:
`356307c651da332c7983e6e7a2596b81e1e3d5996fc8a0307be15c366258a601`).
Simpler than the durable-memory deploy — pure code replace, no new
secrets/DB grants needed. Restarted `karmo-core.service`, active.

**Canary 1** (KarmoLab status path — the one PR #43's trust-floor/routing
policy directly governs): executed successfully end-to-end, full
evidence returned (host/disk/memory/services/containers all correct).
`verification=FAIL` on this run was *correct*, not a bug — PR #43's new
exact-match verifier strictness (only literal `PASS` releases the AI
summary) correctly fell back to raw verified evidence rather than a
possibly-inexact model response. Proves the new strictness works as
designed.

**Canary 2 found a real bug**: `printf 'Please recall this exact phrase
for later: pr43-deploy-canary-final.\n' | ... chat` was refused as a
write-intent request — `_WRITE_WORDS` (pre-existing, not part of PR #43
or #48/#49) includes "deploy", and the canary's own phrase contained
"-deploy-". Same bug class as the "memory" collision fixed in PR #49,
just a different word.

### Systematic fix (PR #57) — VERIFIED
Rather than patch one more word, tested 21 realistic harmless chat
phrases against both `_WRITE_WORDS` and `_STATUS_WORDS` before changing
anything: **11/21** false-positived on `_WRITE_WORDS` (write, start,
stop, remove, change, create, update, patch, deploy, install, delete),
**6/21** on `_STATUS_WORDS` (disk, host, running, service, healthy,
container). Also discovered "healthy" had silently reappeared in
`_STATUS_WORDS` via a PR #43 merge artifact — a line that differed
between branches but wasn't flagged as a conflict, so git's 3-way merge
picked PR #43's older value without anyone reviewing it. A real lesson:
**an unconflicted line is not guaranteed correct after a merge between
branches that both touched nearby code** — worth a second look at
surrounding context even when git doesn't flag anything.

Key judgment call: the operator has zero real write capability wired to
any handler — the model itself refuses per its own system prompt
regardless of whether this pre-filter catches a write-intent phrase
first. So the regex is a cheap UX pre-filter, not a security boundary,
and the fix correctly favors eliminating false positives (which break
ordinary conversation) over catching every possible write-phrasing
before the model sees it (which still safely refuses on its own).
Verified before applying: 0 false positives on the 21-phrase set, 0
missed genuine intents on 17 real write/status phrasings. New test file
(`test_operator_keyword_false_positives.py`) proves both properties
against the actual phrases that motivated the fix.

Deployed commit `fbaf42752e7a4a124379778b9c7a3ea55fdc62c4` the same way
(SHA-256 `5ca51bf72e72a070159043c87be67c560b9362db93445a3b845a913245ad341a`
matched). **Final canary: the exact phrase that failed before
(`pr43-deploy-canary-final`) now correctly reaches chat and durable
memory, `memory=ACTIVE`.**

**Production status: PR #43 and the keyword fix are both DEPLOYED and
VERIFIED on `karmo-ai01`.** BloomBoss (PR #56) remains reconciled and
tested but NOT merged, pending Kamara's decision.

**Next action:** Kamara's merge/promotion decision on BloomBoss (PR
#56), or choice of next capability track.
