# KARMO Extensibility Review

Reviews the architecture verified in `docs/project-state/CURRENT_STATE.md`
(H0.1–H0.4, as actually implemented, not as aspired to) against
`docs/vision/KARMO_PRODUCT_VISION.md`. Scope discipline, per instruction:
this review only flags a change where a *current, already-made* decision
would create a credible blocker for a future domain. It does not redesign
working components for theoretical elegance, and it does not treat an
unbuilt capability's absence as a defect — KARMO Core has not yet built most
planned platform capabilities, so most of this review is forward guidance
for what gets built next, not a list of things to fix in H0.1–H0.4.

## Method

For each future domain in the vision, ask: does anything H0.1–H0.4 actually
did make that domain harder to add later? Then apply I-01–I-09 to the
answer.

## VOICE

**No blocker found.** Nothing in H0.1–H0.4 touches audio, real-time
streaming, or always-on listening. A future voice module would be new code
against whatever the tool-execution/event-execution platform capabilities
become (not yet built) — it does not need to reuse or fight with the
document/memory schema.

- **I-05 (bounded resources):** a wake/listening interface is the one voice
  capability that could plausibly interact with today's architecture (e.g.,
  if it fed transcripts into `conversation_memory`). Recommendation for
  *when that is built*: treat a continuously-running listener as its own
  resource-bounded process with its own explicit start/stop/backpressure
  design, not an extension of the existing outbox relay's polling loop.
- **I-09:** an always-on microphone capability is itself a capability class
  worth classifying explicitly (closer to EXTERNAL-ACTION than READ) at
  design time.

## MEDIA (image/video)

**No blocker found.** No current code path processes non-text media.

- **I-03 (data authority):** if media generation is added, its authoritative
  store (where the generated file lives, and what row/registry describes
  it) should be a *new*, explicitly declared authority — recommend not
  overloading `public.document_registry` (which encodes text-document
  chunk/embedding semantics specific to the H0.2/H0.4 ingest pipeline) for
  media files. A parallel, media-specific registry table is the extensible
  choice, following the same "registry describes expected state,
  reconciliation checks actual state" pattern H0.4 already established —
  the *pattern* generalizes even though the *table* should not be shared.
- **I-05:** video files introduce a new scale dimension (large file size,
  long processing time) beyond anything H0.1–H0.4 bounded. Flag for
  explicit sizing/timeout decisions when this domain is actually designed,
  not before.

## BLOOMBOSS

**No blocker found**, and one concrete piece of evidence that the existing
patterns generalize well: the H0.1 outbox event already carries a generic
`event_type` field (`semantic_memory.upsert.v1`) rather than a hardcoded
type. A future `bloomboss.sale.recorded.v1` (or similar) event could reuse
the same claim/fencing/idempotency machinery without modifying `outbox.py`
or `transactional_memory.py`'s frozen design — it would need its own
consumer, not a change to the H0.1 relay.

- **I-03:** BloomBoss inventory/sales/customer data needs its own
  authoritative store(s), separate from `conversation_memory`,
  `karmo_memory`, and `document_registry`. Recommendation: when BloomBoss is
  scoped, give it its own schema/table namespace from the start (e.g. a
  `bloomboss` schema or clearly prefixed tables) rather than adding
  business columns to KARMO Core's memory/document tables.
- **I-09:** BloomBoss includes genuinely external, consequential actions
  (posting to social media, messaging a customer, recording a sale that
  affects real inventory/financials). Each needs its own capability
  classification and, per the product vision, sits behind whatever approval
  gate `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` establishes
  for EXTERNAL-ACTION/DESTRUCTIVE capabilities — this review does not need
  to invent that mechanism now; the contract already covers it.

## FINANCE / TRADING

**No blocker found**, with one standing constraint carried forward from the
product vision rather than discovered in code (there is no trading code
yet): **any future trade-execution capability requires an explicit human
approval boundary** unless Kamara separately approves a different model.
This is an I-09 DESTRUCTIVE/HIGH-IMPACT classification by definition, not an
architectural finding about existing code.

- **I-04 (idempotency):** if/when order placement is built, the deterministic-
  identity pattern already proven for outbox events (UUID5 from a stable
  name template) is the right model for order-idempotency keys, to avoid
  double-submitting an order on retry. Recommendation for future design,
  not a current gap.

## KARMOLAB / HOME INFRASTRUCTURE

**No blocker found.** Nothing in H0.1–H0.4 models infrastructure/network
state. The instruction to keep KarmoLab conceptually distinct from KARMO AI
Core is a scoping decision for future work, not a correction to existing
code — there is no existing coupling to undo.

- **I-07:** KarmoLab's natural role is exactly the observability gap
  `docs/project-state/DASHBOARD_INVENTORY.md` already flags. Recommendation:
  when observability is built, consider whether KarmoLab is the right home
  for KARMO's own service/health visibility (not just external
  infrastructure), since I-07 already requires it and no surface exists
  today.

## FUTURE EXTERNAL TOOLS / PLUGINS

**No blocker found, one real gap (expected, not a defect):** there is no
tool-discovery/execution or capability/plugin interface anywhere in the
current codebase. This is the single largest piece of unbuilt "Core"
surface relative to the vision, and it is the one place a wrong first
implementation could genuinely create future coupling:

- **Recommendation (applies to whichever workload builds it first):** design
  the tool/capability registry so a tool's declaration includes its I-09
  capability class and its authoritative-store declaration (I-03) as
  required metadata from day one, rather than adding those as an
  afterthought once a second domain needs them. Getting this generic on the
  first implementation is materially cheaper than retrofitting it once
  BloomBoss, voice, and finance tools all exist with inconsistent shapes.
  This is a recommendation for the relevant future workload's design step,
  not a change to anything that exists today.

## PERSONAL PRODUCTIVITY

**No blocker found.** Projects/documents/reminders/schedules are a natural
consumer of the planned memory and event/task-execution capabilities once
built; nothing in H0.1–H0.4 conflicts with this.

## Summary

No credible architectural blocker was found in H0.1–H0.4 for any listed
future domain. This is expected: the current implementation is narrowly
scoped to conversation memory, document knowledge, and integrity, and none
of it hardcodes a future domain out. The actionable output of this review is
a small set of **forward design recommendations** — carried into
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` and
`docs/vision/KARMO_PRODUCT_VISION.md` — for how the *next* genuinely new
platform surface (tool/capability registry, media/business registries,
observability) should be shaped so it stays domain-agnostic, not a set of
changes to make now to already-accepted H0.1–H0.4 architecture.
