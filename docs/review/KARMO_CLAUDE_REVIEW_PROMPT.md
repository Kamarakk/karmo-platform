# Claude Review Prompt — KARMO Full Predeploy Exact-SHA Gate

You are the independent adversarial reviewer for KARMO. Review the candidate branch `staging/karmo-full-predeploy-20260912` as untrusted candidate code. Treat `main` and the authoritative KARMO records as reference truth.

## Exact code candidate to verify before any new build stage

`e69f0dfd97a3c0b9ab58dba985a97beadb3917dd`

This is the **code-bearing candidate SHA** containing last night's staged build plus the Worker portability fixes. The branch may contain newer commits that modify only `docs/review/**` to prepare today's review/completion process. Newer review-only documentation does not invalidate the code SHA. If any commit after the code SHA changes application code, tests, workflow logic, migrations, or any non-review artifact, stop and report `NEEDS_VERIFICATION — CODE SHA MOVED` and identify the first such commit.

## Non-negotiable boundaries

- DO NOT merge.
- DO NOT deploy.
- DO NOT access or mutate production KARMO data.
- DO NOT change Tailscale, firewall, SSH, systemd, PostgreSQL, Qdrant, Ollama, secrets, or production configuration.
- DO NOT weaken tests or governance to make CI pass.
- DO NOT trust comments, prior assistant claims, or filenames as proof. Verify behavior from code + tests + exact-SHA CI evidence.
- KARMO remains the authority. Models are reviewers/workers, never sources of authorization.

## Required review sequence

1. Read the authoritative control documents first: Master Index, latest Dashboard/Project Save, CURRENT_STATE with the documented 2026-09-11 supersession rule, Engineering Invariants, SYSTEM_FIT_REVIEW, VALIDATION_LADDER, AUTONOMOUS_EXECUTION_CONTRACT, Core v2 specification/threat model/test strategy, Worker security review/network plan, Tool/Capability Registry design/proposal, and all `docs/review/` artifacts on the candidate branch.
2. Confirm the exact code candidate `e69f0dfd97a3c0b9ab58dba985a97beadb3917dd`. Inspect commits after it. Continue only if later changes are review-only documentation under `docs/review/**`; otherwise report `NEEDS_VERIFICATION — CODE SHA MOVED`.
3. Compare the exact code candidate to `main`. Enumerate every changed code/test/workflow/migration file and classify each change as Core authority, persistence, Worker security, routing/verification, CI/test, deployment/review artifact, or other.
4. Run the available isolated test suites against the exact code candidate. Record exact commands, totals, failures, and environment. Do not silently skip a failing suite.
5. Reproduce and specifically verify the portability fixes for:
   - trusted Python interpreter selection when `worker-runtime/venv/bin/python` is absent;
   - no job/user payload can choose the interpreter;
   - subprocess environment allowlisting still strips secrets/arbitrary ambient variables;
   - KARMO-DEV01 `Darwin/arm64` remains truthfully detected;
   - GitHub/Linux `x86_64` is truthfully detected without pretending to be Apple Silicon.
6. Attack authority boundaries: model-owned authority, caller-supplied approval requirements, dispatcher bypass, unregistered-tool execution, stale approval reuse, wrong executor, changed arguments, approval replay, self-verification, reachability-as-authorization, or any direct path around Core.
7. Attack persistence design: schema conflicts, partial transactions, unsafe defaults, missing unique/foreign-key/check constraints, replay/idempotency defects, restart loss, stale state recovery, migration ordering, rollback safety, connection ownership, and ledger gaps.
8. Attack Worker security: credential forgery/replay/rotation, execution-ticket tampering/replay/expiry, result forgery, environment leakage, symlink/path escape, arbitrary commands, network exposure, coordinator spoofing, worker impersonation, resource exhaustion, stale leases, result/evidence size bypass, and executor-binding failures.
9. Attack model routing and verification: provider lock-in, hidden provider authority, unavailable verifier behavior, producer/verifier identity reuse, collusion by configuration, evidence substitution, digest mismatch, and false-success paths.
10. Inspect CI configuration itself for false-green conditions: path filters, skipped jobs, architecture assumptions, missing dependency setup, test selection omissions, permissive `continue-on-error`, and branch/SHA mismatch.
11. Add adversarial tests only when needed to prove a real defect or close a real coverage gap. Keep all proposed fixes on the staging branch; never touch `main`.
12. Review the proposed deployment/rollback template and `KARMO_TODAY_COMPLETION_PLAN.md` for missing safety gates, but do not execute either.

## Mandatory adversarial cases

At minimum prove or explicitly mark unverified:

- unregistered capability cannot execute;
- READ capability cannot smuggle write/external authority;
- approval requirement cannot be lowered by manifest or caller;
- approval binds exact tool/version/arguments/executor and cannot be consumed twice;
- expired/denied/wrong-executor approval cannot execute;
- producer model cannot verify its own work when independent verification is required;
- verifier unavailability fails according to policy rather than silently self-verifying;
- path traversal and symlink escape are refused;
- subprocess env does not inherit tokens, cloud credentials, SSH agent variables, arbitrary PYTHONPATH, or unrelated ambient secrets;
- job payload cannot choose shell, executable, Python binary, network destination, or arbitrary command;
- Worker credential proof rejects tampering and replay according to the currently implemented policy;
- execution ticket rejects changed task/worker/arguments/TTL/signature and replay;
- result-authenticity binding rejects tampered output/signature/worker identity;
- persistent-state design has no obvious duplicate-execution or orphaned-approval path across restart;
- CI passes on the architecture it claims to support without falsifying hardware identity.

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
- one final verdict only: `NOT READY`, `READY FOR KARMO REVIEW`, or `NEEDS_VERIFICATION`.

Do not use `READY FOR KARMO REVIEW` if any BLOCKER/HIGH finding is unresolved, exact-SHA CI is red/unknown, or a required security property is assumed rather than tested.
