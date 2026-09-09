# KARMO Core v2 — Consolidated Engineering Specification

Status: **PROPOSED. Not implemented. History is not rewritten; nothing
here is marked as already built.** Consolidates every workstream of the
Core v2 Engineering Blueprint Program (2026-09-09) into one reference
document. Companion Spec-Kit artifact:
`specs/002-core-v2-platform/spec.md`.

## Three-way separation, maintained throughout this document

### EXISTING — KARMO Foundation v1 (VERIFIED, declared complete 2026-09-09)

PostgreSQL + Qdrant + Ollama infrastructure; H0.1 transactional outbox
(semantic memory); H0.2 document lifecycle; H0.4 integrity/reconciliation/
recovery; the nine Engineering Invariants; the Mandatory Phase Invariant
Impact Review, Mandatory Project Save Completion Rule, and Mandatory
Production Access Authorization Gate; Spec Kit brownfield adoption. Full
detail: `docs/architecture/KARMO_CURRENT_ARCHITECTURE_MAP.md` (this
program, Workstream 1) and `docs/evidence/foundation-v1/`. **Nothing in
this section changed as a result of this program.**

### PROPOSED — Core v2 (designed and prototyped this program; not implemented in production)

| Component | Design doc | Prototype | Status |
|---|---|---|---|
| Tool/Capability Registry | `docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md` (prior program) | `core-v2-prototypes/tool_registry/` (this program) | Designed + prototyped, isolated, 62 tests passing |
| Approval Engine | this document + `docs/plans/FINANCE_TRADING_SAFETY_SPEC.md` | `core-v2-prototypes/approval_engine/` | Designed + prototyped, isolated, 15 tests passing |
| Job/Event model | this document | `core-v2-prototypes/job_model/` | Designed + minimally prototyped (deliberately not a full scheduler), 25 tests passing |
| Configuration single-sourcing | `docs/architecture/KARMO_CONFIGURATION_SINGLE_SOURCING_DESIGN.md` | `core-v2-prototypes/config_poc/` | Designed + prototyped, 12 tests passing |
| Failure-injection framework | this document | `core-v2-prototypes/failure_injection/` | Designed + prototyped against the above, 13 tests passing |
| Observability | `docs/architecture/KARMO_OBSERVABILITY_DESIGN.md` | none (explicitly no monitoring software installed) | Design only |
| Autonomous-run verification / Trust Score | `docs/architecture/KARMO_AUTONOMOUS_RUN_VERIFICATION_SYSTEM.md` | `core-v2-prototypes/run_evidence/` | Designed + prototyped, 27 tests passing |
| Security/threat model | `docs/architecture/KARMO_CORE_V2_SECURITY_THREAT_MODEL.md` | N/A (analysis document) | Complete |
| Test strategy | `docs/architecture/KARMO_CORE_V2_TEST_STRATEGY.md` | N/A (governs the above) | Complete |

**154 prototype tests pass across the six code components** — see
`docs/evidence/core-v2/` for raw output and JUnit XML. **None of these
prototypes are wired into any production KARMO path.** Adopting any of
them into a real implementation is a separate, future, explicitly-approved
decision (per the implementation dependency graph,
`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`), not a
consequence of this specification existing.

### FUTURE — Domain capabilities (not designed in implementation detail; readiness-checked only)

| Domain | Readiness spec | Verdict |
|---|---|---|
| BloomBoss | `docs/plans/BLOOMBOSS_READINESS_SPEC.md` | Fits Core v2's proposed abstractions directly; no new Core surface required |
| Voice | `docs/plans/VOICE_MEDIA_READINESS_SPEC.md` | **Requires genuinely new Core surface** (continuous-capability model, streaming) beyond anything designed this program |
| Media | `docs/plans/VOICE_MEDIA_READINESS_SPEC.md` | Mostly fits Core v2 (Job/Event model); needs its own media registry and a large-artifact reference convention |
| KarmoLab | `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` (prior program) | Fits directly; recommended lowest-risk proving ground |
| Personal Productivity | `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` (prior program) | Fits directly |
| Finance/Trading | `docs/plans/FINANCE_TRADING_SAFETY_SPEC.md` | Fits Core v2 for every tier except trade execution, which needs its own separate governance conversation before design even begins |

**No domain above is chosen as the first post-foundation capability by
this document.** That choice remains Natalie's, informed by
`docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` and
`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md` (this program).

## Governing principle, restated once for the whole specification

Every PROPOSED component above is built as a mechanical enforcement layer
for KARMO's *existing* invariants (I-01 through I-09) and existing
approval model (the Autonomous Execution Contract, the Production Access
Authorization Gate) — not a competing governance system. Where any
PROPOSED component's design and an existing invariant could be read as
disagreeing, the invariant governs, exactly as every other KARMO document
already states for itself.

## What changed in the repository tonight vs. what is merely proposed

**Changed** (committed, on branches, not merged): the design documents and
prototypes listed in the PROPOSED table above, plus the three domain
readiness specs and this document. **Not changed**: any file under
`test/h01/`, `h02/`, `h03/`, or `h04/` (Foundation v1's actual
production-path code), any governance document, any production system.
Full accounting: `docs/evidence/core-v2/` and the final PROJECT SAVE for
this program.
