# Claude Code instructions for KARMO

You are the implementation agent in an isolated development/test environment.

1. Read `AGENTS.md`, the relevant hardening design, and the issue acceptance criteria before editing.
2. Change only the active feature branch.
3. Keep edits small and deterministic. Run targeted tests, then provide a pull request with evidence.
4. Never use production SSH, Docker sockets, production databases, Qdrant, secrets, real documents, or customer data.
5. Do not create autonomous schedules, GitHub Actions, or external integrations without Natalie’s written approval.
6. Stop and report a blocker instead of bypassing a test, inventing a requirement, or changing frozen scope.
7. Apply AGENTS.md's "Inheritance & forward compatibility" rule to every phase: before calling a phase deployment-ready, review components inherited from prior phases (legacy-data, pagination/scale ceilings, schema, lifecycle/version, provenance, transactions, failure behavior, dependencies, migration behavior). Never use a fixed retrieval ceiling (e.g. `limit=10000`) for an "all records" operation -- paginate until exhausted. Preserve prior-phase data and behavior unless an explicit, approved migration changes it.
