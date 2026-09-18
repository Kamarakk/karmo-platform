# KARMO Model Router — Design and Build Plan

**Covers:** the concrete, phased design plan for the Model Router component (item 2 of the target architecture) — Kamara's "Sovereign Intelligence and Execution Layer" (SIEL) framing, the research it's built on, the routing/health/fallback/provenance/rollout rules it proposes, and the phased build order
**Read this if:** you're about to implement, extend, or evaluate anything that chooses which model or host handles a KARMO request — chat tool-calling model selection, worker-hosted inference dispatch, or `ask_claude`/`ask_gpt` delegation
**Status:** DRAFT design plan, 2026-09-18 — research-backed, not yet implemented. One research thread (authority-boundary / mixed-resource-scheduling patterns) was still running when this was first written; see "Open research item" below. This document will be updated in place when it lands, not replaced with a new file.

This is the concrete build plan for the component the target architecture
(`docs/architecture/KARMO_ORCHESTRATION_AND_MODEL_ROUTING.md`) already named
"Model Router" on 2026-09-11. Read that document first — it is not
superseded by this one. This document exists because Kamara asked, in her
own words, to go over that routing layer again under the new Full-Context
Review Rule, framed it as building a **Sovereign Intelligence and Execution
Layer** ("outside AI systems are replaceable cognitive resources," KARMO
stays the sole trusted authority), and asked for real research before any
plan got written — the mistake made once already this session (see
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s Mandatory Full-Context
Review Rule) was building a plan without first confirming what already
existed.

SIEL is not a new architecture. It is Kamara's own name for the same
target already on record: KARMO is the trusted coordinator; local models,
Claude, GPT, and any future backend are interchangeable, replaceable
cognitive resources that never gain standing authority just because they
can be reached.

## 1. The concrete problem this plan is answering

Two problems, confirmed with real evidence, not assumption:

1. **Wrong resource is doing the work.** `karmo-ai01` — an 8GB host that
   also runs Postgres, Qdrant, and the worker gateway — is the only host
   KARMO chat currently uses for local-model tool-calling. Worker01 and
   Worker02 run Ollama only, dedicated, and are idle for this kind of work.
   There is no router; there is a hardcoded model list tried in order on
   one box.
2. **That wrong placement is measurably failing.** After the tool-calling
   timeout was already raised from 45s to 120s, and after a real
   durable-memory contamination bug was found and fixed (see that doc's
   "Concrete evidence" section), two real chat questions still failed:
   `qwen3:8b` timed out at the full 120s, then `ministral-3:8b` also timed
   out at the full 120s, before falling back to `granite3.3:2b` — a model
   that does not reliably invoke tools, so it produced a fluent, confident,
   wrong answer instead of calling `bloomboss_report`. One full turn took
   379.5 seconds. This is resource contention on `karmo-ai01`, not a
   memory bug and not an under-provisioned timeout.

Raising the timeout further treats a symptom. Moving the work to idle,
dedicated hosts (Worker01/02) is the actual fix — but Kamara correctly
pushed back that "move it to Worker01/02" by itself is not a router, it's
just relocating the same hardcoded list. A real router has to decide,
per request, *which* fit host/model to use, detect when one is degraded,
fail over without silently degrading answer quality, and leave a record
of why it chose what it chose. That is what the rest of this document
designs.

## 2. Research performed before writing this plan

Four sequential research passes were run specifically so this plan would
be built on established real-world patterns, not invented from scratch.
Kamara's explicit instruction: document the finding, then use it plus a
fresh read of KARMO itself before writing the plan.

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
  This is the general-case version of exactly what's happening on
  `karmo-ai01` (Postgres + Qdrant + gateway + Ollama, one 8GB box).
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
  host. This is a ready-made, zero-new-infrastructure health signal KARMO
  can poll on `karmo-ai01`, Worker01, and Worker02 today.

### Pass 3 — authority boundaries / mixed-resource scheduling

A dedicated research pass on this was launched and had not yet returned
at the time this section was written. **This section is a placeholder —
do not treat it as complete.** It will be filled in from that pass's
findings the same day they return, in this file, not a new one. Until
then, the authority-model section already established in
`KARMO_ORCHESTRATION_AND_MODEL_ROUTING.md` (models may reason/propose/use
scoped capabilities; models never gain standing authority merely by being
reachable) governs, and nothing in Section 4 below is allowed to weaken it.

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
  real response, and is the standard way to validate a new routing
  policy's correctness/latency before it can affect a single real answer.
  Canary rollout (percentage-based traffic split, e.g. 90/10 → 50/50) is
  the standard next step once shadow output looks right. Seldon-style
  frameworks favor this for policy-driven/custom-logic routing
  specifically, which is KARMO's case (not a generic A/B traffic split).
- **Separating router reasoning from model output**: the clearest framing
  found is that a *model gateway* — the layer that sees real production
  signals (load, cache state, fallback path, per-request governance) — is
  where explainability has to live, not the model's own output. A router
  should be able to explain "why this host/model" in plain terms
  independent of what the chosen model then said, and that explanation
  should be logged as its own record, not embedded in or inferred from
  the chat transcript. The sources also warn explicitly against
  after-the-fact/theater explanations that don't reflect the actual
  decision path — the logged reasoning has to be the real signal values
  read at decision time, not a narrative generated afterward.

## 3. What actually needs to be true, given all of the above

Translating the research into rules that fit KARMO's actual scale (single
household deployment, single-digit hourly requests, three hosts, not a
cloud fleet):

1. **Health signal**: poll Ollama's native `/api/ps` on `karmo-ai01`,
   Worker01, and Worker02. This is the router's primary live signal —
   no new infrastructure, no synthetic health check, an officially
   documented endpoint built for this exact purpose.
2. **Routing strategy**: capability-based dispatch first (which hosts can
   even serve tool-calling — i.e., have a tool-capable model loaded),
   then prefer the least-loaded fit host among those. This is closer to
   RouteLLM's "route" than "cascade" — KARMO's actual problem is
   contention, not cost, so picking the right host up front beats trying
   one host repeatedly and escalating only after each failure.
3. **Fallback must be capability-typed, not positional.** The current
   `_CHAT_EXPOSED_TOOLS` fallback chain in `core-service/core_service/
   operator.py` falls back by list position (qwen3 → ministral → granite)
   with no concept of "granite doesn't reliably call tools." A
   capability-typed fallback chain must never silently cross from
   tool-capable to non-tool-capable — if every tool-capable candidate
   fails, the correct behavior is a clear, honest "I couldn't reach a
   capable model right now," not a fluent wrong answer from a model that
   was never a real candidate for this request.
4. **Circuit-breaker windows must be time-based and small**, not
   resilience4j's default 100-call sliding window — KARMO will not see
   100 tool-calling calls in any reasonable evaluation period. A window
   like "last 10 minutes" or "last N attempts where N is single digits"
   is the right shape.
5. **Router decisions get their own audit record**, separate from the
   chat turn's model output — which host, which model, what signal values
   were read (`/api/ps` state, recent latency, breaker state), and why,
   logged at decision time. This must never be reconstructed after the
   fact from the transcript.
6. **Idempotency-key discipline is a prerequisite, not an add-on, for any
   future non-READ tool exposure.** It is not required today because
   every capability in `_CHAT_EXPOSED_TOOLS` is hard-gated to
   `CapabilityClass.READ` — but the hard rule in
   `docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md`
   that no non-READ capability may ever enter that allow-list must stay
   in force *until* this idempotency design exists, not just until
   someone remembers to think about it.
7. **Any new routing policy ships shadow-mode first.** Before a routing
   change is allowed to affect a real answer, it runs alongside the
   current behavior, logging what it *would* have chosen, for a period
   long enough to see real traffic patterns — this directly serves
   Kamara's standing concern about not destabilizing what currently works
   while fixing what doesn't.

## 4. Phased build plan

Each phase requires its own System-Fit Review and Invariant Impact Review
at the time it is actually implemented, per the standing rules in
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. Nothing here is a
deployment order.

- **Phase A — host health signal.** Add a small poller that calls
  `/api/ps` on `karmo-ai01`, Worker01, and Worker02, and exposes current
  loaded-model/load state to the operator. This is the prerequisite for
  everything else and has no behavior change by itself.
- **Phase B — capability-based dispatch to Worker01/02.** This is the
  previously-agreed Phase 2 (worker round-trip proof) + Phase 3 (chat
  routes to workers) from the AskUserQuestion decision, now informed by
  Phase A's signal: chat tool-calling prefers an idle, dedicated,
  tool-capable worker over contended `karmo-ai01` when Phase A shows one
  available, and only falls back to `karmo-ai01` when no worker is fit.
- **Phase C — capability-typed fallback enforcement.** Rework the
  fallback chain in `operator.py`'s tool loop so it can never silently
  cross from a tool-capable candidate to a non-tool-capable one; an
  exhausted capable-candidate list produces an honest failure message,
  not a wrong answer from `granite3.3:2b`.
- **Phase D — router decision audit record.** Log each routing decision
  (host/model chosen, signal values read, reason) as its own record,
  independent of the chat turn's stored output, using the OpenTelemetry
  GenAI attribute shape as a naming reference (not a hard dependency on
  the spec, which is still experimental).
- **Phase E — idempotency-key discipline.** Design and land this *before*
  any capability beyond READ is ever proposed for `_CHAT_EXPOSED_TOOLS`,
  per point 6 above. Not urgent today; a hard prerequisite the moment it
  becomes relevant.
- **Phase F — shadow-mode rollout process.** Establish the mechanism
  (mirror real requests to a candidate routing policy, log what it would
  have chosen, compare against actual outcomes) before any future routing
  *policy* change (not just today's Phase B) is allowed to affect a real
  answer.

## 5. Open research item

The authority-boundary / mixed-resource-scheduling research pass (Section
2, Pass 3) was still running when this plan was first written. When it
returns, its findings get folded into Pass 3 above and Section 3/4 get
re-checked against them — in this file, in place, per the Mandatory
Document Labeling Rule. Do not treat Section 4's phases as authority-model
final until that update happens.

## 6. Safety boundary

This document authorizes no deployment, no production change, and no PR
merge by itself. Building any phase above requires its own System-Fit
Review and Invariant Impact Review at the time it is actually undertaken,
per `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. The hard rule that
no non-READ capability may enter KARMO chat's tool loop
(`docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md`)
remains in force regardless of anything in this plan.
