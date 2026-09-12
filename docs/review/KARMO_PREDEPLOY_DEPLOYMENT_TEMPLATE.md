# KARMO Predeploy Deployment Template

**Do not execute this document.** It is a review template to be completed only after Claude + KARMO review, green CI, merge approval, and separate production authorization.

## Candidate

- Candidate branch/SHA:
- Approved PR:
- Reviewer evidence:
- KARMO invariant/system-fit decision:

## WHAT

List the exact files, schema migrations, services, and configuration proposed for production.

## WHY

State the capability enabled and why existing production behavior is insufficient.

## CHANGE

Enumerate every production mutation, including database schema, service files, permissions, network listeners, credentials, and restart scope. Any item not listed here is unauthorized.

## RISK

- authority / approval bypass risk
- data integrity / migration risk
- credential / secret exposure risk
- network exposure risk
- rollback complexity
- compatibility with Foundation v1 / H0.1 / H0.2 / H0.4

## PREDEPLOY VERIFICATION

- exact candidate SHA CI green
- database schema preflight read-only
- existing Core/Worker health baseline captured
- current KARMO service health captured
- backup/rollback evidence captured
- secrets/credentials supplied through approved runtime mechanism only

## ROLLBACK

Define exact reverse operations for each production mutation. Database rollback must preserve pre-existing data and must not assume destructive downgrade is safe.

## POSTDEPLOY VERIFICATION

Verify Core, Worker, existing KARMO services, Foundation invariants, task persistence, approval enforcement, dispatcher refusal paths, worker authentication, and audit/evidence recording.

## STOP CONDITIONS

Abort and roll back on any unexpected schema difference, failed health check, authority-class mismatch, credential verification failure, result-authenticity failure, unexpected listener, failed invariant, or unexplained regression.
