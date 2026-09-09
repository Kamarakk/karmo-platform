# KARMO Autonomous Workload Execution Contract

Purpose: once Natalie approves a specific workload (as defined in
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` or a future equivalent),
Claude should be able to complete that workload's ordinary, reversible
engineering steps without stopping to ask permission for each one. This
document defines exactly how far that autonomy extends and exactly where it
ends. It does not change, weaken, or duplicate
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, `AGENTS.md`, or
`CLAUDE.md` — it operationalizes them for multi-step autonomous execution.
Where this document and any of those three ever appear to disagree, those
three govern.

## Precondition

This contract applies **only** to a workload Natalie has explicitly
approved, and only within that workload's documented scope. It grants no
standing authority outside an approved workload, and no authority at all
until a workload is approved.

## What "approval" activates (may execute autonomously)

Within an approved workload's documented scope, Claude may, without
stopping to ask first:

- create and edit repository files within the workload's scope;
- create branches for the workload;
- implement the approved functionality;
- run tests, including bringing up and tearing down isolated test
  infrastructure (Docker containers, in-memory stores) per existing
  patterns;
- fix a defect discovered by a test, when the fix remains within the
  workload's approved scope, and rerun the affected tests;
- perform the invariant review required by the workload;
- generate evidence (reports, run logs, JUnit output) under
  `docs/evidence/<phase>/`;
- update project documentation, including `docs/project-state/`;
- prepare a commit or pull request for Natalie's review.

**"Fix and revalidate" default:** if an implementation defect is found
during an approved workload and the fix is an ordinary, in-scope
engineering correction, Claude should fix it and rerun the relevant tests
rather than stopping to ask Natalie how to fix it. This mirrors how H0.4's
pagination ceiling and pre-commit review findings were already handled.
Stopping is for the boundaries below, not for ordinary defect-fixing.

## What approval never activates (must not do without separate, explicit authorization)

Regardless of workload approval, Claude must not:

- deploy to production;
- access production when not explicitly authorized for that specific access — "explicitly authorized" means a valid Production Access Authorization under `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s Mandatory Production Access Authorization Gate specifically, never this contract's general workload approval;
- perform a destructive operation (deleting data, force-pushing, dropping a
  table, `git reset --hard` on shared history, etc.);
- weaken, reinterpret, or bypass any of I-01 through I-09;
- expand scope into a feature or domain the workload did not define;
- expose or store a secret, or write one into a file, log, or evidence
  report;
- perform a financial transaction of any kind;
- send or post anything externally (email, social media, messaging a
  customer, etc.) unless that specific external action was separately
  authorized;
- merge a pull request when the workload requires Natalie's merge approval
  (the default — see Approval Boundaries below).

## Where Claude must STOP and wait for Natalie

Stop, describe the situation, and wait — do not guess and continue — when
any of the following is reached, even mid-workload:

1. A defined human approval gate in the workload (see next section) is
   reached.
2. Safe continuation would require expanding scope beyond what was approved.
3. Evidence contradicts an authoritative record (a governance document, a
   `docs/project-state/` record, or a prior evidence report) — do not
   silently overwrite the prior record or silently proceed on the new
   evidence; surface the conflict.
4. An invariant (I-01–I-09) cannot be satisfied as designed — do not
   implement around it or narrow its meaning to make it pass.
5. Production access would be required to proceed.
6. A requirement is genuinely ambiguous in a way that would materially
   change the architecture (not an ordinary implementation-detail choice,
   which Claude should just make and document).

## Standing human approval gates (apply regardless of workload)

These gates exist independent of any specific workload's own approval
boundaries, and a workload's approval never pre-clears them:

- production deployment;
- any destructive or irreversible operation;
- an irreversible migration or data change;
- authorizing or connecting a new external account/service;
- any financial transaction;
- any public posting or external send, unless authorization for that
  specific channel/action was already explicitly granted;
- any change to KARMO governance or the engineering invariants themselves.

## Relationship to the validation ladder and workload definitions

Each workload in `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` states its
own "approval boundaries" and "where Claude must STOP for Natalie" sections.
Those sections apply this contract's general rules to that workload's
specific scope; they do not need to re-derive the general rules above, and
this contract does not need each workload to repeat them verbatim.
`docs/governance/KARMO_VALIDATION_LADDER.md` defines how much testing rungs
1–10 look like within the autonomy this contract grants; it does not grant
or restrict autonomy itself.

## No self-amendment

Claude may not treat this contract as self-amending. Any change to what
counts as "ordinary reversible work" versus "a stop condition" is itself a
governance change and requires Natalie's explicit approval, per the standing
gate above ("any change to KARMO governance or the engineering invariants
themselves").
