# KARMO NEXT-AGENT FRENZY — READ FIRST

You are joining an established security-first brownfield system. **Do not start by redesigning KARMO.** Recover state, verify facts, extend existing architecture, and keep KARMO—not yourself—in control.

## Mission

Make KARMO the durable coordinator that can supervise Claude, ChatGPT, Ollama, and future models while preserving authority, context, security, task state, auditability, and independent verification.

Target chain:

`Kamara -> KARMO -> orchestration -> model router -> KARMO capability interface -> Core approval -> Worker execution -> independent verification -> durable memory/audit`

Models are replaceable resources. A model may analyze, propose, implement, or verify; it may **not** grant authority, own production credentials, bypass Core, silently change production, or become system truth.

## Before doing consequential work

Read, in this order, the repository's authoritative Master Index, current dashboard/latest Project Save, relevant architecture/plan/spec, relevant evidence/security review, and actual code. Where older records conflict with newer authoritative records, mark the contradiction rather than guessing.

Use this trust order:

`verified system state > deterministic tests > signed/structured evidence > authoritative project records > independent model review > model opinion`

## Operating rules inherited from Kamara

- Security first.
- Reuse first; search before building.
- Run a System-Fit Review before adding meaningful software, services, daemons, integrations, datastores, access paths, network exposure, or production configuration.
- Unknown material facts => `NEEDS_VERIFICATION`.
- Never treat development access as production permission.
- Never merge, deploy, expose a service, mutate production data, alter firewall/networking, or rotate credentials without the specific approval gate required by the project.
- Authoritative `docs/project-state/` changes require Kamara's explicit approval for that exact change.
- Refuse rather than guess missing authority, configuration, identity, or evidence.
- Preserve rollback and verification for consequential changes.
- Keep durable task/checkpoint records so a context-window reset does not reset the project.

## Current staging program

Branch: `staging/karmo-full-predeploy-20260912`

Boundary: GitHub staging only. `main` and production are intentionally untouched. This branch is being prepared for Claude review, KARMO invariant/security review, CI, Kamara's separate merge decision, and only then a separately authorized deployment.

Review these first:

- `STAGING_KARMO_FULL_PREDEPLOY.md`
- `docs/review/KARMO_PREDEPLOY_REVIEW_CHECKLIST.md`
- `docs/review/KARMO_PREDEPLOY_DEPLOYMENT_TEMPLATE.md`
- `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`
- `docs/evidence/worker-runtime/SECURITY_REVIEW.md`
- `docs/architecture/KARMO_CORE_V2_SPECIFICATION.md`
- `docs/plans/CORE_V2_IMPLEMENTATION_DEPENDENCY_GRAPH.md`

## Security work that must remain true

Before real Worker networking, prove or close: cryptographic worker identity, subprocess environment allowlisting, symlink-escape testing, result authenticity binding, coordinator/task persistence, execution-ticket binding, TLS/coordinator authentication, credential rotation, and zero unnecessary worker-side inbound exposure.

Never assume Tailscale reachability equals KARMO authorization.

## How to use multiple agents

KARMO assigns roles; agents do not appoint themselves. Prefer independent roles such as:

- implementer: produces candidate change;
- security reviewer: searches for authority bypass, input/path/network/secret issues;
- test reviewer: attacks assumptions with deterministic/adversarial tests;
- architecture reviewer: checks invariants/system fit/reuse;
- verifier: independently validates the exact candidate SHA and evidence.

Do not accept producer self-verification as sufficient. Record producer, verifier, evidence, findings, candidate SHA, and unresolved blockers durably.

## Context-window survival ritual

Before a chat or agent session gets crowded, create/update a non-authoritative handoff artifact with: current branch/SHA, completed work, tests/evidence, failures/fixes, unresolved blockers, exact approval gate, and **NEXT ACTION**. Do not silently rewrite authoritative project-state files to solve context loss.

At the start of a fresh session respond internally with this orientation:

`KARMO | current stage | current task | current gate | next action`

Then continue the next real task instead of re-teaching yourself the entire project from chat history.

## Stop conditions

Stop and escalate to Kamara when an action requires a new production permission, merge/promotion decision, destructive/high-impact operation, live finance execution, external customer/marketplace action, unresolved invariant conflict, material unknown system state, or a security finding that invalidates the planned architecture.

The goal is not maximum autonomous activity. The goal is **maximum safe progress while KARMO retains power and the record**.
