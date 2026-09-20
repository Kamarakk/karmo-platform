# KARMO — Full Outstanding Plan, for Independent Review Before Any Further Build

**Covers:** every open thread from tonight's session in one place — confirmed current state, real hardware constraints, known unresolved issues, and every strategic decision still open — written so it can be reviewed and adjusted by GPT/Kamara as a whole plan, then executed as one complete build rather than negotiated step by step in chat.
**Read this if:** you're deciding what KARMO should actually do next, in what order, and want the full picture in one place instead of scattered across a long conversation.
**Status:** planning document, 2026-09-19. Nothing in Section 4/5 is authorized to build yet — this is the plan to review and adjust first.

---

## 0. Why this document exists

Kamara's own words: too much back-and-forth, too many small decisions negotiated one at a time in chat, wants one complete plan reviewed by GPT and adjusted before any more building happens, then a single complete build pass instead of incremental chat-driven changes. This document is that — everything outstanding, in one place, honestly scoped, with the real open decisions named explicitly rather than buried in conversation history.

---

## 1. Confirmed current state (what's actually true right now)

**Deployed and live, working today:**
- Chat runs on `karmo-ai01`, with capability-typed fallback (Model Router Phases A/B/C) — a chat request can no longer silently fall through to a non-tool-capable model and give a confident wrong answer (the real incident this session's router work started from).
- Durable conversation memory (Postgres + Qdrant) is deployed and working — KARMO does retain conversation history across sessions.
- `bloomboss_report` is a registered, working chat tool — **but see Section 3.1: a real deployment gap was found tonight that likely explains "KARMO doesn't know about BloomBoss."**

**Built, tested, and merged, but deliberately dormant (zero effect on live chat):**
- Phase D1 (worker tool-calling proof): proven successful once, live, on Worker01 — a worker *can* serve a real chat round trip. Not wired into real traffic.
- Phase E (decision audit), a circuit breaker, and Phase D2 (live worker routing): all built, tested, merged as PR #97/#93/#94. **Deliberately held inactive** after two independent external reviews found real gaps (credential over-privilege, worker tables becoming an undeclared chat-content store, a check-then-act race, and — most importantly — no proven speed benefit was ever measured). The activating credential file does not exist in production; nothing here can affect live chat unless that file is deliberately created later.

**Full detail, if wanted:** `docs/project-state/CURRENT_STATE.md`'s 2026-09-19 entries; the two GPT review docs (`KARMO_D2_TECHNICAL_REVIEW_FOR_CLAUDE_2026-09-19.md`, `KARMO_D2_REVIEW_FOR_NATALIE_2026-09-19.md`).

---

## 2. Real hardware, confirmed live tonight (not assumed)

Three physical machines, **identical**: Intel i7-10700 (8 cores/16 threads, 2.9-4.8 GHz), **15 GiB RAM each**, Intel UHD 630 integrated graphics (no real LLM acceleration value on any of them — no CUDA/ROCm path), ~477 GB NVMe disk.

| Physical host | VM | Role | RAM used / 15 GiB |
|---|---|---|---|
| KVE01 | VM 101 | Worker01 | 11 GiB used, ~265 MB free |
| KVE02 | VM 100 | **karmo-ai01** (Postgres + Qdrant + core-service + Ollama, all together) | 10 GiB used, ~1.3 GB free |
| KVE03 | VM 102 | Worker02 | 11 GiB used, ~362 MB free |

**All three hosts are already using nearly all their RAM. There is no idle physical capacity anywhere in this cluster** — no hidden machine, no unused host. Getting real headroom back requires adding physical RAM to one of these boxes; it isn't a configuration change.

There is a fourth machine in the picture — KARMO-DEV01 (a MacBook Pro M3, 8 GB RAM) — but that's Kamara's own active daily-use laptop (the one this conversation runs on). It should not be used to host a standing model workload; doing so would compete with her own interactive use of her own computer.

**Not yet checked**: the actual per-process memory breakdown on `karmo-ai01` (how much Postgres/Qdrant/core-service individually cost vs. the model itself) — requested but never returned before the conversation moved on. This number matters for any decision about relocating services off `karmo-ai01`.

---

## 3. Known, concrete issues

### 3.1 BloomBoss data was likely never deployed to production (found tonight, fix given, not yet confirmed applied)

Root cause, confirmed by reading the code: `bloomboss_capability.py`'s handler reads historical CSV data from a path computed as `<repo root>/docs/bloomboss/historical_data/` — on production that's `/opt/karmo/docs/bloomboss/historical_data/`. **Every deploy command run this entire session only ever copied `core-service/` and `worker-runtime/` to production, never the top-level `docs/` folder.** The real data (`docs/bloomboss/historical_data/emgarden_invoice_2026040040.csv`) is committed in the repo but was very likely never copied to `/opt/karmo/docs/...` on `karmo-ai01` at all. When the tool is called, it raises an error, the model gets that error back, and (accurately, if unhelpfully) tells Kamara it doesn't have access.

**Fix given, not yet confirmed run**: copy `docs/bloomboss/historical_data/*.csv` to `/opt/karmo/docs/bloomboss/historical_data/` on `karmo-ai01`. No code change, no service restart needed (the handler reads the directory fresh on every call). **This should be the very first thing confirmed/finished before anything else** — it's the one concrete, already-diagnosed, low-risk fix sitting incomplete right now.

### 3.2 The D2 speed premise was never actually tested

Real load numbers exist for a worker under contention (20.1s / 32.1s / 44.1s for 1st/2nd/3rd concurrent request), but **no one ever measured local `karmo-ai01` latency for the same prompts to compare against.** The entire justification for distributed routing (relieving `karmo-ai01` contention) was never verified against evidence that the contention is actually costing anything. This is why D2 activation was held, not just the credential/storage concerns.

---

## 4. Strategic decisions still open (need a real answer, not another back-and-forth)

### 4.1 D2 / distributed routing: pursue the remediation, or stay local-only?

Two independent reviews and Kamara's own decision tonight landed on: hold activation, stay local-only for chat, keep the dormant code as a preserved foundation. **This is already decided** — flagging it here only so GPT can confirm it agrees with the reasoning (Section 5/6 of `docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md`, and the two D2 review docs) rather than re-opening it.

### 4.2 "One brain + narrow mini-helper models on the workers" — worth pursuing, but real hardware limits apply

Kamara's own idea: a small, general "brain" model (no video/voice/coding/security capability baked in) handling ordinary chat, with separate small specialist models (coding help, voice transcription, etc.) invoked as tools only when needed, physically placed on Worker01/Worker02.

**What's real about this idea**: reusing the *already-built* D1/D2 worker-dispatch machinery for *occasional* specialist tool calls (not every chat turn) is a much better fit than routing the brain itself — the per-call SSH/queue overhead matters far less when it's rare, and a dedicated worker with no contention is a genuine win for a heavier specialist model.

**What's constrained by real hardware** (Section 2): there's no free RAM to add a specialist model to a worker beyond what fits in that worker's already-tight 15 GiB host. Concretely, on a 10-11 GiB-committed 15 GiB host, there's realistically only a few hundred MB to ~1-2 GB of slack per worker today — not room for a large specialist model without something else shrinking first, or without confirming the exact current Ollama model footprint on each worker (not yet checked).

**Open, needs a decision**: which specialist (if any) to build first, and whether it fits in the real remaining headroom on Worker01/Worker02 as they stand today.

### 4.3 Voice, video, and chat accessibility, "day one"

**Current state: zero voice or video capability exists anywhere in KARMO today.** Everything built this entire session is text chat only. This was flagged honestly rather than estimated — "day one" is not achievable for a feature that doesn't exist yet in any form; Kamara has not yet clarified what "day one" actually means (day one of starting this build, vs. an expectation it's already close). **This needs a real scope conversation, not an assumption, before any plan can include it.** At minimum, a real voice/video build needs: a chosen speech-to-text model (e.g. Whisper, which is not Ollama-hosted and needs its own runtime), a chosen text-to-speech path, new I/O plumbing in whatever KARMO surfaces chat through today, and a decision about whether voice/video runs locally or needs a specialist worker.

---

## 5. What a "complete build pass" would need, if executed at once

If the intent is genuinely "review this plan, adjust it, then have Claude execute the whole thing in one pass," here is what needs to be true before that's realistic:

1. **Section 3.1 (BloomBoss deploy gap) confirmed fixed** — small, already scoped, should not wait on anything else.
2. **Section 2's missing number** (per-process RAM breakdown on `karmo-ai01`) obtained, so any decision about relocating Postgres/Qdrant/core-service is evidence-based, not guessed.
3. **A firm answer on 4.2**: which specialist model (if any), targeting which worker, confirmed to actually fit in that worker's real remaining headroom.
4. **A firm scope and timeline answer on 4.3** (voice/video) — this is likely the largest single piece of new work in this entire document and deserves to be scoped as its own project, not folded into "the same pass" as everything else, unless Kamara wants a much longer single build than the other items imply.
5. Confirmation that 4.1 (stay local-only, D2 dormant) is accepted as-is, not to be revisited in the same pass.

**Honest caution, not a refusal**: items 1-2 above are small and could genuinely be done in one clean pass. Item 4 (voice/video) is not the same size as the rest of this document — bundling it into "the same build" as everything else risks exactly the kind of rushed, under-scoped work that caused problems earlier tonight (the D2 activation that two independent reviews had to walk back). If GPT agrees, it's worth explicitly splitting item 4 into its own separately-scoped follow-up rather than one pass covering everything.

---

## 6. Standing rules any build must operate inside (for GPT's awareness, not up for renegotiation here)

- Production access (SSH, databases, credentials) requires Kamara's explicit, task-specific authorization each time — never assumed from a prior approval.
- No PR gets merged without Kamara's explicit "merge it" instruction, no exceptions.
- No deletion of KARMO infrastructure without reading the whole plan and approving deletions individually first.
- Every non-trivial change goes through the project's own Invariant Impact Review and System-Fit Review before being built.
- Real evidence over assumption, throughout — this document itself follows that rule (Section 3.2's honest gap, Section 2's real measured numbers, Section 4.3's honest "doesn't exist yet" instead of a hopeful estimate).
