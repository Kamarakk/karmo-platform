# Open Findings Triage — Deduplicated Across All Three Programs

Consolidates findings from the Foundation Closeout Program, the
Post-Foundation Overnight Readiness Program, the Core v2 Engineering
Blueprint Program, and this review, cross-referenced against
`docs/project-state/NEXT_STEPS.md`. Nothing new invented — every item
below already exists in a prior program's evidence; this review only
deduplicates and classifies.

## BLOCKS NEXT CAPABILITY

*(none)* — no finding in any program blocks starting the next
post-foundation capability track. This is itself a finding worth stating
explicitly: three full programs of review have not surfaced anything
that must be fixed before Natalie can choose and start a capability.

## FIX BEFORE RELEVANT FEATURE

- **`document_memory.get_document_history` pagination ceiling** (live
  production code, `docs/handoff/h04/document_memory.py`) — fix before
  document volume grows meaningfully, or before any capability
  (Media's registry, BloomBoss content assets) adds meaningful new
  document volume through the same collection pattern.
- **No connection pooling anywhere in the codebase** — fix before any
  capability introduces a second concurrent worker/polling process
  alongside the H0.1 relay (Voice's continuous listener, a Job/Event
  model background worker, KarmoLab monitoring).
- **No embedding-model provenance on `karmo_semantic_memory`** — fix
  before any embedding-model or dimensionality change is attempted; not
  urgent otherwise.
- **Configuration drift** (≥10 files independently redeclaring
  Qdrant/Postgres endpoints) — a design and isolated POC now exist
  (`docs/architecture/KARMO_CONFIGURATION_SINGLE_SOURCING_DESIGN.md`,
  `core-v2-prototypes/config_poc/`), but nothing is wired into production
  yet. Fix before a second/third domain each independently redeclares
  the same constants again.
- **Tool Registry ↔ Approval Engine integration gap** (this review,
  Workstream 5) — the two prototypes were never exercised together end
  to end; a real `authority_class` was never derived from a real registry
  lookup in any test. Fix — i.e., actually build and prove Tool Registry
  Phase C's dispatcher — before registering any real tool, not before
  choosing a capability.

## NONBLOCKING TECH DEBT

- **H0.1 relay: retry delay is bounded, retry *count* is not**, for
  unanticipated (non-`PermanentDeliveryError`) exceptions — visible in
  outbox status every attempt (I-07 satisfied), not silent; a max-attempt
  safety net is a reasonable future refinement, not urgent.
- **No persistent (PostgreSQL) storage for the Tool Registry, Approval
  Engine, or an invocation ledger** — explicitly, correctly represented
  as future work by every design doc; the implementation dependency
  graph already phases this in as Batch 1/2.
- **No report-only registry auditor exists yet** (the Tool Registry's
  analog to `h04/app/auditor.py`) — same status, already phased.
- **Superseded `h02/app/document_ingest.py` carries the same pagination
  bug as the live one** — dead code, not currently live; low risk unless
  reused as a future template.

## DEFER

- Observability (structured logs/metrics/correlation IDs) — design-only
  by explicit instruction across two programs now; correctly deferred,
  not a gap to close soon.
- Security threat-model mitigations requiring dispatcher code (SSRF
  allowlist, path-traversal guards) — nothing to attach them to yet;
  defer until Tool Registry Phase C is actually built.
- Real git/`gh` subprocess implementations for the run-evidence verifier
  — the design's own injected-callable pattern defers this by design.

## HUMAN DECISION

- **The two ambiguous `karmo-v05-new.html` legacy hashes** — standing
  constraint, unresolved by every program to date, correctly untouched by
  this review too; requires Natalie's explicit version-ordering decision.
- **Configuration Single-Sourcing governance proposal** (prior program) —
  proposed, not adopted.
- **Tool-registration review governance proposal** (Core v2 program) —
  proposed, not adopted.
- **Merge/reject decision for all 8 PRs** (#14–#21) — see the merge
  readiness packet.
- **First post-foundation capability choice** — see the capability
  decision matrix, this review.
- **H0.3 remains NO-PROMOTION** — not a decision pending, a standing,
  already-made decision this review reconfirmed unchanged; listed here
  only to close the loop on the instruction's explicit "check H0.3
  remains NO-PROMOTION" requirement, not because anything needs
  deciding.

## Explicitly not escalated to a finding

Per this program's own instruction ("do not create work merely because
an issue exists"): the `evidence_completeness`/`test_reliability`/etc.
Trust Score components, before this review's fix, technically qualified
as a defect (Finding 2, already fixed) rather than a triage item — it did
not need a NEXT_STEPS entry because it was fixed in the same session it
was found, on the same PR, with tests proving the fix. Same for the other
3 adversarial-review findings and the two stale-reference fixes.
