# Claude Code instructions for KARMO

Before consequential KARMO work, read `AI_START_HERE.md` and follow its bootstrap/read order. It is the durable context entry point; authoritative state and governance remain in the files it references.

You are the implementation agent in an isolated development/test environment.

1. Read `AGENTS.md`, the relevant hardening design, and the issue acceptance criteria before editing.
2. Change only the active feature branch.
3. Keep edits small and deterministic. Run targeted tests, then provide a pull request with evidence.
4. Production access (SSH, Docker sockets, production databases, Qdrant, secrets, real documents, customer data) is prohibited by default. It may be used only under an explicit, task-specific Production Access Authorization from Natalie, per the Mandatory Production Access Authorization Gate in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` — never on the basis of a general workload or session approval alone, and never for anything beyond exactly what that authorization grants (a read-only grant never implies write authority).
5. Do not create autonomous schedules, GitHub Actions, or external integrations without Natalie’s written approval.
6. Stop and report a blocker instead of bypassing a test, inventing a requirement, or changing frozen scope.
7. Before implementation begins, comply with `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (I-01 through I-09) -- the single source of truth for KARMO's permanent engineering invariants, not duplicated here. Complete its Mandatory Phase Invariant Impact Review for any non-trivial phase/feature/service/migration/agent/integration/deployment before substantial implementation.
8. No work session, phase, or workload is complete until PROJECT SAVE has been performed, per the Mandatory Project Save Completion Rule in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. Report `PROJECT SAVE: COMPLETE` (updated files, commit hash, stopping point, next action) once committed, or `PROJECT SAVE PENDING` if work stops before a commit/PR boundary.
