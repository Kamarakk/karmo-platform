# Proposed Merge Sequence — PR #14 through #21

No merge commands were executed to produce this document — every step
below was verified via local simulation only (`git merge` on a scratch
branch, never pushed, discarded after). Natalie (or whoever has merge
authority) performs the actual merges on GitHub.

## Sequence

1. **PR #14** — Foundation v1 verification review. Independent of
   everything else. Merge first or in any order relative to #15/#16.
2. **PR #15** — H0.4 auditor fix. Independent of #14/#16. Isolated code
   change, own test suite.
3. **PR #16** — Tool/Capability Registry design v1 + roadmap v1.
   Independent of #14/#15 technically; merging by this point means PR
   #20's later cross-references (to `docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md`)
   resolve cleanly for anyone reading `main`.
4. **PR #17** — PROJECT SAVE for the first program. **Must merge before
   #21** (see conflict analysis in `KARMO_PR14_21_MERGE_READINESS.md`) —
   merging it here, right after its own program's #14–#16, keeps the
   chronological narrative sensible regardless.
5. **PR #18** — Core v2 architecture/security/test-strategy/verification
   designs. Independent of #14–#17 (no file overlap). Natural to merge
   after the first program closes out, since it opens the second.
6. **PR #19** — Core v2 prototypes (now updated with the 4 adversarial
   fixes, 160/160 tests). Independent of #18 technically (no file
   overlap), but logically follows it.
7. **PR #20** — Domain readiness specs + dependency graph + consolidated
   spec (now updated with correct 160/160 references). References #16,
   #18, #19's content by filename — merging after all three keeps every
   cross-reference resolvable on `main` at the moment #20 lands.
8. **PR #21** — PROJECT SAVE for the second program (now updated with
   correct 160/160 references). **Merges last, after #17** — at this
   point, resolve the expected conflict in `docs/project-state/CHANGE_LOG.md`,
   `CURRENT_STATE.md`, `NEXT_STEPS.md` by keeping both programs' additive
   content (see resolution guidance in the main readiness packet).

## Why this order and not another

- Within each program, the PROJECT SAVE PR (#17, #21) is placed last
  because it is, by definition, the record of everything else in that
  program — merging it after its siblings means its own narrative is
  never describing not-yet-merged work as already merged.
- #16 before #18–#20 is a soft preference (documentation
  cross-reference resolvability), not a hard requirement — no git
  conflict exists between the two programs' design PRs.
- The only HARD ordering constraint discovered by this review is #17
  before #21, to make the (unavoidable either way) conflict resolution
  happen against a stable, already-decided-first-program state rather
  than the reverse.

## What does NOT need to happen first

- PR #19 does not need #18 merged first — they don't share files, and
  #19's prototypes are self-contained (their own `README.md`,
  `requirements.txt`, `conftest.py` files — nothing in #19 imports
  anything from #18's design docs).
- PR #15 does not depend on PR #8's already-merged registry-repair tool
  being anything other than what it already is on `main` — confirmed by
  running both test suites together this session (17/17 pass).
