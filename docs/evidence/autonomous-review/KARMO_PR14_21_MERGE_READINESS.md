# KARMO PR #14–#21 — Independent Merge-Readiness Review

Produced under the KARMO Large Autonomous Review program. Independent
re-audit of all 8 currently open PRs from the two prior autonomous
programs — nothing here is trusted from those programs' own final
reports; every claim below was re-derived this session (fresh git/GitHub
queries, fresh test runs, fresh code reading). No production access, no
merges performed by this review.

## PR #14 — Foundation v1 verification review + checklist correction

- **Purpose**: independent audit of `docs/evidence/foundation-v1/`,
  correcting 3 circular checklist items.
- **Scope check**: matches — docs-only, 3 files, no code.
- **Files inspected**: all 3. No secrets, no runtime artifacts, no
  generated junk.
- **Cross-checks**: `MANIFEST.sha256` re-verified this session (6/6 OK).
  H0.3 NO-PROMOTION status untouched. Ambiguous H0.4 hashes untouched.
  No production changes embedded.
- **Result**: **READY_TO_MERGE**.

## PR #15 — H0.4 `check_active_version_state` legacy-definition fix

- **Purpose**: fix the recorded auditor gap (spurious `ACTIVE_STATE_MISMATCH`
  for legacy-bootstrapped documents).
- **Scope check**: matches — one function in `reconciliation.py`, plus
  tests and evidence.
- **Fresh reproduction this session**: full H0.4 suite (17 tests across
  `test_h04_integrity_reconciliation.py`, `test_h04_pagination.py`,
  `test_h04_registry_repair.py`, `test_h04_active_state_legacy_fix.py`)
  run together against a freshly-created isolated Docker stack —
  **17/17 PASS**. `auditor.py` diff confirmed empty
  (`git diff main <branch> -- h04/app/auditor.py` produces no output).
- **Cross-checks**: compatible with the already-merged `test_h04_registry_repair.py`
  suite (from PR #8, already on `main`) — confirmed by running both
  together. No production changes embedded — isolated Docker stack only.
- **Result**: **READY_TO_MERGE**.

## PR #16 — Tool/Capability Registry design v1 + adversarial review + roadmap v1

- **Purpose**: original registry architecture, prior adversarial findings,
  and the first capability roadmap.
- **Scope check**: matches — docs-only, 5 files.
- **Cross-checks**: `docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md`
  (this PR) is the design PR #19's prototypes and PR #20's consolidated
  spec both build on — merging #16 first (or concurrently) keeps those
  cross-references resolvable, though this is a documentation-completeness
  concern, not a git conflict (confirmed no file overlap in simulation).
- **Result**: **READY_TO_MERGE**.

## PR #17 — PROJECT SAVE for Post-Foundation Overnight Readiness Program

- **Purpose**: reconcile `docs/project-state/` for PRs #14–#16.
- **Scope check**: matches — 3 `docs/project-state/` files.
- **Cross-PR conflict found**: edits the same 3 files as PR #21 (both
  branched from the same pre-#17 `main`). Confirmed via local merge
  simulation: merging #17 first, then #21, produces real content
  conflicts in all 3 files (multiple hunks each — both PRs independently
  rewrote overlapping top-line-summary and "next steps" sections). See
  "Cross-PR Conflict Analysis" below for the exact resolution guidance.
- **Result**: **READY_WITH_NONBLOCKING_NOTES** — the PR's own content is
  correct and clean against current `main`; the conflict is a property of
  the pair (#17, #21), not a defect in #17 itself, and is resolved at
  merge time per the recommended order below.

## PR #18 — Core v2 architecture map, observability/security/test-strategy/verification-system designs

- **Purpose**: Workstreams 1, 6, 8, 13, 14 (design) of the Core v2
  Engineering Blueprint Program.
- **Scope check**: matches — docs-only, 5 files.
- **Cross-checks**: no stale references found (this design doc's own
  description of the run-evidence verifier's checklist item 4 was
  already correct — it was PR #19's *implementation* that fell short,
  now fixed by this review; PR #18 itself needed no update).
- **Result**: **READY_TO_MERGE**.

## PR #19 — Core v2 prototypes

- **Purpose**: isolated Tool Registry, Approval Engine, Job/Event model,
  config POC, failure-injection framework, run-evidence validator.
- **Scope check**: matches — `core-v2-prototypes/` + evidence, no
  production wiring.
- **Fresh reproduction this session**: rebuilt the venv from scratch
  (`rm -rf venv`, reinstalled from `requirements.txt`), ran the full
  suite fresh — originally reproduced the claimed **154/154**
  independently. This review's own adversarial pass (Workstream 4, below)
  then found **4 real, credible defects** (not present in the original
  claim's test count, since the original tests didn't cover these gaps).
  Each was demonstrated failing before being fixed; **this PR has been
  updated in place** (commit `d89956c`) — now **160/160 PASS**, fresh
  run this session, evidence at `docs/evidence/core-v2/ADVERSARIAL_REVIEW_FIXES.md`.
- **Result before this review**: NEEDS_FIX (4 real defects found).
  **Result after this review's fix**: **READY_TO_MERGE**.

## PR #20 — BloomBoss/Voice-Media/Finance readiness specs, dependency graph, consolidated Core v2 spec

- **Purpose**: Workstreams 9–12, 15 of the Core v2 Engineering Blueprint
  Program.
- **Scope check**: matches — docs-only, 6 files.
- **Defect found and fixed this session**: two stale "154 prototype tests
  pass" references (in `KARMO_CORE_V2_SPECIFICATION.md` and
  `specs/002-core-v2-platform/spec.md`), now stale after PR #19's fix
  count grew to 160. **Updated in place** (commit `05f1394`).
- **Result**: **READY_TO_MERGE** (after this session's fix).

## PR #21 — PROJECT SAVE for Core v2 Engineering Blueprint Program

- **Purpose**: reconcile `docs/project-state/` for PRs #18–#20.
- **Scope check**: matches — 3 `docs/project-state/` files.
- **Defects found and fixed this session**: same stale "154" references
  (4 occurrences across `CHANGE_LOG.md`, `CURRENT_STATE.md`,
  `NEXT_STEPS.md`) plus a traceability note added for the adversarial
  fixes. **Updated in place** (commit `814aee5`).
- **Cross-PR conflict with PR #17**: confirmed (see #17's entry above and
  "Cross-PR Conflict Analysis" below).
- **Result**: **READY_WITH_NONBLOCKING_NOTES** (after this session's
  fixes) — same conflict-at-merge-time caveat as #17.

## Cross-PR Conflict Analysis

Simulated merging all 8 branches locally, in dependency order, on a
scratch branch (never pushed, never touching any actual GitHub PR).

- **#14, #15, #16 → clean, no conflicts** (fast-forward or trivial merge).
- **#17 → clean** on top of #14–#16 (no file overlap).
- **#18, #19, #20 → clean** on top of #14–#17 (no file overlap with
  anything in the first program or each other).
- **#21 → CONFLICTS** with #17's changes to `docs/project-state/CHANGE_LOG.md`,
  `CURRENT_STATE.md`, and `NEXT_STEPS.md` — both PRs independently
  rewrote overlapping narrative sections (top-line summary, "next steps"
  lists) starting from the same pre-#17 `main`, each unaware of the
  other. Confirmed with real `git merge` (not merely predicted): 3 files,
  8 total conflict hunks.

**No other file-level overlap exists between any pair of the 8 PRs** —
every other cross-PR reference (Spec Kit files, governance references,
architecture/spec references, test paths, evidence manifests,
documentation indexes) was checked and found consistent, with the two
stale-count exceptions already fixed above.

**Resolution guidance** (not performed by this review — no merges were
executed): merge #17 before #21, in the recommended sequence below.
When #21 is merged second, GitHub (or a local rebase) will show the
conflict in the 3 shared files; resolve by keeping both programs' facts
— #17's "Post-Foundation Overnight Readiness Program" section and #21's
"Core v2 Engineering Blueprint Program" section are additive and do not
actually contradict each other in substance, only in which one currently
appears "last" in each file's chronological narrative. This is a normal,
low-risk, one-time manual resolution for two sequential documentation
PRs — not a sign of a defect in either.

## Merge Order Recommendation

See `docs/evidence/autonomous-review/MERGE_SEQUENCE.md` for the exact
sequence and reasoning.
