# Spec Kit Brownfield Initialization Plan

Status: **approved for integration preparation. Not initialized.**
Formalizes the inspection performed earlier in this reconciliation
(GitHub Spec Kit v1.0.4, brownfield/existing-project path) as a persistent
plan, per Phase 7 of the foundation-acceleration instruction. Nothing in
this document authorizes running `specify init` — that remains a separate,
explicit approval (see Workload 4 in
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`).

## Governance hierarchy

Spec Kit operates strictly beneath existing KARMO governance. This is the
binding order, not a suggestion:

```
Kamara's explicit instructions
        ↓
AGENTS.md / CLAUDE.md
        ↓
docs/governance/KARMO_ENGINEERING_INVARIANTS.md
        ↓
docs/project-state/ (persistent project state)
        ↓
approved KARMO architecture/plans (docs/vision/, docs/architecture/, docs/plans/)
        ↓
Spec Kit specifications/plans/tasks (.specify/, specs/)
        ↓
implementation
```

Spec Kit's constitution (`.specify/memory/constitution.md`, once created)
must explicitly encode this hierarchy by referencing the invariants
document — it must never restate, weaken, or compete with it.

## Inspection findings (verified this session, no repo changes)

- **Version:** GitHub Spec Kit v1.0.4 (latest tagged release as of
  2026-09-02); pin to this tag rather than `@main`.
- **Files added for `--integration claude`:** `.specify/memory/constitution.md`,
  `.specify/templates/`, `.specify/scripts/`, `.claude/skills/speckit-*/SKILL.md`
  (one per command). `specs/NNN-<slug>/` directories are created only when
  `/speckit.specify` is run for an actual feature.
- **AGENTS.md / CLAUDE.md:** confirmed, by reading the `ClaudeIntegration`
  source directly, that the Claude Code integration does **not** write to
  either file (no `context_file` configured; that behavior exists only for
  other, unused integrations and an opt-in `agent-context` extension this
  plan does not add).
- **Constitution mechanism:** a plain Markdown file
  (`.specify/memory/constitution.md`) filled from a placeholder template; a
  convention enforced by later `/speckit.plan`/`/speckit.analyze` prompts,
  not a code-level gate.
- **Brownfield support:** officially documented and recommended path —
  `specify init --here --force --integration claude` on a dedicated,
  reviewable branch, after committing/stashing existing work. `--force` is
  required only because the repo is non-empty overall; it does not delete
  anything outside Spec Kit's own managed paths.
- **No collision found:** no existing file, directory, or branch in this
  repository uses Spec Kit's naming (`specs/`, `.specify/`, `specify`).
  KARMO's `hNN`/`feat/hNN-<slug>` convention is a distinct namespace;
  recommend feature slugs like `specs/001-h05-<name>` to keep phase
  correlation visible.
- **Overwrite risk:** confined to a *future* forced refresh
  (`specify init --here --force` run again later to pick up a newer Spec Kit
  release), which can overwrite `.specify/memory/constitution.md` and any
  customized `.specify/templates/`/`.specify/scripts/` — mitigated by
  keeping these under normal git version control so any future refresh
  shows as a reviewable diff. The first init carries no such risk since none
  of these paths exist yet.

## Exact initialization command (prepared, not executed)

```bash
# Prerequisite (local machine, not a repo change): install uv if not present.
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.4

# On a dedicated branch, from the repo root, with a clean working tree:
git checkout -b feat/h05-spec-kit-adoption
specify init --here --force --integration claude
```

Immediately after, review `git status`/`git diff` and confirm only
`.specify/` and `.claude/skills/` appeared — this is itself part of the
acceptance criteria for Workload 4, not merely a sanity check.

## Constitution content plan

`/speckit.constitution` should be run with content equivalent to:

> This constitution is subordinate to
> `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (I-01–I-09), which
> remains KARMO's single source of truth for permanent engineering
> invariants and governs in any conflict. Every feature plan under this
> workflow must complete that document's Mandatory Phase Invariant Impact
> Review before implementation begins. This constitution supplements — and
> never overrides — `AGENTS.md`, `CLAUDE.md`, and the invariants document.
> Validation follows `docs/governance/KARMO_VALIDATION_LADDER.md`.
> Autonomous execution within an approved workload follows
> `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`.

Base any additional principles on what the repository's own conventions
already demonstrate (the "no overlapping suites" testing rule, the
isolated-before-production pattern, report-only-by-default for audit tools)
— not on invented standards, per Spec Kit's own brownfield guidance.

## What this plan does not authorize

- Running `specify init` (Workload 4 requires Kamara's separate,
  explicit go-ahead for that specific action).
- Retroactively converting H0.0–H0.4 into Spec Kit `specs/` artifacts.
- Any Spec Kit extension beyond the `claude` integration (e.g. the
  `agent-context` extension, which would touch AGENTS.md-style files) —
  out of scope unless separately proposed and approved.
