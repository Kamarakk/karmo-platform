# KARMO Next Steps

See MASTER_INDEX.md for status-tag definitions. **KARMO FOUNDATION v1 was
declared COMPLETE on 2026-09-09** — see
`docs/evidence/foundation-v1/FOUNDATION_V1_CLOSEOUT_REPORT.md` for the full
closeout report. The primary next action is now **Natalie choosing the
first post-foundation capability phase** (see item 6 below) — there is no
outstanding foundation-blocking work.

## 1. Keep the two ambiguous legacy hashes unresolved (no action required, active constraint)

`karmo-v05-new.html` hashes
`23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c` and
`5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78` remain
**intentionally unresolved** (`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`),
reconfirmed present as `ORPHAN_VECTOR` in the 2026-09-09 production audit —
exactly as expected, not touched. Resolution requires a human decision on
which hash is the correct `document_version` ordering for that source file
— `bootstrap_legacy_registry.py` will not and should not guess. Do not mark
these resolved without that explicit decision recorded. Standing
constraint until Natalie decides; does not block Foundation v1 or any
future phase.

## 2. Foundation Completion Workload 1 — Repository hygiene & evidence durability (MERGED, COMPLETE)

Merged 2026-09-08 (PR #7, `db4ff2f`). No further action.

## 3. Foundation Completion Workload 2 — Production verification closeout (COMPLETE, PASS)

Executed 2026-09-09 under Natalie's temporary, session-scoped, task-specific
Production Access Authorization, per the Mandatory Production Access
Authorization Gate. Both defined checks passed: H01-T01 (manifest
presence/hash) and H01-T18 (baseline counts, every value either an exact
match or a fully-explained delta from an already-recorded event). Full
detail: `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.
No further action required for Foundation v1.

## 4. Foundation Completion Workload 3 — Registry integrity repair tool (MERGED, COMPLETE)

Merged 2026-09-09 (PR #8, `06ab726`). Still isolated-only — no production
execution performed or authorized; a separate, future, explicitly-authorized
action if ever pursued (not currently planned).

## 5. Foundation Completion Workload 4 — Spec Kit brownfield adoption (MERGED, COMPLETE)

Merged 2026-09-09 (PR #9, `cd72938`).

## 6. Choose the first post-foundation capability phase (PARTIALLY ACTED ON — Worker Runtime v0.1 built, not merged/deployed)

H0.5's specific scope was not formally chosen by Natalie, but on
2026-09-09 she explicitly authorized building KARMO's first real
post-foundation capability directly: a distributed Worker Runtime
allowing trusted machines (starting with KARMO-DEV01) to register, poll
for bounded jobs, execute them sandboxed, and return evidence. This was
implemented, tested, and evidenced this workload — see "KARMO Worker
Runtime v0.1" in CURRENT_STATE.md and `docs/evidence/worker-runtime/`.
**Not merged to `main` or `core-v2/prototypes`. Not deployed. Not
connected to production.**

**Two rounds of independent (ChatGPT) verification (2026-09-09/10,
before any merge)** of PRs #23–#25. Round 1 found 4 real blocking
findings not caught by this workload's own original review: approval
gated job completion but not execution; timeout enforcement was a
post-return check, not a real deadline; only `stdout_summary` was
bounded, not the full result; a worker heartbeat could set
coordinator-owned scheduling state directly — fixed at commit `5906f61`.
Round 2 found round 1's fix was correct but left the normal WorkerClient
flow no way to represent a legitimately-pending approval other than a
hard failure — an approval-required job was marked FAILED the instant it
was leased — fixed at commit `08c501e` (jobs now park in
`WAITING_FOR_APPROVAL` and resume exactly once approved, or end safely
on denial/expiry). **67/67 tests passing** (was 44/44 → 62/62 → 67/67) —
see CURRENT_STATE.md's Worker Runtime section and
`docs/evidence/worker-runtime/RUN_SUMMARY.json` for full detail. PRs
remain open, awaiting re-verification, still Natalie's to review/merge.
Remaining choice for Natalie: merge this as-is, request further changes,
or treat it as one input alongside the still-undecided Tool/Capability
Registry track when formally scoping H0.5.

## 6a. Worker Runtime v0.1 — named follow-ups before any real network exposure

Not blocking, not started, explicitly deferred per this workload's scope:
cryptographic worker credentials (currently a bare `worker_id` string with
only identity-consistency checking, no proof of possession); subprocess
environment allowlisting for `pytest`/`static_analysis` handlers; a
symlink-escape-specific test to directly prove `resolve_within_sandbox`'s
existing containment check; a result-authenticity binding beyond the
current internal-consistency digest; and coordinator persistence (today
fully in-memory, confirmed by scenario 24 — no restart recovery exists).
Full detail: `docs/evidence/worker-runtime/SECURITY_REVIEW.md`'s "Open
findings" section. None of these block continued isolated-prototype work;
all of them block any real network transport or any capability above
`READ`/workspace-scoped `REVERSIBLE_WRITE`.

## 7. Recommended (non-blocking) follow-up: H0.4 auditor legacy-active-state gap

Discovered during the 2026-09-09 closeout's production audit:
`reconciliation.check_active_version_state` has no legacy-aware carve-out
for a legacy-bootstrapped registry row (unlike `check_provenance`'s
existing `LEGACY_PROVENANCE_UNVERIFIED` handling), so it permanently
reports `ACTIVE_STATE_MISMATCH` for the 3 documents
`bootstrap_legacy_registry.py` already registered — correct data, an
auditor blind spot, not a data-integrity problem. Full detail:
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`. Worth a
small, separately-scoped fix at some point; does not block anything.

## 8. Confirm current live data counts (routine, low urgency — now closed out)

`SOFTWARE_INVENTORY.md` and `NETWORK_INVENTORY.md` flagged several current
counts as **NEEDS VERIFICATION**; all were reconfirmed during the
2026-09-09 Workload 2 closeout — see
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`. Those
two inventory files can be updated from that evidence in a future pass if
desired (routine, not blocking).

## Not next steps (explicitly out of scope, unchanged)

- H0.3 remains NO-PROMOTION — not promoted, not touched.
- The two ambiguous H0.4 legacy hashes were not resolved (see #1).
- No H0.5 spec/plan/tasks were written — Workload 5 remains Natalie's
  scope choice (see #6).
- No production write, restart, deployment, or configuration change was
  ever performed — all production actions across the Foundation Closeout
  Program were read-only, per every authorization granted.
