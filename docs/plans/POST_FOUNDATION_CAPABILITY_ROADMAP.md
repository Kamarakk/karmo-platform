# Post-Foundation Capability Roadmap

Status: **Candidate tracks for analysis only. Does not choose Natalie's
first post-foundation capability.** Produced under the Post-Foundation
Overnight Readiness Program, Workstream 5, from
`docs/vision/KARMO_PRODUCT_VISION.md`,
`docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md`,
`docs/architecture/KARMO_TOOL_CAPABILITY_REGISTRY.md` (Workstream 3, this
same program), and current `docs/project-state/` records.

## Shared Core requirements (apply across most/all tracks)

Every track below depends, to varying degrees, on Core infrastructure
that does not yet exist or has known gaps (per Workstream 4's adversarial
review, this same program):

1. **Tool/Capability Registry** (Workstream 3) — Phase A–C, at minimum
   Phase A+B before any domain registers a real tool; Phase C before any
   domain registers a `financial_action`/`destructive_action` tool.
2. **Connection pooling** (Workstream 4, F3) — every domain adding its own
   polling/worker process compounds the existing no-pooling pattern;
   worth fixing once, centrally, before multiple domains multiply it.
3. **Configuration single-sourcing** (Workstream 4, F5) — the same
   reasoning; a natural registry/Core-layer consolidation.
4. **Embedding-model provenance** (Workstream 4, F4) — Voice and Media
   both plausibly introduce new embedding/model dependencies; the gap
   already present in `karmo_semantic_memory` should not be repeated for
   a second collection.
5. **Observability/dashboard surface** — `docs/project-state/DASHBOARD_INVENTORY.md`
   already records this as absent; the Extensibility Review already flags
   it as required "before any of the above is trusted to run unattended."
   Every track with a background/always-on component (Voice's wake model,
   KarmoLab's monitoring, any scheduled BloomBoss/Finance job) needs this
   more than a request/response-only track does.

## Per-domain analysis

### VOICE

- **Sub-areas**: speech-to-text, wake/listen model, text-to-speech,
  conversation orchestration, interruption handling.
- **Complexity**: HIGH. Wake/listen is a genuinely new architectural
  category — an always-on process, not a request/response tool, with real
  resource and privacy implications the Extensibility Review already
  flagged (I-05: needs its own explicit start/stop/backpressure design;
  I-09: closer to `EXTERNAL_ACTION` than `READ` as a capability class).
- **Risks**: privacy (always-listening surface), resource consumption
  (continuous audio processing), latency requirements for interruption
  handling that don't map cleanly onto the registry's request/response
  dispatcher model as designed (Phase C may need a streaming/session
  extension, not covered by tonight's design).
- **Prerequisites**: Registry Phase A+C (voice tools need real
  authorization gating, e.g. "start listening" is itself worth an
  `EXTERNAL_ACTION`-shaped approval floor); a resource-bounded process
  model distinct from the existing outbox-relay polling pattern.
- **Parallelizable with**: Media, Personal Productivity (no shared data
  dependency). **Not** easily parallelizable with KarmoLab (both may
  compete for the same host's audio/compute resources on a single-node
  deployment — Workstream 4's F7).

### MEDIA

- **Sub-areas**: image generation, image editing, video workflows.
- **Complexity**: MEDIUM–HIGH. Generation/editing calls are naturally
  `EXTERNAL_ACTION`-or-higher if they call a paid third-party API, or
  `REVERSIBLE_WRITE` if purely local; video specifically introduces a new
  scale dimension (file size, processing time) the Extensibility Review
  already flagged as needing explicit sizing/timeout decisions (I-05).
- **Risks**: storage growth (large media files — Workstream 4 did not
  find an existing bounded-storage pattern for non-text content anywhere
  in the current codebase); a new authoritative-store decision (I-03) —
  the Extensibility Review already recommends a media-specific registry,
  not overloading `document_registry`.
- **Prerequisites**: Registry Phase A+B minimum; a storage-quota/cleanup
  policy that doesn't exist yet for any KARMO domain today.
- **Parallelizable with**: Voice, Personal Productivity, KarmoLab.

### BLOOMBOSS

- **Sub-areas**: inventory, plant/product records, orders, customer
  communication, social media assistance, marketing, website/backend
  integrations, analytics.
- **Complexity**: HIGH, but decomposable — this is the widest track (8
  sub-areas), several of which are independently shippable
  (`REVERSIBLE_WRITE` inventory tools) while others are inherently
  `EXTERNAL_ACTION` (customer communication, social posting) and need
  Registry Phase C before they can be built responsibly at all.
- **Risks**: real financial/customer consequence on several sub-areas
  (recording a sale, messaging a customer) — the Autonomous Execution
  Contract and Extensibility Review already require its own approval gate
  for exactly these; genuinely the track most likely to need the
  registry's `financial_action` flag exercised for real, soon.
- **Prerequisites**: its own dedicated schema/table namespace (Extensibility
  Review's explicit recommendation — never business columns added to
  Core's memory/document tables); Registry Phase A minimum for inventory,
  Phase C before any customer-communication or social-posting tool.
- **Parallelizable with**: internally, inventory/analytics work can start
  before customer-communication/social work (different risk tier, same
  domain) — a natural internal sequencing split within this one track.

### KARMOLAB

- **Sub-areas**: infrastructure visibility, monitoring, controlled
  administration.
- **Complexity**: MEDIUM. Read-only visibility/monitoring is the
  lowest-risk work in this entire roadmap (`READ`-class, `NONE` approval
  floor) — genuinely a strong Phase-D "first tool" candidate per the
  registry implementation proposal, since it proves the registry
  end-to-end without touching money, customers, or destructive actions.
  "Controlled administration" (restarting a service, changing config) is
  the opposite extreme — `DESTRUCTIVE_HIGH_IMPACT`, same tier as the
  Production Access Authorization Gate already governs for KARMO's own
  production, and should reuse that exact mechanism rather than a
  KarmoLab-specific one.
- **Risks**: scope bleed — the product vision explicitly requires
  KarmoLab stay conceptually distinct from KARMO AI Core (it observes
  infrastructure; it is not where KARMO's own reasoning/memory lives).
  Easy to violate accidentally if its tools aren't domain-namespaced from
  day one.
- **Prerequisites**: Registry Phase A minimum for the read-only half;
  Phase C (and likely reuse of the Production Access Authorization Gate
  directly) before any administration tool.
- **Parallelizable with**: everything — no data dependency on any other
  track. Best candidate for genuinely independent, low-risk first work.

### PERSONAL PRODUCTIVITY

- **Sub-areas**: reminders, planning, communications, workflows.
- **Complexity**: LOW–MEDIUM for reminders/planning (naturally
  `REVERSIBLE_WRITE`, internal-only); MEDIUM–HIGH for "communications" if
  that means sending anything externally (email, messaging) — that
  sub-area alone jumps to `EXTERNAL_ACTION` and needs the same
  per-call-approval treatment as BloomBoss's customer communication.
- **Risks**: the most likely track to quietly accumulate cross-domain data
  mixing (I-09's explicit prohibition: "do not combine unrelated
  personal, business, infrastructure, security, or other sensitive data
  domains merely because KARMO technically has access to them") —
  reminders/planning naturally want to reference BloomBoss or Finance
  data "for convenience," which is exactly the coupling I-09 already
  warns against.
- **Prerequisites**: Registry Phase A+B for the internal-only sub-areas;
  Phase C before any "communications" tool that sends externally.
- **Parallelizable with**: Voice, Media, KarmoLab. Shares the most
  conceptual surface with BloomBoss (both want scheduling/communication
  primitives) — worth designing the underlying primitive once, generically,
  if both tracks are ever pursued close together, rather than twice.

### FINANCE / TRADING

- **Sub-areas**: market research, portfolio/trade analysis, paper trading,
  strategy evaluation, eventual broker integration, explicit human
  approval before financial execution.
- **Complexity**: research/analysis sub-areas are LOW-MEDIUM
  (`READ`-class, no different in kind from KarmoLab's read-only work);
  paper trading is MEDIUM (simulated `REVERSIBLE_WRITE`, no real money,
  genuinely safe to build and exercise the registry's financial-flag
  machinery without real risk); **live broker integration is the single
  highest-risk sub-area in this entire roadmap** — `DESTRUCTIVE_HIGH_IMPACT`
  and `financial_action: true` simultaneously, the hard-floor
  `EXPLICIT_PER_CALL` case the registry design (Workstream 3) exists
  partly to guarantee can never be silently downgraded.
- **Risks**: exactly the standing constraint already recorded in
  `docs/vision/KARMO_PRODUCT_VISION.md` — any trade-execution capability
  requires its own explicit human approval boundary, full stop, "unless
  Natalie separately approves a different governance model in the
  future." Nothing in this roadmap changes that.
- **Prerequisites**: research/paper-trading sub-areas only need Registry
  Phase A+B; live broker integration needs Phase C fully proven (ideally
  already exercised on a lower-risk domain first, per the implementation
  proposal's Phase D reasoning) plus its own separate, explicit governance
  conversation with Natalie before design even begins.
- **Parallelizable with**: everything, for the research/paper-trading
  sub-areas specifically — genuinely independent of every other track.
  Live broker integration should not start until Registry Phase C exists
  and has been proven on something safer.

## Dependency graph (text form)

```
Registry Phase A (schema + manifest validation)
  |
  +--> Registry Phase B (ledger + report-only auditor)
  |       |
  |       +--> KarmoLab: read-only visibility/monitoring tools   [safe first real tool]
  |       +--> Finance: market research / paper trading tools     [safe, no Phase C needed]
  |       +--> Personal Productivity: reminders/planning (internal-only)
  |       +--> BloomBoss: inventory/analytics (internal-only sub-areas)
  |       +--> Media: image generation/editing (if no external paid API; else needs Phase C)
  |
  +--> Registry Phase C (dispatcher + authorization enforcement)
          |
          +--> BloomBoss: customer communication, social posting
          +--> Personal Productivity: communications (external send)
          +--> Voice: wake/listen (EXTERNAL_ACTION-shaped), full orchestration
          +--> KarmoLab: controlled administration (reuses Production Access
          |       Authorization Gate directly)
          +--> Finance: live broker integration (also needs its own
                  separate governance conversation, independent of Phase C
                  existing)
```

## What can genuinely run in parallel

- KarmoLab (read-only) and Finance (research/paper-trading) share no data
  and no risk-tier dependency on each other — the cleanest pair for
  simultaneous work if Natalie wanted two tracks moving at once.
- Media and Personal Productivity (internal-only sub-areas) are similarly
  independent of everything else.
- BloomBoss's internal sub-areas (inventory, analytics) can proceed while
  its external sub-areas (customer communication, social) wait on
  Registry Phase C — a natural internal split within one track, not a
  reason to delay the whole track.

## Recommended sequencing alternatives (not a choice made for Natalie)

**Alternative 1 — Registry-first.** Build Registry Phase A+B as its own
small increment before touching any domain, then let Natalie pick a
domain with the foundation already in place. Lowest domain-specific risk,
slightly longer time-to-first-visible-capability.

**Alternative 2 — Domain-first, registry-alongside.** Start directly with
whichever domain Natalie most wants to see progress on, building only the
narrow slice of Registry Phase A that domain's first tool actually needs
(e.g. just enough manifest validation for one `READ` tool), expanding the
registry generically later once a second domain arrives. Faster
time-to-value, higher risk of the first domain's ad hoc shortcuts becoming
awkward precedent for the second domain (the exact failure mode the
Extensibility Review already warned "getting this generic on the first
implementation is materially cheaper than retrofitting").

**Alternative 3 — KarmoLab-first as a deliberate proving ground.**
Explicitly build KarmoLab's read-only tools as Registry Phase D's proof
case (as the implementation proposal already suggests), specifically
*because* it is the lowest-risk domain, then move to whichever real
capability domain Natalie actually wants once the registry is proven
end-to-end on low stakes. Slower to reach a "product" capability, safest
path to one.

Natalie's choice among these — or a different sequencing entirely — is
the actual next decision, not made here.
