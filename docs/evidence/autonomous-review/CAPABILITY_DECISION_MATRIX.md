# Capability Decision Matrix — A/B/C Comparison

**Does not choose Natalie's first capability.** Prepared under the KARMO
Large Autonomous Review, Workstream 9, to make that choice easier —
comparing three concrete options plus a hybrid, on the axes requested.
Builds on `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md` and
`docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md` (prior program)
without repeating their full content.

| Axis | A. Tool/Capability Registry first | B. Voice first | C. BloomBoss first |
|---|---|---|---|
| **User value** | Indirect — no end-user-visible capability by itself | Direct and high — "ears and a mouth," Natalie's own stated long-term goal | Direct and high — real business operations value |
| **Dependency requirements** | None beyond what already exists (isolated prototypes proven, 160/160 tests) | Needs the registry (at least Phase A) **plus** a genuinely new Core abstraction (continuous-capability model) this review confirmed does not exist even as a prototype | Needs registry Phase A+B minimum; Phase C before any external-communication tool |
| **How much Core v2 must exist first** | This *is* the Core v2 work — building it for real (Phase A/B minimum) | The most Core v2 must exist first of the three — registry Phase A/B/C **and** a new abstraction not yet designed in implementation detail (Workstream 10's own top finding) | Moderate — internal tools (inventory, cost) only need Phase A/B; external tools (customer messaging, social posting) need Phase C |
| **Implementation effort** | MEDIUM (Phase A) to LARGE (Phase A+B+C) — sized in the dependency graph | VERY LARGE — the continuous-capability model alone is sized VERY LARGE in the dependency graph, before any Voice-specific work even starts | LARGE overall, but decomposable — internal sub-areas alone are a MEDIUM slice |
| **Security risk** | Low — no domain tool, no external action, no financial action registered yet | Medium-High — an always-on listener is inherently `EXTERNAL_ACTION`-adjacent per the Extensibility Review's own I-09 flag, plus new privacy surface | Medium — internal tools are low-risk (`READ`/`REVERSIBLE_WRITE`); external/financial tools (recording sales, messaging customers) are exactly what the registry's `EXPLICIT_PER_CALL` floor exists for |
| **Ability to demonstrate value quickly** | Low on its own — needs a real tool registered through it to be visible at all (see hybrid option) | Low initially (the new Core abstraction has to exist before any Voice interaction works at all) — but very high once it does | Medium-high — an internal inventory-read tool is fast to stand up once Phase A exists |
| **What can run locally** | Everything — pure Python + PostgreSQL, no external dependency | STT/TTS need a model (local Ollama-hosted, per existing pattern, or an external API — not decided) | Everything for internal tools; external tools need real Palmstreet/website/social credentials |
| **External accounts/services needed** | None | Possibly a speech model provider (or local model, per KARMO's existing Ollama pattern) | Palmstreet API access, website backend access, social platform accounts — for the external sub-areas only; none for internal |
| **Likely first usable milestone** | A registered, invocable `READ` tool (e.g. KarmoLab status) with full authority enforcement proven end-to-end — genuinely useful as a *proof*, not as a product | A working STT→response→TTS round trip for a single, bounded interaction (not full wake/listen) | A working "read current inventory" or "record a sale" tool, usable immediately for real BloomBoss bookkeeping |

## Hybrid option: Registry minimal → Voice MVP and/or BloomBoss MVP

**Tool Registry Phase A only** (manifest validation, no ledger, no
dispatcher yet — smallest possible real slice, sized MEDIUM in the
dependency graph) **→ then either or both**:

- **Voice MVP**: a single bounded STT→respond→TTS tool registered through
  Phase A, explicitly *not* wake/listen (defer the VERY LARGE
  continuous-capability model to its own later, dedicated design pass).
  This sidesteps Voice's biggest unknown while still delivering the
  "ears and a mouth" value directly.
- **BloomBoss MVP**: one or two internal-only tools (e.g. read inventory,
  record a sale) registered through the same Phase A, no external
  communication tools yet (defer Phase C).

This hybrid is attractive because it makes Phase A's value concrete
immediately (a real tool, not just a proven prototype) while deferring
both domains' highest-risk/highest-effort pieces (Voice's continuous
model, BloomBoss's external-communication tools) to a deliberate later
decision rather than blocking on them now.

## What this matrix does not do

Choose. Natalie's decision, informed by this comparison and the fuller
roadmap/dependency-graph documents it summarizes.
