# Feature Specification: KARMO Core v2 Platform

**Feature Branch**: `002-core-v2-platform` (not created — this artifact is
a design proposal, not an active feature branch)

**Created**: 2026-09-09

**Status**: **PROPOSAL — not approved, not started.** Produced under the
Core v2 Engineering Blueprint Program, per that program's own instruction
to "use Spec Kit where appropriate." Supersedes nothing in
`specs/001-tool-capability-registry/spec.md`, which remains valid and is
now one component (Tool Registry) of this broader Core v2 proposal, not a
competing document.

**Input**: Core v2 Engineering Blueprint Program instruction, plus every
Workstream 1–15 output this same program produced, consolidated in
`docs/architecture/KARMO_CORE_V2_SPECIFICATION.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Implement post-foundation capabilities in large batches without repeated architecture stops (Priority: P1)

Kamara wants a future large autonomous run to implement real Core v2
components and eventually domain capabilities without stopping repeatedly
to re-derive design decisions this program already made.

**Why this priority**: this is the primary goal stated by the program that
produced this specification — everything else serves it.

**Independent Test**: hand a future run
`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`'s Batch 1 and
confirm it can proceed using only that document, the architecture map, and
the existing prototypes, without needing a new architecture-design
conversation first.

**Acceptance Scenarios**:

1. **Given** the Batch 1 item list, **When** a future run begins
   implementing Tool Registry Phase A, **Then** it can do so from
   `docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md` and
   `core-v2-prototypes/tool_registry/` alone, without a new design pass.
2. **Given** a domain readiness spec (BloomBoss, Voice/Media, or
   Finance/Trading), **When** that domain's first tool is eventually
   built, **Then** its manifest fits the Tool/Capability Registry's
   existing schema without a schema change.

---

### User Story 2 - Enforce authority boundaries mechanically, not by convention (Priority: P1)

Every tool, regardless of which future domain registers it, must have its
human-approval requirement computed from its actual risk profile, never
independently declared or silently downgraded.

**Why this priority**: the security/safety core of the entire Core v2
proposal — proven, not merely asserted, by this program's own prototype
test suites.

**Independent Test**: `core-v2-prototypes/tool_registry/tests/test_authority_cannot_be_lowered.py`
already is this test, for every `capability_class` × `financial_action` ×
`destructive_action` combination.

**Acceptance Scenarios**:

1. **Given** a `financial_action: true` tool of any `capability_class`,
   **When** its approval requirement is computed, **Then** it is always
   `EXPLICIT_PER_CALL`.
2. **Given** a granted approval for one exact tool call, **When** a
   caller attempts to execute a different tool, a different version, or
   changed arguments against that same approval, **Then** execution is
   refused and the approval is invalidated, per
   `core-v2-prototypes/approval_engine/tests/test_approval_engine.py`.

---

### User Story 3 - Independently verify a future large run's own claims (Priority: P2)

Kamara or ChatGPT wants to check a future Core v2 implementation run's
self-reported results against independent ground truth, not narrative.

**Why this priority**: directly generalizes the lesson from the two prior
programs' own evidence packages (one of which needed its own checklist
corrected for circularity).

**Independent Test**: `core-v2-prototypes/run_evidence/tests/test_schema_and_validator.py`'s
"catches a deliberately-wrong record" tests already prove the verifier
distinguishes a true record from a false one.

**Acceptance Scenarios**:

1. **Given** a run's evidence record claiming a commit that does not
   exist, **When** the independent verifier checks it, **Then** it fails
   that specific check and reports which commit is missing.

### Edge Cases

- What happens when a domain's readiness spec and the Tool Registry's
  schema turn out to disagree once real implementation starts? → the
  registry schema governs (it is Core, domains build on top of it); the
  readiness spec is revised, not the other way around, consistent with
  "domain-agnostic Core, domain-specific modules on top."
- How does the system handle a genuinely new domain need this program
  didn't anticipate (like Voice's continuous-capability model)? → named
  explicitly as a gap (`docs/plans/VOICE_MEDIA_READINESS_SPEC.md`), not
  silently forced into an ill-fitting existing abstraction.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every Core v2 component's design MUST be traceable to an
  existing KARMO invariant (I-01–I-09) it operationalizes, not a
  competing rule — per `docs/architecture/KARMO_CORE_V2_SECURITY_THREAT_MODEL.md`'s
  own coverage analysis.
- **FR-002**: No Core v2 prototype or design MUST be treated as
  implemented, deployed, or authorized for production by virtue of this
  specification's existence.
- **FR-003**: Every proposed governance addition (configuration
  single-sourcing, tool-registration review) MUST remain explicitly
  unadopted pending Kamara's separate decision.
- **FR-004**: The implementation dependency graph MUST be re-derivable
  from the readiness specs and architecture documents, not maintained as
  an independent, driftable source of truth.

### Key Entities *(include if feature involves data)*

See `docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md` (Tool Manifest,
`tool_registry` row, Invocation Ledger entry, Authorization) and this
document's own companion architecture docs for the Approval Engine and
Job/Event model's entities — not repeated here to avoid drift between two
copies of the same definitions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of this program's prototype tests pass (160/160 — 154
  at initial creation, plus 6 more from an independent adversarial review
  that found and fixed 4 real defects, see
  `docs/evidence/core-v2/ADVERSARIAL_REVIEW_FIXES.md` — see
  `docs/evidence/core-v2/`).
- **SC-002**: Zero production access, zero merges, zero governance
  modification occurred in producing this specification (see the
  program's own final report).
- **SC-003**: A future implementer can identify, for any of the six Core
  v2 components, exactly one design document and one prototype directory
  to start from — no component has competing or duplicate design sources.

## Assumptions

- Foundation v1 remains stable and unchanged underneath Core v2 — this
  specification assumes no concurrent Foundation-level change.
- The four PRs from the prior Post-Foundation Overnight Readiness Program
  (#14–#17) and this program's own PRs are reviewed on their own timeline;
  this specification does not assume any particular one is merged first.
- Building any PROPOSED component into a real, production-facing
  implementation is a future, separately-approved decision this
  specification does not make.
