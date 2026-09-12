# KARMO Same-Day Completion Plan — Large-Chunk Build / Independent Review / Kamara Approve / Deploy

Status: branch-local execution plan for `staging/karmo-full-predeploy-20260912`. This file does not itself authorize merge or production deployment.

## Objective

Reach a **usable KARMO operational v1** today without bypassing governance. “Usable v1” means Kamara can give KARMO a bounded task, KARMO owns the durable record and authority decision, KARMO can route work to an approved model/Worker path, collect evidence, require independent verification when policy says so, survive process restart without silently losing control state, and execute at least one low-risk KarmoLab READ capability end-to-end.

This does **not** mean every future product domain is finished today. Voice streaming, live broker execution, high-impact administration, BloomBoss external/customer actions, and other separately governed domains remain later tracks unless independently approved.

## Three-reviewer verification policy

For consequential KARMO code, security, architecture, promotion, and deployment-candidate review, KARMO will use a three-reviewer layer:

- **ChatGPT** — independent architecture/security/system-fit verification;
- **Claude** — independent adversarial code review and test verification;
- **Flash 4.1** — independent third reviewer/verifier.

All three reviewers operate **under KARMO authority**. None may grant authority, approve its own infrastructure access, own KARMO credentials, bypass Core/dispatcher/approval policy, or become the source of durable task truth. A producer model must not satisfy its own independent-verification requirement. KARMO records reviewer identity, evidence, findings, disagreements, and final policy outcome. Kamara remains the human promotion/deployment authority where explicit approval is required.

Target authority chain:

`Kamara -> KARMO -> producer/worker -> ChatGPT + Claude + Flash 4.1 independent review -> KARMO evidence/policy evaluation -> Kamara approval where required -> deployment`

DeepSeek is not assigned this dedicated three-reviewer role unless separately approved later.

## Operating rule

Work in **large coherent chunks**, not tiny feature fragments:

`BUILD LARGE CHUNK -> TEST -> THREE-REVIEWER VERIFICATION -> FIX BLOCKERS -> KARMO REVIEW -> KAMARA APPROVAL -> DEPLOY/VERIFY -> NEXT CHUNK`

No merge/deploy occurs merely because tests pass. Kamara approval remains a separate gate.

---

# Gate 0 — Verify Last Night's Candidate Before New Feature Work

Candidate source: PR #36, `staging/karmo-full-predeploy-20260912`.

### Required

1. Exact-SHA GitHub CI green for Core, Core-v2 regression, and Worker tests.
2. Claude executes `docs/review/KARMO_CLAUDE_REVIEW_PROMPT.md` against the exact candidate SHA.
3. Resolve every BLOCKER/HIGH finding on the staging branch.
4. Rerun exact-SHA CI after fixes.
5. Claude verdict must be `READY FOR KARMO REVIEW` before moving to the next major build chunk.
6. KARMO/System-Fit review verifies no authority inversion, duplicate control plane, or unsupported production assumption.
7. Before promotion/deployment, ChatGPT, Claude, and Flash 4.1 each provide an independent review result or KARMO records a policy-approved unavailable/defer outcome; no reviewer may silently substitute for another.

### Stop conditions

- SHA moved without re-review.
- red/unknown CI.
- unresolved BLOCKER/HIGH.
- model can bypass Core/dispatcher/approval.
- persistence semantics are guessed rather than proven.
- deployment/rollback cannot be described deterministically.

---

# Chunk 1 — Durable KARMO Control Plane v1

## Goal

Make KARMO's authority/task record survive restart and become the durable center of orchestration.

## Build as one integrated chunk

### A. Persistent Capability Registry + Invocation Ledger

- production-shaped PostgreSQL-backed capability registry;
- append/audit-safe registration lifecycle;
- closed manifest validation;
- computed approval requirement only;
- immutable invocation record containing task, tool/version, requester, model/worker identity, arguments digest, authority decision, timestamps, result/evidence digest, verification state, and terminal state;
- idempotency/replay protection;
- indexes/constraints for expected lookup paths;
- transaction boundaries documented and tested.

### B. Persistent Approval Engine

Persist:

- approval_id;
- exact tool/version/arguments digest;
- requester;
- approver;
- authorized executor;
- authority class;
- creation/expiry;
- state transitions;
- execution binding;
- audit trail.

Must prove:

- approval survives Core restart;
- expired approvals do not revive;
- consumed approval remains single-use after restart;
- changed args/tool/version/executor fail closed;
- denial/cancellation persist;
- approval and associated execution transition cannot drift into contradictory state.

### C. Persistent Task / Event / Job State

Persist a KARMO-owned task record including:

- task_id;
- objective/requester;
- risk/authority classification;
- allowed capabilities;
- state;
- selected model/tool/Worker;
- input/evidence references;
- approvals;
- actions/checkpoints;
- failures/retries;
- verification result;
- rollback metadata;
- final result;
- next_action.

Must prove restart recovery for queued, awaiting-approval, running/leased, verification-pending, failed, and terminal tasks.

### D. Shared Dispatcher Enforcement

All real capability invocation must pass through one Core-owned path:

`Task -> Registry -> Computed Authority -> Approval Gate -> Dispatcher -> Executor/Worker -> Ledger`

Refuse:

- unknown tool/version;
- stale/deprecated tool where policy forbids it;
- changed argument digest;
- wrong executor;
- bypass invocation;
- missing approval;
- expired/consumed approval;
- tool authority mismatch.

### E. Restart/Recovery Adversarial Suite

Test process restart/crash at critical boundaries:

1. after task creation, before approval;
2. after approval, before execution;
3. after execution starts, before result ack;
4. after Worker result, before Core terminal commit;
5. after verification result, before task completion;
6. stale lease reclaimed by a different Worker;
7. replay of prior approval/ticket/result after restart;
8. duplicate submit with same idempotency key;
9. DB transaction interruption.

## Exit gate

- all targeted tests green;
- no in-memory-only authority state remains for the production path;
- three-reviewer policy satisfied for the promotion candidate;
- KARMO review confirms this extends the existing architecture rather than creating a competing control plane.

---

# Chunk 2 — Secure Worker Coordination + Real Transport Readiness

## Goal

Make Worker execution safe enough for real KARMO-controlled use while preserving Core authority.

## Build as one integrated chunk

### A. Worker cryptographic identity

- proof-of-possession worker credential;
- key/version identity;
- bounded validity;
- rotation semantics;
- replay resistance;
- coordinator verifies identity on every sensitive transport action, not only registration.

### B. Execution tickets

Replace callable-across-network assumptions with data-only authorization:

- short-lived signed ticket;
- bound to approval_id, task_id, tool/version, arguments digest, worker_id, expiry, nonce/ticket id;
- single-use/replay refusal;
- wrong worker/task/args refused.

### C. Result authenticity

- Worker-bound result signature/MAC over canonical result/evidence digest + task/ticket identity;
- coordinator verifies before accepting result;
- tampered output/evidence/wrong worker refused;
- authenticity failure never becomes successful terminal task state.

### D. Worker coordinator persistence

Durably persist enough state to recover:

- workers/identity metadata;
- leases/claim tokens;
- pending/awaiting approval jobs;
- execution-ticket issuance/consumption;
- result submission status;
- retry/recovery metadata.

### E. Transport security design/implementation gate

Prefer existing Tailscale path and outbound-only Worker connections. Before enabling a real network Worker transport, prove:

- coordinator authentication;
- encrypted transport;
- no Worker inbound listener required;
- network reachability never grants KARMO authority;
- transport cannot choose arbitrary commands/capabilities;
- timeout/backoff/reconnect behavior is bounded.

## Exit gate

- Worker restart/replay/tamper tests green;
- credential/ticket/result primitives are actually wired, not just library helpers;
- three-reviewer verification passes for the promotion candidate;
- no new firewall exposure or production networking is required merely to prove the code.

---

# Chunk 3 — KARMO Model Router + Independent Verification + KarmoLab First Real Capability

## Goal

Demonstrate the complete KARMO-owned loop with a useful low-risk capability.

## Model routing

KARMO owns provider/model choice from policy/capability requirements. A model never gains authority by being selected.

Required behavior:

- provider-agnostic model descriptor;
- capability/availability routing;
- explicit producer identity;
- verifier identity distinct when independent verification required;
- dedicated independent reviewer pool includes ChatGPT, Claude, and Flash 4.1 for consequential review;
- verifier unavailable -> policy-defined fail/defer, never silent self-verification;
- routing decision written to task/ledger;
- model output treated as evidence/proposal until KARMO policy accepts it.

## KarmoLab READ proving capability

Implement only READ-class infrastructure visibility first. Candidate bounded capabilities:

- host identity/health summary;
- CPU/memory/disk status;
- service status;
- Docker/container status;
- repo/system-state inspection;
- existing KARMO service health endpoints.

Must not include in this first proving slice:

- restart service;
- edit config;
- delete files/data;
- firewall/network change;
- package install;
- production DB writes;
- secret reads;
- arbitrary shell;
- unrestricted filesystem traversal.

### End-to-end proof

Prove:

`Kamara request -> KARMO task -> registry -> model/router if needed -> Core decision -> READ tool -> Worker -> evidence -> independent verification -> durable task completion`

Then restart the relevant Core process in isolated/dev test context and prove the task/evidence record remains coherent.

## Exit gate

- exact-SHA CI green;
- ChatGPT + Claude + Flash 4.1 independent review policy satisfied;
- KARMO review confirms authority and domain separation;
- KarmoLab READ result is useful and bounded.

---

# Chunk 4 — Deployment Candidate + Controlled Production Rollout

## Goal

Deploy only the reviewed operational v1 subset.

## Pre-deploy package

For every production change specify:

- WHAT;
- WHY;
- exact CHANGE;
- RISK;
- VERIFY;
- ROLLBACK;
- pre-change evidence;
- exact candidate SHA;
- schema migration order if any;
- expected service restarts;
- expected health checks;
- hard abort conditions.

## Required order

1. freeze exact deployment candidate SHA;
2. exact-SHA CI green;
3. ChatGPT independent architecture/security review;
4. Claude final adversarial code/test review;
5. Flash 4.1 independent third review;
6. KARMO System-Fit/invariant evaluation of all evidence;
7. resolve every blocker/high;
8. rerun exact-SHA CI after fixes;
9. Kamara explicitly approves merge/promotion;
10. merge approved candidate only;
11. Kamara separately approves production deployment scope;
12. capture production preflight/read-only state;
13. backup/rollback artifacts where needed;
14. apply only approved migration/config/code changes;
15. verify Core health;
16. verify Worker health;
17. verify existing PostgreSQL/Qdrant/Ollama/KARMO services unaffected;
18. run bounded KarmoLab READ end-to-end smoke test;
19. verify durable task/approval/invocation record;
20. if any invariant/health check fails, rollback and stop.

---

# Definition of “KARMO usable today”

KARMO is usable when all are true:

- KARMO owns durable task truth;
- KARMO owns capability registry/authority classification;
- approvals survive restart and are exact/single-use;
- tool calls pass the shared dispatcher;
- Workers cannot self-authorize;
- Worker identity/results are authenticated for the enabled execution path;
- models are replaceable producers/verifiers, not authority;
- ChatGPT, Claude, and Flash 4.1 are available as the dedicated independent review layer for consequential work under KARMO policy;
- independent verification is enforceable;
- at least one useful KarmoLab READ task runs end-to-end;
- task/evidence/audit history remains after restart;
- deployment has deterministic rollback;
- no voice/live-finance/high-impact-admin/external-customer-action scope is silently bundled into this milestone.

# Review cadence for today

Use three large engineering gates instead of dozens of tiny approval interruptions:

**Gate A — Last-night candidate verification**
Claude verifies PR #36 exact SHA. Fix blockers. ChatGPT/KARMO verifies architecture/system fit. Kamara decides whether candidate is accepted as today's starting substrate.

**Gate B — Large Core/Worker completion build**
Implement Chunks 1 + 2 as a cohesive staging increment where dependencies allow. Run CI and independent ChatGPT + Claude + Flash 4.1 review. Fix all BLOCKER/HIGH findings. KARMO evaluates system fit and reviewer evidence. Kamara approves or rejects promotion of the large increment.

**Gate C — Usable KARMO proof + deployment**
Implement Chunk 3 and the deployment package. Exact-SHA CI + ChatGPT + Claude + Flash 4.1 + KARMO review. Kamara explicitly approves merge, then separately approves the exact deployment scope. Deploy and verify using Chunk 4.

This keeps speed high while retaining explicit human authority over promotion and production.
