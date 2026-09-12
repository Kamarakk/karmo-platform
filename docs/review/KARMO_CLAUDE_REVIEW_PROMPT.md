# Claude Review Prompt — KARMO Full Predeploy

Review branch `staging/karmo-full-predeploy-20260912` as an independent adversarial reviewer. Do **not** merge, deploy, touch production, or change networking. Treat `main` and authoritative project records as reference truth and the staging branch as an untrusted candidate.

Your job is to find defects, not to approve by default.

1. Read the Master Index, latest dashboard/project save, Engineering Invariants, System-Fit Review, Validation Ladder, Autonomous Execution Contract, Core v2 architecture, Worker security review/network plan, and the staging review artifacts.
2. Compare the staging branch to `main` and enumerate every changed file and behavior.
3. Check for authority bypass: model-owned authority, caller-supplied approval requirements, dispatcher bypass, unregistered tool execution, stale approval reuse, wrong-executor use, argument drift, self-verification, or any path that lets reachability substitute for authorization.
4. Attack persistence and migrations: schema conflicts, partial transactions, unsafe defaults, missing constraints/indexes, broken restart semantics, replay/idempotency defects, and rollback problems.
5. Attack Worker security: credential forgery/replay/rotation, execution-ticket tampering/replay/expiry, result forgery, secret/env leakage, symlink/path escape, arbitrary command execution, network exposure, coordinator spoofing, worker impersonation, resource exhaustion, and stale leases.
6. Attack model routing: provider lock-in, hidden authority, missing capability constraints, unavailable-verifier handling, and producer/verifier collusion or accidental identity reuse.
7. Run all available isolated GitHub/dev tests. Add adversarial tests for any real defect you find. Keep fixes on the staging branch only.
8. Do not weaken tests or governance to make CI pass. Refuse rather than guess.
9. Produce a final table with `BLOCKER / HIGH / MEDIUM / LOW`, exact file/line, exploit/failure path, fix, test evidence, and status.
10. End with one of: `NOT READY`, `READY FOR KARMO REVIEW`, or `NEEDS_VERIFICATION`. Never claim production readiness without exact-SHA green CI and resolved blockers.

Preserve KARMO as the authority and source of durable task truth throughout the review.
