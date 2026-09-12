# KARMO Review Prompt — Full Predeploy Candidate

Review `staging/karmo-full-predeploy-20260912` as the system owner/control authority. Do not merge or deploy merely because implementation tests pass.

Recover authoritative project state first. Then evaluate the exact candidate SHA against KARMO's invariants, System-Fit Review, approval model, access boundaries, current production topology, Core/Worker architecture, and evidence hierarchy.

For every staged component determine:

- goal served;
- existing capability reused;
- new software/service/schema/network surface introduced;
- verified current-system facts it depends on;
- duplication/conflict risk;
- lifecycle/maintenance cost;
- security and authority consequences;
- failure/fallback behavior;
- simpler alternative;
- decision: `PROCEED`, `PROCEED WITH CONSTRAINTS`, `DEFER`, `REJECT`, or `NEEDS_VERIFICATION`.

Specifically verify that KARMO retains ownership of task state, capability registration, approval, dispatch, worker authorization, verification evidence, and durable audit. Models must remain replaceable resources, and no model/provider may become an authority or credential holder.

Check the five pre-network Worker blockers, execution-ticket design, coordinator persistence, result authenticity, environment isolation, symlink proof, TLS/coordinator-auth assumptions, worker credential rotation, and outbound-only Worker topology.

Require exact-SHA CI evidence and independent Claude security-review results. If any material production fact is unknown, return `NEEDS_VERIFICATION` instead of inferring it.

Output unresolved blockers and the exact next safe action. Deployment remains separately approval-gated by Kamara.
