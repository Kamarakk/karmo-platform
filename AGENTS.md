# KARMO agent rules

## Required short status block

Start each response with:

**Key point:** one sentence.  
**Your action:** one action or `None`.  
**Safety:** `Production untouched` unless a separately approved production action occurred; otherwise state rollback reference.

Do not repeat full logs in chat. Put evidence in the pull request or `docs/evidence/` and give a concise summary.

## Authority and boundaries

- Never access or modify production KARMO from an AI session.
- Work only on a feature branch in the approved non-production workspace.
- Do not use or request secrets. Do not inspect private documents, database dumps, or real conversation data.
- Do not change the H0 phase order or frozen acceptance criteria without a documented decision approved by Natalie.
- Never merge a pull request, deploy, delete data, alter production schema, restart production services, or weaken access controls.

## Change standard

Every change must state: purpose, files changed, tests run, results, risk, verification, and rollback. A failing test blocks promotion.

## Current hardening constraints

- v0.5/H0.0 remains frozen.
- H0.1 work stays isolated until H01-T01 through H01-T18 pass.
- No legacy backfill, automatic deletion, document outbox work, worker service installation, or production migration in H0.1.

## KARMO Engineering Invariants (every phase, permanent)

`docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (I-01 through I-09) is
the single source of truth for KARMO's permanent engineering invariants
and is not duplicated here. Compliance is mandatory for every phase,
feature, service, migration, agent, integration, and deployment, and its
Mandatory Phase Invariant Impact Review must be completed **before
substantial implementation begins**, not retrofitted afterward.

## Project Save Completion (every major session/workload, permanent)

`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s Mandatory Project Save
Completion Rule is not duplicated here. No major work session, phase,
workload, deployment, configuration session, or infrastructure change is
complete until PROJECT SAVE has been performed and reported, per that
rule.
