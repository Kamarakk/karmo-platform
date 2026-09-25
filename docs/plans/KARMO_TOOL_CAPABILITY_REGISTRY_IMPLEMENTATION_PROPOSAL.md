# KARMO Tool / Capability Registry — Implementation Proposal

Status: **PROPOSAL. Not approved. Not started.** Companion to
`docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md` (the architecture)
and `specs/001-tool-capability-registry/spec.md` (the Spec-Kit-shaped
specification). This document proposes *how* the registry could be built,
in phases, if and when Kamara chooses to build it — it does not choose
that for her, and no phase below is authorized by this document alone.

## Why propose phasing now, without implementing

The Extensibility Review already identified this as "the single largest
piece of unbuilt Core surface" and the one place a wrong first
implementation would be expensive to retrofit. A phased proposal lets
Kamara evaluate scope and cost before any Invariant Impact Review or
`/speckit-plan` cycle begins, consistent with the standing rule that
Workload 5/H0.5 scope is chosen, not inferred.

## Proposed phases (each its own future Invariant Impact Review, its own approval)

### Phase A — Schema and manifest validation only

- `public.tool_registry` migration (mirroring `document_registry`'s
  shape: identity, version, lifecycle columns, `UNIQUE(tool_id, version)`).
- A manifest-validation module: given a manifest, refuse or accept per
  FR-001/FR-002 (architecture document sections 2/5). No dispatcher yet —
  registration only, nothing is invocable through this phase.
- Isolated Docker-stack tests only, exactly the existing H0.1–H0.4
  pattern. No production step.
- **Smallest possible slice** — delivers the "refuse rather than guess"
  guarantee before anything can be called at all.

### Phase B — Invocation ledger and report-only auditor

- `public.tool_invocation_ledger` migration.
- A report-only auditor structurally identical to `h04/app/auditor.py`,
  reconciling registry vs. ledger (section 7 of the architecture doc).
- Still no dispatcher — this phase can be built and evidenced entirely
  against synthetic ledger rows, independent of Phase C.

### Phase C — Shared dispatcher and authorization enforcement

- The one shared code path every tool call must go through (FR-003/FR-004).
- Authorization-record checking, reusing the Production Access
  Authorization Gate's shape (not reinventing it).
- This is the phase that actually makes the registry *load-bearing* —
  correspondingly, the phase that most needs its own careful Invariant
  Impact Review (I-09 especially) before implementation, and likely the
  phase where a second independent review pass (Codex or equivalent, per
  the Validation Ladder's rung 7) is warranted before it gates anything
  real.

### Phase D — First real domain tool, end to end

- One single, low-risk `READ`-class tool from whichever domain Kamara
  chooses first (Workstream 5), registered and invoked through the full
  Phase A–C stack, to prove the registry works end-to-end before any
  higher-risk tool is ever registered.
- Deliberately **not** a `financial_action` or `destructive_action` tool —
  those should only be registered once Phase C has already been proven
  safe on a harmless tool first.

## Explicitly out of scope for every phase above

- Choosing which domain (Voice, Media, BloomBoss, KarmoLab, Personal
  Productivity, Finance) gets its first real tool.
- Any actual financial, external-posting, or destructive tool
  implementation.
- Any change to `CLAUDE.md`, `AGENTS.md`, or the Engineering Invariants —
  the registry is designed to sit underneath them unchanged.

## Rough complexity signal (not a committed estimate)

Phase A and B are each comparable in shape and size to the H0.4 registry
work already completed (a migration + one Python module + an isolated
test suite) — a few hours each, based on that precedent. Phase C is
larger: it is genuinely new Core infrastructure (a dispatcher with
authorization enforcement) with no direct precedent yet in this
repository, so it warrants a wider time estimate and its own dedicated
scoping pass rather than a number guessed here.

## Dependencies

- Phase A depends on nothing new — PostgreSQL access exactly as every
  other H0.x phase already has.
- Phase B depends on Phase A's schema existing.
- Phase C depends on Phase A and B, and on the Production Access
  Authorization Gate (already adopted).
- Phase D depends on Phase C and on Kamara's domain choice (Workstream 5).

See `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` for how this
registry work relates to, and could be sequenced against, the six
candidate domain tracks.
