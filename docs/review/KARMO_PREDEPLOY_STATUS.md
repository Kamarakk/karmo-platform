# KARMO Full Predeploy — Current Staging Status

This is a non-authoritative branch-local status artifact for overnight continuation and morning review.

## Branch

`staging/karmo-full-predeploy-20260912`

## Safety boundary

GitHub-only. No production access, deployment, merge, firewall/network change, live schema mutation, secret rotation, or marketplace/customer action has been performed by this staging program.

## Implemented/staged so far

- production-shaped closed-schema capability registry;
- shared Core dispatcher behind registry + existing ApprovalEngine;
- KARMO-owned durable task-state model;
- PostgreSQL substrate schema for registry, invocation ledger, approval records, tasks, and task events (file only, not applied);
- PostgreSQL capability/task adapters with injected connection ownership;
- model-agnostic router with independent-verifier exclusion;
- verification gate with canonical evidence digest;
- Worker subprocess environment allowlisting;
- explicit symlink-escape regression test;
- versioned worker proof-of-possession credential envelope;
- short-lived execution ticket bound to approval, arguments, worker, task and TTL;
- worker-bound result authenticity signature;
- Core/Worker/Core-v2 CI regression workflow;
- Claude adversarial-review prompt;
- KARMO System-Fit/invariant-review prompt;
- deployment/rollback template;
- next-agent context-window handoff/frenzy.

## Still incomplete / must not be overstated

- persistent ApprovalEngine integration is not complete;
- invocation-ledger runtime integration is not complete;
- coordinator/Worker registry/job-store persistence is not complete;
- execution tickets/result signatures are staged primitives and are not yet wired into network transport;
- credential rotation/replay policy needs end-to-end integration tests;
- no real network Worker transport is enabled;
- no TLS/coordinator-auth transport is implemented;
- KarmoLab proving tools have not yet been wired through the new dispatcher;
- BloomBoss PR #32 remains separate and unmerged;
- voice/streaming continuous-capability Core surface remains a separate large design/build track;
- live finance trade execution remains explicitly out of scope;
- no production-readiness claim is valid until exact-SHA CI + Claude review + KARMO review resolve blockers.

## NEXT ACTION

Continue closing the remaining Core/Worker persistence and integration gaps, inspect CI at the exact branch SHA, fix all failures without weakening security, then stage the lowest-risk KarmoLab end-to-end proving capability. Keep merge/deployment blocked for morning Claude + KARMO + Kamara review.
