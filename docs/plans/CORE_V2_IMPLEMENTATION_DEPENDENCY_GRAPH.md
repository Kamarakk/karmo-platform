# Core v2 Implementation Dependency Graph

Status: **PLANNING ONLY. No batch below is executed by this document.**
Produced under the Core v2 Engineering Blueprint Program, Workstream 12,
from every finding in Workstreams 1–11 of this same program. Goal: let a
future large autonomous run implement in substantial batches instead of
repeatedly stopping for architecture decisions this program has already
made.

## Classification legend

- **MUST BUILD FIRST** — a real dependency; nothing meaningfully domain-
  specific should start before this exists.
- **CAN PARALLELIZE** — independent of other Core v2 items; order among
  these is a scheduling choice, not a technical constraint.
- **DOMAIN-SPECIFIC** — belongs to exactly one future vertical, not Core.
- **OPTIONAL** — improves quality/robustness but nothing else depends on
  it.
- **DEFER** — real, but lower priority than everything else listed;
  revisit once a genuine need appears.

Size: **SMALL** (< 1 day-equivalent), **MEDIUM** (comparable to one H0.x
phase), **LARGE** (multiple H0.x-phase-equivalents), **VERY LARGE**
(a new category of Core surface, comparable in weight to the Tool
Registry itself).

## Items

| Item | Classification | Size | Depends on |
|---|---|---|---|
| Tool Registry Phase A (schema + manifest validation) | MUST BUILD FIRST | MEDIUM | this program's prototype (already proven) |
| Tool Registry Phase B (ledger + report-only auditor) | MUST BUILD FIRST | MEDIUM | Phase A |
| Configuration single-sourcing (real module, wired into ≥1 existing file as proof) | CAN PARALLELIZE | SMALL | this program's POC (already proven) |
| Approval Engine (real implementation, PostgreSQL-backed) | MUST BUILD FIRST | MEDIUM | this program's prototype (already proven); Tool Registry Phase A (needs `capability_class` to compute authority) |
| Tool Registry Phase C (shared dispatcher + authorization enforcement) | MUST BUILD FIRST | LARGE | Tool Registry Phase A+B, Approval Engine |
| Job/Event model (real implementation) | CAN PARALLELIZE | MEDIUM | can build against Tool Registry Phase A alone; full integration needs Phase C |
| Connection pooling (Core-wide) | CAN PARALLELIZE | SMALL–MEDIUM | none technical; independent of registry work entirely |
| Observability (structured logging + correlation IDs, no monitoring software) | CAN PARALLELIZE | MEDIUM | benefits from existing before Phase C, not strictly required first |
| `karmo_semantic_memory` provenance fix (embedding model/version fields) | CAN PARALLELIZE | SMALL | none; a standalone H0.1-scoped fix |
| `document_memory.get_document_history` pagination fix | CAN PARALLELIZE | SMALL | none; a standalone H0.2/H0.4-scoped fix, same shape as the already-completed H0.4 registry-repair pagination fix |
| Continuous-capability model (wake/listen abstraction) | MUST BUILD FIRST *for Voice specifically* | VERY LARGE | Tool Registry Phase C at minimum; genuinely new Core surface, no existing prototype from this program covers it |
| Streaming-result shape | MUST BUILD FIRST *for Voice specifically* | LARGE | Tool Registry Phase A (extends its `output_schema` concept) |
| Media-specific registry (separate from `document_registry`) | MUST BUILD FIRST *for Media specifically* | MEDIUM | mirrors `document_registry`'s already-proven pattern directly |
| Large-artifact reference convention in tool schemas | DOMAIN-SPECIFIC (Media) | SMALL | Tool Registry Phase A |
| BloomBoss entity schema + domain-scoped tools | DOMAIN-SPECIFIC | LARGE | Tool Registry Phase A+B minimum; Phase C before any external-communication tool |
| KarmoLab read-only tools | DOMAIN-SPECIFIC | SMALL | Tool Registry Phase A+B only — the lowest-cost real domain work possible |
| KarmoLab administration tools | DOMAIN-SPECIFIC | MEDIUM | Tool Registry Phase C; reuses the Production Access Authorization Gate directly |
| Finance market-data/research/paper-trading tools | DOMAIN-SPECIFIC | MEDIUM | Tool Registry Phase A+B only |
| Finance trade-execution tool | DOMAIN-SPECIFIC | LARGE | Tool Registry Phase C fully proven, Approval Engine fully proven, plus its own separate governance conversation with Natalie (unchanged from the prior program's roadmap) |
| Failure-injection framework (real, applied to real Core v2 components) | OPTIONAL now, MUST BUILD FIRST before production trust | MEDIUM | components it will test must exist first |
| Autonomous-run evidence/verification tooling (real, wired to real git/gh) | OPTIONAL | SMALL–MEDIUM | this program's prototype (already proven); needs real subprocess/API implementations of the injected interfaces |
| Security threat-model mitigations requiring code (SSRF allowlist, path-traversal guards in the dispatcher) | MUST BUILD FIRST | SMALL | Tool Registry Phase C |
| Proposed "configuration single-sourcing" invariant (governance) | DEFER | N/A | Natalie's decision; not an implementation item |
| Proposed "tool registration review" governance addition | DEFER | N/A | Natalie's decision; not an implementation item |

## Candidate implementation batches

Sized to give a future autonomous run enough scope to reduce supervision
burden, without bundling unrelated risk tiers together.

### Batch 1 — Core substrate (no domain, no financial/destructive risk)

Tool Registry Phase A+B, Approval Engine (real), Job/Event model (real),
connection pooling, configuration single-sourcing (wired into ≥1 real
file), the two standalone bug fixes
(`karmo_semantic_memory` provenance, `document_memory` pagination).
**Estimated size: LARGE** (several MEDIUM items combined, but each
independently low-risk — pure Core infrastructure, zero external side
effects, zero financial/destructive tools involved).

### Batch 2 — Dispatcher and enforcement

Tool Registry Phase C, the SSRF/path-traversal dispatcher guards,
observability (structured logging + correlation IDs). **Estimated size:
LARGE.** Higher-stakes than Batch 1 (this is what makes authorization
enforcement real) — should not be bundled with any domain tool
registration in the same batch, so a problem here is isolated from "did
the domain logic also break."

### Batch 3 — KarmoLab first real domain (proving ground)

KarmoLab read-only tools end-to-end through Batch 1+2's stack, per the
prior program's own recommendation that this is the safest possible
first real domain exercise. **Estimated size: SMALL**, deliberately —
the point is proving the stack works, not building out KarmoLab fully.

### Batch 4a / 4b / 4c — Domain build-out (mutually independent, pick any subset)

- **4a — BloomBoss internal-only** (inventory, cost, propagation tracking
  — everything not requiring `EXTERNAL_ACTION`). **LARGE.**
- **4b — Finance research stack** (market data, research, analysis,
  backtesting, paper trading — no live execution). **MEDIUM.**
- **4c — Media generation/editing + the media-specific registry.**
  **LARGE**, and technically also needs the large-artifact reference
  convention from the table above.

### Batch 5 — External-action domain work (needs Batch 2 fully proven)

BloomBoss external communication tools, KarmoLab administration tools.
**MEDIUM–LARGE.** Should not start before Batch 2's dispatcher has real
production-shaped evidence behind it (Workstream 13's test strategy, this
program, defines what "proven" means objectively).

### Batch 6 — The two VERY LARGE items (Voice's continuous-capability model, streaming)

Deliberately isolated as their own batch — the single largest unknown
this entire program surfaced, per Workstream 10's own finding. Should not
be bundled with anything else; likely needs its own dedicated design pass
before implementation even starts, closer in weight to this whole
program's Workstream 3 than to a normal implementation batch.

### Not batched — deferred by design

Finance trade-execution (needs its own governance conversation before any
batch, per Workstream 11); the two proposed governance additions
(Natalie's decision, not an implementation task at all).

## What this graph does not do

Choose which batch happens first, or whether Natalie wants Batch 3
(KarmoLab proving ground) before or after committing to a specific
vertical's Batch 4. That remains open — see
`docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md`'s three sequencing
alternatives, unchanged by this document.
