# KARMO Predeploy Review Checklist

This checklist is for **Claude + KARMO review before any merge or deployment**.

## Authority and architecture

- Confirm KARMO Core remains the sole approval/authority boundary.
- Confirm no model can grant permission, lower capability class, own credentials, or bypass the shared dispatcher.
- Confirm model routing is replaceable and model-independent.
- Confirm producer and verifier identities are distinct for trust elevation.
- Confirm durable task state remains KARMO-owned and survives model/session changes once PostgreSQL wiring is enabled.

## Capability registry and dispatcher

- Refuse unknown manifest fields and caller-supplied approval requirements.
- Compute authority from capability class plus financial/destructive flags.
- Refuse unregistered/deprecated tools.
- Verify exact tool/version/arguments binding at execution.
- Verify all write/external/destructive classes retain existing approval requirements.

## Worker security blockers

- Verify worker credential proof of possession and key rotation design.
- Verify execution tickets bind approval ID, arguments digest, worker identity, task ID, TTL, and single-use approval state.
- Verify result authenticity binding is independent of worker-reported digest.
- Verify subprocess environment allowlisting excludes tokens, SSH agent state, cloud credentials, and PYTHONPATH injection.
- Verify symlink escape fails closed with a direct test.
- Verify no worker needs an inbound listening port.
- Verify coordinator persistence exists before any real network transport is enabled.

## Data and migration safety

- Review `001_core_v2_substrate.sql` for idempotence, naming conflicts, constraints, indexes, and rollback requirements.
- Compare proposed tables with existing production schemas before approval.
- No migration runs merely because the file exists.
- Create and approve an explicit backup/rollback procedure before production migration.

## CI and code review

- Core service tests green.
- Worker Runtime tests green.
- Core v2 prototype regression green.
- Add negative/adversarial tests for every discovered defect.
- Review dependency additions; prefer stdlib/existing dependencies unless System-Fit approves otherwise.
- Scan for secrets, hard-coded credentials, unsafe shell calls, unexpected network listeners, and broad filesystem access.

## Promotion gate

Deployment is blocked until all of the following are true:

1. Claude review has no unresolved blocker.
2. KARMO invariant/system-fit review has no unresolved blocker.
3. CI is green at the exact candidate SHA.
4. Kamara explicitly approves merge/promotion.
5. A separate production deployment plan defines WHAT / WHY / CHANGE / RISK / VERIFY / ROLLBACK.
6. Production authorization is explicit and task-specific.

Until then, this branch is evidence and staging only.
