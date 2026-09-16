# KARMO Next Steps

## 2026-09-15 update (read this first)

**2026-09-11 through 2026-09-15 is now fully reconciled** into
`CURRENT_STATE.md` — see its "2026-09-11 through 2026-09-14 — Access
rollout, Core/Worker productionization, dual-worker Commander, model
stack" and "Durable Memory Core integration" sections. Covers: Tailscale
enrollment, Core v2 + Worker Runtime productionized and deployed to
`karmo-ai01` (PRs #33–#35), durable worker coordination hardening (PR
#41), the local open model stack (`qwen3:8b`/`ministral-3:8b`/
`mistral:7b`/`granite3.3:2b`, PR #45), Worker01 + Worker02 activation,
dual-worker Commander READ Pack activation (PR #47) with its
`karmo_gateway` grant repair, and durable memory in Core chat (PR
#48/#49). Everything below this point (Foundation v1 through Worker
Runtime v0.1 merge closeout) remains historical context from
2026-09-09/10 and is unaffected.

### 2026-09-15 (later same day) — PR #43 merged

**PR #43 has been reconciled and merged** (`f2ba1a49ebe8baf664a93cf59dc74693506db42a`) —
no longer an open decision. Its full 12+ iterations (approval
authority-binding fix, `ModelRouter`/`ModelResource` validation and hard
policy gates, KarmoLab wired through the registry/dispatcher, verifier
exact-match strictness, durable recovery preflight validation, terminal
invocation status allowlisting, worker document-size cap) are now part
of `main`, independently security-reviewed (no HIGH/MEDIUM findings) and
test-verified (148/111/161/2 passing across all four suites). Three
merge conflicts resolved by hand (`model_router.py`, `operator.py`,
`capabilities.py`) — see `docs/project-state/KARMO_DEVELOPER_NOTES.md`
for the full reconciliation narrative, including the explicit policy
decision to keep chat's 3-way model fallback rather than let the new
trust floor silently narrow it to 2-way.

**Deployed and canary-verified the same day** (`de16b6e959a0ccec30444abea6b1005f6cccd101`).
The deployment canary surfaced a real, separate pre-existing bug in the
keyword dispatch regexes (17 combined false positives against ordinary
English, e.g. "deploy" inside a canary phrase getting refused as a
write-intent request) — fixed systematically in PR #57
(`fbaf42752e7a4a124379778b9c7a3ea55fdc62c4`), also deployed and
re-verified same day. No open item remains for this workstream.

### 2026-09-15/16 — BloomBoss Phase 1 (PR #32) reconciled and MERGED

**PR #56 supersedes PR #32** — reconciled against current `main`, a
second time to catch up with the concurrently-merged PR #43/#57/#58 work
(one further conflict, in `KARMO_DASHBOARD.md` only, resolved in favor of
the more current side), then re-verified: 183 core-service tests, 62
BloomBoss tests, 111 worker-runtime tests, 161 core-v2-prototypes tests,
2 worker-service tests, all pass. **Merged into `main`**
(`e8cda4f9c755d1d2cdd302c3c7cc7f0e8439e8fd`) on Kamara's explicit
merge/promotion decision, given via an approved plan in this session.
`bloomboss/` now exists on `main`. Still isolated/dev-only per the build
plan's own first-implementation boundary: **no production deployment, no
marketplace writes, no customer actions** — those remain future,
separately-scoped decisions (see `docs/plans/BLOOMBOSS_BUILD_PLAN.md`
Phases 2-7).

This merge also closed a real risk: two sessions had been working on
KARMO concurrently and independently on 2026-09-15/16 (this session and
another), including two divergent fixes for the same `operator.py`
keyword-dispatch bug. The broader, better-tested fix (PR #57, already
merged separately) is what's actually deployed on `karmo-ai01` — verified
directly on the host, not assumed from git history.

### 2026-09-16 — "working with KARMO directly" (all 4 access options) CLOSED

`core_service.webui` (PR #60, loopback-only; PR #61, added an explicit
Tailscale-interface bind mode on Kamara's choice) is deployed to
`karmo-ai01`, running in `tailscale` mode, verified reachable at
`http://100.75.239.44:8787` with a live chat round-trip returning
`memory_status: ACTIVE`. `karmo-chat`/`karmo-web` shell helpers added on
KARMO-DEV01. All 4 items from this session's approved plan (finish the
canary, Mac-side access without manual SSH, a nicer browser interface,
mobile/remote reach) are done — see "KARMO webui" section in
`CURRENT_STATE.md` for full detail.

### 2026-09-16 — KARMO orchestration task board (PR #63) deployed

First KARMO↔Claude/GPT collaboration slice: 4 tools
(`create_task`/`list_tasks`/`claim_task`/`complete_task`) registered on
the already-implemented Tool/Capability Registry (correcting a stale
"design only" claim elsewhere in this doc's history — see "KARMO
orchestration task board" in `CURRENT_STATE.md`). Deliberately not
automated model dispatch — no API keys, no per-token billing, a human or
human-operated Claude/ChatGPT session reads/completes tasks via
`python3 -m core_service task ...`. Deployed and canary-verified on
`karmo-ai01`, including both negative-path guards. **Not yet used for a
real piece of work** — only a synthetic canary task so far.

### 2026-09-16 — Worker01/Worker02 model activation (closes the 2026-09-13 checkpoint gap)

Both workers now run a `karmo-ollama` Docker container (matching
`karmo-ai01`'s exact pattern) hosting the same 4 models Core actually
uses (`qwen3:8b`, `ministral-3:8b`, `mistral:7b`, `granite3.3:2b`),
digest-identical to `karmo-ai01`'s copies, functionally smoke-tested on
both, loopback-only. See "Worker model activation" in `CURRENT_STATE.md`
for the full record, including the access-path note (LAN-only, `karmo`
admin account, reached via SSH agent forwarding through `karmo-ai01`)
and the explicit correction to the 2026-09-13 checkpoint's stale
Qwen+DeepSeek+Gemini+Mistral target. **Core is not wired to use these
yet** — that's a new, deliberately-scoped capability (not started).

### Items requiring Kamara's decision (current, as of 2026-09-16)

1. ~~**PR #56** (BloomBoss Phase 1)~~ — **merged**, `e8cda4f9`.
2. **Spot-check BloomBoss Phase 1's analytics output** against 2-3 known
   real purchases/sales, before trusting it further — not yet done. Now
   also a natural candidate for the first *real* orchestration task once
   Kamara provides the data.
3. **PR #26** (learning program branch) — untouched, predates current
   `main` by a wide margin per `AI_START_HERE.md`'s own caution; reconcile
   before any merge attempt.
4. **Choose the next KARMO capability** to build now that durable memory,
   BloomBoss Phase 1, and the orchestration task board are all live —
   BloomBoss Phase 2+ (marketplace research), further Worker Commander
   capabilities (`bounded_text_read`/`directory_list`, currently
   fail-closed pending `allowed_root` design), a report-only registry
   auditor (reconciling `tool_registry` against actual invocations,
   matching `h04/app/auditor.py`'s pattern — recommended before the
   registry carries much more than 5 tools), or something else.
5. Two small non-blocking housekeeping items from the 2026-09-14/15
   sessions: `llama3.2:3b`/`qwen3:4b` remain installed on AI01 but
   inactive (deferred cleanup decision); two
   `/opt/karmo/core-service.bak.*` trees from the durable-memory
   redeploy remain on AI01 (harmless, uncleaned).
6. **Design worker-hosted model inference routing** — Worker01/Worker02
   now have real model capacity (see 2026-09-16 entry above) but Core's
   `OllamaChatClient` is deliberately loopback-only and refuses remote
   endpoints (PR #37's stated security boundary). Actually using the
   workers' models means a new capability, not a config toggle — most
   likely routed through the existing Worker Runtime job/ticket/approval
   path (the same pattern Commander already uses), not by relaxing the
   Ollama client's existing refusal. Needs its own System-Fit Review and
   Invariant Impact Review before any implementation.

---

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
#14–#25 have all merged into `main`** via the approved KARMO merge
sequence (PR #22 at commit `4877aa967805bf540af0cc5645b2c82024ab11c9`, PR
#23 at commit `11d4f86e04d22aae0072923ec387a11f0e205cbc`, PR #24 at commit
`9f3215ecd3be31d2096273be4afb389edbcbf9f8`, PR #25 at commit
`b95acb603e632855298cc0d454df00b2c3d22286`) — see "Worker Runtime v0.1
final merged-main closeout" in `CURRENT_STATE.md`. **This merge-closeout
thread is now complete — every PR from the Foundation-through-Worker-
Runtime sequence is merged, decided, and closed.**

The primary next action is now **a future user decision on the next
engineering capability** (see item 11 below) — there is no outstanding
foundation-blocking work, no PR left to merge or reject, and nothing
requires an urgent response. Per explicit direction: **infrastructure
churn stops here.** Focus moves to the KARMO AI / Agent Engineering
Learning Program and other directly useful capability work, unless
Kamara explicitly chooses to open a new engineering track.

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

### From the Worker Runtime v0.1 workload (MERGED)
10. ~~Merge/reject PR #25~~ (`worker-runtime/evidence`: evidence package +
    PROJECT SAVE) — **merged** into `main` at commit `b95acb603e632855298cc0d454df00b2c3d22286`.
    PR #23 (implementation + tests, commit `11d4f86e`) and PR #24
    (architecture/security/network docs, commit `9f3215ec`) are also
    merged. All merged into the source tree, **not** deployed or
    connected to production. Final merged-main verification (2026-09-10):
    **68/68** worker-runtime tests, **161/161** core-v2-prototypes
    regression — see `docs/evidence/worker-runtime/RUN_SUMMARY.json` and
    "Worker Runtime v0.1 final merged-main closeout" in `CURRENT_STATE.md`.

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
- Worker Runtime v0.1 — implementation + tests (PR #23, commit
  `11d4f86e`), architecture/security/network docs (PR #24, commit
  `9f3215ec`), and evidence + PROJECT SAVE (PR #25, commit `b95acb6`) —
  **all merged** into `main`, **not deployed, not connected to
  production**. Final merged-main verification (2026-09-10): 68/68
  worker-runtime tests, 161/161 core-v2-prototypes regression. This
  closes the entire Worker Runtime v0.1 merge-closeout thread — no item
  remains open in this workload.
- `SOFTWARE_INVENTORY.md`/`NETWORK_INVENTORY.md` current counts —
  reconfirmed during the 2026-09-09 Workload 2 closeout; no further
  action required (routine update from existing evidence deferred, not
  blocking).

## Not next steps (explicitly out of scope, unchanged)

- No production access occurred in either program tonight — zero SSH,
  zero database/Qdrant/container/credential/log/network access.
- No PR was merged *during* either program's own run (PRs #14–#21 were
  all opened, none merged, at that time) — historical, describing that
  night's activity only. PRs #14–#25 have since merged via the separate,
  later approved KARMO merge sequence; see "Completed, no further
  action" above.
- No governance was modified by either program.
- No Voice/Media/BloomBoss/KarmoLab/Personal-Productivity/Finance
  capability was implemented or started.
- No first-capability scope was chosen on Natalie's behalf.
