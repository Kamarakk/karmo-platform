# KARMO Constitution

## Core Principles

### I. Governance Subordination (NON-NEGOTIABLE)
This constitution is subordinate to `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`
(I-01–I-09), which remains KARMO's single source of truth for permanent
engineering invariants and governs in any conflict. This constitution
supplements — and never overrides — `AGENTS.md`, `CLAUDE.md`, and the
invariants document.

### II. Invariant Impact Review Before Implementation
Every feature plan under this workflow must complete the Mandatory Phase
Invariant Impact Review (I-01 through I-09) in
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md` before substantial
implementation begins.

### III. Isolated Before Production
Every feature is designed, implemented, and validated against isolated
infrastructure (Docker-based PostgreSQL/Qdrant, synthetic credentials,
non-default ports) before any production step is proposed. Production
access, deployment, or writes require Kamara's separate, explicit
approval per `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`,
regardless of how thoroughly the isolated stage passed.

### IV. Report-Only By Default for Audit/Repair Capability
Any tool that inspects, audits, or repairs state defaults to report-only
behavior; a write requires an explicit, separately-gated flag (e.g.
`--apply`) and is proven report-only-by-default with a write-call-injection
test, not by convention alone.

### V. No Overlapping Test Suites
Each phase/feature maintains one concise acceptance suite, not duplicate or
overlapping suites for the same requirement — validated per
`docs/governance/KARMO_VALIDATION_LADDER.md`'s ten rungs, using the
smallest validation scope justified by the change (I-08).

## Additional Constraints

Validation follows `docs/governance/KARMO_VALIDATION_LADDER.md`. Autonomous
execution within an approved workload follows
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` — its standing
gates (production deployment, destructive operations, external sends,
financial transactions, governance changes) apply regardless of workload or
constitution approval.

## Development Workflow

Invariant Impact Review → `/speckit-specify` → `/speckit-plan` →
`/speckit-tasks` → `/speckit-implement` → validation ladder → evidence →
phase acceptance, per `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`'s
recorded workflow decision.

## Governance

This constitution never restates, weakens, or competes with
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. Any amendment to this
constitution that would change what counts as an engineering invariant is
itself a governance change and requires Kamara's explicit approval, per
the standing gate in `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`.

**Version**: 1.0.0 | **Ratified**: 2026-09-08 | **Last Amended**: 2026-09-08
