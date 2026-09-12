# Claude Review Prompt — KARMO Full Predeploy Exact-SHA Gate

You are the independent adversarial reviewer for KARMO. Review the candidate branch `staging/karmo-full-predeploy-20260912` as untrusted candidate code. Treat `main` and the authoritative KARMO records as reference truth.

## Exact code candidate to verify

`0359ac8610292e2341f5b31aba688703e6ad22c8`

This is the **code-bearing candidate SHA** containing the previously reviewed substrate plus the durable-control-plane expansion: persistent approval hooks, approval CLAIMED state, dispatcher integration, PostgreSQL invocation ledger/idempotency controls, optimistic task-state versioning, atomic recovery state+event persistence, unfinished-invocation reconciliation, and new recovery adversarial tests.

The branch may contain newer commits only when they modify `docs/review/**` for review instructions/status. Newer review-only documentation does not invalidate the code SHA. If any commit after the code SHA changes application code, tests, workflow logic, migrations, or any non-review artifact, stop and report `NEEDS_VERIFICATION — CODE SHA MOVED` and identify the first such commit.

## Non-negotiable boundaries

- DO NOT merge.
- DO NOT deploy.
- DO NOT access or mutate production KARMO data.
- DO NOT apply the staged PostgreSQL migration.
- DO NOT change Tailscale, firewall, SSH, systemd, PostgreSQL, Qdrant, Ollama, secrets, or production configuration.
- DO NOT weaken tests or governance to make CI pass.
- DO NOT trust comments, prior assistant claims, or filenames as proof. Verify behavior from code + tests + exact-SHA CI evidence.
- KARMO remains the authority. Models are reviewers/workers, never sources of authorization.
- ChatGPT, Claude, and Flash 4.1 are independent reviewers/verifiers under KARMO policy; none may grant authority or bypass Core.

## Required review sequence

1. Read the authoritative control documents first: Master Index, latest Dashboard/Project Save, CURRENT_STATE with the documented 2026-09-11 supersession rule, Engineering Invariants, SYSTEM_FIT_REVIEW, VALIDATION_LADDER, AUTONOMOUS_EXECUTION_CONTRACT, Core v2 specification/threat model/test strategy, Worker security review/network plan, Tool/Capability Registry design/proposal, and all `docs/review/` artifacts on the candidate branch.
2. Confirm exact code candidate `0359ac8610292e2341f5b31aba688703e6ad22c8`. Inspect commits after it. Continue only if later changes are review-only documentation under `docs/review/**`; otherwise report `NEEDS_VERIFICATION — CODE SHA MOVED`.
3. Compare the exact code candidate to `main`. Enumerate every changed code/test/workflow/migration file and classify each change as Core authority, persistence, Worker security, routing/verification, CI/test, deployment/review artifact, or other.
4. Run all available isolated test suites against the exact code candidate. Record exact commands, totals, failures, and environment. Do not silently skip a failing suite.
5. Reproduce the Worker portability checks already required by prior review: trusted interpreter fallback, payload cannot choose interpreter, subprocess env allowlisting, truthful Darwin/arm64 detection, and truthful GitHub/Linux x86_64 detection.
6. Attack authority boundaries: model-owned authority, caller-supplied approval requirements, dispatcher bypass, unregistered-tool execution, stale approval reuse, wrong executor, changed arguments, approval replay, self-verification, reachability-as-authorization, or direct paths around Core.
7. Attack persistence/restart semantics: schema conflicts, partial transactions, stale writers, unsafe defaults, missing unique/foreign-key/check constraints, replay/idempotency defects, restart loss, migration ordering, rollback safety, connection ownership, and ledger gaps.
8. Attack the new approval execution-claim boundary in detail:
   - approval must be APPROVED before claim;
   - exact tool/version/arguments/executor must match;
   - authority claim and invocation STARTED record must be one DB transaction;
   - duplicate idempotency key must roll back the claim rather than consume approval;
   - CLAIMED approval cannot be cancelled, approved again, or executed a second time;
   - handler failure must end as FAILED;
   - process loss after side effect but before final commit must remain an unfinished/unknown outcome and MUST NOT silently replay;
   - stale in-memory approval cache must refresh from durable truth after coordinated completion;
   - expiry handling must be durable and not accidentally rolled back by exception semantics.
9. Attack task/event recovery in detail:
   - optimistic `state_version` must reject stale writers;
   - RUNNING or VERIFYING after restart must move to RECOVERY_REQUIRED, never directly to READY/RUNNING;
   - task state transition and recovery event must commit atomically when PostgreSQL recovery store is used;
   - `event_key` must prevent duplicate recovery events;
   - unfinished invocation must reconcile to its task without replay;
   - unfinished invocation with missing task, no task_id, or conflicting terminal/queued task state must fail closed;
   - repeated startup recovery must be stable/idempotent;
   - RECOVERY_REQUIRED cannot silently jump back to RUNNING.
10. Attack Worker security: credential forgery/replay/rotation, execution-ticket tampering/replay/expiry, result forgery, environment leakage, symlink/path escape, arbitrary commands, network exposure, coordinator spoofing, worker impersonation, resource exhaustion, stale leases, result/evidence size bypass, and executor-binding failures.
11. Attack model routing and verification: provider lock-in, hidden provider authority, unavailable verifier behavior, producer/verifier identity reuse, evidence substitution, digest mismatch, and false-success paths. Confirm the design can support ChatGPT + Claude + Flash 4.1 as independent reviewers without giving any reviewer authority.
12. Inspect CI for false-green conditions: path filters, skipped jobs, architecture assumptions, missing dependency setup, test omissions, permissive `continue-on-error`, branch/SHA mismatch, or tests that only inspect source text rather than runtime behavior.
13. Add adversarial tests only when needed to prove a real defect or close a real coverage gap. Keep fixes on staging only; never touch `main`.
14. Review the deployment/rollback template and `KARMO_TODAY_COMPLETION_PLAN.md`, but do not execute them.

## Mandatory adversarial cases

At minimum prove or explicitly mark unverified:

- unregistered capability cannot execute;
- READ cannot smuggle write/external authority;
- approval requirement cannot be lowered by manifest/caller;
- approval binds exact tool/version/arguments/executor and cannot be consumed twice;
- expired/denied/cancelled/wrong-executor approval cannot execute;
- CLAIMED approval is not reusable;
- producer cannot self-verify when independent verification is required;
- verifier unavailability fails/defer according to policy, never silent self-verification;
- stale task writer is rejected;
- restart of RUNNING/VERIFYING work produces RECOVERY_REQUIRED and no auto-replay;
- task recovery state + event are transactionally coupled in the PostgreSQL path;
- unfinished invocation is visible after restart and never assumed safe to retry;
- duplicate invocation idempotency key cannot cause duplicate side effect;
- path traversal and symlink escape are refused;
- subprocess env does not inherit tokens/cloud creds/SSH agent/PYTHONPATH/unrelated secrets;
- payload cannot choose shell/executable/Python/network destination/arbitrary command;
- Worker credential proof rejects tampering/replay;
- execution ticket rejects changed task/worker/arguments/TTL/signature/replay;
- result authenticity rejects tampered output/signature/worker identity;
- CI passes on the architecture it claims to support without falsifying hardware identity.

## Exact-SHA CI evidence expected

For `0359ac8610292e2341f5b31aba688703e6ad22c8`, GitHub Actions should show both:

- `Core Productionization` — success
- `KARMO Full Predeploy` — success

Verify this yourself; do not trust this document as evidence.

## Required final report

Produce a concise but complete table:

| Severity | File:line | Finding | Exploit/failure path | Required fix | Test/evidence | Status |
|---|---|---|---|---|---|---|

Severity is one of `BLOCKER`, `HIGH`, `MEDIUM`, `LOW`.

Then report:

- exact reviewed code SHA;
- any later review-only documentation commits observed;
- test commands and pass/fail totals;
- whether CI evidence matches that exact code SHA;
- unresolved security gaps;
- unresolved persistence/restart gaps;
- any governance conflict;
- whether the candidate preserves `Kamara -> KARMO -> controlled models/tools`, not `Kamara -> model -> infrastructure`;
- whether reviewer roles preserve `KARMO authority -> ChatGPT / Claude / Flash 4.1 independent verification`;
- one final verdict only: `NOT READY`, `READY FOR KARMO REVIEW`, or `NEEDS_VERIFICATION`.

Do not use `READY FOR KARMO REVIEW` if any BLOCKER/HIGH finding is unresolved, exact-SHA CI is red/unknown, or a required security property is assumed rather than tested.
