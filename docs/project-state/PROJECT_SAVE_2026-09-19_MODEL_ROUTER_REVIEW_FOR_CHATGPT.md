# KARMO Model Router — Routing Layer Work, Prepared for Independent Review

**Covers:** everything built for KARMO's "Model Router" / routing-and-brain layer across this session — the design plan, four build phases, what's deployed vs. merged-but-not-deployed, and a currently unresolved production reliability bug
**Read this if:** you're reviewing whether the routing/dispatch work done tonight is architecturally sound, or helping diagnose the open `submit_result` failure described in Section 6
**Status:** point-in-time session summary, 2026-09-19 — written specifically as a self-contained handoff for ChatGPT review, not itself a living architecture document (see Section 1 for where the actual design lives)

---

## 0. Why this document exists

This is a high-level explanation of everything done on KARMO's model-routing
layer ("the routing and brain") in this session, written for an independent
AI reviewer (ChatGPT) with no prior context. KARMO's own engineering
convention is: Claude Code implements, ChatGPT does independent
architecture/review/verification. This document is that handoff.

Where to find the real, authoritative source if you want to go deeper than
this summary:
- `docs/architecture/KARMO_ORCHESTRATION_AND_MODEL_ROUTING.md` — the
  original target architecture ("KARMO is the trusted coordinator; models
  are replaceable cognitive resources").
- `docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md` — the concrete,
  phased build plan this session executed against (already reviewed once
  by ChatGPT and revised from that review before any of this was built).
- `docs/project-state/NEXT_STEPS.md` (items 6–15) and
  `docs/project-state/CURRENT_STATE.md` (2026-09-18/19 entries) — the full
  blow-by-blow durable record, including exact commands, timestamps, and
  Postgres query results, if you want ground truth beyond this narrative.

---

## 1. The problem this work solves

KARMO is a private, home-lab AI/automation platform. Its chat interface
runs on a single host, `karmo-ai01`, which also runs Postgres, Qdrant, and
a job-coordination gateway — i.e., it's contended, not dedicated inference
hardware. Two additional hosts, Worker01 and Worker02, run Ollama and
nothing else, and were sitting idle for this purpose.

A real incident earlier this session made the cost of that concrete: a
chat question triggered `qwen3:8b` and `ministral-3:8b` (the two real,
tool-capable local models) to both time out under contention, and the
system silently fell through to `granite3.3:2b` — a model that is not
reliably tool-calling-capable — which then produced a fluent, confident,
**wrong** answer instead of an honest failure.

The user's own framing for the fix, in her words: build a **"Sovereign
Intelligence and Execution Layer"** — KARMO stays the sole trusted
coordinator; local models, Claude, GPT, and worker hosts are all
replaceable, interchangeable "cognitive resources" that never gain
standing authority just because they're reachable. This isn't a new
invention — it matches an architecture already named "Model Router" in an
earlier, separate design document — the SIEL framing is just the user's
own name for the same target.

Before any code was written, four rounds of external research were done
(LLM gateway/routing/cascading patterns, contention/circuit-breaker/
capability-aware-fallback patterns, authority-boundary/confused-deputy
patterns, decision-provenance/idempotency/shadow-rollout patterns), and
the resulting plan was independently reviewed by ChatGPT before
implementation began. That review caught real gaps in the first draft
(wrong phase ordering, `/api/ps`-alone treated as a full health check, a
shadow-mode design that would have duplicated real inference load,
missing security requirements, no total request deadline) — all folded
into the plan before Phase A started.

## 2. The phased plan (as approved)

From `KARMO_MODEL_ROUTER_DESIGN_PLAN.md`:

- **Phase A** — multi-signal host health (not just "loaded models," which
  GPT's review flagged as an incomplete signal on its own).
- **Phase B** — capability registry + enforcement (a model must be tagged
  tool-calling-capable to ever be a fallback candidate for a tool-calling
  request).
- **Phase C** — shadow routing (compute and log what a real router
  *would* choose, without ever acting on it, to gather evidence before
  risking real traffic).
- **Phase D** — controlled worker routing, split into D1 (prove a worker
  can serve a request end to end + measure real reliability) and D2
  (actually route real chat traffic to a worker) — D2 is explicitly not
  authorized until D1's evidence supports it.
- **Phase E** (not started) — durable, queryable decision audit records.
- **Phase F** (not started) — idempotency-key discipline, required before
  any capability beyond read-only is ever exposed further.

Each phase required its own Invariant Impact Review and System-Fit Review
(KARMO's standing governance gates) before implementation, and each
shipped as its own small, independently tested, independently deployed
pull request — never one large change.

## 3. What was built, phase by phase

### Phase A — host health signal (PR #82, deployed and live)

- `core_service/host_health.py`: polls `karmo-ai01`'s own local Ollama via
  its official `/api/ps` endpoint (loaded models, never a full health
  check on its own) plus an optional timed probe.
- Added a `tool_calling` capability tag to the existing model registry
  (`qwen3:8b`, `ministral-3:8b`) — sourced from real evidence (both were
  observed actually attempting Ollama's tool-calling contract before
  timing out), never guessed. `granite3.3:2b` and `mistral:7b` were
  deliberately left untagged. This tag changed **zero** runtime behavior
  by itself in this phase — it was pure data, consumed later in Phase B.

### Phase B — capability-typed, equally-authorized fallback (PR #84, deployed and live)

- Changed the chat candidate filter from `required_capabilities={"chat"}`
  to `{"tool_calling"}` — the direct structural fix for the incident in
  Section 1. `granite3.3:2b` can now never again be silently selected as
  a chat fallback.
- Verified (not assumed) that a fallback candidate's tool call already
  goes through identical authorization logic to the primary candidate's —
  the dispatcher doesn't branch on which model produced a call.
- **User-visible behavior change, deployed**: chat now returns an honest
  "unavailable" message instead of any answer at all if both real models
  are down, rather than a wrong answer from a weaker model. This is the
  intended trade-off.

### Phase C — shadow routing (PR #85, deployed and live)

- For every real chat request, computes what a future routing policy
  *would* choose (prefer an idle worker over contended `karmo-ai01`, when
  eligible) and logs it — never affects the real answer.
- Deliberately polls only the cheap `/api/ps` signal for this, never a
  timed inference probe, specifically because running real inference on
  every chat turn just to observe would itself add to the contention
  problem this whole effort exists to relieve.
- Has a directly-tested hard safety property: a test forces the shadow
  decision logic itself to raise an exception and confirms the real chat
  response is completely unaffected.
- One real bug found and fixed during this deployment: the shadow-router
  reused an existing, narrowly-scoped Postgres credential (used for
  chat's durable memory) to read worker health, assuming it had broader
  access than it actually did. Fixed with the minimal grant actually
  needed (read-only, one table) rather than widening the credential's
  scope in general.

### Phase D1, part 1 — worker tool-calling capability (PR #87, merged, not deployed until later — see Section 4)

- The workers' existing chat capability (`model_chat`) only ever called
  Ollama's `/api/generate` (plain prompt) — never `/api/chat` (messages +
  tools). This is the concrete gap that's blocked worker-hosted
  tool-calling since it was first scoped in an earlier session.
- Added a **new**, separate capability, `model_chat_tools`, rather than
  bumping `model_chat`'s version — because the live production worker
  config already had `model_chat` "1.0.0" declared active, and a version
  bump risked the *whole worker* failing config validation on its next
  restart if the deployed config and the manifest ever drifted out of
  sync. The new capability is strictly additive.

### Phase D1, part 2 — Core-side dispatch/wait glue (PR #88, merged, not deployed until later — see Section 4)

- Building this surfaced a real, previously-undiscovered architectural
  gap: the existing worker job/ticket/result system only ever durably
  stored a result's cryptographic **digest and signature**, never the
  actual content. That's correct for a benchmark-style capability with a
  known expected output; it's unusable for chat, where the answer can't
  be known in advance. Closed with a new table
  (`karmo_worker_job_results`) and an additive parameter on the existing,
  already-hardened result-submission path — every prior caller
  unaffected.
- `worker_dispatch.dispatch_and_wait()`: creates an approval pinned to a
  specific worker, enqueues the job, and polls for a terminal state
  within a bounded total deadline. Never retries internally. This is
  explicitly a **proof/measurement harness** — it is not wired into real
  chat traffic. Making a worker an actual candidate for real chat traffic
  is Phase D2, which has not been authorized or started.

## 4. Deploying D1 and the live proof-run that found a real bug

Once merged, PR #87+#88 were deployed to `karmo-ai01` and Worker01, the
new capability was durably granted to Worker01 via the reviewed store API
(not raw SQL), and a real job was dispatched end to end — deliberately,
because this phase's whole purpose is producing real evidence, not
trusting tests alone.

**Finding**: the job reached `LEASED` (Worker01 correctly polled and
claimed it), but never reached a terminal state — it timed out. Worker01's
own log showed the underlying capability call very likely *succeeded*,
but the result was never reported back to Core.

**Root cause #1, confirmed and fixed (PR #89, merged and deployed)**:
`worker_gateway_backend.py`'s `poll()` always leases a job for a fixed
60 seconds regardless of which capability is being run, but
`model_chat`/`model_chat_tools` are both allowed up to 120 seconds. A
real call anywhere near that long structurally could not report its own
success before its lease expired. **This affects the already-deployed
`model_chat` v1 too**, not just the new capability — it's a real,
previously-latent gap, not something this session's new code introduced.

The fix: a job's enqueuer can now specify how long a lease it needs
(bounded 30–600s), consulted automatically at lease time; when not
specified, the historical 60s default still applies. `dispatch_and_wait()`
now defaults its own request to match its own `total_deadline_seconds`,
so the two durations can't silently drift apart. Verified directly
against Postgres after deploying: the lease really was sized correctly
(140 seconds, not 60) on the very next real dispatch.

## 5. The fix worked — but a second, separate bug is still open

Re-running the exact same live proof-run after deploying the lease fix
produced the **same symptom** (timeout, no result reported), but this
time the investigation went further and ruled out timing entirely:

- The worker gave up only ~21 seconds after leasing the job — nowhere
  near either the new 140-second lease or the 120-second capability
  timeout.
- Calling Ollama directly on Worker01 with the identical
  model/prompt/tool schema returned a clean, valid tool call in ~7
  seconds. The underlying capability execution is not the problem.
- Checking the durable event log: the **last time any job on Worker01
  fully succeeded end to end (leased → ticket issued → ticket consumed →
  result submitted → succeeded) was 2026-09-17**, before any of this
  session's worker-runtime deployments. Both real attempts tonight stop
  at the identical point — ticket consumed, then nothing. Heartbeats are
  confirmed still working correctly right now, so this isn't a total
  transport failure, only something specific to the `submit_result`
  operation.
- The exact underlying SSH error is hidden by design in the existing
  code (`ssh_stdio_transport.py` deliberately never surfaces raw stderr
  to callers, to avoid leaking local paths/account names), so the real
  cause isn't visible from inside the existing error handling as it
  stands.

**One additional, separate finding surfaced while investigating this**
(not yet confirmed as the cause, but a real bug regardless): the actual
payload a worker submits isn't the capability's raw output — it's wrapped
one level deeper (`{"output": {...actual result...}, "stdout_summary":
..., "duration_seconds": ..., "evidence_files": [...]}`), a detail that
`dispatch_and_wait()`'s current read-back logic does not account for. This
was found by reading `ssh_worker_client.py`'s actual submission code, not
guessed. Whether this wrapping is *causing* the submit failure, or is
simply a separate, secondary shape bug that would need its own fix once
the submit failure is resolved, is not yet established.

**Investigation stopped at this point** because two consecutive diagnostic
actions were correctly blocked by KARMO's own production-safety
guardrails: temporarily patching the deployed transport file to reveal
the real SSH stderr (a live production code edit, even temporary), and
briefly stopping Worker01's real service to run a clean, race-free manual
test. Both are reasonable things to stop on mid-investigation rather than
push through unilaterally, so the investigation is paused pending explicit
authorization, not abandoned.

Current state: both real attempts' stuck jobs were cleanly reconciled via
the existing, already-proven `recover_expired_leases()` mechanism — no
data loss, both left in an honest "unknown execution outcome" state, never
silently marked as success. Both services (`karmo-core.service`,
`karmo-worker01.service`) are healthy and have not crashed at any point
during this entire investigation.

## 6. Specific questions for review

1. **Does the phased design itself (A → B → C → D1 → D2, each gated on
   evidence from the previous phase) still look sound**, given what's
   actually been found building it? In particular: is treating "the
   worker job/ticket/result system was only ever proven for benchmark-
   style, digest-provable capabilities" as a discovered gap (rather than
   a design flaw that should have been anticipated) a fair read?

2. **On the open `submit_result` failure**: given the constraints
   described (root cause not directly observable without either editing
   deployed code or stopping a live service, both currently paused
   pending authorization), what's the most information-dense next
   diagnostic step that doesn't require either of those two actions?

3. **On the result-wrapping shape mismatch**: is it worth fixing
   `dispatch_and_wait()`'s result unwrapping now, even before the submit
   failure itself is resolved, on the theory that it's a real bug
   regardless of whether it's related to the current blocker? Or does
   fixing two things at once when only one is confirmed-necessary risk
   muddying the eventual root-cause finding?

4. **Given the last fully-successful job on Worker01 was 2026-09-17,
   before any of this session's worker-runtime deployments** — is there
   a more targeted way to bisect which specific deployment (PR #83's
   heartbeat wire-protocol extension vs. PR #87's new capability)
   introduced the regression, without needing a live production test
   each time?

5. **Anything in the security/authority model** (capability classes,
   approval binding, the "no fallback candidate gets a lighter
   authorization path" rule, the worker-address allowlisting) that looks
   weaker than it should, now that there's a real worker-execution path
   being built out, not just the chat-side enforcement from Phase B?
