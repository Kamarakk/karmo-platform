# KARMO Chat Tool-Calling and External Delegation — Scope

Status: **APPROVED by Kamara, 2026-09-17. Implementation proceeds phase
by phase (Section 6); each phase still gets its own PR before merging,
same as every other capability in KARMO.** This document, plus the
runbook in Section 7, is the durable reference for why this exists and
how to safely extend it later — written specifically so a future
session (human, Claude, GPT, or otherwise) can add a new tool correctly
without re-deriving this reasoning from scratch.

## 1. The gap this closes

`operator.py`'s `handle()` is a 3-way keyword router: write-words →
refuse, status-words → status reader, everything else → `_chat()`, a
plain model completion with durable memory injected as reference text.
There is no path today where the model itself decides to call a
capability mid-conversation — every existing KARMO capability (Worker
Commander reads, `model_chat`, the orchestration task board, BloomBoss's
own report function) is only reachable through explicit CLI commands or
scripted calls, never from inside a live chat turn.

Concretely, this was discovered because Kamara asked KARMO a question
about BloomBoss and it had no way to answer — not because BloomBoss
data doesn't exist, but because chat has no mechanism to reach for any
capability at all, regardless of domain.

Verified before writing this plan (not assumed):
- `OllamaChatClient.chat()` already calls Ollama's `/api/chat` endpoint
  (`core-service/core_service/ollama_client.py:45`) — the correct
  endpoint for tool-calling — but does not pass a `tools` parameter and
  only returns the plain answer text, not the structured response
  needed to detect a tool-call request.
- Every chat-capable model currently installed anywhere in KARMO
  supports Ollama's native tool-calling (confirmed live via
  `ollama show`/`/api/show`, not assumed from model names):
  `qwen3:8b`, `ministral-3:8b` (also vision), `mistral:7b`,
  `granite3.3:2b` on `karmo-ai01`/Worker01/Worker02, plus `llama3.2:3b`
  and `qwen2.5:1.5b` on KARMO-DEV01's separate local Ollama install.
  `embeddinggemma` (all hosts) is embedding-only, not a chat/tool model.
- Headless Claude Code (`claude -p`, non-`--bare`) is billed identically
  to interactive use under a Pro/Max subscription — verified directly
  against Anthropic's own current documentation
  (`code.claude.com/docs/en/costs`), not a secondary source — and
  Anthropic's docs actively build and endorse this pattern (scheduled
  tasks, hooks, CI examples, all under subscription billing).
- OpenAI's Codex CLI technically works the same way under a ChatGPT
  Plus/Pro login, but OpenAI's own documentation explicitly recommends
  API-key billing instead for automated/scripted use — a real
  difference in vendor posture, not just a technical difference.

## 2. System-Fit Review

**Does existing infrastructure already solve this?** No new
architecture is required. The Tool/Capability Registry pattern
(`CapabilityDispatcher`, `ApprovalEngine`, capability-class-based
approval computation) already exists and is already used by every other
KARMO capability. This plan adds a new *caller* of that existing
dispatch path (the model itself, via tool-calling) — it does not add a
new authority mechanism, a new datastore, or a new service.

**Reuse vs. new build:**
- Tool-calling itself: reuses Ollama's existing native tool-calling
  support on models already running — no new model, no new host, no new
  network path.
- BloomBoss capability: reuses `bloomboss.ingest` and
  `bloomboss.report.snapshot_report()`, both of which already exist and
  are already tested — this plan adds a thin capability wrapper, not new
  business logic.
- External delegation (Claude/GPT): reuses the `claude`/`codex` CLIs
  already installed for interactive use, authenticated via existing
  subscriptions — no new account, no new billing relationship, no API
  key introduced anywhere.

**What's genuinely new:** the tool-calling loop inside `_chat()` itself,
and two new capability handlers (BloomBoss report, external-model
delegation). Everything else is wiring onto what already exists.

**Lifecycle/security burden added:** one new conversational code path in
`operator.py` (the tool-call loop, bounded and READ-only scoped — see
Section 3); two new capability manifests, following the exact pattern
every existing capability already follows.

## 3. Architecture

### 3.1 Tool-calling loop (the foundational piece)

- Extend `OllamaChatClient.chat()` to accept an optional `tools: list`
  parameter (Ollama's native tool schema) and return the full response
  message object, not just the answer string — needed to detect a
  `tool_calls` field in the model's response.
- Extend `operator.py`'s `_chat()`:
  1. Build a `tools` list from a small, explicit allow-list of
     capabilities exposed to the model (see 3.2 — READ-class only in
     v1).
  2. Pass `tools` on the chat call.
  3. If the response contains `tool_calls`, run each through the
     **existing** `CapabilityDispatcher` (same approval computation,
     same audit ledger, same path every other KARMO action already
     goes through). A model *proposing* a tool call is never treated as
     the tool call being *approved* — `compute_approval_requirement()`
     still governs whether it can execute, exactly as it does for every
     other caller today.
  4. Feed the tool result back to the model as a `tool` role message,
     let it produce the final answer.
  5. Hard cap on tool-call rounds per turn (proposed: 4) so a confused
     model cannot loop indefinitely — on cap exceeded, return the best
     available answer with a note, never hang.
- **v1 scope: only capabilities whose computed approval requirement is
  `NONE` (i.e. `CapabilityClass.READ`) are ever placed in the `tools`
  list the model sees.** Nothing that writes, spends, or destroys
  anything becomes reachable by the model's own judgment in this phase
  — that is explicitly a separate, later decision (Section 5).
- First proof: wire in a capability that already exists (e.g. the
  orchestration task board's `list_tasks`) before adding anything new,
  so "does the loop work" is verified independently of "does the new
  capability work."

### 3.2 BloomBoss capability

- New capability `bloomboss_report`, `CapabilityClass.READ`,
  `network_required=False`.
- Handler wraps `bloomboss.ingest` (build a snapshot from
  `docs/bloomboss/historical_data/*.csv`) and
  `bloomboss.report.snapshot_report()` (already-tested, already-existing
  functions — no new business logic).
- Input schema: none required for v1 (reads the fixed historical-data
  directory); a future version could accept a date-range or cultivar
  filter as an argument once there's a real need.
- Known limitation to state plainly in the tool's own description (so
  the model doesn't imply false confidence): the only real data
  currently in the repo is the EMgarden invoice's 75 units — answers
  will reflect that scope until more real history is imported the same
  clean way.

### 3.3 External delegation — "ask Claude"

- New capability `ask_claude`, `CapabilityClass.READ` (it does not
  write or change anything from KARMO's side).
- Handler shells out to `claude -p "<question>"` — **explicitly not
  `--bare`**, so it authenticates via the existing subscription login
  rather than requiring `ANTHROPIC_API_KEY`.
- **Deliberately scoped to pure Q&A for v1**: the delegated Claude
  invocation itself gets no file or shell access (`--allowedTools ""`
  or equivalent restriction). A locally-running model autonomously
  waking a *fully capable coding agent* is a materially bigger authority
  question than "ask a question, get a text answer" — that stays a
  separate, later, explicitly-scoped decision (Section 5), not bundled
  into this one.
- Bounded timeout on the subprocess call; a failure (timeout, non-zero
  exit, malformed output) is refused the same way every other capability
  refuses a failure — never a silent hang.

### 3.4 External delegation — "ask GPT" (conditional on Kamara's decision)

- Same shape as 3.3, targeting `codex exec` under the existing ChatGPT
  subscription login.
- Built only if Kamara wants it despite the documented vendor-posture
  difference (Section 1) — the capability's own docstring/comment
  states that caveat explicitly, so it is never silently forgotten in
  later maintenance.

## 4. Invariant Impact Review (outline — complete formally before implementation)

- **I-01/I-09 (authority boundary)**: the model gaining tool-call
  *proposal* ability is new; tool call *execution authority* is not —
  it still runs through the unchanged `ApprovalEngine`/
  `CapabilityDispatcher` path. v1's READ-only scope means no new
  approval requirement class is exercised by this change; a later
  write-capable phase would need its own review specifically for how a
  model-proposed action gets a human confirmation step in a
  conversational (not batch/CLI) context.
- **I-03 (authoritative source)**: BloomBoss capability reads existing
  committed historical-data CSVs; no new datastore, no new authoritative
  record.
- **I-05 (resource/lifecycle bounds)**: tool-call loop needs an explicit
  round cap (proposed 4) and the subprocess calls to `claude`/`codex`
  need an explicit timeout — both must be enforced, not advisory, per
  the same standard as every other bounded execution path in KARMO
  (`sandbox.py`'s real-kill timeout is the existing precedent to match).
- **I-06 (config single-sourcing)**: the tool allow-list exposed to the
  model should be a single named constant, not duplicated across call
  sites.
- **No PII/no-secret exposure**: the `ask_claude`/`ask_gpt` handlers
  must never forward memory context or any KARMO-internal data as part
  of the delegated question unless that's the explicit, scoped purpose
  of a given call — default to sending only what the user actually
  asked, not full conversation history, unless a future version
  deliberately extends this.

## 5. Explicitly NOT scoped here (separate future decisions)

- Any `WRITE`/`REVERSIBLE_WRITE`/`DESTRUCTIVE_HIGH_IMPACT` capability
  ever placed in the model's own tool-call list.
- Giving `ask_claude`/`ask_gpt`'s delegated calls file or shell access —
  i.e., turning "ask a question" into "let an external agent act."
- Any change to `worker-runtime`'s existing `model_chat` capability or
  the worker dispatch path — this plan is entirely about `core-service`
  chat, not the worker fleet.
- Voice, image generation, or any other item from
  `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` not directly part
  of this thread.
- Automated/unattended (cron-fired) use of `ask_claude`/`ask_gpt` — v1
  is triggered only by a live chat turn a human is present for.

## 6. Phased implementation plan (for a future, separately-authorized session)

1. Formal Invariant Impact Review sign-off on Section 4 above.
2. Extend `OllamaChatClient.chat()` for `tools` + full response object.
   Tests: tool-call detected and parsed; no-tool-call path unchanged;
   malformed tool-call response handled without crashing.
3. Extend `_chat()`'s loop, wired only to `list_tasks` (nothing new)
   as the first proof. Tests: model calls the tool, gets a real result,
   produces a final answer; round-cap actually stops a looping model;
   a non-READ capability is never placed in the exposed tool list (this
   assertion is itself a test, not just a code comment).
4. Add `bloomboss_report`. Tests: real report data comes back through
   chat; the "only the EMgarden invoice is in scope" limitation is
   reflected honestly in the tool's description; failure (e.g. no data
   files present) refuses cleanly.
5. Add `ask_claude`. Tests: successful delegation round-trip; timeout
   handling; the delegated call is confirmed to have no file/shell tool
   access (a real, verified assertion, not an assumption).
6. (Conditional on Kamara's decision) Add `ask_gpt`, same test shape,
   vendor-posture caveat documented in the handler's own docstring.
7. Full worker-runtime + core-service test suites green. PROJECT SAVE.

No step above begins until Kamara approves this document and,
separately, each phase's own PR before it merges — consistent with how
every other capability in KARMO has been built.

## 7. Runbook — how to add a new chat tool later

This section is the durable, repeatable procedure. Anyone extending
this later — Kamara, this session, a future Claude session, GPT, or any
other AI — should follow it rather than improvise, so every future tool
gets the same safety guarantees this plan established for the first
ones.

### 7.1 Where things live

- **The exposed-tool allow-list** is one named constant (proposed:
  `_CHAT_EXPOSED_TOOLS` in `operator.py`) — never build the list
  ad hoc at more than one call site (I-06, config single-sourcing).
- **Capability manifests** follow the exact existing pattern in
  `worker-runtime/app/capability_manifest.py` (`capability_id`,
  `version`, `authority_class`, `input_schema`, `timeout_seconds`,
  `network_required`) — a chat tool's manifest lives alongside the
  others it's dispatched with, not in a new location.
- **Handlers** are plain functions bound into the existing
  `CapabilityDispatcher`, the same way every capability in this
  codebase is already bound — see `operator.py`'s existing
  `self.dispatcher.bind(...)` calls for the pattern to copy.

### 7.2 The checklist for adding one new tool

1. **Does it already exist somewhere in KARMO?** Per the System-Fit
   Review principle (Section 2), check for existing code before writing
   new business logic. A chat tool's handler should almost always be a
   thin wrapper around something that already exists (as
   `bloomboss_report` wraps `bloomboss.report.snapshot_report()`), not
   new logic invented for the tool itself.
2. **What's its `CapabilityClass`?** If it's anything other than
   `READ`, **stop** — v1's design explicitly never places a
   non-`READ`-class capability in the model's exposed tool list
   (Section 3.1, Section 5). Adding a write/destructive tool to that
   list is a new decision requiring its own Invariant Impact Review
   focused specifically on how a *model's own judgment* triggering a
   consequential action gets a real human confirmation step in a live
   conversation — not something to slip in as "just another tool."
3. **Write the manifest and handler**, following 7.1's pattern exactly.
4. **Add it to the one named allow-list constant.** Nowhere else.
5. **Write tests covering**: the tool actually being callable and
   returning a correct result through a real chat turn; a failure case
   refusing cleanly (never hanging, never a raw traceback reaching the
   user); and — if the handler shells out to anything external (like
   `ask_claude`/`ask_gpt`) — an explicit assertion of what access that
   external call does and does not have, not an assumption.
6. **Update this document's Section 3** with the new tool's design,
   the same level of detail as the existing entries — this file is
   meant to stay the single source of truth for "what can chat reach,
   and why," not just a historical record of what was true in
   September 2026.
7. **Small, single-purpose PR.** Same rule as everything else in this
   codebase — one tool's addition per PR, not bundled with unrelated
   changes.

### 7.3 The one rule that must never be worked around

**No capability with a computed approval requirement above `NONE` may
be placed in the model's exposed tool list without a new, explicit,
separately-authorized design decision — never as an incidental part of
adding "just one more tool."** This is the load-bearing safety property
of the entire tool-calling design: the model's own initiative stays
bounded to read-only, reversible-nothing actions unless a human
deliberately, explicitly decides otherwise for a specific capability,
with its own review of how that capability's execution gets confirmed.
If a future need seems to require this, that need should trigger a new
version of this document's Section 4, not a quiet exception.
