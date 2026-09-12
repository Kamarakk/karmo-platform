# KARMO Full Predeploy Staging

Status: **STAGING ONLY — NOT APPROVED FOR MERGE OR DEPLOYMENT**

Purpose: collect the remaining safe, reviewable KARMO engineering work in one isolated GitHub branch so Claude and KARMO can perform correction/security review before any merge or deployment decision.

## Hard boundaries

- `main` remains untouched by this staging program.
- No production host access, deployment, service restart, firewall/network change, secret rotation, or live database/vector-store mutation is authorized by this branch.
- No pull request from this branch is authorized to merge automatically.
- KARMO Core remains the authority boundary. Models are replaceable compute/review resources and cannot grant authority.
- Live finance trade execution, destructive actions, and customer/marketplace external actions remain separately governed and are not enabled here.
- Existing authoritative `docs/project-state/` records are not rewritten by this staging branch without separate explicit approval.

## Staging targets

1. Production-shaped Tool/Capability Registry.
2. Durable KARMO task state and PostgreSQL schema.
3. Persistent approval/invocation substrate.
4. Shared Core dispatcher that refuses unregistered tools and enforces approval.
5. Model-agnostic model router with independent-verifier selection.
6. Independent verification gate and evidence binding.
7. Worker Runtime security blocker closure before any real network transport.
8. Coordinator persistence and execution-ticket/result-authenticity design implementation.
9. Low-risk KarmoLab/read-only proving capabilities.
10. Safe internal domain scaffolding that uses the same Core capability interface.
11. CI, adversarial tests, rollback/deployment artifacts for reviewer inspection.

## Review order tomorrow

1. Claude code/security review.
2. KARMO architecture/invariant review against authoritative records.
3. Resolve every blocker or contradiction.
4. Re-run CI and independent verification.
5. Kamara makes a separate merge/promotion decision.
6. Only after merge approval: produce a separate deployment authorization and rollback plan.

## Current staged work

- `core_service.registry`: closed-schema KARMO-owned capability registry.
- `core_service.task_state`: durable task-state model matching the handoff fields.
- `core_service.model_router`: model-agnostic routing with self-verification refusal.
- `core_service.verification`: independent result verification records.
- `core_service.dispatcher`: one shared invocation path behind registry + approval.
- `core_service.persistence`: PostgreSQL adapters with injected connection ownership.
- `core_service/migrations/001_core_v2_substrate.sql`: staged tables for registry, invocation ledger, approvals, tasks, and task events.

This file is a review/staging artifact, not an authoritative statement that any staged component is production-approved or deployed.
