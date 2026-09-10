# KARMO Worker Runtime v0.1 — Invariant Impact Review

Performed before implementation, per the Mandatory Phase Invariant Impact
Review. This is KARMO's first real post-foundation capability — treated
with the review depth that deserves, not as a formality.

**Update (post-independent-verification, before any merge):** an
independent (ChatGPT) verification pass of the resulting PRs (#23-#25,
none merged) found four real I-09-relevant gaps this review's own
analysis below did not fully account for: approval gated job
*completion* but not *execution*; timeout was measured after the fact
rather than enforced as a real deadline; the structured result and
evidence-file list were unbounded; and a worker heartbeat could set
coordinator-owned scheduling state directly. All four are fixed on the
same branches — see the "I-09" section below and
`SECURITY_REVIEW.md`'s corresponding update for the full detail. This
does not change any of the I-01–I-08 analysis below, which remains
accurate; it corrects I-09's authority-enforcement claims to match what
the code now actually does.

**Second update (same workload, before any merge):** a second
independent verification pass found the execution-gate fix above was
correct but incomplete: the normal `WorkerClient` flow had no way to
represent "legitimately waiting on a human approval" as anything other
than a hard failure, so an approval-required job was marked `FAILED`
the instant it was leased -- before a human ever had a chance to
approve it. This is an I-08 (validation scope did not cover the
resulting workflow, only the security-gate mechanism in isolation) /
I-07 (observability: a job silently self-destructing looks
indistinguishable from a real failure) gap more than an I-09 one --
nothing unauthorized ever executed at any point, before or after this
fix. Fixed: `job_protocol.WorkerJobQueue.resume()` lets a parked job
be checked on and executed later, exactly once, once approved, or
ended safely (not left dangling) on denial/expiry. See
`SECURITY_REVIEW.md`'s threat #23 for full detail.

```
Phase: KARMO Worker Runtime v0.1 (first post-foundation capability)

I-01 Inheritance/compatibility: AFFECTED
I-02 Production parity: NOT AFFECTED (no production deployment this workload)
I-03 Data authority/transactions: AFFECTED
I-04 Idempotency/retry: AFFECTED
I-05 Resources/scale: AFFECTED
I-06 Migration/rollback: NOT AFFECTED (new capability, no prior state to migrate)
I-07 Observability: AFFECTED
I-08 Validation scope: AFFECTED
I-09 Authority/permissions: AFFECTED
```

## I-01 — Inheritance / compatibility

The Job lifecycle **reuses** `core-v2-prototypes/job_model/jobs.py`'s
`JobState` enum and claim-token fencing design directly (imported, not
reimplemented) — per explicit instruction not to create a competing
lifecycle. The Approval Engine's arguments-digest binding
(`core-v2-prototypes/approval_engine/engine.py`) is reused for job-payload
binding. The Tool/Capability Registry's manifest shape
(`core-v2-prototypes/tool_registry/registry.py`) is reused for capability
declarations. **Dependency risk, stated plainly**: none of these three
prototypes are merged to `main` yet (PR #19, open). This workload's branch
is based on `core-v2/prototypes` specifically so these imports resolve —
`worker-runtime/` therefore has a real, working dependency on PR #19's
content existing, not merely a sequencing preference. This is disclosed
explicitly in the PR description, not discovered later.

## I-02 — Production parity

Not affected — this workload explicitly does not deploy anything to
`karmo-ai01` or connect coordinator/worker across a real network. Phase 15
(future network plan) is design-only.

## I-03 — Data authority / transaction boundaries

**New authoritative stores this workload defines**, none touching
existing KARMO Core state (`conversation_memory`, `document_registry`,
etc.):
- The **Worker Registry** is authoritative for worker identity/status —
  in-memory in this prototype, mirroring the Tool Registry's own
  documented "would be `public.worker_registry` in a real implementation"
  pattern.
- The **Job Queue/Lease store** is authoritative for job state — reuses
  `JobStore` directly.
- A **worker's declared capabilities are an availability claim, not an
  authorization** — explicit design principle (Phase 3's own instruction):
  the Tool/Capability Registry (or, in this prototype, the equivalent
  local capability manifest validation) remains the sole authority for
  what a capability is *permitted* to do; a worker registering itself as
  supporting a capability never grants that capability more authority
  than KARMO Core's own manifest already defines for it.

## I-04 — Idempotency / retry

- **Job identity**: reuses `deterministic_job_id` (UUID5 from job_type +
  idempotency key) — a resubmitted job with the same key returns the
  existing job, never duplicates.
- **Payload digest**: every job carries a `payload_digest` (same
  sha256-of-canonical-content pattern as the Approval Engine's
  `arguments_digest`) — a worker executing a job re-verifies the digest
  before running, refusing (not guessing) on mismatch.
- **Lease/claim fencing**: reuses the Job model's claim-token design
  directly — a stale/crashed worker's lease is reclaimable; an old
  worker's late-arriving result is fenced out by claim-token mismatch,
  exactly as already proven for the H0.1 outbox relay and the Job model
  prototype.
- **Double-completion protection**: a job's `execute`-equivalent
  transition is single-use, same discipline as the Approval Engine's
  single-use execution.

## I-05 — Resources / scale

- **Execution sandbox** bounds: timeout per job, maximum output size,
  working-directory isolation, capability allowlist (no arbitrary
  executable). Per I-05's own "unbounded" checklist: no unbounded
  concurrency (one job per lease), no unbounded output (capped), no
  unbounded retries (bounded retry policy per job).
- **Resource discovery** (Phase 4) is read-only and unprivileged; no
  action this workload takes could exhaust KARMO-DEV01's resources beyond
  the bounded synthetic jobs in Phase 9, each individually timeout-capped.
- Behavior at 10x/100x/1000x scale: a single-worker, single-job-at-a-time
  prototype does not need to answer this yet — explicitly deferred to
  Phase 10 (multi-worker design, design-only, "minimum selection logic
  necessary to prove the model").

## I-06 — Migration / rollback

Not affected — no schema/data migration; this is new, additive capability
with no prior worker-runtime state to migrate from or roll back to.
Rollback of this workload itself is trivial (isolated prototype code on a
feature branch, not merged, not deployed).

## I-07 — Observability

- Every worker registration, heartbeat, job lease, execution, and result
  is recorded in an append-only evidence/audit trail — same pattern as
  the Approval Engine's `audit_trail` and the H0.1 outbox's status
  tracking.
- Failure categories reuse I-07's own suggested vocabulary
  (`DEPENDENCY_UNAVAILABLE`, `AUTHORIZATION_DENIED`, `RETRYABLE_FAILURE`,
  `PERMANENT_FAILURE`) plus worker-specific ones (`WORKER_OFFLINE`,
  `STALE_LEASE`, `CAPABILITY_MISSING`, `PAYLOAD_DIGEST_MISMATCH`).
- `VERIFIED` vs. `AVAILABLE-IN-PRINCIPLE` distinction (Phase 4/12,
  explicit instruction) is itself an observability discipline — never
  claiming a capability is available without having actually checked.

## I-08 — Validation scope

New capability, new integration boundary → full ladder applies: unit
(state machines), contract (capability manifest validation), authority/
security (24 adversarial scenarios, Phase 11), failure injection (reusing
`core-v2-prototypes/failure_injection/`'s framework where applicable),
integration (worker↔coordinator, local transport), evidence generation
(Phase 14). Not rungs 8–10 (no production step this workload).

## I-09 — Authority / permissions (the core subject of this workload)

This is the single most safety-critical property of the entire design,
matching the explicit architectural principle: **workers are not full
KARMO servers; they advertise capabilities, they do not grant themselves
authority.** Concretely:

- A worker's `WORKER_CAPABILITY` declaration is validated against a
  closed, allowlisted set (Phase 5's safe-capability list) — a worker
  cannot invent a new capability name and have it trusted; unknown
  capability IDs are refused, mirroring the Tool Registry's
  unknown-field refusal (a defect this session's prior review found and
  fixed in that exact prototype — the same discipline applies here from
  day one, not retrofitted).
- `authority_class`/`side_effect_class` per capability are **fixed by
  KARMO Core's own manifest**, never by the worker's self-declaration —
  a worker cannot lower (or raise) what a capability is authorized to do
  by claiming to support it.
- No capability in the Phase 5 initial set exceeds `REVERSIBLE_WRITE`
  within the worker's own isolated temp workspace — nothing
  `EXTERNAL_ACTION` or `DESTRUCTIVE_HIGH_IMPACT` is implemented this
  workload (explicit instruction: no shell/ssh/admin/financial/external
  capabilities).
- Explicit worker-specific threats (remote-code execution, worker
  impersonation, job replay, stale identity, capability spoofing, result
  tampering, privilege escalation, secrets exposure) are threat-modeled
  in Phase 13 and defended against structurally in Phases 6–8 (digest
  binding, lease fencing, capability allowlisting, sandboxed execution,
  no inherited secrets).
- **Least privilege**: the execution sandbox never inherits production
  credentials (none exist in this local, non-production context to begin
  with), never permits arbitrary shell, never permits path traversal
  outside an explicit allowed workspace.

**Corrective fixes (post-independent-verification):**
- Approval now gates **execution**, not merely completion —
  `job_protocol.WorkerJobQueue.execute()` invokes a capability's action
  only from inside the reused `ApprovalEngine.execute()`, which enforces
  approval state, executor identity, expiry, and an exact arguments
  digest before running anything, consuming the approval into EXECUTED
  atomically with the run. Previously, execution happened unconditionally
  at lease time and approval was checked only afterward, at completion —
  a real authority-enforcement gap for any future capability whose
  `authority_requirement` is not NONE (none of the current SAFE
  capabilities are, so no unapproved SAFE capability ever actually ran
  unauthorized in practice, but the mechanism itself was not
  authority-correct).
- Worker heartbeats can no longer set coordinator-owned scheduling state
  (`BUSY`/`AVAILABLE`) directly — only a self-reported `WorkerHealth`
  (HEALTHY/DEGRADED). This closes an authority-boundary violation where a
  worker's own heartbeat could bypass the coordinator's lease tracking
  (`mark_busy`/`mark_available`), which is exactly the kind of
  "capability spoofing"/"privilege escalation" shape this section already
  named as a worker-specific threat to defend against structurally.
- Timeout enforcement and result bounding (I-05 concerns) are also now
  real (forked-process kill, `MAX_RESULT_BYTES`/`MAX_EVIDENCE_FILES`) --
  see `SECURITY_REVIEW.md` for full detail; noted here because an
  unenforced deadline and an unbounded result are also, secondarily,
  resource-exhaustion-shaped authority gaps (a job could consume more
  than its declared bound without being stopped).

## Known inherited assumptions

Every I-04/I-06 guarantee above is **only as strong as the underlying
prototypes it reuses** (`job_model`, `approval_engine`, `tool_registry`)
— themselves already independently adversarially reviewed this session
(4 real defects found and fixed). This workload inherits their
*corrected* versions, not the originals.

## Validation plan

Unit + contract + authority/security + failure-injection + integration,
all in isolation, local transport only. See Phase 11's 24-scenario test
plan and Phase 14's evidence package for the concrete acceptance gates.

## Rollback implications

None beyond normal `git revert` — isolated prototype code, not merged,
not deployed, no production or network state created.
