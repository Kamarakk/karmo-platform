# KARMO Product Vision

Status: approved as a **vision/documentation artifact only**. See the notice
at the bottom before reading any section as an implementation commitment.

Governance precedence: this document does not create, weaken, or duplicate
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, `AGENTS.md`, or
`CLAUDE.md`. Where anything below implies a future capability, that
capability is still bound by I-01 through I-09 and by whatever approval
model is current at the time it is actually built.

## The long-term architectural goal

**KARMO is a private, modular personal/business AI platform.** KARMO Core
provides reusable, domain-agnostic platform capabilities. Domain-specific
functionality (a plant-nursery business system, a trading assistant, a
voice interface, etc.) is built *on* KARMO Core, never hard-coded *into* it.

---

## CURRENT CAPABILITIES

What exists today, verified against `docs/project-state/CURRENT_STATE.md`
and committed H0.1–H0.4 evidence. This is deliberately narrow — KARMO today
is a conversational-memory-and-document-knowledge system, not yet a general
platform:

- **Conversation memory** — PostgreSQL `conversation_memory`/`karmo_memory`
  tables; user-prompt-only semantic promotion to Qdrant `karmo_semantic_memory`
  via a transactional outbox relay (H0.1, production).
- **Transactional outbox / event delivery** — durable, idempotent,
  claim-fenced event relay (`karmo-h01-relay`) with deterministic UUID5
  event identity, retry-safe by construction (H0.1, production).
- **Document/RAG knowledge with lifecycle** — SHA-256 content identity,
  document versioning, active/superseded lifecycle, auditable history
  without deletion (H0.2, production).
- **Integrity & reconciliation** — a PostgreSQL `document_registry` as the
  authoritative expected-state record, report-only auditing of
  PostgreSQL↔Qdrant↔archived-file consistency, backup/restore drilled and
  verified (H0.4, production).
- **Governance framework** — nine permanent engineering invariants (I-01
  through I-09) and a mandatory pre-implementation impact review, now
  required for every phase, feature, service, migration, agent, integration,
  and deployment.
- **Persistent project-state record set** — `docs/project-state/` as the
  durable, reconciled source of current state, change history, inventories,
  commands, rollback procedures, and next steps.

What does **not** yet exist, stated plainly so the "planned" section below
is not mistaken for already-built: no general model/reasoning orchestration
layer, no tool-discovery/execution framework, no formal permissions engine
beyond the informal I-09 classification, no dashboard/observability surface
(see `docs/project-state/DASHBOARD_INVENTORY.md`), no plugin/capability
interface, and no domain modules (voice, media, BloomBoss, finance,
KarmoLab, personal productivity).

---

## PLANNED PLATFORM CAPABILITIES (KARMO Core)

These are the reusable, domain-agnostic capabilities KARMO Core is intended
to grow into. Listing them here is planning, not a build order — see
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` for what is actually next,
and the notice at the end of this document.

- **Model/reasoning orchestration** — a place to route a request to the
  right model/reasoning strategy, independent of which domain asked.
- **Persistent memory** — generalizing today's conversation-memory pattern
  (durable, idempotent, versioned) to other memory types as needed.
- **Document/RAG knowledge** — generalizing today's document lifecycle
  pattern beyond the current single knowledge collection.
- **Tool discovery/execution** — a registry of callable capabilities with
  declared inputs, outputs, and — critically — an attached I-09 capability
  class (READ / DRAFT-PROPOSE / REVERSIBLE-WRITE / EXTERNAL-ACTION /
  DESTRUCTIVE-HIGH-IMPACT) at the point each tool is registered, not
  retrofitted later.
- **Permissions** — least-privilege, per-capability, per-domain scoping,
  building on I-09's classification rather than a new ad hoc scheme.
- **Human approval gates** — a first-class mechanism (not per-feature
  bespoke logic) for pausing an action pending explicit approval, reusable
  by every future domain.
- **Auditability** — every consequential action leaves a record of what,
  when, by what component, on what object, why, and with what result —
  generalizing the pattern I-07 already requires.
- **Identity/context** — a coherent model of "who/what is acting" and
  "in what context," so permissions and audit records mean something
  consistent across domains.
- **Event/task execution** — generalizing today's outbox/event pattern
  (deterministic identity, idempotent retry, claim fencing) to
  non-memory background work.
- **Observability** — the dashboard/alerting surface that
  `docs/project-state/DASHBOARD_INVENTORY.md` currently records as absent,
  required by I-07 before any of the above is trusted to run unattended.
- **Capability/plugin interfaces** — the boundary a future domain module
  (BloomBoss, voice, finance, etc.) implements against, so domain code
  never needs to modify KARMO Core to plug in.

---

## FUTURE IDEAS / NOT YET APPROVED FOR IMPLEMENTATION

Everything in this section is a **capability domain to document, not to
build**, until each is separately scoped and separately approved. Order
below is the order given in the request, not a priority ranking.

### VOICE
Speech-to-text, text-to-speech, conversational voice, and — eventually,
where genuinely appropriate — wake/listening interfaces. A wake/listening
interface is an always-on capability with real privacy and resource
implications; it would need its own I-05 (bounded resources) and I-09
(authority/permission boundary) treatment before any implementation
approval, not merely a feature flag.

### MEDIA
Text-to-image, image editing, video generation/editing, and general
media-processing workflows. Media generation/editing implies new bounded-
resource concerns (file size, processing time, storage growth — I-05) and
new authoritative-storage decisions (I-03) distinct from today's document
registry.

### BLOOMBOSS
A plant-nursery/retail business domain: plant inventory, SKU/specimen
tracking where appropriate, imports, purchase cost, landed cost, losses,
inventory quantities, sales, profitability, customers, shipping, Palmstreet
workflows, website/backend workflows, incoming-message assistance,
social-media content, marketing, analytics, and business reporting. This is
a full business-operations domain; it would be built as a module on top of
KARMO Core's planned capabilities (memory, tool execution, permissions,
approval gates), not merged into KARMO Core itself. Actions with real
financial or customer-facing consequence (recording a sale, posting to
social media, messaging a customer) fall under the approval-boundary rule
below and in `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`.

### FINANCE / TRADING
Market research, watchlists, portfolio analysis, stock analysis, options
analysis, strategy/risk analysis, and broker integration as a future
capability.

**Any future capability that can execute a financial trade MUST require an
explicit human approval boundary unless Kamara separately approves a
different governance model in the future.** This is a standing constraint
on this capability domain specifically, not merely a default that a busy
workload can quietly opt out of — a trade-execution action is, by
definition, DESTRUCTIVE/HIGH-IMPACT under I-09's classification.

### KARMOLAB / HOME INFRASTRUCTURE
Infrastructure inventory, monitoring, alerts, home/lab integrations, and
network/service visibility. **KarmoLab is conceptually distinct from KARMO
AI Core** — it observes and reports on infrastructure; it is not where
KARMO's own reasoning/memory/document capabilities live, even though KARMO
Core may eventually consume KarmoLab's observability data as one input.

### PERSONAL PRODUCTIVITY
Projects, documents, reminders, schedules, workflows, and other future
personal tools.

---

## Explicit non-authorization notice

**Documenting the planned platform capabilities and future capability
domains above does not authorize implementing any of them during the
current foundation work.** The only work currently authorized is what is
described in `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` and approved,
workload by workload, by Kamara. This vision document exists so that
foundation-level decisions (naming, schema shape, coupling) can be made with
this future direction in mind — see
`docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md` — not so that any part of
it can be treated as a standing work order.
