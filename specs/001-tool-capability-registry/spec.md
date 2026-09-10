# Feature Specification: KARMO Tool / Capability Registry

**Feature Branch**: `001-tool-capability-registry` (not created — this
artifact is a design proposal, not an active feature branch)

**Created**: 2026-09-09

**Status**: **PROPOSAL — not scoped as H0.5, not approved, not started.**
Produced under the Post-Foundation Overnight Readiness Program, Workstream
3, as a Spec-Kit-shaped artifact per that program's instruction to "use
Spec Kit artifacts where appropriate." This is *not* the output of
`/speckit-specify` run against an approved feature — no such approval
exists yet. It exists so that, if and when Natalie chooses this as a
post-foundation capability track, a specification is already drafted for
her review rather than starting from a blank template. Choosing it is
explicitly **not** decided by this document — see
`docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md`.

**Input**: Post-Foundation Overnight Readiness Program, Workstream 3
instruction, plus `docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md` and
`docs/vision/KARMO_PRODUCT_VISION.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register a new domain tool safely (Priority: P1)

A future domain module (e.g. BloomBoss) needs to add a new callable
capability. Its author declares a manifest (tool identity, contract,
I-09 capability class, risk flags) and the registry either accepts it —
making it invocable — or refuses it for a missing/invalid required field,
exactly as `bootstrap_legacy_registry.py` refuses ambiguous legacy data
rather than guessing.

**Why this priority**: without this, no other capability in this document
can exist at all — it is the foundation every other user story depends on.

**Independent Test**: register a manifest missing `capability_class`;
confirm the registry refuses registration rather than defaulting to a
class.

**Acceptance Scenarios**:

1. **Given** a complete, valid manifest, **When** a domain registers a new
   tool, **Then** it becomes invocable and appears in `tool_registry`.
2. **Given** a manifest missing any required field (section 2 of the
   architecture document), **When** registration is attempted, **Then** it
   is refused with the specific missing field named, not silently
   defaulted.

---

### User Story 2 - Invoke a tool at the correct approval level (Priority: P1)

An agent (or a future domain's own logic) wants to call a registered
tool. The shared dispatcher computes the required approval level from the
tool's manifest and blocks the call unless a valid, matching authorization
exists — for a `financial_action` or `destructive_action` tool, this is
unconditionally `EXPLICIT_PER_CALL`, regardless of what the base
`capability_class` alone would have implied.

**Why this priority**: this is the actual enforcement mechanism — without
it, the manifest is just documentation, not a control.

**Independent Test**: attempt to invoke a `financial_action: true` tool
without a matching authorization; confirm it is blocked and logged as
`denied`, never silently downgraded to a lower approval tier.

**Acceptance Scenarios**:

1. **Given** a `READ` tool with no risk flags, **When** invoked with no
   authorization, **Then** it succeeds immediately (floor is `NONE`).
2. **Given** a `REVERSIBLE_WRITE` tool with `financial_action: true`,
   **When** invoked without an `EXPLICIT_PER_CALL`-shaped authorization,
   **Then** the call is blocked and recorded as `denied` in the
   invocation ledger.
3. **Given** a valid, scope-matching, non-expired authorization, **When**
   the same tool is invoked, **Then** it succeeds and the ledger records
   the `approval_reference` used.

---

### User Story 3 - Independently audit what actually happened (Priority: P2)

Natalie (or a future ChatGPT/ops session) wants to confirm no tool was
ever invoked above its declared approval floor, and that every
`financial_action`/`destructive_action` call has a recorded human
approval reference.

**Why this priority**: directly generalizes I-07 (observability) and the
Mandatory Production Access Authorization Gate's authorization-record
requirement to every future domain, not just production access.

**Independent Test**: run the report-only registry auditor against a
populated `tool_invocation_ledger`; confirm it flags any invocation
missing a required approval reference.

**Acceptance Scenarios**:

1. **Given** the invocation ledger and the current registry state,
   **When** the registry auditor runs, **Then** it reports (report-only,
   no write) any invocation whose recorded approval level doesn't match
   what the tool's current manifest would compute.

---

### Edge Cases

- What happens when a tool's manifest is updated (e.g. a financial flag
  added retroactively) after invocations already occurred under the old,
  laxer manifest? → the auditor flags the historical mismatch
  informationally; it does not rewrite ledger history (append-only,
  matching every other KARMO audit trail's non-destructive design).
- How does the system handle a tool whose dependency (another tool or
  Core service) is unavailable? → the dispatcher's health check fails
  closed — the call is refused, not attempted and silently degraded.
- What happens when two domains try to register the same `tool_id`? →
  refused; namespacing by domain prefix is intended to prevent this by
  construction, but the registry still enforces `UNIQUE(tool_id, version)`
  as a hard backstop.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The registry MUST refuse to register a tool manifest
  missing any required field (identity, contract, capability class, risk
  flags, approval computation inputs, operational contract) rather than
  applying a default.
- **FR-002**: The registry MUST compute `human_approval_requirement` from
  `capability_class`, `financial_action`, and `destructive_action` —
  never accept it as an independently-declared manifest field.
- **FR-003**: Every tool invocation MUST pass through one shared
  dispatcher — no code path may call a registered tool's implementation
  directly.
- **FR-004**: The dispatcher MUST block any invocation lacking a valid,
  scope-matching, non-expired authorization at or above the computed
  approval floor.
- **FR-005**: Every invocation, successful or blocked, MUST be recorded in
  an append-only invocation ledger.
- **FR-006**: A `financial_action: true` tool MUST always require
  `EXPLICIT_PER_CALL` approval, with no manifest-level or
  configuration-level override capable of lowering this.
- **FR-007**: The registry auditor MUST be report-only — no code path in
  it may write to the registry or the ledger.
- **FR-008**: Each domain's tools MUST execute within that domain's own
  credential/connection scope, never a shared one, so a failure or
  compromise in one domain's tool cannot affect another's.

### Key Entities *(include if feature involves data)*

- **Tool Manifest**: the declared contract for one tool version — identity,
  domain, schema, capability class, risk flags, operational metadata (see
  architecture document section 2).
- **`tool_registry` row**: the persisted, authoritative record of one
  registered tool version, including lifecycle (`deprecated_at`/
  `superseded_by`).
- **Invocation Ledger entry**: one record per actual call attempt
  (blocked or successful), the audit trail this whole design exists to
  produce.
- **Authorization**: a specific, task-bound, non-reusable grant — the same
  shape the Mandatory Production Access Authorization Gate already
  defines, generalized to any tool call above the `NONE` floor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero tools are invocable without a complete manifest —
  verifiable by attempting registration with each required field missing
  in turn and confirming refusal every time.
- **SC-002**: Zero `financial_action` or `destructive_action` invocations
  ever appear in the ledger without a recorded `approval_reference` —
  verifiable by the report-only auditor against real invocation history.
- **SC-003**: A new domain can register its first tool without modifying
  any Core dispatcher, ledger, or auditor code — proving the registry is
  genuinely domain-agnostic, not requiring a Core change per domain.

## Assumptions

- PostgreSQL remains the authoritative store for `tool_registry` and
  `tool_invocation_ledger`, consistent with every existing KARMO
  authoritative-state table (I-03).
- The Production Access Authorization Gate's authorization-record shape is
  reused as-is for tool-invocation authorizations, not reinvented.
- No domain module (Voice, Media, BloomBoss, KarmoLab, Personal
  Productivity, Finance) is assumed to exist yet — this registry must work
  correctly with zero domains registered, one domain registered, or many.
- Building this registry is itself a future, separately-approved,
  separately-invariant-reviewed implementation effort — this specification
  does not authorize starting it.
