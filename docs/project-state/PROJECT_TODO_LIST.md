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

## Working sections (2026-09-23), toward Kamara actually using KARMO

Grouped for review-as-you-go, in the order that unlocks real use fastest.

1. **Wire local capabilities into chat — DONE, nothing left.** Only
   `ask_local_coder` fits this pattern (plain text); already wired, PR
   #118. Vision/ears/voice are architecturally *not* wireable this way —
   a text model cannot invent real image/audio bytes as a tool-call
   argument. Corrected 2026-09-23; do not re-attempt this as a task.
2. **Browser client surface — DONE.** Mic-record, image-upload+question,
   and a "speak replies" toggle added to the webui, all routed through
   `KarmoOperator.dispatch_vision()`/`dispatch_transcribe()`/
   `dispatch_speak()` (same `CapabilityDispatcher`/`ApprovalEngine`
   authority path as every other capability, deliberately still not
   `_CHAT_EXPOSED_TOOLS`). PR #120, merged 2026-09-23.
3. **Phone access surface — DONE (code).** Real blocker found: browsers
   refuse `getUserMedia()` (mic/camera) on any non-localhost origin
   without HTTPS, which the plain `tailscale` bind mode is — a phone
   could load the page but not use the mic. Added a `tailscale-https`
   bind mode: resolves this host's own tailnet DNS name
   (`tailscale status --json`) and provisions a real cert via
   `tailscale cert` (Tailscale's own Let's Encrypt-backed service),
   serving over TLS. Also fixed a real mobile bug: the page had no
   viewport meta tag, so phones rendered it desktop-width. **Not yet
   run in production** — needs its own Production Access Authorization
   (creates `/etc/karmo/core/tailscale-tls/`, runs `tailscale cert`,
   restarts the webui in the new mode) before a phone can actually use
   it.
   **LIVE, 2026-09-27.** Kamara enabled HTTPS certificates in the
   tailnet and the webui runs as `webui tailscale-https` on karmo-ai01
   (https://karmo-ai01.tail2d74d7.ts.net:8787; plain-HTTP address no
   longer served; no Serve/Funnel). Still a manual process, not
   systemd -- does not survive a reboot. Phone test then showed voice
   notes rejected by the 48 KiB worker-link argument bound; fix
   (fetch large arguments in pieces, shrink photos/voice in the
   browser) is on branch `claude/project-thread-lm83cs`.
   **DEPLOYED + live-verified 2026-09-27**: karmo-ai01 (backup
   `/opt/karmo/backups/chunks-deploy-20260927T023436Z`) and Worker01
   (backup `chunks-deploy-20260927T023244Z`). Also found and fixed:
   Worker01 was never registered for `vision_describe`/
   `transcribe_audio`/`synthesize_speech` (added to
   `/etc/karmo/worker01.json`, backup `worker01.json.before-media-*`,
   plus `store.update_capabilities`, after `recover_expired_leases()`
   parked 4 dead LEASED chat jobs as RECOVERY_REQUIRED); and the
   service's hardening blocked the tools, fixed with drop-in
   `/etc/systemd/system/karmo-worker01.service.d/10-read-home.conf`
   (`ProtectHome=read-only`, `MemoryDenyWriteExecute=false`, both
   approved by Kamara). Proven: 124 KB voice note transcribed, 280 KB
   photo described, over HTTPS. **Still open**: speak replies longer
   than ~1 second fail (result frame > 64 KiB, same problem in the
   result direction); Worker02 not updated; branch not yet merged.
   **Fix built 2026-09-29, not deployed** (branch
   `claude/project-thread-3jzfd7`): large results uploaded in pieces
   (`upload_result_piece`, migration 012); /speak deadline scales with
   text length. Deploy: migration 012 + Core on karmo-ai01, then
   Worker01; live-verify a multi-sentence spoken reply.
   **DONE, 2026-09-24, fully live-verified.** `karmo_core_dispatch`
   role + `/etc/karmo/core/worker-dispatch.dsn` provisioned; `core-service`
   redeployed to `karmo-ai01` (was up to 4 days stale, missing
   migration 011 and everything since PR #118). Two real bugs found
   and fixed live: a `psql` dollar-quoting interpolation bug that
   silently left the role's password unset (fixed with a plain
   top-level `CREATE ROLE`/`ALTER ROLE` pair), and a truncated `scp`
   transfer that produced a 0-byte tarball on the remote end (caught by
   explicitly checking the remote file's size, not trusting a clean
   exit code). Final state confirmed, not assumed: dispatch-client
   auth check `available: True` / `auth check: OK` against the
   redeployed code; `systemctl status` `active (running)`, clean
   startup, 14+ minutes stable; `ss -H -lntu` unchanged baseline (no
   new listener). Full execution log:
   `docs/runbooks/CORE_DISPATCH_ROLE_AND_DEPLOY_20260924.md`.
   **Next action**: reconfirm Worker01's own vision/ears/voice/
   coding-helper capability config is still registered (proven during
   PR #117's build, never reconfirmed since), and live-test
   `ask_local_coder` from real chat (needs no client surface).
4. **Router/reliability cleanup — CLOSED, nothing to build.** Checked
   the actual code (2026-09-24) before starting: the circuit breaker is
   already wired into live routing (`live_router.py`'s
   `compute_live_routing_decision(breaker_states=...)`, consulted by
   `operator.py`'s `_compute_live_decision()`; the mutating
   `allow_request()`/`record_result()` calls happen at the real
   dispatch site) — done as part of D2, PR #97. This doc's own earlier
   "not wired into real routing decisions yet" line was written before
   PR #97 landed and was never corrected — the same doc-lag pattern
   flagged elsewhere in this project. The remaining Phase A signals
   (memory/CPU headroom, queue depth) still don't exist, but per this
   doc's own note below (Section A table) have no consumer and are
   explicitly not urgent — building them now would be exactly the
   "new infrastructure because it's technically interesting" pattern
   this project's governance says to avoid. Not scheduled.

Reminder for all of 2-4: the underlying capabilities remain inert in
production until the worker-dispatch DSN is created and
`karmo_core_dispatch` is provisioned (Section A above) — code can be
completed and reviewed before that production step, but won't be
live until it happens.

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
| Circuit breaker | **Wired into live routing** (`live_router.py`/`operator.py`, part of D2/PR #97) — corrected 2026-09-24, this row was stale | None |
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

- **KVE01/KVE02/KVE03 topology** — fully verified live 2026-09-19/20 (PR #100): identical spec hosts (i7-10700, 8c/16t, 15GiB RAM, Intel UHD 630 iGPU, ~477GB NVMe), no GPU acceleration anywhere. `karmo-ai01` itself is VM100 on KVE02, 7.8GB RAM allocated. **Worker01/Worker02 have 9.7GB each**, confirmed live 2026-09-20 — more headroom than the brain machine itself, and near-idle (~9.1GB free) since D2 routing is dormant. This is why local eyes/ears/voice/coding-helper all live on the workers, not `karmo-ai01` (see below).
- **Worker01/Worker02 model cleanup** — DONE (2026-09-20): `ministral-3:8b`/`granite3.3:2b` deleted from both (mirrors the `karmo-ai01` cleanup, PR #108), ~7GB freed each, `worker-runtime`'s allowed-model lists updated to match (PR #116). Both now run `qwen3:8b` + `mistral:7b`, same as `karmo-ai01`, plus the new local-capability models below.
- **Local eyes/coding-helper/ears/voice — all four built, tested, live-verified 2026-09-20** (PR #117, not yet merged — awaiting Kamara's go-ahead): see section G below for full detail. This directly answers the former "mini-helper-models-on-dedicated-workers architecture" question — it's built, not just discussed anymore.
- **VM resource allocation ("use all 3 VMs to their max")** — raised, not yet decided or built. No plan exists for reallocating VM memory/CPU shares across KVE01/02/03 beyond what's already used by the models above.

## G. Local eyes / coding-helper / ears / voice (2026-09-20)

Standing policy (Kamara, explicit, corrected once same session — see
`docs/plans/KARMO_VOICE_VISION_EARS_ROADMAP.md`'s standing-constraint
section for the full history): Claude/GPT may be an explicit, optional
supplementary tool for anything, but must never be the only/main source
of a KARMO capability. All four below are built entirely on KARMO's own
local infrastructure (Worker01/Worker02), zero Claude/GPT dependency.

| Item | Model/engine | Live-verified result | Status |
|---|---|---|---|
| Eyes | Moondream2 (Ollama) | 8.13s, ~1.3GB RAM, correct real-image description | Built + tested, PR #117 |
| Coding helper | qwen2.5-coder:7b (Ollama, via existing `model_chat`) | 45.05s, correct Fibonacci function | Built + tested, PR #117 |
| Ears | faster-whisper "small" (dedicated pip venv) | 3.05s, exact transcript match | Built + tested, PR #117 |
| Voice | Piper + en_US-amy-medium voice | real-time factor 0.042 | Built + tested, PR #117 |

Each has a worker-runtime capability + a Core-side dispatch glue module
(`vision_capability.py`, `code_assist_capability.py`,
`audio_transcribe_capability.py`, `speech_synthesize_capability.py`).

**Two things true of all four, not yet resolved:**
1. **Not wired into `_CHAT_EXPOSED_TOOLS`.** Vision/ears/voice genuinely
   can't be yet — no client surface (browser mic/speaker, phone) exists
   to capture/play audio or supply an image (Kamara's answer 2026-09-20:
   she wants all three surfaces — browser, phone, and mic/speaker — this
   is real client-side work, not started). The coding helper *could* be
   wired in today (plain text, no client-surface gap) but is held to the
   same gate for consistency.
2. **Not activated.** All four require `worker_dispatch_client.available`,
   which requires creating `/etc/karmo/core/worker-dispatch.dsn` —
   deliberately never done. **Real finding from tonight, not previously
   known**: that DSN file is a SHARED switch — creating it to activate
   any of these four would *also* silently re-enable Model Router Phase
   D2's own held-back chat-routing-to-worker path (two independent
   reviews found real gaps there: an over-privileged credential, no
   retention policy, a check-then-act race). Do not create that DSN file
   without either resolving D2's own concerns or decoupling the two
   switches first — documented in `vision_capability.py`'s module
   docstring.

**Item 5 of the original lineup (ethical-hacking / pentest lab) is
deliberately deferred to 2026-09-22, per Kamara's own instruction.**
Blocked on one question before any build starts: does an isolated lab
(Metasploitable/Juice Shop VM, separate network, no route to production
KARMO or the real home LAN) already exist, or does it need to be stood
up first? KARMO running Nmap/Metasploit for Kamara (her explicit
choice, confirmed 2026-09-20) needs that isolation to exist before a
target allowlist has anything real to allowlist.

## E. Housekeeping / long-standing cleanup (not urgent, still open)

- `core-v2-prototypes/` vs `worker-service/` coupling and stale README claim (found 2026-09-17, never resolved): decide whether to extract the shared `approval_engine`/`job_model`/`tool_registry` code into a real non-prototype package, whether `worker-service/` should be finished/merged/deleted, and fix the now-false "nothing in this directory is wired into production" claim. Any deletion goes through the standing deletion-approval gate (list candidates individually, Kamara approves each).
- Worker heartbeat renewed only once per loop iteration, before `poll_once()` runs — a long enough capability call could let a worker's own heartbeat lease expire mid-submission. Found 2026-09-19. **Fixed in code 2026-09-27** (`ssh_worker_client.py` renews the heartbeat after execution, before `submit_result`); not yet deployed to Worker01/Worker02.
- `llama3.2:3b`/`qwen3:4b` — confirmed already removed from `karmo-ai01`'s Ollama install (moot, no action needed).
- Two ambiguous legacy document hashes (`karmo-v05-new.html`) — intentionally left unresolved pending a human decision on version ordering. Do not resolve without that explicit decision.
- Report-only registry auditor (reconciling `tool_registry` against actual invocations) — recommended, never started, worth doing before the registry grows past its current ~5 tools.

## F. Open questions needing Kamara's input specifically

1. **Merge PR #117?** All four local capabilities (eyes/coding/ears/voice) are built and tested but not yet merged into `main` — nothing changes in production either way (all four are inert until the DSN activation decision below), so this is low-risk to merge whenever.
2. **Client surface build** — Kamara's answer 2026-09-20: browser, phone, AND mic/speaker, all three. This is real, not-yet-scoped frontend/client work (extending `core_service.webui` for mic capture + audio playback, plus a phone access path) — needed before any of the 4 local capabilities are reachable from a live conversation.
3. **Worker-dispatch DSN activation decision** — creating `/etc/karmo/core/worker-dispatch.dsn` would activate all 4 local capabilities AND silently re-enable Phase D2's held-back chat routing (shared switch, see section G). Needs either resolving D2's own flagged concerns or decoupling the two switches — not a quick decision.
4. **Ethical-hacking lab isolation** — parked for 2026-09-22 per Kamara's instruction. Does an isolated lab (Metasploitable/Juice Shop, separate network) already exist, or does it need to be stood up first?
5. **Next KARMO capability choice beyond the above** — durable memory, BloomBoss Phase 1, and the orchestration task board are all live; no further new capability track has been chosen (BloomBoss Phase 2, further Worker Commander capabilities like `bounded_text_read`/`directory_list`, or something else).
6. **VM resource reallocation** — decide whether/how to shift RAM/CPU shares across KVE01/02/03 to give any single VM more headroom, beyond what's already used by the models built tonight.

---

*This file is meant to be updated in place, not superseded by a new
dated file each session, per the governance fix that caused
`NEXT_STEPS.md` to go stale before (see `MASTER_INDEX.md`'s Mandatory
Document Labeling Rule).*
