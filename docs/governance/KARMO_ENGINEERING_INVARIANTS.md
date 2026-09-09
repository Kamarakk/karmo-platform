# KARMO Engineering Invariants

Approved by Natalie. These nine invariants are permanent and apply to
every current and future KARMO phase, feature, service, migration, agent,
integration, and deployment. This document is the single source of truth
for them -- `AGENTS.md` and `CLAUDE.md` require compliance with it but do
not duplicate its content, so if those files and this one ever appear to
disagree, this document governs.

Compliance with the invariants relevant to a change, including the
Invariant Impact Review below, is required **before implementation
begins**, not retrofitted after deployment preparation.

---

## I-01 — Inheritance & Forward Compatibility

Before a new phase is considered deployment-ready, review every inherited
component that the phase depends upon.

Check for:
- legacy-data compatibility
- missing fields on older records
- previous schema assumptions
- lifecycle/version compatibility
- identity/provenance compatibility
- fixed limits and pagination assumptions
- changed dependency behavior
- upgrade/migration requirements
- behavior at 10x, 100x, and 1000x current scale

Previously created data and behavior must remain supported unless an
explicit migration or intentional breaking change is approved.

If the logical operation means ALL records, paginate until exhausted
rather than relying on an arbitrary fixed limit.

Compatibility review happens BEFORE implementation acceptance, not after
deployment preparation.

## I-02 — Production Parity

Anything intended for production must be evaluated against the actual
production execution model, not merely the development/test environment.

Before deployment determine:
- execution user
- working directory
- Python/runtime/venv
- dependency versions
- environment variables
- credential source
- required services
- service startup ordering
- restart behavior
- reboot persistence
- logout/session persistence
- log destination
- failure visibility
- health verification

No production service may depend on environment variables or
configuration manually exported in an interactive shell.

Development/test success alone does not establish production readiness.

## I-03 — Data Authority & Transaction Boundaries

Every persistent piece of KARMO state must have a declared authoritative
source.

When one logical operation spans PostgreSQL, Qdrant, files, queues, APIs,
or other systems, define:
- authoritative system
- write ordering
- transaction boundary
- failure behavior at every boundary
- retry behavior
- partial-completion detection
- reconciliation method
- rollback/recovery behavior

Never claim distributed atomicity where none exists.

Use durable state, idempotency, reconciliation, transactional outbox
patterns, or another explicit consistency mechanism as appropriate.

Failures that create integrity gaps must not be silently reported as
success.

## I-04 — Idempotency & Retry Safety

Any operation that may be retried must be safe to execute more than once.

Before implementing a retryable worker/action define:
- unique operation/event identity
- duplicate execution behavior
- crash-before-action behavior
- crash-after-action-before-ack behavior
- concurrent-worker behavior
- stale claim recovery
- fencing/ownership where necessary

Prefer deterministic identities for externally persisted operations where
appropriate.

Retries must not create duplicate knowledge, duplicate external actions,
or silently corrupt state.

## I-05 — Bounded Resources & Scale

Review every new production path for:
- fixed result limits
- missing pagination
- unbounded queries
- unbounded memory loading
- unbounded prompts/context
- unbounded logs
- unbounded queues
- unbounded retries
- unbounded concurrency
- unbounded file sizes
- full-table scans
- full-collection scans

Rule:
If the requirement means ALL, paginate/stream until exhausted.
If the requirement means SOME, explicitly bound the operation.

Arbitrary implementation ceilings must not silently redefine application
semantics.

Consider expected behavior at 10x, 100x, and 1000x current scale.

## I-06 — Migration & Rollback Compatibility

Every schema, metadata, identity, lifecycle, or storage change must
explicitly consider:

OLD STATE → MIXED STATE → NEW STATE

Software must tolerate the mixed state during migration unless
downtime/exclusive migration is explicitly approved.

Before deployment determine:
- how legacy data is interpreted
- how new data is interpreted
- how mixed datasets behave
- whether backfill is required
- whether rollback is possible
- whether old software can safely read data written by new software
- whether the migration creates a one-way compatibility boundary

Never assume all historical records contain fields introduced by a newer
version.

A one-way migration requires explicit approval and a recovery plan.

## I-07 — Observability Before Automation

No autonomous or background workflow may be promoted without sufficient
observable state to determine:
- what happened
- when it happened
- which component performed it
- which object/event/document was involved
- why it occurred where applicable
- success/failure status
- retry state
- failure reason
- next expected action

Prefer meaningful failure categories such as:
- `DEPENDENCY_UNAVAILABLE`
- `CONFIGURATION_ERROR`
- `INTEGRITY_FAILURE`
- `RETRYABLE_FAILURE`
- `PERMANENT_FAILURE`
- `LEGACY_DATA_GAP`
- `AUTHORIZATION_DENIED`

Do not incorrectly classify known legacy/unknown state as corruption.

Logs and status must expose failures rather than silently swallowing
them.

## I-08 — Validation Ladder / No Redundant Testing

Use the smallest validation scope justified by the change.

Normal ladder:

changed code
→ targeted validation for changed behavior
→ integration validation only if an integration boundary changed
→ full acceptance/regression only at an appropriate phase/release gate
→ production smoke verification after approved deployment

Previously accepted tests do not need to be rerun merely because
unrelated code changed.

A full suite may be rerun when:
- foundational/shared behavior changed
- dependency/runtime changes could affect it
- security/integrity-sensitive behavior changed
- release/phase acceptance requires it
- a concrete regression risk justifies it

When repeating a previously accepted test, state WHY the rerun is
necessary.

Do not create duplicate evidence files for the same unchanged acceptance
result.

The goal is sufficient evidence, not maximum test count.

## I-09 — Authority & Permission Boundaries

Intelligence does not imply authority.

KARMO deciding that an action would be useful does not automatically
authorize KARMO to execute it.

Classify capabilities approximately as:
1. READ
2. DRAFT / PROPOSE
3. REVERSIBLE WRITE
4. EXTERNAL ACTION
5. DESTRUCTIVE / HIGH-IMPACT ACTION

Higher-impact capabilities require stronger authorization and safeguards.

Before adding an autonomous action define:
- permitted actor
- permitted resources
- permitted action
- authorization requirement
- confirmation requirement
- audit record
- rollback/reversal capability where possible
- blast-radius limit
- credential scope
- data-access scope

Apply least privilege.

Do not combine unrelated personal, business, infrastructure, security, or
other sensitive data domains merely because KARMO technically has access
to them.

Agents/tools inherit the permissions of the explicitly authorized
workflow, not unlimited KARMO authority.

---

## Mandatory Phase Invariant Impact Review

Every future KARMO phase must begin with an Invariant Impact Review
before substantial implementation.

Use:

```
Phase: <phase>

I-01 Inheritance/compatibility: AFFECTED / NOT AFFECTED
I-02 Production parity: AFFECTED / NOT AFFECTED
I-03 Data authority/transactions: AFFECTED / NOT AFFECTED
I-04 Idempotency/retry: AFFECTED / NOT AFFECTED
I-05 Resources/scale: AFFECTED / NOT AFFECTED
I-06 Migration/rollback: AFFECTED / NOT AFFECTED
I-07 Observability: AFFECTED / NOT AFFECTED
I-08 Validation scope: AFFECTED / NOT AFFECTED
I-09 Authority/permissions: AFFECTED / NOT AFFECTED

Then document only what is relevant:

Known inherited assumptions:
Legacy-data considerations:
Authoritative data stores:
Transaction/failure boundaries:
Scale considerations:
Runtime/dependency requirements:
Migration/mixed-state requirements:
Observability requirements:
Authorization boundaries:
Validation plan:
Rollback implications:
```

The review should be concise. Its purpose is to catch design problems
before implementation, not create paperwork.

---

## Mandatory Project Save Completion Rule

No major KARMO work session, phase, workload, deployment, configuration
session, or infrastructure change is considered complete until **PROJECT
SAVE** has been performed. This applies to all future KARMO phases and
workloads, including work performed through Spec Kit.

PROJECT SAVE requires:

1. Read the existing `docs/project-state/` records first.

2. Update the applicable persistent records, including as appropriate:
   `MASTER_INDEX.md`, `CURRENT_STATE.md`, `CHANGE_LOG.md`,
   `SOFTWARE_INVENTORY.md`, `NETWORK_INVENTORY.md`, `DASHBOARD_INVENTORY.md`,
   `COMMAND_LOG.md`, `ROLLBACK_AND_REMOVAL.md`, `NEXT_STEPS.md`.

3. Record consequential installations, configuration changes, commands
   actually executed, verified results, failures and fixes, architecture
   decisions, services/containers/tools, network changes, dependencies,
   rollback/removal procedures, unresolved issues, the stopping point, and
   the next action.

4. Use the three-tier status vocabulary already established for
   `docs/project-state/`: `VERIFIED`, `HISTORICAL`, `NEEDS VERIFICATION`.

5. Never silently replace conflicting verified information. Flag conflicts
   instead.

6. Never store passwords, API keys, tokens, or secret values. Record only
   the location/mechanism used to obtain credentials, per I-09's
   least-privilege and credential-scope discipline.

7. Run appropriate consistency and repository validation after updating the
   records (at minimum, the checks already established in
   `docs/governance/KARMO_VALIDATION_LADDER.md` for a documentation-only
   change: `git diff --check`, `git status`, and a scan for contradictions,
   duplicate governance, secrets, and accidental resolution of historical
   unknowns).

8. The applicable `docs/project-state/` updates must be committed to the
   repository with the work they document, or in an immediately following
   documentation commit, before the session/workload is considered CLOSED.

9. If work intentionally stops before a commit/PR boundary, the session
   must be marked **PROJECT SAVE PENDING**, and the fact that the project
   record is not yet durably committed must be explicitly reported.

10. Before declaring a workload/session COMPLETE, report:

    ```
    PROJECT SAVE: COMPLETE
    Persistent records updated: <files>
    Durable Git commit: <commit hash>
    Current stopping point: <state>
    Next action: <action>
    ```

This rule does not create a new approval gate on its own — committing the
resulting documentation still follows whatever merge/approval boundary the
work itself already required (see
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`). It requires that
the record-keeping happen and be durable, not that every session ends in a
merge.

### Extension: ChatGPT Session Persistence

KARMO architectural decisions, approvals, requirements, constraints, future
goals, project-state changes, and other consequential information created
during Natalie's ChatGPT planning sessions are **not** considered durably
recorded merely because they exist in ChatGPT conversation history.
**ChatGPT conversation history is not the authoritative KARMO project
record.** The Git repository, including `docs/project-state/`, is the
authoritative persistent project record.

When Natalie invokes **PROJECT SAVE** for a ChatGPT KARMO session, the same
PROJECT SAVE rule above applies, entered through this specific path:

1. ChatGPT prepares a handoff containing the consequential decisions,
   approvals, requirements, discoveries, architecture decisions,
   constraints, unresolved items, stopping point, and next action from that
   session.

2. The handoff is provided to a repository-capable KARMO development agent
   (Claude Code or a future equivalent).

3. That agent MUST read and reconcile the existing `docs/project-state/`
   records before writing the handoff into the repository — per rule 1
   above, not a separate step.

4. Existing `VERIFIED` information must never be silently overwritten;
   conflicts between the handoff and the existing record must be explicitly
   reported — per rule 5 above.

5. The applicable `docs/project-state/` files must be updated — per rule 2
   above.

6. Secret values must never be copied from ChatGPT into project records.
   Credential locations/mechanisms may be recorded; passwords, API keys,
   tokens, private keys, and other secret values may not be stored — per
   rule 6 above.

7. The resulting project-state update must be committed to Git before the
   ChatGPT planning session is considered durably CLOSED — per rule 8
   above.

8. If the handoff has been created but not yet committed, report **PROJECT
   SAVE: PENDING** — the ChatGPT-session equivalent of rule 9's PROJECT SAVE
   PENDING state.

9. Once committed, report completion in the same format as rule 10 above:

   ```
   PROJECT SAVE: COMPLETE
   Persistent records updated: <files>
   Durable Git commit: <hash>
   Current stopping point: <state>
   Next action: <action>
   ```

This extension applies regardless of which repository-capable agent
performs the persistence step, including Claude Code or future KARMO
development agents. It does not create a second PROJECT SAVE rule — a
ChatGPT planning session is simply another source of consequential KARMO
information that must flow through the one rule above before it counts as
recorded.
