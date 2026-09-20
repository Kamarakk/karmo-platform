# KARMO — Whole-Project Working Todo List

Covers: every open, undecided, or not-yet-built item across the entire
KARMO project as of 2026-09-20, pulled from `NEXT_STEPS.md`,
`CURRENT_STATE.md`, and today's session — organized by area, not by
date, so it can be worked from directly.
Read this if: planning what to work on next, or handing the whole
project state to GPT for review.
Status: LIVING DOCUMENT — update in place as items close; do not let
this drift the way `NEXT_STEPS.md` did before (see the 2026-09-18
`MASTER_INDEX.md` governance fix). Each item lists its current status
and what would need to happen next.

---

## A. Model Router (KARMO-FIRST Orchestration / SIEL)

| Phase | Status | Next action |
|---|---|---|
| A — host health signals | Partial (Ollama probing only; memory/CPU headroom, queue depth not built) | Not urgent — no consumer needs the missing signals yet |
| B — capability-typed fallback | Live in production | None |
| C — shadow routing (decision-only) | Live in production | None |
| D1 — worker transport proof | Proven live end-to-end (real bug found + fixed: missing DB grant, migration 009) | None |
| D2 — live worker chat routing | Built, reviewed twice, merged **dormant** (activation DSN not created) | On hold — see item 6 in the recommendations doc. Needs: dedicated dispatch credential (not reused gateway role), a retention policy for worker-stored chat content, a fix for the check-then-act worker-selection race, and a real local-vs-worker speed benchmark before reconsidering activation |
| E — decision audit | Built, merged, deployed (migration 010 had to be applied live — found undeployed despite code being live) | None |
| Circuit breaker | Built, merged, **not wired into real routing decisions yet** | Needs wiring into whichever routing path is actually reactivated (D2 or a future replacement) |
| F — idempotency + write-capability support | Not started | No scope defined yet |

## B. Local chat performance (current, real hardware)

- **Selective tool-offering** (PR #106) — DONE, live, verified: only offers a tool's schema when the message matches that tool's trigger keywords, cutting `qwen3:8b`'s effective prompt inflation on tool-free turns.
- **Trivial-message short-circuit** — DONE (built 2026-09-20, see PR opened same day): a pure greeting or acknowledgment (full-message match only, never substring) now returns a canned reply without calling the model at all, skipping the ~6.2GB/~30-40s model-load cost entirely for that class of message. 6 new tests, full suite 356 passed.
- **`num_predict=96` response cap** — DONE (2026-09-20): made a configurable constructor default on `OllamaChatClient` instead of a hardcoded literal; value itself unchanged (still 96), just no longer requires editing `ollama_client.py` to tune. Deployed.
- **External-LLM answer caching** (`ask_claude`/`ask_gpt`) — DONE (2026-09-20): exact-match, in-memory, 1-hour TTL cache (`delegation_cache.py`), only successful text answers are ever cached. Deployed.
- **`TOTAL_CHAT_DEADLINE_SECONDS=300.0`** — accepted trade-off, not a target state; revisit only if hardware changes the underlying token-processing speed (~22 tok/s prompt, ~3.5-4 tok/s generation, both CPU-only, no GPU anywhere in the fleet).

## C. BloomBoss

- Phase 1 (analytics engine) — **live, trustworthy**, spot-checked against real EMgarden invoice + 10 real sales, zero unexplained discrepancies.
- Chat integration bugs (model tool-choice, deadline sizing, tool-result size, tool-schema token inflation) — **all four found and fixed live tonight** (PRs #102-#106), confirmed working with a real successful chat answer.
- Phase 2+ (marketplace research, Palmstreet findings) — **not started**. Scoped in `docs/plans/BLOOMBOSS_BUILD_PLAN.md`, no phase authorized.

## D. Hardware / infrastructure

- **KVE01/KVE02/KVE03 topology** — fully verified live 2026-09-19/20 (PR #100): identical spec hosts (i7-10700, 8c/16t, 15GiB RAM, Intel UHD 630 iGPU, ~477GB NVMe), all near-full RAM, no GPU acceleration anywhere. `karmo-ai01` itself is VM100 on KVE02 (previously undocumented as virtualized) — confirmed to run with only 7.8GB allocated to it, not the full host's 15GB.
- **VM resource allocation ("use all 3 VMs to their max")** — raised, not yet decided or built. No plan exists for reallocating VM memory/CPU shares across KVE01/02/03.
- **Mini-helper-models-on-dedicated-workers architecture** — discussed extensively, NOT decided. See recommendations doc item 4 for tonight's new RAM evidence bearing directly on this.
- **Voice/video accessibility** — zero capability exists, not started. Scoped in `docs/plans/KARMO_VOICE_VISION_EARS_ROADMAP.md`. **Standing constraint, Kamara's explicit decision (2026-09-20)**: `ask_claude`/`ask_gpt` must never be extended beyond plain text Q&A — an image-input extension was built, then explicitly rejected and fully reverted the same day. Eyes/ears/voice must all be built on KARMO's own local infrastructure; eyes specifically is now blocked on a real local-vision-model evaluation or a hardware decision, neither started.

## E. Housekeeping / long-standing cleanup (not urgent, still open)

- `core-v2-prototypes/` vs `worker-service/` coupling and stale README claim (found 2026-09-17, never resolved): decide whether to extract the shared `approval_engine`/`job_model`/`tool_registry` code into a real non-prototype package, whether `worker-service/` should be finished/merged/deleted, and fix the now-false "nothing in this directory is wired into production" claim. Any deletion goes through the standing deletion-approval gate (list candidates individually, Kamara approves each).
- Worker heartbeat renewed only once per loop iteration, before `poll_once()` runs — a long enough capability call could let a worker's own heartbeat lease expire mid-submission. Found 2026-09-19, not fixed.
- `llama3.2:3b`/`qwen3:4b` — confirmed already removed from `karmo-ai01`'s Ollama install (moot, no action needed).
- Two ambiguous legacy document hashes (`karmo-v05-new.html`) — intentionally left unresolved pending a human decision on version ordering. Do not resolve without that explicit decision.
- Report-only registry auditor (reconciling `tool_registry` against actual invocations) — recommended, never started, worth doing before the registry grows past its current ~5 tools.

## F. Open questions needing Kamara's input specifically

1. **"There are more LLMs outside Ollama"** — flagged tonight, unresolved. Need to know what's being referred to beyond `ask_claude`/`ask_gpt` before it can be verified.
2. **Next KARMO capability choice** — durable memory, BloomBoss Phase 1, and the orchestration task board are all live; no new capability track has been chosen (BloomBoss Phase 2, further Worker Commander capabilities like `bounded_text_read`/`directory_list`, or something else).
3. **VM resource reallocation** — decide whether/how to shift RAM/CPU shares across KVE01/02/03 to give any single VM more headroom.
4. **Voice/video/chat scope and timeline** — roadmap now exists (`docs/plans/KARMO_VOICE_VISION_EARS_ROADMAP.md`); still needs Kamara's decision on the client surface (where she'll actually talk to KARMO from) before picking specific STT/TTS engines, per that doc's "What a fresh session should do first" section.

---

*This file is meant to be updated in place, not superseded by a new
dated file each session, per the governance fix that caused
`NEXT_STEPS.md` to go stale before (see `MASTER_INDEX.md`'s Mandatory
Document Labeling Rule).*
