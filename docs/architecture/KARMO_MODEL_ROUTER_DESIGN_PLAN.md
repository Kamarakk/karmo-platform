# KARMO Model Router — Design and Build Plan

**Covers:** the concrete, phased design plan for the Model Router component (item 2 of the target architecture) — Kamara's "Sovereign Intelligence and Execution Layer" (SIEL) framing, the research it's built on, an independent GPT review and the revisions made from it, the health/capability/fallback/security/fail-closed rules it proposes, and the phased build order
**Read this if:** you're about to implement, extend, or evaluate anything that chooses which model or host handles a KARMO request — chat tool-calling model selection, worker-hosted inference dispatch, or `ask_claude`/`ask_gpt` delegation
**Status:** DRAFT design plan, 2026-09-18 — research-backed (four passes complete) and revised against an independent GPT review of this same document. Awaiting Kamara's review/merge decision. Nothing in this plan is authorized to begin on that basis alone.

This is the concrete build plan for the component the target architecture
(`docs/architecture/KARMO_ORCHESTRATION_AND_MODEL_ROUTING.md`) already named
"Model Router" on 2026-09-11. Read that document first — it is not
superseded by this one. This document exists because Kamara asked, in her
own words, to go over that routing layer again under the new Full-Context
Review Rule, framed it as building a **Sovereign Intelligence and Execution
Layer** ("outside AI systems are replaceable cognitive resources," KARMO
stays the sole trusted authority), and asked for real research before any
plan got written.

SIEL is not a new architecture. It is Kamara's own name for the same
target already on record: KARMO is the trusted coordinator; local models,
Claude, GPT, and any future backend are interchangeable, replaceable
cognitive resources that never gain standing authority just because they
can be reached.

**Revision note (2026-09-18):** the first version of this document was
reviewed independently by GPT per KARMO's own engineering collaboration
model (Claude implements, ChatGPT reviews/verifies). That review is not
attached as a separate file — its substance is folded directly into this
document, section by section, below. The two changes worth naming up
front: the phase order was wrong (capability enforcement and shadow
validation must come before live worker routing, not after), and the
document overclaimed certainty about resource contention being the
confirmed root cause when the evidence available so far only supports
"consistent with," not "proven."

## 1. The concrete problem this plan is answering

Two problems. The first is confirmed; the second is evidenced but not yet
isolated from other explanations:

1. **Wrong resource is doing the work (confirmed).** `karmo-ai01` — an
   8GB host that also runs Postgres, Qdrant, and the worker gateway — is
   the only host KARMO chat currently uses for local-model tool-calling.
   Worker01 and Worker02 run Ollama only, dedicated, and are idle for
   this kind of work. There is no router; there is a hardcoded model list
   tried in order on one box.
2. **That placement is measurably failing, for a reason not yet isolated.**
   After the tool-calling timeout was already raised from 45s to 120s,
   and after a real durable-memory contamination bug was found and fixed
   (see the orchestration doc's "Concrete evidence" section), two real
   chat questions still failed: `qwen3:8b` timed out at the full 120s,
   then `ministral-3:8b` also timed out at the full 120s, before falling
   back to `granite3.3:2b` — a model that does not reliably invoke tools,
   so it produced a fluent, confident, wrong answer instead of calling
   `bloomboss_report`. One full turn took 379.5 seconds.

   **This is consistent with resource contention on `karmo-ai01`, and
   requires instrumented confirmation before being treated as proven.**
   The 120-second double-timeout does not by itself rule out: Ollama's
   own request queueing, cold model-load time, prompt/context-window
   size, worker-transport latency, a bug in the tool-calling loop itself,
   or memory swapping under pressure. Phase A below exists specifically
   to produce the instrumentation that can actually distinguish these —
   until then, contention is the leading hypothesis, not a settled fact.

Raising the timeout further treats a symptom regardless of which
explanation turns out to be right. Moving the work to idle, dedicated
hosts (Worker01/02) is a reasonable response to the leading hypothesis —
but Kamara correctly pushed back that "move it to Worker01/02" by itself
is not a router, it's just relocating the same hardcoded list. A real
router has to decide, per request, *which* fit host/model to use, detect
when one is degraded, fail over without silently degrading answer
quality, and leave a record of why it chose what it chose. That is what
the rest of this document designs.

## 2. Research performed before writing this plan

Four sequential research passes were run specifically so this plan would
be built on established real-world patterns, not invented from scratch.
Kamara's explicit instruction: document the finding, then use it plus a
fresh read of KARMO itself before writing the plan. Section 3 below is
where a fifth input — GPT's independent review of the first draft — gets
folded in; it is not a fifth research pass, since it was a review of this
document rather than external-literature research.

### Pass 1 — LLM gateway / load-balancing / cascading patterns

- **LiteLLM** ships five router strategies out of the box: simple-shuffle,
  latency-based, usage-based-v2, least-busy, and cost-based. The takeaway
  for KARMO is not "copy LiteLLM" but that production LLM routers
  universally separate *routing strategy* from *provider adapter* — the
  strategy is pluggable, the adapters are not opinionated about it.
- **RouteLLM** draws a sharp line between **routing** (pick one model
  up-front per request, based on predicted difficulty/fit) and
  **cascading** (try a cheap/fast model first, escalate only on detected
  failure). KARMO's chat tool-calling today is accidentally a cascade
  (try qwen3, then ministral, then granite) with no escalation logic
  beyond "the previous one raised an exception or timed out." A real
  router needs to decide the right pattern per use case rather than
  defaulting to cascade-by-accident.
- **Celery**-style task queues route by declared worker *capability*
  (queues named for what a worker can do), not by guessing at runtime.
  KARMO already has this shape informally (workers only run Ollama;
  `karmo-ai01` is not a dedicated inference host) — it just isn't encoded
  as a routing rule anywhere.

### Pass 2 — contention, health signals, and fallback safety

- **Noisy-neighbor research**: co-located CPU-heavy workloads measurably
  degrade a shared host's other workloads by 53-59% in cited benchmarks.
  This is the general-case version of what's plausibly happening on
  `karmo-ai01` (Postgres + Qdrant + gateway + Ollama, one 8GB box) — see
  Section 1's caveat on why this remains a hypothesis, not a proof.
- **Circuit breakers** (resilience4j defaults: 50% failure threshold, a
  60s "slow call" bar, 60s cooldown) are the standard pattern for "stop
  sending traffic to a host that's failing," but resilience4j's default
  100-call sliding window is unusable at KARMO's actual request volume —
  KARMO will see single-digit tool-calling requests per hour, not per
  minute. A KARMO circuit breaker needs a much smaller window (or a
  time-based rather than count-based window) to ever trip.
- **Capability-aware fallback** is a named, real pattern for the exact
  failure KARMO just had: a fallback that silently drops from a
  tool-capable model to a non-tool-capable one produces a confidently
  wrong answer instead of a visible failure. The pattern's fix is to type
  fallback candidates by capability and never fall back across that
  boundary silently.
- **Ollama's own `/api/ps` endpoint** is official, documented, and built
  by Ollama specifically "to assist with more intelligent load
  balancing" — it reports which models are currently loaded/running per
  host. It is a real, zero-new-infrastructure signal, but — per GPT's
  review, folded into Section 3.1 below — it is only one input, not a
  complete health check by itself.

### Pass 3 — authority boundaries / mixed-resource scheduling

- **The Supervisor pattern** (LangGraph, CrewAI): one orchestrator holds
  shared state and is the sole chokepoint where logging, rate limiting,
  and policy enforcement happen — sub-agents/workers report back to it
  and never get direct execution authority. This is not a new shape for
  KARMO to build; it is the named industry match for what KARMO's
  dispatcher/approval-engine already is. No new architecture is implied
  here, only confirmation that the existing shape is the right one.
- **Confused-deputy risk across models is a real, current, named
  problem**, not a hypothetical. OWASP's 2026 LLM Top 10 ranks "Excessive
  Agency" #3, with three named root causes: excessive functionality (an
  agent can reach tools outside its actual task), excessive permissions
  (a tool runs with broader rights than the task needs), and excessive
  autonomy (a high-impact action proceeds with no human in the loop).
  OWASP's own mitigation is blunt: **"implement authorization in
  downstream systems rather than relying on an LLM to decide if an action
  is allowed."** Applied to KARMO specifically: a fallback model's tool
  call must pass through the exact same authorization check as the
  primary model's — never a lighter or skipped check just because it's
  "only the backup."
- **Mixed free/subscription/pay-per-token cost-shape routing — genuine
  gap, no adoptable framework found.** FinOps-for-LLM material is well
  developed for continuous $/token routing (route to the cheapest model
  meeting a quality bar), but none of it addresses a subscription with
  *soft, shared, non-monetary* headroom — a human and an automated system
  drawing from the same plan-usage-window, with no per-call price at all.
  KARMO's actual situation (free-unmetered-local / shared-subscription-
  headroom / potential-future-metered, three tiers at once) has no named
  framework in the literature searched. This is flagged honestly as
  original design work KARMO has to do itself, not something to adopt.
- **Rate-limit-aware scheduling for a resource a human also draws from**:
  the applicable pattern is dual-bucket token allocation — a separate,
  smaller bucket for background/automated traffic than for foreground/
  interactive traffic, where background work can borrow from the
  foreground bucket only when foreground is idle, never the reverse.
  Maps directly onto Kamara chatting with KARMO live versus KARMO
  deciding on its own to delegate to Claude/GPT in the background.

### Pass 4 — decision provenance, rollout safety, idempotency, transparency

- **OpenTelemetry's GenAI semantic conventions** (CNCF-backed) define
  standard span/metric/event schemas for LLM calls and agent steps,
  including provenance-shaped attributes (`agent.type.id`,
  `agent.instance.id`, `agent.context.size`, `agent.parent.prompt`) under
  a framework called BRACE. Multi-agent-system observability conventions
  are still explicitly experimental/in-development — there is no mature,
  finished standard to adopt wholesale yet, but the attribute *shape* is
  usable as a design reference now.
- **Stripe's idempotency-key discipline** is the clearest real-world
  answer to "a tool call may have already executed and I can't tell
  because the connection died mid-response": never collapse *unknown*
  into *failed*. Stripe stores and replays the exact first response
  (successes and 500s alike) per idempotency key, so a retry can never
  double-execute the underlying action. This matters more the moment any
  non-READ capability is ever exposed to the tool loop; it does not block
  today's READ-only exposure, but it must exist before that boundary is
  ever crossed.
- **Shadow and canary rollout patterns** (KServe, Seldon — standard
  ML-serving practice): shadow deployment mirrors real traffic to a new
  policy and records what it *would* have done, without it affecting the
  real response — standard for validating a new routing policy's
  correctness/latency before it can affect a real answer. Per GPT's
  review, folded into Section 6 Phase C below: naive shadow-mode that
  duplicates real inference calls would worsen the exact contention
  problem this plan exists to fix, so shadow-mode must default to
  shadowing the *decision* only.
- **Separating router reasoning from model output**: a *model gateway* —
  the layer that sees real production signals (load, cache state,
  fallback path, per-request governance) — is where explainability has to
  live, not the model's own output. A router should be able to explain
  "why this host/model" in plain terms independent of what the chosen
  model then said, logged as its own record at decision time, never
  reconstructed after the fact from the transcript.

## 3. What actually needs to be true, given all of the above

Translating the research (and GPT's review of it) into rules that fit
KARMO's actual scale (single household deployment, single-digit hourly
requests, three hosts, not a cloud fleet).

### 3.1 Health signal — multi-signal, not `/api/ps` alone

`/api/ps` shows which models are loaded and their memory footprint. It
does **not** prove a host is responsive, uncongested, or currently
capable of completing a tool call — that was the plan's original error,
caught in review. The router's health signal for a host must combine:

- Ollama's `/api/ps` (loaded-model state) — the free, zero-new-infra
  starting point, still worth polling;
- a timed inference probe (a small, cheap real request, on a schedule,
  to measure actual live responsiveness rather than inferring it from
  loaded-model state);
- recent p50/p95 latency for real tool-calling requests on that host;
- available memory/CPU headroom;
- consecutive failure count for that host;
- worker heartbeat age (workers already send heartbeats to Core — reuse
  that existing signal rather than inventing a parallel one);
- queue depth, where knowable (worker job queue depth is already tracked
  in the coordinator store; `karmo-ai01`'s own Ollama request queue is
  not currently observable and may need its own probe).

A host with stale health data (no signal newer than a defined freshness
window) is excluded from routing entirely — treated the same as an
explicit failure, not as "assume healthy."

### 3.2 Capability registry — separate from, and checked before, health

**"Loaded" is not the same fact as "tool-capable."** `/api/ps` reporting
a model as loaded is a runtime fact about that host right now; whether
that model type supports Ollama's native tool-calling contract at all is
a static property of the model, known ahead of time and independent of
which host it happens to be running on. The plan's first draft implicitly
treated "loaded" as a proxy for "available for tool-calling," which is
wrong — a host could have a loaded model that has never been tool-capable
at all.

The router must consult a capability registry (model name → declared
capabilities, including whether it supports tool-calling) **first**, to
narrow the candidate set to tool-capable models only, and only then use
`/api/ps`/health signals to choose among hosts that are actually serving
one of those models. Health state can exclude a candidate; it can never
promote a non-tool-capable model into eligibility.

The capability registry itself must be protected against unauthorized
change — it is a governance-relevant configuration artifact, not
something a running model, a worker, or any component below Core should
be able to edit. (Security requirement, restated in Section 5.)

### 3.3 Routing strategy

Capability-based dispatch first (Section 3.2), then prefer the
least-loaded *fit* host among the remaining candidates — closer to
RouteLLM's "route" than "cascade," since KARMO's actual problem is
contention, not cost. "Least-loaded" must be a defined, measurable score
derived from Section 3.1's signal set (for example: a weighted function
of recent p95 latency, queue depth, and consecutive-failure count — the
exact weights are Phase A's job to derive from real telemetry, not to be
guessed here).

### 3.4 Fallback — capability-typed, not positional, and equally authorized

The current `_CHAT_EXPOSED_TOOLS` fallback chain in
`core-service/core_service/operator.py` falls back by list position
(qwen3 → ministral → granite) with no concept of "granite doesn't
reliably call tools." Fixes required:

- A capability-typed fallback chain must never silently cross from
  tool-capable to non-tool-capable. If every tool-capable candidate
  fails, the correct behavior is a clear, honest "I couldn't reach a
  capable model right now," not a fluent wrong answer from a model that
  was never a real candidate for this request.
- **A fallback model's tool call gets the identical authorization check
  as the primary model's tool call.** No fallback candidate — including
  `granite3.3:2b` or any future addition — is ever allowed a lighter or
  skipped authorization path merely because it's later in the chain.
  This directly closes the OWASP-named "excessive agency via implicit
  trust" failure mode (Section 2, Pass 3).
- The router must never retry the identical (host, model) pair a second
  time within a single request's total deadline (Section 3.5) —
  protection against routing loops, not just against exhausting the
  candidate list once.

### 3.5 Reliability — circuit breaker, latency budget, no accumulating timeouts

- **Circuit-breaker windows must be time-based and small**, not
  resilience4j's default 100-call sliding window — KARMO will not see
  100 tool-calling calls in any reasonable evaluation period.
  **Initial acceptance criteria** (seeded from resilience4j's ratio/
  cooldown shape, resized for KARMO's volume; to be validated and tuned
  against real Phase A telemetry before Phase D ships — not asserted as
  final tuned constants):
  - trip to **open** when a (host, model) pair records 3 consecutive
    failures, or a failure rate ≥ 50% over the trailing 10 minutes with
    at least 2 attempts recorded;
  - stay open for 5 minutes before allowing a trial;
  - **half-open**: allow exactly 1 trial request. Success closes the
    breaker (reset failure count). Failure reopens it and doubles the
    open duration, up to a cap of 30 minutes.
  - GPT's review caught that the first draft defined the breaker's
    trigger shape but never its half-open recovery behavior at all —
    fixed above.
- **A single total request deadline, not stacked per-candidate
  timeouts.** This is the direct explanation for tonight's 379.5-second
  turn: two sequential 120-second per-candidate timeouts, uncapped in
  total. The design must instead set one total deadline for the whole
  tool-calling turn (health check + routing decision + every candidate
  attempt combined), with each candidate's own attempt scoped as a
  sub-budget within that ceiling — never simply summed across
  candidates. **Initial value: a total deadline in the 60-90 second
  range**, explicitly provisional and to be set from real Phase A
  latency telemetry rather than guessed; it replaces the current
  per-candidate-120s architecture entirely rather than sitting alongside
  it.

### 3.6 Decision audit

Router decisions get their own audit record, separate from the chat
turn's model output — which host, which model, what signal values were
read (health state, recent latency, breaker state), and why, logged at
decision time. This record must **never** contain prompt content,
secrets, credentials, or full tool results (Section 5) — it is a routing
trace, not a transcript. It must never be reconstructed after the fact
from the chat transcript.

### 3.7 Idempotency

Idempotency-key discipline is a prerequisite, not an add-on, for any
future non-READ tool exposure. It is not required today because every
capability in `_CHAT_EXPOSED_TOOLS` is hard-gated to
`CapabilityClass.READ` — but the hard rule in
`docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md`
that no non-READ capability may ever enter that allow-list must stay in
force *until* this idempotency design exists, not just until someone
remembers to think about it. Per Section 3.9's fail-closed rule: an
unknown execution result (connection died mid-response, can't tell if
the action ran) must never be resolved by silently repeating a write.

### 3.8 Shadow-mode — decision-only by default

Any new routing policy ships shadow-mode first, before it is allowed to
affect a real answer. **Per GPT's review: shadow-mode must not duplicate
real inference by default.** Mirroring every request to a second model
to compare outcomes would itself add load to the exact contention problem
this plan exists to fix. The default shadow behavior is to log what the
candidate policy *would have chosen* (the routing decision only, no
second inference call), for a period long enough to see real traffic
patterns; actual duplicate-inference sampling, if ever needed to validate
answer quality (not just routing choice), happens at a small, explicitly
bounded percentage — not by default.

### 3.9 Fail-closed behavior

Every failure mode below has one defined, non-negotiable response —
"fail closed" means the safe, honest answer, never a silent guess:

| Situation | Required behavior |
|---|---|
| No tool-capable model reachable | Explicit "unavailable" response to the user — never a wrong answer from a non-capable fallback |
| Health data for a host is stale | Exclude that host from routing entirely |
| Tool authorization fails for a candidate | Never retry the same tool call using a different model to get a different answer |
| Execution result is unknown (connection lost mid-call) | Never automatically repeat a write; surface as unknown, not as failed or succeeded |
| Router itself errors internally | Fall back to a safe static response or an honest failure message — never silently fall through to unrouted/ungoverned behavior |

### 3.10 Authority and mixed-resource scheduling (forward-looking, not yet actionable)

- **The three-tier resource mix (free local / shared subscription
  headroom / potential future metered) has no adoptable external
  framework.** Any cost-/quota-aware routing policy for this mix is
  original KARMO design work, not an adaptation of an existing pattern —
  call this out explicitly wherever it's designed so it doesn't get
  presented as "following established practice" when it isn't.
- **Background/automated delegation to Claude or GPT must never compete
  head-on with Kamara's own live, interactive use of the same
  subscription.** Any future automated dispatch (KARMO deciding on its
  own to call `ask_claude`/`ask_gpt` without Kamara in the loop) needs
  its own smaller usage allocation, separate from interactive use, that
  backs off automatically when interactive use is detected concurrently.
  Not actionable today — `ask_claude`/`ask_gpt` are only invoked
  synchronously inside a chat turn Kamara herself started — but binding
  the moment autonomous background dispatch is ever proposed.

## 4. Security requirements

Folded in directly from GPT's review; none of this was in the plan's
first draft.

- **Router-to-worker transport authentication.** KARMO's actual worker
  transport is SSH forced-command, not a network listener — there is no
  literal mTLS surface to add. The equivalent requirement: the SSH
  forced-command binding used for worker dispatch must remain
  least-privilege and worker-scoped at every phase; verify this doesn't
  silently drift toward a broader binding as routing logic gets added.
- **Explicit allowlist of worker/host addresses.** The router must never
  accept a model-generated hostname or URL as a dispatch target — target
  hosts come only from a fixed, KARMO-owned allowlist, never from model
  output. This is a direct, concrete defense against the confused-deputy/
  prompt-injection risk named in Section 2 Pass 3, not just a restatement
  of it.
- **Validate tool arguments after model output, before dispatch.** Schema
  validation of the tool call's actual arguments is a router-layer check
  independent of the capability dispatcher's own approval-requirement
  computation — both must exist; neither substitutes for the other.
- **Authorization decisions stay outside the router's scoring/routing
  logic.** Whether a tool call is *allowed* must never be entangled with
  or influenced by which host/model the router happened to pick — a
  routing bug must never be able to grant execution authority as a side
  effect.
- **Audit-log content restriction.** Routing/decision audit records
  (Section 3.6) must never contain prompt content, secrets, credentials,
  or full tool results.
- **Capability-registry integrity.** The registry (Section 3.2) must be
  protected against unauthorized modification — it is governance-relevant
  configuration, not runtime-mutable state.
- **Concurrency limits per host and per model**, so the router cannot
  itself create the contention it exists to relieve by over-dispatching
  to one host.
- **One correlation ID** carried across routing, inference, authorization,
  tool execution, and the final response — required for the audit record
  in Section 3.6 to actually be traceable end to end.
- **READ-only tool-loop enforcement lives in code and tests, not only in
  documentation.** The existing hard rule in
  `docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md`
  is currently a documented rule; it must be backed by an enforced check
  (and a test that fails if a non-READ capability is ever added to
  `_CHAT_EXPOSED_TOOLS`) before this plan's phases touch that code path.

## 5. Required tests before any production routing

Adopted close to verbatim from GPT's review as the exit criteria for
Section 6 Phase D2 below:

- A model advertised as tool-capable but fails the tool contract at
  runtime.
- A worker that is unreachable, slow, overloaded, or returns malformed
  data.
- Stale health information for a host.
- Router restart while a request is in flight.
- A duplicate request / duplicate correlation ID.
- Authorization denial occurring during a fallback attempt, not just the
  primary attempt.
- Every capable candidate unavailable at once.
- Circuit breaker open state, and half-open recovery (success and
  failure both).
- A worker response that arrives after the caller's total deadline has
  already passed.
- A prompt-injection attempt that tries to make the model select a
  different host, model, or capability than the router chose.
- Audit records contain no sensitive prompt/tool data (a direct test of
  Section 4's audit-log content restriction).
- The existing direct-chat (non-routed) path remains available and
  working as a kill-switch rollback, independent of anything the router
  does.

## 6. Phased build plan

Each phase requires its own System-Fit Review and Invariant Impact Review
at the time it is actually implemented, per the standing rules in
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. Nothing here is a
deployment order. **Reordered from the first draft per GPT's review**:
capability enforcement and shadow validation now come before live worker
routing, not after — the original order could have let the router send
production traffic to a mislabeled or non-tool-capable model before the
safety net existed to catch it.

- **Phase A — observability and health signals.** Build the multi-signal
  health model from Section 3.1 (not `/api/ps` alone) on `karmo-ai01`,
  Worker01, and Worker02, and expose it to the operator. Prerequisite for
  everything else; no behavior change by itself. Also the source of real
  telemetry needed to confirm or rule out the contention hypothesis from
  Section 1, and to set real values for Section 3.5's provisional
  circuit-breaker and latency-budget numbers.
- **Phase B — capability registry and enforcement.** Build the
  capability registry (Section 3.2) and the capability-typed,
  equally-authorized fallback chain (Section 3.4) in
  `operator.py`'s tool loop. This is a correctness/safety fix to the
  *existing* `karmo-ai01`-only chain and does not by itself touch worker
  routing — it must land and be proven before Phase D below can safely
  add more hosts into the candidate set.
- **Phase C — shadow routing.** Once A and B exist, run the candidate
  routing policy in shadow mode (Section 3.8: decision-only by default)
  against real traffic long enough to see real patterns, before it's
  allowed to affect a single real answer.
- **Phase D — controlled worker routing, split into two separate gates**
  (per GPT's review — the first draft combined these):
  - **D1 — transport proof.** Prove a worker can serve a chat
    tool-calling round trip end to end at all, including measuring the
    worker job system's real queue delay under realistic load (its
    asynchronous ~5-second polling design may or may not be suitable for
    interactive chat — this must be measured and an explicit bound
    defined, not assumed, before D2).
  - **D2 — production routing.** Only after D1's measurements are
    acceptable and Section 5's required tests all pass: chat
    tool-calling actually prefers an idle, dedicated, tool-capable
    worker over contended `karmo-ai01` when Phase A's signal shows one
    available, falling back to `karmo-ai01` only when no worker is fit.
- **Phase E — decision auditing.** Land the router decision audit record
  (Section 3.6) with the correlation-ID and content-restriction
  requirements from Section 4, using the OpenTelemetry GenAI attribute
  shape as a naming reference (not a hard dependency on the spec, which
  is still experimental).
- **Phase F — idempotency and future write-capability support.** Design
  and land idempotency-key discipline (Section 3.7) *before* any
  capability beyond READ is ever proposed for `_CHAT_EXPOSED_TOOLS`. Not
  urgent today; a hard prerequisite the moment it becomes relevant.

**Not yet phased, flagged for when it becomes relevant:** Section 3.10's
cost-shape design gap and background-delegation dual-bucket rule don't
map to a build phase today because KARMO has no autonomous background
dispatch yet — `ask_claude`/`ask_gpt` only run inside a chat turn Kamara
herself started. Both become required design work the moment autonomous
background dispatch is proposed, not before.

## 7. Research and review status

All four research passes are complete (Section 2). GPT's independent
review of this document's first draft is fully folded in above — the
phase reorder, the softened contention claim, the multi-signal health
model, the capability registry, the fail-closed table, Section 4's
security requirements, Section 5's required tests, and the split of
worker routing into D1/D2 are all direct results of that review, not
restatements of the original research passes. Nothing in this document
is pending further research or review; what remains is Kamara's own
read and merge decision, and, separately, each phase's own System-Fit
Review and Invariant Impact Review at implementation time.

## 8. Safety boundary

This document authorizes no deployment, no production change, and no PR
merge by itself. Building any phase above requires its own System-Fit
Review and Invariant Impact Review at the time it is actually undertaken,
per `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. The hard rule that
no non-READ capability may enter KARMO chat's tool loop
(`docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md`)
remains in force regardless of anything in this plan.
