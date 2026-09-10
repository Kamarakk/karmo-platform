# KARMO Next Steps

See MASTER_INDEX.md for status-tag definitions. **KARMO FOUNDATION v1 was
declared COMPLETE on 2026-09-09.** Two further repository-only,
zero-production-access programs ran the same day: the Post-Foundation
Overnight Readiness Program (PRs #14–#17) and the Core v2 Engineering
Blueprint Program (PRs #18–#21).

**An independent merge-readiness review of PRs #14–#21 completed
2026-09-09** — see
`docs/evidence/autonomous-review/KARMO_PR14_21_MERGE_READINESS.md` for
full PR-by-PR status and `docs/evidence/autonomous-review/MERGE_SEQUENCE.md`
for the recommended merge order (#14, #15, #16, #17, #18, #19, #20, #21 —
#17 before #21 specifically, to resolve a real, documented conflict
between the two PROJECT SAVE PRs). PR #19 was updated in place with 4
adversarial-review fixes (154 → 160 tests); PR #20 and #21 were updated
in place to correct the resulting stale test-count references. No new PR
was created for these fixes — existing PRs were updated directly. **PRs
#14–#24 have since merged into `main`** via the approved KARMO merge
sequence (PR #23 at commit `11d4f86e04d22aae0072923ec387a11f0e205cbc`, PR
#24 at commit `9f3215ecd3be31d2096273be4afb389edbcbf9f8`) — see "Worker
Runtime v0.1 merge closeout" in `CURRENT_STATE.md`.

The primary next action is now **Natalie's set of decisions listed
below** — there is no outstanding foundation-blocking work, and nothing
requires an urgent response.

## Items requiring Natalie's decision

### From the Post-Foundation Overnight Readiness Program (MERGED)
1. ~~Merge/reject PR #14~~ — **merged** into `main`.
2. ~~Merge/reject PR #15~~ — **merged** into `main`.
3. ~~Merge/reject PR #16~~ — **merged** into `main`.
4. ~~Merge/reject PR #17~~ — **merged** into `main`.

### From the Core v2 Engineering Blueprint Program (MERGED)
5. ~~Merge/reject PR #18~~ — **merged** into `main`.
6. ~~Merge/reject PR #19~~ — **merged** into `main`. 160/160 tests pass at
   merge time; nothing wired into production.
7. ~~Merge/reject PR #20~~ — **merged** into `main`.
8. ~~Merge/reject PR #21~~ — **merged** into `main`.

### From the KARMO Large Autonomous Review (MERGED)
9. ~~Merge/reject PR #22~~ (`review/pr14-21-merge-readiness`) — **merged**
   into `main`.

### From the Worker Runtime v0.1 workload (PENDING — the only open item left)
10. **Merge/reject PR #25** (`worker-runtime/evidence`: evidence package +
    PROJECT SAVE). PR #23 (implementation + tests, commit `11d4f86e`) and
    PR #24 (architecture/security/network docs, commit `9f3215ec`) are
    already merged into `main` — merged into the source tree, **not**
    deployed or connected to production. PR #25 was retargeted to `main`
    and, before this commit, was blocked by the expected conflicts in
    these same three `docs/project-state/` files, now resolved here.
    Authoritative verification: **68/68** worker-runtime tests, **161/161**
    core-v2-prototypes regression — see
    `docs/evidence/worker-runtime/RUN_SUMMARY.json`.

### Choices, not just merges
11. **Choose the first post-foundation capability track**, or a
    sequencing alternative (registry-first / domain-first / KarmoLab-
    proving-ground / continue building out Worker Runtime) — see
    `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` and
    `docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`'s 6 candidate
    batches. Still entirely open; nothing merged so far narrows this
    choice, only informs it.
12. **Weigh the two proposed (not adopted) invariant candidates**:
    configuration single-sourcing and tool-registration review.
13. **Decide whether/when to build any further Core v2 component for
    real** — every design and prototype so far is isolated and
    unimplemented in production (Worker Runtime v0.1 is the one
    exception moving toward real use, still not deployed); Batch 1 of the
    dependency graph is the lowest-risk starting point for anything else.
    This includes the specific Workstream 3 question — whether/when to
    build the Tool/Capability Registry itself — for which only a design
    exists and no phase is authorized to start.

## Worker Runtime v0.1 — named follow-ups before any real network exposure

Not blocking, not started, explicitly deferred per that workload's scope:
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

## Recommended (non-blocking) follow-ups, in rough priority order

14. Workstream 4's MEDIUM findings from the Post-Foundation program — live
    pagination ceiling in `document_memory.get_document_history` (same bug
    class already fixed elsewhere in H0.4), no connection pooling
    anywhere, no embedding-model provenance on `karmo_semantic_memory`,
    configuration drift across ~10 files. None urgent at current scale;
    all worth addressing before the capability that would first stress
    them. Full detail:
    `docs/evidence/post-foundation-readiness/WORKSTREAM4_ADVERSARIAL_ARCHITECTURE_REVIEW.md`.
    The Core v2 dependency graph
    (`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`, Batch 1)
    already scopes fixes for the first two as small, standalone,
    parallelizable items.

## Keep the two ambiguous legacy hashes unresolved (no action required, active constraint)

`karmo-v05-new.html` hashes
`23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c` and
`5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78` remain
**intentionally unresolved** (`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`),
reconfirmed present as `ORPHAN_VECTOR` in both the 2026-09-09 production
audit and (structurally) untouched by the Workstream 2 fix. Resolution
requires a human decision on version ordering —
`bootstrap_legacy_registry.py` will not and should not guess. Do not mark
resolved without that explicit decision recorded. Untouched by either
program.

## Completed, no further action

- Foundation Completion Workloads 1–4 (PRs #7, #8, #9, #10) — merged.
- Production Access Authorization Gate (PR #12) — merged, exercised
  successfully the same night.
- Foundation v1 closeout evidence package (PR #13) — merged.
- H0.3 remains NO-PROMOTION — not promoted, not touched by any program.
- Post-Foundation Overnight Readiness Program (PRs #14, #15, #16, #17) —
  merged. H0.4 auditor legacy-active-state gap (Workstream 2) fixed as
  part of PR #15 — no further action.
- Core v2 Engineering Blueprint Program (PRs #18, #19, #20, #21) —
  merged. Nothing wired into production.
- KARMO Large Autonomous Review of PR #14–#21 (PR #22) — merged.
- Worker Runtime v0.1 implementation + tests (PR #23, commit `11d4f86e`)
  and architecture/security/network docs (PR #24, commit `9f3215ec`) —
  merged into `main`, **not deployed, not connected to production**. PR
  #25 (evidence + PROJECT SAVE) is the one item still open — see item 10
  above.
- `SOFTWARE_INVENTORY.md`/`NETWORK_INVENTORY.md` current counts —
  reconfirmed during the 2026-09-09 Workload 2 closeout; no further
  action required (routine update from existing evidence deferred, not
  blocking).

## Not next steps (explicitly out of scope, unchanged)

- No production access occurred in either program tonight — zero SSH,
  zero database/Qdrant/container/credential/log/network access.
- No PR was merged *during* either program's own run (PRs #14–#21 were
  all opened, none merged, at that time) — historical, describing that
  night's activity only. PRs #14–#24 have since merged via the separate,
  later approved KARMO merge sequence; see "Completed, no further
  action" above.
- No governance was modified by either program.
- No Voice/Media/BloomBoss/KarmoLab/Personal-Productivity/Finance
  capability was implemented or started.
- No first-capability scope was chosen on Natalie's behalf.
