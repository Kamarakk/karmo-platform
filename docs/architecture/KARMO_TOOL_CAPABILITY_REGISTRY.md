# KARMO Tool / Capability Registry — Architecture

Status: **DESIGN ONLY. Not implemented, not approved for implementation.**
Produced under the Post-Foundation Overnight Readiness Program, Workstream
3. This document does not choose Kamara's first post-foundation
capability and does not authorize building anything described here — see
`docs/vision/KARMO_PRODUCT_VISION.md`'s explicit non-authorization notice,
which applies equally to this document.

Anticipated by `docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md` ("the
single largest piece of unbuilt Core surface... getting this generic on
the first implementation is materially cheaper than retrofitting") and
`docs/vision/KARMO_PRODUCT_VISION.md`'s "Tool discovery/execution" and
"Permissions" planned platform capabilities.

## Governing principle

**This registry does not create a second governance system.** Every
gating decision it makes is a direct application of
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s I-09 capability
classification and `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`'s
approval boundaries — the registry's job is to make those already-approved
rules *mechanically enforceable and impossible to bypass by omission* as
new tools are added, not to invent new rules. Where this document and the
invariants document ever appear to disagree, the invariants document
governs, exactly as it already states for every other file in this repo.

## 1. Tool identity

Every tool has a globally stable, namespaced identifier:

```
tool_id: "<domain>.<subdomain>.<action>"
```

Examples: `karmo-core.memory.search_documents`,
`bloomboss.inventory.record_sale`, `finance.trading.place_order`,
`karmolab.infra.restart_service`. Namespacing by domain is mandatory —
prevents collision as multiple domains register tools, and makes
"which domain owns this" answerable by inspection alone (I-09's
least-privilege principle needs a clear owner to scope credentials to).

## 2. The Tool Manifest

Every tool registers by declaring a manifest — a structured, versioned
record, not free-form code comments. This is the single artifact that
makes I-09 classification "required metadata from day one" (per the
Extensibility Review) rather than an afterthought.

```yaml
tool_id: bloomboss.inventory.record_sale
domain: bloomboss
version: "1.0.0"
description: >
  Records a completed sale against current inventory, decrementing
  stock and creating a revenue-recognized transaction record.

# --- Contract ---
input_schema: <JSON Schema>
output_schema: <JSON Schema>

# --- I-09 classification (required, not inferred) ---
capability_class: REVERSIBLE_WRITE   # READ | DRAFT_PROPOSE | REVERSIBLE_WRITE | EXTERNAL_ACTION | DESTRUCTIVE_HIGH_IMPACT
read_scope: [bloomboss.inventory, bloomboss.products]
write_scope: [bloomboss.inventory, bloomboss.sales]

# --- Orthogonal risk flags (see section 4) ---
external_side_effects: false
financial_action: true        # affects real revenue/inventory valuation
destructive_action: false

# --- Derived, not independently settable (see section 5) ---
human_approval_requirement: EXPLICIT_PER_CALL   # forced by financial_action

# --- Operational contract ---
network_requirements: []                 # internal DB/Qdrant only
secret_requirements: [bloomboss.db.credential_ref]   # reference only, never a value
invocation_identity: "uuid5(bloomboss.sale, order_id)"   # deterministic, retry-safe
timeout_seconds: 10
retry_policy: {max_attempts: 3, backoff: exponential, cap_seconds: 60}
idempotent: true
idempotency_mechanism: "order_id uniqueness constraint; retry is a no-op on conflict"
rollback_or_compensation: "compensating void-sale tool (bloomboss.inventory.void_sale), itself its own REVERSIBLE_WRITE tool with its own approval requirement — never an in-place delete/rewrite"
health_check: "bloomboss.db reachability, checked at registry startup and on-demand"
deprecation_policy: "superseded_by field once a v2 exists; old version remains invocable and audited until explicitly retired by Kamara"
dependencies: [bloomboss.inventory (read), karmo-core.audit-log (write)]
observability: "every invocation logged to the invocation ledger (section 7) with input hash, output summary, actor, capability_class, approval_reference, result, duration"
failure_isolation: "a failure in this tool must not affect any other domain's tools -- enforced by the registry running each domain's tools against that domain's own connection/credential scope, never a shared one"
```

Every field above is **mandatory at registration time** for every tool,
including `READ` tools — most fields simply take trivial values for a
`READ` tool (see section 6's worked example), but the registry refuses to
register a tool missing any field, mirroring the "refuse rather than
guess" pattern `bootstrap_legacy_registry.py` and `registry_repair.py`
already established for KARMO's data-integrity tools. A tool without a
declared capability class is not registered with a default — it is
rejected.

## 3. I-09 capability classes (reused verbatim, not redefined)

`READ`, `DRAFT_PROPOSE`, `REVERSIBLE_WRITE`, `EXTERNAL_ACTION`,
`DESTRUCTIVE_HIGH_IMPACT` — exactly I-09's five tiers. The registry adds
no sixth tier. What the registry adds is *mechanical enforcement*: each
tier maps to a minimum `human_approval_requirement` floor (section 5), and
the registry's invocation path physically cannot skip that floor — there
is no code path that calls a tool's implementation without first
resolving and checking its approval requirement.

## 4. Orthogonal risk flags

`capability_class` alone under-specifies risk for two dimensions I-09's
base taxonomy doesn't separately name, both explicitly required by this
workstream's instructions:

- **`financial_action`** (bool): can this tool move money, place/cancel/
  modify a trade or order, or otherwise create real financial exposure?
- **`destructive_action`** (bool): can this tool delete, overwrite without
  recoverable history, or cause an irreversible infrastructure change
  (service restart, config change, container/data deletion)?

These are **not new capability classes** — they are orthogonal flags that
can only ever *raise* the effective approval requirement above what
`capability_class` alone implies, never lower it (section 5). A tool can
be `REVERSIBLE_WRITE` and `financial_action: true` at once (e.g. recording
a sale) — the registry's job is to still require the stricter of the two
signals, not to force every financial tool into `DESTRUCTIVE_HIGH_IMPACT`
when it genuinely is reversible in the data sense (a sale can be voided),
while still never letting the "reversible" classification alone excuse it
from real human sign-off before a real financial effect occurs.

## 5. Human-approval requirement (computed, not declared)

```
human_approval_requirement = MAX(
    floor_for(capability_class),
    EXPLICIT_PER_CALL if financial_action else NONE,
    EXPLICIT_PER_CALL if destructive_action else NONE,
)

floor_for(READ)                    = NONE
floor_for(DRAFT_PROPOSE)           = NOTIFY_ONLY
floor_for(REVERSIBLE_WRITE)        = EXPLICIT_PER_SESSION_OR_TASK
floor_for(EXTERNAL_ACTION)         = EXPLICIT_PER_CALL
floor_for(DESTRUCTIVE_HIGH_IMPACT) = EXPLICIT_PER_CALL
```

This directly, structurally implements this program's explicit
instruction — **"Financial execution must retain explicit human
approval"** — as code, not policy prose: `financial_action: true` always
forces at least `EXPLICIT_PER_CALL`, regardless of what `capability_class`
alone would have implied, and no manifest field can override this
computed value; `human_approval_requirement` is derived, never
independently settable, so a tool author cannot accidentally (or
intentionally) under-declare it.

`EXPLICIT_PER_CALL` for a financial or destructive tool means exactly what
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s new Mandatory
Production Access Authorization Gate already defines for production
access generally: a specific, task-bound, non-reusable grant — this
registry is that same pattern, generalized from "production access" to
"any tool invocation above the READ floor."

## 6. Four worked examples, as required by this workstream

| | Harmless read-only | External-posting | Business mutation | Destructive infra | Financial/trading |
|---|---|---|---|---|---|
| Example | `karmolab.infra.get_service_status` | `bloomboss.social.post_update` | `bloomboss.inventory.record_sale` | `karmolab.infra.restart_service` | `finance.trading.place_order` |
| `capability_class` | READ | EXTERNAL_ACTION | REVERSIBLE_WRITE | DESTRUCTIVE_HIGH_IMPACT | DESTRUCTIVE_HIGH_IMPACT (per `KARMO_PRODUCT_VISION.md`: "a trade-execution action is, by definition, DESTRUCTIVE/HIGH-IMPACT") |
| `external_side_effects` | false | true (a real post appears publicly) | false | false | true (a real order reaches a broker) |
| `financial_action` | false | false | true | false | true |
| `destructive_action` | false | false | false | true | true (a fill cannot be un-filled) |
| `human_approval_requirement` | NONE | EXPLICIT_PER_CALL | EXPLICIT_PER_CALL (financial floor, even though REVERSIBLE_WRITE alone would only need per-session) | EXPLICIT_PER_CALL | EXPLICIT_PER_CALL (hard floor — cannot be downgraded by any future domain-level convenience setting) |
| `rollback_or_compensation` | N/A — nothing changed | a delete/edit tool exists, but is itself its own audited action — the fact a post *was* publicly visible is not undone | a compensating `void_sale` tool, itself gated | N/A or domain-specific; must be evaluated per tool, may be genuinely irreversible | N/A — only a new, separately-approved compensating trade is possible |
| `failure_isolation` | isolated to KarmoLab's own scope | isolated to BloomBoss's own credential scope | isolated to BloomBoss's own store | isolated to KarmoLab's own scope; must never share credentials with any other domain | isolated to the finance domain's own broker credential, never reused elsewhere |

## 7. The registry itself: architecture, not just the manifest schema

Following the same "PostgreSQL is the authoritative expected-state
record, reconciliation checks actual state" pattern H0.4 already
established for `document_registry` — reusing the proven pattern rather
than inventing a new one:

- **`public.tool_registry`** (new table, new domain, own migration):
  one row per registered tool version, storing exactly the manifest
  fields from section 2. `UNIQUE(tool_id, version)`. Deprecated versions
  are never deleted — `deprecated_at`/`superseded_by` columns, mirroring
  `document_registry`'s own lifecycle columns exactly.
- **`public.tool_invocation_ledger`** (new table): one row per actual
  invocation — `tool_id`, `version`, `invocation_id` (deterministic where
  the manifest declares one), `actor`/context identity, `capability_class`
  and computed `human_approval_requirement` *at the time of the call*,
  `approval_reference` (who/what approved it, or `NULL` for `NONE`-floor
  tools), input hash (never the raw payload if it could contain a
  secret), output summary, `status` (`succeeded` / `failed` /
  `awaiting_approval` / `denied`), timestamps, duration. This is the
  concrete mechanism satisfying "auditability" and I-07 for every future
  tool call, generalizing the pattern the H0.1 outbox and H0.4 registry
  already use.
- **A report-only registry auditor**, structurally identical to
  `h04/app/auditor.py`: reconciles `tool_registry` (expected: which tools
  exist, what they're allowed to do) against the invocation ledger
  (actual: what was called, at what approval level) — flags any
  invocation whose recorded `human_approval_requirement` doesn't match
  what the manifest would compute today (a manifest changed after the
  fact, e.g.), any invocation missing a required `approval_reference`,
  and any tool invoked that isn't in the registry at all. Report-only,
  same guarantee as `auditor.py`: no write path, ever.
- **Invocation dispatch**: a single, shared dispatcher is the *only* code
  path allowed to call a tool's implementation. It resolves the manifest,
  computes `human_approval_requirement`, checks for a valid, non-expired,
  scope-matching authorization (same shape as the Production Access
  Authorization Gate's authorization record) before any call above
  `NONE`, writes the ledger row, invokes the tool inside its own
  domain-scoped credential/connection context (never a shared one — this
  is what makes `failure_isolation` structural rather than a per-tool
  promise), and enforces `timeout_seconds`/`retry_policy` uniformly so no
  individual tool has to reimplement bounding logic (directly answering
  Workstream 4's F3/F5 findings — connection pooling and configuration
  single-sourcing become properties of this one shared layer, not
  something every future domain module reimplements or forgets).

## 8. Versioning and deprecation

Semantic version per tool (`MAJOR.MINOR.PATCH`). A breaking input/output
contract change is a new `MAJOR` version, registered alongside the old one
(never in place) — mirroring H0.2's document-version lifecycle exactly:
old and new coexist, `is_active`/`superseded_by`-shaped columns track
which is current, nothing is silently replaced. A deprecated tool version
remains invocable (so in-flight callers don't break) but the registry
auditor flags any *new* invocation of a deprecated version as
informational, not an error — the same "known, explained, not silently
hidden" pattern `LEGACY_PROVENANCE_UNVERIFIED` already established.

## 9. Dependency relationships

A tool's manifest declares which other tools/Core services it depends on
(section 2's `dependencies` field). The registry can therefore answer
"what breaks if I remove/change this" by graph traversal before a change
is made — directly useful for Workstream 5's roadmap dependency graph, and
for any future domain's own internal planning.

## 10. What this design deliberately does not do tonight

- No code. No migration file. No registry table actually created.
- No decision about which domain (Voice, Media, BloomBoss, KarmoLab,
  Personal Productivity, Finance) gets its first tool — that remains
  entirely Kamara's choice (Workstream 5).
- No change to I-01 through I-09, to the Autonomous Execution Contract, or
  to the Production Access Authorization Gate — this design is built to
  sit underneath all three unchanged, translating their existing rules
  into a mechanically-enforced shape for a multi-tool future, not
  replacing or duplicating them.

See also `specs/001-tool-capability-registry/spec.md` (Spec-Kit-shaped
specification artifact) and
`docs/plans/KARMO_TOOL_CAPABILITY_REGISTRY_IMPLEMENTATION_PROPOSAL.md`
(phased build proposal) for the rest of this workstream's output.
