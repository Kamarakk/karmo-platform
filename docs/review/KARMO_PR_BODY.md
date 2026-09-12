# Draft PR Summary — KARMO Full Predeploy

## Purpose

Stage the remaining safe/reviewable KARMO control-plane work in one isolated branch for Claude + KARMO review. This PR must remain draft until Kamara makes a separate promotion decision.

## Current scope

- KARMO-owned capability registry and shared dispatcher.
- Durable task-state model and PostgreSQL substrate.
- Model-agnostic routing and independent verification gate.
- Worker credential/execution-ticket/result-authenticity primitives.
- Worker subprocess environment allowlisting and symlink-escape regression proof.
- Dedicated CI regression workflow.
- Review, deployment, context-handoff and morning-gate artifacts.

## Explicitly not authorized

No merge, production access, deployment, migration execution, network/firewall change, secret rotation, external customer/marketplace action, live finance execution, or authoritative project-state rewrite.

## Required gates

1. exact-SHA CI;
2. Claude adversarial code/security review;
3. KARMO System-Fit/invariant review;
4. all blockers resolved;
5. Kamara explicit merge/promotion decision;
6. separate task-specific production deployment authorization with rollback.

See `docs/review/README.md` and `docs/review/KARMO_PREDEPLOY_STATUS.md` for the live branch-local review pack.
