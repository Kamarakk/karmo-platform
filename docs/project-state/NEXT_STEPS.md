# KARMO Next Steps

See MASTER_INDEX.md for status-tag definitions. **KARMO FOUNDATION v1 was
declared COMPLETE on 2026-09-09**; the Post-Foundation Overnight Readiness
Program ran the same night (repository-only, zero production access). The
primary next action is now **Natalie's set of decisions listed under
"Items requiring Natalie's decision" below** — there is no outstanding
foundation-blocking work, and nothing tonight's program did requires an
urgent response.

## Items requiring Natalie's decision

1. **Merge/reject PR #14** (Foundation v1 verification review + checklist
   correction) — docs-only, no code, no production access.
2. **Merge/reject PR #15** (H0.4 `check_active_version_state` legacy-
   definition fix) — isolated code fix, 2 new tests + 15/15 existing tests
   unchanged, not yet deployed to production even if merged (a separate,
   future, explicitly-authorized step).
3. **Merge/reject PR #16** (Tool/Capability Registry architecture,
   adversarial review, post-foundation roadmap) — design/planning
   documentation only, no code.
4. **Choose the first post-foundation capability track** (or a registry-
   first / domain-first / KarmoLab-proving-ground sequencing alternative)
   — see `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md`. Still
   entirely open; nothing in tonight's program narrows this choice, only
   informs it.
5. **Weigh the proposed "configuration single-sourcing" invariant
   candidate** from Workstream 4 — proposed only, governance unchanged.
6. **Decide whether/when to build the Tool/Capability Registry**
   (Workstream 3) — design only exists; no phase is authorized to start.

## Recommended (non-blocking) follow-ups, in rough priority order

7. Workstream 4's MEDIUM findings — live pagination ceiling in
   `document_memory.get_document_history` (same bug class already fixed
   elsewhere in H0.4), no connection pooling anywhere, no embedding-model
   provenance on `karmo_semantic_memory`, configuration drift across ~10
   files. None urgent at current scale; all worth addressing before the
   capability that would first stress them. Full detail:
   `docs/evidence/post-foundation-readiness/WORKSTREAM4_ADVERSARIAL_ARCHITECTURE_REVIEW.md`.
8. `SOFTWARE_INVENTORY.md`/`NETWORK_INVENTORY.md` can be updated from the
   2026-09-09 production evidence (routine, not blocking — unchanged from
   before).

## Keep the two ambiguous legacy hashes unresolved (no action required, active constraint)

`karmo-v05-new.html` hashes
`23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c` and
`5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78` remain
**intentionally unresolved** (`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`),
reconfirmed present as `ORPHAN_VECTOR` in both the 2026-09-09 production
audit and (structurally) untouched by the Workstream 2 fix. Resolution
requires a human decision on version ordering —
`bootstrap_legacy_registry.py` will not and should not guess. Do not mark
resolved without that explicit decision recorded.

## Completed, no further action

- Foundation Completion Workloads 1–4 (PRs #7, #8, #9, #10) — merged.
- Production Access Authorization Gate (PR #12) — merged, first exercised
  successfully the same night.
- Foundation v1 closeout evidence package (PR #13) — merged.
- H0.3 remains NO-PROMOTION — not promoted, not touched, unaffected by
  tonight's program.

## Not next steps (explicitly out of scope, unchanged)

- No production access occurred in tonight's program (explicitly
  prohibited by its own authorization) — zero SSH, zero
  database/Qdrant/container/credential/log/network access.
- No PR was merged by tonight's program (PRs #14, #15, #16 opened, not
  merged).
- No governance was modified.
- No Voice/Media/BloomBoss/KarmoLab/Personal-Productivity/Finance
  capability was implemented or started.
- No H0.5/first-capability scope was chosen on Natalie's behalf.
