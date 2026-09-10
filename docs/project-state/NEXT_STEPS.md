# KARMO Next Steps

See MASTER_INDEX.md for status-tag definitions. **KARMO FOUNDATION v1 was
declared COMPLETE on 2026-09-09.** Two further repository-only,
zero-production-access programs ran the same day: the Post-Foundation
Overnight Readiness Program (PRs #14–#17) and the Core v2 Engineering
Blueprint Program (PRs #18–#21). The primary next action is now
**Natalie's set of decisions listed below** — there is no outstanding
foundation-blocking work, and nothing in either program requires an
urgent response.

## Items requiring Natalie's decision

### From the Post-Foundation Overnight Readiness Program
1. Merge/reject PR #14 (Foundation v1 verification review + checklist
   correction) — docs-only.
2. Merge/reject PR #15 (H0.4 `check_active_version_state` legacy-
   definition fix) — isolated code fix, 17/17 tests (2 new + 15
   existing), not yet deployed to production even if merged.
3. Merge/reject PR #16 (Tool/Capability Registry design v1, adversarial
   review, post-foundation roadmap v1) — design/planning only.
4. Merge/reject PR #17 (PROJECT SAVE for that program).

### From the Core v2 Engineering Blueprint Program
5. Merge/reject PR #18 (architecture map, observability design, Core v2
   security threat model, test strategy, run-verification system design)
   — design/documentation only.
6. Merge/reject PR #19 (Core v2 prototypes: Tool Registry, Approval
   Engine, Job/Event model, config POC, failure injection, run-evidence
   validator) — 160/160 tests pass, nothing wired into production.
7. Merge/reject PR #20 (BloomBoss/Voice-Media/Finance readiness specs,
   implementation dependency graph, consolidated Core v2 spec) —
   design/planning only.
8. Merge/reject PR #21 (PROJECT SAVE for this program).

### Choices, not just merges
9. **Choose the first post-foundation capability track**, or a
   sequencing alternative (registry-first / domain-first / KarmoLab-
   proving-ground) — see
   `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` and
   `docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`'s 6 candidate
   batches. Still entirely open; nothing in either program narrows this
   choice, only informs it.
10. **Weigh the two proposed (not adopted) invariant candidates**:
    configuration single-sourcing (prior program) and tool-registration
    review (this program).
11. **Decide whether/when to build any Core v2 component for real** — every
    design and prototype from this program is isolated and unimplemented
    in production; Batch 1 of the dependency graph is the lowest-risk
    starting point if/when Natalie chooses to proceed. This includes the
    specific Workstream 3 question carried from the prior program —
    whether/when to build the Tool/Capability Registry itself — for which
    only a design exists and no phase is authorized to start.

## Recommended (non-blocking) follow-ups, in rough priority order

12. Workstream 4's MEDIUM findings from the prior program — live
    pagination ceiling in `document_memory.get_document_history` (same bug
    class already fixed elsewhere in H0.4), no connection pooling
    anywhere, no embedding-model provenance on `karmo_semantic_memory`,
    configuration drift across ~10 files. None urgent at current scale;
    all worth addressing before the capability that would first stress
    them. Full detail:
    `docs/evidence/post-foundation-readiness/WORKSTREAM4_ADVERSARIAL_ARCHITECTURE_REVIEW.md`.
    This program's dependency graph
    (`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`, Batch 1)
    already scopes fixes for the first two as small, standalone,
    parallelizable items.
13. `SOFTWARE_INVENTORY.md`/`NETWORK_INVENTORY.md` can be updated from the
    2026-09-09 production evidence (routine, not blocking, unchanged).

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
- H0.3 remains NO-PROMOTION — not promoted, not touched by either program.

## Not next steps (explicitly out of scope, unchanged)

- No production access occurred in either program tonight — zero SSH,
  zero database/Qdrant/container/credential/log/network access.
- No PR was merged by either program (PRs #14–#21 all opened, none
  merged).
- No governance was modified by either program.
- No Voice/Media/BloomBoss/KarmoLab/Personal-Productivity/Finance
  capability was implemented or started.
- No first-capability scope was chosen on Natalie's behalf.
