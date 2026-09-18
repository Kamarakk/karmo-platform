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

## Mandatory Full-Context Review Rule

**Why this exists:** on 2026-09-17/18, a real capability (KARMO chat
tool-calling and external model delegation) was designed and approved
without checking it against an already-documented target architecture —
the "Model Router" / KARMO-FIRST Orchestration vision captured on
2026-09-11. That vision was real and legitimate, but it lived in one
dated `docs/project-state/PROJECT_SAVE_*.md` file that had never been
folded into `MASTER_INDEX.md` or the living `docs/plans/`/`docs/architecture/`
set — so a normally-diligent check of "the plan" did not surface it.
Separately, `MASTER_INDEX.md` itself had fallen roughly a week behind
actual project history at the time, missing more than twenty
project-save records including that one. Both failures compounded: an
agent that skipped checking history, and a history that had stopped
being kept checkable. This rule exists so that combination cannot repeat.

**The rule:**

1. Before **any** KARMO action — implementation, a design proposal, a
   recommendation, or a read-only command — read
   `docs/project-state/MASTER_INDEX.md` in full. It is deliberately kept
   short and skimmable (one line per document) specifically so this is
   fast, not a burden to skip. There is no "this is just a quick
   read-only check" exception. A read-only command run against the wrong
   understanding of the current plan is exactly the failure this rule
   prevents.
2. For anything `MASTER_INDEX.md` flags as relevant to the task at hand,
   read that document in full — not a skim, not an assumption from its
   one-line summary. The index tells you where to look; it is never a
   substitute for reading what it points to.
3. This applies with no reduced scope regardless of which interface or
   tool an agent is working through (CLI, IDE extension, web, or any
   other surface) — the rule binds the work, not the tool used to do it.
4. `MASTER_INDEX.md` itself must stay current for this rule to mean
   anything. The Mandatory Project Save Completion Rule already requires
   updating it — treat that specific line item as load-bearing, not
   optional paperwork: an out-of-date index is what turned a real,
   documented vision into an effectively invisible one for a week.
5. If a design decision touches model routing, multi-model delegation,
   or "which resource should do this work," specifically confirm
   `PROJECT_SAVE_2026-09-11_KARMO_FIRST_ORCHESTRATION_PALMSTREET_KVE.md`
   has been read — that document remains the target architecture for
   this area until it is formally superseded or folded into a living
   plan document.

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

## Mandatory Production Access Authorization Gate

Production access — any production SSH, Docker socket, production
database, Qdrant, secret, real document, or customer-data access — is
**prohibited by default** for every KARMO agent, including within an
already-approved autonomous workload. This gate is the single canonical
resolution of that default prohibition: it defines the only way past it,
so that no other document, approval, or instruction needs to (or may)
restate, narrow, or widen it independently. Where any other document
appears to grant production access on different terms, this section
governs, per this document's own precedence statement above.

### What lifts the default prohibition

Only Natalie's **explicit, task-specific Production Access Authorization**
lifts the default prohibition, and only to the exact extent that
authorization defines. A general workload approval, an approval under
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`, or an
authorization already granted for a different task, NEVER substitutes for
this. Per I-09's least-privilege principle and this document's own
precedence rule: **the narrower rule always wins.** An agent that is
unsure whether a given approval counts as a valid Production Access
Authorization for the task at hand must treat it as not counting, and
STOP.

A valid Production Access Authorization must define or clearly bound:

1. **Target system/environment** — the exact host, database, Qdrant
   collection, or service covered. Not "production" in general.
2. **Purpose** — why this access is needed, traceable to an approved
   workload or an explicit one-off request.
3. **Permitted operations** — the specific action(s) authorized, not an
   open-ended capability.
4. **Read-only vs. write authority** — stated explicitly. **A read-only
   authorization never implies write authorization, under any
   circumstance.** Any write requires its own separate grant (see below).
5. **Applicable commands or command class**, when known — the exact
   command(s), or a clearly bounded class of command, the authorization
   covers.

An authorization missing any of the above for the task actually at hand is
incomplete; treat it the same as no authorization and STOP to ask for the
missing element, rather than filling the gap with an assumption.

### Scope and expiry

Authorization is **single-task, single-session scope**. It expires
automatically the moment the authorized task completes — successfully,
unsuccessfully, or abandoned — and does not carry forward to a later
session, a later task, or a superficially similar task, even within the
same workload. A new task requires a new authorization.

### Writes and higher-impact actions require their own grant

A Production Access Authorization for read-only verification never
authorizes, and must never be treated as implicitly extending to, a
production write, deployment, a destructive action, a migration, a service
restart, a configuration change, a data repair, a deletion, or any other
irreversible action. Each requires its own explicit authorization, stated
with the same specificity as above — matching I-09's capability
classification (a write is at minimum REVERSIBLE WRITE; most of the listed
actions are EXTERNAL ACTION or DESTRUCTIVE/HIGH-IMPACT) and the standing
gates already in `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`.

### Mandatory STOP conditions

Even under a valid, in-scope authorization, an agent must STOP
immediately — before taking or completing any modifying action — and
report rather than proceed, when any of the following occurs:

- production state is unexpected or does not match the authoritative
  record (an "evidence contradicts an authoritative record" condition,
  per the autonomous execution contract);
- the task's scope is ambiguous in a way that could expand what is
  actually touched;
- evidence encountered during the task is contradictory;
- completing the task, or responding to what is found, would require
  greater authority than the authorization actually grants (e.g. a
  read-only grant reveals a problem that can only be fixed with a write).

### Secrets

Never expose, print, log, commit, or otherwise persist a secret value
(password, API key, token, credential) encountered or used under a
Production Access Authorization. An existing, already-approved
secret-loading mechanism (e.g. an environment variable an application
already reads) may be used without ever displaying, echoing, or writing
out the value itself. This is consistent with, not an exception to,
`AGENTS.md`'s "do not use or request secrets": that rule means never ask
Natalie for a secret value or type one into a session; invoking an
existing, already-wired loading mechanism without ever seeing or
disclosing the value is not "using or requesting a secret" in that sense.

### Relationship to other invariants and gates

This gate narrows, and never widens, what an agent may do. A Production
Access Authorization does not override, relax, or substitute for any other
invariant (I-01 through I-09), the Mandatory Phase Invariant Impact
Review, `docs/governance/KARMO_VALIDATION_LADDER.md`'s validation
requirements, any rollback requirement, or any other approval gate in
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`. Where this gate
and any other rule could be read as being in tension, the narrower reading
governs.

### Authorization record (use this shape)

Record every Production Access Authorization actually acted on — in the
task's PR description or evidence, and in
`docs/project-state/CURRENT_STATE.md` once acted on:

```
PRODUCTION ACCESS AUTHORIZATION
Task: <specific task/workload>
Target system/environment: <exact host/db/collection/service>
Purpose: <why>
Permitted operations: <exact action(s)>
Authority: READ-ONLY | READ-ONLY + WRITE (state exactly which writes)
Commands/command class: <exact command(s) or bounded class>
Granted: <date, by Natalie>
Expires: automatically on task completion
```

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
